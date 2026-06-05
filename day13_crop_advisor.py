"""
The Resilience Stack — Day 13
Crop Climate Advisor — Illustrated Edition

Location → botanical crop cards + illustrated AI farming strategy.
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

CROPS: dict[str, dict] = {
    "Maize":          {"emoji":"🌽","category":"Staples","temp_opt":(18,26),"temp_abs":(10,34),"precip_opt":(600,1100),"precip_abs":(400,1800),"frost_days_max":5,"heat_days_max":50,"notes":"Versatile staple. Heat-tolerant varieties available."},
    "Rice":           {"emoji":"🌾","category":"Staples","temp_opt":(22,30),"temp_abs":(15,38),"precip_opt":(1000,2000),"precip_abs":(800,3000),"frost_days_max":0,"heat_days_max":30,"notes":"Requires warm, wet conditions. Zero frost tolerance."},
    "Wheat":          {"emoji":"🌾","category":"Staples","temp_opt":(10,18),"temp_abs":(5,24),"precip_opt":(350,750),"precip_abs":(250,1200),"frost_days_max":90,"heat_days_max":15,"notes":"Cool-season crop. Needs cold winters for vernalization."},
    "Sorghum":        {"emoji":"🌾","category":"Staples","temp_opt":(23,30),"temp_abs":(16,38),"precip_opt":(400,800),"precip_abs":(300,1500),"frost_days_max":5,"heat_days_max":100,"notes":"Excellent drought and heat tolerance. Key resilience crop."},
    "Pearl Millet":   {"emoji":"🌾","category":"Staples","temp_opt":(25,35),"temp_abs":(18,42),"precip_opt":(300,700),"precip_abs":(200,1000),"frost_days_max":0,"heat_days_max":120,"notes":"Extremely heat/drought tolerant. Top pick for hot arid farms."},
    "Cassava":        {"emoji":"🥔","category":"Staples","temp_opt":(22,30),"temp_abs":(18,38),"precip_opt":(750,1500),"precip_abs":(500,2500),"frost_days_max":0,"heat_days_max":80,"notes":"Drought-tolerant starchy root. Can be stored in the ground."},
    "Sweet Potato":   {"emoji":"🍠","category":"Staples","temp_opt":(20,28),"temp_abs":(14,35),"precip_opt":(700,1500),"precip_abs":(500,2000),"frost_days_max":0,"heat_days_max":60,"notes":"Resilient root crop. High vitamin A content."},
    "Teff":           {"emoji":"🌾","category":"Staples","temp_opt":(15,24),"temp_abs":(10,30),"precip_opt":(300,750),"precip_abs":(200,1200),"frost_days_max":10,"heat_days_max":45,"notes":"Ethiopian super grain. Highly drought tolerant and nutritious."},
    "Amaranth":       {"emoji":"🌿","category":"Staples","temp_opt":(18,28),"temp_abs":(12,36),"precip_opt":(400,900),"precip_abs":(300,1400),"frost_days_max":5,"heat_days_max":60,"notes":"Climate-resilient pseudocereal. Exceptional nutritional profile."},
    "Potato":         {"emoji":"🥔","category":"Vegetables","temp_opt":(10,18),"temp_abs":(5,25),"precip_opt":(500,1000),"precip_abs":(350,1500),"frost_days_max":30,"heat_days_max":10,"notes":"Cool-season staple. Tuber failure above 25°C mean temp."},
    "Common Beans":   {"emoji":"🫘","category":"Vegetables","temp_opt":(16,24),"temp_abs":(10,30),"precip_opt":(500,900),"precip_abs":(350,1400),"frost_days_max":5,"heat_days_max":25,"notes":"Key protein source. Heat stress at flowering drops yield sharply."},
    "Cowpeas":        {"emoji":"🫘","category":"Vegetables","temp_opt":(22,32),"temp_abs":(16,40),"precip_opt":(350,800),"precip_abs":(250,1200),"frost_days_max":0,"heat_days_max":80,"notes":"Heat/drought tolerant legume. Best bet for hot climates."},
    "Chickpeas":      {"emoji":"🫘","category":"Vegetables","temp_opt":(14,22),"temp_abs":(8,28),"precip_opt":(300,600),"precip_abs":(200,900),"frost_days_max":30,"heat_days_max":20,"notes":"Cool-season legume. Key crop in South Asia and East Africa."},
    "Lentils":        {"emoji":"🫘","category":"Vegetables","temp_opt":(10,18),"temp_abs":(5,24),"precip_opt":(250,500),"precip_abs":(150,750),"frost_days_max":60,"heat_days_max":10,"notes":"Cool-season legume. Drought tolerant in dry winters."},
    "Tomatoes":       {"emoji":"🍅","category":"Vegetables","temp_opt":(18,26),"temp_abs":(12,32),"precip_opt":(600,1200),"precip_abs":(400,1800),"frost_days_max":0,"heat_days_max":20,"notes":"High-value vegetable. Pollen sterility above 32°C."},
    "Onions":         {"emoji":"🧅","category":"Vegetables","temp_opt":(12,20),"temp_abs":(7,28),"precip_opt":(350,700),"precip_abs":(250,1000),"frost_days_max":30,"heat_days_max":25,"notes":"Cool-season bulb vegetable. High market value."},
    "Banana":         {"emoji":"🍌","category":"Fruits","temp_opt":(24,32),"temp_abs":(18,40),"precip_opt":(1200,2500),"precip_abs":(900,3500),"frost_days_max":0,"heat_days_max":60,"notes":"Perennial tropical fruit. Any frost is lethal."},
    "Mango":          {"emoji":"🥭","category":"Fruits","temp_opt":(24,34),"temp_abs":(18,42),"precip_opt":(600,1500),"precip_abs":(400,2500),"frost_days_max":0,"heat_days_max":80,"notes":"Tropical tree fruit. Needs a dry season to flower."},
    "Avocado":        {"emoji":"🥑","category":"Fruits","temp_opt":(16,26),"temp_abs":(10,34),"precip_opt":(800,1800),"precip_abs":(600,2500),"frost_days_max":5,"heat_days_max":30,"notes":"High-value tree fruit. Sensitive to frost and extreme heat."},
    "Groundnuts":     {"emoji":"🥜","category":"Cash Crops","temp_opt":(22,30),"temp_abs":(15,36),"precip_opt":(500,1000),"precip_abs":(350,1500),"frost_days_max":0,"heat_days_max":60,"notes":"Nitrogen-fixing legume. Dual food/oil/protein value."},
    "Soybeans":       {"emoji":"🫘","category":"Cash Crops","temp_opt":(18,26),"temp_abs":(12,35),"precip_opt":(600,1100),"precip_abs":(450,1600),"frost_days_max":5,"heat_days_max":40,"notes":"High-protein nitrogen-fixing legume."},
    "Coffee (Arabica)":{"emoji":"☕","category":"Cash Crops","temp_opt":(16,22),"temp_abs":(12,26),"precip_opt":(1200,2000),"precip_abs":(900,2800),"frost_days_max":0,"heat_days_max":10,"notes":"Most climate-vulnerable cash crop. Losing suitable zone fast."},
    "Tea":            {"emoji":"🍵","category":"Cash Crops","temp_opt":(14,22),"temp_abs":(10,28),"precip_opt":(1500,3000),"precip_abs":(1200,4000),"frost_days_max":5,"heat_days_max":15,"notes":"Cool, wet highlands crop. Highly climate-sensitive."},
    "Sunflower":      {"emoji":"🌻","category":"Cash Crops","temp_opt":(18,26),"temp_abs":(12,34),"precip_opt":(400,900),"precip_abs":(300,1300),"frost_days_max":10,"heat_days_max":40,"notes":"Oilseed crop. Moderately drought tolerant."},
    "Sesame":         {"emoji":"🌿","category":"Cash Crops","temp_opt":(24,32),"temp_abs":(18,40),"precip_opt":(350,700),"precip_abs":(250,1100),"frost_days_max":0,"heat_days_max":80,"notes":"Drought-tolerant oilseed. Thrives in hot, dry climates."},
}

CATEGORIES = ["All", "Staples", "Vegetables", "Fruits", "Cash Crops"]

CAT_COLORS = {
    "Staples":    "#f59e0b",
    "Vegetables": "#10b981",
    "Fruits":     "#f43f5e",
    "Cash Crops": "#6366f1",
}

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
[data-testid="block-container"] { padding:0 !important; max-width:100% !important; background:transparent !important; }
section[data-testid="stSidebar"] { display:none !important; }
[data-testid="stAppViewContainer"], section.main { background:transparent !important; }

.ca-header {
  background: rgba(255,255,255,.95);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0,0,0,.07);
  padding: 14px 28px 10px;
}
.ca-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #b0b8c8;
  display: flex; align-items: center; gap: 8px;
}
.ca-dot { width:8px; height:8px; border-radius:50%; background:#16a34a; display:inline-block; }

[data-testid="stHorizontalBlock"]:has(.ca-left) { gap:0 !important; align-items:stretch !important; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.90) !important;
  backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid rgba(0,0,0,.08) !important;
  min-height: calc(100vh - 60px);
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child {
  background: transparent !important;
  padding: 24px 28px 40px !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child
  [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child
  [data-testid="stRadio"] {
  padding-left: 20px !important; padding-right: 20px !important;
}

.ca-left  { height:0; margin:0; padding:0; display:block; }
.ca-pad   { padding:18px 22px 12px; }
.ca-title { font-size:1.18rem; font-weight:800; color:#0f172a; line-height:1.25; margin:0 0 .3rem; letter-spacing:-.2px; font-family:'Space Grotesk',sans-serif; }
.ca-desc  { font-size:.76rem; color:#94a3b8; line-height:1.6; margin:0; }
.ca-sep   { border:none; border-top:1px solid rgba(0,0,0,.07); margin:10px 0; }
.ca-lbl   { font-size:.62rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:#94a3b8; margin-bottom:7px; }

section.main label, section.main [data-testid="stWidgetLabel"] p { font-size:.75rem !important; font-weight:600 !important; color:#374151 !important; }
section.main [data-testid="stRadio"] > label { font-size:.74rem !important; font-weight:600 !important; color:#374151 !important; margin-bottom:4px !important; }
section.main [data-testid="stTextInput"] input { font-size:.8rem !important; border-radius:8px !important; }
section.main [data-testid="stButton"] > button {
  border-radius:8px !important; font-size:.74rem !important; font-weight:600 !important;
  border:1px solid rgba(0,0,0,.1) !important; background:rgba(255,255,255,.8) !important;
  backdrop-filter:blur(8px) !important; transition:all .15s !important; padding:6px 14px !important;
}
section.main [data-testid="stButton"] > button:hover { background:rgba(255,255,255,.97) !important; border-color:rgba(0,0,0,.18) !important; }
section.main [data-testid="stButton"] > button[kind="primary"] { background:#15803d !important; color:#fff !important; border-color:#15803d !important; }
section.main [data-testid="stButton"] > button[kind="primary"]:hover { background:#166534 !important; }

/* ── Climate dashboard card ── */
.clim-card {
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-radius: 18px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 20px rgba(0,0,0,.04);
  margin-bottom: 20px;
}
.clim-head {
  background: linear-gradient(135deg, rgba(22,163,74,.1), rgba(16,185,129,.05));
  border-bottom: 1px solid rgba(0,0,0,.06);
  padding: 14px 20px;
}
.clim-loc  { font-size:1.1rem; font-weight:900; color:#0f172a; font-family:'Space Grotesk',sans-serif; }
.clim-body { display:grid; grid-template-columns:repeat(4,1fr); gap:0; }
.clim-stat {
  padding: 14px 16px; border-right: 1px solid rgba(0,0,0,.05);
  text-align: center;
}
.clim-stat:last-child { border-right: none; }
.clim-icon { font-size: 1.4rem; margin-bottom: 5px; }
.clim-val  { font-size: 1.5rem; font-weight: 900; font-family:'Space Grotesk',sans-serif; color:#0f172a; line-height:1; }
.clim-unit { font-size: .6rem; font-weight: 700; color:#94a3b8; letter-spacing:.1em; text-transform:uppercase; margin-top: 2px; }
.clim-delta{ font-size: .68rem; font-weight: 700; margin-top: 5px; }

/* ── Botanical crop card ── */
.crop-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.crop-card {
  background: rgba(255,255,255,.90);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 12px rgba(0,0,0,.04);
  position: relative;
  transition: transform .15s, box-shadow .15s;
}
.crop-card:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,.08); }
.crop-top-bar { height: 3px; width: 100%; }
.crop-inner { padding: 14px 15px; }
.crop-row1 { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:9px; }
.crop-emoji { font-size: 2.2rem; line-height: 1; }
.crop-cat-badge { font-size:.55rem; font-weight:900; letter-spacing:.12em; text-transform:uppercase; padding:3px 8px; border-radius:8px; }
.crop-name { font-size:.88rem; font-weight:800; color:#0f172a; font-family:'Space Grotesk',sans-serif; margin-bottom:4px; letter-spacing:-.05px; }
.crop-notes { font-size:.67rem; color:#94a3b8; line-height:1.4; margin-bottom:12px; }
.crop-scores { display:flex; align-items:center; gap:0; }
.cs-block { text-align:center; flex:1; }
.cs-label { font-size:.52rem; font-weight:900; letter-spacing:.1em; text-transform:uppercase; color:#b0b8c8; margin-bottom:3px; }
.cs-val   { font-size:1.15rem; font-weight:900; font-family:'Space Grotesk',sans-serif; line-height:1; }
.cs-sep   { font-size:.65rem; color:#e2e8f0; padding:0 2px; }
.crop-arrow { margin-left:6px; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.88rem; font-weight:900; flex-shrink:0; }

/* ── Legend ── */
.legend { display:flex; gap:14px; margin-bottom:14px; flex-wrap:wrap; }
.leg-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }

/* ── Advice card ── */
.adv-card {
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-radius: 18px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 20px rgba(0,0,0,.04);
  margin-bottom: 14px;
}
.adv-head {
  display: flex; align-items: center; gap: 13px;
  padding: 14px 20px 12px;
  border-bottom: 1px solid rgba(0,0,0,.055);
}
.adv-head-icon { font-size: 2rem; line-height: 1; flex-shrink: 0; }
.adv-head-step { font-size: .58rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; margin-bottom: 2px; }
.adv-head-title{ font-size: 1rem; font-weight: 800; color: #0f172a; font-family:'Space Grotesk',sans-serif; }
.adv-body { padding: 16px 20px 18px; }

/* ── Grow-now crop tile ── */
.gn-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.gn-tile {
  background: rgba(22,163,74,.06);
  border: 1px solid rgba(22,163,74,.15);
  border-radius: 13px; padding: 14px 13px;
}
.gn-emoji  { font-size:1.8rem; margin-bottom:7px; line-height:1; }
.gn-window { display:inline-block; font-size:.58rem; font-weight:900; letter-spacing:.1em; text-transform:uppercase; padding:2px 7px; border-radius:7px; background:rgba(22,163,74,.15); color:#15803d; margin-bottom:7px; }
.gn-name   { font-size:.85rem; font-weight:800; color:#0f172a; font-family:'Space Grotesk',sans-serif; margin-bottom:5px; }
.gn-why    { font-size:.71rem; color:#4b5563; line-height:1.4; margin-bottom:6px; }
.gn-tip    { font-size:.68rem; color:#64748b; line-height:1.4; padding:6px 8px; background:rgba(255,255,255,.7); border-radius:7px; border-left:2px solid #16a34a; }

/* ── Adapt split ── */
.adp-split { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.adp-col   { border-radius:12px; padding:12px 14px; }
.adp-col-label { font-size:.6rem; font-weight:900; letter-spacing:.14em; text-transform:uppercase; margin-bottom:9px; }
.adp-item  { font-size:.74rem; color:#374151; line-height:1.4; padding:6px 0; border-bottom:1px solid rgba(0,0,0,.05); display:flex; gap:7px; align-items:flex-start; }
.adp-item:last-child { border-bottom:none; }
.adp-dot   { width:5px; height:5px; border-radius:50%; flex-shrink:0; margin-top:6px; }

/* ── By 2040 split ── */
.y40-split { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.y40-losing{ background:rgba(239,68,68,.06); border:1px solid rgba(239,68,68,.15); border-radius:13px; padding:13px 14px; }
.y40-gaining{background:rgba(22,163,74,.06); border:1px solid rgba(22,163,74,.15); border-radius:13px; padding:13px 14px; }
.y40-label { font-size:.6rem; font-weight:900; letter-spacing:.14em; text-transform:uppercase; margin-bottom:9px; }
.y40-item  { font-size:.74rem; color:#374151; margin-bottom:6px; display:flex; gap:6px; align-items:flex-start; line-height:1.35; }

/* ── Action tiles (same as Day 12) ── */
.act-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:4px; }
.act-tile {
  border-radius: 18px; padding: 20px 16px 16px;
  position: relative; overflow: hidden;
  border: 1px solid rgba(0,0,0,.08);
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
}
.act-num {
  position:absolute; top:14px; right:14px;
  width:27px; height:27px; border-radius:50%;
  color:white; font-size:.72rem; font-weight:900;
  display:flex; align-items:center; justify-content:center;
}
.act-big  { font-size:2.4rem; margin-bottom:10px; line-height:1; }
.act-when {
  display:inline-block; font-size:.58rem; font-weight:900;
  letter-spacing:.12em; text-transform:uppercase;
  padding:3px 9px; border-radius:8px; margin-bottom:9px;
}
.act-title{ font-size:.9rem; font-weight:800; color:#0f172a; font-family:'Space Grotesk',sans-serif; margin-bottom:11px; line-height:1.25; }
.act-step { display:flex; gap:7px; align-items:flex-start; font-size:.72rem; color:#4b5563; margin-bottom:5px; line-height:1.4; }
.act-step-dot{ width:5px; height:5px; border-radius:50%; flex-shrink:0; margin-top:6px; }
.act-meta { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; }
.act-pill { display:flex; align-items:center; gap:4px; background:rgba(255,255,255,.72); border-radius:8px; padding:4px 9px; font-size:.68rem; color:#64748b; font-weight:500; }
</style>
"""


