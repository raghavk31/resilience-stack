"""
The Resilience Stack — Day 07 (V4 · Morphocode + Satellite)
Deforestation & Carbon Sink Tracker

Morphocode Explore aesthetic · Illustrative story cards
NASA GIBS MODIS NDVI satellite tiles · SideBySideLayers comparison
Sources: World Bank AG.LND.FRST.ZS / AG.LND.FRST.K2
         Pan et al. 2011 Science · Gatti et al. 2021 Nature · FAO FRA 2020
         NASA GIBS MODIS Terra Vegetation Indices Monthly 250m
"""

import datetime
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
import folium
from folium.plugins import SideBySideLayers
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Forests · Day 07 · Resilience Stack",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_FOREST_PCT = "AG.LND.FRST.ZS"
IND_FOREST_KM2 = "AG.LND.FRST.K2"

FIRST_YEAR, LAST_YEAR = 1990, 2021
TC_TO_TCO2         = 3.667
HA_PER_KM2         = 100.0
PROTECTION_COST_HA = 12.0

CARBON_DENSITY: dict[str, float] = {
    "BRA": 120, "COD": 175, "IDN": 145, "PER": 165, "COL": 155,
    "VEN": 130, "BOL": 115, "PNG": 170, "MYS": 140, "MMR": 110,
    "CMR": 145, "GAB": 175, "CAF": 150, "GUY": 170, "SUR": 165,
    "COG": 160, "GNQ": 155,
    "TZA":  85, "MOZ":  65, "ZMB":  60, "AGO":  75, "MDG":  90,
    "ETH":  70, "GHA": 100, "CIV": 105, "NGA":  80,
    "MEX":  90, "IND":  60, "THA":  95, "VNM":  90, "KHM": 100,
    "LAO":  95, "PHL":  85, "BGD":  70,
    "USA":  65, "FRA":  70, "DEU":  62, "POL":  58, "ESP":  52,
    "ITA":  60, "JPN":  85, "KOR":  70, "CHL":  88, "ARG":  72,
    "AUS":  42, "NZL":  78, "CHN":  52, "TUR":  52, "UKR":  55,
    "CAN":  45, "RUS":  38, "SWE":  46, "FIN":  43, "NOR":  48,
}
DEFAULT_CARBON = 75.0

GLOBAL_FOREST_GHA = {
    1900: 5.9, 1950: 5.5, 1960: 5.4, 1970: 5.2,
    1980: 5.0, 1990: 4.28, 2000: 4.17, 2010: 4.10,
    2015: 4.07, 2020: 4.06,
}

# NASA GIBS MODIS Terra NDVI tile URL — {z}/{y}/{x} for WMTS row/col ordering
# Monthly composite, 250m resolution, available 2002–present
def _gibs_ndvi_url(year: int, month: int = 6) -> str:
    date = f"{year}-{month:02d}-01"
    return (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "MODIS_Terra_Vegetation_Indices_Monthly_250m/default/"
        f"{date}/GoogleMapsCompatible/{{z}}/{{y}}/{{x}}.jpg"
    )

# GIBS True-Color for base reference
def _gibs_truecolor_url(year: int, month: int = 6) -> str:
    date = f"{year}-{month:02d}-01"
    return (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "MODIS_Terra_CorrectedReflectance_TrueColor/default/"
        f"{date}/GoogleMapsCompatible/{{z}}/{{y}}/{{x}}.jpg"
    )

FOREST_REGIONS = {
    "🌍 World":    ([2, 10], 2),
    "🌿 Amazon":   ([-5, -58], 4),
    "🌲 Congo":    ([-1, 24], 4),
    "🌴 Borneo":   ([1, 115], 5),
    "🌨️ Siberia":  ([60, 100], 3),
    "🍁 Canada":   ([56, -100], 3),
}

COMPARE_YEARS = [2003, 2006, 2009, 2012, 2015, 2018, 2022]

# ── Chart constants (light theme) ────────────────────────────────────────────
_BG   = "rgba(0,0,0,0)"
_PBG  = "rgba(0,0,0,0.02)"
_GC   = "rgba(0,0,0,0.07)"
_ZC   = "rgba(0,0,0,0.12)"
_TC   = "#475569"
_FONT = dict(family="Inter", color=_TC)

def _lyt(h: int = 360, **kw) -> dict:
    base = dict(paper_bgcolor=_BG, plot_bgcolor=_PBG, font=_FONT,
                height=h, margin=dict(l=0, r=0, t=30, b=0))
    base.update(kw)
    return base

def _xax(**kw) -> dict:
    return dict(gridcolor=_GC, zerolinecolor=_ZC, color=_TC, **kw)

def _yax(**kw) -> dict:
    return dict(gridcolor=_GC, zerolinecolor=_ZC, color=_TC, **kw)


