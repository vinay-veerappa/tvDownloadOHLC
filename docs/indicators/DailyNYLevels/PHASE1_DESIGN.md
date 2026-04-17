# Phase 1 — Modularize & Generalize: Detailed Design

**Version:** 1.0  
**Created:** 2026-04-17  
**Status:** In Design  
**Parent:** [PRD.md](PRD.md)  
**Source:** `scripts/indicators/DailyNYLevelsV2.pine` (v4.1)  
**Target:** `scripts/indicators/daily-ny-levels/DailyNYLevelsV5.pine` + libraries

---

## 1. Design Goals

1. **Functional parity** with V4.1 custom-range mode — identical visuals for the same inputs.
2. **Preset dropdown** that resolves to the same internal data model as custom mode.
3. **UDT-driven data model** — all range, state, and rendering data flows through typed structures.
4. **Library extraction** — reusable code in importable Pine libraries for cross-script consumption.
5. **Pine sessions** — replace raw HHMM minute-math with `input.session` / `time()` session strings where beneficial.
6. **Multi-range support** — compound presets activate multiple sub-ranges; each tracked independently.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  DailyNYLevelsV5.pine                    │
│                    (Main Indicator)                       │
├─────────────────────────────────────────────────────────┤
│  Inputs & Preset Resolver                                │
│    ↓ produces array<RangeSpec>                           │
│  Session Engine (per RangeSpec)                           │
│    ↓ updates array<RangeState>                           │
│  Excursion Engine (MFE tracking per RangeState)          │
│    ↓ updates ExcursionData inside each RangeState        │
│  Rendering Engine                                        │
│    ↓ reads RangeState[] → draws OR boxes, histograms,   │
│      stat lines, tables, day separators, info box        │
└──────────────┬──────────────┬──────────────┬────────────┘
               │              │              │
     ┌─────────▼──┐  ┌───────▼────┐  ┌──────▼─────┐
     │ RangeSession│  │ DrawingLib  │  │ StatsLib   │
     │ Lib.pine    │  │ .pine      │  │ .pine      │
     │             │  │            │  │            │
     │ • RangeSpec │  │ • clear_*  │  │ • f_size   │
     │ • RangeState│  │ • OR box   │  │ • f_build  │
     │ • resolve   │  │ • hist band│  │   _filtered│
     │ • f_in_sess │  │ • stat line│  │ • percentile│
     │ • f_parse   │  │ • label    │  │ • median   │
     │ • f_duration│  │ • day sep  │  │ • streak   │
     └─────────────┘  └────────────┘  └────────────┘
```

---

## 3. User-Defined Types (UDTs)

### 3.1 `RangeSpec` — Static Range Definition

Immutable after initialization. One per sub-range.

```pine
// In RangeSessionLib
type RangeSpec
    string name           // e.g. "1800 Break", "Market Open"
    string preset_group   // e.g. "Overnight", "Pre-Market", "Intraday", "Custom"
    int    or_start_min   // OR window start in minutes-of-day (ET)
    int    or_end_min     // OR window end in minutes-of-day (ET)
    int    cutoff_min     // Data/MFE+MAE tracking cutoff in minutes-of-day (ET)
    string session_or     // Pine session string for OR: "1800-1815:12345"
    string session_data   // Pine session string for data window: "1815-0300:12345"
    string tz             // Timezone string: "America/New_York"
    bool   is_transfer    // True for 0300 Transfer (directional OR toward 1800 open)
    float  ev_target_pct  // EV win threshold % (default 0.3); per-range configurable
    color  bull_color     // Per-range bull color (auto-generated hue offset if na)
    color  bear_color     // Per-range bear color (auto-generated hue offset if na)
    color  box_color      // Per-range OR box color (auto-generated hue offset if na)
