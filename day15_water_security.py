"""
The Resilience Stack — Day 15
Water Security Planner

Location + roof + household → personalised rainwater harvesting and
greywater recycling plan, with a water-balance simulation, a Water
Security Score, and an AI-generated implementation roadmap.
"""

import math
import os
import pathlib

import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Water Security Planner · Day 15",
    page_icon="💧",
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
HEADERS     = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

MONTHS    = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
DAYS_MO   = 30.4

# ── Domain constants ───────────────────────────────────────────────────────────
PROFILES = {
    "Conservative (80 L)": 80,
    "Average (130 L)":     130,
    "High (200 L)":        200,
}

ROOF_RUNOFF = {
    "Metal / steel":         0.90,
    "Tile (clay/concrete)":  0.85,
    "Asphalt shingle":       0.80,
    "Flat concrete":         0.80,
    "Green roof":            0.35,
}

GW_SYSTEMS = {
    "None":                                0.00,
    "Simple diversion → garden":           0.45,
    "Treated recycling → toilet + garden": 0.65,
}

FIRST_FLUSH_EFF = 0.90   # collection efficiency after gutters + first-flush diverter
GARDEN_L_PER_M2 = 3.0    # average daily irrigation demand (L/m²/day)

# End-use shares of indoor demand (sum = 1.00)
F_TOILET  = 0.28         # non-potable, greywater can offset
F_GREYGEN = 0.50         # shower + laundry + basin → produces greywater
F_POTABLE_INDOOR = 0.45  # drinking, cooking, bathing, basin → must be potable-grade
                         # (the rest of indoor — toilet + laundry — and all garden is non-potable)

# Costs (USD)
# Storage cost falls with volume: small poly tanks are dear per litre, bulk
# ferrocement/HDPE is cheap. Tiers are (upper litre bound, $/L within that tier).
TANK_COST_TIERS = [(5000, 0.40), (20000, 0.22), (float("inf"), 0.12)]
PRACTICAL_TANK_L    = 10000  # largest common single tank; above this, split into N units
COST_COLLECTION     = 350    # gutters, mesh, first-flush diverter
COST_FILTRATION     = 600    # sediment + carbon + UV (potable-grade)
COST_PUMP           = 250
COST_GW = {
    "None":                                0,
    "Simple diversion → garden":           250,
    "Treated recycling → toilet + garden": 1600,
}


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
def fetch_climate_rain(lat: float, lon: float) -> dict:
    """Monthly rainfall (mm) averaged over 2019–2023 from Open-Meteo archive."""
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude":   lat, "longitude": lon,
                "start_date": "2019-01-01", "end_date": "2023-12-31",
                "daily":      "precipitation_sum",
                "timezone":   "auto",
            },
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        daily = r.json().get("daily", {})
        dates = daily.get("time", [])
        prec  = daily.get("precipitation_sum", [])

        rain_b: dict[int, list] = {m: [] for m in range(1, 13)}
        for i, date in enumerate(dates):
            m = int(date[5:7])
            if i < len(prec) and prec[i] is not None:
                rain_b[m].append(float(prec[i]))

        # avg daily mm in month × days/month = avg monthly total mm
        rain_monthly = {
            m: round(sum(v) / len(v) * DAYS_MO, 1) if v else 40.0
            for m, v in rain_b.items()
        }
        return {
            "rain_monthly": rain_monthly,
            "annual_rain":  round(sum(rain_monthly.values()), 0),
            "source":       "Open-Meteo ERA5",
        }
    except Exception:
        return {
            "rain_monthly": {m: 40.0 for m in range(1, 13)},
            "annual_rain":  480.0,
            "source":       "estimate",
        }


# ── Calculations ──────────────────────────────────────────────────────────────

def _simulate(coll: dict, demand: dict, cap: float, cycles: int = 4) -> tuple[float, int, float]:
    """Roll a storage tank through the year. Returns
    (rain supplied/yr, deficit months, overflow/yr) at steady state."""
    tank = 0.0
    supplied = deficit_months = 0
    overflow = 0.0
    for _ in range(cycles):
        supplied, overflow, deficit_months = 0.0, 0.0, 0
        for m in range(1, 13):
            tank += coll[m]
            if tank > cap:
                overflow += tank - cap
                tank = cap
            use = min(tank, demand[m])
            supplied += use
            tank -= use
            if use < demand[m] - 1:
                deficit_months += 1
    return supplied, deficit_months, overflow


def _tank_cost(liters: float) -> float:
    """Tiered storage cost — cheaper per litre at higher volume."""
    cost, prev = 0.0, 0.0
    for cap, rate in TANK_COST_TIERS:
        vol = min(liters, cap) - prev
        if vol <= 0:
            break
        cost += vol * rate
        prev = cap
    return cost


