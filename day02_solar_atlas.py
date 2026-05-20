"""
Day 02 — Solar Potential Atlas  (V2: Interactive Map Edition)
The Resilience Stack: 30 Days Building the Intelligence Layer for Humanity

Run:  streamlit run day02_solar_atlas.py
Data: PVGIS (EU JRC, free) → NASA POWER fallback → Open-Meteo fallback
Map:  Folium — click anywhere on earth to get solar data
      Draw a rectangle to analyse total area solar potential
      OSM building footprints coloured by rooftop potential (zoom ≥ 14)
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

PANEL_W     = 400        # watts peak per panel
PANEL_M2    = 1.7        # m² per panel
EFFICIENCY  = 0.20       # monocrystalline
PERF_RATIO  = 0.80       # system losses
CO2_G_KWH   = 450        # world avg grid CO2 intensity gCO2/kWh
COST_USD_W  = 1.0        # installed cost $/W

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

BENCHMARKS = {
    "Sahara Desert":    7.3,
    "Rajasthan, India": 6.2,
    "Dubai":            5.8,
    "Los Angeles":      5.5,
    "Mumbai":           5.2,
    "Beijing":          4.5,
    "Madrid":           5.1,
    "New York":         4.3,
    "London":           2.8,
    "Berlin":           3.1,
    "Tokyo":            4.0,
    "Sydney":           5.0,
    "São Paulo":        5.3,
    "Lagos":            5.4,
    "Nairobi":          5.7,
}

# (min_ghi, label, colour, tagline)
SOLAR_BANDS = [
    (6.5, "WORLD-CLASS", "#f59e0b", "Top 1% globally — pure solar gold"),
    (5.5, "EXCELLENT",   "#fb923c", "More sun than most of Europe gets in a year"),
    (4.5, "GOOD",        "#fbbf24", "Solar panels pay back in under 6 years here"),
    (3.5, "MODERATE",    "#a3e635", "Viable — best with storage or net metering"),
    (0.0, "LOW",         "#60a5fa", "Solar works, but needs more panels per kWh"),
]

def solar_class(ghi):
    for threshold, label, colour, tagline in SOLAR_BANDS:
        if ghi >= threshold:
            return label, colour, tagline
    return "LOW", "#60a5fa", "Solar works, but needs more panels per kWh"

# ── data fetching ──────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "ResilienceStack/1.0 (climate research; contact@resiliencestack.earth)"}

def _get_session() -> requests.Session:
    s = requests.Session()
    retry = urllib3.Retry(total=3, backoff_factor=0.5,
                          status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s

@st.cache_data(ttl=86400 * 30, show_spinner=False)
def geocode(query: str):
    try:
        r = requests.get(GEOCODE_URL,
                         params={"name": query, "count": 1, "language": "en", "format": "json"},
                         timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        loc = results[0]
        return {
            "lat":     loc["latitude"],
            "lon":     loc["longitude"],
            "name":    loc.get("name", query),
            "country": loc.get("country", ""),
            "admin":   loc.get("admin1", ""),
        }
    except Exception:
        return None

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str:
    """Best-effort reverse geocode via Nominatim (OSM)."""
    try:
        r = requests.get(NOMINATIM,
                         params={"lat": lat, "lon": lon, "format": "jsonv2"},
                         headers=HEADERS, timeout=8)
        r.raise_for_status()
        addr = r.json().get("address", {})
        city = (addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("suburb") or addr.get("county") or "")
        country = addr.get("country", "")
        return f"{city}, {country}" if city and country else f"{lat:.3f}°, {lon:.3f}°"
    except Exception:
        return f"{lat:.3f}°, {lon:.3f}°"

def _month_avg(d: dict) -> dict:
    avgs = {}
    for m in range(1, 13):
        vals = [v for k, v in d.items() if k.endswith(f"{m:02d}") and v and v > 0]
        avgs[m] = round(sum(vals) / len(vals), 3) if vals else None
    return avgs

@st.cache_data(ttl=86400 * 30, show_spinner=False)
def fetch_solar(lat: float, lon: float) -> dict | None:
    """
    3-source waterfall:
      1. PVGIS (EU JRC SARAH-3) — gold standard
      2. NASA POWER              — global fallback
      3. Open-Meteo ERA5         — last resort
    """
    sess = _get_session()

    # ── 1. PVGIS MRcalc ───────────────────────────────────────────────────────
    try:
        r = sess.get(PVGIS_URL, params={
            "lat": round(lat, 4), "lon": round(lon, 4),
            "startyear": 2019, "endyear": 2023,
            "horirrad": 1,
            "outputformat": "json",
            "browser": 0,
        }, timeout=30)
        r.raise_for_status()
        monthly_rows = r.json().get("outputs", {}).get("monthly", [])
        if monthly_rows:
            sums: dict = defaultdict(list)
            for row in monthly_rows:
                m  = int(row["month"])
                yr = int(row["year"])
                hm = row.get("H(h)_m")
                if hm and hm > 0:
                    days = monthrange(yr, m)[1]
                    sums[m].append(hm / days)
            ghi  = {m: round(sum(vs) / len(vs), 3) for m, vs in sums.items() if vs}
            clr  = {m: round(v * 1.18, 3) for m, v in ghi.items()}
            temp = {m: None for m in range(1, 13)}
            valid = [v for v in ghi.values() if v and v > 0]
            if len(valid) >= 10:
                annual = round(sum(valid) / len(valid), 3)
                return {"ghi": ghi, "clear": clr, "temp": temp,
                        "annual": annual, "source": "PVGIS · EU JRC (SARAH-3)"}
    except Exception:
        pass

    # ── 2. NASA POWER ──────────────────────────────────────────────────────────
    try:
        r = sess.get(NASA_URL, params={
            "parameters": "ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,T2M",
            "community":  "RE",
            "longitude":  round(lon, 4),
            "latitude":   round(lat, 4),
            "start": 2019, "end": 2023,
            "format": "JSON",
        }, timeout=30)
        r.raise_for_status()
        data = r.json()["properties"]["parameter"]
        ghi  = _month_avg(data["ALLSKY_SFC_SW_DWN"])
        clr  = _month_avg(data["CLRSKY_SFC_SW_DWN"])
        temp = _month_avg(data["T2M"])
        valid = [v for v in ghi.values() if v]
        if valid:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid) / len(valid), 3),
                    "source": "NASA POWER"}
    except Exception:
        pass

    # ── 3. Open-Meteo ERA5 ────────────────────────────────────────────────────
    try:
        r = sess.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "start_date": "2019-01-01", "end_date": "2023-12-31",
            "daily": "shortwave_radiation_sum", "timezone": "UTC",
        }, timeout=30)
        r.raise_for_status()
        daily = r.json().get("daily", {})
        monthly_sums: dict = defaultdict(list)
        for d, v in zip(daily.get("time", []), daily.get("shortwave_radiation_sum", [])):
            if v is not None and v >= 0:
                monthly_sums[int(d[5:7])].append(v / 3.6)
        ghi  = {m: round(sum(vs) / len(vs), 3) for m, vs in monthly_sums.items() if vs}
        clr  = {m: round(v * 1.15, 3) for m, v in ghi.items()}
        temp = {m: None for m in range(1, 13)}
        valid = list(ghi.values())
        if valid:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid) / len(valid), 3),
                    "source": "Open-Meteo (ERA5)"}
    except Exception:
        pass

    return None

# ── OSM building footprints ────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_buildings(south: float, west: float, north: float, east: float) -> list:
    """Fetch building footprints from OSM Overpass within bbox."""
    query = (
        f"[out:json][timeout:25];\n"
        f"(way[\"building\"]({south:.5f},{west:.5f},{north:.5f},{east:.5f}););\n"
        f"out geom;"
    )
    try:
        sess = _get_session()
        r = sess.post(OVERPASS_URL, data={"data": query}, timeout=30)
        r.raise_for_status()
        elements = r.json().get("elements", [])
        buildings = []
        for el in elements:
            if el.get("type") == "way" and el.get("geometry"):
                coords = [(n["lat"], n["lon"]) for n in el["geometry"]]
                if len(coords) >= 3:
                    area = _polygon_area_m2(coords)
                    if area > 10:   # ignore slivers
                        buildings.append({"coords": coords, "area_m2": round(area, 1)})
        return buildings
    except Exception:
        return []

def _polygon_area_m2(coords: list) -> float:
    """Shoelace formula with local degree→metre conversion."""
    if len(coords) < 3:
        return 0.0
    lat0 = coords[0][0]
    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(lat0))
    n = len(coords)
    area = 0.0
    for i in range(n):
        x1 = coords[i][1] * lon_m
        y1 = coords[i][0] * lat_m
        x2 = coords[(i + 1) % n][1] * lon_m
        y2 = coords[(i + 1) % n][0] * lat_m
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0

def building_solar_kwh_yr(area_m2: float, annual_ghi: float) -> float:
    """Annual solar potential for one rooftop (60% usable area)."""
    return area_m2 * 0.6 * annual_ghi * EFFICIENCY * PERF_RATIO * 365

def building_colour(kwh_yr: float) -> str:
    if kwh_yr >= 20_000: return "#f59e0b"
    if kwh_yr >= 10_000: return "#fb923c"
    if kwh_yr >=  5_000: return "#fbbf24"
    if kwh_yr >=  2_000: return "#a3e635"
    return "#60a5fa"

def calc_area_solar(bounds: dict, annual_ghi: float) -> dict:
    """Solar potential for a drawn rectangle. 20% rooftop coverage assumed."""
    south, north = bounds["south"], bounds["north"]
    west,  east  = bounds["west"],  bounds["east"]
    lat_m   = 111_320.0
    lon_m   = 111_320.0 * math.cos(math.radians((south + north) / 2))
    area_m2 = abs(east - west) * lon_m * abs(north - south) * lat_m
    rooftop = area_m2 * 0.20 * 0.60
    kwh_yr  = rooftop * annual_ghi * EFFICIENCY * PERF_RATIO * 365
    return {
        "area_km2":   round(area_m2 / 1_000_000, 3),
        "area_ha":    round(area_m2 / 10_000, 1),
        "rooftop_m2": round(rooftop),
        "mwh_yr":     round(kwh_yr / 1000),
        "kwh_yr":     round(kwh_yr),
        "homes":      round(kwh_yr / 3500),
        "panels":     int(rooftop / PANEL_M2),
        "co2_kt":     round(kwh_yr * CO2_G_KWH / 1_000_000, 1),
    }

# ── map builder ────────────────────────────────────────────────────────────────
def build_folium_map(lat: float, lon: float, zoom: int, annual_ghi: float,
                     buildings: list | None = None,
                     area_coords: list | None = None) -> folium.Map:
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    # Rectangle-only draw tool
    Draw(
        export=False,
        draw_options={
            "rectangle": {"shapeOptions": {"color": "#f59e0b", "weight": 2,
                                           "fillOpacity": 0.08}},
            "polygon":      False,
            "polyline":     False,
            "circle":       False,
            "marker":       False,
            "circlemarker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(m)

    LocateControl(auto_start=False).add_to(m)

    _, sol_colour, _ = solar_class(annual_ghi)

    # Selected-point marker (glowing dot)
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f"""
            <div style="
              width:18px;height:18px;border-radius:50%;
              background:{sol_colour};
              border:2.5px solid rgba(255,255,255,0.85);
              box-shadow:0 0 14px {sol_colour},0 0 30px {sol_colour}55;
            "></div>""",
            icon_size=(18, 18),
            icon_anchor=(9, 9),
        ),
        popup=folium.Popup(
            f'<div style="font-family:Inter,sans-serif;padding:4px 6px">'
            f'<b style="font-size:14px;color:#1a1a1a">{annual_ghi:.2f} kWh/m²/day</b><br>'
            f'<span style="color:#555;font-size:11px">{lat:.4f}°, {lon:.4f}°</span>'
            f'</div>',
            max_width=190,
        ),
        tooltip=f"☀ {annual_ghi:.2f} kWh/m²/day  ·  click elsewhere to re-analyse",
    ).add_to(m)

    # Building footprints (zoom ≥ 14)
    if buildings:
        for b in buildings[:300]:
            kwh = building_solar_kwh_yr(b["area_m2"], annual_ghi)
            c   = building_colour(kwh)
            folium.Polygon(
                locations=b["coords"],
                color=c, weight=1,
                fill=True, fill_color=c, fill_opacity=0.62,
                tooltip=(
                    f"<b style='font-family:Inter'>{int(kwh):,} kWh/yr</b>"
                    f"<br><span style='font-size:10px'>{int(b['area_m2'])} m² footprint</span>"
                ),
            ).add_to(m)

    # Drawn rectangle overlay
    if area_coords:
        pts = [(c[1], c[0]) for c in area_coords]  # [lon,lat] → [lat,lon]
        folium.Polygon(
            locations=pts,
            color="#f59e0b", weight=2.5, dash_array="8 5",
            fill=True, fill_color="#f59e0b", fill_opacity=0.10,
        ).add_to(m)

    return m

