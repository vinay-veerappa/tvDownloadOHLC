# The Daily Profiler - Requirements Specification

**Goal**: Replicate and extend the statistical dashboard functionality found in "The Daily Profiler" to provide deep insights into session behavior, false breakouts, daily high/low timing, and reference level analysis.

## 🖼️ Reference UI

![Daily Profiler Dashboard](media/profiler_dashboard.png)


---

## 📝 Part 0: Philosophy & Core Logic ("08-12 Philosophy")

### 0.1 Trading Day Definition
*   **Start**: 18:00 ET (Previous Calendar Day)
*   **End**: 17:00 ET (Current Calendar Day)
*   **Anchor**: All statistical calculations are anchored to **18:00 ET**. Timestamps are minutes from 18:00.

### 0.3 Session Independence (The "Reset Flag" Logic)
*   **Definition**: The probability of a level being hit is calculated **independently** for each session.
*   **Logic**: A hit in a prior session (e.g., Asia) **does not** preclude a hit in a later session (e.g., NY1) from being counted. The "Hit Flag" is effectively reset at the start of each session of interest.
*   **Implication**: Hits must be tracked with sufficient granularity (e.g., list of all hit times) to allow dynamic filtering by session boundaries (Asia, London, NY1, etc.). Use **5-minute** distinct buckets for storage and analysis.

### 0.4 Hit Calculation Logic (Strict Precision)
*   **Granularity**: 5-Minute Buckets (e.g., 09:30, 09:35).
*   **Precision (Zero Tolerance)**: A hit is recorded **only if** the price strictly intersects the level:
    *   `Bar Low <= Level <= Bar High`
    *   No tolerance buffer allowed (e.g., a miss by 1 tick is a miss).
*   **Uniqueness (First Hit Rule)**:
    *   For any given session (e.g., NY1), only the **First Hit** is counted towards the probability.
    *   Subsequent hits in the same session are ignored.
    *   This ensures the sum of counts in a distribution histogram never exceeds the total number of days.


---

## 📝 Part 1: Core Statistical Logic

### 1. Session Definitions
| Session | Range Window | Status Check Window | Broken Check Window |
|---------|-------------|---------------------|---------------------|
| **Asia** | 18:00 - 19:30 | 19:30 → 02:30 (London Start) | 02:30 → 18:00 |
| **London** | 02:30 - 03:30 | 03:30 → 07:30 (NY1 Start) | 07:30 → 18:00 |
| **NY1** | 07:30 - 08:30 | 08:30 → 11:30 (NY2 Start) | 11:30 → 18:00 |
| **NY2** | 11:30 - 12:30 | 12:30 → 17:00 (Market Close) | N/A (End of Day) |

- **Mid**: `(Session High + Session Low) / 2`

### 2. "Status" Logic (The Play-Out)
*Window*: **Session End** to **Next Session Start**.

| Status | Condition |
|--------|-----------|
| **Long True** | Price breaks **above** Session High without breaking Session Low |
| **Short True** | Price breaks **below** Session Low without breaking Session High |
| **Long False** | Price breaks High first, then breaks Low (reversal) |
| **Short False** | Price breaks Low first, then breaks High (reversal) |
| **None** | Price remains **inside** Session Range |

### 3. "Broken" Logic
*Window*: **Next Session Start** to **18:00** (Asia Start / End of Cycle).

| State | Condition |
|-------|-----------|
| **Broken (Yes)** | Session **Mid** is touched or crossed during window |
| **Broken (No)** | Session Mid is respected (not touched) |

---

## 📝 Part 2: Tab Structure (5-Tab Layout)

> [!IMPORTANT]
> The Profiler uses a **5-Tab architecture**. All tabs respect the **Global Intersection Filter**.

### Tab Overview

| Tab # | Name | Purpose |
|-------|------|---------|
| 1 | **Daily Overview** | Consolidated view of entire trading day |
| 2 | **Asia** | Session-specific analysis for Asia |
| 3 | **London** | Session-specific analysis for London |
| 4 | **NY1** | Session-specific analysis for NY1 |
| 5 | **NY2** | Session-specific analysis for NY2 |

