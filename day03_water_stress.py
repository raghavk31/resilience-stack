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
    "withdrawal_pct":  "ER.H2O.FWTL.ZS",
    "withdrawal_cap":  "ER.H2O.FWST.ZS",
    "freshwater_cap":  "ER.H2O.INTR.PC",
    "safe_access":     "SH.H2O.BASW.ZS",
    "agri_share":      "ER.H2O.FWAG.ZS",
    "industry_share":  "ER.H2O.FWIN.ZS",
    "domestic_share":  "ER.H2O.FWDM.ZS",
}

BANDS = [
    (80, "CRITICAL", "#ef4444", "rgba(239,68,68,0.10)"),
    (40, "HIGH",     "#f97316", "rgba(249,115,22,0.10)"),
    (20, "MEDIUM",   "#eab308", "rgba(234,179,8,0.10)"),
    (10, "LOW-MED",  "#3b82f6", "rgba(59,130,246,0.10)"),
    ( 0, "ABUNDANT", "#06b6d4", "rgba(6,182,212,0.10)"),
]

CSCALE = [
    (0.00, "#06b6d4"),
    (0.15, "#3b82f6"),
    (0.35, "#8b5cf6"),
    (0.55, "#eab308"),
    (0.75, "#f97316"),
    (1.00, "#ef4444"),
]

COLOR_CAP = 150

FW_THRESHOLDS = [
    (500,  "absolute scarcity", "#ef4444"),
    (1000, "scarcity",          "#f97316"),
    (1700, "stress",            "#eab308"),
]

FOSSIL_STORIES = {
    "EGY": ("Egypt's figure reflects near-total dependence on the Nile, which "
            "originates outside its borders and provides ~97% of its water. "
            "Beneath the western desert, fossil Nubian Sandstone Aquifer water "
            "is also being mined — formed over 20,000 years ago."),
    "BHR": ("Bahrain has no rivers and barely any rain. Every drop comes from "
            "desalination plants or shared fossil aquifers beneath the Gulf — "
            "resources with no meaningful natural recharge rate."),
    "SAU": ("Saudi Arabia built its green revolution on the Great Artesian fossil "
            "aquifer. That water is now largely depleted; the kingdom has largely "
            "abandoned domestic wheat farming and pivoted to food imports."),
    "ARE": ("The UAE meets demand through among the world's most energy-intensive "
            "desalination infrastructure. Freshwater is effectively manufactured "
            "from seawater — at enormous carbon cost."),
    "LBY": ("Libya's Great Man-Made River pumps ancient Saharan aquifer water "
            "1,000 km north to coastal cities. At current rates, reserves are "
            "estimated to last 60–100 years before collapse."),
    "TKM": ("Soviet-era cotton irrigation in Turkmenistan diverted the Amu Darya "
            "so aggressively that the Aral Sea — once Earth's 4th largest lake — "
            "has almost entirely disappeared."),
    "PAK": ("Pakistan's Indus basin faces converging crises: glacial melt, "
            "monsoon variability, and rapid groundwater depletion — high "
            "withdrawal coexists with catastrophic seasonal water insecurity."),
    "SDN": ("Sudan draws heavily on Nile tributaries and fossil groundwater. "
            "Contested with Ethiopia over the Grand Renaissance Dam, its water "
            "future is as much geopolitical as it is hydrological."),
}

# fill level per stress band for the water drop icon
BAND_DROP_FILL = {
    "CRITICAL": 1.00,
    "HIGH":     0.72,
    "MEDIUM":   0.50,
    "LOW-MED":  0.30,
    "ABUNDANT": 0.12,
}

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

:root {
  --bg:       #f5f7fa;
  --surface:  #ffffff;
  --glass:    rgba(255,255,255,0.82);
  --glass-b:  rgba(0,0,0,0.07);
  --text-1:   #0f172a;
  --text-2:   #475569;
  --text-3:   #94a3b8;
  --accent:   #0ea5e9;
  --sh-sm:    0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);
  --sh-md:    0 4px 16px rgba(0,0,0,0.08);
  --r:        10px;
}

/* ── Page ── */
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  background: var(--bg) !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--text-2) !important;
}
.main .block-container {
  padding-top: 8px !important;
  padding-bottom: 12px !important;
  max-width: 100% !important;
  padding-left: 14px !important;
  padding-right: 14px !important;
}
#MainMenu, footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* ── Sidebar glass panel ── */
[data-testid="stSidebar"] {
  background: var(--glass) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--glass-b) !important;
  box-shadow: 4px 0 24px rgba(0,0,0,0.05) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding: 22px 18px 28px !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {
  color: var(--text-2) !important;
  font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] h2 {
  color: var(--text-1) !important;
  font-size: 18px !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
  margin: 4px 0 0 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] input {
  background: rgba(255,255,255,0.95) !important;
  border-color: #e2e8f0 !important;
  color: var(--text-1) !important;
}

