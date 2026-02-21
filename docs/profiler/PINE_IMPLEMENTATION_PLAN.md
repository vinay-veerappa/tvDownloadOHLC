# Profiler PineScript Integration Plan

## Goal

Integrate the newly defined system requirements—specifically NY P12 levels, Cross-Session Previous Mids, and standardized 17:00 ET Day End—into the Pine Script indicator via the `generate_profiler_pine.py` data pipeline. This mapping will ensure the TradingView indicator maintains parity with the Web UI.

## Phase 1: Python Generator Updates (`generate_profiler_pine.py`)

1. **Target Session Data Mapping (Lookahead Bias Prevention)**:
   - The script currently groups touches by dynamically checking which session the touch fell into (`t_ny1m_a` = NY1 Mid hit during Asia).
   - **Update**: For Asia and London session targets (where current day's NY mids haven't formed), the python script MUST read the data keys `prev_asia_mid`, `prev_london_mid`, `prev_ny1_mid`, and `prev_ny2_mid` from the `touches` JSON instead of the current day's keys. This matches the cross-session context logic just implemented in the backend/frontend.
2. **NY P12 Data Processing**:
   - Add `ny_p12h`, `ny_p12m`, and `ny_p12l` to the `TOUCH_LEVELS` array.
   - Process these touches through the 4 target sessions (Asia, London, NY1, NY2) and generate new Pine Library arrays for them (e.g. `LibTouches.get_ny_p12h_asia()`).
3. **Library Schema Overhaul**:
   - Update the export chunks to account for the new NY P12 arrays and the Prev Session Mid arrays.

## Phase 2: Pine Script Indicator Logic Updates

1. **End-Of-Day Standardization (17:00)**:
   - Refactor `f_get_1600_et()` to `f_get_1700_et()`.
   - Update all mid lines (`l_asia_mid`, `l_lon_mid`, `l_ny1_mid`, `l_ny2_mid`) to anchor their ending X-coordinates at `t_close` (17:00) instead of 16:00.
2. **Live NY P12 Calculation**:
   - Add state variables to track the highest high and lowest low from 06:00 to 17:00.
   - At 18:00 (new session start), lock those values into `prev_ny_p12_h` and `prev_ny_p12_l` so they can be drawn as horizontal reference lines throughout the current trading day.
3. **Live "Prev Session Mids" Storage**:
   - The indicator currently calculates and draws `asia_mid`, `lon_mid`, `ny1_mid`, and `ny2_mid`.
   - We must add tracking for `prev_asia_mid`, `prev_lon_mid`, `prev_ny1_mid`, and `prev_ny2_mid`. At 18:00 (or at the end of each session respectively), push the current values into the "prev" variables.
   - Use these `prev_*` variables to draw reference lines when analyzing the Asia and London sessions to visually reflect what the data is checking against.

## Phase 3: Visual & UI Overhaul (Pine Script)

1. **Reference Line Toggles**:
   - Add new `input.bool` and `input.color` groups for "Show NY P12 Levels".
   - Dynamically render the NY P12 lines alongside the traditional P12 lines using `f_draw_lev()`.
2. **Dynamic Table Labeling**:
   - The stats table currently has hardcoded column names (`Asia Mid`, `Lon Mid`, etc.).
   - **Update**: If the indicator is currently evaluating `tgt_idx == 0` (Asia) or `tgt_idx == 1` (London), dynamically change the column headers to read `Prev Asia`, `Prev Lon`, `Prev NY1`, etc.
3. **Table Expansion**:
   - Insert new columns into `tbl_res` for the NY P12 Hit Rates (H/M/L).
   - The total columns will expand from 16 to 19, requiring adjustments to the `table.new` instantiation and the `f_render_row_adv` column mapping.

## Verification

- Run `python scripts/pine_gen/generate_profiler_pine.py` to seamlessly generate the updated `.pine` indicator and library files.
- Copy/Paste the resulting code into TradingView.
- Compare the NY P12 hit rates and the Prev NY1 Mid hit rates on the Asia Session outcome with the Next.js Web Application to verify 100% parity.
