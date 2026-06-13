# TODOS

## Green contrast backport (Days 12–13)

**What:** Replace `#16a34a` with `#15803d` for all green-coloured text in `day12_emergency_prep.py` and `day13_crop_advisor.py` CSS blocks.

**Why:** `#16a34a` on white = 3.18:1 contrast ratio, failing WCAG AA (requires 4.5:1 for body text). `#15803d` = 4.59:1, passes. Affects category badges, chip labels, and any green text on white surfaces.

**Pros:** Full product passes WCAG AA contrast. One-line fix per usage.

**Cons:** Marginally darker green on labels — visually imperceptible difference.

**Context:** Caught during Act II design review (Jun 2026). Act II days already specify `#15803d` for text. Backport completes the fix across all existing days before the Day 29 platform CSS consolidation.

**Depends on:** Nothing. Do before Day 29 platform shell.



## Shared streaming utility

**What:** Extract the shared OpenRouter SSE streaming function into a common `utils.py` module.

**Why:** Days 10, 11, and 12 each reimplement the same `requests.post` + SSE parsing loop independently. A streaming bug (e.g., malformed chunk handling, timeout tweak) must currently be fixed in 3 files.

**Pros:** Bug fixes apply once. Future days import instead of copying. Easier to add retry logic, logging, or model fallback in one place.

**Cons:** Adds a module dependency between daily files — currently each day is self-contained. Requires updating 3 existing files.

**Context:** The pattern is identical across `day10_polycrisis.py`, `day11_resilience_audit.py`, `day12_emergency_prep.py`. The function name varies slightly per day but the structure is the same: `requests.post` to OpenRouter, `stream=True`, SSE line parsing, `[DONE]` sentinel, `except` catches for HTTPError and Exception.

**Depends on:** Nothing — can be done any time. Suggest doing it before Day 15 while the pattern is still fresh.
