Here is a strict, independent, and unsparing audit of the Candle Science Engine & Blueprint component.

### 1. Rule Fidelity & Domain Correctness

**Verdict: Significant divergences from the master trading methodology.**

*   **C2 Open "Line in the Sand" Breach:** The blueprint explicitly dictates a whipsaw filter requiring a *5-minute candle close* below/above $C_2$ Open for confirmed reversal. The verification script (`v_02_candle_science_pa.py`) loops over 1-minute bars and triggers on `bar["low"] < c2_open` or `bar["high"] > c2_open`. This registers a 1-minute wick touch as a breach, completely bypassing Mickey’s 5-minute close confirmation rule. This will generate massive false reversal signals.
*   **Q1 0-5 Box 10 bps Breach:** The blueprint specifies the "0-5 Box" (the first 5 minutes) requires a 10 bps *breach* to confirm momentum. The script calculates this as the total 15-minute Q1 *range* (`q1_range = q1_high - q1_low`) compared to 10 bps. Measuring the 15-minute range is mathematically and structurally different from measuring a directional breach of 10 bps from the 09:30 open or the 0-5 box limits.
*   **Take Profit Execution (TP1, TP2, TP3):** The script's docstring promises to verify TP2 (P50 Median MFE) and TP3 (09:44 AM exit). The actual code *completely omits* TP2 and TP3 logic. Furthermore, TP1 is defined in the blueprint as "10 bps **OR** 1R (profit equals initial risk)". The script only checks the 10 bps condition, ignoring the 1R condition entirely.
*   **C3 Open Price Proxy:** In `candle_science.py` (Open mode), `c3o_price = c2["close"]`. Using yesterday's close as a proxy for today's open is highly flawed for index futures, which frequently gap overnight. This destroys the accuracy of the `c3o_c2*` dimension filters during high-gap environments.
*   **Equality Handling in Filters:** `_build_filters_from_candles` uses strict `>` and `<`. Exact equalities (e.g., `c2_high == c1_high`), which are common in rounded tick data or tight consolidations, will arbitrarily default to "below". This misclassifies the structural state and pollutes the statistical query.

### 2. Edge Cases & Failure Modes

*   **Holidays and Phantom Signals:** In `candle_science.py`, if the daily parquet hasn't updated or it's a market holiday, `last_bar_date != today_et`. The script assumes today is the next trading day and uses `df_1d.iloc[-2]` and `df_1d.iloc[-1]` to predict "today". If today is a holiday, this generates a phantom signal for a day the market is closed.
*   **Missing Intraday Bars:** `v_02_candle_science_pa.py` assumes `bars_1m.iloc[0]` is the 09:30 open. If 1m data has gaps or the feed is delayed, `iloc[0]` might be 09:31 or 09:45. There is no strict timestamp validation enforcing the 09:30 anchor.
*   **Division by Zero in R:R:** `_process_stats_endpoint` calculates `rr_envelope` as `abs(mfe_median / mae_median)`. It has a guard `if ... mae_median != 0`, which prevents a crash, but if `mae_median` is extremely small but non-zero, it will result in an astronomically high R:R envelope that breaks downstream display logic.
*   **Empty Distributions:** If a matched historical sample results in no positive MFEs or negative MAEs, `_extract_percentiles` returns `{}`. Downstream code checks `if sc["mfe"]:`, which handles empty dicts safely, but if P50 is missing from the dict while P30 is present, `mfe_median = res["mfe"].get("p50")` will return `None`, skipping the R:R calculation silently.

### 3. Code Quality, Vectorization & Performance

*   **Non-Vectorized Loops (Critical Performance Issue):** `v_02_candle_science_pa.py` uses `for t_stamp, bar in bars_1m.iterrows():` multiple times per day for breach detection and TP1 hits. `iterrows()` is notoriously slow in Pandas. For a backtest spanning years of 1m data, this will be a severe bottleneck.
*   **Memory Bloat:** `load_fused_data(ticker, timeframe="1m")` loads the *entire* historical 1m dataset into memory for the script, and then the code filters it down to RTH on a per-date basis inside the loop. This is extremely memory-inefficient. Data should be pre-filtered to the target date range before looping.
*   **Magic Numbers:** In `candle_science.py`, the close-mode gap scenarios use hardcoded point values: `c2["high"] + 10.0`. 10 points on NQ is vastly different from 10 points on ES or SPY. This breaks the component's multi-ticker reusability.
*   **Timezone Assumptions:** `df_1d.index.tz_localize("UTC")` assumes naive timestamps are UTC. If the data provider exports naive Eastern timestamps, this will shift the entire daily series by 4-5 hours, misaligning dates completely.

