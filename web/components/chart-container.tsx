"use client"

import { createPortal } from "react-dom"
import { useEffect, useRef, useState, useMemo, forwardRef, useImperativeHandle, memo } from "react"
import { useChart } from "@/hooks/use-chart"
import { DrawingTool } from "./left-toolbar"
import { Drawing } from "./right-sidebar"
import { PropertiesModal } from "./properties-modal"
import { DrawingStorage, SerializedDrawing } from "@/lib/drawing-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"
import { useTradeContext } from "@/components/journal/trade-context"
import { toast } from "sonner"
// New Hooks
import { useChartData } from "@/hooks/chart/use-chart-data"
import { useDataLoading } from "@/hooks/chart/use-data-loading"
import { useChartTrading } from "@/hooks/chart/use-chart-trading"
import { useChartDrag } from "@/hooks/chart/use-chart-drag"
// import { useDrawingInteraction } from "@/hooks/chart/use-drawing-interaction" // Removed Legacy
import { ChartContextMenu } from "@/components/chart/chart-context-menu"
import { ChartLegend, ChartLegendRef } from "@/components/chart/chart-legend"
import { OHLCLegend } from "@/lib/charts/plugins/ohlc-legend"
import { ChartCursorOverlay } from "@/components/chart-cursor-overlay"
import { VWAPSettings } from "@/lib/indicator-api"
import { useChartSettings } from "@/hooks/use-chart-settings"
import { ThemeParams } from "@/lib/themes"
import { EMSettingsDialog, EMSettings } from './em-settings-dialog'
import { V2OptionAdapter } from '@/lib/charts/v2/utils/v2-option-adapter'
import { DrawingStorage as V2DrawingStorage, SerializedDrawing as V2SerializedDrawing } from '@/lib/drawing-storage'
import { BaseLineTool } from "@/lib/charts/v2/core/model/base-line-tool"
import { ColorType } from "lightweight-charts"
import { RangeInfoPanel } from "./range-info-panel"
import { RangeTooltip } from "./range-tooltip"
import { RangeExtensions, RangeExtensionPeriod, getContractSpecs } from "@/lib/charts/indicators/range-extensions"
import { useKeyboardShortcuts } from "@/hooks/chart/use-keyboard-shortcuts"
import { TrendLineSettingsDialog, TrendLineSettingsOptions, DEFAULT_TRENDLINE_OPTIONS } from "@/components/drawing-settings/TrendLineSettings"
import { HorizontalLineSettingsDialog, HorizontalLineSettingsOptions, DEFAULT_HORIZONTAL_OPTIONS } from "@/components/drawing-settings/HorizontalLineSettings"
import { RectangleSettingsDialog, RectangleSettingsOptions, DEFAULT_RECTANGLE_OPTIONS } from "@/components/drawing-settings/RectangleSettings"
import { VerticalLineSettingsDialog, VerticalLineSettingsOptions, DEFAULT_VERTICAL_OPTIONS } from "@/components/drawing-settings/VerticalLineSettings"
import { RaySettingsDialog, RaySettingsOptions, DEFAULT_RAY_OPTIONS } from "@/components/drawing-settings/RaySettings"
import { FloatingToolbar } from "@/components/drawing/FloatingToolbar"
import { InlineTextEditor } from "@/components/drawing/InlineTextEditor"
import { TextSettings } from "@/components/drawing-settings/TextSettings"
import { isInlineEditable } from "@/lib/charts/plugins/base/inline-editable"
import { fetchProfilerStats, fetchLevelTouches, ProfilerSession, LevelTouchesResponse } from "@/lib/api/profiler"
import { useChartPreferences } from "@/hooks/use-chart-preferences"

import type { SessionType } from './top-toolbar'
import { useChartTheme } from "@/hooks/chart/use-chart-theme"
import { useChartLegend } from "@/hooks/chart/use-chart-legend"
import { useChartInfiniteScroll } from "@/hooks/chart/use-chart-infinite-scroll"
import { useTruthProfiler } from "@/hooks/chart/use-truth-profiler"
import { useExpectedMove } from "@/hooks/chart/use-expected-move"
import { useV2DrawingSandbox } from "@/hooks/chart/use-v2-drawing-sandbox"
import { useDrawingSelection } from "@/hooks/chart/use-drawing-selection"

interface ChartContainerProps {
    ticker: string
    timeframe: string
    style: string
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    onDrawingCreated: (drawing: Drawing) => void
    onDrawingDeleted?: (id: string) => void
    indicators: string[]
    theme?: ThemeParams // New Prop
    markers?: any[]
    magnetMode?: MagnetMode
    displayTimezone?: string
    sessionType?: SessionType
    selection?: { type: string, id: string } | null
    onSelectionChange?: (selection: { type: string, id: string } | null) => void
    onDeleteSelection?: () => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onPriceChange?: (price: number) => void
    initialReplayTime?: number // Timestamp to restore replay position after remount
    onTimeframeChange?: (tf: string) => void // New Prop for shortcuts
    mode?: 'historical' | 'live'
    livePrice?: number // Override for 200ms updates

    // Trading Props
    position?: {
        entryPrice: number
        direction: 'LONG' | 'SHORT'
        quantity: number
        unrealizedPnl: number
        stopLoss?: number
        takeProfit?: number
    } | null
    pendingOrders?: Array<{
        id: string
        orderType: 'MARKET' | 'LIMIT' | 'STOP'
        direction: 'LONG' | 'SHORT'
        price: number
        quantity: number
    }>
    onModifyOrder?: (id: string, updates: any) => void
    onModifyPosition?: (updates: any) => void
    vwapSettings?: VWAPSettings
    emSettings?: EMSettings | null
    indicatorParams?: Record<string, any>
    onIndicatorParamsChange?: (type: string, params: any) => void
    trades?: any[] // Backtest trades for visualization
    onOpenEMSettings?: () => void
}

export interface ChartContainerRef {
    deleteDrawing: (id: string) => void;
    editDrawing: (id: string) => void;
    // Navigation functions
    scrollByBars: (n: number) => void;
    scrollToStart: () => void;
    scrollToEnd: () => void;
    scrollToTime: (time: number) => void;
    getDataRange: () => { start: number; end: number; totalBars: number } | null;
    getFullDataRange: () => { start: number; end: number } | null;  // Full range from metadata
    // Replay mode functions
    startReplay: (options?: { index?: number, time?: number }) => void;
    startReplaySelection: () => void;
    stepForward: () => void;
    stepBack: () => void;
    stopReplay: () => void;
    isReplayMode: () => boolean;
    getReplayIndex: () => number;
    getTotalBars: () => number;
    // Capture
    takeScreenshot: () => HTMLCanvasElement | null;
    updateLivePrice: (price: number) => void;
}




