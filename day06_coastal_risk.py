import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Coastal Risk & Sea Level · Day 06",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

HEADERS  = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
WB_BASE  = "https://api.worldbank.org/v2/country/all/indicator"
NOAA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# ── SLR scenarios ──────────────────────────────────────────────────────────────
SLR_SCENARIOS = {
    "Today — current coastline":     0.0,
    "+0.3m — likely by 2050":        0.3,
    "+0.6m — SSP2-4.5 by 2100":      0.6,
    "+1.0m — SSP3-7.0 by 2100":      1.0,
    "+1.5m — SSP5-8.5 high end":     1.5,
    "+2.0m — ice sheet instability":  2.0,
}
SLR_TO_FT = {0.0: None, 0.3: 1, 0.6: 2, 1.0: 3, 1.5: 5, 2.0: 7}

# ── Country coastal exposure data ─────────────────────────────────────────────
# (pop_1m_k, pop_2m_k, pop_3m_k, slr_mm_yr, coastline_km)
# Population in thousands. Sources: Kulp & Strauss 2019 (Nat.Comms.),
# Climate Central, IPCC AR6 Ch.9, PSMSL tide gauge records.
COASTAL_DATA = {
    "BGD": (17000, 28000, 40000, 5.0,   580),
    "CHN": (43000, 78000,110000, 3.8, 14500),
    "IND": ( 7000, 21000, 36000, 3.3,  7517),
    "VNM": ( 9000, 20000, 31000, 4.5,  3260),
    "IDN": ( 6000, 14000, 23000, 5.0, 54720),
    "MDV": (  440,   500,   530, 4.2,   644),
    "USA": ( 4700,  9000, 13000, 3.1, 19924),
    "NLD": ( 3000,  5000,  7000, 2.0,   451),
    "EGY": (10000, 15000, 20000, 3.0,  2450),
    "THA": ( 4500,  8000, 12000, 3.5,  3219),
    "PHL": ( 6000, 11000, 17000, 4.5, 36289),
    "MMR": ( 3000,  5000,  8000, 4.0,  1930),
    "PAK": ( 2000,  3500,  6000, 3.0,  1046),
    "BRA": ( 4000,  7000, 10000, 3.2,  7491),
    "JPN": ( 3700,  8000, 15000, 2.8, 29751),
    "GBR": ( 1000,  2500,  4000, 2.3, 17820),
    "DEU": (  900,  2000,  3500, 2.1,  2389),
    "NGA": ( 2500,  5000,  8000, 3.5,   853),
    "MYS": ( 1500,  3000,  5000, 4.0,  4675),
    "KHM": ( 1500,  2800,  4500, 4.0,   443),
    "TUV": (   11,    11,    11, 5.8,    24),
    "KIR": (  115,   118,   119, 3.9,  1143),
    "MHL": (   42,    56,    58, 3.7,   370),
    "FJI": (  180,   320,   500, 4.5,  1129),
    "PNG": (  500,  1000,  2000, 4.8,  5152),
    "AUS": ( 1200,  2500,  4000, 2.9, 25760),
    "MEX": ( 1500,  3000,  5500, 3.0,  9330),
    "MOZ": ( 1200,  2500,  4000, 3.8,  2470),
    "TZA": (  600,  1200,  2000, 3.5,  1424),
    "ZAF": (  400,   800,  1500, 2.5,  2798),
    "AGO": (  600,  1200,  2000, 3.0,  1600),
    "GHA": (  400,   800,  1400, 2.8,   539),
    "SEN": (  800,  1500,  2500, 2.8,   531),
    "IRN": (  600,  1200,  2200, 2.8,  2440),
    "SAU": (  400,   900,  1600, 2.5,  2640),
    "ARE": (  500,  1000,  1800, 3.2,  1318),
    "KWT": (  200,   450,   800, 3.0,   499),
    "QAT": (  300,   600,  1000, 3.2,   563),
    "BHR": (  350,   600,   900, 3.5,   161),
    "LKA": (  500,  1000,  2000, 3.5,  1340),
    "IRQ": (  800,  1500,  2500, 2.5,    58),
    "CAN": (  500,  1200,  2500, 1.8, 202080),
    "RUS": (  600,  1500,  3000, 1.5,  37653),
    "FRA": (  500,  1200,  2000, 2.5,   5853),
    "ITA": (  800,  2000,  3500, 2.3,   7600),
    "ESP": (  400,   900,  1600, 2.0,   4964),
    "DNK": (  400,   900,  1500, 1.9,   7314),
    "NOR": (  100,   300,   600, 0.8,  25148),
    "POL": (  200,   500,   900, 2.8,    440),
    "TUR": (  600,  1400,  2500, 2.2,   7200),
    "GRC": (  300,   700,  1200, 2.0,  13676),
    "PRT": (  200,   500,   900, 1.8,   1794),
    "MRT": (  200,   400,   700, 2.5,    754),
    "SOM": (  500,  1000,  1800, 3.0,   3025),
    "SGP": (  100,   250,   450, 4.5,   193),
    "HKG": (  100,   300,   600, 3.6,   733),
    "GTM": (  300,   600,  1000, 3.2,   400),
    "HND": (  400,   800,  1500, 3.5,   820),
    "NIC": (  300,   600,  1000, 3.2,   910),
}

# ── Tide gauge stations (NOAA CO-OPS) ─────────────────────────────────────────
TIDE_STATIONS = {
    "San Francisco, USA": {"id": "9414290", "slr": 1.94, "lat": 37.81, "lon": -122.47},
    "New York, USA":      {"id": "8518750", "slr": 3.35, "lat": 40.70, "lon": -74.01},
    "Key West, USA":      {"id": "8724580", "slr": 2.56, "lat": 24.56, "lon": -81.81},
    "Seattle, USA":       {"id": "9447130", "slr": 1.09, "lat": 47.60, "lon": -122.34},
    "Honolulu, Hawaii":   {"id": "1612340", "slr": 1.64, "lat": 21.31, "lon": -157.87},
    "Galveston, USA":     {"id": "8771450", "slr": 6.62, "lat": 29.31, "lon": -94.79},
    "Charleston SC, USA": {"id": "8665530", "slr": 3.55, "lat": 32.78, "lon": -79.93},
    "Boston, USA":        {"id": "8443970", "slr": 2.87, "lat": 42.36, "lon": -71.05},
    "Los Angeles, USA":   {"id": "9410660", "slr": 1.02, "lat": 33.72, "lon": -118.27},
    "Baltimore, USA":     {"id": "8574680", "slr": 3.78, "lat": 39.27, "lon": -76.58},
    "Miami Beach, USA":   {"id": "8723214", "slr": 2.78, "lat": 25.77, "lon": -80.13},
    "San Diego, USA":     {"id": "9410170", "slr": 2.09, "lat": 32.71, "lon": -117.17},
    "Wake Island":        {"id": "1890000", "slr": 2.17, "lat": 19.28, "lon": 166.62},
    "Midway Island":      {"id": "1619910", "slr": 1.58, "lat": 28.21, "lon": -177.36},
    "Portland ME, USA":   {"id": "8418150", "slr": 1.87, "lat": 43.66, "lon": -70.25},
}

# ── Risk tier bands (% of population within 1m elevation) ─────────────────────
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

