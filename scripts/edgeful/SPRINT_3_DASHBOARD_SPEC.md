# Sprint 3: Interactive Edgeful-Style Dashboard

## Overview

Build a web-based conditional probability query engine for macro research data. The user selects filters (macro window, Judas classification, VIX regime, day of week, etc.) and the dashboard instantly shows probability distributions, sample sizes, and outcome statistics for the filtered subset. Think Edgeful, but purpose-built for ICT macro analysis.

**Tech Stack:**
- **Frontend:** Next.js (existing project infrastructure) with React components
- **Query Engine:** DuckDB-WASM (client-side) or DuckDB Node binding (API routes) reading parquet files directly
- **Data Source:** `macro_records.parquet` and `fvg_detail.parquet` from Sprint 2
- **Reference Data:** Prisma DB (SQLite) for news/events, calendar data

**Design Principle:** Every interaction is a groupby-filter-aggregate on the parquet tables. No pre-computed dashboards — everything is dynamic based on the user's filter selections.

---

## Architecture

### Option A: DuckDB-WASM (Client-Side) — Recommended for MVP

```
Browser
├── Load macro_records.parquet into DuckDB-WASM on page load
├── User selects filters → construct SQL query → execute in-browser
├── Results render immediately (no network round-trip for queries)
└── Parquet files served as static assets from /public or API route
```

**Pros:** Zero-latency queries, no backend query API needed, works offline after initial load.
**Cons:** ~50MB parquet file needs to download on first visit. Acceptable for a research tool.

### Option B: DuckDB Node (Server-Side API Routes)

```
Browser → API Route (/api/query) → DuckDB reads parquet on server → JSON response
```

**Pros:** No large download for client, can handle bigger datasets.
**Cons:** Network latency per query, need to build API layer.

**Recommendation:** Start with Option A (client-side DuckDB-WASM). The dataset is small enough (~800K rows macro_records, ~300K rows fvg_detail). If performance becomes an issue, migrate to Option B. The SQL queries are identical either way.

---

## Page Layout

### Single-Page Application with Three Panels

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Macro Research Dashboard                               │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│   FILTER     │              RESULTS PANEL                       │
│   PANEL      │                                                  │
│   (Left      │  ┌─────────────────────────────────────────┐    │
│   Sidebar)   │  │  Summary Cards (sample size, win rate,  │    │
│              │  │  avg continuation, avg reversion)        │    │
│   - Macro    │  └─────────────────────────────────────────┘    │
│     Window   │                                                  │
│   - Judas    │  ┌─────────────────────────────────────────┐    │
│     Class    │  │  Distribution Charts                     │    │
│   - Indicator│  │  (inflection timing, MFE/MAE, etc.)     │    │
│     Class    │  └─────────────────────────────────────────┘    │
│   - VIX      │                                                  │
│     Regime   │  ┌─────────────────────────────────────────┐    │
│   - Day of   │  │  Conditional Probability Table           │    │
│     Week     │  │  (cross-tab of selected dimensions)      │    │
│   - Event    │  └─────────────────────────────────────────┘    │
│     Filter   │                                                  │
│   - Instru-  │  ┌─────────────────────────────────────────┐    │
│     ment     │  │  Drill-Down Table                        │    │
│   - Date     │  │  (individual macro instances)             │    │
│     Range    │  └─────────────────────────────────────────┘    │
│              │                                                  │
├──────────────┴──────────────────────────────────────────────────┤
│  FOOTER: Record count, query time, last data update             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Filter Panel Specification

### Primary Filters (Always Visible)

Each filter is a multi-select dropdown or toggle group. All filters combine with AND logic. Selecting nothing in a filter means "all values" (no restriction).

| Filter | Type | Options | Source Column |
|--------|------|---------|---------------|
| Instrument | Multi-select | ES, NQ, YM, RTY, CL, GC | `instrument` |
| Macro Window | Multi-select | All 24 standard + 3 Hydra. Group by: ICT Named / All Hours / Hydra | `macro_name_raw`, `ict_alias` |
| Judas Classification | Multi-select | bullish_judas, bearish_judas, trend_up, trend_down, neutral | `judas_classification` |
| Indicator Classification | Multi-select | Accum, Expansion, Manip | `indicator_label` |
| VIX Regime | Multi-select | low, medium, high, extreme | `vix_regime` |
| Day of Week | Multi-select | Monday through Friday | `day_of_week` |
| Date Range | Date picker (start/end) | Full history or custom range | `trading_date` |

