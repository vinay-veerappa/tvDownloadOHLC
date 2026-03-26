import { useEffect } from "react"
import { ColorType, IChartApi, ISeriesApi } from "lightweight-charts"
import { ThemeParams } from "@/lib/themes"

interface UseChartThemeProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    theme?: ThemeParams
}

export function useChartTheme({ chart, series, theme }: UseChartThemeProps) {
    useEffect(() => {
        if (!chart || !series || !theme) return

        // Chart Layout
        chart.applyOptions({
            layout: {
                background: { type: ColorType.Solid, color: theme.chart.background },
                textColor: theme.ui.text,
            },
            grid: {
                vertLines: { visible: false, color: theme.chart.grid, style: 0 },
                horzLines: { visible: false, color: theme.chart.grid, style: 0 },
            },
            crosshair: {
                vertLine: { color: theme.chart.crosshair, labelBackgroundColor: theme.chart.background },
                horzLine: { color: theme.chart.crosshair, labelBackgroundColor: theme.chart.background },
            },
        })

        // Candle Colors
        series.applyOptions({
            upColor: theme.candle.upBody,
            downColor: theme.candle.downBody,
            borderUpColor: theme.candle.upBorder,
            borderDownColor: theme.candle.downBorder,
            wickUpColor: theme.candle.upWick,
            wickDownColor: theme.candle.downWick,
        })
    }, [chart, series, theme])
}
