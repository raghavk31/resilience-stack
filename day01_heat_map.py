"""
Day 1 — Heat Relief Map
30 Days of Climate Code

A community map of cool spots, green spaces, and water bodies
for Indian cities. Click the map to mark a spot you discovered.

Run: streamlit run day01_heat_map.py

Before first run:
  1. pip install -r requirements.txt
  2. Run supabase_setup.sql in your Supabase SQL editor
"""

import os
import math
import requests
import folium
from folium.plugins import LocateControl
import streamlit as st
from streamlit_folium import st_folium
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# ── credentials ────────────────────────────────────────────────────────────────
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

db = create_client(SUPABASE_URL, SUPABASE_KEY)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"

# ── category config ────────────────────────────────────────────────────────────
CATEGORIES = {
    "shade":         {"colour": "green",     "emoji": "🌳", "label": "Shade"},
    "water":         {"colour": "blue",      "emoji": "💧", "label": "Water"},
    "park":          {"colour": "darkgreen", "emoji": "🌿", "label": "Park"},
    "cool_building": {"colour": "purple",    "emoji": "🏛",  "label": "Cool building"},
    "other":         {"colour": "gray",      "emoji": "📍", "label": "Other"},
}

# ── defaults ───────────────────────────────────────────────────────────────────
DEFAULT = {"lat": 12.9352, "lon": 77.6245, "neighbourhood": "Koramangala", "city": "Bengaluru"}


# ══ data functions ═════════════════════════════════════════════════════════════

