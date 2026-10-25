# Resilience Stack — Act II Plan: Community Tools (Days 14–20)

**Branch:** master  
**Status:** Drafting (Day 13 complete, Day 14 next)  
**Goal:** Shift from data visualisation to personalised tools that help individuals and communities take action.

---

## What Act II Is

Act I (Days 1–10) built global climate intelligence maps. Act II builds tools that help a specific person in a specific place make a real decision. The user changes from "researcher viewing global data" to "smallholder farmer, homeowner, or community organiser solving a local problem."

---

## Day 14 — Off-Grid Independence Calculator

**Goal:** Given location + household size + budget, show what a complete off-grid system looks like and what it costs.

**Data sources:** Day 02 solar GHI data, World Bank electricity price API, user inputs.

**User flow (rough):**
1. Location input (city/country)
2. Household size selector
3. Budget slider (USD, 3 tiers)
4. System components: solar panels, battery storage, water collection, food self-sufficiency
5. Output: system spec + cost breakdown + years to payback

**Output type:** Calculator with visual summary card. No AI streaming — synchronous calculation.

---

## Day 15 — Water Security Planner

**Goal:** Input location → get a personalised rainwater harvesting + greywater recycling plan.

**Data sources:** Open-Meteo climate precipitation data, user inputs (roof area, household size).

**User flow:**
1. Location + roof area + household size
2. Calculate monthly rainfall capture
3. Greywater recycling potential
4. Output: "Your household can cover X% of water needs"

**Output type:** Form → results card. Similar pattern to Day 14.

---

## Day 16 — Urban Heat Relief Mapper

**Goal:** Show local green spaces + community-submitted cool spots on a map. First UGC feature.

**Data sources:** OpenStreetMap parks/green spaces, Supabase for community-submitted spots.

**User flow:**
1. City search → map loads with green spaces + cool spots
2. User can click "Add a cool spot" → submit name + address + type (library, pool, shade structure)
3. Community-submitted spots show with different pin style

**Output type:** Interactive map (Folium/Leaflet). Supabase write. First community feature.

---

## Day 17 — Food Forest Designer

**Goal:** Climate-appropriate permaculture planting plan for a specific location and land size.

**Data sources:** Day 03 water stress, Day 05 heat data, crop data from Day 13.

**User flow:**
1. Location + land area (m²/acres) + climate zone
2. AI generates a layered food forest planting plan (canopy/understory/ground cover/root/vine/fungi)
3. Plant list with spacing, water needs, harvest timeline
4. Downloadable/shareable plan

**Output type:** AI streaming output (same pattern as Day 12/13). Rich formatted plan.

---

## Day 18 — Climate Finance Finder

**Goal:** Search for grants, subsidies, carbon credits, and green loans by country + sector.

**Data sources:** Curated dataset (static CSV or Airtable). No live API.

**User flow:**
1. Country selector + sector checkboxes (solar, water, agriculture, housing)
2. Filter results table
3. Click program → full details + application link

**Output type:** Search/filter UI. No AI generation. Static data display.

---

## Day 19 — Community Resilience Score

**Goal:** Neighbourhood-level self-assessment comparing to city and national averages.

**Data sources:** User inputs + Day 10 Polycrisis national scores as benchmarks.

**User flow:**
1. Location + 12-question assessment (energy, water, food, health, community cohesion)
2. Score calculation
3. Radar chart: "Your neighbourhood vs your city vs national average"
4. Top 3 recommendations

**Output type:** Questionnaire → radar chart + recommendation cards. No AI.

---

## Day 20 — The Action Map

**Goal:** Community-built global map of who's taking climate action (solar co-ops, community gardens, repair cafes, etc). Supabase-backed.

**Data sources:** Supabase (all UGC). User-submitted.

**User flow:**
1. Map loads with existing pins
2. "Add your action" → form: name, type, description, location, website
3. Moderation: basic spam filter + flagging
4. Browse/search existing actions by type

**Output type:** Interactive map + submission form. Full UGC CRUD. Supabase.

