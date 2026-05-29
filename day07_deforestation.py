"""
The Resilience Stack — Day 07 (V3 · Light Glassmorphism)
Deforestation & Carbon Sink Tracker

Light matte glassmorphism · Story cards · Forest cartography · Year comparison
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

GLOBAL_FOREST_GHA = {
    1900: 5.9, 1950: 5.5, 1960: 5.4, 1970: 5.2,
    1980: 5.0, 1990: 4.28, 2000: 4.17, 2010: 4.10,
    2015: 4.07, 2020: 4.06,
}

MAP_YEARS = [1990, 1995, 2000, 2005, 2010, 2015, 2020]

# ── Chart constants (light theme) ─────────────────────────────────────────────
_BG  = "rgba(0,0,0,0)"         # transparent paper
_PBG = "rgba(255,255,255,0.55)" # plot area
_GC  = "rgba(0,0,0,0.06)"      # grid lines
_ZC  = "rgba(0,0,0,0.10)"      # zero lines
_TC  = "#374151"                 # text / axis labels
_FONT = dict(family="Inter", color=_TC)


# ── CSS — Light Glassmorphism ─────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Background ── */
.stApp {
    background: linear-gradient(155deg, #f9fefb 0%, #f0fdf4 45%, #ecfdf5 100%);
}
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
section.main,
[data-testid="block-container"] {
    background: transparent !important;
}

/* ── Typography ── */
p, li, div { color: #374151; }
h1, h2, h3, h4 { color: #052e16; }
label, .stRadio label span p, .stSelectbox label,
.stSlider label, [data-testid="stWidgetLabel"] p {
    color: #374151 !important;
}
.stMarkdown p { color: #374151; }
[data-testid="stMetricValue"] { color: #052e16; }
[data-testid="stMetricDelta"] { color: #16a34a; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.92);
    border-radius: 14px;
    padding: 4px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    color: rgba(22,101,52,0.55);
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: .88rem;
}
.stTabs [aria-selected="true"] {
    background: rgba(22,163,74,0.1) !important;
    color: #16a34a !important;
    font-weight: 700;
}

/* ── Glass base ── */
.glass {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.92);
    border-radius: 20px;
    padding: 1.6rem 1.8rem;
    box-shadow: 0 4px 24px rgba(0,80,20,0.07), 0 1px 3px rgba(0,0,0,0.04);
}
.glass-sm {
    background: rgba(255,255,255,0.68);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.9);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 12px rgba(0,80,20,0.05);
}
.glass-warn {
    background: rgba(255,251,235,0.8);
    border: 1px solid rgba(251,191,36,0.3);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 12px rgba(180,83,9,0.06);
}
.glass-crit {
    background: rgba(255,241,242,0.8);
    border: 1px solid rgba(220,38,38,0.2);
    border-radius: 14px;
    padding: 1rem 1.2rem;
}

/* ── Story cards ── */
.story-card {
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.92);
    border-radius: 20px;
    padding: 1.8rem 1.6rem;
    box-shadow: 0 4px 20px rgba(0,80,20,0.07);
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
.story-card.green::before  { background: linear-gradient(90deg,#16a34a,#4ade80); }
.story-card.amber::before  { background: linear-gradient(90deg,#d97706,#fbbf24); }
.story-card.red::before    { background: linear-gradient(90deg,#dc2626,#f87171); }
.story-card.blue::before   { background: linear-gradient(90deg,#1d4ed8,#60a5fa); }
.story-card.purple::before { background: linear-gradient(90deg,#7c3aed,#a78bfa); }
.story-card.teal::before   { background: linear-gradient(90deg,#0f766e,#2dd4bf); }

.story-icon   { font-size: 2rem; margin-bottom: .7rem; display: block; }
.story-number { font-size: 2.4rem; font-weight: 900; line-height: 1; letter-spacing: -1px; margin-bottom: .3rem; }
.story-number.green  { color: #16a34a; }
.story-number.amber  { color: #d97706; }
.story-number.red    { color: #dc2626; }
.story-number.blue   { color: #1d4ed8; }
.story-number.purple { color: #7c3aed; }
.story-number.teal   { color: #0f766e; }
.story-headline { font-size: .97rem; font-weight: 700; color: #111827; margin-bottom: .45rem; line-height: 1.3; }
.story-body     { font-size: .81rem; color: #6b7280; line-height: 1.65; }

/* ── Pills ── */
.stat-pill {
    display: inline-flex; align-items: center; gap: .35rem;
    background: rgba(22,163,74,0.1); border: 1px solid rgba(22,163,74,0.2);
    border-radius: 999px; padding: .28rem .85rem;
    font-size: .76rem; font-weight: 600; color: #15803d; margin: .15rem;
}
.stat-pill.amber { background:rgba(217,119,6,.08); border-color:rgba(217,119,6,.2); color:#b45309; }
.stat-pill.red   { background:rgba(220,38,38,.08); border-color:rgba(220,38,38,.2); color:#b91c1c; }

/* ── Progress ── */
.prog-track {
    background: rgba(0,0,0,0.07); border-radius:999px; height:5px;
    margin: .4rem 0 .2rem; overflow:hidden;
}
.prog-fill { height:100%; border-radius:999px; }

/* ── Header ── */
.rs-header {
    background: linear-gradient(135deg, #052e16 0%, #166534 55%, #15803d 100%);
    border-radius: 20px; padding: 2rem 2.5rem 1.8rem;
    color: #fff; margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(5,46,22,0.18);
    position: relative; overflow: hidden;
}
.rs-header::after {
    content: '🌲';
    position:absolute; right:2rem; top:50%;
    transform:translateY(-50%); font-size:5rem; opacity:.1;
}
.rs-header h1 { font-size:2rem; font-weight:900; margin:0 0 .25rem; letter-spacing:-.5px; color:#fff; }
.rs-header p  { font-size:.95rem; color:#bbf7d0; margin:0; }
.rs-badge {
    display:inline-block; background:rgba(255,255,255,.12);
    border:1px solid rgba(255,255,255,.2); border-radius:999px;
    padding:2px 12px; font-size:.72rem; font-weight:700;
    color:#d1fae5; margin-bottom:.6rem; letter-spacing:.5px;
}

/* ── Method note ── */
.method-note {
    background: rgba(255,255,255,0.6); border-left: 2px solid #86efac;
    padding: .6rem 1rem; border-radius: 0 8px 8px 0;
    font-size: .75rem; color: #6b7280; margin-top: 1.2rem;
}

/* ── Divider ── */
hr { border-color: rgba(0,0,0,.08) !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { display:none; }

/* ── Inputs ── */
[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.8) !important;
    border-color: rgba(0,0,0,0.1) !important;
}
[data-baseweb="select"] span { color: #374151 !important; }
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


def _prog(pct: float, color: str = "#16a34a") -> str:
    return (f'<div class="prog-track">'
            f'<div class="prog-fill" style="width:{min(pct,100):.0f}%;background:{color}"></div>'
            f'</div>')


# Each chart builds its layout directly — no shared base dict to avoid
# duplicate-keyword TypeError when overriding keys like showgrid.
def _lyt(height: int = 360, margin: dict | None = None, **extra) -> dict:
    return dict(
        paper_bgcolor=_BG,
        plot_bgcolor=_PBG,
        font=_FONT,
        height=height,
        margin=margin or dict(l=0, r=0, t=40, b=0),
        **extra,
    )


def _xax(**kw) -> dict:
    return dict(gridcolor=_GC, zerolinecolor=_ZC, color=_TC, **kw)


def _yax(**kw) -> dict:
    return dict(gridcolor=_GC, zerolinecolor=_ZC, color=_TC, **kw)


def _style_geo(fig: go.Figure) -> None:
    fig.update_geos(
        showframe=False,
        showcoastlines=True, coastlinecolor="rgba(0,0,0,0.18)",
        bgcolor="rgba(0,0,0,0)",
        showcountries=True, countrycolor="rgba(0,0,0,0.10)",
        showocean=True, oceancolor="#c8dff0",
        showlakes=True, lakecolor="#d6eaf8",
        showland=True, landcolor="#f0e8d8",
        projection_type="natural earth",
    )


# ── Tab 1 — The Story ─────────────────────────────────────────────────────────

def tab_story(df: pd.DataFrame) -> None:
    snap   = df[df["year"] == LAST_YEAR]
    base   = df[df["year"] == FIRST_YEAR]
    common = set(snap["iso3"]) & set(base["iso3"])

    total_now  = snap[snap["iso3"].isin(common)]["forest_km2"].sum()
    total_1990 = base[base["iso3"].isin(common)]["forest_km2"].sum()
    total_C    = snap["carbon_GtCO2"].sum()
    annual_loss_km2 = (total_1990 - total_now) / (LAST_YEAR - FIRST_YEAR)
    annual_loss_ha  = annual_loss_km2 * HA_PER_KM2
    loss_per_sec    = annual_loss_ha / (365.25 * 86400)
    days_elapsed    = (datetime.date.today() - datetime.date(datetime.date.today().year, 1, 1)).days
    lost_this_year  = int(annual_loss_ha * days_elapsed / 365.25)
    lost_mha        = (total_1990 - total_now) * HA_PER_KM2 / 1e6

    # Hero panel
    st.markdown(f"""
    <div class="glass" style="margin-bottom:1.2rem;
         background:linear-gradient(135deg,rgba(240,253,244,0.9),rgba(236,253,245,0.8))">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
        <div>
          <div style="font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#16a34a;margin-bottom:.4rem">
            EARTH'S FORESTS — {LAST_YEAR} SNAPSHOT
          </div>
          <div style="font-size:3rem;font-weight:900;color:#052e16;line-height:1;letter-spacing:-2px">
            {total_now / 1e6:.2f}B
          </div>
          <div style="font-size:.95rem;color:#166534;margin-top:.2rem;font-weight:500">
            hectares of forest remaining
          </div>
          <div style="margin-top:.8rem">
            <span class="stat-pill">🌍 Down from {total_1990/1e6:.2f}B ha in 1990</span>
            <span class="stat-pill amber">⬇ {lost_mha:.0f}M ha lost since 1990</span>
            <span class="stat-pill red">⏱ {loss_per_sec:.1f} ha/second disappearing</span>
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:.7rem;color:#6b7280;margin-bottom:.3rem;font-weight:600;letter-spacing:.05em">
            LOST SO FAR IN {datetime.date.today().year}
          </div>
          <div style="font-size:2.2rem;font-weight:900;color:#dc2626;letter-spacing:-1px">
            {lost_this_year:,.0f}
          </div>
          <div style="font-size:.75rem;color:#9ca3af">
            hectares · as of {datetime.date.today().strftime('%b %d')}
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Story cards
    cards = [
        ("green",  "🌲", "3 trillion",      "Trees still standing",
         "Before farming and cities, Earth had 5.6 trillion trees. We've felled nearly half — "
         "2.6 trillion gone forever. What remains stores 45% of all land-surface carbon.",
         46),
        ("amber",  "🪓", "15 billion",      "Trees cut every single year",
         "We replant 5 billion. Net loss: 10 billion trees per year — enough to circle the "
         "equator over 100 times, laid end to end. Every. Single. Year.",
         None),
        ("red",    "⏱️", f"{loss_per_sec:.1f} ha/sec", "Forest vanishing right now",
         "An area the size of a football pitch lost every two seconds. By the time you finish "
         "this card, another 30 hectares will be gone — permanently.",
         None),
        ("red",    "🔄", "+0.32 PgC/yr",   "The Amazon has flipped",
         "In 2021, scientists confirmed it: the eastern Amazon now emits more CO₂ than it "
         "absorbs. Earth's greatest forest has crossed its carbon tipping point.",
         None),
        ("blue",   "🦜", "80%",             "Of all land species live in forests",
         "Forests host 80% of all terrestrial biodiversity — jaguars, mountain gorillas, "
         "and thousands of plants with undiscovered medicinal properties. Each loss is permanent.",
         80),
        ("purple", "👨‍👩‍👧", "1.6 billion",    "People whose lives depend on forests",
         "Indigenous communities, smallholder farmers, honey collectors. Forests are not "
         "wilderness to them — they are home, food, income, and identity.",
         None),
        ("teal",   "🛡️", f"{total_C:.0f} GtCO₂", "Locked in standing trees",
         "More carbon than all fossil fuels burned since the Industrial Revolution. "
         "Lose these forests and every climate target — Paris, net zero, 1.5°C — becomes unreachable.",
         None),
        ("green",  "✅", "$12/ha/yr",       "What protection actually costs",
         "REDD+ carbon credits make protecting forests more profitable than clearing them. "
         "At $50/tonne CO₂, the economics of conservation finally work.",
         None),
    ]

    for i in range(0, len(cards), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(cards):
                break
            acc, icon, num, headline, body, pct = cards[i + j]
            prog_html = _prog(pct, "#dc2626") if pct else ""
            pct_note  = (f'<div style="font-size:.68rem;color:#9ca3af;margin-top:.2rem">'
                         f'{pct}% gone since civilisation began</div>') if pct else ""
            col.markdown(f"""
            <div class="story-card {acc}">
              <span class="story-icon">{icon}</span>
              <div class="story-number {acc}">{num}</div>
              <div class="story-headline">{headline}</div>
              <div class="story-body">{body}</div>
              {prog_html}{pct_note}
            </div>
            """, unsafe_allow_html=True)

    # Global timeline
    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#16a34a;margin-bottom:.6rem">THE LONG VIEW — GLOBAL FOREST AREA SINCE 1900</div>',
                unsafe_allow_html=True)

    trend_df = pd.DataFrame(list(GLOBAL_FOREST_GHA.items()), columns=["year", "forest_Gha"])
    tfig = go.Figure()
    tfig.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["forest_Gha"],
        mode="lines+markers",
        line=dict(color="#16a34a", width=3),
        marker=dict(size=8, color="#16a34a"),
        fill="tozeroy",
        fillcolor="rgba(22,163,74,0.08)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f} billion hectares<extra></extra>",
    ))
    tfig.add_annotation(x=2020, y=4.06, text="4.06 Gha today",
                        font=dict(color="#dc2626", size=11, family="Inter"),
                        showarrow=True, arrowcolor="#dc2626", arrowwidth=1.5,
                        arrowhead=2, ax=45, ay=-30)
    tfig.add_annotation(x=1900, y=5.9, text="5.9 Gha in 1900",
                        font=dict(color="#16a34a", size=11, family="Inter"),
                        showarrow=True, arrowcolor="#16a34a", arrowwidth=1.5,
                        arrowhead=2, ax=-10, ay=-30)
    tfig.update_layout(**_lyt(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=_xax(showgrid=False, title=""),
        yaxis=_yax(showgrid=True, title="Global forest (billion ha)", range=[3.5, 6.2]),
    ))
    st.plotly_chart(tfig, use_container_width=True)

    st.markdown('<div class="method-note">Forest area: FAO FRA 2020 + Ramankutty & Foley 1999 (pre-1990 reconstruction). Tree count: Crowther et al. 2015 Nature. Amazon flux: Gatti et al. 2021 Nature. REDD+ cost: Busch et al. 2019 NCC.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Forest Map ────────────────────────────────────────────────────────

def tab_forest_map(df: pd.DataFrame) -> None:
    view = st.radio(
        "View mode",
        ["📅 Year explorer", "⬅️ Before & after", "📊 Net change 1990 → 2020"],
        horizontal=True, key="t2_view",
    )

    if view.startswith("📅"):
        year  = st.select_slider("Slide through time", options=MAP_YEARS, value=2020,
                                 key="t2_year", format_func=lambda y: f"🌍  {y}")
        snap_y = df[df["year"] == year]
        base_y = df[df["year"] == 1990]
        common = set(snap_y["iso3"]) & set(base_y["iso3"])
        g_now  = snap_y[snap_y["iso3"].isin(common)]["forest_km2"].sum() * HA_PER_KM2 / 1e9
        g_90   = base_y[base_y["iso3"].isin(common)]["forest_km2"].sum() * HA_PER_KM2 / 1e9
        lost_p = (g_90 - g_now) / g_90 * 100 if g_90 > 0 else 0

        c1, c2, c3 = st.columns(3)
        for col, val, lbl in [
            (c1, f"{g_now:.2f} Gha", f"Global forest cover {year}"),
            (c2, f"−{(g_90-g_now):.2f} Gha", "Lost vs 1990 baseline"),
            (c3, f"{lost_p:.1f}%", f"Of 1990 forests gone by {year}"),
        ]:
            color = "#dc2626" if "−" in val or "%" in val else "#16a34a"
            col.markdown(f'<div class="glass-sm"><div style="font-size:1.45rem;font-weight:800;color:{color}">{val}</div>'
                         f'<div style="font-size:.72rem;color:#6b7280;margin-top:.2rem">{lbl}</div></div>',
                         unsafe_allow_html=True)

        fig = _make_forest_choropleth(snap_y, year)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#16a34a;margin:.8rem 0 .4rem">COUNTRY TREND</div>',
                    unsafe_allow_html=True)
        countries = sorted(df["country"].dropna().unique())
        sel = st.selectbox("", countries,
                           index=countries.index("Brazil") if "Brazil" in countries else 0,
                           key="t2_country", label_visibility="collapsed")
        _render_country_trend(df, sel)

    elif view.startswith("⬅️"):
        col_l, col_r = st.columns(2)
        with col_l:
            y_a = st.selectbox("Earlier year", MAP_YEARS, index=0, key="ya")
        with col_r:
            y_b = st.selectbox("Later year",   MAP_YEARS, index=len(MAP_YEARS)-1, key="yb")

        snap_a, snap_b = df[df["year"] == y_a], df[df["year"] == y_b]

        fig = make_subplots(rows=1, cols=2,
                            subplot_titles=[f"🌍 {y_a}", f"🌍 {y_b}"],
                            specs=[[{"type":"choropleth"},{"type":"choropleth"}]])
        cscale = [[0.0,"#e8d5b7"],[0.2,"#a8c080"],[0.45,"#4a8a3a"],
                  [0.7,"#1e6e1e"],[1.0,"#0a3d0a"]]
        for ci, (snap, yr) in enumerate([(snap_a, y_a), (snap_b, y_b)], 1):
            fig.add_trace(go.Choropleth(
                locations=snap["iso3"], z=snap["forest_pct"],
                colorscale=cscale, zmin=0, zmax=80,
                showscale=(ci == 2),
                colorbar=dict(title="Forest %", thickness=10, len=0.55,
                              tickfont=dict(color=_TC), title_font=dict(color=_TC))
                if ci == 2 else None,
                marker_line_color="rgba(0,0,0,0.08)", marker_line_width=0.4,
            ), row=1, col=ci)

        fig.update_geos(showframe=False, showcoastlines=True,
                        coastlinecolor="rgba(0,0,0,0.15)", bgcolor="rgba(0,0,0,0)",
                        showcountries=True, countrycolor="rgba(0,0,0,0.08)",
                        showocean=True, oceancolor="#c8dff0",
                        showland=True, landcolor="#f0e8d8",
                        projection_type="natural earth")
        fig.update_layout(height=450, paper_bgcolor=_BG,
                          font=_FONT, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

        common = set(snap_a["iso3"]) & set(snap_b["iso3"])
        a_t = snap_a[snap_a["iso3"].isin(common)]["forest_km2"].sum()
        b_t = snap_b[snap_b["iso3"].isin(common)]["forest_km2"].sum()
        d_m = (b_t - a_t) * HA_PER_KM2 / 1e6
        d_p = (b_t - a_t) / a_t * 100
        col = "#dc2626" if d_m < 0 else "#16a34a"
        st.markdown(f'<div class="glass-sm" style="text-align:center;margin-top:.5rem">'
                    f'<span style="font-size:1.8rem;font-weight:900;color:{col}">{d_m:+.0f} Mha</span>'
                    f'<span style="font-size:.85rem;color:#6b7280;margin-left:.5rem">({d_p:+.1f}%) between {y_a} and {y_b}</span>'
                    f'</div>', unsafe_allow_html=True)

    else:
        chg = _net_change(df, 1990, 2020)
        fig = px.choropleth(
            chg, locations="iso3", color="delta_pct",
            color_continuous_scale=[[0,"#7f1d1d"],[0.3,"#f97316"],
                                     [0.46,"#d1d5db"],[0.6,"#4ade80"],[1,"#052e16"]],
            range_color=[-25, 15],
            hover_name="country",
            hover_data={"iso3": False, "delta_pct": ":.1f", "delta_km2": ":,.0f"},
            labels={"delta_pct": "Change (%)"},
            title="Net forest change 1990 → 2020",
        )
        _style_geo(fig)
        fig.update_layout(
            height=500, paper_bgcolor=_BG, font=_FONT,
            coloraxis_colorbar=dict(
                title="Change %", thickness=12, len=0.6, tickfont=dict(color=_TC),
                title_font=dict(color=_TC),
                tickvals=[-25,-10,-2,0,10,15],
                ticktext=["−25 Loss","−10","−2","0","+10","+15 Gain"],
            ),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        losers  = chg.nsmallest(5, "delta_pct")
        gainers = chg.nlargest(5, "delta_pct")
        cl, cr  = st.columns(2)
        with cl:
            st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#dc2626;margin-bottom:.5rem">BIGGEST LOSSES 1990→2020</div>',
                        unsafe_allow_html=True)
            for _, row in losers.iterrows():
                st.markdown(f'<div class="glass-crit" style="margin-bottom:.3rem"><b style="color:#dc2626">{row.country}</b> <span style="color:#6b7280;font-size:.8rem">{row.delta_pct:.1f}% · {row.delta_km2/1000:,.0f}k km²</span></div>',
                            unsafe_allow_html=True)
        with cr:
            st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#16a34a;margin-bottom:.5rem">BIGGEST GAINS 1990→2020</div>',
                        unsafe_allow_html=True)
            for _, row in gainers.iterrows():
                st.markdown(f'<div class="glass-sm" style="margin-bottom:.3rem"><b style="color:#16a34a">{row.country}</b> <span style="color:#6b7280;font-size:.8rem">+{row.delta_pct:.1f}% · +{row.delta_km2/1000:,.0f}k km²</span></div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest cover: World Bank AG.LND.FRST.ZS / AG.LND.FRST.K2 · FAO FRA · 1990–2020. Map shows % of land area classified as forest. Colour scale: beige = sparse, deep green = dense forest.</div>',
                unsafe_allow_html=True)


