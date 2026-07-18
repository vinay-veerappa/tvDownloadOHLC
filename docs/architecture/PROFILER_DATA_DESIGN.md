# Profiler Data Design

**Version:** 1.3.0  
**Last Updated:** July 17, 2026

## 1. Overview

The Profiler system analyzes market sessions (Asia, London, NY1, NY2) to provide statistical insights for trading decisions. This document describes the data architecture that separates **session-level data** from **daily-level data** following normalization principles.

## 2. Data Sources

### 2.1 Session Data (`NQ1_profiler.json`)

**Purpose:** Stores session-specific properties for each trading day.

**Structure:** Array of session objects, one per session per day.

```json
{
  "date": "2024-05-06",
  "session": "Asia",
  "status": "Long True",
  "broken": true,
  "broken_time": "02:45",
  "high_pct": 0.12,
  "low_pct": -0.08,
  "high_time": "19:30",
  "low_time": "18:45",
  "open": 19741.25,
  "range_high": 19765.5,
  "range_low": 19728.0,
  "mid": 19746.75,
  "prior_close": 19738.0,
  "start_time": "2024-05-05T18:00:00-04:00",
  "end_time": "2024-05-06T01:30:00-04:00"
}
```

**Key Fields:**

- `session`: One of "Asia", "London", "NY1", "NY2"
- `status`: Classification outcome ("Long True", "Long False", "Short True", "Short False", "None")
- `broken`: Whether the session range was broken by a subsequent session
- `high_pct`/`low_pct`: Session range expansion as % from session open
- `open`: Session opening price (first bar of session)

### 2.2 Daily Data (`NQ1_daily_hod_lod.json` & `NQ1_daily_hod_lod_unadjusted.json`)

**Purpose:** Stores daily high/low data. We utilize a **mixed data strategy** to optimize for accuracy:

- **Times (HOD/LOD Time):** Sourced from **Adjusted (Backadjusted)** data (`NQ1_daily_hod_lod.json`). This ensures continuity in time analysis across contract rollovers.
- **Levels (HOD/LOD Price %):** Sourced from **Unadjusted** data (`NQ1_daily_hod_lod_unadjusted.json`). This ensures price distribution stats reflect the actual raw market movement for that specific contract day, avoiding skew from rollover gaps.

> **Critical (v1.3.0):** The adjusted and unadjusted files have **different date ranges** (adjusted starts 2006, unadjusted starts 1999). The `useDailyHodLod` hook must merge by **date**, not by index position, to avoid mapping prices to the wrong dates. See §8 for details.

**Structure:** Object keyed by date.

```json
{
  "2024-05-06": {
    "hod_time": "14:30",
    "hod_ts": 1714413000,
    "hod_price": 19895.0,
    "lod_time": "03:15",
    "lod_ts": 1714372500,
    "lod_price": 19677.5,
    "daily_high": 19895.0,
    "daily_low": 19677.5,
    "daily_open": 19741.25
  }
}
```

**Key Fields:**

- `daily_open`: Opening price at 18:00 ET (Globex open)
- `daily_high`: Highest price of the full trading day
- `daily_low`: Lowest price of the full trading day
- `hod_time`/`lod_time`: Time of day when high/low occurred (HH:MM format)
- `hod_ts`/`lod_ts`: Unix timestamps for HOD/LOD (for frontend flexibility)

### 2.3 Level Touches (`NQ1_level_touches.json` & `NQ1_level_touches_columnar.json`)

**Purpose:** Optimized lookup for hit rates of key reference levels. Two formats exist:

- **`NQ1_level_touches.json`** — Daily-level format (dict keyed by date). Used by the lookup table generator's legacy `_compute_level_hits_for_dates()` for global hit rates. Returns `{touched: bool, touch_times: [...]}` per level per day.
- **`NQ1_level_touches_columnar.json`** — Columnar format (arrays indexed by date position). Used by the WebUI frontend (`DailyLevels` component) and the lookup table generator's per-outcome hit computation. Returns `hits.{session}[dateIdx]` = minutes-from-midnight of first touch, or `-1` if not touched. This is the **primary format** for per-session, per-outcome level hit rates.

**Reference Levels (20 total):**

- **Static Macro**: PDH, PDL, PDM (Previous Day stats).
- **Static Day**: P12 (Overnight 06:00-17:59 High/Low/Mid), NY P12 (Day High/Low/Mid).
- **Time-Based**: Daily Open (18:00), Midnight Open (00:00), 07:30 Open.
- **Dynamic Session**: Asia Mid, London Mid, NY1 Mid, NY2 Mid.
- **Cross-Session context**: `prev_asia_mid`, `prev_london_mid`, `prev_ny1_mid`, `prev_ny2_mid`. Used for earlier sessions to analyze relationships to previous day's volatility without lookahead bias.

