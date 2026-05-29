"""
The Resilience Stack — Day 07
Deforestation & Carbon Sink Tracker

Sources:
  World Bank  AG.LND.FRST.ZS / AG.LND.FRST.K2
  Pan et al. 2011 Science — global forest carbon stocks
  Gatti et al. 2021 Nature — Amazon carbon flux reversal
  FAO Global Forest Resources Assessment 2020
  Busch et al. 2019 Nature Climate Change — REDD+ costs
"""

import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Deforestation & Carbon Sink Tracker · Day 07",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_FOREST_PCT = "AG.LND.FRST.ZS"
IND_FOREST_KM2 = "AG.LND.FRST.K2"

FIRST_YEAR, LAST_YEAR = 1990, 2021
TC_TO_TCO2         = 3.667   # tonne C → tonne CO₂ (44/12)
HA_PER_KM2         = 100.0
PROTECTION_COST_HA = 12.0    # $/ha/yr — Busch et al. 2019 Nature Climate Change

# Carbon density tC/ha (above + below ground biomass)
# Source: Pan et al. 2011 Science doi:10.1126/science.1201609
CARBON_DENSITY: dict[str, float] = {
    # Tropical dense
    "BRA": 120, "COD": 175, "IDN": 145, "PER": 165, "COL": 155,
    "VEN": 130, "BOL": 115, "PNG": 170, "MYS": 140, "MMR": 110,
    "CMR": 145, "GAB": 175, "CAF": 150, "GUY": 170, "SUR": 165,
    "COG": 160, "GNQ": 155, "BLZ": 130,
    # Tropical seasonal / dry
    "TZA":  85, "MOZ":  65, "ZMB":  60, "AGO":  75, "MDG":  90,
    "ETH":  70, "GHA": 100, "CIV": 105, "NGA":  80,
    "MEX":  90, "IND":  60, "THA":  95, "VNM":  90, "KHM": 100,
    "LAO":  95, "PHL":  85, "BGD":  70,
    # Temperate
    "USA":  65, "FRA":  70, "DEU":  62, "POL":  58, "ESP":  52,
    "ITA":  60, "JPN":  85, "KOR":  70, "CHL":  88, "ARG":  72,
    "AUS":  42, "NZL":  78, "CHN":  52, "TUR":  52, "UKR":  55,
    "ROU":  65, "BGR":  63,
    # Boreal
    "CAN":  45, "RUS":  38, "SWE":  46, "FIN":  43, "NOR":  48,
}
DEFAULT_CARBON = 75.0   # tC/ha fallback

