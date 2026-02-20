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

### 3. Python (Data Pipeline)

#### [NEW] `scripts/profiler/generate_prediction_datasets.py`

A script to generate probabilistic lookups for Asia and London sessions.

- **Input**:
  - `data/NQ1_profiler.json` (For Session Status/Classification)
  - `data/NQ1_daily_hod_lod_unadjusted.json` (For HOD/LOD Price Probabilities - Critical for accurate % distances)

- **Logic**:
  1.  **Asia Prediction**:
      - Group by Date.
      - Get `NY1` and `NY2` status from _previous_ trading date.
      - Calculate distribution of _current_ `Asia` status.
      - Output: `{"NY1_Status|NY2_Status": {"Long True": %, ...}}`
  2.  **London Prediction**:
      - Get `NY2` status from _previous_ trading date.
      - Get `Asia` status from _current_ date.
      - Calculate distribution of _current_ `London` status.
      - Output: `{"NY2_Status|Asia_Status": {"Long True": %, ...}}`
- **Output Files**:
  - `data/NQ1_asia_predictions.json`
  - `data/NQ1_london_predictions.json`

1.  **Session Configuration Inputs**:
    - Time definitions for Asia, London, NY AM (defaults provided).
    - "Filter Session": Which session triggers the filter? (e.g., Previous Day, Asia, London).
    - "Filter Condition": What happened? (e.g., "Closed > Open", "Broke Prior High", "Trend Up").

2.  **Core Logic**:
    - **Session Stats**: Calculate Open, High, Low, Close for each defined session per day.
    - **Status Determination**: Classify each session (Trend Up/Down, Range, etc.) similar to `ProfilerService`.
    - **Data Collection**:
      - If the _current day_ matches the Filter Condition:
      - Record the time (minute of day) of the NY Session High and Low.
      - Record the price level of High/Low relative to NY Open.

#### [NEW] Frontend (Next.js)

- **New Component**: `web/components/profiler/PredictionPanel.tsx`
  - **Session Tabs (The Selector Mechanism)**:
    - A visible Tab Bar at the top of the panel: `[Target: Asia] | [Target: London] | [Target: NY]`.
    - Switching tabs updates the required Input Dropdowns and the Outcome Charts.
  - **Dynamic Input Section**:
    - If **Asia** Selected: Inputs = `Prev NY1`, `Prev NY2`.
    - If **London** Selected: Inputs = `Prev NY2`, `Current Asia`.
  - **Output Section**: Bar charts showing the probability of the _Next Session_ Status.
- **Modify**: `web/app/profiler/page.tsx`
  - Add a new tab or section for "Session Prediction".

## Verification Plan

### Manual Verification

1.  **Match UI**: Compare the indicator's histogram output with the "Profiler" page on the web app for a specific filter (e.g., "Asia Long").
2.  **Visual Check**: Verify that on days matching the criteria (e.g., Strong Asia trend), the projected HOD/LOD box aligns reasonably with price action.

### 2. Pine Script (Indicator)

#### [NEW] `docs/indicators/profiler_stats.pine`

- **Part A: Live Classification Logic**
  - **Session Inputs**:
    - Asia: 18:00 - 19:30
    - London: 02:30 - 03:30
    - NY1: 07:30 - 08:30
  - **Status Logic (Window: Session End -> Next Session Start)**:
    - `Long True`: Break High, hold Low.
    - `Short True`: Break Low, hold High.
    - `Long False`: Break High, then break Low.
    - `Short False`: Break Low, then break High.
    - `None`: Inside Range.
  - **Broken Logic (Window: Next Session Start -> 18:00)**:
    - `Broken`: Price touches Session Mid `(High+Low)/2`.
    - `None`: Mid not touched.
- **Part B: Embedded Data lookup**
  - Data mapped to classification keys (e.g. `Asia_Short_True_Broken`).
- **Part C: Visualization**
  - Projected HOD/LOD box based on median stats of matching days.
