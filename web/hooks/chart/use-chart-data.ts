"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { getChartData, loadNextChunks, getDataMetadata, DataMetadata, loadChunksForTime } from "@/actions/data-actions"
import { toast } from "sonner"
import { resampleOHLC, canResample } from "@/lib/resampling"

// Memory limits for data (2+ years of 1m data max)
// Eviction happens from the NEWEST end when scrolling into older history
const MAX_BARS = 500000          // ~2 years of 1m data
const EVICT_WHEN_OVER = 525000   // Start evicting when 5% over limit
const EVICT_TO = 475000          // Evict down to 5% under limit
const CHUNKS_PER_LOAD = 5        // Load 5 chunks at a time (~100K bars)

interface UseChartDataProps {
    ticker: string
    timeframe: string
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onPriceChange?: (price: number) => void
    getVisibleTimeRange?: () => { start: number, end: number, center: number } | null
    initialReplayTime?: number // Timestamp to restore replay position on mount
}

export function useChartData({
    ticker,
    timeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    getVisibleTimeRange,
    initialReplayTime
}: UseChartDataProps) {

    // Full data state - NO MORE SLIDING WINDOW!
    // Data grows via prepend, evicts from end when over limit
    const [fullData, setFullData] = useState<any[]>([])

    // Replay mode state
    const [replayMode, setReplayMode] = useState(initialReplayTime !== undefined)
    const [replayIndex, setReplayIndex] = useState(0)
    const [isSelectingReplayStart, setIsSelectingReplayStart] = useState(false)
    const prevWindowStartRef = useRef<number | null>(null)

    // Resampling state
    const baseTimeframeRef = useRef<string>(timeframe)
    const isResamplingRef = useRef<boolean>(false)

    // On-demand loading state
    const [totalRows, setTotalRows] = useState(0)
    const [chunksLoaded, setChunksLoaded] = useState(0)
    const [numChunks, setNumChunks] = useState(0)
    const [nextChunkIndex, setNextChunkIndex] = useState(0)
    const [hasMoreData, setHasMoreData] = useState(true)
    const [isLoadingMore, setIsLoadingMore] = useState(false)
    const lastLoadTimeRef = useRef<number>(0) // For debouncing rapid loads
    const [lastError, setLastError] = useState<string | null>(null) // Debug state

    // Store the initial replay time to use after data loads
    const initialReplayTimeRef = useRef(initialReplayTime)

    // Full data range (from metadata - for calendar)
    const [fullDataRange, setFullDataRange] = useState<{ start: number; end: number } | null>(null)

    // Notify parent of replay state changes
    useEffect(() => {
        const currentTime = fullData.length > 0 && replayIndex < fullData.length ? fullData[replayIndex]?.time : undefined
        onReplayStateChange?.({
            isReplayMode: replayMode,
            index: replayIndex,
            total: fullData.length,
            currentTime
        })
    }, [replayMode, replayIndex, fullData.length, fullData, onReplayStateChange])

    // Helper to find index for time
    const findIndexForTime = (time: number, dataArray: any[] = fullData) => {
        if (!dataArray.length) return 0
        const idx = dataArray.findIndex(item => item.time >= time)
        if (idx === -1) {
            return dataArray.length - 1
        }
        return idx
    }

    // Load Data
    useEffect(() => {
        // Capture current view center time OR replay time BEFORE loading new data
        let timeToRestore: number | null = null;
        let isReplayRestore = false;

        // Priority 1: Use initialReplayTimeRef if provided (for remount with existing replay position)
        if (initialReplayTimeRef.current !== undefined) {
            timeToRestore = initialReplayTimeRef.current;
            isReplayRestore = true;
        } else if (fullData.length > 0) {
            // Priority 2: Use current position from existing data
            if (replayMode) {
                // In replay mode, sync to the exact replay index (the "current" time)
                const safeIndex = Math.min(replayIndex, fullData.length - 1);
                if (safeIndex >= 0) {
                    timeToRestore = fullData[safeIndex].time;
                    isReplayRestore = true;
                }
            } else {
                // In normal mode, sync to the center of the visible view
                const range = getVisibleTimeRange?.();
                if (range) {
                    timeToRestore = range.center;
                }
            }
        }

        async function loadData() {
            try {
                // Reset resampling state
                baseTimeframeRef.current = timeframe
                isResamplingRef.current = false
                setLastError(null)

                let result = await getChartData(ticker, timeframe)

                // If native data not found, try resampling from 1m
                if (!result.success && result.error === "Data not found" && canResample('1m', timeframe)) {
                    console.log(`[Resampling] Native data for ${timeframe} not found, trying resampling from 1m`)
                    setLastError(`Native missing, trying 1m for ${timeframe}`)

                    const baseResult = await getChartData(ticker, '1m')

                    if (baseResult.success) {
                        result = baseResult
                        baseTimeframeRef.current = '1m'
                        isResamplingRef.current = true
                    } else {
                        console.error(`[Resampling] Fallback to 1m FAILED:`, baseResult.error)
                        setLastError(`Native ${timeframe} missing AND 1m fallback failed: ${baseResult.error}`)
                        // If fallback fails, we want the user to know 1m is also missing
                        result.error = `Data not found for ${timeframe} (and 1m base not found)`
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
                        console.log(`[Resampling] Resampled ${result.data.length} 1m bars to ${finalData.length} ${timeframe} bars`)
                    }

                    setFullData(finalData)
                    setTotalRows(result.totalRows || (result.data.length || 0)) // Note: totalRows refers to base TF matches
                    setChunksLoaded(result.chunksLoaded || 0)
                    setNumChunks(result.numChunks || 0)
                    setNextChunkIndex(result.chunksLoaded || 0)
                    setHasMoreData((result.chunksLoaded || 0) < (result.numChunks || 0))

                    // For replay restore, find the index
                    if (timeToRestore !== null && isReplayRestore) {
                        const idx = findIndexForTime(timeToRestore!, finalData)
                        if (idx !== -1) {
                            setReplayIndex(idx)
                            if (initialReplayTimeRef.current !== undefined) {
                                setReplayMode(true)
                            }
                        }
                    }

                    // Clear the initialReplayTimeRef after first use
                    initialReplayTimeRef.current = undefined

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
                    console.error(`[LoadData] Final Failure:`, result.error)
                    toast.error(result.error || `Failed to load data for ${ticker} ${timeframe}`)
                }
            } catch (e) {
                console.error("Failed to load data:", e)
                toast.error("An unexpected error occurred while loading data")
                setLastError(`Exception: ${e}`)
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
    }, [ticker, timeframe])

    // On-demand loading of more historical data
    const LOAD_DEBOUNCE_MS = 200
    const loadMoreData = useCallback(async () => {
        const now = Date.now()
        if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) {
            return
        }

        if (isLoadingMore || !hasMoreData) return

        lastLoadTimeRef.current = now
        setIsLoadingMore(true)

        // Use base timeframe for loading
        const usedTimeframe = baseTimeframeRef.current

        try {
            console.log(`Loading more data from chunk ${nextChunkIndex} for ${usedTimeframe}...`)
            const result = await loadNextChunks(ticker, usedTimeframe, nextChunkIndex, CHUNKS_PER_LOAD)

            if (result.success && result.data && result.data.length > 0) {
                let newData = result.data

                // Resample if needed
                if (isResamplingRef.current) {
                    newData = resampleOHLC(result.data, usedTimeframe, timeframe)
                    console.log(`Resampled loaded chunk: ${result.data.length} -> ${newData.length} bars`)
                }

                const prependedCount = newData.length
                const oldestDate = new Date(newData[0].time * 1000).toLocaleDateString()

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

                    console.log(`[DATA] Total bars: ${combined.length}`)
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

    // Return data for chart
    const data = useMemo(() => {
        if (fullData.length === 0) return []

        if (replayMode) {
            const endIndex = Math.min(replayIndex + 1, fullData.length)
            return fullData.slice(0, endIndex)
        }
        return fullData
    }, [fullData, replayMode, replayIndex])

    // Replay Controls
    const startReplay = (options?: { index?: number, time?: number }, chart?: any) => {
        let startIdx = 0

        if (options?.time !== undefined) {
            const idx = findIndexForTime(options.time)
            if (idx === -1) {
                toast.error("Selected date is beyond available data")
                return
            }
            startIdx = idx
        } else if (options?.index !== undefined) {
            startIdx = options.index
        }

        if (startIdx >= fullData.length - 1 && fullData.length > 0) {
            toast.warning("Replay started at the end of data")
        }

        prevWindowStartRef.current = null

        setReplayIndex(startIdx)
        setReplayMode(true)

        setTimeout(() => {
            if (startIdx < 50) {
                chart?.timeScale().fitContent()
            } else {
                chart?.timeScale().scrollToRealTime()
            }
        }, 100)
    }

    const startReplaySelection = () => {
        setIsSelectingReplayStart(true)
        toast.info("Select a bar to start replay")
    }

    const stepForward = () => {
        if (replayMode && replayIndex < fullData.length - 1) {
            setReplayIndex(prev => prev + 1)
        }
    }

    const stepBack = () => {
        if (replayMode && replayIndex > 0) {
            setReplayIndex(prev => prev - 1)
        }
    }

    const stopReplay = () => {
        setReplayMode(false)
        setIsSelectingReplayStart(false)
        prevWindowStartRef.current = null
    }

    // Auto-scroll on replay update
    useEffect(() => {
        if (data.length > 0) {
            const lastBar = data[data.length - 1]
            if (lastBar && lastBar.close) {
                onPriceChange?.(lastBar.close)
            }
        }
    }, [data, onPriceChange])

    return {
        fullData,
        data,
        replayMode,
        replayIndex,
        isSelectingReplayStart,
        setIsSelectingReplayStart,
        setReplayIndex,
        startReplay,
        startReplaySelection,
        stopReplay,
        stepForward,
        stepBack,
        findIndexForTime,
        // Data loading status
        isLoadingMore,
        hasMoreData,
        loadMoreData,
        totalRows,
        // Full data range for calendar (from metadata)
        fullDataRange,
        // Debug info
        debug: {
            baseTimeframe: baseTimeframeRef.current,
            isResampling: isResamplingRef.current,
            lastError
        },
        // Jump to time (loads data if needed)
        jumpToTime: async (time: number) => {
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
                if (isResamplingRef.current && usedTimeframe === '1m') {
                    chunksToLoad = 36
                }

                const result = await loadChunksForTime(ticker, usedTimeframe, time, chunksToLoad)
                if (result.success && result.data && result.data.length > 0) {
                    let finalData = result.data

                    // Resample if needed
                    if (isResamplingRef.current) {
                        finalData = resampleOHLC(result.data, usedTimeframe, timeframe)
                        console.log(`Resampled jump data: ${result.data.length} -> ${finalData.length}`)
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
        }
    }
}
