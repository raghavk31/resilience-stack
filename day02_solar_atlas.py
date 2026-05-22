"""
Day 02 — Solar Potential Atlas  (V3: Morphocode-style)
The Resilience Stack: 30 Days Building the Intelligence Layer for Humanity

UI: full-screen map canvas  ·  solid dark left panel  ·  hero numbers  ·  micro-labels
Run:  streamlit run day02_solar_atlas.py
"""

import math, requests, urllib3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import folium
from folium.plugins import Draw, LocateControl
from streamlit_folium import st_folium
from calendar import monthrange
from collections import defaultdict

# ── constants ──────────────────────────────────────────────────────────────────
GEOCODE_URL  = "https://geocoding-api.open-meteo.com/v1/search"
PVGIS_URL    = "https://re.jrc.ec.europa.eu/api/v5_3/MRcalc"
NASA_URL     = "https://power.larc.nasa.gov/api/temporal/monthly/point"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM    = "https://nominatim.openstreetmap.org/reverse"

PANEL_W    = 400
PANEL_M2   = 1.7
EFFICIENCY = 0.20
PERF_RATIO = 0.80
CO2_G_KWH  = 450
COST_USD_W = 1.0

MONTHS     = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
MONTHS_3   = ["J","F","M","A","M","J","J","A","S","O","N","D"]

BENCHMARKS = {
    "Sahara":      7.3,
    "Rajasthan":   6.2,
    "Dubai":       5.8,
    "Los Angeles": 5.5,
    "Mumbai":      5.2,
    "Nairobi":     5.7,
    "Lagos":       5.4,
    "São Paulo":   5.3,
    "Sydney":      5.0,
    "Madrid":      5.1,
    "Beijing":     4.5,
    "New York":    4.3,
    "Tokyo":       4.0,
    "Berlin":      3.1,
    "London":      2.8,
}

SOLAR_BANDS = [
    (6.5, "WORLD-CLASS", "#f0a040", "Top 1% globally"),
    (5.5, "EXCELLENT",   "#e8803a", "Better than most of Europe"),
    (4.5, "GOOD",        "#d4b840", "Pays back in under 6 years"),
    (3.5, "MODERATE",    "#6ab87a", "Viable with storage"),
    (0.0, "LOW",         "#5a90d0", "Works, needs more panels"),
]

def solar_class(ghi):
    for t, lbl, col, tag in SOLAR_BANDS:
        if ghi >= t:
            return lbl, col, tag
    return "LOW", "#5a90d0", "Works, needs more panels"

# ── network helpers ─────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "ResilienceStack/1.0 (climate research)"}

