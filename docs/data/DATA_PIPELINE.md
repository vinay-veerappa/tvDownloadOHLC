# Data Pipeline Documentation

**Version:** 0.6.0
**Last Updated:** December 26, 2025

This document serves as the Single Source of Truth for acquiring, processing, and storing OHLC market data.

> [!TIP]
> For **detailed format specifications and conversion procedures**, see [DATA_SOURCES.md](DATA_SOURCES.md).
> For **precomputed/derived data files** (profiler, HOD/LOD, VWAP, etc.), see [DERIVED_DATA.md](DERIVED_DATA.md).
> For **Dolt options database, SQL queries, and scheduled tasks**, see [OPTIONS_DATABASE.md](OPTIONS_DATABASE.md).

---

## 1. Supported Data Sources

We support two primary sources, each with specific "quirks" handled by our scripts.

### Source A: TradingView Export (Standard)
*   **Origin:** Standard CSV export from TradingView chart interface.
*   **Format:** Comma-delimited (`,`).
*   **Timezone:** UTC (Unix timestamps).
*   **Quirk:** Standard format, easiest to work with.
*   **Handling Script:** `scripts/convert_all_csv.py`

### Source B: BacktestMarket.com
*   **Origin:** Purchased historical data.
*   **Format:** Semicolon-delimited (`;`).
*   **Timezone:** **Chicago** (America/Chicago).
*   **Quirks:**
    *   Date Format is **DD/MM/YYYY** (European). Warning: `09/11/2025` is Nov 9th, not Sep 11th.
    *   No header row.
*   **Handling Script:** `scripts/convert_backtestmarket.py`
    *   *Logic:* identifying these files automatically or manual selection required.

---

## 1.1 Source File Locations & Inventory

This section provides a detailed inventory of all raw source data files and their date ranges.

### NinjaTrader Exports (`data/NinjaTrader/`)

High-resolution 1-minute futures data exported from NinjaTrader.

| Folder | Ticker | Start Date | End Date | Format | Notes |
|:---|:---|:---|:---|:---|:---|
| `15Dec2025/` | ES | 2008-01-02 | 2025-12-15 | Comma, Chicago TZ | Includes up/down volume |
| `15Dec2025/` | NQ | 2008-01-02 | 2025-12-15 | Comma, Chicago TZ | Includes up/down volume |
| `15Dec2025/` | CL | 2008-07-20 | 2025-12-15 | Comma, Chicago TZ | Crude Oil futures |
| `15Dec2025/` | GC | 2008-01-13 | 2025-12-15 | Comma, Chicago TZ | Gold futures |
| `15Dec2025/` | RTY | 2017-07-09 | 2025-12-15 | Comma, Chicago TZ | Russell 2000 Micro/Mini |
| `15Dec2025/` | YM | 2008-01-01 | 2025-12-15 | Comma, Chicago TZ | Dow Jones futures |
| `24Dec2025/` | ES | 2008-01-02 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | NQ | 2008-01-02 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | CL | 2008-07-20 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | GC | 2008-01-13 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | RTY | 2017-07-09 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | YM | 2008-01-01 | 2025-12-24 | Comma, Chicago TZ | **Latest** - extends 15Dec |
| `24Dec2025/` | TICKQ | 2011-01-10 | 2025-12-24 | Comma, Chicago TZ | NASDAQ Tick index |

> [!IMPORTANT]
> **Duplicate Analysis:** The `24Dec2025/` folder supersedes `15Dec2025/`. Use `24Dec2025/` files as the canonical source. The `15Dec2025/` folder can be archived.

### TradingView Exports (`data/TV_OHLC/`)

CSV files exported via TradingView UI or Selenium downloader.

| Subfolder | Contents | Notes |
|:---|:---|:---|
| `SPY_QQQ/` | SPY & QQQ 5m, 15m, 1D, 1W chunks | Multiple overlapping files with hash suffixes (TV export quirk) |
| `VIX/` | VIX & VVIX daily/weekly + 1 NinjaTrader VIX export | Mixed sources |
| `downloads_CL1/` | CL1 1m, 5m, 15m history/gap chunks | Auto-downloaded by Selenium script, Dec 2025 |
| `NQ Full_backtestmarket/` | NQ 1m BacktestMarket data | **Semicolon delim, DD/MM/YYYY, Chicago TZ** |
| `SP500_tickData/` | Tick-level SPX data | Legacy/unused |
| `New folder/` | Empty or temp | Can be deleted |