# ── calculations ───────────────────────────────────────────────────────────────
def calc(annual_ghi: float, n_panels: int) -> dict:
    area         = n_panels * PANEL_M2
    kwh_per_day  = annual_ghi * area * EFFICIENCY * PERF_RATIO
    kwh_per_year = kwh_per_day * 365
    peak_kw      = n_panels * PANEL_W / 1000
    co2_kg       = kwh_per_year * CO2_G_KWH / 1000
    cost_usd     = peak_kw * 1000 * COST_USD_W
    return {
        "kwh_per_year":   round(kwh_per_year),
        "kwh_per_day":    round(kwh_per_day, 1),
        "peak_kw":        round(peak_kw, 1),
        "homes":          round(kwh_per_year / 3500, 1),
        "phones_per_day": int(kwh_per_day * 1000 / 12),
        "bulb_years":     round(kwh_per_year / (0.06 * 365), 0),
        "co2_kg":         round(co2_kg),
        "co2_trees":      round(co2_kg / 21),
        "cost_usd":       round(cost_usd),
        "payback_yrs":    round(cost_usd / (kwh_per_year * 0.12), 1) if kwh_per_year > 0 else None,
    }

# ── charts ─────────────────────────────────────────────────────────────────────
def make_monthly_chart(solar_data: dict, location_name: str) -> go.Figure:
    ghi_vals   = [solar_data["ghi"].get(m) or 0 for m in range(1, 13)]
    clear_vals = [solar_data["clear"].get(m) or 0 for m in range(1, 13)]
    colours = []
    for v in ghi_vals:
        if v >= 6.5:   colours.append("#f59e0b")
        elif v >= 5.5: colours.append("#fb923c")
        elif v >= 4.5: colours.append("#fbbf24")
        elif v >= 3.5: colours.append("#a3e635")
        else:          colours.append("#60a5fa")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=MONTHS, y=ghi_vals, name="Actual (all-sky)",
                         marker_color=colours,
                         hovertemplate="<b>%{x}</b><br>%{y:.2f} kWh/m²/day<extra></extra>"))
    fig.add_trace(go.Scatter(x=MONTHS, y=clear_vals, name="Clear-sky max",
                             line=dict(color="rgba(255,255,255,0.2)", width=1.5, dash="dot"),
                             hovertemplate="<b>%{x}</b> clear-sky: %{y:.2f}<extra></extra>",
                             mode="lines"))
    fig.update_layout(
        height=240, margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b", size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#64748b", size=10), ticksuffix=" kWh",
                   title=dict(text="kWh/m²/day", font=dict(color="#475569", size=10))),
        legend=dict(font=dict(color="#64748b", size=10), bgcolor="rgba(0,0,0,0)",
                    orientation="h", y=1.15),
        bargap=0.25,
    )
    return fig

