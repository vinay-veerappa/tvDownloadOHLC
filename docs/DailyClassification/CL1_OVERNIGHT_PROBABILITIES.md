# CL1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 4470 trading sessions of CL1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1080 | DWP | 21.4 | 28.1 | 34.6 | 15.9 |
| **Bearish** | 1087 | DWP | 22.2 | 30.3 | 30.3 | 17.3 |
| **Contradicting** | 2101 | DWP | 21.3 | 29.9 | 33.2 | 15.6 |
| **Neutral/Other** | 202 | DWP | 23.8 | 24.3 | 43.1 | 8.9 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| none \| long true \| Brk:False | **66.6%** | 47.6% | 19.0% | 21 |
| long true \| long true \| Brk:True | **64.5%** | 47.3% | 17.2% | 93 |
| none \| short true \| Brk:True | **57.199999999999996%** | 39.3% | 17.9% | 28 |
| none \| long true \| Brk:True | **56.599999999999994%** | 53.3% | 3.3% | 30 |
| short false \| short false \| Brk:False | **55.5%** | 41.0% | 14.5% | 117 |
| long false \| long true \| Brk:True | **54.3%** | 35.3% | 19.0% | 116 |
| short true \| long true \| Brk:True | **54.199999999999996%** | 37.3% | 16.9% | 142 |
| short true \| long false \| Brk:False | **54.1%** | 31.6% | 22.5% | 187 |
| long true \| long true \| Brk:False | **53.9%** | 34.4% | 19.5% | 262 |
| short true \| short true \| Brk:True | **53.7%** | 33.7% | 20.0% | 95 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| long false | Yes | **40.0%** | 10 |

