"use client"

import { useEffect, useRef } from "react"
import { useChart } from "@/hooks/use-chart"
import { getChartData } from "@/actions/data-actions"
import { DrawingTool } from "./left-toolbar"
import { TrendLineTool } from "@/lib/charts/plugins/trend-line"
import { FibonacciTool } from "@/lib/charts/plugins/fibonacci"
import { RectangleDrawingTool } from "@/lib/charts/plugins/rectangle"
import { VertLineTool } from "@/lib/charts/plugins/vertical-line"
import { useTradeContext } from "@/components/journal/trade-context"

interface ChartContainerProps {
    ticker: string
    timeframe: string
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
}

export function ChartContainer({ ticker, timeframe, selectedTool, onToolSelect }: ChartContainerProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const { chart, series } = useChart(chartContainerRef)
    const activeToolRef = useRef<any>(null)
    const { openTradeDialog } = useTradeContext()

    // Load Data
    useEffect(() => {
        if (!series) return

        async function loadData() {
            try {
                const result = await getChartData(ticker, timeframe)
                if (result.success && result.data && series) {
                    series.setData(result.data)
                    chart?.timeScale().fitContent()
                }
            } catch (e) {
                console.error("Failed to load data:", e)
            }
        }
        loadData()
    }, [series, ticker, timeframe, chart])

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
            const tool = new ToolClass(chart, series, (drawing: any) => {
                console.log('Drawing created:', drawing)
                // Reset to cursor after drawing
                onToolSelect('cursor')
            })

            tool.startDrawing()
            activeToolRef.current = tool
        }

    }, [selectedTool, chart, series, onToolSelect])

    return (
        <div className="relative w-full h-full">
            <div
                ref={chartContainerRef}
                className="w-full h-full"
            />
        </div>
    )
}
