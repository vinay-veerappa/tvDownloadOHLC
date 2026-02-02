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

### 2.2 Daily Data (`NQ1_daily_hod_lod.json`)

**Purpose:** Stores true daily high/low prices and times for the full trading day (18:00 to 17:00 next day).

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
        B --> D[NQ1_profiler.json]
        C --> E[NQ1_daily_hod_lod.json]
    end
    
    subgraph Backend API
        D --> F[/stats/filtered-stats]
        F --> G[matched_dates + sessions]
    end
    
    subgraph Frontend
        G --> H[useServerFilteredStats]
        E --> I[useDailyHodLod]
        H --> J[RangeDistribution]
        I --> J
        J --> K[Join by Date]
        K --> L[Calculate % Distribution]
    end
```

## 4. Design Principles

### 4.1 Normalization

- **Session data** contains only session-specific properties
- **Daily data** contains only day-level aggregates
- No duplication: `daily_open`, `daily_high`, `daily_low` are stored ONCE per day in `daily_hod_lod.json`, NOT in every session

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
| `precompute_daily_hod_lod.py` | Generates daily-level stats |
| `profiler_service.py` | Server-side filtering, returns lean sessions |
| `useDailyHodLod` hook | Fetches daily data on frontend |
| `useServerFilteredStats` hook | Fetches filtered sessions |
| `RangeDistribution` | Joins sessions + dailyHodLod for distribution calc |

## 6. Price Range Distribution Calculation

```typescript
// Frontend: RangeDistribution component
for (const date of matched_dates) {
    const dayData = dailyHodLod[date];
    if (!dayData) continue;
    
    const { daily_open, daily_high, daily_low } = dayData;
    
    // Calculate percentage from daily open
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
- **Bucket Size**: Distribution uses 0.1% buckets

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-02 | Initial design - normalized session/daily data separation |
