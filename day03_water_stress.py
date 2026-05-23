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

/* Sidebar dark panel */
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

/* Hide chrome */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* Selectbox / radio dark */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] input {
    background: #0d0d1a !important;
    border-color: #1a1a2e !important;
    color: #c8c8d4 !important;
}

/* ── Metric grid ── */
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
.benchmark {
    display: block;
    font-size: 9px;
    color: #2a2a42;
    letter-spacing: 0.03em;
    margin-top: 3px;
    line-height: 1.4;
}
.bench-up   { color: #ef4444; }
.bench-down { color: #22d3ee; }

/* ── Stress badge ── */
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
    margin-bottom: 10px;
}
.stress-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ── Story card ── */
.story-card {
    font-size: 12px;
    line-height: 1.85;
    color: #7070888;
    margin-bottom: 16px;
    color: #6868808;
}
.story-card {
    font-size: 12.5px;
    line-height: 1.8;
    color: #686880;
    margin-bottom: 16px;
}

/* ── Fossil water reveal panel ── */
.fossil-reveal {
    border-left: 2px solid #f97316;
    background: rgba(249,115,22,0.05);
    padding: 12px 14px;
    margin: 10px 0 14px;
    border-radius: 0 3px 3px 0;
}
.fossil-title {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #f97316;
    margin-bottom: 7px;
}
.fossil-body {
    font-size: 11.5px;
    line-height: 1.75;
    color: #686868;
}
.fossil-stat {
    font-size: 11px;
    color: #f97316;
    margin-top: 8px;
    letter-spacing: 0.02em;
}

/* ── Sector bars ── */
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
.agri-callout {
    font-size: 11px;
    color: #3a3a52;
    line-height: 1.6;
    margin-top: 12px;
    font-style: italic;
}

/* ── Global stats strip ── */
.stats-strip {
    display: flex;
    gap: 0;
    border-bottom: 1px solid #14142a;
    padding: 14px 24px;
    background: #05050a;
}
.stat-item {
    flex: 1;
    padding-right: 24px;
    border-right: 1px solid #14142a;
    margin-right: 24px;
}
.stat-item:last-child {
    border-right: none;
    margin-right: 0;
    padding-right: 0;
}
.stat-n {
    font-size: 26px;
    font-weight: 700;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    line-height: 1.1;
    margin-bottom: 3px;
}
.stat-l {
    font-size: 9px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #2a2a42;
    line-height: 1.4;
}

/* ── Separator ── */
.sep {
    border: none;
    border-top: 1px solid #14142a;
    margin: 18px 0;
}
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
.data-footer {
    font-size: 10px;
    color: #2a2a42;
    letter-spacing: 0.04em;
    line-height: 2.0;
}

/* ── Tabs ── */
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
[data-testid="stDataFrame"] { background: transparent !important; }
</style>
"""

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def _fetch_indicator(code: str) -> dict[str, tuple[float, str]]:
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


def global_stats(df: pd.DataFrame) -> dict:
    critical = int((df["withdrawal_pct"] >= 80).sum())
    fossil   = int((df["withdrawal_pct"] >= 100).sum())
    avg      = float(df["withdrawal_pct"].mean())
    top      = df.nlargest(1, "withdrawal_pct").iloc[0]
    avgs = {
        "withdrawal_pct": avg,
        "withdrawal_cap": float(df["withdrawal_cap"].dropna().mean()),
        "freshwater_cap": float(df["freshwater_cap"].dropna().mean()),
        "safe_access":    float(df["safe_access"].dropna().mean()),
    }
    return {
        "critical_count": critical,
        "fossil_count":   fossil,
        "global_avg":     avg,
        "top_name":       top["country_name"],
        "top_pct":        float(top["withdrawal_pct"]),
        "avgs":           avgs,
    }


def country_story(r: pd.Series, rank: int, global_avg: float) -> str:
    pct  = r.withdrawal_pct
    name = r.country_name

    # Opening line — stress-level framing
    if pct > 100:
        opening = (f"{name} withdraws {pct:.0f}% of its renewable freshwater — "
                   f"far more than nature replenishes each year.")
    elif pct > 80:
        opening = (f"With {pct:.0f}% of its renewable supply already in use, "
                   f"{name} is in critical water stress — one of the most "
                   f"water-pressured countries on Earth.")
    elif pct > 40:
        opening = (f"{name} draws {pct:.0f}% of its renewable supply, crossing "
                   f"the UN high-stress threshold of 40%.")
    elif pct > 20:
        opening = (f"{name} is under moderate water pressure, using "
                   f"{pct:.0f}% of its renewable freshwater.")
    elif pct > 5:
        opening = (f"{name} uses {pct:.1f}% of its renewable freshwater — "
                   f"relatively modest compared to water-stressed regions.")
    else:
        opening = (f"{name} has exceptional water abundance, drawing just "
                   f"{pct:.1f}% of its renewable supply.")

    # Middle — sector or multiplier angle
    agri = r.agri_share
    agri_ok = agri is not None and not pd.isna(agri)
    mult = pct / global_avg if global_avg > 0 else 1.0

    if agri_ok and agri > 85:
        middle = (f"Nearly all withdrawals — {agri:.0f}% — go to agriculture, "
                  f"typical of arid farming economies.")
    elif agri_ok and agri < 35:
        middle = (f"Unusually, farming accounts for only {agri:.0f}% of withdrawals; "
                  f"industry and urban demand lead.")
    elif mult >= 3:
        middle = f"That's {mult:.1f}× the world average of {global_avg:.0f}%."
    elif mult <= 0.25:
        middle = (f"The world average is {global_avg:.0f}% — "
                  f"{name} uses a fraction of that.")
    else:
        middle = f"The global average for comparison is {global_avg:.0f}%."

    # End — rank
    end = f"Ranked #{rank} globally by water stress."

    return f"{opening} {middle} {end}"


def threshold_crossings(trend_df: pd.DataFrame) -> dict[str, int]:
    """Return {label: first_year_crossed} for HIGH (40%) and CRITICAL (80%)."""
    if trend_df.empty:
        return {}
    crossings: dict[str, int] = {}
    df_s = trend_df.sort_values("year")
    for threshold, label in [(40, "HIGH"), (80, "CRITICAL")]:
        prev_below = False
        for _, row in df_s.iterrows():
            if row["value"] < threshold:
                prev_below = True
            elif prev_below and row["value"] >= threshold:
                crossings[label] = int(row["year"])
                break
    return crossings


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
        bgcolor="#05050a", landcolor="#0d0d1a",
        oceancolor="#060a0f", lakecolor="#060a0f",
        showframe=False, showcoastlines=True,
        coastlinecolor="#1e1e30", coastlinewidth=0.5,
        showland=True, showocean=True, showlakes=True,
        projection_type="natural earth",
    )
    if selected_iso and selected_iso in df["iso"].values:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso], locationmode="ISO-3",
            z=[1], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, marker_line_color="#ffffff",
            marker_line_width=1.8, hoverinfo="skip",
        ))
    fig.update_layout(
        paper_bgcolor="#05050a", plot_bgcolor="#05050a",
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(
            title=dict(text=label_map[col], font=dict(color="#3a3a52", size=9)),
            tickfont=dict(color="#3a3a52", size=9),
            bgcolor="rgba(8,8,15,0.7)", borderwidth=0,
            thickness=10, len=0.38, x=0.99,
        ),
        geo=dict(bgcolor="#05050a"),
        dragmode=False,
    )
    return fig


def make_trend_chart(
    trend_df: pd.DataFrame,
    country_name: str,
    crossings: dict[str, int] | None = None,
) -> go.Figure:
    crossings = crossings or {}
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["value"],
        mode="lines+markers",
        line=dict(color="#60a5fa", width=2),
        marker=dict(color="#60a5fa", size=5),
        fill="tozeroy", fillcolor="rgba(96,165,250,0.06)",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))

    max_val = trend_df["value"].max()

    # UN thresholds
    for y_val, txt, col in [
        (40, "High stress (40%)", "#f97316"),
        (80, "Critical (80%)",    "#ef4444"),
    ]:
        if y_val <= max_val * 1.2:
            fig.add_hline(
                y=y_val, line_dash="dot", line_color=col, line_width=1,
                annotation_text=txt, annotation_font_color=col,
                annotation_font_size=10, annotation_position="top right",
            )

    # Threshold crossing vertical markers
    cross_colours = {"HIGH": "#f97316", "CRITICAL": "#ef4444"}
    for label, yr in crossings.items():
        col = cross_colours.get(label, "#aaaaaa")
        fig.add_vline(
            x=yr, line_dash="dot", line_color=col, line_width=1.2,
        )
        fig.add_annotation(
            x=yr, y=max_val * 0.92,
            text=f"← Crossed {label} ({yr})",
            showarrow=False,
            font=dict(color=col, size=10),
            xanchor="left", yanchor="top",
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080810",
        font=dict(color="#9898a8", size=11),
        title=dict(
            text=f"{country_name} — Freshwater Withdrawal since 1990",
            font=dict(color="#c8c8d4", size=13), x=0.01,
        ),
        xaxis=dict(gridcolor="#14142a", color="#3a3a52",
                   showline=False, zeroline=False, tickformat="d"),
        yaxis=dict(gridcolor="#14142a", color="#3a3a52",
                   showline=False, zeroline=False,
                   title="% of available freshwater",
                   title_font=dict(color="#3a3a52", size=10)),
        margin=dict(l=10, r=30, t=50, b=10),
        showlegend=False,
    )
    return fig


# ── HTML builders ─────────────────────────────────────────────────────────────
def _benchmark_span(val, avg, higher_is_worse=True) -> str:
    """Small comparison text: 'vs. world avg X%'."""
    if val is None or avg is None or pd.isna(val) or pd.isna(avg) or avg == 0:
        return ""
    ratio = val / avg
    if ratio >= 2:
        cls  = "bench-up" if higher_is_worse else "bench-down"
        txt  = f"↑ {ratio:.1f}× world avg ({avg:,.0f})"
    elif ratio <= 0.5:
        cls  = "bench-down" if higher_is_worse else "bench-up"
        txt  = f"↓ {ratio:.1f}× world avg ({avg:,.0f})"
    else:
        cls  = ""
        txt  = f"world avg {avg:,.0f}"
    return f'<span class="benchmark {cls}">{txt}</span>'


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
  <div class="sector-track">
    <div class="sector-fill" style="width:{w};background:{colour}"></div>
  </div>
</div>""")
    return "\n".join(rows)


