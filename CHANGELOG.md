# Changelog

All notable changes to the Resilience Stack are documented here.

Format: `## [VERSION] - YYYY-MM-DD`

## [0.12.0.0] - 2026-06-04

### Added
- **Day 11 → Day 12 integration:** Day 11 Resilience Audit now writes weakest dimensions to `.resilience_gaps.json`; Day 12 Emergency Prep Generator reads that file on load and pre-fills the "Weak areas" field automatically — real cross-day integration instead of manual copy-paste
- **Unit tests for `build_prompt()`:** 8 pytest cases covering adults-only, adults+children, empty/populated special needs, day11_gaps present/absent, and input sanitisation — first test coverage in the project
- **Input sanitisation in `build_prompt()`:** newlines stripped and city truncated to 120 chars before LLM prompt interpolation to prevent prompt injection

### Changed
- **`max_tokens` raised from 2 800 to 4 000:** reduces truncation risk for large households (4+ adults, multiple special needs)
- **Truncation detection:** streaming loop now captures `finish_reason`; if `"length"`, a user-visible note is appended to the plan
- **Copy button HTML deduplicated:** extracted into `_COPY_BTN_HTML` module constant — single source of truth used by both the live-streaming path and the session-state re-render path

### Fixed
- **Error strings no longer saved as plans:** `st.session_state["plan"]` is now only written when `plan_text` is non-None and does not start with `⚠️` — prevents error messages appearing styled as emergency plans on page reload