### 2.1 Daily Overview Tab
Contains:
1. **HOD/LOD Time Analysis**
2. **Global Price Range Distribution** (All sessions combined)
3. **Daily Price Model** (Median High/Low paths, Full Day 18:00→16:00)
4. **Daily Levels Analysis** (All reference levels)
5. **Session HOD/LOD Contribution** (Stats)

### 2.2 Session Tabs (Asia, London, NY1, NY2)
Each session tab uses the `SessionAnalysisView` component with:

| Row | Component | Description |
|-----|-----------|-------------|
| 1 | **HOD/LOD Analysis** | Time histograms + zoom |
| 2 | **Range Distribution** | High/Low % from open |
| 3 | **Median Price Model** | Session-specific timeframe chart |
| 4 | **Outcome Grid** | True/False outcome panels |
| 5 | **Session Levels** | Relevant reference levels |

---

## 📝 Part 3: Global Intersection Filter Logic

> [!IMPORTANT]
> **All tabs display data from the INTERSECTION of all active filters.**

### Filter Behavior
When filters are set in the Profiler Wizard:
- If `Asia=Short` AND `London=Long` are active:
- The **Asia Tab** shows stats *only* for days where BOTH conditions occurred
- NOT just days where Asia=Short

### Filter Display
- **Active Filters Row**: Displayed below the Wizard, shows all active filters as badges
- Clear indication of filter state across sessions

---

## 📝 Part 4: Reference Price Levels


### 4.1 Level Definitions & Strict Time Windows

All times are in **US/Eastern (ET)**.

| Level Name | Definition | Establishment Time | **Valid Touch Window** |
| :--- | :--- | :--- | :--- |
| **PDH** | Previous Day High | 18:00 | **18:00 - 17:00** |
| **PDL** | Previous Day Low | 18:00 | **18:00 - 17:00** |
| **P12 High** | Overnight High (18:00-06:00) | 06:00 | **06:00 - 17:00** |
| **P12 Low** | Overnight Low (18:00-06:00) | 06:00 | **06:00 - 17:00** |
| **P12 Mid** | Overnight Midpoint | 06:00 | **06:00 - 17:00** |
| **Daily Open** | Globex Open (18:00) | 18:00 | **18:00 - 17:00** |
| **Midnight Open** | Midnight Price (00:00) | 00:00 | **00:00 - 17:00** |
| **07:30 Open** | Pre-Market Open | 07:30 | **07:30 - 17:00** |
| **Asia Mid** | Asia Session Midpoint | 02:00 | **02:00 - 17:00** |
| **London Mid** | London Session Midpoint | 07:00 | **07:00 - 17:00** |
| **NY1 Mid** | NY1 Session Midpoint | 12:00 | **12:00 - 17:00** |
| **NY2 Mid** | NY2 Session Midpoint | 16:00 | (Removed from UI) |

### 4.2 Session-Specific Levels
Each session tab displays only relevant levels:

| Session | Displayed Levels |
|---------|------------------|
| **Asia** | Daily Open, PDH, PDL, PDM, P12 H/M/L, Asia Mid |
| **London** | Midnight Open, Asia Mid, London Mid, PDH, PDL |
| **NY1** | 07:30 Open, London Mid, NY1 Mid, Asia Mid |
| **NY2** | NY1 Mid, London Mid, Asia Mid |

### 4.3 Level Statistics
For each level, display:
- **Touch Rate**: % of filtered days where level was touched
- **Mode Time**: Most common time bucket when touched
- **Median Time**: Time where 50% of total hits have occurred (White Dashed Line on chart)
- **Time Histogram**: Distribution of touch times (supports 1min, 5min, 15min granularity)

---

## 📝 Part 5: Price Model Charts

### 5.1 Requirements
- **Median Aggregation**: Use median (not mean) for High/Low paths
- **Session-Trimmed**: Each session chart shows only its relevant timeframe
- **Daily Model**: Full day view (18:00 → 16:00 next day)

### 5.2 Chart Features
- X-axis: Time (session duration or full day)
- Y-axis: % change from session open
- **Green line**: Median High path
- **Red line**: Median Low path
- Gray shaded region: Session boundary

