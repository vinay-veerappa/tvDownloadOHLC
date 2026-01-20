# ES1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 5003 trading sessions of ES1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1234 | R2 | 24.6 | 34.4 | 26.1 | 14.8 |
| **Bearish** | 1079 | R2 | 24.7 | 36.3 | 24.6 | 14.4 |
| **Contradicting** | 2430 | R2 | 24.2 | 34.4 | 26.0 | 15.5 |
| **Neutral/Other** | 260 | R2 | 24.2 | 31.5 | 28.1 | 16.2 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| long false \| short false \| Brk:True | **57.7%** | 36.5% | 21.2% | 52 |
| long true \| none \| Brk:False | **52.4%** | 42.9% | 9.5% | 21 |
| none \| long true \| Brk:False | **52.3%** | 33.3% | 19.0% | 21 |
| none \| short true \| Brk:True | **47.0%** | 29.4% | 17.6% | 34 |
| long true \| short true \| Brk:False | **46.0%** | 28.3% | 17.7% | 368 |
| long true \| long true \| Brk:False | **45.1%** | 29.0% | 16.1% | 397 |
| short true \| short false \| Brk:False | **44.1%** | 28.8% | 15.3% | 177 |
| long true \| short false \| Brk:True | **43.9%** | 28.8% | 15.1% | 73 |
| none \| short true \| Brk:False | **43.8%** | 25.0% | 18.8% | 16 |
| long false \| short true \| Brk:False | **43.8%** | 28.1% | 15.7% | 121 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
_No setups met the threshold._

