## Strict Audit: 3‑Hour Line vs Apex & 0‑5 Box Sequencing

### 1. Rule Fidelity & Domain Correctness

**Critical Failures**

| # | Blueprint Requirement | Implementation | Severity |
|---|-----------------------|----------------|----------|
| 1 | **5‑Stage Reversal Counter (Score 0–5)** includes **Step 0** – “Does price breach the $C_2$ Open price (Line in the Sand) in the direction of the reversal?” | Step 0 is **completely absent**. The code sums only steps 1–4, yielding a maximum score of 4. The classification thresholds (0=Line, 1‑2=Watch, 3=Probable Apex, 4‑5=Confirmed) are therefore **unreachable for score 5** and the entire scoring scale is shifted. | **CRITICAL** |
| 2 | **Step 4 – Instant Extreme Rule**: “Q1 fails to breach its 0‑5 box by ≥10 bps **and reverses**, establishing an Instant High/Low.” | The code’s `step4` is `not (breach_hi and breach_lo)`, i.e. **true whenever there is no whipsaw** (both directions breached). It does **not** check for a reversal after the failure. This makes `step4` almost always `True`, inflating the score and destroying the discriminatory power of the counter. | **CRITICAL** |
| 3 | **Step 1** – “Does price breach & accept outside the **09:30 RTH open range**?” | The code uses only the **09:30 open price** (`rth_open`), not the **opening range** (e.g. first 1‑minute high/low). It also applies a `momentum_threshold_points` filter that is not part of Step 1 in the blueprint. | **CRITICAL** |
| 4 | **Momentum threshold** – “10 basis points (0.10%)” for the 0‑5 box breach. | The code uses an **absolute point threshold** (`mom_threshold`) from `ticker_registry.json`. No basis‑point calculation is performed. For instruments where 10 bps ≠ the configured points, the rule is violated. | **MAJOR** |
| 5 | **Actual outcome classification** – “3‑Hour Apex (Reversal): Hour 2 reverses Hour 1 by sweeping Hour 1’s extreme, rejecting past the 50% midpoint, and establishing a major daily pivot.” | The code defines `is_apex = (h10_hi == block_hi) or (h10_lo == block_lo)`. This **does not verify a reversal**; a continuation that makes a new high in the 10:00 hour would be mis‑classified as an Apex. The check also uses exact floating‑point equality, which is fragile. | **CRITICAL** |

**Additional Domain Deviations**

- **Step 2** – “Accept past the 09:00 hour’s 50% midpoint line.” The code requires a **validation bar** (close beyond midpoint + next bar’s low/high stays beyond). The blueprint does not mandate a two‑bar confirmation; a single close beyond the midpoint may suffice. This makes Step 2 **more conservative** than intended, potentially missing valid acceptances.
- **Step 3** – “Does the 10:00 AM hourly candle take out the 09:00 AM high or low?” Correctly implemented.
- **0‑5 Box** – The box is built from 10:00–10:05 inclusive. If 1‑minute data has gaps, the box may be narrower than the true first 5 minutes. The blueprint says “first 5 minutes”, not “first 5 bars”. This is a minor fidelity issue.

---

### 2. Edge Cases & Failure Modes

| Scenario | Impact | Current Handling |
|----------|--------|------------------|
| **Holiday / half‑day sessions** (e.g. day after Thanksgiving, early close at 13:00 ET) | The 09:00–12:00 block may be present, but the script only checks for empty `bars_9`/`bars_10`. If the market opens late (e.g. 09:30), `bars_9` will be empty → date skipped. That is acceptable. However, if the market closes before 12:00, `bars_block` will be truncated and `block_hi`/`block_lo` may not represent the full 3‑hour block, leading to incorrect “actual outcome”. | No check for session end time. |
| **Missing 1‑minute bars** (data feed gaps) | Slicing by timestamp may return fewer bars than expected. The 0‑5 box range could be artificially narrow; the Q1 range could be incomplete. Step 2’s loop may not find a validation bar even if price accepted the midpoint. | No interpolation or resampling. |
| **Exact timestamp matching** for 09:30 RTH open | `df_1m[df_1m.index == pd.Timestamp(...)]` may return empty if the 09:30 bar is missing. Fallback to `h9_mid` is used, but then Step 1 uses a synthetic open, which is not the true RTH open range. | Fallback exists but is semantically wrong. |
| **Floating‑point equality in `is_apex`** | `h10_hi == block_hi` can fail due to floating‑point representation, causing false negatives. | No tolerance. |
| **`momentum_threshold_points` missing from config** | `cfg.get("momentum_threshold_points", 20.0)` provides a default, but 20 points may be inappropriate for non‑NQ tickers. | Default exists but may be wrong. |
| **`sample_dates` slicing** `[-6:-1]` | If fewer than 6 trading days exist, the list will be empty or raise an error. | No guard. |
| **`load_fused_data` returns empty DataFrame** | The script will crash when trying to slice. | No check. |
| **Whipsaw condition** (both directions breach the 0‑5 box by the threshold) | The code sets `step4 = False` for whipsaw, which is correct in spirit (no failure → no instant extreme). However, the blueprint does not explicitly address whipsaw; the rule is about failure to breach. A whipsaw is a double breach, so it should not trigger Step 4. The code’s handling is acceptable but the overall Step 4 logic is still broken. | Acceptable but moot given the larger flaw. |

