# 📋 Statistical Analysis Standards (The Antigravity Standard)

This document outlines the mandatory requirements for all high-precision statistical reports and technical analyses performed on this codebase. These standards ensure that data is actionable for a "Stats Trader" and free from common statistical biases.

## 1. The Tripartite Statistic Rule
Never report a single average. Every quantitative metric must include:
*   **Mean (Average)**: To understand the "Total Weight" and detect "Fat Tails."
*   **Median (50th Percentile)**: To understand the "Typical Case" (resistant to outliers).
*   **Mode (Most Frequent)**: To identify where price/time "Clusters."
    *   *Example*: A Mean fill time of 60m but a Median of 15m tells the trader the edge is early.

## 2. The Multi-Unit Perspective
Statistics must be viewed through both relative and absolute lenses:
*   **Pattern-Relative (%)**: Move relative to the setup size (e.g., "% of the Gap").
*   **Price-Relative (%)**: Move relative to the absolute index/asset price.
    *   *Standard Conversion*: In NQ reports, always provide the equivalent in "Index Percentage" (e.g., 0.03% = ~7.5 pts at 25k).

## 3. Mandatory Contextual Segmentation (Regimes)
"Overall" stats are insufficient. Data must be segmented by:
*   **Temporal Regimes**: Day of Week (Monday vs. Wednesday).
*   **Volatility Regimes**: ATR buckets (Low, Normal, High).
*   **Market Sentiment Regimes**: VVIX/VIX levels (e.g., VVIX > 110).

## 4. Operationalization (The Logic Gate)
Every statistical finding must be converted into a "Logic Gate" or "Checklist Item":
*   If *[Condition]* and *[Stats Threshold]*, then *[Operational Bias]*.
*   *Example*: "If Gap > 0.5% and ATR is High, then Defense is Favored."

## 5. Temporal Windows (The 15-Minute Rule)
Analyses involving "Fills" or "Touches" must include time-based probability bins:
*   **0-15m**: The High-Probability Window.
*   **15-60m**: The Transition Window.
*   **>60m**: The Fade Window (where the edge degrades).

## 6. Ticker Independence
All scripts must accept a ticker/symbol argument to ensure cross-market verification and batch processing portability.

## 7. Operational Usability (Analysis & Takeaways)
Every statistical section must conclude with a **"Day Trader Takeaway."**
*   **Goal**: Translate raw data (e.g., 68% fill rate) into execution rules (e.g., "Set stop-loss beyond the median 15% fakeout depth").
*   **Context**: Include qualitative analysis explaining *why* the data looks that way (e.g., Institutional hedging vs. retail noise).

## 8. News & Event Correlation Standards
To avoid false correlations or data drift in news analysis:
*   **Timezone Normalization**: Primary source APIs often store news with timezone offsets (e.g., 3-hour shift). Always verify offsets against "Anchor Events" (e.g., NFP is strictly 08:30 ET).
*   **Geographic Filtering**: High-impact news from foreign markets (e.g., Germay FLASH PMI) must be filtered out for indices like NQ to ensure the signal is focused on domestic US drivers.

## 9. Data Integrity & Fusing Standards
To ensure reports are viable at "The Hard Right Edge":
*   **Fused Loading**: Always use the `load_fused_data` utility to merge "Live Storage" (current month) with "Historical Repos" (years).
*   **US/Eastern Locking**: Gaps and RTH sessions must be calculated using a strictly localized `US/Eastern` timezone object to account for Daylight Savings shifts automatically.

---
*Last Updated: January 23, 2026*
