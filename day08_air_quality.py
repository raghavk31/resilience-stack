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

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Air Quality & Health Cost · Day 08",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_PM25   = "EN.ATM.PM25.MC.M3"
IND_MORT   = "SH.STA.AIRP.P5"
IND_POP    = "SP.POP.TOTL"

FIRST_YEAR, LAST_PM25_YEAR, LAST_MORT_YEAR = 1990, 2020, 2019

WHO_2021 = 5.0
WHO_2005 = 10.0

VSL_USD = {"HIC": 8_000_000, "UMC": 3_000_000, "LMC": 1_000_000, "LIC": 500_000}
DEFAULT_VSL = 1_500_000

AQI_BREAKS = [
    (0.0,   12.0,   0,  50, "Good",                  "#16a34a"),
    (12.1,  35.4,  51, 100, "Moderate",              "#ca8a04"),
    (35.5,  55.4, 101, 150, "Unhealthy (Sensitive)", "#ea580c"),
    (55.5, 150.4, 151, 200, "Unhealthy",             "#dc2626"),
    (150.5,250.4, 201, 300, "Very Unhealthy",        "#7c3aed"),
    (250.5,500.0, 301, 500, "Hazardous",             "#7f1d1d"),
]

CITY_AIR: dict[str, tuple] = {
    "Delhi, India":            (28.66, 77.23,  92.0, "India",          "South Asia"),
    "Lahore, Pakistan":        (31.55, 74.34,  85.0, "Pakistan",       "South Asia"),
    "Dhaka, Bangladesh":       (23.81, 90.41,  66.0, "Bangladesh",     "South Asia"),
    "Kolkata, India":          (22.57, 88.37,  55.0, "India",          "South Asia"),
    "Karachi, Pakistan":       (24.86, 67.01,  57.0, "Pakistan",       "South Asia"),
    "Cairo, Egypt":            (30.06, 31.25,  48.0, "Egypt",          "Africa & Middle East"),
    "Lagos, Nigeria":          ( 6.45,  3.47,  51.0, "Nigeria",        "Africa & Middle East"),
    "Mumbai, India":           (19.07, 72.87,  40.0, "India",          "South Asia"),
    "Chengdu, China":          (30.66,104.07,  38.0, "China",          "East Asia"),
    "Jakarta, Indonesia":      (-6.21,106.85,  30.0, "Indonesia",      "SE Asia"),
    "Beijing, China":          (39.91,116.39,  28.0, "China",          "East Asia"),
    "Hanoi, Vietnam":          (21.03,105.83,  25.0, "Vietnam",        "SE Asia"),
    "Ho Chi Minh City, VN":    (10.82,106.63,  23.0, "Vietnam",        "SE Asia"),
    "Bangkok, Thailand":       (13.75,100.52,  22.0, "Thailand",       "SE Asia"),
    "Mexico City, Mexico":     (19.43,-99.13,  18.0, "Mexico",         "Latin America"),
    "Seoul, South Korea":      (37.57,126.98,  16.0, "South Korea",    "East Asia"),
    "Warsaw, Poland":          (52.23, 21.01,  18.0, "Poland",         "Europe"),
    "Los Angeles, USA":        (34.05,-118.24, 14.0, "USA",            "North America"),
    "Bogotá, Colombia":        ( 4.71,-74.07,  14.0, "Colombia",       "Latin America"),
    "Cape Town, South Africa": (-33.93, 18.42, 13.0, "South Africa",   "Africa & Middle East"),
    "Singapore":               ( 1.35,103.82,  12.0, "Singapore",      "SE Asia"),
    "Shanghai, China":         (31.23,121.47,  26.0, "China",          "East Asia"),
    "Nairobi, Kenya":          (-1.29, 36.82,  18.0, "Kenya",          "Africa & Middle East"),
    "Istanbul, Turkey":        (41.01, 28.95,  16.0, "Turkey",         "Europe"),
    "Moscow, Russia":          (55.75, 37.62,  11.0, "Russia",         "Europe"),
    "São Paulo, Brazil":       (-23.55,-46.63, 11.0, "Brazil",         "Latin America"),
    "Madrid, Spain":           (40.42, -3.70,  10.0, "Spain",          "Europe"),
    "Paris, France":           (48.85,  2.35,  10.0, "France",         "Europe"),
    "Tokyo, Japan":            (35.69,139.69,   8.0, "Japan",          "East Asia"),
    "London, UK":              (51.51, -0.13,   8.0, "UK",             "Europe"),
    "Berlin, Germany":         (52.52, 13.40,   8.0, "Germany",        "Europe"),
    "New York, USA":           (40.71,-74.01,   7.0, "USA",            "North America"),
    "Zurich, Switzerland":     (47.38,  8.54,   6.0, "Switzerland",    "Europe"),
    "Toronto, Canada":         (43.65,-79.38,   6.0, "Canada",         "North America"),
    "Sydney, Australia":       (-33.87,151.21,  5.0, "Australia",      "Oceania"),
}


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── App ── */
.stApp { background: #f8fafc; }
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
section.main,
[data-testid="block-container"] { background: transparent !important; }

/* ── Text ── */
p, li { color: #475569; }
h1, h2, h3, h4 { color: #1e293b; font-family: 'Space Grotesk', sans-serif; }
.stMarkdown p { color: #475569; font-size: 13px; }
label, [data-testid="stWidgetLabel"] p { color: #64748b !important; font-size: 11px !important; letter-spacing: .03em; }

/* ── Header ── */
.rs-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
    border-radius: 12px;
    padding: 1.6rem 2rem 1.4rem;
    margin-bottom: 1.2rem;
}
.rs-header h1 {
    font-size: 1.7rem; font-weight: 900; margin: 0 0 .15rem;
    color: #fff; letter-spacing: -.5px;
    font-family: 'Space Grotesk', sans-serif;
}
.rs-header p  { font-size: .82rem; color: #c7d2fe; margin: 0; }
.rs-badge {
    font-size: 9px; font-weight: 700; letter-spacing: .14em;
    color: #a5b4fc; margin-bottom: .45rem; display: block;
    text-transform: uppercase;
}
.rs-stats {
    display: flex; gap: 2rem; flex-wrap: wrap;
    border-top: 1px solid rgba(255,255,255,0.12);
    padding-top: .9rem; margin-top: .7rem;
}
.rs-stat-label {
    font-size: 9px; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #a5b4fc; margin-bottom: .15rem;
}
.rs-stat-val {
    font-size: 1.35rem; font-weight: 900; color: #fff;
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: -.5px; line-height: 1;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 8px; padding: 3px; gap: 1px;
}
.stTabs [data-baseweb="tab"] {
    color: #94a3b8; border-radius: 6px;
    padding: 7px 18px; font-size: 12px; font-weight: 500;
    letter-spacing: .01em;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,0.10) !important;
    color: #4338ca !important; font-weight: 700;
}

/* ── Left-panel story cards ── */
.sc {
    border-radius: 0 8px 8px 0;
    padding: .8rem 1rem;
    margin-bottom: .55rem;
}
.sc-lbl {
    font-size: 8px; font-weight: 700; letter-spacing: .13em;
    text-transform: uppercase; color: #94a3b8; margin-bottom: .2rem;
}
.sc-num {
    font-size: 1.65rem; font-weight: 900; line-height: 1; letter-spacing: -1px;
    font-family: 'Space Grotesk', sans-serif;
}
.sc-line {
    font-size: .72rem; font-weight: 600; color: #334155;
    margin: .22rem 0 .25rem; line-height: 1.4;
}
.sc-body { font-size: .70rem; color: #64748b; line-height: 1.6; }

/* ── Right-panel section label ── */
.r-lbl {
    font-size: 9px; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; margin-bottom: .4rem;
}

/* ── Method note ── */
.method-note {
    background: rgba(0,0,0,0.02);
    border-left: 2px solid rgba(99,102,241,0.3);
    padding: .5rem .9rem; border-radius: 0 6px 6px 0;
    font-size: .72rem; color: #64748b; margin-top: 1rem; line-height: 1.6;
}

/* ── Misc ── */
hr { border-color: rgba(0,0,0,0.06) !important; }
section[data-testid="stSidebar"] { display: none; }
[data-baseweb="select"] > div {
    background: #fff !important; border-color: rgba(0,0,0,0.10) !important;
    color: #1e293b !important;
}
[data-baseweb="select"] span { color: #1e293b !important; }
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
                inc = c.get("incomeLevel", {})
                if isinstance(reg, dict) and reg.get("id") not in ("", "NA", None):
                    rows.append({
                        "iso3":      c["id"],
                        "name":      c["name"],
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
    pm25 = _load_wb_series(IND_PM25, FIRST_YEAR, LAST_PM25_YEAR)
    mort = _load_wb_series(IND_MORT, LAST_MORT_YEAR, LAST_MORT_YEAR)
    pop  = _load_wb_series(IND_POP,  LAST_MORT_YEAR, LAST_MORT_YEAR)

    valid    = set(meta["iso3"])
    pm25     = pm25[pm25["iso3"].isin(valid)].rename(columns={"value": "pm25"})
    mort     = mort[mort["iso3"].isin(valid)].rename(columns={"value": "mort_per_100k"})
    pop      = pop[pop["iso3"].isin(valid)].rename(columns={"value": "population"})

    snap_pm25 = pm25[pm25["year"] == LAST_PM25_YEAR][["iso3", "country", "pm25"]]
    snap = snap_pm25.merge(mort[["iso3", "mort_per_100k"]], on="iso3", how="left")
    snap = snap.merge(pop[["iso3", "population"]],          on="iso3", how="left")
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


def _sc(num: str, lbl: str, line: str, body: str,
        color: str, bg: str = "#f8fafc") -> str:
    """Compact story card for the left panel."""
    return f"""
    <div class="sc" style="border-left:3px solid {color};background:{bg}">
      <div class="sc-lbl">{lbl}</div>
      <div class="sc-num" style="color:{color}">{num}</div>
      <div class="sc-line">{line}</div>
      <div class="sc-body">{body}</div>
    </div>"""


def _r_lbl(text: str, color: str = "#6366f1") -> str:
    return f'<div class="r-lbl" style="color:{color}">{text}</div>'


def _chart_layout(h: int = 460, **kw) -> dict:
    base = dict(
        height=h,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#475569"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    base.update(kw)
    return base


# ── Tab 1 — PM2.5 Exposure Map ────────────────────────────────────────────────

def tab_pm25_map(snap: pd.DataFrame, pm25_ts: pd.DataFrame) -> None:
    left, right = st.columns([1, 2.3], gap="medium")

    years = sorted(pm25_ts["year"].unique())

    with left:
        year = st.select_slider("Year", options=years,
                                value=LAST_PM25_YEAR, key="t1_year")

        snap_y = pm25_ts[pm25_ts["year"] == year].merge(
            snap[["iso3", "name", "region"]], on="iso3", how="left"
        )
        snap_y["exceeds_who"]  = snap_y["pm25"] > WHO_2021
        snap_y["exceeds_2005"] = snap_y["pm25"] > WHO_2005
        snap_y["pm25_ratio"]   = (snap_y["pm25"] / WHO_2021).round(1)

        n_exceed = snap_y["exceeds_who"].sum()
        n_total  = len(snap_y)
        g_avg    = snap_y["pm25"].mean()

        st.markdown(
            _sc("99%", "Unsafe air",
                "of humanity breathes air exceeding the WHO 2021 limit",
                "In 2021 the WHO revised its annual PM2.5 guideline from 10 to 5 µg/m³ — "
                "tighter than any country's legal standard. Virtually the entire world "
                "is now officially non-compliant.",
                "#6366f1", "#f5f3ff") +
            _sc(f"{g_avg:.1f} µg/m³", f"Global mean — {year}",
                f"{n_exceed} of {n_total} countries exceed the 5 µg/m³ limit",
                "The global average has declined slightly since 2010 but remains "
                f"{g_avg/WHO_2021:.1f}× above the WHO threshold. Progress is real but far too slow.",
                "#6366f1", "#f5f3ff") +
            _sc("Indo-Gangetic Plain", "Most exposed region",
                "Bangladesh, India, Pakistan, Nepal — chronically above 50 µg/m³",
                "Crop burning, cookstoves, traffic, and coal power combine to make "
                "South Asia the world's most PM2.5-exposed region. Delhi regularly peaks "
                "above 300 µg/m³ in winter.",
                "#6366f1", "#f5f3ff"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        countries   = sorted(snap_y["country"].dropna().unique())
        default_idx = countries.index("India") if "India" in countries else 0
        sel = st.selectbox("Country trend", countries,
                           index=default_idx, key="t1_country")
        cdf = pm25_ts[pm25_ts["country"] == sel].sort_values("year")
        if not cdf.empty:
            cfig = go.Figure()
            cfig.add_trace(go.Scatter(
                x=cdf["year"], y=cdf["pm25"],
                mode="lines+markers",
                line=dict(color="#6366f1", width=2.5),
                marker=dict(size=5, color="#6366f1"),
                hovertemplate="<b>%{x}</b><br>%{y:.1f} µg/m³<extra></extra>",
            ))
            cfig.add_hline(y=WHO_2021, line_dash="dot", line_color="#dc2626",
                           annotation_text=f"WHO 2021 ({WHO_2021})",
                           annotation_position="top right",
                           annotation_font=dict(color="#dc2626", size=9))
            cfig.add_hline(y=WHO_2005, line_dash="dot", line_color="#ea580c",
                           annotation_text=f"WHO 2005 ({WHO_2005})",
                           annotation_position="bottom right",
                           annotation_font=dict(color="#ea580c", size=9))
            cfig.update_layout(**_chart_layout(
                h=200,
                xaxis=dict(showgrid=False, color="#94a3b8"),
                yaxis=dict(title="PM2.5 µg/m³", gridcolor="#e2e8f0", color="#94a3b8"),
            ))
            st.plotly_chart(cfig, use_container_width=True)

        st.markdown('<div class="method-note">PM2.5: World Bank EN.ATM.PM25.MC.M3 · van Donkelaar et al. satellite-ground fusion · 1990–2020.</div>',
                    unsafe_allow_html=True)

    with right:
        st.markdown(_r_lbl(f"MEAN ANNUAL PM2.5 EXPOSURE — {year}"), unsafe_allow_html=True)

        fig = px.choropleth(
            snap_y, locations="iso3",
            color="pm25",
            color_continuous_scale=[
                "#f0fdf4", "#fef9c3", "#fde68a",
                "#fca5a5", "#ef4444", "#7f1d1d",
            ],
            range_color=[0, 80],
            labels={"pm25": "PM2.5 (µg/m³)"},
            hover_name="country",
            hover_data={"iso3": False, "pm25": ":.1f", "pm25_ratio": ":.1f"},
        )
        fig.update_layout(
            **_chart_layout(h=440),
            geo=dict(
                showframe=False, showcoastlines=True,
                coastlinecolor="#cbd5e1", bgcolor="rgba(0,0,0,0)",
                showcountries=True, countrycolor="#e2e8f0",
                showocean=True, oceancolor="#e0f2fe",
            ),
            coloraxis_colorbar=dict(
                title="µg/m³", thickness=10, len=0.5,
                tickvals=[0, 5, 10, 25, 50, 80],
                ticktext=["0", "5 WHO", "10", "25", "50", "80+"],
                tickfont=dict(size=9),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        # WHO guideline callout
        st.markdown(f"""
        <div style="background:#faf5ff;border:1px solid rgba(99,102,241,0.15);
             border-left:4px solid #6366f1;border-radius:0 8px 8px 0;
             padding:.9rem 1.1rem;margin-top:.2rem">
          <div style="font-size:9px;font-weight:700;letter-spacing:.12em;
                      text-transform:uppercase;color:#6366f1;margin-bottom:.4rem">
            WHO 2021 GUIDELINE — 5 µg/m³ annual mean
          </div>
          <div style="font-size:.78rem;color:#475569;line-height:1.7">
            The revised limit is <b style="color:#1e293b">half the previous 2005 target</b>.
            It is now stricter than the legal air quality standard of every country on Earth.
            Meeting it would prevent an estimated <b style="color:#6366f1">3.3 million premature deaths</b>
            per year in the 15 most polluted countries alone.
          </div>
        </div>
        """, unsafe_allow_html=True)


# ── Tab 2 — Health Impact ─────────────────────────────────────────────────────

def tab_health_impact(snap: pd.DataFrame) -> None:
    snap_h = snap.dropna(subset=["mort_per_100k"]).copy()
    snap_h["deaths_k"] = snap_h["deaths"] / 1000
    total_deaths = snap_h["deaths"].sum()

    left, right = st.columns([1, 2.3], gap="medium")

    with left:
        st.markdown(
            _sc("7 million", "Deaths per year",
                "killed by air pollution annually — more than any single disease",
                "That's one person every 4.5 seconds, every day, without pause. "
                "More than HIV, malaria, and tuberculosis combined. "
                "91% of deaths occur in low- and middle-income countries.",
                "#dc2626", "#fff1f2") +
            _sc(f"{total_deaths/1e6:.1f}M", f"Modelled deaths — {LAST_MORT_YEAR}",
                "from World Bank mortality rates × country population",
                "This covers countries with available data. The WHO Global Health "
                "Observatory estimates the true toll at 6.7–7.0M. "
                "Data gaps mean the poorest nations are most under-counted.",
                "#dc2626", "#fff1f2") +
            _sc("3–5×", "South Asia vs Europe mortality gap",
                "higher air-pollution death rate in South Asia at similar income levels",
                "Crop residue burning in October–November raises India's PM2.5 to "
                "300+ µg/m³ in northern states. Combined with high population density "
                "and limited healthcare access, this drives outsized mortality.",
                "#dc2626", "#fff1f2"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        view = st.radio("Rank countries by",
                        ["Absolute deaths", "Deaths per 100k population"],
                        horizontal=False, key="t2_view")

        st.markdown('<div class="method-note">Mortality rate: World Bank SH.STA.AIRP.P5 (2019). Absolute deaths = rate × population. Global total: WHO GHO 2019.</div>',
                    unsafe_allow_html=True)

    with right:
        if view.startswith("Absolute"):
            top   = snap_h.nlargest(20, "deaths").sort_values("deaths")
            x_col = "deaths_k"
            x_lbl = "Deaths (thousands / yr)"
            fmt   = ",.0f"
            label = "TOP 20 COUNTRIES — ABSOLUTE DEATHS FROM AIR POLLUTION"
        else:
            top   = snap_h.nlargest(20, "mort_per_100k").sort_values("mort_per_100k")
            x_col = "mort_per_100k"
            x_lbl = "Deaths per 100k population"
            fmt   = ".0f"
            label = "TOP 20 COUNTRIES — DEATHS PER 100K FROM AIR POLLUTION"

        st.markdown(_r_lbl(label, "#dc2626"), unsafe_allow_html=True)

        fig = px.bar(
            top, x=x_col, y="country", orientation="h",
            color=x_col,
            color_continuous_scale=["#fca5a5", "#ef4444", "#991b1b"],
            labels={x_col: x_lbl, "country": ""},
            hover_data={"region": True, "pm25": ":.1f", "mort_per_100k": ":.0f"},
            text=x_col,
        )
        fig.update_traces(
            texttemplate=f"%{{x:{fmt}}}",
            textposition="outside",
            textfont=dict(size=9, color="#64748b"),
        )
        fig.update_layout(
            **_chart_layout(h=520, margin=dict(l=0, r=80, t=10, b=0)),
            xaxis=dict(title=x_lbl, gridcolor="#e2e8f0", color="#94a3b8"),
            yaxis=dict(showgrid=False, color="#334155"),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # PM2.5 vs mortality scatter
        st.markdown(_r_lbl("PM2.5 EXPOSURE vs MORTALITY RATE", "#dc2626"),
                    unsafe_allow_html=True)
        sfig = px.scatter(
            snap_h[snap_h["deaths"] > 0],
            x="pm25", y="mort_per_100k",
            size="population", color="region",
            hover_name="country",
            labels={"pm25": "Mean PM2.5 (µg/m³)",
                    "mort_per_100k": "Deaths per 100k",
                    "population": "Population"},
            size_max=40,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#dc2626",
                       annotation_text=f"WHO limit {WHO_2021}",
                       annotation_position="top right",
                       annotation_font=dict(color="#dc2626", size=9))
        sfig.update_layout(
            **_chart_layout(h=320),
            xaxis=dict(gridcolor="#e2e8f0", color="#94a3b8"),
            yaxis=dict(gridcolor="#e2e8f0", color="#94a3b8"),
            legend=dict(font=dict(size=9)),
        )
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 3 — Economic Cost ─────────────────────────────────────────────────────

def tab_economic_cost(snap: pd.DataFrame) -> None:
    snap_e = snap.dropna(subset=["deaths", "econ_cost_B"]).copy()
    snap_e = snap_e[snap_e["deaths"] > 0]

    total_cost  = snap_e["econ_cost_B"].sum()
    top_country = snap_e.loc[snap_e["econ_cost_B"].idxmax(), "country"]
    top_cost    = snap_e["econ_cost_B"].max()

    left, right = st.columns([1, 2.3], gap="medium")

    with left:
        st.markdown(
            _sc("$5.1 trillion", "Annual welfare loss",
                "WHO estimate of total economic damage from air pollution (2016)",
                "Larger than the GDP of Japan. This includes value of life lost, "
                "healthcare costs, and lost productivity. It equals roughly 6% of "
                "global GDP — a recurring annual drain on human potential.",
                "#d97706", "#fffbeb") +
            _sc(f"${total_cost:.0f}B", "Modelled cost — World Bank data",
                "deaths × OECD Value of Statistical Life, by income group",
                f"{top_country} leads at ${top_cost:.0f}B/yr. Note: VSL is "
                "systematically lower in poorer countries — meaning the human "
                "cost of air pollution in South Asia is structurally undervalued "
                "by this methodology.",
                "#d97706", "#fffbeb") +
            _sc("30–50× return", "Clean air investment ratio",
                "every $1 invested in reducing air pollution prevents $30–50 in health costs",
                "WHO and World Bank analyses consistently show air quality "
                "interventions — vehicle emission standards, cookstove transitions, "
                "coal plant retirement — rank among the highest-return public "
                "health investments available.",
                "#d97706", "#fffbeb"),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="method-note">Cost = deaths × VSL by income: HIC $8M · UMC $3M · LMC $1M · LIC $0.5M. OECD 2012 meta-analysis. WHO welfare-loss $5.1T: WHO 2016 health cost report.</div>',
                    unsafe_allow_html=True)

    with right:
        st.markdown(_r_lbl("TOP 20 COUNTRIES — ECONOMIC COST OF AIR POLLUTION", "#d97706"),
                    unsafe_allow_html=True)

        top20 = snap_e.nlargest(20, "econ_cost_B").sort_values("econ_cost_B")
        bfig  = px.bar(
            top20, x="econ_cost_B", y="country", orientation="h",
            color="econ_cost_B",
            color_continuous_scale=["#fde68a", "#f59e0b", "#b45309", "#78350f"],
            labels={"econ_cost_B": "Economic cost ($B/yr)", "country": ""},
            hover_data={"deaths": ":,.0f", "pm25": ":.1f", "income_id": True},
            text="econ_cost_B",
        )
        bfig.update_traces(
            texttemplate="%{x:.1f}B",
            textposition="outside",
            textfont=dict(size=9, color="#64748b"),
        )
        bfig.update_layout(
            **_chart_layout(h=520, margin=dict(l=0, r=80, t=10, b=0)),
            xaxis=dict(title="Economic cost ($B / yr)", gridcolor="#e2e8f0", color="#94a3b8"),
            yaxis=dict(showgrid=False, color="#334155"),
            coloraxis_showscale=False,
        )
        st.plotly_chart(bfig, use_container_width=True)

        # Cost vs PM2.5 scatter
        st.markdown(_r_lbl("COST vs PM2.5 EXPOSURE (bubble = absolute deaths)", "#d97706"),
                    unsafe_allow_html=True)
        sfig = px.scatter(
            snap_e[snap_e["econ_cost_B"] > 0.1],
            x="pm25", y="econ_cost_B",
            size="deaths", color="region",
            hover_name="country",
            hover_data={"deaths": ":,.0f", "income_id": True, "pm25": ":.1f"},
            labels={"pm25": "Mean PM2.5 (µg/m³)", "econ_cost_B": "Economic cost ($B/yr)"},
            size_max=50, log_y=True,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#d97706",
                       annotation_text="WHO 5 µg/m³",
                       annotation_font=dict(color="#d97706", size=9))
        sfig.update_layout(
            **_chart_layout(h=320),
            xaxis=dict(gridcolor="#e2e8f0", color="#94a3b8"),
            yaxis=dict(title="Economic cost ($B/yr, log)", gridcolor="#e2e8f0", color="#94a3b8"),
            legend=dict(font=dict(size=9)),
        )
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 4 — City Air Quality ──────────────────────────────────────────────────

def tab_city_air() -> None:
    rows = []
    for city, (lat, lon, pm25, country, region) in CITY_AIR.items():
        aqi         = _pm25_to_aqi(pm25)
        label, color = _aqi_label(aqi)
        rows.append({
            "city": city, "lat": lat, "lon": lon,
            "pm25": pm25, "country": country, "region": region,
            "aqi": aqi, "category": label, "color": color,
            "who_multiple": round(pm25 / WHO_2021, 1),
        })
    cdf = pd.DataFrame(rows)

    n_safe   = (cdf["pm25"] <= WHO_2021).sum()
    n_2005   = (cdf["pm25"] <= WHO_2005).sum()
    n_danger = (cdf["pm25"] > 35.4).sum()
    worst    = cdf.loc[cdf["pm25"].idxmax(), "city"]
    best     = cdf.loc[cdf["pm25"].idxmin(), "city"]
    best_pm  = cdf["pm25"].min()

    left, right = st.columns([1, 2.3], gap="medium")

    with left:
        st.markdown(
            _sc("Delhi: 92 µg/m³", "Most polluted city",
                f"18× the WHO safe limit — equivalent to smoking 8 cigarettes a day",
                "20 million people breathe this air. In winter, Delhi's PM2.5 exceeds "
                "300 µg/m³ for weeks. Crop burning in Punjab and Haryana, combined with "
                "stagnant air, creates a toxic inversion layer over the entire city.",
                "#0891b2", "#ecfeff") +
            _sc(f"{n_safe} of {len(cdf)}", "Cities meeting WHO 2021 standard",
                f"Only {n_safe} cities at or below 5 µg/m³ · {n_2005} meet the older 10 µg/m³ target",
                "Even London (8 µg/m³) and Paris (10 µg/m³) fail the 2021 standard. "
                "The revised WHO limit exposes how far even wealthy, well-regulated cities "
                "are from truly clean air.",
                "#0891b2", "#ecfeff") +
            _sc(f"{best.split(',')[0]}: {best_pm:.0f} µg/m³", "Cleanest city",
                "at the WHO threshold — proof that large cities can achieve clean air",
                "Sydney's result reflects Australia's vehicle emission standards, "
                "clean electricity grid, and coastal geography. It shows the destination "
                "is reachable — the question is political will and timeline.",
                "#0891b2", "#ecfeff"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        region_filter = st.multiselect(
            "Filter by region",
            sorted(cdf["region"].unique()),
            default=sorted(cdf["region"].unique()),
            key="t4_region",
        )

        st.markdown('<div class="method-note">City PM2.5: IQAir 2022 World Air Quality Report. AQI: US EPA breakpoints. WHO guideline: 5 µg/m³ annual mean (2021).</div>',
                    unsafe_allow_html=True)

    with right:
        fdf = cdf[cdf["region"].isin(region_filter)].sort_values("pm25", ascending=False)

        st.markdown(_r_lbl("ANNUAL MEAN PM2.5 BY CITY — vs WHO GUIDELINES", "#0891b2"),
                    unsafe_allow_html=True)

        bar_fig = px.bar(
            fdf.sort_values("pm25"),
            x="pm25", y="city", orientation="h",
            color="pm25",
            color_continuous_scale=[
                "#16a34a", "#ca8a04", "#ea580c", "#dc2626", "#7c3aed", "#7f1d1d"
            ],
            range_color=[0, 100],
            labels={"pm25": "Annual mean PM2.5 (µg/m³)", "city": ""},
            hover_data={"country": True, "aqi": True, "category": True, "who_multiple": True},
            text="pm25",
        )
        bar_fig.update_traces(
            texttemplate="%{x:.0f}",
            textposition="outside",
            textfont=dict(size=9, color="#64748b"),
        )
        bar_fig.add_vline(
            x=WHO_2021, line_dash="dot", line_color="#dc2626",
            annotation_text=f"WHO 2021 · {WHO_2021} µg/m³",
            annotation_position="top right",
            annotation_font=dict(color="#dc2626", size=9),
        )
        bar_fig.add_vline(
            x=WHO_2005, line_dash="dot", line_color="#ea580c",
            annotation_text=f"WHO 2005 · {WHO_2005} µg/m³",
            annotation_position="bottom right",
            annotation_font=dict(color="#ea580c", size=9),
        )
        bar_fig.update_layout(
            **_chart_layout(h=max(440, len(fdf) * 22),
                            margin=dict(l=0, r=60, t=10, b=0)),
            xaxis=dict(title="PM2.5 (µg/m³)", gridcolor="#e2e8f0", color="#94a3b8"),
            yaxis=dict(showgrid=False, color="#334155"),
            coloraxis_showscale=False,
        )
        st.plotly_chart(bar_fig, use_container_width=True)

        # Bubble map
        st.markdown(_r_lbl("GLOBAL CITY AIR QUALITY MAP", "#0891b2"),
                    unsafe_allow_html=True)
        map_fig = px.scatter_geo(
            fdf, lat="lat", lon="lon",
            size="pm25", color="pm25",
            color_continuous_scale=[
                "#16a34a", "#ca8a04", "#ea580c", "#dc2626", "#7c3aed"
            ],
            range_color=[0, 100],
            hover_name="city",
            hover_data={"lat": False, "lon": False, "pm25": ":.1f",
                        "aqi": True, "category": True, "country": True},
            labels={"pm25": "PM2.5 (µg/m³)"},
            size_max=35,
        )
        map_fig.update_layout(
            **_chart_layout(h=380),
            geo=dict(
                showframe=False, showcoastlines=True,
                coastlinecolor="#cbd5e1",
                bgcolor="rgba(248,250,252,1)",
                showcountries=True, countrycolor="#e2e8f0",
                showocean=True, oceancolor="#e0f2fe",
                projection_type="natural earth",
            ),
            coloraxis_colorbar=dict(
                title="µg/m³", thickness=10, len=0.5, tickfont=dict(size=9)
            ),
        )
        st.plotly_chart(map_fig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="rs-header">
      <div class="rs-badge">DAY 08 · THE RESILIENCE STACK</div>
      <h1>🌫️ Air Quality &amp; Health Cost</h1>
      <p>PM2.5 exposure 1990–2020 · Where people die · What it costs · 35-city benchmark</p>
      <div class="rs-stats">
        <div>
          <div class="rs-stat-label">Annual deaths</div>
          <div class="rs-stat-val">7 million</div>
        </div>
        <div>
          <div class="rs-stat-label">Breathing unsafe air</div>
          <div class="rs-stat-val">99% of humanity</div>
        </div>
        <div>
          <div class="rs-stat-label">Economic welfare loss</div>
          <div class="rs-stat-val">$5.1 trillion / yr</div>
        </div>
        <div>
          <div class="rs-stat-label">Worst city</div>
          <div class="rs-stat-val" style="color:#fca5a5">Delhi — 18× limit</div>
        </div>
      </div>
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
        "🌍  PM2.5 Exposure",
        "💀  Health Impact",
        "💰  Economic Cost",
        "🏙️  City Air Quality",
    ])

    with tab1:
        tab_pm25_map(snap, pm25_ts)
    with tab2:
        tab_health_impact(snap)
    with tab3:
        tab_economic_cost(snap)
    with tab4:
        tab_city_air()

    st.markdown(
        "<div style='text-align:center;color:#94a3b8;font-size:10px;"
        "margin-top:2rem;padding-bottom:1rem'>"
        "Day 08 · The Resilience Stack · "
        "World Bank PM2.5/Mortality/Population · WHO AQG 2021 · IQAir 2022 · OECD VSL"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
