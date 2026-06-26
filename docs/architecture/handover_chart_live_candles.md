# Handover: Live Chart Candle Rendering — Missing Candles, Race Conditions, OHLC Accuracy & Performance

**Date:** 2026-06-26  
**Status:** In Progress — speed and missing candle issues resolved, OHLC accuracy mostly resolved but may need fine-tuning when market opens  
**Commits:** `9c9290e7` through `7ab1e80d` (10 commits on `main`)

---

## 1. Problem Summary

The charting interface had four interconnected issues when displaying live candles:

1. **Missing candles** — The previous candle (e.g., 12:40) disappeared when the next candle (12:41) completed and was never restored.
2. **Race condition on initial load** — When switching tickers, the second candle briefly appeared with real data then reverted to a flat ghost candle (stale HTTP fetch overwrote WS data).
3. **Flat top/bottom on forming candle** — The projected candle's `open` was set to `prevClose` and never updated, causing flat tops/bottoms.
4. **Slow updates** — Every WS `candle` message triggered `setFullData([...raw])` which copied 180k elements.

---

## 2. Architecture Overview

### Data Flow (Live Mode)

```
Schwab Stream
    │
    ▼
stream_chart.py (hub, port 8001)
    │
    ├── chart_handler() → broadcasts WS 'candle' messages (full OHLC for forming candle)
    ├── level_one_handler() → broadcasts WS 'quote' messages (price only, no OHLC)
    └── WS snapshot on connect → sends last 100 in-memory candles
    │
    ▼
Frontend (Next.js, port 3000)
    │
    ├── use-live-data-loading.ts (live mode)
    │   ├── HTTP fetch /api/history → loads parquet into rawDataRef + fullData state
    │   ├── WS 'snapshot' → processAndMergeCandles() + sets liveCandleRef
    │   ├── WS 'quote' → setLivePrice() + setLastUpdate() + updates liveCandleRef
    │   └── WS 'candle' → updates rawDataRef + liveCandleRef + setFullData on transitions
    │
    ├── use-data-loading.ts (historical mode with live updates)
    │   ├── HTTP fetch /api/ohlc → loads historical parquet
    │   ├── HTTP fetch /api/history → loads live parquet, merges
    │   ├── WS 'snapshot' → mergeDatasets() + sets liveCandleRef
    │   ├── WS 'quote' → setLivePrice() + setLastUpdate() + updates liveCandleRef
    │   └── WS 'candle' → updates liveRawDataRef + liveCandleRef + setFullData on transitions
    │
    ├── use-chart-data.ts (data enrichment)
    │   ├── data useMemo → reads liveCandleRef + livePrice → builds enriched array
    │   ├── shouldProjectNew=true → appends forming candle from liveCandleRef
    │   └── shouldProjectNew=false → updates last bar with liveCandleRef + livePrice
    │
    └── use-chart.ts (lightweight-charts rendering)
        ├── setData() → full replace (first load, ticker switch, backwards time)
        └── update() → incremental (last bar update or new bar appended)
```

### Key Concepts

- **`fullData`** (React state) — The complete dataset from parquet + WS transitions. Updated only on candle transitions via `setFullData(prev => prev.concat([newCandle]))`.
- **`liveCandleRef`** (React ref) — The latest forming candle's OHLC. Instant updates (no array copy). Read by the `data` useMemo on every `livePrice`/`lastUpdate` state change.
- **`livePrice`** / **`lastUpdate`** (React state) — Updated by WS `quote` messages. Trigger the `data` useMemo to re-run.
- **`rawDataRef`** (React ref) — The raw 1m candle array from HTTP fetch + WS updates. Used for `setFullData` on transitions.

---

## 3. Changes Made

### 3.1. `scripts/streaming/stream_chart.py` — Broadcast finalized candle

**Problem:** When a new candle arrived, the hub saved the previous finalized candle to parquet but never broadcast it via WebSocket. The frontend only received the new candle — the finalized previous candle was permanently missing.

**Fix:** Added `broadcast_candle` call for the finalized candle before appending the new one:

```python
# Save previous finalized candle to live parquet storage
if cdata["candles"]:
    finalized_candle = cdata["candles"][-1]
    save_candles_to_parquet(key, [finalized_candle], files["parquet"])
    # Broadcast the finalized candle so WS clients receive it
    await broadcast_candle(key, finalized_candle, "1m")
```

### 3.2. `web/hooks/chart/use-live-data-loading.ts` — Race condition + liveCandleRef + performance

**Problem 1 — Race condition:** React Strict Mode fires the reset effect twice, starting two `fetchData()` HTTP calls. The first completes → WS connects → snapshot merges real data. The second stale fetch completes and overwrites with parquet data.

**Fix 1 — Fetch sequence guard:**
```typescript
const fetchSeqRef = useRef<number>(0)

const fetchData = useCallback(async () => {
    const mySeq = ++fetchSeqRef.current;
    // ... await fetch ...
    if (mySeq !== fetchSeqRef.current) return; // Discard stale response
    // ... process data ...
}, [ticker, timeframe, processAndMergeCandles])
```

**Problem 2 — liveCandleRef never populated:** The `liveCandleRef` was only set by WS `candle` messages (infrequent). Quote messages (frequent) didn't update it.

**Fix 2 — Quote handler creates/updates liveCandleRef:**
```typescript
// In quote handler:
if (candleTime === lastRaw.time) {
    // Same candle period — update close/high/low, preserve open
    lastRaw.close = currentLivePrice;
    lastRaw.high = Math.max(lastRaw.high, currentLivePrice);
    lastRaw.low = Math.min(lastRaw.low, currentLivePrice);
    const existing = liveCandleRef.current;
    if (existing && existing.time === candleTime) {
        existing.close = currentLivePrice;
        existing.high = Math.max(existing.high, currentLivePrice);
        existing.low = Math.min(existing.low, currentLivePrice);
    } else {
        liveCandleRef.current = { ...lastRaw };
    }
} else if (candleTime > lastRaw.time) {
    // New candle period — create with open=livePrice (not prevClose)
    const existing = liveCandleRef.current;
    if (existing && existing.time === candleTime) {
        existing.close = currentLivePrice;
        existing.high = Math.max(existing.high, currentLivePrice);
        existing.low = Math.min(existing.low, currentLivePrice);
    } else {
        liveCandleRef.current = {
            time: candleTime,
            open: currentLivePrice,  // First quote price = best estimate of open
            high: currentLivePrice,
            low: currentLivePrice,
            close: currentLivePrice,
            volume: 0
        };
    }
}
```

**Problem 3 — WS candle message overwrites liveCandleRef:** The `candle` handler did `liveCandleRef.current = formattedCandle` (full replace), losing extreme high/low captured by quotes.

**Fix 3 — Merge WS candle with existing liveCandleRef:**
```typescript
const existing = liveCandleRef.current;
if (existing && existing.time === formattedCandle.time) {
    liveCandleRef.current = {
        time: formattedCandle.time,
        open: formattedCandle.open,  // hub's real open
        high: Math.max(formattedCandle.high, existing.high),  // widest range
        low: Math.min(formattedCandle.low, existing.low),     // widest range
        close: formattedCandle.close,
        volume: formattedCandle.volume
    };
} else {
    liveCandleRef.current = formattedCandle;
}
```

**Problem 4 — setFullData copies 180k array:** `setFullData([...raw])` on every WS candle message.

**Fix 4 — Only setFullData on transitions, use concat:**
```typescript
const isTransition = raw.length === 0 || formattedCandle.time > raw[raw.length - 1].time;
// ... update rawDataRef ...
if (isTransition) {
    setFullData(prev => prev.concat([formattedCandle]));  // O(1) not O(n)
}
```

### 3.3. `web/hooks/chart/use-data-loading.ts` — Same fixes for historical mode

Applied the same `fetchSeqRef`, `liveCandleRef`, quote handler, and `setFullData` concat fixes to the historical mode loader.

### 3.4. `web/hooks/chart/use-chart-data.ts` — Projection logic

