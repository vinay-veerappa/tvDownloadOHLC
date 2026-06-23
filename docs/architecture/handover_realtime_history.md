# Handover Document: Live Streaming Updates & Wick Rendering Fix in History Mode

This document serves as a complete technical guide for implementing **Live Streaming Updates in History Mode** and resolving the **projected candle wick rendering bug**. These updates should be applied when the Schwab spoke/hub is online and the market is active.

---

## 1. Technical Analysis: Wick Rendering Bug

### The Symptom
When a new projected candle is first rendered, the wick on the opening side is often flat. Specifically:
- In a **Bullish candle** (open is lower than close), the bottom of the candle is flat (open = low), and no lower wick renders even if the price fluctuates.
- In a **Bearish candle** (open is higher than close), the top of the candle is flat (open = high), and no upper wick renders.

### The Root Cause
Inside [use-chart-data.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/hooks/chart/use-chart-data.ts), when a new projected candle is initialized, the developer incorrectly assumed that the `open` price of the new candle should be the previous candle's close (`lastCandle.close`), while `high` and `low` were set strictly to the current `livePrice` (the first tick of the new bar):

```typescript
// Start a new projected candle (BUGGY INITIALIZATION)
candle = {
    ticker,
    timeframe,
    time: newCandleTime,
    open: lastCandle.close,
    high: livePrice,
    low: livePrice,
    close: livePrice
}
```

This assumption fails because the opening price of a new candle is defined by the **very first trade/tick inside that new candle's interval**, not the close of the previous candle (which leaves gaps unrepresented).

If the first live tick of the new bar ($102$) is higher than the previous close ($100$):
1. `open` = $100$ (previous close)
2. `low` = $102$ (first tick)
3. `close` = $102$

This creates a structurally invalid candle where **`low > open`** (the low lies inside the body). Lightweight Charts requires that `low <= Math.min(open, close)` and `high >= Math.max(open, close)`. Because the low ($102$) is higher than the open ($100$), the library clamps the low to the body bottom ($100$), rendering a flat bottom (no lower wick). A bottom wick would only render if price later dropped below the previous close ($100$).

### The Solution
Initialize the `open` price to the current `livePrice` (which is the actual first tick of the new bar). When a candle first opens, all its values (`open`, `high`, `low`, `close`) should start at the first tick price (`livePrice`). Wicks will then form naturally and correctly as subsequent ticks move:

```typescript
// Start a new projected candle (CORRECT INITIALIZATION)
candle = {
    ticker,
    timeframe,
    time: newCandleTime,
    open: livePrice, // Correctly set the open to the first tick price
    high: livePrice,
    low: livePrice,
    close: livePrice
}
```


---

## 2. Implementation Steps for Live Updates in History Mode

To implement real-time streaming in History Mode, apply the following steps sequentially.

### Phase 1: Modify `use-data-loading.ts`
File: [use-data-loading.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/hooks/chart/use-data-loading.ts)

1. Add `liveUpdatesEnabled?: boolean` to `UseDataLoadingProps` and default it to `false`.
2. Add a `historyLoaded` state:
   ```typescript
   const [historyLoaded, setHistoryLoaded] = useState(false)
   const [livePrice, setLivePrice] = useState<number | null>(null)
   const [lastUpdate, setLastUpdate] = useState<string | null>(null)
   const liveRawDataRef = useRef<OHLCData[]>([])
   const wsRef = useRef<WebSocket | null>(null)
   const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
   const retryCountRef = useRef(0)
   const resamplingSequenceRef = useRef<number>(0)
   ```
