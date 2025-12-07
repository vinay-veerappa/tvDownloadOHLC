"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { normalizeResolution } from "@/lib/resolution"
import { useDataLoading } from "./use-data-loading"
import { useReplay } from "./use-replay"

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
    timeframe: rawTimeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    initialReplayTime
}: UseChartDataProps) {

    // 1. Normalize timeframe
    const timeframe = useMemo(() => normalizeResolution(rawTimeframe), [rawTimeframe])

    // Forward refs for coordination
    const currentReplayTimeRef = useRef<number | null>(null)

    // 2. Data Loading Hook
    const loading = useDataLoading({
        ticker,
        timeframe,
        onDataLoad,
        // When data is prepended (pagination), shift replay index to maintain position
        onPrepend: (count) => replay.adjustIndex(count)
    })

    // 3. Replay Hook
    const replay = useReplay({
        fullData: loading.fullData,
        initialReplayTime,
        onReplayStateChange,
        onPriceChange
    })

    // 4. Coordinator Logic: Persistence across timeframe switches
    // Track current replay time to restore it after loading new data (timeframe switch)
    useEffect(() => {
        // If in replay mode, keep track of the current time
        if (replay.replayMode && replay.data.length > 0) {
            const lastBar = replay.data[replay.data.length - 1]
            if (lastBar) {
                currentReplayTimeRef.current = lastBar.time
            }
        }
    }, [replay.replayMode, replay.data])

    // Restore replay position after main data load (not pagination)
    useEffect(() => {
        // If we just finished loading (isLoading false) and have data
        if (!loading.isLoading && loading.fullData.length > 0) {
            // Priority: Initial Replay > Persisted Replay Time
            // Note: Initial Replay is handled by useReplay internal effect on mount.
            // We only care about PERSISTED time (switching timeframes while in replay).

            if (replay.replayMode && currentReplayTimeRef.current) {
                const newIdx = replay.findIndexForTime(currentReplayTimeRef.current)
                if (newIdx !== -1) {
                    replay.setReplayIndex(newIdx)
                }
            }
        }
    }, [loading.isLoading, loading.fullData.length]) // Only run when loading state changes or data arrives

    // 5. Expose Unified Interface
    return {
        // Data & State
        fullData: loading.fullData,
        data: replay.data, // Sliced data for chart

        // Replay
        replayMode: replay.replayMode,
        replayIndex: replay.replayIndex,
        isSelectingReplayStart: replay.isSelectingReplayStart,
        setIsSelectingReplayStart: replay.setIsSelectingReplayStart,
        setReplayIndex: replay.setReplayIndex,
        startReplay: replay.startReplay,
        startReplaySelection: replay.startReplaySelection,
        stopReplay: replay.stopReplay,
        stepForward: replay.stepForward,
        stepBack: replay.stepBack,
        findIndexForTime: replay.findIndexForTime,

        // Data Loading
        isLoadingMore: loading.isLoadingMore,
        hasMoreData: loading.hasMoreData,
        loadMoreData: loading.loadMoreData,
        totalRows: loading.totalRows,
        fullDataRange: loading.fullDataRange,
        jumpToTime: loading.jumpToTime,

        // Debug / Internals
        debug: {
            baseTimeframe: loading.baseTimeframe,
            isResampling: loading.isResampling,
            lastError: loading.lastError
        }
    }
}
