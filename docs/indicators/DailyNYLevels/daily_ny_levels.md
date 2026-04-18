# Indicator: Daily NY Levels

**Version:** v6 (current published), v7 (target after migration)
**Platform:** Pine v6
**Migration status:** Pending (reference indicator for v3 library migration)
**Libraries:** PineDrawingCore, PineDrawingHorizontalLevels, PineDrawingZones, PineDrawingTables
**Symbol scope:** ES, NQ, YM, RTY, MES, MNQ, MYM, M2K (futures and micros); extendable to equities

---

## 1. Business description

Daily NY Levels displays statistical levels derived from rolling historical samples of the NY AM session (or other configurable sessions). For the trader, the indicator answers: "Given recent session behavior, where is the typical stretch, where is the typical reversal, and what structural pivots does the data support?"

Computed artifacts per session:
- Session open anchor
- Median, average, and percentile MFE / MAE levels from historical samples
- Stretch level (P90 MFE)
- Max reversal level (P90 MAE)
- Invalidation line (max plausible adverse move)
- Activation triggers (breakout and pullback)
- Confirmation level
- Structural pivot (P50 target)
- Target levels at P20, P50, P75
- Day-of-week biased variants
- Fake-breakout reversal zone (historical fakeout statistics)
- Rolling distribution summary tables

The indicator is designed to be visually dense but readable, supporting both real-time trading decisions and session post-mortem analysis. It's the first indicator slated for migration to the v3 library architecture and serves as the reference example of template-bound indicator design.

---

## 2. Inputs

### 2.1 Display inputs (every indicator has these)

- `i_theme` — `Dark | Light | Custom` (default `Dark`)
- `i_display_profile` — `Tiny | Small | Normal | Large | Huge` (default `Normal`)

### 2.2 Session configuration

- `i_session_tz` — timezone (`America/New_York` default)
- `i_session_window` — session window (NY AM, NY PM, London, custom)
- `i_rolling_n_days` — historical sample size (20, 60, 120, 250)
- `i_dow_filter` — optional day-of-week filter

### 2.3 Element toggles

One toggle per family, following input-group conventions:

- `grp_session_levels` — show/hide session H/L/Mid
- `grp_statistical` — show/hide median/avg/pN/stretch/max_reversal
- `grp_thesis` — show/hide invalidation, activation triggers, confirm, pivot
- `grp_targets` — show/hide P20/P50/P75
- `grp_zones` — show/hide reversal target zone
- `grp_tables` — show/hide each table genre rendered

### 2.4 Override (expert-mode)

- `i_enable_expert_overrides` — when true, exposes per-element tier overrides and label_mode overrides. Off by default. Documented in §5.

---

## 3. Element bindings

### 3.1 Session levels (family)

**Template:** `session_level_high`
**Library:** `PineDrawingHorizontalLevels`
**Bindings:**

| Binding ID | Tier | Variant | Direction | Session | Runtime data slots |
|------------|------|---------|-----------|---------|---------------------|
| `session_high_current` | P | — | — | (config) | `session_name`, `probability`, `hit_rate`, `streak_arrow`, `streak_count` |
| `session_high_yesterday` | S | — | — | (config) | same; automatic `[-1d]` suffix |

Lifecycle: default (historical_retention = 1).
label_mode: `Both` (both visible label and tooltip).

**Template:** `session_level_low`
Analogous to `session_level_high`, mirrored.

**Template:** `session_level_mid`
Tier S default; omit if `i_show_mid == false`.

### 3.2 Statistical levels (family)

**Template:** `statistical_level_median`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `mfe_median_bull` | P | bull | `source_name="MFE"`, `value`, `unit="$"` |
| `mfe_median_bear` | P | bear | same with direction bear |
| `mae_median_bull` | S | bull | `source_name="MAE"`, `value`, `unit` |
| `mae_median_bear` | S | bear | same |

**Template:** `statistical_level_avg`
Analogous bindings with `source_name="MFE"` / `"MAE"`. Tier S by default (average is informational context for median).

**Template:** `statistical_level_pN`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `mfe_p25_bull` | S | bull | `source_name="MFE"`, `percentile=25`, `value`, `unit` |
| `mfe_p75_bull` | S | bull | `source_name="MFE"`, `percentile=75`, `value`, `unit` |
| `mfe_p25_bear` | S | bear | analogous |
| `mfe_p75_bear` | S | bear | analogous |
| `mae_p25_bull` | C | bull | analogous for MAE |
| `mae_p75_bull` | C | bull | analogous |
| `mae_p25_bear` | C | bear | analogous |
| `mae_p75_bear` | C | bear | analogous |

