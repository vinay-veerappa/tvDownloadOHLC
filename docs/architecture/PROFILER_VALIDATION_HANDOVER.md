# Profiler Validation Framework — Handover Document

## Session Date: 2026-07-17

## What Was Built

A validation framework at `scripts/testing/` that compares profiler statistics computed locally against the precomputed lookup table (`data/derived/{ticker}_profiler_lookup.json`).

### Architecture

```
scripts/testing/
├── run.py                          # CLI entry point
├── README.md                       # Full documentation
├── core/
│   ├── base.py                     # FeatureValidator protocol, ValidationResult
│   ├── filter_engine.py            # Pivot-table filter (replicates WebUI backend)
│   ├── api_client.py               # WebUI HTTP client
│   ├── comparator.py               # Field-by-field comparison
│   └── reporter.py                 # Markdown/JSON/side-by-side output
└── features/
    ├── __init__.py                  # Feature registry
    └── profiler/
        ├── data.py                 # Data loading + constants
        ├── compute.py              # Local stats computation
        ├── api.py                  # WebUI API calls
        └── validator.py            # ProfilerFeatureValidator
```

### CLI Usage

```bash
# Start backend first
start_api.bat

# Single filter side-by-side comparison
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --filter "LF|LF" --detail

# All filters for a session
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters

# JSON output
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters --format json
```

### Filter Key Formats

- **Status-only**: `LF|LF` (Asia=Long False, London=Long False, no broken filter)
- **Full**: `LF|F|LF|F` (Asia=Long False Held, London=Long False Held)

## What's Working ✅

1. **Count**: Matches lookup table (except 17 keys off by 1-5 due to lookup generator skipping first date)
2. **Distribution**: Probabilities match perfectly
3. **Timing (HOD/LOD mode)**: Matches perfectly (range format like `10:30-10:45`)
4. **Broken rates**: Match perfectly
5. **Level hit rates**: Global (all outcomes combined) match the WebUI's `GET /stats/level-touches` endpoint

### Verified Example: `LF|LF` (Asia=LF, London=LF → NY1) — 154 days
- Count: 154 ✅
- Distribution: LT=0.227, LF=0.292, ST=0.136, SF=0.344 ✅
- LT HOD mode: 10:30-10:45 ✅ (matches WebUI)
- LT LOD mode: 05:00-05:15 ✅ (matches WebUI)
- High mode bin: 0.4 ✅, High median bin: 0.8 ✅
- All 15 level hit rates match ✅

## What Needs Fixing ⚠️

### 1. ~~Per-Outcome Level Hit Rates~~ ✅ FIXED

**Issue**: The validator computed **global** level hit rates (all days combined). The WebUI's `DailyLevels` component shows **per-outcome** level hit rates (e.g., only the 35 Long True days).

**Fix applied**:
- Added `_compute_session_level_hits_from_columnar()` to the lookup table generator, computing per-outcome hits for all 20 columnar level keys (including `prev_asia_mid`, `prev_london_mid`, `prev_ny1_mid`, `prev_ny2_mid`, `daily_open`).
- Expanded `HIT_TO_LEVEL` and `HIT_KEYS` in the validator's compute module to include `prev_*` session mids and `daily_open`.
- Added per-outcome level hit comparison section (8g) to the validator.
- Verified against WebUI browser values: Long True (35 days, target=NY1) and Long True (35 days, target=Daily) — all 11 levels match exactly.

### 2. ~~Low Price Distribution Median~~ ✅ RESOLVED (by count fix)

The count fix (including "None" status dates and excluding missing-session dates) resolved the median discrepancy. The LF|LF baseline now shows all 128/128 fields matching.

### 3. ~~High Mode Tie-Breaking~~ ✅ RESOLVED (by count fix)

Same as above — the count fix resolved the mode tie-breaking discrepancy.

### 4. ~~Count Off By 1-5 (17 keys)~~ ✅ FIXED

**Root causes**:
1. The lookup table generator skipped dates where the target session status was "None" (`if target_status not in ALL_STATUSES: continue`). The WebUI backend includes "None" status dates in the count. Fixed to include "None" status.
2. The filter engine included dates where the target session (NY1) was entirely missing (no session record). Fixed to exclude dates where the target session column is NaN in the pivot table.