/* ── Metrics grid ── */
.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 10px 0;
}
.metric-card {
  background: var(--surface);
  border: 1px solid var(--glass-b);
  border-radius: 8px;
  padding: 10px 11px;
  box-shadow: var(--sh-sm);
  animation: fadeSlideUp 0.3s ease both;
}
.metric-label {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 3px;
}
.metric-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}
.metric-unit {
  font-size: 10px;
  color: var(--text-3);
  font-weight: 400;
  margin-left: 2px;
}
.benchmark {
  display: block;
  font-size: 9px;
  color: var(--text-3);
  letter-spacing: 0.02em;
  margin-top: 2px;
  line-height: 1.4;
}
.bench-up   { color: #ef4444; }
.bench-down { color: #06b6d4; }
.bench-fw   { color: #f97316; font-style: italic; }

/* ── Country heading & drop badge ── */
.country-heading {
  font-size: 17px; font-weight: 600;
  color: var(--text-1); letter-spacing: -0.01em;
  line-height: 1.25; margin-bottom: 6px;
}
.drop-badge {
  display: flex; align-items: center; gap: 8px;
  margin: 2px 0 10px;
}
.drop-band-label {
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--text-3);
}
/* Legacy badge kept for compare tab */
.stress-badge {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 4px 10px 4px 8px; border-radius: 4px;
  font-size: 10px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  margin-top: 4px; margin-bottom: 8px;
}
.stress-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.stress-dot-critical { animation: pulseDot 2s ease infinite; }

/* ── Water tank ── */
.tank-outer {
  display: flex; flex-direction: column;
  align-items: center; margin: 2px 0 12px;
}
.tank-body-wrap {
  position: relative;
  padding-top: 14px;
}
.tank-wrap {
  position: relative;
  width: 90px; height: 70px;
  border: 2px solid #d0d8e4;
  border-top: 3px solid #b0bec8;
  border-radius: 4px 4px 10px 10px;
  background: #f8fafc;
  overflow: hidden;
}
.tank-water {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: var(--fill-pct);
  transform: scaleY(0);
  transform-origin: bottom;
  animation: fillWater 1s ease-out forwards;
  border-radius: 0 0 8px 8px;
}
.tank-critical .tank-water {
  animation: fillWater 1s ease-out forwards, pulseFill 2s 1.1s ease infinite;
}
.tank-pct {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-family: 'Inter', sans-serif;
  font-size: 14px; font-weight: 700;
  color: var(--text-1); z-index: 10;
  text-shadow: 0 0 6px rgba(255,255,255,0.95);
}
.overflow-drop {
  position: absolute;
  top: 3px;
  width: 5px; height: 10px;
  border-radius: 50% 50% 50% 50% / 40% 40% 60% 60%;
  animation: dropFall 1.3s var(--delay,0s) ease-in infinite;
  z-index: 20;
}
.tank-label {
  font-size: 9px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--text-3);
  margin-top: 5px;
}

/* ── Story card ── */
.story-card {
  font-size: 12px; line-height: 1.8;
  color: var(--text-2); margin-bottom: 10px;
  background: var(--surface);
  border: 1px solid var(--glass-b);
  border-radius: 8px; padding: 10px 12px;
  animation: fadeSlideUp 0.35s 0.08s ease both;
  box-shadow: var(--sh-sm);
}

/* ── Fossil reveal ── */
.fossil-reveal {
  border-left: 3px solid #f97316;
  border: 1px solid rgba(249,115,22,0.25);
  border-left-width: 3px;
  background: rgba(249,115,22,0.04);
  padding: 11px 13px;
  margin: 0 0 10px;
  border-radius: 0 6px 6px 0;
  animation: shake 0.45s ease both;
}
.fossil-title {
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: #ea580c; margin-bottom: 6px;
}
.fossil-body { font-size: 11px; line-height: 1.75; color: #78716c; }
.fossil-stat {
  font-size: 11px; color: #ea580c;
  margin-top: 7px; font-weight: 500;
}

/* ── Sector bars ── */
.sector-row { margin-bottom: 10px; }
.sector-label-row {
  display: flex; justify-content: space-between;
  font-size: 10px; letter-spacing: 0.05em;
  text-transform: uppercase; color: var(--text-3);
  margin-bottom: 5px;
}
.sector-track {
  height: 5px; background: #e2e8f0;
  border-radius: 3px; overflow: hidden;
}
.sector-fill {
  height: 5px; border-radius: 3px;
  transform: scaleX(0); transform-origin: left;
  animation: barGrow 0.8s ease-out forwards;
}
.agri-callout {
  font-size: 11px; color: var(--text-3);
  line-height: 1.6; margin-top: 8px; font-style: italic;
}

/* ── Stats strip ── */
.strip-row {
  display: flex; gap: 8px;
  margin: 4px 0 6px; padding: 0 2px;
}
.strip-card {
  flex: 1; min-width: 0;
  background: var(--glass);
  border: 1px solid var(--glass-b);
  border-radius: var(--r);
  padding: 11px 13px;
  box-shadow: var(--sh-sm);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  animation: fadeSlideUp 0.4s ease both;
  cursor: default;
}
.strip-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--sh-md);
}
.strip-icon { margin-bottom: 5px; }
.strip-n {
  font-size: 21px; font-weight: 300;
  font-family: 'Inter', sans-serif;
  color: var(--accent); line-height: 1.1;
  margin-bottom: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.strip-l {
  font-size: 9px; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--text-3);
  line-height: 1.4;
}

