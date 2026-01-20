# RTY1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 2163 trading sessions of RTY1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 534 | DWP | 17.4 | 32.4 | 33.7 | 16.5 |
| **Bearish** | 484 | DWP | 21.7 | 31.0 | 34.7 | 12.6 |
| **Contradicting** | 1031 | DWP | 19.4 | 29.5 | 36.5 | 14.6 |
| **Neutral/Other** | 114 | DWP | 19.3 | 28.1 | 40.4 | 12.3 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| long false \| short false \| Brk:True | **63.6%** | 50.0% | 13.6% | 22 |
| long false \| long true \| Brk:True | **57.4%** | 32.8% | 24.6% | 61 |
| long true \| short true \| Brk:False | **57.1%** | 37.0% | 20.1% | 154 |
| none \| short true \| Brk:False | **57.1%** | 35.7% | 21.4% | 14 |
| long false \| short false \| Brk:False | **56.7%** | 40.5% | 16.2% | 37 |
| none \| short true \| Brk:True | **55.5%** | 44.4% | 11.1% | 18 |
| short true \| long true \| Brk:False | **55.1%** | 39.5% | 15.6% | 147 |
| short true \| long true \| Brk:True | **53.8%** | 33.3% | 20.5% | 78 |
| long true \| long true \| Brk:True | **52.1%** | 37.5% | 14.6% | 48 |
| long true \| short false \| Brk:True | **52.0%** | 40.0% | 12.0% | 25 |

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
| long false \| short false | Yes | **50.0%** | 22 |
| none \| short true | Yes | **44.4%** | 18 |
| short true \| long false | No | **41.6%** | 77 |
| short false \| long false | Yes | **40.9%** | 22 |
| long false \| long false | Yes | **40.7%** | 27 |
| long false \| short false | No | **40.5%** | 37 |
| long false \| long false | No | **40.0%** | 40 |
| long true \| short false | Yes | **40.0%** | 25 |

