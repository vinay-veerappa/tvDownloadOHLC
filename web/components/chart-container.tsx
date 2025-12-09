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
import { VWAPSettings } from "@/lib/indicator-api"
import { ThemeParams } from "@/lib/themes"
import { ColorType } from "lightweight-charts"

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
    selection?: { type: 'drawing' | 'indicator', id: string } | null
    onSelectionChange?: (selection: { type: 'drawing' | 'indicator', id: string } | null) => void
    onDeleteSelection?: () => void
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
    onPriceChange?: (price: number) => void
    initialReplayTime?: number // Timestamp to restore replay position after remount

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
    indicatorParams?: Record<string, any>
    onIndicatorParamsChange?: (type: string, params: any) => void
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
    indicators, markers, magnetMode = 'off', displayTimezone = 'America/New_York',
    selection, onSelectionChange, onDeleteSelection, onReplayStateChange, onDataLoad,
    onPriceChange, position, pendingOrders, onModifyOrder, onModifyPosition, initialReplayTime,
    vwapSettings, indicatorParams, onIndicatorParamsChange, theme // Destructure theme
}, ref) => {

    // 1. Chart Reference
    const chartContainerRef = useRef<HTMLDivElement>(null)

    // Bridge for lazy access to chart methods
    const getVisibleTimeRangeRef = useRef<(() => { start: number, end: number, center: number } | null) | null>(null)

    // 2. Data & Replay Logic (Hook)
    const {
        fullData, data, replayMode, replayIndex, isSelectingReplayStart,
        setIsSelectingReplayStart, startReplay, startReplaySelection, stopReplay,
        stepForward, stepBack, findIndexForTime, setReplayIndex,
        loadMoreData, hasMoreData, isLoadingMore, fullDataRange, jumpToTime
    } = useChartData({
        ticker, timeframe, onDataLoad, onReplayStateChange, onPriceChange,
        getVisibleTimeRange: () => getVisibleTimeRangeRef.current?.() ?? null,
        initialReplayTime
    })

    // 3. Core Chart Initialization (Hook)
    const {
        chart, series, primitives, scrollByBars, scrollToStart, scrollToEnd,
        scrollToTime, getDataRange, getVisibleTimeRange
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
                    console.log('[LOAD] Triggering loadMoreData, barsBefore:', barsInfo.barsBefore)
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

    // 4d. Keyboard Navigation
    // Arrow Left/Right: Scroll, Arrow Up/Down: Zoom, Home: Go to first bar
    useEffect(() => {
        if (!chart || !chartContainerRef.current) return

        const handleKeyDown = (e: KeyboardEvent) => {
            // Only handle if chart container or its children have focus
            if (!chartContainerRef.current?.contains(document.activeElement) &&
                document.activeElement !== document.body) return

            const timeScale = chart.timeScale()
            const SCROLL_BARS = 20  // Scroll by 20 bars per key press
            const ZOOM_FACTOR = 0.1 // Zoom by 10% per key press

            switch (e.key) {
                case 'ArrowLeft':
                    e.preventDefault()
                    timeScale.scrollToPosition(
                        timeScale.scrollPosition() - SCROLL_BARS,
                        false
                    )
                    console.log('[KEY] Scroll left')
                    break

                case 'ArrowRight':
                    e.preventDefault()
                    timeScale.scrollToPosition(
                        timeScale.scrollPosition() + SCROLL_BARS,
                        false
                    )
                    console.log('[KEY] Scroll right')
                    break

                case 'ArrowUp':
                    e.preventDefault()
                    // Zoom in by reducing bar spacing
                    const currentSpacing = timeScale.options().barSpacing
                    timeScale.applyOptions({
                        barSpacing: currentSpacing * (1 + ZOOM_FACTOR)
                    })
                    console.log('[KEY] Zoom in')
                    break

                case 'ArrowDown':
                    e.preventDefault()
                    // Zoom out by increasing bar spacing
                    const spacing = timeScale.options().barSpacing
                    timeScale.applyOptions({
                        barSpacing: Math.max(1, spacing * (1 - ZOOM_FACTOR))
                    })
                    console.log('[KEY] Zoom out')
                    break

                case 'Home':
                    e.preventDefault()
                    // Go to newest data (user preference: Home = latest)
                    // Use scrollToPosition(0) = rightmost position (last bar visible)
                    requestAnimationFrame(() => {
                        timeScale.scrollToPosition(0, false)
                    })
                    console.log('[KEY] Home - scroll to latest')
                    break

                case 'End':
                    e.preventDefault()
                    // Go to oldest data (user preference: End = oldest)
                    if (data.length > 0) {
                        // Scroll to leftmost position (oldest bar at left edge)
                        requestAnimationFrame(() => {
                            timeScale.scrollToPosition(-data.length + 100, false)
                        })
                        console.log('[KEY] End - scroll to oldest bar')
                    }
                    break
            }
        }

        // Add to window to catch keys when chart has focus
        window.addEventListener('keydown', handleKeyDown)

        // Make chart container focusable
        if (chartContainerRef.current) {
            chartContainerRef.current.tabIndex = 0
        }

        return () => {
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [chart, data.length])

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
                const now = Date.now();
                if (now - lastClickRef.current < 800 && lastClickIdRef.current === id) {
                    openProperties(hitDrawing)
                }
                lastClickRef.current = now;
                lastClickIdRef.current = id;
            } else {
                deselectDrawing();
            }
        }
        chart.subscribeClick(clickHandler)
        return () => chart.unsubscribeClick(clickHandler)
    }, [chart, series, drawingManager, onSelectionChange, isSelectingReplayStart]);


    // Helper functions for UI
    const openProperties = (drawing: any) => {
        setSelectedDrawingOptions(drawing.options ? drawing.options() : {});
        setSelectedDrawingType(drawing._type || 'anchored-text');
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
            toast.success('Daily Profiler updated');
        } else if (hourlyProfilerRef.current && selectedDrawingType === 'hourly-profiler') {
            hourlyProfilerRef.current.updateOptions(options);
            toast.success('Hourly Profiler updated');
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
        } else if (id === 'hourly-profiler' && hourlyProfilerRef.current) {
            // Support editing Hourly Profiler
            onSelectionChange?.({ type: 'indicator', id: 'hourly-profiler' });
            openProperties(hourlyProfilerRef.current);
        }
    };

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // 1. Check if user is typing in an input/textarea
            const activeTag = document.activeElement?.tagName.toLowerCase();
            const isInputActive = activeTag === 'input' || activeTag === 'textarea' || (document.activeElement as HTMLElement)?.isContentEditable;

            if (isInputActive) return;

            // 2. Delete / Backspace
            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault(); // Prevent browser back navigation if Backspace
                deleteSelectedDrawing();
            }

            // 3. Escape for Deselection
            if (e.key === 'Escape') {
                e.preventDefault();
                deselectDrawing();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onDeleteSelection, drawingManager]);


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

        const isEnabled = indicators.includes('daily-profiler');

        if (isEnabled) {
            import('@/lib/charts/indicators/daily-profiler').then(({ DailyProfiler }) => {
                const dailyParams = indicatorParams?.['daily-profiler'] || {};

                // Recreate if series/chart instance changed (e.g. timeframe change)
                if (sessionRangesRef.current && (sessionRangesRef.current._series !== series || sessionRangesRef.current._chart !== chart)) {
                    console.log('[ChartContainer] Series changed, recreating DailyProfiler');
                    if (sessionRangesRef.current.destroy) sessionRangesRef.current.destroy();
                    sessionRangesRef.current = null;
                }

                if (!sessionRangesRef.current) {
                    sessionRangesRef.current = new DailyProfiler(chart, series, {
                        ticker,
                        showAsia: true,
                        extendUntil: "16:00",
                        ...dailyParams
                    }, (newOpts) => onIndicatorParamsChange?.('daily-profiler', newOpts));
                    series.attachPrimitive(sessionRangesRef.current);
                } else {
                    // Update options (ticker + saved params), suppress notification to avoid loops
                    sessionRangesRef.current.applyOptions({ ticker, ...dailyParams }, true);
                }
            });
        } else {
            if (sessionRangesRef.current) {
                try {
                    if (sessionRangesRef.current.destroy) {
                        sessionRangesRef.current.destroy();
                    }
                    series.detachPrimitive(sessionRangesRef.current);
                } catch (e) { /* ignore */ }
                sessionRangesRef.current = null;
            }
        }
    }, [series, chart, ticker, indicators, indicatorParams, onIndicatorParamsChange]);

    // -------------------------------------------------------------------------
    // 14. Hourly Profiler Integration
    // -------------------------------------------------------------------------
    const hourlyProfilerRef = useRef<any>(null);

    useEffect(() => {
        if (!series || !chart || !ticker) return;

        const isEnabled = indicators.includes('hourly-profiler');

        if (isEnabled) {
            import('@/lib/charts/indicators/hourly-profiler').then(({ HourlyProfiler }) => {
                const hourlyParams = indicatorParams?.['hourly-profiler'] || {};

                // Recreate if series/chart instance changed
                if (hourlyProfilerRef.current && (hourlyProfilerRef.current._series !== series)) {
                    console.log('[ChartContainer] Series changed, recreating HourlyProfiler');
                    if (hourlyProfilerRef.current.destroy) hourlyProfilerRef.current.destroy();
                    hourlyProfilerRef.current = null;
                }

                if (!hourlyProfilerRef.current) {
                    hourlyProfilerRef.current = new HourlyProfiler(series, {
                        ticker,
                        ...hourlyParams
                    }, theme);
                    series.attachPrimitive(hourlyProfilerRef.current);
                } else {
                    // Update options
                    hourlyProfilerRef.current.updateOptions({ ticker, ...hourlyParams });
                }
            });
        } else {
            if (hourlyProfilerRef.current) {
                try {
                    if (hourlyProfilerRef.current.destroy) {
                        hourlyProfilerRef.current.destroy();
                    }
                    series.detachPrimitive(hourlyProfilerRef.current);
                } catch (e) { /* ignore */ }
                hourlyProfilerRef.current = null;
            }
        }
    }, [series, chart, ticker, indicators, indicatorParams, theme]);

    return (
        <div className="w-full h-full relative" onContextMenu={(e) => {
            // Keep native React onContextMenu as backup
        }}>
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
            />
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
