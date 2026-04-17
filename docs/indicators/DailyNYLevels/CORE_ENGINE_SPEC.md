# Core Engine Spec — Daily NY Levels

Version: 1.0  
Date: 2026-04-17  
Scope: Platform-agnostic algorithm contract for Pine Script and NinjaScript implementations.

---

## 1. Purpose

This document defines the canonical algorithm behavior for:
- Session/range detection
- OR construction
- MFE/MAE tracking (absolute and pullback)
- Mid-hit tracking
- Fakeout classification
- Core derived metrics

Platform implementations may differ in APIs and rendering, but must preserve this behavior.

---

## 2. Time and Normalization Contract

1. All session logic is evaluated in EST/ET context.
2. Before applying algorithms, each bar is represented as:
   - `bar_time_est`
   - `bar_mins_of_day` in [0, 1439]
   - `bar_dow` in Pine day semantics (Sun=1 ... Sat=7) or mapped equivalent.
3. Price-based excursion metrics are normalized as percentages:
   - `pct(a, ref) = ((a - ref) / ref) * 100.0`

---

## 3. Core Data Contracts

## 3.1 RangeSpec (input/static)
- `name`
- `preset_group`
- `or_start_min`, `or_end_min`, `cutoff_min`
- `session_or`, `session_data`, `tz` (Pine-native metadata)
- `is_transfer`
- `ev_target_pct`

## 3.2 RangeState (mutable/day)
- OR values: `or_high`, `or_low`, `or_last_close`, `or_complete`, `or_building`
- refs: `bull_ref=or_high`, `bear_ref=or_low`, `or_mid`
- MFE: `daily_bull_mfe`, `daily_bear_mfe`, `daily_bull_peak_min`, `daily_bear_peak_min`
- MAE abs: `daily_mae_bull_abs`, `daily_mae_bear_abs`
- MAE pullback: `daily_mae_bull_pb`, `daily_mae_bear_pb`, trackers
- Mid-hit: `mid_hit_bull`, `mid_hit_bear`
- Fakeout inputs: `entry_triggered_bull`, `entry_triggered_bear`, `session_low_data`, `session_high_data`, `close_at_cutoff`
- Commit flag: `is_committed`

## 3.3 ExcursionHistory (output/accumulated)
Per-day arrays for MFE/MAE, peaks, hit flags, DOW, EV flags, fakeout flags, and derived metrics.

---

## 4. Session Detection Algorithm

Implementations must support two equivalent paths.

## 4.1 Pine-native path
- `in_or = time(session_or, tz) != na`
- `in_data = time(session_data, tz) != na`
- `is_new_session = in_or and not in_or_prev`

## 4.2 Portable minute-based path

Inputs:
- `bar_mins`, `start_min`, `end_min`, `crosses_midnight`

Pseudocode:

```text
if not crosses_midnight:
    in_session = (bar_mins >= start_min) and (bar_mins < end_min)
else:
    in_session = (bar_mins >= start_min) or (bar_mins < end_min)
```

Cross-midnight rule:
- `crosses_midnight = end_min < start_min`

Session transition:
- `is_new_session = in_or and not prev_in_or`

---

## 5. OR Construction Algorithm

During OR window (`in_or == true`):

```text
if session just started:
    reset daily state
    or_high = bar_high
    or_low = bar_low
    or_last_close = bar_close
    or_building = true
else:
    or_high = max(or_high, bar_high)
    or_low = min(or_low, bar_low)
    or_last_close = bar_close
```

When OR window ends:

```text
or_complete = true
or_building = false
bull_ref = or_high
bear_ref = or_low
or_mid = (or_high + or_low) / 2
ref_set = true
```

---

## 6. MFE Tracking Algorithm

For each bar in data window after refs are set:

```text
bull_exc = max(0, pct(bar_high, bull_ref))
bear_exc = max(0, pct(bear_ref, bar_low))

if bull_exc > daily_bull_mfe:
    daily_bull_mfe = bull_exc
    daily_bull_peak_min = mins_since_or_start

if bear_exc > daily_bear_mfe:
    daily_bear_mfe = bear_exc
    daily_bear_peak_min = mins_since_or_start
```

---

## 7. MAE Tracking Algorithm

## 7.1 Absolute MAE

```text
bull_abs = max(0, pct(or_low, bar_low)) transformed to positive adverse %
bear_abs = max(0, pct(bar_high, or_high)) transformed to positive adverse %

daily_mae_bull_abs = max(daily_mae_bull_abs, bull_abs)
daily_mae_bear_abs = max(daily_mae_bear_abs, bear_abs)
```