```

> **Note on `is_transfer`:** The 0300 Transfer has its own 5-min OR (0300–0305). It is filtered so only the breakout **toward** the 1800 session open price counts. Specifically: bull direction is valid if 1800 open price > 0300 OR close; bear direction if 1800 open price < 0300 OR close. Skip the Transfer day if 1800 open data is unavailable.

> **Note on session days:** The 1800 Break session fires on **Sunday through Thursday evenings** (Pine days `1,2,3,4,5`) to capture Sunday market reopen.

> **Note on date stamping:** Cross-midnight sessions (e.g., 18:00 → 03:00) are stamped with the **cutoff date** (e.g., Monday date for a 18:00 Sun → 03:00 Mon session), matching conventional futures trade-date convention.

### 3.2 `RangeState` — Per-Day Mutable State

One instance per active `RangeSpec`. Reset on each new session day.

```pine
// In RangeSessionLib
type RangeState
    RangeSpec spec              // Back-reference to the defining spec
    // --- OR tracking ---
    float   or_high             // Current OR high
    float   or_low              // Current OR low
    float   or_last_close       // Last close inside the OR window
    bool    or_building         // True while bars are inside the OR window
    bool    or_complete         // True once the OR window has closed
    int     or_start_bar        // bar_index of the first OR bar
    // --- Reference levels ---
    float   bull_ref            // High reference (= or_high)
    float   bear_ref            // Low reference  (= or_low)
    float   or_mid              // Midpoint (or_high + or_low) / 2, set at ref_set
    bool    ref_set             // True once references are locked after OR completion
    // --- Daily MFE ---
    float   daily_bull_mfe      // Today's max bull excursion from OR_high (%)
    float   daily_bear_mfe      // Today's max bear excursion from OR_low (%)
    int     daily_bull_peak_min // Minutes-since-OR-start of bull MFE peak
    int     daily_bear_peak_min // Minutes-since-OR-start of bear MFE peak
    // --- Daily MAE (Absolute) ---
    // Worst adverse excursion from the OR boundary
    float   daily_mae_bull_abs  // Worst adverse below OR_low (%)
    float   daily_mae_bear_abs  // Worst adverse above OR_high (%)
    // --- Daily MAE (Pullback) ---
    // Worst adverse retrace across the breakout level BEFORE peak MFE
    // Bull pullback MAE = worst retrace below OR_HIGH before peak bull MFE
    // Bear pullback MAE = worst retrace above OR_LOW before peak bear MFE
    float   daily_mae_bull_pb   // Pullback MAE, bull side (%)
    float   daily_mae_bear_pb   // Pullback MAE, bear side (%)
    // Running worst adverse SINCE last bull/bear MFE peak (for pullback tracking)
    float   pb_tracker_bull     // Tracks running adverse below OR_high since any bull excursion started
    float   pb_tracker_bear     // Tracks running adverse above OR_low since any bear excursion started
    // --- Mid hit tracking ---
    bool    mid_hit_bull        // Has price touched or exceeded or_mid from bull side (high >= or_mid)
    bool    mid_hit_bear        // Has price touched or exceeded or_mid from bear side (low <= or_mid)
    // --- Fakeout / Entry Trigger tracking ---
    bool    entry_triggered_bull  // Any bar's high > OR_HIGH during data session
    bool    entry_triggered_bear  // Any bar's low  < OR_LOW  during data session
    // Running session extremes from OR completion to cutoff (for fakeout reversal depth)
    float   session_low_data    // Running min of all bar lows during the data session
    float   session_high_data   // Running max of all bar highs during the data session
    float   close_at_cutoff     // Last close of the data session (set at commit time)
    // --- Commit state ---
    bool    is_committed        // True once daily data has been pushed to history
    // --- Drawing handles ---
    box     or_box              // The OR box for this range today
    // --- Pivot tracking ---
    array<float> daily_pivot_bulls
    array<float> daily_pivot_bears
```

### 3.3 `ExcursionHistory` — Accumulated History Per Range

Persists across days. One per `RangeSpec`.

```pine
// In StatsLib  (merged from formerly-separate ExcursionLib)
type ExcursionHistory
    string range_name                  // Matches RangeSpec.name
    // --- MFE ---
    array<float> mfe_bull              // Daily max bull MFE (%)
    array<float> mfe_bear              // Daily max bear MFE (%)
    array<int>   peak_time_bull        // Minutes-since-OR of bull MFE peak
    array<int>   peak_time_bear        // Minutes-since-OR of bear MFE peak
    array<float> pivot_bull            // All bull pivot touches (%)
    array<float> pivot_bear            // All bear pivot touches (%)
    // --- MAE Absolute ---
    // Worst adverse from OR boundary (same refs as MFE)
    array<float> mae_bull_abs          // Worst adverse below OR_low (%)
    array<float> mae_bear_abs          // Worst adverse above OR_high (%)
    // --- MAE Pullback ---
    // Worst adverse retrace across the BREAKOUT LEVEL before peak MFE
    array<float> mae_bull_pb           // Pullback below OR_HIGH before peak bull MFE (%)
    array<float> mae_bear_pb           // Pullback above OR_LOW before peak bear MFE (%)
    // --- Mid hit ---
    array<bool>  mid_hit_bull          // Did price touch or_mid from bull side?
    array<bool>  mid_hit_bear          // Did price touch or_mid from bear side?
    // --- Range size ---
    array<float> or_range_pct          // OR range in % of price (or_high - or_low) / or_low * 100
    // --- Day metadata ---
    array<int>   dow                   // Day of week (1=Sun … 7=Sat) for each session
    // --- Derived metrics ---
    array<float> r_multiple_bull       // MFE_bull / mae_bull_abs per day (na if mae=0)
    array<float> r_multiple_bear       // MFE_bear / mae_bear_abs per day
    array<int>   direction_flag        // Net dominant direction: +1 bull, -1 bear, 0 neutral
    array<bool>  reversal_flag         // True: hit MFE >= P50 then closed below OR_low (bull) / above OR_high (bear)
    array<bool>  ev_win_bull           // bull MFE >= spec.ev_target_pct (na if zero-MFE day)
    array<bool>  ev_win_bear           // bear MFE >= spec.ev_target_pct (na if zero-MFE day)
    // --- Fakeout / Move Failure Classification ---
    // Trigger: price actually broke the OR boundary (high > OR_HIGH or low < OR_LOW)
    array<bool>  entry_triggered_bull  // High broke OR_HIGH at any point during data session
    array<bool>  entry_triggered_bear  // Low  broke OR_LOW  at any point during data session
    // Fakeout: triggered BUT close at cutoff returned inside OR
    array<bool>  fakeout_bull          // entry_triggered_bull AND close_at_cutoff <= OR_HIGH
    array<bool>  fakeout_bear          // entry_triggered_bear AND close_at_cutoff >= OR_LOW
    // Double break: both sides triggered in the same session (stop hunt pattern)
    array<bool>  double_break          // entry_triggered_bull AND entry_triggered_bear
    // Fakeout reversal depth (post-trigger, measured from the breached OR level)
    // Bull: max(0, (OR_HIGH - session_low_data) / OR_HIGH * 100) — how far below BO level
    // Bear: max(0, (session_high_data - OR_LOW)  / OR_LOW  * 100) — how far above BO level
    // na on non-fakeout days (entry never triggered in that direction)
    array<float> fakeout_reversal_bull  // Total adverse below OR_HIGH on bull fakeout days (%)
    array<float> fakeout_reversal_bear  // Total adverse above OR_LOW  on bear fakeout days (%)
