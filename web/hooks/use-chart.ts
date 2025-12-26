"use client"

import { useEffect, useRef, useState, useMemo } from "react"
import { normalizeResolution, getResolutionInMinutes } from "@/lib/resolution"
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
    TickMarkType,
    createSeriesMarkers
} from "lightweight-charts"

import { calculateSMA, calculateEMA, calculateRSI, calculateMACD } from "@/lib/charts/indicator-calculations"
import { INDICATOR_DEFINITIONS } from "@/lib/charts/indicator-config"
import { HistogramSeries } from "lightweight-charts"
import { calculateHeikenAshi } from "@/lib/charts/heiken-ashi"
import { calculateIndicators, toLineSeriesData, VWAPSettings } from "@/lib/indicator-api"
import { INDICATOR_REGISTRY } from "@/lib/charts/indicators"

import { ThemeParams } from "@/lib/themes"
import { useTheme } from "next-themes"
import { formatTimeForTimezone } from "@/lib/utils"

export function useChart(
    containerRef: React.RefObject<HTMLDivElement | null>,
    style: string = 'candles',
    indicators: string[] = [],
    data: any[] = [],
    markers: any[] = [],
    displayTimezone: string = 'America/New_York',
    timeframe: string = '1m',
    vwapSettings?: VWAPSettings,
    ticker?: string,
    theme?: ThemeParams // New Arg
) {
    // console.log('[useChart] displayTimezone:', displayTimezone)
    const { resolvedTheme } = useTheme()
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null)
    const [seriesInstance, setSeriesInstance] = useState<ISeriesApi<any> | null>(null)


    // Track chart lifecycle to prevent "disposed" errors in Strict Mode
    const chartRef = useRef<IChartApi | null>(null)
    const isDisposedRef = useRef(false)
    // Create timezone-aware tick mark formatter
    // Use the imported formatTimeForTimezone, but we need to create a closure if we want to support 'displayTimezone' 
    // actually the imported one doesn't support timezone arg yet?
    // Let's check utils.ts again. 
    // utils.ts: export function formatTimeForTimezone(time: number): string { ... } - NO timezone arg.
    // So I need to UPDATE utils.ts to accept timezone, OR keep the local one but fix it to use toLocaleString (Date+Time).
    // Update: utils.ts WAS updated to accept timezone.

    const formatTimeForTimezoneLocal = (time: number) => {
        // Use the utility function which now supports timezone
        return formatTimeForTimezone(time, displayTimezone)
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
                rightOffset: 50,
                minBarSpacing: 0.02, // Allow zooming out to see more history
                borderColor: isDark ? '#2a2e39' : '#e0e0e0',
                tickMarkFormatter: (time: number, tickMarkType: TickMarkType, locale: string) => {
                    const date = new Date(time * 1000);
                    // Force using the generic formatter with specific options for each type
                    // preventing manual construction errors
                    // use 'en-US' strictly to avoid browser locale variations

                    const tz = displayTimezone === 'local' ? undefined : displayTimezone;

                    try {
                        // Date parts
                        if (tickMarkType === TickMarkType.Year) {
                            return date.toLocaleDateString('en-US', { timeZone: tz, year: 'numeric' });
                        }
                        if (tickMarkType === TickMarkType.Month) {
                            return date.toLocaleDateString('en-US', { timeZone: tz, month: 'short' });
                        }
                        if (tickMarkType === TickMarkType.DayOfMonth) {
                            return date.toLocaleDateString('en-US', { timeZone: tz, day: 'numeric', month: 'short' });
                        }

                        // Time parts
                        const formatted = date.toLocaleTimeString('en-US', {
                            timeZone: tz,
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false,
                            timeZoneName: 'short'
                        });

                        // Debug log for user to check input timestamp vs output




                        return formatted;

                    } catch (e) {
                        // Fallback to UTC if timezone is invalid
                        console.error('Timezone error', e);
                        return date.toISOString().substring(11, 16);
                    }
                }
            },
            localization: {
                locale: 'en-US',
                dateFormat: 'yyyy-MM-dd',
                // Crosshair matching the Tick Mark logic
                timeFormatter: (time: number) => {
                    return formatTimeForTimezone(time, displayTimezone)
                },
            },
            rightPriceScale: {
                borderColor: isDark ? '#2a2e39' : '#e0e0e0',
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
                horzTouchDrag: true,
                vertTouchDrag: true,
            },
            handleScale: {
                axisPressedMouseMove: true,
                mouseWheel: true,
                pinch: true,
            },
            // Note: watermark was removed in lightweight-charts v5
            // Use createTextWatermark plugin if watermark is needed
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

            }
        }
    }, [containerRef, resolvedTheme])

    // Update Timezone Formatter when displayTimezone changes
    useEffect(() => {
        if (!chartInstance) return

        try {
            chartInstance.applyOptions({
                localization: {
                    // Crosshair Label: Show Full Date & Time
                    timeFormatter: (time: number) => {
                        return formatTimeForTimezone(time, displayTimezone)
                    },
                    dateFormat: 'yyyy-MM-dd',
                    locale: 'en-US',
                },
                timeScale: {
                    // Update Tick Formatter on change too
                    tickMarkFormatter: (time: number, tickMarkType: TickMarkType, locale: string) => {
                        const date = new Date(time * 1000);
                        const tz = displayTimezone === 'local' ? undefined : displayTimezone;
                        try {
                            if (tickMarkType === TickMarkType.Year) return date.toLocaleDateString('en-US', { timeZone: tz, year: 'numeric' });
                            if (tickMarkType === TickMarkType.Month) return date.toLocaleDateString('en-US', { timeZone: tz, month: 'short' });
                            if (tickMarkType === TickMarkType.DayOfMonth) return date.toLocaleDateString('en-US', { timeZone: tz, day: 'numeric', month: 'short' });
                            return date.toLocaleTimeString('en-US', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false, timeZoneName: 'short' });
                        } catch (e) { return date.toISOString().substring(11, 16); }
                    }
                }
            })
        } catch (e) {
            console.warn('Failed to apply timezone options', e)
        }
    }, [chartInstance, displayTimezone])

    // Note: watermark update removed - watermark is a plugin in v5

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
                // Clone data to avoid mutations (whitespace added in data update effect)
                const chartData = style === 'heiken-ashi' ? calculateHeikenAshi(data) : [...data];

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

    // Memoize chart data transformation (Heiken Ashi + whitespace)
    const chartData = useMemo(() => {
        if (!data.length) return [];

        // Calculate base data (Heiken Ashi or raw OHLC)
        let result = style === 'heiken-ashi' ? calculateHeikenAshi(data) : [...data];

        // Add whitespace bars
        if (result.length > 0) {
            const lastBar = result[result.length - 1];
            const lastTime = lastBar.time as number;
            const res = normalizeResolution(timeframe);
            const intervalSeconds = getResolutionInMinutes(res) * 60;
            const whitespaceCount = 100;

            for (let i = 1; i <= whitespaceCount; i++) {
                result.push({
                    time: (lastTime + (i * intervalSeconds)) as any
                });
            }
        }

        return result;
    }, [data, style, timeframe]);

    // Update Data when data changes
    useEffect(() => {
        if (!seriesInstance || !chartData.length || isDisposedRef.current || !chartInstance) return

        try {
            const timeScale = chartInstance.timeScale()
            const isFirstLoad = isFirstLoadRef.current || prevDataLengthRef.current === 0

            //console.log(`[useChart] calling setData with ${chartData.length} items. First:`, chartData[0], 'Last:', chartData[chartData.length-1])
            try {
                seriesInstance.setData(chartData)
                //console.log('[useChart] setData success')
            } catch (err) {
                console.error('[useChart] setData FAILED:', err)
            }

            // Only fitContent on first load - chart auto-preserves on subsequent updates
            if (isFirstLoad) {
                isFirstLoadRef.current = false
                console.log('[useChart] First load - executing fitContent()')
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
    const indicatorsRef = useRef<any[]>([])
    const indicatorsKey = useMemo(() => JSON.stringify(indicators), [indicators])

    // Create a stable key for data time range to prevent unnecessary indicator re-renders
    // Only changes when the data boundaries change (new ticker/timeframe), not on every scroll
    const dataTimeRangeKey = useMemo(() => {
        if (!data.length) return '';
        return `${data[0].time}-${data[data.length - 1].time}`;
    }, [data.length > 0 ? data[0]?.time : 0, data.length > 0 ? data[data.length - 1]?.time : 0])

    // Store data in a ref so indicators can access it without causing re-renders  
    const dataRef = useRef(data)
    dataRef.current = data

    // Manage Indicators & Layout (Native Panes)
    useEffect(() => {
        if (!chartInstance || !seriesInstance || !dataTimeRangeKey || isDisposedRef.current) return

        const currentIndicators: string[] = indicatorsKey ? JSON.parse(indicatorsKey) : []
        const activeSeries: ISeriesApi<any>[] = []

        let isCancelled = false;
        let oscillatorPaneIndex = 1;

        try {
            currentIndicators.forEach((ind) => {
                const [baseId, param] = ind.split(":");
                const config = INDICATOR_DEFINITIONS[baseId];
                if (!config) return;

                const indicatorRenderer = INDICATOR_REGISTRY[baseId];
                if (indicatorRenderer) {
                    const params = { ...config, period: param ? parseInt(param) : undefined };

                    const renderPromise = indicatorRenderer.render({
                        chart: chartInstance,
                        data: dataRef.current, // Use ref to avoid re-renders
                        timeframe,
                        ticker,
                        vwapSettings,
                        resolvedTheme,
                        theme, // Pass ThemeParams
                        displayTimezone
                    }, params, oscillatorPaneIndex);

                    renderPromise.then(({ series, paneIndexIncrement }: { series: any[], paneIndexIncrement: number }) => {
                        if (isCancelled || isDisposedRef.current) {
                            // Effect cancelled or chart disposed - clean up immediately
                            series.forEach(s => {
                                try { chartInstance.removeSeries(s); } catch (e) { }
                            });
                            return;
                        }

                        activeSeries.push(...series);

                        // Populate exposed ref for dynamic updates and hit testing
                        // Store paired data for update() calls
                        indicatorsRef.current.push({
                            id: baseId,
                            param,
                            series: series,
                            renderer: indicatorRenderer
                        });

                        oscillatorPaneIndex += paneIndexIncrement;

                        // Re-layout panes if needed
                        if (paneIndexIncrement > 0) {
                            const panes = chartInstance.panes();
                            panes.forEach((pane, index) => {
                                if (index > 0) pane.setHeight(150);
                            });
                        }
                    }).catch(err => {
                        console.error(`Failed to render indicator ${baseId}:`, err);
                    });
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
            isCancelled = true;
            if (isDisposedRef.current) return
            activeSeries.forEach(item => {
                try {
                    chartInstance.removeSeries(item)
                } catch (e) { }
            })
            // Clear ref on cleanup
            indicatorsRef.current = [];
        }
    }, [chartInstance, seriesInstance, indicatorsKey, dataTimeRangeKey, vwapSettings, ticker, resolvedTheme])

    // Dynamic Updates on Scroll
    useEffect(() => {
        if (!chartInstance || isDisposedRef.current) return;

        // Track last calculated range to avoid redundant updates
        let lastVisibleStart = 0;
        let lastVisibleEnd = 0;

        const handleVisibleRangeChange = async () => {
            if (indicatorsRef.current.length === 0) return;

            // Get Visible Range
            const range = chartInstance.timeScale().getVisibleLogicalRange();
            if (!range) return;

            // Convert to Time Range
            const data = dataRef.current;
            if (!data || data.length === 0) return;

            const leftIndex = Math.floor(Math.max(0, range.from));
            const rightIndex = Math.ceil(Math.min(data.length - 1, range.to));

            if (leftIndex > rightIndex) return;

            const visibleRange = {
                start: data[leftIndex].time as number,
                end: data[rightIndex].time as number
            };

            // Skip if range is unchanged (performance optimization)
            if (visibleRange.start === lastVisibleStart && visibleRange.end === lastVisibleEnd) {
                return;
            }
            lastVisibleStart = visibleRange.start;
            lastVisibleEnd = visibleRange.end;

            // Iterate indicators and call update if available
            for (const ind of indicatorsRef.current) {
                if (ind.renderer && typeof ind.renderer.update === 'function') {
                    try {
                        const ctx = {
                            chart: chartInstance,
                            data: data,
                            timeframe,
                            ticker,
                            vwapSettings,
                            resolvedTheme,
                            theme,
                            displayTimezone,
                            visibleRange
                        };
                        await ind.renderer.update(ctx, ind.series, { ...INDICATOR_DEFINITIONS[ind.id], period: ind.param });
                    } catch (e) {
                        console.error(`[Dynamic] Update failed for ${ind.id}: `, e);
                    }
                }
            }
        };

        // Debounce (only fire after scrolling stops for 500ms)
        let timeoutId: any = null;
        const debouncedHandler = () => {
            if (timeoutId) clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                handleVisibleRangeChange();
                timeoutId = null;
            }, 500); // 500ms debounce
        };

        chartInstance.timeScale().subscribeVisibleLogicalRangeChange(debouncedHandler);

        return () => {
            chartInstance.timeScale().unsubscribeVisibleLogicalRangeChange(debouncedHandler);
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [chartInstance, timeframe, ticker, vwapSettings, resolvedTheme, theme, displayTimezone]);

    // Manage Primitives (Sessions, Watermark) - Removed legacy plugins
    useEffect(() => {
        // Legacy primitive management removed as plugins are deleted.
        // If watermark or sessions are needed, they should be reimplemented as V2 tools or native LWCharts plugins.
    }, [])

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
        getVisibleTimeRange,
        indicators: indicatorsRef, // Expose indicators ref

    }
}
