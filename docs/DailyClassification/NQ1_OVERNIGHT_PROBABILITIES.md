# NQ1 Overnight Classification Probability Matrix

This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).

## Methodology
- **Data Source**: 5008 trading sessions of NQ1 history.
- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.
- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).

## 1. Aggregate Scenario Analysis
Do 'Bullish' overnight sessions actually lead to Bullish RTH days?

| Scenario | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bullish** | 1258 | R1 | 44.1 | 14.7 | 28.9 | 12.2 |
| **Bearish** | 1053 | R1 | 45.0 | 16.1 | 27.7 | 11.1 |
| **Contradicting** | 2419 | R1 | 45.9 | 16.8 | 25.7 | 11.6 |
| **Neutral/Other** | 278 | R1 | 44.2 | 11.9 | 29.1 | 14.7 |

## 2. Trend Day Analysis (DWP + DNP)
Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?

| Setup (Asia \| London \| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- |
| none \| short true \| Brk:True | **56.7%** | 45.9% | 10.8% | 37 |
| none \| long true \| Brk:False | **56.599999999999994%** | 43.3% | 13.3% | 30 |
| none \| long false \| Brk:True | **55.6%** | 50.0% | 5.6% | 18 |
| none \| long true \| Brk:True | **51.4%** | 17.1% | 34.3% | 35 |
| short true \| none \| Brk:True | **50.0%** | 14.3% | 35.7% | 14 |
| none \| short true \| Brk:False | **50.0%** | 29.2% | 20.8% | 24 |
| long true \| short false \| Brk:True | **46.5%** | 33.8% | 12.7% | 71 |
| none \| short false \| Brk:False | **45.5%** | 45.5% | 0.0% | 11 |
| long true \| long true \| Brk:False | **44.7%** | 31.4% | 13.3% | 398 |
| short false \| long true \| Brk:False | **44.599999999999994%** | 33.8% | 10.8% | 148 |

> [!TIP]
> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.

## 3. Top High-Probability Setups (Other Insights)
Setups with >40% probability for specific outcomes.

### Trend Killers / Range Days (>40% R1)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| long true \| none | No | **59.1%** | 22 |
| long true \| none | Yes | **56.2%** | 16 |
| none \| long false | No | **56.2%** | 16 |
| short false \| long false | Yes | **55.4%** | 56 |
| long false \| short false | Yes | **52.7%** | 55 |
| long false \| long true | Yes | **52.0%** | 148 |
| long false \| long false | No | **51.1%** | 92 |
| short true \| short false | No | **50.9%** | 175 |
| long false \| long false | Yes | **50.8%** | 61 |
| short true \| long false | No | **50.4%** | 141 |
| short false \| none | No | **50.0%** | 10 |
| short false \| short false | Yes | **48.5%** | 66 |
| short false \| short false | No | **48.2%** | 85 |
| short true \| long false | Yes | **48.1%** | 79 |
| short false \| long false | No | **48.0%** | 100 |
| long true \| long true | Yes | **47.3%** | 129 |
| long true \| short false | No | **47.0%** | 232 |
| short true \| long true | No | **46.5%** | 273 |
| long true \| long false | No | **46.1%** | 217 |
| short false \| short true | Yes | **45.9%** | 133 |
| none \| short false | No | **45.5%** | 11 |
| long false \| long true | No | **45.1%** | 175 |
| short true \| short false | Yes | **45.1%** | 71 |
| long true \| short true | No | **44.7%** | 342 |
| short true \| short true | No | **44.3%** | 305 |
| long true \| long false | Yes | **44.0%** | 50 |
| long true \| short true | Yes | **43.3%** | 157 |
| short false \| long true | No | **43.2%** | 148 |
| none \| long true | Yes | **42.9%** | 35 |
| short true \| none | Yes | **42.9%** | 14 |
| short true \| long true | Yes | **42.6%** | 197 |
| short false \| short true | No | **42.3%** | 168 |
| long true \| long true | No | **42.2%** | 398 |
| long false \| short true | Yes | **41.6%** | 113 |
| long false \| short true | No | **41.1%** | 146 |
| short false \| long true | Yes | **41.1%** | 129 |
| none \| long true | No | **40.0%** | 30 |

### Clean Trend Runners (>30% DNP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| short true \| none | Yes | **35.7%** | 14 |
| none \| long true | Yes | **34.3%** | 35 |

### Reversion / Deep Pullback (>40% DWP)
| Setup (Asia \| London) | Broken? | Prob % | n |
| :--- | :--- | :--- | :--- |
| none \| long false | Yes | **50.0%** | 18 |
| none \| short true | Yes | **45.9%** | 37 |
| none \| short false | No | **45.5%** | 11 |
| none \| long true | No | **43.3%** | 30 |

### Range Extensions (>40% R2)
_No setups met the threshold._

## 4. Exhaustive Probability Matrix (By Scenario)
### Bullish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long true \| long true \| Broken:False | 398 | R1 | 42.2 | 13.1 | 31.4 | 13.3 |
| long true \| long true \| Broken:True | 129 | R1 | 47.3 | 8.5 | 31.8 | 12.4 |
| long true \| short false \| Broken:False | 232 | R1 | 47.0 | 16.8 | 26.7 | 9.5 |
| long true \| short false \| Broken:True | 71 | R1 | 38.0 | 15.5 | 33.8 | 12.7 |
| short false \| long true \| Broken:False | 148 | R1 | 43.2 | 12.2 | 33.8 | 10.8 |
| short false \| long true \| Broken:True | 129 | R1 | 41.1 | 14.7 | 27.9 | 16.3 |
| short false \| short false \| Broken:False | 85 | R1 | 48.2 | 31.8 | 15.3 | 4.7 |
| short false \| short false \| Broken:True | 66 | R1 | 48.5 | 12.1 | 19.7 | 19.7 |

### Bearish Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long false \| Broken:False | 92 | R1 | 51.1 | 15.2 | 18.5 | 15.2 |
| long false \| long false \| Broken:True | 61 | R1 | 50.8 | 13.1 | 27.9 | 8.2 |
| long false \| short true \| Broken:False | 146 | R1 | 41.1 | 15.1 | 31.5 | 12.3 |
| long false \| short true \| Broken:True | 113 | R1 | 41.6 | 20.4 | 29.2 | 8.8 |
| short true \| long false \| Broken:False | 141 | R1 | 50.4 | 12.1 | 29.1 | 8.5 |
| short true \| long false \| Broken:True | 79 | R1 | 48.1 | 16.5 | 24.1 | 11.4 |
| short true \| short true \| Broken:False | 305 | R1 | 44.3 | 16.4 | 28.2 | 11.1 |
| short true \| short true \| Broken:True | 116 | R1 | 38.8 | 19.8 | 28.4 | 12.9 |

### Contradicting Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| long true \| Broken:False | 175 | R1 | 45.1 | 17.1 | 25.1 | 12.6 |
| long false \| long true \| Broken:True | 148 | R1 | 52.0 | 15.5 | 18.9 | 13.5 |
| long false \| short false \| Broken:False | 102 | R1 | 39.2 | 21.6 | 26.5 | 12.7 |
| long false \| short false \| Broken:True | 55 | R1 | 52.7 | 12.7 | 27.3 | 7.3 |
| long true \| long false \| Broken:False | 217 | R1 | 46.1 | 18.4 | 25.8 | 9.7 |
| long true \| long false \| Broken:True | 50 | R1 | 44.0 | 14.0 | 32.0 | 10.0 |
| long true \| short true \| Broken:False | 342 | R1 | 44.7 | 12.6 | 26.9 | 15.8 |
| long true \| short true \| Broken:True | 157 | R1 | 43.3 | 19.1 | 24.8 | 12.7 |
| short false \| long false \| Broken:False | 100 | R1 | 48.0 | 18.0 | 22.0 | 12.0 |
| short false \| long false \| Broken:True | 56 | R1 | 55.4 | 14.3 | 21.4 | 8.9 |
| short false \| short true \| Broken:False | 168 | R1 | 42.3 | 16.7 | 29.2 | 11.9 |
| short false \| short true \| Broken:True | 133 | R1 | 45.9 | 18.8 | 27.8 | 7.5 |
| short true \| long true \| Broken:False | 273 | R1 | 46.5 | 19.4 | 25.3 | 8.8 |
| short true \| long true \| Broken:True | 197 | R1 | 42.6 | 17.3 | 24.9 | 15.2 |
| short true \| short false \| Broken:False | 175 | R1 | 50.9 | 14.3 | 27.4 | 7.4 |
| short true \| short false \| Broken:True | 71 | R1 | 45.1 | 19.7 | 25.4 | 9.9 |

### Neutral/Other Scenarios
| Overnight Key | n | Most Likely | R1% | R2% | DWP% | DNP% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| long false \| none \| Broken:False | 6 | R1 | 66.7 | 0.0 | 16.7 | 16.7 |
| long false \| none \| Broken:True | 7 | R1 | 42.9 | 28.6 | 14.3 | 14.3 |
| long true \| none \| Broken:False | 22 | R1 | 59.1 | 9.1 | 18.2 | 13.6 |
| long true \| none \| Broken:True | 16 | R1 | 56.2 | 12.5 | 18.8 | 12.5 |
| none \| long false \| Broken:False | 16 | R1 | 56.2 | 18.8 | 18.8 | 6.2 |
| none \| long false \| Broken:True | 18 | DWP | 22.2 | 22.2 | 50.0 | 5.6 |
| none \| long true \| Broken:False | 30 | DWP | 40.0 | 3.3 | 43.3 | 13.3 |
| none \| long true \| Broken:True | 35 | R1 | 42.9 | 5.7 | 17.1 | 34.3 |
| none \| none \| Broken:False | 1 | R1 | 100.0 | 0.0 | 0.0 | 0.0 |
| none \| none \| Broken:True | 1 | DWP | 0.0 | 0.0 | 100.0 | 0.0 |
| none \| short false \| Broken:False | 11 | DWP | 45.5 | 9.1 | 45.5 | 0.0 |
| none \| short false \| Broken:True | 16 | DWP | 31.2 | 25.0 | 31.2 | 12.5 |
| none \| short true \| Broken:False | 24 | R1 | 37.5 | 12.5 | 29.2 | 20.8 |
| none \| short true \| Broken:True | 37 | DWP | 35.1 | 8.1 | 45.9 | 10.8 |
| short false \| none \| Broken:False | 10 | R1 | 50.0 | 20.0 | 30.0 | 0.0 |
| short false \| none \| Broken:True | 7 | R1 | 57.1 | 28.6 | 14.3 | 0.0 |
| short true \| none \| Broken:False | 7 | R1 | 85.7 | 14.3 | 0.0 | 0.0 |
| short true \| none \| Broken:True | 14 | R1 | 42.9 | 7.1 | 14.3 | 35.7 |

