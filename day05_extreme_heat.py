import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

st.set_page_config(
    page_title="Extreme Heat Atlas · Day 05",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

HEADERS     = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
OM_ARCHIVE  = "https://archive-api.open-meteo.com/v1/archive"
WB_BASE     = "https://api.worldbank.org/v2/country/all/indicator"
HEAT_THR    = 35   # apparent temperature °C → "heat stress day"
LABOUR_THR  = 32   # apparent temperature °C → outdoor labour restricted

HEAT_BANDS = [
    (120, "EXTREME",  "#7f1d1d", "rgba(127,29,29,0.10)"),
    (80,  "SEVERE",   "#dc2626", "rgba(220,38,38,0.09)"),
    (40,  "HIGH",     "#f97316", "rgba(249,115,22,0.09)"),
    (15,  "MODERATE", "#eab308", "rgba(234,179,8,0.09)"),
    (1,   "LOW",      "#16a34a", "rgba(22,163,74,0.09)"),
    (0,   "MINIMAL",  "#0ea5e9", "rgba(14,165,233,0.09)"),
]

HSCALE = [
    (0.00, "#bae6fd"),
    (0.06, "#86efac"),
    (0.18, "#fde68a"),
    (0.38, "#fb923c"),
    (0.62, "#dc2626"),
    (0.82, "#7f1d1d"),
    (1.00, "#450a0a"),
]

TEMP_DELTAS = {
    "Today — current climate":          0.0,
    "+1.5°C — Paris Agreement target":  1.5,
    "+2.0°C — pledged NDC trajectory":  2.0,
    "+3.0°C — SSP3-7.0 by 2050":       3.0,
}

# Days/year with apparent temperature > 35 °C (2018-2022 avg, country capitals)
# Sourced from ERA5 reanalysis / Open-Meteo; used for global choropleth baseline
HEAT_DATA = {
    "AFG": 45,  "AGO": 25,  "ARE": 148, "ARG": 12,  "AUS": 22,
    "BDI":  8,  "BEN": 52,  "BFA": 98,  "BGD": 72,  "BHR": 128,
    "BOL":  8,  "BRA": 38,  "BWA": 35,  "CAN":  4,  "CHE":  3,
    "CHL":  8,  "CHN": 25,  "CIV": 48,  "CMR": 38,  "COD": 18,
    "COL": 12,  "DEU":  4,  "DZA": 58,  "EGY": 62,  "ESP": 18,
    "ETH": 28,  "FIN":  1,  "FRA":  7,  "GBR":  2,  "GHA": 52,
    "GIN": 42,  "GRC": 22,  "GTM": 22,  "HND": 28,  "IDN": 38,
    "IND": 75,  "IRN": 72,  "IRQ":118,  "ITA": 16,  "JPN": 14,
    "KAZ": 18,  "KEN":  5,  "KHM": 62,  "KOR": 10,  "KWT":148,
    "LAO": 58,  "LBY": 72,  "LKA": 35,  "MAR": 28,  "MDG": 15,
    "MEX": 32,  "MLI":152,  "MMR": 55,  "MOZ": 22,  "MRT":138,
    "MWI": 22,  "MYS": 38,  "NER":162,  "NGA": 58,  "NIC": 32,
    "NLD":  3,  "NOR":  1,  "NPL": 32,  "OMN":138,  "PAK": 82,
    "PER":  8,  "PHL": 52,  "PNG": 32,  "POL":  4,  "PRT": 14,
    "PRY": 28,  "QAT":138,  "RUS":  3,  "RWA":  5,  "SAU":132,
    "SDN":128,  "SEN": 68,  "SLE": 32,  "SOM": 98,  "SSD": 78,
    "SWE":  1,  "SYR": 32,  "TCD":132,  "TGO": 52,  "THA": 58,
    "TUR": 22,  "TZA": 18,  "UGA":  8,  "UKR":  7,  "URY": 10,
    "USA": 18,  "UZB": 38,  "VEN": 22,  "VNM": 42,  "YEM": 88,
    "ZAF": 12,  "ZMB": 12,  "ZWE": 15,  "OMN":138,  "QAT":138,
    "TWN": 35,  "MMR": 55,  "LKA": 35,  "SGP": 32,  "KWT":148,
}

# Approximate agricultural employment share (% total) — for labour impact tab
AGRI_EMPL = {
    "NER":80, "BFA":77, "MLI":75, "TCD":73, "ETH":68, "UGA":66,
    "MOZ":68, "MWI":65, "RWA":62, "TZA":60, "BGD":38, "IND":42,
    "NPL":60, "KHM":28, "VNM":35, "LAO":62, "MMR":48, "PAK":40,
    "SEN":70, "GHA":45, "NGA":36, "GIN":60, "SLE":65, "BEN":55,
    "TGO":58, "CMR":48, "CIV":42, "COD":65, "ZMB":55, "ZWE":60,
    "SDN":45, "SOM":58, "SSD":70, "YEM":35, "IRQ":18, "IRN":16,
    "SAU": 2, "ARE": 1, "KWT": 1, "QAT": 1, "BHR": 1, "EGY":25,
    "DZA":12, "MAR":38, "LBY": 5, "SYR":18, "TUR":18, "GRC": 8,
    "ESP": 4, "ITA": 4, "PRT": 7, "FRA": 3, "DEU": 2, "GBR": 1,
    "POL": 9, "UKR":17, "RUS": 6, "KAZ":18, "UZB":25,
    "CHN":25, "JPN": 3, "KOR": 5, "TWN": 5, "THA":32, "IDN":29,
    "PHL":24, "MYS":11, "SGP": 1, "IND":42, "LKA":25, "AUS": 3,
    "USA": 2, "CAN": 2, "MEX":12, "BRA":10, "ARG": 7, "PRY":18,
    "BOL":30, "PER":28, "COL":16, "VEN":10, "GTM":32, "HND":35,
    "NIC":35, "ZAF": 6, "KEN":51, "BWA":25, "MDG":70, "AGO":55,
    "PNG":72, "SSD":70, "BDI":80, "GIN":60,
}

CITY_LIST = {
    "Dubai, UAE":                (25.20,  55.27),
    "Kuwait City, Kuwait":       (29.37,  47.98),
    "Riyadh, Saudi Arabia":      (24.69,  46.72),
    "Muscat, Oman":              (23.61,  58.59),
    "Doha, Qatar":               (25.29,  51.53),
    "Baghdad, Iraq":             (33.34,  44.40),
    "Tehran, Iran":              (35.69,  51.39),
    "Karachi, Pakistan":         (24.86,  67.01),
    "Lahore, Pakistan":          (31.55,  74.34),
    "New Delhi, India":          (28.64,  77.22),
    "Ahmedabad, India":          (23.03,  72.58),
    "Kolkata, India":            (22.57,  88.36),
    "Chennai, India":            (13.08,  80.27),
    "Dhaka, Bangladesh":         (23.81,  90.41),
    "Bangkok, Thailand":         (13.75, 100.50),
    "Ho Chi Minh City, Vietnam": (10.80, 106.68),
    "Manila, Philippines":       (14.60, 120.98),
    "Jakarta, Indonesia":        (-6.21, 106.85),
    "Phnom Penh, Cambodia":      (11.56, 104.92),
    "Yangon, Myanmar":           (16.87,  96.20),
    "Kuala Lumpur, Malaysia":    (3.15,  101.69),
    "Singapore":                 (1.29,  103.85),
    "Cairo, Egypt":              (30.04,  31.24),
    "Khartoum, Sudan":           (15.55,  32.53),
    "Niamey, Niger":             (13.51,   2.11),
    "Bamako, Mali":              (12.65,  -8.00),
    "Ouagadougou, Burkina Faso": (12.36,  -1.53),
    "N'Djamena, Chad":           (12.11,  15.04),
    "Lagos, Nigeria":            (6.52,    3.38),
    "Dakar, Senegal":            (14.76, -17.37),
    "Addis Ababa, Ethiopia":     (9.02,   38.75),
    "Nairobi, Kenya":            (-1.29,  36.82),
    "Dar es Salaam, Tanzania":   (-6.79,  39.21),
    "Kinshasa, DR Congo":        (-4.32,  15.32),
    "Maputo, Mozambique":        (-25.89, 32.61),
    "Athens, Greece":            (37.98,  23.73),
    "Madrid, Spain":             (40.42,  -3.70),
    "Seville, Spain":            (37.39,  -5.99),
    "Rome, Italy":               (41.90,  12.49),
    "Istanbul, Turkey":          (41.01,  28.95),
    "Phoenix, USA":              (33.45, -112.07),
    "Houston, USA":              (29.76,  -95.37),
    "Miami, USA":                (25.77,  -80.19),
    "Mexico City, Mexico":       (19.43,  -99.13),
    "São Paulo, Brazil":         (-23.55, -46.63),
    "Buenos Aires, Argentina":   (-34.60, -58.38),
    "Sydney, Australia":         (-33.87, 151.21),
    "Beijing, China":            (39.91,  116.39),
    "Shanghai, China":           (31.23,  121.47),
    "Tokyo, Japan":              (35.69,  139.69),
    "Seoul, South Korea":        (37.57,  127.00),
    "London, UK":                (51.51,   -0.13),
    "Paris, France":             (48.85,    2.35),
    "Berlin, Germany":           (52.52,   13.41),
    "Moscow, Russia":            (55.75,   37.62),
}

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');

:root {
  --bg:       #fff7ed;
  --glass:    rgba(255,255,255,0.76);
  --glass-b:  rgba(255,255,255,0.58);
  --glass-bd: rgba(0,0,0,0.06);
  --text-1:   #1c0a00;
  --text-2:   #57534e;
  --text-3:   #a8a29e;
  --accent:   #f97316;
  --accent-2: #dc2626;
  --sh-xs:    0 1px 2px rgba(0,0,0,0.04);
  --sh-sm:    0 2px 8px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.75);
  --sh-md:    0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.72);
  --sh-lg:    0 16px 48px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.65);
  --r:        12px;
  --r-sm:     8px;
}