/* ── Intro card ── */
.intro-card {
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(14,165,233,0.18);
  border-radius: var(--r);
  padding: 16px 20px;
  margin: 4px 0 10px;
  animation: slideDown 0.4s ease both;
  box-shadow: 0 2px 14px rgba(14,165,233,0.07);
}
.intro-inner { display: flex; align-items: center; gap: 18px; }
.intro-text  { flex: 1; }
.intro-heading {
  font-size: 14px; font-weight: 600;
  color: var(--text-1); margin: 0 0 5px;
}
.intro-body {
  font-size: 12px; line-height: 1.7;
  color: var(--text-2); margin: 0 0 10px;
}
.intro-callout { display: flex; align-items: baseline; gap: 7px; }
.intro-n { font-size: 22px; font-weight: 600; color: #ef4444; }
.intro-l { font-size: 11px; color: var(--text-3); }
.intro-svg { flex-shrink: 0; opacity: 0.8; }

/* ── Compare race ── */
.race-row {
  display: flex; align-items: flex-end;
  justify-content: center; gap: 24px;
  margin: 14px 0 18px;
}
.race-side {
  display: flex; flex-direction: column;
  align-items: center; gap: 7px;
}
.race-name {
  font-size: 11px; font-weight: 500; color: var(--text-2);
  text-align: center; max-width: 110px;
}
.race-tank-wrap { position: relative; padding-top: 14px; }
.race-tank {
  position: relative; width: 76px; height: 110px;
  border: 2px solid #d0d8e4;
  border-top: 3px solid #b0bec8;
  border-radius: 4px 4px 10px 10px;
  background: #f8fafc; overflow: hidden;
}
.race-water {
  position: absolute; bottom: 0; left: 0; right: 0;
  height: var(--fill-pct);
  transform: scaleY(0); transform-origin: bottom;
  animation: fillWater 1.2s ease-out forwards;
  border-radius: 0 0 8px 8px;
}
.race-pct {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px; font-weight: 700; color: var(--text-1); z-index: 10;
  text-shadow: 0 0 8px rgba(255,255,255,0.95);
}
.race-drop {
  position: absolute; top: 3px;
  width: 5px; height: 10px;
  border-radius: 50% 50% 50% 50% / 40% 40% 60% 60%;
  background: #f97316;
  animation: dropFall 1.3s var(--delay,0s) ease-in infinite;
  z-index: 20;
}
.race-critical .race-water {
  animation: fillWater 1.2s ease-out forwards, pulseFill 2s 1.2s ease infinite;
}
.race-vs {
  font-size: 12px; color: var(--text-3); font-weight: 500;
  align-self: center; margin-bottom: 26px;
}
.race-band {
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
}

/* ── Misc UI ── */
.sep { border: none; border-top: 1px solid #e2e8f0; margin: 13px 0; }
.country-heading-compare { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.radio-label {
  font-size: 9px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--text-3);
  margin-bottom: 4px; display: block;
}
.day-label {
  font-size: 9px; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--text-3);
}
.data-footer {
  font-size: 10px; color: var(--text-3);
  letter-spacing: 0.04em; line-height: 2.0;
}
.stale-note {
  font-size: 10px; color: var(--text-3);
  letter-spacing: 0.03em; padding: 4px 0 0; font-style: italic;
}
.no-data-note {
  font-size: 10px; color: var(--text-3);
  letter-spacing: 0.04em; padding: 2px 4px 6px;
}

/* ── Tabs ── */
button[data-baseweb="tab"] {
  color: var(--text-3) !important;
  font-size: 11px !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  background: transparent !important;
  font-family: 'Inter', sans-serif !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--text-1) !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: #e2e8f0 !important; }
[data-testid="stTabsContent"] { background: transparent !important; padding-top: 10px !important; }
[data-testid="stDataFrame"] { background: transparent !important; }

/* ── Keyframes ── */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fillWater {
  to { transform: scaleY(1); }
}
@keyframes dropFall {
  0%   { top: 2px;  opacity: 1; }
  100% { top: 22px; opacity: 0; }
}
@keyframes pulseDot {
  0%, 100% { transform: scale(1);   opacity: 1; }
  50%       { transform: scale(1.5); opacity: 0.65; }
}
@keyframes pulseFill {
  0%, 100% { opacity: 0.85; }
  50%       { opacity: 0.5; }
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-16px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes shake {
  0%,100% { transform: translateX(0); }
  20%      { transform: translateX(-4px); }
  40%      { transform: translateX(4px); }
  60%      { transform: translateX(-3px); }
  80%      { transform: translateX(2px); }
}
@keyframes barGrow {
  to { transform: scaleX(1); }
}
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


# ── Core helpers ──────────────────────────────────────────────────────────────
def stress_band(pct: float) -> tuple[str, str, str]:
    for threshold, label, fg, bg in BANDS:
        if pct >= threshold:
            return label, fg, bg
    return "ABUNDANT", "#06b6d4", "rgba(6,182,212,0.10)"


def _fmt(v, dec=1, unit="") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    formatted = f"{v:,.{dec}f}"
    return formatted + unit if unit else formatted


def _hex_rgba(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


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
    if pct > 100:
        opening = (f"{name} withdraws {pct:.0f}% of its renewable freshwater — "
                   f"far more than nature replenishes each year.")
    elif pct > 80:
        opening = (f"With {pct:.0f}% of its renewable supply already in use, "
                   f"{name} is in critical water stress.")
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
    agri    = r.agri_share
    agri_ok = agri is not None and not pd.isna(agri)
    mult    = pct / global_avg if global_avg > 0 else 1.0
    if agri_ok and agri > 85:
        middle = f"Nearly all withdrawals — {agri:.0f}% — go to agriculture."
    elif agri_ok and agri < 35:
        middle = (f"Unusually, farming is only {agri:.0f}% of withdrawals; "
                  f"industry and urban demand lead.")
    elif mult >= 3:
        middle = f"That's {mult:.1f}× the world average of {global_avg:.0f}%."
    elif mult <= 0.25:
        middle = (f"The world average is {global_avg:.0f}% — "
                  f"{name} uses a fraction of that.")
    else:
        middle = f"The global average for comparison is {global_avg:.0f}%."
    return f"{opening} {middle} Ranked #{rank} globally."


def threshold_crossings(trend_df: pd.DataFrame) -> dict[str, int]:
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


def detect_stale_trend(trend_df: pd.DataFrame) -> int | None:
    if len(trend_df) < 4:
        return None
    df_s = trend_df.sort_values("year").reset_index(drop=True)
    last_val = round(df_s["value"].iloc[-1], 3)
    flat_mask = df_s["value"].apply(lambda v: round(v, 3) == last_val)
    flat_indices = df_s.index[flat_mask].tolist()
    if len(flat_indices) < 3:
        return None
    if flat_indices[-1] != len(df_s) - 1:
        return None
    run_start = flat_indices[0]
    if flat_mask.iloc[run_start:].all():
        return int(df_s.loc[run_start, "year"])
    return None


def freshwater_threshold_label(val) -> str:
    if val is None or pd.isna(val):
        return ""
    for threshold, label, _ in FW_THRESHOLDS:
        if val < threshold:
            return f"· {label} (<{threshold:,} m³)"
    return "· above stress threshold"


# ── SVG / visual helpers ──────────────────────────────────────────────────────
def water_drop_svg(fill_level: float, color: str, size: int = 26) -> str:
    fill_level = max(0.0, min(1.0, fill_level))
    uid = f"wd{abs(hash((round(fill_level, 2), color, size))) % 99991}"
    clip_y = 26 - 22 * fill_level
    clip_h = 22 * fill_level
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 28" '
        f'fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><clipPath id="{uid}">'
        f'<rect x="0" y="{clip_y:.1f}" width="24" height="{clip_h:.1f}"/>'
        f'</clipPath></defs>'
        f'<path d="M12 3 C12 3 3 13 3 19 A9 9 0 0 0 21 19 C21 13 12 3 12 3Z" '
        f'stroke="{color}" stroke-width="1.5" fill="none"/>'
        f'<path d="M12 3 C12 3 3 13 3 19 A9 9 0 0 0 21 19 C21 13 12 3 12 3Z" '
        f'fill="{color}" clip-path="url(#{uid})" opacity="0.82"/>'
        f'</svg>'
    )


def tank_svg(pct: float, color: str) -> str:
    fill = min(pct, 100)
    is_over = pct > 100
    is_crit = pct >= 80
    light   = _hex_rgba(color, 0.28)
    crit_cls = " tank-critical" if is_crit else ""

    drops = ""
    if is_over:
        for lft, dly in [(18, 0.0), (50, 0.45), (78, 0.9)]:
            drops += (
                f'<span class="overflow-drop" '
                f'style="left:{lft}%;background:{color};--delay:{dly}s"></span>'
            )

    return (
        f'<div class="tank-outer">'
        f'<div class="tank-body-wrap">'
        f'{drops}'
        f'<div class="tank-wrap{crit_cls}" style="--fill-pct:{fill:.0f}%">'
        f'<div class="tank-water" '
        f'style="background:linear-gradient(180deg,{light} 0%,{color} 100%)"></div>'
        f'<span class="tank-pct">{pct:.0f}%</span>'
        f'</div></div>'
        f'<div class="tank-label">annual withdrawal</div>'
        f'</div>'
    )


def water_cycle_svg() -> str:
    return (
        '<svg width="196" height="78" viewBox="0 0 196 78" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<path d="M10 36 Q10 26 20 26 Q22 18 31 18 Q40 13 49 18 '
        'Q58 13 64 22 Q71 22 71 31 Q71 38 64 38 L17 38 Q10 38 10 36Z" '
        'stroke="#0ea5e9" stroke-width="1.4" fill="rgba(14,165,233,0.06)"/>'
        '<line x1="26" y1="41" x2="23" y2="50" stroke="#0ea5e9" '
        'stroke-width="1.4" stroke-linecap="round"/>'
        '<line x1="40" y1="41" x2="37" y2="52" stroke="#0ea5e9" '
        'stroke-width="1.4" stroke-linecap="round"/>'
        '<line x1="54" y1="41" x2="51" y2="50" stroke="#0ea5e9" '
        'stroke-width="1.4" stroke-linecap="round"/>'
        '<path d="M4 62 Q16 55 28 62 Q40 69 52 62 Q64 55 76 62 '
        'Q88 69 100 62 Q112 55 124 62 Q136 69 148 62 Q160 55 172 62 '
        'Q184 69 191 62" stroke="#0ea5e9" stroke-width="1.4" fill="none" '
        'stroke-linecap="round"/>'
        '<path d="M188 60 C192 46 183 32 188 16" stroke="#0ea5e9" '
        'stroke-width="1.2" stroke-dasharray="3 3" fill="none"/>'
        '<path d="M188 16 L184 24 M188 16 L192 24" stroke="#0ea5e9" '
        'stroke-width="1.2" stroke-linecap="round"/>'
        '<path d="M188 16 Q168 6 140 10 Q110 14 82 20 Q72 23 66 26" '
        'stroke="#0ea5e9" stroke-width="1.0" stroke-dasharray="3 3" '
        'fill="none" stroke-linecap="round"/>'
        '<text x="40" y="75" font-family="Inter,sans-serif" font-size="7" '
        'fill="#94a3b8" text-anchor="middle">rainfall</text>'
        '<text x="178" y="75" font-family="Inter,sans-serif" font-size="7" '
        'fill="#94a3b8" text-anchor="middle">evaporation</text>'
        '</svg>'
    )


# ── Chart factories ───────────────────────────────────────────────────────────
def make_map(df: pd.DataFrame, selected_iso: str, metric: str) -> go.Figure:
    col = "withdrawal_pct" if metric == "Withdrawal %" else "withdrawal_cap"
    label_map = {
        "withdrawal_pct": "Withdrawal<br>% of available",
        "withdrawal_cap": "Withdrawal<br>m³/capita",
    }
    plot_df = df.dropna(subset=[col])

    if col == "withdrawal_pct":
        cap     = COLOR_CAP
        df_norm = plot_df[plot_df[col] <= cap].copy()
        df_xtm  = plot_df[plot_df[col] > cap].copy()
    else:
        cap     = max(plot_df[col].quantile(0.95), 1) if not plot_df.empty else 100
        df_norm = plot_df
        df_xtm  = pd.DataFrame()

    fig = px.choropleth(
        df_norm,
        locations="iso",
        locationmode="ISO-3",
        color=col,
        color_continuous_scale=CSCALE,
        range_color=[0, cap],
        hover_name="country_name",
        hover_data={col: ":.1f", "iso": False},
        labels={col: label_map[col]},
    )
    fig.update_traces(
        hoverlabel=dict(bgcolor="#ffffff", font_color="#0f172a",
                        bordercolor="#e2e8f0", font_family="Inter, sans-serif"),
    )

    if not df_xtm.empty:
        fig.add_trace(go.Choropleth(
            locations=df_xtm["iso"],
            locationmode="ISO-3",
            z=[1] * len(df_xtm),
            colorscale=[[0, "#b91c1c"], [1, "#b91c1c"]],
            showscale=False,
            marker_line_color="#f97316",
            marker_line_width=0.8,
            hovertext=df_xtm.apply(
                lambda r: (f"<b>{r.country_name}</b><br>"
                           f"{r[col]:.0f}% — extreme withdrawal<br>"
                           f"<i>Mining fossil groundwater</i>"),
                axis=1,
            ),
            hoverinfo="text",
            hoverlabel=dict(bgcolor="#ffffff", font_color="#0f172a",
                            bordercolor="#f97316"),
            name="Extreme (>150%)",
        ))

    fig.update_geos(
        bgcolor="#f0f5fb",
        landcolor="#dce4ef",
        oceancolor="#e8f1f8",
        lakecolor="#e8f1f8",
        showrivers=True,
        rivercolor="#c4ddf0",
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#c4d4e4",
        coastlinewidth=0.5,
        showland=True, showocean=True, showlakes=True,
        showcountries=True,
        countrycolor="#ffffff",
        countrywidth=0.6,
        projection_type="natural earth",
    )

    if selected_iso and selected_iso in df["iso"].values:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso], locationmode="ISO-3",
            z=[1], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, marker_line_color="#0f172a",
            marker_line_width=2.2, hoverinfo="skip",
        ))

    colorbar_title = label_map[col]
    if col == "withdrawal_pct":
        colorbar_title += f"<br>(capped at {cap}% —<br>dark red = extreme)"

    fig.update_layout(
        paper_bgcolor="#f5f7fa",
        plot_bgcolor="#f5f7fa",
        margin=dict(l=0, r=0, t=0, b=0),
        height=530,
        coloraxis_colorbar=dict(
            title=dict(text=colorbar_title, font=dict(color="#94a3b8", size=9)),
            tickfont=dict(color="#94a3b8", size=9),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#e2e8f0",
            borderwidth=1,
            thickness=10, len=0.38, x=0.99,
        ),
        geo=dict(bgcolor="#f0f5fb"),
        dragmode=False,
        showlegend=False,
    )
    return fig


