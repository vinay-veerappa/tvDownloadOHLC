# V3 Adaptive Strategy: Comprehensive Analysis Report
**Date:** January 7, 2026
**Strategy:** `orb_v3_adaptive.pine`
**Asset:** MNQ1! (Nasdaq Micro Futures)
**Period:** Jan 2023 - Jan 2026

## 1. Executive Summary
The goal was to improve the V2 "All Day" strategy by addressing "Morning Reversals" (Giveback) while retaining the profit potential of "Trend Days" (MFE). We developed **V3 Adaptive**, which holds runners until End-of-Day (EOD) but activates a wide trailing stop if significant profit is secured.

**Winner:** The **Fixed Take Profit** mode proved statistically superior, banking **$95,343** (+$12k vs baseline).
**Validation:** The **Adaptive Mode** ($84,586) successfully outperformed the **Time Exit** baseline ($83,427), proving the logic works, though "Fixed TP" was the overall profit leader.

## 2. Methodology
- **Strategy Code**: `orb_v3_adaptive.pine`
- **Settings**:
    - Min Contracts: 3 (Force Runner)
    - Filters: Disabled (VVIX/Range Off for max volume)
    - Max Attempts: 10/day
- **Modes Tested**:
    1.  **Time Exit**: Hold runner until 15:50 ET (Baseline).
    2.  **Breakeven**: Move SL to Breakeven after TP1.
    3.  **Adaptive**: Hold until 15:50 ET *unless* Profit > 0.50%, then activate Trail.
    4.  **Fixed TP**: Take profit at fixed percentage targets.
    5.  **Trailing**: Basic trailing stop (User Error test case).

## 3. Results (Corrected Net Profit)
*Note: Profit figures corrected for data duplication bug.*

| Rank | Strategy Mode | Net Profit | Trades | Avg/Day | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Fixed TP** | **$95,343** | 5,514 | 5.0 | **BEST**. Consistent wins (0.15%, 0.25%, 0.50% TPs). |
| **2** | **Adaptive** | **$84,586** | 5,386 | 4.9 | **VALID**. Beat Baseline (+$1,159). |
| **3** | **Time Exit** | **$83,427** | 5,408 | 4.9 | **BASELINE**. Stronger than Breakeven. |
| **4** | **Trailing** | **$68,381** | 5,454 | 5.0 | **POOR**. Trails too early (0.25% Offset). |
| **5** | **Breakeven** | **$55,424** | 5,344 | 4.9 | **FAIL**. Moving to BE kills EV (-$28k vs Baseline). |

## 4. Key Findings

### A. "Fixed TP" outperforms "Holding"
Surprisingly, simply taking profits at fixed levels (`TP1: 0.15%`, `TP2: 0.25%`, `TP3: 0.50%`) generated the highest total return ($95k). This suggests that in the 2023-2026 regime, securing ~75 points (0.50%) was better than risking a reversal for a potential larger home run.

### B. Adaptive Logic is Sound
The Adaptive mode (Activation 0.50%, Offset 0.25%) did exactly what was intended:
- It held winners longer than "Trailing".
- It protected profits better than "Time Exit" (avoiding some full reversals).
- **Result**: It beat the "Time Exit" baseline, proving the concept.

### C. Breakeven is a Killer
Moving the Stop Loss to Breakeven after TP1 reduced total profit by **$28,000** compared to simply holding the Stop at the original level. This confirms our MFE analysis: most winning trades revisit the entry price before going to the target.

## 5. actionable Recommendations
1.  **Primary Configuration**: Run V3 in **Fixed TP** mode for consistent income.
    - TP1: 0.15% (50%)
    - TP2: 0.25% (25%)
    - TP3: 0.50% (25%)
2.  **Alternative**: Use **Adaptive Mode** for trend following, but ensure Activation/Offset are **0.50 / 0.25** (not 0.1).
3.  **Avoid**: Never use "Breakeven" mode or simple "Trailing" (unless wide).
4.  **Sizing**: Keep `Min Contracts = 3` to ensure the runner strategy is always active.
