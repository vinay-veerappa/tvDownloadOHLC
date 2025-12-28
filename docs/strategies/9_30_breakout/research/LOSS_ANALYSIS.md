# 9:30 Strategy: Loss Analysis & Mitigation

## Overview
Analysis of 10 years (2016-2025) of NQ 9:30 breakout trades to categorize losses and identify high-probability avoidance zones.

---

## 📉 Categorizing the Wins & Losses

### 1. Market Regime Impact (The "Alpha" Killer)
The single biggest factor in strategy success is the underlying market regime.

| Regime | Win Rate | PnL Expectancy |
|:---|:---:|:---|
| **BULL** | **45.6%** | High positive expectation |
| **BEAR** | **18.1%** | Significantly negative |

**Insight**: The strategy relies on follow-through expansion. In Bear regimes, "The Snap" (9:30 - 9:34) often results in a "Bull Trap" where the breakout fails almost immediately as sellers use the liquidity to enter.

### 3. Profit Excursion (MFE) & Target Optimization
We analyzed the potential excursion (MFE) for win-rate and PnL sensitivity between 0.1% and 1.0%.

| Target (Pct) | Win Rate | PnL Expectancy (Sum %) |
|:---|:---:|:---|
| 0.10% | 49.1% | +3.52 |
| **0.35%** | **26.7%** | **+12.22** |
| 0.45% | 25.0% | +13.54 |
| **0.90%** | **23.5%** | **+14.33** |

**Insight**: A small target (0.10%) doubles the win rate but destroys the expectancy because it cuts off runners. The "Golden Sweet Spot" is **0.90%**, but a **0.35%** target offers a much smoother equity curve with higher win rate while capturing most of the alpha.

### 4. Trade "Heat" (MAE) Analysis
Analysis of successful vs. failed trades shows a critical "Adverse Excursion" threshold.

| Outcome | Median MAE (Heat) |
|:---|:---:|
| **Winners** | **0.034%** |
| **Losers** | 0.104% |

**Insight**: 90% of winning trades never go against the entry price by more than **0.11%**. If a trade reaches -0.11% MAE, it is a high-probability failure and should be cut early.

### 5. VVIX "Fear" Correlation
Correlation with the Volatility of Volatility (VVIX) index reveals distinct danger zones.

| VVIX Level (Open) | Win Rate | PnL Sum |
|:---|:---:|:---:|
| Normal (85-115) | **28.3%** | +10.73 |
| **High (>115)** | **18.1%** | **-7.50** |

**Insight**: When VVIX is above **115**, market "fear" is too high for clean expansion. Breakouts frequently result in rapid whip-saws and traps.

---

## 🏎️ Pullback Theory: Entry Efficiency

We tested various pullback models to see if waiting for a retest improves the R/R profile and offsets the "missed trade" opportunity cost.

### 1. The Pullback Spectrum (5-Year Comparison)

| Entry Model | Fill Rate | Win Rate | Pts / Trade | Avg MAE (Heat) | Total PnL (Pts) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Market Breakout (Base)** | **100%** | **38%** | 1.77 | 31.2 | 2,285 |
| **Direct Retest (0%)** | 80.1% | 34% | 1.47 | 25.9 | 1,519 |
| **Shallow Pullback (25%)** | **68.5%** | **30%** | **2.76** | **21.9** | **2,434** |
| Midpoint Retest (50%) | 53.3% | 26% | 3.33 | 17.6 | 2,284 |

### 2. The "Shallow 25%" Sweet Spot
- **Findings**: Waiting for 25% penetration into the 9:30 range before entering provides the highest absolute PnL.
- **Improved Efficiency**: Even though we miss ~31.5% of breakouts, our **Profit per filled trade increases by 56%** (from 1.77 to 2.76 pts).
- **Reduced Risk**: Average "Heat" (MAE) dropped by **30%** (31 pts down to 21 pts), allowing for tighter psychological stops.

### 3. Prudence Analysis: When to Wait vs. Skip
Waiting for a pullback isn't just about better R/R; it functions as a **Natural Safety Net**.

- **Loss Mitigation**: 16.2% of trades that fail as standard breakouts **NEVER fill** a pullback order, saving you from a full stop-loss paper cut.
- **High VVIX Protection**: In high-fear environments (VVIX > 115), the safety net is even stronger, avoiding **23.0%** of potential losses.
- **Regime Divergence**:
  - **Bull Regimes**: Higher fill rates (70%). Pullbacks are reliable entry points.
  - **Bear Regimes**: Lower fill rates but **Higher Alpha** (3.44 pts per trade). If you catch a Bear pullback, the expansion is usually more violent.

### 4. Granular VVIX Performance Bins
Analysis of pullback entries (Shallow 25%) across specific volatility ranges:

| VVIX Range | Fill Rate | Win Rate | Pts / Trade | Recommendation |
| :--- | :---: | :---: | :---: | :--- |
| **Low (<85)** | 72.3% | 26.2% | -0.52 | **SKIP** (Low momentum) |
| **Mid (85-98)** | 67.8% | 30.7% | +1.49 | Standard Trade |
| **Elevated (98-115)** | **67.4%** | **32.3%** | **+8.07** | **AGGRESSIVE** (Sweet Spot) |
| **Extreme (>115)** | 67.9% | 26.0% | +0.10 | **WAIT** (Safety Net only) |