def make_trend_chart(
    trend_df: pd.DataFrame,
    country_name: str,
    crossings: dict[str, int] | None = None,
    stale_year: int | None = None,
) -> go.Figure:
    crossings = crossings or {}
    fig = go.Figure()

    if stale_year is not None:
        x_max = int(trend_df["year"].max()) + 1
        y_max = float(trend_df["value"].max()) * 1.3
        fig.add_shape(
            type="rect",
            x0=stale_year - 0.5, x1=x_max,
            y0=0, y1=y_max,
            fillcolor="rgba(148,163,184,0.08)",
            line=dict(color="rgba(0,0,0,0)", width=0),
            layer="below",
        )
        fig.add_annotation(
            x=(stale_year + x_max) / 2, y=y_max * 0.97,
            text=f"No new data after {stale_year}<br>(World Bank fill-forward)",
            showarrow=False,
            font=dict(color="#94a3b8", size=9),
            xanchor="center", yanchor="top",
            bgcolor="rgba(0,0,0,0)",
        )
        fig.add_vline(
            x=stale_year - 0.5,
            line_dash="dot", line_color="#d0d8e4", line_width=1,
        )

    fig.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["value"],
        mode="lines+markers",
        line=dict(color="#0ea5e9", width=2.2),
        marker=dict(color="#0ea5e9", size=5, line=dict(color="#ffffff", width=1)),
        fill="tozeroy", fillcolor="rgba(14,165,233,0.08)",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))

    max_val = float(trend_df["value"].max())

    for y_val, txt, col in [
        (40, "High stress (40%)", "#f97316"),
        (80, "Critical (80%)",    "#ef4444"),
    ]:
        if y_val <= max_val * 1.25:
            fig.add_hline(
                y=y_val, line_dash="dot", line_color=col, line_width=1,
                annotation_text=txt, annotation_font_color=col,
                annotation_font_size=10, annotation_position="top right",
            )

    cross_colours = {"HIGH": "#f97316", "CRITICAL": "#ef4444"}
    for label, yr in crossings.items():
        c = cross_colours.get(label, "#94a3b8")
        fig.add_vline(x=yr, line_dash="dot", line_color=c, line_width=1.2)
        fig.add_annotation(
            x=yr, y=max_val * 0.85,
            text=f"← Crossed {label} ({yr})",
            showarrow=False,
            font=dict(color=c, size=10),
            xanchor="left", yanchor="top",
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor=c, borderwidth=1,
            borderpad=4,
        )

    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font=dict(color="#475569", size=11, family="Inter, sans-serif"),
        title=dict(
            text=f"{country_name} — Freshwater Withdrawal 1990–2024",
            font=dict(color="#0f172a", size=13), x=0.01,
        ),
        xaxis=dict(gridcolor="#e2e8f0", color="#94a3b8",
                   showline=False, zeroline=False, tickformat="d"),
        yaxis=dict(gridcolor="#e2e8f0", color="#94a3b8",
                   showline=False, zeroline=False,
                   title="% of available freshwater",
                   title_font=dict(color="#94a3b8", size=10)),
        margin=dict(l=10, r=30, t=50, b=10),
        showlegend=False,
    )
    return fig