body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  background:
    radial-gradient(ellipse at 12% 18%,  rgba(239,68,68,0.07)   0%, transparent 52%),
    radial-gradient(ellipse at 88% 82%,  rgba(249,115,22,0.07)  0%, transparent 52%),
    radial-gradient(ellipse at 52% 48%,  rgba(234,179,8,0.04)   0%, transparent 65%),
    linear-gradient(160deg, #fff7ed 0%, #fff8f1 40%, #fef9f0 100%) !important;
  background-attachment: fixed !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--text-2) !important;
}
.main .block-container {
  padding-top: 10px !important; padding-bottom: 16px !important;
  max-width: 100% !important;
  padding-left: 16px !important; padding-right: 16px !important;
}
#MainMenu, footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: rgba(255,251,246,0.82) !important;
  backdrop-filter: blur(28px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(28px) saturate(180%) !important;
  border-right: 1px solid rgba(255,255,255,0.6) !important;
  box-shadow: 4px 0 32px rgba(0,0,0,0.07), inset -1px 0 0 rgba(255,255,255,0.5) !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 22px 18px 28px !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: var(--text-2) !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] h2 {
  color: var(--text-1) !important; font-size: 18px !important;
  font-weight: 600 !important; letter-spacing: -0.02em !important; margin: 4px 0 0 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: rgba(255,255,255,0.92) !important;
  border-color: rgba(0,0,0,0.08) !important; color: var(--text-1) !important;
}

/* ── Metrics grid ── */
.metrics-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 8px; margin: 10px 0;
}
.metric-card {
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.72);
  border-radius: var(--r-sm); padding: 10px 11px;
  box-shadow: var(--sh-sm);
  animation: fadeSlideUp 0.3s ease both;
}
.metric-label { font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); margin-bottom: 3px; }
.metric-value { font-size: 18px; font-weight: 600; color: var(--text-1); line-height: 1.15; font-variant-numeric: tabular-nums; }
.metric-unit  { font-size: 10px; color: var(--text-3); font-weight: 400; margin-left: 2px; }

/* ── Country heading & thermo badge ── */
.country-heading { font-size: 17px; font-weight: 600; color: var(--text-1); letter-spacing: -0.02em; line-height: 1.25; margin-bottom: 6px; }
.thermo-badge { display: flex; align-items: center; gap: 10px; margin: 2px 0 10px; }
.heat-band-label { font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-3); }

/* ── Story card ── */
.story-card {
  font-size: 12px; line-height: 1.85; color: var(--text-2); margin-bottom: 10px;
  background: rgba(255,255,255,0.76);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.65);
  border-radius: var(--r-sm); padding: 12px 14px;
  box-shadow: var(--sh-sm);
  animation: fadeSlideUp 0.35s 0.08s ease both;
}

/* ── Dramatic fact callout ── */
.dramatic-fact {
  background: linear-gradient(135deg, rgba(249,115,22,0.04) 0%, rgba(255,255,255,0.64) 100%);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.65);
  border-left: 3px solid var(--fact-color, #f97316);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 11px 13px; margin: 0 0 10px;
  box-shadow: var(--sh-sm);
  font-size: 11px; line-height: 1.75; color: #44403c;
  animation: fadeSlideUp 0.4s 0.05s ease both;
}

/* ── Compound risk callout ── */
.compound-risk {
  border: 1px solid rgba(220,38,38,0.28); border-left: 3px solid #dc2626;
  background: rgba(254,226,226,0.32);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 11px 13px; margin: 0 0 10px;
  animation: shake 0.45s ease both;
  box-shadow: 0 2px 8px rgba(220,38,38,0.08);
}
.compound-risk-title { font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #dc2626; margin-bottom: 5px; }
.compound-risk-body  { font-size: 11px; line-height: 1.75; color: #78716c; }

/* ── Stats strip ── */
.strip-row { display: flex; gap: 10px; margin: 4px 0 8px; padding: 0 1px; }
.strip-card {
  flex: 1; min-width: 0;
  background: rgba(255,255,255,0.76);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,0.68);
  border-radius: var(--r); padding: 13px 15px;
  box-shadow: var(--sh-sm);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
  animation: fadeSlideUp 0.4s ease both; cursor: default;
}
.strip-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.strip-icon { margin-bottom: 6px; font-size: 16px; }
.strip-n {
  font-size: 22px; font-weight: 300; line-height: 1.1; margin-bottom: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.strip-l { font-size: 9px; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-3); line-height: 1.4; }

/* ── Narrative bar ── */
.narrative-bar {
  background: rgba(255,255,255,0.70);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid rgba(255,255,255,0.62);
  border-radius: var(--r); padding: 14px 18px; margin: 6px 0 8px;
  box-shadow: var(--sh-sm);
  animation: slideDown 0.4s 0.1s ease both;
}
.narrative-lede {
  font-size: 14px; font-weight: 500; color: var(--text-1);
  line-height: 1.6; margin-bottom: 6px; letter-spacing: -0.01em;
}
.narrative-context { font-size: 11px; color: var(--text-2); line-height: 1.7; }
.narrative-pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(220,38,38,0.09); border: 1px solid rgba(220,38,38,0.2);
  border-radius: 99px; padding: 2px 9px;
  font-size: 10px; font-weight: 600; color: #dc2626;
  vertical-align: middle; margin: 0 3px;
}
.narrative-pill-amber {
  background: rgba(245,158,11,0.09); border-color: rgba(245,158,11,0.2); color: #b45309;
}

