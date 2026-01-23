# Data Processing Instructions

After downloading the raw CSV data from TradingView, you need to process it to make it usable for the chart. This involves two steps: **Stitching** (combining all CSVs) and **Converting** (creating Parquet files for different timeframes).

## 1. Stitching & Validating

This script takes all the individual CSV files in your `data/downloads_<TICKER>` folder, combines them into one continuous file, removes duplicates, and sorts them by time.

**Script:** `data_processing/stitch_and_validate.py`

### CLI Arguments

| Argument | Description |
| :--- | :--- |
| `--ticker` | The ticker symbol to process (e.g., `ES1!`, `NQ1!`). |

### Examples

**For ES (S&P 500 Futures):**
```powershell
cd data_processing
python stitch_and_validate.py --ticker ES1!
```

**For NQ (Nasdaq 100 Futures):**
```powershell
cd data_processing
python stitch_and_validate.py --ticker NQ1!
```

**Output:**
*   Generates `data/ES1_1m_continuous.csv` (or `NQ1_1m_continuous.csv`).
*   Prints the total number of rows and the date range found.

---

## 2. Converting to Parquet

This script takes the "continuous" CSV file generated in step 1, converts it to the highly efficient Parquet format, and automatically creates aggregated timeframes (5m, 15m, 1h, 4h, 1D). It also merges in any legacy historical data if available.

**Script:** `data_processing/convert_to_parquet.py`

### CLI Arguments

| Argument | Description |
| :--- | :--- |
| `--ticker` | The ticker symbol to convert (e.g., `ES1!`, `NQ1!`). |

### Examples

**For ES:**
```powershell
cd data_processing
python convert_to_parquet.py --ticker ES1!
```

**For NQ:**
```powershell
cd data_processing
python convert_to_parquet.py --ticker NQ1!
```

**Output:**
*   Generates `data/ES1_1m.parquet`
*   Generates `data/ES1_5m.parquet`
*   Generates `data/ES1_15m.parquet`
*   Generates `data/ES1_1h.parquet`
*   Generates `data/ES1_4h.parquet`
*   Generates `data/ES1_1D.parquet`
*   (And similarly for NQ1)

# 3. Automated Update (Schwab API)

For a fully automated workflow that bridges gaps without manual CSV exports, use the Schwab API update script.

**Script:** `scripts/market_data/update_via_schwab.py`

### Examples

**Update everything:**
```powershell
python update_via_schwab.py --all
```

**Update specific ticker (1m):**
```powershell
python update_via_schwab.py NQ --tf 1m
```

---

## 🔄 Complete Workflow Example

Here is the full sequence of commands to update everything for **ES1!**:

```powershell
# OPTION A: Automated (Schwab API)
python scripts/market_data/update_via_schwab.py ES

# OPTION B: Manual (TradingView Selenium)
# 1. Download Data (from selenium_downloader folder)
cd selenium_downloader
python download_ohlc_selenium_enhanced.py --ticker ES1! --check-gap

# 2. Process Data (from data_processing folder)
cd ../data_processing
python stitch_and_validate.py --ticker ES1!
python convert_to_parquet.py --ticker ES1!

# 3. Run Web App (from web folder)
cd ../web
npm run dev
```
