"""
🧠 AGENT COORDINATOR  v8 (ALL PROBLEMS FIXED)
==============================
NEW IN v8:
✅ FIX-C-FLOW:  Itinerary-first workflow: attractions geocoded BEFORE hotel
               search so hotel agent receives lat/lon for centrality scoring
✅ FIX-C-HOTEL: Hotel agent receives days, num_people, check_in_date for
               seasonal pricing and total cost optimisation
✅ FIX-C-DIV:   Hotel categories (Best Value / Location / Cheapest / Luxury)
               surfaced in final output
✅ FIX-C-SCORE: Trip score now penalises poor hotel centrality

Preserved from v7:
✅ shared_state["routes"] — Transport Agent stores route_cache
✅ Proper budget conflict resolution (4 strategies)
✅ num_people passed correctly everywhere
✅ Forecast filtered to trip dates
✅ Hotel scoring includes proximity to attractions
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# =========================================================
# 📦 AGENT STATE
# =========================================================

@dataclass
class AgentState:
    # ── User inputs
    origin:             str   = ""
    destination:        str   = ""
    interest:           str   = ""
    start_date:         str   = ""
    end_date:           str   = ""
    days:               int   = 1
    total_budget:       float = 0.0
    rooms:              int   = 1
    num_people:         int   = 1
    preferred_mode:     str   = "Train"
    preferred_hotel:    str   = "standard"
    lang:               str   = "en"
    user_preference:    str   = ""

    # ── Agent outputs
    weather_data:       Optional[Dict]  = None
    aqi:                Optional[int]   = None
    forecast:           Optional[List]  = None
    forecast_approximate: bool          = False
    weather_risk:       Optional[str]   = None

    places:             Optional[List]  = None
    selected_places:    Optional[List]  = None

    hotels:             Optional[List]  = None
    best_hotel:         Optional[Dict]  = None
    hotel_categories:   Optional[Dict]  = None   # ✅ FIX-C-DIV

    intercity:          Optional[Dict]  = None
    local_transport:    Optional[Dict]  = None
    route_cache:        Dict            = field(default_factory=dict)

    itinerary:          Optional[List]  = None
    budget_breakdown:   Optional[Dict]  = None

    trip_score:         int             = 0
    budget_savings_tips: List[str]      = field(default_factory=list)
    packing_list:       List[str]       = field(default_factory=list)

    # ── Flags
    weather_checked:    bool = False
    places_found:       bool = False
    hotel_found:        bool = False
    transport_planned:  bool = False
    itinerary_generated:bool = False
    budget_validated:   bool = False


# =========================================================
# 🔗 COORDINATOR CLASS
# =========================================================

class AgentCoordinator:

    MAX_BUDGET_RETRIES = 3

    def __init__(self, state: AgentState, translator=None):
        self.state      = state
        self.translator = translator

    # --------------------------------------------------
    # 🚀 FULL RUN
    # ✅ FIX-C-FLOW: geocode attractions BEFORE hotel search
    # so hotel agent gets lat/lon for centrality scoring
    # --------------------------------------------------
    def run_all(self):
        self._run_weather()
        self._run_location()
        self._geocode_places()
        self._run_hotel()
        # v10 pipeline order:
        #   intercity transport → itinerary optimisation →
        #   local transport derived from the FINAL visit sequence → budget
        self._run_intercity_only()
        self._run_itinerary()
        self._run_local_transport_from_itinerary()
        self._run_budget(auto_adjust=True)
        self._run_score()
        self._run_packing()
        self.state.budget_savings_tips = self._suggest_budget_reallocation()

    # --------------------------------------------------
    # ♻️ PARTIAL RE-RUN
    # --------------------------------------------------
    def rerun(self, changed: List[str]):
        """Re-run only the affected dependency chain, but preserve the v10
        pipeline order so local transport always matches the final itinerary."""
        need_weather   = any(c in changed for c in ["weather", "days", "dates"])
        need_places    = any(c in changed for c in ["places", "days", "interest"])
        need_hotel     = need_places or any(c in changed for c in ["hotel", "days", "budget", "hotel_type"])
        need_intercity = any(c in changed for c in ["transport", "days", "budget"])

        if need_weather:
            self._run_weather()
        if need_places:
            self._run_location()
            self._geocode_places()
        if need_hotel:
            self._run_hotel()
        if need_intercity:
            self._run_intercity_only()

        # Itinerary depends on places/hotel/days; local transport must be built
        # after the final visit sequence, then budget uses those real routes.
        self._run_itinerary()
        self._run_local_transport_from_itinerary()
        self._run_budget(auto_adjust=True)
        self._run_score()
        self._run_packing()
        self.state.budget_savings_tips = self._suggest_budget_reallocation()

    # --------------------------------------------------
    # 🌦️  WEATHER AGENT
    # --------------------------------------------------
    def _run_weather(self):
        from weather import (
            get_location, get_weather, get_aqi,
            get_forecast, risk_level,
        )

        print("\n🌦️  [Weather Agent] Checking conditions...")

        loc = get_location(self.state.destination)
        if not loc:
            print("⚠️  Weather data unavailable — proceeding without it.")
            self.state.weather_risk    = "🟢 Low"
            self.state.weather_checked = True
            return

        lat, lon = loc["lat"], loc["lon"]
        weather  = get_weather(lat, lon)
        aqi      = get_aqi(lat, lon)

        forecast, is_approx = get_forecast(
            lat, lon,
            start_date=self.state.start_date,
            end_date=self.state.end_date,
        )

        self.state.weather_data          = weather
        self.state.aqi                   = aqi
        self.state.forecast              = forecast
        self.state.forecast_approximate  = is_approx
        self.state.weather_risk          = risk_level(
            weather["condition"], weather["temp"],
            weather["feels_like"], aqi,
        )
        self.state.weather_checked = True

        if is_approx:
            print("   ⚠️  Trip is beyond 5-day forecast window. Showing nearest available forecast.")
        print(f"   ✅ Risk Level: {self.state.weather_risk}")

    # --------------------------------------------------
    # 📍  LOCATION AGENT
    # --------------------------------------------------
    def _run_location(self):
        from location import get_places

        print("\n📍  [Location Agent] Finding attractions...")

        user_pref = getattr(self.state, "user_preference", None)
        places = get_places(self.state.destination, self.state.interest,
                            user_preference=user_pref)

        if not places:
            print("⚠️  No places found for given interest.")
            self.state.places_found = False
            return

        places = sorted(places, key=lambda x: x.get("_score", x.get("rating", 0)), reverse=True)
        self.state.places          = places
        self.state.selected_places = places[: self.state.days * 3]
        self.state.places_found    = True

        print(f"   ✅ Found {len(places)} places, selected {len(self.state.selected_places)}")

    # --------------------------------------------------
    # ✅ FIX-C-FLOW: PRE-GEOCODE ATTRACTIONS
    # Must run after _run_location, before _run_hotel
    # so hotel scoring gets real lat/lon not None
    # --------------------------------------------------
    def _geocode_places(self):
        from itinerary import attach_coordinates

        if not self.state.selected_places:
            return

        print("\n📍  [Geocoder] Pre-attaching coordinates to attractions...")
        self.state.selected_places = attach_coordinates(
            self.state.selected_places, self.state.destination
        )
        geocoded = sum(1 for p in self.state.selected_places if p.get("lat") is not None)
        print(f"   ✅ Geocoded {geocoded}/{len(self.state.selected_places)} attractions")

    # --------------------------------------------------
    # 🏨  HOTEL AGENT  (v8: full geo + seasonal + total cost)
    # --------------------------------------------------
    def _run_hotel(self, budget_override: Optional[float] = None):
        from hotel import generate_hotels, categorise_hotels

        print("\n🏨  [Hotel Agent] Searching accommodation...")

        hotel_budget = budget_override or (self.state.total_budget * 0.50)
        per_night    = hotel_budget / max(self.state.days, 1)

        modifiers = {"budget": 0.7, "standard": 1.0, "luxury": 1.5}
        per_night *= modifiers.get(self.state.preferred_hotel, 1.0)

        min_price_floor = {"budget": 0, "standard": 1200, "luxury": 5000}
        min_price = min_price_floor.get(self.state.preferred_hotel, 0)

        hotels = generate_hotels(
            self.state.destination,
            per_night,
            self.state.rooms,
            places=self.state.selected_places or [],
            days=self.state.days,
            num_people=self.state.num_people,
            check_in_date=self.state.start_date,    # ✅ FIX-H-SEA
        )

        if not hotels:
            print("⚠️  No hotels found within budget.")
            self.state.hotel_found = False
            return

        filtered = [h for h in hotels if h["price"] >= min_price]
        if not filtered:
            print(f"⚠️  No {self.state.preferred_hotel} hotels found. Showing best available.")
            filtered = hotels

        hotels = filtered

        # ✅ FIX-H-DIV: Build category map for output
        self.state.hotel_categories = categorise_hotels(hotels)
        self.state.hotels     = hotels
        self.state.best_hotel = hotels[0]
        self.state.hotel_found = True

        best = self.state.best_hotel
        avg_d = best.get("_avg_dist_km")
        dist_str = f" | 📏 {avg_d:.1f} km avg to attractions" if avg_d is not None else ""
        print(f"   ✅ Selected: {best['name']} @ ₹{best['price']:,}/night  "
              f"(area: {best.get('area', 'N/A')}){dist_str}")

    # --------------------------------------------------
    # 🚗  TRANSPORT AGENT
    # --------------------------------------------------
    def _run_transport(self, mode_override: Optional[str] = None):
        """Legacy combined intercity+local. Kept for `rerun()` callers."""
        self._run_intercity_only(mode_override)
        if self.state.itinerary:
            self._run_local_transport_from_itinerary()
        else:
            self._run_local_transport_naive()

    def _run_intercity_only(self, mode_override: Optional[str] = None):
        from transport import TransportAgent
        print("\n🚗  [Transport Agent] Planning intercity route...")
        agent = TransportAgent()
        mode  = mode_override or self.state.preferred_mode
        intercity = agent.generate_intercity_travel(
            self.state.origin, self.state.destination,
            self.state.total_budget * 0.30, preferred_mode=mode,
        )
        self.state.intercity         = intercity
        self.state.transport_planned = True
        self._transport_agent        = agent      # keep for local stage
        self.state.route_cache       = agent.route_cache
        print(f"   ✅ Intercity: {mode} ₹{intercity['round_trip_cost']:,}")

    def _run_local_transport_from_itinerary(self):
        """v10: derive local transport from the finalised itinerary so the
        transport section always matches the actual visit sequence."""
        from transport import TransportAgent
        agent = getattr(self, "_transport_agent", None) or TransportAgent()
        print("\n🚗  [Transport Agent] Local routes from final itinerary...")
        local = agent.build_local_transport_from_itinerary(
            self.state.itinerary, hotel=self.state.best_hotel,
            city=self.state.destination)
        self.state.local_transport = local
        self.state.route_cache     = agent.route_cache
        print(f"   ✅ Local: {len(local['routes'])} legs · "
              f"₹{local['total_local_transport_cost']:,}")

    def _run_local_transport_naive(self):
        from transport import TransportAgent
        agent = getattr(self, "_transport_agent", None) or TransportAgent()
        local = agent.generate_local_transport(
            self.state.destination, self.state.selected_places or [],
            self.state.best_hotel, self.state.total_budget * 0.20,
            self.state.days)
        self.state.local_transport = local
        self.state.route_cache     = agent.route_cache

    # --------------------------------------------------
    # 💰  BUDGET AGENT
    # --------------------------------------------------
    def _run_budget(self, auto_adjust: bool = True):
        from budget_agent import BudgetAgent

        print("\n💰  [Budget Agent] Validating costs...")

        agent = BudgetAgent()

        hotel_price    = self.state.best_hotel["price"] if self.state.best_hotel else 0
        intercity_cost = self.state.intercity["round_trip_cost"] if self.state.intercity else 0
        local_cost     = (self.state.local_transport["total_local_transport_cost"]
                          if self.state.local_transport else 0)

        breakdown = agent.validate(
            total_budget          = self.state.total_budget,
            intercity_cost        = intercity_cost,
            hotel_price_per_night = hotel_price,
            local_transport_cost  = local_cost,
            days                  = self.state.days,
            rooms                 = self.state.rooms,
            interest              = self.state.interest,
            hotel_type            = self.state.preferred_hotel,
            num_people            = self.state.num_people,
        )

        self.state.budget_breakdown = breakdown
        self.state.budget_validated = True

        if auto_adjust and breakdown["status"] == "exceeded":
            self._resolve_budget_conflict(breakdown)

        status_map = {"ok": "🟢", "warning": "🟡", "exceeded": "🔴"}
        icon = status_map.get(breakdown["status"], "")
        print(f"   {icon} Status: {breakdown['status'].upper()} — "
              f"Used ₹{breakdown['total_used']:,} / ₹{breakdown['total_budget']:,}")

    # --------------------------------------------------
    # ⚙️  CONFLICT RESOLUTION
    # --------------------------------------------------
    def _resolve_budget_conflict(self, breakdown: dict):
        print("\n⚙️  [Coordinator] Budget conflict — attempting auto-resolution...")

        adjustments = breakdown.get("adjustments", [])

        for adj in adjustments:
            action = adj.get("action")

            if action == "downgrade_hotel":
                print("   → Trying cheaper hotel tier...")
                self._run_hotel(budget_override=self.state.total_budget * 0.35)
                self._run_transport()
                self._run_budget(auto_adjust=False)
                if self.state.budget_breakdown["status"] != "exceeded":
                    print("   ✅ Budget resolved via hotel downgrade")
                    return

            elif action == "use_train":
                print("   → Switching to Train travel...")
                self._run_transport(mode_override="Train")
                self._run_budget(auto_adjust=False)
                if self.state.budget_breakdown["status"] != "exceeded":
                    print("   ✅ Budget resolved via Train mode")
                    return

            elif action == "remove_low_priority_places":
                if self.state.selected_places and len(self.state.selected_places) > 2:
                    print("   → Removing lowest-rated attraction...")
                    self.state.selected_places = sorted(
                        self.state.selected_places,
                        key=lambda x: x.get("rating", 0),
                        reverse=True
                    )[:-1]
                    self._run_transport()
                    self._run_budget(auto_adjust=False)
                    if self.state.budget_breakdown["status"] != "exceeded":
                        print("   ✅ Budget resolved by removing a low-priority place")
                        return

            elif action == "reduce_days":
                if self.state.days > 2:
                    print("   → Reducing trip by 1 day…")
                    self.state.days -= 1
                    all_places = sorted(
                        self.state.places or [],
                        key=lambda x: x.get("_score", x.get("rating", 0)),
                        reverse=True,
                    )
                    self.state.selected_places = all_places[: self.state.days * 3]
                    self._geocode_places()   # ✅ Re-geocode for new selection
                    self._run_hotel()
                    self._run_transport()
                    self._run_budget(auto_adjust=False)
                    if self.state.budget_breakdown["status"] != "exceeded":
                        print("   ✅ Budget resolved by reducing days")
                        return

        print("   ⚠️  Auto-adjustment could not fully resolve budget. "
              "Consider increasing budget or reducing days.")

    # --------------------------------------------------
    # 🗓️  ITINERARY AGENT
    # --------------------------------------------------
    def _run_itinerary(self):
        from itinerary import generate_itinerary

        if not self.state.selected_places:
            return

        print("\n🗓️   [Itinerary Agent] Building day-by-day schedule...")

        weather_constraints = {}
        if self.state.weather_data:
            feels_like = self.state.weather_data.get("feels_like", 0)
            if feels_like >= 35:
                weather_constraints["avoid_afternoon"] = True
            if "rain" in self.state.weather_data.get("condition", "").lower():
                weather_constraints["carry_umbrella"] = True

        plan = generate_itinerary(
            self.state.selected_places,
            self.state.destination,
            self.state.days,
            hotel=self.state.best_hotel,
            shared_routes=self.state.route_cache,
            weather_constraints=weather_constraints,
            weather_data=self.state.weather_data,
            user_interest=self.state.interest,
        )

        self.state.itinerary            = plan
        self.state.itinerary_generated  = True

        print(f"   ✅ Itinerary ready — {self.state.days} day(s)")

    # --------------------------------------------------
    # 💸  BUDGET REALLOCATION
    # --------------------------------------------------
    def _suggest_budget_reallocation(self):
        if not self.state.budget_breakdown:
            return []

        bd    = self.state.budget_breakdown
        saved = bd.get("remaining", 0)
        if saved <= 0:
            return []

        interest  = self.state.interest.lower()
        weather   = self.state.weather_data or {}
        condition = weather.get("condition", "").lower()
        days      = self.state.days
        n_people  = self.state.num_people

        suggestions = []

        if interest in ("beach", "general") and saved >= 1200 * n_people:
            suggestions.append(f"🌊 Water activities / boat tour (~₹{1200 * n_people:,})")
        if interest in ("fort", "adventure", "general") and saved >= 800 * n_people:
            suggestions.append(f"🥾 Guided trek or heritage walk (~₹{800 * n_people:,})")
        if interest in ("temple", "museum", "general") and saved >= 500 * n_people:
            suggestions.append(f"🎭 Cultural show or local performance (~₹{500 * n_people:,})")
        if interest == "adventure" and saved >= 1500 * n_people:
            suggestions.append(f"🪂 Adventure sport experience (~₹{1500 * n_people:,})")
        if ("clear" in condition or "sun" in condition) and saved >= 600 * n_people:
            suggestions.append(f"📸 Sunrise/sunset photography tour (~₹{600 * n_people:,})")
        if "rain" in condition and saved >= 400 * n_people:
            suggestions.append(f"🍲 Indoor food trail / cooking class (~₹{400 * n_people:,})")
        if saved >= 600 * n_people:
            suggestions.append(f"🍽️  Fine dining / local speciality meal (~₹{600 * n_people:,})")
        if days >= 2 and saved >= 300 * n_people:
            suggestions.append(f"☕ Local street food & market exploration (~₹{300 * n_people:,})")
        if saved >= 500:
            suggestions.append(f"🎁 Local handicrafts / souvenirs (~₹500)")

        return suggestions[:5]

    # --------------------------------------------------
    # 📊  TRIP SCORE  (v8: centrality penalty added)
    # --------------------------------------------------
    def _run_score(self):
        bd       = self.state.budget_breakdown or {}
        used     = bd.get("total_used", 0)
        total    = bd.get("total_budget", self.state.total_budget)
        risk     = self.state.weather_risk or ""
        places   = self.state.selected_places or []
        n_places = len(places)

        score = 85

        # Budget fitness
        if total > 0:
            ratio = used / total
            if ratio > 1.0:
                score -= 15
            elif ratio > 0.95:
                score -= 8
            elif ratio > 0.90:
                score -= 4
            elif 0.60 <= ratio <= 0.90:
                score += 5
            elif ratio < 0.40:
                score -= 3

        # Weather risk
        if "Extreme" in risk or "Hazardous" in risk:
            score -= 15
        elif "High" in risk:
            score -= 8
        elif "Moderate" in risk:
            score -= 4

        # Attraction density
        pday = n_places / max(self.state.days, 1)
        if pday < 2:
            score -= 8
        elif 2 <= pday <= 4:
            score += 5
        elif pday > 5:
            score -= 3

        # Afternoon heat conflict
        weather    = self.state.weather_data or {}
        feels_like = weather.get("feels_like", 0)
        if feels_like >= 35 and self.state.itinerary:
            afternoon_visits = [
                item for item in self.state.itinerary
                if item.get("type") == "visit"
                and "12:00" <= item.get("start", "00:00") < "15:00"
                and item.get("end", "00:00") <= "15:00"
            ]
            if afternoon_visits:
                score -= 5

        # ✅ FIX-C-SCORE: Hotel centrality penalty
        if self.state.best_hotel:
            avg_dist = self.state.best_hotel.get("_avg_dist_km")
            if avg_dist is not None:
                if avg_dist > 25:
                    score -= 8    # hotel far from attractions — significant penalty
                elif avg_dist > 15:
                    score -= 4

        # Data quality
        if places:
            template_phrase = "highly recommended for tourists due to its cultural"
            generic_count = sum(
                1 for p in places
                if template_phrase in p.get("detailed_description", "").lower()
            )
            generic_ratio = generic_count / n_places
            if generic_ratio > 0.5:
                score -= 5
            elif generic_ratio > 0.25:
                score -= 2

        self.state.trip_score = max(0, min(score, 100))

    # --------------------------------------------------
    # 🧳  PACKING LIST
    # --------------------------------------------------
    def _run_packing(self):
        items     = ["👕 Comfortable clothes", "👟 Walking shoes",
                     "🪪 ID proof", "💊 Basic medicines"]
        condition = ""
        aqi       = self.state.aqi or 0

        if self.state.weather_data:
            condition = self.state.weather_data.get("condition", "").lower()

        if "rain" in condition:
            items += ["☂️ Umbrella", "🥾 Waterproof shoes"]
        if "clear" in condition or "sun" in condition:
            items += ["🕶 Sunglasses", "🧴 Sunscreen"]
        if aqi >= 3:
            items += ["😷 N95 Mask"]
        if self.state.days >= 3:
            items += ["🔋 Power Bank", "🧳 Extra clothes"]

        interest = self.state.interest.lower()
        if "beach" in interest:
            items += ["🏖 Beach towel", "🩱 Swimwear"]
        if "fort" in interest or "adventure" in interest:
            items += ["🥾 Trekking shoes", "🎒 Daypack"]
        if "temple" in interest:
            items += ["👘 Modest clothing", "👣 Easy-to-remove footwear"]

        self.state.packing_list = items