def _get_session():
    s = requests.Session()
    retry = urllib3.Retry(total=3, backoff_factor=0.5,
                          status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s

# ── geocoding ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400*30, show_spinner=False)
def geocode(query: str):
    try:
        r = requests.get(GEOCODE_URL,
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=10)
        r.raise_for_status()
        res = r.json().get("results", [])
        if not res:
            return None
        loc = res[0]
        return {"lat": loc["latitude"], "lon": loc["longitude"],
                "name": loc.get("name", query),
                "country": loc.get("country", ""),
                "admin": loc.get("admin1", "")}
    except Exception:
        return None

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str:
    try:
        r = requests.get(NOMINATIM,
            params={"lat": lat, "lon": lon, "format": "jsonv2"},
            headers=HEADERS, timeout=8)
        r.raise_for_status()
        addr = r.json().get("address", {})
        city = (addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("suburb") or addr.get("county") or "")
        country = addr.get("country_code", "").upper()
        return f"{city}, {country}" if city else f"{lat:.3f}°, {lon:.3f}°"
    except Exception:
        return f"{lat:.3f}°, {lon:.3f}°"

# ── solar data ─────────────────────────────────────────────────────────────────
def _month_avg(d: dict) -> dict:
    avgs = {}
    for m in range(1, 13):
        vals = [v for k, v in d.items() if k.endswith(f"{m:02d}") and v and v > 0]
        avgs[m] = round(sum(vals)/len(vals), 3) if vals else None
    return avgs

@st.cache_data(ttl=86400*30, show_spinner=False)
def fetch_solar(lat: float, lon: float) -> dict | None:
    sess = _get_session()
    # 1. PVGIS
    try:
        r = sess.get(PVGIS_URL, params={"lat": round(lat,4), "lon": round(lon,4),
            "startyear": 2019, "endyear": 2023, "horirrad": 1,
            "outputformat": "json", "browser": 0}, timeout=30)
        r.raise_for_status()
        rows = r.json().get("outputs", {}).get("monthly", [])
        if rows:
            sums: dict = defaultdict(list)
            for row in rows:
                m, yr, hm = int(row["month"]), int(row["year"]), row.get("H(h)_m")
                if hm and hm > 0:
                    sums[m].append(hm / monthrange(yr, m)[1])
            ghi  = {m: round(sum(vs)/len(vs), 3) for m, vs in sums.items() if vs}
            clr  = {m: round(v*1.18, 3) for m, v in ghi.items()}
            temp = {m: None for m in range(1,13)}
            valid = [v for v in ghi.values() if v and v > 0]
            if len(valid) >= 10:
                return {"ghi": ghi, "clear": clr, "temp": temp,
                        "annual": round(sum(valid)/len(valid), 3),
                        "source": "PVGIS · EU JRC"}
    except Exception:
        pass
    # 2. NASA POWER
    try:
        r = sess.get(NASA_URL, params={
            "parameters": "ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,T2M",
            "community": "RE", "longitude": round(lon,4), "latitude": round(lat,4),
            "start": 2019, "end": 2023, "format": "JSON"}, timeout=30)
        r.raise_for_status()
        data = r.json()["properties"]["parameter"]
        ghi  = _month_avg(data["ALLSKY_SFC_SW_DWN"])
        clr  = _month_avg(data["CLRSKY_SFC_SW_DWN"])
        temp = _month_avg(data["T2M"])
        valid = [v for v in ghi.values() if v]
        if valid:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid)/len(valid), 3),
                    "source": "NASA POWER"}
    except Exception:
        pass
    # 3. Open-Meteo
    try:
        r = sess.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": round(lat,4), "longitude": round(lon,4),
            "start_date": "2019-01-01", "end_date": "2023-12-31",
            "daily": "shortwave_radiation_sum", "timezone": "UTC"}, timeout=30)
        r.raise_for_status()
        daily = r.json().get("daily", {})
        ms: dict = defaultdict(list)
        for d, v in zip(daily.get("time",[]), daily.get("shortwave_radiation_sum",[])):
            if v is not None and v >= 0:
                ms[int(d[5:7])].append(v/3.6)
        ghi  = {m: round(sum(vs)/len(vs),3) for m, vs in ms.items() if vs}
        clr  = {m: round(v*1.15,3) for m, v in ghi.items()}
        temp = {m: None for m in range(1,13)}
        valid = list(ghi.values())
        if valid:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid)/len(valid),3),
                    "source": "Open-Meteo ERA5"}
    except Exception:
        pass
    return None

# ── OSM buildings ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_buildings(south, west, north, east) -> list:
    query = (f"[out:json][timeout:25];\n"
             f"(way[\"building\"]({south:.5f},{west:.5f},{north:.5f},{east:.5f}););\n"
             f"out geom;")
    try:
        r = _get_session().post(OVERPASS_URL, data={"data": query}, timeout=30)
        r.raise_for_status()
        out = []
        for el in r.json().get("elements", []):
            if el.get("type") == "way" and el.get("geometry"):
                coords = [(n["lat"], n["lon"]) for n in el["geometry"]]
                if len(coords) >= 3:
                    area = _poly_area_m2(coords)
                    if area > 10:
                        out.append({"coords": coords, "area_m2": round(area, 1)})
        return out
    except Exception:
        return []

def _poly_area_m2(coords) -> float:
    if len(coords) < 3:
        return 0.0
    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(coords[0][0]))
    n, area = len(coords), 0.0
    for i in range(n):
        x1, y1 = coords[i][1]*lon_m,       coords[i][0]*lat_m
        x2, y2 = coords[(i+1)%n][1]*lon_m, coords[(i+1)%n][0]*lat_m
        area += x1*y2 - x2*y1
    return abs(area) / 2.0

def bldg_kwh_yr(area_m2, ghi):
    return area_m2 * 0.6 * ghi * EFFICIENCY * PERF_RATIO * 365

def bldg_colour(kwh):
    if kwh >= 20_000: return "#f0a040"
    if kwh >= 10_000: return "#d4824a"
    if kwh >=  5_000: return "#c8b044"
    if kwh >=  2_000: return "#5aab78"
    return "#4888c8"

