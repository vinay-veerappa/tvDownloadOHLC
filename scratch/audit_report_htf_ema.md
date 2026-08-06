## Independent Audit Report: HTF Weekly EMA(5) Excursion Analysis

**Component**: `htf_ema_analysis.py` + `v_03_htf_ema_pa.py`  
**Auditor**: Senior Quantitative Trading Auditor & Python Engineer  
**Date**: 2025-03-23  
**Severity Scale**: Critical / High / Medium / Low / Informational

---

### 1. Rule Fidelity & Domain Correctness

| # | Finding | Severity | Detail |
|---|---------|----------|--------|
| 1.1 | **Undefined variable `last_bar_session`** | **Critical** | In `compute_htf_ema_analysis`, line `eval_date = t_dt if target_date else last_bar_session` references a name that is never defined. This will raise `NameError` whenever `target_date` is `None`, crashing the entire analysis. |
| 1.2 | **Incorrect prior completed week selection** | **Critical** | The code always uses `df_wk.iloc[-2]` as the “prior completed week”. If the target date is a Friday after the close, the last weekly bar (`iloc[-1]`) is actually the most recently completed week. The blueprint requires the **most recent completed Weekly EMA(5)**. Using `iloc[-2]` in that case skips the true prior week and uses the week before, producing wrong excursion distances and invalidating all downstream statistics. |
| 1.3 | **52‑week lookback yields only 51 excursions** | **High** | The lookback slice `df_wk.iloc[-53:-1]` gives 52 weekly bars, but the loop `for i in range(1, len(lookback_wks))` produces only 51 excursion pairs. The blueprint mandates “exactly 52 prior weeks” of excursion data. To obtain 52 excursions, 53 weekly bars are required (52 pairs). The current implementation is off by one, systematically under‑sampling the distribution. |
| 1.4 | **Mode tie‑breaking not implemented** | **High** | The blueprint specifies: “If multiple bins tie for highest frequency, the bin center closest to the arithmetic Mean is selected as the Mode.” The code simply takes `mode_counts.index[0]` (the first bin in ascending order), ignoring ties and the mean‑proximity rule. This can silently select a wrong mode, distorting the magnet‑zone analysis. |
| 1.5 | **Hit‑rate classification (Good/Fair/Rare) missing** | **High** | The blueprint defines a three‑tier hit‑rate classification (≥66.67%, 33.33–66.67%, <33.33%) that is completely absent from the output. This classification is a core part of Mickey’s methodology for judging exhaustion vs. continuation. |
| 1.6 | **NFP 08:30 candle boundaries not returned by analysis function** | **Medium** | The blueprint states: “Records the highest high and lowest low of the pre‑market 08:30 AM EST NFP release candle.” The analysis function only sets a boolean `is_nfp_friday`. The actual high/low are computed in the separate verification script, but the primary analysis engine should expose them as part of its contract. |
| 1.7 | **Sunday 18:00 ET and Tuesday 09:30 AM anchors not implemented** | **Medium** | The blueprint explicitly lists these as “Key Intraday Anchors”. Neither the analysis function nor the verification script computes or verifies them. The verification script’s docstring mentions them but the code does nothing. |
| 1.8 | **Excursion formulas are mathematically correct** | ✅ | `dUp = max(0, (High - EMA5)/EMA5 * 100)` and `dDn = max(0, (EMA5 - Low)/EMA5 * 100)` are implemented exactly as specified. |
| 1.9 | **2%–3% magnet zone detection is correct** | ✅ | `2.0 <= abs(dist_pct) <= 3.0` matches the blueprint. |
| 1.10 | **Zero‑bin purge and 0.5% binning are correct** | ✅ | Values ≤0.001% are excluded; bins are created with `np.arange(0, max+1, 0.5)`. |

---

### 2. Edge Cases & Failure Modes