---

## Interaction States

| Feature | LOADING | EMPTY | ERROR | SUCCESS |
|---------|---------|-------|-------|---------|
| Day 14 — calculate | Spinner + "Calculating your system…" | "Enter your location and budget to see your off-grid system" (centered, with icon) | "Location not found — try a nearby city" | Metric cards animate in (stagger 80ms) |
| Day 15 — calculate | Spinner + "Fetching climate data…" | "Enter your location and roof size to see your water potential" | "No precipitation data for this area" | Water % bar fills with animation |
| Day 16 — map load | Skeleton shimmer on map area | **"Be the first to add a cool spot here!** This map grows with your community. Tap ＋ to add a shady cafe, library, or public pool." (centred over map, green CTA button) | "Map tiles failed to load. Tap to retry." | Green space pins + community pins animate in |
| Day 16 — cool spot submit | Button shows spinner, label "Submitting…" | — | "Couldn't save your spot — check your connection and try again" | "Your spot is on the map! ✓" toast + pin appears |
| Day 17 — AI plan | Streaming text (same as Day 12) | "Enter your location and land size to generate your food forest plan" | API error with retry button | Full plan rendered |
| Day 18 — search | Skeleton rows (3 rows) | **"No programs found for [country] + [sectors].** Try broader sectors or a neighbouring country. [See all programs →]" | "Search failed — try again" | Results table fades in |
| Day 19 — questionnaire | n/a | n/a | n/a | Radar chart animates in after Q12 |
| Day 20 — map load | Skeleton shimmer | **"Be the first to put your climate action on the map!** Every solar panel, community garden, and repair cafe counts. [Add my action →]" (green CTA, full map overlay) | "Map failed to load. Tap to retry." | Action pins cluster-animate in |
| Day 20 — action submit | Button spinner | — | "Submit failed — your draft is saved, try again" | "Your action is live! ✓" toast + pin zooms to location |

**Empty state design note:** Days 16 and 20 empty states are the product's activation moment. If a user lands on a blank map with no message, they assume it's broken. The empty state must feel like an invitation, not a failure.

## Cross-cutting concerns (all 7 days)

- All apps run as Streamlit on the same repo
- Consistent page header pattern (title + subtitle + "Day X" badge)
- Mobile: unknown — no responsive specs yet
- Error states: not specified per day
- Loading states: not specified
- Empty states for map/search tools: not specified
- Supabase schema for Days 16 + 20: not designed
- Moderation for UGC Days 16 + 20: not specified
- Shareable outputs: mentioned for Day 11, not re-stated
- No design system / component library
- No DESIGN.md

---

## Layout Architecture (locked)

Three distinct layout paradigms across Act II:

### Paradigm 1 — Two-panel (Days 14, 15, 17)
Mirrors Days 12–13. Form on left (fixed 340px, white glassmorphism), output on right (scrollable).
- Day 14: left = calculator inputs, right = system spec cards
- Day 15: left = location/roof/household inputs, right = water coverage summary + monthly table
- Day 17: left = location/area/climate inputs, right = AI streaming food forest plan

### Paradigm 2 — Full-screen map (Days 16, 20)
Map fills 100vh. Controls float over the map.
- Search bar: floating top-left overlay (white card, 320px wide, z-index over map)
- Pin detail: slides in from right on click (white card, 360px, semi-transparent)
- FAB: "Add spot / Add action" floating button, bottom-right, #16a34a green
- Day 16: two pin styles — OSM green spaces (filled circle) vs community cool spots (star/custom)
- Day 20: pin types by action category (solar=yellow, garden=green, repair=blue, other=gray)

### Paradigm 3 — Progressive questionnaire (Day 19)
One question at a time, full viewport focus.
- Screen = question number (1/12) + question text (large, Space Grotesk) + answer options
- Progress bar top (linear, green fill)
- "Next" button advances. Keyboard: Enter to advance.
- After Q12: score reveal screen — radar chart (you vs city vs national) + top 3 recommendations
- Hierarchy on score reveal: PRIMARY = radar chart, SECONDARY = score (X/100), TERTIARY = recommendations

