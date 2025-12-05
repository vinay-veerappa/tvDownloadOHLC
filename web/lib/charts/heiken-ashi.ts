export interface OHLC {
    time: string | number
    open: number
    high: number
    low: number
    close: number
}

export function calculateHeikenAshi(data: OHLC[]): OHLC[] {
    if (!data || data.length === 0) return []

    const result: OHLC[] = []

    // First HA candle
    let prevHAOpen = data[0].open
    let prevHAClose = data[0].close

    for (let i = 0; i < data.length; i++) {
        const candle = data[i]

        const haClose = (candle.open + candle.high + candle.low + candle.close) / 4
        const haOpen = i === 0 ? (candle.open + candle.close) / 2 : (prevHAOpen + prevHAClose) / 2
        const haHigh = Math.max(candle.high, haOpen, haClose)
        const haLow = Math.min(candle.low, haOpen, haClose)

        result.push({
            time: candle.time,
            open: haOpen,
            high: haHigh,
            low: haLow,
            close: haClose
        })

        prevHAOpen = haOpen
        prevHAClose = haClose
    }

    return result
}
