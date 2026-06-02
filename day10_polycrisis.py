"""
The Resilience Stack — Day 10
The Polycrisis Dashboard

Composite Country Resilience Score across 7 climate-risk dimensions.
"Polycrisis" — Adam Tooze 2022: multiple crises compound and reinforce each other.

Sources: World Bank Open Data + IPCC AR6 WG2
"""

import math
import streamlit as st
import streamlit.components.v1 as components
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

DIMS = {
    "Energy":  ("d_energy", "#f97316", 0.15),
    "Water":   ("d_water",  "#3b82f6", 0.18),
    "Food":    ("d_food",   "#ca8a04", 0.15),
    "Air":     ("d_air",    "#8b5cf6", 0.15),
    "Heat":    ("d_heat",   "#ef4444", 0.15),
    "Economy": ("d_eco",    "#64748b", 0.12),
    "Carbon":  ("d_co2",    "#16a34a", 0.10),
}

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

CARD_DATA = {
    "Energy":  {"stat": "733M",   "lbl": "without electricity",         "body": "Half in Sub-Saharan Africa — energy poverty shapes every downstream crisis, from food storage to vaccine refrigeration.",                 "src": "IEA World Energy Outlook 2023"},
    "Water":   {"stat": "4B",     "lbl": "face severe water scarcity",  "body": "Agriculture consumes 70% of all freshwater drawn — when aquifers fail, crops fail, and people move.",                                   "src": "Mekonnen & Hoekstra, Science Advances 2016"},
    "Food":    {"stat": "733M",   "lbl": "face hunger daily",           "body": "Three countries supply 40% of world wheat — one drought cascades into 50 price spikes felt across billions of plates.",                  "src": "FAO State of Food Security 2023"},
    "Air":     {"stat": "99%",    "lbl": "breathe air above WHO limits","body": "PM2.5 kills 7 million per year — more than AIDS, malaria, and tuberculosis combined.",                                                    "src": "WHO Air Quality Database 2022"},
    "Heat":    {"stat": "3.5B",   "lbl": "in climate-vulnerable areas", "body": "35°C wet-bulb is physiologically unsurvivable in 6 hours — and 2 billion will face this threshold by 2050.",                           "src": "IPCC AR6 WG2 Summary, 2022"},
    "Economy": {"stat": "10–23%", "lbl": "potential GDP loss by 2100",  "body": "The most exposed countries contribute less than 5% of cumulative emissions — adaptive capacity is the inverse of vulnerability.",       "src": "Swiss Re Institute, 2021"},
    "Carbon":  {"stat": "Top 1%", "lbl": "emit = bottom 50% combined", "body": "Ten countries drive 68% of emissions, yet the severest impacts land on those who caused the least.",                                     "src": "World Inequality Report, Chancel 2022"},
}

ICONS = {
    "Energy":  '<svg width="18" height="18" viewBox="0 0 24 24" fill="#f97316"><path d="M13 2L4.09 12.97H12L11 22L19.91 11.03H12L13 2Z"/></svg>',
    "Water":   '<svg width="18" height="18" viewBox="0 0 24 24" fill="#3b82f6"><path d="M12 2C6.48 10 4 13.5 4 16a8 8 0 0 0 16 0c0-2.5-2.48-6-8-14z"/></svg>',
    "Food":    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" stroke-width="2" stroke-linecap="round"><line x1="12" y1="22" x2="12" y2="10"/><path d="M9 5c0 3 3 5 3 5s3-2 3-5a3 3 0 0 0-6 0z"/><path d="M9 11c0 3 3 5 3 5s3-2 3-5"/></svg>',
    "Air":     '<svg width="18" height="18" viewBox="0 0 24 24" fill="#8b5cf6"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>',
    "Heat":    '<svg width="18" height="18" viewBox="0 0 24 24" fill="#ef4444"><path d="M12 2C9.5 6 8 8.5 8 11a4 4 0 0 0 8 0c0-2.5-1.5-5-4-9z"/><circle cx="12" cy="18" r="3"/><line x1="12" y1="15" x2="12" y2="11" stroke="#ef4444" stroke-width="2"/></svg>',
    "Economy": '<svg width="18" height="18" viewBox="0 0 24 24" fill="#64748b"><rect x="2" y="14" width="4" height="8" rx="1"/><rect x="9" y="9" width="4" height="13" rx="1"/><rect x="16" y="4" width="4" height="18" rx="1"/></svg>',
    "Carbon":  '<svg width="18" height="18" viewBox="0 0 24 24" fill="#16a34a"><path d="M17 8C8 10 5.9 16.17 3.82 22.5"/><path d="M10.99 8.99c-1.49.9-1.99 1.6-1.99 2.41v3.5"/><path d="M14 9.8l.67.68a2.3 2.3 0 0 1 .33 3.41L12 16.11"/><path d="M16.5 8.5l1.88 1.88a4 4 0 0 1 0 5.66L15 19.42"/></svg>',
}

