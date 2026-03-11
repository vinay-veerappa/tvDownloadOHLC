# Noon Curve Strategy Gap Analysis

**Date**: March 9, 2026  
**Strategy File**: `NoonCurve_Strategy.pine` (v1.0)  
**Research Reference**: Noon Curve Statistics (NQStats)

---

## Executive Summary

The strategy is **NOT implementing the noon curve hypothesis correctly** and is using a **different directional bias** than what the research validates. This mismatch explains why the strategy's probability performance does not align with the 72-75% research edge.

**Key Finding**: The strategy uses "Last Extreme in AM" as directional bias, while the research validates "Time-based Opposite Sides" probability.

---

## 1. Research Hypothesis (What the Stats Say)

### The Validated Edge (72-75% Probability)

**Noon Curve Research Finding**:
- **72.4%** (NQ1) to **74.9%** (ES1) of the time, the Session High and Session Low form on **opposite sides of 12:00 PM**.
- This is a **time-based probability**, not a directional prediction.

**Research Data** (10 years, 2015-2025):
| Ticker | Opposite Sides | Same Side (AM) | Same Side (PM) |
|--------|---------------|----------------|----------------|
| **NQ1** | **72.4%** | 21.8% | 5.7% |
| **ES1** | **74.9%** | 18.1% | 7.0% |
| **YM1** | **72.3%** | 22.4% | 5.3% |

**What This Means Operationally**:
1. If BOTH the session high AND low are already set before 12:00 PM (pre-noon), there is a **72-75% probability** that one of them will break in the PM session.
2. The research does NOT tell you **which direction** the break will occur.
3. The research is about **time distribution** of extremes, not about trend continuation or range bias.

---

## 2. Strategy Implementation (What the Code Does)

### Current Strategy Logic (Lines 438-476)

```pine
// At entry window (12:00-13:30), determine bias:
float setupBiasHigh = i_rangeBiasSource == "IB (09:30-10:30)" ? ss.ibHigh : ss.amHigh
float setupBiasLow = i_rangeBiasSource == "IB (09:30-10:30)" ? ss.ibLow : ss.amLow
int setupBiasHighBar = i_rangeBiasSource == "IB (09:30-10:30)" ? ss.ibHighBar : ss.amHighBar
int setupBiasLowBar = i_rangeBiasSource == "IB (09:30-10:30)" ? ss.ibLowBar : ss.amLowBar

// Range direction = which extreme formed LAST
bool setupRangeBull = setupBiasReady and setupBiasHighBar > setupBiasLowBar  // High bar index > Low bar index
bool setupRangeBear = setupBiasReady and setupBiasLowBar > setupBiasHighBar  // Low bar index > High bar index
```

**What This Does**:
- Compares **bar indices** (timestamps) of AM High vs AM Low
- If `amHighBar > amLowBar` → **Bullish** (high formed after low)
- If `amLowBar > amHighBar` → **Bearish** (low formed after high)
- **Assumption**: The extreme that formed LAST indicates the direction PM will continue

### The Hypothesis Gap

| Aspect | Research Says | Strategy Does |
|--------|---------------|---------------|
| **Question Asked** | "Did high/low form on opposite sides of noon?" | "Which extreme formed LAST in AM?" |
| **Probability Edge** | 72-75% opposite sides (time-based) | Unknown (sequence-based) |
| **Directional Prediction** | No direction given—just says "one will break" | Strong directional bias (assumes continuation) |
| **Time Sensitivity** | Noon (12:00 PM) is the pivot | Timing within AM session matters |
| **Validation Status** | ✅ Validated with 10 years of data | ❌ NOT validated—different hypothesis |

---

## 3. Critical Disconnects

### Disconnect #1: Different Hypothesis Entirely

**Example Scenario**:
- **08:30 AM**: Price makes session LOW at 18,500 → `amLowBar = 30`
- **11:45 AM**: Price makes session HIGH at 18,650 → `amHighBar = 195`

**Strategy Interpretation**:
- `setupRangeBull = true` (high formed last)
- **Bias**: Expect PM to push HIGHER (bullish continuation)
- **Entry**: Buy on pullback to 50% retracement

**Research Interpretation**:
- Both extremes formed in AM (before noon)
- **Probability**: 72.4% chance ONE of them breaks in PM
- **Direction**: Could be EITHER way (no directional edge given)

**The Problem**: The strategy assumes "last extreme = continuation direction", but the research does NOT validate this. The research only tells you "a break will happen" but not which way.

---

