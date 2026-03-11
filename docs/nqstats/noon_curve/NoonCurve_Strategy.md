# Noon Curve Trend Continuation Strategy

**Version**: 1.0
**Author**: NQStats-Derived
**Assets**: MNQ / NQ / ES (Equity Index Futures)
**Timeframe**: 1-Minute Execution, 5-Minute Confirmation
**Session**: 08:00 AM - 16:00 PM ET

---

## 1. THESIS

The Noon Curve is a **trend continuation** strategy built on a verified statistical edge:

> **~75% of the time, the session High and Low form on opposite sides of 12:00 PM (Noon).**
> — Verified: ES 74.9%, NQ 72.4% (10-year sample, 2014-2025)

**Core Insight**: If the AM session establishes one extreme (High or Low) within specific time and price windows, the PM session will produce the opposite extreme. This is NOT a mean-reversion play — it's a **continuation trade** exploiting the directional commitment revealed in the AM.

### Why This Works (Market Microstructure)
1. **AM Liquidity Sweep**: The 9:30-10:00 window generates the AM extreme via opening volatility, stop hunts, and institutional order flow
2. **Q2 Confirmation**: The 10:00-12:00 period validates direction by breaking the Q1 structural level
3. **PM Delivery**: The 12:00-15:00 window delivers the continuation to the opposite extreme with 75% probability
4. **Mechanical Entry**: The 40-60% retracement of the AM leg provides optimal risk/reward mechanical entry

### Statistical Foundation
| Metric | Value | Source |
|--------|-------|--------|
| Opposite Sides (NQ) | 72.4% | Noon Curve Verification |
| Opposite Sides (ES) | 74.9% | Noon Curve Verification |
| AM High/Low Time | 09:30-10:00 ET | NQStats Distribution |
| PM High/Low Time | 14:00-15:00 ET | NQStats Distribution |
| AM Extreme % from 8AM Open | ~0.5% (typical peak) | Net Change Curve |
| 9AM Green → NY Closes Green | 71.6% | 1H Continuation |
| IB Upper Half → Breaks IB High | 81.3% | Initial Balance |
| Q1 Sweep Fade (0-15min) | 82% | Hour Stats |

---

## 2. METHODOLOGY

### Phase 1: Pre-Qualifying the Day (08:00 - 09:30 ET)

**Gate 1 — ALN Bias** (08:00 AM)
- Check London/Asia interaction:
  - **LPEU** (London broke Asia High only) → **Bullish bias** (82.2% continuation)
  - **LPED** (London broke Asia Low only) → **Bearish bias** (76% continuation)
  - **LEA** (Engulfed both) → **No trade** (too volatile/ambiguous)
  - **Neither** → **No trade** (no directional commitment)

**Gate 2 — Gap Filter** (09:25 AM)
- If overnight gap > 0.3% from prior close → **Defense mode** (reduce size or skip)
- Inside open → **Expansion mode** (full size)

### Phase 2: AM Extreme Formation (09:30 - 10:30 ET)

**Step 1: Observe the AM Extreme**
- Track the 8:00 AM open price
- Track the developing session High and Low
- At 10:00 AM, check:
  - Did the AM Low form at -0.3% to -0.7% from 8AM open? → **Bullish setup** (AM low in expected range)
  - Did the AM High form at +0.3% to +0.7% from 8AM open? → **Bearish setup** (AM high in expected range)
  - If the extreme is outside this range → **Still valid** but less optimal

**Step 2: 9AM Candle Confirmation**
- 9AM candle GREEN → confirms bullish continuation bias (71.6%)
- 9AM candle RED → confirms bearish continuation bias (62.7%)
- Must align with ALN bias from Gate 1

**Step 3: Initial Balance (10:30 AM)**
- Mark the 09:30-10:30 High/Low as the "Initial Balance"
- 10:30 candle closes in Upper Half of IB → **Long bias confirmed** (81.3%)
- 10:30 candle closes in Lower Half of IB → **Short bias confirmed** (79.5%)

