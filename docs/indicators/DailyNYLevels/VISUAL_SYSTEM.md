# Visual System

**Version:** 4.0
**Scope:** Base visual layer for chart indicators and strategies (Pine Script v6 + NinjaScript).
**Out of scope:** Next.js dashboard and web surfaces (separate paradigm).
**Parent for:** `VISUAL_TEMPLATES.md`, `LIBRARY_ARCHITECTURE.md`, `INDICATORS/*.md`, `STRATEGIES/*.md`.

---

## 1. Purpose

This document defines the **base visual layer** — everything that indicators and strategies share but should never define for themselves. Specifically:

- **Palette** — the complete set of named colors available to the system
- **Typography** — text sizing, fonts, anchor rules
- **Geometry** — line widths, transparencies, padding, gaps
- **Theme resolver** — how a color token resolves to a concrete color under Dark / Light / Custom themes
- **Display profile** — how sizes scale for different physical display setups (Tiny through Huge)
- **State modifiers** — how element state (active, inactive, suppressed, etc.) affects rendering
- **Render pipeline** — the canonical sequence of steps every indicator follows
- **Lifecycle state machine** — how elements transition from forming through expired
- **Governance** — versioning and deprecation rules

What's **not** in this document:

- Specific template definitions (that's `VISUAL_TEMPLATES.md`)
- Library implementation (that's `LIBRARY_ARCHITECTURE.md`)
- Per-indicator element bindings (that's `INDICATORS/*.md`)
- Hit-tracking infrastructure (separate module, not yet documented)

### 1.1 Design principles

The system follows five principles:

- **Single source of truth.** Every visual value has exactly one definition. If it's wrong, it's wrong in one place, fix it in one place.
- **Templates own styling, indicators own semantics.** Indicators describe what they're drawing; templates describe how it's drawn.
- **Profile-scaled, theme-aware.** A display profile and theme are chart-wide inputs. Every sizing and color token responds to them automatically.
- **Canonical first.** Templates in the canonical catalog are stable contracts. Indicator-specific templates are the escape hatch, not the norm.
- **Contrast-validated.** Every (color, theme) pair is verified for adequate contrast on its intended background. No guessing.

---

## 2. Palette

The palette is organized into three tiers. Every indicator uses the core tier. Indicators with narrative dashboards or status displays also use the semantic UI tier. Indicators rendering session concepts use the session tier.

### 2.1 Core palette

Always available. Used by every template category.

| Token | Role | Dark value | Light value | Notes |
|-------|------|------------|-------------|-------|
| `bull` | Positive direction | `#38BD8A` | `#008060` | Green; primary bull color |
| `bear` | Negative direction | `#F87171` | `#B3261E` | Red; primary bear color |
| `neutral` | No direction | `#94A3B8` | `#6B7280` | Gray |
| `positive` | Positive state (non-directional) | `#86EFAC` | `#16A34A` | Lighter green; for "good" states |
| `negative` | Negative state (non-directional) | `#FCA5A5` | `#B91C1C` | Lighter red; for "bad" states |
| `caution` | Warning without alarm | `#FB923C` | `#C2410C` | Orange |
| `confirm` | Confirmation, success | `#2DD4BF` | `#0D9488` | Teal |
| `warning` | Alert, requires attention | `#F97316` | `#C2410C` | Orange, distinct from caution |
| `median` | Statistical median | `#FACC15` | `#CA8A04` | Amber/yellow (same hue family both themes) |
| `average` | Statistical mean | `#22D3EE` | `#0891B2` | Cyan |
| `stretch` | Extreme statistical value (P90+) | `#FB923C` | `#C2410C` | Orange |
| `pivot_color` | Structural pivot | `#60A5FA` | `#2563EB` | Blue (distinct from average cyan) |
| `invalidation` | Thesis-ending level | `#F87171` | `#B3261E` | Same as bear; invalidation is inherently bearish of current thesis |
| `max_reversal` | Max adverse excursion | `#FCA5A5` | `#DC2626` | Coral/red (distinct from stretch orange) |

**Contrast validation:** All Dark values pass WCAG AA (3:1 minimum) against `#131722`. All Light values pass WCAG AA against `#FFFFFF`. Text tokens (where labels render) pass AA for text (4.5:1 minimum).

### 2.2 Semantic UI palette

Used by narrative dashboards, status tables, hit-rate tables, and outcome tables. Indicators that only draw chart elements (no dashboard surface) don't reference these.

| Token | Role | Dark value | Light value |
|-------|------|------------|-------------|
| `bg_primary` | Primary background | `#0F172A` | `#F8FAFC` |
| `bg_secondary` | Secondary background (cells) | `#1E293B` | `#FFFFFF` |
| `bg_border` | Table and cell borders | `#334155` | `#94A3B8` |
| `text_primary` | Primary foreground text | `#F1F5F9` | `#0F172A` |
| `text_secondary` | Secondary text | `#CBD5E1` | `#475569` |
| `text_dim` | De-emphasized text | `#94A3B8` | `#78716C` |
| `header_bg` | Table header row background | `#1E3A8A` | `#BFDBFE` |
| `header_text` | Table header row text | `#E2E8F0` | `#111827` |
| `validated_bg` | Confirmed / hit state background | `#166534` | `#DCFCE7` |
| `validated_text` | Confirmed / hit state text | `#DCFCE7` | `#166534` |
| `pending_bg` | Awaiting resolution background | `#92400E` | `#FEF3C7` |
| `pending_text` | Awaiting resolution text | `#FEF3C7` | `#92400E` |
| `skip_bg` | Skip / avoid state background | `#7F1D1D` | `#FEE2E2` |
| `skip_text` | Skip / avoid state text | `#FECACA` | `#991B1B` |

### 2.3 Session palette

Used by session-based templates (session ranges, session-anchored levels, session-specific dashboards).

| Token | Role | Dark value | Light value |
|-------|------|------------|-------------|
| `asia` | Asia session | `#3B82F6` | `#1D4ED8` |
| `london` | London session | `#EF4444` | `#B91C1C` |
| `ny` | NY session (morning / primary) | `#10B981` | `#047857` |
| `ny2` | NY session (afternoon) | `#8B5CF6` | `#6D28D9` |
| `p12` | P12 window (18:00-06:00 range) | `#FACC15` | `#CA8A04` |
| `prev_day` | Previous trading day | `#9CA3AF` | `#6B7280` |
| `settlement` | Futures settlement / prior close | `#FB923C` | `#C2410C` |
| `overnight` | Overnight / Globex session | `#F59E0B` | `#D97706` |

**Contrast validation:** all session colors pass WCAG AA against their respective theme backgrounds.

### 2.4 Theme resolver

Color resolution follows this function, available through `PineDrawingCore`:

```pine
f_resolve_color(string token, string theme_mode) =>
    // theme_mode: "Dark" | "Light" | "Custom"
    // returns the concrete color for this token under the active theme
```

When `theme_mode == "Custom"`, the user's input color passes through unchanged. When `"Dark"` or `"Light"`, the palette value for that theme is used.

Resolution happens once per render cycle in the indicator. All drawing calls in that cycle consume the resolved color, not the token.

---

## 3. Typography

### 3.1 Size tokens

Pine and NT8 both support five size levels. They map one-to-one:

| Token | Pine | NT8 (point size) |
|-------|------|------------------|
| `tiny` | `size.tiny` | 8 |
| `small` | `size.small` | 10 |
| `normal` | `size.normal` | 12 |
| `large` | `size.large` | 14 |
| `huge` | `size.huge` | 16 |

### 3.2 Font family

Templates declare `label_font` as one of:

- `monospace` — for labels containing numeric data (prices, percentages, counters). Aligns digits visually, improves table readability. This is the default for any template where numeric content appears.
- `proportional` — for pure-text labels (section titles, status tags). Uses default chart font.

Override: indicators can override `label_font` per-binding if a specific instance needs different typography, though this is discouraged for canonical templates (see `VISUAL_TEMPLATES.md §1.5`).

### 3.3 Label anchor rules

Labels anchor to their element with a convention based on position:

| Label position | Label style | Arrow direction |
|----------------|-------------|-----------------|
| Right of element (most horizontal lines, right-edge labels) | `style_label_left` | Arrow points left, back at element |
| Left of element | `style_label_right` | Arrow points right, back at element |
| Above element | `style_label_down` | Arrow points down, at element |
| Below element | `style_label_up` | Arrow points up, at element |
| Centered inside element (in-zone labels) | `style_none` | No arrow |
| Dense session level labels (many on screen) | `style_none` | No arrow (reduces clutter) |

Rule of thumb: **when density is low, use arrows; when density is high, use `style_none`.** Canonical templates declare their intended label style.

### 3.4 Text color

Label text color defaults to the element's own color (a green bull line gets a green label). Exception: in narrative dashboards and status tables, label text uses `text_primary` or `text_dim` per the cell's semantic meaning.

### 3.5 Profile-scaled typography

Label size scales with the display profile (see §5). The template declares its intended "baseline" size at the `Normal` profile; the resolver scales up or down.

---

## 4. Geometry

### 4.1 Priority-tier widths

The priority-tier system (P / S / C) drives line width and line style defaults. Every template declares what each tier means for it, but the baseline widths are:

| Tier | Width (at Normal profile) | Intended style |
|------|---------------------------|-----------------|
| P (Primary) | 2 | Solid |
| S (Secondary) | 1 | Dashed |
| C (Context) | 1 | Dotted |

Templates may override the tier-to-style mapping (e.g., `activation_trigger` uses dotted at P for breakout, dashed at S for pullback). Widths remain consistent across templates.

### 4.2 Transparency levels

Standard transparency tokens for consistent visual weight:

| Token | Value | Use |
|-------|-------|-----|
| `transparency_opaque` | 0 | Full color, no transparency |
| `transparency_slight` | 15 | Very subtle fade for background lines |
| `transparency_subtle` | 30 | Standard fade for secondary lines |
| `transparency_medium` | 50 | Clear fade for context lines and zone borders |
| `transparency_zone` | 75 | Zone fill default — visible but doesn't obscure price |
| `transparency_background` | 90 | Background elements that shouldn't compete |
| `transparency_invisible` | 100 | Hidden |

### 4.3 Spacing and extension

| Token | Default | Use |
|-------|---------|-----|
| `right_extend_bars` | 20 | How far horizontal lines extend past current bar |
| `label_gap_bars` | 8 | Horizontal gap between line end and its right-edge label |
| `label_offset_bars` | 2 | Default column offset for staggered labels |
| `column_step_bars` | 2 | Horizontal step between label collision columns |
| `line_length_bars` | 6 | Default short-line length for reference markers |

### 4.4 Label merge threshold

Label merging requires a vertical-proximity threshold. Because tick sizes vary wildly across instruments (ES = 0.25, CL = 0.01, GC = 0.1), the threshold is instrument-aware:

| Instrument class | Merge threshold (ticks) |
|------------------|-------------------------|
| ES / MES | 20 |
| NQ / MNQ | 40 |
| YM / MYM | 20 |
| RTY / M2K | 10 |
| CL / MCL | 10 |
| GC / MGC | 15 |
| Default (anything else) | 20 |

The library provides `f_merge_threshold_for_symbol(symbol, mintick) → float price_distance`. Indicators never hardcode a tick count.

### 4.5 Label collision strategies

Labels near each other in Y space can collide visually. Two strategies are supported, declared per-template:

- **`merge`** — overlapping labels combine into one: `"Avg 0.32% | Median 0.30%"`. Useful when the labels describe siblings that happen to coincide.
- **`stagger`** — overlapping labels distribute into offset columns. Useful when labels describe different things that happen to be near each other. More readable at scale.
- **`hide`** — when overflow, hide labels that would overlap. Simple fallback.
- **`off`** — no collision handling; labels render at their natural position regardless.

Default: `stagger`. Statistical-sibling templates (`statistical_level_median` and `statistical_level_avg` together) use `merge` since their semantic is "these are sibling statistics."

---

## 5. Display profile

The display profile is a chart-wide input scaling size and weight for the physical display being used. One input, applied uniformly across all templates.

### 5.1 Profile values

| Profile | Label size | Width multiplier | Transparency delta |
|---------|-----------|------------------|---------------------|
| `Tiny` | `tiny` | 0.75× (rounds to 1) | +5 (lighter) |
| `Small` | `small` | 0.85× (rounds to 1) | +5 |
| `Normal` | `small` (baseline) | 1.0× | 0 |
| `Large` | `normal` | 1.25× | -5 |
| `Huge` | `large` | 1.5× | -10 (more opaque) |

**Default:** `Normal`.

Rationale for matching Pine's `size.*` names: you're already familiar with them, they map naturally to the label size enum, and they describe what you actually see on screen rather than abstract concepts like "compact / standard / large."

### 5.2 Profile application rules

- **Label size:** profile sets the global label size. Templates that need distinct sizing (e.g., section titles being larger than stat labels) scale relative to profile baseline.
- **Line widths:** profile multiplier applies to all P/S/C widths. Rounded to nearest integer, minimum 1.
- **Transparency:** profile delta adds to base transparency. `transparency_zone` at Normal is 75; at Huge it's 65 (more opaque, more visible at distance).
- **Table text:** follows the profile for all body text. Headers scale one step up.
- **Debug elements:** exempt from profile scaling; always use their own fixed size (usually `tiny`).

### 5.3 Profile as chart input

Every indicator exposes the profile as a single input in a `grp_display` group:

```
grp_display = "Display"
i_display_profile = input.string("Normal", "Display Profile",
                                  options=["Tiny", "Small", "Normal", "Large", "Huge"],
                                  group=grp_display)
```

The library provides `f_display_profile_scale(token, profile) → value` to resolve any size/width/transparency token under the active profile.

---

## 6. State modifiers

Every rendered element carries a **state** that modulates its visual emphasis. The library applies state modifiers automatically when the indicator declares state on a binding.

### 6.1 State vocabulary

| State | Meaning | Default visual treatment |
|-------|---------|--------------------------|
| `active` | Primary focus, current thesis | Base style; no modification |
| `inactive` | Visible but de-emphasized | +40 transparency, -1 width (minimum 1) |
| `suppressed` | Hidden due to collision or priority | Not drawn |
| `merged` | Represented by a combined label/aggregate | Line drawn, label suppressed (handled by merge logic) |
| `debug` | Debug-only element | Drawn but with `transparency_background`; never competes with production elements |
| `historical_1d` | One session back | +30 transparency; label gets `[-1d]` suffix |
| `historical_2d` | Two sessions back | +45 transparency; label gets `[-2d]` suffix |
| `historical_Nd` | N sessions back | +45 transparency (cap); label gets `[-Nd]` suffix |
| `expired` | Retention exceeded | Not drawn; registry entry cleared |

### 6.2 Adaptive states

Some templates have mode-switching driven by runtime conditions (e.g., Candle Science's high zone switches between MFE and MAE modes based on probability threshold). The `adaptive` state extension allows templates to declare:

```yaml
adaptive_mode:
  condition: "probability >= 50"
  true_state: active
  false_state: inverted       # swaps color family, adjusts semantic
```

The indicator provides the probability; the template determines which rendering applies.

### 6.3 Regime-driven state (optional)

Indicators with regime classification (PINNED, TRENDING, COILED, BATTLE_ZONE) can declare state mappings in their profile:

```yaml
regime_state_map:
  PINNED:
    expected_move_band: active
    activation_trigger: inactive
  TRENDING:
    activation_trigger: active
    reversal_target_zone: inactive
```

Not required; purely indicator-level opt-in.

---

## 7. Render pipeline

Every indicator follows this canonical sequence per render cycle:

```
1. Compute
   Derive business values from RangeSessionLib, StatsLib, request.security,
   or other computation helpers.

2. Resolve
   Call f_resolve_color() for each color token.
   Call f_display_profile_scale() for each size/width/transparency token.
   Cache resolved values in local variables.

3. Register labels
   For each element to render, append to a shared LabelRegistry if the
   template participates in label merging/staggering.

4. Suppress and merge
   Apply collision rules. Tactical overrides context. Same-priority elements
   at same Y merge per template's label_collision strategy.

5. Draw
   Invoke semantic renderer for each element. The library issues primitive
   calls through the lifecycle manager, which tags each draw object.

6. Flush registry
   Render the final label set from the registry after merge/stagger
   decisions are complete.

7. Reconcile (NT8)
   On NT8, the lifecycle manager mutates in-place when style and geometry
   match existing tags, avoiding flicker.
   On Pine, reconcile degenerates to delete-and-recreate; the registry
   still tracks tags for selective clearing.
```

### 7.1 Current implementation status (Unified)

The indicator now uses a library-owned unified label registry flow in Pine:

- Indicator code registers labels through `f_label_registry_push(...)` in `PineDrawingLib`.
- Label merge-on-proximity and final draw emission are handled by `f_label_registry_draw_merged(...)` in the library.
- Local indicator merge loops are removed from the active code path.

This preserves existing merge-threshold semantics while moving ownership from indicator code into the shared drawing layer.

---

## 8. Lifecycle state machine

Every element has a lifecycle governed by a four-state machine.

### 8.1 State diagram

```
         element created
              │
              ▼
         ┌────────┐
         │ forming│  ── element evolving during its active window
         └────┬───┘     (session in progress, range still expanding,
              │          threshold not yet met)
              │
              │  completion event
              │  (session close, window end, threshold hit)
              ▼
         ┌─────────┐
         │finalized│  ── current session's completed element;
         └────┬────┘     primary focus
              │
              │  next session produces its own finalized
              ▼
         ┌──────────┐
         │historical│  ── prior session's element, kept for context
         └────┬─────┘     per template's historical_retention setting
              │
              │  retention count exceeded
              ▼
         ┌────────┐
         │ expired│  ── removed from display; registry cleared
         └────────┘
```

### 8.2 Historical retention

Every template declares its default historical retention. Indicators can override per-binding.

Default retention values by family:

| Template family | Default retention |
|-----------------|-------------------|
| Session levels (session_level_*) | 1 (yesterday's still contextually useful) |
| Previous-period levels | 0 (they already roll; retaining historical doubles up) |
| FVG / Order Block zones | Unlimited until mitigated/filled |
| Invalidation / activation lines | 0 (only current thesis matters) |
| Statistical distribution lines | 0 (stats are rolling) |
| Trade markers (entry, exit) | Unlimited (trade history value) |
| Debug elements | 0 |

### 8.3 Historical styling

When an element transitions to `historical_1d`, `historical_2d`, etc., the library applies:

- Transparency delta per state (see §6.1)
- Label suffix: `[-1d]`, `[-2d]`, `[-Nd]`
- Optional width reduction (template-specific)

The indicator author never manually manages historical rendering. The indicator just creates new instances; the library handles state transitions based on retention policy and age.

### 8.4 Pine implementation note

Pine re-runs the script from bar 1 on every bar. State is computed at render time by comparing instance age (in sessions or bars) to the current bar. This means replay and backtesting work naturally: at any historical bar, the indicator reflects what it knew at that bar, and state machine transitions happen in their natural order.

### 8.5 NT8 implementation note

NT8 is event-driven. State transitions fire on bar close events or session close events. The lifecycle manager tracks element age in sessions; when a new session's finalized element appears, prior elements transition to historical with the registry updating in place.

---

## 9. Library splits

Pine Script enforces a line-count limit per library (~50,000 compiled lines) and indicators pay a per-import cost. A monolithic drawing library would consume too much budget for simple indicators and leave no headroom for expansion.

The drawing system is split into tiers:

### 9.1 Core tier — `PineDrawingCore`

Required by every indicator. Contains:

- Lifecycle manager (draw registry, tag convention, cleanup)
- Style resolver (theme + display profile)
- Primitives (line, box, label, table, polyline, linefill, vline)
- Label registry (merge, stagger, collision resolution)
- Helpers (`f_theme_color`, `f_near_any`, `f_display_profile_scale`, `f_merge_threshold_for_symbol`, format-string interpreter with `{if:slot}...{endif}` support)

Estimated size: 2,000-3,000 lines.

### 9.2 Family tier — per element family

Indicators import only what they use:

- `PineDrawingHorizontalLevels` — all line-family templates
- `PineDrawingZones` — all zone-family templates
- `PineDrawingMarkers` — all point-marker templates
- `PineDrawingVerticalMarkers` — vertical time markers
- `PineDrawingTables` — all five table genres
- `PineDrawingComposites` — projected_candle, prediction_box, price_model_trajectory, synthetic multi-primitive compositions

Each family library: 1,500-3,000 lines.

### 9.3 Specialized tier — `PineDrawingSpecialized`

Indicator-contributed templates with narrow domain use:

- GEX/DEX wall family (MacroDealerLevels)
- Scored level family (MacroDealerLevels W/A/I)
- Probability-annotated level variants (Probability Engine)
- Any other contributed template with fewer than 2 canonical adopters

Indicators import this only if they use these specialized templates.

### 9.4 NT8 equivalent

The NinjaScript implementation follows the same tiering pattern but as C# namespaces rather than separate libraries:

- `NtDrawingLib.Core`
- `NtDrawingLib.HorizontalLevels`
- `NtDrawingLib.Zones`
- `NtDrawingLib.Markers`
- `NtDrawingLib.Tables`
- `NtDrawingLib.Composites`
- `NtDrawingLib.Specialized`

NT8 doesn't have Pine's library size limit; the split is purely for code organization.

---

## 10. Governance

### 10.1 Versioning

Each library follows semantic versioning (`major.minor.patch`). TradingView publishes Pine libraries by integer version, so the public `PineDrawing{Family}/{N}` number aligns with the major version.

- **Major:** breaking API change (rename, remove, signature change)
- **Minor:** additive (new template, new helper, new composite)
- **Patch:** bug fix, no API change

### 10.2 Breaking changes

- Deprecate for one minor cycle with `// @deprecated` annotation and migration note
- Remove in the next major version

### 10.3 Palette changes

Any change to a color token in the palette requires:

- WCAG contrast re-validation against both theme backgrounds
- Visual regression check on at least two reference indicators
- Minor version bump (color shifts are additive-visible, not structurally breaking)

### 10.4 Template changes (canonical)

Canonical template changes follow stricter rules. See `VISUAL_TEMPLATES.md §10` for the full governance policy on template evolution.

### 10.5 Review gate

No new indicator ships with direct drawing API calls. Code review rejects any `line.new`, `box.new`, `label.new`, `linefill.new`, `polyline.new`, `Draw.Line`, `Draw.Rectangle`, `Draw.Text` outside of the Core tier's primitives layer.

Documented exceptions require justification in the indicator profile's Overrides section. See `INDICATORS/README.md §5` for the exception discipline.

---

## 11. Glossary

- **Template** — a named, pre-styled preset that indicators bind to. Defines all visual properties for a class of elements. See `VISUAL_TEMPLATES.md`.
- **Category** — one of: line, zone, marker, vertical_marker, label, table, fill, composite, debug. Every template has exactly one category.
- **Family** — the semantic grouping within a category (e.g., `wall`, `flip`, `magnet`, `session_level`, `expected_move`). A category has many families.
- **Tier** — P (Primary), S (Secondary), C (Context). Orthogonal emphasis modulator.
- **Variant** — optional template sub-type (e.g., `line_wall` has variants `standard`, `whale`, `macro`, `golden_sweep`).
- **Direction** — for directional templates: `bull` / `bear`, `call` / `put`, `up` / `down`, or `neutral`.
- **Instance key** — a stable identifier for a specific element occurrence (e.g., `"london_high_2026_04_18"`). Indicators define these.
- **State** — runtime element state (`active`, `inactive`, `suppressed`, `merged`, `debug`, `historical_Nd`, `expired`).
- **Profile** — display profile (`Tiny` / `Small` / `Normal` / `Large` / `Huge`), scales sizes globally.
- **Theme** — color theme (`Dark` / `Light` / `Custom`), selects palette values.

---

## 12. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial spec (Daily NY Levels focused) |
| 2.0 | 2026-04-18 | Multi-indicator, cross-platform rendering architecture |
| 3.0 | 2026-04-18 | Full rewrite. Base-layer only. Adds three-tier palette, display profile, four-state lifecycle, library splits, contrast validation. Template catalog moved to VISUAL_TEMPLATES.md. |
| 3.1 | 2026-04-18 | Phase 2 label-registry extraction in Pine (`f_label_registry_push`, `f_label_registry_draw_merged`). |
| 4.0 | 2026-04-20 | Unified Architecture: Removed "Phase" nomenclature. Unified Phase 1 & Phase 2 into a singular viewpoint with shared drawing ownership. |