#### BacktestMarket NQ Details
*   **File:** `nq-1m_bk.csv` (373 MB)
*   **Date Range:** 2008-11-12 to 2025-11-27
*   **Format:** Semicolon delimiter, DD/MM/YYYY (European), Chicago timezone
*   **Status:** Superseded by NinjaTrader NQ which has earlier start date and later end date

### Options & Expected Moves (`data/options/`)

| Path | Contents | Date Range | Notes |
|:---|:---|:---|:---|
| `historical_iv.csv` | IV/HV for major tickers (AAPL, AMD, AMZN, etc.) | 2023-01-02 to 2025-12-17 | Scraped data |
| `options/.dolt/` | Dolt database (live git-like DB) | 2019-02-09 to present | Connect via `dolt sql` |
| `options/doltdump/option_chain.csv` | Full option chain dump (~8.4 GB) | 2019-02-09 to ~Dec 2025 | All strikes, all expirations |
| `options/doltdump/volatility_history.csv` | IV/HV history for all symbols (~190 MB) | 2019-02-09 to 2025-12-17 | Has yearly high/low dates |

### Journal & Calendar Data (`data/journal/`)

| File | Contents | Date Range | Notes |
|:---|:---|:---|:---|
| `economic_calendar.csv` | Economic events with dates, impact, times | 2000-01-03 to 2025-12-31 | ISM, FOMC, Jobs, etc. |
| `vix_vvix_daily.csv` | VIX/VVIX daily history | Historical | Merged into Prisma |

### Schwab API Live Data (`data/live_storage_*.parquet`)

1-minute OHLC data streamed from Schwab Trader API.

| File | Ticker | Date Range | Bars | Notes |
|:---|:---|:---|:---|:---|
| `live_storage_-ES.parquet` | ES (futures) | 2025-12-18 → 2025-12-24 | 2,551 | 1m bars |
| `live_storage_-NQ.parquet` | NQ (futures) | 2025-12-18 → 2025-12-24 | 2,550 | 1m bars |
| `live_storage_NVDA.parquet` | NVDA | 2025-12-17 → 2025-12-24 | 2,022 | 1m bars |
| `live_storage_QQQ.parquet` | QQQ | 2025-12-18 → 2025-12-24 | 1,431 | 1m bars |
| `live_storage_SPY.parquet` | SPY | 2025-12-18 → 2025-12-24 | 1,467 | 1m bars |
| `live_storage_GOOG.parquet` | GOOG | 2025-12-17 → 2025-12-18 | 461 | 1m bars |
| `live_storage_RIVN.parquet` | RIVN | 2025-12-17 → 2025-12-18 | 475 | 1m bars |
| `live_storage.parquet` | (mixed) | 2025-12-17 → 2025-12-18 | 156 | Initial test |

> [!NOTE]
> **Prisma Migration:** Economic calendar data has been migrated to the Prisma SQLite database at `web/prisma/dev.db`. The `EconomicEvent` model stores this data for use by the web application. The CSV remains as a backup/source file.

### Data Quality Summary

This section consolidates findings from the detailed [DATA_ANOMALY_REPORT.md](DATA_ANOMALY_REPORT.md) and [DATA_GAPS_REPORT.md](../reports/DATA_GAPS_REPORT.md).

#### Price Anomalies (Large Single-Bar Moves)

| Ticker | Total Rows | Threshold | Anomalies | Status | Notes |
|:---|:---|:---|:---|:---|:---|
| ES1 | 6,214,524 | >80pt | 11 | ✅ Imported | April 2025 volatility |
| NQ1 | 5,895,490 | >200pt | 25 | ✅ Imported | April 2025 volatility |
| YM1 | 5,886,390 | >80pt | 2,477 | ⚠️ Normal | Smaller point range |
| RTY1 | 2,768,519 | >80pt | 1 | ✅ Clean | |
| GC1 | 6,153,069 | >80pt | 1 | ✅ Clean | |
| CL1 | 6,004,895 | >80pt | 0 | ✅ Clean | |

