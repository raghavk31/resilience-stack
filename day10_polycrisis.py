"""
The Resilience Stack — Day 10
The Polycrisis Dashboard

Composite Country Resilience Score across 7 climate-risk dimensions.
"Polycrisis" — Adam Tooze 2022: multiple crises compound and reinforce each other.

Dimensions (each 0-100, higher = more vulnerable):
  Energy     — fossil dependency + electricity access gap
  Water      — freshwater withdrawal stress
  Food       — undernourishment prevalence
  Air        — mean annual PM2.5 exposure
  Heat       — climate-zone heat stress index (IPCC AR6 WG2)
  Economy    — inverse log GDP/capita (adaptive capacity)
  Carbon     — CO₂ emissions per capita

Sources:
  World Bank EG.USE.COMM.FO.ZS — fossil fuel % of total energy
  World Bank EG.ELC.ACCS.ZS    — electricity access %
  World Bank ER.H2O.FWTL.ZS   — freshwater withdrawal %
  World Bank SN.ITK.DEFC.ZS   — undernourishment %
  World Bank EN.ATM.PM25.MC.M3 — mean PM2.5 µg/m³
  World Bank NY.GDP.PCAP.CD   — GDP per capita USD
  World Bank SP.POP.TOTL       — population
  World Bank EN.ATM.CO2E.PC   — CO₂ per capita tonnes
  IPCC AR6 WG2 heat hazard maps — heat stress score by country
"""

import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests

st.set_page_config(
    page_title="Polycrisis Dashboard · Day 10",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ──────────────────────────────────────────────────────────────────
WB_META    = "https://api.worldbank.org/v2/country"
HEADERS    = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}

IND_FOSSIL = "EG.USE.COMM.FO.ZS"
IND_ELEC   = "EG.ELC.ACCS.ZS"
IND_WATER  = "ER.H2O.FWTL.ZS"
IND_FOOD   = "SN.ITK.DEFC.ZS"
IND_PM25   = "EN.ATM.PM25.MC.M3"
IND_GDP    = "NY.GDP.PCAP.CD"
IND_POP    = "SP.POP.TOTL"
IND_CO2    = "EN.ATM.CO2E.PC"

# Dimension display config: label → (column, colour, weight)
DIMS = {
    "Energy":  ("d_energy", "#f97316", 0.15),
    "Water":   ("d_water",  "#3b82f6", 0.18),
    "Food":    ("d_food",   "#ca8a04", 0.15),
    "Air":     ("d_air",    "#8b5cf6", 0.15),
    "Heat":    ("d_heat",   "#ef4444", 0.15),
    "Economy": ("d_eco",    "#64748b", 0.12),
    "Carbon":  ("d_co2",    "#16a34a", 0.10),
}

# IPCC AR6 WG2 — heat stress score by ISO3 (0-100, higher = worse)
HEAT_SCORE: dict[str, float] = {
    "SAU":95,"ARE":95,"QAT":95,"KWT":95,"BHR":90,"OMN":90,"YEM":88,"IRQ":88,
    "DJI":92,"ERI":80,"SDN":92,"SSD":88,"NER":92,"MLI":90,"BFA":88,"TCD":90,
    "SEN":80,"MRT":88,"SOM":85,"PAK":88,"IND":78,"BGD":75,"LKA":65,
    "NGA":72,"GHA":70,"CIV":68,"TGO":70,"BEN":70,"CMR":68,"ETH":72,
    "KEN":65,"UGA":62,"TZA":62,"MOZ":60,"ZMB":58,"ZWE":60,"BWA":68,
    "NAM":65,"AGO":62,"MDG":58,"EGY":82,"LBY":78,"TUN":70,"DZA":72,
    "MAR":62,"SYR":78,"JOR":78,"PSE":75,"AFG":70,"UZB":68,"TJK":55,
    "THA":78,"VNM":75,"KHM":77,"LAO":72,"MMR":74,"IDN":70,"PHL":72,
    "MYS":68,"MEX":62,"GTM":60,"SLV":62,"HND":62,"NIC":60,"HTI":65,
    "COL":58,"VEN":60,"BRA":58,"BOL":52,"PRY":55,"ZAF":48,"COD":65,
    "GAB":62,"CHN":52,"KOR":48,"JPN":50,"TUR":58,"GRC":62,"ESP":55,
    "ITA":52,"PRT":52,"AUS":55,"ARG":42,"CHL":30,"PER":48,"ECU":50,
    "USA":40,"UKR":32,"RUS":25,"KAZ":42,"GBR":28,"DEU":30,"FRA":38,
    "POL":32,"SWE":20,"NOR":18,"FIN":18,"DNK":22,"NLD":28,"CAN":28,"NZL":32,
    "IRN":78,"TWN":62,"SGP":65,
}
DEFAULT_HEAT = 52.0

RESILIENCE_BANDS = [
    (80, 100, "Resilient",  "#16a34a"),
    (60,  80, "Stable",     "#4ade80"),
    (40,  60, "Vulnerable", "#f59e0b"),
    (20,  40, "At Risk",    "#ef4444"),
    ( 0,  20, "Critical",   "#7f1d1d"),
]

# ── Story card editorial content ───────────────────────────────────────────────
CARD_DATA = {
    "Energy": {
        "stat": "733M",
        "stat_label": "people without electricity",
        "body": "Half live in Sub-Saharan Africa. Energy poverty shapes every downstream crisis — how food is stored, whether clinics refrigerate vaccines, whether children can study after dark. Nations burning 80%+ fossil fuels face both supply-shock volatility and carbon lock-in.",
        "source": "IEA World Energy Outlook 2023",
    },
    "Water": {
        "stat": "4 billion",
        "stat_label": "face severe water scarcity ≥1 month/year",
        "body": "Agriculture consumes 70% of all freshwater drawn globally. When aquifers fail, crops fail. When crops fail, people move. The water–food–migration chain is the most direct polycrisis pathway on Earth.",
        "source": "Mekonnen & Hoekstra, Science Advances, 2016",
    },
    "Food": {
        "stat": "733M",
        "stat_label": "people face hunger daily",
        "body": "2.4 billion face food insecurity. The global food system is optimised for efficiency, not resilience — three countries supply 40% of the world's wheat. One drought cascades into 50 price spikes felt across billions of plates.",
        "source": "FAO State of Food Security 2023",
    },
    "Air": {
        "stat": "99%",
        "stat_label": "breathe air above WHO limits",
        "body": "PM2.5 kills 7 million people annually — more than AIDS, malaria, and tuberculosis combined. The worst air is concentrated precisely where adaptive capacity is lowest, compounding every other vulnerability.",
        "source": "WHO Air Quality Database 2022",
    },
    "Heat": {
        "stat": "3.5B",
        "stat_label": "in climate-highly-vulnerable contexts",
        "body": "35°C wet-bulb temperature is physiologically unsurvivable in 6 hours — regardless of fitness or shelter. By 2050, 2 billion people will live in zones exceeding this threshold on some days. Heat deaths go systematically undercounted.",
        "source": "IPCC AR6 WG2 Summary for Policymakers, 2022",
    },
    "Economy": {
        "stat": "10–23%",
        "stat_label": "potential global GDP loss by 2100",
        "body": "The countries most exposed — Sub-Saharan Africa, South Asia, small island states — contribute less than 5% of cumulative emissions. Adaptive capacity is the inverse of vulnerability: those who caused least suffer most.",
        "source": "Swiss Re Institute, 2021",
    },
    "Carbon": {
        "stat": "Top 1%",
        "stat_label": "emit as much as the bottom 50%",
        "body": "Ten countries account for 68% of global emissions. Yet the severest climate impacts land on the least responsible emitters — a moral calculus that no resilience score can fully capture, but every resilience plan must reckon with.",
        "source": "World Inequality Report, Chancel 2022",
    },
}