def _agri_callout(agri, country_name: str) -> str:
    if agri is None or pd.isna(agri):
        return "Agriculture accounts for ~70% of global freshwater withdrawals."
    if agri > 90:
        return (f"{country_name} is exceptionally agriculture-dependent — "
                f"9 in 10 litres go to crops.")
    if agri > 70:
        return (f"Agriculture dominates at {agri:.0f}% — above the global average of 70%.")
    if agri < 35:
        return (f"Unusually, industry and urban use outweigh farming here — "
                f"agriculture is just {agri:.0f}% of withdrawals.")
    return f"Agriculture takes {agri:.0f}% of withdrawals — the global average is 70%."


def _country_panel(r: pd.Series, rank: int, avgs: dict) -> str:
    pct         = r.withdrawal_pct
    label, fg, bg = stress_band(pct)
    story_text  = country_story(r, rank, avgs["withdrawal_pct"])

    # Fossil water reveal panel
    if pct > 100:
        excess = pct - 100
        fossil_html = f"""
<div class="fossil-reveal">
  <div class="fossil-title">⚠ Mining Ancient Water</div>
  <div class="fossil-body">This country withdraws more water than nature
  replenishes each year. The deficit is drawn from fossil aquifers —
  groundwater reserves that formed over thousands of years. Once
  depleted, they cannot refill on any human timescale.</div>
  <div class="fossil-stat">Drawing {excess:.0f}% over the annual recharge rate</div>
</div>"""
    else:
        fossil_html = ""

    # Metric cells with benchmark anchors
    cells = [
        ("Withdrawal",  _fmt(pct, 1),            "%",
         _benchmark_span(pct, avgs["withdrawal_pct"], higher_is_worse=True)),
        ("Per Capita",  _fmt(r.withdrawal_cap, 0), "m³",
         _benchmark_span(r.withdrawal_cap, avgs["withdrawal_cap"], higher_is_worse=True)),
        ("Freshwater",  _fmt(r.freshwater_cap, 0), "m³/cap",
         _benchmark_span(r.freshwater_cap, avgs["freshwater_cap"], higher_is_worse=False)),
        ("Safe Access", _fmt(r.safe_access, 1),    "%",
         _benchmark_span(r.safe_access, avgs["safe_access"], higher_is_worse=False)),
    ]
    grid_html = "".join(f"""
<div>
  <div class="metric-label">{n}</div>
  <div class="metric-value">{v}<span class="metric-unit">{u}</span></div>
  {bench}
</div>""" for n, v, u, bench in cells)

    return f"""
<div class="country-heading">{r.country_name}</div>
<div class="stress-badge" style="background:{bg};color:{fg}">
  <div class="stress-dot" style="background:{fg}"></div>{label}
</div>
<div class="story-card">{story_text}</div>
{fossil_html}
<div class="metrics-grid">{grid_html}</div>"""