**Problem:** The `data` useMemo copied the entire `baseData` array (180k elements) on every quote tick via `const enriched = [...baseData]`.

**Fix — Share prefix, only build tail:**
- `shouldProjectNew=true`: `baseData.concat(tail)` — only creates new objects for projected candles
- `shouldProjectNew=false`: `baseData.slice(0, lastIdx)` + push modified last element

**Projection logic (current state):**
```typescript
if (shouldProjectNew && lastUpdate) {
    // New candle period — append forming candle from liveCandleRef
    const tail: OHLCData[] = []
    if (liveCandle && liveCandle.time === newCandleTime && liveCandle.open !== undefined) {
        const realHigh = Math.max(liveCandle.high!, livePrice)
        const realLow = Math.min(liveCandle.low!, livePrice)
        tail.push({
            time: newCandleTime,
            open: liveCandle.open,
            high: realHigh,
            low: realLow,
            close: livePrice,
            volume: liveCandle.volume
        })
    }
    enriched = tail.length > 0 ? baseData.concat(tail) : baseData;
} else {
    // Last bar is forming candle — update with liveCandleRef + livePrice
    if (liveCandle && liveCandle.time === barTime && liveCandle.open !== undefined) {
        const realHigh = Math.max(liveCandle.high!, livePrice)
        const realLow = Math.min(liveCandle.low!, livePrice)
        enriched = baseData.slice(0, lastIdx);
        enriched.push({
            ...lastCandle,
            open: liveCandle.open,
            high: realHigh,
            low: realLow,
            close: livePrice,
            volume: liveCandle.volume
        });
    } else {
        enriched = baseData;  // No liveCandle — return as-is
    }
}
```

### 3.5. `web/hooks/use-chart.ts` — Incremental update detection

**Problem:** When the projected candle was replaced by real data from `setFullData`, the chart's last bar time went backwards (e.g., 13:24 projected → 13:23 real). `update(13:23)` tried to update an older time than the chart's last bar (13:24) → `Cannot update oldest data` error.

**Fix — Detect backwards time and force setData:**
```typescript
if (isIncremental && prevDataRef.current.length > 0 && chartData.length > 0) {
    const newLastTime = chartData[chartData.length - 1].time;
    const prevLastTime = prevDataRef.current[prevDataRef.current.length - 1].time;
    if (newLastTime < prevLastTime) {
        isIncremental = false;  // Force setData()
    }
}
```

**Debug log throttling:** Only log on `setData()` calls (transitions/first load), not on incremental `update()` calls.

### 3.6. `web/actions/data-actions.ts` — OHLCData interface

Reverted `open/high/low/close` back to required fields (not optional). Whitespace bars approach was tried but reverted — it caused `undefined` OHLC values and crashes in the legend plugin.

---

## 4. Files Modified

| File | Changes |
|------|---------|
| `scripts/streaming/stream_chart.py` | Broadcast finalized candle on transition |
| `web/hooks/chart/use-live-data-loading.ts` | `fetchSeqRef`, `liveCandleRef`, quote handler creates/updates liveCandleRef, WS candle merge, `setFullData` concat on transitions only |
| `web/hooks/chart/use-data-loading.ts` | Same fixes as above for historical mode |
| `web/hooks/chart/use-chart-data.ts` | Projection logic with `liveCandleRef`, prefix-sharing array optimization, removed `projections` cache for active candles |
| `web/hooks/use-chart.ts` | Backwards-time detection → force `setData()`, debug log throttling, Heiken Ashi whitespace filtering (may need cleanup) |
| `web/actions/data-actions.ts` | `OHLCData` interface — reverted to required fields |

---

## 5. Known Issues to Verify When Market Opens

### 5.1. Flat candle on new candle period (brief)
When a new candle period starts, the first quote creates `liveCandleRef` with `open = high = low = close = livePrice` (flat candle). This is visible for ~1-3 seconds until the price moves. The WS `candle` message later updates the `open` to the real market open.

**If still problematic:** Consider not appending the candle until the second quote arrives (so the candle has at least some range). Or wait for the WS `candle` message before showing the candle.

