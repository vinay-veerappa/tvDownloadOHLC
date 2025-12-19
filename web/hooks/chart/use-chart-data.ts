"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { normalizeResolution, getResolutionInMinutes } from "@/lib/resolution"
import { useDataLoading } from "./use-data-loading"
import { useLiveDataLoading } from "./use-live-data-loading"
import { useReplay } from "./use-replay"

import { SessionType } from "@/components/top-toolbar"

interface UseChartDataProps {
    ticker: string
    timeframe: string
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onPriceChange?: (price: number, ticker: string) => void
    getVisibleTimeRange?: () => { start: number, end: number, center: number } | null
    initialReplayTime?: number
    mode?: 'historical' | 'live'
    sessionType?: SessionType
}

// Cached formatter for performance
const nyTimeFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false
});

function isRTH(time: number, isFuture: boolean): boolean {
    // time is seconds
    const d = new Date(time * 1000);
    const parts = nyTimeFormatter.formatToParts(d);
    let hour = 0;
    let minute = 0;
    for (const p of parts) {
        if (p.type === 'hour') hour = parseInt(p.value);
        if (p.type === 'minute') minute = parseInt(p.value);
    }

    // RTH: 09:30 - 16:00 (Stocks) / 16:15 (Futures)
    const t = hour * 100 + minute;

    if (t < 930) return false;

    const end = isFuture ? 1615 : 1600;
    if (t >= end) return false; // Strict inequality? 16:00 is usually the CLOSE bar time.

    // Wait, bar time is OPEN time usually for candles?
    // If bar time is 15:59, it closes at 16:00 -> Included.
    // If bar time is 16:00, it closes at 16:01 -> Excluded for stocks? 
    // TV timestamp is usually Open Time.
    // So 15:59 is the last 1m bar.
    // 16:00 bar is After Hours.
    // So `t < end` is correct if `end` is 1600.

    return true;
}

export function useChartData({
    ticker,
    timeframe: rawTimeframe,
    onDataLoad,
    onReplayStateChange,
    onPriceChange,
    initialReplayTime,
    mode = 'historical',
    sessionType = 'ETH'
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

    // Filter for RTH if needed
    const effectiveFullData = useMemo(() => {
        // Skip filtering if mode is ETH or if timeframe is Daily or higher (not intraday)
        const isIntraday = getResolutionInMinutes(timeframe) < 1440;
        if (sessionType === 'ETH' || !isIntraday) return loading.fullData;

        const isFuture = ticker.includes('!');
        return loading.fullData.filter(bar => isRTH(bar.time, isFuture));
    }, [loading.fullData, sessionType, ticker, timeframe]);

    const replay = useReplay({
        fullData: effectiveFullData,
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
