# Library Architecture

**Version:** 3.0
**Scope:** Library structure, layering, split plan, and platform specifics for Pine v6 and NinjaScript.
**Parent:** `VISUAL_SYSTEM.md`, `VISUAL_TEMPLATES.md`

---

## 1. Purpose

This document describes **how the drawing system is physically structured as libraries** and how indicators consume them. It covers:

- The five-layer model (what belongs where)
- Library split plan (Core + Family + Specialized tiers)
- Current state of the Pine libraries (v2 published) vs target state
- NT8 namespace plan (design target, not yet validated against existing code)
- Platform differences and known limitations
- Migration plan for moving the reference indicator (Daily NY Levels) onto the new architecture

---

## 2. Five-layer model

Every drawing operation passes through five logical layers. Each layer has a clear responsibility. Indicators and strategies consume the top layer; they never bypass it.

```
┌──────────────────────────────────────────────────────────────┐
│ Indicator / Strategy code                                     │
│ (declares WHAT to draw: templates + bindings + runtime data)  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Layer E — Semantic renderers                                  │
│ (one function per template: session_level_high, wall_level,   │
│  projected_candle, etc.)                                      │
│ Lives in: PineDrawingHorizontalLevels, PineDrawingZones, ...  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Layer D — Label registry                                      │
│ (collision resolution, merge, stagger, format string render)  │
│ Lives in: PineDrawingCore                                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Layer C — Primitives                                          │
│ (line, box, label, table, polyline, linefill, vline)          │
│ Lives in: PineDrawingCore                                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Layer B — Style resolver                                      │
│ (theme + display profile → concrete values)                   │
│ Lives in: PineDrawingCore                                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Layer A — Lifecycle manager                                   │
│ (draw registry, tag convention, state tracking, cleanup)      │
│ Lives in: PineDrawingCore                                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  Platform drawing API
                  (Pine line.new, box.new, etc. or
                   NT8 Draw.Line, Draw.Rectangle, etc.)
```

### 2.1 Layer responsibilities

**Layer A — Lifecycle manager.** Owns the draw registry. Every drawn object gets a stable tag. When the indicator re-renders, the manager reconciles: create new, update changed, delete removed, transition between lifecycle states (forming → finalized → historical → expired). On NT8, mutates in place when possible to avoid flicker. On Pine, reconciles through delete-and-recreate since Pine objects are immutable once created beyond their basic setters.

**Layer B — Style resolver.** Takes abstract tokens (`bull`, `median`, `transparency_zone`, `P-tier width`) and resolves them to concrete values under the current theme and display profile. Cached per render cycle.

**Layer C — Primitives.** Thin wrappers around the platform's drawing API. Every drawing call goes through these; no indicator code invokes `line.new` or `Draw.Line` directly. Primitives are: `line`, `box`, `label`, `table`, `polyline`, `linefill`, `vline`. Each primitive accepts already-resolved values (concrete colors, widths, sizes) and a tag from the lifecycle manager.

**Layer D — Label registry.** Handles label collision. Indicators call `f_register_label(tag, x, y, format_string, runtime_data)`. The registry:
- Parses the format string and substitutes runtime data
- Compares positions across all registered labels in this cycle
- Applies merge / stagger / hide rules per the label's collision strategy
- Emits the final positioned labels to Layer C during flush

**Layer E — Semantic renderers.** One function per template. `f_draw_session_level_high(instance_key, tier, price, time_range, runtime_data)` — called by the indicator, internally orchestrates Layers D → C → B → A. This is the primary consumer-facing API.

### 2.2 What crosses layer boundaries

Indicators only talk to Layer E (semantic renderers). Rare exception: the generic `line_priority_P/S/C` templates expose low-level styling because they are explicitly escape hatches. Even there, the indicator still goes through a semantic renderer — the renderer just accepts more parameters.

The format-string interpreter and `f_resolve_color` / `f_display_profile_scale` helpers in Layer B are exposed as utilities and occasionally called directly by indicators that need to pre-compute values (e.g., building table cell text). These crossings are fine — they don't bypass lifecycle, they just pre-compute.

