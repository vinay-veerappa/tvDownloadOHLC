# 📊 Consolidated RTH Gap Analysis Report

**Date:** January 23, 2026
**Ticker:** NQ1 (E-mini Nasdaq 100)
**Data Range:** ~2006 - Present (4,962 Sessions with Gaps)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps**—situations where the 09:30 ET Open price differs from the previous day's 16:15 ET Close.

Key findings:
*   **Defense**: A gap acts as a "moat". The previous day's extreme (High/Low) is defended **67.3%** of the time.
*   **Fills**: While **66.8%** of all gaps fill, success is highly dependent on size, day of the week, and volatility regime.
*   **Trend**: Large gaps (>0.5%) have a coin-flip probability (~51%) of trending in the gap direction ("Gap & Go").

---

## 2. Terminology: Reversion vs. Defense

Understanding how to use these probabilities for a Daily Bias:

| Term | Strategy | Market Context | Bias Edge |
| :--- | :--- | :--- | :--- |
| **Reversion Favored** | **Trade for the Fill**. Fade the gap move back to yesterday's close. | Low ATR, Low VVIX, Wednesday. | **70%+ Fill Rate**. |
| **Defense Favored** | **Trade for Continuation**. Bet on the gap holding (The "Moat"). | High ATR, High VVIX, Monday. | **68%+ Defense Rate**. |

---

## 3. Daily Bias Inference: Morning Checklist
Do we have enough info? **Yes.** Use this logic gate every morning at 09:30 ET:

### STEP 1: Check the Baseline (The Environment)
*   **Day of Week**: Is it Monday (Defense Edge) or Wednesday (Reversion Edge)?
*   **Volatility**: Is Daily ATR % High? Is VVIX > 110? (If yes -> **Defense Favored**).

### STEP 2: Measure the Gap Size
*   **Gap < 0.15%**: High probability **Reversion** (Treat as noise).
*   **Gap 0.15% - 0.45%**: The **Conflict Zone**. Lean on Volatility/DOW filters.
*   **Gap > 0.45%**: High probability **Defense** (Expect Trend Continuation).

### STEP 3: The 15-Minute Execution Filter
*   **The Fakeout Check**: If price extends > 0.03% (Index Pct) but stays < 0.15% (Index Pct) and then reverses, the **Reversion** play is active.
*   **The Moat Check**: If Yesterday's Extreme holds for the first 15m, the **Defense** bias is confirmed. Target a 1x extension of the gap size.

---

## 4. Statistical Breakdown

### A. Fill Probabilities by Size
Small gaps are noise; large gaps are signal.

| Gap Bucket | Range (Approx %) | Fill Rate | Interpretation |
| :--- | :--- | :--- | :--- |
| **Very Small** | < 0.07% | **94.2%** | Almost always fills (Noise). |
| **Small** | 0.07% - 0.14% | **80.1%** | Highly likely to fill. |
| **Medium** | 0.14% - 0.25% | **68.8%** | Bias towards filling. |
| **Large** | 0.25% - 0.47% | **53.0%** | **The Tipping Point**. Coin flip. |
| **Very Large** | > 0.47% | **38.0%** | **Unlikely to fill**. Expect continuation or chop. |

### B. Day of Week Segmentation
| Day | Fill Rate | Fill Timing (Med) | Fill Timing (Mean) |
| :--- | :--- | :--- | :--- |
| **Monday** | 60.6% | 20m | 75m |
| **Tuesday** | 68.0% | 15m | 62m |
| **Wednesday** | **70.0%** | 12m | 58m |
| **Thursday** | 69.0% | 15m | 65m |
| **Friday** | 66.0% | 18m | 70m |

---

## 3. MAE / MFE Precision (Stats Trader View)

Treating the gap as a "Range" to be broken or filled.

### A. The "Fakeout" Move (MFE before Fill)
How much "heat" do you take *in the gap direction* before the fill actually happens?
*   **Median Fakeout**: **6.8% of Gap Size**.
*   **Mode Fakeout**: **0%**.
*   **Mean Fakeout**: **27.5%**.
*   *Insight*: If you are fading a gap, your stop should likely be > 30% of the gap size. A 0% Mode suggests most fills happen with ZERO adverse extension beyond the open.

### B. Retracement Depth (MAE for Trend / Progress for Fill)
How much of the gap actually gets filled on average?
*   **Median Retrace**: **100%** (i.e. Full Fill is the median outcome).
*   **Mean Retrace**: **68.1%**.
*   *Insight*: While 67% fill eventually, the "average" day recoups 2/3rds of the gap.

### C. Total Extension (MFE for Trend)
How much does prize run *beyond* the open by the end of the session?
*   **Median Extension**: **85.0% of Gap Size**.
*   **Mean Extension**: **111.9% of Gap Size**.

### D. Pure Price Percentage Levels (Move / Index Price %)
Measuring the move relative to the absolute index level (e.g. NQ @ 25,000).

| Metric | Mean | Median | Mode |
| :--- | :--- | :--- | :--- |
| **MAE (Retrace / Pullback)** | **1.33%** | **0.33%** | 0.01% |
| **MFE (Fakeout before Fill)**| **0.15%** | **0.03%** | 0.01% |
| **MFE (Total Session Ext)** | **0.40%** | **0.25%** | 0.01% |

*   *Stats Trader Note*: A 0.03% Median Fakeout on NQ @ 25,000 is only **7.5 points**. If you are fading a gap and price extends > 10-15 pts beyond the open, the "clean" fill probability is dropping.

