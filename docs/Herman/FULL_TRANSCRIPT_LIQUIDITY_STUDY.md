# Deep Asia–London Session Liquidity Study on Nasdaq Futures (NQ) _ 17-Year Statistical Analysis — Herman Trading

Deep Asia–London Session Study: 17 Years of Nasdaq Futures Data
By Herman Trading

## Introduction
Understanding the relationship between the Asia, Pre-London, and London sessions provides valuable insight into how liquidity develops before major directional moves in Nasdaq Futures (NQ).
This study examines 17 years of historical 1-minute data (4,262 trading days) to quantify how frequently price sweeps the Asia session’s high or low, and how those events influence the rest of the day’s behavior.
The findings reveal repeatable structures that can help traders anticipate continuation, reversal, or consolidation conditions based purely on historical probability.

## Data and Methodology
*   Data source: BacktestMarket.com
*   Instrument: Nasdaq Futures (NQ)
*   Sample size: 4,262 trading days (≈17 years)
*   Resolution: 1-minute OHLCV data
*   Timezone: Converted from Chicago Time (CT) to New York Time (ET)
*   Weekends: Excluded (Monday–Friday only)

Each day was segmented into sessions based on New York time:
*   Asia Session: 20:00 – 23:59
*   Pre-London (Dead Zone): 00:00 – 01:59
*   London Session: 02:00 – 04:59

All timestamps were normalized to ensure consistency across years and volatility regimes.

### Session Definitions
To analyze liquidity interaction across sessions, the script isolated each period as separate dataframes using pandas. This allowed for precise testing of how often each session swept (broke) the Asia range’s high or low, and how the daily candle subsequently closed.

## Pre-London Statistics (00:00–02:00)
### [Chart: Pre-London Statistics]
*(Visual shows a bar chart comparing sweep frequencies)*

**Pre-London / Dead Zone (00:00–02:00)**
*   Sweeps Asia High: **34.44%**
*   Sweeps Asia Low: **27.29%**
*   Sweeps Both High and Low: **1.74%**

**Interpretation:**
The Pre-London window rarely captures both sides of the Asia range. It typically serves as a liquidity-building phase, often setting traps before the London session expands directionally.

## London Session Statistics (02:00–05:00)
*   Sweeps Asia High: **59.81%**
*   Sweeps Asia Low: **49.46%**
*   Sweeps Both: **17.97%**

The London Killzone shows a distinct increase in volatility and sweep activity. Roughly 60% of days break the Asia high, and 50% take the Asia low. Both sides are swept on nearly 18% of all days — often leading to major reversals or strong directional days.

### [Chart: Combined Session Stats]
*(Visual shows aggregate probabilities)*

**Combined Session (00:00–05:00)**
*   Sweeps Asia High: **65.32%**
*   Sweeps Asia Low: **55.42%**

When combining both Pre-London and London sessions, Asia highs are swept in nearly two-thirds of all days, confirming a consistent liquidity interaction before the New York open.

## Average Asia Range and Volatility Context
The average Asia session range since 2020 measures 78.45 points on NQ. This 5-year window (2020–2025) better represents current market volatility than older data, as session amplitude has increased significantly since 2019.
This average was used as a dynamic threshold to divide all days into:
*   Above-average Asia Range Days
*   Below-average Asia Range Days

**Sweep Behavior by Asia Range Size**
*Transcribed from Image p5_0.png*

| Statistic | Above Average Asia (>78.45pts) | Below Average Asia (<78.45pts) |
| :--- | :--- | :--- |
| **Sample Size** | n=485 | n=936 |
| London takes Asia High | 49.48% | **61.00%** |
| London takes Asia Low | 40.62% | **52.35%** |
| **London takes BOTH** | **6.39%** | **18.70%** |
| Pre-London takes Asia High | 32.16% | 35.26% |
| Pre-London takes Asia Low | 24.33% | 27.46% |
| Pre-London takes BOTH | 0.21% | 1.60% |

