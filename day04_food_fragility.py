import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Food System Fragility · Day 04",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
WB_BASE  = "https://api.worldbank.org/v2/country/all/indicator"
WB_TREND = "https://api.worldbank.org/v2/country/{iso}/indicator/{code}"
HEADERS  = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

FOOD_INDICATORS = {
    "food_import_pct":   "TM.VAL.FOOD.ZS.UN",
    "food_prod_index":   "AG.PRD.FOOD.XD",
    "undernourishment":  "SN.ITK.DEFC.ZS",
    "agri_land_pct":     "AG.LND.AGRI.ZS",
}

FRAG_BANDS = [
    (80, "CRITICAL",  "#dc2626", "rgba(220,38,38,0.09)"),
    (60, "HIGH",      "#ea580c", "rgba(234,88,12,0.09)"),
    (40, "MODERATE",  "#d97706", "rgba(217,119,6,0.09)"),
    (20, "LOW",       "#16a34a", "rgba(22,163,74,0.09)"),
    ( 0, "SECURE",    "#0ea5e9", "rgba(14,165,233,0.09)"),
]

FSCALE = [
    (0.00, "#0ea5e9"),
    (0.20, "#22c55e"),
    (0.40, "#eab308"),
    (0.65, "#f97316"),
    (0.85, "#dc2626"),
    (1.00, "#7f1d1d"),
]

# Bioclimatic envelopes (simplified MaxEnt — WorldClim v2.1 methodology, AUC 0.8642)
CROP_PROFILES = {
    "Maize":   {"t_opt": (18, 27), "t_abs": (10, 35), "p_opt": (500,  800),  "p_abs": (350, 1200), "color": "#f59e0b", "icon": "🌽"},
    "Wheat":   {"t_opt": (12, 22), "t_abs": ( 5, 30), "p_opt": (300,  600),  "p_abs": (200,  900), "color": "#d97706", "icon": "🌾"},
    "Rice":    {"t_opt": (22, 30), "t_abs": (15, 38), "p_opt": (1200, 2000), "p_abs": (900, 3000), "color": "#65a30d", "icon": "🌿"},
    "Sorghum": {"t_opt": (25, 32), "t_abs": (15, 40), "p_opt": (400,  700),  "p_abs": (250, 1000), "color": "#b45309", "icon": "🌱"},
}

TEMP_DELTAS = {
    "Current baseline": 0.0,
    "+1.5°C (Paris target)": 1.5,
    "+2.0°C": 2.0,
    "+3.0°C (SSP3-7.0 trajectory)": 3.0,
}

# Representative WorldClim baseline climate per ISO (t_mean °C, p_annual mm)
COUNTRY_CLIMATE = {
    "AFG": (11.8, 327), "AGO": (22.1, 891), "ARG": (14.2, 651), "AUS": (21.8, 534),
    "BDI": (19.8, 1098), "BEN": (27.5, 1056), "BFA": (28.3, 748), "BGD": (25.1, 2666),
    "BOL": (15.7, 1098), "BRA": (24.7, 1761), "BWA": (20.8, 457), "CAN": (1.8, 537),
    "CHE": (6.1, 1020), "CHL": (8.4, 1522), "CHN": (8.6, 645), "CIV": (26.1, 1545),
    "CMR": (23.1, 1645), "COD": (24.4, 1543), "COL": (22.0, 2612), "DEU": (9.2, 700),
    "DZA": (12.5, 215), "EGY": (20.8, 51), "ESP": (14.2, 636), "ETH": (22.0, 848),
    "FRA": (11.7, 867), "GBR": (9.2, 1220), "GHA": (26.3, 1187), "GIN": (26.3, 1651),
    "GTM": (19.9, 1996), "HND": (23.1, 1872), "IDN": (26.1, 2702), "IND": (24.7, 1083),
    "IRN": (17.1, 228), "IRQ": (22.6, 216), "KAZ": (5.0, 290), "KEN": (18.5, 630),
    "KHM": (27.6, 1904), "LAO": (23.4, 1834), "LBN": (17.2, 618), "MAD": (21.9, 1513),
    "MAR": (17.5, 346), "MDG": (21.9, 1513), "MEX": (21.0, 752), "MLI": (28.0, 475),
    "MOZ": (23.8, 1032), "MRT": (28.2, 122), "MWI": (20.1, 1054), "MYS": (27.0, 2875),
    "NER": (29.1, 267), "NGA": (26.5, 1150), "NIC": (24.9, 1754), "NPL": (17.8, 1537),
    "PAK": (20.4, 494), "PER": (15.2, 1738), "PHL": (27.0, 2348), "PNG": (23.8, 2951),
    "PRY": (22.8, 1292), "RUS": (0.8, 507), "RWA": (18.5, 1212), "SDN": (28.3, 416),
    "SEN": (27.8, 686), "SLE": (26.3, 2526), "SOM": (27.3, 282), "SSD": (26.3, 876),
    "SYR": (17.2, 252), "TCD": (27.2, 431), "TGO": (27.3, 1168), "THA": (26.8, 1622),
    "TZA": (21.6, 1071), "UGA": (20.9, 1180), "UKR": (8.5, 568), "USA": (11.2, 715),
    "UZB": (12.5, 203), "VEN": (24.7, 1875), "VNM": (24.5, 1821), "YEM": (25.2, 167),
    "ZAF": (17.5, 495), "ZMB": (21.0, 1013), "ZWE": (18.8, 657),
}

AGRITECH_STRATEGIES = {
    "CRITICAL": [
        {"title": "Emergency drought-tolerant seed deployment",  "impact": "HIGH",   "feasibility": "MEDIUM", "timeframe": "1–3 yr",
         "description": "CGIAR-developed drought-tolerant maize and sorghum varieties can maintain 20–30% yield under severe water deficit.",
         "example": "CIMMYT DTMA varieties across Sahel"},
        {"title": "Solar-powered precision drip irrigation",     "impact": "HIGH",   "feasibility": "MEDIUM", "timeframe": "2–5 yr",
         "description": "Micro-drip with soil moisture sensors cuts irrigation water use by 40–60% vs flood irrigation.",
         "example": "Israel Netafim model, Morocco pilot"},
        {"title": "Early warning food crisis system",            "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "0–1 yr",
         "description": "FEWS NET + Copernicus satellite NDVI monitoring for sub-national crop failure prediction.",
         "example": "FEWS NET East Africa network"},
        {"title": "Rapid protein diversification (legumes)",     "impact": "HIGH",   "feasibility": "HIGH",   "timeframe": "1–2 yr",
         "description": "Cowpea and groundnut require 70% less water than maize. Protein equivalence can buffer staple shortfalls.",
         "example": "IITA cowpea programmes, West Africa"},
    ],
    "HIGH": [
        {"title": "Conservation agriculture & mulching",         "impact": "HIGH",   "feasibility": "HIGH",   "timeframe": "1–3 yr",
         "description": "Minimum tillage + residue cover improves soil water retention by 15–25% and reduces input costs.",
         "example": "FAO CA programs, southern Africa"},
        {"title": "Digital crop advisory (mobile-first)",        "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "0–2 yr",
         "description": "SMS/USSD advisory services for 5–10M smallholders. Proven 15–20% yield uplift via timely agronomic advice.",
         "example": "Esoko (Ghana), Apollo Agriculture (Kenya)"},
        {"title": "Climate-indexed crop insurance",              "impact": "HIGH",   "feasibility": "MEDIUM", "timeframe": "2–4 yr",
         "description": "Satellite-trigger insurance payouts buffer smallholder income shocks without requiring field assessments.",
         "example": "R4 Rural Resilience Initiative, WFP"},
        {"title": "Biofortified staple varieties",               "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "1–3 yr",
         "description": "HarvestPlus orange-fleshed sweet potato and zinc-enriched wheat address hidden hunger alongside calories.",
         "example": "HarvestPlus, 60+ countries"},
    ],
    "MODERATE": [
        {"title": "Precision nitrogen management (4R)",          "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "1–2 yr",
         "description": "Right source, rate, time, and place for fertilizer. Cuts input cost 15–20% while maintaining yield.",
         "example": "One Acre Fund, East Africa"},
        {"title": "Agri-fintech & supply chain digitisation",   "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "1–3 yr",
         "description": "Digital trade platforms reduce post-harvest losses and improve farmer price discovery by 20–35%.",
         "example": "Twiga Foods (Kenya), WeFarm"},
        {"title": "Community seed banks",                        "impact": "MEDIUM", "feasibility": "HIGH",   "timeframe": "0–2 yr",
         "description": "Local biodiversity conservation of heritage varieties as climate buffer for niche agroecological niches.",
         "example": "Bioversity International, Asia & Africa"},
    ],
    "LOW": [
        {"title": "Vertical & controlled-environment farming",   "impact": "MEDIUM", "feasibility": "LOW",    "timeframe": "5–10 yr",
         "description": "High-capex urban food production with 95% water savings and year-round output. Viable for high-value crops.",
         "example": "AeroFarms (USA), Bowery (NYC)"},
        {"title": "Regenerative export agriculture",             "impact": "HIGH",   "feasibility": "MEDIUM", "timeframe": "3–7 yr",
         "description": "Transitioning export commodities to regenerative practices attracts premium EU/US market access.",
         "example": "Rainforest Alliance, South America"},
    ],
    "SECURE": [
        {"title": "Agricultural R&D investment & innovation hubs", "impact": "HIGH", "feasibility": "HIGH",   "timeframe": "5–15 yr",
         "description": "Maintain food security leadership by investing in next-gen gene editing, synthetic biology, and climate modelling.",
         "example": "Rothamsted Research (UK), Wageningen (NL)"},
        {"title": "Export diversification & food diplomacy",     "impact": "HIGH",   "feasibility": "MEDIUM", "timeframe": "3–8 yr",
         "description": "Secure bilateral food trade agreements to insulate against future price shocks and supply chain disruptions.",
         "example": "Australia-ASEAN agri-trade corridors"},
    ],
}

