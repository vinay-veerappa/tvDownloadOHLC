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

import { calculateSMA, calculateEMA, calculateRSI, calculateMACD } from "@/lib/charts/indicators"
import { INDICATOR_DEFINITIONS } from "@/lib/charts/indicator-config"
import { HistogramSeries } from "lightweight-charts"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"
import { AnchoredText } from "@/lib/charts/plugins/anchored-text"
import { SessionHighlighting } from "@/lib/charts/plugins/session-highlighting"
import { calculateIndicators, toLineSeriesData } from "@/lib/indicator-api"

import { useTheme } from "next-themes"

export function useChart(
    containerRef: React.RefObject<HTMLDivElement | null>,
    style: string = 'candles',
    indicators: string[] = [],
    data: any[] = [],
    markers: any[] = [],
    displayTimezone: string = 'America/New_York'
) {
    const { resolvedTheme } = useTheme()
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null)
    const [seriesInstance, setSeriesInstance] = useState<ISeriesApi<any> | null>(null)

    // Track chart lifecycle to prevent "disposed" errors in Strict Mode
    const chartRef = useRef<IChartApi | null>(null)
    const isDisposedRef = useRef(false)

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
        // Wait for theme to resolve to prevent flash during hydration
        if (!containerRef.current || resolvedTheme === undefined) return

        const isDark = resolvedTheme === 'dark'

        // Reset disposed flag for new chart
        isDisposedRef.current = false

        // Clear container to prevent duplication
        containerRef.current.innerHTML = ''

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: isDark ? '#1e222d' : '#ffffff' },
                textColor: isDark ? '#d1d4dc' : '#333333',
                panes: {
                    enableResize: true,
                    separatorColor: isDark ? '#FFFFFF' : '#000000', // Explicit high-contrast separators
                }
            },
            grid: {
                vertLines: { color: isDark ? '#2a2e39' : '#e0e0e0' },
                horzLines: { color: isDark ? '#2a2e39' : '#e0e0e0' },
            },
            autoSize: true,
            timeScale: {
                timeVisible: true,
                rightOffset: 5,
                tickMarkFormatter: (time: number) => formatTimeForTimezone(time),
                borderColor: isDark ? '#2a2e39' : '#e0e0e0',
            },
            rightPriceScale: {
                borderColor: isDark ? '#2a2e39' : '#e0e0e0',
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
        })


        chartRef.current = chart
        setChartInstance(chart)

        return () => {

            // Mark as disposed BEFORE removal to prevent race conditions
            isDisposedRef.current = true
            chartRef.current = null
            setChartInstance(null)
            setSeriesInstance(null)
            try {
                chart.remove()

            } catch (e) {

                // Chart may already be disposed in Strict Mode double-mount
            }
        }

    }, [containerRef, resolvedTheme])

    // Manage Series based on Style
    useEffect(() => {
        if (!chartInstance || isDisposedRef.current) return

        let newSeries: ISeriesApi<any>

        const commonOptions = {
            upColor: '#26a69a',
            downColor: '#ef5350',
        }

        try {
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
                        pane: 0 // Explicitly assign to pane 0
                    } as any)
                    break
            }


            setSeriesInstance(newSeries)

            if (data.length > 0) {
                const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
                newSeries.setData(chartData)
                chartInstance.timeScale().fitContent()

            } else {

            }
        } catch (e) {

            // Chart may be disposed during rapid re-renders
            return
        }

        return () => {

            if (!isDisposedRef.current && chartInstance && newSeries) {
                try {
                    chartInstance.removeSeries(newSeries)
                } catch (e) { }
            }
            setSeriesInstance(null)
        }
    }, [chartInstance, style])

    // Track if this is the first data load for this ticker
    const isFirstLoadRef = useRef(true)
    const prevDataLengthRef = useRef(0)

    // Update Data when data changes
    useEffect(() => {
        if (!seriesInstance || !data.length || isDisposedRef.current || !chartInstance) return

        try {
            const timeScale = chartInstance.timeScale()
            const isFirstLoad = isFirstLoadRef.current || prevDataLengthRef.current === 0

            // Set the new data
            const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : data
            seriesInstance.setData(chartData)

            // Only fitContent on first load - chart auto-preserves on subsequent updates
            if (isFirstLoad) {
                isFirstLoadRef.current = false
                requestAnimationFrame(() => {
                    try {
                        if (!isDisposedRef.current) {
                            timeScale.fitContent()
                        }
                    } catch { }
                })
            }
            // NO ELSE NEEDED - chart preserves position by TIME automatically!

            prevDataLengthRef.current = data.length

            if (markers && markers.length > 0) {
                if (typeof createSeriesMarkers === 'function') {
                    createSeriesMarkers(seriesInstance as any, markers)
                } else if (typeof (seriesInstance as any).setMarkers === 'function') {
                    (seriesInstance as any).setMarkers(markers)
                }
            }
        } catch (e) {
            // Series may be disposed
        }
    }, [seriesInstance, data, style, markers, chartInstance])

    const primitivesRef = useRef<any[]>([])
    const indicatorsKey = useMemo(() => JSON.stringify(indicators), [indicators])

    // Manage Indicators & Layout (Native Panes)
    useEffect(() => {
        if (!chartInstance || !seriesInstance || !data.length || isDisposedRef.current) return

        const currentIndicators: string[] = indicatorsKey ? JSON.parse(indicatorsKey) : []
        const activeSeries: ISeriesApi<any>[] = []

        let oscillatorPaneIndex = 1;

        try {
            currentIndicators.forEach((ind) => {
                const [baseId, param] = ind.split(":");
                const config = INDICATOR_DEFINITIONS[baseId];
                if (!config) return;

                const period = param ? parseInt(param) : (config.defaultParams?.period || 14);

                if (config.type === 'overlay') {
                    if (baseId === 'sma') {
                        const smaData = calculateSMA(data, period);
                        const line = chartInstance.addSeries(LineSeries, {
                            color: config.color || '#2962FF',
                            lineWidth: 1,
                            title: `${config.label} ${period}`,
                            priceScaleId: 'right',
                            pane: 0
                        } as any);
                        line.setData(smaData);
                        activeSeries.push(line);
                    } else if (baseId === 'ema') {
                        const emaData = calculateEMA(data, period);
                        const line = chartInstance.addSeries(LineSeries, {
                            color: config.color || '#FF6D00',
                            lineWidth: 1,
                            title: `${config.label} ${period}`,
                            priceScaleId: 'right',
                            pane: 0
                        } as any);
                        line.setData(emaData);
                        activeSeries.push(line);
                    } else if (baseId === 'vwap') {
                        // VWAP requires Python API - fetch asynchronously
                        (async () => {
                            try {
                                const result = await calculateIndicators(data, ['vwap']);
                                if (result && result.indicators.vwap && chartInstance && !isDisposedRef.current) {
                                    const vwapData = toLineSeriesData(result.time, result.indicators.vwap);
                                    const line = chartInstance.addSeries(LineSeries, {
                                        color: config.color || '#9C27B0',
                                        lineWidth: 2,
                                        title: 'VWAP',
                                        priceScaleId: 'right',
                                        pane: 0
                                    } as any);
                                    line.setData(vwapData as any);
                                    activeSeries.push(line);
                                }
                            } catch (e) {
                                console.error('Failed to calculate VWAP:', e);
                            }
                        })();
                    }
                } else if (config.type === 'oscillator') {
                    const currentPane = oscillatorPaneIndex++;

                    if (baseId === 'rsi') {
                        const rsiData = calculateRSI(data, period);
                        const rsiSeries = chartInstance.addSeries(LineSeries, {
                            color: config.color || '#9C27B0',
                            lineWidth: 1,
                            title: `RSI ${period}`,
                        } as any, currentPane);
                        rsiSeries.setData(rsiData);
                        activeSeries.push(rsiSeries);
                    } else if (baseId === 'macd') {
                        const defaults = config.defaultParams || {};
                        const macdData = calculateMACD(data, defaults.fast || 12, defaults.slow || 26, defaults.signal || 9);

                        const histSeries = chartInstance.addSeries(HistogramSeries, {
                            color: '#26a69a',
                            priceLineVisible: false,
                        } as any, currentPane);
                        histSeries.setData(macdData.map(d => ({
                            time: d.time,
                            value: d.histogram,
                            color: d.histogram >= 0 ? '#26a69a' : '#ef5350'
                        })));

                        const macdLine = chartInstance.addSeries(LineSeries, {
                            color: '#2962FF',
                            lineWidth: 1,
                            title: 'MACD',
                        } as any, currentPane);
                        macdLine.setData(macdData.map(d => ({ time: d.time, value: d.macd })));

                        const signalLine = chartInstance.addSeries(LineSeries, {
                            color: '#FF6D00',
                            lineWidth: 1,
                            title: 'Signal',
                        } as any, currentPane);
                        signalLine.setData(macdData.map(d => ({ time: d.time, value: d.signal })));

                        activeSeries.push(histSeries, macdLine, signalLine);
                    }
                }
            });

            // 2. Set Pane Sizing
            const panes = chartInstance.panes();
            panes.forEach((pane, index) => {
                pane.moveTo(index); // Explicitly move pane to its index
                if (index > 0) {
                    pane.setHeight(150);
                }
            });

        } catch (e) {
            console.error('[CHART] Error in pane sizing:', e);
            return;
        }

        return () => {
            if (isDisposedRef.current) return
            activeSeries.forEach(item => {
                try {
                    chartInstance.removeSeries(item)
                } catch (e) { }
            })
        }
    }, [chartInstance, seriesInstance, indicatorsKey, data])

    // Manage Primitives (Sessions, Watermark) - NO data dependency
    useEffect(() => {
        if (!chartInstance || !seriesInstance || isDisposedRef.current) return

        const currentIndicators: string[] = indicatorsKey ? JSON.parse(indicatorsKey) : []
        const primitiveItems: Array<{ primitive: any, series: any }> = []
        primitivesRef.current = []

        try {
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
        } catch (e) {
            // Chart may be disposed
            return
        }

        return () => {
            if (isDisposedRef.current) return
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

    const getVisibleTimeRange = () => {
        if (!chartInstance || !seriesInstance || data.length === 0) return null

        // Logical range
        const range = chartInstance.timeScale().getVisibleLogicalRange()
        if (!range) return null

        // Safe mapping: logic index -> data array index
        const leftIndex = Math.floor(Math.max(0, range.from))
        const rightIndex = Math.ceil(Math.min(data.length - 1, range.to))

        if (leftIndex < 0 || rightIndex >= data.length || leftIndex > rightIndex) return null

        return {
            start: data[leftIndex].time,
            end: data[rightIndex].time,
            center: data[Math.floor((leftIndex + rightIndex) / 2)].time
        }
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
        getVisibleBarIndex,
        getVisibleTimeRange
    }
}