### Information hierarchy per day
| Day | PRIMARY | SECONDARY | TERTIARY |
|-----|---------|-----------|----------|
| 14 | Result — "Your system covers X% at $Yk" | Calculator form | Component breakdown |
| 15 | Result — "You can capture X litres/month (Y%)" | Inputs | Monthly breakdown table |
| 16 | Map (full viewport) | Floating search bar | Pin detail panel |
| 17 | AI streaming plan (right) | Form (left) | Layer breakdown |
| 18 | Results table | Filter bar (country + sector) | Program detail |
| 19 | Current question (large, centered) | Progress bar | Score reveal after Q12 |
| 20 | Community map | FAB "Add action" | Browse/search sidebar |

## User Journey & Emotional Design

### Day 19 — Score framing (decided: relative + dimension)
No single total score. Instead:
- **Lead highlight:** "Your neighbourhood leads on Energy Independence" (green, top dimension)
- **Gap highlight:** "Water Security is your biggest opportunity (bottom 30% nationally)" (amber)
- Radar chart shows 6 dimensions vs city vs national — the comparison IS the insight
- Top 3 recommendations flow directly from the lowest-scoring dimensions
- No score out of 100. Framing is "where you stand" not "how you scored"

### Day 19 — After score reveal
Don't end at the chart. Offer: "Take this to your neighbours →" (copy link button) + "What can you do? → Day 15 Water Planner / Day 14 Off-Grid Calculator" (links to relevant tools based on weakest dimension)

### Day 20 — Submission confirmation moment (decided: rich)
After successful submit:
1. Map zooms smoothly to submitted pin (1.2s ease)
2. Confirmation overlay (small card, bottom-center): **"Your action is on the map! You're #N worldwide."**
3. Share prompt below count: "Show your community what you're doing" + [Copy link] [Share on WhatsApp] [Share on X]
4. Overlay auto-dismisses after 6s or on map click
5. Supabase query: `SELECT count(*) FROM actions` (cached, refreshed on submit)

## Responsive Behavior

| Day | Mobile (375px) |
|-----|----------------|
| 14, 15, 17 | Stack: inputs top, output scrolls below. Same glassmorphism surfaces, full-width. |
| 16, 20 | Map full-screen. Floating panel moves to bottom-sheet (slides up 50vh). FAB stays bottom-right. |
| 18 | Filter bar collapses to "Filters ▼" button → opens a bottom-sheet filter panel. Results stack as cards. |
| 19 | Same full-screen questionnaire. Chips stack vertically if needed. "Next" button pinned to bottom of viewport. |

## Accessibility Specs

- **Touch targets:** All interactive elements min 44×44px. `.rs-chip-option` min-height 44px (not 40px).
- **Keyboard — Day 19:** `Enter` advances to next question. `Arrow keys` navigate chip options. `Escape` exits early with score-so-far.
- **Map a11y (Days 16, 20):** "View as list" toggle in the floating panel — renders all pins as a scrollable accessible list. Required because maps are screen-reader hostile.
- **Color contrast (decided):** `#16a34a` (`--rs-green`) is for fills, borders, and large display text only (≥24px bold). All green-coloured body text and labels use `#15803d` (`--rs-green-dark`, ratio 4.59:1 on white ✓).
- **Form labels (Days 16, 20 submission):** Every field has a visible `<label>` above it. No placeholder-as-label pattern.

## Design System Tokens (Act II)

All Act II days inherit from the existing Day 12–13 implicit design system. Codify as CSS custom properties at the top of each day's `_CSS` block:

```css
--rs-green: #16a34a;
--rs-green-dark: #15803d;
--rs-green-faint: rgba(22,163,74,.08);
--rs-bg: #edf2ed;
--rs-surface: rgba(255,255,255,.94);
--rs-border: rgba(0,0,0,.07);
--rs-text: #0f172a;
--rs-text-muted: #94a3b8;
--rs-radius: 10px;
--rs-radius-lg: 16px;
--font-display: 'Space Grotesk', sans-serif;
--font-body: 'Inter', sans-serif;
```

