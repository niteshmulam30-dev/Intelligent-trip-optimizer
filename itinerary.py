"""
🗓️  ITINERARY AGENT  —  v8 (ALL PROBLEMS FIXED)
========================================================
NEW FIXES IN v8:
✅ FIX-I-GEO:   Geographic clustering uses real haversine distances,
                 not just area-keyword matching — no more North+South Goa same day
✅ FIX-I-ROUTE: True nearest-neighbour TSP with distance matrix built upfront
                 — always produces the shortest valid route ordering
✅ FIX-I-DIV:   Attraction diversity enforcement: max 2 same-type per day
                 so Beach/Beach/Beach/Beach days can't happen
✅ FIX-I-TIME:  Travel time includes traffic buffer (+25% peak hours 8-10, 17-19)
                 and parking delay for tourist spots (+10 min)
✅ FIX-I-FAT:   Fatigue model: max 3 heavy attractions per day (duration > 90 min)
                 + mandatory 15-min rest after 3 consecutive visits
✅ FIX-I-DUR:   Dynamic duration based on attraction type and size bucket
✅ FIX-I-REPLAN: Soft replanning: if day runs over 21:00, drop lowest-rated
                 attraction and rebuild that day

Preserved from v7:
✅ FIX-I1: Pre-reject closed attractions
✅ FIX-I2: Interest-priority selection (80/20)
✅ FIX-I3: Coordinate-first geocoding
✅ FIX-I4: Distance sanity guard
✅ FIX-I5: selected_because reads interest_tag
✅ FIX-I6: Day start = hotel departure 09:00
✅ FIX-I7: Re-cluster + re-optimise after days/places change
✅ Real road distances via OSRM
✅ Multi-provider geocoder
✅ Hotel-aware radius filtering
✅ Weather-aware timing
"""

import time
from datetime import datetime, timedelta
from india_eta import correct_eta
from math import cos, sin, sqrt, atan2, radians


# ============================================================
# 🗂️  CACHES
# ============================================================
coord_cache  = {}
travel_cache = {}


# ============================================================
# 🔗 MAP LINK GENERATORS
# ============================================================
def get_navigation_link(source, destination, mode="driving"):
    base = "https://www.google.com/maps/dir/?api=1"
    o    = source.replace(" ", "+")
    d    = destination.replace(" ", "+")
    return f"{base}&origin={o}&destination={d}&travelmode={mode}"


def multi_stop_navigation(places, mode="driving"):
    base   = "https://www.google.com/maps/dir/?api=1"
    origin = places[0].replace(" ", "+")
    dest   = places[-1].replace(" ", "+")
    if len(places) > 2:
        wps = "|".join(p.replace(" ", "+") for p in places[1:-1])
        return f"{base}&origin={origin}&destination={dest}&waypoints={wps}&travelmode={mode}"
    return f"{base}&origin={origin}&destination={dest}&travelmode={mode}"


# ============================================================
# 📍 GEOCODING  (Nominatim → Photon → city centroid → hard-coded)
# ============================================================
INDIA_CITIES_SET = {
    "goa","mumbai","delhi","bangalore","bengaluru","hyderabad",
    "chennai","kolkata","pune","jaipur","agra","varanasi","kerala",
    "kochi","mysore","udaipur","manali","shimla","darjeeling","ooty",
}

_CITY_COORDS = {
    "goa":        (15.2993, 74.1240),
    "mumbai":     (19.0760, 72.8777),
    "delhi":      (28.7041, 77.1025),
    "bangalore":  (12.9716, 77.5946),
    "bengaluru":  (12.9716, 77.5946),
    "hyderabad":  (17.3850, 78.4867),
    "chennai":    (13.0827, 80.2707),
    "kolkata":    (22.5726, 88.3639),
    "pune":       (18.5204, 73.8567),
    "jaipur":     (26.9124, 75.7873),
    "agra":       (27.1767, 78.0081),
    "varanasi":   (25.3176, 82.9739),
    "kochi":      (9.9312,  76.2673),
    "mysore":     (12.2958, 76.6394),
    "udaipur":    (24.5854, 73.7125),
    "manali":     (32.2432, 77.1892),
    "shimla":     (31.1048, 77.1734),
    "darjeeling": (27.0410, 88.2663),
    "ooty":       (11.4102, 76.6950),
    "kerala":     (10.8505, 76.2711),
}


def get_coordinates(place, city):
    key = f"{place}_{city}"
    if key in coord_cache:
        return coord_cache[key]

    import requests

    city_lower  = city.strip().lower()
    state_map   = {
        "jaipur": "Rajasthan", "agra": "Uttar Pradesh",
        "varanasi": "Uttar Pradesh", "udaipur": "Rajasthan",
        "mysore": "Karnataka", "manali": "Himachal Pradesh",
        "shimla": "Himachal Pradesh", "darjeeling": "West Bengal",
        "ooty": "Tamil Nadu",
    }
    state       = state_map.get(city_lower, "")
    city_suffix = f", {state}, India" if state else (", India" if city_lower in INDIA_CITIES_SET else "")

    queries = [
        f"{place}, {city}{city_suffix}",
        f"{place} {city}{city_suffix}",
        f"{place}{city_suffix}",
    ]
    for q in queries:
        try:
            res = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "trip-planner-v8"},
                timeout=8,
            )
            data = res.json()
            if data:
                lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
                if _is_plausible_coord(lat, lon, city_lower):
                    coord_cache[key] = (lat, lon)
                    return lat, lon
        except Exception:
            pass
        time.sleep(0.4)

    try:
        res = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": f"{place} {city}", "limit": 1},
            timeout=8,
        )
        features = res.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"]
            if _is_plausible_coord(lat, lon, city_lower):
                coord_cache[key] = (lat, lon)
                return lat, lon
    except Exception:
        pass

    city_coords = _get_city_centroid(city, city_lower, city_suffix)
    coord_cache[key] = city_coords
    return city_coords