def _stats_strip(gs: dict) -> str:
    items = [
        (f"{gs['critical_count']}",        "countries in critical stress (&gt;80%)",  "#ef4444"),
        (f"{gs['fossil_count']}",           "drawing down fossil groundwater (&gt;100%)", "#f97316"),
        (f"{gs['global_avg']:.0f}%",        "global average withdrawal",               "#60a5fa"),
        (gs["top_name"],
         f"most stressed &mdash; {gs['top_pct']:.0f}%",                               "#a78bfa"),
    ]
    parts = "".join(f"""
<div class="stat-item">
  <div class="stat-n" style="color:{c}">{n}</div>
  <div class="stat-l">{l}</div>
</div>""" for n, l, c in items)
    return f'<div class="stats-strip">{parts}</div>'


# ── App ────────────────────────────────────────────────────────────────────────
st.markdown(CSS, unsafe_allow_html=True)

with st.spinner("Loading freshwater data…"):
    df = load_water_data()
    names = load_country_names()

df["country_name"] = df["iso"].map(names).fillna(df["iso"])
iso_to_name = dict(zip(df["iso"], df["country_name"]))
name_to_iso = {v: k for k, v in iso_to_name.items()}
iso_list    = sorted(iso_to_name.values())

# Global stats — computed once, used in strip + panel
gs   = global_stats(df)
avgs = gs["avgs"]