# ── CSS — Morphocode Dark ─────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── App background ── */
.stApp { background: #f8fafc; }
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
section.main,
[data-testid="block-container"] { background: transparent !important; }

/* ── Text ── */
p, li, span { color: #475569; }
h1, h2, h3, h4 { color: #1e293b; font-family: 'Space Grotesk', 'Inter', sans-serif; }
label, [data-testid="stWidgetLabel"] p,
.stRadio label span p,
.stSelectbox label { color: #64748b !important; font-size: 11px !important; letter-spacing: 0.04em; }
.stMarkdown p { color: #475569; font-size: 13px; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 8px;
    padding: 3px;
    gap: 1px;
}
.stTabs [data-baseweb="tab"] {
    color: #94a3b8;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.02em;
}
.stTabs [aria-selected="true"] {
    background: rgba(34,197,94,0.10) !important;
    color: #16a34a !important;
    font-weight: 600;
}

/* ── Morphocode card ── */
.m-card {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 8px;
    padding: 1.2rem 1.4rem;
    margin-bottom: .5rem;
}
.m-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: .5rem;
}
.m-value {
    font-size: 1.9rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    letter-spacing: -0.5px;
    font-family: 'Space Grotesk', 'Inter', sans-serif;
}
.m-sub { font-size: 11px; color: #94a3b8; margin-top: .3rem; line-height: 1.4; }

/* ── Story cards ── */
.s-card {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 10px;
    padding: 1.4rem;
    position: relative;
    overflow: hidden;
    margin-bottom: .6rem;
    min-height: 220px;
}
.s-card-accent {
    position: absolute;
    top: 0; left: 0;
    width: 3px;
    height: 100%;
    border-radius: 10px 0 0 10px;
}
.s-label {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: .6rem;
}
.s-number {
    font-size: 2.2rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: -1px;
    font-variant-numeric: tabular-nums;
    font-family: 'Space Grotesk', sans-serif;
    margin-bottom: .25rem;
}
.s-headline {
    font-size: .82rem;
    font-weight: 600;
    color: #334155;
    margin-bottom: .4rem;
}
.s-body {
    font-size: .75rem;
    color: #64748b;
    line-height: 1.6;
}
.s-viz { margin: .8rem 0; }

/* ── Colors ── */
.c-green  { color: #16a34a; }
.c-amber  { color: #d97706; }
.c-red    { color: #dc2626; }
.c-blue   { color: #2563eb; }
.c-purple { color: #7c3aed; }
.c-teal   { color: #0d9488; }
.c-white  { color: #1e293b; }

/* ── Mini viz elements ── */
.mini-bar-track {
    background: rgba(0,0,0,0.07);
    border-radius: 2px;
    height: 4px;
    margin: 2px 0;
    overflow: hidden;
}
.mini-bar-fill { height: 100%; border-radius: 2px; }

.pixel-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 2px;
    margin: .6rem 0;
}
.px { width: 100%; aspect-ratio: 1; border-radius: 1px; }

/* ── Header ── */
.rs-header {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 60%, #f0fdf4 100%);
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 10px;
    padding: 1.6rem 2rem 1.4rem;
    margin-bottom: 1.2rem;
}
.rs-header h1 {
    font-size: 1.7rem; font-weight: 900; margin: 0 0 .2rem;
    color: #14532d; letter-spacing: -.5px;
    font-family: 'Space Grotesk', sans-serif;
}
.rs-header p { font-size: .82rem; color: #16a34a; margin: 0; }
.rs-badge {
    font-size: 9px; font-weight: 700; letter-spacing: .12em;
    color: #16a34a; margin-bottom: .5rem; display: block;
}

/* ── Method note ── */
.method-note {
    background: rgba(0,0,0,0.02);
    border-left: 2px solid rgba(22,163,74,0.35);
    padding: .5rem .9rem;
    border-radius: 0 6px 6px 0;
    font-size: .72rem; color: #64748b; margin-top: 1rem;
}

/* ── Map label ── */
.map-label {
    font-size: 10px; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: #94a3b8;
    margin-bottom: .4rem;
}

/* ── Divider ── */
hr { border-color: rgba(0,0,0,0.07) !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { display: none; }

/* ── Inputs ── */
[data-baseweb="select"] > div {
    background: #ffffff !important;
    border-color: rgba(0,0,0,0.10) !important;
    color: #1e293b !important;
}
[data-baseweb="select"] span { color: #1e293b !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: #16a34a !important;
}

/* ── st_folium container ── */
iframe { border-radius: 8px !important; }
</style>
"""


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=86_400 * 30, show_spinner=False)
def _load_country_meta() -> pd.DataFrame:
    rows, page = [], 1
    while True:
        try:
            r = requests.get(f"{WB_META}?format=json&per_page=500&page={page}",
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            meta, data = r.json()
            for c in data:
                reg = c.get("region", {})
                if isinstance(reg, dict) and reg.get("id") not in ("", "NA", None):
                    rows.append({"iso3": c["id"], "name": c["name"],
                                 "region": reg.get("value", "")})
            if page * meta.get("per_page", 500) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def _load_wb_series(indicator: str) -> pd.DataFrame:
    rows, page = [], 1
    while True:
        url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
               f"?format=json&date={FIRST_YEAR}:{LAST_YEAR}&per_page=1000&page={page}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            if len(payload) < 2 or not payload[1]:
                break
            meta, data = payload
            rows.extend(data)
            if page * meta.get("per_page", 1000) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df[df["value"].notna()].copy()
    df["year"]    = df["date"].astype(int)
    df["iso3"]    = df["countryiso3code"]
    df["country"] = df["country"].apply(lambda x: x["value"] if isinstance(x, dict) else x)
    df["value"]   = df["value"].astype(float)
    return df[["iso3", "country", "year", "value"]].sort_values(["iso3", "year"]).reset_index(drop=True)


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def load_forest_data() -> pd.DataFrame:
    meta = _load_country_meta()
    km2  = _load_wb_series(IND_FOREST_KM2)
    pct  = _load_wb_series(IND_FOREST_PCT)
    if meta.empty or km2.empty:
        return pd.DataFrame()
    valid = set(meta["iso3"])
    km2 = km2[km2["iso3"].isin(valid)].rename(columns={"value": "forest_km2"})
    pct = pct[pct["iso3"].isin(valid)].rename(columns={"value": "forest_pct"})
    df  = km2.merge(pct[["iso3", "year", "forest_pct"]], on=["iso3", "year"], how="left")
    df  = df.merge(meta[["iso3", "name", "region"]], on="iso3", how="left")
    df["cd"]           = df["iso3"].map(CARBON_DENSITY).fillna(DEFAULT_CARBON)
    df["carbon_GtCO2"] = df["forest_km2"] * HA_PER_KM2 * df["cd"] * TC_TO_TCO2 / 1e9
    return df


def _net_change(df: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
    s = df[df["year"] == y0][["iso3", "country", "name", "region", "forest_km2", "cd"]].rename(
        columns={"forest_km2": "km2_0"})
    e = df[df["year"] == y1][["iso3", "forest_km2", "forest_pct"]].rename(
        columns={"forest_km2": "km2_1"})
    m = s.merge(e, on="iso3", how="inner").dropna(subset=["km2_0", "km2_1"])
    m["delta_km2"] = m["km2_1"] - m["km2_0"]
    m["delta_pct"] = m["delta_km2"] / m["km2_0"] * 100
    return m


# ── Story card mini-visualizations (inline HTML/CSS) ─────────────────────────

def _donut(pct_gone: float, color_gone: str = "#ef4444",
           color_left: str = "#22c55e", size: int = 56) -> str:
    deg = pct_gone / 100 * 360
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:conic-gradient({color_gone} 0deg {deg:.0f}deg, '
        f'{color_left} {deg:.0f}deg 360deg);margin:.6rem 0"></div>'
    )


def _bars(values: list[tuple[float, str, str]], max_val: float,
          height: int = 40, bar_w: int = 18) -> str:
    bars = ""
    for val, color, label in values:
        h = int(val / max_val * height)
        bars += (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
                 f'<div style="width:{bar_w}px;height:{h}px;background:{color};'
                 f'border-radius:2px 2px 0 0"></div>'
                 f'<div style="font-size:8px;color:#475569;font-variant-numeric:tabular-nums">{label}</div>'
                 f'</div>')
    return (f'<div style="display:flex;gap:6px;align-items:flex-end;'
            f'height:{height+18}px;margin:.5rem 0">{bars}</div>')


def _pixel_grid(pct_lost: float, rows: int = 4, cols: int = 12) -> str:
    total = rows * cols
    lost  = int(total * pct_lost / 100)
    cells = ""
    for i in range(total):
        color = "#1a1a2e" if i < lost else "#22c55e"
        cells += f'<div class="px" style="background:{color}"></div>'
    return f'<div class="pixel-grid" style="grid-template-columns:repeat({cols},1fr)">{cells}</div>'


def _mini_progress(pct: float, color: str = "#22c55e", label: str = "") -> str:
    return (f'<div style="margin:.4rem 0">'
            f'<div class="mini-bar-track">'
            f'<div class="mini-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>'
            f'</div>'
            f'{"<div style=\"font-size:9px;color:#475569;margin-top:2px\">" + label + "</div>" if label else ""}'
            f'</div>')


def _arrow_flip() -> str:
    return """
    <div style="display:flex;gap:16px;align-items:center;margin:.6rem 0">
      <div style="text-align:center">
        <div style="font-size:20px">⬇️</div>
        <div style="font-size:8px;color:#22c55e;margin-top:2px">Pre-2021<br>absorbing</div>
      </div>
      <div style="color:#475569;font-size:10px">→</div>
      <div style="text-align:center">
        <div style="font-size:20px">⬆️</div>
        <div style="font-size:8px;color:#ef4444;margin-top:2px">Post-2021<br>emitting</div>
      </div>
    </div>
    """


# ── Live deforestation counter ────────────────────────────────────────────────

def _live_counter(loss_per_sec: float) -> None:
    components.html(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700;900&family=Inter:wght@400;500;600&display=swap');
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{ background:#fff7f7; font-family:'Inter',sans-serif; }}
      .wrap {{
        background:#fff7f7;
        border:1px solid rgba(220,38,38,0.12);
        border-top:4px solid #dc2626;
        border-radius:0 0 10px 10px;
        padding:1.6rem 2rem 1.4rem;
        text-align:center;
      }}
      .label {{
        font-size:10px; font-weight:700; letter-spacing:.12em;
        text-transform:uppercase; color:#94a3b8; margin-bottom:.6rem;
      }}
      .counter {{
        font-size:5rem; font-weight:900; color:#dc2626;
        font-family:'Space Grotesk',sans-serif;
        line-height:1; letter-spacing:-4px;
        font-variant-numeric:tabular-nums;
      }}
      .unit {{ font-size:1.4rem; font-weight:600; color:#dc2626; letter-spacing:0; margin-left:4px; }}
      .sub {{ font-size:.82rem; color:#64748b; margin-top:.55rem; }}
      .sub b {{ color:#dc2626; }}
      .rate {{
        font-size:.72rem; color:#94a3b8; margin-top:.3rem;
        border-top:1px solid rgba(220,38,38,0.08);
        padding-top:.5rem; margin-top:.6rem;
        display:flex; justify-content:center; gap:1.6rem; flex-wrap:wrap;
      }}
      .rate span {{ white-space:nowrap; }}
    </style>
    <div class="wrap">
      <div class="label">hectares of forest cleared since you opened this tab</div>
      <div>
        <span class="counter" id="ha">0.0</span>
        <span class="unit">ha</span>
      </div>
      <div class="sub">= <b id="pitches">0</b> football pitches gone</div>
      <div class="rate">
        <span>{loss_per_sec:.2f} ha / sec</span>
        <span>{loss_per_sec * 60:.0f} ha / min</span>
        <span>{loss_per_sec * 3600:.0f} ha / hr</span>
        <span>{loss_per_sec * 86400:,.0f} ha / day</span>
      </div>
    </div>
    <script>
      const rate = {loss_per_sec};
      const t0 = performance.now();
      function fmt(n) {{
        return n.toLocaleString('en-US', {{minimumFractionDigits:1, maximumFractionDigits:1}});
      }}
      function tick() {{
        const ha = (performance.now() - t0) / 1000 * rate;
        document.getElementById('ha').textContent = fmt(ha);
        document.getElementById('pitches').textContent = Math.floor(ha / 0.714).toLocaleString('en-US');
        requestAnimationFrame(tick);
      }}
      tick();
    </script>
    """, height=190, scrolling=False)


# ── Tab 1 — The Story ─────────────────────────────────────────────────────────

def tab_story(df: pd.DataFrame) -> None:
    snap   = df[df["year"] == LAST_YEAR]
    base   = df[df["year"] == FIRST_YEAR]
    common = set(snap["iso3"]) & set(base["iso3"])

    total_now       = snap[snap["iso3"].isin(common)]["forest_km2"].sum()
    total_1990      = base[base["iso3"].isin(common)]["forest_km2"].sum()
    total_C         = snap["carbon_GtCO2"].sum()
    annual_loss_km2 = (total_1990 - total_now) / (LAST_YEAR - FIRST_YEAR)
    annual_loss_ha  = annual_loss_km2 * HA_PER_KM2
    loss_per_sec    = annual_loss_ha / (365.25 * 86400)
    days_elapsed    = (datetime.date.today() - datetime.date(datetime.date.today().year, 1, 1)).days
    lost_this_year  = int(annual_loss_ha * days_elapsed / 365.25)
    lost_mha        = (total_1990 - total_now) * HA_PER_KM2 / 1e6

    # ── Live counter ──────────────────────────────────────────────────────────
    _live_counter(loss_per_sec)

    st.markdown("<div style='height:.2rem'></div>", unsafe_allow_html=True)

    # ── Beat 1: The Scale ─────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="s-card" style="border-top:4px solid #16a34a;min-height:auto;padding:1.8rem 2rem;margin-bottom:.6rem">
      <div class="s-label" style="color:#16a34a;margin-bottom:1.2rem">ACT I — THE SCALE OF WHAT WE'RE LOSING</div>
      <div style="display:grid;grid-template-columns:1fr 48px 1fr;gap:1rem;align-items:center;margin-bottom:1.4rem">
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;color:#94a3b8;text-transform:uppercase;margin-bottom:.3rem">1900</div>
          <div style="font-size:3.4rem;font-weight:900;color:#16a34a;font-family:'Space Grotesk',sans-serif;line-height:1;letter-spacing:-2px">5.9<span style="font-size:1.2rem;font-weight:600;color:#64748b;letter-spacing:0"> Bn ha</span></div>
          <div style="font-size:.75rem;color:#64748b;margin-top:.3rem">forest covered the Earth</div>
        </div>
        <div style="text-align:center;font-size:1.4rem;color:#cbd5e1;padding-top:.8rem">→</div>
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;color:#94a3b8;text-transform:uppercase;margin-bottom:.3rem">TODAY</div>
          <div style="font-size:3.4rem;font-weight:900;color:#dc2626;font-family:'Space Grotesk',sans-serif;line-height:1;letter-spacing:-2px">{total_now/1e9:.2f}<span style="font-size:1.2rem;font-weight:600;color:#64748b;letter-spacing:0"> Bn ha</span></div>
          <div style="font-size:.75rem;color:#64748b;margin-top:.3rem">remain — and falling</div>
        </div>
      </div>
      <div style="background:#fef2f2;border:1px solid rgba(220,38,38,0.12);border-radius:6px;padding:.9rem 1.1rem;font-size:.82rem;color:#7f1d1d;line-height:1.65">
        <b>{lost_mha:.0f} million hectares erased</b> — an area roughly the size of Russia, stripped bare in 120 years.
        What still stands absorbs a third of humanity's annual CO₂ emissions, regulates rainfall for billions of people,
        and shelters 80% of all land species. We are burning the infrastructure of life on Earth.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Beat 2 + Beat 3 ───────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div class="s-card" style="border-top:4px solid #dc2626;min-height:260px;margin-bottom:.6rem">
          <div class="s-label" style="color:#dc2626">ACT II — IT'S HAPPENING RIGHT NOW</div>
          <div style="font-size:3rem;font-weight:900;color:#dc2626;font-family:'Space Grotesk',sans-serif;
               line-height:1;letter-spacing:-1.5px;margin:.5rem 0 .2rem">{loss_per_sec:.1f} ha</div>
          <div style="font-size:.8rem;font-weight:600;color:#334155;margin-bottom:.9rem">vanishing every second</div>
          <div style="font-size:.78rem;color:#64748b;line-height:1.7">
            By the time you finish reading this card,
            <b style="color:#dc2626">{int(loss_per_sec * 25):,} hectares</b> will have been cleared.
            <br><br>
            Since 1 January {datetime.date.today().year}: <b style="color:#dc2626">{lost_this_year:,} ha</b> gone —
            that's <b>{lost_this_year / 0.714:,.0f} football pitches</b>, this year alone,
            as of {datetime.date.today().strftime('%b %d')}.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="s-card" style="border-top:4px solid #f59e0b;min-height:260px;margin-bottom:.6rem">
          <div class="s-label" style="color:#d97706">ACT III — THE POINT OF NO RETURN</div>
          <div style="font-size:3rem;font-weight:900;color:#f59e0b;font-family:'Space Grotesk',sans-serif;
               line-height:1;letter-spacing:-1.5px;margin:.5rem 0 .2rem">+0.86</div>
          <div style="font-size:.8rem;font-weight:600;color:#334155;margin-bottom:.9rem">PgC/yr — the Amazon now emits more than it absorbs</div>
          <div style="font-size:.78rem;color:#64748b;line-height:1.7">
            For decades the Amazon was Earth's emergency brake on climate change — absorbing
            carbon even as we burned the rest of the planet. In 2021 that ended.
            Scientists confirmed the eastern Amazon now <b style="color:#f59e0b">emits 0.86 PgC/yr</b>,
            driven by fire and fragmentation. The world's largest forest has become part of the problem.
            <span style="display:block;margin-top:.6rem;font-size:.68rem;color:#94a3b8">
              Gatti et al. 2021, Nature · doi:10.1038/s41586-021-03629-6
            </span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Beat 4: The Fix ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="s-card" style="border-top:4px solid #16a34a;min-height:auto;
         background:linear-gradient(135deg,#f0fdf4 0%,#ffffff 60%);padding:1.8rem 2rem;margin-bottom:.6rem">
      <div class="s-label" style="color:#16a34a;margin-bottom:.8rem">ACT IV — THE FIX EXISTS. IT'S CHEAPER THAN YOU THINK.</div>
      <div style="display:grid;grid-template-columns:auto 1fr;gap:2.5rem;align-items:start">
        <div>
          <div style="font-size:3.4rem;font-weight:900;color:#16a34a;font-family:'Space Grotesk',sans-serif;
               line-height:1;letter-spacing:-2px">$12</div>
          <div style="font-size:.72rem;color:#64748b;margin-top:.3rem;line-height:1.4">per hectare<br>per year</div>
        </div>
        <div style="font-size:.82rem;color:#334155;line-height:1.75">
          That's what it costs to protect one hectare of tropical forest for a year under REDD+.
          At a carbon price of $50/tonne — the Paris-aligned floor — a single protected hectare
          generates <b style="color:#16a34a">$600/yr in credits</b>. The economics work.
          What's missing is not money. It's political will.
          <div style="margin-top:.9rem;display:flex;gap:.6rem;flex-wrap:wrap">
            <span style="background:#dcfce7;border:1px solid rgba(22,163,74,0.2);border-radius:4px;
                  padding:3px 10px;font-size:11px;color:#15803d;font-weight:600">
              $12 cost → $600 revenue at $50/t CO₂
            </span>
            <span style="background:#fefce8;border:1px solid rgba(202,138,4,0.2);border-radius:4px;
                  padding:3px 10px;font-size:11px;color:#854d0e;font-weight:600">
              {total_C:.0f} GtCO₂ locked in standing forests today
            </span>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Timeline ──────────────────────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="m-label" style="margin-bottom:.5rem">THE LONG DECLINE — GLOBAL FOREST SINCE 1900</div>',
                unsafe_allow_html=True)
    trend_df = pd.DataFrame(list(GLOBAL_FOREST_GHA.items()), columns=["year", "gha"])
    tf = go.Figure()
    tf.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["gha"],
        mode="lines+markers",
        line=dict(color="#16a34a", width=2.5),
        marker=dict(size=7, color="#16a34a", line=dict(color="#ffffff", width=1.5)),
        fill="tozeroy", fillcolor="rgba(22,163,74,0.08)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f} Gha<extra></extra>",
    ))
    tf.add_annotation(x=2020, y=4.06, text="4.06 Gha today",
                      font=dict(color="#dc2626", size=10, family="Inter"),
                      showarrow=True, arrowcolor="#dc2626", arrowwidth=1, arrowhead=2, ax=40, ay=-25)
    tf.add_annotation(x=1900, y=5.9, text="5.9 Gha · 1900",
                      font=dict(color="#16a34a", size=10, family="Inter"),
                      showarrow=True, arrowcolor="#16a34a", arrowwidth=1, arrowhead=2, ax=10, ay=-25)
    tf.update_layout(**_lyt(h=240, margin=dict(l=0, r=0, t=10, b=0),
                            xaxis=_xax(showgrid=False),
                            yaxis=_yax(showgrid=True, title="Billion ha", range=[3.5, 6.3])))
    st.plotly_chart(tf, use_container_width=True)

    st.markdown('<div class="method-note">Forest area: FAO FRA 2020 + Ramankutty &amp; Foley 1999 (pre-1990). Amazon tipping point: Gatti et al. 2021 Nature. REDD+ economics: Busch et al. 2019 NCC.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Forest from Space ─────────────────────────────────────────────────

def tab_satellite_map() -> None:
    st.markdown("""
    <div class="m-card" style="margin-bottom:.8rem;padding:1rem 1.2rem">
      <div class="m-label">WHAT YOU'RE LOOKING AT</div>
      <div style="font-size:12px;color:#64748b;line-height:1.6;max-width:800px">
        Real NASA satellite imagery — MODIS Terra True Color, 250m resolution, June composite.
        <span style="color:#16a34a;font-weight:600">Deep green</span> = intact forest.
        <span style="color:#92400e;font-weight:600">Tan/brown</span> = cleared land.
        Drag the centre divider to reveal the earlier year on the left vs the later year on the right.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right, col_focus = st.columns([2, 2, 2])
    with col_left:
        yr_left  = st.selectbox("Earlier year (left)", COMPARE_YEARS,
                                index=0, key="yr_l")
    with col_right:
        yr_right = st.selectbox("Later year (right)", COMPARE_YEARS,
                                index=len(COMPARE_YEARS)-1, key="yr_r")
    with col_focus:
        region_name = st.selectbox("Focus region", list(FOREST_REGIONS.keys()),
                                   index=1, key="focus")  # default Amazon

    center, zoom = FOREST_REGIONS[region_name]

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        prefer_canvas=True,
    )

    # Neutral light base — visible only where MODIS tiles are missing
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        attr="© CARTO · © OpenStreetMap",
        name="Base",
        overlay=False,
        control=False,
    ).add_to(m)

    # True Color tiles — GIBS WMTS uses {z}/{y}/{x} (TileMatrix/TileRow/TileCol)
    layer_left = folium.TileLayer(
        tiles=_gibs_truecolor_url(yr_left),
        attr=f"NASA GIBS MODIS Terra True Color {yr_left}",
        name=str(yr_left),
        overlay=True,
        control=False,
        opacity=1.0,
    )
    layer_right = folium.TileLayer(
        tiles=_gibs_truecolor_url(yr_right),
        attr=f"NASA GIBS MODIS Terra True Color {yr_right}",
        name=str(yr_right),
        overlay=True,
        control=False,
        opacity=1.0,
    )
    layer_left.add_to(m)
    layer_right.add_to(m)

    SideBySideLayers(layer_left=layer_left, layer_right=layer_right).add_to(m)

    # Forest region pins
    forest_pins = [
        ([-5,  -58], "🌿 Amazon",       "5.5M km² · world's largest tropical forest"),
        ([-1,   24], "🌲 Congo",        "3.7M km² · world's second largest tropical forest"),
        ([ 1,  115], "🌴 Borneo",       "Most biodiverse forest on Earth"),
        ([60,  100], "🌨️ Taiga",        "12M km² · world's largest forest biome"),
        ([56, -100], "🍁 Boreal Canada","3.4M km² of intact boreal forest"),
    ]
    for loc, title, desc in forest_pins:
        folium.Marker(
            location=loc,
            tooltip=folium.Tooltip(
                f"<b style='font-size:11px'>{title}</b><br>"
                f"<span style='font-size:10px;color:#64748b'>{desc}</span>",
                sticky=False,
            ),
            icon=folium.DivIcon(
                html=f'<div style="background:rgba(255,255,255,0.92);border:1px solid #16a34a;'
                     f'color:#14532d;font-size:9px;font-weight:700;padding:2px 6px;'
                     f'border-radius:4px;white-space:nowrap;font-family:Inter,sans-serif;'
                     f'box-shadow:0 1px 4px rgba(0,0,0,0.15)">{title}</div>',
                icon_size=(130, 22),
                icon_anchor=(65, 11),
            ),
        ).add_to(m)

    # Year labels — light theme
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:absolute;top:16px;left:20px;z-index:1000;
         background:rgba(255,255,255,0.92);border:1px solid rgba(22,163,74,0.4);
         color:#14532d;font-family:Inter,sans-serif;font-size:13px;font-weight:800;
         padding:5px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,0.12)">
      {yr_left}
    </div>
    <div style="position:absolute;top:16px;right:20px;z-index:1000;
         background:rgba(255,255,255,0.92);border:1px solid rgba(220,38,38,0.4);
         color:#991b1b;font-family:Inter,sans-serif;font-size:13px;font-weight:800;
         padding:5px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,0.12)">
      {yr_right}
    </div>
    <div style="position:absolute;bottom:40px;left:50%;transform:translateX(-50%);
         z-index:1000;background:rgba(255,255,255,0.85);
         color:#64748b;font-family:Inter,sans-serif;font-size:10px;font-weight:500;
         padding:3px 10px;border-radius:4px;pointer-events:none">
      ← drag divider to compare →
    </div>
    """))

    st_folium(m, height=600, use_container_width=True, returned_objects=[])

    st.markdown(f"""
    <div class="method-note">
      NASA GIBS MODIS Terra CorrectedReflectance TrueColor · 250m · June {yr_left} vs June {yr_right}.
      Zoom into the Amazon, Congo Basin, or Borneo for pixel-level detail.
      Deep green = dense canopy. Tan/grey = deforested or degraded land.
    </div>
    """, unsafe_allow_html=True)


# ── Tab 3 — Deforestation ─────────────────────────────────────────────────────

def tab_deforestation(df: pd.DataFrame) -> None:
    st.markdown("""
    <div class="m-card" style="margin-bottom:.8rem;padding:1rem 1.2rem">
      <div class="m-label">WHERE THE LOSS IS HAPPENING</div>
      <div style="font-size:12px;color:#64748b;line-height:1.6;max-width:800px">
        Top 20 countries by forest loss. Switch between <b>absolute</b> (total km² cleared)
        and <b>rate</b> (% of original forest lost) to see a different picture —
        small island nations often rank highest by rate even though large tropical countries
        dominate by raw area.
      </div>
    </div>
    """, unsafe_allow_html=True)

    PERIODS = {
        "1990 → 2000": (1990, 2000),
        "2000 → 2010": (2000, 2010),
        "2010 → 2020": (2010, 2020),
        "Full period (1990 → 2020)": (1990, 2020),
    }
    col_l, col_r = st.columns([2, 2])
    with col_l:
        period = st.selectbox("Time period", list(PERIODS.keys()), index=2, key="t3_period")
    with col_r:
        view = st.radio("Rank by", ["Absolute (km²)", "Rate (%)"],
                        horizontal=True, key="t3_view")

    y0, y1  = PERIODS[period]
    chg     = _net_change(df, y0, y1)
    losers  = chg[chg["delta_km2"] < 0].copy()
    losers["abs_loss"] = -losers["delta_km2"]
    losers["rate"]     = -losers["delta_pct"]
    n_years = y1 - y0

    total_km2  = losers["abs_loss"].sum()
    carbon_Gt  = (losers["abs_loss"] * HA_PER_KM2 * losers["cd"] * TC_TO_TCO2 / 1e9).sum()
    ha_day     = total_km2 * HA_PER_KM2 / n_years / 365.25

    c1, c2, c3, c4 = st.columns(4)
    facts = [
        (f"{total_km2/1e6:.2f}M km²",   f"Forest lost {period}",       "#dc2626"),
        (f"{carbon_Gt:.1f} GtCO₂",      "Carbon released equivalent",  "#d97706"),
        (f"{total_km2/242495:.1f}× UK", "Area equivalent",             "#2563eb"),
        (f"{ha_day/0.714:,.0f}/day",    "Football pitches lost daily", "#dc2626"),
    ]
    for col, (val, lbl, color) in zip([c1, c2, c3, c4], facts):
        col.markdown(f'<div class="m-card"><div class="m-label">{lbl}</div>'
                     f'<div class="m-value" style="color:{color}">{val}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

    x_col = "abs_loss" if view.startswith("Absolute") else "rate"
    x_lbl = "Forest lost (km²)" if view.startswith("Absolute") else "Loss (% of forest)"
    top   = losers.nlargest(20, x_col).sort_values(x_col)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top[x_col], y=top["country"], orientation="h",
        marker=dict(color=top[x_col],
                    colorscale=[[0,"#7f1d1d"],[0.5,"#dc2626"],[1,"#f87171"]],
                    showscale=False),
        text=top[x_col].apply(lambda v: f"{v:,.0f}" if view.startswith("Absolute") else f"{v:.1f}%"),
        textposition="outside", textfont=dict(color="#64748b", size=9),
    ))
    fig.update_layout(**_lyt(h=540, margin=dict(l=0, r=70, t=10, b=0),
                             xaxis=_xax(showgrid=True, title=x_lbl),
                             yaxis=_yax(showgrid=False)))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div class="m-card" style="border-color:rgba(220,38,38,0.15);border-left:4px solid #dc2626;border-radius:0 8px 8px 0">
      <div class="m-label" style="color:#dc2626">THE AMAZON TIPPING POINT — 2021</div>
      <div style="font-size:12px;color:#475569;line-height:1.8">
        The eastern Amazon now emits <b style="color:#dc2626">+0.86 PgC/yr</b>.
        The western Amazon is still a sink (−0.54 PgC/yr).
        Net result: Earth's greatest forest crossed its <b style="color:#1e293b">carbon tipping point</b>.
        59% driven by fires · 41% by deforestation-linked degradation.
        <br><span style="font-size:10px;color:#94a3b8">Gatti et al. 2021, Nature · doi:10.1038/s41586-021-03629-6</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest area: World Bank AG.LND.FRST.ZS/K2. Carbon = area × density (Pan et al. 2011). UK 242,495 km². FIFA pitch 0.714 ha.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — Solutions ─────────────────────────────────────────────────────────

def tab_solutions(df: pd.DataFrame) -> None:
    st.markdown("""
    <div class="m-card" style="margin-bottom:.8rem;padding:1rem 1.2rem">
      <div class="m-label">REDD+ — CAN PROTECTING FORESTS PAY FOR ITSELF?</div>
      <div style="font-size:12px;color:#64748b;line-height:1.6;max-width:800px">
        REDD+ (Reducing Emissions from Deforestation and Degradation) pays countries
        a carbon credit for every tonne of CO₂ they keep locked in standing forest.
        Drag the slider to change the carbon price and see how many countries tip into
        profit — and how large the net global opportunity becomes.
      </div>
    </div>
    """, unsafe_allow_html=True)

    price = st.slider("Carbon price ($/tCO₂)", 10, 150, 50, 5, key="t4_price",
                      help="Voluntary market ~$10–30. Policy-aligned: $50–150.")

    snap = df[df["year"] == LAST_YEAR].copy()
    base = df[df["year"] == 2000][["iso3", "forest_km2"]].rename(columns={"forest_km2": "km2_2000"})
    snap = snap.merge(base, on="iso3", how="left")
    snap["ann_loss"]   = ((snap["km2_2000"] - snap["forest_km2"]) / (LAST_YEAR - 2000)).clip(lower=0)
    snap = snap[snap["ann_loss"] > 10].copy()
    snap["co2_Mt"]     = snap["ann_loss"] * HA_PER_KM2 * snap["cd"] * TC_TO_TCO2 / 1e6
    snap["revenue_M"]  = snap["co2_Mt"] * price
    snap["cost_M"]     = snap["ann_loss"] * HA_PER_KM2 * PROTECTION_COST_HA / 1e6
    snap["net_M"]      = snap["revenue_M"] - snap["cost_M"]
    snap["break_even"] = snap["cost_M"] / snap["co2_Mt"].clip(lower=0.001)

    total_rev    = snap["revenue_M"].sum() / 1000
    total_cost   = snap["cost_M"].sum() / 1000
    net          = snap["net_M"].sum() / 1000
    n_profitable = (snap["net_M"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, color in [
        (c1, f"${total_rev:.0f}B/yr",  "REDD+ revenue potential",    "#16a34a"),
        (c2, f"${total_cost:.0f}B/yr", "Estimated protection cost",  "#d97706"),
        (c3, f"${net:+.0f}B/yr",       "Net at this price",          "#16a34a" if net > 0 else "#dc2626"),
        (c4, f"{n_profitable}",        "Countries where profitable", "#2563eb"),
    ]:
        col.markdown(f'<div class="m-card"><div class="m-label">{lbl}</div>'
                     f'<div class="m-value" style="color:{color}">{val}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

    top20 = snap.nlargest(20, "co2_Mt").copy()
    bfig  = go.Figure()
    bfig.add_trace(go.Bar(name="REDD+ revenue",   x=top20["country"],
                          y=top20["revenue_M"],  marker_color="#16a34a"))
    bfig.add_trace(go.Bar(name="Protection cost", x=top20["country"],
                          y=top20["cost_M"],     marker_color="rgba(148,163,184,0.7)"))
    bfig.update_layout(**_lyt(h=360, margin=dict(l=0, r=0, t=30, b=90),
                              barmode="group",
                              xaxis=_xax(showgrid=False, tickangle=-35),
                              yaxis=_yax(showgrid=True, title="USD M / yr"),
                              legend=dict(orientation="h", y=1.06, font=dict(color=_TC))))
    st.plotly_chart(bfig, use_container_width=True)

    befig = px.scatter(
        snap.nlargest(30, "co2_Mt"),
        x="co2_Mt", y="break_even", size="ann_loss", color="region",
        hover_name="country",
        labels={"co2_Mt": "CO₂ saved if halted (MtCO₂/yr)",
                "break_even": "Break-even ($/tCO₂)"},
        size_max=40, color_discrete_sequence=px.colors.qualitative.Set3,
    )
    befig.add_hline(y=price, line_dash="dash", line_color="#16a34a",
                    annotation_text=f"${price}/tCO₂",
                    annotation_font=dict(color="#16a34a", size=10))
    befig.update_layout(**_lyt(h=360,
                               xaxis=_xax(showgrid=True, type="log",
                                          title="CO₂ saved (MtCO₂/yr, log)"),
                               yaxis=_yax(showgrid=True, title="Break-even ($/tCO₂)"),
                               legend=dict(font=dict(color=_TC, size=10))))
    st.plotly_chart(befig, use_container_width=True)

    st.markdown(f'<div class="method-note">REDD+ revenue = CO₂ saved × carbon price. Protection cost = ${PROTECTION_COST_HA}/ha/yr (Busch et al. 2019 NCC). Break-even = price at which REDD+ becomes self-funding. Points below the green line are profitable at your selected price.</div>',
                unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 07 · THE RESILIENCE STACK</div>
      <h1>🌲 Forests & Deforestation</h1>
      <p style="margin-bottom:1.2rem">What remains · Where it's going · Real satellite imagery · What would actually help</p>
      <div style="display:flex;gap:2rem;flex-wrap:wrap;border-top:1px solid rgba(22,163,74,0.2);padding-top:1rem;margin-top:.2rem">
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#86efac;margin-bottom:.15rem">Forest remaining</div>
          <div style="font-size:1.5rem;font-weight:900;color:#14532d;font-family:'Space Grotesk',sans-serif;letter-spacing:-1px;line-height:1">4.06 Bn ha</div>
        </div>
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#86efac;margin-bottom:.15rem">Lost since 1900</div>
          <div style="font-size:1.5rem;font-weight:900;color:#14532d;font-family:'Space Grotesk',sans-serif;letter-spacing:-1px;line-height:1">1.84 Bn ha</div>
        </div>
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#86efac;margin-bottom:.15rem">Disappearing</div>
          <div style="font-size:1.5rem;font-weight:900;color:#991b1b;font-family:'Space Grotesk',sans-serif;letter-spacing:-1px;line-height:1">1 pitch / 2 sec</div>
        </div>
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#86efac;margin-bottom:.15rem">Carbon locked</div>
          <div style="font-size:1.5rem;font-weight:900;color:#14532d;font-family:'Space Grotesk',sans-serif;letter-spacing:-1px;line-height:1">861 GtCO₂</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading forest data…"):
        df = load_forest_data()

    if df.empty:
        st.error("Failed to load forest data from World Bank.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌿  The Story",
        "🛰️  Forest from Space",
        "🔥  Deforestation",
        "💡  Solutions",
    ])

    with tab1:
        tab_story(df)
    with tab2:
        tab_satellite_map()
    with tab3:
        tab_deforestation(df)
    with tab4:
        tab_solutions(df)

    st.markdown(
        "<div style='text-align:center;color:#334155;font-size:10px;margin-top:2rem;padding-bottom:1rem'>"
        "Day 07 · The Resilience Stack · "
        "World Bank AG.LND.FRST.ZS/K2 · Pan et al. 2011 · Gatti et al. 2021 · "
        "NASA GIBS MODIS Terra True Color · FAO FRA 2020"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