### Disconnect #2: Ignoring "Same Side AM" Scenarios (21.8%)

**Research Finding**: 21.8% of days have BOTH high and low in AM, and NEITHER breaks in PM.

**Strategy Behavior**: 
- Strategy ALWAYS expects a breakout in PM if both extremes are in AM.
- This means **21.8% of the time**, the strategy is entering a trade based on a false premise (expecting breakout when range will hold).

**Impact**: ~1 in 5 trades are structurally flawed from the start.

---

### Disconnect #3: No Time-of-Day Validation

**Research Finding**: 
- AM extremes typically form **09:30-10:00**
- PM extremes typically form **14:00-15:00**

**Strategy Behavior**:
- Tracks AM high/low across entire 08:00-12:00 window
- Does NOT validate if extremes formed during high-probability time windows
- Enters at 12:00-13:30 without checking if AM extreme is "confirmed" by time

**Why This Matters**: 
- If AM high forms at 11:59 AM (just before noon), it's NOT a "clean AM extreme" — it's basically a noon price.
- Research probabilities assume extremes are CLEARLY in AM or PM, not edge cases near noon.

---

### Disconnect #4: Midpoint Confirmation Adds Unvalidated Filter

**Strategy Logic** (Lines 448-450):
```pine
bool setupMidBull = setupBiasReady and close > setupMid
bool setupMidBear = setupBiasReady and close < setupMid
bool gateRangeBear = not i_useRangeBias or (setupRangeBear and (not midConfirm or setupMidBear))
```

**What This Does**:
- Requires current price to be on the "correct side" of the AM range midpoint
- Bullish setup requires `close > midpoint`
- Bearish setup requires `close < midpoint`

**The Problem**:
- This filter is **NOT part of the noon curve research**
- It's an additional constraint that **reduces trade frequency** without validated edge
- May be filtering OUT valid trades that would have worked per research

---

## 4. Probability Math Breakdown

### Research Edge Chain

Starting with 1000 trading days:

1. **72.4%** (724 days) have opposite sides → **One extreme will break in PM**
2. But we don't know WHICH direction → **50/50 guess** = 362 correct directional calls
3. Of those 362, some will hit your entry zone → ~70% = **253 valid entries**
4. Of those 253, your TP/SL management determines win rate

**Expected Strategy Win Rate** (if aligned with research): ~60-65%

---

### Current Strategy Probability Chain

Starting with 1000 trading days:

1. Strategy filters by "last extreme" direction → Unknown base rate (NOT validated)
2. Adds 9AM candle filter → Reduces sample
3. Adds midpoint confirmation → Further reduces sample
4. Enters on 50% retracement → May miss entries entirely

**Issues**:
- **Base hypothesis is unvalidated** (last extreme ≠ noon curve)
- **Multiple filters compound uncertainty** without validated edges
- **No data shows "last extreme" predicts PM direction**

---

## 5. Why Probability Levels Don't Match

### The Strategy Is Solving a Different Problem

| Research | Strategy |
|----------|----------|
| "Will an AM extreme break in PM?" (72% yes) | "Will price continue in the last AM direction?" (unknown %) |
| Time-based probability | Sequence-based assumption |
| Validated with 10 years of data | Not validated |
| Non-directional (just says "a break") | Strongly directional |

### The Missing Validation

**To use "last extreme" as directional bias, you need to prove**:
1. What % of the time does the LAST AM extreme indicate PM direction?
2. Does this vary by market structure (trending vs ranging)?
3. How does 9AM candle color correlation with "last extreme"?
4. What's the base rate when midpoint confirmation is added?

**None of this data exists in your research.**

---

## 6. Recommended Fixes

### Option A: Align Strategy to Research (Conservative)

**Change**: Remove directional bias assumption. Trade BOTH directions simultaneously.

**Implementation**:
1. At 12:00 PM, if BOTH AM high and low are set, place:
   - Bullish limit order at 50% retracement from AM high (targeting new PM high)
   - Bearish limit order at 50% retracement from AM low (targeting new PM low)
2. Whichever fills first = your trade direction (the market tells you)
3. Cancel the unfilled order
4. 72.4% of the time, ONE of them will trigger and work

**Pros**: 
- Directly matches research hypothesis
- No directional guesswork
- Higher trade frequency

**Cons**: 
- May whipsaw if both orders fill on volatile days

---

### Option B: Validate "Last Extreme" Hypothesis (Data-Driven)

