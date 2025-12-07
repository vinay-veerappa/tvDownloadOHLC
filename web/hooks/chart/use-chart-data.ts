"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { getChartData, loadNextChunks } from "@/actions/data-actions"
import { toast } from "sonner"

// Memory limits for sliding window (3 years max, evict 1 year when full)
const MAX_BARS_3_YEARS = 1050000  // ~3 years of 1m data (~350K bars/year)
const EVICT_BARS_1_YEAR = 350000  // Drop 1 year when limit reached
const CHUNKS_PER_LOAD = 5         // Load 5 chunks at a time (~100K bars, ~3 months)

// Window size based on timeframe for performance
// 20K bars balances between render speed and scroll smoothness
export function getWindowSizeForTimeframe(timeframe: string): number {
    switch (timeframe) {
        case '1m':
            return 20000  // ~14 days of 1m data
        case '5m':
            return 20000  // ~70 days of 5m data
        case '15m':
            return 20000  // ~200 days of 15m data
        case '1h':
            return 20000  // ~3 years of 1h data
        case '4h':
        case 'D':
        case 'W':
        default:
            return 20000  // All years for higher TFs
    }
}

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

    // Full data and window state
    const [fullData, setFullData] = useState<any[]>([])
    const [windowStart, setWindowStart] = useState(0)
    const windowSize = useMemo(() => getWindowSizeForTimeframe(timeframe), [timeframe])

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

                    let newStart = Math.max(0, result.data.length - windowSize);

                    if (timeToRestore !== null) {
                        // Find the index in the NEW data that matches our restore time
                        const idx = result.data.findIndex((item: any) => item.time >= timeToRestore!);

                        if (idx !== -1) {
                            if (isReplayRestore) {
                                // If we were in replay mode, simply set the new replay index.
                                // The new window will be calculated in useMemo based on this index.
                                setReplayIndex(idx);
                                // Keep replay mode on if restoring from initialReplayTime
                                if (initialReplayTimeRef.current !== undefined) {
                                    setReplayMode(true);
                                }
                            } else {
                                // Standard mode: center the view on the restored time
                                const halfWindow = Math.floor(windowSize / 2);
                                newStart = Math.max(0, Math.min(idx - halfWindow, result.data.length - windowSize));
                            }
                        }
                    }

                    // Clear the initialReplayTimeRef after first use
                    initialReplayTimeRef.current = undefined;

                    if (!isReplayRestore) {
                        setWindowStart(newStart)
                    }

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

                // Check if we need to evict old data first
                setFullData(prev => {
                    let newData = [...result.data!, ...prev]

                    // If exceeding 3-year limit, evict oldest 1 year from the END (newest data)
                    if (newData.length > MAX_BARS_3_YEARS) {
                        const evictCount = EVICT_BARS_1_YEAR
                        const evictedDate = new Date(newData[newData.length - 1].time * 1000).toLocaleDateString()
                        newData = newData.slice(0, newData.length - evictCount)
                        toast.warning(`Memory limit reached. Dropped 1 year of newest data (up to ${evictedDate})`)
                    }


                    return newData
                })

                // Adjust windowStart to maintain user's position
                setWindowStart(prev => prev + prependedCount)

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

    // Auto-trigger loading more data when windowStart is getting low
    // This pre-loads data BEFORE the user reaches the oldest data
    const PRELOAD_THRESHOLD = 50000 // Trigger loading when within 50K bars of start
    useEffect(() => {
        // If windowStart is below threshold and we have more data to load, load it
        if (windowStart < PRELOAD_THRESHOLD && hasMoreData && !isLoadingMore && fullData.length > 0) {
            loadMoreData()
        }
    }, [windowStart, hasMoreData, isLoadingMore, fullData.length, loadMoreData])

    // Return data for chart - windowed for performance
    // Window can be shifted via windowStart state
    const data = useMemo(() => {
        if (fullData.length === 0) return []

        let result: any[]
        if (replayMode) {
            // In replay mode, show data up to the replay index
            const endIndex = Math.min(replayIndex + 1, fullData.length)
            result = fullData.slice(0, endIndex)
        } else {
            // Apply windowing for performance
            if (fullData.length <= windowSize) {
                result = fullData
            } else {
                // Use windowStart state - clamp to valid range
                const start = Math.max(0, Math.min(windowStart, fullData.length - windowSize))
                result = fullData.slice(start, start + windowSize)
            }
        }


        return result
    }, [fullData, windowStart, windowSize, replayMode, replayIndex])

    // Shift window to show a specific time (for scroll handling)
    const shiftWindowToTime = useCallback((targetTime: number, position: 'center' | 'start' | 'end' = 'center') => {
        if (fullData.length <= windowSize) return // No need to shift

        const idx = fullData.findIndex(item => item.time >= targetTime)
        if (idx === -1) return

        let newStart: number
        if (position === 'start') {
            newStart = idx
        } else if (position === 'end') {
            newStart = idx - windowSize + 1
        } else {
            newStart = idx - Math.floor(windowSize / 2)
        }

        // Clamp to valid range
        newStart = Math.max(0, Math.min(newStart, fullData.length - windowSize))
        setWindowStart(newStart)
    }, [fullData, windowSize])

    // Shift window by number of bars (positive = forward/right, negative = back/left)
    const shiftWindowByBars = useCallback((bars: number) => {
        if (fullData.length <= windowSize) return

        setWindowStart(prev => {
            const newStart = prev + bars
            return Math.max(0, Math.min(newStart, fullData.length - windowSize))
        })
    }, [fullData.length, windowSize])

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

        prevWindowStartRef.current = windowStart

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
        if (prevWindowStartRef.current !== null) {
            setWindowStart(prevWindowStartRef.current)
            prevWindowStartRef.current = null
        } else {
            setWindowStart(Math.max(0, fullData.length - windowSize))
        }
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
        windowSize,
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
        // Window control for scroll handling
        shiftWindowByBars,
        shiftWindowToTime
    }
}

