"""
The Resilience Stack — Day 09
Climate Migration Pressure Index

Sources:
  World Bank ER.H2O.FWTL.ZS — freshwater withdrawal % (water stress proxy)
  World Bank SN.ITK.DEFC.ZS — undernourishment % (food insecurity)
  World Bank NY.GDP.PCAP.CD — GDP per capita (adaptive capacity)
  World Bank SP.POP.TOTL    — population
  IDMC Global Report on Internal Displacement 2023
  IOM World Migration Report 2022 — 1.2B people at risk of displacement by 2050
  Heat stress index derived from IPCC AR6 WG2 climate hazard maps
"""

import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Climate Migration Pressure · Day 09",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META   = "https://api.worldbank.org/v2/country"
HEADERS   = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
IND_WATER = "ER.H2O.FWTL.ZS"
IND_FOOD  = "SN.ITK.DEFC.ZS"
IND_GDP   = "NY.GDP.PCAP.CD"
IND_POP   = "SP.POP.TOTL"
W_WATER = W_FOOD = W_HEAT = W_ECO = 0.25

HEAT_SCORE: dict[str, float] = {
    "SAU": 95, "ARE": 95, "QAT": 95, "KWT": 95, "BHR": 90, "OMN": 90,
    "YEM": 88, "IRQ": 88, "IRN": 78, "DJI": 92, "ERI": 80,
    "SDN": 92, "SSD": 88, "NER": 92, "MLI": 90, "BFA": 88, "TCD": 90,
    "SEN": 80, "GMB": 78, "GNB": 75, "MRT": 88, "SOM": 85,
    "PAK": 88, "IND": 78, "BGD": 75, "LKA": 65,
    "NGA": 72, "GHA": 70, "CIV": 68, "TGO": 70, "BEN": 70, "CMR": 68,
    "ETH": 72, "KEN": 65, "UGA": 62, "TZA": 62, "MOZ": 60, "ZMB": 58,
    "ZWE": 60, "BWA": 68, "NAM": 65, "AGO": 62, "MDG": 58,
    "EGY": 82, "LBY": 78, "TUN": 70, "DZA": 72, "MAR": 62,
    "SYR": 78, "JOR": 78, "PSE": 75, "AFG": 70, "UZB": 68, "TJK": 55,
    "THA": 78, "VNM": 75, "KHM": 77, "LAO": 72, "MMR": 74,
    "IDN": 70, "PHL": 72, "MYS": 68,
    "MEX": 62, "GTM": 60, "SLV": 62, "HND": 62, "NIC": 60, "HTI": 65,
    "COL": 58, "VEN": 60, "BRA": 58, "BOL": 52, "PRY": 55,
    "ZAF": 48, "COD": 65, "GAB": 62, "COG": 62,
    "CHN": 52, "KOR": 48, "JPN": 50,
    "TUR": 58, "GRC": 62, "ESP": 55, "ITA": 52, "PRT": 52,
    "AUS": 55, "ARG": 42, "CHL": 30, "PER": 48, "ECU": 50,
    "USA": 40, "UKR": 32, "RUS": 25, "KAZ": 42,
    "GBR": 28, "DEU": 30, "FRA": 38, "POL": 32,
    "SWE": 20, "NOR": 18, "FIN": 18, "DNK": 22, "NLD": 28,
    "CAN": 28, "NZL": 32,
}
DEFAULT_HEAT = 52.0

REGIONAL_GROWTH: dict[str, float] = {
    "Sub-Saharan Africa": 2.00, "Middle East & North Africa": 1.48,
    "South Asia": 1.28, "East Asia & Pacific": 1.08,
    "Latin America & Caribbean": 1.18, "Europe & Central Asia": 0.97,
    "North America": 1.14,
}
DEFAULT_GROWTH = 1.15

IDMC_NEW_2022: dict[str, float] = {
    "PAK": 8183, "PHL": 5451, "IND": 2505, "CHN": 2132, "NGA": 2150,
    "BRA": 2069, "COD": 2900, "ETH": 2053, "USA": 1680, "SOM": 1140,
    "AFG": 1020, "SDN": 1065, "BGD": 740,  "MOZ": 420,  "IDN": 452,
    "MEX": 653,  "HND": 447,  "VEN": 409,  "ZMB": 380,  "TZA": 360,
    "KEN": 320,  "MDG": 300,  "HTI": 280,  "ZWE": 260,
}

