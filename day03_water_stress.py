import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Water Stress Index · Day 03",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_BASE = "https://api.worldbank.org/v2/country/all/indicator"
HEADERS = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

INDICATORS = {
    "withdrawal_pct":  "ER.H2O.FWTL.ZS",  # % of available freshwater
    "withdrawal_cap":  "ER.H2O.FWST.ZS",  # m³ per capita withdrawn
    "freshwater_cap":  "ER.H2O.INTR.PC",  # renewable freshwater per capita (m³)
    "safe_access":     "SH.H2O.BASW.ZS",  # % with basic water access
    "agri_share":      "ER.H2O.FWAG.ZS",  # agriculture % of withdrawals
    "industry_share":  "ER.H2O.FWIN.ZS",  # industry % of withdrawals
    "domestic_share":  "ER.H2O.FWDM.ZS",  # domestic % of withdrawals
}

# UN/FAO water stress thresholds
BANDS = [
    (80, "CRITICAL", "#ef4444", "rgba(239,68,68,0.18)"),
    (40, "HIGH",     "#f97316", "rgba(249,115,22,0.18)"),
    (20, "MEDIUM",   "#eab308", "rgba(234,179,8,0.18)"),
    (10, "LOW-MED",  "#60a5fa", "rgba(96,165,250,0.18)"),
    ( 0, "ABUNDANT", "#22d3ee", "rgba(34,211,238,0.18)"),
]

CSCALE = [
    (0.00, "#22d3ee"),
    (0.12, "#60a5fa"),
    (0.30, "#a78bfa"),
    (0.52, "#eab308"),
    (0.72, "#f97316"),
    (1.00, "#ef4444"),
]

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
/* Global dark background */
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #05050a !important;
    color: #c8c8d4 !important;
}
.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 12px !important;
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* Sidebar dark panel — Morphocode-style */
[data-testid="stSidebar"] {
    background: #08080f !important;
    border-right: 1px solid #14142a !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 24px 20px 32px !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] .stMarkdown {
    color: #9898a8 !important;
}
[data-testid="stSidebar"] h2 {
    color: #e8e8f0 !important;
    font-size: 18px !important;
    letter-spacing: -0.02em !important;
    margin: 4px 0 0 !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
}

/* Selectbox / radio dark */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] input {
    background: #0d0d1a !important;
    border-color: #1a1a2e !important;
    color: #c8c8d4 !important;
}

/* 2-column metric grid */
.metrics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px 14px;
    margin: 14px 0;
}
.metric-label {
    font-size: 9px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #3a3a52;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 20px;
    font-weight: 600;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    color: #e0e0ec;
    line-height: 1.15;
}
.metric-unit {
    font-size: 11px;
    color: #44445a;
    font-weight: 400;
    margin-left: 2px;
}

/* Stress badge */
.stress-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 10px 5px 8px;
    border-radius: 2px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 8px;
    margin-bottom: 14px;
}
.stress-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* Sector bars */
.sector-row { margin-bottom: 11px; }
.sector-label-row {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #3a3a52;
    margin-bottom: 5px;
}
.sector-track {
    height: 3px;
    background: #14142a;
    border-radius: 2px;
}
.sector-fill { height: 3px; border-radius: 2px; }

/* Separator */
.sep {
    border: none;
    border-top: 1px solid #14142a;
    margin: 18px 0;
}

/* Country heading */
.country-heading {
    font-size: 17px;
    font-weight: 700;
    color: #e8e8f0;
    letter-spacing: -0.01em;
    line-height: 1.25;
    margin-bottom: 2px;
}
.day-label {
    font-size: 9px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #2a2a42;
}

/* Overflow warning */
.overflow-warn {
    font-size: 10px;
    letter-spacing: 0.03em;
    color: #f97316;
}

/* Data footer */
.data-footer {
    font-size: 10px;
    color: #2a2a42;
    letter-spacing: 0.04em;
    line-height: 2.0;
}

/* Tab styling */
button[data-baseweb="tab"] {
    color: #3a3a52 !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    background: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #c8c8d4 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    background: #14142a !important;
}

