"use client"

import { useEffect, useRef, useState } from "react"
import { useChart } from "@/hooks/use-chart"
import { Button } from "@/components/ui/button"
import { TrendLineTool } from "@/lib/charts/plugins/trend-line"

export function ChartContainer() {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const { chart, series } = useChart(chartContainerRef)
    const [activeTool, setActiveTool] = useState<string | null>(null)
    const toolRef = useRef<any>(null)

    useEffect(() => {
        if (!series) return

        // Dummy Data
        series.setData([
            { time: '2018-12-22', open: 75.16, high: 82.84, low: 36.16, close: 45.72 },
            { time: '2018-12-23', open: 45.12, high: 53.90, low: 45.12, close: 48.09 },
            { time: '2018-12-24', open: 60.71, high: 60.71, low: 53.39, close: 59.29 },
            { time: '2018-12-25', open: 68.26, high: 68.26, low: 59.04, close: 60.50 },
            { time: '2018-12-26', open: 67.71, high: 105.85, low: 66.67, close: 91.04 },
            { time: '2018-12-27', open: 91.04, high: 121.40, low: 82.70, close: 111.40 },
            { time: '2018-12-28', open: 111.51, high: 142.83, low: 103.34, close: 131.25 },
            { time: '2018-12-29', open: 131.33, high: 151.17, low: 77.68, close: 96.43 },
            { time: '2018-12-30', open: 106.33, high: 110.20, low: 90.39, close: 98.10 },
            { time: '2018-12-31', open: 109.87, high: 114.69, low: 85.66, close: 111.26 },
        ])
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
            </div>
            <div
                ref={chartContainerRef}
                className="w-full h-[600px]"
            />
        </div>
    )
}
