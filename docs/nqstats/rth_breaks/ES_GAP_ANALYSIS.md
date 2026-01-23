# 📊 Consolidated RTH Gap Analysis Report: ES

**Date:** January 23, 2026
**Ticker:** ES1 (ES)
**Data Range:** 2006-01-06 to 2026-01-22 (4962 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for ES. Key findings show that ES gaps fill approximately 64.5% of the time.

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
| Very Small (<0.07%) |    830 | 94.3%       |
| Small (0.07-0.15%)  |    918 | 82.7%       |
| Medium (0.15-0.25%) |    845 | 67.7%       |
| Large (0.25-0.45%)  |   1070 | 56.0%       |
| Very Large (>0.45%) |   1250 | 35.0%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     932 | 58.4%       |               23 |
| Tuesday   |    1027 | 65.0%       |               29 |
| Wednesday |    1023 | 69.2%       |               25 |
| Thursday  |    1004 | 66.4%       |               23 |
| Friday    |     976 | 62.7%       |               25 |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          447 |             14   |           14   |
| 5-15m      |          459 |             14.3 |           28.3 |
| 15-30m     |          342 |             10.7 |           39   |
| 30-60m     |          402 |             12.6 |           51.6 |
| 60-120m    |          379 |             11.8 |           63.4 |
| 120m+      |          697 |             21.8 |           85.2 |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |               1 |            84.9 |          783 |
| Small (0.07-0.15%)  |              16 |            47.6 |          759 |
| Medium (0.15-0.25%) |              39 |            29   |          572 |
| Large (0.25-0.45%)  |              74 |            13.7 |          599 |
| Very Large (>0.45%) |             126 |             3.9 |          437 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     572 |         11.5 |
| 25-50%     |     467 |          9.4 |
| 50-75%     |     344 |          6.9 |
| 75-99%     |     359 |          7.2 |
| 100%       |    3199 |         64.5 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 73.0%          |     4384 |
| 50%             | 81.4%          |     3928 |
| 75%             | 89.7%          |     3566 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 68.1%       |   1764 |
| Prior Filled   | 62.4%       |   3198 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 66.6%       |          1144 |
|              2 | 79.7%       |           592 |
|              3 | 87.9%       |           340 |
|              4 | 94.7%       |           187 |
|              5 | 94.8%       |           115 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 76.3%       |   1733 |
| Normal (50-100%) | 61.2%       |   2709 |
| Wide (>100%)     | 41.2%       |    503 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 59.2%       |   1424 |
| Middle Third      | 78.8%       |   1593 |
| Upper Third       | 56.6%       |   1945 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 77.8% of Gap Size.
- **Mean Fakeout**: 155.3%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 80.1%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 421.4 | Med: 139.1 | Mode: 100.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 0.53%  |
| MFE (Fakeout) | 0.36%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 69.6%       |    862 |
| ('Bearish', 'UP')   | 64.2%       |   1022 |
| ('Bullish', 'DOWN') | 67.7%       |   1028 |
| ('Bullish', 'UP')   | 64.2%       |   1180 |
| ('Unknown', 'DOWN') | 58.9%       |    392 |
| ('Unknown', 'UP')   | 54.0%       |    478 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 91.1%       |    946 | +26.7% |
| Trend Continuation | 31.6%       |    651 | -32.8% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`