/* Dataframe dark */
[data-testid="stDataFrame"] { background: transparent !important; }
</style>
"""

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def _fetch_indicator(code: str) -> dict[str, tuple[float, str]]:
    """Returns {iso3: (value, year)} for most-recent non-null observation."""
    url = f"{WB_BASE}/{code}?format=json&mrv=1&per_page=300"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return {}
    if len(payload) < 2 or not payload[1]:
        return {}
    out: dict[str, tuple[float, str]] = {}
    for item in payload[1]:
        iso = item.get("countryiso3code", "")
        val = item.get("value")
        yr  = str(item.get("date", ""))
        if iso and len(iso) == 3 and iso.isalpha() and val is not None:
            out[iso] = (float(val), yr)
    return out


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_water_data() -> pd.DataFrame:
    """Merge all 7 WB indicators into one DataFrame keyed by ISO3."""
    raw = {key: _fetch_indicator(code) for key, code in INDICATORS.items()}

    rows = []
    for iso, (w_pct, yr) in raw["withdrawal_pct"].items():
        rows.append({
            "iso":            iso,
            "withdrawal_pct": w_pct,
            "year":           yr,
            "withdrawal_cap": raw["withdrawal_cap"].get(iso,  (None, ""))[0],
            "freshwater_cap": raw["freshwater_cap"].get(iso,  (None, ""))[0],
            "safe_access":    raw["safe_access"].get(iso,     (None, ""))[0],
            "agri_share":     raw["agri_share"].get(iso,      (None, ""))[0],
            "industry_share": raw["industry_share"].get(iso,  (None, ""))[0],
            "domestic_share": raw["domestic_share"].get(iso,  (None, ""))[0],
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_country_trend(iso: str) -> pd.DataFrame:
    """1990–2024 time series of withdrawal % for one country."""
    code = INDICATORS["withdrawal_pct"]
    url = (f"https://api.worldbank.org/v2/country/{iso}/indicator/{code}"
           f"?format=json&date=1990:2024&per_page=50")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return pd.DataFrame()
    if len(payload) < 2 or not payload[1]:
        return pd.DataFrame()
    rows = [
        {"year": int(d["date"]), "value": d["value"]}
        for d in payload[1]
        if d.get("value") is not None
    ]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("year")


@st.cache_data(ttl=86_400 * 14, persist="disk", show_spinner=False)
def load_country_names() -> dict[str, str]:
    """ISO3 → display name from World Bank country list."""
    url = "https://api.worldbank.org/v2/country?format=json&per_page=300"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        payload = r.json()
        return {
            c["id"]: c["name"]
            for c in payload[1]
            if len(c.get("id", "")) == 3 and c["id"].isalpha()
        }
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def stress_band(pct: float) -> tuple[str, str, str]:
    for threshold, label, fg, bg in BANDS:
        if pct >= threshold:
            return label, fg, bg
    return "ABUNDANT", "#22d3ee", "rgba(34,211,238,0.18)"


def _fmt(v, dec=1, unit="") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    formatted = f"{v:,.{dec}f}"
    return formatted + unit if unit else formatted


# ── Chart factories ───────────────────────────────────────────────────────────
def make_map(df: pd.DataFrame, selected_iso: str, metric: str) -> go.Figure:
    col = "withdrawal_pct" if metric == "Withdrawal %" else "withdrawal_cap"
    label_map = {
        "withdrawal_pct": "Withdrawal<br>% of available",
        "withdrawal_cap": "Withdrawal<br>m³/capita",
    }
    plot_df = df.dropna(subset=[col])
    cmax = max(plot_df[col].quantile(0.95), 1) if not plot_df.empty else 100

    fig = px.choropleth(
        plot_df,
        locations="iso",
        locationmode="ISO-3",
        color=col,
        color_continuous_scale=CSCALE,
        range_color=[0, cmax],
        hover_name="country_name",
        hover_data={col: ":.1f", "iso": False},
        labels={col: label_map[col]},
    )

    fig.update_geos(
        bgcolor="#05050a",
        landcolor="#0d0d1a",
        oceancolor="#060a0f",
        lakecolor="#060a0f",
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#1e1e30",
        coastlinewidth=0.5,
        showland=True,
        showocean=True,
        showlakes=True,
        projection_type="natural earth",
    )

    # White outline for selected country
    if selected_iso and selected_iso in df["iso"].values:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso],
            locationmode="ISO-3",
            z=[1],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False,
            marker_line_color="#ffffff",
            marker_line_width=1.8,
            hoverinfo="skip",
        ))

    fig.update_layout(
        paper_bgcolor="#05050a",
        plot_bgcolor="#05050a",
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(
            title=dict(text=label_map[col], font=dict(color="#3a3a52", size=9)),
            tickfont=dict(color="#3a3a52", size=9),
            bgcolor="rgba(8,8,15,0.7)",
            borderwidth=0,
            thickness=10,
            len=0.38,
            x=0.99,
        ),
        geo=dict(bgcolor="#05050a"),
        dragmode=False,
    )
    return fig


def make_trend_chart(trend_df: pd.DataFrame, country_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend_df["year"],
        y=trend_df["value"],
        mode="lines+markers",
        line=dict(color="#60a5fa", width=2),
        marker=dict(color="#60a5fa", size=5),
        fill="tozeroy",
        fillcolor="rgba(96,165,250,0.06)",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))
    # UN stress thresholds
    for y_val, txt, col in [
        (40, "High stress threshold (40%)", "#f97316"),
        (80, "Critical threshold (80%)",    "#ef4444"),
    ]:
        if y_val <= trend_df["value"].max() * 1.2:
            fig.add_hline(
                y=y_val, line_dash="dot", line_color=col, line_width=1,
                annotation_text=txt, annotation_font_color=col,
                annotation_font_size=10, annotation_position="top right",
            )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#080810",
        font=dict(color="#9898a8", size=11),
        title=dict(
            text=f"{country_name} — Freshwater Withdrawal since 1990",
            font=dict(color="#c8c8d4", size=13),
            x=0.01,
        ),
        xaxis=dict(gridcolor="#14142a", color="#3a3a52", showline=False, zeroline=False,
                   tickformat="d"),
        yaxis=dict(gridcolor="#14142a", color="#3a3a52", showline=False, zeroline=False,
                   title="% of available freshwater", title_font=dict(color="#3a3a52", size=10)),
        margin=dict(l=10, r=30, t=50, b=10),
        showlegend=False,
    )
    return fig


# ── HTML builders ─────────────────────────────────────────────────────────────
def _sector_bars(agri, ind, dom) -> str:
    sectors = [
        ("Agriculture", agri, "#22d3ee"),
        ("Industry",    ind,  "#60a5fa"),
        ("Municipal",   dom,  "#a78bfa"),
    ]
    rows = []
    for name, val, colour in sectors:
        w    = f"{min(val or 0, 100):.1f}%"
        disp = f"{val:.0f}%" if (val is not None and not pd.isna(val)) else "—"
        rows.append(f"""