def make_compare_chart(df: pd.DataFrame, iso_a: str, iso_b: str,
                       name_a: str, name_b: str) -> go.Figure:
    metrics = [
        ("withdrawal_pct", "Withdrawal %",       "%"),
        ("safe_access",    "Safe Access %",      "%"),
        ("agri_share",     "Agriculture Share",  "%"),
    ]
    fig = go.Figure()
    for col, label, _ in metrics:
        va = df.loc[df["iso"] == iso_a, col].values
        vb = df.loc[df["iso"] == iso_b, col].values
        va = float(va[0]) if len(va) and va[0] is not None and not pd.isna(va[0]) else 0
        vb = float(vb[0]) if len(vb) and vb[0] is not None and not pd.isna(vb[0]) else 0
        fig.add_trace(go.Bar(
            name=name_a, x=[label], y=[va],
            marker_color="#0ea5e9",
            marker_line_width=0,
            showlegend=(col == "withdrawal_pct"),
        ))
        fig.add_trace(go.Bar(
            name=name_b, x=[label], y=[vb],
            marker_color="#8b5cf6",
            marker_line_width=0,
            showlegend=(col == "withdrawal_pct"),
        ))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8fafc",
        font=dict(color="#475569", size=11, family="Inter, sans-serif"),
        legend=dict(font=dict(color="#475569"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#e2e8f0", color="#94a3b8", showline=False),
        yaxis=dict(gridcolor="#e2e8f0", color="#94a3b8", showline=False,
                   title="%", title_font=dict(color="#94a3b8", size=10)),
        margin=dict(l=10, r=20, t=20, b=10),
        height=280,
    )
    return fig


# ── HTML builders ─────────────────────────────────────────────────────────────
def _benchmark_span(val, avg, higher_is_worse=True) -> str:
    if val is None or avg is None or pd.isna(val) or pd.isna(avg) or avg == 0:
        return ""
    ratio = val / avg
    if ratio >= 2:
        cls = "bench-up" if higher_is_worse else "bench-down"
        txt = f"↑ {ratio:.1f}× world avg ({avg:,.0f})"
    elif ratio <= 0.5:
        cls = "bench-down" if higher_is_worse else "bench-up"
        txt = f"↓ {ratio:.1f}× world avg ({avg:,.0f})"
    else:
        cls = ""
        txt = f"world avg {avg:,.0f}"
    return f'<span class="benchmark {cls}">{txt}</span>'


def _fw_threshold_span(val) -> str:
    if val is None or pd.isna(val):
        return ""
    for threshold, label, _ in FW_THRESHOLDS:
        if val < threshold:
            return (f'<span class="benchmark bench-fw">'
                    f'· {label} (&lt;{threshold:,} m³)</span>')
    return '<span class="benchmark">· above stress threshold</span>'


def _sector_bars(agri, ind, dom) -> str:
    sectors = [
        ("🌾 Agriculture", agri, "#22c55e", "0s"),
        ("🏭 Industry",    ind,  "#3b82f6", "0.15s"),
        ("🏠 Municipal",   dom,  "#a78bfa", "0.30s"),
    ]
    rows = []
    for name, val, colour, delay in sectors:
        w    = f"{min(val or 0, 100):.1f}%"
        disp = f"{val:.0f}%" if (val is not None and not pd.isna(val)) else "—"
        rows.append(
            f'<div class="sector-row">'
            f'<div class="sector-label-row"><span>{name}</span><span>{disp}</span></div>'
            f'<div class="sector-track">'
            f'<div class="sector-fill" '
            f'style="width:{w};background:{colour};animation-delay:{delay}"></div>'
            f'</div></div>'
        )
    return "\n".join(rows)


def _agri_callout(agri, country_name: str) -> str:
    if agri is None or pd.isna(agri):
        return "Agriculture accounts for ~70% of global freshwater withdrawals."
    if agri > 90:
        return f"{country_name} is exceptionally agriculture-dependent — 9 in 10 litres go to crops."
    if agri > 70:
        return f"Agriculture dominates at {agri:.0f}% — above the global average of 70%."
    if agri < 35:
        return (f"Unusually, industry and urban use outweigh farming — "
                f"agriculture is just {agri:.0f}% of withdrawals.")
    return f"Agriculture takes {agri:.0f}% of withdrawals; global average is 70%."


def _country_panel_v2(r: pd.Series, rank: int, avgs: dict) -> str:
    pct           = r.withdrawal_pct
    label, fg, bg = stress_band(pct)
    story_text    = country_story(r, rank, avgs["withdrawal_pct"])

    # Water drop badge
    drop_fill = BAND_DROP_FILL.get(label, 0.5)
    pulse_cls = " stress-dot-critical" if label == "CRITICAL" else ""
    drop_html = (
        f'<div class="drop-badge">'
        f'{water_drop_svg(drop_fill, fg, 24)}'
        f'<span class="drop-band-label" style="color:{fg}">{label}</span>'
        f'</div>'
    )

    # Fossil reveal
    if pct > 100:
        excess    = pct - 100
        specific  = FOSSIL_STORIES.get(r.iso, "")
        body_text = (specific if specific else
                     "This country withdraws more water than nature replenishes "
                     "each year. The deficit is drawn from fossil aquifers that "
                     "cannot refill on any human timescale.")
        fossil_html = (
            f'<div class="fossil-reveal">'
            f'<div class="fossil-title">⚠ Mining Ancient Water</div>'
            f'<div class="fossil-body">{body_text}</div>'
            f'<div class="fossil-stat">Drawing {excess:.0f}% over annual recharge limit</div>'
            f'</div>'
        )
    else:
        fossil_html = ""

    # Metrics grid
    cells = [
        ("Withdrawal",  _fmt(pct, 1),             "%",
         _benchmark_span(pct, avgs["withdrawal_pct"], higher_is_worse=True),       0),
        ("Per Capita",  _fmt(r.withdrawal_cap, 0), "m³",
         _benchmark_span(r.withdrawal_cap, avgs["withdrawal_cap"], higher_is_worse=True), 1),
        ("Freshwater",  _fmt(r.freshwater_cap, 0), "m³/cap",
         _fw_threshold_span(r.freshwater_cap),                                      2),
        ("Safe Access", _fmt(r.safe_access, 1),    "%",
         _benchmark_span(r.safe_access, avgs["safe_access"], higher_is_worse=False), 3),
    ]
    grid_html = "".join(
        f'<div class="metric-card" style="animation-delay:{n*55}ms">'
        f'<div class="metric-label">{nm}</div>'
        f'<div class="metric-value">{v}<span class="metric-unit">{u}</span></div>'
        f'{bench}</div>'
        for nm, v, u, bench, n in cells
    )

    return (
        f'<div class="country-heading">{r.country_name}</div>'
        f'{drop_html}'
        f'{tank_svg(pct, fg)}'
        f'<div class="story-card">{story_text}</div>'
        f'{fossil_html}'
        f'<div class="metrics-grid">{grid_html}</div>'
    )


def _stats_strip_v2(gs: dict) -> str:
    top_short = gs["top_name"].split(",")[0]

    # SVG icons (24×24 viewBox)
    icon_warn  = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
                  'stroke="#ef4444" stroke-width="1.8" stroke-linecap="round">'
                  '<path d="M12 2L2 20h20L12 2zm0 6v6m0 2v2"/></svg>')
    icon_globe = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
                  'stroke="#f97316" stroke-width="1.8" stroke-linecap="round">'
                  '<circle cx="12" cy="12" r="9"/>'
                  '<path d="M3 12h18M12 3C9 7 9 17 12 21M12 3c3 4 3 14 0 18"/></svg>')
    icon_drop  = ('<svg width="18" height="18" viewBox="0 0 24 28" fill="none" '
                  'stroke="#0ea5e9" stroke-width="1.8" stroke-linecap="round">'
                  '<path d="M12 3C12 3 3 13 3 19a9 9 0 0 0 18 0C21 13 12 3 12 3Z"/>'
                  '</svg>')
    icon_star  = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
                  'stroke="#8b5cf6" stroke-width="1.8" stroke-linecap="round">'
                  '<path d="M12 2l3.1 6.2L22 9.1l-5 4.9 1.2 6.9L12 17.7'
                  'l-6.2 3.2L7 14 2 9.1l6.9-.9L12 2z"/></svg>')

    items = [
        (icon_warn,  f"{gs['critical_count']}",  "countries at critical stress",   0),
        (icon_globe, f"{gs['fossil_count']}",     "mining fossil groundwater",      1),
        (icon_drop,  f"{gs['global_avg']:.0f}%", "global avg withdrawal",          2),
        (icon_star,  top_short,                   f"{gs['top_pct']:.0f}% — highest", 3),
    ]
    cards = "".join(
        f'<div class="strip-card" style="animation-delay:{delay*100}ms">'
        f'<div class="strip-icon">{icon}</div>'
        f'<div class="strip-n">{n}</div>'
        f'<div class="strip-l">{l}</div>'
        f'</div>'
        for icon, n, l, delay in items
    )
    return f'<div class="strip-row">{cards}</div>'


