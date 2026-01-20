# NQ1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 5001 trading sessions of NQ1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1257 | DWP | 19.9 | 31.6 | 31.8 | 16.7 |
| **Bearish** | 1051 | R2 | 20.7 | 35.0 | 30.4 | 13.8 |
| **Contradicting** | 2414 | R2 | 19.6 | 34.6 | 29.7 | 16.1 |
| **Neutral/Other** | 279 | DWP | 17.6 | 29.4 | 32.3 | 20.8 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| none \| long false \| Brk:True | **72.2%** | 50.0% | 22.2% | 18 |
| short true \| none \| Brk:True | **64.3%** | 14.3% | 50.0% | 14 |
| none \| short true \| Brk:False | **64.0%** | 36.0% | 28.0% | 25 |
| none \| short true \| Brk:True | **62.2%** | 51.4% | 10.8% | 37 |
| none \| long true \| Brk:False | **60.0%** | 43.3% | 16.7% | 30 |
| none \| long true \| Brk:True | **57.1%** | 20.0% | 37.1% | 35 |
| none \| short false \| Brk:True | **56.3%** | 37.5% | 18.8% | 16 |
| none \| short false \| Brk:False | **54.6%** | 45.5% | 9.1% | 11 |
| long true \| none \| Brk:False | **54.6%** | 27.3% | 27.3% | 22 |
| long true \| long true \| Brk:False | **53.5%** | 34.7% | 18.8% | 398 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
_No setups met the threshold._

