# Project Status: NY Session Strategy (Paused)
**Date:** Jan 11, 2026
**Status:** Paused / Debugging

## 1. Current Objective
Develop a **Trend Following** strategy for the NY Session (9:30 ET) that captures momentum while filtering out overextended moves using volatility statistics.

## 2. Strategy Logic (`ny_session_strategy.pine`)
-   **Setup**: Breakout of the 10-minute Open Range (9:30 - 9:40 ET).
-   **Entry**:
    -   Long: Close > 10m High.
    -   Short: Close < 10m Low.
-   **Filter (Confluence)**:
    -   Uses **Full Day (00:00 - 16:00) Median Distribution** stats.
    -   Logic: Do *not* enter if Price is already extended > `Session Open + (1.0 * Median Dist)`.
    -   *Hypothesis*: Avoid buying the top of a standard distribution day.

## 3. Simulation Findings
We ran Python simulations on 623 days of NQ data:
1.  **Hourly SD vs DC Stats**:
    -   **Hourly SD (Mult 2.0)**: +3.5 pts/trade, 35.4% WR. (Good but relies on hardcoded vol).
    -   **Full Day Median Dist (Mult 1.0)**: **+3.4 pts/trade, 35.4% WR**. (Best dynamic logic).
2.  **Manipulation Reversal**:
    -   Waiting for price to "touch" manipulation level *before* entry reduced profit (+2.9 pts).
    -   clean breakouts performed better.

## 4. Current Issue
**"No Trades"**: User reports the Pine Script strategy is not taking any trades.

### Possible Causes to Investigate:
1.  **Filter Initialization**:
    -   The filter relies on `dist_history` (Rolling Median).
    -   This array starts empty. `dc_median` is `na` until at least 1 day completes.
    -   Logic: `filter_type == "DC Median" and not na(dc_median)`.
    -   **Result**: Strategy *cannot* trade on Day 1. If testing on limited data, it may never trigger.
    -   *Fix*: Add fallback logic (e.g., `dc_median = na ? symbolData.daily_sd : ...`).
2.  **Session Time Logic**:
    -   `hour < 16` logic in Pine Script might be missing bars if the chart time/timeframe isn't aligning perfectly with the 00:00 start.
3.  **Variable Scope**:
    -   Ensure `dist_history` is actually preserving values across days (`var` keyword usage seems correct).

## 5. Next Steps
1.  **Debug Pine Script**: Add a label or plot to visualize `array.size(dist_history)` and `dc_median` to see if it's populating.
2.  **Add Fallback**: Allow trading with a default volatility value if the dynamic history isn't built yet.
3.  **Verify Timezone**: Ensure chart is set to `America/New_York` so `hour` checks align with the simulation.
