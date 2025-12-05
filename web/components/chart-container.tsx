"use client"

import { useEffect, useRef, forwardRef, useImperativeHandle } from "react"
import { useChart } from "@/hooks/use-chart"
import { getChartData } from "@/actions/data-actions"
import { DrawingTool } from "./left-toolbar"
import { Drawing } from "./right-sidebar"
import { TrendLineTool } from "@/lib/charts/plugins/trend-line"
import { FibonacciTool } from "@/lib/charts/plugins/fibonacci"
import { RectangleDrawingTool } from "@/lib/charts/plugins/rectangle"
import { VertLineTool } from "@/lib/charts/plugins/vertical-line"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"

import { useTradeContext } from "@/components/journal/trade-context"

interface ChartContainerProps {
    ticker: string
    timeframe: string
    style: string
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    onDrawingCreated: (drawing: Drawing) => void
}

export interface ChartContainerRef {
    deleteDrawing: (id: string) => void
}

export const ChartContainer = forwardRef<ChartContainerRef, ChartContainerProps>(({ ticker, timeframe, style, selectedTool, onToolSelect, onDrawingCreated }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const { chart, series } = useChart(chartContainerRef as React.RefObject<HTMLDivElement>, style)
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
            }
        }
    }))


    // Load Data
    useEffect(() => {
        if (!series) return

        async function loadData() {
            try {
                const result = await getChartData(ticker, timeframe)
                if (result.success && result.data && series) {
                    const data = style === 'heiken-ashi'
                        ? calculateHeikenAshi(result.data as any)
                        : result.data

                    series.setData(data as any)
                    chart?.timeScale().fitContent()
                }
            } catch (e) {
                console.error("Failed to load data:", e)
            }
        }
        loadData()
    }, [series, ticker, timeframe, chart, style])

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

                    // Notify parent
                    onDrawingCreated({
                        id: id,
                        type: selectedTool as any, // Cast to avoid type issues if needed
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

    return (
        <div className="relative w-full h-full">
            <div
                ref={chartContainerRef}
                className="w-full h-full"
            />
        </div>
    )
})

ChartContainer.displayName = "ChartContainer"
