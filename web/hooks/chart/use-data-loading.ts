"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getDataMetadata, OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"
import { canResample, parseTimeframeToSeconds, resampleDataForWMY } from "@/lib/resampling"
import { resampleOHLCAsync } from "@/lib/resampling-client"
import { resolutionToFolderName } from "@/lib/resolution"

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

interface UseDataLoadingProps {
    ticker: string
    timeframe: string // Standardized resolution (e.g., "1", "240")
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onPrepend?: (count: number) => void
}

export function useDataLoading({
    ticker,
    timeframe,
    onDataLoad,
    onPrepend
}: UseDataLoadingProps) {
    // Core Data State
    const [fullData, setFullData] = useState<OHLCData[]>([])

    // Loading State
    const [isLoading, setIsLoading] = useState(true)
    const [lastError, setLastError] = useState<string | null>(null)

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

    // Metadata State (Full Range)
    const [fullDataRange, setFullDataRange] = useState<{ start: number; end: number } | null>(null)

    // Initial Data Load Effect
    useEffect(() => {
        async function loadData() {
            setIsLoading(true)
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
                    let finalData = result.data

                    // Apply resampling if needed
                    if (isResamplingRef.current) {
                        if (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y')) {
                            finalData = result.data // Already resampled on fallback load
                        } else {
                            finalData = await resampleOHLCAsync(result.data, baseTimeframeRef.current, timeframe)
                        }
                    }

                    setFullData(finalData)
                    if (finalData.length > 0) {
                        leftBoundaryRef.current = finalData[0].time
                        rightBoundaryRef.current = finalData[finalData.length - 1].time
                        setHasMoreDataLeft(true) // assume more history exists
                        setHasMoreDataRight(false) // initially we are at the newest edge
                        
                        onDataLoad?.({
                            start: finalData[0].time,
                            end: finalData[finalData.length - 1].time,
                            totalBars: finalData.length
                        })
                    }

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
    }, [ticker, timeframe, onDataLoad])

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
        console.log(`⏱️ [useDataLoading] loadMoreDataLeft started: fetching history before ${leftBoundaryRef.current}`);

        try {
            // Fetch next 20000 bars strictly older than current left boundary
            const result = await fetchBinaryOHLC(ticker, usedTimeframe, 0, leftBoundaryRef.current, 20000, "left")
            const fetchEnd = performance.now()
            console.log(`⏱️ [useDataLoading] fetchBinaryOHLC (left) completed in ${(fetchEnd - loadStart).toFixed(2)} ms`);

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
                    console.log(`⏱️ [useDataLoading] Resampling finished in ${(performance.now() - resampleStart).toFixed(2)} ms`);
                }

                const prependedCount = newData.length
                if (onPrepend) onPrepend(prependedCount)

                // Filter duplicates synchronously using boundary refs to avoid React state timing issues
                let cleanNewData = newData
                const firstExistingDataTime = leftBoundaryRef.current
                console.log(`⏱️ [useDataLoading] Filter check: newData length=${newData.length}, firstExisting=${firstExistingDataTime}, oldestNew=${newData[0]?.time}, newestNew=${newData[newData.length - 1]?.time}`);
                if (newData.length > 0 && firstExistingDataTime !== 9999999999) {
                    if (newData[newData.length - 1].time >= firstExistingDataTime) {
                        cleanNewData = newData.filter(d => d.time < firstExistingDataTime)
                        console.log(`⏱️ [useDataLoading] Filtered out overlapping/newer bars. Remaining unique count: ${cleanNewData.length}`);
                    }
                }

                const actualAddedCount = cleanNewData.length
                console.log(`⏱️ [useDataLoading] actualAddedCount=${actualAddedCount}, hasMoreDataLeft calculation basis: newData.length=${newData.length}`);

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
                    console.log(`⏱️ [useDataLoading] No new unique bars found left. Setting hasMoreDataLeft = false`);
                } else {
                    const hasMore = newData.length >= 1000;
                    setHasMoreDataLeft(hasMore)
                    console.log(`⏱️ [useDataLoading] Set hasMoreDataLeft = ${hasMore} (fetched count: ${newData.length})`);
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
    }, [ticker, timeframe, isLoadingMoreLeft, hasMoreDataLeft, onPrepend])

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
        console.log(`⏱️ [useDataLoading] loadMoreDataRight started: fetching newer data after ${rightBoundaryRef.current}`);

        try {
            // Fetch next 20000 bars strictly newer than current right boundary
            const result = await fetchBinaryOHLC(ticker, usedTimeframe, rightBoundaryRef.current, 9999999999, 20000, "right")
            const fetchEnd = performance.now()
            console.log(`⏱️ [useDataLoading] fetchBinaryOHLC (right) completed in ${(fetchEnd - loadStart).toFixed(2)} ms`);

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
                    console.log(`⏱️ [useDataLoading] Resampling finished in ${(performance.now() - resampleStart).toFixed(2)} ms`);
                }

                // Filter duplicates synchronously using boundary refs to avoid React state timing issues
                let cleanNewData = newData
                const lastExistingDataTime = rightBoundaryRef.current
                console.log(`⏱️ [useDataLoading] Filter check (right): newData length=${newData.length}, lastExisting=${lastExistingDataTime}, oldestNew=${newData[0]?.time}, newestNew=${newData[newData.length - 1]?.time}`);
                if (newData.length > 0 && lastExistingDataTime !== 0) {
                    if (newData[0].time <= lastExistingDataTime) {
                        cleanNewData = newData.filter(d => d.time > lastExistingDataTime)
                        console.log(`⏱️ [useDataLoading] Filtered out overlapping/older bars (right). Remaining unique count: ${cleanNewData.length}`);
                    }
                }

                const actualAddedCount = cleanNewData.length
                console.log(`⏱️ [useDataLoading] actualAddedCount (right)=${actualAddedCount}, hasMoreDataRight calculation basis: newData.length=${newData.length}`);

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
                    console.log(`⏱️ [useDataLoading] No new unique bars found right. Setting hasMoreDataRight = false`);
                } else {
                    const hasMore = newData.length >= 1000;
                    setHasMoreDataRight(hasMore)
                    console.log(`⏱️ [useDataLoading] Set hasMoreDataRight = ${hasMore} (fetched count: ${newData.length})`);
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
        // Debug
        baseTimeframe: baseTimeframeRef.current,
        isResampling: isResamplingRef.current,
        lastError
    }
}