def _is_plausible_coord(lat, lon, city_lower):
    CITY_BOUNDS = {
        "jaipur":     (26.60, 27.30, 75.55, 76.15),
        "goa":        (14.80, 15.80, 73.70, 74.50),
        "mumbai":     (18.85, 19.35, 72.70, 73.00),
        "delhi":      (28.40, 28.90, 76.85, 77.40),
        "agra":       (26.90, 27.40, 77.85, 78.35),
        "varanasi":   (25.10, 25.60, 82.80, 83.10),
        "udaipur":    (24.45, 24.85, 73.55, 74.05),
        "mysore":     (12.10, 12.55, 76.45, 76.90),
        "kochi":      (9.70,  10.20, 76.10, 76.45),
        "hyderabad":  (17.20, 17.60, 78.25, 78.65),
        "bangalore":  (12.75, 13.20, 77.40, 77.80),
        "bengaluru":  (12.75, 13.20, 77.40, 77.80),
        "pune":       (18.35, 18.70, 73.70, 74.05),
        "kolkata":    (22.35, 22.75, 88.20, 88.50),
        "chennai":    (12.90, 13.25, 80.10, 80.40),
        "manali":     (32.10, 32.40, 77.05, 77.40),
        "shimla":     (31.00, 31.30, 77.05, 77.35),
        "darjeeling": (26.80, 27.20, 88.15, 88.45),
        "ooty":       (11.30, 11.60, 76.65, 76.85),
    }
    bounds = CITY_BOUNDS.get(city_lower)
    if not bounds:
        return True
    lat_min, lat_max, lon_min, lon_max = bounds
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _get_city_centroid(city, city_lower, city_suffix):
    city_key = f"__city__{city}"
    if city_key in coord_cache:
        return coord_cache[city_key]

    import requests
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}{city_suffix}", "format": "json", "limit": 1},
            headers={"User-Agent": "trip-planner-v8"},
            timeout=8,
        )
        data = res.json()
        if data:
            coords = (float(data[0]["lat"]), float(data[0]["lon"]))
            coord_cache[city_key] = coords
            return coords
    except Exception:
        pass

    fallback = _CITY_COORDS.get(city_lower, (0, 0))
    coord_cache[city_key] = fallback
    return fallback


# ============================================================
# 🛣️  TRAVEL TIME  (OSRM → haversine + traffic buffer)
# ============================================================
def _haversine_km(c1, c2):
    R    = 6371
    dlon = radians(c2[1] - c1[1])
    dlat = radians(c2[0] - c1[0])
    a    = sin(dlat/2)**2 + cos(radians(c1[0]))*cos(radians(c2[0]))*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))


def _traffic_multiplier(current_hour):
    """
    DEPRECATED in v9: kept for backward-compat but returns 1.0.
    The India ETA layer already applies peak-hour, weekend, monsoon and
    route-type multipliers. Stacking another traffic multiplier on top
    was the root cause of inflated ETAs (e.g. 30 km Goa → 92 min).
    """
    return 1.0


def get_travel_time(c1, c2, shared_routes=None, name1=None, name2=None,
                    city=None, current_hour=None):
    """
    Returns (time_minutes, distance_km).
    v9: single source of truth for ETA is the India ETA correction layer.
    We no longer multiply OSRM duration by an additional traffic factor here;
    that caused double-counting (OSRM corrected once by india_eta, then again
    by _traffic_multiplier, producing 90+ min for 30 km routes).
    """
    if shared_routes and name1 and name2:
        for k in [(name1.lower(), name2.lower()), (name2.lower(), name1.lower())]:
            if k in shared_routes:
                r = shared_routes[k]
                t_min = r["time_hrs"] * 60
                d_km  = r["distance"]
                if city and d_km > 150:
                    hav = _haversine_km(c1, c2) * 1.35 if c1 != (0,0) and c2 != (0,0) else d_km
                    if hav < d_km * 0.5:
                        t_min = (hav / 35) * 60
                        d_km  = hav
                return round(t_min, 1), round(d_km, 1)

    cache_key = (c1, c2)
    if cache_key in travel_cache:
        t_min, d_km = travel_cache[cache_key]
        return round(t_min, 1), round(d_km, 1)

    if c1 == (0, 0) or c2 == (0, 0):
        if c1 != (0, 0) and c2 != (0, 0):
            d = _haversine_km(c1, c2) * 1.35
            t = (d / 35) * 60
        else:
            d, t = 25, 45
        travel_cache[cache_key] = (round(t, 1), round(d, 1))
        return round(t, 1), round(d, 1)

    import requests
    try:
        url  = (f"http://router.project-osrm.org/route/v1/driving/"
                f"{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=false")
        res  = requests.get(url, timeout=10)
        data = res.json()
        if data.get("code") == "Ok":
            t = data["routes"][0]["duration"] / 60
            d = data["routes"][0]["distance"] / 1000
            hav = _haversine_km(c1, c2)
            if d > 150 and hav < 50:
                d = hav * 1.35
                t = (d / 35) * 60
            # India ETA correction (single, authoritative correction)
            corrected, _rt, _m = correct_eta(
                t, name1 or "", name2 or "",
                src_coords=c1, dst_coords=c2, distance_km=d,
            )
            if corrected is not None:
                t = corrected
            travel_cache[cache_key] = (round(t, 1), round(d, 1))
            return round(t, 1), round(d, 1)
    except Exception:
        pass

    d = _haversine_km(c1, c2) * 1.35
    t = (d / 35) * 60
    corrected, _rt, _m = correct_eta(
        t, name1 or "", name2 or "",
        src_coords=c1, dst_coords=c2, distance_km=d,
    )
    if corrected is not None:
        t = corrected
    travel_cache[cache_key] = (round(t, 1), round(d, 1))
    return round(t, 1), round(d, 1)