Equivalent formulas:
- bull absolute adverse: `max(0, (or_low - bar_low) / or_low * 100)`
- bear absolute adverse: `max(0, (bar_high - or_high) / or_high * 100)`

## 7.2 Pullback MAE (before peak finalization)

- Bull pullback MAE reference level: `OR_HIGH`
- Bear pullback MAE reference level: `OR_LOW`

```text
bull_pb = max(0, (or_high - bar_low) / or_high * 100)
bear_pb = max(0, (bar_high - or_low) / or_low * 100)

if bull peak not finalized:
    daily_mae_bull_pb = max(daily_mae_bull_pb, bull_pb)
if bear peak not finalized:
    daily_mae_bear_pb = max(daily_mae_bear_pb, bear_pb)
```

Peak finalization policy is implementation-defined but must be deterministic and consistent in backtest/live modes.

---

## 8. Mid-Hit Tracking Algorithm

For each data-window bar:

```text
if bar_high >= or_mid:
    mid_hit_bull = true
if bar_low <= or_mid:
    mid_hit_bear = true
```

Once true, flags remain true for the rest of the session day.

---

## 9. Fakeout Classification Algorithm

At/after cutoff, compute using final session close and trigger flags.

Inputs:
- `entry_triggered_bull` (any high > OR_HIGH)
- `entry_triggered_bear` (any low < OR_LOW)
- `close_at_cutoff`

Pseudocode:

```text
fakeout_bull = entry_triggered_bull and (close_at_cutoff <= or_high)
fakeout_bear = entry_triggered_bear and (close_at_cutoff >= or_low)
double_break = entry_triggered_bull and entry_triggered_bear
```

Reversal depth on fakeout days:

```text
fakeout_reversal_bull = if fakeout_bull then max(0, (or_high - session_low_data) / or_high * 100) else na
fakeout_reversal_bear = if fakeout_bear then max(0, (session_high_data - or_low) / or_low * 100) else na
```

---

## 10. Commit Algorithm (End of Session)

When data window closes and `is_committed == false`:

1. Compute derived metrics:
   - `ev_win_bull = na if daily_bull_mfe == 0 else daily_bull_mfe >= ev_target_pct`
   - `ev_win_bear = na if daily_bear_mfe == 0 else daily_bear_mfe >= ev_target_pct`
   - `r_multiple_bull = daily_bull_mfe / daily_mae_bull_abs` (na if denominator is 0/na)
   - `r_multiple_bear = daily_bear_mfe / daily_mae_bear_abs`
   - `direction_flag = +1 if bull_mfe > bear_mfe, -1 if bear_mfe > bull_mfe, else 0`
2. Compute fakeout outputs (Section 9).
3. Append all day values to `ExcursionHistory` arrays in a single atomic commit step.
4. Set `is_committed = true`.

---

## 11. Percentiles and Statistics Contract

1. Unless explicitly specified otherwise, percentile method is nearest-rank.
2. Filtering rules:
   - For MFE percentile stats: remove `na`; remove zeros when the metric implies non-move exclusion.
   - For EV win rate: zero-MFE days are excluded by storing `na` in EV flag.
3. Conditional probability:

```text
P(hit upper | hit lower) = count(values >= upper and >= lower) / count(values >= lower)
```

4. Named levels map:
- Confirm: P20
- Target1: P50
- Target2: P75
- Stretch: P90
- Pullback invalidation: P80 of pullback MAE distribution

---

## 12. Platform Implementation Notes

## 12.1 Pine Script
- May use session-string + `time()` path directly.
- Drawing object management is handled in `PineDrawingLib`.
- LTF ingestion may use `request.security_lower_tf`.

## 12.2 NinjaScript
- Implement minute-based session helper contract from Section 4.2.
- Implement rendering separately (no dependency on Pine drawing objects).
- Maintain behavioral parity with this spec; API differences are adapter-level concerns.

---

## 13. Parity Validation Requirements

Each platform implementation must pass:
1. Session inclusion parity for all presets, including cross-midnight windows.
2. OR high/low parity for the same bar stream.
3. MFE/MAE parity within floating-point tolerance.
4. Fakeout flags and reversal-depth parity.
5. Percentile-level parity for sufficiently large history windows.

---

This file is the canonical engine contract for future phases.