---

## 3. Library split plan

Pine Script enforces a ~50,000-line cap per library and charges a per-import cost. A single monolithic drawing library is not viable.

The system splits into three tiers.

### 3.1 Core tier — `PineDrawingCore`

**Status:** Not yet published. Target for v3.
**Estimated size:** 2,000-3,000 compiled lines.
**Required by:** every indicator and strategy that uses the drawing system.

Contents:

- Layer A: lifecycle manager, draw registry, tag convention, state tracking, cleanup routines, historical state transitions, retention policy enforcement
- Layer B: style resolver (`f_resolve_color`, `f_display_profile_scale`, `f_merge_threshold_for_symbol`)
- Layer C: primitives — `f_draw_line`, `f_draw_box`, `f_draw_label`, `f_draw_table_cell`, `f_draw_polyline`, `f_draw_linefill`, `f_draw_vline`
- Layer D: label registry (`f_register_label`, `f_flush_labels`, `f_merge_labels`, `f_stagger_labels`), format-string interpreter
- Helpers: `f_near_any`, `f_unicode_bar`, `f_unicode_sparkline`, `f_unicode_progress`
- Utility types: `DrawInstance`, `LabelEntry`, `LifecycleState` enum, `DisplayProfile` enum, `Theme` enum

### 3.2 Family tier

Each family library contains only the semantic renderers for its category. Indicators import only what they use.

#### `PineDrawingHorizontalLevels`

**Status:** Not yet published.
**Estimated size:** 2,500-3,500 lines.
**Contents:** every `line` category template from `VISUAL_TEMPLATES.md §2-§3`.

Functions exposed:
- `f_draw_line_priority_P/S/C(...)`
- `f_draw_statistical_level_median/avg/pN(...)`
- `f_draw_stretch_level(...)`, `f_draw_max_excursion_level(...)`
- `f_draw_invalidation_level(...)`, `f_draw_activation_trigger(...)`, `f_draw_confirm_level(...)`, `f_draw_pivot_structural(...)`
- `f_draw_target_level_p20/p50/p75(...)`
- `f_draw_session_level_high/low/mid(...)`, `f_draw_session_open_level(...)`
- `f_draw_previous_period_level(...)`, `f_draw_settlement_level(...)`
- `f_draw_anchored_level(...)`, `f_draw_anchored_level_with_offsets(...)`, `f_draw_reference_level(...)`
- `f_draw_zero_gamma_level(...)`, `f_draw_gamma_flip_level(...)`, `f_draw_gamma_cliff_level(...)`
- `f_draw_wall_level(...)`, `f_draw_magnet_level(...)`
- `f_draw_expected_move_boundary(...)`

#### `PineDrawingZones`

**Status:** Not yet published.
**Estimated size:** 1,500-2,500 lines.
**Contents:** zone category (§4) and fill category (§5).

Functions: `f_draw_expected_move_band`, `f_draw_session_range_box`, `f_draw_reversal_target_zone`, `f_draw_forecast_zone`, `f_draw_fvg_bull/bear`, `f_draw_order_block_bull/bear`, `f_draw_value_area`, `f_draw_single_print_zone`, `f_draw_macro_window`, `f_draw_reclaim_band`, `f_draw_liquidity_pool`, `f_draw_fill_expected_move`, `f_draw_fill_between_levels`.

#### `PineDrawingMarkers`

**Status:** Not yet published.
**Estimated size:** 1,000-1,500 lines.
**Contents:** §6 marker family.

Functions: `f_draw_judas_extreme_high/low`, `f_draw_manip_pivot_high/low`, `f_draw_liquidity_sweep_marker`, `f_draw_entry_marker`, `f_draw_exit_marker_profit/loss`, `f_draw_fvg_fill_marker`.

#### `PineDrawingVerticalMarkers`