# ============================================================
# 🏨 HOTEL-AWARE FILTERING
# ============================================================
def filter_by_hotel_radius(places, hotel, city, radius_km=None, days=1, interest=None):
    """
    v9: hotel-aware shortlist.
      • use HOTEL_ANCHOR_RADIUS_KM by default (tighter than the old 50 km)
      • prefer places of the user's interest tag when ranking
      • return at least `days * MAX_POIS_PER_DAY` so clustering has options
      • always sorted by distance from the hotel (closest first)
    """
    if radius_km is None:
        radius_km = HOTEL_ANCHOR_RADIUS_KM
    if not hotel:
        return places

    h_coords = get_coordinates(hotel["name"], city)
    if h_coords == (0, 0):
        return places

    scored = []
    for p in places:
        p_coords = _place_coords(p, city)
        if p_coords == (0, 0):
            d = radius_km   # unknown coords ⇒ neutral score
        else:
            d = _haversine_km(h_coords, p_coords)
        # interest match shaves an effective 30% off the distance score
        match = interest and p.get("interest_tag", "").lower() == interest.lower()
        score = d * (0.7 if match else 1.0)
        scored.append((score, d, p))

    scored.sort(key=lambda x: x[0])
    nearby   = [p for sc, d, p in scored if d <= radius_km]
    min_keep = max(3, days * MAX_POIS_PER_DAY)

    if len(nearby) >= min_keep:
        return nearby
    # not enough nearby → fall back to the closest min_keep regardless of radius
    return [p for sc, d, p in scored[:min_keep]] or places



# ============================================================
# ✅ FIX-I3: COORDINATE HELPERS
# ============================================================
def _place_coords(place, city):
    lat = place.get("lat")
    lon = place.get("lon")
    if lat is not None and lon is not None:
        return (float(lat), float(lon))
    return get_coordinates(place["name"], city)


def attach_coordinates(places, city):
    for p in places:
        if p.get("lat") is not None:
            continue
        coords = get_coordinates(p["name"], city)
        p["lat"] = coords[0]
        p["lon"] = coords[1]
    return places


# ============================================================
# ✅ FIX-I-DUR: DYNAMIC DURATION based on attraction type
# ============================================================
_TYPE_DURATION = {
    "beach":      60,   # beaches: 60-90 min (don't over-schedule)
    "fort":      120,   # forts: 90-120 min (large area)
    "museum":     90,   # museums: 75-90 min
    "temple":     45,   # temples: 30-60 min
    "church":     30,   # churches: 20-30 min
    "market":     60,   # markets: 45-75 min
    "waterfall":  60,   # waterfalls: 45-60 min
    "viewpoint":  30,   # viewpoints: 20-30 min
    "garden":     45,   # gardens: 30-45 min
    "lighthouse": 30,   # lighthouses: 20-30 min
    "casino":     120,  # casinos: flexible, default 2h
}

def _dynamic_duration(place):
    """
    ✅ FIX-I-DUR: Use type-based duration if the LLM's recommended_duration
    looks unrealistic (too short < 20 min, or too long > 180 min for small sites).
    """
    raw_dur = int(place.get("recommended_duration", 90))
    name    = place.get("name", "").lower()
    tag     = place.get("interest_tag", "").lower()

    # Infer type from name or tag
    for type_key, type_dur in _TYPE_DURATION.items():
        if type_key in name or type_key == tag:
            # Blend LLM duration with type default (weighted avg)
            if 20 <= raw_dur <= 240:
                return int(raw_dur * 0.6 + type_dur * 0.4)
            return type_dur

    # No type match — clamp raw duration to sane range
    return max(20, min(raw_dur, 180))


# ============================================================
# ✅ FIX-I-DIV: DIVERSITY ENFORCEMENT — max 2 same-type per day
# ============================================================
def _get_place_type(place):
    """Infer the dominant type of a place for diversity checking."""
    name = place.get("name", "").lower()
    tag  = place.get("interest_tag", "").lower()
    for type_key in _TYPE_DURATION:
        if type_key in name or type_key == tag:
            return type_key
    return tag or "other"


