"""
The Resilience Stack — Day 11
Personal Resilience Audit

Step-by-step wizard → personalised resilience score across 5 dimensions.
Action plan prioritised by weakest area. Shareable via URL encoding.
"""

import json
import base64
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Resilience Audit · Day 11",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Icons ──────────────────────────────────────────────────────────────────────

ICONS = {
    "Energy":    "⚡",
    "Water":     "💧",
    "Food":      "🌾",
    "Community": "🤝",
    "Finance":   "💰",
}

# ── Questionnaire ──────────────────────────────────────────────────────────────

SECTIONS = [
    {
        "name": "Energy",
        "color": "#f97316",
        "weight": 0.20,
        "desc": "Grid dependency, backup power, renewable sources",
        "questions": [
            {
                "key": "e1",
                "text": "Primary energy setup",
                "options": [
                    ("Grid only, no backup", 85),
                    ("Grid with fossil generator", 60),
                    ("Grid + some solar panels", 35),
                    ("Solar with battery backup", 15),
                    ("Fully off-grid renewable", 5),
                ],
            },
            {
                "key": "e2",
                "text": "How long can you power essentials (fridge, lights, phone) during a grid outage?",
                "options": [
                    ("Not at all", 90),
                    ("Hours only (power bank / car charger)", 70),
                    ("1–3 days (generator / small battery)", 45),
                    ("1–2 weeks (robust battery system)", 20),
                    ("Indefinitely (off-grid)", 5),
                ],
            },
        ],
        "actions": {
            "critical": [
                ("Buy a 20,000 mAh power bank", "~$40 · keeps phone + light running 2+ days during outages", "Quick"),
                ("Switch all lighting to LED", "75% energy reduction — frees capacity for critical loads", "Quick"),
                ("Identify your 5 biggest energy consumers", "Fridge, HVAC, water heater, washer, dryer — know your load", "Quick"),
            ],
            "moderate": [
                ("Get a 1–2 kWh portable battery (EcoFlow, Jackery, Bluetti)", "Powers fridge + lights 12–24h. ~$300–600", "Medium"),
                ("Get solar quotes from 3 local installers", "Payback typically 6–10 years, then near-free energy", "Medium"),
                ("Join a community solar programme", "No roof needed — buy shares in local solar generation", "Medium"),
            ],
            "good": [
                ("Add battery storage to your solar system", "Store excess generation for nights and outages", "Longer-term"),
                ("Explore vehicle-to-home (V2H) if you have an EV", "Your car becomes a 40–80 kWh backup battery", "Longer-term"),
            ],
        },
    },
    {
        "name": "Water",
        "color": "#3b82f6",
        "weight": 0.20,
        "desc": "Storage, backup sources, treatment capability",
        "questions": [
            {
                "key": "w1",
                "text": "Water sources available to you",
                "options": [
                    ("Municipal grid only", 80),
                    ("Municipal + stored reserve", 50),
                    ("Borehole / well", 30),
                    ("Rainwater harvesting system", 25),
                    ("Multiple independent sources", 10),
                ],
            },
            {
                "key": "w2",
                "text": "Drinking water stored at home",
                "options": [
                    ("None", 90),
                    ("1–3 days (a few bottles)", 70),
                    ("1–2 weeks (large containers)", 40),
                    ("1+ month (tanks / barrels)", 10),
                ],
            },
        ],
        "actions": {
            "critical": [
                ("Store 2L per person per day — minimum 2-week supply", "28L for 1 person. Stack large 10–20L food-grade containers", "Quick"),
                ("Buy a portable water filter (LifeStraw, Sawyer, Berkey)", "Makes creek / rainwater / grey water safe to drink. ~$25–50", "Quick"),
                ("Map your nearest natural water sources", "River, stream, spring, lake — know what's within 5 km", "Quick"),
            ],
            "moderate": [
                ("Install a 200–1,000L rainwater tank", "$200–600. Covers garden + grey water indefinitely", "Medium"),
                ("Get a gravity-fed ceramic filter", "No power needed. 4L/hr. Works when everything else fails", "Medium"),
                ("Investigate borehole / well options on your land", "Hydrogeological survey ~$500–1,000. Could be transformative", "Medium"),
            ],
            "good": [
                ("Upgrade to a full rainwater harvesting + treatment system", "Full household supply independent of municipal infrastructure", "Longer-term"),
                ("Join a community water resilience group", "Shared tanks + filtration — more cost-effective at scale", "Longer-term"),
            ],
        },
    },
    {
        "name": "Food",
        "color": "#ca8a04",
        "weight": 0.20,
        "desc": "Stockpile, self-production, local food network",
        "questions": [
            {
                "key": "f1",
                "text": "How many days of food could you sustain without shopping?",
                "options": [
                    ("Less than 3 days", 90),
                    ("3–7 days", 65),
                    ("2–4 weeks", 40),
                    ("1–3 months", 15),
                    ("3+ months", 5),
                ],
            },
            {
                "key": "f2",
                "text": "Food self-production",
                "options": [
                    ("None — 100% purchased", 70),
                    ("Small herbs / pots (windowsill)", 55),
                    ("Vegetable garden (supplements diet)", 30),
                    ("Substantial garden or allotment", 15),
                    ("Smallholder farm / food forest", 5),
                ],
            },
        ],
        "actions": {
            "critical": [
                ("Build a 2-week emergency food supply", "Rice, lentils, oats, canned goods. Rotate every 12 months", "Quick"),
                ("Learn 3 cheap, high-calorie staple meals", "Rice + beans + spice = complete protein at ~50¢/meal", "Quick"),
                ("Find your nearest food bank / mutual aid group", "Resilience includes knowing your local safety net exists", "Quick"),
            ],
            "moderate": [
                ("Start a container garden — even one tomato plant", "Gateway to food production. 5m² = meaningful calories by summer", "Medium"),
                ("Extend food store to 1–3 months", "Focus on: pulses, whole grains, tinned fish, dried fruit", "Medium"),
                ("Join a local food buying collective or CSA", "Lower cost + local relationships + bulk storage together", "Medium"),
            ],
            "good": [
                ("Design a food forest or perennial growing system", "Once established: near-zero maintenance, multi-decade yields", "Longer-term"),
                ("Learn seed-saving", "Close the food loop — full independence from supply chains", "Longer-term"),
            ],
        },
    },
    {
        "name": "Community",
        "color": "#8b5cf6",
        "weight": 0.20,
        "desc": "Neighbour connections, mutual aid, emergency planning",
        "questions": [
            {
                "key": "c1",
                "text": "Neighbourhood connections",
                "options": [
                    ("Don't know my neighbours", 85),
                    ("Know faces / names only", 60),
                    ("Know several neighbours well", 35),
                    ("Strong network, regular contact", 10),
                ],
            },
            {
                "key": "c2",
                "text": "Emergency preparedness",
                "options": [
                    ("No plan at all", 90),
                    ("Vague idea of what I'd do", 65),
                    ("Written plan + basic supplies", 30),
                    ("Full plan + coordinated with others", 10),
                ],
            },
        ],
        "actions": {
            "critical": [
                ("Introduce yourself to 3 immediate neighbours this week", "Resilience = knowing who you can knock on in a crisis", "Quick"),
                ("Write a one-page emergency plan", "Who to call, where to go, what to grab. Takes 20 minutes", "Quick"),
                ("Start or join a neighbourhood communication group", "WhatsApp / Signal group = zero-cost comms infrastructure", "Quick"),
            ],
            "moderate": [
                ("Find your local Mutual Aid or Transition Towns group", "Pre-built resilience networks — just show up once", "Medium"),
                ("Build a 72-hour grab bag", "Documents, cash, water, food, meds, charger, torch, radio", "Medium"),
                ("Host a neighbourhood prep conversation", "Even 5 households coordinating multiplies everyone's capacity", "Medium"),
            ],
            "good": [
                ("Host community skill-shares (first aid, food preservation, solar)", "Knowledge is the most freely shareable resource", "Longer-term"),
                ("Map your neighbourhood's skills, tools, and resources", "Who has a generator? Medical training? A well?", "Longer-term"),
            ],
        },
    },
    {
        "name": "Finance",
        "color": "#64748b",
        "weight": 0.20,
        "desc": "Emergency savings, income diversity, financial buffers",
        "questions": [
            {
                "key": "fi1",
                "text": "Emergency savings (months of living expenses)",
                "options": [
                    ("Less than 1 month", 90),
                    ("1–3 months", 65),
                    ("3–6 months", 35),
                    ("6–12 months", 15),
                    ("12+ months", 5),
                ],
            },
            {
                "key": "fi2",
                "text": "Income diversity",
                "options": [
                    ("Single job, nothing else", 75),
                    ("Single job + some savings buffer", 55),
                    ("Second income stream or freelance work", 30),
                    ("Multiple streams or significant passive income", 10),
                ],
            },
        ],
        "actions": {
            "critical": [
                ("Open a high-yield savings account and auto-transfer $50/month", "1-month buffer in 6 months. The habit matters more than the amount", "Quick"),
                ("Cancel one unused subscription → redirect to savings", "Small levers compound. Every recurring cut is permanent resilience", "Quick"),
                ("Check eligibility for government resilience grants", "Energy efficiency, solar, insulation — often 50–100% subsidised", "Quick"),
            ],
            "moderate": [
                ("Build a 3-month emergency fund before other investing", "This is your resilience buffer — non-negotiable foundation", "Medium"),
                ("Explore one additional income stream", "Freelance, tutoring, selling surplus produce or skills", "Medium"),
                ("Review insurance for climate risks", "Flood, storm, wildfire — check exclusions and coverage gaps", "Medium"),
            ],
            "good": [
                ("Invest in your own resilience infrastructure", "Solar, water tanks, food garden — savings + insurance in one", "Longer-term"),
                ("Explore community investment (bonds, co-ops, credit unions)", "Align capital with local resilience building", "Longer-term"),
            ],
        },
    },
]

