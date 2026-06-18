"""
The Resilience Stack — Day 14
Off-Grid Independence Calculator

Location + household profile → custom solar / battery / water / food system
with an independence score and AI-generated implementation roadmap.
"""

import math
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor

import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Off-Grid Calculator · Day 14",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    for env_file in [
        pathlib.Path(__file__).resolve().parent / ".env",
        pathlib.Path(os.getcwd()) / ".env",
        pathlib.Path.home() / "dev" / "climate-30" / ".env",
    ]:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    try:
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return ""


OPENROUTER_KEY = _get_api_key()
MODEL = "anthropic/claude-sonnet-4-5"

GEO_URL     = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_URL    = "https://power.larc.nasa.gov/api/temporal/monthly/point"
HEADERS     = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

PANEL_COST_PER_WP    = 0.65
INVERTER_COST        = 800
BOS_COST             = 500
BATTERY_COST_PER_KWH = 380
TANK_COST_PER_LITER  = 0.50
WATER_FILTER_COST    = 450
GARDEN_PER_M2        = 8.0

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


# ── Data fetching ─────────────────────────────────────────────────────────────

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
            "name":    top.get("name", location),
            "country": top.get("country", ""),
            "admin1":  top.get("admin1", ""),
            "lat":     top["latitude"],
            "lon":     top["longitude"],
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_solar_ghi(lat: float, lon: float) -> dict:
    try:
        r = requests.get(
            NASA_URL,
            params={
                "parameters": "ALLSKY_SFC_SW_DWN",
                "community":  "RE",
                "longitude":  round(lon, 3),
                "latitude":   round(lat, 3),
                "format":     "JSON",
                "start":      2019,
                "end":        2022,
            },
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        raw = r.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
        buckets: dict[int, list] = {m: [] for m in range(1, 13)}
        for key, val in raw.items():
            if val and val != -999:
                buckets[int(key[4:6])].append(float(val))
        monthly = {
            m: round(sum(v) / len(v), 2) if v else _lat_ghi(lat, m)
            for m, v in buckets.items()
        }
        return {"monthly": monthly, "annual_avg": round(sum(monthly.values()) / 12, 2), "source": "NASA POWER"}
    except Exception:
        return _lat_solar_fallback(lat)


def _lat_ghi(lat: float, month: int) -> float:
    lat_abs = abs(lat)
    season = math.cos(math.radians((month - (6.5 if lat >= 0 else 0.5)) * 30))
    return max(1.0, round(6.5 - lat_abs * 0.045 + season * lat_abs * 0.03, 2))


def _lat_solar_fallback(lat: float) -> dict:
    monthly = {m: _lat_ghi(lat, m) for m in range(1, 13)}
    return {"monthly": monthly, "annual_avg": round(sum(monthly.values()) / 12, 2), "source": "estimate"}


@st.cache_data(ttl=3600)
def fetch_climate_rain(lat: float, lon: float) -> dict:
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude":   lat, "longitude": lon,
                "start_date": "2019-01-01", "end_date": "2023-12-31",
                "daily":      "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone":   "auto",
            },
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        daily = r.json().get("daily", {})
        dates = daily.get("time", [])
        tmax  = daily.get("temperature_2m_max", [])
        tmin  = daily.get("temperature_2m_min", [])
        prec  = daily.get("precipitation_sum",  [])

        rain_b: dict[int, list] = {m: [] for m in range(1, 13)}
        temp_b: dict[int, list] = {m: [] for m in range(1, 13)}
        for i, date in enumerate(dates):
            m = int(date[5:7])
            if i < len(prec) and prec[i] is not None:
                rain_b[m].append(float(prec[i]))
            if i < len(tmax) and tmax[i] is not None and i < len(tmin) and tmin[i] is not None:
                temp_b[m].append((float(tmax[i]) + float(tmin[i])) / 2)

        rain_monthly = {
            m: round(sum(v) / len(v) * 30, 1) if v else 50.0
            for m, v in rain_b.items()
        }
        temp_monthly = {
            m: round(sum(v) / len(v), 1) if v else 15.0
            for m, v in temp_b.items()
        }
        all_temps = [t for v in temp_b.values() for t in v]
        mean_temp = round(sum(all_temps) / len(all_temps), 1) if all_temps else 15.0

        return {
            "rain_monthly": rain_monthly,
            "annual_rain":  round(sum(rain_monthly.values()), 0),
            "temp_monthly": temp_monthly,
            "mean_temp":    mean_temp,
        }
    except Exception:
        return {
            "rain_monthly": {m: 50.0 for m in range(1, 13)},
            "annual_rain":  600.0,
            "temp_monthly": {m: 15.0 for m in range(1, 13)},
            "mean_temp":    15.0,
        }


# ── Calculations ──────────────────────────────────────────────────────────────

def calc_solar(monthly_kwh: float, solar: dict, roof_area: float) -> dict:
    daily_kwh  = monthly_kwh / 30
    annual_kwh = monthly_kwh * 12
    sys_eff    = 0.75

    worst_psh  = min(solar["monthly"].values())
    required_wp = math.ceil((daily_kwh * 1000) / (worst_psh * sys_eff) / 50) * 50

    num_panels  = math.ceil(required_wp / 400)
    panel_area  = num_panels * 2.0

    monthly_gen = {
        m: round(required_wp / 1000 * ghi * sys_eff * 30, 1)
        for m, ghi in solar["monthly"].items()
    }
    annual_gen     = sum(monthly_gen.values())
    self_suff_pct  = min(100.0, round(annual_gen / annual_kwh * 100, 1))
    cost           = required_wp * PANEL_COST_PER_WP + INVERTER_COST + BOS_COST

    return {
        "required_wp":    required_wp,
        "num_panels":     num_panels,
        "panel_area_m2":  round(panel_area, 1),
        "annual_gen_kwh": round(annual_gen, 0),
        "self_suff_pct":  self_suff_pct,
        "monthly_gen":    monthly_gen,
        "monthly_demand": {m: monthly_kwh for m in range(1, 13)},
        "cost":           round(cost, 0),
        "roof_pct":       round(panel_area / max(roof_area, 1) * 100, 1),
        "fits_roof":      panel_area <= roof_area,
        "annual_ghi":     solar["annual_avg"],
        "ghi_source":     solar["source"],
    }


def calc_battery(monthly_kwh: float, autonomy_days: int) -> dict:
    daily_kwh    = monthly_kwh / 30
    required_kwh = daily_kwh * autonomy_days / (0.8 * 0.95)
    num_units    = max(1, math.ceil(required_kwh / 5.12))
    capacity     = round(num_units * 5.12, 1)
    return {
        "capacity_kwh":   capacity,
        "required_kwh":   round(required_kwh, 1),
        "num_units":      num_units,
        "autonomy_days":  autonomy_days,
        "daily_kwh":      round(daily_kwh, 2),
        "cost":           round(capacity * BATTERY_COST_PER_KWH, 0),
    }


