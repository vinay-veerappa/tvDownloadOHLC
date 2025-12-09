# Data Pipeline Documentation

**Version:** 0.4.0
**Last Updated:** December 09, 2025

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

| Script | Purpose |
| :--- | :--- |
| `scripts/update_data.py` | **Master script**. Orchestrates import -> convert -> update. |
| `scripts/convert_backtestmarket.py` | Handles the specific parsing of BacktestMarket's DD/MM/YYYY + Chicago time format. |
| `scripts/convert_all_csv.py` | Bulk converter for standard simple CSVs. |
| `scripts/merge_daily_with_offset.py` | Adds 24h offset to Futures daily candles (to align session start dates). |
| `scripts/verify_ohlc_match.py` | Validation tool to compare overlapping data between sources. |

## 4. Troubleshooting Data

**Issue:** "Future Dates" in data (e.g., Dec 12 verified when today is Dec 6).
*   **Cause:** Incorrect parsing of BacktestMarket dates (MM/DD/YYYY vs DD/MM/YYYY).
*   **Fix:** Ensure you are using `convert_backtestmarket.py` for these files.

**Issue:** Gaps in data.
*   **Check:** Run `python scripts/check_data_gaps.py` to generate a report (`docs/DATA_GAPS_REPORT.md`).
