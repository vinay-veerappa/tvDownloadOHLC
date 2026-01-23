# 📊 Consolidated RTH Gap Analysis Report: GC

**Date:** January 23, 2026
**Ticker:** GC1 (GC)
**Data Range:** 2008-01-15 to 2025-12-24 (4474 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for GC. Key findings show that GC gaps fill approximately 51.5% of the time.

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
| Very Small (<0.07%) |    635 | 79.2%       |
| Small (0.07-0.15%)  |    710 | 76.3%       |
| Medium (0.15-0.25%) |    755 | 62.0%       |
| Large (0.25-0.45%)  |   1020 | 47.9%       |
| Very Large (>0.45%) |   1343 | 21.9%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     852 | 48.7%       |             17   |
| Tuesday   |     919 | 53.2%       |             11   |
| Wednesday |     916 | 56.3%       |             16   |
| Thursday  |     900 | 49.8%       |             11.5 |
| Friday    |     887 | 49.4%       |              6   |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          172 |              7.5 |            7.5 |
| 5-15m      |          213 |              9.2 |           16.7 |
| 15-30m     |          206 |              8.9 |           25.6 |
| 30-60m     |          247 |             10.7 |           36.3 |
| 60-120m    |          233 |             10.1 |           46.4 |
| 120m+      |          404 |             17.5 |           63.9 |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |             0   |            75.3 |          503 |
| Small (0.07-0.15%)  |             3   |            62.9 |          542 |
| Medium (0.15-0.25%) |            13   |            50.9 |          468 |
| Large (0.25-0.45%)  |            36   |            34.4 |          489 |
| Very Large (>0.45%) |            89.5 |            19   |          294 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     352 |          7.9 |
| 25-50%     |     402 |          9   |
| 50-75%     |     381 |          8.5 |
| 75-99%     |     314 |          7   |
| 100%       |    2306 |         51.5 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 67.7%          |     3404 |
| 50%             | 76.8%          |     3003 |
| 75%             | 88.0%          |     2620 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 53.1%       |   2169 |
| Prior Filled   | 50.1%       |   2305 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 51.6%       |          1127 |
|              2 | 53.6%       |           541 |
|              3 | 54.3%       |           258 |
|              4 | 57.8%       |           128 |
|              5 | 52.9%       |            51 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 72.7%       |    473 |
| Normal (50-100%) | 57.6%       |   2786 |
| Wide (>100%)     | 29.1%       |   1200 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 50.9%       |   1070 |
| Middle Third      | 54.6%       |   1997 |
| Upper Third       | 47.7%       |   1407 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 57.6% of Gap Size.
- **Mean Fakeout**: 188.1%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 67.4%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 407.6 | Med: 101.3 | Mode: 0.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 0.42%  |
| MFE (Fakeout) | 0.30%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 51.1%       |    959 |
| ('Bearish', 'UP')   | 53.9%       |    891 |
| ('Bullish', 'DOWN') | 53.6%       |    761 |
| ('Bullish', 'UP')   | 51.5%       |    994 |
| ('Unknown', 'DOWN') | 50.0%       |    408 |
| ('Unknown', 'UP')   | 46.0%       |    461 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 78.9%       |    722 | +27.4% |
| Trend Continuation | 22.3%       |    878 | -29.2% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`