# ── SVG icons (inline, 20×20 viewport) ────────────────────────────────────────
ICONS: dict[str, str] = {
    "Energy": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#f97316">'
        '<path d="M13 2L4.09 12.97H12L11 22L19.91 11.03H12L13 2Z"/>'
        '</svg>'
    ),
    "Water": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#3b82f6">'
        '<path d="M12 2C6.48 10 4 13.5 4 16a8 8 0 0 0 16 0c0-2.5-2.48-6-8-14z"/>'
        '</svg>'
    ),
    "Food": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="2" stroke-linecap="round">'
        '<line x1="12" y1="22" x2="12" y2="10"/>'
        '<path d="M9 5c0 3 3 5 3 5s3-2 3-5a3 3 0 0 0-6 0z"/>'
        '<path d="M9 11c0 3 3 5 3 5s3-2 3-5"/>'
        '</svg>'
    ),
    "Air": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#8b5cf6">'
        '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>'
        '</svg>'
    ),
    "Heat": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#ef4444">'
        '<path d="M12 2C9.5 6 8 8.5 8 11a4 4 0 0 0 8 0c0-2.5-1.5-5-4-9z"/>'
        '<circle cx="12" cy="18" r="3"/>'
        '<line x1="12" y1="15" x2="12" y2="11" stroke="#ef4444" stroke-width="2"/>'
        '</svg>'
    ),
    "Economy": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#64748b">'
        '<rect x="2" y="14" width="4" height="8" rx="1"/>'
        '<rect x="9" y="9" width="4" height="13" rx="1"/>'
        '<rect x="16" y="4" width="4" height="18" rx="1"/>'
        '</svg>'
    ),
    "Carbon": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="#16a34a">'
        '<path d="M17 8C8 10 5.9 16.17 3.82 22.5"/>'
        '<path d="M10.99 8.99c-1.49.9-1.99 1.6-1.99 2.41v3.5"/>'
        '<path d="M14 9.8l.67.68a2.3 2.3 0 0 1 .33 3.41L12 16.11"/>'
        '<path d="M16.5 8.5l1.88 1.88a4 4 0 0 1 0 5.66L15 19.42"/>'
        '</svg>'
    ),
}

# ── Polycrisis network SVG ─────────────────────────────────────────────────────
# 7 dimension nodes at angles 90°, 39°, −13°, −64°, −116°, −167°, 141°
# from center (100,100), radius 70
_POLY_SVG = """
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:210px;display:block;margin:8px auto 0">
  <defs>
    <radialGradient id="cg" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#111" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#111" stop-opacity="0.03"/>
    </radialGradient>
  </defs>

  <!-- Ring connections between adjacent nodes -->
  <polygon points="100,30 156,56 169,117 130,166 70,166 31,117 44,56"
    fill="none" stroke="#e5e7eb" stroke-width="1"/>

  <!-- Spoke connections center → each node -->
  <line x1="100" y1="100" x2="100"  y2="30"  stroke="#f97316" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="156"  y2="56"  stroke="#3b82f6" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="169"  y2="117" stroke="#ca8a04" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="130"  y2="166" stroke="#8b5cf6" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="70"   y2="166" stroke="#ef4444" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="31"   y2="117" stroke="#64748b" stroke-width="1.2" opacity="0.35"/>
  <line x1="100" y1="100" x2="44"   y2="56"  stroke="#16a34a" stroke-width="1.2" opacity="0.35"/>

  <!-- Cross connections (strongest polycrisis links) -->
  <line x1="100" y1="30" x2="169" y2="117" stroke="#f97316" stroke-width="0.7" opacity="0.18" stroke-dasharray="3,3"/>
  <line x1="156" y1="56" x2="130" y2="166" stroke="#3b82f6" stroke-width="0.7" opacity="0.18" stroke-dasharray="3,3"/>
  <line x1="169" y1="117" x2="70" y2="166" stroke="#ca8a04" stroke-width="0.7" opacity="0.18" stroke-dasharray="3,3"/>
  <line x1="31"  y1="117" x2="100" y2="30" stroke="#64748b" stroke-width="0.7" opacity="0.18" stroke-dasharray="3,3"/>

  <!-- Centre node -->
  <circle cx="100" cy="100" r="22" fill="url(#cg)" stroke="#d1d5db" stroke-width="1"/>
  <text x="100" y="97" text-anchor="middle" font-family="'Space Grotesk',sans-serif"
        font-size="7" font-weight="800" fill="#374151" letter-spacing="0.8">POLY</text>
  <text x="100" y="107" text-anchor="middle" font-family="'Space Grotesk',sans-serif"
        font-size="7" font-weight="800" fill="#374151" letter-spacing="0.8">CRISIS</text>

  <!-- Dimension nodes -->
  <!-- Energy -->
  <circle cx="100" cy="30" r="16" fill="#fff7ed" stroke="#f97316" stroke-width="1.5"/>
  <text x="100" y="34" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="6.2" font-weight="700" fill="#ea580c">ENERGY</text>

  <!-- Water -->
  <circle cx="156" cy="56" r="16" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
  <text x="156" y="60" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="6.2" font-weight="700" fill="#2563eb">WATER</text>

  <!-- Food -->
  <circle cx="169" cy="117" r="16" fill="#fffbeb" stroke="#ca8a04" stroke-width="1.5"/>
  <text x="169" y="121" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="6.2" font-weight="700" fill="#b45309">FOOD</text>

  <!-- Air -->
  <circle cx="130" cy="166" r="16" fill="#f5f3ff" stroke="#8b5cf6" stroke-width="1.5"/>
  <text x="130" y="170" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="6.2" font-weight="700" fill="#7c3aed">AIR</text>

  <!-- Heat -->
  <circle cx="70" cy="166" r="16" fill="#fef2f2" stroke="#ef4444" stroke-width="1.5"/>
  <text x="70" y="170" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="6.2" font-weight="700" fill="#dc2626">HEAT</text>

  <!-- Economy -->
  <circle cx="31" cy="117" r="16" fill="#f8fafc" stroke="#64748b" stroke-width="1.5"/>
  <text x="31" y="121" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="5.8" font-weight="700" fill="#475569">ECON</text>

  <!-- Carbon -->
  <circle cx="44" cy="56" r="16" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
  <text x="44" y="60" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="5.8" font-weight="700" fill="#15803d">CO₂</text>
</svg>
"""


