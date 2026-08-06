# AUDIT REPORT: HTF Weekly EMA(5) Excursion Analysis

**Auditor**: Senior Quantitative Trading Engineer
**Date**: October 26, 2023
**Component**: `htf_ema_analysis.py`, `v_03_htf_ema_pa.py`
**Status**: **FAIL** (Requires Critical Remediation before Production Use)

---

## 1. Rule Fidelity & Domain Correctness

### ❌ Critical Failure: Magnet Zone Logic (Close vs. High/Low)
**Issue**: The Blueprint defines excursions based on **High/Low** (`dUp` uses High, `dDn` uses Low). However, `htf_ema_analysis.py` determines `is_2to3_zone` based on `current_close`.
**Impact**: If price wicks to 2.5% excursion intraday but closes at 1.8%, the system reports `is_2to3_zone: False`. This misses the "Magnet" interaction entirely, invalidating the mean-reversion signal.
**Fix**: `is_2to3_zone` must evaluate `max(dUp, dDn)` of the *current* session, not just `dist_pct` derived from Close.

### ❌ Critical Failure: Mode Tie-Breaking Logic
**Issue**: Blueprint specifies: *"If multiple bins tie for highest frequency, the bin center closest to the arithmetic Mean is selected."*
**Code**: `mode_counts.index[0]` simply picks the first bin returned by `value_counts()`. Pandas sorts ties by the bin index (value), not proximity to Mean.
**Impact**: Statistical Mode will be incorrect during flat distributions, skewing the "Most Probable Excursion" metric.

### ⚠️ Warning: 52-Week Lookback Integrity
**Issue**: The code falls back to `iloc[:-1]` if `len(df_wk) < 53`. This allows the engine to run with 10, 20, or 51 weeks of data.
**Impact**: Statistical significance is compromised. A 10-week mode is noise, not a signal.
**Fix**: Enforce a hard minimum. If `len(lookback_wks) < 52`, return `None` or raise `InsufficientDataError`.

### ⚠️ Warning: Missing Anchor Implementations
**Issue**: Blueprint requires **Sunday 18:00 ET** and **Tuesday 09:30 ET** anchors.
**Code**: Neither `htf_ema_analysis.py` nor `v_03_htf_ema_pa.py` calculates or verifies these anchors. Only NFP is partially implemented.
**Impact**: 33% of the methodology's temporal edge cases are unmonitored.

---

## 2. Edge Cases & Failure Modes

### 🛑 Data Gaps & Holiday Weeks
**Scenario**: A 4-day trading week (e.g., Thanksgiving).
**Risk**: `resample("W-FRI")` creates a weekly bar regardless of trading days. A 4-day week naturally has lower excursion potential than a 5-day week. Including these in the 52-week distribution without normalization introduces downward bias in Mean/Mode.
**Recommendation**: Filter `lookback_wks` to exclude weeks with `< 5` daily bars (check volume or count) OR normalize excursion by `sqrt(trading_days)`.