def calc_area_solar(bounds, ghi) -> dict:
    s,n,w,e = bounds["south"],bounds["north"],bounds["west"],bounds["east"]
    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians((s+n)/2))
    area_m2  = abs(e-w)*lon_m * abs(n-s)*lat_m
    rooftop  = area_m2 * 0.20 * 0.60
    kwh_yr   = rooftop * ghi * EFFICIENCY * PERF_RATIO * 365
    return {
        "area_km2":   round(area_m2/1_000_000, 3),
        "area_ha":    round(area_m2/10_000, 1),
        "rooftop_m2": round(rooftop),
        "mwh_yr":     round(kwh_yr/1000),
        "homes":      round(kwh_yr/3500),
        "panels":     int(rooftop/PANEL_M2),
        "co2_kt":     round(kwh_yr*CO2_G_KWH/1_000_000, 1),
    }

# ── calculator ─────────────────────────────────────────────────────────────────
def calc(ghi, n):
    kwh_yr  = ghi * n*PANEL_M2 * EFFICIENCY * PERF_RATIO * 365
    peak_kw = n*PANEL_W/1000
    cost    = peak_kw*1000*COST_USD_W
    return {
        "kwh_yr":    round(kwh_yr),
        "kwh_day":   round(kwh_yr/365, 1),
        "peak_kw":   round(peak_kw, 1),
        "homes":     round(kwh_yr/3500, 1),
        "phones":    int(kwh_yr/365*1000/12),
        "co2_trees": round(kwh_yr*CO2_G_KWH/1000/21),
        "cost":      round(cost),
        "payback":   round(cost/(kwh_yr*0.12), 1) if kwh_yr > 0 else None,
    }

# ── map builder ────────────────────────────────────────────────────────────────
def build_map(lat, lon, zoom, ghi, buildings=None, area_coords=None):
    m = folium.Map(location=[lat, lon], zoom_start=zoom,
                   tiles="CartoDB dark_matter", prefer_canvas=True)
    Draw(export=False, draw_options={
        "rectangle": {"shapeOptions": {"color": "#f0a040", "weight": 2, "fillOpacity": 0.06}},
        "polygon": False, "polyline": False,
        "circle": False, "marker": False, "circlemarker": False},
        edit_options={"edit": False, "remove": True}).add_to(m)
    LocateControl(auto_start=False).add_to(m)

    _, col, _ = solar_class(ghi)
    folium.Marker([lat, lon], icon=folium.DivIcon(
        html=f'<div style="width:16px;height:16px;border-radius:50%;'
             f'background:{col};border:2px solid rgba(255,255,255,0.9);'
             f'box-shadow:0 0 12px {col},0 0 28px {col}44"></div>',
        icon_size=(16,16), icon_anchor=(8,8)),
        popup=folium.Popup(
            f'<div style="font-family:Inter,sans-serif;padding:6px 8px">'
            f'<b style="font-size:15px;color:#111">{ghi:.2f}</b>'
            f'<span style="color:#666;font-size:11px"> kWh/m²/day</span><br>'
            f'<span style="color:#999;font-size:10px">{lat:.4f}°, {lon:.4f}°</span>'
            f'</div>', max_width=180),
        tooltip=f"☀ {ghi:.2f} kWh/m²/day").add_to(m)

    if buildings:
        for b in buildings[:400]:
            kwh = bldg_kwh_yr(b["area_m2"], ghi)
            c   = bldg_colour(kwh)
            folium.Polygon(b["coords"], color=c, weight=0.8,
                fill=True, fill_color=c, fill_opacity=0.65,
                tooltip=f"{int(kwh):,} kWh/yr · {int(b['area_m2'])}m²").add_to(m)

    if area_coords:
        folium.Polygon([(c[1],c[0]) for c in area_coords],
            color="#f0a040", weight=2, dash_array="8 5",
            fill=True, fill_color="#f0a040", fill_opacity=0.08).add_to(m)
    return m

