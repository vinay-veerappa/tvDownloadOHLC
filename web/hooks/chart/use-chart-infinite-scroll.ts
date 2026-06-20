import { useEffect, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"

interface UseChartInfiniteScrollProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    replayMode?: boolean
    data: any[]
    
    // Legacy (leftward pagination)
    hasMoreData?: boolean
    isLoadingMore?: boolean
    loadMoreData?: () => void

    // Bidirectional pagination
    hasMoreDataLeft?: boolean
    isLoadingMoreLeft?: boolean
    loadMoreDataLeft?: () => void
    hasMoreDataRight?: boolean
    isLoadingMoreRight?: boolean
    loadMoreDataRight?: () => void
    isRestoringRangeRef?: React.RefObject<boolean>
}

export function useChartInfiniteScroll({
    chart,
    series,
    replayMode,
    data,
    hasMoreData,
    isLoadingMore,
    loadMoreData,
    hasMoreDataLeft,
    isLoadingMoreLeft,
    loadMoreDataLeft,
    hasMoreDataRight,
    isLoadingMoreRight,
    loadMoreDataRight,
    isRestoringRangeRef
}: UseChartInfiniteScrollProps) {
    const lastLoadTimeRef = useRef<number>(0)
    const lastScrollCheckTimeRef = useRef<number>(0)
    const LOAD_DEBOUNCE_MS = 300

    // Resolve active parameters
    const activeHasMoreDataLeft = hasMoreDataLeft !== undefined ? hasMoreDataLeft : (hasMoreData ?? false)
    const activeIsLoadingMoreLeft = isLoadingMoreLeft !== undefined ? isLoadingMoreLeft : (isLoadingMore ?? false)
    const activeLoadMoreDataLeft = loadMoreDataLeft ?? loadMoreData

    const activeHasMoreDataRight = hasMoreDataRight ?? false
    const activeIsLoadingMoreRight = isLoadingMoreRight ?? false
    const activeLoadMoreDataRight = loadMoreDataRight

    useEffect(() => {
        if (!chart || !series || replayMode || data.length === 0) return

        const handleVisibleRangeChange = (logicalRange: { from: number; to: number } | null) => {
            if (!logicalRange) return

            // Guard scroll check during range restoration
            if (isRestoringRangeRef?.current) return

            const now = Date.now()
            // Throttle evaluation to at most once per 50ms to avoid UI jank during drag
            if (now - lastScrollCheckTimeRef.current < 50) {
                return
            }
            lastScrollCheckTimeRef.current = now

            if (now - lastLoadTimeRef.current < LOAD_DEBOUNCE_MS) {
                return
            }

            const barsInfo = series.barsInLogicalRange(logicalRange)
            if (!barsInfo) return

            // Left scroll check (older data)
            if (barsInfo.barsBefore !== null && barsInfo.barsBefore < 1000) {
                if (activeHasMoreDataLeft && !activeIsLoadingMoreLeft && !activeIsLoadingMoreRight && activeLoadMoreDataLeft) {
                    lastLoadTimeRef.current = now
                    console.log(`⏱️ [useChartInfiniteScroll] Scroll check triggered loadMoreDataLeft() at ${now} (barsBefore: ${barsInfo.barsBefore})`);
                    activeLoadMoreDataLeft()
                }
            }

            // Right scroll check (newer data)
            if (barsInfo.barsAfter !== null && barsInfo.barsAfter < 1000) {
                if (activeHasMoreDataRight && !activeIsLoadingMoreRight && !activeIsLoadingMoreLeft && activeLoadMoreDataRight) {
                    lastLoadTimeRef.current = now
                    console.log(`⏱️ [useChartInfiniteScroll] Scroll check triggered loadMoreDataRight() at ${now} (barsAfter: ${barsInfo.barsAfter})`);
                    activeLoadMoreDataRight()
                }
            }
        }

        chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        return () => {
            chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
        }
    }, [
        chart,
        series,
        replayMode,
        data.length,
        activeHasMoreDataLeft,
        activeIsLoadingMoreLeft,
        activeLoadMoreDataLeft,
        activeHasMoreDataRight,
        activeIsLoadingMoreRight,
        activeLoadMoreDataRight,
        isRestoringRangeRef
    ])
}