```

> **Fakeout stat framework:**
> | Level | Source | Trading Use |
> |-------|--------|-------------|
> | P75 MFE (fake) | `percentile(mfe_bull where fakeout_bull, 75)` | Real breakout confirmed above this |
> | P50 MFE (fake) | `percentile(mfe_bull where fakeout_bull, 50)` | Mean-reversion zone OR real BO continuation decision |
> | P25–P50 reversal | `percentile(fakeout_reversal_bull, 25..50)` | Normal counter-move target after fake |
> | P90 reversal | `percentile(fakeout_reversal_bull, 90)` | Max reversal / danger zone for fading the fake |

### 3.4 `DrawingState` — Ephemeral Drawing Object Pools

Managed per render cycle. Cleared and rebuilt on `barstate.islast`.

```pine
// In DrawingLib (or inline)
type DrawingState
    array<box>   boxes
    array<line>  lines
    array<label> labels
```

---

## 4. Pine Session Strings — Migration Strategy

### 4.1 Current Approach (V4.1)
- HHMM strings → `f_parse_hhmm()` → minutes-of-day integers
- `f_in_range(bar_mins, start, end)` manual cross-midnight logic
- `f_duration()`, `f_mins_since()` manual arithmetic

### 4.2 Target Approach (V5)
- **Hybrid**: Use Pine `time()` with session strings for clean in-session detection, retain minutes-of-day math for MFE/MAE time tracking (minutes-since-OR).
- **Rationale**: `time()` handles DST and cross-midnight natively; but peak-time tracking needs relative minute offsets which session strings don't expose directly.

### 4.3 Session String Format

Pine session format: `"HHMM-HHMM:DAYS"` where days = `1234567` (Sun=1, Sat=7).

> All times are **EST (America/New_York)**. Pine's `time()` with `"America/New_York"` tz handles ET/EDT transitions automatically.

| Range | OR Session | Data Session | Notes |
|-------|-----------|--------------|-------|
| 1800 Break | `"1800-1815:12345"` | `"1815-0300:12345"` | Days 1-5 (Sun–Thu) for Sunday reopen. Cross-midnight data window. |
| 0300 Break | `"0300-0305:23456"` | `"0305-0830:23456"` | |
| Q1 Break | `"0300-0700:23456"` | `"0700-0830:23456"` | Wide 4-hour OR |
| Market Open | `"0930-0935:23456"` | `"0935-1200:23456"` | |
| Magic Hour | `"0600-0830:23456"` | `"0830-1200:23456"` | |
| 1100 BO | `"1100-1115:23456"` | `"1115-1230:23456"` | |
| Market Open Wide | `"0830-1200:23456"` | `"1200-1600:23456"` | 3.5-hour OR |
| 1400 Break | `"1400-1415:23456"` | `"1415-1600:23456"` | |

### 4.4 Session Detection Pattern

```pine
// Instead of f_in_range(bar_mins, RANGE_START, RANGE_END):
bool in_or  = not na(time(timeframe.period, spec.session_or, spec.tz))
bool in_data = not na(time(timeframe.period, spec.session_data, spec.tz))

// New-day detection: session transition
bool is_new_session = in_or and not in_or[1]
```

**Benefit**: Eliminates manual cross-midnight edge cases. Pine handles DST transitions internally.

### 4.5 What We Keep as Minutes-of-Day

- `f_mins_since(current_min, or_start_min)` — for MFE peak-time tracking (relative offset)
- `f_mins_of_day(time)` — for time-distribution histogram bin placement
- `f_duration(start_min, end_min)` — for histogram width scaling

These stay because they produce *relative* values that Pine sessions don't expose.

---

## 5. Library Decomposition

### 5.1 `RangeSessionLib.pine`

**Purpose:** UDT definitions, preset catalog, range resolution, session detection helpers.

> **Note:** `ExcursionHistory` UDT lives in `StatsLib` (Section 5.3) so that all statistical types and accumulators are co-located. `RangeSessionLib` only contains `RangeSpec` and `RangeState`.

```pine
//@version=6
// @description Range session engine: UDTs, preset resolver, session helpers
library("RangeSessionLib")

// ── Exported UDTs ──
export type RangeSpec
    // ... (see Section 3.1)

export type RangeState
    // ... (see Section 3.2)

// ── Preset Catalog ──
// Returns array<RangeSpec> for a given preset name
export f_resolve_preset(string preset, string custom_start, string custom_end, 
                        string custom_cutoff, string tz) => array<RangeSpec>

// ── Session Helpers ──
export f_build_session_string(int start_min, int end_min, string days) => string
export f_in_session(string session_str, string tz) => bool
export f_is_new_session(string session_str, string tz) => bool
export f_parse_hhmm(string hhmm) => int
export f_mins_of_day(int t, string tz) => int
export f_mins_since(int current_min, int start_min) => int
export f_duration(int start_min, int end_min) => int

// ── State Management ──
export f_new_range_state(RangeSpec spec) => RangeState
export f_reset_daily(RangeState state) => void
```

### 5.2 `DrawingLib.pine`

**Purpose:** Drawing object pool management, OR box rendering, histogram bands, stat lines/labels, day separators.

```pine
//@version=6
library("DrawingLib")

export type DrawingState
    // ... (see Section 3.4)

// ── Pool Management ──
export f_new_drawing_state() => DrawingState
export f_clear_all(DrawingState ds) => void

// ── Rendering Primitives ──
export f_draw_or_box(DrawingState ds, int start_bar, float hi, float lo, 
                     int end_bar, color clr, string style, int width) => box
