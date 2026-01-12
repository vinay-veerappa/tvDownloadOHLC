# Pine Script Architecture: Embedded Profiler Data

## 1. Problem Statement
The "Daily Profiler" relies on statistical distributions derived from 1-minute OHLC data over long periods (e.g., 2 years). Pine Script measures history by bars. On a 1-minute chart, 2 years is ~500,000 bars.
*   **Limitation 1:** `request.security` has limits on data depth.
*   **Limitation 2:** Calculating "Session Status" (e.g., Did Asia break high?) for 500 days on every tick is inefficient.
*   **Solution:** Pre-compute the history in Python and embed it as hardcoded arrays in the Pine Script.

## 2. Embedded Data Schema

We will use **Int 32 Compressed Arrays** to store the historical data. Each trading day is one entry in the arrays.

### Array 1: `dates` (int)
*   Format: `YYYYMMDD`
*   Example: `20241201`

### Array 2: `status_flags` (int bitmask)
We encode the status of all sessions into a single integer using bitmasks.
*   **Bits 0-3:** Asia Status (0=None, 1=LongTrue, 2=LongFalse, 3=ShortTrue, 4=ShortFalse)
*   **Bits 4-7:** London Status
*   **Bits 8-11:** NY1 Status
*   **Bits 12:** Asia Broken (0/1)
*   **Bits 13:** London Broken (0/1)
*   **Bits 14:** NY1 Broken (0/1)

### Array 3: `outcomes` (float / int)
To visualize the "Projected Box", we need the NY HOD/LOD statistics for that day.
*   We likely need multiple arrays if we want precise HOD/LOD times and prices.
*   *Optimization*: Since we visualize specific outcomes, maybe we only store the "NY Session High %" and "NY Session Low %" relative to open.

## 3. Pine Script Logic Flow

1.  **Detect Today's Status:**
    *   Script runs logic on current bar to update `current_asia_status`, `current_london_status`, etc.
2.  **Filter History:**
    *   Loop through the `status_flags` array.
    *   If `status_flags[i]` matches `current_status`, add index `i` to `matches[]`.
3.  **Aggregate Matches:**
    *   Loop through `matches[]`.
    *   Collect `ny_high_pct[i]` and `ny_low_pct[i]`.
    *   Calculate Median High/Low.
4.  **Plot:**
    *   Draw the "Projected Range" box for the current session.

## 4. Limitations & Constraints
*   **Script Size:** Pine Scripts have a 2MB size limit (approx). Storing 1000 days of data (3-4 arrays) is negligible (~50KB).
*   **Loop Limit:** Pine has a loop limit (often 500ms execution). Iterating 1000 days is safe.
*   **Maintenance:** The script is "static". It does not learn new days automatically. Use `generate_profiler_pine.py` to update it weekly/monthly.

## 5. File Structure
*   `docs/profiler/pine_architecture_design.md`: This file.
*   `scripts/pine_gen/generate_profiler_pine.py`: The generator script.
*   `docs/indicators/profiler_stats.pine`: The generated output.
