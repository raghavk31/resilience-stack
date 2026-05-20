"""
Day 02 — Solar Potential Atlas
The Resilience Stack: 30 Days Building the Intelligence Layer for Humanity

Run:  streamlit run day02_solar_atlas.py
Data: NASA POWER API (free, no key) + Open-Meteo geocoding (free, no key)
"""

import os, json, requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── constants ──────────────────────────────────────────────────────────────────
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
NASA_URL    = "https://power.larc.nasa.gov/api/temporal/monthly/point"
PANEL_W     = 400        # watts peak per panel
PANEL_M2    = 1.7        # m² per panel
EFFICIENCY  = 0.20       # monocrystalline
PERF_RATIO  = 0.80       # system losses
CO2_G_KWH   = 450        # world avg grid CO2 intensity gCO2/kWh
COST_USD_W  = 1.0        # installed cost $/W (global avg, falling fast)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

# Notable locations for comparison
BENCHMARKS = {
    "Sahara Desert":   7.3,
    "Rajasthan, India":6.2,
    "Dubai":           5.8,
    "Los Angeles":     5.5,
    "Mumbai":          5.2,
    "Beijing":         4.5,
    "Madrid":          5.1,
    "New York":        4.3,
    "London":          2.8,
    "Berlin":          3.1,
    "Tokyo":           4.0,
    "Sydney":          5.0,
    "São Paulo":       5.3,
    "Lagos":           5.4,
    "Nairobi":         5.7,
}

# Solar class bands: (min_ghi, label, colour, tagline)
SOLAR_BANDS = [
    (6.5, "WORLD-CLASS", "#f59e0b", "Top 1% globally — pure solar gold"),
    (5.5, "EXCELLENT",   "#fb923c", "More sun than most of Europe gets in a year"),
    (4.5, "GOOD",        "#fbbf24", "Solar panels pay back in under 6 years here"),
    (3.5, "MODERATE",    "#a3e635", "Viable — best with storage or net metering"),
    (0.0, "LOW",         "#60a5fa", "Solar works, but needs more panels per kWh"),
]

def solar_class(ghi):
    for threshold, label, colour, tagline in SOLAR_BANDS:
        if ghi >= threshold:
            return label, colour, tagline
    return "LOW", "#60a5fa", "Solar works, but needs more panels per kWh"