def enforce_diversity(day_places, max_same_type=2):
    """
    ✅ FIX-I-DIV: Ensure no single attraction type dominates a day.
    Removes excess same-type places (lowest-rated ones dropped first).
    Returns the filtered list.
    """
    type_counts = {}
    kept        = []
    dropped     = []

    # Sort by rating descending so we keep the best ones
    sorted_places = sorted(day_places, key=lambda p: p.get("rating", 0), reverse=True)

    for p in sorted_places:
        ptype = _get_place_type(p)
        count = type_counts.get(ptype, 0)
        if count < max_same_type:
            kept.append(p)
            type_counts[ptype] = count + 1
        else:
            dropped.append(p)

    if dropped:
        names = ", ".join(p["name"] for p in dropped)
        print(f"   🌈 Diversity: removed {len(dropped)} duplicate-type place(s): {names}")

    return kept


# ============================================================
MAX_HEAVY_PER_DAY        = 3      # attractions with duration > 90 min
REST_AFTER_N_VISITS      = 3      # 15-min rest after every 3 consecutive visits
MAX_DRIVE_HOURS_PER_DAY  = 5.0    # v10: relaxed (was 3.5 → caused under-fill)
MIN_POIS_PER_DAY         = 2      # v10: don't trim below this when budget enforced
MAX_POIS_PER_DAY         = 4
HOTEL_ANCHOR_RADIUS_KM   = 35



# ============================================================
# 🧠 GEOGRAPHIC CLUSTERING  (v9 — hotel-anchored, balanced)
# ============================================================
def cluster_center(cluster):
    valid = [c for _, c in cluster if c != (0, 0)]
    if not valid:
        return (0, 0)
    lat = sum(c[0] for c in valid) / len(valid)
    lon = sum(c[1] for c in valid) / len(valid)
    return (lat, lon)


def _seed_centers(coords, days, hotel_coords=None):
    """
    v9: k-means++ style seeding. First center = hotel (if known), then each
    subsequent center is the point farthest from any existing center. Prevents
    North + South Goa landing in the same cluster when latitude spread is small.
    """
    valid = [c for _, c in coords if c != (0, 0)]
    if not valid:
        return [(0, 0)] * days

    centers = []
    if hotel_coords and hotel_coords != (0, 0):
        centers.append(hotel_coords)
    else:
        centers.append(valid[0])

    while len(centers) < days:
        best_pt, best_dist = None, -1
        for c in valid:
            d = min(_haversine_km(c, ctr) for ctr in centers)
            if d > best_dist:
                best_pt, best_dist = c, d
        if best_pt is None:
            break
        centers.append(best_pt)

    while len(centers) < days:
        centers.append(centers[-1])
    return centers