# ── CSS ────────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1a1a1a; }
#MainMenu, header[data-testid="stHeader"], footer { display: none !important; }
.stApp { background: #f0f0f0 !important; }
[data-testid="block-container"] {
  padding: 0 !important; max-width: 100% !important; background: transparent !important;
}
[data-testid="stAppViewContainer"], section.main { background: #f0f0f0 !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── App header ── */
.mc-header {
  background: #ffffff;
  border-bottom: 1px solid rgba(0,0,0,0.07);
  padding: 14px 32px;
  display: flex; align-items: center; justify-content: space-between;
}
.mc-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .18em;
  text-transform: uppercase; color: #bbb;
  display: flex; align-items: center; gap: 8px;
}
.mc-dot { width: 8px; height: 8px; border-radius: 50%; background: #f97316; display: inline-block; }
.mc-header-right {
  font-size: .7rem; color: #ccc; font-weight: 500;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: #ffffff !important; border: none !important;
  border-radius: 0 !important; padding: 0 0 0 24px !important; gap: 0 !important;
  border-bottom: 1px solid rgba(0,0,0,0.07) !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: #bbb !important;
  font-size: 10.5px !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: .1em !important;
  padding: 14px 22px !important; border-radius: 0 !important; border: none !important;
}
.stTabs [aria-selected="true"] {
  color: #111 !important; border-bottom: 2px solid #111 !important;
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none !important; }
[data-testid="stTabsContent"] { padding: 0 !important; }

/* ── Two-column independent scroll ── */
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) {
  gap: 0 !important;
  align-items: stretch !important;
  height: calc(100vh - 96px) !important;
  overflow: hidden !important;
}
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"] {
  min-height: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"]:first-child {
  background: #ffffff !important;
  border-right: 1px solid rgba(0,0,0,0.07) !important;
}
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"]:last-child {
  background: #f0f0f0 !important;
}

/* Thin custom scrollbars */
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"]::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"]::-webkit-scrollbar-track { background: transparent; }
[data-testid="stHorizontalBlock"]:has(.mc-scroll-anchor) > [data-testid="column"]::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.13); border-radius: 2px;
}

