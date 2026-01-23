# 📊 Consolidated RTH Gap Analysis Report: YM

**Date:** January 23, 2026
**Ticker:** YM1 (YM)
**Data Range:** 2008-01-03 to 2025-12-23 (4459 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for YM. Key findings show that YM gaps fill approximately 63.3% of the time, with defense probabilities shifting significantly based on ATR and VIX regimes.

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
| Very Small (<0.07%) |    720 | 94.2%       |
| Small (0.07-0.15%)  |    782 | 83.2%       |
| Medium (0.15-0.25%) |    726 | 67.8%       |
| Large (0.25-0.45%)  |    980 | 57.1%       |
| Very Large (>0.45%) |   1223 | 33.9%       |

### B. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     841 | 57.9%       |               26 |
| Tuesday   |     924 | 62.3%       |               18 |
| Wednesday |     918 | 69.7%       |               14 |
| Thursday  |     901 | 66.9%       |               20 |
| Friday    |     875 | 59.1%       |               20 |

## 5. MAE / MFE Precision (Stats Trader View)
- **MAE (Retrace %)**: Mean: 78.9 | Med: 100.0 | Mode: 100.0
- **MFE (Fakeout %)**: Mean: 183.9 | Med: 85.0 | Mode: 0.0 (Extension BEFORE fill)
- **MFE (Extension %)**: Mean: 500.8 | Med: 147.1 | Mode: 0.0 (Total Session Extension)

### Pure Price Percentage Levels (Move / Price %)
- **MAE (Retrace Pct)**: Mean: 0.56 | Med: 0.36 | Mode: 0.01%
- **MFE (Fakeout Pct)**: Mean: 0.40 | Med: 0.20 | Mode: 0.01%
- **MFE (Extension Pct)**: Mean: 0.55 | Med: 0.37 | Mode: 0.06%

## 6. Trend & Bias Correlation Analysis

### Impact of Previous Day Bias
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 67.7%       |    790 |
| ('Bearish', 'UP')   | 64.4%       |    872 |
| ('Bullish', 'DOWN') | 66.5%       |    914 |
| ('Bullish', 'UP')   | 60.6%       |   1030 |
| ('Unknown', 'DOWN') | 63.1%       |    393 |
| ('Unknown', 'UP')   | 53.5%       |    460 |

### ATR Volatility Correlation
| atr_bucket   | Fill Rate   |   Avg Gap % |   Days |
|:-------------|:------------|------------:|-------:|
| Low ATR      | 65.3%       |    0.206512 |   1483 |
| Normal ATR   | 63.2%       |    0.310458 |   1483 |
| High ATR     | 61.5%       |    0.632603 |   1484 |

## 7. RTH Open Types & Boundary Defense
| open_type   |   Days | Fill Rate   | Near Side   | Far Side   |
|:------------|-------:|:------------|:------------|:-----------|
| IBR         |   2198 | 75.9%       | 100.0%      | 43.3%      |
| OBR (Above) |    824 | 46.7%       | 63.3%       | 14.2%      |
| OBR (Below) |    584 | 47.1%       | 68.7%       | 14.2%      |
| Unknown     |    853 | 57.9%       | 0.0%        | 0.0%       |

## 8. Volatility Regime Impact
| vol_regime   | Fill Rate   |   Days |
|:-------------|:------------|-------:|
| High VIX     | 59.9%       |    167 |
| Low VIX      | 71.7%       |    230 |
| Normal VIX   | 67.0%       |    633 |
| Unknown      | 62.2%       |   3429 |

## 9. 8:30 AM News Impact
|           |   Avg Gap % | Fill Rate   |   Days |
|:----------|------------:|:------------|-------:|
| No News   |    0.388011 | 62.9%       |   3918 |
| 8:30 News |    0.349402 | 66.2%       |    541 |

## 10. Deferred Fill Analysis (IPDA Windows)
- **IPDA 20-Day (Short Term)**: 75.1%
- **IPDA 40-Day (Med Term)**: 82.8%
- **IPDA 60-Day (Long Term)**: 85.7%
- **Friday Persistence**: If a Friday gap holds, only 7.8% fill on the subsequent Monday.

## 11. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`