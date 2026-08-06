# Independent Audit: Candle Science Engine & Blueprint

**Audit posture:** Strict, evidence-based, methodology-first.  
**Scope:** `BLUEPRINT.md`, `candle_science.py`, `v_02_candle_science_pa.py`.  
**Verdict:** The current implementation is a *thin filter wrapper* over an opaque `CandleScienceService`. It captures the **vocabulary** of Mickey’s Candle Science but misses several **operational mechanics** that make the methodology tradable. The intraday verification script is conceptually useful but technically immature, non-vectorized, and does not actually verify the blueprint’s central claims.

---

## 1. Rule Fidelity & Domain Correctness

### 1.1 Critical: C3 Open Proxy Is Wrong in `open` Mode
**Blueprint rule:** C2 Open is the “line in the sand.” The directional regime is determined by **where C3 actually opens** relative to C2 Open.

**Code deviation:**
```python
# candle_science.py, open mode
c3o_price = c2["close"]
```
For index futures (`NQ1`, `ES1`), the RTH open can gap tens to hundreds of points away from the prior daily close. Using yesterday’s close as a proxy for today’s C3 open **directly contradicts** the blueprint’s “C3 opens above/below C2 Open” rule and will produce wrong filters, wrong probabilities, and wrong MFE/MAE baselines.

**Fix:** Pull the true RTH/primary-session open from 1-minute data, or at minimum use the first 1m bar’s open. Document the fallback clearly.

---

### 1.2 The “Inside Upper Wick / Apex Risk” Nuance Is Lost
**Blueprint rule (Nuance 3):**
- A+ continuation: `C2 Close > C1 High`
- Weak close inside C1 upper wick: `C2 breaches C1 High but closes inside C1’s upper wick footprint` → 59–62% containment risk.

**Code deviation:** The only relevant filter is `c2CloseVsC1High = "above" if c2_close > c1_high else "below"` (and only in the `full` preset). A C2 close at 90% retracement of C1’s upper wick is coded identically to a close at the C1 low — both are `"below"`. The engine cannot distinguish A+, Apex-risk, and deep-reversal closes.

**Fix:** Add a categorical dimension:
```python
def c2_close_vs_c1_footprint(c1, c2):
    if c2_close > c1_high: return "above_wick"
    elif c2_close > c1_close: return "inside_upper_wick"
    elif c2_close > c1_open: return "inside_body"
    else: return "below_body"
```

---

### 1.3 The Intraday Reclaim Rule Is Not Implemented
**Blueprint rule (Nuance 1):**
- Wick breach of C2 Open = reversal warning.
- **Confirmed** reversal requires a **5-minute close** below C2 Open.
- Reclaim and 5m close back above C2 Open restores bullish probabilities with 5–10% decay.

**Code deviation:** `candle_science.py` has no concept of wick-vs-close breach, 5m confirmation, or reclaim decay. The verification script only records the first 1m wick breach. The engine therefore cannot apply the 65–85% → 66–68% probability flip described in the blueprint.

**Fix:** Add a bar-state machine that resamples 1m to 5m and tracks:
1. `state = "holding"`
2. `state = "warning"` on 1m wick breach
3. `state = "confirmed_bear"` on 5m close below C2 Open
4. `state = "reclaimed_bull"` on 5m close back above C2 Open, with decay factor.

---

### 1.4 The 0–5 Box / Q1 Rule Is Misinterpreted
**Blueprint rule (Nuance 4):**
- `0-5 Box 10 bps Rule` appears tied to the first 5-minute box, not the entire Q1 15-minute window.
- Requires a 10 bps breach **and** a failure/return inside the box to flag an “Instant High/Low.”

**Code deviation:** In `v_02_candle_science_pa.py`, the entire 09:30–09:45 window is used:
```python
q1_bars = bars_1m[bars_1m.index <= q1_end]
q1_bps = (q1_range / c2_close) * 10000.0
```
The script only checks `q1_bps >= 10.0`; it does not detect the “false breakout → instant high/low” pattern.

