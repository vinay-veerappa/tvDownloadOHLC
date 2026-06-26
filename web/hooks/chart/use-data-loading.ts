"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getDataMetadata, OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"
import { canResample, parseTimeframeToSeconds, resampleDataForWMY } from "@/lib/resampling"
import { resampleOHLCAsync } from "@/lib/resampling-client"
import { resolutionToFolderName } from "@/lib/resolution"
import { mergeDatasets } from "@/lib/data-merger"

const fetchBinaryOHLC = async (
    ticker: string,
    tf: string,
    t_start: number,
    t_end: number,
    limit: number = 20000,
    direction: "left" | "right" = "left"
): Promise<{success: boolean, data?: OHLCData[], error?: string}> => {
    try {
        const backendTf = resolutionToFolderName(tf);
        const url = `http://127.0.0.1:8000/api/ohlc/${ticker}/${backendTf}?t_start=${t_start}&t_end=${t_end}&limit=${limit}&format=binary&direction=${direction}`;
        const res = await fetch(url);
        if (!res.ok) {
            if (res.status === 404) return { success: false, error: "Data not found" };
            return { success: false, error: `HTTP ${res.status}` };
        }
        
        const buffer = await res.arrayBuffer();
        const arr = new Float64Array(buffer); 
        
        const bars: OHLCData[] = [];
        for (let i = 0; i < arr.length; i += 5) {
            bars.push({
                time: arr[i],
                open: arr[i+1],
                high: arr[i+2],
                low: arr[i+3],
                close: arr[i+4]
            });
        }
        return { success: true, data: bars };
    } catch (e) {
        return { success: false, error: String(e) };
    }
};



// Memory limits - keep setData fast while preserving enough history
const MAX_BARS = 60000           // Hard cap
const EVICT_WHEN_OVER = 50000    // Start evicting at 50k
const EVICT_TO = 40000           // Settle at 40k (~60-80ms setData)

async function processLiveData(liveData: OHLCData[], targetTf: string): Promise<OHLCData[]> {
    if (liveData.length === 0) return [];
    
    // Normalize timestamps to seconds (Schwab API history yields milliseconds)
    const normalizedLive = liveData.map(c => ({
        ...c,
        time: c.time > 10000000000 ? c.time / 1000 : c.time
    }));
    
    const targetUpper = targetTf.toUpperCase();
    const isCalendarTf = targetUpper.endsWith('D') || 
                          targetUpper.endsWith('W') || 
                          targetUpper.endsWith('M') || 
                          targetUpper.endsWith('Y');
                          
    if (isCalendarTf) {
        return resampleDataForWMY(normalizedLive, targetTf);
    } else if (targetTf !== '1' && targetTf !== '1m' && targetTf !== '15s' && targetTf !== '30s') {
        return await resampleOHLCAsync(normalizedLive, '1', targetTf);
    }
    return normalizedLive;
}

interface UseDataLoadingProps {
    ticker: string
    timeframe: string // Standardized resolution (e.g., "1", "240")
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onPrepend?: (count: number) => void
    liveUpdatesEnabled?: boolean
}

