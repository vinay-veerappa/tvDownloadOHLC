# Profiler Data Design

**Version:** 1.0.0  
**Last Updated:** February 02, 2026

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

### 2.3 Level Touches (`NQ1_level_touches.json`)

**Purpose:** Optimized lookup for hit rates of key reference levels. To reduce payload size, the API returns only the _first hit_ per session window.

**Reference Levels:**

- **Static Macro**: PDH, PDL, PDM (Previous Day stats).
- **Static Day**: NY P12 (Previous Day 06:00-17:59 High/Low/Mid).
- **Time-Based**: Daily Open (18:00), Midnight Open (00:00), 07:30 Open.
- **Dynamic Session**: Asia Mid, London Mid, NY1 Mid, NY2 Mid.
- **Cross-Session context**: `prev_asia_mid`, `prev_london_mid`, etc. Used for earlier sessions to analyze relationships to previous day's volatility without lookahead bias.

**Session Observation Windows:**
The API optimizes "touches" based on the **Target Session**.

- **Start Bound**: The end of a level's "Utility Window" (e.g. Asia Mid formed by 19:30).
- **End Bound**: 17:00 (End of trading day).
- _Special Case_: For Asia/London sessions, `prev_*` session mids are used as they are already formed before the trading day starts.

---

## 3. Data Flow

```mermaid
graph TD
    subgraph Data Generation
        A[NQ1_1m.parquet] --> B[precompute_profiler.py]
        A --> C[precompute_daily_hod_lod.py]
        A --> LT_GEN[precompute_level_touches.py]
        B --> D[NQ1_profiler.json]
        C --> E[NQ1_daily_hod_lod.json]
        C --> F[NQ1_daily_hod_lod_unadjusted.json]
        LT_GEN --> LT_JSON[NQ1_level_touches.json]
    end

    subgraph Pine Generator
        D --> G[generate_profiler_pine.py]
        E --> G
        F --> G
        G --> H[Pine Libraries (Mixed Sources, 3-bit Status)]
    end

    subgraph Backend API
        D --> I[/stats/filtered-stats]
        LT_JSON --> LT_API[/stats/level-touches]
        I --> J[matched_dates + sessions]
    end

    subgraph Frontend
        J --> K[useServerFilteredStats]
        E --> L[useDailyHodLod (Merged)]
        F --> L
        LT_API --> L_TOUCH_FE[useLevelTouches]
        K --> M[RangeDistribution]
        L --> M
        M --> N[Join by Date (Adj Times + Unadj Pcts)]
        L_TOUCH_FE --> M_SA[SessionAnalysisView]
        M_SA --> N_DL[DailyLevels / LevelCard]
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

## 5. Key Components

| Component                     | Role                                                |
| ----------------------------- | --------------------------------------------------- |
| `precompute_profiler.py`      | Generates session-level stats                       |
| `precompute_daily_hod_lod.py` | Generates daily-level stats (Adj & Unadj)           |
| `generate_profiler_pine.py`   | Generates Pine libraries (3-bit Status, Mixed Data) |
| `profiler_service.py`         | Server-side filtering, returns lean sessions        |
| `useDailyHodLod` hook         | Fetches & merges daily data (Times=Adj, Pct=Unadj)  |
| `useServerFilteredStats` hook | Fetches filtered sessions                           |
| `RangeDistribution`           | Joins sessions + dailyHodLod for distribution calc  |

## 6. Price Range Distribution Calculation

```typescript
// Frontend: RangeDistribution component
for (const date of matched_dates) {
  const dayData = dailyHodLod[date]; // Merged: Adj Times, Unadj Prices
  if (!dayData) continue;

  const { daily_open, daily_high, daily_low } = dayData;

  // Calculate percentage from daily open (Unadjusted)
  const highPct = ((daily_high - daily_open) / daily_open) * 100;
  const lowPct = ((daily_low - daily_open) / daily_open) * 100;

  highPcts.push(highPct);
  lowPcts.push(lowPct);
}
```

## 7. Technology & Constraints

- **Trading Day Definition**: 18:00 ET to 17:00 ET next day
- **Timezone**: All timestamps stored as Unix (UTC), display in America/New_York
- **Anchor Point**: `daily_open` is the 18:00 ET bar open price
- **Bucket Size**: Distribution uses 0.2% buckets (aligned with Pine)

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