### Secondary Filters (Collapsible "Advanced" Section)

| Filter | Type | Options | Source Column |
|--------|------|---------|---------------|
| Real Direction | Multi-select | up, down | `real_direction` |
| Has FVG | Toggle | Yes / No / Any | `has_fvg` |
| Is Complete | Toggle | Yes / No / Any | `is_complete` |
| News Within 60m | Toggle | Yes / No / Any | `news_within_60m` |
| Is OpEx Week | Toggle | Yes / No / Any | `is_opex_week` |
| Open vs Midnight | Multi-select | above, below | `open_vs_midnight` |
| Open vs Daily Open | Multi-select | above, below | `open_vs_daily_open` |
| Open vs RTH Bar | Multi-select | above, below, inside | `macro_open_vs_rth_bar` |
| Prior Macro Direction | Multi-select | up, down | `prior_macro_real_direction` |
| Same Direction as Prior | Toggle | Yes / No / Any | `same_direction_as_prior` |
| Macro Streak | Range slider | 1 to 10+ | `macro_streak` |
| Macro Range Percentile | Range slider | Min to Max % | `macro_range_pct` |
| Judas First | Toggle | Yes / No / Any | `judas_first` |

### Filter State Management

- All filter state stored in React state (useState or useReducer)
- Filter changes trigger a new DuckDB SQL query
- Debounce filter changes by 200ms to avoid rapid re-queries during multi-select
- URL query params sync with filter state for shareable links
- "Reset All" button clears all filters

---

## Results Panel Specification

### 1. Summary Cards (Top Row)

Four to six key metrics that update instantly with filter changes:

| Card | Metric | SQL |
|------|--------|-----|
| Sample Size | Total macro count matching filters | `COUNT(*)` |
| Judas Rate | % of macros that are bullish_judas or bearish_judas | `COUNT(CASE WHEN judas_classification LIKE '%judas%') / COUNT(*)` |
| Avg Continuation | Mean post_macro_continuation_pct | `AVG(post_macro_continuation_pct)` |
| Avg Reversion | Mean post_macro_reversion_pct | `AVG(post_macro_reversion_pct)` |
| Continuation Win Rate | % where continuation > reversion | `COUNT(CASE WHEN post_macro_continuation_pct > post_macro_reversion_pct) / COUNT(*)` |
| Avg MFE | Mean post_macro_mfe_pct | `AVG(post_macro_mfe_pct)` |

**Critical UX rule:** Always display the sample size prominently. A 90% win rate on 8 samples is meaningless. Use color coding: green if N > 100, yellow if 30-100, red if < 30.

### 2. Distribution Charts

Configurable chart area. User selects which distribution to view from a dropdown:

**Chart Options:**

| Chart | X-Axis | Type | Description |
|-------|--------|------|-------------|
| Inflection Timing | Minutes into macro (0-20) | Histogram | When does the Judas extreme occur? Tests the "10 minute" hypothesis |
| Judas Magnitude | % of macro open | Histogram | How large is the Judas swing? |
| Real Move Magnitude | % of macro open | Histogram | How large is the real move? |
| Judas-to-Real Ratio | Ratio | Histogram | Trap size relative to real move |
| Post-Macro Continuation | % | Histogram | How far does price continue? |
| Post-Macro Reversion | % | Histogram | How far does price revert? |
| MFE Distribution | % | Histogram | Max favorable excursion distribution |
| MAE Distribution | % | Histogram | Max adverse excursion distribution |
| Macro Range | % | Histogram | Overall macro volatility |
| FVG Fill Depth | 0-100% | Histogram | How deep do FVGs get filled? (from fvg_detail) |
| FVG Hold Rate by Phase | judas/transition/real_move | Bar chart | Which phase FVGs hold best? |
| Classification by Hour | Hour of day | Stacked bar | Judas rate by macro window |
| Continuation by Day | Day of week | Bar chart | Which days continue most? |