def _make_forest_choropleth(snap: pd.DataFrame, year: int) -> go.Figure:
    fig = px.choropleth(
        snap, locations="iso3", color="forest_pct",
        color_continuous_scale=[
            [0.00, "#e8d5b7"],
            [0.12, "#c4a97a"],
            [0.28, "#a8c080"],
            [0.48, "#4a8a3a"],
            [0.70, "#1e6e1e"],
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
        height=500, paper_bgcolor=_BG, font=_FONT,
        coloraxis_colorbar=dict(
            title="Forest %", thickness=12, len=0.58,
            tickvals=[0, 10, 20, 40, 60, 80],
            ticktext=["0", "10%", "20%", "40%", "60%", "80%"],
            tickfont=dict(color=_TC), title_font=dict(color=_TC),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def _render_country_trend(df: pd.DataFrame, country: str) -> None:
    cdf = df[df["country"] == country].sort_values("year")
    if cdf.empty:
        return
    cfig = go.Figure()
    cfig.add_trace(go.Scatter(
        x=cdf["year"], y=cdf["forest_km2"] / 1e3,
        mode="lines+markers",
        line=dict(color="#16a34a", width=2.5),
        marker=dict(size=6, color="#16a34a"),
        fill="tozeroy", fillcolor="rgba(22,163,74,0.07)",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}k km²<extra></extra>",
    ))
    cfig.update_layout(**_lyt(
        height=240, margin=dict(l=0, r=0, t=30, b=0),
        title=dict(text=f"{country} — forest area", font=dict(size=13, color="#166534")),
        xaxis=_xax(showgrid=False),
        yaxis=_yax(showgrid=True, title="Forest (thousand km²)"),
        showlegend=False,
    ))
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
    ha_day     = total_km2 * HA_PER_KM2 / n_years / 365.25
    fields_day = ha_day / 0.714

    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in [
        (c1, f"{total_km2/1e6:.2f}M km²",    f"Forest lost {period}"),
        (c2, f"{carbon_Gt:.1f} GtCO₂",       "Carbon released equivalent"),
        (c3, f"{total_km2/242495:.1f}× UK",  "Area equivalent"),
        (c4, f"{fields_day:,.0f}/day",        "Football pitches lost daily"),
    ]:
        col.markdown(f'<div class="glass-sm">'
                     f'<div style="font-size:1.4rem;font-weight:800;color:#dc2626">{val}</div>'
                     f'<div style="font-size:.72rem;color:#6b7280;margin-top:.2rem">{lbl}</div>'
                     f'</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    x_col = "abs_loss" if view.startswith("Absolute") else "rate"
    x_lbl = "Forest lost (km²)" if view.startswith("Absolute") else "Loss (% of forest)"
    top   = losers.nlargest(20, x_col).sort_values(x_col)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top[x_col], y=top["country"], orientation="h",
        marker=dict(color=top[x_col],
                    colorscale=[[0,"#fca5a5"],[0.5,"#ef4444"],[1,"#7f1d1d"]],
                    showscale=False),
        text=top[x_col].apply(lambda v: f"{v:,.0f}" if view.startswith("Absolute") else f"{v:.1f}%"),
        textposition="outside", textfont=dict(color=_TC, size=10),
        hovertemplate="<b>%{y}</b><br>" + x_lbl + ": %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_lyt(
        height=560, margin=dict(l=0, r=80, t=10, b=0),
        xaxis=_xax(showgrid=True, title=x_lbl),
        yaxis=_yax(showgrid=False),
    ))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(127,29,29,0.06),rgba(153,27,27,0.04));
                border:1px solid rgba(220,38,38,0.18);border-radius:16px;padding:1.4rem 1.6rem;margin:1rem 0">
      <div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;color:#dc2626;margin-bottom:.5rem">
        THE AMAZON TIPPING POINT
      </div>
      <div style="font-size:.88rem;color:#374151;line-height:1.7">
        In 2021, measurements confirmed what scientists feared: the <b>eastern Amazon</b> now emits
        <b style="color:#dc2626">+0.86 PgC/yr</b> — more CO₂ than it absorbs.
        The western Amazon remains a sink (−0.54 PgC/yr), but the net result is that
        Earth's greatest forest has <b>crossed its carbon tipping point</b>.
        59% of the flux comes from fires; 41% from deforestation-driven degradation.<br>
        <span style="font-size:.76rem;color:#9ca3af">Gatti et al. 2021, Nature · doi:10.1038/s41586-021-03629-6</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Forest area: World Bank AG.LND.FRST.ZS/K2. Carbon released = area lost × carbon density (Pan et al. 2011 Science). UK area 242,495 km². FIFA pitch 0.714 ha.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — Solutions ─────────────────────────────────────────────────────────

