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

import { calculateSMA, calculateEMA } from "@/lib/charts/indicators"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"

export function useChart(containerRef: React.RefObject<HTMLDivElement>, style: string = 'candles', indicators: string[] = [], data: any[] = []) {
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

        // Set Data if available
        if (data.length > 0) {
            const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
            newSeries.setData(chartData)
            chartInstance.timeScale().fitContent()
        }

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
    }, [chartInstance, style]) // Re-create series if style changes

    // Update Data when data changes (but style stays same)
    useEffect(() => {
        if (!seriesInstance || !data.length) return

        const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
        seriesInstance.setData(chartData)
    }, [seriesInstance, data, style])


    // Manage Indicators
    useEffect(() => {
        if (!chartInstance || !data.length || !indicators.length) return

        const indicatorSeries: ISeriesApi<"Line">[] = []

        indicators.forEach(ind => {
            // Parse indicator string "type:period" (e.g., "sma:9")
            // If just "sma", default to 9
            const [type, param] = ind.split(":")
            const period = param ? parseInt(param) : 9

            if (type === 'sma') {
                const smaData = calculateSMA(data, period)
                const lineSeries = chartInstance.addSeries(LineSeries, {
                    color: '#2962FF',
                    lineWidth: 1,
                    title: `SMA ${period}`,
                })
                lineSeries.setData(smaData)
                indicatorSeries.push(lineSeries)
            } else if (type === 'ema') {
                const emaData = calculateEMA(data, period)
                const lineSeries = chartInstance.addSeries(LineSeries, {
                    color: '#FF6D00',
                    lineWidth: 1,
                    title: `EMA ${period}`,
                })
                lineSeries.setData(emaData)
                indicatorSeries.push(lineSeries)
            }
        })

        return () => {
            indicatorSeries.forEach(series => {
                try {
                    chartInstance.removeSeries(series)
                } catch (e) { }
            })
        }
    }, [chartInstance, indicators, data])

    return {
        chart: chartInstance,
        series: seriesInstance,
    }
}
