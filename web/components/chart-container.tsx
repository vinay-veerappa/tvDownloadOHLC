"use client"

import { useEffect, useRef, useState } from "react"
import { useChart } from "@/hooks/use-chart"
import { Button } from "@/components/ui/button"
import { TrendLineTool } from "@/lib/charts/plugins/trend-line"
import { useTradeContext } from "@/components/journal/trade-context"

import { getChartData } from "@/actions/data-actions"

export function ChartContainer() {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const { chart, series } = useChart(chartContainerRef as React.RefObject<HTMLDivElement>)
    const [activeTool, setActiveTool] = useState<string | null>(null)
    const toolRef = useRef<any>(null)
    const { openTradeDialog } = useTradeContext()

    useEffect(() => {
        if (!series) return

        async function loadData() {
            try {
                const result = await getChartData("ES1", "1D")
                if (result.success && result.data && series) {
                    series.setData(result.data)
                    chart?.timeScale().fitContent()
                }
            } catch (e) {
                console.error("Failed to load data:", e)
            }
        }
        loadData()
    }, [series])

    const handleToolClick = (tool: string) => {
        if (activeTool === tool) {
            // Deactivate
            if (toolRef.current) toolRef.current.stopDrawing()
            toolRef.current = null
            setActiveTool(null)
        } else {
            // Activate
            if (toolRef.current) toolRef.current.stopDrawing()

            if (tool === 'trendline' && chart && series) {
                toolRef.current = new TrendLineTool(chart, series, () => {
                    // Callback when drawing finished
                    setActiveTool(null)
                    toolRef.current = null
                })
                toolRef.current.startDrawing()
                setActiveTool('trendline')
            }
        }
    }

    const handleTradeClick = () => {
        // In a real app, we'd get the last price from the data
        // For now, we'll just use a dummy price or the last one from our dummy data
        const lastPrice = 111.26
        openTradeDialog({
            symbol: "ES", // Hardcoded for now, would come from chart state
            price: lastPrice,
            date: new Date(),
            direction: "LONG"
        })
    }

    return (
        <div className="relative w-full h-full">
            <div className="absolute top-4 left-4 z-10 flex gap-2">
                <Button
                    variant={activeTool === 'trendline' ? "default" : "secondary"}
                    size="sm"
                    onClick={() => handleToolClick('trendline')}
                >
                    Trend Line
                </Button>
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleTradeClick}
                >
                    Trade
                </Button>
            </div>
            <div
                ref={chartContainerRef}
                className="w-full h-[600px]"
            />
        </div>
    )
}
