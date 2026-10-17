"""
📍 LOCATION AGENT  —  v7 (ITINERARY LOGIC FIXES)
=====================================
✅ Activity diversity: 70/30 mix (main interest + complementary)
✅ Geographic clustering by area
✅ Strict category filter
✅ Weighted place scoring
"""

import requests
import os
import json
import time

# 🔑 NVIDIA API key
API_KEY = os.environ.get("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", "")

# 🔑 Pexels API key
PEXELS_API_KEY = os.environ.get("AC9QThbONAypxXQTQv9YSwVOvIsCVJxgCYA5K3pDpX8Hsi8n6xcUuqQG", "")

URL = "https://integrate.api.nvidia.com/v1/chat/completions"


# ============================================================
# 🎯 ACTIVITY DIVERSITY CONFIG
# Main interest gets 70%, complementary 30%
# ============================================================

COMPLEMENTARY = {
    "beach":     ["fort", "lighthouse", "market", "church", "sunset point"],
    "temple":    ["museum", "market", "garden", "fort"],
    "fort":      ["museum", "temple", "viewpoint", "beach"],
    "museum":    ["garden", "market", "temple", "fort"],
    "adventure": ["waterfall", "viewpoint", "beach", "fort"],
    "mosque":    ["market", "garden", "museum"],
    "general":   ["museum", "market", "garden", "viewpoint"],
}


# ============================================================
# 🖼️  GET IMAGES (Pexels)
# ============================================================
def get_images(place_name):
    try:
        res  = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": place_name + " tourist place", "per_page": 3},
        )
        data = res.json()
        return [photo["src"]["medium"] for photo in data.get("photos", [])]
    except Exception:
        return []


# ============================================================
# ✅ CATEGORY FILTER
# ============================================================
def is_valid_place(name, interest):
    name = name.lower()
    if interest in ["temple", "temples"]:
        return (
            any(w in name for w in ["temple", "mandir"])
            and not any(w in name for w in ["dargah", "mosque", "church", "memorial"])
        )
    elif interest == "mosque":
        return any(w in name for w in ["mosque", "dargah"])
    elif interest == "beach":
        return "beach" in name
    return True


# ============================================================
# 🧠 JSON PARSER
# ============================================================
def extract_json(content):
    try:
        return json.loads(content)
    except Exception:
        try:
            s = content.find("[")
            e = content.rfind("]") + 1
            return json.loads(content[s:e])
        except Exception:
            return None


# ============================================================
# 🔁 REMOVE DUPLICATES
# ============================================================
def remove_duplicates(places):
    seen, unique = set(), []
    for p in places:
        n = p.get("name", "").lower()
        if n and n not in seen:
            seen.add(n)
            unique.append(p)
    return unique


# ============================================================
# 📝 DESCRIPTION PADDER
# ============================================================
def ensure_long_description(desc, place_name="", interest=""):
    if len(desc.split()) >= 60:
        return desc
    ext = {
        "beach":     f"{place_name} is beloved for its golden sands, clear waters, and vibrant beach shacks offering fresh seafood and cold drinks.",
        "temple":    f"{place_name} draws devotees and history enthusiasts alike with its intricate carvings, spiritual atmosphere, and centuries-old traditions.",
        "fort":      f"{place_name} offers panoramic views and a glimpse into the military architecture and history of the region.",
        "museum":    f"{place_name} houses a fascinating collection that traces the cultural and artistic heritage of the area.",
        "adventure": f"{place_name} is a favourite among thrill-seekers for its outdoor activities and natural landscapes.",
    }.get(interest.lower(), f"{place_name} is a must-visit destination known for its unique character and local charm.")
    return desc.rstrip() + " " + ext


INDIA_CITIES = {
    "goa", "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "jaipur", "agra", "varanasi", "kerala",
    "kochi", "mysore", "udaipur", "manali", "shimla", "darjeeling", "ooty",
}