/* ── Left panel typography & layout ── */
.mc-scroll-anchor { height: 0; display: block; overflow: hidden; }
.lp-inner        { padding: 22px 20px 40px; }
.lp-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.25rem; font-weight: 800; color: #111;
  letter-spacing: -.3px; line-height: 1.2; margin: 0 0 .4rem;
}
.lp-desc  { font-size: .76rem; color: #999; line-height: 1.7; margin: 0; }
.lp-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 16px 0; }
.lp-sec   { font-size: .65rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .12em; margin-bottom: 10px; }
.lp-note  { font-size: .64rem; color: #ccc; line-height: 1.65; }

/* ── Story cards ── */
.story-card {
  background: #fafafa;
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 10px;
  padding: 14px 14px 12px;
  margin-bottom: 10px;
  border-left-width: 3px;
  border-left-style: solid;
  transition: box-shadow .15s ease;
}
.story-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.07); }
.story-card-top  { display: flex; align-items: flex-start; gap: 11px; margin-bottom: 9px; }
.story-icon {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.story-stat {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.45rem; font-weight: 900; line-height: 1; letter-spacing: -.5px;
}
.story-stat-lbl { font-size: .64rem; color: #999; margin-top: 2px; line-height: 1.3; }
.story-body  { font-size: .71rem; color: #555; line-height: 1.68; margin-bottom: 7px; }
.story-src   { font-size: .62rem; color: #ccc; font-style: italic; }

/* ── Polycrisis quote card ── */
.poly-quote-card {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px; padding: 18px; margin-bottom: 14px;
}
.poly-byline { font-size: .62rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: #f97316; margin-bottom: 10px; }
.poly-quote  {
  font-family: 'Space Grotesk', sans-serif;
  font-size: .98rem; font-weight: 700; color: #f8fafc; line-height: 1.5;
  margin-bottom: 11px;
}
.poly-context { font-size: .7rem; color: rgba(248,250,252,0.5); line-height: 1.7; }

/* ── Score badge ── */
.score-badge        { border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }
.score-badge-lbl    { font-size: .65rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 3px; }
.score-badge-val    { font-family: 'Space Grotesk', sans-serif; font-size: 2.9rem; font-weight: 900; line-height: 1; letter-spacing: -2px; }
.score-badge-band   { font-size: .82rem; font-weight: 600; margin-top: 5px; color: #555; }

/* ── Dimension bars ── */
.dim-row  { margin-bottom: 10px; }
.dim-hdr  { display: flex; justify-content: space-between; align-items: baseline; font-size: .72rem; font-weight: 600; color: #444; margin-bottom: 4px; }
.dim-sub  { font-size: .63rem; color: #bbb; font-weight: 400; }
.dim-track { background: rgba(0,0,0,0.06); border-radius: 3px; height: 5px; overflow: hidden; }
.dim-fill  { height: 100%; border-radius: 3px; }

/* ── Right panel ── */
.rp-inner   { padding: 20px 24px 32px; }
.rp-label   { font-size: .65rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #bbb; margin-bottom: 6px; }
.rp-divider { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 16px 0; }

/* ── Stat pills ── */
.stat-row   { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
.stat-pill  {
  background: white; border-radius: 8px; padding: 10px 14px;
  border: 1px solid rgba(0,0,0,0.07); flex: 1; min-width: 90px;
}
.stat-pill-val { font-family: 'Space Grotesk', sans-serif; font-size: 1.3rem; font-weight: 800; color: #111; line-height: 1; }
.stat-pill-lbl { font-size: .62rem; color: #bbb; margin-top: 3px; line-height: 1.35; }

/* ── Score band legend ── */
.band-row  { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.band-dot  { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.band-lbl  { font-size: .71rem; color: #555; flex: 1; }
.band-cnt  { font-size: .71rem; font-weight: 700; color: #333; }

/* ── Correlation insight card ── */
.insight-card {
  background: white; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px;
  border: 1px solid rgba(0,0,0,0.06);
}
.insight-pair { font-size: .75rem; font-weight: 700; color: #111; margin-bottom: 2px; }
.insight-r    { font-size: .7rem; color: #f97316; font-weight: 700; float: right; }
.insight-why  { font-size: .68rem; color: #777; line-height: 1.55; clear: both; margin-top: 5px; }
.insight-bar  { background: rgba(0,0,0,0.07); border-radius: 2px; height: 3px; margin-top: 7px; overflow: hidden; }
.insight-fill { height: 100%; background: #f97316; border-radius: 2px; }

/* ── Narrative card ── */
.narrative-card {
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border-radius: 8px; border: 1px solid rgba(0,0,0,0.06);
  padding: 12px 14px; margin-bottom: 4px;
}
.narrative-label { font-size: .63rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #94a3b8; margin-bottom: 6px; }
.narrative-body  { font-size: .73rem; color: #475569; line-height: 1.65; }

/* ── Widget overrides ── */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .76rem !important; font-weight: 600 !important; color: #333 !important;
}
[data-baseweb="select"] > div {
  background: white !important; border: 1px solid rgba(0,0,0,0.11) !important;
  border-radius: 6px !important; font-size: .78rem !important;
}
[data-baseweb="select"] span { color: #333 !important; }
</style>
"""


# ── Data loading (unchanged) ───────────────────────────────────────────────────

@st.cache_data(ttl=86_400 * 30, show_spinner=False)
def _load_country_meta() -> pd.DataFrame:
    rows, page = [], 1
    while True:
        try:
            r = requests.get(f"{WB_META}?format=json&per_page=500&page={page}",
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            meta, data = r.json()
            for c in data:
                reg = c.get("region", {})
                inc = c.get("incomeLevel", {})
                if isinstance(reg, dict) and reg.get("id") not in ("", "NA", None):
                    rows.append({
                        "iso3":      c["id"], "name": c["name"],
                        "region":    reg.get("value", ""),
                        "income_id": inc.get("id", "INX") if isinstance(inc, dict) else "INX",
                    })
            if page * meta.get("per_page", 500) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def _load_wb_latest(indicator: str) -> pd.DataFrame:
    rows, page = [], 1
    while True:
        url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
               f"?format=json&mrv=5&per_page=1000&page={page}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            if len(payload) < 2 or not payload[1]:
                break
            meta, data = payload
            rows.extend(data)
            if page * meta.get("per_page", 1000) >= meta.get("total", 0):
                break
            page += 1
        except Exception:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df[df["value"].notna()].copy()
    df["iso3"]    = df["countryiso3code"]
    df["country"] = df["country"].apply(lambda x: x["value"] if isinstance(x, dict) else x)
    df["year"]    = df["date"].astype(int)
    df["value"]   = df["value"].astype(float)
    return (df.sort_values("year", ascending=False)
              .groupby("iso3").first().reset_index()[["iso3", "country", "value"]])


@st.cache_data(ttl=86_400 * 7, show_spinner=False)
def load_polycrisis_data() -> pd.DataFrame:
    meta   = _load_country_meta()
    fossil = _load_wb_latest(IND_FOSSIL).rename(columns={"value": "fossil_pct"})
    elec   = _load_wb_latest(IND_ELEC).rename(columns={"value": "elec_access"})
    water  = _load_wb_latest(IND_WATER).rename(columns={"value": "water_withdrawal"})
    food   = _load_wb_latest(IND_FOOD).rename(columns={"value": "undernourishment"})
    pm25   = _load_wb_latest(IND_PM25).rename(columns={"value": "pm25"})
    gdp    = _load_wb_latest(IND_GDP).rename(columns={"value": "gdp_pc"})
    pop    = _load_wb_latest(IND_POP).rename(columns={"value": "population"})
    co2    = _load_wb_latest(IND_CO2).rename(columns={"value": "co2_pc"})

    valid = set(meta["iso3"])
    df    = meta[["iso3", "name", "region", "income_id"]].copy()
    for d in [fossil, elec, water, food, pm25, gdp, pop, co2]:
        if d.empty or "iso3" not in d.columns:
            continue
        d2 = d[d["iso3"].isin(valid)][["iso3"] + [c for c in d.columns if c not in ("iso3","country")]]
        df = df.merge(d2, on="iso3", how="left")

    _col_defaults = {
        "fossil_pct": 70.0, "elec_access": 85.0, "water_withdrawal": 15.0,
        "undernourishment": 8.0, "pm25": 22.0, "gdp_pc": 5000.0,
        "population": 10_000_000.0, "co2_pc": 4.0,
    }
    for _col, _val in _col_defaults.items():
        if _col not in df.columns:
            df[_col] = _val

    df["heat_score"] = df["iso3"].map(HEAT_SCORE).fillna(DEFAULT_HEAT)

    fp  = df["fossil_pct"].fillna(df["fossil_pct"].median())
    ea  = df["elec_access"].fillna(df["elec_access"].median())
    df["d_energy"] = (fp * 0.55 + (100 - ea) * 0.45).clip(0, 100)

    ww  = df["water_withdrawal"].fillna(df["water_withdrawal"].median())
    df["d_water"] = (ww.clip(0, 150) / 150 * 100).clip(0, 100)

    fn  = df["undernourishment"].fillna(df["undernourishment"].median())
    df["d_food"] = fn.clip(0, 100)

    p25 = df["pm25"].fillna(df["pm25"].median())
    df["d_air"] = (p25 / 80 * 100).clip(0, 100)

    df["d_heat"] = df["heat_score"]

    def _eco(g):
        if pd.isna(g) or g <= 0:
            return 80.0
        return max(0.0, 100.0 - math.log10(g) / math.log10(80_000) * 100)
    df["d_eco"] = df["gdp_pc"].apply(_eco)

    co2v = df["co2_pc"].fillna(df["co2_pc"].median())
    df["d_co2"] = (co2v / 20 * 100).clip(0, 100)

    dim_cols = [v[0] for v in DIMS.values()]
    weights  = [v[2] for v in DIMS.values()]
    df["vulnerability"] = sum(df[col] * w for col, w in zip(dim_cols, weights))
    df["resilience"]    = (100 - df["vulnerability"]).round(1).clip(0, 100)

    return df.dropna(subset=["resilience"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resilience_band(score: float) -> tuple[str, str]:
    for lo, hi, label, color in RESILIENCE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#888"


def _chart_base(h: int = 520, **kw) -> dict:
    base = dict(
        height=h,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#999", size=11),
        margin=dict(l=0, r=0, t=8, b=0),
    )
    base.update(kw)
    return base


def _story_card_html(dim: str) -> str:
    d      = CARD_DATA[dim]
    color  = DIMS[dim][1]
    icon   = ICONS[dim]
    bg     = color + "14"
    return (
        f'<div class="story-card" style="border-left-color:{color}">'
        f'<div class="story-card-top">'
        f'<div class="story-icon" style="background:{bg}">{icon}</div>'
        f'<div>'
        f'<div class="story-stat" style="color:{color}">{d["stat"]}</div>'
        f'<div class="story-stat-lbl">{d["stat_label"]}</div>'
        f'</div>'
        f'</div>'
        f'<div class="story-body">{d["body"]}</div>'
        f'<div class="story-src">{d["source"]}</div>'
        f'</div>'
    )


def _dim_bar_html(name: str, vuln: float) -> str:
    color = DIMS[name][1]
    w     = DIMS[name][2]
    return (
        f'<div class="dim-row">'
        f'<div class="dim-hdr">'
        f'<span>{name} <span class="dim-sub">wt {int(w*100)}%</span></span>'
        f'<span style="color:{color};font-weight:700">{vuln:.0f}</span>'
        f'</div>'
        f'<div class="dim-track">'
        f'<div class="dim-fill" style="width:{min(vuln,100):.0f}%;background:{color}"></div>'
        f'</div>'
        f'</div>'
    )


# ── Tab 1 — Resilience Map ─────────────────────────────────────────────────────

def tab_map(df: pd.DataFrame) -> None:
    n_critical  = int((df["resilience"] < 20).sum())
    n_at_risk   = int((df["resilience"] < 40).sum())
    n_stable    = int((df["resilience"] >= 60).sum())
    n_resilient = int((df["resilience"] >= 80).sum())
    most_r      = df.loc[df["resilience"].idxmax(), "name"]
    least_r     = df.loc[df["resilience"].idxmin(), "name"]

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-scroll-anchor"></span>', unsafe_allow_html=True)
        st.markdown('<div class="lp-inner">', unsafe_allow_html=True)

        st.markdown(
            '<h2 class="lp-title">Resilience Map</h2>'
            '<p class="lp-desc">Composite Country Resilience Score across 7 dimensions '
            'of climate vulnerability — energy, water, food, air, heat, economy, and carbon. '
            '100 = fully resilient · 0 = critical.</p>',
            unsafe_allow_html=True,
        )

        # Polycrisis quote card
        st.markdown(
            '<hr class="lp-sep">'
            '<div class="poly-quote-card">'
            '<div class="poly-byline">Adam Tooze · Foreign Policy · October 2022</div>'
            '<div class="poly-quote">'
            '"Not a crisis, but a polycrisis — where distinct crises interact so that '
            'the whole is <span style="color:#f97316">more harmful than the sum of its parts.</span>"'
            '</div>'
            '<div class="poly-context">'
            f'The {n_at_risk} countries in the red zone face energy stress, water scarcity, '
            'food insecurity, air pollution, and extreme heat — simultaneously, with the '
            'least capacity to adapt. This is the defining challenge of the 2020s.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Polycrisis network illustration
        st.markdown(
            '<div class="lp-sec">The 7-dimension polycrisis network</div>'
            + _POLY_SVG +
            '<p style="font-size:.62rem;color:#ccc;text-align:center;margin:6px 0 0;line-height:1.5">'
            'Each node is a dimension. Lines show compounding relationships.<br>'
            'Countries in the red zone sit at the intersection of all seven.'
            '</p>',
            unsafe_allow_html=True,
        )

        # Score band distribution
        st.markdown('<hr class="lp-sep"><div class="lp-sec">Score distribution</div>', unsafe_allow_html=True)
        for lo, hi, label, color in RESILIENCE_BANDS:
            n = int(((df["resilience"] >= lo) & (df["resilience"] < hi)).sum())
            pct = n / len(df) * 100
            st.markdown(
                f'<div class="band-row">'
                f'<div class="band-dot" style="background:{color}"></div>'
                f'<div class="band-lbl">{label} ({lo}–{hi})</div>'
                f'<div class="band-cnt">{n} <span style="font-size:.6rem;font-weight:400;color:#bbb">({pct:.0f}%)</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Extremes
        st.markdown(
            '<hr class="lp-sep">'
            '<div class="lp-sec">Global extremes</div>'
            f'<div style="display:flex;gap:10px">'
            f'<div style="flex:1;background:#f0fdf4;border-radius:8px;padding:10px 12px;border:1px solid #bbf7d0">'
            f'<div style="font-size:.6rem;color:#16a34a;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px">Most Resilient</div>'
            f'<div style="font-size:.85rem;font-weight:700;color:#111;font-family:Space Grotesk,sans-serif">{most_r}</div>'
            f'<div style="font-size:.65rem;color:#16a34a;margin-top:2px">{df.loc[df["resilience"].idxmax(),"resilience"]:.0f} / 100</div>'
            f'</div>'
            f'<div style="flex:1;background:#fef2f2;border-radius:8px;padding:10px 12px;border:1px solid #fecaca">'
            f'<div style="font-size:.6rem;color:#ef4444;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px">Most Vulnerable</div>'
            f'<div style="font-size:.85rem;font-weight:700;color:#111;font-family:Space Grotesk,sans-serif">{least_r}</div>'
            f'<div style="font-size:.65rem;color:#ef4444;margin-top:2px">{df.loc[df["resilience"].idxmin(),"resilience"]:.0f} / 100</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 7 dimension story cards
        st.markdown('<hr class="lp-sep"><div class="lp-sec">The 7 dimensions — key facts</div>', unsafe_allow_html=True)
        for dim in DIMS:
            st.markdown(_story_card_html(dim), unsafe_allow_html=True)

        # Methodology note
        st.markdown(
            '<hr class="lp-sep">'
            '<div class="lp-note">'
            '<b style="color:#999">Weights:</b> Energy 15% · Water 18% · Food 15% · Air 15% · Heat 15% · Economy 12% · Carbon 10%.<br><br>'
            '<b style="color:#999">Data:</b> World Bank Open Data (most recent year available per country, 2018–2023). '
            'Heat stress: IPCC AR6 WG2 Table 16.SM.1 country-level hazard scores.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rp-inner">', unsafe_allow_html=True)
        st.markdown(
            '<div class="rp-label">Country Resilience Score — Composite 7-Dimension Index</div>',
            unsafe_allow_html=True,
        )

        # Stat pills row
        st.markdown(
            f'<div class="stat-row">'
            f'<div class="stat-pill"><div class="stat-pill-val" style="color:#7f1d1d">{n_critical}</div>'
            f'<div class="stat-pill-lbl">Countries in Critical zone<br>(score &lt; 20)</div></div>'
            f'<div class="stat-pill"><div class="stat-pill-val" style="color:#ef4444">{n_at_risk}</div>'
            f'<div class="stat-pill-lbl">Countries At Risk or worse<br>(score &lt; 40)</div></div>'
            f'<div class="stat-pill"><div class="stat-pill-val" style="color:#16a34a">{n_stable}</div>'
            f'<div class="stat-pill-lbl">Countries Stable or better<br>(score &gt; 60)</div></div>'
            f'<div class="stat-pill"><div class="stat-pill-val">{df["resilience"].mean():.0f}</div>'
            f'<div class="stat-pill-lbl">Global mean resilience<br>score</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Choropleth
        df["band"] = df["resilience"].apply(lambda s: _resilience_band(s)[0])
        fig = px.choropleth(
            df, locations="iso3", color="resilience",
            color_continuous_scale=["#7f1d1d", "#ef4444", "#f59e0b", "#4ade80", "#16a34a"],
            range_color=[0, 100],
            hover_name="name",
            hover_data={"iso3": False, "resilience": ":.0f", "band": True,
                        "d_energy": ":.0f", "d_water": ":.0f", "d_food": ":.0f",
                        "d_air": ":.0f", "d_heat": ":.0f"},
            labels={"resilience": "Resilience", "band": "Status"},
        )
        fig.update_layout(
            **_chart_base(h=460),
            geo=dict(
                showframe=False, showcoastlines=True,
                coastlinecolor="#d4d4d4", bgcolor="rgba(0,0,0,0)",
                showcountries=True, countrycolor="#e5e5e5",
                showocean=True, oceancolor="#dde8f5",
                showlakes=True, lakecolor="#dde8f5",
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Score", font=dict(size=10, color="#aaa")),
                thickness=8, len=0.55, x=1.01,
                tickvals=[0, 20, 40, 60, 80, 100],
                ticktext=["0  Critical", "20", "40", "60", "80", "100  Resilient"],
                tickfont=dict(size=9, color="#aaa"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Context paragraph
        st.markdown(
            '<hr class="rp-divider">'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
            '<div style="background:white;border-radius:8px;padding:14px 16px;border:1px solid rgba(0,0,0,0.06)">'
            '<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#f97316;margin-bottom:8px">The Polycrisis dynamic</div>'
            '<div style="font-size:.74rem;color:#555;line-height:1.7">'
            'Water stress amplifies food insecurity. Heat degrades economic output. Air pollution '
            'overwhelms health systems when they are needed most. The countries scoring lowest face '
            '<b style="color:#111">all seven pressures simultaneously</b> — with the least capacity to adapt.'
            '</div>'
            '</div>'
            '<div style="background:white;border-radius:8px;padding:14px 16px;border:1px solid rgba(0,0,0,0.06)">'
            '<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#3b82f6;margin-bottom:8px">The resilience gap</div>'
            '<div style="font-size:.74rem;color:#555;line-height:1.7">'
            'The most resilient countries are largely temperate, wealthy, and diversified. '
            'The least resilient are disproportionately in the Global South — '
            'contributing the fewest emissions, yet absorbing the highest climate risk. '
            'Resilience today is largely a function of historical accident.'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)


# ── Tab 2 — Country Profile ────────────────────────────────────────────────────

def tab_country(df: pd.DataFrame) -> None:
    left, right = st.columns([1.05, 2.95], gap="large")
    countries   = sorted(df["name"].dropna().unique())
    default     = countries.index("Pakistan") if "Pakistan" in countries else 0

    with left:
        st.markdown('<span class="mc-scroll-anchor"></span>', unsafe_allow_html=True)
        st.markdown('<div class="lp-inner">', unsafe_allow_html=True)

        st.markdown(
            '<h2 class="lp-title">Country Profile</h2>'
            '<p class="lp-desc">Drill into any country across all 7 resilience dimensions. '
            'See where it sits relative to its region and the world.</p>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="lp-sep">', unsafe_allow_html=True)
        sel   = st.selectbox("Select country", countries, index=default, key="cp_country",
                             label_visibility="collapsed")
        row   = df[df["name"] == sel].iloc[0]
        score = row["resilience"]
        band, bcolor = _resilience_band(score)

        st.markdown(
            f'<div class="score-badge" style="background:{bcolor}12;border:1px solid {bcolor}25;margin-top:10px">'
            f'<div class="score-badge-lbl" style="color:{bcolor}">Resilience Score</div>'
            f'<div class="score-badge-val" style="color:{bcolor}">{score:.0f}</div>'
            f'<div class="score-badge-band">{band} · {sel}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Dimension bars
        st.markdown('<div class="lp-sec">Vulnerability by dimension (0 = safe · 100 = critical)</div>',
                    unsafe_allow_html=True)
        for name, (col, color, _) in DIMS.items():
            st.markdown(_dim_bar_html(name, float(row[col])), unsafe_allow_html=True)

        # Narrative card
        vuln_sorted = sorted(DIMS.keys(), key=lambda d: float(row[DIMS[d][0]]), reverse=True)
        top1, top2  = vuln_sorted[0], vuln_sorted[1]
        best1, best2 = vuln_sorted[-1], vuln_sorted[-2]
        region_df   = df[df["region"] == row["region"]]
        reg_avg     = region_df["resilience"].mean()
        global_avg  = df["resilience"].mean()
        reg_rank    = int((region_df["resilience"] > score).sum()) + 1
        reg_total   = len(region_df)

        direction = "above" if score > global_avg else "below"
        gap       = abs(score - global_avg)

        narrative = (
            f"{sel}'s most acute vulnerabilities are "
            f"<b style='color:{DIMS[top1][1]}'>{top1.lower()}</b> and "
            f"<b style='color:{DIMS[top2][1]}'>{top2.lower()}</b>. "
            f"Its strongest dimensions are {best1.lower()} and {best2.lower()}. "
            f"At {score:.0f}/100, it ranks #{reg_rank} of {reg_total} in its region "
            f"and sits {gap:.0f} points {direction} the global average of {global_avg:.0f}."
        )
        st.markdown(
            '<hr class="lp-sep">'
            '<div class="narrative-card">'
            '<div class="narrative-label">Country narrative</div>'
            f'<div class="narrative-body">{narrative}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Region comparison summary
        st.markdown(
            '<hr class="lp-sep">'
            f'<div style="display:flex;gap:10px">'
            f'<div style="flex:1;background:#f8f9fa;border-radius:8px;padding:10px 12px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.6rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Region avg</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">{reg_avg:.0f}</div>'
            f'<div style="font-size:.62rem;color:#bbb;margin-top:2px">{row["region"].split("&")[0].strip()[:18]}</div>'
            f'</div>'
            f'<div style="flex:1;background:#f8f9fa;border-radius:8px;padding:10px 12px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.6rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Global avg</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">{global_avg:.0f}</div>'
            f'<div style="font-size:.62rem;color:#bbb;margin-top:2px">All {len(df)} countries</div>'
            f'</div>'
            f'<div style="flex:1;background:#f8f9fa;border-radius:8px;padding:10px 12px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.6rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Region rank</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">#{reg_rank}</div>'
            f'<div style="font-size:.62rem;color:#bbb;margin-top:2px">of {reg_total} in region</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # What this means card
        st.markdown(
            '<hr class="lp-sep">'
            '<div class="lp-note" style="font-size:.67rem;color:#777;line-height:1.7">'
            '<b style="color:#555">Reading the radar:</b> each axis shows vulnerability (0 = none, 100 = critical). '
            'A smaller, tighter shape is better. The dotted rings show the world average (~50) '
            'and high-risk threshold (75). The bar chart compares this country against its region peers.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rp-inner">', unsafe_allow_html=True)

        dim_names  = list(DIMS.keys())
        dim_cols   = [v[0] for v in DIMS.values()]
        dim_colors = [v[1] for v in DIMS.values()]
        vuln_vals  = [float(row[c]) for c in dim_cols]
        cats       = dim_names + [dim_names[0]]
        vals       = vuln_vals + [vuln_vals[0]]

        st.markdown(f'<div class="rp-label">Vulnerability Radar — {sel}</div>', unsafe_allow_html=True)

        rfig = go.Figure()
        # Fill per-dimension in dimension color (subtle)
        rfig.add_trace(go.Scatterpolar(
            r=vals, theta=cats, fill="toself",
            fillcolor="rgba(239,68,68,0.10)", line=dict(color="#ef4444", width=2),
            name=sel, hovertemplate="%{theta}: %{r:.0f} vulnerability<extra></extra>",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[50] * len(cats), theta=cats,
            line=dict(color="#94a3b8", width=1, dash="dot"),
            mode="lines", name="World avg (~50)", hoverinfo="skip",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[75] * len(cats), theta=cats,
            line=dict(color="#dc2626", width=1, dash="dot"),
            mode="lines", name="High-risk (75)", hoverinfo="skip",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(
                    range=[0, 100],
                    tickvals=[25, 50, 75],
                    tickfont=dict(size=9, color="#ccc"),
                    gridcolor="rgba(0,0,0,0.06)",
                    linecolor="rgba(0,0,0,0.06)",
                ),
                angularaxis=dict(tickfont=dict(size=11.5, color="#444")),
                bgcolor="rgba(0,0,0,0)",
            ),
            **_chart_base(h=380, margin=dict(l=30, r=30, t=20, b=40)),
            legend=dict(
                orientation="h", y=-0.12, x=0.5, xanchor="center",
                font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)",
            ),
        )
        st.plotly_chart(rfig, use_container_width=True)

        # Regional comparison bar
        st.markdown(
            f'<hr class="rp-divider">'
            f'<div class="rp-label">Regional comparison — {row["region"]}</div>',
            unsafe_allow_html=True,
        )
        reg_df = (df[df["region"] == row["region"]]
                  .sort_values("resilience").head(25).copy())
        reg_df["highlight"] = reg_df["name"] == sel
        cfig = px.bar(
            reg_df, x="resilience", y="name", orientation="h",
            color="highlight",
            color_discrete_map={True: "#ef4444", False: "#d1d5db"},
            labels={"resilience": "Resilience Score", "name": ""},
            text="resilience",
        )
        cfig.update_traces(
            texttemplate="%{x:.0f}", textposition="outside",
            textfont=dict(size=9, color="#aaa"),
        )
        cfig.update_layout(
            **_chart_base(h=max(280, len(reg_df) * 26), margin=dict(l=0, r=60, t=0, b=0)),
            xaxis=dict(range=[0, 106], gridcolor="rgba(0,0,0,0.05)",
                       color="#ccc", tickfont=dict(size=10),
                       title=dict(text="Resilience Score (100 = fully resilient)", font=dict(size=10, color="#bbb"))),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10.5)),
            showlegend=False,
        )
        st.plotly_chart(cfig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Tab 3 — Crisis Correlations ───────────────────────────────────────────────

# Short "why they correlate" text for the top pairs
_CORR_WHY = {
    ("Energy", "Economy"):  "Energy poverty and economic underdevelopment are deeply co-determined — each entrenches the other.",
    ("Energy", "Air"):      "Burning fossil fuels for power is the primary source of PM2.5 pollution in most developing nations.",
    ("Water", "Food"):      "70% of freshwater withdrawal globally is for agriculture. When aquifers fail, harvests fail.",
    ("Food", "Economy"):    "Food insecurity is both a symptom of poverty and a drag on it — hungry populations cannot build adaptive capacity.",
    ("Air", "Economy"):     "Air pollution costs 5–6% of GDP in high-exposure economies through lost productivity and healthcare burden.",
    ("Heat", "Economy"):    "Heat reduces agricultural and outdoor labour productivity, compressing GDP in the regions most exposed.",
    ("Heat", "Water"):      "Higher temperatures accelerate evaporation and glacial melt — amplifying water stress directly.",
    ("Water", "Economy"):   "Water scarcity raises food costs, energy costs, and industrial costs simultaneously.",
    ("Food", "Air"):        "Crop-burning is a major PM2.5 source in South and Southeast Asia — food and air crises share causes.",
    ("Energy", "Water"):    "Thermoelectric power plants require vast cooling water; water scarcity directly threatens grid reliability.",
}


def tab_correlations(df: pd.DataFrame) -> None:
    dim_cols  = [v[0] for v in DIMS.values()]
    dim_names = list(DIMS.keys())
    corr      = df[dim_cols].rename(columns={v[0]: k for k, v in DIMS.items()}).corr()

    pairs = []
    for i, a in enumerate(dim_names):
        for j, b in enumerate(dim_names):
            if i < j:
                r_val = corr.loc[a, b]
                if not math.isnan(r_val):
                    pairs.append((abs(r_val), r_val, a, b))
    pairs.sort(reverse=True)

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-scroll-anchor"></span>', unsafe_allow_html=True)
        st.markdown('<div class="lp-inner">', unsafe_allow_html=True)

        st.markdown(
            '<h2 class="lp-title">Crisis Correlations</h2>'
            '<p class="lp-desc">When crises cluster, they compound. Countries at the intersection '
            'of multiple high-correlation dimensions face cascading failures — '
            'one system\'s collapse accelerates the others.</p>',
            unsafe_allow_html=True,
        )

        # Multiplier concept card
        st.markdown(
            '<hr class="lp-sep">'
            '<div style="background:#fff7f0;border-radius:10px;padding:16px;border:1px solid rgba(249,115,22,0.15);border-left:3px solid #f97316;margin-bottom:14px">'
            '<div style="font-size:.65rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#f97316;margin-bottom:8px">The compounding dynamic</div>'
            '<div style="font-size:.8rem;font-weight:700;color:#111;font-family:Space Grotesk,sans-serif;line-height:1.4;margin-bottom:8px">'
            'Not A + B + C, but A × B × C.'
            '</div>'
            '<div style="font-size:.72rem;color:#555;line-height:1.7">'
            'Water stress raises food prices. Food insecurity undercuts economic stability. '
            'Economic weakness limits energy investment. Energy deficits worsen air quality. '
            'Air pollution degrades health. Degraded health reduces labour capacity. '
            'Each crisis feeds back into the others — the loop tightens.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Insight cards for strongest pairs
        st.markdown('<div class="lp-sec">Strongest co-occurrence pairs</div>', unsafe_allow_html=True)
        shown = 0
        for abs_r, r, a, b in pairs[:8]:
            if shown >= 6:
                break
            arrow  = "↑↑" if r > 0 else "↑↓"
            bar_w  = int(abs_r * 100)
            key    = (a, b) if (a, b) in _CORR_WHY else (b, a)
            why    = _CORR_WHY.get(key, "These dimensions frequently affect the same countries.")
            ca, cb = DIMS[a][1], DIMS[b][1]
            st.markdown(
                f'<div class="insight-card">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">'
                f'<div class="insight-pair">'
                f'<span style="color:{ca}">{a}</span>'
                f'<span style="color:#ccc;font-weight:400;margin:0 5px">+</span>'
                f'<span style="color:{cb}">{b}</span>'
                f'</div>'
                f'<div class="insight-r">{r:.2f} {arrow}</div>'
                f'</div>'
                f'<div class="insight-why">{why}</div>'
                f'<div class="insight-bar"><div class="insight-fill" style="width:{bar_w}%"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            shown += 1

        # Interpretation note
        st.markdown(
            '<hr class="lp-sep">'
            '<div style="background:#f8fafc;border-radius:8px;padding:12px 14px;border:1px solid rgba(0,0,0,0.06)">'
            '<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;margin-bottom:6px">How to read the heatmap →</div>'
            '<div style="font-size:.7rem;color:#64748b;line-height:1.7">'
            '<b style="color:#ef4444">Deep red (+1.0):</b> crises always strike together.<br>'
            '<b style="color:#475569">Near zero:</b> crises are independent.<br>'
            '<b style="color:#3b82f6">Deep blue (−1.0):</b> one crisis means less of the other.<br><br>'
            'High positive correlation = policy leverage: fixing one dimension often helps others.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rp-inner">', unsafe_allow_html=True)
        st.markdown(
            '<div class="rp-label">Crisis Correlation Matrix — Pearson r between all 7 dimensions</div>',
            unsafe_allow_html=True,
        )

        hfig = px.imshow(
            corr,
            color_continuous_scale=["#dbeafe", "#f8fafc", "#fef2f2"],
            zmin=-1, zmax=1,
            text_auto=".2f",
            labels=dict(color="Pearson r"),
        )
        hfig.update_traces(textfont=dict(size=12, color="#333"))
        hfig.update_layout(
            **_chart_base(h=420, margin=dict(l=80, r=20, t=8, b=80)),
            xaxis=dict(tickfont=dict(size=12, color="#555"), side="bottom"),
            yaxis=dict(tickfont=dict(size=12, color="#555")),
            coloraxis_colorbar=dict(
                title=dict(text="r", font=dict(size=10, color="#aaa")),
                thickness=8, tickfont=dict(size=9, color="#aaa"),
                tickvals=[-1, -0.5, 0, 0.5, 1],
            ),
        )
        st.plotly_chart(hfig, use_container_width=True)

        if not pairs:
            st.markdown('</div>', unsafe_allow_html=True)
            return

        top_a, top_b = pairs[0][2], pairs[0][3]
        top_r  = pairs[0][1]
        col_a  = DIMS[top_a][0]
        col_b  = DIMS[top_b][0]
        color_a = DIMS[top_a][1]

        st.markdown(
            f'<hr class="rp-divider">'
            f'<div class="rp-label">Strongest pair: {top_a} vs {top_b} (r = {top_r:.2f})</div>',
            unsafe_allow_html=True,
        )
        _pop_col = "population" if "population" in df.columns else None
        sfig = px.scatter(
            df.dropna(subset=[col_a, col_b]),
            x=col_a, y=col_b, size=_pop_col, color="region",
            hover_name="name",
            labels={col_a: f"{top_a} vulnerability (0–100)",
                    col_b: f"{top_b} vulnerability (0–100)"},
            size_max=36,
            color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155",
                                      "#1e293b","#0f172a","#ef4444"],
        )
        sfig.update_layout(
            **_chart_base(h=310),
            xaxis=dict(gridcolor="rgba(0,0,0,0.05)", color="#ccc",
                       tickfont=dict(size=10),
                       title=dict(font=dict(size=10, color="#bbb"))),
            yaxis=dict(gridcolor="rgba(0,0,0,0.05)", color="#ccc",
                       tickfont=dict(size=10),
                       title=dict(font=dict(size=10, color="#bbb"))),
            legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(sfig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Tab 4 — Rankings ──────────────────────────────────────────────────────────

def tab_rankings(df: pd.DataFrame) -> None:
    left, right = st.columns([1.05, 2.95], gap="large")
    regions     = ["All regions"] + sorted(df["region"].dropna().unique())

    bottom10 = df.nsmallest(10, "resilience")
    top10    = df.nlargest(10, "resilience")

    with left:
        st.markdown('<span class="mc-scroll-anchor"></span>', unsafe_allow_html=True)
        st.markdown('<div class="lp-inner">', unsafe_allow_html=True)

        st.markdown(
            '<h2 class="lp-title">Rankings</h2>'
            '<p class="lp-desc">Countries ranked by composite resilience. Filter by region '
            'to compare within peer groups. Hover any bar for dimension-level detail.</p>',
            unsafe_allow_html=True,
        )

        # Most / least resilient cards
        st.markdown('<hr class="lp-sep"><div class="lp-sec">Top extremes</div>', unsafe_allow_html=True)
        for i in range(3):
            r_row = top10.iloc[i]
            v_row = bottom10.iloc[i]
            rb, rc = _resilience_band(r_row["resilience"])
            vb, vc = _resilience_band(v_row["resilience"])
            st.markdown(
                f'<div style="display:flex;gap:8px;margin-bottom:8px">'
                f'<div style="flex:1;background:{rc}12;border-radius:8px;padding:9px 11px;border-left:3px solid {rc}">'
                f'<div style="font-size:.6rem;color:{rc};font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px">#{i+1} resilient</div>'
                f'<div style="font-size:.82rem;font-weight:700;color:#111">{r_row["name"].split(",")[0]}</div>'
                f'<div style="font-size:.68rem;color:{rc};font-weight:700">{r_row["resilience"]:.0f}</div>'
                f'</div>'
                f'<div style="flex:1;background:{vc}12;border-radius:8px;padding:9px 11px;border-left:3px solid {vc}">'
                f'<div style="font-size:.6rem;color:{vc};font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px">#{i+1} vulnerable</div>'
                f'<div style="font-size:.82rem;font-weight:700;color:#111">{v_row["name"].split(",")[0]}</div>'
                f'<div style="font-size:.68rem;color:{vc};font-weight:700">{v_row["resilience"]:.0f}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Filter controls
        st.markdown('<hr class="lp-sep"><div class="lp-sec">Filter &amp; view</div>', unsafe_allow_html=True)
        region_sel = st.selectbox("Region", regions, key="rk_region", label_visibility="collapsed")
        view       = st.radio("Show", ["Most vulnerable", "Most resilient", "All countries"],
                              key="rk_view", label_visibility="collapsed")

        # Distribution callout
        n_crit = int((df["resilience"] < 20).sum())
        n_risk = int((df["resilience"] < 40).sum())
        n_good = int((df["resilience"] > 60).sum())
        st.markdown(
            '<hr class="lp-sep">'
            f'<div style="background:#fef2f2;border-radius:8px;padding:12px 14px;border:1px solid #fecaca;margin-bottom:10px">'
            f'<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#ef4444;margin-bottom:6px">Risk distribution</div>'
            f'<div style="font-size:.73rem;color:#555;line-height:1.7">'
            f'<b style="color:#7f1d1d">{n_crit} countries</b> are in the Critical zone (score &lt; 20). '
            f'<b style="color:#ef4444">{n_risk}</b> are At Risk or worse. '
            f'Only <b style="color:#16a34a">{n_good}</b> score above 60 (Stable or better). '
            f'The distribution is heavily skewed toward vulnerability.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="lp-note">Score = 100 − weighted vulnerability. '
            'Hover a bar for per-dimension scores. '
            'Colour encodes resilience: dark red = critical, dark green = resilient.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rp-inner">', unsafe_allow_html=True)
        fdf = df if region_sel == "All regions" else df[df["region"] == region_sel]

        if view == "Most vulnerable":
            plot_df = fdf.nsmallest(30, "resilience").sort_values("resilience")
            lbl     = f"Bottom 30 — Most Vulnerable{'  ·  ' + region_sel if region_sel != 'All regions' else ''}"
        elif view == "Most resilient":
            plot_df = fdf.nlargest(30, "resilience").sort_values("resilience")
            lbl     = f"Top 30 — Most Resilient{'  ·  ' + region_sel if region_sel != 'All regions' else ''}"
        else:
            plot_df = fdf.sort_values("resilience")
            lbl     = f"All Countries{'  ·  ' + region_sel if region_sel != 'All regions' else ''}"

        st.markdown(f'<div class="rp-label">{lbl}</div>', unsafe_allow_html=True)
        dim_hover = {v[0]: ":.0f" for v in DIMS.values()}
        bfig = px.bar(
            plot_df, x="resilience", y="name", orientation="h",
            color="resilience",
            color_continuous_scale=["#7f1d1d", "#ef4444", "#f59e0b", "#4ade80", "#16a34a"],
            range_color=[0, 100],
            labels={"resilience": "Resilience Score", "name": ""},
            hover_data=dim_hover,
            text="resilience",
        )
        bfig.update_traces(
            texttemplate="%{x:.0f}", textposition="outside",
            textfont=dict(size=9, color="#aaa"),
        )
        bfig.update_layout(
            **_chart_base(h=max(520, len(plot_df) * 22), margin=dict(l=0, r=60, t=0, b=0)),
            xaxis=dict(
                range=[0, 108],
                title=dict(text="Resilience Score (100 = fully resilient)", font=dict(size=10, color="#bbb")),
                gridcolor="rgba(0,0,0,0.05)", color="#ccc", tickfont=dict(size=10),
            ),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10.5)),
            coloraxis_showscale=False,
        )
        st.plotly_chart(bfig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="mc-header">'
        '<div class="mc-topline"><span class="mc-dot"></span>'
        'POLYCRISIS DASHBOARD · DAY 10 · THE RESILIENCE STACK'
        '</div>'
        '<div class="mc-header-right">7 dimensions · 190+ countries · World Bank + IPCC data</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Building Country Resilience Scores from 8 World Bank indicators…"):
        df = load_polycrisis_data()

    if df.empty:
        st.error("Failed to load data from World Bank. Please try again.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Resilience Map",
        "Country Profile",
        "Crisis Correlations",
        "Rankings",
    ])

    with tab1: tab_map(df)
    with tab2: tab_country(df)
    with tab3: tab_correlations(df)
    with tab4: tab_rankings(df)


if __name__ == "__main__":
    main()
