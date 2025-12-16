# TradingView OHLC Download

- [x] Locate `download_contract_selenium.py` (Not found) <!-- id: 0 -->
- [x] Review `download_ohlc_selenium_enhanced.py` vs `download_ohlc_selenium.py` <!-- id: 1 -->
- [x] Analyze `download_contracts_selenium.py` <!-- id: 4 -->
- [x] Locate and analyze key rollover CSVs and scripts <!-- id: 8 -->
- [x] Create detailed plan for merging replay logic with rollover boundaries <!-- id: 5 -->
- [x] Implement `download_contracts_replay.py` with rollover boundaries <!-- id: 6 -->
- [x] Verify download loop and boundary logic (Debugging Replay Navigation) <!-- id: 7 -->

# Data Schema & Metrics
- [x] Add `metadata` field to Trade model in `schema.prisma` <!-- id: 16 -->
- [x] Journal Context: Live Economic Calendar <!-- id: 4 -->
    - [x] Implement `fetchLiveCalendar()` with `User-Agent` fix <!-- id: 5 -->
    - [x] Create `EconomicCalendarWidget` (Client Component) <!-- id: 6 -->
    - [x] Implement "Week View" and Sticky Headers <!-- id: 7 -->
    - [x] Implement Server Action `getLiveEconomicEvents` (Proxy) <!-- id: 8 -->
    - [x] Implement Background Sync `syncLiveEvents` <!-- id: 9 -->

- [x] Journal Context: Delayed Market Data (Yahoo Finance) <!-- id: 10 -->
    - [x] Verify existing Yahoo Finance implementation (`web/lib/yahoo-finance.ts`) <!-- id: 11 -->
    - [x] Create Server Action `getMarketQuotes` (Reuse `fetchMarketData`) <!-- id: 12 -->
    - [x] Create `MarketTickerWidget` for dashboard header <!-- id: 13 -->
    - [x] Integrate into `app/journal/context/page.tsx` <!-- id: 14 -->
    - [x] Implement Refreshable News Widget <!-- id: 15 -->
    - [x] Sync Market News to Database <!-- id: 16 -->
        - [x] Add `MarketNews` model to `schema.prisma`
        - [x] Run migration
        - [x] Update `getLatestNews` to sync and return merged data
- [x] Run migration <!-- id: 17 -->
- [ ] Update `BacktestTrade` type to include metadata <!-- id: 18 -->

# Data Management Module
- [x] Document Requirements & Safety Strategy (`docs/DataManagementRequirements.md`) <!-- id: 19 -->
- [x] Create Data Manager UI Skeleton <!-- id: 20 -->
    - [x] Create `app/data/page.tsx` (Dashboard Layout)
    - [x] Add "Data" link to `components/app-sidebar.tsx`
    - [x] Create `DataStatusWidget` (Visual Mockup)
- [x] Implement Read-Only Status Backend <!-- id: 21 -->
    - [x] Create `scripts/check_data_status.py`
    - [x] Wire up `getDataStatus` Server Action
- [x] Implement Safe Data Operations (Planned) <!-- id: 22 -->
    - [x] Implement Backup Utilities (`scripts/data_utils.py`)
    - [x] Implement `yfinance` Updater (`scripts/update_intraday.py`)
    - [x] Wire up Update Action in UI

# Refinements
- [x] Show Complete Data Range in Data Manager <!-- id: 23 -->
    - [x] Update `check_data_status.py` to extraction Min/Max dates
    - [x] Update `DataStatusWidget` to display Start/End columns
    - [x] Segregate Files by Category (Market Data vs Derived)

# Journal Integration
- [x] Implement `exportToJournal` action <!-- id: 13 -->
- [x] Add "Export" UI to Backtest Page <!-- id: 14 -->
- [x] Add "Next/Prev" trade navigation controls <!-- id: 11 -->
- [ ] Verify `scrollToTime` data loading for historical trades <!-- id: 12 -->