def plan_water(people: int, per_capita: int, roof_area: float,
               runoff: float, garden_area: float, gw_system: str,
               climate: dict) -> dict:
    rain_m = climate["rain_monthly"]

    # ── Demand ──
    indoor_daily = people * per_capita
    garden_daily = garden_area * GARDEN_L_PER_M2
    total_daily  = indoor_daily + garden_daily
    annual_demand = total_daily * 365

    # ── Greywater ──
    grey_gen_daily = indoor_daily * F_GREYGEN
    gw_eff = GW_SYSTEMS[gw_system]
    if gw_system.startswith("Simple"):
        offsettable = garden_daily
    elif gw_system.startswith("Treated"):
        offsettable = indoor_daily * F_TOILET + garden_daily
    else:
        offsettable = 0.0
    grey_usable_daily = min(grey_gen_daily * gw_eff, offsettable)

    # ── Rainwater (monthly collection vs the demand left after greywater) ──
    monthly_coll = {
        m: round(rain_m[m] * roof_area * runoff * FIRST_FLUSH_EFF, 0)
        for m in range(1, 13)
    }
    annual_coll = sum(monthly_coll.values())

    remaining_daily   = max(0.0, total_daily - grey_usable_daily)
    annual_remaining  = remaining_daily * 365
    supply_limited    = annual_coll < annual_remaining

    # Steady "draw" the system can sustain: you can only draw, on average,
    # what the roof actually collects. Cap demand at the collectable supply so
    # tank sizing stays finite (an undersized roof can't be fixed by a bigger tank).
    draw_daily   = min(remaining_daily, 0.95 * annual_coll / 365)
    monthly_draw = {m: draw_daily * DAYS_MO for m in range(1, 13)}

    # The monthly "need" the table and chart show is the sustainable draw the tank
    # is actually sized against — not the full post-greywater demand. Comparing
    # collection to the draw keeps the monthly balance, the deficit list, and the
    # tank simulation telling one story (otherwise an undersized roof flags every
    # month as a deficit while the simulation reports only the dry ones).
    monthly_rain_need = {m: round(monthly_draw[m], 0) for m in range(1, 13)}

    # Tank sizing — Rippl mass-curve: storage needed to bridge the dry season
    # for the sustainable draw. Run two cycles so a dry run spanning the year
    # boundary is captured. Floor at 14 days of draw, cap at annual collection.
    deficit = max_def = 0.0
    for _ in range(2):
        for m in range(1, 13):
            deficit = max(0.0, deficit + monthly_draw[m] - monthly_coll[m])
            max_def = max(max_def, deficit)
    tank_l = max(draw_daily * 14, max_def)
    tank_l = min(tank_l, annual_coll)
    tank_l = max(1000, math.ceil(tank_l / 500) * 500)

    rain_supplied, deficit_months, overflow = _simulate(monthly_coll, monthly_draw, tank_l)
    rain_supplied = min(rain_supplied, annual_remaining)

    # ── Coverage & score ──
    grey_annual = grey_usable_daily * 365
    covered     = grey_annual + rain_supplied
    coverage_pct = min(100.0, round(covered / max(annual_demand, 1) * 100, 1))
    grey_pct     = round(grey_annual / max(annual_demand, 1) * 100, 1)
    rain_pct     = round(rain_supplied / max(annual_demand, 1) * 100, 1)

    # ── Potable vs non-potable coverage ──
    # Greywater is non-potable only (toilet/laundry/garden). Filtered rainwater
    # can serve potable demand, so allocate greywater to non-potable first, then
    # rainwater to potable first (highest-value use), spilling any surplus onto
    # the non-potable demand greywater didn't reach.
    potable_daily  = indoor_daily * F_POTABLE_INDOOR
    nonpot_daily   = total_daily - potable_daily
    potable_annual = potable_daily * 365
    nonpot_annual  = nonpot_daily * 365

    np_from_grey  = min(grey_annual, nonpot_annual)
    pot_from_rain = min(rain_supplied, potable_annual)
    np_from_rain  = min(rain_supplied - pot_from_rain, nonpot_annual - np_from_grey)

    potable_pct = round(min(100.0, pot_from_rain / max(potable_annual, 1) * 100), 1)
    nonpot_pct  = round(min(100.0, (np_from_grey + np_from_rain) / max(nonpot_annual, 1) * 100), 1)

    tank_days   = tank_l / max(draw_daily, 1)
    reliability = max(0.0, (12 - deficit_months) / 12)     # months the tank meets the draw
    # Coverage is the ceiling — you can't be secure beyond what you actually supply.
    # Dry-season reliability scales how much of that ceiling holds year-round.
    score = min(100, round(coverage_pct * (0.70 + 0.30 * reliability)))

    # ── Cost ──
    tank_cost  = _tank_cost(tank_l)
    tank_units = max(1, math.ceil(tank_l / PRACTICAL_TANK_L))
    cost = (tank_cost + COST_COLLECTION
            + COST_FILTRATION + COST_PUMP + COST_GW[gw_system])

    monthly_balance = {m: monthly_coll[m] - monthly_rain_need[m] for m in range(1, 13)}
    deficit_list = [MONTHS[m-1] for m in range(1, 13) if monthly_balance[m] < 0]

    return {
        "people":          people,
        "per_capita":      per_capita,
        "roof_area":       roof_area,
        "runoff":          runoff,
        "garden_area":     garden_area,
        "gw_system":       gw_system,
        "score":           score,
        "coverage_pct":    coverage_pct,
        "rain_pct":        rain_pct,
        "grey_pct":        grey_pct,
        # potable vs non-potable
        "potable_pct":     potable_pct,
        "nonpot_pct":      nonpot_pct,
        "potable_daily":   round(potable_daily, 0),
        "nonpot_daily":    round(nonpot_daily, 0),
        # demand
        "indoor_daily":    round(indoor_daily, 0),
        "garden_daily":    round(garden_daily, 0),
        "total_daily":     round(total_daily, 0),
        "annual_demand":   round(annual_demand, 0),
        # rainwater
        "monthly_coll":    monthly_coll,
        "monthly_need":    monthly_rain_need,
        "monthly_balance": monthly_balance,
        "annual_coll":     round(annual_coll, 0),
        "rain_supplied":   round(rain_supplied, 0),
        "overflow":        round(overflow, 0),
        "deficit_months":  deficit_months,
        "deficit_list":    deficit_list,
        "supply_limited":  supply_limited,
        "tank_liters":     int(tank_l),
        "tank_days":       round(tank_days, 0),
        "tank_units":      tank_units,
        # greywater
        "grey_gen_daily":  round(grey_gen_daily, 0),
        "grey_usable":     round(grey_usable_daily, 0),
        "grey_eff":        gw_eff,
        # rain climate
        "annual_rain_mm":  climate["annual_rain"],
        "rain_source":     climate["source"],
        "rain_monthly":    rain_m,
        # cost
        "cost":            round(cost, 0),
        "tank_cost":       round(tank_cost, 0),
        "gw_cost":         COST_GW[gw_system],
    }


# ── AI roadmap ────────────────────────────────────────────────────────────────

def build_roadmap_prompt(r: dict, loc: dict) -> str:
    loc_str = loc["name"]
    if loc.get("admin1"):
        loc_str += f", {loc['admin1']}"
    if loc.get("country"):
        loc_str += f", {loc['country']}"

    return f"""You are a water-resilience engineer. Return ONLY valid JSON (no markdown fences, no commentary) matching the schema below.

LOCATION: {loc_str}
HOUSEHOLD: {r['people']} people · {r['per_capita']} L/person/day · {r['total_daily']:.0f} L/day total demand
RAINFALL: {r['annual_rain_mm']:.0f} mm/yr · roof {r['roof_area']:.0f} m² (runoff {r['runoff']}) · {r['annual_coll']:,.0f} L collectable/yr
GREYWATER: {r['gw_system']} · {r['grey_usable']:.0f} L/day reusable
RESULT: {r['coverage_pct']:.0f}% of demand covered ({r['rain_pct']:.0f}% rain + {r['grey_pct']:.0f}% greywater) · tank {r['tank_liters']:,} L · {r['deficit_months']} dry months
SECURITY SCORE: {r['score']}/100  |  SYSTEM COST: ${r['cost']:,.0f}

JSON schema (fill every field):
{{
  "one_liner": "<one bold sentence about this household's path to water security>",
  "phase1": {{
    "title": "Quick Wins",
    "timeframe": "0–3 months",
    "budget": <integer USD>,
    "highlight": "<one sentence: what this phase achieves>",
    "coverage_after": <integer 0-100, must be > {int(r['coverage_pct'])}>,
    "actions": [
      {{"icon": "<single emoji>", "title": "<short action>", "detail": "<specific spec or product>", "cost": <integer USD>}}
    ]
  }},
  "phase2": {{
    "title": "Core System",
    "timeframe": "3–12 months",
    "budget": <integer USD>,
    "highlight": "<one sentence>",
    "coverage_after": <integer 0-100, must be > phase1 coverage_after>,
    "actions": [...]
  }},
  "phase3": {{
    "title": "Full Water Security",
    "timeframe": "12–24 months",
    "budget": <integer USD>,
    "highlight": "<one sentence>",
    "coverage_after": <integer 0-100, must be > phase2 coverage_after>,
    "actions": [...]
  }},
  "tips": [
    {{"icon": "<emoji>", "tip": "<short conservation action>", "saving": "<estimated litres/day or % saved>"}}
  ],
  "products": [
    {{"category": "Collection|Storage|Filtration|Greywater", "icon": "<emoji>", "name": "<product name>", "why": "<1-sentence reason specific to {loc_str}>"}}
  ]
}}

Rules: max 4 actions per phase · exactly 3–4 conservation tips · exactly 4 products (one per category: Collection, Storage, Filtration, Greywater) · coverage must increase each phase · be specific to {loc_str} rainfall pattern. Return ONLY the JSON object."""


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
  background: #eef4fb !important;
  color: #1e293b !important;
  font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stApp"] { background: #eef4fb !important; }
