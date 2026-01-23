# 📊 Consolidated RTH Gap Analysis Report: RTY

**Date:** January 23, 2026
**Ticker:** RTY1 (RTY)
**Data Range:** 2017-07-11 to 2025-12-23 (2100 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for RTY. Key findings show that RTY gaps fill approximately 65.4% of the time, with defense probabilities shifting significantly based on ATR and VIX regimes.

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
| Very Small (<0.07%) |    209 | 94.7%       |
| Small (0.07-0.15%)  |    277 | 88.8%       |
| Medium (0.15-0.25%) |    274 | 82.5%       |
| Large (0.25-0.45%)  |    461 | 65.7%       |
| Very Large (>0.45%) |    864 | 44.6%       |

### B. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     394 | 64.2%       |             10   |
| Tuesday   |     435 | 63.2%       |             10   |
| Wednesday |     430 | 67.4%       |             11   |
| Thursday  |     424 | 65.6%       |             10.5 |
| Friday    |     417 | 66.4%       |             14   |

## 5. MAE / MFE Precision (Stats Trader View)
- **MAE (Retrace %)**: Mean: 80.7 | Med: 100.0 | Mode: 100.0
- **MFE (Fakeout %)**: Mean: 194.1 | Med: 87.6 | Mode: 0.0 (Extension BEFORE fill)
- **MFE (Extension %)**: Mean: 587.6 | Med: 154.8 | Mode: 0.0 (Total Session Extension)

### Pure Price Percentage Levels (Move / Price %)
- **MAE (Retrace Pct)**: Mean: 0.85 | Med: 0.63 | Mode: 0.01%
- **MFE (Fakeout Pct)**: Mean: 0.58 | Med: 0.29 | Mode: 0.01%
- **MFE (Extension Pct)**: Mean: 0.81 | Med: 0.61 | Mode: 0.01%

## 6. Trend & Bias Correlation Analysis

### Impact of Previous Day Bias
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 68.5%       |    372 |
| ('Bearish', 'UP')   | 66.8%       |    458 |
| ('Bullish', 'DOWN') | 64.0%       |    417 |
| ('Bullish', 'UP')   | 63.7%       |    444 |
| ('Unknown', 'DOWN') | 63.2%       |    163 |
| ('Unknown', 'UP')   | 64.6%       |    246 |

### ATR Volatility Correlation
| atr_bucket   | Fill Rate   |   Avg Gap % |   Days |
|:-------------|:------------|------------:|-------:|
| Low ATR      | 68.4%       |    0.298572 |    697 |
| Normal ATR   | 64.8%       |    0.485489 |    697 |
| High ATR     | 62.8%       |    0.834711 |    697 |

## 7. RTH Open Types & Boundary Defense
| open_type   |   Days | Fill Rate   | Near Side   | Far Side   |
|:------------|-------:|:------------|:------------|:-----------|
| IBR         |   1082 | 74.5%       | 99.9%       | 41.5%      |
| OBR (Above) |    348 | 50.6%       | 70.1%       | 14.4%      |
| OBR (Below) |    261 | 49.4%       | 70.9%       | 12.3%      |
| Unknown     |    409 | 64.1%       | 0.0%        | 0.0%       |

## 8. Volatility Regime Impact
| vol_regime   | Fill Rate   |   Days |
|:-------------|:------------|-------:|
| High VIX     | 64.7%       |    167 |
| Low VIX      | 61.3%       |    230 |
| Normal VIX   | 66.0%       |    632 |
| Unknown      | 66.0%       |   1071 |

## 9. 8:30 AM News Impact
|           |   Avg Gap % | Fill Rate   |   Days |
|:----------|------------:|:------------|-------:|
| No News   |    0.542459 | 65.0%       |   1841 |
| 8:30 News |    0.506814 | 68.3%       |    259 |

## 10. Deferred Fill Analysis (IPDA Windows)
- **IPDA 20-Day (Short Term)**: 77.9%
- **IPDA 40-Day (Med Term)**: 85.6%
- **IPDA 60-Day (Long Term)**: 88.2%
- **Friday Persistence**: If a Friday gap holds, only 5.0% fill on the subsequent Monday.

## 11. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`