# ── charts ─────────────────────────────────────────────────────────────────────
def chart_monthly(solar) -> go.Figure:
    """P2: single amber colour, no grid, no tick labels, no clear-sky line.
    The shape speaks; colour does not classify."""
    vals = [solar["ghi"].get(m) or 0 for m in range(1, 13)]
    # Highlight peak + trough only; rest are uniform amber at low opacity
    peak = max(range(12), key=lambda i: vals[i])
    cols = ["rgba(240,160,64,0.28)"] * 12
    cols[peak] = "rgba(240,160,64,0.85)"

    fig = go.Figure(go.Bar(
        x=MONTHS_3, y=vals,
        marker_color=cols,
        hovertemplate="<b>%{x}</b>  %{y:.2f} kWh/m²/day<extra></extra>",
    ))
    fig.update_layout(
        height=110,
        margin=dict(l=0, r=0, t=2, b=0),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=True,
                   tickfont=dict(color="#2c2f48", size=8),
                   tickmode="array", tickvals=MONTHS_3),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        bargap=0.22,
    )
    return fig

def chart_rank(my_ghi, my_name) -> go.Figure:
    """P2: grey bars for all cities, single amber bar for selected.
    No text annotations on bars — values in hover only."""
    data  = dict(BENCHMARKS)
    short = my_name.split(",")[0].strip()
    data[short] = my_ghi
    df = pd.DataFrame({"city": list(data.keys()), "ghi": list(data.values())})
    df = df.sort_values("ghi", ascending=True)

    cols = ["rgba(240,160,64,0.9)" if c == short
            else "rgba(255,255,255,0.1)" for c in df["city"]]
    labels = [c if c != short else f"{c} ◀" for c in df["city"].tolist()]

    fig = go.Figure(go.Bar(
        x=df["ghi"], y=labels, orientation="h",
        marker_color=cols,
        hovertemplate="<b>%{y}</b>  %{x:.2f} kWh/m²/day<extra></extra>",
    ))
    fig.update_layout(
        height=max(260, len(df) * 18),
        margin=dict(l=0, r=8, t=2, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False,
                   tickfont=dict(color="#404468", size=9)),
    )
    return fig

# ══ CSS ════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── reset & base ───────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body { background: #0b0c10 !important; }

.stApp,
[data-testid="stAppViewContainer"] {
  background: #0b0c10 !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  color: #d8dce8 !important;
  /* NO overflow:hidden — that clips the folium iframe */
}

/* ── hide chrome ────────────────────────────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
footer,
#MainMenu { display: none !important; }

[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── main block: zero padding, full width ───────────────────────────────── */
.main .block-container,
[data-testid="block-container"] {
  padding: 0 0 0 0 !important;
  max-width: 100% !important;
}

/* ── sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #0d0e15 !important;
  border-right: 1px solid rgba(255,255,255,0.055) !important;
  min-width: 355px !important;
  max-width: 355px !important;
  width: 355px !important;
  /* overflow on sidebar is fine — it only clips the sidebar panel */
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
  padding: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  height: 100vh !important;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.08) transparent;
}
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.07); border-radius: 2px; }

/* sidebar streamlit elements */
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: 8px !important;
  color: #d8dce8 !important;
  font-size: 13px !important;
  padding: 9px 12px !important;
  transition: border-color .2s;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input:focus {
  border-color: rgba(240,160,64,0.5) !important;
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(240,160,64,0.08) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] label { display: none !important; }

/* sidebar button */
[data-testid="stSidebar"] [data-testid="stButton"] > button {
  background: rgba(240,160,64,0.12) !important;
  border: 1px solid rgba(240,160,64,0.3) !important;
  color: #f0a040 !important;
  border-radius: 8px !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  letter-spacing: .06em !important;
  padding: 9px 0 !important;
  transition: all .2s !important;
  width: 100% !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
  background: rgba(240,160,64,0.2) !important;
  border-color: rgba(240,160,64,0.5) !important;
}

/* sidebar slider */
[data-testid="stSidebar"] [data-testid="stSlider"] > div > div > div {
  color: #606888 !important; font-size: 12px !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {
  background: #f0a040 !important;
  border-color: #f0a040 !important;
}

/* sidebar plotly charts */
[data-testid="stSidebar"] .js-plotly-plot .plotly { background: transparent !important; }

/* ── design tokens as utility classes ───────────────────────────────────── */
/* P1: tighter padding, invisible labels, flatter radius everywhere */
.section {
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.048);
}
.section-last { padding: 14px 20px 24px; }

/* Labels: barely there — #2c2f48, not readable from across the room */
.label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .15em;
  text-transform: uppercase;
  color: #2c2f48;
  margin-bottom: 2px;
}
.label-md {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .13em;
  text-transform: uppercase;
  color: #323656;
  margin-bottom: 8px;
}