### Phase 3: Q2 Structural Confirmation (10:00 - 12:00 ET)

**The Critical Gate — Q1 High/Low Break**
- **Bullish**: Q2 (10:00-12:00) must break ABOVE the Q1 High (09:30-10:00 high)
- **Bearish**: Q2 (10:00-12:00) must break BELOW the Q1 Low (09:30-10:00 low)
- If Q2 does NOT break Q1's boundary → **No trade** (no structural confirmation)

This is the **primary filter**. Without it, the Noon Curve setup is not validated.

### Phase 4: Entry — The Retracement (12:00 - 13:30 ET)

**The Mechanical Entry**
After Q2 confirms direction by breaking Q1 boundary:

1. **Identify the AM Leg**: From AM Low to AM High (or vice versa for shorts)
2. **Calculate Retracement Zone**: 40% to 60% of the AM leg
   - **Bullish**: Entry zone = AM High - (0.4 to 0.6) × (AM High - AM Low)
   - **Bearish**: Entry zone = AM Low + (0.4 to 0.6) × (AM High - AM Low)
3. **Wait for Price to Enter the Zone**: Limit order at the 50% level, or market order on confirmation candle within the zone
4. **Entry Confirmation** (Optional tighter filter):
   - Bullish: Look for a bullish FVG or OB within the retracement zone
   - Bearish: Look for a bearish FVG or OB within the retracement zone

**Time Filter**: Entry should occur between 12:00-13:30 ET. If no retracement by 13:30, the setup is dead.

### Phase 5: Trade Management

#### Stop Loss (SL)
| Method | Level | Points (MNQ typical) |
|--------|-------|---------------------|
| **Primary SL** | Below the AM Extreme (Low for longs, High for shorts) | 15-25 pts |
| **Tight SL** | Below the 61.8% retracement level | 10-15 pts |
| **Maximum SL** | Never exceed 30 points on MNQ | 30 pts |

#### Take Profit — Multi-TP Scaling
| TP Level | % of Position | Target | Logic |
|----------|---------------|--------|-------|
| **TP1** | 50% | Break-even of the retracement (halfway back into the down-leg) | Defensive — protects if structure fails |
| **TP2** | 25% | AM High (for longs) / AM Low (for shorts) | Re-test of the AM extreme |
| **TP3** | 25% | New PM Extreme (14:00-15:00 window) | Full continuation target |

#### Trailing Stop (after TP1)
- Activate trailing stop after TP1 is hit
- Trail by 10-15 points behind price
- This protects remaining 50% of position while allowing PM extension

---

## 3. MAE / MFE EXPECTATIONS

### Maximum Adverse Excursion (MAE)
*How far does price typically move against you before going to target?*

| Scenario | MAE (Points MNQ) | MAE (% of leg) | Notes |
|----------|------------------|-----------------|-------|
| **Optimal Entry (50% retrace)** | 5-12 pts | 10-20% of AM leg | Tight — enters at equilibrium |
| **Aggressive Entry (40% retrace)** | 8-18 pts | 15-30% of AM leg | Slightly more heat |
| **Late Entry (post-13:00)** | 12-25 pts | 20-40% of AM leg | Too much slippage |
| **Failed Setup (25% of time)** | Full SL hit | >60% retrace | Structure breakdown — SL protects |

**Risk Budget**: Design SL to survive the 95th percentile MAE of winning trades (~20 pts MNQ).

### Maximum Favorable Excursion (MFE)
*How far does price typically move in your favor?*

| Scenario | MFE (Points MNQ) | MFE (% move from 8AM) | Notes |
|----------|------------------|------------------------|-------|
| **Median Day** | 40-60 pts | 0.5-0.8% from entry | Standard continuation |
| **Strong Trend Day** | 80-120 pts | 1.0-1.5% from entry | Full ADR expansion |
| **Weak Continuation** | 15-25 pts | 0.2-0.3% from entry | TP1 hit, TP2/3 stopped |

