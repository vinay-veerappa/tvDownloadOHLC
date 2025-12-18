"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { normalizeResolution, getResolutionInMinutes } from "@/lib/resolution"
import { useDataLoading } from "./use-data-loading"
import { useLiveDataLoading } from "./use-live-data-loading"
import { useReplay } from "./use-replay"

interface UseChartDataProps {
    ticker: string
    timeframe: string
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onPriceChange?: (price: number, ticker: string) => void
    getVisibleTimeRange?: () => { start: number, end: number, center: number } | null
    initialReplayTime?: number
    mode?: 'historical' | 'live'
}

export function useChartData({
    ticker,
    timeframe: rawTimeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    initialReplayTime,
    mode = 'historical'
}: UseChartDataProps) {

    const timeframe = useMemo(() => normalizeResolution(rawTimeframe), [rawTimeframe])

    const currentReplayTimeRef = useRef<number | null>(null)

    const histLoading = useDataLoading({
        ticker,
        timeframe,
        onDataLoad,
        onPrepend: (count) => replay.adjustIndex(count)
    })

    const liveLoading = useLiveDataLoading({
        ticker,
        timeframe,
        onDataLoad
    })

    const loading = mode === 'live' ? liveLoading : histLoading

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

    const data = useMemo(() => {
        const baseData = replay.data
        if (mode === 'live' && baseData.length > 0) {
            const liveStore = loading as any
            const livePrice = liveStore.livePrice
            const lastUpdate = liveStore.lastUpdate // ISO String

            if (livePrice !== null && livePrice !== undefined) {
                const enriched = [...baseData]
                const lastIdx = enriched.length - 1
                const lastCandle = { ...enriched[lastIdx] }

                // Determine if we should project a NEW candle
                let shouldProjectNew = false
                let newCandleTime = 0

                if (lastUpdate) {
                    const lastBarTime = lastCandle.time
                    const liveTime = Math.floor(new Date(lastUpdate).getTime() / 1000)
                    const resolutionMins = getResolutionInMinutes(timeframe) // 0.25 for 15s
                    const resolutionSecs = resolutionMins * 60

                    // Check if liveTime belongs to a future interval
                    // If lastBarTime is 9:00:00 (1m), next is 9:01:00
                    // If liveTime is 9:01:05, we need a new bar

                    if (liveTime >= lastBarTime + resolutionSecs) {
                        // Align to grid
                        newCandleTime = Math.floor(liveTime / resolutionSecs) * resolutionSecs
                        if (newCandleTime > lastBarTime) {
                            shouldProjectNew = true
                        }
                    }
                }

                if (shouldProjectNew) {
                    // Start new candle
                    enriched.push({
                        time: newCandleTime,
                        open: lastCandle.close, // Gapless? Or use livePrice? Usually open = last close or livePrice
                        high: livePrice,
                        low: livePrice,
                        close: livePrice,
                        volume: 0
                    })
                } else {
                    // Update existing last candle
                    lastCandle.close = livePrice
                    if (livePrice > lastCandle.high) lastCandle.high = livePrice
                    if (livePrice < lastCandle.low) lastCandle.low = livePrice
                    enriched[lastIdx] = lastCandle
                }

                return enriched
            }
        }
        return baseData
    }, [replay.data, mode, (loading as any).livePrice, (loading as any).lastUpdate, timeframe])

    useEffect(() => {
        if (!loading.isLoading && loading.fullData.length > 0) {
            if (mode === 'historical' && replay.replayMode && currentReplayTimeRef.current) {
                const newIdx = replay.findIndexForTime(currentReplayTimeRef.current)
                if (newIdx !== -1) {
                    replay.setReplayIndex(newIdx)
                }
            }
        }
    }, [loading.isLoading, loading.fullData.length, mode])

    return {
        fullData: loading.fullData,
        data, // Use the enriched data

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