**Chart library:** Recharts (already available in the artifact environment) or Chart.js.

### 3. Conditional Probability Table (Cross-Tab)

This is the core Edgeful feature. User selects two dimensions and the table shows the probability of an outcome for each combination.

**Configuration:**
- Row dimension: dropdown (any categorical column)
- Column dimension: dropdown (any categorical column)
- Value metric: dropdown (continuation rate, avg MFE, avg continuation_pct, judas rate, etc.)

**Example output:**

*Row: indicator_label, Column: judas_classification, Value: avg post_macro_continuation_pct*

| | bullish_judas | bearish_judas | trend_up | trend_down |
|---|---|---|---|---|
| Accum | 0.042% (N=12,340) | 0.038% (N=11,890) | 0.051% (N=8,230) | 0.047% (N=7,990) |
| Expansion | 0.061% (N=9,870) | 0.058% (N=10,120) | 0.072% (N=6,540) | 0.069% (N=6,890) |
| Manip | 0.028% (N=4,560) | 0.025% (N=4,230) | 0.031% (N=3,120) | 0.029% (N=3,450) |

Each cell shows the metric value AND the sample size. Cells with N < 30 are grayed out / flagged.

**SQL pattern:**
```sql
SELECT 
    {row_dimension},
    {col_dimension},
    AVG({metric}) as value,
    COUNT(*) as n
FROM macro_records
WHERE {all_filter_conditions}
GROUP BY {row_dimension}, {col_dimension}
```

### 4. Drill-Down Table

A sortable, paginated table showing individual macro instances matching the current filters. Clicking a row could expand to show FVG details for that macro.

**Default columns:**
- trading_date, instrument, macro_name_raw, ict_alias
- judas_classification, indicator_label
- macro_range_pct, judas_magnitude_pct, real_move_magnitude_pct
- post_macro_continuation_pct, post_macro_reversion_pct
- fvg_count, has_fvg

**Sortable** by any column. **Paginated** at 50 rows per page.

---

## SQL Query Construction

### Dynamic WHERE Clause Builder

Every filter maps to a SQL condition. The query engine concatenates active filters:

```javascript
function buildWhereClause(filters) {
    const conditions = [];
    
    if (filters.instruments.length > 0) {
        conditions.push(`instrument IN (${filters.instruments.map(i => `'${i}'`).join(',')})`);
    }
    if (filters.macroWindows.length > 0) {
        conditions.push(`macro_name_raw IN (${filters.macroWindows.map(m => `'${m}'`).join(',')})`);
    }
    if (filters.judasClass.length > 0) {
        conditions.push(`judas_classification IN (${filters.judasClass.map(j => `'${j}'`).join(',')})`);
    }
    if (filters.vixRegime.length > 0) {
        conditions.push(`vix_regime IN (${filters.vixRegime.map(v => `'${v}'`).join(',')})`);
    }
    if (filters.dayOfWeek.length > 0) {
        conditions.push(`day_of_week IN (${filters.dayOfWeek.map(d => `'${d}'`).join(',')})`);
    }
    if (filters.dateRange.start) {
        conditions.push(`trading_date >= '${filters.dateRange.start}'`);
    }
    if (filters.dateRange.end) {
        conditions.push(`trading_date <= '${filters.dateRange.end}'`);
    }
    // ... additional filters
    
    return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}
```

### Query Templates

**Summary cards:**
```sql
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN judas_classification IN ('bullish_judas', 'bearish_judas') THEN 1 END) * 100.0 / COUNT(*) as judas_rate,
    AVG(post_macro_continuation_pct) as avg_continuation,
    AVG(post_macro_reversion_pct) as avg_reversion,
    COUNT(CASE WHEN post_macro_continuation_pct > post_macro_reversion_pct THEN 1 END) * 100.0 / COUNT(*) as continuation_win_rate,
    AVG(post_macro_mfe_pct) as avg_mfe
FROM macro_records
{WHERE_CLAUSE}
```

