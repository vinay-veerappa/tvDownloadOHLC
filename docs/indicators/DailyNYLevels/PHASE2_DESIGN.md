# Phase 2 - Directional Breakout Analytics: Detailed Design

**Version:** 1.3  
**Created:** 2026-04-17  
**Updated:** 2026-04-19  
**Status:** Implemented (core level set + theme system) - runtime visual validation pending  
**Parent:** [PRD.md](PRD.md)  
**Visual System:** [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md)  
**Depends on:** Phase 1 data model and libraries (`RangeSessionLib`, `StatsLib`, `PineDrawingLib`)

---

## 1. Objective

Phase 2 adds a direction-aware tactical overlay on top of existing bilateral MFE context.

The core idea is:
- Keep MFE context visible for both sides.
- Determine live directional bias from close behavior.
- Once direction is known, display tactical breakout/pullback/reversal levels as lines/zones.
- Keep MAE histogram optional and OFF by default.

This document locks formulas, activation rules, rendering behavior, and UI input requirements.

---

## 2. Scope and Non-Goals

### 2.1 In Scope

- Standalone analytics script: `DailyNYLevelsAnalytics.pine`.
- Directional bias engine (close-based only).
- Breakout side selection based on first close outside OR.
- Tactical line/zone rendering with locked formulas.
- Shared invalidation line with one merged label and unified label merging.
- Per-line and per-zone color configurability.
- Global theme mode (`Custom` / `Dark` / `Light`) for palette-level control across all rendered elements.
- Mid probability percentage display.
- Optional MAE histogram toggle (default OFF).
- Historical-only percentile sourcing for Phase 2 tactical lines (no current-session MAE/MFE blending).
- Explicit persistence and usage of all three MAE/MFE families: OR-based, breakout-based, and fake-move based.

### 2.2 Out of Scope

- Changing Phase 1 data capture model.
- Replacing bilateral MFE display with one-sided MFE.
- Probability-based side selection beyond first close outside OR (future enhancement).
- NinjaScript implementation (Phase 3).

---

## 3. Dependencies and Data Contract

Phase 2 reuses Phase 1 history/state fields already stored in `StatsLib.ExcursionHistory` and runtime `RangeState`.

Required arrays/fields:
- `mfe_bull`, `mfe_bear`
- `bo_mfe_bull`, `bo_mfe_bear`
- `mae_bull_abs`, `mae_bear_abs`
- `mae_bull_pb`, `mae_bear_pb`
- `bo_mae_bull`, `bo_mae_bear`
- `fakeout_bull`, `fakeout_bear`
- `fake_mfe_bull`, `fake_mfe_bear`
- `fake_mae_bull`, `fake_mae_bear`
- `fakeout_reversal_bull`, `fakeout_reversal_bear`
- `mid_hit_bull`, `mid_hit_bear`
- OR references: `or_high`, `or_low`, `or_mid`

Implementation note:
- Phase 2 now depends on the extended `StatsLib` contract (v2), including 26-arg `f_commit_daily` and persisted breakout/fake MAE/MFE families.

---

## 4. Direction and Activation Model

### 4.1 Live Bias Activation (close-based only)

For each bar after OR is complete:
- Bull live bias if `close > or_mid`
- Bear live bias if `close < or_mid`
- Neutral if `close == or_mid`

This bias controls which tactical line set is emphasized as active.

### 4.2 Breakout Side Selection (key event)

Breakout side is selected by the first candle close outside OR:
- First close `> or_high` => breakout side = Bull
- First close `< or_low` => breakout side = Bear

If both sides close outside OR later in session, the first close-outside remains the canonical side for that session.

### 4.3 Pullback Activation Trigger

Pullback logic activates only after breakout side is selected and price reaches P25 breakout MAE from breakout activation price.

Breakout price definition:
- Close of the first candle that closes outside OR on the selected side.

Activation threshold:
- P25 of `bo_mae_{side}` mapped from breakout activation price.

---

## 5. Locked Tactical Level Definitions

All percentages below are computed from historical arrays using `array.percentile_nearest_rank` on the relevant filtered sample.

### 5.1 BO Cashflow

Definition:
- `P20 MFE from breakout`

Bull price:
- `y = breakout_price * (1 + p20_mfe_breakout / 100)`

