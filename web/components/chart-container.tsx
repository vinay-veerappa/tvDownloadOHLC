"use client"

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
import type { EMSettings } from './em-settings-dialog'
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
// import { isInlineEditable } from "@/lib/charts/plugins/base/inline-editable"
import { fetchProfilerStats, fetchLevelTouches, ProfilerSession, LevelTouchesResponse } from "@/lib/api/profiler"
import { useChartPreferences } from "@/hooks/use-chart-preferences"
import { V2SandboxManager } from "@/lib/charts/v2/sandbox-manager"

import type { SessionType } from './top-toolbar'

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
}




export const ChartContainer = memo(forwardRef<ChartContainerRef, ChartContainerProps>(({
    ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, onDrawingDeleted,
    indicators, markers, magnetMode = 'off', displayTimezone = 'America/New_York', sessionType = 'ETH',
    selection, onSelectionChange, onDeleteSelection, onReplayStateChange, onDataLoad,
    onPriceChange, position, pendingOrders, onModifyOrder, onModifyPosition, initialReplayTime,
    vwapSettings, emSettings, indicatorParams, onIndicatorParamsChange, theme, onTimeframeChange, trades, mode, // Destructure mode
    onOpenEMSettings
}, ref) => {

    // 0. Global Chart Settings
    const { settings: chartSettings } = useChartSettings()
    const { showTrades } = chartSettings
    const { experimentalDrawingV2 } = useChartPreferences()
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const v2SandboxRef = useRef<V2SandboxManager<any> | null>(null)

    // Bridge for lazy access to chart methods
    const getVisibleTimeRangeRef = useRef<(() => { start: number, end: number, center: number } | null) | null>(null)

    // Range UI State
    const [rangeExtensionsActive, setRangeExtensionsActive] = useState(false);
    const [rangeData, setRangeData] = useState<RangeExtensionPeriod[]>([]);

    // 2. Truth Profiler State
    const [truthSessions, setTruthSessions] = useState<ProfilerSession[]>([]);
    const [truthLevels, setTruthLevels] = useState<LevelTouchesResponse>({});
    const truthProfilerRef = useRef<any>(null);


    // 2. Data & Replay Logic (Hook)
    const {
        fullData, data, replayMode, replayIndex, isSelectingReplayStart,
        setIsSelectingReplayStart, startReplay, startReplaySelection, stopReplay,
        stepForward, stepBack, findIndexForTime, setReplayIndex,
        loadMoreData, hasMoreData, isLoadingMore, fullDataRange, jumpToTime
    } = useChartData({
        ticker, timeframe, onDataLoad, onReplayStateChange, onPriceChange,
        getVisibleTimeRange: () => getVisibleTimeRangeRef.current?.() ?? null,
        initialReplayTime,
        mode, // Pass mode
        sessionType // Pass sessionType
    })



    // 3. Core Chart Initialization (Hook)
    const {
        chart, series, primitives, scrollByBars, scrollToStart, scrollToEnd,
        scrollToTime, getDataRange, getVisibleTimeRange, indicators: activeIndicatorsRef
    } = useChart(
        chartContainerRef as React.RefObject<HTMLDivElement>,
        style, indicators, data, markers, displayTimezone, timeframe, vwapSettings, ticker
    )

    // Apply Theme Changes
    useEffect(() => {
        if (!chart || !series || !theme) return

        // Chart Layout
        chart.applyOptions({
            layout: {
                background: { type: ColorType.Solid, color: theme.chart.background },
                textColor: theme.ui.text,
            },
            grid: {
                vertLines: { visible: false, color: theme.chart.grid, style: 0 },
                horzLines: { visible: false, color: theme.chart.grid, style: 0 },
            },
            crosshair: {
                vertLine: { color: theme.chart.crosshair, labelBackgroundColor: theme.chart.background },
                horzLine: { color: theme.chart.crosshair, labelBackgroundColor: theme.chart.background },
            },
        })

        // Candle Colors
        series.applyOptions({
            upColor: theme.candle.upBody,
            downColor: theme.candle.downBody,
            borderUpColor: theme.candle.upBorder,
            borderDownColor: theme.candle.downBorder,
            wickUpColor: theme.candle.upWick,
            wickDownColor: theme.candle.downWick,
        })
    }, [chart, series, theme])

    // Keep ref synced
    useEffect(() => {
        getVisibleTimeRangeRef.current = getVisibleTimeRange
    }, [getVisibleTimeRange])

    // 4. Force Replay Scroll ONLY on initial start (not on every step)
    // This allows normal chart dragging during replay
    const hasScrolledOnReplayStartRef = useRef(false)
    useEffect(() => {
        if (replayMode && data.length > 0 && !hasScrolledOnReplayStartRef.current) {
            // Only scroll once when replay starts
            setTimeout(() => {
                chart?.timeScale().scrollToRealTime()
            }, 50)
            hasScrolledOnReplayStartRef.current = true
        }
        // Reset when replay ends
        if (!replayMode) {
            hasScrolledOnReplayStartRef.current = false
        }
    }, [data, replayMode, chart])

    // 4b. OHLC Legend - use ref to avoid re-render loops
    const legendRef = useRef<ChartLegendRef>(null)
    const canvasLegendRef = useRef<OHLCLegend | null>(null)
    const dataRef = useRef(data)
    const seriesRef = useRef(series)
    const isSubscribedRef = useRef(false)

    // Keep refs in sync
    dataRef.current = data
    seriesRef.current = series

    // Subscribe to crosshair moves ONCE when chart is ready
    useEffect(() => {
        if (!chart || !series || isSubscribedRef.current) return

        // Create canvas legend and attach to series
        if (!canvasLegendRef.current) {
            const formatPrice = (price: number) => {
                // Use ticker-appropriate decimal places
                const isFutures = ticker.includes('!')
                const decimals = isFutures ? 2 : 2
                return price.toFixed(decimals)
            }

            canvasLegendRef.current = new OHLCLegend(chart, series, {
                ticker: ticker.replace('!', ''),
                timeframe: timeframe,
                upColor: theme?.candle.upBody || '#26a69a',
                downColor: theme?.candle.downBody || '#ef5350',
                textColor: theme?.ui.text || '#d1d4dc'
            }, formatPrice)

            series.attachPrimitive(canvasLegendRef.current)
        }

        const handleCrosshairMove = (param: any) => {
            const currentData = dataRef.current
            const currentSeries = seriesRef.current
            if (!currentData || currentData.length === 0 || !currentSeries) return

            let ohlcData = null

            if (!param || !param.time) {
                // Mouse left chart - show latest candle
                const lastBar = currentData[currentData.length - 1]
                if (lastBar) {
                    ohlcData = { open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close }
                }
            } else {
                // Get the candle data at crosshair position
                const candleData = param.seriesData.get(currentSeries)
                if (candleData) {
                    ohlcData = {
                        open: candleData.open,
                        high: candleData.high,
                        low: candleData.low,
                        close: candleData.close
                    }
                }
            }

            if (ohlcData) {
                // Update canvas legend
                canvasLegendRef.current?.updateOHLC(ohlcData)
                // Update HTML legend (will be removed later)
                legendRef.current?.updateOHLC(ohlcData)
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        isSubscribedRef.current = true

        // Set initial value after a small delay
        const timer = setTimeout(() => {
            const currentData = dataRef.current
            if (currentData && currentData.length > 0) {
                const lastBar = currentData[currentData.length - 1]
                const ohlcData = { open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close }
                canvasLegendRef.current?.updateOHLC(ohlcData)
                legendRef.current?.updateOHLC(ohlcData)
            }
        }, 100)

        return () => {
            clearTimeout(timer)
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
            isSubscribedRef.current = false
            // Don't detach canvas legend here - it persists with the series
        }
    }, [chart, series, ticker, timeframe, theme])

    // 4c. Load more data when scrolling near the left edge (oldest data)
    // Uses official Lightweight Charts pattern: barsInLogicalRange().barsBefore
    const lastLoadTimeRef = useRef<number>(0)
    const LOAD_DEBOUNCE_MS = 500 // Debounce loading

    useEffect(() => {
        if (!chart || !series || replayMode || data.length === 0) return

        const handleVisibleRangeChange = (logicalRange: { from: number; to: number } | null) => {
            if (!logicalRange) return

            // Debounce
            const now = Date.now()
            if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) return

            // Use barsInLogicalRange to check how many bars are to the left of visible area
            const barsInfo = series.barsInLogicalRange(logicalRange)
            // console.log('[ChartContainer] Visible Range changed:', logicalRange, 'BarsInfo:', barsInfo, 'HasMore:', hasMoreData)

            // If less than 50 bars to the left and we have more data to load
            if (barsInfo && barsInfo.barsBefore !== null && barsInfo.barsBefore < 50) {
                if (hasMoreData && !isLoadingMore) {
                    //console.log('[LOAD] Triggering loadMoreData, barsBefore:', barsInfo.barsBefore)
                    lastLoadTimeRef.current = now
                    loadMoreData()
                }
            }
        }

        chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        return () => {
            chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        }
    }, [chart, series, replayMode, data.length, hasMoreData, isLoadingMore, loadMoreData])

    // 4d. Keyboard Navigation (Centralized Hook)
    // Legacy listeners removed in favor of useKeyboardShortcuts
    useKeyboardShortcuts({
        chart,
        series,
        data,
        ticker,
        onTimeframeChange,
        onGoToDate: () => {
            // Future: Open Go To Date Modal
            // For now, jump to end
            scrollToEnd()
            toast.info("Go To Date: Coming soon (Use Home/End for now)")
        },
        onResetView: () => chart?.timeScale().fitContent(),
        onDeleteSelection: () => deleteSelectedDrawing(),
        onDeselect: () => deselectDrawing(),
        isReplayMode: replayMode
    })


    // 6. Selection State Management
    const selectedDrawingRef = useRef<any>(null)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)
    const [propertiesModalOpen, setPropertiesModalOpen] = useState(false)
    const [trendLineSettingsOpen, setTrendLineSettingsOpen] = useState(false) // New TrendLine dialog
    const [horizontalLineSettingsOpen, setHorizontalLineSettingsOpen] = useState(false) // New Horizontal dialog
    const [rectangleSettingsOpen, setRectangleSettingsOpen] = useState(false) // New Rectangle dialog
    const [verticalLineSettingsOpen, setVerticalLineSettingsOpen] = useState(false) // New Vertical dialog
    const [raySettingsOpen, setRaySettingsOpen] = useState(false) // New Ray dialog
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const [toolbarPosition, setToolbarPosition] = useState<{ x: number; y: number } | null>(null)
    const [isDrawingLocked, setIsDrawingLocked] = useState(false)
    const [isDrawingHidden, setIsDrawingHidden] = useState(false)
    const [textSettingsOpen, setTextSettingsOpen] = useState(false)  // Text settings dialog
    const [inlineTextEditing, setInlineTextEditing] = useState<{
        drawingId: string;
        position: { x: number; y: number };
        layout?: any;
        text: string;
        options: any;
        drawingType?: string; // For bounded mode (rectangle vs text)
    } | null>(null)
    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)


    // Known drawing types (for selection sync)
    const DRAWING_TYPES = ['trend-line', 'ray', 'fibonacci', 'rectangle', 'vertical-line', 'horizontal-line', 'text', 'risk-reward', 'measure', 'price-label', 'price-range', 'date-range', 'drawing'];

    // Sync external selection  
    useEffect(() => {
        if (!selection) {
            deselectDrawing();
            return;
        }
        // Check if it's a drawing type
        const isDrawingType = DRAWING_TYPES.includes(selection.type);
        if (isDrawingType) {
            // V1 Drawing sync removed.
            // TODO: Add V2 Selection Sync
        } else {
            // For indicators or other types, just deselect any drawing
            deselectDrawing();
        }
    }, [selection]);

    const deselectDrawing = () => {
        if (selectedDrawingRef.current?.setSelected) selectedDrawingRef.current.setSelected(false);
        selectedDrawingRef.current = null;
        setSelectedDrawingId(null);
        setSelectedDrawingOptions({});
    };

    // 7. Trading Visuals (Hook)
    const { positionLineRef, pendingLinesRef, slLineRef, tpLineRef } = useChartTrading({
        series, position, pendingOrders
    })

    // 8. Interaction & Drag Logic (Hook)
    // 8. Interaction & Drag Logic (Hook)
    // We need to know if trading drag is active to disable drawing drag
    const isTradingDragActive = useRef(false); // We need to expose this from useChartDrag? 
    // Actually useChartDrag doesn't expose it. We might need to refactor useChartDrag to accept a ref or return state.
    // For now, let's assume they don't overlap much or we update useChartDrag to update a ref.

    // Let's modify useChartDrag to return isDragging? 
    // Or simpler: useChartDrag accepts a ref to update?
    // Let's rely on cursor state or z-order? 
    // Ideally, pass a shared ref.

    // TODO: Ideally refactor useChartDrag to expose isDragging. 
    // For now, let's just initialize DrawingInteraction. 
    // If we want perfection, we pass "isDraggingRef" to useChartDrag.

    useChartDrag({
        chartContainerRef, chart, series, data,
        positionLineRef, pendingLinesRef, slLineRef, tpLineRef,
        onModifyOrder, onModifyPosition
    })

    // Legacy handleDrawingModified removed



    // 9. Tool Initiation
    // 9. Tool Initiation
    useEffect(() => {
        // Legacy V1 initiation removed.
        // V2 handles tools via V2SandboxManager.
    }, [selectedTool, magnetMode, data, onToolSelect, onSelectionChange]);

    // 9.2 V2 Sandbox Tool Initiation
    useEffect(() => {
        if (!experimentalDrawingV2 || !chart || !series) {
            if (v2SandboxRef.current) {
                v2SandboxRef.current.destroy();
                v2SandboxRef.current = null;
            }
            return;
        }

        if (!v2SandboxRef.current) {
            console.log('Initializing V2 Drawing Sandbox...');

            // Define Callbacks for Persistence & State Sync
            // Define Callbacks for Persistence & State Sync
            const handleDrawingCreated = (exportData: any) => {
                // The tool argument is ALREADY the export data from core-plugin

                const drawing: SerializedDrawing = {
                    id: exportData.id,
                    type: exportData.toolType,
                    points: exportData.points,
                    options: exportData.options,
                    createdAt: Date.now()
                };

                // console.log('[ChartContainer] V2 Drawing Created:', drawing);

                // 1. Persist to Storage
                DrawingStorage.addDrawing(ticker, timeframe, drawing);

                // 2. Notify Parent (for Object Tree)
                // We adapter for legacy interface (RightSidebar) to ensure it appears in the tree
                if (onDrawingCreated) {
                    onDrawingCreated({
                        // Pass full V2 object first
                        ...drawing,
                        // Adapter for Legacy Drawing Interface
                        p1: drawing.points?.[0] || { time: 0, price: 0 },
                        p2: drawing.points?.[1] || { time: 0, price: 0 },
                        text: drawing.options.text?.value || '',
                        type: drawing.type as any
                    } as any);
                }
            };

            const handleDrawingModified = (exportData: any) => {
                // Update Storage
                DrawingStorage.updateDrawing(ticker, timeframe, exportData.id, {
                    points: exportData.points,
                    options: exportData.options
                });
            };

            const handleDrawingDeleted = (id: string) => {
                DrawingStorage.deleteDrawing(ticker, timeframe, id);
                onDrawingDeleted?.(id);
            };

            // NEW: Handle Selection Change Event from V2 Core
            const handleSelectionChanged = (id: string | null, tool: any | null) => {
                if (id && tool) {
                    // Update Internal State
                    setSelectedDrawingId(id);
                    selectedDrawingRef.current = tool; // Now points to V2 Tool Instance (proxied by exports usually, but here tool is the actual instance or export?)
                    // Actually V2SandboxManager passes the tool instance wrapper or export? 
                    // In sandbox-manager we pass: callbacks.onSelectionChanged?.(tool.id, tool);
                    // The 'tool' in sandbox manager is the internal tool object (with .options(), id(), etc)
                    // So we can call methods on it.

                    if (tool.options) {
                        try {
                            setSelectedDrawingOptions(tool.options());
                        } catch (e) {
                            setSelectedDrawingOptions({});
                        }
                    }
                    const toolType = typeof tool.toolType === 'function' ? tool.toolType() : (tool.toolType || 'drawing');
                    setSelectedDrawingType(toolType);

                    // Notify Parent
                    onSelectionChange?.({ type: toolType, id });
                } else {
                    // Deselect
                    setSelectedDrawingId(null);
                    selectedDrawingRef.current = null;
                    setSelectedDrawingOptions(null);
                    onSelectionChange?.(null);
                }
            };


            v2SandboxRef.current = new V2SandboxManager(chart, series, {
                onDrawingCreated: handleDrawingCreated,
                onDrawingModified: handleDrawingModified,
                onDrawingDeleted: handleDrawingDeleted,
                onSelectionChanged: handleSelectionChanged
            });

            // Load Saved Drawings
            const savedDrawings = DrawingStorage.getDrawings(ticker, timeframe);
            if (savedDrawings && savedDrawings.length > 0) {
                // Adapter: Ensure 'points' array exists
                const adaptedDrawings = savedDrawings.map(d => ({
                    toolType: d.type,
                    id: d.id,
                    options: d.options,
                    points: d.points || (d.p1 && d.p2 ? [d.p1, d.p2] : [])
                }));
                console.log(`[ChartContainer] Loading ${adaptedDrawings.length} saved V2 drawings...`);
                v2SandboxRef.current.loadTools(adaptedDrawings);

                // MANUALLY SYNC TO OBJECT TREE ON LOAD
                // Since this component relies on 'onDrawingCreated' to populate the parent's list,
                // we must fire it for each loaded drawing so the parent (Object Tree) knows about them.
                // NOTE: This might duplicate items if parent persists state separately, 
                // but usually parent state is ephemeral on reload or re-fetched.
                // Ideally Parent should handle persistence loading, but if we handle it here, we must sync up.
                savedDrawings.forEach(d => {
                    if (onDrawingCreated) {
                        onDrawingCreated({
                            ...d,
                            p1: d.points?.[0] || d.p1 || { time: 0, price: 0 },
                            p2: d.points?.[1] || d.p2 || { time: 0, price: 0 },
                            text: d.options?.text?.value || '',
                            type: d.type as any
                        } as any);
                    }
                });
            }
        }

        const sandbox = v2SandboxRef.current;

        // Map tool selection
        if (selectedTool === 'trend-line') {
            sandbox.addTool('TrendLine');
        } else if (selectedTool === 'rectangle') {
            sandbox.addTool('Rectangle');
        } else if (selectedTool === 'horizontal-line') {
            sandbox.addTool('HorizontalLine');
        } else if (selectedTool === 'ray') {
            sandbox.addTool('Ray');
        } else if (selectedTool === 'vertical-line') {
            sandbox.addTool('VerticalLine');
        } else if (selectedTool === 'text') {
            sandbox.addTool('Text');
        } else if (selectedTool === 'price-label') {
            sandbox.addTool('PriceLabel');
        } else if (selectedTool === 'price-range') {
            sandbox.addTool('PriceRange');
        } else if (selectedTool === 'date-range') {
            sandbox.addTool('DateRange');
        } else if (selectedTool === 'measure') {
            sandbox.addTool('Measure');
        } else if (selectedTool === 'arrow') {
            sandbox.addTool('Arrow');
        } else if (selectedTool === 'extended-line') {
            sandbox.addTool('ExtendedLine');
        } else if (selectedTool === 'horizontal-ray') {
            sandbox.addTool('HorizontalRay');
        } else if (selectedTool === 'cross-line') {
            sandbox.addTool('CrossLine');
        } else if (selectedTool === 'circle') {
            sandbox.addTool('Circle');
        } else if (selectedTool === 'triangle') {
            sandbox.addTool('Triangle');
        } else if (selectedTool === 'parallel-channel') {
            sandbox.addTool('ParallelChannel');
        } else if (selectedTool === 'brush') {
            sandbox.addTool('Brush');
        } else if (selectedTool === 'path') {
            sandbox.addTool('Path');
        } else if (selectedTool === 'highlighter') {
            sandbox.addTool('Highlighter');
        } else if (selectedTool === 'callout') {
            sandbox.addTool('Callout');
        } else if (selectedTool === 'fibonacci') {
            sandbox.addTool('FibRetracement');
        } else if (selectedTool === 'risk-reward') {
            sandbox.addTool('LongShortPosition');
        } else if (selectedTool === 'cursor') {
            // Deselect in V2?
        }
    }, [experimentalDrawingV2, chart, series, selectedTool, ticker, timeframe, onDrawingCreated, onDrawingDeleted]);


    // 10. Load Drawings
    const hasLoadedDrawingsRef = useRef(false);
    useEffect(() => { hasLoadedDrawingsRef.current = false; }, [ticker, timeframe]);
    useEffect(() => {
        if (data && data.length > 0 && !hasLoadedDrawingsRef.current) {
            // drawingManager.loadDrawings(data); // Removed V1 loading
            // TODO: V2 Load Drawings
            hasLoadedDrawingsRef.current = true;
        }
    }, [ticker, timeframe, data]);


    // 11. Click Handler (Selection)
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
            // V1 hitTest removed
            if (primitives?.current) {
                for (const p of primitives.current) {
                    if (p.hitTest?.(param.point.x, param.point.y)) { hitDrawing = p; break; }
                }
            }

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;
                onSelectionChange?.({ type: hitDrawing._type || 'drawing', id });
                // Set toolbar position near click point
                setToolbarPosition({ x: param.point.x, y: param.point.y });
                setIsDrawingLocked(hitDrawing._locked || false);
                setIsDrawingHidden(hitDrawing._visible === false);
                // Sync options!
                setSelectedDrawingOptions(hitDrawing.options ? hitDrawing.options() : {});
                setSelectedDrawingType(hitDrawing._type || 'drawing');

                // Inline Text Edit: V1 removed. V2 handles text editing differently.

            } else {
                deselectDrawing();
                setToolbarPosition(null);
                setInlineTextEditing(null);
            }
        }

        const dblClickHandler = (param: any) => {
            if (!param.point) return;

            let hitDrawing: any = null;
            // V1 hitTest removed
            if (false) { } // dummy
            else {
                // Check generic primitives
                // Check generic primitives
                if (primitives?.current) {
                    for (const p of primitives.current) {
                        if (p.hitTest?.(param.point.x, param.point.y)) { hitDrawing = p; break; }
                    }
                }

                // Check specific indicators if no hit yet
                // FIX: Check OpeningRange (top-most) FIRST to prevent background profilers from stealing the click
                if (!hitDrawing && openingRangeRef.current?.hitTest?.(param.point.x, param.point.y)) {
                    hitDrawing = openingRangeRef.current;
                }
                if (!hitDrawing && rangeExtensionsRef.current?.hitTest?.(param.point.x, param.point.y)) {
                    hitDrawing = rangeExtensionsRef.current;
                }
                if (!hitDrawing && sessionRangesRef.current?.hitTest?.(param.point.x, param.point.y)) {
                    hitDrawing = sessionRangesRef.current;
                }
                if (!hitDrawing && hourlyProfilerRef.current?.hitTest?.(param.point.x, param.point.y)) {
                    hitDrawing = hourlyProfilerRef.current;
                }
                if (!hitDrawing && truthProfilerRef.current?.hitTest?.(param.point.x, param.point.y)) {
                    hitDrawing = truthProfilerRef.current;
                }

                // Check Standard Indicators (LineSeries, etc.)
                if (!hitDrawing && activeIndicatorsRef?.current) {
                    const timeScale = chart.timeScale();
                    const time = timeScale.coordinateToTime(param.point.x);

                    for (const ind of activeIndicatorsRef.current) {
                        // ind = { series: ISeriesApi, id: string }
                        // We need to get the data at this time
                        // Lightweight charts doesn't make this super easy without internal access
                        // But param.seriesData map might have it if we knew the series object

                        // param.seriesData is a Map<ISeriesApi, Data>
                        if (param.seriesData && param.seriesData.has(ind.series)) {
                            const dataItem = param.seriesData.get(ind.series);
                            const value = dataItem.value ?? dataItem.close;
                            if (value !== undefined) {
                                const priceY = ind.series.priceToCoordinate(value);
                                if (priceY !== null && Math.abs(priceY - param.point.y) < 5) { // 5px tolerance
                                    hitDrawing = {
                                        id: ind.id,
                                        _type: 'indicator',
                                        // We need to mimic drawing object for openProperties
                                        // But openProperties expects a drawing with an ID or type
                                        // Let's create a proxy object or just handle it directly
                                    };
                                    // Hack: Store reference to series on the hit object if needed
                                    break;
                                }
                            }
                        }
                    }
                }
            }

            if (hitDrawing) {
                // If it's a standard indicator (string ID), we need to open its properties
                if (hitDrawing._type === 'indicator') {
                    // Handle standard indicator
                    setSelectedDrawingOptions(indicatorParams?.[hitDrawing.id] || {});
                    setSelectedDrawingType(hitDrawing.id);
                    setPropertiesModalOpen(true);
                } else {
                    openProperties(hitDrawing);
                }
            }
        };

        chart.subscribeClick(clickHandler)
        // @ts-ignore - subscribeDblClick might be missing in older type definitions but exists at runtime
        chart.subscribeDblClick?.(dblClickHandler)

        return () => {
            chart.unsubscribeClick(clickHandler)
            // @ts-ignore
            chart.unsubscribeDblClick?.(dblClickHandler)
        }
    }, [chart, series, onSelectionChange, isSelectingReplayStart]);


    // Helper functions for UI
    const openProperties = (drawing: any) => {
        const options = drawing.options ? drawing.options() : {};
        const type = drawing._type || 'anchored-text';
        setSelectedDrawingOptions(options);
        setSelectedDrawingType(type);

        // Type-specific settings dialogs
        if (type === 'trend-line') {
            setTrendLineSettingsOpen(true);
        } else if (type === 'horizontal-line') {
            setHorizontalLineSettingsOpen(true);
        } else if (type === 'rectangle') {
            setRectangleSettingsOpen(true);
        } else if (type === 'vertical-line') {
            setVerticalLineSettingsOpen(true);
        } else if (type === 'ray') {
            setRaySettingsOpen(true);
        } else if (type === 'text') {
            setTextSettingsOpen(true);
        } else {
            // Fallback to generic PropertiesModal
            setPropertiesModalOpen(true);
        }
    }

    const openDrawingSettings = () => {
        if (selectedDrawingRef.current) openProperties(selectedDrawingRef.current);
    };

    const deleteDrawingInternal = (id: string) => {
        if (v2SandboxRef.current) {
            // Remove from V2 Core
            v2SandboxRef.current.plugin.removeLineToolsById([id]);

            // Update Storage & UI since CorePlugin doesn't emit delete events for programmatic calls
            DrawingStorage.deleteDrawing(ticker, timeframe, id);
            onDrawingDeleted?.(id);

            // Also clear selection if this tool was selected
            if (selectedDrawingId === id) {
                setSelectedDrawingId(null);
                setSelectedDrawingOptions({});
                setIsDrawingLocked(false);
                setIsDrawingHidden(false);
                setToolbarPosition(null);
            }
        }
    };

    const deleteSelectedDrawing = () => {
        // Always perform the deletion if there's a selected drawing
        if (selectedDrawingRef.current) {
            // Get ID safely
            let id = null;
            if (typeof selectedDrawingRef.current.id === 'function') {
                id = selectedDrawingRef.current.id();
            } else {
                id = selectedDrawingRef.current.id || selectedDrawingRef.current._id;
            }

            if (id) {
                deleteDrawingInternal(id);
                // Also ensure it is deselected visually
                deselectDrawing();
            }
        }
        // Also notify parent if callback exists (for indicators etc)
        if (onDeleteSelection) onDeleteSelection();
        setToolbarPosition(null);
    };

    const cloneSelectedDrawing = () => {
        if (selectedDrawingRef.current && !isDrawingLocked) {
            // Clone functionality - TODO: implement in drawingManager
            toast.info('Clone: Coming soon');
        }
    };

    const toggleDrawingLock = () => {
        setIsDrawingLocked(prev => !prev);
        if (selectedDrawingRef.current?.applyOptions) {
            selectedDrawingRef.current.applyOptions({ locked: !isDrawingLocked });
        }
    };

    const toggleDrawingVisibility = () => {
        setIsDrawingHidden(prev => !prev);
        if (selectedDrawingRef.current?.setVisible) {
            selectedDrawingRef.current.setVisible(!isDrawingHidden);
        }
    };

    // --- Keyboard Shortcut: Delete/Backspace to delete selected drawing ---
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Check if user is typing in an input field
            const target = e.target as HTMLElement;
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
                return;
            }

            // Delete or Backspace key
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (selectedDrawingRef.current) {
                    e.preventDefault();
                    deleteSelectedDrawing();
                }
            }

            // Escape key to deselect
            if (e.key === 'Escape') {
                if (selectedDrawingRef.current) {
                    deselectDrawing();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [ticker, timeframe]); // Dependencies to ensure fresh refs

    const handlePropertiesSave = (options: any) => {
        if (selectedDrawingRef.current && selectedDrawingType !== 'daily-profiler' && selectedDrawingType !== 'hourly-profiler') {
            const drawing = selectedDrawingRef.current;
            drawing.applyOptions?.(options);
            const id = typeof drawing.id === 'function' ? drawing.id() : drawing._id;

            if (id) {
                // Legacy serialization removed.
                // Assuming V2 updates via plugin or internal state if shared ref?
                // For now, just save options.
                DrawingStorage.updateDrawingOptions(ticker, timeframe, id, options);
            }
            toast.success('Properties saved');
        } else if (primitives?.current && selectedDrawingType === 'anchored-text') {
            const primitive = primitives.current.find((p: any) => p._type === 'anchored-text');
            primitive?.applyOptions?.(options);
            toast.success('Watermark updated');
        } else if (sessionRangesRef.current && selectedDrawingType === 'daily-profiler') {
            sessionRangesRef.current.applyOptions(options);
            onIndicatorParamsChange?.('daily-profiler', options); // FIX: Persist settings
            toast.success('Daily Profiler updated');
        } else if (selectedDrawingType === 'hourly-profiler') {
            // ...
            if (hourlyProfilerRef.current) {
                hourlyProfilerRef.current.applyOptions(options);
            }
            onIndicatorParamsChange?.('hourly-profiler', options);
            toast.success('Hourly Profiler updated');
        } else if (selectedDrawingType === 'range-extensions') {
            console.log('[ChartContainer] Saving Range Extensions:', options); // DEBUG
            if (rangeExtensionsRef.current) {
                rangeExtensionsRef.current.updateOptions(options);
            }
            onIndicatorParamsChange?.('range-extensions', options);
            toast.success('Range Extensions updated');
        } else if (selectedDrawingType === 'opening-range') {
            if (openingRangeRef.current) {
                openingRangeRef.current.applyOptions(options);
            }
            onIndicatorParamsChange?.('opening-range', options);
            toast.success('Opening Range updated');
        } else if (selectedDrawingType === 'truth-profiler') {
            if (truthProfilerRef.current) {
                truthProfilerRef.current.applyOptions(options);
            }
            onIndicatorParamsChange?.('truth-profiler', options);
            toast.success('Truth Profiler updated');
        }
    };

    const handleEditDrawing = (id: string) => {
        // Legacy drawingManager.getDrawing logic removed.
        const drawing = null;
        if (drawing) {
            // ...
        } else if (id === 'watermark' && primitives?.current) {
            const p = primitives.current.find((p: any) => p._type === 'anchored-text');
            if (p) {
                onSelectionChange?.({ type: 'indicator', id: 'watermark' });
                openProperties(p);
            }
        } else if (id === 'daily-profiler' && sessionRangesRef.current) {
            // Support editing Daily Profiler
            onSelectionChange?.({ type: 'indicator', id: 'daily-profiler' });
            openProperties(sessionRangesRef.current);
        } else if (id === 'hourly-profiler') {
            // Support editing Hourly Profiler - even if disabled (ref is null)
            onSelectionChange?.({ type: 'indicator', id: 'hourly-profiler' });
            if (hourlyProfilerRef.current) {
                openProperties(hourlyProfilerRef.current);
            } else {
                // Fallback for disabled state
                const currentParams = indicatorParams?.['hourly-profiler'] || {};
                setSelectedDrawingOptions(currentParams);
                setSelectedDrawingType('hourly-profiler');
                setPropertiesModalOpen(true);
            }
        } else if (id === 'range-extensions') {
            onSelectionChange?.({ type: 'indicator', id: 'range-extensions' });
            if (rangeExtensionsRef.current) {
                openProperties(rangeExtensionsRef.current);
                setRangeData(rangeExtensionsRef.current.data); // Sync data for panel
            } else {
                const currentParams = indicatorParams?.['range-extensions'] || {};
                setSelectedDrawingOptions(currentParams);
                setSelectedDrawingType('range-extensions');
                setPropertiesModalOpen(true);
            }
        } else if (id === 'opening-range') {
            onSelectionChange?.({ type: 'indicator', id: 'opening-range' });
            if (openingRangeRef.current) {
                openProperties(openingRangeRef.current);
            } else {
                const currentParams = indicatorParams?.['opening-range'] || {};
                setSelectedDrawingOptions(currentParams);
                setSelectedDrawingType('opening-range');
                setPropertiesModalOpen(true);
            }
        } else if (id === 'truth-profiler') {
            onSelectionChange?.({ type: 'indicator', id: 'truth-profiler' });
            if (truthProfilerRef.current) {
                openProperties(truthProfilerRef.current);
            } else {
                const currentParams = indicatorParams?.['truth-profiler'] || {};
                setSelectedDrawingOptions(currentParams);
                setSelectedDrawingType('truth-profiler');
                setPropertiesModalOpen(true);
            }
        } else if (id === 'expected-move') {
            onSelectionChange?.({ type: 'indicator', id: 'expected-move' });
            // Custom dialog for EM
            if (onOpenEMSettings) {
                onOpenEMSettings();
            }
        }
    };

    // Keyboard Shortcuts handled by useKeyboardShortcuts hook
    // Legacy implementation removed


    // Expose Functions
    useImperativeHandle(ref, () => ({
        deleteDrawing: (id) => {
            deleteDrawingInternal(id);
        },
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
                // Try to load data if needed (async), then scroll
                const result = await jumpToTime(time)
                if (result.needsScroll) {
                    // Data loaded or already present, scroll to target
                    setTimeout(() => {
                        scrollToTime(time)
                    }, 100)  // Small delay to let chart update
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
        takeScreenshot: () => {
            if (!chart) return null;
            return chart.takeScreenshot();
        }
    }), [scrollByBars, scrollToStart, scrollToEnd, scrollToTime, getDataRange, replayMode, replayIndex, fullData, chart, fullDataRange, jumpToTime])


    // -------------------------------------------------------------------------
    // 12. Volume Profile Plugin Integration
    // -------------------------------------------------------------------------

    // Import (Dynamic / Lazy to avoid SSR issues if any, but regular import is fine here)
    // Note: We need to import these at the top level, but for this edit block we assume they are added.
    // I will add the imports via a separate edit or assume the user accepts the diff logic if I put imports here? 
    // Typescript might complain. I'll add imports in a separate block first.

    const vpPrimitiveRef = useRef<any>(null); // Type: VolumeProfilePrimitive

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

    // -------------------------------------------------------------------------
    // 13. Session Ranges Integration
    // -------------------------------------------------------------------------
    const sessionRangesRef = useRef<any>(null);

    // 13. Truth Profiler Data Fetching
    useEffect(() => {
        if (!ticker) return;

        const loadData = async () => {
            try {
                // Fetch in parallel
                const [sessionsRes, levelsRes] = await Promise.all([
                    fetchProfilerStats(ticker),
                    fetchLevelTouches(ticker)
                ]);

                setTruthSessions(sessionsRes.sessions);
                setTruthLevels(levelsRes);

                if (truthProfilerRef.current) {
                    truthProfilerRef.current.setRemoteData(sessionsRes.sessions, levelsRes);
                }
            } catch (err) {
                console.error('[ChartContainer] Failed to fetch Truth Profiler data:', err);
            }
        };

        loadData();
    }, [ticker]);

    // 14. Truth Profiler Lifecycle
    useEffect(() => {
        if (!chart || !series || !theme) return;

        const isEnabled = indicators.includes('truth-profiler');

        if (isEnabled) {
            import('@/lib/charts/indicators/truth-profiler').then(({ TruthProfiler }) => {
                if (!truthProfilerRef.current) {
                    truthProfilerRef.current = new TruthProfiler(
                        chart,
                        series,
                        indicatorParams?.['truth-profiler'] || {},
                        theme,
                        () => { } // Redraw handled by internal primitive updates
                    );
                    series.attachPrimitive(truthProfilerRef.current);

                    // Push data if already loaded
                    if (truthSessions.length > 0) {
                        truthProfilerRef.current.setRemoteData(truthSessions, truthLevels);
                    }
                } else {
                    // Update options
                    truthProfilerRef.current.applyOptions(indicatorParams?.['truth-profiler'] || {});
                }
            });
        } else {
            if (truthProfilerRef.current) {
                series.detachPrimitive(truthProfilerRef.current);
                truthProfilerRef.current = null;
            }
        }
    }, [chart, series, indicators, theme, indicatorParams]);

    // Theme Sync for Truth Profiler
    useEffect(() => {
        if (truthProfilerRef.current && theme) {
            truthProfilerRef.current.updateTheme(theme);
        }
    }, [theme]);

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
    const emPluginRef = useRef<any>(null);

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
                    // If emSettings?.ticker is set, use it.
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
    const tradeVisualizationsRef = useRef<any[]>([]);

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
    const rangeExtensionsRef = useRef<any>(null);

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
    const hourlyProfilerRef = useRef<any>(null);

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
    const openingRangeRef = useRef<any>(null);

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
    const sessionHighlightingRef = useRef<any>(null);

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

            {/* FloatingToolbar - appears on drawing selection */}
            {selectedDrawingId && toolbarPosition && (
                <FloatingToolbar
                    drawingId={selectedDrawingId || ''}
                    drawingType={selectedDrawingType}
                    position={toolbarPosition}
                    options={selectedDrawingOptions || {}}
                    isLocked={isDrawingLocked}
                    isHidden={isDrawingHidden}
                    onSettings={openDrawingSettings}
                    onClone={cloneSelectedDrawing}
                    onLock={toggleDrawingLock}
                    onDelete={deleteSelectedDrawing}
                    onToggleVisibility={toggleDrawingVisibility}
                    onOptionsChange={(updates) => {
                        if (selectedDrawingRef.current && typeof selectedDrawingRef.current.applyOptions === 'function') {
                            selectedDrawingRef.current.applyOptions(updates);
                            setSelectedDrawingOptions((prev: Record<string, any> | null) => ({ ...prev, ...updates }));
                        }
                    }}
                    onPositionChange={(pos) => setToolbarPosition(pos)}
                />
            )}

            <PropertiesModal
                open={propertiesModalOpen}
                onOpenChange={setPropertiesModalOpen}
                drawingType={selectedDrawingType as any}
                initialOptions={selectedDrawingOptions}
                onSave={handlePropertiesSave}
                ticker={ticker}
            />

            {/* Inline Text Editor Overlay - Removed Legacy V1 */}
            {/* V2 Text Tool handles editing internally or will use a new overlay */}

            {/* Text Settings Dialog */}
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
                    if (selectedDrawingRef.current && typeof selectedDrawingRef.current.applyOptions === 'function') {
                        selectedDrawingRef.current.applyOptions(opts);
                        setSelectedDrawingOptions((prev: Record<string, any> | null) => ({ ...prev, ...opts }));
                    }
                    setTextSettingsOpen(false);
                }}
                onCancel={() => setTextSettingsOpen(false)}
            />

            {/* New TrendLine Settings Dialog */}
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
                points={selectedDrawingRef.current?._p1 && selectedDrawingRef.current?._p2 ? {
                    p1: selectedDrawingRef.current._p1,
                    p2: selectedDrawingRef.current._p2
                } : undefined}
                onApply={(opts) => {
                    // Convert back to TrendLine format
                    handlePropertiesSave({
                        lineColor: opts.color,
                        lineWidth: opts.width,
                        lineStyle: opts.style,
                        opacity: opts.opacity,
                        extendLeft: opts.extendLeft,
                        extendRight: opts.extendRight,
                        showAngle: opts.showAngle,
                        showDistance: opts.showDistance,
                        showPriceRange: opts.showPriceRange,
                        showBarsRange: opts.showBarsRange,
                        text: opts.text,
                        textColor: opts.textColor,
                        fontSize: opts.fontSize,
                        bold: opts.bold,
                        italic: opts.italic,
                        alignment: opts.alignment,
                        alignmentVertical: opts.alignmentVertical,
                        alignmentHorizontal: opts.alignmentHorizontal,
                    });
                }}
                onCancel={() => { }}
            />

            {/* Horizontal Line Settings Dialog */}
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
                price={selectedDrawingRef.current?._price}
                onApply={(opts, price) => {
                    handlePropertiesSave({
                        color: opts.color,
                        width: opts.width,
                        lineStyle: opts.style,
                        showLabel: opts.showLabel,
                        labelBackgroundColor: opts.labelBackgroundColor,
                        labelTextColor: opts.labelTextColor,
                        text: opts.text,
                        textColor: opts.textColor,
                        fontSize: opts.fontSize,
                        bold: opts.bold,
                        italic: opts.italic,
                        alignmentVertical: opts.alignmentVertical,
                        alignmentHorizontal: opts.alignmentHorizontal,
                    });
                }}
                onCancel={() => { }}
            />

            {/* Rectangle Settings Dialog */}
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
                }}
                points={selectedDrawingRef.current?._p1 && selectedDrawingRef.current?._p2 ? {
                    p1: selectedDrawingRef.current._p1,
                    p2: selectedDrawingRef.current._p2
                } : undefined}
                onApply={(opts) => {
                    handlePropertiesSave({
                        borderColor: opts.borderColor,
                        borderWidth: opts.borderWidth,
                        borderStyle: opts.borderStyle,
                        fillColor: opts.fillColor,
                        fillOpacity: opts.fillOpacity,
                        showMidline: opts.showMidline,
                        showQuarterLines: opts.showQuarterLines,
                        text: opts.text,
                        textColor: opts.textColor,
                        fontSize: opts.fontSize,
                        bold: opts.bold,
                        italic: opts.italic,
                        alignmentVertical: opts.alignmentVertical,
                        alignmentHorizontal: opts.alignmentHorizontal,
                    });
                }}
                onCancel={() => { }}
            />

            {/* Vertical Line Settings Dialog */}
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
                time={selectedDrawingRef.current?._time}
                onApply={(opts) => {
                    handlePropertiesSave({
                        color: opts.color,
                        width: opts.width,
                        lineStyle: opts.style,
                        showLabel: opts.showLabel,
                        labelBackgroundColor: opts.labelBackgroundColor,
                        labelTextColor: opts.labelTextColor,
                        text: opts.text,
                        textColor: opts.textColor,
                        fontSize: opts.fontSize,
                        bold: opts.bold,
                        italic: opts.italic,
                        alignmentVertical: opts.alignmentVertical,
                        alignmentHorizontal: opts.alignmentHorizontal,
                        orientation: opts.orientation,
                    });
                }}
                onCancel={() => { }}
            />

            {/* Ray Settings Dialog */}
            <RaySettingsDialog
                open={raySettingsOpen}
                onOpenChange={setRaySettingsOpen}
                options={{
                    ...DEFAULT_RAY_OPTIONS,
                    color: selectedDrawingOptions?.lineColor || '#2962FF',
                    width: selectedDrawingOptions?.lineWidth || 2,
                    style: selectedDrawingOptions?.lineStyle || 0,
                    text: selectedDrawingOptions?.text,
                    textColor: selectedDrawingOptions?.textColor,
                    fontSize: selectedDrawingOptions?.fontSize,
                    bold: selectedDrawingOptions?.bold,
                    italic: selectedDrawingOptions?.italic,
                    alignmentVertical: selectedDrawingOptions?.alignmentVertical,
                    alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
                }}
                point={selectedDrawingRef.current?._p1}
                onApply={(opts) => {
                    handlePropertiesSave({
                        lineColor: opts.color,
                        lineWidth: opts.width,
                        lineStyle: opts.style,
                        text: opts.text,
                        textColor: opts.textColor,
                        fontSize: opts.fontSize,
                        bold: opts.bold,
                        italic: opts.italic,
                        alignmentVertical: opts.alignmentVertical,
                        alignmentHorizontal: opts.alignmentHorizontal,
                    });
                }}
                onCancel={() => { }}
            />
        </div>
    )
}))

ChartContainer.displayName = "ChartContainer"
