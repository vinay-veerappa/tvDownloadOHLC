'use client'

import { useState, useEffect, useCallback } from 'react'
import { TopToolbar } from './top-toolbar'
import { ChartWrapper, type NavigationFunctions } from './chart-wrapper'
import { BottomBar } from './bottom-bar'
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
const TIMEZONE_STORAGE_KEY = 'chart-timezone'

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
    const [displayTimezone, setDisplayTimezone] = useState('America/New_York')

    // Navigation state
    const [navigation, setNavigation] = useState<NavigationFunctions | null>(null)
    const [dataRange, setDataRange] = useState<{ start: number; end: number; totalBars: number } | null>(null)

    // Load preferences from localStorage on mount
    useEffect(() => {
        const savedMagnet = localStorage.getItem(MAGNET_STORAGE_KEY) as MagnetMode | null
        if (savedMagnet && ['off', 'weak', 'strong'].includes(savedMagnet)) {
            setMagnetMode(savedMagnet)
        }

        const savedTimezone = localStorage.getItem(TIMEZONE_STORAGE_KEY)
        if (savedTimezone) {
            setDisplayTimezone(savedTimezone)
        }
    }, [])

    const handleMagnetModeChange = (mode: MagnetMode) => {
        setMagnetMode(mode)
        localStorage.setItem(MAGNET_STORAGE_KEY, mode)
    }

    const handleTimezoneChange = (tz: string) => {
        setDisplayTimezone(tz)
        localStorage.setItem(TIMEZONE_STORAGE_KEY, tz)
    }

    // Replay state
    const [replayState, setReplayState] = useState<{ isReplayMode: boolean, index: number, total: number }>({
        isReplayMode: false,
        index: 0,
        total: 0
    })

    // Handle navigation ready callback from ChartWrapper
    const handleNavigationReady = useCallback((nav: NavigationFunctions) => {
        setNavigation(nav)
        // Also get initial data range
        const range = nav.getDataRange()
        setDataRange(range)
    }, [])

    const handleReplayStateChange = useCallback((state: { isReplayMode: boolean, index: number, total: number }) => {
        setReplayState(state)
    }, [])

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
                    displayTimezone={displayTimezone}
                    onNavigationReady={handleNavigationReady}
                    onReplayStateChange={handleReplayStateChange}
                />
            </div>

            {/* Bottom Bar with Timezone Selector and Navigation */}
            <BottomBar
                timezone={displayTimezone}
                onTimezoneChange={handleTimezoneChange}
                onScrollByBars={navigation?.scrollByBars}
                onScrollToStart={navigation?.scrollToStart}
                onScrollToEnd={navigation?.scrollToEnd}
                onScrollToTime={navigation?.scrollToTime}
                dataRange={dataRange}
                // Replay props
                onStartReplay={navigation?.startReplay}
                onStepForward={navigation?.stepForward}
                onStepBack={navigation?.stepBack}
                onStopReplay={navigation?.stopReplay}
                isReplayMode={replayState.isReplayMode}
                replayIndex={replayState.index}
                totalBars={replayState.total}
            />
        </>
    )
}
