# Daily Levels Indicator: Cashflow vs. Extended Cashflow TPs

**Video Reference:** [(68) Daily Levels Indicator / How I personally adjust my TPs from Cashflow vs Extended Cashflow](https://www.youtube.com/watch?v=yn8u0p2QHh4)

## Core Philosophy
The objective is to move away from "robotic" target choosing and instead use **human alignment**. This involves syncing the **Daily Profiler** (daily candle context) with objective **9:30 Trajectories (MF)**.

### The 9:30 Edge
- When price breaks above/below the 9:30 range, there is a high-probability "Generic Measured Move."
- **Standard Expectation:** A favorable price movement (MF) of **0.1% to 0.3%** is consistent across various market conditions.
- These levels are not "static calculations"; they are dynamic, adapting to the current market pulse (typically looking back 75 days on 1m data).

---

## Technical Overview of the Indicator

The **Daily New York Levels Indicator** specifically focuses on **MF (Max Favorable Excursion)** data to provide objective checkpoints for scaling out or trailing.

### Key Features & Settings
- **MF-Only Data:** Unlike other indicators that show both MAE and MF, this is designed strictly for **Exit/Take Profit (TP) Logic**.
- **Distribution Bars:** Shows granular clusters of where price actually goes, rather than just a simple box.
- **Granular Execution Window:**
    - **Cutoff Time:** 12:00 PM EST (Ideal for those who execute between 8:00 AM and Noon).
    - Base data is **1-minute**, though it can be calculated while viewing 5-minute charts for better lookback.
- **Percentile Granularity:** (e.g., 2% intervals) allows for very specific target setting right before "major walls" like the 50th or 60th percentile.

### Hit Rate Statistics
- Levels are labeled with hit rate percentages (e.g., "72.41% accuracy").
- **Combined vs. Directional Stats:** "Combined" uses all days (bullish/bearish), while "Directional" splits them (more specific but fewer samples).
- **Defcon Levels:** A mean reversion tool for high-strike-rate levels (e.g., waiting for a level to "fail" once to increase the odds of the next hit).

---

## Take Profit (TP) Strategy: Cashflow vs. Extended

### 1. The Cashflow Area (< 50th Percentile)
- Represents the **0.1% to 0.3%** move from 9:30.
- This is the "meat and potatoes" area: highly achievable, high-frequency "Cashflow" hits.
- Median and average moves usually cluster right in the middle of this zone (around 0.2%).

### 2. The Extended Target Area (> 50th Percentile)
- Used when the **Daily Profiler** and **Analysis** suggest a **Directional Day** (3-hour line, True Day).
- **Mechanical Trigger for Extended TPs:**
    - Look for **"False Drop-off Time"** (rejections/stalls at key times like 10:00).
    - Align with the upper echelon of the distribution (80th percentile).
    - Check if 9:30 MF aligns with other structural levels (Previous Day High, Globex Open, Midnight Open).

### 3. Time Distribution
- Highlights **when** the max extension typically occurs (Median range: **10:15 - 10:45 AM EST**).
- If the trade hasn't hit targets by 12:00 PM, the probability of further extension significantly drops (the "cutoff").

---

## Strategy Summary (The "Weapon" Metaphor)
- **9:30 Trajectory:** The "Max Effective Range" of the initial breakout.
- **Market Conditions:** The "environment" (Wind, Dirt, etc.) that affects that range.
- **The Process:** Use the Daily Profiler to understand the environment, then align it with the 9:30 trajectory to choose between a standard Cashflow exit or an Extended target.