[data-testid="stAppViewContainer"] { background: transparent !important; }
[data-testid="stMainBlockContainer"] { background: transparent !important; }
[data-testid="block-container"] { background: transparent !important; }
[data-testid="stVerticalBlock"] { background: transparent !important; }
[data-testid="stMarkdown"] { color: #1e293b; }
[data-testid="stMarkdown"] p, [data-testid="stMarkdown"] span,
[data-testid="stMarkdown"] li, [data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2, [data-testid="stMarkdown"] h3 { color: inherit !important; }
[data-testid="stAlert"] { border-radius: 12px !important; }
[data-testid="stAlert"] p { color: #1e293b !important; }
[data-testid="stSpinner"] p { color: #475569 !important; }
[data-testid="stStatusWidget"] { color: #475569 !important; }

/* ── Base & aqua background ── */
#MainMenu, header, footer { visibility: hidden; }
section.main > div:first-child { padding-top: 0 !important; }
[data-testid="stAppViewBlockContainer"] { max-width: 100% !important; padding: 0 !important; }
section.main {
  background:
    radial-gradient(ellipse at 12% 14%, rgba(56,189,248,.24) 0%, transparent 50%),
    radial-gradient(ellipse at 88% 16%, rgba(45,212,191,.22) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 88%, rgba(99,102,241,.20) 0%, transparent 52%),
    radial-gradient(ellipse at 16% 84%, rgba(125,211,252,.22) 0%, transparent 50%),
    linear-gradient(135deg, #eff6ff 0%, #ecfeff 100%);
  font-family: 'Space Grotesk', sans-serif;
  min-height: 100vh;
  color: #1e293b;
}

/* ── Two-column frame ── */
[data-testid="stHorizontalBlock"]:has(.ws-left) { gap: 0 !important; align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.42);
  backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px);
  border-right: 1px solid rgba(255,255,255,.6);
  min-height: 100vh; max-height: 100vh;
  overflow-y: auto; position: sticky; top: 0;
  scrollbar-width: thin; scrollbar-color: rgba(15,23,42,.14) transparent;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar-thumb { background: rgba(15,23,42,.16); border-radius: 2px; }
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:last-child {
  padding: 28px 32px !important; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: rgba(15,23,42,.14) transparent;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar-thumb { background: rgba(15,23,42,.16); border-radius: 2px; }

/* ── Left panel widget spacing ── */
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stNumberInput"],
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stSelectbox"],
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stSlider"] {
  padding: 4px 20px 15px !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] { padding: 0 20px 20px !important; }

/* ── Buttons ── */
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
  width: 100% !important; border-radius: 12px !important;
  font-size: .82rem !important; font-weight: 700 !important; letter-spacing: .02em !important;
  padding: 11px 16px !important; transition: all .2s ease !important;
  font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 50%, #0284c7 100%) !important;
  color: #ffffff !important; border: none !important;
  box-shadow: 0 4px 20px rgba(2,132,199,.42), inset 0 1px 0 rgba(255,255,255,.3) !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #7dd3fc 0%, #38bdf8 50%, #0ea5e9 100%) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 30px rgba(2,132,199,.52), inset 0 1px 0 rgba(255,255,255,.35) !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button:not([kind="primary"]) {
  background: rgba(255,255,255,.55) !important; color: #475569 !important;
  border: 1px solid rgba(15,23,42,.1) !important;
  box-shadow: 0 2px 8px rgba(31,41,55,.06) !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button:not([kind="primary"]):hover {
  background: rgba(255,255,255,.8) !important; color: #1e293b !important;
}

/* ── Inputs ── */
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child input {
  background: rgba(255,255,255,.6) !important;
  border: 1px solid rgba(15,23,42,.12) !important;
  color: #1e293b !important;
  border-radius: 10px !important; font-size: .83rem !important;
  font-family: 'Space Grotesk', sans-serif !important;
  padding: 10px 13px !important; line-height: 1.5 !important; min-height: 42px !important;
  transition: all .18s !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-baseweb="input"],
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-baseweb="base-input"] {
  background: transparent !important; border: none !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child input:focus {
  background: rgba(255,255,255,.9) !important;
  border-color: rgba(14,165,233,.6) !important;
  box-shadow: 0 0 0 3px rgba(14,165,233,.16), 0 0 16px rgba(14,165,233,.1) !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child input::placeholder { color: #94a3b8 !important; }

/* Selectbox */
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] > div:first-child {
  background: rgba(255,255,255,.6) !important;
  border: 1px solid rgba(15,23,42,.12) !important;
  border-radius: 10px !important; color: #1e293b !important;
  min-height: 42px !important; padding: 3px 6px !important;
}
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] div[value],
[data-testid="stHorizontalBlock"]:has(.ws-left) > [data-testid="stColumn"]:first-child [data-baseweb="select"] span {
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
.ws-left { display: none; }
.lp-pad  { padding: 22px 20px 14px; }
.lp-logo { font-size: 2.2rem; line-height: 1; margin-bottom: 10px; filter: drop-shadow(0 0 14px rgba(14,165,233,.55)); }
.lp-title { font-size: .95rem; font-weight: 800; color: #0f172a; margin-bottom: 6px; letter-spacing: -.1px; line-height: 1.3; }
.lp-desc  { font-size: .72rem; color: #64748b; line-height: 1.65; }
.ca-sep   { border: none; border-top: 1px solid rgba(15,23,42,.08); margin: 0; }
.lp-lbl   { font-size: .6rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase;
  color: #94a3b8; display: block; padding: 15px 20px 8px; line-height: 1.5; }

/* Location data box */
.lp-box {
  background: linear-gradient(135deg, rgba(56,189,248,.22) 0%, rgba(56,189,248,.08) 100%);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 14px; padding: 15px 16px; margin: 6px 20px 18px;
  border: 1px solid rgba(14,165,233,.32);
  box-shadow: 0 4px 20px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.lp-box-label { font-size: .58rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: #0369a1; margin-bottom: 8px; }
.lp-box-loc   { font-size: .86rem; font-weight: 800; color: #0f172a; margin-bottom: 11px; line-height: 1.3; }
.lp-box-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.lp-stat      { background: rgba(255,255,255,.6); border: 1px solid rgba(255,255,255,.7); border-radius: 10px; padding: 9px 11px; }
.lp-stat-icon { font-size: .88rem; margin-bottom: 4px; }
.lp-stat-val  { font-size: .93rem; font-weight: 900; color: #0f172a; line-height: 1.1; }
.lp-stat-lbl  { font-size: .57rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-top: 2px; }

/* ── Result header ── */
.result-header {
  background: linear-gradient(135deg, rgba(56,189,248,.2) 0%, rgba(56,189,248,.07) 100%);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(14,165,233,.3);
  border-radius: 18px; padding: 15px 24px; margin-bottom: 22px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  box-shadow: 0 4px 24px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.rh-loc { font-size: .83rem; font-weight: 700; color: #334155; }
.rh-badge { font-size: .71rem; font-weight: 800; padding: 7px 16px; border-radius: 20px; white-space: nowrap; letter-spacing: .03em; backdrop-filter: blur(10px); }

/* ── Score section ── */
.score-micro-lbl { font-size: .6rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.score-headline { font-size: 4rem; font-weight: 900; color: #0f172a; line-height: 1.08; margin-bottom: 14px; text-shadow: 0 4px 24px rgba(14,165,233,.18); }
.score-sub { font-size: .74rem; color: #64748b; line-height: 1.65; max-width: 320px; margin-bottom: 2px; }
.score-label-chip { display: inline-block; margin-top: 12px; padding: 6px 16px; border-radius: 20px; font-size: .72rem; font-weight: 700; backdrop-filter: blur(10px); }

/* ── Potable / non-potable tier split ── */
.tier-split { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 4px 0 20px; }
.tier-row {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,.7); border-radius: 16px; padding: 15px 18px;
  box-shadow: 0 4px 16px rgba(31,41,55,.07);
}
.tier-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px; }
.tier-name { font-size: .74rem; font-weight: 700; color: #334155; display: flex; align-items: center; gap: 7px; }
.tier-pct  { font-size: 1.5rem; font-weight: 900; line-height: 1; }
.tier-bar  { height: 7px; background: rgba(15,23,42,.07); border-radius: 5px; overflow: hidden; margin-bottom: 9px; }
.tier-fill { height: 100%; border-radius: 5px; transition: width .4s ease; }
.tier-note { font-size: .64rem; color: #64748b; line-height: 1.5; }

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
.sys-pct  { font-size: 2.2rem; font-weight: 900; line-height: 1.1; margin-bottom: 5px; }
.sys-pct-unit { font-size: .62rem; font-weight: 600; color: #64748b; margin-bottom: 10px; }
.sys-metric { font-size: .69rem; color: #475569; margin-bottom: 3px; display: flex; align-items: flex-start; gap: 6px; }
.sys-metric-dot { width: 4px; height: 4px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; opacity: .7; }
.sys-cost { display: inline-flex; align-items: center; gap: 4px; margin-top: 11px; padding: 4px 10px; border-radius: 8px; font-size: .69rem; font-weight: 700; }

/* ── Cost strip ── */
.cost-wrap {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 18px; border: 1px solid rgba(255,255,255,.7);
  padding: 16px 22px; margin-bottom: 22px;
  display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap;
  box-shadow: 0 4px 20px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.6);
}
.cost-item   { display: flex; flex-direction: column; gap: 2px; }
.cost-item-v { font-size: 1.35rem; font-weight: 900; color: #0f172a; line-height: 1.1; }
.cost-item-l { font-size: .6rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #64748b; }
.cost-div    { width: 1px; align-self: stretch; background: rgba(15,23,42,.08); }

/* ── Chart card ── */
.chart-card {
  background: rgba(255,255,255,.5);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: 20px; border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,41,55,.09), inset 0 1px 0 rgba(255,255,255,.6);
  margin-bottom: 22px; overflow: hidden;
}
.chart-head  { padding: 20px 24px 12px; }
.chart-title { font-size: .96rem; font-weight: 800; color: #0f172a; margin-bottom: 6px; line-height: 1.3; }
.chart-sub   { font-size: .72rem; color: #64748b; line-height: 1.5; margin-bottom: 0; }

/* ── Spec tiles ── */
.spec-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.spec-tile  {
  background: rgba(255,255,255,.5);
  border-radius: 14px; padding: 16px; border: 1px solid rgba(255,255,255,.7);
  backdrop-filter: blur(12px); box-shadow: 0 4px 16px rgba(31,41,55,.06);
}
.spec-icon  { font-size: 1.3rem; margin-bottom: 8px; }
.spec-val   { font-size: 1.4rem; font-weight: 900; color: #0f172a; line-height: 1.1; margin-bottom: 5px; }
.spec-unit  { font-size: .59rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; color: #64748b; margin-bottom: 5px; }
.spec-label { font-size: .69rem; color: #475569; line-height: 1.45; }

/* ── Warning pill ── */
.warn-pill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border-radius: 10px; font-size: .74rem; font-weight: 600; margin-bottom: 16px; backdrop-filter: blur(10px); }

/* ── Monthly table ── */
.mtbl { width: 100%; border-collapse: collapse; font-size: .72rem; }
.mtbl th { text-align: right; padding: 8px 12px; font-size: .58rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #64748b; border-bottom: 1px solid rgba(15,23,42,.1); }
.mtbl th:first-child { text-align: left; }
.mtbl td { text-align: right; padding: 7px 12px; color: #334155; border-bottom: 1px solid rgba(15,23,42,.05); }
.mtbl td:first-child { text-align: left; font-weight: 700; color: #0f172a; }
.mtbl tr:hover td { background: rgba(14,165,233,.05); }

/* ── Greywater flow ── */
.gw-flow { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; align-items: center; gap: 8px; margin: 4px 0 20px; }
.gw-node { background: rgba(255,255,255,.55); border: 1px solid rgba(255,255,255,.7); border-radius: 16px; padding: 16px 14px; text-align: center; backdrop-filter: blur(16px); box-shadow: 0 4px 16px rgba(31,41,55,.07); }
.gw-node-ic  { font-size: 1.5rem; margin-bottom: 6px; }
.gw-node-v   { font-size: 1.3rem; font-weight: 900; color: #0f172a; line-height: 1.1; }
.gw-node-u   { font-size: .56rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: #64748b; margin-top: 2px; }
.gw-node-l   { font-size: .64rem; color: #475569; margin-top: 6px; line-height: 1.35; }
.gw-arrow    { font-size: 1.3rem; color: #0d9488; }

/* ── AI prompt card ── */
.ai-intro {
  background: linear-gradient(135deg, rgba(56,189,248,.18), rgba(56,189,248,.06));
  backdrop-filter: blur(20px); border: 1px solid rgba(14,165,233,.3);
  border-radius: 18px; padding: 20px 24px; margin-bottom: 22px;
  box-shadow: 0 4px 20px rgba(31,41,55,.08);
}
.ai-intro-title { font-size: 1.0rem; font-weight: 800; color: #0f172a; margin-bottom: 8px; line-height: 1.3; }
.ai-intro-desc  { font-size: .77rem; color: #475569; line-height: 1.65; }

/* ── AI Roadmap visual ── */
.ra-hero {
  background: linear-gradient(135deg, rgba(56,189,248,.2) 0%, rgba(56,189,248,.06) 100%);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(14,165,233,.3); border-radius: 18px;
  padding: 20px 24px; margin-bottom: 22px;
  display: flex; align-items: flex-start; gap: 16px;
  box-shadow: 0 4px 24px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.5);
}
.ra-hero-icon { font-size: 1.7rem; flex-shrink: 0; filter: drop-shadow(0 2px 6px rgba(14,165,233,.45)); }
.ra-hero-text { font-size: .88rem; font-weight: 600; color: #334155; line-height: 1.7; }
.ra-section-lbl { font-size: .59rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: #64748b; margin-bottom: 12px; margin-top: 8px; }

/* Phase cards */
.ra-phases { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 24px; }
.ra-phase-card {
  background: rgba(255,255,255,.55);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 18px; border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,41,55,.1), inset 0 1px 0 rgba(255,255,255,.6);
  padding: 18px; display: flex; flex-direction: column; gap: 10px; transition: all .22s ease;
}
.ra-phase-card:hover {
  background: rgba(255,255,255,.75); border-color: rgba(255,255,255,.9);
  box-shadow: 0 14px 44px rgba(31,41,55,.16), inset 0 1px 0 rgba(255,255,255,.7);
  transform: translateY(-3px);
}
.ra-phase-top  { display: flex; align-items: center; justify-content: space-between; }
.ra-phase-num  { font-size: .58rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; padding: 3px 10px; border-radius: 20px; }
.ra-phase-time { font-size: .63rem; font-weight: 600; color: #64748b; }
.ra-phase-title  { font-size: .9rem; font-weight: 800; color: #0f172a; }
.ra-phase-budget { font-size: 1.55rem; font-weight: 900; color: #0f172a; line-height: 1.1; }
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

/* Tip + product cards */
.ra-risks, .ra-products { display: flex; flex-direction: column; gap: 10px; }
.ra-risk-card, .ra-product-card {
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
.ra-product-top  { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.ra-product-ic   { font-size: 1.2rem; flex-shrink: 0; }
.ra-product-cat  { font-size: .58rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 2px; }
.ra-product-name { font-size: .76rem; font-weight: 700; color: #1e293b; }
.ra-product-why  { font-size: .68rem; color: #475569; line-height: 1.55; }

/* ── Placeholder / empty state ── */
.ph-wrap  { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 72vh; gap: 22px; padding: 36px 24px; text-align: center; }
.ph-big   { font-size: 4.5rem; line-height: 1; filter: drop-shadow(0 6px 16px rgba(14,165,233,.35)); }
.ph-title { font-size: 1.2rem; font-weight: 800; color: #0f172a; letter-spacing: -.2px; }
.ph-desc  { font-size: .8rem; color: #64748b; max-width: 380px; line-height: 1.75; }
.ph-chips { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; max-width: 500px; }
.ph-chip  {
  display: flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 20px;
  background: rgba(255,255,255,.55);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 2px 10px rgba(31,41,55,.06); transition: all .2s ease;
}
.ph-chip:hover { background: rgba(255,255,255,.8); transform: translateY(-2px); box-shadow: 0 6px 18px rgba(31,41,55,.12); }
.ph-chip-icon { font-size: 1.0rem; }
.ph-chip-text { font-size: .72rem; font-weight: 600; color: #475569; }

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
  padding: 8px 14px !important; border-radius: 9px !important; color: #64748b !important;
  font-family: 'Space Grotesk', sans-serif !important; transition: all .18s !important; background: transparent !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover { color: #1e293b !important; background: rgba(255,255,255,.55) !important; }
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
  background: rgba(255,255,255,.85) !important; color: #0f172a !important; font-weight: 700 !important;
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


def _left_box_html(loc: dict, annual_rain: float, roof_area: float) -> str:
    return (
        f'<div class="lp-box">'
        f'<div class="lp-box-label">Location data loaded</div>'
        f'<div class="lp-box-loc">📍 {_loc_label(loc)}</div>'
        f'<div class="lp-box-grid">'
        f'<div class="lp-stat"><div class="lp-stat-icon">🌧️</div>'
        f'<div class="lp-stat-val">{annual_rain:.0f}mm</div>'
        f'<div class="lp-stat-lbl">Annual rainfall</div></div>'
        f'<div class="lp-stat"><div class="lp-stat-icon">🏠</div>'
        f'<div class="lp-stat-val">{roof_area:.0f}m²</div>'
        f'<div class="lp-stat-lbl">Roof catchment</div></div>'
        f'</div></div>'
    )


def _empty_state_html() -> str:
    chips = [
        ("🌧️", "Rainwater harvesting"),
        ("♻️", "Greywater recycling"),
        ("🛢️", "Tank sizing"),
        ("📅", "Dry-season balance"),
        ("🤖", "AI water plan"),
    ]
    chips_html = "".join(
        f'<div class="ph-chip"><span class="ph-chip-icon">{ic}</span>'
        f'<span class="ph-chip-text">{tx}</span></div>'
        for ic, tx in chips
    )
    return (
        f'<div class="ph-wrap">'
        f'<div class="ph-big">💧</div>'
        f'<div class="ph-title">Plan Your Water Security</div>'
        f'<div class="ph-desc">Enter your location, roof size and household, then hit Calculate to see how much of '
        f'your water needs you can cover with rainwater harvesting and greywater recycling — plus your Water Security Score.</div>'
        f'<div class="ph-chips">{chips_html}</div>'
        f'</div>'
    )


def _score_label(score: int) -> tuple[str, str, str]:
    if score >= 75:
        return "Water Secure", "#0369a1", "rgba(14,165,233,.18)"
    if score >= 50:
        return "On Track", "#0d9488", "rgba(13,148,136,.18)"
    if score >= 25:
        return "Vulnerable", "#b45309", "rgba(245,158,11,.2)"
    return "At Risk", "#dc2626", "rgba(239,68,68,.16)"


def _score_gauge(score: int) -> go.Figure:
    _, color, _ = _score_label(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        number={"font": {"size": 36, "family": "Space Grotesk", "color": "#0f172a"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "rgba(0,0,0,0)", "showticklabels": False},
            "bar":  {"color": color, "thickness": 0.28},
            "bgcolor": "rgba(15,23,42,.05)",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  25], "color": "rgba(239,68,68,.14)"},
                {"range": [25, 50], "color": "rgba(245,158,11,.14)"},
                {"range": [50, 75], "color": "rgba(13,148,136,.14)"},
                {"range": [75,100], "color": "rgba(14,165,233,.16)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(height=210, margin=dict(l=8, r=8, t=22, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", font={"family": "Space Grotesk"})
    return fig


def _sys_card_html(icon: str, name: str, pct_text: str, pct_unit: str,
                   metrics: list[str], cost: str, color: str) -> str:
    dots = "".join(
        f'<div class="sys-metric"><span class="sys-metric-dot" style="background:{color}"></span>{m}</div>'
        for m in metrics
    )
    cost_html = (f'<div class="sys-cost" style="background:{color}12;color:{color}">{cost}</div>'
                 if cost else "")
    return (
        f'<div class="sys-card">'
        f'<div class="sys-bar" style="background:{color}"></div>'
        f'<div class="sys-body">'
        f'<div class="sys-icon-row">'
        f'<div class="sys-icon-box" style="background:{color}18">{icon}</div>'
        f'<div class="sys-name" style="color:{color}">{name}</div></div>'
        f'<div class="sys-pct" style="color:{color}">{pct_text}</div>'
        f'<div class="sys-pct-unit">{pct_unit}</div>'
        f'{dots}{cost_html}'
        f'</div></div>'
    )


def _spec_tile_html(icon: str, val: str, unit: str, label: str) -> str:
    return (
        f'<div class="spec-tile">'
        f'<div class="spec-icon">{icon}</div>'
        f'<div class="spec-val">{val}</div>'
        f'<div class="spec-unit">{unit}</div>'
        f'<div class="spec-label">{label}</div></div>'
    )


def _coll_chart(coll: list, need: float) -> go.Figure:
    bar_colors = ["#0284c7" if c >= need else "#f59e0b" for c in coll]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=MONTHS, y=coll, name="Collected (L)",
                         marker_color=bar_colors, marker_line_width=0))
    fig.add_trace(go.Scatter(x=MONTHS, y=[need] * 12, name="Monthly need",
                             line=dict(color="#ef4444", width=2, dash="dash"), mode="lines"))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=240,
        margin=dict(l=0, r=0, t=8, b=0),
        legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11, color="#475569")),
        yaxis=dict(gridcolor="rgba(15,23,42,.08)", zeroline=False, tickfont=dict(size=11, color="#64748b")),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11, color="#64748b")),
        font=dict(family="Space Grotesk"), bargap=0.32,
    )
    return fig


def _journey_chart(start: int, data: dict) -> go.Figure:
    labels = ["Now", "Phase 1", "Phase 2", "Phase 3"]
    values = [start, data["phase1"]["coverage_after"],
              data["phase2"]["coverage_after"], data["phase3"]["coverage_after"]]
    dot_colors = ["#94a3b8", "#0ea5e9", "#0d9488", "#0369a1"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=values, fill="tozeroy",
                             fillcolor="rgba(14,165,233,.12)", line=dict(color="rgba(0,0,0,0)"),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=labels, y=values, mode="lines+markers+text",
        line=dict(color="#0ea5e9", width=2.5, shape="spline"),
        marker=dict(size=14, color=dot_colors, line=dict(color="#ffffff", width=2.5)),
        text=[f"{v}%" for v in values], textposition="top center",
        textfont=dict(size=13, family="Space Grotesk", color="#0f172a"),
        showlegend=False, hovertemplate="%{x}: %{y}% covered<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=170,
        margin=dict(l=10, r=10, t=32, b=10),
        yaxis=dict(range=[0, min(118, max(values) + 16)], showgrid=False, showticklabels=False, zeroline=False),
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
        f'<div class="ra-action-detail">{a["detail"]}</div></div>'
        f'<div class="ra-action-cost" style="color:{color}">${a["cost"]:,}</div>'
        f'</div>'
        for a in p.get("actions", [])
    )
    return (
        f'<div class="ra-phase-card" style="border-top:3px solid {color}">'
        f'<div class="ra-phase-top">'
        f'<div class="ra-phase-num" style="background:{color}1a;color:{color}">Phase {num}</div>'
        f'<div class="ra-phase-time">{p["timeframe"]}</div></div>'
        f'<div class="ra-phase-title" style="color:{color}">{p["title"]}</div>'
        f'<div class="ra-phase-budget">${p["budget"]:,}</div>'
        f'<div class="ra-phase-hl">{p["highlight"]}</div>'
        f'<div class="ra-actions">{actions}</div>'
        f'<div class="ra-score-bar"><div class="ra-score-bar-fill" style="width:{p["coverage_after"]}%;background:{color}"></div></div>'
        f'<div class="ra-score-after" style="color:{color}">Coverage → {p["coverage_after"]}%</div>'
        f'</div>'
    )


# ── Tab renderers ─────────────────────────────────────────────────────────────

C_RAIN  = "#0284c7"
C_GREY  = "#0d9488"
C_STORE = "#6366f1"
C_DEMAND = "#f43f5e"


def _render_overview(r: dict) -> None:
    score = r["score"]
    label, color, bg = _score_label(score)

    col_g, col_info = st.columns([1, 2.4])
    with col_g:
        st.plotly_chart(_score_gauge(score), use_container_width=True, config={"displayModeBar": False})
    with col_info:
        st.markdown(
            f'<div style="padding-top:14px">'
            f'<div class="score-micro-lbl">Water Security Score</div>'
            f'<div class="score-headline">{score}<span style="font-size:1.4rem;color:#94a3b8;font-weight:500">/100</span></div>'
            f'<div class="score-sub">You can cover <strong style="color:{C_RAIN}">{r["coverage_pct"]:.0f}%</strong> of your '
            f'{r["total_daily"]:,.0f} L/day demand from rain &amp; greywater. '
            f'Coverage sets the ceiling; dry-season reliability scales how much of it holds year-round.</div>'
            f'<span class="score-label-chip" style="background:{bg};color:{color};border:1px solid {color}28">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="tier-split">'
        f'<div class="tier-row">'
        f'<div class="tier-head"><span class="tier-name">🚰 Potable water</span>'
        f'<span class="tier-pct" style="color:{C_RAIN}">{r["potable_pct"]:.0f}%</span></div>'
        f'<div class="tier-bar"><div class="tier-fill" style="width:{r["potable_pct"]}%;background:{C_RAIN}"></div></div>'
        f'<div class="tier-note">Drinking · cooking · bathing — {r["potable_daily"]:,.0f} L/day. '
        f'Met by filtered rainwater only; the ${COST_FILTRATION} filtration is what makes this safe to drink.</div></div>'
        f'<div class="tier-row">'
        f'<div class="tier-head"><span class="tier-name">🚽 Non-potable water</span>'
        f'<span class="tier-pct" style="color:{C_GREY}">{r["nonpot_pct"]:.0f}%</span></div>'
        f'<div class="tier-bar"><div class="tier-fill" style="width:{r["nonpot_pct"]}%;background:{C_GREY}"></div></div>'
        f'<div class="tier-note">Toilet · laundry · garden — {r["nonpot_daily"]:,.0f} L/day. '
        f'Met by greywater first, then any surplus rainwater.</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sys-grid">'
        + _sys_card_html("🌧️", "Rainwater", f"{r['rain_pct']:.0f}", "% of demand",
                         [f"{r['annual_coll']:,.0f} L collectable/yr",
                          f"{r['rain_supplied']:,.0f} L usable/yr",
                          f"{r['annual_rain_mm']:.0f}mm/yr rainfall"], "", C_RAIN)
        + _sys_card_html("♻️", "Greywater", f"{r['grey_pct']:.0f}", "% of demand",
                         [f"{r['grey_gen_daily']:,.0f} L/day produced",
                          f"{r['grey_usable']:,.0f} L/day reused",
                          (r['gw_system'] if r['gw_system'] != "None" else "No system yet")], "", C_GREY)
        + _sys_card_html("🛢️", "Storage", f"{r['tank_liters']:,}", "L tank",
                         [f"{r['tank_days']:.0f} days of buffer",
                          f"{r['deficit_months']} dry months/yr",
                          f"{r['overflow']:,.0f} L overflow/yr"], "", C_STORE)
        + _sys_card_html("🚿", "Demand", f"{r['total_daily']:,.0f}", "L/day",
                         [f"{r['indoor_daily']:,.0f} L indoor",
                          f"{r['garden_daily']:,.0f} L garden",
                          f"{r['per_capita']} L/person/day"], "", C_DEMAND)
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="cost-wrap">'
        f'<div class="cost-item"><div class="cost-item-v">${r["cost"]:,.0f}</div><div class="cost-item-l">System cost</div></div>'
        f'<div class="cost-div"></div>'
        f'<div class="cost-item"><div class="cost-item-v">{r["coverage_pct"]:.0f}%</div><div class="cost-item-l">Demand covered</div></div>'
        f'<div class="cost-div"></div>'
        f'<div class="cost-item"><div class="cost-item-v">{r["tank_liters"]:,} L</div><div class="cost-item-l">Tank size</div></div>'
        f'<div class="cost-div"></div>'
        f'<div class="cost-item"><div class="cost-item-v">{(r["rain_supplied"]+r["grey_usable"]*365)/1000:,.0f} m³</div><div class="cost-item-l">Water saved/yr</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_rain_tab(r: dict) -> None:
    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">🌧️ Rainwater Harvesting</div>'
        f'<div class="chart-sub">{r["annual_rain_mm"]:.0f}mm/yr · roof {r["roof_area"]:.0f}m² @ {r["runoff"]} runoff · '
        f'90% first-flush efficiency · source: {r["rain_source"]}</div></div>',
        unsafe_allow_html=True,
    )
    tank_label = f"{r['tank_days']:.0f} days of buffer"
    if r["tank_units"] > 1:
        tank_label += f" · ≈{r['tank_units']} tanks"
    specs = [
        _spec_tile_html("🌧️", f"{r['annual_coll']:,.0f}", "L/yr", "Collectable from your roof"),
        _spec_tile_html("✅", f"{r['rain_supplied']:,.0f}", "L/yr", f"Actually usable ({r['rain_pct']:.0f}% of demand)"),
        _spec_tile_html("🛢️", f"{r['tank_liters']:,}", "L tank", tank_label),
    ]
    st.markdown('<div style="padding:18px 22px 0"><div class="spec-grid">' + "".join(specs) + "</div></div>",
                unsafe_allow_html=True)

    coll_vals = [r["monthly_coll"][m] for m in range(1, 13)]
    st.plotly_chart(_coll_chart(coll_vals, r["monthly_need"][1]),
                    use_container_width=True, config={"displayModeBar": False})

    if r["supply_limited"]:
        st.markdown(
            f'<div style="padding:0 22px"><div class="warn-pill" style="background:rgba(245,158,11,.16);color:#b45309;border:1px solid rgba(245,158,11,.3)">'
            f'⚠️ Supply-limited: your roof collects {r["annual_coll"]:,.0f}L/yr against {r["total_daily"]*365/1000:,.0f}m³ demand — '
            f'rainwater covers {r["rain_pct"]:.0f}%. A larger catchment or lower use raises this; a bigger tank alone won\'t.'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    elif r["deficit_list"]:
        st.markdown(
            f'<div style="padding:0 22px"><div class="warn-pill" style="background:rgba(14,165,233,.14);color:#0369a1;border:1px solid rgba(14,165,233,.3)">'
            f'💧 Collection dips below demand in {", ".join(r["deficit_list"])} — your {r["tank_liters"]:,}L tank stores wet-season surplus to bridge them.'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # Monthly table (tertiary)
    rows = ""
    for m in range(1, 13):
        bal = r["monthly_balance"][m]
        bal_color = "#0369a1" if bal >= 0 else "#dc2626"
        bal_txt = f"+{bal:,.0f}" if bal >= 0 else f"{bal:,.0f}"
        rows += (
            f'<tr><td>{MONTHS[m-1]}</td>'
            f'<td>{r["rain_monthly"][m]:.0f}</td>'
            f'<td>{r["monthly_coll"][m]:,.0f}</td>'
            f'<td>{r["monthly_need"][m]:,.0f}</td>'
            f'<td style="color:{bal_color};font-weight:700">{bal_txt}</td></tr>'
        )
    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">📅 Monthly Water Balance</div>'
        '<div class="chart-sub">Litres collected each month vs. the steady draw your roof + tank can sustain</div></div>'
        '<div style="padding:4px 22px 18px"><table class="mtbl">'
        '<tr><th>Month</th><th>Rain (mm)</th><th>Collected (L)</th><th>Need (L)</th><th>Balance</th></tr>'
        + rows + '</table></div></div>',
        unsafe_allow_html=True,
    )


def _render_grey_tab(r: dict) -> None:
    st.markdown(
        '<div class="chart-card"><div class="chart-head">'
        '<div class="chart-title">♻️ Greywater Recycling</div>'
        f'<div class="chart-sub">System: {r["gw_system"]} · recovers shower, laundry &amp; basin water for non-potable reuse</div></div>',
        unsafe_allow_html=True,
    )

    if r["gw_system"] == "None":
        st.markdown(
            '<div style="padding:6px 22px 22px"><div class="warn-pill" style="background:rgba(13,148,136,.14);color:#0d9488;border:1px solid rgba(13,148,136,.3)">'
            f'💡 No greywater system selected. Your household produces ~{r["grey_gen_daily"]:,.0f} L/day of reusable greywater — '
            'a simple diversion could offset garden and toilet demand. Pick a system on the left to model it.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    eff_pct = int(r["grey_eff"] * 100)
    st.markdown(
        '<div style="padding:8px 22px 0"><div class="gw-flow">'
        f'<div class="gw-node"><div class="gw-node-ic">🚿</div>'
        f'<div class="gw-node-v">{r["grey_gen_daily"]:,.0f}</div><div class="gw-node-u">L/day produced</div>'
        f'<div class="gw-node-l">Shower · laundry · basin</div></div>'
        f'<div class="gw-arrow">→</div>'
        f'<div class="gw-node"><div class="gw-node-ic">⚙️</div>'
        f'<div class="gw-node-v">{eff_pct}%</div><div class="gw-node-u">recovery</div>'
        f'<div class="gw-node-l">After treatment losses</div></div>'
        f'<div class="gw-arrow">→</div>'
        f'<div class="gw-node" style="border-color:rgba(13,148,136,.45)"><div class="gw-node-ic">🌱</div>'
        f'<div class="gw-node-v" style="color:{C_GREY}">{r["grey_usable"]:,.0f}</div><div class="gw-node-u">L/day reused</div>'
        f'<div class="gw-node-l">{"Toilet + garden" if "Treated" in r["gw_system"] else "Garden irrigation"}</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    specs = [
        _spec_tile_html("♻️", f"{r['grey_usable']:,.0f}", "L/day", f"Reused — {r['grey_pct']:.0f}% of total demand"),
        _spec_tile_html("📉", f"{r['grey_usable']*365/1000:,.1f}", "m³/yr", "Mains water displaced"),
        _spec_tile_html("💰", f"${r['gw_cost']:,.0f}", "USD", "Greywater system cost"),
    ]
    st.markdown('<div style="padding:8px 22px 22px"><div class="spec-grid">' + "".join(specs) + "</div></div>",
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_ai_tab(r: dict, loc: dict) -> None:
    start = int(r["coverage_pct"])
    if st.session_state.get("ws_ai_data"):
        data = st.session_state["ws_ai_data"]
        if "_error" in data:
            st.error(f"AI generation failed — {data['_error']}")
        else:
            one_liner = data.get("one_liner", "")
            if one_liner:
                st.markdown(
                    f'<div class="ra-hero"><div class="ra-hero-icon">🤖</div>'
                    f'<div class="ra-hero-text">{one_liner}</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div class="ra-section-lbl">Coverage Journey</div>', unsafe_allow_html=True)
            st.plotly_chart(_journey_chart(start, data), use_container_width=True, config={"displayModeBar": False})

            st.markdown('<div class="ra-section-lbl">Implementation Roadmap</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="ra-phases">'
                + _phase_card_html(data["phase1"], 1, "#0ea5e9")
                + _phase_card_html(data["phase2"], 2, "#0d9488")
                + _phase_card_html(data["phase3"], 3, "#0369a1")
                + '</div>',
                unsafe_allow_html=True,
            )

            col_t, col_p = st.columns([1, 1])
            with col_t:
                st.markdown('<div class="ra-section-lbl">Conservation Tips</div>', unsafe_allow_html=True)
                tips_html = '<div class="ra-risks">'
                for tip in data.get("tips", []):
                    tips_html += (
                        f'<div class="ra-risk-card">'
                        f'<div class="ra-risk-top">'
                        f'<span class="ra-risk-ic">{tip.get("icon","💧")}</span>'
                        f'<div class="ra-risk-title">{tip["tip"]}</div>'
                        f'<span class="ra-risk-sev" style="background:rgba(13,148,136,.14);color:#0d9488">{tip.get("saving","")}</span>'
                        f'</div></div>'
                    )
                tips_html += '</div>'
                st.markdown(tips_html, unsafe_allow_html=True)
            with col_p:
                st.markdown('<div class="ra-section-lbl">Top Product Picks</div>', unsafe_allow_html=True)
                cat_clr = {"Collection": "#0284c7", "Storage": "#6366f1", "Filtration": "#0d9488", "Greywater": "#14b8a6"}
                prods_html = '<div class="ra-products">'
                for prod in data.get("products", []):
                    pc = cat_clr.get(prod.get("category", ""), "#64748b")
                    prods_html += (
                        f'<div class="ra-product-card" style="border-left:3px solid {pc}">'
                        f'<div class="ra-product-top">'
                        f'<span class="ra-product-ic">{prod.get("icon","🔧")}</span>'
                        f'<div><div class="ra-product-cat" style="color:{pc}">{prod.get("category","")}</div>'
                        f'<div class="ra-product-name">{prod["name"]}</div></div></div>'
                        f'<div class="ra-product-why">{prod["why"]}</div></div>'
                    )
                prods_html += '</div>'
                st.markdown(prods_html, unsafe_allow_html=True)

        if st.button("Regenerate Plan", key="ws_ai_regen"):
            st.session_state.pop("ws_ai_data", None)
            st.rerun()
    else:
        if not OPENROUTER_KEY:
            st.warning("Set OPENROUTER_API_KEY to enable AI roadmap generation.")
            return
        st.markdown(
            f'<div class="ai-intro">'
            f'<div class="ai-intro-title">🤖 AI Water Security Roadmap</div>'
            f'<div class="ai-intro-desc">'
            f'Coverage now: {start}% · Claude will generate a phased plan specific to {loc["name"]}\'s rainfall — '
            f'with coverage projections, conservation tips, and product picks.</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Generate My Roadmap", type="primary", key="ws_ai_gen"):
            with st.spinner("Claude is designing your water plan…"):
                data = fetch_ai_plan(build_roadmap_prompt(r, loc))
            st.session_state["ws_ai_data"] = data
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    left, right = st.columns([1, 2.5], gap="medium")

    with left:
        st.markdown('<div class="ws-left"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="lp-pad">'
            '<div class="lp-logo">💧</div>'
            '<div class="lp-title">Water Security Planner</div>'
            '<div class="lp-desc">Size your rainwater harvesting &amp; greywater recycling — see what share of your '
            'household water you can self-supply, plus an AI roadmap.</div>'
            '</div><hr class="ca-sep"/>',
            unsafe_allow_html=True,
        )

        st.markdown('<span class="lp-lbl">Location</span>', unsafe_allow_html=True)
        loc_input = st.text_input("Location", placeholder="e.g. Chennai, India",
                                  label_visibility="collapsed", key="ws_loc_input")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Household</span>', unsafe_allow_html=True)
        people  = st.number_input("Number of people", 1, 20, 4, key="ws_people")
        profile = st.selectbox("Water usage profile", list(PROFILES.keys()), index=1, key="ws_profile")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Roof Catchment</span>', unsafe_allow_html=True)
        roof_area = st.number_input("Roof catchment area (m²)", 5, 2000, 90, step=5, key="ws_roof")
        roof_type = st.selectbox("Roof surface", list(ROOF_RUNOFF.keys()), key="ws_roof_type")

        st.markdown('<hr class="ca-sep"/><span class="lp-lbl">Garden &amp; Greywater</span>', unsafe_allow_html=True)
        garden_area = st.number_input("Garden / irrigation area (m²)", 0, 20000, 30, step=5, key="ws_garden")
        gw_system   = st.selectbox("Greywater system", list(GW_SYSTEMS.keys()), index=1, key="ws_gw")

        st.markdown('<hr class="ca-sep"/>', unsafe_allow_html=True)
        calc_btn = st.button("Calculate My Plan", type="primary", key="ws_calc")

        if "ws_result" in st.session_state:
            res = st.session_state["ws_result"]
            st.markdown(
                _left_box_html(res["loc"], res["plan"]["annual_rain_mm"], res["plan"]["roof_area"]),
                unsafe_allow_html=True,
            )

    with right:
        if "ws_result" not in st.session_state:
            st.markdown(_empty_state_html(), unsafe_allow_html=True)
        else:
            res = st.session_state["ws_result"]
            r = res["plan"]
            _sl, _sc, _sbg = _score_label(r["score"])
            st.markdown(
                f'<div class="result-header">'
                f'<div class="rh-loc">📍 <strong>{_loc_label(res["loc"])}</strong></div>'
                f'<div class="rh-badge" style="background:{_sbg};color:{_sc};border:1px solid {_sc}38">'
                f'{r["score"]}/100 &nbsp;·&nbsp; {_sl}</div></div>',
                unsafe_allow_html=True,
            )
            if r["rain_source"] == "estimate":
                st.markdown(
                    '<div class="warn-pill" style="background:rgba(245,158,11,.16);color:#b45309;'
                    'border:1px solid rgba(245,158,11,.3);margin-bottom:18px">'
                    '⚠️ Live rainfall data was unavailable for this location, so this plan falls back on a '
                    'generic ~480&nbsp;mm/yr estimate. Treat every number here as a rough guide, not a final design — '
                    'recheck with local rainfall records before you buy a tank.</div>',
                    unsafe_allow_html=True,
                )
            t1, t2, t3, t4 = st.tabs(["Overview", "🌧️ Rainwater", "♻️ Greywater", "🤖 AI Plan"])
            with t1:
                _render_overview(r)
            with t2:
                _render_rain_tab(r)
            with t3:
                _render_grey_tab(r)
            with t4:
                _render_ai_tab(r, res["loc"])

    if calc_btn:
        if not loc_input.strip():
            st.warning("Please enter a location first.")
            return
        with right:
            with st.spinner("Fetching climate data…"):
                loc = geocode(loc_input.strip())
                if not loc:
                    st.error(f"Could not find '{loc_input}'. Try a different city name.")
                    return
                climate = fetch_climate_rain(loc["lat"], loc["lon"])
                plan = plan_water(
                    people, PROFILES[profile], roof_area, ROOF_RUNOFF[roof_type],
                    garden_area, gw_system, climate,
                )
                st.session_state["ws_result"] = {"loc": loc, "plan": plan}
                st.session_state.pop("ws_ai_data", None)
                st.rerun()


if __name__ == "__main__":
    main()
