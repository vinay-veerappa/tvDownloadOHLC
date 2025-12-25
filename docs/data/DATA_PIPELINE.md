# Data Pipeline Documentation

**Version:** 0.5.0
**Last Updated:** December 25, 2025

This document serves as the Single Source of Truth for acquiring, processing, and storing OHLC market data.

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

## 1.1 Timezone Strategy (Critical)

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

## 4. Troubleshooting Data

**Issue:** "Future Dates" in data (e.g., Dec 12 verified when today is Dec 6).
*   **Cause:** Incorrect parsing of BacktestMarket dates (MM/DD/YYYY vs DD/MM/YYYY).
*   **Fix:** Ensure you are using `convert_backtestmarket.py` for these files.

**Issue:** Gaps in data.
*   **Check:** Run `python scripts/check_data_gaps.py` to generate a report (`docs/DATA_GAPS_REPORT.md`).