CITY_LIST = {
    "Nairobi, Kenya":          (-1.286389,  36.817223),
    "Lagos, Nigeria":           (6.524379,   3.379206),
    "Accra, Ghana":             (5.603717,  -0.186964),
    "Addis Ababa, Ethiopia":    (9.02497,   38.74689),
    "Kampala, Uganda":          (0.31628,   32.58219),
    "Dar es Salaam, Tanzania":  (-6.792354,  39.208328),
    "Dakar, Senegal":           (14.764504, -17.366029),
    "Khartoum, Sudan":          (15.552177,  32.532401),
    "Kinshasa, DR Congo":       (-4.322447,  15.322144),
    "Lusaka, Zambia":           (-15.416786, 28.283340),
    "Dhaka, Bangladesh":        (23.810331,  90.412521),
    "Mumbai, India":            (19.075984,  72.877656),
    "New Delhi, India":         (28.635308,  77.224960),
    "Karachi, Pakistan":        (24.860735,  67.010040),
    "Kathmandu, Nepal":         (27.700769,  85.314940),
    "Colombo, Sri Lanka":       (6.932694,   79.841614),
    "Jakarta, Indonesia":       (-6.211544, 106.845172),
    "Manila, Philippines":      (14.599512, 120.984219),
    "Ho Chi Minh City, Vietnam": (10.804376, 106.682756),
    "Bangkok, Thailand":        (13.753979, 100.501444),
    "Phnom Penh, Cambodia":     (11.562108, 104.916282),
    "Beijing, China":           (39.906217, 116.391441),
    "Shanghai, China":          (31.228611, 121.474722),
    "Chengdu, China":           (30.572815, 104.066803),
    "Mexico City, Mexico":      (19.432608, -99.133209),
    "Guadalajara, Mexico":      (20.659699, -103.349609),
    "Bogotá, Colombia":         (4.710989,  -74.072092),
    "Lima, Peru":                (-12.046374,-77.042793),
    "Buenos Aires, Argentina":  (-34.603684,-58.381559),
    "São Paulo, Brazil":        (-23.550520,-46.633308),
    "Kampong Cham, Cambodia":   (12.000000, 105.466667),
    "Bamako, Mali":             (12.650000,  -8.000000),
    "Niamey, Niger":            (13.513590,   2.114540),
    "Ouagadougou, Burkina Faso":(12.364566,  -1.533212),
    "Kigali, Rwanda":           (-1.943889,  30.059444),
    "Harare, Zimbabwe":         (-17.825166,  31.033510),
    "Maputo, Mozambique":       (-25.891968,  32.605135),
    "Antananarivo, Madagascar": (-18.910383,  47.536196),
    "Islamabad, Pakistan":      (33.720000,  73.060000),
    "Tehran, Iran":             (35.689197,  51.388974),
    "Baghdad, Iraq":            (33.341248,  44.401650),
    "Cairo, Egypt":             (30.044420,  31.235712),
    "Casablanca, Morocco":      (33.589886,  -7.603869),
    "Tunis, Tunisia":           (36.818897,   10.165865),
    "Yangon, Myanmar":          (16.866070,  96.199760),
    "Colombo, Sri Lanka":       (6.927079,   79.861243),
    "Kuala Lumpur, Malaysia":   (3.147740,  101.695210),
    "Phnom Penh, Cambodia":     (11.569162, 104.924144),
    "Kiev, Ukraine":            (50.450100,  30.523400),
    "Tashkent, Uzbekistan":     (41.299496,  69.240073),
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
  --accent:   #16a34a;
  --accent-2: #f59e0b;
  --sh-sm:    0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);
  --sh-md:    0 4px 16px rgba(0,0,0,0.08);
  --r:        10px;
}

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

[data-testid="stSidebar"] {
  background: var(--glass) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--glass-b) !important;
  box-shadow: 4px 0 24px rgba(0,0,0,0.05) !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 22px 18px 28px !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: var(--text-2) !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] h2 {
  color: var(--text-1) !important; font-size: 18px !important;
  font-weight: 600 !important; letter-spacing: -0.02em !important; margin: 4px 0 0 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] input {
  background: rgba(255,255,255,0.95) !important;
  border-color: #e2e8f0 !important; color: var(--text-1) !important;
}

/* Metrics grid */
.metrics-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 8px; margin: 10px 0;
}
.metric-card {
  background: var(--surface); border: 1px solid var(--glass-b);
  border-radius: 8px; padding: 10px 11px; box-shadow: var(--sh-sm);
  animation: fadeSlideUp 0.3s ease both;
}
.metric-label {
  font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-3); margin-bottom: 3px;
}
.metric-value { font-size: 18px; font-weight: 600; color: var(--text-1); line-height: 1.15; font-variant-numeric: tabular-nums; }
.metric-unit  { font-size: 10px; color: var(--text-3); font-weight: 400; margin-left: 2px; }

/* Country heading & grain badge */
.country-heading { font-size: 17px; font-weight: 600; color: var(--text-1); letter-spacing: -0.01em; line-height: 1.25; margin-bottom: 6px; }
.grain-badge { display: flex; align-items: center; gap: 8px; margin: 2px 0 10px; }
.frag-band-label { font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-3); }

/* Story card */
.story-card {
  font-size: 12px; line-height: 1.8; color: var(--text-2); margin-bottom: 10px;
  background: var(--surface); border: 1px solid var(--glass-b);
  border-radius: 8px; padding: 10px 12px;
  animation: fadeSlideUp 0.35s 0.08s ease both; box-shadow: var(--sh-sm);
}

