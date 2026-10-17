"""
🏨 HOTEL AGENT  —  v8 (ALL HOTEL PROBLEMS FIXED)
===================================
NEW FIXES IN v8:
✅ FIX-H-LOC:  Geo-distance scoring: hotels scored by haversine distance
               to every selected attraction centroid, not just area keyword match
✅ FIX-H-TOT:  Total trip cost optimisation: score includes estimated
               transport cost from hotel → attractions, not just hotel price
✅ FIX-H-SEA:  Seasonal pricing awareness: peak multiplier applied for
               Dec-Jan, Apr-May, long weekends (Diwali, Holi, Christmas)
✅ FIX-H-DIV:  Recommendation diversity: returns 4 categories —
               Best Location, Best Value, Cheapest, Luxury
✅ FIX-H-CENT: Centrality scoring: average distance to all attractions
               (lower = higher score), replacing simple area-keyword overlap

Preserved from v4:
✅ Weighted scoring with rating, reviews, price
✅ Verified hotels database for major cities
✅ LLM supplement for other cities
✅ Booking links (Booking.com, Google Hotels, MakeMyTrip, Goibibo)
"""

import requests
import os
import urllib.parse
import json
import math
from datetime import date, datetime
from math import cos, sin, sqrt, atan2, radians

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
URL     = "https://integrate.api.nvidia.com/v1/chat/completions"


