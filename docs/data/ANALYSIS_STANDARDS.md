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

---
*Created: January 23, 2026*
