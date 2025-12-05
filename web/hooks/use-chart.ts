"use client"

import { useEffect, useRef, useState } from "react"
import { createChart, ColorType, CrosshairMode, IChartApi, ISeriesApi, CandlestickSeries } from "lightweight-charts"

export function useChart(containerRef: React.RefObject<HTMLDivElement>) {
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null)
    const [seriesInstance, setSeriesInstance] = useState<ISeriesApi<"Candlestick"> | null>(null)

    useEffect(() => {
        if (!containerRef.current) return

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#1e222d' },
                textColor: '#d1d4dc',
            },
            grid: {
                vertLines: { color: '#2a2e39' },
                horzLines: { color: '#2a2e39' },
            },
            width: containerRef.current.clientWidth,
            height: 500,
            autoSize: true,
            timeScale: {
                timeVisible: true,
                rightOffset: 5,
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
        })

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        })

        setChartInstance(chart)
        setSeriesInstance(candlestickSeries)

        return () => {
            chart.remove()
            setChartInstance(null)
            setSeriesInstance(null)
        }
    }, [containerRef])

    return {
        chart: chartInstance,
        series: seriesInstance,
    }
}
