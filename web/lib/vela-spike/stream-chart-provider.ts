import type { DataProvider, ProviderInfo } from '@luxalgo/vela'
import type { OHLCV } from '@luxalgo/vela'
import type { BarRange } from '@luxalgo/vela'

// Throwaway spike provider — bridges Vela's DataProvider port to the existing
// stream_chart.py API (:8001 /history + /stream) so the "live" comparison uses
// the same real feed the lightweight-charts app does, not synthetic data.
//
// Only base-1m + a fixed set of intraday multiples are supported (bucket-resampled
// here, mirroring what web/hooks/chart/use-live-data-loading.ts already does by
// hand) — W/M/Y are NOT handled. This is scoped to answer one question: does
// Vela's built-in subscribe()/getBars() flow replace that hook's hand-rolled
// merge/resample/reconnect logic for the common intraday case.

const TIMEFRAME_MS: Record<string, number> = {
    '1': 60_000,
    '5': 5 * 60_000,
    '15': 15 * 60_000,
    '30': 30 * 60_000,
    '60': 60 * 60_000,
    '240': 4 * 60 * 60_000,
    D: 24 * 60 * 60_000,
}

function apiHost(): string {
    return typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'localhost'
}

function normalize1m(c: { time: number; open: number; high: number; low: number; close: number; volume?: number }): OHLCV {
    return {
        time: c.time > 1e12 ? c.time : c.time * 1000,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
    }
}

function bucketStart(timeMs: number, timeframe: string): number {
    const step = TIMEFRAME_MS[timeframe] ?? TIMEFRAME_MS['1']
    return Math.floor(timeMs / step) * step
}

function resample(bars1m: OHLCV[], timeframe: string): OHLCV[] {
    if (timeframe === '1' || !TIMEFRAME_MS[timeframe]) return bars1m
    const out: OHLCV[] = []
    for (const bar of bars1m) {
        const start = bucketStart(bar.time, timeframe)
        const last = out[out.length - 1]
        if (last && last.time === start) {
            last.high = Math.max(last.high, bar.high)
            last.low = Math.min(last.low, bar.low)
            last.close = bar.close
            last.volume = (last.volume ?? 0) + (bar.volume ?? 0)
        } else {
            out.push({ ...bar, time: start })
        }
    }
    return out
}

export class StreamChartProvider implements DataProvider {
    info(): ProviderInfo {
        return {
            name: 'streamchart',
            displayName: 'stream_chart.py (:8001)',
            capabilities: { enumerate: false, stream: true, symbolInfo: false },
            supportedTimeframes: Object.keys(TIMEFRAME_MS),
        }
    }

    async getBars(ticker: string, timeframe: string, range: BarRange): Promise<OHLCV[]> {
        const res = await fetch(`http://${apiHost()}:8001/history?symbol=${encodeURIComponent(ticker)}&limit=${range.limit ?? 20000}`, {
            cache: 'no-store',
        })
        if (!res.ok) throw new Error(`stream_chart.py /history returned ${res.status} — is it running on :8001?`)
        const json = await res.json()
        if (json.error) throw new Error(json.error)
        const bars1m: OHLCV[] = (json.candles || []).map(normalize1m)
        return resample(bars1m, timeframe)
    }

    subscribe(ticker: string, timeframe: string, onBar: (bar: OHLCV) => void): () => void {
        const w = window as unknown as { __velaSpikeDebug?: unknown[] }
        w.__velaSpikeDebug = w.__velaSpikeDebug ?? []
        const log = (event: string, data: unknown) => {
            w.__velaSpikeDebug!.push({ t: Date.now(), event, data })
            if (w.__velaSpikeDebug!.length > 200) w.__velaSpikeDebug!.shift()
        }
        log('subscribe:called', { ticker, timeframe })

        const ws = new WebSocket(`ws://${apiHost()}:8001/stream?symbol=${encodeURIComponent(ticker)}&timeframe=1m`)
        ws.onopen = () => log('ws:open', {})
        ws.onerror = () => log('ws:error', {})
        ws.onclose = () => log('ws:close', {})
        let bucket: OHLCV | null = null

        const feed1m = (bar1m: OHLCV) => {
            const start = bucketStart(bar1m.time, timeframe)
            if (!bucket || bucket.time !== start) {
                bucket = { ...bar1m, time: start }
            } else {
                // Always produce a NEW object — mutating `bucket` in place and passing
                // the same reference to onBar() looked like a no-op update to Vela's
                // feed (likely a reference-equality check), so bars stopped visibly
                // updating even though onBar() was being called correctly.
                bucket = {
                    ...bucket,
                    high: Math.max(bucket.high, bar1m.high),
                    low: Math.min(bucket.low, bar1m.low),
                    close: bar1m.close,
                    volume: (bucket.volume ?? 0) + (bar1m.volume ?? 0),
                }
            }
            log('onBar:candle', bucket)
            onBar(bucket)
        }

        // A 1m 'candle' message only arrives on a bar close / OHLC-delta batch from the
        // upstream hub — measured empirically at effectively zero per 18s of connection.
        // 'quote' ticks are what actually arrives every ~1s; the forming bar has to be
        // built from those; a provider that only listens for 'candle' never visibly updates.
        const feedTick = (price: number, timeMs: number) => {
            const start = bucketStart(timeMs, timeframe)
            if (!bucket || bucket.time !== start) {
                bucket = { time: start, open: price, high: price, low: price, close: price, volume: 0 }
            } else {
                bucket = {
                    ...bucket,
                    high: Math.max(bucket.high, price),
                    low: Math.min(bucket.low, price),
                    close: price,
                }
            }
            log('onBar:tick', bucket)
            onBar(bucket)
        }

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data)
                if (msg.type === 'snapshot' && msg.candles?.length) {
                    feed1m(normalize1m(msg.candles[msg.candles.length - 1]))
                } else if (msg.type === 'candle' && msg.candle) {
                    // Authoritative OHLC from the hub — corrects whatever quote-tick
                    // approximation built the bar so far (real open, real volume).
                    feed1m(normalize1m(msg.candle))
                } else if (msg.type === 'quote' && typeof msg.price === 'number') {
                    feedTick(msg.price, new Date(msg.time).getTime())
                }
                log('msg', msg.type)
            } catch (e) {
                log('parse:error', String(e))
            }
        }

        return () => ws.close()
    }
}
