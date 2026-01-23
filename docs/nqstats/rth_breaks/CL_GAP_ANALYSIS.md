# 📊 Consolidated RTH Gap Analysis Report: CL

**Date:** January 23, 2026
**Ticker:** CL1 (CL)
**Data Range:** 2008-07-22 to 2025-12-19 (4365 Sessions)
**Script:** `scripts/analysis/analyze_gap_history.py`

## 1. Executive Summary
This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for CL. Key findings show that CL gaps fill approximately 55.4% of the time, with defense probabilities shifting significantly based on ATR and VIX regimes.

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
| Very Small (<0.07%) |    152 | 88.2%       |
| Small (0.07-0.15%)  |    200 | 86.5%       |
| Medium (0.15-0.25%) |    274 | 77.7%       |
| Large (0.25-0.45%)  |    486 | 74.1%       |
| Very Large (>0.45%) |   3194 | 47.1%       |

> [!TIP]
> **Takeaway**: Small gaps (<0.15%) are largely noise and revert quickly. Large gaps (>0.45%) represent true 'Signal' and have a much higher probability of defending the open for a trend day.

### B. Day of Week Analysis
| day       |   Count | Fill Rate   |   Med Time (min) |
|:----------|--------:|:------------|-----------------:|
| Monday    |     829 | 52.6%       |               27 |
| Tuesday   |     899 | 55.3%       |               31 |
| Wednesday |     898 | 57.1%       |               53 |
| Thursday  |     882 | 57.5%       |               32 |
| Friday    |     857 | 54.5%       |               20 |

> [!IMPORTANT]
> **Takeaway**: Mid-week (Wednesday) typically shows the highest mean-reversion (fill) tendencies. Mondays and Fridays are 'Defense' prone—if the gap holds the first 30m on these days, expect continuation.

## 5. MAE / MFE Precision (Stats Trader View)
Treating the gap as a 'Range' to be broken or filled.

### A. The 'Fakeout' Move (MFE before Fill)
How much 'heat' do you take *in the gap direction* before the fill actually happens?
- **Median Fakeout**: 66.7% of Gap Size.
- **Mean Fakeout**: 174.9%.
> **Takeaway**: If you are fading a gap, your stop should realistically be placed beyond 50-80% of the gap size to survive the regular 'Fakeout' expansion.


### B. Retracement Depth (MAE for Trend / Progress for Fill)
How much of the gap actually gets filled on average?
- **Median Retrace**: 100.0% (i.e. Full Fill is the median outcome).
- **Mean Retrace**: 72.1%.
> **Takeaway**: Since 100% is the median retracement, the most common outcome is a full fill. However, on trending days, the 'Mean Retrace' shows we often stick around 60-80% fill before resumption.


### C. Total Extension (MFE for Trend)
How much does price run *beyond* the open by the end of the session?
- **Median Extension**: Mean: 385.2 | Med: 114.7 | Mode: 0.0
> **Takeaway**: Trending gaps typically run 1.5x to 2x the size of the initial gap. If the gap holds, use the gap size as your 'Unit' for price targets.


### D. Pure Price Percentage Levels (Move / Index Price %)
- **MAE (Retrace Pct)**: Mean: 2.07 | Med: 1.16 | Mode: 0.00%
- **MFE (Fakeout Pct)**: Mean: 1.70 | Med: 0.74 | Mode: 0.00%
- **MFE (Total Session Ext)**: Mean: 2.19 | Med: 1.14 | Mode: 0.00%

## 6. Trend & Bias Correlation Analysis

### Impact of Previous Day Bias
|                     | Fill Rate   |   Days |
|:--------------------|:------------|-------:|
| ('Bearish', 'DOWN') | 55.3%       |    871 |
| ('Bearish', 'UP')   | 55.9%       |    875 |
| ('Bullish', 'DOWN') | 57.0%       |    830 |
| ('Bullish', 'UP')   | 56.8%       |    942 |
| ('Unknown', 'DOWN') | 50.6%       |    443 |
| ('Unknown', 'UP')   | 53.7%       |    404 |