# ── Climate helpers (unchanged logic) ──────────────────────────────────────────

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
    daily = data.get("daily", {})
    tmax_key = next((k for k in daily if "temperature_2m_max" in k), None)
    tmin_key = next((k for k in daily if "temperature_2m_min" in k), None)
    prec_key = next((k for k in daily if "precipitation_sum" in k), None)
    if not tmax_key:
        raise ValueError("Expected temperature keys not found in response")
    tmax  = pd.Series(daily[tmax_key], dtype=float).dropna()
    tmin  = pd.Series(daily[tmin_key], dtype=float).dropna()
    prec  = pd.Series(daily[prec_key], dtype=float).fillna(0)
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
            delta_t = 0.6 if year == 2030 else 1.1
            projections[str(year)] = {
                "mean_temp":        round(current["mean_temp"] + delta_t, 1),
                "annual_precip":    round(current["annual_precip"] * (0.97 if year == 2030 else 0.94), 0),
                "frost_days":       max(0.0, round(current["frost_days"] * (0.85 if year == 2030 else 0.70), 1)),
                "heat_stress_days": round(current["heat_stress_days"] * (1.30 if year == 2030 else 1.65), 1),
            }

    return {"current": current, "2030": projections["2030"], "2040": projections["2040"]}


def score_crop(crop: dict, climate: dict) -> int:
    score = 100.0
    mt, prec, frost, heat = climate["mean_temp"], climate["annual_precip"], climate["frost_days"], climate["heat_stress_days"]
    to_lo, to_hi = crop["temp_opt"]
    t_lo,  t_hi  = crop["temp_abs"]
    po_lo, po_hi = crop["precip_opt"]
    p_lo,  p_hi  = crop["precip_abs"]
    if mt < to_lo:
        score -= (to_lo - mt) * 8
        if mt < t_lo:
            score -= (t_lo - mt) * 20
    elif mt > to_hi:
        score -= (mt - to_hi) * 8
        if mt > t_hi:
            score -= (mt - t_hi) * 20
    if prec < po_lo:
        score -= (po_lo - prec) / max(po_lo, 1) * 30
        if prec < p_lo:
            score -= (p_lo - prec) / max(p_lo, 1) * 20
    elif prec > po_hi:
        score -= (prec - po_hi) / max(po_hi, 1) * 20
        if prec > p_hi:
            score -= (prec - p_hi) / max(p_hi, 1) * 15
    fdmax = crop["frost_days_max"]
    if frost > fdmax:
        score -= min(55, (frost - fdmax) * (3.0 if fdmax == 0 else 1.5))
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