**Histogram data:**
```sql
SELECT 
    FLOOR({column} / {bin_width}) * {bin_width} as bin_start,
    COUNT(*) as count
FROM macro_records
{WHERE_CLAUSE}
AND {column} IS NOT NULL
GROUP BY bin_start
ORDER BY bin_start
```

**Cross-tab:**
```sql
SELECT 
    {row_dim},
    {col_dim},
    AVG({metric}) as value,
    COUNT(*) as n
FROM macro_records
{WHERE_CLAUSE}
GROUP BY {row_dim}, {col_dim}
ORDER BY {row_dim}, {col_dim}
```

**Drill-down (paginated):**
```sql
SELECT *
FROM macro_records
{WHERE_CLAUSE}
ORDER BY {sort_column} {sort_direction}
LIMIT {page_size} OFFSET {page * page_size}
```

---

## FVG Analysis Tab

A separate tab or section for FVG-specific analysis. This queries `fvg_detail.parquet` instead of (or joined to) `macro_records.parquet`.

### FVG-Specific Filters
- FVG Type: bullish / bearish
- Phase: judas_phase / transition / real_move_phase
- Is First Presented: Yes / No
- Is Silver Bullet: Yes / No
- Was Tested: Yes / No
- Held: Yes / No
- Failed: Yes / No

### FVG Metrics
- Total FVGs matching filters
- Test rate (% tested)
- Hold rate (% that held after testing)
- Fail rate (% that failed)
- Average fill depth
- Average test time (minutes)
- Average FVG size (% of macro open)

### FVG Distribution Charts
- Fill depth distribution (0-100%)
- Test time distribution (minutes)
- FVG size distribution
- Hold rate by phase (bar chart)
- Hold rate by FVG tag (first_presented vs others)

---

## DuckDB-WASM Integration

### Setup (Next.js)

```javascript
// lib/duckdb.js
import * as duckdb from '@duckdb/duckdb-wasm';

let db = null;
let conn = null;

export async function initDuckDB() {
    if (db) return { db, conn };
    
    const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
    const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);
    
    const worker = new Worker(bundle.mainWorker);
    const logger = new duckdb.ConsoleLogger();
    db = new duckdb.AsyncDuckDB(logger, worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    conn = await db.connect();
    
    return { db, conn };
}

export async function loadParquet(db, name, url) {
    // Register remote parquet file
    await db.registerFileURL(name, url, duckdb.DuckDBDataProtocol.HTTP, false);
    // Or for local files served from /public:
    // const response = await fetch(url);
    // const buffer = await response.arrayBuffer();
    // await db.registerFileBuffer(name, new Uint8Array(buffer));
}

export async function query(conn, sql) {
    const result = await conn.query(sql);
    return result.toArray().map(row => row.toJSON());
}
```

### Data Loading Strategy

On dashboard page mount:
1. Initialize DuckDB-WASM
2. Fetch `macro_records.parquet` and `fvg_detail.parquet` from the server
3. Register them as tables in DuckDB
4. Run initial unfiltered summary query
5. Dashboard is ready for interactive filtering

```javascript
// On page load
const { db, conn } = await initDuckDB();
await loadParquet(db, 'macro_records.parquet', '/api/data/macro_records');
await loadParquet(db, 'fvg_detail.parquet', '/api/data/fvg_detail');

// Create views for convenience
await conn.query(`CREATE VIEW macros AS SELECT * FROM 'macro_records.parquet'`);
await conn.query(`CREATE VIEW fvgs AS SELECT * FROM 'fvg_detail.parquet'`);
```

### API Route to Serve Parquet Files

```javascript
// pages/api/data/[filename].js
import { readFileSync } from 'fs';
import path from 'path';

export default function handler(req, res) {
    const { filename } = req.query;
    const filePath = path.join(process.env.DERIVED_DATA_DIR, filename);
    const data = readFileSync(filePath);
    res.setHeader('Content-Type', 'application/octet-stream');
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.send(data);
}
```

---

## Component Structure

