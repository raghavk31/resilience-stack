"""
Day 01 — Global Grid Stress Map
The Resilience Stack: 30 Days Building the Intelligence Layer for Humanity

Run:   streamlit run day01_grid_stress.py
Data:  Our World in Data (energy) + World Bank (access, grid loss, regions)
"""

import os, requests, json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from functools import lru_cache

OWID_URL   = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"
CACHE_DIR  = "data"
OWID_FILE  = "data/owid_energy.csv"
WB_FILE    = "data/worldbank_cache.json"

WB_ACCESS  = "EG.ELC.ACCS.ZS"   # % population with electricity
WB_LOSS    = "EG.ELC.LOSS.ZS"   # transmission & distribution losses %

# ── CO₂ lifecycle weights (gCO₂/kWh) ──────────────────────────────────────────
CO2_W = dict(coal=820, oil=650, gas=490, nuclear=12, hydro=24,
             solar=45, wind=11, other_renewables=30)

ESRC = {
    "Coal":"coal_share_elec","Gas":"gas_share_elec","Oil":"oil_share_elec",
    "Nuclear":"nuclear_share_elec","Hydro":"hydro_share_elec",
    "Solar":"solar_share_elec","Wind":"wind_share_elec",
    "Other RES":"other_renewables_share_elec",
}
IS_CLEAN = {"Nuclear","Hydro","Solar","Wind","Other RES"}

ECOLOUR = dict(Coal="#6b7280",Gas="#9ca3af",Oil="#d1d5db",Nuclear="#a78bfa",
               Hydro="#38bdf8",Solar="#fb923c",Wind="#60a5fa",**{"Other RES":"#4ade80"})

BANDS = [
    (70,"CRITICAL","✕","#ef4444","rgba(239,68,68,0.14)","rgba(239,68,68,0.28)"),
    (50,"HIGH",    "△","#f97316","rgba(249,115,22,0.14)","rgba(249,115,22,0.28)"),
    (30,"MODERATE","◯","#eab308","rgba(234,179,8,0.14)", "rgba(234,179,8,0.28)"),
    ( 0,"RESILIENT","✓","#22c55e","rgba(34,197,94,0.14)","rgba(34,197,94,0.28)"),
]
def stress_meta(s):
    for t,lbl,icon,fg,bg,glow in BANDS:
        if s >= t: return lbl,icon,fg,bg,glow
    return "RESILIENT","✓","#22c55e","rgba(34,197,94,0.14)","rgba(34,197,94,0.28)"

YEAR_RANGE = (2000, 2023)

# ── data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_raw() -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not os.path.exists(OWID_FILE):
        r = requests.get(OWID_URL, timeout=60); r.raise_for_status()
        with open(OWID_FILE,"w",encoding="utf-8") as f: f.write(r.text)
    return pd.read_csv(OWID_FILE, low_memory=False)