3. Inside the initial load `useEffect` (`loadData` function):
   - Set `setHistoryLoaded(false)` and reset the live refs/states on entry.
   - After successfully loading parquet data, if `liveUpdatesEnabled` is `true`, fetch the live cache from the Schwab hub:
     ```typescript
     try {
         const liveRes = await fetch(`/api/history?symbol=${encodeURIComponent(ticker)}&limit=5000`, { cache: 'no-store' })
         if (liveRes.ok) {
             const json = await liveRes.json()
             if (json && json.success && json.data && json.data.candles) {
                 const liveCandles = json.data.candles
                 
                 // Normalize live candles (handle ms to seconds conversion)
                 const formattedLive = liveCandles.map((c: any) => ({
                     time: c.time > 10000000000 ? c.time / 1000 : c.time,
                     open: c.open,
                     high: c.high,
                     low: c.low,
                     close: c.close,
                     volume: c.volume
                 }))
                 liveRawDataRef.current = formattedLive
                 
                 // Resample live data to match current timeframe
                 const processedLive = await processLiveData(liveRawDataRef.current, timeframe)
                 // Merge with the parquet data
                 finalData = mergeDatasets(finalData, processedLive)
             }
         }
     } catch (e) {
         console.error("[useDataLoading] Live cache fetch failed:", e)
     }
     ```
   - Call `setHistoryLoaded(true)` at the end of `loadData`.
4. Add the `processAndMergeWebSocketCandles` callback:
   ```typescript
   const processAndMergeWebSocketCandles = useCallback(async (rawCandles: any[], isInitial: boolean) => {
       if (rawCandles.length === 0) return;
       const currentSeq = ++resamplingSequenceRef.current;

       const formatted: OHLCData[] = rawCandles.map((c: any) => ({
           time: c.time > 10000000000 ? c.time / 1000 : c.time,
           open: c.open,
           high: c.high,
           low: c.low,
           close: c.close,
           volume: c.volume
       }));

       if (isInitial) {
           liveRawDataRef.current = formatted;
       } else {
           const combined = [...liveRawDataRef.current, ...formatted];
           combined.sort((a, b) => a.time - b.time);

           const unique: OHLCData[] = [];
           if (combined.length > 0) {
               unique.push(combined[0]);
               for (let i = 1; i < combined.length; i++) {
                   const current = combined[i];
                   const last = unique[unique.length - 1];
                   if (current.time === last.time) {
                       unique[unique.length - 1] = current;
                   } else {
                       unique.push(current);
                   }
               }
           }
           liveRawDataRef.current = unique;
       }

       const resampledLive = await processLiveData(liveRawDataRef.current, timeframe);
       if (currentSeq !== resamplingSequenceRef.current) return;

       setFullData(prev => {
           const merged = mergeDatasets(prev, resampledLive);
           if (merged.length > 0) {
               leftBoundaryRef.current = merged[0].time;
               rightBoundaryRef.current = merged[merged.length - 1].time;
           }
           return merged;
       });
   }, [timeframe]);
   ```
5. Add a `useEffect` to connect to the WebSocket:
   - Connect to `ws://${host}:8001/stream?symbol=${encodeURIComponent(ticker)}&timeframe=${encodeURIComponent(timeframe)}`.
   - On `snapshot`: Call `processAndMergeWebSocketCandles(msg.candles, false)`.
   - On `candle`: Call `processAndMergeWebSocketCandles([msg.candle], false)`.
   - On `quote`: Update `livePrice`, `lastUpdate`, and update the last candle in `fullData` in-place (following the same structure as `useLiveDataLoading`).
6. Return `livePrice` and `lastUpdate` from the hook.

### Phase 2: Modify `use-chart-data.ts`
File: [use-chart-data.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/hooks/chart/use-chart-data.ts)