export f_draw_hist_band(DrawingState ds, int anchor, float p_top, float p_bot, 
                        int width, color clr, int transp) => box
export f_draw_stat_line(DrawingState ds, int x1, float y, int x2, 
                        color clr, string style, int width) => line
export f_draw_stat_label(DrawingState ds, int x, float y, string txt, 
                         color txt_clr, string lbl_style, string sz) => label
export f_draw_day_separator(int bar_idx, float price_hi, float price_lo, 
                            color clr, string style, int width) => line

// ── Utility ──
export f_line_style(string s) => int   // "Dashed"/"Dotted"/"Solid" → line.style_*
export f_table_pos(string s) => string // "Top Right" → position.top_right
export f_text_size(string s) => string // "Small" → size.small
export f_display_size(string s) => string // "tiny" → size.tiny
```

### 5.3 `StatsLib.pine`

**Purpose:** Statistical computations, all excursion analytics, data table rendering. Owns `ExcursionHistory` UDT and all commit/query functions.

```pine
//@version=6
library("StatsLib")

// ── ExcursionHistory UDT ──
export type ExcursionHistory
    // ... (see Section 3.3)

// ── Factory & Commit ──
export f_new_excursion_history(string name) => ExcursionHistory
// Pushes one completed day of RangeState into history arrays
export f_commit_daily(RangeState state, ExcursionHistory hist) => void

// ── Filtering ──
export f_build_filtered(array<float> src) => array<float>  // Remove zeros/na

// ── Aggregation ──
export f_count_at_or_above(array<float> arr, float threshold) => int
export f_compute_streak(array<float> arr, float threshold) => int       // Current streak from tail
export f_compute_max_streak(array<float> arr, float threshold) => int   // Longest streak ever

// ── Percentile Table Row ──
export type PctRow
    int   percentile
    float mfe_pct          // MFE level at this percentile
    int   days_hit         // Days in history where MFE >= mfe_pct
    bool  prev_hit         // Did the most-recent completed day hit this level?
    int   streak           // Current streak of consecutive hits from latest
    int   max_streak       // Longest streak ever
    float conditional_pct  // Given previous level was hit, % that also hit this level (na for first level)

export f_compute_pct_row(array<float> filtered, array<float> full, int pct, 
                         float prev_threshold) => PctRow

// ── MFE Tracking (real-time, runs each bar for the active range) ──
// Single call tracks BOTH bull and bear arms.
// Returns [bull_mfe, bear_mfe, bull_peak_min, bear_peak_min]
export f_track_mfe(float bar_h, float bar_l, int bar_mins_since_or,
                   float bull_ref, float bear_ref,
                   float prev_bull_mfe, float prev_bear_mfe,
                   int prev_bull_peak, int prev_bear_peak) =>
                   [float, float, int, int]

// ── MAE Tracking (real-time, runs each bar) ──

// Absolute MAE — worst adverse from OR boundaries (same direction as MFE refs)
// bull abs MAE = worst below OR_low; bear abs MAE = worst above OR_high
// Returns [bull_abs_mae, bear_abs_mae] as positive % values
export f_track_mae_abs(float bar_h, float bar_l,
                       float or_low, float or_high,
                       float prev_bull_abs, float prev_bear_abs) =>
                       [float, float]

// Pullback MAE — worst retrace across the BREAKOUT LEVEL before peak is finalized
// bull pullback: worst drop below OR_HIGH (breakout level) before bull peak
// bear pullback: worst rise above OR_LOW (breakout level) before bear peak
// Once peak_finalized = true for a direction, stop updating that side.
// Returns [bull_pb_mae, bear_pb_mae] as positive % values
export f_track_mae_pullback(float bar_h, float bar_l,
                            float or_high, float or_low,
                            bool bull_peak_finalized, bool bear_peak_finalized,
                            float prev_bull_pb, float prev_bear_pb) =>
                            [float, float]

// ── Mid Hit Tracking ──
// Touch: high >= or_mid for bull; low <= or_mid for bear
// Returns [hit_bull, hit_bear]
export f_track_mid_hit(float bar_h, float bar_l, float or_mid,
                       bool prev_bull_hit, bool prev_bear_hit) =>
                       [bool, bool]

// ── EV Win ──
// Zero-MFE days: mfe = 0 → returns na (excluded from win rate)
export f_compute_ev_win(float mfe, float ev_target_pct) => bool

// ── R-Multiple ──
// Returns na if mae_abs = 0 or na
export f_compute_r_multiple(float mfe, float mae_abs) => float

// ── MFE Efficiency ──
// mfe / (mfe + abs_mae) — returns na if both zero
export f_compute_mfe_efficiency(float mfe, float mae_abs) => float

// ── Conditional Probability ──
// Of days where data >= lower_threshold, what fraction also reached upper_threshold?
export f_conditional_prob(array<float> data, float lower_threshold,
                          float upper_threshold) => float

// ── Reversal Flag ──
// is_bull: True if checking bull reversal (MFE >= p50 then close below OR_low)
//          False if checking bear reversal (MFE >= p50 then close above OR_high)
export f_is_reversal(float peak_mfe, float p50_mfe,
                     float session_final_price, float or_boundary,
                     bool is_bull) => bool

// ── DOW Stats ──
// Returns [hit_rate, avg_mfe, ev_win_rate, session_count] for a given DOW
// Hit rate = % of sessions where MFE >= ev_target (uses ev_win arrays)
export f_dow_stats(array<float> mfe, array<int> dow,
                   array<bool> ev_wins, int target_dow) =>
                   [float, float, float, int]

// ── Session Continuation Rate ──
// % of days where bull_mfe > bear_mfe
export f_continuation_rate(array<float> mfe_bull, array<float> mfe_bear) => float

