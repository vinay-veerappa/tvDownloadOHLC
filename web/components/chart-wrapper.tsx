
'use client'

import dynamic from 'next/dynamic'
import { useState, useRef, useEffect, useCallback } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'
import { RightSidebar, Drawing } from './right-sidebar'
import type { ChartContainerRef } from './chart-container'
import { IndicatorStorage } from '@/lib/indicator-storage'
import { IndicatorSettingsModal } from './indicator-settings-modal'
import type { MagnetMode } from '@/lib/charts/magnet-utils'
import { BuySellPanel } from "@/components/trading/buy-sell-panel"
import { toast } from "sonner"
import { SettingsDialog } from "@/components/settings-dialog"
import { useTrading } from "@/context/trading-context"
import { useTheme } from "@/context/theme-context"

// ... imports
import { VWAPSettings } from "@/lib/indicator-api"

const ChartContainer = dynamic(
    () => import('./chart-container').then((mod) => mod.ChartContainer),
    { ssr: false }
)

export interface NavigationFunctions {
    scrollByBars: (n: number) => void
    scrollToStart: () => void
    scrollToEnd: () => void
    scrollToTime: (time: number) => void
    getDataRange: () => { start: number; end: number; totalBars: number } | null
    getFullDataRange: () => { start: number; end: number } | null  // Full range from metadata
    // Replay mode functions
    startReplay: (options?: { index?: number, time?: number }) => void
    startReplaySelection: () => void
    stepForward: () => void
    stepBack: () => void
    stopReplay: () => void
    isReplayMode: () => boolean
    getReplayIndex: () => number
    getTotalBars: () => number
}

interface ChartWrapperProps {
    ticker: string
    timeframe: string
    style: string
    indicators: string[]
    magnetMode?: MagnetMode
    displayTimezone?: string
    onNavigationReady?: (nav: NavigationFunctions) => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    initialReplayTime?: number // Timestamp to restore replay position after remount
    vwapSettings?: VWAPSettings
    onOpenVwapSettings?: () => void
    onTimeframeChange?: (tf: string) => void
}

