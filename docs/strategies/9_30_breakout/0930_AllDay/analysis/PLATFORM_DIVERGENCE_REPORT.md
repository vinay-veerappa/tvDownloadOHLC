# Platform Divergence Report: NinjaTrader vs TradingView
**Strategy**: ORB V5 (Breakout)
**Asset**: MNQ (Micro Nasdaq-100)
**Date**: January 10, 2026

## 1. Executive Summary
A deep-dive comparison of the strategy execution on NinjaTrader (using individual contracts, e.g., `MNQ 03-26`) versus TradingView (using back-adjusted continuous data, `MNQ1!`) revealed a significant **$8,270 P&L divergence** over the year 2023, despite 99% identical trade logic.

**The "Outcome Flip" Phenomenon**:
The divergence is driven by small price differences (~26 points) causing critical flips in trade outcomes (Win → Loss or Loss → Win) for trades that test the edges of TP/SL levels.

| Metric | NinjaTrader Results | TradingView Results |
|--------|---------------------|---------------------|
| **Data Source** | Individual Contract (Raw) | Back-Adjusted Continuous (Smoothed) |
| **Net P&L (2023)** | **+$1,723** | **+$9,993** |
| **Total Trades** | 1,213 | 1,284 |
| **Win Rate** | ~35% | ~36% |

---

## 2. Root Cause Analysis

### A. The ~26 Point Basis Offset
*   **NinjaTrader**: Trades the specific contract (e.g., `MNQ 03-26`). Prices are exact execution prices.
*   **TradingView**: Uses `MNQ1!` (Continuous Back-Adjusted). Historical prices are spliced and adjusted to remove gaps at rollovers.
*   **Impact**: On any given day in 2023, the price level in TV might be ~26 points different from the raw contract price NT traded.

### B. "Outcome Flips" (The Killer)
Because the strategy uses tight stops and Take Profits (TP1 @ 0.20%, TP2 @ 0.50%), a price shift of 26 points shifts the absolute levels of these orders relative to the wicks of the candles.

**Scenario**:
1.  **TradingView**: Wick touches TP1 exactly. Trade is a **WIN (+57)**.
2.  **NinjaTrader**: Due to the offset/basis, the same wick misses the relative TP level by 2 ticks, reverses, and hits the stop. Trade is a **LOSS (-$30)**.

**Analysis**:
We found **177 trades** (15% of volume) where this "Flip" occurred.
*   **Dec 04, 2023**: NT Loss (-$57, MAE) vs TV Win (+$72, TP). Diff: **-$130**.
*   **Oct 12, 2023**: NT Loss (-$19, MAE) vs TV Win (+$70, TP). Diff: **-$90**.

The cumulative effect of these edge cases is massive: **$8k difference**.

---

## 3. Which One is "Real"?
**NinjaTrader represents the harsh reality of live execution.**
TradingView's back-adjusted data is an idealization. While excellent for trend analysis, it "smoothes out" the volatility of contract rollovers and specific expiration wicks. Real trading happens on the individual contract with its specific liquidity and wicks.

**Key Takeaway**:
If a backtest on TradingView shows a $10k profit, expect significantly less ($2-5k) in live execution due to:
1.  **Basis/Data Differences**: As proven here ($10k → $1.7k).
2.  **Slippage/Commissions**: Further erodes the edge.

## 4. Recommendations for Live Trading
1.  **Trust NT for Execution Expectations**: Use the NinjaTrader backtest metrics (DRR, Drawdown) for capital planning, not TradingView's.
2.  **Use "Continuum" in NT**: To better match TradingView for *research*, set the NinjaTrader Data Series to "Continuum (Back Adjusted)". This will align the price levels closer to TV.
3.  **Buffer Your Edge**: A strategy needs a robust margin of error. If it breaks from a 26-point data shift, it is sensitive to noise.
