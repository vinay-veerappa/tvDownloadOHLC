# 📊 Consolidated RTH Gap Analysis Report: RTY

**Date:** January 23, 2026
**Ticker:** RTY1 (RTY)
**Data Range:** 2017-07-11 to 2025-12-23 (2100 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py` 

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for RTY. Key findings show that RTY gaps fill approximately 65.4% of the time.

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
| Very Small (<0.07%) |    209 | 94.7%       |
| Small (0.07-0.15%)  |    277 | 88.8%       |
| Medium (0.15-0.25%) |    274 | 82.5%       |
| Large (0.25-0.45%)  |    461 | 65.7%       |
| Very Large (>0.45%) |    864 | 44.6%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open.

## 5. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     394 | 64.2%       |             10   |
| Tuesday   |     435 | 63.2%       |             10   |
| Wednesday |     430 | 67.4%       |             11   |
| Thursday  |     424 | 65.6%       |             10.5 |
| Friday    |     417 | 66.4%       |             14   |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows highest reversion. Mondays/Fridays are 'Defense' prone.

## 6. Time-to-Fill Distribution (Module 1)
| t_bucket   |   Fill Count |   % of All Fills |   Cumulative % |
|:-----------|-------------:|-----------------:|---------------:|
| 0-5m       |          273 |             19.9 |           19.9 |
| 5-15m      |          173 |             12.6 |           32.5 |
| 15-30m     |          150 |             10.9 |           43.4 |
| 30-60m     |          130 |              9.5 |           52.9 |
| 60-120m    |          143 |             10.4 |           63.3 |
| 120m+      |          213 |             15.5 |           78.8 |


### Intensity by Gap Size
| bucket              |   Med Fill Time |   % Filled <15m |   Fill Count |
|:--------------------|----------------:|----------------:|-------------:|
| Very Small (<0.07%) |               0 |            94.9 |          198 |
| Small (0.07-0.15%)  |               2 |            76.8 |          246 |
| Medium (0.15-0.25%) |               6 |            66.8 |          226 |
| Large (0.25-0.45%)  |              22 |            41.9 |          303 |
| Very Large (>0.45%) |              73 |            13.2 |          385 |

> **Takeaway**: If a fill isn't achieved in the first 30 minutes, probability of same-day fill drops. High-conviction reversions happen fast (<15m).

## 7. Partial Fill Behavior (Module 2)
| r_bucket   |   Count |   % of Total |
|:-----------|--------:|-------------:|
| 0-25%      |     226 |         10.8 |
| 25-50%     |     185 |          8.8 |
| 50-75%     |     157 |          7.5 |
| 75-99%     |     145 |          6.9 |
| 100%       |    1373 |         65.4 |


### Conditional Probability of Full Fill
| If Reached X%   | P(Full Fill)   |   Sample |
|:----------------|:---------------|---------:|
| 25%             | 73.8%          |     1860 |
| 50%             | 82.0%          |     1675 |
| 75%             | 90.4%          |     1518 |

> **Takeaway**: If price 'hangs' at the 50% retracement level for more than 15m, failure probability increases.

## 8. Consecutive Day / Streak Analysis (Module 3)
|                | Fill Rate   |   Days |
|:---------------|:------------|-------:|
| Prior Defended | 65.0%       |    728 |
| Prior Filled   | 65.6%       |   1372 |


### Streak Persistence
|   streak_count | Fill Rate   |   Sample Size |
|---------------:|:------------|--------------:|
|              1 | 66.2%       |           474 |
|              2 | 77.5%       |           262 |
|              3 | 84.0%       |           162 |
|              4 | 92.5%       |            93 |
|              5 | 98.0%       |            50 |

> **Takeaway**: Volatility and outcomes cluster. After two consecutive fills, expect a defense day soon.

## 9. Globex Range Context (Module 4)
| globex_bucket    | Fill Rate   |   Days |
|:-----------------|:------------|-------:|
| Narrow (<50%)    | 75.7%       |    855 |
| Normal (50-100%) | 61.3%       |   1029 |
| Wide (>100%)     | 42.1%       |    202 |


### RTH Open Position
| globex_position   | Fill Rate   |   Days |
|:------------------|:------------|-------:|
| Lower Third       | 61.3%       |    602 |
| Middle Third      | 76.1%       |    645 |
| Upper Third       | 60.1%       |    853 |

> **Takeaway**: Wide Globex ranges signal breakaway. Position within range helps predict early defense.

## 10. MAE / MFE Precision (Stats Trader View)
### A. The 'Fakeout' Move (MFE before Fill)
- **Median Fakeout**: 87.6% of Gap Size.
- **Mean Fakeout**: 194.1%.
> **Takeaway**: Set stops beyond 50-80% of gap size.

### B. Retracement Depth (MAE for Trend)
- **Median Retrace**: 100.0%
- **Mean Retrace**: 80.7%.
### C. Total Extension (MFE for Trend)
- **Median Extension**: Mean: 587.6 | Med: 154.8 | Mode: 0.0
> **Takeaway**: Trending gaps run 1.5x to 2x the unit of the gap.


### D. Pure Price Percentage Levels
| Metric        | Mean   |
|:--------------|:-------|
| MAE (Retrace) | 0.85%  |
| MFE (Fakeout) | 0.58%  |

## 11. Trend & Bias Correlation
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 68.5%       |    372 |
| ('Bearish', 'UP')   | 66.8%       |    458 |
| ('Bullish', 'DOWN') | 64.0%       |    417 |
| ('Bullish', 'UP')   | 63.7%       |    444 |
| ('Unknown', 'DOWN') | 63.2%       |    163 |
| ('Unknown', 'UP')   | 64.6%       |    246 |

> **Takeaway**: Gaps against trend revert more often.

## 12. 🏆 Highest Edge Setups (Compound Detector)
| Setup              | Fill Rate   |   Days | Lift   |
|:-------------------|:------------|-------:|:-------|
| Perfect Reversion  | 90.6%       |    297 | +25.2% |
| Trend Continuation | 38.5%       |    408 | -26.9% |

## 13. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`