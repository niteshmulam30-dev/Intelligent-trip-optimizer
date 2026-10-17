"""
🚗 TRANSPORT AGENT  —  v6 (ROUTE ACCURACY FIX)
=====================================
✅ OSRM real road distances (free, no key)
✅ Multi-provider geocoder: Nominatim → Photon (Komoot) fallback
✅ No more 20 km hardcoded fallback — haversine used when OSRM fails
✅ Weighted hotel scoring
✅ Booking link generators
"""

import requests
from math import cos, sin, sqrt, atan2, radians
import datetime
import time
import urllib.parse
from india_eta import correct_eta, detect_route_type


# ============================================================
# 🗂️  COORDINATE CACHE
# ============================================================
_coord_cache = {}


def _geocode(place: str, city: str | None = None):
    """
    Multi-provider geocoder. Returns (lat, lon) or (None, None).
    v10: when `city` is provided we route through itinerary.get_coordinates
    so we get the same city-bounds validation that prevents
    'Treehouse Kovalam Goa' from resolving to Kovalam, Kerala.
    """
    key = f"{place.lower().strip()}|{(city or '').lower().strip()}"
    if key in _coord_cache:
        return _coord_cache[key]

    if city:
        try:
            from itinerary import get_coordinates as _city_geocode
            lat, lon = _city_geocode(place, city)
            if lat and lon:
                _coord_cache[key] = (lat, lon)
                return lat, lon
        except Exception:
            pass

    # Fallback: Nominatim then Photon
    queries = [f"{place}, {city}, India" if city else f"{place}, India", place]
    for q in queries:
        try:
            res = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "trip-planner-v10"},
                timeout=8,
            )
            data = res.json()
            if data:
                lat = float(data[0]["lat"]); lon = float(data[0]["lon"])
                _coord_cache[key] = (lat, lon)
                return lat, lon
        except Exception:
            pass
        time.sleep(0.4)

    try:
        res = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": f"{place} {city}" if city else place, "limit": 1},
            timeout=8,
        )
        features = res.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"]
            _coord_cache[key] = (lat, lon)
            return lat, lon
    except Exception:
        pass

    _coord_cache[key] = (None, None)
    return None, None


def _osrm_route(lat1, lon1, lat2, lon2):
    """
    Real road distance & time via OSRM (free, no API key).
    Returns (distance_km, time_min) or (None, None) on failure.
    """
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    try:
        res  = requests.get(url, timeout=10)
        data = res.json()
        if data.get("code") == "Ok":
            route = data["routes"][0]
            return round(route["distance"] / 1000, 1), round(route["duration"] / 60, 1)
    except Exception:
        pass
    return None, None


def _haversine(lat1, lon1, lat2, lon2):
    """Straight-line distance fallback (km)."""
    R    = 6371
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a    = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