### 5.3 Tooltip Style
- **Header Info Style**: As user hovers, values appear in fixed header row above chart
- Keep chart view unobstructed (no floating tooltips)

---

## 📝 Part 6: Outcome Panels

### 6.1 Panel Structure
Each outcome panel contains:
1. **Header**: Outcome name, % probability, sample count
2. **Average Price Path**: Median High/Low lines
3. **HOD/LOD Distribution**: Combined histogram
4. **Range Distribution**: % from open histograms
5. **Level Touch Rates**: P12 and session-relevant levels

### 6.2 Dynamic Panel Count

| Filter State | Possible Outcomes | Panels |
|--------------|-------------------|--------|
| No filter | Long True, Long False, Short True, Short False | 4 |
| Direction known (e.g., "Long") | Long True, Long False | 2 |
| Full outcome known | Single outcome | 1 |

---

## ✅ Implementation Status (as of Dec 11, 2024)

### Completed ✅

| Feature | Notes |
|---------|-------|
| **5-Tab UI Structure** | Daily Overview, Asia, London, NY1, NY2 tabs |
| **SessionAnalysisView Component** | Reusable session analysis template |
| **Global Intersection Filter** | All tabs respect filter intersection |
| **Active Filters Row** | Badge display of active filters |
| **Profiler Wizard (Compact)** | Horizontal layout, inline filters |
| **Median Price Model Charts** | Backend + Frontend implementation |
| **Header-Style Chart Tooltips** | Fixed header (PriceModel), Standardized Floating (Others) |
| **True Daily HOD/LOD** | Computed from 1-min data |
| **HOD/LOD Time Distributions** | Histograms with granularity selector |
| **Range Distribution** | High/Low from open charts |
| **PDH/PDM/PDL Touch Stats** | Hit rate, mode, median, histogram |
| **P12 H/M/L Touch Stats** | Hit rate, mode, median, histogram |
| **Session Mids** | All session mids with touch stats |
| **Time-Based Opens** | Daily (18:00), Midnight, 07:30 |
| **Precompute Scripts** | All level/stats precomputation |
| **Session Stats Cards** | Direction bias, True/False, Broken |
| **History Table** | Filterable session history |
| **Backend Optimization** | Vectorized price model + Optimized Level Touches |
| **Standardized Tooltips** | Unified styling across all Recharts components |
| **Outcome Panel Grid** | Integrated in session tabs |
| **Session-Specific Levels** | `limitLevels` prop verified |

### Pending ⏳

| Feature | Priority |
|---------|----------|
| **PWH/PWL (Previous Week H/L)** | Medium |
| **PMH/PML (Previous Month H/L)** | Medium |
| **Weekly Close** | Low |
| **Volatility Models** | Low |
| **Reference Level Filtering** | Low |

---

## 📁 Key Files

### Backend
| File | Purpose |
|------|---------|
| `api/routers/profiler.py` | API endpoints |
| `api/services/profiler_service.py` | Calculation logic (optimized) |
| `scripts/precompute_daily_hod_lod.py` | Daily HOD/LOD times |
| `scripts/precompute_level_touches.py` | Level touch data |
| `scripts/precompute_profiler.py` | Session statistics |

### Frontend
| File | Purpose |
|------|---------|
| `web/app/profiler/page.tsx` | Page entry point |
| `web/components/profiler/profiler-view.tsx` | 5-Tab container |
| `web/components/profiler/session-analysis-view.tsx` | Reusable session layout |
| `web/components/profiler/profiler-wizard.tsx` | Filter wizard |
| `web/components/profiler/active-filters-row.tsx` | Filter badge display |
| `web/components/profiler/price-model-chart.tsx` | Median chart component |
| `web/components/profiler/chart-header-info.tsx` | Header-style tooltip |
| `web/components/profiler/hod-lod-analysis.tsx` | HOD/LOD histograms |
| `web/components/profiler/daily-levels.tsx` | Reference levels (with limitLevels) |
| `web/components/profiler/range-distribution.tsx` | Range charts (with forcedSession) |
| `web/components/profiler/outcome-panel.tsx` | Individual outcome panel |
| `web/hooks/use-profiler-filter.ts` | Filter intersection logic |
| `web/lib/api/profiler.ts` | API types and fetchers |

