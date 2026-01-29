# Historical Sweep and Return to Open Study on Nasdaq Futures (NQ) – 10-Year Statistical Analysis — Herman Trading


Historical Sweep + Return to Open Study on 1H Candles [NQ]
Historical Sweep and Return to Open Study on Nasdaq Futures (NQ)
By Herman Trading

**Introduction**
This research investigates how the Nasdaq Futures (NQ) market behaves after a liquidity sweep. The goal was to quantify, with statistical precision, how often price returns to either the next hour’s open or the 50% equilibrium of the previous hourly range.
The study is based on more than a decade of historical 1-minute data and translated into clear, repeatable metrics that can help traders understand when mean reversion is statistically more likely to occur.


**Data and Methodology**
*   Data source: BacktestMarket.com
*   Instrument: Nasdaq Futures (NQ)
*   Period covered: 2009 – August 2025
*   Resolution: 1-minute OHLC data
*   Timezone: Converted from Chicago Time (CT) to New York Time (ET)

Each data point includes date, time, open, high, low, close, and volume. The dataset contains millions of rows processed in Python.

**Analytical Framework**
Python logic overview:
1.  Resample data to hourly intervals.
2.  Detect liquidity sweeps (breaks of the previous hour’s high or low).
3.  Track whether price subsequently reverted to the previous hour’s open or 50% midpoint.
4.  Aggregate all outcomes into summary tables and visual charts.


This approach preserves the precision of 1-minute data while analyzing market behavior through a higher-timeframe (1H) structure, which aligns with professional trading frameworks.

**Example Structure: Sweep and Return Logic**
Each “range hour” (for example, 02:00–03:00 AM ET) defines a liquidity pool. The following “trading window” (03:00–04:00 AM ET) is tested for:
*   A sweep of the previous hour’s high or low.
*   A subsequent reversion to the 3 AM open.
*   Or a reversion to 50% of the previous range (equilibrium level).

This framework quantifies a common market behavior observed during transitional or “killzone” hours, when liquidity is typically engineered before directional expansion.


**Results Overview**
The chart below shows the percentage of times price returned to the next hour’s open (blue) or 50% equilibrium (red) after a sweep, across all hourly ranges.

### [Table: Aggregate Stats]
*Transcribed from Image p4_0.png*
*   **Sessions analyzed**: 4,291
*   **Sweep occurred**: **94.7%**
*   **Return to 3AM Open**: **72.4%**
*   **Return to 50% of range**: **58.4%**

### [Chart: Return Percentages across Hours]
*Transcribed from Image p4_1.png*
*X-Axis: Hour of Day (ET) | Y-Axis: Return Probability (%)*

### [Table: Hourly Return Probabilities]
*Transcribed from Image p4_1.png (Visual Approximation of Bar Heights)*

| Price Range (Liquidity Pool) | Trading Window (Execution) | Return to Open % | Return to Mid % | Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| **00-01 AM** | **01-02 AM** | ~68% | ~48% | - |
| **01-02 AM** | **02-03 AM** | ~69% | ~49% | - |
| **02-03 AM** | **03-04 AM** | **~72%** | ~58% | **London Open**: Trading the 02-03 Range in the 03-04 Window. |
| **03-04 AM** | **04-05 AM** | ~56% | ~29% | **Trend**: Expansion often ignores reversion here. |
| **04-05 AM** | **05-06 AM** | ~61% | ~39% | - |
| **05-06 AM** | **06-07 AM** | ~64% | ~33% | - |
| **06-07 AM** | **07-08 AM** | ~61% | ~41% | - |
| **07-08 AM** | **08-09 AM** | **~69%** | ~50% | **Pre-NY**: Trading the NY AM (07-08) Range. |
| **08-09 AM** | **09-10 AM** | **~79%** | **~67%** | **GOLDEN HOUR**: Trading 09-10 (NYSE Open). Massive Mean Reversion. |
| **09-10 AM** | **10-11 AM** | ~62% | ~37% | - |
| **10-11 AM** | **11-12 PM** | ~55% | ~22% | **Trend**: Morning expansion continues. |
| **11-12 AM** | **12-13 PM** | ~58% | ~28% | - |
| **12-13 PM** | **13-14 PM** | ~61% | ~35% | - |
| **13-14 PM** | **14-15 PM** | ~63% | ~39% | - |
| **14-15 PM** | **15-16 PM** | ~67% | ~45% | - |
| **15-16 PM** | **16-17 PM** | ~57% | ~16% | **Trend**: Market Close / MOC. |
| **16-17 PM** | **17-18 PM** | ~58% | ~8% | **Dead Zone**: Post-Close. |
| **17-18 PM** | **18-19 PM** | **~76%** | ~58% | **Globex Open**: Fills the 17:00-18:00 gap. |
| **18-19 PM** | **19-20 PM** | ~60% | ~33% | - |
| **19-20 PM** | **20-21 PM** | ~66% | ~48% | - |
| **20-21 PM** | **21-22 PM** | ~62% | ~35% | - |
| **21-22 PM** | **22-23 PM** | ~60% | ~30% | - |
| **22-23 PM** | **23-00 AM** | ~61% | ~32% | - |

