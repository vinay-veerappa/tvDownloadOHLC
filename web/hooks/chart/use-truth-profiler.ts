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
}

export function useTruthProfiler({
    chart, series, ticker, indicators, theme, indicatorParams
}: UseTruthProfilerProps) {
    const [truthSessions, setTruthSessions] = useState<ProfilerSession[]>([])
    const [truthLevels, setTruthLevels] = useState<LevelTouchesResponse>({})
    const truthProfilerRef = useRef<any>(null)

    // Data Fetching
    useEffect(() => {
        if (!ticker) return

        const loadData = async () => {
            try {
                const [sessionsRes, levelsRes] = await Promise.all([
                    fetchProfilerStats(ticker),
                    fetchLevelTouches(ticker)
                ])

                setTruthSessions(sessionsRes.sessions)
                setTruthLevels(levelsRes)

                if (truthProfilerRef.current) {
                    truthProfilerRef.current.setRemoteData(sessionsRes.sessions, levelsRes)
                }
            } catch (err) {
                console.error('[useTruthProfiler] Failed to fetch Truth Profiler data:', err)
            }
        }

        loadData()
    }, [ticker])

    // Lifecycle
    useEffect(() => {
        if (!chart || !series || !theme) return

        const isEnabled = indicators.includes('truth-profiler')

        if (isEnabled) {
            import('@/lib/charts/indicators/truth-profiler').then(({ TruthProfiler }) => {
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
            })
        } else {
            if (truthProfilerRef.current) {
                series.detachPrimitive(truthProfilerRef.current)
                truthProfilerRef.current = null
            }
        }
    }, [chart, series, indicators, theme, indicatorParams])

    // Theme Sync
    useEffect(() => {
        if (truthProfilerRef.current && theme) {
            truthProfilerRef.current.updateTheme(theme)
        }
    }, [theme])

    return { truthSessions, truthLevels, truthProfilerRef }
}