RESILIENCE_BANDS = [
    (80, 100, "Resilient",  "#16a34a"),
    (60,  80, "Stable",     "#22c55e"),
    (40,  60, "Vulnerable", "#f59e0b"),
    (20,  40, "At Risk",    "#ef4444"),
    ( 0,  20, "Critical",   "#7f1d1d"),
]


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

*, html, body { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }

/* ── Background ── */
.stApp {
  background:
    radial-gradient(ellipse at 15% 25%, rgba(249,115,22,.07) 0%, transparent 50%),
    radial-gradient(ellipse at 85% 75%, rgba(99,102,241,.08) 0%, transparent 50%),
    radial-gradient(ellipse at 55% 5%,  rgba(59,130,246,.06) 0%, transparent 45%),
    #f7f8fa !important;
}

/* ── Strip Streamlit chrome padding ── */
[data-testid="block-container"] {
  padding: 0 !important; max-width: 100% !important; background: transparent !important;
}
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"], section.main { background: transparent !important; }

/* ── Top header bar ── */
.mc-header {
  background: rgba(255,255,255,.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0,0,0,0.07);
  padding: 14px 28px 10px;
}
.mc-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #b0b8c8;
  display: flex; align-items: center; gap: 8px;
}
.mc-dot { width: 8px; height: 8px; border-radius: 50%; border: 2px solid #c0c8d4; display: inline-block; }

/* ── Two-column layout ── */
[data-testid="stHorizontalBlock"]:has(.mc-left) {
  gap: 0 !important;
  align-items: stretch !important;
}

/* Left wizard panel */
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.90) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 60px);
}