Bear price:
- `y = breakout_price * (1 - p20_mfe_breakout / 100)`

### 5.2 BO Confirm

Definition:
- `P75 MFE of fakeouts`

Sample:
- Bull: historical `fake_mfe_bull`
- Bear: historical `fake_mfe_bear`

### 5.3 Pivot

Definition:
- `P50 MFE of fakeouts`

Sample:
- Same side-specific historical `fake_mfe_*` sample as BO Confirm.

### 5.4 Reversal Target Zone

Definition:
- `P20-P50 of fakeout MAE`

Sample:
- Bull: historical `fake_mae_bull`
- Bear: historical `fake_mae_bear`

Rendered as a zone band between P20 and P50 reversal depth, projected from OR breakout boundary on selected side.

### 5.5 Max Reversal

Definition:
- `P90 of fakeout MAE`

Sample:
- Same side-specific historical `fake_mae_*` sample as Reversal Target Zone.

### 5.6 PB Invalidation

Definition:
- `P80 MAE of breakout`

Sample:
- Bull side: historical `bo_mae_bull`
- Bear side: historical `bo_mae_bear`

### 5.7 BO Invalidation

Definition:
- `P80 MAE of breakout` (same as PB Invalidation for current version)

Rendering rule:
- Draw one shared line at this level.
- Render one merged label: `PB | BO Invalidation`.

### 5.8 Mid Probability

Definition:
- Hit-rate percentage for OR midpoint interaction.

Computation:
- Combined midpoint hit rate from historical arrays:
  - hits = sum(`mid_hit_bull`) + sum(`mid_hit_bear`)
  - denom = `2 * session_count`
  - pct = `hits / denom * 100`

---

## 6. Rendering System

### 6.1 Baseline Visibility

Always visible:
- Bilateral MFE context (both bull and bear).
- OR references and midpoint line.

Direction-dependent emphasis:
- Tactical lines/zones for selected breakout side use active styling.
- Opposite side tactical set can be hidden or de-emphasized (default: de-emphasized).

### 6.2 Draw Order (back to front)

1. OR box and baseline references.
2. MFE histogram/profile context (both sides).
3. Reversal target zone fill (if active).
4. Max reversal line.
5. BO Cashflow, BO Confirm, Pivot lines.
6. Shared invalidation line.
7. Mid probability label.
8. Shared merged labels for all remaining text labels.

This order keeps tactical lines readable over context fills.

### 6.3 Unified Label System

All stat and tactical labels participate in one shared label registry.

Rules:
- One shared right-edge label column.
- One shared label size token: `i_label_size`.
- One shared label text color token: `i_label_text_color`.
- One shared directional offset token: `i_label_offset_ticks`.
- One shared merge threshold token: `i_label_merge_threshold_ticks`.

Merge behavior:
- Labels within `i_label_merge_threshold_ticks × mintick` are merged into one pipe-delimited label.
- Context stat lines near tactical levels are suppressed before label rendering, so the combined system stays readable without separate tactical/stat spacing controls.

### 6.4 Theme Resolution Rules

Phase 2 rendering uses a theme resolver model:
- `Custom`: use user-selected color inputs directly.
- `Dark`: use a dark-chart optimized palette fallback per visual token.
- `Light`: use a light-chart optimized palette fallback per visual token.

Resolver contract:
- `f_theme_color(custom_color, dark_color, light_color)` selects the effective color per token.
- Token resolution happens before rendering and is reused by all drawing modules (stat lines, histograms, time distribution, phase-2 tactical levels, table, debug labels).

Scope of theme token application:
- OR/bull/bear baseline colors.
- Stat labels, median/avg/stretch/mid lines.
- Time distribution bars/title/avg/median lines.
- Breakout activation and pullback activation levels.
- BO cashflow/confirm/pivot/reversal/invalidation labels and lines.
- Data table background, border, header, and body text.
- Debug labels.

---

## 7. Inputs

Phase 2 must expose configurable colors per line/zone.

### 7.1 Required Feature Toggles

- `i_show_phase2_levels` (master toggle)
- `i_show_mae_hist` (default `false`)
- `i_emphasize_active_side` (default `true`)

### 7.2 Required Color Inputs