### New components (Days 16–20 only)

**.rs-fab** — Floating action button (Days 16, 20)
- 52×52px circle, `var(--rs-green)` fill, white SVG icon
- Position: fixed bottom-right, 24px margin
- box-shadow: `0 4px 16px rgba(22,163,74,.35)`
- Label tooltip on hover: "Add a cool spot" / "Add your action"

**.rs-floating-panel** — Map overlay control (Days 16, 20)
- White glassmorphism (`backdrop-filter: blur(20px)`)
- 320px width, `var(--rs-radius-lg)` radius
- z-index: 1000, position: absolute top-left
- Contains: search input + filter chips

**.rs-chip-option** — Questionnaire answer chip (Day 19)
- Outlined default: `1.5px solid var(--rs-border)`, white bg, 40px min-height
- Active/selected: `var(--rs-green)` fill, white text
- Hover: `var(--rs-green-faint)` bg tint
- min-width: 120px, `var(--rs-radius)` radius

**.rs-submit-drawer** — UGC submission form (Days 16, 20)
- Desktop: slides in from right, 400px wide, full height
- Mobile: slides up from bottom, full width, 80vh height
- Glassmorphism surface, drag handle on mobile

## AI Slop Mitigations

**Day 14 output:** No 3-column metric card grid. Use horizontal summary strip (cost + payback + coverage%) at top, then vertical stack of component cards (solar, battery, water, food).

**Day 18 results:** No bare HTML table. Each grant program = card: program name (Space Grotesk bold) + country flag + sector badge + amount range + deadline. Same card surface language as Day 13 crop cards.

**Day 19 questionnaire:** Keep green background (not plain white). Answer options = styled button chips, not radio inputs. Question text = Space Grotesk 1.6rem. Progress bar = animated green fill.

## Resolved Design Decisions

| Decision | Resolution |
|----------|------------|
| UGC moderation (Days 16, 20) | Flag button + email notification. Schema: add `flagged bool default false` column to both `cool_spots` and `actions` tables. Supabase Edge Function sends email to raghav@perspectives.community on flag. User-side: small "🚩 Flag" button on each pin detail card. |
| Day 19 persistence | Persist + share. Supabase table: `scores(id uuid primary key default gen_random_uuid(), responses jsonb, location text, created_at timestamptz default now())`. Share URL: `?score={id}`. On load with `score` param: fetch from Supabase and render result directly (skip questionnaire). |
| Day 20 confirmation | Rich: map zoom + submission count + share prompt (see User Journey section). |
| Day 19 score framing | Relative + dimension (no single score out of 100). See User Journey section. |
| Layout paradigms | Three locked: two-panel (14/15/17), full-screen map (16/20), progressive questionnaire (19). |
| Green text contrast | `#16a34a` for fills only. `#15803d` for all green text. |

## Deferred (Open) Questions

- **Day 18 data source:** Static CSV (fast to ship, harder to maintain) vs Airtable (maintainable, needs API key). Decision deferred to Day 18 build. Minimum viable: 20 programs across 10 countries covering solar, water, agriculture, housing.
- **Day 17 shareable plan:** Download as PDF or copy-to-clipboard text. Decision deferred — implement copy first (same as Day 12 plan), add PDF later if time allows.
- **Day 14/15 location → climate data wiring:** Needs confirmation that Open-Meteo climate API provides sufficient data for the calculator formulas. Validate on Day 14 build day.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above.

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — Layout — Implement full-screen map layout for Day 16 and Day 20
  - Surfaced by: Pass 1 (Information Architecture) — map-in-a-column loses all value
  - Files: `day16_heat_mapper.py`, `day20_action_map.py`
  - Verify: Map fills 100vh; floating panel overlays correctly on both desktop and mobile

