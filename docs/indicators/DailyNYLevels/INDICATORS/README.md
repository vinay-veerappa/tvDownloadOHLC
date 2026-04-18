# Indicator Profiles

**Scope:** Workflow for designing new indicators under the visual system, and the reference template for per-indicator profile documents.

**Parent:** `VISUAL_SYSTEM.md`, `VISUAL_TEMPLATES.md`, `LIBRARY_ARCHITECTURE.md`
**Siblings:** each `INDICATORS/{indicator_name}.md`

---

## 1. Purpose

This folder holds one profile document per indicator. Profiles describe:

- What the indicator does (business purpose)
- Every visual element it renders, bound to canonical templates from `VISUAL_TEMPLATES.md`
- Runtime data slots each binding supplies
- Lifecycle and state overrides (if any)
- Libraries imported
- Known overrides and exceptions to canonical rules (must be justified)

Profiles are the **indicator's contract with the visual system**. They describe what the indicator needs in template-catalog terms, not how it computes values.

### 1.1 What profiles are NOT

- Not implementation docs — no Pine or C# code
- Not user docs — no "how to use this indicator"
- Not strategy docs — strategies go in `STRATEGIES/`
- Not the indicator itself — the `.pine` file is separate, and this profile just describes its visual surface

---

## 2. Workflow for a new indicator

When designing a new indicator or porting an existing one, follow this sequence:

### Step 1 — Write the business description
Describe what the indicator does in prose. What does it compute? What problem does it solve for the trader? What's the domain (session profiling, macro windows, options flow, etc.)?

### Step 2 — Enumerate every visual element
List every thing that appears on the chart or in a panel: lines, zones, markers, vertical markers, tables, composites, debug overlays. Group by family. Be exhaustive — every pixel you intend to render must be listed.

### Step 3 — Bind each element to a canonical template
For each element, find the canonical template in `VISUAL_TEMPLATES.md` that best fits. Pick the tier (P/S/C), variant (if applicable), direction (if directional). If no canonical template fits, flag it for discussion — it's either a new variant, a new canonical template, or an indicator-contributed template.

### Step 4 — Enumerate runtime data slots
For each binding, list what runtime data the indicator supplies to the template's label format string. `{session_name}`, `{probability}`, `{hit_rate}`, etc. Reference the template's `data_slots` and supply only those (or document the template needs expansion).

### Step 5 — Declare lifecycle & retention
Default retention per template is respected unless the indicator overrides. If the indicator needs different retention (e.g., "I want 5 sessions of Asia highs visible, not 1"), declare that in the binding and justify.

### Step 6 — Declare label_mode per binding if different from default
If the binding needs `Label`, `Tooltip`, `Both`, or `None` different from the template's `label_mode_default`, declare it. Otherwise omit.

### Step 7 — List libraries imported
Identify the libraries needed based on the template categories used. Core is always required; add family libraries for each category bound.

### Step 8 — Overrides section
List any deviations from canonical template policy. These require justification. Examples of legitimate overrides:
- "This indicator needs a third sub-tier; P/S/C isn't sufficient, so I'm using `line_priority_P` at two different contexts with distinct color bindings." (Contribute a new template? Or accept as escape hatch.)
- "I need to render this FVG with a different color scheme than canonical because of the specific market regime it represents." (Probably means contributing a `fvg_bull_variant_regime` template.)

Illegitimate overrides:
- "I want this line blue because I like blue." (No — use the template's palette binding.)
- "I want this label to read differently." (No — supply different runtime data, or contribute a new template.)

### Step 9 — Table positioning & display
Declare table default positions (top_right, bottom_left, etc.) so conflicts with other indicators are visible.

### Step 10 — Migration status
If this indicator exists today in pre-system form, describe migration state: `Not migrated | In progress | Migrated | Legacy (will retire)`.

---

## 3. Profile document template

Every `INDICATORS/{name}.md` follows this structure:

```markdown
# Indicator: {Indicator Name}

**Version:** {semantic version, or N/A if unreleased}
**Platform:** Pine v6 | NinjaScript | Both
**Migration status:** Not migrated | In progress | Migrated | Legacy
**Libraries:** PineDrawingCore, PineDrawing{families used}
**Symbol scope:** ES, NQ, YM, RTY, ... | All | {specific}

---

## 1. Business description

{What the indicator does, what it computes, who it's for}

## 2. Inputs

{List input groups and key inputs — including the display profile and theme inputs that every indicator now has}

## 3. Element bindings

For each element, specify:
- Canonical template (from VISUAL_TEMPLATES.md)
- Tier (P / S / C)
- Variant (if applicable)
- Direction (if applicable)
- Instance key pattern
- Runtime data slots supplied
- Lifecycle overrides (if any)
- Label_mode override (if any)

### 3.1 {Family name — e.g., Session levels}
### 3.2 {Next family}
... etc.

## 4. Tables

For each table rendered:
- Genre (from VISUAL_TEMPLATES §9)
- Default position
- Content description

## 5. Overrides & exceptions

{Any deviation from canonical rules, with justification}

## 6. Notes

{Anything else relevant — known issues, design intent, future plans}
```

---

## 4. Profile index

Indicators currently documented:

| Indicator | Status | Profile document |
|-----------|--------|------------------|
| Daily NY Levels | Pending migration | [`daily_ny_levels.md`](daily_ny_levels.md) |
| MFE Tracker (Pine v4.1) | Pending migration | `mfe_tracker.md` (not yet drafted; subset of Daily NY Levels) |
| MacroDealerLevels | Pending migration | `macro_dealer_levels.md` (not yet drafted) |
| Probability Engine (v5) | Pending migration | `probability_engine.md` (not yet drafted) |
| Daily Profiler | Pending migration | `daily_profiler.md` (not yet drafted) |
| Candle Science Engine (v17.5) | Pending migration | `candle_science.md` (not yet drafted) |
| Daily Expected Move | Pending migration | `daily_expected_move.md` (not yet drafted) |
| Edgeful Macros (research) | In planning | `edgeful_macros.md` (not yet drafted) |

Drafts will be added as each indicator is migrated or as design stabilizes.

---

## 5. Override discipline

The template system is strict on purpose. Overrides exist to handle genuine edge cases, not to express preferences. Every override in an indicator profile needs:

- **Justification:** why the canonical template doesn't work
- **Alternative considered:** what you tried from the canonical catalog first
- **Graduation path:** if this is reusable, note it as a candidate for contribution

Reviewers flag overrides without justification. The goal is to catch "I didn't read the catalog carefully" early and steer toward the right canonical template.

---

## 6. Cross-indicator consistency

Because templates are canonical, the same concept renders the same way across all indicators:

- Asia session highs look the same in Daily Profiler, Probability Engine, and Daily NY Levels
- Invalidation lines look the same regardless of which indicator drew them
- Stats tables use the same fonts, colors, and layout everywhere
- Display profile affects every indicator simultaneously when the user changes it

This is the whole point. If an indicator has a session-high that looks different from other indicators' session-highs, something is wrong. Either the template needs updating, or the indicator is overriding when it shouldn't be.

---

## 7. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial README. Workflow, profile template, index. |