// ── Fakeout Classification ──
// Determined at session commit time — not real-time
// close_at_cutoff: last close of the data session
// Returns [fakeout_bull, fakeout_bear, double_break]
export f_classify_fakeout(bool trig_bull, bool trig_bear,
                          float close_at_cutoff,
                          float or_high, float or_low) =>
                          [bool, bool, bool]

// ── Fakeout Reversal Depth ──
// session_low_data / session_high_data: running extremes during data session
// Returns reversal depth as % from OR level (0 if price never crossed it)
// Bull: max(0, (or_high - session_low) / or_high * 100) if fakeout_bull, else na
// Bear: max(0, (session_high - or_low) / or_low * 100) if fakeout_bear, else na
export f_fakeout_reversal_depth(bool fakeout_bull, bool fakeout_bear,
                                float session_low_data, float session_high_data,
                                float or_high, float or_low) =>
                                [float, float]

// ── Fakeout Stats ──
// Filters mfe/reversal arrays to fakeout days only, returns [p25, p50, p75, p90] for each
// mfe_arr: full mfe_bull or mfe_bear array; mask: fakeout_bull or fakeout_bear
export f_fakeout_mfe_percentiles(array<float> mfe_arr, array<bool> mask) =>
                                 [float, float, float, float]
// returns [p25, p50, p75, p90] of reversal depth on fakeout days
export f_fakeout_reversal_percentiles(array<float> reversal_arr, array<bool> mask) =>
                                      [float, float, float, float]
// returns [p25, p50, p75, p90]

// Double-break rate: % of triggered sessions that had both sides break
export f_double_break_rate(array<bool> double_break,
                           array<bool> trig_bull,
                           array<bool> trig_bear) => float

// ── Display Helpers ──
export f_tf_display() => string
export f_day_full(int dow) => string
export f_pct_fmt(float v) => string   // Formats float as "0.42%" string
```

---

## 6. Stat Lines & Named Percentile Levels

### 6.1 Named Percentile Levels

Four configurable percentile levels are used across Phase 1 for breakout confirmation, targets, and invalidation. All are input-configurable (dropdown or integer input in the main script).

| Name | Default | Pine Input Key | Purpose |
|------|---------|---------------|---------|
| **Confirm** | P20 | `input_pct_confirm` | BO Cashflow threshold — first confirmation of a live breakout |
| **Target1** | P50 | `input_pct_target1` | Primary target / median MFE |
| **Target2** | P75 | `input_pct_target2` | Secondary target |
| **Stretch** | P90 | `input_pct_stretch` | Max MFE / extended target |
| **Invalidation** | P80 MAE | `input_pct_invalidation` | Pullback MAE exceeds P80 → breakout invalidated |

> The Invalidation level applies to the **pullback MAE distribution**, not the MFE distribution.

### 6.2 Live Stat Lines (Phase 1)

Five horizontal lines are drawn on the chart, extending **forward from today's OR anchor**. These are derived from the historical `ExcursionHistory` of the focused range.

| Line | Source | Label | Style |
|------|--------|-------|-------|
| **P20 "BO Cashflow"** | `array.percentile_nearest_rank(mfe_bull_filtered, 20)` | `"P20 BO Cashflow: 0.18%"` | Dotted, `input_pct_color_confirm` |
| **Median MFE** | `array.percentile_nearest_rank(mfe_bull_filtered, 50)` | `"Median: 0.37%"` | Solid (thin), bull color |
| **Avg MFE** | `array.avg(mfe_bull_filtered)` | `"Avg: 0.41%"` | Dashed, bull color |
| **P90 "Max MFE"** | `array.percentile_nearest_rank(mfe_bull_filtered, 90)` | `"P90 Max MFE: 0.84%"` | Dotted, `input_pct_color_stretch` |
| **Range Mid** | `(or_high + or_low) / 2` | `"Mid [hit 62%]"` | Dashed, neutral color |

- Bull and bear sides each get their own set of stat lines (5 lines × 2 directions = 10 lines per sub-range on chart).
- The **Range Mid** line is shared (one line) — hit% shows the higher of bull/bear hit rate, or combined: `(mid_hit_bull_count + mid_hit_bear_count) / (2 × total_sessions)`.
- Lines extend from `or_start_bar` of today's complete OR to `barstate.last_bar_index + 20` (configurable right-extension).

### 6.3 Invalidation Level

The P80 pullback MAE level is drawn as a special annotation in **Phase 2** (MAE histogram view). In Phase 1, the invalidation percentile is **captured and stored** in `ExcursionHistory`'s pullback MAE arrays, but the visual invalidation band is deferred to Phase 2.

### 6.4 Fakeout Stat Lines (Phase 1 — data capture; Phase 2 — visual rendering)

Five additional reference levels per direction, derived from the **fakeout-filtered MFE and reversal depth distributions**. These are computed in Phase 1 and stored; visual rendering as chart overlays is in Phase 2.

| Level | Source | Trading Use |
|-------|--------|-------------|
| **P75 Fake MFE** — "BO Confirm" | `percentile(mfe_bull where fakeout_bull, 75)` | Price above this → real breakout (only 25% of fakes get this far) |
| **P50 Fake MFE** — "Decision Zone" | `percentile(mfe_bull where fakeout_bull, 50)` | Mean reversion entry OR real breakout continuation decision |
| **P25 Reversal** | `percentile(fakeout_reversal_bull, 25)` | Near-side reversal target after fake (typical reaction) |
| **P50 Reversal** — "Reversal Zone" | `percentile(fakeout_reversal_bull, 50)` | Median post-fake counter-move depth |
| **P90 Reversal** — "Max Reversal" | `percentile(fakeout_reversal_bull, 90)` | Danger zone / max adverse for shorts fading the fake |

> All five levels apply symmetrically to the bear side (using `fakeout_bear` and `fakeout_reversal_bear`).

**Distinction from `reversal_flag`:** `reversal_flag` requires MFE ≥ P50 first (a *real-looking* move that fails). Fakeout classification requires only that the OR boundary was breached and close returned inside — no minimum MFE threshold. These are complementary, not redundant.

### 6.4 On-Chart Color Scheme

```
Bull stat lines:      Shaded variations of `input_bull_color`
Bear stat lines:      Shaded variations of `input_bear_color`
Range Mid:            Light gray / neutral
P20 Confirm line:     Configurable (suggest teal/green)
P90 Stretch line:     Configurable (suggest amber/orange)
```

---

## 7. Data Table Views

The data table is rendered at `barstate.islast` only. The view is selected via a dropdown input in the indicator's settings panel.

### 7.1 View Toggle

```pine
input_table_view = input.string("MFE View", "Table View",
    options=["MFE View", "MAE View", "DOW View", "Fakeout View"])
