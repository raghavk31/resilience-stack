"""
The Resilience Stack — Day 10
The Polycrisis Dashboard

Composite Country Resilience Score across 7 climate-risk dimensions.
"Polycrisis" — Adam Tooze 2022: multiple crises compound and reinforce each other.

Dimensions (each 0-100, higher = more vulnerable):
  Energy     — fossil dependency + electricity access gap
  Water      — freshwater withdrawal stress
  Food       — undernourishment prevalence
  Air        — mean annual PM2.5 exposure
  Heat       — climate-zone heat stress index (IPCC AR6 WG2)
  Economy    — inverse log GDP/capita (adaptive capacity)
  Carbon     — CO₂ emissions per capita

Sources:
  World Bank EG.USE.COMM.FO.ZS — fossil fuel % of total energy
  World Bank EG.ELC.ACCS.ZS    — electricity access %
  World Bank ER.H2O.FWTL.ZS   — freshwater withdrawal %
  World Bank SN.ITK.DEFC.ZS   — undernourishment %
  World Bank EN.ATM.PM25.MC.M3 — mean PM2.5 µg/m³
  World Bank NY.GDP.PCAP.CD   — GDP per capita USD
  World Bank SP.POP.TOTL       — population
  World Bank EN.ATM.CO2E.PC   — CO₂ per capita tonnes
  IPCC AR6 WG2 heat hazard maps — heat stress score by country
"""

import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests

st.set_page_config(
    page_title="Polycrisis Dashboard · Day 10",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META    = "https://api.worldbank.org/v2/country"
HEADERS    = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_FOSSIL = "EG.USE.COMM.FO.ZS"
IND_ELEC   = "EG.ELC.ACCS.ZS"
IND_WATER  = "ER.H2O.FWTL.ZS"
IND_FOOD   = "SN.ITK.DEFC.ZS"
IND_PM25   = "EN.ATM.PM25.MC.M3"
IND_GDP    = "NY.GDP.PCAP.CD"
IND_POP    = "SP.POP.TOTL"
IND_CO2    = "EN.ATM.CO2E.PC"

# Dimension display config: label → (column, colour, weight)
DIMS = {
    "Energy":  ("d_energy", "#f97316", 0.15),
    "Water":   ("d_water",  "#3b82f6", 0.18),
    "Food":    ("d_food",   "#ca8a04", 0.15),
    "Air":     ("d_air",    "#8b5cf6", 0.15),
    "Heat":    ("d_heat",   "#ef4444", 0.15),
    "Economy": ("d_eco",    "#64748b", 0.12),
    "Carbon":  ("d_co2",    "#16a34a", 0.10),
}

# IPCC AR6 WG2 — heat stress score by ISO3 (0-100, higher = worse)
HEAT_SCORE: dict[str, float] = {
    "SAU":95,"ARE":95,"QAT":95,"KWT":95,"BHR":90,"OMN":90,"YEM":88,"IRQ":88,
    "DJI":92,"ERI":80,"SDN":92,"SSD":88,"NER":92,"MLI":90,"BFA":88,"TCD":90,
    "SEN":80,"MRT":88,"SOM":85,"PAK":88,"IND":78,"BGD":75,"LKA":65,
    "NGA":72,"GHA":70,"CIV":68,"TGO":70,"BEN":70,"CMR":68,"ETH":72,
    "KEN":65,"UGA":62,"TZA":62,"MOZ":60,"ZMB":58,"ZWE":60,"BWA":68,
    "NAM":65,"AGO":62,"MDG":58,"EGY":82,"LBY":78,"TUN":70,"DZA":72,
    "MAR":62,"SYR":78,"JOR":78,"PSE":75,"AFG":70,"UZB":68,"TJK":55,
    "THA":78,"VNM":75,"KHM":77,"LAO":72,"MMR":74,"IDN":70,"PHL":72,
    "MYS":68,"MEX":62,"GTM":60,"SLV":62,"HND":62,"NIC":60,"HTI":65,
    "COL":58,"VEN":60,"BRA":58,"BOL":52,"PRY":55,"ZAF":48,"COD":65,
    "GAB":62,"CHN":52,"KOR":48,"JPN":50,"TUR":58,"GRC":62,"ESP":55,
    "ITA":52,"PRT":52,"AUS":55,"ARG":42,"CHL":30,"PER":48,"ECU":50,
    "USA":40,"UKR":32,"RUS":25,"KAZ":42,"GBR":28,"DEU":30,"FRA":38,
    "POL":32,"SWE":20,"NOR":18,"FIN":18,"DNK":22,"NLD":28,"CAN":28,"NZL":32,
    "IRN":78,"MMR":74,"TWN":62,"SGP":65,"VNM":75,
}
DEFAULT_HEAT = 52.0

RESILIENCE_BANDS = [
    (80, 100, "Resilient",   "#16a34a"),
    (60,  80, "Stable",      "#4ade80"),
    (40,  60, "Vulnerable",  "#f59e0b"),
    (20,  40, "At Risk",     "#ef4444"),
    ( 0,  20, "Critical",    "#7f1d1d"),
]


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }
.stApp { background: #f2f2f2 !important; }
[data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; background: transparent !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"], section.main { background: #f2f2f2 !important; }

.mc-header {
  background: #ffffff;
  border-bottom: 1px solid rgba(0,0,0,0.08);
  padding: 18px 32px 0;
}
.mc-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #bbb;
  display: flex; align-items: center; gap: 8px; margin-bottom: 16px;
}
.mc-dot { width: 9px; height: 9px; border-radius: 50%; border: 2px solid #bbb; display: inline-block; }

.stTabs [data-baseweb="tab-list"] {
  background: transparent !important; border: none !important;
  border-radius: 0 !important; padding: 0 !important; gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: #bbb !important;
  font-size: 11px !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: .1em !important;
  padding: 12px 24px !important; border-radius: 0 !important;
  border-right: 1px solid rgba(0,0,0,0.06) !important;
}
.stTabs [data-baseweb="tab"]:last-child { border-right: none !important; }
.stTabs [aria-selected="true"] { color: #111 !important; border-bottom: 2px solid #111 !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none !important; }
[data-testid="stTabsContent"] { padding: 0 !important; }

[data-testid="stHorizontalBlock"]:has(.mc-left) { gap: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:first-child {
  background: #ffffff !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 120px);
}
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:last-child {
  background: #f2f2f2 !important;
  padding: 24px 28px !important;
}

.mc-left  { height: 0; margin: 0; padding: 0; display: block; }
.mc-pad   { padding: 24px 22px 0; }
.mc-title {
  font-size: 1.35rem; font-weight: 800; color: #111; line-height: 1.2;
  margin: 0 0 .4rem; letter-spacing: -.25px;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-desc  { font-size: .78rem; color: #888; line-height: 1.65; margin: 0; }
.mc-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 14px 0; }
.mc-ctrl-lbl { font-size: .78rem; font-weight: 600; color: #333; margin-bottom: 1px; }
.mc-ctrl-sub { font-size: .7rem; color: #bbb; margin-bottom: 6px; }
.mc-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 4px 0; }
.mc-val   {
  font-size: 1.4rem; font-weight: 700; color: #111; line-height: 1;
  letter-spacing: -.3px; font-variant-numeric: tabular-nums;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-lbl   { font-size: .64rem; color: #aaa; margin-top: 4px; line-height: 1.4; }
.mc-sec   { font-size: .67rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.mc-note  { font-size: .64rem; color: #ccc; line-height: 1.6; }

.r-lbl    { font-size: .67rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #bbb; margin-bottom: 6px; }

.score-badge {
  border-radius: 8px; padding: 14px 16px; margin: 4px 0 12px;
}
.score-badge-lbl  { font-size: .67rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px; }
.score-badge-val  { font-size: 2.8rem; font-weight: 900; line-height: 1; letter-spacing: -2px; font-family: 'Space Grotesk', sans-serif; }
.score-badge-band { font-size: .8rem; font-weight: 600; margin-top: 4px; }

.dim-row  { margin-bottom: 11px; }
.dim-lbl  { display: flex; justify-content: space-between; font-size: .72rem; font-weight: 600; color: #555; margin-bottom: 4px; }
.dim-track { background: rgba(0,0,0,0.07); border-radius: 3px; height: 6px; overflow: hidden; }
.dim-fill  { height: 100%; border-radius: 3px; }

.poly-callout {
  background: #fff7f0; border: 1px solid rgba(249,115,22,0.15);
  border-left: 3px solid #f97316; border-radius: 0 6px 6px 0;
  padding: .8rem 1rem; margin-bottom: 4px;
}

section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .78rem !important; font-weight: 600 !important; color: #333 !important;
}
[data-baseweb="select"] > div {
  background: white !important; border: 1px solid rgba(0,0,0,0.12) !important;
  border-radius: 4px !important; font-size: .78rem !important;
}
[data-baseweb="select"] span { color: #333 !important; }
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
                inc = c.get("incomeLevel", {})
                if isinstance(reg, dict) and reg.get("id") not in ("", "NA", None):
                    rows.append({
                        "iso3":      c["id"], "name": c["name"],
                        "region":    reg.get("value", ""),
                        "income_id": inc.get("id", "INX") if isinstance(inc, dict) else "INX",
                    })
            if page * meta.get("per_page", 500) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def _load_wb_latest(indicator: str) -> pd.DataFrame:
    rows, page = [], 1
    while True:
        url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
               f"?format=json&mrv=5&per_page=1000&page={page}")
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
    df["iso3"]    = df["countryiso3code"]
    df["country"] = df["country"].apply(lambda x: x["value"] if isinstance(x, dict) else x)
    df["year"]    = df["date"].astype(int)
    df["value"]   = df["value"].astype(float)
    return (df.sort_values("year", ascending=False)
              .groupby("iso3").first().reset_index()[["iso3", "country", "value"]])


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def load_polycrisis_data() -> pd.DataFrame:
    meta   = _load_country_meta()
    fossil = _load_wb_latest(IND_FOSSIL).rename(columns={"value": "fossil_pct"})
    elec   = _load_wb_latest(IND_ELEC).rename(columns={"value": "elec_access"})
    water  = _load_wb_latest(IND_WATER).rename(columns={"value": "water_withdrawal"})
    food   = _load_wb_latest(IND_FOOD).rename(columns={"value": "undernourishment"})
    pm25   = _load_wb_latest(IND_PM25).rename(columns={"value": "pm25"})
    gdp    = _load_wb_latest(IND_GDP).rename(columns={"value": "gdp_pc"})
    pop    = _load_wb_latest(IND_POP).rename(columns={"value": "population"})
    co2    = _load_wb_latest(IND_CO2).rename(columns={"value": "co2_pc"})

    valid  = set(meta["iso3"])
    df     = meta[["iso3", "name", "region", "income_id"]].copy()
    for d in [fossil, elec, water, food, pm25, gdp, pop, co2]:
        if d.empty or "iso3" not in d.columns:
            continue
        d2 = d[d["iso3"].isin(valid)][["iso3"] + [c for c in d.columns if c not in ("iso3","country")]]
        df = df.merge(d2, on="iso3", how="left")

    # Ensure all indicator columns exist (fallback to world-typical values if API failed)
    _col_defaults = {
        "fossil_pct": 70.0, "elec_access": 85.0, "water_withdrawal": 15.0,
        "undernourishment": 8.0, "pm25": 22.0, "gdp_pc": 5000.0,
        "population": 10_000_000.0, "co2_pc": 4.0,
    }
    for _col, _val in _col_defaults.items():
        if _col not in df.columns:
            df[_col] = _val

    # Heat score
    df["heat_score"] = df["iso3"].map(HEAT_SCORE).fillna(DEFAULT_HEAT)

    # ── Vulnerability dimensions 0-100 (100 = most vulnerable) ──────────────
    # Energy: fossil dependency + access gap
    fp  = df["fossil_pct"].fillna(df["fossil_pct"].median())
    ea  = df["elec_access"].fillna(df["elec_access"].median())
    df["d_energy"] = (fp * 0.55 + (100 - ea) * 0.45).clip(0, 100)

    # Water: withdrawal stress (>100% = fully stressed, cap 150)
    ww  = df["water_withdrawal"].fillna(df["water_withdrawal"].median())
    df["d_water"] = (ww.clip(0, 150) / 150 * 100).clip(0, 100)

    # Food: undernourishment %
    fn  = df["undernourishment"].fillna(df["undernourishment"].median())
    df["d_food"] = fn.clip(0, 100)

    # Air: PM2.5 normalised (80 µg/m³ → score 100)
    p25 = df["pm25"].fillna(df["pm25"].median())
    df["d_air"] = (p25 / 80 * 100).clip(0, 100)

    # Heat: IPCC lookup
    df["d_heat"] = df["heat_score"]

    # Economy: inverse log GDP/cap (low GDP = high vulnerability)
    def _eco(g):
        if pd.isna(g) or g <= 0:
            return 80.0
        return max(0.0, 100.0 - math.log10(g) / math.log10(80_000) * 100)
    df["d_eco"] = df["gdp_pc"].apply(_eco)

    # Carbon: CO₂ per capita (higher = more responsible for problem)
    co2v = df["co2_pc"].fillna(df["co2_pc"].median())
    df["d_co2"] = (co2v / 20 * 100).clip(0, 100)

    # ── Composite vulnerability + resilience ─────────────────────────────────
    dim_cols = [v[0] for v in DIMS.values()]
    weights  = [v[2] for v in DIMS.values()]
    df["vulnerability"] = sum(df[col] * w for col, w in zip(dim_cols, weights))
    df["resilience"]    = (100 - df["vulnerability"]).round(1).clip(0, 100)

    return df.dropna(subset=["resilience"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resilience_band(score: float) -> tuple[str, str]:
    for lo, hi, label, color in RESILIENCE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#888"

def _mg(pairs: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div><div class="mc-val">{v}</div><div class="mc-lbl">{l}</div></div>'
                    for v, l in pairs)
    return f'<div class="mc-grid">{cells}</div>'

def _sep() -> str:
    return '<hr class="mc-sep">'

def _chart(h: int = 520, **kw) -> dict:
    base = dict(height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#888", size=11),
                margin=dict(l=0, r=0, t=8, b=0))
    base.update(kw)
    return base


# ── Tab 1 — Resilience Map ────────────────────────────────────────────────────

def tab_map(df: pd.DataFrame) -> None:
    n_critical  = int((df["resilience"] < 20).sum())
    n_at_risk   = int((df["resilience"] < 40).sum())
    n_resilient = int((df["resilience"] >= 80).sum())
    most_r  = df.loc[df["resilience"].idxmax(), "name"]
    least_r = df.loc[df["resilience"].idxmin(), "name"]

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Resilience Map</h2>'
            '<p class="mc-desc">Composite Country Resilience Score — 7 dimensions of '
            'climate vulnerability, weighted and combined. 100 = fully resilient, 0 = critical.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            (f"{n_critical}",  "Countries in Critical zone (score < 20)"),
            (f"{n_at_risk}",   "Countries At Risk or worse (< 40)"),
            (f"{n_resilient}", "Countries Resilient (score ≥ 80)"),
            (f"{df['resilience'].mean():.0f}", "Global mean resilience score"),
        ]), unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div class="mc-sec">Score bands</div>'
            '<div style="display:flex;flex-direction:column;gap:5px;margin-bottom:4px">',
            unsafe_allow_html=True,
        )
        bands_html = ""
        for lo, hi, label, color in RESILIENCE_BANDS:
            n = int(((df["resilience"] >= lo) & (df["resilience"] < hi)).sum())
            bands_html += (
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<div style="width:10px;height:10px;border-radius:2px;'
                f'background:{color};flex-shrink:0"></div>'
                f'<span style="font-size:.72rem;color:#555;flex:1">{label} ({lo}–{hi})</span>'
                f'<span style="font-size:.72rem;font-weight:600;color:#333">{n}</span>'
                f'</div>'
            )
        st.markdown(bands_html + '</div>', unsafe_allow_html=True)

        st.markdown(
            _sep() +
            f'<div class="mc-sec">Extremes</div>'
            f'<div class="mc-val">{most_r}</div>'
            f'<div class="mc-lbl">Most resilient country</div>'
            f'<div class="mc-val" style="margin-top:8px">{least_r}</div>'
            f'<div class="mc-lbl">Least resilient country</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            _sep() +
            '<div class="mc-note">Energy 15% · Water 18% · Food 15% · Air 15% · '
            'Heat 15% · Economy 12% · Carbon 10%. '
            'World Bank data (latest available per country). '
            'Heat: IPCC AR6 WG2 climate hazard maps.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="r-lbl">COUNTRY RESILIENCE SCORE — COMPOSITE 7-DIMENSION INDEX</div>',
                    unsafe_allow_html=True)
        df["band"] = df["resilience"].apply(lambda s: _resilience_band(s)[0])
        fig = px.choropleth(
            df, locations="iso3", color="resilience",
            color_continuous_scale=["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"],
            range_color=[0, 100],
            hover_name="name",
            hover_data={"iso3": False, "resilience": ":.0f", "band": True,
                        "d_energy": ":.0f", "d_water": ":.0f", "d_food": ":.0f",
                        "d_air": ":.0f", "d_heat": ":.0f"},
            labels={"resilience": "Resilience", "band": "Status"},
        )
        fig.update_layout(
            **_chart(h=500),
            geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#d4d4d4",
                     bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e5e5e5",
                     showocean=True, oceancolor="#ddeeff"),
            coloraxis_colorbar=dict(
                title=dict(text="Score", font=dict(size=10, color="#aaa")),
                thickness=9, len=0.5,
                tickvals=[0, 20, 40, 60, 80, 100],
                ticktext=["0 Critical","20","40","60","80","100 Resilient"],
                tickfont=dict(size=9, color="#aaa"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Polycrisis callout
        st.markdown("""
        <div class="poly-callout">
          <div style="font-size:.67rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
                      color:#f97316;margin-bottom:.35rem">THE POLYCRISIS</div>
          <div style="font-size:.78rem;color:#555;line-height:1.7">
            Adam Tooze's concept: we no longer face <em>one</em> crisis at a time.
            Water stress amplifies food insecurity. Heat stress erodes economic productivity.
            Air pollution degrades health systems exactly when they're needed most.
            The countries scoring lowest on this map face <b style="color:#333">all seven pressures simultaneously</b>.
          </div>
        </div>
        """, unsafe_allow_html=True)


# ── Tab 2 — Country Profile ───────────────────────────────────────────────────

def tab_country(df: pd.DataFrame) -> None:
    left, right = st.columns([1.1, 2.9], gap="large")
    countries = sorted(df["name"].dropna().unique())
    default   = countries.index("Pakistan") if "Pakistan" in countries else 0

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Country Profile</h2>'
            '<p class="mc-desc">Per-country breakdown across all 7 resilience dimensions.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep(), unsafe_allow_html=True)

        sel  = st.selectbox("Country", countries, index=default, key="cp_country",
                            label_visibility="collapsed")
        row  = df[df["name"] == sel].iloc[0]
        score = row["resilience"]
        band, bcolor = _resilience_band(score)

        st.markdown(
            f'<div class="score-badge" style="background:{bcolor}14;border:1px solid {bcolor}30">'
            f'<div class="score-badge-lbl" style="color:{bcolor}">Resilience Score</div>'
            f'<div class="score-badge-val" style="color:{bcolor}">{score:.0f}</div>'
            f'<div class="score-badge-band" style="color:#555">{band} · {sel}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        dim_html = ""
        for name, (col, color, _) in DIMS.items():
            vuln = row[col]
            res  = 100 - vuln
            dim_html += (
                f'<div class="dim-row">'
                f'<div class="dim-lbl">'
                f'<span>{name}</span>'
                f'<span style="color:{color}">{vuln:.0f} vuln</span>'
                f'</div>'
                f'<div class="dim-track">'
                f'<div class="dim-fill" style="width:{vuln:.0f}%;background:{color}"></div>'
                f'</div>'
                f'</div>'
            )
        st.markdown(dim_html, unsafe_allow_html=True)

        # Region comparison summary
        region_df = df[df["region"] == row["region"]]
        reg_avg   = region_df["resilience"].mean()
        global_avg = df["resilience"].mean()
        st.markdown(
            _sep() +
            _mg([
                (f"{reg_avg:.0f}",    f"Region average ({row['region'].split('&')[0].strip()[:12]})"),
                (f"{global_avg:.0f}", "Global average"),
            ]),
            unsafe_allow_html=True,
        )

        st.markdown(
            _sep() +
            '<div class="mc-note">Radar axes = vulnerability (0=safe, 100=critical). '
            'Bar fill = vulnerability score for each dimension.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        dim_names  = list(DIMS.keys())
        dim_cols   = [v[0] for v in DIMS.values()]
        dim_colors = [v[1] for v in DIMS.values()]
        vuln_vals  = [float(row[c]) for c in dim_cols]
        radar_cats = dim_names + [dim_names[0]]
        radar_vals = vuln_vals + [vuln_vals[0]]

        st.markdown(f'<div class="r-lbl">VULNERABILITY RADAR — {sel.upper()}</div>',
                    unsafe_allow_html=True)

        rfig = go.Figure()
        rfig.add_trace(go.Scatterpolar(
            r=radar_vals, theta=radar_cats, fill="toself",
            fillcolor="rgba(239,68,68,0.12)", line=dict(color="#ef4444", width=2),
            name=sel,
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[50]*len(radar_cats), theta=radar_cats,
            line=dict(color="#94a3b8", width=1, dash="dot"),
            mode="lines", name="World average (~50)",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[75]*len(radar_cats), theta=radar_cats,
            line=dict(color="#dc2626", width=1, dash="dot"),
            mode="lines", name="High-risk threshold (75)",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(range=[0, 100], tickfont=dict(size=9, color="#aaa"),
                                gridcolor="rgba(0,0,0,0.08)"),
                angularaxis=dict(tickfont=dict(size=11, color="#555")),
                bgcolor="rgba(0,0,0,0)",
            ),
            **_chart(h=380, margin=dict(l=30, r=30, t=20, b=40)),
            legend=dict(orientation="h", y=-0.1, font=dict(size=9, color="#888"),
                        bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(rfig, use_container_width=True)

        # Regional comparison bar
        st.markdown(f'<div class="r-lbl" style="margin-top:1rem">REGIONAL COMPARISON — {row["region"].upper()}</div>',
                    unsafe_allow_html=True)
        reg_df = (df[df["region"] == row["region"]]
                  .sort_values("resilience").head(20).copy())
        reg_df["highlight"] = reg_df["name"] == sel
        cfig = px.bar(reg_df, x="resilience", y="name", orientation="h",
                      color="highlight",
                      color_discrete_map={True: "#ef4444", False: "#d1d5db"},
                      labels={"resilience": "Resilience Score", "name": ""},
                      text="resilience")
        cfig.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        cfig.update_layout(
            **_chart(h=max(260, len(reg_df)*26), margin=dict(l=0, r=60, t=8, b=0)),
            xaxis=dict(range=[0, 105], gridcolor="rgba(0,0,0,0.06)",
                       color="#bbb", tickfont=dict(size=10)),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(cfig, use_container_width=True)


# ── Tab 3 — Crisis Correlations ───────────────────────────────────────────────

def tab_correlations(df: pd.DataFrame) -> None:
    dim_cols  = [v[0] for v in DIMS.values()]
    dim_names = list(DIMS.keys())
    corr      = df[dim_cols].rename(columns={v[0]: k for k, v in DIMS.items()}).corr()

    # Top positive correlations (excluding self and NaN pairs)
    pairs = []
    for i, a in enumerate(dim_names):
        for j, b in enumerate(dim_names):
            if i < j:
                r_val = corr.loc[a, b]
                if not math.isnan(r_val):
                    pairs.append((abs(r_val), r_val, a, b))
    pairs.sort(reverse=True)

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Crisis Correlations</h2>'
            '<p class="mc-desc">How the seven dimensions of vulnerability cluster and reinforce each other. '
            'Positive correlation = crises that strike the same countries simultaneously.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div class="poly-callout">'
            '<div style="font-size:.67rem;font-weight:700;letter-spacing:.1em;'
            'text-transform:uppercase;color:#f97316;margin-bottom:.3rem">COMPOUNDING</div>'
            '<div style="font-size:.75rem;color:#555;line-height:1.65">'
            'Countries at the intersection of multiple high-correlation clusters '
            'face cascading failures — one system&#39;s collapse accelerates the others. '
            'This is the polycrisis: not A + B + C, but A × B × C.'
            '</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(_sep() + '<div class="mc-sec">Strongest co-occurrence pairs</div>',
                    unsafe_allow_html=True)
        top5_html = ""
        for abs_r, r, a, b in pairs[:5]:
            arrow = "↑↑" if r > 0 else "↑↓"
            bar_w = int(abs_r * 100)
            top5_html += (
                f'<div style="margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:.72rem;color:#555;margin-bottom:3px">'
                f'<span><b>{a}</b> + <b>{b}</b></span>'
                f'<span style="color:#f97316;font-weight:700">{r:.2f} {arrow}</span>'
                f'</div>'
                f'<div style="background:rgba(0,0,0,0.07);border-radius:2px;height:4px">'
                f'<div style="width:{bar_w}%;background:#f97316;height:4px;border-radius:2px"></div>'
                f'</div></div>'
            )
        st.markdown(top5_html, unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div class="mc-note">Pearson correlation across all countries with complete data. '
            'Values near +1 = crises co-occur. Near 0 = independent. Near -1 = trade-off.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="r-lbl">CRISIS CORRELATION MATRIX — PEARSON r BETWEEN DIMENSIONS</div>',
                    unsafe_allow_html=True)
        hfig = px.imshow(
            corr,
            color_continuous_scale=["#dbeafe","#f8fafc","#fef2f2"],
            zmin=-1, zmax=1,
            text_auto=".2f",
            labels=dict(color="Pearson r"),
        )
        hfig.update_traces(textfont=dict(size=11, color="#333"))
        hfig.update_layout(
            **_chart(h=420, margin=dict(l=80, r=20, t=8, b=80)),
            xaxis=dict(tickfont=dict(size=11, color="#555"), side="bottom"),
            yaxis=dict(tickfont=dict(size=11, color="#555")),
            coloraxis_colorbar=dict(
                title=dict(text="r", font=dict(size=10, color="#aaa")),
                thickness=9, tickfont=dict(size=9, color="#aaa"),
                tickvals=[-1, -0.5, 0, 0.5, 1],
            ),
        )
        st.plotly_chart(hfig, use_container_width=True)

        # Scatter of the strongest pair
        if not pairs:
            st.markdown('<div class="mc-note">Correlation data unavailable.</div>',
                        unsafe_allow_html=True)
            return
        top_a, top_b = pairs[0][2], pairs[0][3]
        top_r = pairs[0][1]
        col_a = DIMS[top_a][0]
        col_b = DIMS[top_b][0]
        color_a = DIMS[top_a][1]

        st.markdown(f'<div class="r-lbl" style="margin-top:1.5rem">STRONGEST PAIR: {top_a.upper()} vs {top_b.upper()} (r = {top_r:.2f})</div>',
                    unsafe_allow_html=True)
        _pop_col = "population" if "population" in df.columns else None
        sfig = px.scatter(
            df.dropna(subset=[col_a, col_b]),
            x=col_a, y=col_b, size=_pop_col, color="region",
            hover_name="name",
            labels={col_a: f"{top_a} vulnerability (0–100)",
                    col_b: f"{top_b} vulnerability (0–100)"},
            size_max=40,
            color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a","#ef4444"],
        )
        sfig.update_layout(
            **_chart(h=300),
            xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
            yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
            legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 4 — Rankings ──────────────────────────────────────────────────────────

def tab_rankings(df: pd.DataFrame) -> None:
    left, right = st.columns([1.1, 2.9], gap="large")

    regions = ["All regions"] + sorted(df["region"].dropna().unique())

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Rankings</h2>'
            '<p class="mc-desc">Countries ranked by overall resilience. '
            'Filter by region to compare within peer groups.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)

        bottom10 = df.nsmallest(10, "resilience")
        top10    = df.nlargest(10, "resilience")
        st.markdown(_sep() + _mg([
            (bottom10.iloc[0]["name"].split(",")[0], f"Most vulnerable · {bottom10.iloc[0]['resilience']:.0f}"),
            (top10.iloc[0]["name"].split(",")[0],    f"Most resilient · {top10.iloc[0]['resilience']:.0f}"),
            (f"{int((df['resilience']<40).sum())}",  "Countries at risk (score < 40)"),
            (f"{int((df['resilience']>60).sum())}",  "Countries stable or better (> 60)"),
        ]), unsafe_allow_html=True)

        st.markdown(_sep() + '<div class="mc-ctrl-lbl">Filter by region</div>',
                    unsafe_allow_html=True)
        region_sel = st.selectbox("", regions, key="rk_region",
                                  label_visibility="collapsed")

        st.markdown('<div class="mc-ctrl-lbl" style="margin-top:10px">Show</div>',
                    unsafe_allow_html=True)
        view = st.radio("", ["Most vulnerable", "Most resilient", "All countries"],
                        key="rk_view", label_visibility="collapsed")

        st.markdown(
            _sep() +
            '<div class="mc-note">Score = 100 − vulnerability. Hover a bar for '
            'individual dimension scores. Width = overall vulnerability index.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        fdf = df if region_sel == "All regions" else df[df["region"] == region_sel]

        if view == "Most vulnerable":
            plot_df = fdf.nsmallest(25, "resilience").sort_values("resilience")
            lbl = "BOTTOM 25 — MOST VULNERABLE COUNTRIES"
            bar_color = "resilience"
            color_scale = ["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"]
        elif view == "Most resilient":
            plot_df = fdf.nlargest(25, "resilience").sort_values("resilience")
            lbl = "TOP 25 — MOST RESILIENT COUNTRIES"
            bar_color = "resilience"
            color_scale = ["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"]
        else:
            plot_df = fdf.sort_values("resilience")
            lbl = f"ALL COUNTRIES{'  ·  ' + region_sel if region_sel != 'All regions' else ''}"
            bar_color = "resilience"
            color_scale = ["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"]

        dim_cols_hover = {v[0]: ":.0f" for v in DIMS.values()}
        st.markdown(f'<div class="r-lbl">{lbl}</div>', unsafe_allow_html=True)
        bfig = px.bar(
            plot_df, x="resilience", y="name", orientation="h",
            color=bar_color,
            color_continuous_scale=color_scale,
            range_color=[0, 100],
            labels={"resilience": "Resilience Score", "name": ""},
            hover_data=dim_cols_hover,
            text="resilience",
        )
        bfig.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        bfig.update_layout(
            **_chart(h=max(500, len(plot_df)*20), margin=dict(l=0, r=60, t=8, b=0)),
            xaxis=dict(range=[0, 108], title="Resilience Score (100 = fully resilient)",
                       gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
            coloraxis_colorbar=dict(title=dict(text="Score", font=dict(size=10, color="#aaa")),
                                    thickness=9, tickfont=dict(size=9, color="#aaa")),
        )
        st.plotly_chart(bfig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="mc-header">
      <div class="mc-topline">
        <span class="mc-dot"></span>
        POLYCRISIS DASHBOARD · DAY 10 · THE RESILIENCE STACK
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Building Country Resilience Scores from 8 World Bank indicators…"):
        df = load_polycrisis_data()

    if df.empty:
        st.error("Failed to load data from World Bank. Please try again.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Resilience Map",
        "Country Profile",
        "Crisis Correlations",
        "Rankings",
    ])

    with tab1: tab_map(df)
    with tab2: tab_country(df)
    with tab3: tab_correlations(df)
    with tab4: tab_rankings(df)


if __name__ == "__main__":
    main()