# ── Hotspot regions for the flood viewer ───────────────────────────────────────
HOTSPOT_REGIONS = {
    "Bangladesh — Ganges Delta": {
        "center": [22.5, 90.5], "zoom": 7, "is_noaa": False,
        "narrative": "World's most densely populated river delta. 170M people; 17M at risk at 1 m SLR.",
        "pop_k": {0.0: 0, 0.3: 5000, 0.6: 9000, 1.0: 17000, 1.5: 23000, 2.0: 28000},
    },
    "Maldives — Indian Ocean Atolls": {
        "center": [4.2, 73.5], "zoom": 9, "is_noaa": False,
        "narrative": "80 % of land is within 1 m of sea level. Average island elevation: 1.5 m.",
        "pop_k": {0.0: 0, 0.3: 80, 0.6: 220, 1.0: 440, 1.5: 500, 2.0: 530},
    },
    "Vietnam — Mekong Delta": {
        "center": [10.0, 105.5], "zoom": 8, "is_noaa": False,
        "narrative": "Rice bowl of SE Asia. 20 M residents farm land mostly below 2 m elevation.",
        "pop_k": {0.0: 0, 0.3: 2000, 0.6: 5000, 1.0: 9000, 1.5: 14000, 2.0: 20000},
    },
    "Egypt — Nile Delta": {
        "center": [31.0, 31.0], "zoom": 8, "is_noaa": False,
        "narrative": "8 % of Egypt's land, 23 % of its population. Northern delta largely below 1 m.",
        "pop_k": {0.0: 0, 0.3: 2500, 0.6: 5000, 1.0: 10000, 1.5: 14000, 2.0: 18000},
    },
    "Miami — South Florida, USA": {
        "center": [25.77, -80.25], "zoom": 10, "is_noaa": True,
        "narrative": "Miami Beach averages 15 cm above sea level. $1 T+ in real estate faces chronic flooding.",
        "pop_k": {0.0: 0, 0.3: 180, 0.6: 400, 1.0: 800, 1.5: 1200, 2.0: 1800},
    },
    "Tuvalu — Pacific Island Nation": {
        "center": [-8.52, 179.19], "zoom": 13, "is_noaa": False,
        "narrative": "Average elevation under 2 m. Already floods regularly. Could be uninhabitable by 2050.",
        "pop_k": {0.0: 0, 0.3: 4, 0.6: 7, 1.0: 11, 1.5: 11, 2.0: 11},
    },
}


# ── Flood zone polygons (research-based simplified approximations) ─────────────
# Each entry: (region_name, slr_m) → GeoJSON FeatureCollection dict
# Coordinates in [lon, lat] (GeoJSON convention).
# Sources: Kulp & Strauss 2019, Climate Central risk zones, IPCC AR6 regional Ch.9

def _poly(coords, label=""):
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {"label": label}}

def _fc(*feats):
    return {"type": "FeatureCollection", "features": list(feats)}

FLOOD_ZONES = {
    # ── Bangladesh ──────────────────────────────────────────────────────────────
    ("Bangladesh — Ganges Delta", 0.3): _fc(
        _poly([[89.0,22.3],[89.5,21.8],[90.5,21.6],[91.0,21.8],[91.5,21.6],
               [92.0,21.3],[92.4,21.5],[92.3,22.0],[91.8,22.2],[91.0,22.3],
               [90.5,22.1],[90.0,22.0],[89.5,22.3],[89.0,22.3]], "Coastal fringe"),
    ),
    ("Bangladesh — Ganges Delta", 0.6): _fc(
        _poly([[89.0,22.6],[89.5,22.2],[90.0,22.0],[90.5,21.8],[91.0,21.9],
               [91.5,21.7],[92.0,21.3],[92.5,21.5],[92.5,22.0],[92.0,22.5],
               [91.5,22.5],[91.0,22.6],[90.5,22.4],[90.0,22.3],[89.5,22.5],
               [89.0,22.6]], "0.6 m"),
    ),
    ("Bangladesh — Ganges Delta", 1.0): _fc(
        _poly([[89.0,23.0],[89.5,22.5],[90.0,22.3],[90.5,22.2],[91.0,22.2],
               [91.5,22.0],[92.0,21.5],[92.5,21.5],[92.5,22.3],[92.2,22.8],
               [91.8,23.0],[91.2,23.0],[90.5,22.8],[90.0,22.7],[89.5,22.8],
               [89.0,23.0]], "1.0 m"),
    ),
    ("Bangladesh — Ganges Delta", 1.5): _fc(
        _poly([[89.0,23.3],[89.5,23.0],[90.0,22.8],[90.5,22.7],[91.0,22.7],
               [91.5,22.5],[92.0,22.0],[92.5,21.7],[92.5,22.5],[92.0,23.0],
               [91.5,23.2],[91.0,23.3],[90.5,23.1],[90.0,23.0],[89.5,23.1],
               [89.0,23.3]], "1.5 m"),
    ),
    ("Bangladesh — Ganges Delta", 2.0): _fc(
        _poly([[89.0,23.8],[89.3,23.5],[90.0,23.3],[90.5,23.2],[91.0,23.3],
               [91.5,23.0],[92.0,22.5],[92.5,22.0],[92.5,22.8],[92.0,23.3],
               [91.5,23.5],[91.0,23.7],[90.5,23.5],[90.0,23.4],[89.5,23.5],
               [89.0,23.8]], "2.0 m"),
    ),

    # ── Maldives ────────────────────────────────────────────────────────────────
    ("Maldives — Indian Ocean Atolls", 0.3): _fc(
        _poly([[73.38,4.40],[73.55,4.40],[73.55,4.05],[73.38,4.05],[73.38,4.40]], "N. Malé"),
        _poly([[73.38,3.90],[73.55,3.90],[73.55,3.65],[73.38,3.65],[73.38,3.90]], "S. Malé"),
    ),
    ("Maldives — Indian Ocean Atolls", 0.6): _fc(
        _poly([[73.35,4.50],[73.60,4.50],[73.60,4.00],[73.35,4.00],[73.35,4.50]], "N. Malé"),
        _poly([[73.35,3.95],[73.60,3.95],[73.60,3.60],[73.35,3.60],[73.35,3.95]], "S. Malé"),
        _poly([[73.45,3.55],[73.55,3.55],[73.55,3.40],[73.45,3.40],[73.45,3.55]], "Vaavu"),
    ),
    ("Maldives — Indian Ocean Atolls", 1.0): _fc(
        _poly([[73.30,4.60],[73.65,4.60],[73.65,3.95],[73.30,3.95],[73.30,4.60]], "N. Malé"),
        _poly([[73.30,3.90],[73.65,3.90],[73.65,3.55],[73.30,3.55],[73.30,3.90]], "S. Malé"),
        _poly([[73.40,3.50],[73.60,3.50],[73.60,3.30],[73.40,3.30],[73.40,3.50]], "Vaavu"),
        _poly([[73.00,5.20],[73.20,5.20],[73.20,4.95],[73.00,4.95],[73.00,5.20]], "Lhaviyani"),
    ),
    ("Maldives — Indian Ocean Atolls", 1.5): _fc(
        _poly([[73.25,4.70],[73.70,4.70],[73.70,3.90],[73.25,3.90],[73.25,4.70]], "Central atolls"),
        _poly([[73.35,3.85],[73.65,3.85],[73.65,3.25],[73.35,3.25],[73.35,3.85]], "South"),
        _poly([[72.95,5.30],[73.25,5.30],[73.25,4.90],[72.95,4.90],[72.95,5.30]], "North"),
    ),
    ("Maldives — Indian Ocean Atolls", 2.0): _fc(
        _poly([[72.90,5.50],[73.70,5.50],[73.70,3.20],[72.90,3.20],[72.90,5.50]], "Near-total"),
    ),

    # ── Mekong Delta ─────────────────────────────────────────────────────────────
    ("Vietnam — Mekong Delta", 0.3): _fc(
        _poly([[104.6,9.2],[105.0,8.8],[105.5,8.6],[106.0,9.0],[105.8,9.5],
               [105.3,9.7],[104.8,9.5],[104.6,9.2]], "Ca Mau coast"),
    ),
    ("Vietnam — Mekong Delta", 0.6): _fc(
        _poly([[104.5,9.8],[105.0,9.3],[105.5,8.8],[106.0,9.0],[106.0,9.7],
               [105.7,10.2],[105.2,10.3],[104.7,10.0],[104.5,9.8]], "Southern delta"),
    ),
    ("Vietnam — Mekong Delta", 1.0): _fc(
        _poly([[104.5,10.5],[105.0,10.0],[105.3,9.5],[105.5,9.0],[106.0,9.0],
               [106.3,9.5],[106.3,10.3],[106.0,10.8],[105.5,11.0],[105.0,10.8],
               [104.5,10.5]], "Mekong Delta"),
    ),
    ("Vietnam — Mekong Delta", 1.5): _fc(
        _poly([[104.5,11.0],[105.0,10.5],[105.5,10.0],[106.0,9.5],[106.5,9.5],
               [106.8,10.0],[107.0,10.5],[106.8,11.0],[106.3,11.2],[105.7,11.3],
               [105.0,11.2],[104.5,11.0]], "Delta + HCMC fringe"),
    ),
    ("Vietnam — Mekong Delta", 2.0): _fc(
        _poly([[104.5,11.5],[105.0,11.0],[105.5,10.5],[106.0,10.0],[106.5,9.5],
               [107.0,9.5],[107.3,10.0],[107.2,10.8],[107.0,11.5],[106.5,11.8],
               [106.0,11.7],[105.5,11.7],[105.0,11.6],[104.5,11.5]], "HCMC region"),
    ),

    # ── Nile Delta ────────────────────────────────────────────────────────────────
    ("Egypt — Nile Delta", 0.3): _fc(
        _poly([[29.8,31.3],[30.5,31.5],[31.0,31.5],[31.5,31.4],[32.0,31.3],
               [32.2,31.1],[31.8,31.0],[31.3,31.0],[30.8,31.1],[30.3,31.1],
               [29.9,31.2],[29.8,31.3]], "Alexandria coast"),
    ),
    ("Egypt — Nile Delta", 0.6): _fc(
        _poly([[29.6,31.4],[30.3,31.6],[31.0,31.6],[31.7,31.5],[32.3,31.3],
               [32.3,31.0],[31.8,30.8],[31.2,30.7],[30.6,30.8],[30.0,31.0],
               [29.6,31.2],[29.6,31.4]], "Northern delta"),
    ),
    ("Egypt — Nile Delta", 1.0): _fc(
        _poly([[29.5,31.5],[30.0,31.7],[30.8,31.8],[31.5,31.7],[32.2,31.5],
               [32.5,31.2],[32.3,30.8],[31.8,30.5],[31.2,30.4],[30.5,30.5],
               [30.0,30.7],[29.6,31.0],[29.5,31.5]], "Major delta"),
    ),
    ("Egypt — Nile Delta", 1.5): _fc(
        _poly([[29.4,31.6],[30.0,31.9],[30.8,32.0],[31.5,31.9],[32.3,31.7],
               [32.6,31.3],[32.4,30.8],[31.8,30.3],[31.0,30.2],[30.2,30.3],
               [29.7,30.6],[29.4,31.0],[29.4,31.6]], "Extended delta"),
    ),
    ("Egypt — Nile Delta", 2.0): _fc(
        _poly([[29.3,31.7],[30.0,32.0],[31.0,32.1],[32.0,32.0],[32.7,31.7],
               [33.0,31.2],[32.5,30.5],[31.8,30.0],[30.8,29.9],[30.0,30.1],
               [29.5,30.5],[29.3,31.0],[29.3,31.7]], "Deep delta inundation"),
    ),

    # ── Tuvalu (Funafuti atoll) ───────────────────────────────────────────────────
    ("Tuvalu — Pacific Island Nation", 0.3): _fc(
        _poly([[179.18,-8.55],[179.20,-8.55],[179.21,-8.52],[179.20,-8.49],
               [179.18,-8.49],[179.17,-8.52],[179.18,-8.55]], "Funafuti fringe"),
    ),
    ("Tuvalu — Pacific Island Nation", 0.6): _fc(
        _poly([[179.17,-8.60],[179.22,-8.60],[179.23,-8.52],[179.22,-8.45],
               [179.17,-8.45],[179.16,-8.52],[179.17,-8.60]], "Funafuti"),
    ),
    ("Tuvalu — Pacific Island Nation", 1.0): _fc(
        _poly([[179.16,-8.63],[179.23,-8.63],[179.24,-8.52],[179.23,-8.42],
               [179.16,-8.42],[179.15,-8.52],[179.16,-8.63]], "Funafuti — most of atoll"),
        _poly([[179.06,-8.10],[179.12,-8.10],[179.12,-8.05],[179.06,-8.05],
               [179.06,-8.10]], "Outer islets"),
    ),
    ("Tuvalu — Pacific Island Nation", 1.5): _fc(
        _poly([[179.15,-8.68],[179.25,-8.68],[179.26,-8.52],[179.25,-8.38],
               [179.15,-8.38],[179.14,-8.52],[179.15,-8.68]], "Funafuti"),
        _poly([[179.05,-8.15],[179.14,-8.15],[179.14,-7.95],[179.05,-7.95],
               [179.05,-8.15]], "Northern islets"),
    ),
    ("Tuvalu — Pacific Island Nation", 2.0): _fc(
        _poly([[179.13,-8.73],[179.27,-8.73],[179.28,-8.52],[179.27,-8.35],
               [179.13,-8.35],[179.12,-8.52],[179.13,-8.73]], "Near-total inundation"),
        _poly([[179.04,-8.18],[179.15,-8.18],[179.15,-7.90],[179.04,-7.90],
               [179.04,-8.18]], "Northern atolls"),
    ),
}

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');