### Clean Trend Runners (>30% DNP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short true \| none | Yes | **50.0%** | 14 |
| none \| long true | Yes | **37.1%** | 35 |

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| short true | Yes | **51.4%** | 37 |
| none \| long false | Yes | **50.0%** | 18 |
| none \| short false | No | **45.5%** | 11 |
| none \| long true | No | **43.3%** | 30 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short false \| short false | No | **62.4%** | 85 |
| short false \| none | No | **60.0%** | 10 |
| short true \| long false | Yes | **45.6%** | 79 |
| none \| long false | No | **43.8%** | 16 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 398 | DWP | 21.1 | 25.4 | 34.7 | 18.8 |
| long true \| long true \| Broken:True | 129 | DWP | 17.8 | 29.5 | 34.9 | 17.8 |
| long true \| short false \| Broken:False | 231 | R2 | 22.9 | 33.3 | 29.9 | 13.9 |
| long true \| short false \| Broken:True | 71 | DWP | 18.3 | 31.0 | 35.2 | 15.5 |
| short false \| long true \| Broken:False | 148 | DWP | 18.9 | 32.4 | 36.5 | 12.2 |
| short false \| long true \| Broken:True | 129 | R2 | 17.8 | 31.0 | 30.2 | 20.9 |
| short false \| short false \| Broken:False | 85 | R2 | 10.6 | 62.4 | 18.8 | 8.2 |
| short false \| short false \| Broken:True | 66 | R2 | 25.8 | 27.3 | 21.2 | 25.8 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 92 | R1 | 30.4 | 30.4 | 20.7 | 18.5 |
| long false \| long false \| Broken:True | 61 | DWP | 19.7 | 27.9 | 36.1 | 16.4 |
| long false \| short true \| Broken:False | 145 | R2 | 13.8 | 38.6 | 33.8 | 13.8 |
| long false \| short true \| Broken:True | 113 | R2 | 16.8 | 37.2 | 30.1 | 15.9 |
| short true \| long false \| Broken:False | 140 | R2 | 30.0 | 31.4 | 30.0 | 8.6 |
| short true \| long false \| Broken:True | 79 | R2 | 15.2 | 45.6 | 26.6 | 12.7 |
| short true \| short true \| Broken:False | 305 | R2 | 19.7 | 34.8 | 32.1 | 13.4 |
| short true \| short true \| Broken:True | 116 | R2 | 21.6 | 33.6 | 30.2 | 14.7 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 174 | R2 | 19.5 | 35.6 | 27.6 | 17.2 |
| long false \| long true \| Broken:True | 147 | R2 | 19.7 | 38.8 | 22.4 | 19.0 |
| long false \| short false \| Broken:False | 102 | R2 | 15.7 | 38.2 | 27.5 | 18.6 |
| long false \| short false \| Broken:True | 55 | DWP | 25.5 | 30.9 | 32.7 | 10.9 |
| long true \| long false \| Broken:False | 217 | R2 | 20.7 | 33.6 | 30.9 | 14.7 |
| long true \| long false \| Broken:True | 50 | DWP | 20.0 | 34.0 | 34.0 | 12.0 |
| long true \| short true \| Broken:False | 339 | DWP | 18.0 | 30.7 | 31.6 | 19.8 |
| long true \| short true \| Broken:True | 157 | R2 | 19.1 | 36.9 | 27.4 | 16.6 |
| short false \| long false \| Broken:False | 100 | R2 | 18.0 | 38.0 | 27.0 | 17.0 |
| short false \| long false \| Broken:True | 56 | R2 | 25.0 | 39.3 | 26.8 | 8.9 |
| short false \| short true \| Broken:False | 168 | R2 | 14.9 | 37.5 | 32.1 | 15.5 |
| short false \| short true \| Broken:True | 133 | DWP | 19.5 | 31.6 | 33.1 | 15.8 |
| short true \| long true \| Broken:False | 273 | R2 | 22.7 | 35.2 | 28.9 | 13.2 |
| short true \| long true \| Broken:True | 197 | R2 | 17.8 | 34.5 | 28.9 | 18.8 |
| short true \| short false \| Broken:False | 176 | DWP | 22.2 | 33.0 | 33.0 | 11.9 |
| short true \| short false \| Broken:True | 70 | DWP | 22.9 | 30.0 | 30.0 | 17.1 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 6 | R1 | 33.3 | 33.3 | 16.7 | 16.7 |
| long false \| none \| Broken:True | 7 | R2 | 14.3 | 57.1 | 14.3 | 14.3 |
| long true \| none \| Broken:False | 22 | R2 | 13.6 | 31.8 | 27.3 | 27.3 |
| long true \| none \| Broken:True | 16 | R2 | 25.0 | 37.5 | 18.8 | 18.8 |
| none \| long false \| Broken:False | 16 | R2 | 18.8 | 43.8 | 25.0 | 12.5 |
| none \| long false \| Broken:True | 18 | DWP | 5.6 | 22.2 | 50.0 | 22.2 |
| none \| long true \| Broken:False | 30 | DWP | 23.3 | 16.7 | 43.3 | 16.7 |
| none \| long true \| Broken:True | 35 | DNP | 28.6 | 14.3 | 20.0 | 37.1 |
| none \| none \| Broken:False | 1 | R1 | 100.0 | 0.0 | 0.0 | 0.0 |
| none \| none \| Broken:True | 1 | DWP | 0.0 | 0.0 | 100.0 | 0.0 |
| none \| short false \| Broken:False | 11 | DWP | 18.2 | 27.3 | 45.5 | 9.1 |
| none \| short false \| Broken:True | 16 | DWP | 12.5 | 31.2 | 37.5 | 18.8 |
| none \| short true \| Broken:False | 25 | DWP | 16.0 | 20.0 | 36.0 | 28.0 |
| none \| short true \| Broken:True | 37 | DWP | 10.8 | 27.0 | 51.4 | 10.8 |
| short false \| none \| Broken:False | 10 | R2 | 0.0 | 60.0 | 30.0 | 10.0 |
| short false \| none \| Broken:True | 7 | R2 | 14.3 | 71.4 | 14.3 | 0.0 |
| short true \| none \| Broken:False | 7 | R2 | 42.9 | 57.1 | 0.0 | 0.0 |
| short true \| none \| Broken:True | 14 | DNP | 7.1 | 28.6 | 14.3 | 50.0 |

