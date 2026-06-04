"""
The Resilience Stack — Day 12
Emergency Preparedness Generator

City + household + budget → Claude-generated localised emergency plan.
"""

import json
import os

import requests
import streamlit as st

st.set_page_config(
    page_title="Emergency Prep Generator · Day 12",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "anthropic/claude-sonnet-4-5"

RISK_OPTIONS = [
    "Flooding / flash floods",
    "Wildfire",
    "Extreme heat",
    "Hurricane / cyclone / typhoon",
    "Earthquake",
    "Winter storm / blizzard",
    "Tornado",
    "Drought / water shortage",
    "Power grid failure",
    "Coastal storm surge",
]

SPECIAL_OPTIONS = [
    "Pets",
    "Infants or young children",
    "Elderly household members",
    "Medical equipment (CPAP, oxygen, dialysis, etc.)",
    "Mobility limitations",
    "Dietary restrictions / food allergies",
    "Non-English speaking household",
]

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

[data-testid="block-container"] {
  padding: 0 !important; max-width: 100% !important; background: transparent !important;
}
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"], section.main { background: transparent !important; }

/* ── Header ── */
.mc-header {
  background: rgba(255,255,255,.95);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
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
[data-testid="stHorizontalBlock"]:has(.mc-left) { gap: 0 !important; align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child {
  background: rgba(255,255,255,.90) !important;
  backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid rgba(0,0,0,0.08) !important;
  min-height: calc(100vh - 60px);
}
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:last-child {
  background: transparent !important;
  padding: 24px 32px 40px !important;
}

/* Pad widgets in left column */
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stTextInput"],
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stRadio"],
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stMultiSelect"],
[data-testid="stHorizontalBlock"]:has(.mc-left) > [data-testid="stColumn"]:first-child
  [data-testid="stNumberInput"] {
  padding-left: 20px !important;
  padding-right: 20px !important;
}

/* ── Typography tokens ── */
.mc-left  { height: 0; margin: 0; padding: 0; display: block; }
.mc-pad   { padding: 18px 22px 12px; }
.mc-title {
  font-size: 1.18rem; font-weight: 800; color: #0f172a; line-height: 1.25;
  margin: 0 0 .3rem; letter-spacing: -.2px;
  font-family: 'Space Grotesk', sans-serif;
}
.mc-desc  { font-size: .76rem; color: #94a3b8; line-height: 1.6; margin: 0; }
.mc-sep   { border: none; border-top: 1px solid rgba(0,0,0,0.07); margin: 10px 0; }
.mc-lbl   { font-size: .65rem; font-weight: 700; letter-spacing: .12em;
            text-transform: uppercase; color: #94a3b8; margin-bottom: 6px; }

/* ── Form labels ── */
section.main label, section.main [data-testid="stWidgetLabel"] p {
  font-size: .75rem !important; font-weight: 600 !important; color: #374151 !important;
}
section.main [data-testid="stRadio"] > label {
  font-size: .74rem !important; font-weight: 600 !important; color: #374151 !important;
  margin-bottom: 4px !important;
}
section.main [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
  font-size: .74rem !important; color: #555 !important;
}
section.main [data-testid="stTextInput"] input {
  font-size: .8rem !important; border-radius: 8px !important;
}
section.main [data-testid="stNumberInput"] input {
  font-size: .8rem !important; border-radius: 8px !important;
}

/* ── Buttons ── */
section.main [data-testid="stButton"] > button {
  border-radius: 8px !important; font-size: .74rem !important; font-weight: 600 !important;
  border: 1px solid rgba(0,0,0,.1) !important;
  background: rgba(255,255,255,.8) !important;
  backdrop-filter: blur(8px) !important; transition: all .15s !important;
  padding: 6px 14px !important;
}
section.main [data-testid="stButton"] > button:hover {
  background: rgba(255,255,255,.97) !important; border-color: rgba(0,0,0,.18) !important;
}
section.main [data-testid="stButton"] > button[kind="primary"] {
  background: #0f172a !important; color: #fff !important; border-color: #0f172a !important;
}
section.main [data-testid="stButton"] > button[kind="primary"]:hover {
  background: #1e293b !important;
}
section.main [data-testid="stButton"] > button:disabled {
  opacity: .4 !important; cursor: not-allowed !important;
}

/* ── Plan output markdown ── */
.plan-output h2 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem; font-weight: 700; color: #0f172a;
  margin: 24px 0 10px; padding-bottom: 6px;
  border-bottom: 1px solid rgba(0,0,0,.07);
  letter-spacing: -.1px;
}
.plan-output h2:first-child { margin-top: 4px; }
.plan-output h3 {
  font-size: .85rem; font-weight: 700; color: #374151; margin: 14px 0 6px;
}
.plan-output p { font-size: .82rem; color: #374151; line-height: 1.7; margin: 0 0 8px; }
.plan-output ul, .plan-output ol {
  font-size: .82rem; color: #374151; line-height: 1.7;
  padding-left: 18px; margin: 4px 0 10px;
}
.plan-output li { margin-bottom: 3px; }
.plan-output strong { color: #1e293b; font-weight: 600; }
.plan-output code {
  background: rgba(0,0,0,.05); border-radius: 4px; padding: 1px 5px;
  font-size: .78rem;
}

/* ── Plan card wrapper ── */
.plan-card {
  background: rgba(255,255,255,.85);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-radius: 14px; padding: 22px 26px;
  border: 1px solid rgba(0,0,0,.07);
  box-shadow: 0 2px 16px rgba(0,0,0,.04);
}

/* ── Download/copy button ── */
.copy-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 16px; border-radius: 8px;
  background: rgba(255,255,255,.8); backdrop-filter: blur(8px);
  border: 1px solid rgba(0,0,0,.1); color: #374151;
  font-size: .72rem; font-weight: 600; cursor: pointer;
  transition: all .15s; font-family: Inter, sans-serif;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}
.copy-btn:hover { background: rgba(255,255,255,.97); border-color: rgba(0,0,0,.18); }
</style>
"""


def build_prompt(
    city: str,
    adults: int,
    children: int,
    special: list,
    budget: str,
    housing: str,
    risks: list,
    day11_gaps: str,
) -> str:
    household = f"{adults} adult{'s' if adults != 1 else ''}"
    if children:
        household += f" and {children} child{'ren' if children != 1 else ''}"
    special_str = ", ".join(special) if special else "none"
    risks_str = ", ".join(risks) if risks else "general emergencies"
    day11_note = (
        f"\n\nIMPORTANT: Their resilience audit flagged these as weak areas: {day11_gaps}. "
        "Weight the plan toward closing these specific gaps."
        if day11_gaps
        else ""
    )

    return f"""You are a senior emergency preparedness advisor. Generate a personalised, specific emergency plan.

HOUSEHOLD PROFILE:
- Location: {city}
- Household: {household}
- Housing: {housing}
- Budget: {budget}
- Special needs: {special_str}
- Primary risks: {risks_str}{day11_note}

Write a complete emergency preparedness plan with EXACTLY these 7 sections (use the exact headers shown):

## 🎒 72-Hour Emergency Kit
Specific items with quantities for {household}. Include approximate costs. Prioritise by importance. Note anything specific to their special needs: {special_str}.

## 💧 Water Plan
Calculate exact litres needed (4L/person/day minimum × 3 days). Recommend specific container types. Identify backup water sources relevant to {city}. Purification methods.

## 🍱 Food & Medication
Specific foods to stock with quantities for {household} × 14 days. Calorie targets. Storage tips. Medication/first-aid specifics for: {special_str}. Rotation schedule.

## 📡 Communication Plan
Step-by-step: who to call first, out-of-area contact, local emergency numbers for {city}. Two meeting points (near home + far from neighbourhood). Offline communication fallbacks.

## 🚗 Evacuation Plan
For {city}'s risks ({risks_str}): when to go vs shelter-in-place decision criteria. Grab-bag priorities for 90 seconds, 5 minutes, 15 minutes. Specific evacuation routes and destinations.

## 💰 Budget Breakdown ({budget})
Numbered priority list within their {budget} budget. Item name, quantity, estimated cost, where to buy. Running total. What to defer if budget is tight.

## ✅ 3 Actions This Week
Three concrete actions completable in 7 days. Each: action title, exactly what to do, time required, cost.

Rules: Be specific to {city} (real local numbers, known hazards, actual resources). No generic filler. Write as if for this exact household. Use bullet points, not paragraphs, for lists."""


def stream_plan(prompt: str):
    """Generator yielding text deltas from OpenRouter streaming response."""
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
                "max_tokens": 2800,
                "stream": True,
            },
            stream=True,
            timeout=90,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith(b"data: "):
                data = line[6:]
                if data == b"[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    pass
    except requests.HTTPError as e:
        yield f"\n\n⚠️ API error ({e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        yield f"\n\n⚠️ Generation failed: {e}"


def _render_plan(plan_text: str, city: str) -> None:
    if city:
        st.markdown(
            f'<div class="mc-lbl" style="margin-bottom:10px">'
            f'EMERGENCY PLAN — {city.upper()}'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="plan-card plan-output">', unsafe_allow_html=True)
    st.markdown(plan_text)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="margin-top:14px;display:flex;gap:8px">'
        '<button class="copy-btn" onclick="'
        "var t=document.querySelector('.plan-output')?.innerText||'';"
        "navigator.clipboard.writeText(t).then(function(){"
        "this.innerHTML='&#10003; Copied';var b=this;"
        "setTimeout(function(){b.innerHTML='&#9112; Copy plan text'},1500);"
        "}.bind(this))"
        '">&#9112; Copy plan text</button>'
        "</div>",
        unsafe_allow_html=True,
    )


def _placeholder() -> None:
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;min-height:65vh;gap:20px;padding:32px 20px;text-align:center">'
        '<div style="font-size:3.5rem;line-height:1">🛡️</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#1e293b;'
        'font-family:Space Grotesk,sans-serif;letter-spacing:-.2px">Your Emergency Plan</div>'
        '<div style="font-size:.8rem;color:#94a3b8;max-width:320px;line-height:1.65">'
        'Fill in your city, household, and budget on the left.<br>'
        'Claude generates a personalised plan in ~20 seconds.</div>'
        '<div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-top:4px">'
        + "".join(
            f'<div style="font-size:.7rem;color:#cbd5e1;display:flex;align-items:center;gap:5px">'
            f'<span>{icon}</span><span>{label}</span></div>'
            for icon, label in [
                ("🎒", "72-hr kit"),
                ("💧", "Water plan"),
                ("🍱", "Food & meds"),
                ("📡", "Comms plan"),
                ("🚗", "Evacuation"),
                ("💰", "Budget"),
                ("✅", "3 actions"),
            ]
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
        <div class="mc-header">
          <div class="mc-topline">
            <span class="mc-dot"></span>
            EMERGENCY PREP GENERATOR · DAY 12 · THE RESILIENCE STACK
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 2.55], gap="small")

    # ── Left: form ─────────────────────────────────────────────────────────────
    with left:
        st.markdown('<span class="mc-left"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mc-pad">'
            '<h2 class="mc-title">Emergency Preparedness Generator</h2>'
            '<p class="mc-desc">Your city · your household · your budget.<br>'
            'A personalised plan in about 20 seconds.</p>'
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

        housing = st.radio(
            "Housing type",
            ["Apartment / flat", "House with garden", "Rural / farm", "Vehicle or boat"],
            key="housing",
        )

        budget = st.radio(
            "Preparedness budget",
            ["Under $50", "$50–$150", "$150–$350", "$350–$750", "$750+"],
            index=1,
            key="budget",
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
            help="Paste your lowest-scoring dimensions from the Resilience Audit "
                 "to focus this plan on your biggest gaps.",
        )

        st.markdown('<hr class="mc-sep" style="margin:10px 20px">', unsafe_allow_html=True)

        st.markdown('<div style="padding:0 20px 28px">', unsafe_allow_html=True)
        gen = st.button(
            "Generate my plan →",
            type="primary",
            use_container_width=True,
            disabled=not city.strip(),
            key="gen",
        )
        if not city.strip():
            st.markdown(
                '<div style="font-size:.68rem;color:#94a3b8;text-align:center;margin-top:4px">'
                'Enter your city to enable</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Right: plan ─────────────────────────────────────────────────────────────
    with right:
        if gen:
            if not OPENROUTER_KEY:
                st.error(
                    "OPENROUTER_API_KEY not set. "
                    "Add it to your `.env` file and restart the app."
                )
            else:
                prompt = build_prompt(
                    city=city.strip(),
                    adults=int(adults),
                    children=int(children),
                    special=special,
                    budget=budget,
                    housing=housing,
                    risks=risks,
                    day11_gaps=day11_gaps.strip(),
                )
                st.markdown(
                    f'<div class="mc-lbl" style="margin-bottom:10px">'
                    f'EMERGENCY PLAN — {city.upper()}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="plan-card plan-output">', unsafe_allow_html=True)
                plan_text = st.write_stream(stream_plan(prompt))
                st.markdown("</div>", unsafe_allow_html=True)

                st.session_state["plan"] = plan_text
                st.session_state["plan_city"] = city.strip()

                st.markdown(
                    '<div style="margin-top:14px;display:flex;gap:8px">'
                    '<button class="copy-btn" onclick="'
                    "var t=document.querySelector('.plan-output')?.innerText||'';"
                    "navigator.clipboard.writeText(t).then(function(){"
                    "this.innerHTML='&#10003; Copied';var b=this;"
                    "setTimeout(function(){b.innerHTML='&#9112; Copy plan text'},1500);"
                    "}.bind(this))"
                    '">&#9112; Copy plan text</button>'
                    "</div>",
                    unsafe_allow_html=True,
                )

        elif st.session_state.get("plan"):
            _render_plan(
                st.session_state["plan"],
                st.session_state.get("plan_city", ""),
            )

        else:
            _placeholder()


if __name__ == "__main__":
    main()