_POLY_SVG = """<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" style="width:180px;display:block;margin:8px auto">
  <polygon points="100,30 156,56 169,117 130,166 70,166 31,117 44,56" fill="none" stroke="#e5e7eb" stroke-width="1"/>
  <line x1="100" y1="100" x2="100"  y2="30"  stroke="#f97316" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="156"  y2="56"  stroke="#3b82f6" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="169"  y2="117" stroke="#ca8a04" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="130"  y2="166" stroke="#8b5cf6" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="70"   y2="166" stroke="#ef4444" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="31"   y2="117" stroke="#64748b" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="100" x2="44"   y2="56"  stroke="#16a34a" stroke-width="1.2" opacity="0.4"/>
  <line x1="100" y1="30"  x2="169"  y2="117" stroke="#f97316" stroke-width="0.6" opacity="0.15" stroke-dasharray="3,3"/>
  <line x1="156" y1="56"  x2="130"  y2="166" stroke="#3b82f6" stroke-width="0.6" opacity="0.15" stroke-dasharray="3,3"/>
  <line x1="31"  y1="117" x2="100"  y2="30"  stroke="#64748b" stroke-width="0.6" opacity="0.15" stroke-dasharray="3,3"/>
  <circle cx="100" cy="100" r="20" fill="#f8f9fa" stroke="#e5e7eb" stroke-width="1"/>
  <text x="100" y="97"  text-anchor="middle" font-family="'Space Grotesk',sans-serif" font-size="6.5" font-weight="800" fill="#374151">POLY</text>
  <text x="100" y="107" text-anchor="middle" font-family="'Space Grotesk',sans-serif" font-size="6.5" font-weight="800" fill="#374151">CRISIS</text>
  <circle cx="100" cy="30"  r="14" fill="#fff7ed" stroke="#f97316" stroke-width="1.5"/>
  <text x="100" y="34"  text-anchor="middle" font-family="Inter,sans-serif" font-size="6" font-weight="700" fill="#ea580c">ENERGY</text>
  <circle cx="156" cy="56"  r="14" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
  <text x="156" y="60"  text-anchor="middle" font-family="Inter,sans-serif" font-size="6" font-weight="700" fill="#2563eb">WATER</text>
  <circle cx="169" cy="117" r="14" fill="#fffbeb" stroke="#ca8a04" stroke-width="1.5"/>
  <text x="169" y="121" text-anchor="middle" font-family="Inter,sans-serif" font-size="6" font-weight="700" fill="#b45309">FOOD</text>
  <circle cx="130" cy="166" r="14" fill="#f5f3ff" stroke="#8b5cf6" stroke-width="1.5"/>
  <text x="130" y="170" text-anchor="middle" font-family="Inter,sans-serif" font-size="6" font-weight="700" fill="#7c3aed">AIR</text>
  <circle cx="70"  cy="166" r="14" fill="#fef2f2" stroke="#ef4444" stroke-width="1.5"/>
  <text x="70"  y="170" text-anchor="middle" font-family="Inter,sans-serif" font-size="6" font-weight="700" fill="#dc2626">HEAT</text>
  <circle cx="31"  cy="117" r="14" fill="#f8fafc" stroke="#64748b" stroke-width="1.5"/>
  <text x="31"  y="121" text-anchor="middle" font-family="Inter,sans-serif" font-size="5.5" font-weight="700" fill="#475569">ECON</text>
  <circle cx="44"  cy="56"  r="14" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
  <text x="44"  y="60"  text-anchor="middle" font-family="Inter,sans-serif" font-size="5.5" font-weight="700" fill="#15803d">CO₂</text>
</svg>"""

# ── CSS ────────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1a1a1a; }
#MainMenu, header[data-testid="stHeader"], footer { display: none !important; }

/* ── Full-viewport scroll lock ─────────────────────── */
html { overflow: hidden !important; }
.stApp,
[data-testid="stAppViewContainer"],
section.main { height: 100vh !important; overflow: hidden !important; }

[data-testid="block-container"] {
  height: 100vh !important; overflow: hidden !important; padding: 0 !important;
  max-width: 100% !important; display: flex !important; flex-direction: column !important;
}

/* ── Tabs flex chain ───────────────────────────────── */
[data-testid="stTabs"] {
  flex: 1 1 0% !important; min-height: 0 !important; overflow: hidden !important;
  display: flex !important; flex-direction: column !important;
}
[data-baseweb="tab-list"] { flex-shrink: 0 !important; }
[data-testid="stTabsContent"] {
  flex: 1 1 0% !important; min-height: 0 !important; overflow: hidden !important;
}
/* All wrapper divs between stTabsContent and stHorizontalBlock */
[data-testid="stTabsContent"] > div,
[data-testid="stTabsContent"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stTabsContent"] [data-testid="stVerticalBlock"] {
  height: 100% !important; min-height: 0 !important; overflow: hidden !important;
}

/* ── Two-column independent scroll ────────────────── */
[data-testid="stHorizontalBlock"]:has(.mc-anchor) {
  height: 100% !important; min-height: 0 !important;
  overflow: hidden !important; align-items: stretch !important;
  gap: 0 !important; flex-wrap: nowrap !important;
}
/* Target Streamlit 1.37+ column testid */
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="stColumn"],
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="column"] {
  min-height: 0 !important; overflow-y: auto !important; overflow-x: hidden !important;
  padding: 0 !important; margin: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="stColumn"]:first-child,
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="column"]:first-child {
  background: #ffffff !important; border-right: 1px solid rgba(0,0,0,0.07) !important;
}
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="stColumn"]:last-child,
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="column"]:last-child {
  background: #f0f0f0 !important;
}
/* Thin scrollbars */
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="stColumn"]::-webkit-scrollbar,
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="column"]::-webkit-scrollbar { width: 3px; }
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="stColumn"]::-webkit-scrollbar-thumb,
[data-testid="stHorizontalBlock"]:has(.mc-anchor) > [data-testid="column"]::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.14); border-radius: 2px;
}