### Clean Trend Runners (>30% DNP)
_No setups met the threshold._

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| long true \| none | No | **42.9%** | 21 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short true \| none | Yes | **54.5%** | 11 |
| none \| short false | No | **47.1%** | 17 |
| short true \| none | No | **42.9%** | 14 |
| short false \| short false | No | **42.2%** | 90 |
| long false \| long true | No | **41.8%** | 158 |
| long false \| none | No | **41.7%** | 12 |
| long false \| long false | No | **41.6%** | 77 |
| long false \| none | Yes | **40.0%** | 10 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 397 | R2 | 22.9 | 32.0 | 29.0 | 16.1 |
| long true \| long true \| Broken:True | 142 | R2 | 24.6 | 34.5 | 24.6 | 16.2 |
| long true \| short false \| Broken:False | 189 | R2 | 27.0 | 34.9 | 24.3 | 13.8 |
| long true \| short false \| Broken:True | 73 | R2 | 24.7 | 31.5 | 28.8 | 15.1 |
| short false \| long true \| Broken:False | 160 | R2 | 23.1 | 36.2 | 25.0 | 15.6 |
| short false \| long true \| Broken:True | 124 | R2 | 27.4 | 33.1 | 25.8 | 13.7 |
| short false \| short false \| Broken:False | 90 | R2 | 25.6 | 42.2 | 20.0 | 12.2 |
| short false \| short false \| Broken:True | 59 | R2 | 25.4 | 39.0 | 25.4 | 10.2 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 77 | R2 | 26.0 | 41.6 | 19.5 | 13.0 |
| long false \| long false \| Broken:True | 58 | R2 | 31.0 | 36.2 | 27.6 | 5.2 |
| long false \| short true \| Broken:False | 121 | R2 | 22.3 | 33.9 | 28.1 | 15.7 |
| long false \| short true \| Broken:True | 114 | R2 | 21.9 | 38.6 | 23.7 | 15.8 |
| short true \| long false \| Broken:False | 156 | R2 | 26.9 | 39.1 | 23.1 | 10.9 |
| short true \| long false \| Broken:True | 84 | R2 | 23.8 | 35.7 | 21.4 | 19.0 |
| short true \| short true \| Broken:False | 315 | R2 | 24.1 | 35.6 | 24.8 | 15.6 |
| short true \| short true \| Broken:True | 154 | R2 | 25.3 | 33.1 | 26.6 | 14.9 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 158 | R2 | 23.4 | 41.8 | 21.5 | 13.3 |
| long false \| long true \| Broken:True | 147 | R2 | 21.8 | 34.7 | 27.2 | 16.3 |
| long false \| short false \| Broken:False | 85 | R2 | 29.4 | 34.1 | 18.8 | 17.6 |
| long false \| short false \| Broken:True | 52 | DWP | 19.2 | 23.1 | 36.5 | 21.2 |
| long true \| long false \| Broken:False | 212 | R2 | 21.7 | 35.4 | 27.4 | 15.6 |
| long true \| long false \| Broken:True | 53 | R1 | 30.2 | 30.2 | 20.8 | 18.9 |
| long true \| short true \| Broken:False | 368 | R2 | 23.9 | 30.2 | 28.3 | 17.7 |
| long true \| short true \| Broken:True | 167 | R2 | 25.7 | 34.7 | 29.3 | 10.2 |
| short false \| long false \| Broken:False | 106 | R2 | 25.5 | 35.8 | 20.8 | 17.9 |
| short false \| long false \| Broken:True | 44 | R2 | 20.5 | 36.4 | 29.5 | 13.6 |
| short false \| short true \| Broken:False | 155 | R2 | 22.6 | 34.8 | 27.1 | 15.5 |
| short false \| short true \| Broken:True | 136 | R2 | 23.5 | 39.0 | 25.0 | 12.5 |
| short true \| long true \| Broken:False | 273 | R2 | 25.6 | 35.9 | 23.1 | 15.4 |
| short true \| long true \| Broken:True | 222 | R2 | 24.3 | 34.7 | 26.1 | 14.9 |
| short true \| short false \| Broken:False | 177 | R2 | 23.7 | 32.2 | 28.8 | 15.3 |
| short true \| short false \| Broken:True | 75 | R2 | 29.3 | 32.0 | 22.7 | 16.0 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 12 | R2 | 25.0 | 41.7 | 16.7 | 16.7 |
| long false \| none \| Broken:True | 10 | R2 | 30.0 | 40.0 | 20.0 | 10.0 |
| long true \| none \| Broken:False | 21 | DWP | 14.3 | 33.3 | 42.9 | 9.5 |
| long true \| none \| Broken:True | 4 | DNP | 25.0 | 25.0 | 25.0 | 25.0 |
| none \| long false \| Broken:False | 8 | DNP | 12.5 | 0.0 | 37.5 | 50.0 |
| none \| long false \| Broken:True | 19 | R2 | 21.1 | 36.8 | 26.3 | 15.8 |
| none \| long true \| Broken:False | 21 | DWP | 23.8 | 23.8 | 33.3 | 19.0 |
| none \| long true \| Broken:True | 46 | R1 | 32.6 | 23.9 | 21.7 | 21.7 |
| none \| none \| Broken:False | 2 | DWP | 50.0 | 0.0 | 50.0 | 0.0 |
| none \| none \| Broken:True | 1 | R2 | 0.0 | 100.0 | 0.0 | 0.0 |
| none \| short false \| Broken:False | 17 | R2 | 23.5 | 47.1 | 23.5 | 5.9 |
| none \| short false \| Broken:True | 9 | DWP | 33.3 | 22.2 | 44.4 | 0.0 |
| none \| short true \| Broken:False | 16 | R1 | 31.2 | 25.0 | 25.0 | 18.8 |
| none \| short true \| Broken:True | 34 | DWP | 23.5 | 29.4 | 29.4 | 17.6 |
| short false \| none \| Broken:False | 8 | R1 | 37.5 | 37.5 | 12.5 | 12.5 |
| short false \| none \| Broken:True | 7 | DWP | 14.3 | 28.6 | 42.9 | 14.3 |
| short true \| none \| Broken:False | 14 | R2 | 14.3 | 42.9 | 28.6 | 14.3 |
| short true \| none \| Broken:True | 11 | R2 | 9.1 | 54.5 | 27.3 | 9.1 |

