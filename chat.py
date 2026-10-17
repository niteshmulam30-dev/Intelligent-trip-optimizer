"""
🤖 CHAT AGENT  —  Intelligent Trip Optimizer
=============================================
As described in the IEEE paper:

  "A central Chat Agent manages communication between the user and the system,
   ensuring that user requirements are accurately captured and routed to the
   relevant agents. When the user asks the system to make changes, the system
   will re-invoke only those agents that are affected — preventing unnecessary
   re-calculation."

Architecture:
  ChatAgent → AgentCoordinator → [WeatherAgent, LocationAgent,
              HotelAgent, TransportAgent, BudgetAgent, ItineraryAgent]
"""

import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from coordinator  import AgentCoordinator, AgentState
from language     import IndianLanguageTranslator, ui
from location     import print_places
from hotel        import print_hotels
from itinerary    import print_itinerary
from transport    import print_transport
from budget_agent import BudgetAgent
from weather      import (
    travel_impact, smart_recommendation,
    interpret_aqi, forecast_trend,
)


LANGUAGE_OPTIONS = {
    "1":  ("en", "English"),
    "2":  ("hi", "Hindi / हिंदी"),
    "3":  ("mr", "Marathi / मराठी"),
    "4":  ("ta", "Tamil / தமிழ்"),
    "5":  ("te", "Telugu / తెలుగు"),
    "6":  ("kn", "Kannada / ಕನ್ನಡ"),
    "7":  ("ml", "Malayalam / മലയാളം"),
    "8":  ("bn", "Bengali / বাংলা"),
    "9":  ("gu", "Gujarati / ગુજરાતી"),
    "10": ("pa", "Punjabi / ਪੰਜਾਬੀ"),
}

HISTORY_FILE = "trip_history.json"


def select_language():
    print("\n🌐 Choose your language / अपनी भाषा चुनें:")
    print("=" * 42)
    for key, (_, name) in LANGUAGE_OPTIONS.items():
        print(f"  {key}. {name}")
    print("=" * 42)
    choice = input("\nEnter choice (default 1): ").strip()
    lang, name = LANGUAGE_OPTIONS.get(choice, ("en", "English"))
    print(f"\n✅ Selected: {name}\n")
    return lang


def _t(text, lang, tr):
    return tr.manual_translate(text, lang) if lang != "en" else text


