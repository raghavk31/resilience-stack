"""
The Resilience Stack — Day 13
Crop Climate Advisor

Location → current climate + 2030/2040 projections → crop suitability scores for smallholder farmers.
"""

import json
import os
import pathlib

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Crop Climate Advisor · Day 13",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── API config ──────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    candidates = [
        pathlib.Path(__file__).resolve().parent / ".env",
        pathlib.Path(os.getcwd()) / ".env",
        pathlib.Path.home() / "dev" / "climate-30" / ".env",
    ]
    for env_file in candidates:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    try:
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return ""


OPENROUTER_KEY = _get_api_key()
MODEL = "anthropic/claude-sonnet-4-5"

GEO_URL     = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"
HEADERS     = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

# ── Crop database ───────────────────────────────────────────────────────────────
# temp_opt/abs: mean annual °C (optimal range, absolute viability range)
# precip_opt/abs: annual mm
# frost_days_max: frost days/yr before significant yield impact
# heat_days_max: days >35°C/yr before significant yield impact

CROPS: dict[str, dict] = {
    "Maize": {
        "emoji": "🌽", "category": "Staples",
        "temp_opt": (18, 26), "temp_abs": (10, 34),
        "precip_opt": (600, 1100), "precip_abs": (400, 1800),
        "frost_days_max": 5, "heat_days_max": 50,
        "notes": "Versatile staple. Heat-tolerant varieties available.",
    },
    "Rice": {
        "emoji": "🌾", "category": "Staples",
        "temp_opt": (22, 30), "temp_abs": (15, 38),
        "precip_opt": (1000, 2000), "precip_abs": (800, 3000),
        "frost_days_max": 0, "heat_days_max": 30,
        "notes": "Requires warm, wet conditions. Zero frost tolerance.",
    },
    "Wheat": {
        "emoji": "🌾", "category": "Staples",
        "temp_opt": (10, 18), "temp_abs": (5, 24),
        "precip_opt": (350, 750), "precip_abs": (250, 1200),
        "frost_days_max": 90, "heat_days_max": 15,
        "notes": "Cool-season crop. Needs cold winters for vernalization.",
    },
    "Sorghum": {
        "emoji": "🌾", "category": "Staples",
        "temp_opt": (23, 30), "temp_abs": (16, 38),
        "precip_opt": (400, 800), "precip_abs": (300, 1500),
        "frost_days_max": 5, "heat_days_max": 100,
        "notes": "Excellent drought and heat tolerance. Key resilience crop.",
    },
    "Pearl Millet": {
        "emoji": "🌾", "category": "Staples",
        "temp_opt": (25, 35), "temp_abs": (18, 42),
        "precip_opt": (300, 700), "precip_abs": (200, 1000),
        "frost_days_max": 0, "heat_days_max": 120,
        "notes": "Extremely heat/drought tolerant. Top pick for hot arid farms.",
    },
    "Cassava": {
        "emoji": "🥔", "category": "Staples",
        "temp_opt": (22, 30), "temp_abs": (18, 38),
        "precip_opt": (750, 1500), "precip_abs": (500, 2500),
        "frost_days_max": 0, "heat_days_max": 80,
        "notes": "Drought-tolerant starchy root. Can be stored in the ground.",
    },
    "Sweet Potato": {
        "emoji": "🍠", "category": "Staples",
        "temp_opt": (20, 28), "temp_abs": (14, 35),
        "precip_opt": (700, 1500), "precip_abs": (500, 2000),
        "frost_days_max": 0, "heat_days_max": 60,
        "notes": "Resilient root crop. High vitamin A content.",
    },
    "Teff": {
        "emoji": "🌾", "category": "Staples",
        "temp_opt": (15, 24), "temp_abs": (10, 30),
        "precip_opt": (300, 750), "precip_abs": (200, 1200),
        "frost_days_max": 10, "heat_days_max": 45,
        "notes": "Ethiopian super grain. Highly drought tolerant and nutritious.",
    },
    "Amaranth": {
        "emoji": "🌿", "category": "Staples",
        "temp_opt": (18, 28), "temp_abs": (12, 36),
        "precip_opt": (400, 900), "precip_abs": (300, 1400),
        "frost_days_max": 5, "heat_days_max": 60,
        "notes": "Climate-resilient pseudocereal. Exceptional nutritional profile.",
    },
    "Potato": {
        "emoji": "🥔", "category": "Vegetables",
        "temp_opt": (10, 18), "temp_abs": (5, 25),
        "precip_opt": (500, 1000), "precip_abs": (350, 1500),
        "frost_days_max": 30, "heat_days_max": 10,
        "notes": "Cool-season staple. Tuber failure above 25°C mean temp.",
    },
    "Common Beans": {
        "emoji": "🫘", "category": "Vegetables",
        "temp_opt": (16, 24), "temp_abs": (10, 30),
        "precip_opt": (500, 900), "precip_abs": (350, 1400),
        "frost_days_max": 5, "heat_days_max": 25,
        "notes": "Key protein source. Heat stress at flowering drops yield sharply.",
    },
    "Cowpeas": {
        "emoji": "🫘", "category": "Vegetables",
        "temp_opt": (22, 32), "temp_abs": (16, 40),
        "precip_opt": (350, 800), "precip_abs": (250, 1200),
        "frost_days_max": 0, "heat_days_max": 80,
        "notes": "Heat/drought tolerant legume. Best bet for hot climates.",
    },
    "Chickpeas": {
        "emoji": "🫘", "category": "Vegetables",
        "temp_opt": (14, 22), "temp_abs": (8, 28),
        "precip_opt": (300, 600), "precip_abs": (200, 900),
        "frost_days_max": 30, "heat_days_max": 20,
        "notes": "Cool-season legume. Key crop in South Asia and East Africa.",
    },
    "Lentils": {
        "emoji": "🫘", "category": "Vegetables",
        "temp_opt": (10, 18), "temp_abs": (5, 24),
        "precip_opt": (250, 500), "precip_abs": (150, 750),
        "frost_days_max": 60, "heat_days_max": 10,
        "notes": "Cool-season legume. Drought tolerant in dry winters.",
    },
    "Tomatoes": {
        "emoji": "🍅", "category": "Vegetables",
        "temp_opt": (18, 26), "temp_abs": (12, 32),
        "precip_opt": (600, 1200), "precip_abs": (400, 1800),
        "frost_days_max": 0, "heat_days_max": 20,
        "notes": "High-value vegetable. Pollen sterility above 32°C.",
    },
    "Onions": {
        "emoji": "🧅", "category": "Vegetables",
        "temp_opt": (12, 20), "temp_abs": (7, 28),
        "precip_opt": (350, 700), "precip_abs": (250, 1000),
        "frost_days_max": 30, "heat_days_max": 25,
        "notes": "Cool-season bulb vegetable. High market value.",
    },
    "Banana": {
        "emoji": "🍌", "category": "Fruits",
        "temp_opt": (24, 32), "temp_abs": (18, 40),
        "precip_opt": (1200, 2500), "precip_abs": (900, 3500),
        "frost_days_max": 0, "heat_days_max": 60,
        "notes": "Perennial tropical fruit. Any frost is lethal.",
    },
    "Mango": {
        "emoji": "🥭", "category": "Fruits",
        "temp_opt": (24, 34), "temp_abs": (18, 42),
        "precip_opt": (600, 1500), "precip_abs": (400, 2500),
        "frost_days_max": 0, "heat_days_max": 80,
        "notes": "Tropical tree fruit. Needs a dry season to flower.",
    },
    "Avocado": {
        "emoji": "🥑", "category": "Fruits",
        "temp_opt": (16, 26), "temp_abs": (10, 34),
        "precip_opt": (800, 1800), "precip_abs": (600, 2500),
        "frost_days_max": 5, "heat_days_max": 30,
        "notes": "High-value tree fruit. Sensitive to frost and extreme heat.",
    },
    "Groundnuts": {
        "emoji": "🥜", "category": "Cash Crops",
        "temp_opt": (22, 30), "temp_abs": (15, 36),
        "precip_opt": (500, 1000), "precip_abs": (350, 1500),
        "frost_days_max": 0, "heat_days_max": 60,
        "notes": "Nitrogen-fixing legume. Dual food/oil/protein value.",
    },
    "Soybeans": {
        "emoji": "🫘", "category": "Cash Crops",
        "temp_opt": (18, 26), "temp_abs": (12, 35),
        "precip_opt": (600, 1100), "precip_abs": (450, 1600),
        "frost_days_max": 5, "heat_days_max": 40,
        "notes": "High-protein nitrogen-fixing legume.",
    },
    "Coffee (Arabica)": {
        "emoji": "☕", "category": "Cash Crops",
        "temp_opt": (16, 22), "temp_abs": (12, 26),
        "precip_opt": (1200, 2000), "precip_abs": (900, 2800),
        "frost_days_max": 0, "heat_days_max": 10,
        "notes": "Most climate-vulnerable cash crop. Losing suitable zone fast.",
    },
    "Tea": {
        "emoji": "🍵", "category": "Cash Crops",
        "temp_opt": (14, 22), "temp_abs": (10, 28),
        "precip_opt": (1500, 3000), "precip_abs": (1200, 4000),
        "frost_days_max": 5, "heat_days_max": 15,
        "notes": "Cool, wet highlands crop. Highly climate-sensitive.",
    },
    "Sunflower": {
        "emoji": "🌻", "category": "Cash Crops",
        "temp_opt": (18, 26), "temp_abs": (12, 34),
        "precip_opt": (400, 900), "precip_abs": (300, 1300),
        "frost_days_max": 10, "heat_days_max": 40,
        "notes": "Oilseed crop. Moderately drought tolerant.",
    },
    "Sesame": {
        "emoji": "🌿", "category": "Cash Crops",
        "temp_opt": (24, 32), "temp_abs": (18, 40),
        "precip_opt": (350, 700), "precip_abs": (250, 1100),
        "frost_days_max": 0, "heat_days_max": 80,
        "notes": "Drought-tolerant oilseed. Thrives in hot, dry climates.",
    },
}

