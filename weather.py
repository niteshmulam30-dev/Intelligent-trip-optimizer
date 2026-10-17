import requests
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# 🔑 PUT YOUR API KEY HERE
API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")


# 🗺️ KNOWN INDIAN CITIES — country + state hints to prevent wrong-country matches
INDIA_CITY_HINTS = {
    "goa":       {"country": "IN", "state": "Goa"},
    "mumbai":    {"country": "IN", "state": "Maharashtra"},
    "delhi":     {"country": "IN"},
    "bangalore": {"country": "IN"},
    "bengaluru": {"country": "IN"},
    "hyderabad": {"country": "IN"},
    "chennai":   {"country": "IN"},
    "kolkata":   {"country": "IN"},
    "pune":      {"country": "IN"},
    "jaipur":    {"country": "IN"},
    "agra":      {"country": "IN"},
    "varanasi":  {"country": "IN"},
    "kerala":    {"country": "IN"},
    "kochi":     {"country": "IN"},
    "mysore":    {"country": "IN"},
    "udaipur":   {"country": "IN"},
    "manali":    {"country": "IN"},
    "shimla":    {"country": "IN"},
    "darjeeling":{"country": "IN"},
    "ooty":      {"country": "IN"},
}


# 📍 LOCATION
def get_location(city):
    """
    FIX: Disambiguate Indian city names to prevent wrong-country selection.
    E.g. 'Goa' must resolve to Goa, India — not Goa, Philippines.
    Strategy: first try '<city>,IN' for known Indian cities; fall back to generic.
    """
    city_lower = city.strip().lower()
    hint = INDIA_CITY_HINTS.get(city_lower, {})

    # Build queries: country-qualified first, then generic fallback
    queries = []
    if hint.get("country") == "IN":
        state = hint.get("state", "")
        if state:
            queries.append(f"{city},{state},IN")
        queries.append(f"{city},IN")
    queries.append(city)   # always include unqualified as last resort

    for q in queries:
        url = f"https://api.openweathermap.org/geo/1.0/direct?q={q}&limit=5&appid={API_KEY}"
        try:
            res = requests.get(url, timeout=8).json()
        except Exception:
            continue

        if not res:
            continue

        # Filter to India-only results when hint says so
        if hint.get("country") == "IN":
            india_results = [r for r in res if r.get("country") == "IN"]
            if india_results:
                loc = india_results[0]
                if len(res) > 1:
                    print(f"⚠️  Multiple geo matches — locked to India: "
                          f"{loc['name']}, {loc.get('state','')}, {loc['country']}")
                return loc

        # No country filter needed
        loc = res[0]
        if len(res) > 1:
            print(f"⚠️  Multiple matches found. Using: "
                  f"{loc['name']}, {loc.get('state','')}, {loc['country']}")
        return loc

    return None


# 🌦️ WEATHER
def get_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    data = requests.get(url, timeout=8).json()

    return {
        "condition": data["weather"][0]["description"],
        "temp": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"]
    }


