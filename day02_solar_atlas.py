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
    vals  = [solar["ghi"].get(m) or 0 for m in range(1,13)]
    clear = [solar["clear"].get(m) or 0 for m in range(1,13)]
    cols  = []
    for v in vals:
        if v >= 6.5:   cols.append("#f0a040")
        elif v >= 5.5: cols.append("#d4824a")
        elif v >= 4.5: cols.append("#c8b044")
        elif v >= 3.5: cols.append("#5aab78")
        else:          cols.append("#4888c8")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=MONTHS_3, y=vals, marker_color=cols, marker_opacity=0.9,
        hovertemplate="<b>%{x}</b>  %{y:.2f} kWh/m²/day<extra></extra>"))
    fig.add_trace(go.Scatter(x=MONTHS_3, y=clear, mode="lines",
        line=dict(color="rgba(255,255,255,0.15)", width=1.5, dash="dot"),
        hovertemplate="Clear-sky: %{y:.2f}<extra></extra>", showlegend=False))
    fig.update_layout(
        height=130, margin=dict(l=0,r=0,t=4,b=0), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color="#3e4260", size=9),
                   tickmode="array", tickvals=MONTHS_3),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#3e4260", size=8), showticklabels=True,
                   nticks=4),
        bargap=0.18)
    return fig

