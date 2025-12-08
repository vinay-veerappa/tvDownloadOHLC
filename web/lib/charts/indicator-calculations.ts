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

export function calculateRSI(data: { time: Time; close: number }[], period: number = 14): IndicatorData[] {
    if (data.length < period + 1) return [];

    const rsiData: IndicatorData[] = [];
    let gains = 0;
    let losses = 0;

    // First average gain/loss
    for (let i = 1; i <= period; i++) {
        const change = data[i].close - data[i - 1].close;
        if (change > 0) gains += change;
        else losses += Math.abs(change);
    }

    let avgGain = gains / period;
    let avgLoss = losses / period;

    // First RSI
    let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    let rsi = 100 - (100 / (1 + rs));

    rsiData.push({ time: data[period].time, value: rsi });

    // Subsequent RSIs (Smoothed)
    for (let i = period + 1; i < data.length; i++) {
        const change = data[i].close - data[i - 1].close;
        const gain = change > 0 ? change : 0;
        const loss = change < 0 ? Math.abs(change) : 0;

        avgGain = ((avgGain * (period - 1)) + gain) / period;
        avgLoss = ((avgLoss * (period - 1)) + loss) / period;

        rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        rsi = 100 - (100 / (1 + rs));

        rsiData.push({ time: data[i].time, value: rsi });
    }

    return rsiData;
}

export interface MACDData {
    time: Time;
    macd: number;
    signal: number;
    histogram: number;
}

export function calculateMACD(
    data: { time: Time; close: number }[],
    fastPeriod: number = 12,
    slowPeriod: number = 26,
    signalPeriod: number = 9
): MACDData[] {
    const emaFast = calculateEMA(data, fastPeriod);
    const emaSlow = calculateEMA(data, slowPeriod);

    // Align by time
    const macdSeries: { time: Time; value: number }[] = [];

    // Create map for faster lookup or assume sorted
    // Assuming data is sorted, we can iterate
    let fastIdx = 0;
    let slowIdx = 0;

    while (fastIdx < emaFast.length && slowIdx < emaSlow.length) {
        const tDesc = (emaFast[fastIdx].time as number) - (emaSlow[slowIdx].time as number);
        if (tDesc < 0) { fastIdx++; continue; }
        if (tDesc > 0) { slowIdx++; continue; }

        // Match
        macdSeries.push({
            time: emaFast[fastIdx].time,
            value: emaFast[fastIdx].value - emaSlow[slowIdx].value
        });
        fastIdx++;
        slowIdx++;
    }

    const signalSeries = calculateEMA(macdSeries.map(d => ({ time: d.time, close: d.value })), signalPeriod);

    // Combine for final result
    const result: MACDData[] = [];
    let macdIdx = 0;
    let sigIdx = 0;

    while (macdIdx < macdSeries.length && sigIdx < signalSeries.length) {
        const tDesc = (macdSeries[macdIdx].time as number) - (signalSeries[sigIdx].time as number);
        if (tDesc < 0) { macdIdx++; continue; }
        if (tDesc > 0) { sigIdx++; continue; }

        const macdVal = macdSeries[macdIdx].value;
        const sigVal = signalSeries[sigIdx].value;

        result.push({
            time: macdSeries[macdIdx].time,
            macd: macdVal,
            signal: sigVal,
            histogram: macdVal - sigVal
        });
        macdIdx++;
        sigIdx++;
    }

    return result;
}