- [ ] **T2 (P1, human: ~30min / CC: ~5min)** — Layout — Implement progressive questionnaire layout for Day 19
  - Surfaced by: Pass 1 — questionnaire in a two-panel feels like a government form
  - Files: `day19_resilience_score.py`
  - Verify: One question visible at a time, Space Grotesk 1.6rem, progress bar animates

- [ ] **T3 (P1, human: ~2h / CC: ~15min)** — Empty states — Design and implement Day 16+20 community invitation empty states
  - Surfaced by: Pass 2 — blank map on first load looks broken, kills activation
  - Files: `day16_heat_mapper.py`, `day20_action_map.py`
  - Verify: Empty map shows invitation copy with green CTA button, not a blank tile set

- [ ] **T4 (P1, human: ~2h / CC: ~20min)** — UGC — Add `flagged` column + Supabase Edge Function for Days 16+20
  - Surfaced by: Pass 7 — moderation decision: flag button + email notification
  - Files: `supabase_setup.sql`, `day16_heat_mapper.py`, `day20_action_map.py`
  - Verify: 🚩 button appears on pin detail; flagging sends email to raghav@perspectives.community

- [ ] **T5 (P1, human: ~2h / CC: ~15min)** — Day 19 — Add Supabase persistence + share URL
  - Surfaced by: Pass 7 — ephemeral score kills sharing potential
  - Files: `day19_resilience_score.py`, `supabase_setup.sql`
  - Verify: `?score=uuid` in URL rerenders result without re-answering; copy link button works

- [ ] **T6 (P1, human: ~1h / CC: ~10min)** — Day 20 — Implement rich confirmation (zoom + count + share)
  - Surfaced by: Pass 3 — submission confirmation is the belonging moment; toast alone misses it
  - Files: `day20_action_map.py`
  - Verify: Map zooms to pin; "You're #N worldwide" counter shows; share prompt appears

- [ ] **T7 (P2, human: ~30min / CC: ~5min)** — Design tokens — Add CSS custom properties to each Act II day
  - Surfaced by: Pass 5 — no shared tokens, 7 days will drift
  - Files: All `day14` through `day20` `.py` files
  - Verify: `--rs-green`, `--rs-green-dark`, `--font-display` etc. defined at top of each `_CSS` block

- [ ] **T8 (P2, human: ~30min / CC: ~5min)** — Accessibility — Fix `#16a34a` text contrast in Act II days
  - Surfaced by: Pass 6 — 3.18:1 fails WCAG AA; use `#15803d` for all green text
  - Files: All `day14` through `day20` `.py` files
  - Verify: No `color: #16a34a` on text elements; only fills and borders use this value

- [ ] **T9 (P2, human: ~1h / CC: ~10min)** — Accessibility — Add "View as list" toggle to Day 16+20 maps
  - Surfaced by: Pass 6 — maps are screen-reader hostile; list fallback required
  - Files: `day16_heat_mapper.py`, `day20_action_map.py`
  - Verify: "View as list" button in floating panel renders accessible scrollable list of pins

- [ ] **T10 (P2, human: ~20min / CC: ~3min)** — Day 18 — Results as cards, not table
  - Surfaced by: Pass 4 — bare HTML table looks like a government grants database
  - Files: `day18_finance_finder.py`
  - Verify: Each program renders as a card with name/country/sector-badge/amount/deadline

- [ ] **T11 (P3, human: ~1h / CC: ~10min)** — CSS — Backport contrast fix to Days 12–13
  - Surfaced by: Pass 6 — `#16a34a` text in existing days also fails contrast
  - Files: `day12_emergency_prep.py`, `day13_crop_advisor.py`
  - Verify: All green text uses `#15803d`; tracked in TODOS.md

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | ISSUES_RESOLVED | score: 3/10 → 8/10, 6 decisions made |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 3 deferred (Day 18 data source, Day 17 share format, Day 14/15 climate API wiring) — all implementation-level, none blocking design.

**VERDICT:** Design Review CLEARED — 6 design decisions made, 11 implementation tasks generated. Eng review required before shipping Act II.

NO UNRESOLVED DECISIONS
