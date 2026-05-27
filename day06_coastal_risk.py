import io
import math
import base64
import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
import numpy as np
from PIL import Image
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Coastal Risk & Sea Level · Day 06",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

HEADERS       = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
WB_BASE       = "https://api.worldbank.org/v2/country/all/indicator"
NOAA_API      = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

# ── IPCC AR6 SLR projections (Table 9.9, median, m above 1995-2014 baseline) ──
# Source: IPCC AR6 WG1 Ch.9, Fox-Kemper et al. 2021
IPCC_SLR = {
    ("SSP1-1.9", 2030): 0.09, ("SSP1-1.9", 2040): 0.14, ("SSP1-1.9", 2050): 0.19,
    ("SSP1-1.9", 2060): 0.24, ("SSP1-1.9", 2070): 0.28, ("SSP1-1.9", 2080): 0.32,
    ("SSP1-1.9", 2090): 0.35, ("SSP1-1.9", 2100): 0.38,

    ("SSP2-4.5", 2030): 0.10, ("SSP2-4.5", 2040): 0.16, ("SSP2-4.5", 2050): 0.23,
    ("SSP2-4.5", 2060): 0.30, ("SSP2-4.5", 2070): 0.38, ("SSP2-4.5", 2080): 0.46,
    ("SSP2-4.5", 2090): 0.52, ("SSP2-4.5", 2100): 0.56,

    ("SSP3-7.0", 2030): 0.10, ("SSP3-7.0", 2040): 0.17, ("SSP3-7.0", 2050): 0.25,
    ("SSP3-7.0", 2060): 0.34, ("SSP3-7.0", 2070): 0.44, ("SSP3-7.0", 2080): 0.55,
    ("SSP3-7.0", 2090): 0.66, ("SSP3-7.0", 2100): 0.77,

    ("SSP5-8.5", 2030): 0.11, ("SSP5-8.5", 2040): 0.19, ("SSP5-8.5", 2050): 0.29,
    ("SSP5-8.5", 2060): 0.40, ("SSP5-8.5", 2070): 0.53, ("SSP5-8.5", 2080): 0.68,
    ("SSP5-8.5", 2090): 0.84, ("SSP5-8.5", 2100): 1.01,
}

SSP_LABELS = {
    "SSP1-1.9": "SSP1-1.9 — Paris-aligned (1.5°C)",
    "SSP2-4.5": "SSP2-4.5 — Intermediate (2.5°C)",
    "SSP3-7.0": "SSP3-7.0 — High emissions (3°C)",
    "SSP5-8.5": "SSP5-8.5 — Fossil fuel (4°C+)",
}
SSP_COLORS = {
    "SSP1-1.9": "#16a34a", "SSP2-4.5": "#eab308",
    "SSP3-7.0": "#f97316", "SSP5-8.5": "#dc2626",
}

# ── Country coastal exposure (57 countries) ────────────────────────────────────
# (pop_1m_k, pop_2m_k, pop_3m_k, slr_mm_yr, coastline_km, total_pop_k)
# Sources: Kulp & Strauss 2019 (Nat.Comms.), Climate Central, IPCC AR6 Ch.9
COASTAL_DATA = {
    "BGD": (17000, 28000, 40000, 5.0,   580, 170000),
    "CHN": (43000, 78000,110000, 3.8, 14500,1400000),
    "IND": ( 7000, 21000, 36000, 3.3,  7517,1380000),
    "VNM": ( 9000, 20000, 31000, 4.5,  3260,  97000),
    "IDN": ( 6000, 14000, 23000, 5.0, 54720, 270000),
    "MDV": (  440,   500,   530, 4.2,   644,    540),
    "USA": ( 4700,  9000, 13000, 3.1, 19924, 330000),
    "NLD": ( 3000,  5000,  7000, 2.0,   451,  17000),
    "EGY": (10000, 15000, 20000, 3.0,  2450, 100000),
    "THA": ( 4500,  8000, 12000, 3.5,  3219,  70000),
    "PHL": ( 6000, 11000, 17000, 4.5, 36289, 110000),
    "MMR": ( 3000,  5000,  8000, 4.0,  1930,  55000),
    "PAK": ( 2000,  3500,  6000, 3.0,  1046, 220000),
    "BRA": ( 4000,  7000, 10000, 3.2,  7491, 215000),
    "JPN": ( 3700,  8000, 15000, 2.8, 29751, 126000),
    "GBR": ( 1000,  2500,  4000, 2.3, 17820,  67000),
    "DEU": (  900,  2000,  3500, 2.1,  2389,  83000),
    "NGA": ( 2500,  5000,  8000, 3.5,   853, 210000),
    "MYS": ( 1500,  3000,  5000, 4.0,  4675,  32000),
    "KHM": ( 1500,  2800,  4500, 4.0,   443,  16000),
    "TUV": (   11,    11,    11, 5.8,    24,     11),
    "KIR": (  115,   118,   119, 3.9,  1143,    120),
    "MHL": (   42,    56,    58, 3.7,   370,     60),
    "FJI": (  180,   320,   500, 4.5,  1129,    900),
    "PNG": (  500,  1000,  2000, 4.8,  5152,   9000),
    "AUS": ( 1200,  2500,  4000, 2.9, 25760,  25000),
    "MEX": ( 1500,  3000,  5500, 3.0,  9330, 128000),
    "MOZ": ( 1200,  2500,  4000, 3.8,  2470,  32000),
    "TZA": (  600,  1200,  2000, 3.5,  1424,  60000),
    "ZAF": (  400,   800,  1500, 2.5,  2798,  60000),
    "AGO": (  600,  1200,  2000, 3.0,  1600,  33000),
    "GHA": (  400,   800,  1400, 2.8,   539,  31000),
    "SEN": (  800,  1500,  2500, 2.8,   531,  17000),
    "IRN": (  600,  1200,  2200, 2.8,  2440,  85000),
    "SAU": (  400,   900,  1600, 2.5,  2640,  35000),
    "ARE": (  500,  1000,  1800, 3.2,  1318,  10000),
    "KWT": (  200,   450,   800, 3.0,   499,   4000),
    "QAT": (  300,   600,  1000, 3.2,   563,   3000),
    "BHR": (  350,   600,   900, 3.5,   161,   1700),
    "LKA": (  500,  1000,  2000, 3.5,  1340,  22000),
    "IRQ": (  800,  1500,  2500, 2.5,    58,  40000),
    "CAN": (  500,  1200,  2500, 1.8,202080,  38000),
    "RUS": (  600,  1500,  3000, 1.5, 37653, 144000),
    "FRA": (  500,  1200,  2000, 2.5,  5853,  67000),
    "ITA": (  800,  2000,  3500, 2.3,  7600,  60000),
    "ESP": (  400,   900,  1600, 2.0,  4964,  47000),
    "DNK": (  400,   900,  1500, 1.9,  7314,   6000),
    "NOR": (  100,   300,   600, 0.8, 25148,   5000),
    "POL": (  200,   500,   900, 2.8,   440,  38000),
    "TUR": (  600,  1400,  2500, 2.2,  7200,  84000),
    "GRC": (  300,   700,  1200, 2.0, 13676,  11000),
    "PRT": (  200,   500,   900, 1.8,  1794,  10000),
    "MRT": (  200,   400,   700, 2.5,   754,   4000),
    "SOM": (  500,  1000,  1800, 3.0,  3025,  15000),
    "SGP": (  100,   250,   450, 4.5,   193,   6000),
    "GTM": (  300,   600,  1000, 3.2,   400,  17000),
    "HND": (  400,   800,  1500, 3.5,   820,   9000),
}