**Fix:** Operate on 5m (or 1m-derived 5m) boxes. Track whether price extends ≥10 bps and then retraces back into the opening 5m range.

---

### 1.5 The 3-Tier TP System Is Not a First-Class Output
**Blueprint rule (Section 3):**
- TP1: 50% at 10 bps / 1R → risk-free.
- TP2: P30 or P50 median MFE.
- TP3: Hard exit by 09:44 before the 09:45 pivot.

**Code deviation:** `candle_science.py` outputs raw MFE/MAE percentiles but does not compute TP levels, scaling sizes, or the 09:44 hard exit. The verification script checks TP1 timing but not the full 3-tier lifecycle.

**Fix:** Add a `build_trade_plan()` helper that returns:
```python
{
  "entry": c2_open or c2_close,
  "stop": c2_low/high or c2_open,
  "tp1": c3_open + 0.0010 * c2_close,
  "tp2": p50_mfe,
  "tp3_time": time(9, 44, tzinfo=ET),
  "size": risk_dollars / (entry - stop)
}
```

---

### 1.6 Close-Mode Scenarios Use Arbitrary 10-Point Gaps
```python
scenarios = {
    "Gap Up (opens above today's High)": c2["high"] + 10.0,
    "Flat / Inside (opens at today's Close)": c2["close"],
    "Gap Down (opens below today's Low)": c2["low"] - 10.0,
}
```
For NQ, ±10 points is often inside the overnight range and is not a realistic gap-up/gap-down scenario. This makes the scenario analysis low-signal.

**Fix:** Use instrument-aware spacing: prior 20-day gap ATR, session-open ATR, or fixed percentage (e.g., ±0.3%, ±0.5%, ±1.0%).

---

### 1.7 “Buy Red, Sell Green” Is Not Enforced
**Blueprint rule (Rule 1):** Never buy green breakouts or sell red breakdowns blindly; buy red pullbacks in bullish daily configs.

**Code deviation:** The engine outputs probabilities but does not flag whether the current 1m bar is a “green breakout” or “red pullback” relative to the daily setup. A user could still take the signal on the wrong candle color.

**Fix:** Add a `signal_quality` field: `valid_entry_candle`, `avoid_chase`, `wait_for_red_pullback`, etc.

---

## 2. Edge Cases & Failure Modes

### 2.1 Fragile Date Alignment Assumes Data Is Updated to “Today”
```python
last_bar_date = df_1d.index[-1].date()
today_et = datetime.now(pytz.timezone("America/New_York")).date()

if last_bar_date == today_et:
    ...
else:
    ...
```
This fails on:
- Weekends/holidays.
- Runs after market close but before daily parquet update.
- Runs in a backtest where “today” is historical.
- Runs near midnight ET / UTC boundary.

**Fix:** Use an explicit `as_of_date` parameter and a trading-calendar lookup. Do not infer semantics from wall-clock time.

---

### 2.2 `searchsorted` Misuse in Verification Script
```python
daily_idx = df_1d.index.searchsorted(pd.Timestamp(target_dt).tz_localize("US/Eastern"))
```
`searchsorted` returns an insertion index, not a confirmed date match. If `target_dt` is a weekend or holiday, `daily_idx` points to the next trading day, and `c3_actual` becomes the wrong candle.

**Fix:**
```python
matches = df_1d.index[df_1d.index.date == target_dt]
if len(matches) == 0:
    log.warning("No daily bar for %s", target_dt); continue
daily_idx = df_1d.index.get_loc(matches[0])
```

---

### 2.3 Timezone Conversion of Daily Bars Can Shift Dates
Daily bars stamped at UTC midnight become 20:00 or 19:00 ET of the previous calendar day. `df_1d.index.date` after conversion may map to the wrong trading date.

**Fix:** Standardize daily index to market-close time (e.g., 16:00 ET) before `.date()` extraction, or store an explicit `trade_date` column.

---

### 2.4 No Validation of Missing/NaN OHLC
Neither file checks for `NaN`, zero-volume, or zero-range bars. A single missing value propagates silently into wrong filters.

