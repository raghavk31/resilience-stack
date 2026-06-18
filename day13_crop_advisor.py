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

# ISO 3166-1 alpha-3 country centroids — used by plotly choropleth (locationmode='ISO-3')
COUNTRY_CENTROIDS = [
    # ── Africa ──────────────────────────────────────────────────────────────────
    {"iso3": "DZA", "name": "Algeria",                  "lat": 28.0,  "lon":   3.0},
    {"iso3": "AGO", "name": "Angola",                   "lat":-11.2,  "lon":  17.9},
    {"iso3": "BEN", "name": "Benin",                    "lat":  9.3,  "lon":   2.3},
    {"iso3": "BWA", "name": "Botswana",                 "lat":-22.3,  "lon":  24.7},
    {"iso3": "BFA", "name": "Burkina Faso",             "lat": 12.4,  "lon":  -1.5},
    {"iso3": "BDI", "name": "Burundi",                  "lat": -3.4,  "lon":  29.9},
    {"iso3": "CPV", "name": "Cabo Verde",               "lat": 15.1,  "lon": -23.6},
    {"iso3": "CMR", "name": "Cameroon",                 "lat":  4.5,  "lon":  13.5},
    {"iso3": "CAF", "name": "Central African Republic", "lat":  6.6,  "lon":  20.5},
    {"iso3": "TCD", "name": "Chad",                     "lat": 15.5,  "lon":  18.7},
    {"iso3": "COM", "name": "Comoros",                  "lat":-11.7,  "lon":  43.3},
    {"iso3": "COD", "name": "DR Congo",                 "lat": -4.0,  "lon":  21.8},
    {"iso3": "COG", "name": "Republic of Congo",        "lat": -0.2,  "lon":  15.8},
    {"iso3": "CIV", "name": "Cote d'Ivoire",            "lat":  6.0,  "lon":  -5.5},
    {"iso3": "DJI", "name": "Djibouti",                 "lat": 11.8,  "lon":  42.6},
    {"iso3": "EGY", "name": "Egypt",                    "lat": 26.0,  "lon":  30.0},
    {"iso3": "GNQ", "name": "Equatorial Guinea",        "lat":  1.7,  "lon":  10.3},
    {"iso3": "ERI", "name": "Eritrea",                  "lat": 15.3,  "lon":  38.9},
    {"iso3": "SWZ", "name": "Eswatini",                 "lat":-26.5,  "lon":  31.5},
    {"iso3": "ETH", "name": "Ethiopia",                 "lat":  9.1,  "lon":  40.5},
    {"iso3": "GAB", "name": "Gabon",                    "lat": -1.0,  "lon":  11.8},
    {"iso3": "GMB", "name": "Gambia",                   "lat": 13.5,  "lon": -15.3},
    {"iso3": "GHA", "name": "Ghana",                    "lat":  8.0,  "lon":  -1.0},
    {"iso3": "GIN", "name": "Guinea",                   "lat": 11.0,  "lon": -10.9},
    {"iso3": "GNB", "name": "Guinea-Bissau",            "lat": 11.8,  "lon": -15.2},
    {"iso3": "KEN", "name": "Kenya",                    "lat": -1.3,  "lon":  36.8},
    {"iso3": "LSO", "name": "Lesotho",                  "lat":-29.6,  "lon":  28.2},
    {"iso3": "LBR", "name": "Liberia",                  "lat":  6.4,  "lon":  -9.4},
    {"iso3": "LBY", "name": "Libya",                    "lat": 25.0,  "lon":  17.0},
    {"iso3": "MDG", "name": "Madagascar",               "lat":-20.3,  "lon":  44.3},
    {"iso3": "MWI", "name": "Malawi",                   "lat":-13.3,  "lon":  34.3},
    {"iso3": "MLI", "name": "Mali",                     "lat": 17.6,  "lon":  -4.0},
    {"iso3": "MRT", "name": "Mauritania",               "lat": 20.3,  "lon": -10.9},
    {"iso3": "MUS", "name": "Mauritius",                "lat":-20.1,  "lon":  57.6},
    {"iso3": "MAR", "name": "Morocco",                  "lat": 31.8,  "lon":  -7.1},
    {"iso3": "MOZ", "name": "Mozambique",               "lat":-18.7,  "lon":  35.5},
    {"iso3": "NAM", "name": "Namibia",                  "lat":-22.0,  "lon":  17.0},
    {"iso3": "NER", "name": "Niger",                    "lat": 16.1,  "lon":   8.1},
    {"iso3": "NGA", "name": "Nigeria",                  "lat":  9.1,  "lon":   8.7},
    {"iso3": "RWA", "name": "Rwanda",                   "lat": -2.0,  "lon":  29.9},
    {"iso3": "STP", "name": "Sao Tome & Principe",      "lat":  0.2,  "lon":   6.6},
    {"iso3": "SEN", "name": "Senegal",                  "lat": 14.5,  "lon": -14.5},
    {"iso3": "SLE", "name": "Sierra Leone",             "lat":  8.5,  "lon": -11.8},
    {"iso3": "SOM", "name": "Somalia",                  "lat":  5.0,  "lon":  46.0},
    {"iso3": "ZAF", "name": "South Africa",             "lat":-29.0,  "lon":  25.0},
    {"iso3": "SSD", "name": "South Sudan",              "lat":  8.0,  "lon":  30.5},
    {"iso3": "SDN", "name": "Sudan",                    "lat": 15.6,  "lon":  32.5},
    {"iso3": "TZA", "name": "Tanzania",                 "lat": -6.4,  "lon":  35.0},
    {"iso3": "TGO", "name": "Togo",                     "lat":  8.6,  "lon":   1.2},
    {"iso3": "TUN", "name": "Tunisia",                  "lat": 34.0,  "lon":   9.0},
    {"iso3": "UGA", "name": "Uganda",                   "lat":  1.4,  "lon":  32.0},
    {"iso3": "ZMB", "name": "Zambia",                   "lat":-14.0,  "lon":  28.0},
    {"iso3": "ZWE", "name": "Zimbabwe",                 "lat":-19.0,  "lon":  29.0},
    # ── Asia ────────────────────────────────────────────────────────────────────
    {"iso3": "AFG", "name": "Afghanistan",              "lat": 33.9,  "lon":  67.7},
    {"iso3": "ARM", "name": "Armenia",                  "lat": 40.1,  "lon":  45.0},
    {"iso3": "AZE", "name": "Azerbaijan",               "lat": 40.4,  "lon":  49.9},
    {"iso3": "BHR", "name": "Bahrain",                  "lat": 26.0,  "lon":  50.6},
    {"iso3": "BGD", "name": "Bangladesh",               "lat": 23.7,  "lon":  90.4},
    {"iso3": "BTN", "name": "Bhutan",                   "lat": 27.5,  "lon":  90.4},
    {"iso3": "BRN", "name": "Brunei",                   "lat":  4.9,  "lon": 114.9},
    {"iso3": "KHM", "name": "Cambodia",                 "lat": 11.6,  "lon": 104.9},
    {"iso3": "CHN", "name": "China",                    "lat": 35.0,  "lon": 103.8},
    {"iso3": "CYP", "name": "Cyprus",                   "lat": 35.1,  "lon":  33.4},
    {"iso3": "GEO", "name": "Georgia",                  "lat": 42.3,  "lon":  43.4},
    {"iso3": "IND", "name": "India",                    "lat": 20.6,  "lon":  78.9},
    {"iso3": "IDN", "name": "Indonesia",                "lat": -2.5,  "lon": 118.0},
    {"iso3": "IRN", "name": "Iran",                     "lat": 32.4,  "lon":  53.7},
    {"iso3": "IRQ", "name": "Iraq",                     "lat": 33.2,  "lon":  43.7},
    {"iso3": "ISR", "name": "Israel",                   "lat": 31.5,  "lon":  35.0},
    {"iso3": "JPN", "name": "Japan",                    "lat": 36.2,  "lon": 138.3},
    {"iso3": "JOR", "name": "Jordan",                   "lat": 30.6,  "lon":  36.8},
    {"iso3": "KAZ", "name": "Kazakhstan",               "lat": 48.0,  "lon":  66.9},
    {"iso3": "KWT", "name": "Kuwait",                   "lat": 29.3,  "lon":  47.5},
    {"iso3": "KGZ", "name": "Kyrgyzstan",               "lat": 41.2,  "lon":  74.8},
    {"iso3": "LAO", "name": "Laos",                     "lat": 18.2,  "lon": 103.9},
    {"iso3": "LBN", "name": "Lebanon",                  "lat": 33.9,  "lon":  35.9},
    {"iso3": "MYS", "name": "Malaysia",                 "lat":  3.8,  "lon": 109.7},
    {"iso3": "MDV", "name": "Maldives",                 "lat":  3.2,  "lon":  73.2},
    {"iso3": "MNG", "name": "Mongolia",                 "lat": 46.9,  "lon": 103.8},
    {"iso3": "MMR", "name": "Myanmar",                  "lat": 19.2,  "lon":  96.7},
    {"iso3": "NPL", "name": "Nepal",                    "lat": 28.4,  "lon":  84.1},
    {"iso3": "PRK", "name": "North Korea",              "lat": 40.3,  "lon": 127.5},
    {"iso3": "OMN", "name": "Oman",                     "lat": 21.5,  "lon":  55.9},
    {"iso3": "PAK", "name": "Pakistan",                 "lat": 30.4,  "lon":  69.3},
    {"iso3": "PHL", "name": "Philippines",              "lat": 12.9,  "lon": 121.8},
    {"iso3": "QAT", "name": "Qatar",                    "lat": 25.3,  "lon":  51.2},
    {"iso3": "SAU", "name": "Saudi Arabia",             "lat": 23.9,  "lon":  45.1},
    {"iso3": "SGP", "name": "Singapore",                "lat":  1.4,  "lon": 103.8},
    {"iso3": "KOR", "name": "South Korea",              "lat": 36.5,  "lon": 127.9},
    {"iso3": "LKA", "name": "Sri Lanka",                "lat":  7.9,  "lon":  80.8},
    {"iso3": "SYR", "name": "Syria",                    "lat": 35.0,  "lon":  38.0},
    {"iso3": "TJK", "name": "Tajikistan",               "lat": 38.9,  "lon":  71.3},
    {"iso3": "THA", "name": "Thailand",                 "lat": 15.0,  "lon": 101.0},
    {"iso3": "TLS", "name": "Timor-Leste",              "lat": -8.9,  "lon": 125.7},
    {"iso3": "TKM", "name": "Turkmenistan",             "lat": 39.1,  "lon":  59.6},
    {"iso3": "TUR", "name": "Turkey",                   "lat": 39.1,  "lon":  35.6},
    {"iso3": "ARE", "name": "UAE",                      "lat": 24.5,  "lon":  54.5},
    {"iso3": "UZB", "name": "Uzbekistan",               "lat": 41.4,  "lon":  64.6},
    {"iso3": "VNM", "name": "Vietnam",                  "lat": 14.1,  "lon": 108.3},
    {"iso3": "YEM", "name": "Yemen",                    "lat": 15.9,  "lon":  48.5},
    # ── Europe ──────────────────────────────────────────────────────────────────
    {"iso3": "ALB", "name": "Albania",                  "lat": 41.2,  "lon":  20.2},
    {"iso3": "AND", "name": "Andorra",                  "lat": 42.5,  "lon":   1.6},
    {"iso3": "AUT", "name": "Austria",                  "lat": 47.5,  "lon":  14.6},
    {"iso3": "BLR", "name": "Belarus",                  "lat": 53.7,  "lon":  28.0},
    {"iso3": "BEL", "name": "Belgium",                  "lat": 50.5,  "lon":   4.5},
    {"iso3": "BIH", "name": "Bosnia & Herzegovina",     "lat": 44.2,  "lon":  17.9},
    {"iso3": "BGR", "name": "Bulgaria",                 "lat": 42.7,  "lon":  25.5},
    {"iso3": "HRV", "name": "Croatia",                  "lat": 45.1,  "lon":  15.2},
    {"iso3": "CZE", "name": "Czech Republic",           "lat": 49.8,  "lon":  15.5},
    {"iso3": "DNK", "name": "Denmark",                  "lat": 56.3,  "lon":   9.5},
    {"iso3": "EST", "name": "Estonia",                  "lat": 58.6,  "lon":  25.0},
    {"iso3": "FIN", "name": "Finland",                  "lat": 61.9,  "lon":  25.7},
    {"iso3": "FRA", "name": "France",                   "lat": 46.2,  "lon":   2.2},
    {"iso3": "DEU", "name": "Germany",                  "lat": 51.2,  "lon":  10.4},
    {"iso3": "GRC", "name": "Greece",                   "lat": 39.1,  "lon":  22.0},
    {"iso3": "HUN", "name": "Hungary",                  "lat": 47.2,  "lon":  19.5},
    {"iso3": "ISL", "name": "Iceland",                  "lat": 64.7,  "lon": -18.0},
    {"iso3": "IRL", "name": "Ireland",                  "lat": 53.1,  "lon":  -8.2},
    {"iso3": "ITA", "name": "Italy",                    "lat": 42.5,  "lon":  12.6},
    {"iso3": "LVA", "name": "Latvia",                   "lat": 57.0,  "lon":  25.0},
    {"iso3": "LIE", "name": "Liechtenstein",            "lat": 47.2,  "lon":   9.6},
    {"iso3": "LTU", "name": "Lithuania",                "lat": 55.9,  "lon":  23.9},
    {"iso3": "LUX", "name": "Luxembourg",               "lat": 49.8,  "lon":   6.1},
    {"iso3": "MLT", "name": "Malta",                    "lat": 35.9,  "lon":  14.5},
    {"iso3": "MDA", "name": "Moldova",                  "lat": 47.4,  "lon":  28.4},
    {"iso3": "MNE", "name": "Montenegro",               "lat": 42.8,  "lon":  19.4},
    {"iso3": "NLD", "name": "Netherlands",              "lat": 52.1,  "lon":   5.3},
    {"iso3": "MKD", "name": "North Macedonia",          "lat": 41.6,  "lon":  21.7},
    {"iso3": "NOR", "name": "Norway",                   "lat": 60.5,  "lon":   8.5},
    {"iso3": "POL", "name": "Poland",                   "lat": 52.1,  "lon":  19.4},
    {"iso3": "PRT", "name": "Portugal",                 "lat": 39.6,  "lon":  -8.0},
    {"iso3": "ROU", "name": "Romania",                  "lat": 45.9,  "lon":  24.9},
    {"iso3": "RUS", "name": "Russia",                   "lat": 61.5,  "lon": 105.3},
    {"iso3": "SRB", "name": "Serbia",                   "lat": 44.0,  "lon":  21.0},
    {"iso3": "SVK", "name": "Slovakia",                 "lat": 48.7,  "lon":  19.7},
    {"iso3": "SVN", "name": "Slovenia",                 "lat": 46.2,  "lon":  14.8},
    {"iso3": "ESP", "name": "Spain",                    "lat": 40.0,  "lon":  -4.0},
    {"iso3": "SWE", "name": "Sweden",                   "lat": 60.1,  "lon":  18.6},
    {"iso3": "CHE", "name": "Switzerland",              "lat": 46.8,  "lon":   8.2},
    {"iso3": "UKR", "name": "Ukraine",                  "lat": 49.0,  "lon":  31.5},
    {"iso3": "GBR", "name": "United Kingdom",           "lat": 54.5,  "lon":  -3.4},
    # ── Americas ────────────────────────────────────────────────────────────────
    {"iso3": "ATG", "name": "Antigua & Barbuda",        "lat": 17.1,  "lon": -61.8},
    {"iso3": "ARG", "name": "Argentina",                "lat":-34.6,  "lon": -58.4},
    {"iso3": "BHS", "name": "Bahamas",                  "lat": 24.2,  "lon": -76.0},
    {"iso3": "BRB", "name": "Barbados",                 "lat": 13.2,  "lon": -59.5},
    {"iso3": "BLZ", "name": "Belize",                   "lat": 17.3,  "lon": -88.5},
    {"iso3": "BOL", "name": "Bolivia",                  "lat":-17.1,  "lon": -64.7},
    {"iso3": "BRA", "name": "Brazil",                   "lat":-10.0,  "lon": -55.0},
    {"iso3": "CAN", "name": "Canada",                   "lat": 56.1,  "lon":-106.3},
    {"iso3": "CHL", "name": "Chile",                    "lat":-30.0,  "lon": -71.0},
    {"iso3": "COL", "name": "Colombia",                 "lat":  4.6,  "lon": -74.3},
    {"iso3": "CRI", "name": "Costa Rica",               "lat":  9.7,  "lon": -83.8},
    {"iso3": "CUB", "name": "Cuba",                     "lat": 21.6,  "lon": -79.0},
    {"iso3": "DMA", "name": "Dominica",                 "lat": 15.4,  "lon": -61.4},
    {"iso3": "DOM", "name": "Dominican Republic",       "lat": 18.7,  "lon": -70.2},
    {"iso3": "ECU", "name": "Ecuador",                  "lat": -1.8,  "lon": -78.2},
    {"iso3": "SLV", "name": "El Salvador",              "lat": 13.8,  "lon": -88.9},
    {"iso3": "GRD", "name": "Grenada",                  "lat": 12.1,  "lon": -61.7},
    {"iso3": "GTM", "name": "Guatemala",                "lat": 15.8,  "lon": -90.2},
    {"iso3": "GUY", "name": "Guyana",                   "lat":  4.9,  "lon": -58.9},
    {"iso3": "HTI", "name": "Haiti",                    "lat": 19.1,  "lon": -72.3},
    {"iso3": "HND", "name": "Honduras",                 "lat": 15.2,  "lon": -86.2},
    {"iso3": "JAM", "name": "Jamaica",                  "lat": 18.1,  "lon": -77.3},
    {"iso3": "MEX", "name": "Mexico",                   "lat": 23.6,  "lon":-102.5},
    {"iso3": "NIC", "name": "Nicaragua",                "lat": 12.8,  "lon": -85.2},
    {"iso3": "PAN", "name": "Panama",                   "lat":  8.5,  "lon": -80.8},
    {"iso3": "PRY", "name": "Paraguay",                 "lat":-23.4,  "lon": -58.4},
    {"iso3": "PER", "name": "Peru",                     "lat": -9.2,  "lon": -75.0},
    {"iso3": "KNA", "name": "Saint Kitts & Nevis",      "lat": 17.3,  "lon": -62.7},
    {"iso3": "LCA", "name": "Saint Lucia",              "lat": 13.9,  "lon": -60.8},
    {"iso3": "VCT", "name": "St Vincent & Grenadines",  "lat": 13.3,  "lon": -61.2},
    {"iso3": "SUR", "name": "Suriname",                 "lat":  3.9,  "lon": -56.0},
    {"iso3": "TTO", "name": "Trinidad & Tobago",        "lat": 10.7,  "lon": -61.2},
    {"iso3": "USA", "name": "United States",            "lat": 37.1,  "lon": -95.7},
    {"iso3": "URY", "name": "Uruguay",                  "lat":-32.5,  "lon": -55.8},
    {"iso3": "VEN", "name": "Venezuela",                "lat":  8.0,  "lon": -66.6},
    # ── Oceania ──────────────────────────────────────────────────────────────────
    {"iso3": "AUS", "name": "Australia",                "lat":-25.3,  "lon": 133.8},
    {"iso3": "FJI", "name": "Fiji",                     "lat":-17.7,  "lon": 178.1},
    {"iso3": "KIR", "name": "Kiribati",                 "lat":  1.9,  "lon":-157.4},
    {"iso3": "MHL", "name": "Marshall Islands",         "lat":  7.1,  "lon": 171.2},
    {"iso3": "FSM", "name": "Micronesia",               "lat":  6.9,  "lon": 158.2},
    {"iso3": "NRU", "name": "Nauru",                    "lat": -0.5,  "lon": 166.9},
    {"iso3": "NZL", "name": "New Zealand",              "lat":-41.3,  "lon": 172.5},
    {"iso3": "PLW", "name": "Palau",                    "lat":  7.5,  "lon": 134.6},
    {"iso3": "PNG", "name": "Papua New Guinea",         "lat": -6.3,  "lon": 143.6},
    {"iso3": "WSM", "name": "Samoa",                    "lat":-13.8,  "lon":-172.1},
    {"iso3": "SLB", "name": "Solomon Islands",          "lat": -9.6,  "lon": 160.2},
    {"iso3": "TON", "name": "Tonga",                    "lat":-20.5,  "lon":-175.2},
    {"iso3": "TUV", "name": "Tuvalu",                   "lat": -8.5,  "lon": 179.2},
    {"iso3": "VUT", "name": "Vanuatu",                  "lat":-15.4,  "lon": 166.9},
]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1e293b; }