> **Critical Insight**: The Bar Chart displays the **Price Range Hour**. The trade occurs in the **Next Hour**.
> *   Highest Reversion (79%) is the **08-09 Range** → Traded in **09-10 Window**.
> *   Globex Reversion (76%) is the **17-18 Range** → Traded in **18-19 Window**.

## Interpretation and Practical Use Cases
*Derived from the hourly probability distribution.*

### 1. The "Golden Zones" (Fade the Sweep)
The data identifies specific liquidity windows where mean reversion is the dominant regime.
*   **08:00 – 09:00 AM Range (Trade 09:00 Open)**:
    *   **Logic**: Pre-market positioning often pushes price to an extreme to create liquidity before the NYSE Open.
    *   **Action**: If the 08:00 candle sweeps the 07:00 High/Low, **FADE IT**. Expect price to return to the 09:00 Open.
    *   **Confidence**: **Highest in Study (79%)**.

*   **17:00 – 18:00 PM Range (Trade Globex Open)**:
    *   **Logic**: The 17:00-18:00 gap often resets sentiment.
    *   **Action**: Fade the initial Globex expansion if it sweeps the 17:00 range. Focus on closure of the gap / return to Open.

### 2. The "Expansion Zones" (Respect the Trend)
Conversely, certain hours show a sharp DROP in reversion probability.
*   **03:00 – 04:00 AM (London Expansion)**:
    *   Reversion drops to **~56%**.
    *   **Insight**: London often trends *away* from the open after the initial sweep. Do not blindly fade breaks here; they are likely real moves.
*   **09:30 – 10:30 AM (NY Open)**:
    *   Reversion dips (~55-60%).
    *   **Insight**: The liquidity provided by the 08:00 fade is often used to fuel the 09:30 trend.

### 3. Target Selection
*   **Aggressive**: Target **Return to Open** in Golden Zones (08:00, 02:00, 17:00).
*   **Conservative**: Target **Return to 50% Midpoint** in lower probability zones or strong trends. The 50% level (Equilibrium) is hit **58.4%** of the time universally.




## Conclusion
Mean reversion is not random; it is time-dependent.
*   **Fade** the "Prep" hours (08:00, 02:00, 17:00).
*   **Follow** the "Move" hours (03:00, 09:30).
Using time as a filter transforms a ~50/50 setup into a **79% edge**.

## Interpretation and Use Cases
This dataset provides objective evidence of how often reversion occurs following liquidity sweeps. Traders can integrate these probabilities in several ways:

1.  **Killzone Backtesting**: Identify which hours historically show the highest reversion rates.
2.  **Directional Bias Filtering**:
    *   **Sweep + Return** → potential mean-reversion scenario.
    *   **Sweep without Return** → likely continuation bias.
3.  **Mechanical Model Design**: Convert the statistical tendencies into structured rules.
4.  **Entry Confirmation**: Validate trade ideas around session opens (e.g., 3 AM or 8 AM New York time).


*(Visualizations and Standard Disclaimer)*
Herman Trading | Risk Disclosure: Trading futures involves significant risk.
