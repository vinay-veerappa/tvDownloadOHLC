# Validation Analysis: Raw Data Analysis vs. Strategy Trade Performance

## Executive Summary

**The 75% Noon Curve Claim:** Based on 20 years of data (2004-2024), the raw analysis shows that 75% of days in the 8AM-4PM New York session form a HIGH on one side of noon and a LOW on the other side.

**The Strategy:** The NoonCurve_Strategy v2.0a doesn't simply trade on the fact that this will happen—it's much more selective. It attempts to predict *which side* and only trades when very specific conditions align during the 12:00-13:30 entry window.

---

## 1. The Raw Data Analysis Methodology

### `verify_noon_curve.py` Logic

**What It Measures:**
```
For each trading day in 8AM-4PM New York session:
  1. Find the highest high and lowest low in the session
  2. Determine when each formed (AM = before noon, PM = after noon)
  3. Classify outcome:
     - Opposite Sides (75%): High on one side, Low on the other
     - Same Side AM (20%): Both High and Low formed before noon
     - Same Side PM (5%): Both High and Low formed after noon
```

**Key Constraints:**
- Looks at the SESSION high/low (not tick-by-tick)
- Uses CANDLE data (OHLC)
- Timezone: US/Eastern (handles EST/EDT automatically)
- Date range: 2004-2024 (20 years)
- Tickers: NQ1, ES1, YM1, RTY1, GC1, CL1

**Result:** ~75% probability that market forms high and low on opposite sides of noon

---

## 2. The Strategy Entry Logic

### NoonCurve_Strategy v2.0a Filters

The strategy adds **multiple layers of filtering** that the raw analysis does NOT apply:

#### A. **Setup Bias Detection (9AM-10AM Candle)**
- Tracks the **bias period candle** (first trading hour, 9-10AM ET)
- Uses `biasCandleOpen` and `biasCandleClose` to predict AM bias direction
- If close > open → bullish bias → expects 50% retrace down, then up
- If close < open → bearish bias → expects 50% retrace up, then down

#### B. **Q1 Tracking (First 90 minutes)**
- Identifies Q1 High and Q1 Low (8AM-9:30AM)
- Forms the "range" that Q2 might break
- If Q2 breaks Q1 extremes, it confirms the directional bias

#### C. **Entry Window Confirmation (12:00-13:30 ET)**
- Price MUST hit the 50% retracement zone (38.2%-61.8% typical range) during entry window
- Only trades when specific price action occurs during this 90-minute window
- This is the **selective filter** that dramatically reduces trade count

#### D. **Optional Filters (all toggle-able)**
- **Q2 Break filter**: Did Q2 (9:30AM-12PM) actually break Q1 extremes?
- **Market Structure**: HH/HL for bulls, LL/LH for bears
- **Gap filter**: Overnight gap threshold
- **Time-Gap filter**: Minutes between AM high and low formation (120-240m typical)
- **First Hour Candle**: Bias candle directionality
- **Range Bias**: Which extreme formed last?
- **Midpoint confirmation**: Did price close on the "right" side?

---

## 3. Key Differences (Why Discrepancy Exists)

| Aspect | Raw Analysis | Strategy |
|--------|--------------|----------|
| **Entry Condition** | Any day where 75% probability occurs | ONLY when: bias signals + retrace + entry window + filters |
| **Selectiveness** | 100% of eligible days (250-260/year) | ~10-20% of days (filtered heavily) |
| **Win Definition** | High/Low form on opposite sides | Price reaches TP level before SL |
| **Bias Prediction** | Not predicted; just counts outcome | Predicted from 9-10AM candle direction |
| **Entry Timing** | Any time (implicit) | ONLY 12:00-13:30 ET |
| **Price Target** | Not explicit; just observes extremes | 3-level TP scaling (50%-25%-25%) |
| **Stop Loss** | Not applied | Below range extreme (configurable) |
| **Slippage/Execution** | None (historical data) | Limit orders, potential slippage |
| **Entry Price** | Session open | 50% retracement zone |

---

## 4. Expected Win Rate Translation

### Raw Analysis → Strategy Cascade

**Starting Point:** 75% of days have opposite-side high/low formation

**Filter 1: Bias Candle Directionality**
- Only trade days where 9-10AM candle aligns with expected direction
- ~50% of "opposite side" days will have matching bias
- **Remaining: 75% × 50% = 37.5%**

**Filter 2: Entry Window Hit**
- Price must touch 50% retrace zone between 12:00-13:30
- Not all days will have this price action
- ~60% of bias-aligned days touch the zone
- **Remaining: 37.5% × 60% = 22.5%**

**Filter 3: Slippage & Execution**
- Limit order entry at exact zone price
- Actual fills occur at worse prices due to market conditions
- Reduces win rate by ~5-10 percentage points
- **Remaining: 22.5% × 90% = 20.25%**

**Filter 4: TP/SL Level Reach**
- Multi-TP scaling means position partially taken at various levels
- Some trades are SL hits, some scale into winners
- Win definition becomes "more wins than losses" across scaling
- Expected: 50-60% individual trade wins

---

## 5. Critical Questions to Answer

### Data Alignment
- [ ] What date range does the strategy backtest actually use?
- [ ] Does verify_noon_curve.py use the same date range?
- [ ] Are both analyses using the same ticker (NQ1 vs ES1 vs others)?