def geocode(location: str) -> tuple[float, float, str, str]:
    """Return (lat, lon, neighbourhood_name, city) for a typed location string."""
    resp = requests.get(
        GEOCODING_URL,
        params={"name": location + ", India", "count": 1, "language": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        raise ValueError(f"Could not find '{location}'. Try adding the city, e.g. 'Dharavi, Mumbai'.")
    r = results[0]
    name = r.get("name", location)
    city = r.get("admin2") or r.get("admin1") or "India"
    return r["latitude"], r["longitude"], name, city


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_osm_features(lat: float, lon: float, radius: int = 2000) -> dict:
    """Fetch parks, water bodies, and drinking water taps from OpenStreetMap."""
    query = f"""
    [out:json][timeout:25];
    (
      way["leisure"="park"](around:{radius},{lat},{lon});
      way["natural"="wood"](around:{radius},{lat},{lon});
      way["natural"="water"](around:{radius},{lat},{lon});
      node["amenity"="drinking_water"](around:{radius},{lat},{lon});
    );
    out center;
    """
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception:
        return {"parks": [], "water": [], "drinking_water": []}

    features: dict = {"parks": [], "water": [], "drinking_water": []}
    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "node":
            flat, flon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            flat, flon = center.get("lat"), center.get("lon")
        if flat is None or flon is None:
            continue
        name = tags.get("name", "")
        if tags.get("amenity") == "drinking_water":
            features["drinking_water"].append({"lat": flat, "lon": flon, "name": name})
        elif tags.get("natural") == "water":
            features["water"].append({"lat": flat, "lon": flon, "name": name or "Water body"})
        else:
            features["parks"].append({"lat": flat, "lon": flon, "name": name or "Green space"})
    return features


def get_community_spots(lat: float, lon: float, radius_km: float = 2.0) -> list:
    """Fetch nearby community-marked cool spots from Supabase."""
    delta = radius_km / 111.0
    try:
        result = (
            db.table("cool_spots")
            .select("*")
            .gte("lat", lat - delta)
            .lte("lat", lat + delta)
            .gte("lng", lon - delta)
            .lte("lng", lon + delta)
            .order("created_at", desc=True)
            .execute()
        )
        spots = result.data or []
    except Exception:
        return []
    return [s for s in spots if haversine_km(lat, lon, s["lat"], s["lng"]) <= radius_km]


def add_community_spot(lat: float, lng: float, description: str, category: str,
                        neighbourhood: str, city: str) -> None:
    db.table("cool_spots").insert({
        "lat": lat, "lng": lng,
        "description": description, "category": category,
        "neighbourhood": neighbourhood, "city": city,
    }).execute()


# ══ map ════════════════════════════════════════════════════════════════════════

def build_map(lat: float, lon: float, osm: dict, community: list) -> folium.Map:
    m = folium.Map(
        location=[lat, lon],
        zoom_start=15,
        tiles="CartoDB positron",
    )

    LocateControl(auto_start=False, strings={"title": "Find my location"}).add_to(m)

    # you-are-here pin
    folium.Marker(
        [lat, lon],
        tooltip="You are here",
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
    ).add_to(m)

    # green spaces
    for p in osm["parks"]:
        folium.CircleMarker(
            [p["lat"], p["lon"]],
            radius=14,
            color="#1b4332",
            fill=True, fill_color="#52b788", fill_opacity=0.55,
            tooltip=f"🌿 {p['name']}",
        ).add_to(m)

    # water bodies
    for w in osm["water"]:
        folium.CircleMarker(
            [w["lat"], w["lon"]],
            radius=14,
            color="#023e8a",
            fill=True, fill_color="#90e0ef", fill_opacity=0.55,
            tooltip=f"💧 {w['name']}",
        ).add_to(m)

    # drinking water taps
    for dw in osm["drinking_water"]:
        folium.Marker(
            [dw["lat"], dw["lon"]],
            tooltip=f"🚰 {dw['name'] or 'Free drinking water'}",
            icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        ).add_to(m)

    # community cool spots
    for spot in community:
        cat = spot.get("category", "other")
        cfg = CATEGORIES.get(cat, CATEGORIES["other"])
        folium.Marker(
            [spot["lat"], spot["lng"]],
            tooltip=f"{cfg['emoji']} {spot['description'][:60]}",
            popup=folium.Popup(
                f"<b>{cfg['emoji']} {cfg['label']}</b><br><br>{spot['description']}",
                max_width=220,
            ),
            icon=folium.Icon(color=cfg["colour"], icon="leaf", prefix="fa"),
        ).add_to(m)

    # legend
    legend = """
    <div style="position:fixed;bottom:28px;left:28px;z-index:1000;
                background:white;padding:12px 16px;border-radius:10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.12);font-size:13px;line-height:2;">
      <b style="font-size:14px;">Map layers</b><br>
      <span style="color:#52b788;font-size:18px;">●</span> Green space / park<br>
      <span style="color:#90e0ef;font-size:18px;">●</span> Water body<br>
      🚰 Free drinking water<br>
      ⭐ You are here<br>
      📍 Community cool spot
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    return m


# ══ Claude strategy ════════════════════════════════════════════════════════════

def get_claude_strategy(neighbourhood: str, city: str, osm: dict, community: list) -> str:
    parks_text = ", ".join(p["name"] for p in osm["parks"] if p["name"]) or "none found"
    water_text = ", ".join(w["name"] for w in osm["water"] if w["name"]) or "none found"
    n_taps     = len(osm["drinking_water"])
    comm_text  = (
        "\n".join(f"- {s['description']} ({s['category']})" for s in community[:5])
        or "No community spots marked yet in this area."
    )

    prompt = f"""You are a local guide helping someone beat the heat in {city}.

They are near {neighbourhood}. Within 2km of them right now:
- Parks / green spaces: {parks_text}
- Water bodies: {water_text}
- Free drinking water taps: {n_taps}
- Cool spots the community has marked:
{comm_text}

Write exactly 4–5 lines. Name the single best place to go right now and the best time to go.
Give one thing they can do immediately that costs nothing.
Be specific to what actually exists near them. No bullet points. No generic advice.
Write it like a friend texting them."""

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/climate-30",
            "X-Title": "30 Days of Climate Code",
        },
        json={
            "model": "anthropic/claude-opus-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ══ Streamlit app ══════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "lat":              DEFAULT["lat"],
        "lon":              DEFAULT["lon"],
        "neighbourhood":    DEFAULT["neighbourhood"],
        "city":             DEFAULT["city"],
        "osm":              None,
        "community":        [],
        "clicked_lat":      None,
        "clicked_lon":      None,
        "last_click_lat":   None,
        "last_click_lon":   None,
        "strategy":         None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def main():
    st.set_page_config(page_title="Heat Relief Map", page_icon="🌿", layout="wide")
    init_session()

    # ── header
    st.title("🌿 Heat Relief Map")
    st.caption("Find cool spots near you. Mark what you discover. Help your city.")

    # ── location search
    col1, col2 = st.columns([4, 1])
    with col1:
        location_input = st.text_input(
            "location",
            placeholder="e.g. Dharavi, Mumbai · Anna Nagar, Chennai · Begumpet, Hyderabad",
            label_visibility="collapsed",
        )
    with col2:
        search = st.button("Find cool spots", type="primary", use_container_width=True)

    if search and location_input:
        with st.spinner("Locating..."):
            try:
                lat, lon, name, city = geocode(location_input)
                st.session_state.update(
                    lat=lat, lon=lon, neighbourhood=name, city=city,
                    osm=None, community=[], strategy=None,
                    clicked_lat=None, clicked_lon=None,
                    last_click_lat=None, last_click_lon=None,
                )
            except ValueError as e:
                st.error(str(e))

    # ── fetch map data (cached in session until location changes)
    if st.session_state.osm is None:
        with st.spinner("Loading green spaces and water near you..."):
            st.session_state.osm       = get_osm_features(st.session_state.lat, st.session_state.lon)
            st.session_state.community = get_community_spots(st.session_state.lat, st.session_state.lon)

    osm       = st.session_state.osm
    community = st.session_state.community

    # ══ sidebar ════════════════════════════════════════════════════════════════
    with st.sidebar:

        # stats
        st.markdown(f"### {st.session_state.neighbourhood}, {st.session_state.city}")
        c1, c2 = st.columns(2)
        c1.metric("Green spaces", len(osm["parks"]))
        c2.metric("Water bodies", len(osm["water"]))
        c1.metric("Water taps", len(osm["drinking_water"]))
        c2.metric("Community spots", len(community))

        st.divider()

        # add-a-spot form
        st.markdown("### 📍 Add a cool spot")
        if st.session_state.clicked_lat:
            st.success(
                f"Pinned at {st.session_state.clicked_lat:.4f}°, "
                f"{st.session_state.clicked_lon:.4f}°"
            )
            with st.form("spot_form", clear_on_submit=True):
                description = st.text_area(
                    "What did you find here?",
                    placeholder="e.g. Shaded walkway along the compound wall, free water outside the temple...",
                    max_chars=200,
                )
                category = st.selectbox(
                    "Category",
                    list(CATEGORIES.keys()),
                    format_func=lambda c: f"{CATEGORIES[c]['emoji']}  {CATEGORIES[c]['label']}",
                )
                submitted = st.form_submit_button("Add to map ✓", type="primary", use_container_width=True)

            if submitted and description.strip():
                add_community_spot(
                    lat=st.session_state.clicked_lat,
                    lng=st.session_state.clicked_lon,
                    description=description.strip(),
                    category=category,
                    neighbourhood=st.session_state.neighbourhood,
                    city=st.session_state.city,
                )
                st.session_state.clicked_lat  = None
                st.session_state.clicked_lon  = None
                st.session_state.last_click_lat = None
                st.session_state.last_click_lon = None
                st.session_state.community    = get_community_spots(
                    st.session_state.lat, st.session_state.lon
                )
                st.success("Spot added! Others can now find it.")
                st.rerun()
        else:
            st.info("Click anywhere on the map to drop a pin.")

        st.divider()

        # Claude strategy
        st.markdown("### 🧭 Plan my cool route")
        if st.button("Ask Claude →", use_container_width=True):
            with st.spinner("Thinking..."):
                st.session_state.strategy = get_claude_strategy(
                    st.session_state.neighbourhood,
                    st.session_state.city,
                    osm, community,
                )
        if st.session_state.strategy:
            st.markdown(st.session_state.strategy)

    # ══ map ════════════════════════════════════════════════════════════════════
    m = build_map(st.session_state.lat, st.session_state.lon, osm, community)
    map_data = st_folium(m, width="100%", height=560, returned_objects=["last_clicked"])

    # detect new map clicks (guard against re-processing same click on rerun)
    if map_data and map_data.get("last_clicked"):
        clk  = map_data["last_clicked"]
        clat = round(clk["lat"], 6)
        clon = round(clk["lng"], 6)
        if clat != st.session_state.last_click_lat or clon != st.session_state.last_click_lon:
            st.session_state.clicked_lat    = clat
            st.session_state.clicked_lon    = clon
            st.session_state.last_click_lat = clat
            st.session_state.last_click_lon = clon
            st.rerun()


if __name__ == "__main__":
    main()