### Clean Trend Runners (>30% DNP)
_No setups met the threshold._

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| long true | Yes | **53.3%** | 30 |
| none \| long true | No | **47.6%** | 21 |
| none \| short false | Yes | **47.4%** | 19 |
| long true \| long true | Yes | **47.3%** | 93 |
| none \| short true | No | **42.9%** | 21 |
| short false \| short false | No | **41.0%** | 117 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short false \| long false | Yes | **40.0%** | 65 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 262 | DWP | 19.5 | 26.7 | 34.4 | 19.5 |
| long true \| long true \| Broken:True | 93 | DWP | 18.3 | 17.2 | 47.3 | 17.2 |
| long true \| short false \| Broken:False | 205 | DWP | 25.4 | 29.3 | 34.1 | 11.2 |
| long true \| short false \| Broken:True | 93 | DWP | 19.4 | 28.0 | 34.4 | 18.3 |
| short false \| long true \| Broken:False | 138 | DWP | 23.9 | 26.8 | 31.2 | 18.1 |
| short false \| long true \| Broken:True | 96 | R2 | 27.1 | 39.6 | 21.9 | 11.5 |
| short false \| short false \| Broken:False | 117 | DWP | 19.7 | 24.8 | 41.0 | 14.5 |
| short false \| short false \| Broken:True | 76 | R2 | 14.5 | 35.5 | 34.2 | 15.8 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 92 | R2 | 21.7 | 33.7 | 30.4 | 14.1 |
| long false \| long false \| Broken:True | 82 | DWP | 18.3 | 28.0 | 37.8 | 15.9 |
| long false \| short true \| Broken:False | 128 | R2 | 21.1 | 38.3 | 19.5 | 21.1 |
| long false \| short true \| Broken:True | 98 | DWP | 25.5 | 30.6 | 30.6 | 13.3 |
| short true \| long false \| Broken:False | 187 | DWP | 23.5 | 22.5 | 31.6 | 22.5 |
| short true \| long false \| Broken:True | 82 | DWP | 18.3 | 32.9 | 36.6 | 12.2 |
| short true \| short true \| Broken:False | 323 | R2 | 23.8 | 31.3 | 29.1 | 15.8 |
| short true \| short true \| Broken:True | 95 | DWP | 18.9 | 27.4 | 33.7 | 20.0 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 139 | DWP | 25.2 | 27.3 | 34.5 | 12.9 |
| long false \| long true \| Broken:True | 116 | DWP | 17.2 | 28.4 | 35.3 | 19.0 |
| long false \| short false \| Broken:False | 94 | R2 | 26.6 | 33.0 | 30.9 | 9.6 |
| long false \| short false \| Broken:True | 66 | DWP | 21.2 | 30.3 | 33.3 | 15.2 |
| long true \| long false \| Broken:False | 200 | DWP | 20.0 | 30.5 | 32.5 | 17.0 |
| long true \| long false \| Broken:True | 72 | R2 | 22.2 | 37.5 | 25.0 | 15.3 |
| long true \| short true \| Broken:False | 235 | DWP | 24.3 | 30.2 | 31.9 | 13.6 |
| long true \| short true \| Broken:True | 124 | R2 | 15.3 | 33.1 | 31.5 | 20.2 |
| short false \| long false \| Broken:False | 108 | DWP | 18.5 | 27.8 | 39.8 | 13.9 |
| short false \| long false \| Broken:True | 65 | R2 | 12.3 | 40.0 | 36.9 | 10.8 |
| short false \| short true \| Broken:False | 127 | DWP | 21.3 | 28.3 | 35.4 | 15.0 |
| short false \| short true \| Broken:True | 114 | R2 | 14.9 | 35.1 | 28.9 | 21.1 |
| short true \| long true \| Broken:False | 228 | R2 | 22.4 | 31.6 | 30.7 | 15.4 |
| short true \| long true \| Broken:True | 142 | DWP | 20.4 | 25.4 | 37.3 | 16.9 |
| short true \| short false \| Broken:False | 212 | DWP | 25.0 | 24.1 | 35.4 | 15.6 |
| short true \| short false \| Broken:True | 59 | DWP | 27.1 | 27.1 | 30.5 | 15.3 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 7 | R1 | 57.1 | 0.0 | 42.9 | 0.0 |
| long false \| none \| Broken:True | 2 | DWP | 0.0 | 0.0 | 100.0 | 0.0 |
| long true \| none \| Broken:False | 9 | R2 | 33.3 | 44.4 | 11.1 | 11.1 |
| long true \| none \| Broken:True | 7 | DWP | 14.3 | 0.0 | 71.4 | 14.3 |
| none \| long false \| Broken:False | 11 | DWP | 27.3 | 36.4 | 36.4 | 0.0 |
| none \| long false \| Broken:True | 10 | R1 | 40.0 | 30.0 | 30.0 | 0.0 |
| none \| long true \| Broken:False | 21 | DWP | 19.0 | 14.3 | 47.6 | 19.0 |
| none \| long true \| Broken:True | 30 | DWP | 13.3 | 30.0 | 53.3 | 3.3 |
| none \| none \| Broken:False | 3 | DWP | 33.3 | 33.3 | 33.3 | 0.0 |
| none \| short false \| Broken:False | 11 | DWP | 18.2 | 36.4 | 36.4 | 9.1 |
| none \| short false \| Broken:True | 19 | DWP | 31.6 | 15.8 | 47.4 | 5.3 |
| none \| short true \| Broken:False | 21 | DWP | 14.3 | 33.3 | 42.9 | 9.5 |
| none \| short true \| Broken:True | 28 | DWP | 17.9 | 25.0 | 39.3 | 17.9 |
| short false \| none \| Broken:False | 5 | R1 | 80.0 | 0.0 | 20.0 | 0.0 |
| short false \| none \| Broken:True | 4 | DWP | 25.0 | 25.0 | 50.0 | 0.0 |
| short true \| none \| Broken:False | 5 | DWP | 40.0 | 0.0 | 60.0 | 0.0 |
| short true \| none \| Broken:True | 9 | DWP | 11.1 | 33.3 | 33.3 | 22.2 |