/* ── Intro card ── */
.intro-card {
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,0.72);
  border-top: 2px solid rgba(239,68,68,0.38);
  border-radius: var(--r); padding: 18px 22px; margin: 4px 0 10px;
  animation: slideDown 0.4s ease both;
  box-shadow: var(--sh-md);
}
.intro-heading { font-size: 15px; font-weight: 600; color: var(--text-1); margin: 0 0 12px; letter-spacing: -0.02em; }
.intro-pillars { display: flex; gap: 12px; flex-wrap: wrap; }
.intro-pillar {
  flex: 1; min-width: 140px;
  background: rgba(249,115,22,0.04); border: 1px solid rgba(249,115,22,0.12);
  border-radius: var(--r-sm); padding: 10px 12px;
}
.intro-pillar-icon  { font-size: 18px; margin-bottom: 5px; }
.intro-pillar-title { font-size: 11px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.intro-pillar-body  { font-size: 10px; line-height: 1.65; color: var(--text-2); }

/* ── Wet-bulb explainer ── */
.wb-explainer {
  background: linear-gradient(135deg, rgba(220,38,38,0.06) 0%, rgba(255,255,255,0.62) 100%);
  border: 1px solid rgba(220,38,38,0.15);
  border-radius: var(--r); padding: 14px 18px; margin: 8px 0;
  box-shadow: var(--sh-sm);
  font-size: 11px; line-height: 1.75; color: var(--text-2);
}
.wb-explainer strong { color: var(--text-1); }
.wb-threshold-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.wb-threshold {
  flex: 1; min-width: 110px; padding: 8px 10px;
  border-radius: var(--r-sm); border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.72);
}
.wb-t-label { font-size: 8px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-3); margin-bottom: 3px; }
.wb-t-temp  { font-size: 16px; font-weight: 600; line-height: 1.2; }
.wb-t-desc  { font-size: 9px; color: var(--text-3); line-height: 1.55; margin-top: 2px; }