@st.cache_data(ttl=86400*7)
def load_wb() -> dict:
    """Fetch World Bank access, grid-loss, and region data. Cache to disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(WB_FILE):
        with open(WB_FILE) as f: return json.load(f)
    result = {"access": {}, "loss": {}, "region": {}}
    for ind, key in [(WB_ACCESS,"access"),(WB_LOSS,"loss")]:
        try:
            url = f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&mrv=1&per_page=500"
            r = requests.get(url, timeout=20); r.raise_for_status()
            for row in r.json()[1]:
                iso = row.get("countryiso3code","")
                val = row.get("value")
                if iso and val is not None and len(iso)==3:
                    result[key][iso] = round(float(val), 2)
        except Exception: pass
    try:
        r = requests.get("https://api.worldbank.org/v2/country?format=json&per_page=500",timeout=20)
        r.raise_for_status()
        for row in r.json()[1]:
            iso3 = row.get("id","")
            region = (row.get("region") or {}).get("value","")
            if iso3 and region and region != "Aggregates" and len(iso3)==3:
                result["region"][iso3] = region
    except Exception: pass
    with open(WB_FILE,"w") as f: json.dump(result, f)
    return result

def get_data_for_year(raw: pd.DataFrame, year: int) -> pd.DataFrame:
    """Get one row per country for a specific year, falling back to nearest prior year."""
    c = raw[
        raw["iso_code"].notna()
        & ~raw["iso_code"].str.startswith("OWID", na=False)
        & (raw["iso_code"].str.len()==3)
    ].copy()
    # get exact year, or most recent available up to that year
    before = c[c["year"] <= year]
    return before.sort_values("year", ascending=False).groupby("iso_code", as_index=False).first()

def compute_stress(df: pd.DataFrame, wb: dict) -> pd.DataFrame:
    """
    Stress score (0–100) — three independent components:
      fossil dependency  45%   OWID fossil_share_elec
      access gap         35%   World Bank EG.ELC.ACCS.ZS (inverted)
      grid inefficiency  20%   World Bank EG.ELC.LOSS.ZS (scaled ×2.5, cap 100)
    Weights are adjusted when a component is unavailable.
    """
    df = df.copy()
    df["wb_access"] = df["iso_code"].map(wb.get("access",{}))
    df["wb_loss"]   = df["iso_code"].map(wb.get("loss",  {}))
    df["wb_region"] = df["iso_code"].map(wb.get("region",{}))

    fossil = df["fossil_share_elec"].clip(0,100)
    access_gap = (100 - df["wb_access"].clip(0,100))
    grid_loss  = (df["wb_loss"].clip(0,100) * 2.5).clip(0,100)   # scale: 40% loss → 100

    hf = df["fossil_share_elec"].notna()
    ha = df["wb_access"].notna()
    hl = df["wb_loss"].notna()

    scores = pd.Series(index=df.index, dtype=float)
    # all three
    mask = hf & ha & hl
    scores[mask] = fossil[mask]*0.45 + access_gap[mask]*0.35 + grid_loss[mask]*0.20
    # fossil + access
    mask = hf & ha & ~hl
    scores[mask] = fossil[mask]*0.56 + access_gap[mask]*0.44
    # fossil only
    mask = hf & ~ha & ~hl
    scores[mask] = fossil[mask]
    # access only
    mask = ~hf & ha
    scores[mask] = access_gap[mask]

    df["stress_score"]  = scores.round(1)
    df["stress_fossil"] = fossil.round(1)
    df["stress_access"] = access_gap.round(1)
    df["stress_loss"]   = grid_loss.round(1)
    return df

def compute_projection(raw: pd.DataFrame, country: str) -> tuple[int|None, float|None]:
    """Linear regression on renewables share → year to reach 50% clean. Returns (year, slope)."""
    h = raw[(raw["country"]==country) & raw["renewables_share_elec"].notna()
            & (raw["year"]>=2005)].sort_values("year")
    if len(h) < 5: return None, None
    xs = h["year"].tolist(); ys = h["renewables_share_elec"].tolist()
    n = len(xs)
    xm = sum(xs)/n; ym = sum(ys)/n
    denom = sum((x-xm)**2 for x in xs)
    if denom == 0: return None, None
    slope = sum((xs[i]-xm)*(ys[i]-ym) for i in range(n)) / denom
    intercept = ym - slope*xm
    if slope <= 0: return None, slope
    current_renew = ys[-1]
    if current_renew >= 50: return int(xs[-1]), slope
    years_needed = (50 - current_renew) / slope
    return int(xs[-1] + years_needed), slope

def estimate_co2(row) -> float|None:
    total = 0; weight = 0
    for src, gco2 in CO2_W.items():
        v = row.get(f"{src}_share_elec")
        if pd.notna(v): total += v*gco2; weight += v
    return round(total/100,1) if weight > 10 else None

def renewables_trend_5y(raw: pd.DataFrame, country: str) -> float|None:
    h = raw[(raw["country"]==country)&raw["renewables_share_elec"].notna()].sort_values("year")
    if len(h)<6: return None
    return round(h.iloc[-1]["renewables_share_elec"] - h.iloc[-6]["renewables_share_elec"],1)

# ── chart factories ────────────────────────────────────────────────────────────
def make_map(mapped: pd.DataFrame, selected_iso: str) -> go.Figure:
    fig = px.choropleth(
        mapped, locations="iso_code", color="stress_score", hover_name="country",
        hover_data={"stress_score":":.0f","fossil_share_elec":":.1f",
                    "wb_access":":.1f","renewables_share_elec":":.1f",
                    "year":True,"iso_code":False},
        color_continuous_scale=[
            (0.0,"#1d4ed8"),(0.25,"#7c3aed"),(0.5,"#ea580c"),(0.75,"#dc2626"),(1.0,"#450a0a")
        ],
        range_color=[0,100],
        labels={"stress_score":"Stress","fossil_share_elec":"Fossil %",
                "wb_access":"Electricity Access %","renewables_share_elec":"Renewables %","year":"Year"},
    )
    # highlight selected country with an outline trace
    sel = mapped[mapped["iso_code"]==selected_iso]
    if not sel.empty:
        fig.add_trace(go.Choropleth(
            locations=[selected_iso], z=[1],
            colorscale=[[0,"rgba(255,255,255,0.25)"],[1,"rgba(255,255,255,0.25)"]],
            showscale=False, marker_line_color="#ffffff", marker_line_width=2.5,
            hoverinfo="skip",
        ))
    fig.update_layout(
        height=500, margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor="#05050a",
        coloraxis_colorbar=dict(
            title=dict(text="Stress",font=dict(color="#64748b",size=10)),
            tickvals=[0,25,50,75,100],
            ticktext=["✓ Resilient","Low","Moderate","High","✕ Critical"],
            tickfont=dict(color="#64748b",size=9),len=0.5,thickness=10,
        ),
        geo=dict(showframe=False,showcoastlines=True,coastlinecolor="#1e1e2e",
                 projection_type="natural earth",bgcolor="#05050a",
                 showland=True,landcolor="#0d0d14",showocean=True,oceancolor="#080c14",
                 showcountries=True,countrycolor="#1a1a2a"),
    )
    return fig

def make_gauge(score, fg):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"font":{"size":56,"color":fg,"family":"Inter"}},
        gauge=dict(
            axis=dict(range=[0,100],tickwidth=0,ticks="",showticklabels=False),
            bar=dict(color=fg,thickness=0.28),
            bgcolor="#0d0d18", borderwidth=0,
            steps=[
                {"range":[0,30],  "color":"rgba(29,78,216,0.1)"},
                {"range":[30,50], "color":"rgba(234,179,8,0.08)"},
                {"range":[50,70], "color":"rgba(234,88,12,0.08)"},
                {"range":[70,100],"color":"rgba(220,38,38,0.08)"},
            ],
            threshold=dict(line=dict(color=fg,width=4),thickness=0.85,value=score),
        ),
    ))
    fig.update_layout(height=190,margin=dict(l=20,r=20,t=0,b=0),
                      paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#f1f5f9",family="Inter"))
    return fig

def make_donut(row, fg):
    data = [(k,row.get(v,0)) for k,v in ESRC.items()
            if pd.notna(row.get(v)) and row.get(v,0)>0.5]
    if not data: return None
    labels,values = zip(*data)
    fossil_t = sum(v for l,v in data if l not in IS_CLEAN)
    fig = go.Figure(go.Pie(
        labels=list(labels),values=list(values),hole=0.72,
        marker_colors=[ECOLOUR.get(l,"#6b7280") for l in labels],
        textinfo="label+percent",textfont=dict(size=10,color="#94a3b8"),
        insidetextorientation="radial",
        hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",sort=False,
    ))
    centre_col = fg if fossil_t>50 else "#22c55e"
    fig.add_annotation(text=f"<b>{fossil_t:.0f}%</b><br><span style='font-size:10px'>fossil</span>",
                       x=0.5,y=0.5,showarrow=False,
                       font=dict(size=18,color=centre_col,family="Inter"),align="center")
    fig.update_layout(height=260,margin=dict(l=0,r=0,t=0,b=0),
                      paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
                      font=dict(color="#f1f5f9",family="Inter"))
    return fig

def make_trend(raw, country):
    h = raw[(raw["country"]==country)&(raw["year"]>=2000)][
        ["year","renewables_share_elec","fossil_share_elec"]
    ].dropna(how="all",subset=["renewables_share_elec","fossil_share_elec"])
    if len(h)<4: return None
    fig = go.Figure()
    for col,name,c,fill in [
        ("fossil_share_elec","Fossil","#f97316","rgba(249,115,22,0.07)"),
        ("renewables_share_elec","Renewables","#22c55e","rgba(34,197,94,0.07)"),
    ]:
        s = h[h[col].notna()]
        if len(s)>3:
            fig.add_trace(go.Scatter(x=s["year"],y=s[col],name=name,
                line=dict(color=c,width=2.5),fill="tozeroy",fillcolor=fill,
                hovertemplate=f"%{{y:.1f}}%<extra>{name}</extra>"))
    fig.update_layout(
        height=220,margin=dict(l=0,r=0,t=8,b=0),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False,color="#334155",tickfont=dict(size=10)),
        yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",
                   color="#334155",tickfont=dict(size=10),ticksuffix="%"),
        legend=dict(font=dict(color="#64748b",size=10),bgcolor="rgba(0,0,0,0)",
                    orientation="h",y=1.12),
        hovermode="x unified",
    )
    return fig

def make_compare_chart(r1, r2, c1, c2, mapped):
    metrics = ["stress_score","fossil_share_elec","renewables_share_elec","wb_access"]
    labels  = ["Grid Stress","Fossil %","Renewables %","Access %"]
    vals1   = [r1.get(m,0) or 0 for m in metrics]
    vals2   = [r2.get(m,0) or 0 for m in metrics]
    fig = go.Figure()
    fig.add_trace(go.Bar(name=c1,x=labels,y=vals1,marker_color="#60a5fa",
                         text=[f"{v:.0f}" for v in vals1],textposition="outside",
                         textfont=dict(color="#94a3b8",size=10)))
    fig.add_trace(go.Bar(name=c2,x=labels,y=vals2,marker_color="#f97316",
                         text=[f"{v:.0f}" for v in vals2],textposition="outside",
                         textfont=dict(color="#94a3b8",size=10)))
    fig.update_layout(
        height=280,barmode="group",margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False,color="#334155",tickfont=dict(size=11)),
        yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",
                   color="#334155",tickfont=dict(size=10),ticksuffix="%"),
        legend=dict(font=dict(color="#94a3b8",size=11),bgcolor="rgba(0,0,0,0)"),
    )
    return fig

# ── html helpers ───────────────────────────────────────────────────────────────
def source_bars(row) -> str:
    items = [(k,row.get(v,0),k in IS_CLEAN) for k,v in ESRC.items()
             if pd.notna(row.get(v)) and row.get(v,0)>0.5]
    items.sort(key=lambda x:-x[1])
    out = ""
    for name,pct,clean in items:
        col  = ECOLOUR.get(name,"#6b7280")
        icon = "✦" if clean else "◆"
        lc   = "#4ade80" if clean else "#94a3b8"
        out += f"""