---

## 4. The "Moat" & Continuation (Defense)

### A. RTH Break Defense
Does the gap hold the "Far Side" (Yesterday's Low for Gap Up, High for Gap Down)?
**Result**: **67.3% Defense Rate**.

### B. Continuation Logic (When Gap Holds)
For gaps > 0.25% that do not fill within the first 60 minutes:
*   **Trend Day Probability**: **76.5%**
*   **Extension Ratio**: **1.16x** (Price runs another 1.16x the gap size past the open).

---

## 4. Mechanics & Precision

### A. Fill Timing (The 15-Minute Rule)
The opening range is the primary fill window.

| Time Bucket | % of Fills | Cumulative | Insight |
| :--- | :--- | :--- | :--- |
| **0 - 15m** | **40.3%** | 40.3% | **The Golden Window**. Fills usually happen early. |
| **15m - 30m** | 13.8% | 54.1% | Odds of fill start dropping fast. |
| **30m - 60m** | 13.3% | 67.4% | - |
| **> 2 Hours** | 20.5% | 100% | The "Long Tail". Likely a slow drift fill. |

### B. Partial Fill Precision (If Unfilled)
| Retracement % | Probability | Insight |
| :--- | :--- | :--- |
| **0-25%** | **33.1%** | Strongest trending days. No look-back. |
| **25-50%** | 25.5% | Common test of gap mid-point. |
| **50-75%** | 21.4% | Deep retrace, but doesn't fill. |
| **75-99%** | 20.0% | The "Close Call" (Front-run). |

*   **Median Retracement**: 40.0% | **Mean Retracement**: 43.9%

---

## 5. Volatility Regimes

### A. VVIX Regimes
High VVIX indicates unstable volatility, favoring gap defense.

| VVIX Regime | Fill Rate | Gap Defense | Insight |
| :--- | :--- | :--- | :--- |
| **Low (<90)** | **69.2%** | 66.2% | Reversion favored. |
| **High (>110)** | **63.6%** | **68.9%** | **Defense favored**. |

### B. Daily ATR %
| ATR Bucket | Fill Rate | Gap Defense | Avg Gap Size |
| :--- | :--- | :--- | :--- |
| **Low ATR** | **70.6%** | 66.3% | 14.9 pts |
| **High ATR** | **63.1%** | **68.4%** | **56.3 pts** |

---

## 6. Operational Trading Rules
1.  **The 0.5% Rule**: If Gap > 0.50%, **DO NOT TRADE FOR THE FILL**.
2.  **The 15-Minute Rule**: If the gap hasn't filled by 09:45, shift bias to trend continuation.
3.  **Defensive Stop**: Stops should be placed at the "Moat" (Yesterday's Low/High). Probability of hold is ~67%.
4.  **Targeting**: If the gap holds, target **1x the Gap Size** extension from the Open.

---

## 7. Deferred Fill Analysis (Magnetic Gaps)

How "magnetic" are gaps that don't fill on Day 1? We scanned the 20 trading days following every unfilled gap.

### A. Cumulative Fill Probabilities (IPDA Lookbacks) 📈
For gaps that **do not fill** during their initial RTH session, we tracked institutional "collection" over the 60-day IPDA cycle.

| Timeframe | Cumulative Fill % | IPDA Designation |
| :--- | :--- | :--- |
| **Day 1 (Next Day)** | **23.1%** | Intra-Week Correction |
| **Cumulative 20-Day**| **74.4%** | **IPDA Short-Term Window** |
| **Cumulative 40-Day**| **81.5%** | **IPDA Med-Term Window** |
| **Cumulative 60-Day**| **84.5%** | **IPDA Long-Term Window** |

*   *IPDA Interpretation*: Gaps have massive gravity within the first 20 days. If a gap survives past 60 trading days (approx 3 months), it is statistically likely to remain an "unfilled" structural level for the long term.

### B. Deferred Fill Probabilities by Creation Day 📅
Does the day the gap was born affect its magnetism?

| Creation Day | Unfilled Count | Fill Day 1 (Next Day) | 3-Day Cumulative |
| :--- | :--- | :--- | :--- |
| **Monday** | 367 | **29.2%** | **51.8%** |
| **Tuesday** | 329 | 27.4% | 47.1% |
| **Wednesday** | 307 | 26.4% | 39.1% |
| **Thursday** | 311 | 23.5% | 35.4% |
| **Friday** | 333 | **8.7%** | 40.5% |

**Key Insights:**
*   **The Monday Revisit**: If a Monday gap doesn't fill on Monday, there is a very high (**29.2%**) chance it fills on Tuesday. The market often "over-extends" on Mondays and corrects early Tuesday.
*   **The Friday Persistence**: If a Friday gap doesn't fill on Friday, it is **unlikely** to fill on Monday (only 8.7%). Friday trends tend to have more "staying power" heading into the new week.

### C. Days to Fill (The "Pull" Speed)
For the gaps that eventually fill:
*   **Median Time to Fill**: **3 Days**.
*   **Mode Time to Fill**: **1 Day**.
*   **Mean Time to Fill**: **5 Days**.

*   *Strategic Trade*: "Unfilled Gaps" become high-attraction magnets. If price is trading near a 2-day-old unfilled gap, the 43% probability of a fill within the 3rd day offers a significant secondary bias.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`
