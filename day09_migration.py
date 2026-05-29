"""
The Resilience Stack — Day 09
Climate Migration Pressure Index

Sources:
  World Bank ER.H2O.FWTL.ZS — freshwater withdrawal % (water stress proxy)
  World Bank SN.ITK.DEFC.ZS — undernourishment % (food insecurity)
  World Bank NY.GDP.PCAP.CD — GDP per capita (adaptive capacity)
  World Bank SP.POP.TOTL    — population
  IDMC Global Report on Internal Displacement 2023 — embedded displacement stock & flows
  IOM World Migration Report 2022 — 1.2B people at risk of displacement by 2050
  Heat stress index derived from climate zone classification (IPCC AR6 WG2)
"""

import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Climate Migration Pressure Index · Day 09",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_WATER = "ER.H2O.FWTL.ZS"   # freshwater withdrawal % of internal resources
IND_FOOD  = "SN.ITK.DEFC.ZS"   # prevalence of undernourishment %
IND_GDP   = "NY.GDP.PCAP.CD"    # GDP per capita (current USD)
IND_POP   = "SP.POP.TOTL"       # total population

# CMPI component weights (must sum to 1.0)
W_WATER = 0.25
W_FOOD  = 0.25
W_HEAT  = 0.25
W_ECO   = 0.25

# Heat stress score 0-100 per country (higher = worse)
# Derived from IPCC AR6 WG2 climate hazard maps + Koppen-Geiger climate zones
HEAT_SCORE: dict[str, float] = {
    # Extreme (>80): Arabian Peninsula, Sahel, Horn of Africa
    "SAU": 95, "ARE": 95, "QAT": 95, "KWT": 95, "BHR": 90, "OMN": 90,
    "YEM": 88, "IRQ": 88, "IRN": 78, "DJI": 92, "ERI": 80,
    "SDN": 92, "SSD": 88, "NER": 92, "MLI": 90, "BFA": 88, "TCD": 90,
    "SEN": 80, "GMB": 78, "GNB": 75, "MRT": 88, "SOM": 85,
    # Very high (65-80): South Asia, West Africa, MENA interior
    "PAK": 88, "IND": 78, "BGD": 75, "LKA": 65,
    "NGA": 72, "GHA": 70, "CIV": 68, "TGO": 70, "BEN": 70, "CMR": 68,
    "ETH": 72, "KEN": 65, "UGA": 62, "TZA": 62, "MOZ": 60, "ZMB": 58,
    "ZWE": 60, "BWA": 68, "NAM": 65, "AGO": 62, "MDG": 58,
    "EGY": 82, "LBY": 78, "TUN": 70, "DZA": 72, "MAR": 62,
    "SYR": 78, "JOR": 78, "PSE": 75, "AFG": 70, "UZB": 68, "TJK": 55,
    # High (45-65): SE Asia, Central America, coastal tropics
    "THA": 78, "VNM": 75, "KHM": 77, "LAO": 72, "MMR": 74,
    "IDN": 70, "PHL": 72, "MYS": 68,
    "MEX": 62, "GTM": 60, "SLV": 62, "HND": 62, "NIC": 60, "HTI": 65,
    "COL": 58, "VEN": 60, "BRA": 58, "BOL": 52, "PRY": 55,
    "ZAF": 48, "COD": 65, "GAB": 62, "COG": 62,
    # Moderate (25-45): East Asia, S Europe, southern temperate
    "CHN": 52, "KOR": 48, "JPN": 50, "TWN": 62,
    "TUR": 58, "GRC": 62, "ESP": 55, "ITA": 52, "PRT": 52,
    "AUS": 55, "ARG": 42, "CHL": 30, "PER": 48, "ECU": 50,
    "USA": 40, "UKR": 32, "RUS": 25, "KAZ": 42,
    # Low (<25): Northern Europe, high latitudes
    "GBR": 28, "DEU": 30, "FRA": 38, "POL": 32, "CZE": 28,
    "SWE": 20, "NOR": 18, "FIN": 18, "DNK": 22, "NLD": 28,
    "CAN": 28, "NZL": 32, "BLR": 28,
}
DEFAULT_HEAT = 52.0

