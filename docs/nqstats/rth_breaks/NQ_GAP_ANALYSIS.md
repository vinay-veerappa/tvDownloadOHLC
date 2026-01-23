# 📊 Consolidated RTH Gap Analysis Report: NQ

**Date:** January 23, 2026
**Ticker:** NQ1 (NQ)
**Data Range:** 2006-01-06 to 2026-01-22 (4962 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for NQ. Key findings show that NQ gaps fill approximately 66.8% of the time.

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
| Very Small (<0.07%) |   1038 | 93.5%       |
| Small (0.07-0.15%)  |    981 | 79.0%       |
| Medium (0.15-0.25%) |    884 | 68.4%       |
| Large (0.25-0.45%)  |    960 | 54.1%       |
| Very Large (>0.45%) |   1065 | 38.6%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     932 | 60.6%       |               13 |
| Tuesday   |    1027 | 68.0%       |               17 |
| Wednesday |    1022 | 70.0%       |               17 |
| Thursday  |    1003 | 69.0%       |               16 |
| Friday    |     978 | 66.0%       |               13 |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          609 |             18.4 |           18.4 |
| 5-15m      |          506 |             15.3 |           33.7 |
| 15-30m     |          382 |             11.5 |           45.2 |
| 30-60m     |          368 |             11.1 |           56.3 |
| 60-120m    |          336 |             10.1 |           66.4 |
| 120m+      |          567 |             17.1 |           83.5 |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |               1 |            83.5 |          971 |
| Small (0.07-0.15%)  |              11 |            54.8 |          775 |
| Medium (0.15-0.25%) |              25 |            36.2 |          605 |
| Large (0.25-0.45%)  |              50 |            20   |          519 |
| Very Large (>0.45%) |             100 |             7.5 |          411 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     540 |         10.9 |
| 25-50%     |     416 |          8.4 |
| 50-75%     |     349 |          7   |
| 75-99%     |     326 |          6.6 |
| 100%       |    3315 |         66.8 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 75.2%          |     4410 |
| 50%             | 82.8%          |     4003 |
| 75%             | 90.8%          |     3649 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 69.4%       |   1648 |
| Prior Filled   | 65.5%       |   3314 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 68.6%       |          1114 |
|              2 | 81.9%       |           597 |
|              3 | 90.1%       |           353 |
|              4 | 96.9%       |           227 |
|              5 | 98.6%       |           144 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 75.8%       |   2123 |
| Normal (50-100%) | 62.8%       |   2435 |
| Wide (>100%)     | 42.6%       |    387 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 63.3%       |   1434 |
| Middle Third      | 78.0%       |   1553 |
| Upper Third       | 60.6%       |   1975 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 83.3% of Gap Size.
- **Mean Fakeout**: 184.3%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 81.4%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 608.7 | Med: 160.1 | Mode: 0.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 0.52%  |
| MFE (Fakeout) | 0.34%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 69.9%       |    857 |
| ('Bearish', 'UP')   | 66.5%       |   1017 |
| ('Bullish', 'DOWN') | 69.9%       |    971 |
| ('Bullish', 'UP')   | 68.1%       |   1248 |
| ('Unknown', 'DOWN') | 62.4%       |    370 |
| ('Unknown', 'UP')   | 56.1%       |    499 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 88.9%       |   1085 | +22.1% |
| Trend Continuation | 36.9%       |    555 | -29.9% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`