"""
The Resilience Stack — Day 08
Air Quality & Health Cost

Sources:
  World Bank EN.ATM.PM25.MC.M3 — mean annual PM2.5 exposure by country (1990-2020)
  World Bank SH.STA.AIRP.P5    — air pollution mortality rate per 100k (2019)
  World Bank SP.POP.TOTL        — population
  WHO Global Ambient Air Quality Guidelines 2021
  IQAir 2023 World Air Quality Report — city-level annual mean PM2.5 (2022 data)
  IQAir AirVisual API           — real-time city PM2.5 (requires IQAIR_KEY secret)
  OECD 2020 VSL meta-analysis   — value of statistical life by income level
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Air Quality Explorer · Day 08",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_PM25 = "EN.ATM.PM25.MC.M3"
IND_MORT = "SH.STA.AIRP.P5"
IND_POP  = "SP.POP.TOTL"

FIRST_YEAR, LAST_PM25_YEAR, LAST_MORT_YEAR = 1990, 2020, 2019
WHO_2021, WHO_2005 = 5.0, 10.0

# OECD 2020 updated VSL by income group
VSL_USD     = {"HIC": 9_400_000, "UMC": 3_500_000, "LMC": 1_200_000, "LIC": 600_000}
DEFAULT_VSL = 1_800_000

AQI_BREAKS = [
    (0.0,   12.0,   0,  50, "Good",                  "#16a34a"),
    (12.1,  35.4,  51, 100, "Moderate",              "#ca8a04"),
    (35.5,  55.4, 101, 150, "Unhealthy (Sensitive)", "#ea580c"),
    (55.5, 150.4, 151, 200, "Unhealthy",             "#dc2626"),
    (150.5,250.4, 201, 300, "Very Unhealthy",        "#7c3aed"),
    (250.5,500.0, 301, 500, "Hazardous",             "#7f1d1d"),
]

CITY_AIR: dict[str, tuple] = {
    "Delhi, India":            (28.66, 77.23,  92.0, "India",        "South Asia"),
    "Lahore, Pakistan":        (31.55, 74.34,  85.0, "Pakistan",     "South Asia"),
    "Dhaka, Bangladesh":       (23.81, 90.41,  66.0, "Bangladesh",   "South Asia"),
    "Kolkata, India":          (22.57, 88.37,  55.0, "India",        "South Asia"),
    "Karachi, Pakistan":       (24.86, 67.01,  57.0, "Pakistan",     "South Asia"),
    "Cairo, Egypt":            (30.06, 31.25,  48.0, "Egypt",        "Africa & Middle East"),
    "Lagos, Nigeria":          ( 6.45,  3.47,  51.0, "Nigeria",      "Africa & Middle East"),
    "Mumbai, India":           (19.07, 72.87,  40.0, "India",        "South Asia"),
    "Chengdu, China":          (30.66,104.07,  38.0, "China",        "East Asia"),
    "Jakarta, Indonesia":      (-6.21,106.85,  30.0, "Indonesia",    "SE Asia"),
    "Beijing, China":          (39.91,116.39,  28.0, "China",        "East Asia"),
    "Shanghai, China":         (31.23,121.47,  26.0, "China",        "East Asia"),
    "Hanoi, Vietnam":          (21.03,105.83,  25.0, "Vietnam",      "SE Asia"),
    "Ho Chi Minh City":        (10.82,106.63,  23.0, "Vietnam",      "SE Asia"),
    "Bangkok, Thailand":       (13.75,100.52,  22.0, "Thailand",     "SE Asia"),
    "Mexico City":             (19.43,-99.13,  18.0, "Mexico",       "Latin America"),
    "Warsaw, Poland":          (52.23, 21.01,  18.0, "Poland",       "Europe"),
    "Nairobi, Kenya":          (-1.29, 36.82,  18.0, "Kenya",        "Africa & Middle East"),
    "Istanbul, Turkey":        (41.01, 28.95,  16.0, "Turkey",       "Europe"),
    "Seoul, South Korea":      (37.57,126.98,  16.0, "South Korea",  "East Asia"),
    "Los Angeles, USA":        (34.05,-118.24, 14.0, "USA",          "North America"),
    "Bogotá, Colombia":        ( 4.71,-74.07,  14.0, "Colombia",     "Latin America"),
    "Cape Town, S. Africa":    (-33.93, 18.42, 13.0, "South Africa", "Africa & Middle East"),
    "Singapore":               ( 1.35,103.82,  12.0, "Singapore",    "SE Asia"),
    "Moscow, Russia":          (55.75, 37.62,  11.0, "Russia",       "Europe"),
    "São Paulo, Brazil":       (-23.55,-46.63, 11.0, "Brazil",       "Latin America"),
    "Madrid, Spain":           (40.42, -3.70,  10.0, "Spain",        "Europe"),
    "Paris, France":           (48.85,  2.35,  10.0, "France",       "Europe"),
    "Tokyo, Japan":            (35.69,139.69,   8.0, "Japan",        "East Asia"),
    "London, UK":              (51.51, -0.13,   8.0, "UK",           "Europe"),
    "Berlin, Germany":         (52.52, 13.40,   8.0, "Germany",      "Europe"),
    "New York, USA":           (40.71,-74.01,   7.0, "USA",          "North America"),
    "Zurich, Switzerland":     (47.38,  8.54,   6.0, "Switzerland",  "Europe"),
    "Toronto, Canada":         (43.65,-79.38,   6.0, "Canada",       "North America"),
    "Sydney, Australia":       (-33.87,151.21,  5.0, "Australia",    "Oceania"),
}

MODES = [
    "PM2.5 Exposure",
    "Health Impact",
    "Economic Cost",
    "City Air Quality",
]


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700;800;900&display=swap');

/* ── App shell ── */
html, body, [class*="css"] {
  font-family: 'Inter', Sailec, helvetica, sans-serif;
  color: #323232;
}
.stApp { background: #f5f5f5 !important; }
[data-testid="stAppViewContainer"] { background: #f5f5f5 !important; }
section.main { background: #f5f5f5 !important; }
[data-testid="block-container"] {
  background: transparent !important;
  padding: 2rem 2.5rem !important;
  max-width: 100% !important;
}

/* ── Sidebar — the left panel ── */
section[data-testid="stSidebar"] {
  background: #ffffff !important;
  border-right: 1px solid rgba(0,0,0,0.10);
  min-width: 360px !important;
  max-width: 360px !important;
}
section[data-testid="stSidebar"] > div {
  background: #ffffff !important;
  padding: 0 !important;
}
[data-testid="stSidebarContent"] {
  padding: 0 !important;
  background: #ffffff !important;
}
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* Sidebar typography */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] li { color: #555; font-size: .82rem; }
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  font-size: .82rem !important;
  font-weight: 600 !important;
  color: #323232 !important;
  letter-spacing: 0 !important;
}

/* Sidebar inputs */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: #fff !important;
  border: 1px solid rgba(0,0,0,0.12) !important;
  border-radius: 4px !important;
  font-size: .82rem !important;
  color: #323232 !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span { color: #323232 !important; }
section[data-testid="stSidebar"] [data-testid="stSlider"] { padding: 0; }

/* Sidebar radio (mode selector) */
section[data-testid="stSidebar"] .stRadio [data-baseweb="radio-group"] {
  gap: 0;
}
section[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] {
  padding: 0;
}

/* Sidebar multiselect */
section[data-testid="stSidebar"] [data-baseweb="tag"] {
  background: rgba(0,0,0,0.06) !important;
}

/* ── Morphocode component classes ── */

/* Top bar */
.mc-bar {
  padding: 13px 20px;
  border-bottom: 1px solid rgba(0,0,0,0.10);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
  color: #111;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  font-family: 'Space Grotesk', sans-serif;
  text-transform: uppercase;
}
.mc-bar-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  border: 2px solid #111;
  display: inline-block;
  flex-shrink: 0;
}

/* Mode tabs */
.mc-modes {
  display: flex;
  border-bottom: 1px solid rgba(0,0,0,0.10);
}
.mc-mode {
  flex: 1;
  padding: 9px 6px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .04em;
  color: #aaa;
  text-align: center;
  cursor: pointer;
  text-transform: uppercase;
  border-right: 1px solid rgba(0,0,0,0.08);
  transition: color .15s, background .15s;
}
.mc-mode:last-child { border-right: none; }
.mc-mode.active {
  color: #111;
  background: #fafafa;
  border-bottom: 2px solid #111;
}

/* Panel body */
.mc-body { padding: 20px 20px 0; }

/* Section title */
.mc-title {
  font-size: 1.45rem;
  font-weight: 800;
  color: #111;
  line-height: 1.2;
  margin: 0 0 .45rem;
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: -.3px;
}

/* Description */
.mc-desc {
  font-size: .8rem;
  color: #666;
  line-height: 1.65;
  margin: 0;
}
.mc-learn { color: #aaa; font-size: .78rem; }

/* Thin separator */
.mc-sep {
  border: none;
  border-top: 1px solid rgba(0,0,0,0.10);
  margin: 18px 0;
}

/* Control block */
.mc-ctrl-lbl {
  font-size: .82rem;
  font-weight: 600;
  color: #323232;
  margin-bottom: 2px;
}
.mc-ctrl-sub {
  font-size: .73rem;
  color: #999;
  margin-bottom: 8px;
  line-height: 1.4;
}

/* Metric grid */
.mc-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 4px 0;
}
.mc-metrics.three { grid-template-columns: 1fr 1fr 1fr; }
.mc-metric-val {
  font-size: 1.55rem;
  font-weight: 700;
  color: #111;
  font-family: 'Space Grotesk', sans-serif;
  line-height: 1;
  letter-spacing: -.4px;
  font-variant-numeric: tabular-nums;
}
.mc-metric-lbl {
  font-size: .68rem;
  color: #999;
  margin-top: 4px;
  line-height: 1.4;
}

/* Secondary section header */
.mc-sec-hdr {
  font-size: .72rem;
  font-weight: 600;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin-bottom: 10px;
}

/* Sub-panel (light gray bg, like "Figure Ground" in Morphocode) */
.mc-subpanel {
  background: #f7f7f7;
  margin: 0 -20px;
  padding: 16px 20px;
  border-top: 1px solid rgba(0,0,0,0.08);
}

/* Method note */
.mc-note {
  font-size: .68rem;
  color: #bbb;
  line-height: 1.6;
  margin-top: 6px;
}

/* ── Main area ── */
.main-label {
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #aaa;
  margin-bottom: .5rem;
}

/* ── Live lookup result ── */
.live-result {
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 6px;
  padding: 12px 14px;
  margin-top: 10px;
  background: #fff;
}
.live-city { font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #aaa; margin-bottom: 4px; }
.live-val  { font-size: 1.6rem; font-weight: 700; font-family: 'Space Grotesk', sans-serif; line-height: 1; letter-spacing: -.5px; }
.live-sub  { font-size: .7rem; color: #888; margin-top: 4px; }
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

    valid = set(meta["iso3"])
    pm25  = pm25[pm25["iso3"].isin(valid)].rename(columns={"value": "pm25"})
    mort  = mort[mort["iso3"].isin(valid)].rename(columns={"value": "mort_per_100k"})
    pop   = pop[pop["iso3"].isin(valid)].rename(columns={"value": "population"})

    snap  = pm25[pm25["year"] == LAST_PM25_YEAR][["iso3", "country", "pm25"]]
    snap  = snap.merge(mort[["iso3", "mort_per_100k"]], on="iso3", how="left")
    snap  = snap.merge(pop[["iso3", "population"]],     on="iso3", how="left")
    snap  = snap.merge(meta[["iso3", "name", "region", "income_id"]], on="iso3", how="left")
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


@st.cache_data(ttl=3_600, show_spinner=False)
def _fetch_live_pm25(lat: float, lon: float) -> float | None:
    key = st.secrets.get("IQAIR_KEY", "")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.airvisual.com/v2/nearest_city",
            params={"lat": lat, "lon": lon, "key": key},
            timeout=8,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                return float(d["data"]["current"]["pollution"]["p2"]["conc"])
    except Exception:
        pass
    return None


def _metrics(*pairs: tuple[str, str], cols: int = 2) -> str:
    cls = "mc-metrics" + (" three" if cols == 3 else "")
    cells = "".join(
        f'<div><div class="mc-metric-val">{v}</div>'
        f'<div class="mc-metric-lbl">{l}</div></div>'
        for v, l in pairs
    )
    return f'<div class="{cls}">{cells}</div>'


def _sep() -> str:
    return '<hr class="mc-sep">'


def _chart(h: int = 520, **kw) -> dict:
    base = dict(
        height=h,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#666", size=11),
        margin=dict(l=0, r=0, t=8, b=0),
    )
    base.update(kw)
    return base


# ── Mode: PM2.5 Exposure ──────────────────────────────────────────────────────

def mode_pm25(snap: pd.DataFrame, pm25_ts: pd.DataFrame) -> None:
    years = sorted(pm25_ts["year"].unique())

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        year = st.select_slider(
            "Year", options=years, value=LAST_PM25_YEAR, key="pm_year"
        )

    snap_y = pm25_ts[pm25_ts["year"] == year].merge(
        snap[["iso3", "name", "region"]], on="iso3", how="left"
    )
    snap_y["exceeds_who"] = snap_y["pm25"] > WHO_2021
    snap_y["pm25_ratio"]  = (snap_y["pm25"] / WHO_2021).round(1)

    n_exceed  = int(snap_y["exceeds_who"].sum())
    n_total   = len(snap_y)
    g_avg     = snap_y["pm25"].mean()
    worst_row = snap_y.nlargest(1, "pm25").iloc[0] if len(snap_y) else None

    with st.sidebar:
        st.markdown(_sep() + _metrics(
            (f"{g_avg:.1f} µg/m³", f"Global mean PM2.5 — {year}"),
            (f"{n_exceed}/{n_total}", "Countries over WHO limit"),
        ) + _sep(), unsafe_allow_html=True)

        if worst_row is not None:
            st.markdown(
                f'<div class="mc-sec-hdr">Most exposed country — {year}</div>'
                f'<div class="mc-metric-val">{worst_row["country"]}</div>'
                f'<div class="mc-metric-lbl">{worst_row["pm25"]:.1f} µg/m³ · '
                f'{worst_row["pm25_ratio"]:.1f}× WHO limit</div>' + _sep(),
                unsafe_allow_html=True,
            )

        st.markdown('<div class="mc-ctrl-lbl">Country trend</div>'
                    '<div class="mc-ctrl-sub">PM2.5 annual mean 1990–2020</div>',
                    unsafe_allow_html=True)
        countries   = sorted(snap_y["country"].dropna().unique())
        default_idx = countries.index("India") if "India" in countries else 0
        sel = st.selectbox("Country", countries, index=default_idx,
                           key="pm_country", label_visibility="collapsed")

        cdf = pm25_ts[pm25_ts["country"] == sel].sort_values("year")
        if not cdf.empty:
            tfig = go.Figure()
            tfig.add_trace(go.Scatter(
                x=cdf["year"], y=cdf["pm25"], mode="lines+markers",
                line=dict(color="#323232", width=1.8),
                marker=dict(size=4, color="#323232"),
                hovertemplate="<b>%{x}</b><br>%{y:.1f} µg/m³<extra></extra>",
            ))
            tfig.add_hline(y=WHO_2021, line_dash="dot", line_color="#dc2626",
                           annotation_text=f"WHO 2021", annotation_position="top right",
                           annotation_font=dict(color="#dc2626", size=9))
            tfig.add_hline(y=WHO_2005, line_dash="dot", line_color="#ea580c",
                           annotation_text=f"WHO 2005", annotation_position="bottom right",
                           annotation_font=dict(color="#ea580c", size=9))
            tfig.update_layout(**_chart(
                h=160,
                margin=dict(l=0, r=40, t=4, b=0),
                xaxis=dict(showgrid=False, color="#bbb", tickfont=dict(size=10)),
                yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb",
                           tickfont=dict(size=10), title="µg/m³",
                           title_font=dict(size=10, color="#bbb")),
            ))
            st.plotly_chart(tfig, use_container_width=True)

        st.markdown(
            '<hr class="mc-sep">'
            '<div class="mc-note">World Bank EN.ATM.PM25.MC.M3 · van Donkelaar et al. '
            'satellite-ground fusion · 1990–2020 · WHO guideline 5 µg/m³ (2021)</div>',
            unsafe_allow_html=True,
        )

    # ── Main: choropleth ─────────────────────────────────────────────────────
    st.markdown(f'<div class="main-label">Mean annual PM2.5 exposure — {year}</div>',
                unsafe_allow_html=True)

    fig = px.choropleth(
        snap_y, locations="iso3",
        color="pm25",
        color_continuous_scale=["#f0fdf4","#fef9c3","#fde68a","#fca5a5","#ef4444","#7f1d1d"],
        range_color=[0, 80],
        hover_name="country",
        hover_data={"iso3": False, "pm25": ":.1f", "pm25_ratio": ":.1f"},
    )
    fig.update_layout(
        **_chart(h=560),
        geo=dict(
            showframe=False, showcoastlines=True,
            coastlinecolor="#d4d4d4", bgcolor="rgba(0,0,0,0)",
            showcountries=True, countrycolor="#e5e5e5",
            showocean=True, oceancolor="#e8f4fd",
            showlakes=True, lakecolor="#e8f4fd",
        ),
        coloraxis_colorbar=dict(
            title=dict(text="µg/m³", font=dict(size=10, color="#999")),
            thickness=10, len=0.5,
            tickvals=[0, 5, 10, 25, 50, 80],
            ticktext=["0", "5 WHO", "10", "25", "50", "80+"],
            tickfont=dict(size=9, color="#999"),
            bgcolor="rgba(255,255,255,0.8)",
            borderwidth=0,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Mode: Health Impact ───────────────────────────────────────────────────────

def mode_health(snap: pd.DataFrame) -> None:
    snap_h = snap.dropna(subset=["mort_per_100k"]).copy()
    snap_h["deaths_k"] = snap_h["deaths"] / 1000
    total_deaths = snap_h["deaths"].sum()

    sa_rate = snap_h[snap_h["region"].str.contains("South Asia", na=False)]["mort_per_100k"].mean()
    eu_rate = snap_h[snap_h["region"].str.contains("Europe", na=False)]["mort_per_100k"].mean()
    sa_eu   = f"{sa_rate/eu_rate:.1f}×" if eu_rate and eu_rate > 0 else "—"

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(_sep() + _metrics(
            ("7 million",            "Deaths per year (WHO)"),
            ("800/hr",               "Lives lost every hour"),
            (f"{total_deaths/1e6:.1f}M", f"Modelled — {LAST_MORT_YEAR}"),
            (sa_eu,                  "South Asia vs Europe rate"),
        ) + _sep(), unsafe_allow_html=True)

        st.markdown('<div class="mc-ctrl-lbl">Rank countries by</div>',
                    unsafe_allow_html=True)
        view = st.radio(
            "", ["Absolute deaths", "Deaths per 100k"],
            key="h_view", label_visibility="collapsed"
        )

        st.markdown(
            '<hr class="mc-sep">'
            '<div class="mc-note">World Bank SH.STA.AIRP.P5 (2019) · '
            'Absolute deaths = rate × population · WHO GHO 2019</div>',
            unsafe_allow_html=True,
        )

    # ── Main ─────────────────────────────────────────────────────────────────
    if view.startswith("Absolute"):
        top   = snap_h.nlargest(20, "deaths").sort_values("deaths")
        x_col, x_lbl, fmt = "deaths_k", "Deaths (thousands / yr)", ",.0f"
        lbl   = "TOP 20 — ABSOLUTE DEATHS FROM AIR POLLUTION"
    else:
        top   = snap_h.nlargest(20, "mort_per_100k").sort_values("mort_per_100k")
        x_col, x_lbl, fmt = "mort_per_100k", "Deaths per 100k population", ".0f"
        lbl   = "TOP 20 — DEATHS PER 100K FROM AIR POLLUTION"

    st.markdown(f'<div class="main-label">{lbl}</div>', unsafe_allow_html=True)

    fig = px.bar(
        top, x=x_col, y="country", orientation="h",
        color=x_col,
        color_continuous_scale=["#fca5a5","#ef4444","#991b1b"],
        labels={x_col: x_lbl, "country": ""},
        hover_data={"region": True, "pm25": ":.1f", "mort_per_100k": ":.0f"},
        text=x_col,
    )
    fig.update_traces(
        texttemplate=f"%{{x:{fmt}}}",
        textposition="outside",
        textfont=dict(size=9, color="#999"),
    )
    fig.update_layout(
        **_chart(h=560, margin=dict(l=0, r=80, t=8, b=0)),
        xaxis=dict(title=dict(text=x_lbl, font=dict(size=10, color="#bbb")),
                   gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        yaxis=dict(showgrid=False, color="#323232", tickfont=dict(size=10)),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # PM2.5 vs mortality scatter
    st.markdown('<div class="main-label" style="margin-top:1.5rem">PM2.5 EXPOSURE vs MORTALITY RATE</div>',
                unsafe_allow_html=True)
    sfig = px.scatter(
        snap_h[snap_h["deaths"] > 0],
        x="pm25", y="mort_per_100k",
        size="population", color="region",
        hover_name="country",
        labels={"pm25": "Mean PM2.5 (µg/m³)", "mort_per_100k": "Deaths per 100k",
                "population": "Population"},
        size_max=40,
        color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a"],
    )
    sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#dc2626",
                   annotation_text="WHO 5 µg/m³",
                   annotation_font=dict(color="#dc2626", size=9))
    sfig.update_layout(
        **_chart(h=300),
        xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        legend=dict(font=dict(size=9, color="#999"), bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(sfig, use_container_width=True)


# ── Mode: Economic Cost ───────────────────────────────────────────────────────

def mode_economic(snap: pd.DataFrame) -> None:
    snap_e = snap.dropna(subset=["deaths", "econ_cost_B"]).copy()
    snap_e = snap_e[snap_e["deaths"] > 0]

    total_cost  = snap_e["econ_cost_B"].sum()
    top_country = snap_e.loc[snap_e["econ_cost_B"].idxmax(), "country"]
    top_cost    = snap_e["econ_cost_B"].max()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(_sep() + _metrics(
            ("$5.1 trillion",        "Annual welfare loss — WHO 2016"),
            (f"${total_cost:.0f}B",  "Modelled (World Bank data)"),
            (top_country,            f"Highest cost · ${top_cost:.0f}B/yr"),
            ("up to 30×",            "Return on clean air investment"),
        ) + _sep(), unsafe_allow_html=True)

        st.markdown(
            '<div class="mc-note">'
            'Cost = deaths × VSL by income: HIC $9.4M · UMC $3.5M · LMC $1.2M · LIC $0.6M. '
            'OECD 2020 meta-analysis. WHO welfare-loss $5.1T: WHO/World Bank 2016.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Main ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="main-label">TOP 20 — ECONOMIC COST OF AIR POLLUTION</div>',
                unsafe_allow_html=True)

    top20 = snap_e.nlargest(20, "econ_cost_B").sort_values("econ_cost_B")
    bfig  = px.bar(
        top20, x="econ_cost_B", y="country", orientation="h",
        color="econ_cost_B",
        color_continuous_scale=["#fde68a","#f59e0b","#b45309","#78350f"],
        labels={"econ_cost_B": "Economic cost ($B/yr)", "country": ""},
        hover_data={"deaths": ":,.0f", "pm25": ":.1f", "income_id": True},
        text="econ_cost_B",
    )
    bfig.update_traces(
        texttemplate="%{x:.1f}B",
        textposition="outside",
        textfont=dict(size=9, color="#999"),
    )
    bfig.update_layout(
        **_chart(h=560, margin=dict(l=0, r=80, t=8, b=0)),
        xaxis=dict(title=dict(text="Economic cost ($B / yr)", font=dict(size=10, color="#bbb")),
                   gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        yaxis=dict(showgrid=False, color="#323232", tickfont=dict(size=10)),
        coloraxis_showscale=False,
    )
    st.plotly_chart(bfig, use_container_width=True)

    st.markdown('<div class="main-label" style="margin-top:1.5rem">COST vs PM2.5 EXPOSURE — bubble = absolute deaths</div>',
                unsafe_allow_html=True)
    sfig = px.scatter(
        snap_e[snap_e["econ_cost_B"] > 0.1],
        x="pm25", y="econ_cost_B",
        size="deaths", color="region",
        hover_name="country",
        hover_data={"deaths": ":,.0f", "income_id": True, "pm25": ":.1f"},
        labels={"pm25": "Mean PM2.5 (µg/m³)", "econ_cost_B": "Economic cost ($B/yr)"},
        size_max=50, log_y=True,
        color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a"],
    )
    sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#d97706",
                   annotation_text="WHO 5 µg/m³",
                   annotation_font=dict(color="#d97706", size=9))
    sfig.update_layout(
        **_chart(h=300),
        xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        yaxis=dict(title=dict(text="$B/yr (log)", font=dict(size=10, color="#bbb")),
                   gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        legend=dict(font=dict(size=9, color="#999"), bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(sfig, use_container_width=True)


# ── Mode: City Air Quality ────────────────────────────────────────────────────

def mode_city() -> None:
    rows = []
    for city, (lat, lon, pm25, country, region) in CITY_AIR.items():
        aqi          = _pm25_to_aqi(pm25)
        label, color = _aqi_label(aqi)
        rows.append({
            "city": city, "lat": lat, "lon": lon,
            "pm25": pm25, "country": country, "region": region,
            "aqi": aqi, "category": label, "color": color,
            "who_x": round(pm25 / WHO_2021, 1),
        })
    cdf = pd.DataFrame(rows)

    n_safe  = int((cdf["pm25"] <= WHO_2021).sum())
    n_2005  = int((cdf["pm25"] <= WHO_2005).sum())
    worst   = cdf.loc[cdf["pm25"].idxmax(), "city"].split(",")[0]
    worst_v = cdf["pm25"].max()
    best    = cdf.loc[cdf["pm25"].idxmin(), "city"].split(",")[0]
    best_v  = cdf["pm25"].min()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(_sep() + _metrics(
            (f"{worst}: {worst_v:.0f}", "Most polluted city (µg/m³)"),
            (f"{best}: {best_v:.0f}",   "Cleanest city (µg/m³)"),
            (f"{n_safe}/{len(cdf)}",     "Meet WHO 2021 (≤5 µg/m³)"),
            (f"{n_2005}/{len(cdf)}",     "Meet WHO 2005 (≤10 µg/m³)"),
        ) + _sep(), unsafe_allow_html=True)

        st.markdown('<div class="mc-ctrl-lbl">Filter by region</div>',
                    unsafe_allow_html=True)
        region_filter = st.multiselect(
            "", sorted(cdf["region"].unique()),
            default=sorted(cdf["region"].unique()),
            key="c_region", label_visibility="collapsed",
        )

        # Live lookup
        st.markdown(_sep() +
                    '<div class="mc-sec-hdr">Live AQI lookup</div>',
                    unsafe_allow_html=True)
        live_city = st.selectbox("", list(CITY_AIR.keys()),
                                 key="c_live", label_visibility="collapsed")
        if st.button("Fetch current reading", key="c_fetch", use_container_width=True):
            lat, lon, annual, _, _ = CITY_AIR[live_city]
            with st.spinner(""):
                live = _fetch_live_pm25(lat, lon)
            if live is not None:
                live_aqi       = _pm25_to_aqi(live)
                live_lbl, live_col = _aqi_label(live_aqi)
                delta          = live - annual
                delta_str      = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
                st.markdown(f"""
                <div class="live-result">
                  <div class="live-city">{live_city.split(',')[0].upper()} — RIGHT NOW</div>
                  <div class="live-val" style="color:{live_col}">{live:.1f} µg/m³</div>
                  <div class="live-sub">
                    AQI {live_aqi} · <b style="color:{live_col}">{live_lbl}</b><br>
                    Annual avg {annual:.0f} µg/m³ · current {delta_str}
                  </div>
                </div>""", unsafe_allow_html=True)
            elif not st.secrets.get("IQAIR_KEY", ""):
                st.caption("Add `IQAIR_KEY` to Streamlit secrets to enable live readings.")
            else:
                st.caption("API error or rate limit — try again shortly.")

        st.markdown(
            '<hr class="mc-sep">'
            '<div class="mc-note">IQAir 2023 World Air Quality Report (2022 data). '
            'Live: IQAir AirVisual API nearest_city. '
            'AQI: US EPA PM2.5 breakpoints.</div>',
            unsafe_allow_html=True,
        )

    # ── Main ─────────────────────────────────────────────────────────────────
    fdf = cdf[cdf["region"].isin(region_filter)].sort_values("pm25")

    st.markdown('<div class="main-label">ANNUAL MEAN PM2.5 BY CITY — vs WHO GUIDELINES</div>',
                unsafe_allow_html=True)

    bar = px.bar(
        fdf, x="pm25", y="city", orientation="h",
        color="pm25",
        color_continuous_scale=["#16a34a","#ca8a04","#ea580c","#dc2626","#7c3aed","#7f1d1d"],
        range_color=[0, 100],
        labels={"pm25": "Annual mean PM2.5 (µg/m³)", "city": ""},
        hover_data={"country": True, "aqi": True, "category": True, "who_x": True},
        text="pm25",
    )
    bar.update_traces(texttemplate="%{x:.0f}",
                      textposition="outside",
                      textfont=dict(size=9, color="#999"))
    bar.add_vline(x=WHO_2021, line_dash="dot", line_color="#dc2626",
                  annotation_text=f"WHO 2021 · {WHO_2021} µg/m³",
                  annotation_position="top right",
                  annotation_font=dict(color="#dc2626", size=9))
    bar.add_vline(x=WHO_2005, line_dash="dot", line_color="#ea580c",
                  annotation_text=f"WHO 2005 · {WHO_2005} µg/m³",
                  annotation_position="bottom right",
                  annotation_font=dict(color="#ea580c", size=9))
    bar.update_layout(
        **_chart(h=max(500, len(fdf) * 22), margin=dict(l=0, r=60, t=8, b=0)),
        xaxis=dict(title=dict(text="PM2.5 (µg/m³)", font=dict(size=10, color="#bbb")),
                   gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
        yaxis=dict(showgrid=False, color="#323232", tickfont=dict(size=10)),
        coloraxis_showscale=False,
    )
    st.plotly_chart(bar, use_container_width=True)

    st.markdown('<div class="main-label" style="margin-top:1.5rem">GLOBAL CITY AIR QUALITY</div>',
                unsafe_allow_html=True)
    mfig = px.scatter_geo(
        fdf, lat="lat", lon="lon",
        size="pm25", color="pm25",
        color_continuous_scale=["#16a34a","#ca8a04","#ea580c","#dc2626","#7c3aed"],
        range_color=[0, 100],
        hover_name="city",
        hover_data={"lat": False, "lon": False, "pm25": ":.1f",
                    "aqi": True, "category": True, "country": True},
        size_max=35,
    )
    mfig.update_layout(
        **_chart(h=360),
        geo=dict(
            showframe=False, showcoastlines=True,
            coastlinecolor="#d4d4d4", bgcolor="rgba(248,248,248,1)",
            showcountries=True, countrycolor="#e5e5e5",
            showocean=True, oceancolor="#e8f4fd",
            projection_type="natural earth",
        ),
        coloraxis_colorbar=dict(
            title=dict(text="µg/m³", font=dict(size=10, color="#999")),
            thickness=10, len=0.5,
            tickfont=dict(size=9, color="#999"),
            bgcolor="rgba(255,255,255,0.8)",
            borderwidth=0,
        ),
    )
    st.plotly_chart(mfig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Sidebar top bar + mode selector ──────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div class="mc-bar">'
            '<span class="mc-bar-dot"></span>'
            'AIR QUALITY EXPLORER'
            '</div>',
            unsafe_allow_html=True,
        )

        mode = st.radio(
            "", MODES, key="mode", label_visibility="collapsed",
            horizontal=False,
        )

        # Panel header rendered per mode
        mode_titles = {
            "PM2.5 Exposure":  ("PM2.5 Exposure",
                                "Mean annual PM2.5 concentration by country, "
                                "satellite-ground fusion dataset 1990–2020."),
            "Health Impact":   ("Health Impact",
                                "Air pollution mortality rates and absolute death "
                                f"toll by country — World Bank {LAST_MORT_YEAR} data."),
            "Economic Cost":   ("Economic Cost",
                                "Monetised welfare loss using OECD Value of "
                                "Statistical Life by income group."),
            "City Air Quality":("City Air Quality",
                                "35 cities, IQAir 2023 annual PM2.5 means. "
                                "Live readings via IQAir API when key is configured."),
        }
        title, desc = mode_titles[mode]
        st.markdown(
            f'<div class="mc-body">'
            f'<h2 class="mc-title">{title}</h2>'
            f'<p class="mc-desc">{desc}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner(""):
        data = load_air_data()

    if data["snap"].empty:
        st.error("Failed to load data from World Bank.")
        return

    snap    = data["snap"]
    pm25_ts = data["pm25_ts"]

    # ── Render selected mode ──────────────────────────────────────────────────
    if mode == "PM2.5 Exposure":
        mode_pm25(snap, pm25_ts)
    elif mode == "Health Impact":
        mode_health(snap)
    elif mode == "Economic Cost":
        mode_economic(snap)
    else:
        mode_city()


if __name__ == "__main__":
    main()
