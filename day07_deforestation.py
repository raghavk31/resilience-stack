"""
The Resilience Stack — Day 07 (V2 · Beautiful Redesign)
Deforestation & Carbon Sink Tracker

Dark glassmorphism · Story cards · Animated forest cartography · Year comparison
Sources: World Bank AG.LND.FRST.ZS / AG.LND.FRST.K2
         Pan et al. 2011 Science · Gatti et al. 2021 Nature
         FAO FRA 2020 · Busch et al. 2019 Nature Climate Change
         Crowther et al. 2015 Nature (global tree count)
"""

import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests

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
    "COG": 160, "GNQ": 155, "BLZ": 130,
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

AMAZON = {"eastern_source_pgc": 0.86, "western_sink_pgc": 0.54, "net_pgc": 0.32}

# Global forest area estimates (Gha) — FAO FRA 2020 + historical reconstructions
GLOBAL_FOREST_GHA = {1900: 5.9, 1950: 5.5, 1960: 5.4, 1970: 5.2, 1980: 5.0,
                     1990: 4.28, 2000: 4.17, 2010: 4.10, 2015: 4.07, 2020: 4.06}

# Map years available from World Bank data
MAP_YEARS = [1990, 1995, 2000, 2005, 2010, 2015, 2020]


# ── CSS — Dark Glassmorphism ──────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Background ── */
.stApp {
    background: linear-gradient(160deg, #060e08 0%, #0a1a0f 45%, #071410 100%);
}
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
section.main,
[data-testid="block-container"] {
    background: transparent !important;
}

/* ── Text on dark ── */
p, li, span, div { color: #e2f5ea; }
label, .stRadio label span, .stSelectbox label, .stSlider label {
    color: #86efac !important;
}
h1, h2, h3, h4 { color: #f0fdf4; }
.stMarkdown p { color: #d1fae5; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 4px;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    color: rgba(134,239,172,0.55);
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: .88rem;
}
.stTabs [aria-selected="true"] {
    background: rgba(74,222,128,0.12) !important;
    color: #4ade80 !important;
    font-weight: 600;
}

/* ── Glass card ── */
.glass {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 20px;
    padding: 1.6rem 1.8rem;
    color: #f0fdf4;
    margin-bottom: .6rem;
}
.glass-sm {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    color: #f0fdf4;
}
.glass-warn {
    background: rgba(251,191,36,0.07);
    border: 1px solid rgba(251,191,36,0.2);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
}
.glass-crit {
    background: rgba(248,113,113,0.07);
    border: 1px solid rgba(248,113,113,0.2);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
}

/* ── Story card ── */
.story-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 1.8rem 1.6rem;
    height: 100%;
    position: relative;
    overflow: hidden;
}
.story-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 20px 20px 0 0;
}
.story-card.green::before  { background: linear-gradient(90deg, #22c55e, #4ade80); }
.story-card.amber::before  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.story-card.red::before    { background: linear-gradient(90deg, #ef4444, #f87171); }
.story-card.blue::before   { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.story-card.purple::before { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.story-card.teal::before   { background: linear-gradient(90deg, #14b8a6, #2dd4bf); }

.story-icon {
    font-size: 2.2rem;
    margin-bottom: .8rem;
    display: block;
}
.story-number {
    font-size: 2.6rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: -1px;
    margin-bottom: .3rem;
}
.story-number.green  { color: #4ade80; }
.story-number.amber  { color: #fbbf24; }
.story-number.red    { color: #f87171; }
.story-number.blue   { color: #60a5fa; }
.story-number.purple { color: #a78bfa; }
.story-number.teal   { color: #2dd4bf; }

.story-headline {
    font-size: 1rem;
    font-weight: 700;
    color: #f0fdf4;
    margin-bottom: .5rem;
    line-height: 1.3;
}
.story-body {
    font-size: .82rem;
    color: rgba(209,250,229,.7);
    line-height: 1.65;
}

/* ── Stat pill ── */
.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    background: rgba(74,222,128,0.1);
    border: 1px solid rgba(74,222,128,0.2);
    border-radius: 999px;
    padding: .3rem .9rem;
    font-size: .78rem;
    font-weight: 600;
    color: #4ade80;
    margin: .2rem .15rem;
}
.stat-pill.amber {
    background: rgba(251,191,36,0.1);
    border-color: rgba(251,191,36,0.2);
    color: #fbbf24;
}
.stat-pill.red {
    background: rgba(248,113,113,0.1);
    border-color: rgba(248,113,113,0.2);
    color: #f87171;
}

/* ── Progress bar ── */
.prog-track {
    background: rgba(255,255,255,0.08);
    border-radius: 999px;
    height: 6px;
    margin: .4rem 0 .2rem;
    overflow: hidden;
}
.prog-fill {
    height: 100%;
    border-radius: 999px;
}

/* ── Stat grid ── */
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; margin: .8rem 0; }
.stat-block { text-align: center; }
.stat-v { font-size: 1.5rem; font-weight: 800; color: #4ade80; line-height: 1; }
.stat-l { font-size: .7rem; color: rgba(134,239,172,.65); margin-top: .15rem; }

/* ── Header ── */
.rs-header {
    background: linear-gradient(135deg, #0a2a10 0%, #0d3b18 50%, #0a2a10 100%);
    border: 1px solid rgba(74,222,128,.12);
    border-radius: 20px;
    padding: 2rem 2.5rem 1.8rem;
    color: #fff;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.rs-header::after {
    content: '🌲';
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 5rem;
    opacity: .08;
}
.rs-header h1 { font-size: 2rem; font-weight: 900; margin: 0 0 .25rem; letter-spacing: -.5px; color: #f0fdf4; }
.rs-header p  { font-size: .95rem; color: #86efac; margin: 0; }
.rs-badge {
    display: inline-block;
    background: rgba(74,222,128,.12);
    border: 1px solid rgba(74,222,128,.2);
    border-radius: 999px;
    padding: 2px 12px;
    font-size: .72rem;
    font-weight: 700;
    color: #4ade80;
    margin-bottom: .6rem;
    letter-spacing: .5px;
}

/* ── Method note ── */
.method-note {
    background: rgba(255,255,255,.03);
    border-left: 2px solid rgba(74,222,128,.3);
    padding: .6rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: .75rem;
    color: rgba(134,239,172,.6);
    margin-top: 1.2rem;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,.06) !important; }

/* ── Sidebar hide ── */
section[data-testid="stSidebar"] { display: none; }

/* ── Select / slider ── */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: rgba(255,255,255,.06) !important;
    border-color: rgba(255,255,255,.1) !important;
    color: #f0fdf4 !important;
}
[data-testid="stSlider"] > div { color: #86efac; }
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _net_change(df: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
    s = df[df["year"] == y0][["iso3", "country", "name", "region", "forest_km2", "cd"]].rename(
        columns={"forest_km2": "km2_0"})
    e = df[df["year"] == y1][["iso3", "forest_km2", "forest_pct"]].rename(
        columns={"forest_km2": "km2_1"})
    m = s.merge(e, on="iso3", how="inner").dropna(subset=["km2_0", "km2_1"])
    m["delta_km2"] = m["km2_1"] - m["km2_0"]
    m["delta_pct"] = m["delta_km2"] / m["km2_0"] * 100
    return m


def _prog(pct: float, color: str = "#4ade80") -> str:
    return (f'<div class="prog-track">'
            f'<div class="prog-fill" style="width:{min(pct,100):.0f}%;background:{color}"></div>'
            f'</div>')


def _plotly_dark_layout() -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.02)",
        font=dict(family="Inter", color="#d1fae5"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", showgrid=True,
                   zerolinecolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", showgrid=True,
                   zerolinecolor="rgba(255,255,255,0.08)"),
        margin=dict(l=0, r=0, t=40, b=0),
    )


# ── Tab 1 — The Story ─────────────────────────────────────────────────────────

def tab_story(df: pd.DataFrame) -> None:
    snap   = df[df["year"] == LAST_YEAR]
    base   = df[df["year"] == FIRST_YEAR]
    common = set(snap["iso3"]) & set(base["iso3"])

    total_now  = snap[snap["iso3"].isin(common)]["forest_km2"].sum()
    total_1990 = base[base["iso3"].isin(common)]["forest_km2"].sum()
    lost_mha   = (total_1990 - total_now) * HA_PER_KM2 / 1e6
    total_C    = snap["carbon_GtCO2"].sum()

    annual_loss_km2 = (total_1990 - total_now) / (LAST_YEAR - FIRST_YEAR)
    annual_loss_ha  = annual_loss_km2 * HA_PER_KM2
    loss_per_sec    = annual_loss_ha / (365.25 * 86400)
    days_elapsed    = (datetime.date.today() - datetime.date(datetime.date.today().year, 1, 1)).days
    lost_this_year  = int(annual_loss_ha * days_elapsed / 365.25)

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="glass" style="margin-bottom:1.2rem;background:linear-gradient(135deg,rgba(22,101,52,0.18),rgba(10,26,15,0.4))">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
        <div>
          <div style="font-size:.75rem;font-weight:700;letter-spacing:.1em;color:#4ade80;margin-bottom:.4rem">
            EARTH'S FORESTS — {LAST_YEAR} SNAPSHOT
          </div>
          <div style="font-size:3.2rem;font-weight:900;color:#f0fdf4;line-height:1;letter-spacing:-2px">
            {total_now / 1e6:.2f}B
          </div>
          <div style="font-size:1rem;color:#86efac;margin-top:.2rem">hectares of forest remaining</div>
          <div style="margin-top:.8rem">
            <span class="stat-pill">🌍 Down from {total_1990/1e6:.2f}B ha in 1990</span>
            <span class="stat-pill amber">⬇ {lost_mha:.0f}M ha lost since 1990</span>
            <span class="stat-pill red">🔥 {loss_per_sec:.1f} ha vanishing per second</span>
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:.72rem;color:rgba(134,239,172,.5);margin-bottom:.3rem">LOST SO FAR THIS YEAR</div>
          <div style="font-size:2.4rem;font-weight:900;color:#f87171;letter-spacing:-1px">{lost_this_year:,.0f}</div>
          <div style="font-size:.78rem;color:rgba(134,239,172,.5)">hectares · as of {datetime.date.today().strftime('%b %d, %Y')}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Story cards grid ──────────────────────────────────────────────────────
    cards = [
        ("green",  "🌲", "3 trillion",      "Trees still standing",
         "Before farming and cities began, Earth had an estimated 5.6 trillion trees. "
         "We've cut down nearly half — 2.6 trillion gone. What remains stores 45% of all carbon on land.",
         46),
        ("amber",  "🪓", "15 billion",      "Trees cut every single year",
         "We plant 5 billion back. Net loss: 10 billion trees per year — enough to circle "
         "the equator more than 100 times, laid end to end. Every year.",
         None),
        ("red",    "⏱️", f"{loss_per_sec:.1f} ha/sec", "Forest disappearing right now",
         "An area the size of a football pitch lost every two seconds. "
         "By the time you finish reading this card, another 30 hectares will be gone — permanently.",
         None),
        ("red",    "🔄", "+0.32 PgC/yr",   "The Amazon has flipped",
         "In 2021, scientists confirmed it: the eastern Amazon now emits more CO₂ than it absorbs. "
         "Earth's largest rainforest — once a vital carbon sink — crossed its tipping point.",
         None),
        ("blue",   "🦜", "80%",             "Of land species live in forests",
         "Forests host 80% of all terrestrial biodiversity. Each species lost to deforestation "
         "is gone forever — including thousands of plants with undiscovered medicinal properties.",
         80),
        ("purple", "👨‍👩‍👧", "1.6 billion",     "People whose lives depend on forests",
         "Indigenous communities, smallholder farmers, timber workers, honey collectors. "
         "Forests are not wilderness to them — they are home, food, income, and identity.",
         None),
        ("teal",   "🛡️", f"{total_C:.0f} GtCO₂", "Locked away in standing trees",
         "More carbon than all fossil fuels burned since the Industrial Revolution. "
         "Lose these forests and every climate target — Paris, net zero, 1.5°C — becomes unreachable.",
         None),
        ("green",  "✅", "$12/ha/yr",       "What it costs to protect a forest",
         "REDD+ carbon credits can make protecting forests more profitable than clearing them. "
         "At $50/tonne CO₂, protection pays for itself — the economics of conservation finally work.",
         None),
    ]

    for i in range(0, len(cards), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(cards):
                break
            acc, icon, num, headline, body, pct = cards[i + j]
            prog_html = _prog(pct, "#4ade80" if acc == "green" else "#f87171") if pct else ""
            col.markdown(f"""
            <div class="story-card {acc}">
              <span class="story-icon">{icon}</span>
              <div class="story-number {acc}">{num}</div>
              <div class="story-headline">{headline}</div>
              <div class="story-body">{body}</div>
              {prog_html}
              {'<div style="font-size:.7rem;color:rgba(134,239,172,.45);margin-top:.3rem">' + str(pct) + '% gone since civilisation began</div>' if pct else ''}
            </div>
            """, unsafe_allow_html=True)

    # ── Global trend timeline ─────────────────────────────────────────────────
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#4ade80;margin-bottom:.8rem">THE LONG VIEW — GLOBAL FOREST AREA SINCE 1900</div>',
                unsafe_allow_html=True)

    trend_df = pd.DataFrame(list(GLOBAL_FOREST_GHA.items()), columns=["year", "forest_Gha"])
    tfig = go.Figure()
    tfig.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["forest_Gha"],
        mode="lines+markers",
        line=dict(color="#4ade80", width=3),
        marker=dict(size=8, color="#4ade80"),
        fill="tozeroy",
        fillcolor="rgba(74,222,128,0.07)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f} billion hectares<extra></extra>",
    ))
    tfig.add_annotation(x=2020, y=4.06, text="4.06 Gha today",
                        font=dict(color="#f87171", size=11), showarrow=True,
                        arrowcolor="#f87171", arrowwidth=1.5, arrowhead=2,
                        ax=40, ay=-30)
    tfig.add_annotation(x=1900, y=5.9, text="5.9 Gha in 1900",
                        font=dict(color="#4ade80", size=11), showarrow=True,
                        arrowcolor="#4ade80", arrowwidth=1.5, arrowhead=2,
                        ax=-10, ay=-30)
    layout = _plotly_dark_layout()
    layout.update(height=280,
                  xaxis=dict(**layout.get("xaxis", {}), title="", showgrid=False),
                  yaxis=dict(**layout.get("yaxis", {}), title="Global forest (billion ha)",
                             range=[3.5, 6.2]))
    tfig.update_layout(**layout)
    st.plotly_chart(tfig, use_container_width=True)

    st.markdown('<div class="method-note">Forest area: FAO Global Forest Resources Assessment 2020 + historical reconstructions (Ramankutty & Foley 1999 for pre-1990). Tree count: Crowther et al. 2015 Nature. Amazon flux: Gatti et al. 2021 Nature. REDD+ cost: Busch et al. 2019 Nature Climate Change.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Forest Cartography ────────────────────────────────────────────────

def tab_forest_map(df: pd.DataFrame) -> None:
    view = st.radio(
        "View mode",
        ["📅 Year explorer", "⬅️ Before & after", "📊 Net change 1990 → 2020"],
        horizontal=True, key="t2_view",
    )

    if view.startswith("📅"):
        # ── Single year choropleth with year slider ────────────────────────
        year = st.select_slider(
            "Slide through time",
            options=MAP_YEARS,
            value=2020,
            key="t2_year",
            format_func=lambda y: f"🌍  {y}",
        )
        snap_y = df[df["year"] == year]
        total_Gha = snap_y["forest_km2"].sum() * HA_PER_KM2 / 1e9
        base_y    = df[df["year"] == 1990]
        total_90  = base_y["forest_km2"].sum() * HA_PER_KM2 / 1e9
        lost_pct  = (total_90 - total_Gha) / total_90 * 100 if total_90 > 0 else 0

        c1, c2, c3 = st.columns(3)
        for col, val, lbl in [
            (c1, f"{total_Gha:.2f} Gha", f"Global forest cover {year}"),
            (c2, f"−{(total_90 - total_Gha):.2f} Gha", f"Lost vs 1990 baseline"),
            (c3, f"{lost_pct:.1f}%", f"Of 1990 forest gone by {year}"),
        ]:
            col.markdown(f'<div class="glass-sm"><div style="font-size:1.5rem;font-weight:800;color:#4ade80">{val}</div><div style="font-size:.73rem;color:rgba(134,239,172,.6);margin-top:.2rem">{lbl}</div></div>',
                         unsafe_allow_html=True)

        fig = _make_forest_choropleth(snap_y, year)
        st.plotly_chart(fig, use_container_width=True)

        # Country trend
        st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#4ade80;margin:.8rem 0 .4rem">COUNTRY TREND</div>',
                    unsafe_allow_html=True)
        countries = sorted(df["country"].dropna().unique())
        sel = st.selectbox("", countries,
                           index=countries.index("Brazil") if "Brazil" in countries else 0,
                           key="t2_country", label_visibility="collapsed")
        _render_country_trend(df, sel)

    elif view.startswith("⬅️"):
        # ── Side-by-side before/after ──────────────────────────────────────
        col_l, col_r = st.columns(2)
        with col_l:
            y_a = st.selectbox("Earlier year", MAP_YEARS, index=0, key="ya")
        with col_r:
            y_b = st.selectbox("Later year", MAP_YEARS, index=len(MAP_YEARS)-1, key="yb")

        snap_a = df[df["year"] == y_a]
        snap_b = df[df["year"] == y_b]

        fig = make_subplots(rows=1, cols=2,
                            subplot_titles=[f"🌍 {y_a}", f"🌍 {y_b}"],
                            specs=[[{"type": "choropleth"}, {"type": "choropleth"}]])

        for col_idx, (snap, yr) in enumerate([(snap_a, y_a), (snap_b, y_b)], 1):
            fig.add_trace(
                go.Choropleth(
                    locations=snap["iso3"], z=snap["forest_pct"],
                    colorscale=[
                        [0.00, "#4a3728"], [0.15, "#7d6235"],
                        [0.30, "#6b8e4e"], [0.55, "#2d7d2d"],
                        [0.80, "#166016"], [1.00, "#0a3d0a"],
                    ],
                    zmin=0, zmax=80,
                    showscale=(col_idx == 2),
                    colorbar=dict(title="Forest %", thickness=10, len=0.6,
                                  tickfont=dict(color="#86efac"), title_font=dict(color="#86efac"))
                    if col_idx == 2 else None,
                    marker_line_color="rgba(255,255,255,0.06)",
                    marker_line_width=0.4,
                    hovertemplate="<b>%{location}</b><br>Forest: %{z:.1f}%<extra></extra>",
                ),
                row=1, col=col_idx,
            )

        fig.update_geos(
            showframe=False, showcoastlines=True, coastlinecolor="rgba(255,255,255,0.1)",
            bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="rgba(255,255,255,0.06)",
            showocean=True, oceancolor="#081629",
            showlakes=False, showrivers=False,
            projection_type="natural earth",
        )
        fig.update_layout(
            height=460, paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#d1fae5"),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Delta stats
        common = set(snap_a["iso3"]) & set(snap_b["iso3"])
        a_tot = snap_a[snap_a["iso3"].isin(common)]["forest_km2"].sum()
        b_tot = snap_b[snap_b["iso3"].isin(common)]["forest_km2"].sum()
        delta_Mha = (b_tot - a_tot) * HA_PER_KM2 / 1e6
        delta_pct = (b_tot - a_tot) / a_tot * 100

        colour = "#f87171" if delta_Mha < 0 else "#4ade80"
        st.markdown(f"""
        <div class="glass-sm" style="text-align:center;margin-top:.6rem">
          <span style="font-size:2rem;font-weight:900;color:{colour}">{delta_Mha:+.0f} Mha</span>
          <span style="font-size:.85rem;color:rgba(134,239,172,.6);margin-left:.5rem">
            ({delta_pct:+.1f}%) between {y_a} and {y_b}
          </span>
        </div>
        """, unsafe_allow_html=True)

    else:
        # ── Net change choropleth 1990→2020 ───────────────────────────────
        chg = _net_change(df, 1990, 2020)
        chg["change_label"] = chg["delta_pct"].apply(
            lambda x: "Large gain (>10%)" if x > 10
            else ("Moderate gain" if x > 2
                  else ("Stable (±2%)" if x > -2
                        else ("Moderate loss" if x > -10
                              else "Large loss (>10%)"))))

        fig = px.choropleth(
            chg, locations="iso3", color="delta_pct",
            color_continuous_scale=[
                [0.0,  "#7f1d1d"],
                [0.25, "#c2410c"],
                [0.42, "#6b7280"],
                [0.6,  "#166534"],
                [1.0,  "#052e16"],
            ],
            range_color=[-25, 15],
            hover_name="country",
            hover_data={"iso3": False, "delta_pct": ":.1f", "delta_km2": ":,.0f"},
            labels={"delta_pct": "Change (%)"},
            title="Net forest change 1990 → 2020",
        )
        _style_geo(fig)
        fig.update_layout(
            height=500, paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#d1fae5"),
            coloraxis_colorbar=dict(
                title="Change %", thickness=12, len=0.6,
                tickvals=[-25, -10, -2, 0, 10, 15],
                ticktext=["−25 Large loss", "−10", "−2", "0", "+10", "+15 Gain"],
                tickfont=dict(color="#86efac"),
                title_font=dict(color="#86efac"),
            ),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Biggest losers & gainers callout
        losers  = chg.nsmallest(5, "delta_pct")[["country", "delta_pct", "delta_km2"]]
        gainers = chg.nlargest(5, "delta_pct")[["country", "delta_pct", "delta_km2"]]

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#f87171;margin-bottom:.5rem">BIGGEST LOSSES 1990→2020</div>',
                        unsafe_allow_html=True)
            for _, row in losers.iterrows():
                st.markdown(f'<div class="glass-crit" style="margin-bottom:.4rem"><b style="color:#f87171">{row.country}</b> &nbsp;<span style="color:rgba(209,250,229,.5);font-size:.8rem">{row.delta_pct:.1f}% · {row.delta_km2/1000:,.0f}k km²</span></div>',
                            unsafe_allow_html=True)
        with col_r:
            st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#4ade80;margin-bottom:.5rem">BIGGEST GAINS 1990→2020</div>',
                        unsafe_allow_html=True)
            for _, row in gainers.iterrows():
                st.markdown(f'<div class="glass-sm" style="margin-bottom:.4rem"><b style="color:#4ade80">{row.country}</b> &nbsp;<span style="color:rgba(209,250,229,.5);font-size:.8rem">+{row.delta_pct:.1f}% · +{row.delta_km2/1000:,.0f}k km²</span></div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest cover: World Bank AG.LND.FRST.ZS / AG.LND.FRST.K2 · FAO Global Forest Resources Assessment · satellite-era data 1990–2020. Color scale: brown = low cover, deep green = dense forest, navy = ocean.</div>',
                unsafe_allow_html=True)


def _make_forest_choropleth(snap: pd.DataFrame, year: int) -> go.Figure:
    fig = px.choropleth(
        snap, locations="iso3", color="forest_pct",
        color_continuous_scale=[
            [0.00, "#4a3728"],
            [0.10, "#7d6235"],
            [0.25, "#8aad5a"],
            [0.45, "#4a8a3a"],
            [0.70, "#206020"],
            [1.00, "#0a3d0a"],
        ],
        range_color=[0, 80],
        hover_name="country",
        hover_data={"iso3": False, "forest_km2": ":,.0f", "forest_pct": ":.1f"},
        labels={"forest_pct": "Forest cover (%)"},
        title=f"Forest cover of land area — {year}",
    )
    _style_geo(fig)
    fig.update_layout(
        height=500, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#d1fae5"),
        coloraxis_colorbar=dict(
            title="Forest %", thickness=12, len=0.6,
            tickvals=[0, 10, 20, 40, 60, 80],
            ticktext=["0", "10%", "20%", "40%", "60%", "80% dense"],
            tickfont=dict(color="#86efac"),
            title_font=dict(color="#86efac"),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def _style_geo(fig: go.Figure) -> None:
    fig.update_geos(
        showframe=False, showcoastlines=True, coastlinecolor="rgba(255,255,255,0.12)",
        bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="rgba(255,255,255,0.07)",
        showocean=True, oceancolor="#081629",
        showlakes=True, lakecolor="#0c1e35",
        showrivers=False, showland=True, landcolor="#2a2118",
        projection_type="natural earth",
    )


def _render_country_trend(df: pd.DataFrame, country: str) -> None:
    cdf = df[df["country"] == country].sort_values("year")
    if cdf.empty:
        return
    cfig = go.Figure()
    cfig.add_trace(go.Scatter(
        x=cdf["year"], y=cdf["forest_km2"] / 1e3,
        mode="lines+markers",
        line=dict(color="#4ade80", width=2.5),
        marker=dict(size=6, color="#4ade80"),
        fill="tozeroy",
        fillcolor="rgba(74,222,128,0.06)",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}k km²<extra></extra>",
    ))
    layout = _plotly_dark_layout()
    layout.update(
        height=240, title=dict(text=f"{country} — forest area trend", font=dict(size=13, color="#86efac")),
        yaxis=dict(**layout.get("yaxis", {}), title="Forest (thousand km²)"),
        xaxis=dict(**layout.get("xaxis", {}), showgrid=False),
    )
    cfig.update_layout(**layout)
    st.plotly_chart(cfig, use_container_width=True)


# ── Tab 3 — Deforestation ─────────────────────────────────────────────────────

def tab_deforestation(df: pd.DataFrame) -> None:
    PERIODS = {
        "1990 → 2000": (1990, 2000),
        "2000 → 2010": (2000, 2010),
        "2010 → 2020": (2010, 2020),
        "All time (1990 → 2020)": (1990, 2020),
    }
    col_l, col_r = st.columns([2, 2])
    with col_l:
        period = st.selectbox("Time period", list(PERIODS.keys()), index=2, key="t3_period")
    with col_r:
        view = st.radio("Rank by", ["Absolute loss (km²)", "Rate (% of forest)"],
                        horizontal=True, key="t3_view")

    y0, y1   = PERIODS[period]
    chg      = _net_change(df, y0, y1)
    losers   = chg[chg["delta_km2"] < 0].copy()
    losers["abs_loss"] = -losers["delta_km2"]
    losers["rate"]     = -losers["delta_pct"]
    n_years  = y1 - y0

    total_km2  = losers["abs_loss"].sum()
    carbon_Gt  = (losers["abs_loss"] * HA_PER_KM2 * losers["cd"] * TC_TO_TCO2 / 1e9).sum()
    rate_km2yr = total_km2 / n_years

    # Relatable comparisons
    uk_km2       = 242_495
    football_ha  = 0.714
    ha_lost_day  = rate_km2yr * HA_PER_KM2 / 365.25
    fields_day   = ha_lost_day / football_ha

    c1, c2, c3, c4 = st.columns(4)
    facts = [
        (f"{total_km2/1e6:.2f}M km²", f"Forest lost {period}"),
        (f"{carbon_Gt:.1f} GtCO₂", "Carbon released equivalent"),
        (f"{total_km2/uk_km2:.1f}× UK", "Area equivalent"),
        (f"{fields_day:,.0f}/day", "Football pitches lost daily"),
    ]
    for col, (val, lbl) in zip([c1, c2, c3, c4], facts):
        col.markdown(f'<div class="glass-sm"><div style="font-size:1.45rem;font-weight:800;color:#f87171">{val}</div><div style="font-size:.72rem;color:rgba(134,239,172,.55);margin-top:.2rem">{lbl}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    x_col = "abs_loss" if view.startswith("Absolute") else "rate"
    x_lbl = "Forest lost (km²)" if view.startswith("Absolute") else "Loss (% of 1990 forest)"
    top = losers.nlargest(20, x_col).sort_values(x_col)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top[x_col], y=top["country"], orientation="h",
        marker=dict(
            color=top[x_col],
            colorscale=[[0, "#7f1d1d"], [0.5, "#dc2626"], [1, "#f87171"]],
            showscale=False,
        ),
        text=top[x_col].apply(lambda v: f"{v:,.0f}" if view.startswith("Absolute") else f"{v:.1f}%"),
        textposition="outside",
        textfont=dict(color="#d1fae5", size=10),
        hovertemplate="<b>%{y}</b><br>" + x_lbl + ": %{x:,.0f}<extra></extra>",
    ))
    layout = _plotly_dark_layout()
    layout.update(height=560, xaxis=dict(**layout.get("xaxis", {}), title=x_lbl),
                  yaxis=dict(**layout.get("yaxis", {}), showgrid=False),
                  margin=dict(l=0, r=80, t=10, b=0))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(127,29,29,0.25),rgba(153,27,27,0.15));
                border:1px solid rgba(248,113,113,0.2);border-radius:16px;padding:1.4rem 1.6rem;margin:1rem 0">
      <div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#f87171;margin-bottom:.5rem">THE AMAZON TIPPING POINT</div>
      <div style="font-size:.9rem;color:#fca5a5;line-height:1.7">
        In 2021, measurements confirmed what scientists feared: the <b style="color:#fff">eastern Amazon</b>
        now emits <b style="color:#f87171">+0.86 PgC/yr</b> — more CO₂ than it absorbs.
        The western Amazon is still a sink (−0.54 PgC/yr), but the net result is that
        Earth's greatest forest has <b style="color:#fff">crossed its carbon tipping point</b>.
        59% of the flux comes from fires; 41% from deforestation-driven forest degradation.<br>
        <span style="font-size:.78rem;color:rgba(252,165,165,.55)">Gatti et al. 2021, Nature · doi:10.1038/s41586-021-03629-6</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest area: World Bank AG.LND.FRST.ZS/K2. Carbon released = area lost × carbon density (Pan et al. 2011 Science). Relatable comparisons use UK land area 242,495 km², FIFA pitch 0.714 ha.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — Solutions ─────────────────────────────────────────────────────────

def tab_solutions(df: pd.DataFrame) -> None:
    st.markdown("""
    <div style="font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#4ade80;margin-bottom:1rem">
      WHAT WOULD IT ACTUALLY TAKE TO STOP DEFORESTATION?
    </div>
    """, unsafe_allow_html=True)

    price = st.slider("Carbon price ($/tCO₂)", 10, 150, 50, 5, key="t4_price",
                      help="Voluntary market ~$10–30. Policy-aligned scenarios: $50–150.")

    snap = df[df["year"] == LAST_YEAR].copy()
    base = df[df["year"] == 2000][["iso3", "forest_km2"]].rename(columns={"forest_km2": "km2_2000"})
    snap = snap.merge(base, on="iso3", how="left")
    snap["ann_loss"] = ((snap["km2_2000"] - snap["forest_km2"]) / (LAST_YEAR - 2000)).clip(lower=0)
    snap = snap[snap["ann_loss"] > 10].copy()
    snap["co2_Mt"]      = snap["ann_loss"] * HA_PER_KM2 * snap["cd"] * TC_TO_TCO2 / 1e6
    snap["revenue_M"]   = snap["co2_Mt"] * price
    snap["cost_M"]      = snap["ann_loss"] * HA_PER_KM2 * PROTECTION_COST_HA / 1e6
    snap["net_M"]       = snap["revenue_M"] - snap["cost_M"]
    snap["break_even"]  = snap["cost_M"] / snap["co2_Mt"].clip(lower=0.001)

    total_rev   = snap["revenue_M"].sum() / 1000
    total_cost  = snap["cost_M"].sum() / 1000
    net         = snap["net_M"].sum() / 1000
    n_profitable = (snap["net_M"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    kvs = [
        (f"${total_rev:.0f}B/yr", "REDD+ revenue at this price", "#4ade80"),
        (f"${total_cost:.0f}B/yr", "Estimated global protection cost", "#fbbf24"),
        (f"${net:+.0f}B/yr", "Net (revenue minus cost)", "#4ade80" if net > 0 else "#f87171"),
        (f"{n_profitable}", "Countries where it's profitable today", "#60a5fa"),
    ]
    for col, (v, l, c) in zip([c1, c2, c3, c4], kvs):
        col.markdown(f'<div class="glass-sm"><div style="font-size:1.4rem;font-weight:800;color:{c}">{v}</div><div style="font-size:.72rem;color:rgba(134,239,172,.55);margin-top:.2rem">{l}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    top20 = snap.nlargest(20, "co2_Mt").copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="REDD+ revenue", x=top20["country"],
                         y=top20["revenue_M"], marker_color="#4ade80"))
    fig.add_trace(go.Bar(name="Protection cost", x=top20["country"],
                         y=top20["cost_M"], marker_color="rgba(134,239,172,0.25)"))
    layout = _plotly_dark_layout()
    layout.update(
        barmode="group", height=380,
        xaxis=dict(**layout.get("xaxis", {}), showgrid=False, tickangle=-35),
        yaxis=dict(**layout.get("yaxis", {}), title="USD million / year"),
        legend=dict(orientation="h", y=1.08, font=dict(color="#d1fae5")),
        margin=dict(l=0, r=0, t=30, b=90),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)

    # Break-even scatter
    befig = px.scatter(
        snap.nlargest(30, "co2_Mt"),
        x="co2_Mt", y="break_even", size="ann_loss", color="region",
        hover_name="country",
        labels={"co2_Mt": "CO₂ saved if halted (MtCO₂/yr)",
                "break_even": "Break-even price ($/tCO₂)"},
        size_max=40,
    )
    befig.add_hline(y=price, line_dash="dash", line_color="#4ade80",
                    annotation_text=f"Your price ${price}/tCO₂",
                    annotation_font_color="#4ade80")
    layout2 = _plotly_dark_layout()
    layout2.update(
        height=360,
        xaxis=dict(**layout2.get("xaxis", {}), type="log",
                   title="CO₂ saved (MtCO₂/yr, log scale)"),
        yaxis=dict(**layout2.get("yaxis", {}), title="Break-even price ($/tCO₂)"),
        legend=dict(font=dict(color="#d1fae5")),
    )
    befig.update_layout(**layout2)
    st.plotly_chart(befig, use_container_width=True)

    st.markdown(f'<div class="method-note">REDD+ revenue = CO₂ saved × carbon price. Protection cost = ${PROTECTION_COST_HA}/ha/yr (Busch et al. 2019). Break-even = price at which REDD+ becomes self-funding. Deforestation rate: World Bank 2000–2021 trend. Country below the dashed line is profitable at your selected price.</div>',
                unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 07 · THE RESILIENCE STACK</div>
      <h1>🌲 Forests &amp; Deforestation</h1>
      <p>What remains · Where it's going · The carbon crisis · What would actually help</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading forest data…"):
        df = load_forest_data()

    if df.empty:
        st.error("Failed to load forest data from World Bank. Please try again.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌿  The Story",
        "🗺️  Forest Map",
        "🔥  Deforestation",
        "💡  Solutions",
    ])

    with tab1:
        tab_story(df)
    with tab2:
        tab_forest_map(df)
    with tab3:
        tab_deforestation(df)
    with tab4:
        tab_solutions(df)

    st.markdown(
        "<div style='text-align:center;color:rgba(134,239,172,.3);font-size:.72rem;margin-top:2rem;padding-bottom:1rem'>"
        "Day 07 · The Resilience Stack · "
        "World Bank AG.LND.FRST.ZS/K2 · Pan et al. 2011 Science · "
        "Gatti et al. 2021 Nature · FAO FRA 2020 · Busch et al. 2019 NCC"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
