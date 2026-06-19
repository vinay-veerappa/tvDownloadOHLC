import { useEffect, useRef, useState } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { ThemeParams } from "@/lib/themes"
import { EMSettings } from "@/components/em-settings-dialog" 
import { useDataLoading } from "@/hooks/chart/use-data-loading"

interface UseExpectedMoveProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    ticker: string
    indicators: string[]
    theme?: ThemeParams
    initialSettings?: EMSettings | null
    onSettingsChange?: (settings: EMSettings) => void
    data: any[]
    isDisposed?: () => boolean
}

export function useExpectedMove({
    chart, series, ticker, indicators, theme, initialSettings, onSettingsChange, data, isDisposed
}: UseExpectedMoveProps) {
    const [settings, setSettings] = useState<EMSettings | null>(initialSettings || null)
    const emPluginRef = useRef<any>(null)
    const dataRef = useRef(data)
    dataRef.current = data

    // Update settings if initialSettings prop changes
    useEffect(() => {
        if (initialSettings) {
            setSettings(initialSettings)
        }
    }, [initialSettings])

    useEffect(() => {
        let isCurrent = true
        if (!series || !chart || !ticker || isDisposed?.()) return

        const showEM = indicators.includes('expected-move') || indicators.includes('em')

        if (showEM) {
            const load = async () => {
                try {
                    const { ExpectedMoveLevels } = await import('@/lib/charts/plugins/expected-move-levels')
                    if (!isCurrent || isDisposed?.()) return

                    if (!emPluginRef.current) {
                        emPluginRef.current = new ExpectedMoveLevels(chart, series, {
                            ticker,
                            showLabels: true
                        })
                        series.attachPrimitive(emPluginRef.current)
                    }

                    let apiTicker = ticker
                    if (settings?.ticker) {
                        apiTicker = settings.ticker
                    } else {
                        if (ticker.includes('ES') || ticker.includes('/ES')) apiTicker = 'ES'
                        else if (ticker.includes('SPX') || ticker === '$SPX') apiTicker = 'SPX'
                        else if (ticker.includes('SPY')) apiTicker = 'SPY'
                    }

                    const daysLimit = settings?.daysToShow || 30
                    const resp = await fetch(`/api/em-levels?ticker=${apiTicker}&days=${daysLimit}`)
                    if (!isCurrent || isDisposed?.()) return
                    if (!resp.ok) return

                    const result = await resp.json()
                    if (!isCurrent || isDisposed?.()) return
                    if (!result.data || result.data.length === 0) return

                    const methodDataMap = new Map<string, any[]>()
                    for (const row of result.data) {
                        const methodId = row.method
                        if (!methodDataMap.has(methodId)) methodDataMap.set(methodId, [])
                        
                        const existing = methodDataMap.get(methodId)!
                        if (!existing.find((e: any) => e.date === row.date)) {
                            existing.push({
                                date: row.date,
                                anchor: row.anchor,
                                emValue: row.em_value,
                                anchorType: row.method.includes('open') ? 'open' : 'close'
                            })
                        }
                    }

                    for (const [methodId, methodData] of methodDataMap) {
                        emPluginRef.current.setMethodData(methodId, methodData)
                    }

                    if (dataRef.current.length > 0) {
                        emPluginRef.current.updateFromBars(dataRef.current)
                    }

                } catch (e) {
                    console.error("[useExpectedMove] Failed to load EM Plugin", e)
                }
            }
            load()
        } else {
            if (emPluginRef.current) {
                try {
                    series.detachPrimitive(emPluginRef.current)
                } catch (e) {}
                emPluginRef.current = null
            }
        }

        return () => {
            isCurrent = false
            if (isDisposed && !isDisposed() && series && emPluginRef.current) {
                try {
                    series.detachPrimitive(emPluginRef.current)
                } catch (e) {}
                emPluginRef.current = null
            }
        }
    }, [series, chart, ticker, theme, indicators, settings?.daysToShow, settings?.ticker])

    // Update from Current Data
    useEffect(() => {
        if (!isDisposed?.() && emPluginRef.current && data.length > 0) {
            try {
                emPluginRef.current.updateFromBars(data)
            } catch (e) {}
        }
    }, [data])

    // Sync with Settings
    useEffect(() => {
        if (!isDisposed?.() && emPluginRef.current && settings) {
            try {
                emPluginRef.current.updateFromSettings({
                    methods: settings.methods,
                    levelMultiples: settings.levelMultiples,
                    showLabels: settings.showLabels,
                    showWeeklyClose: settings.showWeeklyClose,
                    labelFontSize: settings.labelFontSize
                })
                if (dataRef.current.length > 0) {
                    emPluginRef.current.updateFromBars(dataRef.current)
                }
            } catch (e) {}
            onSettingsChange?.(settings)
        }
    }, [settings])

    const dailyDataLogic = useDataLoading({
        ticker,
        timeframe: '1D',
    })

    useEffect(() => {
        if (!isDisposed?.() && emPluginRef.current && dailyDataLogic.fullData.length > 0) {
            try {
                emPluginRef.current.setDailySettlements(dailyDataLogic.fullData)
            } catch (e) {}
        }
    }, [dailyDataLogic.fullData])

    return { settings, setSettings }
}