def make_comparison_chart(my_ghi: float, my_name: str) -> go.Figure:
    data = dict(BENCHMARKS)
    data[my_name] = my_ghi
    df = pd.DataFrame({"city": list(data.keys()), "ghi": list(data.values())})
    df = df.sort_values("ghi", ascending=True)
    colours = []
    for _, row in df.iterrows():
        if row["city"] == my_name:
            colours.append("#ffffff")
        else:
            _, c, _ = solar_class(row["ghi"])
            colours.append(c)
    labels = ["▶ " + c if c == my_name else c for c in df["city"].tolist()]
    fig = go.Figure(go.Bar(
        x=df["ghi"], y=labels, orientation="h",
        marker_color=colours,
        hovertemplate="<b>%{y}</b><br>%{x:.2f} kWh/m²/day<extra></extra>",
        text=[f"{v:.1f}" for v in df["ghi"]], textposition="outside",
        textfont=dict(color="#64748b", size=9),
    ))
    fig.update_layout(
        height=max(320, len(df) * 22), margin=dict(l=0, r=40, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#64748b", size=9), ticksuffix=" kWh"),
        yaxis=dict(showgrid=False, tickfont=dict(color="#64748b", size=10)),
    )
    my_row = df[df["city"] == my_name]
    if not my_row.empty:
        fig.add_annotation(
            x=my_row["ghi"].values[0], y="▶ " + my_name,
            text=" ← you", showarrow=False, xanchor="left",
            font=dict(color="#ffffff", size=9), xshift=4,
        )
    return fig

def make_generation_chart(solar_data: dict, n_panels: int) -> go.Figure:
    ghi_vals    = [solar_data["ghi"].get(m) or 0 for m in range(1, 13)]
    area        = n_panels * PANEL_M2
    monthly_kwh = [round(v * area * EFFICIENCY * PERF_RATIO * 30) for v in ghi_vals]
    fig = go.Figure(go.Bar(
        x=MONTHS, y=monthly_kwh,
        marker_color="#f59e0b", marker_opacity=0.85,
        hovertemplate="<b>%{x}</b><br>%{y:,} kWh generated<extra></extra>",
    ))
    fig.update_layout(
        height=180, margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b", size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#64748b", size=10), ticksuffix=" kWh"),
        bargap=0.25,
    )
    return fig