**Key Insights**:
- **The Sweet Spot (98-115)**: This range provides the highest edge. Pullbacks are not only safer but significantly more explosive, capturing 4x more profit than the "Mid" range.
- **The Safety Net (>115)**: While the win rate is lower, waiting for a pullback avoids **23% of breakout losses** that never fill, providing critical protection when the market is chaotic.
- **The Trap (<85)**: Paradoxically, very low VVIX is the worst environment for pullbacks because the "re-test" often indicates a total lack of momentum rather than a healthy breather.

---

## 🛡️ Mitigation Strategies

### 1. Regime-Based Filtering (Priority 1)
> [!IMPORTANT]
> **Mitigation**: Implement a "Regime Filter" using the Previous Day's 20-day Simple Moving Average (SMA).
> - **Bias BULL**: Trade normally (Target ~45% WR).
> - **Bias BEAR**: **REDUCE SIZE** by 50% or **SKIP** initial breakout. In Bear regimes, wait for the *reversal* (fading the first breakout) which often has higher probability.

### 2. The "Tuesday" Effect
Historical data shows Tuesdays are the worst performing day for pure ORB breakouts across multiple assets.
**Mitigation**: The **V2 Strategy** already incorporates "Tuesday Avoidance".

### 3. Dynamic Stop Loss Adjustment
Currently, the stop is often at the opposite side of the 9:30 range. On wide candle days (Q4), this stop is too far, leading to poor R/R.
**Mitigation**: Cap the stop loss at a maximum of **0.20% of the open price**. If the 9:30 range is wider than this, the stop is "structural" inside the range rather than at the extreme.

### 5. Volatility Filter (VVIX)
> [!CAUTION]
> **Mitigation**: Monitor the VVIX level at the 9:30 AM open.
> - **IF VVIX > 115**: **SKIP** all breakout attempts. The probability of follow-through is mathematically negative.

### 6. The "MAE Heat Filter" (Early Stop)
> [!TIP]
> **Mitigation**: Implement a "Maximum Heat" rule.
> - **Rule**: If the trade hits **-0.12% adverse excursion** (MAE), close immediately. This protects capital by cutting 90% of eventually failed trades before they hit the full range-low stop.

### 7. Avoid "Covering the Queen" (Early Scale-outs)
Data analysis shows that taking partial profits (50% at 1R) and moving stops to BE actually **reduces Total PnL** by ~20% over 5 years.
**Mitigation**: Stay with the core runner. Take full profit at the target (0.35% or 0.90%) or exit at the hard time limit (10:00 AM).

### 8. The "Early Exit" Rule (Close Inside Range)
Comparing versions with and without the "Early Exit" rule (closing as soon as the price closes back inside the opening candle):
- **With Early Exit**: $23.5\%$ Win Rate | **+12.1 PnL**
- **Without Early Exit**: $38.0\%$ Win Rate | +7.7 PnL

**Insight**: While the "Early Exit" rule lowers the win rate (by cutting trades that might eventually work), it significantly boosts PnL by preventing small paper-cuts from turning into full stop-losses. 

---

## 🔍 Comparison with Mickey's Trade Log

Deep-dive comparison against Mickey's external backtest ($82\%$ Win Rate) revealed critical operational differences:

### 1. Entry Efficiency & "Sync"
Mickey's entries are NOT strict 1-minute candle breakouts. 
- **Finding**: $55\%$ of Mickey's entries occurred >5 pts away from the 9:30 range boundaries. 
- **Probable Strategy**: Mickey likely enters on **limit pullbacks** to the range high/low or uses a different candle timeframe (e.g., 5-min range), giving him a significantly better average entry price.

### 2. Price Scaling (Back-Adjustment)
Our backtest uses **back-adjusted** continuous futures data (standard for multi-year analysis). Mickey's log uses **unadjusted** absolute prices. 
- **Result**: Absolute entry price comparison is skewed (prices shifted by >3000 pts in 2008-2012 due to roll gaps). However, the **relative mechanics** (excursion ratios and win rates) remain comparable.

### 3. The "Early Exit" Discrepancy
Mickey does NOT use an automated early exit for closes inside the range. Replacing our "Early Exit" with his looser stop methodology:
- Reclaims $88\%$ of same-direction losses.
- **BUT**: It introduces higher drawdown as losers hit the full stop.
- **Conclusion**: Mickey's higher win rate is likely achieved through **Entry Selection** (pullbacks) rather than Exit Strategy.

---

---

## Summary of Optimization Rules
To maximize Alpha, the 9:30 Strategy should be traded with the following filters:
1. **Regime**: LONG only in Bull Bias (Price > SMA20).
2. **Tuesday**: Skip entirely.
3. **VVIX**: Skip if > 115.
4. **Target**: 0.35% (Conservative) or 0.90% (Aggressive).
5. **MAE Filter**: Cut early if adverse excursion > -0.12%.
6. **Early Exit**: KEEP "Close Inside Range" for PnL preservation, even if it lowers win rate.
7. **Entry**: Prefer limit orders at **25% penetration** into the 9:30 range (Shallow Pullback) rather than market-in on breakout close. This increases points-per-filled-trade by **+56%**.
8. **Attempts**: Max 3 entries within the 9:31-9:35 window.

---
*Analysis Date: December 27, 2025*
*Data Source: scripts/backtest/9_30_breakout/results/*