/* ── Background ── */
.stApp {
  background:
    radial-gradient(ellipse at 12% 18%, rgba(22,163,74,.07) 0%, transparent 50%),
    radial-gradient(ellipse at 88% 80%, rgba(16,185,129,.08) 0%, transparent 55%),
    #eef3ef !important;
}
[data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── Header ── */
.ca-header {
  background: linear-gradient(135deg, #071a0b 0%, #0f2d18 55%, #163d22 100%);
  padding: 14px 32px 16px;
  border-bottom: 2px solid rgba(74,222,128,.18);
}
.ca-topline {
  font-size: .65rem; font-weight: 700; letter-spacing: .2em;
  text-transform: uppercase; color: rgba(255,255,255,.38);
  display: flex; align-items: center; gap: 7px; margin-bottom: 5px;
}
.ca-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #4ade80;
  display: inline-block; animation: blink 2.4s ease-in-out infinite; flex-shrink: 0;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.25} }
.ca-h1 {
  font-size: 1.45rem; font-weight: 900; color: #fff;
  font-family: 'Space Grotesk', sans-serif; letter-spacing: -.4px; line-height: 1.15;
}
.ca-sub { font-size: .73rem; color: rgba(255,255,255,.42); margin-top: 4px; letter-spacing: .01em; }
.ca-badges { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.ca-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 20px;
  background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.12);
  font-size: .67rem; color: rgba(255,255,255,.65); font-weight: 600; white-space: nowrap;
}