# ============================================================
# 🤖 LLM FETCH FOR ONE CATEGORY
# ============================================================
def _fetch_category(location_qualified, category, count=9):
    prompt = f"""
You are a professional travel expert with deep knowledge of {location_qualified}.

Suggest TOP {count} MOST FAMOUS and HIGHLY VISITED {category} in {location_qualified}.

STRICT RULES:
- Only include {category} (no other category)
- Only famous and well-known places
- Descriptions must be SPECIFIC — mention unique features, history, best time, what makes it stand out.
- Do NOT use generic filler phrases.

For EACH place provide:
- name
- area  (specific locality / neighbourhood)
- rating (out of 5, realistic)
- detailed_description (80+ words, specific to this exact place)
- opening_time  (HH:MM, 24-hour format, e.g. "09:00"; use "00:00" if open 24 hours)
- closing_time  (HH:MM, 24-hour format, e.g. "18:00"; use "23:59" if open 24 hours)
- recommended_duration  (integer minutes, e.g. 90)

Sort by DESCENDING rating.

Return ONLY JSON:
[
  {{
    "name": "",
    "area": "",
    "rating": 4.5,
    "detailed_description": "",
    "opening_time": "09:00",
    "closing_time": "18:00",
    "recommended_duration": 90
  }}
]
"""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model":       "meta/llama-3.1-70b-instruct",
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens":  2500,
    }
    try:
        res = requests.post(URL, headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            return []
        content = res.json()["choices"][0]["message"]["content"]
        raw = extract_json(content) or []
        return raw
    except Exception:
        return []


# ============================================================
# 🏆 WEIGHTED PLACE SCORING
# score = 0.5*rating + 0.3*popularity_signal + 0.2*diversity_bonus
# ============================================================
def _score_place(p, is_main_interest=True):
    rating = float(p.get("rating", 4.0))
    base   = rating * 0.5
    pop    = min(len(p.get("detailed_description", "").split()) / 100, 1.0) * 0.3
    div    = 0.0 if is_main_interest else 0.2   # diversity bonus for complementary
    return round(base + pop + div, 4)


# ============================================================
# 📍 MAIN FUNCTION  (with diversity + clustering)
# ============================================================
def get_places(location, interest, user_preference=None):
    """
    Returns up to 12 places with 70% main interest + 30% complementary.
    user_preference: 'relaxation' | 'adventure' | 'nightlife' | 'photography'
    """
    loc_q = location
    if location.strip().lower() in INDIA_CITIES:
        loc_q = f"{location.strip()}, India"

    # ── Main interest fetch (9 places)
    main_raw  = _fetch_category(loc_q, interest, count=9)

    # ── Complementary fetch (3-4 places for variety)
    comp_interests = COMPLEMENTARY.get(interest.lower(), ["market", "garden"])
    comp_interest  = comp_interests[0]   # pick first complementary type
    comp_raw = _fetch_category(loc_q, comp_interest, count=4)

    def _build(raw, interest_tag, is_main):
        out = []
        for p in raw:
            name = p.get("name", "")
            if not name:
                continue
            if is_main and not is_valid_place(name, interest):
                continue
            try:
                rating = float(p.get("rating", 4.0))
            except Exception:
                rating = 4.0
            entry = {
                "name":                 name,
                "area":                 p.get("area", "N/A"),
                "rating":               rating,
                "interest_tag":         interest_tag,
                "detailed_description": ensure_long_description(
                    p.get("detailed_description", ""),
                    place_name=name,
                    interest=interest_tag,
                ),
                "opening_time":         p.get("opening_time", "09:00"),
                "closing_time":         p.get("closing_time", "18:00"),
                "recommended_duration": int(p.get("recommended_duration", 90)),
                # ✅ FIX-I3: lat/lon seeded as None; itinerary.attach_coordinates()
                # geocodes once and fills these in before any routing.
                "lat":  None,
                "lon":  None,
            }
            entry["_score"] = _score_place(entry, is_main)
            out.append(entry)
        return out

    main_places = _build(main_raw, interest, True)
    comp_places = _build(comp_raw, comp_interest, False)

    # Apply preference boost
    if user_preference:
        pref_keywords = {
            "relaxation":   ["beach", "garden", "resort", "spa", "sunset"],
            "adventure":    ["fort", "waterfall", "trek", "water sport", "cliff"],
            "nightlife":    ["market", "shack", "bar", "casino", "festival"],
            "photography":  ["fort", "lighthouse", "sunset", "church", "viewpoint"],
        }
        keywords = pref_keywords.get(user_preference.lower(), [])
        for p in main_places + comp_places:
            desc = (p["name"] + " " + p.get("detailed_description", "")).lower()
            if any(kw in desc for kw in keywords):
                p["_score"] += 0.15

    main_places = sorted(remove_duplicates(main_places), key=lambda x: x["_score"], reverse=True)
    comp_places = sorted(remove_duplicates(comp_places), key=lambda x: x["_score"], reverse=True)

    # 70 / 30 mix — 9 main + 3 complementary = 12
    selected = main_places[:9] + comp_places[:3]

    # ── Geographic clustering: group by area keyword
    clusters = {}
    for p in selected:
        area_key = p.get("area", "").split(",")[0].strip().lower() or "other"
        clusters.setdefault(area_key, []).append(p)

    # Interleave clusters so days naturally form geographic groups
    interleaved = []
    max_len = max((len(v) for v in clusters.values()), default=1)
    cluster_lists = list(clusters.values())
    for i in range(max_len):
        for cl in cluster_lists:
            if i < len(cl):
                interleaved.append(cl[i])

    # Final dedup + limit
    return remove_duplicates(interleaved)[:12]


# ============================================================
# 🖨️  PRINT FUNCTION
# ============================================================
def print_places(places):
    print("\n✨ Top Places (Sorted by Score):\n")
    for i, p in enumerate(places, 1):
        tag = f" [{p.get('interest_tag','')}]" if p.get("interest_tag") else ""
        print(f"{i}. 🏝️  {p['name']}{tag} ⭐ {p['rating']}")
        print(f"   📍 Area: {p['area']}")
        print("\n   📝 Description:")
        print(p["detailed_description"])

        images = get_images(p["name"])
        if images:
            print("\n   🖼️  Images:")
            for img in images:
                print("   ", img)

        print(f"\n   🗺️  https://www.google.com/maps/search/{p['name'].replace(' ', '+')}")
        print("-" * 60)
