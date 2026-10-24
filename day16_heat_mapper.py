"""
The Resilience Stack — Day 16
Urban Heat Relief Mapper

A full-screen map of where to cool down in any city: OpenStreetMap green
spaces, water bodies and public drinking-water taps, layered with
community-submitted cool spots (shaded cafés, libraries, public pools).

Why it matters is framed by Day 05 (Extreme Heat Atlas): we pull the local
count of dangerous-heat days per year so the map answers a real question —
"it's going to be brutal here, where do I actually go?"

First Act II tool with a community / UGC layer (Supabase-backed, with a
local fallback so it always runs). Foreshadows Day 20 (The Action Map).

Run: streamlit run day16_heat_mapper.py
Optional: run supabase_setup.sql once for the shared cool_spots table.
"""

import math
import os
import pathlib
from datetime import date

import folium
import requests
import streamlit as st
from folium.plugins import LocateControl
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Urban Heat Relief Mapper · Day 16",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Environment / credentials ───────────────────────────────────────────────────

def _get_env(name: str) -> str:
    """Read a key from the environment, a local .env, or st.secrets."""
    val = os.environ.get(name, "")
    if val:
        return val
    for env_file in [
        pathlib.Path(__file__).resolve().parent / ".env",
        pathlib.Path(os.getcwd()) / ".env",
        pathlib.Path.home() / "dev" / "climate-30" / ".env",
    ]:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


OPENROUTER_KEY = _get_env("OPENROUTER_API_KEY")
SUPABASE_URL   = _get_env("SUPABASE_URL").rstrip("/")
SUPABASE_KEY   = _get_env("SUPABASE_KEY")
SUPABASE_OK    = bool(SUPABASE_URL and SUPABASE_KEY)
MODEL          = "anthropic/claude-sonnet-4-5"

GEO_URL      = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS      = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

# Dangerous-heat threshold for the Day 05 framing: apparent ("feels like")
# temperature at/above which sustained outdoor exposure is hazardous.
HEAT_DANGER_C = 35.0
HEAT_YEARS    = ("2019-01-01", "2023-12-31")  # 5-year normal

# Community cool-spot categories (must match the cool_spots CHECK constraint).
CATEGORIES = {
    "shade":         {"colour": "green",     "emoji": "🌳", "label": "Shade / tree cover"},
    "water":         {"colour": "blue",      "emoji": "💧", "label": "Water / misting"},
    "park":          {"colour": "darkgreen", "emoji": "🌿", "label": "Park / open green"},
    "cool_building": {"colour": "purple",    "emoji": "🏛", "label": "Cool building (library, mall, pool)"},
    "other":         {"colour": "gray",      "emoji": "📍", "label": "Other relief spot"},
}

DEFAULT = {"lat": 12.9719, "lon": 77.5937, "name": "Bengaluru", "country": "India"}


# ══ Data: geocoding & distance ═══════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def geocode(location: str) -> dict | None:
    try:
        r = requests.get(
            GEO_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            headers=HEADERS, timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        top = results[0]
        return {
            "lat":     top["latitude"],
            "lon":     top["longitude"],
            "name":    top.get("name", location),
            "admin1":  top.get("admin1", ""),
            "country": top.get("country", ""),
        }
    except Exception:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ══ Data: OpenStreetMap green/blue assets ════════════════════════════════════════

@st.cache_data(ttl=1800)
def get_osm_features(lat: float, lon: float, radius: int = 2500) -> dict:
    """Parks, woods, water bodies and public drinking-water taps within `radius` m."""
    query = f"""
    [out:json][timeout:25];
    (
      way["leisure"="park"](around:{radius},{lat},{lon});
      way["leisure"="garden"](around:{radius},{lat},{lon});
      way["natural"="wood"](around:{radius},{lat},{lon});
      way["landuse"="forest"](around:{radius},{lat},{lon});
      way["natural"="water"](around:{radius},{lat},{lon});
      node["amenity"="drinking_water"](around:{radius},{lat},{lon});
      node["amenity"="fountain"](around:{radius},{lat},{lon});
    );
    out center;
    """
    out = {"parks": [], "water": [], "taps": []}
    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=35)
        r.raise_for_status()
        elements = r.json().get("elements", [])
    except Exception:
        return out

    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "node":
            flat, flon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center", {})
            flat, flon = c.get("lat"), c.get("lon")
        if flat is None or flon is None:
            continue
        name = tags.get("name", "")
        amenity = tags.get("amenity")
        if amenity in ("drinking_water", "fountain"):
            out["taps"].append({"lat": flat, "lon": flon, "name": name or "Public water"})
        elif tags.get("natural") == "water":
            out["water"].append({"lat": flat, "lon": flon, "name": name or "Water body"})
        else:
            out["parks"].append({"lat": flat, "lon": flon, "name": name or "Green space"})
    return out


