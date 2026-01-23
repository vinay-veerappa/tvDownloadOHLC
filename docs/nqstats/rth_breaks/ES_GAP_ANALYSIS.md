# 📊 Consolidated RTH Gap Analysis Report: ES

**Date:** January 23, 2026
**Ticker:** ES1 (ES)
**Data Range:** 2006-01-06 to 2026-01-22 (4962 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for ES. Key findings show that ES gaps fill approximately 64.5% of the time, with defense probabilities shifting significantly based on ATR and VIX regimes.

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

## 4. Statistical Breakdown

### A. Fill Probabilities by Size
| bucket              |   Days | Fill Rate   |
|:--------------------|-------:|:------------|
| Very Small (<0.07%) |    830 | 94.3%       |
| Small (0.07-0.15%)  |    918 | 82.7%       |
| Medium (0.15-0.25%) |    845 | 67.7%       |
| Large (0.25-0.45%)  |   1070 | 56.0%       |
| Very Large (>0.45%) |   1250 | 35.0%       |

### B. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     932 | 58.4%       |               23 |
| Tuesday   |    1027 | 65.0%       |               29 |
| Wednesday |    1023 | 69.2%       |               25 |
| Thursday  |    1004 | 66.4%       |               23 |
| Friday    |     976 | 62.7%       |               25 |

## 5. MAE / MFE Precision (Stats Trader View)
Treating the gap as a 'Range' to be broken or filled.

### A. The 'Fakeout' Move (MFE before Fill)
How much 'heat' do you take *in the gap direction* before the fill actually happens?
- **Median Fakeout**: 77.8% of Gap Size.
- **Mean Fakeout**: 155.3%.

### B. Retracement Depth (MAE for Trend / Progress for Fill)
How much of the gap actually gets filled on average?
- **Median Retrace**: 100.0% (i.e. Full Fill is the median outcome).
- **Mean Retrace**: 80.1%.

### C. Total Extension (MFE for Trend)
How much does price run *beyond* the open by the end of the session?
- **Median Extension**: Mean: 421.4 | Med: 139.1 | Mode: 100.0

### D. Pure Price Percentage Levels (Move / Index Price %)
- **MAE (Retrace Pct)**: Mean: 0.53 | Med: 0.35 | Mode: 0.01%
- **MFE (Fakeout Pct)**: Mean: 0.36 | Med: 0.16 | Mode: 0.01%
- **MFE (Total Session Ext)**: Mean: 0.50 | Med: 0.33 | Mode: 0.06%

## 6. Trend & Bias Correlation Analysis

### Impact of Previous Day Bias
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 69.6%       |    862 |
| ('Bearish', 'UP')   | 64.2%       |   1022 |
| ('Bullish', 'DOWN') | 67.7%       |   1028 |
| ('Bullish', 'UP')   | 64.2%       |   1180 |
| ('Unknown', 'DOWN') | 58.9%       |    392 |
| ('Unknown', 'UP')   | 54.0%       |    478 |

### ATR Volatility Correlation
| atr_bucket   | Fill Rate   |   Avg Gap % |   Days |
|:-------------|:------------|------------:|-------:|
| Low ATR      | 67.7%       |    0.182083 |   1650 |
| Normal ATR   | 63.6%       |    0.29486  |   1650 |
| High ATR     | 62.1%       |    0.588455 |   1651 |

## 7. RTH Open Types & Boundary Defense
| open_type   |   Days | Fill Rate   | Near Side   | Far Side   |
|:------------|-------:|:------------|:------------|:-----------|
| IBR         |   2532 | 76.1%       | 100.0%      | 41.0%      |
| OBR (Above) |    942 | 50.0%       | 67.5%       | 15.3%      |
| OBR (Below) |    618 | 50.6%       | 70.1%       | 15.2%      |
| Unknown     |    870 | 56.2%       | 0.0%        | 0.0%       |

## 8. Volatility Regime Impact
| vol_regime   | Fill Rate   |   Days |
|:-------------|:------------|-------:|
| High VIX     | 65.3%       |    167 |
| Low VIX      | 64.0%       |    236 |
| Normal VIX   | 66.3%       |    652 |
| Unknown      | 64.2%       |   3907 |

## 9. 8:30 AM News Impact
|           |   Avg Gap % | Fill Rate   |   Days |
|:----------|------------:|:------------|-------:|
| No News   |    0.358892 | 64.1%       |   4352 |
| 8:30 News |    0.325267 | 66.9%       |    610 |

### Specific News Type Breakdown
| Event Type   |   Days | Avg Gap   | Fill Rate   |
|:-------------|-------:|:----------|:------------|
| CPI          |    137 | 0.35%     | 63.5%       |
| NFP          |    230 | 0.32%     | 68.3%       |
| Retail Sales |    137 | 0.35%     | 63.5%       |
| GDP          |     48 | 0.23%     | 79.2%       |

## 10. Deferred Fill Analysis (IPDA Windows)
- **IPDA 20-Day (Short Term)**: 76.1%
- **IPDA 40-Day (Med Term)**: 83.2%
- **IPDA 60-Day (Long Term)**: 86.2%

### Deferred Fill Probabilities by Creation Day
| Creation Day   |   Unfilled | Fill Day 1   | 3-Day Cum   |
|:---------------|-----------:|:-------------|:------------|
| Monday         |        388 | 27.6%        | 54.1%       |
| Tuesday        |        359 | 27.6%        | 47.1%       |
| Wednesday      |        315 | 30.2%        | 42.9%       |
| Thursday       |        337 | 23.7%        | 37.4%       |
| Friday         |        364 | 9.3%         | 45.1%       |

- **Friday Persistence**: If a Friday gap holds, only 9.3% fill on the subsequent Monday.

## 11. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`