| # | Finding | Severity | Detail |
|---|---------|----------|--------|
| 2.1 | **Insufficient data for 52‑week lookback** | **High** | The code only checks `len(df_1d) < 15` and `len(df_wk) < 5`. A proper 52‑week excursion analysis requires at least 53 completed weekly bars. If fewer are available, the function silently returns partial (and misleading) statistics. It should either raise a clear error or return an empty result with a warning. |
| 2.2 | **Session date logic may misclassify bars** | **Medium** | The rule `if dt.hour >= 17: next day` is a heuristic that can mislabel bars between 17:00 and 18:00 ET. For equity index futures, the Globex session runs 18:00–17:00 ET. A bar at 17:30 belongs to the *same* session day, not the next. This can cause the target‑date filter to include/exclude bars incorrectly, shifting the weekly resample boundaries. |
| 2.3 | **Timezone fragility** | **Medium** | The code assumes data is either already in `US/Eastern` or in `UTC`. If the parquet file contains a different timezone (e.g., `Europe/London`), the `tz_localize('UTC')` will fail or produce wrong times. A robust loader should handle arbitrary timezones or enforce a strict contract. |
| 2.4 | **NFP Friday detection depends on undefined variable** | **Critical** | As noted in 1.1, the `eval_date` fallback crashes when `target_date` is `None`. This makes the entire NFP flag unusable in automated batch runs. |
| 2.5 | **Verification script loads 1m data for full day but may miss NFP candle** | **Low** | The script slices 1m bars from 00:00 to 16:00 ET. If the data source does not provide pre‑market bars (e.g., only RTH 09:30–16:00), the 08:30 NFP candle will be empty. The script handles this gracefully, but the user may not realise the data is incomplete. |
| 2.6 | **No handling of market holidays** | **Low** | On holidays (e.g., Thanksgiving Friday), the “first Friday of the month” may not be a trading day. The NFP release still occurs, but the daily data may be missing. The code does not account for this, potentially misclassifying or crashing. |

---

### 3. Code Quality, Vectorization & Performance

| # | Finding | Severity | Detail |
|---|---------|----------|--------|
| 3.1 | **Non‑vectorised excursion loop** | **Medium** | The `for i in range(1, len(lookback_wks))` loop computes excursions one week at a time. This can be fully vectorised using `df_wk['ema5'].shift(1)` and column operations, improving readability and performance (though the impact is negligible for 52 rows, it sets a bad precedent). |
| 3.2 | **List comprehension for session_date** | **Low** | `df_1d["session_date"] = [ _session_date(t) for t in df_1d.index ]` is not vectorised but acceptable for daily data. Could be replaced with a vectorised `np.where` for consistency. |
| 3.3 | **Mutable default argument risk** | **Low** | `verify_htf_ema_pa(sample_dates: list[str] = None)` is safe because `None` is used, but the pattern is fragile. Consider using `Optional[list[str]]` and an immutable default. |
| 3.4 | **Unused imports** | **Informational** | `pytz` is imported but `ET` is defined but never used in `htf_ema_analysis.py`. The verification script re‑defines `ET`. |
| 3.5 | **Type hints are incomplete** | **Low** | The return dict is typed as `dict[str, Any]`. A `TypedDict` would improve maintainability and catch key errors. |
| 3.6 | **No logging of critical failures** | **Medium** | When the daily parquet is missing or data is insufficient, the function returns a default dict with a `log.warning`. However, the undefined variable crash (1.1) produces no log – just a stack trace. All error paths should be logged. |

---

### 4. Concrete Actionable Enhancements

#### 4.1 Fix the Critical Bugs Immediately
- **Define `last_bar_session`** before the `eval_date` line:
  ```python
  last_bar_session = df_1d["session_date"].iloc[-1] if not df_1d.empty else None
  ```
- **Correct prior completed week selection**:
  ```python
  # Determine if the last weekly bar is complete (its Friday date <= target_date and target is after Friday close)
  last_wk_date = df_wk.index[-1].date()
  if target_date and last_wk_date <= t_dt and t_dt.weekday() == 4:
      # Current week is complete; prior completed week is the last weekly bar
      prior_wk = df_wk.iloc[-1]
  else:
      prior_wk = df_wk.iloc[-2] if len(df_wk) >= 2 else df_wk.iloc[-1]
  ```