**Status:** Not yet published.
**Estimated size:** 500-1,000 lines.
**Contents:** §7 vertical marker family.

Functions: `f_draw_session_boundary`, `f_draw_news_event_marker`, `f_draw_macro_window_start/end`.

#### `PineDrawingTables`

**Status:** Not yet published.
**Estimated size:** 2,000-3,000 lines.
**Contents:** §9 five table genres.

Functions: `f_draw_stats_table`, `f_draw_narrative_dashboard`, `f_draw_hit_rate_table`, `f_draw_distribution_table`, `f_draw_outcome_table`. Plus table-row helpers and cell formatters.

#### `PineDrawingComposites`

**Status:** Not yet published.
**Estimated size:** 1,500-2,000 lines.
**Contents:** §8 composite family.

Functions: `f_draw_projected_candle`, `f_draw_prediction_box`, `f_draw_price_model_trajectory`, `f_draw_time_histogram`, `f_draw_distribution_histogram`.

### 3.3 Specialized tier — `PineDrawingSpecialized`

**Status:** Not yet published.
**Estimated size:** 1,000-2,000 lines.
**Contents:** indicator-contributed templates (§10) that haven't graduated to canonical.

Examples:
- GEX/DEX wall scored variants (MacroDealerLevels)
- Scored level W/A/I family (MacroDealerLevels)
- Other specialized variants as they arise

Indicators import this only when using these specialized templates.

### 3.4 Per-indicator import examples

**Daily NY Levels** imports:
- `PineDrawingCore`
- `PineDrawingHorizontalLevels`
- `PineDrawingZones`
- `PineDrawingTables`

**Daily Expected Move** imports:
- `PineDrawingCore`
- `PineDrawingHorizontalLevels`
- `PineDrawingTables` (for the EM summary table)

**Probability Engine** imports:
- `PineDrawingCore`
- `PineDrawingHorizontalLevels`
- `PineDrawingZones`
- `PineDrawingTables`
- `PineDrawingVerticalMarkers`

**MacroDealerLevels** imports:
- `PineDrawingCore`
- `PineDrawingHorizontalLevels`
- `PineDrawingZones`
- `PineDrawingTables`
- `PineDrawingSpecialized` (for the scored W/A/I family)

**Candle Science Engine** imports:
- `PineDrawingCore`
- `PineDrawingHorizontalLevels`
- `PineDrawingZones`
- `PineDrawingTables`
- `PineDrawingComposites` (for `projected_candle`)

---

## 4. Current state (Pine v2)

The currently-published `PineDrawingLib/2` is thin. It provides basic primitives and collision helpers but does not yet implement the full layered architecture. Migration is in progress.

### 4.1 What v2 has

Published on TradingView under `vveerappa/PineDrawingLib/2`:

- Basic primitive wrappers with tag support
- Partial collision helpers (`f_near_any`)
- Some style constants

### 4.2 What v2 does not have

- No theme resolver (indicators handle theme themselves)
- No display profile concept
- No lifecycle manager (indicators track and delete their own objects)
- No label registry (indicators handle collision ad-hoc)
- No format-string interpreter (labels built with string concatenation)
- No semantic renderers (indicators call primitives directly)
- No split into family libraries

### 4.3 Migration to v3

v3 is a breaking major version. It:

- Replaces the monolithic library with Core + family libraries
- Introduces layered API
- Follows the template catalog as the stable contract

Old indicators continue to work against v2 until migrated. Migration is per-indicator, not atomic.

---

## 5. NT8 / NinjaScript architecture

**Status caveat:** the NT8 side is design target, not yet validated. You don't have existing NinjaScript drawing code to validate against. This section describes the target architecture; it will likely need adjustment when actually implemented.

### 5.1 Namespace structure

Pine's multi-library split translates to C# namespaces within a single assembly:

```
NtDrawingLib
├── Core/
│   ├── LifecycleManager.cs
│   ├── DrawRegistry.cs
│   ├── StyleResolver.cs
│   ├── LabelRegistry.cs
│   ├── FormatStringInterpreter.cs
│   ├── Primitives.cs
│   ├── Palette.cs
│   ├── DisplayProfile.cs
│   └── UnicodeHelpers.cs
├── HorizontalLevels/
│   ├── SessionLevels.cs
│   ├── StatisticalLevels.cs
│   ├── ThesisLevels.cs
│   ├── TargetLevels.cs
│   ├── PreviousPeriodLevels.cs
│   ├── AnchoredLevels.cs
│   └── GammaLevels.cs
├── Zones/
│   ├── ExpectedMove.cs
│   ├── SessionRange.cs
│   ├── ReversalTarget.cs
│   ├── Forecast.cs
│   ├── Fvg.cs
│   ├── OrderBlock.cs
│   ├── ValueArea.cs
│   ├── Macro.cs
│   └── Liquidity.cs
├── Markers/
│   ├── Judas.cs
│   ├── Liquidity.cs
│   └── Trade.cs
├── VerticalMarkers/
│   ├── Session.cs
│   └── News.cs
├── Tables/
│   ├── StatsTable.cs
│   ├── NarrativeDashboard.cs
│   ├── HitRateTable.cs
│   ├── DistributionTable.cs
│   └── OutcomeTable.cs
├── Composites/
│   ├── ProjectedCandle.cs
│   ├── PredictionBox.cs
│   ├── Trajectory.cs
│   └── Histograms.cs
└── Specialized/
    └── (indicator-contributed)
```

Indicators and strategies reference the assembly and use only the namespaces they need.

### 5.2 Platform primitive mapping

NinjaScript uses `Draw.*` static methods for chart annotations.

| Primitive | NT8 implementation |
|-----------|---------------------|
| line | `Draw.Line(this, tag, ...)` with `DashStyleHelper` |
| box | `Draw.Rectangle(this, tag, ...)` |
| label | `Draw.Text(this, tag, ...)` with `SimpleFont` |
| vline | `Draw.VerticalLine(this, tag, ...)` |
| arrow marker | `Draw.ArrowUp/ArrowDown(...)` |
| dot marker | `Draw.Dot(...)` |
| diamond marker | `Draw.Diamond(...)` |
| triangle marker | `Draw.TriangleUp/TriangleDown(...)` |
| x marker | `Draw.Text(...)` with "✗" glyph or custom `OnRender` |
| polyline | Compose from multiple `Draw.Line(...)` OR custom `OnRender` + SharpDX `PathGeometry` |
| linefill | `Draw.Region(...)` OR stacked `Draw.Rectangle` OR custom `OnRender` with SharpDX |
| table | Custom `OnRender(...)` with SharpDX `TextFormat` and `RectangleLayoutF` |

### 5.3 Known NT8 limitations

The following are genuine platform limitations that the NT8 implementation must work around. Documenting them here so expectations are set.