# ============================================================
# 📚 VERIFIED HOTELS DATABASE
# ============================================================
VERIFIED_HOTELS = {
    "goa": [
        {"name": "Taj Fort Aguada Resort & Spa",         "price": 8500,  "rating": 8.9, "area": "Candolim, North Goa",    "reviews": 4200, "lat": 15.5189, "lon": 73.7668},
        {"name": "The Leela Goa",                         "price": 9200,  "rating": 9.1, "area": "Cavelossim, South Goa",  "reviews": 3800, "lat": 15.1667, "lon": 73.9500},
        {"name": "Alila Diwa Goa",                        "price": 6800,  "rating": 8.7, "area": "Majorda, South Goa",     "reviews": 2900, "lat": 15.2167, "lon": 73.9667},
        {"name": "Park Hyatt Goa Resort",                 "price": 7500,  "rating": 8.8, "area": "Arossim, South Goa",     "reviews": 3100, "lat": 15.2000, "lon": 73.9500},
        {"name": "O Hotel Goa",                           "price": 3800,  "rating": 8.2, "area": "Calangute, North Goa",   "reviews": 1800, "lat": 15.5440, "lon": 73.7550},
        {"name": "Lemon Tree Amarante Beach Resort",      "price": 3200,  "rating": 8.0, "area": "Candolim, North Goa",    "reviews": 1500, "lat": 15.5150, "lon": 73.7600},
        {"name": "Keys Select Ronil Goa",                 "price": 2500,  "rating": 7.8, "area": "Baga, North Goa",        "reviews": 1200, "lat": 15.5600, "lon": 73.7520},
        {"name": "Hotel Baga Marina",                     "price": 2200,  "rating": 7.6, "area": "Baga, North Goa",        "reviews": 900,  "lat": 15.5580, "lon": 73.7500},
        {"name": "Treehouse Kovalam Goa",                 "price": 1800,  "rating": 7.5, "area": "Candolim, North Goa",    "reviews": 700,  "lat": 15.5100, "lon": 73.7600},
        {"name": "Zostel Goa",                            "price": 800,   "rating": 7.5, "area": "Anjuna, North Goa",      "reviews": 2200, "lat": 15.5700, "lon": 73.7400},
    ],
    "mumbai": [
        {"name": "The Taj Mahal Palace",                  "price": 18000, "rating": 9.3, "area": "Colaba, South Mumbai",   "reviews": 9800, "lat": 18.9217, "lon": 72.8332},
        {"name": "The Oberoi Mumbai",                     "price": 15000, "rating": 9.2, "area": "Nariman Point",          "reviews": 7200, "lat": 18.9258, "lon": 72.8233},
        {"name": "Trident Nariman Point",                 "price": 9500,  "rating": 8.9, "area": "Nariman Point",          "reviews": 5400, "lat": 18.9256, "lon": 72.8217},
        {"name": "ITC Grand Central",                     "price": 7000,  "rating": 8.7, "area": "Parel, Central Mumbai",  "reviews": 4200, "lat": 19.0058, "lon": 72.8423},
        {"name": "Novotel Mumbai Juhu Beach",             "price": 5500,  "rating": 8.3, "area": "Juhu",                   "reviews": 3100, "lat": 19.0990, "lon": 72.8264},
        {"name": "Hotel Sahara Star",                     "price": 4500,  "rating": 8.2, "area": "Vile Parle, near Airport","reviews": 2800, "lat": 19.0896, "lon": 72.8656},
        {"name": "Ginger Mumbai Airport",                 "price": 2800,  "rating": 7.9, "area": "Andheri East",           "reviews": 1900, "lat": 19.1136, "lon": 72.8697},
        {"name": "Hotel City Palace",                     "price": 1800,  "rating": 7.5, "area": "Colaba, South Mumbai",   "reviews": 1400, "lat": 18.9250, "lon": 72.8320},
    ],
    "delhi": [
        {"name": "The Leela Palace New Delhi",            "price": 18000, "rating": 9.3, "area": "Diplomatic Enclave",     "reviews": 6800, "lat": 28.5992, "lon": 77.1721},
        {"name": "The Imperial New Delhi",                "price": 14000, "rating": 9.2, "area": "Janpath, Connaught Place","reviews": 7200, "lat": 28.6261, "lon": 77.2188},
        {"name": "Hyatt Regency Delhi",                   "price": 8000,  "rating": 8.7, "area": "Bhikaji Cama Place",     "reviews": 4100, "lat": 28.5672, "lon": 77.1870},
        {"name": "Radisson Blu Plaza Delhi Airport",      "price": 5500,  "rating": 8.3, "area": "Mahipalpur",             "reviews": 3200, "lat": 28.5376, "lon": 77.1218},
        {"name": "Hotel Broadway",                        "price": 2500,  "rating": 7.6, "area": "Daryaganj, Old Delhi",   "reviews": 1100, "lat": 28.6447, "lon": 77.2395},
    ],
    "jaipur": [
        {"name": "Rambagh Palace",                        "price": 22000, "rating": 9.4, "area": "Bhawani Singh Road",     "reviews": 5400, "lat": 26.8942, "lon": 75.8069},
        {"name": "ITC Rajputana",                         "price": 7000,  "rating": 8.7, "area": "Palace Road",            "reviews": 3200, "lat": 26.9124, "lon": 75.7873},
        {"name": "Hotel Pearl Palace",                    "price": 1500,  "rating": 8.0, "area": "Hathroi Fort, Ajmer Road","reviews": 2100, "lat": 26.9180, "lon": 75.8120},
        {"name": "Zostel Jaipur",                         "price": 600,   "rating": 7.8, "area": "Bani Park",              "reviews": 1800, "lat": 26.9199, "lon": 75.7960},
    ],
    "varanasi": [
        {"name": "Taj Nadesar Palace",                    "price": 12000, "rating": 9.0, "area": "Nadesar",                "reviews": 2800, "lat": 25.3400, "lon": 83.0100},
        {"name": "BrijRama Palace",                       "price": 8000,  "rating": 8.8, "area": "Darbhanga Ghat",         "reviews": 2200, "lat": 25.3100, "lon": 83.0200},
        {"name": "Hotel Alka",                            "price": 2000,  "rating": 7.7, "area": "Meer Ghat",              "reviews": 900,  "lat": 25.3082, "lon": 83.0100},
    ],
}


def _get_verified(city, budget):
    hotels = VERIFIED_HOTELS.get(city.strip().lower(), [])
    return [h for h in hotels if h["price"] <= budget and h["rating"] >= 7.0]


# ============================================================
# ✅ FIX-H-SEA: SEASONAL PRICE MULTIPLIER
# ============================================================
_PEAK_MONTHS = {12, 1}          # Dec, Jan  (winter peak)
_SHOULDER_MONTHS = {4, 5, 10}   # Apr, May, Oct

_HOLIDAY_WINDOWS = [
    # (month, day_start, day_end)  — approximate Diwali, Holi, Christmas windows
    (10, 20, 31),   # Diwali window (October)
    (11, 1,  5),    # Diwali spillover (November)
    (3,  20, 31),   # Holi window
    (12, 22, 31),   # Christmas / New Year
    (1,  1,  5),    # New Year spillover
]


