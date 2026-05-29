"""
The Resilience Stack — Day 08
Air Quality & Health Cost Map

Sources:
  World Bank EN.ATM.PM25.MC.M3 — mean annual PM2.5 exposure by country (1990-2020)
  World Bank SH.STA.AIRP.P5    — air pollution mortality rate per 100k (2019)
  World Bank SP.POP.TOTL        — population
  WHO Global Ambient Air Quality Guidelines 2021
  IQAir 2022 World Air Quality Report — city-level reference PM2.5
  OECD / WHO — value of statistical life by income level
"""

import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Air Quality & Health Cost Map · Day 08",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_PM25     = "EN.ATM.PM25.MC.M3"   # mean PM2.5 µg/m³
IND_MORT     = "SH.STA.AIRP.P5"      # deaths per 100k from air pollution
IND_POP      = "SP.POP.TOTL"         # total population
IND_EXCEED   = "EN.ATM.PM25.MC.ZS"   # % population above WHO guideline

FIRST_YEAR, LAST_PM25_YEAR, LAST_MORT_YEAR = 1990, 2020, 2019

# WHO PM2.5 annual guideline values (µg/m³)
WHO_2021 = 5.0    # revised 2021 guideline
WHO_2005 = 10.0   # interim target 1 (2005 guideline, most country targets)

# Value of Statistical Life by WB income level (USD)
# Source: OECD 2012; WHO cost-effectiveness thresholds; adapted
VSL_USD = {
    "HIC":  8_000_000,
    "UMC":  3_000_000,
    "LMC":  1_000_000,
    "LIC":    500_000,
}
DEFAULT_VSL = 1_500_000

# AQI breakpoints (US EPA PM2.5 24h standard basis, used for annual mean reference)
AQI_BREAKS = [
    (0.0,   12.0,   0,  50, "Good",                     "#22c55e"),
    (12.1,  35.4,  51, 100, "Moderate",                 "#eab308"),
    (35.5,  55.4, 101, 150, "Unhealthy (Sensitive)",    "#f97316"),
    (55.5, 150.4, 151, 200, "Unhealthy",                "#ef4444"),
    (150.5,250.4, 201, 300, "Very Unhealthy",           "#8b5cf6"),
    (250.5,500.0, 301, 500, "Hazardous",                "#7f1d1d"),
]

