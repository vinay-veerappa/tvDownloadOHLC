# The Daily Profiler - Replication Requirements

**Goal**: Replicate the statistical dashboard functionality found in "The Daily Profiler" (see screenshot below) to provide deep insights into session behavior, false breakouts, and daily high/low timing.

## 🖼️ Reference UI

![Daily Profiler Dashboard](media/profiler_dashboard.png)

---
## 📝 Statistical Logic Definitions

The following rules define the "Status" and "Broken" metrics used in the Profit Cards.

### 1. Definitions
*   **Session Range**: Based on the High/Low of the defined session hours.
    *   *Asia*: 18:00 - 19:30
    *   *London*: 02:30 - 03:30
    *   *NY1*: 07:30 - 08:30
    *   *NY2*: 11:30 - 12:30
*   **Next Start**: The start time of the *next* chronological session (e.g., for London, Next Start is 07:30/NY1).
*   **Mid**: The arithmetic mean of the Session High and Low.

### 2. "Status" Logic (The Play-Out)
*Window*: **Session End** to **Next Start**.
*   **True Long**: Price breaks **above** Session High and determines direction without breaking Session Low during the window.
*   **True Short**: Price breaks **below** Session Low and determines direction without breaking Session High during the window.
*   **False**: Price breaks **BOTH** Session High and Session Low in any order during the window.
*   **None**: Price remains completely **INSIDE** the Session Range during the window.

### 3. "Broken" Logic
*Window*: **Next Start** to **18:00** (Asia Start / End of Cycle).
*   **Broken (Yes)**: The Session **Mid** is touched or crossed by price at any point during this window.
*   **Broken (No)**: The Session Mid is respected (not touched) during this window.

---


### 4. Conditional Profiling (The "Wizard")
The dashboard must allow filtering historical data based on simple boolean inputs of prior events to predict the current session's outcome.

**Workflow:**
1.  **Select Context**: User inputs the status of completed sessions (e.g. Asia=True Long, London=False Short).
2.  **Filter Data**: System filters the historical dataset to find matching days.
3.  **Display Probabilities**: Shows the probability distribution of the *current* session's 4 outcomes based on that history.
    *   **Outcomes**: Long True, Short True, Long False, Short False.
4.  **Intra-Session Update**: User inputs "what has happened so far" in the current session (e.g. "NY1 has broken High") to further refine the probabilities.


### 1. Profiler Sessions (Statistical Cards)
For each major session (Asia, London, NY1, NY2), display:
*   **Direction Bias**: Percentage of time the session is Long vs Short.
*   **True/False Breakouts**: Stats on whether the initial move was sustained.
*   **Broken Stats**: Frequency of the session range being broken.
*   **Time Histograms**:
    *   **False Times**: Distribution of WHEN false moves occur.
    *   **Broken Times**: Distribution of WHEN the range is broken.

### 2. High and Low of Day (HOD/LOD) Analysis
*   **Timing Distributions**: Histograms showing the probability of the HOD or LOD forming at specific times of the day.
*   **Daily Low/High Distribution**: Visual representation of price levels where H/L often form.

### 3. Price Models
*   **Average Path**: Line charts showing the "typical" price action for each session (aggregated average movement).
*   **Volatility Models**: Expected range expansion over time.

---

## 🆕 New Requirements (Phase 2)

### 5. Outcome-Based Side-by-Side Panels

When a filter narrows down the possible outcomes, the UI should display **separate panels** for each remaining possibility, each with its own complete set of statistics.

#### 5.1 Panel Structure
Each outcome panel should contain:
1. **Header**
   - Outcome name (e.g., "Short True", "Short False")
   - Percentage probability (e.g., "46.00%")
   - Sample count (e.g., "46 Days")
2. **Average Price Path Chart**
   - Line chart showing normalized % from open
   - One line for High path, one for Low path
   - Session boundaries marked (e.g., gray NY1 zone)
3. **HOD/LOD Time Distribution**
   - Combined histogram (HOD green up, LOD red down)
   - Mode and Median times for both
   - Granularity selector (15m default)
4. **Daily High/Low Distribution from Open**
   - % distribution histograms (red for low, green for high)
   - Mode and Median percentages
5. **P12 Reference Level Statistics**
   - P12 High touch probability
   - P12 Mid touch probability  
   - P12 Low touch probability

