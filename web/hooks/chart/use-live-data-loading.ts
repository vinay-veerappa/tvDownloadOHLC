"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getLiveChartData } from "@/actions/get-live-chart"
import { OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"

interface UseLiveDataLoadingProps {
    ticker: string
    timeframe: string
    enabled?: boolean
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
}

export function useLiveDataLoading({
    ticker,
    timeframe,
    enabled = true,
    onDataLoad
}: UseLiveDataLoadingProps) {
    const [fullData, setFullData] = useState<OHLCData[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [lastError, setLastError] = useState<string | null>(null)
    const [livePrice, setLivePrice] = useState<number | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(true)
    const [hasMoreData, setHasMoreData] = useState(false)
    const [isLoadingMore, setIsLoadingMore] = useState(false)

    const isFirstLoad = useRef(true)
    const isRunningRef = useRef(isRunning)
    useEffect(() => { isRunningRef.current = isRunning }, [isRunning])

    const lastTimeRef = useRef<number>(0)
    const rawDataRef = useRef<OHLCData[]>([]) // Keep raw array to avoid closure staleness

    const fetchData = useCallback(async () => {
        try {
            // Request delta since last known time (in ms)
            const sinceMs = lastTimeRef.current * 1000

            const res = await getLiveChartData(ticker, timeframe, isFirstLoad.current ? undefined : sinceMs, isFirstLoad.current ? 180000 : undefined)

            if (res.success && res.data) {
                const rawCandles = res.data.candles || []

                if (rawCandles.length > 0) {
                    const formatted: OHLCData[] = rawCandles.map((c: any) => ({
                        time: c.time / 1000,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume
                    }))

                    if (isFirstLoad.current) {
                        rawDataRef.current = formatted
                    } else {
                        // Robust Merge Strategy:
                        // 1. Combine arrays
                        // 2. Sort by time
                        // 3. Deduplicate by time (keeping latest version of same timestamp)

                        const combined = [...rawDataRef.current, ...formatted]

                        // Sort first
                        combined.sort((a, b) => a.time - b.time)

                        // Deduplicate
                        const unique: OHLCData[] = []
                        if (combined.length > 0) {
                            unique.push(combined[0])
                            for (let i = 1; i < combined.length; i++) {
                                const current = combined[i]
                                const last = unique[unique.length - 1]
                                if (current.time === last.time) {
                                    // Replace with new version (usually updated close/volume)
                                    unique[unique.length - 1] = current
                                } else {
                                    unique.push(current)
                                }
                            }
                        }
                        rawDataRef.current = unique
                    }

                    // Sorting again (redundant but safe)
                    // rawDataRef.current.sort((a, b) => a.time - b.time)
                    // setFullData([...rawDataRef.current])
                    setFullData((prev) => {
                        // Optimizing: only update fullData if we have a NEW candle or first load
                        // Intraday price updates are handled by livePrice state + reference logic in use-chart-data
                        if (rawDataRef.current.length > prev.length || prev.length === 0) {
                            return [...rawDataRef.current]
                        }
                        return prev
                    })

                    // Update ref for next poll using the absolute latest time we have
                    if (rawDataRef.current.length > 0) {
                        const lastBar = rawDataRef.current[rawDataRef.current.length - 1]
                        lastTimeRef.current = lastBar.time
                    }

                    // First Load Callback
                    if (isFirstLoad.current) {
                        onDataLoad?.({
                            start: formatted[0].time,
                            end: formatted[formatted.length - 1].time,
                            totalBars: formatted.length
                        })
                        isFirstLoad.current = false
                    }
                }

                // Always update metadata
                const currentLivePrice = res.data.live_price
                setLivePrice(currentLivePrice)
                setLastUpdate(res.data.last_update)

                // Update current candle with live price (tick-by-tick rendering)
                if (currentLivePrice && rawDataRef.current.length > 0) {
                    const lastCandle = rawDataRef.current[rawDataRef.current.length - 1]
                    const updatedCandle = {
                        ...lastCandle,
                        close: currentLivePrice,
                        high: Math.max(lastCandle.high, currentLivePrice),
                        low: Math.min(lastCandle.low, currentLivePrice)
                    }
                    rawDataRef.current[rawDataRef.current.length - 1] = updatedCandle
                    setFullData([...rawDataRef.current])
                }

                // Set hasMore based on API response
                if (res.data.hasMore !== undefined) {
                    setHasMoreData(res.data.hasMore);
                }

            } else if (isFirstLoad.current) {
                setLastError(res.error || "Failed to fetch live data")
            }
        } catch (e: any) {
            console.error("Live fetch error:", e)
            setLastError(e.message)
        } finally {
            setIsLoading(false)
        }
    }, [onDataLoad, ticker, timeframe])

    useEffect(() => {
        // Skip if not enabled (historical mode)
        if (!enabled) return;

        fetchData()
        const id = setInterval(() => {
            if (isRunningRef.current) fetchData()
        }, 2000) // Reduced polling (2s) to prevent I/O overload, relying on livePrice for ticks
        return () => clearInterval(id)
    }, [fetchData, enabled])

    return {
        fullData,
        fullDataRange: fullData.length > 0 ? {
            start: fullData[0].time,
            end: fullData[fullData.length - 1].time
        } : null,
        isLoading,
        livePrice,
        lastUpdate,
        isRunning,
        setIsRunning,
        lastError,
        // Lazy loading support
        loadMoreData: async () => {
            if (isLoadingMore || !hasMoreData) return;

            setIsLoadingMore(true);
            try {
                const oldestTime = rawDataRef.current[0]?.time;
                if (!oldestTime) return;

                // Request data before oldest timestamp, limited to 50k candles
                const beforeMs = oldestTime * 1000;
                const res = await getLiveChartData(ticker, timeframe, undefined, 50000);

                if (res.success && res.data && res.data.candles) {
                    const formatted: OHLCData[] = res.data.candles.map((c: any) => ({
                        time: c.time / 1000,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume
                    }));

                    // Filter to only get data older than current oldest
                    const olderData = formatted.filter(c => c.time < oldestTime);

                    if (olderData.length > 0) {
                        rawDataRef.current = [...olderData, ...rawDataRef.current];
                        setFullData([...rawDataRef.current]);
                    } else {
                    }
                }
            } catch (e) {
                console.error('[LiveDataLoading] Load more failed:', e);
            } finally {
                setIsLoadingMore(false);
            }
        },
        jumpToTime: async () => ({ success: false, needsScroll: false }),
        hasMoreData,
        isLoadingMore,
        totalRows: fullData.length,
        baseTimeframe: timeframe,
        isResampling: false
    }
}