### Methodology Alignment
- [ ] How does the strategy define "entry" (bid vs ask vs mid)?
- [ ] How does raw analysis handle multiple highs/lows same day?
- [ ] Does entry window filtering match the analysis assumptions?

### Execution Alignment
- [ ] Are TP/SL levels in strategy same as implied by analysis?
- [ ] Does slippage model match reality?
- [ ] Are filters applied in the same order as analysis?

### Missing Piece: Q2 Break Logic
- [ ] The strategy has optional Q2 break filter—is this enabled?
- [ ] Does raw analysis account for Q2 behavior?
- [ ] Could Q2 breaks be the source of the discrepancy?

---

## 6. Validation Steps

### Phase 1: Run Raw Analysis on Backtested Date Range
```bash
python scripts/nqstats/noon_curve/verify_noon_curve.py
# Output: Probability distribution (75% / 20% / 5% assumed)
# Note the actual date range and ticker
```

### Phase 2: Extract Strategy Backtest Results
```
Need to:
1. Find the TradingView backtest CSV if it exists
2. Parse entry dates, entry prices, exit prices, P&L
3. Calculate win rate, average trade duration
4. Map to corresponding days in raw analysis
5. Check if "winning trades" align with "opposite side formation"
```

### Phase 3: Deep Analysis Script
```bash
python scripts/nqstats/noon_curve/deep_analysis_time_gaps.py  
# This script already exists and does detailed time-gap analysis
# Shows: time gaps, entry window state, news correlation, etc.
```

### Phase 4: Matching Comparison
```
For each day in strategy backtest:
  1. Did raw analysis predict "opposite sides"? YES/NO
  2. Did strategy take a trade? YES/NO
  3. Was strategy trade a win? YES/NO
  4. If raw analysis said YES but strategy said NO: Why?
     - Bias filter failed?
     - Entry window not hit?
     - Time-gap too large?
     - Q2 break detected?
  5. If raw analysis said YES and strategy said YES but trade lost:
     - TP/SL calculation issue?
     - Slippage worse than assumed?
     - Entry timing problem?
```

---

## 7. Hypotheses for Discrepancy

### Hypothesis A: Selection Bias
**If:** Strategy's 20% actual win rate vs. 75% raw probability

**Root Cause:** The strategy's filters are TOO selective and eliminate the 75% high-probability days, trading only the hardest setups.

**Evidence to Check:**
- Count total setups that would pass raw analysis (should be ~260/year for NQ1)
- Count setups strategy actually trades (~30-50/year for current settings)
- Overlap percentage

**Fix:** Loosen filters to capture more of the 75% probability

---

### Hypothesis B: Prediction Error
**If:** Strategy consistently picks the wrong direction

**Root Cause:** The 9-10AM bias candle doesn't actually predict 12PM-4PM direction reliably.

**Evidence to Check:**
- On days where strategy predicted BULL: what happened? UP or DOWN?
- On days where strategy predicted BEAR: what happened? UP or DOWN?
- Bias prediction accuracy should be ~50% if it's random

**Fix:** Replace bias logic or add confirmation

---

### Hypothesis C: Execution Timing
**If:** Entry window (12:00-13:30) is NOT when the retrace actually occurs

**Root Cause:** The AM extreme forms right at noon, leaving no room for 50% retrace and entry during this window.

**Evidence to Check:**
- Deep_analysis_time_gaps.py checks this explicitly
- Histogram of: time between AM low/high formation and entry window
- If most extremes form BEFORE noon, retrace won't happen during 12-1:30PM

**Fix:** Shift entry window OR change zone calculation

---

### Hypothesis D: TP/SL Miscalibration
**If:** TP levels are too tight or SL levels too loose

**Root Cause:** SL hits often, TP rarely hits → win rate tanks even if direction correct.

**Evidence to Check:**
- Compare preset SL size vs. ATR and typical intraday ranges
- Check TP levels: are they reachable in sessions with 75% opposite-side formation?

**Fix:** Calibrate SL (wider) and TP (tighter/smart) levels

---

### Hypothesis E: Data/Timezone Issues
**If:** Raw analysis and strategy use different time references

**Root Cause:** Timezone conversion error, daylight saving issues, or data misalignment

**Evidence to Check:**
- Both use America/New_York timezone explicitly? YES
- Same parquet data source?
- Same date range?

**Fix:** Align data sources

---

## 8. Expected Outputs

### Report Should Include:
1. **Raw Analysis Results:** 
   - Probability distribution (Opposite/Same-AM/Same-PM)
   - Date range analyzed
   - Ticker(s) used
   - Sample size (trading days)

2. **Strategy Backtest Results:**
   - Win rate (%)
   - Avg profit per trade ($)
   - Total trades and winning trades
   - Avg trade duration
   - Max drawdown

3. **Gap Analysis:**
   - Expected win rate given filters (theoretical)
   - Actual win rate (observed)
   - Delta and root cause

4. **Recommendations:**
   - Which filters help most? Which hurt?
   - Parameter adjustments needed?
   - Is the 75% claim still valid given these filters?

---

## 9. Next Steps

1. **Run verify_noon_curve.py** to confirm the 75% baseline
2. **Run deep_analysis_time_gaps.py** to understand timing dynamics
3. **Extract strategy backtest dates and results**
4. **Create matching analysis** that compares day-by-day
5. **Document all findings** in this report
6. **Propose and test adjustments** based on root cause

---

**Author:** Validation Analysis
**Date:** 2026-03-09
**Status:** Planning Phase - Awaiting Data Extraction