# ── AI advice (JSON mode) ────────────────────────────────────────────────────────

def build_advice_prompt(location_name: str, climate: dict, scores: list[dict]) -> str:
    top5 = [c for c in scores if c["score_now"] >= 45][:5]
    declining = sorted(
        [c for c in scores if c["delta"] < -10 and c["score_now"] >= 40],
        key=lambda x: x["delta"]
    )[:3]

    def fmt(c): return f"{c['emoji']} {c['name']} ({c['score_now']}→{c['score_2040']} by 2040)"

    curr = climate["current"]
    proj = climate["2040"]
    top_str = ", ".join(fmt(c) for c in top5) or "none"
    dec_str = ", ".join(fmt(c) for c in declining) or "none"

    return f"""You are an expert agricultural advisor for smallholder farmers adapting to climate change.

LOCATION: {location_name}
CURRENT CLIMATE: Mean {curr['mean_temp']}°C, Rain {curr['annual_precip']:.0f}mm/yr, Frost {curr['frost_days']:.0f} days/yr, Heat stress {curr['heat_stress_days']:.0f} days/yr
2040 PROJECTION: Mean {proj['mean_temp']}°C (+{proj['mean_temp']-curr['mean_temp']:.1f}°C), Rain {proj['annual_precip']:.0f}mm/yr, Heat {proj['heat_stress_days']:.0f} days/yr
BEST CROPS NOW: {top_str}
CROPS DECLINING BY 2040: {dec_str}

Return ONLY valid JSON, no prose, no markdown fences, exactly this schema:
{{
  "grow_now": [
    {{
      "emoji":"🌾","name":"Sorghum",
      "why":"Matches your heat + low-rainfall profile exactly",
      "tip":"Plant at start of rains in May. Space 60cm apart. Intercrop with cowpeas.",
      "window":"May–August"
    }}
  ],
  "adapt_2035": {{
    "varieties": ["Switch to heat-tolerant Sorghum SC403 — 20% better yield above 32°C"],
    "introduce": ["Add Cowpeas as second crop — fixes nitrogen + handles heat stress days"]
  }},
  "by_2040": {{
    "losing": ["Coffee (Arabica) — heat stress days will exceed 10/yr tolerance by 2038"],
    "gaining": ["Pearl Millet — 2040 projections fall squarely in its optimal range"]
  }},
  "actions": [
    {{
      "icon":"🌱","title":"Diversity trial this season",
      "when":"This planting season",
      "steps":["Select 2 new heat-tolerant varieties from your list","Plant 1 row each alongside existing crops","Record germination and first-harvest yields for comparison"],
      "time":"3 hours","cost":"$8–15"
    }}
  ]
}}

grow_now: exactly 3 crops. adapt_2035.varieties: 2–3 items. adapt_2035.introduce: 2–3 items.
by_2040.losing: 2–3 items. by_2040.gaining: 2–3 items. actions: exactly 3 items.
Be specific to {location_name} and this climate profile. Write for a smallholder with limited resources."""


