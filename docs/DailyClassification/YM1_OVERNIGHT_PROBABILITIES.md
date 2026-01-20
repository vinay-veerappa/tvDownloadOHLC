# YM1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 4591 trading sessions of YM1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1145 | R2 | 20.2 | 36.1 | 30.0 | 13.7 |
| **Bearish** | 974 | R2 | 21.9 | 37.0 | 26.8 | 14.4 |
| **Contradicting** | 2222 | R2 | 22.2 | 34.3 | 29.9 | 13.6 |
| **Neutral/Other** | 250 | R2 | 21.6 | 35.2 | 25.6 | 17.6 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| long true \| none \| Brk:False | **60.0%** | 50.0% | 10.0% | 20 |
| none \| long false \| Brk:True | **55.5%** | 33.3% | 22.2% | 18 |
| short false \| short true \| Brk:False | **50.0%** | 34.1% | 15.9% | 138 |
| long true \| long true \| Brk:False | **47.6%** | 31.1% | 16.5% | 328 |
| long true \| short true \| Brk:True | **47.099999999999994%** | 34.4% | 12.7% | 157 |
| short false \| long false \| Brk:False | **47.0%** | 27.2% | 19.8% | 81 |
| long true \| long true \| Brk:True | **46.6%** | 27.1% | 19.5% | 118 |
| short true \| short false \| Brk:True | **46.5%** | 22.4% | 24.1% | 58 |
| long true \| long false \| Brk:False | **46.3%** | 30.5% | 15.8% | 203 |
| long false \| short true \| Brk:False | **46.3%** | 29.4% | 16.9% | 136 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
_No setups met the threshold._

