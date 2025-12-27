# Scripts Documentation

This document provides an overview of all scripts organized by folder.

---

## Folder Structure

| Folder | Purpose | Key Scripts |
|:---|:---|:---|
| `analysis/` | Data analysis, charts, reports | `generate_coverage_report.py`, `mae_mfe_analyzer.py` |
| `backtest/` | Strategy backtesting | `backtest_engine.py`, `9_30_breakout/` |
| `data_processing/` | Data import, conversion, cleanup | `import_ninjatrader.py`, `convert_all_csv.py` |
| `debug/` | Debugging and diagnostics | `diagnose_data.py`, `check_*.py` |
| `derived/` | Precompute derived data | `regenerate_derived.py`, `precompute_profiler.py` |
| `maintenance/` | Backups, merges, repairs | `backup-to-drive.ps1`, `merge_all_tickers.py` |
| `market_data/` | Live data updates, EM sync | `run_rth_open.bat`, `dolt_em_sync.py` |
| `streaming/` | Schwab API streaming | `schwab_streamer.py` |
| `validation/` | Data validation and audits | `verify_*.py`, `audit_*.py` |
| `utils/` | Shared utilities | `data_utils.py` |

---

## Key Scripts by Task

### Data Import & Processing

| Script | Location | Purpose |
|:---|:---|:---|
| `import_ninjatrader.py` | `data_processing/` | Import NinjaTrader CSV exports |
| `convert_all_csv.py` | `data_processing/` | Convert TradingView CSVs to parquet |
| `convert_backtestmarket.py` | `data_processing/` | Convert BacktestMarket format |
| `resample_parquet.py` | `data_processing/` | Upsample 1m to 5m/15m/1h/4h |

### Derived Data Generation

| Script | Location | Purpose |
|:---|:---|:---|
| `regenerate_derived.py` | `derived/` | Master script - regenerates all derived data |
| `precompute_profiler.py` | `derived/` | Generate profiler JSON |
| `precompute_daily_hod_lod.py` | `derived/` | Generate daily HOD/LOD JSON |
| `precompute_level_touches.py` | `derived/` | Generate level touches JSON |
| `precompute_vwap.py` | `derived/` | Generate VWAP parquet |

### Backtesting

| Script | Location | Purpose |
|:---|:---|:---|
| `backtest_engine.py` | `backtest/` | Core Python backtest engine |
| `enhanced_backtest_engine.py` | `backtest/` | Enhanced version with more features |
| `full-scale-backtest.ts` | `backtest/` | TypeScript 10-year backtest runner |
| `verify_930_strategy.py` | `backtest/9_30_breakout/` | 9:30 strategy verification |

### Market Data Updates

| Script | Location | Purpose |
|:---|:---|:---|
| `run_rth_open.bat` | `market_data/` | Capture RTH open metrics (scheduled) |
| `run_live_update.bat` | `market_data/` | Sync Dolt + Schwab EM data (scheduled) |
| `dolt_em_sync.py` | `market_data/` | Sync expected moves from Dolt |
| `update_em_history_live.py` | `market_data/` | Update EM from Schwab API |

### Analysis & Reports

| Script | Location | Purpose |
|:---|:---|:---|
| `generate_coverage_report.py` | `analysis/` | Update DATA_COVERAGE_REPORT.md |
| `check_data_gaps.py` | `analysis/` | Generate DATA_GAPS_REPORT.md |
| `mae_mfe_analyzer.py` | `analysis/` | Analyze trade MAE/MFE |
| `generate_bias_charts.py` | `analysis/` | Generate ICT bias charts |

### Validation & Debugging

| Script | Location | Purpose |
|:---|:---|:---|
| `verify_import_alignment.py` | `validation/` | Check import alignment |
| `diagnose_data.py` | `debug/` | Diagnose data issues |
| `check_parquet_duplicates.py` | `debug/` | Find duplicate rows |
| `inspect_parquet.py` | `debug/` | Inspect parquet file contents |

---

## Common Workflows

### After Data Import
```powershell
# 1. Import new data
python scripts/data_processing/import_ninjatrader.py "path/to/file.csv" ES1 1m

# 2. Regenerate all derived data
python scripts/derived/regenerate_derived.py ES1

# 3. Update coverage report
python scripts/analysis/generate_coverage_report.py
```

### Daily Market Data Updates (Automated)
These run via Windows Task Scheduler:
- **9:35 AM**: `scripts/market_data/run_rth_open.bat`
- **6:00 PM**: `scripts/market_data/run_live_update.bat`

### Debugging Data Issues
```powershell
# Check for gaps
python scripts/analysis/check_data_gaps.py ES1

# Diagnose specific issues
python scripts/debug/diagnose_data.py ES1

# Inspect parquet structure
python scripts/debug/inspect_parquet.py data/ES1_1m.parquet
```
