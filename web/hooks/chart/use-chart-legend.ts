import { useEffect, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { ThemeParams } from "@/lib/themes"
import { OHLCLegend } from "@/lib/charts/plugins/ohlc-legend"
import { ChartLegendRef } from "@/components/chart/chart-legend"

interface UseChartLegendProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    ticker: string
    timeframe: string
    theme?: ThemeParams
    data: any[]
}

export function useChartLegend({ chart, series, ticker, timeframe, theme, data }: UseChartLegendProps) {
    const legendRef = useRef<ChartLegendRef>(null)
    const canvasLegendRef = useRef<OHLCLegend | null>(null)
    const dataRef = useRef(data)
    const seriesRef = useRef(series)
    const isSubscribedRef = useRef(false)

    // Keep refs in sync
    dataRef.current = data
    seriesRef.current = series

    useEffect(() => {
        if (!chart || !series || isSubscribedRef.current) return

        // Create canvas legend and attach to series
        if (!canvasLegendRef.current) {
            const formatPrice = (price: number) => {
                const isFutures = ticker.includes('!')
                const decimals = isFutures ? 2 : 2
                return price.toFixed(decimals)
            }

            canvasLegendRef.current = new OHLCLegend(chart, series, {
                ticker: ticker.replace('!', ''),
                timeframe: timeframe,
                upColor: theme?.candle.upBody || '#26a69a',
                downColor: theme?.candle.downBody || '#ef5350',
                textColor: theme?.ui.text || '#d1d4dc'
            }, formatPrice)

            series.attachPrimitive(canvasLegendRef.current)
        }

        const handleCrosshairMove = (param: any) => {
            const currentData = dataRef.current
            const currentSeries = seriesRef.current
            if (!currentData || currentData.length === 0 || !currentSeries) return

            let ohlcData = null

            if (!param || !param.time) {
                // Mouse left chart - show latest candle
                const lastBar = currentData[currentData.length - 1]
                if (lastBar) {
                    ohlcData = { open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close }
                }
            } else {
                // Get the candle data at crosshair position
                const candleData = param.seriesData.get(currentSeries)
                if (candleData) {
                    ohlcData = {
                        open: candleData.open,
                        high: candleData.high,
                        low: candleData.low,
                        close: candleData.close
                    }
                }
            }

            if (ohlcData) {
                // Update canvas legend
                canvasLegendRef.current?.updateOHLC(ohlcData)
                // Update HTML legend
                legendRef.current?.updateOHLC(ohlcData)
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        isSubscribedRef.current = true

        // Set initial value
        const timer = setTimeout(() => {
            const currentData = dataRef.current
            if (currentData && currentData.length > 0) {
                const lastBar = currentData[currentData.length - 1]
                const ohlcData = { open: lastBar.open, high: lastBar.high, low: lastBar.low, close: lastBar.close }
                canvasLegendRef.current?.updateOHLC(ohlcData)
                legendRef.current?.updateOHLC(ohlcData)
            }
        }, 100)

        return () => {
            clearTimeout(timer)
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
            isSubscribedRef.current = false
        }
    }, [chart, series, ticker, timeframe, theme])

    return { legendRef, canvasLegendRef }
}
