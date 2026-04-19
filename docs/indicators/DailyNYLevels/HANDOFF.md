# Handoff — IDE Entry Point

**Purpose:** Ground truth for any Claude instance or developer picking up work on this system. Read this first before editing anything.

---

## 1. Who / What / Why

**Owner:** Niharika (trading handle `vveerappa` on TradingView).
**Project:** Coherent visual system for Pine Script v6 and NinjaScript chart indicators and strategies.
**Not in scope:** Next.js dashboard and web surfaces. Those are a different paradigm (React, Tailwind, web browser) and aren't addressed by any document in this folder.

**Goal:** establish a single source of truth for how every indicator renders visual elements, so that:
1. A given concept (e.g., "London session high") looks the same across all indicators
2. Indicators are small — most logic lives in shared libraries
3. Cross-platform Pine and NT8 ports share the same design, differing only where the platform forces it
4. Adding a new indicator is "bind to templates" not "write drawing code"

---

## 2. Document hierarchy

Read in this order when first orienting:

1. **`README.md`** (this folder's top level) — overview and folder map
2. **`VISUAL_SYSTEM.md`** — base layer: palette, typography, geometry, theme, display profile, state modifiers, render pipeline, lifecycle state machine, library splits, governance
3. **`VISUAL_TEMPLATES.md`** — the catalog. Every canonical template documented. Every indicator binds to these. This is the longest document and the most-consulted one.
4. **`LIBRARY_ARCHITECTURE.md`** — physical library structure, tier split, layer responsibilities, Pine vs NT8 mapping, migration plan
5. **`INDICATORS/README.md`** — workflow for designing new indicators, profile template
6. **`INDICATORS/{indicator}.md`** — per-indicator profiles (currently only `daily_ny_levels.md` is drafted)
7. **`STRATEGIES/`** — currently empty; for future NT8 strategy profiles

### 2.1 Relationship

```
VISUAL_SYSTEM.md (base layer)
      │
      ├── VISUAL_TEMPLATES.md (catalog, uses base layer)
      │         │
      │         ├── INDICATORS/*.md (bind to templates)
      │         │
      │         └── STRATEGIES/*.md (bind to templates)
      │
      └── LIBRARY_ARCHITECTURE.md (implements base layer + catalog)
```

---

## 3. Current state (as of initial draft)

### 3.1 What exists

- Full set of design documents (this folder)
- One published Pine library: `vveerappa/PineDrawingLib/4` — thin and predates this architecture. Considered legacy.
- Business-logic libraries published: `RangeSessionLib/6`, `StatsLib/2` — referenced for computation but outside the drawing system's scope.
- Six reference Pine indicators (source shared during design) — not yet migrated to the new architecture:
  - Daily NY Levels v6
  - MFE Tracker (Pine 4.1)
  - MacroDealerLevels
  - Probability Engine v5
  - Daily Profiler
  - Candle Science Engine v17.5
  - Daily Expected Move
- Research pipeline (`ROOT/scripts/edgeful/`) with parquet outputs — produces data consumed by the Edgeful Macros indicator (planned).

### 3.2 What doesn't exist yet

- `PineDrawingCore v3` — not published
- Any of the `PineDrawing{Family}` libraries — not published
- Any of the NT8 libraries — not started (zero existing NT8 code)
- Migrated versions of any indicator — all indicators still use direct primitive calls

### 3.3 Starting points for future work

**If migrating the first indicator:**
1. Publish `PineDrawingCore v3` first (it's a dependency of everything else)
2. Then publish `PineDrawingHorizontalLevels v3` and `PineDrawingZones v3` and `PineDrawingTables v3`
3. Then migrate Daily NY Levels to v7 following `INDICATORS/daily_ny_levels.md` bindings and `LIBRARY_ARCHITECTURE.md §8` migration steps

**If starting NT8 work:**
1. Re-read `LIBRARY_ARCHITECTURE.md §5` (NT8 namespace structure + known limitations)
2. Acknowledge: this side is "design target, not yet validated" — expect to discover platform constraints that require adjusting the spec
3. Start with `NtDrawingLib.Core` (primitives + lifecycle), then `HorizontalLevels`
4. Choose the simplest indicator for the first port (probably a strategy with session levels + trade markers)

**If adding a new template to the catalog:**
1. Check if an existing canonical template + variant fits (`VISUAL_TEMPLATES.md`)
2. If not, check if an indicator-contributed template fits (`§10`)
3. If still nothing fits, follow the graduation process in `§11`
4. Document the new template following the schema in `§1.1`

---

## 4. Key architectural decisions (locked)

These decisions survived multiple rounds of design discussion and should not be re-opened without strong new evidence:

| Decision | Rationale |
|----------|-----------|
| P/S/C tier vocabulary (Primary/Secondary/Context) | Standard emphasis levels, applied uniformly across all templates |
| Two-dimensional template catalog (category × family) with variants | Scales better than one-dimensional enum; keeps related concepts grouped |
| Canonical vs indicator-contributed templates | Allows experimentation without compromising canonical stability |
| No inline overrides on canonical templates | Prevents visual drift across indicators |
| Template label formatting via format strings with `{if:slot}...{endif}` | Canonical templates control formatting; indicators supply data |
| Tooltips in scope, per-template `label_mode` | Supports rich hover content without cluttering the chart |
| Monospace default for numeric labels | Readability in tables and statistical displays |
| Three-tier palette (core + semantic UI + session) | Simple indicators use core only; dashboards opt into semantic UI |
| WCAG contrast validation for all (token, theme) pairs | Visibility on both dark and light charts |
| Display profile (Tiny/Small/Normal/Large/Huge) | Handles small laptops to large TV setups with one knob |
| Five table genres | stats / narrative / hit_rate / distribution / outcome — each distinct enough to warrant its own template |
| Library split into Core + family + specialized | Forced by Pine's ~50K line library cap; incidentally improves per-indicator import size |
| Four-state lifecycle (forming/finalized/historical/expired) with per-template retention | Supports use case A: displaying current + N sessions of historical elements simultaneously |
| Historical label suffix `[-Nd]` automatic | Zero indicator effort; consistent across templates |
| Pine v6 primary, NT8 flagged as design target | Pine has existing code to validate against; NT8 starts fresh |
| Hit-tracking infrastructure OUT of scope | Separate module; templates just flag `hit_trackable` |
| Play-window / session visual start/end IN scope (as lifecycle) | Addresses recurring pain point; one-and-done at system level |
| Data-driven labels via Approach A (format strings) | Template owns formatting; simple; avoids needing to specify behavior per-template |
| Direct Unicode glyphs in format strings (not named tokens) | Simpler; glyphs render the same across themes |

---

## 5. What NOT to do

- Don't add direct `line.new`, `box.new`, `label.new`, `table.new`, `Draw.Line`, `Draw.Rectangle`, `Draw.Text`, etc. calls in indicator code. Use Layer E (semantic renderers) always.
- Don't override canonical template styling inline. Pick a tier/variant/direction, or contribute a new template.
- Don't define your own color palette in an indicator. Use `f_resolve_color(token, theme)`.
- Don't hardcode `size.small` or `size.large` in an indicator. Use the display profile.
- Don't ignore `historical_retention`. If an element shouldn't show historical, declare `historical_retention: 0` in the binding.
- Don't treat canonical templates as suggestions. They're contracts.

---

## 6. What to watch for during drafting

When writing new docs or editing existing ones:

- Every color token referenced must exist in `VISUAL_SYSTEM.md §2`
- Every template referenced must exist in `VISUAL_TEMPLATES.md`
- Every library referenced must exist in `LIBRARY_ARCHITECTURE.md §3`
- Every override in an indicator profile needs justification in its §5 Overrides section
- Breaking changes to the template catalog require a major version bump of the affected family library
- Palette changes require WCAG re-validation
- New canonical templates require two-indicator adoption proof before graduation

---

## 7. Known gaps and future work

### 7.1 Still-pending indicator profiles

Seven indicators have business descriptions but no formal profile yet. Priority order matches migration priority:

1. Daily NY Levels (drafted)
2. MFE Tracker
3. Candle Science Engine (because it introduces projected_candle template use)
4. MacroDealerLevels (because it introduces specialized GEX/DEX variants)
5. Probability Engine
6. Daily Profiler
7. Daily Expected Move
8. Edgeful Macros (research-stage)

### 7.2 Strategy profiles

Four NT8 strategies are on Niharika's roadmap:
- VWAP reclaim/rejection
- Initial Balance breakout/pullback
- EMA pullback continuation
- Failed auction / single-print fill

None have NT8 code yet. When work begins, each gets a `STRATEGIES/{name}.md` profile.

### 7.3 Hit-tracking infrastructure

Templates that flag `hit_trackable` need a companion module to actually track hits. This is planned but not designed yet. See `VISUAL_SYSTEM.md §1` ("What's NOT in this document") — hit tracking is explicitly out of scope for the visual system.

### 7.4 Live decision engine

Niharika has designed a pre-session batch job that consumes regime state, GEX/DEX levels, and strategy conditions to emit a daily playbook. If this ever renders chart annotations (entry zones, target bands, stop-loss lines), it'll consume the template catalog like any other indicator. Profile to be created when that work resumes.

---

## 8. How to update this handoff

Whenever a significant decision changes or a new document is added:
1. Update the "Current state" section (§3) with what now exists
2. Update "Key architectural decisions" (§4) if a locked decision is revised
3. Update "Known gaps" (§7) as work progresses

Keep this document short enough that it can be read in 5 minutes. It's the quickest possible way to get oriented.

---

## 9. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial handoff. Covers locked decisions, current state, priority indicator profiles, known gaps, pointers to all documents. |
