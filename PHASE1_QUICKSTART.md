<!--
Phase 1 File Inventory & Quickstart

This document lists all Phase 1 files delivered and provides a quick reference
for running the generation and validation scripts.
-->

# Phase 1 Deliverables

## New Files Created

```
scripts/edgeful/lib/
├── __init__.py                      [Module initialization]
├── data_loader.py                   [Unified parquet loading + live fusion]
├── session_tagger.py                [Trading date & session classification]
├── context.py                       [Daily context computation]
├── filters.py                       [Filter dimension declarations]
├── generate_daily_context.py        [Main generation CLI]
├── validate_daily_context.py        [QA validation CLI]
├── smoke_test.py                    [Pre-generation validation]
└── README.md                        [Complete API documentation]
```

## Modified Files

```
.gitignore                           [Added exclusion for daily_context_*.parquet]
```

## Generated Artifacts (after running generate_daily_context.py)

```
data/derived/
├── daily_context_NQ1.parquet        [~1.2 MB]
├── daily_context_ES1.parquet        [~1.2 MB]
├── daily_context_YM1.parquet        [~1.2 MB]
├── daily_context_RTY1.parquet       [~1.2 MB]
├── daily_context_CL1.parquet        [~1.2 MB]
└── daily_context_GC1.parquet        [~1.2 MB]
                                     [Total: ~7.2 MB, not versioned]
```

## Quick Start

### 1. Verify Installation
```bash
cd c:\Users\vinay\tvDownloadOHLC
python scripts/edgeful/lib/smoke_test.py
```

✓ Expected output:
```
Results: 6 passed, 0 failed
✓ All smoke tests passed! Ready for generation.
```

### 2. Test with One Symbol
```bash
python scripts/edgeful/lib/generate_daily_context.py --symbol NQ1
```

✓ Expected output:
```
Generating Daily Context for 1 symbols...
Generating NQ1...
  ✓ NQ1: 1000 trading days → daily_context_NQ1.parquet
Summary: 1 success, 0 failed, 0 skipped
```

### 3. Validate Test Output
```bash
python scripts/edgeful/lib/validate_daily_context.py --symbol NQ1 --checks 10
```

✓ Expected output:
```
Validating Daily Context for 1 symbols...
  NQ1: 1000 rows
    ✓ All checks passed
Summary: 1/1 symbols passed validation
```

### 4. Generate All Symbols (Full Dataset)
```bash
python scripts/edgeful/lib/generate_daily_context.py
```

✓ Expected output:
```
Generating Daily Context for 6 symbols...
Generating CL1...
  ✓ CL1: 1200 trading days → daily_context_CL1.parquet
Generating ES1...
  ✓ ES1: 1200 trading days → daily_context_ES1.parquet
[... etc ...]
Summary: 6 success, 0 failed, 0 skipped
```

Estimated time: 10–15 minutes

### 5. Validate All Output
```bash
python scripts/edgeful/lib/validate_daily_context.py --checks 20
```

✓ Expected output:
```
Validating Daily Context for 6 symbols...
[... spot-checks for each symbol ...]
Summary: 6/6 symbols passed validation
```

## API Quick Reference

### Load Data
```python
from scripts.edgeful.lib.data_loader import DataLoader

loader = DataLoader()
df_1m = loader.load_1m("NQ1")          # 1-minute bars
df_5m = loader.load_5m("NQ1")          # 5-minute bars
df_daily = loader.load_daily("NQ1")    # Daily bars
df_vix = loader.load_vix()             # VIX daily close
```

### Tag Sessions
```python
from scripts.edgeful.lib.session_tagger import tag_session

df_tagged = tag_session(df_1m)
# Adds: trading_date, session, is_rth, day_of_week, minutes_into_session
```

### Build Daily Context
```python
from scripts.edgeful.lib.context import DailyContextBuilder

builder = DailyContextBuilder(loader)
ctx_df = builder.compute_for_symbol("NQ1")
ctx_df.to_parquet("daily_context_NQ1.parquet", index=False)
```

### Query Filters
```python
from scripts.edgeful.lib.filters import UNIVERSAL_FILTERS, get_filter_by_name

vix_filter = get_filter_by_name("vix_regime", UNIVERSAL_FILTERS)
print(vix_filter.values)  # ['LOW', 'NORMAL', 'HIGH', 'EXTREME']

gap_filter = get_filter_by_name("gap_direction", UNIVERSAL_FILTERS)
print(gap_filter.values)  # ['UP', 'DOWN', 'NONE']
```

