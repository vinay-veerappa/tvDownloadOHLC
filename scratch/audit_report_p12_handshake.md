## 1. Rule Fidelity & Domain Correctness

### 1.1 P12 Midline Directional Switch (06:00–08:30)
**Blueprint requirement**:  
> If price steps above and **finds footing (accepts)** on P12 Mid between 06:00 and 08:30 AM, bias flips BULLISH.  
> If price **rejects** P12 Mid or accepts below it, bias flips BEARISH.

**Implementation**:  
```python
last_pre_close = float(pre_bars.iloc[-1]["close"]) if not pre_bars.empty else p12_mid
p12_bias = "BULLISH (P12 High Target)" if last_pre_close >= p12_mid else "BEARISH (P12 Low Target)"
```
- **Flaw**: Uses only the **last tick at 08:30** to determine bias. This ignores the entire 2.5‑hour acceptance/rejection process. A single late‑minute spike or dip can flip the bias, violating the “footing” concept.
- **Missing**: No detection of the **“Swiping” signature** (repeated crosses of the midline) that signals an R1 chop day.

### 1.2 06:00–07:00 Early Rejection Window
**Blueprint requirement**:  
> P12 High Early Rejection (06:00–07:00 AM): **84.52% probability HOD is already locked in overnight**.  
> P12 Low Early Rejection: **81.85% probability LOD is already locked in overnight**.

**Implementation**:  
```python
early_rej_h = abs(w7_high - p12_high) < (p12_mid * 0.0005)  # within 5 bps
early_rej_l = abs(w7_low - p12_low) < (p12_mid * 0.0005)
```
- **Flaw**: This merely checks **proximity** of the 06:00–07:00 high/low to the P12 extremes. It does **not** detect a *rejection* (price touching the level and then reversing). A market that simply trades near the P12 high without testing it would trigger a false positive.
- **Missing**: The computed `early_rej_h` / `early_rej_l` flags are **never used** in the output table or any decision logic. The entire early‑rejection rule is effectively dead code.

### 1.3 99.26% “All Levels Hit” Pre‑Market Sweep Rule
**Blueprint requirement**:  
> If **BOTH Asia and London session extremes (or both P12 High & Low) are broken** between 06:00 and 08:30 AM → 99.26% probability both HOD and LOD form after 08:30.  
> **Asia Broken Exception**: If Asia’s extremes are broken (regardless of London), 94.70% probability both HOD/LOD form after 09:00.

**Implementation**:  
```python
both_swept_pre = (pre_high > p12_high) and (pre_low < p12_low)
```
- **Partial**: Only checks P12 High & Low. The Asia/London session extremes are **not computed or checked**, so the Asia‑broken exception (94.70% rule) is completely absent.
- **No verification**: The script flags the sweep but does **not** confirm whether HOD/LOD actually formed after 08:30 (or 09:00) as the rule predicts. The output table shows HOD/LOD times but no cross‑check.

### 1.4 NY Opening Handshake Vector
**Blueprint requirement**:  
> Agreement: RTH opens **above P12 Mid** when overnight profile is **bullish (Long True LT)**.  
> Disagreement: RTH opens trapped inside pre‑market consolidation or opposite to overnight expansion.

**Implementation**:  
```python
handshake = "AGREEMENT" if (p12_bias.startswith("BULLISH") and rth_open >= p12_mid) or (p12_bias.startswith("BEARISH") and rth_open < p12_mid) else "DISAGREEMENT"
```
- **Acceptable** as a first‑order proxy, but the blueprint’s “Long True (LT)” / “Short True (ST)” classification is a richer overnight profile assessment (likely involving volume‑weighted distribution, not just the final pre‑market close). The current implementation reduces it to a binary P12 bias, which may misclassify days where the overnight profile is neutral or mixed.

---

## 2. Edge Cases & Failure Modes

### 2.1 Data Gaps & Missing Bars
- If `pre_bars` is empty (e.g., no 1‑minute data between 06:00–08:30), the script sets `pre_high = pre_low = p12_mid`. This **silently fabricates** a flat pre‑market, causing:
  - `both_swept_pre` to be `False` (no sweep detected) even if a sweep occurred in reality.
  - `p12_bias` to default to `p12_mid` (BEARISH if `p12_mid` is used as `last_pre_close`), which is arbitrary.
- The same fallback is used for the 06:00–07:00 window (`w7_bars` empty → `w7_high = w7_low = p12_mid`), making early rejection checks meaningless.

### 2.2 Holiday & Partial Sessions
- The script selects sample dates from `df_1d.index` without filtering for full trading days. On early‑close days (e.g., day after Thanksgiving, half‑day holidays), the P12 window (18:00–06:00) may be truncated or non‑standard, producing a **distorted P12 range** and invalidating all subsequent rules.
- No check for weekends or exchange holidays; the script assumes every calendar day in the index is a valid session.