```

The table auto-focuses on whichever sub-range is **currently inside its OR or data window** on the realtime bar. If no range is live, it defaults to the most recently completed range.

### 7.2 MFE View Columns

| Column | Description |
|--------|-------------|
| Level | Confirm / T1 / T2 / Stretch (with percentile label) |
| Price | Absolute price of MFE level from today's OR anchor |
| Hit% | % of historical sessions where MFE ≥ this level |
| Cond% | Conditional: given previous level hit, % also hit this level (na for Confirm row) |
| Streak | Current / Max streak of consecutive hits |

### 7.3 MAE View Columns

| Column | Description |
|--------|-------------|
| Level | Confirm / T1 / T2 / Stretch |
| Pullback MAE% | Avg historical pullback MAE at each MFE tier (% of price) |
| Abs MAE% | Avg absolute MAE at each MFE tier |
| R-Multiple | Avg `MFE / abs_MAE` at each tier |
| EV Win% | % of days in this tier where MFE ≥ ev_target_pct |

### 7.4 DOW View Columns

| Column | Description |
|--------|-------------|
| DOW | Mon / Tue / Wed / Thu / Fri |
| Hit% | % of sessions on this DOW where MFE ≥ Confirm (P20) |
| Avg MFE% | Average MFE on this DOW |
| EV Win% | % of sessions on this DOW flagged as EV wins |
| Sessions | Count of historical sessions on this DOW |

### 7.5 Fakeout View Columns

| Column | Description |
|--------|-------------|
| Type | Pure Fake (MFE < P20) / Trap (MFE ≥ P20) / Double Break |
| Fake Rate | % of triggered sessions that were fakeouts |
| P50 Fake MFE% | Median how far fakes travel (decision zone) |
| P75 Fake MFE% | 75th pct — real BO confirmed above this |
| P50 Reversal% | Median counter-move depth from OR level |
| P90 Reversal% | Max reversal (danger zone for shorts) |
| Dbl Break% | % of all sessions with both sides triggered |

---

## 8. Main Script Architecture (`DailyNYLevelsV5.pine`)

### 6.1 Module Map

```
MODULE 1: Imports & Inputs
    - import RangeSessionLib, DrawingLib, StatsLib
    - Dropdown: "Overnight / 0300 Transfer" | "Pre-Market / Q1" | "Intraday Breakouts" | "Custom"
    - Custom HHMM inputs (conditional on dropdown = "Custom")
    - Style, MFE, Time Dist, Separator, Info, Debug, Data Table inputs (same as V4.1)

MODULE 2: Preset Resolution
    - Call f_resolve_preset() → array<RangeSpec>
    - Initialize array<RangeState> and array<ExcursionHistory> (once, on bar 0)

MODULE 3: Session Engine Loop
    - For each RangeSpec:
        a. Detect new session (OR window start)
        b. Commit previous day's data if uncommitted
        c. Reset daily state
        d. Track OR high/low (LTF security + current bar fallback)
        e. Detect OR completion
        f. Set reference levels

MODULE 4: MFE Tracking Loop
    - For each active RangeState where ref_set == true:
        a. Track MFE using LTF bars (or current bar fallback)
        b. Track pivots

MODULE 5: Daily Commit
    - Detect data-session end
    - Push daily metrics to ExcursionHistory

MODULE 6: Rendering (barstate.islast only)
    - Clear all drawing pools
    - For each RangeState:
        a. Draw OR box
        b. Draw MFE histogram bands
        c. Draw stat lines (avg, median)
        d. Draw time distribution histogram
    - Draw day separators
    - Draw info box
    - Draw data table
