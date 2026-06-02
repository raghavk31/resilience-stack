"""
The Resilience Stack — Day 11
Personal Resilience Audit

5-minute questionnaire → personalised resilience score across 5 dimensions.
Action plan prioritised by weakest area. Shareable via URL encoding.

Dimensions:
  Energy    — grid dependency, backup power, renewables
  Water     — storage, backup sources, treatment
  Food      — stockpile, self-production, local sourcing
  Community — neighbour connections, mutual aid, emergency planning
  Finance   — emergency savings, income diversity, insurance
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
    (60,  80, "Stable",     "#4ade80"),
    (40,  60, "Vulnerable", "#f59e0b"),
    (20,  40, "At Risk",    "#ef4444"),
    ( 0,  20, "Critical",   "#7f1d1d"),
]


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #323232; }
.stApp { background: #f2f2f2 !important; }
[data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; background: transparent !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"], section.main { background: #f2f2f2 !important; }

.mc-header {
  background: #ffffff;
  border-bottom: 1px solid rgba(0,0,0,0.08);
  padding: 18px 32px 14px;
}
.mc-topline {
  font-size: 10px; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: #bbb;
  display: flex; align-items: center; gap: 8px;
}
.mc-dot { width: 9px; height: 9px; border-radius: 50%; border: 2px solid #bbb; display: inline-block; }

[data-testid="stHorizontalBlock"]:has(.mc-left) { gap: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:first-child {
  background: #ffffff !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 80px);
}
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="column"]:last-child {
  background: #f2f2f2 !important;
  padding: 20px 28px !important;
}

.mc-left  { height: 0; margin: 0; padding: 0; display: block; }
.mc-pad   { padding: 20px 22px 0; }
.mc-title {
  font-size: 1.3rem; font-weight: 800; color: #111; line-height: 1.2;
  margin: 0 0 .4rem; letter-spacing: -.25px;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-desc  { font-size: .78rem; color: #888; line-height: 1.65; margin: 0; }
.mc-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 14px 0; }
.mc-sec   { font-size: .67rem; font-weight: 700; color: #ccc; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.mc-note  { font-size: .65rem; color: #bbb; line-height: 1.6; }
.r-lbl    { font-size: .67rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #bbb; margin-bottom: 6px; }

.score-badge {
  border-radius: 10px; padding: 16px 18px; margin-bottom: 16px;
}
.score-badge-lbl  { font-size: .67rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px; }
.score-badge-val  { font-size: 3.2rem; font-weight: 900; line-height: 1; letter-spacing: -2px; font-family: 'Space Grotesk', sans-serif; }
.score-badge-band { font-size: .85rem; font-weight: 600; margin-top: 6px; }

/* Compact radio styling */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .75rem !important; font-weight: 500 !important; color: #555 !important;
}
section.main [data-testid="stRadio"] > label {
  font-size: .72rem !important; font-weight: 600 !important; color: #333 !important;
  margin-bottom: 3px !important;
}
section.main [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
  font-size: .72rem !important; color: #555 !important;
}

.action-card {
  background: white; border-radius: 8px; padding: 14px 16px;
  margin-bottom: 12px; border-left: 3px solid #ddd;
}
.action-row {
  background: #f8f9fa; border-radius: 5px; padding: 8px 10px; margin-bottom: 6px;
}
</style>
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resilience_band(score: float) -> tuple[str, str]:
    for lo, hi, label, color in RESILIENCE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#888"


def compute_vuln_scores(answers: dict) -> dict[str, float]:
    scores: dict[str, float] = {}
    for sec in SECTIONS:
        vals = []
        for q in sec["questions"]:
            idx = max(0, min(len(q["options"]) - 1, answers.get(q["key"], 0)))
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

    # Pre-populate from URL params on first load
    if "audit_initialized" not in st.session_state:
        st.session_state["audit_initialized"] = True
        if "a" in st.query_params:
            try:
                loaded = decode_answers(st.query_params["a"])
                for k, v in loaded.items():
                    if isinstance(v, int):
                        st.session_state[f"q_{k}"] = v
            except Exception:
                pass

    left, right = st.columns([1.15, 2.85], gap="large")
    current_answers: dict[str, int] = {}

    # ── Left: questionnaire ───────────────────────────────────────────────────

    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Personal Resilience Audit</h2>'
            '<p class="mc-desc">10 questions · 5 dimensions · ~3 minutes.<br>'
            'Your score and action plan update live as you answer.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        for sec in SECTIONS:
            st.markdown(
                f'<div style="padding:0 22px">'
                f'<hr class="mc-sep">'
                f'<div style="font-size:.67rem;font-weight:700;color:{sec["color"]};'
                f'text-transform:uppercase;letter-spacing:.12em;margin-bottom:1px">'
                f'{sec["name"]}</div>'
                f'<div style="font-size:.68rem;color:#bbb;margin-bottom:8px">{sec["desc"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            for q in sec["questions"]:
                key = f"q_{q['key']}"
                default_idx = st.session_state.get(key, 0)
                opts = [o[0] for o in q["options"]]
                st.markdown('<div style="padding:0 22px 2px">', unsafe_allow_html=True)
                sel = st.radio(q["text"], opts, index=default_idx, key=key)
                st.markdown("</div>", unsafe_allow_html=True)
                current_answers[q["key"]] = opts.index(sel)

        # Update URL params (reflects current answers for sharing)
        encoded = encode_answers(current_answers)
        try:
            if st.query_params.get("a") != encoded:
                st.query_params["a"] = encoded
        except Exception:
            pass

        st.markdown(
            '<div style="padding:0 22px 28px">'
            '<hr class="mc-sep">'
            '<div class="mc-sec">Share your results</div>'
            '<div class="mc-note">The URL in your browser reflects your current answers. '
            'Copy it to share your score with others — they\'ll see your exact results.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Compute ───────────────────────────────────────────────────────────────

    vuln = compute_vuln_scores(current_answers)
    resilience = compute_resilience(vuln)
    band, bcolor = _resilience_band(resilience)
    sorted_secs = sorted(SECTIONS, key=lambda s: vuln[s["name"]], reverse=True)

    # ── Right: score + radar + actions ────────────────────────────────────────

    with right:

        # Score badge + dimension pills
        dim_pills = "".join(
            f'<div style="text-align:center;padding:8px 12px;background:{sec["color"]}12;'
            f'border-radius:8px;border:1px solid {sec["color"]}25">'
            f'<div style="font-size:1.25rem;font-weight:800;color:{sec["color"]};'
            f'font-family:Space Grotesk,sans-serif;line-height:1">'
            f'{vuln[sec["name"]]:.0f}</div>'
            f'<div style="font-size:.6rem;color:#bbb;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-top:3px">{sec["name"][:3]} vuln</div>'
            f'</div>'
            for sec in SECTIONS
        )
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:8px">'
            f'<div class="score-badge" style="background:{bcolor}14;border:1px solid {bcolor}30;min-width:140px">'
            f'<div class="score-badge-lbl" style="color:{bcolor}">Your Resilience Score</div>'
            f'<div class="score-badge-val" style="color:{bcolor}">{resilience:.0f}</div>'
            f'<div class="score-badge-band" style="color:#555">{band}</div>'
            f'</div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">{dim_pills}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Radar chart
        sec_names = [s["name"] for s in SECTIONS]
        vuln_vals = [vuln[n] for n in sec_names]
        cats = sec_names + [sec_names[0]]
        vals = vuln_vals + [vuln_vals[0]]

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
            r=[75] * len(cats), theta=cats,
            line=dict(color="#ef4444", width=1, dash="dot"),
            mode="lines", name="High-risk (75)",
        ))
        rfig.update_layout(
            polar=dict(
                radialaxis=dict(
                    range=[0, 100],
                    tickvals=[25, 50, 75],
                    tickfont=dict(size=9, color="#ccc"),
                    gridcolor="rgba(0,0,0,0.07)",
                ),
                angularaxis=dict(tickfont=dict(size=11, color="#555")),
                bgcolor="rgba(0,0,0,0)",
            ),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#888", size=11),
            margin=dict(l=30, r=30, t=12, b=12),
            legend=dict(
                orientation="h", y=-0.08, x=0.5, xanchor="center",
                font=dict(size=9, color="#aaa"),
                bgcolor="rgba(0,0,0,0)",
            ),
        )

        r1, r2 = st.columns([2, 1])
        with r1:
            st.markdown(
                '<div class="r-lbl">VULNERABILITY RADAR — higher = more exposed</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(rfig, use_container_width=True)
        with r2:
            st.markdown(
                '<div class="r-lbl">How to read this</div>'
                '<div class="mc-note" style="font-size:.71rem;color:#666;line-height:1.7">'
                '<b style="color:#6366f1">Purple area</b> = your vulnerability profile.<br><br>'
                'Closer to centre = lower vulnerability = more resilient.<br><br>'
                'Dotted blue = typical person (~50).<br><br>'
                'Dotted red = high-risk threshold (75).<br><br>'
                '<b>Resilience score</b> = 100 − weighted average vulnerability across all 5 dimensions.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Action plan
        st.markdown(
            '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.08);margin:4px 0 16px">'
            '<div class="r-lbl">YOUR PRIORITY ACTION PLAN — sorted by gap</div>',
            unsafe_allow_html=True,
        )

        effort_colors = {"Quick": "#16a34a", "Medium": "#f59e0b", "Longer-term": "#6366f1"}

        for sec in sorted_secs:
            v = vuln[sec["name"]]
            if v >= 60:
                level, level_label, level_color = "critical", "Critical", "#ef4444"
            elif v >= 35:
                level, level_label, level_color = "moderate", "Moderate", "#f59e0b"
            else:
                level, level_label, level_color = "good", "Well prepared", "#16a34a"

            actions = sec["actions"].get(level, [])[:2]

            rows_html = "".join(
                f'<div class="action-row">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">'
                f'<div style="font-size:.76rem;font-weight:600;color:#333;flex:1">{title}</div>'
                f'<div style="font-size:.64rem;font-weight:700;color:{effort_colors.get(effort,"#888")};'
                f'white-space:nowrap;padding:2px 7px;border-radius:9px;'
                f'background:{effort_colors.get(effort,"#888")}15">{effort}</div>'
                f'</div>'
                f'<div style="font-size:.69rem;color:#888;margin-top:3px;line-height:1.55">{detail}</div>'
                f'</div>'
                for title, detail, effort in actions
            )

            st.markdown(
                f'<div class="action-card" style="border-left-color:{sec["color"]}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
                f'<div style="font-size:.78rem;font-weight:700;color:{sec["color"]};'
                f'text-transform:uppercase;letter-spacing:.08em">{sec["name"]}</div>'
                f'<div style="font-size:.68rem;font-weight:700;color:{level_color};'
                f'background:{level_color}15;padding:2px 10px;border-radius:10px">'
                f'{level_label} · {v:.0f} vuln</div>'
                f'</div>'
                f'{rows_html}'
                f'</div>',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
