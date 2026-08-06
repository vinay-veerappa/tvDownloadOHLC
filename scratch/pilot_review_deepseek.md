## Code Review: `scripts/wargaming/pilot_single_day.py`

### 1. Strict Prevention of Look-Ahead Bias (Critical)

**Finding: The pre‑market wargame (08:30 AM) uses future data from the 09:30 RTH open, violating the no‑look‑ahead constraint.**

- **Handshake Vector**  
  `handshake` is computed using `rth_open` (the 09:30 bar open). At 08:30 this price is unknown.  
  ```python
  rth_open = float(rth_bars.iloc[0]["open"]) if not rth_bars.empty else p12_mid
  handshake = "AGREEMENT" if (p12_bias == "BULLISH" and rth_open >= p12_mid) or (p12_bias == "BEARISH" and rth_open < p12_mid) else "DISAGREEMENT"
  ```
  This makes the entire `confluence_status` (which depends on `handshake`) biased.

- **Position Sizing**  
  `stop_dist` is based on `abs(rth_open - p12_mid)`, again using the future open.  
  ```python
  stop_dist = max(10.0, abs(rth_open - p12_mid))
  sizing = calculate_position_size(account_equity, risk_pct, stop_dist, ticker=ticker)
  ```
  The resulting contract count and dollars‑at‑risk are therefore not available at 08:30.

**Impact:** The pre‑market briefing prints a “Signal Confluence Status” and a “Position Sizing” that unknowingly incorporate post‑open information. This defeats the purpose of a wargame that should rely solely on pre‑market data.

**Recommendation:**  
- Move the handshake and position sizing to the **EOD reengineering** section (where they can be compared against the pre‑market expectations).  
- In the pre‑market section, compute a **pre‑market handshake** using only the 08:30 pre‑market close vs. P12 mid, and a **pre‑market position size** based on a volatility measure available before the open (e.g., previous day’s ATR, pre‑market range, or a fixed stop).  
- The confluence matrix should then reflect only pre‑market signals (Candle Science bias, P12 bias, HTF EMA zone, and the pre‑market handshake).

---

### 2. Robustness & Error Handling

**a) Missing or empty data**  
- `df_1d` and `df_1m` are loaded without any `try/except`. A missing file raises an unhandled `FileNotFoundError`.  
- If `p12_bars` is empty, `p12_high`, `p12_low`, `p12_mid` are set to `0.0`. This cascades into nonsensical values (e.g., `p12_bias` becomes `True` because `last_pre_close >= 0` is always true).  
- If `rth_bars` is empty (holiday, early close), `rth_open` falls back to `p12_mid` (which may be 0.0), and the EOD section still prints a report with zero values.  
- The 3‑hour line/apex counter gracefully returns `"N/A"` when bars are missing, which is good.

**b) Timezone handling**  
- The code assumes that a tz‑naive index is **UTC**. If the data is actually in another timezone (e.g., already US/Eastern but without tz info), the conversion will be wrong.  
- The conversion chain `tz_localize("UTC").tz_convert("US/Eastern")` is correct for UTC‑naive data, but a comment or a configuration parameter would make the assumption explicit.

**c) Holiday / early‑close sessions**  
- No check for whether `target_date` is a valid trading day. The script will run on weekends/holidays and produce empty RTH bars, leading to a degraded report.  
- The `rth_bars` slice uses `<= rth_end` (16:00). If the market closes early, the last bar may be before 16:00, but the slice still works; however, `rth_close` will be the last available bar, which is correct.

**d) Edge cases in the 3‑hour line/apex logic**  
- `step4` is hard‑coded to `True` with a comment “Instant High/Low check”. This appears to be a placeholder; it inflates the score by 1 unconditionally.  
- The loop in `step2` is not vectorised and will be slow on large data, though for 1‑hour windows it is acceptable.

---

### 3. Type Safety & Code Quality

**a) Typing**  
- The function signature uses `dict[str, Any]` for the return, which is acceptable for a script. Internal variables lack type annotations; adding them would improve readability.  
- `cfg` is loaded but only `mom_threshold` is used; the rest of the config is ignored.

**b) Dead code**  
- `df_1d` is loaded from `{ticker}_1d.parquet` but **never used** in the function. It should be removed or passed to `compute_htf_ema_analysis` if that function requires it.

