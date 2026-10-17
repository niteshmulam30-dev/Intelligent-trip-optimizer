"""
🇮🇳  INDIA ETA CORRECTION LAYER
=================================
OSRM gives optimistic free-flow durations. Indian roads almost never deliver
those numbers — tolls, hill ghats, coastal villages, urban congestion, and
mixed traffic all inflate the real ETA.

This module classifies a route into one of five categories and applies an
India-specific multiplier on top of the raw OSRM duration.

    OpenStreetMap → Nominatim → Coordinates
                          ↓
                        OSRM
                          ↓
                Distance + Base ETA
                          ↓
            ── INDIA ETA CORRECTION LAYER ──   ← (this file)
                          ↓
                  Itinerary Planner

Public API
----------
    detect_route_type(source, destination, src_coords=None, dst_coords=None,
                      distance_km=None) -> str
    correct_eta(osrm_minutes, source, destination, **kwargs) -> (minutes, route_type, multiplier)
    ROUTE_MULTIPLIERS : dict

Future-ready hooks (return 1.0 today, easy to extend):
    weekend_multiplier(when=None)
    monsoon_multiplier(when=None, route_type=None)
    peak_hour_multiplier(when=None, route_type=None)
    hill_road_penalty(distance_km, route_type)
"""

from __future__ import annotations
import datetime
import re

# ------------------------------------------------------------------
# 🎚️  CORE MULTIPLIERS  (per requirement)
# ------------------------------------------------------------------
# v10: OSRM already returns realistic India travel times in most regions.
# Multiplying on top was producing 30 km = 83 min (Goa). Baseline is now 1.0
# for every route type; the only residual penalty is a small hill bump because
# OSRM under-models ghats. Peak-hour / monsoon hooks below are also softened.
ROUTE_MULTIPLIERS = {
    "expressway": 1.00,
    "highway":    1.00,
    "coastal":    1.00,
    "hill":       1.15,   # OSRM under-estimates ghat sections
    "urban":      1.00,
}

# ------------------------------------------------------------------
# 🗺️  CITY / TERRAIN LEXICON
# ------------------------------------------------------------------
HILL_STATIONS = {
    "manali", "shimla", "kullu", "dharamshala", "mcleodganj", "dalhousie",
    "kasol", "spiti", "kaza", "leh", "ladakh", "kargil", "nubra",
    "mussoorie", "nainital", "almora", "ranikhet", "kausani", "auli",
    "chopta", "rishikesh", "haridwar", "dehradun",
    "darjeeling", "gangtok", "pelling", "lachung", "lachen", "kalimpong",
    "tawang", "ziro", "shillong", "cherrapunji", "mawlynnong",
    "ooty", "udhagamandalam", "coonoor", "kodaikanal", "yercaud",
    "munnar", "wayanad", "vagamon", "thekkady",
    "coorg", "madikeri", "chikmagalur", "sakleshpur",
    "mount abu", "matheran", "mahabaleshwar", "panchgani", "lonavala",
    "khandala", "lavasa", "saputara", "pachmarhi",
}

COASTAL_CITIES = {
    "goa", "panaji", "panjim", "vasco", "margao", "calangute", "baga",
    "anjuna", "candolim", "morjim", "palolem", "agonda",
    "mumbai", "alibaug", "ratnagiri", "tarkarli", "ganpatipule",
    "daman", "diu", "veraval", "dwarka", "porbandar",
    "karwar", "gokarna", "udupi", "mangalore", "kasaragod",
    "kannur", "kozhikode", "calicut", "kochi", "cochin", "alleppey",
    "alappuzha", "kollam", "varkala", "thiruvananthapuram", "trivandrum",
    "kanyakumari", "rameshwaram", "rameswaram", "tuticorin",
    "pondicherry", "puducherry", "mahabalipuram", "mamallapuram",
    "chennai", "kovalam",
    "vizag", "visakhapatnam", "vizianagaram", "kakinada",
    "puri", "konark", "gopalpur", "chandipur",
    "digha", "mandarmani", "tajpur",
    "port blair", "havelock", "neil island",
}

METRO_CITIES = {
    "delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida",
    "faridabad", "ghaziabad",
    "mumbai", "navi mumbai", "thane",
    "bangalore", "bengaluru", "chennai", "kolkata", "hyderabad",
    "pune", "ahmedabad", "surat", "jaipur", "lucknow", "kanpur",
    "indore", "bhopal", "nagpur", "patna", "chandigarh",
}