# ══ Data: Day 05 heat context ═════════════════════════════════════════════════════

@st.cache_data(ttl=86400)
def get_heat_context(lat: float, lon: float) -> dict | None:
    """Dangerous-heat days/yr (apparent temp ≥ 35 °C), 2019–2023 normal."""
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": lat, "longitude": lon,
                "start_date": HEAT_YEARS[0], "end_date": HEAT_YEARS[1],
                "daily": "apparent_temperature_max",
                "timezone": "auto",
            },
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        vals = [v for v in r.json().get("daily", {}).get("apparent_temperature_max", []) if v is not None]
        if not vals:
            return None
        danger = sum(1 for v in vals if v >= HEAT_DANGER_C)
        years  = len(vals) / 365.25
        return {
            "danger_per_year": round(danger / years) if years else 0,
            "peak_feels_like": round(max(vals)),
        }
    except Exception:
        return None


# ══ Data: community cool spots (Supabase REST + local fallback) ═══════════════════

def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def get_community_spots(lat: float, lon: float, radius_km: float = 3.0) -> list:
    """Nearby, non-flagged community spots. Supabase first, else session-local."""
    local = st.session_state.get("local_spots", [])
    if SUPABASE_OK:
        delta = radius_km / 111.0
        url = (
            f"{SUPABASE_URL}/rest/v1/cool_spots"
            f"?select=*&lat=gte.{lat - delta}&lat=lte.{lat + delta}"
            f"&lng=gte.{lon - delta}&lng=lte.{lon + delta}&order=created_at.desc"
        )
        try:
            r = requests.get(url, headers=_sb_headers(), timeout=15)
            r.raise_for_status()
            rows = r.json()
        except Exception:
            rows = None
        if rows is not None:
            spots = [s for s in rows if not s.get("flagged")]
            return [s for s in spots if haversine_km(lat, lon, s["lat"], s["lng"]) <= radius_km]

    # Fallback: local, in-session spots
    return [
        s for s in local
        if not s.get("flagged") and haversine_km(lat, lon, s["lat"], s["lng"]) <= radius_km
    ]


def add_community_spot(lat, lng, description, category, city, country) -> bool:
    payload = {
        "lat": lat, "lng": lng,
        "description": description, "category": category,
        "city": city, "neighbourhood": country,
    }
    if SUPABASE_OK:
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/cool_spots",
                headers=_sb_headers({"Prefer": "return=representation"}),
                json=payload, timeout=15,
            )
            r.raise_for_status()
            return True
        except Exception:
            pass  # fall through to local store so the demo never dead-ends
    payload["id"] = f"local-{len(st.session_state.get('local_spots', []))}"
    payload["flagged"] = False
    st.session_state.setdefault("local_spots", []).append(payload)
    return True


def flag_spot(spot_id: str) -> None:
    """Hide a spot from the map. Supabase PATCH, else local mark."""
    if SUPABASE_OK and not str(spot_id).startswith("local-"):
        try:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/cool_spots?id=eq.{spot_id}",
                headers=_sb_headers({"Prefer": "return=minimal"}),
                json={"flagged": True}, timeout=15,
            )
        except Exception:
            pass
    for s in st.session_state.get("local_spots", []):
        if str(s.get("id")) == str(spot_id):
            s["flagged"] = True
    st.session_state.setdefault("flagged_ids", set()).add(str(spot_id))