IDMC_STOCK_2022: dict[str, float] = {
    "SYR": 6865, "COD": 6931, "COL": 6013, "AFG": 4600, "ETH": 3860,
    "YEM": 4527, "SDN": 3706, "PAK": 8200, "NGA": 3640, "SSD": 2225,
    "UKR": 5900, "MMR": 1100, "MOZ": 1102, "SOM": 3024, "IRQ": 1188,
    "CAF": 718,  "MLI": 402,  "CMR": 1098, "TCD": 381,  "BGD": 427,
    "ZWE": 300,  "BRA": 220,  "VEN": 509,
}


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

.mc-left { height: 0; margin: 0; padding: 0; display: block; }
.mc-pad  { padding: 24px 22px 0; }
.mc-title {
  font-size: 1.35rem; font-weight: 800; color: #111; line-height: 1.2;
  margin: 0 0 .4rem; letter-spacing: -.25px;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-desc { font-size: .78rem; color: #888; line-height: 1.65; margin: 0; }
.mc-sep  { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 14px 0; }
.mc-ctrl-lbl { font-size: .78rem; font-weight: 600; color: #333; margin-bottom: 1px; }
.mc-ctrl-sub { font-size: .7rem; color: #bbb; margin-bottom: 6px; }
.mc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 4px 0; }
.mc-val {
  font-size: 1.4rem; font-weight: 700; color: #111; line-height: 1;
  letter-spacing: -.3px; font-variant-numeric: tabular-nums;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-lbl { font-size: .64rem; color: #aaa; margin-top: 4px; line-height: 1.4; }
.mc-sec  { font-size: .67rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.mc-note { font-size: .64rem; color: #ccc; line-height: 1.6; }

.r-lbl { font-size: .67rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #bbb; margin-bottom: 6px; }

.cmpi-badge {
  border-radius: 8px; padding: 14px 16px; margin: 4px 0 12px;
}
.cmpi-badge-label { font-size: .67rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px; }
.cmpi-badge-val { font-size: 2.4rem; font-weight: 900; line-height: 1; letter-spacing: -2px; font-family: 'Space Grotesk', sans-serif; }
.cmpi-badge-name { font-size: .78rem; margin-top: 4px; }

.driver-row { margin-bottom: 12px; }
.driver-lbl { font-size: .72rem; font-weight: 600; color: #555; margin-bottom: 4px; }
.driver-bar-track { background: rgba(0,0,0,0.07); border-radius: 3px; height: 6px; overflow: hidden; }
.driver-bar-fill  { height: 100%; border-radius: 3px; }
.driver-score { font-size: 1.1rem; font-weight: 700; font-family: 'Space Grotesk', sans-serif; line-height: 1; margin-top: 3px; }

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
    df["year"]    = df["date"].astype(int)
    df["iso3"]    = df["countryiso3code"]
    df["country"] = df["country"].apply(lambda x: x["value"] if isinstance(x, dict) else x)
    df["value"]   = df["value"].astype(float)
    return df.sort_values("year", ascending=False).groupby("iso3").first().reset_index()[["iso3","country","year","value"]]


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def load_migration_data() -> pd.DataFrame:
    meta  = _load_country_meta()
    water = _load_wb_latest(IND_WATER).rename(columns={"value": "water_withdrawal"})
    food  = _load_wb_latest(IND_FOOD).rename(columns={"value": "undernourishment"})
    gdp   = _load_wb_latest(IND_GDP).rename(columns={"value": "gdp_pc"})
    pop   = _load_wb_latest(IND_POP).rename(columns={"value": "population"})
    if meta.empty:
        return pd.DataFrame()
    valid = set(meta["iso3"])
    df    = water[water["iso3"].isin(valid)][["iso3","country","water_withdrawal"]]
    for d in [food[["iso3","undernourishment"]], gdp[["iso3","gdp_pc"]], pop[["iso3","population"]]]:
        df = df.merge(d, on="iso3", how="outer")
    df = df.merge(meta[["iso3","name","region"]], on="iso3", how="left")
    df = df[df["iso3"].isin(valid)].copy()
    df["heat_score"]  = df["iso3"].map(HEAT_SCORE).fillna(DEFAULT_HEAT)
    df["water_score"] = (df["water_withdrawal"].fillna(df["water_withdrawal"].median())
                         .clip(0,150) / 150 * 100)
    df["food_score"]  = df["undernourishment"].fillna(df["undernourishment"].median()).clip(0,100)
    def _eco(g):
        if pd.isna(g) or g <= 0: return 80.0
        return max(0, 100 - math.log10(g) / math.log10(80_000) * 100)
    df["eco_score"]   = df["gdp_pc"].apply(_eco)
    df["cmpi"]        = (W_WATER*df["water_score"] + W_FOOD*df["food_score"] +
                         W_HEAT*df["heat_score"]   + W_ECO*df["eco_score"]).round(1)
    df["displaced_new_k"]   = df["iso3"].map(IDMC_NEW_2022).fillna(0)
    df["displaced_stock_k"] = df["iso3"].map(IDMC_STOCK_2022).fillna(0)
    df["growth_factor"]     = df["region"].map(REGIONAL_GROWTH).fillna(DEFAULT_GROWTH)
    df["pop_2050"]          = df["population"] * df["growth_factor"]
    heat_2050               = (df["heat_score"] * 1.18).clip(0,100)
    df["cmpi_2050"]         = (W_WATER*df["water_score"] + W_FOOD*df["food_score"] +
                               W_HEAT*heat_2050           + W_ECO*df["eco_score"]).clip(0,100).round(1)
    df["at_risk_2050_M"]    = (df["pop_2050"] * df["cmpi_2050"] / 100 * 0.12 / 1e6).round(2)
    return df.dropna(subset=["cmpi"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cmpi_color(s: float) -> str:
    if s < 30:  return "#16a34a"
    if s < 50:  return "#ca8a04"
    if s < 65:  return "#ea580c"
    if s < 80:  return "#dc2626"
    return "#7f1d1d"

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


# ── Tab 1 — Pressure Map ─────────────────────────────────────────────────────

def tab_pressure(df: pd.DataFrame) -> None:
    n_high    = int((df["cmpi"] >= 65).sum())
    n_extreme = int((df["cmpi"] >= 80).sum())
    at_risk   = df["at_risk_2050_M"].sum()
    worst     = df.loc[df["cmpi"].idxmax(), "country"]
    worst_v   = df["cmpi"].max()

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Migration Pressure</h2>'
            '<p class="mc-desc">Composite Migration Pressure Index (CMPI) — 25% water stress, '
            '25% food insecurity, 25% heat stress, 25% economic vulnerability. Scale 0–100.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            (f"{n_high}",         "Countries at high risk (≥65)"),
            (f"{n_extreme}",      "Countries at extreme risk (≥80)"),
            (f"{at_risk:.0f}M",   "People at risk by 2050 (SSP2)"),
            (worst.split(",")[0], f"Highest pressure · {worst_v:.0f} CMPI"),
        ]), unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div class="mc-sec">CMPI colour scale</div>'
            '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:4px">'
            '<span style="font-size:.7rem;color:#16a34a">■ &lt;30 Low</span>'
            '<span style="font-size:.7rem;color:#ca8a04">■ 30–50</span>'
            '<span style="font-size:.7rem;color:#ea580c">■ 50–65</span>'
            '<span style="font-size:.7rem;color:#dc2626">■ 65–80 High</span>'
            '<span style="font-size:.7rem;color:#7f1d1d">■ &gt;80 Extreme</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            _sep() +
            '<div class="mc-note">CMPI: World Bank water/food/GDP data + IPCC AR6 WG2 heat index. '
            'Higher = more vulnerable. Use Driver Breakdown tab for per-country detail.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="r-lbl">CLIMATE MIGRATION PRESSURE INDEX (CMPI) — COMPOSITE 0–100</div>',
                    unsafe_allow_html=True)
        fig = px.choropleth(
            df, locations="iso3", color="cmpi",
            color_continuous_scale=["#f0fdf4","#fef9c3","#fed7aa","#fca5a5","#ef4444","#7f1d1d"],
            range_color=[0, 100], hover_name="country",
            hover_data={"iso3": False, "cmpi": ":.0f", "water_score": ":.0f",
                        "food_score": ":.0f", "heat_score": ":.0f", "eco_score": ":.0f"},
        )
        fig.update_layout(
            **_chart(h=480),
            geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#d4d4d4",
                     bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e5e5e5",
                     showocean=True, oceancolor="#ddeeff"),
            coloraxis_colorbar=dict(
                title=dict(text="CMPI", font=dict(size=10, color="#aaa")),
                thickness=9, len=0.5,
                tickvals=[0,25,50,65,80,100],
                ticktext=["0","25","50","65 High","80 Extreme","100"],
                tickfont=dict(size=9, color="#aaa"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">TOP 20 — CMPI BROKEN DOWN BY COMPONENT</div>',
                    unsafe_allow_html=True)
        top20 = df.nlargest(20, "cmpi").sort_values("cmpi")
        bfig  = go.Figure()
        for col, label, color in [
            ("water_score", "Water stress",           "#3b82f6"),
            ("food_score",  "Food insecurity",        "#f59e0b"),
            ("heat_score",  "Heat stress",            "#ef4444"),
            ("eco_score",   "Economic vulnerability", "#8b5cf6"),
        ]:
            bfig.add_trace(go.Bar(name=label, x=top20[col]*0.25, y=top20["country"],
                                  orientation="h", marker_color=color))
        bfig.update_layout(**_chart(h=480, margin=dict(l=0, r=0, t=8, b=0)),
                           barmode="stack",
                           xaxis=dict(title="CMPI (stacked by component)",
                                      gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                           legend=dict(orientation="h", y=1.04, font=dict(size=9, color="#888"),
                                       bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(bfig, use_container_width=True)


# ── Tab 2 — Current Displacement ─────────────────────────────────────────────

def tab_displacement(df: pd.DataFrame) -> None:
    idmc_df = df[df["displaced_new_k"] > 0].copy()
    total_new   = idmc_df["displaced_new_k"].sum() / 1000
    total_stock = df["displaced_stock_k"].sum() / 1000
    worst_new   = idmc_df.loc[idmc_df["displaced_new_k"].idxmax(), "country"]
    worst_stock = df[df["displaced_stock_k"] > 0].loc[
                  df[df["displaced_stock_k"] > 0]["displaced_stock_k"].idxmax(), "country"]

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Current Displacement</h2>'
            '<p class="mc-desc">IDMC 2023 — new climate/disaster displacements 2022 '
            'and total internally displaced persons stock.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            ("32.6M",             "New climate displacements 2022 — IDMC"),
            (f"{total_new:.1f}M", "Modelled (top countries in dataset)"),
            (worst_new,           "Most new displacements 2022"),
            (worst_stock,         "Largest displaced population"),
        ]), unsafe_allow_html=True)

        st.markdown(_sep() + '<div class="mc-ctrl-lbl">View</div>', unsafe_allow_html=True)
        view = st.radio("", ["New displacements 2022", "Total displaced stock"],
                        key="d_view", label_visibility="collapsed")

        st.markdown(
            _sep() +
            '<div class="mc-note">IDMC Global Report on Internal Displacement 2023. '
            'New = climate/disaster events only. Stock includes conflict.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        if view.startswith("New"):
            plot_df = idmc_df.nlargest(20, "displaced_new_k").sort_values("displaced_new_k").copy()
            plot_df["val_M"] = plot_df["displaced_new_k"] / 1000
            x_col, x_lbl = "val_M", "New displacements 2022 (millions)"
            lbl = "TOP 20 — NEW CLIMATE/DISASTER DISPLACEMENTS 2022"
        else:
            stock_df = df[df["displaced_stock_k"] > 0].copy()
            stock_df["val_M"] = stock_df["displaced_stock_k"] / 1000
            plot_df  = stock_df.nlargest(20, "displaced_stock_k").sort_values("displaced_stock_k").copy()
            x_col, x_lbl = "val_M", "Total internally displaced (millions)"
            lbl = "TOP 20 — TOTAL DISPLACED PERSONS STOCK 2022"

        st.markdown(f'<div class="r-lbl">{lbl}</div>', unsafe_allow_html=True)
        bfig = px.bar(plot_df, x=x_col, y="country", orientation="h",
                      color="cmpi",
                      color_continuous_scale=["#fef9c3","#f97316","#ef4444","#7f1d1d"],
                      range_color=[30, 90],
                      labels={x_col: x_lbl, "country": "", "cmpi": "CMPI"},
                      hover_data={"cmpi": ":.0f", "region": True}, text=x_col)
        bfig.update_traces(texttemplate="%{x:.1f}M", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        bfig.update_layout(**_chart(h=540, margin=dict(l=0, r=80, t=8, b=0)),
                           xaxis=dict(title=x_lbl, gridcolor="rgba(0,0,0,0.06)",
                                      color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                           coloraxis_colorbar=dict(title="CMPI", thickness=9,
                                                   tickfont=dict(size=9, color="#aaa")))
        st.plotly_chart(bfig, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">CLIMATE PRESSURE vs ACTUAL DISPLACEMENT</div>',
                    unsafe_allow_html=True)
        sc_df = df[(df["displaced_new_k"] > 0) & df["cmpi"].notna()].copy()
        sc_df["new_M"] = sc_df["displaced_new_k"] / 1000
        sfig = px.scatter(sc_df, x="cmpi", y="new_M", size="population", color="region",
                          hover_name="country",
                          labels={"cmpi": "CMPI score", "new_M": "New displacements 2022 (M)"},
                          size_max=50, log_y=True,
                          color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b"])
        sfig.update_layout(**_chart(h=300),
                           xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 3 — 2050 Hotspots ─────────────────────────────────────────────────────

def tab_projections(df: pd.DataFrame) -> None:
    total_2050    = df["at_risk_2050_M"].sum()
    reg_totals    = df.groupby("region")["at_risk_2050_M"].sum().sort_values(ascending=False)
    top_region    = reg_totals.index[0]
    top_region_v  = reg_totals.iloc[0]
    n_over_10m    = int((df["at_risk_2050_M"] >= 10).sum())

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">2050 Hotspots</h2>'
            '<p class="mc-desc">Under SSP2 / 2°C: +18% heat stress, UN population projections. '
            'At-risk calibrated to IOM 1.2B estimate.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            (f"{total_2050:.0f}M",                   "People at risk by 2050"),
            (top_region.split("&")[0].strip()[:14],  f"Highest-risk region · {top_region_v:.0f}M"),
            (f"{n_over_10m}",                        "Countries with >10M at risk"),
            ("1.2 billion",                          "IOM upper estimate by 2050"),
        ]), unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div style="background:#fff7f7;border:1px solid rgba(220,38,38,0.1);'
            'border-left:3px solid #dc2626;border-radius:0 6px 6px 0;padding:.8rem 1rem;'
            'margin-bottom:4px">'
            '<div style="font-size:.67rem;font-weight:700;letter-spacing:.1em;'
            'text-transform:uppercase;color:#dc2626;margin-bottom:.3rem">IOM PROJECTION</div>'
            '<div style="font-size:.75rem;color:#555;line-height:1.65">'
            'At 2°C, 1.2 billion people could be displaced by 2050 — '
            'primarily from sea level rise, crop failure, extreme heat, and water stress. '
            '<span style="color:#aaa;font-size:.7rem">IOM WMR 2022 · Rigaud et al. 2018</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="mc-note">SSP2: +18% heat stress above current levels. '
            'Population: UN WPP 2022 regional growth rates. '
            'At-risk = pop × CMPI/100 × 12% factor. Not a forecast.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="r-lbl">TOP 25 — PEOPLE AT DISPLACEMENT RISK BY 2050 (SSP2 / 2°C)</div>',
                    unsafe_allow_html=True)
        top25 = df.nlargest(25, "at_risk_2050_M").sort_values("at_risk_2050_M").copy()
        top25["cmpi_delta"] = (top25["cmpi_2050"] - top25["cmpi"]).clip(lower=0)
        pfig = go.Figure()
        pfig.add_trace(go.Bar(
            name="Current CMPI component",
            x=top25["cmpi"]/100 * top25["at_risk_2050_M"],
            y=top25["country"], orientation="h", marker_color="#f97316",
        ))
        pfig.add_trace(go.Bar(
            name="Additional 2050 heat stress",
            x=top25["cmpi_delta"]/100 * top25["at_risk_2050_M"],
            y=top25["country"], orientation="h", marker_color="#7f1d1d",
        ))
        pfig.update_layout(**_chart(h=540, margin=dict(l=0, r=0, t=8, b=0)),
                           barmode="stack",
                           xaxis=dict(title="People at risk 2050 (millions)",
                                      gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                           legend=dict(orientation="h", y=1.04, font=dict(size=9, color="#888"),
                                       bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(pfig, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">BY REGION — PEOPLE AT RISK 2050</div>',
                    unsafe_allow_html=True)
        reg = (df.groupby("region")[["at_risk_2050_M","population"]].sum()
               .reset_index().sort_values("at_risk_2050_M", ascending=False))
        reg["pct"] = reg["at_risk_2050_M"] * 1e6 / reg["population"] * 100
        rfig = px.bar(reg, x="region", y="at_risk_2050_M", color="pct",
                      color_continuous_scale=["#fef9c3","#f97316","#7f1d1d"],
                      labels={"at_risk_2050_M": "People at risk (M)", "pct": "% of pop"},
                      text="at_risk_2050_M")
        rfig.update_traces(texttemplate="%{y:.0f}M", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        rfig.update_layout(**_chart(h=300, margin=dict(l=0, r=0, t=8, b=80)),
                           xaxis=dict(showgrid=False, tickangle=-20, color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(title="People at risk (M)", gridcolor="rgba(0,0,0,0.06)",
                                      color="#bbb", tickfont=dict(size=10)),
                           coloraxis_colorbar=dict(title="% of pop", thickness=9,
                                                   tickfont=dict(size=9, color="#aaa")))
        st.plotly_chart(rfig, use_container_width=True)


# ── Tab 4 — Driver Breakdown ──────────────────────────────────────────────────

def tab_drivers(df: pd.DataFrame) -> None:
    left, right = st.columns([1.1, 2.9], gap="large")

    countries = sorted(df["country"].dropna().unique())
    default   = countries.index("Pakistan") if "Pakistan" in countries else 0

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Driver Breakdown</h2>'
            '<p class="mc-desc">Per-country CMPI decomposition — each driver scored 0–100.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep(), unsafe_allow_html=True)

        sel = st.selectbox("Country", countries, index=default, key="d_country",
                           label_visibility="collapsed")
        row = df[df["country"] == sel].iloc[0]
        cmpi  = row["cmpi"]
        color = _cmpi_color(cmpi)

        st.markdown(
            f'<div class="cmpi-badge" style="background:{color}14;border:1px solid {color}30">'
            f'<div class="cmpi-badge-label" style="color:{color}">CMPI SCORE</div>'
            f'<div class="cmpi-badge-val" style="color:{color}">{cmpi:.0f}</div>'
            f'<div class="cmpi-badge-name" style="color:#555">{sel}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        drivers = [
            ("Water stress",         row["water_score"], "#3b82f6"),
            ("Food insecurity",      row["food_score"],  "#f59e0b"),
            ("Heat stress",          row["heat_score"],  "#ef4444"),
            ("Economic vulnerability", row["eco_score"], "#8b5cf6"),
        ]
        html = ""
        for lbl, score, dc in drivers:
            html += (f'<div class="driver-row">'
                     f'<div class="driver-lbl">{lbl}</div>'
                     f'<div style="display:flex;align-items:center;gap:8px">'
                     f'<div style="flex:1"><div class="driver-bar-track">'
                     f'<div class="driver-bar-fill" style="width:{int(score)}%;background:{dc}"></div>'
                     f'</div></div>'
                     f'<div class="driver-score" style="color:{dc}">{score:.0f}</div>'
                     f'</div></div>')
        st.markdown(html, unsafe_allow_html=True)

        if row["displaced_new_k"] > 0 or row["displaced_stock_k"] > 0:
            st.markdown(_sep(), unsafe_allow_html=True)
            idmc_html = '<div class="mc-sec">IDMC 2022 displacement</div>'
            if row["displaced_new_k"] > 0:
                idmc_html += (f'<div class="mc-val">{row["displaced_new_k"]/1000:.2f}M</div>'
                              f'<div class="mc-lbl">New climate displacements 2022</div>')
            if row["displaced_stock_k"] > 0:
                idmc_html += (f'<div class="mc-val" style="margin-top:8px">{row["displaced_stock_k"]/1000:.2f}M</div>'
                              f'<div class="mc-lbl">Total displaced stock 2022</div>')
            st.markdown(idmc_html, unsafe_allow_html=True)

        st.markdown(
            _sep() +
            '<div class="mc-note">Radar: each CMPI driver 0–100. Red dashed = 65 high-risk threshold. '
            '2050: +18% heat stress + UN WPP regional population growth (SSP2).</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        cats   = ["Water stress","Food insecurity","Heat stress","Economic vulnerability","Water stress"]
        vals   = [row["water_score"],row["food_score"],row["heat_score"],row["eco_score"],row["water_score"]]
        rfig   = go.Figure()
        rfig.add_trace(go.Scatterpolar(r=vals, theta=cats, fill="toself",
                                       fillcolor="rgba(234,88,12,0.18)",
                                       line=dict(color="#ea580c", width=2), name=sel))
        rfig.add_trace(go.Scatterpolar(r=[65,65,65,65,65], theta=cats,
                                       line=dict(color="#dc2626", width=1, dash="dot"),
                                       name="High-risk threshold (65)", mode="lines"))
        rfig.update_layout(
            polar=dict(radialaxis=dict(range=[0,100], tickfont=dict(size=9, color="#aaa")),
                       bgcolor="rgba(0,0,0,0)"),
            **_chart(h=360, margin=dict(l=20,r=20,t=20,b=40)),
            legend=dict(orientation="h", y=-0.08, font=dict(size=9, color="#888"),
                        bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(rfig, use_container_width=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("CMPI 2050",       f"{row['cmpi_2050']:.0f}",  f"+{row['cmpi_2050']-row['cmpi']:.0f}")
        m2.metric("Population 2050", f"{row['pop_2050']/1e6:.0f}M", f"×{row['growth_factor']:.2f}")
        m3.metric("At risk 2050",    f"{row['at_risk_2050_M']:.1f}M")

        st.markdown('<div class="r-lbl" style="margin-top:1.2rem">REGIONAL CMPI COMPARISON</div>',
                    unsafe_allow_html=True)
        reg_df = (df[df["region"] == row["region"]]
                  .sort_values("cmpi", ascending=False).head(15)
                  .copy())
        reg_df["highlight"] = reg_df["country"] == sel
        cfig = px.bar(reg_df.sort_values("cmpi"), x="cmpi", y="country", orientation="h",
                      color="highlight",
                      color_discrete_map={True: "#ea580c", False: "#d1d5db"},
                      labels={"cmpi": "CMPI", "country": ""},
                      text="cmpi")
        cfig.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        cfig.update_layout(**_chart(h=max(280, len(reg_df)*26), margin=dict(l=0, r=60, t=8, b=0)),
                           xaxis=dict(range=[0,105], gridcolor="rgba(0,0,0,0.06)",
                                      color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                           showlegend=False)
        st.plotly_chart(cfig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="mc-header">
      <div class="mc-topline">
        <span class="mc-dot"></span>
        MIGRATION PRESSURE EXPLORER · DAY 09 · THE RESILIENCE STACK
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        df = load_migration_data()

    if df.empty:
        st.error("Failed to load data from World Bank.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Pressure Map",
        "Current Displacement",
        "2050 Hotspots",
        "Driver Breakdown",
    ])

    with tab1: tab_pressure(df)
    with tab2: tab_displacement(df)
    with tab3: tab_projections(df)
    with tab4: tab_drivers(df)


if __name__ == "__main__":
    main()