def tab_solutions(df: pd.DataFrame) -> None:
    st.markdown('<div style="font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#16a34a;margin-bottom:.8rem">WHAT WOULD IT ACTUALLY TAKE TO STOP DEFORESTATION?</div>',
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
        (c1, f"${total_rev:.0f}B/yr",    "REDD+ revenue at this price",  "#16a34a"),
        (c2, f"${total_cost:.0f}B/yr",   "Estimated protection cost",    "#d97706"),
        (c3, f"${net:+.0f}B/yr",         "Net (revenue − cost)",         "#16a34a" if net>0 else "#dc2626"),
        (c4, f"{n_profitable}",           "Countries where it's profitable", "#1d4ed8"),
    ]:
        col.markdown(f'<div class="glass-sm"><div style="font-size:1.4rem;font-weight:800;color:{color}">{val}</div>'
                     f'<div style="font-size:.72rem;color:#6b7280;margin-top:.2rem">{lbl}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    top20 = snap.nlargest(20, "co2_Mt").copy()
    bfig  = go.Figure()
    bfig.add_trace(go.Bar(name="REDD+ revenue",  x=top20["country"], y=top20["revenue_M"],
                          marker_color="#4ade80"))
    bfig.add_trace(go.Bar(name="Protection cost", x=top20["country"], y=top20["cost_M"],
                          marker_color="rgba(22,163,74,0.2)"))
    bfig.update_layout(**_lyt(
        height=380, margin=dict(l=0, r=0, t=30, b=90),
        barmode="group",
        xaxis=_xax(showgrid=False, tickangle=-35),
        yaxis=_yax(showgrid=True, title="USD million / year"),
        legend=dict(orientation="h", y=1.08, font=dict(color=_TC)),
    ))
    st.plotly_chart(bfig, use_container_width=True)

    befig = px.scatter(
        snap.nlargest(30, "co2_Mt"),
        x="co2_Mt", y="break_even", size="ann_loss", color="region",
        hover_name="country",
        labels={"co2_Mt": "CO₂ saved if halted (MtCO₂/yr)",
                "break_even": "Break-even price ($/tCO₂)"},
        size_max=40,
    )
    befig.add_hline(y=price, line_dash="dash", line_color="#16a34a",
                    annotation_text=f"Your price ${price}/tCO₂",
                    annotation_font_color="#16a34a")
    befig.update_layout(**_lyt(
        height=360,
        xaxis=_xax(showgrid=True, type="log", title="CO₂ saved (MtCO₂/yr, log scale)"),
        yaxis=_yax(showgrid=True, title="Break-even price ($/tCO₂)"),
        legend=dict(font=dict(color=_TC)),
    ))
    st.plotly_chart(befig, use_container_width=True)

    st.markdown(f'<div class="method-note">REDD+ revenue = CO₂ saved × carbon price. Protection cost = ${PROTECTION_COST_HA}/ha/yr (Busch et al. 2019 NCC). Break-even = price at which REDD+ becomes self-funding. Points below the green dashed line are profitable at your price.</div>',
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
        "<div style='text-align:center;color:#9ca3af;font-size:.72rem;margin-top:2rem;padding-bottom:1rem'>"
        "Day 07 · The Resilience Stack · "
        "World Bank AG.LND.FRST.ZS/K2 · Pan et al. 2011 Science · "
        "Gatti et al. 2021 Nature · FAO FRA 2020 · Busch et al. 2019 NCC"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
