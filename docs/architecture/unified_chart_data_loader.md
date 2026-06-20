# Unified Chart Data Loader Architecture & Handover Document

This document provides a comprehensive blueprint and handover reference for the chart data loading architecture, covering client-side resampling, bidirectional pagination, memory eviction, and the seamless integration of historical parquet files with live storage data.

---

## 1. Context & Core Problems

### Current State
* **Historical Mode (`useDataLoading`)**: Loads deep historical OHLC data from binary Parquet slices via `fetchBinaryOHLC` (port 8000). Features a robust bidirectional pagination engine, coordinate-locking to prevent scroll jumping, and a 50,000-candle eviction cap to keep the lightweight-charts rendering engine performant.
* **Live Mode (`useLiveDataLoading`)**: Loads initial streaming history from the `/api/history` NextJS proxy (pointing to the Schwab streaming API on port 8001) and connects to a WebSocket server (`ws://localhost:8001/stream`) to apply real-time quote updates to the latest bar.

### Identified Gaps
1. **Historical W/M/Y Resampling Bug**: When requesting non-native resolutions ending in `W`/`M`/`Y` (e.g. `2M`, `3M`, `6M`, `1Y`), the hook correctly loads `1D` fallback data and calls `resampleDataForWMY()`. However, it incorrectly routes the result through the worker's `resampleOHLCAsync()` which rejects calendar resolutions, rendering a blank chart.
2. **Live Resampling Calendar Drift**: In live mode, multi-month and yearly resolutions are resampled using a simple seconds-based approximation (e.g. `30 * 86400` seconds per month). This causes **calendar drift** because month lengths vary (28, 29, 30, 31 days) and leap years are ignored.
3. **Data Silos**: Historical data and live storage (Schwab parquet data cached on disk during trading hours) are currently treated as separate worlds. A trader in "History Mode" cannot view the newest live-cached candles without manually switching to "Live Mode."

---

## 2. Target Architecture: Seamless Data Fusion & Parity

To address these gaps, the system is designed around two pillars:
1. **Shared Resampling & Eviction Engine**: All client-side resampling (intraday worker-based and calendar-based W/M/Y) and pagination boundaries are managed by a single unified controller.
2. **Seamless Historical + Live Storage Merge in History Mode**: When in History Mode, the engine will query the deep historical parquets AND automatically fetch/merge the live storage cache (Schwab data) at the right boundary, rendering a single continuous chart without requiring the WebSocket connection.

### Detailed Data Pathways & Fallbacks

#### 1. Resampling Matrix
* **Intraday (e.g. `3m`, `5m`, `15m`, `1h`, `4h`)**: Loaded natively. If native is missing, resampled from `1m` using the Web Worker `resampleOHLCAsync()` (fixed-seconds division).
* **Calendar (Weekly `1W`, Monthly `1M`/`2M`/`3M`/`4M`/`6M`, Yearly `1Y`)**: Loaded natively. If native is missing, resampled from `1D` using the calendar-aligned `resampleDataForWMY()` to preserve settlement close prices.

#### 2. History Mode Data Merge Pathway
```
GIVEN the user selects History Mode for ticker NQ1 and timeframe 1D:
1. Load historical parquets from /api/ohlc/NQ1/1D (port 8000).
2. Fetch newest live-stored candles from /api/history (port 8001).
3. Align and deduplicate both datasets at the boundary (Historical ending, Live starting).
4. Merge into a single array: [Historical Parquet Bars] + [Live Storage Bars].
5. Present the seamless continuous dataset on the chart.
```

#### 3. Live Mode Pathway (No-Regress Contract)
* Continue to fetch initial data from `/api/history` and stream real-time ticks over WebSocket on port 8001 to prevent disruption to live trading execution.
* **Fix**: Replace the simple seconds-based division in `useLiveDataLoading` with the shared, high-fidelity `resampleDataForWMY()` calendar resampler, resolving the calendar drift issue.

---

## 3. The Shared Interface & Strategy Pattern

To achieve unification, we abstract transport logic from storage logic:

```typescript
export interface DataSourceProvider {
    // Initial fetch of historical bars
    fetchInitial: (ticker: string, timeframe: string) => Promise<OHLCData[]>;
    
    // Paginate left (older) or right (newer)
    fetchMore: (
        ticker: string, 
        timeframe: string, 
        boundaryTime: number, 
        direction: 'left' | 'right'
    ) => Promise<OHLCData[]>;
    
    // Live subscription (WebSocket ticks/quotes)
    subscribe?: (
        ticker: string, 
        timeframe: string, 
        onTick: (tick: { price: number; time: string; type: 'quote' | 'candle' | 'snapshot' }) => void
    ) => () => void;
}
```

### 1. `HistoricalMergeProvider` (History Mode)
* `fetchInitial`: Pulls the initial historical slice (port 8000). If it reaches the current time boundary, it fetches the latest live storage data from port 8001, merges them, deduplicates overlaps, and returns the combined set.
* `fetchMore (left)`: Requests older slices from port 8000.
* `fetchMore (right)`: Requests newer slices from port 8000, falling back to port 8001 when parquet data ends.

### 2. `LiveProvider` (Live Mode)
* `fetchInitial`: Fetches 180,000 candles from `/api/history` (port 8001).
* `subscribe`: Establishes WebSocket connection on port 8001, streaming real-time snapshots, quotes, and candle closes.

---

## 4. Specific Test Cases & Verification Protocol

Any modifications to resampling or pagination boundaries must pass these verification rules:

### Resampling Contract Tests
1. **Weekly Sunday Alignment (`1W`)**:
   * **Test**: Provide Tuesday and Wednesday candles.
   * **Assert**: Resampled candle must have a timestamp of the preceding Sunday at `00:00:00 UTC`.
2. **Multi-Month Quarterly Alignment (`3M`, `6M`)**:
   * **Test**: Provide candles spanning December to April across a leap year.
   * **Assert**: Groupings must occur exactly on calendar quarter boundaries (Jan-Mar, Apr-Jun, etc.) starting on the 1st of the month, preserving leap-day data.
3. **Yearly Alignment (`1Y`)**:
   * **Test**: Provide candles from multiple years.
   * **Assert**: Candles must align to January 1st at `00:00:00 UTC`.

### Merging & Boundary Deduplication
4. **Overlap Protection (Left & Right)**:
   * **Test**: Merge two blocks: Block A (`T = 100` to `T = 200`) and Block B (`T = 180` to `T = 300`).
   * **Assert**: The merged dataset must have unique timestamps, prioritizing the newer values from Block B for any overlapping indices (`180` to `200`).
5. **Symmetric Eviction**:
   * **Test**: Stream data beyond 50,000 bars.
   * **Assert**: The older candles must be pruned from the left, updating `hasMoreDataLeft` to `true`, and keeping the active chart size to `40,000` bars.

---

## 5. Handover Plan for Next Session

When starting a new session to implement these features, follow this step-by-step checklist:

- [ ] **Step 1: Move & Export Resampling**:
  * Cut `resampleDataForWMY` out of `web/hooks/chart/use-data-loading.ts` and paste it into `web/lib/resampling.ts` as an exportable function.
- [ ] **Step 2: Fix Historical Mode W/M/Y Bug**:
  * Edit `web/hooks/chart/use-data-loading.ts`. Locate the initial load `useEffect` and `jumpToTime` methods.
  * Wrap the `resampleOHLCAsync()` calls in a check: `if (!timeframe.endsWith('W') && !timeframe.endsWith('M') && !timeframe.endsWith('Y'))`. This prevents worker failure for W/M/Y.
- [ ] **Step 3: Create Resampling Unit Tests**:
  * Create `web/tests/resampling.test.mjs` using the built-in `node:test` framework to mock and assert all calendar grouping rules (2M, 3M, 1Y).
- [ ] **Step 4: Fix Live Mode Calendar Drift**:
  * Edit `web/hooks/chart/use-live-data-loading.ts`. Find the resampling logic (lines 84-110).
  * Integrate the exported `resampleDataForWMY` for W/M/Y timeframes instead of the seconds-based `Math.floor(candle.time / toSeconds)` loop.
- [ ] **Step 5: Implement Seamless Merger**:
  * In `use-data-loading.ts` (History Mode), when loading or paging right, call `/api/history` to load live-stored Schwab data, merge it with historical parquet data, and deduplicate overlaps.