<div style='margin:6px 0'>
  <div style='display:flex;justify-content:space-between;margin-bottom:3px;font-size:0.78rem'>
    <span style='color:{lc}'>{icon} {name}</span>
    <span style='color:#f1f5f9;font-weight:600'>{pct:.1f}%</span>
  </div>
  <div style='background:rgba(255,255,255,0.06);border-radius:999px;height:7px;overflow:hidden'>
    <div style='width:{min(pct,100):.1f}%;height:100%;background:{col};border-radius:999px'></div>
  </div>
</div>"""
    return out

def chips(items: list) -> str:
    """items = [(label, value, sub), ...]"""
    inner = "".join(f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:14px;padding:12px 16px;flex:1;min-width:100px'>
  <div style='color:#475569;font-size:0.65rem;text-transform:uppercase;
              letter-spacing:0.1em;font-weight:600'>{l}</div>
  <div style='color:#f1f5f9;font-size:1.25rem;font-weight:700;margin-top:2px'>{v}</div>
  <div style='color:#334155;font-size:0.68rem;margin-top:2px'>{s}</div>
</div>""" for l,v,s in items)
    return f"<div style='display:flex;gap:10px;flex-wrap:wrap;margin:12px 0'>{inner}</div>"

def score_formula(fossil, access_gap, loss, hf, ha, hl) -> str:
    rows = ""
    if hf: rows += f"<tr><td style='color:#94a3b8'>Fossil dependency</td><td style='color:#f97316;font-weight:700'>{fossil:.1f}</td><td style='color:#475569'>× 0.45</td></tr>"
    if ha: rows += f"<tr><td style='color:#94a3b8'>Access gap (100 − access%)</td><td style='color:#f97316;font-weight:700'>{access_gap:.1f}</td><td style='color:#475569'>× 0.35</td></tr>"
    if hl: rows += f"<tr><td style='color:#94a3b8'>Grid loss (scaled)</td><td style='color:#f97316;font-weight:700'>{loss:.1f}</td><td style='color:#475569'>× 0.20</td></tr>"
    return f"""
<div style='background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);
            border-radius:12px;padding:16px;font-size:0.82rem'>
  <div style='color:#64748b;margin-bottom:10px;font-size:0.72rem;text-transform:uppercase;
              letter-spacing:0.1em;font-weight:600'>How this score is calculated</div>
  <table style='width:100%;border-collapse:collapse'>
    <tr style='border-bottom:1px solid rgba(255,255,255,0.05)'>
      <th style='color:#475569;font-weight:500;text-align:left;padding:4px 0;font-size:0.72rem'>Component</th>
      <th style='color:#475569;font-weight:500;text-align:left;padding:4px 0;font-size:0.72rem'>Value</th>
      <th style='color:#475569;font-weight:500;text-align:left;padding:4px 0;font-size:0.72rem'>Weight</th>
    </tr>
    {rows}
  </table>
  <div style='margin-top:8px;color:#475569;font-size:0.7rem'>
    ✦ Clean sources (nuclear, hydro, solar, wind) reduce fossil dependency component.
  </div>
</div>"""

