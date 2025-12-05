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

import { useTradeContext } from "@/components/journal/trade-context"
import { toast } from "sonner"

interface ChartContainerProps {
    ticker: string
    timeframe: string
    style: string
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    onDrawingCreated: (drawing: Drawing) => void
    indicators: string[]
    markers?: any[]
}

export interface ChartContainerRef {
    deleteDrawing: (id: string) => void
}

export const ChartContainer = forwardRef<ChartContainerRef, ChartContainerProps>(({ ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated, indicators, markers }, ref) => {
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
                        const { Fibonacci } = require('@/lib/charts/plugins/fibonacci');
                        drawing = new Fibonacci(chart, series, saved.p1, saved.p2, saved.options);
                        break;
                    case 'vertical-line':
                        // Restore VerticalLine
                        const { VertLine } = require('@/lib/charts/plugins/vertical-line');
                        drawing = new VertLine(chart, series, saved.p1, saved.options);
                        break;
                }

                if (drawing) {
                    // Manually assign the same ID
                    drawing._id = saved.id;
                    series.attachPrimitive(drawing);
                    drawingsRef.current.set(saved.id, drawing);
                }
            } catch (error) {
                console.error('Failed to restore drawing:', saved, error);
            }
        });

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
        }

        if (ToolClass) {
            console.log('Instantiating tool:', selectedTool);
            const tool = new ToolClass(chart, series, (drawing: any) => {
                console.log('Drawing created callback triggered', drawing);
                // Store drawing instance
                const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;

                if (id) {
                    console.log('Registering drawing with ID:', id);
                    drawingsRef.current.set(id, drawing)

                    // Serialize and save to storage
                    const serialized: SerializedDrawing = {
                        id,
                        type: selectedTool as any,
                        p1: drawing._p1,
                        p2: drawing._p2,
                        options: drawing._options,
                        createdAt: Date.now()
                    };
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
            })

            tool.startDrawing()
            activeToolRef.current = tool
        }

    }, [selectedTool, chart, series, onToolSelect, onDrawingCreated])

    const [propertiesModalOpen, setPropertiesModalOpen] = useState(false)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)

    // Handle Chart Clicks for Selection and Double Click
    useEffect(() => {
        if (!chart || !series) return

        const clickHandler = (param: any) => {
            if (!param.point) return;

            // Iterate over drawings to check for hit
            let hitDrawing: any = null

            for (const [id, drawing] of drawingsRef.current.entries()) {
                if (drawing.hitTest) {
                    const hit = drawing.hitTest(param.point.x, param.point.y)
                    if (hit) {
                        hitDrawing = drawing
                        break
                    }
                }
            }

            if (hitDrawing) {
                const id = typeof hitDrawing.id === 'function' ? hitDrawing.id() : hitDrawing.id;

                const now = Date.now()
                const lastClick = lastClickRef.current
                const lastClickId = lastClickIdRef.current

                // Double Click Logic (Threshold increased to 800ms)
                if (now - lastClick < 800 && lastClickId === id) {
                    setSelectedDrawingId(id)
                    setSelectedDrawingOptions(hitDrawing.options ? hitDrawing.options() : {})
                    setSelectedDrawingType('Drawing')
                    setPropertiesModalOpen(true)
                    toast.dismiss() // Dismiss selection toast
                } else {
                    // Single Click Logic
                    toast.success(`Selected: ${selectedTool === 'vertical-line' ? 'Vertical Line' : 'Drawing'}`)
                }

                lastClickRef.current = now
                lastClickIdRef.current = id
            }
        }

        chart.subscribeClick(clickHandler)

        return () => {
            chart.unsubscribeClick(clickHandler)
        }
    }, [chart, series])

    const handlePropertiesSave = (newOptions: any) => {
        if (selectedDrawingId) {
            const drawing = drawingsRef.current.get(selectedDrawingId)
            if (drawing && drawing.applyOptions) {
                drawing.applyOptions(newOptions)
            }
        }
    }

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
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
