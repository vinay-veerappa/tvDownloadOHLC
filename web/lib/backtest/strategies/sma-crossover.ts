
import { Strategy, OHLCData, Trade } from "../types"
import { calculateSMA } from "@/lib/charts/indicator-calculations"

export class SmaCrossoverStrategy implements Strategy {
    name = "SMA_CROSSOVER"

    async run(data: OHLCData[], params: Record<string, any>): Promise<Trade[]> {
        const fastPeriod = params.fastPeriod || 9
        const slowPeriod = params.slowPeriod || 21

        // Calculate Indicators
        // @ts-ignore - calculateSMA expects generic array with time/value but we pass OHLC
        const fastSMA = calculateSMA(data, fastPeriod)
        // @ts-ignore
        const slowSMA = calculateSMA(data, slowPeriod)

        // Create Maps for O(1) lookup by time
        const fastSMAMap = new Map(fastSMA.map(i => [i.time as number, i.value]))
        const slowSMAMap = new Map(slowSMA.map(i => [i.time as number, i.value]))

        const trades: Trade[] = []
        let position: 'LONG' | 'SHORT' | null = null
        let entryPrice = 0
        let entryIndex = 0

        // Start after enough data for indicators
        const startIndex = Math.max(fastPeriod, slowPeriod)

        for (let i = startIndex; i < data.length; i++) {
            const currentTime = data[i].time
            const prevTime = data[i - 1].time

            const currentPrice = data[i].close

            const prevFast = fastSMAMap.get(prevTime)
            const currFast = fastSMAMap.get(currentTime)
            const prevSlow = slowSMAMap.get(prevTime)
            const currSlow = slowSMAMap.get(currentTime)

            if (prevFast === undefined || currFast === undefined || prevSlow === undefined || currSlow === undefined) {
                continue
            }

            // Check for Crossover
            const longSignal = prevFast <= prevSlow && currFast > currSlow
            const shortSignal = prevFast >= prevSlow && currFast < currSlow

            // Exit Logic
            if (position === 'LONG' && shortSignal) {
                // Close Long
                const pnl = currentPrice - entryPrice
                trades.push({
                    entryDate: data[entryIndex].time,
                    exitDate: data[i].time,
                    entryPrice,
                    exitPrice: currentPrice,
                    direction: 'LONG',
                    pnl,
                    result: pnl > 0 ? 'WIN' : 'LOSS'
                })
                position = null
            } else if (position === 'SHORT' && longSignal) {
                // Close Short
                const pnl = entryPrice - currentPrice
                trades.push({
                    entryDate: data[entryIndex].time,
                    exitDate: data[i].time,
                    entryPrice,
                    exitPrice: currentPrice,
                    direction: 'SHORT',
                    pnl,
                    result: pnl > 0 ? 'WIN' : 'LOSS'
                })
                position = null
            }

            // Entry Logic
            if (!position) {
                if (longSignal) {
                    position = 'LONG'
                    entryPrice = currentPrice
                    entryIndex = i
                } else if (shortSignal) {
                    position = 'SHORT'
                    entryPrice = currentPrice
                    entryIndex = i
                }
            }
        }

        return trades
    }
}