# ── data fetching ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400*30, show_spinner=False)
def geocode(query: str):
    try:
        r = requests.get(GEOCODE_URL, params={"name": query, "count": 1, "language": "en", "format": "json"}, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        loc = results[0]
        return {
            "lat":     loc["latitude"],
            "lon":     loc["longitude"],
            "name":    loc.get("name", query),
            "country": loc.get("country", ""),
            "admin":   loc.get("admin1", ""),
        }
    except Exception:
        return None

@st.cache_data(ttl=86400*30, show_spinner=False)
def fetch_solar(lat: float, lon: float) -> dict | None:
    """Fetch 5-year monthly average GHI from NASA POWER."""
    try:
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,T2M",
            "community":  "RE",
            "longitude":  round(lon, 4),
            "latitude":   round(lat, 4),
            "start":      2019,
            "end":        2023,
            "format":     "JSON",
        }
        r = requests.get(NASA_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()["properties"]["parameter"]

        ghi_monthly   = data["ALLSKY_SFC_SW_DWN"]   # {YYYYMM: value}
        clear_monthly = data["CLRSKY_SFC_SW_DWN"]
        temp_monthly  = data["T2M"]

        # Average across years by month
        def month_avg(d):
            avgs = {}
            for m in range(1, 13):
                vals = [v for k, v in d.items()
                        if k.endswith(f"{m:02d}") and v > 0]
                avgs[m] = round(sum(vals)/len(vals), 3) if vals else None
            return avgs

        ghi  = month_avg(ghi_monthly)
        clr  = month_avg(clear_monthly)
        temp = month_avg(temp_monthly)

        valid = [v for v in ghi.values() if v]
        annual = round(sum(valid)/len(valid), 3) if valid else None

        return {"ghi": ghi, "clear": clr, "temp": temp, "annual": annual}
    except Exception:
        return None

# ── calculations ───────────────────────────────────────────────────────────────
def calc(annual_ghi: float, n_panels: int) -> dict:
    area          = n_panels * PANEL_M2
    kwh_per_day   = annual_ghi * area * EFFICIENCY * PERF_RATIO
    kwh_per_year  = kwh_per_day * 365
    peak_kw       = n_panels * PANEL_W / 1000
    co2_kg_saved  = kwh_per_year * CO2_G_KWH / 1000
    cost_usd      = peak_kw * 1000 * COST_USD_W

    # What it powers (annual kWh benchmarks)
    homes_avg_kwh = 3500    # global average home
    phone_kwh     = 0.012   # per full charge
    led_day_kwh   = 0.06    # 10W bulb, 6 hours

    return {
        "kwh_per_year":   round(kwh_per_year),
        "kwh_per_day":    round(kwh_per_day, 1),
        "peak_kw":        round(peak_kw, 1),
        "homes":          round(kwh_per_year / homes_avg_kwh, 1),
        "phones_per_day": int(kwh_per_day * 1000 / 12),   # phones charged/day
        "bulb_years":     round(kwh_per_year / (led_day_kwh * 365), 0),
        "co2_kg":         round(co2_kg_saved),
        "co2_trees":      round(co2_kg_saved / 21),   # ~21 kg CO2/tree/year
        "cost_usd":       round(cost_usd),
        "payback_yrs":    round(cost_usd / (kwh_per_year * 0.12), 1) if kwh_per_year > 0 else None,
    }

# ── charts ─────────────────────────────────────────────────────────────────────
def make_monthly_chart(solar_data: dict, location_name: str) -> go.Figure:
    ghi  = solar_data["ghi"]
    clr  = solar_data["clear"]
    months_vals = [ghi.get(m) or 0 for m in range(1, 13)]
    clear_vals  = [clr.get(m) or 0 for m in range(1, 13)]

    # Colour bars by intensity
    colours = []
    for v in months_vals:
        if v >= 6.5:   colours.append("#f59e0b")
        elif v >= 5.5: colours.append("#fb923c")
        elif v >= 4.5: colours.append("#fbbf24")
        elif v >= 3.5: colours.append("#a3e635")
        else:          colours.append("#60a5fa")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=MONTHS, y=months_vals,
        name="Actual (all-sky)",
        marker_color=colours,
        hovertemplate="<b>%{x}</b><br>%{y:.2f} kWh/m²/day<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=MONTHS, y=clear_vals,
        name="Clear-sky max",
        line=dict(color="rgba(255,255,255,0.2)", width=1.5, dash="dot"),
        hovertemplate="<b>%{x}</b> clear-sky: %{y:.2f}<extra></extra>",
        mode="lines",
    ))
    fig.update_layout(
        height=240,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b", size=10)),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            tickfont=dict(color="#64748b", size=10),
            ticksuffix=" kWh",
            title=dict(text="kWh/m²/day", font=dict(color="#475569", size=10)),
        ),
        legend=dict(font=dict(color="#64748b", size=10), bgcolor="rgba(0,0,0,0)",
                    orientation="h", y=1.15),
        bargap=0.25,
    )
    return fig

