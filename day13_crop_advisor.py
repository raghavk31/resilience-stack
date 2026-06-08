"""
The Resilience Stack — Day 13
Crop Climate Advisor — Illustrated Edition

Location → botanical crop cards + illustrated AI farming strategy.
"""

import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

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

GLOBAL_AGRICULTURAL_POINTS = [
    # East Africa
    {"name": "Nairobi",        "lat": -1.3,  "lon": 36.8,   "region": "East Africa"},
    {"name": "Addis Ababa",    "lat":  9.0,  "lon": 38.7,   "region": "East Africa"},
    {"name": "Dar es Salaam",  "lat": -6.8,  "lon": 39.3,   "region": "East Africa"},
    {"name": "Kampala",        "lat":  0.3,  "lon": 32.6,   "region": "East Africa"},
    {"name": "Kigali",         "lat": -1.9,  "lon": 30.1,   "region": "East Africa"},
    # West Africa
    {"name": "Lagos",          "lat":  6.5,  "lon":  3.4,   "region": "West Africa"},
    {"name": "Accra",          "lat":  5.6,  "lon": -0.2,   "region": "West Africa"},
    {"name": "Dakar",          "lat": 14.7,  "lon":-17.4,   "region": "West Africa"},
    {"name": "Kano",           "lat": 12.0,  "lon":  8.5,   "region": "West Africa"},
    {"name": "Bamako",         "lat": 12.6,  "lon": -8.0,   "region": "West Africa"},
    {"name": "Ouagadougou",    "lat": 12.4,  "lon": -1.5,   "region": "West Africa"},
    # Central Africa
    {"name": "Kinshasa",       "lat": -4.3,  "lon": 15.3,   "region": "Central Africa"},
    {"name": "Yaounde",        "lat":  3.9,  "lon": 11.5,   "region": "Central Africa"},
    # Southern Africa
    {"name": "Lusaka",         "lat":-15.4,  "lon": 28.3,   "region": "Southern Africa"},
    {"name": "Harare",         "lat":-17.8,  "lon": 31.0,   "region": "Southern Africa"},
    {"name": "Johannesburg",   "lat":-26.2,  "lon": 28.0,   "region": "Southern Africa"},
    {"name": "Cape Town",      "lat":-33.9,  "lon": 18.4,   "region": "Southern Africa"},
    {"name": "Lilongwe",       "lat":-13.9,  "lon": 33.8,   "region": "Southern Africa"},
    # North Africa
    {"name": "Cairo",          "lat": 30.1,  "lon": 31.2,   "region": "North Africa"},
    {"name": "Khartoum",       "lat": 15.6,  "lon": 32.5,   "region": "North Africa"},
    {"name": "Casablanca",     "lat": 33.6,  "lon": -7.6,   "region": "North Africa"},
    {"name": "Tunis",          "lat": 36.8,  "lon": 10.2,   "region": "North Africa"},
    # South Asia
    {"name": "Delhi",          "lat": 28.6,  "lon": 77.2,   "region": "South Asia"},
    {"name": "Mumbai",         "lat": 19.1,  "lon": 72.9,   "region": "South Asia"},
    {"name": "Chennai",        "lat": 13.1,  "lon": 80.3,   "region": "South Asia"},
    {"name": "Kolkata",        "lat": 22.6,  "lon": 88.4,   "region": "South Asia"},
    {"name": "Dhaka",          "lat": 23.7,  "lon": 90.4,   "region": "South Asia"},
    {"name": "Kathmandu",      "lat": 27.7,  "lon": 85.3,   "region": "South Asia"},
    {"name": "Colombo",        "lat":  6.9,  "lon": 79.9,   "region": "South Asia"},
    {"name": "Lahore",         "lat": 31.5,  "lon": 74.3,   "region": "South Asia"},
    # Southeast Asia
    {"name": "Bangkok",        "lat": 13.8,  "lon":100.5,   "region": "Southeast Asia"},
    {"name": "Ho Chi Minh",    "lat": 10.8,  "lon":106.7,   "region": "Southeast Asia"},
    {"name": "Manila",         "lat": 14.6,  "lon":121.0,   "region": "Southeast Asia"},
    {"name": "Jakarta",        "lat": -6.2,  "lon":106.8,   "region": "Southeast Asia"},
    {"name": "Yangon",         "lat": 16.9,  "lon": 96.2,   "region": "Southeast Asia"},
    {"name": "Phnom Penh",     "lat": 11.6,  "lon":104.9,   "region": "Southeast Asia"},
    {"name": "Kuala Lumpur",   "lat":  3.1,  "lon":101.7,   "region": "Southeast Asia"},
    # East Asia
    {"name": "Beijing",        "lat": 39.9,  "lon":116.4,   "region": "East Asia"},
    {"name": "Shanghai",       "lat": 31.2,  "lon":121.5,   "region": "East Asia"},
    {"name": "Guangzhou",      "lat": 23.1,  "lon":113.3,   "region": "East Asia"},
    {"name": "Chengdu",        "lat": 30.7,  "lon":104.1,   "region": "East Asia"},
    {"name": "Kunming",        "lat": 25.0,  "lon":102.7,   "region": "East Asia"},
    {"name": "Seoul",          "lat": 37.6,  "lon":127.0,   "region": "East Asia"},
    {"name": "Tokyo",          "lat": 35.7,  "lon":139.7,   "region": "East Asia"},
    # Central Asia
    {"name": "Tashkent",       "lat": 41.3,  "lon": 69.3,   "region": "Central Asia"},
    {"name": "Almaty",         "lat": 43.3,  "lon": 77.0,   "region": "Central Asia"},
    # Middle East
    {"name": "Riyadh",         "lat": 24.7,  "lon": 46.7,   "region": "Middle East"},
    {"name": "Tehran",         "lat": 35.7,  "lon": 51.4,   "region": "Middle East"},
    {"name": "Istanbul",       "lat": 41.0,  "lon": 29.0,   "region": "Middle East"},
    {"name": "Amman",          "lat": 31.9,  "lon": 35.9,   "region": "Middle East"},
    {"name": "Baghdad",        "lat": 33.3,  "lon": 44.4,   "region": "Middle East"},
    # Europe
    {"name": "Madrid",         "lat": 40.4,  "lon": -3.7,   "region": "Europe"},
    {"name": "Rome",           "lat": 41.9,  "lon": 12.5,   "region": "Europe"},
    {"name": "Paris",          "lat": 48.9,  "lon":  2.3,   "region": "Europe"},
    {"name": "Berlin",         "lat": 52.5,  "lon": 13.4,   "region": "Europe"},
    {"name": "Kyiv",           "lat": 50.5,  "lon": 30.5,   "region": "Europe"},
    {"name": "Moscow",         "lat": 55.8,  "lon": 37.6,   "region": "Europe"},
    {"name": "Athens",         "lat": 37.9,  "lon": 23.7,   "region": "Europe"},
    {"name": "Bucharest",      "lat": 44.4,  "lon": 26.1,   "region": "Europe"},
    # North America
    {"name": "Iowa Corn Belt", "lat": 41.9,  "lon":-93.6,   "region": "North America"},
    {"name": "Kansas City",    "lat": 39.1,  "lon":-94.6,   "region": "North America"},
    {"name": "Atlanta",        "lat": 33.7,  "lon":-84.4,   "region": "North America"},
    {"name": "Mexico City",    "lat": 19.4,  "lon":-99.1,   "region": "North America"},
    {"name": "Toronto",        "lat": 43.7,  "lon":-79.4,   "region": "North America"},
    {"name": "Guadalajara",    "lat": 20.7,  "lon":-103.3,  "region": "North America"},
    {"name": "Central Valley", "lat": 36.7,  "lon":-119.7,  "region": "North America"},
    # Latin America
    {"name": "Bogota",         "lat":  4.7,  "lon":-74.1,   "region": "Latin America"},
    {"name": "Medellin",       "lat":  6.2,  "lon":-75.6,   "region": "Latin America"},
    {"name": "Lima",           "lat":-12.0,  "lon":-77.0,   "region": "Latin America"},
    {"name": "Sao Paulo",      "lat":-23.5,  "lon":-46.6,   "region": "Latin America"},
    {"name": "Brasilia",       "lat":-15.8,  "lon":-47.9,   "region": "Latin America"},
    {"name": "Manaus",         "lat": -3.1,  "lon":-60.0,   "region": "Latin America"},
    {"name": "Buenos Aires",   "lat":-34.6,  "lon":-58.4,   "region": "Latin America"},
    {"name": "Cordoba (AR)",   "lat":-31.4,  "lon":-64.2,   "region": "Latin America"},
    {"name": "Santiago",       "lat":-33.5,  "lon":-70.6,   "region": "Latin America"},
    {"name": "Havana",         "lat": 23.1,  "lon":-82.4,   "region": "Latin America"},
    {"name": "Guatemala City", "lat": 14.6,  "lon":-90.5,   "region": "Latin America"},
    # Australia / Oceania
    {"name": "Sydney",         "lat":-33.9,  "lon":151.2,   "region": "Australia"},
    {"name": "Melbourne",      "lat":-37.8,  "lon":144.9,   "region": "Australia"},
    {"name": "Brisbane",       "lat":-27.5,  "lon":153.0,   "region": "Australia"},
    {"name": "Perth",          "lat":-31.9,  "lon":115.9,   "region": "Australia"},
    {"name": "Darwin",         "lat":-12.5,  "lon":130.8,   "region": "Australia"},
    {"name": "Auckland",       "lat":-36.9,  "lon":174.8,   "region": "Australia"},
]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1e293b; }