/* ── Two-panel layout ── */
[data-testid="stHorizontalBlock"]:has(.ca-left) {
  gap: 0 !important; align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.97) !important;
  border-right: 1px solid rgba(0,0,0,.07) !important;
  overflow-y: auto !important; min-height: calc(100vh - 68px);
  scrollbar-width: thin; scrollbar-color: #dde3ea transparent;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child {
  overflow-y: auto !important; padding: 22px 26px 52px !important;
  scrollbar-width: thin; scrollbar-color: #dde3ea transparent;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:last-child::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }

/* Left-panel gap collapse + consistent 20px side padding */
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"] {
  gap: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"] {
  padding: 0 20px 14px !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] {
  padding: 0 20px 20px !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
  width: 100% !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stRadio"] {
  padding: 0 20px 8px !important;
}

/* Left-panel Streamlit widget overrides */
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"] input {
  font-size: .83rem !important; border-radius: 10px !important;
  border: 1.5px solid rgba(0,0,0,.11) !important; padding: 10px 14px !important;
  transition: border-color .15s !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stTextInput"] input:focus {
  border-color: #15803d !important; box-shadow: 0 0 0 3px rgba(21,128,61,.1) !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
  border-radius: 10px !important; font-size: .8rem !important; font-weight: 700 !important;
  transition: all .15s !important; padding: 10px 16px !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #16a34a, #14532d) !important;
  color: #fff !important; border: none !important;
  box-shadow: 0 2px 8px rgba(22,163,74,.28) !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #15803d, #0f3b20) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 14px rgba(22,163,74,.35) !important;
}
[data-testid="stHorizontalBlock"]:has(.ca-left) > [data-testid="stColumn"]:first-child [data-testid="stButton"] > button:not([kind="primary"]) {
  background: #f8fafc !important; color: #475569 !important;
  border: 1px solid rgba(0,0,0,.1) !important;
}
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .75rem !important; font-weight: 600 !important; color: #475569 !important;
}

