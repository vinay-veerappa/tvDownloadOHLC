# 9:30 Breakout Analysis Report (NQ1)
**Generated Algorithmically**
**Range Analyzed:** 2008-01-02 to 2025-12-24 (4492 Trading Days)

## Executive Summary
This analysis tests the predictive power of the **9:30 AM 1-minute candle direction**.
- **Theory:** If the 9:30 candle is Green (Bullish), the market should extend further UP (MFE) than DOWN (MAE).
- **Metric:** Extensions are measured as % change from the 9:30 High/Low.

## Statistical Findings

| Window | Win Rate | Median MFE | Mode MFE | Median MAE | Mode MAE | R/R (Mode) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **09:30-09:44** | 59.4% | 0.083% | 0.010% | 0.037% | 0.010% | 1.00 |
| **09:45-10:00** | 56.7% | 0.091% | 0.010% | 0.037% | 0.010% | 1.00 |
| **10:00-10:30** | 55.7% | 0.114% | 0.010% | 0.056% | 0.010% | 1.00 |
| **10:30-11:00** | 56.1% | 0.103% | 0.010% | 0.029% | 0.010% | 1.00 |
| **11:00-11:30** | 55.8% | 0.096% | 0.010% | 0.016% | 0.010% | 1.00 |
| **11:30-12:00** | 55.2% | 0.084% | 0.010% | 0.000% | 0.010% | 1.00 |

## Definitions
- **MFE**: Max Favorable Excursion (extension in 9:30 direction).
- **MAE**: Max Adverse Excursion (extension against 9:30 direction).
- **Mode**: The most frequent extension value (calculated using 0.02% bins). Ideally represents the "typical" move.
- **Ratio (Mode)**: Mode MFE / Mode MAE. High ratio = The "typical" win is much larger than the "typical" adverse move.

## Detailed Data
Raw data and daily logs are available in:
- [Summary CSV](tanja_930_summary.csv)
- [Daily Log CSV](tanja_930_breakout_stats.csv)

## Day Trader Simulation: Trend vs Reversal
A backtest of 4,492 sessions comparing two distinct trading behaviors using the 9:30 candle as a signal.

- **Trend Strategy**: Enter on breakout of 9:30 range in the direction of the candle. Stop Loss = 1R.
- **Reversal Strategy (Judas)**: Fade the 9:30 breakout (assume it is false). Stop Loss = 1R.

| Target (R-Multiple) | **Trend Win Rate** | Reversal Win Rate | Advantage |
| :--- | :--- | :--- | :--- |
| **0.5 R** | **34.6%** | 22.3% | +12.3% (Trend) |
| **1.0 R** | **33.9%** | 21.7% | +12.2% (Trend) |
| **2.0 R** | **30.8%** | 19.4% | +11.4% (Trend) |
| **3.0 R** | **26.3%** | 16.1% | +10.2% (Trend) |

### Conclusion
The **Trend Following** approach significantly outperforms the Reversal/Judas approach on the 9:30 breakout setup. The probability of the first move being the "Real Move" is structurally higher than it being a "Fake Move".