:root {
  --bg:       #f0f9ff;
  --glass:    rgba(255,255,255,0.76);
  --glass-b:  rgba(255,255,255,0.58);
  --glass-bd: rgba(0,0,0,0.06);
  --text-1:   #0c1a2b;
  --text-2:   #334155;
  --text-3:   #94a3b8;
  --accent:   #0891b2;
  --accent-2: #1d4ed8;
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
    radial-gradient(ellipse at 12% 18%,  rgba(8,145,178,0.08)   0%, transparent 52%),
    radial-gradient(ellipse at 88% 82%,  rgba(29,78,216,0.06)   0%, transparent 52%),
    radial-gradient(ellipse at 52% 48%,  rgba(14,165,233,0.04)  0%, transparent 65%),
    linear-gradient(160deg, #f0f9ff 0%, #e0f2fe 40%, #f0f9ff 100%) !important;
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
  background: rgba(240,249,255,0.88) !important;
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
.metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }
.metric-card {
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.72);
  border-radius: var(--r-sm); padding: 10px 11px;
  box-shadow: var(--sh-sm); animation: fadeSlideUp 0.3s ease both;
}
.metric-label { font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); margin-bottom: 3px; }
.metric-value { font-size: 18px; font-weight: 600; color: var(--text-1); line-height: 1.15; font-variant-numeric: tabular-nums; }
.metric-unit  { font-size: 10px; color: var(--text-3); font-weight: 400; margin-left: 2px; }

/* ── Country heading & wave badge ── */
.country-heading { font-size: 17px; font-weight: 600; color: var(--text-1); letter-spacing: -0.02em; line-height: 1.25; margin-bottom: 6px; }
.wave-badge { display: flex; align-items: center; gap: 10px; margin: 2px 0 10px; }

/* ── Story / dramatic fact / compound risk cards ── */
.story-card {
  font-size: 12px; line-height: 1.85; color: var(--text-2); margin-bottom: 10px;
  background: rgba(255,255,255,0.76);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.65); border-radius: var(--r-sm);
  padding: 12px 14px; box-shadow: var(--sh-sm); animation: fadeSlideUp 0.35s 0.08s ease both;
}
.dramatic-fact {
  background: linear-gradient(135deg, rgba(8,145,178,0.06) 0%, rgba(255,255,255,0.64) 100%);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.65);
  border-left: 3px solid var(--fact-color, #0891b2);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 11px 13px; margin: 0 0 10px;
  box-shadow: var(--sh-sm); font-size: 11px; line-height: 1.75; color: #1e3a5f;
  animation: fadeSlideUp 0.4s 0.05s ease both;
}
.compound-risk {
  border: 1px solid rgba(29,78,216,0.28); border-left: 3px solid #1d4ed8;
  background: rgba(219,234,254,0.32);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 11px 13px; margin: 0 0 10px;
  box-shadow: 0 2px 8px rgba(29,78,216,0.08);
}
.compound-risk-title { font-size: 9px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #1d4ed8; margin-bottom: 5px; }
.compound-risk-body  { font-size: 11px; line-height: 1.75; color: #334155; }

/* ── Stats strip ── */
.strip-row { display: flex; gap: 10px; margin: 4px 0 8px; padding: 0 1px; }
.strip-card {
  flex: 1; min-width: 0;
  background: rgba(255,255,255,0.76);
  backdrop-filter: blur(24px) saturate(160%); -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,0.68); border-radius: var(--r);
  padding: 13px 15px; box-shadow: var(--sh-sm);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
  animation: fadeSlideUp 0.4s ease both; cursor: default;
}
.strip-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.strip-icon { margin-bottom: 6px; font-size: 16px; }
.strip-n { font-size: 22px; font-weight: 300; line-height: 1.1; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.strip-l { font-size: 9px; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-3); line-height: 1.4; }

/* ── Narrative bar ── */
.narrative-bar {
  background: rgba(255,255,255,0.70); backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid rgba(255,255,255,0.62); border-radius: var(--r);
  padding: 14px 18px; margin: 6px 0 8px; box-shadow: var(--sh-sm);
  animation: slideDown 0.4s 0.1s ease both;
}
.narrative-lede { font-size: 14px; font-weight: 500; color: var(--text-1); line-height: 1.6; margin-bottom: 6px; letter-spacing: -0.01em; }
.narrative-context { font-size: 11px; color: var(--text-2); line-height: 1.7; }
.narrative-pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(8,145,178,0.09); border: 1px solid rgba(8,145,178,0.22);
  border-radius: 99px; padding: 2px 9px;
  font-size: 10px; font-weight: 600; color: #0891b2; vertical-align: middle; margin: 0 3px;
}
.narrative-pill-red {
  background: rgba(127,29,29,0.09); border-color: rgba(127,29,29,0.22); color: #7f1d1d;
}