def call_advice_api(prompt: str) -> dict | None:
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
                "max_tokens": 2500,
                "temperature": 0.25,
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in content:
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else parts[0]
            if content.startswith("json"):
                content = content[4:].lstrip()
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return None


# ── HTML rendering ──────────────────────────────────────────────────────────────

def _climate_dashboard_html(loc: dict, climate: dict) -> str:
    curr = climate["current"]
    proj = climate["2040"]

    location_label = loc["name"]
    if loc.get("admin1"):
        location_label += f", {loc['admin1']}"
    if loc.get("country"):
        location_label += f", {loc['country']}"

    def delta_html(val: float, unit: str, bad_positive: bool = True) -> str:
        if abs(val) < 0.05:
            return '<span style="color:#94a3b8;font-size:.65rem">→ stable</span>'
        color = ("#ef4444" if val > 0 else "#16a34a") if bad_positive else ("#16a34a" if val > 0 else "#ef4444")
        arrow = "↑" if val > 0 else "↓"
        sign  = "+" if val > 0 else ""
        return f'<span style="color:{color};font-size:.68rem;font-weight:700">{arrow} {sign}{val:.1f}{unit} by 2040</span>'

    stats = [
        ("🌡️", "Mean temp", f"{curr['mean_temp']}", "°C",  delta_html(proj['mean_temp']-curr['mean_temp'], "°C", bad_positive=True)),
        ("🌧️", "Annual rain", f"{curr['annual_precip']:.0f}", "mm/yr", delta_html(proj['annual_precip']-curr['annual_precip'], "mm", bad_positive=False)),
        ("❄️",  "Frost days",  f"{curr['frost_days']:.0f}", "days/yr", delta_html(proj['frost_days']-curr['frost_days'], "d", bad_positive=False)),
        ("🔥", "Heat stress", f"{curr['heat_stress_days']:.0f}", "days >35°C", delta_html(proj['heat_stress_days']-curr['heat_stress_days'], "d", bad_positive=True)),
    ]

    stats_html = "".join(
        f'<div class="clim-stat">'
        f'<div class="clim-icon">{icon}</div>'
        f'<div class="clim-val">{val}</div>'
        f'<div class="clim-unit">{unit}</div>'
        f'<div class="clim-delta">{delta}</div>'
        f'</div>'
        for icon, label, val, unit, delta in stats
    )

    return (
        f'<div class="clim-card">'
        f'<div class="clim-head">'
        f'<div style="font-size:.6rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#94a3b8;margin-bottom:4px">Climate Profile · 2019–2023 baseline</div>'
        f'<div class="clim-loc">📍 {location_label}</div>'
        f'</div>'
        f'<div class="clim-body">{stats_html}</div>'
        f'</div>'
    )