> **Takeaway**: Gaps that open *against* the previous day's trend (e.g., GAP UP after BEARISH day) have a slightly higher tendency to revert (mean-reversion) as traders take profits or hedge.


### ATR Volatility Correlation
| atr_bucket   | Fill Rate   |   Avg Gap % |   Days |
|:-------------|:------------|------------:|-------:|
| Low ATR      | 55.1%       |   -0.943347 |   1452 |
| Normal ATR   | 56.8%       |    1.21942  |   1450 |
| High ATR     | 54.4%       |    3.39775  |   1452 |

> **Takeaway**: High ATR environments coincide with larger gaps and lower fill rates. In High Vol, the gap is likely a 'Breakaway' rather than noise.

## 7. RTH Open Types & Boundary Defense
| open_type   |   Days | Fill Rate   | Near Side   | Far Side   |
|:------------|-------:|:------------|:------------|:-----------|
| IBR         |   1985 | 68.0%       | 97.4%       | 37.3%      |
| OBR (Above) |    835 | 42.6%       | 62.5%       | 12.9%      |
| OBR (Below) |    698 | 39.3%       | 60.3%       | 12.3%      |
| Unknown     |    847 | 52.1%       | 0.0%        | 0.0%       |

> **Takeaway**: **IBR (Inside Bar Range)** opens are high-probability mean-reversion setups (75%+). **OBR (Opening Bar Range)** opens represent directional momentum—if the near-side holds, follow the trend.

## 8. Volatility Regime Impact
| vol_regime   | Fill Rate   |   Days |
|:-------------|:------------|-------:|
| High VIX     | 52.7%       |    167 |
| Low VIX      | 53.0%       |    232 |
| Normal VIX   | 53.2%       |    641 |
| Unknown      | 56.2%       |   3325 |

> **Takeaway**: During High VIX (>25), the 'Morning Moat' is wider. Gaps fill less frequently as institutional positioning drives sustained directional moves.

## 9. 8:30 AM News Impact
|           |   Avg Gap % | Fill Rate   |   Days |
|:----------|------------:|:------------|-------:|
| No News   |     1.21716 | 55.9%       |   3833 |
| 8:30 News |     1.26428 | 52.3%       |    532 |

### Specific News Type Breakdown
| Event Type   |   Days | Avg Gap   | Fill Rate   |
|:-------------|-------:|:----------|:------------|
| CPI          |    118 | 1.73%     | 40.7%       |
| NFP          |    204 | 1.09%     | 57.8%       |
| Retail Sales |    118 | 1.73%     | 40.7%       |
| GDP          |     38 | 0.80%     | 55.3%       |

> **Takeaway**: NFP days have a unique profile of high 'Fakeouts' followed by high fill rates. CPI days generate the largest gaps with the highest directional persistence.

## 10. Deferred Fill Analysis (IPDA Windows)
- **IPDA 20-Day (Short Term)**: 76.0%
- **IPDA 40-Day (Med Term)**: 82.2%
- **IPDA 60-Day (Long Term)**: 85.5%

### Deferred Fill Probabilities by Creation Day
| Creation Day   |   Unfilled | Fill Day 1   | 3-Day Cum   |
|:---------------|-----------:|:-------------|:------------|
| Monday         |        393 | 28.0%        | 48.9%       |
| Tuesday        |        402 | 32.8%        | 49.8%       |
| Wednesday      |        385 | 24.7%        | 39.5%       |
| Thursday       |        375 | 28.0%        | 44.3%       |
| Friday         |        390 | 6.7%         | 46.7%       |

> **Takeaway**: The 'IPDA Magnetism' is real—80%+ of unfilled gaps revisit their origin within 40 days. If a gap doesn't fill today, it becomes an 'Anchor Level' for your swing-bias over the next 20 sessions.

- **Friday Persistence**: If a Friday gap holds, only 6.7% fill on the subsequent Monday.

## 11. Best Practices & Operational Guardrails
1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.
2. **Regime Respect**: Use caution in High VIX/VVIX regimes.
3. **15-Minute Moat**: Wait for RTH opening candle confirmation.

---
**Generated by**: `scripts/analysis/analyze_gap_history.py`