export function ChartWrapper(props: ChartWrapperProps) {
    const { themeParams } = useTheme()
    const [selectedTool, setSelectedTool] = useState<DrawingTool>("cursor")
    const [showTrading, setShowTrading] = useState(false)
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [drawings, setDrawings] = useState<Drawing[]>([])
    const chartRef = useRef<ChartContainerRef>(null)

    // Live Price State
    const [currentPrice, setCurrentPrice] = useState<number>(0)

    // Trading Engine (Global Context)
    const { activePosition: position, executeOrder, updatePrice, modifyOrder, modifyPosition, pendingOrders } = useTrading()

    // Sync Chart Price with Context
    useEffect(() => {
        if (currentPrice > 0) {
            updatePrice(currentPrice, props.ticker)
        }
    }, [currentPrice, updatePrice, props.ticker])

    // Load indicators from storage
    const chartId = IndicatorStorage.getDefaultChartId()
    const [indicators, setIndicators] = useState<string[]>([])
    const [indicatorParams, setIndicatorParams] = useState<Record<string, any>>({})

    // Indicator Settings Modal State
    const [indicatorSettingsOpen, setIndicatorSettingsOpen] = useState(false)
    const [editingIndicator, setEditingIndicator] = useState<string | null>(null)
    const [indicatorOptions, setIndicatorOptions] = useState<Record<string, any>>({})

    // Notify parent when navigation is ready (only once)
    const navReadyRef = useRef(false)
    useEffect(() => {
        // Use a short timeout to ensure chartRef is populated after ChartContainer mounts
        const timer = setTimeout(() => {
            if (chartRef.current && props.onNavigationReady && !navReadyRef.current) {
                navReadyRef.current = true
                const ref = chartRef.current
                props.onNavigationReady({
                    scrollByBars: (n) => chartRef.current?.scrollByBars(n),
                    scrollToStart: () => chartRef.current?.scrollToStart(),
                    scrollToEnd: () => chartRef.current?.scrollToEnd(),
                    scrollToTime: (t) => chartRef.current?.scrollToTime(t),
                    getDataRange: () => chartRef.current?.getDataRange() ?? null,
                    getFullDataRange: () => chartRef.current?.getFullDataRange() ?? null,
                    // Replay functions (Delegated to Ref to ensure fresh state)
                    startReplay: (opts) => chartRef.current?.startReplay(opts),
                    stepForward: () => chartRef.current?.stepForward(),
                    stepBack: () => chartRef.current?.stepBack(),
                    stopReplay: () => chartRef.current?.stopReplay(),
                    isReplayMode: () => chartRef.current?.isReplayMode() ?? false,
                    getReplayIndex: () => chartRef.current?.getReplayIndex() ?? 0,
                    getTotalBars: () => chartRef.current?.getTotalBars() ?? 0,
                    startReplaySelection: () => chartRef.current?.startReplaySelection()
                })
            }
        }, 500)
        return () => clearTimeout(timer)
    }, [props.onNavigationReady])

    useEffect(() => {
        const savedIndicators = IndicatorStorage.getIndicators(chartId)

        if (savedIndicators.length > 0) {
            setIndicators(savedIndicators.filter(i => i.enabled).map(i => i.type))

            // Extract params into map
            const paramsMap: Record<string, any> = {}
            savedIndicators.forEach(ind => {
                if (ind.params) paramsMap[ind.type] = ind.params
            })

            setIndicatorParams(prev => {
                // Merge storage params, but prioritize existing local state to prevent overwrite race conditions
                const next = { ...prev };
                Object.entries(paramsMap).forEach(([key, value]) => {
                    // Only load from storage if we don't have local state (e.g. init or new indicator)
                    if (next[key] === undefined) {
                        next[key] = value;
                    }
                });
                return next;
            })
        } else if (props.indicators && props.indicators.length > 0) {
            const initialIndicators = props.indicators.map((type: string) => ({
                type,
                enabled: true,
                params: {}
            }))
            IndicatorStorage.saveIndicators(chartId, initialIndicators)
            setIndicators(props.indicators)
        }
    }, [chartId, props.indicators])

    // Toggle indicator visibility
    const handleToggleIndicator = useCallback((type: string) => {
        IndicatorStorage.toggleIndicator(chartId, type);
        // Force re-render by updating state
        const updated = IndicatorStorage.getIndicators(chartId);
        setIndicators(updated.filter(i => i.enabled).map(i => i.type));
    }, [chartId]);

    // Save params from child components
    const handleIndicatorParamsChange = useCallback((type: string, newParams: any) => {
        setIndicatorParams(prev => ({ ...prev, [type]: newParams }));

        // Use targeted update to avoid overwriting entire storage with potentially stale list
        const success = IndicatorStorage.updateIndicatorParams(chartId, type, newParams);
        if (!success) {
            IndicatorStorage.addIndicator(chartId, {
                type,
                params: newParams,
                enabled: true
            });
        }
    }, [chartId]);

    // Global Selection State
    const [selection, setSelection] = useState<{ type: 'drawing' | 'indicator', id: string } | null>(null);

    // Validated order execution - only allows trading in replay mode
    const validatedExecuteOrder = useCallback((params: Parameters<typeof executeOrder>[0]) => {
        const isReplay = chartRef.current?.isReplayMode() ?? false
        const replayIndex = chartRef.current?.getReplayIndex() ?? 0
        const totalBars = chartRef.current?.getTotalBars() ?? 0

        // Must be in replay mode to trade
        if (!isReplay) {
            toast.error("Start Replay mode first to place trades")
            return
        }

        // Cannot trade at end of data
        if (totalBars > 0 && replayIndex >= totalBars - 1) {
            toast.error("Cannot trade at end of data. Step back or load more data to continue.")
            return
        }

        executeOrder(params)
    }, [executeOrder])

    const handleDrawingCreated = useCallback((drawing: Drawing) => {
        setDrawings(prev => {
            if (prev.some(d => d.id === drawing.id)) return prev;
            return [...prev, drawing];
        });
    }, []);

    const handleDeleteDrawing = useCallback((id: string) => {
        if (chartRef.current) {
            chartRef.current.deleteDrawing(id)
            setDrawings(prev => prev.filter(d => d.id !== id))
            if (selection?.id === id) setSelection(null);
        }
    }, [selection?.id]);

    const handleDeleteIndicator = useCallback((type: string) => {
        IndicatorStorage.removeIndicator(chartId, type)
        setIndicators(prev => prev.filter(ind => ind !== type))
        if (selection?.id === type) setSelection(null);
    }, [chartId, selection?.id]);

    const handleDeleteSelection = useCallback(() => {
        if (!selection) return;

        if (selection.type === 'drawing') {
            handleDeleteDrawing(selection.id);
        } else if (selection.type === 'indicator') {
            handleDeleteIndicator(selection.id);
        }
    }, [selection, handleDeleteDrawing, handleDeleteIndicator]);

    const handleChartDrawingDeleted = useCallback((id: string) => {
        setDrawings(prev => prev.filter(d => d.id !== id))
        if (selection?.id === id) setSelection(null);
    }, [selection?.id]);

    // Indicator Settings Handlers
    const handleEditIndicator = useCallback((type: string) => {
        // Handle special case for VWAP
        if (type === 'vwap') {
            props.onOpenVwapSettings?.();
            return;
        }

        // Handle Daily Profiler (uses PropertiesModal via ChartContainer)
        if (type === 'daily-profiler') {
            chartRef.current?.editDrawing('daily-profiler');
            return;
        }

        // Handle Hourly Profiler (uses PropertiesModal via ChartContainer)
        if (type === 'hourly-profiler') {
            chartRef.current?.editDrawing('hourly-profiler');
            return;
        }

        // Handle Range Extensions (uses PropertiesModal via ChartContainer)
        if (type === 'range-extensions') {
            chartRef.current?.editDrawing('range-extensions');
            return;
        }

        // Parse existing options from type string (e.g., "sma:9" -> period=9)
        const [indType, param] = type.split(":");
        const existingOptions: Record<string, any> = {};

        if (indType === 'sma' || indType === 'ema') {
            existingOptions.period = param ? parseInt(param) : 9;
            existingOptions.color = indType === 'sma' ? '#2962FF' : '#FF6D00';
            existingOptions.lineWidth = 1;
        }

        setEditingIndicator(type);
        setIndicatorOptions(existingOptions);
        setIndicatorSettingsOpen(true);
    }, [props.onOpenVwapSettings]);

    const handleSaveIndicatorSettings = useCallback((newOptions: Record<string, any>) => {
        if (!editingIndicator) return;

        const [indType] = editingIndicator.split(":");

        // Build new indicator string with updated params
        let newIndicatorStr = indType;
        if (indType === 'sma' || indType === 'ema') {
            newIndicatorStr = `${indType}:${newOptions.period || 9}`;
        }

        // Update indicators list
        setIndicators(prev => {
            const idx = prev.findIndex(i => i === editingIndicator);
            if (idx === -1) return prev;
            const updated = [...prev];
            updated[idx] = newIndicatorStr;
            return updated;
        });

        // Update storage
        const savedIndicators = IndicatorStorage.getIndicators(chartId);
        const updated = savedIndicators.map(ind => {
            if (ind.type === editingIndicator) {
                return { ...ind, type: newIndicatorStr, params: newOptions };
            }
            return ind;
        });
        IndicatorStorage.saveIndicators(chartId, updated);

        setEditingIndicator(null);
    }, [editingIndicator, chartId]);

    // Map indicator types to display objects for sidebar
    // Show ALL indicators (including hidden ones) in sidebar
    const allSavedIndicators = IndicatorStorage.getIndicators(chartId);
    const indicatorObjects = allSavedIndicators.map(ind => {
        const [indType, param] = ind.type.split(":");
        let label = ind.type.toUpperCase();
        if (indType === 'sma') label = `SMA (${param || 9})`;
        else if (indType === 'ema') label = `EMA (${param || 9})`;
        else if (indType === 'sessions') label = 'Session Highlighting';
        else if (indType === 'watermark') label = `Watermark: ${param || 'Text'}`;
        else if (indType === 'daily-profiler') label = 'Daily Profiler';
        else if (indType === 'hourly-profiler') label = 'Hourly Profiler';
        else if (indType === 'range-extensions') label = 'Range Extensions';
        return { type: ind.type, label, enabled: ind.enabled };
    });

    return (
        <>
            <div className="flex flex-1 h-full overflow-hidden">
                <LeftToolbar
                    selectedTool={selectedTool}
                    onToolSelect={setSelectedTool}
                    showTrading={showTrading}
                    onToggleTrading={() => setShowTrading(!showTrading)}
                />
                <div className="flex-1 relative min-w-0">
                    {/* Trading Panel Overlay */}
                    {showTrading && (
                        <div className="absolute top-4 left-4 z-20">
                            <BuySellPanel
                                currentPrice={currentPrice}
                                onBuy={(qty, type, price, sl, tp) => validatedExecuteOrder({
                                    ticker: props.ticker,
                                    direction: 'BUY',
                                    quantity: qty,
                                    orderType: type,
                                    price: price || 0,
                                    stopLoss: sl,
                                    takeProfit: tp
                                })}
                                onSell={(qty, type, price, sl, tp) => validatedExecuteOrder({
                                    ticker: props.ticker,
                                    direction: 'SELL',
                                    quantity: qty,
                                    orderType: type,
                                    price: price || 0,
                                    stopLoss: sl,
                                    takeProfit: tp
                                })}
                                position={position}
                            />
                        </div>
                    )}
                    <ChartContainer
                        ref={chartRef}
                        {...props}
                        theme={themeParams}
                        selectedTool={selectedTool}
                        onToolSelect={setSelectedTool}
                        onDrawingCreated={handleDrawingCreated}
                        onDrawingDeleted={handleChartDrawingDeleted}
                        indicators={indicators}
                        indicatorParams={indicatorParams}
                        onIndicatorParamsChange={handleIndicatorParamsChange}
                        selection={selection}
                        onSelectionChange={setSelection}
                        onDeleteSelection={handleDeleteSelection}
                        onPriceChange={setCurrentPrice}
                        position={position}
                        pendingOrders={pendingOrders}

                        onModifyOrder={modifyOrder}
                        onModifyPosition={modifyPosition}
                        vwapSettings={props.vwapSettings}
                        onTimeframeChange={props.onTimeframeChange}
                    />
                </div>
                <RightSidebar
                    drawings={drawings}
                    indicators={indicatorObjects}
                    onDeleteDrawing={handleDeleteDrawing}
                    onDeleteIndicator={handleDeleteIndicator}
                    onToggleIndicator={handleToggleIndicator}
                    onEditDrawing={(id) => chartRef.current?.editDrawing(id)}
                    onEditIndicator={handleEditIndicator}
                    selection={selection}
                    onSelect={setSelection}
                    onOpenSettings={() => setSettingsOpen(true)}
                />
            </div>

            {/* General Settings Modal */}
            <SettingsDialog
                open={settingsOpen}
                onOpenChange={setSettingsOpen}
                showTrading={showTrading}
                onToggleTrading={() => setShowTrading(!showTrading)}
            />

            {/* Indicator Settings Modal */}
            <IndicatorSettingsModal
                open={indicatorSettingsOpen}
                onOpenChange={setIndicatorSettingsOpen}
                indicatorType={editingIndicator || ''}
                initialOptions={indicatorOptions}
                onSave={handleSaveIndicatorSettings}
            />
        </>
    )
}