### Clean Trend Runners (>30% DNP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| short false | No | **30.8%** | 13 |

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| long true \| none | No | **50.0%** | 20 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| short true | No | **53.8%** | 13 |
| short false \| short false | Yes | **50.7%** | 69 |
| short true \| none | No | **45.0%** | 20 |
| short true \| long false | Yes | **42.6%** | 61 |
| none \| short true | Yes | **41.7%** | 36 |
| short true \| short false | Yes | **41.4%** | 58 |
| none \| long true | Yes | **40.0%** | 35 |
| short false \| short true | Yes | **40.0%** | 120 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 328 | R2 | 18.9 | 33.5 | 31.1 | 16.5 |
| long true \| long true \| Broken:True | 118 | R2 | 22.9 | 30.5 | 27.1 | 19.5 |
| long true \| short false \| Broken:False | 198 | R2 | 21.7 | 34.3 | 31.8 | 12.1 |
| long true \| short false \| Broken:True | 78 | R2 | 24.4 | 34.6 | 29.5 | 11.5 |
| short false \| long true \| Broken:False | 167 | R2 | 19.8 | 39.5 | 31.7 | 9.0 |
| short false \| long true \| Broken:True | 106 | R2 | 20.8 | 36.8 | 32.1 | 10.4 |
| short false \| short false \| Broken:False | 81 | R2 | 18.5 | 39.5 | 25.9 | 16.0 |
| short false \| short false \| Broken:True | 69 | R2 | 14.5 | 50.7 | 23.2 | 11.6 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 74 | R2 | 24.3 | 35.1 | 28.4 | 12.2 |
| long false \| long false \| Broken:True | 59 | DWP | 32.2 | 25.4 | 32.2 | 10.2 |
| long false \| short true \| Broken:False | 136 | R2 | 17.6 | 36.0 | 29.4 | 16.9 |
| long false \| short true \| Broken:True | 107 | R2 | 27.1 | 39.3 | 21.5 | 12.1 |
| short true \| long false \| Broken:False | 132 | R2 | 26.5 | 33.3 | 26.5 | 13.6 |
| short true \| long false \| Broken:True | 61 | R2 | 16.4 | 42.6 | 32.8 | 8.2 |
| short true \| short true \| Broken:False | 294 | R2 | 19.7 | 39.5 | 25.9 | 15.0 |
| short true \| short true \| Broken:True | 111 | R2 | 18.0 | 37.8 | 24.3 | 19.8 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 152 | R2 | 21.7 | 34.2 | 33.6 | 10.5 |
| long false \| long true \| Broken:True | 145 | R2 | 22.8 | 37.2 | 25.5 | 14.5 |
| long false \| short false \| Broken:False | 95 | R1 | 32.6 | 28.4 | 30.5 | 8.4 |
| long false \| short false \| Broken:True | 55 | R2 | 23.6 | 36.4 | 25.5 | 14.5 |
| long true \| long false \| Broken:False | 203 | R2 | 19.2 | 34.5 | 30.5 | 15.8 |
| long true \| long false \| Broken:True | 51 | R2 | 19.6 | 37.3 | 31.4 | 11.8 |
| long true \| short true \| Broken:False | 332 | R2 | 20.8 | 34.6 | 31.0 | 13.6 |
| long true \| short true \| Broken:True | 157 | R2 | 16.6 | 36.3 | 34.4 | 12.7 |
| short false \| long false \| Broken:False | 81 | R2 | 23.5 | 29.6 | 27.2 | 19.8 |
| short false \| long false \| Broken:True | 54 | R2 | 29.6 | 31.5 | 25.9 | 13.0 |
| short false \| short true \| Broken:False | 138 | DWP | 22.5 | 27.5 | 34.1 | 15.9 |
| short false \| short true \| Broken:True | 120 | R2 | 24.2 | 40.0 | 27.5 | 8.3 |
| short true \| long true \| Broken:False | 243 | R2 | 22.2 | 36.2 | 29.6 | 11.9 |
| short true \| long true \| Broken:True | 170 | DWP | 25.9 | 30.6 | 30.6 | 12.9 |
| short true \| short false \| Broken:False | 168 | R2 | 23.8 | 33.9 | 26.8 | 15.5 |
| short true \| short false \| Broken:True | 58 | R2 | 12.1 | 41.4 | 22.4 | 24.1 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 4 | DNP | 25.0 | 25.0 | 25.0 | 25.0 |
| long false \| none \| Broken:True | 5 | DWP | 20.0 | 40.0 | 40.0 | 0.0 |
| long true \| none \| Broken:False | 20 | DWP | 15.0 | 25.0 | 50.0 | 10.0 |
| long true \| none \| Broken:True | 5 | DNP | 20.0 | 0.0 | 40.0 | 40.0 |
| none \| long false \| Broken:False | 9 | R2 | 0.0 | 55.6 | 44.4 | 0.0 |
| none \| long false \| Broken:True | 18 | DWP | 22.2 | 22.2 | 33.3 | 22.2 |
| none \| long true \| Broken:False | 31 | R1 | 35.5 | 22.6 | 25.8 | 16.1 |
| none \| long true \| Broken:True | 35 | R2 | 17.1 | 40.0 | 22.9 | 20.0 |
| none \| short false \| Broken:False | 13 | R2 | 15.4 | 38.5 | 15.4 | 30.8 |
| none \| short false \| Broken:True | 21 | R2 | 28.6 | 33.3 | 23.8 | 14.3 |
| none \| short true \| Broken:False | 13 | R2 | 23.1 | 53.8 | 7.7 | 15.4 |
| none \| short true \| Broken:True | 36 | R2 | 22.2 | 41.7 | 22.2 | 13.9 |
| short false \| none \| Broken:False | 9 | R2 | 0.0 | 55.6 | 11.1 | 33.3 |
| short false \| none \| Broken:True | 5 | R2 | 20.0 | 40.0 | 20.0 | 20.0 |
| short true \| none \| Broken:False | 20 | R2 | 20.0 | 45.0 | 20.0 | 15.0 |
| short true \| none \| Broken:True | 6 | R1 | 50.0 | 0.0 | 16.7 | 33.3 |