# ── html helpers ───────────────────────────────────────────────────────────────
def stat_chip(label, value, sub, colour="#f1f5f9"):
    return f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:16px;padding:14px 18px;flex:1;min-width:110px'>
  <div style='color:#475569;font-size:.65rem;text-transform:uppercase;
              letter-spacing:.1em;font-weight:600'>{label}</div>
  <div style='color:{colour};font-size:1.3rem;font-weight:800;margin-top:3px'>{value}</div>
  <div style='color:#334155;font-size:.68rem;margin-top:2px'>{sub}</div>
</div>"""

def power_item(icon, label, value, sub):
    return f"""
<div style='display:flex;align-items:center;gap:12px;padding:10px 14px;
            background:rgba(255,255,255,0.025);border-radius:12px;margin-bottom:6px'>
  <span style='font-size:1.5rem'>{icon}</span>
  <div style='flex:1'>
    <div style='color:#94a3b8;font-size:.82rem'>{label}</div>
    <div style='color:#334155;font-size:.7rem'>{sub}</div>
  </div>
  <div style='color:#f1f5f9;font-weight:700;font-size:.95rem'>{value}</div>
</div>"""

# ══ CSS ════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,*::before,*::after{box-sizing:border-box}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="block-container"]{
  background:#05050a!important;font-family:'Inter',system-ui,sans-serif!important;color:#e2e8f0!important}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"]{background:#080810!important}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer{display:none!important}

[data-testid="metric-container"]{
  background:rgba(255,255,255,0.03)!important;backdrop-filter:blur(16px)!important;
  border:1px solid rgba(255,255,255,0.07)!important;border-radius:18px!important;
  padding:20px 22px!important}
[data-testid="stMetricLabel"]>div{color:#64748b!important;font-size:.72rem!important;
  letter-spacing:.1em;text-transform:uppercase;font-weight:600}
[data-testid="stMetricValue"]>div{color:#f1f5f9!important;font-size:1.75rem!important;font-weight:800}
[data-testid="stMetricDelta"]>div{font-size:.8rem!important}

[data-testid="stTabs"] [data-baseweb="tab-list"]{
  background:rgba(255,255,255,0.025)!important;border-radius:12px!important;
  padding:4px!important;gap:2px!important;border:1px solid rgba(255,255,255,0.05)!important}
[data-testid="stTabs"] [data-baseweb="tab"]{
  background:transparent!important;border-radius:9px!important;color:#475569!important;
  font-size:.82rem!important;font-weight:600;padding:8px 16px!important;transition:all .2s!important}
[data-testid="stTabs"] [aria-selected="true"]{
  background:rgba(255,255,255,0.07)!important;color:#f1f5f9!important}

[data-testid="stTextInput"]>div>div>input{
  background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.08)!important;
  border-radius:12px!important;color:#e2e8f0!important;font-size:1rem!important}
[data-testid="stSlider"] [data-baseweb="slider"]{padding:0!important}
hr{border-color:rgba(255,255,255,0.05)!important;margin:24px 0!important}

.glass{background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.07);
  border-radius:24px;padding:24px 28px;transition:border-color .25s,box-shadow .25s}
.glass:hover{border-color:rgba(255,255,255,0.11);box-shadow:0 8px 40px rgba(0,0,0,0.4)}
.glass-sm{background:rgba(255,255,255,0.025);backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,0.06);border-radius:18px;padding:18px 22px}
.fade-in{animation:fadeIn .35s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.gradient-text{background:linear-gradient(135deg,#fbbf24 0%,#f97316 60%,#f1f5f9 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 13px;
  border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}

/* Folium map card */
.map-wrap{border-radius:20px;overflow:hidden;
  border:1px solid rgba(255,255,255,0.07);
  box-shadow:0 4px 40px rgba(0,0,0,0.5)}
.map-hint{color:#475569;font-size:.76rem;text-align:center;padding:8px 0 2px;
  letter-spacing:.02em}

/* Building legend */
.bleg{display:flex;gap:10px;flex-wrap:wrap;align-items:center;
  padding:10px 16px;background:rgba(255,255,255,0.025);
  border-radius:12px;border:1px solid rgba(255,255,255,0.05)}
.bleg-dot{width:12px;height:12px;border-radius:3px;flex-shrink:0}
.bleg-lbl{color:#64748b;font-size:.72rem}
</style>
"""

