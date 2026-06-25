import { useEffect, useState, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { ThemeParams } from "@/lib/themes"
import { fetchProfilerStats, fetchLevelTouches, ProfilerSession, LevelTouchesResponse } from "@/lib/api/profiler"

interface UseTruthProfilerProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    ticker: string
    indicators: string[]
    theme?: ThemeParams
    indicatorParams?: Record<string, any>
    isDisposed?: () => boolean
}

export function useTruthProfiler({
    chart, series, ticker, indicators, theme, indicatorParams, isDisposed
}: UseTruthProfilerProps) {
    const [truthSessions, setTruthSessions] = useState<ProfilerSession[]>([])
    const [truthLevels, setTruthLevels] = useState<LevelTouchesResponse>({ dates: [], levels: {} })
    const truthProfilerRef = useRef<any>(null)

    // Data Fetching
    useEffect(() => {
        if (!ticker) return
        let isCurrent = true

        const loadData = async () => {
            try {
                const [sessionsRes, levelsRes] = await Promise.all([
                    fetchProfilerStats(ticker),
                    fetchLevelTouches(ticker)
                ])
                if (!isCurrent) return

                setTruthSessions(sessionsRes.sessions)
                setTruthLevels(levelsRes)

                if (!isDisposed?.() && truthProfilerRef.current) {
                    try {
                        truthProfilerRef.current.setRemoteData(sessionsRes.sessions, levelsRes)
                    } catch (e) {}
                }
            } catch (err) {
                console.error('[useTruthProfiler] Failed to fetch Truth Profiler data:', err)
            }
        }

        loadData()
        return () => {
            isCurrent = false
        }
    }, [ticker])

    // Lifecycle
    useEffect(() => {
        let isCurrent = true
        if (!chart || !series || !theme || isDisposed?.()) return

        const isEnabled = indicators.includes('truth-profiler')

        if (isEnabled) {
            import('@/lib/charts/indicators/truth-profiler').then(({ TruthProfiler }) => {
                if (!isCurrent || isDisposed?.()) return

                try {
                    if (!truthProfilerRef.current) {
                        truthProfilerRef.current = new TruthProfiler(
                            chart,
                            series,
                            indicatorParams?.['truth-profiler'] || {},
                            theme,
                            () => { }
                        )
                        series.attachPrimitive(truthProfilerRef.current)

                        if (truthSessions.length > 0) {
                            truthProfilerRef.current.setRemoteData(truthSessions, truthLevels)
                        }
                    } else {
                        truthProfilerRef.current.applyOptions(indicatorParams?.['truth-profiler'] || {})
                    }
                } catch (e) {
                    console.error('[TruthProfiler] Error instantiating/attaching:', e)
                }
            })
        } else {
            if (truthProfilerRef.current) {
                try {
                    series.detachPrimitive(truthProfilerRef.current)
                } catch (e) {}
                truthProfilerRef.current = null
            }
        }

        return () => {
            isCurrent = false
            if (isDisposed && !isDisposed() && series && truthProfilerRef.current) {
                try {
                    series.detachPrimitive(truthProfilerRef.current)
                } catch (e) {}
                truthProfilerRef.current = null
            }
        }
    }, [chart, series, indicators, theme, indicatorParams])

    // Theme Sync
    useEffect(() => {
        if (!isDisposed?.() && truthProfilerRef.current && theme) {
            try {
                truthProfilerRef.current.updateTheme(theme)
            } catch (e) {}
        }
    }, [theme])

    return { truthSessions, truthLevels, truthProfilerRef }
}
