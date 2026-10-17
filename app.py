"""Trip Optimizer — Flask API + browser frontend.

Production-minded wrapper around the existing multi-agent coordinator.
Adds input validation, SQLite persistence, safer error handling, optional
restricted CORS, and security headers while keeping the agent pipeline intact.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import traceback
import uuid
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coordinator import AgentCoordinator, AgentState  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DB_PATH = Path(os.environ.get("TRIP_DB_PATH", APP_DIR / "trip_optimizer.db"))
MAX_TRIP_DAYS = int(os.environ.get("MAX_TRIP_DAYS", "30"))

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

# Optional cross-origin support. Same-origin frontend requires no CORS at all.
allowed_origins = [x.strip() for x in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if x.strip()]
if allowed_origins:
    try:
        from flask_cors import CORS
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
    except ImportError:
        pass

LANGUAGE_OPTIONS = [
    {"code": "en", "label": "English"}, {"code": "hi", "label": "Hindi / हिंदी"},
    {"code": "mr", "label": "Marathi / मराठी"}, {"code": "ta", "label": "Tamil / தமிழ்"},
    {"code": "te", "label": "Telugu / తెలుగు"}, {"code": "kn", "label": "Kannada / ಕನ್ನಡ"},
    {"code": "ml", "label": "Malayalam / മലയാളം"}, {"code": "bn", "label": "Bengali / বাংলা"},
    {"code": "gu", "label": "Gujarati / ગુજરાતી"}, {"code": "pa", "label": "Punjabi / ਪੰਜਾਬੀ"},
]
INTEREST_OPTIONS = ["beach", "temple", "fort", "adventure", "museum", "general"]
PREFERENCE_OPTIONS = ["relaxation", "adventure", "nightlife", "photography", "general"]
TRANSPORT_OPTIONS = ["Flight", "Train", "Bus", "Car"]
HOTEL_OPTIONS = ["budget", "standard", "luxury"]
LANGUAGE_CODES = {x["code"] for x in LANGUAGE_OPTIONS}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                trip_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                days INTEGER NOT NULL,
                total_budget REAL NOT NULL,
                trip_score INTEGER NOT NULL DEFAULT 0,
                plan_json TEXT NOT NULL
            )
        """)


def state_to_json(state: AgentState) -> dict:
    data = asdict(state)
    if isinstance(data.get("route_cache"), dict):
        data["route_cache"] = {str(k): v for k, v in data["route_cache"].items()}
    return data


def state_from_json(data: dict) -> AgentState:
    allowed = {f.name for f in fields(AgentState)}
    clean = {k: v for k, v in data.items() if k in allowed}
    # Serialized tuple cache keys cannot be faithfully reconstructed; rebuilding
    # them on the next route calculation is safer than reusing malformed keys.
    clean["route_cache"] = {}
    return AgentState(**clean)


def save_trip(trip_id: str, state: AgentState, created_at: str | None = None) -> None:
    created_at = created_at or utc_now()
    payload = json.dumps(state_to_json(state), ensure_ascii=False)
    with db() as conn:
        conn.execute("""
            INSERT INTO trips(trip_id, created_at, updated_at, origin, destination,
                              days, total_budget, trip_score, plan_json)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(trip_id) DO UPDATE SET
                updated_at=excluded.updated_at, origin=excluded.origin,
                destination=excluded.destination, days=excluded.days,
                total_budget=excluded.total_budget, trip_score=excluded.trip_score,
                plan_json=excluded.plan_json
        """, (trip_id, created_at, utc_now(), state.origin, state.destination,
              state.days, state.total_budget, state.trip_score, payload))