---

### 3. Code Quality, Vectorization & Performance

**Non‑Vectorized Loop**  
Step 2 uses a Python `for` loop over `bars_10` (max 60 iterations). Performance impact is negligible, but the loop is fragile and harder to test. It could be vectorized with `.shift()` and boolean masks.

**Type Safety & Robustness**  
- `float()` casts on `.max()`/`.min()` are safe but unnecessary if the DataFrame contains floats.
- No `try`/`except` around data loading; any I/O error will crash the script.
- The function always returns `True`, regardless of success. It should return a boolean or a result summary.

**Memory / Leaks**  
No memory leaks. DataFrames are sliced and discarded; no large persistent objects.

**Logging**  
Only a single `logging.info` at module level. The verification script uses `print()` for output, which is acceptable for a CLI tool but inconsistent with the logging setup.

**Code Duplication**  
Timezone localization is repeated for `df_1d` and `df_1m`. Could be extracted.

---

### 4. Concrete Actionable Enhancements

#### 4.1 Restore the Full 5‑Stage Counter (Step 0)

Add Step 0 using the previous day’s open ($C_2$ Open) as the “Line in the Sand”.

```python
# Fetch previous day's open
prev_day = t_dt - timedelta(days=1)
c2_open = df_1d.loc[df_1d.index.date == prev_day, 'open']
if not c2_open.empty:
    c2_open = float(c2_open.iloc[0])
    # Step 0: price breaches C2 open in the direction of the reversal
    # For a bearish reversal, price must trade above C2 open then reverse below it, etc.
    # Simplified: did the 10:00 hour breach C2 open?
    step0 = (h10_hi > c2_open and h10_lo < c2_open)  # needs refinement per direction
else:
    step0 = False
```

*Note: The exact logic for Step 0 must be clarified from the methodology. The above is a placeholder.*

#### 4.2 Correct Step 4 – Instant Extreme Rule

Implement the true rule: Q1 **fails to breach** the 0‑5 box by the threshold **and then reverses** (price moves back inside the box or makes a new extreme in the opposite direction).

```python
# Compute 0-5 box with threshold
box_hi_thresh = box_hi + mom_threshold
box_lo_thresh = box_lo - mom_threshold

# Q1 high/low
q1_hi = float(bars_10_q1['high'].max())
q1_lo = float(bars_10_q1['low'].min())

# Failure condition: Q1 stays within the box + threshold (no significant breakout)
no_breakout = (q1_hi <= box_hi_thresh) and (q1_lo >= box_lo_thresh)

# Reversal condition: after Q1, price moves back across the box midpoint or makes a new opposite extreme
# Simplest: check if the 10:00 hour close is inside the 0-5 box (or opposite extreme)
h10_close = float(bars_10.iloc[-1]['close'])
reversal = (h10_close < box_lo) or (h10_close > box_hi)  # needs refinement: reversal means it went the other way
# Better: if no breakout, and the hour's low is below box_lo (for a failed upside) or high above box_hi (for failed downside)
# This requires knowing the initial direction. A robust approach:
if no_breakout:
    # If Q1 high failed to break out, look for a subsequent move below box_lo
    reversal_down = (bars_10['low'].min() < box_lo) and (q1_hi <= box_hi_thresh)
    # If Q1 low failed to break out, look for a subsequent move above box_hi
    reversal_up = (bars_10['high'].max() > box_hi) and (q1_lo >= box_lo_thresh)
    step4 = reversal_down or reversal_up
else:
    step4 = False
```

