"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { getChartData, loadNextChunks, getDataMetadata, DataMetadata, loadChunksForTime } from "@/actions/data-actions"
import { toast } from "sonner"

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

    // On-demand loading state
    const [totalRows, setTotalRows] = useState(0)
    const [chunksLoaded, setChunksLoaded] = useState(0)
    const [numChunks, setNumChunks] = useState(0)
    const [nextChunkIndex, setNextChunkIndex] = useState(0)
    const [hasMoreData, setHasMoreData] = useState(true)
    const [isLoadingMore, setIsLoadingMore] = useState(false)
    const lastLoadTimeRef = useRef<number>(0) // For debouncing rapid loads

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
                const result = await getChartData(ticker, timeframe)
                if (result.success && result.data) {

                    setFullData(result.data)
                    setTotalRows(result.totalRows || result.data.length)
                    setChunksLoaded(result.chunksLoaded || 0)
                    setNumChunks(result.numChunks || 0)
                    setNextChunkIndex(result.chunksLoaded || 0)
                    setHasMoreData((result.chunksLoaded || 0) < (result.numChunks || 0))

                    // For replay restore, find the index
                    if (timeToRestore !== null && isReplayRestore) {
                        const idx = result.data.findIndex((item: any) => item.time >= timeToRestore!)
                        if (idx !== -1) {
                            setReplayIndex(idx)
                            if (initialReplayTimeRef.current !== undefined) {
                                setReplayMode(true)
                            }
                        }
                    }

                    // Clear the initialReplayTimeRef after first use
                    initialReplayTimeRef.current = undefined

                    if (result.data.length > 0) {
                        onDataLoad?.({
                            start: result.data[0].time,
                            end: result.data[result.data.length - 1].time,
                            totalBars: result.data.length
                        })
                    }
                } else {
                    toast.error(`Failed to load data for ${ticker} ${timeframe}`)
                }
            } catch (e) {
                console.error("Failed to load data:", e)
                toast.error("An unexpected error occurred while loading data")
            }
        }
        loadData()

        // Also fetch full data range metadata (for calendar)
        async function fetchMetadata() {
            const metaResult = await getDataMetadata(ticker, timeframe)
            if (metaResult.success && metaResult.metadata) {
                setFullDataRange({
                    start: metaResult.metadata.firstBarTime,
                    end: metaResult.metadata.lastBarTime
                })
            }
        }
        fetchMetadata()
    }, [ticker, timeframe])

    // On-demand loading of more historical data
    // Called when user scrolls to the oldest data and wants more
    const LOAD_DEBOUNCE_MS = 200 // Prevent rapid double-loads
    const loadMoreData = useCallback(async () => {
        // Debounce: prevent rapid successive calls
        const now = Date.now()
        if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) {
            return
        }

        if (isLoadingMore || !hasMoreData) return

        lastLoadTimeRef.current = now
        setIsLoadingMore(true)

        try {
            const result = await loadNextChunks(ticker, timeframe, nextChunkIndex, CHUNKS_PER_LOAD)

            if (result.success && result.data && result.data.length > 0) {
                const prependedCount = result.data.length
                const oldestDate = new Date(result.data[0].time * 1000).toLocaleDateString()

                toast.info(`Loading more data... ${prependedCount.toLocaleString()} bars from ${oldestDate}`)

                // Check if we need to evict data from the END (newest)
                setFullData(prev => {
                    let newData = [...result.data!, ...prev]

                    // If exceeding limit, evict from the START (oldest data)
                    // This preserves newest data so Home key always works
                    if (newData.length > EVICT_WHEN_OVER) {
                        const evictCount = newData.length - EVICT_TO
                        const evictedDate = new Date(newData[0].time * 1000).toLocaleDateString()
                        newData = newData.slice(evictCount) // Drop from beginning (oldest)
                        console.log(`[EVICT] Dropped ${evictCount} oldest bars (from ${evictedDate})`)
                        toast.info(`Freed memory: dropped ${evictCount.toLocaleString()} oldest bars`)
                    }

                    console.log(`[DATA] Total bars: ${newData.length}`)
                    return newData
                })

                // NO windowStart adjustment needed - chart preserves by TIME!

                // Update chunk tracking
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

    // REMOVED: Preload threshold useEffect - replaced by barsInLogicalRange in chart-container

    // Return data for chart - SIMPLIFIED: use fullData directly (no windowing)
    const data = useMemo(() => {
        if (fullData.length === 0) return []

        if (replayMode) {
            // In replay mode, show data up to the replay index
            const endIndex = Math.min(replayIndex + 1, fullData.length)
            return fullData.slice(0, endIndex)
        }

        // NO WINDOWING - pass all data to chart
        // Chart handles position by TIME, auto-preserves scroll
        console.log(`[DATA] Passing ${fullData.length} bars to chart`)
        return fullData
    }, [fullData, replayMode, replayIndex])

    // REMOVED: shiftWindowToTime and shiftWindowByBars
    // No longer needed - chart handles position by TIME automatically

    // Helper to find index for time
    const findIndexForTime = (time: number) => {
        if (!fullData.length) return 0
        const idx = fullData.findIndex(item => item.time >= time)
        if (idx === -1) {
            return fullData.length - 1
        }
        return idx
    }

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

        prevWindowStartRef.current = null // No longer used for window position

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
        // NO windowStart to restore - chart handles position by TIME
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
        // Jump to time (loads data if needed)
        jumpToTime: async (time: number) => {
            // Check if time is within loaded data
            if (fullData.length > 0) {
                const loadedStart = fullData[0].time
                const loadedEnd = fullData[fullData.length - 1].time

                if (time >= loadedStart && time <= loadedEnd) {
                    // Already loaded, just return success
                    return { success: true, needsScroll: true }
                }
            }

            // Need to load data for this time
            toast.info(`Loading data for ${new Date(time * 1000).toLocaleDateString()}...`)

            try {
                const result = await loadChunksForTime(ticker, timeframe, time, 12)
                if (result.success && result.data && result.data.length > 0) {
                    // Replace fullData with new data centered on target time
                    setFullData(result.data)
                    setNextChunkIndex(result.endChunkIndex || 0)
                    setHasMoreData((result.endChunkIndex || 0) < numChunks)

                    toast.success(`Loaded ${result.data.length.toLocaleString()} bars`)
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
        // REMOVED: shiftWindowByBars, shiftWindowToTime, windowSize
    }
}