def seasonal_price_multiplier(check_in_date: str) -> float:
    """
    ✅ FIX-H-SEA: Returns a price multiplier based on travel date.
    Peak season: 1.40x | Shoulder: 1.15x | Holiday window: 1.30x | Off: 1.0x
    check_in_date: 'YYYY-MM-DD' string or None (defaults to today).
    """
    try:
        dt = datetime.strptime(check_in_date, "%Y-%m-%d").date() if check_in_date else date.today()
    except Exception:
        dt = date.today()

    m, d = dt.month, dt.day

    if m in _PEAK_MONTHS:
        return 1.40

    for hm, hs, he in _HOLIDAY_WINDOWS:
        if m == hm and hs <= d <= he:
            return 1.30

    if m in _SHOULDER_MONTHS:
        return 1.15

    # Weekend premium
    if dt.weekday() >= 5:   # Saturday or Sunday
        return 1.10

    return 1.0


# ============================================================
# ✅ FIX-H-CENT / FIX-H-LOC: GEOGRAPHIC CENTRALITY SCORING
# ============================================================
def _haversine_km(lat1, lon1, lat2, lon2):
    R    = 6371
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a    = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))


def _attraction_centroid(places):
    """Return the geographic centroid of all selected attractions."""
    lats = [float(p["lat"]) for p in places if p.get("lat") is not None]
    lons = [float(p["lon"]) for p in places if p.get("lon") is not None]
    if not lats:
        return None, None
    return sum(lats) / len(lats), sum(lons) / len(lons)


def _avg_distance_to_attractions(hotel, places):
    """
    ✅ FIX-H-CENT: Compute average haversine distance from hotel
    to all selected attractions. Lower = more central = better.
    Returns distance in km, or None if coords unavailable.
    """
    h_lat = hotel.get("lat")
    h_lon = hotel.get("lon")
    if h_lat is None or h_lon is None:
        return None

    dists = []
    for p in places:
        p_lat = p.get("lat")
        p_lon = p.get("lon")
        if p_lat is not None and p_lon is not None:
            dists.append(_haversine_km(h_lat, h_lon, p_lat, p_lon))

    return sum(dists) / len(dists) if dists else None


def _estimated_transport_cost(avg_dist_km, days, num_people=1):
    """
    ✅ FIX-H-TOT: Estimate total local transport cost based on avg
    distance to attractions. Assumes taxi at ₹15/km, 3 trips/day.
    Returns cost in INR for the entire trip.
    """
    if avg_dist_km is None:
        return 0
    cost_per_day = avg_dist_km * 2 * 3 * 15   # 2-way × 3 trips × ₹15/km
    return round(cost_per_day * days * min(num_people / 2, 1), 0)


# ============================================================
# 🏆 COMPREHENSIVE HOTEL SCORE  (v8)
# ============================================================
def hotel_score(hotel, places=None, per_night=5000, days=1, num_people=1):
    """
    ✅ FIX-H-LOC + FIX-H-TOT + FIX-H-CENT:
    score = 0.30*rating + 0.30*centrality + 0.20*review + 0.20*total_cost_efficiency
    Total cost efficiency accounts for (hotel_cost + estimated transport cost).
    """
    rating_score  = hotel["rating"] / 10.0

    reviews       = hotel.get("reviews", 500)
    review_score  = min(math.log10(max(reviews, 1)) / 4, 1.0)

    # Centrality score: 0→1 where 0 km avg = 1.0, 30+ km = 0.0
    avg_dist = _avg_distance_to_attractions(hotel, places or [])
    if avg_dist is not None:
        centrality_score = max(0, 1 - avg_dist / 30.0)
    else:
        # Fallback: area keyword overlap
        place_areas = set()
        for p in (places or []):
            for w in p.get("area", "").lower().split(","):
                place_areas.add(w.strip())
        hotel_area = hotel.get("area", "").lower()
        overlap    = sum(1 for a in place_areas if a and a in hotel_area)
        centrality_score = min(overlap * 0.25 + 0.25, 1.0)

    # Total cost efficiency: compare (hotel + transport) vs budget
    hotel_total    = hotel["price"] * days
    transport_cost = _estimated_transport_cost(avg_dist, days, num_people)
    total_trip_cost = hotel_total + transport_cost
    budget_total    = per_night * days * 1.5   # reference = 1.5x hotel budget
    cost_score      = max(0, 1 - total_trip_cost / max(budget_total, 1))

    score = (
        0.30 * rating_score
        + 0.30 * centrality_score
        + 0.20 * review_score
        + 0.20 * cost_score
    )

    # Store breakdown for display
    hotel["_avg_dist_km"]       = round(avg_dist, 1) if avg_dist is not None else None
    hotel["_transport_cost"]    = int(transport_cost)
    hotel["_total_trip_cost"]   = int(total_trip_cost)

    return round(score, 4)