## CLI Command Reference

### generate_daily_context.py

```bash
# All symbols (default)
python scripts/edgeful/lib/generate_daily_context.py

# Specific symbols
python scripts/edgeful/lib/generate_daily_context.py --symbol NQ1 ES1 YM1

# Force regeneration (overwrite existing)
python scripts/edgeful/lib/generate_daily_context.py --force

# With spot-check validation (future feature)
python scripts/edgeful/lib/generate_daily_context.py --verify 5
```

### validate_daily_context.py

```bash
# All symbols (default, 10 spot-checks each)
python scripts/edgeful/lib/validate_daily_context.py

# Specific symbols
python scripts/edgeful/lib/validate_daily_context.py --symbol NQ1

# More spot-checks
python scripts/edgeful/lib/validate_daily_context.py --checks 50

# With verbose output
python scripts/edgeful/lib/validate_daily_context.py --verbose

# Combine options
python scripts/edgeful/lib/validate_daily_context.py --symbol ES1 RTY1 --checks 20
```

## DailyContext Field Reference

Each row in daily_context.parquet has 46 fields:

### Identity (3)
- `symbol` — NQ1, ES1, YM1, RTY1, CL1, GC1
- `trading_date` — Date (rolled at 18:00 ET)
- `day_of_week` — 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri

### Volatility (4)
- `vix_close` — Prior day VIX close
- `vix_regime` — LOW | NORMAL | HIGH | EXTREME
- `vix_pctile_60d` — 0–100 percentile (60-day lookback)
- `atr_14d` — 14-day average true range (points)

### Levels (5)
- `pdh` — Prior day high
- `pdl` — Prior day low
- `pdc` — Prior day close
- `pd_mid` — (PDH + PDL) / 2
- `pd_range` — PDH - PDL

### Gap Analysis (6)
- `gap_size_points` — Open - Prior close
- `gap_size_pct` — gap_size_points / prior_close as %
- `gap_direction` — UP | DOWN | NONE
- `gap_size_bucket` — NONE | SMALL | MEDIUM | LARGE
- `gap_filled` — Boolean (gap closed during session)
- `gap_fill_time_minutes` — Minutes to fill (-1 if not filled)

### Overnight (3)
- `overnight_high` — High from 16:00 PDC to 09:30 open
- `overnight_low` — Low from 16:00 PDC to 09:30 open
- `midnight_open` — Opening price at 20:00 ET

### Open Location (4)
- `open_vs_pd_range` — ABOVE_PDH | INSIDE | BELOW_PDL
- `open_vs_midnight` — ABOVE | BELOW
- `is_inside_day` — Max of day < PDH and Min of day > PDL
- `is_outside_day` — Max of day > PDH and Min of day < PDL

### Session Outcome (7)
- `session_close` — RTH close price
- `session_direction` — GREEN (close > open) | RED (close < open)
- `pdh_broken` — Boolean (intraday high > PDH)
- `pdl_broken` — Boolean (intraday low < PDL)
- `both_pd_broken` — Boolean (both PDH and PDL touched)
- `pdh_break_time_minutes` — Minutes to PDH break (-1 if not broken)
- `pdl_break_time_minutes` — Minutes to PDL break (-1 if not broken)

### Streaks (2)
- `streak_direction` — GREEN | RED (direction of current streak)
- `streak_length` — Days in streak (1–N)

### Events (4)
- `is_event_day` — Boolean (economic event scheduled)
- `event_type` — Primary event category (first match)
- `event_types` — List of all matching categories
- `is_opex_week` — Boolean (3rd Friday week)

### Weekly Context (4)
- `prior_week_high` — High from prior Friday-Sunday
- `prior_week_low` — Low from prior Friday-Sunday
- `prior_week_close` — Prior Friday close
- `weekly_open` — Monday open

## Event Categories

When `is_event_day = True`, `event_type` is one of:

```
FOMC, NFP, CPI, PPI, OPEX, ECB, BOE, BOJ, PMI, ISM,
GDP, EARNINGS, RETAIL, HOUSING, INCOME, CLAIMS,
CONFERENCE, DURABLE, OIL, ENERGY, RATES
```

## Filter Dimensions Available

### Universal (13)
```
day_of_week, vix_regime, gap_direction, gap_size_bucket,
open_vs_pd_range, is_event_day, is_opex_week, atr_respected,
session_direction, streak_direction, event_type, both_pd_broken,
lookback_days
```

