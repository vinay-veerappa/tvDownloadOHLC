# Tanja Model Analysis Summary
**Date**: 2026-01-11
**Best Configuration**: `a2e57`

## Performance Overview
The analysis of `ORBv6-Tanja` exports reveals `a2e57` as the superior configuration, though all variants carry high drawdown risks.

| Metric | a2e57 (Best) | 4c920 | 31bca | 2229b |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy Mode** | **Off (Standard ORB)** | **Trend Confirmation** | **Smart (Pattern Priority)** | **Inverse (Reversal)** |
| **Profit Factor** | **1.72** | 1.71 | 1.60 | 1.45 |
| **Combined Edge** | **27.1** | 21.9 | 14.8 | 11.3 |
| **Win Rate** | **30.8%** | 26.9% | 23.7% | 24.6% |
| **Total P&L** | **$62,516** | $31,756 | $20,744 | $15,822 |
| **Drawdown Score** | High (54.9) | High (66.8) | High (47.1) |

## Key Findings
1.  **Golden Minutes**: The 09:32 minute is consistently the most profitable entry time across most configurations (e.g., +$10k in `a2e57`), aligning with the Tanja "Smart Mode" focus on early pattern recognition.
2.  **Volatility**: The "High DRR" flag indicates significant volatility. While profitable, the strategy experiences deep drawdowns relative to the average risk per trade.
3.  **Trend Confirmation**: The high performance of 09:32 and 09:34 entries supports the "Trend Confirmation" and "Smart Mode" hypothesis where early patterns dictate the successful moves.

## Recommendations
*   **Focus on `a2e57` settings**: Investigate the specific parameters of this export (likely "Smart Mode" enabled given the 09:32 performance).
*   **Risk Management**: The high DRR suggests needing tighter stops or more selective filtering (e.g., Wick Retest or stricter MAE limits).
