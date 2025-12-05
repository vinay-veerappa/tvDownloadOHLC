"use client"

import { useEffect, useRef, useState } from "react"
import {
    createChart,
    ColorType,
    CrosshairMode,
    IChartApi,
    ISeriesApi,
    CandlestickSeries,
    BarSeries,
    LineSeries,
    AreaSeries
} from "lightweight-charts"

export function useChart(containerRef: React.RefObject<HTMLDivElement>, style: string = 'candles') {
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null)
    const [seriesInstance, setSeriesInstance] = useState<ISeriesApi<any> | null>(null)

    // Create Chart Instance
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

        setChartInstance(chart)

        const handleResize = () => {
            if (containerRef.current) {
                chart.applyOptions({ width: containerRef.current.clientWidth })
            }
        }

        const resizeObserver = new ResizeObserver(handleResize)
        resizeObserver.observe(containerRef.current)

        return () => {
            resizeObserver.disconnect()
            chart.remove()
            setChartInstance(null)
        }
    }, [containerRef])

    // Manage Series based on Style
    useEffect(() => {
        if (!chartInstance) return

        let newSeries: ISeriesApi<any>

        const commonOptions = {
            upColor: '#26a69a',
            downColor: '#ef5350',
        }

        switch (style) {
            case 'bars':
                newSeries = chartInstance.addSeries(BarSeries, {
                    ...commonOptions,
                    thinBars: false,
                })
                break
            case 'line':
                newSeries = chartInstance.addSeries(LineSeries, {
                    color: '#2962FF',
                    lineWidth: 2,
                })
                break
            case 'area':
                newSeries = chartInstance.addSeries(AreaSeries, {
                    topColor: 'rgba(41, 98, 255, 0.3)',
                    bottomColor: 'rgba(41, 98, 255, 0)',
                    lineColor: '#2962FF',
                    lineWidth: 2,
                })
                break
            case 'heiken-ashi':
            case 'candles':
            default:
                newSeries = chartInstance.addSeries(CandlestickSeries, {
                    ...commonOptions,
                    borderVisible: false,
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350',
                })
                break
        }

        setSeriesInstance(newSeries)

        return () => {
            if (chartInstance && newSeries) {
                try {
                    chartInstance.removeSeries(newSeries)
                } catch (e) {
                    // Ignore cleanup errors
                }
            }
            setSeriesInstance(null)
        }
    }, [chartInstance, style])

    return {
        chart: chartInstance,
        series: seriesInstance,
    }
}