1. Pass `liveUpdatesEnabled: mode === 'historical'` to `useDataLoading`.
2. Update the `data` memoization logic to enable active candle projection when not replaying:
   ```typescript
   const data = useMemo(() => {
       const baseData = replay.data
       const showLiveUpdates = mode === 'live' || (mode === 'historical' && !replay.replayMode)
       
       if (showLiveUpdates && baseData.length > 0) {
           const liveStore = loading as any
           const livePrice = liveStore.livePrice
           const lastUpdate = liveStore.lastUpdate

           if (livePrice !== null && livePrice !== undefined) {
               const enriched = [...baseData]
               const lastIdx = enriched.length - 1
               const lastCandle = { ...enriched[lastIdx] }

               // Determine if we should project a NEW candle
               let shouldProjectNew = false
               let newCandleTime = 0

               if (lastUpdate) {
                   const lastBarTime = lastCandle.time
                   const liveTime = Math.floor(new Date(lastUpdate).getTime() / 1000)
                   const resolutionMins = getResolutionInMinutes(timeframe)
                   const resolutionSecs = resolutionMins * 60

                   if (liveTime >= lastBarTime + resolutionSecs) {
                       newCandleTime = Math.floor(liveTime / resolutionSecs) * resolutionSecs
                       if (newCandleTime > lastBarTime) {
                           shouldProjectNew = true
                       }
                   }
               }

               if (shouldProjectNew) {
                   const ref = liveCandleRef.current
                   let candle: any
                   if (ref && ref.ticker === ticker && ref.timeframe === timeframe && ref.time === newCandleTime) {
                       ref.close = livePrice
                       ref.high = Math.max(ref.high, livePrice)
                       ref.low = Math.min(ref.low, livePrice)
                       candle = ref
                    } else {
                        // Corrected initialization to fix flat wick bug!
                        candle = {
                            ticker,
                            timeframe,
                            time: newCandleTime,
                            open: livePrice, // Correctly set the open to the first tick price
                            high: livePrice,
                            low: livePrice,
                            close: livePrice
                        }
                        liveCandleRef.current = candle
                    }

                   enriched.push({
                       time: candle.time,
                       open: candle.open,
                       high: candle.high,
                       low: candle.low,
                       close: candle.close,
                       volume: 0
                   })
               } else {
                   liveCandleRef.current = null
                   lastCandle.close = livePrice
                   lastCandle.high = Math.max(lastCandle.high, livePrice)
                   lastCandle.low = Math.min(lastCandle.low, livePrice)
                   enriched[lastIdx] = lastCandle
               }

               return enriched
           }
       }
       return baseData
   }, [replay.data, mode, (loading as any).livePrice, (loading as any).lastUpdate, timeframe, ticker, replay.replayMode])
   ```

### Phase 3: Modify `use-chart.ts`
File: [use-chart.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/hooks/use-chart.ts)

1. Add `liveUpdatesActive?: boolean` as the final parameter to the `useChart` hook.
2. In the `chartData` memo:
   ```typescript
   const isLiveMode = mode === 'live' || liveUpdatesActive;
   ```
3. This ensures that when live updates are streaming, the manual 100 whitespace dummy bars are **not** appended to the end of the array, preventing them from stealing incremental price ticks.

### Phase 4: Modify `chart-container.tsx`
File: [chart-container.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/components/chart-container.tsx)

1. Locate the call to `useChart`.
2. Pass `mode === 'historical' && !replayMode` as the `liveUpdatesActive` parameter to `useChart`.

---

## 3. Verification Protocol

Once implemented, perform the following validation checks:
1. **Wick Verification**:
   - Ensure the market is open or Schwab spoke is streaming quotes.
   - Look at the forming candle. Verify that lower wicks (for bullish candles) and upper wicks (for bearish candles) render immediately as price moves, with no flat bottoms or flat tops unless price is exactly at the extreme.
2. **Startup Synchronization**:
   - Open History Mode.
   - Verify the chart immediately shows the current time's candle (synced with Schwab in-memory buffer) instead of leaving a gap since the last parquet record.
3. **Replay Mode Isolation**:
   - Enter Replay Mode.
   - Verify that the chart stops updating with live ticks and freezes on the selected historical point.
   - Exit Replay Mode.
   - Verify the chart snaps back to the present and continues updating in real-time.
