# RTH Breaks Verification Report

**Source**: [NQStats - RTH Breaks](https://nqstats.com/rth-breaks) (Credit to NQStats)
**Date Verified**: January 3, 2026
**Tickers Analyzed**: NQ, ES, YM, RTY, GC, CL (10 Years: 2014-2025)

## 1. Concept & Context
The **RTH (Regular Trading Hours)** metric analyzes the relationship between Today's Open (09:30 AM ET) and Yesterday's RTH Range (09:30-16:00 ET).

### Two Scenarios
1.  **Inside Open**: Today opens *inside* yesterday's high-low range.
    *   **The Statistic**: 73% probability of breaking **one side** (Trend Day or Expansion), but only 13% chance of breaking **both** (Outside Day).
2.  **Outside Open (Gap)**: Today opens *outside* yesterday's range (Gap Up or Gap Down).
    *   **The Statistic**: 84% probability of **holding the gap**. (e.g., If Gap Up, do NOT expect price to break Yesterday's Low).

## 2. Verification Analysis (The Data)
We verified these probabilities across 10 years of data.

### Scenario A: Inside Open (The "Expansion" Setup)
**Claim Checked**: High probability of breaking at least one side.

| Ticker | Break One Side | Break Both (Outside Day) | Stay Inside (Chop) | Claim | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NQ1** | **73.0%** | 9.5% | 17.5% | ~73% | ✅ **PERFECT** |
| **RTY1** | **73.5%** | 9.4% | 17.0% | ~73% | ✅ VALID |
| **ES1** | **71.6%** | 9.2% | 19.2% | ~73% | ✅ VALID |
| **YM1** | **70.4%** | 9.7% | 19.8% | ~73% | ✅ VALID |

### Scenario B: Outside Open (The "Gap Defense" Rule)
**Claim Checked**: Probability that the "Gap Side" (the far side of yesterday's range) holds.

| Ticker | Gap Up (Holds Prev Low) | Gap Down (Holds Prev High) | Claim | Status |
| :--- | :--- | :--- | :--- | :--- |
| **NQ1** | **87.6%** | **89.9%** | 84% | ✅ **STRONGER** |
| **ES1** | **88.6%** | **89.4%** | 84% | ✅ **STRONGER** |
| **GC1** | **91.7%** | **92.4%** | - | ✅ ROBUST |
| **CL1** | **90.3%** | **92.3%** | - | ✅ ROBUST |

## 3. Operational Strategy
*   **Inside Open Strategy**:
    *   **Bias**: Expect expansion. Do not play for a "range day".
    *   **Action**: If you are Long, your target should AT LEAST be the Prior High. (73% chance one side breaks).
*   **Outside Open Gap Strategy**:
    *   **Rule**: Do **NOT** target the far side.
    *   **Example**: If Gap Up, do **not** short expecting to break Yesterday's Low. That trade fails ~88% of the time.
    *   **Bias**: Trend following or partial fill only. The Gap Structure is defensive.

## 4. Source Code & Data
*   **Verification Script**: [verify_rth_breaks.py](file:///scripts/nqstats/rth_breaks/verify_rth_breaks.py)
*   **Raw Results (CSV)**: [rth_breaks_verification.csv](file:///scripts/nqstats/results/rth_breaks_verification.csv)
