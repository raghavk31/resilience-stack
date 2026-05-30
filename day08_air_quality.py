"""
The Resilience Stack — Day 08
Air Quality & Health Cost

Sources:
  World Bank EN.ATM.PM25.MC.M3 — mean annual PM2.5 exposure (1990-2020)
  World Bank SH.STA.AIRP.P5    — air pollution mortality rate per 100k (2019)
  World Bank SP.POP.TOTL        — population
  WHO Global Ambient Air Quality Guidelines 2021
  IQAir 2023 World Air Quality Report — city-level annual mean PM2.5
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
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_META = "https://api.worldbank.org/v2/country"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
IND_PM25, IND_MORT, IND_POP = "EN.ATM.PM25.MC.M3", "SH.STA.AIRP.P5", "SP.POP.TOTL"
FIRST_YEAR, LAST_PM25_YEAR, LAST_MORT_YEAR = 1990, 2020, 2019
WHO_2021, WHO_2005 = 5.0, 10.0
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
    "Delhi":           (28.66, 77.23,  92.0, "India",        "South Asia"),
    "Lahore":          (31.55, 74.34,  85.0, "Pakistan",     "South Asia"),
    "Dhaka":           (23.81, 90.41,  66.0, "Bangladesh",   "South Asia"),
    "Kolkata":         (22.57, 88.37,  55.0, "India",        "South Asia"),
    "Karachi":         (24.86, 67.01,  57.0, "Pakistan",     "South Asia"),
    "Cairo":           (30.06, 31.25,  48.0, "Egypt",        "Africa & M. East"),
    "Lagos":           ( 6.45,  3.47,  51.0, "Nigeria",      "Africa & M. East"),
    "Mumbai":          (19.07, 72.87,  40.0, "India",        "South Asia"),
    "Chengdu":         (30.66,104.07,  38.0, "China",        "East Asia"),
    "Jakarta":         (-6.21,106.85,  30.0, "Indonesia",    "SE Asia"),
    "Beijing":         (39.91,116.39,  28.0, "China",        "East Asia"),
    "Shanghai":        (31.23,121.47,  26.0, "China",        "East Asia"),
    "Hanoi":           (21.03,105.83,  25.0, "Vietnam",      "SE Asia"),
    "Ho Chi Minh":     (10.82,106.63,  23.0, "Vietnam",      "SE Asia"),
    "Bangkok":         (13.75,100.52,  22.0, "Thailand",     "SE Asia"),
    "Mexico City":     (19.43,-99.13,  18.0, "Mexico",       "Latin America"),
    "Warsaw":          (52.23, 21.01,  18.0, "Poland",       "Europe"),
    "Nairobi":         (-1.29, 36.82,  18.0, "Kenya",        "Africa & M. East"),
    "Istanbul":        (41.01, 28.95,  16.0, "Turkey",       "Europe"),
    "Seoul":           (37.57,126.98,  16.0, "South Korea",  "East Asia"),
    "Los Angeles":     (34.05,-118.24, 14.0, "USA",          "North America"),
    "Bogotá":          ( 4.71,-74.07,  14.0, "Colombia",     "Latin America"),
    "Cape Town":       (-33.93, 18.42, 13.0, "South Africa", "Africa & M. East"),
    "Singapore":       ( 1.35,103.82,  12.0, "Singapore",    "SE Asia"),
    "Moscow":          (55.75, 37.62,  11.0, "Russia",       "Europe"),
    "São Paulo":       (-23.55,-46.63, 11.0, "Brazil",       "Latin America"),
    "Madrid":          (40.42, -3.70,  10.0, "Spain",        "Europe"),
    "Paris":           (48.85,  2.35,  10.0, "France",       "Europe"),
    "Tokyo":           (35.69,139.69,   8.0, "Japan",        "East Asia"),
    "London":          (51.51, -0.13,   8.0, "UK",           "Europe"),
    "Berlin":          (52.52, 13.40,   8.0, "Germany",      "Europe"),
    "New York":        (40.71,-74.01,   7.0, "USA",          "North America"),
    "Zurich":          (47.38,  8.54,   6.0, "Switzerland",  "Europe"),
    "Toronto":         (43.65,-79.38,   6.0, "Canada",       "North America"),
    "Sydney":          (-33.87,151.21,  5.0, "Australia",    "Oceania"),
}


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }

/* ── Shell ── */
.stApp { background: #f2f2f2 !important; }
[data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; background: transparent !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"],
section.main { background: #f2f2f2 !important; }

/* ── Page header ── */
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

/* ── Tab navigation ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
  gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: #bbb !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: .1em !important;
  padding: 12px 24px !important;
  border-radius: 0 !important;
  border-right: 1px solid rgba(0,0,0,0.06) !important;
}
.stTabs [data-baseweb="tab"]:last-child { border-right: none !important; }
.stTabs [aria-selected="true"] {
  color: #111 !important;
  border-bottom: 2px solid #111 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]   { display: none !important; }
[data-testid="stTabsContent"] { padding: 0 !important; }

/* ── Two-column layout — left panel via :has() ── */
[data-testid="stHorizontalBlock"]:has(.mc-left) {
  gap: 0 !important;
  background: transparent;
}
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:first-child {
  background: #ffffff !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 120px);
}
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:last-child {
  background: #f2f2f2 !important;
  padding: 24px 28px !important;
}

/* ── Left panel typography ── */
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
.mc-ctrl-sub { font-size: .7rem; color: #bbb; margin-bottom: 6px; line-height: 1.4; }
.mc-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 14px; padding: 4px 0;
}
.mc-val {
  font-size: 1.4rem; font-weight: 700; color: #111; line-height: 1;
  letter-spacing: -.3px; font-variant-numeric: tabular-nums;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-lbl { font-size: .64rem; color: #aaa; margin-top: 4px; line-height: 1.4; }
.mc-sec  { font-size: .67rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.mc-note { font-size: .64rem; color: #ccc; line-height: 1.6; }

/* ── Right panel labels ── */
.r-lbl {
  font-size: .67rem; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: #bbb; margin-bottom: 6px;
}

/* ── Live result ── */
.live-box {
  border: 1px solid rgba(0,0,0,0.08); border-radius: 6px;
  padding: 12px 14px; margin-top: 8px; background: #fafafa;
}
.live-city { font-size: .65rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #bbb; margin-bottom: 4px; }
.live-val  { font-size: 1.5rem; font-weight: 700; font-family: 'Space Grotesk', sans-serif; line-height: 1; }
.live-sub  { font-size: .68rem; color: #888; margin-top: 4px; }

/* ── Widgets ── */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .78rem !important; font-weight: 600 !important; color: #333 !important;
}
[data-baseweb="select"] > div {
  background: white !important; border: 1px solid rgba(0,0,0,0.12) !important;
  border-radius: 4px !important; font-size: .78rem !important;
}
[data-baseweb="select"] span { color: #333 !important; }
.stRadio > div { gap: 4px !important; }
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
        r = requests.get("https://api.airvisual.com/v2/nearest_city",
                         params={"lat": lat, "lon": lon, "key": key}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                return float(d["data"]["current"]["pollution"]["p2"]["conc"])
    except Exception:
        pass
    return None

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


# ── Tab 1 — PM2.5 Exposure ────────────────────────────────────────────────────

def tab_pm25(snap: pd.DataFrame, pm25_ts: pd.DataFrame) -> None:
    years = sorted(pm25_ts["year"].unique())
    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">PM2.5 Exposure</h2>'
            '<p class="mc-desc">Mean annual PM2.5 concentration by country, satellite-ground fusion 1990–2020.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)

        year = st.select_slider("Year", options=years, value=LAST_PM25_YEAR, key="pm_yr",
                                label_visibility="collapsed")

        snap_y = pm25_ts[pm25_ts["year"] == year].merge(
            snap[["iso3", "name", "region"]], on="iso3", how="left")
        snap_y["exceeds_who"] = snap_y["pm25"] > WHO_2021
        snap_y["pm25_ratio"]  = (snap_y["pm25"] / WHO_2021).round(1)
        n_exceed = int(snap_y["exceeds_who"].sum())
        n_total  = len(snap_y)
        g_avg    = snap_y["pm25"].mean()
        worst_row = snap_y.nlargest(1, "pm25").iloc[0] if len(snap_y) else None

        st.markdown(_sep() + _mg([
            (f"{g_avg:.1f} µg/m³", f"Global mean — {year}"),
            (f"{n_exceed}/{n_total}", "Countries over WHO 5 µg/m³"),
        ]), unsafe_allow_html=True)

        if worst_row is not None:
            st.markdown(
                _sep() +
                f'<div class="mc-sec">Most exposed — {year}</div>'
                f'<div class="mc-val">{worst_row["country"]}</div>'
                f'<div class="mc-lbl">{worst_row["pm25"]:.1f} µg/m³ · {worst_row["pm25_ratio"]:.1f}× WHO limit</div>',
                unsafe_allow_html=True,
            )

        st.markdown(_sep() +
                    '<div class="mc-ctrl-lbl">Country trend</div>'
                    '<div class="mc-ctrl-sub">PM2.5 annual mean 1990–2020</div>',
                    unsafe_allow_html=True)
        countries   = sorted(snap_y["country"].dropna().unique())
        default_idx = countries.index("India") if "India" in countries else 0
        sel = st.selectbox("", countries, index=default_idx, key="pm_ctry",
                           label_visibility="collapsed")
        cdf = pm25_ts[pm25_ts["country"] == sel].sort_values("year")
        if not cdf.empty:
            tf = go.Figure()
            tf.add_trace(go.Scatter(
                x=cdf["year"], y=cdf["pm25"], mode="lines+markers",
                line=dict(color="#323232", width=1.8), marker=dict(size=3.5, color="#323232"),
                hovertemplate="<b>%{x}</b> — %{y:.1f} µg/m³<extra></extra>",
            ))
            tf.add_hline(y=WHO_2021, line_dash="dot", line_color="#dc2626",
                         annotation_text="WHO 2021", annotation_position="top right",
                         annotation_font=dict(color="#dc2626", size=9))
            tf.update_layout(**_chart(h=150,
                margin=dict(l=0, r=36, t=4, b=0),
                xaxis=dict(showgrid=False, color="#ccc", tickfont=dict(size=9)),
                yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#ccc",
                           tickfont=dict(size=9), title="µg/m³",
                           title_font=dict(size=9, color="#ccc"))))
            st.plotly_chart(tf, use_container_width=True)

        st.markdown(_sep() +
                    '<div class="mc-note">World Bank EN.ATM.PM25.MC.M3 · van Donkelaar et al. satellite-ground fusion · WHO AQG 2021: 5 µg/m³ annual.</div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown(f'<div class="r-lbl">Mean annual PM2.5 — {year}</div>', unsafe_allow_html=True)
        fig = px.choropleth(
            snap_y, locations="iso3", color="pm25",
            color_continuous_scale=["#f0fdf4","#fef9c3","#fde68a","#fca5a5","#ef4444","#7f1d1d"],
            range_color=[0, 80], hover_name="country",
            hover_data={"iso3": False, "pm25": ":.1f", "pm25_ratio": ":.1f"},
        )
        fig.update_layout(
            **_chart(h=500),
            geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#d4d4d4",
                     bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e5e5e5",
                     showocean=True, oceancolor="#ddeeff"),
            coloraxis_colorbar=dict(
                title=dict(text="µg/m³", font=dict(size=10, color="#aaa")),
                thickness=9, len=0.5,
                tickvals=[0,5,10,25,50,80], ticktext=["0","5 WHO","10","25","50","80+"],
                tickfont=dict(size=9, color="#aaa"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"""
        <div style="background:#fff;border:1px solid rgba(0,0,0,0.07);border-left:3px solid #6366f1;
             border-radius:0 6px 6px 0;padding:.8rem 1rem;margin-top:.4rem">
          <div style="font-size:.67rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
                      color:#6366f1;margin-bottom:.35rem">WHO 2021 GUIDELINE — 5 µg/m³</div>
          <div style="font-size:.78rem;color:#555;line-height:1.7">
            The 2021 revision halved the previous 10 µg/m³ target — making it stricter than any
            country's legal standard. <b style="color:#333">99% of humanity</b> now lives in officially
            non-compliant air. Meeting it globally would prevent the majority of 7M annual deaths
            attributed to air pollution.
          </div>
        </div>
        """, unsafe_allow_html=True)


# ── Tab 2 — Health Impact ─────────────────────────────────────────────────────

def tab_health(snap: pd.DataFrame) -> None:
    snap_h = snap.dropna(subset=["mort_per_100k"]).copy()
    snap_h["deaths_k"] = snap_h["deaths"] / 1000
    total_deaths = snap_h["deaths"].sum()
    sa_rate = snap_h[snap_h["region"].str.contains("South Asia", na=False)]["mort_per_100k"].mean()
    eu_rate = snap_h[snap_h["region"].str.contains("Europe", na=False)]["mort_per_100k"].mean()
    sa_eu   = f"{sa_rate/eu_rate:.1f}×" if eu_rate and eu_rate > 0 else "—"

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Health Impact</h2>'
            '<p class="mc-desc">Air pollution mortality — where people die and how many.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            ("7 million",            "Deaths/yr — WHO estimate"),
            ("800/hr",               "Lives lost every hour"),
            (f"{total_deaths/1e6:.1f}M", f"Modelled — {LAST_MORT_YEAR}"),
            (sa_eu,                  "South Asia vs Europe rate"),
        ]), unsafe_allow_html=True)

        st.markdown(_sep() + '<div class="mc-ctrl-lbl">Rank countries by</div>',
                    unsafe_allow_html=True)
        view = st.radio("", ["Absolute deaths", "Deaths per 100k"],
                        key="h_view", label_visibility="collapsed")

        st.markdown(_sep() +
                    '<div class="mc-note">World Bank SH.STA.AIRP.P5 (2019). '
                    'Absolute deaths = rate × population. WHO GHO 2019.</div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        if view.startswith("Absolute"):
            top   = snap_h.nlargest(20, "deaths").sort_values("deaths")
            x_col, x_lbl = "deaths_k", "Deaths (thousands / yr)"
            lbl   = "TOP 20 — ABSOLUTE DEATHS FROM AIR POLLUTION"
        else:
            top   = snap_h.nlargest(20, "mort_per_100k").sort_values("mort_per_100k")
            x_col, x_lbl = "mort_per_100k", "Deaths per 100k"
            lbl   = "TOP 20 — DEATHS PER 100K FROM AIR POLLUTION"

        st.markdown(f'<div class="r-lbl">{lbl}</div>', unsafe_allow_html=True)
        fig = px.bar(top, x=x_col, y="country", orientation="h",
                     color=x_col,
                     color_continuous_scale=["#fca5a5","#ef4444","#991b1b"],
                     labels={x_col: x_lbl, "country": ""},
                     hover_data={"region": True, "pm25": ":.1f", "mort_per_100k": ":.0f"},
                     text=x_col)
        fig.update_traces(texttemplate="%{x:,.0f}" if view.startswith("Absolute") else "%{x:.0f}",
                          textposition="outside", textfont=dict(size=9, color="#aaa"))
        fig.update_layout(**_chart(h=540, margin=dict(l=0, r=80, t=8, b=0)),
                          xaxis=dict(title=x_lbl, gridcolor="rgba(0,0,0,0.06)",
                                     color="#bbb", tickfont=dict(size=10)),
                          yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">PM2.5 EXPOSURE vs MORTALITY RATE</div>',
                    unsafe_allow_html=True)
        sfig = px.scatter(snap_h[snap_h["deaths"] > 0],
                          x="pm25", y="mort_per_100k", size="population", color="region",
                          hover_name="country",
                          labels={"pm25": "Mean PM2.5 (µg/m³)", "mort_per_100k": "Deaths per 100k"},
                          size_max=40,
                          color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a"])
        sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#dc2626",
                       annotation_text="WHO 5 µg/m³",
                       annotation_font=dict(color="#dc2626", size=9))
        sfig.update_layout(**_chart(h=300),
                           xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 3 — Economic Cost ─────────────────────────────────────────────────────

def tab_economic(snap: pd.DataFrame) -> None:
    snap_e = snap.dropna(subset=["deaths", "econ_cost_B"]).copy()
    snap_e = snap_e[snap_e["deaths"] > 0]
    total_cost  = snap_e["econ_cost_B"].sum()
    top_country = snap_e.loc[snap_e["econ_cost_B"].idxmax(), "country"]
    top_cost    = snap_e["econ_cost_B"].max()

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Economic Cost</h2>'
            '<p class="mc-desc">Monetised welfare loss — deaths × OECD Value of Statistical Life by income group.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            ("$5.1 trillion",       "Annual welfare loss — WHO 2016"),
            (f"${total_cost:.0f}B", "Modelled (World Bank data)"),
            (top_country,           f"Highest cost · ${top_cost:.0f}B/yr"),
            ("up to 30×",           "Return on clean air investment"),
        ]), unsafe_allow_html=True)

        st.markdown(_sep() +
                    '<div class="mc-note">Cost = deaths × VSL by income: '
                    'HIC $9.4M · UMC $3.5M · LMC $1.2M · LIC $0.6M. '
                    'OECD 2020. WHO welfare-loss $5.1T: WHO/WB 2016.</div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="r-lbl">TOP 20 — ECONOMIC COST OF AIR POLLUTION</div>',
                    unsafe_allow_html=True)
        top20 = snap_e.nlargest(20, "econ_cost_B").sort_values("econ_cost_B")
        bfig  = px.bar(top20, x="econ_cost_B", y="country", orientation="h",
                       color="econ_cost_B",
                       color_continuous_scale=["#fde68a","#f59e0b","#b45309","#78350f"],
                       labels={"econ_cost_B": "$B/yr", "country": ""},
                       hover_data={"deaths": ":,.0f", "pm25": ":.1f"}, text="econ_cost_B")
        bfig.update_traces(texttemplate="%{x:.1f}B", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        bfig.update_layout(**_chart(h=540, margin=dict(l=0, r=80, t=8, b=0)),
                           xaxis=dict(title="Economic cost ($B / yr)",
                                      gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                           coloraxis_showscale=False)
        st.plotly_chart(bfig, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">COST vs PM2.5 (bubble = deaths)</div>',
                    unsafe_allow_html=True)
        sfig = px.scatter(snap_e[snap_e["econ_cost_B"] > 0.1],
                          x="pm25", y="econ_cost_B", size="deaths", color="region",
                          hover_name="country",
                          labels={"pm25": "Mean PM2.5 (µg/m³)", "econ_cost_B": "$B/yr"},
                          size_max=50, log_y=True,
                          color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a"])
        sfig.add_vline(x=WHO_2021, line_dash="dot", line_color="#d97706",
                       annotation_text="WHO 5 µg/m³",
                       annotation_font=dict(color="#d97706", size=9))
        sfig.update_layout(**_chart(h=300),
                           xaxis=dict(gridcolor="rgba(0,0,0,0.06)", color="#bbb", tickfont=dict(size=10)),
                           yaxis=dict(title="$B/yr (log)", gridcolor="rgba(0,0,0,0.06)",
                                      color="#bbb", tickfont=dict(size=10)),
                           legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(sfig, use_container_width=True)


# ── Tab 4 — City Air Quality ──────────────────────────────────────────────────

def tab_city() -> None:
    rows = []
    for city, (lat, lon, pm25, country, region) in CITY_AIR.items():
        aqi = _pm25_to_aqi(pm25)
        lbl, col = _aqi_label(aqi)
        rows.append({"city": city, "lat": lat, "lon": lon, "pm25": pm25,
                     "country": country, "region": region, "aqi": aqi,
                     "category": lbl, "color": col, "who_x": round(pm25/WHO_2021, 1)})
    cdf = pd.DataFrame(rows)
    n_safe  = int((cdf["pm25"] <= WHO_2021).sum())
    n_2005  = int((cdf["pm25"] <= WHO_2005).sum())
    worst   = cdf.loc[cdf["pm25"].idxmax(), "city"]
    worst_v = cdf["pm25"].max()
    best    = cdf.loc[cdf["pm25"].idxmin(), "city"]
    best_v  = cdf["pm25"].min()

    left, right = st.columns([1.1, 2.9], gap="large")

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">City Air Quality</h2>'
            '<p class="mc-desc">35 cities · IQAir 2023 annual PM2.5 means (2022 data).</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="padding:0 22px">', unsafe_allow_html=True)
        st.markdown(_sep() + _mg([
            (f"{worst}: {worst_v:.0f}", "Most polluted (µg/m³)"),
            (f"{best}: {best_v:.0f}",   "Cleanest (µg/m³)"),
            (f"{n_safe}/{len(cdf)}",    "Meet WHO 2021 (≤5)"),
            (f"{n_2005}/{len(cdf)}",    "Meet WHO 2005 (≤10)"),
        ]), unsafe_allow_html=True)

        st.markdown(_sep() + '<div class="mc-ctrl-lbl">Filter by region</div>',
                    unsafe_allow_html=True)
        region_filter = st.multiselect("", sorted(cdf["region"].unique()),
                                       default=sorted(cdf["region"].unique()),
                                       key="c_region", label_visibility="collapsed")

        st.markdown(_sep() + '<div class="mc-sec">Live AQI lookup</div>',
                    unsafe_allow_html=True)
        live_city = st.selectbox("", list(CITY_AIR.keys()),
                                 key="c_live", label_visibility="collapsed")
        if st.button("Fetch current reading", key="c_fetch", use_container_width=True):
            lat, lon, annual, _, _ = CITY_AIR[live_city]
            with st.spinner(""):
                live = _fetch_live_pm25(lat, lon)
            if live is not None:
                live_aqi = _pm25_to_aqi(live)
                live_lbl, live_col = _aqi_label(live_aqi)
                delta = live - annual
                delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
                st.markdown(f"""
                <div class="live-box">
                  <div class="live-city">{live_city} — right now</div>
                  <div class="live-val" style="color:{live_col}">{live:.1f} µg/m³</div>
                  <div class="live-sub">AQI {live_aqi} · <b style="color:{live_col}">{live_lbl}</b>
                  <br>Annual avg {annual:.0f} · current {delta_str}</div>
                </div>""", unsafe_allow_html=True)
            elif not st.secrets.get("IQAIR_KEY", ""):
                st.caption("Add `IQAIR_KEY` to Streamlit secrets to enable.")
            else:
                st.caption("API error — try again.")

        st.markdown(_sep() +
                    '<div class="mc-note">IQAir 2023 report (2022 data). '
                    'Live: IQAir AirVisual nearest_city, cached 1 hr. '
                    'AQI: US EPA PM2.5 breakpoints.</div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        fdf = cdf[cdf["region"].isin(region_filter)].sort_values("pm25")
        st.markdown('<div class="r-lbl">ANNUAL MEAN PM2.5 — WHO GUIDELINES</div>',
                    unsafe_allow_html=True)
        bar = px.bar(fdf, x="pm25", y="city", orientation="h",
                     color="pm25",
                     color_continuous_scale=["#16a34a","#ca8a04","#ea580c","#dc2626","#7c3aed","#7f1d1d"],
                     range_color=[0, 100],
                     labels={"pm25": "PM2.5 (µg/m³)", "city": ""},
                     hover_data={"country": True, "aqi": True, "category": True, "who_x": True},
                     text="pm25")
        bar.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                          textfont=dict(size=9, color="#aaa"))
        bar.add_vline(x=WHO_2021, line_dash="dot", line_color="#dc2626",
                      annotation_text=f"WHO 2021 · {WHO_2021} µg/m³",
                      annotation_position="top right",
                      annotation_font=dict(color="#dc2626", size=9))
        bar.add_vline(x=WHO_2005, line_dash="dot", line_color="#ea580c",
                      annotation_text=f"WHO 2005 · {WHO_2005} µg/m³",
                      annotation_position="bottom right",
                      annotation_font=dict(color="#ea580c", size=9))
        bar.update_layout(**_chart(h=max(480, len(fdf)*22), margin=dict(l=0, r=60, t=8, b=0)),
                          xaxis=dict(title="PM2.5 (µg/m³)", gridcolor="rgba(0,0,0,0.06)",
                                     color="#bbb", tickfont=dict(size=10)),
                          yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10)),
                          coloraxis_showscale=False)
        st.plotly_chart(bar, use_container_width=True)

        st.markdown('<div class="r-lbl" style="margin-top:1.5rem">GLOBAL CITY MAP</div>',
                    unsafe_allow_html=True)
        mfig = px.scatter_geo(fdf, lat="lat", lon="lon", size="pm25", color="pm25",
                              color_continuous_scale=["#16a34a","#ca8a04","#ea580c","#dc2626","#7c3aed"],
                              range_color=[0, 100], hover_name="city",
                              hover_data={"lat": False, "lon": False, "pm25": ":.1f",
                                          "aqi": True, "category": True, "country": True},
                              size_max=32)
        mfig.update_layout(**_chart(h=340),
                           geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#ddd",
                                    bgcolor="rgba(248,248,248,1)", showcountries=True,
                                    countrycolor="#eee", showocean=True, oceancolor="#e8f0f8",
                                    projection_type="natural earth"),
                           coloraxis_colorbar=dict(
                               title=dict(text="µg/m³", font=dict(size=10, color="#aaa")),
                               thickness=9, len=0.5, tickfont=dict(size=9, color="#aaa")))
        st.plotly_chart(mfig, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="mc-header">
      <div class="mc-topline">
        <span class="mc-dot"></span>
        AIR QUALITY EXPLORER · DAY 08 · THE RESILIENCE STACK
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        data = load_air_data()

    if data["snap"].empty:
        st.error("Failed to load data from World Bank.")
        return

    snap    = data["snap"]
    pm25_ts = data["pm25_ts"]

    tab1, tab2, tab3, tab4 = st.tabs([
        "PM2.5 Exposure",
        "Health Impact",
        "Economic Cost",
        "City Air Quality",
    ])

    with tab1: tab_pm25(snap, pm25_ts)
    with tab2: tab_health(snap)
    with tab3: tab_economic(snap)
    with tab4: tab_city()


if __name__ == "__main__":
    main()