# Regional population growth factor 2022 → 2050 (UN World Population Prospects 2022)
REGIONAL_GROWTH: dict[str, float] = {
    "Sub-Saharan Africa":                    2.00,
    "Middle East & North Africa":            1.48,
    "South Asia":                            1.28,
    "East Asia & Pacific":                   1.08,
    "Latin America & Caribbean":             1.18,
    "Europe & Central Asia":                 0.97,
    "North America":                         1.14,
}
DEFAULT_GROWTH = 1.15

# IDMC Global Report on Internal Displacement 2023
# Climate/disaster-induced NEW displacements 2022 (thousands)
IDMC_NEW_2022: dict[str, float] = {
    "PAK": 8183, "PHL": 5451, "IND": 2505, "CHN": 2132, "NGA": 2150,
    "BRA": 2069, "COD": 2900, "ETH": 2053, "USA": 1680, "SOM": 1140,
    "AFG": 1020, "SDN": 1065, "BGD": 740,  "MOZ": 420,  "IDN": 452,
    "MEX": 653,  "HND": 447,  "VEN": 409,  "ZMB": 380,  "TZA": 360,
    "KEN": 320,  "MDG": 300,  "HTI": 280,  "ZWE": 260,
}

# IDMC total internally displaced persons stock end-2022 (thousands) — all causes
IDMC_STOCK_2022: dict[str, float] = {
    "SYR": 6865, "COD": 6931, "COL": 6013, "AFG": 4600, "ETH": 3860,
    "YEM": 4527, "SDN": 3706, "PAK": 8200, "NGA": 3640, "SSD": 2225,
    "UKR": 5900, "MMR": 1100, "MOZ": 1102, "SOM": 3024, "IRQ": 1188,
    "CAF": 718,  "MLI": 402,  "CMR": 1098, "TCD": 381,  "LBY": 188,
    "ZWE": 300,  "BRA": 220,  "VEN": 509,  "COL": 6013, "BGD": 427,
}


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.rs-header {
    background: linear-gradient(135deg, #431407 0%, #7c2d12 55%, #9a3412 100%);
    border-radius: 16px; padding: 2rem 2.5rem 1.8rem; color: #fff; margin-bottom: 1.5rem;
}
.rs-header h1 { font-size: 2rem; font-weight: 800; margin: 0 0 .25rem; letter-spacing: -.5px; }
.rs-header p  { font-size: .95rem; color: #fed7aa; margin: 0; }
.rs-badge {
    display: inline-block; background: rgba(255,255,255,.12);
    border-radius: 20px; padding: 2px 12px; font-size: .75rem; font-weight: 600;
    color: #ffedd5; margin-bottom: .6rem; letter-spacing: .5px;
}

.stat-card { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 12px; padding: 1rem 1.2rem; }
.stat-val  { font-size: 1.6rem; font-weight: 700; color: #7c2d12; line-height: 1; }
.stat-lbl  { font-size: .75rem; color: #64748b; margin-top: .25rem; }
.stat-card.neutral { background: #f8fafc; border-color: #e2e8f0; }
.stat-card.neutral .stat-val { color: #0f172a; }
.stat-card.crit { background: #fef2f2; border-color: #fecaca; }
.stat-card.crit .stat-val { color: #7f1d1d; }

.iom-panel {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    border-radius: 12px; padding: 1.2rem 1.5rem; color: #fff; margin: 1rem 0;
}
.iom-panel h4 { margin: 0 0 .5rem; font-size: 1rem; font-weight: 700; }
.iom-panel p  { margin: 0; font-size: .85rem; color: #c7d2fe; line-height: 1.6; }

.driver-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: .8rem 1rem; margin-bottom: .5rem;
}
.driver-card .label { font-size: .75rem; color: #64748b; }
.driver-card .score { font-size: 1.3rem; font-weight: 700; color: #7c2d12; }

.method-note {
    background: #fff7ed; border-left: 3px solid #f97316;
    padding: .6rem 1rem; border-radius: 0 8px 8px 0;
    font-size: .78rem; color: #475569; margin-top: 1rem;
}
section[data-testid="stSidebar"] { display: none; }
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
                    rows.append({
                        "iso3":   c["id"],
                        "name":   c["name"],
                        "region": reg.get("value", ""),
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
    df["year"]    = df["date"].astype(int)
    df["iso3"]    = df["countryiso3code"]
    df["country"] = df["country"].apply(lambda x: x["value"] if isinstance(x, dict) else x)
    df["value"]   = df["value"].astype(float)
    # Keep most recent value per country
    df = df.sort_values("year", ascending=False).groupby("iso3").first().reset_index()
    return df[["iso3", "country", "year", "value"]]


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
    dfs = [
        water[water["iso3"].isin(valid)][["iso3", "country", "water_withdrawal"]],
        food[food["iso3"].isin(valid)][["iso3", "undernourishment"]],
        gdp[gdp["iso3"].isin(valid)][["iso3", "gdp_pc"]],
        pop[pop["iso3"].isin(valid)][["iso3", "population"]],
    ]
    df = dfs[0]
    for d in dfs[1:]:
        df = df.merge(d, on="iso3", how="outer")

    df = df.merge(meta[["iso3", "name", "region"]], on="iso3", how="left")
    df = df[df["iso3"].isin(valid)].copy()

    # Heat score
    df["heat_score"] = df["iso3"].map(HEAT_SCORE).fillna(DEFAULT_HEAT)

    # Normalise components 0-100
    # Water: >100% withdrawal = fully stressed; cap at 150
    df["water_score"] = (df["water_withdrawal"].fillna(df["water_withdrawal"].median())
                         .clip(0, 150) / 150 * 100)
    # Food: undernourishment % is already 0-100
    df["food_score"] = df["undernourishment"].fillna(df["undernourishment"].median()).clip(0, 100)
    # Economic vulnerability: inverse of log-normalised GDP/capita (max $80k)
    import math
    def _eco(g):
        if pd.isna(g) or g <= 0:
            return 80.0
        return max(0, 100 - math.log10(g) / math.log10(80_000) * 100)
    df["eco_score"] = df["gdp_pc"].apply(_eco)

    # Composite CMPI
    df["cmpi"] = (W_WATER * df["water_score"] +
                  W_FOOD  * df["food_score"]  +
                  W_HEAT  * df["heat_score"]  +
                  W_ECO   * df["eco_score"]).round(1)

    # Displacement data
    df["displaced_new_k"] = df["iso3"].map(IDMC_NEW_2022).fillna(0)
    df["displaced_stock_k"] = df["iso3"].map(IDMC_STOCK_2022).fillna(0)

    # 2050 projection
    df["growth_factor"] = df["region"].map(REGIONAL_GROWTH).fillna(DEFAULT_GROWTH)
    df["pop_2050"]      = df["population"] * df["growth_factor"]
    heat_2050           = (df["heat_score"] * 1.18).clip(0, 100)   # +18% heat stress under SSP2
    df["cmpi_2050"]     = (W_WATER * df["water_score"] +
                           W_FOOD  * df["food_score"]  +
                           W_HEAT  * heat_2050          +
                           W_ECO   * df["eco_score"]).clip(0, 100).round(1)
    # At-risk: people potentially displaced at 2°C (calibrated to IOM 1.2B estimate)
    df["at_risk_2050_M"] = (df["pop_2050"] * df["cmpi_2050"] / 100 * 0.12 / 1e6).round(2)

    return df.dropna(subset=["cmpi"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _card(val: str, lbl: str, cls: str = "neutral") -> str:
    return (f'<div class="stat-card {cls}">'
            f'<div class="stat-val">{val}</div>'
            f'<div class="stat-lbl">{lbl}</div></div>')


def _cmpi_color(score: float) -> str:
    if score < 30: return "#22c55e"
    if score < 50: return "#eab308"
    if score < 65: return "#f97316"
    if score < 80: return "#ef4444"
    return "#7f1d1d"


# ── Tab 1 — Migration Pressure Map ───────────────────────────────────────────

def tab_pressure_map(df: pd.DataFrame) -> None:
    n_high   = (df["cmpi"] >= 65).sum()
    n_extreme = (df["cmpi"] >= 80).sum()
    at_risk   = df["at_risk_2050_M"].sum()
    worst     = df.loc[df["cmpi"].idxmax(), "country"]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(f"{n_high}", "Countries at high climate migration risk (CMPI ≥ 65)"), unsafe_allow_html=True)
    c2.markdown(_card(f"{n_extreme}", "Countries at extreme risk (CMPI ≥ 80)", "crit"), unsafe_allow_html=True)
    c3.markdown(_card(f"{at_risk:.0f}M", "People at displacement risk by 2050 (SSP2)", "crit"), unsafe_allow_html=True)
    c4.markdown(_card(worst.split(",")[0], "Highest pressure country"), unsafe_allow_html=True)

    st.markdown("---")

    fig = px.choropleth(
        df, locations="iso3", color="cmpi",
        color_continuous_scale=["#f0fdf4", "#fef9c3", "#fed7aa", "#fca5a5", "#ef4444", "#7f1d1d"],
        range_color=[0, 100],
        labels={"cmpi": "CMPI score"},
        hover_name="country",
        hover_data={"iso3": False, "cmpi": ":.0f", "water_score": ":.0f",
                    "food_score": ":.0f", "heat_score": ":.0f", "eco_score": ":.0f"},
        title="Climate Migration Pressure Index (CMPI) — composite score 0-100",
    )
    fig.update_layout(
        height=490, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#cbd5e1",
                 bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e2e8f0",
                 showocean=True, oceancolor="#e0f2fe"),
        coloraxis_colorbar=dict(title="CMPI", thickness=12, len=0.55,
                                tickvals=[0, 25, 50, 65, 80, 100],
                                ticktext=["0 Safe", "25", "50", "65 High", "80 Extreme", "100"]),
        margin=dict(l=0, r=0, t=40, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Top 20 ranked bar
    st.markdown("#### Top 20 highest-pressure countries")
    top20 = df.nlargest(20, "cmpi").sort_values("cmpi")
    bfig = go.Figure()
    for col, label, color in [
        ("water_score", "Water stress",        "#3b82f6"),
        ("food_score",  "Food insecurity",     "#f59e0b"),
        ("heat_score",  "Heat stress",         "#ef4444"),
        ("eco_score",   "Economic vulnerability", "#8b5cf6"),
    ]:
        bfig.add_trace(go.Bar(
            name=label, x=top20[col] * 0.25, y=top20["country"],
            orientation="h", marker_color=color,
        ))
    bfig.update_layout(
        barmode="stack", height=500,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="CMPI score (stacked by component)", gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=1.06), font=dict(family="Inter"),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(bfig, use_container_width=True)

    st.markdown('<div class="method-note">CMPI = 25% water stress + 25% food insecurity + 25% heat stress + 25% economic vulnerability. All components normalised 0–100. Higher = worse. World Bank data for water, food, GDP; climate-zone heat index (IPCC AR6 WG2). See Tab 4 for per-country driver breakdown.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Current Displacement ─────────────────────────────────────────────

def tab_displacement(df: pd.DataFrame) -> None:
    idmc_df = df[df["displaced_new_k"] > 0].copy()
    idmc_df["displaced_new_M"] = idmc_df["displaced_new_k"] / 1000

    total_new   = idmc_df["displaced_new_k"].sum() / 1000
    total_stock = df["displaced_stock_k"].sum() / 1000
    worst_new   = idmc_df.loc[idmc_df["displaced_new_k"].idxmax(), "country"]

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card("32.6M", "New climate/disaster displacements in 2022 (IDMC)"), unsafe_allow_html=True)
    c2.markdown(_card(f"{total_new:.1f}M",
                      "Modelled from embedded IDMC dataset (top countries)", "crit"), unsafe_allow_html=True)
    c3.markdown(_card(worst_new, "Most new climate displacements in 2022"), unsafe_allow_html=True)

    st.markdown("---")

    view = st.radio("Show", ["New displacements 2022", "Total displaced (stock)"],
                    horizontal=True, key="t2_view")

    if view.startswith("New"):
        plot_df = idmc_df.nlargest(20, "displaced_new_k").sort_values("displaced_new_k").copy()
        x_col, x_lbl = "displaced_new_M", "New displacements 2022 (millions)"
    else:
        stock_df = df[df["displaced_stock_k"] > 0].copy()
        stock_df["displaced_stock_M"] = stock_df["displaced_stock_k"] / 1000
        plot_df  = stock_df.nlargest(20, "displaced_stock_k").sort_values("displaced_stock_k").copy()
        x_col, x_lbl = "displaced_stock_M", "Total internally displaced (millions)"

    bfig = px.bar(
        plot_df, x=x_col, y="country", orientation="h",
        color="cmpi",
        color_continuous_scale=["#fef9c3", "#f97316", "#ef4444", "#7f1d1d"],
        range_color=[30, 90],
        labels={x_col: x_lbl, "country": "", "cmpi": "CMPI"},
        hover_data={"cmpi": ":.0f", "region": True},
        text=x_col,
    )
    bfig.update_traces(texttemplate="%{x:.1f}M", textposition="outside")
    bfig.update_layout(
        height=520, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=x_lbl, gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        coloraxis_colorbar=dict(title="CMPI", thickness=10),
        margin=dict(l=0, r=80, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(bfig, use_container_width=True)

    # Displacement vs CMPI scatter
    st.markdown("#### Climate pressure vs actual displacement")
    sc_df = df[(df["displaced_new_k"] > 0) & df["cmpi"].notna()].copy()
    sc_df["new_M"] = sc_df["displaced_new_k"] / 1000
    sfig = px.scatter(
        sc_df, x="cmpi", y="new_M",
        size="population", color="region",
        hover_name="country",
        labels={"cmpi": "CMPI score", "new_M": "New displacements 2022 (M)", "population": "Population"},
        size_max=55, log_y=True,
    )
    sfig.update_layout(
        height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#e2e8f0"), yaxis=dict(gridcolor="#e2e8f0"),
        font=dict(family="Inter"), margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(sfig, use_container_width=True)

    st.markdown('<div class="method-note">Displacement data: IDMC Global Report on Internal Displacement 2023. New displacements = climate/disaster events (excludes conflict). Total stock includes conflict-driven displacement. CMPI from World Bank + heat index.</div>',
                unsafe_allow_html=True)


# ── Tab 3 — 2050 Hotspot Projections ─────────────────────────────────────────

def tab_projections(df: pd.DataFrame) -> None:
    st.markdown("""
    <div class="iom-panel">
      <h4>🔭 IOM Projection: 1.2 Billion People at Risk by 2050</h4>
      <p>
        The International Organization for Migration estimates that at 2°C of warming,
        1.2 billion people could be displaced by 2050 — primarily from sea level rise,
        agricultural collapse, extreme heat, and freshwater stress. Sub-Saharan Africa,
        South Asia, and the Pacific face the greatest compounding risks.
        <br><br>
        <em>IOM World Migration Report 2022 · Rigaud et al. 2018 Groundswell (World Bank)</em>
      </p>
    </div>
    """, unsafe_allow_html=True)

    total_2050 = df["at_risk_2050_M"].sum()
    top_region = (df.groupby("region")["at_risk_2050_M"].sum()
                  .sort_values(ascending=False).index[0])
    top_region_val = df.groupby("region")["at_risk_2050_M"].sum().max()
    n_over_10m = (df["at_risk_2050_M"] >= 10).sum()

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card(f"{total_2050:.0f}M", "People at displacement risk by 2050 (modelled)", "crit"),
                unsafe_allow_html=True)
    c2.markdown(_card(f"{top_region.split('&')[0].strip()}", f"Highest-risk region ({top_region_val:.0f}M at risk)"),
                unsafe_allow_html=True)
    c3.markdown(_card(f"{n_over_10m}", "Countries with >10M people at risk"), unsafe_allow_html=True)

    st.markdown("---")

    # Top 25 countries by at-risk population 2050
    st.markdown("#### Top 25 countries: people at displacement risk 2050 (SSP2 / 2°C)")
    top25 = df.nlargest(25, "at_risk_2050_M").sort_values("at_risk_2050_M").copy()
    top25["cmpi_change"] = top25["cmpi_2050"] - top25["cmpi"]

    pfig = go.Figure()
    pfig.add_trace(go.Bar(
        name="Current CMPI", x=top25["cmpi"] / 100 * top25["at_risk_2050_M"],
        y=top25["country"], orientation="h", marker_color="#f97316",
    ))
    pfig.add_trace(go.Bar(
        name="Additional heat stress 2050", x=top25["cmpi_change"].clip(lower=0) / 100 * top25["at_risk_2050_M"],
        y=top25["country"], orientation="h", marker_color="#7f1d1d",
    ))
    pfig.update_layout(
        barmode="stack", height=560,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="People at displacement risk 2050 (millions)", gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=1.06), font=dict(family="Inter"),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(pfig, use_container_width=True)

    # Regional breakdown
    st.markdown("#### By region — people at risk 2050")
    reg = (df.groupby("region")[["at_risk_2050_M", "population"]]
             .sum().reset_index()
             .sort_values("at_risk_2050_M", ascending=False))
    reg["pct_of_pop"] = reg["at_risk_2050_M"] * 1e6 / reg["population"] * 100

    rfig = px.bar(
        reg, x="region", y="at_risk_2050_M",
        color="pct_of_pop",
        color_continuous_scale=["#fef9c3", "#f97316", "#7f1d1d"],
        labels={"at_risk_2050_M": "People at risk (millions)", "pct_of_pop": "% of regional pop"},
        text="at_risk_2050_M",
    )
    rfig.update_traces(texttemplate="%{y:.0f}M", textposition="outside")
    rfig.update_layout(
        height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickangle=-20),
        yaxis=dict(title="People at risk (millions)", gridcolor="#e2e8f0"),
        coloraxis_colorbar=dict(title="% of pop", thickness=12),
        margin=dict(l=0, r=0, t=30, b=80), font=dict(family="Inter"),
    )
    st.plotly_chart(rfig, use_container_width=True)

    st.markdown('<div class="method-note">2050 projection: current CMPI adjusted for +18% heat stress under SSP2 (1.5-2°C warming, IPCC AR6). Population scaled by UN WPP 2022 regional growth rates. At-risk = pop × CMPI/100 × 12% displacement factor, calibrated to IOM 1.2B global estimate. Not a forecast — a relative pressure index.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — Driver Breakdown ──────────────────────────────────────────────────

def tab_drivers(df: pd.DataFrame) -> None:
    countries = sorted(df["country"].dropna().unique())
    default   = countries.index("Pakistan") if "Pakistan" in countries else 0
    sel       = st.selectbox("Select country", countries, index=default, key="t4_country")
    row       = df[df["country"] == sel].iloc[0]

    col_a, col_b = st.columns([2, 3])

    with col_a:
        cmpi = row["cmpi"]
        color = _cmpi_color(cmpi)
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:14px;
                    padding:1.2rem 1.5rem;margin-bottom:1rem">
          <div style="font-size:.8rem;color:#64748b;font-weight:600">CLIMATE MIGRATION PRESSURE</div>
          <div style="font-size:3rem;font-weight:800;color:{color};line-height:1.1">{cmpi:.0f}</div>
          <div style="font-size:.85rem;color:#475569">{sel}</div>
        </div>
        """, unsafe_allow_html=True)

        components = [
            ("Water stress",         row["water_score"],  "#3b82f6"),
            ("Food insecurity",      row["food_score"],   "#f59e0b"),
            ("Heat stress",          row["heat_score"],   "#ef4444"),
            ("Economic vulnerability", row["eco_score"],  "#8b5cf6"),
        ]
        for label, score, color_c in components:
            bar_pct = int(score)
            st.markdown(f"""
            <div class="driver-card">
              <div class="label">{label}</div>
              <div style="display:flex;align-items:center;gap:.6rem;margin-top:.3rem">
                <div style="flex:1;background:#e2e8f0;border-radius:4px;height:8px">
                  <div style="width:{bar_pct}%;background:{color_c};border-radius:4px;height:8px"></div>
                </div>
                <div class="score" style="color:{color_c}">{score:.0f}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        if row["displaced_new_k"] > 0:
            st.markdown(f"""
            <div class="driver-card" style="margin-top:.8rem">
              <div class="label">IDMC climate displacements 2022</div>
              <div class="score">{row['displaced_new_k']/1000:.2f}M people</div>
            </div>
            """, unsafe_allow_html=True)
        if row["displaced_stock_k"] > 0:
            st.markdown(f"""
            <div class="driver-card">
              <div class="label">Total displaced (stock) 2022</div>
              <div class="score">{row['displaced_stock_k']/1000:.2f}M people</div>
            </div>
            """, unsafe_allow_html=True)

    with col_b:
        # Radar chart
        categories = ["Water stress", "Food insecurity", "Heat stress",
                      "Economic vulnerability", "Water stress"]
        values     = [row["water_score"], row["food_score"], row["heat_score"],
                      row["eco_score"], row["water_score"]]

        rfig = go.Figure()
        rfig.add_trace(go.Scatterpolar(
            r=values, theta=categories, fill="toself",
            fillcolor="rgba(234,88,12,0.20)", line=dict(color="#ea580c", width=2),
            name=sel,
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[65, 65, 65, 65, 65], theta=categories,
            line=dict(color="#ef4444", width=1, dash="dot"),
            name="High-risk threshold (65)", mode="lines",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(range=[0, 100], tickfont=dict(size=9)),
                bgcolor="rgba(0,0,0,0)",
            ),
            height=380, paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.05),
            font=dict(family="Inter"),
            margin=dict(l=20, r=20, t=20, b=40),
        )
        st.plotly_chart(rfig, use_container_width=True)

        # 2050 projection delta
        st.markdown("##### Projected change to 2050 (SSP2)")
        delta_heat = row["heat_score"] * 1.18 - row["heat_score"]
        pop_2050_M = row["pop_2050"] / 1e6
        at_risk_M  = row["at_risk_2050_M"]

        d1, d2, d3 = st.columns(3)
        d1.metric("CMPI 2050", f"{row['cmpi_2050']:.0f}", f"+{row['cmpi_2050']-row['cmpi']:.0f}")
        d2.metric("Population 2050", f"{pop_2050_M:.0f}M",
                  f"×{row['growth_factor']:.2f} growth")
        d3.metric("People at risk", f"{at_risk_M:.1f}M",
                  help="Estimated climate displacement pressure 2050 under SSP2")

    # Regional comparison
    st.markdown("---")
    st.markdown("#### Regional CMPI comparison")
    region_sel = row["region"]
    reg_df = df[df["region"] == region_sel].sort_values("cmpi", ascending=False).head(15)
    reg_df["highlight"] = reg_df["country"] == sel

    colfig = px.bar(
        reg_df.sort_values("cmpi"), x="cmpi", y="country", orientation="h",
        color="highlight",
        color_discrete_map={True: "#ea580c", False: "#94a3b8"},
        labels={"cmpi": "CMPI score", "country": ""},
        text="cmpi",
    )
    colfig.update_traces(texttemplate="%{x:.0f}", textposition="outside")
    colfig.update_layout(
        height=max(300, len(reg_df) * 28),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 105], gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False), showlegend=False,
        margin=dict(l=0, r=60, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(colfig, use_container_width=True)

    st.markdown('<div class="method-note">Radar shows each CMPI driver 0–100. Red dashed ring = high-risk threshold (65). 2050 projection applies +18% heat stress and regional UN population growth (SSP2 scenario). Economic vulnerability = inverse log-normalised GDP/capita.</div>',
                unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 09 · THE RESILIENCE STACK</div>
      <h1>🧭 Climate Migration Pressure Index</h1>
      <p>Composite vulnerability by country · 32M displaced in 2022 · 1.2B at risk by 2050 · Driver breakdown</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Building Climate Migration Pressure Index…"):
        df = load_migration_data()

    if df.empty:
        st.error("Failed to load data from World Bank. Please try again.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌍  Pressure Map",
        "📊  Current Displacement",
        "🔮  2050 Hotspots",
        "🔗  Driver Breakdown",
    ])

    with tab1:
        tab_pressure_map(df)
    with tab2:
        tab_displacement(df)
    with tab3:
        tab_projections(df)
    with tab4:
        tab_drivers(df)

    st.markdown(
        "<div style='text-align:center;color:#94a3b8;font-size:.75rem;margin-top:2rem'>"
        "Day 09 · The Resilience Stack · "
        "World Bank ER.H2O.FWTL.ZS / SN.ITK.DEFC.ZS / NY.GDP.PCAP.CD · "
        "IDMC GRID 2023 · IOM WMR 2022 · IPCC AR6 WG2"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
