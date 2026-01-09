# OR Retest Analysis System

## Overview
This system analyzes "First Retest" events after Opening Range (OR) breakouts to identify optimal entry windows and risk profiles.

## Scripts

### 1. `extract_or_retests.py` - ETL Pipeline
Extracts retest events from raw OHLC data.

**Output**: `data/derived/retests/or_retests_{TICKER}.jsonl`

**Key Fields Extracted**:
- `retest_time` - When price returned to OR boundary
- `excursion_mfe_pct` - Maximum favorable excursion (Price %)
- `excursion_mae_pct` - Maximum adverse excursion (Price %)
- `pre_retest_fam_norm` - Displacement before retest (R-multiple)
- `is_failure` - Whether the retest resulted in a stop-out

### 2. `analyze_retest_stats.py` - Report Generator
Generates comprehensive forensic reports with visualizations.

**Usage**:
```powershell
# Full History
python analyze_retest_stats.py

# Date Filtered (In-Sample/Out-of-Sample Testing)
python analyze_retest_stats.py --start 2023-01-01 --end 2023-12-31
```

**Output**: `docs/strategies/9_30_breakout/0930_AllDay/reports/`
- `{TICKER}_Retest_Forensics.md` - Per-ticker detailed report
- `README_Summary.md` - Executive summary across all tickers

## Report Features

### Visualizations (Per Hour)
1. **Time Scatter Plot** (`*_scatter.png`)
   - X-Axis: Minute (0-59)
   - Y-Axis: Price % Change
   - Green dots = Reward (MFE), Red dots = Risk (-MAE)

2. **Win/Loss Distribution** (`*_time.png`)
   - Bidirectional bar chart
   - Green bars (up) = Wins, Red bars (down) = Losses

3. **Price % Histograms** (`*_hist.png`)
   - MAE Distribution: 0-1.5% (0.05% bins)
   - MFE Distribution: 0-3% (0.1% bins)

### Tables
- **Percentile Stats**: Median, p75, p90, Max for Risk/Reward
- **Best 5-Min Windows**: Highest win rate time buckets
- **Worst 5-Min Windows**: Lowest win rate (avoid these)

## Filters Applied
- **Displacement Filter**: Pre-retest displacement > 0.5x OR Height
  - Removes "chop" scenarios where price barely breaks out before returning
- **Date Range**: Optional `--start` and `--end` arguments

## Key Findings (NQ1 Example)
| Hour | Win Rate | Best Window | Avoid |
| :--- | :--- | :--- | :--- |
| 09:00 | 81.2% | 09:55 (90.8%) | 09:45 |
| 10:00 | 85.4% | 10:40 (100%) | 10:35 |
| 11:00 | 84.3% | 11:40 (100%) | 11:20 |
