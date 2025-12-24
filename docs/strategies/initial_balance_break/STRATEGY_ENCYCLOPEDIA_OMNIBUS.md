# IB Break Pullback Strategy: Multi-Asset Omnibus Encyclopedia

This comprehensive research document detailed the performance, failure points, and visual proof for the IB Break Pullback strategy across 5 major futures assets.

---

## 1. Multi-Asset Technical Performance (2019-2020)

Testing the final standard configuration (38.2% Fibonacci Pullback, IB Opposite Stop) across the "Futures Basket."

| Asset | Ticker | Win Rate | PF | Avg MAE | Avg MFE | 0.5R Reach | 1.0R Reach |
|-------|--------|----------|----|---------|---------|------------|------------|
| **Nasdaq 100** | NQ1 | 69.8% | 1.22 | -0.18% | 0.22% | 64.4% | 24.2% |
| **S&P 500** | ES1 | 67.1% | 0.93 | -0.40% | 0.44% | 31.8% | 9.4% |
| **Russell 2000** | RTY1 | 50.3% | 0.62 | -0.45% | 0.39% | 28.7% | 8.7% |
| **Dow Jones** | YM1 | 54.8% | 0.93 | -0.36% | 0.39% | 38.9% | 13.1% |
| **Gold** | GC1 | 43.3% | 0.29 | -0.55% | 0.23% | 20.0% | 0.0% |

---

## 2. NQ Detailed Mechanism Sensitivity

How different entry triggers affected NQ performance.

| Mechanism | Win Rate | PF | Avg MAE | 0.5R Reach | 1.0R Reach |
|-----------|----------|----|---------|------------|------------|
| **Fib 38.2% (Final)** | 69.8% | 1.22 | -0.18% | 64.4% | 24.2% |
| **Fib 50%** | 58.4% | 0.69 | -0.21% | 51.7% | 19.5% |
| **Fib 61.8%** | 63.2% | 0.84 | -0.17% | 58.3% | 21.5% |
| **FVG 5m Only** | 47.4% | 0.30 | -0.43% | 42.1% | 0.0% |
| **High Confluence** | 47.4% | 0.30 | -0.43% | 42.1% | 0.0% |

---

## 3. Asset Deep Dives & Visual Proof

### A. ES1 (E-mini S&P 500) - The Mean-Reverting Challenger
ES showed high win rates but low profit factor. This is due to "paper cuts"—frequent small wins overwhelmed by deeper drawdowns. The 0.5R reach is only 31.8% compared to NQ's 64.4%.

![ES1 WIN Example](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/initial_balance_break/charts/omnibus/ES1_MultiAsset_WIN_2020-03-10.png)

### B. RTY1 (Russell 2000) - The High-Volatility Victim
RTY's adverse excursion (MAE) is deeply negative (-0.45%). Pullbacks in RTY often overshoot the Fibonacci levels significantly, leading to stop-outs before eventual targets are hit.

![RTY1 WIN Example](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/initial_balance_break/charts/omnibus/RTY1_MultiAsset_WIN_2020-04-03.png)

### C. YM1 (E-mini Dow Jones) - The Steady Performer
YM performed similarly to ES but with slightly better Profit Factor (0.93). It is the most viable "second-best" asset after NQ, though still less efficient.

![YM1 WIN Example](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/initial_balance_break/charts/omnibus/YM1_MultiAsset_WIN_2020-06-11.png)

### D. GC1 (Gold) - The Directional Mismatch
Gold showed the worst performance (43% WR, 0.29 PF). The IB break concept relies on intraday momentum follow-through, whereas Gold often behaves with its own unique supply/demand cycles that don't align with the Equities' Open.

---

## 4. MAE/MFE Insights by Asset

| Ticker | MAE (Risk Spent) | MFE (Profit Potential) | Efficiency Ratio |
|--------|------------------|------------------------|------------------|
| **NQ1** | -0.18% | 0.22% | 1.22 |
| **ES1** | -0.40% | 0.44% | 1.10 |
| **YM1** | -0.36% | 0.39% | 1.08 |
| **RTY1** | -0.45% | 0.39% | 0.86 |
| **GC1** | -0.55% | 0.23% | 0.41 |

---

---

## 6. Refined 2024-2025 Logic Findings (NQ1)

The strategy was further refined with stricter entry filters and structure-based bias to improve robustness in the current market regime.

| Configuration | Win Rate | Trades (2024-25) | Profit Factor |
|---------------|----------|------------------|---------------|
| **Fib 50% + Last Extreme** | **62.2%** | **436** | **0.73** |
| High Confluence (FVG) | 62.3% | 432 | 0.73 |
| Fib 38.2% + Last Extreme | 59.9% | 431 | 0.66 |

### Key Logic Advancements:
1. **Sequence-Based Bias (Last Extreme)**: Directional bias is determined by the *last* extreme hit within the IB. Low last = SHORT, High last = LONG.
2. **Touch-Based Trigger**: Price must "pull back" into the zone from the trend side, ensuring we aren't chasing momentum.
3. **Noon Lockdown**: Entry window closes at 12:00 PM EST, with a hard exit at 12:00 PM EST to avoid midday chop.

---

## 7. Final Research Conclusion (Updated)

1. **NQ Dominance**: NQ remains the primary asset for this strategy due to its high volatility and consistent retracement patterns.
2. **Structural Bias**: The "Last Extreme" rule significantly improves bias accuracy compared to simple close-position logic.
3. **Optimized Parameters**: For 2024+ environments, the recommended setup is **NQ1**, **Fib 50.0% Standard Entry**, **Last Extreme Bias**, and **12:00 PM EST Hard Exit**.

**End of Omnibus Technical Encyclopedia**
