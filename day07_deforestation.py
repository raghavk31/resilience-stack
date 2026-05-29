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

    # Hero
    st.markdown(f"""
    <div class="m-card" style="border-color:rgba(34,197,94,0.15);padding:1.6rem 1.8rem;margin-bottom:1rem">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
        <div>
          <div class="m-label" style="color:#22c55e">EARTH'S FORESTS — {LAST_YEAR}</div>
          <div style="font-size:3rem;font-weight:900;color:#f0fdf4;line-height:1;letter-spacing:-2px;font-family:'Space Grotesk',sans-serif">
            {total_now / 1e6:.2f}B ha
          </div>
          <div style="font-size:.8rem;color:#4ade80;margin:.3rem 0 .7rem;font-weight:500">of forest remaining on Earth</div>
          <div style="display:flex;gap:.5rem;flex-wrap:wrap">
            <span style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.2);border-radius:4px;padding:3px 10px;font-size:11px;color:#22c55e;font-weight:600">
              📉 {lost_mha:.0f}M ha lost since 1990
            </span>
            <span style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.15);border-radius:4px;padding:3px 10px;font-size:11px;color:#ef4444;font-weight:600">
              ⏱ {loss_per_sec:.1f} ha/sec vanishing
            </span>
          </div>
        </div>
        <div style="text-align:right">
          <div class="m-label">LOST IN {datetime.date.today().year} SO FAR</div>
          <div style="font-size:2.4rem;font-weight:900;color:#ef4444;letter-spacing:-1px;font-family:'Space Grotesk',sans-serif">
            {lost_this_year:,.0f}
          </div>
          <div style="font-size:10px;color:#475569">ha · as of {datetime.date.today().strftime('%b %d')}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Story cards — 2 per row, 4 rows
    cards = [
        # (accent_color, label, number, number_class, headline, body, viz_html)
        ("#22c55e", "TREES REMAINING", "3 trillion",    "c-green",
         "Trees still standing on Earth",
         "Before farming, Earth held 5.6 trillion trees. We have cut nearly half — "
         "2.6 trillion gone. What remains stores 45% of all land-surface carbon.",
         _donut(46, "#dc2626", "#22c55e")),

        ("#ef4444", "ANNUAL CUT", "15 billion",   "c-red",
         "Trees felled every single year",
         "We plant 5 billion back. The net loss is 10 billion trees per year — "
         "a deficit running every year since the 1960s without pause.",
         _bars([(15, "#ef4444", "Cut"), (5, "#22c55e", "Planted")], 15)),

        ("#f59e0b", "REAL-TIME LOSS", f"{loss_per_sec:.1f} ha/sec",  "c-amber",
         "Forest disappearing right now",
         "An area the size of a football pitch lost every two seconds. "
         "The grid below represents what we've lost since 1990 — one pixel per 2%.",
         _pixel_grid(46)),

        ("#ef4444", "AMAZON FLIP", "+0.32 PgC/yr", "c-red",
         "The Amazon crossed its tipping point",
         "In 2021 scientists confirmed: the eastern Amazon emits +0.86 PgC/yr — "
         "more than it absorbs. Earth's greatest forest is now a carbon source.",
         _arrow_flip()),

        ("#60a5fa", "BIODIVERSITY", "80%",          "c-blue",
         "Of all land species live in forests",
         "Jaguars, mountain gorillas, thousands of undiscovered plant compounds. "
         "Forests host 80% of terrestrial biodiversity — each hectare lost, permanently.",
         _mini_progress(80, "#60a5fa", "80% of terrestrial species")),

        ("#a78bfa", "LIVELIHOODS", "1.6 billion",   "c-purple",
         "People whose lives depend on forests",
         "Indigenous communities, smallholder farmers, honey collectors. "
         "Forests are not wilderness to them — they are home, food, and income.",
         _mini_progress(20, "#a78bfa", "20% of humanity directly dependent")),

        ("#2dd4bf", "CARBON SHIELD", f"{total_C:.0f} GtCO₂", "c-teal",
         "Locked in standing trees right now",
         "More carbon than all fossil fuels burned since the Industrial Revolution. "
         "Lose these forests and every 1.5°C target becomes unreachable.",
         _mini_progress(45, "#2dd4bf", "45% of all land carbon stored here")),

        ("#22c55e", "THE SOLUTION", "$12/ha/yr",    "c-green",
         "What it costs to protect a forest",
         "REDD+ carbon credits make protecting forests more profitable than clearing them. "
         "At $50/tonne CO₂, the economics of conservation fully work.",
         _bars([(50, "#22c55e", "Revenue"), (12, "#475569", "Cost")], 50)),
    ]

    for i in range(0, len(cards), 2):
        c1, c2 = st.columns(2)
        for col, card in zip([c1, c2], cards[i:i+2]):
            accent, lbl, num, num_cls, headline, body, viz = card
            col.markdown(f"""
            <div class="s-card">
              <div class="s-card-accent" style="background:{accent}"></div>
              <div class="s-label">{lbl}</div>
              <div class="s-number {num_cls}">{num}</div>
              <div class="s-headline">{headline}</div>
              <div class="s-viz">{viz}</div>
              <div class="s-body">{body}</div>
            </div>
            """, unsafe_allow_html=True)

    # Timeline
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="m-label" style="margin-bottom:.5rem">THE LONG DECLINE — GLOBAL FOREST SINCE 1900</div>',
                unsafe_allow_html=True)
    trend_df = pd.DataFrame(list(GLOBAL_FOREST_GHA.items()), columns=["year", "gha"])
    tf = go.Figure()
    tf.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["gha"],
        mode="lines+markers",
        line=dict(color="#22c55e", width=2.5),
        marker=dict(size=7, color="#16a34a", line=dict(color="#ffffff", width=1.5)),
        fill="tozeroy", fillcolor="rgba(34,197,94,0.06)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f} Gha<extra></extra>",
    ))
    tf.add_annotation(x=2020, y=4.06, text="4.06 Gha today",
                      font=dict(color="#ef4444", size=10, family="Inter"),
                      showarrow=True, arrowcolor="#ef4444", arrowwidth=1, arrowhead=2, ax=40, ay=-25)
    tf.add_annotation(x=1900, y=5.9, text="5.9 Gha · 1900",
                      font=dict(color="#16a34a", size=10, family="Inter"),
                      showarrow=True, arrowcolor="#16a34a", arrowwidth=1, arrowhead=2, ax=10, ay=-25)
    tf.update_layout(**_lyt(h=240, margin=dict(l=0, r=0, t=10, b=0),
                            xaxis=_xax(showgrid=False),
                            yaxis=_yax(showgrid=True, title="Billion ha", range=[3.5, 6.3])))
    st.plotly_chart(tf, use_container_width=True)

    st.markdown('<div class="method-note">Forest area: FAO FRA 2020 + Ramankutty & Foley 1999 (pre-1990). Tree count: Crowther et al. 2015 Nature. Amazon: Gatti et al. 2021 Nature. REDD+: Busch et al. 2019 NCC.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Forest from Space ─────────────────────────────────────────────────

def tab_satellite_map() -> None:
    st.markdown("""
    <div class="m-card" style="margin-bottom:.8rem;padding:1rem 1.2rem">
      <div class="m-label">WHAT YOU'RE LOOKING AT</div>
      <div style="font-size:12px;color:#94a3b8;line-height:1.6;max-width:800px">
        Real satellite data — NASA MODIS Terra Vegetation Index (NDVI), 250m resolution.
        <span style="color:#22c55e">Bright green</span> = dense forest &amp; vegetation.
        <span style="color:#92400e">Brown/dark</span> = cleared land, desert, or urban.
        Drag the divider to compare two years of forest coverage.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right, col_focus = st.columns([2, 2, 2])
    with col_left:
        yr_left  = st.selectbox("Earlier year (left)", COMPARE_YEARS,
                                index=0, key="yr_l",
                                help="Drag the map divider left to reveal this year")
    with col_right:
        yr_right = st.selectbox("Later year (right)", COMPARE_YEARS,
                                index=len(COMPARE_YEARS)-1, key="yr_r",
                                help="Drag the map divider right to reveal this year")
    with col_focus:
        region_name = st.selectbox("Focus region", list(FOREST_REGIONS.keys()),
                                   index=0, key="focus")

    center, zoom = FOREST_REGIONS[region_name]

    # Build Folium map
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        prefer_canvas=True,
    )

    # Dark base
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="© CARTO · © OpenStreetMap",
        name="Dark base",
        overlay=False,
        control=False,
    ).add_to(m)

    # NDVI layers for both years — WMTS row/col = {y}/{x} in Leaflet notation
    layer_left = folium.TileLayer(
        tiles=_gibs_ndvi_url(yr_left),
        attr=f"NASA GIBS MODIS Terra NDVI {yr_left}",
        name=str(yr_left),
        overlay=True,
        control=False,
        opacity=0.92,
    )
    layer_right = folium.TileLayer(
        tiles=_gibs_ndvi_url(yr_right),
        attr=f"NASA GIBS MODIS Terra NDVI {yr_right}",
        name=str(yr_right),
        overlay=True,
        control=False,
        opacity=0.92,
    )
    layer_left.add_to(m)
    layer_right.add_to(m)

    # Side-by-side divider
    sbs = SideBySideLayers(layer_left=layer_left, layer_right=layer_right)
    sbs.add_to(m)

    # Annotate major forest regions
    forest_pins = [
        ([-5, -58],   "🌿 Amazon", "5.5M km² · world's largest tropical forest"),
        ([-1, 24],    "🌲 Congo",  "3.7M km² · world's second largest tropical forest"),
        ([1, 115],    "🌴 Borneo", "Most biodiverse forest on Earth"),
        ([60, 100],   "🌨️ Taiga",  "12M km² · world's largest forest biome"),
        ([56, -100],  "🍁 Boreal Canada", "3.4M km² of intact boreal forest"),
    ]
    for loc, title, desc in forest_pins:
        folium.Marker(
            location=loc,
            tooltip=folium.Tooltip(
                f"<b style='font-size:11px'>{title}</b><br>"
                f"<span style='font-size:10px;color:#888'>{desc}</span>",
                sticky=False,
            ),
            icon=folium.DivIcon(
                html=f'<div style="background:#ffffff;border:1px solid #16a34a;color:#16a34a;'
                     f'font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;'
                     f'white-space:nowrap;font-family:Inter,sans-serif">{title}</div>',
                icon_size=(120, 22),
                icon_anchor=(60, 11),
            ),
        ).add_to(m)

    # Year labels on map edges
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:absolute;top:16px;left:20px;z-index:1000;
         background:rgba(11,11,17,0.85);border:1px solid rgba(34,197,94,0.3);
         color:#22c55e;font-family:Inter,sans-serif;font-size:12px;font-weight:700;
         padding:4px 10px;border-radius:4px">{yr_left}</div>
    <div style="position:absolute;top:16px;right:20px;z-index:1000;
         background:rgba(11,11,17,0.85);border:1px solid rgba(239,68,68,0.3);
         color:#ef4444;font-family:Inter,sans-serif;font-size:12px;font-weight:700;
         padding:4px 10px;border-radius:4px">{yr_right}</div>
    """))

    st_folium(m, height=580, use_container_width=True, returned_objects=[])

    st.markdown(f"""
    <div class="method-note">
      Data: NASA GIBS MODIS Terra Vegetation Indices Monthly 250m · NDVI composite June {yr_left} vs June {yr_right}.
      Green = vegetation (forest / crops). Brown = bare ground / urban. Drag the divider on the map to compare years.
      Zoom into the Amazon, Congo Basin, or Borneo to see pixel-level deforestation in detail.
    </div>
    """, unsafe_allow_html=True)


# ── Tab 3 — Deforestation ─────────────────────────────────────────────────────

def tab_deforestation(df: pd.DataFrame) -> None:
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
        (f"{total_km2/1e6:.2f}M km²",   f"Forest lost {period}",       "#ef4444"),
        (f"{carbon_Gt:.1f} GtCO₂",      "Carbon released equivalent",  "#f59e0b"),
        (f"{total_km2/242495:.1f}× UK", "Area equivalent",             "#60a5fa"),
        (f"{ha_day/0.714:,.0f}/day",    "Football pitches lost daily", "#ef4444"),
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
    <div class="m-card" style="border-color:rgba(239,68,68,0.15)">
      <div class="m-label" style="color:#ef4444">THE AMAZON TIPPING POINT — 2021</div>
      <div style="font-size:12px;color:#94a3b8;line-height:1.7">
        The eastern Amazon now emits <b style="color:#ef4444">+0.86 PgC/yr</b>.
        The western Amazon is still a sink (−0.54 PgC/yr).
        Net result: Earth's greatest forest crossed its <b style="color:#f1f5f9">carbon tipping point</b>.
        59% from fires · 41% from deforestation-driven degradation.
        <br><span style="font-size:10px;color:#334155">Gatti et al. 2021, Nature · doi:10.1038/s41586-021-03629-6</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest area: World Bank AG.LND.FRST.ZS/K2. Carbon = area × density (Pan et al. 2011). UK 242,495 km². FIFA pitch 0.714 ha.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — Solutions ─────────────────────────────────────────────────────────

def tab_solutions(df: pd.DataFrame) -> None:
    st.markdown('<div class="m-label" style="margin-bottom:.6rem">REDD+ — CAN PROTECTING FORESTS PAY FOR ITSELF?</div>',
                unsafe_allow_html=True)

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
        (c1, f"${total_rev:.0f}B/yr",  "REDD+ revenue potential",    "#22c55e"),
        (c2, f"${total_cost:.0f}B/yr", "Estimated protection cost",  "#f59e0b"),
        (c3, f"${net:+.0f}B/yr",       "Net at this price",          "#22c55e" if net > 0 else "#ef4444"),
        (c4, f"{n_profitable}",        "Countries where profitable", "#60a5fa"),
    ]:
        col.markdown(f'<div class="m-card"><div class="m-label">{lbl}</div>'
                     f'<div class="m-value" style="color:{color}">{val}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

    top20 = snap.nlargest(20, "co2_Mt").copy()
    bfig  = go.Figure()
    bfig.add_trace(go.Bar(name="REDD+ revenue",   x=top20["country"],
                          y=top20["revenue_M"],  marker_color="#22c55e"))
    bfig.add_trace(go.Bar(name="Protection cost", x=top20["country"],
                          y=top20["cost_M"],     marker_color="rgba(71,85,105,0.6)"))
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
    befig.add_hline(y=price, line_dash="dash", line_color="#22c55e",
                    annotation_text=f"${price}/tCO₂",
                    annotation_font=dict(color="#22c55e", size=10))
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
      <p>What remains · Where it's going · Real satellite imagery · What would actually help</p>
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
        "NASA GIBS MODIS Terra NDVI · FAO FRA 2020"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