### 2.3 Timezone & DST Transitions
- The script localizes timestamps with `"US/Eastern"` (pytz). While correct, it does not handle the **two 1‑hour gaps** during DST “spring‑forward” / “fall‑back” transitions. On those days, the 18:00–06:00 window may contain 11 or 13 hours of data, breaking the “12‑hour” assumption.

### 2.4 Sample Date Selection Bug
```python
sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-6:-1]]
```
- **Intended**: “last 5 available trading days” (comment).  
- **Actual**: `[-6:-1]` selects the **6th‑from‑last to 2nd‑from‑last** day, **excluding the most recent day**. This is almost certainly a bug; the correct slice for the last 5 days is `[-5:]`.

### 2.5 Unused Daily Data
- `df_1d` is loaded solely to extract `unique_dates`. This is wasteful; the same dates could be obtained from `df_1m` or a lightweight index file.

---

## 3. Code Quality, Vectorization & Performance

### 3.1 Strengths
- No explicit Python loops over rows; all operations are vectorized pandas.
- Proper use of timezone‑aware timestamps.
- Clear separation of windows and calculations.

### 3.2 Weaknesses
- **Dead code**: `early_rej_h` and `early_rej_l` are computed but never used in output or logic.
- **Magic number**: `0.0005` (5 bps) is hard‑coded with no explanation. For instruments with vastly different price levels (e.g., ES ~6000 vs NQ ~20000), a fixed percentage may be too tight or too loose.
- **No return value**: The function always returns `True`, making it impossible to programmatically consume the verification results. The table is printed to stdout only.
- **Fragile fallback**: Using `p12_mid` as a substitute for missing pre‑market data is a silent failure that can lead to incorrect conclusions.
- **Logging vs print**: Results are printed with `print()` rather than logged, which is acceptable for a verification script but inconsistent with the module‑level `logging` setup.

---

## 4. Concrete Actionable Enhancements

### 4.1 Fix the Sample Date Bug
```python
# Replace
sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-6:-1]]
# With
sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-5:]]
```

### 4.2 Implement True Early Rejection Detection
Replace the proximity check with a **rejection pattern**:
- For P12 High rejection: price must have **traded at or above P12 High** during 06:00–07:00 and then **closed below it** by the end of the window (or by 07:00).
- For P12 Low rejection: price traded at or below P12 Low and closed above it.
- Add these flags to the output table.

### 4.3 Enhance Directional Switch with Acceptance Logic
Instead of a single close, compute a **pre‑market VWAP or a simple moving average** of closes over the 06:00–08:30 window. Bias is BULLISH if the VWAP/MA is above P12 Mid and the majority of bars closed above it; BEARISH otherwise. Also detect **swiping** (count of midline crosses) and flag R1 chop days.

### 4.4 Add Asia/London Session Extremes & the 94.70% Exception
- Define Asia session: 18:00–02:00 ET (or 18:00–00:00 as per blueprint Q1+Q2).  
- Define London session: 02:00–06:00 ET (Q3+Q4).  
- Compute their highs/lows.  
- Check if **Asia extremes are broken** during 06:00–08:30; if so, flag the 94.70% rule.  
- Integrate with the existing both‑sides sweep logic.

### 4.5 Validate the 99.26% Rule Post‑Facto
After computing RTH HOD/LOD times, verify:
- If `both_swept_pre` is true, assert that both HOD and LOD timestamps are **after 08:30** (or after 09:00 for Asia‑broken exception).  
- Report a **pass/fail** for the rule on each day.

### 4.6 Robust Handling of Missing Data
- If `pre_bars` is empty, **skip the day** with a clear warning instead of fabricating values.
- If `w7_bars` is empty, skip early rejection checks for that day.
- Add a pre‑check for holiday/half‑day sessions using a trading calendar (e.g., `pandas_market_calendars`).

### 4.7 Return Structured Results
Return a `pd.DataFrame` (or a list of dicts) instead of `True`. This allows downstream consumers to run statistical validation across many days.

### 4.8 Remove Unnecessary Daily Data Load
Replace `df_1d` with a lightweight date extraction from `df_1m`:
```python
unique_dates = sorted(pd.Series(df_1m.index.date).unique())
```

### 4.9 Make Tolerance Configurable
Replace the hard‑coded `0.0005` with a parameter, or compute it dynamically from the instrument’s average true range (ATR) over the P12 window.

### 4.10 Add Logging for Skipped/Anomalous Days
Use `log.warning()` for days with missing data, partial sessions, or rule violations, instead of `print`.

---

**Summary**: The script captures the skeleton of the P12 methodology but falls short on the nuanced acceptance/rejection logic, omits the Asia‑broken exception, and contains a date‑selection bug. The early rejection rule is effectively non‑functional. With the above targeted fixes, the component can become a faithful, production‑grade verification tool.