**Template:** `stretch_level`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `mfe_stretch_bull` | P | bull | `source_name="MFE"`, `percentile=90`, `value`, `unit` |
| `mfe_stretch_bear` | P | bear | analogous |

**Template:** `max_excursion_level`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `mae_p90_bull` | P | bull | `source_name="MAE"`, `percentile=90`, `value`, `unit` |
| `mae_p90_bear` | P | bear | analogous |

### 3.3 Thesis lines (family)

**Template:** `invalidation_level`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `invalidation_bull` | P | bull | `source="MAE"`, `percentile=98`, `value`, `unit`, `direction_hint="Bull"` |
| `invalidation_bear` | P | bear | analogous |

**Template:** `activation_trigger`

| Binding ID | Tier | Variant | Direction | Runtime data slots |
|------------|------|---------|-----------|---------------------|
| `breakout_trigger_bull` | P | breakout | bull | `variant_display="Breakout"`, `value`, `unit`, `basis="session H"` |
| `breakout_trigger_bear` | P | breakout | bear | analogous |
| `pullback_trigger_bull` | S | pullback | bull | `variant_display="Pullback"`, `value`, `unit`, `basis="median MFE"` |
| `pullback_trigger_bear` | S | pullback | bear | analogous |

**Template:** `confirm_level`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `confirm_bull` | C | bull | `source="MFE"`, `percentile=20`, `value`, `unit` |
| `confirm_bear` | C | bear | analogous |

**Template:** `pivot_structural`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `pivot_p50_bull` | P | bull | `label_suffix="P50"`, `value`, `unit`, `basis="MFE median"` |
| `pivot_p50_bear` | P | bear | analogous |

### 3.4 Target levels (family)

**Template:** `target_level_p20`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `target_p20_bull` | S | bull | `value`, `unit`, `basis="MFE P20"` |
| `target_p20_bear` | S | bear | analogous |

**Template:** `target_level_p75`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `target_p75_bull` | S | bull | `value`, `unit`, `basis="MFE P75"` |
| `target_p75_bear` | S | bear | analogous |

### 3.5 Reversal zones (family)

**Template:** `reversal_target_zone`

| Binding ID | Tier | Direction | Runtime data slots |
|------------|------|-----------|---------------------|
| `bull_trap_reversal` | S | bull_trap | `trap_side="Bull Trap"`, `p50_value`, `p75_value`, `p90_value`, `unit` |
| `bear_trap_reversal` | S | bear_trap | `trap_side="Bear Trap"`, analogous |

Internal reference line (P50) rendered automatically by the template using `statistical_level_median` styling at tier C.

### 3.6 Debug elements (optional)

When `i_debug == true`, render `debug_label` and `debug_marker` to show computation boundaries (e.g., session start/end bar indices, sample-size indicators). Debug always at tier C with `transparency_background`.

---

## 4. Tables

### 4.1 Stats table — MFE summary

**Genre:** `stats_table`
**Position:** `top_right`
**Content:** columns = [Percentile, Bull MFE, Bear MFE, Bull MAE, Bear MAE]. Rows = [P20, P50, P75, P90].

### 4.2 Stats table — DOW table

**Genre:** `stats_table`
**Position:** `middle_right`
**Content:** columns = [DoW, MFE bull median, MFE bear median, MAE bull median, MAE bear median]. Rows = Mon-Fri.

### 4.3 Distribution table — MFE distribution

**Genre:** `distribution_table`
**Position:** `bottom_right`
**Content:** Buckets across the MFE P90 range, rendered with inline Unicode bars. Zone threshold default 50%. Helper used: `f_unicode_bar`.

### 4.4 Stats table — fakeout table

**Genre:** `stats_table`
**Position:** `bottom_left`
**Content:** fake-breakout statistics: frequency of bull trap, bear trap, P50/P75/P90 MAE after fakeout direction was established.

### 4.5 Table display conventions

All four tables follow the `size_scaling: profile_aware` policy — sizes scale with the chart-wide display profile. Headers use `header_bg`/`header_text` tokens. Numeric cells use monospace.

---

## 5. Overrides & exceptions

### 5.1 Expert mode tier overrides (optional)

When `i_enable_expert_overrides == true`, the user can override any binding's tier at runtime. This is an escape hatch for custom emphasis preferences. Documented impact: expert mode breaks cross-indicator consistency for this session only; not recommended for normal use.

**Justification:** power users have asked to deprioritize specific lines without removing them. Rather than introducing a fourth tier or adding per-line hide toggles, expert mode lets users move any line to C tier. Default off so the canonical ruleset is respected.

**Graduation path:** if this pattern is adopted by other indicators, it could become a canonical "user tier override" feature documented in `VISUAL_SYSTEM.md §6`.

### 5.2 No other overrides