#### 5.2 Dynamic Panel Count
The number of panels displayed depends on filter state:

| Wizard State | Possible Outcomes | Panels Shown |
|--------------|-------------------|--------------|
| No filter (Any) | Long True, Long False, Short True, Short False | 4 panels |
| Direction known (e.g., "Long") | Long True, Long False | 2 panels |
| Full outcome known (e.g., "Long True") | Long True | 1 panel |

#### 5.3 Visual Example
When NY1 is determined to be "Short" based on prior session data (or current intra-session observation):

```
┌─────────────────────────────────┐ ┌─────────────────────────────────┐
│ SHORT TRUE (46.00% - 46 Days)   │ │ SHORT FALSE (54.00% - 54 Days)  │
├─────────────────────────────────┤ ├─────────────────────────────────┤
│ [Average Price Path Chart]      │ │ [Average Price Path Chart]      │
│                                 │ │                                 │
│ [HOD/LOD Time Distribution]     │ │ [HOD/LOD Time Distribution]     │
│                                 │ │                                 │
│ [Price Range Distribution]      │ │ [Price Range Distribution]      │
│                                 │ │                                 │
│ P12 High: 65.22%                │ │ P12 High: 92.59%                │
│ P12 Mid:  100.00%               │ │ P12 Mid:  98.15%                │
│ P12 Low:  93.48%                │ │ P12 Low:  77.78%                │
└─────────────────────────────────┘ └─────────────────────────────────┘
```

### 6. Integrated Global Filter

All analysis components must respect the active filter. When the user applies filters in the Wizard, the following components should all update to reflect only the filtered data:

- ✅ Time Histograms (False Moves / Session Breaks)
- ✅ HOD/LOD Analysis (Time distributions, Session attribution)
- ✅ Price Range Distribution (High/Low from open)
- ✅ Session Stats Cards
- ✅ History Table

**Implementation Note**: Wizard filters are applied by matching **dates** - when filters match a day, ALL sessions from that day are included in the filtered dataset.

### 7. Reference Price Levels

Multiple reference price levels serve as key support/resistance areas. For each outcome panel, calculate touch probabilities for all levels.

#### 7.1 Level Definitions

| Level | Definition | Calculation |
|-------|------------|-------------|
| **PDH** | Previous Day High | High of previous trading day (18:00 - 18:00) |
| **PDL** | Previous Day Low | Low of previous trading day |
| **PDM** | Previous Day Mid | (PDH + PDL) / 2 |
| **PWH** | Previous Week High | High of previous week |
| **PWL** | Previous Week Low | Low of previous week |
| **Weekly Close** | Prior Week Settlement | Settlement close from weekly parquet data |
| **PMH** | Previous Month High | High of previous month |
| **PML** | Previous Month Low | Low of previous month |
| **Daily Open** | Globex Open | Price at 18:00 (Asia start) |
| **Midnight Open** | Midnight Price | Price at 00:00 EST |
| **07:30 Open** | Pre-Market Open | Price at 07:30 EST |
| **P12 High** | Overnight High | High from 18:00 to 06:00 |
| **P12 Low** | Overnight Low | Low from 18:00 to 06:00 |
| **P12 Mid** | Overnight Midpoint | (P12 High + P12 Low) / 2 |
| **Asia Mid** | Asia Session Midpoint | (Asia High + Asia Low) / 2 |
| **London Mid** | London Session Midpoint | (London High + London Low) / 2 |
| **NY1 Mid** | NY1 Session Midpoint | (NY1 High + NY1 Low) / 2 |
| **NY2 Mid** | NY2 Session Midpoint | (NY2 High + NY2 Low) / 2 |

#### 7.2 Statistics per Outcome
For each outcome (Short True, Short False, Long True, Long False), calculate:
- % of days where each level was **touched** (price reached or crossed)
- % of days where each level was **respected** (price approached but did not cross)

#### 7.3 Display Format
```
┌─────────────────────────────────┐
│ Reference Level Touch Rates    │
├─────────────────────────────────┤
│ PDH        ↗ 72.34%            │
│ PDL        ↗ 45.67%            │
│ PDM        ↗ 88.00%            │
│ P12 High   ↗ 65.22%            │
│ P12 Mid    ↗ 100.00%           │
│ P12 Low    ↗ 93.48%            │
│ Weekly Close ↗ 58.00%          │
│ Daily Open ↗ 89.00%            │
│ Asia Mid   ↗ 95.00%            │
└─────────────────────────────────┘
```

