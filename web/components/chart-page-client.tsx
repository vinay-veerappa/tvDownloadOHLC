'use client'

import { useState, useEffect } from 'react'
import { TopToolbar } from './top-toolbar'
import { ChartWrapper } from './chart-wrapper'
import type { MagnetMode } from '@/lib/charts/magnet-utils'

interface ChartPageClientProps {
    tickers: string[]
    timeframes: string[]
    tickerMap: Record<string, string[]>
    ticker: string
    timeframe: string
    style: string
    indicators: string[]
}

const MAGNET_STORAGE_KEY = 'chart_magnet_mode'

export function ChartPageClient({
    tickers,
    timeframes,
    tickerMap,
    ticker,
    timeframe,
    style,
    indicators
}: ChartPageClientProps) {
    const [magnetMode, setMagnetMode] = useState<MagnetMode>('off')

    // Load magnet mode from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem(MAGNET_STORAGE_KEY) as MagnetMode | null
        if (saved && ['off', 'weak', 'strong'].includes(saved)) {
            setMagnetMode(saved)
        }
    }, [])

    const handleMagnetModeChange = (mode: MagnetMode) => {
        setMagnetMode(mode)
        localStorage.setItem(MAGNET_STORAGE_KEY, mode)
    }

    return (
        <>
            {/* Top Toolbar */}
            <div className="border-b">
                <TopToolbar
                    tickers={tickers}
                    timeframes={timeframes}
                    tickerMap={tickerMap}
                    magnetMode={magnetMode}
                    onMagnetModeChange={handleMagnetModeChange}
                >
                    <div className="flex items-center gap-4 px-4">
                        <div className="h-4 w-[1px] bg-border" />
                        <div className="flex items-center gap-2 text-sm">
                            <span className="text-muted-foreground">Trades:</span>
                            <span className="font-bold">0</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                            <span className="text-muted-foreground">Win Rate:</span>
                            <span className="font-bold">0%</span>
                        </div>
                    </div>
                </TopToolbar>
            </div>

            {/* Chart Wrapper */}
            <div className="flex-1 p-0 relative min-h-0">
                <ChartWrapper
                    ticker={ticker}
                    timeframe={timeframe}
                    style={style}
                    indicators={indicators}
                    magnetMode={magnetMode}
                />
            </div>
        </>
    )
}
