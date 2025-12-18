"use client"

import { Suspense, useEffect, useState } from "react"
import { getAvailableData } from "@/actions/data-actions"
import { ChartPageClient } from "@/components/chart-page-client"
import { useSearchParams } from "next/navigation"

function LiveChartContent() {
    const searchParams = useSearchParams()
    const [data, setData] = useState<{ tickers: string[]; timeframes: string[]; tickerMap: Record<string, string[]> } | null>(null)

    // Load available data for the selectors
    useEffect(() => {
        getAvailableData().then(setData)
    }, [])

    if (!data) return <div className="flex items-center justify-center h-screen bg-background">Loading Live Chart...</div>

    const ticker = searchParams.get('ticker') || "/NQ"
    const timeframe = searchParams.get('timeframe') || "1m"
    const indicators = searchParams.get('indicators')?.split(',') || []

    return (
        <ChartPageClient
            tickers={data.tickers}
            timeframes={data.timeframes}
            tickerMap={data.tickerMap}
            ticker={ticker}
            timeframe={timeframe}
            style="candles"
            indicators={indicators}
            mode="live"
        />
    )
}

export default function LiveChartPage() {
    return (
        <Suspense fallback={<div className="flex items-center justify-center h-screen bg-background text-foreground">Loading...</div>}>
            <div className="flex flex-col h-screen overflow-hidden">
                <LiveChartContent />
            </div>
        </Suspense>
    )
}