/* ── Intro card ── */
.intro-card {
  background: rgba(255,255,255,0.82); backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,0.72);
  border-top: 2px solid rgba(8,145,178,0.42);
  border-radius: var(--r); padding: 18px 22px; margin: 4px 0 10px;
  animation: slideDown 0.4s ease both; box-shadow: var(--sh-md);
}
.intro-heading { font-size: 15px; font-weight: 600; color: var(--text-1); margin: 0 0 12px; letter-spacing: -0.02em; }
.intro-pillars { display: flex; gap: 12px; flex-wrap: wrap; }
.intro-pillar {
  flex: 1; min-width: 140px;
  background: rgba(8,145,178,0.04); border: 1px solid rgba(8,145,178,0.12);
  border-radius: var(--r-sm); padding: 10px 12px;
}
.intro-pillar-icon  { font-size: 18px; margin-bottom: 5px; }
.intro-pillar-title { font-size: 11px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.intro-pillar-body  { font-size: 10px; line-height: 1.65; color: var(--text-2); }

/* ── Flood callout ── */
.flood-callout {
  background: linear-gradient(135deg, rgba(8,145,178,0.08) 0%, rgba(255,255,255,0.70) 100%);
  border: 1px solid rgba(8,145,178,0.22);
  border-radius: var(--r); padding: 14px 18px; margin: 8px 0;
  box-shadow: var(--sh-sm); font-size: 12px; line-height: 1.75; color: var(--text-2);
}
.flood-callout strong { color: var(--text-1); }

/* ── Method note ── */
.method-note {
  font-size: 10px; color: var(--text-3); line-height: 1.65;
  background: rgba(8,145,178,0.04); border: 1px solid rgba(8,145,178,0.10);
  border-radius: var(--r-sm); padding: 9px 13px; margin-top: 12px;
}

/* ── Misc UI ── */
.sep { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 13px 0; }
.day-label   { font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-3); }
.data-footer { font-size: 10px; color: var(--text-3); letter-spacing: 0.04em; line-height: 2.0; }
.no-data-note { font-size: 10px; color: var(--text-3); padding: 2px 4px 6px; }

/* ── Tabs ── */
button[data-baseweb="tab"] {
  color: var(--text-3) !important; font-size: 11px !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  background: transparent !important; font-family: 'Inter', sans-serif !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--text-1) !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: rgba(0,0,0,0.08) !important; }
[data-testid="stTabsContent"] { background: transparent !important; padding-top: 10px !important; }

/* ── Select ── */
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
@keyframes wavePulse {
  0%, 100% { transform: translateX(0); }
  50%      { transform: translateX(4px); }
}