#### 7.4 Filtering by Reference Level (Future)
Enable filtering the dataset by:
- "Days where PDH was touched"
- "Days where PDL was NOT touched"
- Combinations of reference level behaviors

### 8. Average Price Path Charts

Normalized price movement charts showing typical behavior for each outcome.

#### 8.1 Data Requirements
For each session in the filtered dataset:
- Normalize price to % change from session open
- Track high envelope and low envelope over time
- Average across all matching days

#### 8.2 Chart Features
- X-axis: Time (session duration)
- Y-axis: % from open
- Green line: Average high path
- Red line: Average low path
- Gray shaded region: Target session window
- Dotted lines: Session boundaries

---

### 9. Tabbed Profiler View

The main profiler analysis area uses a **3-tab structure**. All tabs respect the active Wizard filters.

#### 9.1 Tab Structure

| Tab | Name | Content |
|-----|------|---------|
| 1 | **HOD/LOD** | Time-of-day histograms for daily high and low occurrences |
| 2 | **Outcome Panels** | 1-4 panels showing stats for each outcome (Long True, Short True, etc.) |
| 3 | **Daily Levels** | Reference level touch analysis (Previous Day and P12 levels) |

#### 9.2 Daily Levels Tab Content

The Daily Levels tab contains two subsections:

##### Previous Day Levels
Three cards showing touch statistics for:
- **Previous Day Low (PDL)**: Hit rate, mode time, median time, touch time histogram
- **Previous Day Mid (PDM)**: Hit rate, mode time, median time, touch time histogram  
- **Previous Day High (PDH)**: Hit rate, mode time, median time, touch time histogram

##### P12 Levels (Overnight)
Three cards showing touch statistics for:
- **P12 High**: Hit rate, mode time, median time, touch time histogram
- **P12 Mid**: Hit rate, mode time, median time, touch time histogram
- **P12 Low**: Hit rate, mode time, median time, touch time histogram

#### 9.3 Touch Time Histogram
Each level card displays:
- **Hit Rate**: % of filtered days where level was touched
- **Mode**: Most common time bucket when level is touched
- **Median**: Median time range for touches
- **Histogram**: Bar chart showing touch time distribution (configurable granularity: 15m/30m/1h)

