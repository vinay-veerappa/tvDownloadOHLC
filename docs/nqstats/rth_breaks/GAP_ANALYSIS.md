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

## 4. NQStats RTH Logic (Open Types & Boundary Defense)

Calculating the probability of breaking previous RTH boundaries based on where we open.

### A. Open Type Distribution
| Open Type | Fill Rate | Near Side Break | Far Side Break | Insight |
| :--- | :--- | :--- | :--- | :--- |
| **IBR** (Inside Range) | **76.4%** | 100.0% | 41.6% | High probability of full-range rotation. |
| **OBR Above** (Gap Up) | 54.4% | 70.5% | 17.2% | **Far Side (Low) is defended 82.8% of the time**. |
| **OBR Below** (Gap Down) | 53.1% | 72.1% | 14.7% | **Far Side (High) is defended 85.3% of the time**. |

*   *Key Takeaway*: When opening **Outside** the previous RTH range, the "Far Side" (the extreme opposite of the gap) is an extremely strong level. Breaking it (15-17% prob) usually signals a major trend reversal or "failed gap" scenario.

### B. Boundary Defense by Volatility (Near Side)
How often do we even return to test the "Near Side" (Yesterday's High/Low closest to the open)?

| Regime | Near Side Break (Fill Start) | Insight |
| :--- | :--- | :--- |
| **Low ATR** | **76.3%** | Price almost always tests the previous range. |
| **High ATR** | **72.4%** | Even in high vol, 7 out of 10 days revisit the previous range. |
| **High VVIX** | **72.4%** | Unstable vol leads to frequent range tests. |

---

## 5. Trend & Bias Correlation Analysis

Does the previous day's direction or the current day's gap alignment create a better edge?

### A. Impact of Previous Day Bias
| Prev Day Bias | Gap Direction | Fill Rate | Trend Continuation |
| :--- | :--- | :--- | :--- |
| **Bearish** | **UP** (Fade) | 66.5% | 54.9% |
| **Bearish** | **DOWN** (Cont) | **69.9%** | 44.9% |
| **Bullish** | **UP** (Cont) | 68.1% | 51.6% |
| **Bullish** | **DOWN** (Fade) | **69.9%** | 45.7% |

*   **The Mean Reversion Edge**: Gaps **DOWN** after a **Bullish** day fill **69.9%** of the time (Mean Reversion).
*   **The Trend Continuation Edge**: Gaps **UP** after a **Bullish** day have a **51.6%** continuation rate, but still fill **68.1%** of the time.

### B. Continuation Logic (When Gap Holds)
For gaps > 0.25% that do not fill within the first 60 minutes:
*   **Trend Day Probability**: **76.5%**
*   **Extension Ratio**: **1.5x (Mean)** | **1.2x (Median)**
*   *Insight*: If a medium/large gap is defended for the first hour, the market is likely to run 120-150% of the gap size *beyond* the open by the close.

---

## 6. Mechanics & Precision

### A. Fill Timing (The 15-Minute Rule)
The opening range is the primary fill window.

| Time Bucket | % of Fills | Cumulative | Insight |
| :--- | :--- | :--- | :--- |
| **0 - 15m** | **40.3%** | 40.3% | **The Golden Window**. Fills usually happen early. |
| **15m - 30m** | 13.8% | 54.1% | Odds of fill start dropping fast. |
| **30m - 60m** | 13.3% | 67.4% | - |
| **> 2 Hours** | 20.5% | 100% | The "Long Tail". Likely a slow drift fill. |

---

## 7. Deferred Fill Analysis (Magnetic Gaps)

How "magnetic" are gaps that don't fill on Day 1? We scanned the 60 trading days following every unfilled gap (IPDA Windows).

### A. Cumulative Fill Probabilities 📈
| Timeframe | Cumulative Fill % | IPDA Designation |
| :--- | :--- | :--- |
| **Day 1 (Next Day)** | **23.1%** | Intra-Week Correction |
| **Cumulative 20-Day**| **74.4%** | **IPDA Short-Term Window** |
| **Cumulative 40-Day**| **81.5%** | **IPDA Med-Term Window** |
| **Cumulative 60-Day**| **84.5%** | **IPDA Long-Term Window** |

### B. Deferred Fill Probabilities by Creation Day 📅
| Creation Day | Unfilled Count | Fill Day 1 (Next Day) | 3-Day Cumulative |
| :--- | :--- | :--- | :--- |
| **Monday** | 367 | **29.2%** | **51.8%** |
| **Tuesday** | 329 | 27.4% | 47.1% |
| **Wednesday** | 307 | 26.4% | 39.1% |
| **Thursday** | 311 | 23.5% | 35.4% |
| **Friday** | 333 | **8.7%** | 40.5% |

---

## 8. 8:30 AM News Impact Analysis (NFP, CPI, GDP)

How do major pre-market releases at 08:30 ET influence the open and subsequent gap behavior?

### A. News vs. Non-News Openings
| Market Context | Days | Avg Gap % | Fill Rate | Near Side Break | Ext Ratio (Med) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **No Major News** | 4,352 | 0.32% | 66.7% | 73.2% | 1.56x |
| **8:30 AM News Day** | **610** | 0.30% | **67.7%** | **80.8%** | **1.83x** |

*   **Higher Revisit Probability**: High-impact news days see an **8% increase** (80.8% vs 73.2%) in the probability of price returning to test the previous day's range. 
*   **Greater Extension**: If the news day trends, it trends harder. The median extension beyond the open is **1.83x** the gap size (vs 1.56x on normal days).

### B. Specific News Type Breakdown
| Event Type | Avg Gap Size | Fill Rate | Insight |
| :--- | :--- | :--- | :--- |
| **NFP** (Employment) | 0.30% | **71.3%** | Very high fill probability. |
| **CPI** (Inflation) | **0.33%** | 65.0% | Larger gaps, lower fill probability. |
| **Retail Sales** | 0.33% | 65.0% | Similar profile to CPI. |
| **GDP** | 0.29% | 68.8% | Moderate fill probability. |

*   *Operational Note*: **NFP Gaps** are the most "mean-reverting" of the major releases. Despite the initial volatility, there is a **71%+ probability** of the gap being collected during the RTH session.

---

## 9. Best Practices & Operational Guardrails

To ensure these statistics translate into consistent trading performance, the following guardrails should be followed:

### 🛡️ Execution Best Practices
1.  **The "Size-Signal" Filter**: Treat gaps between **0.15% and 0.45%** as the highest quality. Gaps smaller than 0.1% are often "noise" with poor R:R, while gaps > 0.5% are structural "Runway Gaps" where fading is dangerous.
2.  **The 15-Minute "Moat" Verification**: Validated defense of the "Far Side" (Yesterday's High/Low) for the first 15 minutes of RTH increases the probability of a "Gap & Go" significantly.
3.  **Regime Respect**: Disregard "Mean Reversion" (Fill) biases if **VVIX > 110** or **ATR is "High"**. These regimes favor expansion and defense, not reversion.
4.  **News Day Patience**: On NFP or CPI days, the "Revisit" to the previous range often happens later in the session or with more "heat" (Fakeouts). Increase stop-loss tolerance to **50% of gap size** on news days.

### 🧪 Statistical Standards (For Future Analysis)
1.  **The Rule of 30**: Never draw conclusions from a context filter (e.g., a specific news event) with fewer than 30 historical samples. 
2.  **Timezone Lock**: All RTH calculations must strictly use **US/Eastern** (09:30 - 16:15) to avoid session drift in futures data.
3.  **Distribution over Averages**: Always compare **Mean, Median, and Mode**. If the Mode is 0 (Clean Start) but Median is high, the "Clean" trade is the outlier.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`