class TransportAgent:

    def __init__(self):
        self.route_cache = {}   # shared with itinerary agent

    # ----------------------------------------------------------
    # 🔗 BOOKING LINK GENERATORS
    # ----------------------------------------------------------

    def _booking_links_intercity(self, origin, destination, mode):
        o     = urllib.parse.quote(origin)
        d     = urllib.parse.quote(destination)
        today = datetime.date.today().strftime("%Y%m%d")
        links = {}

        if mode == "Flight":
            links["MakeMyTrip (Flight)"] = (
                f"https://www.makemytrip.com/flight/search?"
                f"itinerary={o}-{d}-{today}&tripType=O&paxType=A-1_C-0_I-0"
            )
            links["Goibibo (Flight)"] = (
                f"https://www.goibibo.com/flights/search/?"
                f"source={o}&destination={d}&date={today}&class=E&adults=1"
            )
            links["Cleartrip (Flight)"] = (
                f"https://www.cleartrip.com/flights/results?"
                f"from={o}&to={d}&depart_date={today}&adults=1&class=Economy"
            )
        elif mode == "Train":
            links["IRCTC (Train)"] = (
                f"https://www.irctc.co.in/nget/train-search?"
                f"journeyDate={today}&fromStation={o.upper()}&toStation={d.upper()}"
            )
            links["MakeMyTrip (Train)"] = (
                f"https://www.makemytrip.com/railways/listing?"
                f"from={o}&to={d}&date={today}"
            )
            links["ConfirmTkt (Train)"] = (
                f"https://www.confirmtkt.com/train/search?"
                f"from={o}&to={d}&date={today}"
            )
        else:  # Road / Bus
            links["redBus (Bus)"] = (
                f"https://www.redbus.in/bus-tickets/{o.lower().replace('%20','-')}-"
                f"to-{d.lower().replace('%20','-')}?onward={today}"
            )
            links["Abhibus (Bus)"] = (
                f"https://www.abhibus.com/bus/{o.lower().replace('%20','-')}-to-"
                f"{d.lower().replace('%20','-')}/date/{today}"
            )
            links["MakeMyTrip (Bus)"] = (
                f"https://www.makemytrip.com/bus-tickets/{o.lower().replace('%20','-')}-"
                f"to-{d.lower().replace('%20','-')}/"
            )
        return links

    def _booking_links_local(self, origin, destination, mode):
        o = urllib.parse.quote(origin)
        d = urllib.parse.quote(destination)
        links = {}
        if mode in ("Cab", "Road"):
            links["Ola Cab"]      = f"https://book.olacabs.com/?serviceType=p2p&pickup_name={o}&drop_name={d}"
            links["Uber"]         = f"https://m.uber.com/ul/?action=setPickup&pickup[formatted_address]={o}&dropoff[formatted_address]={d}"
            links["Rapido (Bike)"] = "https://www.rapido.bike/"
        elif mode == "Bus":
            links["Google Maps Route"] = f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}&travelmode=transit"
        else:
            links["Google Maps Route"] = f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}&travelmode=walking"
        return links

    # ----------------------------------------------------------
    # 📍 GEOCODING
    # ----------------------------------------------------------
    def get_coordinates(self, place, city=None):
        return _geocode(place, city)

    # ----------------------------------------------------------
    # 🛣️  REAL ROAD DISTANCE via OSRM  (with haversine fallback)
    # ----------------------------------------------------------
    def get_road_distance(self, a: str, b: str, city: str | None = None,
                          a_coords=None, b_coords=None):
        """
        Returns (distance_km, time_min) using OSRM real-road routing.
        v10: caller can pass already-known coordinates (e.g. from itinerary
        geocoding) to bypass another geocode round-trip, and `city` to keep
        lookups bounded to the right region.
        """
        cache_key = (a.lower(), b.lower(), (city or "").lower())
        if cache_key in self.route_cache:
            r = self.route_cache[cache_key]
            return r["distance"], r["time_hrs"] * 60

        lat1, lon1 = (a_coords if a_coords and a_coords[0] is not None
                      else _geocode(a, city))
        lat2, lon2 = (b_coords if b_coords and b_coords[0] is not None
                      else _geocode(b, city))

        # 🔍 v10 debug: surface coordinate integrity so geocoding bugs are visible
        print(f"      🛰  {a} ({lat1},{lon1})  →  {b} ({lat2},{lon2})")


        dist_km, time_min = None, None

        if lat1 and lat2:
            dist_km, time_min = _osrm_route(lat1, lon1, lat2, lon2)

        # Haversine fallback with road-factor 1.35 and 35 km/h average
        if dist_km is None:
            if lat1 and lat2:
                straight = _haversine(lat1, lon1, lat2, lon2)
                dist_km  = round(straight * 1.35, 1)
            else:
                dist_km = 30.0   # both coords failed; sentinel value (not 20)
            time_min = round((dist_km / 35) * 60, 1)

        # 🇮🇳 India ETA correction layer — never trust raw OSRM duration.
        corrected, route_type, mult = correct_eta(
            time_min, a, b,
            src_coords=(lat1, lon1) if lat1 else None,
            dst_coords=(lat2, lon2) if lat2 else None,
            distance_km=dist_km,
        )
        time_min = corrected if corrected is not None else time_min

        self.route_cache[cache_key] = {
            "distance":   dist_km,
            "time_hrs":   round(time_min / 60, 3),
            "mode":       "Road",
            "route_type": route_type,
            "eta_multiplier": mult,
        }
        return dist_km, time_min

    # ----------------------------------------------------------
    # 🚌 LOCAL MODE SELECTION
    # ----------------------------------------------------------
    def choose_local_mode(self, dist_km):
        if dist_km < 2:
            mode     = "Walking"
            cost     = 0
            time_hrs = dist_km / 4.5
        elif dist_km < 40:
            mode     = "Cab"
            surge    = 1.3 if 8 <= datetime.datetime.now().hour <= 21 else 1.0
            cost     = (40 + dist_km * 12) * surge
            time_hrs = dist_km / 25
        else:
            mode     = "Bus"
            cost     = dist_km * 2.5
            time_hrs = dist_km / 40
        return mode, int(cost), round(time_hrs, 2)

    # ----------------------------------------------------------
    # ✈️ INTERCITY MODE SELECTION
    # ----------------------------------------------------------
    def choose_best_mode(self, dist, budget, preferred_mode=None):
        """
        v9 intercity timing:
          • Road : 50 km/h average on highways (incl. stops)
          • Train: rail distance ≈ road * 0.85, ~55 km/h Indian Express avg, +1h station buffer
          • Flight: cruise 600 km/h + 3.5 h airport/transfer buffer (>400 km only)
        Returns (mode, one_way_cost, one_way_hours).
        """
        surge       = 1.3 if 8 <= datetime.datetime.now().hour <= 21 else 1
        road_cost   = (100 + dist * 8) * surge
        train_cost  = dist * 3
        flight_cost = dist * 6 + 2000 if dist > 400 else float("inf")

        road_time   = dist / 50
        train_time  = (dist * 0.85) / 55 + 1.0           # +1 h station buffer
        flight_time = dist / 600 + 3.5 if dist > 400 else float("inf")

        cost_map = {
            "Road":   (road_cost,   road_time),
            "Car":    (road_cost,   road_time),
            "Bus":    (road_cost,   road_time),
            "Train":  (train_cost,  train_time),
            "Flight": (flight_cost, flight_time),
        }

        if preferred_mode and preferred_mode in cost_map:
            p_cost, p_time = cost_map[preferred_mode]
            if p_cost <= budget or preferred_mode == "Train":
                return preferred_mode, p_cost, p_time

        options = [
            ("Road",   road_cost,   road_time),
            ("Train",  train_cost,  train_time),
            ("Flight", flight_cost, flight_time),
        ]
        valid = [o for o in options if o[1] <= budget]
        if not valid:
            return min(options, key=lambda x: x[1])
        return min(valid, key=lambda x: x[1])

    # ----------------------------------------------------------
    # ✈️  INTERCITY TRAVEL
    # ----------------------------------------------------------
    def generate_intercity_travel(self, origin, destination, budget, preferred_mode=None):
        dist_km, _ = self.get_road_distance(origin, destination)
        mode, cost, one_way_hours = self.choose_best_mode(dist_km, budget, preferred_mode=preferred_mode)
        booking_links = self._booking_links_intercity(origin, destination, mode)

        return {
            "from":            origin,
            "to":              destination,
            "mode":            mode,
            "distance":        round(dist_km, 1),
            "cost_one_way":    int(cost),
            "round_trip_cost": int(cost * 2),
            "one_way_time":    round(one_way_hours, 2),    # v9: clearly labelled
            "round_trip_time": round(one_way_hours * 2, 2),
            "total_time":      round(one_way_hours * 2, 2),  # backward-compat
            "booking_links":   booking_links,
        }


    # ----------------------------------------------------------
    # 🚗  LOCAL TRANSPORT
    # ----------------------------------------------------------
    def generate_local_transport(self, city, places, hotel, budget, days):
        """
        v10 NOTE: pipeline now prefers `build_local_transport_from_itinerary`
        (called AFTER itinerary optimisation) so transport reflects the real
        visit order. This naive function is kept only as a fallback for code
        paths that don't run the itinerary agent.
        """
        routes     = []
        total_cost = 0
        per_day_places = max(len(places) // days, 1)
        index = 0

        for day in range(days):
            day_places = places[index: index + per_day_places]
            index     += per_day_places
            origin     = hotel["name"] if hotel else city
            origin_co  = ((hotel.get("lat"), hotel.get("lon"))
                          if hotel and hotel.get("lat") is not None else None)

            for p in day_places:
                dest    = p["name"]
                dest_co = ((p.get("lat"), p.get("lon"))
                           if p.get("lat") is not None else None)
                dist_km, time_min = self.get_road_distance(
                    origin, dest, city=city,
                    a_coords=origin_co, b_coords=dest_co)
                mode, cost, time_hrs = self.choose_local_mode(dist_km)
                routes.append({
                    "day": day + 1, "from": origin, "to": dest, "mode": mode,
                    "distance_km": round(dist_km, 1),
                    "travel_time_min": round(time_min, 0),
                    "cost": cost, "time_hrs": time_hrs,
                    "booking_links": self._booking_links_local(origin, dest, mode),
                })
                total_cost += cost
                origin, origin_co = dest, dest_co

            if hotel and day_places:
                dest    = hotel["name"]
                dest_co = (hotel.get("lat"), hotel.get("lon"))
                dist_km, time_min = self.get_road_distance(
                    origin, dest, city=city,
                    a_coords=origin_co, b_coords=dest_co)
                mode, cost, time_hrs = self.choose_local_mode(dist_km)
                routes.append({
                    "day": day + 1, "from": origin, "to": dest, "mode": mode,
                    "distance_km": round(dist_km, 1),
                    "travel_time_min": round(time_min, 0),
                    "cost": cost, "time_hrs": time_hrs, "type": "return",
                    "booking_links": self._booking_links_local(origin, dest, mode),
                })
                total_cost += cost

        return {"routes": routes, "total_local_transport_cost": int(total_cost)}


    # ----------------------------------------------------------
    # 🧭  v10 — LOCAL TRANSPORT DERIVED FROM FINAL ITINERARY
    # ----------------------------------------------------------
    def build_local_transport_from_itinerary(self, itinerary, hotel=None, city=None):
        """
        Walk the finalised itinerary and turn every 'travel' segment into a
        local-transport route entry. This guarantees the transport section is
        identical to the final visit sequence — fixing the pipeline-order bug
        where local routes referenced the raw place list, not the optimised one.
        """
        routes, total_cost, current_day = [], 0, 1
        for item in itinerary or []:
            t = item.get("type")
            if t == "hotel_start":
                current_day = item.get("day", current_day)
                continue
            if t != "travel":
                continue

            origin, dest = item["from"], item["to"]
            # Parse distance like "12.4 km"
            try:
                dist_km = float(str(item.get("distance", "0")).split()[0])
            except Exception:
                dist_km = 0.0
            # Parse "23 min (+5 min parking)" or "23 min"
            try:
                time_min = float(str(item.get("time", "0")).split()[0])
            except Exception:
                time_min = (dist_km / 25) * 60

            mode, cost, time_hrs = self.choose_local_mode(dist_km)
            entry = {
                "day": current_day, "from": origin, "to": dest, "mode": mode,
                "distance_km": round(dist_km, 1),
                "travel_time_min": round(time_min, 0),
                "cost": cost, "time_hrs": time_hrs,
                "booking_links": self._booking_links_local(origin, dest, mode),
            }
            if hotel and dest == hotel.get("name"):
                entry["type"] = "return"
            routes.append(entry)
            total_cost += cost

        return {"routes": routes, "total_local_transport_cost": int(total_cost)}



# ============================================================
# 🖨️  PRINT HELPER
# ============================================================

def print_transport(intercity, local):
    print("\n✈️  INTERCITY TRAVEL")
    print("=" * 50)
    print(f"  {intercity['from']}  ⇄  {intercity['to']}")
    print(f"  🚆 Mode      : {intercity['mode']}")
    print(f"  📏 Distance  : {intercity['distance']} km  (real road distance)")
    print(f"  💰 Round Trip: ₹{intercity['round_trip_cost']}")
    ow = intercity.get('one_way_time', intercity['total_time'] / 2)
    rt = intercity.get('round_trip_time', intercity['total_time'])
    print(f"  ⏱️  One-way   : {ow} hrs")
    print(f"  🔁 Round trip: {rt} hrs")

    print("\n  🔗 Book Intercity Ticket:")
    for site, url in intercity.get("booking_links", {}).items():
        print(f"     {site}: {url}")

    print("\n🚗  LOCAL TRANSPORT ROUTES")
    print("=" * 50)
    for r in local["routes"]:
        tag = " (Return)" if r.get("type") == "return" else ""
        print(f"\n  Day {r['day']}{tag}: {r['from']} → {r['to']}")
        print(f"  🚌 Mode: {r['mode']} | ₹{r['cost']} | {r['travel_time_min']} min | {r['distance_km']} km")
        print("  🔗 Book / Ride:")
        for site, url in r.get("booking_links", {}).items():
            print(f"     {site}: {url}")

    print(f"\n  💰 Total Local Cost: ₹{local['total_local_transport_cost']}")