```
web/app/research/macros/
├── page.tsx                    # Main dashboard page
├── components/
│   ├── FilterPanel.tsx         # Left sidebar with all filters
│   ├── SummaryCards.tsx        # Top-row metric cards
│   ├── DistributionChart.tsx   # Configurable histogram/bar chart
│   ├── CrossTab.tsx            # Conditional probability table
│   ├── DrillDownTable.tsx      # Paginated individual records
│   ├── FVGAnalysis.tsx         # FVG-specific tab/section
│   └── QueryStatus.tsx         # Shows record count, query time
├── hooks/
│   ├── useDuckDB.ts            # DuckDB initialization and query hook
│   ├── useFilters.ts           # Filter state management
│   └── useQueryBuilder.ts      # SQL construction from filter state
└── lib/
    ├── duckdb.ts               # DuckDB-WASM setup utilities
    ├── queries.ts              # SQL template functions
    └── types.ts                # TypeScript interfaces for filter state, results
```

---

## Implementation Order

### Phase 1: Foundation (Get data queryable in the browser)
1. Set up DuckDB-WASM in Next.js
2. API route to serve parquet files
3. Basic page that loads data and runs a test query
4. Verify data loads correctly and queries return expected results

### Phase 2: Filter Panel + Summary Cards
1. Build FilterPanel component with primary filters
2. Build useFilters hook for state management  
3. Build useQueryBuilder hook for SQL construction
4. Build SummaryCards component
5. Wire filters → query → summary cards (end-to-end reactivity)

### Phase 3: Distribution Charts
1. Build DistributionChart component with chart selector dropdown
2. Implement histogram query for each chart option
3. Add Recharts rendering
4. Wire to filter state

### Phase 4: Cross-Tab + Drill-Down
1. Build CrossTab component with dimension/metric selectors
2. Implement cross-tab SQL query
3. Build DrillDownTable with pagination and sorting
4. Wire to filter state

### Phase 5: FVG Analysis
1. Build FVGAnalysis component with FVG-specific filters
2. Implement FVG metric queries (joined to macro_records for context)
3. Add FVG distribution charts

### Phase 6: Polish
1. URL query param sync for shareable links
2. Loading states and error handling
3. Export filtered results as CSV
4. Responsive layout
5. Dark mode (matches TradingView aesthetic)

---

## Key UX Requirements

1. **Sub-second query response.** DuckDB-WASM on ~800K rows should return in <100ms. If not, add a loading spinner but never block the UI.

2. **Sample size always visible.** Every metric, every chart, every cell in the cross-tab shows N. Color code: green (N>100), yellow (N=30-100), red (N<30).

3. **No empty states.** If filters produce zero results, show a clear message: "No macros match these filters. Try broadening your selection."

4. **Progressive disclosure.** Primary filters always visible. Advanced filters collapsed by default. FVG analysis is a separate tab.

5. **Dark theme.** Research tool for a trader — dark background, high contrast text, chart colors that match TradingView's palette.

6. **Comparison mode (Sprint 4+).** Side-by-side panels where user can set different filter conditions and compare outcome distributions. Not for MVP, but design the layout to accommodate it.

---

## Data Refresh Strategy

The parquet files are static outputs of the Sprint 2 pipeline. When the pipeline runs (daily or on-demand), it overwrites the parquet files. The dashboard picks up new data on next page load (or with a manual refresh button).

For the MVP, this is sufficient. No real-time streaming, no WebSocket updates. The research tool operates on historical data that updates at most once per day.

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Initial page load (including parquet download) | < 5 seconds |
| Query response time (any filter combination) | < 200ms |
| Chart render time | < 100ms |
| Cross-tab computation | < 300ms |
| Drill-down pagination | < 100ms |

These are achievable with DuckDB-WASM on the dataset sizes we're working with. If the FVG detail table is too large for client-side, we can serve it via API routes (Option B) while keeping macro_records client-side.

---

## Future Enhancements (Sprint 4+)

- **Comparison mode:** Side-by-side filter panels
- **Custom scenario builder:** Name and save filter combinations as "scenarios"
- **Alert rules:** "When a macro matching [scenario X] occurs live, notify me"
- **Pine Script export:** Generate Pine Script code from statistically validated rules
- **Backtest simulator:** Walk-forward test of strategies using the probability tables
- **GEX/DEX overlay:** Integrate options flow data as additional filter dimensions
- **Multi-timeframe FVG:** Toggle between 1-minute and 5-minute FVG analysis