/* ── Viewport lock — panels scroll, page does not ── */
html { height: 100%; overflow: hidden !important; }
body { height: 100%; overflow: hidden !important; }
.stApp {
  height: 100vh !important; overflow: hidden !important;
  background:
    radial-gradient(ellipse at 12% 20%, rgba(22,163,74,.08) 0%, transparent 50%),
    radial-gradient(ellipse at 88% 78%, rgba(16,185,129,.09) 0%, transparent 55%),
    #edf2ed !important;
}
[data-testid="stAppViewContainer"] { height: 100vh !important; overflow: hidden !important; }
section.main { height: 100vh !important; overflow: hidden !important; background: transparent !important; }
section.main > div { height: 100vh !important; overflow: hidden !important; }
[data-testid="block-container"] {
  padding: 0 !important; max-width: 100% !important;
  height: 100vh !important; overflow: hidden !important; background: transparent !important;
}
section[data-testid="stSidebar"] { display: none !important; }

/* ── Header ── */
.ca-header {
  background: rgba(255,255,255,.97);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0,0,0,.07);
  padding: 10px 28px 8px;
}
.ca-topline {
  font-size: 9.5px; font-weight: 700; letter-spacing: .18em;
  text-transform: uppercase; color: #94a3b8;
  display: flex; align-items: center; gap: 7px; margin-bottom: 3px;
}
.ca-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #16a34a;
  display: inline-block; animation: blink 2.4s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