<div class="sector-row">
  <div class="sector-label-row"><span>{name}</span><span>{disp}</span></div>
  <div class="sector-track"><div class="sector-fill" style="width:{w};background:{colour}"></div></div>
</div>""")
    return "\n".join(rows)


def _country_panel(r: pd.Series) -> str:
    label, fg, bg = stress_band(r.withdrawal_pct)
    over  = r.withdrawal_pct > 100
    warn  = '<br><span class="overflow-warn">⚠ Drawing down fossil groundwater</span>' if over else ""
    cells = [
        ("Withdrawal",  _fmt(r.withdrawal_pct, 1), "%"),
        ("Per Capita",  _fmt(r.withdrawal_cap, 0), "m³"),
        ("Freshwater",  _fmt(r.freshwater_cap, 0), "m³/cap"),
        ("Safe Access", _fmt(r.safe_access,    1), "%"),
    ]
    grid_html = "".join(f"""
<div>
  <div class="metric-label">{n}</div>
  <div class="metric-value">{v}<span class="metric-unit">{u}</span></div>
</div>""" for n, v, u in cells)

    return f"""
<div class="country-heading">{r.country_name}</div>
<div class="stress-badge" style="background:{bg};color:{fg}">
  <div class="stress-dot" style="background:{fg}"></div>{label}
