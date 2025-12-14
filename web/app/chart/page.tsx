"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { getAvailableData } from "@/actions/data-actions"
import { ChartPageClient } from "@/components/chart-page-client"
import { useSearchParams } from "next/navigation"

export default function ChartPage() {
    const searchParams = useSearchParams()
    const [data, setData] = useState<{ tickers: string[]; timeframes: string[]; tickerMap: Record<string, string[]> } | null>(null)
    const [markers, setMarkers] = useState<any[]>([])

    // Load available data
    useEffect(() => {
        getAvailableData().then(setData)
    }, [])

    // Load markers from localStorage
    useEffect(() => {
        const stored = localStorage.getItem('backtest_markers_preview')
        if (stored) {
            try {
                setMarkers(JSON.parse(stored))
                // Optional: Clear markers after loading? 
                // localStorage.removeItem('backtest_markers_preview') 
                // Better to keep them so refresh works.
            } catch (e) {
                console.error("Failed to parse markers", e)
            }
        }
    }, [])

    if (!data) return <div className="flex items-center justify-center h-screen">Loading Chart...</div>

    const ticker = searchParams.get('ticker') || "ES1!"
    const timeframe = searchParams.get('timeframe') || "1m"
    const indicators = searchParams.get('indicators')?.split(',') || []

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
            />
        </div>
    )
}
