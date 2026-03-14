# Data Pipeline Overview

**Version:** 0.8.0
**Last Updated:** 2026-03-13

This document serves as the guide for acquiring, processing, and storing OHLC market data.

> [!TIP]
> - **Formats & Sources**: See [SOURCES.md](SOURCES.md)
> - **Precomputed/Derived Data**: See [../core/DERIVED.md](../core/DERIVED.md)
> - **Options Database**: See [../core/OPTIONS.md](../core/OPTIONS.md)
> - **Architecture & Timezones**: See [../core/STRATEGY.md](../core/STRATEGY.md)

---

## 1. Supported Data Sources

See [SOURCES.md](SOURCES.md) for detailed specifications.

-   **TradingView Export (Standard)**: CSV, UTC. Handled by `scripts/data_processing/convert/convert_all_csv.py`.
-   **BacktestMarket.com**: Semicolon-delimited, Chicago Time. Handled by `scripts/data_processing/convert/convert_backtestmarket.py`.
-   **yfinance (Yahoo Finance)**: Futures daily/weekly HTF only (NQ1, ES1, YM1, RTY1, CL1, GC1). Pulled automatically by `scripts/streaming/stream_chart.py` on each run. Matches Thinkorswim / Yahoo Finance daily close. See [SOURCES.md](SOURCES.md) for details and the `FUTURES_HTF_SOURCE` toggle.

---

## 2. Current Data Inventory

For a live, automated inventory of all available tickers and timeframes, see:
👉 **[../reports/COVERAGE.md](../reports/COVERAGE.md)**

For known data gaps and anomalies, see:
👉 **[../reports/ANOMALIES.md](../reports/ANOMALIES.md)**
👉 **[../reports/GAPS.md](../reports/GAPS.md)**

---

## 3. Processing Workflow

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
*   **Aggregation:** 1m data is resampled to 5m, 15m, 1h, 4h, 1D.

---

## 4. Scripts Reference

| Category | Task | Script Path | Notes |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Bulk TV CSV Import | `scripts/data_processing/convert/convert_all_csv.py` | Handles standard TV exports. |
|  | NinjaTrader Import | `scripts/data_processing/import_ninjatrader.py` | SOP for historical high-res data. |
| **Processing**| Upsample (1m-4h) | `scripts/data_processing/resample_parquet.py` | Generates intermediate timeframes. |
| **Derived** | **Master Refresh** | `scripts/derived/regenerate_derived.py` | **Main script** to run after any import. |
|  | Daily HOD/LOD | `scripts/derived/precompute_daily_hod_lod.py` | Critical for scatter plots. |
|  | Profiler Stats | `scripts/derived/precompute_profiler.py` | Generates `{ticker}_profiler.json`. |
|  | Level Touches | `scripts/derived/precompute_level_touches.py` | Generates `{ticker}_level_touches.json`. |
|  | Daily Classification | `scripts/derived/precompute_daily_classification.py` | Generates `{ticker}_daily_classification.parquet`. |
|  | Web JSON Chunks | `scripts/data_processing/convert/convert_to_chunked_json.py` | Optimizes data for frontend. |
| **Analysis** | Data Inventory | `scripts/analysis/generate_coverage_report.py` | Updates `reports/COVERAGE.md`. |
|  | Continuity Check | `scripts/analysis/check_data_continuity.py` | Validates no gaps in history. |
| **Validation** | Futures HTF close verification | `scripts/validation/verify_futures_htf_parquet.py` | Compares futures 1d parquet vs yfinance (and TV for NQ) for N days. |

---

## 5. Standard Operating Procedure (SOP)

### 5.1. Historical Import (NinjaTrader)
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

### 5.2. Safety & Backup
- **Backups**: All scripts using `scripts/utils/data_utils.py` automatically create `.bak` files.
- **Display Timezone**: **America/New_York**.
- **Settlement Prices**: Always use Official `1D` TradingView files. Never upsample 1m to 1d.

---

## 6. Scheduled Tasks (Windows Task Scheduler)

### 6.1 RTH Open Metrics (`scripts/market_data/run_rth_open.bat`)
**Schedule:** Daily at 9:30 AM.
Runs `capture_rth_open.py` to calculate RTH expected moves using live straddle prices.

### 6.2 Live EM Update (`scripts/market_data/run_live_update.bat`)
**Schedule:** Daily at 6:00 PM.
Runs `dolt_em_sync.py` and `update_em_history_live.py` to sync expected move history.

### 6.3 Live Data Architecture
See [../core/LIVE_ARCHITECTURE.md](../core/LIVE_ARCHITECTURE.md).