def _legend_html(scores: list[dict]) -> str:
    well  = sum(1 for s in scores if s["score_now"] >= 70)
    marg  = sum(1 for s in scores if 45 <= s["score_now"] < 70)
    not_s = sum(1 for s in scores if s["score_now"] < 45)
    return (
        f'<div class="legend">'
        f'<div style="display:flex;align-items:center;gap:5px">'
        f'<span class="leg-dot" style="background:#16a34a"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{well} well suited</span></div>'
        f'<div style="display:flex;align-items:center;gap:5px">'
        f'<span class="leg-dot" style="background:#d97706"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{marg} marginal</span></div>'
        f'<div style="display:flex;align-items:center;gap:5px">'
        f'<span class="leg-dot" style="background:#dc2626"></span>'
        f'<span style="font-size:.72rem;color:#64748b">{not_s} not suited</span></div>'
        f'</div>'
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

        cat_color = CAT_COLORS.get(c["category"], "#64748b")

        # Background tint based on suitability
        if sn >= 70:
            bg_tint = "rgba(22,163,74,.04)"
        elif sn >= 45:
            bg_tint = "rgba(217,119,6,.04)"
        else:
            bg_tint = "rgba(220,38,38,.03)"

        card = (
            f'<div class="crop-card" style="background:{bg_tint} !important">'
            f'<div class="crop-top-bar" style="background:linear-gradient(90deg,{col_now},{col_40})"></div>'
            f'<div class="crop-inner">'
            f'<div class="crop-row1">'
            f'<div class="crop-emoji">{c["emoji"]}</div>'
            f'<div class="crop-cat-badge" style="background:{cat_color}15;color:{cat_color}">{c["category"]}</div>'
            f'</div>'
            f'<div class="crop-name">{c["name"]}</div>'
            f'<div class="crop-notes">{c["notes"]}</div>'
            f'<div class="crop-scores">'
            f'<div class="cs-block">'
            f'<div class="cs-label">Now</div>'
            f'<div class="cs-val" style="color:{col_now}">{sn}</div>'
            f'</div>'
            f'<div class="cs-sep">›</div>'
            f'<div class="cs-block">'
            f'<div class="cs-label">2030</div>'
            f'<div class="cs-val" style="color:{col_30}">{s30}</div>'
            f'</div>'
            f'<div class="cs-sep">›</div>'
            f'<div class="cs-block">'
            f'<div class="cs-label">2040</div>'
            f'<div class="cs-val" style="color:{col_40}">{s40}</div>'
            f'</div>'
            f'<div class="crop-arrow" style="background:{arrow_color}15;color:{arrow_color}">{arrow}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        cards.append(card)

    return f'<div class="crop-grid">{"".join(cards)}</div>'


# ── Advice section renderers ────────────────────────────────────────────────────

def _render_grow_now(crops: list) -> str:
    col = "#16a34a"
    tiles = "".join(
        f'<div class="gn-tile">'
        f'<div class="gn-emoji">{c.get("emoji","🌱")}</div>'
        f'<div class="gn-window">{c.get("window","")}</div>'
        f'<div class="gn-name">{c.get("name","")}</div>'
        f'<div class="gn-why">{c.get("why","")}</div>'
        f'<div class="gn-tip">💡 {c.get("tip","")}</div>'
        f'</div>'
        for c in crops[:3]
    )
    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(22,163,74,.1),rgba(22,163,74,.03))">'
        f'<div class="adv-head-icon">🌱</div>'
        f'<div>'
        f'<div class="adv-head-step" style="color:{col}">SECTION 01</div>'
        f'<div class="adv-head-title">What to Grow Now</div>'
        f'</div>'
        f'</div>'
        f'<div class="adv-body">'
        f'<div class="gn-grid">{tiles}</div>'
        f'</div>'
        f'</div>'
    )


