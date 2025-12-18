"use client"

import { Suspense, useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { getAvailableData } from "@/actions/data-actions"
import { ChartPageClient } from "@/components/chart-page-client"
import { useSearchParams } from "next/navigation"

function ChartPageContent() {
    const searchParams = useSearchParams()
    const [data, setData] = useState<{ tickers: string[]; timeframes: string[]; tickerMap: Record<string, string[]> } | null>(null)
    const [markers, setMarkers] = useState<any[]>([])
    const [trades, setTrades] = useState<any[]>([])

    // Load available data
    useEffect(() => {
        getAvailableData().then(setData)
    }, [])

    // Load markers and trades from localStorage
    useEffect(() => {
        const storedMarkers = localStorage.getItem('backtest_markers_preview')
        if (storedMarkers) {
            try {
                setMarkers(JSON.parse(storedMarkers))
            } catch (e) {
                console.error("Failed to parse markers", e)
            }
        }

        const storedTrades = localStorage.getItem('backtest_trades_preview')
        if (storedTrades) {
            try {
                setTrades(JSON.parse(storedTrades))
            } catch (e) {
                console.error("Failed to parse trades", e)
            }
        }
    }, [])

    if (!data) return <div className="flex items-center justify-center h-screen">Loading Chart...</div>

    const ticker = searchParams.get('ticker') || "ES1!"
    const timeframe = searchParams.get('timeframe') || "1m"
    const indicators = searchParams.get('indicators')?.split(',') || []
    const mode = (searchParams.get('mode') as 'historical' | 'live') || 'historical'

    return (
        <div className="flex flex-col h-screen overflow-hidden">
            <ChartPageClient
                tickers={data.tickers}
                timeframes={data.timeframes}
                tickerMap={data.tickerMap}
                ticker={ticker}
                timeframe={timeframe}
                style="candles"
                indicators={indicators}
                markers={markers}
                trades={trades}
                mode={mode}
            />
        </div>
    )
}

export default function ChartPage() {
    return (
        <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
            <ChartPageContent />
        </Suspense>
    )
}