# ============================================================
# ✅ FIX-H-DIV: CATEGORISED RECOMMENDATIONS
# ============================================================
def categorise_hotels(hotels):
    """
    ✅ FIX-H-DIV: Return 4 meaningful categories so users get real choices.
    Categories: Best Location, Best Value, Cheapest, Luxury
    """
    if not hotels:
        return {}

    # Best Location: lowest avg distance to attractions
    with_dist = [h for h in hotels if h.get("_avg_dist_km") is not None]
    best_loc  = min(with_dist, key=lambda h: h["_avg_dist_km"]) if with_dist else hotels[0]

    # Best Value: best score overall (already sorted)
    best_val  = hotels[0]

    # Cheapest: lowest price with rating >= 7.5
    decent    = [h for h in hotels if h["rating"] >= 7.5]
    cheapest  = min(decent, key=lambda h: h["price"]) if decent else min(hotels, key=lambda h: h["price"])

    # Luxury: highest price (if budget allows)
    luxury    = max(hotels, key=lambda h: h["price"])

    return {
        "🏆 Best Value":    best_val,
        "📍 Best Location": best_loc,
        "💸 Cheapest":      cheapest,
        "✨ Luxury Pick":   luxury,
    }


# ============================================================
# 🔗 BOOKING LINKS
# ============================================================
def generate_booking_links(hotel_name, city):
    q = urllib.parse.quote_plus(f"{hotel_name} {city}")
    return {
        "Booking.com":   f"https://www.booking.com/searchresults.html?ss={q}",
        "Google Hotels": f"https://www.google.com/travel/hotels/{q}",
        "MakeMyTrip":    f"https://www.makemytrip.com/hotels/hotel-listing/?searchText={q}",
        "Goibibo":       f"https://www.goibibo.com/hotels/find-hotels/?searchQuery={q}",
    }


# ============================================================
# 🔍 JSON PARSER
# ============================================================
def extract_json(content):
    try:
        return json.loads(content)
    except Exception:
        try:
            s = content.find("[")
            e = content.rfind("]") + 1
            return json.loads(content[s:e]) if s != -1 and e > 0 else None
        except Exception:
            return None


FAKE_WORDS = [
    "budget stay","comfort inn","elite residency","prime hotel",
    "sample hotel","test hotel","demo hotel","luxury stay",
    "grand stay","city inn","tourist lodge",
]

def valid_hotel_name(name):
    if not name or len(name.strip()) < 5:
        return False
    return not any(fw in name.strip().lower() for fw in FAKE_WORDS)


def remove_duplicates(hotels):
    seen, unique = set(), []
    for h in hotels:
        k = h["name"].lower()
        if k not in seen:
            seen.add(k)
            unique.append(h)
    return unique


def parse_hotels(text, budget):
    raw = extract_json(text)
    if not raw:
        return []
    out = []
    for h in raw:
        try:
            name   = str(h.get("name", "")).strip()
            price  = int(float(h.get("price", 0)))
            rating = float(h.get("rating", 0))
            area   = str(h.get("area", "Unknown")).strip()
            if valid_hotel_name(name) and 0 < price <= budget and rating >= 7.0:
                out.append({"name": name, "price": price, "rating": rating,
                             "area": area, "reviews": h.get("reviews", 500),
                             "lat": h.get("lat"), "lon": h.get("lon")})
        except Exception:
            continue
    return out