# ══ CSS ════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,*::before,*::after{box-sizing:border-box}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="block-container"]{
  background:#05050a!important;font-family:'Inter',system-ui,sans-serif!important;color:#e2e8f0!important}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"]{background:#080810!important}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer{display:none!important}

[data-testid="metric-container"]{
  background:rgba(255,255,255,0.03)!important;backdrop-filter:blur(16px)!important;
  border:1px solid rgba(255,255,255,0.07)!important;border-radius:18px!important;
  padding:20px 22px!important;transition:border-color .2s,box-shadow .2s}
[data-testid="metric-container"]:hover{border-color:rgba(255,255,255,0.13)!important;
  box-shadow:0 4px 24px rgba(0,0,0,0.35)!important}
[data-testid="stMetricLabel"]>div{color:#64748b!important;font-size:.72rem!important;
  letter-spacing:.1em;text-transform:uppercase;font-weight:600}
[data-testid="stMetricValue"]>div{color:#f1f5f9!important;font-size:1.75rem!important;font-weight:800}

[data-testid="stTabs"] [data-baseweb="tab-list"]{
  background:rgba(255,255,255,0.025)!important;border-radius:12px!important;
  padding:4px!important;gap:2px!important;border:1px solid rgba(255,255,255,0.05)!important}
[data-testid="stTabs"] [data-baseweb="tab"]{
  background:transparent!important;border-radius:9px!important;color:#475569!important;
  font-size:.82rem!important;font-weight:600;padding:8px 16px!important;transition:all .2s!important}
[data-testid="stTabs"] [aria-selected="true"]{
  background:rgba(255,255,255,0.07)!important;color:#f1f5f9!important}

[data-testid="stSelectbox"]>div>div{
  background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.08)!important;
  border-radius:12px!important;color:#e2e8f0!important}
[data-testid="stSlider"]>div>div>div{background:rgba(255,255,255,0.06)!important}
.stCaption{color:#334155!important}
hr{border-color:rgba(255,255,255,0.05)!important;margin:24px 0!important}

.glass{background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.07);
  border-radius:24px;padding:24px 28px;transition:border-color .25s,box-shadow .25s}
.glass:hover{border-color:rgba(255,255,255,0.11);box-shadow:0 8px 40px rgba(0,0,0,0.4)}
.glass-sm{background:rgba(255,255,255,0.025);backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,0.06);border-radius:18px;padding:18px 22px}
.fade-in{animation:fadeIn .35s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.gradient-text{background:linear-gradient(135deg,#f1f5f9 0%,#94a3b8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 13px;
  border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.pill{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;
  border-radius:999px;font-size:.72rem;font-weight:600}
</style>
"""

# ══ MAIN ═══════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Grid Stress · Day 01",page_icon="⚡",
                       layout="wide",initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)

    # ── load data
    with st.spinner("Loading energy data…"):
        raw = load_raw()
        wb  = load_wb()

    # ── URL state
    params = st.query_params
    if "iso" not in st.session_state:
        st.session_state.iso = params.get("iso","IND")
    if "iso2" not in st.session_state:
        st.session_state.iso2 = ""

    # ── year slider (above everything)
    st.markdown("""
<div style='padding:32px 0 16px'>
  <div style='font-size:.72rem;color:#475569;letter-spacing:.15em;text-transform:uppercase;
              font-weight:600;margin-bottom:6px'>Day 01 · The Resilience Stack</div>
  <h1 class='gradient-text' style='font-size:2.6rem;font-weight:900;margin:0;line-height:1.1'>
    Global Grid Stress Map
  </h1>
  <p style='color:#475569;margin:8px 0 0;font-size:.95rem;max-width:520px'>
    The grid is the nervous system of civilisation.
    Click any country. Scrub through time. See what's changing.
  </p>
</div>
""", unsafe_allow_html=True)

    year = st.slider("", YEAR_RANGE[0], YEAR_RANGE[1], YEAR_RANGE[1],
                     format="%d", label_visibility="collapsed",
                     help="Scrub to see how grid stress changed over time")

    # ── compute for selected year
    df     = get_data_for_year(raw, year)
    df     = compute_stress(df, wb)
    mapped = df.dropna(subset=["stress_score"]).copy()

    # sync URL
    st.query_params["iso"]  = st.session_state.iso
    st.query_params["year"] = str(year)

    # ── summary strip
    n_crit = int((mapped["stress_score"]>=70).sum())
    n_high = int(((mapped["stress_score"]>=50)&(mapped["stress_score"]<70)).sum())
    n_mod  = int(((mapped["stress_score"]>=30)&(mapped["stress_score"]<50)).sum())
    n_res  = int((mapped["stress_score"]<30).sum())
    avg    = mapped["stress_score"].mean()
    n_wb   = int(mapped["wb_access"].notna().sum())

    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("✕  Critical",  n_crit)
    m2.metric("△  High",      n_high)
    m3.metric("◯  Moderate",  n_mod)
    m4.metric("✓  Resilient", n_res)
    m5.metric("Avg score",    f"{avg:.0f}/100")
    m6.metric("Access data",  f"{n_wb} countries", help="Countries with World Bank electricity access data")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ══ map + spotlight ════════════════════════════════════════════════════════
    map_col, detail_col = st.columns([2.6,1.1], gap="large")

    with map_col:
        st.markdown("<div class='glass' style='padding:14px'>", unsafe_allow_html=True)
        event = st.plotly_chart(make_map(mapped, st.session_state.iso),
                                use_container_width=True, on_select="rerun", key="wmap")
        if event and event.selection and event.selection.get("points"):
            iso = event.selection["points"][0].get("location")
            if iso and iso in mapped["iso_code"].values:
                st.session_state.iso = iso
                st.session_state.iso2 = ""
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(
            f"Score = fossil dependency (45%) + access gap (35%) + grid loss (20%)  ·  "
            f"Sources: Our World in Data + World Bank  ·  Year: {year}"
        )

    with detail_col:
        iso  = st.session_state.iso
        rows = mapped[mapped["iso_code"]==iso]
        if rows.empty:
            st.info("Click any country on the map.")
        else:
            row     = rows.iloc[0]
            score   = row["stress_score"]
            lbl,icon,fg,bg,glow = stress_meta(score)
            country = row["country"]
            yr      = int(row["year"]) if pd.notna(row.get("year")) else "—"
            trend5  = renewables_trend_5y(raw, country)
            co2     = estimate_co2(row)
            proj50, slope = compute_projection(raw, country)

            # trend pill
            trend_html = ""
            if trend5 is not None:
                arr = "↑" if trend5>0 else "↓"
                tc  = "#22c55e" if trend5>0 else "#ef4444"
                tbg = "rgba(34,197,94,0.12)" if trend5>0 else "rgba(239,68,68,0.12)"
                trend_html = f"<span class='pill' style='background:{tbg};color:{tc}'>{arr} {abs(trend5):.1f}pp/5yr</span>"

            # projection pill
            proj_html = ""
            if proj50:
                if proj50 <= year:
                    proj_html = "<span class='pill' style='background:rgba(34,197,94,0.12);color:#22c55e'>✓ 50% clean</span>"
                else:
                    dist = proj50 - year
                    proj_html = f"<span class='pill' style='background:rgba(96,165,250,0.12);color:#60a5fa'>50% clean ~{proj50}</span>"

            st.markdown(f"""
<div class='glass fade-in' style='box-shadow:0 0 48px {glow}'>
  <div style='font-size:1.55rem;font-weight:800;color:#f1f5f9;margin-bottom:8px'>{country}</div>
  <div style='display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px'>
    <span class='badge' style='background:{bg};color:{fg};border:1px solid {fg}50'>
      {icon} {lbl}
    </span>
    {trend_html} {proj_html}
  </div>
  <div style='color:#334155;font-size:.72rem;margin-top:4px'>data year: {yr}</div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown("<div class='glass-sm'>", unsafe_allow_html=True)
            st.plotly_chart(make_gauge(score,fg), use_container_width=True, key="gauge")

            chip_data = [("Fossil", f"{row.get('fossil_share_elec',0):.0f}%"
                          if pd.notna(row.get('fossil_share_elec')) else "—", "of electricity")]
            if pd.notna(row.get("wb_access")):
                chip_data.append(("Access", f"{row['wb_access']:.0f}%","have electricity"))
            if co2:
                chip_data.append(("CO₂ est.", f"{co2:.0f}","gCO₂/kWh"))
            if pd.notna(row.get("renewables_share_elec")):
                chip_data.append(("Renewables", f"{row['renewables_share_elec']:.0f}%","of electricity"))
            st.markdown(chips(chip_data), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # score formula expander
            with st.expander("How is this score calculated?"):
                st.markdown(score_formula(
                    row.get("stress_fossil",0) or 0,
                    row.get("stress_access",50),
                    row.get("stress_loss",0) or 0,
                    pd.notna(row.get("fossil_share_elec")),
                    pd.notna(row.get("wb_access")),
                    pd.notna(row.get("wb_loss")),
                ), unsafe_allow_html=True)

    # ══ deep-dive tabs ═════════════════════════════════════════════════════════
    iso  = st.session_state.iso
    rows = mapped[mapped["iso_code"]==iso]
    if not rows.empty:
        row     = rows.iloc[0]
        score   = row["stress_score"]
        lbl,icon,fg,bg,glow = stress_meta(score)
        country = row["country"]

        st.markdown(f"""
<div style='margin:24px 0 10px;display:flex;align-items:center;gap:10px'>
  <span style='color:#334155;font-size:.72rem;text-transform:uppercase;
               letter-spacing:.12em;font-weight:600'>Exploring</span>
  <span style='color:#f1f5f9;font-size:1.05rem;font-weight:700'>{country}</span>
</div>""", unsafe_allow_html=True)

        t1,t2,t3,t4 = st.tabs([
            "⚡ Where the energy comes from",
            "📈 Is it improving?",
            "🌍 How it compares",
            "⚖️ Compare countries",
        ])

        # ── Tab 1: energy mix
        with t1:
            c1,c2 = st.columns([1.1,1],gap="large")
            with c1:
                st.markdown("<div class='glass'>", unsafe_allow_html=True)
                st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:14px;"
                            "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                            "Source breakdown</p>",unsafe_allow_html=True)
                st.markdown(source_bars(row), unsafe_allow_html=True)

                fossil_t = sum(row.get(v,0) or 0 for k,v in ESRC.items() if k not in IS_CLEAN and pd.notna(row.get(v)))
                clean_t  = 100-fossil_t
                gap50    = max(0,50-clean_t)
                gap_col  = "#22c55e" if gap50==0 else fg
                st.markdown(f"""
<div style='margin-top:16px;padding:12px 14px;background:rgba(255,255,255,0.025);
            border-radius:12px;display:flex;justify-content:space-between;align-items:center'>
  <span style='color:#64748b;font-size:.8rem'>Gap to 50% clean</span>
  <span style='color:{gap_col};font-weight:700;font-size:1.1rem'>
    {"Already there ✓" if gap50==0 else f"+{gap50:.0f}pp needed"}
  </span>
</div>""",unsafe_allow_html=True)
                st.markdown("</div>",unsafe_allow_html=True)
            with c2:
                donut = make_donut(row,fg)
                if donut:
                    st.markdown("<div class='glass'>",unsafe_allow_html=True)
                    st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                                "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                                "Mix overview</p>",unsafe_allow_html=True)
                    st.plotly_chart(donut,use_container_width=True,key="donut")
                    if co2:
                        st.markdown(f"""
<div style='padding:10px 14px;background:rgba(255,255,255,0.025);border-radius:10px;margin-top:4px;
            display:flex;justify-content:space-between'>
  <span style='color:#64748b;font-size:.8rem'>Est. CO₂ intensity</span>
  <span style='color:#94a3b8;font-weight:600'>{co2:.0f} gCO₂/kWh <span style='color:#334155;font-weight:400'>(lifecycle)</span></span>
</div>""",unsafe_allow_html=True)
                    st.markdown("</div>",unsafe_allow_html=True)

        # ── Tab 2: trend + projection
        with t2:
            st.markdown("<div class='glass'>",unsafe_allow_html=True)
            trend_fig = make_trend(raw,country)
            if trend_fig:
                st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                            "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                            "Fossil vs renewables — since 2000</p>",unsafe_allow_html=True)
                st.plotly_chart(trend_fig,use_container_width=True,key="trend")

            # projection card
            proj50, slope = compute_projection(raw,country)
            cur_renew = row.get("renewables_share_elec",0) or 0
            if slope is not None:
                if slope > 0:
                    pace = f"+{slope:.2f}pp/year"
                    if proj50 and proj50 <= YEAR_RANGE[1]:
                        msg = f"<b style='color:#22c55e'>Already past 50% clean</b> — at {cur_renew:.0f}% renewables"
                    elif proj50:
                        msg = f"At current pace reaches 50% clean around <b style='color:#60a5fa'>{proj50}</b>"
                    else:
                        msg = f"Improving at {slope:.2f}pp/year"
                else:
                    pace = f"{slope:.2f}pp/year"
                    msg  = f"<b style='color:#ef4444'>Renewables share declining</b> — {slope:.2f}pp/year"
                st.markdown(f"""
<div style='margin-top:12px;padding:14px 18px;background:rgba(255,255,255,0.025);
            border-radius:12px;display:flex;justify-content:space-between;align-items:center'>
  <span style='color:#94a3b8;font-size:.85rem'>{msg}</span>
  <span style='color:#475569;font-size:.78rem;font-weight:600'>{pace}</span>
</div>""",unsafe_allow_html=True)
            else:
                st.caption("Not enough data for projection.")
            st.markdown("</div>",unsafe_allow_html=True)

        # ── Tab 3: comparison vs world + region
        with t3:
            region = row.get("wb_region","") or "Unknown"
            region_df = mapped[mapped["wb_region"]==region] if region != "Unknown" else pd.DataFrame()

            col_a,col_b = st.columns(2,gap="large")
            compare_metrics = [
                ("Stress score",       "stress_score",           "100=most stressed"),
                ("Fossil share",       "fossil_share_elec",      "% of electricity"),
                ("Renewables share",   "renewables_share_elec",  "% of electricity"),
                ("Electricity access", "wb_access",              "% of population"),
            ]
            with col_a:
                st.markdown("<div class='glass'>",unsafe_allow_html=True)
                st.markdown(f"<p style='color:#64748b;font-size:.75rem;margin-bottom:14px;"
                            f"text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                            f"{country} vs world median</p>",unsafe_allow_html=True)
                for label,col_name,sub in compare_metrics:
                    val     = row.get(col_name)
                    w_med   = mapped[col_name].median() if col_name in mapped else None
                    if pd.isna(val) or w_med is None: continue
                    diff    = val-w_med
                    higher_bad = col_name not in ("renewables_share_elec","wb_access")
                    bad  = (diff>0)==higher_bad
                    dc   = "#ef4444" if bad else "#22c55e"
                    sign = "+" if diff>0 else ""
                    st.markdown(f"""
<div style='display:flex;justify-content:space-between;align-items:center;
            padding:9px 12px;background:rgba(255,255,255,0.025);border-radius:10px;margin-bottom:7px'>
  <div>
    <div style='color:#94a3b8;font-size:.82rem'>{label}</div>
    <div style='color:#475569;font-size:.68rem'>{sub}</div>
  </div>
  <div style='text-align:right'>
    <div style='color:#f1f5f9;font-weight:700'>{val:.1f}</div>
    <div style='color:{dc};font-size:.75rem;font-weight:600'>{sign}{diff:.1f} vs world</div>
  </div>
</div>""",unsafe_allow_html=True)
                st.markdown("</div>",unsafe_allow_html=True)

            with col_b:
                st.markdown("<div class='glass'>",unsafe_allow_html=True)
                st.markdown(f"<p style='color:#64748b;font-size:.75rem;margin-bottom:14px;"
                            f"text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                            f"{country} vs {region} median</p>",unsafe_allow_html=True)
                if not region_df.empty:
                    for label,col_name,sub in compare_metrics:
                        val    = row.get(col_name)
                        r_med  = region_df[col_name].median() if col_name in region_df else None
                        if pd.isna(val) or r_med is None or pd.isna(r_med): continue
                        diff   = val-r_med
                        higher_bad = col_name not in ("renewables_share_elec","wb_access")
                        bad  = (diff>0)==higher_bad
                        dc   = "#ef4444" if bad else "#22c55e"
                        sign = "+" if diff>0 else ""
                        st.markdown(f"""
<div style='display:flex;justify-content:space-between;align-items:center;
            padding:9px 12px;background:rgba(255,255,255,0.025);border-radius:10px;margin-bottom:7px'>
  <div>
    <div style='color:#94a3b8;font-size:.82rem'>{label}</div>
    <div style='color:#475569;font-size:.68rem'>{sub}</div>
  </div>
  <div style='text-align:right'>
    <div style='color:#f1f5f9;font-weight:700'>{val:.1f}</div>
    <div style='color:{dc};font-size:.75rem;font-weight:600'>{sign}{diff:.1f} vs region</div>
  </div>
</div>""",unsafe_allow_html=True)
                else:
                    st.caption("Region data unavailable.")
                st.markdown("</div>",unsafe_allow_html=True)

        # ── Tab 4: compare two countries
        with t4:
            c_list  = sorted(mapped["country"].dropna().unique().tolist())
            cur_name= mapped[mapped["iso_code"]==iso]["country"].values[0]
            col1,col2 = st.columns([1,1])
            with col1:
                st.markdown(f"<div style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                            f"text-transform:uppercase;letter-spacing:.08em;font-weight:600'>"
                            f"Country A</div>",unsafe_allow_html=True)
                st.markdown(f"<div class='glass-sm' style='padding:12px 16px;margin-bottom:4px'>"
                            f"<span style='color:#f1f5f9;font-weight:700'>{cur_name}</span>"
                            f"</div>",unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='color:#64748b;font-size:.75rem;margin-bottom:4px;"
                            f"text-transform:uppercase;letter-spacing:.08em;font-weight:600'>"
                            f"Country B</div>",unsafe_allow_html=True)
                default_b = "DEU" if iso != "DEU" else "CHN"
                cur_b = mapped[mapped["iso_code"]==st.session_state.iso2] if st.session_state.iso2 else pd.DataFrame()
                b_default_name = cur_b["country"].values[0] if not cur_b.empty else mapped[mapped["iso_code"]==default_b]["country"].values[0] if default_b in mapped["iso_code"].values else c_list[0]
                chosen_b = st.selectbox("",c_list,index=c_list.index(b_default_name),
                                        label_visibility="collapsed",key="compare_b")
                if chosen_b:
                    m = mapped[mapped["country"]==chosen_b]["iso_code"].values
                    if len(m): st.session_state.iso2 = m[0]

            if st.session_state.iso2 and st.session_state.iso2 in mapped["iso_code"].values:
                row_b   = mapped[mapped["iso_code"]==st.session_state.iso2].iloc[0]
                score_b = row_b["stress_score"]
                lbl_b,icon_b,fg_b,bg_b,_ = stress_meta(score_b)
                name_b  = row_b["country"]

                # two gauges
                g1,g2 = st.columns(2)
                with g1:
                    st.markdown(f"<div class='glass-sm'>",unsafe_allow_html=True)
                    st.markdown(f"<p style='text-align:center;color:{fg};font-weight:700;"
                                f"font-size:.9rem;margin-bottom:0'>{cur_name}</p>",unsafe_allow_html=True)
                    st.plotly_chart(make_gauge(score,fg),use_container_width=True,key="g_a")
                    st.markdown(f"<div style='text-align:center'><span class='badge' style='background:{bg};color:{fg};border:1px solid {fg}50'>{icon} {lbl}</span></div>",unsafe_allow_html=True)
                    st.markdown("</div>",unsafe_allow_html=True)
                with g2:
                    st.markdown(f"<div class='glass-sm'>",unsafe_allow_html=True)
                    st.markdown(f"<p style='text-align:center;color:{fg_b};font-weight:700;"
                                f"font-size:.9rem;margin-bottom:0'>{name_b}</p>",unsafe_allow_html=True)
                    st.plotly_chart(make_gauge(score_b,fg_b),use_container_width=True,key="g_b")
                    st.markdown(f"<div style='text-align:center'><span class='badge' style='background:{bg_b};color:{fg_b};border:1px solid {fg_b}50'>{icon_b} {lbl_b}</span></div>",unsafe_allow_html=True)
                    st.markdown("</div>",unsafe_allow_html=True)

                st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)
                st.markdown("<div class='glass'>",unsafe_allow_html=True)
                st.plotly_chart(make_compare_chart(row,row_b,cur_name,name_b,mapped),
                                use_container_width=True,key="cmp")
                st.markdown("</div>",unsafe_allow_html=True)

    # ══ bottom ════════════════════════════════════════════════════════════════
    st.divider()
    bl,br = st.columns([1,2],gap="large")
    with bl:
        st.markdown("<div class='glass'>",unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:10px;"
                    "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                    "Search any country</p>",unsafe_allow_html=True)
        c_list   = sorted(mapped["country"].dropna().unique().tolist())
        cur_rows = mapped[mapped["iso_code"]==st.session_state.iso]
        cur_name = cur_rows["country"].values[0] if not cur_rows.empty else c_list[0]
        chosen   = st.selectbox("",c_list,index=c_list.index(cur_name),
                                label_visibility="collapsed",key="search_box")
        if chosen and chosen!=cur_name:
            m = mapped[mapped["country"]==chosen]["iso_code"].values
            if len(m): st.session_state.iso=m[0]; st.rerun()
        st.markdown("</div>",unsafe_allow_html=True)

    with br:
        st.markdown("<p style='color:#64748b;font-size:.75rem;margin-bottom:10px;"
                    "text-transform:uppercase;letter-spacing:.1em;font-weight:600'>"
                    f"20 most stressed grids — {year}</p>",unsafe_allow_html=True)
        top20 = (
            mapped.nlargest(20,"stress_score")
            [["country","stress_score","fossil_share_elec","wb_access","renewables_share_elec","wb_region"]]
            .rename(columns={"country":"Country","stress_score":"Stress",
                             "fossil_share_elec":"Fossil %","wb_access":"Access %",
                             "renewables_share_elec":"Renewables %","wb_region":"Region"})
            .reset_index(drop=True)
        )
        top20.index += 1
        st.dataframe(top20, use_container_width=True, height=290,
            column_config={
                "Stress":      st.column_config.ProgressColumn("Stress",min_value=0,max_value=100,format="%.0f"),
                "Fossil %":    st.column_config.NumberColumn(format="%.1f%%"),
                "Access %":    st.column_config.NumberColumn(format="%.1f%%"),
                "Renewables %":st.column_config.NumberColumn(format="%.1f%%"),
            })

    # ══ closing ═══════════════════════════════════════════════════════════════
    st.markdown("""
<div class='glass' style='margin-top:8px;border-color:rgba(255,255,255,0.04)'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px'>
    <div style='flex:2;min-width:260px'>
      <p style='color:#475569;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
                font-weight:600;margin:0 0 8px'>What this map is really saying</p>
      <p style='color:#94a3b8;margin:0;line-height:1.7;font-size:.9rem'>
        A country in the red isn't just paying more for electricity.
        Its water pumps stop when the grid fails.
        Its food rots when cold chains break.
        Its hospitals run on fuel that can be cut off.
        <strong style='color:#64748b'>Grid fragility is the root of every other fragility.</strong>
      </p>
    </div>
    <div style='flex:1;min-width:200px;padding:16px 20px;background:rgba(255,255,255,0.025);
                border-radius:16px;border:1px solid rgba(255,255,255,0.06)'>
      <div style='color:#334155;font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600'>Next</div>
      <div style='color:#f1f5f9;font-weight:700;font-size:1rem;margin:6px 0 4px'>Day 02 →</div>
      <div style='color:#64748b;font-size:.82rem'>Solar Potential Atlas — for any point on earth, how much sun and what it could replace.</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