### 4. Concrete Actionable Enhancements

**Action 1: Fix the C2 Open 5-Minute Close Whipsaw Filter**
In `v_02_candle_science_pa.py`, replace the 1m iterrows breach logic with a 5m resampled close check:
```python
# Resample 1m to 5m closing prices
bars_5m_close = bars_1m['close'].resample('5min').last().dropna()

if opened_above_c2_open:
    breach_mask = bars_5m_close < c2_open
else:
    breach_mask = bars_5m_close > c2_open

c2_open_breach_time = bars_5m_close[breach_mask].index[0].strftime("%H:%M") if breach_mask.any() else "No (Held)"
```

**Action 2: Implement Vectorized Breach and TP Detection**
Remove all `iterrows()` loops. Use vectorized boolean masks:
```python
# Vectorized C2 Open breach detection
if opened_above_c2_open:
    breach_mask = bars_1m['low'] < c2_open
else:
    breach_mask = bars_1m['high'] > c2_open
c2_open_breach_time = bars_1m.index[breach_mask][0].strftime("%H:%M") if breach_mask.any() else None

# Vectorized TP1 detection
if opened_above_c2_open:
    tp1_mask = bars_1m['high'] >= tp1_long_target
else:
    tp1_mask = bars_1m['low'] <= tp1_short_target
tp1_hit_time = bars_1m.index[tp1_mask][0].strftime("%H:%M") if tp1_mask.any() else "Not Hit"
```

**Action 3: Correct Q1 0-5 Box Bps Breach Calculation**
Fix the 10 bps breach to measure directional movement from the open within the first 5 minutes:
```python
# 0-5 Box is first 5 minutes
box_end = pd.Timestamp(datetime.combine(target_dt, time(9, 35))).tz_localize("US/Eastern")
box_bars = bars_1m[bars_1m.index < box_end]

# Measure breach from 09:30 open
max_high_breach = box_bars['high'].max() - c3_open_rth
max_low_breach = c3_open_rth - box_bars['low'].min()

# Check if either direction breached 10 bps (0.0010)
q1_10bps_met = (max_high_breach >= c3_open_rth * 0.0010) or (max_low_breach >= c3_open_rth * 0.0010)
```

**Action 4: Implement TP2 and TP3 in Verification Script**
Add the missing execution logic from the blueprint:
```python
# TP3: Hard exit at 09:44 AM
tp3_exit_time = "09:44"

# TP2: P50 MFE Hit (requires getting CS read first)
cs_read = get_candle_science_read(ticker, mode="open", target_date=date_str)
p50_mfe = cs_read.get("mfe", {}).get("p50")
tp2_hit_time = None
if p50_mfe is not None:
    # Calculate absolute price target for long/short based on p50_mfe percentage
    if opened_above_c2_open:
        tp2_target = c3_open_rth * (1 + p50_mfe / 100.0)
        tp2_mask = bars_1m['high'] >= tp2_target
    else:
        tp2_target = c3_open_rth * (1 - p50_mfe / 100.0)
        tp2_mask = bars_1m['low'] <= tp2_target
    
    tp2_hit_time = bars_1m.index[tp2_mask][0].strftime("%H:%M") if tp2_mask.any() else "Not Hit"
```

**Action 5: Make Gap Scenarios Dynamic**
In `candle_science.py`, replace hardcoded `10.0` point gaps with percentage-based dynamic gaps:
```python
gap_pct = 0.005  # 0.5% gap for scenarios
scenarios = {
    "Gap Up (opens above today's High)": c2["high"] * (1 + gap_pct),
    "Flat / Inside (opens at today's Close)": c2["close"],
    "Gap Down (opens below today's Low)": c2["low"] * (1 - gap_pct),
}
```