def chart_rank(my_ghi, my_name) -> go.Figure:
    data = dict(BENCHMARKS)
    short = my_name.split(",")[0].strip()
    data[short] = my_ghi
    df = pd.DataFrame({"city": list(data.keys()), "ghi": list(data.values())})
    df = df.sort_values("ghi", ascending=True)
    cols, opacities = [], []
    for _, row in df.iterrows():
        if row["city"] == short:
            cols.append("#f0a040"); opacities.append(1.0)
        else:
            _, c, _ = solar_class(row["ghi"])
            cols.append(c); opacities.append(0.55)
    labels = ["▶ " + c if c == short else c for c in df["city"].tolist()]
    fig = go.Figure(go.Bar(
        x=df["ghi"], y=labels, orientation="h",
        marker_color=cols, marker_opacity=opacities,
        hovertemplate="<b>%{y}</b>  %{x:.2f} kWh/m²/day<extra></extra>",
        text=[f"{v:.1f}" for v in df["ghi"]], textposition="outside",
        textfont=dict(color="#3e4260", size=8)))
    fig.update_layout(
        height=max(280, len(df)*20), margin=dict(l=0,r=36,t=4,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#3e4260", size=8), range=[0, 8.5]),
        yaxis=dict(showgrid=False, tickfont=dict(color="#606888", size=9)))
    my_row = df[df["city"] == short]
    if not my_row.empty:
        fig.add_annotation(x=my_row["ghi"].values[0], y="▶ " + short,
            text="  ◀ you", showarrow=False, xanchor="left",
            font=dict(color="#f0a040", size=8))
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
.section {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.048);
}
.section-last { padding: 20px 24px 28px; }
.label {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: #3e4260;
  margin-bottom: 2px;
}
.label-md {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #4a5070;
  margin-bottom: 10px;
}
.hero-val {
  font-size: 46px;
  font-weight: 800;
  letter-spacing: -.03em;
  line-height: 1;
  color: #eef0f8;
  font-variant-numeric: tabular-nums;
}
.hero-unit {
  font-size: 12px;
  color: #3e4260;
  letter-spacing: .06em;
  margin-top: 5px;
}
.val-lg {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -.02em;
  color: #d8dce8;
}
.val-md {
  font-size: 15px;
  font-weight: 600;
  color: #c8ccd8;
}
.muted { color: #4a5070; font-size: 11px; }
.accent { color: #f0a040; }
.divider {
  height: 1px;
  background: rgba(255,255,255,0.048);
  margin: 16px 0;
}
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
}
.row { display: flex; align-items: baseline; gap: 6px; }
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: rgba(255,255,255,0.04);
  border-radius: 10px;
  overflow: hidden;
  margin-top: 10px;
}
.grid-cell {
  background: #0d0e15;
  padding: 12px 14px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.stat-row:last-child { border-bottom: none; }

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

/* area analysis card (in sidebar) */
.area-card {
  background: rgba(240,160,64,0.05);
  border: 1px solid rgba(240,160,64,0.15);
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 10px;
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

def _grid_cell(label, val, col="#d8dce8"):
    return f"""<div class='grid-cell'>
  <div class='label'>{label}</div>
  <div class='val-md' style='color:{col};margin-top:4px'>{val}</div>
</div>"""

def _power_row(icon, val, label):
    return f"""<div style='display:flex;align-items:center;gap:10px;
        padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>
  <span style='font-size:14px;width:20px;text-align:center'>{icon}</span>
  <span class='muted' style='flex:1'>{label}</span>
  <span style='font-size:12px;font-weight:600;color:#c8ccd8'>{val}</span>
</div>"""

# ══ SESSION STATE ══════════════════════════════════════════════════════════════
def _init():
    defs = dict(lat=19.076, lon=72.878, loc_name="Mumbai",
                map_zoom=12, mode="point",
                area_bounds=None, area_coords=None, prev_click=None)
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

    # Buildings if zoomed in
    buildings = []
    show_bldgs = zoom >= 14
    if show_bldgs and solar:
        delta = max(0.003, 0.035 / (2 ** (zoom - 14)))
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
<div style='margin-bottom:14px'>
  <div style='font-size:17px;font-weight:700;color:#eef0f8;letter-spacing:-.02em'>
    {short_name}
  </div>
  <div class='muted' style='margin-top:2px'>{rest_name}</div>
  <div class='muted' style='margin-top:1px;font-size:10px'>{lat:.4f}°&thinsp;N &nbsp;{lon:.4f}°&thinsp;E</div>
</div>
<div style='display:flex;align-items:flex-end;justify-content:space-between'>
  <div>
    <div class='label'>ANNUAL AVERAGE GHI</div>
    <div style='display:flex;align-items:baseline;gap:6px;margin-top:4px'>
      <span class='hero-val' style='color:{sol_col}'>{ghi:.2f}</span>
      <span class='hero-unit'>kWh / m² / day</span>
    </div>
  </div>
  <span class='badge' style='background:{sol_col}18;color:{sol_col};
    border:1px solid {sol_col}40;margin-bottom:4px'>
    ● {sol_lbl}
  </span>
</div>
<div class='muted' style='margin-top:6px;font-style:italic'>{sol_tag}</div>
<div class='divider'></div>
<div style='display:flex;gap:0'>
  <div style='flex:1'>
    <div class='label'>PEAK MONTH</div>
    <div style='font-size:14px;font-weight:600;color:#f0a040;margin-top:3px'>
      {MONTHS[best_m-1]}
    </div>
    <div class='muted'>{solar["ghi"].get(best_m,0):.1f} kWh</div>
  </div>
  <div style='flex:1'>
    <div class='label'>LOW MONTH</div>
    <div style='font-size:14px;font-weight:600;color:#4888c8;margin-top:3px'>
      {MONTHS[worst_m-1]}
    </div>
    <div class='muted'>{solar["ghi"].get(worst_m,0):.1f} kWh</div>
  </div>
  <div style='flex:1'>
    <div class='label'>AVG TEMP</div>
    <div style='font-size:14px;font-weight:600;color:#5aab78;margin-top:3px'>
      {f"{temp_avg}°C" if temp_avg is not None else "—"}
    </div>
    <div class='muted'>{"panel loss" if temp_avg and temp_avg>28 else "source"}: {solar.get("source","PVGIS")[:6]}</div>
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
<div class='label-md' style='color:#f0a040'>
  📐 AREA ANALYSIS
</div>
<div class='muted' style='margin-bottom:10px'>
  {bs["south"]:.3f}°–{bs["north"]:.3f}°N &nbsp;·&nbsp; {ar["area_km2"]} km²
</div>
<div class='area-card'>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>
    <div>
      <div class='label'>SOLAR POTENTIAL</div>
      <div class='val-lg accent' style='margin-top:4px'>{ar["mwh_yr"]:,}</div>
      <div class='muted'>MWh / year</div>
    </div>
    <div>
      <div class='label'>HOMES POWERED</div>
      <div class='val-lg' style='color:#5aab78;margin-top:4px'>{ar["homes"]:,}</div>
      <div class='muted'>at 3,500 kWh/yr</div>
    </div>
    <div>
      <div class='label'>PANELS NEEDED</div>
      <div class='val-md' style='margin-top:4px'>{ar["panels"]:,}</div>
      <div class='muted'>{ar["rooftop_m2"]:,} m² roof</div>
    </div>
    <div>
      <div class='label'>CO₂ AVOIDED</div>
      <div class='val-md' style='color:#5aab78;margin-top:4px'>{ar["co2_kt"]} kt</div>
      <div class='muted'>per year</div>
    </div>
  </div>
</div>
<div class='muted' style='margin-top:8px;font-size:10px'>
  20% rooftop coverage · 60% usable · click map to exit
</div>
"""), unsafe_allow_html=True)

        # ── calculator ────────────────────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:4px'>
  <div class='label-md'>PANEL CALCULATOR</div>
</div>
""", unsafe_allow_html=True)

        with st.sidebar:
            n_panels = st.slider(" ", min_value=1, max_value=100, value=10,
                                  format="%d panels", key="n_panels",
                                  label_visibility="collapsed")
        r = calc(ghi, n_panels)

        st.markdown(_sec(f"""
<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px'>
  <div>
    <span class='val-lg' style='color:#f0a040'>{r["peak_kw"]}</span>
    <span class='muted' style='margin-left:4px'>kWp system</span>
  </div>
  <div style='text-align:right'>
    <span class='val-md' style='color:#eef0f8'>{r["kwh_yr"]:,}</span>
    <span class='muted' style='margin-left:3px'>kWh/yr</span>
  </div>
</div>
{_row("Installed cost", f"${r['cost']:,}")}
{_row("Payback period", f"{r['payback']} yrs", "#5aab78")}
{_row("CO₂ offset", f"{r['co2_trees']:,} trees/yr", "#5aab78")}
<div class='divider'></div>
{_power_row("🏠", f"{r['homes']}x", "avg homes powered")}
{_power_row("📱", f"{r['phones']:,}/day", "phones charged")}
"""), unsafe_allow_html=True)

        # ── world rank chart ──────────────────────────────────────────────────
        st.markdown("""
<div class='section' style='padding-bottom:8px'>
  <div class='label-md'>GLOBAL RANKING</div>
</div>
""", unsafe_allow_html=True)
        st.sidebar.plotly_chart(chart_rank(ghi, name), use_container_width=True,
                                 config={"displayModeBar": False}, key="rank_chart")

        # ── attribution ───────────────────────────────────────────────────────
        st.markdown(f"""
<div class='section-last' style='padding-top:12px'>
  <div class='label'>DATA SOURCES</div>
  <div class='muted' style='margin-top:4px;line-height:1.6'>
    {solar.get("source","PVGIS EU JRC")} · OpenStreetMap · Nominatim
    <br>5-year average 2019–2023
  </div>
  <div class='label' style='margin-top:12px'>DAY 03 NEXT →</div>
  <div class='muted' style='margin-top:4px;line-height:1.6'>
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

    map_data = st_folium(m,
        returned_objects=["last_clicked", "last_active_drawing", "bounds", "zoom"],
        key="solar_map",
        height=750,
        use_container_width=True)

    # Hint overlay (rendered below map in DOM but styled to look overlaid)
    if show_bldgs and buildings:
        hint = f"🏗  {len(buildings)} buildings · coloured by rooftop solar"
    else:
        hint = "Click anywhere to analyse · Draw a rectangle for area potential · Zoom ≥ 14 for rooftop data"
    st.markdown(f"""
<div style='text-align:center;padding:6px 0 0;position:relative'>
  <span style='display:inline-block;background:rgba(13,14,21,0.7);
    border:1px solid rgba(255,255,255,0.055);border-radius:5px;
    padding:5px 16px;font-size:10.5px;color:#3e4260;letter-spacing:.04em'>
    {hint}
  </span>
</div>
""", unsafe_allow_html=True)

    # Building colour legend
    if show_bldgs and buildings:
        st.markdown("""
<div style='display:flex;gap:14px;justify-content:center;padding:8px 0 0;flex-wrap:wrap'>
  <span style='color:#3e4260;font-size:9px;letter-spacing:.1em;
    text-transform:uppercase;font-weight:600;align-self:center'>Rooftop kWh/yr</span>
  <span style='display:flex;align-items:center;gap:5px'>
    <span style='width:10px;height:10px;border-radius:2px;background:#4888c8;display:inline-block'></span>
    <span style='font-size:10px;color:#3e4260'>&lt;2k</span></span>
  <span style='display:flex;align-items:center;gap:5px'>
    <span style='width:10px;height:10px;border-radius:2px;background:#5aab78;display:inline-block'></span>
    <span style='font-size:10px;color:#3e4260'>2–5k</span></span>
  <span style='display:flex;align-items:center;gap:5px'>
    <span style='width:10px;height:10px;border-radius:2px;background:#c8b044;display:inline-block'></span>
    <span style='font-size:10px;color:#3e4260'>5–10k</span></span>
  <span style='display:flex;align-items:center;gap:5px'>
    <span style='width:10px;height:10px;border-radius:2px;background:#d4824a;display:inline-block'></span>
    <span style='font-size:10px;color:#3e4260'>10–20k</span></span>
  <span style='display:flex;align-items:center;gap:5px'>
    <span style='width:10px;height:10px;border-radius:2px;background:#f0a040;display:inline-block'></span>
    <span style='font-size:10px;color:#3e4260'>&gt;20k kWh</span></span>
</div>
""", unsafe_allow_html=True)

    # ── handle map events ──────────────────────────────────────────────────────
    if map_data:
        new_zoom = map_data.get("zoom")
        if new_zoom and new_zoom != st.session_state.map_zoom:
            st.session_state.map_zoom = new_zoom

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