export const ChartContainer = memo(forwardRef<ChartContainerRef, ChartContainerProps>(({
    ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, onDrawingDeleted,
    indicators, markers, magnetMode = 'off', displayTimezone = 'America/New_York', sessionType = 'ETH',
    selection, onSelectionChange, onDeleteSelection, onReplayStateChange, onDataLoad,
    onPriceChange, position, pendingOrders, onModifyOrder, onModifyPosition, initialReplayTime,
    vwapSettings, emSettings, indicatorParams, onIndicatorParamsChange, theme, onTimeframeChange, trades, mode, // Destructure mode
    livePrice, // Destructure
    onOpenEMSettings
}, ref) => {

    // 0. Global Chart Settings
    const { settings: chartSettings } = useChartSettings()
    const { showTrades } = chartSettings
    const { experimentalDrawingV2 } = useChartPreferences()
    const chartContainerRef = useRef<HTMLDivElement>(null)

    // Bridge for lazy access to chart methods
    const getVisibleTimeRangeRef = useRef<(() => { start: number, end: number, center: number } | null) | null>(null)

    const sessionHighlightingRef = useRef<any>(null);
    const vpPrimitiveRef = useRef<any>(null);
    const tradeVisualizationsRef = useRef<any[]>([]);
    const emPluginRef = useRef<any>(null);
    const sessionRangesRef = useRef<any>(null);
    const hourlyProfilerRef = useRef<any>(null);
    const rangeExtensionsRef = useRef<any>(null);
    const openingRangeRef = useRef<any>(null);

    // Data Flow Refs
    const dataRef = useRef<any[]>([]);
    const seriesRef = useRef<any>(null);

    // Range UI State
    const [rangeExtensionsActive, setRangeExtensionsActive] = useState(false);
    const [rangeData, setRangeData] = useState<RangeExtensionPeriod[]>([]);

    // --- Core Hooks ---
    const {
        fullData, data, replayMode, replayIndex, isSelectingReplayStart,
        setIsSelectingReplayStart, startReplay, startReplaySelection, stopReplay,
        stepForward, stepBack, findIndexForTime, setReplayIndex,
        loadMoreData, hasMoreData, isLoadingMore, fullDataRange, jumpToTime,
        hasMoreDataLeft, isLoadingMoreLeft, loadMoreDataLeft,
        hasMoreDataRight, isLoadingMoreRight, loadMoreDataRight
    } = useChartData({
        ticker, timeframe, onDataLoad, onReplayStateChange, onPriceChange,
        getVisibleTimeRange: () => getVisibleTimeRangeRef.current?.() ?? null,
        initialReplayTime,
        mode,
        sessionType
    })

    // Sync Data Refs
    useEffect(() => {
        dataRef.current = data;
    }, [data]);

    const isRestoringRangeRef = useRef(false)

    const {
        chart, series, primitives, scrollByBars, scrollToStart, scrollToEnd,
        scrollToTime, getDataRange, getVisibleTimeRange, indicators: activeIndicatorsRef,
        isDisposed
    } = useChart(
        chartContainerRef as React.RefObject<HTMLDivElement>,
        style, indicators, data, showTrades ? markers : [], displayTimezone, timeframe, vwapSettings, ticker, theme, mode, isRestoringRangeRef, mode === 'historical' && !replayMode
    )

    // Sync Series Ref
    useEffect(() => {
        seriesRef.current = series;
    }, [series]);

    // --- New Modular Hooks ---
    useChartTheme({ chart, series, theme })

    const { legendRef, canvasLegendRef } = useChartLegend({
        chart, series, ticker, timeframe, theme, data
    })

    useChartInfiniteScroll({
        chart,
        series,
        replayMode,
        data,
        hasMoreData,
        isLoadingMore,
        loadMoreData,
        hasMoreDataLeft,
        isLoadingMoreLeft,
        loadMoreDataLeft,
        hasMoreDataRight,
        isLoadingMoreRight,
        loadMoreDataRight,
        isRestoringRangeRef
    })

    const { truthSessions, truthLevels, truthProfilerRef } = useTruthProfiler({
        chart, series, ticker, indicators, theme, indicatorParams
    })

    const { settings: emSettingsState, setSettings: setEmSettingsState } = useExpectedMove({
        chart, series, ticker, indicators, theme,
        initialSettings: emSettings,
        onSettingsChange: (settings: EMSettings) => {
            onIndicatorParamsChange?.('expected-move', settings);
        },
        data
    })

    // 1. V2 Drawing Sandbox Logic (Hook)
    const v2SandboxRef = useV2DrawingSandbox({
        chart, series, ticker, timeframe, theme, drawingToolsEnabled: experimentalDrawingV2,
        selectedTool, // Pass selectedTool
        onDrawingCreated: (exportData) => {
            const drawing: V2SerializedDrawing = {
                id: exportData.id,
                type: exportData.toolType,
                points: exportData.points,
                options: exportData.options,
                createdAt: Date.now()
            };
            V2DrawingStorage.addDrawing(ticker, timeframe, drawing);
            if (onDrawingCreated) {
                onDrawingCreated({
                    ...drawing,
                    p1: drawing.points?.[0] || { time: 0, price: 0 },
                    p2: drawing.points?.[1] || { time: 0, price: 0 },
                    text: drawing.options.text?.value || '',
                    type: drawing.type as any
                } as any);
            }
            onToolSelect?.('cursor');
        },
        onDrawingModified: (exportData) => {
            const drawing: V2SerializedDrawing = {
                id: exportData.id,
                type: exportData.toolType,
                points: exportData.points,
                options: exportData.options,
                createdAt: Date.now()
            };
            V2DrawingStorage.updateDrawing(ticker, timeframe, drawing.id, drawing);
        },
        onDrawingDeleted: (id) => {
            V2DrawingStorage.deleteDrawing(ticker, timeframe, id);
            onDrawingDeleted?.(id);
        },
        onDrawingSelected: () => {},
        onDrawingDeselected: () => {}
    })

    const DRAWING_TYPES = [
        'trend-line', 'ray', 'fibonacci', 'rectangle', 'vertical-line', 'horizontal-line', 'text', 'risk-reward', 'measure', 'price-label', 'price-range', 'date-range', 'drawing',
        'TrendLine', 'Ray', 'FibRetracement', 'Rectangle', 'VerticalLine', 'HorizontalLine', 'Text', 'LongShortPosition', 'Measure', 'PriceLabel', 'PriceRange', 'DateRange'
    ];

    const {
        selectedDrawingId, setSelectedDrawingId,
        selectedDrawingRef,
        selectedDrawingType, setSelectedDrawingType,
        selectedDrawingOptions, setSelectedDrawingOptions,
        selectedDrawingPoints, setSelectedDrawingPoints,
        toolbarPosition, setToolbarPosition,
        showProperties: propertiesModalOpen, setShowProperties: setPropertiesModalOpen,
        isDrawingLocked, setIsDrawingLocked,
        isDrawingHidden, setIsDrawingHidden,
        textSettingsOpen, setTextSettingsOpen,
        inlineTextEditing, setInlineTextEditing,
        trendLineSettingsOpen, setTrendLineSettingsOpen,
        horizontalLineSettingsOpen, setHorizontalLineSettingsOpen,
        rectangleSettingsOpen, setRectangleSettingsOpen,
        verticalLineSettingsOpen, setVerticalLineSettingsOpen,
        raySettingsOpen, setRaySettingsOpen,
        deselectDrawing, deleteSelectedDrawing,
        handleUpdateDrawing
    } = useDrawingSelection({
        v2Sandbox: v2SandboxRef.current,
        onSelectionChange,
        onToolSelect,
        selectionProp: selection,
        DRAWING_TYPES
    })

    // Local state for Indicator Specific Settings
    const [selectedDrawingOptionsIndicator, setSelectedDrawingOptionsIndicator] = useState<any>({});
    const [selectedDrawingTypeIndicator, setSelectedDrawingTypeIndicator] = useState<string>('');

    // --- Helper Functions ---
    const openProperties = (drawing: any) => {
        const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;
        setSelectedDrawingId(id);
        selectedDrawingRef.current = drawing;
        const type = drawing._type || 'indicator';
        setSelectedDrawingType(type);
        setPropertiesModalOpen(true);

        const options = indicatorParams?.[id] || {};
        setSelectedDrawingOptions(options);
    };

    const handlePropertiesSave = (updates: any, points?: any) => {
        if (selectedDrawingId && v2SandboxRef.current) {
            // Check if it's a V2 drawing
            const tool = v2SandboxRef.current.plugin.getLineTool(selectedDrawingId);
            if (tool) {
                const adaptedUpdates = V2OptionAdapter.toV2NestedOptions(updates, selectedDrawingType);
                v2SandboxRef.current.updateDrawing(selectedDrawingId, adaptedUpdates, points);
                setSelectedDrawingOptions(updates);
                if (points) setSelectedDrawingPoints(points);
                return;
            }
        }

        // If not V2, handle as indicator or classic primitive
        if (selectedDrawingType && onIndicatorParamsChange) {
            onIndicatorParamsChange(selectedDrawingType, updates);
        }
        setPropertiesModalOpen(false);
        setTrendLineSettingsOpen(false);
        setHorizontalLineSettingsOpen(false);
        setRectangleSettingsOpen(false);
        setVerticalLineSettingsOpen(false);
        setRaySettingsOpen(false);
    };

    const handleInlineSave = (text: string) => {
        if (selectedDrawingId && v2SandboxRef.current) {
            v2SandboxRef.current.updateDrawing(selectedDrawingId, { text: { value: text } });
        }
        setInlineTextEditing(null);
    };

    const handleInlineCancel = () => setInlineTextEditing(null);

    const toggleDrawingLock = () => {
        const newLocked = !isDrawingLocked;
        handleUpdateDrawing({ locked: { value: newLocked } });
        setIsDrawingLocked(newLocked);
    };

    const toggleDrawingVisibility = () => {
        const newHidden = !isDrawingHidden;
        handleUpdateDrawing({ hidden: { value: newHidden } });
        setIsDrawingHidden(newHidden);
    };

    const cloneSelectedDrawing = () => {
        if (selectedDrawingId && v2SandboxRef.current) {
            v2SandboxRef.current.cloneDrawing(selectedDrawingId);
        }
    };

    const openDrawingSettings = () => {
        if (selectedDrawingType === 'trend-line') setTrendLineSettingsOpen(true);
        else if (selectedDrawingType === 'horizontal-line') setHorizontalLineSettingsOpen(true);
        else if (selectedDrawingType === 'rectangle') setRectangleSettingsOpen(true);
        else if (selectedDrawingType === 'vertical-line') setVerticalLineSettingsOpen(true);
        else if (selectedDrawingType === 'ray') setRaySettingsOpen(true);
        else if (selectedDrawingType === 'text') setTextSettingsOpen(true);
        else setPropertiesModalOpen(true);
    };

    const deleteDrawingInternal = (id: string) => {
        if (v2SandboxRef.current) {
            v2SandboxRef.current.deleteDrawing(id);
        }
        if (id === selectedDrawingId) deselectDrawing();
    };

    // Keep ref synced
    useEffect(() => {
        getVisibleTimeRangeRef.current = getVisibleTimeRange
    }, [getVisibleTimeRange])

    // 4. Force Replay Scroll ONLY on initial start
    const hasScrolledOnReplayStartRef = useRef(false)
    useEffect(() => {
        if (replayMode && data.length > 0 && !hasScrolledOnReplayStartRef.current) {
            setTimeout(() => {
                chart?.timeScale().scrollToRealTime()
            }, 50)
            hasScrolledOnReplayStartRef.current = true
        }
        if (!replayMode) {
            hasScrolledOnReplayStartRef.current = false
        }
    }, [data, replayMode, chart])

    // 4d. Keyboard Navigation
    useKeyboardShortcuts({
        chart, series, data, ticker, onTimeframeChange,
        onGoToDate: () => {
            scrollToEnd()
            toast.info("Go To Date: Coming soon (Use Home/End for now)")
        },
        onResetView: () => chart?.timeScale().fitContent(),
        onDeleteSelection: () => deleteSelectedDrawing(),
        onDeselect: () => deselectDrawing(),
        isReplayMode: replayMode
    })

    // 7. Trading Visuals
    const { positionLineRef, pendingLinesRef, slLineRef, tpLineRef } = useChartTrading({
        series, position, pendingOrders
    })

    // 8. Interaction & Drag Logic
    useChartDrag({
        chartContainerRef, chart, series, data,
        positionLineRef, pendingLinesRef, slLineRef, tpLineRef,
        onModifyOrder, onModifyPosition
    })

    // 11. Click Handler (Selection for Non-Drawing Primitives)
    useEffect(() => {
        if (!chart || !series) return
        const clickHandler = (param: any) => {
            if (!param.point) return;
            if (isSelectingReplayStart && param.time) {
                startReplay({ time: param.time as number })
                setIsSelectingReplayStart(false)
                toast.info(`Replay started from selected time`)
                return
            }

            let hitDrawing: any = null;
            if (primitives?.current) {
                for (const p of primitives.current) {
                    if (p.toolType || p._toolType) continue;
                    if (p.hitTest?.(param.point.x, param.point.y)) { hitDrawing = p; break; }
                }
            }

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;
                onSelectionChange?.({ type: hitDrawing._type || 'indicator', id });
            }
        }
        chart.subscribeClick(clickHandler);
        return () => chart.unsubscribeClick(clickHandler);
    }, [chart, series, isSelectingReplayStart])

    // 11b. Double Click Handler
    useEffect(() => {
        if (!chart) return;
        const dblClickHandler = (param: any) => {
            if (!param.point) return;
            let hit: any = null;
            if (primitives?.current) {
                for (const p of primitives.current) {
                    if (p.toolType || p._toolType) continue; 
                    if (p.hitTest?.(param.point.x, param.point.y)) { hit = p; break; }
                }
            }
            if (hit?._type === 'indicator') {
                setSelectedDrawingOptions(indicatorParams?.[hit.id] || {});
                setSelectedDrawingType(hit.id);
                setPropertiesModalOpen(true);
            }
        };
        // @ts-ignore
        chart.subscribeDblClick?.(dblClickHandler);
        return () => {
            // @ts-ignore
            chart.unsubscribeDblClick?.(dblClickHandler);
        };
    }, [chart, indicatorParams]);

    const handleEditDrawing = (id: string) => {
        let drawing: any = null;

        // 1. Check Primitives
        if (primitives?.current) {
            drawing = primitives.current.find((p: any) => {
                const pId = typeof p.id === 'function' ? p.id() : (p._id || p.id);
                return pId === id;
            });
        }

        // 2. Check V2 Tools
        if (!drawing && v2SandboxRef.current) {
            const tool = v2SandboxRef.current.plugin.getLineTool(id);
            if (tool) drawing = tool;
        }

        // 3. Check Specific Indicators
        if (!drawing) {
            if (id === 'watermark' && primitives?.current) {
                drawing = primitives.current.find((p: any) => p._type === 'anchored-text');
            } else if (id === 'daily-profiler') {
                drawing = sessionRangesRef.current;
            } else if (id === 'hourly-profiler') {
                drawing = hourlyProfilerRef.current;
            } else if (id === 'range-extensions') {
                drawing = rangeExtensionsRef.current;
            } else if (id === 'opening-range') {
                drawing = openingRangeRef.current;
            } else if (id === 'truth-profiler') {
                drawing = truthProfilerRef.current;
            }
        }

        // 4. Open Properties
        if (drawing) {
            const isV2Tool = (drawing.toolType && typeof drawing.toolType === 'string') || (typeof drawing.options === 'function');

            if (isV2Tool) {
                const toolType = drawing.toolType || (drawing instanceof BaseLineTool ? (drawing as any).toolType : 'unknown');
                try {
                    const v2Options = typeof drawing.options === 'function' ? drawing.options() : drawing._options;
                    if (v2Options && toolType) {
                        const typeKey = toolType.toLowerCase();
                        const flatOptions = V2OptionAdapter.toV1FlatOptions(v2Options, typeKey);
                        setSelectedDrawingOptions(flatOptions);
                        setSelectedDrawingType(typeKey);
                        selectedDrawingRef.current = drawing;
                        
                        if (typeKey === 'rectangle') setRectangleSettingsOpen(true);
                        else if (typeKey === 'trend-line') setTrendLineSettingsOpen(true);
                        else if (typeKey === 'horizontal-line') setHorizontalLineSettingsOpen(true);
                        else if (typeKey === 'vertical-line') setVerticalLineSettingsOpen(true);
                        else if (typeKey === 'ray') setRaySettingsOpen(true);
                        else if (typeKey === 'text') setTextSettingsOpen(true);
                        else setPropertiesModalOpen(true);
                    } else {
                        openProperties(drawing);
                    }
                } catch (e) {
                    openProperties(drawing);
                }
            } else {
                openProperties(drawing);
            }
            onSelectionChange?.({ type: 'drawing', id: id });
        } else if (id === 'expected-move') {
            if (onOpenEMSettings) onOpenEMSettings();
        } else {
            if (indicatorParams?.[id]) {
                setSelectedDrawingOptions(indicatorParams[id]);
                setSelectedDrawingType(id);
                setPropertiesModalOpen(true);
            }
        }
    };

    // Expose Functions
    useImperativeHandle(ref, () => ({
        deleteDrawing: (id) => deleteDrawingInternal(id),
        editDrawing: (id) => handleEditDrawing(id),
        scrollByBars: replayMode ? stepForward : scrollByBars,
        scrollToStart: replayMode ? () => setReplayIndex(0) : scrollToStart,
        scrollToEnd: replayMode ? () => setReplayIndex(fullData.length - 1) : scrollToEnd,
        scrollToTime: async (time) => {
            if (replayMode) {
                const idx = findIndexForTime(time)
                setReplayIndex(idx)
                setTimeout(() => chart?.timeScale().scrollToRealTime(), 50)
            } else {
                const result = await jumpToTime(time)
                if (result.needsScroll) {
                    setTimeout(() => scrollToTime(time), 100)
                }
            }
        },
        getDataRange,
        getFullDataRange: () => fullDataRange,
        startReplay: (op) => startReplay(op),
        startReplaySelection,
        stepForward,
        stepBack,
        stopReplay,
        isReplayMode: () => replayMode,
        getReplayIndex: () => replayIndex,
        getTotalBars: () => fullData.length,
        takeScreenshot: () => chart?.takeScreenshot() || null,
        updateLivePrice: (price: number) => {
            if (isDisposed() || !series || !data || data.length === 0) return;
            const lastBar = data[data.length - 1];
            if (!lastBar) return;
            const updatedBar = { ...lastBar, close: price, high: Math.max(lastBar.high, price), low: Math.min(lastBar.low, price) };
            series.update(updatedBar);
        }
    }), [scrollByBars, scrollToStart, scrollToEnd, scrollToTime, getDataRange, replayMode, replayIndex, fullData, chart, fullDataRange, jumpToTime, series, data, isDisposed])


    // -------------------------------------------------------------------------
    // 12. Volume Profile Plugin Integration
    // -------------------------------------------------------------------------

    // Import (Dynamic / Lazy to avoid SSR issues if any, but regular import is fine here)
    // Note: We need to import these at the top level, but for this edit block we assume they are added.
    // I will add the imports via a separate edit or assume the user accepts the diff logic if I put imports here? 
    // Typescript might complain. I'll add imports in a separate block first.


    useEffect(() => {
        if (!series || !chart || !data || data.length === 0) return;

        // Check if enabled (hacky check for now, ideally strictly typed)
        const isVPEnabled = indicators.includes('Volume Profile') || indicators.includes('vp');

        if (isVPEnabled) {
            // Dynamic Import to avoid circular dependencies or server side issues
            import('@/components/chart/plugins/volume-profile-primitive').then(({ VolumeProfilePrimitive }) => {
                import('@/lib/charts/volume-profile-calc').then(({ calculateVolumeProfile }) => {

                    // 1. Calculate Profile (Visible Range or Session?)
                    // For now, let's use the visible data range or last n bars
                    // A true VPVR updates on scroll. A Session VP is static per day.
                    // Let's implement a simple "Visible Range" style initial load

                    const profileData = calculateVolumeProfile(data, null, 50); // 50 rows

                    // 2. Create or Update Primitive
                    if (!vpPrimitiveRef.current) {
                        vpPrimitiveRef.current = new VolumeProfilePrimitive({
                            time: data[data.length - 1].time, // Anchor to latest
                            width: 50, // 50 bars wide
                            profile: profileData
                        });
                        series.attachPrimitive(vpPrimitiveRef.current);
                    } else {
                        vpPrimitiveRef.current.setData({
                            time: data[data.length - 1].time,
                            width: 50,
                            profile: profileData
                        });
                    }
                    vpPrimitiveRef.current.setVisible(true);

                });
            });
        } else {
            if (vpPrimitiveRef.current) {
                vpPrimitiveRef.current.setVisible(false);
                // Optionally detach? vpPrimitiveRef.current.detach();
            }
        }

    }, [series, chart, data, indicators]); // Re-run when data updates or switch indicators

    // 2. Truth Profiler - Logic moved to useTruthProfiler hook
    // -------------------------------------------------------------------------
    // 13. Truth Profiler Data Fetching
    // -------------------------------------------------------------------------
    // Logic moved to useTruthProfiler hook
    // -------------------------------------------------------------------------
    // 14. Truth Profiler Lifecycle
    // -------------------------------------------------------------------------
    // Logic moved to useTruthProfiler hook
    // -------------------------------------------------------------------------
    // Theme Sync for Truth Profiler
    // -------------------------------------------------------------------------
    // Logic moved to useTruthProfiler hook

    useEffect(() => {
        if (!series || !chart || !ticker) return;

        // Check for low timeframe (1-29 minutes)
        // TradingView/Our app uses "1", "5", "15" for minutes. "1D" etc for days.
        const isMinute = /^\d+$/.test(timeframe);
        const minutes = isMinute ? parseInt(timeframe) : (timeframe.endsWith('m') ? parseInt(timeframe) : 9999);
        const isLowTimeframe = minutes < 30;
        const isEnabled = indicators.includes('daily-profiler') && isLowTimeframe;
        //console.log('[ChartContainer] Effect triggered. Timeframe:', timeframe, 'isLow?', isLowTimeframe, 'Indicators:', indicators, 'Enabled?', isEnabled);




        if (isEnabled && theme) {
            //console.log('[ChartContainer] DailyProfiler ENABLED. Importing...');
            import('@/lib/charts/indicators/daily-profiler').then(({ DailyProfiler, getDailyProfilerDefaults }) => {
                const defaults = getDailyProfilerDefaults(theme);
                const dailyParams = { ...defaults, ...(indicatorParams?.['daily-profiler'] || {}) };
                //console.log('[ChartContainer] DailyProfiler Module Loaded. Params:', dailyParams);

                // Recreate if series/chart instance changed (e.g. timeframe change)
                if (sessionRangesRef.current && (sessionRangesRef.current._series !== series || sessionRangesRef.current._chart !== chart)) {
                    //console.log('[ChartContainer] Series changed, recreating DailyProfiler');
                    if (sessionRangesRef.current.destroy) sessionRangesRef.current.destroy();
                    sessionRangesRef.current = null;
                }

                if (!sessionRangesRef.current) {
                    sessionRangesRef.current = new DailyProfiler(chart, series, {
                        ...dailyParams,
                        ticker
                    }, (newOpts) => onIndicatorParamsChange?.('daily-profiler', newOpts)); // Pass callback correctly

                    //console.log('[ChartContainer] DailyProfiler Instantiated. Attaching primitive...');
                    series.attachPrimitive(sessionRangesRef.current);

                    // Initial Data Push
                    if (data && data.length > 0) {
                        sessionRangesRef.current.setData(data);
                    }
                } else {
                    // Update options
                    if (sessionRangesRef.current.applyOptions) {
                        sessionRangesRef.current.applyOptions({
                            ...dailyParams,
                            ticker
                        }, true);
                    }
                }
            });
        } else {
            if (sessionRangesRef.current) {
                if (sessionRangesRef.current.destroy) sessionRangesRef.current.destroy();
                series.detachPrimitive(sessionRangesRef.current);
                sessionRangesRef.current = null;
            }
        }
    }, [series, chart, ticker, indicators, indicatorParams, timeframe, theme]);

    // Data Sync Effect for Daily Profiler
    useEffect(() => {
        if (sessionRangesRef.current && data && data.length > 0) {
            //console.log('[ChartContainer] Syncing data to DailyProfiler', data.length);
            sessionRangesRef.current.setData(data);
        } else if (!data || data.length === 0) {
            //console.log('[ChartContainer] No data to sync to DailyProfiler');
        }
    }, [data]);

    // Theme Sync Effect for Daily Profiler
    useEffect(() => {
        if (sessionRangesRef.current && theme && sessionRangesRef.current.setTheme) {
            //console.log('[ChartContainer] Syncing Theme to DailyProfiler');
            sessionRangesRef.current.setTheme(theme);
        }
    }, [theme]);

    // -------------------------------------------------------------------------
    // 14. Expected Move Levels (New)
    // -------------------------------------------------------------------------

    useEffect(() => {
        if (!series || !chart || !ticker) return;

        // Strict enable via indicators list
        const showEM = indicators.includes('expected-move') || indicators.includes('em');

        if (showEM) {
            const load = async () => {
                try {
                    const { ExpectedMoveLevels } = await import('@/lib/charts/plugins/expected-move-levels');

                    if (!emPluginRef.current) {
                        emPluginRef.current = new ExpectedMoveLevels(chart, series, {
                            ticker,
                            showLabels: true
                        });
                        series.attachPrimitive(emPluginRef.current);
                    }

                    // Fetch EM levels from API
                    // Map ticker if needed, but respect Settings ticker if provided?
                    // Usually we want to load data for the CHART ticker, but if user overrides in settings (Proxy), use that.
                    // Note: emSettings.ticker might be 'SPY' by default, so be careful not to override valid chart ticker 'ES'.
                    // Use chart ticker unless it's not a standard index?
                    // Let's stick to the mapped chart ticker for now to avoid confusion.
                    // Or check if emSettings.ticker matches one of the expected types.

                    let apiTicker = ticker;
                    // Logic to prioritize emSettings ticker if user explicitly set it?
                    // If emSettings?.ticker is set, use it.    // 3. Expected Move - Logic moved to useExpectedMove hook
                    if (emSettings?.ticker) {
                        apiTicker = emSettings.ticker;
                    } else {
                        // Fallback mapping
                        if (ticker.includes('ES') || ticker.includes('/ES')) apiTicker = 'ES';
                        else if (ticker.includes('SPX') || ticker === '$SPX') apiTicker = 'SPX';
                        else if (ticker.includes('SPY')) apiTicker = 'SPY';
                    }

                    // Limit days if setting exists
                    const daysLimit = emSettings?.daysToShow || 30;

                    const resp = await fetch(`/api/em-levels?ticker=${apiTicker}&days=${daysLimit}`);
                    if (!resp.ok) {
                        console.warn('EM Levels API returned error:', resp.status);
                        return;
                    }

                    const result = await resp.json();
                    if (!result.data || result.data.length === 0) {
                        console.warn('No EM data available for ticker:', apiTicker);
                        return;
                    }

                    // Group data by method
                    const methodDataMap = new Map<string, any[]>();
                    for (const row of result.data) {
                        const methodId = row.method;
                        if (!methodDataMap.has(methodId)) {
                            methodDataMap.set(methodId, []);
                        }
                        // Only store unique dates (first multiple entry per date)
                        const existing = methodDataMap.get(methodId)!;
                        if (!existing.find((e: any) => e.date === row.date)) {
                            methodDataMap.get(methodId)!.push({
                                date: row.date,
                                anchor: row.anchor,
                                emValue: row.em_value,
                                anchorType: row.method.includes('open') ? 'open' : 'close'
                            });
                        }
                    }

                    // Load each method's data
                    // Clear existing data first?
                    // The plugin's setMethodData overwrites.

                    for (const [methodId, data] of methodDataMap) {
                        emPluginRef.current.setMethodData(methodId, data);
                    }

                    // Trigger initial update with bar data
                    if (dataRef.current.length > 0) {
                        emPluginRef.current.updateFromBars(dataRef.current);
                    }

                } catch (e) {
                    console.error("Failed to load EM Plugin", e);
                }
            };
            load();
        } else {
            // Cleanup/Detach if it exists but shouldn't be shown
            if (emPluginRef.current) {
                series.detachPrimitive(emPluginRef.current);
                emPluginRef.current = null;
            }
        }
    }, [series, chart, ticker, theme, indicators, emSettings?.daysToShow, emSettings?.ticker]);

    useEffect(() => {
        if (emPluginRef.current && data.length > 0) {
            emPluginRef.current.updateFromBars(data);
        }
    }, [data, timeframe]);

    // Update EM plugin when settings change from the dialog
    useEffect(() => {
        if (emPluginRef.current && emSettings) {
            emPluginRef.current.updateFromSettings({
                methods: emSettings.methods,
                levelMultiples: emSettings.levelMultiples,
                showLabels: emSettings.showLabels,
                showWeeklyClose: emSettings.showWeeklyClose,
                labelFontSize: emSettings.labelFontSize
            });
            // Re-render with current bar data
            if (dataRef.current.length > 0) {
                emPluginRef.current.updateFromBars(dataRef.current);
            }
        }
    }, [emSettings]);

    // -------------------------------------------------------------------------
    // 13.5 Daily Settlement Data for EM Anchoring (ES Futures)
    // -------------------------------------------------------------------------

    // Fetch daily data unconditionally for the current ticker to get accurate settlement closes
    const dailyDataLogic = useDataLoading({
        ticker,
        timeframe: '1D',
        // No callbacks needed, just need the data
    });

    // Pass Daily Settlements to Plugin
    useEffect(() => {
        if (emPluginRef.current && dailyDataLogic.fullData.length > 0) {
            emPluginRef.current.setDailySettlements(dailyDataLogic.fullData);
        }
    }, [dailyDataLogic.fullData]);

    // -------------------------------------------------------------------------
    // 14. Trade Visualizations (Risk/Reward)
    // -------------------------------------------------------------------------

    useEffect(() => {
        if (!series || !chart || !trades || trades.length === 0 || !showTrades) {
            tradeVisualizationsRef.current.forEach(p => series?.detachPrimitive(p));
            tradeVisualizationsRef.current = [];
            return;
        }
        // Legacy RiskReward visualization removed (requires V2 port).
        // TODO: Port Trade Visualization to V2
    }, [series, chart, trades, showTrades]);

    // -------------------------------------------------------------------------
    // 14. Range Extensions Integration
    // -------------------------------------------------------------------------

    useEffect(() => {
        if (!series || !chart || !ticker || data.length === 0) return;

        const isEnabled = indicators.includes('range-extensions');

        if (isEnabled) {
            import('@/lib/charts/indicators/range-extensions').then(({ RangeExtensions }) => {
                const params = indicatorParams?.['range-extensions'] || {};

                // Recreate if series/chart instance changed
                if (rangeExtensionsRef.current && (rangeExtensionsRef.current._series !== series)) {
                    // Detach old?
                    // Lightweight charts doesn't have easy detach for primitives if we lose ref?
                    // Actually we should detach current ref below if exists.
                    if (rangeExtensionsRef.current.destroy) rangeExtensionsRef.current.destroy();
                    rangeExtensionsRef.current = null;
                }

                if (!rangeExtensionsRef.current) {
                    // Calculate time range (last 14 days)
                    const LOAD_DAYS = 14;
                    const SECONDS_PER_DAY = 24 * 60 * 60;
                    const endTs = data.length > 0 ? data[data.length - 1].time as number : undefined;
                    const startTs = endTs ? endTs - (LOAD_DAYS * SECONDS_PER_DAY) : undefined;

                    rangeExtensionsRef.current = new RangeExtensions(chart, series, {
                        ...params,
                        ticker,
                        displayTimezone, // Pass timezone
                        startTs,
                        endTs
                    });
                    series.attachPrimitive(rangeExtensionsRef.current);

                    // Initial Data Push
                    if (data && data.length > 0) {
                        rangeExtensionsRef.current.setData(data);
                    }
                } else {
                    rangeExtensionsRef.current.updateOptions({ ...params, ticker, displayTimezone });
                }
                setRangeExtensionsActive(true);
                // We trust crosshair or explicit update for continuous data

                // Let's add a quick sync after a delay to catch initial load
                setTimeout(() => {
                    if (rangeExtensionsRef.current) setRangeData(rangeExtensionsRef.current.data);
                }, 2000);
            });
        } else {
            setRangeExtensionsActive(false);
            setRangeData([]);
            if (rangeExtensionsRef.current) {
                try {
                    if (rangeExtensionsRef.current.destroy) rangeExtensionsRef.current.destroy();
                    series.detachPrimitive(rangeExtensionsRef.current);
                    if (rangeExtensionsRef.current.detached) rangeExtensionsRef.current.detached();
                } catch (e) { }
                rangeExtensionsRef.current = null;
            }
        }
    }, [series, chart, ticker, indicators, indicatorParams, data.length > 0]);

    // -------------------------------------------------------------------------
    // 15. Hourly Profiler Integration
    // -------------------------------------------------------------------------

    // Instantiation Effect
    useEffect(() => {
        if (!series || !chart || !ticker) {
            return;
        }

        const isEnabled = indicators.includes('hourly-profiler');

        if (isEnabled) {
            import('@/lib/charts/indicators/hourly-profiler').then(({ HourlyProfiler }) => {
                const hourlyParams = indicatorParams?.['hourly-profiler'] || {};

                // Recreate if series/chart instance changed
                if (hourlyProfilerRef.current && (hourlyProfilerRef.current._series !== series)) {
                    if (hourlyProfilerRef.current.destroy) hourlyProfilerRef.current.destroy();
                    hourlyProfilerRef.current = null;
                }

                if (!hourlyProfilerRef.current) {
                    hourlyProfilerRef.current = new HourlyProfiler(chart, series, {
                        ...hourlyParams,
                        ticker,
                    }, theme, (newOpts) => onIndicatorParamsChange?.('hourly-profiler', newOpts));
                    series.attachPrimitive(hourlyProfilerRef.current);

                    // Initial Data Push
                    if (data && data.length > 0) {
                        hourlyProfilerRef.current.setData(data);
                    }
                } else {
                    hourlyProfilerRef.current.applyOptions({ ...hourlyParams, ticker }, true);
                }
            }).catch(err => {
                console.error('[ChartContainer] Failed to load HourlyProfiler module:', err);
            });
        } else {
            if (hourlyProfilerRef.current) {
                try {
                    if (hourlyProfilerRef.current.destroy) {
                        hourlyProfilerRef.current.destroy();
                    }
                    series.detachPrimitive(hourlyProfilerRef.current);
                } catch (e) {
                    console.error('[ChartContainer] Error destroying HourlyProfiler:', e);
                }
                hourlyProfilerRef.current = null;
            }
        }
    }, [series, chart, ticker, indicators, indicatorParams, theme]);


    // Data Sync Effect for Hourly Profiler
    useEffect(() => {
        if (hourlyProfilerRef.current && data && data.length > 0) {
            hourlyProfilerRef.current.setData(data);
        }
    }, [data]);

    // Theme Sync Effect for Hourly Profiler
    useEffect(() => {
        if (hourlyProfilerRef.current && theme && hourlyProfilerRef.current.setTheme) {
            hourlyProfilerRef.current.setTheme(theme);
        }
    }, [theme]);

    // -------------------------------------------------------------------------
    // 16. Opening Range Indicator
    // -------------------------------------------------------------------------

    useEffect(() => {
        if (!series || !chart || !data || data.length === 0) return;

        // Check for 'opening-range' or 'OR'
        const isEnabled = indicators.includes('opening-range') || indicators.includes('OR');

        if (isEnabled) {
            import('@/lib/charts/indicators/opening-range').then(({ OpeningRange }) => {
                // Recreate if series changed
                if (openingRangeRef.current && openingRangeRef.current._series !== series) {
                    series.detachPrimitive(openingRangeRef.current);
                    openingRangeRef.current = null;
                }

                if (!openingRangeRef.current) {
                    openingRangeRef.current = new OpeningRange(chart, series, {
                        lineColor: theme?.chart?.crosshair || '#2962FF',
                        fillColor: theme?.chart?.crosshair || '#2962FF',
                        // Use user params if available
                        ...indicatorParams?.['opening-range']
                    });
                    series.attachPrimitive(openingRangeRef.current);
                } else {
                    openingRangeRef.current.applyOptions({
                        ...indicatorParams?.['opening-range']
                    });
                }

                // Update Data
                openingRangeRef.current.setData(data);

            }).catch(e => {
                console.error('[ChartContainer] Failed to load OpeningRange:', e);
            });
        } else {
            if (openingRangeRef.current) {
                series.detachPrimitive(openingRangeRef.current);
                openingRangeRef.current = null;
            }
        }
    }, [series, chart, data, indicators, indicatorParams, theme]);

    // -------------------------------------------------------------------------
    // 17. Session Highlighting Integration
    // -------------------------------------------------------------------------

    useEffect(() => {
        if (!series || !chart || !data || data.length === 0) return;

        // Check aliases
        const isEnabled = indicators.includes('session-highlighting') || indicators.includes('sessions');

        if (isEnabled) {
            import('@/lib/charts/plugins/session-highlighting').then(({ SessionHighlighting, getSessionHighlightingDefaults }) => {
                // Recreate if series changed
                if (sessionHighlightingRef.current && sessionHighlightingRef.current._series !== series) {
                    series.detachPrimitive(sessionHighlightingRef.current);
                    sessionHighlightingRef.current = null;
                }

                if (!sessionHighlightingRef.current) {
                    // Use theme for defaults
                    sessionHighlightingRef.current = new SessionHighlighting(
                        indicatorParams?.['session-highlighting'],
                        theme
                    );
                    series.attachPrimitive(sessionHighlightingRef.current);
                } else {
                    // Just update theme if needed, but options usually don't change dynamically like this without theme
                }

                // Trigger calculation if data exists
                if (sessionHighlightingRef.current.requestUpdate) {
                    sessionHighlightingRef.current.requestUpdate();
                }

            }).catch(e => {
                console.error('[ChartContainer] Failed to load SessionHighlighting:', e);
            });
        } else {
            if (sessionHighlightingRef.current) {
                series.detachPrimitive(sessionHighlightingRef.current);
                sessionHighlightingRef.current = null;
            }
        }
    }, [series, chart, data, indicators, indicatorParams, theme]);

    // Theme Sync for Session Highlighting
    useEffect(() => {
        if (sessionHighlightingRef.current && theme && sessionHighlightingRef.current.setTheme) {
            sessionHighlightingRef.current.setTheme(theme);
        }
    }, [theme]);

    return (
        <div className="w-full h-full relative" onContextMenu={(e) => {
            // Keep native React onContextMenu as backup
        }}>

            {/* Range Extensions UI */}
            {rangeExtensionsActive && (() => {
                const params = indicatorParams?.['range-extensions'] || {};
                const accountBalance = params.accountBalance ?? 50000;
                const riskPercent = params.riskPercent ?? 1.0;

                const { pointValue, microMultiplier: mm } = getContractSpecs(ticker);
                const tickValue = pointValue; // Use Point Value for Logic
                const microMultiplier = mm;

                return (
                    <>
                        <RangeInfoPanel
                            data={rangeData}
                            accountBalance={accountBalance}
                            riskPercent={riskPercent}
                            tickValue={tickValue} // Now passing Point Value
                            microMultiplier={microMultiplier}
                        />
                        <ChartCursorOverlay
                            chart={chart}
                            rangeExtensionsRef={rangeExtensionsRef as any}
                            indicatorParams={indicatorParams}
                            tickValue={tickValue} // Pass corrected Point Value
                            microMultiplier={microMultiplier} // Pass corrected Multiplier
                        />
                    </>
                );
            })()}

            {/* Chart canvas container - innerHTML gets cleared by useChart */}
            <div ref={chartContainerRef} className="w-full h-full" />

            {/* OHLC Legend - Now using Canvas-based legend (see ohlc-legend.ts)
            <ChartLegend
                ref={legendRef}
                ticker={ticker}
                timeframe={timeframe}
                className="absolute top-2 left-2 z-50 bg-background/80 backdrop-blur-sm px-2 py-1 rounded pointer-events-none"
            />
            */}

            <ChartContextMenu
                containerRef={chartContainerRef}
                selectedDrawing={selectedDrawingRef.current}
                onDelete={deleteSelectedDrawing}
                onSettings={openDrawingSettings}
            />

            {/* Toolbar - appears on drawing selection (Portal to bypass parent CSS constraints) */}
            {typeof document !== 'undefined' && selectedDrawingId && createPortal(
                <div className="fixed inset-0 z-[99999] pointer-events-none">
                    <FloatingToolbar
                        drawingId={selectedDrawingId || ''}
                        drawingType={selectedDrawingType}
                        position={toolbarPosition || { x: 100, y: 100 }}
                        options={selectedDrawingOptions || {}}
                        isLocked={isDrawingLocked}
                        isHidden={isDrawingHidden}
                        isPinned={false}
                        onSettings={openDrawingSettings}
                        onClone={cloneSelectedDrawing}
                        onLock={toggleDrawingLock}
                        onDelete={deleteSelectedDrawing}
                        onToggleVisibility={toggleDrawingVisibility}
                        onZOrderChange={(action) => {
                            if (v2SandboxRef.current) {
                                const plugin = v2SandboxRef.current.plugin;
                                switch (action) {
                                    case 'bringToFront': plugin.bringToFront(selectedDrawingId!); break;
                                    case 'sendToBack': plugin.sendToBack(selectedDrawingId!); break;
                                    case 'bringForward': plugin.bringForward(selectedDrawingId!); break;
                                    case 'sendBackward': plugin.sendBackward(selectedDrawingId!); break;
                                }
                            }
                        }}
                        onPositionChange={(pos) => setToolbarPosition(pos)}
                        onOptionsChange={(updates) => {
                            // Use the centralized handler to ensure V2 conversion, application to real tool, and storage persistence
                            handlePropertiesSave(updates);
                        }}
                    />
                </div>,
                document.body
            )}

            {propertiesModalOpen && (
                <PropertiesModal
                    open={propertiesModalOpen}
                    onOpenChange={setPropertiesModalOpen}
                    drawingType={selectedDrawingType as any}
                    initialOptions={selectedDrawingOptions}
                    points={selectedDrawingPoints}
                    onSave={handlePropertiesSave}
                    ticker={ticker}
                />
            )}

            {/* Inline Text Editor Overlay */}
            {inlineTextEditing && (
                <InlineTextEditor
                    position={(inlineTextEditing as any).position}
                    layout={(inlineTextEditing as any).layout}
                    initialText={(inlineTextEditing as any).text}
                    onSave={handleInlineSave}
                    onCancel={handleInlineCancel}
                    fontSize={(inlineTextEditing as any).options.text?.font?.size || 14}
                    fontFamily={(inlineTextEditing as any).options.text?.font?.family || 'Arial'}
                    color={(inlineTextEditing as any).options.text?.color || '#FFFFFF'}
                    backgroundColor={(inlineTextEditing as any).options.text?.box?.background?.color}
                    bounded={(inlineTextEditing as any).drawingType === 'rectangle'}
                />
            )}

            {/* Text Settings Dialog */}
            {textSettingsOpen && (
                <TextSettings
                    open={textSettingsOpen}
                    onOpenChange={setTextSettingsOpen}
                    options={{
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor || selectedDrawingOptions?.color,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        visibleTimeframes: selectedDrawingOptions?.visibleTimeframes,
                        backgroundColor: selectedDrawingOptions?.backgroundColor,
                        backgroundVisible: selectedDrawingOptions?.backgroundVisible,
                        borderColor: selectedDrawingOptions?.borderColor,
                        borderVisible: selectedDrawingOptions?.borderVisible,
                        wordWrap: selectedDrawingOptions?.wordWrap,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                    }}
                    onSave={(opts) => {
                        handlePropertiesSave(opts);
                        setTextSettingsOpen(false);
                    }}
                    onCancel={() => setTextSettingsOpen(false)}
                />
            )}

            {/* Rectangle Settings Dialog */}
            {rectangleSettingsOpen && (
                <RectangleSettingsDialog
                    open={rectangleSettingsOpen}
                    onOpenChange={setRectangleSettingsOpen}
                    options={{
                        ...DEFAULT_RECTANGLE_OPTIONS,
                        borderColor: selectedDrawingOptions?.borderColor || '#2962FF',
                        borderWidth: selectedDrawingOptions?.borderWidth || 1,
                        borderStyle: selectedDrawingOptions?.borderStyle || 0,
                        fillColor: selectedDrawingOptions?.fillColor || '#2962FF',
                        fillOpacity: selectedDrawingOptions?.fillOpacity ?? 0.1,
                        showMidline: selectedDrawingOptions?.showMidline || false,
                        showQuarterLines: selectedDrawingOptions?.showQuarterLines || false,
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                        visibleTimeframes: selectedDrawingOptions?.visibleTimeframes
                    }}
                    points={(() => {
                        const drawing = selectedDrawingRef.current;
                        if (!drawing) return undefined;
                        if (drawing._p1 && drawing._p2) return { p1: drawing._p1, p2: drawing._p2 };
                        if (drawing.points && typeof drawing.points === 'function') {
                            const pts = drawing.points();
                            return (pts && pts.length >= 2) ? { p1: pts[0], p2: pts[1] } : undefined;
                        }
                        if (drawing.points && drawing.points.length >= 2) {
                            return { p1: drawing.points[0], p2: drawing.points[1] };
                        }
                        return undefined;
                    })()}
                    onApply={(opts, pts) => {
                        handlePropertiesSave(opts, pts);
                        setRectangleSettingsOpen(false);
                    }}
                    onCancel={() => setRectangleSettingsOpen(false)}
                />
            )}

            {/* New TrendLine Settings Dialog */}
            {trendLineSettingsOpen && (
                <TrendLineSettingsDialog
                    open={trendLineSettingsOpen}
                    onOpenChange={setTrendLineSettingsOpen}
                    options={{
                        ...DEFAULT_TRENDLINE_OPTIONS,
                        color: selectedDrawingOptions?.lineColor || '#2962FF',
                        width: selectedDrawingOptions?.lineWidth || 2,
                        style: selectedDrawingOptions?.lineStyle || 0,
                        opacity: selectedDrawingOptions?.opacity || 1,
                        extendLeft: selectedDrawingOptions?.extendLeft || false,
                        extendRight: selectedDrawingOptions?.extendRight || false,
                        showAngle: selectedDrawingOptions?.showAngle || false,
                        showDistance: selectedDrawingOptions?.showDistance || false,
                        showPriceRange: selectedDrawingOptions?.showPriceRange || false,
                        showBarsRange: selectedDrawingOptions?.showBarsRange || false,
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        alignment: selectedDrawingOptions?.alignment,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                    }}
                    points={(() => {
                        const drawing = selectedDrawingRef.current;
                        if (!drawing) return undefined;
                        if (drawing._p1 && drawing._p2) return { p1: drawing._p1, p2: drawing._p2 };
                        if (drawing.points && drawing.points.length >= 2) {
                            return { p1: drawing.points[0], p2: drawing.points[1] };
                        }
                        return undefined;
                    })()}
                    onApply={(opts, pts) => handlePropertiesSave(opts, pts)}
                    onCancel={() => setTrendLineSettingsOpen(false)}
                />
            )}

            {/* Horizontal Line Settings Dialog */}
            {horizontalLineSettingsOpen && (
                <HorizontalLineSettingsDialog
                    open={horizontalLineSettingsOpen}
                    onOpenChange={setHorizontalLineSettingsOpen}
                    options={{
                        ...DEFAULT_HORIZONTAL_OPTIONS,
                        color: selectedDrawingOptions?.color || '#2962FF',
                        width: selectedDrawingOptions?.width || 1,
                        style: selectedDrawingOptions?.lineStyle || 1,
                        showLabel: selectedDrawingOptions?.showLabel ?? true,
                        labelBackgroundColor: selectedDrawingOptions?.labelBackgroundColor || '#2962FF',
                        labelTextColor: selectedDrawingOptions?.labelTextColor || '#FFFFFF',
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                    }}
                    price={(() => {
                        const drawing = selectedDrawingRef.current;
                        if (!drawing) return 0;
                        if (drawing._price !== undefined) return drawing._price;
                        if (drawing.points && drawing.points.length >= 1) {
                            return drawing.points[0].price;
                        }
                        return 0;
                    })()}
                    onApply={(opts, price) => handlePropertiesSave(opts, price)}
                    onCancel={() => setHorizontalLineSettingsOpen(false)}
                />
            )}


            {/* Vertical Line Settings Dialog */}
            {verticalLineSettingsOpen && (
                <VerticalLineSettingsDialog
                    open={verticalLineSettingsOpen}
                    onOpenChange={setVerticalLineSettingsOpen}
                    options={{
                        ...DEFAULT_VERTICAL_OPTIONS,
                        color: selectedDrawingOptions?.color || '#2962FF',
                        width: selectedDrawingOptions?.width || 2,
                        style: selectedDrawingOptions?.lineStyle || 0,
                        showLabel: selectedDrawingOptions?.showLabel ?? true,
                        labelBackgroundColor: selectedDrawingOptions?.labelBackgroundColor || '#2962FF',
                        labelTextColor: selectedDrawingOptions?.labelTextColor || '#FFFFFF',
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                        orientation: selectedDrawingOptions?.orientation || 'horizontal',
                    }}
                    time={(() => {
                        const drawing = selectedDrawingRef.current;
                        if (!drawing) return 0;
                        if (drawing._time !== undefined) return drawing._time;
                        if (drawing.points && drawing.points.length >= 1) {
                            return drawing.points[0].timestamp || drawing.points[0].time;
                        }
                        return 0;
                    })()}
                    onApply={(opts, time) => handlePropertiesSave(opts, time)}
                    onCancel={() => setVerticalLineSettingsOpen(false)}
                />
            )}

            {/* Ray Settings Dialog */}
            {raySettingsOpen && (
                <RaySettingsDialog
                    open={raySettingsOpen}
                    onOpenChange={setRaySettingsOpen}
                    options={{
                        color: selectedDrawingOptions?.lineColor || selectedDrawingOptions?.color || DEFAULT_RAY_OPTIONS.color,
                        width: selectedDrawingOptions?.lineWidth || selectedDrawingOptions?.width || DEFAULT_RAY_OPTIONS.width,
                        style: selectedDrawingOptions?.lineStyle ?? selectedDrawingOptions?.style ?? DEFAULT_RAY_OPTIONS.style,
                        opacity: selectedDrawingOptions?.opacity ?? DEFAULT_RAY_OPTIONS.opacity,
                        text: selectedDrawingOptions?.text,
                        textColor: selectedDrawingOptions?.textColor,
                        fontSize: selectedDrawingOptions?.fontSize,
                        bold: selectedDrawingOptions?.bold,
                        italic: selectedDrawingOptions?.italic,
                        alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                        alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                    }}
                    points={(() => {
                        const drawing = selectedDrawingRef.current;
                        if (!drawing) return undefined;
                        if (drawing._p1 && drawing._p2) return { p1: drawing._p1, p2: drawing._p2 };
                        if (drawing.points && drawing.points.length >= 2) {
                            return { p1: drawing.points[0], p2: drawing.points[1] };
                        }
                        return undefined;
                    })()}
                    onApply={(opts, pts) => handlePropertiesSave(opts, pts)}
                    onCancel={() => setRaySettingsOpen(false)}
                />
            )}
        </div>
    )
}))

ChartContainer.displayName = "ChartContainer"