**c) Pandas usage**  
- Slicing with timezone‑aware timestamps is correct.  
- The `step2` loop can be replaced with vectorised operations (see enhancements).  
- `rth_bars[rth_bars["high"] == rth_high].index[0]` works but will raise an `IndexError` if `rth_bars` is empty; the code guards against that with the `if not rth_bars.empty` check.

**d) Modularity**  
- The entire logic resides in one large function. It could be split into `generate_premarket_wargame()` and `generate_eod_reengineering()` for clarity and testability.

---

### 4. Actionable Code Enhancements

#### 4.1 Remove Look‑Ahead Bias (Refactor)

**Pre‑market section (08:30) – use only pre‑market data:**
```python
# Pre-market handshake (using 08:30 pre-market close)
pre_handshake = "AGREEMENT" if (p12_bias == "BULLISH" and last_pre_close >= p12_mid) or \
                               (p12_bias == "BEARISH" and last_pre_close < p12_mid) else "DISAGREEMENT"

# Pre-market position sizing (e.g., based on pre-market range or fixed stop)
pre_stop_dist = max(10.0, pre_bars["high"].max() - pre_bars["low"].min()) if not pre_bars.empty else 10.0
pre_sizing = calculate_position_size(account_equity, risk_pct, pre_stop_dist, ticker=ticker)

# Confluence using only pre-market signals
is_aligned = (cs_bias == p12_bias) and (pre_handshake == "AGREEMENT") and not is_2to3
confluence_status = "ALIGNED (High Conviction)" if is_aligned else "CONFLICTED (Caution / Reversion Risk)"
```

**EOD section (16:00) – compute actual handshake and compare:**
```python
actual_handshake = "AGREEMENT" if (p12_bias == "BULLISH" and rth_open >= p12_mid) or \
                                 (p12_bias == "BEARISH" and rth_open < p12_mid) else "DISAGREEMENT"
# Then report whether the pre-market handshake matched the actual.
```

#### 4.2 Add Basic Error Handling

```python
try:
    df_1m = load_fused_data(ticker, timeframe="1m")
except FileNotFoundError:
    log.error("1m data file not found for %s", ticker)
    return {"error": "Missing data"}
if df_1m.empty:
    log.warning("1m DataFrame is empty")
    # handle gracefully
```

For empty P12 bars, fall back to the previous day’s P12 or raise a clear warning:
```python
if p12_bars.empty:
    log.warning("No P12 bars for %s – using previous day’s range", target_date)
    # attempt to load previous day’s P12 or set to NaN and skip wargame
```

#### 4.3 Vectorise the 3‑Hour Line Step 2

Replace the loop with:
```python
bars_10["close_prev"] = bars_10["close"].shift(1)
cond_above = (bars_10["close_prev"] > h9_mid) & (bars_10["low"] > h9_mid)
cond_below = (bars_10["close_prev"] < h9_mid) & (bars_10["high"] < h9_mid)
step2 = (cond_above | cond_below).any()
```

#### 4.4 Remove Dead Code and Simplify Timezone Handling

- Delete `df_1d = pd.read_parquet(...)` if it is not used.
- Use `pd.Timestamp` with a timezone string for clarity:
  ```python
  p12_start = pd.Timestamp(f"{prev_day} 18:00", tz="US/Eastern")
  p12_end   = pd.Timestamp(f"{t_dt} 06:00", tz="US/Eastern")
  ```
- Add a comment that tz‑naive data is assumed to be UTC.

#### 4.5 Improve the `step4` Placeholder

Either implement the intended “Instant High/Low” check or remove `step4` and adjust the score denominator to 3. A hard‑coded `True` is misleading.

#### 4.6 Enhance the Report Structure

Return a dictionary that clearly separates **pre‑market expectations** from **EOD actuals**, and include a `"lookahead_free"` flag for the pre‑market section to make the contract explicit.

---

### Summary

The module is well‑structured and readable, but the **critical look‑ahead bias** in the pre‑market wargame must be fixed before it can be used for any serious simulation or live decision support. Once the handshake and position sizing are moved to the EOD section (or replaced with pre‑market analogues), the script will correctly enforce the 08:30 information cutoff. Additional robustness improvements (error handling, empty‑data guards, vectorisation) will make it production‑ready.