- `i_color_bo_cashflow`
- `i_color_bo_confirm`
- `i_color_pivot`
- `i_color_reversal_zone`
- `i_color_max_reversal`
- `i_color_invalidation_line`
- `i_color_mid_probability`
- `i_color_breakout_activation`
- `i_color_pullback_activation`
- `i_stat_avg_color`
- `i_stat_stretch_color`
- `i_mid_line_color`
- `i_time_title_color`
- `i_table_bg_color`
- `i_table_border_color`
- `i_table_header_bg_color`
- `i_table_header_text_color`
- `i_table_body_text_color`
- `i_debug_text_color`
- `i_debug_bg_color`

### 7.3 Required Theme Inputs

- `i_theme_mode` with options `Custom`, `Dark`, `Light`.

### 7.4 Required Style Inputs (Visual System)

All visual style tokens are now shared across Phase 1 and Phase 2 via the unified
Visual System (see [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md) §5).

- `i_line_width_primary` — shared, `grp_visual`
- `i_line_width_secondary` — shared, `grp_visual`
- `i_zone_transparency` — shared, `grp_visual`
- `i_label_size` — shared (replaces former `i_label_size_phase2`), `grp_visual`
- `i_label_offset_ticks` — shared (replaces former `i_label_offset_ticks_phase2`), `grp_visual`
- `i_label_merge_threshold_ticks` — shared, `grp_visual`

---

## 8. Processing Flow

Per-bar pipeline after OR completion:

1. Resolve active range/state and history.
2. Compute live bias from close vs OR midpoint.
3. Detect first close outside OR and lock breakout side/breakout price.
4. Compute breakout-side tactical percentiles from history.
5. Check pullback activation at P25 from breakout price.
6. Build price levels/zones from locked formulas.
7. Render lines/zones with configured colors and emphasis rules.
8. Render the unified label registry with merge-on-proximity.

Data sourcing rule:
- All percentile calculations in steps 4-6 must use historical persisted arrays only.

---

## 9. Edge Cases and Fallbacks

- If sample size is insufficient for any percentile (< minimum required), hide that line and mark as `n/a` in label/debug text.
- If no fakeout sample exists for selected side, hide BO Confirm, Pivot, reversal zone, and max reversal.
- If no breakout close occurs yet in session, keep tactical lines inactive; show only baseline context.
- If live bias and locked breakout side diverge, breakout side remains canonical for tactical set; live bias can still be displayed as status.

---

## 10. Acceptance Criteria

1. Live bias activation is driven only by close vs OR midpoint.
2. Breakout side is selected by first close outside OR and does not flip later in session.
3. All tactical lines match locked formulas exactly.
4. PB and BO invalidation share one line and render one merged shared label.
5. Every line/zone has dedicated color input and responds at runtime.
6. MAE histogram is optional and default OFF.
7. Mid probability shows OR-mid hit-rate percentage.
8. No tactical percentile uses current-session MAE/MFE values before commit.
9. BO/fake tactical levels are computed from persisted `bo_*` and `fake_*` historical arrays.

---

## 11. Implementation Status (2026-04-18)

Implemented:
- Breakout activation line and pullback activation line naming finalized.
- Pullback activation uses P25 breakout MAE from breakout activation price.
- Shared PB/BO invalidation line with one merged label in the unified label system.
- Post-cutoff rendering extension for tactical lines/labels.
- Historical persistence and consumption of breakout and fake MAE/MFE families.
- Historical-only tactical percentile sourcing enforced.

Pending:
- Final chart-level visual verification pass across sessions/timeframes.

---

## 12. Testing Checklist

- Verify bullish and bearish sessions each trigger correct side by first close-outside rule.
- Verify equal close at midpoint stays neutral.
- Validate percentile calculations against manually sampled history slices.
- Validate shared invalidation dual-label spacing on dense-chart and sparse-chart conditions.
- Validate all color inputs modify the intended visual element only.
- Validate MAE histogram toggle OFF by default and ON behavior when enabled.

---

## 13. Future Enhancement Hook

- Optional replacement of first-close breakout side keying with a probability-weighted side model (tracked in PRD open item O-8).
- Optional divergence of PB invalidation and BO invalidation formulas when a distinct BO invalidation definition is finalized.
