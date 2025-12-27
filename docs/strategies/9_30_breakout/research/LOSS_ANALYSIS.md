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

### 2. Volatility (Range Size) Impact
We analyzed win rates by 9:30 candle range size (in points).

| Range Quartile | Avg Win Rate |
|:---|:---:|
| **Q1 (Smallest: <8 pts)** | **38.1%** |
| **Q2 (Medium: 8-16 pts)** | 33.6% |
| **Q3 (Large: 16-25 pts)** | 38.6% |
| **Q4 (Extreme: >25 pts)** | 34.9% |

**Insight**: Absolute point size is less predictive than regime, but moderate-to-large ranges (Q3) actually perform slightly better than mid-range (Q2), likely due to the presence of genuine institutional buy/sell pressure.

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

### 4. Time-of-Entry Filter
Breakouts occurring after **09:40 EST** have a higher failure rate as they run into the 9:45 reversal window.
**Mitigation**: Tighten the entry window to **09:31 - 09:35 EST** only. If it hasn't broken out by then, the "initial" impulse is likely exhausted.

---

## Summary of Findings
The strategy's "low" win rate is partially a byproduct of its trend-following nature (waiting for big runners). However, by **eliminating Bear regime trades** and **Tuesdays**, the mathematical expectancy shifts from a marginal profit to a robust Alpha source.

---
*Analysis Date: December 26, 2025*
*Data Source: scripts/backtest/9_30_breakout/results/*