CATEGORIES = ["All", "Staples", "Vegetables", "Fruits", "Cash Crops"]

# ── CSS ─────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

*, html, body { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }

.stApp {
  background:
    radial-gradient(ellipse at 10% 20%, rgba(22,163,74,.06) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 80%, rgba(16,185,129,.07) 0%, transparent 50%),
    radial-gradient(ellipse at 55% 5%,  rgba(5,150,105,.05) 0%, transparent 45%),
    #f7f8fa !important;
}
[data-testid="block-container"] {
  padding: 0 !important; max-width: 100% !important; background: transparent !important;
}
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"], section.main { background: transparent !important; }

/* ── Header ── */
.ca-header {
  background: rgba(255,255,255,.95);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0,0,0,0.07);
  padding: 14px 28px 10px;
}
.ca-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #b0b8c8;
  display: flex; align-items: center; gap: 8px;
}
.ca-dot { width: 8px; height: 8px; border-radius: 50%; background: #16a34a; display: inline-block; }

/* ── Two-column layout ── */
[data-testid="stHorizontalBlock"]:has(.ca-left) { gap: 0 !important; align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.90) !important;
  backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 60px);
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child {
  background: transparent !important;
  padding: 24px 28px 40px !important;
}

/* Pad widgets in left column */
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child
  [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child
  [data-testid="stRadio"] {
  padding-left: 20px !important;
  padding-right: 20px !important;
}

/* ── Typography tokens ── */
.ca-left  { height: 0; margin: 0; padding: 0; display: block; }
.ca-pad   { padding: 18px 22px 12px; }
.ca-title {
  font-size: 1.18rem; font-weight: 800; color: #0f172a; line-height: 1.25;
  margin: 0 0 .3rem; letter-spacing: -.2px;
  font-family: 'Space Grotesk', sans-serif;
}
.ca-desc  { font-size: .76rem; color: #94a3b8; line-height: 1.6; margin: 0; }
.ca-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 10px 0; }
.ca-lbl   { font-size: .65rem; font-weight: 700; letter-spacing: .12em;
            text-transform: uppercase; color: #94a3b8; margin-bottom: 6px; }

/* ── Form labels ── */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .75rem !important; font-weight: 600 !important; color: #374151 !important;
}
section.main [data-testid="stRadio"] > label {
  font-size: .74rem !important; font-weight: 600 !important; color: #374151 !important;
  margin-bottom: 4px !important;
}
section.main [data-testid="stTextInput"] input {
  font-size: .8rem !important; border-radius: 8px !important;
}

/* ── Buttons ── */
section.main [data-testid="stButton"] > button {
  border-radius: 8px !important; font-size: .74rem !important; font-weight: 600 !important;
  border: 1px solid rgba(0,0,0,.1) !important;
  background: rgba(255,255,255,.8) !important;
  backdrop-filter: blur(8px) !important; transition: all .15s !important;
  padding: 6px 14px !important;
}
section.main [data-testid="stButton"] > button:hover {
  background: rgba(255,255,255,.97) !important; border-color: rgba(0,0,0,.18) !important;
}
section.main [data-testid="stButton"] > button[kind="primary"] {
  background: #15803d !important; color: #fff !important; border-color: #15803d !important;
}
section.main [data-testid="stButton"] > button[kind="primary"]:hover {
  background: #166534 !important; border-color: #166534 !important;
}

/* ── Advice output ── */
.advice-card {
  background: rgba(255,255,255,.85);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-radius: 14px; padding: 22px 26px;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
}
.advice-output { font-size: .82rem; color: #374151; line-height: 1.7; }
.advice-output h2 { font-size: .9rem; font-weight: 700; color: #0f172a; margin: 16px 0 6px; font-family: 'Space Grotesk', sans-serif; }
.advice-output li { margin-bottom: 3px; }
.advice-output strong { color: #1e293b; font-weight: 600; }
</style>
"""

# ── Climate helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def geocode(location: str) -> dict | None:
    try:
        r = requests.get(
            GEO_URL,
            params={"name": location, "count": 5, "language": "en", "format": "json"},
            headers=HEADERS, timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        top = results[0]
        return {
            "name": top.get("name", location),
            "country": top.get("country", ""),
            "admin1": top.get("admin1", ""),
            "lat": top["latitude"],
            "lon": top["longitude"],
        }
    except Exception:
        return None


def _parse_climate(data: dict) -> dict:
    """Aggregate daily Open-Meteo response into annual climate stats."""
    daily = data.get("daily", {})
    # Climate model API prefixes keys with the model name
    tmax_key = next((k for k in daily if "temperature_2m_max" in k), None)
    tmin_key = next((k for k in daily if "temperature_2m_min" in k), None)
    prec_key = next((k for k in daily if "precipitation_sum" in k), None)

    if not tmax_key:
        raise ValueError("Expected temperature keys not found in response")

    tmax  = pd.Series(daily[tmax_key],  dtype=float).dropna()
    tmin  = pd.Series(daily[tmin_key],  dtype=float).dropna()
    prec  = pd.Series(daily[prec_key],  dtype=float).fillna(0)

    n_years = max(1, len(tmax) / 365)
    tmean   = (tmax + tmin) / 2

    return {
        "mean_temp":        round(float(tmean.mean()), 1),
        "annual_precip":    round(float(prec.sum() / n_years), 0),
        "frost_days":       round(float((tmin < 0).sum() / n_years), 1),
        "heat_stress_days": round(float((tmax > 35).sum() / n_years), 1),
    }


@st.cache_data(ttl=3600)
def fetch_all_climate(lat: float, lon: float) -> dict:
    """Returns {"current": {...}, "2030": {...}, "2040": {...}} or {"error": ...}."""
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": lat, "longitude": lon,
                "start_date": "2019-01-01", "end_date": "2023-12-31",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        current = _parse_climate(r.json())
    except Exception as e:
        return {"error": f"Could not fetch climate data: {e}"}

    projections = {}
    for year in (2030, 2040):
        try:
            r = requests.get(
                CLIMATE_URL,
                params={
                    "latitude": lat, "longitude": lon,
                    "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
                    "models": "EC_Earth3P_HR",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                },
                headers=HEADERS, timeout=30,
            )
            r.raise_for_status()
            projections[str(year)] = _parse_climate(r.json())
        except Exception:
            # IPCC SSP2-4.5 typical deltas as fallback
            delta_t = 0.6 if year == 2030 else 1.1
            projections[str(year)] = {
                "mean_temp":        round(current["mean_temp"] + delta_t, 1),
                "annual_precip":    round(current["annual_precip"] * (0.97 if year == 2030 else 0.94), 0),
                "frost_days":       max(0.0, round(current["frost_days"] * (0.85 if year == 2030 else 0.70), 1)),
                "heat_stress_days": round(current["heat_stress_days"] * (1.30 if year == 2030 else 1.65), 1),
            }

    return {"current": current, "2030": projections["2030"], "2040": projections["2040"]}


# ── Crop scoring ────────────────────────────────────────────────────────────────

def score_crop(crop: dict, climate: dict) -> int:
    score = 100.0
    mt    = climate["mean_temp"]
    prec  = climate["annual_precip"]
    frost = climate["frost_days"]
    heat  = climate["heat_stress_days"]

    to_lo, to_hi = crop["temp_opt"]
    t_lo,  t_hi  = crop["temp_abs"]
    po_lo, po_hi = crop["precip_opt"]
    p_lo,  p_hi  = crop["precip_abs"]

    # Temperature: deduct inside sub-optimal range, heavily outside absolute
    if mt < to_lo:
        score -= (to_lo - mt) * 8
        if mt < t_lo:
            score -= (t_lo - mt) * 20
    elif mt > to_hi:
        score -= (mt - to_hi) * 8
        if mt > t_hi:
            score -= (mt - t_hi) * 20

    # Precipitation
    if prec < po_lo:
        score -= (po_lo - prec) / max(po_lo, 1) * 30
        if prec < p_lo:
            score -= (p_lo - prec) / max(p_lo, 1) * 20
    elif prec > po_hi:
        score -= (prec - po_hi) / max(po_hi, 1) * 20
        if prec > p_hi:
            score -= (prec - p_hi) / max(p_hi, 1) * 15

    # Frost tolerance
    fdmax = crop["frost_days_max"]
    if frost > fdmax:
        score -= min(55, (frost - fdmax) * (3.0 if fdmax == 0 else 1.5))

    # Heat stress tolerance
    hdmax = crop["heat_days_max"]
    if heat > hdmax:
        score -= min(45, (heat - hdmax) * (1.5 if hdmax == 0 else 0.8))

    return max(0, min(100, int(score)))


def classify(s: int) -> tuple[str, str]:
    if s >= 70:
        return "Well suited", "#16a34a"
    if s >= 45:
        return "Marginal", "#d97706"
    return "Not suited", "#dc2626"


def compute_scores(climate_data: dict) -> list[dict]:
    rows = []
    for name, crop in CROPS.items():
        sn  = score_crop(crop, climate_data["current"])
        s30 = score_crop(crop, climate_data["2030"])
        s40 = score_crop(crop, climate_data["2040"])
        rows.append({
            "name": name, "emoji": crop["emoji"],
            "category": crop["category"], "notes": crop["notes"],
            "score_now": sn, "score_2030": s30, "score_2040": s40,
            "delta": s40 - sn,
        })
    return sorted(rows, key=lambda x: x["score_now"], reverse=True)


# ── LLM streaming ───────────────────────────────────────────────────────────────

def stream_advice(location_name: str, climate: dict, scores: list[dict]):
    """Generator yielding text deltas from Claude."""
    top5     = [c for c in scores if c["score_now"] >= 45][:5]
    declining = sorted(
        [c for c in scores if c["delta"] < -10 and c["score_now"] >= 40],
        key=lambda x: x["delta"]
    )[:3]

    def fmt(c: dict) -> str:
        return f"{c['emoji']} {c['name']} ({c['score_now']}→{c['score_2040']} by 2040)"

    curr = climate["current"]
    proj = climate["2040"]

    prompt = f"""You are an expert agricultural advisor helping smallholder farmers adapt to climate change.

LOCATION: {location_name}
CURRENT CLIMATE: Mean {curr['mean_temp']}°C, Rain {curr['annual_precip']:.0f}mm/yr, Frost {curr['frost_days']:.0f} days/yr, Heat stress {curr['heat_stress_days']:.0f} days/yr (days >35°C)
2040 PROJECTION: Mean {proj['mean_temp']}°C (+{proj['mean_temp']-curr['mean_temp']:.1f}°C), Rain {proj['annual_precip']:.0f}mm/yr, Frost {proj['frost_days']:.0f} days/yr, Heat stress {proj['heat_stress_days']:.0f} days/yr

BEST PERFORMING CROPS NOW: {', '.join(fmt(c) for c in top5)}
CROPS FACING DECLINE BY 2040: {', '.join(fmt(c) for c in declining) or 'None flagged'}

Write a practical advisory for a smallholder farmer in {location_name} with EXACTLY these 4 sections:

## 🌱 What to Grow Now
Top 3 crop recommendations for this climate. Include planting windows and one practical tip per crop.

## 🔄 Adapt by 2035
Which current crops need heat or drought-tolerant varieties? What new crops to introduce now to build 2035 resilience?

## 🌡️ By 2040: What Changes
Which crops will become unviable? What replaces them? Name specific varieties or alternatives to plant today.

## 💡 3 Actions This Season
Three concrete steps for this growing season. Each: action, what to do, time required, approximate cost.

Rules: Be specific to {location_name}. No filler. Write for a smallholder with limited resources. Use bullet points for lists."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Raghavk31/resilience-stack",
                "X-Title": "30 Days of Climate Intelligence",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "stream": True,
            },
            stream=True,
            timeout=90,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith(b"data: "):
                data = line[6:]
                if data == b"[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    pass
    except requests.HTTPError as e:
        yield f"\n\n⚠️ API error ({e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        yield f"\n\n⚠️ Generation failed: {e}"


# ── HTML rendering helpers ───────────────────────────────────────────────────────

def _climate_card_html(loc: dict, climate: dict) -> str:
    curr = climate["current"]
    proj = climate["2040"]
    dt   = proj["mean_temp"]   - curr["mean_temp"]
    dp   = proj["annual_precip"] - curr["annual_precip"]
    dh   = proj["heat_stress_days"] - curr["heat_stress_days"]
    df   = proj["frost_days"]  - curr["frost_days"]

    def delta_span(val: float, unit: str, bad_positive: bool = True) -> str:
        if abs(val) < 0.05:
            return f'<span style="color:#94a3b8">→</span>'
        color = ("#dc2626" if val > 0 else "#16a34a") if bad_positive else ("#16a34a" if val > 0 else "#dc2626")
        arrow = "↑" if val > 0 else "↓"
        return f'<span style="color:{color};font-size:.72rem;font-weight:600">{arrow}{abs(val):.1f}{unit} by 2040</span>'

    location_label = loc["name"]
    if loc.get("admin1"):
        location_label += f", {loc['admin1']}"
    if loc.get("country"):
        location_label += f", {loc['country']}"

    stats = [
        ("🌡️", "Mean temp", f"{curr['mean_temp']}°C",  delta_span(dt,  "°C", bad_positive=True)),
        ("🌧️", "Annual rain", f"{curr['annual_precip']:.0f}mm", delta_span(dp, "mm", bad_positive=False)),
        ("❄️", "Frost days/yr", f"{curr['frost_days']:.0f}", delta_span(df, " days", bad_positive=False)),
        ("🔥", "Heat stress days/yr", f"{curr['heat_stress_days']:.0f}", delta_span(dh, " days", bad_positive=True)),
    ]

    stat_html = "".join(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:7px 0;border-bottom:1px solid rgba(0,0,0,.05)">'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<span style="font-size:1rem">{icon}</span>'
        f'<span style="font-size:.75rem;color:#64748b">{label}</span>'
        f'</div>'
        f'<div style="text-align:right">'
        f'<span style="font-size:.8rem;font-weight:700;color:#0f172a;font-family:Space Grotesk,sans-serif">{value}</span>'
        f'<span style="margin-left:8px">{delta}</span>'
        f'</div>'
        f'</div>'
        for icon, label, value, delta in stats
    )

    return (
        f'<div style="background:rgba(255,255,255,.88);backdrop-filter:blur(14px);'
        f'border-radius:14px;padding:16px 20px;border:1px solid rgba(0,0,0,.07);'
        f'box-shadow:0 2px 12px rgba(0,0,0,.04);margin-bottom:20px">'
        f'<div style="font-size:.62rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;'
        f'color:#94a3b8;margin-bottom:4px">Climate Profile</div>'
        f'<div style="font-size:.95rem;font-weight:800;color:#0f172a;'
        f'font-family:Space Grotesk,sans-serif;margin-bottom:12px">{location_label}</div>'
        f'{stat_html}'
        f'</div>'
    )


def _legend_html(scores: list[dict]) -> str:
    well  = sum(1 for s in scores if s["score_now"] >= 70)
    marg  = sum(1 for s in scores if 45 <= s["score_now"] < 70)
    not_s = sum(1 for s in scores if s["score_now"] < 45)
    return (
        '<div style="display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap">'
        f'<div style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:10px;'
        f'border-radius:50%;background:#16a34a;display:inline-block"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{well} well suited</span></div>'
        f'<div style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:10px;'
        f'border-radius:50%;background:#d97706;display:inline-block"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{marg} marginal</span></div>'
        f'<div style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:10px;'
        f'border-radius:50%;background:#dc2626;display:inline-block"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{not_s} not suited</span></div>'
        '</div>'
    )


def _crop_grid_html(scores: list[dict]) -> str:
    cards = []
    for c in scores:
        sn, s30, s40 = c["score_now"], c["score_2030"], c["score_2040"]
        _, col_now = classify(sn)
        _, col_30  = classify(s30)
        _, col_40  = classify(s40)
        delta = s40 - sn
        arrow       = "↑" if delta > 5 else ("↓" if delta < -5 else "→")
        arrow_color = "#16a34a" if delta > 5 else ("#dc2626" if delta < -5 else "#94a3b8")

        card = (
            f'<div style="background:rgba(255,255,255,.85);backdrop-filter:blur(12px);'
            f'border-radius:12px;padding:14px 16px;border:1px solid rgba(0,0,0,.07);'
            f'box-shadow:0 1px 8px rgba(0,0,0,.04);position:relative;overflow:hidden">'
            f'<div style="position:absolute;top:0;left:0;width:4px;height:100%;'
            f'background:{col_now};border-radius:12px 0 0 12px"></div>'
            f'<div style="padding-left:4px">'
            f'<div style="font-size:1.4rem;line-height:1;margin-bottom:5px">{c["emoji"]}</div>'
            f'<div style="font-size:.8rem;font-weight:700;color:#0f172a;'
            f'font-family:Space Grotesk,sans-serif;letter-spacing:-.1px;margin-bottom:3px">{c["name"]}</div>'
            f'<div style="font-size:.66rem;color:#94a3b8;margin-bottom:10px;line-height:1.35">{c["notes"]}</div>'
            f'<div style="display:flex;align-items:center;gap:6px">'
            f'<div style="text-align:center">'
            f'<div style="font-size:.57rem;font-weight:700;letter-spacing:.08em;color:#b0b8c8;text-transform:uppercase">Now</div>'
            f'<div style="font-size:.88rem;font-weight:800;color:{col_now};font-family:Space Grotesk,sans-serif">{sn}</div>'
            f'</div>'
            f'<div style="font-size:.7rem;color:#cbd5e1">›</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:.57rem;font-weight:700;letter-spacing:.08em;color:#b0b8c8;text-transform:uppercase">2030</div>'
            f'<div style="font-size:.88rem;font-weight:700;color:{col_30};font-family:Space Grotesk,sans-serif">{s30}</div>'
            f'</div>'
            f'<div style="font-size:.7rem;color:#cbd5e1">›</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:.57rem;font-weight:700;letter-spacing:.08em;color:#b0b8c8;text-transform:uppercase">2040</div>'
            f'<div style="font-size:.88rem;font-weight:700;color:{col_40};font-family:Space Grotesk,sans-serif">{s40}</div>'
            f'</div>'
            f'<div style="margin-left:auto;font-size:1.05rem;font-weight:700;color:{arrow_color}">{arrow}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        cards.append(card)

    inner = "".join(cards)
    return (
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">'
        f'{inner}'
        f'</div>'
    )


def _placeholder() -> None:
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;min-height:65vh;gap:20px;padding:32px 20px;text-align:center">'
        '<div style="font-size:3.5rem;line-height:1">🌱</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#1e293b;'
        'font-family:Space Grotesk,sans-serif;letter-spacing:-.2px">Crop Climate Advisor</div>'
        '<div style="font-size:.8rem;color:#94a3b8;max-width:340px;line-height:1.65">'
        'Enter any city or region to see which crops suit your current climate '
        'and how that changes by 2030 and 2040.</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:4px;max-width:440px">'
        + "".join(
            f'<div style="display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:20px;'
            f'background:rgba(255,255,255,.7);border:1px solid rgba(0,0,0,.07);backdrop-filter:blur(8px)">'
            f'<span style="font-size:1rem">{icon}</span>'
            f'<span style="font-size:.72rem;font-weight:500;color:#64748b">{label}</span>'
            f'</div>'
            for icon, label in [
                ("🌡️", "Climate match"),
                ("📅", "2030 outlook"),
                ("🔮", "2040 outlook"),
                ("🤖", "AI advice"),
            ]
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    # Header
    st.markdown(
        '<div class="ca-header">'
        '<div class="ca-topline"><span class="ca-dot"></span>'
        'THE RESILIENCE STACK &nbsp;·&nbsp; DAY 13 OF 30</div>'
        '<div class="ca-title" style="font-size:1.4rem;margin-top:4px">🌱 Crop Climate Advisor</div>'
        '<div class="ca-desc">25 smallholder crops · current climate vs 2030 & 2040 projections · AI farming advice</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Session state init
    defaults = {
        "loc":      None,
        "climate":  None,
        "scores":   [],
        "category": "All",
        "advice":   "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    left_col, right_col = st.columns([1, 2.2])

    # ── LEFT PANEL ──────────────────────────────────────────────────────────────
    with left_col:
        st.markdown('<div class="ca-left"></div>', unsafe_allow_html=True)
        st.markdown('<div class="ca-pad">', unsafe_allow_html=True)
        st.markdown(
            '<div class="ca-title">Find your region</div>'
            '<div class="ca-desc">City, region, or country for any smallholder farm location worldwide.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<hr class="ca-sep">', unsafe_allow_html=True)

        location_input = st.text_input(
            "Location",
            placeholder="e.g. Nairobi, Punjab, Mato Grosso…",
            label_visibility="collapsed",
            key="location_input",
        )

        with st.container():
            st.markdown('<div style="padding: 0 20px 12px">', unsafe_allow_html=True)
            search_clicked = st.button("🔍 Analyse climate", use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<hr class="ca-sep">', unsafe_allow_html=True)
        st.markdown('<div style="padding:0 20px 8px"><div class="ca-lbl">Filter crops</div></div>', unsafe_allow_html=True)
        category = st.radio(
            "Category",
            CATEGORIES,
            index=CATEGORIES.index(st.session_state["category"]),
            label_visibility="collapsed",
            key="category_radio",
        )
        if category != st.session_state["category"]:
            st.session_state["category"] = category
            st.rerun()

        if st.session_state["climate"]:
            st.markdown('<hr class="ca-sep">', unsafe_allow_html=True)
            st.markdown('<div style="padding:0 20px 8px"><div class="ca-lbl">AI farming advice</div></div>', unsafe_allow_html=True)
            with st.container():
                st.markdown('<div style="padding: 0 20px 12px">', unsafe_allow_html=True)
                ask_ai = st.button("🤖 Get AI advice", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown(
                '<div style="padding:0 20px"><div class="ca-desc">'
                'Claude generates localised crop strategy for now, 2030, and 2040.</div></div>',
                unsafe_allow_html=True,
            )
        else:
            ask_ai = False

    # ── RIGHT PANEL ─────────────────────────────────────────────────────────────
    with right_col:
        # Handle search
        if search_clicked and location_input.strip():
            with st.spinner("Locating…"):
                loc = geocode(location_input.strip())
            if not loc:
                st.error(f"Location '{location_input}' not found. Try a different spelling.")
                st.stop()

            with st.spinner(f"Fetching climate data for {loc['name']}…"):
                climate = fetch_all_climate(loc["lat"], loc["lon"])

            if "error" in climate:
                st.error(climate["error"])
                st.stop()

            st.session_state["loc"]     = loc
            st.session_state["climate"] = climate
            st.session_state["scores"]  = compute_scores(climate)
            st.session_state["advice"]  = ""

        if not st.session_state["climate"]:
            _placeholder()
            st.stop()

        # Climate summary
        st.markdown(
            _climate_card_html(st.session_state["loc"], st.session_state["climate"]),
            unsafe_allow_html=True,
        )

        # Crop grid
        scores = st.session_state["scores"]
        if st.session_state["category"] != "All":
            scores = [s for s in scores if s["category"] == st.session_state["category"]]

        st.markdown(
            f'<div class="ca-lbl" style="margin-bottom:8px">'
            f'{len(scores)} crops · sorted by climate match</div>',
            unsafe_allow_html=True,
        )
        st.markdown(_legend_html(scores), unsafe_allow_html=True)
        st.markdown(_crop_grid_html(scores), unsafe_allow_html=True)

        # AI Advice
        if ask_ai:
            st.session_state["advice"] = ""
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="ca-lbl" style="margin-bottom:10px">AI FARMING ADVICE</div>', unsafe_allow_html=True)
            st.markdown('<div class="advice-card advice-output">', unsafe_allow_html=True)
            advice_placeholder = st.empty()
            full_text = ""
            for chunk in stream_advice(
                f'{st.session_state["loc"]["name"]}, {st.session_state["loc"]["country"]}',
                st.session_state["climate"],
                st.session_state["scores"],
            ):
                full_text += chunk
                advice_placeholder.markdown(full_text)
            st.session_state["advice"] = full_text
            st.markdown("</div>", unsafe_allow_html=True)

        elif st.session_state["advice"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="ca-lbl" style="margin-bottom:10px">AI FARMING ADVICE</div>', unsafe_allow_html=True)
            st.markdown('<div class="advice-card advice-output">', unsafe_allow_html=True)
            st.markdown(st.session_state["advice"])
            st.markdown("</div>", unsafe_allow_html=True)


main()