- **Adjust 52‑week lookback to yield 52 excursions**:
  ```python
  # Need 53 weekly bars for 52 excursions
  if len(df_wk) >= 54:
      lookback_wks = df_wk.iloc[-54:-1]  # 53 bars → 52 excursions
  else:
      lookback_wks = df_wk.iloc[:-1]  # fallback, but warn
  ```
  Then the loop `for i in range(1, len(lookback_wks))` will produce `len(lookback_wks)-1` excursions, which is 52 when 53 bars are provided.

#### 4.2 Implement Missing Blueprint Features
- **Mode tie‑breaking**:
  ```python
  mode_counts = binned.value_counts()
  if len(mode_counts) > 1 and mode_counts.iloc[0] == mode_counts.iloc[1]:
      # tie: choose bin whose center is closest to mean
      top_bins = mode_counts[mode_counts == mode_counts.iloc[0]].index
      centers = [(b.left + b.right) / 2 for b in top_bins]
      closest_idx = np.argmin([abs(c - mean_val) for c in centers])
      top_bin = top_bins[closest_idx]
  else:
      top_bin = mode_counts.index[0]
  ```
- **Add hit‑rate classification** (define what “hit” means – likely the percentage of weeks where excursion reached ≥2%? Clarify with domain expert). For now, add a placeholder and a warning.
- **Extract NFP 08:30 candle high/low** in the analysis function by optionally accepting 1‑minute data, or provide a separate utility that the verification script already uses. The analysis dict should include `nfp_high`, `nfp_low` when `is_nfp_friday` is true.
- **Implement Sunday/Tuesday anchor detection** using intraday data. At minimum, flag the presence of these anchors and record the opening price at 18:00 ET Sunday and 09:30 ET Tuesday.

#### 4.3 Harden Edge Cases
- **Enforce minimum data requirement**: if `len(df_wk) < 54`, return an empty result with a clear warning that 53 completed weeks are needed.
- **Improve session date logic**: use a market‑aware session definition (e.g., CME Globex 18:00–17:00 ET). For daily bars, the index is often already the session date; consider dropping `session_date` entirely and filtering by `df_1d.index.date <= t_dt` after ensuring the index is in `US/Eastern`.
- **Add timezone safety**: attempt `tz_convert('US/Eastern')` first; if that fails, try `tz_localize('UTC').tz_convert('US/Eastern')`; if both fail, raise a clear error.
- **Handle NFP on holidays**: check if the first Friday is a trading day; if not, skip or flag.

#### 4.4 Improve Code Quality
- **Vectorise excursion calculation**:
  ```python
  lookback_wks['prev_ema5'] = lookback_wks['ema5'].shift(1)
  lookback_wks['dUp'] = np.maximum(0, (lookback_wks['high'] - lookback_wks['prev_ema5']) / lookback_wks['prev_ema5'] * 100)
  lookback_wks['dDn'] = np.maximum(0, (lookback_wks['prev_ema5'] - lookback_wks['low']) / lookback_wks['prev_ema5'] * 100)
  dup_list = lookback_wks['dUp'].dropna().tolist()
  ddn_list = lookback_wks['dDn'].dropna().tolist()
  ```
- **Use `TypedDict` for the return value** to prevent key typos and improve IDE support.
- **Add comprehensive logging** for all early‑return paths and data insufficiency.
- **Write unit tests** covering: normal Friday close, mid‑week target, insufficient data, tie‑breaking, NFP detection, and the undefined variable scenario.

#### 4.5 Verification Script Improvements
- **Actually verify Sunday/Tuesday anchors** as promised in the docstring.
- **Use a precise 1‑minute candle for NFP** (08:30–08:31) instead of a 15‑minute window, or make the window configurable.
- **Check data availability** before slicing and warn if pre‑market bars are missing.

---

### Summary

The component contains **two critical bugs** (undefined variable and incorrect prior‑week selection) that will cause crashes or silently wrong outputs in production. The 52‑week lookback is off by one, and the mode tie‑breaking rule is ignored, both of which directly violate the master blueprint. Several required features (hit‑rate classification, NFP candle extraction, Sunday/Tuesday anchors) are missing. Code quality is acceptable but relies on non‑vectorised loops and fragile timezone handling.

**Recommendation**: Do not deploy to production until the critical and high‑severity items are resolved. After fixes, a full backtest against known Mickey‑style trade examples is strongly advised to validate the corrected statistics.