# Chart Integration
- [x] Create dedicated `/chart` page (`web/app/chart/page.tsx`) <!-- id: 22 -->
- [x] Add "Open in Chart" button to Backtest Page <!-- id: 19 -->
- [x] Implement `localStorage` marker passing <!-- id: 20 -->
- [x] Update Chart Page to read valid markers <!-- id: 21 -->

# Performance Optimization
- [x] Profile backtest execution (Skipped - assumed Data Loading bottleneck) <!-- id: 23 -->
- [x] Optimize data loading (In-Memory Cache) <!-- id: 24 -->
- [x] Optimize strategy loop logic (Calculations optimized manually) <!-- id: 25 -->

# Trade Visualization
- [x] Update `Trade` model to include TP/SL/MAE/MFE <!-- id: 26 -->
- [x] Implement MAE/MFE calculation in strategy runner <!-- id: 27 -->
- [x] Visualize TP/SL levels on chart (Lines/Box) (Via Markers) <!-- id: 28 -->
- [x] Show MAE/MFE metrics in Trade List/Details <!-- id: 29 -->

# New Indicators
- [x] Implement `OpeningRange` primitive <!-- id: 30 -->
- [x] Integrate `OpeningRange` into `ChartContainer` <!-- id: 31 -->
- [x] Fix "No configurable options" error
- [x] Fix "timeScale undefined" error
- [x] Refine Opening Range Extension Logic
    - [x] Add `extend` (bool) and `extendCount` (number) options
    - [x] Implement robust "End of Session" detection (handle holidays)
    - [x] Update Properties UI for new options
- [x] Implement Measured Moves (Extensions)
    - [x] Add Measured Moves options to RangeDefinition
    - [x] Update Renderer to draw deviation/fixed lines
    - [x] Update Settings UI
- [x] Make Opening Range configurable <!-- id: 32 -->

# NinjaTrader Integration (Historical Data)
- [x] Audit NinjaTrader Export (Format, Timezone, Prices) <!-- id: 33 -->
- [x] Update Import Script (`import_ninjatrader.py`) <!-- id: 34 -->
    - [x] Handle Header/Delimiter detection
    - [x] Implement Timezone Conversion (Central -> Eastern)
    - [x] Implement Timestamp Shift (-1m Close->Open)
    - [x] Implement Price Auto-Alignment (Recent Overlap)
- [x] Verify Import Integrity (Audit Tool) <!-- id: 35 -->
- [x] Execute Import for `ES1` (17 Years) <!-- id: 36 -->
- [x] Regenerate Derived Data (`regenerate_derived.py`) <!-- id: 37 -->
    - [x] Upsample Timeframes (5m, 15m, 1h, 4h)
    - [x] Precompute Sessions
    - [x] Precompute Daily HOD/LOD
    - [x] Precompute Profiler Stats (Fixed via Copy)
    - [x] Precompute Level Touches
    - [x] Update Web Chunks
- [x] Update Web Chunks

# Additional Imports (NinjaTrader)
- [x] Import `CL1` (Crude Oil) <!-- id: 38 -->
    - [x] Audit & Verify
    - [x] Import & Align
    - [x] Regenerate Derived
- [x] Import `GC1` (Gold) <!-- id: 39 -->
    - [x] Audit & Verify
    - [x] Import & Align
    - [x] Regenerate Derived
- [x] Import `RTY1` (Russell 2000) <!-- id: 40 -->
    - [x] Audit & Verify
    - [x] Import & Align
    - [x] Regenerate Derived
- [x] Import `YM1` (Dow Jones) <!-- id: 41 -->
    - [x] Audit & Verify
    - [x] Import & Align
    - [x] Regenerate Derived
