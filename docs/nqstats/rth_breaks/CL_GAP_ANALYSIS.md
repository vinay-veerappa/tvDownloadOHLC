# 📊 Consolidated RTH Gap Analysis Report: CL

**Date:** January 23, 2026
**Ticker:** CL1 (CL)
**Data Range:** 2008-07-22 to 2025-12-19 (4365 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for CL. Key findings show that CL gaps fill approximately 55.4% of the time.

---
## 2. Terminology: Reversion vs. Defense

| Term | Strategy | Market Context | Bias Edge |
| :--- | :--- | :--- | :--- |
| **Reversion Favored** | **Trade for the Fill**. Fade the gap move back to yesterday's close. | Low ATR, Low VVIX. | **High Fill Rate**. |
| **Defense Favored** | **Trade for Continuation**. Bet on the gap holding (The 'Moat'). | High ATR, High VVIX. | **High Defense Rate**. |

---
## 3. Daily Bias Inference: Morning Checklist
Use this logic gate every morning at 09:30 ET:

### STEP 1: Check the Environment
*   **Volatility**: Is VVIX > 110 or is ATR High? (If yes -> **Defense Favored**).
*   **News**: Is there an 8:30 AM US News release (NFP/CPI)? (If yes -> **Expect wider volatility before fill**).

### STEP 2: Measure the Gap Size
*   **Gap < 0.15%**: High probability **Reversion** (Treat as noise).
*   **Gap 0.15% - 0.45%**: The **Conflict Zone**. Lean on Volatility/Context filters.
*   **Gap > 0.45%**: High probability **Defense** (Expect Trend Continuation).

### STEP 3: The 15-Minute Execution Filter
*   **The Moat Check**: If Yesterday's Extreme (High/Low) holds for the first 15m, the **Defense** bias is confirmed.

---
## 4. Fill Probabilities by Size
| bucket              |   Days | Fill Rate   |
|:--------------------|-------:|:------------|
| Very Small (<0.07%) |    152 | 88.2%       |
| Small (0.07-0.15%)  |    200 | 86.5%       |
| Medium (0.15-0.25%) |    274 | 77.7%       |
| Large (0.25-0.45%)  |    486 | 74.1%       |
| Very Large (>0.45%) |   3194 | 47.1%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     829 | 52.6%       |               27 |
| Tuesday   |     899 | 55.3%       |               31 |
| Wednesday |     898 | 57.1%       |               53 |
| Thursday  |     882 | 57.5%       |               32 |
| Friday    |     857 | 54.5%       |               20 |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          193 |              8   |            8   |
| 5-15m      |          203 |              8.4 |           16.4 |
| 15-30m     |          168 |              6.9 |           23.3 |
| 30-60m     |          335 |             13.8 |           37.1 |
| 60-120m    |          418 |             17.3 |           54.4 |
| 120m+      |          474 |             19.6 |           74   |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |               0 |            76.1 |          134 |
| Small (0.07-0.15%)  |               0 |            74   |          173 |
| Medium (0.15-0.25%) |               1 |            63.8 |          213 |
| Large (0.25-0.45%)  |              10 |            55.3 |          360 |
| Very Large (>0.45%) |              59 |            27.7 |         1503 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     348 |          8   |
| 25-50%     |     405 |          9.3 |
| 50-75%     |     395 |          9   |
| 75-99%     |     324 |          7.4 |
| 100%       |    2420 |         55.4 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 68.3%          |     3544 |
| 50%             | 77.1%          |     3140 |
| 75%             | 88.2%          |     2744 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 56.8%       |   1945 |
| Prior Filled   | 54.4%       |   2420 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 56.2%       |          1086 |
|              2 | 60.8%       |           525 |
|              3 | 66.2%       |           263 |
|              4 | 70.2%       |           141 |
|              5 | 77.5%       |            71 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 72.5%       |    759 |
| Normal (50-100%) | 58.4%       |   2865 |
| Wide (>100%)     | 25.7%       |    725 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 50.3%       |   1243 |
| Middle Third      | 62.1%       |   1681 |
| Upper Third       | 52.1%       |   1441 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 66.7% of Gap Size.
- **Mean Fakeout**: 174.9%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 72.1%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 385.2 | Med: 114.7 | Mode: 0.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 2.07%  |
| MFE (Fakeout) | 1.70%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 55.3%       |    871 |
| ('Bearish', 'UP')   | 55.9%       |    875 |
| ('Bullish', 'DOWN') | 57.0%       |    830 |
| ('Bullish', 'UP')   | 56.8%       |    942 |
| ('Unknown', 'DOWN') | 50.6%       |    443 |
| ('Unknown', 'UP')   | 53.7%       |    404 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 88.3%       |    205 | +32.9% |
| Trend Continuation | 39.4%       |   1437 | -16.1% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`