# ══ AI: plan a cool route ═════════════════════════════════════════════════════════

def get_cool_route(place: str, osm: dict, community: list, heat: dict | None) -> str:
    if not OPENROUTER_KEY:
        return "_Add an OPENROUTER_API_KEY to your .env to get a personalised cool-route tip._"

    parks = ", ".join(p["name"] for p in osm["parks"] if p["name"])[:400] or "none named"
    water = ", ".join(w["name"] for w in osm["water"] if w["name"])[:200] or "none named"
    comm  = "\n".join(f"- {s['description']} ({s['category']})" for s in community[:6]) \
            or "No community spots marked here yet."
    heat_line = (
        f"This area sees about {heat['danger_per_year']} dangerous-heat days a year "
        f"(feels-like ≥ {int(HEAT_DANGER_C)} °C; peak felt {heat['peak_feels_like']} °C)."
        if heat else "Heat data unavailable for this area."
    )
    prompt = f"""You are a streetwise local helping someone beat the heat in {place}.

{heat_line}

Within ~2.5 km of them right now:
- Parks / green space: {parks}
- Water bodies: {water}
- Public water taps / fountains: {len(osm['taps'])}
- Community-marked cool spots:
{comm}

Write 4–5 short lines, like a friend texting. Name the single best place to head
to right now and the best time of day to go. Give one free thing they can do
immediately. Be specific to what actually exists near them — no generic advice,
no bullet points."""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/climate-30",
                "X-Title": "Resilience Stack — Day 16",
            },
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 220},
            timeout=40,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"_Couldn't reach the AI guide right now ({e})._"


# ══ Map ════════════════════════════════════════════════════════════════════════