**Result**: 76/76 NY1 filter combinations now pass (was 59/76).

## Key Files Modified

1. `scripts/libs_py/profiler/generate_profiler_lookup.py` — Removed fallback keys, added status-only keys, changed to use unadjusted data, changed mode/median to use floor-to-bin-start
2. `scripts/testing/` — New validation framework (all files)
3. `data/derived/NQ1_profiler_lookup.json` — Regenerated with new format

## Data Flow (Important)

```
WebUI Frontend:
  useDailyHodLod hook → fetches BOTH:
    - GET /stats/daily-hod-lod/{ticker}?unadjusted=false  (adjusted TIMES)
    - GET /stats/daily-hod-lod/{ticker}?unadjusted=true   (unadjusted PRICES)
  Merges: adjusted times + unadjusted prices

  RangeDistribution component:
    - Uses daily_high/daily_low/daily_open from MERGED data
    - Computes: ((daily_high - daily_open) / daily_open) * 100 (NOT rounded)
    - modeBin: Math.floor(v / 0.1) * 0.1 (floor to bin start)
    - medianBin: sorted[Math.floor(len/2)], then floor to bin start
    - Tie-breaking: JS Object.entries().sort((a,b) => b[1] - a[1]) — insertion order on ties

  DailyLevels component:
    - Uses GET /stats/level-touches/{ticker}
    - Per-level: hits.{targetSession}[dateIdx] !== -1
    - Target session is user-selectable (Asia/London/NY1/NY2/Daily)
    - Hit rate = touched / total * 100

Lookup Table Generator:
    - Uses NQ1_daily_hod_lod_unadjusted.json (unadjusted prices)
    - Uses daily_high/daily_low (not hod_price/lod_price)
    - Does NOT round percentages before binning
    - mode: floor to bin start, tie-break: first alphabetically
    - median: sorted[len//2], floor to bin start
```

## Next Steps

1. ~~**Fix per-outcome level hit rates**~~ ✅ DONE — Added per-outcome level hit computation to the lookup table generator using columnar level touches data. The validator now compares per-outcome level hits for all 20 level keys (including `prev_*` session mids and `daily_open`). Verified against WebUI browser values: all match.

2. ~~**Fix count off-by-1**~~ ✅ DONE — Two root causes found and fixed:
   - The lookup table generator was skipping dates where the target session status was "None". Fixed to include "None" status dates in the sample count (matching WebUI behavior).
   - The filter engine was including dates where the target session (NY1) was entirely missing (no session record). Fixed to exclude dates where the target session column is NaN in the pivot table.
   - Result: **76/76 NY1 filter combinations now pass** (was 59/76).

3. ~~**Verify validator catches mismatches**~~ ✅ DONE — Created `test_validator_detection.py` that deliberately corrupts lookup table values and confirms the validator detects them. All 4 test cases pass (per-outcome level hit, count, price stats).

4. ~~**Fix price distribution data mismatch**~~ ✅ DONE — Root cause: `useDailyHodLod` hook merged adjusted dates with unadjusted prices **by index position**, but the two data files have different date ranges (adjusted starts 2006, unadjusted starts 1999), causing every price to be mapped to the wrong date. Fixed the merge to align by date using a date→index map. Verified: all 35 highPcts and 35 lowPcts values now match exactly between WebUI and local computation.

5. ~~**Fix mode tie-breaking**~~ ✅ DONE — The WebUI's `modeBin` function used `Object.entries().sort((a,b) => b[1] - a[1])` which relies on JS object insertion order for ties — non-deterministic. Fixed to sort by count desc, then bin value asc (numerically first). Applied consistently across all three layers: lookup table generator, validator compute, and WebUI `range-distribution.tsx`. Verified in browser: Low MODE now shows -0.4 to -0.3% (was -0.3 to -0.2%), matching lookup table.

6. ~~**Fix WebUI backend count bug**~~ ✅ DONE — The backend's `apply_filters()` included dates where the target session was missing, causing `count` to be 1 higher than the distribution total. Fixed by adding `mask &= status_pivot[target_session].notna()`.

7. **Extend to other sessions** — Asia, London, NY2.

8. **Extend to other features** — Candle Science, etc.

9. **Regenerate lookup tables for other tickers** — ES1, CL1, etc. now that the generator is fixed.