/* ── Heat tech card ── */
.heat-tech-card {
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.66);
  border-radius: var(--r); padding: 14px 16px; margin-bottom: 10px;
  box-shadow: var(--sh-sm);
  animation: fadeSlideUp 0.35s ease both;
  transition: transform 0.2s, box-shadow 0.2s;
}
.heat-tech-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.heat-tech-header { display: flex; align-items: center; gap: 10px; margin-bottom: 7px; }
.heat-tech-title  { font-size: 13px; font-weight: 600; color: var(--text-1); flex: 1; letter-spacing: -0.01em; }
.badge {
  font-size: 8px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 2px 7px; border-radius: 4px;
}
.badge-high   { background: rgba(220,38,38,0.11);  color: #b91c1c; }
.badge-medium { background: rgba(245,158,11,0.11);  color: #b45309; }
.badge-low    { background: rgba(148,163,184,0.14); color: #64748b; }
.heat-tech-desc { font-size: 11px; line-height: 1.75; color: var(--text-2); margin-bottom: 6px; }
.heat-tech-meta { display: flex; gap: 14px; font-size: 10px; color: var(--text-3); }

/* ── Method note ── */
.method-note {
  font-size: 10px; color: var(--text-3); line-height: 1.65;
  background: rgba(14,165,233,0.04); border: 1px solid rgba(14,165,233,0.1);
  border-radius: var(--r-sm); padding: 9px 13px; margin-top: 12px;
}

/* ── Glass panel ── */
.glass-panel {
  background: rgba(255,255,255,0.74);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid rgba(255,255,255,0.62);
  border-radius: var(--r); box-shadow: var(--sh-sm);
}

/* ── Misc UI ── */
.sep { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 13px 0; }
.day-label  { font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-3); }
.data-footer{ font-size: 10px; color: var(--text-3); letter-spacing: 0.04em; line-height: 2.0; }
.no-data-note{ font-size: 10px; color: var(--text-3); padding: 2px 4px 6px; }

/* ── Tabs ── */
button[data-baseweb="tab"] {
  color: var(--text-3) !important; font-size: 11px !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  background: transparent !important; font-family: 'Inter', sans-serif !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--text-1) !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: rgba(0,0,0,0.08) !important; }
[data-testid="stTabsContent"] { background: transparent !important; padding-top: 10px !important; }

/* ── Select styling ── */
div[data-baseweb="select"] > div {
  background: rgba(255,255,255,0.88) !important;
  border-color: rgba(0,0,0,0.09) !important;
  backdrop-filter: blur(12px) !important;
}

/* ── Keyframes ── */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-18px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes shake {
  0%,100% { transform: translateX(0); }
  20%     { transform: translateX(-4px); }
  40%     { transform: translateX(4px); }
  60%     { transform: translateX(-3px); }
  80%     { transform: translateX(2px); }
}
@keyframes barGrow { to { transform: scaleX(1); } }
@keyframes grainFill { to { transform: scaleY(1); } }
@keyframes pulseDot {
  0%, 100% { transform: scale(1);   opacity: 1; }
  50%      { transform: scale(1.5); opacity: 0.65; }
}
@keyframes heatPulse {
  0%, 100% { opacity: 0.7; }
  50%      { opacity: 1.0; }
}

/* ── Mobile ── */
@media (max-width: 768px) {
  .main .block-container { padding-left: 10px !important; padding-right: 10px !important; }
  .strip-row { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 8px !important; }
  .strip-card { min-width: unset !important; }
  .intro-pillars { flex-direction: column !important; gap: 8px !important; }
  .wb-threshold-row { flex-direction: column !important; }
  button[data-baseweb="tab"] { padding: 10px 8px !important; font-size: 10px !important; }
}
</style>
"""

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=86_400 * 14, persist="disk", show_spinner=False)
def load_country_names() -> dict[str, str]:
    url = "https://api.worldbank.org/v2/country?format=json&per_page=300"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        payload = r.json()
        return {c["id"]: c["name"] for c in payload[1] if len(c.get("id","")) == 3 and c["id"].isalpha()}
    except Exception:
        return {}


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_wb_indicator(code: str) -> dict[str, float]:
    """Fetch most-recent non-null value per country from World Bank (mrv=5)."""
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


def build_heat_df(country_names: dict[str, str]) -> pd.DataFrame:
    rows = []
    for iso, days in HEAT_DATA.items():
        rows.append({
            "iso": iso,
            "heat_days": days,
            "country_name": country_names.get(iso, iso),
            "agri_empl_pct": AGRI_EMPL.get(iso, 15),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_city_heat(lat: float, lon: float) -> dict:
    """Fetch heat stress day count per year (2000-2023) from Open-Meteo archive."""
    try:
        r = requests.get(OM_ARCHIVE, params={
            "latitude": lat, "longitude": lon,
            "start_date": "2000-01-01", "end_date": "2023-12-31",
            "daily": "apparent_temperature_max",
            "timezone": "auto",
        }, headers=HEADERS, timeout=45)
        r.raise_for_status()
        data   = r.json()
        dates  = data.get("daily", {}).get("time", [])
        vals   = data.get("daily", {}).get("apparent_temperature_max", [])

        year_heat: dict[int, int]   = {}
        year_labour: dict[int, int] = {}
        year_max: dict[int, float]  = {}

        for d, v in zip(dates, vals):
            if v is None:
                continue
            y = int(d[:4])
            year_heat[y]   = year_heat.get(y, 0) + (1 if v >= HEAT_THR else 0)
            year_labour[y] = year_labour.get(y, 0) + (1 if v >= LABOUR_THR else 0)
            if v > year_max.get(y, -999):
                year_max[y] = v

        years = sorted(year_heat.keys())
        if not years:
            return {}

        early = [year_heat[y] for y in years[:8]]
        recent = [year_heat[y] for y in years[-8:]]
        early_avg  = sum(early)  / len(early)  if early  else 0
        recent_avg = sum(recent) / len(recent) if recent else 0

        # Linear trend slope (days/year)
        n = len(years)
        x_m = sum(years) / n
        y_m = sum(year_heat[y] for y in years) / n
        denom = sum((y - x_m) ** 2 for y in years) or 1
        slope = sum((y - x_m) * (year_heat[y] - y_m) for y in years) / denom

        peak_year = max(year_heat, key=year_heat.get)

        return {
            "heat_by_year":       year_heat,
            "labour_by_year":     year_labour,
            "max_by_year":        year_max,
            "years":              years,
            "early_avg":          round(early_avg, 1),
            "recent_avg":         round(recent_avg, 1),
            "slope":              round(slope, 2),
            "peak_year":          peak_year,
            "peak_days":          year_heat[peak_year],
        }
    except Exception:
        return {}


# ── Core helpers ───────────────────────────────────────────────────────────────
def heat_band(days: float | None) -> tuple[str, str, str]:
    if days is None:
        return "N/A", "#94a3b8", "rgba(148,163,184,0.08)"
    for threshold, label, fg, bg in HEAT_BANDS:
        if days >= threshold:
            return label, fg, bg
    return "MINIMAL", "#0ea5e9", "rgba(14,165,233,0.09)"


def projected_days(baseline: float, delta_t: float) -> float:
    """Approximate heat stress days under warming scenario."""
    if baseline <= 0:
        # Near-zero baseline: rapid growth as threshold crossed
        return baseline + max(0, delta_t * 6)
    if baseline < 15:
        multiplier = 0.45
    elif baseline < 40:
        multiplier = 0.32
    elif baseline < 80:
        multiplier = 0.22
    else:
        multiplier = 0.12   # near saturation; growth slows
    return min(300, baseline * (1 + delta_t * multiplier))


def labour_loss_pct(heat_days: float, agri_pct: float) -> float:
    """Estimated % of annual outdoor work hours lost to heat restriction."""
    outdoor_share = min(agri_pct / 100, 0.85)
    loss_per_day  = 0.027   # ILO: ~2.7% hourly loss at peak heat (35°C apparent)
    return round(heat_days * loss_per_day * outdoor_share, 1)


def _fmt(v, dec: int = 1, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.{dec}f}{unit}"


# ── SVG helpers ────────────────────────────────────────────────────────────────
def thermometer_svg(fill_pct: float, color: str) -> str:
    """Animated thermometer badge (40×80px viewport)."""
    pct      = max(0.0, min(1.0, fill_pct))
    fill_h   = max(3, int(50 * pct))
    merc_y   = 15 + (50 - fill_h)
    return f"""<svg width="32" height="64" viewBox="0 0 40 80" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="16" y="10" width="8" height="54" rx="4" fill="rgba(0,0,0,0.06)" stroke="rgba(0,0,0,0.14)" stroke-width="1"/>
  <circle cx="20" cy="68" r="9" fill="{color}" opacity="0.88"/>
  <circle cx="20" cy="68" r="9" stroke="rgba(0,0,0,0.14)" stroke-width="1" fill="none"/>
  <rect x="17.5" y="{merc_y}" width="5" height="{fill_h + 9}" rx="2"
        fill="{color}" opacity="0.88"
        style="transform-origin:bottom center;transform:scaleY(0);animation:grainFill 0.75s 0.1s ease-out forwards;"/>
  <line x1="14" y1="15" x2="16" y2="15" stroke="rgba(0,0,0,0.28)" stroke-width="1"/>
  <line x1="14" y1="28" x2="16" y2="28" stroke="rgba(0,0,0,0.15)" stroke-width="0.8"/>
  <line x1="14" y1="41" x2="16" y2="41" stroke="rgba(0,0,0,0.15)" stroke-width="0.8"/>
  <line x1="14" y1="54" x2="16" y2="54" stroke="rgba(0,0,0,0.15)" stroke-width="0.8"/>
  <line x1="14" y1="63" x2="16" y2="63" stroke="rgba(0,0,0,0.28)" stroke-width="1"/>
</svg>"""


def heat_wave_icon(color: str = "#f97316") -> str:
    return f"""<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round">
  <path d="M2 12 C4 9, 6 9, 8 12 S12 15, 14 12 S18 9, 20 12 S22 9, 24 12"/>
  <path d="M2 16 C4 13, 6 13, 8 16 S12 19, 14 16 S18 13, 20 16"/>
  <path d="M2 8  C4 5, 6 5, 8 8 S12 11, 14 8 S18 5, 20 8"/>
</svg>"""


# ── HTML component builders ────────────────────────────────────────────────────
def _stats_strip(df: pd.DataFrame) -> str:
    extreme  = int((df["heat_days"] >= 80).sum())
    avg_days = df["heat_days"].mean()
    hottest  = df.loc[df["heat_days"].idxmax()]
    coolest  = df[df["heat_days"] <= 5]
    safe_ct  = len(coolest)

    cards = [
        ("🔥", f'<span style="color:#dc2626">{extreme}</span>', "countries · severe or worse"),
        ("🌡️", f"{avg_days:.0f}", "global avg heat stress days/yr"),
        ("🏜️", hottest["country_name"], f'{hottest["heat_days"]:.0f} days · most heat-stressed'),
        ("❄️", f"{safe_ct}", "countries · minimal heat stress"),
    ]
    parts = []
    for i, (icon, val, label) in enumerate(cards):
        delay = i * 0.06
        parts.append(f"""
        <div class="strip-card" style="animation-delay:{delay:.2f}s">
          <div class="strip-icon">{icon}</div>
          <div class="strip-n">{val}</div>
          <div class="strip-l">{label}</div>
        </div>""")
    return f'<div class="strip-row">{"".join(parts)}</div>'


def _narrative_bar(df: pd.DataFrame) -> str:
    extreme = int((df["heat_days"] >= 120).sum())
    severe  = int((df["heat_days"] >= 80).sum())
    at_risk_pop_proxy = int((df[df["heat_days"] >= 40]["agri_empl_pct"]).sum())
    return f"""<div class="narrative-bar">
  <div class="narrative-lede">
    <span class="narrative-pill">{extreme} countries</span> already exceed 120 heat-stress days per year —
    a reality where outdoor work becomes life-threatening for months at a time.
  </div>
  <div class="narrative-context">
    A <strong>heat stress day</strong> is any day when apparent temperature peaks above 35 °C —
    the threshold at which the body cannot cool itself through sweat alone.
    <span class="narrative-pill-amber">{severe} nations</span> face 80+ such days annually,
    concentrated in the Sahel, Arabian Peninsula, South Asia, and Mekong basin.
    Under SSP3-7.0 by 2050, this number expands dramatically into temperate zones currently considered safe.
  </div>
</div>"""


def country_heat_fact(r: pd.Series, water_stress: float | None) -> tuple[str, str]:
    name  = r.get("country_name", "")
    days  = r.get("heat_days", 0) or 0
    agri  = r.get("agri_empl_pct", 15) or 15
    ll    = labour_loss_pct(days, agri)

    if days >= 130:
        fact  = (f"<strong>{name}</strong> endures more than <strong>{int(days)} heat-stress days a year</strong> — "
                 f"over a third of the year at dangerous apparent temperatures. Outdoor workers here "
                 f"face conditions that exceed the ILO survivability guideline for months on end.")
        color = "#7f1d1d"
    elif days >= 80:
        fact  = (f"In <strong>{name}</strong>, <strong>{int(days)} days a year</strong> push apparent temperatures "
                 f"above 35 °C. Estimated labour productivity loss: <strong>{ll:.0f}% of annual outdoor hours</strong>, "
                 f"costing agricultural output and widening economic vulnerability.")
        color = "#dc2626"
    elif days >= 40:
        fact  = (f"<strong>{name}</strong> faces <strong>{int(days)} heat-stress days annually</strong>. "
                 f"With {agri:.0f}% of workers in agriculture, that translates to an estimated "
                 f"<strong>{ll:.0f}% loss of outdoor labour productivity</strong> — a quiet economic drag.")
        color = "#f97316"
    elif days >= 10:
        if water_stress and water_stress > 40:
            fact  = (f"<strong>{name}</strong> currently experiences moderate heat stress ({int(days)} days/yr). "
                     f"Combined with high water stress, a warming climate creates compounding agricultural risk "
                     f"even for a country not yet in crisis.")
            color = "#eab308"
        else:
            fact  = (f"<strong>{name}</strong> has <strong>{int(days)} heat-stress days per year</strong> today — "
                     f"a moderate exposure. Under a +3 °C scenario, that number is projected to more than double.")
            color = "#eab308"
    else:
        fact  = (f"<strong>{name}</strong> currently sees minimal extreme heat. "
                 f"But climate models show even northern and temperate nations will face growing heat exposure "
                 f"by 2040–2050 under current emissions trajectories.")
        color = "#16a34a"

    return f'<div class="dramatic-fact" style="--fact-color:{color}">{fact}</div>', color


def _country_panel(r: pd.Series, water_stress: float | None) -> str:
    name    = r.get("country_name", r.get("iso", ""))
    days    = r.get("heat_days") or 0
    agri    = r.get("agri_empl_pct") or 15
    ll      = labour_loss_pct(days, agri)
    label, fg, bg = heat_band(days)
    fill_pct      = min(1.0, days / 180)

    thermo = thermometer_svg(fill_pct, fg)
    fact_html, fact_color = country_heat_fact(r, water_stress)

    # Scenario projections
    proj_15 = projected_days(days, 1.5)
    proj_30 = projected_days(days, 3.0)

    metrics = f"""<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-label">Heat stress days/yr</div>
    <div class="metric-value" style="color:{fg}">{_fmt(days, 0)}<span class="metric-unit">days</span></div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Heat tier</div>
    <div class="metric-value" style="color:{fg};font-size:13px;font-weight:700">{label}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Labour hours lost</div>
    <div class="metric-value">{_fmt(ll, 1)}<span class="metric-unit">%/yr</span></div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Agri workforce</div>
    <div class="metric-value">{_fmt(agri, 0)}<span class="metric-unit">%</span></div>
  </div>
</div>"""

    proj_html = f"""<div style="font-size:10px;color:var(--text-3);margin:6px 0 2px;letter-spacing:0.06em;text-transform:uppercase">Projected heat days</div>
<div style="display:flex;gap:8px;margin-bottom:8px">
  <div style="flex:1;background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.18);border-radius:8px;padding:7px 9px;text-align:center">
    <div style="font-size:8px;color:#b45309;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px">+1.5°C</div>
    <div style="font-size:16px;font-weight:600;color:#c2410c">{proj_15:.0f}</div>
  </div>
  <div style="flex:1;background:rgba(220,38,38,0.08);border:1px solid rgba(220,38,38,0.18);border-radius:8px;padding:7px 9px;text-align:center">
    <div style="font-size:8px;color:#991b1b;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px">+3.0°C</div>
    <div style="font-size:16px;font-weight:600;color:#991b1b">{proj_30:.0f}</div>
  </div>
</div>"""

    compound = ""
    if water_stress and water_stress > 40 and days >= 40:
        compound = f"""<div class="compound-risk">
  <div class="compound-risk-title">⚠ Compound water + heat stress</div>
  <div class="compound-risk-body">Water stress at {water_stress:.0f}% withdrawal rate combined with
  {int(days)} heat days creates a dual agricultural crisis where drought and dangerous working
  conditions co-occur. A single bad season can cascade into food insecurity.</div>
</div>"""

    narrative_map = {
        "EXTREME": (f"{name} is at the extreme edge of human heat tolerance. Outdoor survival depends on shade, water, and rest — infrastructure that most residents lack.",),
        "SEVERE":  (f"In {name}, extreme heat is already embedded in daily life for millions of outdoor workers and subsistence farmers.",),
        "HIGH":    (f"{name} faces significant heat stress across several months a year. The economic impact on agriculture and construction is measurable and growing.",),
        "MODERATE":(f"{name} is in a transitional zone — heat stress is real and growing, but not yet at crisis level. The trajectory under +3°C is the critical concern.",),
        "LOW":     (f"{name} currently sees limited extreme heat, but climate models show rapid expansion of heat-stress days under mid-century warming.",),
        "MINIMAL": (f"{name} is one of the least heat-stressed countries today. Warming will bring change, but from a low baseline.",),
    }
    story_text = narrative_map.get(label, (f"{name} — heat exposure data available above.",))[0]

    return f"""<div class="country-heading">{name}</div>
<div class="thermo-badge">{thermo}
  <div>
    <div style="font-size:10px;color:{fg};font-weight:700;letter-spacing:0.1em;text-transform:uppercase">{label}</div>
    <div style="font-size:10px;color:var(--text-3)">{int(days)} days/yr above 35 °C apparent temp</div>
  </div>
</div>
{metrics}
{proj_html}
{fact_html}
{compound}
<div class="story-card">{story_text}</div>"""


# ── Chart builders ─────────────────────────────────────────────────────────────
def make_heat_map(df: pd.DataFrame, selected_iso: str, delta_t: float) -> go.Figure:
    plot_df = df.copy()
    if delta_t > 0:
        plot_df["heat_days"] = plot_df["heat_days"].apply(lambda d: projected_days(d, delta_t))

    cscale = [[v, c] for v, c in HSCALE]
    zmax   = 200

    fig = px.choropleth(
        plot_df,
        locations="iso",
        color="heat_days",
        hover_name="country_name",
        hover_data={"iso": False, "heat_days": ":.0f"},
        color_continuous_scale=cscale,
        range_color=(0, zmax),
        labels={"heat_days": "Days/yr"},
    )
    fig.update_traces(
        marker_line_width=0.4,
        marker_line_color="rgba(255,255,255,0.4)",
        hovertemplate="<b>%{hovertext}</b><br>Heat stress days: %{z:.0f}/yr<extra></extra>",
    )

    # Extreme countries overlay
    extreme = plot_df[plot_df["heat_days"] >= 120]
    if not extreme.empty:
        fig.add_trace(go.Choropleth(
            locations=extreme["iso"],
            z=[1] * len(extreme),
            colorscale=[[0, "rgba(127,29,29,0.0)"], [1, "rgba(127,29,29,0.0)"]],
            showscale=False,
            marker_line_width=1.2,
            marker_line_color="#7f1d1d",
            hoverinfo="skip",
        ))

    # Selected country outline
    if selected_iso:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso],
            z=[1],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False,
            marker_line_width=2.4,
            marker_line_color="#f97316",
            hoverinfo="skip",
        ))

    fig.update_geos(
        showframe=False, showcoastlines=False, showland=True,
        landcolor="rgba(241,245,249,0.9)",
        showocean=True, oceancolor="rgba(219,234,254,0.55)",
        showcountries=False,
        projection_type="natural earth",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_coloraxes(
        colorbar=dict(
            title=dict(text="Days/yr", font=dict(size=10, color="#57534e")),
            thickness=10, len=0.55, x=1.0, y=0.5,
            tickfont=dict(size=9, color="#57534e"),
            tickvals=[0, 40, 80, 120, 160, 200],
            ticktext=["0", "40", "80", "120", "160", "200+"],
            bgcolor="rgba(255,255,255,0.5)",
            bordercolor="rgba(0,0,0,0.1)", borderwidth=1,
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def make_city_trend(city_data: dict, city_name: str) -> go.Figure:
    heat_by_year   = city_data.get("heat_by_year", {})
    labour_by_year = city_data.get("labour_by_year", {})
    slope          = city_data.get("slope", 0)

    if not heat_by_year:
        return go.Figure()

    years      = sorted(heat_by_year.keys())
    heat_vals  = [heat_by_year[y]   for y in years]
    labour_vals= [labour_by_year.get(y, 0) for y in years]

    # Trend line
    n    = len(years)
    x_m  = sum(years) / n
    y_m  = sum(heat_vals) / n
    trend_vals = [y_m + slope * (y - x_m) for y in years]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=labour_vals,
        name="Labour-restricted days (>32°C)",
        marker_color="rgba(234,179,8,0.25)",
        marker_line_width=0,
        hovertemplate="%{x}: %{y} labour-restricted days<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=years, y=heat_vals,
        name="Heat stress days (>35°C)",
        marker_color="rgba(220,38,38,0.65)",
        marker_line_width=0,
        hovertemplate="%{x}: %{y} heat stress days<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=trend_vals,
        name=f"Trend ({slope:+.1f} days/yr)",
        line=dict(color="#7f1d1d", width=1.8, dash="dot"),
        hoverinfo="skip",
    ))

    # 2050 projection
    proj_y = [2030, 2040, 2050]
    recent_avg = city_data.get("recent_avg", heat_vals[-1])
    base_2023  = heat_vals[-1]
    for i, py in enumerate(proj_y):
        dt = [1.0, 2.0, 3.0][i]
        pv = projected_days(base_2023, dt)
        fig.add_trace(go.Scatter(
            x=[py], y=[pv],
            mode="markers+text",
            marker=dict(size=9, color=["#f97316", "#dc2626", "#7f1d1d"][i], symbol="diamond"),
            text=[f"+{dt:.0f}°C"],
            textposition="top center",
            textfont=dict(size=8),
            name=f"2050 (+{dt:.0f}°C)",
            hovertemplate=f"2050 at +{dt}°C: {{y:.0f}} days<extra></extra>",
        ))

    fig.update_layout(
        barmode="overlay",
        height=320,
        margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.5)",
        legend=dict(
            orientation="h", x=0, y=-0.18,
            font=dict(size=9, color="#57534e"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(size=9, color="#57534e"),
        ),
        yaxis=dict(
            title=dict(text="Days/year", font=dict(size=9, color="#57534e")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False,
            tickfont=dict(size=9, color="#57534e"),
        ),
        title=dict(text=f"Heat stress history — {city_name}", font=dict(size=12, color="#1c0a00"), x=0.02),
    )
    return fig


def make_labour_chart(df: pd.DataFrame, delta_t: float, water_stress_dict: dict) -> go.Figure:
    plot_df = df.copy()
    if delta_t > 0:
        plot_df["heat_days"] = plot_df["heat_days"].apply(lambda d: projected_days(d, delta_t))
    plot_df["ll"] = plot_df.apply(lambda r: labour_loss_pct(r["heat_days"], r["agri_empl_pct"]), axis=1)
    top = plot_df.nlargest(25, "ll").reset_index(drop=True)

    colors = []
    for _, row in top.iterrows():
        label, fg, _ = heat_band(row["heat_days"])
        colors.append(fg)

    fig = go.Figure(go.Bar(
        x=top["ll"],
        y=top["country_name"],
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=[f"{v:.1f}%" for v in top["ll"]],
        textposition="outside",
        textfont=dict(size=8),
        hovertemplate="<b>%{y}</b><br>Labour hours lost: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        height=560,
        margin=dict(l=8, r=40, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.5)",
        xaxis=dict(
            title=dict(text="Annual outdoor work hours lost (%)", font=dict(size=9, color="#57534e")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            tickfont=dict(size=9, color="#57534e"),
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=9, color="#57534e"),
        ),
        title=dict(text="Labour productivity loss from heat (top 25 countries)", font=dict(size=12, color="#1c0a00"), x=0.01),
    )
    return fig


def make_compound_scatter(df: pd.DataFrame, water_stress_dict: dict) -> go.Figure:
    rows = []
    for _, r in df.iterrows():
        ws = water_stress_dict.get(r["iso"])
        if ws is not None:
            rows.append({
                "iso": r["iso"],
                "name": r["country_name"],
                "heat": r["heat_days"],
                "water": ws,
                "agri": r["agri_empl_pct"],
            })
    if not rows:
        return go.Figure()

    sdf = pd.DataFrame(rows)
    label_arr, color_arr = zip(*[heat_band(d)[:2] for d in sdf["heat"]])

    fig = go.Figure(go.Scatter(
        x=sdf["heat"],
        y=sdf["water"],
        mode="markers+text",
        text=sdf["iso"],
        textposition="top center",
        textfont=dict(size=7, color="#57534e"),
        marker=dict(
            size=sdf["agri"].apply(lambda a: max(6, min(24, a * 0.28))),
            color=list(color_arr),
            opacity=0.82,
            line=dict(width=1, color="rgba(255,255,255,0.7)"),
        ),
        customdata=sdf[["name", "heat", "water", "agri"]].values,
        hovertemplate="<b>%{customdata[0]}</b><br>Heat stress: %{customdata[1]:.0f} days<br>Water stress: %{customdata[2]:.0f}%<br>Agri employment: %{customdata[3]:.0f}%<extra></extra>",
    ))

    # Quadrant shading
    fig.add_shape(type="rect", x0=80, x1=300, y0=40, y1=110,
                  fillcolor="rgba(220,38,38,0.07)", line_width=0)
    fig.add_annotation(x=190, y=103, text="⚠ HIGH COMPOUND RISK",
                       font=dict(size=8, color="#dc2626"), showarrow=False)

    fig.update_layout(
        height=420,
        margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.52)",
        xaxis=dict(
            title=dict(text="Heat stress days/yr", font=dict(size=9, color="#57534e")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            tickfont=dict(size=9, color="#57534e"),
        ),
        yaxis=dict(
            title=dict(text="Water withdrawal stress (%)", font=dict(size=9, color="#57534e")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            tickfont=dict(size=9, color="#57534e"),
        ),
        title=dict(text="Compound heat + water stress (bubble size = agricultural workforce %)", font=dict(size=11, color="#1c0a00"), x=0.01),
    )
    return fig


# ── Heat adaptation strategies ─────────────────────────────────────────────────
HEAT_STRATEGIES = {
    "EXTREME": [
        {"title": "Cool centres & shade infrastructure", "urgency": "HIGH",
         "desc": "Public cool zones with misting systems can cut heat mortality 30–40%. Chennai and Ahmedabad have city-scale networks.",
         "example": "Ahmedabad Heat Action Plan — 40% mortality reduction"},
        {"title": "Shift work windows (pre-dawn agriculture)", "urgency": "HIGH",
         "desc": "ILO guidelines recommend moving outdoor labour to 4–9am. Productivity loss drops from 30% to under 8% in the same heat event.",
         "example": "Bangladesh garment sector + Saudi construction"},
        {"title": "Drought & heat-tolerant crop varieties", "urgency": "HIGH",
         "desc": "CGIAR HTMA sorghum and pearl millet withstand 40°C+ with 20% better yield than standard varieties.",
         "example": "ICRISAT HTMA varieties — Sahel + South Asia"},
        {"title": "Urban greening & cool roof mandates", "urgency": "MEDIUM",
         "desc": "Increasing urban albedo from 0.15 to 0.40 via cool roofs lowers peak urban temps 2–4°C, cutting heat stress days.",
         "example": "Los Angeles Cool Roof program, New York CoolRoofs"},
    ],
    "SEVERE": [
        {"title": "Early warning + community alert systems", "urgency": "HIGH",
         "desc": "SMS-based heat alerts reach 80% of at-risk populations in 24h. Proven 25–35% reduction in heat-related ER visits.",
         "example": "EU Copernicus heat warning, India National Heat Action"},
        {"title": "Micro-drip irrigation (heat + water co-benefit)", "urgency": "HIGH",
         "desc": "Soil-moisture-triggered drip irrigation cuts water use 50% and maintains crop temperature 3–5°C cooler via evapotranspiration.",
         "example": "Netafim model — Morocco, Tunisia, India"},
        {"title": "Occupational heat standard enforcement", "urgency": "MEDIUM",
         "desc": "OSHA-equivalent heat standards mandate rest-water-shade at 32°C+. Compliance cuts heat illness 60–70% in field workers.",
         "example": "California outdoor heat standards (2005, expanded 2021)"},
    ],
    "HIGH": [
        {"title": "Green building + passive cooling design", "urgency": "MEDIUM",
         "desc": "Natural ventilation, thermal mass, and shading reduce indoor temperatures 5–8°C without air conditioning energy cost.",
         "example": "Singapore BCA Green Mark, EU EPBD passive cooling"},
        {"title": "Agricultural calendar adjustment", "urgency": "MEDIUM",
         "desc": "Shifting sowing dates 4–6 weeks earlier avoids peak heat during grain filling. 8–15% yield improvement documented.",
         "example": "CIMMYT heat-escape phenology — India, Pakistan"},
    ],
    "MODERATE": [
        {"title": "Heat health surveillance systems", "urgency": "LOW",
         "desc": "Hospital admission tracking + weather monitoring creates an early-warning signal before crisis thresholds are crossed.",
         "example": "French PSAS-9 surveillance network post-2003 heatwave"},
        {"title": "Urban heat island mitigation", "urgency": "LOW",
         "desc": "Tree canopy targets of 30%+ in residential areas reduce peak heat by 2–3°C and improve pedestrian thermal comfort.",
         "example": "Singapore Urban Greenery Plan, Melbourne Urban Forest Strategy"},
    ],
}


def _heat_tech_cards(band_label: str) -> str:
    strategies = HEAT_STRATEGIES.get(band_label, HEAT_STRATEGIES["MODERATE"])
    parts = []
    for s in strategies:
        urgency_cls = {"HIGH": "badge-high", "MEDIUM": "badge-medium", "LOW": "badge-low"}.get(s["urgency"], "badge-low")
        parts.append(f"""<div class="heat-tech-card">
  <div class="heat-tech-header">
    <div class="heat-tech-title">{s["title"]}</div>
    <span class="badge {urgency_cls}">{s["urgency"]} URGENCY</span>
  </div>
  <div class="heat-tech-desc">{s["desc"]}</div>
  <div class="heat-tech-meta"><span>📍 {s["example"]}</span></div>
</div>""")
    return "\n".join(parts)


# ── Main app ───────────────────────────────────────────────────────────────────
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    with st.spinner("Loading country data…"):
        country_names    = load_country_names()
        water_stress_raw = load_wb_indicator("ER.H2O.FWTL.ZS")

    df = build_heat_df(country_names)
    df = df[df["heat_days"].notna()].copy()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="day-label">Day 05 · The Resilience Stack</div>', unsafe_allow_html=True)
        st.markdown("## Extreme Heat Atlas")
        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        sorted_df      = df.sort_values("country_name")
        iso_options    = sorted_df["iso"].tolist()
        name_options   = sorted_df["country_name"].tolist()
        default_idx    = iso_options.index("IND") if "IND" in iso_options else 0

        selected_name  = st.selectbox("Select country", name_options, index=default_idx)
        selected_iso   = iso_options[name_options.index(selected_name)]

        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        selected_row = df[df["iso"] == selected_iso].iloc[0]
        ws_val       = water_stress_raw.get(selected_iso)
        st.markdown(_country_panel(selected_row, ws_val), unsafe_allow_html=True)

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("""<div class="data-footer">
Sources: ERA5 reanalysis · Open-Meteo Archive API<br>
World Bank ER.H2O.FWTL.ZS · ILO heat-labour guidelines<br>
IPCC AR6 WG1 · Steadman apparent temperature formula
</div>""", unsafe_allow_html=True)
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.page_link("day04_food_fragility.py", label="← Day 04 · Food Fragility")

    # ── Main area ──────────────────────────────────────────────────────────────
    # Intro card
    if not st.session_state.get("hide_intro_05"):
        cols_intro = st.columns([1, 20, 1])
        with cols_intro[1]:
            st.markdown("""<div class="intro-card">
<div class="intro-heading">What is extreme heat? Why does wet-bulb temperature matter?</div>
<div class="intro-pillars">
  <div class="intro-pillar">
    <div class="intro-pillar-icon">🌡️</div>
    <div class="intro-pillar-title">The 35°C wet-bulb limit</div>
    <div class="intro-pillar-body">At 35°C wet-bulb temperature, sweat can no longer evaporate — the human body's only cooling mechanism. Six hours of exposure is fatal regardless of shade or water access. This is not a distant threshold: parts of the Persian Gulf already brush it.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">💧</div>
    <div class="intro-pillar-title">Apparent temperature vs. air temperature</div>
    <div class="intro-pillar-body">A 40°C day in dry Phoenix feels different than a 35°C day in humid Dhaka. Apparent temperature (the "feels-like" measure) combines heat and humidity via the Steadman formula — the metric used throughout this atlas.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">⚡</div>
    <div class="intro-pillar-title">Compounding crises</div>
    <div class="intro-pillar-body">Heat peaks exactly when electricity demand is highest (air conditioning) and water demand for crops is greatest. Countries with fragile grids and water stress face all three simultaneously — the polycrisis scenario.</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)
        if st.button("Dismiss", key="dismiss_intro_05"):
            st.session_state.hide_intro_05 = True
            st.rerun()

    # Stats strip
    st.markdown(_stats_strip(df), unsafe_allow_html=True)

    # Narrative bar
    st.markdown(_narrative_bar(df), unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "HEAT MAP",
        "CITY HEAT HISTORY",
        "COMPOUND RISK",
        "LABOUR & ADAPTATION",
    ])

    # ── TAB 1: Heat map ────────────────────────────────────────────────────────
    with tab1:
        scenario_label = st.select_slider(
            "Warming scenario",
            options=list(TEMP_DELTAS.keys()),
            value="Today — current climate",
            key="scenario_05",
        )
        delta_t = TEMP_DELTAS[scenario_label]

        if delta_t > 0:
            st.markdown(
                f'<div style="font-size:11px;color:#c2410c;padding:4px 0 6px">'
                f'Showing projected heat stress days at <strong>{scenario_label}</strong>. '
                f'Countries in moderate zones today cross into HIGH or SEVERE tier under this scenario.</div>',
                unsafe_allow_html=True,
            )

        map_fig = make_heat_map(df, selected_iso, delta_t)
        event   = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun", key="heat_map")

        if event and event.get("selection", {}).get("points"):
            clicked_iso = event["selection"]["points"][0].get("location")
            if clicked_iso and clicked_iso in df["iso"].values:
                selected_iso  = clicked_iso
                selected_name = df[df["iso"] == clicked_iso]["country_name"].iloc[0]

        # Map legend
        legend_bands = [
            ("#bae6fd", "MINIMAL", "0–1"),
            ("#86efac", "LOW",     "1–15"),
            ("#fde68a", "MODERATE","15–40"),
            ("#fb923c", "HIGH",    "40–80"),
            ("#dc2626", "SEVERE",  "80–120"),
            ("#7f1d1d", "EXTREME", "120+"),
        ]
        legend_parts = " ".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block"></span>'
            f'<span style="font-size:9px;color:#78716c;letter-spacing:0.06em">{label} ({rng} days/yr)</span>'
            f'</span>'
            for c, label, rng in legend_bands
        )
        st.markdown(
            f'<div style="padding:4px 2px 8px;display:flex;flex-wrap:wrap">{legend_parts}</div>',
            unsafe_allow_html=True,
        )

        # Wet-bulb explainer
        st.markdown("""<div class="wb-explainer">
<strong>Understanding heat thresholds</strong> — apparent temperature (Steadman formula) is used throughout, as it incorporates humidity.
<div class="wb-threshold-row">
  <div class="wb-threshold" style="border-color:rgba(234,179,8,0.25)">
    <div class="wb-t-label">Caution</div>
    <div class="wb-t-temp" style="color:#b45309">32°C</div>
    <div class="wb-t-desc">Outdoor labour restricted. Fatigue & heat cramps likely. ILO rest mandates apply.</div>
  </div>
  <div class="wb-threshold" style="border-color:rgba(249,115,22,0.25)">
    <div class="wb-t-label">Danger</div>
    <div class="wb-t-temp" style="color:#c2410c">35°C</div>
    <div class="wb-t-desc">Our "heat stress day" threshold. Heat exhaustion likely without intervention.</div>
  </div>
  <div class="wb-threshold" style="border-color:rgba(220,38,38,0.30)">
    <div class="wb-t-label">Extreme Danger</div>
    <div class="wb-t-temp" style="color:#991b1b">38°C</div>
    <div class="wb-t-desc">Heat stroke imminent. Outdoor exposure for any duration is life-threatening.</div>
  </div>
  <div class="wb-threshold" style="border-color:rgba(127,29,29,0.35)">
    <div class="wb-t-label">Unsurvivable (wet-bulb)</div>
    <div class="wb-t-temp" style="color:#7f1d1d">35°C WB</div>
    <div class="wb-t-desc">Equivalent to ~46°C dry / 50% RH. Fatal within 6h even at rest in shade.</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)

    # ── TAB 2: City heat history ───────────────────────────────────────────────
    with tab2:
        c_city, c_info = st.columns([2, 1])
        with c_city:
            city_name = st.selectbox("Select city", ["— select a city —"] + sorted(CITY_LIST.keys()), key="city_05")

        if city_name == "— select a city —":
            st.markdown(
                '<div class="no-data-note" style="padding:24px 0;text-align:center;color:#a8a29e">'
                'Select a city above to view its heat stress history since 2000 and projections to 2050.</div>',
                unsafe_allow_html=True,
            )
        else:
            lat, lon = CITY_LIST[city_name]
            with st.spinner(f"Fetching heat data for {city_name}…"):
                city_data = load_city_heat(lat, lon)

            if not city_data or not city_data.get("heat_by_year"):
                st.warning("Could not load data for this city. Try another.")
            else:
                early_avg  = city_data["early_avg"]
                recent_avg = city_data["recent_avg"]
                slope      = city_data["slope"]
                peak_year  = city_data["peak_year"]
                peak_days  = city_data["peak_days"]
                change_pct = ((recent_avg - early_avg) / max(early_avg, 1)) * 100 if early_avg else 0

                # City KPI strip
                kpi_color = "#dc2626" if slope > 1 else "#f97316" if slope > 0.3 else "#16a34a"
                st.markdown(f"""<div class="strip-row" style="margin-bottom:12px">
  <div class="strip-card">
    <div class="strip-icon">📅</div>
    <div class="strip-n">{recent_avg:.0f}</div>
    <div class="strip-l">avg heat days/yr · 2016–2023</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">📈</div>
    <div class="strip-n" style="color:{kpi_color}">{slope:+.1f}</div>
    <div class="strip-l">days gained per year (trend)</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">🔥</div>
    <div class="strip-n">{peak_days}</div>
    <div class="strip-l">peak year · {peak_year}</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">⚡</div>
    <div class="strip-n" style="color:{kpi_color}">{change_pct:+.0f}%</div>
    <div class="strip-l">change vs. early 2000s baseline</div>
  </div>
</div>""", unsafe_allow_html=True)

                trend_fig = make_city_trend(city_data, city_name)
                st.plotly_chart(trend_fig, use_container_width=True)

                # Decade comparison callout
                if slope > 0.5:
                    st.markdown(
                        f'<div class="compound-risk" style="margin-top:8px">'
                        f'<div class="compound-risk-title">📈 Rising heat trend</div>'
                        f'<div class="compound-risk-body">{city_name} is gaining <strong>{slope:.1f} heat stress days per year</strong>. '
                        f'At this rate, by 2040 the city will face ~{recent_avg + slope*17:.0f} days/yr — '
                        f'a {(recent_avg + slope*17 - early_avg) / max(early_avg,1)*100:.0f}% increase from the early-2000s baseline. '
                        f'Workers, elderly residents, and outdoor crops face compounding exposure.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div class="method-note">Data: Open-Meteo ERA5-Land historical reanalysis. '
                    'Heat stress day = apparent temperature max > 35 °C (Steadman formula). '
                    'Labour-restricted day = apparent temperature max > 32 °C (ILO guideline). '
                    'Projections apply empirical sensitivity multipliers calibrated to CMIP6 SSP3-7.0.</div>',
                    unsafe_allow_html=True,
                )

    # ── TAB 3: Compound risk ───────────────────────────────────────────────────
    with tab3:
        st.markdown("""<div class="narrative-bar" style="margin-top:0">
  <div class="narrative-lede">Heat and water stress are the same crisis seen from two angles.</div>
  <div class="narrative-context">Countries that simultaneously face extreme heat <em>and</em> severe water stress sit at the epicentre of the coming agricultural polycrisis.
  Bubble size = share of workforce in agriculture — nations where these three factors overlap face economic disruption that cannot be absorbed through normal adaptation channels.</div>
</div>""", unsafe_allow_html=True)

        scatter_fig = make_compound_scatter(df, water_stress_raw)
        if scatter_fig.data:
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            st.info("Water stress data unavailable — check network connection.")

        # Day 03 cross-reference
        extreme_compound = [
            iso for iso, ws in water_stress_raw.items()
            if ws > 40 and HEAT_DATA.get(iso, 0) >= 80
        ]
        if extreme_compound:
            names_ec = [country_names.get(iso, iso) for iso in extreme_compound[:8]]
            st.markdown(
                f'<div class="wb-explainer" style="margin-top:8px">'
                f'<strong>Dual-crisis countries</strong> (water stress >40% AND heat stress ≥80 days/yr): '
                f'{", ".join(names_ec)}{"…" if len(extreme_compound) > 8 else ""}. '
                f'These {len(extreme_compound)} nations account for a disproportionate share of global food insecurity risk '
                f'(see Day 04 — Food Fragility for fragility scores).</div>',
                unsafe_allow_html=True,
            )

    # ── TAB 4: Labour & adaptation ─────────────────────────────────────────────
    with tab4:
        c_l, c_r = st.columns([3, 2])

        with c_l:
            scenario_label4 = st.select_slider(
                "Scenario for labour projection",
                options=list(TEMP_DELTAS.keys()),
                value="Today — current climate",
                key="scenario_labour_05",
            )
            delta_t4 = TEMP_DELTAS[scenario_label4]
            labour_fig = make_labour_chart(df, delta_t4, water_stress_raw)
            st.plotly_chart(labour_fig, use_container_width=True)
            st.markdown(
                '<div class="method-note">Labour loss estimate: heat_days × 2.7% hourly loss coefficient (ILO 2019) × '
                'agricultural workforce share. Does not account for informal sector heat adaptation or A/C penetration. '
                'GDP impact = directional indicator only.</div>',
                unsafe_allow_html=True,
            )

        with c_r:
            sel_label, sel_fg, _ = heat_band(selected_row["heat_days"])
            st.markdown(
                f'<div style="font-size:10px;color:var(--text-3);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">'
                f'Adaptation strategies — {selected_name} ({sel_label})</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_heat_tech_cards(sel_label), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