# Amazon carbon flux (Gatti et al. 2021 Nature doi:10.1038/s41586-021-03629-6)
AMAZON = {
    "eastern_source_pgc": 0.86,
    "western_sink_pgc":   0.54,
    "net_pgc":            0.32,
    "fire_pct":           59,
    "deforest_pct":       41,
}

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.rs-header {
    background: linear-gradient(135deg, #052e16 0%, #14532d 55%, #166534 100%);
    border-radius: 16px; padding: 2rem 2.5rem 1.8rem; color: #fff; margin-bottom: 1.5rem;
}
.rs-header h1 { font-size: 2rem; font-weight: 800; margin: 0 0 .25rem; letter-spacing: -.5px; }
.rs-header p  { font-size: .95rem; color: #bbf7d0; margin: 0; }
.rs-badge {
    display: inline-block; background: rgba(255,255,255,.12);
    border-radius: 20px; padding: 2px 12px; font-size: .75rem; font-weight: 600;
    color: #d1fae5; margin-bottom: .6rem; letter-spacing: .5px;
}

.stat-card { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 1rem 1.2rem; }
.stat-val  { font-size: 1.6rem; font-weight: 700; color: #14532d; line-height: 1; }
.stat-lbl  { font-size: .75rem; color: #4b5563; margin-top: .25rem; }
.stat-card.warn { background: #fff7ed; border-color: #fed7aa; }
.stat-card.warn .stat-val { color: #9a3412; }
.stat-card.crit { background: #fef2f2; border-color: #fecaca; }
.stat-card.crit .stat-val { color: #7f1d1d; }

.amazon-panel {
    background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
    border-radius: 12px; padding: 1.2rem 1.5rem; color: #fff; margin: 1rem 0;
}
.amazon-panel h4 { margin: 0 0 .5rem; font-size: 1rem; font-weight: 700; }
.amazon-panel p  { margin: 0; font-size: .85rem; color: #fecaca; line-height: 1.6; }

.method-note {
    background: #f8fafc; border-left: 3px solid #22c55e;
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
    """World Bank forest time-series filtered to sovereign countries, with carbon estimates."""
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


def _card(val: str, lbl: str, cls: str = "") -> str:
    return (f'<div class="stat-card {cls}">'
            f'<div class="stat-val">{val}</div>'
            f'<div class="stat-lbl">{lbl}</div></div>')


# ── Tab 1 — Forest Cover Map ──────────────────────────────────────────────────

def tab_forest_map(df: pd.DataFrame) -> None:
    years = sorted(df["year"].unique())
    year  = st.select_slider("Year", options=years, value=LAST_YEAR, key="t1_year")

    snap = df[df["year"] == year]
    base = df[df["year"] == FIRST_YEAR]

    # Compare only countries with data in both years
    common = set(snap["iso3"]) & set(base["iso3"])
    snap_c = snap[snap["iso3"].isin(common)]
    base_c = base[base["iso3"].isin(common)]

    total_km2_now = snap_c["forest_km2"].sum() / 1e6
    total_km2_90  = base_c["forest_km2"].sum() / 1e6
    lost_mha      = (total_km2_90 - total_km2_now) * 100   # million km² → Mha
    total_carbon  = snap_c["carbon_GtCO2"].sum()

    chg = snap_c.merge(base_c[["iso3", "forest_km2"]], on="iso3", suffixes=("", "_90"))
    n_losing = (chg["forest_km2"] < chg["forest_km2_90"]).sum()
    n_total  = len(chg)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(f"{total_km2_now:.1f}M km²", f"Global forest cover {year}"), unsafe_allow_html=True)
    c2.markdown(_card(f"{lost_mha:,.0f} Mha",
                      f"Net loss since 1990 (+{year - 1990} yr)",
                      "crit" if lost_mha > 100 else "warn"), unsafe_allow_html=True)
    c3.markdown(_card(f"{total_carbon:.0f} GtCO₂", "Carbon stored in forests"), unsafe_allow_html=True)
    c4.markdown(_card(f"{n_losing} / {n_total}",
                      "Countries losing forest",
                      "crit" if n_losing > n_total * 0.55 else "warn"), unsafe_allow_html=True)

    st.markdown("---")

    fig = px.choropleth(
        snap, locations="iso3",
        color="forest_pct",
        color_continuous_scale=["#fefce8", "#86efac", "#22c55e", "#15803d", "#052e16"],
        range_color=[0, 80],
        labels={"forest_pct": "Forest cover (%)"},
        hover_name="country",
        hover_data={"iso3": False, "forest_km2": ":,.0f", "forest_pct": ":.1f"},
        title=f"Forest cover by country — {year}",
    )
    fig.update_layout(
        height=480, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#cbd5e1",
                 bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e2e8f0",
                 showocean=True, oceancolor="#e0f2fe"),
        coloraxis_colorbar=dict(title="Forest %", thickness=12, len=0.55),
        margin=dict(l=0, r=0, t=40, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Country trend")
    countries = sorted(snap["country"].dropna().unique())
    default_idx = countries.index("Brazil") if "Brazil" in countries else 0
    sel = st.selectbox("Select country", countries, index=default_idx, key="t1_country")
    cdf = df[df["country"] == sel].sort_values("year")
    if not cdf.empty:
        cfig = go.Figure()
        cfig.add_trace(go.Scatter(
            x=cdf["year"], y=cdf["forest_km2"] / 1e3,
            mode="lines+markers", line=dict(color="#22c55e", width=2.5),
            marker=dict(size=5),
            hovertemplate="<b>%{x}</b><br>%{y:.1f}k km²<extra></extra>",
        ))
        cfig.update_layout(
            height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(title="Forest area (thousand km²)", gridcolor="#e2e8f0"),
            margin=dict(l=0, r=0, t=10, b=0), font=dict(family="Inter"), showlegend=False,
        )
        st.plotly_chart(cfig, use_container_width=True)

    st.markdown('<div class="method-note">Data: World Bank AG.LND.FRST.ZS / AG.LND.FRST.K2 · FAO Global Forest Resources Assessment · 1990–2021.</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Deforestation Pulse ───────────────────────────────────────────────

def tab_deforestation(df: pd.DataFrame) -> None:
    PERIODS = {
        "1990–2000": (1990, 2000),
        "2000–2010": (2000, 2010),
        "2010–2021": (2010, 2021),
        "2000–2021": (2000, 2021),
    }
    col_left, col_right = st.columns([2, 2])
    with col_left:
        period = st.selectbox("Time period", list(PERIODS.keys()), index=2, key="t2_period")
    with col_right:
        view = st.radio("Rank by", ["Absolute loss (km²)", "Relative rate (%)"],
                        horizontal=True, key="t2_view")

    y0, y1 = PERIODS[period]
    chg    = _net_change(df, y0, y1)
    losers = chg[chg["delta_km2"] < 0].copy()
    losers["abs_loss_km2"] = -losers["delta_km2"]
    losers["rate_pct"]     = -losers["delta_pct"]
    n_years                = y1 - y0

    total_lost_km2    = losers["abs_loss_km2"].sum()
    carbon_lost_GtCO2 = (losers["abs_loss_km2"] * HA_PER_KM2 * losers["cd"] * TC_TO_TCO2 / 1e9).sum()

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card(f"{total_lost_km2 / 1e6:.2f}M km²", f"Forest lost {period}", "crit"), unsafe_allow_html=True)
    c2.markdown(_card(f"{carbon_lost_GtCO2:.1f} GtCO₂", "Carbon released equivalent", "warn"), unsafe_allow_html=True)
    c3.markdown(_card(f"{total_lost_km2 / n_years / 1000:,.0f}k km²/yr", "Average annual rate", "warn"), unsafe_allow_html=True)

    st.markdown("---")

    if view.startswith("Absolute"):
        top = losers.nlargest(20, "abs_loss_km2").sort_values("abs_loss_km2")
        x_col, x_lbl, x_fmt = "abs_loss_km2", "Forest lost (km²)", ",.0f"
    else:
        top = losers.nlargest(20, "rate_pct").sort_values("rate_pct")
        x_col, x_lbl, x_fmt = "rate_pct", "Forest lost (% of base)", ".1f"

    fig = px.bar(
        top, x=x_col, y="country", orientation="h",
        color=x_col,
        color_continuous_scale=["#fca5a5", "#ef4444", "#7f1d1d"],
        labels={x_col: x_lbl, "country": ""},
        hover_data={"region": True, "abs_loss_km2": ":,.0f", "rate_pct": ":.2f"},
        text=x_col,
    )
    fig.update_traces(texttemplate=f"%{{x:{x_fmt}}}", textposition="outside")
    fig.update_layout(
        height=520, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=x_lbl, gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        coloraxis_showscale=False,
        margin=dict(l=0, r=80, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div class="amazon-panel">
      <h4>🔴 The Amazon Tipping Point</h4>
      <p>
        In 2021, researchers measured a threshold crossed: the eastern Amazon now <strong>emits</strong>
        more CO₂ than it absorbs — releasing +0.86 PgC/yr. The western Amazon is still a sink
        (−0.54 PgC/yr), but the net result is that the world's largest rainforest has flipped from
        carbon absorber to carbon source. 59% of the flux comes from fires, 41% from
        deforestation-driven forest degradation.<br><br>
        <em>Gatti et al. 2021, Nature — doi:10.1038/s41586-021-03629-6</em>
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Deforestation = change in World Bank forest area between period endpoints. Carbon released = area lost × carbon density (Pan et al. 2011 Science).</div>',
                unsafe_allow_html=True)


# ── Tab 3 — Carbon Sink Status ────────────────────────────────────────────────

def tab_carbon_status(df: pd.DataFrame) -> None:
    snap = df[df["year"] == LAST_YEAR].copy()
    base = df[df["year"] == FIRST_YEAR][["iso3", "forest_km2"]].rename(columns={"forest_km2": "km2_1990"})
    snap = snap.merge(base, on="iso3", how="left")
    snap["annual_loss_km2"] = ((snap["km2_1990"] - snap["forest_km2"]) / (LAST_YEAR - FIRST_YEAR)).clip(lower=0)
    snap["forest_Mha"]      = snap["forest_km2"] * HA_PER_KM2 / 1e6

    total_C         = snap["carbon_GtCO2"].sum()
    annual_rel      = (snap["annual_loss_km2"] * HA_PER_KM2 * snap["cd"] * TC_TO_TCO2 / 1e9).sum()
    at_risk_2050    = annual_rel * (2050 - LAST_YEAR)
    trees_per_sec   = snap["annual_loss_km2"].sum() * HA_PER_KM2 * 400 / (365.25 * 86400)

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card(f"{total_C:.0f} GtCO₂", "Carbon stored in all forests"), unsafe_allow_html=True)
    c2.markdown(_card(f"{at_risk_2050:.0f} GtCO₂", "At risk by 2050 (current trend)", "crit"), unsafe_allow_html=True)
    c3.markdown(_card(f"~{trees_per_sec:.0f} / sec", "Trees lost at 1990–2021 rate", "warn"), unsafe_allow_html=True)

    st.markdown("---")

    # Bubble scatter: forest size vs carbon density vs total carbon
    plot_df = snap[(snap["forest_Mha"] > 0.05) & (snap["carbon_GtCO2"] > 0.01)].copy()
    plot_df["trend"] = plot_df["annual_loss_km2"].apply(
        lambda x: "Gaining / stable" if x < 20 else ("Moderate loss" if x < 300 else "Rapid loss"))

    bfig = px.scatter(
        plot_df, x="forest_Mha", y="cd", size="carbon_GtCO2",
        color="trend",
        color_discrete_map={"Gaining / stable": "#22c55e", "Moderate loss": "#f59e0b", "Rapid loss": "#ef4444"},
        hover_name="country",
        hover_data={"iso3": False, "carbon_GtCO2": ":.2f", "forest_Mha": ":.1f", "cd": ":.0f"},
        labels={"forest_Mha": "Forest area (Mha)", "cd": "Carbon density (tC/ha)",
                "carbon_GtCO2": "Carbon (GtCO₂)"},
        size_max=65, title="Forest Carbon Stores — bubble size = total carbon stored",
    )
    bfig.update_layout(
        height=440, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(type="log", title="Forest area (Mha, log scale)", gridcolor="#e2e8f0"),
        yaxis=dict(title="Carbon density (tC/ha)", gridcolor="#e2e8f0"),
        legend=dict(orientation="h", y=1.06), font=dict(family="Inter"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(bfig, use_container_width=True)

    # Amazon flip split view
    st.markdown("#### The Amazon Carbon Flip")
    cola, colb = st.columns([2, 3])

    with cola:
        st.markdown(f"""
        <div class="amazon-panel">
          <h4>Was a sink. Now a source.</h4>
          <p>
            <strong>Eastern Amazon</strong><br>
            +{AMAZON['eastern_source_pgc']} PgC/yr (carbon source)<br><br>
            <strong>Western Amazon</strong><br>
            −{AMAZON['western_sink_pgc']} PgC/yr (still a sink)<br><br>
            <strong>Net Amazon flux</strong><br>
            +{AMAZON['net_pgc']} PgC/yr — net source<br><br>
            {AMAZON['fire_pct']}% from fires · {AMAZON['deforest_pct']}% from land degradation<br><br>
            <em>Gatti et al. 2021, Nature</em>
          </p>
        </div>
        """, unsafe_allow_html=True)

    with colb:
        afig = go.Figure(go.Bar(
            x=["Eastern Amazon\n(source)", "Western Amazon\n(sink)", "Net Amazon"],
            y=[AMAZON["eastern_source_pgc"], -AMAZON["western_sink_pgc"], AMAZON["net_pgc"]],
            marker_color=["#ef4444", "#22c55e", "#f59e0b"],
            text=[f"+{AMAZON['eastern_source_pgc']} PgC/yr",
                  f"−{AMAZON['western_sink_pgc']} PgC/yr",
                  f"+{AMAZON['net_pgc']} PgC/yr"],
            textposition="outside",
        ))
        afig.update_layout(
            height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Carbon flux (PgC/yr)", gridcolor="#e2e8f0",
                       zeroline=True, zerolinecolor="#94a3b8", zerolinewidth=2),
            xaxis=dict(showgrid=False),
            margin=dict(l=0, r=0, t=10, b=60), font=dict(family="Inter"),
            showlegend=False,
        )
        st.plotly_chart(afig, use_container_width=True)

    # Cumulative CO₂ at risk projection
    st.markdown("#### Carbon at Risk — Projection to 2050")
    proj_years = list(range(LAST_YEAR, 2051))
    cumulative = [(y - LAST_YEAR) * annual_rel for y in proj_years]

    pfig = go.Figure()
    pfig.add_trace(go.Scatter(
        x=proj_years, y=cumulative, mode="lines", fill="tozeroy",
        line=dict(color="#ef4444", width=2),
        fillcolor="rgba(239,68,68,0.12)",
        hovertemplate="<b>%{x}</b><br>%{y:.1f} GtCO₂ released<extra></extra>",
    ))
    pfig.add_vline(x=datetime.date.today().year, line_dash="dot", line_color="#64748b",
                   annotation_text="Today", annotation_position="top right")
    pfig.update_layout(
        height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(title="Cumulative CO₂ released (GtCO₂)", gridcolor="#e2e8f0"),
        margin=dict(l=0, r=0, t=10, b=0), font=dict(family="Inter"), showlegend=False,
    )
    st.plotly_chart(pfig, use_container_width=True)

    st.markdown('<div class="method-note">Carbon stored = forest area × carbon density (Pan et al. 2011 Science). At-risk projection assumes 1990–2021 average deforestation rate continues unchanged to 2050. Amazon flux data from Gatti et al. 2021 Nature.</div>',
                unsafe_allow_html=True)


# ── Tab 4 — REDD+ Economics ───────────────────────────────────────────────────

def tab_redd_economics(df: pd.DataFrame) -> None:
    carbon_price = st.slider(
        "Carbon price ($/tCO₂)", min_value=10, max_value=150, value=50, step=5, key="t4_price",
        help="Voluntary carbon market ~$10–30; Paris-aligned policy $50–150",
    )

    snap = df[df["year"] == LAST_YEAR].copy()
    base = df[df["year"] == 2000][["iso3", "forest_km2"]].rename(columns={"forest_km2": "km2_2000"})
    snap = snap.merge(base, on="iso3", how="left")
    snap["annual_loss_km2"]      = ((snap["km2_2000"] - snap["forest_km2"]) / (LAST_YEAR - 2000)).clip(lower=0)
    snap = snap[snap["annual_loss_km2"] > 10].copy()   # ≥10 km²/yr loss only

    snap["co2_saved_MtCO2_yr"]      = snap["annual_loss_km2"] * HA_PER_KM2 * snap["cd"] * TC_TO_TCO2 / 1e6
    snap["redd_revenue_MUSD_yr"]    = snap["co2_saved_MtCO2_yr"] * carbon_price
    snap["protection_cost_MUSD_yr"] = snap["annual_loss_km2"] * HA_PER_KM2 * PROTECTION_COST_HA / 1e6
    snap["net_benefit_MUSD_yr"]     = snap["redd_revenue_MUSD_yr"] - snap["protection_cost_MUSD_yr"]
    snap["break_even_usd"]          = (snap["protection_cost_MUSD_yr"] /
                                        snap["co2_saved_MtCO2_yr"].clip(lower=0.001))

    total_rev  = snap["redd_revenue_MUSD_yr"].sum() / 1000
    total_cost = snap["protection_cost_MUSD_yr"].sum() / 1000
    net_total  = snap["net_benefit_MUSD_yr"].sum() / 1000
    n_viable   = (snap["net_benefit_MUSD_yr"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(f"${carbon_price}/tCO₂", "Selected carbon price"), unsafe_allow_html=True)
    c2.markdown(_card(f"${total_rev:.1f}B/yr", "REDD+ revenue potential"), unsafe_allow_html=True)
    c3.markdown(_card(f"${total_cost:.1f}B/yr", f"Protection cost est."), unsafe_allow_html=True)
    net_cls = "" if net_total > 0 else "crit"
    c4.markdown(_card(f"${net_total:.1f}B/yr", f"Net benefit · {n_viable} countries profitable", net_cls),
                unsafe_allow_html=True)

    st.markdown("---")

    top20 = snap.nlargest(20, "co2_saved_MtCO2_yr").copy()

    bfig = go.Figure()
    bfig.add_trace(go.Bar(
        name="REDD+ revenue", x=top20["country"],
        y=top20["redd_revenue_MUSD_yr"], marker_color="#22c55e",
    ))
    bfig.add_trace(go.Bar(
        name="Protection cost", x=top20["country"],
        y=top20["protection_cost_MUSD_yr"], marker_color="#94a3b8",
    ))
    bfig.update_layout(
        barmode="group", height=380,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickangle=-35),
        yaxis=dict(title="USD million / year", gridcolor="#e2e8f0"),
        legend=dict(orientation="h", y=1.06), font=dict(family="Inter"),
        margin=dict(l=0, r=0, t=30, b=90),
    )
    st.plotly_chart(bfig, use_container_width=True)

    st.markdown("#### Country breakdown")
    tbl = top20[["country", "annual_loss_km2", "co2_saved_MtCO2_yr",
                  "redd_revenue_MUSD_yr", "protection_cost_MUSD_yr",
                  "net_benefit_MUSD_yr", "break_even_usd"]].rename(columns={
        "country":                "Country",
        "annual_loss_km2":        "Ann. loss (km²/yr)",
        "co2_saved_MtCO2_yr":    "CO₂ saved (MtCO₂/yr)",
        "redd_revenue_MUSD_yr":   f"Revenue at ${carbon_price} ($M/yr)",
        "protection_cost_MUSD_yr":"Protection cost ($M/yr)",
        "net_benefit_MUSD_yr":    "Net benefit ($M/yr)",
        "break_even_usd":         "Break-even ($/tCO₂)",
    }).round(1).set_index("Country")
    st.dataframe(tbl, use_container_width=True)

    st.markdown("#### Break-even carbon price by country")
    befig = px.scatter(
        snap.nlargest(30, "co2_saved_MtCO2_yr"),
        x="co2_saved_MtCO2_yr", y="break_even_usd",
        size="annual_loss_km2", color="region",
        hover_name="country",
        labels={"co2_saved_MtCO2_yr": "CO₂ saved if halted (MtCO₂/yr)",
                "break_even_usd": "Break-even price ($/tCO₂)"},
        size_max=40,
    )
    befig.add_hline(y=carbon_price, line_dash="dash", line_color="#ef4444",
                    annotation_text=f"Selected price ${carbon_price}/tCO₂",
                    annotation_position="top left")
    befig.update_layout(
        height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(type="log", title="CO₂ saved (MtCO₂/yr, log scale)", gridcolor="#e2e8f0"),
        yaxis=dict(title="Break-even price ($/tCO₂)", gridcolor="#e2e8f0"),
        font=dict(family="Inter"), margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(befig, use_container_width=True)

    st.markdown(
        f'<div class="method-note">REDD+ revenue = CO₂ saved × carbon price. '
        f'Protection cost = ${PROTECTION_COST_HA}/ha/yr (Busch et al. 2019 Nature Climate Change, mid-range). '
        f'Break-even = price at which REDD+ credits cover protection cost. '
        f'Deforestation rate from World Bank 2000–2021 trend.</div>',
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 07 · THE RESILIENCE STACK</div>
      <h1>🌳 Deforestation &amp; Carbon Sink Tracker</h1>
      <p>Global forest cover 1990–2021 · Carbon stored &amp; at risk · Amazon carbon flip · REDD+ economics</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading forest data from World Bank…"):
        df = load_forest_data()

    if df.empty:
        st.error("Failed to load forest data from World Bank. Please try again.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️  Forest Cover Map",
        "🔥  Deforestation Pulse",
        "🌡️  Carbon Sink Status",
        "💰  REDD+ Economics",
    ])

    with tab1:
        tab_forest_map(df)
    with tab2:
        tab_deforestation(df)
    with tab3:
        tab_carbon_status(df)
    with tab4:
        tab_redd_economics(df)

    st.markdown(
        "<div style='text-align:center;color:#94a3b8;font-size:.75rem;margin-top:2rem'>"
        "Day 07 · The Resilience Stack · "
        "World Bank AG.LND.FRST.ZS/K2 · Pan et al. 2011 Science · "
        "Gatti et al. 2021 Nature · FAO FRA 2020 · Busch et al. 2019 NCC"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