```

### 6.2 Multi-Range Rendering Strategy

When a compound preset has 3 sub-ranges active simultaneously:

- **OR Boxes**: Each sub-range gets its own box, colored by its `RangeSpec.box_color` (distinct per sub-range).
- **MFE Histograms**: Anchored to each range's `or_start_bar`. Since sub-ranges start at different times, histograms naturally offset.
- **Stat Lines**: Each range's avg/median lines span from its own anchor to its own cutoff boundary.
- **Data Table**: Shows the currently focused range (user can pick via a secondary dropdown or we show all rows grouped by range name).
- **Time Distribution**: Positioned below the lowest MFE histogram, per range.

**Visual conflict mitigation:**
- Sub-ranges within a preset get automatically assigned distinct alpha/hue variations of the global bull/bear colors.
- Labels include the range name prefix (e.g., "1800 Break — 0.42% AVG").

---

## 9. Migration Mapping (V4.1 → V5)

| V4.1 Location | V5 Location | Change |
|----------------|-------------|--------|
| MODULE 1: Inputs (booleans) | MODULE 1: Single dropdown | Replace 9 booleans with 1 dropdown |
| MODULE 2: Utility functions | `DrawingLib`, `StatsLib`, `RangeSessionLib` | Extract to libraries |
| MODULE 3: Session detection | `RangeSessionLib.f_in_session()` + session strings | Replace manual minute math |
| MODULE 4: Opening Range | MODULE 3: Session Engine Loop (per RangeSpec) | Generalize to N ranges |
| MODULE 5: Reference levels | MODULE 3: Session Engine Loop (ref_set step) | Folded into engine |
| MODULE 6: MFE tracking | MODULE 4: MFE Tracking Loop | Per-range iteration |
| MODULE 7: Daily commit | MODULE 5: Daily Commit | Per-range commit |
| MODULE 8: Day separators | MODULE 6: Rendering (unchanged logic) | DrawingLib helpers |
| MODULE 9: Info box | MODULE 6: Rendering (add range name) | Minor enhancement |
| MODULE 10: MFE histogram | MODULE 6: Rendering (per range) | DrawingLib + StatsLib |
| MODULE 11: Time distribution | MODULE 6: Rendering (per range) | DrawingLib |
| MODULE 12: Data table | MODULE 6: Rendering (per range, grouped rows) | StatsLib |
| MODULE 13: Debug | MODULE 6: Rendering (enhanced with range name) | Unchanged logic |

---

## 10. LTF Data Handling

The current script uses `request.security_lower_tf(syminfo.tickerid, "1", ...)` to get 1-minute granularity within higher-TF bars. This approach is preserved in V5:

- The LTF arrays (`ltf_high_arr`, `ltf_low_arr`, etc.) are fetched **once** per bar.
- The Session Engine and MFE Tracking loops iterate the same LTF arrays but apply different session filters per `RangeSpec`.
- **Performance note**: With 3 sub-ranges, we iterate the LTF array 3x per bar. This is acceptable since the array is typically small (e.g., 5 elements for a 5m chart).

---

## 11. Pine Library Constraints & Considerations

| Constraint | Impact | Mitigation |
|-----------|--------|------------|
| Libraries cannot use `input.*` | All inputs stay in main script | Pass config values as function parameters |
| Libraries cannot use `request.*` | LTF security call stays in main script | Pass LTF arrays to engine functions |
| Libraries cannot use global `bar_index`, `time`, etc. | Pass as parameters | All library functions are pure (inputs → outputs) |
| Library functions are **stateless** | State (arrays, vars) stays in main script | Libraries return values; main script manages persistence |
| Library UDTs are **exported** but instances are created in the importing script | Main script calls `RangeSpec.new(...)` | Factory functions can wrap `.new()` for convenience |
| Max 15 library imports per script | We use 3 libraries | Well within limit |

---

## 12. Implementation Sequence

### Step 1: Create Library Stubs
1. `lib/RangeSessionLib.pine` — UDT exports (`RangeSpec`, `RangeState`) + stub functions
2. `lib/DrawingLib.pine` — `DrawingState` UDT + stub renderers
3. `lib/StatsLib.pine` — `ExcursionHistory` UDT + stub computations

### Step 2: Implement RangeSessionLib
1. `RangeSpec` and `RangeState` UDTs (see Section 3.1 and 3.2 — all fields including `ev_target_pct`, `or_mid`, MAE trackers, mid hit booleans)
2. `f_parse_hhmm`, `f_build_session_string`, `f_in_session`, `f_duration`, `f_mins_since`, `f_mins_of_day`
3. `f_resolve_preset` — hardcoded preset catalog (all 8 sub-ranges + Custom)
4. `f_new_range_state`, `f_reset_daily`

### Step 3: Implement DrawingLib
1. `f_clear_all`, pool management
2. `f_draw_or_box`, `f_draw_hist_band`, `f_draw_stat_line`, `f_draw_stat_label`
3. `f_draw_day_separator`, `f_line_style`, `f_table_pos`, `f_text_size`
4. `f_display_size`

### Step 4: Implement StatsLib
1. `ExcursionHistory` UDT with all Phase 1 array fields (see Section 3.3)
2. `f_new_excursion_history`, `f_commit_daily` (pushes full RangeState → history)
3. `f_build_filtered`, aggregation helpers (`f_count_at_or_above`, streak helpers)
4. **MFE tracking**: `f_track_mfe` (returns both bull + bear each bar)
5. **MAE tracking**: `f_track_mae_abs`, `f_track_mae_pullback`
6. **Mid hit tracking**: `f_track_mid_hit`
7. **Fakeout tracking** (real-time, runs each bar during data session):
   - Update `entry_triggered_bull/bear` when OR boundary is broken
   - Update `session_low_data` / `session_high_data` as running extremes
   - At commit: call `f_classify_fakeout` → `fakeout_bull/bear/double_break`
   - At commit: call `f_fakeout_reversal_depth` → `fakeout_reversal_bull/bear`
8. **Derived metrics**: `f_compute_ev_win`, `f_compute_r_multiple`, `f_compute_mfe_efficiency`, `f_is_reversal`
9. **Aggregated stats**: `f_conditional_prob`, `f_dow_stats`, `f_continuation_rate`
10. **Fakeout stats**: `f_fakeout_mfe_percentiles`, `f_fakeout_reversal_percentiles`, `f_double_break_rate`
11. `f_compute_pct_row` with `conditional_pct` field
12. Display helpers: `f_tf_display`, `f_day_full`, `f_pct_fmt`

### Step 5: Build Main Script — Custom Mode, MFE Parity Gate
1. Imports + inputs (all V4.1 inputs preserved; add `ev_target_pct`, named percentile inputs, `table_view` dropdown)
2. Preset resolution → single `RangeSpec` (Custom mode default)
3. Session engine (single range) — OR building, OR complete, ref levels, `or_mid`, Transfer direction
4. MFE + MAE tracking per bar (calls `f_track_mfe`, `f_track_mae_abs`, `f_track_mae_pullback`, `f_track_mid_hit`)
5. Daily commit to `ExcursionHistory`
6. Rendering: OR box, MFE histogram bands (parity match), Avg + Median stat lines
7. **Add Phase 1 stat lines**: P20 "BO Cashflow", Median, Avg, P90 "Max MFE", Range Mid (dashed + hit% label)
8. **Acceptance gate**: V4.1 vs V5 Custom mode — identical OR boxes, identical MFE histogram bands, identical data table values

### Step 6: Data Table (all four views)
1. Wire `table_view` dropdown → MFE View / MAE View / DOW View / Fakeout View render paths
2. Auto-focus on live range (uses `or_building` / `or_complete` flags)
3. **MFE View**: Level / Price / Hit% / Cond% / Streak columns
4. **MAE View**: Level / Pullback MAE% / Abs MAE% / R-Multiple / EV Win% columns
5. **DOW View**: DOW summary rows using `f_dow_stats`
6. **Fakeout View**: Type / Fake Rate / P50+P75 Fake MFE% / P50+P90 Reversal% / Dbl Break% columns (uses `f_fakeout_mfe_percentiles`, `f_fakeout_reversal_percentiles`)
7. **Acceptance gate**: all four views render without Pine runtime errors; Fakeout View fake rate + double-break rate match manual count

### Step 7: Enable Compound Presets
1. Wire dropdown options to multi-range resolution
2. Multi-range session engine loop (all ranges each bar)
3. Multi-range MAE + mid tracking
4. Multi-range rendering with visual conflict mitigation (hue offsets per sub-range)
5. Data table auto-focus on the live sub-range
6. **Acceptance gate**: each preset variant shows all sub-ranges correctly; 1800 Break fires on Sun–Thu only

### Step 8: Cleanup & Polish
1. Debug mode enhancements (range name in all log output)
2. Info box: show active preset name, sub-range count, EV target setting
3. Edge case testing: cross-midnight, DST transitions, weekend bars, zero-MFE days
4. Performance profiling (drawing object counts, LTF iteration cost with 3 sub-ranges)

---

## 13. Acceptance Tests

| Test | Method | Pass Criteria |
|------|--------|---------------|
| Custom parity | Apply V4.1 and V5 to same chart, same custom settings | Identical OR boxes, MFE histogram bands, data table values (within float precision) |
| MAE capture | Inspect debug table on a day with known OR breach | Abs MAE and pullback MAE stored; R-multiple = MFE/abs_MAE; EV win flag correct |
| Mid hit tracking | Check session where price crossed OR midpoint | `mid_hit_bull` or `mid_hit_bear` true; Mid stat line label shows correct hit% |
| Stat lines | Load on any chart with ≥30 sessions | All 5 stat lines (P20/Median/Avg/P90/Mid) visible; labels include value and name |
| EV win | `ev_target_pct = 0.3`, MFE = 0.31% | `ev_win_bull = true`; MFE = 0% side shows `na` (not false) |
| Preset A rendering | Select "Overnight / 0300 Transfer" | Two OR boxes (1800 Break + 0300 Break) visible; Transfer fires with correct direction |
| Preset C rendering | Select "Intraday Breakouts" | Three OR boxes visible with distinct hue colors |
| 1800 Break session days | Check Sunday bar on live chart | 1800 Break OR box builds on Sunday evening (Pine day 1) |
| Cross-midnight | 1800 Break range on 5m chart, date stamp | Date stamp on completed session = Monday date (cutoff date convention) |
| DST transition | Navigate to March/November DST change | No broken sessions or missing data |
| DOW View | Open DOW View in table on >60 session range | All 5 DOW rows present; total sessions across rows = total history count |
| Zero-MFE exclusion | Inspect DOW row for low-session DOW | MFE=0 days not counted in EV Win%; excluded from filtered stats |
| Drawing cleanup | Switch timeframes 5× | No stale/orphaned boxes, lines, or labels |
| Object limits | Load on daily chart, 2000+ bars | No "exceeded max objects" runtime errors |

---

## 14. Open Questions (Phase 1 Specific)

All questions from the original design have been resolved through exhaustive Q&A across 4 question batches (2026-04-17 session). No open items remain for Phase 1 implementation.

| ID | Question | Resolution |
|----|----------|-----------|
| P1-1 | Should all sub-ranges in a preset render simultaneously? | **YES** — all sub-ranges active simultaneously; distinct hue offsets per sub-range |
| P1-2 | 0300 Transfer: how is direction determined? | **5-min OR (0300–0305).** Bull if 1800 open price > 0300 OR close; bear vice versa. Skip day if 1800 open unavailable. |
| P1-3 | Pine library publishing: private or local? | **Code locally first; publish to TradingView manually** (3 private libraries) |
| P1-4 | Data table: all sub-ranges or focused? | **Toggle dropdown in settings.** Auto-focuses on the sub-range currently in its OR/data window. |
| P1-5 | Per-range colors: auto-derived or configurable? | **Auto-generated hue offsets** from global bull/bear colors per sub-range |

---

**Last Updated:** 2026-04-17 (v2.0 — all Phase 1 design questions resolved; UDTs, library APIs, stat lines, data table views, implementation sequence fully updated)
