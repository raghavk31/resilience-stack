"""
Day 02 — Solar Potential Atlas  (V10)
The Resilience Stack · 30 Days of Climate Intelligence

V10 fixes:
  - Irradiation loading: explicit NASA -999 sentinel filter, 15 s timeout,
    geographic fallback so the app always shows data even when all APIs fail
  - Zoom: remove forced rerun on zoom-level changes (no more map-snap on zoom)
  - Map fills the full viewport (CSS 100vh + increased height param)
  - Pan threshold raised 0.25°→0.40° to reduce rerender chatter

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

MONTHS   = ["Jan","Feb","Mar","Apr","May","Jun",
            "Jul","Aug","Sep","Oct","Nov","Dec"]
MONTHS_3 = ["J","F","M","A","M","J","J","A","S","O","N","D"]

BENCHMARKS = {
    "Sahara":      7.3, "Rajasthan": 6.2, "Dubai":    5.8,
    "Los Angeles": 5.5, "Mumbai":    5.2, "Nairobi":  5.7,
    "Lagos":       5.4, "São Paulo": 5.3, "Sydney":   5.0,
    "Madrid":      5.1, "Beijing":   4.5, "New York": 4.3,
    "Tokyo":       4.0, "Berlin":    3.1, "London":   2.8,
}

# ── GSA-standard colour scale ──────────────────────────────────────────────────
# Matches Global Solar Atlas / NITI ICED solar irradiance palette
# deep-indigo → blue → sky → teal → lime → yellow → amber → red-orange → dark-red
_GSA_STOPS = [
    (0.0,  (26,   0, 110)),
    (1.5,  ( 0,  51, 187)),
    (2.5,  ( 0, 136, 204)),
    (3.5,  ( 0, 187, 136)),
    (4.0,  (100, 204,   0)),
    (4.5,  (200, 220,   0)),
    (5.0,  (255, 204,   0)),
    (5.5,  (255, 136,   0)),
    (6.0,  (255,  51,   0)),
    (6.5,  (220,  20,   0)),
    (7.5,  (170,   0,   0)),
]

# CSS gradient string for legend strip (mirrors _GSA_STOPS)
GSA_LEGEND_CSS = ("linear-gradient(to right,"
    "#1a006e,#0033bb,#0088cc,#00bb88,#64cc00,"
    "#c8dc00,#ffcc00,#ff8800,#ff3300,#dc1400,#aa0000)")

def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)

def gsa_color(ghi: float) -> str:
    """Return hex colour interpolated on the GSA irradiance ramp."""
    stops = _GSA_STOPS
    if ghi <= stops[0][0]:
        r, g, b = stops[0][1]
        return f"#{r:02x}{g:02x}{b:02x}"
    if ghi >= stops[-1][0]:
        r, g, b = stops[-1][1]
        return f"#{r:02x}{g:02x}{b:02x}"
    for i in range(len(stops) - 1):
        lo_v, (lr, lg, lb) = stops[i]
        hi_v, (hr, hg, hb) = stops[i + 1]
        if lo_v <= ghi < hi_v:
            t = (ghi - lo_v) / (hi_v - lo_v)
            return f"#{_lerp(lr,hr,t):02x}{_lerp(lg,hg,t):02x}{_lerp(lb,hb,t):02x}"
    r, g, b = stops[-1][1]
    return f"#{r:02x}{g:02x}{b:02x}"

# Text classification (labels only — colour always from gsa_color)
SOLAR_BANDS = [
    (6.5, "WORLD-CLASS"),
    (5.5, "EXCELLENT"),
    (4.5, "GOOD"),
    (3.5, "MODERATE"),
    (0.0, "LOW"),
]

def solar_class(ghi: float) -> str:
    for t, lbl in SOLAR_BANDS:
        if ghi >= t:
            return lbl
    return "LOW"

# ── network ────────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "ResilienceStack/1.0"}

def _get_session():
    s = requests.Session()
    # total=2: don't hammer slow servers; backoff is irrelevant at 8 s timeout
    retry = urllib3.Retry(total=2, backoff_factor=0.3,
                          status_forcelist=[429,500,502,503,504])
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
                "country": loc.get("country",""),
                "admin": loc.get("admin1","")}
    except Exception:
        return None

@st.cache_data(ttl=86400*30, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str:
    try:
        r = requests.get(NOMINATIM,
            params={"lat": lat, "lon": lon, "format": "jsonv2"},
            headers=HEADERS, timeout=5)
        r.raise_for_status()
        addr = r.json().get("address", {})
        city = (addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("suburb") or addr.get("county") or "")
        cc = addr.get("country_code","").upper()
        return f"{city}, {cc}" if city else f"{lat:.3f}°N, {lon:.3f}°E"
    except Exception:
        return f"{lat:.3f}°N, {lon:.3f}°E"

# ── solar data ─────────────────────────────────────────────────────────────────
def _month_avg(d: dict) -> dict:
    """Aggregate dict(YYYYMM → value) into {month: mean}.
    NASA POWER uses -999 as a fill/missing sentinel — always excluded.
    """
    avgs = {}
    for m in range(1, 13):
        vals = [v for k, v in d.items()
                if k.endswith(f"{m:02d}")
                and v is not None
                and isinstance(v, (int, float))
                and v > 0
                and v != -999]
        avgs[m] = round(sum(vals) / len(vals), 3) if vals else None
    return avgs


def _latlon_fallback(lat: float) -> dict:
    """Return a rough climatological solar estimate when all live APIs fail.

    Values are a simplified latitude-band average; the monthly profile uses a
    northern-hemisphere sinusoidal shape (flipped for the southern hemisphere).
    Shown with source tag "Estimated" so the UI can flag it.
    """
    al = abs(lat)
    if   al <= 10: annual = 5.8
    elif al <= 20: annual = 5.5
    elif al <= 30: annual = 5.1
    elif al <= 40: annual = 4.3
    elif al <= 50: annual = 3.3
    elif al <= 60: annual = 2.5
    else:          annual = 1.8

    # Normalised month weights for northern hemisphere (peak in June)
    weights = [0.75, 0.82, 0.96, 1.07, 1.15, 1.20,
               1.18, 1.12, 1.02, 0.90, 0.76, 0.70]
    if lat < 0:               # flip for southern hemisphere
        weights = weights[6:] + weights[:6]
    ghi  = {m: round(annual * weights[m - 1], 3) for m in range(1, 13)}
    clr  = {m: round(v * 1.15, 3) for m, v in ghi.items()}
    return {
        "ghi":    ghi,
        "clear":  clr,
        "temp":   {m: None for m in range(1, 13)},
        "annual": annual,
        "source": "Estimated",
    }

@st.cache_data(ttl=86400*7, show_spinner=False)
def fetch_solar(lat: float, lon: float):
    """
    Try three solar APIs fastest-first.
    NASA POWER returns pre-aggregated monthly means — tiny payload, ~1-3 s globally.
    Results cached in-memory for 7 days (no persist="disk" to avoid diskcache dep).
    Falls back to a geographic estimate if all live APIs fail so the UI always works.
    """
    # Round to 2 dp so nearby points share cache (≈1 km granularity)
    lat4, lon4 = round(lat, 2), round(lon, 2)
    sess = _get_session()

    # 1. NASA POWER — monthly means pre-computed server-side, ~24 values, fast globally
    #    timeout=15 s: NASA POWER can be slow from Asia; -999 is NASA's missing-data fill
    try:
        r = sess.get(NASA_URL, params={
            "parameters": "ALLSKY_SFC_SW_DWN,T2M",
            "community": "RE",
            "longitude": lon4, "latitude": lat4,
            "start": 2020, "end": 2023, "format": "JSON",
        }, timeout=15)
        r.raise_for_status()
        prop = r.json().get("properties", {}).get("parameter", {})
        ghi_raw  = prop.get("ALLSKY_SFC_SW_DWN", {})
        temp_raw = prop.get("T2M", {})
        ghi  = _month_avg(ghi_raw)
        temp = _month_avg(temp_raw)
        clr  = {m: round(v * 1.18, 3) for m, v in ghi.items() if v}
        valid = [v for v in ghi.values() if v and v > 0]
        if len(valid) >= 10:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid) / len(valid), 3),
                    "source": "NASA POWER"}
    except Exception:
        pass

    # 2. PVGIS EU JRC — accurate but EU server (~5-15 s from Asia)
    try:
        r = sess.get(PVGIS_URL, params={
            "lat": lat4, "lon": lon4,
            "startyear": 2020, "endyear": 2023,
            "horirrad": 1, "outputformat": "json", "browser": 0,
        }, timeout=10)
        r.raise_for_status()
        rows = r.json().get("outputs", {}).get("monthly", [])
        if rows:
            sums: dict = defaultdict(list)
            for row in rows:
                m, yr, hm = int(row["month"]), int(row["year"]), row.get("H(h)_m")
                if hm and hm > 0:
                    sums[m].append(hm / monthrange(yr, m)[1])
            ghi  = {m: round(sum(vs)/len(vs), 3) for m, vs in sums.items() if vs}
            clr  = {m: round(v * 1.18, 3) for m, v in ghi.items()}
            temp = {m: None for m in range(1, 13)}
            valid = [v for v in ghi.values() if v and v > 0]
            if len(valid) >= 10:
                return {"ghi": ghi, "clear": clr, "temp": temp,
                        "annual": round(sum(valid) / len(valid), 3),
                        "source": "PVGIS · EU JRC"}
    except Exception:
        pass

    # 3. Open-Meteo ERA5 — daily data needs client aggregation, larger payload
    try:
        r = sess.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat4, "longitude": lon4,
            "start_date": "2021-01-01", "end_date": "2023-12-31",
            "daily": "shortwave_radiation_sum", "timezone": "UTC",
        }, timeout=10)
        r.raise_for_status()
        daily = r.json().get("daily", {})
        ms: dict = defaultdict(list)
        for d, v in zip(daily.get("time", []), daily.get("shortwave_radiation_sum", [])):
            if v is not None and v >= 0:
                ms[int(d[5:7])].append(v / 3.6)
        ghi  = {m: round(sum(vs)/len(vs), 3) for m, vs in ms.items() if vs}
        clr  = {m: round(v * 1.15, 3) for m, v in ghi.items()}
        temp = {m: None for m in range(1, 13)}
        valid = list(ghi.values())
        if len(valid) >= 10:
            return {"ghi": ghi, "clear": clr, "temp": temp,
                    "annual": round(sum(valid) / len(valid), 3),
                    "source": "Open-Meteo ERA5"}
    except Exception:
        pass

    # All live APIs failed — return a geographic climatological estimate so the
    # app remains usable offline / during outages.
    return _latlon_fallback(lat4)

# ── buildings ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_buildings(south, west, north, east):
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
                    area = _poly_area(coords)
                    if area > 10:
                        out.append({"coords": coords, "area_m2": round(area, 1)})
        return out
    except Exception:
        return []

def _poly_area(coords):
    if len(coords) < 3:
        return 0.0
    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(coords[0][0]))
    n, area = len(coords), 0.0
    for i in range(n):
        x1, y1 = coords[i][1]*lon_m,        coords[i][0]*lat_m
        x2, y2 = coords[(i+1)%n][1]*lon_m,  coords[(i+1)%n][0]*lat_m
        area += x1*y2 - x2*y1
    return abs(area) / 2.0

def bldg_kwh(area, ghi):
    return area * 0.6 * ghi * EFFICIENCY * PERF_RATIO * 365

def bldg_col(kwh):
    if kwh >= 20_000: return "#e87820"
    if kwh >= 10_000: return "#d4a020"
    if kwh >=  5_000: return "#a0c020"
    if kwh >=  2_000: return "#20b060"
    return "#2080d0"

# ── area calc ──────────────────────────────────────────────────────────────────
def calc_area(bounds, ghi):
    s, n, w, e = bounds["south"], bounds["north"], bounds["west"], bounds["east"]
    lat_m   = 111_320.0
    lon_m   = 111_320.0 * math.cos(math.radians((s+n)/2))
    area_m2 = abs(e-w)*lon_m * abs(n-s)*lat_m
    roof    = area_m2 * 0.20 * 0.60
    kwh_yr  = roof * ghi * EFFICIENCY * PERF_RATIO * 365
    return {
        "area_km2": round(area_m2/1_000_000, 3),
        "roof_m2":  round(roof),
        "mwh_yr":   round(kwh_yr/1000),
        "homes":    round(kwh_yr/3500),
        "panels":   int(roof/PANEL_M2),
        "co2_kt":   round(kwh_yr*CO2_G_KWH/1_000_000, 1),
    }

# ── panel calculator ───────────────────────────────────────────────────────────
def calc(ghi, n):
    kwh_yr = ghi * n * PANEL_M2 * EFFICIENCY * PERF_RATIO * 365
    peak   = n * PANEL_W / 1000
    cost   = peak * 1000 * COST_USD_W
    return {
        "kwh_yr":  round(kwh_yr),
        "peak_kw": round(peak, 1),
        "homes":   round(kwh_yr/3500, 1),
        "phones":  int(kwh_yr/365*1000/12),
        "trees":   round(kwh_yr*CO2_G_KWH/1000/21),
        "cost":    round(cost),
        "payback": round(cost/(kwh_yr*0.12), 1) if kwh_yr > 0 else None,
    }

# ── solar pathways (context-aware) ────────────────────────────────────────────
def solar_pathways(ghi: float, lat: float, lon: float):
    """Return 3-4 relevant service links based on location + irradiance tier."""
    is_india = (8 <= lat <= 37 and 68 <= lon <= 97)
    pvgis_url = f"https://re.jrc.ec.europa.eu/pvg_tools/en/?lat={lat:.4f}&lon={lon:.4f}"
    tier = solar_class(ghi)
    items = []

    if is_india:
        items.append({
            "cat": "GOVT SCHEME",
            "icon": "🏛",
            "title": "PM Surya Ghar Muft Bijli Yojana",
            "desc": "Up to ₹78,000 subsidy + 300 units/month free electricity",
            "url": "https://pmsuryaghar.gov.in",
            "cta": "Check eligibility →",
        })
        if ghi >= 4.5:
            items.append({
                "cat": "INSTALLER",
                "icon": "⚡",
                "title": "Get Rooftop Quotes",
                "desc": f"At {ghi:.1f} kWh/m²/day your system pays back in ~6–8 yrs",
                "url": "https://www.tatapowersolar.com/solar-rooftop/",
                "cta": "Compare quotes →",
            })
        items.append({
            "cat": "AGRI SOLAR",
            "icon": "🌾",
            "title": "PM-KUSUM Scheme",
            "desc": "Solar pumps & farm solarisation — 30% central subsidy",
            "url": "https://mnre.gov.in/pm-kusum/",
            "cta": "Explore scheme →",
        })
        items.append({
            "cat": "SIMULATION",
            "icon": "📐",
            "title": "PVGIS Detailed Simulation",
            "desc": "Monthly yield, losses, tilt optimisation for this exact location",
            "url": pvgis_url,
            "cta": "Open tool ↗",
        })
    else:
        items.append({
            "cat": "SIMULATION",
            "icon": "📐",
            "title": "PVGIS Radiation Report",
            "desc": "EU JRC monthly radiation + PV yield for this location",
            "url": pvgis_url,
            "cta": "Open tool ↗",
        })
        items.append({
            "cat": "ROOFTOP AI",
            "icon": "🛰",
            "title": "Google Project Sunroof",
            "desc": "Aerial imagery to estimate your roof's solar potential",
            "url": "https://sunroof.withgoogle.com/",
            "cta": "Try Sunroof →",
        })
        if ghi >= 5.0:
            items.append({
                "cat": "COMMERCIAL",
                "icon": "🏭",
                "title": "Global Solar Atlas",
                "desc": f"World-class {ghi:.1f} kWh/m²/day — ideal for utility-scale",
                "url": f"https://globalsolaratlas.info/map?c={lat:.4f},{lon:.4f},10",
                "cta": "View atlas →",
            })
        if ghi < 3.5:
            items.append({
                "cat": "ALTERNATIVE",
                "icon": "🌐",
                "title": "Community Solar",
                "desc": "Subscribe to off-site solar — no rooftop needed",
                "url": "https://www.energy.gov/eere/solar/community-solar",
                "cta": "Learn more →",
            })
        items.append({
            "cat": "FINANCIAL",
            "icon": "📊",
            "title": "PVWatts Calculator",
            "desc": "NREL tool: detailed financial model with local electricity rates",
            "url": f"https://pvwatts.nrel.gov/pvwatts.php?lat={lat:.4f}&lon={lon:.4f}",
            "cta": "Model savings →",
        })

    return items[:4]

# ── map builder ────────────────────────────────────────────────────────────────
def _draw_brush(m, lat: float, lon: float, radius_m: int, ghi: float):
    """GSA-gradient circle brush: 6 concentric shells simulate radial fade."""
    c = gsa_color(ghi)
    # Shells from outside→in, opacity increases toward centre
    for frac, alpha in [(1.00, 0.04), (0.78, 0.08), (0.56, 0.13),
                        (0.36, 0.20), (0.18, 0.30), (0.06, 0.50)]:
        folium.Circle(
            location=[lat, lon], radius=int(radius_m * frac),
            color="none", weight=0,
            fill=True, fill_color=c, fill_opacity=alpha,
        ).add_to(m)
    # Crisp outer ring
    folium.Circle(
        location=[lat, lon], radius=radius_m,
        color=c, weight=1.5, opacity=0.5,
        fill=False,
        tooltip=(f"<b style='font-family:Inter'>{ghi:.2f} kWh/m²/day</b><br>"
                 f"<span style='font-size:10px;color:#666'>"
                 f"Radius {radius_m/1000:.1f} km · click anywhere to move</span>"),
    ).add_to(m)
    # Pulsing centre dot
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f"""
            <div style="position:relative;width:20px;height:20px">
              <div style="position:absolute;inset:0;border-radius:50%;
                background:{c};opacity:0.25;animation:ring 2s ease-out infinite;">
              </div>
              <div style="position:absolute;inset:3px;border-radius:50%;
                background:{c};border:2px solid rgba(255,255,255,0.9);
                box-shadow:0 2px 8px {c}88;">
              </div>
            </div>
            <style>
              @keyframes ring{{
                0%{{transform:scale(1);opacity:.3}}
                80%{{transform:scale(2.2);opacity:0}}
                100%{{transform:scale(2.2);opacity:0}}
              }}
            </style>""",
            icon_size=(20, 20), icon_anchor=(10, 10),
        ),
        tooltip=f"☀ {ghi:.2f} kWh/m²/day",
    ).add_to(m)

def build_map(lat, lon, zoom, ghi, radius_m, buildings=None, area_coords=None):
    m = folium.Map(
        location=[lat, lon], zoom_start=zoom,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )
    Draw(export=False, draw_options={
        "rectangle": {"shapeOptions":{"color":"#e87820","weight":2,"fillOpacity":0.05}},
        "polygon":False,"polyline":False,"circle":False,
        "marker":False,"circlemarker":False},
        edit_options={"edit":False,"remove":True}).add_to(m)
    LocateControl(auto_start=False).add_to(m)

    _draw_brush(m, lat, lon, radius_m, ghi)

    if buildings:
        for b in buildings[:400]:
            kwh = bldg_kwh(b["area_m2"], ghi)
            c   = bldg_col(kwh)
            folium.Polygon(b["coords"], color=c, weight=0.8,
                fill=True, fill_color=c, fill_opacity=0.55,
                tooltip=f"{int(kwh):,} kWh/yr · {int(b['area_m2'])}m²").add_to(m)

    if area_coords:
        folium.Polygon([(c[1], c[0]) for c in area_coords],
            color="#e87820", weight=2, dash_array="8 5",
            fill=True, fill_color="#e87820", fill_opacity=0.07).add_to(m)

    return m

# ── charts ─────────────────────────────────────────────────────────────────────
CHART_BG = "rgba(0,0,0,0)"
ACCENT   = "#e87820"

def chart_monthly(solar, ghi) -> go.Figure:
    vals = [solar["ghi"].get(m) or 0 for m in range(1, 13)]
    peak = max(range(12), key=lambda i: vals[i])
    cols = [f"rgba(232,120,32,{0.85 if i==peak else 0.25})" for i in range(12)]
    fig = go.Figure(go.Bar(
        x=MONTHS_3, y=vals, marker_color=cols,
        hovertemplate="<b>%{x}</b>  %{y:.2f} kWh/m²/day<extra></extra>",
    ))
    fig.add_shape(type="line", x0=-0.5, x1=11.5, y0=ghi, y1=ghi,
                  line=dict(color="rgba(232,120,32,0.4)", width=1.5, dash="dot"))
    fig.update_layout(
        height=110, margin=dict(l=0,r=0,t=0,b=0), showlegend=False,
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        xaxis=dict(showgrid=False, showticklabels=True,
                   tickfont=dict(color="#9aa0b8", size=8),
                   tickmode="array", tickvals=MONTHS_3),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        bargap=0.2,
    )
    return fig

def chart_rank(my_ghi, my_name) -> go.Figure:
    data  = dict(BENCHMARKS)
    short = my_name.split(",")[0].strip()
    data[short] = my_ghi
    df = pd.DataFrame({"city": list(data.keys()), "ghi": list(data.values())})
    df = df.sort_values("ghi", ascending=True)
    cols   = [ACCENT if c == short else "rgba(30,34,64,0.12)" for c in df["city"]]
    labels = [f"{c} ◀" if c == short else c for c in df["city"]]
    fig = go.Figure(go.Bar(
        x=df["ghi"], y=labels, orientation="h",
        marker_color=cols,
        hovertemplate="<b>%{y}</b>  %{x:.2f} kWh/m²/day<extra></extra>",
    ))
    fig.update_layout(
        height=max(260, len(df)*19),
        margin=dict(l=0, r=4, t=0, b=0),
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, tickfont=dict(color="#4a5070", size=9)),
    )
    return fig

# ══ CSS ════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body {
  background: linear-gradient(145deg, #fdf4e3 0%, #eef3fb 55%, #e6eef8 100%) !important;
  min-height: 100vh;
}
.stApp, [data-testid="stAppViewContainer"] {
  background: transparent !important;
  font-family: 'Inter', system-ui, sans-serif !important;
}

/* ── hide Streamlit chrome ────────────────────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
footer, #MainMenu { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── main block: zero padding ─────────────────────────────────────────────── */
.main .block-container,
[data-testid="block-container"] {
  padding: 0 !important;
  max-width: 100% !important;
}

/* ── sidebar: frosted glass panel ─────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: rgba(255,255,255,0.72) !important;
  backdrop-filter: blur(28px) saturate(1.6) !important;
  -webkit-backdrop-filter: blur(28px) saturate(1.6) !important;
  border-right: 1px solid rgba(255,255,255,0.95) !important;
  box-shadow: 4px 0 32px rgba(0,20,80,0.08),
              inset -1px 0 0 rgba(200,215,235,0.5) !important;
  min-width: 340px !important;
  max-width: 340px !important;
  width: 340px !important;
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
  padding: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  height: 100vh !important;
  background: transparent !important;
  scrollbar-width: thin;
  scrollbar-color: rgba(0,20,80,0.10) transparent;
}
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 3px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
  background: rgba(0,20,80,0.10); border-radius: 2px; }

/* ── form elements ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stTextInput"] label { display:none !important; }
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input {
  background: rgba(255,255,255,0.6) !important;
  border: 1px solid rgba(0,20,80,0.12) !important;
  border-radius: 3px !important;
  color: #1e2240 !important;
  font-size: 13px !important;
  padding: 9px 12px !important;
  box-shadow: 0 1px 4px rgba(0,20,80,0.06) !important;
  transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input::placeholder {
  color: #9aa0b8 !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input:focus {
  border-color: rgba(232,120,32,0.55) !important;
  box-shadow: 0 0 0 3px rgba(232,120,32,0.10) !important;
  outline: none !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button {
  background: rgba(232,120,32,0.10) !important;
  border: 1px solid rgba(232,120,32,0.35) !important;
  border-radius: 3px !important;
  color: #c45d00 !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  letter-spacing: .07em !important;
  transition: all .18s !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
  background: rgba(232,120,32,0.18) !important;
  border-color: rgba(232,120,32,0.55) !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {
  background: #e87820 !important; border-color: #e87820 !important; }
[data-testid="stSidebar"] [data-testid="stSlider"] label {
  color: #4a5070 !important; font-size: 11px !important; font-weight: 500 !important; }

/* ── design tokens ────────────────────────────────────────────────────────── */
.sec      { padding: 14px 20px; border-bottom: 1px solid rgba(0,20,80,0.06); }
.sec-last { padding: 14px 20px 28px; }

.lbl {
  font-size: 9px; font-weight: 600; letter-spacing: .15em;
  text-transform: uppercase; color: #9aa0b8; margin-bottom: 2px;
}
.lbl-md {
  font-size: 9.5px; font-weight: 600; letter-spacing: .13em;
  text-transform: uppercase; color: #8890a8; margin-bottom: 8px;
}

.hero {
  font-size: 40px; font-weight: 700; letter-spacing: -.03em;
  line-height: 1; color: #1e2240; font-variant-numeric: tabular-nums;
}
.hero-unit { font-size: 11px; color: #9aa0b8; letter-spacing: .07em; margin-top: 4px; }
.val-lg    { font-size: 18px; font-weight: 600; letter-spacing: -.01em; color: #1e2240; }
.val-md    { font-size: 13px; font-weight: 600; color: #2a304a; }
.muted     { color: #7a80a0; font-size: 11px; }
.accent-txt { color: #c45d00; }
.pos-txt    { color: #1a7a48; }
.div { height: 1px; background: rgba(0,20,80,0.06); margin: 10px 0; }

.srow {
  display:flex; justify-content:space-between; align-items:center; padding: 5px 0;
}
.badge { font-size:8.5px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }

.hero-block {
  background: rgba(255,255,255,0.45);
  border-radius: 10px; padding: 16px 18px; margin-bottom: 12px;
  border: 1px solid rgba(255,255,255,0.85);
  box-shadow: 0 2px 12px rgba(0,20,80,0.06), inset 0 1px 0 rgba(255,255,255,0.6);
}

.area-card {
  border-left: 2px solid rgba(232,120,32,0.45);
  padding: 8px 0 8px 12px; margin-top: 6px;
}

/* Pathway cards */
.pathway-card {
  background: rgba(255,255,255,0.5);
  border: 1px solid rgba(0,20,80,0.07);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  transition: box-shadow .2s, background .2s;
}
.pathway-card:hover {
  background: rgba(255,255,255,0.75);
  box-shadow: 0 2px 14px rgba(0,20,80,0.08);
}
.pathway-cat {
  font-size: 7.5px; font-weight: 700; letter-spacing: .18em;
  text-transform: uppercase; color: #b0b8d0; margin-bottom: 3px;
}
.pathway-title {
  font-size: 12px; font-weight: 600; color: #1e2240; margin-bottom: 2px;
}
.pathway-desc { font-size: 10.5px; color: #7a80a0; line-height: 1.4; }
.pathway-cta {
  font-size: 10px; font-weight: 600; color: #c45d00;
  letter-spacing: .04em; margin-top: 5px; display: block;
  text-decoration: none;
}

/* Building legend chips */
.bchip { display:inline-flex; align-items:center; gap:5px; font-size:9.5px; color:#7a80a0; }
.bdot  { width:8px; height:8px; border-radius:2px; flex-shrink:0; }

/* ── map full-viewport ────────────────────────────────────────────────────── */
/* Remove Streamlit's residual vertical padding in the main column */
section[data-testid="stMain"] {
  overflow: hidden !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}
section[data-testid="stMain"] > div:first-child,
[data-testid="stMainBlockContainer"] {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  height: 100vh !important;
  max-height: 100vh !important;
  overflow: hidden !important;
}
/* Streamlit custom component host div + the iframe inside it */
[data-testid="stCustomComponentV1"] {
  height: 100vh !important;
  min-height: 100vh !important;
}
[data-testid="stCustomComponentV1"] > iframe {
  height: 100vh !important;
  min-height: 100vh !important;
  display: block !important;
}
</style>
"""

