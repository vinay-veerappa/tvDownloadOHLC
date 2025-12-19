"use client"

import { useEffect, useRef, useState, useMemo, forwardRef, useImperativeHandle } from "react"
import { useChart } from "@/hooks/use-chart"
import { DrawingTool } from "./left-toolbar"
import { Drawing } from "./right-sidebar"
import { PropertiesModal } from "./properties-modal"
import { DrawingStorage, SerializedDrawing } from "@/lib/drawing-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"
import { useTradeContext } from "@/components/journal/trade-context"
import { toast } from "sonner"
import { useDrawingManager } from "@/hooks/use-drawing-manager"
// New Hooks
import { useChartData } from "@/hooks/chart/use-chart-data"
import { useChartTrading } from "@/hooks/chart/use-chart-trading"
import { useChartDrag } from "@/hooks/chart/use-chart-drag"
import { useDrawingInteraction } from "@/hooks/chart/use-drawing-interaction"
import { ChartContextMenu } from "@/components/chart/chart-context-menu"
import { ChartLegend, ChartLegendRef } from "@/components/chart/chart-legend"
import { ChartCursorOverlay } from "@/components/chart-cursor-overlay"
import { VWAPSettings } from "@/lib/indicator-api"
import { ThemeParams } from "@/lib/themes"
import type { EMSettings } from './em-settings-dialog'
import { ColorType } from "lightweight-charts"
import { RangeInfoPanel } from "./range-info-panel"
import { RangeTooltip } from "./range-tooltip"
import { RangeExtensions, RangeExtensionPeriod, getContractSpecs } from "@/lib/charts/indicators/range-extensions"
import { useKeyboardShortcuts } from "@/hooks/chart/use-keyboard-shortcuts"

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
    selection?: { type: 'drawing' | 'indicator', id: string } | null
    onSelectionChange?: (selection: { type: 'drawing' | 'indicator', id: string } | null) => void
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
}