**Session Observation Windows:**
The API optimizes "touches" based on the **Target Session**.

- **Start Bound**: The end of a level's "Utility Window" (e.g. Asia Mid formed by 19:30).
- **End Bound**: 17:00 (End of trading day).
- _Special Case_: For Asia/London sessions, `prev_*` session mids are used as they are already formed before the trading day starts.

**Who uses what:**
- **Columnar format** → WebUI `DailyLevels` component (per-session hit rates), lookup table generator (per-outcome hit rates), validator `compute.py`
- **Daily-level format** → Lookup table generator's global hit rates (legacy fallback)

---

## 3. Data Flow

```mermaid
graph TD
    subgraph Data Generation
        A[NQ1_1m.parquet] --> B[precompute_profiler.py]
        A --> C[precompute_daily_hod_lod.py]
        A --> LT_GEN[precompute_level_touches.py]
        B --> D[NQ1_profiler.json]
        C --> E[NQ1_daily_hod_lod.json<br/>Adjusted: Times]
        C --> F[NQ1_daily_hod_lod_unadjusted.json<br/>Unadjusted: Prices]
        LT_GEN --> LT_JSON[NQ1_level_touches.json<br/>Daily-level]
        LT_GEN --> LT_COL[NQ1_level_touches_columnar.json<br/>Columnar: Per-session hits]
    end

    subgraph Lookup Table Generator
        D --> LKG[generate_profiler_lookup.py]
        F --> LKG
        LT_COL --> LKG
        LKG --> LK_OUT[data/derived/NQ1_profiler_lookup.json<br/>Context keys + per-outcome stats]
    end

    subgraph Pine Generator
        D --> G[generate_profiler_pine.py]
        E --> G
        F --> G
        G --> H[Pine Libraries (Mixed Sources, 3-bit Status)]
    end

    subgraph Backend API
        D --> I[/stats/filtered-stats]
        LT_COL --> LT_API[/stats/level-touches<br/>Columnar format]
        I --> J[matched_dates + lean sessions]
    end

    subgraph Frontend
        J --> K[useServerFilteredStats]
        E --> L[useDailyHodLod<br/>Merge by DATE: Adj Times + Unadj Prices]
        F --> L
        LT_API --> L_TOUCH_FE[useLevelTouches]
        K --> M[RangeDistribution<br/>Uses Unadj prices from dailyHodLod]
        L --> M
        K --> ODV[OutcomeDetailView<br/>Builds synthetic sessions from dailyHodLod]
        L --> ODV
        ODV --> M
        L_TOUCH_FE --> M_SA[SessionAnalysisView]
        M_SA --> N_DL[DailyLevels / LevelCard<br/>Uses columnar hits by target session]
        ODV --> N_DL
    end

    subgraph Validation
        D --> VAL[scripts/testing/]
        F --> VAL
        LT_COL --> VAL
        LK_OUT --> VAL
        I --> VAL
        VAL --> VAL_OUT[128/128 fields match<br/>76/76 NY1 filters pass]
    end
```

## 4. Design Principles

### 4.1 Normalization

- **Session data** contains only session-specific properties
- **Daily data** contains only day-level aggregates
- No duplication: `daily_open`, `daily_high`, `daily_low` are stored ONCE per day.

### 4.2 Separation of Concerns

- **Filters** operate on session properties (status, broken, direction)
- **Daily calculations** (Price Range Distribution) use daily values
- **Join** happens at the frontend using `date` as the key

### 4.3 Payload Optimization

Backend's `get_filtered_stats` returns lean sessions without daily values:

- Reduces payload size by ~25%
- Frontend already has `dailyHodLod` data via separate hook
- No need to duplicate daily values across 4 sessions per day

### 4.4 Unadjusted Data Usage (v1.3.0)

The following components use **unadjusted** price data for computations:

