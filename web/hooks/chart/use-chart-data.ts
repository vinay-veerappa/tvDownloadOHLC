"use client"

import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { normalizeResolution, getResolutionInMinutes } from "@/lib/resolution"
import { useDataLoading } from "./use-data-loading"
import { useLiveDataLoading } from "./use-live-data-loading"
import { useReplay } from "./use-replay"
import { OHLCData } from "@/actions/data-actions"

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
    sessionType: SessionType
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
    const liveCandlesRef = useRef<Map<number, {
        ticker: string
        timeframe: string
        time: number
        open: number
        high: number
        low: number
        close: number
    }>>(new Map())

    // Clear projected candles when ticker/timeframe changes
    useEffect(() => {
        liveCandlesRef.current.clear()
    }, [ticker, timeframe])

    const histLoading = useDataLoading({
        ticker,
        timeframe,
        onDataLoad,
        onPrepend: (count) => replay.adjustIndex(count),
        liveUpdatesEnabled: mode === 'historical'
    })

    const liveLoading = useLiveDataLoading({
        ticker,
        timeframe,
        enabled: mode === 'live',
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

    // Replay Logic
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
        const showLiveUpdates = mode === 'live' || (mode === 'historical' && !replay.replayMode)
        if (showLiveUpdates && baseData.length > 0) {
            const liveStore = loading as any
            const livePrice = liveStore.livePrice
            const lastUpdate = liveStore.lastUpdate // ISO String

            if (livePrice !== null && livePrice !== undefined) {
                // Avoid copying the entire baseData array on every tick.
                // We only modify the last candle and/or append projections,
                // so we share the prefix by reference and build a new tail.
                const lastIdx = baseData.length - 1
                const lastCandle = baseData[lastIdx]
                const projections = liveCandlesRef.current

                // Determine if we should project a NEW candle (or multiple)
                let shouldProjectNew = false
                let newCandleTime = 0

                if (lastUpdate) {
                    const lastBarTime = lastCandle.time
                    const liveTime = Math.floor(new Date(lastUpdate).getTime() / 1000)
                    const resolutionMins = getResolutionInMinutes(timeframe)
                    const resolutionSecs = resolutionMins * 60

                    const nextExpectedTime = lastBarTime + resolutionSecs
                    if (liveTime >= nextExpectedTime) {
                        newCandleTime = Math.floor(liveTime / resolutionSecs) * resolutionSecs
                        if (newCandleTime > lastBarTime) {
                            shouldProjectNew = true
                        }
                    }
                }

                let enriched: OHLCData[];

                if (shouldProjectNew && lastUpdate) {
                    const lastBarTime = lastCandle.time
                    const resolutionMins = getResolutionInMinutes(timeframe)
                    const resolutionSecs = resolutionMins * 60

                    const nextExpectedTime = lastBarTime + resolutionSecs
                    let tempTime = nextExpectedTime
                    let prevClose = lastCandle.close

                    // Build the tail: intermediate + active projected candles
                    const tail: OHLCData[] = []

                    // 1. Project intermediate candles — use cached data if available
                    while (tempTime < newCandleTime) {
                        const cached = projections.get(tempTime)
                        if (cached && cached.ticker === ticker && cached.timeframe === timeframe) {
                            tail.push({
                                time: tempTime,
                                open: cached.open,
                                high: cached.high,
                                low: cached.low,
                                close: cached.close,
                                volume: 0
                            })
                            prevClose = cached.close
                        } else {
                            tail.push({
                                time: tempTime,
                                open: prevClose,
                                high: prevClose,
                                low: prevClose,
                                close: prevClose,
                                volume: 0
                            })
                        }
                        tempTime += resolutionSecs
                    }

                    // 2. Project the active forming candle at newCandleTime
                    const existing = projections.get(newCandleTime)
                    if (existing && existing.ticker === ticker && existing.timeframe === timeframe) {
                        existing.close = livePrice
                        if (livePrice > existing.high) existing.high = livePrice
                        if (livePrice < existing.low) existing.low = livePrice
                    } else {
                        // Use prevClose as the open (matches hub behavior: open = prev close).
                        // Initialize high/low to span both prevClose and livePrice so the
                        // candle doesn't start with a flat top/bottom (O=H or O=L).
                        projections.set(newCandleTime, {
                            ticker,
                            timeframe,
                            time: newCandleTime,
                            open: prevClose,
                            high: Math.max(prevClose, livePrice),
                            low: Math.min(prevClose, livePrice),
                            close: livePrice
                        })
                    }

                    const activeCandle = projections.get(newCandleTime)!
                    tail.push({
                        time: activeCandle.time,
                        open: activeCandle.open,
                        high: activeCandle.high,
                        low: activeCandle.low,
                        close: activeCandle.close,
                        volume: 0
                    })

                    // Clean up entries already in fullData
                    for (const [t] of projections) {
                        if (t <= lastBarTime) projections.delete(t)
                    }

                    // Concatenate shared prefix with new tail (avoids copying baseData)
                    enriched = baseData.concat(tail);
                } else {
                    // Not projecting — accumulate high/low for the current bar
                    const barTime = lastCandle.time
                    let tracked = projections.get(barTime)

                    if (!tracked || tracked.ticker !== ticker || tracked.timeframe !== timeframe) {
                        tracked = {
                            ticker, timeframe, time: barTime,
                            open: lastCandle.open,
                            high: lastCandle.high,
                            low: lastCandle.low,
                            close: lastCandle.close
                        }
                        projections.set(barTime, tracked)
                    } else {
                        // Projection was created from the shouldProjectNew=true path
                        // with a synthetic open. Now that the real candle arrived in
                        // fullData, correct the open to match the real market open.
                        tracked.open = lastCandle.open
                    }

                    // Merge base values (in case a candle message updated fullData)
                    tracked.high = Math.max(tracked.high, lastCandle.high)
                    tracked.low = Math.min(tracked.low, lastCandle.low)

                    // Apply current tick
                    tracked.close = livePrice
                    tracked.high = Math.max(tracked.high, livePrice)
                    tracked.low = Math.min(tracked.low, livePrice)

                    // Build enriched: share prefix, replace only last element
                    enriched = baseData.slice(0, lastIdx);
                    enriched.push({
                        ...lastCandle,
                        high: tracked.high,
                        low: tracked.low,
                        close: tracked.close
                    });

                    // Clean up old entries
                    for (const [t] of projections) {
                        if (t < barTime) projections.delete(t)
                    }
                }

                if (enriched.length >= 2) {
                    const l1 = enriched[enriched.length - 1];
                    const l2 = enriched[enriched.length - 2];
                    const bl1 = baseData[baseData.length - 1];
                    const bl2 = baseData[baseData.length - 2];
                    console.log(`[useChartData] enriched: [${new Date(l2.time * 1000).toLocaleTimeString()}] O:${l2.open} H:${l2.high} L:${l2.low} C:${l2.close} | [${new Date(l1.time * 1000).toLocaleTimeString()}] O:${l1.open} H:${l1.high} L:${l1.low} C:${l1.close} (base: [${new Date(bl2.time * 1000).toLocaleTimeString()}] C:${bl2.close} | [${new Date(bl1.time * 1000).toLocaleTimeString()}] C:${bl1.close}), livePrice: ${livePrice}, lastUpdate: ${lastUpdate}, shouldProjectNew: ${shouldProjectNew}, newCandleTime: ${newCandleTime}`);
                }
                return enriched;
            }
        }
        return baseData
    }, [replay.data, mode, (loading as any).livePrice, (loading as any).lastUpdate, timeframe, ticker])

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

        isLoadingMoreLeft: (loading as any).isLoadingMoreLeft !== undefined ? (loading as any).isLoadingMoreLeft : loading.isLoadingMore,
        isLoadingMoreRight: (loading as any).isLoadingMoreRight !== undefined ? (loading as any).isLoadingMoreRight : false,
        hasMoreDataLeft: (loading as any).hasMoreDataLeft !== undefined ? (loading as any).hasMoreDataLeft : loading.hasMoreData,
        hasMoreDataRight: (loading as any).hasMoreDataRight !== undefined ? (loading as any).hasMoreDataRight : false,
        loadMoreDataLeft: (loading as any).loadMoreDataLeft !== undefined ? (loading as any).loadMoreDataLeft : loading.loadMoreData,
        loadMoreDataRight: (loading as any).loadMoreDataRight !== undefined ? (loading as any).loadMoreDataRight : () => {},

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