# ── Flood viewer cities ────────────────────────────────────────────────────────
# lat, lon, NOAA station id (None = use OpenTopoData), zoom, radius_km, subsidence_mm_yr
FLOOD_CITIES = {
    # South & SE Asia
    "Dhaka, Bangladesh":          { "lat": 23.73, "lon":  90.39, "noaa": None,      "zoom": 9,  "radius": 35, "sub": 5.0,  "note": "17M people at risk in the Ganges-Brahmaputra delta" },
    "Khulna, Bangladesh":         { "lat": 22.82, "lon":  89.55, "noaa": None,      "zoom": 10, "radius": 25, "sub": 6.0,  "note": "Gateway to the Sundarban mangrove coast" },
    "Mumbai, India":              { "lat": 18.94, "lon":  72.84, "noaa": None,      "zoom": 10, "radius": 20, "sub": 3.0,  "note": "Financial capital; $1T+ in coastal real estate at risk" },
    "Kolkata, India":             { "lat": 22.57, "lon":  88.36, "noaa": None,      "zoom": 10, "radius": 25, "sub": 3.0,  "note": "Hugli river delta; major port city" },
    "Colombo, Sri Lanka":         { "lat":  6.93, "lon":  79.85, "noaa": None,      "zoom": 11, "radius": 15, "sub": 2.0,  "note": "Low-lying capital with 400km of coastline" },
    "Dhaka — coastal plain":      { "lat": 22.30, "lon":  90.80, "noaa": None,      "zoom":  9, "radius": 40, "sub": 5.0,  "note": "Southern Bangladesh coastal lowlands" },
    # SE Asia
    "Jakarta, Indonesia":         { "lat": -6.21, "lon": 106.85, "noaa": None,      "zoom": 10, "radius": 25, "sub": 80.0, "note": "Sinking 25cm/yr — effective SLR already 30cm/yr" },
    "Bangkok, Thailand":          { "lat": 13.75, "lon": 100.50, "noaa": None,      "zoom": 10, "radius": 25, "sub": 50.0, "note": "Sinking 50mm/yr from groundwater extraction" },
    "Ho Chi Minh City, Vietnam":  { "lat": 10.80, "lon": 106.68, "noaa": None,      "zoom": 10, "radius": 25, "sub": 50.0, "note": "Mekong Delta; 70% of the city below 1.5m" },
    "Mekong Delta, Vietnam":      { "lat":  9.80, "lon": 105.50, "noaa": None,      "zoom":  9, "radius": 40, "sub": 30.0, "note": "Rice bowl of SE Asia; 20M people mostly below 2m" },
    "Manila, Philippines":        { "lat": 14.60, "lon": 120.98, "noaa": None,      "zoom": 10, "radius": 20, "sub": 8.0,  "note": "Manila Bay exposed to storm surge + SLR" },
    "Singapore":                  { "lat":  1.29, "lon": 103.85, "noaa": None,      "zoom": 11, "radius": 15, "sub": 1.0,  "note": "Average elevation 15m, but Changi and reclaimed land at 1-3m" },
    # East Asia
    "Shanghai, China":            { "lat": 31.23, "lon": 121.47, "noaa": None,      "zoom": 10, "radius": 30, "sub": 8.0,  "note": "Yangtze River delta; major subsidence from groundwater" },
    "Guangzhou, China":           { "lat": 23.13, "lon": 113.26, "noaa": None,      "zoom": 10, "radius": 25, "sub": 5.0,  "note": "Pearl River delta; 40M in the broader metro at risk" },
    "Osaka, Japan":               { "lat": 34.69, "lon": 135.50, "noaa": None,      "zoom": 11, "radius": 20, "sub": 3.0,  "note": "Historic subsidence of 3m in 20th century; partially recovered" },
    "Tokyo Bay, Japan":           { "lat": 35.64, "lon": 139.78, "noaa": None,      "zoom": 11, "radius": 20, "sub": 2.0,  "note": "Reclaimed bay-fill land; tidal barriers protect the core" },
    # Oceania / Pacific
    "Funafuti, Tuvalu":           { "lat": -8.52, "lon": 179.19, "noaa": None,      "zoom": 13, "radius":  5, "sub": 0.5,  "note": "Average 2m elevation — existential risk even at 0.5m SLR" },
    "Tarawa, Kiribati":           { "lat":  1.33, "lon": 173.02, "noaa": None,      "zoom": 12, "radius":  8, "sub": 0.5,  "note": "Atoll nation; 1m SLR puts most land underwater" },
    "Male, Maldives":             { "lat":  4.18, "lon":  73.51, "noaa": None,      "zoom": 13, "radius":  5, "sub": 0.3,  "note": "80% of all Maldivian land within 1m of sea level" },
    "Sydney, Australia":          { "lat": -33.87, "lon": 151.21, "noaa": None,     "zoom": 11, "radius": 20, "sub": 0.5,  "note": "Manly Beach and Parramatta River lowlands at risk" },
    # Middle East / Africa
    "Alexandria, Egypt":          { "lat": 31.20, "lon":  29.92, "noaa": None,      "zoom": 11, "radius": 25, "sub": 2.5,  "note": "Nile Delta city; northern coastal strip largely below 1m" },
    "Nile Delta, Egypt":          { "lat": 31.00, "lon":  31.00, "noaa": None,      "zoom":  9, "radius": 40, "sub": 2.5,  "note": "23% of Egypt's population; breadbasket at risk" },
    "Lagos, Nigeria":             { "lat":  6.52, "lon":   3.38, "noaa": None,      "zoom": 11, "radius": 20, "sub": 5.0,  "note": "25M+ metro on a low-lying lagoon coast" },
    "Dakar, Senegal":             { "lat": 14.76, "lon": -17.37, "noaa": None,      "zoom": 11, "radius": 15, "sub": 1.5,  "note": "Cape Verde peninsula; low-lying coastal suburbs at risk" },
    # Europe
    "Amsterdam, Netherlands":     { "lat": 52.37, "lon":   4.90, "noaa": None,      "zoom": 11, "radius": 20, "sub": 0.8,  "note": "26% of Netherlands below sea level; dykes hold 4m of water back" },
    "Venice, Italy":              { "lat": 45.44, "lon":  12.34, "noaa": None,      "zoom": 12, "radius": 12, "sub": 1.8,  "note": "Sinking 2mm/yr; already experiencing >100 flooding days/yr" },
    "Rotterdam, Netherlands":     { "lat": 51.92, "lon":   4.48, "noaa": None,      "zoom": 11, "radius": 20, "sub": 1.2,  "note": "World's largest port; 90% of city below sea level" },
    "Hamburg, Germany":           { "lat": 53.55, "lon":   9.99, "noaa": None,      "zoom": 11, "radius": 20, "sub": 1.0,  "note": "Elbe River estuary; storm surges already top 6m above MSL" },
    # Americas
    "Miami, USA":                 { "lat": 25.77, "lon": -80.20, "noaa": "8723214", "zoom": 11, "radius": 20, "sub": 1.0,  "note": "Miami Beach at 15cm avg elevation — $1T+ real estate at risk" },
    "New York, USA":              { "lat": 40.70, "lon": -74.01, "noaa": "8518750", "zoom": 11, "radius": 25, "sub": 1.5,  "note": "Lower Manhattan and Brooklyn waterfront exposed" },
    "New Orleans, USA":           { "lat": 29.95, "lon": -90.07, "noaa": "8761927", "zoom": 11, "radius": 20, "sub": 9.0,  "note": "Already 2m below sea level in parts; held by levees" },
    "Houston / Galveston, USA":   { "lat": 29.31, "lon": -94.79, "noaa": "8771450", "zoom": 11, "radius": 25, "sub": 6.0,  "note": "6mm/yr subsidence; Harvey showed vulnerability to surge" },
    "Norfolk, USA":               { "lat": 36.84, "lon": -76.30, "noaa": "8638610", "zoom": 11, "radius": 15, "sub": 4.5,  "note": "Fastest sea level rise on US East Coast; naval base at risk" },
    "Jacksonville, USA":          { "lat": 30.33, "lon": -81.66, "noaa": "8720218", "zoom": 11, "radius": 20, "sub": 2.0,  "note": "St. Johns River estuary; widespread low-lying floodplain" },
    "Buenos Aires, Argentina":    { "lat": -34.62, "lon": -58.38, "noaa": None,     "zoom": 11, "radius": 20, "sub": 1.5,  "note": "Río de la Plata estuary; low coastal districts at risk" },
}

# ── Country coastal exposure data ──────────────────────────────────────────────
RISK_BANDS = [
    (50, "EXISTENTIAL", "#7f1d1d", "rgba(127,29,29,0.10)"),
    (20, "CRITICAL",    "#1d4ed8", "rgba(29,78,216,0.09)"),
    (10, "SEVERE",      "#0891b2", "rgba(8,145,178,0.09)"),
    (3,  "HIGH",        "#0e7490", "rgba(14,116,144,0.09)"),
    (1,  "MODERATE",    "#0284c7", "rgba(2,132,199,0.09)"),
    (0,  "LOW",         "#38bdf8", "rgba(56,189,248,0.09)"),
]

CSCALE = [
    (0.00, "#e0f2fe"), (0.12, "#bae6fd"), (0.28, "#38bdf8"),
    (0.48, "#0ea5e9"), (0.65, "#0284c7"), (0.82, "#1d4ed8"),
    (1.00, "#1e3a5f"),
]

# ── Tide gauge stations ────────────────────────────────────────────────────────
TIDE_STATIONS = {
    "San Francisco, USA":   {"id": "9414290", "slr": 1.94},
    "New York, USA":        {"id": "8518750", "slr": 3.35},
    "Key West, USA":        {"id": "8724580", "slr": 2.56},
    "Seattle, USA":         {"id": "9447130", "slr": 1.09},
    "Honolulu, Hawaii":     {"id": "1612340", "slr": 1.64},
    "Galveston, USA":       {"id": "8771450", "slr": 6.62},
    "Charleston SC, USA":   {"id": "8665530", "slr": 3.55},
    "Boston, USA":          {"id": "8443970", "slr": 2.87},
    "Los Angeles, USA":     {"id": "9410660", "slr": 1.02},
    "Baltimore, USA":       {"id": "8574680", "slr": 3.78},
    "Miami Beach, USA":     {"id": "8723214", "slr": 2.78},
    "San Diego, USA":       {"id": "9410170", "slr": 2.09},
    "Norfolk, USA":         {"id": "8638610", "slr": 5.14},
    "New Orleans, USA":     {"id": "8761927", "slr": 9.21},
    "Portland ME, USA":     {"id": "8418150", "slr": 1.87},
    "Wake Island":          {"id": "1890000", "slr": 2.17},
    "Midway Island":        {"id": "1619910", "slr": 1.58},
}

# ── CSS ─────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');

:root {
  --bg:       #f0f9ff;
  --glass:    rgba(255,255,255,0.76);
  --text-1:   #0c1a2b;
  --text-2:   #334155;
  --text-3:   #94a3b8;
  --accent:   #0891b2;
  --accent-2: #1d4ed8;
  --sh-sm:    0 2px 8px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.75);
  --sh-md:    0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.72);
  --r: 12px; --r-sm: 8px;
}

body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background:
    radial-gradient(ellipse at 12% 18%, rgba(8,145,178,0.08)  0%, transparent 52%),
    radial-gradient(ellipse at 88% 82%, rgba(29,78,216,0.06)  0%, transparent 52%),
    radial-gradient(ellipse at 52% 48%, rgba(14,165,233,0.04) 0%, transparent 65%),
    linear-gradient(160deg, #f0f9ff 0%, #e0f2fe 40%, #f0f9ff 100%) !important;
  background-attachment: fixed !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--text-2) !important;
}
.main .block-container {
  padding-top: 10px !important; padding-bottom: 16px !important;
  max-width: 100% !important; padding-left: 16px !important; padding-right: 16px !important;
}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none!important; }

[data-testid="stSidebar"] {
  background: rgba(240,249,255,0.88) !important;
  backdrop-filter: blur(28px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(28px) saturate(180%) !important;
  border-right: 1px solid rgba(255,255,255,0.6) !important;
  box-shadow: 4px 0 32px rgba(0,0,0,0.07) !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 22px 18px 28px !important; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color:var(--text-2)!important; }
[data-testid="stSidebar"] h2 { color:var(--text-1)!important; font-size:18px!important; font-weight:600!important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div { background:rgba(255,255,255,0.92)!important; }

.metrics-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0; }
.metric-card {
  background:rgba(255,255,255,0.82); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(255,255,255,0.72); border-radius:var(--r-sm); padding:10px 11px;
  box-shadow:var(--sh-sm); animation:fadeSlideUp 0.3s ease both;
}
.metric-label { font-size:9px; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-3); margin-bottom:3px; }
.metric-value { font-size:18px; font-weight:600; color:var(--text-1); line-height:1.15; }
.metric-unit  { font-size:10px; color:var(--text-3); font-weight:400; margin-left:2px; }

.country-heading { font-size:17px; font-weight:600; color:var(--text-1); letter-spacing:-0.02em; margin-bottom:6px; }
.wave-badge { display:flex; align-items:center; gap:10px; margin:2px 0 10px; }