def build_map(lat: float, lon: float, osm: dict, community: list,
              pin: tuple | None) -> folium.Map:
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles="CartoDB positron",
                   control_scale=True)
    LocateControl(auto_start=False, strings={"title": "Find my location"}).add_to(m)

    folium.Marker([lat, lon], tooltip="Search centre",
                  icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # OSM green spaces — filled green circles (per spec: filled circle style)
    for p in osm["parks"]:
        folium.CircleMarker([p["lat"], p["lon"]], radius=13, color="#15803d", weight=1.5,
                            fill=True, fill_color="#4ade80", fill_opacity=0.55,
                            tooltip=f"🌿 {p['name']}").add_to(m)
    # Water bodies — filled blue circles
    for w in osm["water"]:
        folium.CircleMarker([w["lat"], w["lon"]], radius=13, color="#0369a1", weight=1.5,
                            fill=True, fill_color="#7dd3fc", fill_opacity=0.55,
                            tooltip=f"💧 {w['name']}").add_to(m)
    # Public taps / fountains
    for t in osm["taps"]:
        folium.Marker([t["lat"], t["lon"]], tooltip=f"🚰 {t['name']}",
                      icon=folium.Icon(color="cadetblue", icon="tint", prefix="fa")).add_to(m)

    # Community cool spots — distinct star markers, coloured by category
    for s in community:
        cfg = CATEGORIES.get(s.get("category", "other"), CATEGORIES["other"])
        folium.Marker(
            [s["lat"], s["lng"]],
            tooltip=f"{cfg['emoji']} {s['description'][:60]}",
            popup=folium.Popup(f"<b>{cfg['emoji']} {cfg['label']}</b><br><br>{s['description']}",
                               max_width=240),
            icon=folium.Icon(color=cfg["colour"], icon="star", prefix="fa"),
        ).add_to(m)

    # Pending pin (where the user just clicked to add a spot)
    if pin:
        folium.Marker(pin, tooltip="New spot — fill the form to save",
                      icon=folium.Icon(color="orange", icon="plus", prefix="fa")).add_to(m)

    legend = """
    <div style="position:fixed;bottom:26px;left:26px;z-index:1000;background:rgba(255,255,255,.94);
        padding:12px 16px;border-radius:14px;box-shadow:0 6px 22px rgba(0,0,0,.14);
        font-size:12.5px;line-height:1.95;font-family:Inter,sans-serif;backdrop-filter:blur(8px);">
      <b style="font-size:13px;color:#0f172a;">Map layers</b><br>
      <span style="color:#4ade80;font-size:17px;">●</span> Green space &nbsp;
      <span style="color:#7dd3fc;font-size:17px;">●</span> Water<br>
      🚰 Public water tap &nbsp; ⭐ Community cool spot<br>
      ✚ Search centre / your new pin
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    return m


# ══ CSS ════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --rs-green: #16a34a;
  --rs-green-dark: #15803d;
  --rs-green-faint: rgba(22,163,74,.08);
  --rs-bg: #edf2ed;
  --rs-surface: rgba(255,255,255,.94);
  --rs-border: rgba(0,0,0,.07);
  --rs-text: #0f172a;
  --rs-text-muted: #64748b;
  --rs-radius: 10px;
  --rs-radius-lg: 16px;
  --font-display: 'Space Grotesk', sans-serif;
  --font-body: 'Inter', sans-serif;
}

html, body, [data-testid="stApp"] { background: var(--rs-bg) !important; font-family: var(--font-body) !important; }
#MainMenu, header, footer { visibility: hidden; }
[data-testid="stAppViewBlockContainer"], .block-container {
  max-width: 100% !important; padding: 1.1rem 1.4rem 0 !important;
}
[data-testid="stMarkdown"] { color: var(--rs-text); }

/* Header bar */
.rs-header { display:flex; align-items:center; gap:14px; margin-bottom:12px; }
.rs-title { font-family: var(--font-display); font-weight:800; font-size:1.5rem; color:var(--rs-text); letter-spacing:-.02em; }
.rs-sub { font-family: var(--font-body); color: var(--rs-text-muted); font-size:.85rem; margin-top:1px; }
.rs-badge { margin-left:auto; background:var(--rs-green); color:#fff; font-family:var(--font-display);
  font-weight:700; font-size:.72rem; padding:6px 14px; border-radius:20px; letter-spacing:.04em; }

/* Heat context banner */
.rs-heat { display:flex; align-items:center; gap:12px; background:rgba(251,146,60,.12);
  border:1px solid rgba(234,88,12,.25); border-radius:var(--rs-radius-lg); padding:12px 18px; margin:4px 0 14px; }
.rs-heat .big { font-family:var(--font-display); font-weight:800; font-size:1.7rem; color:#c2410c; line-height:1; }
.rs-heat .txt { font-size:.86rem; color:#7c2d12; }
.rs-heat .txt b { color:#9a3412; }

/* Empty-state invitation (Days 16/20 activation moment) */
.rs-empty { background:var(--rs-surface); border:1.5px dashed rgba(22,163,74,.45); border-radius:var(--rs-radius-lg);
  padding:22px 24px; margin:10px 0 16px; }
.rs-empty h4 { font-family:var(--font-display); font-weight:800; color:var(--rs-green-dark); font-size:1.05rem; margin:0 0 6px; }
.rs-empty p { color:var(--rs-text-muted); font-size:.9rem; margin:0; line-height:1.55; }

/* Sidebar as floating glass control panel */
[data-testid="stSidebar"] { background: var(--rs-surface) !important; backdrop-filter: blur(20px);
  border-right:1px solid var(--rs-border); }
[data-testid="stSidebar"] h3 { font-family:var(--font-display); color:var(--rs-text); font-weight:700; font-size:1rem; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { font-family:var(--font-display); color:var(--rs-green-dark); }

/* Buttons */
.stButton > button, [data-testid="stForm"] button {
  font-family:var(--font-display) !important; font-weight:700 !important; border-radius:var(--rs-radius) !important;
}
.stButton > button[kind="primary"], [data-testid="stForm"] button[kind="primaryFormSubmit"] {
  background: var(--rs-green) !important; border-color: var(--rs-green) !important;
}

/* Spot list cards (a11y list view + flag UI) */
.rs-spot { background:var(--rs-surface); border:1px solid var(--rs-border); border-radius:var(--rs-radius);
  padding:10px 13px; margin-bottom:8px; }
.rs-spot .cat { font-family:var(--font-display); font-weight:700; font-size:.78rem; color:var(--rs-green-dark); }
.rs-spot .desc { font-size:.85rem; color:var(--rs-text); margin-top:2px; }
.rs-spot .dist { font-size:.72rem; color:var(--rs-text-muted); }

.rs-fab-hint { position:fixed; right:26px; bottom:26px; z-index:1001; background:var(--rs-green); color:#fff;
  font-family:var(--font-display); font-weight:700; font-size:.82rem; padding:13px 18px; border-radius:30px;
  box-shadow:0 4px 16px rgba(22,163,74,.35); }
</style>
"""


# ══ Session ════════════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "lat": DEFAULT["lat"], "lon": DEFAULT["lon"],
        "place": f"{DEFAULT['name']}, {DEFAULT['country']}",
        "country": DEFAULT["country"], "city": DEFAULT["name"],
        "osm": None, "heat": None, "community": [],
        "pin": None, "last_click": None, "route": None,
        "view_list": False, "local_spots": [], "flagged_ids": set(),
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def main():
    init_session()
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Header + search ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="rs-header"><div>'
        '<div class="rs-title">🌳 Urban Heat Relief Mapper</div>'
        '<div class="rs-sub">Find green space, water and community cool spots near you — '
        'mark what you discover.</div></div>'
        '<div class="rs-badge">DAY 16</div></div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([5, 1])
    with c1:
        loc = st.text_input("Search a city or neighbourhood", placeholder="e.g. Dharavi, Mumbai · Phoenix, Arizona · Lagos",
                            label_visibility="collapsed")
    with c2:
        go = st.button("Find relief", type="primary", use_container_width=True)

    if go and loc.strip():
        with st.spinner("Locating…"):
            g = geocode(loc.strip())
        if not g:
            st.error("Location not found — try a nearby city or add the country.")
        else:
            place = ", ".join(p for p in [g["name"], g["admin1"], g["country"]] if p)
            st.session_state.update(
                lat=g["lat"], lon=g["lon"], place=place,
                city=g["name"], country=g["country"],
                osm=None, heat=None, community=[], pin=None, last_click=None, route=None,
            )

    # ── Fetch layers (cached per location) ───────────────────────────────────────
    if st.session_state.osm is None:
        with st.spinner("Loading green spaces, water and community spots…"):
            st.session_state.osm       = get_osm_features(st.session_state.lat, st.session_state.lon)
            st.session_state.heat      = get_heat_context(st.session_state.lat, st.session_state.lon)
            st.session_state.community = get_community_spots(st.session_state.lat, st.session_state.lon)

    osm, heat, community = st.session_state.osm, st.session_state.heat, st.session_state.community

    # ── Heat context banner (Day 05 framing) ─────────────────────────────────────
    if heat and heat["danger_per_year"] > 0:
        st.markdown(
            f'<div class="rs-heat"><div class="big">{heat["danger_per_year"]}</div>'
            f'<div class="txt"><b>dangerous-heat days a year</b> around {st.session_state.city} '
            f'(feels-like ≥ {int(HEAT_DANGER_C)}°C; peak felt {heat["peak_feels_like"]}°C). '
            f'Here is where to cool down.</div></div>',
            unsafe_allow_html=True,
        )

    # ── Community empty-state invitation ─────────────────────────────────────────
    if not community:
        st.markdown(
            '<div class="rs-empty"><h4>🌱 Be the first to add a cool spot here</h4>'
            '<p>This map grows with your community. Click anywhere on the map to drop a pin — '
            'a shady café, a library, a public pool or fountain — and help your neighbours beat the heat.</p></div>',
            unsafe_allow_html=True,
        )

    # ══ Control panel (floating glass sidebar) ════════════════════════════════════
    with st.sidebar:
        st.markdown(f"### {st.session_state.place}")
        m1, m2 = st.columns(2)
        m1.metric("Green spaces", len(osm["parks"]))
        m2.metric("Water bodies", len(osm["water"]))
        m1.metric("Public taps", len(osm["taps"]))
        m2.metric("Community spots", len(community))
        if not SUPABASE_OK:
            st.caption("⚠️ Supabase not configured — spots you add stay in this session only.")

        st.divider()

        # Add-a-spot form (triggered by clicking the map)
        st.markdown("### 📍 Add a cool spot")
        if st.session_state.pin:
            plat, plon = st.session_state.pin
            st.success(f"Pinned at {plat:.4f}, {plon:.4f}")
            with st.form("add_spot", clear_on_submit=True):
                desc = st.text_area("What did you find here?",
                                    placeholder="e.g. Shaded reading room, free water fountain, misting plaza…",
                                    max_chars=200)
                cat = st.selectbox("Category", list(CATEGORIES.keys()),
                                   format_func=lambda c: f"{CATEGORIES[c]['emoji']}  {CATEGORIES[c]['label']}")
                submitted = st.form_submit_button("Add to map ✓", type="primary", use_container_width=True)
            if submitted and desc.strip():
                ok = add_community_spot(plat, plon, desc.strip(), cat,
                                        st.session_state.city, st.session_state.country)
                if ok:
                    st.session_state.pin = None
                    st.session_state.last_click = None
                    st.session_state.community = get_community_spots(
                        st.session_state.lat, st.session_state.lon)
                    st.toast("Your spot is on the map! ✓", icon="✅")
                    st.rerun()
                else:
                    st.error("Couldn't save your spot — check your connection and try again.")
        else:
            st.info("Click anywhere on the map to drop a pin here.")

        st.divider()

        # AI cool-route
        st.markdown("### 🧭 Plan my cool route")
        if st.button("Ask the guide →", use_container_width=True):
            with st.spinner("Thinking…"):
                st.session_state.route = get_cool_route(
                    st.session_state.place, osm, community, heat)
        if st.session_state.route:
            st.markdown(st.session_state.route)

        st.divider()

        # Accessibility: view pins as a list (maps are screen-reader hostile)
        st.session_state.view_list = st.toggle("View spots as a list",
                                                value=st.session_state.view_list)

    # ══ Map (primary, full width) ═════════════════════════════════════════════════
    m = build_map(st.session_state.lat, st.session_state.lon, osm, community, st.session_state.pin)
    map_data = st_folium(m, width="100%", height=640, returned_objects=["last_clicked"])

    st.markdown('<div class="rs-fab-hint">＋ Click the map to add a spot</div>',
                unsafe_allow_html=True)

    # Detect a fresh map click → set pending pin
    if map_data and map_data.get("last_clicked"):
        clk = map_data["last_clicked"]
        key = (round(clk["lat"], 6), round(clk["lng"], 6))
        if key != st.session_state.last_click:
            st.session_state.pin = key
            st.session_state.last_click = key
            st.rerun()

    # ══ Accessible list view + flag/moderation ════════════════════════════════════
    if st.session_state.view_list:
        st.markdown("#### Community cool spots near you")
        if not community:
            st.caption("No community spots yet — be the first to add one.")
        for s in community:
            cfg = CATEGORIES.get(s.get("category", "other"), CATEGORIES["other"])
            dist = haversine_km(st.session_state.lat, st.session_state.lon, s["lat"], s["lng"])
            col, btn = st.columns([6, 1])
            with col:
                st.markdown(
                    f'<div class="rs-spot"><div class="cat">{cfg["emoji"]} {cfg["label"]}</div>'
                    f'<div class="desc">{s["description"]}</div>'
                    f'<div class="dist">{dist:.1f} km away</div></div>',
                    unsafe_allow_html=True,
                )
            with btn:
                if st.button("🚩 Flag", key=f"flag-{s.get('id')}", help="Report this spot for review"):
                    flag_spot(s.get("id"))
                    st.session_state.community = get_community_spots(
                        st.session_state.lat, st.session_state.lon)
                    st.toast("Reported for review. Thanks for keeping the map clean.", icon="🚩")
                    st.rerun()


if __name__ == "__main__":
    main()
