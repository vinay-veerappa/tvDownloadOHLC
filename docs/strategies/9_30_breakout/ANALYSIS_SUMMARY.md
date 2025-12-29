# 9:30 Breakout Strategy: Research & Analysis Summary

## 📊 Executive Summary
This document summarizes the extensive research conducted on the **9:30 AM Opening Range Breakout (ORB)** strategy for **NQ Futures**.
The study covers **10 Years of Data (2016-2025)** and documents the evolution from a simple breakout model to the current production-grade **V6 Strategy**.

### Key Findings
1.  **Alpha Source**: The edge is primarily in **Trend Extension** ("Runners"). Removing arbitrary time exits (e.g., 9:44 AM) **doubles** total profitability.
2.  **Regime Matters**: Win rates drop from **~45% in Bull Regimes** to **~18% in Bear Regimes**. Filtering for Trend (SMA20) is critical.
3.  **Volatility Sweet Spot**: Extremely high volatility (VVIX > 115) leads to chop/stop-outs. Avoiding these days improves Sharpe Ratio.

---

## 📈 Strategy Evolution & Performance

### V1: Baseline (The Impulse Scalper)
*   **Logic**: Breakout of 1-minute range. Hard Exit at 9:44 AM.
*   **Performance**: **+4,418 pts** (10 Years).
*   **Verdict**: Profitable but caps upside. High Win Rate (~37%), Low Avg Trade (+4.5 pts).

### V2: Optimized (The Trend Follower)
*   **Logic**: Removed 9:44 Exit (Hold until 10:00 AM or 4:00 PM). Added Tuesday Avoidance.
*   **Performance**: **+9,478 pts** (10 Years).
*   **Verdict**: **2.1x Profitability** vs V1. Lower Win Rate (~23%) but massive winners (+9.5 avg trade). Proved that "Runners" are the key.

### V6: Production (The Smart Filtered Model)
*   **Logic**: Combines V2's runners with strict **Pre-Trade Filters** to improve Win Rate.
*   **Enhancements**:
    *   **Regime Filter**: Only trade Long if Daily Close > SMA20.
    *   **VVIX Filter**: Skip if Volatility is extreme (>115).
    *   **Execution**: "Pullback + Fallback" logic to reduce slippage on entries.
    *   **Risk**: Capped Limits (0.30% Max SL) to survive "Black Swan" expands.

---

## 🔬 Research Reports
Detailed analysis documents are available in the `research/` directory:

| Report | Findings |
|--------|----------|
| **[Time Exit Analysis](research/time_exit_analysis.md)** | Comparing 9:44 AM vs 10:00 AM vs 4:00 PM exits. |
| **[Win Rate Optimization](research/winrate_optimization.md)** | Analysis of optimal Take Profit targets (1R vs Runners). |
| **[MFE/MAE Analysis](research/analyze_mfe_mae.py)** | Study of Maximum Favorable/Adverse Excursion to set Stop/Target levels. |
| **[Loss Analysis](research/LOSS_ANALYSIS.md)** | Breakdown of why trades fail (Bear Regime is #1 cause). |
| **[Timing Analysis](research/timing_analysis.md)** | Why entries after 9:35 AM have lower expectancy. |

---

## 🛠️ Testing Infrastructure

All Python scripts used to validate these findings are cataloged in the **[Script Inventory](research/PYTHON_SCRIPT_INVENTORY.md)**.

### Key Scripts
*   **`run_930_v6_strategy.py`**: The current engine testing the V6 Logic (Regime/VVIX/Pullback).
*   **`compare_930_variants.py`**: Comparative tool for V1 vs V2 logic.
*   **`analyze_mfe_mae.py`**: Tool for calculating probability of hitting price targets.

---

## 🔗 Reference Links
*   **[Master Specification](../ORB_STRATEGY_MASTER_SPEC.md)** (The Code Logic)
*   **[Archive](../archive/README.md)** (Old Specs V1-V5)
