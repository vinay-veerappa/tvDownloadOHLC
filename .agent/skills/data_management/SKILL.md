---
name: Data Management
description: Handles the regeneration and maintenance of derived data files (Profiler, Classifications, HOD/LOD).
applyTo: "**/*.py"
---

# Data Management Skill

This skill is used to maintain the derived datasets that empower the Daily Bias reports. These should be run periodically or when significant data gaps are bridged.

## When to use

Use when the user needs to regenerate or maintain derived data files (Profiler, Classification, Indicators) — handles the full data pipeline.

## 🔄 Regeneration Workflows

### 1. Update Daily Classifications
Recalculates R1, R2, DWP, and DNP classifications for all historical data. Use this if you have filled large holes in historical data.

```bash
python scripts/derived/precompute_daily_classification.py --tickers NQ1 ES1
```

### 2. Update Profiler JSON
Refreshes the `ticker_profiler.json` used for backtesting and deep statistical analysis.

```bash
# Full refresh (all history)
python scripts/derived/precompute_profiler.py ALL

# Partial refresh (last 30 days)
python scripts/derived/precompute_profiler.py NQ1 --days 30
```

### 3. Synchronize All Data
A master script or workflow command to update everything at once.

```bash
# Update everything for major tickers
python scripts/derived/precompute_daily_classification.py --tickers NQ1 ES1
python scripts/derived/precompute_profiler.py ALL
```

## 📊 Derived Data Storage
- **Classifications**: `data/derived/TICKER_daily_classification.parquet`
- **Session Profiler**: `data/TICKER_profiler.json`
- **HOD/LOD Times**: `data/TICKER_daily_hod_lod.json`