export function useDataLoading({
    ticker,
    timeframe,
    onDataLoad,
    onPrepend,
    liveUpdatesEnabled = false
}: UseDataLoadingProps) {
    const onDataLoadRef = useRef(onDataLoad)
    const onPrependRef = useRef(onPrepend)
    useEffect(() => { onDataLoadRef.current = onDataLoad }, [onDataLoad])
    useEffect(() => { onPrependRef.current = onPrepend }, [onPrepend])

    // Core Data State
    const [fullData, setFullData] = useState<OHLCData[]>([])

    // Loading State
    const [isLoading, setIsLoading] = useState(true)
    const [lastError, setLastError] = useState<string | null>(null)

    // History and Live Connection State
    const [historyLoaded, setHistoryLoaded] = useState(false)
    const [livePrice, setLivePrice] = useState<number | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string | null>(null)
    const liveRawDataRef = useRef<OHLCData[]>([])
    const wsRef = useRef<WebSocket | null>(null)
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const retryCountRef = useRef(0)
    const resamplingSequenceRef = useRef<number>(0)

    // Pagination State (Time Based)
    const [hasMoreDataLeft, setHasMoreDataLeft] = useState(true)
    const [hasMoreDataRight, setHasMoreDataRight] = useState(false)
    const [isLoadingMoreLeft, setIsLoadingMoreLeft] = useState(false)
    const [isLoadingMoreRight, setIsLoadingMoreRight] = useState(false)
    const lastLoadTimeRef = useRef<number>(0)
    const leftBoundaryRef = useRef<number>(9999999999)
    const rightBoundaryRef = useRef<number>(0)

    // Resampling Internal State (Managed by loader discovery)
    const baseTimeframeRef = useRef<string>(timeframe)
    const isResamplingRef = useRef<boolean>(false)
    const fetchSeqRef = useRef<number>(0) // Guards against stale HTTP fetch responses (React Strict Mode double-fire)

    // Latest WS candle (instant ref, no array copy). Used by use-chart-data.ts
    // to render the forming candle with real OHLC without waiting for setFullData.
    const liveCandleRef = useRef<OHLCData | null>(null)

    // Metadata State (Full Range)
    const [fullDataRange, setFullDataRange] = useState<{ start: number; end: number } | null>(null)

    // Initial Data Load Effect
    useEffect(() => {
        const mySeq = ++fetchSeqRef.current // Unique ID for this load; stale responses are discarded
        async function loadData() {
            setIsLoading(true)
            setHistoryLoaded(false)
            liveRawDataRef.current = []
            setLivePrice(null)
            setLastUpdate(null)
            try {
                // Reset state
                baseTimeframeRef.current = timeframe
                isResamplingRef.current = false
                setLastError(null)
                setHasMoreDataLeft(true)
                setHasMoreDataRight(false)
                setIsLoadingMoreLeft(false)
                setIsLoadingMoreRight(false)
                leftBoundaryRef.current = 9999999999
                rightBoundaryRef.current = 0

                // Initial load: get newest 20000 bars
                let result = await fetchBinaryOHLC(ticker, timeframe, 0, 9999999999, 20000, "left")

                // If native data not found, try resampling from 1m (standardized as "1")
                if (!result.success && result.error === "Data not found" && canResample('1', timeframe)) {
                    setLastError(`Native missing, trying 1 for ${timeframe}`)

                    const baseResult = await fetchBinaryOHLC(ticker, '1', 0, 9999999999, 20000, "left")

                    if (baseResult.success) {
                        result = baseResult
                        baseTimeframeRef.current = '1'
                        isResamplingRef.current = true
                    } else {
                        console.error(`[Resampling] Fallback to 1 FAILED:`, baseResult.error)
                        setLastError(`Native ${timeframe} missing AND 1 fallback failed: ${baseResult.error}`)
                        result.error = `Data not found for ${timeframe} (and 1 base not found)`
                    }
                } else if (!result.success && result.error === "Data not found" && (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y'))) {
                    setLastError(`Native missing, trying 1D fallback for ${timeframe}`)

                    const baseResult = await fetchBinaryOHLC(ticker, '1D', 0, 9999999999, 20000, "left")

                    if (baseResult.success && baseResult.data) {
                        result = {
                            success: true,
                            data: resampleDataForWMY(baseResult.data, timeframe)
                        }
                        baseTimeframeRef.current = '1D'
                        isResamplingRef.current = true
                    } else {
                        console.error(`[Resampling] Fallback to 1D FAILED:`, baseResult.error)
                        setLastError(`Native ${timeframe} missing AND 1D fallback failed: ${baseResult.error}`)
                        result.error = `Data not found for ${timeframe} (and 1D base not found)`
                    }
                } else if (!result.success) {
                    console.warn(`[LoadData] Failed:`, result.error)
                    setLastError(`Load failed: ${result.error}`)
                }

                if (result.success && result.data) {
                    let finalData: OHLCData[] = []

                    if (isResamplingRef.current) {
                        const targetUpper = timeframe.toUpperCase()
                        const isCalendarTf = targetUpper.endsWith('D') || targetUpper.endsWith('W') || targetUpper.endsWith('M') || targetUpper.endsWith('Y')
                        if (isCalendarTf) {
                            finalData = resampleDataForWMY(result.data, timeframe)
                        } else {
                            finalData = await resampleOHLCAsync(result.data, baseTimeframeRef.current, timeframe)
                        }
                    } else {
                        finalData = result.data
                    }

                    if (liveUpdatesEnabled) {
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
                                    // Merge with the historical data
                                    finalData = mergeDatasets(finalData, processedLive)
                                }
                            }
                        } catch (e) {
                            console.error("[useDataLoading] Live cache fetch failed:", e)
                        }
                    }

                    // Discard stale response (e.g. React Strict Mode double-fire or rapid ticker switch)
                    if (mySeq !== fetchSeqRef.current) return

                    setFullData(finalData)
                    if (finalData.length > 0) {
                        leftBoundaryRef.current = finalData[0].time
                        rightBoundaryRef.current = finalData[finalData.length - 1].time
                        setHasMoreDataLeft(true) // assume more history exists
                        setHasMoreDataRight(false) // initially we are at the newest edge
                        
                        onDataLoadRef.current?.({
                            start: finalData[0].time,
                            end: finalData[finalData.length - 1].time,
                            totalBars: finalData.length
                        })
                    }

                    setHistoryLoaded(true)
                    // Fetch metadata using the BASE timeframe
                    fetchMetadata(baseTimeframeRef.current)
                } else {
                    if (result.error !== "Data not found") {
                        toast.error(result.error || `Failed to load data for ${ticker} ${timeframe}`)
                    }
                }
            } catch (e) {
                console.error("Failed to load data:", e)
                toast.error("An unexpected error occurred while loading data")
                setLastError(`Exception: ${e}`)
            } finally {
                setIsLoading(false)
            }
        }

        async function fetchMetadata(tf: string) {
            try {
                const metaResult = await getDataMetadata(ticker, tf)
                if (metaResult.success && metaResult.metadata) {
                    setFullDataRange({
                        start: metaResult.metadata.firstBarTime,
                        end: metaResult.metadata.lastBarTime
                    })
                }
            } catch (error) {
                console.error("Failed to load metadata:", error)
            }
        }

        loadData()
    }, [ticker, timeframe, liveUpdatesEnabled])

    // WebSocket Streaming Effect
    useEffect(() => {
        if (!liveUpdatesEnabled || !historyLoaded) return

        let isCancelled = false

        // Map ticker to standard futures symbol or raw ticker
        let safeTicker = ticker
        const roots = ["ES", "NQ", "YM", "RTY", "GC", "CL"]
        const root = ticker.replace(/1!$/, "")
        if (roots.includes(root)) {
            safeTicker = "/" + root
        }

        // Map timeframe to ws timeframe (15s, 30s are supported, other/higher timeframes resampled from 1m)
        const wsTimeframe = (timeframe === "15s" || timeframe === "30s") ? timeframe : "1m"

        function connect() {
            if (isCancelled) return

            if (wsRef.current) {
                try {
                    wsRef.current.close()
                } catch (e) {}
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
            // Spoke API runs on port 8001
            const wsUrl = `${protocol}//localhost:8001/stream?symbol=${encodeURIComponent(safeTicker)}&timeframe=${encodeURIComponent(wsTimeframe)}`

            const ws = new WebSocket(wsUrl)
            wsRef.current = ws

            ws.onopen = () => {
                if (isCancelled) {
                    ws.close()
                    return
                }
                retryCountRef.current = 0
            }

            ws.onmessage = async (event) => {
                if (isCancelled) return
                try {
                    const msg = JSON.parse(event.data)
                    if (!msg || typeof msg !== 'object') return

                    if (msg.type === 'snapshot') {
                        if (msg.candles && Array.isArray(msg.candles)) {
                            const formatted = msg.candles.map((c: any) => ({
                                time: c.time > 10000000000 ? c.time / 1000 : c.time,
                                open: Number(c.open),
                                high: Number(c.high),
                                low: Number(c.low),
                                close: Number(c.close),
                                volume: Number(c.volume || 0)
                            }))
                            liveRawDataRef.current = formatted

                            // Set liveCandleRef to the last snapshot candle (the forming candle)
                            if (formatted.length > 0) {
                                liveCandleRef.current = { ...formatted[formatted.length - 1] }
                            }

                            // Resample and merge
                            const processed = await processLiveData(liveRawDataRef.current, timeframe)
                            setFullData(prev => mergeDatasets(prev, processed))
                        }
                        if (msg.live_price !== undefined && msg.live_price !== null) {
                            setLivePrice(msg.live_price)
                            setLastUpdate(new Date().toISOString())
                        }
                    } else if (msg.type === 'candle') {
                        const rawCandle = msg.candle
                        if (rawCandle) {
                            const formattedCandle: OHLCData = {
                                time: rawCandle.time > 10000000000 ? rawCandle.time / 1000 : rawCandle.time,
                                open: Number(rawCandle.open),
                                high: Number(rawCandle.high),
                                low: Number(rawCandle.low),
                                close: Number(rawCandle.close),
                                volume: Number(rawCandle.volume || 0)
                            }

                            // Merge with existing liveCandleRef to preserve extreme prices
                            // captured by the quote handler between candle messages.
                            const existingLC = liveCandleRef.current
                            if (existingLC && existingLC.time === formattedCandle.time) {
                                liveCandleRef.current = {
                                    time: formattedCandle.time,
                                    open: formattedCandle.open,
                                    high: Math.max(formattedCandle.high, existingLC.high),
                                    low: Math.min(formattedCandle.low, existingLC.low),
                                    close: formattedCandle.close,
                                    volume: formattedCandle.volume
                                }
                            } else {
                                liveCandleRef.current = formattedCandle
                            }

                            // Add or update in liveRawDataRef
                            const existingIdx = liveRawDataRef.current.findIndex(c => c.time === formattedCandle.time)
                            const isTransition = existingIdx < 0
                            if (existingIdx >= 0) {
                                liveRawDataRef.current[existingIdx] = formattedCandle
                            } else {
                                liveRawDataRef.current.push(formattedCandle)
                            }

                            // Fast path: for native timeframes, only trigger setFullData on
                            // candle transitions (new candle). Updates to the forming candle
                            // are handled by liveCandleRef in use-chart-data.ts.
                            const needsResampling = timeframe !== '1' && timeframe !== '1m' && timeframe !== '15s' && timeframe !== '30s'
                            if (!needsResampling) {
                                if (isTransition) {
                                    // Append without copying the entire array
                                    setFullData(prev => prev.concat([formattedCandle]))
                                }
                            } else {
                                // Resample and merge
                                const processed = await processLiveData(liveRawDataRef.current, timeframe)
                                setFullData(prev => mergeDatasets(prev, processed))
                            }
                        }
                    } else if (msg.type === 'quote') {
                        if (msg.price !== undefined && msg.price !== null) {
                            const price = Number(msg.price)
                            setLivePrice(price)
                            const currentIsoTime = msg.time || new Date().toISOString()
                            setLastUpdate(currentIsoTime)

                            if (liveRawDataRef.current.length > 0) {
                                const lastRaw = liveRawDataRef.current[liveRawDataRef.current.length - 1]
                                const liveTime = Math.floor(new Date(currentIsoTime).getTime() / 1000)
                                const rawTimeframe = (timeframe === "15s" || timeframe === "30s") ? timeframe : "1m"
                                const rawSecs = parseTimeframeToSeconds(rawTimeframe)

                                // Determine which candle period this quote belongs to
                                const candleTime = Math.floor(liveTime / rawSecs) * rawSecs;

                                if (candleTime === lastRaw.time) {
                                    // Same candle period — update in-place
                                    lastRaw.close = price
                                    lastRaw.high = Math.max(lastRaw.high, price)
                                    lastRaw.low = Math.min(lastRaw.low, price)
                                    // Preserve open from WS candle message, only update close/high/low
                                    const existing = liveCandleRef.current
                                    if (existing && existing.time === candleTime) {
                                        existing.close = price
                                        existing.high = Math.max(existing.high, price)
                                        existing.low = Math.min(existing.low, price)
                                    } else {
                                        liveCandleRef.current = { ...lastRaw }
                                    }
                                } else if (candleTime > lastRaw.time) {
                                    // New candle period — only update if liveCandleRef already
                                    // exists (created by WS candle message). Do NOT create a
                                    // synthetic liveCandleRef from quotes.
                                    const existing = liveCandleRef.current
                                    if (existing && existing.time === candleTime) {
                                        existing.close = price
                                        existing.high = Math.max(existing.high, price)
                                        existing.low = Math.min(existing.low, price)
                                    }
                                }
                            }
                        }
                    }
                } catch (err) {
                    console.error(`❌ [useDataLoading] Error processing WS message:`, err)
                }
            }

            ws.onerror = (err) => {
                console.error(`🔌 [useDataLoading] WebSocket error for ${safeTicker}:`, err)
            }

            ws.onclose = (event) => {
                if (isCancelled) return

                // Reconnect with backoff
                const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 10000)
                retryCountRef.current += 1

                reconnectTimeoutRef.current = setTimeout(() => {
                    connect()
                }, delay)
            }
        }

        connect()

        return () => {
            isCancelled = true
            if (wsRef.current) {
                try {
                    wsRef.current.close()
                } catch (e) {}
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current)
            }
        }
    }, [ticker, timeframe, liveUpdatesEnabled, historyLoaded])

    const LOAD_DEBOUNCE_MS = 200

    // Load More Data (Pagination Left - Older Data)
    const loadMoreDataLeft = useCallback(async () => {
        const now = Date.now()
        if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) return
        if (isLoadingMoreLeft || !hasMoreDataLeft) return

        lastLoadTimeRef.current = now
        setIsLoadingMoreLeft(true)

        // Use base timeframe for loading
        const usedTimeframe = baseTimeframeRef.current
        const loadStart = performance.now()

        try {
            // Fetch next 20000 bars strictly older than current left boundary
            const result = await fetchBinaryOHLC(ticker, usedTimeframe, 0, leftBoundaryRef.current, 20000, "left")
            const fetchEnd = performance.now()

            if (result.success && result.data && result.data.length > 0) {
                let newData = result.data

                // Resample if needed
                if (isResamplingRef.current) {
                    const resampleStart = performance.now()
                    if (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y')) {
                        newData = resampleDataForWMY(result.data, timeframe)
                    } else {
                        newData = await resampleOHLCAsync(result.data, usedTimeframe, timeframe)
                    }
                }

                const prependedCount = newData.length
                if (onPrependRef.current) onPrependRef.current(prependedCount)

                // Filter duplicates synchronously using boundary refs to avoid React state timing issues
                let cleanNewData = newData
                const firstExistingDataTime = leftBoundaryRef.current
                if (newData.length > 0 && firstExistingDataTime !== 9999999999) {
                    if (newData[newData.length - 1].time >= firstExistingDataTime) {
                        cleanNewData = newData.filter(d => d.time < firstExistingDataTime)
                    }
                }

                const actualAddedCount = cleanNewData.length

                setFullData(prev => {
                    let combined = [...cleanNewData, ...prev]

                    if (combined.length > EVICT_WHEN_OVER) {
                        const overflow = combined.length - EVICT_TO
                        if (overflow > 0 && overflow < combined.length) {
                            combined = combined.slice(0, combined.length - overflow)
                            setHasMoreDataRight(true) // We evicted from the right, so more exists right
                        }
                    }
                    
                    if (combined.length > 0) {
                        leftBoundaryRef.current = combined[0].time
                        rightBoundaryRef.current = combined[combined.length - 1].time
                    }
                    return combined
                })

                if (actualAddedCount === 0) {
                    setHasMoreDataLeft(false)
                } else {
                    const hasMore = newData.length >= 1000;
                    setHasMoreDataLeft(hasMore)
                }
            } else {
                setHasMoreDataLeft(false)
                toast.info("Reached the end of available historical data")
            }
        } catch (e) {
            console.error("Failed to load more historical data:", e)
            toast.error("Failed to load more historical data")
        } finally {
            setIsLoadingMoreLeft(false)
        }
    }, [ticker, timeframe, isLoadingMoreLeft, hasMoreDataLeft])

    // Load More Data (Pagination Right - Newer Data)
    const loadMoreDataRight = useCallback(async () => {
        const now = Date.now()
        if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) return
        if (isLoadingMoreRight || !hasMoreDataRight) return

        lastLoadTimeRef.current = now
        setIsLoadingMoreRight(true)

        // Use base timeframe for loading
        const usedTimeframe = baseTimeframeRef.current
        const loadStart = performance.now()

        try {
            // Fetch next 20000 bars strictly newer than current right boundary
            const result = await fetchBinaryOHLC(ticker, usedTimeframe, rightBoundaryRef.current, 9999999999, 20000, "right")
            const fetchEnd = performance.now()

            if (result.success && result.data && result.data.length > 0) {
                const histData = result.data
                let liveData: OHLCData[] = []
                
                // Only fetch live data if we are paging close to the present (newest timestamp is within 5 days of now)
                const newestHistTime = histData.length > 0 ? histData[histData.length - 1].time : 0
                const isCloseToPresent = (Date.now() / 1000 - newestHistTime) < 5 * 86400

                if (isCloseToPresent || histData.length === 0) {
                    try {
                        const liveRes = await fetch(`/api/history?symbol=${encodeURIComponent(ticker)}&limit=5000`, { cache: 'no-store' })
                        if (liveRes.ok) {
                            const json = await liveRes.json()
                            if (json.success && json.data && json.data.candles) {
                                liveData = json.data.candles
                            }
                        }
                    } catch (e) {
                        console.error("[useDataLoading] Failed to fetch live storage cache for merge (right):", e)
                    }
                }

                let newData: OHLCData[] = []

                if (isResamplingRef.current) {
                    // Merge base datasets first after resampling live data to base timeframe (e.g. 1D live matches 1D parquet)
                    const processedLive = await processLiveData(liveData, baseTimeframeRef.current)
                    const mergedBase = mergeDatasets(histData, processedLive)
                    const resampleStart = performance.now()
                    const targetUpper = timeframe.toUpperCase()
                    const isCalendarTf = targetUpper.endsWith('D') || targetUpper.endsWith('W') || targetUpper.endsWith('M') || targetUpper.endsWith('Y')
                    if (isCalendarTf) {
                        newData = resampleDataForWMY(mergedBase, timeframe)
                    } else {
                        newData = await resampleOHLCAsync(mergedBase, usedTimeframe, timeframe)
                    }
                } else {
                    // Resample live data first to match native native timeframe
                    const processedLive = await processLiveData(liveData, timeframe)
                    newData = mergeDatasets(histData, processedLive)
                }

                // Filter duplicates synchronously using boundary refs to avoid React state timing issues
                let cleanNewData = newData
                const lastExistingDataTime = rightBoundaryRef.current
                if (newData.length > 0 && lastExistingDataTime !== 0) {
                    if (newData[0].time <= lastExistingDataTime) {
                        cleanNewData = newData.filter(d => d.time > lastExistingDataTime)
                    }
                }

                const actualAddedCount = cleanNewData.length

                // Check if we need to evict data from the START (oldest, left)
                setFullData(prev => {
                    let combined = [...prev, ...cleanNewData]

                    if (combined.length > EVICT_WHEN_OVER) {
                        const overflow = combined.length - EVICT_TO
                        if (overflow > 0 && overflow < combined.length) {
                            combined = combined.slice(overflow)
                            setHasMoreDataLeft(true) // We evicted from the left, so more exists left
                        }
                    }
                    
                    if (combined.length > 0) {
                        leftBoundaryRef.current = combined[0].time
                        rightBoundaryRef.current = combined[combined.length - 1].time
                    }
                    return combined
                })

                if (actualAddedCount === 0) {
                    setHasMoreDataRight(false)
                } else {
                    const hasMore = newData.length >= 1000;
                    setHasMoreDataRight(hasMore)
                }
            } else {
                setHasMoreDataRight(false)
                toast.info("Reached the latest available data")
            }
        } catch (e) {
            console.error("Failed to load more newer data:", e)
            toast.error("Failed to load more newer data")
        } finally {
            setIsLoadingMoreRight(false)
        }
    }, [ticker, timeframe, isLoadingMoreRight, hasMoreDataRight])

    // Jump to Time Logic
    const jumpToTime = useCallback(async (time: number) => {
        // Check if time is within loaded data
        if (fullData.length > 0) {
            const loadedStart = fullData[0].time
            const loadedEnd = fullData[fullData.length - 1].time

            if (time >= loadedStart && time <= loadedEnd) {
                return { success: true, needsScroll: true }
            }
        }

        // Need to load data for this time
        toast.info(`Loading data for ${new Date(time * 1000).toLocaleDateString()}...`)

        try {
            const usedTimeframe = baseTimeframeRef.current;
            const padding = 172800; // 2 days in seconds
            const result = await fetchBinaryOHLC(ticker, usedTimeframe, 0, time + padding, 20000, "left")
            if (result.success && result.data && result.data.length > 0) {
                let finalData = result.data

                // Resample if needed
                if (isResamplingRef.current) {
                    if (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y')) {
                        finalData = resampleDataForWMY(result.data, timeframe)
                    } else {
                        finalData = await resampleOHLCAsync(result.data, usedTimeframe, timeframe)
                    }
                }

                // Replace fullData with new data centered on target time
                setFullData(finalData)
                if (finalData.length > 0) {
                    leftBoundaryRef.current = finalData[0].time
                    rightBoundaryRef.current = finalData[finalData.length - 1].time
                }
                
                // Assuming more history exists since we bounded it
                setHasMoreDataLeft(true)
                setHasMoreDataRight(true)

                toast.success(`Loaded ${finalData.length.toLocaleString()} bars`)
                return { success: true, needsScroll: true }
            } else {
                toast.error(result.error || 'Failed to load data')
                return { success: false }
            }
        } catch (e) {
            console.error('jumpToTime error:', e)
            toast.error('Failed to load data')
            return { success: false }
        }
    }, [fullData, ticker, timeframe])

    return {
        fullData,
        fullDataRange,
        isLoading,
        loadMoreData: loadMoreDataLeft,
        loadMoreDataLeft,
        loadMoreDataRight,
        jumpToTime,
        // Pagination info
        totalRows: fullData.length,
        hasMoreData: hasMoreDataLeft,
        hasMoreDataLeft,
        hasMoreDataRight,
        isLoadingMore: isLoadingMoreLeft,
        isLoadingMoreLeft,
        isLoadingMoreRight,
        // Live streaming state
        livePrice,
        lastUpdate,
        liveCandleRef,
        // Debug
        baseTimeframe: baseTimeframeRef.current,
        isResampling: isResamplingRef.current,
        lastError
    }
}