def load_trip(trip_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM trips WHERE trip_id=?", (trip_id,)).fetchone()
    if not row:
        return None
    state = state_from_json(json.loads(row["plan_json"]))
    return {"state": state, "coordinator": AgentCoordinator(state), "created_at": row["created_at"]}


def _clean_text(value, name: str, max_len=100) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    if len(text) > max_len:
        raise ValueError(f"{name} is too long")
    return text


def build_state_from_payload(payload: dict) -> AgentState:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    origin = _clean_text(payload.get("origin"), "origin")
    destination = _clean_text(payload.get("destination"), "destination")
    if origin.casefold() == destination.casefold():
        raise ValueError("origin and destination must be different")

    try:
        start_obj = datetime.strptime(str(payload.get("start_date", "")), "%Y-%m-%d")
        end_obj = datetime.strptime(str(payload.get("end_date", "")), "%Y-%m-%d")
    except ValueError:
        raise ValueError("start_date / end_date must be in YYYY-MM-DD format")
    days = (end_obj - start_obj).days + 1
    if days <= 0:
        raise ValueError("end_date must be on/after start_date")
    if days > MAX_TRIP_DAYS:
        raise ValueError(f"trip length cannot exceed {MAX_TRIP_DAYS} days")

    try:
        total_budget = float(payload.get("total_budget"))
        rooms = int(payload.get("rooms", 1))
        num_people = int(payload.get("num_people", 1))
    except (TypeError, ValueError):
        raise ValueError("total_budget, rooms and num_people must be numeric")
    if not 500 <= total_budget <= 100_000_000:
        raise ValueError("total_budget must be between ₹500 and ₹10,00,00,000")
    if not 1 <= rooms <= 50:
        raise ValueError("rooms must be between 1 and 50")
    if not 1 <= num_people <= 100:
        raise ValueError("num_people must be between 1 and 100")

    interest = str(payload.get("interest", "general")).strip().lower()
    preference = str(payload.get("user_preference", "general")).strip().lower()
    mode = str(payload.get("preferred_mode", "Train")).strip().title()
    hotel = str(payload.get("preferred_hotel", "standard")).strip().lower()
    lang = str(payload.get("lang", "en")).strip().lower()
    if interest not in INTEREST_OPTIONS: raise ValueError("Invalid interest")
    if preference not in PREFERENCE_OPTIONS: raise ValueError("Invalid user_preference")
    if mode not in TRANSPORT_OPTIONS: raise ValueError("Invalid preferred_mode")
    if hotel not in HOTEL_OPTIONS: raise ValueError("Invalid preferred_hotel")
    if lang not in LANGUAGE_CODES: raise ValueError("Invalid language")

    return AgentState(origin=origin, destination=destination, interest=interest,
        start_date=start_obj.strftime("%Y-%m-%d"), end_date=end_obj.strftime("%Y-%m-%d"),
        days=days, total_budget=total_budget, rooms=rooms, num_people=num_people,
        preferred_mode=mode, preferred_hotel=hotel, lang=lang, user_preference=preference)


def error_response(message, status=400):
    return jsonify({"ok": False, "error": message}), status


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.errorhandler(413)
def too_large(_):
    return error_response("Request body is too large", 413)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/health")
def health():
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM trips").fetchone()["n"]
    return jsonify({"ok": True, "service": "trip-optimizer", "persisted_trips": count})


@app.route("/api/options")
def options():
    return jsonify({"ok": True, "languages": LANGUAGE_OPTIONS, "interests": INTEREST_OPTIONS,
                    "preferences": PREFERENCE_OPTIONS, "transport_modes": TRANSPORT_OPTIONS,
                    "hotel_types": HOTEL_OPTIONS, "max_trip_days": MAX_TRIP_DAYS})


@app.route("/api/plan", methods=["POST"])
def create_plan():
    payload = request.get_json(silent=True)
    try:
        state = build_state_from_payload(payload or {})
    except ValueError as e:
        return error_response(str(e))
    coordinator = AgentCoordinator(state)
    try:
        coordinator._run_weather()
        high_risk = bool(state.weather_risk) and any(x in state.weather_risk for x in ("Extreme", "High"))
        if high_risk and not bool(payload.get("force", False)):
            return jsonify({"ok": True, "status": "weather_warning", "weather_risk": state.weather_risk,
                            "weather_data": state.weather_data,
                            "message": "High weather risk detected. Choose Plan anyway to continue."})
        coordinator._run_location()
        if not state.places_found:
            return error_response("No places found for that destination/interest. Try 'general'.", 422)
        coordinator._geocode_places(); coordinator._run_hotel(); coordinator._run_intercity_only()
        coordinator._run_itinerary(); coordinator._run_local_transport_from_itinerary()
        coordinator._run_budget(auto_adjust=True); coordinator._run_score(); coordinator._run_packing()
        state.budget_savings_tips = coordinator._suggest_budget_reallocation()
    except Exception as e:
        traceback.print_exc()
        if app.debug:
            return error_response(f"Agent pipeline failed: {e}", 500)
        return error_response("The trip planner could not complete this request. Check API configuration and try again.", 500)

    trip_id = str(uuid.uuid4())
    save_trip(trip_id, state)
    return jsonify({"ok": True, "status": "complete", "trip_id": trip_id, "plan": state_to_json(state)})


@app.route("/api/plan/<trip_id>")
def get_plan(trip_id):
    rec = load_trip(trip_id)
    if not rec: return error_response("Trip not found", 404)
    return jsonify({"ok": True, "trip_id": trip_id, "plan": state_to_json(rec["state"])})


@app.route("/api/plan/<trip_id>/refine", methods=["POST"])
def refine_plan(trip_id):
    rec = load_trip(trip_id)
    if not rec: return error_response("Trip not found", 404)
    state, coordinator = rec["state"], rec["coordinator"]
    payload = request.get_json(silent=True) or {}
    changed = []

    if "interest" in payload:
        v = str(payload["interest"]).strip().lower()
        if v not in INTEREST_OPTIONS: return error_response("Invalid interest")
        if v != state.interest: state.interest = v; changed += ["interest", "places"]
    if "preferred_hotel" in payload:
        v = str(payload["preferred_hotel"]).strip().lower()
        if v not in HOTEL_OPTIONS: return error_response("Invalid preferred_hotel")
        if v != state.preferred_hotel: state.preferred_hotel = v; changed += ["hotel_type", "hotel"]
    if "preferred_mode" in payload:
        v = str(payload["preferred_mode"]).strip().title()
        if v not in TRANSPORT_OPTIONS: return error_response("Invalid preferred_mode")
        if v != state.preferred_mode: state.preferred_mode = v; changed.append("transport")
    if "total_budget" in payload:
        try: v = float(payload["total_budget"])
        except (TypeError, ValueError): return error_response("total_budget must be numeric")
        if not 500 <= v <= 100_000_000: return error_response("total_budget is outside the allowed range")
        if v != state.total_budget: state.total_budget = v; changed.append("budget")
    if "start_date" in payload or "end_date" in payload:
        start_s = str(payload.get("start_date", state.start_date)); end_s = str(payload.get("end_date", state.end_date))
        try: start_obj = datetime.strptime(start_s, "%Y-%m-%d"); end_obj = datetime.strptime(end_s, "%Y-%m-%d")
        except ValueError: return error_response("start_date / end_date must be in YYYY-MM-DD format")
        new_days = (end_obj - start_obj).days + 1
        if not 1 <= new_days <= MAX_TRIP_DAYS: return error_response(f"trip length must be 1-{MAX_TRIP_DAYS} days")
        if (start_s, end_s) != (state.start_date, state.end_date):
            state.start_date, state.end_date, state.days = start_s, end_s, new_days
            changed += ["days", "dates"]

    if not changed: return error_response("No recognised fields changed. Nothing to refine.", 422)
    try:
        coordinator.rerun(sorted(set(changed)))
    except Exception as e:
        traceback.print_exc()
        if app.debug: return error_response(f"Refine failed: {e}", 500)
        return error_response("The updated plan could not be generated.", 500)
    save_trip(trip_id, state, created_at=rec["created_at"])
    return jsonify({"ok": True, "status": "complete", "trip_id": trip_id,
                    "changed": sorted(set(changed)), "plan": state_to_json(state)})


@app.route("/api/history")
def history():
    limit = min(max(request.args.get("limit", default=20, type=int), 1), 100)
    with db() as conn:
        rows = conn.execute("""SELECT trip_id,origin,destination,days,total_budget,trip_score,created_at,updated_at
                             FROM trips ORDER BY updated_at DESC LIMIT ?""", (limit,)).fetchall()
    return jsonify({"ok": True, "trips": [dict(r) for r in rows]})


@app.route("/api/history/<trip_id>", methods=["DELETE"])
def delete_history(trip_id):
    with db() as conn:
        cur = conn.execute("DELETE FROM trips WHERE trip_id=?", (trip_id,))
    if not cur.rowcount: return error_response("Trip not found", 404)
    return jsonify({"ok": True})


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"🚀 Trip Optimizer running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