def make_comparison_chart(my_ghi: float, my_name: str) -> go.Figure:
    data = dict(BENCHMARKS)
    data[my_name] = my_ghi
    df = pd.DataFrame({"city": list(data.keys()), "ghi": list(data.values())})
    df = df.sort_values("ghi", ascending=True)

    colours = []
    for _, row in df.iterrows():
        if row["city"] == my_name:
            colours.append("#ffffff")
        else:
            lbl, c, _ = solar_class(row["ghi"])
            colours.append(c)

    fig = go.Figure(go.Bar(
        x=df["ghi"], y=df["city"],
        orientation="h",
        marker_color=colours,
        hovertemplate="<b>%{y}</b><br>%{x:.2f} kWh/m²/day<extra></extra>",
        text=[f"{v:.1f}" for v in df["ghi"]],
        textposition="outside",
        textfont=dict(color="#64748b", size=9),
    ))
    fig.update_layout(
        height=max(320, len(df)*22),
        margin=dict(l=0, r=40, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#64748b", size=9), ticksuffix=" kWh"),
        yaxis=dict(showgrid=False, tickfont=dict(
            color=["#ffffff" if c == "#ffffff" else "#64748b" for c in colours],
            size=10)),
    )
    return fig

def make_generation_chart(solar_data: dict, n_panels: int) -> go.Figure:
    ghi_vals = [solar_data["ghi"].get(m) or 0 for m in range(1, 13)]
    area = n_panels * PANEL_M2
    monthly_kwh = [round(v * area * EFFICIENCY * PERF_RATIO * 30) for v in ghi_vals]

    fig = go.Figure(go.Bar(
        x=MONTHS, y=monthly_kwh,
        marker_color="#f59e0b",
        marker_opacity=0.85,
        hovertemplate="<b>%{x}</b><br>%{y:,} kWh generated<extra></extra>",
    ))
    fig.update_layout(
        height=180,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b", size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                   tickfont=dict(color="#64748b", size=10), ticksuffix=" kWh"),
        bargap=0.25,
    )
    return fig

# ── html helpers ───────────────────────────────────────────────────────────────
def stat_chip(label, value, sub, colour="#f1f5f9"):
    return f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:16px;padding:14px 18px;flex:1;min-width:110px'>
  <div style='color:#475569;font-size:.65rem;text-transform:uppercase;
              letter-spacing:.1em;font-weight:600'>{label}</div>
  <div style='color:{colour};font-size:1.3rem;font-weight:800;margin-top:3px;
              font-family:Inter,sans-serif'>{value}</div>
  <div style='color:#334155;font-size:.68rem;margin-top:2px'>{sub}</div>
</div>"""

def power_item(icon, label, value, sub):
    return f"""
<div style='display:flex;align-items:center;gap:12px;padding:10px 14px;
            background:rgba(255,255,255,0.025);border-radius:12px;margin-bottom:6px'>
  <span style='font-size:1.5rem'>{icon}</span>
  <div style='flex:1'>
    <div style='color:#94a3b8;font-size:.82rem'>{label}</div>
    <div style='color:#334155;font-size:.7rem'>{sub}</div>
  </div>
  <div style='color:#f1f5f9;font-weight:700;font-size:.95rem'>{value}</div>
</div>"""

# ══ CSS ════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,*::before,*::after{box-sizing:border-box}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="block-container"]{
  background:#05050a!important;font-family:'Inter',system-ui,sans-serif!important;color:#e2e8f0!important}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"]{background:#080810!important}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer{display:none!important}

[data-testid="metric-container"]{
  background:rgba(255,255,255,0.03)!important;backdrop-filter:blur(16px)!important;
  border:1px solid rgba(255,255,255,0.07)!important;border-radius:18px!important;
  padding:20px 22px!important}
[data-testid="stMetricLabel"]>div{color:#64748b!important;font-size:.72rem!important;
  letter-spacing:.1em;text-transform:uppercase;font-weight:600}
[data-testid="stMetricValue"]>div{color:#f1f5f9!important;font-size:1.75rem!important;font-weight:800}
[data-testid="stMetricDelta"]>div{font-size:.8rem!important}

[data-testid="stTabs"] [data-baseweb="tab-list"]{
  background:rgba(255,255,255,0.025)!important;border-radius:12px!important;
  padding:4px!important;gap:2px!important;border:1px solid rgba(255,255,255,0.05)!important}
[data-testid="stTabs"] [data-baseweb="tab"]{
  background:transparent!important;border-radius:9px!important;color:#475569!important;
  font-size:.82rem!important;font-weight:600;padding:8px 16px!important;transition:all .2s!important}
[data-testid="stTabs"] [aria-selected="true"]{
  background:rgba(255,255,255,0.07)!important;color:#f1f5f9!important}

[data-testid="stTextInput"]>div>div>input{
  background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.08)!important;
  border-radius:12px!important;color:#e2e8f0!important;font-size:1rem!important}
[data-testid="stSlider"] [data-baseweb="slider"]{padding:0!important}
hr{border-color:rgba(255,255,255,0.05)!important;margin:24px 0!important}

.glass{background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.07);
  border-radius:24px;padding:24px 28px;transition:border-color .25s,box-shadow .25s}
.glass:hover{border-color:rgba(255,255,255,0.11);box-shadow:0 8px 40px rgba(0,0,0,0.4)}
.glass-sm{background:rgba(255,255,255,0.025);backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,0.06);border-radius:18px;padding:18px 22px}
.fade-in{animation:fadeIn .35s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.gradient-text{background:linear-gradient(135deg,#fbbf24 0%,#f97316 60%,#f1f5f9 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 13px;
  border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.sun-ring{width:120px;height:120px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;margin:0 auto 8px;position:relative}
</style>
"""

# ══ MAIN ═══════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Solar Atlas · Day 02", page_icon="☀️",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)

    # ── header ────────────────────────────────────────────────────────────────
    st.markdown("""
<div style='padding:32px 0 20px'>
  <div style='font-size:.72rem;color:#475569;letter-spacing:.15em;text-transform:uppercase;
              font-weight:600;margin-bottom:6px'>Day 02 · The Resilience Stack</div>
  <h1 class='gradient-text' style='font-size:2.6rem;font-weight:900;margin:0;line-height:1.1'>
    Solar Potential Atlas
  </h1>
  <p style='color:#475569;margin:8px 0 0;font-size:.95rem;max-width:540px'>
    The answer to grid stress is already falling on your roof.
    Search any city on earth — see how much sun it gets, what you could generate,
    and what that would replace.
  </p>
</div>
""", unsafe_allow_html=True)

    # ── search ────────────────────────────────────────────────────────────────
    params = st.query_params
    default_q = params.get("q", "Mumbai")

    col_search, col_btn = st.columns([4, 1], gap="small")
    with col_search:
        query = st.text_input("", value=default_q, placeholder="Search any city — Lagos, Oslo, Dubai, São Paulo…",
                              label_visibility="collapsed", key="city_input")
    with col_btn:
        search_btn = st.button("☀️ Explore", use_container_width=True, type="primary")

    if search_btn or query:
        st.query_params["q"] = query

    # ── fetch location ────────────────────────────────────────────────────────
    with st.spinner("Locating…"):
        loc = geocode(query)

    if not loc:
        st.error("Location not found. Try a major city name.")
        return

    lat, lon = loc["lat"], loc["lon"]
    display_name = f"{loc['name']}{', ' + loc['admin'] if loc['admin'] else ''}, {loc['country']}"

    # ── fetch solar data ──────────────────────────────────────────────────────
    with st.spinner(f"Pulling NASA POWER solar data for {loc['name']}…"):
        solar = fetch_solar(lat, lon)

    if not solar or not solar["annual"]:
        st.error("Could not fetch solar data for this location. Try another city.")
        return

    annual_ghi = solar["annual"]
    sol_label, sol_colour, sol_tagline = solar_class(annual_ghi)
    peak_sun_hrs = round(annual_ghi, 1)   # kWh/m²/day = peak sun hours/day

    # ── spotlight row ─────────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    spot_col, chart_col = st.columns([1, 1.8], gap="large")

    with spot_col:
        best_month  = max(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
        worst_month = min(solar["ghi"], key=lambda m: solar["ghi"].get(m) or 0)
        best_val  = solar["ghi"].get(best_month)  or 0
        worst_val = solar["ghi"].get(worst_month) or 0
        temp_avg  = round(sum(v for v in solar["temp"].values() if v) /
                          len([v for v in solar["temp"].values() if v]), 1)
        # Temperature efficiency factor (panels lose ~0.4%/°C above 25°C)
        temp_penalty = max(0, (temp_avg - 25) * 0.4)

        st.markdown(f"""
<div class='glass fade-in' style='box-shadow:0 0 60px rgba(251,191,36,0.08)'>
  <div style='display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px'>
    <div>
      <div style='font-size:1.4rem;font-weight:800;color:#f1f5f9'>{loc['name']}</div>
      <div style='color:#475569;font-size:.82rem;margin-top:2px'>{loc['country']}</div>
      <div style='color:#334155;font-size:.72rem;margin-top:1px'>{lat:.2f}°, {lon:.2f}°</div>
    </div>
    <span class='badge' style='background:rgba(251,191,36,0.12);color:{sol_colour};
          border:1px solid {sol_colour}50;margin-top:4px'>
      ☀ {sol_label}
    </span>
  </div>

  <div style='text-align:center;padding:20px 0 16px'>
    <div style='font-size:3.8rem;font-weight:900;color:{sol_colour};
                font-family:Inter,sans-serif;line-height:1'>{annual_ghi:.2f}</div>
    <div style='color:#64748b;font-size:.8rem;margin-top:4px'>kWh / m² / day  ·  annual average</div>
    <div style='color:#475569;font-size:.78rem;margin-top:6px;
                font-style:italic;max-width:200px;margin-left:auto;margin-right:auto'>
      {sol_tagline}
    </div>
  </div>

  <div style='display:flex;gap:8px;margin-top:4px'>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.65rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Best month</div>
      <div style='color:#fbbf24;font-weight:700;margin-top:3px'>{MONTHS[best_month-1]}</div>
      <div style='color:#64748b;font-size:.75rem'>{best_val:.1f} kWh</div>
    </div>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.65rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Low month</div>
      <div style='color:#60a5fa;font-weight:700;margin-top:3px'>{MONTHS[worst_month-1]}</div>
      <div style='color:#64748b;font-size:.75rem'>{worst_val:.1f} kWh</div>
    </div>
    <div style='flex:1;background:rgba(255,255,255,0.025);border-radius:12px;
                padding:10px;text-align:center'>
      <div style='color:#475569;font-size:.65rem;text-transform:uppercase;
                  letter-spacing:.08em;font-weight:600'>Avg temp</div>
      <div style='color:#f97316;font-weight:700;margin-top:3px'>{temp_avg}°C</div>
      <div style='color:#64748b;font-size:.75rem'>{"−"+str(round(temp_penalty,1))+"% eff." if temp_penalty > 0.5 else "Ideal"}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    with chart_col:
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                    "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                    "Monthly solar irradiance — 5-year average (NASA POWER 2019–2023)</p>",
                    unsafe_allow_html=True)
        st.plotly_chart(make_monthly_chart(solar, loc["name"]),
                        use_container_width=True, key="monthly_chart")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── calculator ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
  <span style='color:#334155;font-size:.72rem;text-transform:uppercase;
               letter-spacing:.12em;font-weight:600'>Solar calculator</span>
  <span style='color:#475569;font-size:.8rem'>— drag to size your installation</span>
</div>""", unsafe_allow_html=True)

    calc_col, result_col = st.columns([1, 1.6], gap="large")

    with calc_col:
        st.markdown("<div class='glass-sm'>", unsafe_allow_html=True)
        n_panels = st.slider("Number of panels", min_value=1, max_value=100, value=10,
                             help="Standard 400W panels, 1.7m² each")
        res = calc(annual_ghi, n_panels)

        st.markdown(f"""
<div style='margin-top:12px'>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>System size</span>
    <span style='color:#f1f5f9;font-weight:600'>{res["peak_kw"]} kWp</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Annual generation</span>
    <span style='color:#fbbf24;font-weight:700'>{res["kwh_per_year"]:,} kWh</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Daily average</span>
    <span style='color:#f1f5f9;font-weight:600'>{res["kwh_per_day"]} kWh/day</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0;
              border-bottom:1px solid rgba(255,255,255,0.04)'>
    <span style='color:#64748b;font-size:.82rem'>Installed cost (est.)</span>
    <span style='color:#f1f5f9;font-weight:600'>${res["cost_usd"]:,}</span>
  </div>
  <div style='display:flex;justify-content:space-between;padding:8px 0'>
    <span style='color:#64748b;font-size:.82rem'>Payback period</span>
    <span style='color:#4ade80;font-weight:700'>{res["payback_yrs"]} years</span>
  </div>
</div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with result_col:
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:12px;"
                    "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                    "What your panels replace</p>", unsafe_allow_html=True)

        st.markdown(
            power_item("🏠", "Homes powered (average)", f"{res['homes']}", f"at 3,500 kWh/yr per household") +
            power_item("📱", "Phones charged per day", f"{res['phones_per_day']:,}", "based on 12 Wh per full charge") +
            power_item("🌳", "Trees worth of CO₂/year", f"{res['co2_trees']:,}", f"{res['co2_kg']:,} kg CO₂ avoided annually") +
            power_item("💡", "Equivalent LED bulb-years", f"{int(res['bulb_years']):,}", "10W bulb running 6 hours/day"),
            unsafe_allow_html=True)

        # Monthly generation chart
        st.markdown("<p style='color:#64748b;font-size:.72rem;margin:12px 0 4px;"
                    "text-transform:uppercase;letter-spacing:.08em'>Monthly output</p>",
                    unsafe_allow_html=True)
        st.plotly_chart(make_generation_chart(solar, n_panels),
                        use_container_width=True, key="gen_chart")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── comparison ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='glass'>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                f"text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                f"{loc['name']} vs the world — where does it rank?</p>",
                unsafe_allow_html=True)
    # Find neighbours in the benchmark list
    better = [(k, v) for k, v in BENCHMARKS.items() if v < annual_ghi]
    worse  = [(k, v) for k, v in BENCHMARKS.items() if v >= annual_ghi]
    if better:
        nearest_lower = max(better, key=lambda x: x[1])
        lower_txt = f"Better than {nearest_lower[0]} ({nearest_lower[1]} kWh/m²/day)"
    else:
        lower_txt = "Among the sunniest places on earth"
    if worse:
        nearest_higher = min(worse, key=lambda x: x[1])
        higher_txt = f"Less sun than {nearest_higher[0]} ({nearest_higher[1]} kWh/m²/day)"
    else:
        higher_txt = "Top of the global solar rankings"

    st.markdown(f"""
<div style='display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap'>
  <span style='color:#4ade80;font-size:.82rem;
    background:rgba(74,222,128,0.08);padding:4px 12px;border-radius:999px'>
    ✓ {lower_txt}
  </span>
  <span style='color:#94a3b8;font-size:.82rem;
    background:rgba(255,255,255,0.04);padding:4px 12px;border-radius:999px'>
    → {higher_txt}
  </span>
</div>""", unsafe_allow_html=True)
    st.plotly_chart(make_comparison_chart(annual_ghi, loc["name"]),
                    use_container_width=True, key="compare_chart")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"""
<div class='glass' style='border-color:rgba(255,255,255,0.04)'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;
              flex-wrap:wrap;gap:16px'>
    <div style='flex:2;min-width:260px'>
      <p style='color:#475569;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
                font-weight:600;margin:0 0 8px'>The uncomfortable truth about solar</p>
      <p style='color:#94a3b8;margin:0;line-height:1.7;font-size:.9rem'>
        The sunniest places on earth — the Sahel, South Asia, the Middle East —
        are exactly the places with the most grid stress and the least energy access.
        The resource and the need are perfectly aligned.
        The only thing missing is the capital to build it.
        <strong style='color:#64748b'>That's a financial problem, not a technical one.</strong>
      </p>
    </div>
    <div style='flex:1;min-width:200px;padding:16px 20px;background:rgba(255,255,255,0.025);
                border-radius:16px;border:1px solid rgba(255,255,255,0.06)'>
      <div style='color:#334155;font-size:.72rem;text-transform:uppercase;
                  letter-spacing:.1em;font-weight:600'>Next</div>
      <div style='color:#f1f5f9;font-weight:700;font-size:1rem;margin:6px 0 4px'>Day 03 →</div>
      <div style='color:#64748b;font-size:.82rem'>
        Water Stress Index — where freshwater is already running out,
        and which grids will fail first when rivers stop flowing.
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