> [!TIP]
> Most anomalies are concentrated in **April 2025** (known market volatility) and at **session boundaries** (17:00, 18:00, 23:00 gaps). See [DATA_ANOMALY_REPORT.md](DATA_ANOMALY_REPORT.md) for specific dates to spot-check.

#### Time Gaps

Most gaps are **expected** (weekends, holidays). Notable exceptions:

| Ticker | Issue | Details |
|:---|:---|:---|
| ES1 1D | 9/11 gap | 2001-09-10 → 2001-09-16 (6 days) |
| CL1 1D | 9/11 gap | 2001-09-06 → 2001-09-16 (10 days) |
| All | Holiday gaps | Christmas, New Year's, Good Friday (3-5 days) |

#### Volume Issues

| Ticker | Timeframe | Issue | Notes |
|:---|:---|:---|:---|
| ES1, NQ1 | 1h | NaN volume | 17,260 bars in ES1 1h (pre-2024 data) |
| CL1, GC1, YM1, RTY1 | 1D, 4h, 1h | Zero volume | Expected - resampled from 1m without volume aggregation |
| QQQ, SPX | 4h | Zero volume | TradingView export quirk |

> [!WARNING]
> **Zero Volume on Daily/4h bars**: This is a known artifact of TradingView OHLC exports for aggregated timeframes. Volume is reliable only on 1m data.

---

## 1.2 Timezone Strategy (Critical)

We strictly adhere to a **"Store as UTC, Consume as NY"** architecture.

### Storage Layer (Parquet)
*   **Format:** Naive UTC (Implicit).
*   **Data:** Timestamps are stored as Unix Seconds or Naive Datetime objects representing UTC.
*   **Rule:** Parquet files must **NEVER** contain timezone-aware objects (e.g. `America/New_York`). They must be clean UTC.

### Consumption Layer (Scripts/App)
*   **Input:** Scripts read Naive UTC Parquet.
*   **Conversion:** Immediately localize to `UTC` then convert to `America/New_York` (Target Trading Timezone).
*   **Logic:** All trading logic (Session definitions, HOD/LOD, Day Breaks) operates on the converted **NY Time**.
*   **Output:** Derived JSONs/APIs typically return **NY-based** labels (e.g. "09:30") or explicit Unix timestamps, but logically aligned to NY trading days.

---

## 2. Processing Workflow

### Step 1: Download / Import
*   **Automated:** Run `selenium_downloader/download_ohlc_selenium_enhanced.py` to fetch from TradingView.
*   **Manual:** Place CSV files into `data/imports/`.

### Step 2: Standardization (Stitching)
Run the stitching script to merge new chunks with existing history and fix timezones.
```powershell
python scripts/update_data.py
```
*   **Under the hood:**
    *   Detects file format (TV vs BacktestMarket).
    *   Converts all to UTC Unix Timestamps.
    *   Sorts and removes duplicates.
    *   Saves to `data/processed/<TICKER>_1m.csv`.

### Step 3: Parquet Conversion
For high-performance API access, we convert CSVs to Parquet and pre-aggregate timeframes.
```powershell
python data_processing/convert_to_parquet.py --ticker ES1!
```
*   **Outputs:** `data/parquet/ES1_1m.parquet`, `ES1_5m.parquet`, `ES1_1h.parquet`, etc.
*   **Aggregation:** 1m data is resampled to 5m, 15m, 1h, 4h, 1D to speed up chart loading.

---

## 3. Scripts Reference

This table provides a Single Source of Truth for all data operations. Use full paths to avoid confusion.