| Consumer | Data Source | Purpose |
|----------|-----------|---------|
| `useDailyHodLod` hook | `GET /stats/daily-hod-lod/{ticker}?unadjusted=true` | Fetches `daily_open`, `daily_high`, `daily_low` (unadjusted) |
| `RangeDistribution` component | `dailyHodLod` (merged, unadjusted prices) | Computes `highPct`/`lowPct` arrays for distribution |
| `OutcomeDetailView` | `dailyHodLod` (merged, unadjusted prices) | Builds synthetic daily sessions for per-outcome analysis |
| Lookup table generator | `NQ1_daily_hod_lod_unadjusted.json` | Computes per-outcome `h_mode`, `h_med`, `l_mode`, `l_med` |
| Validator `compute.py` | `NQ1_daily_hod_lod_unadjusted.json` | Same computation as lookup table generator |

The following components use **adjusted** data:

| Consumer | Data Source | Purpose |
|----------|-----------|---------|
| `useDailyHodLod` hook | `GET /stats/daily-hod-lod/{ticker}?unadjusted=false` | Fetches `hod_time`, `lod_time` (adjusted for contract continuity) |
| Lookup table generator | `NQ1_daily_hod_lod.json` (adjusted) | HOD/LOD timing modes |
| Validator `compute.py` | `NQ1_daily_hod_lod.json` (adjusted) | Same timing computation |

### 4.5 Backend Count Integrity (v1.3.0)

The backend's `apply_filters()` method excludes dates where the target session is entirely missing (NaN in the pivot table). This ensures:
- `count` == sum of `distribution` values
- Dates with context filters matching but no target session record are excluded
- The validator's `FilterEngine` applies the same exclusion for consistency

## 5. Key Components

| Component                     | Role                                                |
| ----------------------------- | --------------------------------------------------- |
| `precompute_profiler.py`      | Generates session-level stats                       |
| `precompute_daily_hod_lod.py` | Generates daily-level stats (Adj & Unadj)           |
| `precompute_level_touches.py` | Generates level touches (daily-level + columnar)    |
| `generate_profiler_pine.py`   | Generates Pine libraries (3-bit Status, Mixed Data) |
| `generate_profiler_lookup.py` | Generates lookup tables (context keys + per-outcome stats + per-outcome level hits) |
| `profiler_service.py`         | Server-side filtering, returns lean sessions        |
| `useDailyHodLod` hook         | Fetches & merges daily data **by date** (Times=Adj, Prices=Unadj) |
| `useServerFilteredStats` hook | Fetches filtered sessions                           |
| `useLevelTouches` hook        | Fetches columnar level touches                      |
| `RangeDistribution`           | Computes price distribution from Unadj daily data   |
| `OutcomeDetailView`           | Builds synthetic daily sessions from dailyHodLod for per-outcome analysis |
| `DailyLevels` / `LevelCard`   | Computes per-session, per-outcome level hit rates from columnar data |
| `scripts/testing/`            | Validation framework — compares local, lookup table, and WebUI API |

## 6. Price Range Distribution Calculation

```typescript
// Frontend: RangeDistribution component
for (const date of matched_dates) {
  const dayData = dailyHodLod[date]; // Merged: Adj Times, Unadj Prices (aligned by DATE)
  if (!dayData) continue;

  const { daily_open, daily_high, daily_low } = dayData;

  // Calculate percentage from daily open (Unadjusted)
  const highPct = ((daily_high - daily_open) / daily_open) * 100;
  const lowPct = ((daily_low - daily_open) / daily_open) * 100;

  highPcts.push(highPct);
  lowPcts.push(lowPct);
}
```

### Mode Tie-Breaking (v1.3.0)

When multiple bins have the same count, the mode is selected by **sorting tied bins numerically ascending** (first bin wins). This is deterministic and reproducible across Python and JavaScript:

```typescript
// Fixed modeBin in range-distribution.tsx
const sorted = Object.entries(counts).sort((a, b) => {
  const countDiff = b[1] - a[1];        // Sort by count desc
  if (countDiff !== 0) return countDiff;
  return parseFloat(a[0]) - parseFloat(b[0]); // Tie: sort by bin value asc
});
```

```python
# Lookup table generator + validator compute.py
max_count = max(buckets.values())
candidates = sorted([k for k, v in buckets.items() if v == max_count])
return candidates[0]  # First numerically
```

Previously, the WebUI relied on JS `Object.entries().sort((a,b) => b[1] - a[1])` which uses insertion order for ties — non-deterministic and dependent on data processing order.

## 7. Technology & Constraints

- **Trading Day Definition**: 18:00 ET to 17:00 ET next day
- **Timezone**: All timestamps stored as Unix (UTC), display in America/New_York
- **Anchor Point**: `daily_open` is the 18:00 ET bar open price
- **Bucket Size**: Distribution uses 0.1% buckets (mode/median use floor-to-bin-start)
- **Tie-Breaking**: Mode bins are sorted numerically ascending on ties (deterministic)
- **Date Alignment**: Adjusted and unadjusted data files have different date ranges and must be merged by date, not by index

