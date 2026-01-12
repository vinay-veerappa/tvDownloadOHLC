# Profiler Indicator Implementation Plan

## Goal Description
Create a Pine Script indicator that replicates the "Daily Profiling" capabilities of the web UI. This allows the user to filter historical days based on specific session behaviors (e.g., "Asia was Long") and visualize the resulting High/Low of Day (HOD/LOD) timing and price distributions for the NY Session directly on the chart.

## User Review Required
> [!IMPORTANT]
> The indicator will require 1-minute data resolution to accurately calculate session HOD/LOD times. It may be heavy on calculation as it needs to process historical session data for every bar (or efficiently using arrays).

## Proposed Changes

### Pine Script
#### [NEW] `docs/indicators/profiler_stats.pine`
A new indicator script with the following features:

1.  **Session Configuration Inputs**:
    *   Time definitions for Asia, London, NY AM (defaults provided).
    *   "Filter Session": Which session triggers the filter? (e.g., Previous Day, Asia, London).
    *   "Filter Condition": What happened? (e.g., "Closed > Open", "Broke Prior High", "Trend Up").

2.  **Core Logic**:
    *   **Session Stats**: Calculate Open, High, Low, Close for each defined session per day.
    *   **Status Determination**: Classify each session (Trend Up/Down, Range, etc.) similar to `ProfilerService`.
    *   **Data Collection**:
        *   If the *current day* matches the Filter Condition:
        *   Record the time (minute of day) of the NY Session High and Low.
        *   Record the price level of High/Low relative to NY Open.

3.  **Visualization (The "Outcome")**:
    *   **HOD/LOD Histograms**: Plot vertical histogram bars at the bottom of the chart showing the probability of HOD/LOD occurring at specific times (based on the filtered history).
    *   **Projected Range**: Plot a "Typical High/Low" box for the current day based on the average/median of the matching historical days.

## Verification Plan

### Manual Verification
1.  **Match UI**: Compare the indicator's histogram output with the "Profiler" page on the web app for a specific filter (e.g., "Asia Long").
2.  **Visual Check**: Verify that on days matching the criteria (e.g., Strong Asia trend), the projected HOD/LOD box aligns reasonably with price action.
### 2. Pine Script (Indicator)
#### [NEW] `docs/indicators/profiler_stats.pine`

*   **Part A: Live Classification Logic**
    *   **Session Inputs**:
        *   Asia: 18:00 - 19:30
        *   London: 02:30 - 03:30
        *   NY1: 07:30 - 08:30
    *   **Status Logic (Window: Session End -> Next Session Start)**:
        *   `Long True`: Break High, hold Low.
        *   `Short True`: Break Low, hold High.
        *   `Long False`: Break High, then break Low.
        *   `Short False`: Break Low, then break High.
        *   `None`: Inside Range.
    *   **Broken Logic (Window: Next Session Start -> 18:00)**:
        *   `Broken`: Price touches Session Mid `(High+Low)/2`.
        *   `None`: Mid not touched.
*   **Part B: Embedded Data lookup**
    *   Data mapped to classification keys (e.g. `Asia_Short_True_Broken`).
*   **Part C: Visualization**
    *   Projected HOD/LOD box based on median stats of matching days.