def _render_adapt_2035(data: dict) -> str:
    col = "#f59e0b"
    varieties = data.get("varieties", [])
    introduce = data.get("introduce", [])

    def items_html(lst: list, dot_color: str) -> str:
        return "".join(
            f'<div class="adp-item">'
            f'<div class="adp-dot" style="background:{dot_color}"></div>'
            f'<span>{item}</span>'
            f'</div>'
            for item in lst
        )

    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(245,158,11,.1),rgba(245,158,11,.03))">'
        f'<div class="adv-head-icon">🔄</div>'
        f'<div>'
        f'<div class="adv-head-step" style="color:{col}">SECTION 02</div>'
        f'<div class="adv-head-title">Adapt by 2035</div>'
        f'</div>'
        f'</div>'
        f'<div class="adv-body">'
        f'<div class="adp-split">'
        f'<div class="adp-col" style="background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15)">'
        f'<div class="adp-col-label" style="color:{col}">🔀 Switch varieties</div>'
        + items_html(varieties, col) +
        f'</div>'
        f'<div class="adp-col" style="background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.15)">'
        f'<div class="adp-col-label" style="color:#10b981">✨ Introduce now</div>'
        + items_html(introduce, "#10b981") +
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_by_2040(data: dict) -> str:
    col = "#6366f1"
    losing  = data.get("losing", [])
    gaining = data.get("gaining", [])

    def loss_items(lst):
        return "".join(
            f'<div class="y40-item">'
            f'<span style="color:#ef4444;font-size:.8rem;flex-shrink:0">↘</span>'
            f'<span style="font-size:.74rem;color:#374151">{item}</span>'
            f'</div>'
            for item in lst
        )

    def gain_items(lst):
        return "".join(
            f'<div class="y40-item">'
            f'<span style="color:#16a34a;font-size:.8rem;flex-shrink:0">↗</span>'
            f'<span style="font-size:.74rem;color:#374151">{item}</span>'
            f'</div>'
            for item in lst
        )

    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(99,102,241,.1),rgba(99,102,241,.03))">'
        f'<div class="adv-head-icon">🌡️</div>'
        f'<div>'
        f'<div class="adv-head-step" style="color:{col}">SECTION 03</div>'
        f'<div class="adv-head-title">By 2040: What Changes</div>'
        f'</div>'
        f'</div>'
        f'<div class="adv-body">'
        f'<div class="y40-split">'
        f'<div class="y40-losing">'
        f'<div class="y40-label" style="color:#ef4444">⚠️ Becoming unviable</div>'
        + loss_items(losing) +
        f'</div>'
        f'<div class="y40-gaining">'
        f'<div class="y40-label" style="color:#16a34a">🌿 Opportunity crops</div>'
        + gain_items(gaining) +
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_actions(actions: list) -> str:
    col = "#14b8a6"
    action_cols = ["#14b8a6", "#f97316", "#8b5cf6"]
    tiles = []
    for i, a in enumerate(actions[:3]):
        ac = action_cols[i % 3]
        steps_html = "".join(
            f'<div class="act-step">'
            f'<div class="act-step-dot" style="background:{ac}"></div>'
            f'<span>{s}</span>'
            f'</div>'
            for s in a.get("steps", [])
        )
        tiles.append(
            f'<div class="act-tile" style="background:linear-gradient(145deg,{ac}12,{ac}05)">'
            f'<div class="act-num" style="background:{ac}">{i+1}</div>'
            f'<div class="act-big">{a.get("icon","🌱")}</div>'
            f'<div class="act-when" style="background:{ac}20;color:{ac}">{a.get("when","This season")}</div>'
            f'<div class="act-title">{a.get("title","")}</div>'
            + steps_html +
            f'<div class="act-meta">'
            f'<div class="act-pill">⏱ {a.get("time","")}</div>'
            f'<div class="act-pill">💰 {a.get("cost","")}</div>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(20,184,166,.1),rgba(20,184,166,.03))">'
        f'<div class="adv-head-icon">💡</div>'
        f'<div>'
        f'<div class="adv-head-step" style="color:{col}">SECTION 04</div>'
        f'<div class="adv-head-title">3 Actions This Season</div>'
        f'</div>'
        f'</div>'
        f'<div class="adv-body">'
        f'<div class="act-grid">{"".join(tiles)}</div>'
        f'</div>'
        f'</div>'
    )