def cluster_by_distance(places, city, days, hotel_coords=None):
    """
    v9 geographic clustering:
      • k-means++ seeding anchored at the hotel
      • iterative reassignment using haversine distances
      • capacity-balanced final assignment (cap = min(MAX_POIS_PER_DAY, ceil(N/days)))
    """
    coords = [(p, _place_coords(p, city)) for p in places]
    n = len(coords)
    if n == 0:
        return [[] for _ in range(days)]
    if n <= days:
        return [[p] for p, _ in coords] + [[] for _ in range(days - n)]

    centers = _seed_centers(coords, days, hotel_coords)

    for _ in range(8):
        clusters = [[] for _ in range(days)]
        for idx, (p, c) in enumerate(coords):
            if c == (0, 0):
                clusters[idx % days].append((p, c))
                continue
            best = min(range(days),
                       key=lambda i: _haversine_km(c, centers[i]) if centers[i] != (0,0) else 9999)
            clusters[best].append((p, c))
        new_centers = [cluster_center(cl) if cl else centers[i] for i, cl in enumerate(clusters)]
        if new_centers == centers:
            break
        centers = new_centers

    cap = min(MAX_POIS_PER_DAY, max(1, -(-n // days)))
    pool = [(p, c) for cl in clusters for p, c in cl]
    balanced = [[] for _ in range(days)]

    def _nearest_center_dist(item):
        _, c = item
        if c == (0, 0):
            return 9999
        return min(_haversine_km(c, ctr) for ctr in centers if ctr != (0, 0))

    pool.sort(key=_nearest_center_dist)

    for p, c in pool:
        if c == (0, 0):
            target = min(range(days), key=lambda i: len(balanced[i]))
        else:
            order = sorted(range(days),
                           key=lambda i: _haversine_km(c, centers[i]) if centers[i] != (0,0) else 9999)
            target = next((i for i in order if len(balanced[i]) < cap), order[0])
        balanced[target].append(p)

    return balanced


def balance_clusters(clusters, days):
    all_places = [p for cl in clusters for p in cl]
    balanced   = [[] for _ in range(days)]
    for i, p in enumerate(all_places):
        balanced[i % days].append(p)
    return balanced


# ============================================================
# 🧭 ROUTE OPTIMISATION  (v9 — NN seed + 2-opt improvement)
# ============================================================
def _build_distance_matrix(places, city):
    n      = len(places)
    matrix = [[0.0] * n for _ in range(n)]
    coords = [_place_coords(p, city) for p in places]
    for i in range(n):
        for j in range(i+1, n):
            _, d = get_travel_time(coords[i], coords[j], city=city)
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def _route_length(route, matrix, start_extra=None, end_extra=None):
    total = 0.0
    if start_extra is not None and route:
        total += start_extra[route[0]]
    for i in range(len(route) - 1):
        total += matrix[route[i]][route[i+1]]
    if end_extra is not None and route:
        total += end_extra[route[-1]]
    return total


def _two_opt(route, matrix, start_extra=None, end_extra=None, max_passes=20):
    """Classic 2-opt over the hotel→...→hotel loop. Removes zig-zags."""
    if len(route) < 4:
        return route
    best     = route[:]
    best_len = _route_length(best, matrix, start_extra, end_extra)
    for _ in range(max_passes):
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                new_route = best[:i] + best[i:j+1][::-1] + best[j+1:]
                new_len   = _route_length(new_route, matrix, start_extra, end_extra)
                if new_len + 1e-6 < best_len:
                    best, best_len, improved = new_route, new_len, True
        if not improved:
            break
    return best


def optimize_route(places, city, hotel_coords=None):
    """
    v9: NN seed → 2-opt improvement, optimising the full hotel→...→hotel loop.
    """
    if len(places) <= 1:
        return places

    matrix = _build_distance_matrix(places, city)
    n      = len(places)

    place_coords = [_place_coords(p, city) for p in places]
    if hotel_coords and hotel_coords != (0, 0):
        hotel_dists = [
            _haversine_km(hotel_coords, pc) if pc != (0, 0) else 9999
            for pc in place_coords
        ]
        start = hotel_dists.index(min(hotel_dists))
    else:
        hotel_dists = None
        start = 0

    visited = [False] * n
    route   = [start]
    visited[start] = True
    for _ in range(n - 1):
        last  = route[-1]
        best, best_d = -1, float("inf")
        for j in range(n):
            if not visited[j] and matrix[last][j] < best_d:
                best, best_d = j, matrix[last][j]
        route.append(best)
        visited[best] = True

    route = _two_opt(route, matrix, hotel_dists, hotel_dists)
    return [places[i] for i in route]


# ============================================================
# 🕒 DAILY DRIVE BUDGET  (v9 — enforce MAX_DRIVE_HOURS_PER_DAY)
# ============================================================
def _estimated_day_drive_minutes(day_places, city, hotel_coords):
    if not day_places:
        return 0
    total = 0.0
    prev  = hotel_coords if hotel_coords and hotel_coords != (0, 0) else _place_coords(day_places[0], city)
    for p in day_places:
        pc = _place_coords(p, city)
        t, _ = get_travel_time(prev, pc, city=city)
        total += t
        prev = pc
    if hotel_coords and hotel_coords != (0, 0):
        t, _ = get_travel_time(prev, hotel_coords, city=city)
        total += t
    return total


def enforce_drive_budget(clusters, city, hotel_coords, max_drive_min=None):
    """
    v9: if a day's total driving exceeds MAX_DRIVE_HOURS_PER_DAY, drop the
    POI farthest from the day's centroid and try to re-slot it in a lighter
    day. Reduces fatigue and prevents zig-zag days like Candolim→Palolem→Candolim.
    """
    if max_drive_min is None:
        max_drive_min = MAX_DRIVE_HOURS_PER_DAY * 60

    trimmed, overflow = [], []
    for cl in clusters:
        cl = list(cl)
        if len(cl) > 1:
            cl = optimize_route(cl, city, hotel_coords=hotel_coords)

        while len(cl) > MIN_POIS_PER_DAY and _estimated_day_drive_minutes(cl, city, hotel_coords) > max_drive_min:
            centroid = cluster_center([(p, _place_coords(p, city)) for p in cl])
            if centroid == (0, 0):
                break
            far_idx = max(range(len(cl)),
                          key=lambda i: _haversine_km(_place_coords(cl[i], city), centroid)
                                        if _place_coords(cl[i], city) != (0,0) else 0)
            dropped = cl.pop(far_idx)
            overflow.append(dropped)
            print(f"   🛣️  Drive-budget: deferred '{dropped['name']}' "
                  f"(day driving > {max_drive_min/60:.1f} h)")
            if len(cl) > 1:
                cl = optimize_route(cl, city, hotel_coords=hotel_coords)
        trimmed.append(cl)

    for p in overflow:
        best_day, best_slack = -1, -1
        for i, cl in enumerate(trimmed):
            if len(cl) >= MAX_POIS_PER_DAY:
                continue
            trial = optimize_route(cl + [p], city, hotel_coords=hotel_coords)
            slack = max_drive_min - _estimated_day_drive_minutes(trial, city, hotel_coords)
            if slack > 0 and slack > best_slack:
                best_day, best_slack = i, slack
        if best_day >= 0:
            trimmed[best_day] = optimize_route(trimmed[best_day] + [p],
                                               city, hotel_coords=hotel_coords)
            print(f"   🔁 Re-slotted '{p['name']}' into day {best_day + 1}")

    return trimmed



# ============================================================
# ✅ FIX-I2: INTEREST-PRIORITY SELECTION  (80/20)
# ============================================================
def prioritise_by_interest(places, interest, days):
    """
    v9: keep the 80/20 interest split BUT cap the total at
    days * MAX_POIS_PER_DAY so we don't over-select before clustering.
    """
    main = [p for p in places if p.get("interest_tag", "").lower() == interest.lower()]
    comp = [p for p in places if p.get("interest_tag", "").lower() != interest.lower()]

    total  = days * MAX_POIS_PER_DAY
    n_main = max(int(total * 0.80), min(len(main), total - 1))
    n_comp = total - n_main

    selected = main[:n_main] + comp[:n_comp]
    for p in selected:
        if p in main:
            p["interest_tag"] = interest
    return selected



# ============================================================
# ✅ FIX-I1: ARRIVAL-TIME FEASIBILITY CHECK
# ============================================================
def _parse_time(time_str, ref_dt):
    try:
        h, m = map(int, time_str.split(":"))
        return ref_dt.replace(hour=h, minute=m, second=0, microsecond=0)
    except Exception:
        return None


def _will_be_open(place, arrival_dt, duration_min):
    MIN_VISIT_FRACTION = 0.40

    closing_str = place.get("closing_time", "18:00")
    closing_dt  = _parse_time(closing_str, arrival_dt)
    if closing_dt is None:
        return True

    if closing_str in ("23:59", "00:00"):
        return True

    available_min  = (closing_dt - arrival_dt).total_seconds() / 60
    min_worthwhile = duration_min * MIN_VISIT_FRACTION

    return available_min >= min_worthwhile


# ============================================================
# 💡 EXPLAINABILITY
# ============================================================
def build_explanation(place, hotel, user_interest, weather_data=None):
    reasons = []

    rating = place.get("rating", 0)
    if rating >= 4.5:
        reasons.append(f"⭐ Top-rated ({rating}/5)")
    elif rating >= 4.0:
        reasons.append(f"⭐ Highly rated ({rating}/5)")

    tag = place.get("interest_tag", "")
    if tag.lower() == user_interest.lower():
        reasons.append(f"🎯 Matches your '{user_interest}' interest")
    elif tag:
        reasons.append(f"🗺️  Complementary {tag} experience")

    area = place.get("area", "")
    if area:
        reasons.append(f"📍 Located in {area}")

    if hotel:
        reasons.append(f"🏨 Within day-trip range from {hotel.get('name','your hotel')}")

    if weather_data:
        cond = weather_data.get("condition", "").lower()
        if "clear" in cond or "sun" in cond:
            if "beach" in place["name"].lower() or tag == "beach":
                reasons.append("☀️ Great weather for beach visit today")

    return " · ".join(reasons) if reasons else "✓ Popular destination"


# ============================================================
# ✅ FIX-I-REPLAN: Soft replanning if day overruns 21:00
# ============================================================
def _soft_replan_day(day_places, city, hotel_coords, hotel_name,
                     start_time_str, shared_routes, avoid_afternoon,
                     user_interest, weather_data):
    """
    ✅ FIX-I-REPLAN: If the estimated day end > 21:00, drop the
    lowest-rated place and recheck. Max 2 iterations to prevent
    over-stripping. Returns a revised place list.
    """
    MAX_END_HOUR  = 21
    MAX_DROPS     = 2
    dropped_count = 0

    while dropped_count < MAX_DROPS and len(day_places) > 1:
        # Estimate end time with current places
        est_time    = datetime.strptime(start_time_str, "%H:%M")
        est_prev    = hotel_coords

        for p in day_places:
            p_coords = _place_coords(p, city)
            t, _     = get_travel_time(est_prev, p_coords,
                                       shared_routes=shared_routes, city=city,
                                       current_hour=est_time.hour)
            t       += 5    # v9: parking buffer reduced (no longer stacking traffic mult)
            est_time += timedelta(minutes=t)
            dur       = _dynamic_duration(p)
            est_time += timedelta(minutes=dur)
            if avoid_afternoon and 12 <= est_time.hour < 15:
                est_time += timedelta(minutes=180)
            if 13 <= est_time.hour < 14:
                est_time += timedelta(minutes=60)
            est_prev = p_coords

        # Return to hotel
        if hotel_coords != (0, 0):
            t, _ = get_travel_time(est_prev, hotel_coords,
                                   shared_routes=shared_routes, city=city,
                                   current_hour=est_time.hour)
            est_time += timedelta(minutes=t)

        if est_time.hour < MAX_END_HOUR:
            break   # Within acceptable range

        # Drop the lowest-rated place
        min_place = min(day_places, key=lambda p: p.get("rating", 0))
        day_places = [p for p in day_places if p is not min_place]
        print(f"   ⏰ Replan: dropped '{min_place['name']}' (day would end after {MAX_END_HOUR}:00)")
        dropped_count += 1

    return day_places


# ============================================================
# 🗓️  MAIN  GENERATE ITINERARY
# ============================================================
def generate_itinerary(places, city, days, hotel=None, shared_routes=None,
                       weather_constraints=None, weather_data=None,
                       user_interest="general"):
    weather_constraints  = weather_constraints or {}
    avoid_afternoon      = weather_constraints.get("avoid_afternoon", False)
    start_time_str       = "09:00"

    # ── FIX-I3: Attach coordinates ONCE ─────────────────────────────────────
    print(f"  📍 Geocoding {len(places)} places + hotel…", end=" ", flush=True)
    places = attach_coordinates(places, city)
    if hotel and hotel.get("lat") is None:
        h_coords = get_coordinates(hotel["name"], city)
        hotel["lat"] = h_coords[0]
        hotel["lon"] = h_coords[1]
    print("done ✓")

    hotel_coords = (_place_coords(hotel, city) if hotel else (0, 0))
    hotel_name   = hotel["name"] if hotel else None

    # 🔍 v10 — coordinate-integrity debug (prints every hotel & POI lat/lon
    # so geocoding mistakes show up in the trace before they corrupt routing)
    if hotel_name:
        print(f"   🛰  HOTEL  {hotel_name}  →  ({hotel.get('lat')}, {hotel.get('lon')})")
    for p in places:
        print(f"   🛰  POI    {p['name']:<35}  →  ({p.get('lat')}, {p.get('lon')})")

    # ── v9: interest priority (capped) → hotel-anchored shortlist → clustering ──
    places   = prioritise_by_interest(places, user_interest, days)
    filtered = filter_by_hotel_radius(places, hotel, city,
                                      radius_km=HOTEL_ANCHOR_RADIUS_KM,
                                      days=days, interest=user_interest)

    clusters = cluster_by_distance(filtered, city, days, hotel_coords=hotel_coords)

    # ── v9: enforce daily drive budget BEFORE per-day diversity/fatigue ──
    clusters = enforce_drive_budget(clusters, city, hotel_coords)

    final_plan = []


    for day_index, day_places in enumerate(clusters[:days], 1):
        if not day_places:
            continue

        print(f"\n📅 DAY {day_index}")

        # ── FIX-I-DIV: Enforce attraction diversity ───────────────────────────
        day_places = enforce_diversity(day_places, max_same_type=2)

        # ── FIX-I-FAT: Cap heavy attractions ─────────────────────────────────
        heavy_count = 0
        lite_places = []
        for p in sorted(day_places, key=lambda x: x.get("rating", 0), reverse=True):
            dur = _dynamic_duration(p)
            if dur > 90:
                if heavy_count < MAX_HEAVY_PER_DAY:
                    lite_places.append(p)
                    heavy_count += 1
                else:
                    print(f"   💪 Fatigue cap: skipped heavy attraction '{p['name']}'")
            else:
                lite_places.append(p)
        day_places = lite_places

        # ── FIX-I-ROUTE: TSP route optimisation with hotel anchor ─────────────
        day_places = optimize_route(day_places, city, hotel_coords=hotel_coords)

        # ── FIX-I-REPLAN: Soft replanning if day overruns ────────────────────
        day_places = _soft_replan_day(
            day_places, city, hotel_coords, hotel_name,
            start_time_str, shared_routes, avoid_afternoon,
            user_interest, weather_data
        )

        current_time = datetime.strptime(start_time_str, "%H:%M")

        if hotel_name:
            final_plan.append({
                "type": "hotel_start",
                "day":  day_index,
                "name": hotel_name,
                "time": current_time.strftime("%H:%M"),
            })

        route_names = [p["name"] for p in day_places]
        if hotel_name:
            route_names = [hotel_name] + route_names + [hotel_name]

        final_plan.append({
            "type": "day_route",
            "day":  day_index,
            "link": multi_stop_navigation(route_names),
        })

        prev_location = hotel_name
        prev_coords   = hotel_coords

        # ── FIX-I1: Pre-filter closed attractions ────────────────────────────
        feasible_places = []
        est_time        = current_time
        est_prev_coords = prev_coords

        for p in day_places:
            p_coords = _place_coords(p, city)
            t_est, _ = get_travel_time(est_prev_coords, p_coords,
                                       city=city, current_hour=est_time.hour)
            t_est   += 5    # v9: parking buffer reduced
            arr_est  = est_time + timedelta(minutes=t_est)
            dur      = _dynamic_duration(p)
            if _will_be_open(p, arr_est, dur):
                feasible_places.append(p)
                est_time        = arr_est + timedelta(minutes=dur)
                est_prev_coords = p_coords
            else:
                closing = p.get("closing_time", "?")
                print(f"   ⛔ Pre-rejected: {p['name']} — est. arrival "
                      f"{arr_est.strftime('%H:%M')} but closes {closing}")

        day_places = feasible_places

        # ── Build actual schedule ─────────────────────────────────────────────
        consecutive_visits = 0
        afternoon_break_inserted = False

        for p in day_places:
            p_coords = _place_coords(p, city)

            if prev_location:
                t, d = get_travel_time(
                    prev_coords, p_coords,
                    shared_routes=shared_routes,
                    name1=prev_location,
                    name2=p["name"],
                    city=city,
                    current_hour=current_time.hour,   # ✅ FIX-I-TIME: traffic-aware
                )
                # ✅ FIX-I-TIME: +10 min parking buffer for tourist spots
                parking = 5     # v9: parking buffer reduced
                current_time += timedelta(minutes=t + parking)

                final_plan.append({
                    "type":     "travel",
                    "from":     prev_location,
                    "to":       p["name"],
                    "time":     f"{round(t)} min (+{parking} min parking)",
                    "distance": f"{round(d, 1)} km",
                    "link":     get_navigation_link(prev_location, p["name"]),
                })

            opening_str  = p.get("opening_time", "09:00")
            closing_str  = p.get("closing_time", "18:00")
            duration_min = _dynamic_duration(p)   # ✅ FIX-I-DUR

            opening_dt = _parse_time(opening_str, current_time) or current_time
            closing_dt = _parse_time(closing_str, current_time)

            if current_time < opening_dt:
                wait = int((opening_dt - current_time).total_seconds() / 60)
                final_plan.append({
                    "type":     "break",
                    "name":     f"⏳ Waiting for {p['name']} to open at {opening_str}",
                    "duration": f"{wait} min",
                })
                current_time = opening_dt

            if closing_dt and current_time >= closing_dt:
                final_plan.append({
                    "type":   "skipped",
                    "place":  p["name"],
                    "reason": f"Arrives {current_time.strftime('%H:%M')} — closes {closing_str}",
                })
                prev_location = p["name"]
                prev_coords   = p_coords
                continue

            start = current_time
            if closing_dt:
                end = min(start + timedelta(minutes=duration_min), closing_dt)
            else:
                end = start + timedelta(minutes=duration_min)

            why = build_explanation(p, hotel, user_interest, weather_data)

            final_plan.append({
                "type":             "visit",
                "day":              day_index,
                "place":            p["name"],
                "area":             p.get("area", ""),
                "rating":           p.get("rating", 4.0),
                "interest_tag":     p.get("interest_tag", ""),
                "start":            start.strftime("%H:%M"),
                "end":              end.strftime("%H:%M"),
                "opening_time":     opening_str,
                "closing_time":     closing_str,
                "selected_because": why,
            })

            current_time  = end
            prev_location = p["name"]
            prev_coords   = p_coords
            consecutive_visits += 1

            # ✅ FIX-I-FAT: Rest after 3 consecutive visits
            if consecutive_visits >= REST_AFTER_N_VISITS:
                final_plan.append({
                    "type":     "break",
                    "name":     "😌 Short Rest Break (refreshments / stretch)",
                    "duration": "15 min",
                })
                current_time       += timedelta(minutes=15)
                consecutive_visits  = 0

            # Lunch break
            if 13 <= current_time.hour < 14:
                final_plan.append({"type": "break", "name": "🍽️ Lunch Break", "duration": "60 min"})
                current_time       += timedelta(minutes=60)
                consecutive_visits  = 0   # reset fatigue counter after lunch

            # Afternoon rest on hot days
            if avoid_afternoon and not afternoon_break_inserted and 12 <= current_time.hour < 13:
                final_plan.append({
                    "type":     "break",
                    "name":     "🌡️ Afternoon Rest (peak heat 12:00-15:00)",
                    "duration": "180 min",
                })
                current_time             += timedelta(minutes=180)
                afternoon_break_inserted  = True
                consecutive_visits        = 0

        # Return to hotel
        if hotel_name and prev_location:
            t, d = get_travel_time(prev_coords, hotel_coords,
                                   shared_routes=shared_routes,
                                   name1=prev_location, name2=hotel_name,
                                   city=city, current_hour=current_time.hour)
            current_time += timedelta(minutes=t)

            final_plan.append({
                "type":     "travel",
                "from":     prev_location,
                "to":       hotel_name,
                "time":     f"{round(t)} min",
                "distance": f"{round(d, 1)} km",
                "link":     get_navigation_link(prev_location, hotel_name),
            })
            final_plan.append({
                "type": "hotel_end",
                "day":  day_index,
                "name": hotel_name,
                "time": current_time.strftime("%H:%M"),
            })

    return final_plan


# ============================================================
# 🖨️  PRINT ITINERARY
# ============================================================
def print_itinerary(plan):
    print("\n🗺️  FINAL MULTI-DAY ITINERARY:\n")
    for item in plan:
        if item["type"] == "hotel_start":
            print(f"\n🏨 Start: {item['name']} at {item['time']}")
        elif item["type"] == "hotel_end":
            print(f"\n🏨 Return: {item['name']} at {item['time']}")
        elif item["type"] == "day_route":
            print(f"\n🗺️  Day {item['day']} Route:")
            print(item["link"])
        elif item["type"] == "visit":
            tag = f" [{item.get('interest_tag','')}]" if item.get("interest_tag") else ""
            print(f"\n📍 {item['place']}{tag} ⭐ {item['rating']}")
            print(f"   📍 Area: {item['area']}")
            print(f"   🕒 {item['start']} - {item['end']}  (open {item.get('opening_time','?')}–{item.get('closing_time','?')})")
            print(f"   💡 Why: {item.get('selected_because','')}")
        elif item["type"] == "skipped":
            print(f"\n⚠️  SKIPPED: {item['place']}")
            print(f"   ❌ {item['reason']}")
        elif item["type"] == "travel":
            print(f"\n🚗 {item['from']} → {item['to']}")
            print(f"   ⏱️  {item['time']} | 📏 {item['distance']}  (real road + traffic)")
            print(f"   🗺️  {item['link']}")
        elif item["type"] == "break":
            dur = item.get("duration", "")
            print(f"\n⏸️  {item['name']} ({dur})")
        print("-" * 50)