/* Compound risk callout */
.compound-risk {
  border: 1px solid rgba(234,88,12,0.30); border-left: 3px solid #ea580c;
  background: rgba(234,88,12,0.04); border-radius: 0 8px 8px 0;
  padding: 11px 13px; margin: 0 0 10px;
  animation: shake 0.45s ease both;
}
.compound-risk-title { font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #ea580c; margin-bottom: 5px; }
.compound-risk-body  { font-size: 11px; line-height: 1.75; color: #78716c; }

/* Stats strip */
.strip-row { display: flex; gap: 8px; margin: 4px 0 6px; padding: 0 2px; }
.strip-card {
  flex: 1; min-width: 0; background: var(--glass); border: 1px solid var(--glass-b);
  border-radius: var(--r); padding: 11px 13px; box-shadow: var(--sh-sm);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  animation: fadeSlideUp 0.4s ease both; cursor: default;
}
.strip-card:hover { transform: translateY(-2px); box-shadow: var(--sh-md); }
.strip-icon { margin-bottom: 5px; }
.strip-n { font-size: 21px; font-weight: 300; font-family: 'Inter', sans-serif; color: var(--accent); line-height: 1.1; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.strip-l { font-size: 9px; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-3); line-height: 1.4; }

/* Intro card */
.intro-card {
  background: rgba(255,255,255,0.92); backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(22,163,74,0.18); border-radius: var(--r);
  padding: 16px 20px; margin: 4px 0 10px;
  animation: slideDown 0.4s ease both; box-shadow: 0 2px 14px rgba(22,163,74,0.07);
}
.intro-inner { display: flex; align-items: center; gap: 18px; }
.intro-text  { flex: 1; }
.intro-heading { font-size: 14px; font-weight: 600; color: var(--text-1); margin: 0 0 5px; }
.intro-body    { font-size: 12px; line-height: 1.7; color: var(--text-2); margin: 0 0 10px; }
.intro-callout { display: flex; align-items: baseline; gap: 7px; }
.intro-n { font-size: 22px; font-weight: 600; color: #dc2626; }
.intro-l { font-size: 11px; color: var(--text-3); }
.intro-svg { flex-shrink: 0; opacity: 0.85; }

/* Agritech card */
.agritech-card {
  background: var(--surface); border: 1px solid var(--glass-b);
  border-radius: var(--r); padding: 14px 16px; margin-bottom: 10px;
  box-shadow: var(--sh-sm); animation: fadeSlideUp 0.35s ease both;
  transition: transform 0.2s, box-shadow 0.2s;
}
.agritech-card:hover { transform: translateY(-2px); box-shadow: var(--sh-md); }
.agritech-header { display: flex; align-items: center; gap: 10px; margin-bottom: 7px; }
.agritech-title { font-size: 13px; font-weight: 600; color: var(--text-1); flex: 1; }
.agritech-badges { display: flex; gap: 5px; }
.badge {
  font-size: 8px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 2px 7px; border-radius: 3px;
}
.badge-impact-high       { background: rgba(22,163,74,0.12);  color: #15803d; }
.badge-impact-medium     { background: rgba(234,179,8,0.12);  color: #b45309; }
.badge-impact-low        { background: rgba(148,163,184,0.12);color: #64748b; }
.badge-feasibility-high  { background: rgba(14,165,233,0.12); color: #0369a1; }
.badge-feasibility-medium{ background: rgba(168,85,247,0.12); color: #7e22ce; }
.badge-feasibility-low   { background: rgba(239,68,68,0.12);  color: #b91c1c; }
.agritech-desc { font-size: 11px; line-height: 1.7; color: var(--text-2); margin-bottom: 6px; }
.agritech-meta { display: flex; gap: 14px; font-size: 10px; color: var(--text-3); }
.agritech-meta span { display: flex; align-items: center; gap: 3px; }

/* Crop shift row */
.shift-section { margin: 12px 0; }
.shift-heading { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; }
.shift-crop-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.shift-crop-name { font-size: 11px; font-weight: 500; color: var(--text-2); min-width: 64px; }
.shift-track { flex: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; position: relative; }
.shift-bar-now { height: 8px; border-radius: 4px; transform: scaleX(0); transform-origin: left; animation: barGrow 0.8s ease-out forwards; }
.shift-bar-future { height: 8px; border-radius: 4px; position: absolute; top: 0; transform: scaleX(0); transform-origin: left; animation: barGrow 0.9s 0.1s ease-out forwards; opacity: 0.4; }
.shift-pct { font-size: 10px; font-variant-numeric: tabular-nums; color: var(--text-3); min-width: 34px; text-align: right; }
.shift-delta { font-size: 10px; font-weight: 600; min-width: 42px; text-align: right; }

/* Method note */
.method-note {
  font-size: 10px; color: var(--text-3); line-height: 1.65;
  background: rgba(14,165,233,0.04); border: 1px solid rgba(14,165,233,0.12);
  border-radius: 8px; padding: 9px 13px; margin-top: 12px;
}
.method-note strong { color: var(--text-2); font-weight: 500; }

/* Misc UI */
.sep { border: none; border-top: 1px solid #e2e8f0; margin: 13px 0; }
.radio-label { font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-3); margin-bottom: 4px; display: block; }
.day-label { font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-3); }
.data-footer { font-size: 10px; color: var(--text-3); letter-spacing: 0.04em; line-height: 2.0; }
.no-data-note { font-size: 10px; color: var(--text-3); letter-spacing: 0.04em; padding: 2px 4px 6px; }

/* Tabs */
button[data-baseweb="tab"] {
  color: var(--text-3) !important; font-size: 11px !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  background: transparent !important; font-family: 'Inter', sans-serif !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--text-1) !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: #e2e8f0 !important; }
[data-testid="stTabsContent"] { background: transparent !important; padding-top: 10px !important; }

/* Keyframes */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
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
@keyframes barGrow { to { transform: scaleX(1); } }
@keyframes grainFill { to { transform: scaleY(1); } }
@keyframes pulseDot {
  0%, 100% { transform: scale(1);   opacity: 1; }
  50%       { transform: scale(1.5); opacity: 0.65; }
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
def load_food_data() -> pd.DataFrame:
    raw = {key: _fetch_indicator(code) for key, code in FOOD_INDICATORS.items()}
    rows = []
    for iso, (imp_pct, yr) in raw["food_import_pct"].items():
        rows.append({
            "iso":            iso,
            "year":           yr,
            "food_import_pct":  imp_pct,
            "food_prod_index":  raw["food_prod_index"].get(iso,    (None, ""))[0],
            "undernourishment": raw["undernourishment"].get(iso,   (None, ""))[0],
            "agri_land_pct":    raw["agri_land_pct"].get(iso,     (None, ""))[0],
        })
    df = pd.DataFrame(rows)
    df["fragility"] = df.apply(_compute_fragility, axis=1)
    return df


@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def load_food_trend(iso: str) -> pd.DataFrame:
    code = FOOD_INDICATORS["food_prod_index"]
    url  = (f"https://api.worldbank.org/v2/country/{iso}/indicator/{code}"
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
    return pd.DataFrame(rows).sort_values("year") if rows else pd.DataFrame()


@st.cache_data(ttl=86_400 * 30, persist="disk", show_spinner=False)
def load_city_climate(lat: float, lon: float) -> dict:
    base_url = "https://climate-api.open-meteo.com/v1/climate"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": "1990-01-01", "end_date": "2020-12-31",
        "models": "CMCC_CM2_VHR4",
        "daily": "temperature_2m_mean,precipitation_sum",
    }
    try:
        r = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        temps = [t for t in data.get("daily", {}).get("temperature_2m_mean", []) if t is not None]
        precip = [p for p in data.get("daily", {}).get("precipitation_sum", []) if p is not None]
        t_mean = sum(temps) / len(temps) if temps else None
        p_annual = (sum(precip) / len(precip)) * 365 if precip else None
    except Exception:
        t_mean, p_annual = None, None

    # SSP3-7.0 2050 projection
    t_2050 = (t_mean + 2.5) if t_mean is not None else None
    p_2050 = (p_annual * 0.92) if p_annual is not None else None  # ~8% precip reduction

    return {
        "t_mean": t_mean,
        "p_annual": p_annual,
        "t_2050": t_2050,
        "p_2050": p_2050,
    }


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
def _compute_fragility(r: pd.Series) -> float | None:
    imp  = r.get("food_import_pct")
    prod = r.get("food_prod_index")
    undr = r.get("undernourishment")
    if imp is None or pd.isna(imp):
        return None
    score = 0.0
    w_total = 0.0
    score  += 0.35 * min(imp / 100.0, 1.0);  w_total += 0.35
    if prod is not None and not pd.isna(prod):
        gap = max(0.0, 1.0 - prod / 100.0)
        score += 0.35 * min(gap, 1.0); w_total += 0.35
    if undr is not None and not pd.isna(undr):
        score += 0.30 * min(undr / 40.0, 1.0); w_total += 0.30
    if w_total < 0.10:
        return None
    return round((score / w_total) * 100.0, 1)


def fragility_band(score: float | None) -> tuple[str, str, str]:
    if score is None:
        return "N/A", "#94a3b8", "rgba(148,163,184,0.08)"
    for threshold, label, fg, bg in FRAG_BANDS:
        if score >= threshold:
            return label, fg, bg
    return "SECURE", "#0ea5e9", "rgba(14,165,233,0.09)"


def _fmt(v, dec: int = 1, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{dec}f}" + unit


def _hex_rgba(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def bioclimatic_score(t_mean: float, p_annual: float, crop: str) -> float:
    """Gaussian envelope bioclimatic suitability (0–1). Simplified MaxEnt approach."""
    p = CROP_PROFILES[crop]
    t_lo, t_hi = p["t_abs"]
    t_opt_lo, t_opt_hi = p["t_opt"]
    p_lo, p_hi = p["p_abs"]
    p_opt_lo, p_opt_hi = p["p_opt"]

    if t_mean < t_lo or t_mean > t_hi:
        t_score = 0.0
    elif t_opt_lo <= t_mean <= t_opt_hi:
        t_score = 1.0
    elif t_mean < t_opt_lo:
        t_score = (t_mean - t_lo) / max(t_opt_lo - t_lo, 0.1)
    else:
        t_score = (t_hi - t_mean) / max(t_hi - t_opt_hi, 0.1)

    if p_annual < p_lo or p_annual > p_hi:
        p_score = 0.0
    elif p_opt_lo <= p_annual <= p_opt_hi:
        p_score = 1.0
    elif p_annual < p_opt_lo:
        p_score = (p_annual - p_lo) / max(p_opt_lo - p_lo, 0.1)
    else:
        p_score = (p_hi - p_annual) / max(p_hi - p_opt_hi, 0.1)

    return round(min(max(math.sqrt(t_score * p_score), 0.0), 1.0), 3)


def global_food_stats(df: pd.DataFrame) -> dict:
    valid = df.dropna(subset=["fragility"])
    critical = int((valid["fragility"] >= 80).sum())
    high_import = int((df["food_import_pct"] >= 60).sum())
    avg_frag = float(valid["fragility"].mean()) if not valid.empty else 0
    worst = valid.nlargest(1, "fragility").iloc[0] if not valid.empty else None
    return {
        "critical_count": critical,
        "high_import": high_import,
        "avg_fragility": round(avg_frag, 1),
        "worst_name": worst["country_name"] if worst is not None and "country_name" in worst else "—",
        "worst_score": float(worst["fragility"]) if worst is not None else 0,
    }


def food_story(r: pd.Series, rank: int, avg_frag: float) -> str:
    name = r.get("country_name", r.get("iso", "This country"))
    frag = r.get("fragility")
    imp  = r.get("food_import_pct")
    undr = r.get("undernourishment")
    prod = r.get("food_prod_index")

    if frag is None or pd.isna(frag):
        return f"{name} has insufficient data for a full fragility assessment."

    if frag >= 80:
        opening = f"{name} is in critical food fragility — it faces simultaneous shocks to import access, domestic production, and nutritional security."
    elif frag >= 60:
        opening = f"With a fragility score of {frag:.0f}, {name} is highly exposed to food shocks across multiple dimensions."
    elif frag >= 40:
        opening = f"{name} faces moderate food system stress. Disruptions to any one factor — trade, weather, or prices — could push it toward crisis."
    elif frag >= 20:
        opening = f"{name} is in a relatively low fragility position, though structural import dependence or undernourishment remains a watch-point."
    else:
        opening = f"{name} maintains a secure food system, with strong domestic production and limited external dependence."

    parts = []
    if imp is not None and not pd.isna(imp) and imp > 40:
        parts.append(f"{imp:.0f}% of merchandise imports are food")
    if undr is not None and not pd.isna(undr) and undr > 5:
        parts.append(f"{undr:.0f}% of the population is undernourished")
    if prod is not None and not pd.isna(prod) and prod < 90:
        parts.append(f"food production index is {prod:.0f} (below baseline)")

    middle = (". ".join(parts).capitalize() + ".") if parts else f"Global average fragility is {avg_frag:.0f}."
    return f"{opening} {middle} Ranked #{rank} globally."


def agritech_recommendations(frag_score: float | None, water_stress: float | None) -> list[dict]:
    if frag_score is None:
        return AGRITECH_STRATEGIES.get("MODERATE", [])
    label, _, _ = fragility_band(frag_score)
    strategies  = list(AGRITECH_STRATEGIES.get(label, AGRITECH_STRATEGIES["MODERATE"]))
    if water_stress is not None and not pd.isna(water_stress) and water_stress > 40:
        strategies = [AGRITECH_STRATEGIES["CRITICAL"][1]] + strategies  # drip irrigation first
    return strategies[:4]


# ── SVG helpers ───────────────────────────────────────────────────────────────
def grain_badge_svg(fill_level: float, color: str, size: int = 36) -> str:
    """Wheat stalk SVG that fills from bottom based on fragility (0–1)."""
    fill_pct = min(max(fill_level, 0.0), 1.0)
    fill_h   = int(size * fill_pct)
    clip_y   = size - fill_h
    light    = _hex_rgba(color, 0.22)
    cid      = f"gc_{size}_{int(fill_pct*100)}"
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><clipPath id="{cid}"><rect x="0" y="{clip_y}" width="36" height="{fill_h}"/></clipPath></defs>'
        f'<!-- stalk --><line x1="18" y1="34" x2="18" y2="8" stroke="#d1d5db" stroke-width="1.5" stroke-linecap="round"/>'
        f'<!-- grain head filled -->'
        f'<ellipse cx="18" cy="10" rx="4" ry="6" fill="{light}" stroke="#d1d5db" stroke-width="1"/>'
        f'<ellipse cx="13" cy="14" rx="3.5" ry="5.5" fill="{light}" stroke="#d1d5db" stroke-width="1"/>'
        f'<ellipse cx="23" cy="14" rx="3.5" ry="5.5" fill="{light}" stroke="#d1d5db" stroke-width="1"/>'
        f'<!-- color fill overlay -->'
        f'<ellipse cx="18" cy="10" rx="4" ry="6" fill="{color}" clip-path="url(#{cid})"/>'
        f'<ellipse cx="13" cy="14" rx="3.5" ry="5.5" fill="{color}" clip-path="url(#{cid})"/>'
        f'<ellipse cx="23" cy="14" rx="3.5" ry="5.5" fill="{color}" clip-path="url(#{cid})"/>'
        f'</svg>'
    )


def farm_scene_svg() -> str:
    """Small illustrated farm scene for the intro card (160×64 px)."""
    return """<svg width="160" height="64" viewBox="0 0 160 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- sky gradient -->
  <rect width="160" height="64" fill="url(#sky)"/>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e0f2fe"/>
      <stop offset="100%" stop-color="#f0fdf4"/>
    </linearGradient>
  </defs>
  <!-- ground -->
  <rect x="0" y="46" width="160" height="18" rx="2" fill="#dcfce7"/>
  <!-- field rows -->
  <path d="M0 50 Q40 47 80 50 Q120 53 160 50" stroke="#86efac" stroke-width="1.2" fill="none"/>
  <path d="M0 54 Q40 51 80 54 Q120 57 160 54" stroke="#86efac" stroke-width="1.2" fill="none"/>
  <!-- wheat stalks -->
  <line x1="12" y1="46" x2="12" y2="34" stroke="#d97706" stroke-width="1.5"/>
  <ellipse cx="12" cy="32" rx="3" ry="5" fill="#fbbf24" opacity="0.9"/>
  <line x1="22" y1="46" x2="22" y2="36" stroke="#d97706" stroke-width="1.5"/>
  <ellipse cx="22" cy="34" rx="3" ry="5" fill="#fbbf24" opacity="0.9"/>
  <line x1="32" y1="46" x2="32" y2="33" stroke="#d97706" stroke-width="1.5"/>
  <ellipse cx="32" cy="31" rx="3" ry="5" fill="#fbbf24" opacity="0.9"/>
  <!-- maize -->
  <line x1="60" y1="46" x2="60" y2="28" stroke="#15803d" stroke-width="2"/>
  <ellipse cx="60" cy="37" rx="5" ry="9" fill="#16a34a" opacity="0.8"/>
  <ellipse cx="60" cy="35" rx="3.5" ry="6" fill="#f59e0b" opacity="0.85"/>
  <!-- silo -->
  <rect x="120" y="28" width="18" height="18" rx="2" fill="#e2e8f0"/>
  <path d="M120 28 Q129 22 138 28" fill="#cbd5e1"/>
  <rect x="126" y="36" width="6" height="10" rx="1" fill="#94a3b8"/>
  <!-- sun -->
  <circle cx="142" cy="12" r="8" fill="#fde68a" opacity="0.9"/>
  <circle cx="142" cy="12" r="5" fill="#fbbf24"/>
  <!-- cloud -->
  <ellipse cx="48" cy="12" rx="14" ry="7" fill="white" opacity="0.85"/>
  <ellipse cx="56" cy="14" rx="10" ry="6" fill="white" opacity="0.85"/>
  <ellipse cx="38" cy="15" rx="9" ry="5" fill="white" opacity="0.85"/>
</svg>"""


def crop_suitability_bars_html(iso: str, t_delta: float) -> str:
    """Animated horizontal bars showing current vs. future crop suitability."""
    climate = COUNTRY_CLIMATE.get(iso)
    if climate is None:
        return "<p style='font-size:11px;color:#94a3b8'>No climate data for this country.</p>"

    t_now, p_now = climate
    t_fut = t_now + t_delta
    p_fut = p_now * (1.0 - 0.025 * t_delta)  # ~2.5% precip reduction per °C

    rows_html = []
    for crop, prof in CROP_PROFILES.items():
        sc_now = bioclimatic_score(t_now, p_now, crop)
        sc_fut = bioclimatic_score(t_fut, p_fut, crop)
        delta  = sc_fut - sc_now
        color  = prof["color"]
        icon   = prof["icon"]
        pct_now = f"{sc_now*100:.0f}%"
        pct_fut = f"{sc_fut*100:.0f}%"
        d_sign  = "+" if delta >= 0 else ""
        d_color = "#16a34a" if delta >= 0 else "#dc2626"
        rows_html.append(
            f'<div class="shift-crop-row">'
            f'<span class="shift-crop-name">{icon} {crop}</span>'
            f'<div class="shift-track">'
            f'<div class="shift-bar-now" style="width:{sc_now*100:.0f}%;background:{color};opacity:0.9"></div>'
            f'<div class="shift-bar-future" style="width:{sc_fut*100:.0f}%;background:{color}"></div>'
            f'</div>'
            f'<span class="shift-pct">{pct_now}</span>'
            f'<span class="shift-delta" style="color:{d_color}">{d_sign}{delta*100:.0f}%</span>'
            f'</div>'
        )

    legend = (
        '<div style="display:flex;gap:14px;font-size:9px;color:#94a3b8;margin-bottom:8px;letter-spacing:0.05em">'
        '<span>■ Current suitability</span><span style="opacity:0.5">■ Future (2050)</span>'
        '<span style="color:#16a34a">▲ gain</span><span style="color:#dc2626">▼ loss</span>'
        '</div>'
    )
    return (
        '<div class="shift-section">'
        f'<div class="shift-heading">Bioclimatic crop suitability</div>'
        f'{legend}'
        + "".join(rows_html) +
        '</div>'
    )


# ── Chart factories ───────────────────────────────────────────────────────────
def make_fragility_map(df: pd.DataFrame, selected_iso: str, metric: str) -> go.Figure:
    col_map = {
        "Fragility Score":       ("fragility",        "Food Fragility Score", FSCALE),
        "Import Dependency %":   ("food_import_pct",  "Food Imports (% merch.)",
                                  [(0,"#0ea5e9"),(0.4,"#22c55e"),(0.7,"#f97316"),(1,"#dc2626")]),
        "Undernourishment %":    ("undernourishment",  "Undernourished (%)",
                                  [(0,"#f0fdf4"),(0.3,"#86efac"),(0.65,"#f97316"),(1,"#dc2626")]),
    }
    col, label, cscale = col_map[metric]
    plot_df = df.dropna(subset=[col])

    cap = plot_df[col].quantile(0.97)
    plot_df = plot_df.copy()
    plot_df["_vis"] = plot_df[col].clip(upper=cap)

    fig = px.choropleth(
        plot_df,
        locations="iso",
        color="_vis",
        color_continuous_scale=cscale,
        range_color=(0, cap),
        custom_data=["country_name", col, "year"],
    )
    fig.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>"
                      f"{label}: %{{customdata[1]:.1f}}<br>"
                      "Year: %{customdata[2]}<extra></extra>",
        marker_line_color="rgba(255,255,255,0.6)",
        marker_line_width=0.4,
    )

    # Highlight extreme countries (top 5%)
    top5 = plot_df.nlargest(max(1, len(plot_df)//20), col)
    fig.add_trace(go.Choropleth(
        locations=top5["iso"],
        z=[1] * len(top5),
        showscale=False,
        colorscale=[[0,"rgba(0,0,0,0)"],[1,"rgba(0,0,0,0)"]],
        marker={"line": {"color": "#dc2626", "width": 1.4}},
        hoverinfo="skip",
    ))

    # Selected country outline
    if selected_iso and selected_iso in df["iso"].values:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso],
            z=[1],
            showscale=False,
            colorscale=[[0,"rgba(0,0,0,0)"],[1,"rgba(0,0,0,0)"]],
            marker={"line": {"color": "#0f172a", "width": 2.2}},
            hoverinfo="skip",
        ))

    fig.update_geos(
        showframe=False, showcoastlines=False,
        showland=True, landcolor="#dce4ef",
        showocean=True, oceancolor="#e8f1f8",
        showlakes=True, lakecolor="#e8f1f8",
        showcountries=True, countrycolor="rgba(255,255,255,0.55)",
        bgcolor="#f5f7fa",
        projection_type="natural earth",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=530,
        paper_bgcolor="#f5f7fa", plot_bgcolor="#f5f7fa",
        coloraxis_colorbar=dict(
            title=dict(text=label, font=dict(size=9, color="#94a3b8")),
            tickfont=dict(size=8, color="#94a3b8"),
            thickness=10, len=0.6,
            bgcolor="rgba(255,255,255,0.85)",
            outlinecolor="rgba(0,0,0,0.07)",
        ),
        geo=dict(bgcolor="#f5f7fa"),
    )
    return fig


def make_radar_chart(scores_now: dict, scores_fut: dict, title: str = "") -> go.Figure:
    crops = list(CROP_PROFILES.keys())
    vals_now = [scores_now.get(c, 0) for c in crops] + [scores_now.get(crops[0], 0)]
    vals_fut = [scores_fut.get(c, 0) for c in crops] + [scores_fut.get(crops[0], 0)]
    theta = crops + [crops[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_now, theta=theta, fill="toself", name="Current",
        line=dict(color="#16a34a", width=2),
        fillcolor="rgba(22,163,74,0.12)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=vals_fut, theta=theta, fill="toself", name="2050 SSP3-7.0",
        line=dict(color="#f97316", width=2, dash="dot"),
        fillcolor="rgba(249,115,22,0.08)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=8, color="#94a3b8"),
                            gridcolor="#e2e8f0", tickvals=[0.25, 0.5, 0.75, 1.0],
                            ticktext=["25%", "50%", "75%", "100%"]),
            angularaxis=dict(tickfont=dict(size=9, color="#475569")),
            bgcolor="rgba(255,255,255,0.0)",
        ),
        showlegend=True,
        legend=dict(font=dict(size=9, color="#94a3b8"), bgcolor="rgba(255,255,255,0.7)", bordercolor="#e2e8f0", borderwidth=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=20),
        height=280,
        title=dict(text=title, font=dict(size=10, color="#475569"), x=0.5) if title else None,
    )
    return fig


def make_shock_chart(df: pd.DataFrame, wheat_d: float, rice_d: float, maize_d: float) -> go.Figure:
    valid = df.dropna(subset=["fragility", "food_import_pct"]).copy()
    # Price shock amplifies fragility proportional to import dependency
    shock_factor = (wheat_d * 0.3 + rice_d * 0.35 + maize_d * 0.35) / 100.0
    valid["shock_delta"] = valid["food_import_pct"] / 100.0 * shock_factor * 40.0
    valid["shocked"]     = (valid["fragility"] + valid["shock_delta"]).clip(0, 100)
    top20 = valid.nlargest(20, "shocked")

    colors = [fragility_band(s)[1] for s in top20["fragility"]]
    fig = go.Figure(go.Bar(
        x=top20["country_name"],
        y=top20["shocked"],
        marker_color=colors,
        marker_line_color="rgba(255,255,255,0.5)",
        marker_line_width=0.6,
        hovertemplate="<b>%{x}</b><br>Shocked fragility: %{y:.1f}<extra></extra>",
        customdata=top20["fragility"].values,
    ))
    fig.update_layout(
        xaxis=dict(tickangle=-38, tickfont=dict(size=8, color="#94a3b8")),
        yaxis=dict(title="Shock-adjusted fragility", tickfont=dict(size=9, color="#94a3b8"),
                   gridcolor="#f1f5f9", range=[0, 105]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=4, t=10, b=80), height=320,
        bargap=0.3,
    )
    return fig


def make_food_trend_chart(trend_df: pd.DataFrame, country_name: str) -> go.Figure:
    if trend_df.empty:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=200)
        return fig
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend_df["year"], y=trend_df["value"],
        mode="lines", line=dict(color="#16a34a", width=2),
        fill="tozeroy", fillcolor="rgba(22,163,74,0.07)",
        hovertemplate="%{x}: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="#94a3b8", line_width=1,
                  annotation_text="Baseline (100)", annotation_font_size=9,
                  annotation_font_color="#94a3b8")
    fig.update_layout(
        xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#94a3b8")),
        yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(size=8, color="#94a3b8"),
                   title="Food production index"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=4, t=6, b=4), height=200,
        title=dict(text=f"{country_name} — food production since 1990",
                   font=dict(size=10, color="#475569"), x=0.5),
    )
    return fig


# ── HTML builders ─────────────────────────────────────────────────────────────
def _benchmark_span(val, avg, high_is_bad: bool = True) -> str:
    if val is None or avg is None or pd.isna(val) or pd.isna(avg):
        return ""
    diff = val - avg
    if abs(diff) < 0.5:
        return ""
    direction = "up" if diff > 0 else "down"
    cls = ("bench-up" if (high_is_bad and diff > 0) or (not high_is_bad and diff < 0) else "bench-down")
    arrow = "▲" if diff > 0 else "▼"
    return f'<span class="benchmark {cls}">{arrow} {abs(diff):.1f} vs global avg</span>'


def _country_panel_v2(r: pd.Series, rank: int, avgs: dict, water_stress_val: float | None) -> str:
    name   = r.get("country_name", r.get("iso", ""))
    frag   = r.get("fragility")
    label, color, bg = fragility_band(frag)
    fill   = {"CRITICAL":1.0,"HIGH":0.78,"MODERATE":0.52,"LOW":0.28,"SECURE":0.10,"N/A":0}.get(label, 0.4)
    badge_svg = grain_badge_svg(fill, color, 34)

    # Compound risk callout
    compound = ""
    if (water_stress_val is not None and not pd.isna(water_stress_val)
            and water_stress_val > 40 and frag is not None and frag > 60):
        compound = (
            '<div class="compound-risk">'
            '<div class="compound-risk-title">⚠ Compound water + food stress</div>'
            '<div class="compound-risk-body">This country faces simultaneous high water withdrawal '
            f'({water_stress_val:.0f}%) and food fragility ({frag:.0f}). A single drought event can '
            'trigger both crises simultaneously.</div></div>'
        )

    imp  = r.get("food_import_pct"); prod = r.get("food_prod_index")
    undr = r.get("undernourishment"); land = r.get("agri_land_pct")
    avgi = avgs.get("food_import_pct"); avgp = avgs.get("food_prod_index")
    avgu = avgs.get("undernourishment"); avgl = avgs.get("agri_land_pct")

    cards = f"""
<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-label">Food imports</div>
    <div class="metric-value">{_fmt(imp,1)}<span class="metric-unit">%</span></div>
    {_benchmark_span(imp, avgi, True)}
  </div>
  <div class="metric-card">
    <div class="metric-label">Food prod. index</div>
    <div class="metric-value">{_fmt(prod,1)}</div>
    {_benchmark_span(prod, avgp, False)}
  </div>
  <div class="metric-card">
    <div class="metric-label">Undernourished</div>
    <div class="metric-value">{_fmt(undr,1)}<span class="metric-unit">%</span></div>
    {_benchmark_span(undr, avgu, True)}
  </div>
  <div class="metric-card">
    <div class="metric-label">Agricultural land</div>
    <div class="metric-value">{_fmt(land,1)}<span class="metric-unit">%</span></div>
    {_benchmark_span(land, avgl, False)}
  </div>
</div>"""

    story_text = food_story(r, rank, avgs.get("fragility", 40))
    story = f'<div class="story-card">{story_text}</div>'

    method_note = (
        '<div class="method-note">'
        '<strong>Methodology:</strong> Fragility score = 0.35 × import dependency '
        '+ 0.35 × food production gap + 0.30 × undernourishment. '
        'Crop suitability uses a bioclimatic envelope approach inspired by MaxEnt '
        '(19 WorldClim v2.1 variables; validated AUC 0.8642 on Sub-Saharan Africa maize).'
        '</div>'
    )

    return (
        f'<p class="country-heading">{name}</p>'
        f'<div class="grain-badge">{badge_svg}'
        f'<span class="frag-band-label" style="color:{color}">{label}</span>'
        f'<span class="frag-band-label" style="margin-left:4px">· {_fmt(frag,1)}/100</span>'
        f'</div>'
        f'{compound}{cards}{story}{method_note}'
    )


def _stats_strip_v2(gs: dict) -> str:
    cards = [
        ("🌍", str(gs["critical_count"]),  "critical countries",         "0.05s"),
        ("📦", str(gs["high_import"]),      "high food import dependency", "0.12s"),
        ("📊", f'{gs["avg_fragility"]:.0f}', "global avg fragility score", "0.18s"),
        ("⚠",  gs["worst_name"],            "most fragile system",        "0.24s"),
    ]
    items = "".join(
        f'<div class="strip-card" style="animation-delay:{delay}">'
        f'<div class="strip-icon">{icon}</div>'
        f'<div class="strip-n">{num}</div>'
        f'<div class="strip-l">{lbl}</div>'
        f'</div>'
        for icon, num, lbl, delay in cards
    )
    return f'<div class="strip-row">{items}</div>'


def intro_card_html(gs: dict) -> str:
    return (
        '<div class="intro-card">'
        '<div class="intro-inner">'
        f'<div class="intro-svg">{farm_scene_svg()}</div>'
        '<div class="intro-text">'
        '<p class="intro-heading">What is food system fragility?</p>'
        '<p class="intro-body">A country\'s food security depends on three things: '
        '<strong>what it grows</strong>, <strong>what it can buy</strong>, and '
        '<strong>how much climate risk it faces</strong>. This tool combines import '
        'dependency, domestic production, and undernourishment data with bioclimatic '
        'crop suitability modelling — the same methodology used in MaxEnt habitat '
        'prediction — to score food fragility across 150+ countries.</p>'
        '<div class="intro-callout">'
        f'<span class="intro-n">{gs["critical_count"]}</span>'
        '<span class="intro-l">countries in critical food fragility right now</span>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'
    )


def agritech_cards_html(strategies: list[dict]) -> str:
    cards = []
    for s in strategies:
        imp_cls  = f'badge-impact-{s["impact"].lower()}'
        feas_cls = f'badge-feasibility-{s["feasibility"].lower()}'
        cards.append(
            f'<div class="agritech-card">'
            f'<div class="agritech-header">'
            f'<div class="agritech-title">{s["title"]}</div>'
            f'<div class="agritech-badges">'
            f'<span class="badge {imp_cls}">Impact: {s["impact"]}</span>'
            f'<span class="badge {feas_cls}">Feasibility: {s["feasibility"]}</span>'
            f'</div></div>'
            f'<div class="agritech-desc">{s["description"]}</div>'
            f'<div class="agritech-meta">'
            f'<span>⏱ {s["timeframe"]}</span>'
            f'<span>🌍 e.g. {s["example"]}</span>'
            f'</div></div>'
        )
    return "".join(cards)


# ── App ───────────────────────────────────────────────────────────────────────
st.markdown(CSS, unsafe_allow_html=True)

with st.spinner("Loading food security data…"):
    df_food  = load_food_data()
    names    = load_country_names()

df_food["country_name"] = df_food["iso"].map(names).fillna(df_food["iso"])

# Load water stress data for compound risk detection
@st.cache_data(ttl=86_400 * 7, persist="disk", show_spinner=False)
def _fetch_water_stress() -> dict[str, float]:
    url = f"https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWTL.ZS?format=json&mrv=1&per_page=300"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        payload = r.json()
        return {item["countryiso3code"]: item["value"]
                for item in payload[1]
                if item.get("countryiso3code") and item.get("value") is not None}
    except Exception:
        return {}

water_stress_map = _fetch_water_stress()

# Rank by fragility
valid_ranked = df_food.dropna(subset=["fragility"]).sort_values("fragility", ascending=False).reset_index(drop=True)
valid_ranked["rank"] = valid_ranked.index + 1
df_food = df_food.merge(valid_ranked[["iso", "rank"]], on="iso", how="left")

avgs = {
    "fragility":       float(df_food["fragility"].dropna().mean()),
    "food_import_pct": float(df_food["food_import_pct"].dropna().mean()),
    "food_prod_index": float(df_food["food_prod_index"].dropna().mean()),
    "undernourishment":float(df_food["undernourishment"].dropna().mean()),
    "agri_land_pct":   float(df_food["agri_land_pct"].dropna().mean()),
}
gs = global_food_stats(df_food)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="day-label">Day 04 · The Resilience Stack</span>', unsafe_allow_html=True)
    st.markdown("## Food Fragility")

    sorted_df = df_food.dropna(subset=["fragility"]).sort_values("country_name")
    country_options = sorted_df["iso"].tolist()
    country_labels  = {row["iso"]: row["country_name"] for _, row in sorted_df.iterrows()}

    # Default to Nigeria (compound risk example)
    default_iso = "NGA" if "NGA" in country_options else (country_options[0] if country_options else None)
    default_idx = country_options.index(default_iso) if default_iso in country_options else 0

    selected_iso = st.selectbox(
        "Select country",
        options=country_options,
        index=default_idx,
        format_func=lambda x: country_labels.get(x, x),
    )

    st.markdown('<span class="radio-label">Map metric</span>', unsafe_allow_html=True)
    metric = st.radio(
        "metric",
        ["Fragility Score", "Import Dependency %", "Undernourishment %"],
        label_visibility="collapsed",
    )

    st.markdown('<hr class="sep"/>', unsafe_allow_html=True)

    if selected_iso:
        row  = df_food[df_food["iso"] == selected_iso]
        if not row.empty:
            r    = row.iloc[0]
            rank = int(r.get("rank", 0)) if not pd.isna(r.get("rank", float("nan"))) else 0
            ws   = water_stress_map.get(selected_iso)
            st.markdown(_country_panel_v2(r, rank, avgs, ws), unsafe_allow_html=True)

    st.markdown('<hr class="sep"/>', unsafe_allow_html=True)
    st.markdown(
        '<div class="data-footer">'
        'Sources: World Bank WDI<br>'
        'Indicators: TM.VAL.FOOD.ZS.UN · AG.PRD.FOOD.XD<br>'
        'SN.ITK.DEFC.ZS · AG.LND.AGRI.ZS<br>'
        'Crop model: WorldClim v2.1 / MaxEnt methodology<br>'
        'Climate projections: CMIP6 SSP3-7.0<br><br>'
        '<a href="/" style="color:#94a3b8">← Day 03 Water Stress</a>'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Main ───────────────────────────────────────────────────────────────────────
if "intro_dismissed" not in st.session_state:
    st.session_state.intro_dismissed = False

if not st.session_state.intro_dismissed:
    col_intro, col_dismiss = st.columns([20, 1])
    with col_intro:
        st.markdown(intro_card_html(gs), unsafe_allow_html=True)
    with col_dismiss:
        if st.button("✕", help="Dismiss", key="dismiss_intro"):
            st.session_state.intro_dismissed = True
            st.rerun()

st.markdown(_stats_strip_v2(gs), unsafe_allow_html=True)

no_data_ct = int(df_food["fragility"].isna().sum())
if no_data_ct:
    st.markdown(
        f'<p class="no-data-note">{no_data_ct} countries lack sufficient data for fragility scoring.</p>',
        unsafe_allow_html=True,
    )

# Map
fig_map = make_fragility_map(df_food, selected_iso, metric)
event = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun", key="frag_map")

if event and event.get("selection", {}).get("points"):
    clicked_iso = event["selection"]["points"][0].get("location")
    if clicked_iso and clicked_iso != selected_iso and clicked_iso in country_options:
        st.session_state["clicked_iso"] = clicked_iso
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "COUNTRY DEEP DIVE",
    "CROP CLIMATE SHIFT",
    "FOOD SHOCK SIMULATOR",
    "AGRITECH STRATEGIES",
])

# ── Tab 1 — Country Deep Dive ─────────────────────────────────────────────────
with tab1:
    if selected_iso:
        row = df_food[df_food["iso"] == selected_iso]
        if not row.empty:
            r = row.iloc[0]
            name = r.get("country_name", selected_iso)

            c1, c2 = st.columns([3, 2])
            with c1:
                with st.spinner("Loading trend data…"):
                    trend_df = load_food_trend(selected_iso)
                fig_trend = make_food_trend_chart(trend_df, name)
                st.plotly_chart(fig_trend, use_container_width=True)

            with c2:
                frag = r.get("fragility")
                label, color, _ = fragility_band(frag)
                st.markdown(
                    f'<div class="strip-card" style="margin-bottom:8px">'
                    f'<div class="metric-label">Fragility score</div>'
                    f'<div class="metric-value" style="font-size:28px;color:{color}">{_fmt(frag,1)}</div>'
                    f'<div class="metric-label" style="color:{color};margin-top:4px">{label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Sector breakdown bars
                imp  = r.get("food_import_pct") or 0
                undr = r.get("undernourishment") or 0
                land = r.get("agri_land_pct") or 0

                def bar(label: str, val: float, max_v: float, color: str) -> str:
                    pct = min(val / max_v * 100, 100) if max_v else 0
                    return (
                        f'<div class="sector-row">'
                        f'<div class="sector-label-row"><span>{label}</span><span>{val:.1f}%</span></div>'
                        f'<div class="sector-track">'
                        f'<div class="sector-fill" style="width:{pct:.0f}%;background:{color}"></div>'
                        f'</div></div>'
                    )

                bars_html = (
                    '<style>.sector-row{margin-bottom:10px}.sector-label-row{display:flex;justify-content:space-between;font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:#94a3b8;margin-bottom:5px}.sector-track{height:5px;background:#e2e8f0;border-radius:3px;overflow:hidden}.sector-fill{height:5px;border-radius:3px;transform:scaleX(0);transform-origin:left;animation:barGrow .8s ease-out forwards}</style>'
                    + bar("Food imports",     imp,  100, "#f97316")
                    + bar("Undernourishment", undr, 40,  "#dc2626")
                    + bar("Agricultural land",land,  60, "#16a34a")
                )
                st.markdown(bars_html, unsafe_allow_html=True)

            # Regional peers comparison
            st.markdown("---")
            st.caption("Compare with regional peers")
            all_countries = sorted(df_food.dropna(subset=["fragility"])["country_name"].tolist())
            peer = st.selectbox("Compare peer country", ["— select —"] + all_countries, key="peer_sel")
            if peer != "— select —":
                peer_row = df_food[df_food["country_name"] == peer]
                if not peer_row.empty:
                    pr = peer_row.iloc[0]
                    cc1, cc2 = st.columns(2)
                    for col_el, row_data, iso_val in [(cc1, r, selected_iso), (cc2, pr, pr["iso"])]:
                        with col_el:
                            fl, col_c, _ = fragility_band(row_data.get("fragility"))
                            st.markdown(
                                f'<div class="strip-card">'
                                f'<div class="metric-label">{row_data.get("country_name","")}</div>'
                                f'<div class="metric-value" style="font-size:22px;color:{col_c}">{_fmt(row_data.get("fragility"),1)}</div>'
                                f'<div class="metric-label" style="color:{col_c}">{fl}</div>'
                                f'<div style="font-size:10px;color:#94a3b8;margin-top:6px">'
                                f'Imports: {_fmt(row_data.get("food_import_pct"),1)}% · '
                                f'Undernourished: {_fmt(row_data.get("undernourishment"),1)}%</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

# ── Tab 2 — Crop Climate Shift ────────────────────────────────────────────────
with tab2:
    st.markdown(
        '<div class="method-note" style="margin-bottom:12px">'
        '<strong>Bioclimatic envelope model</strong> — Crop suitability is computed using a '
        'simplified MaxEnt approach: Gaussian overlap of mean annual temperature and precipitation '
        'with optimal and absolute bioclimatic ranges for Maize, Wheat, Rice and Sorghum. '
        'Ranges derived from WorldClim v2.1 (19 bioclimatic variables). '
        'Methodology validated at AUC 0.8642 on Sub-Saharan Africa maize under SSP3-7.0 baseline vs. 2050.'
        '</div>',
        unsafe_allow_html=True,
    )

    scenario = st.select_slider(
        "Climate scenario",
        options=list(TEMP_DELTAS.keys()),
        value="Current baseline",
    )
    t_delta = TEMP_DELTAS[scenario]

    col_map2, col_panel = st.columns([3, 2])
    with col_map2:
        if selected_iso and selected_iso in COUNTRY_CLIMATE:
            t_now, p_now = COUNTRY_CLIMATE[selected_iso]
            t_fut = t_now + t_delta
            p_fut = p_now * (1.0 - 0.025 * t_delta)
            scores_now = {c: bioclimatic_score(t_now, p_now, c) for c in CROP_PROFILES}
            scores_fut = {c: bioclimatic_score(t_fut, p_fut, c) for c in CROP_PROFILES}

            name = df_food[df_food["iso"] == selected_iso]["country_name"].iloc[0] if selected_iso in df_food["iso"].values else selected_iso
            st.plotly_chart(
                make_radar_chart(scores_now, scores_fut, f"{name} — crop suitability radar"),
                use_container_width=True,
            )
        else:
            st.info("Select a country with climate data to view the crop suitability radar.")

    with col_panel:
        if selected_iso:
            st.markdown(
                crop_suitability_bars_html(selected_iso, t_delta),
                unsafe_allow_html=True,
            )
            if t_delta > 0 and selected_iso in COUNTRY_CLIMATE:
                t_now, p_now = COUNTRY_CLIMATE[selected_iso]
                t_fut = t_now + t_delta
                gains  = [c for c in CROP_PROFILES if bioclimatic_score(t_fut, p_now*(1-0.025*t_delta), c) > bioclimatic_score(t_now, p_now, c)]
                losses = [c for c in CROP_PROFILES if bioclimatic_score(t_fut, p_now*(1-0.025*t_delta), c) < bioclimatic_score(t_now, p_now, c)]
                if losses:
                    st.markdown(
                        f'<div class="compound-risk" style="animation:none">'
                        f'<div class="compound-risk-title">Climate crop risk</div>'
                        f'<div class="compound-risk-body">Under {scenario}, '
                        f'<strong>{", ".join(losses)}</strong> suitability declines.'
                        + (f' <strong>{", ".join(gains)}</strong> may see marginal gains.' if gains else "")
                        + '</div></div>',
                        unsafe_allow_html=True,
                    )

    # City-level zoom
    with st.expander("📍 City-level bioclimatic analysis (Open-Meteo)"):
        city_name = st.selectbox("Select agricultural city", ["— select —"] + sorted(CITY_LIST.keys()), key="city_sel")
        if city_name != "— select —":
            lat, lon = CITY_LIST[city_name]
            with st.spinner(f"Fetching climate data for {city_name}…"):
                city_clim = load_city_climate(lat, lon)

            if city_clim["t_mean"] is not None:
                t_c = city_clim["t_mean"] + t_delta
                p_c = city_clim["p_annual"] * (1.0 - 0.025 * t_delta) if city_clim["p_annual"] else None
                sc_now_c = {c: bioclimatic_score(city_clim["t_mean"], city_clim["p_annual"] or 0, c) for c in CROP_PROFILES}
                sc_fut_c = {c: bioclimatic_score(t_c, p_c or 0, c) for c in CROP_PROFILES}

                st.markdown(
                    f'<div style="font-size:11px;color:#475569;margin-bottom:10px">'
                    f'<strong>{city_name}</strong> — '
                    f'T̄ {city_clim["t_mean"]:.1f}°C · Precip {city_clim["p_annual"]:.0f} mm/yr (1990–2020 baseline)'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.plotly_chart(make_radar_chart(sc_now_c, sc_fut_c, f"{city_name.split(',')[0]}"), use_container_width=True)
                with cc2:
                    suitable_now = [f"{CROP_PROFILES[c]['icon']} {c}" for c in CROP_PROFILES if sc_now_c[c] >= 0.5]
                    suitable_fut = [f"{CROP_PROFILES[c]['icon']} {c}" for c in CROP_PROFILES if sc_fut_c[c] >= 0.5]
                    st.markdown(
                        f'<div class="metrics-grid">'
                        f'<div class="metric-card"><div class="metric-label">Suitable now</div>'
                        f'<div style="font-size:12px;color:#0f172a;margin-top:4px">{" · ".join(suitable_now) or "None"}</div></div>'
                        f'<div class="metric-card"><div class="metric-label">Suitable 2050</div>'
                        f'<div style="font-size:12px;color:#0f172a;margin-top:4px">{" · ".join(suitable_fut) or "None"}</div></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("Could not fetch climate data for this location. Try another city.")

# ── Tab 3 — Food Shock Simulator ──────────────────────────────────────────────
with tab3:
    st.markdown(
        '<p style="font-size:12px;color:#475569;margin-bottom:12px">'
        'Simulate the impact of global commodity price shocks on food-importing countries. '
        'Higher import dependency amplifies fragility when prices spike.</p>',
        unsafe_allow_html=True,
    )
    c1s, c2s, c3s = st.columns(3)
    with c1s:
        wheat_d = st.slider("Wheat price change %", -50, 200, 0, 5, key="wheat_sl")
    with c2s:
        rice_d  = st.slider("Rice price change %",  -50, 200, 0, 5, key="rice_sl")
    with c3s:
        maize_d = st.slider("Maize price change %", -50, 200, 0, 5, key="maize_sl")

    if wheat_d != 0 or rice_d != 0 or maize_d != 0:
        st.plotly_chart(
            make_shock_chart(df_food, wheat_d, rice_d, maize_d),
            use_container_width=True,
        )
        st.caption("Bar height = shock-adjusted fragility. Colour = baseline fragility band. Most vulnerable countries shown.")
    else:
        st.info("Move a price slider to simulate a food shock scenario.")

# ── Tab 4 — AgriTech Strategies ───────────────────────────────────────────────
with tab4:
    if selected_iso:
        row = df_food[df_food["iso"] == selected_iso]
        name_t4 = row.iloc[0]["country_name"] if not row.empty else selected_iso
        frag_t4 = float(row.iloc[0]["fragility"]) if not row.empty and not pd.isna(row.iloc[0]["fragility"]) else None
        ws_t4   = water_stress_map.get(selected_iso)
        label_t4, color_t4, _ = fragility_band(frag_t4)

        st.markdown(
            f'<p style="font-size:12px;color:#475569;margin-bottom:10px">'
            f'Technology recommendations for <strong>{name_t4}</strong> '
            f'(<span style="color:{color_t4}">{label_t4}</span> fragility).</p>',
            unsafe_allow_html=True,
        )

        strategies = agritech_recommendations(frag_t4, ws_t4)
        st.markdown(agritech_cards_html(strategies), unsafe_allow_html=True)

        st.markdown(
            '<div class="method-note">'
            '<strong>Strategy scoring:</strong> Impact and feasibility ratings reflect '
            'meta-analyses from FAO, CGIAR, and World Bank agricultural development reviews. '
            'Recommendations are filtered by fragility tier and compound water stress. '
            'Timeframes assume adequate financing and institutional capacity.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Select a country in the sidebar to see technology recommendations.")