/* ── Mobile ── */
@media (max-width: 768px) {
  .main .block-container { padding-left: 10px !important; padding-right: 10px !important; }
  .strip-row { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 8px !important; }
  .strip-card { min-width: unset !important; }
  .intro-pillars { flex-direction: column !important; gap: 8px !important; }
  button[data-baseweb="tab"] { padding: 10px 8px !important; font-size: 10px !important; }
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
    """Fetch annual mean sea level from NOAA CO-OPS (2000–2023)."""
    try:
        r = requests.get(NOAA_API, params={
            "station": station_id,
            "product": "monthly_mean",
            "datum": "MSL",
            "time_zone": "GMT",
            "begin_date": "20000101",
            "end_date": "20231231",
            "units": "metric",
            "format": "json",
            "application": "ResilienceStack",
        }, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    records = data.get("data", [])
    if not records:
        return {}

    # Aggregate to annual means
    year_vals: dict[int, list[float]] = {}
    for rec in records:
        try:
            yr  = int(rec["t"][:4])
            msl = float(rec["MSL"])
            year_vals.setdefault(yr, []).append(msl)
        except (KeyError, ValueError):
            continue

    years     = sorted(year_vals)
    ann_means = [sum(year_vals[y]) / len(year_vals[y]) for y in years]
    if not years:
        return {}

    # Normalise so year-2000 = 0 mm
    baseline  = ann_means[0]
    ann_rel   = [(v - baseline) * 1000 for v in ann_means]  # → mm

    # Linear trend
    n   = len(years)
    x_m = sum(years) / n
    y_m = sum(ann_rel) / n
    den = sum((y - x_m) ** 2 for y in years) or 1
    slope = sum((y - x_m) * (ann_rel[i] - y_m) for i, y in enumerate(years)) / den

    return {
        "years": years,
        "values_mm": ann_rel,
        "slope_mm_yr": round(slope, 2),
        "total_rise_mm": round(ann_rel[-1] - ann_rel[0], 1),
    }


# ── Core helpers ───────────────────────────────────────────────────────────────
def risk_band(pct: float | None) -> tuple[str, str, str]:
    if pct is None:
        return "N/A", "#94a3b8", "rgba(148,163,184,0.08)"
    for threshold, label, fg, bg in RISK_BANDS:
        if pct >= threshold:
            return label, fg, bg
    return "LOW", "#38bdf8", "rgba(56,189,248,0.09)"


def pop_at_slr(iso: str, slr_m: float) -> int | None:
    if iso not in COASTAL_DATA:
        return None
    p1, p2, p3, *_ = COASTAL_DATA[iso]
    if slr_m <= 0.0:
        return 0
    if slr_m <= 0.65:
        frac = slr_m / 1.0
        return int(p1 * frac * 0.55)
    if slr_m <= 1.05:
        return p1
    if slr_m <= 1.55:
        return int(p1 + (p2 - p1) * (slr_m - 1.0) / 1.0)
    return p2 if slr_m <= 1.55 else p3


def _fmt(v, dec: int = 1, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.{dec}f}{unit}"


def _fmt_pop(k: int | None) -> str:
    if k is None:
        return "—"
    if k >= 1_000_000:
        return f"{k/1_000_000:.1f}B"
    if k >= 1_000:
        return f"{k/1_000:.1f}M"
    return f"{k}K"


# ── SVG helpers ───────────────────────────────────────────────────────────────
def wave_svg(color: str = "#0891b2") -> str:
    return f"""<svg width="48" height="32" viewBox="0 0 60 40" fill="none" xmlns="http://www.w3.org/2000/svg"
     style="animation: wavePulse 2s ease-in-out infinite">
  <path d="M2 28 C8 20, 14 20, 20 28 S32 36, 38 28 S50 20, 56 28"
        stroke="{color}" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.9"/>
  <path d="M2 20 C8 12, 14 12, 20 20 S32 28, 38 20 S50 12, 56 20"
        stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.55"/>
  <path d="M2 12 C8 4,  14 4,  20 12 S32 20, 38 12 S50 4,  56 12"
        stroke="{color}" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.30"/>
</svg>"""


# ── HTML component builders ────────────────────────────────────────────────────
def _stats_strip(df: pd.DataFrame) -> str:
    critical   = int((df["risk_pct"] >= 20).sum())
    total_1m   = int(df["pop_1m_k"].sum())
    fastest    = df.loc[df["slr_mm_yr"].idxmax()]
    existential = int((df["risk_pct"] >= 50).sum())

    cards = [
        ("🌊", f'<span style="color:#1d4ed8">{critical}</span>', "countries — critical or worse"),
        ("👥", _fmt_pop(total_1m), "people within 1 m elevation"),
        ("📈", fastest["country_name"], f'{fastest["slr_mm_yr"]:.1f} mm/yr · fastest rising'),
        ("🏝️", f"{existential}", "countries — existential risk (>50 % at risk)"),
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
    critical = int((df["risk_pct"] >= 10).sum())
    total_1m  = int(df["pop_1m_k"].sum())
    return f"""<div class="narrative-bar">
  <div class="narrative-lede">
    <span class="narrative-pill">{_fmt_pop(total_1m)} people</span> live within 1 metre of sea level today —
    and the ocean is rising faster than at any point in recorded history.
  </div>
  <div class="narrative-context">
    The IPCC projects <strong>0.3–1.0 m of global mean sea level rise by 2100</strong> under current
    emissions trajectories, with up to 2 m possible if ice sheets destabilise.
    <span class="narrative-pill">{critical} nations</span> already face severe or worse exposure,
    concentrated in low-elevation river deltas, small island states, and subsiding megacities.
    Unlike other climate risks, sea level rise is effectively irreversible on human timescales.
  </div>
</div>"""


def _country_fact(r: pd.Series, water_stress: float | None) -> tuple[str, str]:
    name    = r.get("country_name", "")
    p1      = r.get("pop_1m_k",  0) or 0
    pct     = r.get("risk_pct",  0) or 0
    slr     = r.get("slr_mm_yr", 3) or 3
    coast   = r.get("coastline_km", 0) or 0

    if pct >= 50:
        fact  = (f"<strong>{name}</strong> faces an <strong>existential threat</strong>. "
                 f"More than half the country's population — {_fmt_pop(p1)} people — "
                 f"lives within 1 m of sea level. At +1.5 m, the nation as a geographic entity may cease to exist.")
        color = "#7f1d1d"
    elif pct >= 20:
        fact  = (f"<strong>{name}</strong> has <strong>{_fmt_pop(p1)} people within 1 m elevation</strong> "
                 f"({pct:.1f} % of the population). Sea level is rising at {slr:.1f} mm/yr at representative gauges. "
                 f"Displacement is not a future risk — it is already beginning.")
        color = "#1d4ed8"
    elif pct >= 10:
        fact  = (f"In <strong>{name}</strong>, <strong>{_fmt_pop(p1)} people</strong> ({pct:.1f} % of the population) "
                 f"occupy land below 1 m elevation. With {coast:,.0f} km of coastline and rising seas, "
                 f"adaptation costs are already running into billions annually.")
        color = "#0891b2"
    elif pct >= 3:
        fact  = (f"<strong>{name}</strong> has {_fmt_pop(p1)} people within 1 m of sea level. "
                 f"The risk is concentrated in coastal cities and river mouths rather than spread evenly — "
                 f"making targeted infrastructure investment the critical lever.")
        color = "#0e7490"
    else:
        fact  = (f"<strong>{name}</strong> currently faces low coastal population exposure. "
                 f"At {slr:.1f} mm/yr of sea level rise, the cumulative effect by 2100 will still reshape "
                 f"coastal infrastructure, tourism zones, and flood insurance markets significantly.")
        color = "#38bdf8"

    return f'<div class="dramatic-fact" style="--fact-color:{color}">{fact}</div>', color


def _country_panel(r: pd.Series, water_stress: float | None) -> str:
    name    = r.get("country_name", r.get("iso", ""))
    p1      = r.get("pop_1m_k",  0) or 0
    p2      = r.get("pop_2m_k",  0) or 0
    slr     = r.get("slr_mm_yr", 3) or 3
    coast   = r.get("coastline_km", 0) or 0
    pct     = r.get("risk_pct",  0) or 0
    label, fg, _bg = risk_band(pct)

    fact_html, fact_color = _country_fact(r, water_stress)
    wv        = wave_svg(fg)

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
    <div class="metric-value">{_fmt(slr, 1)}<span class="metric-unit">mm/yr</span></div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Coastline</div>
    <div class="metric-value">{coast:,.0f}<span class="metric-unit">km</span></div>
  </div>
</div>"""

    proj_html = f"""<div style="font-size:10px;color:var(--text-3);margin:6px 0 2px;letter-spacing:0.06em;text-transform:uppercase">Population at risk by scenario</div>
<div style="display:flex;gap:8px;margin-bottom:8px">
  <div style="flex:1;background:rgba(8,145,178,0.08);border:1px solid rgba(8,145,178,0.18);border-radius:8px;padding:7px 9px;text-align:center">
    <div style="font-size:8px;color:#0e7490;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px">+1.0 m</div>
    <div style="font-size:16px;font-weight:600;color:#0891b2">{_fmt_pop(p1)}</div>
  </div>
  <div style="flex:1;background:rgba(29,78,216,0.08);border:1px solid rgba(29,78,216,0.18);border-radius:8px;padding:7px 9px;text-align:center">
    <div style="font-size:8px;color:#1d4ed8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px">+2.0 m</div>
    <div style="font-size:16px;font-weight:600;color:#1d4ed8">{_fmt_pop(p2)}</div>
  </div>
</div>"""

    compound = ""
    if water_stress and water_stress > 25:
        compound = f"""<div class="compound-risk">
  <div class="compound-risk-title">⚠ Saltwater intrusion risk</div>
  <div class="compound-risk-body">Water stress at {water_stress:.0f}% combined with coastal flooding
  creates saltwater intrusion into freshwater aquifers — degrading drinking water and
  irrigation supplies simultaneously with displacement pressure.</div>
</div>"""

    return f"""<div class="country-heading">{name}</div>
<div class="wave-badge">{wv}
  <div>
    <div style="font-size:10px;color:{fg};font-weight:700;letter-spacing:0.1em;text-transform:uppercase">{label}</div>
    <div style="font-size:10px;color:var(--text-3)">{pct:.1f}% of population within 1 m</div>
  </div>
</div>
{metrics}
{proj_html}
{fact_html}
{compound}"""


# ── Chart builders ─────────────────────────────────────────────────────────────
def make_risk_map(df: pd.DataFrame, selected_iso: str, slr_m: float) -> go.Figure:
    plot_df = df.copy()
    # Scale pop at given SLR scenario for colour
    def _scaled_pop(r):
        if slr_m <= 0.05:
            return 0.0
        p1, p2, p3 = r["pop_1m_k"], r["pop_2m_k"], r["pop_3m_k"]
        if slr_m <= 1.05:
            return p1 * (slr_m / 1.0)
        if slr_m <= 2.05:
            return p1 + (p2 - p1) * (slr_m - 1.0)
        return p2 + (p3 - p2) * (slr_m - 2.0)
    plot_df["display_pop"] = plot_df.apply(_scaled_pop, axis=1)
    plot_df["display_pop_fmt"] = plot_df["display_pop"].apply(lambda v: _fmt_pop(int(v)))

    fig = px.choropleth(
        plot_df,
        locations="iso",
        color="display_pop",
        hover_name="country_name",
        hover_data={"iso": False, "display_pop": False, "display_pop_fmt": True, "slr_mm_yr": ":.1f"},
        color_continuous_scale=CSCALE,
        range_color=(0, plot_df["display_pop"].quantile(0.95)),
        labels={"display_pop_fmt": "Population at risk", "slr_mm_yr": "SLR rate (mm/yr)"},
    )
    fig.update_traces(
        marker_line_width=0.4,
        marker_line_color="rgba(255,255,255,0.4)",
        hovertemplate="<b>%{hovertext}</b><br>At risk: %{customdata[0]}<br>SLR rate: %{customdata[1]:.1f} mm/yr<extra></extra>",
    )
    # Extreme countries outline
    extreme = plot_df[plot_df["risk_pct"] >= 50]
    if not extreme.empty:
        fig.add_trace(go.Choropleth(
            locations=extreme["iso"], z=[1] * len(extreme),
            colorscale=[[0, "rgba(127,29,29,0)"], [1, "rgba(127,29,29,0)"]],
            showscale=False, marker_line_width=1.2, marker_line_color="#7f1d1d",
            hoverinfo="skip",
        ))
    # Selected country
    if selected_iso:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso], z=[1],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, marker_line_width=2.4, marker_line_color="#0891b2",
            hoverinfo="skip",
        ))
    fig.update_geos(
        showframe=False, showcoastlines=False, showland=True,
        landcolor="rgba(241,245,249,0.9)",
        showocean=True, oceancolor="rgba(186,230,253,0.55)",
        showcountries=False, projection_type="natural earth",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_coloraxes(colorbar=dict(
        title=dict(text="People at risk", font=dict(size=10, color="#334155")),
        thickness=10, len=0.55, x=1.0, y=0.5,
        tickfont=dict(size=9, color="#334155"),
        bgcolor="rgba(255,255,255,0.5)",
        bordercolor="rgba(0,0,0,0.1)", borderwidth=1,
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=480,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def make_tide_chart(gauge_data: dict, station_name: str) -> go.Figure:
    years  = gauge_data.get("years", [])
    values = gauge_data.get("values_mm", [])
    slope  = gauge_data.get("slope_mm_yr", 0)
    if not years:
        return go.Figure()

    n   = len(years)
    x_m = sum(years) / n
    y_m = sum(values) / n
    trend = [y_m + slope * (y - x_m) for y in years]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=values, mode="lines+markers",
        name="Annual mean sea level",
        line=dict(color="#0891b2", width=2),
        marker=dict(size=5, color="#0891b2"),
        fill="tozeroy", fillcolor="rgba(8,145,178,0.08)",
        hovertemplate="%{x}: %{y:.0f} mm above 2000 baseline<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=trend, mode="lines",
        name=f"Trend ({slope:+.1f} mm/yr)",
        line=dict(color="#1d4ed8", width=1.8, dash="dot"),
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.5)",
        legend=dict(orientation="h", x=0, y=-0.2, font=dict(size=9, color="#334155"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#334155")),
        yaxis=dict(
            title=dict(text="mm above 2000 baseline", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=True,
            zerolinecolor="rgba(8,145,178,0.3)", tickfont=dict(size=9, color="#334155"),
        ),
        title=dict(text=f"Sea level rise — {station_name}", font=dict(size=12, color="#0c1a2b"), x=0.02),
    )
    return fig


def make_city_risk_chart(df: pd.DataFrame, slr_m: float) -> go.Figure:
    plot_df = df.copy()
    def _pop(r):
        p1, p2, p3 = r["pop_1m_k"], r["pop_2m_k"], r["pop_3m_k"]
        if slr_m <= 1.05:
            return p1
        if slr_m <= 2.05:
            return p1 + (p2 - p1) * (slr_m - 1.0)
        return p3
    plot_df["scen_pop"] = plot_df.apply(_pop, axis=1)
    top = plot_df.nlargest(25, "scen_pop").reset_index(drop=True)
    colors = [risk_band(r["risk_pct"])[1] for _, r in top.iterrows()]

    fig = go.Figure(go.Bar(
        x=top["scen_pop"] / 1000,
        y=top["country_name"],
        orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[_fmt_pop(int(v)) for v in top["scen_pop"]],
        textposition="outside", textfont=dict(size=8),
        hovertemplate="<b>%{y}</b><br>Population at risk: %{text}<extra></extra>",
    ))
    fig.update_layout(
        height=560, margin=dict(l=8, r=40, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.5)",
        xaxis=dict(
            title=dict(text="Population at risk (millions)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#334155")),
        title=dict(text="Top 25 countries by population at risk", font=dict(size=12, color="#0c1a2b"), x=0.01),
    )
    return fig


def make_compound_scatter(df: pd.DataFrame, water_stress: dict) -> go.Figure:
    rows = []
    for _, r in df.iterrows():
        ws = water_stress.get(r["iso"])
        if ws is not None:
            rows.append({"iso": r["iso"], "name": r["country_name"],
                         "pop": r["pop_1m_k"], "water": ws, "slr": r["slr_mm_yr"]})
    if not rows:
        return go.Figure()
    sdf = pd.DataFrame(rows)
    colors = [risk_band(
        (COASTAL_DATA[r["iso"]][0] / max(1, sum(1 for _ in range(1))) * 100)
        if r["iso"] in COASTAL_DATA else 0
    )[1] for _, r in sdf.iterrows()]
    # Use pre-computed risk_pct from main df
    sdf = sdf.merge(df[["iso", "risk_pct"]], on="iso", how="left")
    colors = [risk_band(v)[1] for v in sdf["risk_pct"].fillna(0)]

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
        hovertemplate="<b>%{customdata[0]}</b><br>Pop. at risk (1m): %{customdata[1]:.0f}K<br>Water stress: %{customdata[2]:.0f}%<br>SLR rate: %{customdata[3]:.1f} mm/yr<extra></extra>",
    ))
    fig.add_shape(type="rect", x0=5000, x1=120000, y0=40, y1=110,
                  fillcolor="rgba(29,78,216,0.06)", line_width=0)
    fig.add_annotation(x=60000, y=105, text="⚠ COMPOUND COASTAL + WATER CRISIS",
                       font=dict(size=8, color="#1d4ed8"), showarrow=False)
    fig.update_layout(
        height=420, margin=dict(l=8, r=8, t=20, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.52)",
        xaxis=dict(
            title=dict(text="Population within 1 m elevation (thousands)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        yaxis=dict(
            title=dict(text="Water withdrawal stress (%)", font=dict(size=9, color="#334155")),
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=9, color="#334155"),
        ),
        title=dict(
            text="Compound coastal + water stress (bubble size = SLR rate mm/yr)",
            font=dict(size=11, color="#0c1a2b"), x=0.01,
        ),
    )
    return fig


# ── Folium flood viewer ────────────────────────────────────────────────────────
def make_flood_map(region_name: str, slr_m: float) -> folium.Map:
    region = HOTSPOT_REGIONS[region_name]
    m = folium.Map(
        location=region["center"],
        zoom_start=region["zoom"],
        tiles="CartoDB positron",
        attr="© CartoDB · © OpenStreetMap contributors",
    )

    if region["is_noaa"] and slr_m > 0:
        ft = SLR_TO_FT.get(slr_m)
        if ft:
            wms_url = f"https://coast.noaa.gov/arcgis/services/dc_slr/slr_{ft}ft/MapServer/WmsServer"
            try:
                folium.WmsTileLayer(
                    url=wms_url,
                    name=f"NOAA SLR {ft}ft inundation",
                    fmt="image/png",
                    transparent=True,
                    layers="0",
                    overlay=True,
                    control=False,
                    opacity=0.65,
                ).add_to(m)
            except Exception:
                pass
    else:
        key = (region_name, slr_m)
        geojson = FLOOD_ZONES.get(key)
        if geojson and slr_m > 0:
            folium.GeoJson(
                geojson,
                name="Flood zone",
                style_function=lambda _: {
                    "fillColor":   "#0ea5e9",
                    "color":       "#0891b2",
                    "weight":      1.5,
                    "fillOpacity": 0.52,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["label"],
                    aliases=["Zone:"],
                    style="font-size:11px;font-family:Inter,sans-serif",
                ),
            ).add_to(m)

    # City marker
    center = region["center"]
    folium.CircleMarker(
        location=center,
        radius=7, color="#0891b2", fill=True, fill_color="#0891b2",
        fill_opacity=0.9, weight=2,
        tooltip=folium.Tooltip(
            f"<b style='font-family:Inter,sans-serif'>{region_name}</b><br>"
            f"<span style='font-size:10px;color:#334155'>{region['narrative']}</span>",
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
    for iso, (p1, p2, p3, slr, coast) in COASTAL_DATA.items():
        name = country_names.get(iso, iso)
        # Approximate national population (World Bank) for risk%  — use p1/(pop) if known
        # We embed rough country populations to compute exposure %
        POP_APPROX = {
            "BGD":170e3,"CHN":1400e3,"IND":1380e3,"VNM":97e3,"IDN":270e3,
            "MDV":  540,"USA":330e3,"NLD":17e3,"EGY":100e3,"THA":70e3,
            "PHL":110e3,"MMR":55e3,"PAK":220e3,"BRA":215e3,"JPN":126e3,
            "GBR":67e3,"DEU":83e3,"NGA":210e3,"MYS":32e3,"KHM":16e3,
            "TUV":   11,"KIR": 120,"MHL":  60,"FJI":900,"PNG":9e3,
            "AUS":25e3,"MEX":128e3,"MOZ":32e3,"TZA":60e3,"ZAF":60e3,
            "AGO":33e3,"GHA":31e3,"SEN":17e3,"IRN":85e3,"SAU":35e3,
            "ARE": 10e3,"KWT": 4e3,"QAT": 3e3,"BHR": 1700,"LKA":22e3,
            "IRQ":40e3,"CAN":38e3,"RUS":144e3,"FRA":67e3,"ITA":60e3,
            "ESP":47e3,"DNK": 6e3,"NOR": 5e3,"POL":38e3,"TUR":84e3,
            "GRC":11e3,"PRT":10e3,"MRT": 4e3,"SOM":15e3,"SGP": 6e3,
            "HKG": 7e3,"GTM":17e3,"HND": 9e3,"NIC": 6e3,
        }
        pop_total = POP_APPROX.get(iso, 30e3)
        risk_pct  = (p1 / pop_total * 100) if pop_total > 0 else 0
        rows.append({
            "iso": iso, "country_name": name,
            "pop_1m_k": p1, "pop_2m_k": p2, "pop_3m_k": p3,
            "slr_mm_yr": slr, "coastline_km": coast,
            "risk_pct": round(risk_pct, 2),
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

        selected_row = df[df["iso"] == selected_iso].iloc[0]
        ws_val       = water_stress_raw.get(selected_iso)
        st.markdown(_country_panel(selected_row, ws_val), unsafe_allow_html=True)

        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("""<div class="data-footer">
Sources: Kulp & Strauss 2019 · Nat. Comms.<br>
Climate Central · IPCC AR6 Ch. 9<br>
NOAA CO-OPS tide gauges · World Bank ER.H2O.FWTL.ZS<br>
NOAA Digital Coast SLR inundation tiles
</div>""", unsafe_allow_html=True)
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown('<div class="data-footer"><a href="day05_extreme_heat" style="color:var(--text-3)">← Day 05 · Extreme Heat</a></div>', unsafe_allow_html=True)

    # ── Main area ──────────────────────────────────────────────────────────────
    # Intro card
    if not st.session_state.get("hide_intro_06"):
        cols_intro = st.columns([1, 20, 1])
        with cols_intro[1]:
            st.markdown("""<div class="intro-card">
<div class="intro-heading">Why sea level rise is unlike any other climate risk</div>
<div class="intro-pillars">
  <div class="intro-pillar">
    <div class="intro-pillar-icon">🌊</div>
    <div class="intro-pillar-title">Irreversibility</div>
    <div class="intro-pillar-body">Even if emissions reach net-zero tomorrow, thermal expansion and ice melt already locked in will raise seas for centuries. The land displaced today does not return on any human planning horizon.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">📉</div>
    <div class="intro-pillar-title">Subsidence multiplier</div>
    <div class="intro-pillar-body">Jakarta sinks 25 cm/yr from groundwater extraction — 10× the IPCC global mean. Effective relative SLR in some megacities already exceeds the worst-case 2100 IPCC scenario.</div>
  </div>
  <div class="intro-pillar">
    <div class="intro-pillar-icon">⚡</div>
    <div class="intro-pillar-title">Compound crises</div>
    <div class="intro-pillar-body">Rising seas contaminate freshwater aquifers with salt, destroying irrigation sources. Combined with Day 03 water stress and Day 05 heat, coastal delta nations face simultaneous displacement, food, and water shocks.</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)
        if st.button("Dismiss", key="dismiss_intro_06"):
            st.session_state.hide_intro_06 = True
            st.rerun()

    # Stats strip + narrative
    st.markdown(_stats_strip(df), unsafe_allow_html=True)
    st.markdown(_narrative_bar(df), unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "RISK MAP", "FLOOD VIEWER", "SEA LEVEL HISTORY", "COMPOUND RISK",
    ])

    # ── TAB 1: Risk Map ────────────────────────────────────────────────────────
    with tab1:
        scenario_label = st.select_slider(
            "Sea level rise scenario",
            options=list(SLR_SCENARIOS.keys()),
            value="Today — current coastline",
            key="slr_scenario_06",
        )
        slr_m = SLR_SCENARIOS[scenario_label]

        if slr_m > 0:
            total_at_risk = int(sum(
                (r["pop_1m_k"] if slr_m >= 1.0 else r["pop_1m_k"] * slr_m)
                for _, r in df.iterrows()
            ))
            st.markdown(
                f'<div style="font-size:11px;color:#0e7490;padding:4px 0 6px">'
                f'At <strong>{scenario_label}</strong>: estimated '
                f'<strong>{_fmt_pop(total_at_risk)}</strong> people at direct inundation risk globally. '
                f'Countries that were moderate today enter SEVERE or CRITICAL tier.</div>',
                unsafe_allow_html=True,
            )

        map_fig = make_risk_map(df, selected_iso, slr_m)
        event   = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun", key="coast_map")

        if event and event.get("selection", {}).get("points"):
            clicked = event["selection"]["points"][0].get("location")
            if clicked and clicked in df["iso"].values:
                selected_iso  = clicked
                selected_name = df[df["iso"] == clicked]["country_name"].iloc[0]

        # Legend
        legend_bands = [
            ("#e0f2fe", "LOW",         "<1% at risk"),
            ("#38bdf8", "MODERATE",    "1–3%"),
            ("#0ea5e9", "HIGH",        "3–10%"),
            ("#0284c7", "SEVERE",      "10–20%"),
            ("#1d4ed8", "CRITICAL",    "20–50%"),
            ("#7f1d1d", "EXISTENTIAL", ">50%"),
        ]
        legend_parts = " ".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block"></span>'
            f'<span style="font-size:9px;color:#78716c;letter-spacing:0.06em">{label} ({rng})</span>'
            f'</span>'
            for c, label, rng in legend_bands
        )
        st.markdown(
            f'<div style="padding:4px 2px 8px;display:flex;flex-wrap:wrap">{legend_parts}</div>',
            unsafe_allow_html=True,
        )

        # Subsidence callout
        st.markdown("""<div class="flood-callout">
<strong>The subsidence multiplier:</strong> global mean SLR of 3–4 mm/yr is just part of the picture.
Jakarta (Indonesia) is sinking at <strong>25 cm/yr</strong> from groundwater pumping —
an effective relative SLR of ~30 cm/yr. Ho Chi Minh City: 30–70 mm/yr. Bangkok: 30–80 mm/yr.
These cities are experiencing the 2100 worst-case scenario <em>right now</em>.
</div>""", unsafe_allow_html=True)

    # ── TAB 2: Flood Viewer ────────────────────────────────────────────────────
    with tab2:
        c_left, c_right = st.columns([2, 1])
        with c_left:
            region_name = st.selectbox(
                "Select a coastal hotspot",
                list(HOTSPOT_REGIONS.keys()),
                key="region_06",
            )
        with c_right:
            slr_label_2 = st.select_slider(
                "SLR scenario",
                options=list(SLR_SCENARIOS.keys()),
                value="+1.0m — SSP3-7.0 by 2100",
                key="slr_flood_06",
            )
        slr_m2  = SLR_SCENARIOS[slr_label_2]
        region  = HOTSPOT_REGIONS[region_name]
        pop_k   = region["pop_k"].get(slr_m2, 0)

        # Callout
        is_noaa = region["is_noaa"]
        noaa_note = (
            " Flood zones rendered using <strong>NOAA Digital Coast</strong> pre-computed inundation tiles."
            if is_noaa else
            " Flood zones are <strong>research-based simplified approximations</strong> (Kulp & Strauss 2019, Climate Central)."
        )

        if slr_m2 == 0.0:
            callout = f"""<div class="flood-callout">
<strong>{region_name}</strong> — current coastline shown. Use the slider to see projected inundation.
<br><span style="font-size:10px;color:var(--text-3)">{region['narrative']}</span>
</div>"""
        else:
            callout = f"""<div class="flood-callout">
<strong>At {slr_label_2}:</strong> an estimated <strong>{_fmt_pop(pop_k)} people</strong> in this region
face inundation or chronic flooding risk. <span style="color:#0891b2">Blue areas</span> show
land at or below the {slr_m2:.1f} m flood threshold.
<br><span style="font-size:10px;color:var(--text-3)">{region['narrative']}{noaa_note}</span>
</div>"""
        st.markdown(callout, unsafe_allow_html=True)

        flood_map = make_flood_map(region_name, slr_m2)
        st_folium(flood_map, use_container_width=True, height=500, returned_objects=[])

        st.markdown(
            '<div class="method-note">Flood zones for non-US regions are simplified research-based polygons '
            'approximating areas at or below each SLR threshold. US/Miami region uses NOAA Digital Coast '
            'pre-computed inundation tiles (1–10 ft scenarios). Not suitable for site-specific engineering decisions.</div>',
            unsafe_allow_html=True,
        )

    # ── TAB 3: Sea Level History ───────────────────────────────────────────────
    with tab3:
        c_sta, c_info = st.columns([2, 1])
        with c_sta:
            station_name = st.selectbox(
                "Select tide gauge station",
                ["— select a station —"] + sorted(TIDE_STATIONS.keys()),
                key="station_06",
            )

        if station_name == "— select a station —":
            st.markdown(
                '<div class="no-data-note" style="padding:24px 0;text-align:center;color:#94a3b8">'
                'Select a tide gauge station above to view its sea level history since 2000 via NOAA CO-OPS.</div>',
                unsafe_allow_html=True,
            )
        else:
            sta_info = TIDE_STATIONS[station_name]
            with st.spinner(f"Fetching tide gauge data for {station_name}…"):
                gauge_data = load_tide_gauge(sta_info["id"])

            if not gauge_data or not gauge_data.get("years"):
                st.warning(f"Could not load NOAA CO-OPS data for {station_name}. Try another station.")
            else:
                slope      = gauge_data["slope_mm_yr"]
                total_rise = gauge_data["total_rise_mm"]
                trend_color = "#dc2626" if slope > 4 else "#0891b2" if slope > 2 else "#16a34a"

                st.markdown(f"""<div class="strip-row" style="margin-bottom:12px">
  <div class="strip-card">
    <div class="strip-icon">📈</div>
    <div class="strip-n" style="color:{trend_color}">{slope:+.1f}</div>
    <div class="strip-l">mm per year (linear trend)</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">🌊</div>
    <div class="strip-n">{total_rise:.0f}</div>
    <div class="strip-l">mm total rise since 2000</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">📅</div>
    <div class="strip-n">{2000 + len(gauge_data['years']) - 1}</div>
    <div class="strip-l">most recent year in record</div>
  </div>
  <div class="strip-card">
    <div class="strip-icon">⚡</div>
    <div class="strip-n">{slope * 80:.0f}</div>
    <div class="strip-l">mm projected rise to 2100 (linear)</div>
  </div>
</div>""", unsafe_allow_html=True)

                tide_fig = make_tide_chart(gauge_data, station_name)
                st.plotly_chart(tide_fig, use_container_width=True)

                if slope > 4:
                    st.markdown(
                        f'<div class="compound-risk">'
                        f'<div class="compound-risk-title">📈 Accelerated sea level rise</div>'
                        f'<div class="compound-risk-body">{station_name} is rising at <strong>{slope:.1f} mm/yr</strong> — '
                        f'significantly above the global mean of ~3.6 mm/yr. This likely reflects both '
                        f'global ocean warming and local land subsidence. At this rate, '
                        f'the station will see ~<strong>{slope * 80:.0f} mm</strong> of additional rise by 2100 '
                        f'under a linear assumption — before accounting for climate scenario acceleration.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div class="method-note">Data: NOAA CO-OPS monthly mean sea level, MSL datum, 2000–2023. '
                    'Annual means computed from monthly records. Rise relative to year-2000 baseline. '
                    'Linear trend via ordinary least squares. Acceleration (IPCC scenario) not included in projection.</div>',
                    unsafe_allow_html=True,
                )

        # Global SLR acceleration callout
        st.markdown("""<div class="flood-callout" style="margin-top:16px">
<strong>The acceleration problem:</strong> global mean sea level rise was ~1.4 mm/yr in the 20th century.
It is now <strong>3.6 mm/yr</strong> and accelerating. IPCC AR6 projects 3.7 mm/yr by 2050 under SSP1-2.6,
rising to <strong>10–12 mm/yr by 2100</strong> under SSP5-8.5 — an order-of-magnitude increase within living memory.
</div>""", unsafe_allow_html=True)

    # ── TAB 4: Compound Risk ───────────────────────────────────────────────────
    with tab4:
        st.markdown("""<div class="narrative-bar" style="margin-top:0">
  <div class="narrative-lede">Coastal flooding and water scarcity are the same crisis from two angles.</div>
  <div class="narrative-context">Saltwater intrusion from rising seas contaminates freshwater aquifers, degrading the drinking
  water and irrigation supplies of nations already under freshwater stress (Day 03). The compound effect is self-reinforcing:
  farmers drill deeper wells, accelerating subsidence, which worsens relative SLR. Bubble size = SLR rate.</div>
</div>""", unsafe_allow_html=True)

        scatter_fig = make_compound_scatter(df, water_stress_raw)
        if scatter_fig.data:
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            st.info("Water stress data unavailable — check network connection.")

        # Dual-crisis countries
        dual_crisis = [
            iso for iso, ws in water_stress_raw.items()
            if ws > 25 and iso in COASTAL_DATA and COASTAL_DATA[iso][0] >= 500
        ]
        if dual_crisis:
            names_dc = [country_names.get(iso, iso) for iso in dual_crisis[:10]]
            st.markdown(
                f'<div class="flood-callout" style="margin-top:8px">'
                f'<strong>Dual coastal + water stress nations</strong> (water withdrawal >25% AND >500K people within 1m): '
                f'{", ".join(names_dc)}{"…" if len(dual_crisis) > 10 else ""}. '
                f'These {len(dual_crisis)} nations face simultaneous saltwater intrusion, freshwater scarcity, '
                f'and coastal displacement — a compound crisis that conventional adaptation strategies cannot address in isolation.</div>',
                unsafe_allow_html=True,
            )

        # Country comparison bar
        c_bar_l, c_bar_r = st.columns(2)
        with c_bar_l:
            slr_scenario_4 = st.select_slider(
                "Scenario for country ranking",
                options=list(SLR_SCENARIOS.keys()),
                value="+1.0m — SSP3-7.0 by 2100",
                key="slr_comp_06",
            )
            slr_m4 = SLR_SCENARIOS[slr_scenario_4]
            city_fig = make_city_risk_chart(df, slr_m4)
            st.plotly_chart(city_fig, use_container_width=True)
        with c_bar_r:
            st.markdown("""<div style="padding:12px 0">
<div style="font-size:11px;font-weight:600;color:var(--text-1);margin-bottom:10px;letter-spacing:-0.01em">
  What this compound risk means in practice
</div>""", unsafe_allow_html=True)
            for title, body in [
                ("Saltwater intrusion", "As seas rise, salt water pushes into coastal aquifers. Bangladesh's coastal wells are already brackish — a creeping freshwater emergency beneath the flooding one."),
                ("Delta agriculture collapse", "The Mekong Delta, Nile Delta, and Ganges-Brahmaputra Delta together feed ~500 million people. At 2m SLR, all three face catastrophic farmland loss."),
                ("Climate migration trigger", "World Bank projects 216M internal climate migrants by 2050 — coastal flooding in BGD, VNM, and PHL is the single largest driver. This feeds into Day 09."),
            ]:
                st.markdown(f"""<div class="flood-callout" style="margin-bottom:8px">
<strong>{title}</strong><br><span style="font-size:11px">{body}</span>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
