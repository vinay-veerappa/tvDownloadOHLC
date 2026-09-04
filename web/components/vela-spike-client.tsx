'use client'

import { useEffect, useRef, useState } from 'react'
import { useTheme } from 'next-themes'
import type { VelaWorkspace as VelaWorkspaceType } from '@luxalgo/vela/workspace'

interface VelaSpikeClientProps {
    ticker: string
}

const TIMEFRAMES = ['1', '5', '15', '30', '60', '240', 'D']

// Throwaway comparison spike (see conversation) — NOT wired into the real chart stack.
// Now wired for LIVE data via a custom DataProvider (lib/vela-spike/stream-chart-provider.ts)
// that bridges Vela's provider port to stream_chart.py's :8001 /history + /stream — the
// same feed the real lightweight-charts app uses. Tests whether Vela's built-in
// getBars/subscribe flow replaces the ~250 lines of hand-rolled merge/resample/reconnect
// logic in web/hooks/chart/use-live-data-loading.ts. Requires stream_chart.py on :8001.
// W/M/Y timeframes are NOT supported by the provider (see its header) — deliberately
// left out of the topbar's timeframe list below rather than silently misbehaving.
export function VelaSpikeClient({ ticker }: VelaSpikeClientProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const wsRef = useRef<VelaWorkspaceType | null>(null)
    const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
    const [error, setError] = useState<string | null>(null)
    const { resolvedTheme } = useTheme()

    useEffect(() => {
        let cancelled = false

        async function mount() {
            setStatus('loading')
            setError(null)
            try {
                const [{ VelaWorkspace }, { StreamChartProvider }] = await Promise.all([
                    import('@luxalgo/vela/workspace'),
                    import('@/lib/vela-spike/stream-chart-provider'),
                ])

                if (cancelled || !containerRef.current) return

                wsRef.current?.destroy()
                const ws = new VelaWorkspace(containerRef.current, {
                    layout: false,
                    // Explicit `provider:ticker` form — a bare symbol only resolves if the
                    // provider implements listSymbols() to build an index (ours doesn't),
                    // and the live-subscribe path resolves strictly through that registry
                    // (unlike the initial getBars load, which tolerated the bare symbol).
                    // Without the prefix, chart.data.resolve() returns null and
                    // LiveSession silently no-ops instead of ever calling subscribe().
                    symbol: `streamchart:${ticker}`,
                    timeframe: '1',
                    timeframes: TIMEFRAMES,
                    live: true,
                    providers: { streamchart: () => new StreamChartProvider() },
                    theme: resolvedTheme === 'light' ? 'light' : 'dark',
                    persist: false,
                })
                wsRef.current = ws
                ;(window as unknown as { __velaSpike: VelaWorkspaceType }).__velaSpike = ws
                setStatus('ready')
            } catch (e) {
                if (!cancelled) {
                    setError(e instanceof Error ? e.message : String(e))
                    setStatus('error')
                }
            }
        }

        void mount()

        return () => {
            cancelled = true
            wsRef.current?.destroy()
            wsRef.current = null
        }
    }, [ticker, resolvedTheme])

    return (
        <div className="flex flex-col h-full w-full">
            <div className="flex-none px-3 py-1.5 text-xs border-b border-border bg-muted/30 flex items-center justify-between">
                <span>Vela spike (live) — {ticker}</span>
                <span>
                    {status === 'loading' && 'loading…'}
                    {status === 'ready' && 'connected'}
                    {status === 'error' && <span className="text-red-500">{error}</span>}
                </span>
            </div>
            <div ref={containerRef} className="flex-1 min-h-0 w-full" />
        </div>
    )
}