def intro_card_html(gs: dict) -> str:
    return (
        f'<div class="intro-card">'
        f'<div class="intro-inner">'
        f'<div class="intro-text">'
        f'<div class="intro-heading">What is water stress?</div>'
        f'<p class="intro-body">A country is <b>water stressed</b> when it withdraws '
        f'more than 20% of its renewable supply each year. Cross 40% and it\'s '
        f'<b style="color:#f97316">HIGH</b>. Cross 80% and it\'s '
        f'<b style="color:#ef4444">CRITICAL</b> — crops fail, taps run dry, '
        f'aquifers collapse. Above 100% means mining ancient groundwater that '
        f'took millennia to accumulate.</p>'
        f'<div class="intro-callout">'
        f'<span class="intro-n">{gs["critical_count"]}</span>'
        f'<span class="intro-l">countries at critical stress right now. '
        f'Global average: {gs["global_avg"]:.0f}%.</span>'
        f'</div></div>'
        f'<div class="intro-svg">{water_cycle_svg()}</div>'
        f'</div></div>'
    )


def _compare_tanks(row_a, row_b, name_a: str, name_b: str) -> str:
    def _pct(r):
        v = r.withdrawal_pct
        return float(v) if (v is not None and not pd.isna(v)) else 0.0

    pct_a = _pct(row_a)
    pct_b = _pct(row_b)
    _, color_a, _ = stress_band(pct_a)
    _, color_b, _ = stress_band(pct_b)
    lbl_a = stress_band(pct_a)[0]
    lbl_b = stress_band(pct_b)[0]

    def _side(pct, color, name, lbl):
        fill    = min(pct, 100)
        is_over = pct > 100
        is_crit = pct >= 80
        light   = _hex_rgba(color, 0.25)
        crit_cls = " race-critical" if is_crit else ""
        drops   = ""
        if is_over:
            for lft, dly in [(18, 0.0), (50, 0.5), (78, 1.0)]:
                drops += (
                    f'<span class="race-drop" '
                    f'style="left:{lft}%;background:{color};--delay:{dly}s"></span>'
                )
        short_name = name[:22] + ("…" if len(name) > 22 else "")
        return (
            f'<div class="race-side">'
            f'<div class="race-name">{short_name}</div>'
            f'<div class="race-tank-wrap">'
            f'{drops}'
            f'<div class="race-tank{crit_cls}" style="--fill-pct:{fill:.0f}%">'
            f'<div class="race-water" '
            f'style="background:linear-gradient(180deg,{light} 0%,{color} 100%)"></div>'
            f'<span class="race-pct">{pct:.0f}%</span>'
            f'</div></div>'
            f'<div class="race-band" style="color:{color}">{lbl}</div>'
            f'</div>'
        )

    return (
        f'<div class="race-row">'
        f'{_side(pct_a, color_a, name_a, lbl_a)}'
        f'<div class="race-vs">vs</div>'
        f'{_side(pct_b, color_b, name_b, lbl_b)}'
        f'</div>'
    )


