"use client"

import { useEffect, useRef, useState, useMemo } from "react"
import {
    createChart,
    ColorType,
    CrosshairMode,
    IChartApi,
    ISeriesApi,
    CandlestickSeries,
    BarSeries,
    LineSeries,
    AreaSeries,
    createSeriesMarkers
} from "lightweight-charts"

import { calculateSMA, calculateEMA } from "@/lib/charts/indicators"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"
import { AnchoredText } from "@/lib/charts/plugins/anchored-text"
import { SessionHighlighting } from "@/lib/charts/plugins/session-highlighting"

export function useChart(
    containerRef: React.RefObject<HTMLDivElement>,
    style: string = 'candles',
    indicators: string[] = [],
    data: any[] = [],
    markers: any[] = [],
    displayTimezone: string = 'America/New_York'
) {
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null)
    const [seriesInstance, setSeriesInstance] = useState<ISeriesApi<any> | null>(null)

    // Create timezone-aware tick mark formatter
    const formatTimeForTimezone = (time: number) => {
        const date = new Date(time * 1000)
        const tz = displayTimezone === 'local' ? undefined : displayTimezone
        try {
            return date.toLocaleTimeString('en-US', {
                timeZone: tz,
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            })
        } catch {
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
        }
    }

    const formatDateForTimezone = (time: number) => {
        const date = new Date(time * 1000)
        const tz = displayTimezone === 'local' ? undefined : displayTimezone
        try {
            return date.toLocaleDateString('en-US', {
                timeZone: tz,
                month: 'short',
                day: 'numeric'
            })
        } catch {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        }
    }

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
            autoSize: true,
            timeScale: {
                timeVisible: true,
                rightOffset: 5,
                tickMarkFormatter: (time: number) => formatTimeForTimezone(time),
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
        })

        setChartInstance(chart)

        return () => {
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

        if (data.length > 0) {
            const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
            newSeries.setData(chartData)
            chartInstance.timeScale().fitContent()
        }

        return () => {
            if (chartInstance && newSeries) {
                try {
                    chartInstance.removeSeries(newSeries)
                } catch (e) { }
            }
            setSeriesInstance(null)
        }
    }, [chartInstance, style])

    // Update Data when data changes
    useEffect(() => {
        if (!seriesInstance || !data.length) return

        const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
        seriesInstance.setData(chartData)

        if (markers && markers.length > 0) {
            if (typeof createSeriesMarkers === 'function') {
                createSeriesMarkers(seriesInstance as any, markers)
            } else if (typeof (seriesInstance as any).setMarkers === 'function') {
                (seriesInstance as any).setMarkers(markers)
            }
        }
    }, [seriesInstance, data, style, markers])

    const primitivesRef = useRef<any[]>([])
    const indicatorsKey = useMemo(() => JSON.stringify(indicators), [indicators])

    // Manage Data-Dependent Indicators (SMA, EMA)
    useEffect(() => {
        if (!chartInstance || !seriesInstance || !data.length) return

        const currentIndicators: string[] = indicatorsKey ? JSON.parse(indicatorsKey) : []
        const indicatorSeries: ISeriesApi<"Line">[] = []

        currentIndicators.forEach(ind => {
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
            indicatorSeries.forEach(item => {
                try {
                    chartInstance.removeSeries(item)
                } catch (e) { }
            })
        }
    }, [chartInstance, seriesInstance, indicatorsKey, data])

    // Manage Primitives (Sessions, Watermark) - NO data dependency
    useEffect(() => {
        if (!chartInstance || !seriesInstance) return

        const currentIndicators: string[] = indicatorsKey ? JSON.parse(indicatorsKey) : []
        const primitiveItems: Array<{ primitive: any, series: any }> = []
        primitivesRef.current = []

        currentIndicators.forEach(ind => {
            const [type, param] = ind.split(":")

            if (type === 'watermark') {
                const watermark = new AnchoredText(chartInstance, seriesInstance, {
                    text: param || 'Watermark',
                    color: 'rgba(0, 150, 136, 0.5)',
                    font: 'bold 48px Arial',
                    horzAlign: 'center',
                    vertAlign: 'middle'
                });
                seriesInstance.attachPrimitive(watermark);
                primitiveItems.push({ primitive: watermark, series: seriesInstance });
                primitivesRef.current.push(watermark);
            } else if (type === 'sessions') {
                const sessions = new SessionHighlighting();
                seriesInstance.attachPrimitive(sessions);
                primitiveItems.push({ primitive: sessions, series: seriesInstance });
                primitivesRef.current.push(sessions);
            }
        })

        return () => {
            primitiveItems.forEach(item => {
                try {
                    item.series.detachPrimitive(item.primitive);
                } catch (e) { }
            })
        }
    }, [chartInstance, seriesInstance, indicatorsKey]) // NO data dependency!

    // Navigation functions for replay mode
    const scrollToTime = (time: number) => {
        if (!chartInstance) return
        chartInstance.timeScale().scrollToPosition(-5, false)
        // Find logical index for this time
        const timeScale = chartInstance.timeScale()
        timeScale.scrollToRealTime()
        // Then scroll to specific time
        chartInstance.timeScale().setVisibleRange({
            from: time - 3600 * 24, // 1 day before
            to: time + 3600 * 24    // 1 day after
        } as any)
    }

    const scrollByBars = (numBars: number) => {
        if (!chartInstance) return
        const timeScale = chartInstance.timeScale()
        const visibleRange = timeScale.getVisibleLogicalRange()
        if (visibleRange) {
            timeScale.setVisibleLogicalRange({
                from: visibleRange.from + numBars,
                to: visibleRange.to + numBars
            })
        }
    }

    const scrollToStart = () => {
        if (!chartInstance) return
        chartInstance.timeScale().scrollToPosition(10, false)
    }

    const scrollToEnd = () => {
        if (!chartInstance) return
        chartInstance.timeScale().scrollToRealTime()
    }

    const getDataRange = () => {
        if (data.length === 0) return null
        return {
            start: data[0].time,
            end: data[data.length - 1].time,
            totalBars: data.length
        }
    }

    const getVisibleBarIndex = () => {
        if (!chartInstance) return null
        const range = chartInstance.timeScale().getVisibleLogicalRange()
        return range ? Math.floor((range.from + range.to) / 2) : null
    }

    return {
        chart: chartInstance,
        series: seriesInstance,
        primitives: primitivesRef,
        // Navigation functions
        scrollToTime,
        scrollByBars,
        scrollToStart,
        scrollToEnd,
        getDataRange,
        getVisibleBarIndex
    }
}

