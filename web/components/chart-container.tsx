"use client"

import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react"
import { useChart } from "@/hooks/use-chart"
import { getChartData } from "@/actions/data-actions"
import { DrawingTool } from "./left-toolbar"
import { Drawing } from "./right-sidebar"
import { PropertiesModal } from "./properties-modal"
import { DrawingStorage, SerializedDrawing } from "@/lib/drawing-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"
import { useTradeContext } from "@/components/journal/trade-context"
import { toast } from "sonner"
import { useDrawingManager } from "@/hooks/use-drawing-manager"

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
    selection?: { type: 'drawing' | 'indicator', id: string } | null
    onSelectionChange?: (selection: { type: 'drawing' | 'indicator', id: string } | null) => void
    onDeleteSelection?: () => void
}

export interface ChartContainerRef {
    deleteDrawing: (id: string) => void;
    editDrawing: (id: string) => void;
}

export const ChartContainer = forwardRef<ChartContainerRef, ChartContainerProps>(({ ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, onDrawingDeleted, indicators, markers, magnetMode = 'off', selection, onSelectionChange, onDeleteSelection }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const [data, setData] = useState<any[]>([])
    const { chart, series } = useChart(chartContainerRef as React.RefObject<HTMLDivElement>, style, indicators, data, markers)

    const { openTradeDialog } = useTradeContext()

    // Internal state that should be synced with props if valid
    const selectedDrawingRef = useRef<any>(null)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)

    // Drawing Manager
    const drawingManager = useDrawingManager(
        chart,
        series,
        ticker,
        timeframe,
        onDrawingCreated,
        onDrawingDeleted
    );

    // Sync external selection prop to internal state
    useEffect(() => {
        if (!selection) {
            deselectDrawing();
            return;
        }

        if (selection.type === 'drawing') {
            const drawing = drawingManager.getDrawing(selection.id);
            if (drawing) {
                if (selectedDrawingRef.current && selectedDrawingRef.current !== drawing) {
                    if (selectedDrawingRef.current.setSelected) {
                        selectedDrawingRef.current.setSelected(false);
                    }
                }
                if (drawing.setSelected) {
                    drawing.setSelected(true);
                }
                selectedDrawingRef.current = drawing;
                setSelectedDrawingId(selection.id);
            }
        } else {
            deselectDrawing();
        }
    }, [selection, drawingManager]);

    // UI State
    const [propertiesModalOpen, setPropertiesModalOpen] = useState(false)
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)
    const [contextMenu, setContextMenu] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false })

    // Helper functions
    const deselectDrawing = () => {
        if (selectedDrawingRef.current?.setSelected) {
            selectedDrawingRef.current.setSelected(false);
        }
        selectedDrawingRef.current = null;
        setSelectedDrawingId(null);
    };

    // Open settings from sidebar
    const handleEditDrawing = (id: string) => {
        const drawing = drawingManager.getDrawing(id);
        if (drawing) {
            onSelectionChange?.({ type: 'drawing', id });

            setSelectedDrawingOptions(drawing.options ? drawing.options() : {});

            const drawingType = drawing._type;

            setSelectedDrawingType(drawingType);
            setPropertiesModalOpen(true);
        }
    };

    useImperativeHandle(ref, () => ({
        deleteDrawing: (id: string) => {
            drawingManager.deleteDrawing(id);
        },
        editDrawing: (id: string) => {
            handleEditDrawing(id);
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

    // Load Saved Drawings via Manager
    const { loadDrawings, initiateTool } = drawingManager;
    const hasLoadedDrawingsRef = useRef(false);

    // Reset load state on ticker/timeframe change
    useEffect(() => {
        hasLoadedDrawingsRef.current = false;
    }, [ticker, timeframe]);

    useEffect(() => {
        if (data && data.length > 0 && !hasLoadedDrawingsRef.current) {
            loadDrawings(data);
            hasLoadedDrawingsRef.current = true;
        }
    }, [loadDrawings, ticker, timeframe, data]);


    // Handle Tool Selection with Manager
    useEffect(() => {
        initiateTool(
            selectedTool,
            magnetMode,
            data,
            () => onToolSelect('cursor'),
            (id, drawing) => {
                onSelectionChange?.({ type: 'drawing', id });
                setSelectedDrawingOptions(drawing.options ? drawing.options() : {});
                setSelectedDrawingType('text');
                setPropertiesModalOpen(true);
            }
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedTool, initiateTool, magnetMode, onToolSelect, onSelectionChange]); // Removed data to prevent tool reset


    // Context Menu Logic
    const openDrawingSettings = () => {
        if (selectedDrawingRef.current) {
            const drawing = selectedDrawingRef.current;
            setSelectedDrawingOptions(drawing.options ? drawing.options() : {});

            const drawingType = drawing._type;

            setSelectedDrawingType(drawingType);
            setPropertiesModalOpen(true);
        }
        setContextMenu({ ...contextMenu, visible: false });
    };

    const deleteSelectedDrawing = () => {
        if (onDeleteSelection) {
            onDeleteSelection();
        } else if (selectedDrawingRef.current) {
            const drawing = selectedDrawingRef.current;
            const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;
            drawingManager.deleteDrawing(id);
            deselectDrawing();
        }
        setContextMenu({ ...contextMenu, visible: false });
    };

    // Handle Delete Key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.key === 'Delete' || e.key === 'Backspace')) {
                if (onDeleteSelection) {
                    onDeleteSelection();
                } else if (selectedDrawingRef.current) {
                    const drawing = selectedDrawingRef.current;
                    const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;
                    drawingManager.deleteDrawing(id);
                    deselectDrawing();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onDeleteSelection, drawingManager]);

    // Handle Click (Selection) use Manager hitTest
    useEffect(() => {
        if (!chart || !series) return

        const clickHandler = (param: any) => {
            if (!param.point) return;

            const result = drawingManager.hitTest(param.point.x, param.point.y);
            const hitDrawing = result?.drawing;

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;
                onSelectionChange?.({ type: 'drawing', id });

                const now = Date.now()
                const lastClick = lastClickRef.current
                const lastClickId = lastClickIdRef.current

                if (now - lastClick < 800 && lastClickId === id) {
                    setSelectedDrawingOptions(hitDrawing.options ? hitDrawing.options() : {})

                    const drawingType = hitDrawing._type;

                    setSelectedDrawingType(drawingType)
                    setPropertiesModalOpen(true)
                }

                lastClickRef.current = now
                lastClickIdRef.current = id
            } else {
                deselectDrawing();
            }
        }
        chart.subscribeClick(clickHandler)
        return () => {
            chart.unsubscribeClick(clickHandler)
        }
    }, [chart, series, drawingManager, onSelectionChange]);


    // DRAG LOGIC
    const isDraggingRef = useRef(false)
    const dragInfoRef = useRef<{ hitType: string; startPoint: { x: number; y: number }; startP1: any; startP2: any } | null>(null)

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

            const findSnapPrice = (time: any, price: number): number => {
                if (magnetMode === 'off' || !data || data.length === 0) return price;

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

            if (drawing._type === 'rectangle') {
                const minTime = Math.min(startP1.time, startP2.time)
                const maxTime = Math.max(startP1.time, startP2.time)
                const minPrice = Math.min(startP1.price, startP2.price)
                const maxPrice = Math.max(startP1.price, startP2.price)

                let newP1 = { ...startP1 }
                let newP2 = { ...startP2 }

                if (hitType === 'body' || hitType === 'center') {
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
            } else if (drawing._type === 'horizontal-line') {
                const rawPrice = series.coordinateToPrice(
                    (series.priceToCoordinate(startP1.price) as number) + dy
                ) as number

                if (rawPrice !== null) {
                    const newPrice = rawPrice;
                    const newP = { price: newPrice };
                    if (drawing.updatePoints) {
                        drawing.updatePoints(newP);
                    }
                }
            } else if (drawing._type === 'text') {
                const newTime = coordToTime(startP1.time, dx);
                const newPrice = coordToPrice(startP1.price, dy);

                if (newTime && newPrice !== null) {
                    const newP = { time: newTime, price: newPrice };
                    if (drawing.updatePoints) {
                        drawing.updatePoints(newP);
                    }
                }
            } else if (drawing._type === 'vertical-line') {
                const newTime = coordToTime(startP1.time, dx);
                if (newTime) {
                    const newP = { time: newTime };
                    if (drawing.updatePoints) {
                        drawing.updatePoints(newP);
                    }
                }
            } else {
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
                chart.applyOptions({
                    handleScroll: true,
                    handleScale: true
                })

                if (selectedDrawingRef.current) {
                    const drawing = selectedDrawingRef.current
                    const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id

                    const drawingType = drawing._type;

                    const serialized: SerializedDrawing = {
                        id,
                        type: drawingType as any,
                        p1: drawing._p1,
                        p2: drawing._p2,
                        options: drawing._options,
                        createdAt: Date.now()
                    }
                    DrawingStorage.updateDrawing(ticker, timeframe, id, serialized)
                }
            }

            isDraggingRef.current = false
            dragInfoRef.current = null
        }

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
            const drawing = drawingManager.getDrawing(selectedDrawingId)
            if (drawing && drawing.applyOptions) {
                drawing.applyOptions(newOptions)
                // Persistence handled during create/delete/drag.
                // Property updates might need explicit save to storage?
                // Yes, we should update storage here too.
                const drawingType = drawing._type;

                const serialized: SerializedDrawing = {
                    id: selectedDrawingId,
                    type: drawingType as any,
                    p1: drawing._p1,
                    p2: drawing._p2,
                    options: drawing._options,
                    createdAt: Date.now()
                }
                DrawingStorage.updateDrawing(ticker, timeframe, selectedDrawingId, serialized);
            }
        }
    }


    // Context Menu Effect
    useEffect(() => {
        if (!chartContainerRef.current) return;
        const container = chartContainerRef.current;

        const handleContextMenu = (e: MouseEvent) => {
            if (!selectedDrawingRef.current) return;

            const rect = container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const hit = selectedDrawingRef.current.hitTest?.(x, y);
            if (hit) {
                e.preventDefault();
                setContextMenu({ x: e.clientX - rect.left, y: e.clientY - rect.top, visible: true });
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
        <div ref={chartContainerRef} className="w-full h-full relative" onContextMenu={(e) => {
            // Keep native React onContextMenu as backup or for other interactions if needed
        }}>
            {/* Custom Context Menu */}
            {contextMenu.visible && selectedDrawingId && (
                <div
                    className="absolute bg-popover text-popover-foreground border rounded-md shadow-md p-1 min-w-[150px] z-50 flex flex-col gap-1"
                    style={{ left: contextMenu.x, top: contextMenu.y }}
                >
                    <button className="text-left px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded-sm flex items-center gap-2" onClick={openDrawingSettings}>
                        Settings
                    </button>
                    <div className="border-t my-1" />
                    <button className="text-left px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded-sm flex items-center text-destructive gap-2" onClick={deleteSelectedDrawing}>
                        Delete
                    </button>
                </div>
            )}

            <PropertiesModal
                open={propertiesModalOpen}
                onOpenChange={setPropertiesModalOpen}
                drawingType={selectedDrawingType}
                initialOptions={selectedDrawingOptions}
                onSave={handlePropertiesSave}
            />
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
