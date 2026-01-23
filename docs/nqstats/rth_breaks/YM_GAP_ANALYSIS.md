# 📊 Consolidated RTH Gap Analysis Report: YM

**Date:** January 23, 2026
**Ticker:** YM1 (YM)
**Data Range:** 2008-01-03 to 2025-12-23 (4459 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for YM. Key findings show that YM gaps fill approximately 63.3% of the time.

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
| Very Small (<0.07%) |    720 | 94.2%       |
| Small (0.07-0.15%)  |    782 | 83.2%       |
| Medium (0.15-0.25%) |    726 | 67.8%       |
| Large (0.25-0.45%)  |    980 | 57.1%       |
| Very Large (>0.45%) |   1223 | 33.9%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     841 | 57.9%       |               26 |
| Tuesday   |     924 | 62.3%       |               18 |
| Wednesday |     918 | 69.7%       |               14 |
| Thursday  |     901 | 66.9%       |               20 |
| Friday    |     875 | 59.1%       |               20 |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          468 |             16.6 |           16.6 |
| 5-15m      |          360 |             12.8 |           29.4 |
| 15-30m     |          255 |              9   |           38.4 |
| 30-60m     |          299 |             10.6 |           49   |
| 60-120m    |          328 |             11.6 |           60.6 |
| 120m+      |          614 |             21.7 |           82.3 |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |             0   |            86.1 |          678 |
| Small (0.07-0.15%)  |             9   |            57.8 |          651 |
| Medium (0.15-0.25%) |            23   |            39   |          492 |
| Large (0.25-0.45%)  |            71   |            16.4 |          560 |
| Very Large (>0.45%) |           118.5 |             5.3 |          414 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     552 |         12.4 |
| 25-50%     |     422 |          9.5 |
| 50-75%     |     332 |          7.4 |
| 75-99%     |     304 |          6.8 |
| 100%       |    2823 |         63.3 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 72.6%          |     3890 |
| 50%             | 81.3%          |     3472 |
| 75%             | 90.1%          |     3133 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 66.5%       |   1637 |
| Prior Filled   | 61.4%       |   2822 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 65.0%       |          1053 |
|              2 | 76.4%       |           538 |
|              3 | 85.9%       |           290 |
|              4 | 94.9%       |           158 |
|              5 | 96.7%       |            90 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 77.4%       |   1537 |
| Normal (50-100%) | 59.2%       |   2441 |
| Wide (>100%)     | 38.9%       |    468 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 58.2%       |   1382 |
| Middle Third      | 78.7%       |   1331 |
| Upper Third       | 55.7%       |   1746 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 85.0% of Gap Size.
- **Mean Fakeout**: 183.9%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 78.9%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 500.8 | Med: 147.1 | Mode: 0.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 0.56%  |
| MFE (Fakeout) | 0.40%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 67.7%       |    790 |
| ('Bearish', 'UP')   | 64.4%       |    872 |
| ('Bullish', 'DOWN') | 66.5%       |    914 |
| ('Bullish', 'UP')   | 60.6%       |   1030 |
| ('Unknown', 'DOWN') | 63.1%       |    393 |
| ('Unknown', 'UP')   | 53.5%       |    460 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 91.1%       |    854 | +27.8% |
| Trend Continuation | 30.2%       |    656 | -33.1% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`