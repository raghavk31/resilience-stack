# TODOS

## Shared streaming utility

**What:** Extract the shared OpenRouter SSE streaming function into a common `utils.py` module.

**Why:** Days 10, 11, and 12 each reimplement the same `requests.post` + SSE parsing loop independently. A streaming bug (e.g., malformed chunk handling, timeout tweak) must currently be fixed in 3 files.

**Pros:** Bug fixes apply once. Future days import instead of copying. Easier to add retry logic, logging, or model fallback in one place.

**Cons:** Adds a module dependency between daily files — currently each day is self-contained. Requires updating 3 existing files.

**Context:** The pattern is identical across `day10_polycrisis.py`, `day11_resilience_audit.py`, `day12_emergency_prep.py`. The function name varies slightly per day but the structure is the same: `requests.post` to OpenRouter, `stream=True`, SSE line parsing, `[DONE]` sentinel, `except` catches for HTTPError and Exception.

**Depends on:** Nothing — can be done any time. Suggest doing it before Day 15 while the pattern is still fresh.
