# RTH Gap Analysis Report

**Date:** January 23, 2026
**Ticker:** NQ1 (E-mini Nasdaq 100)
**Data Range:** ~2006 - Present (4,962 Sessions with Gaps)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps**—situations where the 09:30 ET Open price differs from the previous day's 16:15 ET Close.

Key findings:
*   **Defense**: A gap acts as a "moat". The previous day's extreme (High/Low) is defended **67%** of the time.
*   **Fills**: While **67%** of all gaps fill, this is heavily skewed by small gaps.
*   **Trend**: Large gaps (>0.5%) have a coin-flip probability (~51%) of trending in the gap direction ("Gap & Go").

## 2. Statistical Breakdown

### A. Fill Probabilities by Size
Small gaps are noise; large gaps are signal.

| Gap Bucket | Range (Approx %) | Fill Rate | Interpretation |
| :--- | :--- | :--- | :--- |
| **Very Small** | < 0.07% | **94.2%** | Almost always fills (Noise). |
| **Small** | 0.07% - 0.14% | **80.1%** | Highly likely to fill. |
| **Medium** | 0.14% - 0.25% | **68.8%** | Bias towards filling. |
| **Large** | 0.25% - 0.47% | **53.0%** | **The Tipping Point**. Coin flip. |
| **Very Large** | > 0.47% | **38.0%** | **Unlikely to fill**. Expect continuation or chop. |

### B. Mechanics
*   **Median Time to Fill**: **15 minutes**.
    *   *Insight*: If a gap is going to fill, it usually happens immediately (in the Opening Range). If it persists beyond the first hour, the odds of filling drop significantly.
*   **Unfilled Retracement**: **40.0%**.
    *   *Insight*: When a gap does *not* fill, prices typically retrace about 40% of the gap distance before resuming the trend.

### C. RTH Break "Defense" (The Moat)
Does the gap hold the "Far Side"?
*   *Gap Up*: Does Yesterday's **Low** hold?
*   *Gap Down*: Does Yesterday's **High** hold?

**Result**: **67.3% Defense Rate**.
This validates the "Outside Open" logic: When the market gaps significantly, the previous day's range acts as strong support/resistance.

## 3. Operational Rules (Draft)
Based on this data, we can derive the following operational bias:

1.  **The 0.5% Rule**: If the Gap is > **0.50%** (approx 125 pts on NQ @ 25k), **DO NOT TRADE FOR THE FILL**. Assume the gap will hold.
2.  **The 15-Minute Rule**: If the gap hasn't filled in the first 15-30 minutes, shift bias to "Gap Defense" / Trend Continuation.
3.  **Defensive Stop**: For Gap Ups, placing stops below Yesterday's Low is a high-probability (>67%) play.

## 4. Source Data
*   **Gaps Database**: `data/derived/rth_gaps.json`
*   **Analysis Script**: `scripts/analysis/analyze_gap_history.py`