```
┌──────────────────────────────────────────────────────────────────┐
│  [HOD/LOD] | [Outcome Panels] | [Daily Levels]                   │  ← Tab bar
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Previous Day Levels                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ PDL          │ │ PDM          │ │ PDH          │             │
│  │ 35.93%       │ │ 62.87%       │ │ 55.09%       │             │
│  │ Mode: 09:30  │ │ Mode: 09:30  │ │ Mode: 18:00  │             │
│  │ [histogram]  │ │ [histogram]  │ │ [histogram]  │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│                                                                  │
│  P12 Levels                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ P12 High     │ │ P12 Mid      │ │ P12 Low      │             │
│  │ 86.83%       │ │ 98.20%       │ │ 77.84%       │             │
│  │ Mode: 06:00  │ │ Mode: 09:30  │ │ Mode: 09:30  │             │
│  │ [histogram]  │ │ [histogram]  │ │ [histogram]  │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## ✅ Implementation Status (as of Dec 10, 2024)

### Completed ✅

| Feature | Status | Notes |
|---------|--------|-------|
| **Profiler Wizard** | ✅ Done | Full filter support for prior sessions, direction, outcome state |
| **3-Tab UI Structure** | ✅ Done | HOD/LOD Analysis, Outcome Panels, Daily Levels tabs implemented |
| **True Daily HOD/LOD** | ✅ Done | Computed from 1-min OHLC, not session-based. See `precompute_daily_hod_lod.py` |
| **HOD/LOD Time Distributions** | ✅ Done | Histograms in HOD/LOD tab with granularity selector |
| **Time Histograms (False Moves)** | ✅ Done | Integrated in HOD/LOD Analysis tab |
| **Range Distribution** | ✅ Done | High/Low from open distribution charts |
| **Outcome Panel Grid** | ✅ Done | 1-4 panels based on filter state (dynamic count) |
| **PDH/PDM/PDL Touch Stats** | ✅ Done | Hit rate, mode, median, histogram in Daily Levels tab |
| **P12 H/M/L Touch Stats** | ✅ Done | Hit rate, mode, median, histogram in Daily Levels tab |
| **Time-Based Opens** | ✅ Done | Daily Open (18:00), Midnight Open, 07:30 Open |
| **Session Mids** | ✅ Done | Asia, London, NY1, NY2 session mids with touch stats |
| **Global Filter Context** | ✅ Done | All tabs respond to Wizard filters |
| **Precompute Scripts** | ✅ Done | `precompute_daily_hod_lod.py`, `precompute_level_touches.py` |
| **Session Stats Cards** | ✅ Done | Direction bias, True/False counts, Broken stats |
| **History Table** | ✅ Done | Filterable session history |

### In Progress 🔄

| Feature | Status | Notes |
|---------|--------|-------|
| **Average Price Path Charts** | 🔄 Partial | UI component exists but not fully integrated |

### Pending ⏳

| Feature | Priority | Notes |
|---------|----------|-------|
| **PWH/PWL (Previous Week H/L)** | Medium | Requires weekly OHLC aggregation |
| **PMH/PML (Previous Month H/L)** | Medium | Requires monthly OHLC aggregation |
| **Weekly Close** | Low | Settlement price from weekly data |
| **Volatility Models** | Low | Expected range expansion over time |
| **Reference Level Filtering** | Low | Filter by "PDH touched" or "PDL not touched" |
| **Touch vs Respected Stats** | Low | Differentiate touched vs just approached |

### Known Issues 🐛

| Issue | Severity | Notes |
|-------|----------|-------|
| Build TypeScript error in `hourly-profiler.ts` | Medium | `hitTest` return type mismatch - unrelated to profiler pages |
| CSS inline style lint warnings | Low | Cosmetic, doesn't affect functionality |
| Form label accessibility warnings | Low | Select components need aria labels |

---

## 🛠️ Implementation Strategy (Draft)

1.  **Backend (`/api/stats/profiler`)**:
    *   New endpoints to aggregate historical session data.
    *   Calculate histograms for "Time of High", "Time of Low", etc.
    *   Add P12 reference level calculations.
    *   Add average price path computation.
    *   **NEW**: Precompute level touch times (PDH/PDL/PDM, P12 H/L/M).
2.  **Frontend (`/profiler`)**:
    *   New page separate from the main Chart.
    *   **NEW**: 3-tab structure (HOD/LOD | Outcome Panels | Daily Levels).
    *   Grid layout using Shadcn UI Cards.
    *   Charts using `Recharts` (better for bar/line charts than Lightweight Charts).
    *   Dynamic outcome panel grid (1, 2, or 4 panels).
    *   Global filter context from Wizard to all components.

---

## 📁 Key Files

### Backend
| File | Purpose |
|------|---------|
| `api/routers/profiler.py` | API endpoints for profiler data |
| `api/services/profiler_service.py` | Profiler calculation logic |
| `scripts/precompute_daily_hod_lod.py` | Precompute true daily HOD/LOD times |
| `scripts/precompute_level_touches.py` | Precompute reference level touch data |

### Frontend
| File | Purpose |
|------|---------|
| `web/app/profiler/page.tsx` | Profiler page entry point |
| `web/components/profiler/profiler-view.tsx` | Main profiler container (3 tabs) |
| `web/components/profiler/profiler-wizard.tsx` | Filter wizard component |
| `web/components/profiler/hod-lod-analysis.tsx` | HOD/LOD histograms |
| `web/components/profiler/daily-levels.tsx` | Daily Levels tab (all reference levels) |
| `web/components/profiler/outcome-panel-grid.tsx` | Dynamic outcome panel layout |
| `web/components/profiler/outcome-panel.tsx` | Individual outcome panel |
| `web/lib/api/profiler.ts` | API types and fetch functions |

### Data Files
| File | Purpose |
|------|---------|
| `data/NQ1_daily_hod_lod.json` | Precomputed HOD/LOD times by date |
| `data/NQ1_level_touches.json` | Precomputed level touch data by date |
| `data/NQ1_profiler_stats.json` | Precomputed session statistics |