### Macro Module (3)
```
judas_direction, indicator_class, session_group
```

### Range Module (4)
```
range_width_category, first_boundary_broken, close_vs_mid, range_name
```

## Example: Using Daily Context in Downstream Modules

### Macro Module Integration
```python
import pandas as pd

# Load both
ctx = pd.read_parquet("data/derived/daily_context_NQ1.parquet")
macro = pd.read_parquet("data/macro_records.parquet")

# Join on (symbol, trading_date)
merged = macro.merge(ctx, on=["symbol", "trading_date"], how="left")

# Now macro has all DailyContext columns available
print(merged.columns)
# Includes: vix_regime, gap_direction, pdh_broken, event_type, etc.

# Filter by context
high_vix_gap_down = merged[
    (merged.vix_regime.isin(["HIGH", "EXTREME"])) &
    (merged.gap_direction == "DOWN")
]
```

### Range Module Integration
```python
import pandas as pd

# Load context
ctx = pd.read_parquet("data/derived/daily_context_NQ1.parquet")

# Use as universal filter dimension source
vix_regimes = ctx.vix_regime.unique()  # ['LOW', 'NORMAL', 'HIGH', 'EXTREME']
gap_directions = ctx.gap_direction.unique()  # ['UP', 'DOWN', 'NONE']
event_types = ctx.event_type.unique()  # Any event that occurred

# Build dynamic UI filters from these values
```

## Files to Keep in Git

```
✓ scripts/edgeful/lib/__init__.py
✓ scripts/edgeful/lib/data_loader.py
✓ scripts/edgeful/lib/session_tagger.py
✓ scripts/edgeful/lib/context.py
✓ scripts/edgeful/lib/filters.py
✓ scripts/edgeful/lib/generate_daily_context.py
✓ scripts/edgeful/lib/validate_daily_context.py
✓ scripts/edgeful/lib/smoke_test.py
✓ scripts/edgeful/lib/README.md
✓ .gitignore (updated)
```

## Files to Exclude from Git

```
✗ data/derived/daily_context_*.parquet   (already in .gitignore)
```

## Typical Project Structure After Phase 1

```
c:\Users\vinay\tvDownloadOHLC\
├── scripts/edgeful/lib/               ← Phase 1 core (8 files)
│   ├── __init__.py
│   ├── data_loader.py
│   ├── session_tagger.py
│   ├── context.py
│   ├── filters.py
│   ├── generate_daily_context.py
│   ├── validate_daily_context.py
│   ├── smoke_test.py
│   └── README.md
├── data/
│   ├── NQ1_1m.parquet                 ← Raw data (existing)
│   ├── ES1_1m.parquet                 ← Raw data (existing)
│   ├── live/
│   │   ├── live_storage_-NQ.parquet   ← Live data (existing)
│   │   └── ...
│   └── derived/
│       ├── daily_context_NQ1.parquet  ← Generated (not versioned)
│       ├── daily_context_ES1.parquet  ← Generated (not versioned)
│       └── ...
└── docs/                              ← Existing docs
```

## Troubleshooting

**Q: "ModuleNotFoundError: No module named 'scripts.edgeful.lib'"**  
A: Run from repo root:
```bash
cd c:\Users\vinay\tvDownloadOHLC
python scripts/edgeful/lib/smoke_test.py
```

**Q: "FileNotFoundError: data/NQ1_1m.parquet"**  
A: Symbol data missing. Check:
```bash
ls c:\Users\vinay\tvDownloadOHLC\data\NQ*.parquet
```

**Q: Generation hangs or runs very slowly**  
A: First run loads all historical data. Subsequent runs use cache. Check disk space:
```bash
dir /s "data" | find /c ".parquet"  # Count parquet files
```

**Q: Validation finds NaN in critical fields**  
A: Normal for early history (< 14 days for ATR). Inspect:
```python
import pandas as pd
ctx = pd.read_parquet("data/derived/daily_context_NQ1.parquet")
print(ctx[ctx.atr_14d.isna()])  # Show rows with missing ATR
```

## Next Phase (Phase 2)

Phase 2 will:
1. Retrofit macro pipeline to read daily_context
2. Join macro_records with daily_context on (symbol, trading_date)
3. Expose filter dimensions in API/UI
4. Add context to narrative module

Phase 1 library itself requires no changes; it is read-only downstream.

---

For detailed documentation, see: [scripts/edgeful/lib/README.md](scripts/edgeful/lib/README.md)