All other styling strictly follows the canonical template catalog. No color overrides, no format string overrides, no font overrides.

---

## 6. Lifecycle and state

### 6.1 Retention

- Session levels: 1 (show yesterday's session faded with `[-1d]` suffix)
- Statistical / thesis / target levels: 0 (they roll with each session)
- Reversal zones: 0
- Debug elements: 0

### 6.2 State transitions

At session open: new instances created in `forming` state for session H/L/M (which evolve during session).
At session close: transition to `finalized`. Statistical lines compute once and are `finalized` from creation.
At next session open: prior session's finalized elements transition to `historical_1d`.
At next session+1 open: elements transition to `expired` (retention == 1).

---

## 7. Notes

### 7.1 Migration reference

This indicator is the first migration target for the v3 library architecture. Its migration doubles as validation: if v3 can reproduce this indicator exactly, v3 is viable. Migration criteria in `LIBRARY_ARCHITECTURE.md §8.4`.

### 7.2 Performance

Expect object count to be significant:
- ~20 horizontal lines (session + statistical + thesis + targets, both directions)
- ~4 right-edge labels with content
- 1-2 zones
- 4 tables

Object caps in indicator header should be:
```
max_lines_count = 50
max_boxes_count = 20
max_labels_count = 50
```

### 7.3 Related indicators

- **MFE Tracker** (separate indicator): a slimmer variant of Daily NY Levels focused only on MFE P90 tracking. Likely becomes a preset/profile of this indicator rather than a separate one, post-migration.
- **Daily Profiler**: complementary — covers multi-session profiling with hit-rate tracking. Daily NY Levels is single-session-deep; Daily Profiler is multi-session-broad.

### 7.4 Open questions for migration

1. Should the fakeout table be a separate `stats_table` or a section of the main stats table?
2. Should DOW filtering produce a dim visual treatment of out-of-filter historical samples (educational) or suppress them entirely (clean)?
3. Should the bull/bear pair of a line render as two separate bindings (current proposal) or one binding with directional variants (simpler)?

These will be resolved during migration and incorporated into v7.

### 7.5 Phase 1 label-engine parity matrix (v6 -> v3)

Phase 1 target is ownership extraction, not feature change. The following matrix defines parity expectations between current indicator behavior and the new `PineDrawingCore` label registry.

| Current behavior in v6 | Registry contract field(s) | Expected parity outcome |
|------------------------|----------------------------|-------------------------|
| Right-edge labels are pushed after line geometry decisions | `LabelEntry.x`, `LabelEntry.y`, `LabelEntry.price_y`, `f_register_label()` | Labels stay anchored to the same price and time columns. |
| Near-price labels merge when within symbol-aware threshold | `collision_strategy=merge`, `merge_group`, `f_merge_threshold_for_symbol()` | Same sibling merge behavior for tightly-clustered levels. |
| Tactical labels outrank nearby context/stat labels | `collision_priority`, `state` ordering in `f_resolve_label_collisions()` | Tactical labels remain visible when overlap occurs. |
| Dense layouts use stagger columns to avoid unreadable overlap | `collision_strategy=stagger`, profile-scaled `column_step_bars` | Same columnized layout behavior under overlap. |
| Hidden/suppressed labels are not drawn but source lines remain | `ResolvedLabelEntry.drawn=false`, `suppressed_reason` | Suppression remains label-only unless caller explicitly suppresses line. |
| Label text is built from shared template semantics + runtime values | `base_text`, `label_format`, `runtime_data`, `f_resolve_label_text()` | Produced text matches current content and conditional slot logic. |
| Historical labels carry day-age context suffix | `state=historical_Nd`, lifecycle-aware label post-processing | `[-Nd]` suffix semantics remain unchanged. |
| Label mode can be Label/Tooltip/Both/None per binding | `label_mode`, `tooltip_format` | Existing visibility behavior preserved per binding defaults. |

### 7.6 Phase 1 acceptance checklist

Before removing any indicator-local collision logic, all checks below must pass.

- [ ] No new diagnostics in migrated files.
- [ ] Session/stat/thesis/target right-edge labels appear at identical anchor prices on the same bar snapshot.
- [ ] Merge cases (median/average siblings and close-proximity tactical/stat overlaps) produce identical visible text outcomes.
- [ ] Stagger cases produce deterministic column ordering across reruns.
- [ ] Historical labels preserve `[-1d]` suffix and retention behavior.
- [ ] `label_mode` behavior (Label, Tooltip, Both, None) remains unchanged for existing bindings.
- [ ] No direct label collision/merge helper remains in indicator code path after extraction.

---

## 8. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial profile rewritten in template-binding form. Covers all elements of current v6 Pine script. Migration target for v3 library architecture. |
