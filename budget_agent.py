"""
💰 BUDGET AGENT
===============
FIX #5: All costs now properly scale with num_people AND rooms.
FIX #4: Improved conflict resolution with 3 fallback strategies.
"""


# =========================================================
# 📊 FOOD & ENTRY FEE ESTIMATES  (per person per day, INR)
# =========================================================

FOOD_ESTIMATES = {
    "budget":   400,
    "standard": 700,
    "luxury":   1500,
}

ENTRY_FEE_ESTIMATES = {
    "temple":    50,
    "beach":     0,
    "fort":      100,
    "museum":    150,
    "adventure": 500,
    "mosque":    0,
    "general":   80,
}


# =========================================================
# 💡 BUDGET AGENT CLASS
# =========================================================

class BudgetAgent:

    def __init__(self):
        self.breakdown   = {}
        self.status      = "ok"
        self.adjustments = []

    # --------------------------------------------------
    # 🧮 MAIN: VALIDATE & BREAKDOWN
    # --------------------------------------------------
    def validate(
        self,
        total_budget: float,
        intercity_cost: float,
        hotel_price_per_night: float,
        local_transport_cost: float,
        days: int,
        rooms: int = 1,
        interest: str = "general",
        hotel_type: str = "standard",
        num_people: int = 1,
    ) -> dict:

        # ✅ FIX #5: food and entry fees correctly scaled per person
        food_per_day  = FOOD_ESTIMATES.get(hotel_type, 700) * num_people
        entry_per_day = ENTRY_FEE_ESTIMATES.get(interest.lower(), 80) * num_people
        misc_per_day  = 200 * num_people

        # ✅ FIX #5: hotel cost depends on rooms (not just 1 room)
        hotel_total = hotel_price_per_night * days * rooms
        food_total  = food_per_day * days
        entry_total = entry_per_day * days
        misc_total  = misc_per_day * days

        # ✅ FIX #5: intercity cost should scale per person for non-flight modes
        # (passed in already scaled from transport agent, so we use as-is)
        total_used = (
            intercity_cost
            + hotel_total
            + local_transport_cost
            + food_total
            + entry_total
            + misc_total
        )

        remaining = total_budget - total_used
        pct_used  = (total_used / total_budget * 100) if total_budget > 0 else 0

        if pct_used > 100:
            self.status = "exceeded"
        elif pct_used > 90:
            self.status = "warning"
        else:
            self.status = "ok"

        self.breakdown = {
            "intercity_transport": int(intercity_cost),
            "hotel":               int(hotel_total),
            "local_transport":     int(local_transport_cost),
            "food":                int(food_total),
            "entry_fees":          int(entry_total),
            "miscellaneous":       int(misc_total),
            "total_used":          int(total_used),
            "total_budget":        int(total_budget),
            "remaining":           int(remaining),
            "percent_used":        round(pct_used, 1),
            "status":              self.status,
            "adjustments":         self._suggest_adjustments(
                                       total_budget,
                                       total_used,
                                       intercity_cost,
                                       hotel_total,
                                       hotel_price_per_night,
                                       local_transport_cost,
                                       days,
                                       rooms,
                                       num_people,
                                   ),
        }

        return self.breakdown

    # --------------------------------------------------
    # 🔧 ADJUSTMENT SUGGESTIONS
    # --------------------------------------------------
    def _suggest_adjustments(
        self,
        budget,
        used,
        intercity,
        hotel_total,
        hotel_per_night,
        local,
        days,
        rooms,
        num_people,
    ) -> list:

        suggestions = []

        if used <= budget:
            return suggestions

        # 1. Cheaper hotel
        suggestions.append({
            "type":    "hotel",
            "action":  "downgrade_hotel",
            "message": "Switch to a cheaper hotel tier (saves ~30%/night)",
            "savings": int(hotel_per_night * 0.30 * days * rooms),
        })

        # 2. Transport mode downgrade
        if intercity > budget * 0.25:
            suggestions.append({
                "type":    "transport",
                "action":  "use_train",
                "message": "Switch intercity travel to Train (40-60% cheaper than flights)",
                "savings": int(intercity * 0.50),
            })

        # ✅ FIX #4: Added reduce_places as option 3
        suggestions.append({
            "type":    "places",
            "action":  "remove_low_priority_places",
            "message": "Remove 1-2 lowest-rated attractions to cut local transport cost",
            "savings": int(local * 0.20),
        })

        # 4. Reduce days
        if days > 2:
            suggestions.append({
                "type":    "days",
                "action":  "reduce_days",
                "message": f"Reduce trip by 1 day (saves hotel + food + local costs)",
                "savings": int(hotel_per_night * rooms + local / days + 700 * num_people),
            })

        # 5. Reduce rooms
        if rooms > 1:
            suggestions.append({
                "type":    "rooms",
                "action":  "reduce_rooms",
                "message": "Reduce rooms by 1",
                "savings": int(hotel_per_night * days),
            })

        return suggestions

    # --------------------------------------------------
    # 🖨️ DISPLAY
    # --------------------------------------------------
    def print_breakdown(self, breakdown: dict):

        print("\n" + "=" * 55)
        print("💰 BUDGET BREAKDOWN (Budget Agent)")
        print("=" * 55)

        items = [
            ("✈️  Intercity Transport", "intercity_transport"),
            ("🏨 Hotel",                "hotel"),
            ("🚗 Local Transport",      "local_transport"),
            ("🍽️  Food",                "food"),
            ("🎟️  Entry Fees",          "entry_fees"),
            ("🎒 Miscellaneous",        "miscellaneous"),
        ]

        for label, key in items:
            print(f"  {label:<22} : ₹{breakdown[key]:>8,}")

        print("-" * 55)
        print(f"  {'💸 Total Used':<22} : ₹{breakdown['total_used']:>8,}")
        print(f"  {'💳 Total Budget':<22} : ₹{breakdown['total_budget']:>8,}")
        print(f"  {'💵 Remaining':<22} : ₹{breakdown['remaining']:>8,}")
        print(f"  {'📊 % Used':<22} : {breakdown['percent_used']}%")

        status_icons = {
            "ok":       "🟢 Within Budget",
            "warning":  "🟡 Near Budget Limit (>90%)",
            "exceeded": "🔴 Budget Exceeded!",
        }

        print(f"\n  Status: {status_icons.get(breakdown['status'], '')}")

        if breakdown.get("adjustments"):
            print("\n⚙️  Auto-Adjustment Suggestions:")
            for adj in breakdown["adjustments"]:
                print(f"  • {adj['message']}  (saves ≈ ₹{adj['savings']:,})")

        print("=" * 55)
