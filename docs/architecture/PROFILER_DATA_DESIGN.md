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
  "range_high": 19765.50,
  "range_low": 19728.00,
  "mid": 19746.75,
  "prior_close": 19738.00,
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
*   **Times (HOD/LOD Time):** Sourced from **Adjusted (Backadjusted)** data (`NQ1_daily_hod_lod.json`). This ensures continuity in time analysis across contract rollovers.
*   **Levels (HOD/LOD Price %):** Sourced from **Unadjusted** data (`NQ1_daily_hod_lod_unadjusted.json`). This ensures price distribution stats reflect the actual raw market movement for that specific contract day, avoiding skew from rollover gaps.

**Structure:** Object keyed by date.

```json
{
  "2024-05-06": {
    "hod_time": "14:30",
    "hod_ts": 1714413000,
    "hod_price": 19895.00,
    "lod_time": "03:15",
    "lod_ts": 1714372500,
    "lod_price": 19677.50,
    "daily_high": 19895.00,
    "daily_low": 19677.50,
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

## 3. Data Flow

```mermaid
graph TD
    subgraph Data Generation
        A[NQ1_1m.parquet] --> B[precompute_profiler.py]
        A --> C[precompute_daily_hod_lod.py]
        B --> D[NQ1_profiler.json (Status/Session)]
        C --> E[NQ1_daily_hod_lod.json (Adj Times)]
        C --> F[NQ1_daily_hod_lod_unadjusted.json (Unadj Prices)]
    end
    
    subgraph Pine Generator
        D --> G[generate_profiler_pine.py]
        E --> G
        F --> G
        G --> H[Pine Libraries (Mixed Sources, 3-bit Status)]
    end

    subgraph Backend API
        D --> I[/stats/filtered-stats]
        I --> J[matched_dates + sessions]
    end
    
    subgraph Frontend
        J --> K[useServerFilteredStats]
        E --> L[useDailyHodLod (Merged)]
        F --> L
        K --> M[RangeDistribution]
        L --> M
        M --> N[Join by Date (Adj Times + Unadj Pcts)]
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

| Component | Role |
|-----------|------|
| `precompute_profiler.py` | Generates session-level stats |
| `precompute_daily_hod_lod.py` | Generates daily-level stats (Adj & Unadj) |
| `generate_profiler_pine.py` | Generates Pine libraries (3-bit Status, Mixed Data) |
| `profiler_service.py` | Server-side filtering, returns lean sessions |
| `useDailyHodLod` hook | Fetches & merges daily data (Times=Adj, Pct=Unadj) |
| `useServerFilteredStats` hook | Fetches filtered sessions |
| `RangeDistribution` | Joins sessions + dailyHodLod for distribution calc |

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

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-02 | Initial design - normalized session/daily data separation |
| 1.1.0 | 2026-02-03 | Implemented Mixed Data Strategy (Adj Times / Unadj Levels). Increased Pine status packing to 3-bit. Updated Frontend to merge sources. |