# Project Cleanup
- [x] Validate Intermediate Timeframes (5m, 15m, 1h, 4h) <!-- id: 42 -->
- [x] Backup Data to Google Drive (`scripts/backup_to_gdrive.py`) <!-- id: 43 -->
- [x] Check-in Code to GitHub <!-- id: 44 -->

    - [x] Identify Validation Overlap (Checking NT CSV End Dates)
    - [x] Create `scripts/verify_data_quality.py` (Bar-by-bar comparison)
    - [x] Run Verification for `GC1`, `CL1`, `RTY1`, `YM1`, `ES1`
    - [x] Report Discrepancies (Bad Wicks/Candles)
- [/] Re-Import Clean Data Overwrite <!-- id: 46 -->
    - [x] Correct NinjaTrader Import Timezone (Pacific vs Central)
    - [x] Run `scripts/reimport_clean.py` for GC1, CL1, RTY1, YM1
    - [/] Run `scripts/reimport_clean.py` for ES1
- [ ] **Data Quality Issues**
    - [ ] **Investigate Yahoo Finance Auto-Update Reliability** (Random Candles reported)
    - [x] Action: Yahoo Auto-Update Suspended.
- [x] **Verification**
    - [x] **Verify API Endpoints** (GC1, CL1, RTY1, YM1, ES1) - All Passed 200 OK
    - [x] **Git Commit** (Fix YM1/ES1 bugs)
- [x] **Feature: Range-based Stats** (Profiler)
    - Updated `range-distribution.tsx` to display Mode/Median as ranges (e.g. "0.2 to 0.3 %") using floor-based binning.
    - Verified data integrity for RTY1, GC1, CL1 against user reference.
    - Polished UI: Removed Close Dist chart, improved typography, implemented >5% aggregation.
- [x] **Refactor: Price Model Grid**
    - [x] Create `PriceModelGrid` component with 4-session layout.
    - [x] Integrate Grid into Daily Overview (`ProfilerView`).
    - [x] Integrate Grid into Outcome Tabs (`OutcomeDetailView`).
- [x] **Feature: Chart Pop-out**
    - [x] Add Expand button/Dialog to `PriceModelChart`.
    - [x] Add Expand button/Dialog to `RangeDistribution` (High/Low).
    - [x] Add Expand button/Dialog to `HodLodChart`.
    - [x] Add Expand button/Dialog to `DailyLevels`.
    - [x] **Fix Daily Levels Start Times** (Dynamic "Smart" Start Times for P12, Midnight, etc.)
    - [x] **Fix Price Model for "Any" Outcome** (Fixed logic in `profiler_service.py`)
    - [x] **Fix Missing Open Price** (Mapped `price` key from `_profiler.json`)
    - [x] **Fix Missing Web Chunks** (Generated using `convert_to_chunked_json.py`)

# Data Updates
- [/] **Update NQ1 Data** (2008 Gap Fill)
    - [x] Verify existing NQ1 gaps.
    - [ ] Analyze new Ninjatrader export.
    - [/] Verify Timezone & Alignment (Verified: Pacific Time)
    - [x] Merge and update Parquet.
    - [x] Validate gap closure.

- [/] **Data Pre-warming** (Improve API Performance)
    - [/] Regenerate derived data for ES1, YM1, RTY1, GC1, CL1 (Running in background).
- [x] Bug: ES1 Missing Timeframes (1D, 15m, 1h)
    - Fix: Updated `convert_to_chunked_json.py` to write to `web/public/data`. Regenerated.
- [x] Bug: YM1 Timezone Offset (Off by 2 hours)
    - Verification: `verify_ym1_open.py` shows peak volume at 09:30 ET (Correct). Previous shift puts it at 11:30 ET. Confirmed Parquet has 6.4M rows.
- [x] Bug: YM1 SyntaxError (NaN in JSON)
    - Root cause: `convert_to_chunked_json.py` didn't sanitize `NaN` values, resulting in invalid JSON output when YM1 data contained missing values (likely from new import).
    - Fix: Added explicit `dropna` and integer type enforcement for `time` column in conversion script. Regenerated YM1.
