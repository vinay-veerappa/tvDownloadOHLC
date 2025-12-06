import { Time } from "lightweight-charts"

export interface IndicatorData {
    time: Time
    value: number
}

export function calculateSMA(data: { time: Time; close: number }[], period: number): IndicatorData[] {
    const smaData: IndicatorData[] = []

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            continue
        }

        let sum = 0
        for (let j = 0; j < period; j++) {
            sum += data[i - j].close
        }

        smaData.push({
            time: data[i].time,
            value: sum / period,
        })
    }

    return smaData
}

export function calculateEMA(data: { time: Time; close: number }[], period: number): IndicatorData[] {
    const emaData: IndicatorData[] = []

    // Not enough data to calculate EMA
    if (data.length < period) {
        return []
    }

    const multiplier = 2 / (period + 1)

    // Start with SMA for the first EMA value
    let sum = 0
    for (let i = 0; i < period; i++) {
        sum += data[i].close
    }
    let prevEma = sum / period

    // Push the first EMA value (at index period - 1)
    emaData.push({
        time: data[period - 1].time,
        value: prevEma
    })

    // Calculate subsequent EMA values
    for (let i = period; i < data.length; i++) {
        const close = data[i].close
        const ema = (close - prevEma) * multiplier + prevEma
        emaData.push({
            time: data[i].time,
            value: ema
        })
        prevEma = ema
    }

    return emaData
}
