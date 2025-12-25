# Indicators Architecture

This document describes the architecture and design patterns used in the charting indicators system.

## Overview

Indicators are implemented as lightweight-charts `ISeriesPrimitive` plugins that render custom visualizations on the chart. They process OHLC data and generate visual overlays like session boxes, lines, and levels.

## Directory Structure

```
web/lib/charts/indicators/
├── types.ts                    # Core indicator interfaces
├── index.ts                    # Exports
│
├── vwap.ts                     # VWAP indicator
├── vwap.worker.ts              # VWAP calculation worker
├── vwap-worker-manager.ts      # VWAP worker manager
│
├── daily-profiler.ts           # Session profiler (Asia, London, NY, etc.)
├── profiler.worker.ts          # DailyProfiler calculation worker
├── profiler-worker-manager.ts  # DailyProfiler worker manager
│
├── hourly-profiler.ts          # Hourly/3-hour period profiler
├── hourly-profiler.worker.ts   # HourlyProfiler calculation worker
├── hourly-profiler-worker-manager.ts
│
├── opening-range.ts            # Opening range indicator
├── range-extensions.ts         # Range extension levels
├── ema.ts / sma.ts / rsi.ts / macd.ts  # Standard indicators
└── ...
```

---

## Web Worker Pattern

### Motivation

Heavy calculations (session detection, VWAP rolling, period aggregation) can block the main thread during:
- Initial data load (100K+ bars)
- Scroll events triggering recalculation
- Dynamic range updates

### Architecture

```
┌─────────────────┐      postMessage      ┌──────────────────┐
│   Main Thread   │ ───────────────────▶  │    Web Worker    │
│                 │                        │                  │
│  indicator.ts   │                        │  *.worker.ts     │
│  setData()      │      result           │  calculateXXX()  │
│  update()       │ ◀───────────────────  │                  │
└─────────────────┘                        └──────────────────┘
         │
         ▼
  ┌─────────────────┐
  │  Worker Manager │  (Singleton, request tracking, timeout handling)
  └─────────────────┘
```

### Pattern Implementation

Each indicator with Web Worker support has 3 files:

1. **`*.worker.ts`** - Pure calculation logic (no DOM/chart dependencies)
   ```typescript
   // Extract pure functions (no chart API calls)
   function calculateXXX(data): Result { ... }
   
   self.onmessage = (e) => {
       const result = calculateXXX(e.data.input);
       self.postMessage({ id: e.data.id, success: true, result });
   };
   ```

2. **`*-worker-manager.ts`** - Async API wrapper
   ```typescript
   class WorkerManager {
       private worker: Worker | null = null;
       private pendingRequests = new Map<string, PendingRequest>();
       
       async calculate(input): Promise<Result> {
           // Create worker lazily, track requests, handle timeout
       }
   }
   
   // Export singleton getter
   export function getXXXWorker(): WorkerManager { ... }
   ```

3. **Main indicator file** - Uses worker with fallback
   ```typescript
   public setData(data: any[]) {
       if (typeof Worker !== 'undefined') {
           import('./xxx-worker-manager').then(({ getXXXWorker }) => {
               getXXXWorker().calculate({ data }).then((result) => {
                   this._data = result;
                   this._requestUpdate();
               }).catch((e) => {
                   // Fallback to main thread
                   this._calculateXXX(data);
                   this._requestUpdate();
               });
           });
       } else {
           this._calculateXXX(data);
           this._requestUpdate();
       }
   }
   ```

### Key Design Decisions

1. **Dynamic import** - Worker manager is lazy-loaded to avoid bundling issues
2. **Main thread fallback** - Always works if Worker fails or unavailable
3. **Singleton workers** - One worker per indicator type, reused across instances
4. **Request ID tracking** - Handles concurrent calls correctly
5. **Timeout handling** - 10-15 second timeout prevents hanging

---

## Indicator Lifecycle

```
1. Constructor   →  Initialize options, create formatter
2. attached()    →  Store requestUpdate callback
3. setData()     →  Calculate data (async via worker or sync)
4. paneViews()   →  Return renderer for drawing
5. update()      →  (Optional) Recalculate on visible range change
6. detached()    →  Cleanup
7. destroy()     →  Remove event listeners, terminate workers
```

---

## Performance Optimizations

### Calculation Optimizations
| Technique | Used In | Benefit |
|-----------|---------|---------|
| Web Worker | VWAP, DailyProfiler, HourlyProfiler | Off-thread calculation |
| Binary search | VWAP, Profilers | O(log n) vs O(n) lookups |
| Cached DateTimeFormat | All profilers | Avoid expensive object creation |
| Reduced lookback | VWAP | Limit historical scanning |

### Rendering Optimizations
| Technique | Used In | Benefit |
|-----------|---------|---------|
| Visible range culling | All profilers | Skip off-screen elements |
| Pre-calculated colors | HourlyProfiler | Avoid per-frame hex parsing |
| Draw count limits | Profilers | Cap at 100 items visible |

---

## Adding a New Indicator

1. Create `indicators/my-indicator.ts` implementing `ISeriesPrimitive`
2. (Optional) If heavy calculation needed:
   - Create `my-indicator.worker.ts` with pure calculation
   - Create `my-indicator-worker-manager.ts`
   - Use async pattern in `setData()`
3. Export from `indicators/index.ts`
4. Register in chart hook (`use-chart.ts`)

---

## Testing Considerations

- Web Workers require proper bundler config (Vite/Webpack handles this)
- Workers run in separate context (no DOM, no imports from main app)
- Always test fallback path (disable workers in DevTools)
