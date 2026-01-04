# ICT Time Levels Strategy

**Sources**:  
- [TTrades: Important Time Levels For Trading](https://www.youtube.com/watch?v=EYzP7c24AwM)  
- [MMT Trading: How To Trade ICT's 9:30 OPEN](https://www.youtube.com/watch?v=JRyVueQZZbc)  

**Last Updated**: January 4, 2026  
**Status**: Documented, Awaiting Validation

---

## Executive Summary

This strategy uses **key time levels** (midnight, 8:30, 9:30) to determine bias and identify high-probability trades. Both sources confirm the same core rule:

> **Below midnight + 8:30 = DISCOUNT → Only look for LONGS**  
> **Above midnight + 8:30 = PREMIUM → Only look for SHORTS**

---

## Key Time Levels (Eastern Time)

| Time | Significance | Primary Use |
|------|-------------|-------------|
| **12:00 AM** | New daily candle (midnight open) | S/R, premium/discount |
| **8:30 AM** | News embargo lifts | Judas swing, order block |
| **9:30 AM** | NYSE opens | Order pairing, breaker formation |
| **10:00 AM** | New 4-hour candle | 4H Power of Three |
| **11:30 AM** | Cutoff | Midnight/8:30 levels expire |
| **2:00 PM** | New 4-hour candle | Retracement, continuation |

---

## Core Rule: Premium vs Discount

### The "Training Wheels" Rule (MMT Trading)

| At 9:30 Open | Position | Action |
|--------------|----------|--------|
| Below midnight AND below 8:30 | **DISCOUNT** | **ONLY LONGS** |
| Above midnight AND above 8:30 | **PREMIUM** | **ONLY SHORTS** |

### Deep Premium / Deep Discount (MMT Trading)

| Condition | Status | Probability |
|-----------|--------|-------------|
| Below midnight + 8:30 + below old sell-side | **Deep Discount** | HIGH PROB LONG |
| Above midnight + 8:30 + above old buy-side | **Deep Premium** | HIGH PROB SHORT |

---

## Order Pairing & Breakers (MMT Trading)

### What is Order Pairing?
At 9:30, price often "pairs orders" with liquidity pools from pre-market (runs stops before reversing).

### The Breaker Rule
> *"Anytime you have orders being paired, you always have a breaker"*

- **Bullish**: Low → High → Low sweep = Bullish Breaker
- **Bearish**: High → Low → High sweep = Bearish Breaker
- After breaker forms, trust the PDAs on the right side of the curve

---

## 4-Hour Power of Three (TTrades)

| Candle | Time | Bullish Sequence | Bearish Sequence |
|--------|------|------------------|------------------|
| 10:00 AM | 4H start | Open → Low → High → Close | Open → High → Low → Close |
| 2:00 PM | 4H start | Retracement or continuation | Retracement or continuation |

---

## Time Cutoff (MMT Trading)

> *"Once you get past 11:30 AM, you disregard those openings"*

- Midnight and 8:30 levels are **only valid until 11:30 AM**
- Exception: FOMC or high-impact news in PM session

---

## Trading Framework (Combined)

```
Step 1: At 9:30, determine position relative to:
        - Midnight open
        - 8:30 open
        - Old liquidity pools (buy-side/sell-side)

Step 2: Apply the Premium/Discount Rule:
        - Below both = DISCOUNT → Only LONGS
        - Above both = PREMIUM → Only SHORTS

Step 3: Watch for 9:30 order pairing (Judas swing into liquidity)

Step 4: After pairing, look for BREAKER formation

Step 5: Enter at breaker OR fair value gap after shift

Step 6: Use 10:00/2:00 for 4H OHLC timing

Step 7: Disregard midnight/8:30 levels after 11:30 AM
```

---

## Example Patterns

### High Probability Long Setup (Deep Discount)
1. Price below midnight open
2. Price below 8:30 open
3. Price below old sell-side liquidity
4. 9:30 sweeps sell-side (pairs orders)
5. Bullish breaker forms
6. Enter long at FVG or breaker retest
7. Target: Buy-side liquidity above

### High Probability Short Setup (Deep Premium)
1. Price above midnight open
2. Price above 8:30 open
3. Price above old buy-side liquidity
4. 9:30 sweeps buy-side (pairs orders)
5. Bearish breaker forms
6. Enter short at FVG or breaker retest
7. Target: Midnight open or sell-side below

---

## Judas Swing Detection (TTrades)

| Setup | What Happens | Result |
|-------|--------------|--------|
| **Bullish** | 8:30/9:30 makes run DOWN, closes over | Order block formed → Expect higher |
| **Bearish** | 8:30/9:30 makes run UP, closes below | Order block formed → Expect lower |

---

## Source Comparison

| Concept | TTrades | MMT Trading | Status |
|---------|---------|-------------|--------|
| Midnight as S/R | ✓ | ✓ | **Confirmed** |
| 8:30 as reference | ✓ | ✓ | **Confirmed** |
| Premium/Discount rule | ✓ | ✓ | **Confirmed** |
| Only longs in discount | ✓ | ✓ | **Confirmed** |
| Only shorts in premium | ✓ | ✓ | **Confirmed** |
| Judas swing at 9:30 | ✓ | ✓ (order pairing) | **Confirmed** |
| Breaker formation | Not detailed | **✓ Detailed** | MMT adds detail |
| 11:30 cutoff | Not mentioned | **✓** | MMT only |
| 10:00/2:00 4H candles | ✓ | Not mentioned | TTrades only |

---

## Validation Tasks (TODO)

1. **Premium/Discount → Bias**: Does position at 9:30 predict direction?
2. **Deep Premium/Discount**: Does adding liquidity pool condition improve accuracy?
3. **11:30 Cutoff**: Do midnight/8:30 lose predictive power after 11:30?
4. **Order Pairing**: Does 9:30 sweep predict reversal?
5. **Breaker Formation**: Detect and track breaker patterns after 9:30
6. **4H OHLC**: Validate 10:00 and 2:00 candle behavior

---

## Overlap with Existing Research

| This Strategy | Our Existing Work |
|---------------|-------------------|
| Midnight open | ✗ Not tracked yet |
| 8:30 open | ✗ Not tracked yet |
| Premium/discount | ✓ Similar to ALN (Asia/London above/below) |
| 9:30 Judas | ✓ Tanja model (87-90% reversal rate) |
| Breaker | ✗ Not tracked yet |
| 4H OHLC | ✗ Not tracked yet |

---

## Quick Resume Prompt

> "I'm working on the ICT Time Levels strategy in `docs/strategies/9_30_breakout/ttrades/TIME_LEVELS.md`.
>
> Sources: TTrades + MMT Trading (both confirm same rules).
>
> Key concept: Below midnight+8:30 = ONLY LONGS, Above = ONLY SHORTS.
>
> I want to validate [premium-discount bias / 11:30 cutoff / breaker formation / 4H OHLC]."

---


---

## Validation Results (January 2026)

We validated these concepts using 2023-2024 NQ 1-minute data (515 trading days).

### Test 1: Simple Premium/Discount Rule
**Hypothesis**: Above Midnight+8:30 = Bearish (Premium), Below = Bullish (Discount).
- **Result**: **FAILED (Accuracy ~45%)**
- The simple rule is statistically invalid. Being in "discount" did not predict a bullish day.

### Test 2: Deep Premium/Discount (Liquidity Layout)
**Hypothesis**: Adding liquidity pool filters (Above PDH / Below PDL) improves accuracy.
- **Deep Premium** (Above PDH + Midnight + 8:30): **46.1% Bearish** (Better than random, but still weak)
- **Deep Discount** (Below PDL + Midnight + 8:30): **40.8% Bullish** (Counter-trend! Market continued lower)
- **Result**: **FAILED**. The market tended to trend *against* the reversal logic.

### Test 3: Judas Swing (Opposing Run)
**Hypothesis**: A move *against* the bias zone at 8:30/9:30 predicts a reversal.
- **9:30 Bearish Setup** (Premium + Move UP): Only **37.4%** reversed to Short.
- **Result**: **FAILED (Counter-Predictive)**. 
- **Key Finding**: If price is in a Premium Zone and moves UP at 9:30, it continues HIGHER **62.6% of the time**. It does not reverse as the "Judas" theory suggests.

### Conclusion
The specific mechanical rules described in these videos (Premium/Discount zones, opposing runs = reversals) did not work on NQ1 during the 2023-2024 period. The market showed strong **continuation** characteristics rather than the mean reversion implied by the strategy.

---

*Verified by `scripts/research/ttrades/validate_time_levels.py`*