# ── App ────────────────────────────────────────────────────────────────────────
st.markdown(CSS, unsafe_allow_html=True)

with st.spinner("Loading freshwater data…"):
    df    = load_water_data()
    names = load_country_names()

df["country_name"] = df["iso"].map(names).fillna(df["iso"])
iso_to_name = dict(zip(df["iso"], df["country_name"]))
name_to_iso = {v: k for k, v in iso_to_name.items()}
iso_list    = sorted(iso_to_name.values())

gs   = global_stats(df)
avgs = gs["avgs"]

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

    st.markdown('<span class="radio-label">Colour map by</span>',
                unsafe_allow_html=True)
    metric = st.radio("Colour map by", ["Withdrawal %", "Per Capita m³"],
                      horizontal=True, label_visibility="collapsed")

    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    iso    = st.session_state.iso
    row_df = df[df["iso"] == iso]

    if not row_df.empty:
        r = row_df.iloc[0].copy()
        if (pd.isna(r.domestic_share) or r.domestic_share is None) \
                and not pd.isna(r.agri_share) and not pd.isna(r.industry_share):
            r["domestic_share"] = max(0.0, 100.0 - r.agri_share - r.industry_share)

        rank = iso_to_rank.get(iso, 0)
        st.markdown(_country_panel_v2(r, rank, avgs), unsafe_allow_html=True)
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
            f'<div class="data-footer">Data as of {r.year} · World Bank</div>',
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