.story-card {
  font-size:12px; line-height:1.85; color:var(--text-2); margin-bottom:10px;
  background:rgba(255,255,255,0.76); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(255,255,255,0.65); border-radius:var(--r-sm);
  padding:12px 14px; box-shadow:var(--sh-sm); animation:fadeSlideUp 0.35s 0.08s ease both;
}
.dramatic-fact {
  background:linear-gradient(135deg,rgba(8,145,178,0.06) 0%,rgba(255,255,255,0.64) 100%);
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(255,255,255,0.65); border-left:3px solid var(--fact-color,#0891b2);
  border-radius:0 var(--r-sm) var(--r-sm) 0; padding:11px 13px; margin:0 0 10px;
  box-shadow:var(--sh-sm); font-size:11px; line-height:1.75; color:#1e3a5f;
  animation:fadeSlideUp 0.4s 0.05s ease both;
}
.compound-risk {
  border:1px solid rgba(29,78,216,0.28); border-left:3px solid #1d4ed8;
  background:rgba(219,234,254,0.32); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  border-radius:0 var(--r-sm) var(--r-sm) 0; padding:11px 13px; margin:0 0 10px;
  box-shadow:0 2px 8px rgba(29,78,216,0.08);
}
.compound-risk-title { font-size:9px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#1d4ed8; margin-bottom:5px; }
.compound-risk-body  { font-size:11px; line-height:1.75; color:#334155; }

.strip-row { display:flex; gap:10px; margin:4px 0 8px; padding:0 1px; }
.strip-card {
  flex:1; min-width:0; background:rgba(255,255,255,0.76);
  backdrop-filter:blur(24px) saturate(160%); -webkit-backdrop-filter:blur(24px) saturate(160%);
  border:1px solid rgba(255,255,255,0.68); border-radius:var(--r); padding:13px 15px;
  box-shadow:var(--sh-sm); transition:transform 0.22s ease,box-shadow 0.22s ease;
  animation:fadeSlideUp 0.4s ease both; cursor:default;
}
.strip-card:hover { transform:translateY(-3px); box-shadow:var(--sh-md); }
.strip-icon { margin-bottom:6px; font-size:16px; }
.strip-n { font-size:22px; font-weight:300; line-height:1.1; margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.strip-l { font-size:9px; letter-spacing:0.07em; text-transform:uppercase; color:var(--text-3); line-height:1.4; }

.narrative-bar {
  background:rgba(255,255,255,0.70); backdrop-filter:blur(20px) saturate(150%);
  -webkit-backdrop-filter:blur(20px) saturate(150%);
  border:1px solid rgba(255,255,255,0.62); border-radius:var(--r);
  padding:14px 18px; margin:6px 0 8px; box-shadow:var(--sh-sm); animation:slideDown 0.4s 0.1s ease both;
}
.narrative-lede { font-size:14px; font-weight:500; color:var(--text-1); line-height:1.6; margin-bottom:6px; }
.narrative-context { font-size:11px; color:var(--text-2); line-height:1.7; }
.narrative-pill {
  display:inline-flex; align-items:center; gap:5px;
  background:rgba(8,145,178,0.09); border:1px solid rgba(8,145,178,0.22);
  border-radius:99px; padding:2px 9px; font-size:10px; font-weight:600; color:#0891b2;
  vertical-align:middle; margin:0 3px;
}

.ssp-badge {
  display:inline-block; border-radius:6px; padding:3px 10px;
  font-size:10px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase;
}
.flood-info {
  background:linear-gradient(135deg,rgba(8,145,178,0.08) 0%,rgba(255,255,255,0.70) 100%);
  border:1px solid rgba(8,145,178,0.22); border-radius:var(--r);
  padding:14px 18px; margin:8px 0; box-shadow:var(--sh-sm);
  font-size:12px; line-height:1.75; color:var(--text-2);
}
.flood-info strong { color:var(--text-1); }

.subsidence-warning {
  border:1px solid rgba(234,179,8,0.35); border-left:3px solid #eab308;
  background:rgba(254,252,232,0.5); border-radius:0 var(--r-sm) var(--r-sm) 0;
  padding:10px 13px; margin:6px 0; font-size:11px; line-height:1.7; color:#78716c;
}

.intro-card {
  background:rgba(255,255,255,0.82); backdrop-filter:blur(24px) saturate(160%);
  -webkit-backdrop-filter:blur(24px) saturate(160%);
  border:1px solid rgba(255,255,255,0.72); border-top:2px solid rgba(8,145,178,0.42);
  border-radius:var(--r); padding:18px 22px; margin:4px 0 10px;
  animation:slideDown 0.4s ease both; box-shadow:var(--sh-md);
}
.intro-heading { font-size:15px; font-weight:600; color:var(--text-1); margin:0 0 12px; }
.intro-pillars { display:flex; gap:12px; flex-wrap:wrap; }
.intro-pillar {
  flex:1; min-width:140px; background:rgba(8,145,178,0.04);
  border:1px solid rgba(8,145,178,0.12); border-radius:var(--r-sm); padding:10px 12px;
}
.intro-pillar-icon  { font-size:18px; margin-bottom:5px; }
.intro-pillar-title { font-size:11px; font-weight:600; color:var(--text-1); margin-bottom:4px; }
.intro-pillar-body  { font-size:10px; line-height:1.65; color:var(--text-2); }

.method-note {
  font-size:10px; color:var(--text-3); line-height:1.65;
  background:rgba(8,145,178,0.04); border:1px solid rgba(8,145,178,0.10);
  border-radius:var(--r-sm); padding:9px 13px; margin-top:12px;
}

.sep { border:none; border-top:1px solid rgba(0,0,0,0.07); margin:13px 0; }
.day-label   { font-size:9px; letter-spacing:0.14em; text-transform:uppercase; color:var(--text-3); }
.data-footer { font-size:10px; color:var(--text-3); letter-spacing:0.04em; line-height:2.0; }
.no-data-note { font-size:10px; color:var(--text-3); padding:2px 4px 6px; }

button[data-baseweb="tab"] {
  color:var(--text-3)!important; font-size:11px!important;
  letter-spacing:0.08em!important; text-transform:uppercase!important;
  background:transparent!important;
}
button[data-baseweb="tab"][aria-selected="true"] { color:var(--text-1)!important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background:rgba(0,0,0,0.08)!important; }
[data-testid="stTabsContent"] { background:transparent!important; padding-top:10px!important; }

div[data-baseweb="select"] > div { background:rgba(255,255,255,0.88)!important; border-color:rgba(0,0,0,0.09)!important; }

@keyframes fadeSlideUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes slideDown   { from{opacity:0;transform:translateY(-18px)} to{opacity:1;transform:translateY(0)} }
@keyframes wavePulse   { 0%,100%{transform:translateX(0)} 50%{transform:translateX(4px)} }

@media (max-width:768px) {
  .main .block-container { padding-left:10px!important; padding-right:10px!important; }
  .strip-row { display:grid!important; grid-template-columns:1fr 1fr!important; gap:8px!important; }
  .intro-pillars { flex-direction:column!important; gap:8px!important; }
}
</style>
"""


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=86_400 * 14, persist="disk", show_spinner=False)
def load_country_names() -> dict[str, str]:
    try:
        r = requests.get(
            "https://api.worldbank.org/v2/country?format=json&per_page=300",
            headers=HEADERS, timeout=15,
        )
        return {c["id"]: c["name"] for c in r.json()[1]
                if len(c.get("id", "")) == 3 and c["id"].isalpha()}
    except Exception:
        return {}


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_wb_indicator(code: str) -> dict[str, float]:
    url = f"{WB_BASE}/{code}?format=json&mrv=5&per_page=1000"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        payload = r.json()
    except Exception:
        return {}
    if len(payload) < 2 or not payload[1]:
        return {}
    latest: dict[str, tuple[int, float]] = {}
    for item in payload[1]:
        iso = item.get("countryiso3code", "")
        val = item.get("value")
        yr  = str(item.get("date", ""))
        if not (iso and len(iso) == 3 and iso.isalpha() and val is not None):
            continue
        yr_int = int(yr) if yr.isdigit() else 0
        if iso not in latest or yr_int > latest[iso][0]:
            latest[iso] = (yr_int, float(val))
    return {iso: v for iso, (_, v) in latest.items()}


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_tide_gauge(station_id: str) -> dict:
    try:
        r = requests.get(NOAA_API, params={
            "station": station_id, "product": "monthly_mean",
            "datum": "MSL", "time_zone": "GMT",
            "begin_date": "20000101", "end_date": datetime.date.today().strftime("%Y%m%d"),
            "units": "metric", "format": "json",
            "application": "ResilienceStack",
        }, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    records = data.get("data", [])
    if not records:
        return {}

    year_vals: dict[int, list[float]] = {}
    for rec in records:
        try:
            yr  = int(rec["t"][:4])
            msl = float(rec["MSL"])
            year_vals.setdefault(yr, []).append(msl)
        except (KeyError, ValueError):
            continue

    years     = sorted(year_vals)
    if not years:
        return {}
    ann_means = [sum(year_vals[y]) / len(year_vals[y]) for y in years]
    baseline  = ann_means[0]
    ann_rel   = [(v - baseline) * 1000 for v in ann_means]

    n   = len(years)
    x_m = sum(years) / n
    y_m = sum(ann_rel) / n
    den = sum((y - x_m) ** 2 for y in years) or 1
    slope = sum((y - x_m) * (ann_rel[i] - y_m) for i, y in enumerate(years)) / den

    # Acceleration: compare first-half slope vs second-half slope
    mid = n // 2
    def half_slope(ys, vs):
        xm = sum(ys) / len(ys); ym = sum(vs) / len(vs)
        d = sum((y - xm) ** 2 for y in ys) or 1
        return sum((y - xm) * (v - ym) for y, v in zip(ys, vs)) / d
    early_slope  = half_slope(years[:mid], ann_rel[:mid])
    recent_slope = half_slope(years[mid:], ann_rel[mid:])

    return {
        "years":          years,
        "values_mm":      ann_rel,
        "slope_mm_yr":    round(slope, 2),
        "total_rise_mm":  round(ann_rel[-1] - ann_rel[0], 1),
        "recent_slope":   round(recent_slope, 2),
        "early_slope":    round(early_slope, 2),
        "last_year":      max(years),
    }


def _lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Web Mercator lat/lon → tile (x, y) at given zoom."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def _tile_bounds(tx: int, ty: int, zoom: int) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) degrees for a tile."""
    n = 2 ** zoom
    lon_west  = tx / n * 360.0 - 180.0
    lon_east  = (tx + 1) / n * 360.0 - 180.0
    lat_north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    lat_south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
    return lat_south, lon_west, lat_north, lon_east


@st.cache_data(ttl=86_400 * 30, persist="disk", show_spinner=False)
def fetch_terrain_elevation(lat: float, lon: float, zoom: int = 11) -> dict:
    """Download a 5×5 grid of AWS Terrarium tiles and decode pixel-level elevation.

    Returns dict with:
      elevation: 2-D numpy float32 array (rows=lat descending, cols=lon ascending)
      bounds:    [[south, west], [north, east]] for ImageOverlay
      px_res_m:  approx metres per pixel
      tiles:     number of tiles fetched
    """
    cx, cy = _lat_lon_to_tile(lat, lon, zoom)
    half = 2  # fetch 5×5 tile grid centred on (cx, cy)

    tile_size = 256  # Terrarium tiles are 256×256 px
    rows, cols = 5, 5
    full_h = rows * tile_size
    full_w = cols * tile_size
    canvas = np.full((full_h, full_w, 3), 128, dtype=np.uint8)  # neutral fill

    fetched = 0
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = TERRARIUM_URL.format(z=zoom, x=tx, y=ty)
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                arr = np.array(img, dtype=np.uint8)
                row_off = (dy + half) * tile_size
                col_off = (dx + half) * tile_size
                canvas[row_off:row_off + tile_size, col_off:col_off + tile_size] = arr
                fetched += 1
            except Exception:
                pass  # leave neutral fill; still renders plausibly

    # Decode Terrarium RGB → elevation (m): elev = R*256 + G + B/256 − 32768
    R = canvas[:, :, 0].astype(np.float32)
    G = canvas[:, :, 1].astype(np.float32)
    B = canvas[:, :, 2].astype(np.float32)
    elevation = R * 256.0 + G + B / 256.0 - 32768.0

    # Compute geographic bounds of the stitched canvas
    s0, w0, n0, e0 = _tile_bounds(cx - half,     cy + half,     zoom)
    s1, w1, n1, e1 = _tile_bounds(cx + half,     cy - half,     zoom)
    south, west = min(s0, s1), min(w0, w1)
    north, east = max(n0, n1), max(e0, e1)

    # Approx pixel resolution (Web Mercator equatorial metres per pixel)
    px_res_m = 156543.03 * math.cos(math.radians(lat)) / (2 ** zoom)

    return {
        "elevation": elevation,
        "bounds": [[south, west], [north, east]],
        "px_res_m": px_res_m,
        "tiles": fetched,
    }


def make_flood_overlay(terrain: dict, slr_m: float) -> str:
    """Convert elevation array + SLR threshold into a base64 PNG RGBA image.

    Color zones:
      Navy  (#1e3a5f, 85% opacity) : already below sea level (elev ≤ 0)
      Cyan  (#0891b2, 75% opacity) : flooded at this SLR scenario (0 < elev ≤ slr_m)
      Sky   (#7dd3fc, 50% opacity) : near-term risk zone (slr_m < elev ≤ slr_m + 0.5)
      Transparent                  : safe land
    """
    elev = terrain["elevation"]
    h, w = elev.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    below_sea  = elev <= 0
    flooded    = (elev > 0) & (elev <= slr_m)
    near_risk  = (elev > slr_m) & (elev <= slr_m + 0.5)

    # Navy — already below sea
    rgba[below_sea]  = [30,  58,  95,  217]
    # Cyan-blue — flooded at scenario
    rgba[flooded]    = [8,  145, 178,  191]
    # Sky blue — near-term risk
    rgba[near_risk]  = [125, 211, 252,  128]

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ── Helpers ────────────────────────────────────────────────────────────────────
def risk_band(pct: float | None) -> tuple[str, str, str]:
    if pct is None:
        return "N/A", "#94a3b8", "rgba(148,163,184,0.08)"
    for threshold, label, fg, bg in RISK_BANDS:
        if pct >= threshold:
            return label, fg, bg
    return "LOW", "#38bdf8", "rgba(56,189,248,0.09)"


def get_ipcc_slr(ssp: str, year: int) -> float:
    """IPCC AR6 median SLR (m) for given SSP and year. Interpolates between decades."""
    years = sorted({k[1] for k in IPCC_SLR if k[0] == ssp})
    if year <= years[0]:
        return IPCC_SLR[(ssp, years[0])]
    if year >= years[-1]:
        return IPCC_SLR[(ssp, years[-1])]
    for i in range(len(years) - 1):
        y0, y1 = years[i], years[i + 1]
        if y0 <= year <= y1:
            v0 = IPCC_SLR[(ssp, y0)]
            v1 = IPCC_SLR[(ssp, y1)]
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    return 0.0


def effective_slr(ssp: str, year: int, subsidence_mm_yr: float) -> float:
    """Total effective SLR = global mean + local subsidence since 2024."""
    global_slr   = get_ipcc_slr(ssp, year)
    years_ahead  = max(0, year - 2024)
    sub_slr      = (subsidence_mm_yr * years_ahead) / 1000.0
    return round(global_slr + sub_slr, 3)


def slr_to_noaa_ft(slr_m: float) -> int:
    ft = slr_m * 3.28084
    return max(1, min(10, round(ft)))


def _pop_at_slr(pop_1m: int, pop_2m: int, pop_3m: int, slr_m: float) -> int:
    """Population displaced (K) at given effective SLR — mirrors the inline _pop_at logic."""
    if slr_m <= 0:
        return 0
    elif slr_m <= 1.0:
        return int(pop_1m * slr_m)
    elif slr_m <= 2.0:
        return int(pop_1m + (pop_2m - pop_1m) * (slr_m - 1.0))
    else:
        return int(pop_2m + (pop_3m - pop_2m) * min(slr_m - 2.0, 1.0))


@st.cache_data(ttl=86_400 * 90, persist="disk", show_spinner=False)
def load_world_geojson() -> dict:
    """Fetch naturalearth 110m world-countries GeoJSON (folium example dataset).
    'id' field on each feature is the ISO alpha-3 code."""
    url = ("https://raw.githubusercontent.com/python-visualization/folium/"
           "main/examples/data/world-countries.json")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"type": "FeatureCollection", "features": []}


def make_world_flood_map(df: pd.DataFrame, ssp: str, year: int) -> folium.Map:
    """Global coastal risk map: choropleth by displaced-population % + city bubbles.

    Country fill: risk % at effective SLR for the chosen SSP/year (scaled by subsidence).
    City circles: all FLOOD_CITIES, radius ∝ effective SLR, colour = severity tier.
    """
    world_geo  = load_world_geojson()
    slr_global = get_ipcc_slr(ssp, year)

    # Build per-country risk % at this scenario
    risk_rows = []
    for iso, vals in COASTAL_DATA.items():
        p1, p2, p3, sub_mm_yr, _, pop_total = vals
        slr_eff = effective_slr(ssp, year, sub_mm_yr)
        exposed  = _pop_at_slr(p1, p2, p3, slr_eff)
        pct      = round(exposed / pop_total * 100, 3) if pop_total > 0 else 0.0
        risk_rows.append({"iso": iso, "risk_pct": pct})
    risk_df = pd.DataFrame(risk_rows)

    m = folium.Map(
        location=[15, 10], zoom_start=2,
        tiles="CartoDB positron",
        attr="© CartoDB · © OpenStreetMap",
        max_zoom=14,
    )

    if world_geo.get("features"):
        folium.Choropleth(
            geo_data=world_geo,
            data=risk_df,
            columns=["iso", "risk_pct"],
            key_on="feature.id",
            fill_color="YlOrRd",
            fill_opacity=0.72,
            line_opacity=0.25,
            line_color="#ffffff",
            nan_fill_color="rgba(148,163,184,0.10)",
            nan_fill_opacity=0.4,
            legend_name=f"Population displaced (%) — {ssp} {year}",
            threshold_scale=[0, 1, 5, 15, 30, 55],
        ).add_to(m)

    # City bubble markers — size and colour by effective SLR severity
    for city_name, city in FLOOD_CITIES.items():
        sub     = city.get("sub", 0.0)
        slr_eff = effective_slr(ssp, year, sub)
        sub_m   = sub * (year - 2024) / 1000.0

        if slr_eff > 3.0:
            c = "#7f1d1d"
        elif slr_eff > 1.5:
            c = "#dc2626"
        elif slr_eff > 0.8:
            c = "#f97316"
        else:
            c = "#0891b2"

        radius = min(18, max(5, slr_eff * 5 + 3))

        sub_line = (f"  +  subsidence +{sub_m:.2f}m" if sub_m >= 0.05 else "")
        folium.CircleMarker(
            location=[city["lat"], city["lon"]],
            radius=radius,
            color=c, fill=True, fill_color=c,
            fill_opacity=0.78, weight=1.5,
            tooltip=folium.Tooltip(
                f"<div style='font-family:Inter,sans-serif;min-width:190px'>"
                f"<b style='font-size:12px'>{city_name}</b><br>"
                f"<span style='color:#334155;font-size:10px'>"
                f"Global SLR +{slr_global:.2f}m{sub_line}<br>"
                f"<b>Effective SLR: +{slr_eff:.2f}m</b><br>"
                f"{city['note']}"
                f"</span></div>",
                sticky=True,
            ),
        ).add_to(m)

    return m


def _fmt(v, dec: int = 1, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.{dec}f}{unit}"


def _fmt_pop(k: int | None) -> str:
    if k is None:
        return "—"
    if k >= 1_000_000:
        return f"{k / 1_000_000:.1f}B"
    if k >= 1_000:
        return f"{k / 1_000:.1f}M"
    return f"{k:,}K"


# ── SVG helpers ────────────────────────────────────────────────────────────────
def wave_svg(color: str = "#0891b2") -> str:
    return (f'<svg width="48" height="32" viewBox="0 0 60 40" fill="none"'
            f' style="animation:wavePulse 2s ease-in-out infinite">'
            f'<path d="M2 28 C8 20,14 20,20 28 S32 36,38 28 S50 20,56 28"'
            f' stroke="{color}" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.9"/>'
            f'<path d="M2 20 C8 12,14 12,20 20 S32 28,38 20 S50 12,56 20"'
            f' stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.55"/>'
            f'<path d="M2 12 C8 4,14 4,20 12 S32 20,38 12 S50 4,56 12"'
            f' stroke="{color}" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.30"/>'
            f'</svg>')


# ── HTML component builders ────────────────────────────────────────────────────
def _stats_strip(df: pd.DataFrame) -> str:
    critical    = int((df["risk_pct"] >= 20).sum())
    total_1m    = int(df["pop_1m_k"].sum())
    fastest     = df.loc[df["slr_mm_yr"].idxmax()]
    existential = int((df["risk_pct"] >= 50).sum())
    cards = [
        ("🌊", f'<span style="color:#1d4ed8">{critical}</span>', "countries — critical or worse"),
        ("👥", _fmt_pop(total_1m),   "people within 1 m elevation"),
        ("📈", fastest["country_name"], f'{fastest["slr_mm_yr"]:.1f} mm/yr · fastest rising'),
        ("🏝️", f"{existential}", "countries — existential risk"),
    ]
    parts = []
    for i, (icon, val, label) in enumerate(cards):
        parts.append(f'<div class="strip-card" style="animation-delay:{i*0.06:.2f}s">'
                     f'<div class="strip-icon">{icon}</div>'
                     f'<div class="strip-n">{val}</div>'
                     f'<div class="strip-l">{label}</div></div>')
    return f'<div class="strip-row">{"".join(parts)}</div>'


def _narrative_bar(df: pd.DataFrame) -> str:
    critical = int((df["risk_pct"] >= 10).sum())
    total_1m  = int(df["pop_1m_k"].sum())
    return f"""<div class="narrative-bar">
  <div class="narrative-lede">
    <span class="narrative-pill">{_fmt_pop(total_1m)} people</span> live within 1 metre of sea level today —
    and the ocean is rising faster than at any point in 3,000 years.
  </div>
  <div class="narrative-context">
    IPCC AR6 projects <strong>0.3–1.0 m of global mean sea level rise by 2100</strong> under current trajectories,
    with up to 2 m possible if ice sheets destabilise.
    <span class="narrative-pill">{critical} nations</span> face severe or worse exposure,
    concentrated in low-elevation river deltas, small island states, and subsiding megacities where
    land is sinking faster than the sea is rising.
  </div>
</div>"""


def _country_fact(r: pd.Series, water_stress: float | None) -> tuple[str, str]:
    name  = r.get("country_name", "")
    p1    = r.get("pop_1m_k",  0) or 0
    pct   = r.get("risk_pct",  0) or 0
    slr   = r.get("slr_mm_yr", 3) or 3
    coast = r.get("coastline_km", 0) or 0

    if pct >= 50:
        fact  = (f"<strong>{name}</strong> faces an <strong>existential threat</strong>. "
                 f"Over half its population — {_fmt_pop(p1)} people — lives within 1 m of sea level. "
                 f"At +1.5 m the nation as a geographic entity may cease to exist.")
        color = "#7f1d1d"
    elif pct >= 20:
        fact  = (f"<strong>{name}</strong> has <strong>{_fmt_pop(p1)} people within 1 m elevation</strong> "
                 f"({pct:.1f}% of the population). SLR is running at {slr:.1f} mm/yr. "
                 f"Displacement has already begun in coastal communities.")
        color = "#1d4ed8"
    elif pct >= 10:
        fact  = (f"In <strong>{name}</strong>, {_fmt_pop(p1)} people ({pct:.1f}% of the population) "
                 f"occupy land below 1 m elevation across {coast:,.0f} km of coastline. "
                 f"Adaptation costs are already running into billions annually.")
        color = "#0891b2"
    elif pct >= 3:
        fact  = (f"<strong>{name}</strong> has {_fmt_pop(p1)} people within 1 m of sea level — "
                 f"exposure concentrated in coastal cities and river mouths where targeted "
                 f"infrastructure investment is critical.")
        color = "#0e7490"
    else:
        fact  = (f"<strong>{name}</strong> has low coastal population exposure today. "
                 f"SLR at {slr:.1f} mm/yr will still reshape coastal infrastructure, "
                 f"tourism, and flood insurance markets significantly by 2100.")
        color = "#38bdf8"

    return f'<div class="dramatic-fact" style="--fact-color:{color}">{fact}</div>', color


def _country_panel(r: pd.Series, water_stress: float | None) -> str:
    name  = r.get("country_name", r.get("iso", ""))
    p1    = r.get("pop_1m_k", 0) or 0
    p2    = r.get("pop_2m_k", 0) or 0
    slr   = r.get("slr_mm_yr", 3) or 3
    coast = r.get("coastline_km", 0) or 0
    pct   = r.get("risk_pct", 0) or 0
    label, fg, _bg = risk_band(pct)
    fact_html, _ = _country_fact(r, water_stress)

    metrics = f"""<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-label">Pop. within 1 m</div>
    <div class="metric-value" style="color:{fg}">{_fmt_pop(p1)}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Risk tier</div>
    <div class="metric-value" style="color:{fg};font-size:13px;font-weight:700">{label}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">SLR rate</div>
    <div class="metric-value">{_fmt(slr,1)}<span class="metric-unit">mm/yr</span></div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Coastline</div>
    <div class="metric-value">{coast:,.0f}<span class="metric-unit">km</span></div>
  </div>
</div>"""

    # SSP projections mini-card
    proj_parts = []
    for ssp, col in [("SSP1-1.9","#16a34a"),("SSP5-8.5","#dc2626")]:
        v_2050 = get_ipcc_slr(ssp, 2050)
        v_2100 = get_ipcc_slr(ssp, 2100)
        proj_parts.append(
            f'<div style="flex:1;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);'
            f'border-radius:8px;padding:7px 9px;text-align:center">'
            f'<div style="font-size:8px;color:{col};letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px">{ssp}</div>'
            f'<div style="font-size:11px;font-weight:600;color:{col}">'
            f'+{v_2050:.2f}m <span style="opacity:0.6">2050</span></div>'
            f'<div style="font-size:11px;font-weight:600;color:{col}">'
            f'+{v_2100:.2f}m <span style="opacity:0.6">2100</span></div></div>'
        )
    proj_html = (f'<div style="font-size:10px;color:var(--text-3);margin:6px 0 2px;'
                 f'letter-spacing:0.06em;text-transform:uppercase">Global SLR projections (IPCC AR6 median)</div>'
                 f'<div style="display:flex;gap:8px;margin-bottom:8px">{"".join(proj_parts)}</div>')

    compound = ""
    if water_stress and water_stress > 25:
        compound = (f'<div class="compound-risk"><div class="compound-risk-title">⚠ Saltwater intrusion risk</div>'
                    f'<div class="compound-risk-body">Water stress at {water_stress:.0f}% + coastal flooding → '
                    f'saltwater intrusion into freshwater aquifers, degrading irrigation '
                    f'and drinking water simultaneously with displacement.</div></div>')

    return (f'<div class="country-heading">{name}</div>'
            f'<div class="wave-badge">{wave_svg(fg)}'
            f'<div><div style="font-size:10px;color:{fg};font-weight:700;letter-spacing:0.1em;text-transform:uppercase">{label}</div>'
            f'<div style="font-size:10px;color:var(--text-3)">{pct:.1f}% of population within 1 m</div></div></div>'
            f'{metrics}{proj_html}{fact_html}{compound}')


# ── Chart builders ─────────────────────────────────────────────────────────────
def make_risk_map(df: pd.DataFrame, selected_iso: str, ssp: str, year: int) -> go.Figure:
    slr_m = get_ipcc_slr(ssp, year)
    plot_df = df.copy()

    def _pop_at(r):
        p1, p2, p3 = r["pop_1m_k"], r["pop_2m_k"], r["pop_3m_k"]
        if slr_m <= 1.0:
            return p1 * slr_m
        elif slr_m <= 2.0:
            return p1 + (p2 - p1) * (slr_m - 1.0)
        else:
            return p2 + (p3 - p2) * min(slr_m - 2.0, 1.0)

    plot_df["disp"] = plot_df.apply(_pop_at, axis=1).clip(lower=0)
    plot_df["disp_fmt"] = plot_df["disp"].apply(lambda v: _fmt_pop(int(v)))

    zmax = max(1, float(plot_df["disp"].quantile(0.95)))

    fig = px.choropleth(
        plot_df, locations="iso", color="disp",
        hover_name="country_name",
        hover_data={"iso": False, "disp": False, "disp_fmt": True, "slr_mm_yr": ":.1f"},
        color_continuous_scale=CSCALE,
        range_color=(0, zmax),
        labels={"disp_fmt": "At risk", "slr_mm_yr": "SLR (mm/yr)"},
    )
    fig.update_traces(
        marker_line_width=0.4, marker_line_color="rgba(255,255,255,0.4)",
        hovertemplate="<b>%{hovertext}</b><br>At risk: %{customdata[0]}<br>Local SLR: %{customdata[1]:.1f} mm/yr<extra></extra>",
    )
    # Existential countries border
    ext = plot_df[plot_df["risk_pct"] >= 50]
    if not ext.empty:
        fig.add_trace(go.Choropleth(
            locations=ext["iso"], z=[1]*len(ext),
            colorscale=[[0,"rgba(127,29,29,0)"],[1,"rgba(127,29,29,0)"]],
            showscale=False, marker_line_width=1.5, marker_line_color="#7f1d1d", hoverinfo="skip",
        ))
    if selected_iso:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso], z=[1],
            colorscale=[[0,"rgba(0,0,0,0)"],[1,"rgba(0,0,0,0)"]],
            showscale=False, marker_line_width=2.4, marker_line_color="#0891b2", hoverinfo="skip",
        ))
    fig.update_geos(
        showframe=False, showcoastlines=False, showland=True,
        landcolor="rgba(241,245,249,0.9)",
        showocean=True, oceancolor="rgba(186,230,253,0.60)",
        showcountries=False, projection_type="natural earth",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_coloraxes(colorbar=dict(
        title=dict(text="People at risk", font=dict(size=10, color="#334155")),
        thickness=10, len=0.55, x=1.0, y=0.5,
        tickfont=dict(size=9, color="#334155"),
        bgcolor="rgba(255,255,255,0.5)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1,
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=480,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def make_tide_chart(gauge_data: dict, station_name: str) -> go.Figure:
    years        = gauge_data.get("years", [])
    values       = gauge_data.get("values_mm", [])
    slope        = gauge_data.get("slope_mm_yr", 0)
    early_slope  = gauge_data.get("early_slope", 0)
    recent_slope = gauge_data.get("recent_slope", 0)
    if not years:
        return go.Figure()

    n   = len(years)
    x_m = sum(years) / n
    y_m = sum(values) / n
    trend = [y_m + slope * (y - x_m) for y in years]

    window = 5
    smooth = []
    for i in range(n):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        smooth.append(sum(values[lo:hi]) / (hi - lo))

    fig = go.Figure()

    # Shade acceleration zone (second half) when detected
    accel = recent_slope - early_slope
    if accel > 0.5 and n > 4:
        mid_year = years[n // 2]
        fig.add_vrect(
            x0=mid_year - 0.5, x1=years[-1] + 0.5,
            fillcolor="rgba(220,38,38,0.06)", line_width=0,
        )
        fig.add_annotation(
            x=mid_year, y=max(values) * 0.92,
            text="⬆ Accelerating",
            showarrow=False, xanchor="left",
            font=dict(size=8, color="#dc2626"),
        )

    fig.add_trace(go.Bar(
        x=years, y=values, name="Annual mean SL",
        marker_color="rgba(8,145,178,0.35)", marker_line_width=0,
        hovertemplate="%{x}: %{y:.0f} mm above 2000 baseline<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=smooth, mode="lines", name="5-yr rolling avg",
        line=dict(color="#0891b2", width=2.5),
        hovertemplate="%{x}: %{y:.0f} mm (5yr avg)<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=trend, mode="lines",
        name=f"Trend ({slope:+.1f} mm/yr)",
        line=dict(color="#1d4ed8", width=1.8, dash="dot"),
        hoverinfo="skip",
    ))
    # Label trend slope at right end
    if trend:
        fig.add_annotation(
            x=years[-1], y=trend[-1],
            text=f"  {slope:+.1f} mm/yr",
            showarrow=False, xanchor="left",
            font=dict(size=8, color="#1d4ed8"),
        )

    fig.update_layout(
        height=300, margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.5)",
        barmode="overlay",
        legend=dict(orientation="h", x=0, y=-0.22, font=dict(size=9, color="#334155"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#334155")),
        yaxis=dict(
            title=dict(text="mm above 2000 baseline", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=True,
            zerolinecolor="rgba(8,145,178,0.3)", tickfont=dict(size=9, color="#334155"),
        ),
        title=dict(text=f"Sea level rise — {station_name}", font=dict(size=12, color="#0c1a2b"), x=0.02),
    )
    return fig


def make_city_risk_chart(df: pd.DataFrame, ssp: str, year: int) -> go.Figure:
    slr_m = get_ipcc_slr(ssp, year)
    plot_df = df.copy()

    def _pop(r):
        p1, p2, p3 = r["pop_1m_k"], r["pop_2m_k"], r["pop_3m_k"]
        if slr_m <= 1.0:
            return p1 * slr_m
        elif slr_m <= 2.0:
            return p1 + (p2 - p1) * (slr_m - 1.0)
        else:
            return p2 + (p3 - p2) * min(slr_m - 2.0, 1.0)

    plot_df["scen_pop"] = plot_df.apply(_pop, axis=1).clip(lower=0)
    top    = plot_df.nlargest(25, "scen_pop").reset_index(drop=True)
    colors = [risk_band(r["risk_pct"])[1] for _, r in top.iterrows()]

    fig = go.Figure(go.Bar(
        x=top["scen_pop"] / 1000,
        y=top["country_name"],
        orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[_fmt_pop(int(v)) for v in top["scen_pop"]],
        textposition="outside", textfont=dict(size=8),
        hovertemplate="<b>%{y}</b><br>At risk: %{text}<extra></extra>",
    ))
    fig.update_layout(
        height=560, margin=dict(l=8, r=50, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.5)",
        xaxis=dict(
            title=dict(text="Population at risk (millions)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#334155")),
        title=dict(text=f"Top 25 countries · {ssp} · {year}", font=dict(size=12, color="#0c1a2b"), x=0.01),
    )
    return fig


def make_compound_scatter(df: pd.DataFrame, water_stress: dict) -> go.Figure:
    rows = []
    for _, r in df.iterrows():
        ws = water_stress.get(r["iso"])
        if ws is not None and r["pop_1m_k"] > 0:
            rows.append({
                "iso":      r["iso"],
                "name":     r["country_name"],
                "pop":      r["pop_1m_k"],
                "water":    ws,
                "slr":      r["slr_mm_yr"],
                "risk_pct": r["risk_pct"],
            })
    if not rows:
        return go.Figure()

    sdf    = pd.DataFrame(rows)
    colors = [risk_band(v)[1] for v in sdf["risk_pct"]]

    fig = go.Figure(go.Scatter(
        x=sdf["pop"] / 1000,
        y=sdf["water"],
        mode="markers+text",
        text=sdf["iso"],
        textposition="top center",
        textfont=dict(size=7, color="#334155"),
        marker=dict(
            size=sdf["slr"].apply(lambda s: max(6, min(22, s * 3.5))),
            color=colors, opacity=0.82,
            line=dict(width=1, color="rgba(255,255,255,0.7)"),
        ),
        customdata=sdf[["name", "pop", "water", "slr"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Pop. at risk (1m): %{customdata[1]:,.0f}K<br>"
            "Water stress: %{customdata[2]:.0f}%<br>"
            "SLR rate: %{customdata[3]:.1f} mm/yr<extra></extra>"
        ),
    ))
    x_max_m = sdf["pop"].max() / 1000
    fig.add_shape(type="rect", x0=5, x1=x_max_m * 1.1,
                  y0=40, y1=110, fillcolor="rgba(29,78,216,0.06)", line_width=0)
    fig.add_annotation(x=max(6, x_max_m * 0.55), y=105,
                       text="⚠ COMPOUND COASTAL + WATER CRISIS",
                       font=dict(size=8, color="#1d4ed8"), showarrow=False)
    fig.update_layout(
        height=420, margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.52)",
        xaxis=dict(
            title=dict(text="Population within 1 m of sea level (millions)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        yaxis=dict(
            title=dict(text="Water withdrawal stress (%)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        title=dict(
            text="Compound coastal + water stress  (bubble size = SLR rate mm/yr)",
            font=dict(size=11, color="#0c1a2b"), x=0.01,
        ),
    )
    return fig


# ── Flood viewer map ───────────────────────────────────────────────────────────
_FLOOD_LEGEND_HTML = """
<div style="position:fixed;bottom:20px;left:20px;z-index:1000;
     background:rgba(255,255,255,0.94);padding:12px 16px;
     border-radius:8px;border:1px solid rgba(0,0,0,0.10);
     box-shadow:0 2px 12px rgba(0,0,0,0.14);
     font-family:Inter,sans-serif;font-size:11px;color:#0c1a2b;min-width:180px">
  <div style="font-weight:600;margin-bottom:9px;letter-spacing:-0.01em">Flood Risk Zones</div>
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:6px">
    <span style="width:14px;height:14px;background:#1e3a5f;display:inline-block;border-radius:2px;flex-shrink:0"></span>
    <span style="color:#334155">Currently below sea level</span>
  </div>
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:6px">
    <span style="width:14px;height:14px;background:#0891b2;display:inline-block;border-radius:2px;flex-shrink:0"></span>
    <span style="color:#334155">Flooded at this scenario</span>
  </div>
  <div style="display:flex;align-items:center;gap:9px">
    <span style="width:14px;height:14px;background:#7dd3fc;display:inline-block;border-radius:2px;flex-shrink:0;opacity:0.75"></span>
    <span style="color:#334155">Near-term risk (+0.5 m)</span>
  </div>
</div>"""


def make_flood_map(city_name: str, slr_total: float,
                   terrain: dict | None, noaa_station: str | None,
                   noaa_ft: int) -> folium.Map:
    city = FLOOD_CITIES[city_name]
    m = folium.Map(
        location=[city["lat"], city["lon"]],
        zoom_start=city["zoom"],
        tiles="CartoDB positron",
        attr="© CartoDB · © OpenStreetMap",
    )

    if noaa_station and slr_total > 0:
        # NOAA pre-computed inundation tiles — accurate for US coastal cities
        wms_url = (f"https://coast.noaa.gov/arcgis/services/dc_slr/"
                   f"slr_{noaa_ft}ft/MapServer/WmsServer")
        try:
            folium.WmsTileLayer(
                url=wms_url, name=f"NOAA {noaa_ft}ft SLR",
                fmt="image/png", transparent=True,
                layers="0", overlay=True, control=False, opacity=0.65,
            ).add_to(m)
        except Exception:
            pass

    elif terrain is not None and slr_total > 0:
        # Pixel-level flood overlay from AWS Terrarium elevation tiles
        png_data_uri = make_flood_overlay(terrain, slr_total)
        folium.raster_layers.ImageOverlay(
            image=png_data_uri,
            bounds=terrain["bounds"],
            opacity=1.0,
            name="Flood zones",
            interactive=False,
            cross_origin=False,
            zindex=10,
        ).add_to(m)
        m.get_root().html.add_child(folium.Element(_FLOOD_LEGEND_HTML))

    # City centre marker
    folium.CircleMarker(
        location=[city["lat"], city["lon"]],
        radius=7, color="#0891b2", fill=True, fill_color="#0891b2",
        fill_opacity=0.9, weight=2,
        tooltip=folium.Tooltip(
            f"<b style='font-family:Inter,sans-serif'>{city_name}</b><br>"
            f"<span style='font-size:10px;color:#334155'>{city['note']}</span>",
            sticky=True,
        ),
    ).add_to(m)
    return m


# ── Main app ───────────────────────────────────────────────────────────────────
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    with st.spinner("Loading coastal data…"):
        country_names    = load_country_names()
        water_stress_raw = load_wb_indicator("ER.H2O.FWTL.ZS")

    # Build main dataframe
    rows = []
    for iso, vals in COASTAL_DATA.items():
        p1, p2, p3, slr, coast, pop_total = vals
        risk_pct = round((p1 / pop_total * 100) if pop_total > 0 else 0, 2)
        rows.append({
            "iso": iso,
            "country_name": country_names.get(iso, iso),
            "pop_1m_k": p1, "pop_2m_k": p2, "pop_3m_k": p3,
            "slr_mm_yr": slr, "coastline_km": coast, "risk_pct": risk_pct,
        })
    df = pd.DataFrame(rows)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="day-label">Day 06 · The Resilience Stack</div>', unsafe_allow_html=True)
        st.markdown("## Coastal Risk & Sea Level")
        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        sorted_df    = df.sort_values("country_name")
        iso_opts     = sorted_df["iso"].tolist()
        name_opts    = sorted_df["country_name"].tolist()
        default_idx  = iso_opts.index("BGD") if "BGD" in iso_opts else 0

        selected_name = st.selectbox("Select country", name_opts, index=default_idx)
        selected_iso  = iso_opts[name_opts.index(selected_name)]

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        sel_row = df[df["iso"] == selected_iso].iloc[0]
        ws_val  = water_stress_raw.get(selected_iso)
        st.markdown(_country_panel(sel_row, ws_val), unsafe_allow_html=True)

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("""<div class="data-footer">
Sources: Kulp & Strauss 2019 · Nat. Comms.<br>
IPCC AR6 Ch. 9 · Fox-Kemper et al. 2021<br>
NOAA CO-OPS tide gauges<br>
NOAA Digital Coast SLR tiles (US)<br>
AWS Terrarium tiles · NASA SRTM 90m (intl)<br>
World Bank ER.H2O.FWTL.ZS
</div>""", unsafe_allow_html=True)
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown('<div class="data-footer"><a href="day05_extreme_heat" style="color:var(--text-3)">← Day 05 · Extreme Heat</a></div>',
                    unsafe_allow_html=True)

    # ── Main area ──────────────────────────────────────────────────────────────
    if not st.session_state.get("hide_intro_06"):
        cols = st.columns([1, 20, 1])
        with cols[1]:
            st.markdown("""<div class="intro-card">
<div class="intro-heading">Why sea level rise is unlike any other climate risk</div>
<div class="intro-pillars">
  <div class="intro-pillar">
    <div class="intro-pillar-icon">🌊</div>
    <div class="intro-pillar-title">Irreversibility</div>
    <div class="intro-pillar-body">Even at net-zero tomorrow, thermal expansion and ice melt already locked in will raise seas for centuries. Land flooded today does not return on any human planning horizon.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">📉</div>
    <div class="intro-pillar-title">Subsidence multiplier</div>
    <div class="intro-pillar-body">Jakarta sinks 25 cm/yr from groundwater extraction — 10× the IPCC global mean. Effective relative SLR in some megacities already exceeds the 2100 worst-case IPCC scenario.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">⚡</div>
    <div class="intro-pillar-title">Compound crises</div>
    <div class="intro-pillar-body">Rising seas contaminate freshwater aquifers with salt, destroying irrigation sources. Combined with Day 03 water stress and Day 05 heat, delta nations face simultaneous displacement, food, and water shocks.</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)
        if st.button("Dismiss", key="dismiss_intro_06"):
            st.session_state.hide_intro_06 = True
            st.rerun()

    st.markdown(_stats_strip(df), unsafe_allow_html=True)
    st.markdown(_narrative_bar(df), unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "RISK MAP", "FLOOD VIEWER", "SEA LEVEL HISTORY", "COMPOUND RISK",
    ])

    # ── TAB 1: Risk Map ────────────────────────────────────────────────────────
    with tab1:
        c_ssp1, c_yr1 = st.columns([2, 1])
        with c_ssp1:
            ssp1 = st.selectbox(
                "Emissions scenario",
                list(SSP_LABELS.keys()),
                format_func=lambda k: SSP_LABELS[k],
                index=2, key="ssp_map",
            )
        with c_yr1:
            year1 = st.select_slider("Year", [2030,2040,2050,2060,2070,2080,2090,2100],
                                     value=2100, key="yr_map")

        slr_now = get_ipcc_slr(ssp1, year1)
        ssp_col = SSP_COLORS[ssp1]
        st.markdown(
            f'<div style="font-size:11px;color:{ssp_col};padding:4px 0 6px">'
            f'<span class="ssp-badge" style="background:{ssp_col}22;color:{ssp_col}">{ssp1}</span>&nbsp;&nbsp;'
            f'Global mean SLR at {year1}: <strong>+{slr_now:.2f} m</strong> (IPCC AR6 median). '
            f'Map shows population exposed at this scenario.</div>',
            unsafe_allow_html=True,
        )

        map_fig = make_risk_map(df, selected_iso, ssp1, year1)
        event   = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun", key="coast_map")

        if event and event.get("selection", {}).get("points"):
            clicked = event["selection"]["points"][0].get("location")
            if clicked and clicked in df["iso"].values:
                selected_iso  = clicked
                selected_name = df[df["iso"] == clicked]["country_name"].iloc[0]

        # Legend
        legend_bands = [
            ("#e0f2fe","LOW","<1% of pop"),("#38bdf8","MODERATE","1–3%"),
            ("#0ea5e9","HIGH","3–10%"),("#0284c7","SEVERE","10–20%"),
            ("#1d4ed8","CRITICAL","20–50%"),("#7f1d1d","EXISTENTIAL",">50%"),
        ]
        lp = " ".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block"></span>'
            f'<span style="font-size:9px;color:#78716c;letter-spacing:0.06em">{l} ({r})</span></span>'
            for c, l, r in legend_bands
        )
        st.markdown(f'<div style="padding:4px 2px 8px;display:flex;flex-wrap:wrap">{lp}</div>',
                    unsafe_allow_html=True)
        st.markdown("""<div class="flood-info">
<strong>The subsidence multiplier:</strong> global mean SLR of 3–4 mm/yr is just part of the picture.
Jakarta (Indonesia) sinks at <strong>25 cm/yr</strong> from groundwater extraction —
an effective relative SLR of ~30 cm/yr. Ho Chi Minh City: 30–70 mm/yr. Bangkok: 30–80 mm/yr.
These cities are experiencing the 2100 worst-case scenario <em>right now</em>.
</div>""", unsafe_allow_html=True)

    # ── TAB 2: Flood Viewer ────────────────────────────────────────────────────
    with tab2:
        WORLD_OPT  = "🌍  World Overview"
        city_opts  = [WORLD_OPT] + sorted(FLOOD_CITIES.keys())

        c_city, c_ssp2, c_yr2 = st.columns([2, 1.5, 1])
        with c_city:
            city_name = st.selectbox("Select city / region", city_opts, key="city_06")
        with c_ssp2:
            ssp2 = st.selectbox(
                "SSP scenario",
                list(SSP_LABELS.keys()),
                format_func=lambda k: SSP_LABELS[k],
                index=2, key="ssp_flood",
            )
        with c_yr2:
            year2 = st.select_slider("Year", [2030,2040,2050,2060,2070,2080,2090,2100],
                                     value=2050, key="yr_flood")

        slr_g    = get_ipcc_slr(ssp2, year2)
        ssp_col2 = SSP_COLORS[ssp2]

        # ── WORLD OVERVIEW ─────────────────────────────────────────────────────
        if city_name == WORLD_OPT:
            # Global summary stats across all COASTAL_DATA countries
            total_risk_k, critical_n = 0, 0
            for iso, vals in COASTAL_DATA.items():
                p1, p2, p3, sub_mm, _, pop_total = vals
                exp = _pop_at_slr(p1, p2, p3, effective_slr(ssp2, year2, sub_mm))
                total_risk_k += exp
                if pop_total and exp / pop_total >= 0.20:
                    critical_n += 1

            worst_city_name, worst_slr = max(
                ((cn, effective_slr(ssp2, year2, cd.get("sub", 0)))
                 for cn, cd in FLOOD_CITIES.items()),
                key=lambda x: x[1],
            )

            st.markdown(
                f'<div class="flood-info">'
                f'<span class="ssp-badge" style="background:{ssp_col2}22;color:{ssp_col2};margin-right:8px">{ssp2}</span>'
                f'Global mean SLR at {year2}: <strong>+{slr_g:.2f} m</strong> (IPCC AR6 median). '
                f'Country colours = population displaced as % of total, adjusted for local subsidence. '
                f'Bubble markers show all {len(FLOOD_CITIES)} tracked flood-risk cities — size and colour reflect effective SLR. '
                f'Hover for city detail.'
                f'</div>',
                unsafe_allow_html=True,
            )

            c_w1, c_w2, c_w3, c_w4 = st.columns(4)
            for col, icon, val, label in [
                (c_w1, "🌊", f"+{slr_g:.2f}m",          "global mean SLR · IPCC AR6"),
                (c_w2, "👥", _fmt_pop(total_risk_k),      "people at risk across tracked nations"),
                (c_w3, "🔴", str(critical_n),              "countries at critical or worse risk"),
                (c_w4, "📍", worst_city_name.split(",")[0],
                             f"+{worst_slr:.2f}m effective SLR · highest tracked"),
            ]:
                col.markdown(
                    f'<div class="strip-card" style="padding:10px 12px">'
                    f'<div class="strip-icon">{icon}</div>'
                    f'<div class="strip-n" style="font-size:18px">{val}</div>'
                    f'<div class="strip-l">{label}</div></div>',
                    unsafe_allow_html=True,
                )

            with st.spinner("Building world flood risk map…"):
                world_map = make_world_flood_map(df, ssp2, year2)
            st_folium(world_map, use_container_width=True, height=560, returned_objects=[])

            st.markdown(
                '<div class="method-note">'
                '<strong>Data:</strong> Country choropleth uses coastal exposure data from '
                'Kulp &amp; Strauss 2019 (Climate Central / Nat. Comms.) with dynamic '
                'population displacement computed at the selected IPCC AR6 SLR + '
                'country-average subsidence. City bubble size and colour reflect effective '
                'relative SLR (global mean + local land subsidence since 2024). '
                'Countries without data shown in grey. '
                'Select any city from the dropdown to drill into a pixel-level flood map.</div>',
                unsafe_allow_html=True,
            )

        # ── CITY DETAIL VIEW ───────────────────────────────────────────────────
        else:
            city    = FLOOD_CITIES[city_name]
            sub     = city.get("sub", 0.0)
            slr_eff = effective_slr(ssp2, year2, sub)

            sub_note = ""
            if sub >= 5:
                sub_note = (f'<div class="subsidence-warning">⚠ <strong>High subsidence city:</strong> '
                            f'land is sinking at <strong>{sub:.0f} mm/yr</strong> from groundwater extraction. '
                            f'Effective relative SLR at {year2} = global {slr_g:.2f} m + subsidence '
                            f'{(sub*(year2-2024)/1000):.2f} m = <strong>{slr_eff:.2f} m total</strong>. '
                            f'The flood zone shown already accounts for this.</div>')

            noaa_station = city.get("noaa")
            noaa_ft      = slr_to_noaa_ft(slr_eff) if noaa_station else 0
            data_source  = (f"NOAA Digital Coast inundation tiles ({noaa_ft}ft scenario)"
                            if noaa_station
                            else "AWS Terrarium tiles · SRTM-derived pixel-level elevation")

            st.markdown(
                f'<div class="flood-info">'
                f'<span class="ssp-badge" style="background:{ssp_col2}22;color:{ssp_col2};margin-right:8px">{ssp2}</span>'
                f'<strong>{city_name}</strong> · {year2} · '
                f'Global SLR <strong>+{slr_g:.2f} m</strong>'
                f'{"" if sub < 1 else f" + subsidence <strong>+{(sub*(year2-2024)/1000):.2f} m</strong>"}'
                f' = effective <strong>+{slr_eff:.2f} m</strong><br>'
                f'<span style="font-size:10px;color:var(--text-3)">{city["note"]} · Source: {data_source}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if sub_note:
                st.markdown(sub_note, unsafe_allow_html=True)

            terrain = None
            if not noaa_station and slr_eff > 0:
                radius_km = city["radius"]
                zoom = 13 if radius_km <= 8 else (12 if radius_km <= 20 else 11)

                with st.spinner(f"Loading terrain tiles for {city_name} (cached 30 days)…"):
                    terrain = fetch_terrain_elevation(city["lat"], city["lon"], zoom=zoom)

                if terrain is None or terrain["tiles"] == 0:
                    st.warning("Could not load terrain tiles. Check your internet connection and retry.")
                else:
                    elev        = terrain["elevation"]
                    total_px    = elev.size
                    flooded_px  = int(np.sum((elev > 0) & (elev <= slr_eff)))
                    below_px    = int(np.sum(elev <= 0))
                    risk_px     = int(np.sum((elev > slr_eff) & (elev <= slr_eff + 0.5)))
                    flooded_pct = (flooded_px + below_px) / total_px * 100
                    px_res_m    = terrain["px_res_m"]

                    c_f1, c_f2, c_f3, c_f4 = st.columns(4)
                    for col, icon, val, label in [
                        (c_f1, "🌊", f"+{slr_eff:.2f}m",   "effective SLR at this scenario"),
                        (c_f2, "📐", f"{flooded_pct:.0f}%", "of mapped area at flood risk"),
                        (c_f3, "⚠️", f"{risk_px:,}",        "near-risk pixels (next +0.5m)"),
                        (c_f4, "🔭", f"~{px_res_m:.0f}m",  "terrain pixel resolution"),
                    ]:
                        col.markdown(
                            f'<div class="strip-card" style="padding:10px 12px">'
                            f'<div class="strip-icon">{icon}</div>'
                            f'<div class="strip-n" style="font-size:18px">{val}</div>'
                            f'<div class="strip-l">{label}</div></div>',
                            unsafe_allow_html=True,
                        )

            flood_map = make_flood_map(city_name, slr_eff, terrain, noaa_station, noaa_ft)
            st_folium(flood_map, use_container_width=True, height=520, returned_objects=[])

            st.markdown(
                '<div class="method-note">'
                '<strong>Methodology:</strong> US cities use NOAA Digital Coast pre-computed inundation tiles '
                '(precise surveyed DEMs, ±30cm accuracy). International cities use AWS Terrain Tiles '
                '(Terrarium format, derived from NASA SRTM 90m) decoded at pixel level — every pixel is '
                'coloured by its elevation zone relative to the effective SLR threshold. '
                'Navy = already below sea level · Cyan = flooded at this scenario · Sky = near-term risk (+0.5m). '
                'SRTM includes building heights so urban flood extent may be slightly underestimated. '
                'Effective SLR = IPCC AR6 median global SLR + local subsidence since 2024. '
                'Not suitable for site-specific engineering decisions.</div>',
                unsafe_allow_html=True,
            )

    # ── TAB 3: Sea Level History ───────────────────────────────────────────────
    with tab3:
        station_name = st.selectbox(
            "Select tide gauge station (NOAA CO-OPS)",
            ["— select a station —"] + sorted(TIDE_STATIONS.keys()),
            key="station_06",
        )

        if station_name == "— select a station —":
            st.markdown(
                '<div class="no-data-note" style="padding:24px 0;text-align:center;color:#94a3b8">'
                'Select a NOAA tide gauge station to view its sea level history 2000–2023.</div>',
                unsafe_allow_html=True,
            )
        else:
            sta = TIDE_STATIONS[station_name]
            with st.spinner(f"Fetching NOAA CO-OPS data for {station_name}…"):
                gauge_data = load_tide_gauge(sta["id"])

            if not gauge_data or not gauge_data.get("years"):
                st.warning(f"Could not load data for {station_name}. The station may have gaps — try another.")
            else:
                slope        = gauge_data["slope_mm_yr"]
                total_rise   = gauge_data["total_rise_mm"]
                recent_slope = gauge_data["recent_slope"]
                early_slope  = gauge_data["early_slope"]
                last_year    = gauge_data["last_year"]
                trend_color  = "#dc2626" if slope > 5 else "#0891b2" if slope > 2 else "#16a34a"
                accel        = recent_slope - early_slope

                st.markdown(f"""<div class="strip-row" style="margin-bottom:12px">
  <div class="strip-card"><div class="strip-icon">📈</div>
    <div class="strip-n" style="color:{trend_color}">{slope:+.1f}</div>
    <div class="strip-l">mm per year · full trend</div></div>
  <div class="strip-card"><div class="strip-icon">🌊</div>
    <div class="strip-n">{total_rise:.0f}</div>
    <div class="strip-l">mm total rise since 2000</div></div>
  <div class="strip-card"><div class="strip-icon">⚡</div>
    <div class="strip-n" style="color:{'#dc2626' if accel>0.5 else '#334155'}">{accel:+.1f}</div>
    <div class="strip-l">mm/yr acceleration (recent vs early)</div></div>
  <div class="strip-card"><div class="strip-icon">📅</div>
    <div class="strip-n">{last_year}</div>
    <div class="strip-l">most recent year on record</div></div>
</div>""", unsafe_allow_html=True)

                tide_fig = make_tide_chart(gauge_data, station_name)
                st.plotly_chart(tide_fig, use_container_width=True)

                if accel > 0.5:
                    st.markdown(
                        f'<div class="compound-risk">'
                        f'<div class="compound-risk-title">📈 Accelerating rise detected</div>'
                        f'<div class="compound-risk-body">'
                        f'{station_name} gained {early_slope:.1f} mm/yr in the early 2000s, '
                        f'now gaining <strong>{recent_slope:.1f} mm/yr</strong> — an acceleration of {accel:+.1f} mm/yr. '
                        f'Acceleration is a critical signal: linear projections understate risk when the rate is increasing.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div class="method-note">Data: NOAA CO-OPS monthly mean sea level, MSL datum, 2000–2023. '
                    'Annual means from monthly records; rise relative to 2000 baseline. '
                    '5-year rolling average applied. Acceleration = recent-half slope minus early-half slope (OLS).</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("""<div class="flood-info" style="margin-top:16px">
<strong>The acceleration problem:</strong> global mean SLR was ~1.4 mm/yr in the 20th century.
It is now <strong>3.6 mm/yr</strong> and accelerating. IPCC AR6 projects up to
<strong>10–12 mm/yr by 2100</strong> under SSP5-8.5 — an order-of-magnitude increase within living memory.
Tide gauges show this acceleration is already detectable at individual stations.
</div>""", unsafe_allow_html=True)

    # ── TAB 4: Compound Risk ───────────────────────────────────────────────────
    with tab4:
        st.markdown("""<div class="narrative-bar" style="margin-top:0">
  <div class="narrative-lede">Coastal flooding and water scarcity are the same crisis from two angles.</div>
  <div class="narrative-context">Saltwater intrusion from rising seas contaminates freshwater aquifers — degrading irrigation
  and drinking water in nations already under water stress (Day 03). The compound effect self-reinforces:
  farmers drill deeper wells, accelerating subsidence, which worsens relative SLR. Bubble size = SLR rate.</div>
</div>""", unsafe_allow_html=True)

        scatter_fig = make_compound_scatter(df, water_stress_raw)
        if scatter_fig.data:
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            st.info("Water stress data unavailable — check network connection.")

        # Dual-crisis nations callout
        dual = [iso for iso, ws in water_stress_raw.items()
                if ws > 25 and iso in COASTAL_DATA and COASTAL_DATA[iso][0] >= 500]
        if dual:
            names_dc = [country_names.get(iso, iso) for iso in dual[:10]]
            st.markdown(
                f'<div class="flood-info" style="margin-top:8px">'
                f'<strong>Dual coastal + water stress nations</strong> (withdrawal >25% AND >500K within 1m): '
                f'{", ".join(names_dc)}{"…" if len(dual) > 10 else ""}. '
                f'These {len(dual)} nations face simultaneous saltwater intrusion, freshwater scarcity, '
                f'and coastal displacement — a compound crisis that cannot be addressed in isolation.</div>',
                unsafe_allow_html=True,
            )

        c_ssp4, c_yr4 = st.columns([2, 1])
        with c_ssp4:
            ssp4 = st.selectbox(
                "Scenario",
                list(SSP_LABELS.keys()),
                format_func=lambda k: SSP_LABELS[k],
                index=2, key="ssp_comp",
            )
        with c_yr4:
            year4 = st.select_slider("Year ", [2030,2040,2050,2060,2070,2080,2090,2100],
                                     value=2100, key="yr_comp")

        city_fig = make_city_risk_chart(df, ssp4, year4)
        st.plotly_chart(city_fig, use_container_width=True)

        # Insight cards below the chart in a 3-column row
        c1, c2, c3 = st.columns(3)
        for col, (title, body) in zip([c1, c2, c3], [
            ("🌊 Saltwater intrusion",
             "As seas rise, salt water pushes into coastal aquifers. Bangladesh's coastal wells are already brackish — a creeping freshwater emergency underneath the flooding one."),
            ("🌾 Delta agriculture collapse",
             "The Mekong, Nile, and Ganges-Brahmaputra deltas together feed ~500M people. At 2m SLR, all three face catastrophic farmland loss within decades."),
            ("🏘 Climate migration trigger",
             "World Bank projects 216M internal climate migrants by 2050. Coastal flooding in BGD, VNM, and PHL is the single largest driver — this feeds directly into Day 09's migration index."),
        ]):
            col.markdown(
                f'<div class="flood-info" style="height:100%;box-sizing:border-box">'
                f'<strong>{title}</strong><br>'
                f'<span style="font-size:11px">{body}</span></div>',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