**Fix:** Add a `_validate_bar(s)` guard:
```python
if s[["open", "high", "low", "close"]].isna().any():
    raise ValueError("Invalid OHLC bar")
if s["high"] < s["low"]:
    raise ValueError("H < L")
```

---

### 2.5 Empty Sample Sets Are Not Surfaced Reliably
`_process_stats_endpoint` returns default 50/50 probabilities when `sample_count == 0`. This can be mistaken for a real edge.

**Fix:** Raise or return `edge=None`, `p_bull=None`, `p_bear=None`, and flag `insufficient_sample` when `n_matches < min_sample_threshold` (e.g., 30).

---

### 2.6 Circular / Dynamic Import Risk
```python
from api.features.candle_science.service import CandleScienceService
```
is imported inside functions. If this is to avoid a circular import, it should be documented; otherwise it hides dependencies and complicates testing.

**Fix:** Move to module top or inject the service as a dependency.

---

### 2.7 The Service Schema Is Assumed, Not Validated
The code reaches deep into nested dicts:
```python
stats.get("direction", {}).get("c3", {})
stats.get("high_wicks", {}).get("c3_vs_c2", {}).get("high_vs_high", {})
```
If `CandleScienceService` changes key names, the engine silently returns `None` for every field. There is no schema contract.

**Fix:** Define a `CandleScienceStats` dataclass or Pydantic model and validate the service response.

---

## 3. Code Quality, Vectorization & Performance

### 3.1 Verification Script Uses Explicit Python Loops Over 1m Bars
```python
for t_stamp, bar in bars_1m.iterrows():
    if opened_above_c2_open:
        if bar["low"] < c2_open:
            c2_open_breach_time = t_stamp.strftime("%H:%M")
            break
```
`iterrows()` over 1-minute data for many dates is slow and un-Pythonic for pandas.

**Fix:** Vectorize:
```python
mask_long_breach = bars_1m["low"] < c2_open
if opened_above_c2_open and mask_long_breach.any():
    c2_open_breach_time = mask_long_breach.idxmax().strftime("%H:%M")
```

Same issue for the TP1 loop.

---

### 3.2 `_extract_percentiles` Direction Filtering Is Semantically Risky
```python
if direction == "negative":
    s = s[s < 0]
...
if mae_median != 0:
    res["rr_envelope"] = round(abs(mfe_median / mae_median), 2)
```
If the service already returns MAE as positive distances, filtering `s < 0` yields an empty series and the fallback silently masks it. If MAE is returned as signed deltas (e.g., `low - open`), then `mae_median` is negative and the `abs()` ratio is correct only by accident.

**Fix:** Define the service distribution contract explicitly. Use `numpy.percentile` and ensure both MFE and MAE are positive magnitudes before computing R:R.

---

### 3.3 R:R Envelope Uses Medians of Different Baselines
The code first tries `c3_high_vs_c2_open` / `c3_low_vs_c2_open`, then falls back to `c3_high_vs_c2_high` / `c3_low_vs_c2_low`. Mixing baselines (open vs high/low) produces an apples-to-oranges R:R ratio.

**Fix:** Use a single, documented baseline per mode (e.g., C2 Open for open mode, C2 Close for close mode). Do not mix.

---

### 3.4 Magic Numbers and Hardcoded Paths
- `+10.0` / `-10.0` in scenarios.
- `0.0010` for 10 bps.
- Path `_REPO / "data" / f"{ticker}_1d.parquet"`.

**Fix:** Move to config: `scenario_gap_basis`, `bps_threshold`, `parquet_path_template`.

---

### 3.5 `format_candle_science_block` Does Too Much
It branches on `mode` and contains inline string formatting for two different reports. This violates single responsibility.

**Fix:** Split into `_format_open_read()` and `_format_close_read()`.

---

## 4. Concrete Actionable Enhancements

