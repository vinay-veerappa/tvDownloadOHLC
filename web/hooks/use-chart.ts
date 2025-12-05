"use client"

import { useEffect, useRef, useState } from "react"
import { createChart, ColorType, CrosshairMode, IChartApi, ISeriesApi, CandlestickSeries } from "lightweight-charts"

export function useChart(containerRef: React.RefObject<HTMLDivElement>) {
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)

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

        chartRef.current = chart
        seriesRef.current = candlestickSeries

        return () => {
            chart.remove()
        }
    }, [containerRef])

    return {
        chart: chartRef.current,
        series: seriesRef.current,
    }
}
