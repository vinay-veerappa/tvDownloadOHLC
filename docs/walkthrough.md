# Daily Profiler & Data Integrity Updates

## Objective
Enable Daily Profiler for new tickers (GC1, CL1, RTY1, YM1) and ensure data integrity.

## Key Changes

### 1. Frontend Updates
- Added `GC1`, `CL1`, `RTY1`, `YM1` to `AVAILABLE_TICKERS` in `profiler-view.tsx`.
- Updated `ProfilerFilterSidebar` with descriptive labels for all tickers.

### 2. API & Backend Fixes
- **Fixed 500 Server Error**: `ProfilerService` crashed on `None` open prices due to sparse data. Added safe checks.
- **Fixed 404 Missing Files**: `get_daily_hod_lod` method was missing, causing startup crashes.
- **Timeframes Fix**:
    - **ES1 Blank**: Web chunks (`public/data/ES1`) were actually missing. The previous chunk generation (Fix #3) might have been interrupted or skipped ES1. **UPDATE**: User reported 1D/15m/1h still missing. Found script was writing to `ROOT/public/data` instead of `web/public/data`.
    - **YM1 Gap**: Confirmed via `check_parquet_gap.py` that `YM1_1m.parquet` has ZERO rows for Hour 15. This is a source data import issue, unlike RTY1/ES1 which were stale derived data.
- **Fix**:
    - Ran `convert_to_chunked_json.py` with **corrected path** (`web/public/data`) to generate ALL ES1 timeframes. Verified 15m, 1h, 1d folders now exist.
    -   Ran `reimport_clean.py YM1` with `America/Chicago` source timezone.
        -   Verified Peak Volume is at 09:30 ET (Market Open), correcting the +2 hour shift seen when assuming Pacific Time.
        -   Verified Parquet has 6.4M rows (vs 5.8M old).
        -   Verified HOD/LOD data regenerated.
    -   **Fixed JSON Error**: YM1 chunks contained `NaN`, crashing the chart. Added `dropna` and strict type casting to cleaner script. Regenerated chunks.

### 3. Data Integrity & Timezones
- **NinjaTrader Import Fix**: Identified that imports were shifted by 2-3 hours because script assumed `US/Central` while files were in `Pacific Time`.
    - Updated `scripts/import_ninjatrader.py` to use `America/Los_Angeles`.
- **Clean Re-Import**: ran `reimport_clean.py` for all tickers to regenerate Parquet files with correct timestamps.
- **ES1 Data Cleanup**: Re-imported ES1 to remove corrupt/random candles caused by unreliable Yahoo Finance updates.

### 4. Workflow Enhancements
- Created `.agent/workflows/regenerate_all_data.md` for consistent data regeneration.
- Updated `docs/DataManagementRequirements.md` with Yahoo Finance Warning and Derived Data workflow.

### 5. Bug Fixes (Final Review)
- **API: No Data in Price Model**: Fixed logic to handle "Any" outcome and "missing open price" in `profiler_service.py`.
- **UI: React Render Error**: Fixed "Rendered fewer hooks" crash in `ProfilerView` by fixing hook order.
- **Chart: Data Not Found**: Generated missing web chunks for `GC1`, `ES1`, etc., and fixed generation script path.

## Verification
- **API**: All endpoints (`/stats/filtered-price-model`, `/stats/daily-hod-lod`) tested and working.
- **Data**: New data files verified in `data/` directory with correct sizes and timestamps.
- **Backup**: Full data backup executed to Google Drive.

### 6. Feature Validation: Range-based Stats & Outlier Handling
- **Objective**: Match "Intraday Path" statistics from Reference JSON vs actual Volatility.
- **Verification**:
    -   Verified that "Daily Low Median" for RTY1 (-0.7%) matches the Reference Image exactly.
    -   Confirmed that the "Close Distribution" (Path) was effectively 0.0% and not the target metric.
- **Implementation**:
    -   Updated `range-distribution.tsx` to display stats as **Ranges** (e.g. "0.3 to 0.4 %").
    -   Implemented **Outlier Aggregation**: Values > 5% are clamped and labeled as `> 5 %`.
    -   Polished UI: Removed Close Distribution chart, improved typography (tabular numbers).
### 7. Modularization: Price Model Grid
- **Objective**: Break down "Price Models" into individual session charts (Asia, London, NY1, NY2) for clearer analysis, while retaining the Daily aggregate. Modularize for reuse.
- **Implementation**:
    -   Created `PriceModelGrid` component (2x2 responsive grid).
    -   Added Grid to `ProfilerView` (Daily Overview) to show both Aggregate and Breakdown.
    -   Replaced single chart in `OutcomeDetailView` with Grid. **Benefit**: Outcomes (e.g., "Asia Long") now visually show their impact flow across subsequent sessions (London -> NY1) in the same view.
### 8. UX Refinement: Smart Start Times
- **Objective**: Remove empty "dead space" on charts where the level (e.g., Midnight Open) hasn't started yet relative to the Daily session.
- **Implementation**:
    -   Updated `DailyLevels` X-axis logic.
    -   If a level starts *after* the session start (e.g., "Midnight Open" starts at 00:00, but "Daily" session starts at 18:00 prev day), the chart now dynamically starts at 00:00 instead of 18:00.
    -   Applied to: P12, Midnight, 07:30 Open, and Session Mids.

### 9. Data Integrity: NQ1 2008 Gap Fill & Standardization
- **Objective**: Fill the large data gap in NQ1 (Jan-Dec 2008) and standardize the import process for future updates.
- **Implementation**:
    -   **Gap Fill**: Imported `NQ Monday 1755.csv` (NinjaTrader export) covering 2008-2025.
    -   **Verification**: Confirmed new data aligns perfectly with existing 2025 data when interpretation is **Pacific Time** with a **-1 minute shift** (Close->Open).
    -   **Standardization**:
        -   Refactored verification logic into reusable scripts: `scripts/verify_import_alignment.py` and `scripts/check_data_continuity.py`.
        -   Documented a rigorous **Standard Operating Procedure (SOP)** in `docs/DataManagementRequirements.md` for all future imports.
    -   **Regeneration**: Fully regenerated all derived data (Profiler, Levels, HOD/LOD) for NQ1.

### 10. Performance Optimization: Pre-warming Derived Data
- **Objective**: Improve API response times by pre-computing expensive derived datasets for all supported tickers.
- **Implementation**:
    -   **Optimized Regeneration Script**: Modified `regenerate_derived.py` to target specific tickers for web chunking, avoiding redundant global processing (5x speedup).
    -   **Batch Execution**: Triggered full regeneration for ES1, YM1, RTY1, GC1, and CL1 to ensure all caches (Profiler, HOD/LOD, Levels) are fresh and ready for instant API delivery.

### 11. Feature: Profiler Clipboard Export
- **Objective**: Allow users to instantly copy complex profiler statistics in a standardized pipe-delimited format for use in external tools (e.g., TradingView indicators).
- **Format**: `Session|Direction|Stats|LOD Time Mode|HOD Time Mode|LOD Dist|HOD Dist|P12 High|P12 Mid|P12 Low|Asia Mid|London Mid|Captured At`.
- **Implementation**:
    -   Created `web/lib/profiler-export.ts` utility to handle complex formatting (Mode-to-Median ranges, Time Mode Buckets).
    -   **Bulk Export**: Added "Copy All Outcomes" button to `SessionAnalysisView` to capture Long/Short True/False stats in one click.
    -   **Single Export**: Added "Copy Export String" button to individual `OutcomeDetailView`.
    -   **Logic**: Implemented rigorous date-subset filtering to ensure Level Probabilities (P12) reflect only the days matching the specific outcome.

## 12. NQ1 December Data Fix (NinjaTrader)
-   **Issue**: December 2025 data was corrupt/missing due to Yahoo import issues.
-   **Fix**: Imported `data/NinjaTrader/NQ Monday 1755.csv` with:
    -   Timezone: `America/Los_Angeles` (Source) -> `America/New_York` (Target).
    -   Bar Shift: -1 minute (Close timestamps adjusted to Open timestamps).
-   **Verification**:
    -   Regenerated all derived data (5m, 15m, 1h, 4h).
    -   Recomputed Profiler statistics and Level Touches.
    -   **Update**: Fixed silent data loss in Web Chunks. The import script failed to populate the `time` column (Unix timestamp) for new rows.
    -   **Fix**: Backfilled `time` from Index and re-ran chunk generation. Dec 2025 data now visible.