/* Hero: 36px, weight 700, always cool off-white — colour lives in badge only */
.hero-val {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -.025em;
  line-height: 1;
  color: #eef0f8;
  font-variant-numeric: tabular-nums;
}
.hero-unit {
  font-size: 11px;
  color: #2c2f48;
  letter-spacing: .07em;
  margin-top: 4px;
}

/* Flatten secondary value sizes — less jumping hierarchy */
.val-lg {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -.015em;
  color: #d4d8e8;
}
.val-md {
  font-size: 13px;
  font-weight: 600;
  color: #b8bcd0;
}
.muted { color: #404468; font-size: 11px; }
.accent { color: #f0a040; }

.divider {
  height: 1px;
  background: rgba(255,255,255,0.048);
  margin: 12px 0;
}

/* Badge: just text + colour, no border, no background */
.badge {
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
  padding: 2px 0;
}

.row { display: flex; align-items: baseline; gap: 6px; }

/* Grid-2: no rounded corners, no card backgrounds */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin-top: 10px;
}
.grid-cell { padding: 10px 0; }

/* stat-row: spacing only, no separator lines */
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

/* ── map area ───────────────────────────────────────────────────────────── */
/* Let folium iframe breathe — no overflow:hidden, no fixed height on wrapper */
[data-testid="stFolium"] > div,
.stFolium,
iframe[title="streamlit_folium.st_folium"] {
  border-radius: 0 !important;
  border: none !important;
}
.bleg-row {
  display: flex; align-items: center; gap: 7px;
  margin-bottom: 5px;
}
.bleg-row:last-child { margin-bottom: 0; }
.bleg-dot {
  width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
}
.bleg-lbl { font-size: 9.5px; color: #4a5070; }

/* area analysis card: flat, minimal border */
.area-card {
  border-left: 2px solid rgba(240,160,64,0.4);
  padding: 10px 0 10px 12px;
  margin-top: 8px;
}

/* sidebar input / button: flatten radius */
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input {
  border-radius: 3px !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button {
  border-radius: 3px !important;
}
</style>
"""

# ── html blocks ────────────────────────────────────────────────────────────────
def _sec(content, last=False):
    cls = "section-last" if last else "section"
    return f"<div class='{cls}'>{content}</div>"

def _row(label, value, colour="#d8dce8", sub=""):
    sub_html = f"<span class='muted' style='margin-left:6px'>{sub}</span>" if sub else ""
    return f"""<div class='stat-row'>
  <span class='muted'>{label}</span>
  <span style='font-size:13px;font-weight:600;color:{colour}'>{value}{sub_html}</span>
</div>"""


# ══ SESSION STATE ══════════════════════════════════════════════════════════════
def _init():
    defs = dict(lat=19.076, lon=72.878, loc_name="Mumbai",
                map_zoom=12, mode="point",
                area_bounds=None, area_coords=None,
                prev_click=None, viewport_bounds=None)
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ══ MAIN ═══════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Solar Atlas", page_icon="☀️",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    _init()

    lat  = st.session_state.lat
    lon  = st.session_state.lon
    zoom = st.session_state.map_zoom
    name = st.session_state.loc_name

    # Fetch solar for current point
    solar = fetch_solar(lat, lon)
    ghi   = solar["annual"] if solar else 0.0
    sol_lbl, sol_col, sol_tag = solar_class(ghi)

    # Buildings if zoomed in — use viewport bounds when available (stored from last rerun)
    buildings  = []
    show_bldgs = zoom >= 14
    if show_bldgs and solar:
        vp = st.session_state.get("viewport_bounds")
        if vp:
            buildings = get_buildings(vp["south"], vp["west"], vp["north"], vp["east"])
        else:
            delta     = max(0.003, 0.035 / (2 ** (zoom - 14)))
            buildings = get_buildings(lat-delta, lon-delta, lat+delta, lon+delta)

    # ══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:

        # ── brand ─────────────────────────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:18px;border-bottom:1px solid rgba(255,255,255,0.048)'>
  <div style='display:flex;align-items:center;gap:8px'>
    <span style='font-size:16px'>☀</span>
    <div>
      <div style='font-size:13px;font-weight:700;color:#c8ccd8;letter-spacing:-.01em'>
        Solar Atlas
      </div>
      <div class='label' style='margin-top:1px'>Day 02 · The Resilience Stack</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── search ────────────────────────────────────────────────────────────
        st.markdown("<div style='padding:16px 24px 0'>", unsafe_allow_html=True)
        query   = st.text_input("loc", value=name.split(",")[0], label_visibility="collapsed",
                                placeholder="Search any city…", key="city_q")
        go_btn  = st.button("→  Search", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if go_btn and query:
            with st.spinner(""):
                loc = geocode(query)
            if loc:
                st.session_state.lat      = loc["lat"]
                st.session_state.lon      = loc["lon"]
                st.session_state.loc_name = (
                    f"{loc['name']}{', '+loc['admin'] if loc['admin'] else ''}, {loc['country']}")
                st.session_state.map_zoom = 12
                st.session_state.mode     = "point"
                st.session_state.area_bounds = None
                st.session_state.area_coords = None
                st.session_state.prev_click  = None
                st.rerun()
            else:
                st.error("Not found.")
                return

        if not solar:
            st.markdown(_sec(
                "<div class='muted' style='text-align:center;padding:20px 0'>"
                "No solar data available for this location.</div>"),
                unsafe_allow_html=True)
            return

        # ── location + hero GHI ───────────────────────────────────────────────
        short_name = name.split(",")[0].strip()
        rest_name  = ", ".join(name.split(",")[1:]).strip()
        _temp_vals = [v for v in solar["temp"].values() if v is not None]
        temp_avg   = round(sum(_temp_vals)/len(_temp_vals),1) if _temp_vals else None
        best_m   = max(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
        worst_m  = min(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)

        st.markdown(_sec(f"""
<div style='margin-bottom:12px'>
  <div style='font-size:15px;font-weight:600;color:#eef0f8;letter-spacing:-.01em'>
    {short_name}
  </div>
  <div class='muted' style='margin-top:2px'>{rest_name}</div>
  <div style='font-size:9px;color:#2c2f48;margin-top:2px;letter-spacing:.04em'>
    {lat:.4f}° N &nbsp; {lon:.4f}° E
  </div>
</div>

<div class='label'>ANNUAL AVERAGE GHI</div>
<div style='display:flex;align-items:baseline;gap:8px;margin-top:5px'>
  <span class='hero-val'>{ghi:.2f}</span>
  <span class='hero-unit'>kWh / m² / day</span>
  <span class='badge' style='color:{sol_col};margin-left:4px'>{sol_lbl}</span>
</div>
<div style='font-size:10px;color:#2c2f48;margin-top:4px;font-style:italic'>{sol_tag}</div>

<div class='divider'></div>

<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:0'>
  <div>
    <div class='label'>PEAK</div>
    <div style='font-size:13px;font-weight:600;color:#d4d8e8;margin-top:3px'>
      {MONTHS[best_m-1]}
    </div>
    <div style='font-size:10px;color:#2c2f48;margin-top:1px'>{solar["ghi"].get(best_m,0):.1f} kWh</div>
  </div>
  <div>
    <div class='label'>LOW</div>
    <div style='font-size:13px;font-weight:600;color:#d4d8e8;margin-top:3px'>
      {MONTHS[worst_m-1]}
    </div>
    <div style='font-size:10px;color:#2c2f48;margin-top:1px'>{solar["ghi"].get(worst_m,0):.1f} kWh</div>
  </div>
  <div>
    <div class='label'>AVG TEMP</div>
    <div style='font-size:13px;font-weight:600;color:#d4d8e8;margin-top:3px'>
      {f"{temp_avg} °C" if temp_avg is not None else "—"}
    </div>
    <div style='font-size:10px;color:#2c2f48;margin-top:1px'>{solar.get("source","PVGIS")[:8]}</div>
  </div>
</div>
"""), unsafe_allow_html=True)

        # ── monthly irradiance chart ──────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:12px'>
  <div class='label-md'>MONTHLY IRRADIANCE — 2019–2023 avg</div>
</div>
""", unsafe_allow_html=True)
        st.sidebar.plotly_chart(chart_monthly(solar), use_container_width=True,
                                 config={"displayModeBar": False}, key="m_chart")

        # ── area analysis panel ───────────────────────────────────────────────
        if st.session_state.mode == "area" and st.session_state.area_bounds:
            ar = calc_area_solar(st.session_state.area_bounds, ghi)
            bs = st.session_state.area_bounds
            st.markdown(_sec(f"""
<div style='display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px'>
  <span class='label-md' style='color:#f0a040;margin-bottom:0'>AREA ANALYSIS</span>
  <span style='font-size:9px;color:#2c2f48'>{ar["area_km2"]} km²</span>
</div>
<div style='font-size:9px;color:#2c2f48;margin-bottom:10px'>
  {bs["south"]:.3f}°–{bs["north"]:.3f}°N · {bs["west"]:.3f}°–{bs["east"]:.3f}°E
</div>
<div class='area-card'>
  <div style='display:grid;grid-template-columns:1fr 1fr;row-gap:14px'>
    <div>
      <div class='label'>SOLAR POTENTIAL</div>
      <div class='val-lg' style='color:#f0a040;margin-top:4px'>{ar["mwh_yr"]:,}</div>
      <div style='font-size:10px;color:#2c2f48;margin-top:1px'>MWh / year</div>
    </div>
    <div>
      <div class='label'>HOMES POWERED</div>
      <div class='val-lg' style='margin-top:4px'>{ar["homes"]:,}</div>
      <div style='font-size:10px;color:#2c2f48;margin-top:1px'>at 3,500 kWh/yr</div>
    </div>
    <div>
      <div class='label'>PANELS NEEDED</div>
      <div class='val-md' style='margin-top:4px'>{ar["panels"]:,}</div>
      <div style='font-size:10px;color:#2c2f48;margin-top:1px'>{ar["rooftop_m2"]:,} m² roof</div>
    </div>
    <div>
      <div class='label'>CO₂ AVOIDED</div>
      <div class='val-md' style='margin-top:4px'>{ar["co2_kt"]} kt</div>
      <div style='font-size:10px;color:#2c2f48;margin-top:1px'>per year</div>
    </div>
  </div>
</div>
<div style='font-size:9px;color:#2c2f48;margin-top:8px'>
  20% rooftop coverage · 60% usable · click map to exit
</div>
"""), unsafe_allow_html=True)

        # ── calculator ────────────────────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:4px'>
  <div class='label-md'>PANEL CALCULATOR</div>
</div>
""", unsafe_allow_html=True)

        n_panels = st.slider(" ", min_value=1, max_value=100, value=10,
                              format="%d panels", key="n_panels",
                              label_visibility="collapsed")
        r = calc(ghi, n_panels)

        st.markdown(_sec(f"""
<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px'>
  <div>
    <span class='val-lg' style='color:#f0a040'>{r["peak_kw"]}</span>
    <span style='font-size:10px;color:#2c2f48;margin-left:4px'>kWp</span>
  </div>
  <div style='text-align:right'>
    <span class='val-md' style='color:#d4d8e8'>{r["kwh_yr"]:,}</span>
    <span style='font-size:10px;color:#2c2f48;margin-left:3px'>kWh / yr</span>
  </div>
</div>
{_row("Cost", f"${r['cost']:,}")}
{_row("Payback", f"{r['payback']} yrs", "#d4d8e8")}
{_row("CO₂ offset", f"{r['co2_trees']:,} trees / yr")}
<div class='divider'></div>
{_row("Homes powered", f"{r['homes']}×")}
{_row("Phones charged", f"{r['phones']:,} / day")}
"""), unsafe_allow_html=True)

        # ── world rank chart ──────────────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:8px'>
  <div class='label-md'>GLOBAL RANKING</div>
</div>
""", unsafe_allow_html=True)
        st.sidebar.plotly_chart(chart_rank(ghi, name), use_container_width=True,
                                 config={"displayModeBar": False}, key="rank_chart")

        # ── map hints + building legend (P3: live in sidebar, not below map) ──
        if show_bldgs and buildings:
            st.markdown(f"""
<div class='section' style='padding-top:10px;padding-bottom:10px'>
  <div class='label' style='margin-bottom:8px'>ROOFTOP SOLAR / YEAR</div>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:5px 12px'>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='width:8px;height:8px;border-radius:1px;background:#4888c8;display:inline-block;flex-shrink:0'></span>
      <span style='font-size:9.5px;color:#404468'>&lt; 2k kWh</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='width:8px;height:8px;border-radius:1px;background:#5aab78;display:inline-block;flex-shrink:0'></span>
      <span style='font-size:9.5px;color:#404468'>2–5k kWh</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='width:8px;height:8px;border-radius:1px;background:#c8b044;display:inline-block;flex-shrink:0'></span>
      <span style='font-size:9.5px;color:#404468'>5–10k kWh</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='width:8px;height:8px;border-radius:1px;background:#d4824a;display:inline-block;flex-shrink:0'></span>
      <span style='font-size:9.5px;color:#404468'>10–20k kWh</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='width:8px;height:8px;border-radius:1px;background:#f0a040;display:inline-block;flex-shrink:0'></span>
      <span style='font-size:9.5px;color:#404468'>&gt; 20k kWh</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <span style='font-size:9.5px;color:#2c2f48'>{len(buildings)} buildings</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div class='section' style='padding-top:8px;padding-bottom:8px'>
  <div style='font-size:9px;color:#2c2f48;line-height:1.7'>
    Click map to analyse any point<br>
    Draw rectangle for area potential<br>
    Zoom &ge; 14 for rooftop data
  </div>
</div>
""", unsafe_allow_html=True)

        # ── attribution ───────────────────────────────────────────────────────
        st.markdown(f"""
<div class='section-last' style='padding-top:10px'>
  <div class='label'>DATA SOURCES</div>
  <div style='font-size:10px;color:#2c2f48;margin-top:4px;line-height:1.7'>
    {solar.get("source","PVGIS EU JRC")}<br>
    OpenStreetMap · Nominatim · 2019–2023
  </div>
  <div class='label' style='margin-top:12px'>DAY 03</div>
  <div style='font-size:10px;color:#2c2f48;margin-top:3px;line-height:1.6'>
    Water Stress Index — where freshwater is running out
    and which grids fail when rivers stop flowing.
  </div>
</div>
""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN — full-screen map
    # ══════════════════════════════════════════════════════════════════════════
    m = build_map(lat, lon, zoom, ghi,
                  buildings=buildings if show_bldgs else None,
                  area_coords=st.session_state.area_coords)

    # P3: map fills the viewport — no content below it
    map_data = st_folium(m,
        returned_objects=["last_clicked", "last_active_drawing", "bounds", "zoom"],
        key="solar_map",
        height=820,
        use_container_width=True)

    # ── handle map events ──────────────────────────────────────────────────────
    if map_data:
        new_zoom = map_data.get("zoom")
        zoom_changed = new_zoom and new_zoom != st.session_state.map_zoom
        if zoom_changed:
            st.session_state.map_zoom = new_zoom

        # Store viewport bounds for accurate building fetch next rerun
        raw_bounds = map_data.get("bounds")
        if raw_bounds:
            st.session_state.viewport_bounds = {
                "south": raw_bounds["_southWest"]["lat"],
                "west":  raw_bounds["_southWest"]["lng"],
                "north": raw_bounds["_northEast"]["lat"],
                "east":  raw_bounds["_northEast"]["lng"],
            }

        # Zoom crosses 14 threshold → rerun so buildings appear immediately
        prev_zoom = zoom  # zoom was captured before map_data
        if zoom_changed and (
            (prev_zoom < 14 <= new_zoom) or (new_zoom < 14 <= prev_zoom)
        ):
            st.rerun()

        drawing = map_data.get("last_active_drawing")
        if drawing and drawing.get("geometry", {}).get("type") == "Polygon":
            coords = drawing["geometry"]["coordinates"][0]
            lats, lons = [c[1] for c in coords], [c[0] for c in coords]
            nb = {"south": min(lats), "north": max(lats),
                  "west":  min(lons), "east":  max(lons)}
            if nb != st.session_state.area_bounds:
                st.session_state.area_bounds = nb
                st.session_state.area_coords = coords
                st.session_state.mode = "area"
                st.rerun()

        click = map_data.get("last_clicked")
        if click:
            new_lat = round(click["lat"], 5)
            new_lon = round(click["lng"], 5)
            if st.session_state.prev_click != (new_lat, new_lon):
                st.session_state.prev_click  = (new_lat, new_lon)
                st.session_state.lat         = new_lat
                st.session_state.lon         = new_lon
                st.session_state.mode        = "point"
                st.session_state.area_bounds = None
                st.session_state.area_coords = None
                st.session_state.loc_name    = reverse_geocode(new_lat, new_lon)
                st.rerun()

if __name__ == "__main__":
    main()