# Rank lookup (1 = most stressed)
rank_series = df["withdrawal_pct"].rank(ascending=False, method="min").astype(int)
iso_to_rank = dict(zip(df["iso"], rank_series))

if "iso" not in st.session_state:
    st.session_state.iso = st.query_params.get("iso", "IND")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="day-label">Day 03 · Resilience Stack</div>',
                unsafe_allow_html=True)
    st.markdown("## Water Stress")
    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    current_name = iso_to_name.get(st.session_state.iso, st.session_state.iso)
    idx = iso_list.index(current_name) if current_name in iso_list else 0
    chosen = st.selectbox("", iso_list, index=idx, label_visibility="collapsed")
    chosen_iso = name_to_iso.get(chosen, st.session_state.iso)
    if chosen_iso != st.session_state.iso:
        st.session_state.iso = chosen_iso
        st.query_params["iso"] = chosen_iso
        st.rerun()

    metric = st.radio("Colour map by", ["Withdrawal %", "Per Capita m³"],
                      horizontal=True, label_visibility="collapsed")

    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    iso     = st.session_state.iso
    row_df  = df[df["iso"] == iso]

    if not row_df.empty:
        r = row_df.iloc[0].copy()
        # Derive municipal if missing
        if (pd.isna(r.domestic_share) or r.domestic_share is None) \
                and not pd.isna(r.agri_share) and not pd.isna(r.industry_share):
            r["domestic_share"] = max(0.0, 100.0 - r.agri_share - r.industry_share)

        rank = iso_to_rank.get(iso, 0)
        st.markdown(_country_panel(r, rank, avgs), unsafe_allow_html=True)
        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        st.markdown('<div class="metric-label">Sector Breakdown</div>',
                    unsafe_allow_html=True)
        st.markdown(
            _sector_bars(r.agri_share, r.industry_share, r.domestic_share),
            unsafe_allow_html=True,
        )
        callout = _agri_callout(r.agri_share, r.country_name)
        st.markdown(f'<div class="agri-callout">{callout}</div>',
                    unsafe_allow_html=True)

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="data-footer">Data as of {r.year}<br>Source: World Bank</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="metric-label">No data available for this country</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    st.markdown(
        '<div class="data-footer">'
        '→ Day 01: Grid Stress Map<br>'
        '→ Day 04: Food Fragility (coming soon)'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Main: stats strip + full-width map ───────────────────────────────────────
st.markdown(_stats_strip(gs), unsafe_allow_html=True)

fig = make_map(df, st.session_state.iso, metric)
event = st.plotly_chart(
    fig,
    on_select="rerun",
    use_container_width=True,
    config={"displayModeBar": False, "scrollZoom": True},
    key="wmap",
)

if event and event.selection and event.selection.get("points"):
    clicked_iso = event.selection["points"][0].get("location")
    if clicked_iso and clicked_iso != st.session_state.iso:
        st.session_state.iso = clicked_iso
        st.query_params["iso"] = clicked_iso
        st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
st.markdown("<div style='padding: 0 20px'>", unsafe_allow_html=True)
tab1, tab2 = st.tabs(["  Trend since 1990  ", "  Most Stressed Countries  "])

with tab1:
    iso          = st.session_state.iso
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
        crossings = threshold_crossings(trend)
        st.plotly_chart(
            make_trend_chart(trend, country_name, crossings),
            use_container_width=True,
            config={"displayModeBar": False},
        )

with tab2:
    top20 = (
        df.nlargest(20, "withdrawal_pct")
        [["country_name", "withdrawal_pct", "agri_share",
          "industry_share", "domestic_share", "year"]]
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