# ── Main content ──────────────────────────────────────────────────────────────

# Dismissible intro card
if not st.session_state.get("intro_dismissed"):
    st.markdown(intro_card_html(gs), unsafe_allow_html=True)
    if st.button("Got it, explore the map →", key="dismiss_intro"):
        st.session_state.intro_dismissed = True
        st.rerun()

# Stats strip (glass cards)
st.markdown(_stats_strip_v2(gs), unsafe_allow_html=True)

st.markdown(
    f'<div class="no-data-note">Grey countries: no World Bank data. '
    f'Dark red countries exceed {COLOR_CAP}% withdrawal.</div>',
    unsafe_allow_html=True,
)

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
tab1, tab2, tab3 = st.tabs([
    "  Trend since 1990  ",
    "  Most Stressed  ",
    "  Compare Countries  ",
])

with tab1:
    iso          = st.session_state.iso
    country_name = iso_to_name.get(iso, iso)
    with st.spinner("Loading trend data…"):
        trend = load_country_trend(iso)
    if trend.empty:
        st.markdown(
            f"<div style='color:#94a3b8;font-size:13px;padding:24px 0'>"
            f"No historical trend data available for <b>{country_name}</b>.</div>",
            unsafe_allow_html=True,
        )
    else:
        crossings  = threshold_crossings(trend)
        stale_year = detect_stale_trend(trend)
        if stale_year:
            st.markdown(
                f'<div class="stale-note">⚠ World Bank data for {country_name} '
                f'has not been updated since {stale_year}. '
                f'The flat portion reflects repeated values, not actual stability.</div>',
                unsafe_allow_html=True,
            )
        st.plotly_chart(
            make_trend_chart(trend, country_name, crossings, stale_year),
            use_container_width=True,
            config={"displayModeBar": False},
        )

with tab2:
    top20 = (
        df.nlargest(20, "withdrawal_pct")
        [["country_name", "withdrawal_pct", "agri_share",
          "industry_share", "domestic_share", "year"]]
        .copy()
        .reset_index(drop=True)
    )
    top20.index += 1
    st.dataframe(
        top20,
        use_container_width=True,
        height=480,
        column_config={
            "country_name":   st.column_config.TextColumn("Country"),
            "withdrawal_pct": st.column_config.NumberColumn(
                "Withdrawal %", format="%.1f%%",
                help="Annual freshwater withdrawal as % of renewable supply",
            ),
            "agri_share":     st.column_config.NumberColumn("Agriculture %", format="%.0f%%"),
            "industry_share": st.column_config.NumberColumn("Industry %",    format="%.0f%%"),
            "domestic_share": st.column_config.NumberColumn("Municipal %",   format="%.0f%%"),
            "year":           st.column_config.TextColumn("Data Year"),
        },
    )

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        chosen_a = st.selectbox(
            "Country A", iso_list,
            index=iso_list.index(iso_to_name.get(st.session_state.iso, iso_list[0]))
                  if iso_to_name.get(st.session_state.iso) in iso_list else 0,
            key="cmp_a",
        )
    with col_b:
        default_b      = "CHN" if st.session_state.iso != "CHN" else "USA"
        default_b_name = iso_to_name.get(default_b, iso_list[1])
        chosen_b = st.selectbox(
            "Country B", iso_list,
            index=iso_list.index(default_b_name) if default_b_name in iso_list else 1,
            key="cmp_b",
        )

    iso_a = name_to_iso.get(chosen_a, "IND")
    iso_b = name_to_iso.get(chosen_b, "CHN")

    rows_a = df[df["iso"] == iso_a]
    rows_b = df[df["iso"] == iso_b]

    if not rows_a.empty and not rows_b.empty:
        ra = rows_a.iloc[0]
        rb = rows_b.iloc[0]

        # Water race (expressive animation)
        st.markdown(_compare_tanks(ra, rb, chosen_a, chosen_b), unsafe_allow_html=True)

        # Side-by-side metric cards
        mc1, mc2 = st.columns(2)
        for col_widget, r, name in [(mc1, ra, chosen_a), (mc2, rb, chosen_b)]:
            with col_widget:
                lbl, fg, bg = stress_band(r.withdrawal_pct)
                st.markdown(
                    f'<div class="country-heading-compare">{name}</div>'
                    f'<div class="stress-badge" style="background:{bg};color:{fg};margin-bottom:10px">'
                    f'<div class="stress-dot" style="background:{fg}"></div>{lbl}</div>',
                    unsafe_allow_html=True,
                )
                for label, val, unit in [
                    ("Withdrawal",  _fmt(r.withdrawal_pct, 1), "%"),
                    ("Per Capita",  _fmt(r.withdrawal_cap, 0), "m³"),
                    ("Freshwater",  _fmt(r.freshwater_cap, 0), "m³/cap"),
                    ("Safe Access", _fmt(r.safe_access, 1),    "%"),
                ]:
                    st.markdown(
                        f'<div class="metric-label" style="margin-top:8px">{label}</div>'
                        f'<div class="metric-value" style="font-size:16px">'
                        f'{val}<span class="metric-unit">{unit}</span></div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        st.plotly_chart(
            make_compare_chart(df, iso_a, iso_b, chosen_a, chosen_b),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.markdown(
            '<div style="color:#94a3b8;font-size:13px;padding:24px 0">'
            'Select two countries to compare.</div>',
            unsafe_allow_html=True,
        )