# ══ SESSION STATE ══════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "lat":         19.0760,
        "lon":         72.8777,
        "loc_name":    "Mumbai",
        "map_zoom":    12,
        "mode":        "point",   # "point" | "area"
        "area_bounds": None,
        "area_coords": None,      # [[lon,lat], ...] from GeoJSON
        "prev_click":  None,      # (lat,lon) to detect changes
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ══ MAIN ═══════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Solar Atlas · Day 02", page_icon="☀️",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)
    _init_state()

    # ── header ────────────────────────────────────────────────────────────────
    st.markdown("""
<div style='padding:28px 0 16px'>
  <div style='font-size:.72rem;color:#475569;letter-spacing:.15em;text-transform:uppercase;
              font-weight:600;margin-bottom:6px'>Day 02 · The Resilience Stack</div>
  <h1 class='gradient-text' style='font-size:2.6rem;font-weight:900;margin:0;line-height:1.1'>
    Solar Potential Atlas
  </h1>
  <p style='color:#475569;margin:8px 0 0;font-size:.92rem;max-width:600px'>
    Click anywhere on earth to see how much sun it gets.
    Draw a rectangle to measure an area's solar potential.
    Zoom in to see individual rooftops coloured by what they could generate.
  </p>
</div>
""", unsafe_allow_html=True)

    # ── search bar ────────────────────────────────────────────────────────────
    params = st.query_params
    default_q = params.get("q", "Mumbai")

    col_s, col_b = st.columns([4, 1], gap="small")
    with col_s:
        query = st.text_input("", value=default_q,
                              placeholder="Search any city — Lagos, Oslo, Dubai, São Paulo…",
                              label_visibility="collapsed", key="city_input")
    with col_b:
        search_btn = st.button("☀️ Explore", use_container_width=True, type="primary")

    if search_btn and query:
        st.query_params["q"] = query
        with st.spinner("Locating…"):
            loc = geocode(query)
        if loc:
            st.session_state.lat      = loc["lat"]
            st.session_state.lon      = loc["lon"]
            st.session_state.loc_name = f"{loc['name']}{', ' + loc['admin'] if loc['admin'] else ''}, {loc['country']}"
            st.session_state.map_zoom = 12
            st.session_state.mode     = "point"
            st.session_state.area_bounds = None
            st.session_state.area_coords = None
            st.session_state.prev_click  = None
            st.rerun()
        else:
            st.error("Location not found. Try a major city name.")
            return

    # ── fetch solar for current point ─────────────────────────────────────────
    lat  = st.session_state.lat
    lon  = st.session_state.lon
    zoom = st.session_state.map_zoom

    with st.spinner(f"Fetching solar data…"):
        solar = fetch_solar(lat, lon)

    if not solar or not solar.get("annual"):
        st.error("Could not fetch solar data for this location. Try another.")
        return

    annual_ghi    = solar["annual"]
    sol_label, sol_colour, sol_tagline = solar_class(annual_ghi)

    # ── building footprints (zoom ≥ 14) ───────────────────────────────────────
    buildings = []
    show_buildings = zoom >= 14
    if show_buildings:
        delta = max(0.003, 0.035 / (2 ** (zoom - 14)))   # shrinks as you zoom in
        with st.spinner("Loading building footprints…"):
            buildings = get_buildings(lat - delta, lon - delta,
                                      lat + delta, lon + delta)

    # ── map ───────────────────────────────────────────────────────────────────
    m = build_folium_map(lat, lon, zoom, annual_ghi,
                         buildings=buildings if show_buildings else None,
                         area_coords=st.session_state.area_coords)

    # Map hint
    if show_buildings and buildings:
        hint = f"🏗 {len(buildings)} buildings loaded · coloured by rooftop solar potential"
    elif show_buildings:
        hint = "Zoom in more or pan to a built-up area to load building footprints"
    else:
        hint = "🖱 Click anywhere to analyse solar  ·  📐 Draw a rectangle for area analysis  ·  Zoom ≥ 14 for building footprints"

    st.markdown(f"<p class='map-hint'>{hint}</p>", unsafe_allow_html=True)

    st.markdown("<div class='map-wrap'>", unsafe_allow_html=True)
    map_data = st_folium(
        m,
        returned_objects=["last_clicked", "last_active_drawing", "bounds", "zoom"],
        key="solar_map",
        height=540,
        use_container_width=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ── handle map events ─────────────────────────────────────────────────────
    if map_data:
        # Track zoom (no rerun needed — just update for next render)
        new_zoom = map_data.get("zoom")
        if new_zoom and new_zoom != st.session_state.map_zoom:
            st.session_state.map_zoom = new_zoom

        # Drawn rectangle → area mode
        drawing = map_data.get("last_active_drawing")
        if drawing and drawing.get("geometry", {}).get("type") == "Polygon":
            coords = drawing["geometry"]["coordinates"][0]  # [[lon,lat],...]
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            new_bounds = {
                "south": min(lats), "north": max(lats),
                "west":  min(lons), "east":  max(lons),
            }
            if new_bounds != st.session_state.area_bounds:
                st.session_state.area_bounds = new_bounds
                st.session_state.area_coords = coords
                st.session_state.mode = "area"
                st.rerun()

        # Map click → re-analyse new point
        click = map_data.get("last_clicked")
        if click:
            new_lat = round(click["lat"], 5)
            new_lon = round(click["lng"], 5)
            prev = st.session_state.prev_click
            if prev != (new_lat, new_lon):
                st.session_state.prev_click  = (new_lat, new_lon)
                st.session_state.lat         = new_lat
                st.session_state.lon         = new_lon
                st.session_state.mode        = "point"
                st.session_state.area_bounds = None
                st.session_state.area_coords = None
                # Reverse geocode in background for a nicer name
                st.session_state.loc_name = reverse_geocode(new_lat, new_lon)
                st.rerun()

    # ── building legend ───────────────────────────────────────────────────────
    if show_buildings and buildings:
        st.markdown("""
<div class='bleg'>
  <span style='color:#64748b;font-size:.72rem;font-weight:600;text-transform:uppercase;
               letter-spacing:.08em'>Rooftop solar / yr</span>
  <span class='bleg-dot' style='background:#60a5fa'></span><span class='bleg-lbl'>&lt; 2k kWh</span>
  <span class='bleg-dot' style='background:#a3e635'></span><span class='bleg-lbl'>2–5k</span>
  <span class='bleg-dot' style='background:#fbbf24'></span><span class='bleg-lbl'>5–10k</span>
  <span class='bleg-dot' style='background:#fb923c'></span><span class='bleg-lbl'>10–20k</span>
  <span class='bleg-dot' style='background:#f59e0b'></span><span class='bleg-lbl'>&gt; 20k kWh</span>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── AREA MODE: solar potential panel ─────────────────────────────────────
    if st.session_state.mode == "area" and st.session_state.area_bounds:
        area = calc_area_solar(st.session_state.area_bounds, annual_ghi)
        bs   = st.session_state.area_bounds
        st.markdown(f"""
<div class='glass fade-in' style='border-color:rgba(245,158,11,0.25);
     box-shadow:0 0 40px rgba(245,158,11,0.06);margin-bottom:16px'>
  <div style='display:flex;align-items:center;gap:10px;margin-bottom:16px'>
    <span style='font-size:1.3rem'>📐</span>
    <div>
      <div style='font-size:.72rem;color:#f59e0b;text-transform:uppercase;
                  letter-spacing:.1em;font-weight:700'>Area Solar Analysis</div>
      <div style='color:#64748b;font-size:.8rem;margin-top:2px'>
        {bs["south"]:.3f}°–{bs["north"]:.3f}°N · {bs["west"]:.3f}°–{bs["east"]:.3f}°E
      </div>
    </div>
    <div style='margin-left:auto'>
      <span class='badge' style='background:rgba(245,158,11,0.1);color:#f59e0b;
            border:1px solid rgba(245,158,11,0.3)'>{area["area_km2"]} km²</span>
    </div>
  </div>
  <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px'>
    <div style='background:rgba(255,255,255,0.025);border-radius:14px;padding:14px;text-align:center'>
      <div style='color:#f59e0b;font-size:1.6rem;font-weight:800'>{area["mwh_yr"]:,}</div>
      <div style='color:#64748b;font-size:.7rem;margin-top:3px'>MWh / year</div>
      <div style='color:#334155;font-size:.65rem'>total rooftop potential</div>
    </div>
    <div style='background:rgba(255,255,255,0.025);border-radius:14px;padding:14px;text-align:center'>
      <div style='color:#4ade80;font-size:1.6rem;font-weight:800'>{area["homes"]:,}</div>
      <div style='color:#64748b;font-size:.7rem;margin-top:3px'>homes powered</div>
      <div style='color:#334155;font-size:.65rem'>at 3,500 kWh/yr avg</div>
    </div>
    <div style='background:rgba(255,255,255,0.025);border-radius:14px;padding:14px;text-align:center'>
      <div style='color:#60a5fa;font-size:1.6rem;font-weight:800'>{area["panels"]:,}</div>
      <div style='color:#64748b;font-size:.7rem;margin-top:3px'>panels needed</div>
      <div style='color:#334155;font-size:.65rem'>{area["rooftop_m2"]:,} m² usable roof</div>
    </div>
    <div style='background:rgba(255,255,255,0.025);border-radius:14px;padding:14px;text-align:center'>
      <div style='color:#f97316;font-size:1.6rem;font-weight:800'>{area["co2_kt"]}</div>
      <div style='color:#64748b;font-size:.7rem;margin-top:3px'>kt CO₂ / year</div>
      <div style='color:#334155;font-size:.65rem'>avoided vs grid average</div>
    </div>
  </div>
  <div style='margin-top:12px;padding:10px 14px;background:rgba(245,158,11,0.06);
              border-radius:12px;border:1px solid rgba(245,158,11,0.15)'>
    <span style='color:#94a3b8;font-size:.78rem'>
      Assumes <b style="color:#64748b">20% rooftop coverage</b> of total area,
      <b style="color:#64748b">60% usable</b> per rooftop.
      Click on the map to exit area mode.
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── spotlight row (point data) ─────────────────────────────────────────────
    loc_name = st.session_state.loc_name
    best_month  = max(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
    worst_month = min(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
    best_val    = solar["ghi"].get(best_month) or 0
    worst_val   = solar["ghi"].get(worst_month) or 0
    _temp_vals  = [v for v in solar["temp"].values() if v is not None]
    temp_avg    = round(sum(_temp_vals) / len(_temp_vals), 1) if _temp_vals else None
    temp_penalty = max(0, (temp_avg - 25) * 0.4) if temp_avg is not None else 0

    spot_col, chart_col = st.columns([1, 1.8], gap="large")

    with spot_col:
        st.markdown(f"""
<div class='glass fade-in' style='box-shadow:0 0 60px rgba(251,191,36,0.06)'>
  <div style='display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px'>
    <div>
      <div style='font-size:1.3rem;font-weight:800;color:#f1f5f9'>{loc_name.split(",")[0]}</div>
      <div style='color:#475569;font-size:.8rem;margin-top:2px'>{", ".join(loc_name.split(",")[1:]).strip()}</div>
      <div style='color:#334155;font-size:.7rem;margin-top:1px'>{lat:.3f}°, {lon:.3f}°</div>
    </div>
    <span class='badge' style='background:rgba(251,191,36,0.1);color:{sol_colour};
          border:1px solid {sol_colour}50;margin-top:4px'>
      ☀ {sol_label}
    </span>
  </div>

  <div style='text-align:center;padding:18px 0 14px'>
    <div style='font-size:3.6rem;font-weight:900;color:{sol_colour};line-height:1'>{annual_ghi:.2f}</div>
    <div style='color:#64748b;font-size:.78rem;margin-top:4px'>kWh / m² / day  ·  annual average</div>
    <div style='color:#475569;font-size:.76rem;margin-top:6px;font-style:italic;
                max-width:200px;margin-left:auto;margin-right:auto'>{sol_tagline}</div>
  </div>

  <div style='display:flex;gap:8px;margin-top:4px'>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.63rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Best</div>
      <div style='color:#fbbf24;font-weight:700;margin-top:3px'>{MONTHS[best_month-1]}</div>
      <div style='color:#64748b;font-size:.72rem'>{best_val:.1f} kWh</div>
    </div>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.63rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Low</div>
      <div style='color:#60a5fa;font-weight:700;margin-top:3px'>{MONTHS[worst_month-1]}</div>
      <div style='color:#64748b;font-size:.72rem'>{worst_val:.1f} kWh</div>
    </div>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.63rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Temp</div>
      <div style='color:#f97316;font-weight:700;margin-top:3px'>{f"{temp_avg}°C" if temp_avg is not None else "—"}</div>
      <div style='color:#64748b;font-size:.72rem'>
        {"−"+str(round(temp_penalty,1))+"% eff" if temp_penalty > 0.5 else "n/a" if temp_avg is None else "ideal"}
      </div>
    </div>
  </div>

  <div style='margin-top:10px;text-align:center'>
    <span style='color:#334155;font-size:.68rem'>
      Source: {solar.get("source","PVGIS")}
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

    with chart_col:
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='color:#64748b;font-size:.73rem;margin-bottom:4px;"
            f"text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
            f"Monthly solar irradiance — 5-year avg (2019–2023)</p>",
            unsafe_allow_html=True)
        st.plotly_chart(make_monthly_chart(solar, loc_name),
                        use_container_width=True, key="monthly_chart")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── calculator ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
  <span style='color:#334155;font-size:.72rem;text-transform:uppercase;
               letter-spacing:.12em;font-weight:600'>Solar calculator</span>
  <span style='color:#475569;font-size:.8rem'>— drag to size your installation</span>
</div>""", unsafe_allow_html=True)

    calc_col, result_col = st.columns([1, 1.6], gap="large")

    with calc_col:
        st.markdown("<div class='glass-sm'>", unsafe_allow_html=True)
        n_panels = st.slider("Number of panels", min_value=1, max_value=100, value=10,
                             help="Standard 400W panels, 1.7m² each")
        res = calc(annual_ghi, n_panels)
        st.markdown(f"""
<div style='margin-top:12px'>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>System size</span>
    <span style='color:#f1f5f9;font-weight:600'>{res["peak_kw"]} kWp</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Annual generation</span>
    <span style='color:#fbbf24;font-weight:700'>{res["kwh_per_year"]:,} kWh</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Daily average</span>
    <span style='color:#f1f5f9;font-weight:600'>{res["kwh_per_day"]} kWh/day</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Installed cost</span>
    <span style='color:#f1f5f9;font-weight:600'>${res["cost_usd"]:,}</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0'>
    <span style='color:#64748b;font-size:.82rem'>Payback period</span>
    <span style='color:#4ade80;font-weight:700'>{res["payback_yrs"]} yrs</span>
  </div>
</div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with result_col:
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;font-size:.73rem;margin-bottom:12px;"
                    "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                    "What your panels replace</p>", unsafe_allow_html=True)
        st.markdown(
            power_item("🏠", "Homes powered (avg)",   f"{res['homes']}",           "at 3,500 kWh/yr per household") +
            power_item("📱", "Phones charged per day", f"{res['phones_per_day']:,}", "based on 12 Wh per full charge") +
            power_item("🌳", "Trees worth of CO₂/yr", f"{res['co2_trees']:,}",      f"{res['co2_kg']:,} kg CO₂ avoided/yr") +
            power_item("💡", "LED bulb-years",         f"{int(res['bulb_years']):,}", "10W bulb, 6 hours/day"),
            unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;font-size:.7rem;margin:12px 0 4px;"
                    "text-transform:uppercase;letter-spacing:.08em'>Monthly output</p>",
                    unsafe_allow_html=True)
        st.plotly_chart(make_generation_chart(solar, n_panels),
                        use_container_width=True, key="gen_chart")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── comparison chart ───────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    display_short = loc_name.split(",")[0].strip()
    better = [(k, v) for k, v in BENCHMARKS.items() if v < annual_ghi]
    worse  = [(k, v) for k, v in BENCHMARKS.items() if v >= annual_ghi]
    lower_txt  = (f"Better than {max(better, key=lambda x: x[1])[0]}"
                  if better else "Among the sunniest on earth")
    higher_txt = (f"Less sun than {min(worse, key=lambda x: x[1])[0]}"
                  if worse  else "Top of global solar rankings")

    st.markdown("<div class='glass'>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#64748b;font-size:.73rem;margin-bottom:8px;"
                f"text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                f"{display_short} vs the world</p>", unsafe_allow_html=True)
    st.markdown(f"""
<div style='display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap'>
  <span style='color:#4ade80;font-size:.8rem;background:rgba(74,222,128,0.08);
               padding:4px 12px;border-radius:999px'>✓ {lower_txt}</span>
  <span style='color:#94a3b8;font-size:.8rem;background:rgba(255,255,255,0.04);
               padding:4px 12px;border-radius:999px'>→ {higher_txt}</span>
</div>""", unsafe_allow_html=True)
    st.plotly_chart(make_comparison_chart(annual_ghi, display_short),
                    use_container_width=True, key="compare_chart")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
<div class='glass' style='border-color:rgba(255,255,255,0.04)'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;
              flex-wrap:wrap;gap:16px'>
    <div style='flex:2;min-width:260px'>
      <p style='color:#475569;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
                font-weight:600;margin:0 0 8px'>The uncomfortable truth about solar</p>
      <p style='color:#94a3b8;margin:0;line-height:1.7;font-size:.88rem'>
        The sunniest places on earth — the Sahel, South Asia, the Middle East —
        are exactly where grid stress is highest and energy access lowest.
        The resource and the need are perfectly aligned.
        The only thing missing is the capital to build it.
        <strong style='color:#64748b'>That's a financial problem, not a technical one.</strong>
      </p>
    </div>
    <div style='flex:1;min-width:200px;padding:16px 20px;background:rgba(255,255,255,0.025);
                border-radius:16px;border:1px solid rgba(255,255,255,0.06)'>
      <div style='color:#334155;font-size:.72rem;text-transform:uppercase;
                  letter-spacing:.1em;font-weight:600'>Next</div>
      <div style='color:#f1f5f9;font-weight:700;font-size:1rem;margin:6px 0 4px'>Day 03 →</div>
      <div style='color:#64748b;font-size:.82rem'>
        Water Stress Index — where freshwater is already running out,
        and which grids will fail first when rivers stop flowing.
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
