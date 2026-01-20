# GC1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 4542 trading sessions of GC1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1076 | R2 | 24.3 | 29.7 | 29.6 | 16.4 |
| **Bearish** | 1045 | DWP | 23.8 | 27.0 | 33.8 | 15.4 |
| **Contradicting** | 2189 | DWP | 22.6 | 28.4 | 31.5 | 17.5 |
| **Neutral/Other** | 232 | DWP | 17.2 | 31.9 | 32.3 | 18.5 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| long false \| short false \| Brk:True | **64.3%** | 42.9% | 21.4% | 42 |
| long false \| none \| Brk:False | **59.1%** | 50.0% | 9.1% | 22 |
| none \| long true \| Brk:False | **58.800000000000004%** | 41.2% | 17.6% | 17 |
| short false \| long false \| Brk:True | **57.9%** | 40.4% | 17.5% | 57 |
| none \| short true \| Brk:False | **56.3%** | 37.5% | 18.8% | 16 |
| short true \| none \| Brk:True | **56.2%** | 31.2% | 25.0% | 16 |
| short true \| short false \| Brk:True | **56.0%** | 36.0% | 20.0% | 25 |
| long true \| short false \| Brk:True | **56.0%** | 28.0% | 28.0% | 25 |
| long false \| long false \| Brk:False | **55.900000000000006%** | 41.2% | 14.7% | 102 |
| long true \| long false \| Brk:True | **54.699999999999996%** | 33.3% | 21.4% | 42 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
_No setups met the threshold._

### Clean Trend Runners (>30% DNP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short false \| none | Yes | **30.0%** | 10 |

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| long false \| none | No | **50.0%** | 22 |
| long false \| short false | Yes | **42.9%** | 42 |
| long false \| long false | No | **41.2%** | 102 |
| none \| long true | No | **41.2%** | 17 |
| short false \| long false | Yes | **40.4%** | 57 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short false \| none | No | **50.0%** | 16 |
| short false \| none | Yes | **40.0%** | 10 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 291 | R2 | 22.7 | 31.6 | 29.2 | 16.5 |
| long true \| long true \| Broken:True | 68 | R2 | 26.5 | 33.8 | 17.6 | 22.1 |
| long true \| short false \| Broken:False | 166 | DWP | 24.7 | 29.5 | 30.7 | 15.1 |
| long true \| short false \| Broken:True | 25 | DNP | 28.0 | 16.0 | 28.0 | 28.0 |
| short false \| long true \| Broken:False | 234 | DWP | 28.6 | 26.1 | 29.9 | 15.4 |
| short false \| long true \| Broken:True | 123 | DWP | 21.1 | 27.6 | 36.6 | 14.6 |
| short false \| short false \| Broken:False | 109 | R2 | 23.9 | 34.9 | 24.8 | 16.5 |
| short false \| short false \| Broken:True | 60 | DWP | 18.3 | 31.7 | 35.0 | 15.0 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 102 | DWP | 19.6 | 24.5 | 41.2 | 14.7 |
| long false \| long false \| Broken:True | 47 | R2 | 19.1 | 38.3 | 23.4 | 19.1 |
| long false \| short true \| Broken:False | 231 | DWP | 27.3 | 27.7 | 31.6 | 13.4 |
| long false \| short true \| Broken:True | 114 | DWP | 19.3 | 29.8 | 33.3 | 17.5 |
| short true \| long false \| Broken:False | 118 | DWP | 21.2 | 26.3 | 35.6 | 16.9 |
| short true \| long false \| Broken:True | 47 | DWP | 19.1 | 31.9 | 31.9 | 17.0 |
| short true \| short true \| Broken:False | 293 | DWP | 25.9 | 25.3 | 35.5 | 13.3 |
| short true \| short true \| Broken:True | 93 | DWP | 26.9 | 22.6 | 30.1 | 20.4 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 208 | DWP | 22.6 | 25.5 | 34.1 | 17.8 |
| long false \| long true \| Broken:True | 134 | R2 | 23.1 | 31.3 | 28.4 | 17.2 |
| long false \| short false \| Broken:False | 113 | R2 | 19.5 | 32.7 | 27.4 | 20.4 |
| long false \| short false \| Broken:True | 42 | DWP | 21.4 | 14.3 | 42.9 | 21.4 |
| long true \| long false \| Broken:False | 146 | R2 | 22.6 | 34.2 | 26.7 | 16.4 |
| long true \| long false \| Broken:True | 42 | DWP | 19.0 | 26.2 | 33.3 | 21.4 |
| long true \| short true \| Broken:False | 287 | R1 | 27.5 | 27.5 | 27.2 | 17.8 |
| long true \| short true \| Broken:True | 141 | DWP | 21.3 | 27.0 | 35.5 | 16.3 |
| short false \| long false \| Broken:False | 131 | R2 | 16.8 | 38.9 | 26.0 | 18.3 |
| short false \| long false \| Broken:True | 57 | DWP | 12.3 | 29.8 | 40.4 | 17.5 |
| short false \| short true \| Broken:False | 224 | DWP | 21.4 | 25.9 | 36.6 | 16.1 |
| short false \| short true \| Broken:True | 131 | DWP | 22.1 | 28.2 | 35.9 | 13.7 |
| short true \| long true \| Broken:False | 270 | DWP | 24.1 | 27.0 | 32.2 | 16.7 |
| short true \| long true \| Broken:True | 121 | DWP | 21.5 | 29.8 | 29.8 | 19.0 |
| short true \| short false \| Broken:False | 117 | DWP | 27.4 | 25.6 | 28.2 | 18.8 |
| short true \| short false \| Broken:True | 25 | DWP | 28.0 | 16.0 | 36.0 | 20.0 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 22 | DWP | 18.2 | 22.7 | 50.0 | 9.1 |
| long false \| none \| Broken:True | 8 | DNP | 0.0 | 0.0 | 50.0 | 50.0 |
| long true \| none \| Broken:False | 21 | DWP | 14.3 | 33.3 | 38.1 | 14.3 |
| long true \| none \| Broken:True | 18 | R2 | 16.7 | 38.9 | 22.2 | 22.2 |
| none \| long false \| Broken:False | 6 | DWP | 16.7 | 33.3 | 33.3 | 16.7 |
| none \| long false \| Broken:True | 8 | DWP | 37.5 | 25.0 | 37.5 | 0.0 |
| none \| long true \| Broken:False | 17 | DWP | 17.6 | 23.5 | 41.2 | 17.6 |
| none \| long true \| Broken:True | 21 | DWP | 9.5 | 38.1 | 38.1 | 14.3 |
| none \| none \| Broken:True | 1 | DNP | 0.0 | 0.0 | 0.0 | 100.0 |
| none \| short false \| Broken:False | 7 | DWP | 14.3 | 42.9 | 42.9 | 0.0 |
| none \| short false \| Broken:True | 5 | R1 | 40.0 | 20.0 | 20.0 | 20.0 |
| none \| short true \| Broken:False | 16 | DWP | 18.8 | 25.0 | 37.5 | 18.8 |
| none \| short true \| Broken:True | 13 | R1 | 38.5 | 30.8 | 15.4 | 15.4 |
| short false \| none \| Broken:False | 16 | R2 | 25.0 | 50.0 | 18.8 | 6.2 |
| short false \| none \| Broken:True | 10 | R2 | 10.0 | 40.0 | 20.0 | 30.0 |
| short true \| none \| Broken:False | 27 | R2 | 14.8 | 33.3 | 22.2 | 29.6 |
| short true \| none \| Broken:True | 16 | R2 | 6.2 | 37.5 | 31.2 | 25.0 |