def _render_advice(data: dict) -> None:
    st.markdown(_render_grow_now(data.get("grow_now", [])), unsafe_allow_html=True)
    st.markdown(_render_adapt_2035(data.get("adapt_2035", {})), unsafe_allow_html=True)
    st.markdown(_render_by_2040(data.get("by_2040", {})), unsafe_allow_html=True)
    st.markdown(_render_actions(data.get("actions", [])), unsafe_allow_html=True)


def _placeholder() -> None:
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;min-height:65vh;gap:20px;padding:32px 20px;text-align:center">'
        '<div style="font-size:3.5rem;line-height:1">🌱</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#1e293b;'
        'font-family:Space Grotesk,sans-serif;letter-spacing:-.2px">Crop Climate Advisor</div>'
        '<div style="font-size:.8rem;color:#94a3b8;max-width:360px;line-height:1.65">'
        'Enter any city or region to see botanical climate cards for 25 crops '
        '— and how each changes by 2030 and 2040.</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:4px;max-width:460px">'
        + "".join(
            f'<div style="display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:20px;'
            f'background:rgba(255,255,255,.7);border:1px solid rgba(0,0,0,.07);backdrop-filter:blur(8px)">'
            f'<span style="font-size:1rem">{icon}</span>'
            f'<span style="font-size:.72rem;font-weight:500;color:#64748b">{label}</span>'
            f'</div>'
            for icon, label in [
                ("🌡️", "Climate match"), ("📅", "2030 outlook"),
                ("🔮", "2040 outlook"), ("🌱", "What to grow"),
                ("🔄", "Adapt by 2035"), ("💡", "3 actions"),
            ]
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="ca-header">'
        '<div class="ca-topline"><span class="ca-dot"></span>'
        'THE RESILIENCE STACK &nbsp;·&nbsp; DAY 13 OF 30</div>'
        '<div class="ca-title" style="font-size:1.4rem;margin-top:4px">🌱 Crop Climate Advisor</div>'
        '<div class="ca-desc">25 crops · botanical climate cards · current vs 2030 &amp; 2040 · illustrated AI farming strategy</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    defaults = {"loc": None, "climate": None, "scores": [], "category": "All", "advice_data": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    left_col, right_col = st.columns([1, 2.2])

    with left_col:
        st.markdown('<div class="ca-left"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ca-pad">'
            '<div class="ca-title">Find your region</div>'
            '<div class="ca-desc">City, region, or country — anywhere in the world.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
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
            st.markdown(
                '<div style="padding:0 20px 8px">'
                '<div class="ca-lbl">AI Farming Strategy</div>'
                '<div class="ca-desc" style="padding:0 0 10px">Illustrated advice for now, 2035, and 2040.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            with st.container():
                st.markdown('<div style="padding: 0 20px 12px">', unsafe_allow_html=True)
                ask_ai = st.button("🤖 Get illustrated advice", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            ask_ai = False

    with right_col:
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

            st.session_state["loc"]         = loc
            st.session_state["climate"]     = climate
            st.session_state["scores"]      = compute_scores(climate)
            st.session_state["advice_data"] = None

        if not st.session_state["climate"]:
            _placeholder()
            st.stop()

        # Climate dashboard
        st.markdown(
            _climate_dashboard_html(st.session_state["loc"], st.session_state["climate"]),
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
            if not OPENROUTER_KEY:
                st.error("OPENROUTER_API_KEY not set.")
            else:
                with st.spinner("Claude is building your illustrated farming strategy…"):
                    advice_data = call_advice_api(
                        build_advice_prompt(
                            f'{st.session_state["loc"]["name"]}, {st.session_state["loc"]["country"]}',
                            st.session_state["climate"],
                            st.session_state["scores"],
                        )
                    )
                if advice_data is None:
                    st.error("Advice generation failed. Please try again.")
                else:
                    st.session_state["advice_data"] = advice_data
                    st.markdown("<br>", unsafe_allow_html=True)
                    _render_advice(advice_data)

        elif st.session_state.get("advice_data"):
            st.markdown("<br>", unsafe_allow_html=True)
            _render_advice(st.session_state["advice_data"])


main()