*This is a simplified version; the exact “Instant High/Low” definition should be coded precisely from the methodology.*

#### 4.3 Fix Step 1 – Use the RTH Opening Range

Define the RTH open range as the first 1‑minute bar after 09:30 (or first 5 minutes). Check for a breach of that range (high or low) without a points threshold.

```python
rth_open_bar = df_1m[df_1m.index == pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize('US/Eastern')]
if not rth_open_bar.empty:
    rth_open_hi = float(rth_open_bar.iloc[0]['high'])
    rth_open_lo = float(rth_open_bar.iloc[0]['low'])
else:
    # fallback: use first 5 minutes of RTH
    rth_open_start = pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize('US/Eastern')
    rth_open_end = pd.Timestamp(datetime.combine(t_dt, time(9, 35))).tz_localize('US/Eastern')
    rth_bars = df_1m[(df_1m.index >= rth_open_start) & (df_1m.index <= rth_open_end)]
    if not rth_bars.empty:
        rth_open_hi = float(rth_bars['high'].max())
        rth_open_lo = float(rth_bars['low'].min())
    else:
        rth_open_hi = rth_open_lo = h9_mid  # ultimate fallback

step1 = (h10_hi > rth_open_hi) or (h10_lo < rth_open_lo)
```

#### 4.4 Use Basis Points for the 0‑5 Box Threshold

Compute the threshold dynamically as 0.10% of the 09:00 hour’s midpoint (or the box price). This aligns with the blueprint.

```python
bps_threshold = 0.001  # 10 bps
mom_threshold = h9_mid * bps_threshold
# Optionally override with ticker-specific points if config provides a bps flag
```

#### 4.5 Correct the Actual Outcome Classification

Determine Apex vs Line based on **reversal behaviour**, not just whether the 10:00 hour set the block high/low.

```python
# Apex: 10:00 hour took out 09:00 extreme AND then closed back inside the 09:00 range (rejection)
took_out_high = h10_hi > h9_hi
took_out_low = h10_lo < h9_lo
closed_inside = h9_lo <= h10_close <= h9_hi
is_apex = (took_out_high or took_out_low) and closed_inside
actual_outcome = "3-Hour Apex (Pivot)" if is_apex else "3-Hour Line (Trend)"
```

#### 4.6 Robustness & Edge‑Case Handling

- **Check session hours**: Verify that the market is open until at least 12:00 ET on the given date (e.g. using a trading calendar).
- **Resample 1‑minute data** to a regular grid before slicing to avoid missing bars.
- **Use `np.isclose`** for floating‑point comparisons in apex detection.
- **Guard against empty DataFrames** after loading.
- **Handle short date lists** gracefully.
- **Return a structured result** (e.g. a DataFrame of results) instead of just printing.

#### 4.7 Code Quality Improvements

- Replace the Step 2 loop with a vectorized check:
  ```python
  closes = bars_10['close']
  lows = bars_10['low']
  highs = bars_10['high']
  above_mid = (closes.shift(1) > h9_mid) & (lows > h9_mid)
  below_mid = (closes.shift(1) < h9_mid) & (highs < h9_mid)
  step2 = above_mid.any() or below_mid.any()
  ```
- Use `logging` instead of `print` for consistency, or keep `print` for the final table but log debug info.
- Add a `__main__` guard that accepts `--ticker` and `--dates` arguments properly.

---

### Summary of Severity

| Issue | Severity |
|-------|----------|
| Missing Step 0 | CRITICAL |
| Step 4 logic completely wrong | CRITICAL |
| Step 1 uses open price instead of opening range | CRITICAL |
| Actual outcome misclassifies continuations as Apex | CRITICAL |
| Absolute points instead of basis points | MAJOR |
| Step 2 overly conservative (validation bar) | MINOR |
| Fragile floating‑point equality | MINOR |
| No session completeness checks | MINOR |
| Non‑vectorized loop (negligible) | MINOR |

**The component in its current form does not faithfully implement the master methodology and will produce misleading classifications.** The critical flaws must be resolved before any reliance on its output.