### Range Extensions (>40% R2)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short true \| short false | Yes | **42.9%** | 28 |

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 184 | DWP | 17.4 | 32.1 | 34.2 | 16.3 |
| long true \| long true \| Broken:True | 48 | DWP | 14.6 | 33.3 | 37.5 | 14.6 |
| long true \| short false \| Broken:False | 93 | R2 | 15.1 | 36.6 | 32.3 | 16.1 |
| long true \| short false \| Broken:True | 25 | DWP | 20.0 | 28.0 | 40.0 | 12.0 |
| short false \| long true \| Broken:False | 78 | DWP | 16.7 | 32.1 | 32.1 | 19.2 |
| short false \| long true \| Broken:True | 41 | DWP | 26.8 | 22.0 | 29.3 | 22.0 |
| short false \| short false \| Broken:False | 47 | DWP | 17.0 | 34.0 | 36.2 | 12.8 |
| short false \| short false \| Broken:True | 18 | R2 | 16.7 | 38.9 | 27.8 | 16.7 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 40 | DWP | 25.0 | 30.0 | 40.0 | 5.0 |
| long false \| long false \| Broken:True | 27 | DWP | 25.9 | 22.2 | 40.7 | 11.1 |
| long false \| short true \| Broken:False | 76 | DWP | 22.4 | 26.3 | 31.6 | 19.7 |
| long false \| short true \| Broken:True | 38 | DWP | 23.7 | 28.9 | 31.6 | 15.8 |
| short true \| long false \| Broken:False | 77 | DWP | 20.8 | 28.6 | 41.6 | 9.1 |
| short true \| long false \| Broken:True | 34 | R2 | 17.6 | 35.3 | 26.5 | 20.6 |
| short true \| short true \| Broken:False | 135 | R2 | 22.2 | 34.1 | 32.6 | 11.1 |
| short true \| short true \| Broken:True | 57 | R2 | 17.5 | 36.8 | 35.1 | 10.5 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 55 | R2 | 21.8 | 36.4 | 34.5 | 7.3 |
| long false \| long true \| Broken:True | 61 | DWP | 16.4 | 26.2 | 32.8 | 24.6 |
| long false \| short false \| Broken:False | 37 | DWP | 16.2 | 27.0 | 40.5 | 16.2 |
| long false \| short false \| Broken:True | 22 | DWP | 13.6 | 22.7 | 50.0 | 13.6 |
| long true \| long false \| Broken:False | 90 | DWP | 20.0 | 32.2 | 36.7 | 11.1 |
| long true \| long false \| Broken:True | 20 | DWP | 20.0 | 30.0 | 30.0 | 20.0 |
| long true \| short true \| Broken:False | 154 | DWP | 21.4 | 21.4 | 37.0 | 20.1 |
| long true \| short true \| Broken:True | 64 | R2 | 18.8 | 39.1 | 26.6 | 15.6 |
| short false \| long false \| Broken:False | 41 | DWP | 22.0 | 31.7 | 39.0 | 7.3 |
| short false \| long false \| Broken:True | 22 | DWP | 18.2 | 31.8 | 40.9 | 9.1 |
| short false \| short true \| Broken:False | 76 | DWP | 18.4 | 36.8 | 38.2 | 6.6 |
| short false \| short true \| Broken:True | 47 | DWP | 29.8 | 23.4 | 36.2 | 10.6 |
| short true \| long true \| Broken:False | 147 | DWP | 17.0 | 27.9 | 39.5 | 15.6 |
| short true \| long true \| Broken:True | 78 | DWP | 17.9 | 28.2 | 33.3 | 20.5 |
| short true \| short false \| Broken:False | 89 | DWP | 21.3 | 29.2 | 36.0 | 13.5 |
| short true \| short false \| Broken:True | 28 | R2 | 10.7 | 42.9 | 39.3 | 7.1 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 1 | DWP | 0.0 | 0.0 | 100.0 | 0.0 |
| long false \| none \| Broken:True | 2 | DWP | 0.0 | 50.0 | 50.0 | 0.0 |
| long true \| none \| Broken:False | 6 | DWP | 16.7 | 0.0 | 66.7 | 16.7 |
| long true \| none \| Broken:True | 5 | DWP | 0.0 | 40.0 | 40.0 | 20.0 |
| none \| long false \| Broken:False | 5 | DWP | 40.0 | 20.0 | 40.0 | 0.0 |
| none \| long false \| Broken:True | 9 | DWP | 11.1 | 22.2 | 44.4 | 22.2 |
| none \| long true \| Broken:False | 13 | DWP | 30.8 | 30.8 | 30.8 | 7.7 |
| none \| long true \| Broken:True | 16 | R2 | 25.0 | 37.5 | 25.0 | 12.5 |
| none \| none \| Broken:False | 3 | DWP | 0.0 | 33.3 | 66.7 | 0.0 |
| none \| short false \| Broken:False | 3 | DWP | 33.3 | 0.0 | 66.7 | 0.0 |
| none \| short false \| Broken:True | 7 | DWP | 0.0 | 14.3 | 57.1 | 28.6 |
| none \| short true \| Broken:False | 14 | DWP | 28.6 | 14.3 | 35.7 | 21.4 |
| none \| short true \| Broken:True | 18 | DWP | 11.1 | 33.3 | 44.4 | 11.1 |
| short false \| none \| Broken:False | 2 | DWP | 0.0 | 50.0 | 50.0 | 0.0 |
| short false \| none \| Broken:True | 2 | R2 | 0.0 | 100.0 | 0.0 | 0.0 |
| short true \| none \| Broken:False | 7 | R1 | 42.9 | 28.6 | 28.6 | 0.0 |
| short true \| none \| Broken:True | 1 | R2 | 0.0 | 100.0 | 0.0 | 0.0 |

