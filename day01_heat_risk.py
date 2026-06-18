"""
Day 1 — Heat Risk Communicator
30 Days of Climate Code

Input:  neighbourhood + city in India
Output: plain-language heat risk, who is most vulnerable, 3 actions to take

Usage:
    python day01_heat_risk.py "Koramangala" "Bengaluru"
    python day01_heat_risk.py "Dharavi" "Mumbai"

Streamlit:
    streamlit run day01_heat_risk.py
"""

import os
import sys
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


# ---------- data layer ----------

def geocode(neighbourhood: str, city: str) -> tuple[float, float]:
    """Return (lat, lon) for a neighbourhood in an Indian city."""
    for query in [f"{neighbourhood}, {city}, India", f"{city}, India"]:
        resp = requests.get(GEOCODING_URL, params={"name": query, "count": 1, "language": "en"}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results")
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    raise ValueError(f"Could not geocode: {neighbourhood}, {city}")


def get_forecast(lat: float, lon: float) -> dict:
    """Fetch 7-day forecast with heat-relevant variables from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
        ],
        "timezone": "Asia/Kolkata",
        "forecast_days": 7,
    }
    resp = requests.get(WEATHER_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def heat_risk_level(forecast: dict) -> str:
    peak = max(forecast["daily"]["apparent_temperature_max"])
    if peak >= 47:   return "EXTREME"
    if peak >= 43:   return "VERY HIGH"
    if peak >= 40:   return "HIGH"
    if peak >= 35:   return "MODERATE"
    return "LOW"


# ---------- AI layer ----------

def call_claude(prompt: str) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/climate-30",
            "X-Title": "30 Days of Climate Code",
        },
        json={
            "model": "anthropic/claude-opus-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def build_prompt(neighbourhood: str, city: str, forecast: dict, risk: str) -> str:
    daily = forecast["daily"]
    rows = []
    for i, date in enumerate(daily["time"]):
        rows.append(
            f"  {date}: {daily['temperature_2m_max'][i]:.0f}°C max "
            f"(feels like {daily['apparent_temperature_max'][i]:.0f}°C), "
            f"rain {daily['precipitation_sum'][i]:.0f}mm"
        )
    weather_block = "\n".join(rows)

    return f"""You are a climate health communicator helping residents of Indian cities understand heat risk in plain language.

LOCATION: {neighbourhood}, {city}
HEAT RISK THIS WEEK: {risk}

FORECAST (next 7 days):
{weather_block}

Write a heat risk brief for residents. Structure it exactly like this:

HEAT RISK: {risk}

[2–3 sentences explaining what this heat actually feels like and what it means day-to-day. No jargon. Concrete.]

WHO IS MOST AT RISK:
[2–3 sentences. Name specific groups likely present in this neighbourhood — outdoor workers, construction labour, the elderly, children, people without AC. Explain why heat hits them harder.]

WHAT YOU CAN DO THIS WEEK:
1. [Specific, actionable. Time of day matters. e.g. "Don't go outside between 11am–4pm"]
2. [Specific, actionable. Something about hydration, shelter, or helping a neighbour]
3. [Specific, actionable. One thing that costs nothing]

Keep the tone warm and direct. This is for real people making daily decisions."""


# ---------- entry points ----------

def run_cli(neighbourhood: str, city: str):
    print(f"\nLooking up {neighbourhood}, {city}...", flush=True)
    lat, lon = geocode(neighbourhood, city)
    forecast = get_forecast(lat, lon)
    risk = heat_risk_level(forecast)
    prompt = build_prompt(neighbourhood, city, forecast, risk)

    print("Generating heat risk brief...\n")
    result = call_claude(prompt)
    print(result)
    print(f"\n─────────────────────────────────────────")
    print(f"Weather data: Open-Meteo  |  AI: Claude via OpenRouter")
    print(f"Coordinates: {lat:.4f}°N, {lon:.4f}°E")


def run_streamlit():
    import streamlit as st

    st.set_page_config(page_title="Heat Risk Communicator", page_icon="🌡️")
    st.title("🌡️ Heat Risk Communicator")
    st.caption("Day 1 of 30 Days of Climate Code — for Indian cities")

    col1, col2 = st.columns(2)
    with col1:
        neighbourhood = st.text_input("Neighbourhood", placeholder="e.g. Koramangala")
    with col2:
        city = st.text_input("City", placeholder="e.g. Bengaluru")

    if st.button("Check heat risk", type="primary"):
        if not neighbourhood or not city:
            st.warning("Please enter both a neighbourhood and city.")
        elif not OPENROUTER_API_KEY:
            st.error("OPENROUTER_API_KEY not found in .env")
        else:
            with st.spinner(f"Fetching forecast for {neighbourhood}, {city}..."):
                try:
                    lat, lon = geocode(neighbourhood, city)
                    forecast = get_forecast(lat, lon)
                    risk = heat_risk_level(forecast)
                    prompt = build_prompt(neighbourhood, city, forecast, risk)
                except ValueError as e:
                    st.error(str(e))
                    st.stop()
                except requests.RequestException as e:
                    st.error(f"Network error: {e}")
                    st.stop()

            with st.spinner("Generating brief..."):
                result = call_claude(prompt)

            risk_colors = {
                "EXTREME": "🔴", "VERY HIGH": "🟠", "HIGH": "🟡",
                "MODERATE": "🟢", "LOW": "🟢"
            }
            st.markdown(f"### {risk_colors.get(risk, '⚪')} {risk} heat risk")
            st.markdown(result)
            st.caption(f"📍 {lat:.4f}°N, {lon:.4f}°E · Weather: Open-Meteo · AI: Claude")


# detect whether we're running under Streamlit or plain Python
if "__streamlit__" in dir() or any("streamlit" in arg for arg in sys.argv):
    run_streamlit()
elif __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heat risk communicator for Indian cities")
    parser.add_argument("neighbourhood", help='e.g. "Koramangala"')
    parser.add_argument("city", help='e.g. "Bengaluru"')
    args = parser.parse_args()

    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    run_cli(args.neighbourhood, args.city)