### A. Add a Real C3 Open Resolver
```python
def get_c3_open(ticker: str, target_date: date) -> float:
    df_1m = load_fused_data(ticker, "1m")
    rth_open = df_1m.between_time("09:30", "09:31").iloc[0]["open"]
    return rth_open
```
Use this in `open` mode instead of `c2["close"]`.

### B. Encode All Blueprint Nuances as Filter Dimensions
Add dimensions:
- `c2CloseFootprint`: `above_wick`, `inside_upper_wick`, `inside_body`, `below_body`
- `c2BodySizeVsC1`: `engulfing`, `inside`, `normal`
- `c3OpenVsC2Open`: `above`, `inside_body`, `below`
- `c1ColorMagnifier`: `red_break_high`, `green_break_high`, `red_break_low`, `green_break_low`

### C. Implement 5m Reclaim State Machine
```python
def c2_open_state(bars_5m: pd.DataFrame, c2_open: float) -> pd.Series:
    states = []
    state = "neutral"
    for _, bar in bars_5m.iterrows():
        if bar["close"] < c2_open:
            state = "confirmed_bear"
        elif bar["close"] > c2_open and state == "confirmed_bear":
            state = "reclaimed_bull"
        states.append(state)
    return pd.Series(states, index=bars_5m.index)
```

### D. Vectorize Verification Script
Rewrite all intraday checks with pandas masks and `idxmax()`.

### E. Add Trading-Calendar-Aware Date Handling
Use `pandas_market_calendars` or an internal holiday file for `NQ`/`ES`.

### F. Define a Service Response Schema
```python
from pydantic import BaseModel, Field

class DirectionProb(BaseModel):
    bull: float = Field(ge=0, le=100)
    bear: float = Field(ge=0, le=100)

class CandleScienceStats(BaseModel):
    sample_count: int
    direction: dict[str, DirectionProb]
    high_wicks: dict
    low_wicks: dict
    body: dict
    distributions: dict[str, list[float]]
```

### G. Add Minimum Sample Threshold
```python
MIN_SAMPLE = cs_cfg.get("min_sample_count", 30)
if sample < MIN_SAMPLE:
    return {"error": "insufficient_sample", "n_matches": sample}
```

### H. Implement Full 3-Tier TP Logic in Output
Return entry, stop, TP1/TP2 prices, TP3 time, and recommended contracts.

### I. Add Unit Tests for Each Blueprint Rule
Test cases:
1. Red C1 + C2 breaks C1 high → P(bull C3) ≥ baseline + 8%.
2. C2 close inside C1 upper wick → P(C3H > C2H) ∈ [59, 62].
3. 5m close below C2 Open → P(take C2 low) ≈ 66–68%.
4. Reclaim of C2 Open → probability restoration with decay.
5. Q1 10 bps breach → TP1 hit before 09:44.

### J. Document and Fix Daily Bar Timestamp Assumption
Add a preprocessing step that coerces daily index to 16:00 ET so `.date()` is unambiguous.

---

## Executive Summary

| Area | Grade | Key Finding |
|------|-------|-------------|
| Rule fidelity | **C-** | Captures C1 color and simple C2 relationships; misses C2 close footprint, 5m reclaim rule, true C3 open, and 0–5 box mechanics. |
| Edge cases | **D+** | Wall-clock date logic, `searchsorted` misuse, no holiday handling, silent empty samples. |
| Code quality | **C** | Readable but contains non-vectorized loops, deep unvalidated dict access, and mixed MFE/MAE baselines. |
| Performance | **C+** | Acceptable for daily queries; verification script will bog down on large histories. |
| Testability | **D** | Dynamic imports, no schema, no unit tests for blueprint rules. |

**Bottom line:** This component is currently a **filter-translation layer**, not a verified Candle Science engine. The highest-impact fixes are (1) resolving the true C3 open from intraday data, (2) adding the C2-close footprint and 5m reclaim state machine, and (3) replacing the ad-hoc date logic with a trading-calendar-aware index. Without these, the probabilities being emitted are not faithful to the blueprint and should not be used for live sizing or execution.