## 8. Validation Framework (v1.3.0)

A validation framework at `scripts/testing/` compares profiler statistics computed locally against the precomputed lookup table (`data/derived/{ticker}_profiler_lookup.json`) and the live WebUI API.

### Architecture

```
scripts/testing/
├── run.py                          # CLI entry point
├── core/
│   ├── base.py                     # FeatureValidator protocol, ValidationResult
│   ├── filter_engine.py            # Pivot-table filter (replicates WebUI backend)
│   ├── api_client.py               # WebUI HTTP client
│   ├── comparator.py               # Field-by-field comparison
│   └── reporter.py                 # Markdown/JSON/side-by-side output
└── features/profiler/
    ├── data.py                     # Data loading + constants (20 level keys)
    ├── compute.py                  # Local stats computation
    ├── api.py                      # WebUI API calls
    └── validator.py                # ProfilerFeatureValidator
```

### What It Validates

- **Count**: Total matched dates (including "None" status, excluding missing target sessions)
- **Distribution**: Per-outcome probabilities (LT/LF/ST/SF)
- **Price Stats**: Per-outcome mode, median (floor-to-bin-start, sorted tie-breaking)
- **Timing**: Per-outcome HOD/LOD mode (15-min buckets)
- **Broken Rates**: Per-outcome broken percentages
- **Level Hit Rates**: Global (all outcomes combined) — 20 columnar level keys
- **Per-Outcome Level Hits**: Per-outcome level hit rates — 20 columnar level keys including `prev_*` session mids and `daily_open`

### Level Keys (20 total)

The validator tracks all 20 columnar level keys used by the WebUI's `DailyLevels` component:
`pdh`, `pdm`, `pdl`, `p12h`, `p12m`, `p12l`, `ny_p12h`, `ny_p12m`, `ny_p12l`, `daily_open`, `midnight_open`, `open_0730`, `asia_mid`, `london_mid`, `ny1_mid`, `ny2_mid`, `prev_asia_mid`, `prev_london_mid`, `prev_ny1_mid`, `prev_ny2_mid`

### Usage

```bash
# Start backend first
start_api.bat

# Single filter comparison
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --filter "LF|LF" --detail

# All filters for a session
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters

# JSON output
python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters --format json
```

### Validation Results (NQ1 NY1)

**76/76 filter combinations pass** (128/128 fields match on LF|LF baseline).

Cross-verified against live WebUI browser values for 3 filters (LF|LF, LT|ST, SF|ST):
- All price distribution arrays (highPcts, lowPcts) match exactly
- All mode/median values match
- All per-outcome level hit rates (12 levels × 2 outcomes) match

## 9. Cross-Session Reference Logic

To maintain statistical integrity and avoid **Lookahead Bias**, the system dynamically adjusts which reference levels are used based on the active **Target Session**:

- **Target: Asia / London**: These sessions occur early in the trading day. Current day levels (like NY1 Mid) have not formed yet. Therefore, the UI and API map these to **Previous Day's** session mids (`prev_asia_mid`, `prev_ny1_mid`, etc.).
- **Target: NY1 / NY2**: By this time, the current day's Asia and London mids are formed. The system uses the **Current Day's** Asia/London mids but still relies on **Previous Day's** NY mids if needed for historical context.

This logic ensures that "Hit Rates" only reflect price action that _could_ have happened in real-time.

## 10. Changelog

| Version | Date       | Changes                                                                                                                                                                |
| ------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0.0   | 2026-02-02 | Initial design - normalized session/daily data separation                                                                                                              |
| 1.1.0   | 2026-02-03 | Implemented Mixed Data Strategy (Adj Times / Unadj Levels). Increased Pine status packing to 3-bit. Updated Frontend to merge sources.                                 |
| 1.2.0   | 2026-02-20 | Implemented Level Touches precomputation. Added NY P12 (Day stats) and explicitly tracked Previous Session Mids to eliminate lookahead bias in early session analysis. |
| 1.3.0   | 2026-07-17 | **Validation Framework**: Added `scripts/testing/` validation framework. Fixed `useDailyHodLod` date alignment (merge by date, not index). Fixed mode tie-breaking (sorted numerically, deterministic). Fixed backend count bug (exclude missing target sessions). Added per-outcome level hit rates to lookup table. Expanded level keys to 20 (includes `prev_*` and `daily_open`). |