# City-level annual mean PM2.5 (µg/m³) — IQAir 2022 World Air Quality Report
# lat, lon, pm25, country
CITY_AIR: dict[str, tuple] = {
    "Delhi, India":            (28.66, 77.23,  92.0, "India",          "South Asia"),
    "Lahore, Pakistan":        (31.55, 74.34,  85.0, "Pakistan",       "South Asia"),
    "Kolkata, India":          (22.57, 88.37,  55.0, "India",          "South Asia"),
    "Dhaka, Bangladesh":       (23.81, 90.41,  66.0, "Bangladesh",     "South Asia"),
    "Karachi, Pakistan":       (24.86, 67.01,  57.0, "Pakistan",       "South Asia"),
    "Mumbai, India":           (19.07, 72.87,  40.0, "India",          "South Asia"),
    "Beijing, China":          (39.91,116.39,  28.0, "China",          "East Asia"),
    "Shanghai, China":         (31.23,121.47,  26.0, "China",          "East Asia"),
    "Chengdu, China":          (30.66,104.07,  38.0, "China",          "East Asia"),
    "Jakarta, Indonesia":      (-6.21,106.85,  30.0, "Indonesia",      "SE Asia"),
    "Hanoi, Vietnam":          (21.03,105.83,  25.0, "Vietnam",        "SE Asia"),
    "Bangkok, Thailand":       (13.75,100.52,  22.0, "Thailand",       "SE Asia"),
    "Ho Chi Minh City, VN":    (10.82,106.63,  23.0, "Vietnam",        "SE Asia"),
    "Cairo, Egypt":            (30.06, 31.25,  48.0, "Egypt",          "Middle East/Africa"),
    "Lagos, Nigeria":          ( 6.45,  3.47,  51.0, "Nigeria",        "Middle East/Africa"),
    "Nairobi, Kenya":          (-1.29, 36.82,  18.0, "Kenya",          "Middle East/Africa"),
    "Istanbul, Turkey":        (41.01, 28.95,  16.0, "Turkey",         "Europe"),
    "Moscow, Russia":          (55.75, 37.62,  11.0, "Russia",         "Europe"),
    "Warsaw, Poland":          (52.23, 21.01,  18.0, "Poland",         "Europe"),
    "London, UK":              (51.51, -0.13,   8.0, "UK",             "Europe"),
    "Paris, France":           (48.85,  2.35,  10.0, "France",         "Europe"),
    "Berlin, Germany":         (52.52, 13.40,   8.0, "Germany",        "Europe"),
    "Madrid, Spain":           (40.42, -3.70,  10.0, "Spain",          "Europe"),
    "Zurich, Switzerland":     (47.38,  8.54,   6.0, "Switzerland",    "Europe"),
    "Tokyo, Japan":            (35.69,139.69,   8.0, "Japan",          "East Asia"),
    "Seoul, South Korea":      (37.57,126.98,  16.0, "South Korea",    "East Asia"),
    "Singapore":               ( 1.35,103.82,  12.0, "Singapore",      "SE Asia"),
    "Mexico City, Mexico":     (19.43,-99.13,  18.0, "Mexico",         "Latin America"),
    "São Paulo, Brazil":       (-23.55,-46.63, 11.0, "Brazil",         "Latin America"),
    "Bogotá, Colombia":        ( 4.71,-74.07,  14.0, "Colombia",       "Latin America"),
    "New York, USA":           (40.71,-74.01,   7.0, "USA",            "North America"),
    "Los Angeles, USA":        (34.05,-118.24, 14.0, "USA",            "North America"),
    "Toronto, Canada":         (43.65,-79.38,   6.0, "Canada",         "North America"),
    "Sydney, Australia":       (-33.87,151.21,  5.0, "Australia",      "Oceania"),
    "Cape Town, South Africa": (-33.93, 18.42, 13.0, "South Africa",   "Middle East/Africa"),
}


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.rs-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
    border-radius: 16px; padding: 2rem 2.5rem 1.8rem; color: #fff; margin-bottom: 1.5rem;
}
.rs-header h1 { font-size: 2rem; font-weight: 800; margin: 0 0 .25rem; letter-spacing: -.5px; }
.rs-header p  { font-size: .95rem; color: #cbd5e1; margin: 0; }
.rs-badge {
    display: inline-block; background: rgba(255,255,255,.12);
    border-radius: 20px; padding: 2px 12px; font-size: .75rem; font-weight: 600;
    color: #e2e8f0; margin-bottom: .6rem; letter-spacing: .5px;
}

.stat-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem 1.2rem; }
.stat-val  { font-size: 1.6rem; font-weight: 700; color: #0f172a; line-height: 1; }
.stat-lbl  { font-size: .75rem; color: #64748b; margin-top: .25rem; }
.stat-card.warn { background: #fff7ed; border-color: #fed7aa; }
.stat-card.warn .stat-val { color: #9a3412; }
.stat-card.crit { background: #fef2f2; border-color: #fecaca; }
.stat-card.crit .stat-val { color: #7f1d1d; }

.who-panel {
    background: linear-gradient(135deg, #312e81 0%, #4338ca 100%);
    border-radius: 12px; padding: 1.2rem 1.5rem; color: #fff; margin: 1rem 0;
}
.who-panel h4 { margin: 0 0 .5rem; font-size: 1rem; font-weight: 700; }
.who-panel p  { margin: 0; font-size: .85rem; color: #c7d2fe; line-height: 1.6; }

.aqi-pill {
    display: inline-block; border-radius: 20px; padding: 3px 14px;
    font-size: .8rem; font-weight: 600; color: #fff;
}

.method-note {
    background: #f8fafc; border-left: 3px solid #6366f1;
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
                inc = c.get("incomeLevel", {})
                if isinstance(reg, dict) and reg.get("id") not in ("", "NA", None):
                    rows.append({
                        "iso3":        c["id"],
                        "name":        c["name"],
                        "region":      reg.get("value", ""),
                        "income_id":   inc.get("id", "INX") if isinstance(inc, dict) else "INX",
                    })
            if page * meta.get("per_page", 500) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def _load_wb_series(indicator: str, start: int, end: int) -> pd.DataFrame:
    rows, page = [], 1
    while True:
        url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
               f"?format=json&date={start}:{end}&per_page=1000&page={page}")
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
def load_air_data() -> dict[str, pd.DataFrame]:
    meta = _load_country_meta()
    pm25 = _load_wb_series(IND_PM25,   FIRST_YEAR, LAST_PM25_YEAR)
    mort = _load_wb_series(IND_MORT,   LAST_MORT_YEAR, LAST_MORT_YEAR)
    pop  = _load_wb_series(IND_POP,    LAST_MORT_YEAR, LAST_MORT_YEAR)

    valid = set(meta["iso3"])
    pm25 = pm25[pm25["iso3"].isin(valid)].rename(columns={"value": "pm25"})
    mort = mort[mort["iso3"].isin(valid)].rename(columns={"value": "mort_per_100k"})
    pop  = pop[pop["iso3"].isin(valid)].rename(columns={"value": "population"})

    # Snapshot for latest year
    snap_pm25 = pm25[pm25["year"] == LAST_PM25_YEAR][["iso3", "country", "pm25"]]
    snap = snap_pm25.merge(mort[["iso3", "mort_per_100k"]], on="iso3", how="left")
    snap = snap.merge(pop[["iso3", "population"]], on="iso3", how="left")
    snap = snap.merge(meta[["iso3", "name", "region", "income_id"]], on="iso3", how="left")
    snap["vsl"]         = snap["income_id"].map(VSL_USD).fillna(DEFAULT_VSL)
    snap["deaths"]      = (snap["mort_per_100k"] * snap["population"] / 100_000).round(0)
    snap["econ_cost_B"] = (snap["deaths"] * snap["vsl"] / 1e9).round(2)
    snap["exceeds_who"] = snap["pm25"] > WHO_2021
    snap["pm25_ratio"]  = (snap["pm25"] / WHO_2021).round(1)

    return {"snap": snap, "pm25_ts": pm25}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pm25_to_aqi(pm25: float) -> int:
    for c_lo, c_hi, i_lo, i_hi, _, _ in AQI_BREAKS:
        if c_lo <= pm25 <= c_hi:
            return int((i_hi - i_lo) / (c_hi - c_lo) * (pm25 - c_lo) + i_lo)
    return 500


def _aqi_label(aqi: int) -> tuple[str, str]:
    for _, _, i_lo, i_hi, label, color in AQI_BREAKS:
        if i_lo <= aqi <= i_hi:
            return label, color
    return "Hazardous", "#7f1d1d"


def _card(val: str, lbl: str, cls: str = "") -> str:
    return (f'<div class="stat-card {cls}">'
            f'<div class="stat-val">{val}</div>'
            f'<div class="stat-lbl">{lbl}</div></div>')


# ── Tab 1 — PM2.5 Exposure Map ────────────────────────────────────────────────

def tab_pm25_map(snap: pd.DataFrame, pm25_ts: pd.DataFrame) -> None:
    years = sorted(pm25_ts["year"].unique())
    year  = st.select_slider("Year", options=years, value=LAST_PM25_YEAR, key="t1_year")

    snap_y = pm25_ts[pm25_ts["year"] == year].merge(
        snap[["iso3", "name", "region"]], on="iso3", how="left"
    )
    snap_y["exceeds_who"]  = snap_y["pm25"] > WHO_2021
    snap_y["exceeds_2005"] = snap_y["pm25"] > WHO_2005
    snap_y["pm25_ratio"]   = (snap_y["pm25"] / WHO_2021).round(1)

    n_exceed_2021 = snap_y["exceeds_who"].sum()
    n_exceed_2005 = snap_y["exceeds_2005"].sum()
    n_total       = len(snap_y)
    global_avg    = snap_y["pm25"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(f"{global_avg:.1f} µg/m³", f"Global mean PM2.5 ({year})"), unsafe_allow_html=True)
    c2.markdown(_card(f"{n_exceed_2021}/{n_total}",
                      f"Countries > WHO 2021 limit ({WHO_2021} µg/m³)", "crit"), unsafe_allow_html=True)
    c3.markdown(_card(f"{n_exceed_2005}/{n_total}",
                      f"Countries > WHO 2005 limit ({WHO_2005} µg/m³)", "warn"), unsafe_allow_html=True)
    c4.markdown(_card("99%", "World population breathing unsafe air (WHO 2021)", "crit"),
                unsafe_allow_html=True)

    st.markdown("---")

    fig = px.choropleth(
        snap_y, locations="iso3",
        color="pm25",
        color_continuous_scale=["#f0fdf4", "#fef9c3", "#fed7aa", "#fca5a5", "#ef4444", "#7f1d1d"],
        range_color=[0, 80],
        labels={"pm25": "PM2.5 (µg/m³)"},
        hover_name="country",
        hover_data={"iso3": False, "pm25": ":.1f", "pm25_ratio": ":.1f"},
        title=f"Mean annual PM2.5 exposure — {year}",
    )
    fig.update_layout(
        height=480, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#cbd5e1",
                 bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e2e8f0",
                 showocean=True, oceancolor="#e0f2fe"),
        coloraxis_colorbar=dict(title="PM2.5 µg/m³", thickness=12, len=0.55,
                                tickvals=[0, 5, 10, 25, 50, 80],
                                ticktext=["0", "5 WHO", "10", "25", "50", "80"]),
        margin=dict(l=0, r=0, t=40, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Country PM2.5 trend")
    countries = sorted(snap_y["country"].dropna().unique())
    default_idx = countries.index("India") if "India" in countries else 0
    sel = st.selectbox("Select country", countries, index=default_idx, key="t1_country")
    cdf = pm25_ts[pm25_ts["country"] == sel].sort_values("year")
    if not cdf.empty:
        cfig = go.Figure()
        cfig.add_trace(go.Scatter(
            x=cdf["year"], y=cdf["pm25"],
            mode="lines+markers", line=dict(color="#6366f1", width=2.5),
            marker=dict(size=5),
            hovertemplate="<b>%{x}</b><br>%{y:.1f} µg/m³<extra></extra>",
        ))
        cfig.add_hline(y=WHO_2021, line_dash="dot", line_color="#ef4444",
                       annotation_text=f"WHO 2021 guideline ({WHO_2021} µg/m³)",
                       annotation_position="top right", annotation_font_color="#ef4444")
        cfig.add_hline(y=WHO_2005, line_dash="dot", line_color="#f97316",
                       annotation_text=f"WHO 2005 target ({WHO_2005} µg/m³)",
                       annotation_position="bottom right", annotation_font_color="#f97316")
        cfig.update_layout(
            height=270, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(title="PM2.5 (µg/m³)", gridcolor="#e2e8f0"),
            margin=dict(l=0, r=0, t=10, b=0), font=dict(family="Inter"), showlegend=False,
        )
        st.plotly_chart(cfig, use_container_width=True)

    st.markdown('<div class="method-note">PM2.5 data: World Bank EN.ATM.PM25.MC.M3 · Satellite + ground-station fusion dataset (van Donkelaar et al.) · 1990–2020. WHO guidelines: 5 µg/m³ annual (2021 revision), 10 µg/m³ (2005 interim target).</div>',
                unsafe_allow_html=True)


# ── Tab 2 — Health Impact ─────────────────────────────────────────────────────

def tab_health_impact(snap: pd.DataFrame, pm25_ts: pd.DataFrame) -> None:
    view = st.radio("Rank countries by", ["Absolute deaths", "Deaths per 100k population"],
                    horizontal=True, key="t2_view")

    snap_h = snap.dropna(subset=["mort_per_100k"]).copy()
    snap_h["deaths_k"] = snap_h["deaths"] / 1000

    total_deaths = snap_h["deaths"].sum()

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card("7 million", "Global deaths/yr from air pollution (WHO)", "crit"),
                unsafe_allow_html=True)
    c2.markdown(_card(f"{total_deaths / 1e6:.1f}M",
                      f"Deaths modelled from WB data ({LAST_MORT_YEAR})", "crit"),
                unsafe_allow_html=True)
    c3.markdown(_card("800 / hr", "Lives lost to air pollution every hour", "warn"),
                unsafe_allow_html=True)

    st.markdown("---")

    if view.startswith("Absolute"):
        top = snap_h.nlargest(20, "deaths").sort_values("deaths")
        x_col, x_lbl = "deaths_k", "Deaths (thousands / yr)"
        fmt = ",.0f"
    else:
        top = snap_h.nlargest(20, "mort_per_100k").sort_values("mort_per_100k")
        x_col, x_lbl = "mort_per_100k", "Deaths per 100k population"
        fmt = ".0f"

    fig = px.bar(
        top, x=x_col, y="country", orientation="h",
        color=x_col,
        color_continuous_scale=["#fca5a5", "#ef4444", "#7f1d1d"],
        labels={x_col: x_lbl, "country": ""},
        hover_data={"region": True, "pm25": ":.1f", "mort_per_100k": ":.0f"},
        text=x_col,
    )
    fig.update_traces(texttemplate=f"%{{x:{fmt}}}", textposition="outside")
    fig.update_layout(
        height=540, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=x_lbl, gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        coloraxis_showscale=False,
        margin=dict(l=0, r=80, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # PM2.5 vs mortality scatter
    st.markdown("#### PM2.5 exposure vs mortality rate")
    sfig = px.scatter(
        snap_h[snap_h["deaths"] > 0],
        x="pm25", y="mort_per_100k",
        size="population", color="region",
        hover_name="country",
        labels={"pm25": "Mean PM2.5 (µg/m³)", "mort_per_100k": "Deaths per 100k from air pollution",
                "population": "Population"},
        size_max=45,
    )
    sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#ef4444",
                   annotation_text=f"WHO limit {WHO_2021}", annotation_position="top right")
    sfig.update_layout(
        height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#e2e8f0"), yaxis=dict(gridcolor="#e2e8f0"),
        font=dict(family="Inter"), margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(sfig, use_container_width=True)

    st.markdown("""
    <div class="who-panel">
      <h4>🫁 Why PM2.5 Kills</h4>
      <p>
        Particles ≤ 2.5 µm pass through the lungs directly into the bloodstream, causing
        cardiovascular disease, stroke, lung cancer, and chronic respiratory illness.
        4.2 million deaths/yr from outdoor air pollution · 3.8 million from household cooking smoke.
        In 2021 WHO revised its annual PM2.5 limit from 10 to 5 µg/m³ — making 99% of
        the world's population officially exposed to unsafe air.
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="method-note">Mortality rate: World Bank SH.STA.AIRP.P5 (2019). Absolute deaths = mortality rate × population. Global total from WHO Global Health Observatory 2019.</div>',
                unsafe_allow_html=True)


# ── Tab 3 — Economic Cost ─────────────────────────────────────────────────────

def tab_economic_cost(snap: pd.DataFrame) -> None:
    snap_e = snap.dropna(subset=["deaths", "econ_cost_B"]).copy()
    snap_e = snap_e[snap_e["deaths"] > 0]

    total_cost = snap_e["econ_cost_B"].sum()
    top_country = snap_e.loc[snap_e["econ_cost_B"].idxmax(), "country"]
    top_cost    = snap_e["econ_cost_B"].max()

    c1, c2, c3 = st.columns(3)
    c1.markdown(_card(f"${total_cost:.0f}B/yr", "Estimated global economic cost", "crit"),
                unsafe_allow_html=True)
    c2.markdown(_card(f"{top_country}", f"Highest cost country (${top_cost:.0f}B/yr)", "warn"),
                unsafe_allow_html=True)
    c3.markdown(_card("$5.1 trillion", "WHO welfare-loss estimate (global, 2016)", "warn"),
                unsafe_allow_html=True)

    st.markdown("---")

    # Top 20 economic cost
    top20 = snap_e.nlargest(20, "econ_cost_B").sort_values("econ_cost_B")
    bfig = px.bar(
        top20, x="econ_cost_B", y="country", orientation="h",
        color="econ_cost_B",
        color_continuous_scale=["#fde68a", "#f59e0b", "#b45309", "#78350f"],
        labels={"econ_cost_B": "Economic cost ($B/yr)", "country": ""},
        hover_data={"deaths": ":,.0f", "pm25": ":.1f", "income_id": True},
        text="econ_cost_B",
    )
    bfig.update_traces(texttemplate="%{x:.1f}B", textposition="outside")
    bfig.update_layout(
        height=540, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Economic cost ($B / yr)", gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False), coloraxis_showscale=False,
        margin=dict(l=0, r=80, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(bfig, use_container_width=True)

    # Cost vs PM2.5 scatter
    st.markdown("#### Cost per death vs PM2.5 exposure (VSL by income level)")
    snap_e["cost_per_death_k"] = snap_e["econ_cost_B"] * 1e9 / snap_e["deaths"] / 1000
    sfig = px.scatter(
        snap_e[snap_e["econ_cost_B"] > 0.1],
        x="pm25", y="econ_cost_B",
        size="deaths", color="region",
        hover_name="country",
        hover_data={"deaths": ":,.0f", "income_id": True, "pm25": ":.1f"},
        labels={"pm25": "Mean PM2.5 (µg/m³)", "econ_cost_B": "Economic cost ($B/yr)"},
        size_max=55,
        log_y=True,
    )
    sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#ef4444",
                   annotation_text="WHO limit 5 µg/m³")
    sfig.update_layout(
        height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#e2e8f0"),
        yaxis=dict(title="Economic cost ($B/yr, log scale)", gridcolor="#e2e8f0"),
        font=dict(family="Inter"), margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(sfig, use_container_width=True)

    st.markdown(
        f'<div class="method-note">Economic cost = deaths × VSL by income group: '
        f'HIC ${VSL_USD["HIC"]/1e6:.0f}M · UMC ${VSL_USD["UMC"]/1e6:.0f}M · '
        f'LMC ${VSL_USD["LMC"]/1e6:.0f}M · LIC ${VSL_USD["LIC"]/1e6:.1f}M per death. '
        f'VSL estimates: OECD 2012 meta-analysis. Deaths from World Bank 2019. '
        f'WHO welfare-loss $5.1T from WHO 2016 report on health costs of air pollution.</div>',
        unsafe_allow_html=True,
    )


# ── Tab 4 — City Air Quality ──────────────────────────────────────────────────

def tab_city_air() -> None:
    # Build city dataframe
    rows = []
    for city, (lat, lon, pm25, country, region) in CITY_AIR.items():
        aqi   = _pm25_to_aqi(pm25)
        label, color = _aqi_label(aqi)
        ratio = pm25 / WHO_2021
        rows.append({
            "city": city, "lat": lat, "lon": lon,
            "pm25": pm25, "country": country, "region": region,
            "aqi": aqi, "category": label, "color": color,
            "who_multiple": ratio,
        })
    cdf = pd.DataFrame(rows)

    # Stats
    n_safe   = (cdf["pm25"] <= WHO_2021).sum()
    n_danger = (cdf["pm25"] > 35.4).sum()
    worst    = cdf.loc[cdf["pm25"].idxmax(), "city"]
    best     = cdf.loc[cdf["pm25"].idxmin(), "city"]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(f"{n_safe}/{len(cdf)}", f"Cities meeting WHO guideline ≤{WHO_2021} µg/m³"), unsafe_allow_html=True)
    c2.markdown(_card(f"{n_danger}/{len(cdf)}", "Cities in Unhealthy+ zone (>35 µg/m³)", "crit"), unsafe_allow_html=True)
    c3.markdown(_card(worst.split(",")[0], "Most polluted city in dataset", "crit"), unsafe_allow_html=True)
    c4.markdown(_card(best.split(",")[0], "Cleanest city in dataset"), unsafe_allow_html=True)

    st.markdown("---")

    region_filter = st.multiselect(
        "Filter by region",
        sorted(cdf["region"].unique()),
        default=sorted(cdf["region"].unique()),
        key="t4_region",
    )
    fdf = cdf[cdf["region"].isin(region_filter)].sort_values("pm25", ascending=False)

    # Horizontal bar chart — sorted by PM2.5
    bar_fig = px.bar(
        fdf.sort_values("pm25"),
        x="pm25", y="city", orientation="h",
        color="pm25",
        color_continuous_scale=["#22c55e", "#eab308", "#f97316", "#ef4444", "#8b5cf6", "#7f1d1d"],
        range_color=[0, 100],
        labels={"pm25": "Annual mean PM2.5 (µg/m³)", "city": ""},
        hover_data={"country": True, "aqi": True, "category": True},
        text="pm25",
    )
    bar_fig.update_traces(texttemplate="%{x:.0f}", textposition="outside")
    bar_fig.add_vline(x=WHO_2021, line_dash="dot", line_color="#ef4444",
                      annotation_text=f"WHO {WHO_2021}", annotation_position="top right",
                      annotation_font_color="#ef4444", annotation_font_size=10)
    bar_fig.add_vline(x=WHO_2005, line_dash="dot", line_color="#f97316",
                      annotation_text=f"Old limit {WHO_2005}", annotation_position="bottom right",
                      annotation_font_color="#f97316", annotation_font_size=10)
    bar_fig.update_layout(
        height=max(420, len(fdf) * 22),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="PM2.5 (µg/m³)", gridcolor="#e2e8f0"),
        yaxis=dict(showgrid=False),
        coloraxis_showscale=False,
        margin=dict(l=0, r=60, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    # World bubble map
    st.markdown("#### Global city air quality map")
    map_fig = px.scatter_geo(
        fdf, lat="lat", lon="lon",
        size="pm25", color="pm25",
        color_continuous_scale=["#22c55e", "#eab308", "#f97316", "#ef4444", "#8b5cf6"],
        range_color=[0, 100],
        hover_name="city",
        hover_data={"lat": False, "lon": False, "pm25": ":.1f",
                    "aqi": True, "category": True, "country": True},
        labels={"pm25": "PM2.5 (µg/m³)"},
        size_max=40,
    )
    map_fig.update_layout(
        height=420, paper_bgcolor="rgba(0,0,0,0)",
        geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#cbd5e1",
                 bgcolor="rgba(248,250,252,1)", showcountries=True, countrycolor="#e2e8f0",
                 showocean=True, oceancolor="#e0f2fe", projection_type="natural earth"),
        coloraxis_colorbar=dict(title="PM2.5 µg/m³", thickness=12, len=0.55),
        margin=dict(l=0, r=0, t=10, b=0), font=dict(family="Inter"),
    )
    st.plotly_chart(map_fig, use_container_width=True)

    # AQI reference table
    st.markdown("#### AQI categories")
    aqi_rows = [{"Category": lbl, "PM2.5 range (µg/m³)": f"{c_lo:.1f} – {c_hi:.1f}",
                 "AQI range": f"{i_lo} – {i_hi}"}
                for c_lo, c_hi, i_lo, i_hi, lbl, _ in AQI_BREAKS]
    st.dataframe(pd.DataFrame(aqi_rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="method-note">City PM2.5: IQAir 2022 World Air Quality Report annual mean values. AQI computed from US EPA PM2.5 breakpoints. WHO guideline: 5 µg/m³ annual mean (2021 revision).</div>',
                unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 08 · THE RESILIENCE STACK</div>
      <h1>🌫️ Air Quality &amp; Health Cost Map</h1>
      <p>PM2.5 exposure 1990–2020 · 7 million deaths/yr · Economic cost by country · 35-city AQI</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading air quality data from World Bank…"):
        data = load_air_data()

    if data["snap"].empty:
        st.error("Failed to load data from World Bank. Please try again.")
        return

    snap    = data["snap"]
    pm25_ts = data["pm25_ts"]

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌫️  PM2.5 Exposure Map",
        "💀  Health Impact",
        "💰  Economic Cost",
        "🏙️  City Air Quality",
    ])

    with tab1:
        tab_pm25_map(snap, pm25_ts)
    with tab2:
        tab_health_impact(snap, pm25_ts)
    with tab3:
        tab_economic_cost(snap)
    with tab4:
        tab_city_air()

    st.markdown(
        "<div style='text-align:center;color:#94a3b8;font-size:.75rem;margin-top:2rem'>"
        "Day 08 · The Resilience Stack · "
        "World Bank EN.ATM.PM25.MC.M3 / SH.STA.AIRP.P5 · "
        "WHO Global AQ Guidelines 2021 · IQAir 2022 Report"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
