"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getLiveChartData } from "@/actions/get-live-chart"
import { OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"

interface UseLiveDataLoadingProps {
    ticker: string
    timeframe: string
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
}

export function useLiveDataLoading({
    ticker,
    timeframe,
    onDataLoad
}: UseLiveDataLoadingProps) {
    const [fullData, setFullData] = useState<OHLCData[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [lastError, setLastError] = useState<string | null>(null)
    const [livePrice, setLivePrice] = useState<number | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(true)

    const isFirstLoad = useRef(true)
    const isRunningRef = useRef(isRunning)
    useEffect(() => { isRunningRef.current = isRunning }, [isRunning])

    const fetchData = useCallback(async () => {
        try {
            const res = await getLiveChartData(ticker)
            if (res.success && res.data) {
                const rawCandles = res.data.candles || []

                // Transform to OHLCData (seconds instead of ms)
                const formatted: OHLCData[] = rawCandles.map((c: any) => ({
                    time: c.time / 1000,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume
                }))

                // Sorting is important for Lightweight Charts
                formatted.sort((a, b) => a.time - b.time)

                setFullData(formatted)
                setLivePrice(res.data.live_price)
                setLastUpdate(res.data.last_update)

                if (isFirstLoad.current && formatted.length > 0) {
                    onDataLoad?.({
                        start: formatted[0].time,
                        end: formatted[formatted.length - 1].time,
                        totalBars: formatted.length
                    })
                    isFirstLoad.current = false
                }
            } else if (isFirstLoad.current) {
                setLastError(res.error || "Failed to fetch live data")
            }
        } catch (e: any) {
            console.error("Live fetch error:", e)
            setLastError(e.message)
        } finally {
            setIsLoading(false)
        }
    }, [onDataLoad])

    useEffect(() => {
        fetchData()
        const id = setInterval(() => {
            if (isRunningRef.current) fetchData()
        }, 2000)
        return () => clearInterval(id)
    }, [fetchData])

    return {
        fullData,
        fullDataRange: fullData.length > 0 ? {
            start: fullData[0].time,
            end: fullData[fullData.length - 1].time
        } : null,
        isLoading,
        livePrice,
        lastUpdate,
        isRunning,
        setIsRunning,
        lastError,
        // Mock historical methods for live mode compatibility
        loadMoreData: async () => { },
        jumpToTime: async () => ({ success: false, needsScroll: false }),
        hasMoreData: false,
        isLoadingMore: false,
        totalRows: fullData.length,
        baseTimeframe: timeframe,
        isResampling: false
    }
}
