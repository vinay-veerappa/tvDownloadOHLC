# Noon Curve Verification Report

**Source**: [NQStats - Noon Curve](https://nqstats.com/noon-curve) (Credit to NQStats)
**Date Verified**: January 3, 2026
**Tickers Analyzed**: NQ, ES, YM, RTY, GC, CL (10 Years: 2014-2025)

## 1. Concept & Context
The **Noon Curve** metric leverages time-based probabilities, specifically around the **12:00 PM ET** mark (The "Noon Line").
*   **The Theory**: The market rarely forms both the Session High and Session Low on the same side of Noon.
*   **The Claim**: ~75% of the time, the High and Low will be on **Opposite Sides** of the Noon Line.
*   **Implication**: If both the High and Low are established *before* 12:00 PM, probability suggests that one of them will break before the session closes.

## 2. Verification Analysis (The Data)
We verified this 75% claim across 6 asset classes.

### Outcome: Perfect for Equities, Fails for Commodities
**ES (S&P 500)** is the "Golden Child" for this metric, hitting the 75% claim almost exactly.

| Ticker | Metric | Result | vs Claim | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ES1** | Opposite Sides | **74.9%** | Matches 75% | ✅ **PERFECT** |
| **NQ1** | Opposite Sides | **72.4%** | Close (>70%) | ✅ **VALID** |
| **YM1** | Opposite Sides | **72.3%** | Close (>70%) | ✅ **VALID** |
| **RTY1** | Opposite Sides | **69.8%** | Weaker | ⚠️ OK |
| **CL1** | Opposite Sides | **66.3%** | Weak | ❌ AVOID |
| **GC1** | Opposite Sides | **51.8%** | **FAIL** | ⛔ **FAIL** |

### Detailed Breakdown (ES1)
*   **Opposite Sides**: 74.9% (The Edge).
*   **Same Side (AM)**: 18.1% (High and Low both set before Noon).
*   **Same Side (PM)**: 7.0% (Rarely set entirely after Noon).

## 3. Commodity Optimization (The Fix)
Standard Noon Curve fails for Gold/Oil because their "Midline" is not 12:00 PM ET. We optimized the pivot times:
*   **Gold (GC)**: Shift Pivot to **09:00 AM ET**. -> Restores **74.5%** Edge.
*   **Oil (CL)**: Shift Pivot to **10:00 AM ET**. -> Restores **75.2%** Edge.
*   *See [COMMODITY_PIVOTS.md](COMMODITY_PIVOTS.md) for full analysis.*

## 4. Operational Strategy
*   **Best Asset**: **ES** (S&P 500).
*   **The Setup**:
    1.  At 12:00 PM ET, mark the Session High and Low.
    2.  Check if they are both "locked" (AM High / AM Low).
    3.  **Action**: If locked, expect a break of one side in the PM Session.
    4.  **Commodities**: Apply the same logic but at 09:00 (Gold) or 10:00 (Oil).

## 5. Source Code & Data
*   **Verification Script**: [verify_noon_curve.py](file:///scripts/nqstats/noon_curve/verify_noon_curve.py)
*   **Commodity Pivot Finder**: [find_optimal_pivot.py](file:///scripts/nqstats/noon_curve/find_optimal_pivot.py)
*   **Raw Results (CSV)**: [noon_curve_verification.csv](file:///scripts/nqstats/results/noon_curve_verification.csv)
