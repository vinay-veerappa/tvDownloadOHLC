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
    onPriceChange?: (price: number, ticker: string) => void
    getVisibleTimeRange?: () => { start: number, end: number, center: number } | null
    initialReplayTime?: number
}

export function useChartData({
    ticker,
    timeframe: rawTimeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    initialReplayTime
}: UseChartDataProps) {

    const timeframe = useMemo(() => normalizeResolution(rawTimeframe), [rawTimeframe])

    const currentReplayTimeRef = useRef<number | null>(null)

    const loading = useDataLoading({
        ticker,
        timeframe,
        onDataLoad,
        onPrepend: (count) => replay.adjustIndex(count)
    })

    const replay = useReplay({
        fullData: loading.fullData,
        ticker,
        initialReplayTime,
        onReplayStateChange,
        onPriceChange
    })

    useEffect(() => {
        if (replay.replayMode && replay.data.length > 0) {
            const lastBar = replay.data[replay.data.length - 1]
            if (lastBar) {
                currentReplayTimeRef.current = lastBar.time
            }
        }
    }, [replay.replayMode, replay.data])

    useEffect(() => {
        if (!loading.isLoading && loading.fullData.length > 0) {
            if (replay.replayMode && currentReplayTimeRef.current) {
                const newIdx = replay.findIndexForTime(currentReplayTimeRef.current)
                if (newIdx !== -1) {
                    replay.setReplayIndex(newIdx)
                }
            }
        }
    }, [loading.isLoading, loading.fullData.length])

    return {
        fullData: loading.fullData,
        data: replay.data,

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

        isLoadingMore: loading.isLoadingMore,
        hasMoreData: loading.hasMoreData,
        loadMoreData: loading.loadMoreData,
        totalRows: loading.totalRows,
        fullDataRange: loading.fullDataRange,
        jumpToTime: loading.jumpToTime,

        debug: {
            baseTimeframe: loading.baseTimeframe,
            isResampling: loading.isResampling,
            lastError: loading.lastError
        }
    }
}