.ca-h1 { font-size: 1.28rem; font-weight: 900; color: #0f172a; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.3px; }
.ca-sub { font-size: .71rem; color: #94a3b8; margin-top: 1px; }

/* ── Two-panel layout — each column scrolls independently ── */
[data-testid="stHorizontalBlock"]:has(.ca-left) {
  gap: 0 !important; align-items: stretch !important;
  height: calc(100vh - 56px) !important; overflow: hidden !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child {
  height: calc(100vh - 56px) !important; overflow-y: auto !important;
  background: rgba(255,255,255,.94) !important;
  backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid rgba(0,0,0,.07) !important;
  scrollbar-width: thin; scrollbar-color: #dde3ea transparent;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child {
  height: calc(100vh - 56px) !important; overflow-y: auto !important;
  padding: 20px 24px 48px !important;
  scrollbar-width: thin; scrollbar-color: #dde3ea transparent;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }

/* Left-panel Streamlit widget overrides */
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"] input {
  font-size: .8rem !important; border-radius: 10px !important;
  border: 1.5px solid rgba(0,0,0,.1) !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
  border-radius: 10px !important; font-size: .77rem !important; font-weight: 700 !important;
  border: 1.5px solid rgba(0,0,0,.12) !important; transition: all .15s !important; padding: 8px 14px !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"] {
  background: #15803d !important; color: #fff !important; border-color: #15803d !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"]:hover {
  background: #14532d !important;
}
section.main label, section.main [data-testid="stWidgetLabel"] p { font-size: .73rem !important; font-weight: 600 !important; color: #475569 !important; }

/* ── Left panel HTML components ── */
.ca-left { display: none; }
.lp-pad  { padding: 16px 18px 10px; }
.lp-title { font-size: 1.05rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 3px; letter-spacing: -.15px; }
.lp-desc  { font-size: .71rem; color: #94a3b8; line-height: 1.55; }
.ca-sep   { border: none; border-top: 1px solid rgba(0,0,0,.07); margin: 0; }
.lp-lbl   { font-size: .6rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; color: #94a3b8; margin-bottom: 7px; display: block; padding: 0 18px; }
.lp-ai-pad { padding: 0 18px 14px; }
.lp-ai-desc { font-size: .69rem; color: #94a3b8; line-height: 1.5; margin-bottom: 10px; }

/* Mini climate box in left panel */
.lp-climate-box {
  background: linear-gradient(135deg, rgba(15,38,23,.92), rgba(22,60,35,.88));
  border-radius: 13px; padding: 13px 14px; margin: 0 18px 14px;
}
.lp-climate-label { font-size: .57rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.4); margin-bottom: 8px; }
.lp-climate-loc   { font-size: .85rem; font-weight: 800; color: #fff; font-family: 'Space Grotesk', sans-serif; margin-bottom: 10px; line-height: 1.2; }
.lp-climate-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.lp-stat { background: rgba(255,255,255,.08); border-radius: 9px; padding: 8px 10px; }
.lp-stat-icon  { font-size: .85rem; margin-bottom: 3px; }
.lp-stat-val   { font-size: .88rem; font-weight: 900; color: #fff; font-family: 'Space Grotesk', sans-serif; line-height: 1.1; }
.lp-stat-label { font-size: .55rem; color: rgba(255,255,255,.45); font-weight: 600; text-transform: uppercase; letter-spacing: .08em; }

/* ── Climate dashboard card ── */
.clim-card {
  background: #fff;
  border-radius: 18px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 20px rgba(0,0,0,.05);
  margin-bottom: 18px;
}
.clim-head {
  background: linear-gradient(135deg, #0c1f12 0%, #1a3a24 100%);
  padding: 16px 22px 14px;
}
.clim-head-label { font-size: .56rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: rgba(255,255,255,.38); margin-bottom: 6px; }
.clim-loc { font-size: 1.12rem; font-weight: 900; color: #fff; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.2px; }
.clim-body { display: grid; grid-template-columns: repeat(4, 1fr); }
.clim-stat {
  padding: 16px 12px 14px; border-right: 1px solid rgba(0,0,0,.06);
  text-align: center;
}
.clim-stat:last-child { border-right: none; }
.clim-icon-box {
  width: 38px; height: 38px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; margin: 0 auto 9px;
}
.clim-val  { font-size: 1.55rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; color: #0f172a; line-height: 1; }
.clim-unit { font-size: .55rem; font-weight: 700; color: #94a3b8; letter-spacing: .09em; text-transform: uppercase; margin-top: 3px; }
.clim-delta {
  display: inline-block; font-size: .62rem; font-weight: 700;
  margin-top: 7px; padding: 2px 8px; border-radius: 8px;
}

/* ── Crop grid ── */
.crop-count { font-size: .62rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; color: #94a3b8; margin-bottom: 12px; }
.legend { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
.leg-item { display: flex; align-items: center; gap: 5px; }
.leg-dot  { width: 8px; height: 8px; border-radius: 50%; }
.leg-text { font-size: .7rem; color: #64748b; }

.crop-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.crop-card {
  background: #fff;
  border-radius: 14px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.08);
  box-shadow: 0 1px 8px rgba(0,0,0,.04);
  display: flex; flex-direction: column;
  transition: transform .15s, box-shadow .15s;
}
.crop-card:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,0,0,.09); }
.crop-top-bar { height: 3px; flex-shrink: 0; }
.crop-inner { padding: 12px 12px 11px; flex: 1; display: flex; flex-direction: column; }
.crop-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; margin-bottom: 8px; }
.crop-emoji-bg {
  width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.5rem; line-height: 1;
}
.crop-cat-badge {
  font-size: .5rem; font-weight: 900; letter-spacing: .09em;
  text-transform: uppercase; padding: 3px 7px; border-radius: 7px; white-space: nowrap; margin-top: 2px;
}
.crop-name {
  font-size: .84rem; font-weight: 800; color: #0f172a;
  font-family: 'Space Grotesk', sans-serif; margin-bottom: 4px;
  letter-spacing: -.05px; line-height: 1.2;
}
.crop-notes {
  font-size: .63rem; color: #94a3b8; line-height: 1.4; margin-bottom: 10px; flex: 1;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
/* Score visualisation */
.crop-scores { margin-top: auto; }
.score-nums { display: flex; align-items: center; gap: 0; margin-bottom: 6px; font-family: 'Space Grotesk', sans-serif; }
.sn-item { text-align: center; flex: 1; }
.sn-lbl  { font-size: .5rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #b0b8c8; display: block; margin-bottom: 1px; }
.sn-val  { font-size: .95rem; font-weight: 900; line-height: 1.1; }
.sn-div  { color: #e2e8f0; font-size: .7rem; padding: 0 1px; }
.score-track-row { display: flex; align-items: center; gap: 6px; }
.score-track { flex: 1; height: 4px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.score-fill  { height: 100%; border-radius: 4px; }
.trend-badge {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .7rem; font-weight: 900; flex-shrink: 0;
}

/* ── Advice cards ── */
.adv-card {
  background: #fff;
  border-radius: 18px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 18px rgba(0,0,0,.04);
  margin-bottom: 14px;
}
.adv-head {
  display: flex; align-items: center; gap: 14px;
  padding: 15px 20px 13px;
  border-bottom: 1px solid rgba(0,0,0,.06);
}
.adv-icon-box {
  width: 46px; height: 46px; border-radius: 13px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.5rem;
}
.adv-section-num { font-size: .56rem; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; margin-bottom: 2px; }
.adv-title { font-size: .98rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; }
.adv-body { padding: 16px 20px 18px; }

/* Grow now tiles */
.gn-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.gn-tile {
  background: rgba(22,163,74,.05);
  border: 1px solid rgba(22,163,74,.14);
  border-radius: 13px; padding: 14px 13px;
  display: flex; flex-direction: column;
}
.gn-emoji-box {
  width: 46px; height: 46px; border-radius: 12px;
  background: rgba(22,163,74,.13);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.65rem; margin-bottom: 9px; flex-shrink: 0;
}
.gn-window {
  display: inline-block; font-size: .56rem; font-weight: 900;
  letter-spacing: .1em; text-transform: uppercase;
  padding: 2px 8px; border-radius: 7px; margin-bottom: 7px;
  background: rgba(22,163,74,.15); color: #15803d; align-self: flex-start;
}
.gn-name { font-size: .87rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 5px; line-height: 1.2; }
.gn-why  { font-size: .69rem; color: #4b5563; line-height: 1.45; margin-bottom: 8px; flex: 1; }
.gn-tip  { font-size: .66rem; color: #374151; line-height: 1.45; padding: 8px 9px; background: rgba(255,255,255,.85); border-radius: 8px; border-left: 2px solid #16a34a; }

/* Adapt 2035 */
.adp-split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.adp-col   { border-radius: 12px; padding: 13px 14px; }
.adp-col-label { font-size: .58rem; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 10px; }
.adp-item  { font-size: .72rem; color: #374151; line-height: 1.4; padding: 7px 0; border-bottom: 1px solid rgba(0,0,0,.05); display: flex; gap: 6px; align-items: flex-start; }
.adp-item:last-child { border-bottom: none; }
.adp-dot   { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; margin-top: 7px; }

/* By 2040 */
.y40-split   { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.y40-losing  { background: rgba(239,68,68,.05); border: 1px solid rgba(239,68,68,.14); border-radius: 13px; padding: 13px 14px; }
.y40-gaining { background: rgba(22,163,74,.05); border: 1px solid rgba(22,163,74,.14); border-radius: 13px; padding: 13px 14px; }
.y40-label   { font-size: .58rem; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 5px; }
.y40-item    { font-size: .72rem; color: #374151; margin-bottom: 7px; display: flex; gap: 6px; align-items: flex-start; line-height: 1.4; }
.y40-item:last-child { margin-bottom: 0; }
.y40-icon    { font-size: .8rem; flex-shrink: 0; }

/* Action tiles */
.act-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.act-tile  { border-radius: 16px; padding: 15px 14px 13px; border: 1px solid rgba(0,0,0,.07); box-shadow: 0 2px 12px rgba(0,0,0,.04); }
.act-top   { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.act-icon-box { width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; }
.act-num-circle { width: 25px; height: 25px; border-radius: 50%; color: #fff; font-size: .7rem; font-weight: 900; display: flex; align-items: center; justify-content: center; }
.act-when  { display: inline-block; font-size: .56rem; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; padding: 2px 8px; border-radius: 7px; margin-bottom: 7px; }
.act-title { font-size: .87rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 9px; line-height: 1.25; }
.act-step  { display: flex; gap: 6px; align-items: flex-start; font-size: .69rem; color: #4b5563; margin-bottom: 5px; line-height: 1.4; }
.act-step-circle { width: 17px; height: 17px; border-radius: 50%; color: #fff; font-size: .55rem; font-weight: 900; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.act-meta  { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
.act-pill  { display: flex; align-items: center; gap: 4px; background: rgba(255,255,255,.7); border-radius: 8px; padding: 3px 8px; font-size: .65rem; color: #64748b; font-weight: 500; border: 1px solid rgba(0,0,0,.06); }

/* ── Placeholder ── */
.ph-center { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 68vh; gap: 18px; padding: 32px 24px; text-align: center; }
.ph-big    { font-size: 3.2rem; line-height: 1; }
.ph-title  { font-size: 1.08rem; font-weight: 800; color: #1e293b; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.2px; }
.ph-desc   { font-size: .78rem; color: #94a3b8; max-width: 340px; line-height: 1.65; }
.ph-chips  { display: flex; gap: 7px; flex-wrap: wrap; justify-content: center; max-width: 430px; }
.ph-chip   { display: flex; align-items: center; gap: 6px; padding: 6px 11px; border-radius: 20px; background: rgba(255,255,255,.78); border: 1px solid rgba(0,0,0,.07); }
.ph-chip-icon { font-size: .95rem; }
.ph-chip-text { font-size: .7rem; font-weight: 500; color: #64748b; }

/* ── Global map tab ── */
[data-testid="stTabs"]         { overflow: visible !important; }
[data-testid="stTabContent"]   { overflow-y: auto !important; }
[data-testid="stDeckGlJsonChart"] { overflow: visible !important; border-radius: 14px; }
.map-desc { font-size: .76rem; color: #64748b; line-height: 1.55; padding: 12px 0 14px; }
.map-stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-top: 14px; }
.map-stat { border-radius: 13px; padding: 14px 16px; text-align: center; }
.map-stat-val { font-size: 1.5rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; line-height: 1; }
.map-stat-lbl { font-size: .6rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; margin-top: 4px; opacity: .75; }
.map-stat-sub { font-size: .66rem; margin-top: 3px; opacity: .5; }
.map-top-label { font-size: .6rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; color: #94a3b8; margin: 14px 0 8px; }
.map-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 20px;
  background: rgba(22,163,74,.1); border: 1px solid rgba(22,163,74,.2);
  margin: 3px; font-size: .72rem; color: #15803d; font-weight: 500;
}
.map-chip-score { font-weight: 800; }
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
        location_label += f" · {loc['country']}"

    def delta_pill(val: float, unit: str, bad_positive: bool = True) -> str:
        if abs(val) < 0.05:
            return '<span class="clim-delta" style="background:rgba(148,163,184,.1);color:#94a3b8">→ stable</span>'
        color_bg, color_text = (
            ("rgba(239,68,68,.12)", "#dc2626") if (val > 0) == bad_positive
            else ("rgba(22,163,74,.12)", "#16a34a")
        )
        arrow = "↑" if val > 0 else "↓"
        sign  = "+" if val > 0 else ""
        return (
            f'<span class="clim-delta" style="background:{color_bg};color:{color_text}">'
            f'{arrow} {sign}{val:.1f}{unit} by 2040</span>'
        )

    stat_defs = [
        ("🌡️", "rgba(239,68,68,.12)",  "Mean temp",   f"{curr['mean_temp']}", "°C",        delta_pill(proj["mean_temp"]-curr["mean_temp"], "°C", bad_positive=True)),
        ("🌧️", "rgba(59,130,246,.12)", "Annual rain", f"{curr['annual_precip']:.0f}", "mm/yr", delta_pill(proj["annual_precip"]-curr["annual_precip"], "mm", bad_positive=False)),
        ("❄️",  "rgba(99,102,241,.12)", "Frost days",  f"{curr['frost_days']:.0f}", "days/yr", delta_pill(proj["frost_days"]-curr["frost_days"], "d", bad_positive=False)),
        ("🔥", "rgba(245,158,11,.12)", "Heat stress", f"{curr['heat_stress_days']:.0f}", "days >35°C", delta_pill(proj["heat_stress_days"]-curr["heat_stress_days"], "d", bad_positive=True)),
    ]

    stats_html = "".join(
        f'<div class="clim-stat">'
        f'<div class="clim-icon-box" style="background:{bg}">{icon}</div>'
        f'<div class="clim-val">{val}</div>'
        f'<div class="clim-unit">{unit}</div>'
        f'{pill}'
        f'</div>'
        for icon, bg, _label, val, unit, pill in stat_defs
    )

    return (
        f'<div class="clim-card">'
        f'<div class="clim-head">'
        f'<div class="clim-head-label">Climate Profile · 2019–2023 baseline → 2040 projection</div>'
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
        f'<div class="leg-item"><span class="leg-dot" style="background:#16a34a"></span><span class="leg-text">{well} well suited</span></div>'
        f'<div class="leg-item"><span class="leg-dot" style="background:#d97706"></span><span class="leg-text">{marg} marginal</span></div>'
        f'<div class="leg-item"><span class="leg-dot" style="background:#dc2626"></span><span class="leg-text">{not_s} not suited</span></div>'
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
        cat_color   = CAT_COLORS.get(c["category"], "#64748b")

        # Score bar: show NOW score width, gradient from now-color to 2040-color
        bar_width  = max(4, sn)
        bar_color  = f"linear-gradient(90deg, {col_now}, {col_40})"

        card = (
            f'<div class="crop-card">'
            f'<div class="crop-top-bar" style="background:linear-gradient(90deg,{col_now},{col_40})"></div>'
            f'<div class="crop-inner">'
            f'<div class="crop-header">'
            f'<div class="crop-emoji-bg" style="background:{cat_color}18">{c["emoji"]}</div>'
            f'<div class="crop-cat-badge" style="background:{cat_color}18;color:{cat_color}">{c["category"]}</div>'
            f'</div>'
            f'<div class="crop-name">{c["name"]}</div>'
            f'<div class="crop-notes">{c["notes"]}</div>'
            f'<div class="crop-scores">'
            f'<div class="score-nums">'
            f'<div class="sn-item"><span class="sn-lbl">Now</span><span class="sn-val" style="color:{col_now}">{sn}</span></div>'
            f'<span class="sn-div">›</span>'
            f'<div class="sn-item"><span class="sn-lbl">2030</span><span class="sn-val" style="color:{col_30}">{s30}</span></div>'
            f'<span class="sn-div">›</span>'
            f'<div class="sn-item"><span class="sn-lbl">2040</span><span class="sn-val" style="color:{col_40}">{s40}</span></div>'
            f'</div>'
            f'<div class="score-track-row">'
            f'<div class="score-track"><div class="score-fill" style="width:{bar_width}%;background:{bar_color}"></div></div>'
            f'<div class="trend-badge" style="background:{arrow_color}18;color:{arrow_color}">{arrow}</div>'
            f'</div>'
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
        f'<div class="gn-emoji-box">{c.get("emoji","🌱")}</div>'
        f'<div class="gn-window">{c.get("window","")}</div>'
        f'<div class="gn-name">{c.get("name","")}</div>'
        f'<div class="gn-why">{c.get("why","")}</div>'
        f'<div class="gn-tip">💡 {c.get("tip","")}</div>'
        f'</div>'
        for c in crops[:3]
    )
    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(22,163,74,.08),rgba(22,163,74,.02))">'
        f'<div class="adv-icon-box" style="background:rgba(22,163,74,.14)">🌱</div>'
        f'<div>'
        f'<div class="adv-section-num" style="color:{col}">SECTION 01</div>'
        f'<div class="adv-title">What to Grow Now</div>'
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
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(245,158,11,.08),rgba(245,158,11,.02))">'
        f'<div class="adv-icon-box" style="background:rgba(245,158,11,.14)">🔄</div>'
        f'<div>'
        f'<div class="adv-section-num" style="color:{col}">SECTION 02</div>'
        f'<div class="adv-title">Adapt by 2035</div>'
        f'</div>'
        f'</div>'
        f'<div class="adv-body">'
        f'<div class="adp-split">'
        f'<div class="adp-col" style="background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.14)">'
        f'<div class="adp-col-label" style="color:{col}">🔀 Switch varieties</div>'
        + items_html(varieties, col) +
        f'</div>'
        f'<div class="adp-col" style="background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.14)">'
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
            f'<span class="y40-icon" style="color:#ef4444">↘</span>'
            f'<span>{item}</span>'
            f'</div>'
            for item in lst
        )

    def gain_items(lst):
        return "".join(
            f'<div class="y40-item">'
            f'<span class="y40-icon" style="color:#16a34a">↗</span>'
            f'<span>{item}</span>'
            f'</div>'
            for item in lst
        )

    return (
        f'<div class="adv-card">'
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(99,102,241,.08),rgba(99,102,241,.02))">'
        f'<div class="adv-icon-box" style="background:rgba(99,102,241,.13)">🌡️</div>'
        f'<div>'
        f'<div class="adv-section-num" style="color:{col}">SECTION 03</div>'
        f'<div class="adv-title">By 2040: What Changes</div>'
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
            f'<div class="act-step-circle" style="background:{ac}">{j+1}</div>'
            f'<span>{s}</span>'
            f'</div>'
            for j, s in enumerate(a.get("steps", []))
        )
        tiles.append(
            f'<div class="act-tile" style="background:linear-gradient(145deg,{ac}14,{ac}05)">'
            f'<div class="act-top">'
            f'<div class="act-icon-box" style="background:{ac}18">{a.get("icon","🌱")}</div>'
            f'<div class="act-num-circle" style="background:{ac}">{i+1}</div>'
            f'</div>'
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
        f'<div class="adv-head" style="background:linear-gradient(135deg,rgba(20,184,166,.08),rgba(20,184,166,.02))">'
        f'<div class="adv-icon-box" style="background:rgba(20,184,166,.14)">💡</div>'
        f'<div>'
        f'<div class="adv-section-num" style="color:{col}">SECTION 04</div>'
        f'<div class="adv-title">3 Actions This Season</div>'
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
    chips = "".join(
        f'<div class="ph-chip">'
        f'<span class="ph-chip-icon">{icon}</span>'
        f'<span class="ph-chip-text">{label}</span>'
        f'</div>'
        for icon, label in [
            ("🌡️", "Climate match"), ("📅", "2030 outlook"),
            ("🔮", "2040 outlook"), ("🌱", "What to grow"),
            ("🔄", "Adapt by 2035"), ("💡", "3 actions"),
        ]
    )
    st.markdown(
        f'<div class="ph-center">'
        f'<div class="ph-big">🌱</div>'
        f'<div class="ph-title">Crop Climate Advisor</div>'
        f'<div class="ph-desc">Enter any city or region to see botanical climate cards for 25 crops — and how each changes by 2030 and 2040.</div>'
        f'<div class="ph-chips">{chips}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Global crop map helpers ─────────────────────────────────────────────────────

def _fetch_climate_point_raw(lat: float, lon: float) -> dict | None:
    """Single-point climate fetch without Streamlit cache — safe for threading."""
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": lat, "longitude": lon,
                "start_date": "2019-01-01", "end_date": "2023-12-31",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        current = _parse_climate(r.json())
        p2030 = {
            "mean_temp":        round(current["mean_temp"] + 0.6, 1),
            "annual_precip":    round(current["annual_precip"] * 0.97, 0),
            "frost_days":       max(0.0, round(current["frost_days"] * 0.85, 1)),
            "heat_stress_days": round(current["heat_stress_days"] * 1.30, 1),
        }
        p2040 = {
            "mean_temp":        round(current["mean_temp"] + 1.1, 1),
            "annual_precip":    round(current["annual_precip"] * 0.94, 0),
            "frost_days":       max(0.0, round(current["frost_days"] * 0.70, 1)),
            "heat_stress_days": round(current["heat_stress_days"] * 1.65, 1),
        }
        return {"current": current, "2030": p2030, "2040": p2040}
    except Exception:
        return None


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fetch_global_map_climate() -> dict:
    """Parallel fetch for all 86 global agricultural points. Cached 7 days."""
    results = {}
    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = {
            executor.submit(_fetch_climate_point_raw, pt["lat"], pt["lon"]): pt
            for pt in GLOBAL_AGRICULTURAL_POINTS
        }
        for future in as_completed(futures):
            pt   = futures[future]
            data = future.result()
            if data:
                results[pt["name"]] = {"point": pt, "climate": data}
    return results


def _score_color(score: int) -> list[int]:
    if score >= 70:
        return [22, 163, 74, 215]
    if score >= 45:
        return [217, 119, 6, 215]
    return [220, 38, 38, 215]


def _render_global_map_tab() -> None:
    """Global crop suitability map: 86 agricultural zones, 3 time periods."""
    try:
        import pydeck as pdk
    except ImportError:
        st.error("pydeck is required for the map. Run: pip install pydeck")
        return

    st.markdown(
        '<div class="map-desc">'
        'Select a crop and time period. Each dot = one agricultural zone, coloured by climate suitability score (0–100).<br>'
        'Data: Open-Meteo archive 2019–2023 (current) · EC_Earth3P_HR fallback deltas for 2030/2040 · 86 zones worldwide.'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        map_crop = st.selectbox(
            "Crop",
            list(CROPS.keys()),
            key="map_crop",
            format_func=lambda x: f"{CROPS[x]['emoji']}  {x}",
        )
    with c2:
        map_year_label = st.radio(
            "Time period", ["Now (2019–23)", "2030", "2040"],
            horizontal=True, key="map_year",
        )
    year_key = "current" if "Now" in map_year_label else map_year_label

    # Load global data on demand
    if st.session_state.get("global_map_data") is None:
        col_btn, col_note = st.columns([1, 3])
        with col_btn:
            load = st.button("🌍 Load global climate data", type="primary", key="load_map")
        with col_note:
            st.markdown(
                '<div style="font-size:.71rem;color:#94a3b8;padding-top:10px">'
                'Fetches 86-point climate dataset in parallel (~25 s first run, then cached 7 days).</div>',
                unsafe_allow_html=True,
            )
        if load:
            with st.spinner("Fetching climate data for 86 global agricultural zones … (~25 s)"):
                st.session_state["global_map_data"] = fetch_global_map_climate()
            st.rerun()
        return

    global_data = st.session_state["global_map_data"]
    crop_info   = CROPS[map_crop]

    rows = []
    for name, item in global_data.items():
        pt   = item["point"]
        clim = item["climate"].get(year_key)
        if not clim:
            continue
        score = score_crop(crop_info, clim)
        label, _ = classify(score)
        rows.append({
            "name":   name,
            "region": pt["region"],
            "lat":    pt["lat"],
            "lon":    pt["lon"],
            "score":  score,
            "label":  label,
            "temp":   clim["mean_temp"],
            "precip": int(clim["annual_precip"]),
            "color":  _score_color(score),
        })

    if not rows:
        st.warning("No data loaded. Click 'Load global climate data'.")
        return

    df = pd.DataFrame(rows)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=260000,
        pickable=True,
        opacity=0.88,
        stroked=True,
        line_width_min_pixels=1,
        get_line_color=[255, 255, 255, 55],
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=15, longitude=15, zoom=1.15, pitch=0),
        tooltip={
            "html": (
                "<div style='font-family:Inter,sans-serif;padding:9px 13px;min-width:170px'>"
                "<div style='font-size:13px;font-weight:700;margin-bottom:2px'>{name}</div>"
                "<div style='font-size:11px;color:#94a3b8;margin-bottom:8px'>{region}</div>"
                "<div style='font-size:12px;font-weight:600'>{label} &bull; {score} / 100</div>"
                "<div style='font-size:11px;margin-top:5px'>🌡️ {temp}°C &nbsp;·&nbsp; 🌧️ {precip} mm/yr</div>"
                "</div>"
            ),
            "style": {
                "backgroundColor": "rgba(15,23,42,0.93)",
                "color": "white",
                "borderRadius": "10px",
                "border": "1px solid rgba(255,255,255,0.08)",
            },
        },
        map_provider="carto",
        map_style="light",
        height=480,
    )

    st.pydeck_chart(deck, use_container_width=True)

    # Summary stats
    well  = sum(1 for r in rows if r["score"] >= 70)
    marg  = sum(1 for r in rows if 45 <= r["score"] < 70)
    bad   = sum(1 for r in rows if r["score"] < 45)
    avg   = round(sum(r["score"] for r in rows) / len(rows))
    total = len(rows)

    st.markdown(
        f'<div class="map-stat-grid">'
        + "".join(
            f'<div class="map-stat" style="background:{bg}">'
            f'<div class="map-stat-val" style="color:{tc}">{val}</div>'
            f'<div class="map-stat-lbl" style="color:{tc}">{lbl}</div>'
            f'<div class="map-stat-sub" style="color:{tc}">{sub}</div>'
            f'</div>'
            for val, lbl, sub, bg, tc in [
                (well, "Well suited",  f"{well * 100 // total}% of zones", "rgba(22,163,74,.09)",  "#16a34a"),
                (marg, "Marginal",     f"{marg * 100 // total}% of zones", "rgba(217,119,6,.09)",  "#d97706"),
                (bad,  "Not suited",   f"{bad  * 100 // total}% of zones", "rgba(220,38,38,.09)",  "#dc2626"),
                (avg,  "Avg score",    "out of 100",                        "rgba(99,102,241,.09)", "#6366f1"),
            ]
        )
        + '</div>',
        unsafe_allow_html=True,
    )

    # Top suited zones
    top = [r for r in sorted(rows, key=lambda r: r["score"], reverse=True) if r["score"] >= 45][:10]
    if top:
        st.markdown('<div class="map-top-label">Top suited zones</div>', unsafe_allow_html=True)
        chips = "".join(
            f'<div class="map-chip">'
            f'<span class="map-chip-score">{r["score"]}</span> {r["name"]}'
            f'</div>'
            for r in top
        )
        st.markdown(f'<div style="display:flex;flex-wrap:wrap">{chips}</div>', unsafe_allow_html=True)


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="ca-header">'
        '<div class="ca-topline"><span class="ca-dot"></span>'
        'THE RESILIENCE STACK &nbsp;·&nbsp; DAY 13 OF 30</div>'
        '<div class="ca-h1">🌱 Crop Climate Advisor</div>'
        '<div class="ca-sub">25 crops · botanical climate cards · current vs 2030 &amp; 2040 · AI farming strategy</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    defaults = {"loc": None, "climate": None, "scores": [], "category": "All", "advice_data": None, "global_map_data": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    left_col, right_col = st.columns([1, 2.2])

    with left_col:
        st.markdown('<div class="ca-left"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="lp-pad">'
            '<div class="lp-title">Find your region</div>'
            '<div class="lp-desc">City, region, or country — anywhere in the world.</div>'
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
            st.markdown('<div style="padding: 0 18px 12px">', unsafe_allow_html=True)
            search_clicked = st.button("🔍 Analyse climate", use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<hr class="ca-sep">', unsafe_allow_html=True)
        st.markdown('<span class="lp-lbl" style="display:block;padding-top:14px">Filter crops</span>', unsafe_allow_html=True)
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
            # Mini climate summary
            curr = st.session_state["climate"]["current"]
            loc  = st.session_state["loc"]
            loc_label = loc["name"]
            if loc.get("country"):
                loc_label += f", {loc['country']}"
            st.markdown('<hr class="ca-sep" style="margin-top:10px">', unsafe_allow_html=True)
            st.markdown(
                f'<div class="lp-climate-box">'
                f'<div class="lp-climate-label">Current climate</div>'
                f'<div class="lp-climate-loc">📍 {loc_label}</div>'
                f'<div class="lp-climate-grid">'
                f'<div class="lp-stat"><div class="lp-stat-icon">🌡️</div>'
                f'<div class="lp-stat-val">{curr["mean_temp"]}°C</div>'
                f'<div class="lp-stat-label">Mean temp</div></div>'
                f'<div class="lp-stat"><div class="lp-stat-icon">🌧️</div>'
                f'<div class="lp-stat-val">{curr["annual_precip"]:.0f}mm</div>'
                f'<div class="lp-stat-label">Annual rain</div></div>'
                f'<div class="lp-stat"><div class="lp-stat-icon">❄️</div>'
                f'<div class="lp-stat-val">{curr["frost_days"]:.0f}d</div>'
                f'<div class="lp-stat-label">Frost days</div></div>'
                f'<div class="lp-stat"><div class="lp-stat-icon">🔥</div>'
                f'<div class="lp-stat-val">{curr["heat_stress_days"]:.0f}d</div>'
                f'<div class="lp-stat-label">Heat stress</div></div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<hr class="ca-sep">', unsafe_allow_html=True)
            st.markdown(
                '<div class="lp-ai-pad">'
                '<span class="lp-lbl" style="display:block;padding:14px 0 4px 0">AI Farming Strategy</span>'
                '<div class="lp-ai-desc">Illustrated advice for now, 2035, and 2040.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            with st.container():
                st.markdown('<div style="padding: 0 18px 16px">', unsafe_allow_html=True)
                ask_ai = st.button("🤖 Get illustrated advice", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            ask_ai = False

    with right_col:
        # Handle location search before tabs so st.stop() works cleanly
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

        tab_cards, tab_map = st.tabs(["📊 Crop Suitability Cards", "🗺️ Global Crop Map"])

        with tab_cards:
            if not st.session_state["climate"]:
                _placeholder()
            else:
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
                    f'<div class="crop-count">{len(scores)} crops · sorted by climate match</div>',
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

        with tab_map:
            _render_global_map_tab()


main()