def calc_water(people: int, climate: dict, roof_area: float) -> dict:
    daily_l      = people * 100
    monthly_need = {m: round(daily_l * 30, 0) for m in range(1, 13)}
    monthly_coll = {
        m: round(climate["rain_monthly"][m] * roof_area * 0.85, 0)
        for m in range(1, 13)
    }
    annual_need  = sum(monthly_need.values())
    annual_coll  = sum(monthly_coll.values())
    coverage_pct = min(100.0, round(annual_coll / max(annual_need, 1) * 100, 1))

    monthly_def  = {m: max(0.0, monthly_need[m] - monthly_coll[m]) for m in range(1, 13)}
    max_deficit  = max(monthly_def.values()) if any(d > 0 for d in monthly_def.values()) else 0

    tank_l = max(daily_l * 30, max_deficit * 1.5) if max_deficit > 0 else daily_l * 14
    tank_l = math.ceil(tank_l / 500) * 500

    return {
        "daily_liters":   daily_l,
        "coverage_pct":   coverage_pct,
        "annual_need":    round(annual_need, 0),
        "annual_coll":    round(annual_coll, 0),
        "monthly_need":   monthly_need,
        "monthly_coll":   monthly_coll,
        "monthly_def":    monthly_def,
        "tank_liters":    tank_l,
        "annual_rain_mm": climate["annual_rain"],
        "cost":           round(tank_l * TANK_COST_PER_LITER + WATER_FILTER_COST, 0),
    }


def calc_food(people: int, land_area: float, climate: dict) -> dict:
    mean_t = climate.get("mean_temp", 15.0)
    temp_m = climate.get("temp_monthly", {m: mean_t for m in range(1, 13)})

    grow_months = sum(1 for t in temp_m.values() if t >= 10)
    grow_months = max(3, grow_months)

    m2_per_person  = round(800 * (12 / grow_months))
    required_total = m2_per_person * people
    coverage_pct   = min(100.0, round(land_area / max(required_total, 1) * 100, 1))

    return {
        "required_m2":    required_total,
        "m2_per_person":  m2_per_person,
        "coverage_pct":   coverage_pct,
        "grow_months":    grow_months,
        "land_area":      land_area,
        "temp_monthly":   temp_m,
        "cost":           round(land_area * GARDEN_PER_M2, 0),
    }


def independence_score(solar_pct: float, water_pct: float, food_pct: float) -> int:
    return min(100, round(0.40 * solar_pct + 0.30 * water_pct + 0.30 * food_pct))


# ── AI streaming ──────────────────────────────────────────────────────────────

def build_roadmap_prompt(r: dict) -> str:
    loc   = r["loc"]
    s     = r["solar"]
    b     = r["battery"]
    w     = r["water"]
    f     = r["food"]
    score = r["score"]
    total = int(s["cost"] + b["cost"] + w["cost"] + f["cost"])
    budget = r["budget"]
    loc_str = loc["name"]
    if loc.get("admin1"):
        loc_str += f", {loc['admin1']}"
    if loc.get("country"):
        loc_str += f", {loc['country']}"

    return f"""You are an off-grid systems expert. Return ONLY valid JSON (no markdown fences, no commentary) matching the schema below.

LOCATION: {loc_str}
HOUSEHOLD: {r['people']} people, {r['monthly_kwh']} kWh/month
SOLAR: {s['required_wp']}W · {s['annual_ghi']} kWh/m²/day · {s['self_suff_pct']}% self-sufficient · ${s['cost']:,.0f}
BATTERY: {b['capacity_kwh']} kWh · {b['autonomy_days']}d autonomy · ${b['cost']:,.0f}
WATER: {w['coverage_pct']}% coverage · {w['tank_liters']:,}L tank · {w['annual_rain_mm']:.0f}mm/yr · ${w['cost']:,.0f}
FOOD: {f['coverage_pct']}% caloric coverage · {f['land_area']}m² · {f['grow_months']} grow months · ${f['cost']:,.0f}
CURRENT SCORE: {score}/100  |  TOTAL COST: ${total:,}  |  BUDGET: ${budget:,}

JSON schema (fill every field):
{{
  "one_liner": "<one bold sentence about this household's independence path>",
  "phase1": {{
    "title": "Quick Wins",
    "timeframe": "0–6 months",
    "budget": <integer USD>,
    "highlight": "<one sentence: what this phase achieves>",
    "score_after": <integer 0-100, must be > {score}>,
    "actions": [
      {{"icon": "<single emoji>", "title": "<short action>", "detail": "<specific product model or spec>", "cost": <integer USD>}}
    ]
  }},
  "phase2": {{
    "title": "Core System",
    "timeframe": "6–18 months",
    "budget": <integer USD>,
    "highlight": "<one sentence>",
    "score_after": <integer 0-100, must be > phase1 score_after>,
    "actions": [...]
  }},
  "phase3": {{
    "title": "Full Independence",
    "timeframe": "18–36 months",
    "budget": <integer USD>,
    "highlight": "<one sentence>",
    "score_after": <integer 0-100, must be > phase2 score_after>,
    "actions": [...]
  }},
  "risks": [
    {{"icon": "<emoji>", "risk": "<short risk title>", "mitigation": "<practical fix>", "severity": "high|medium|low"}}
  ],
  "products": [
    {{"category": "Solar|Battery|Water|Food", "icon": "<emoji>", "name": "<product name>", "why": "<1-sentence reason specific to {loc_str}>"}}
  ]
}}

Rules: max 4 actions per phase · exactly 3–4 risks · exactly 4 products (one per category: Solar, Battery, Water, Food) · scores must increase each phase · be specific to {loc_str} climate. Return ONLY the JSON object."""