**No native polyline.** NT8 has no primitive equivalent to Pine's `polyline.new`. Implementation options:
1. Compose from a series of `Draw.Line` calls (simple, but each segment is a separate draw object with its own tag)
2. Custom `OnRender` with SharpDX `PathGeometry` (faster, better visual quality, but requires SharpDX knowledge and doesn't produce chart-editable objects)

Proposed: use option 1 for Layer E, letting the lifecycle manager batch-tag the segments.

**No native linefill.** Pine's `linefill.new` fills between two lines cleanly. NT8's closest equivalent is `Draw.Region` (if the underlying lines are indicator plots) or stacked `Draw.Rectangle`. For arbitrary linefill between two `Draw.Line` objects, a custom `OnRender` with SharpDX `FillGeometry` is required.

Proposed: use stacked rectangles for simple fills, fall back to custom render for complex cases.

**No native table.** NT8 has no chart-overlay table primitive. Every table is rendered via `OnRender(ChartControl, ChartScale)` using SharpDX:
- `TextFormat` for text styling
- `SolidColorBrush` for cell backgrounds
- `RectangleF` for cell geometry
- Careful `OnRender` performance: tables render every frame

Proposed: `PineDrawingTables` Core helpers provide a `RenderTable` utility that takes a table schema + data and handles all the SharpDX calls. Indicators just declare the table; the library handles rendering.

**No true hover tooltip in chart drawing API.** Pine's `label.new(..., tooltip=...)` shows platform-native tooltip on hover. NT8's `Draw.Text` has no tooltip parameter. Workarounds:
1. Multi-line text with the tooltip content inline (always visible, defeats the purpose)
2. Use NT8 chart panels to display context about the hovered object (requires `OnRender` hit-testing and panel management)
3. Accept that tooltips don't work on NT8 and document it

Proposed: the template's `label_mode_default` is respected on NT8 as follows:
- `Label`: visible text label, no tooltip. Full support.
- `Tooltip`: on NT8, renders as a dimmed label with the tooltip text pre-rendered. Document this as an accepted divergence.
- `Both`: visible label + dimmed tooltip-like footnote below the label.
- `None`: no label.

This is not ideal but is realistic for the platform. Tooltip-heavy indicators will look different on Pine vs NT8 and that's documented.

### 5.4 NT8 implementation priority

Migration order when NT8 work begins:
1. Core primitives and lifecycle (`NtDrawingLib.Core`)
2. `HorizontalLevels` family (covers most indicators)
3. `Tables` family (dashboards and stats)
4. `Zones` family
5. `Markers` and `VerticalMarkers` families
6. `Composites` (projected candle is the hard one on NT8)
7. `Specialized` as needed

First NT8 indicator: most likely the simplest one that has existing Pine equivalent we can validate against. Given your current focus, that's probably a VWAP reclaim or EMA pullback strategy which has only session levels, invalidation lines, and trade markers.

---

## 6. Tag convention

Every drawn object carries a stable tag used for lifecycle tracking.

### 6.1 Tag structure

```
{instance_key}:{template_name}:{element_subtype}
```

Examples:
- `london_high_2026_04_18:session_level_high:line`
- `london_high_2026_04_18:session_level_high:label`
- `es_fvg_20260418_093015:fvg_bull:box`
- `es_fvg_20260418_093015:fvg_bull:label`
- `projected_candle_forecast:projected_candle:body`
- `projected_candle_forecast:projected_candle:upper_wick`
- `projected_candle_forecast:projected_candle:lower_wick`
- `projected_candle_forecast:projected_candle:label`

Composite templates produce multiple tagged objects under one instance key. The lifecycle manager treats them as a unit: deleting the instance deletes all sub-tagged objects.

### 6.2 Tag uniqueness

`instance_key` is the indicator's responsibility. Instance keys must be stable across render cycles — the lifecycle manager reconciles by comparing tags. If an indicator recomputes a London high at bar N with the same instance key, the manager finds the existing tagged objects and updates them in place (on NT8) or deletes and recreates (on Pine).

### 6.3 Cleanup

At render start, the lifecycle manager marks all existing objects as "pending reconcile." Each draw call removes the pending mark from the matched tag. At render end, objects still marked pending are deleted.

---

## 7. Platform differences

Beyond the NT8 limitations in §5.3, these differences are worth knowing:

### 7.1 Re-execution model

- **Pine:** re-runs the full script from bar 1 on every bar. Lifecycle state is computed each cycle by comparing instance age to current bar.
- **NT8:** event-driven. `OnBarUpdate` fires per bar. Lifecycle state is persisted in C# instance variables across bars.

This means Pine implementations are stateless per-bar (state is recomputed); NT8 implementations carry state in memory. Indicators written for both platforms should express state declaratively so this difference is transparent.

### 7.2 Object limits

- **Pine:** `max_lines_count`, `max_boxes_count`, `max_labels_count`, `max_polylines_count` are declared at indicator header, default 50 each, max 500. Hitting the cap silently drops oldest objects.
- **NT8:** no hard cap, but performance degrades with thousands of draw objects.

Indicators must declare appropriate `max_*_count` values in Pine. The lifecycle manager tracks object counts and warns (via debug label) if an indicator is near its cap.

### 7.3 Font support

- **Pine:** five sizes (`size.tiny`/`small`/`normal`/`large`/`huge`). No font family selection; uses chart default.
- **NT8:** arbitrary point sizes via `SimpleFont`. Font family configurable.

The template's `label_font: monospace | proportional` is respected on NT8 (using `"Consolas"` or `"Segoe UI"`). On Pine, font family is ignored; indicators get the default Pine font at the profile-scaled size.

### 7.4 Color semantics

- **Pine:** `color.new(color, transparency)` where transparency is 0-100 (inverse of alpha).
- **NT8:** WPF/XAML `Brush` with alpha 0-255.

Layer B abstracts both. Templates declare transparency on a 0-100 scale; the primitives layer translates.

---

## 8. Migration plan — Daily NY Levels

Daily NY Levels is the first indicator to migrate. Migration sequence:

### 8.1 Before migration (current state)

Indicator has:
- ~1,500 lines of Pine code
- Direct calls to `line.new`, `box.new`, `label.new`, `table.new`
- Inline theme handling (hardcoded colors for dark vs light)
- Hand-rolled label collision (y-proximity checks scattered in render loop)
- Explicit object deletion at render end

### 8.2 After migration (target)

Indicator will:
- Import `PineDrawingCore`, `PineDrawingHorizontalLevels`, `PineDrawingZones`, `PineDrawingTables`
- Declare indicator-wide inputs: display profile, theme
- Use template bindings for every element
- Supply runtime data dicts; library handles formatting
- Never call primitive drawing APIs directly

Expected size reduction: from ~1,500 lines to ~600 lines. The saved code becomes reusable library code.

### 8.3 Migration steps

1. Publish `PineDrawingCore v3` with all Layer A-D infrastructure
2. Publish `PineDrawingHorizontalLevels v3` with the canonical line templates
3. Publish `PineDrawingZones v3` and `PineDrawingTables v3`
4. Create a new indicator script `daily_ny_levels_v7.pine`
5. For each element in the old indicator, identify its canonical template + tier + variant
6. Migrate elements one family at a time: session levels first, then statistical, then zones, then tables
7. Run side-by-side comparison with v6 on historical data to validate visual equivalence
8. Retire v6 once v7 is validated

### 8.4 Validation criteria

Migrated indicator passes validation if:
- Every visual element from v6 is reproduced in v7 at equivalent styling
- Label content matches (allowing for format-string-driven minor wording changes)
- Performance is equivalent or better
- No direct primitive calls (`line.new`, `box.new`, etc.) remain in the indicator code

---

## 9. Governance

### 9.1 Library versioning

Per `VISUAL_SYSTEM.md §10`. Each library has its own version; the published Pine `/N` integer tracks major version.

### 9.2 Coordinated releases

Breaking changes ripple through the library tree:
- Breaking Core change → all family libraries need to bump majors
- Breaking family library change → indicators importing that library need to migrate

Coordinate such releases: stage the Core major, migrate each family library one at a time, migrate indicators last.

### 9.3 Code review gate

Any PR adding direct primitive calls (`line.new`, `box.new`, `label.new`, `Draw.Line`, etc.) outside Layer C of a library is rejected. Indicators route all drawing through semantic renderers in Layer E.

### 9.4 Deprecation announcements

Deprecated functions carry `@deprecated` annotation with migration note. Tracking: maintain a `DEPRECATED.md` in each library repo listing what's deprecated, when, and what replaces it.

---

## 10. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial architecture (Daily NY Levels focus) |
| 2.0 | 2026-04-18 | Multi-indicator, cross-platform, five-layer model |
| 3.0 | 2026-04-18 | Library split into Core + family + Specialized tiers. NT8 namespace plan. Known platform limitations documented. Migration plan for Daily NY Levels. |