**Interpretation**:
*   **Narrow Asia (<78 pts)**: London is aggressive. It takes **BOTH** sides nearly 19% of the time (3x more likely than on wide days).
*   **Wide Asia**: London is selective. It rarely sweeps both (6.39%).

## Continuation Patterns: Pre-London → London
One of the most statistically significant findings is the continuation effect from Pre-London into London.

### [Diagram: Continuation Mechanics]
*(Visual showing a "Small Asia" box, followed by "Pre-London" breaking out, then "London" continuing higher)*
**Caption**: "If Pre took Asia High → London takes Pre High: **77.16%**"

**Detailed Conditional Statistics (All Days n=1421)**
*Transcribed from Image p8_0.png*

**1. Continued Direction (Pre → London)**
*   If Pre took Asia High → London takes Pre High again: **77.16%**
*   If Pre took Asia Low → London takes Pre Low again: **69.60%**

**2. Reversal / Expansion (Pre → Other Side)**
*   If Pre took Asia Low → London takes Asia High: **30.13%**
*   If Pre took Asia High → London takes Asia Low: **23.05%**

### [Table: Day Close Behavior After Sweeps]
*Transcribed from Image p7_0.png*

| Event | Day Closed Higher | Day Closed Lower |
| :--- | :--- | :--- |
| **London took Asia High** | **60.81%** | 39.19% |
| **London took Asia Low** | 48.10% | **51.90%** |
| **Pre took Asia High** | **57.22%** | 42.78% |
| **Pre took Asia Low** | **53.14%** | 46.86% |

**Interpretation**:
*   **London Sweeps High**: Strong bias for the day to close GREEN (60.8%).
*   **London Sweeps Low**: Slight bias for RED close (51.9%).
*   **Pre-London**: Less predictive, but Pre-High sweeps still favor upside continuation (57%).

**Below-Average Asia Range Days (Specifics)**
*   If Pre took Asia High → London continues same direction: **79.09%**
*   If Pre took Asia Low → London continues same direction: **75.10%**

This reveals a strong directional follow-through when Asia volatility is low — confirming that Pre-London often sets the stage for the London expansion.

## Day Close Behavior After Sweeps
This confirms a mild bullish bias after London takes the Asia high, while Asia-low sweeps show modest continuation to the downside. Although not extreme, these probabilities support bias confirmation into the New York session.

## Practical Takeaways for Traders
1.  **Directional Bias from Liquidity Sweep**
    *   If London sweeps Asia High → expect higher close bias (≈60%).
    *   If London sweeps Asia Low → expect lower close bias (≈52%).
    *   Use these probabilities to filter directional setups.

2.  **Continuation from Pre-London into London**
    *   If Pre-London sweeps one side, expect London to continue that move 70–79% of the time.
    *   Ideal for London Killzone entries after initial liquidity grab.

3.  **Asia Range Size as Volatility Filter**
    *   Narrow Asia ranges (<78 pts) → increased London sweep frequency and continuation probability.

4.  **Avoid Overtrading During Dead Zone**
    *   The Pre-London session sweeps both Asia highs and lows only 1.13% of the time.
    *   Focus on observation and liquidity mapping rather than aggressive entries.

**Conclusion**
Across 17 years of Nasdaq Futures data, the Asia–London interaction consistently reveals predictable liquidity behavior:
*   Two-thirds of all days sweep the Asia high before 05:00 ET.
*   Continuation from Pre-London into London occurs in nearly 3 out of 4 cases.
*   Narrow Asia sessions create the most exploitable trading conditions.

These patterns form a quantifiable statistical edge, allowing traders to align with historical behavior rather than speculation.

## Page 9
*(References)*
NQ London Playbook — Decision Tree (with stats)
Historical Sweep + Return to Open Study on 1H Candles [NQ]
For ongoing updates and further probability research, visit:
hermantrading.pro
and follow @R_Herman_ on X.