/* Right results panel */
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:last-child {
  background: transparent !important;
  padding: 24px 28px 32px !important;
}

/* Pad widget rows inside the left column */
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stRadio"] {
  padding-left: 20px !important;
  padding-right: 20px !important;
  padding-bottom: 6px !important;
}

/* Nav buttons row in the left column */
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stHorizontalBlock"]:not(:has(.mc-left)) {
  padding: 2px 20px 0 !important;
}

/* ── Misc tokens ── */
.mc-left  { height: 0; margin: 0; padding: 0; display: block; }
.mc-pad   { padding: 18px 22px 12px; }
.mc-title {
  font-size: 1.18rem; font-weight: 800; color: #0f172a; line-height: 1.25;
  margin: 0 0 .3rem; letter-spacing: -.2px;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-desc  { font-size: .76rem; color: #94a3b8; line-height: 1.6; margin: 0; }
.mc-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 10px 0; }
.mc-sec   { font-size: .66rem; font-weight: 700; color: #c8d2e0; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
.mc-note  { font-size: .65rem; color: #94a3b8; line-height: 1.6; }
.r-lbl    { font-size: .65rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px; }

/* ── Score badge ── */
.score-badge {
  border-radius: 14px; padding: 14px 18px; margin-bottom: 0;
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
.score-badge-lbl  { font-size: .65rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px; }
.score-badge-val  { font-size: 3rem; font-weight: 900; line-height: 1; letter-spacing: -2px; font-family: 'Space Grotesk', sans-serif; }
.score-badge-band { font-size: .82rem; font-weight: 600; margin-top: 5px; }

/* ── Radio labels ── */
section.main [data-testid="stRadio"] > label {
  font-size: .74rem !important; font-weight: 600 !important; color: #374151 !important;
  margin-bottom: 4px !important;
}
section.main [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
  font-size: .74rem !important; color: #555 !important;
}

/* ── Buttons ── */
section.main [data-testid="stButton"] > button {
  border-radius: 8px !important;
  font-size: .74rem !important; font-weight: 600 !important;
  border: 1px solid rgba(0,0,0,.1) !important;
  background: rgba(255,255,255,.8) !important;
  backdrop-filter: blur(8px) !important; -webkit-backdrop-filter: blur(8px) !important;
  transition: all .15s !important;
  padding: 6px 14px !important;
}
section.main [data-testid="stButton"] > button:hover {
  background: rgba(255,255,255,.97) !important;
  border-color: rgba(0,0,0,.18) !important;
}
section.main [data-testid="stButton"] > button[kind="primary"] {
  background: #0f172a !important; color: #fff !important; border-color: #0f172a !important;
}
section.main [data-testid="stButton"] > button[kind="primary"]:hover {
  background: #1e293b !important;
}

/* ── Copy link button ── */
.copy-btn {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  padding: 7px 14px; border-radius: 8px; width: 100%;
  background: rgba(255,255,255,.8); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(0,0,0,.1); color: #374151;
  font-size: .72rem; font-weight: 600; cursor: pointer;
  transition: all .15s; font-family: Inter, sans-serif;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
  margin-top: 6px;
}
.copy-btn:hover { background: rgba(255,255,255,.97); border-color: rgba(0,0,0,.18); }

/* ── Action cards ── */
.action-card {
  background: rgba(255,255,255,.82);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 12px; overflow: hidden; margin-bottom: 10px;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 1px 8px rgba(0,0,0,.04);
}
.action-card-body { padding: 12px 14px 14px; }
.action-row {
  background: rgba(248,250,252,.85);
  border-radius: 8px; padding: 8px 10px; margin-bottom: 6px;
  border: 1px solid rgba(0,0,0,.04);
}

/* ── Expander ── */
section.main [data-testid="stExpander"] {
  border: 1px solid rgba(0,0,0,.06) !important;
  background: rgba(255,255,255,.6) !important;
  border-radius: 10px !important;
  margin-top: 2px !important;
}
section.main [data-testid="stExpander"] summary {
  font-size: .7rem !important; color: #64748b !important; padding: 8px 12px !important;
  font-weight: 500 !important;
}

/* ── Radar legend row ── */
.radar-legend {
  display: flex; gap: 20px; flex-wrap: wrap;
  padding: 4px 0 12px; margin-top: -4px;
}
.radar-legend-item {
  display: flex; align-items: center; gap: 6px;
  font-size: .68rem; color: #888;
}
</style>
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resilience_band(score: float) -> tuple[str, str]:
    for lo, hi, label, color in RESILIENCE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#888"


def _default_answers() -> dict[str, str]:
    """Return mid-range option strings (not indices) — Streamlit radio stores strings."""
    return {
        q["key"]: q["options"][len(q["options"]) // 2][0]
        for sec in SECTIONS for q in sec["questions"]
    }


def compute_vuln_scores(answers: dict) -> dict[str, float]:
    scores: dict[str, float] = {}
    for sec in SECTIONS:
        vals = []
        for q in sec["questions"]:
            n = len(q["options"])
            idx = max(0, min(n - 1, answers.get(q["key"], n // 2)))
            vals.append(q["options"][idx][1])
        scores[sec["name"]] = sum(vals) / len(vals) if vals else 50.0
    return scores


def compute_resilience(vuln: dict[str, float]) -> float:
    total = sum(vuln.get(sec["name"], 50) * sec["weight"] for sec in SECTIONS)
    return max(0.0, min(100.0, round(100.0 - total, 1)))


def encode_answers(answers: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(answers, separators=(",", ":")).encode()
    ).decode()


def decode_answers(s: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(s.encode()).decode())


def _step_pills_html(current_step: int) -> str:
    pills = []
    total = len(SECTIONS)
    for i, sec in enumerate(SECTIONS):
        icon = ICONS[sec["name"]]
        name = sec["name"]
        color = sec["color"]
        if i == current_step:
            style = (
                f"background:{color};color:white;border-color:{color};"
                "font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,.12);"
            )
            label = f"{icon} {name}"
        elif i < current_step:
            style = (
                "background:rgba(22,163,74,.1);color:#15803d;"
                "border-color:rgba(22,163,74,.3);"
            )
            label = f"✓ {name}"
        else:
            style = "background:rgba(255,255,255,.5);color:#94a3b8;border-color:rgba(0,0,0,.08);"
            label = f"{icon} {name}"
        pills.append(
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'padding:3px 8px;border-radius:20px;font-size:.6rem;'
            f'border:1.5px solid;{style};white-space:nowrap">{label}</span>'
        )
    active_color = SECTIONS[current_step]["color"]
    pct = round((current_step + 1) / total * 100)
    pills_row = (
        '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:10px 20px 6px;'
        'align-items:center">'
        + "".join(pills)
        + f'<span style="margin-left:auto;font-size:.6rem;font-weight:700;color:#94a3b8;'
        f'white-space:nowrap;align-self:center">'
        f'{current_step + 1} / {total}</span>'
        + "</div>"
    )
    progress_bar = (
        f'<div style="height:3px;background:rgba(0,0,0,.06);margin:0 20px 0">'
        f'<div style="height:3px;width:{pct}%;background:{active_color};'
        f'border-radius:2px;transition:width .3s ease"></div>'
        f'</div>'
    )
    return pills_row + progress_bar


def _action_row_html(title: str, detail: str, effort: str, effort_colors: dict) -> str:
    ec = effort_colors.get(effort, "#888")
    return (
        f'<div class="action-row">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">'
        f'<div style="font-size:.76rem;font-weight:600;color:#333;flex:1">{title}</div>'
        f'<div style="font-size:.64rem;font-weight:700;color:{ec};white-space:nowrap;'
        f'padding:2px 7px;border-radius:9px;background:{ec}15">{effort}</div>'
        f'</div>'
        f'<div style="font-size:.69rem;color:#888;margin-top:3px;line-height:1.55">{detail}</div>'
        f'</div>'
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="mc-header">
      <div class="mc-topline">
        <span class="mc-dot"></span>
        RESILIENCE AUDIT · DAY 11 · THE RESILIENCE STACK
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Init session state ────────────────────────────────────────────────────
    if "audit_initialized" not in st.session_state:
        st.session_state["audit_initialized"] = True
        st.session_state["current_step"] = 0
        st.session_state["audit_done"] = False
        st.session_state["audit_from_url"] = False
        st.session_state["url_decode_error"] = False
        # Load URL params first; fall back to mid-range defaults
        # Session_state radio keys must be option strings, not integer indices
        if "a" in st.query_params:
            try:
                loaded = decode_answers(st.query_params["a"])
                for sec in SECTIONS:
                    for q in sec["questions"]:
                        if q["key"] in loaded and isinstance(loaded[q["key"]], int):
                            n = len(q["options"])
                            idx = max(0, min(n - 1, loaded[q["key"]]))
                            st.session_state[f"q_{q['key']}"] = q["options"][idx][0]
                st.session_state["audit_from_url"] = True
                st.session_state["audit_done"] = True
            except Exception:
                st.session_state["url_decode_error"] = True
        # For keys not yet set (no URL param), seed with mid-range option string
        for k, v in _default_answers().items():
            if f"q_{k}" not in st.session_state:
                st.session_state[f"q_{k}"] = v

    # ── Collect all answers from session_state ────────────────────────────────
    # Session_state holds option strings (not ints) after any radio interaction
    current_answers: dict[str, int] = {}
    for sec in SECTIONS:
        for q in sec["questions"]:
            n = len(q["options"])
            opts = [o[0] for o in q["options"]]
            val = st.session_state.get(f"q_{q['key']}")
            if isinstance(val, str) and val in opts:
                current_answers[q["key"]] = opts.index(val)
            else:
                current_answers[q["key"]] = n // 2

    left, right = st.columns([1.45, 2.55], gap="small")

    # ── Left: wizard ──────────────────────────────────────────────────────────
    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Personal Resilience Audit</h2>'
            '<p class="mc-desc">5 dimensions · 10 questions · ~3 minutes.<br>'
            'Results update live as you answer.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        step = max(0, min(len(SECTIONS) - 1, st.session_state.get("current_step", 0)))
        sec = SECTIONS[step]

        st.markdown(_step_pills_html(step), unsafe_allow_html=True)

        # Section header with icon
        st.markdown(
            f'<div style="padding:2px 22px 0">'
            f'<hr class="mc-sep" style="margin:6px 0 8px">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
            f'<div style="width:30px;height:30px;border-radius:50%;flex-shrink:0;'
            f'background:{sec["color"]}1a;display:flex;align-items:center;'
            f'justify-content:center;font-size:1rem">{ICONS[sec["name"]]}</div>'
            f'<div>'
            f'<div style="font-size:.76rem;font-weight:700;color:{sec["color"]};'
            f'text-transform:uppercase;letter-spacing:.1em">{sec["name"]}</div>'
            f'<div style="font-size:.64rem;color:#94a3b8">{sec["desc"]}</div>'
            f'</div></div></div>',
            unsafe_allow_html=True,
        )

        # Questions for this step
        for q in sec["questions"]:
            key = f"q_{q['key']}"
            opts = [o[0] for o in q["options"]]
            sel = st.radio(q["text"], opts, key=key)
            current_answers[q["key"]] = opts.index(sel)

        # Navigation buttons
        nav_l, nav_r = st.columns(2)
        with nav_l:
            if step > 0:
                if st.button("← Back", use_container_width=True):
                    st.session_state["current_step"] = step - 1
                    st.rerun()
        with nav_r:
            is_last = step == len(SECTIONS) - 1
            label = "Done ✓" if is_last else "Next →"
            btn_type = "primary" if is_last else "secondary"
            if st.button(label, use_container_width=True, type=btn_type):
                if is_last:
                    st.session_state["audit_done"] = True
                    st.rerun()
                else:
                    st.session_state["current_step"] = step + 1
                    st.rerun()

        # Reset + share
        st.markdown('<hr class="mc-sep" style="margin:8px 20px 10px">', unsafe_allow_html=True)

        st.markdown('<div style="padding:0 20px">', unsafe_allow_html=True)
        if st.button("↺ Reset all answers", use_container_width=True):
            for k, v in _default_answers().items():
                st.session_state[f"q_{k}"] = v
            st.session_state["current_step"] = 0
            st.session_state["audit_done"] = False
            st.session_state["audit_from_url"] = False
            st.session_state["url_decode_error"] = False
            st.rerun()

        st.markdown(
            '<div class="mc-sec" style="margin-top:12px">Share your results</div>'
            '<div class="mc-note">The URL encodes your exact answers — copy it to share.</div>'
            '<button class="copy-btn" onclick="'
            "navigator.clipboard.writeText(window.location.href).then(function(){"
            "this.innerHTML='&#10003; Copied!';var b=this;"
            "setTimeout(function(){b.innerHTML='&#8853; Copy audit link'},1500);"
            "}.bind(this))"
            '">&#8853; Copy audit link</button>'
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Update URL ────────────────────────────────────────────────────────────
    encoded = encode_answers(current_answers)
    try:
        if st.query_params.get("a") != encoded:
            st.query_params["a"] = encoded
    except Exception:
        pass

    # ── Compute scores ────────────────────────────────────────────────────────
    vuln = compute_vuln_scores(current_answers)
    resilience = compute_resilience(vuln)
    band, bcolor = _resilience_band(resilience)
    sorted_secs = sorted(SECTIONS, key=lambda s: vuln[s["name"]], reverse=True)

    # ── Right: results ────────────────────────────────────────────────────────
    with right:

        audit_done = st.session_state.get("audit_done", False)
        audit_from_url = st.session_state.get("audit_from_url", False)
        show_results = audit_done or audit_from_url

        # ── URL decode error notice ───────────────────────────────────────────
        if st.session_state.get("url_decode_error"):
            st.markdown(
                '<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);'
                'border-radius:10px;padding:10px 14px;margin-bottom:12px;'
                'font-size:.72rem;color:#92400e">'
                '⚠️ That shared link was incomplete — starting fresh with default values.'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Intro placeholder (fresh load, no URL params, not yet done) ──────
        if not show_results:
            dim_teaser = "".join(
                f'<div style="text-align:center">'
                f'<div style="font-size:1.5rem">{ICONS[s["name"]]}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;margin-top:2px;'
                f'text-transform:uppercase;letter-spacing:.08em">{s["name"]}</div>'
                f'</div>'
                for s in SECTIONS
            )
            st.markdown(
                f'<div style="display:flex;flex-direction:column;align-items:center;'
                f'justify-content:center;min-height:60vh;gap:28px;padding:32px 20px">'
                f'<div style="text-align:center">'
                f'<div style="font-size:2.8rem;font-weight:900;color:#e2e8f0;'
                f'font-family:Space Grotesk,sans-serif;line-height:1;letter-spacing:-2px">?</div>'
                f'<div style="font-size:1.05rem;font-weight:700;color:#1e293b;'
                f'font-family:Space Grotesk,sans-serif;margin-top:12px;letter-spacing:-.2px">'
                f'Your Resilience Score</div>'
                f'<div style="font-size:.8rem;color:#94a3b8;margin-top:6px;line-height:1.6;max-width:340px">'
                f'Work through all 5 steps on the left to see how you score across five dimensions of personal resilience.</div>'
                f'</div>'
                f'<div style="display:flex;gap:24px;justify-content:center;flex-wrap:wrap">'
                f'{dim_teaser}'
                f'</div>'
                f'<div style="background:rgba(255,255,255,.7);backdrop-filter:blur(12px);'
                f'-webkit-backdrop-filter:blur(12px);border:1px solid rgba(0,0,0,.08);'
                f'border-radius:10px;padding:12px 20px;font-size:.74rem;color:#64748b;'
                f'display:flex;align-items:center;gap:8px">'
                f'<span>←</span> Start with <strong style="color:#374151">Energy</strong> — takes about 3 minutes'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            return

        # ── Completion banner + mobile scroll trigger + share ─────────────────
        if audit_done and not audit_from_url:
            st.markdown(
                '<div id="results-top"></div>'
                '<script>window.scrollTo({top:document.getElementById("results-top")?.getBoundingClientRect()?.top+window.scrollY-20||9999,behavior:"smooth"});</script>'
                f'<div style="background:rgba(22,163,74,.08);border:1px solid rgba(22,163,74,.25);'
                f'border-radius:12px;padding:12px 16px;margin-bottom:14px;'
                f'display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">'
                f'<div style="display:flex;align-items:center;gap:10px">'
                f'<span style="font-size:1.3rem">✅</span>'
                f'<div>'
                f'<div style="font-size:.78rem;font-weight:700;color:#15803d">Audit complete</div>'
                f'<div style="font-size:.7rem;color:#64748b;margin-top:1px">'
                f'Your action plan is below — sorted by biggest gap.</div>'
                f'</div></div>'
                f'<button class="copy-btn" style="width:auto;padding:6px 14px;margin:0" onclick="'
                "navigator.clipboard.writeText(window.location.href).then(function(){"
                "this.innerHTML='&#10003; Copied!';var b=this;"
                "setTimeout(function(){b.innerHTML='&#8853; Share results'},1500);"
                "}.bind(this))"
                '">&#8853; Share results</button>'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif audit_from_url:
            st.markdown('<div id="results-top"></div>', unsafe_allow_html=True)

        # Score badge + per-dimension resilience pills
        dim_pills = "".join(
            f'<div style="text-align:center;padding:8px 12px;'
            f'background:rgba(255,255,255,.75);backdrop-filter:blur(10px);'
            f'-webkit-backdrop-filter:blur(10px);'
            f'border-radius:10px;border:1px solid rgba(255,255,255,.9);'
            f'box-shadow:0 1px 4px rgba(0,0,0,.04);min-width:52px">'
            f'<div style="font-size:1rem;margin-bottom:2px">{ICONS[s["name"]]}</div>'
            f'<div style="font-size:1.05rem;font-weight:800;color:{s["color"]};'
            f'font-family:Space Grotesk,sans-serif;line-height:1">'
            f'{100 - vuln[s["name"]]:.0f}</div>'
            f'<div style="font-size:.6rem;color:#94a3b8;margin-top:3px;'
            f'white-space:nowrap;letter-spacing:0">{s["name"]}</div>'
            f'</div>'
            for s in SECTIONS
        )
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:16px">'
            f'<div class="score-badge" style="background:{bcolor}14;border:1px solid {bcolor}30;min-width:140px">'
            f'<div class="score-badge-lbl" style="color:{bcolor}">Resilience Score</div>'
            f'<div class="score-badge-val" style="color:{bcolor}">{resilience:.0f}</div>'
            f'<div class="score-badge-band" style="color:#555">{band}</div>'
            f'</div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">{dim_pills}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Radar chart — resilience (higher = better, more intuitive)
        sec_names = [s["name"] for s in SECTIONS]
        resil_vals = [round(100 - vuln[n], 1) for n in sec_names]
        cats = sec_names + [sec_names[0]]
        vals = resil_vals + [resil_vals[0]]

        rfig = go.Figure()
        rfig.add_trace(go.Scatterpolar(
            r=vals, theta=cats, fill="toself",
            fillcolor="rgba(99,102,241,0.14)",
            line=dict(color="#6366f1", width=2.5),
            name="You",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[50] * len(cats), theta=cats,
            line=dict(color="#94a3b8", width=1, dash="dot"),
            mode="lines", name="Typical (~50)",
        ))
        rfig.add_trace(go.Scatterpolar(
            r=[25] * len(cats), theta=cats,
            line=dict(color="#ef4444", width=1, dash="dot"),
            mode="lines", name="High-risk (<25)",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(
                    range=[0, 100],
                    tickvals=[25, 50, 75],
                    tickfont=dict(size=9, color="#ccc"),
                    gridcolor="rgba(0,0,0,0.07)",
                ),
                angularaxis=dict(tickfont=dict(size=12, color="#555")),
                bgcolor="rgba(0,0,0,0)",
            ),
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#888", size=11),
            margin=dict(l=40, r=40, t=16, b=8),
            showlegend=False,
        )

        st.markdown(
            '<div class="r-lbl">RESILIENCE RADAR — larger area = more resilient</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(rfig, use_container_width=True)
        st.markdown(
            '<div class="radar-legend">'
            '<span class="radar-legend-item">'
            '<span style="width:12px;height:3px;background:#6366f1;border-radius:2px;display:inline-block"></span>'
            'Your score</span>'
            '<span class="radar-legend-item">'
            '<span style="width:12px;height:2px;background:#94a3b8;border-radius:2px;display:inline-block;opacity:.6"></span>'
            'Typical (~50)</span>'
            '<span class="radar-legend-item">'
            '<span style="width:12px;height:2px;background:#ef4444;border-radius:2px;display:inline-block;opacity:.7"></span>'
            'High-risk (&lt;25)</span>'
            '<span class="radar-legend-item" style="margin-left:auto;font-size:.64rem;color:#b0b8c8">'
            'Score = weighted resilience across all 5 dimensions</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Action plan
        st.markdown(
            '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.07);margin:4px 0 16px">'
            '<div class="r-lbl">YOUR PRIORITY ACTION PLAN — sorted by gap</div>',
            unsafe_allow_html=True,
        )

        effort_colors = {"Quick": "#16a34a", "Medium": "#f59e0b", "Longer-term": "#6366f1"}

        def _render_action_card(s, v):
            r_score = round(100 - v)
            if v >= 60:
                level, level_label, level_color = "critical", "Critical", "#ef4444"
            elif v >= 35:
                level, level_label, level_color = "moderate", "Moderate", "#f59e0b"
            else:
                level, level_label, level_color = "good", "Well prepared", "#16a34a"

            all_actions = s["actions"].get(level, [])
            top_actions = all_actions[:2]
            extra_actions = all_actions[2:]

            rows_html = "".join(
                _action_row_html(t, d, e, effort_colors) for t, d, e in top_actions
            )
            st.markdown(
                f'<div class="action-card">'
                # Header band — tinted fill, no left-border
                f'<div style="background:{s["color"]}12;border-bottom:1px solid {s["color"]}22;'
                f'padding:9px 14px;display:flex;justify-content:space-between;align-items:center">'
                f'<div style="display:flex;align-items:center;gap:7px">'
                f'<span style="font-size:1rem">{ICONS[s["name"]]}</span>'
                f'<span style="font-size:.76rem;font-weight:700;color:{s["color"]};'
                f'text-transform:uppercase;letter-spacing:.09em">{s["name"]}</span>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span style="font-size:.9rem;font-weight:800;color:{s["color"]};'
                f'font-family:Space Grotesk,sans-serif;letter-spacing:-1px">{r_score}</span>'
                f'<span style="font-size:.66rem;font-weight:700;color:{level_color};'
                f'background:{level_color}15;padding:2px 9px;border-radius:9px">'
                f'{level_label}</span>'
                f'</div></div>'
                # Body
                f'<div class="action-card-body">{rows_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if extra_actions:
                n_extra = len(extra_actions)
                with st.expander(f"+ {n_extra} more action{'s' if n_extra > 1 else ''}"):
                    st.markdown(
                        "".join(_action_row_html(t, d, e, effort_colors) for t, d, e in extra_actions),
                        unsafe_allow_html=True,
                    )

        priority_secs = [(s, vuln[s["name"]]) for s in sorted_secs if vuln[s["name"]] >= 35]
        prepared_secs = [(s, vuln[s["name"]]) for s in sorted_secs if vuln[s["name"]] < 35]

        for s, v in priority_secs:
            _render_action_card(s, v)

        if prepared_secs:
            label = (
                f"✓ {len(prepared_secs)} well-prepared area{'s' if len(prepared_secs) > 1 else ''}"
            )
            with st.expander(label):
                for s, v in prepared_secs:
                    _render_action_card(s, v)

        if not priority_secs:
            st.markdown(
                '<div style="text-align:center;padding:24px;color:#94a3b8;font-size:.78rem">'
                '🎉 All dimensions are in good shape. Expand above to see maintenance actions.'
                '</div>',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
