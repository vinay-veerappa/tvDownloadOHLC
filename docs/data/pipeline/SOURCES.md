# Data Sources Documentation

This document describes the various data sources used by the trading platform and how to import data from each.

> [!TIP]
> For **file locations, date ranges, and data quality issues**, see [../reports/COVERAGE.md](../reports/COVERAGE.md).

## Overview

| Source | Format | Timezone | Conversion Script |
|--------|--------|----------|-------------------|
| TradingView Export | Unix timestamps | UTC | `scripts/convert_all_csv.py` |
| BacktestMarket | Semicolon-delimited | Chicago | `scripts/convert_backtestmarket.py` |
| Selenium Downloader | Unix timestamps | UTC | `scripts/convert_all_csv.py` |
| NinjaTrader Export | Local (Shifted) | Local -> EST | `scripts/data_processing/import_ninjatrader.py` |
| **yfinance (Yahoo Finance)** | Daily/Weekly OHLC | UTC | `stream_chart.py` (automatic) |

---

## TradingView Export (Standard)

**Source**: Direct export from TradingView charts

**File Format**:
- Delimiter: Comma (,)
- Timestamps: Unix (seconds since epoch, UTC)
- Header row present: `time,open,high,low,close,Volume`

**Example**:
```csv
time,open,high,low,close,Volume
1762729200,25320.75,25391.50,25320.75,25351.75,1293
```

**Conversion**: Use `scripts/convert_all_csv.py`

---

## BacktestMarket

**Source**: https://www.backtestmarket.com/

**File Format**:
- Delimiter: **Semicolon (;)**
- Date Format: **DD/MM/YYYY** (European format!)
- Time Format: **HH:MM** (24-hour)
- Timezone: **Chicago (America/Chicago)**
- No header row

> **⚠️ WARNING**: The date format is DD/MM/YYYY, NOT MM/DD/YYYY!
> This means `09/11/2025` is **November 9, 2025**, not September 11!

**Chicago Timezone**:
- CST (Nov-Mar): UTC-6
- CDT (Mar-Nov): UTC-5

**Example**:
```
09/11/2025;18:40;25319.25;25323.75;25315.50;25323.00;150
```

This corresponds to: **November 9, 2025 at 6:40 PM Chicago time** = **November 10, 2025 at 00:40 UTC**

### Conversion Process

1. **Run the conversion script**:
   ```bash
   python scripts/convert_backtestmarket.py data/TV_OHLC/nq-1m_bk.csv data/TV_OHLC/nq-1m_converted.csv --ticker NQ1
   ```

2. **Verify the conversion** by matching OHLC values against TradingView data:
   ```bash
   python scripts/verify_ohlc_match.py
   ```

3. **Load into parquet**:
   ```bash
   python scripts/rebuild_nq1_parquet.py
   ```

### Troubleshooting

