"use client"

import { useState, useEffect, useMemo, useRef } from "react"
import { getChartData } from "@/actions/data-actions"
import { toast } from "sonner"

// Window size based on timeframe for performance
export function getWindowSizeForTimeframe(timeframe: string): number {
    switch (timeframe) {
        case '1m':
        case '5m':
            return 5000
        case '15m':
        case '1h':
            return 7500
        case '4h':
        case 'D':
        case 'W':
        default:
            return 10000
    }
}

interface UseChartDataProps {
    ticker: string
    timeframe: string
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number }) => void
    onPriceChange?: (price: number) => void
    getVisibleTimeRange?: () => { start: number, end: number, center: number } | null
}

export function useChartData({
    ticker,
    timeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    getVisibleTimeRange
}: UseChartDataProps) {

    // Full data and window state
    const [fullData, setFullData] = useState<any[]>([])
    const [windowStart, setWindowStart] = useState(0)
    const windowSize = useMemo(() => getWindowSizeForTimeframe(timeframe), [timeframe])

    // Replay mode state
    const [replayMode, setReplayMode] = useState(false)
    const [replayIndex, setReplayIndex] = useState(0)
    const [isSelectingReplayStart, setIsSelectingReplayStart] = useState(false)
    const prevWindowStartRef = useRef<number | null>(null)

    // Notify parent of replay state changes
    useEffect(() => {
        onReplayStateChange?.({
            isReplayMode: replayMode,
            index: replayIndex,
            total: fullData.length
        })
    }, [replayMode, replayIndex, fullData.length, onReplayStateChange])

    // Load Data
    useEffect(() => {
        // Capture current view center time OR replay time BEFORE loading new data
        let timeToRestore: number | null = null;
        let isReplayRestore = false;

        if (fullData.length > 0) {
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

                    let newStart = Math.max(0, result.data.length - windowSize);

                    if (timeToRestore !== null) {
                        // Find the index in the NEW data that matches our restore time
                        const idx = result.data.findIndex((item: any) => item.time >= timeToRestore!);

                        if (idx !== -1) {
                            if (isReplayRestore) {
                                // If we were in replay mode, simply set the new replay index.
                                // The new window will be calculated in useMemo based on this index.
                                setReplayIndex(idx);
                            } else {
                                // Standard mode: center the view on the restored time
                                const halfWindow = Math.floor(windowSize / 2);
                                newStart = Math.max(0, Math.min(idx - halfWindow, result.data.length - windowSize));
                            }
                        }
                    }

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

    // Apply windowing and replay slice to data
    const data = useMemo(() => {
        if (fullData.length === 0) return []

        if (replayMode) {
            const endIndex = Math.min(replayIndex + 1, fullData.length)
            const startIndex = Math.max(0, endIndex - windowSize)
            return fullData.slice(startIndex, endIndex)
        } else {
            if (fullData.length <= windowSize) return fullData
            const start = Math.max(0, Math.min(windowStart, fullData.length - windowSize))
            return fullData.slice(start, start + windowSize)
        }
    }, [fullData, windowStart, windowSize, replayMode, replayIndex])

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
        findIndexForTime
    }
}