export const ChartContainer = forwardRef<ChartContainerRef, ChartContainerProps>(({
    ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, onDrawingDeleted,
    indicators, markers, magnetMode = 'off', displayTimezone = 'America/New_York', sessionType = 'ETH',
    selection, onSelectionChange, onDeleteSelection, onReplayStateChange, onDataLoad,
    onPriceChange, position, pendingOrders, onModifyOrder, onModifyPosition, initialReplayTime,
    vwapSettings, indicatorParams, onIndicatorParamsChange, theme, onTimeframeChange, trades, mode // Destructure mode
}, ref) => {

    // 1. Chart Reference
    const chartContainerRef = useRef<HTMLDivElement>(null)

    // Bridge for lazy access to chart methods
    const getVisibleTimeRangeRef = useRef<(() => { start: number, end: number, center: number } | null) | null>(null)

    // Range UI State
    const [rangeExtensionsActive, setRangeExtensionsActive] = useState(false);
    const [rangeData, setRangeData] = useState<RangeExtensionPeriod[]>([]);


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
    const dataRef = useRef(data)
    const seriesRef = useRef(series)
    const isSubscribedRef = useRef(false)

    // Keep refs in sync
    dataRef.current = data
    seriesRef.current = series

    // Subscribe to crosshair moves ONCE when chart is ready
    useEffect(() => {
        if (!chart || !series || isSubscribedRef.current) return

        const handleCrosshairMove = (param: any) => {
            const currentData = dataRef.current
            const currentSeries = seriesRef.current
            if (!currentData || currentData.length === 0 || !currentSeries) return

            if (!param || !param.time) {
                // Mouse left chart - show latest candle
                const lastBar = currentData[currentData.length - 1]
                if (lastBar) {
                    legendRef.current?.updateOHLC({ open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close })
                }
                return
            }

            // Get the candle data at crosshair position
            const candleData = param.seriesData.get(currentSeries)
            if (candleData) {
                legendRef.current?.updateOHLC({
                    open: candleData.open,
                    high: candleData.high,
                    low: candleData.low,
                    close: candleData.close
                })
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        isSubscribedRef.current = true

        // Set initial value after a small delay
        const timer = setTimeout(() => {
            const currentData = dataRef.current
            if (currentData && currentData.length > 0) {
                const lastBar = currentData[currentData.length - 1]
                legendRef.current?.updateOHLC({ open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close })
            }
        }, 100)

        return () => {
            clearTimeout(timer)
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
            isSubscribedRef.current = false
        }
    }, [chart, series])

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

    // 5. Drawing Manager
    const drawingManager = useDrawingManager(
        chart, series, ticker, timeframe,
        onDrawingCreated, onDrawingDeleted
    );

    // 6. Selection State Management
    const selectedDrawingRef = useRef<any>(null)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)
    const [propertiesModalOpen, setPropertiesModalOpen] = useState(false)
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)

    // Sync external selection
    useEffect(() => {
        if (!selection) {
            deselectDrawing();
            return;
        }
        if (selection.type === 'drawing') {
            const drawing = drawingManager.getDrawing(selection.id);
            if (drawing) {
                if (selectedDrawingRef.current?.setSelected) selectedDrawingRef.current.setSelected(false);
                if (drawing.setSelected) drawing.setSelected(true);
                selectedDrawingRef.current = drawing;
                setSelectedDrawingId(selection.id);
            }
        } else {
            deselectDrawing();
        }
    }, [selection, drawingManager]);

    const deselectDrawing = () => {
        if (selectedDrawingRef.current?.setSelected) selectedDrawingRef.current.setSelected(false);
        selectedDrawingRef.current = null;
        setSelectedDrawingId(null);
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

    const handleDrawingModified = (id: string, drawing: any) => {
        // Persist
        const opts = drawing.options ? drawing.options() : {};
        if (id) DrawingStorage.updateDrawingOptions(ticker, timeframe, id, opts);

        // Also update points if strictly needed (DrawingStorage usually handles options, but points are separate?)
        // DrawingStorage.updateDrawingOptions stores "options". 
        // Most drawings store points in options or separate? 
        // Looking at drawing-storage.ts: updateDrawingOptions saves "options". 
        // Does it save points? 
        // Standard Lightweight Charts primitives usually keep points in private fields, 
        // but our wrappers might expose them in options() or we need a separate savePoints?

        // For Fib/TrendLine, points are usually part of the serialized state.
        // DrawingStorage.saveDrawing saves the whole object.
        // updateDrawingOptions only updates the "options" object.

        // If we drag, points change. We should probably use drawingManager.saveDrawings() or similar?
        // Or specific update method.

        // Let's check drawingManager. 
        // drawingManager doesn't expose granular updates easily.
        // But DrawingStorage has updateDrawing (full replace?).

        // Let's assume for now we can just save all drawings or update specific one.
        // Better: DrawingStorage.updateDrawing(ticker, timeframe, serializedDrawing);

        const serialized = drawingManager.serializeDrawing(drawing);
        if (serialized) {
            DrawingStorage.updateDrawing(ticker, timeframe, serialized.id, serialized);
        }
    };

    const handleDrawingClicked = (id: string, drawing: any) => {
        onSelectionChange?.({ type: 'drawing', id });
    };

    useDrawingInteraction({
        chartContainerRef,
        chart,
        series,
        drawingManager,
        onDrawingModified: handleDrawingModified,
        onDrawingClicked: handleDrawingClicked,
        isTradingDragActive: false // Placeholder until we wire up shared state
    });


    // 9. Tool Initiation
    useEffect(() => {
        drawingManager.initiateTool(
            selectedTool, magnetMode, data,
            () => onToolSelect('cursor'),
            (id, drawing) => {
                onSelectionChange?.({ type: 'drawing', id });
                setSelectedDrawingOptions(drawing.options ? drawing.options() : {});
                setSelectedDrawingType(drawing._type || selectedTool);
                // Only open properties for text or if configured to do so (Fibonacci usually doesn't auto-open, but we can if desired)
                // For now, let's keep the behavior consistent but correct the type.
                if (selectedTool === 'text' || selectedTool === 'fibonacci') {
                    setPropertiesModalOpen(true);
                }
            }
        );
    }, [selectedTool, magnetMode, data, drawingManager, onToolSelect, onSelectionChange]);


    // 10. Load Drawings
    const hasLoadedDrawingsRef = useRef(false);
    useEffect(() => { hasLoadedDrawingsRef.current = false; }, [ticker, timeframe]);
    useEffect(() => {
        if (data && data.length > 0 && !hasLoadedDrawingsRef.current) {
            drawingManager.loadDrawings(data);
            hasLoadedDrawingsRef.current = true;
        }
    }, [drawingManager, ticker, timeframe, data]);


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
            const result = drawingManager.hitTest(param.point.x, param.point.y);
            if (result) hitDrawing = result.drawing;
            else if (primitives?.current) {
                for (const p of primitives.current) {
                    if (p.hitTest?.(param.point.x, param.point.y)) { hitDrawing = p; break; }
                }
            }

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;
                onSelectionChange?.({ type: hitDrawing._type || 'drawing', id });
            } else {
                deselectDrawing();
            }
        }

        const dblClickHandler = (param: any) => {
            if (!param.point) return;

            let hitDrawing: any = null;
            const result = drawingManager.hitTest(param.point.x, param.point.y);
            if (result) hitDrawing = result.drawing;
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
    }, [chart, series, drawingManager, onSelectionChange, isSelectingReplayStart]);


    // Helper functions for UI
    const openProperties = (drawing: any) => {
        const options = drawing.options ? drawing.options() : {};
        const type = drawing._type || 'anchored-text';
        setSelectedDrawingOptions(options);
        setSelectedDrawingType(type);
        setPropertiesModalOpen(true);
    }

    const openDrawingSettings = () => {
        if (selectedDrawingRef.current) openProperties(selectedDrawingRef.current);
    };

    const deleteSelectedDrawing = () => {
        if (onDeleteSelection) onDeleteSelection();
        else if (selectedDrawingRef.current) {
            const id = typeof selectedDrawingRef.current.id === 'function' ? selectedDrawingRef.current.id() : selectedDrawingRef.current.id;
            drawingManager.deleteDrawing(id);
            deselectDrawing();
        }
    };

    const handlePropertiesSave = (options: any) => {
        if (selectedDrawingRef.current && selectedDrawingType !== 'daily-profiler' && selectedDrawingType !== 'hourly-profiler') {
            const drawing = selectedDrawingRef.current;
            drawing.applyOptions?.(options);
            const id = typeof drawing.id === 'function' ? drawing.id() : drawing._id;

            if (id) {
                // Use full serialization to ensure atomic update of options + points (if interconnected)
                const serialized = drawingManager.serializeDrawing(drawing);
                if (serialized) {
                    DrawingStorage.updateDrawing(ticker, timeframe, id, serialized);
                } else {
                    // Fallback
                    DrawingStorage.updateDrawingOptions(ticker, timeframe, id, options);
                }
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
        }
    };

    const handleEditDrawing = (id: string) => {
        const drawing = drawingManager.getDrawing(id);
        if (drawing) {
            onSelectionChange?.({ type: 'drawing', id });
            openProperties(drawing);
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
        }
    };

    // Keyboard Shortcuts handled by useKeyboardShortcuts hook
    // Legacy implementation removed


    // Expose Functions
    useImperativeHandle(ref, () => ({
        deleteDrawing: (id) => drawingManager?.deleteDrawing(id),
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
        getTotalBars: () => fullData.length
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

        // Enable if 'expected-move' or 'em' is in indicators list
        // OR if the ticker is SPY, ES, or SPX (auto-enable for these)
        const isEMTicker = ticker.includes('SPY') || ticker.includes('ES') || ticker.includes('SPX');
        const showEM = indicators.includes('expected-move') || indicators.includes('em') || isEMTicker;

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
                    // Map ticker to API format (ES1 -> ES, SPX -> SPX, SPY -> SPY)
                    let apiTicker = ticker;
                    if (ticker.includes('ES') || ticker.includes('/ES')) apiTicker = 'ES';
                    else if (ticker.includes('SPX') || ticker === '$SPX') apiTicker = 'SPX';
                    else if (ticker.includes('SPY')) apiTicker = 'SPY';

                    const resp = await fetch(`/api/em-levels?ticker=${apiTicker}`);
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
    }, [series, chart, ticker, theme, indicators]);

    useEffect(() => {
        if (emPluginRef.current && data.length > 0) {
            emPluginRef.current.updateFromBars(data);
        }
    }, [data, timeframe]);

    // -------------------------------------------------------------------------
    // 14. Trade Visualizations (Risk/Reward)
    // -------------------------------------------------------------------------
    const tradeVisualizationsRef = useRef<any[]>([]);

    useEffect(() => {
        if (!series || !chart || !trades || trades.length === 0) {
            // Cleanup if no trades
            tradeVisualizationsRef.current.forEach(p => series?.detachPrimitive(p));
            tradeVisualizationsRef.current = [];
            return;
        }

        import('@/lib/charts/plugins/risk-reward').then(({ RiskReward }) => {
            // Cleanup old
            tradeVisualizationsRef.current.forEach(p => series.detachPrimitive(p));
            tradeVisualizationsRef.current = [];

            // Performance: Limit to last 50 trades to prevent hanging
            // Assuming trades are chronological or we take the end of the array
            const visibleTrades = trades.slice(-50);

            visibleTrades.forEach(trade => {
                // Ensure we have necessary prices
                if (!trade.entryPrice) return;

                // Construct points
                // For closed trades, we want the box to span from Entry Time to Exit Time
                // Entry Point
                const entry = { time: trade.entryDate, price: trade.entryPrice };

                // Target Point (controls Width and TP Level)
                // Use Exit Time for width. Use TP Price for level.
                // If no TP price (e.g. manual exit), use Exit Price or calculate R?
                // Let's use trade.tpPrice if available, else exitPrice.
                const targetPrice = trade.tpPrice || trade.exitPrice || (trade.entryPrice * 1.01);
                const target = { time: trade.exitDate, price: targetPrice };

                // Stop Point (controls SL Level)
                // Use Exit Time for consistency? RiskRewardRenderer uses targetX for width.
                const stopPrice = trade.slPrice || (trade.entryPrice * 0.99);
                const stop = { time: trade.exitDate, price: stopPrice };

                const rr = new RiskReward(chart, series, entry, stop, target, {
                    stopOpacity: 0.1,
                    targetOpacity: 0.1,
                    lineColor: trade.pnl > 0 ? '#4CAF50' : (trade.pnl < 0 ? '#EF5350' : '#888888'),
                    showLabels: false // Too noisy for many trades? Maybe true for single trade.
                });

                // Hack: If we want to show Labels only on Selected trade? 
                // For now, let's enable labels but maybe compact mode?
                rr.applyOptions({
                    showLabels: true,
                    compactMode: true,
                    // If trade is a LOSS, color the "Target" zone grey? 
                    // No, "Target" is where TP WAS. "Stop" is where SL WAS.
                    // The actual exit is just where the box ends.
                });

                series.attachPrimitive(rr);
                tradeVisualizationsRef.current.push(rr);
            });
        });

    }, [series, chart, trades]);

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
                    }, theme);
                    series.attachPrimitive(hourlyProfilerRef.current);

                    // Initial Data Push
                    if (data && data.length > 0) {
                        hourlyProfilerRef.current.setData(data);
                    }
                } else {
                    hourlyProfilerRef.current.applyOptions({ ...hourlyParams, ticker });
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

                // Auto-detect specs from ticker
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

            {/* OHLC Legend Overlay - outside chartContainerRef so it survives */}
            <ChartLegend
                ref={legendRef}
                ticker={ticker}
                timeframe={timeframe}
                className="absolute top-2 left-2 z-50 bg-background/80 backdrop-blur-sm px-2 py-1 rounded pointer-events-none"
            />

            <ChartContextMenu
                containerRef={chartContainerRef}
                selectedDrawing={selectedDrawingRef.current}
                onDelete={deleteSelectedDrawing}
                onSettings={openDrawingSettings}
            />

            <PropertiesModal
                open={propertiesModalOpen}
                onOpenChange={setPropertiesModalOpen}
                drawingType={selectedDrawingType as any}
                initialOptions={selectedDrawingOptions}
                onSave={handlePropertiesSave}
                ticker={ticker}
            />
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