### 🛑 NFP Timezone & Candle Definition
**Scenario**: NFP Release is 08:30 EST.
**Code**: `v_03_htf_ema_pa.py` aggregates 08:30–08:45 (15 minutes).
**Risk**: Mickey's methodology typically focuses on the immediate reaction (08:30–09:00 or the specific 5m candle). A 15m aggregation dilutes the initial volatility spike used for the "Anchor Box."
**Risk**: Daylight Savings Time (DST) transitions. `pytz` handles this, but hardcoded `time(8, 30)` can be ambiguous during DST shifts if not explicitly `EST` (not `ET`). NFP is always **EST** (New York Standard Time), even during DST (when it's 09:30 ET trading, NFP is still 08:30 EST/09:30 EDT). The code uses `US/Eastern`, which auto-adjusts. This is acceptable but fragile if data source is UTC without DST metadata.

### 🛑 Zero-Division & Data Types
**Scenario**: `prev_ema` is 0.0 (corrupt data or specific ticker).
**Risk**: `ZeroDivisionError` in excursion calculation.
**Code**: No check for `prev_ema == 0`.

### 🛑 Session Date Cutoff
**Code**: `if dt.hour >= 17: return (dt + 1).date()`
**Risk**: CME Friday close is 17:00 ET. A timestamp of `17:00:00` is the Close. A timestamp of `17:00:01` is Sunday Open. The logic `>= 17` pushes the 17:00:00 bar to the *next* day (Saturday). This misaligns the Weekly Resample `W-FRI`.
**Fix**: Use `dt.hour > 17` or strictly handle the 17:00 boundary to ensure Friday Close stays in the Friday bucket.

---

## 3. Code Quality, Vectorization & Performance

### 📉 Performance: Python Loop in Hot Path
**Location**: `htf_ema_analysis.py`, lines 85-93.
```python
for i in range(1, len(lookback_wks)):
    prev_ema = float(lookback_wks.iloc[i-1]["ema5"])
    # ... manual calculation
```
**Critique**: This is O(N) Python iteration. For 52 weeks, it's negligible. However, if this is scaled to run on 500 tickers daily, it becomes a bottleneck. It violates Pandas best practices.
**Fix**: Use vectorized `shift()`.

### 📉 Memory: Parquet Loading
**Critique**: `pd.read_parquet` loads the entire history every time.
**Fix**: For a production engine, pass the DataFrame in or use a cached singleton loader. For a script, it's acceptable but should be noted.

### 📉 Logging & Configuration
**Critique**: `REPO_ROOT = Path(__file__).parent.parent.parent` is fragile. If the script is moved or imported differently, paths break.
**Critique**: `logging.basicConfig` is missing in the library module (`htf_ema_analysis.py`). Logs will be suppressed if imported without configuration in the caller.

### 📉 Type Safety
**Critique**: Return dict uses `Any`. Specific `TypedDict` or `dataclass` should be used to enforce schema (e.g., ensuring `dup_stats` always has keys `mean`, `median`, `mode`).

---

## 4. Concrete Actionable Enhancements

### 1. Vectorize Excursion Calculation (Refactor `htf_ema_analysis.py`)
Replace the `for` loop with this vectorized block for performance and readability:

```python
# Vectorized Excursion Calculation
wk = lookback_wks.copy()
wk['prev_ema'] = wk['ema5'].shift(1)
wk['d_up'] = np.maximum(0.0, ((wk['high'] - wk['prev_ema']) / wk['prev_ema']) * 100.0)
wk['d_dn'] = np.maximum(0.0, ((wk['prev_ema'] - wk['low']) / wk['prev_ema']) * 100.0)

# Drop the first row (NaN due to shift)
wk = wk.dropna(subset=['prev_ema'])

dup_list = wk['d_up'].tolist()
ddn_list = wk['d_dn'].tolist()
```

### 2. Implement Correct Mode Tie-Breaking
Replace `calc_excursion_stats` logic with:

```python
# Inside calc_excursion_stats
binned = pd.cut(s[s > 0.001], bins=bins, include_lowest=True)
mode_counts = binned.value_counts()
max_count = mode_counts.max()
top_bins = mode_counts[mode_counts == max_count].index

if len(top_bins) > 1:
    # Tie-Breaker: Closest to Mean
    bin_centers = [(b.left + b.right) / 2 for b in top_bins]
    distances = [abs(c - mean_val) for c in bin_centers]
    top_bin = top_bins[np.argmin(distances)]
else:
    top_bin = top_bins[0]
```

### 3. Fix Magnet Zone Logic
Update `is_2to3_zone` calculation to use High/Low of the current session, not Close.
*Note: This requires intraday data access in `compute_htf_ema_analysis` or passing High/Low from the daily bar if analyzing Daily.*
If using Daily data:
```python
current_high = float(df_1d.iloc[-1]["high"])
current_low = float(df_1d.iloc[-1]["low"])
d_up_curr = max(0.0, ((current_high - prior_ema5) / prior_ema5) * 100.0)
d_dn_curr = max(0.0, ((prior_ema5 - current_low) / prior_ema5) * 100.0)
res["is_2to3_zone"] = bool((2.0 <= d_up_curr <= 3.0) or (2.0 <= d_dn_curr <= 3.0))
```

### 4. Enforce Data Integrity
Add a hard check for the 52-week requirement:
```python
if len(lookback_wks) < 52:
    log.error(f"Insufficient data for 52-week stats. Found {len(lookback_wks)}.")
    return res # Or raise Exception
```

### 5. Add Sunday/Tuesday Anchors
Extend the return dict and logic to capture:
```python
# Sunday Anchor (18:00 ET Open of the week)
# Requires 1m or 5m data to pinpoint exact 18:00 candle
sunday_open = get_session_open_price(df_1m, week_start_date, hour=18) 
res["sunday_anchor"] = sunday_open

# Tuesday Anchor (09:30 ET RTH Open)
tuesday_open = get_rth_open_price(df_1m, tuesday_date)
res["tuesday_anchor"] = tuesday_open
```

### 6. Robust NFP Detection
Refine NFP detection in `v_03_htf_ema_pa.py`. Instead of a 15m aggregate, isolate the 08:30:00 to 08:34:59 (5m) or 08:30:00 to 08:30:59 (1m) candle to capture the true "Release Candle."
```python
# Strict 08:30 AM EST 5-minute candle
nfp_start = pd.Timestamp(datetime.combine(t_dt, time(8, 30))).tz_localize("US/Eastern")
nfp_end = nfp_start + pd.Timedelta(minutes=5)
nfp_bars = bars_1m[(bars_1m.index >= nfp_start) & (bars_1m.index < nfp_end)]
```

---

## Final Verdict
The component is **functional for prototyping** but **unsafe for live trading**. The logic errors regarding the Magnet Zone (Close vs. High/Low) and the Mode Tie-Breaker directly contradict the Master Blueprint. The missing Sunday/Tuesday anchors reduce the system's edge.

**Priority**: HIGH. Implement the Vectorization, Magnet Zone fix, and Mode Tie-Breaker immediately.