# ============================================================
# 🏨 MAIN FUNCTION
# ============================================================
def generate_hotels(city, budget, rooms=1, places=None, days=1,
                    num_people=1, check_in_date=None):
    """
    ✅ v8: Accepts days, num_people, check_in_date for better scoring.
    places: list of selected attractions with lat/lon — used for centrality scoring.
    """
    print("\n🏨 Finding hotels...")

    # ✅ FIX-H-SEA: Adjust effective budget by seasonal multiplier
    season_mult  = seasonal_price_multiplier(check_in_date)
    eff_budget   = budget / season_mult   # same money buys less in peak season
    if season_mult > 1.0:
        print(f"   📅 Seasonal pricing: {season_mult:.2f}x multiplier — "
              f"effective budget ₹{int(eff_budget):,}/night")

    verified = _get_verified(city, eff_budget)

    prompt = f"""
You are a hotel booking expert for India.

Suggest 10 REAL, EXISTING hotels in {city}, India with price under ₹{int(eff_budget)} per night.

STRICT RULES:
- Only REAL hotels that actually exist and are bookable online
- No fictional or generic names
- Include the exact property name as found on Booking.com or MakeMyTrip
- Price per night in INR, realistic for {city}
- Rating on a 10-point scale (like Booking.com), minimum 7.0
- Include actual locality / area within {city}
- Estimate number of reviews (integer, e.g. 1200)
- Include approximate lat/lon if you know them

Return ONLY valid JSON, no markdown:
[
  {{
    "name": "Exact Hotel Name",
    "price": 3500,
    "rating": 8.2,
    "area": "Locality in {city}",
    "reviews": 1500,
    "lat": 15.52,
    "lon": 73.77
  }}
]
"""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model":       "meta/llama-3.1-70b-instruct",
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens":  1200,
    }
    llm_hotels = []
    try:
        res = requests.post(URL, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            text       = res.json()["choices"][0]["message"]["content"]
            llm_hotels = parse_hotels(text, eff_budget)
    except Exception:
        pass

    seen = {h["name"].lower() for h in verified}
    for h in llm_hotels:
        if h["name"].lower() not in seen and valid_hotel_name(h["name"]):
            verified.append(h)
            seen.add(h["name"].lower())

    if not verified:
        print("⚠️ Live hotel availability limited. Showing nearest matches.")
        return _get_verified(city, budget * 1.5)

    verified = remove_duplicates(verified)

    # ✅ FIX-H-CENT + FIX-H-TOT: Score with full geo + transport cost awareness
    for h in verified:
        h["_score"]        = hotel_score(h, places=places or [], per_night=eff_budget,
                                         days=days, num_people=num_people)
        h["_season_price"] = int(h["price"] * season_mult)  # display realistic price

    verified.sort(key=lambda h: h["_score"], reverse=True)

    # Return top 8 for categorisation (need pool for 4 distinct categories)
    return verified[:8]


# ============================================================
# 🖨️  DISPLAY  (v8: shows diversity + transport cost)
# ============================================================
def print_hotels(hotels, city, days=1):
    print("\n🏨 Hotel Recommendations (categorised):\n")
    if not hotels:
        print("⚠️ No hotels match your budget. Consider increasing it slightly.")
        return

    categories = categorise_hotels(hotels)

    seen_names = set()
    for category, h in categories.items():
        if h["name"] in seen_names:
            continue
        seen_names.add(h["name"])

        reviews     = h.get("reviews", "N/A")
        score       = h.get("_score", 0)
        season_px   = h.get("_season_price", h["price"])
        avg_dist    = h.get("_avg_dist_km")
        t_cost      = h.get("_transport_cost", 0)
        total_cost  = h.get("_total_trip_cost", 0)

        print(f"{category}")
        print(f"  🏨 {h['name']}")
        print(f"  💰 ₹{season_px:,}/night (base ₹{h['price']:,}) | ⭐ {h['rating']}/10 | 💬 {reviews} reviews")
        print(f"  📍 {h['area']}")
        if avg_dist is not None:
            print(f"  📏 Avg distance to attractions: {avg_dist:.1f} km")
        if t_cost:
            print(f"  🚗 Est. transport cost for trip: ₹{t_cost:,}")
        if total_cost:
            print(f"  💵 Total (hotel {days}n + transport): ₹{total_cost:,}")
        print(f"  🏆 Match Score: {score:.2f}")
        links = generate_booking_links(h["name"], city)
        print("  🔗 Book here:")
        for site, url in links.items():
            print(f"     {site}: {url}")
        print()

    # Also show full ranked list
    print("\n📋 All options ranked by score:\n")
    for i, h in enumerate(hotels, 1):
        season_px = h.get("_season_price", h["price"])
        print(f"  {i}. {h['name']} — ₹{season_px:,}/n | ⭐ {h['rating']} | 📍 {h['area']} | Score: {h.get('_score',0):.2f}")