/* ── Left panel HTML components ── */
.ca-left { display: none; }
.lp-pad  { padding: 20px 20px 12px; }
.lp-title { font-size: 1.08rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 4px; letter-spacing: -.15px; }
.lp-desc  { font-size: .74rem; color: #94a3b8; line-height: 1.6; }
.ca-sep   { border: none; border-top: 1px solid rgba(0,0,0,.07); margin: 0; }
.lp-lbl   { font-size: .65rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: #94a3b8; margin-bottom: 8px; display: block; padding: 0 20px; }
.lp-ai-pad { padding: 0 20px 16px; }
.lp-ai-desc { font-size: .73rem; color: #94a3b8; line-height: 1.55; margin-bottom: 11px; }

/* Mini climate box in left panel */
.lp-climate-box {
  background: linear-gradient(135deg, #071a0b 0%, #163d22 100%);
  border-radius: 14px; padding: 15px 16px; margin: 0 20px 16px;
  border: 1px solid rgba(74,222,128,.12);
}
.lp-climate-label { font-size: .62rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.38); margin-bottom: 8px; }
.lp-climate-loc   { font-size: .9rem; font-weight: 800; color: #fff; font-family: 'Space Grotesk', sans-serif; margin-bottom: 11px; line-height: 1.25; }
.lp-climate-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.lp-stat { background: rgba(255,255,255,.08); border-radius: 10px; padding: 9px 11px; }
.lp-stat-icon  { font-size: .9rem; margin-bottom: 4px; }
.lp-stat-val   { font-size: .93rem; font-weight: 900; color: #fff; font-family: 'Space Grotesk', sans-serif; line-height: 1.1; }
.lp-stat-label { font-size: .6rem; color: rgba(255,255,255,.42); font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-top: 2px; }

/* ── Climate dashboard card ── */
.clim-card {
  background: #fff;
  border-radius: 20px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 4px 28px rgba(0,0,0,.06);
  margin-bottom: 22px;
}
.clim-head {
  background: linear-gradient(135deg, #071a0b 0%, #163d22 100%);
  padding: 18px 24px 16px;
}
.clim-head-label { font-size: .63rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: rgba(255,255,255,.35); margin-bottom: 7px; }
.clim-loc { font-size: 1.18rem; font-weight: 900; color: #fff; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.2px; }
.clim-body { display: grid; grid-template-columns: repeat(4, 1fr); }
.clim-stat {
  padding: 18px 14px 16px; border-right: 1px solid rgba(0,0,0,.06);
  text-align: center;
}
.clim-stat:last-child { border-right: none; }
.clim-icon-box {
  width: 42px; height: 42px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem; margin: 0 auto 10px;
}
.clim-val  { font-size: 1.65rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; color: #0f172a; line-height: 1; }
.clim-unit { font-size: .62rem; font-weight: 700; color: #94a3b8; letter-spacing: .09em; text-transform: uppercase; margin-top: 4px; }
.clim-delta {
  display: inline-block; font-size: .67rem; font-weight: 700;
  margin-top: 8px; padding: 3px 9px; border-radius: 9px;
}

/* ── Crop grid ── */
.crop-count { font-size: .67rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; color: #94a3b8; margin-bottom: 13px; }
.legend { display: flex; gap: 14px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
.leg-item { display: flex; align-items: center; gap: 6px; }
.leg-dot  { width: 9px; height: 9px; border-radius: 50%; }
.leg-text { font-size: .74rem; color: #64748b; }

.crop-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.crop-card {
  background: #fff;
  border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.08);
  box-shadow: 0 2px 12px rgba(0,0,0,.04);
  display: flex; flex-direction: column;
  transition: transform .18s, box-shadow .18s;
}
.crop-card:hover { transform: translateY(-3px); box-shadow: 0 8px 28px rgba(0,0,0,.1); }
.crop-top-bar { height: 4px; flex-shrink: 0; }
.crop-inner { padding: 15px 15px 13px; flex: 1; display: flex; flex-direction: column; }
.crop-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; margin-bottom: 10px; }
.crop-emoji-bg {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.7rem; line-height: 1;
}
.crop-cat-badge {
  font-size: .58rem; font-weight: 900; letter-spacing: .09em;
  text-transform: uppercase; padding: 3px 8px; border-radius: 7px; white-space: nowrap; margin-top: 2px;
}
.crop-name {
  font-size: .9rem; font-weight: 800; color: #0f172a;
  font-family: 'Space Grotesk', sans-serif; margin-bottom: 5px;
  letter-spacing: -.05px; line-height: 1.25;
}
.crop-notes {
  font-size: .69rem; color: #94a3b8; line-height: 1.5; margin-bottom: 11px; flex: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
/* Score visualisation */
.crop-scores { margin-top: auto; }
.score-nums { display: flex; align-items: center; gap: 0; margin-bottom: 7px; font-family: 'Space Grotesk', sans-serif; }
.sn-item { text-align: center; flex: 1; }
.sn-lbl  { font-size: .58rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #b0b8c8; display: block; margin-bottom: 2px; }
.sn-val  { font-size: 1.05rem; font-weight: 900; line-height: 1.1; }
.sn-div  { color: #e2e8f0; font-size: .75rem; padding: 0 2px; }
.score-track-row { display: flex; align-items: center; gap: 7px; }
.score-track { flex: 1; height: 5px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.score-fill  { height: 100%; border-radius: 4px; }
.trend-badge {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .75rem; font-weight: 900; flex-shrink: 0;
}

/* ── Advice cards ── */
.adv-card {
  background: #fff;
  border-radius: 20px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 3px 22px rgba(0,0,0,.05);
  margin-bottom: 16px;
}
.adv-head {
  display: flex; align-items: center; gap: 16px;
  padding: 18px 22px 16px;
  border-bottom: 1px solid rgba(0,0,0,.06);
}
.adv-icon-box {
  width: 50px; height: 50px; border-radius: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.6rem;
}
.adv-section-num { font-size: .63rem; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; margin-bottom: 3px; }
.adv-title { font-size: 1.05rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; }
.adv-body { padding: 18px 22px 20px; }

/* Grow now tiles */
.gn-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.gn-tile {
  background: rgba(22,163,74,.05);
  border: 1px solid rgba(22,163,74,.15);
  border-radius: 15px; padding: 16px 15px;
  display: flex; flex-direction: column;
}
.gn-emoji-box {
  width: 50px; height: 50px; border-radius: 13px;
  background: rgba(22,163,74,.13);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.8rem; margin-bottom: 10px; flex-shrink: 0;
}
.gn-window {
  display: inline-block; font-size: .62rem; font-weight: 900;
  letter-spacing: .1em; text-transform: uppercase;
  padding: 3px 9px; border-radius: 8px; margin-bottom: 8px;
  background: rgba(22,163,74,.15); color: #15803d; align-self: flex-start;
}
.gn-name { font-size: .93rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 5px; line-height: 1.25; }
.gn-why  { font-size: .74rem; color: #4b5563; line-height: 1.5; margin-bottom: 9px; flex: 1; }
.gn-tip  { font-size: .71rem; color: #374151; line-height: 1.5; padding: 10px 11px; background: rgba(255,255,255,.9); border-radius: 9px; border-left: 3px solid #16a34a; }

/* Adapt 2035 */
.adp-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.adp-col   { border-radius: 14px; padding: 15px 16px; }
.adp-col-label { font-size: .64rem; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 12px; }
.adp-item  { font-size: .74rem; color: #374151; line-height: 1.5; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,.05); display: flex; gap: 7px; align-items: flex-start; }
.adp-item:last-child { border-bottom: none; }
.adp-dot   { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; margin-top: 7px; }

/* By 2040 */
.y40-split   { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.y40-losing  { background: rgba(239,68,68,.05); border: 1px solid rgba(239,68,68,.15); border-radius: 14px; padding: 15px 16px; }
.y40-gaining { background: rgba(22,163,74,.05); border: 1px solid rgba(22,163,74,.15); border-radius: 14px; padding: 15px 16px; }
.y40-label   { font-size: .64rem; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 11px; display: flex; align-items: center; gap: 5px; }
.y40-item    { font-size: .74rem; color: #374151; margin-bottom: 8px; display: flex; gap: 7px; align-items: flex-start; line-height: 1.5; }
.y40-item:last-child { margin-bottom: 0; }
.y40-icon    { font-size: .85rem; flex-shrink: 0; }

/* Action tiles */
.act-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.act-tile  { border-radius: 17px; padding: 17px 16px 15px; border: 1px solid rgba(0,0,0,.07); box-shadow: 0 2px 14px rgba(0,0,0,.04); }
.act-top   { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.act-icon-box { width: 46px; height: 46px; border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; }
.act-num-circle { width: 27px; height: 27px; border-radius: 50%; color: #fff; font-size: .72rem; font-weight: 900; display: flex; align-items: center; justify-content: center; }
.act-when  { display: inline-block; font-size: .63rem; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; padding: 3px 9px; border-radius: 8px; margin-bottom: 8px; }
.act-title { font-size: .93rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 10px; line-height: 1.25; }
.act-step  { display: flex; gap: 7px; align-items: flex-start; font-size: .72rem; color: #4b5563; margin-bottom: 6px; line-height: 1.5; }
.act-step-circle { width: 19px; height: 19px; border-radius: 50%; color: #fff; font-size: .62rem; font-weight: 900; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.act-meta  { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
.act-pill  { display: flex; align-items: center; gap: 4px; background: rgba(255,255,255,.75); border-radius: 8px; padding: 4px 9px; font-size: .68rem; color: #64748b; font-weight: 500; border: 1px solid rgba(0,0,0,.07); }

/* ── Placeholder ── */
.ph-center { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 65vh; gap: 20px; padding: 36px 24px; text-align: center; }
.ph-big    { font-size: 3.6rem; line-height: 1; }
.ph-title  { font-size: 1.15rem; font-weight: 800; color: #1e293b; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.2px; }
.ph-desc   { font-size: .8rem; color: #94a3b8; max-width: 360px; line-height: 1.7; }
.ph-chips  { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; max-width: 450px; }
.ph-chip   { display: flex; align-items: center; gap: 6px; padding: 7px 13px; border-radius: 20px; background: rgba(255,255,255,.82); border: 1px solid rgba(0,0,0,.08); box-shadow: 0 1px 4px rgba(0,0,0,.03); }
.ph-chip-icon { font-size: 1.0rem; }
.ph-chip-text { font-size: .73rem; font-weight: 500; color: #64748b; }

/* ── Global map tab ── */
[data-testid="stTabs"]         { overflow: visible !important; }
[data-testid="stTabContent"]   { overflow-y: auto !important; }
[data-testid="stDeckGlJsonChart"] { overflow: visible !important; border-radius: 14px; }
.map-desc { font-size: .78rem; color: #64748b; line-height: 1.6; padding: 14px 0 16px; }
.map-stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-top: 16px; }
.map-stat { border-radius: 14px; padding: 16px 18px; text-align: center; }
.map-stat-val { font-size: 1.6rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; line-height: 1; }
.map-stat-lbl { font-size: .63rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; margin-top: 5px; opacity: .75; }
.map-stat-sub { font-size: .68rem; margin-top: 4px; opacity: .55; }
.map-top-label { font-size: .63rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; color: #94a3b8; margin: 16px 0 9px; }
.map-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 12px; border-radius: 20px;
  background: rgba(22,163,74,.1); border: 1px solid rgba(22,163,74,.2);
  margin: 3px; font-size: .74rem; color: #15803d; font-weight: 500;
}
.map-chip-score { font-weight: 800; }

/* ── Tab styling ── */
[data-testid="stTabs"] button[data-baseweb="tab"] {
  font-size: .8rem !important; font-weight: 600 !important;
}
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

_MAP_DATA_VERSION = 3  # bump to force-invalidate cached session data


def _lat_climate_fallback(lat: float) -> dict:
    """Latitude-based climate estimate — used when the API call fails so every
    country still gets a colour on the choropleth."""
    a = abs(lat)
    if a < 10:
        t, p, frost, heat = 26.5, 1900, 0.0, 140
    elif a < 20:
        t, p, frost, heat = 24.0, 1300, 0.0,  90
    elif a < 30:
        t, p, frost, heat = 20.0,  600, 0.0,  40
    elif a < 35:
        t, p, frost, heat = 16.5,  650, 5.0,  15
    elif a < 42:
        t, p, frost, heat = 13.0,  700, 20.0,  6
    elif a < 50:
        t, p, frost, heat =  9.0,  650, 55.0,  1
    elif a < 58:
        t, p, frost, heat =  5.0,  600, 100.0, 0
    else:
        t, p, frost, heat =  0.0,  450, 160.0, 0
    return {"mean_temp": t, "annual_precip": float(p),
            "frost_days": float(frost), "heat_stress_days": float(heat)}


def _fetch_climate_point_raw(lat: float, lon: float) -> dict:
    """Single-point climate fetch without Streamlit cache — safe for threading.
    Falls back to a latitude estimate so the map has no grey holes."""
    def _proj(base: dict, dt: float, dp: float, df: float, dh: float) -> dict:
        return {
            "mean_temp":        round(base["mean_temp"] + dt, 1),
            "annual_precip":    round(base["annual_precip"] * dp, 0),
            "frost_days":       max(0.0, round(base["frost_days"] * df, 1)),
            "heat_stress_days": round(base["heat_stress_days"] * dh, 1),
        }
    try:
        r = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": lat, "longitude": lon,
                "start_date": "2019-01-01", "end_date": "2023-12-31",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            headers=HEADERS, timeout=25,
        )
        r.raise_for_status()
        current = _parse_climate(r.json())
    except Exception:
        current = _lat_climate_fallback(lat)
    return {
        "current": current,
        "2030":    _proj(current, 0.6, 0.97, 0.85, 1.30),
        "2040":    _proj(current, 1.1, 0.94, 0.70, 1.65),
    }


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fetch_global_map_climate(_version: int = _MAP_DATA_VERSION) -> dict:
    """Parallel fetch for all ~194 country centroids. Cached 7 days.
    The _version arg busts the cache automatically when _MAP_DATA_VERSION changes."""
    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(_fetch_climate_point_raw, pt["lat"], pt["lon"]): pt
            for pt in COUNTRY_CENTROIDS
        }
        for future in as_completed(futures):
            pt   = futures[future]
            data = future.result()
            results[pt["iso3"]] = {"point": pt, "climate": data}
    return results


def _render_global_map_tab() -> None:
    """Global crop suitability choropleth — ~194 countries, 3 time periods."""
    import plotly.graph_objects as go

    st.markdown(
        '<div class="map-desc">'
        'Select a crop and time period. Each country is filled by its climate suitability score — '
        'dark red = no fit, amber = marginal, green = well suited.<br>'
        'Data: Open-Meteo archive 2019–2023 (baseline) · EC_Earth3P_HR delta projections for 2030 / 2040 · ~194 countries.'
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

    # Invalidate stale session data from old formats
    if st.session_state.get("_map_ver") != _MAP_DATA_VERSION:
        st.session_state["global_map_data"] = None
        st.session_state["_map_ver"] = _MAP_DATA_VERSION

    # Load / fetch data on demand
    if st.session_state.get("global_map_data") is None:
        col_btn, col_note = st.columns([1, 3])
        with col_btn:
            load = st.button("🌍 Load global climate data", type="primary", key="load_map")
        with col_note:
            st.markdown(
                '<div style="font-size:.71rem;color:#94a3b8;padding-top:10px">'
                'Fetches ~194-country climate dataset in parallel (~30 s first run, cached 7 days).</div>',
                unsafe_allow_html=True,
            )
        if load:
            with st.spinner("Fetching climate data for ~194 country centroids … (~30 s)"):
                st.session_state["global_map_data"] = fetch_global_map_climate(_MAP_DATA_VERSION)
            st.rerun()
        return

    # Reload button (shown after data is loaded)
    if st.button("↺ Reload data", key="reload_map"):
        fetch_global_map_climate.clear()
        st.session_state["global_map_data"] = None
        st.rerun()

    global_data = st.session_state["global_map_data"]
    crop_info   = CROPS[map_crop]

    iso3_list, name_list, score_list, label_list, temp_list, precip_list = [], [], [], [], [], []
    for iso3, item in global_data.items():
        clim = item["climate"].get(year_key)
        if not clim:
            continue
        score = score_crop(crop_info, clim)
        label, _ = classify(score)
        iso3_list.append(iso3)
        name_list.append(item["point"]["name"])
        score_list.append(score)
        label_list.append(label)
        temp_list.append(clim["mean_temp"])
        precip_list.append(int(clim["annual_precip"]))

    if not iso3_list:
        st.warning("No climate data available. Click 'Load global climate data'.")
        return

    hover_text = [
        f"<b>{n}</b><br>{lbl}: {s}/100<br>🌡️ {t}°C · 🌧️ {p} mm/yr"
        for n, lbl, s, t, p in zip(name_list, label_list, score_list, temp_list, precip_list)
    ]

    # Continuous red→amber→green scale anchored at suitability thresholds
    colorscale = [
        [0.00, "#7f1d1d"],   # 0   — completely unsuited
        [0.15, "#dc2626"],   # 15
        [0.35, "#f97316"],   # 35
        [0.45, "#fbbf24"],   # 45  — marginal threshold
        [0.55, "#a3e635"],   # 55
        [0.70, "#22c55e"],   # 70  — well-suited threshold
        [0.85, "#15803d"],   # 85
        [1.00, "#052e16"],   # 100 — ideal
    ]

    fig = go.Figure(go.Choropleth(
        locations=iso3_list,
        locationmode="ISO-3",
        z=score_list,
        text=hover_text,
        hovertemplate="%{text}<extra></extra>",
        colorscale=colorscale,
        zmin=0,
        zmax=100,
        marker=dict(
            line=dict(color="rgba(255,255,255,0.45)", width=0.5),
            opacity=0.92,
        ),
        colorbar=dict(
            title=dict(text="Score", font=dict(size=11, color="#374151")),
            tickvals=[0, 45, 70, 100],
            ticktext=["0 — No fit", "45 — Marginal", "70 — Suited", "100 — Ideal"],
            len=0.7,
            thickness=14,
            x=1.01,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0.07)",
            borderwidth=1,
            tickfont=dict(size=10, color="#374151"),
        ),
    ))

    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="rgba(150,170,190,0.6)",
            coastlinewidth=0.5,
            showland=True,
            landcolor="rgba(236,239,236,1)",
            showocean=True,
            oceancolor="rgba(210,228,242,0.85)",
            showlakes=True,
            lakecolor="rgba(210,228,242,0.85)",
            showrivers=False,
            showcountries=True,
            countrycolor="rgba(180,195,210,0.4)",
            countrywidth=0.3,
            projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=70, t=0, b=0),
        height=530,
        font=dict(family="Inter, sans-serif", size=11, color="#374151"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary stats row
    total = len(score_list)
    well  = sum(1 for s in score_list if s >= 70)
    marg  = sum(1 for s in score_list if 45 <= s < 70)
    bad   = sum(1 for s in score_list if s < 45)
    avg   = round(sum(score_list) / total)

    st.markdown(
        f'<div class="map-stat-grid">'
        + "".join(
            f'<div class="map-stat" style="background:{bg}">'
            f'<div class="map-stat-val" style="color:{tc}">{val}</div>'
            f'<div class="map-stat-lbl" style="color:{tc}">{lbl}</div>'
            f'<div class="map-stat-sub" style="color:{tc}">{sub}</div>'
            f'</div>'
            for val, lbl, sub, bg, tc in [
                (well, "Well suited",  f"{well * 100 // total}% of countries", "rgba(22,163,74,.09)",  "#16a34a"),
                (marg, "Marginal",     f"{marg * 100 // total}% of countries", "rgba(217,119,6,.09)",  "#d97706"),
                (bad,  "Not suited",   f"{bad  * 100 // total}% of countries", "rgba(220,38,38,.09)",  "#dc2626"),
                (avg,  "Avg score",    "out of 100",                            "rgba(99,102,241,.09)", "#6366f1"),
            ]
        )
        + '</div>',
        unsafe_allow_html=True,
    )

    # Top suited countries
    ranked = sorted(zip(name_list, score_list), key=lambda x: x[1], reverse=True)
    top = [(n, s) for n, s in ranked if s >= 45][:12]
    if top:
        st.markdown('<div class="map-top-label">Top suited countries</div>', unsafe_allow_html=True)
        chips = "".join(
            f'<div class="map-chip"><span class="map-chip-score">{s}</span> {n}</div>'
            for n, s in top
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
        '<div class="ca-sub">Climate-matched suitability scores for 25 crops — now, 2030, and 2040</div>'
        '<div class="ca-badges">'
        '<div class="ca-badge">🌾 25 crops</div>'
        '<div class="ca-badge">📅 2040 projections</div>'
        '<div class="ca-badge">🤖 AI strategy</div>'
        '<div class="ca-badge">🗺️ Global map</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    defaults = {"loc": None, "climate": None, "scores": [], "category": "All", "advice_data": None, "global_map_data": None, "_map_ver": 0}
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
        st.markdown('<hr class="ca-sep" style="margin-bottom:8px">', unsafe_allow_html=True)

        location_input = st.text_input(
            "Location",
            placeholder="e.g. Nairobi, Punjab, Mato Grosso…",
            label_visibility="collapsed",
            key="location_input",
        )

        search_clicked = st.button("🔍 Analyse climate", use_container_width=True, type="primary")

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
            ask_ai = st.button("🤖 Get illustrated advice", use_container_width=True)
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