# Pairs known to ride on an actual expressway / access-controlled highway.
EXPRESSWAY_PAIRS = {
    frozenset({"delhi", "agra"}),
    frozenset({"delhi", "jaipur"}),
    frozenset({"delhi", "meerut"}),
    frozenset({"delhi", "chandigarh"}),
    frozenset({"delhi", "katra"}),
    frozenset({"delhi", "dehradun"}),
    frozenset({"mumbai", "pune"}),
    frozenset({"mumbai", "nagpur"}),
    frozenset({"bangalore", "mysore"}),
    frozenset({"bengaluru", "mysore"}),
    frozenset({"bangalore", "chennai"}),
    frozenset({"bengaluru", "chennai"}),
    frozenset({"ahmedabad", "vadodara"}),
    frozenset({"ahmedabad", "mumbai"}),
    frozenset({"hyderabad", "vijayawada"}),
    frozenset({"lucknow", "agra"}),
    frozenset({"lucknow", "ghaziabad"}),
    frozenset({"purvanchal", "lucknow"}),
}

_WORD_RE = re.compile(r"[a-z]+")


def _tokens(text: str) -> set:
    if not text:
        return set()
    return set(_WORD_RE.findall(text.lower()))


def _matches(text: str, lexicon: set) -> bool:
    if not text:
        return False
    t = text.lower()
    # multi-word entries
    for entry in lexicon:
        if " " in entry and entry in t:
            return True
    toks = _tokens(text)
    return bool(toks & {e for e in lexicon if " " not in e})


# ------------------------------------------------------------------
# 🔍  ROUTE TYPE DETECTION
# ------------------------------------------------------------------
def detect_route_type(source: str,
                      destination: str,
                      src_coords=None,
                      dst_coords=None,
                      distance_km: float | None = None) -> str:
    """
    Classify an India route. Order of precedence:
        hill > coastal > expressway > urban > highway
    """
    src = (source or "").strip()
    dst = (destination or "").strip()

    # 1. Hill — either endpoint is a hill destination, or coords > 1000 m.
    if _matches(src, HILL_STATIONS) or _matches(dst, HILL_STATIONS):
        return "hill"

    # 2. Coastal — either endpoint is on the coast.
    if _matches(src, COASTAL_CITIES) or _matches(dst, COASTAL_CITIES):
        return "coastal"

    # 3. Expressway — known access-controlled pair.
    s_toks = _tokens(src)
    d_toks = _tokens(dst)
    for pair in EXPRESSWAY_PAIRS:
        a, b = list(pair)
        if (a in s_toks and b in d_toks) or (b in s_toks and a in d_toks):
            return "expressway"

    # 4. Urban — short hop, both endpoints inside a metro footprint.
    if distance_km is not None and distance_km <= 30:
        if _matches(src, METRO_CITIES) or _matches(dst, METRO_CITIES) \
           or (src_coords and dst_coords):
            return "urban"

    # 5. Default — open highway.
    return "highway"


# ------------------------------------------------------------------
# 🔮  FUTURE-READY HOOKS  (currently neutral)
# ------------------------------------------------------------------
def weekend_multiplier(when: datetime.datetime | None = None) -> float:
    """v10: neutral. OSRM duration is the source of truth."""
    return 1.0


def monsoon_multiplier(when: datetime.datetime | None = None,
                       route_type: str | None = None) -> float:
    """v10: only a small hill/coastal bump during monsoon."""
    when = when or datetime.datetime.now()
    if when.month in (6, 7, 8, 9) and route_type in ("hill", "coastal"):
        return 1.10
    return 1.0


def peak_hour_multiplier(when: datetime.datetime | None = None,
                         route_type: str | None = None) -> float:
    """v10: gentle urban rush-hour bump only."""
    when = when or datetime.datetime.now()
    h = when.hour
    if route_type == "urban" and (8 <= h <= 10 or 18 <= h <= 20):
        return 1.10
    return 1.0


def hill_road_penalty(distance_km: float | None, route_type: str) -> float:
    """v10: long ghats still cost extra time."""
    if route_type == "hill" and distance_km and distance_km > 150:
        return 1.05
    return 1.0


# ------------------------------------------------------------------
# 🧮  ETA CORRECTION
# ------------------------------------------------------------------
def correct_eta(osrm_minutes: float,
                source: str,
                destination: str,
                src_coords=None,
                dst_coords=None,
                distance_km: float | None = None,
                when: datetime.datetime | None = None,
                apply_future_hooks: bool = True):
    """
    Apply the India correction layer to a raw OSRM duration.

    Returns
    -------
    (corrected_minutes: float, route_type: str, effective_multiplier: float)
    """
    if osrm_minutes is None:
        return None, "highway", 1.0

    route_type = detect_route_type(source, destination,
                                   src_coords, dst_coords, distance_km)
    base = ROUTE_MULTIPLIERS.get(route_type, 1.25)
    mult = base

    if apply_future_hooks:
        mult *= weekend_multiplier(when)
        mult *= monsoon_multiplier(when, route_type)
        mult *= peak_hour_multiplier(when, route_type)
        mult *= hill_road_penalty(distance_km, route_type)

    corrected = osrm_minutes * mult
    return round(corrected, 1), route_type, round(mult, 3)


__all__ = [
    "ROUTE_MULTIPLIERS",
    "detect_route_type",
    "correct_eta",
    "weekend_multiplier",
    "monsoon_multiplier",
    "peak_hour_multiplier",
    "hill_road_penalty",
]
