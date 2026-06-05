"""
The Resilience Stack — Day 12
Emergency Preparedness Generator — Illustrated Edition
"""

import json
import os
import pathlib

import requests
import streamlit as st

st.set_page_config(
    page_title="Emergency Prep Generator · Day 12",
    page_icon="🛡️",
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

RISK_OPTIONS = [
    "Flooding / flash floods", "Wildfire", "Extreme heat",
    "Hurricane / cyclone / typhoon", "Earthquake",
    "Winter storm / blizzard", "Tornado", "Drought / water shortage",
    "Power grid failure", "Coastal storm surge",
]
SPECIAL_OPTIONS = [
    "Pets", "Infants or young children", "Elderly household members",
    "Medical equipment (CPAP, oxygen, dialysis, etc.)", "Mobility limitations",
    "Dietary restrictions / food allergies", "Non-English speaking household",
]

C = {
    "kit":    "#f97316",
    "water":  "#0ea5e9",
    "food":   "#16a34a",
    "comms":  "#8b5cf6",
    "evac":   "#ef4444",
    "budget": "#6366f1",
    "action": "#14b8a6",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

*, html, body { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }

.stApp {
  background:
    radial-gradient(ellipse at 10% 20%, rgba(239,68,68,.06) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 80%, rgba(99,102,241,.07) 0%, transparent 50%),
    radial-gradient(ellipse at 55% 5%,  rgba(249,115,22,.05) 0%, transparent 45%),
    #f7f8fa !important;
}
[data-testid="block-container"] { padding:0 !important; max-width:100% !important; background:transparent !important; }
section[data-testid="stSidebar"] { display:none !important; }
[data-testid="stAppViewContainer"], section.main { background:transparent !important; }

.ep-header {
  background: rgba(255,255,255,.95);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0,0,0,.07);
  padding: 14px 28px 10px;
}
.ep-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #b0b8c8;
  display: flex; align-items: center; gap: 8px;
}
.ep-dot { width:8px; height:8px; border-radius:50%; border:2px solid #c0c8d4; display:inline-block; }

[data-testid="stHorizontalBlock"]:has(.ep-left) { gap:0 !important; align-items:stretch !important; }
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.90) !important;
  backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid rgba(0,0,0,.08) !important;
  min-height: calc(100vh - 60px);
}
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:last-child {
  background: transparent !important;
  padding: 24px 32px 40px !important;
}
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:first-child
  [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:first-child
  [data-testid="stRadio"],
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:first-child
  [data-testid="stMultiSelect"],
[data-testid="stHorizontalBlock"]:has(.ep-left) > [data-testid="stColumn"]:first-child
  [data-testid="stNumberInput"] {
  padding-left: 20px !important; padding-right: 20px !important;
}

.ep-left { height:0; margin:0; padding:0; display:block; }
.ep-pad  { padding:18px 22px 12px; }
.ep-title { font-size:1.18rem; font-weight:800; color:#0f172a; line-height:1.25; margin:0 0 .3rem; letter-spacing:-.2px; font-family:'Space Grotesk',sans-serif; }
.ep-desc  { font-size:.76rem; color:#94a3b8; line-height:1.6; margin:0; }
.ep-sep   { border:none; border-top:1px solid rgba(0,0,0,.07); margin:10px 0; }
.ep-lbl   { font-size:.62rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:#94a3b8; margin-bottom:7px; margin-top:2px; }

section.main label, section.main [data-testid="stWidgetLabel"] p { font-size:.75rem !important; font-weight:600 !important; color:#374151 !important; }
section.main [data-testid="stRadio"] > label { font-size:.74rem !important; font-weight:600 !important; color:#374151 !important; margin-bottom:4px !important; }
section.main [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { font-size:.74rem !important; color:#555 !important; }
section.main [data-testid="stTextInput"] input { font-size:.8rem !important; border-radius:8px !important; }
section.main [data-testid="stNumberInput"] input { font-size:.8rem !important; border-radius:8px !important; }
section.main [data-testid="stButton"] > button {
  border-radius:8px !important; font-size:.74rem !important; font-weight:600 !important;
  border:1px solid rgba(0,0,0,.1) !important; background:rgba(255,255,255,.8) !important;
  backdrop-filter:blur(8px) !important; transition:all .15s !important; padding:6px 14px !important;
}
section.main [data-testid="stButton"] > button:hover { background:rgba(255,255,255,.97) !important; border-color:rgba(0,0,0,.18) !important; }
section.main [data-testid="stButton"] > button[kind="primary"] { background:#0f172a !important; color:#fff !important; border-color:#0f172a !important; }
section.main [data-testid="stButton"] > button[kind="primary"]:hover { background:#1e293b !important; }
section.main [data-testid="stButton"] > button:disabled { opacity:.4 !important; cursor:not-allowed !important; }

/* ── Plan card shell ── */
.ps-card {
  background: rgba(255,255,255,.93);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  border-radius: 20px; overflow: hidden;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 24px rgba(0,0,0,.04);
  margin-bottom: 14px;
}
.ps-head {
  display: flex; align-items: center; gap: 13px;
  padding: 14px 20px 12px;
  border-bottom: 1px solid rgba(0,0,0,.055);
}
.ps-head-icon { font-size: 2rem; line-height: 1; flex-shrink: 0; }
.ps-head-step { font-size: .58rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; margin-bottom: 2px; }
.ps-head-title { font-size: 1rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; letter-spacing: -.1px; }
.ps-body { padding: 14px 20px 18px; }

/* ── Illustrated to-do item ── */
.td {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,.04);
}
.td:last-child { border-bottom: none; }
.td-ring {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  border: 2px solid; display: flex; align-items: center;
  justify-content: center; font-size: .6rem; font-weight: 900; margin-top: 1px;
}
.td-icon { font-size: 1.18rem; flex-shrink: 0; line-height: 1.35; }
.td-body { flex: 1; min-width: 0; }
.td-name { font-size: .83rem; font-weight: 700; color: #0f172a; }
.td-note { font-size: .7rem; color: #94a3b8; margin-top: 2px; line-height: 1.35; }
.td-qty {
  font-size: .65rem; font-weight: 800; padding: 2px 9px;
  border-radius: 12px; flex-shrink: 0; white-space: nowrap;
  align-self: flex-start; margin-top: 2px;
}

/* ── Chip rows ── */
.chips { display: flex; gap: 7px; flex-wrap: wrap; margin: 8px 0 2px; }
.chip {
  display: flex; align-items: center; gap: 5px;
  background: rgba(0,0,0,.04); border-radius: 20px;
  padding: 5px 11px; font-size: .72rem; color: #374151; font-weight: 500;
}

/* ── Water stat ── */
.wn { font-size: 3rem; font-weight: 900; font-family: 'Space Grotesk', sans-serif; line-height: 1; }
.wu { font-size: .68rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: #94a3b8; }

/* ── Mini bullet list ── */
.mbul { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; font-size: .76rem; color: #374151; line-height: 1.4; }
.mbul-dot { width: 5px; height: 5px; border-radius: 50%; background: #cbd5e1; flex-shrink: 0; margin-top: 6px; }

/* ── Evac split ── */
.ev-split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.ev-go   { background: rgba(239,68,68,.07); border-radius: 13px; padding: 13px 15px; border: 1px solid rgba(239,68,68,.18); }
.ev-stay { background: rgba(34,197,94,.07); border-radius: 13px; padding: 13px 15px; border: 1px solid rgba(34,197,94,.18); }
.ev-lbl  { font-size: .6rem; font-weight: 900; letter-spacing: .15em; text-transform: uppercase; margin-bottom: 9px; }
.ev-item { font-size: .72rem; color: #374151; margin-bottom: 5px; display: flex; gap: 6px; line-height: 1.35; }
.ev-bullet { flex-shrink: 0; margin-top: 1px; }

/* ── Bag timeline ── */
.bag-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
.bag-col { background: rgba(239,68,68,.06); border-radius: 11px; padding: 10px 12px; border: 1px solid rgba(239,68,68,.12); }
.bag-t   { font-size: .58rem; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: #ef4444; margin-bottom: 7px; }
.bag-i   { font-size: .72rem; color: #374151; margin-bottom: 3px; line-height: 1.3; display: flex; gap: 5px; }

/* ── Budget row ── */
.bd-row  { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid rgba(0,0,0,.04); }
.bd-row:last-child { border-bottom: none; }
.bd-n    { font-size: .62rem; font-weight: 800; color: #b0b8c8; width: 16px; text-align: center; flex-shrink: 0; }
.bd-name { font-size: .79rem; font-weight: 600; color: #0f172a; flex: 1; min-width: 0; }
.bd-sub  { font-size: .66rem; color: #94a3b8; }
.bd-cost { font-size: .84rem; font-weight: 800; font-family: 'Space Grotesk', sans-serif; flex-shrink: 0; }

/* ── Action tiles ── */
.act-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 4px; }
.act-tile {
  border-radius: 18px; padding: 20px 16px 16px;
  position: relative; overflow: hidden;
  border: 1px solid rgba(0,0,0,.08);
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
}
.act-num {
  position: absolute; top: 14px; right: 14px;
  width: 27px; height: 27px; border-radius: 50%;
  color: white; font-size: .72rem; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
}
.act-big  { font-size: 2.4rem; margin-bottom: 10px; line-height: 1; }
.act-when {
  display: inline-block; font-size: .58rem; font-weight: 900;
  letter-spacing: .12em; text-transform: uppercase;
  padding: 3px 9px; border-radius: 8px; margin-bottom: 9px;
}
.act-title { font-size: .9rem; font-weight: 800; color: #0f172a; font-family: 'Space Grotesk', sans-serif; margin-bottom: 11px; line-height: 1.25; }
.act-step { display: flex; gap: 7px; align-items: flex-start; font-size: .72rem; color: #4b5563; margin-bottom: 5px; line-height: 1.4; }
.act-step-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; margin-top: 6px; }
.act-meta { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
.act-pill {
  display: flex; align-items: center; gap: 4px;
  background: rgba(255,255,255,.72); border-radius: 8px;
  padding: 4px 9px; font-size: .68rem; color: #64748b; font-weight: 500;
}

/* ── Plan title bar ── */
.plan-bar {
  background: rgba(255,255,255,.88); backdrop-filter: blur(14px);
  border-radius: 14px; padding: 14px 20px; border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 1px 10px rgba(0,0,0,.04); margin-bottom: 18px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
}
.plan-bar-city { font-size: 1.1rem; font-weight: 900; color: #0f172a; font-family: 'Space Grotesk', sans-serif; }
.plan-bar-sub  { font-size: .72rem; color: #94a3b8; margin-top: 2px; }

/* ── Loading ── */
@keyframes ep-pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
.ep-load-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; animation: ep-pulse 1.4s ease-in-out infinite; }

/* ── Two-col plan grid ── */
.plan-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

/* ── Section label spacing ── */
.sl { margin-top: 13px; margin-bottom: 6px; }
</style>
"""


def build_prompt(city, adults, children, special, budget, housing, risks, day11_gaps):
    city = city.replace("\n", " ")[:120]
    household = f"{adults} adult{'s' if adults != 1 else ''}"
    if children:
        household += f" + {children} child{'ren' if children != 1 else ''}"
    special_str = ", ".join(special) if special else "none"
    risks_str = ", ".join(risks) if risks else "general emergencies"
    gap_note = f"\nPrioritise closing these weak areas: {day11_gaps}." if day11_gaps else ""

    return f"""You are a senior emergency preparedness advisor.
Household: {household} in {city}. Housing: {housing}. Budget: {budget}. Special needs: {special_str}. Risks: {risks_str}.{gap_note}

Return ONLY valid JSON, no prose, no markdown fences, exactly this schema:
{{
  "kit": [
    {{"icon":"🔦","name":"Flashlight","qty":"2 units","note":"LED, 100hr battery life","priority":"critical"}}
  ],
  "water": {{
    "total_litres": 36,
    "containers": ["6× 6-litre bottles — $18 at Walmart"],
    "backup": ["Fill bathtub before storm (80L)", "Nearest creek: 1.2km north"],
    "purify": ["Boil 1 min", "Iodine tablets × 50", "Lifestraw filter"]
  }},
  "food": [
    {{"icon":"🥫","name":"Canned chickpeas","qty":"14 cans","note":"protein + fibre, 5yr shelf life"}}
  ],
  "food_notes": "Rotate annually. Keep in cool dark place below 20°C. Open oldest first.",
  "meds": ["Paracetamol 500mg × 48 tabs", "Sterile bandages × 10", "Antiseptic wipes × 20"],
  "comms": {{
    "call_order": ["999 / 911 (local emergency)", "Out-of-area contact: family member in different city"],
    "meet_near": "Corner of Main St & Park Ave — the red post office, 3 min walk",
    "meet_far": "City library car park, 8km inland, 45 High Street",
    "offline": ["Battery-powered AM/FM radio", "Written note under doormat with destination", "3 whistle blasts = help needed"]
  }},
  "evac": {{
    "go_when": ["Mandatory evacuation order issued", "Wildfire smoke visible from home", "Water level at doorstep"],
    "stay_when": ["Power outage only", "Heavy rain but no flooding risk", "Advisory (not mandatory) warning"],
    "bag_90s": ["Passport/ID", "Phone + charger", "Cash $200", "3-day medication"],
    "bag_5m": ["72hr kit bag", "Laptop + hard drive", "Pet carrier + food"],
    "bag_15m": ["Sleeping bags × 2", "3 days clothing", "Children school records"],
    "routes": ["Primary: Highway 1 North → Exit 42 → Red Cross shelter (12km)", "Backup: River Road East → County fairgrounds (9km, avoids highway)"]
  }},
  "budget": [
    {{"priority":1,"name":"Water storage (6× 6L bottles)","qty":"6 units","cost":"$18","where":"Walmart / dollar store"}}
  ],
  "budget_total": "$145",
  "actions": [
    {{
      "icon":"💧",
      "title":"Build your water cache",
      "when":"This weekend",
      "steps":["Buy 6× 6L bottles at Walmart ($18)","Fill and store under sink or in closet","Label with today's date — replace in 12 months"],
      "time":"45 minutes",
      "cost":"$18"
    }}
  ]
}}

Rules: kit ≥ 12 items. food ≥ 8 items. budget ≥ 8 items ordered by priority. Exactly 3 actions covering different days (Day 1–2, Day 3–5, Day 6–7). Be specific to {city} — real local numbers, known hazards."""


def call_api(prompt: str) -> dict | None:
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
                "max_tokens": 4096,
                "temperature": 0.25,
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if model adds them
        if "```" in content:
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else parts[0]
            if content.startswith("json"):
                content = content[4:].lstrip()
        return json.loads(content)
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


# ── HTML component helpers ──────────────────────────────────────────────────────

def _card(color: str, icon: str, step: str, title: str, body: str) -> str:
    return (
        f'<div class="ps-card">'
        f'<div class="ps-head" style="background:linear-gradient(135deg,{color}14,{color}05)">'
        f'<div class="ps-head-icon">{icon}</div>'
        f'<div>'
        f'<div class="ps-head-step" style="color:{color}">{step}</div>'
        f'<div class="ps-head-title">{title}</div>'
        f'</div>'
        f'</div>'
        f'<div class="ps-body">{body}</div>'
        f'</div>'
    )


def _todo(icon: str, name: str, qty: str, note: str, color: str, priority: str = "med") -> str:
    ring_opacity = "1" if priority == "critical" else ("0.75" if priority == "high" else "0.5")
    return (
        f'<div class="td">'
        f'<div class="td-ring" style="color:{color};border-color:{color};opacity:{ring_opacity}">✓</div>'
        f'<div class="td-icon">{icon}</div>'
        f'<div class="td-body">'
        f'<div class="td-name">{name}</div>'
        f'{"<div class=td-note>" + note + "</div>" if note else ""}'
        f'</div>'
        f'<div class="td-qty" style="background:{color}18;color:{color}">{qty}</div>'
        f'</div>'
    )


def _bullet(text: str, dot_color: str = "#cbd5e1") -> str:
    return (
        f'<div class="mbul">'
        f'<div class="mbul-dot" style="background:{dot_color}"></div>'
        f'<span>{text}</span>'
        f'</div>'
    )


def _chip(icon: str, text: str) -> str:
    return f'<div class="chip">{icon} {text}</div>'


# ── Section renderers ───────────────────────────────────────────────────────────

def _render_kit(items: list) -> str:
    col = C["kit"]
    body = "".join(
        _todo(i.get("icon", "📦"), i.get("name", ""), i.get("qty", ""),
              i.get("note", ""), col, i.get("priority", "med"))
        for i in items
    )
    return _card(col, "🎒", "SECTION 01", "72-Hour Emergency Kit", body)


def _render_water(data: dict) -> str:
    col = C["water"]
    total = data.get("total_litres", 0)
    containers = "".join(_chip("🪣", c) for c in data.get("containers", []))
    backup = "".join(_bullet(b, col) for b in data.get("backup", []))
    purify = "".join(_chip("✨", p) for p in data.get("purify", []))
    body = (
        f'<div style="display:flex;align-items:flex-end;gap:7px;margin-bottom:16px">'
        f'<div class="wn" style="color:{col}">{total}</div>'
        f'<div style="padding-bottom:6px">'
        f'<div class="wu">litres total</div>'
        f'<div style="font-size:.68rem;color:#b0b8c8">minimum for 3 days</div>'
        f'</div>'
        f'</div>'
        f'<div class="ep-lbl">Storage containers</div>'
        f'<div class="chips">{containers}</div>'
        f'<div class="ep-lbl sl">Backup water sources</div>'
        + backup +
        f'<div class="ep-lbl sl">Purification methods</div>'
        f'<div class="chips">{purify}</div>'
    )
    return _card(col, "💧", "SECTION 02", "Water Plan", body)


def _render_food(items: list, notes: str, meds: list) -> str:
    col = C["food"]
    food_html = "".join(
        _todo(i.get("icon", "🥫"), i.get("name", ""), i.get("qty", ""), i.get("note", ""), col)
        for i in items
    )
    meds_html = "".join(_bullet(m, col) for m in meds)
    body = (
        food_html +
        (f'<div class="ep-lbl sl">Storage note</div>'
         f'<div style="font-size:.74rem;color:#64748b;line-height:1.55;'
         f'background:rgba(22,163,74,.06);border-radius:9px;padding:8px 11px;'
         f'border-left:3px solid {col}">{notes}</div>'
         if notes else "") +
        f'<div class="ep-lbl sl">Medications &amp; first aid</div>'
        + meds_html
    )
    return _card(col, "🍱", "SECTION 03", "Food & Medication", body)


def _render_comms(data: dict) -> str:
    col = C["comms"]
    calls_html = "".join(
        f'<div class="td">'
        f'<div class="td-ring" style="color:{col};border-color:{col}">{i+1}</div>'
        f'<div class="td-body"><div class="td-name">{c}</div></div>'
        f'</div>'
        for i, c in enumerate(data.get("call_order", []))
    )
    offline_html = "".join(_bullet(o, col) for o in data.get("offline", []))
    near = data.get("meet_near", "")
    far = data.get("meet_far", "")
    body = (
        f'<div class="ep-lbl">Who to call (in order)</div>'
        + calls_html +
        f'<div class="ep-lbl sl">Meeting points</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px">'
        f'<div style="background:rgba(139,92,246,.07);border-radius:11px;padding:11px 13px;border:1px solid rgba(139,92,246,.15)">'
        f'<div style="font-size:.58rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:{col};margin-bottom:5px">Near home</div>'
        f'<div style="font-size:.74rem;color:#0f172a;line-height:1.4">{near}</div>'
        f'</div>'
        f'<div style="background:rgba(139,92,246,.07);border-radius:11px;padding:11px 13px;border:1px solid rgba(139,92,246,.15)">'
        f'<div style="font-size:.58rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:{col};margin-bottom:5px">Far from area</div>'
        f'<div style="font-size:.74rem;color:#0f172a;line-height:1.4">{far}</div>'
        f'</div>'
        f'</div>'
        f'<div class="ep-lbl sl">Offline fallbacks</div>'
        + offline_html
    )
    return _card(col, "📡", "SECTION 04", "Communications Plan", body)


def _render_evac(data: dict) -> str:
    col = C["evac"]
    go_items = "".join(
        f'<div class="ev-item"><span class="ev-bullet" style="color:#ef4444">⚡</span><span>{g}</span></div>'
        for g in data.get("go_when", [])
    )
    stay_items = "".join(
        f'<div class="ev-item"><span class="ev-bullet" style="color:#16a34a">✓</span><span>{s}</span></div>'
        for s in data.get("stay_when", [])
    )
    def bag_col(time_label: str, items: list) -> str:
        rows = "".join(
            f'<div class="bag-i"><span style="color:#ef4444;font-size:.7rem">›</span><span>{item}</span></div>'
            for item in items
        )
        return (
            f'<div class="bag-col">'
            f'<div class="bag-t">{time_label}</div>'
            + rows +
            f'</div>'
        )
    routes_html = "".join(
        f'<div style="font-size:.74rem;color:#374151;padding:6px 0;border-bottom:1px solid rgba(0,0,0,.04);'
        f'display:flex;gap:8px;align-items:flex-start">'
        f'<span style="font-size:.9rem;flex-shrink:0">🗺️</span><span>{r}</span></div>'
        for r in data.get("routes", [])
    )
    body = (
        f'<div class="ev-split">'
        f'<div class="ev-go"><div class="ev-lbl" style="color:#ef4444">🚗 Go now when…</div>{go_items}</div>'
        f'<div class="ev-stay"><div class="ev-lbl" style="color:#16a34a">🏠 Stay when…</div>{stay_items}</div>'
        f'</div>'
        f'<div class="ep-lbl">Grab bag — what to take</div>'
        f'<div class="bag-row">'
        + bag_col("90 seconds", data.get("bag_90s", []))
        + bag_col("5 minutes", data.get("bag_5m", []))
        + bag_col("15 minutes", data.get("bag_15m", []))
        + f'</div>'
        f'<div class="ep-lbl sl">Evacuation routes</div>'
        + routes_html
    )
    return _card(col, "🚗", "SECTION 05", "Evacuation Plan", body)


def _render_budget(items: list, total: str) -> str:
    col = C["budget"]
    rows_html = "".join(
        f'<div class="bd-row">'
        f'<div class="bd-n">{i+1}</div>'
        f'<div style="flex:1;min-width:0">'
        f'<div class="bd-name">{item.get("name","")}'
        f'{"<span style=font-size:.65rem;color:#94a3b8;margin-left:4px>× " + item.get("qty","") + "</span>" if item.get("qty") else ""}'
        f'</div>'
        f'<div class="bd-sub">{item.get("where","")}</div>'
        f'</div>'
        f'<div class="bd-cost" style="color:{col}">{item.get("cost","")}</div>'
        f'</div>'
        for i, item in enumerate(items)
    )
    total_bar = (
        f'<div style="margin-top:12px;padding-top:12px;border-top:2px solid rgba(99,102,241,.15);'
        f'display:flex;justify-content:space-between;align-items:center">'
        f'<div style="font-size:.72rem;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase">Estimated total</div>'
        f'<div style="font-size:1.4rem;font-weight:900;font-family:Space Grotesk,sans-serif;color:{col}">{total}</div>'
        f'</div>'
    ) if total else ""
    return _card(col, "💰", "SECTION 06", "Budget Breakdown", rows_html + total_bar)


def _render_actions(actions: list) -> str:
    col = C["action"]
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
        tile = (
            f'<div class="act-tile" style="background:linear-gradient(145deg,{ac}12,{ac}05)">'
            f'<div class="act-num" style="background:{ac}">{i+1}</div>'
            f'<div class="act-big">{a.get("icon","✅")}</div>'
            f'<div class="act-when" style="background:{ac}20;color:{ac}">{a.get("when","This week")}</div>'
            f'<div class="act-title">{a.get("title","")}</div>'
            + steps_html +
            f'<div class="act-meta">'
            f'<div class="act-pill">⏱ {a.get("time","")}</div>'
            f'<div class="act-pill">💰 {a.get("cost","")}</div>'
            f'</div>'
            f'</div>'
        )
        tiles.append(tile)

    header = (
        f'<div style="display:flex;align-items:center;gap:13px;padding:14px 20px 12px;'
        f'background:linear-gradient(135deg,{col}14,{col}05);'
        f'border-bottom:1px solid rgba(0,0,0,.055);margin:-0px">'
        f'<div style="font-size:2rem;line-height:1">✅</div>'
        f'<div>'
        f'<div style="font-size:.58rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:{col};margin-bottom:2px">SECTION 07</div>'
        f'<div style="font-size:1rem;font-weight:800;color:#0f172a;font-family:Space Grotesk,sans-serif">3 Actions This Week</div>'
        f'</div>'
        f'</div>'
    )
    body = (
        f'<div class="act-grid">'
        + "".join(tiles) +
        f'</div>'
    )
    return (
        f'<div class="ps-card">'
        + header +
        f'<div class="ps-body">{body}</div>'
        f'</div>'
    )


def _render_plan(data: dict, city: str, household: str) -> None:
    budget_str = data.get("budget_total", "")
    st.markdown(
        f'<div class="plan-bar">'
        f'<div>'
        f'<div class="plan-bar-city">📍 {city}</div>'
        f'<div class="plan-bar-sub">{household}</div>'
        f'</div>'
        f'{"<div style=font-size:.8rem;font-weight:700;color:#6366f1>" + budget_str + " estimated</div>" if budget_str else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Top row: Kit + Water side by side
    st.markdown('<div class="plan-2col">', unsafe_allow_html=True)
    st.markdown(_render_kit(data.get("kit", [])), unsafe_allow_html=True)
    st.markdown(_render_water(data.get("water", {})), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Food + Comms
    st.markdown('<div class="plan-2col">', unsafe_allow_html=True)
    st.markdown(
        _render_food(data.get("food", []), data.get("food_notes", ""), data.get("meds", [])),
        unsafe_allow_html=True,
    )
    st.markdown(_render_comms(data.get("comms", {})), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Evacuation — full width
    st.markdown(_render_evac(data.get("evac", {})), unsafe_allow_html=True)

    # Budget — full width
    st.markdown(_render_budget(data.get("budget", []), data.get("budget_total", "")), unsafe_allow_html=True)

    # 3 Actions — full width
    st.markdown(_render_actions(data.get("actions", [])), unsafe_allow_html=True)


def _placeholder() -> None:
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;min-height:65vh;gap:20px;padding:32px 20px;text-align:center">'
        '<div style="font-size:3.5rem;line-height:1">🛡️</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#1e293b;'
        'font-family:Space Grotesk,sans-serif;letter-spacing:-.2px">Your Emergency Plan</div>'
        '<div style="font-size:.8rem;color:#94a3b8;max-width:320px;line-height:1.65">'
        'Fill in your city, household, and budget on the left.<br>'
        'Claude generates a beautiful illustrated plan in ~30 seconds.</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:4px;max-width:460px">'
        + "".join(
            f'<div style="display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:20px;'
            f'background:rgba(255,255,255,.7);border:1px solid rgba(0,0,0,.07);backdrop-filter:blur(8px)">'
            f'<span style="font-size:1rem">{icon}</span>'
            f'<span style="font-size:.72rem;font-weight:500;color:#64748b">{label}</span>'
            f'</div>'
            for icon, label in [
                ("🎒", "Illustrated kit"), ("💧", "Water calc"), ("🍱", "Food & meds"),
                ("📡", "Comms plan"), ("🚗", "Evac routes"), ("💰", "Budget list"), ("✅", "3 actions"),
            ]
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    if "day11_gaps" not in st.session_state:
        try:
            gaps_file = pathlib.Path(".resilience_gaps.json")
            if gaps_file.exists():
                data = json.loads(gaps_file.read_text())
                st.session_state["day11_gaps"] = ", ".join(data.get("gaps", []))
        except Exception:
            pass

    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="ep-header">'
        '<div class="ep-topline"><span class="ep-dot"></span>'
        'EMERGENCY PREP GENERATOR · DAY 12 · THE RESILIENCE STACK'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 2.55], gap="small")

    with left:
        st.markdown('<span class="ep-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ep-pad">'
            '<h2 class="ep-title">Emergency Plan Generator</h2>'
            '<p class="ep-desc">City · household · budget → illustrated plan in ~30 seconds.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        city = st.text_input(
            "Your city or region",
            placeholder="e.g. Miami FL · rural Yorkshire UK · Lagos Nigeria",
            key="city",
        )

        c1, c2 = st.columns(2)
        with c1:
            adults = st.number_input("Adults", min_value=1, max_value=20, value=2, key="adults")
        with c2:
            children = st.number_input("Children", min_value=0, max_value=20, value=0, key="children")

        budget = st.radio(
            "Preparedness budget",
            ["Under $50", "$50–150", "$150–350", "$350–750", "$750+"],
            index=1,
            key="budget",
        )

        st.markdown('<hr class="ep-sep" style="margin:8px 20px">', unsafe_allow_html=True)
        st.markdown('<div style="padding:0 20px 12px">', unsafe_allow_html=True)
        gen = st.button(
            "Generate illustrated plan →",
            type="primary",
            use_container_width=True,
            disabled=not city.strip(),
            key="gen",
        )
        if not city.strip():
            st.markdown(
                '<div style="font-size:.68rem;color:#94a3b8;text-align:center;margin-top:4px">'
                'Enter your city above to enable</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("+ More details (housing, risks, special needs)"):
            housing = st.radio(
                "Housing type",
                ["Apartment / flat", "House with garden", "Rural / farm", "Vehicle or boat"],
                key="housing",
            )
            risks = st.multiselect(
                "Primary risks in your area",
                RISK_OPTIONS,
                placeholder="Select all that apply",
                key="risks",
            )
            special = st.multiselect(
                "Special household needs",
                SPECIAL_OPTIONS,
                placeholder="Select if relevant",
                key="special",
            )
            day11_gaps = st.text_input(
                "Weak areas from Day 11 audit (optional)",
                placeholder="e.g. Water, Food",
                key="day11_gaps",
            )

    with right:
        if gen:
            if not OPENROUTER_KEY:
                st.error("OPENROUTER_API_KEY not set. Add it to your .env file and restart.")
            else:
                hh_adults = int(adults)
                hh_children = int(children)
                household_str = f"{hh_adults} adult{'s' if hh_adults != 1 else ''}"
                if hh_children:
                    household_str += f" + {hh_children} child{'ren' if hh_children != 1 else ''}"

                prompt = build_prompt(
                    city=city.strip(),
                    adults=hh_adults,
                    children=hh_children,
                    special=special if "special" in st.session_state else [],
                    budget=budget,
                    housing=housing if "housing" in st.session_state else "Apartment / flat",
                    risks=risks if "risks" in st.session_state else [],
                    day11_gaps=day11_gaps.strip() if "day11_gaps" in st.session_state else "",
                )

                with st.spinner("Claude is building your illustrated plan…"):
                    plan_data = call_api(prompt)

                if plan_data is None:
                    st.error("Plan generation failed — the response wasn't valid JSON. Please try again.")
                else:
                    st.session_state["plan_data"] = plan_data
                    st.session_state["plan_city"] = city.strip()
                    st.session_state["plan_household"] = household_str
                    _render_plan(plan_data, city.strip(), household_str)

        elif st.session_state.get("plan_data"):
            _render_plan(
                st.session_state["plan_data"],
                st.session_state.get("plan_city", ""),
                st.session_state.get("plan_household", ""),
            )
        else:
            _placeholder()


if __name__ == "__main__":
    main()