**Expected Value**: With 72-75% win rate and 2:1 average RR (TP1 defensive + TP2/3 runners):
- **Win**: 72% × avg 35pt gain = +25.2 pts expected
- **Loss**: 28% × avg 20pt loss = -5.6 pts expected  
- **Net Edge**: ~+19.6 pts per trade (before commissions)

---

## 4. RISK PARAMETERS

### Position Sizing ($3,000 Account — MNQ)
| Risk Level | Contracts | SL (20 pts) | Risk $ | % of Account |
|------------|-----------|-------------|--------|--------------|
| **Conservative** | 1 | 20 pts | $40 | 1.3% |
| **Standard** | 2 | 20 pts | $80 | 2.7% |
| **Aggressive** | 3 | 20 pts | $120 | 4.0% |

### Daily Limits
- **Max Daily Loss**: $300 (10% of $3,000 account)
- **Max Trades Per Day**: 1 (this is a once-a-day setup)
- **Max Concurrent Positions**: 1 (no pyramiding)

### Kill Switches
1. **No ALN Bias** → No trade
2. **Q2 doesn't break Q1** → No trade
3. **No retracement by 13:30** → No trade
4. **Gap > 0.3%** → Reduce to 1 contract
5. **AM extreme outside ±0.1% to ±1.0% from 8AM** → Caution (edge weakens at extremes)

---

## 5. SCORING SYSTEM (CONFLUENCE)

Each filter adds confidence. Trade with 4+ points of confluence:

| Filter | Points | Condition |
|--------|--------|-----------|
| ALN Bias (LPEU/LPED) | +2 | Matches trade direction |
| 9AM Candle Color | +1 | Matches trade direction |
| IB Close Position | +1 | Upper half = long, lower = short |
| Q2 Breaks Q1 Boundary | +2 | **MANDATORY** (gate) |
| AM Extreme in Expected Window (9:30-10:00) | +1 | Time alignment |
| AM Extreme in Expected Range (±0.3-0.7%) | +1 | Price alignment |
| Net Change SDEV alignment | +1 | Price at/near distribution peak |
| FVG/OB in retracement zone | +1 | ICT structural confluence |

| Score | Action |
|-------|--------|
| **7-10** | Full size (2-3 contracts) |
| **5-6** | Standard size (1-2 contracts) |
| **4** | Minimum size (1 contract) |
| **< 4** | **NO TRADE** |

---

## 6. EXAMPLE WALKTHROUGH (from ExampleNoonCurveTrade.md)

| Step | Time | Observation | Score |
|------|------|-------------|-------|
| ALN Check | 08:00 | Pattern 4 (LPED → sweep London lows) → Bullish after sweep | +2 |
| AM Low | 09:50 | Low at -0.51% from 8AM open (within -0.3 to -0.7%) | +1 (time) +1 (price) |
| 9AM Candle | 10:00 | Check color for bias confirmation | +1 if green |
| Q2 Breaks Q1 High | 10:00-12:00 | Q2 broke above Q1 high → **CONFIRMED** | +2 |
| Noon Check | 12:00 | AM low locked, expect PM high | +0 (already counted) |
| Entry | 12:00-13:00 | 50% retracement of AM low → AM high leg | ENTER LONG |
| TP1 | ~12:30 | Halfway back up the minor pullback → Scale 50% | LOCK PROFIT |
| TP2/TP3 | 14:00-15:00 | New PM high target | EXIT REMAINING |

**Result**: Picture-perfect setup. AM low at correct time and price, Q2 confirmed, textbook 50% retracement, PM high delivered.

---

## 7. PINESCRIPT IMPLEMENTATION

See: [NoonCurve_Strategy.pine](NoonCurve_Strategy.pine)

The strategy implements all phases above with:
- Automated AM extreme tracking (8AM open, session H/L)
- % net change calculation from 8AM open
- Q1/Q2 structural break detection
- Fibonacci retracement zone calculation (40-60%)
- Multi-TP exit management (50%/25%/25%)
- Trailing stop activation after TP1
- Confluence scoring dashboard
- Time-based kill switches
- Full MAE/MFE tracking via strategy tester
