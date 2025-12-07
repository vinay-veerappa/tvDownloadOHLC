"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getChartData, loadNextChunks, getDataMetadata, loadChunksForTime, OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"
import { resampleOHLC, canResample } from "@/lib/resampling"

// Memory limits for data (2+ years of 1m data max)
const MAX_BARS = 500000          // ~2 years of 1m data
const EVICT_WHEN_OVER = 525000   // Start evicting when 5% over limit
const EVICT_TO = 475000          // Evict down to 5% under limit
const CHUNKS_PER_LOAD = 5        // Load 5 chunks at a time (~100K bars)

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

    // Pagination State
    const [totalRows, setTotalRows] = useState(0)
    const [chunksLoaded, setChunksLoaded] = useState(0)
    const [numChunks, setNumChunks] = useState(0)
    const [nextChunkIndex, setNextChunkIndex] = useState(0)
    const [hasMoreData, setHasMoreData] = useState(true)
    const [isLoadingMore, setIsLoadingMore] = useState(false)
    const lastLoadTimeRef = useRef<number>(0)

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
                // Reset resampling state
                baseTimeframeRef.current = timeframe
                isResamplingRef.current = false
                setLastError(null)

                let result = await getChartData(ticker, timeframe)

                // If native data not found, try resampling from 1m (standardized as "1")
                if (!result.success && result.error === "Data not found" && canResample('1', timeframe)) {
                    setLastError(`Native missing, trying 1 for ${timeframe}`)

                    const baseResult = await getChartData(ticker, '1')

                    if (baseResult.success) {
                        result = baseResult
                        baseTimeframeRef.current = '1'
                        isResamplingRef.current = true
                    } else {
                        console.error(`[Resampling] Fallback to 1 FAILED:`, baseResult.error)
                        setLastError(`Native ${timeframe} missing AND 1 fallback failed: ${baseResult.error}`)
                        // If fallback fails, we want the user to know 1 is also missing
                        result.error = `Data not found for ${timeframe} (and 1 base not found)`
                    }
                } else if (!result.success) {
                    console.warn(`[LoadData] Failed:`, result.error)
                    setLastError(`Load failed: ${result.error}`)
                }

                if (result.success && result.data) {
                    let finalData = result.data

                    // Apply resampling if needed
                    if (isResamplingRef.current) {
                        finalData = resampleOHLC(result.data, baseTimeframeRef.current, timeframe)
                    }

                    setFullData(finalData)
                    setTotalRows(result.totalRows || (result.data.length || 0))
                    setChunksLoaded(result.chunksLoaded || 0)
                    setNumChunks(result.numChunks || 0)
                    setNextChunkIndex(result.chunksLoaded || 0)
                    setHasMoreData((result.chunksLoaded || 0) < (result.numChunks || 0))

                    if (finalData.length > 0) {
                        onDataLoad?.({
                            start: finalData[0].time,
                            end: finalData[finalData.length - 1].time,
                            totalBars: finalData.length
                        })
                    }

                    // Fetch metadata using the BASE timeframe
                    fetchMetadata(baseTimeframeRef.current)
                } else {
                    // console.error(`[LoadData] Final Failure:`, result.error) // Silent to avoid console noise if handled by toast
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

    // Load More Data (Pagination)
    const LOAD_DEBOUNCE_MS = 200
    const loadMoreData = useCallback(async () => {
        const now = Date.now()
        if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) return
        if (isLoadingMore || !hasMoreData) return

        lastLoadTimeRef.current = now
        setIsLoadingMore(true)

        // Use base timeframe for loading
        const usedTimeframe = baseTimeframeRef.current

        try {
            const result = await loadNextChunks(ticker, usedTimeframe, nextChunkIndex, CHUNKS_PER_LOAD)

            if (result.success && result.data && result.data.length > 0) {
                let newData = result.data

                // Resample if needed
                if (isResamplingRef.current) {
                    newData = resampleOHLC(result.data, usedTimeframe, timeframe)
                }

                const prependedCount = newData.length
                const oldestDate = new Date(newData[0].time * 1000).toLocaleDateString()

                // Notify parent to adjust replay index if needed
                if (onPrepend) onPrepend(prependedCount)

                toast.info(`Loading more data... ${prependedCount.toLocaleString()} bars from ${oldestDate}`)

                // Check if we need to evict data from the END (newest)
                setFullData(prev => {
                    let combined = [...newData, ...prev]

                    if (combined.length > EVICT_WHEN_OVER) {
                        const overflow = combined.length - EVICT_TO
                        if (overflow > 0 && overflow < combined.length) {
                            combined = combined.slice(0, combined.length - overflow)
                            console.log(`[EVICT] Dropped ${overflow} newest bars`)
                        }
                    }
                    return combined
                })

                setNextChunkIndex(result.nextChunkIndex || nextChunkIndex + CHUNKS_PER_LOAD)
                setHasMoreData(result.hasMore || false)
                setChunksLoaded(prev => prev + (result.chunksLoaded || 0))
            } else if (!result.hasMore) {
                setHasMoreData(false)
                toast.info("Reached the end of available data")
            }
        } catch (e) {
            console.error("Failed to load more data:", e)
            toast.error("Failed to load more historical data")
        } finally {
            setIsLoadingMore(false)
        }
    }, [ticker, timeframe, nextChunkIndex, isLoadingMore, hasMoreData])

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
            // Use base timeframe for loading
            const usedTimeframe = baseTimeframeRef.current

            // Adjust chunks needed if resampling
            let chunksToLoad = 12
            if (isResamplingRef.current && usedTimeframe === '1') {
                chunksToLoad = 36
            }

            const result = await loadChunksForTime(ticker, usedTimeframe, time, chunksToLoad)
            if (result.success && result.data && result.data.length > 0) {
                let finalData = result.data

                // Resample if needed
                if (isResamplingRef.current) {
                    finalData = resampleOHLC(result.data, usedTimeframe, timeframe)
                }

                // Replace fullData with new data centered on target time
                setFullData(finalData)
                setNextChunkIndex(result.endChunkIndex || 0)
                // Update metadata tracking
                setHasMoreData((result.endChunkIndex || 0) < numChunks)

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
    }, [fullData, ticker, timeframe, numChunks])

    return {
        fullData,
        fullDataRange,
        isLoading,
        loadMoreData,
        jumpToTime,
        // Pagination info
        totalRows,
        hasMoreData,
        isLoadingMore,
        // Debug
        baseTimeframe: baseTimeframeRef.current,
        isResampling: isResamplingRef.current,
        lastError
    }
}
