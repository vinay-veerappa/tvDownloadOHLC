"use client"

import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react"
import { useChart } from "@/hooks/use-chart"
import { getChartData } from "@/actions/data-actions"
import { DrawingTool } from "./left-toolbar"
import { Drawing } from "./right-sidebar"
import { TrendLineTool } from "@/lib/charts/plugins/trend-line"
import { FibonacciTool } from "@/lib/charts/plugins/fibonacci"
import { RectangleDrawingTool } from "@/lib/charts/plugins/rectangle"
import { VertLineTool } from "@/lib/charts/plugins/vertical-line"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"
import { PropertiesModal } from "./properties-modal"
import { DrawingStorage, SerializedDrawing } from "@/lib/drawing-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"

import { useTradeContext } from "@/components/journal/trade-context"
import { toast } from "sonner"

interface ChartContainerProps {
    ticker: string
    timeframe: string
    style: string
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    onDrawingCreated: (drawing: Drawing) => void
    onDrawingDeleted?: (id: string) => void
    indicators: string[]
    markers?: any[]
    magnetMode?: MagnetMode
}

export interface ChartContainerRef {
    deleteDrawing: (id: string) => void
}

export const ChartContainer = forwardRef<ChartContainerRef, ChartContainerProps>(({ ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, onDrawingDeleted, indicators, markers, magnetMode = 'off' }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const [data, setData] = useState<any[]>([])
    const { chart, series } = useChart(chartContainerRef as React.RefObject<HTMLDivElement>, style, indicators, data, markers)
    const activeToolRef = useRef<any>(null)
    const drawingsRef = useRef<Map<string, any>>(new Map())
    const { openTradeDialog } = useTradeContext()

    useImperativeHandle(ref, () => ({
        deleteDrawing: (id: string) => {
            if (!series) return
            const drawing = drawingsRef.current.get(id)
            if (drawing) {
                series.detachPrimitive(drawing)
                drawingsRef.current.delete(id)
                // Remove from storage
                DrawingStorage.deleteDrawing(ticker, timeframe, id)
                toast.success('Drawing deleted')
            }
        }
    }))


    // Load Data
    useEffect(() => {
        async function loadData() {
            try {
                const result = await getChartData(ticker, timeframe)
                if (result.success && result.data) {
                    setData(result.data)
                } else {
                    toast.error(`Failed to load data for ${ticker} ${timeframe}`)
                }
            } catch (e) {
                console.error("Failed to load data:", e)
                toast.error("An unexpected error occurred while loading data")
            }
        }
        loadData()
    }, [ticker, timeframe])

    // Load Saved Drawings
    useEffect(() => {
        if (!chart || !series || !data.length) return;

        // Clear existing drawings
        drawingsRef.current.forEach(drawing => {
            series.detachPrimitive(drawing);
        });
        drawingsRef.current.clear();

        // Load from storage
        const savedDrawings = DrawingStorage.getDrawings(ticker, timeframe);
        const restoredDrawings: Drawing[] = [];

        savedDrawings.forEach(saved => {
            try {
                let DrawingClass: any;
                let drawing: any;

                switch (saved.type) {
                    case 'trend-line':
                        // Restore TrendLine
                        const { TrendLine } = require('@/lib/charts/plugins/trend-line');
                        drawing = new TrendLine(chart, series, saved.p1, saved.p2, saved.options);
                        break;
                    case 'rectangle':
                        // Restore Rectangle
                        const { Rectangle } = require('@/lib/charts/plugins/rectangle');
                        drawing = new Rectangle(chart, series, saved.p1, saved.p2, saved.options);
                        break;
                    case 'fibonacci':
                        // Restore Fibonacci
                        const { FibonacciRetracement } = require('@/lib/charts/plugins/fibonacci');
                        drawing = new FibonacciRetracement(chart, series, saved.p1, saved.p2, saved.options);
                        break;
                    case 'vertical-line':
                        // Restore VerticalLine - uses time, not p1/p2 point
                        const { VertLine } = require('@/lib/charts/plugins/vertical-line');
                        const vTime = saved.p1?.time ?? saved.p1;
                        drawing = new VertLine(chart, series, vTime, saved.options);
                        break;
                    case 'horizontal-line':
                        // Restore HorizontalLine - uses price
                        const { HorizontalLine } = require('@/lib/charts/plugins/horizontal-line');
                        const hPrice = saved.p1?.price ?? saved.p1;
                        drawing = new HorizontalLine(chart, series, hPrice, saved.options);
                        break;
                    case 'text':
                        // Restore TextDrawing
                        const { TextDrawing } = require('@/lib/charts/plugins/text-tool');
                        drawing = new TextDrawing(chart, series, saved.p1.time, saved.p1.price, saved.options);
                        break;
                }

                if (drawing) {
                    // Manually assign the same ID
                    drawing._id = saved.id;
                    series.attachPrimitive(drawing);
                    drawingsRef.current.set(saved.id, drawing);

                    // Track for notifying parent
                    restoredDrawings.push({
                        id: saved.id,
                        type: saved.type,
                        createdAt: saved.createdAt
                    });
                }
            } catch (error) {
                console.error('Failed to restore drawing:', saved, error);
            }
        });

        // Notify parent about all restored drawings
        restoredDrawings.forEach(d => onDrawingCreated(d));

        if (savedDrawings.length > 0) {
            toast.success(`Loaded ${savedDrawings.length} drawing(s)`);
        }
    }, [chart, series, ticker, timeframe, data])


    // Handle Tool Selection
    useEffect(() => {
        if (!chart || !series) return

        // Stop previous tool if any
        if (activeToolRef.current) {
            if (typeof activeToolRef.current.stopDrawing === 'function') {
                activeToolRef.current.stopDrawing()
            }
            activeToolRef.current = null
        }

        if (selectedTool === 'cursor') {
            return
        }

        let ToolClass: any
        switch (selectedTool) {
            case 'trend-line':
                ToolClass = TrendLineTool
                break
            case 'fibonacci':
                ToolClass = FibonacciTool
                break
            case 'rectangle':
                ToolClass = RectangleDrawingTool
                break
            case 'vertical-line':
                ToolClass = VertLineTool
                break
            case 'horizontal-line':
                const { HorizontalLineTool } = require('@/lib/charts/plugins/horizontal-line');
                ToolClass = HorizontalLineTool
                break
            case 'text':
                const { TextTool } = require('@/lib/charts/plugins/text-tool');
                ToolClass = TextTool
                break;
        }

        if (ToolClass) {
            console.log('Instantiating tool:', selectedTool);
            // Prepare magnet options for tools that support it
            const magnetOptions = selectedTool !== 'vertical-line' && selectedTool !== 'horizontal-line' && selectedTool !== 'text'
                ? { magnetMode, ohlcData: data }
                : undefined;
            const tool = new ToolClass(chart, series, (drawing: any) => {
                console.log('Drawing created callback triggered', drawing);
                // Store drawing instance
                const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;

                if (id) {
                    console.log('Registering drawing with ID:', id);
                    drawingsRef.current.set(id, drawing)

                    // If it's a new Text tool (or generic if we want), select it and open properties
                    if (selectedTool === 'text') {
                        setSelectedDrawingId(id);
                        selectedDrawingRef.current = drawing;
                        if (drawing.setSelected) drawing.setSelected(true);

                        // Open modal immediately for text editing
                        setSelectedDrawingOptions(drawing.options ? drawing.options() : {});
                        setSelectedDrawingType('text');
                        setPropertiesModalOpen(true);
                    }

                    // Serialize and save to storage
                    // Handle different drawing types appropriately
                    let serialized: SerializedDrawing;
                    if (selectedTool === 'vertical-line') {
                        // VertLine uses _time, not _p1/_p2
                        serialized = {
                            id,
                            type: selectedTool as any,
                            p1: { time: drawing._time, price: 0 },
                            p2: { time: drawing._time, price: 0 },
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else if (selectedTool === 'horizontal-line') {
                        // HorizontalLine uses _price
                        serialized = {
                            id,
                            type: selectedTool as any,
                            p1: { time: 0, price: drawing._price },
                            p2: { time: 0, price: drawing._price },
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else if (selectedTool === 'text') {
                        serialized = {
                            id,
                            type: selectedTool as any,
                            p1: { time: drawing._time, price: drawing._price },
                            p2: { time: drawing._time, price: drawing._price }, // p2 redundant
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else {
                        serialized = {
                            id,
                            type: selectedTool as any,
                            p1: drawing._p1,
                            p2: drawing._p2,
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    }
                    DrawingStorage.addDrawing(ticker, timeframe, serialized);
                    toast.success(`Drawing saved`);

                    // Notify parent
                    onDrawingCreated({
                        id: id,
                        type: selectedTool as any,
                        createdAt: Date.now()
                    })
                } else {
                    console.error('Drawing created but no ID found', drawing);
                }

                // Reset to cursor after drawing
                onToolSelect('cursor')
            }, magnetOptions)

            tool.startDrawing()
            activeToolRef.current = tool
        }

    }, [selectedTool, chart, series, onToolSelect, onDrawingCreated, magnetMode, data])

    const [propertiesModalOpen, setPropertiesModalOpen] = useState(false)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)
    const selectedDrawingRef = useRef<any>(null)

    // Context menu state
    const [contextMenu, setContextMenu] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false })

    // Open settings from context menu
    const openDrawingSettings = () => {
        if (selectedDrawingRef.current) {
            const drawing = selectedDrawingRef.current;
            setSelectedDrawingOptions(drawing.options ? drawing.options() : {});

            const className = drawing.constructor?.name;
            let drawingType = 'Drawing';
            if (className === 'TrendLine') drawingType = 'trend-line';
            else if (className === 'Rectangle') drawingType = 'rectangle';
            else if (className === 'FibonacciRetracement') drawingType = 'fibonacci';
            else if (className === 'VertLine') drawingType = 'vertical-line';

            setSelectedDrawingType(drawingType);
            setPropertiesModalOpen(true);
        }
        setContextMenu({ ...contextMenu, visible: false });
    };

    // Delete from context menu
    const deleteSelectedDrawing = () => {
        if (selectedDrawingRef.current && series) {
            const drawing = selectedDrawingRef.current;
            const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;

            series.detachPrimitive(drawing);
            drawingsRef.current.delete(id);
            DrawingStorage.deleteDrawing(ticker, timeframe, id);

            if (onDrawingDeleted) {
                onDrawingDeleted(id);
            }

            deselectDrawing();
            toast.success('Drawing deleted');
        }
        setContextMenu({ ...contextMenu, visible: false });
    };

    // Deselect drawing helper
    const deselectDrawing = () => {
        if (selectedDrawingRef.current?.setSelected) {
            selectedDrawingRef.current.setSelected(false);
        }
        selectedDrawingRef.current = null;
        setSelectedDrawingId(null);
    };

    // Handle Delete key to remove selected drawing
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.key === 'Delete' || e.key === 'Backspace') && selectedDrawingRef.current && series) {
                const drawing = selectedDrawingRef.current;
                const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;

                // Detach and remove from map
                series.detachPrimitive(drawing);
                drawingsRef.current.delete(id);

                // Remove from storage
                DrawingStorage.deleteDrawing(ticker, timeframe, id);

                // Notify parent to update Object Tree
                if (onDrawingDeleted) {
                    onDrawingDeleted(id);
                }

                // Deselect
                deselectDrawing();

                toast.success('Drawing deleted');
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [series, ticker, timeframe, onDrawingDeleted]);

    // Handle Chart Clicks for Selection and Double Click
    useEffect(() => {
        if (!chart || !series) return

        const clickHandler = (param: any) => {
            if (!param.point) return;

            // Iterate over drawings to check for hit
            let hitDrawing: any = null
            let hitInfo: any = null

            for (const [id, drawing] of drawingsRef.current.entries()) {
                if (drawing.hitTest) {
                    const hit = drawing.hitTest(param.point.x, param.point.y)
                    if (hit) {
                        hitDrawing = drawing
                        hitInfo = hit
                        break
                    }
                }
            }

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;

                // Deselect previous drawing if different
                if (selectedDrawingRef.current && selectedDrawingRef.current !== hitDrawing) {
                    if (selectedDrawingRef.current.setSelected) {
                        selectedDrawingRef.current.setSelected(false);
                    }
                }

                // Select new drawing
                if (hitDrawing.setSelected) {
                    hitDrawing.setSelected(true);
                }
                selectedDrawingRef.current = hitDrawing;
                setSelectedDrawingId(id);

                const now = Date.now()
                const lastClick = lastClickRef.current
                const lastClickId = lastClickIdRef.current

                // Double Click Logic (Threshold 800ms)
                if (now - lastClick < 800 && lastClickId === id) {
                    setSelectedDrawingOptions(hitDrawing.options ? hitDrawing.options() : {})

                    // Determine drawing type from class name
                    const className = hitDrawing.constructor?.name;
                    let drawingType = 'Drawing';
                    if (className === 'TrendLine') drawingType = 'trend-line';
                    else if (className === 'Rectangle') drawingType = 'rectangle';
                    else if (className === 'FibonacciRetracement') drawingType = 'fibonacci';
                    else if (className === 'VertLine') drawingType = 'vertical-line';
                    else if (className === 'HorizontalLine') drawingType = 'horizontal-line';
                    else if (className === 'TextDrawing') drawingType = 'text';

                    setSelectedDrawingType(drawingType)
                    setPropertiesModalOpen(true)
                }

                lastClickRef.current = now
                lastClickIdRef.current = id
            } else {
                // Click on empty space - deselect
                deselectDrawing();
            }
        }

        chart.subscribeClick(clickHandler)

        return () => {
            chart.unsubscribeClick(clickHandler)
        }
    }, [chart, series])

    // Drag state refs
    const isDraggingRef = useRef(false)
    const dragInfoRef = useRef<{ hitType: string; startPoint: { x: number; y: number }; startP1: any; startP2: any } | null>(null)

    // Handle Drag Operations for resizing/moving drawings
    useEffect(() => {
        if (!chartContainerRef.current || !chart || !series) return

        const container = chartContainerRef.current

        const handleMouseDown = (e: MouseEvent) => {
            if (!selectedDrawingRef.current) return

            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            const hit = selectedDrawingRef.current.hitTest?.(x, y)
            if (hit && hit.hitType) {
                isDraggingRef.current = true
                dragInfoRef.current = {
                    hitType: hit.hitType,
                    startPoint: { x, y },
                    startP1: selectedDrawingRef.current._p1 ? { ...selectedDrawingRef.current._p1 } : null,
                    startP2: selectedDrawingRef.current._p2 ? { ...selectedDrawingRef.current._p2 } : null
                }

                // Disable chart scrolling/panning during drag
                chart.applyOptions({
                    handleScroll: false,
                    handleScale: false
                })

                e.preventDefault()
                e.stopPropagation()
            }
        }

        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current || !dragInfoRef.current || !selectedDrawingRef.current) return

            e.preventDefault()
            e.stopPropagation()

            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            const dx = x - dragInfoRef.current.startPoint.x
            const dy = y - dragInfoRef.current.startPoint.y

            const drawing = selectedDrawingRef.current
            const { hitType, startP1, startP2 } = dragInfoRef.current

            const timeScale = chart.timeScale()

            // Helper: Find snap price if magnet mode is enabled
            const findSnapPrice = (time: any, price: number): number => {
                if (magnetMode === 'off' || !data || data.length === 0) return price;

                // Find the bar at this time
                const bar = data.find((b: any) => b.time === time);
                if (!bar) return price;

                const ohlcValues = [bar.open, bar.high, bar.low, bar.close];
                let closest = ohlcValues[0];
                let minDist = Math.abs(price - closest);

                for (const val of ohlcValues) {
                    const dist = Math.abs(price - val);
                    if (dist < minDist) {
                        minDist = dist;
                        closest = val;
                    }
                }

                // For 'weak' mode, only snap if within threshold
                if (magnetMode === 'weak') {
                    const priceRange = bar.high - bar.low;
                    const threshold = priceRange * 0.3;
                    if (minDist > threshold) return price;
                }

                return closest;
            };

            const coordToTime = (baseTime: any, pixelDelta: number) => {
                const baseCoord = timeScale.timeToCoordinate(baseTime) as number
                return timeScale.coordinateToTime(baseCoord + pixelDelta)
            }
            const coordToPrice = (basePrice: number, pixelDelta: number, time?: any) => {
                const baseCoord = series.priceToCoordinate(basePrice) as number
                const rawPrice = series.coordinateToPrice(baseCoord + pixelDelta) as number
                if (rawPrice === null) return null
                return time ? findSnapPrice(time, rawPrice) : rawPrice
            }

            // For Rectangle corner/edge handles, we need to update both points appropriately
            if (drawing.constructor?.name === 'Rectangle') {
                const minTime = Math.min(startP1.time, startP2.time)
                const maxTime = Math.max(startP1.time, startP2.time)
                const minPrice = Math.min(startP1.price, startP2.price)
                const maxPrice = Math.max(startP1.price, startP2.price)

                let newP1 = { ...startP1 }
                let newP2 = { ...startP2 }

                if (hitType === 'body' || hitType === 'center') {
                    // Move entire rectangle
                    const newT1 = coordToTime(startP1.time, dx)
                    const newT2 = coordToTime(startP2.time, dx)
                    const newPr1 = coordToPrice(startP1.price, dy, newT1)
                    const newPr2 = coordToPrice(startP2.price, dy, newT2)
                    if (newT1 && newT2 && newPr1 !== null && newPr2 !== null) {
                        newP1 = { time: newT1, price: newPr1 as number }
                        newP2 = { time: newT2, price: newPr2 as number }
                    }
                } else if (hitType === 'tl') {
                    const newT = coordToTime(minTime, dx)
                    const newPr = coordToPrice(maxPrice, dy, newT)
                    if (newT && newPr !== null) {
                        newP1 = { time: newT, price: newPr as number }
                        newP2 = { time: maxTime as any, price: minPrice }
                    }
                } else if (hitType === 'br') {
                    const newT = coordToTime(maxTime, dx)
                    const newPr = coordToPrice(minPrice, dy, newT)
                    if (newT && newPr !== null) {
                        newP1 = { time: minTime as any, price: maxPrice }
                        newP2 = { time: newT, price: newPr as number }
                    }
                } else if (hitType === 'tr') {
                    const newT = coordToTime(maxTime, dx)
                    const newPr = coordToPrice(maxPrice, dy, newT)
                    if (newT && newPr !== null) {
                        newP1 = { time: minTime as any, price: minPrice }
                        newP2 = { time: newT, price: newPr as number }
                    }
                } else if (hitType === 'bl') {
                    const newT = coordToTime(minTime, dx)
                    const newPr = coordToPrice(minPrice, dy, newT)
                    if (newT && newPr !== null) {
                        newP1 = { time: newT, price: newPr as number }
                        newP2 = { time: maxTime as any, price: maxPrice }
                    }
                } else if (hitType === 't') {
                    const newPr = coordToPrice(maxPrice, dy, minTime)
                    if (newPr !== null) {
                        newP1 = { time: minTime as any, price: newPr as number }
                        newP2 = { time: maxTime as any, price: minPrice }
                    }
                } else if (hitType === 'b') {
                    const newPr = coordToPrice(minPrice, dy, maxTime)
                    if (newPr !== null) {
                        newP1 = { time: minTime as any, price: maxPrice }
                        newP2 = { time: maxTime as any, price: newPr as number }
                    }
                } else if (hitType === 'l') {
                    const newT = coordToTime(minTime, dx)
                    if (newT) {
                        newP1 = { time: newT, price: maxPrice }
                        newP2 = { time: maxTime as any, price: minPrice }
                    }
                } else if (hitType === 'r') {
                    const newT = coordToTime(maxTime, dx)
                    if (newT) {
                        newP1 = { time: minTime as any, price: maxPrice }
                        newP2 = { time: newT, price: minPrice }
                    }
                }

                if (drawing.updatePoints) {
                    drawing.updatePoints(newP1, newP2)
                }
            } else if (selectedDrawingType === 'horizontal-line') {
                // Horizontal Line - only Y/Price changes
                const rawPrice = series.coordinateToPrice(
                    (series.priceToCoordinate(startP1.price) as number) + dy
                ) as number

                if (rawPrice !== null) {
                    const newPrice = findSnapPrice(null, rawPrice); // Magnet for price? Only if needed. Start with null time. 
                    // Actually findSnapPrice likely requires time to match bar? 
                    // Horizontal line snaps to High/Low of bars nearby? 
                    // For now, let's just use rawPrice or simple price magnet if we can infer time. 
                    // Simpler: Just rawPrice for now, add PriceMagnet later if requested.

                    const newP = { price: newPrice };
                    if (drawing.updatePoints) {
                        drawing.updatePoints(newP);
                    }
                }
            } else if (selectedDrawingType === 'text') {
                // Text Tool - moves like a point (Time/Price)
                const newTime = coordToTime(startP1.time, dx);
                // Disable magnet for text: do not pass time to coordToPrice
                const newPrice = coordToPrice(startP1.price, dy);

                if (newTime && newPrice !== null) {
                    const newP = { time: newTime, price: newPrice };
                    if (drawing.updatePoints) {
                        drawing.updatePoints(newP);
                    }
                }
            } else {
                // TrendLine, Fibonacci - simple two-point handling
                if (hitType === 'body' && startP1 && startP2 && drawing.updatePoints) {
                    const newP1Time = timeScale.coordinateToTime(
                        (timeScale.timeToCoordinate(startP1.time) as number) + dx
                    )
                    const newP2Time = timeScale.coordinateToTime(
                        (timeScale.timeToCoordinate(startP2.time) as number) + dx
                    )
                    const rawP1Price = series.coordinateToPrice(
                        (series.priceToCoordinate(startP1.price) as number) + dy
                    ) as number
                    const rawP2Price = series.coordinateToPrice(
                        (series.priceToCoordinate(startP2.price) as number) + dy
                    ) as number

                    if (newP1Time && newP2Time && rawP1Price !== null && rawP2Price !== null) {
                        const newP1Price = findSnapPrice(newP1Time, rawP1Price)
                        const newP2Price = findSnapPrice(newP2Time, rawP2Price)
                        drawing.updatePoints(
                            { time: newP1Time, price: newP1Price },
                            { time: newP2Time, price: newP2Price }
                        )
                    }
                } else if (hitType === 'p1' && startP1 && startP2 && drawing.updatePoints) {
                    const newP1Time = timeScale.coordinateToTime(
                        (timeScale.timeToCoordinate(startP1.time) as number) + dx
                    )
                    const rawP1Price = series.coordinateToPrice(
                        (series.priceToCoordinate(startP1.price) as number) + dy
                    ) as number

                    if (newP1Time && rawP1Price !== null) {
                        const newP1Price = findSnapPrice(newP1Time, rawP1Price)
                        drawing.updatePoints(
                            { time: newP1Time, price: newP1Price },
                            startP2
                        )
                    }
                } else if (hitType === 'p2' && startP2 && (drawing.updateEnd || drawing.updatePoints)) {
                    const newP2Time = timeScale.coordinateToTime(
                        (timeScale.timeToCoordinate(startP2.time) as number) + dx
                    )
                    const rawP2Price = series.coordinateToPrice(
                        (series.priceToCoordinate(startP2.price) as number) + dy
                    ) as number

                    if (newP2Time && rawP2Price !== null) {
                        const newP2Price = findSnapPrice(newP2Time, rawP2Price)
                        if (drawing.updateEnd) {
                            drawing.updateEnd({ time: newP2Time, price: newP2Price })
                        } else if (drawing.updatePoints) {
                            drawing.updatePoints(startP1, { time: newP2Time, price: newP2Price })
                        }
                    }
                }
            }
        }

        const handleMouseUp = () => {
            if (isDraggingRef.current) {
                // Re-enable chart scrolling
                chart.applyOptions({
                    handleScroll: true,
                    handleScale: true
                })

                if (selectedDrawingRef.current) {
                    // Save updated position to storage
                    const drawing = selectedDrawingRef.current
                    const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id
                    const className = drawing.constructor?.name

                    let drawingType = 'trend-line'
                    if (className === 'Rectangle') drawingType = 'rectangle'
                    else if (className === 'FibonacciRetracement') drawingType = 'fibonacci'
                    else if (className === 'VertLine') drawingType = 'vertical-line'
                    else if (className === 'HorizontalLine') drawingType = 'horizontal-line'
                    else if (className === 'TextDrawing') drawingType = 'text'

                    const serialized: SerializedDrawing = {
                        id,
                        type: drawingType as any,
                        p1: drawing._p1,
                        p2: drawing._p2, // Text/Horizontal/Vert will return duplicate/dummy p2 via getter
                        options: drawing._options,
                        createdAt: Date.now()
                    }
                    DrawingStorage.updateDrawing(ticker, timeframe, id, serialized)
                }
            }

            isDraggingRef.current = false
            dragInfoRef.current = null
        }

        // Use capture phase for mousedown to intercept before chart
        container.addEventListener('mousedown', handleMouseDown, true)
        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('mouseup', handleMouseUp)

        return () => {
            container.removeEventListener('mousedown', handleMouseDown, true)
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
        }
    }, [chart, series, ticker, timeframe, magnetMode, data])

    const handlePropertiesSave = (newOptions: any) => {
        if (selectedDrawingId) {
            const drawing = drawingsRef.current.get(selectedDrawingId)
            if (drawing && drawing.applyOptions) {
                drawing.applyOptions(newOptions)
            }
        }
    }

    // Handle right-click context menu
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const container = chartContainerRef.current;

        const handleContextMenu = (e: MouseEvent) => {
            if (!selectedDrawingRef.current) return;

            const rect = container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // Check if right-click is on selected drawing
            const hit = selectedDrawingRef.current.hitTest?.(x, y);
            if (hit) {
                e.preventDefault();
                setContextMenu({ x: e.clientX, y: e.clientY, visible: true });
            }
        };

        const handleClickOutside = () => {
            setContextMenu(prev => ({ ...prev, visible: false }));
        };

        container.addEventListener('contextmenu', handleContextMenu);
        window.addEventListener('click', handleClickOutside);

        return () => {
            container.removeEventListener('contextmenu', handleContextMenu);
            window.removeEventListener('click', handleClickOutside);
        };
    }, []);

    return (
        <div className="relative w-full h-full">
            <div
                ref={chartContainerRef}
                className="w-full h-full"
            />
            <PropertiesModal
                isOpen={propertiesModalOpen}
                onClose={() => setPropertiesModalOpen(false)}
                drawingType={selectedDrawingType}
                initialOptions={selectedDrawingOptions}
                onSave={handlePropertiesSave}
            />

            {/* Context Menu */}
            {contextMenu.visible && (
                <div
                    className="fixed bg-zinc-800 border border-zinc-700 rounded-md shadow-xl py-1 z-50 min-w-[160px]"
                    style={{ left: contextMenu.x, top: contextMenu.y }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <button
                        className="w-full px-4 py-2 text-left text-sm text-zinc-200 hover:bg-zinc-700 flex items-center gap-2"
                        onClick={openDrawingSettings}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        Settings...
                    </button>
                    <div className="border-t border-zinc-700 my-1" />
                    <button
                        className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-zinc-700 flex items-center gap-2"
                        onClick={deleteSelectedDrawing}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        Remove
                        <span className="ml-auto text-zinc-500 text-xs">Del</span>
                    </button>
                </div>
            )}
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