# ── html helpers ───────────────────────────────────────────────────────────────
def _sec(html, last=False):
    c = "sec-last" if last else "sec"
    return f"<div class='{c}'>{html}</div>"

def _row(lbl, val, col="#2a304a"):
    return (f"<div class='srow'>"
            f"<span class='muted'>{lbl}</span>"
            f"<span style='font-size:12px;font-weight:600;color:{col}'>{val}</span>"
            f"</div>")

# ══ SESSION STATE ══════════════════════════════════════════════════════════════
def _init():
    defs = dict(
        lat=19.076, lon=72.878, loc_name="Mumbai",
        map_zoom=12, mode="point",
        area_bounds=None, area_coords=None,
        viewport_bounds=None,
        # nav_id: incremented on each search so st_folium gets a fresh key.
        nav_id=0,
    )
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ══ MAIN ═══════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Solar Atlas · Day 02", page_icon="☀️",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    _init()

    lat  = st.session_state.lat
    lon  = st.session_state.lon
    zoom = st.session_state.map_zoom
    name = st.session_state.loc_name

    with st.spinner("Fetching solar data…"):
        solar = fetch_solar(lat, lon)
    ghi   = solar["annual"] if solar else 0.0
    lbl   = solar_class(ghi)
    col   = gsa_color(ghi)

    # Buildings (viewport-aware)
    buildings  = []
    show_bldgs = zoom >= 14
    if show_bldgs and solar:
        vp = st.session_state.viewport_bounds
        if vp:
            buildings = get_buildings(vp["south"], vp["west"], vp["north"], vp["east"])
        else:
            d = max(0.003, 0.035/(2**(zoom-14)))
            buildings = get_buildings(lat-d, lon-d, lat+d, lon+d)

    # ══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:

        # Brand
        st.markdown("""
<div class='sec' style='padding-bottom:12px'>
  <div style='display:flex;align-items:center;gap:8px'>
    <span style='font-size:18px'>☀</span>
    <div>
      <div style='font-size:13px;font-weight:700;color:#1e2240;letter-spacing:-.01em'>
        Solar Atlas
      </div>
      <div class='lbl' style='margin:0'>Day 02 · The Resilience Stack</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Search
        st.markdown("<div style='padding:12px 20px 4px'>", unsafe_allow_html=True)
        query  = st.text_input("q", value=name.split(",")[0],
                               placeholder="Search any city…",
                               label_visibility="collapsed", key="city_q")
        go_btn = st.button("→  Search", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if go_btn and query:
            with st.spinner(""):
                loc = geocode(query)
            if loc:
                st.session_state.lat      = loc["lat"]
                st.session_state.lon      = loc["lon"]
                st.session_state.loc_name = (
                    f"{loc['name']}{', '+loc['admin'] if loc['admin'] else ''}, {loc['country']}")
                st.session_state.map_zoom        = 12
                st.session_state.mode            = "point"
                st.session_state.area_bounds     = None
                st.session_state.area_coords     = None
                st.session_state.viewport_bounds = None
                # New nav_id → new st_folium key → fresh Leaflet instance.
                st.session_state.nav_id += 1
                st.rerun()
            else:
                st.error("Location not found.")
                return

        # fetch_solar now always returns data (falls back to geographic estimate)
        # so this branch is kept only as a safety net for unexpected None returns
        if not solar:
            st.markdown(_sec("<div class='muted' style='padding:20px 0;text-align:center'>"
                             "Solar data unavailable for this location.</div>"),
                        unsafe_allow_html=True)
            return

        # ── location + hero ───────────────────────────────────────────────────
        short  = name.split(",")[0].strip()
        rest   = ", ".join(name.split(",")[1:]).strip()
        tvs    = [v for v in solar["temp"].values() if v is not None]
        t_avg  = round(sum(tvs)/len(tvs), 1) if tvs else None
        best_m = max(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
        low_m  = min(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)

        st.markdown(_sec(f"""
<div style='margin-bottom:12px'>
  <div style='font-size:15px;font-weight:600;color:#1e2240;letter-spacing:-.01em'>{short}</div>
  <div class='muted' style='margin-top:1px'>{rest}</div>
  <div style='font-size:9px;color:#9aa0b8;margin-top:1px;letter-spacing:.04em'>
    {lat:.4f}°N &nbsp; {lon:.4f}°E &nbsp;
    <span style='color:#c0c8dc'>nav#{st.session_state.nav_id}</span>
  </div>
</div>

<div class='hero-block'>
  <div class='lbl'>ANNUAL SOLAR IRRADIANCE</div>
  <div style='display:flex;align-items:baseline;gap:8px;margin-top:6px'>
    <span class='hero'>{ghi:.2f}</span>
    <span class='hero-unit'>kWh / m² / day</span>
  </div>
  <div style='display:flex;align-items:center;gap:8px;margin-top:6px'>
    <span class='badge' style='color:{col}'>{lbl}</span>
    <span style='font-size:10px;color:#9aa0b8;font-style:italic'>
      {solar.get("source","PVGIS")} · 2019–2023
    </span>
  </div>
  <!-- GSA colour legend strip -->
  <div style='margin-top:10px'>
    <div style='height:5px;border-radius:3px;
      background:{GSA_LEGEND_CSS};'></div>
    <div style='display:flex;justify-content:space-between;margin-top:3px'>
      <span style='font-size:7.5px;color:#b0b8d0'>0</span>
      <span style='font-size:7.5px;color:#b0b8d0'>2.5</span>
      <span style='font-size:7.5px;color:#b0b8d0'>5.0</span>
      <span style='font-size:7.5px;color:#b0b8d0'>7.5 kWh/m²/day</span>
    </div>
  </div>
</div>

<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:0'>
  <div>
    <div class='lbl'>PEAK</div>
    <div style='font-size:13px;font-weight:600;color:#1e2240;margin-top:3px'>
      {MONTHS[best_m-1]}
    </div>
    <div style='font-size:10px;color:#9aa0b8'>{solar["ghi"].get(best_m,0):.1f} kWh</div>
  </div>
  <div>
    <div class='lbl'>LOW</div>
    <div style='font-size:13px;font-weight:600;color:#1e2240;margin-top:3px'>
      {MONTHS[low_m-1]}
    </div>
    <div style='font-size:10px;color:#9aa0b8'>{solar["ghi"].get(low_m,0):.1f} kWh</div>
  </div>
  <div>
    <div class='lbl'>AVG TEMP</div>
    <div style='font-size:13px;font-weight:600;color:#1e2240;margin-top:3px'>
      {f"{t_avg}°C" if t_avg is not None else "—"}
    </div>
    <div style='font-size:10px;color:#9aa0b8'>{"hot ↓eff" if t_avg and t_avg>28 else "optimal"}</div>
  </div>
</div>
"""), unsafe_allow_html=True)

        # ── brush radius ──────────────────────────────────────────────────────
        st.markdown("""
<div class='sec' style='padding-bottom:4px'>
  <div class='lbl-md'>BRUSH RADIUS</div>
</div>
""", unsafe_allow_html=True)
        radius_km = st.select_slider(
            " ", options=[0.5, 1, 2, 5, 10],
            value=st.session_state.get("radius_km", 2),
            format_func=lambda x: f"{x} km",
            label_visibility="collapsed", key="radius_km",
        )

        # ── monthly chart ─────────────────────────────────────────────────────
        st.markdown("""
<div class='sec' style='padding-bottom:6px;padding-top:10px'>
  <div class='lbl-md'>MONTHLY IRRADIANCE</div>
</div>
""", unsafe_allow_html=True)
        st.plotly_chart(chart_monthly(solar, ghi), use_container_width=True,
                        config={"displayModeBar": False}, key="m_chart")

        # ── area analysis ─────────────────────────────────────────────────────
        if st.session_state.mode == "area" and st.session_state.area_bounds:
            ar = calc_area(st.session_state.area_bounds, ghi)
            bs = st.session_state.area_bounds
            st.markdown(_sec(f"""
<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px'>
  <span class='lbl-md' style='color:#c45d00;margin-bottom:0'>AREA ANALYSIS</span>
  <span style='font-size:9px;color:#9aa0b8'>{ar["area_km2"]} km²</span>
</div>
<div style='font-size:9px;color:#9aa0b8;margin-bottom:8px'>
  {bs["south"]:.3f}° – {bs["north"]:.3f}°N
</div>
<div class='area-card'>
  <div style='display:grid;grid-template-columns:1fr 1fr;row-gap:12px'>
    <div>
      <div class='lbl'>SOLAR YIELD</div>
      <div class='val-lg accent-txt' style='margin-top:3px'>{ar["mwh_yr"]:,}</div>
      <div style='font-size:9px;color:#9aa0b8'>MWh / year</div>
    </div>
    <div>
      <div class='lbl'>HOMES POWERED</div>
      <div class='val-lg pos-txt' style='margin-top:3px'>{ar["homes"]:,}</div>
      <div style='font-size:9px;color:#9aa0b8'>at 3,500 kWh/yr</div>
    </div>
    <div>
      <div class='lbl'>PANELS</div>
      <div class='val-md' style='margin-top:3px'>{ar["panels"]:,}</div>
      <div style='font-size:9px;color:#9aa0b8'>{ar["roof_m2"]:,} m² roof</div>
    </div>
    <div>
      <div class='lbl'>CO₂ AVOIDED</div>
      <div class='val-md pos-txt' style='margin-top:3px'>{ar["co2_kt"]} kt</div>
      <div style='font-size:9px;color:#9aa0b8'>per year</div>
    </div>
  </div>
</div>
<div style='font-size:9px;color:#9aa0b8;margin-top:6px'>
  20% rooftop · 60% usable · click map to exit
</div>
"""), unsafe_allow_html=True)

        # ── panel calculator ──────────────────────────────────────────────────
        st.markdown("""
<div class='sec' style='padding-bottom:4px'>
  <div class='lbl-md'>PANEL CALCULATOR</div>
</div>
""", unsafe_allow_html=True)
        n_panels = st.slider(" ", 1, 100, 10, format="%d panels",
                             key="n_panels", label_visibility="collapsed")
        r = calc(ghi, n_panels)
        st.markdown(_sec(f"""
<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px'>
  <div>
    <span class='val-lg accent-txt'>{r["peak_kw"]}</span>
    <span style='font-size:10px;color:#9aa0b8;margin-left:3px'>kWp</span>
  </div>
  <div style='text-align:right'>
    <span class='val-md'>{r["kwh_yr"]:,}</span>
    <span style='font-size:10px;color:#9aa0b8;margin-left:3px'>kWh / yr</span>
  </div>
</div>
{_row("Installed cost",   f"${r['cost']:,}")}
{_row("Payback",          f"{r['payback']} yrs",    "#1a7a48")}
{_row("CO₂ offset",       f"{r['trees']:,} trees/yr","#1a7a48")}
<div class='div'></div>
{_row("Homes powered",    f"{r['homes']} ×")}
{_row("Phones / day",     f"{r['phones']:,}")}
"""), unsafe_allow_html=True)

        # ── solar pathways ────────────────────────────────────────────────────
        pathways = solar_pathways(ghi, lat, lon)
        cards_html = "".join(f"""
<a href='{p["url"]}' target='_blank' style='text-decoration:none'>
  <div class='pathway-card'>
    <div class='pathway-cat'>{p["cat"]}</div>
    <div class='pathway-title'>{p["icon"]} {p["title"]}</div>
    <div class='pathway-desc'>{p["desc"]}</div>
    <span class='pathway-cta'>{p["cta"]}</span>
  </div>
</a>
""" for p in pathways)
        st.markdown(_sec(f"""
<div class='lbl-md'>SOLAR PATHWAYS</div>
{cards_html}
"""), unsafe_allow_html=True)

        # ── global rank ───────────────────────────────────────────────────────
        st.markdown("""
<div class='sec' style='padding-bottom:6px'>
  <div class='lbl-md'>GLOBAL RANKING</div>
</div>
""", unsafe_allow_html=True)
        st.plotly_chart(chart_rank(ghi, name), use_container_width=True,
                        config={"displayModeBar": False}, key="rank_chart")

        # ── building legend ───────────────────────────────────────────────────
        if show_bldgs and buildings:
            st.markdown(f"""
<div class='sec' style='padding-top:10px;padding-bottom:10px'>
  <div class='lbl-md'>ROOFTOP SOLAR / YEAR</div>
  <div style='display:flex;flex-wrap:wrap;gap:6px 12px'>
    <span class='bchip'><span class='bdot' style='background:#2080d0'></span>&lt;2k kWh</span>
    <span class='bchip'><span class='bdot' style='background:#20b060'></span>2–5k</span>
    <span class='bchip'><span class='bdot' style='background:#a0c020'></span>5–10k</span>
    <span class='bchip'><span class='bdot' style='background:#d4a020'></span>10–20k</span>
    <span class='bchip'><span class='bdot' style='background:#e87820'></span>&gt;20k</span>
    <span class='bchip'>{len(buildings)} buildings</span>
  </div>
</div>
""", unsafe_allow_html=True)

        st.markdown(f"""
<div class='sec-last'>
  <div style='font-size:9px;color:#9aa0b8;line-height:1.9'>
    Pan the map to move the solar brush<br>
    Draw a rectangle for area solar analysis<br>
    Zoom ≥ 14 to see building-level potential<br>
    <span style='color:#bcc4d0'>NASA POWER · PVGIS · OSM · 2020–2023</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MAP — full canvas
    # ══════════════════════════════════════════════════════════════════════════
    radius_m = int(radius_km * 1000)
    m = build_map(lat, lon, zoom, ghi, radius_m,
                  buildings=buildings if show_bldgs else None,
                  area_coords=st.session_state.area_coords)

    nav_id = st.session_state.nav_id
    map_data = st_folium(m,
        # "last_clicked" removed — unreliable across reruns/nav changes.
        # Location now tracks the map CENTER via bounds (pan to explore).
        returned_objects=["last_active_drawing", "bounds", "zoom"],
        key=f"solar_map_{nav_id}",
        height=1200,          # CSS overrides this to 100vh; large fallback for tall screens
        use_container_width=True)

    # ── handle map events ──────────────────────────────────────────────────────
    if map_data:
        # ── zoom tracking (NO forced rerun — avoid map snap on zoom) ──────────
        # Buildings show/hide on the NEXT natural rerun (pan, slider, etc.).
        # Removing the zoom_crossed rerun eliminates the jank users feel when
        # zooming in/out quickly.
        new_zoom = map_data.get("zoom")
        if new_zoom:
            st.session_state.map_zoom = new_zoom

        # ── bounds → viewport + center-based location update ──────────────────
        rb = map_data.get("bounds")
        if rb:
            sw, ne = rb["_southWest"], rb["_northEast"]
            st.session_state.viewport_bounds = {
                "south": sw["lat"], "west": sw["lng"],
                "north": ne["lat"], "east": ne["lng"],
            }
            # Derive map center from bounds
            c_lat = round((sw["lat"] + ne["lat"]) / 2, 4)
            c_lon = round((sw["lng"] + ne["lng"]) / 2, 4)
            # Only update when the user has panned significantly (>0.40° ≈ 44 km).
            # Raised from 0.25° to reduce chatter on slow zooms/small pans.
            if (abs(c_lat - lat) > 0.40 or abs(c_lon - lon) > 0.40):
                st.session_state.lat         = c_lat
                st.session_state.lon         = c_lon
                st.session_state.mode        = "point"
                st.session_state.area_bounds = None
                st.session_state.area_coords = None
                st.session_state.loc_name    = reverse_geocode(c_lat, c_lon)
                st.rerun()

        # ── rectangle draw ────────────────────────────────────────────────────
        drawing = map_data.get("last_active_drawing")
        if drawing and drawing.get("geometry", {}).get("type") == "Polygon":
            coords = drawing["geometry"]["coordinates"][0]
            lats   = [c[1] for c in coords]
            lons   = [c[0] for c in coords]
            nb     = {"south": min(lats), "north": max(lats),
                      "west":  min(lons),  "east":  max(lons)}
            if nb != st.session_state.area_bounds:
                st.session_state.area_bounds = nb
                st.session_state.area_coords = coords
                st.session_state.mode = "area"
                st.rerun()

if __name__ == "__main__":
    main()