### Data Files
| File | Purpose |
|------|---------|
| `data/NQ1_profiler.json` | Precomputed session stats |
| `data/NQ1_daily_hod_lod.json` | Daily HOD/LOD times |
| `data/NQ1_level_touches.json` | Level touch data |
| `data/NQ1_range_dist.json` | Range distribution data |

---

## 📝 Part 5: Backend API Reference

> [!NOTE]
> All endpoints are served from `http://localhost:8000`. The `{ticker}` parameter is required and should be the ticker symbol (e.g., `NQ1`).

### 5.1 Core Data Endpoints

#### `GET /stats/profiler/{ticker}`
**Purpose**: Get all session statistics for the last N days.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ticker` | path | required | Ticker symbol (e.g., `NQ1`) |
| `days` | query | 50 | Number of days to analyze |

**Response**: Returns list of session objects with status, broken flags, and price data.
```json
{
  "sessions": [...],
  "metadata": { "ticker": "NQ1", "days": 50, "count": 200 }
}
```

---

#### `POST /stats/profiler/{ticker}/filtered`
**Purpose**: Get pre-aggregated stats using filter criteria (server-side filtering).

**Request Body**:
```json
{
  "target_session": "NY1",
  "filters": { "Asia": "Short True", "London": "Long" },
  "broken_filters": { "Asia": "Broken" },
  "intra_state": "Any"
}
```

**Response**:
```json
{
  "matched_dates": ["2024-12-01", "2024-12-02", ...],
  "count": 250,
  "distribution": {
    "Long True": { "count": 45, "pct": 18.0 },
    "Short True": { "count": 80, "pct": 32.0 }
  },
  "range_stats": { "high_pct": {...}, "low_pct": {...} }
}
```

---

#### `POST /stats/profiler/{ticker}/price-model`
**Purpose**: Get median price model using filter criteria.

**Request Body**:
```json
{
  "target_session": "Daily",
  "filters": { "Asia": "Short True" },
  "broken_filters": {},
  "intra_state": "Any"
}
```

**Response**:
```json
{
  "average": [{ "time_idx": 0, "high": 0.01, "low": -0.02 }, ...],
  "extreme": [...],
  "count": 150
}
```

---

### 5.2 Reference Level Endpoints

#### `GET /stats/level-touches/{ticker}`
**Purpose**: Get level touch statistics (hit rate, mode time, histograms).

---

#### `GET /stats/daily-hod-lod/{ticker}`
**Purpose**: Get daily high/low of day timing data.

---

#### `GET /stats/hod-lod/{ticker}`
**Purpose**: Get pre-computed HOD/LOD time statistics.

---

#### `GET /stats/reference`
**Purpose**: Get reference price levels (P12, PDH/PDL, etc.).

---

### 5.3 Price Model Endpoints

#### `GET /stats/price-model/{ticker}`
**Purpose**: Get price model for specific session and outcome.

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | query | Session name (e.g., `NY1`, `Daily`) |
| `outcome` | query | Outcome filter (e.g., `Long True`) |
| `days` | query | Number of days |

---

#### `POST /stats/price-model/custom`
**Purpose**: Get price model for specific list of dates.

**Request Body**:
```json
{
  "ticker": "NQ1",
  "target_session": "Daily",
  "dates": ["2024-12-01", "2024-12-02"]
}
```

---

### 5.4 Utility Endpoints

#### `POST /stats/clear-cache/{ticker}`
**Purpose**: Clear in-memory cache for specified ticker.

#### `POST /stats/clear-cache`
**Purpose**: Clear all in-memory caches.

---

### 5.5 Frontend Usage Patterns

**Current Architecture**:
1. Frontend fetches all sessions: `GET /stats/profiler/{ticker}?days=10000`
2. Frontend applies filters client-side using `useProfilerFilter` hook
3. Frontend components render based on `filteredDates` Set

**Recommended Architecture** (Filter-Based):
1. Frontend sends filter criteria: `POST /stats/profiler/{ticker}/filtered`
2. Backend applies filters and returns aggregated stats
3. Frontend renders pre-computed data