def save_trip(record):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
    history.append(record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def show_trip_history(lang, tr):
    if not os.path.exists(HISTORY_FILE):
        print(_t("📂 No trip history found", lang, tr))
        return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        print("\n" + "=" * 55)
        print(_t(f"📜 TRIP HISTORY  ({len(history)} trips)", lang, tr))
        print("=" * 55)
        for i, trip in enumerate(history, 1):
            print(
                f"{i}. {trip.get('origin','?')} → {trip.get('destination','?')} | "
                f"{trip.get('days','?')} days | ₹{trip.get('budget','?')} | "
                f"{trip.get('timestamp','?')}"
            )
        print()
    except Exception as e:
        print(f"⚠️ Error reading history: {e}")


# ─── display helpers ─────────────────────────────────

def display_weather(state, lang, tr):
    w = state.weather_data
    if not w:
        return
    print("\n" + "=" * 55)
    print(_t(f"🌦️  WEATHER  — {state.destination}", lang, tr))
    print("=" * 55)
    print(_t(f"🌤  Condition   : {w['condition']}", lang, tr))
    print(_t(f"🌡  Temperature : {w['temp']}°C", lang, tr))
    print(_t(f"🤒  Feels Like  : {w['feels_like']}°C", lang, tr))
    print(_t(f"💧  Humidity    : {w['humidity']}%", lang, tr))
    print(_t(f"🌫  AQI         : {state.aqi} ({interpret_aqi(state.aqi)})", lang, tr))
    print(_t(f"🚦  Risk Level  : {state.weather_risk}", lang, tr))
    impact = travel_impact(w["condition"], w["temp"], w["feels_like"], state.aqi)
    print("\n" + _t("🚗  Travel Impact:", lang, tr))
    for mode, advice in impact.items():
        print(_t(f"  {mode}: {advice}", lang, tr))
    if state.forecast:
        print("\n" + _t("📅  5-Day Forecast:", lang, tr))
        for date, temp, cond in state.forecast:
            print(_t(f"  {date} → {temp}°C | {cond}", lang, tr))
        print(_t(f"📈  Trend: {forecast_trend(state.forecast)}", lang, tr))
    smart_recommendation(w["condition"], w["temp"], w["feels_like"], state.aqi)
    print("=" * 55)


def display_places(state, lang, tr):
    if not state.places:
        return
    print("\n" + "=" * 55)
    print(_t(f"📍  TOP ATTRACTIONS  — {state.destination}", lang, tr))
    print("=" * 55)
    print_places(state.places)


def display_hotels(state, lang, tr):
    if not state.hotels:
        return
    print("\n" + "=" * 55)
    print(_t("🏨  HOTEL RECOMMENDATIONS", lang, tr))
    print("=" * 55)
    print_hotels(state.hotels, state.destination)
    if state.best_hotel:
        h = state.best_hotel
        print("\n" + _t("✅ Selected Hotel", lang, tr))
        print("-" * 40)
        print(_t(f"🏨 {h['name']}", lang, tr))
        print(_t(f"💰 ₹{h['price']:,}/night", lang, tr))
        print(_t(f"⭐ {h['rating']}/10", lang, tr))
        print(_t(f"📍 {h['area']}", lang, tr))


def display_transport(state, lang, tr):
    if not state.intercity or not state.local_transport:
        return
    print_transport(state.intercity, state.local_transport)


def display_budget(state, lang, tr):
    if not state.budget_breakdown:
        return
    ba = BudgetAgent()
    ba.print_breakdown(state.budget_breakdown)


def display_itinerary(state, lang, tr):
    if not state.itinerary:
        return
    print("\n" + "=" * 55)
    print(_t("🗺  DAY-BY-DAY ITINERARY", lang, tr))
    print("=" * 55)
    print_itinerary(state.itinerary)


def display_packing(state, lang, tr):
    if not state.packing_list:
        return
    print("\n" + _t("🧳  SMART PACKING LIST", lang, tr))
    print("-" * 40)
    for item in state.packing_list:
        print(_t(f"✔ {item}", lang, tr))
    print()


def display_summary(state, lang, tr):
    bd = state.budget_breakdown or {}
    print("\n" + "=" * 55)
    print(_t("📄  FINAL TRIP SUMMARY", lang, tr))
    print("=" * 55)
    print(_t(f"📍  Destination   : {state.destination}", lang, tr))
    print(_t(f"📅  Dates         : {state.start_date}  →  {state.end_date}", lang, tr))
    print(_t(f"📆  Days          : {state.days}", lang, tr))
    print(_t(f"🚆  Travel Mode   : {state.preferred_mode}", lang, tr))
    print(_t(f"🏨  Hotel Type    : {state.preferred_hotel.title()}", lang, tr))
    if state.best_hotel:
        print(_t(f"🏨  Hotel         : {state.best_hotel['name']}", lang, tr))
    print(_t(f"💰  Total Budget  : ₹{int(state.total_budget):,}", lang, tr))
    print(_t(f"💸  Total Used    : ₹{bd.get('total_used', 0):,}", lang, tr))
    print(_t(f"💵  Remaining     : ₹{bd.get('remaining', 0):,}", lang, tr))
    print(_t(f"📊  Trip Score    : {state.trip_score}/100", lang, tr))
    print(_t(f"🚦  Weather Risk  : {state.weather_risk}", lang, tr))

    # 💸 v4: Dynamic budget reallocation suggestions
    tips = getattr(state, "budget_savings_tips", [])
    if tips:
        saved = bd.get("remaining", 0)
        print(_t(f"\n💡  You saved ₹{saved:,}! Consider spending it on:", lang, tr))
        for tip in tips:
            print(f"     ✓ {tip}")
    print("=" * 55)


def display_full_plan(state, lang, tr):
    display_weather(state, lang, tr)
    display_places(state, lang, tr)
    display_hotels(state, lang, tr)
    display_transport(state, lang, tr)
    display_budget(state, lang, tr)
    display_itinerary(state, lang, tr)
    display_packing(state, lang, tr)
    display_summary(state, lang, tr)


# ─── feedback loop ────────────────────────────────────

def feedback_loop(state, coordinator, lang, tr):
    """
    IEEE paper: Users can refine the plan interactively.
    Only affected agents are re-run (partial re-invocation).
    """

    MENU = """
╔══════════════════════════════════════════════╗
║   🔄  REFINE YOUR TRIP  (Feedback Loop)      ║
╠══════════════════════════════════════════════╣
║  1. Change destination interest              ║
║  2. Change hotel type (budget/std/luxury)    ║
║  3. Change travel mode                       ║
║  4. Change budget                            ║
║  5. Change trip dates / duration             ║
║  6. Re-check weather                         ║
║  7. View full plan again                     ║
║  8. View budget breakdown                    ║
║  9. Save & Exit                              ║
╚══════════════════════════════════════════════╝"""

    TRAVEL_MODES = {"1": "Flight", "2": "Train", "3": "Bus", "4": "Car"}
    HOTEL_TYPES  = {"1": "budget", "2": "standard", "3": "luxury"}

    while True:
        print(MENU)
        choice = input("Enter choice (1-9): ").strip()
        changed = []

        if choice == "1":
            new_interest = input("🎯 New interest (beach/temple/fort/etc): ").strip().lower()
            if new_interest:
                state.interest = new_interest
                changed = ["places", "interest"]

        elif choice == "2":
            print("1.Budget  2.Standard  3.Luxury")
            hc = input("Choose: ").strip()
            new_type = HOTEL_TYPES.get(hc)
            if new_type:
                state.preferred_hotel = new_type
                changed = ["hotel", "hotel_type"]

        elif choice == "3":
            print("1.Flight  2.Train  3.Bus  4.Car")
            tc = input("Choose: ").strip()
            new_mode = TRAVEL_MODES.get(tc)
            if new_mode:
                state.preferred_mode = new_mode
                changed = ["transport"]

        elif choice == "4":
            try:
                new_budget = float(input("💰 New total budget (₹): ").strip())
                if new_budget > 0:
                    state.total_budget = new_budget
                    changed = ["budget", "hotel", "transport"]
            except ValueError:
                print("❌ Invalid budget")
                continue

        elif choice == "5":
            try:
                sd = input("📅 New start date (YYYY-MM-DD): ").strip()
                ed = input("📅 New end date   (YYYY-MM-DD): ").strip()
                s  = datetime.strptime(sd, "%Y-%m-%d")
                e  = datetime.strptime(ed, "%Y-%m-%d")
                nd = (e - s).days + 1
                if nd > 0:
                    state.start_date = sd
                    state.end_date   = ed
                    state.days       = nd
                    changed = ["days", "hotel", "transport", "places"]
                else:
                    print("❌ Invalid dates")
                    continue
            except ValueError:
                print("❌ Invalid date format (use YYYY-MM-DD)")
                continue

        elif choice == "6":
            changed = ["weather"]

        elif choice == "7":
            display_full_plan(state, lang, tr)
            continue

        elif choice == "8":
            display_budget(state, lang, tr)
            continue

        elif choice == "9":
            break

        else:
            print("❌ Invalid choice")
            continue

        if changed:
            print(f"\n⚙️  Re-running affected agents: {changed} ...")
            coordinator.rerun(changed)
            print("\n✅ Plan updated!\n")
            display_full_plan(state, lang, tr)


# ─── main chat agent ──────────────────────────────────

def chat_agent():
    lang = select_language()
    tr   = IndianLanguageTranslator()

    def T(text):
        return _t(text, lang, tr)

    print("\n" + "=" * 55)
    print(T("🤖  INTELLIGENT TRIP OPTIMIZER"))
    print(T("    Multi-Agent AI Travel Planner"))
    print("=" * 55)

    view = input(T("\n📜 View previous trip history? (y/n): ")).strip().lower()
    if view == "y":
        show_trip_history(lang, tr)

    # user inputs
    origin   = input(T("\n🏠 Enter starting city: ")).strip()
    city     = input(T("📍 Enter destination city: ")).strip()
    interest = input(T("🎯 Interest (beach/temple/fort/adventure/museum/general): ")).strip().lower()

    # 🎯 v4: Travel preference for personalised recommendations
    print("\n" + T("✨ What kind of experience do you prefer?"))
    print("  1. Relaxation  2. Adventure  3. Nightlife  4. Photography  5. General")
    pref_map = {"1": "relaxation", "2": "adventure", "3": "nightlife", "4": "photography"}
    user_preference = pref_map.get(input(T("Enter choice (1-5, default 5): ")).strip(), "general")
    print(T(f"   ✅ Preference: {user_preference.capitalize()}"))

    try:
        start_date = input(T("📅 Trip start date (YYYY-MM-DD): ")).strip()
        end_date   = input(T("📅 Trip end date   (YYYY-MM-DD): ")).strip()
        start_obj  = datetime.strptime(start_date, "%Y-%m-%d")
        end_obj    = datetime.strptime(end_date, "%Y-%m-%d")
        days       = (end_obj - start_obj).days + 1
        if days <= 0:
            print(T("⚠️ Invalid trip dates"))
            return
    except ValueError:
        print(T("⚠️ Invalid date format"))
        return

    print(T(f"\n📆 Trip Duration: {days} day(s)"))

    print("\n" + T("🚆 Choose Travel Mode:"))
    print("  1. Flight\n  2. Train\n  3. Bus\n  4. Car")
    preferred_mode = {"1": "Flight","2": "Train","3": "Bus","4": "Car"}.get(
        input(T("Enter choice (1-4): ")).strip(), "Train"
    )

    print("\n" + T("🏨 Choose Hotel Type:"))
    print("  1. Budget\n  2. Standard\n  3. Luxury")
    preferred_hotel = {"1": "budget","2": "standard","3": "luxury"}.get(
        input(T("Enter choice (1-3): ")).strip(), "standard"
    )

    try:
        total_budget = float(input(T("💰 Total budget (₹): ")).strip())
        rooms        = int(input(T("🛏  Number of rooms: ")).strip())
        num_people   = int(input(T("👥 Number of people: ")).strip())
    except ValueError:
        print(T("⚠️ Invalid input"))
        return

    # Build state
    state = AgentState(
        origin          = origin,
        destination     = city,
        interest        = interest,
        start_date      = start_date,
        end_date        = end_date,
        days            = days,
        total_budget    = total_budget,
        rooms           = rooms,
        num_people      = num_people,
        preferred_mode  = preferred_mode,
        preferred_hotel  = preferred_hotel,
        lang             = lang,
        user_preference  = user_preference,
    )

    coordinator = AgentCoordinator(state, translator=tr)

    print("\n" + "=" * 55)
    print(T("🚀 Starting Agent Workflow..."))
    print("=" * 55)

    # Weather gate
    coordinator._run_weather()

    if state.weather_risk and (
        "Extreme" in state.weather_risk or "High" in state.weather_risk
    ):
        display_weather(state, lang, tr)
        proceed = input(T("⚠️  High weather risk. Still plan the trip? (y/n): ")).strip().lower()
        if proceed != "y":
            print(T("🔙 Trip planning cancelled due to weather conditions."))
            return

    coordinator._run_location()

    if not state.places_found:
        print(T("❌ No places found. Try 'general' as interest."))
        return

    coordinator._run_hotel()
    coordinator._run_transport()
    coordinator._run_budget(auto_adjust=True)
    coordinator._run_itinerary()
    coordinator._run_score()
    coordinator._run_packing()

    print("\n" + "=" * 55)
    print(T("✅ TRIP PLAN GENERATED"))
    print("=" * 55)

    display_full_plan(state, lang, tr)

    refine = input(T("\n🔄 Would you like to refine the plan? (y/n): ")).strip().lower()
    if refine == "y":
        feedback_loop(state, coordinator, lang, tr)

    # save
    bd = state.budget_breakdown or {}
    save_trip({
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "origin":       origin,
        "destination":  city,
        "interest":     interest,
        "days":         state.days,
        "budget":       int(total_budget),
        "used":         bd.get("total_used", 0),
        "remaining":    bd.get("remaining", 0),
        "hotel":        state.best_hotel["name"] if state.best_hotel else "N/A",
        "hotel_type":   preferred_hotel,
        "transport":    state.preferred_mode,
        "weather_risk": state.weather_risk,
        "trip_score":   state.trip_score,
        "lang":         lang,
        "start_date":   state.start_date,
        "end_date":     state.end_date,
        "num_people":   num_people,
    })

    print(T("\n💾 Trip saved to history."))
    print(T("✅ Thank you for using Intelligent Trip Optimizer! Happy Journey 🌍"))


def main():
    while True:
        chat_agent()
        again = input("\n🔄 Plan another trip? (y/n): ").strip().lower()
        if again != "y":
            print("\n👋 Goodbye! Happy Journey 🌍")
            break


if __name__ == "__main__":
    main()
