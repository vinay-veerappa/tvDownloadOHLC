import { useEffect, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"

interface UseChartInfiniteScrollProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    replayMode?: boolean
    data: any[]
    hasMoreData: boolean
    isLoadingMore: boolean
    loadMoreData: () => void
}

export function useChartInfiniteScroll({
    chart, series, replayMode, data, hasMoreData, isLoadingMore, loadMoreData
}: UseChartInfiniteScrollProps) {
    const lastLoadTimeRef = useRef<number>(0)
    const LOAD_DEBOUNCE_MS = 500

    useEffect(() => {
        if (!chart || !series || replayMode || data.length === 0) return

        const handleVisibleRangeChange = (logicalRange: { from: number; to: number } | null) => {
            if (!logicalRange) return

            const now = Date.now()
            if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) return

            const barsInfo = series.barsInLogicalRange(logicalRange)

            if (barsInfo && barsInfo.barsBefore !== null && barsInfo.barsBefore < 50) {
                if (hasMoreData && !isLoadingMore) {
                    lastLoadTimeRef.current = now
                    loadMoreData()
                }
            }
        }

        chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        return () => {
            chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        }
    }, [chart, series, replayMode, data.length, hasMoreData, isLoadingMore, loadMoreData])
}
