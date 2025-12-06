'use client'

import { useState, useEffect, useCallback } from 'react'
import { TopToolbar } from './top-toolbar'
import { useTheme } from "next-themes"
import { ChartWrapper, type NavigationFunctions } from './chart-wrapper'
import { BottomBar } from './bottom-bar'
import { BottomPanel } from './trading/bottom-panel'
import { TradingProvider } from '@/context/trading-context'
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

    // Replay state (lifted from child to persist across timeframe changes)
    const [replayState, setReplayState] = useState<{ isReplayMode: boolean, index: number, total: number, currentTime?: number }>({
        isReplayMode: false,
        index: 0,
        total: 0,
        currentTime: undefined
    })

    // Handle navigation ready callback from ChartWrapper
    const handleNavigationReady = useCallback((nav: NavigationFunctions) => {
        setNavigation(nav)
        // Also get initial data range
        const range = nav.getDataRange()
        setDataRange(range)
    }, [])

    const handleReplayStateChange = useCallback((state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => {
        setReplayState(state)
    }, [])

    // Handle data load updates (fix for stale calendar constraints)
    const handleDataLoad = useCallback((range: { start: number; end: number; totalBars: number }) => {
        setDataRange(range)
    }, [])



    // Bottom Panel state
    const [isPanelOpen, setIsPanelOpen] = useState(false)
    const { resolvedTheme } = useTheme()

    return (
        <TradingProvider>
            <div className="flex flex-col h-screen overflow-hidden bg-background">
                {/* Top Toolbar */}
                <div className="flex-none border-b border-border">
                    <TopToolbar
                        tickers={tickers}
                        timeframes={timeframes}
                        tickerMap={tickerMap}
                        magnetMode={magnetMode}
                        onMagnetModeChange={handleMagnetModeChange}
                    />
                </div>

                {/* Chart Wrapper (Flex Grow) */}
                <div className="flex-1 min-h-0 relative">
                    <ChartWrapper
                        key={`${ticker}-${timeframe}`} // Force hard remount to prevent state leakage/double-rendering artifacts
                        ticker={ticker}
                        timeframe={timeframe}
                        style={style}
                        indicators={indicators}
                        magnetMode={magnetMode}
                        displayTimezone={displayTimezone}
                        onNavigationReady={handleNavigationReady}
                        onReplayStateChange={handleReplayStateChange}
                        onDataLoad={handleDataLoad}
                        initialReplayTime={replayState.isReplayMode ? replayState.currentTime : undefined}
                    />
                </div>

                {/* Bottom Bar (Status/Controls) - Flex None */}
                <div className="flex-none border-t border-border">
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
                        onStartReplaySelection={navigation?.startReplaySelection}
                        onStepForward={navigation?.stepForward}
                        onStepBack={navigation?.stepBack}
                        onStopReplay={navigation?.stopReplay}
                        isReplayMode={replayState.isReplayMode}
                        replayIndex={replayState.index}
                        totalBars={replayState.total}
                    />
                </div>

                {/* Trading Panel (Docked Bottom) - Flex None */}
                <div className="flex-none z-20">
                    <BottomPanel
                        isOpen={isPanelOpen}
                        onToggle={() => setIsPanelOpen(!isPanelOpen)}
                        height={250}
                    />
                </div>
            </div>
        </TradingProvider>
    )
}
