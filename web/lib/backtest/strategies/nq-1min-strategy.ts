import { Strategy, OHLCData, Trade } from "../types"

// Constants for NQ
// const POINT_VALUE = 20 // $20 per point per contract

interface DailyState {
    date: string
    rangeHigh: number
    rangeLow: number
    rangeDefined: boolean
    hasTraded: boolean
}

export class Nq1MinStrategy implements Strategy {
    name = "NQ_1MIN_STRATEGY"

    async run(data: OHLCData[], params: Record<string, any>): Promise<Trade[]> {
        const trades: Trade[] = []

        let currentState: DailyState = {
            date: "",
            rangeHigh: 0,
            rangeLow: 0,
            rangeDefined: false,
            hasTraded: false
        }

        // Params
        const tp_mode = params.tp_mode || 'R'
        const tp_value = params.tp_value || 1.0
        const exit_hour = params.exit_hour !== undefined ? params.exit_hour : 9
        const exit_minute = params.exit_minute !== undefined ? params.exit_minute : 44

        // Helper to get ET time parts
        // Reuse formatter for performance (crucial for 5M+ bars)
        const formatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hour: 'numeric',
            minute: 'numeric',
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric'
        })

        const getEtTime = (timestamp: number) => {
            const date = new Date(timestamp * 1000)
            const parts = formatter.formatToParts(date)
            // Manual optimization: map lookup is faster than find for known parts? 
            // array.find is slow in tight loop.
            // formatToParts returns known order usually, but safer to loop once.

            let year = '', month = '', day = '', hour = '0', minute = '0'

            for (let i = 0; i < parts.length; i++) {
                const p = parts[i]
                if (p.type === 'hour') hour = p.value
                else if (p.type === 'minute') minute = p.value
                else if (p.type === 'year') year = p.value
                else if (p.type === 'month') month = p.value
                else if (p.type === 'day') day = p.value
            }

            return {
                dateStr: `${year}-${month}-${day}`,
                hour: parseInt(hour),
                minute: parseInt(minute)
            }
        }

        // State variables for active trade management
        let position: 'LONG' | 'SHORT' | null = null
        let entryPrice = 0
        let stopLoss = 0
        let entryTime = 0
        let tp1Hit = false

        for (let i = 0; i < data.length; i++) {
            const bar = data[i]
            const time = getEtTime(bar.time)

            // 1. New Day Reset
            if (time.dateStr !== currentState.date) {
                // Force close at open of new day (error state catch)
                if (position) {
                    const pnl = position === 'LONG' ? (bar.open - entryPrice) : (entryPrice - bar.open)
                    trades.push({
                        entryDate: entryTime,
                        exitDate: bar.time,
                        entryPrice,
                        exitPrice: bar.open,
                        direction: position,
                        pnl: pnl, // Points
                        result: pnl > 0 ? 'WIN' : 'LOSS'
                    })
                    position = null
                }

                currentState = {
                    date: time.dateStr,
                    rangeHigh: 0,
                    rangeLow: 0,
                    rangeDefined: false,
                    hasTraded: false
                }
            }

            // 2. Define Range (9:30 Candle)
            if (time.hour === 9 && time.minute === 30) {
                currentState.rangeHigh = bar.high
                currentState.rangeLow = bar.low
                currentState.rangeDefined = true
                continue
            }

            if (!currentState.rangeDefined) continue
            // Allow re-entries? Rules say "More attempts" in advanced fade section, but confirmation is likely one-shot.
            // "The position" usually implies singular. Staying conservative: one trade per day.
            if (currentState.hasTraded && !position) continue

            // 3. Execution Window (9:31 - Exit)
            // Hard exit time check
            let isHardExitTime = false;

            // Simple check: matches exact exit minute or is after
            if (time.hour > exit_hour || (time.hour === exit_hour && time.minute >= exit_minute)) {
                isHardExitTime = true
            }

            // Execution window logic: From 9:31 until Exit
            // Strict window: 9:31 to Exit Time
            // We shouldn't enter if we are AT or PAST exit time
            let isExecutionWindow = false
            if (time.hour === 9 && time.minute >= 31) {
                if (!isHardExitTime) isExecutionWindow = true
            }

            // --- TRADE MANAGEMENT ---
            if (position) {
                // A. Check Stop Loss
                let stoppedOut = false
                if (position === 'LONG') {
                    if (bar.low <= stopLoss) {
                        const exitPrice = stopLoss
                        const pnl = exitPrice - entryPrice
                        trades.push({
                            entryDate: entryTime,
                            exitDate: bar.time,
                            entryPrice,
                            exitPrice,
                            direction: 'LONG',
                            pnl: pnl,
                            result: 'LOSS'
                        })
                        position = null
                        stoppedOut = true
                    }
                } else {
                    if (bar.high >= stopLoss) {
                        const exitPrice = stopLoss
                        const pnl = entryPrice - exitPrice
                        trades.push({
                            entryDate: entryTime,
                            exitDate: bar.time,
                            entryPrice,
                            exitPrice,
                            direction: 'SHORT',
                            pnl: pnl,
                            result: 'LOSS'
                        })
                        position = null
                        stoppedOut = true
                    }
                }

                if (stoppedOut) continue

                // B. Check TP1 (Cover the Queen) - 50% exit
                // Calculate Target Price
                let tp1Target = 0
                const risk = Math.abs(entryPrice - stopLoss)

                if (tp_mode === 'BPS') {
                    // Basis points: Entry * (1 ± (bps / 10000))
                    // e.g. 10 bps = 10/10000 = 0.001
                    const adjustment = entryPrice * (tp_value / 10000)
                    tp1Target = position === 'LONG' ? (entryPrice + adjustment) : (entryPrice - adjustment)
                } else {
                    // R-Multiple
                    tp1Target = position === 'LONG' ? (entryPrice + (risk * tp_value)) : (entryPrice - (risk * tp_value))
                }

                if (!tp1Hit) {
                    const hitTp1 = position === 'LONG' ? (bar.high >= tp1Target) : (bar.low <= tp1Target)
                    if (hitTp1) {
                        // Log 50% profit
                        const pnl = Math.abs(entryPrice - tp1Target) // Exact profit per contract
                        // Note: We don't have "size" in Trade object yet, so we just log the PnL of this *segment*
                        trades.push({
                            entryDate: entryTime,
                            exitDate: bar.time,
                            entryPrice,
                            exitPrice: tp1Target,
                            direction: position!,
                            pnl: pnl,
                            result: 'WIN'
                        })
                        tp1Hit = true
                        // Move SL to Breakeven
                        stopLoss = entryPrice
                    }
                }

                // C. Hard Time Exit (9:44)
                if (isHardExitTime) {
                    // Close Remaining Position
                    const exitPrice = bar.close
                    const pnl = position === 'LONG' ? (exitPrice - entryPrice) : (entryPrice - exitPrice)

                    trades.push({
                        entryDate: entryTime,
                        exitDate: bar.time,
                        entryPrice,
                        exitPrice,
                        direction: position!,
                        pnl: pnl,
                        result: pnl > 0 ? 'WIN' : 'LOSS'
                    })
                    position = null
                }

                continue
            }

            // --- ENTRY LOGIC ---
            if (isExecutionWindow && !currentState.hasTraded) {
                // Breakout Confirmation: Close outside 9:30 range

                // Long Entry
                if (bar.close > currentState.rangeHigh) {
                    position = 'LONG'
                    entryPrice = bar.close
                    stopLoss = currentState.rangeLow
                    entryTime = bar.time
                    tp1Hit = false
                    currentState.hasTraded = true
                }
                // Short Entry
                else if (bar.close < currentState.rangeLow) {
                    position = 'SHORT'
                    entryPrice = bar.close
                    stopLoss = currentState.rangeHigh
                    entryTime = bar.time
                    tp1Hit = false
                    currentState.hasTraded = true
                }
            }
        }

        return trades
    }
}
