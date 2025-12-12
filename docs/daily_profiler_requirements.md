# The Daily Profiler - Requirements Specification

**Goal**: Replicate and extend the statistical dashboard functionality found in "The Daily Profiler" to provide deep insights into session behavior, false breakouts, daily high/low timing, and reference level analysis.

## 🖼️ Reference UI

![Daily Profiler Dashboard](media/profiler_dashboard.png)

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
1. **Global Price Range Distribution** (All sessions combined)
2. **Daily Price Model** (Median High/Low paths, Full Day 18:00→16:00)
3. **Daily Levels Analysis** (All reference levels)

### 2.2 Session Tabs (Asia, London, NY1, NY2)
Each session tab uses the `SessionAnalysisView` component with:

| Row | Component | Description |
|-----|-----------|-------------|
| 1 | **Range Distribution** | High/Low % from open, locked to this session |
| 2 | **Median Price Model** | Session-specific timeframe chart |
| 3 | **Outcome Grid** | True/False outcome panels with detailed stats |
| 4 | **HOD/LOD Analysis** | Time histograms filtered to session context |
| 5 | **Session Levels** | Relevant reference levels for this session |

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

### 4.1 Level Definitions

| Level | Definition | Calculation |
|-------|------------|-------------|
| **PDH** | Previous Day High | High of previous trading day (18:00 - 18:00) |
| **PDL** | Previous Day Low | Low of previous trading day |
| **PDM** | Previous Day Mid | (PDH + PDL) / 2 |
| **P12 High** | Overnight High | High from 18:00 to 06:00 |
| **P12 Low** | Overnight Low | Low from 18:00 to 06:00 |
| **P12 Mid** | Overnight Midpoint | (P12 High + P12 Low) / 2 |
| **Daily Open** | Globex Open | Price at 18:00 (Asia start) |
| **Midnight Open** | Midnight Price | Price at 00:00 EST |
| **07:30 Open** | Pre-Market Open | Price at 07:30 EST |
| **Asia Mid** | Asia Session Midpoint | (Asia High + Asia Low) / 2 |
| **London Mid** | London Session Midpoint | (London High + London Low) / 2 |
| **NY1 Mid** | NY1 Session Midpoint | (NY1 High + NY1 Low) / 2 |
| **NY2 Mid** | NY2 Session Midpoint | (NY2 High + NY2 Low) / 2 |

### 4.2 Session-Specific Levels
Each session tab displays only relevant levels:

| Session | Displayed Levels |
|---------|------------------|
| **Asia** | Daily Open, PDH, PDL, PDM, P12 H/M/L, Asia Mid |
| **London** | Midnight Open, Asia Mid, London Mid, PDH, PDL |
| **NY1** | 07:30 Open, London Mid, NY1 Mid, Asia Mid |
| **NY2** | NY1 Mid, NY2 Mid, London Mid |

### 4.3 Level Statistics
For each level, display:
- **Touch Rate**: % of filtered days where level was touched
- **Mode Time**: Most common time bucket when touched
- **Median Time**: Median time for touches
- **Time Histogram**: Distribution of touch times

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
| **Header-Style Chart Tooltips** | Fixed header, not floating |
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
| **Backend Optimization** | Vectorized price model generation |

### In Progress 🔄

| Feature | Notes |
|---------|-------|
| **Outcome Panel Grid** | Needs integration in session tabs |
| **Session-Specific Levels** | `limitLevels` prop added, needs verification |

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