/* ── Header ─────────────────────────────────────────── */
.mc-header {
  background: #fff; border-bottom: 1px solid rgba(0,0,0,0.07);
  padding: 13px 30px; display: flex; align-items: center;
  justify-content: space-between; flex-shrink: 0;
}
.mc-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .18em;
  text-transform: uppercase; color: #bbb; display: flex; align-items: center; gap: 8px;
}
.mc-dot { width: 8px; height: 8px; border-radius: 50%; background: #f97316; display: inline-block; }
.mc-header-right { font-size: .68rem; color: #ccc; font-weight: 500; }

/* ── Tab bar ──────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: #fff !important; padding: 0 22px !important; gap: 0 !important;
  border-bottom: 1px solid rgba(0,0,0,0.07) !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: #bbb !important;
  font-size: 10.5px !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: .1em !important;
  padding: 12px 20px !important; border: none !important; border-radius: 0 !important;
}
.stTabs [aria-selected="true"] { color: #111 !important; border-bottom: 2.5px solid #111 !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none !important; }
[data-testid="stTabsContent"] { padding: 0 !important; }

/* ── Left panel typographic ──────────────────────── */
.mc-anchor { display: none !important; }
.lp-sep  { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 14px 0; }
.lp-sec  { font-size: .63rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .12em; margin-bottom: 10px; }
.lp-note { font-size: .63rem; color: #bbb; line-height: 1.65; }
.lp-title { font-family: 'Space Grotesk',sans-serif; font-size: 1.18rem; font-weight: 800; color: #111; letter-spacing: -.3px; line-height: 1.2; margin: 0 0 .35rem; }
.lp-desc  { font-size: .74rem; color: #999; line-height: 1.7; margin: 0; }

/* ── Story cards ─────────────────────────────────── */
.sc {
  border-radius: 8px; padding: 11px 12px 10px; margin-bottom: 8px;
  background: #fafafa; border: 1px solid rgba(0,0,0,0.06); border-left-width: 3px;
}
.sc-top  { display: flex; align-items: center; gap: 9px; margin-bottom: 6px; }
.sc-icon { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.sc-stat { font-family: 'Space Grotesk',sans-serif; font-size: 1.25rem; font-weight: 900; line-height: 1; letter-spacing: -.4px; }
.sc-lbl  { font-size: .62rem; color: #999; margin-top: 2px; }
.sc-body { font-size: .69rem; color: #555; line-height: 1.62; margin-bottom: 5px; }
.sc-src  { font-size: .6rem; color: #ccc; font-style: italic; }

/* ── Score badge ─────────────────────────────────── */
.sb { border-radius: 9px; padding: 12px 14px; }
.sb-lbl { font-size: .63rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 2px; }
.sb-val { font-family: 'Space Grotesk',sans-serif; font-size: 2.8rem; font-weight: 900; line-height: 1; letter-spacing: -2px; }
.sb-sub { font-size: .78rem; font-weight: 600; margin-top: 4px; color: #555; }

/* ── Dim bars ────────────────────────────────────── */
.db  { margin-bottom: 8px; }
.db-h { display: flex; justify-content: space-between; font-size: .7rem; font-weight: 600; color: #444; margin-bottom: 3px; }
.db-t { background: rgba(0,0,0,0.06); border-radius: 3px; height: 5px; overflow: hidden; }
.db-f { height: 100%; border-radius: 3px; }

/* ── Polycrisis card ─────────────────────────────── */
.poly-card { background: linear-gradient(135deg, #0f172a, #1e293b); border-radius: 10px; padding: 15px 17px; margin-bottom: 12px; }
.poly-by   { font-size: .6rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: #f97316; margin-bottom: 8px; }
.poly-q    { font-family: 'Space Grotesk',sans-serif; font-size: .92rem; font-weight: 700; color: #f8fafc; line-height: 1.45; margin-bottom: 8px; }
.poly-sub  { font-size: .68rem; color: rgba(248,250,252,.42); line-height: 1.62; }

/* ── Right panel ─────────────────────────────────── */
.rp-lbl { font-size: .63rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #bbb; margin-bottom: 5px; }
.rp-sep { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 12px 0; }

/* ── Stat pills ──────────────────────────────────── */
.sp-row { display: flex; gap: 8px; flex-wrap: nowrap; margin-bottom: 4px; }
.sp { background: white; border-radius: 8px; padding: 9px 11px; border: 1px solid rgba(0,0,0,0.07); flex: 1; min-width: 0; }
.sp-val { font-family: 'Space Grotesk',sans-serif; font-size: 1.2rem; font-weight: 800; color: #111; line-height: 1; }
.sp-lbl { font-size: .6rem; color: #bbb; margin-top: 3px; line-height: 1.3; }

/* ── Band legend ─────────────────────────────────── */
.bl-row { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.bl-dot { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
.bl-lbl { font-size: .69rem; color: #555; flex: 1; }
.bl-cnt { font-size: .69rem; font-weight: 700; color: #333; }

/* ── Insight cards ───────────────────────────────── */
.ic { background: white; border-radius: 7px; padding: 10px 12px; margin-bottom: 6px; border: 1px solid rgba(0,0,0,0.06); }
.ic-body { font-size: .67rem; color: #777; line-height: 1.52; margin-top: 4px; }

/* ── Narrative card ──────────────────────────────── */
.nc { background: linear-gradient(135deg,#f8fafc,#f1f5f9); border-radius: 8px; border: 1px solid rgba(0,0,0,0.06); padding: 11px 13px; }
.nc-l { font-size: .61rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #94a3b8; margin-bottom: 5px; }
.nc-b { font-size: .71rem; color: #475569; line-height: 1.65; }

/* ── Widget cleanup ──────────────────────────────── */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .74rem !important; font-weight: 600 !important; color: #333 !important;
}
[data-baseweb="select"] > div {
  background: white !important; border: 1px solid rgba(0,0,0,0.11) !important;
  border-radius: 6px !important; font-size: .75rem !important;
}
/* Collapse Streamlit's default vertical gaps inside our panels */
[data-testid="stHorizontalBlock"]:has(.mc-anchor) [data-testid="stMarkdown"],
[data-testid="stHorizontalBlock"]:has(.mc-anchor) .stMarkdown { margin-bottom: 0 !important; }
</style>
"""

# ── JS scroll fix (imperative fallback via iframe → parent DOM) ────────────────
_JS = """
<script>
(function(){
  function fix(){
    try{
      var p=window.parent.document;
      var aa=p.querySelectorAll('.mc-anchor');
      if(!aa.length){setTimeout(fix,250);return;}
      aa.forEach(function(a){
        var h=a.closest('[data-testid="stHorizontalBlock"]');
        if(!h)return;
        var hdr=p.querySelector('.mc-header');
        var tabs=p.querySelector('[data-baseweb="tab-list"]');
        var hh=hdr?hdr.getBoundingClientRect().height:52;
        var th=tabs?tabs.getBoundingClientRect().height:44;
        var av=window.parent.innerHeight-hh-th-2;
        h.style.height=av+'px';h.style.minHeight='0';
        h.style.overflow='hidden';h.style.alignItems='stretch';h.style.gap='0';
        var cs=h.querySelectorAll('[data-testid="stColumn"],[data-testid="column"]');
        cs.forEach(function(c,i){
          c.style.minHeight='0';c.style.overflowY='auto';
          c.style.overflowX='hidden';c.style.padding='0';
          c.style.background=i===0?'#ffffff':'#f0f0f0';
          if(i===0)c.style.borderRight='1px solid rgba(0,0,0,0.07)';
          c.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stVerticalBlock"]')
           .forEach(function(w){w.style.minHeight='0';});
        });
      });
    }catch(e){}
  }
  fix();[250,600,1400].forEach(function(d){setTimeout(fix,d);});
  try{
    window.parent.document.addEventListener('click',function(){setTimeout(fix,150);});
    window.parent.addEventListener('resize',fix);
  }catch(e){}
})();
</script>
"""


# ── Data loading ───────────────────────────────────────────────────────────────

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
    df["iso3"]  = df["countryiso3code"]
    df["year"]  = df["date"].astype(int)
    df["value"] = df["value"].astype(float)
    return (df.sort_values("year", ascending=False)
              .groupby("iso3").first().reset_index()[["iso3", "value"]])


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
        if d.empty:
            continue
        d2 = d[d["iso3"].isin(valid)]
        df = df.merge(d2, on="iso3", how="left")

    defaults = {
        "fossil_pct": 70.0, "elec_access": 85.0, "water_withdrawal": 15.0,
        "undernourishment": 8.0, "pm25": 22.0, "gdp_pc": 5000.0,
        "population": 10_000_000.0, "co2_pc": 4.0,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    df["heat_score"] = df["iso3"].map(HEAT_SCORE).fillna(DEFAULT_HEAT)

    # Relative (percentile-rank) scoring: 0 = least vulnerable in cohort, 100 = most vulnerable.
    # Absolute thresholds made most countries look resilient because real-world values
    # cluster far below the theoretical maximums (e.g. water withdrawal rarely hits 150%).
    def _pct(s: pd.Series) -> pd.Series:
        return s.rank(pct=True).mul(100).fillna(50).clip(0, 100)

    fp   = df["fossil_pct"].fillna(df["fossil_pct"].median())
    ea   = df["elec_access"].fillna(df["elec_access"].median())
    ww   = df["water_withdrawal"].fillna(df["water_withdrawal"].median())
    fn   = df["undernourishment"].fillna(df["undernourishment"].median())
    p25  = df["pm25"].fillna(df["pm25"].median())
    gdp  = df["gdp_pc"].fillna(df["gdp_pc"].median())
    co2v = df["co2_pc"].fillna(df["co2_pc"].median())

    df["d_energy"] = _pct(fp * 0.55 + (100 - ea) * 0.45)
    df["d_water"]  = _pct(ww)
    df["d_food"]   = _pct(fn)
    df["d_air"]    = _pct(p25)
    df["d_heat"]   = _pct(df["heat_score"])
    # Economy: higher GDP → lower vulnerability; negate log so poor countries rank highest
    df["d_eco"]    = _pct(gdp.clip(lower=1).apply(lambda x: -math.log10(x)))
    df["d_co2"]    = _pct(co2v)

    dim_cols = [v[0] for v in DIMS.values()]
    weights  = [v[2] for v in DIMS.values()]
    df["vulnerability"] = sum(df[col] * w for col, w in zip(dim_cols, weights))
    df["resilience"]    = (100 - df["vulnerability"]).round(1).clip(0, 100)
    return df.dropna(subset=["resilience"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _band(score: float) -> tuple[str, str]:
    for lo, hi, label, color in RESILIENCE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#888"


def _chart(h: int = 480, **kw) -> dict:
    base = dict(height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#999", size=11),
                margin=dict(l=0, r=0, t=6, b=0))
    base.update(kw)
    return base


def _story_card(dim: str) -> str:
    d, color, icon = CARD_DATA[dim], DIMS[dim][1], ICONS[dim]
    return (
        f'<div class="sc" style="border-left-color:{color}">'
        f'<div class="sc-top">'
        f'<div class="sc-icon" style="background:{color}14">{icon}</div>'
        f'<div><div class="sc-stat" style="color:{color}">{d["stat"]}</div>'
        f'<div class="sc-lbl">{d["lbl"]}</div></div>'
        f'</div>'
        f'<div class="sc-body">{d["body"]}</div>'
        f'<div class="sc-src">{d["src"]}</div>'
        f'</div>'
    )


def _dim_bar(name: str, vuln: float) -> str:
    color, w = DIMS[name][1], DIMS[name][2]
    return (
        f'<div class="db">'
        f'<div class="db-h"><span>{name} <span style="font-size:.6rem;color:#bbb;font-weight:400">wt {int(w*100)}%</span></span>'
        f'<span style="color:{color};font-weight:700">{vuln:.0f}</span></div>'
        f'<div class="db-t"><div class="db-f" style="width:{min(vuln,100):.0f}%;background:{color}"></div></div>'
        f'</div>'
    )


# ── Tab 1 — Resilience Map ─────────────────────────────────────────────────────

def tab_map(df: pd.DataFrame) -> None:
    n_crit  = int((df["resilience"] < 20).sum())
    n_risk  = int((df["resilience"] < 40).sum())
    n_good  = int((df["resilience"] >= 60).sum())
    most_r  = df.loc[df["resilience"].idxmax(), "name"]
    least_r = df.loc[df["resilience"].idxmin(), "name"]
    glb     = df["resilience"].mean()
    most_s  = df["resilience"].max()
    least_s = df["resilience"].min()

    # Band legend rows
    bands_html = ""
    for lo, hi, label, color in RESILIENCE_BANDS:
        n   = int(((df["resilience"] >= lo) & (df["resilience"] < hi)).sum())
        pct = n / len(df) * 100
        bands_html += (
            f'<div class="bl-row">'
            f'<div class="bl-dot" style="background:{color}"></div>'
            f'<div class="bl-lbl">{label} ({lo}–{hi})</div>'
            f'<div class="bl-cnt">{n} <span style="font-size:.58rem;font-weight:400;color:#ccc">({pct:.0f}%)</span></div>'
            f'</div>'
        )

    # Single complete HTML for entire left panel
    left_html = f"""
<div style="padding:20px 18px 44px">
  <h2 class="lp-title">Resilience Map</h2>
  <p class="lp-desc">Composite Country Resilience Score across 7 climate dimensions. 100&nbsp;=&nbsp;fully resilient · 0&nbsp;=&nbsp;critical.</p>

  <hr class="lp-sep">

  <div class="poly-card">
    <div class="poly-by">Adam Tooze · Foreign Policy · Oct 2022</div>
    <div class="poly-q">"Not a crisis, but a polycrisis — distinct crises that interact so the whole is <span style="color:#f97316">more harmful than the sum of its parts.</span>"</div>
    <div class="poly-sub">The {n_risk} countries in the red zone face energy stress, water scarcity, food insecurity, air pollution, and extreme heat — simultaneously, with the least capacity to adapt.</div>
  </div>

  <div class="lp-sec">The 7-dimension network</div>
  {_POLY_SVG}
  <p style="font-size:.6rem;color:#ccc;text-align:center;margin:6px 0 0;line-height:1.5">
    Lines show compounding relationships.<br>Countries in the red zone sit at the intersection of all seven.
  </p>

  <hr class="lp-sep">
  <div class="lp-sec">Score distribution</div>
  {bands_html}

  <hr class="lp-sep">
  <div class="lp-sec">Global extremes</div>
  <div style="display:flex;gap:8px">
    <div style="flex:1;background:#f0fdf4;border-radius:8px;padding:9px 11px;border:1px solid #bbf7d0;border-left:3px solid #16a34a">
      <div style="font-size:.58rem;color:#16a34a;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px">Most Resilient</div>
      <div style="font-size:.82rem;font-weight:700;color:#111;font-family:'Space Grotesk',sans-serif">{most_r}</div>
      <div style="font-size:.65rem;color:#16a34a;font-weight:700;margin-top:2px">{most_s:.0f} / 100</div>
    </div>
    <div style="flex:1;background:#fef2f2;border-radius:8px;padding:9px 11px;border:1px solid #fecaca;border-left:3px solid #ef4444">
      <div style="font-size:.58rem;color:#ef4444;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px">Most Vulnerable</div>
      <div style="font-size:.82rem;font-weight:700;color:#111;font-family:'Space Grotesk',sans-serif">{least_r}</div>
      <div style="font-size:.65rem;color:#ef4444;font-weight:700;margin-top:2px">{least_s:.0f} / 100</div>
    </div>
  </div>

  <hr class="lp-sep">
  <div class="lp-sec">The 7 dimensions — global context</div>
  {''.join(_story_card(d) for d in DIMS)}

  <hr class="lp-sep">
  <div class="lp-note">
    <b style="color:#aaa">Weights:</b> Energy 15% · Water 18% · Food 15% · Air 15% · Heat 15% · Economy 12% · Carbon 10%.<br>
    <b style="color:#aaa">Data:</b> World Bank Open Data (most recent year, 2018–2023) · IPCC AR6 WG2 heat hazard scores.
  </div>
</div>"""

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-anchor"></span>', unsafe_allow_html=True)
        st.markdown(left_html, unsafe_allow_html=True)

    with right:
        # Stat pills — complete self-contained HTML
        st.markdown(
            f'<div style="padding:18px 22px 0">'
            f'<div class="rp-lbl">Country Resilience Score — Composite 7-Dimension Index</div>'
            f'<div class="sp-row">'
            f'<div class="sp"><div class="sp-val" style="color:#7f1d1d">{n_crit}</div><div class="sp-lbl">Critical zone<br>(score &lt; 20)</div></div>'
            f'<div class="sp"><div class="sp-val" style="color:#ef4444">{n_risk}</div><div class="sp-lbl">At Risk or worse<br>(score &lt; 40)</div></div>'
            f'<div class="sp"><div class="sp-val" style="color:#16a34a">{n_good}</div><div class="sp-lbl">Stable or better<br>(score &gt; 60)</div></div>'
            f'<div class="sp"><div class="sp-val">{glb:.0f}</div><div class="sp-lbl">Global mean<br>resilience score</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Choropleth
        df["band"] = df["resilience"].apply(lambda s: _band(s)[0])
        fig = px.choropleth(
            df, locations="iso3", color="resilience",
            color_continuous_scale=["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"],
            range_color=[0, 100], hover_name="name",
            hover_data={"iso3": False, "resilience": ":.0f", "band": True,
                        "d_energy": ":.0f", "d_water": ":.0f", "d_food": ":.0f"},
            labels={"resilience": "Resilience", "band": "Status"},
        )
        fig.update_layout(
            **_chart(h=440),
            geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#d4d4d4",
                     bgcolor="rgba(0,0,0,0)", showcountries=True, countrycolor="#e5e5e5",
                     showocean=True, oceancolor="#dde8f5", showlakes=True, lakecolor="#dde8f5"),
            coloraxis_colorbar=dict(
                title=dict(text="Score", font=dict(size=10, color="#aaa")),
                thickness=8, len=0.55, x=1.01,
                tickvals=[0, 20, 40, 60, 80, 100],
                ticktext=["0  Critical","20","40","60","80","100  Resilient"],
                tickfont=dict(size=9, color="#aaa"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Context cards — complete self-contained HTML
        st.markdown(
            '<div style="padding:0 22px 28px;display:grid;grid-template-columns:1fr 1fr;gap:10px">'
            '<div style="background:white;border-radius:8px;padding:13px 15px;border:1px solid rgba(0,0,0,0.06)">'
            '<div style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#f97316;margin-bottom:7px">The polycrisis dynamic</div>'
            '<div style="font-size:.72rem;color:#555;line-height:1.68">Water stress amplifies food insecurity. Heat erodes economic output. Air pollution overwhelms health systems at the worst moment. Countries scoring lowest face <b style="color:#111">all seven pressures simultaneously</b> — with the least capacity to adapt.</div>'
            '</div>'
            '<div style="background:white;border-radius:8px;padding:13px 15px;border:1px solid rgba(0,0,0,0.06)">'
            '<div style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#3b82f6;margin-bottom:7px">The resilience gap</div>'
            '<div style="font-size:.72rem;color:#555;line-height:1.68">The most resilient countries are temperate, wealthy, and diversified. The least resilient are disproportionately in the Global South — contributing the fewest emissions while absorbing the highest climate risk.</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ── Tab 2 — Country Profile ────────────────────────────────────────────────────

def tab_country(df: pd.DataFrame) -> None:
    countries = sorted(df["name"].dropna().unique())
    default   = countries.index("Pakistan") if "Pakistan" in countries else 0

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-anchor"></span>', unsafe_allow_html=True)

        # Section 1: title (no widget dependency)
        st.markdown(
            '<div style="padding:20px 18px 10px">'
            '<h2 class="lp-title">Country Profile</h2>'
            '<p class="lp-desc">Drill into any country across all 7 resilience dimensions.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Widget (must be a standalone Streamlit call)
        with st.container():
            st.markdown('<div style="padding:0 18px 4px"></div>', unsafe_allow_html=True)
            sel = st.selectbox("Country", countries, index=default, key="cp_country",
                               label_visibility="collapsed")

        # Section 2: all dynamic content in ONE call
        row   = df[df["name"] == sel].iloc[0]
        score = row["resilience"]
        band_label, bcolor = _band(score)

        dims_html = "".join(_dim_bar(n, float(row[DIMS[n][0]])) for n in DIMS)

        vuln_sorted = sorted(DIMS.keys(), key=lambda d: float(row[DIMS[d][0]]), reverse=True)
        top1, top2  = vuln_sorted[0], vuln_sorted[1]
        best1       = vuln_sorted[-1]
        region_df   = df[df["region"] == row["region"]]
        reg_avg     = region_df["resilience"].mean()
        reg_rank    = int((region_df["resilience"] > score).sum()) + 1
        reg_total   = len(region_df)
        glb_avg     = df["resilience"].mean()
        direction   = "above" if score > glb_avg else "below"
        gap         = abs(score - glb_avg)
        c1, c2      = DIMS[top1][1], DIMS[top2][1]

        st.markdown(
            f'<div style="padding:4px 18px 44px">'
            f'<div class="sb" style="background:{bcolor}12;border:1px solid {bcolor}25;margin-bottom:12px">'
            f'<div class="sb-lbl" style="color:{bcolor}">Resilience Score</div>'
            f'<div class="sb-val" style="color:{bcolor}">{score:.0f}</div>'
            f'<div class="sb-sub">{band_label} · {sel}</div>'
            f'</div>'
            f'<div class="lp-sec">Vulnerability by dimension (0&nbsp;=&nbsp;safe · 100&nbsp;=&nbsp;critical)</div>'
            f'{dims_html}'
            f'<hr class="lp-sep">'
            f'<div class="nc">'
            f'<div class="nc-l">Country narrative</div>'
            f'<div class="nc-b">{sel}\'s most acute vulnerabilities are '
            f'<b style="color:{c1}">{top1.lower()}</b> and <b style="color:{c2}">{top2.lower()}</b>. '
            f'Strongest dimension: {best1.lower()}. '
            f'At {score:.0f}/100, ranked #{reg_rank} of {reg_total} in its region — '
            f'{gap:.0f} pts {direction} the global average of {glb_avg:.0f}.</div>'
            f'</div>'
            f'<hr class="lp-sep">'
            f'<div style="display:flex;gap:8px">'
            f'<div style="flex:1;background:#f8f9fa;border-radius:7px;padding:9px 11px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.58rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px">Region avg</div>'
            f'<div style="font-size:1.2rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">{reg_avg:.0f}</div>'
            f'<div style="font-size:.6rem;color:#bbb;margin-top:1px">{row["region"].split("&")[0].strip()[:16]}</div>'
            f'</div>'
            f'<div style="flex:1;background:#f8f9fa;border-radius:7px;padding:9px 11px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.58rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px">Global avg</div>'
            f'<div style="font-size:1.2rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">{glb_avg:.0f}</div>'
            f'<div style="font-size:.6rem;color:#bbb;margin-top:1px">All {len(df)} countries</div>'
            f'</div>'
            f'<div style="flex:1;background:#f8f9fa;border-radius:7px;padding:9px 11px;border:1px solid rgba(0,0,0,0.06)">'
            f'<div style="font-size:.58rem;color:#bbb;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px">Region rank</div>'
            f'<div style="font-size:1.2rem;font-weight:800;color:#111;font-family:Space Grotesk,sans-serif">#{reg_rank}</div>'
            f'<div style="font-size:.6rem;color:#bbb;margin-top:1px">of {reg_total}</div>'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with right:
        dim_names = list(DIMS.keys())
        vuln_vals = [float(row[DIMS[d][0]]) for d in dim_names]
        cats = dim_names + [dim_names[0]]
        vals = vuln_vals + [vuln_vals[0]]

        st.markdown(
            f'<div style="padding:18px 22px 0"><div class="rp-lbl">Vulnerability Radar — {sel}</div></div>',
            unsafe_allow_html=True,
        )
        rfig = go.Figure()
        rfig.add_trace(go.Scatterpolar(
            r=vals, theta=cats, fill="toself",
            fillcolor="rgba(239,68,68,0.10)", line=dict(color="#ef4444", width=2),
            name=sel, hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[50]*len(cats), theta=cats,
            line=dict(color="#94a3b8", width=1, dash="dot"),
            mode="lines", name="World avg (~50)", hoverinfo="skip",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[75]*len(cats), theta=cats,
            line=dict(color="#dc2626", width=1, dash="dot"),
            mode="lines", name="High-risk (75)", hoverinfo="skip",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(range=[0,100], tickvals=[25,50,75],
                               tickfont=dict(size=9, color="#ccc"),
                               gridcolor="rgba(0,0,0,0.06)"),
                angularaxis=dict(tickfont=dict(size=11.5, color="#444")),
                bgcolor="rgba(0,0,0,0)",
            ),
            **_chart(h=360, margin=dict(l=30, r=30, t=16, b=36)),
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center",
                       font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(rfig, use_container_width=True)

        st.markdown(
            f'<div style="padding:0 22px 4px"><hr class="rp-sep">'
            f'<div class="rp-lbl">Regional comparison — {row["region"]}</div></div>',
            unsafe_allow_html=True,
        )
        reg_df = (df[df["region"] == row["region"]]
                  .sort_values("resilience").head(25).copy())
        reg_df["hl"] = reg_df["name"] == sel
        cfig = px.bar(
            reg_df, x="resilience", y="name", orientation="h",
            color="hl", color_discrete_map={True: "#ef4444", False: "#d1d5db"},
            labels={"resilience": "Resilience Score", "name": ""}, text="resilience",
        )
        cfig.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        cfig.update_layout(
            **_chart(h=max(260, len(reg_df)*26), margin=dict(l=0, r=56, t=0, b=0)),
            xaxis=dict(range=[0, 106], gridcolor="rgba(0,0,0,0.05)", color="#ccc",
                       tickfont=dict(size=10)),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10.5)),
            showlegend=False,
        )
        st.plotly_chart(cfig, use_container_width=True)


# ── Tab 3 — Crisis Correlations ───────────────────────────────────────────────

_CORR_WHY = {
    ("Energy","Economy"): "Energy poverty and underdevelopment are deeply co-determined — each entrenches the other.",
    ("Energy","Air"):     "Burning fossil fuels for power is the primary source of PM2.5 in most developing nations.",
    ("Water","Food"):     "Agriculture uses 70% of freshwater — when aquifers fail, harvests fail.",
    ("Food","Economy"):   "Food insecurity is both a symptom of poverty and a drag on it.",
    ("Air","Economy"):    "Air pollution costs 5–6% of GDP in high-exposure economies via productivity losses.",
    ("Heat","Economy"):   "Heat reduces outdoor and agricultural labour, compressing GDP in the most exposed regions.",
    ("Heat","Water"):     "Higher temperatures accelerate evaporation — amplifying water stress directly.",
    ("Water","Economy"):  "Water scarcity raises food, energy, and industrial costs simultaneously.",
    ("Food","Air"):       "Crop-burning is a major PM2.5 source in South and Southeast Asia.",
    ("Energy","Water"):   "Thermoelectric plants require vast cooling water — scarcity directly threatens grids.",
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

    # Build insight cards HTML
    insights_html = ""
    shown = 0
    for abs_r, r, a, b in pairs[:8]:
        if shown >= 6:
            break
        arrow = "↑↑" if r > 0 else "↑↓"
        ca, cb = DIMS[a][1], DIMS[b][1]
        key  = (a, b) if (a, b) in _CORR_WHY else (b, a)
        why  = _CORR_WHY.get(key, "These dimensions frequently affect the same countries.")
        bar_w = int(abs_r * 100)
        insights_html += (
            f'<div class="ic">'
            f'<div style="display:flex;align-items:center;justify-content:space-between">'
            f'<div style="font-size:.74rem;font-weight:700;color:#111">'
            f'<span style="color:{ca}">{a}</span>'
            f'<span style="color:#ddd;margin:0 5px;font-weight:400">+</span>'
            f'<span style="color:{cb}">{b}</span></div>'
            f'<div style="font-size:.68rem;font-weight:700;color:#f97316">{r:.2f} {arrow}</div>'
            f'</div>'
            f'<div class="ic-body">{why}</div>'
            f'<div style="background:rgba(0,0,0,0.07);border-radius:2px;height:3px;margin-top:7px;overflow:hidden">'
            f'<div style="width:{bar_w}%;background:#f97316;height:3px;border-radius:2px"></div>'
            f'</div></div>'
        )
        shown += 1

    left_html = f"""
<div style="padding:20px 18px 44px">
  <h2 class="lp-title">Crisis Correlations</h2>
  <p class="lp-desc">When crises cluster, they compound. Countries at the intersection of multiple dimensions face cascading failures.</p>

  <hr class="lp-sep">

  <div style="background:#fff7f0;border-radius:9px;padding:14px 15px;border:1px solid rgba(249,115,22,0.15);border-left:3px solid #f97316;margin-bottom:12px">
    <div style="font-size:.62rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#f97316;margin-bottom:7px">The compounding dynamic</div>
    <div style="font-size:.78rem;font-weight:700;color:#111;font-family:'Space Grotesk',sans-serif;line-height:1.4;margin-bottom:7px">Not A + B + C, but A × B × C.</div>
    <div style="font-size:.7rem;color:#555;line-height:1.68">Water stress raises food prices. Insecurity undercuts stability. Weak economies limit energy investment. Fossil energy worsens air. Bad air degrades health. Each crisis feeds the others — the loop tightens.</div>
  </div>

  <div class="lp-sec">Strongest co-occurrence pairs</div>
  {insights_html}

  <hr class="lp-sep">
  <div style="background:#f8fafc;border-radius:8px;padding:11px 13px;border:1px solid rgba(0,0,0,0.06)">
    <div style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;margin-bottom:6px">How to read the heatmap →</div>
    <div style="font-size:.69rem;color:#64748b;line-height:1.65">
      <b style="color:#ef4444">Deep red (+1.0):</b> crises always strike together.<br>
      <b style="color:#64748b">Near zero:</b> crises are independent.<br>
      <b style="color:#3b82f6">Deep blue (−1.0):</b> one crisis means less of the other.<br><br>
      High positive correlation = policy leverage: fixing one dimension often helps others.
    </div>
  </div>
</div>"""

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-anchor"></span>', unsafe_allow_html=True)
        st.markdown(left_html, unsafe_allow_html=True)

    with right:
        st.markdown(
            '<div style="padding:18px 22px 0"><div class="rp-lbl">Crisis Correlation Matrix — Pearson r between all 7 dimensions</div></div>',
            unsafe_allow_html=True,
        )
        hfig = px.imshow(
            corr,
            color_continuous_scale=["#dbeafe","#f8fafc","#fef2f2"],
            zmin=-1, zmax=1, text_auto=".2f",
            labels=dict(color="Pearson r"),
        )
        hfig.update_traces(textfont=dict(size=12, color="#333"))
        hfig.update_layout(
            **_chart(h=400, margin=dict(l=80, r=20, t=4, b=80)),
            xaxis=dict(tickfont=dict(size=12, color="#555"), side="bottom"),
            yaxis=dict(tickfont=dict(size=12, color="#555")),
            coloraxis_colorbar=dict(
                title=dict(text="r", font=dict(size=10, color="#aaa")),
                thickness=8, tickfont=dict(size=9, color="#aaa"),
                tickvals=[-1,-0.5,0,0.5,1],
            ),
        )
        st.plotly_chart(hfig, use_container_width=True)

        if pairs:
            top_a, top_b = pairs[0][2], pairs[0][3]
            top_r = pairs[0][1]
            col_a, col_b = DIMS[top_a][0], DIMS[top_b][0]
            st.markdown(
                f'<div style="padding:0 22px 4px"><hr class="rp-sep">'
                f'<div class="rp-lbl">Strongest pair: {top_a} vs {top_b} (r = {top_r:.2f})</div></div>',
                unsafe_allow_html=True,
            )
            pop_col = "population" if "population" in df.columns else None
            sfig = px.scatter(
                df.dropna(subset=[col_a, col_b]),
                x=col_a, y=col_b, size=pop_col, color="region",
                hover_name="name",
                labels={col_a: f"{top_a} vulnerability (0–100)",
                        col_b: f"{top_b} vulnerability (0–100)"},
                size_max=34,
                color_discrete_sequence=["#94a3b8","#64748b","#475569","#334155","#1e293b","#0f172a","#ef4444"],
            )
            sfig.update_layout(
                **_chart(h=290),
                xaxis=dict(gridcolor="rgba(0,0,0,0.05)", color="#ccc", tickfont=dict(size=10),
                           title=dict(font=dict(size=10, color="#bbb"))),
                yaxis=dict(gridcolor="rgba(0,0,0,0.05)", color="#ccc", tickfont=dict(size=10),
                           title=dict(font=dict(size=10, color="#bbb"))),
                legend=dict(font=dict(size=9, color="#aaa"), bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(sfig, use_container_width=True)


# ── Tab 4 — Rankings ──────────────────────────────────────────────────────────

def tab_rankings(df: pd.DataFrame) -> None:
    regions  = ["All regions"] + sorted(df["region"].dropna().unique())
    bottom10 = df.nsmallest(10, "resilience")
    top10    = df.nlargest(10, "resilience")
    n_crit   = int((df["resilience"] < 20).sum())
    n_risk   = int((df["resilience"] < 40).sum())
    n_good   = int((df["resilience"] > 60).sum())

    # Build top-3 extremes HTML
    extremes_html = ""
    for i in range(3):
        r_row = top10.iloc[i]
        v_row = bottom10.iloc[i]
        rb, rc = _band(r_row["resilience"])
        vb, vc = _band(v_row["resilience"])
        extremes_html += (
            f'<div style="display:flex;gap:7px;margin-bottom:7px">'
            f'<div style="flex:1;background:{rc}10;border-radius:7px;padding:8px 10px;border-left:3px solid {rc}">'
            f'<div style="font-size:.58rem;color:{rc};font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">#{i+1} resilient</div>'
            f'<div style="font-size:.8rem;font-weight:700;color:#111">{r_row["name"].split(",")[0]}</div>'
            f'<div style="font-size:.65rem;color:{rc};font-weight:700">{r_row["resilience"]:.0f}</div>'
            f'</div>'
            f'<div style="flex:1;background:{vc}10;border-radius:7px;padding:8px 10px;border-left:3px solid {vc}">'
            f'<div style="font-size:.58rem;color:{vc};font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">#{i+1} vulnerable</div>'
            f'<div style="font-size:.8rem;font-weight:700;color:#111">{v_row["name"].split(",")[0]}</div>'
            f'<div style="font-size:.65rem;color:{vc};font-weight:700">{v_row["resilience"]:.0f}</div>'
            f'</div></div>'
        )

    left, right = st.columns([1.05, 2.95], gap="large")

    with left:
        st.markdown('<span class="mc-anchor"></span>', unsafe_allow_html=True)

        # Top section (no widget dependency) — single call
        st.markdown(
            f'<div style="padding:20px 18px 10px">'
            f'<h2 class="lp-title">Rankings</h2>'
            f'<p class="lp-desc">Countries ranked by composite resilience. Filter by region to compare within peer groups.</p>'
            f'<hr class="lp-sep">'
            f'<div class="lp-sec">Top extremes</div>'
            f'{extremes_html}'
            f'<hr class="lp-sep">'
            f'<div class="lp-sec">Filter &amp; view</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Widgets
        region_sel = st.selectbox("Region", regions, key="rk_region", label_visibility="collapsed")
        view       = st.radio("Show", ["Most vulnerable", "Most resilient", "All countries"],
                              key="rk_view", label_visibility="collapsed")

        # Bottom section (no widget dependency) — single call
        st.markdown(
            f'<div style="padding:4px 18px 44px">'
            f'<hr class="lp-sep">'
            f'<div style="background:#fef2f2;border-radius:8px;padding:11px 13px;border:1px solid #fecaca;margin-bottom:10px">'
            f'<div style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#ef4444;margin-bottom:5px">Risk distribution</div>'
            f'<div style="font-size:.71rem;color:#555;line-height:1.65">'
            f'<b style="color:#7f1d1d">{n_crit} countries</b> Critical (score &lt; 20). '
            f'<b style="color:#ef4444">{n_risk}</b> At Risk or worse. '
            f'Only <b style="color:#16a34a">{n_good}</b> score above 60 (Stable or better).'
            f'</div></div>'
            f'<div class="lp-note">Score = 100 − weighted vulnerability. Hover any bar for per-dimension scores.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with right:
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

        st.markdown(
            f'<div style="padding:18px 22px 0"><div class="rp-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )
        dim_hover = {v[0]: ":.0f" for v in DIMS.values()}
        bfig = px.bar(
            plot_df, x="resilience", y="name", orientation="h",
            color="resilience",
            color_continuous_scale=["#7f1d1d","#ef4444","#f59e0b","#4ade80","#16a34a"],
            range_color=[0, 100],
            labels={"resilience": "Resilience Score", "name": ""},
            hover_data=dim_hover, text="resilience",
        )
        bfig.update_traces(texttemplate="%{x:.0f}", textposition="outside",
                           textfont=dict(size=9, color="#aaa"))
        bfig.update_layout(
            **_chart(h=max(520, len(plot_df)*22), margin=dict(l=0, r=56, t=0, b=0)),
            xaxis=dict(range=[0, 108], gridcolor="rgba(0,0,0,0.05)", color="#ccc",
                       tickfont=dict(size=10),
                       title=dict(text="Resilience Score (100 = fully resilient)",
                                  font=dict(size=10, color="#bbb"))),
            yaxis=dict(showgrid=False, color="#333", tickfont=dict(size=10.5)),
            coloraxis_showscale=False,
        )
        st.plotly_chart(bfig, use_container_width=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="mc-header">'
        '<div class="mc-topline"><span class="mc-dot"></span>'
        'POLYCRISIS DASHBOARD · DAY 10 · THE RESILIENCE STACK'
        '</div>'
        '<div class="mc-header-right">7 dimensions · 190+ countries · World Bank + IPCC</div>'
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

    # JS scroll fix — runs after DOM is built, accesses parent from iframe
    components.html(_JS, height=0, scrolling=False)


if __name__ == "__main__":
    main()