</div>
{warn}
<div class="metrics-grid">{grid_html}</div>"""


# ── App ────────────────────────────────────────────────────────────────────────
st.markdown(CSS, unsafe_allow_html=True)

# Data
with st.spinner("Loading freshwater data…"):
    df = load_water_data()
    names = load_country_names()

df["country_name"] = df["iso"].map(names).fillna(df["iso"])
iso_to_name = dict(zip(df["iso"], df["country_name"]))
name_to_iso = {v: k for k, v in iso_to_name.items()}
iso_list = sorted(iso_to_name.values())

# Session state
if "iso" not in st.session_state:
    st.session_state.iso = st.query_params.get("iso", "IND")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="day-label">Day 03 · Resilience Stack</div>', unsafe_allow_html=True)
    st.markdown("## Water Stress")
    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    # Country search
    current_name = iso_to_name.get(st.session_state.iso, st.session_state.iso)
    idx = iso_list.index(current_name) if current_name in iso_list else 0
    chosen = st.selectbox("", iso_list, index=idx, label_visibility="collapsed")
    chosen_iso = name_to_iso.get(chosen, st.session_state.iso)
    if chosen_iso != st.session_state.iso:
        st.session_state.iso = chosen_iso
        st.query_params["iso"] = chosen_iso
        st.rerun()

    # Metric toggle
    metric = st.radio("Colour map by", ["Withdrawal %", "Per Capita m³"],
                      horizontal=True, label_visibility="collapsed")

    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    # Country data panel
    iso = st.session_state.iso
    row_df = df[df["iso"] == iso]
    if not row_df.empty:
        r = row_df.iloc[0]
        # Fallback: compute municipal if missing
        if (r.domestic_share is None or pd.isna(r.domestic_share)) \
                and r.agri_share is not None and r.industry_share is not None:
            r = r.copy()
            r["domestic_share"] = max(0.0, 100.0 - r.agri_share - r.industry_share)

        st.markdown(_country_panel(r), unsafe_allow_html=True)
        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        st.markdown('<div class="metric-label">Sector Breakdown</div>', unsafe_allow_html=True)
        st.markdown(_sector_bars(r.agri_share, r.industry_share, r.domestic_share),
                    unsafe_allow_html=True)
        st.caption("Agriculture accounts for ~70% of global freshwater withdrawals")

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="data-footer">Data as of {r.year}<br>'
            'Source: World Bank</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="metric-label">No data available</div>', unsafe_allow_html=True)

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    st.markdown(
        '<div class="data-footer">'
        '→ Day 01: Grid Stress Map<br>'
        '→ Day 04: Food Fragility (coming soon)'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Main: full-width map ──────────────────────────────────────────────────────
fig = make_map(df, st.session_state.iso, metric)
event = st.plotly_chart(
    fig,
    on_select="rerun",
    use_container_width=True,
    config={"displayModeBar": False, "scrollZoom": True},
    key="wmap",
)

# Handle click
if event and event.selection and event.selection.get("points"):
    clicked_iso = event.selection["points"][0].get("location")
    if clicked_iso and clicked_iso != st.session_state.iso:
        st.session_state.iso = clicked_iso
        st.query_params["iso"] = clicked_iso
        st.rerun()

# ── Below map: tabs ───────────────────────────────────────────────────────────
st.markdown("<div style='padding: 0 20px'>", unsafe_allow_html=True)
tab1, tab2 = st.tabs(["  Trend since 1990  ", "  Most Stressed Countries  "])

with tab1:
    iso = st.session_state.iso
    country_name = iso_to_name.get(iso, iso)
    with st.spinner("Loading trend data…"):
        trend = load_country_trend(iso)
    if trend.empty:
        st.markdown(
            f"<div style='color:#3a3a52;font-size:13px;padding:24px 0'>"
            f"No historical trend data available for <b>{country_name}</b>.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.plotly_chart(
            make_trend_chart(trend, country_name),
            use_container_width=True,
            config={"displayModeBar": False},
        )

with tab2:
    top20 = (
        df.nlargest(20, "withdrawal_pct")
        [["country_name", "withdrawal_pct", "agri_share", "industry_share",
          "domestic_share", "year"]]
        .copy()
    )
    top20.rename(columns={
        "country_name":   "Country",
        "withdrawal_pct": "Withdrawal %",
        "agri_share":     "Agriculture %",
        "industry_share": "Industry %",
        "domestic_share": "Municipal %",
        "year":           "Data Year",
    }, inplace=True)

    def _pct_fmt(x):
        return f"{x:.1f}%" if pd.notna(x) else "—"

    for col in ["Withdrawal %", "Agriculture %", "Industry %", "Municipal %"]:
        top20[col] = top20[col].apply(_pct_fmt)

    top20 = top20.reset_index(drop=True)
    top20.index += 1
    st.dataframe(top20, use_container_width=True, height=480)

st.markdown("</div>", unsafe_allow_html=True)