| Category | Task | Script Path | Notes |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Bulk TV CSV Import | `scripts/data_processing/convert_all_csv.py` | Handles standard TV exports recursively. |
|  | NinjaTrader Import | `scripts/data_processing/import_ninjatrader.py` | SOP for historical high-res data. |
|  | Intraday Update (YF) | `scripts/market_data/update_intraday.py` | **Suspended** (Dec 2025) in favor of NinjaTrader. |
| **Processing**| Upsample (1m-4h) | `scripts/data_processing/resample_parquet.py` | Generates intermediate timeframes. |
| **Derived** | **Master Refresh** | `scripts/derived/regenerate_derived.py` | **Main script** to run after any import. |
|  | Daily HOD/LOD | `scripts/derived/precompute_daily_hod_lod.py` | Critical for scatter plots. |
|  | Profiler Stats | `scripts/derived/precompute_profiler.py` | Generates `{ticker}_profiler.json`. |
|  | Level Touches | `scripts/derived/precompute_level_touches.py` | Generates `{ticker}_level_touches.json`. |
|  | Web JSON Chunks | `scripts/data_processing/convert_to_chunked_json.py` | Optimizes data for frontend. |
| **Analysis** | Data Inventory | `scripts/analysis/generate_coverage_report.py` | Updates `DATA_COVERAGE_REPORT.md`. |
|  | Continuity Check | `scripts/analysis/check_data_continuity.py` | Validates no gaps in history. |

---

## 4. Standard Operating Procedure (SOP)

### 4.1. Historical Import (NinjaTrader)
1. **Alignment**: Verify new CSV matches existing data ends.
   ```powershell
   python scripts/verify_import_alignment.py "path/to/ES.csv" ES1
   ```
2. **Execute Import**: Handle timezone shifts and merging.
   ```powershell
   python scripts/data_processing/import_ninjatrader.py "path/to/ES.csv" ES1 1m
   ```
3. **Regenerate Derived**: This is MANDATORY after import.
   ```powershell
   python scripts/derived/regenerate_derived.py ES1
   ```

### 4.2. Safety & Backup
- **Backups**: All scripts using `scripts/utils/data_utils.py` automatically create `.bak` files.
- **Display Timezone**: **EST (America/New_York)** is our standard.
- **Settlement Prices**: Always use Official `1D` TradingView files. Never upsample 1m to 1d.

## 5. Troubleshooting Data

**Issue:** "Future Dates" in data (e.g., Dec 12 verified when today is Dec 6).
*   **Cause:** Incorrect parsing of BacktestMarket dates (MM/DD/YYYY vs DD/MM/YYYY).
*   **Fix:** Ensure you are using `convert_backtestmarket.py` for these files.

**Issue:** Gaps in data.
*   **Check:** Run `python scripts/check_data_gaps.py` to generate a report (`docs/DATA_GAPS_REPORT.md`).

## 6. Scheduled Tasks (Windows Task Scheduler)

The following batch files are scheduled to run automatically for data updates:

### 6.1 RTH Open Metrics (`scripts/market_data/run_rth_open.bat`)

**Purpose:** Capture expected move calculations at RTH open (9:30 AM ET)
**Schedule:** Daily at 9:35 AM (after market open)

**What it does:**
1. Runs `capture_rth_open.py`
2. Fetches current straddle prices from Schwab API
3. Gets VIX value
4. Calculates and stores RTH expected move in `RthExpectedMove` table

```batch
@echo off
cd /d "C:\Users\vinay\tvDownloadOHLC"
python scripts/market_data/capture_rth_open.py
```

### 6.2 Live EM Update (`scripts/market_data/run_live_update.bat`)

**Purpose:** Synchronize expected move history from Dolt and Schwab
**Schedule:** Daily at 6:00 PM (after market close)

**What it does:**
1. **Step 1:** Runs `dolt_em_sync.py`
   - Pulls latest data from DoltHub
   - Queries option chain for straddles
   - Updates `ExpectedMoveHistory` table in Prisma
2. **Step 2:** Runs `update_em_history_live.py`
   - Fetches today's live data from Schwab
   - Updates straddle prices for current day

```batch
@echo off
cd /d "C:\Users\vinay\tvDownloadOHLC"
call python scripts/market_data/dolt_em_sync.py
call python scripts/market_data/update_em_history_live.py
```

