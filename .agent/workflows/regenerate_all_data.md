---
description: Regenerate all derived data (Profiler, HOD/LOD) for all tickers
---

# Regenerate Derived Data

This workflow ensures that all analysis files are up-to-date with the latest market data (Parquet files). Run this if you see 404s or unexpected data in the Profiler.

## 1. Run the Master Regeneration Script

This script automatically handles:
- Upsampling (1m -> 5m, 15m, 1h, 4h)
- Profiler Sessions (`_profiler.json`)
- Levels (`_level_touches.json`)
- **Daily HOD/LOD (`_daily_hod_lod.json`)** (Crucial for scatter plots)
- VWAP

// turbo-all
```bash
python scripts/regenerate_derived.py ES1
python scripts/regenerate_derived.py NQ1
python scripts/regenerate_derived.py CL1
python scripts/regenerate_derived.py GC1
python scripts/regenerate_derived.py RTY1
python scripts/regenerate_derived.py YM1
```

## 2. Verify Output

Ensure the following files exist in `data/` for each ticker:
- `{ticker}_profiler.json`
- `{ticker}_level_touches.json`
- `{ticker}_daily_hod_lod.json`