**Problem**: Future dates in converted data (e.g., data showing Dec 12 when it's Dec 6)

**Cause**: Date format was parsed incorrectly (MM/DD/YYYY instead of DD/MM/YYYY)

**Solution**: 
1. Check the first few rows of the source file
2. If dates look like `11/12/2008`, this is **December 11, 2008** (DD/MM/YYYY)
3. Use `convert_backtestmarket.py` which handles this correctly

**Problem**: Times don't match after conversion

**Cause**: Timezone offset wasn't applied correctly

**Solution**:
1. Find overlapping data between BacktestMarket and TradingView
2. Match OHLC values to verify correct time offset
3. Chicago time + 5 or 6 hours = UTC (depending on DST)

---

## NinjaTrader Export

**Source**: NinjaTrader 8 "Export Data" feature / MCP Bridge Export (`nt_export_bars`)

**File Format**:
- Delimiter: Comma (,) or Semicolon (;)
- Header: Optional (Auto-detected)
- Timestamp: **PST / Pacific Time (`America/Los_Angeles`)** (Local workstation time) or configured NT8 display timezone

**Key Caveats**:

1.  **Timestamp Shift (Close vs Open Time)**:
    - NinjaTrader exports use **End of Bar** timestamps (e.g., 09:31 for the 09:30-09:31 bar).
    - Our system uses **Start of Bar** (Open Time).
    - **Logic**: The import script automatically **shifts timestamps BACKWARDS** by the bar duration (e.g., -1 minute for 1m bars) to align with TradingView/standard conventions.

2.  **Timezone Conversion**:
    - NinjaTrader exports carry **PST (`America/Los_Angeles`)** workstation local time by default.
    - **Logic**: The script converts PST timestamps to UTC / EST to ensure consistency with our database.

**Import Command**:
```bash
python scripts/data_processing/import_ninjatrader.py <file> <ticker> <interval> --timezone America/Los_Angeles
```
*Use `--align` to verify price alignment against existing data.*

---

## Futures Daily Data (+24h Offset)

Futures daily/weekly data from TradingView uses "session start" timestamps.

**Example**: A daily bar for December 5th trading session has timestamp `2025-12-04 23:00 UTC`

**Conversion**: Add 24 hours to daily timestamps for futures (ES1, NQ1, YM1, RTY1, GC1, CL1)

**Script**: `scripts/merge_daily_with_offset.py`

> **Note**: This offset only applies to **futures** daily/weekly data.
> Stocks/ETFs (QQQ, SPX) do NOT need this adjustment.

---

---

## yfinance (Yahoo Finance) — Futures Daily/Weekly HTF

**Source**: Yahoo Finance via the [`yfinance`](https://pypi.org/project/yfinance/) Python library

**Scope**: Futures **daily and weekly** parquet files only (NQ1, ES1, YM1, RTY1, CL1, GC1).
Intraday (1m, 5m, 15m, 1h, 4h) data is **not** sourced from yfinance.

**Why yfinance instead of Schwab API for daily bars?**

The Schwab quote API's `reference.futureSettlementPrice` and `quote.closePrice` fields reflect the **previous session's official CME settlement**, not the current day's final traded price. This caused an off-by-settlement discrepancy vs Thinkorswim / Yahoo Finance. yfinance was verified to match TOS/Yahoo daily close exactly for all 6 futures symbols over 200 days.

**Symbol Mapping**:

| Schwab symbol | yfinance ticker |
|---|---|
| `/NQ` | `NQ=F` |
| `/ES` | `ES=F` |
| `/YM` | `YM=F` |
| `/RTY` | `RTY=F` |
| `/CL` | `CL=F` |
| `/GC` | `GC=F` |

**Critical date-shift**: yfinance daily bars are timestamped at midnight ET of the **next calendar day** (e.g. the March 12 trading session is stamped `2026-03-13`). `stream_chart.py` corrects this by subtracting 1 calendar day before anchoring to the standard futures trade-date convention (prior calendar day at 18:00 ET = 23:00 UTC index key in the parquet).

**TradingView CSV vs yfinance**: TradingView's continuous futures charts (e.g. `CME_MINI_NQ1!`) apply **back-adjustment at each quarterly roll**, shifting all older bars retroactively to produce a smooth continuous series. yfinance uses the **unadjusted** front-month contract price, matching TOS / Yahoo Finance / broker statements. The parquet files store **unadjusted** prices.

**Toggle**: The data source can be changed via environment variable:
```powershell
# Default (yfinance)
$env:FUTURES_HTF_SOURCE = 'yfinance'

# Revert to Schwab API daily history
$env:FUTURES_HTF_SOURCE = 'schwab'
```
Source switching is implemented in `scripts/streaming/stream_chart.py` via `FUTURES_HTF_SOURCE`.

**Verification**:
```powershell
.\.venv\Scripts\python.exe scripts/validation/verify_futures_htf_parquet.py --days 200
# Single symbol with full row-by-row table:
.\.venv\Scripts\python.exe scripts/validation/verify_futures_htf_parquet.py --symbol NQ1 --verbose
```

Last verified **2026-03-13**: all 6 futures symbols — **200/200 exact matches** between parquet and yfinance.

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `convert_backtestmarket.py` | Convert BacktestMarket CSV to Unix timestamps |
| `convert_all_csv.py` | Convert TradingView CSV exports |
| `merge_daily_with_offset.py` | Merge daily data with +24h offset for futures |
| `rebuild_nq1_parquet.py` | Rebuild NQ1 parquet files from converted CSV |
| `verify_ohlc_match.py` | Verify conversion by matching OHLC values |
| `generate_coverage_report.py` | Generate data coverage report |
| `verify_futures_htf_parquet.py` | Verify futures daily parquet vs yfinance (and TV for NQ) |
