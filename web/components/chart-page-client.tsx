'use client'

import { useState, useEffect, useCallback } from 'react'
import { TopToolbar } from './top-toolbar'
import { useTheme } from "next-themes"
import { ChartWrapper, type NavigationFunctions } from './chart-wrapper'
import { BottomBar } from './bottom-bar'
import { BottomPanel } from './trading/bottom-panel'
import { TradingProvider } from '@/context/trading-context'
import type { MagnetMode } from '@/lib/charts/magnet-utils'
import { VWAPSettingsDialog } from './vwap-settings-dialog'

interface ChartPageClientProps {
    tickers: string[]
    timeframes: string[]
    tickerMap: Record<string, string[]>
    ticker: string
    timeframe: string
    style: string
    indicators: string[]
    markers?: any[]
    trades?: any[]
    mode?: 'historical' | 'live'
}

const MAGNET_STORAGE_KEY = 'chart_magnet_mode'
const TIMEZONE_STORAGE_KEY = 'chart-timezone'
const BOTTOM_PANEL_STORAGE_KEY = 'bottom_panel_open'

export function ChartPageClient({
    tickers,
    timeframes,
    tickerMap,
    ticker,
    timeframe,
    style,
    indicators,
    markers,
    trades,
    mode = 'historical'
}: ChartPageClientProps) {
    const [magnetMode, setMagnetMode] = useState<MagnetMode>('off')
    const [displayTimezone, setDisplayTimezone] = useState('America/New_York')
    // VWAP Settings State
    const [vwapSettings, setVwapSettings] = useState<any>({
        anchor: 'session',
        anchor_time: '09:30', // Default, will be adjusted by logic
        bands: [1.0, 2.0, 3.0]
    })
    const [isVwapSettingsOpen, setIsVwapSettingsOpen] = useState(false)

    // Update VWAP settings when ticker changes (Futures vs Stocks)
    useEffect(() => {
        // Simple heuristic: If ticker contains '!' (e.g. ES1!), it's a future -> 18:00
        // Otherwise (e.g. SPX, AAPL), it's a stock/index -> 09:30
        const isFuture = ticker.includes('!')

        // Load from localStorage or use defaults
        const savedSettings = localStorage.getItem('vwap-settings')
        let initialSettings = savedSettings ? JSON.parse(savedSettings) : {
            anchor: 'session',
            bands: [1.0, 2.0, 3.0],
            bandsEnabled: [true, true, true]
        }

        // Always override anchor_time based on ticker type logic (unless we want to persist that too?)
        // Better to respect the "Smart Default" for anchor time, but persist other preferences like bands
        setVwapSettings((prev: any) => ({
            ...initialSettings,
            ...prev, // Keep current session state if any? actually we want to overwrite with logic + storage
            anchor_time: isFuture ? '18:00' : '09:30'
        }))
    }, [ticker])

    // Save VWAP settings to localStorage whenever they change
    useEffect(() => {
        if (vwapSettings) {
            // Don't save anchor_time as it's dynamic per ticker type, or maybe we should? 
            // Let's save everything for now, but the loader overrides anchor_time.
            localStorage.setItem('vwap-settings', JSON.stringify(vwapSettings))
        }
    }, [vwapSettings])

    // Navigation state
    const [navigation, setNavigation] = useState<NavigationFunctions | null>(null)
    const [dataRange, setDataRange] = useState<{ start: number; end: number; totalBars: number } | null>(null)
    const [fullDataRange, setFullDataRange] = useState<{ start: number; end: number } | null>(null)

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

        // Load bottom panel state (default closed)
        const savedPanelState = localStorage.getItem(BOTTOM_PANEL_STORAGE_KEY)
        if (savedPanelState !== null) {
            setIsPanelOpen(savedPanelState === 'true')
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
        // Also get initial data range and full data range
        const range = nav.getDataRange()
        setDataRange(range)
        const fullRange = nav.getFullDataRange()
        setFullDataRange(fullRange)
    }, [])

    const handleReplayStateChange = useCallback((state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => {
        setReplayState(state)
    }, [])

    // Handle data load updates (fix for stale calendar constraints)
    const handleDataLoad = useCallback((range: { start: number; end: number; totalBars: number }) => {
        setDataRange(range)
    }, [])

    // Poll for fullDataRange after navigation is ready (metadata loads async)
    useEffect(() => {
        if (!navigation) return

        // Try immediately
        const fullRange = navigation.getFullDataRange()
        if (fullRange) {
            setFullDataRange(fullRange)
            return
        }

        // If null, poll every 500ms until available
        const interval = setInterval(() => {
            const fullRange = navigation.getFullDataRange()
            if (fullRange) {
                setFullDataRange(fullRange)
                clearInterval(interval)
            }
        }, 500)

        return () => clearInterval(interval)
    }, [navigation])



    // Bottom Panel state
    const [isPanelOpen, setIsPanelOpen] = useState(false)

    // Save panel state to localStorage when it changes
    useEffect(() => {
        localStorage.setItem(BOTTOM_PANEL_STORAGE_KEY, isPanelOpen.toString())
    }, [isPanelOpen])

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
                        markers={markers}
                        magnetMode={magnetMode}
                        displayTimezone={displayTimezone}
                        onNavigationReady={handleNavigationReady}
                        onReplayStateChange={handleReplayStateChange}
                        onDataLoad={handleDataLoad}
                        initialReplayTime={replayState.isReplayMode ? replayState.currentTime : undefined}
                        vwapSettings={vwapSettings}
                        trades={trades}
                        onOpenVwapSettings={() => setIsVwapSettingsOpen(true)}
                        onTimeframeChange={(newTf) => {
                            // Use window.location to force a full navigation/refresh state, 
                            // matching the existing pattern of full remount on key props
                            const params = new URLSearchParams(window.location.search)
                            params.set('timeframe', newTf)
                            window.location.search = params.toString()
                        }}
                        mode={mode}
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
                        fullDataRange={fullDataRange}
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
                <VWAPSettingsDialog
                    settings={vwapSettings}
                    onSave={setVwapSettings}
                    open={isVwapSettingsOpen}
                    onOpenChange={setIsVwapSettingsOpen}
                    showTrigger={false}
                />
            </div>
        </TradingProvider>
    )
}