**Research Required**:
1. Run analysis: "When AM high forms AFTER AM low, what % of time does PM make new high?"
2. Separate by time windows (e.g., if low at 09:00 and high at 11:30, what's the edge?)
3. Add confluence: 9AM candle + last extreme + market structure
4. Measure edge at each step

**If edge exists** (>60% win rate), then strategy is valid but needs optimization.

**If edge doesn't exist** (50-55% win rate), then abandon "last extreme" logic entirely.

---

### Option C: Hybrid Approach (Best of Both)

**Implementation**:
1. Use noon curve time-based probability (72.4% edge) as SETUP filter:
   - Only trade when BOTH AM extremes are confirmed before 11:45 AM
   - This ensures you're in the 72.4% probability bucket
2. Use "last extreme" as DIRECTION hint (but with low confidence):
   - If high formed last + 9AM green → bullish bias
   - If low formed last + 9AM red → bearish bias
3. Add market structure as TIE-BREAKER:
   - If structure conflicts with "last extreme", skip trade (wait for confirmation)
4. Enter ONLY when all filters align (confluence)

**Pros**: 
- Leverages validated time-based edge (72.4%)
- Adds directional filters for trade selection
- Avoids forcing trades when signals conflict

**Cons**: 
- Lower trade frequency (high selectivity)
- Still need to validate "last extreme" edge

---

## 7. Key Metrics to Track

If you run backtest/forward test, track these metrics separately:

| Metric | Target | Current Strategy |
|--------|--------|------------------|
| **Opposite Sides Trade Rate** | 72.4% of days should have BOTH AM extremes set | Unknown |
| **Directional Accuracy (Last Extreme)** | Should be >60% if hypothesis is valid | Unknown |
| **9AM Candle Correlation** | Should be >65% if color predicts direction | Unknown |
| **Midpoint Confirmation Edge** | Should improve win rate by >5% | Unknown |
| **Same Side AM Filter** | Should skip ~22% of days (no breakout expected) | Not implemented |

---

## 8. Immediate Action Items

1. **Run Validation Script**: 
   - Modify `verify_noon_curve.py` to track "last extreme" direction
   - Calculate: "When amHighBar > amLowBar, what % of time does PM make new high?"
   - Repeat for opposite case

2. **Add Time Window Filters**:
   - Only accept AM extremes if they form 09:00-11:00 (avoid noon edge cases)
   - Skip days where AM range is tiny (<0.3% from 8AM open)

3. **Test Bi-Directional Entry**:
   - Remove directional bias
   - Place both bull and bear limit orders
   - Measure which one fills first and track win rate

4. **Separate "Same Side AM" Days**:
   - Add check: "Did both extremes hold through PM?" (21.8% of days)
   - On those days, strategy should NOT enter (research says no breakout)

---

## 9. Conclusion

### The Core Issue

**Your strategy is built on an unvalidated hypothesis** ("last AM extreme predicts PM direction") while claiming to use the noon curve edge (72-75% opposite sides probability).

**These are not the same thing.**

The noon curve research tells you:
- ✅ "A break will happen" (72.4% probability)
- ❌ NOT "which direction the break will be"

Your strategy assumes:
- "The direction of the last AM extreme = the direction of the PM continuation"
- This assumption is **NOT validated by the research data**

### Why Win Rates Are Lower Than Expected

1. **Base hypothesis mismatch**: Using wrong signal for direction
2. **21.8% of days have no PM breakout**: Strategy doesn't skip these
3. **Filters are stacked without validation**: Each filter needs individual edge proof
4. **Entry timing may miss fills**: 50% retracement may never get touched

### Path Forward

**Before making ANY code changes**:
1. Run the validation analysis (last extreme vs PM direction correlation)
2. Measure base rates for each filter independently
3. Decide if you want to align to research OR validate new hypothesis

**If data shows <55% edge on "last extreme"**: Abandon it. Use bi-directional entry.

**If data shows >65% edge on "last extreme"**: Keep it. Add time/structure confluence.

---

## Appendix: Research Data Reference

**Source**: `scripts/nqstats/results/noon_curve_verification.csv`

**NQ1 (Nasdaq Futures)**:
- Opposite Sides: 72.42% (2,054 days out of 2,836 total)
- Same Side (AM): 21.83% (619 days) — **NO PM BREAKOUT**
- Same Side (PM): 5.75% (163 days)

**Validation Period**: 2015-2025 (10 years)
**Data Source**: 1-minute OHLC data
**Session Definition**: 08:00-16:00 ET
**Noon Pivot**: 12:00 PM ET