# 🌫️ AQI
def get_aqi(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    data = requests.get(url, timeout=8).json()
    return data["list"][0]["main"]["aqi"]


# ✅ FIX #7: FORECAST FILTERED TO TRIP DATES
def get_forecast(lat, lon, start_date=None, end_date=None):
    """
    Returns forecast filtered to trip dates.
    If trip is beyond 5-day window, returns best-available data with a note.
    start_date / end_date: strings in 'YYYY-MM-DD' format
    """
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    data = requests.get(url, timeout=8).json()

    forecast = []
    seen = set()

    for item in data["list"]:
        date = item["dt_txt"].split(" ")[0]
        if date not in seen:
            forecast.append((date, item["main"]["temp"], item["weather"][0]["main"]))
            seen.add(date)

    # Filter to trip date range if provided
    if start_date and end_date:
        try:
            trip_start = datetime.strptime(start_date, "%Y-%m-%d")
            trip_end   = datetime.strptime(end_date,   "%Y-%m-%d")
            filtered = [
                (d, t, c) for d, t, c in forecast
                if trip_start <= datetime.strptime(d, "%Y-%m-%d") <= trip_end
            ]
            if filtered:
                return filtered, False   # (data, is_approximate)
            else:
                # Trip is beyond the 5-day window — return all available with flag
                return forecast[:5], True
        except ValueError:
            pass

    return forecast[:5], False


# 🧠 AQI INTERPRETATION
def interpret_aqi(aqi):
    return {
        1: "🟢 Good",
        2: "🟡 Fair",
        3: "🟠 Moderate",
        4: "🔴 Poor",
        5: "⚫ Hazardous"
    }.get(aqi, "Unknown")


# 🚦 RISK LEVEL
def risk_level(condition, temp, feels_like, aqi):
    condition = condition.lower()

    if aqi == 5:
        return "🔴 Extreme (Hazardous Air)"
    elif aqi >= 4:
        return "🔴 High (Air Quality)"
    elif feels_like >= 35:
        return "🟡 Moderate (Heat Stress)"
    elif aqi == 3 or "haze" in condition:
        return "🟡 Moderate (Air Quality)"
    elif "rain" in condition:
        return "🟡 Moderate (Rain)"
    return "🟢 Low"


# 🚗 TRAVEL IMPACT
def travel_impact(condition, temp, feels_like, aqi):
    condition = condition.lower()

    if aqi >= 4:
        return {
            "Road": "⚠️ Avoid long exposure (poor air)",
            "Train": "⚠️ Moderate exposure risk",
            "Flight": "✅ Best option"
        }

    if aqi == 3 or "haze" in condition:
        return {
            "Road": "⚠️ Heat discomfort + reduced visibility",
            "Train": "✅ Comfortable",
            "Flight": "⚠️ Possible minor delays"
        }

    if feels_like >= 35:
        return {
            "Road": "⚠️ High heat discomfort, avoid long drives",
            "Train": "✅ Better option",
            "Flight": "✅ Fast and efficient"
        }

    if "rain" in condition:
        return {
            "Road": "⚠️ Wet roads",
            "Train": "⚠️ Minor delays",
            "Flight": "✅ Mostly unaffected"
        }

    return {
        "Road": "✅ Smooth travel",
        "Train": "✅ On time",
        "Flight": "✅ No issues"
    }


# 📈 TREND
def forecast_trend(forecast):
    temps = [t for _, t, _ in forecast]

    if temps[-1] < temps[0]:
        return "📉 Cooling trend expected"
    elif temps[-1] > temps[0]:
        return "📈 Warming trend expected"
    else:
        return "📊 Stable temperature trend"


# 🎯 SMART RECOMMENDATION
def smart_recommendation(condition, temp, feels_like, aqi):
    print("\n🎯 SMART RECOMMENDATION")
    print("------------------------------------------")

    if aqi == 5:
        print("🚫 Avoid outdoor travel — hazardous air")
        print("😷 Mask mandatory")
        print("✈️ Prefer shortest travel time")
        return

    if aqi >= 4:
        print("⚠️ Poor air quality — limit exposure")
        print("😷 Wear mask outdoors")

    elif aqi == 3:
        print("😷 Sensitive individuals may feel discomfort")

    if feels_like >= 35:
        print("🔥 High discomfort due to humidity")
        print("⛱ Avoid afternoon travel")
        print("💧 Stay hydrated")
        print("✈️ Prefer faster transport")

    if "haze" in condition.lower():
        print("🌫 Reduced visibility — travel cautiously")

    if "rain" in condition.lower():
        print("☔ Carry umbrella")
        print("🚗 Drive carefully")

    if aqi < 3 and feels_like < 32 and "rain" not in condition.lower():
        print("✅ Weather conditions are favorable for travel")