### 5.2. OHLC accuracy vs hub data
The `liveCandleRef` merges quote data with WS `candle` message data. The high/low should be the widest range from both sources. But if the WS `candle` message arrives with a narrower range than what quotes captured, the merge preserves the wider quote range. This should be correct, but verify against the hub's actual data.

### 5.3. Missing candle on transition
When `setFullData` is called on a candle transition (WS `candle` message with new timestamp), it uses `prev.concat([formattedCandle])`. This should add the new candle to `fullData`. But if the WS `candle` message for the transition doesn't arrive (e.g., hub restart), the candle won't be added until the next transition or a page refresh.

### 5.4. `use-chart.ts` Heiken Ashi whitespace filtering
The `chartData` memo filters out whitespace bars before Heiken Ashi calculation. Since we reverted to not using whitespace bars, this filtering is unnecessary but harmless. Can be cleaned up.

### 5.5. Debug console.log in `use-chart-data.ts`
There's still a throttled `console.log` in the `data` useMemo that logs on `shouldProjectNew=true`. This should be removed for production.

---

## 6. How to Pick Up Fast

1. **Read this document** — understand the data flow and the fixes.
2. **Check the console logs** — look for `[useChartData] project:` and `[useChart] setData:` logs.
3. **Key things to verify:**
   - `liveCandle` is NOT null when `shouldProjectNew=true` (check the log for `active=[time] O:number`)
   - The `open` value changes when the WS `candle` message arrives (should match hub's real open)
   - No `Cannot update oldest data` errors in console
   - No `undefined` OHLC values in logs
   - Candle transitions work (new candle appears, old candle preserved)
4. **If issues recur:**
   - Add `console.log` in the quote handler to trace `liveCandleRef` updates
   - Add `console.log` in the `candle` handler to trace merge behavior
   - Check if WS `candle` messages are arriving (they should broadcast on every Schwab CHART_BAR update)
   - Check `stream_chart.py` logs for `broadcast_candle` calls

---

## 7. Key Design Decisions

1. **`liveCandleRef` (ref, not state)** — Updated instantly by WS handlers without triggering React re-renders. Read by the `data` useMemo which IS triggered by `livePrice`/`lastUpdate` state changes.

2. **`setFullData` only on transitions** — Non-transition candle updates go through `liveCandleRef` → `data` useMemo → `seriesInstance.update()`. No O(n) array copy on every tick.

3. **`prev.concat([newCandle])` instead of `[...raw]`** — Shares the prefix by reference, only creates a new array with one additional element. O(1) instead of O(n).

4. **Merge WS candle with liveCandleRef** — Takes `max(high)` and `min(low)` from both sources to preserve the widest range. The hub's `open` is used (real market open).

5. **Quote handler creates liveCandleRef with `open=livePrice`** — Not `prevClose`. The first quote price is the best estimate of the opening price. The WS `candle` message later updates it to the real market open.

6. **Backwards-time detection** — When `setFullData` catches up and the enriched array's last time goes backwards, force `setData()` instead of `update()` to avoid the `Cannot update oldest data` error.

---

## 8. Commit History (newest first)

| Commit | Description |
|--------|-------------|
| `7ab1e80d` | Create liveCandleRef from first quote with open=livePrice, revert whitespace bars |
| `f5cf441e` | Use whitespace bars for new candle periods (reverted in 7ab1e80d) |
| `f4970c5c` | Merge WS candle message with liveCandleRef to preserve extreme high/low |
| `f1604482` | Re-enable projection with liveCandleRef data, detect backwards time in use-chart.ts |
| `7f9be6ab` | Stop projecting beyond fullData, preserve real open from WS candle messages |
| `f9ae6261` | Update liveCandleRef from quote handler for all candle periods, optimize setFullData |
| `7b7aa86d` | Don't render projected candles until real WS data arrives |
| `15026463` | Populate liveCandleRef from WS snapshot and quote handlers |
| `01742bca` | Use liveCandleRef for real OHLC, only setFullData on transitions, throttle debug logs |
| `9c9290e7` | Resolve ghost candles, race conditions, flat top/bottom; optimize rendering performance |