def fetch_ai_plan(prompt: str) -> dict:
    import json as _json
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://github.com/Raghavk31/resilience-stack",
                "X-Title":       "30 Days of Climate Intelligence",
            },
            json={
                "model":    MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1800,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=90,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            lines = text.split("\n")
            inner = lines[1:] if lines[0].startswith("```") else lines
            text = "\n".join(l for l in inner if not l.strip().startswith("```"))
        return _json.loads(text)
    except Exception as e:
        return {"_error": str(e)}


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700;800;900&display=swap');

/* ── Global light reset ── */
html, body {
  background: #f4f3fb !important;
  color: #1e293b !important;
  font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stApp"] { background: #f4f3fb !important; }
[data-testid="stAppViewContainer"] { background: transparent !important; }
[data-testid="stMainBlockContainer"] { background: transparent !important; }
[data-testid="block-container"] { background: transparent !important; }
[data-testid="stVerticalBlock"] { background: transparent !important; }
[data-testid="stMarkdown"] { color: #1e293b; }
[data-testid="stMarkdown"] p, [data-testid="stMarkdown"] span,
[data-testid="stMarkdown"] li, [data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2, [data-testid="stMarkdown"] h3 {
  color: inherit !important;
}
[data-testid="stAlert"] { border-radius: 12px !important; }
[data-testid="stAlert"] p { color: #1e293b !important; }
[data-testid="stSpinner"] p { color: #475569 !important; }
[data-testid="stStatusWidget"] { color: #475569 !important; }

/* ── Base & pastel background ── */
#MainMenu, header, footer { visibility: hidden; }
section.main > div:first-child { padding-top: 0 !important; }
[data-testid="stAppViewBlockContainer"] { max-width: 100% !important; padding: 0 !important; }
section.main {
  background:
    radial-gradient(ellipse at 12% 14%, rgba(251,191,36,.22) 0%, transparent 50%),
    radial-gradient(ellipse at 88% 16%, rgba(167,139,250,.24) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 88%, rgba(96,165,250,.22) 0%, transparent 52%),
    radial-gradient(ellipse at 16% 84%, rgba(110,231,183,.20) 0%, transparent 50%),
    linear-gradient(135deg, #f7f5ff 0%, #fdf3ec 100%);
  font-family: 'Space Grotesk', sans-serif;
  min-height: 100vh;
  color: #1e293b;
}

/* ── Two-column frame ── */
[data-testid="stHorizontalBlock"]:has(.og-left) { gap: 0 !important; align-items: stretch !important; }

[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.42);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border-right: 1px solid rgba(255,255,255,.6);
  min-height: 100vh; max-height: 100vh;
  overflow-y: auto; position: sticky; top: 0;
  scrollbar-width: thin; scrollbar-color: rgba(15,23,42,.14) transparent;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar-thumb { background: rgba(15,23,42,.16); border-radius: 2px; }

[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:last-child {
  padding: 28px 32px !important; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: rgba(15,23,42,.14) transparent;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar-thumb { background: rgba(15,23,42,.16); border-radius: 2px; }

/* ── Left panel widget spacing ── */
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stNumberInput"],
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stSelectbox"],
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stSlider"] {
  padding: 4px 20px 15px !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] {
  padding: 0 20px 20px !important;
}

/* ── Buttons ── */
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
  width: 100% !important; border-radius: 12px !important;
  font-size: .82rem !important; font-weight: 700 !important; letter-spacing: .02em !important;
  padding: 11px 16px !important; transition: all .2s ease !important;
  font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%) !important;
  color: #0a0500 !important; border: none !important;
  box-shadow: 0 4px 20px rgba(245,158,11,.45), inset 0 1px 0 rgba(255,255,255,.25) !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #fcd34d 0%, #fbbf24 50%, #f59e0b 100%) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 30px rgba(245,158,11,.55), inset 0 1px 0 rgba(255,255,255,.3) !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button:not([kind="primary"]) {
  background: rgba(255,255,255,.55) !important; color: #475569 !important;
  border: 1px solid rgba(15,23,42,.1) !important;
  box-shadow: 0 2px 8px rgba(31,41,55,.06) !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button:not([kind="primary"]):hover {
  background: rgba(255,255,255,.8) !important; color: #1e293b !important;
}

/* ── Inputs ── */
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child input {
  background: rgba(255,255,255,.6) !important;
  border: 1px solid rgba(15,23,42,.12) !important;
  color: #1e293b !important;
  border-radius: 10px !important; font-size: .83rem !important;
  font-family: 'Space Grotesk', sans-serif !important;
  padding: 10px 13px !important; line-height: 1.5 !important; min-height: 42px !important;
  transition: all .18s !important;
}
/* Input wrapper (BaseWeb) — strip its own border so only the input shows */
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-baseweb="input"],
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-baseweb="base-input"] {
  background: transparent !important; border: none !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child input:focus {
  background: rgba(255,255,255,.9) !important;
  border-color: rgba(245,158,11,.6) !important;
  box-shadow: 0 0 0 3px rgba(245,158,11,.16), 0 0 16px rgba(245,158,11,.1) !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child input::placeholder { color: #94a3b8 !important; }

/* Selectbox */
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] > div:first-child {
  background: rgba(255,255,255,.6) !important;
  border: 1px solid rgba(15,23,42,.12) !important;
  border-radius: 10px !important; color: #1e293b !important;
  min-height: 42px !important; padding: 3px 6px !important;
}
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] div[value],
[data-testid="stHorizontalBlock"]:has(.og-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] span {
  font-size: .83rem !important; line-height: 1.5 !important;
}

/* Labels */
section.main [data-testid="stWidgetLabel"] { margin-bottom: 7px !important; }
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .7rem !important; font-weight: 700 !important;
  color: #64748b !important;
  letter-spacing: .06em !important; text-transform: uppercase !important;
  line-height: 1.5 !important;
}

/* ── Left panel HTML ── */
.og-left { display: none; }
.lp-pad  { padding: 22px 20px 14px; }
.lp-logo { font-size: 2.2rem; line-height: 1; margin-bottom: 10px;
  filter: drop-shadow(0 0 14px rgba(245,158,11,.55)); }
.lp-title { font-size: .95rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 6px; letter-spacing: -.1px; line-height: 1.3; }
.lp-desc  { font-size: .72rem; color: #64748b; line-height: 1.65; }
.ca-sep   { border: none; border-top: 1px solid rgba(15,23,42,.08); margin: 0; }
.lp-lbl   { font-size: .6rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase;
  color: #94a3b8; display: block; padding: 15px 20px 8px; line-height: 1.5; }

/* Location data box */
.lp-box {
  background: linear-gradient(135deg, rgba(251,191,36,.22) 0%, rgba(251,191,36,.08) 100%);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 14px; padding: 15px 16px; margin: 6px 20px 18px;
  border: 1px solid rgba(245,158,11,.32);
  box-shadow: 0 4px 20px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.lp-box-label { font-size: .58rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: #b45309; margin-bottom: 8px; }
.lp-box-loc   { font-size: .86rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 11px; line-height: 1.3; }
.lp-box-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.lp-stat      { background: rgba(255,255,255,.6); border: 1px solid rgba(255,255,255,.7); border-radius: 10px; padding: 9px 11px; }
.lp-stat-icon { font-size: .88rem; margin-bottom: 4px; }
.lp-stat-val  { font-size: .93rem; font-weight: 900; color: #0f172a; font-family: 'Space Grotesk', sans-serif; line-height: 1.1; }
.lp-stat-lbl  { font-size: .57rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-top: 2px; }

/* ── Result header ── */
.result-header {
  background: linear-gradient(135deg, rgba(251,191,36,.2) 0%, rgba(251,191,36,.07) 100%);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(245,158,11,.3);
  border-radius: 18px; padding: 15px 24px; margin-bottom: 22px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  box-shadow: 0 4px 24px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.rh-loc { font-size: .83rem; font-weight: 700; color: #334155; }
.rh-badge { font-size: .71rem; font-weight: 800; padding: 7px 16px; border-radius: 20px; white-space: nowrap; letter-spacing: .03em; backdrop-filter: blur(10px); }

/* ── Score section ── */
.score-micro-lbl { font-size: .6rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.score-headline { font-size: 4rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; color: #0f172a; line-height: 1.08; margin-bottom: 14px;
  text-shadow: 0 4px 24px rgba(245,158,11,.18); }
.score-sub { font-size: .74rem; color: #64748b; line-height: 1.65; max-width: 300px; margin-bottom: 2px; }
.score-label-chip { display: inline-block; margin-top: 12px; padding: 6px 16px; border-radius: 20px; font-size: .72rem; font-weight: 700; backdrop-filter: blur(10px); }

/* ── System cards ── */
.sys-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.sys-card {
  background: rgba(255,255,255,.55);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 20px; border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,41,55,.1), inset 0 1px 0 rgba(255,255,255,.6);
  overflow: hidden; transition: all .22s ease;
}
.sys-card:hover {
  background: rgba(255,255,255,.75); border-color: rgba(255,255,255,.9);
  box-shadow: 0 14px 44px rgba(31,41,55,.16), inset 0 1px 0 rgba(255,255,255,.7);
  transform: translateY(-3px);
}
.sys-bar { height: 3px; }
.sys-body { padding: 16px 16px 14px; }
.sys-icon-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.sys-icon-box { width: 40px; height: 40px; border-radius: 11px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; flex-shrink: 0; }
.sys-name { font-size: .69rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.sys-pct  { font-size: 2.2rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; line-height: 1.1; margin-bottom: 5px; }
.sys-pct-unit { font-size: .62rem; font-weight: 600; color: #64748b; margin-bottom: 10px; }
.sys-metric { font-size: .69rem; color: #475569; margin-bottom: 3px; display: flex; align-items: flex-start; gap: 6px; }
.sys-metric-dot { width: 4px; height: 4px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; opacity: .7; }
.sys-cost { display: inline-flex; align-items: center; gap: 4px; margin-top: 11px; padding: 4px 10px; border-radius: 8px; font-size: .69rem; font-weight: 700; }

/* ── Budget bar ── */
.budget-wrap {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 18px; border: 1px solid rgba(255,255,255,.7);
  padding: 18px 22px; margin-bottom: 22px;
  box-shadow: 0 4px 20px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.6);
}
.budget-title { font-size: .6rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: #64748b; margin-bottom: 12px; }
.budget-track { height: 8px; background: rgba(15,23,42,.08); border-radius: 6px; overflow: hidden; margin-bottom: 10px; }
.budget-fill  { height: 100%; border-radius: 6px; transition: width .7s ease; box-shadow: 0 0 8px currentColor; }
.budget-nums  { display: flex; justify-content: space-between; font-size: .7rem; color: #475569; }

/* ── Chart card ── */
.chart-card {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 20px; border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,41,55,.09), inset 0 1px 0 rgba(255,255,255,.6);
  margin-bottom: 22px; overflow: hidden;
}
.chart-head  { padding: 20px 24px 12px; }
.chart-title { font-size: .96rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 6px; line-height: 1.3; }
.chart-sub   { font-size: .72rem; color: #64748b; line-height: 1.5; margin-bottom: 0; }

/* ── Spec tiles ── */
.spec-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.spec-tile  {
  background: rgba(255,255,255,.5);
  border-radius: 14px; padding: 16px; border: 1px solid rgba(255,255,255,.7);
  backdrop-filter: blur(12px);
  box-shadow: 0 4px 16px rgba(31,41,55,.06);
}
.spec-icon  { font-size: 1.3rem; margin-bottom: 8px; }
.spec-val   { font-size: 1.4rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; color: #0f172a; line-height: 1.1; margin-bottom: 5px; }
.spec-unit  { font-size: .59rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; color: #64748b; margin-bottom: 5px; }
.spec-label { font-size: .69rem; color: #475569; line-height: 1.45; }

/* ── Warning pill ── */
.warn-pill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border-radius: 10px; font-size: .74rem; font-weight: 600; margin-bottom: 16px; backdrop-filter: blur(10px); }

/* ── Growing calendar ── */
.grow-cal { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-top: 14px; }
.gcm { border-radius: 10px; padding: 10px 6px; text-align: center; border: 1px solid rgba(15,23,42,.06); backdrop-filter: blur(8px); }
.gcm-name { font-size: .57rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; margin-bottom: 6px; }
.gcm-icon { font-size: 1.1rem; }

/* ── AI prompt card ── */
.ai-intro {
  background: linear-gradient(135deg, rgba(251,191,36,.18), rgba(251,191,36,.06));
  backdrop-filter: blur(20px); border: 1px solid rgba(245,158,11,.3);
  border-radius: 18px; padding: 20px 24px; margin-bottom: 22px;
  box-shadow: 0 4px 20px rgba(31,41,55,.08);
}
.ai-intro-title { font-size: 1.0rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 8px; line-height: 1.3; }
.ai-intro-desc  { font-size: .77rem; color: #475569; line-height: 1.65; }

/* ── AI Roadmap visual ── */
.ra-hero {
  background: linear-gradient(135deg, rgba(251,191,36,.2) 0%, rgba(251,191,36,.06) 100%);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(245,158,11,.3); border-radius: 18px;
  padding: 20px 24px; margin-bottom: 22px;
  display: flex; align-items: flex-start; gap: 16px;
  box-shadow: 0 4px 24px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.ra-hero-icon { font-size: 1.7rem; flex-shrink: 0; filter: drop-shadow(0 2px 6px rgba(245,158,11,.45)); }
.ra-hero-text { font-size: .88rem; font-weight: 600; color: #334155; line-height: 1.7; font-family: 'Space Grotesk', sans-serif; }

.ra-section-lbl { font-size: .59rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: #64748b; margin-bottom: 12px; margin-top: 8px; }

/* Phase cards */
.ra-phases { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 24px; }
.ra-phase-card {
  background: rgba(255,255,255,.55);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 18px; border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,41,55,.1), inset 0 1px 0 rgba(255,255,255,.6);
  padding: 18px; display: flex; flex-direction: column; gap: 10px;
  transition: all .22s ease;
}
.ra-phase-card:hover {
  background: rgba(255,255,255,.75); border-color: rgba(255,255,255,.9);
  box-shadow: 0 14px 44px rgba(31,41,55,.16), inset 0 1px 0 rgba(255,255,255,.7);
  transform: translateY(-3px);
}
.ra-phase-top  { display: flex; align-items: center; justify-content: space-between; }
.ra-phase-num  { font-size: .58rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; padding: 3px 10px; border-radius: 20px; }
.ra-phase-time { font-size: .63rem; font-weight: 600; color: #64748b; }
.ra-phase-title  { font-size: .9rem; font-weight: 800; font-family: 'Space Grotesk', sans-serif; color: #0f172a; }
.ra-phase-budget { font-size: 1.55rem; font-weight: 900; color: #0f172a; font-family: 'Space Grotesk', sans-serif; line-height: 1.1; }
.ra-phase-hl    { font-size: .7rem; color: #475569; line-height: 1.6; }

.ra-actions     { display: flex; flex-direction: column; gap: 7px; }
.ra-action      { display: flex; align-items: flex-start; gap: 9px; background: rgba(255,255,255,.55); border: 1px solid rgba(15,23,42,.06); border-radius: 10px; padding: 9px 10px; }
.ra-action-ic   { font-size: 1.0rem; flex-shrink: 0; margin-top: 1px; }
.ra-action-body { flex: 1; min-width: 0; }
.ra-action-title  { font-size: .71rem; font-weight: 700; color: #1e293b; margin-bottom: 2px; }
.ra-action-detail { font-size: .66rem; color: #64748b; line-height: 1.45; }
.ra-action-cost   { font-size: .7rem; font-weight: 800; white-space: nowrap; padding-top: 1px; }

.ra-score-bar      { height: 5px; background: rgba(15,23,42,.08); border-radius: 4px; overflow: hidden; }
.ra-score-bar-fill { height: 100%; border-radius: 4px; }
.ra-score-after    { font-size: .66rem; font-weight: 700; color: #64748b; }

/* Risk cards */
.ra-risks { display: flex; flex-direction: column; gap: 10px; }
.ra-risk-card {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 14px; border: 1px solid rgba(255,255,255,.7);
  padding: 14px 16px; box-shadow: 0 4px 16px rgba(31,41,55,.07);
}
.ra-risk-top   { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
.ra-risk-ic    { font-size: 1.0rem; flex-shrink: 0; }
.ra-risk-title { font-size: .75rem; font-weight: 700; color: #1e293b; flex: 1; }
.ra-risk-sev   { font-size: .57rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; padding: 2px 8px; border-radius: 10px; backdrop-filter: blur(10px); }
.ra-risk-mit   { font-size: .7rem; color: #475569; line-height: 1.55; }

/* Product cards */
.ra-products { display: flex; flex-direction: column; gap: 10px; }
.ra-product-card {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 14px; border: 1px solid rgba(255,255,255,.7);
  padding: 14px 16px; box-shadow: 0 4px 16px rgba(31,41,55,.07);
}
.ra-product-top  { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.ra-product-ic   { font-size: 1.2rem; flex-shrink: 0; }
.ra-product-cat  { font-size: .58rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 2px; }
.ra-product-name { font-size: .76rem; font-weight: 700; color: #1e293b; }
.ra-product-why  { font-size: .68rem; color: #475569; line-height: 1.55; }

/* ── Placeholder / empty state ── */
.ph-wrap  { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 72vh; gap: 22px; padding: 36px 24px; text-align: center; }
.ph-big   { font-size: 4.5rem; line-height: 1; filter: drop-shadow(0 6px 16px rgba(245,158,11,.35)); }
.ph-title { font-size: 1.2rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.2px; }
.ph-desc  { font-size: .8rem; color: #64748b; max-width: 380px; line-height: 1.75; }
.ph-chips { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; max-width: 500px; }
.ph-chip  {
  display: flex; align-items: center; gap: 6px; padding: 8px 14px;
  border-radius: 20px;
  background: rgba(255,255,255,.55);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 2px 10px rgba(31,41,55,.06);
  transition: all .2s ease;
}
.ph-chip:hover { background: rgba(255,255,255,.8); transform: translateY(-2px); box-shadow: 0 6px 18px rgba(31,41,55,.12); }
.ph-chip-icon { font-size: 1.0rem; }
.ph-chip-text { font-size: .72rem; font-weight: 600; color: #475569; }

/* ── Generic fallback: any input/select text ── */
input, textarea, select { color: #1e293b !important; }

/* ── Tabs ── */
[data-testid="stTabs"]        { background: transparent !important; }
[data-testid="stTabsContent"] { background: transparent !important; }
[data-testid="stTabs"] [role="tablist"] {
  background: rgba(255,255,255,.5) !important;
  backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important;
  border-radius: 12px !important; padding: 4px !important;
  border: 1px solid rgba(255,255,255,.7) !important; gap: 3px !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
  font-size: .77rem !important; font-weight: 600 !important;
  padding: 8px 14px !important; border-radius: 9px !important;
  color: #64748b !important;
  font-family: 'Space Grotesk', sans-serif !important;
  transition: all .18s !important;
  background: transparent !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
  color: #1e293b !important;
  background: rgba(255,255,255,.55) !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
  background: rgba(255,255,255,.85) !important;
  color: #0f172a !important; font-weight: 700 !important;
  box-shadow: 0 2px 10px rgba(31,41,55,.1), inset 0 1px 0 rgba(255,255,255,.7) !important;
}
[data-testid="stTabsContent"] { padding-top: 20px !important; }
[data-testid="stPlotlyChart"] { margin-bottom: 0 !important; }
</style>
"""


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _loc_label(loc: dict) -> str:
    s = loc["name"]
    if loc.get("admin1"):
        s += f", {loc['admin1']}"
    if loc.get("country"):
        s += f" · {loc['country']}"
    return s


def _left_box_html(loc: dict, ghi: float, annual_rain: float) -> str:
    return (
        f'<div class="lp-box">'
        f'<div class="lp-box-label">Location data loaded</div>'
        f'<div class="lp-box-loc">📍 {_loc_label(loc)}</div>'
        f'<div class="lp-box-grid">'
        f'<div class="lp-stat"><div class="lp-stat-icon">☀️</div>'
        f'<div class="lp-stat-val">{ghi}</div>'
        f'<div class="lp-stat-lbl">kWh/m²/day GHI</div></div>'
        f'<div class="lp-stat"><div class="lp-stat-icon">🌧️</div>'
        f'<div class="lp-stat-val">{annual_rain:.0f}mm</div>'
        f'<div class="lp-stat-lbl">Annual rainfall</div></div>'
        f'</div></div>'
    )


def _empty_state_html() -> str:
    chips = [
        ("☀️", "Solar sizing"),
        ("🔋", "Battery storage"),
        ("💧", "Water harvesting"),
        ("🌱", "Food production"),
        ("🤖", "AI roadmap"),
    ]
    chips_html = "".join(
        f'<div class="ph-chip"><span class="ph-chip-icon">{ic}</span>'
        f'<span class="ph-chip-text">{tx}</span></div>'
        for ic, tx in chips
    )
    return (
        f'<div class="ph-wrap">'
        f'<div class="ph-big">⚡</div>'
        f'<div class="ph-title">Design Your Off-Grid System</div>'
        f'<div class="ph-desc">Enter your location and household details, then hit Calculate to get a custom solar, water and food system — plus your Independence Score.</div>'
        f'<div class="ph-chips">{chips_html}</div>'
        f'</div>'
    )


def _score_label(score: int) -> tuple[str, str, str]:
    if score >= 75:
        return "High Independence", "#15803d", "rgba(34,197,94,.18)"
    if score >= 50:
        return "On Track", "#b45309", "rgba(245,158,11,.2)"
    if score >= 25:
        return "Early Stage", "#c2410c", "rgba(249,115,22,.18)"
    return "Getting Started", "#dc2626", "rgba(239,68,68,.16)"


def _score_gauge(score: int) -> go.Figure:
    label, color, _ = _score_label(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        number={"font": {"size": 36, "family": "Space Grotesk", "color": "#0f172a"}, "suffix": ""},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "rgba(0,0,0,0)", "showticklabels": False},
            "bar":  {"color": color, "thickness": 0.28},
            "bgcolor": "rgba(15,23,42,.05)",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  25], "color": "rgba(239,68,68,.14)"},
                {"range": [25, 50], "color": "rgba(245,158,11,.14)"},
                {"range": [50, 75], "color": "rgba(245,158,11,.14)"},
                {"range": [75,100], "color": "rgba(34,197,94,.14)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(
        height=210,
        margin=dict(l=8, r=8, t=22, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Space Grotesk"},
    )
    return fig


def _sys_card_html(icon: str, name: str, pct: float, pct_unit: str,
                   metrics: list[str], cost: float, color: str) -> str:
    dots = "".join(
        f'<div class="sys-metric">'
        f'<span class="sys-metric-dot" style="background:{color}"></span>{m}</div>'
        for m in metrics
    )
    return (
        f'<div class="sys-card">'
        f'<div class="sys-bar" style="background:{color}"></div>'
        f'<div class="sys-body">'
        f'<div class="sys-icon-row">'
        f'<div class="sys-icon-box" style="background:{color}18">{icon}</div>'
        f'<div class="sys-name" style="color:{color}">{name}</div>'
        f'</div>'
        f'<div class="sys-pct" style="color:{color}">{pct:.0f}</div>'
        f'<div class="sys-pct-unit">{pct_unit}</div>'
        f'{dots}'
        f'<div class="sys-cost" style="background:{color}12;color:{color}">💰 ${cost:,.0f}</div>'
        f'</div></div>'
    )


def _spec_tile_html(icon: str, val: str, unit: str, label: str) -> str:
    return (
        f'<div class="spec-tile">'
        f'<div class="spec-icon">{icon}</div>'
        f'<div class="spec-val">{val}</div>'
        f'<div class="spec-unit">{unit}</div>'
        f'<div class="spec-label">{label}</div>'
        f'</div>'
    )


def _monthly_chart(title: str, sub: str,
                   bar_vals: list, bar_name: str, bar_color: str,
                   line_val: float, line_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=MONTHS, y=bar_vals,
        name=bar_name,
        marker_color=bar_color,
        marker_line_width=0,
    ))
    fig.add_trace(go.Scatter(
        x=MONTHS, y=[line_val] * 12,
        name=line_name,
        line=dict(color="#ef4444", width=2, dash="dash"),
        mode="lines",
    ))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=240,
        margin=dict(l=0, r=0, t=8, b=0),
        legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11, color="#475569")),
        yaxis=dict(gridcolor="rgba(15,23,42,.08)", zeroline=False, tickfont=dict(size=11, color="#64748b")),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11, color="#64748b")),
        font=dict(family="Space Grotesk"),
        bargap=0.32,
    )
    return fig


def _budget_html(total_cost: float, budget: float) -> str:
    pct = min(100, round(total_cost / max(budget, 1) * 100))
    over = total_cost > budget
    fill_color = "#ef4444" if over else "#f59e0b"
    status = f"⚠️ ${total_cost - budget:,.0f} over budget" if over else f"✅ ${budget - total_cost:,.0f} remaining"
    status_color = "#dc2626" if over else "#15803d"
    return (
        f'<div class="budget-wrap">'
        f'<div class="budget-title">Budget Overview</div>'
        f'<div class="budget-track">'
        f'<div class="budget-fill" style="width:{pct}%;background:{fill_color}"></div>'
        f'</div>'
        f'<div class="budget-nums">'
        f'<span style="color:#475569">Total cost: <strong style="color:#0f172a">${total_cost:,.0f}</strong></span>'
        f'<span style="color:{status_color};font-weight:700">{status}</span>'
        f'</div>'
        f'</div>'
    )


# ── Tab renderers ─────────────────────────────────────────────────────────────

def _render_overview(r: dict) -> None:
    s, b, w, f = r["solar"], r["battery"], r["water"], r["food"]
    score = r["score"]
    label, color, bg = _score_label(score)

    # Score row
    col_g, col_info = st.columns([1, 2.4])
    with col_g:
        st.plotly_chart(_score_gauge(score), use_container_width=True, config={"displayModeBar": False})
    with col_info:
        st.markdown(
            f'<div style="padding-top:14px">'
            f'<div class="score-micro-lbl">Independence Score</div>'
            f'<div class="score-headline">{score}<span style="font-size:1.4rem;color:#94a3b8;font-weight:500">/100</span></div>'
            f'<div class="score-sub">Weighted: 40% energy · 30% water · 30% food</div>'
            f'<span class="score-label-chip" style="background:{bg};color:{color};border:1px solid {color}28">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="sys-grid">'
        + _sys_card_html("☀️", "Solar", s["self_suff_pct"], "% self-sufficient",
                         [f"{s['required_wp']:,}W · {s['num_panels']} panels",
                          f"{s['annual_gen_kwh']:,.0f} kWh/year",
                          f"{s['panel_area_m2']}m² roof needed"],
                         s["cost"], "#d97706")
        + _sys_card_html("🔋", "Battery", min(100.0, b["autonomy_days"] / 7 * 100), f"{b['autonomy_days']}d autonomy",
                         [f"{b['capacity_kwh']} kWh capacity",
                          f"{b['num_units']} × 5.12 kWh units",
                          f"{b['daily_kwh']} kWh/day use"],
                         b["cost"], "#7c3aed")
        + _sys_card_html("💧", "Water", w["coverage_pct"], "% needs covered",
                         [f"{w['tank_liters']:,}L tank size",
                          f"{w['annual_rain_mm']:.0f}mm/yr rainfall",
                          f"{w['daily_liters']:,}L/day household"],
                         w["cost"], "#2563eb")
        + _sys_card_html("🌱", "Food", f["coverage_pct"], "% caloric coverage",
                         [f"{f['land_area']:,.0f}m² available",
                          f"{f['required_m2']:,}m² for 100%",
                          f"{f['grow_months']} growing months/yr"],
                         f["cost"], "#16a34a")
        + '</div>',
        unsafe_allow_html=True,
    )

    total = int(s["cost"] + b["cost"] + w["cost"] + f["cost"])
    st.markdown(_budget_html(total, r["budget"]), unsafe_allow_html=True)


def _render_solar_tab(r: dict) -> None:
    s, b = r["solar"], r["battery"]

    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">☀️ Solar System Design</div>'
        f'<div class="chart-sub">Annual GHI: {s["annual_ghi"]} kWh/m²/day · Source: {s["ghi_source"]}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    specs = [
        _spec_tile_html("🔆", f"{s['required_wp']:,}", "Wp", f"{s['num_panels']} × 400W panels"),
        _spec_tile_html("📐", f"{s['panel_area_m2']}", "m²", f"{s['roof_pct']}% of your roof"),
        _spec_tile_html("⚡", f"{s['annual_gen_kwh']:,.0f}", "kWh/yr", f"{s['self_suff_pct']}% self-sufficient"),
    ]
    st.markdown('<div style="padding:18px 22px 0"><div class="spec-grid">' + "".join(specs) + "</div></div>",
                unsafe_allow_html=True)

    if not s["fits_roof"]:
        st.markdown(
            f'<div style="padding:0 22px"><div class="warn-pill" style="background:rgba(245,158,11,.16);color:#b45309;border:1px solid rgba(245,158,11,.3)">'
            f'⚠️ Panel area ({s["panel_area_m2"]}m²) exceeds your roof ({r["roof_area"] if "roof_area" in r else "?"}m²) — '
            f'consider ground mount or reducing system size.</div></div>',
            unsafe_allow_html=True,
        )

    gen_vals = [s["monthly_gen"][m] for m in range(1, 13)]
    fig = _monthly_chart(
        "Monthly Solar Generation vs Demand", "",
        gen_vals, "Generation (kWh)", "#f59e0b",
        r["monthly_kwh"], "Monthly Demand",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">🔋 Battery Storage</div>'
        f'<div class="chart-sub">{b["autonomy_days"]}-day autonomy · LiFePO4 chemistry (80% DoD, 95% roundtrip)</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    bat_specs = [
        _spec_tile_html("🔋", f"{b['capacity_kwh']}", "kWh", f"{b['num_units']} × 5.12 kWh units"),
        _spec_tile_html("🌙", f"{b['autonomy_days']}", "days", "Without solar input"),
        _spec_tile_html("💰", f"${b['cost']:,.0f}", "USD", "Installed LiFePO4 cost"),
    ]
    st.markdown('<div style="padding:18px 22px 22px"><div class="spec-grid">' + "".join(bat_specs) + "</div></div>",
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_water_tab(r: dict) -> None:
    w = r["water"]
    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">💧 Water Harvesting System</div>'
        f'<div class="chart-sub">{w["annual_rain_mm"]:.0f}mm annual rainfall · {w["daily_liters"]:,}L/day household need · 85% collection coefficient</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    water_specs = [
        _spec_tile_html("🏠", f"{w['tank_liters']:,}", "L", "Recommended tank size"),
        _spec_tile_html("💧", f"{w['coverage_pct']:.0f}%", "covered", f"{w['annual_coll']:,.0f}L collected/yr"),
        _spec_tile_html("💰", f"${w['cost']:,.0f}", "USD", "Tank + filtration installed"),
    ]
    st.markdown('<div style="padding:18px 22px 0"><div class="spec-grid">' + "".join(water_specs) + "</div></div>",
                unsafe_allow_html=True)

    coll_vals = [w["monthly_coll"][m] for m in range(1, 13)]
    fig = _monthly_chart(
        "Monthly Collection vs Household Need", "",
        coll_vals, "Collected (L)", "#3b82f6",
        w["monthly_need"][1], "Monthly Need",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    deficit_months = [MONTHS[m-1] for m, d in w["monthly_def"].items() if d > 0]
    if deficit_months:
        st.markdown(
            f'<div style="padding:0 22px 22px"><div class="warn-pill" style="background:rgba(96,165,250,.16);color:#2563eb;border:1px solid rgba(37,99,235,.3)">'
            f'⚠️ Deficit months: {", ".join(deficit_months)} — tank storage bridges these gaps.</div></div>',
            unsafe_allow_html=True,
        )


def _render_food_tab(r: dict) -> None:
    f = r["food"]
    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">🌱 Food Production System</div>'
        f'<div class="chart-sub">{f["grow_months"]} growing months · {f["m2_per_person"]}m² required per person · intensive organic methods</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    food_specs = [
        _spec_tile_html("🌿", f"{f['coverage_pct']:.0f}%", "caloric coverage", f"{f['land_area']:,.0f}m² available"),
        _spec_tile_html("📏", f"{f['required_m2']:,}", "m² for 100%", f"{r['people']} people @ {f['m2_per_person']}m²/person"),
        _spec_tile_html("💰", f"${f['cost']:,.0f}", "USD", "Beds, irrigation & seeds"),
    ]
    st.markdown('<div style="padding:18px 22px 8px"><div class="spec-grid">' + "".join(food_specs) + "</div></div>",
                unsafe_allow_html=True)

    # Growing calendar — 12 months colored by temperature
    temp_m = f["temp_monthly"]
    def grow_style(t: float) -> tuple[str, str, str]:
        if t >= 18:
            return "rgba(34,197,94,.18)", "#15803d", "🌿"
        if t >= 10:
            return "rgba(245,158,11,.2)", "#b45309", "🌱"
        if t >= 5:
            return "rgba(100,116,139,.16)", "#475569", "🥶"
        return "rgba(100,116,139,.1)", "#64748b", "❄️"

    cal_html = '<div style="padding:0 22px 22px"><div style="font-size:.65rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#94a3b8;margin-bottom:10px">Growing Calendar</div><div class="grow-cal">'
    for m in range(1, 13):
        t = temp_m.get(m, 15.0)
        bg, col, icon = grow_style(t)
        cal_html += (
            f'<div class="gcm" style="background:{bg}">'
            f'<div class="gcm-name" style="color:{col}">{MONTHS[m-1]}</div>'
            f'<div class="gcm-icon">{icon}</div>'
            f'<div style="font-size:.65rem;font-weight:700;color:{col};margin-top:4px">{t:.0f}°C</div>'
            f'</div>'
        )
    cal_html += "</div></div>"
    st.markdown(cal_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _score_journey_chart(score: int, data: dict) -> go.Figure:
    labels = ["Now", "Phase 1", "Phase 2", "Phase 3"]
    values = [
        score,
        data["phase1"]["score_after"],
        data["phase2"]["score_after"],
        data["phase3"]["score_after"],
    ]
    dot_colors = ["#94a3b8", "#d97706", "#7c3aed", "#16a34a"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        fill="tozeroy", fillcolor="rgba(245,158,11,.12)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=values,
        mode="lines+markers+text",
        line=dict(color="#d97706", width=2.5, shape="spline"),
        marker=dict(size=14, color=dot_colors, line=dict(color="#ffffff", width=2.5)),
        text=[str(v) for v in values],
        textposition="top center",
        textfont=dict(size=13, family="Space Grotesk", color="#0f172a"),
        showlegend=False,
        hovertemplate="%{x}: %{y}/100<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=170,
        margin=dict(l=10, r=10, t=32, b=10),
        yaxis=dict(range=[0, min(115, max(values) + 16)], showgrid=False, showticklabels=False, zeroline=False),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=12, family="Space Grotesk", color="#64748b")),
        font=dict(family="Space Grotesk"),
    )
    return fig


def _phase_card_html(p: dict, num: int, color: str) -> str:
    actions = "".join(
        f'<div class="ra-action">'
        f'<span class="ra-action-ic">{a["icon"]}</span>'
        f'<div class="ra-action-body">'
        f'<div class="ra-action-title">{a["title"]}</div>'
        f'<div class="ra-action-detail">{a["detail"]}</div>'
        f'</div>'
        f'<div class="ra-action-cost" style="color:{color}">${a["cost"]:,}</div>'
        f'</div>'
        for a in p.get("actions", [])
    )
    return (
        f'<div class="ra-phase-card" style="border-top:3px solid {color}">'
        f'<div class="ra-phase-top">'
        f'<div class="ra-phase-num" style="background:{color}1a;color:{color}">Phase {num}</div>'
        f'<div class="ra-phase-time">{p["timeframe"]}</div>'
        f'</div>'
        f'<div class="ra-phase-title" style="color:{color}">{p["title"]}</div>'
        f'<div class="ra-phase-budget">${p["budget"]:,}</div>'
        f'<div class="ra-phase-hl">{p["highlight"]}</div>'
        f'<div class="ra-actions">{actions}</div>'
        f'<div class="ra-score-bar"><div class="ra-score-bar-fill" style="width:{p["score_after"]}%;background:{color}"></div></div>'
        f'<div class="ra-score-after" style="color:{color}">Score → {p["score_after"]}/100</div>'
        f'</div>'
    )


def _render_ai_tab(r: dict) -> None:
    score = r["score"]

    if "og_ai_data" in st.session_state and st.session_state["og_ai_data"]:
        data = st.session_state["og_ai_data"]
        if "_error" in data:
            st.error(f"AI generation failed — {data['_error']}")
        else:
            # Hero one-liner
            one_liner = data.get("one_liner", "")
            if one_liner:
                st.markdown(
                    f'<div class="ra-hero"><div class="ra-hero-icon">🤖</div>'
                    f'<div class="ra-hero-text">{one_liner}</div></div>',
                    unsafe_allow_html=True,
                )

            # Score journey chart
            st.markdown('<div class="ra-section-lbl">Score Journey</div>', unsafe_allow_html=True)
            st.plotly_chart(_score_journey_chart(score, data), use_container_width=True,
                            config={"displayModeBar": False})

            # Phase cards
            st.markdown('<div class="ra-section-lbl">Implementation Roadmap</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="ra-phases">'
                + _phase_card_html(data["phase1"], 1, "#d97706")
                + _phase_card_html(data["phase2"], 2, "#7c3aed")
                + _phase_card_html(data["phase3"], 3, "#16a34a")
                + '</div>',
                unsafe_allow_html=True,
            )

            # Risks + Products side by side
            col_r, col_p = st.columns([1, 1])
            with col_r:
                st.markdown('<div class="ra-section-lbl">Key Risks</div>', unsafe_allow_html=True)
                sev_clr = {"high": "#dc2626", "medium": "#b45309", "low": "#15803d"}
                risks_html = '<div class="ra-risks">'
                for risk in data.get("risks", []):
                    sc = sev_clr.get(risk.get("severity", "medium"), "#b45309")
                    risks_html += (
                        f'<div class="ra-risk-card">'
                        f'<div class="ra-risk-top">'
                        f'<span class="ra-risk-ic">{risk.get("icon","⚠️")}</span>'
                        f'<div class="ra-risk-title">{risk["risk"]}</div>'
                        f'<span class="ra-risk-sev" style="background:{sc}18;color:{sc}">{risk.get("severity","medium")}</span>'
                        f'</div>'
                        f'<div class="ra-risk-mit">✅ {risk["mitigation"]}</div>'
                        f'</div>'
                    )
                risks_html += '</div>'
                st.markdown(risks_html, unsafe_allow_html=True)

            with col_p:
                st.markdown('<div class="ra-section-lbl">Top Product Picks</div>', unsafe_allow_html=True)
                cat_clr = {"Solar": "#d97706", "Battery": "#7c3aed", "Water": "#2563eb", "Food": "#16a34a"}
                prods_html = '<div class="ra-products">'
                for prod in data.get("products", []):
                    pc = cat_clr.get(prod.get("category", ""), "#64748b")
                    prods_html += (
                        f'<div class="ra-product-card" style="border-left:3px solid {pc}">'
                        f'<div class="ra-product-top">'
                        f'<span class="ra-product-ic">{prod.get("icon","🔧")}</span>'
                        f'<div>'
                        f'<div class="ra-product-cat" style="color:{pc}">{prod.get("category","")}</div>'
                        f'<div class="ra-product-name">{prod["name"]}</div>'
                        f'</div></div>'
                        f'<div class="ra-product-why">{prod["why"]}</div>'
                        f'</div>'
                    )
                prods_html += '</div>'
                st.markdown(prods_html, unsafe_allow_html=True)

        if st.button("Regenerate Plan", key="og_ai_regen"):
            st.session_state.pop("og_ai_data", None)
            st.rerun()
    else:
        if not OPENROUTER_KEY:
            st.warning("Set OPENROUTER_API_KEY to enable AI roadmap generation.")
            return
        st.markdown(
            f'<div class="ai-intro">'
            f'<div class="ai-intro-title">🤖 AI Implementation Roadmap</div>'
            f'<div class="ai-intro-desc">'
            f'Score: {score}/100 · Claude will generate a visual, phased plan specific to {r["loc"]["name"]} — '
            f'with score projections, product picks, and risk cards.'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Generate My Roadmap", type="primary", key="og_ai_gen"):
            with st.spinner("Claude is designing your roadmap…"):
                data = fetch_ai_plan(build_roadmap_prompt(r))
            st.session_state["og_ai_data"] = data
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    left, right = st.columns([1, 2.5], gap="medium")

    with left:
        st.markdown('<div class="og-left"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="lp-pad">'
            '<div class="lp-logo">⚡</div>'
            '<div class="lp-title">Off-Grid Independence</div>'
            '<div class="lp-desc">Design your solar, water &amp; food systems — get an independence score and AI roadmap.</div>'
            '</div><hr class="ca-sep"/>',
            unsafe_allow_html=True,
        )

        st.markdown('<span class="lp-lbl">Location</span>', unsafe_allow_html=True)
        loc_input = st.text_input("Location", placeholder="e.g. Nairobi, Kenya",
                                   label_visibility="collapsed", key="og_loc_input")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Household</span>', unsafe_allow_html=True)
        people    = st.number_input("Number of people", 1, 20, 4, key="og_people")
        home_type = st.selectbox("Home type", ["House", "Apartment", "Small farm", "Large farm"], key="og_home")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Energy</span>', unsafe_allow_html=True)
        monthly_kwh = st.number_input("Monthly electricity use (kWh)", 10, 5000, 300, step=10, key="og_kwh")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Water &amp; Food</span>', unsafe_allow_html=True)
        roof_area = st.number_input("Roof catchment area (m²)", 10, 2000, 80, step=5, key="og_roof")
        land_area = st.number_input("Available growing land (m²)", 0, 50000, 200, step=10, key="og_land")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Battery Target</span>', unsafe_allow_html=True)
        autonomy = st.slider("Days autonomy without sun", 1, 7, 3, key="og_auto")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Budget</span>', unsafe_allow_html=True)
        budget = st.number_input("Total available budget (USD)", 500, 500000, 15000, step=500, key="og_budget")

        st.markdown('<hr class="ca-sep"/>', unsafe_allow_html=True)
        calc_btn = st.button("Calculate My System", type="primary", key="og_calc")

        if "og_result" in st.session_state:
            res = st.session_state["og_result"]
            st.markdown(
                _left_box_html(res["loc"], res["solar"]["annual_ghi"], res["climate"]["annual_rain"]),
                unsafe_allow_html=True,
            )

    with right:
        if "og_result" not in st.session_state:
            st.markdown(_empty_state_html(), unsafe_allow_html=True)
        else:
            res = st.session_state["og_result"]
            _s = res["score"]
            _sl, _sc, _sbg = _score_label(_s)
            st.markdown(
                f'<div class="result-header">'
                f'<div class="rh-loc">📍 <strong>{_loc_label(res["loc"])}</strong></div>'
                f'<div class="rh-badge" style="background:{_sbg};color:{_sc};border:1px solid {_sc}38">'
                f'{_s}/100 &nbsp;·&nbsp; {_sl}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            t1, t2, t3, t4, t5 = st.tabs(
                ["Overview", "☀️ Solar & Battery", "💧 Water", "🌱 Food", "🤖 AI Roadmap"]
            )
            with t1:
                _render_overview(res)
            with t2:
                _render_solar_tab(res)
            with t3:
                _render_water_tab(res)
            with t4:
                _render_food_tab(res)
            with t5:
                _render_ai_tab(res)

    if calc_btn:
        if not loc_input.strip():
            st.warning("Please enter a location first.")
            return
        with right:
            with st.spinner("Fetching solar & climate data…"):
                loc = geocode(loc_input.strip())
                if not loc:
                    st.error(f"Could not find '{loc_input}'. Try a different city name.")
                    return

                with ThreadPoolExecutor(max_workers=2) as pool:
                    solar_f   = pool.submit(fetch_solar_ghi,    loc["lat"], loc["lon"])
                    climate_f = pool.submit(fetch_climate_rain, loc["lat"], loc["lon"])
                    solar   = solar_f.result()
                    climate = climate_f.result()

                s_calc = calc_solar(monthly_kwh, solar, roof_area)
                b_calc = calc_battery(monthly_kwh, autonomy)
                w_calc = calc_water(people, climate, roof_area)
                f_calc = calc_food(people, land_area, climate)
                score  = independence_score(
                    s_calc["self_suff_pct"],
                    w_calc["coverage_pct"],
                    f_calc["coverage_pct"],
                )

                st.session_state["og_result"] = {
                    "loc":        loc,
                    "solar":      s_calc,
                    "battery":    b_calc,
                    "water":      w_calc,
                    "food":       f_calc,
                    "score":      score,
                    "budget":     budget,
                    "monthly_kwh": monthly_kwh,
                    "people":     people,
                    "home_type":  home_type,
                    "roof_area":  roof_area,
                    "climate":    climate,
                }
                st.session_state.pop("og_ai_data", None)
                st.rerun()


if __name__ == "__main__":
    main()
