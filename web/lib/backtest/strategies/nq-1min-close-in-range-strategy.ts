import { Strategy, OHLCData, Trade } from "../types"

interface DailyState {
    date: string
    rangeHigh: number
    rangeLow: number
    rangeDefined: boolean
    hasTraded: boolean
}

export class Nq1MinCloseInRangeStrategy implements Strategy {
    name = "NQ_1MIN_CLOSE_IN_RANGE_STRATEGY"

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
        const max_trades = params.max_trades !== undefined ? params.max_trades : -1
        const penetration_threshold = params.penetration_threshold !== undefined ? params.penetration_threshold : 0.0
        const max_range_pct = params.max_range_pct !== undefined ? params.max_range_pct : 0.0 // Default 0 means disabled


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
        let currentTpTarget = 0 // Track TP for visualization
        let entryTime = 0
        let tp1Hit = false

        // MAE/MFE Tracking
        let maxAdverse = 0 // Price
        let maxFavorable = 0 // Price

        for (let i = 0; i < data.length; i++) {
            // Check max trades limit
            if (max_trades > 0 && trades.length >= max_trades) {
                break;
            }

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
                        pnl: pnl,
                        result: pnl > 0 ? 'WIN' : 'LOSS',
                        mae: maxAdverse,
                        mfe: maxFavorable,
                        tpPrice: currentTpTarget,
                        slPrice: stopLoss,
                        exitReason: 'NEW_DAY',
                        metadata: {
                            rangeHigh: currentState.rangeHigh,
                            rangeLow: currentState.rangeLow
                        }

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

            // 3. Execution Window (9:31 - Exit)
            let isHardExitTime = false;
            if (time.hour > exit_hour || (time.hour === exit_hour && time.minute >= exit_minute)) {
                isHardExitTime = true
            }

            let isExecutionWindow = false
            if (time.hour === 9 && time.minute >= 31) {
                if (!isHardExitTime) isExecutionWindow = true
            }

            // --- TRADE MANAGEMENT ---
            if (position) {
                // UPDATE MAE/MFE
                if (position === 'LONG') {
                    // Adverse = Low
                    if (bar.low < maxAdverse) maxAdverse = bar.low
                    // Favorable = High
                    if (bar.high > maxFavorable) maxFavorable = bar.high
                } else {
                    // Short
                    // Adverse = High
                    if (bar.high > maxAdverse) maxAdverse = bar.high
                    // Favorable = Low
                    if (bar.low < maxFavorable) maxFavorable = bar.low
                }

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
                            result: 'LOSS',
                            mae: maxAdverse, // Logic above captured bar.low
                            mfe: maxFavorable,
                            tpPrice: currentTpTarget,
                            slPrice: stopLoss,
                            exitReason: 'SL',
                            metadata: {
                                rangeHigh: currentState.rangeHigh,
                                rangeLow: currentState.rangeLow
                            }


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
                            result: 'LOSS',
                            mae: maxAdverse,
                            mfe: maxFavorable,
                            tpPrice: currentTpTarget,
                            slPrice: stopLoss,
                            exitReason: 'SL',
                            metadata: {
                                rangeHigh: currentState.rangeHigh,
                                rangeLow: currentState.rangeLow
                            }


                        })
                        position = null
                        stoppedOut = true
                    }
                }

                if (stoppedOut) continue

                // B. Check TP1 (Cover the Queen) - 50% exit (Not implemented as separate trades here, standard exit is full close)
                // The original code handled partials by potentially pushing a trade and keeping position open?
                // Wait, original code:
                /*
                        trades.push({ ... })
                        tp1Hit = true
                        stopLoss = entryPrice
                */
                // It PUSHES a trade but DOES NOT set position=null. It sets tp1Hit=true and moves SL.
                // So it treats TP1 as a partial exit event but keeps the loop running for the rest?
                // Actually the "trades" array implies individual closed trade segments.
                // But `position` remains not null.

                let tp1Target = currentTpTarget

                if (!tp1Hit) {
                    const hitTp1 = position === 'LONG' ? (bar.high >= tp1Target) : (bar.low <= tp1Target)
                    if (hitTp1) {
                        // Log 50% profit
                        const pnl = Math.abs(entryPrice - tp1Target)
                        trades.push({
                            entryDate: entryTime,
                            exitDate: bar.time,
                            entryPrice,
                            exitPrice: tp1Target,
                            direction: position!,
                            pnl: pnl,
                            result: 'WIN',
                            mae: maxAdverse,
                            mfe: maxFavorable,
                            tpPrice: currentTpTarget,
                            slPrice: stopLoss,
                            exitReason: 'TP1',
                            metadata: {
                                rangeHigh: currentState.rangeHigh,
                                rangeLow: currentState.rangeLow
                            }

                        })
                        tp1Hit = true
                        // Move SL to Breakeven
                        stopLoss = entryPrice
                    }
                }

                // C. Check Close Inside Range (NEW LOGIC with Threshold)
                let closedInsideRange = false
                const rangeSize = currentState.rangeHigh - currentState.rangeLow

                if (position === 'LONG') {
                    // Breakout was above RangeHigh. Retracement is going DOWN.
                    // 0% penetration = RangeHigh
                    // 100% penetration = RangeLow
                    // Threshold 0.25 means we tolerate drop to High - (0.25 * Range)
                    const exitThreshold = currentState.rangeHigh - (rangeSize * penetration_threshold)

                    if (bar.close <= exitThreshold) {
                        closedInsideRange = true
                    }
                } else {
                    // Breakout was below RangeLow. Retracement is going UP.
                    // 0% penetration = RangeLow
                    // 100% penetration = RangeHigh
                    // Threshold 0.25 means we tolerate rise to Low + (0.25 * Range)
                    const exitThreshold = currentState.rangeLow + (rangeSize * penetration_threshold)

                    if (bar.close >= exitThreshold) {
                        closedInsideRange = true
                    }
                }

                if (closedInsideRange) {
                    const exitPrice = bar.close
                    const pnl = position === 'LONG' ? (exitPrice - entryPrice) : (entryPrice - exitPrice)

                    trades.push({
                        entryDate: entryTime,
                        exitDate: bar.time,
                        entryPrice,
                        exitPrice,
                        direction: position!,
                        pnl: pnl,
                        result: pnl > 0 ? 'WIN' : 'LOSS',
                        mae: maxAdverse,
                        mfe: maxFavorable,
                        tpPrice: currentTpTarget,
                        slPrice: stopLoss,
                        exitReason: 'CLOSE_INSIDE_RANGE',
                        metadata: {
                            rangeHigh: currentState.rangeHigh,
                            rangeLow: currentState.rangeLow
                        }

                    })
                    position = null
                    continue
                }


                // D. Hard Time Exit (9:44)
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
                        result: pnl > 0 ? 'WIN' : 'LOSS',
                        mae: maxAdverse,
                        mfe: maxFavorable,
                        tpPrice: currentTpTarget,
                        slPrice: stopLoss,
                        exitReason: 'TIME_EXIT',
                        metadata: {
                            rangeHigh: currentState.rangeHigh,
                            rangeLow: currentState.rangeLow
                        }

                    })
                    position = null
                }

                continue
            }

            // --- ENTRY LOGIC ---
            if (isExecutionWindow && !currentState.hasTraded) {
                // Check Range Filter (if enabled)
                if (max_range_pct > 0) {
                    const rangeSize = currentState.rangeHigh - currentState.rangeLow
                    const rangePct = (rangeSize / bar.close) * 100 // Use current price approx for %
                    if (rangePct > max_range_pct) {
                        // Skip day
                        currentState.hasTraded = true // Mark as "handled" so we don't try every candle
                        continue
                    }
                }

                // Breakout Confirmation: Close outside 9:30 range

                // Long Entry
                if (bar.close > currentState.rangeHigh) {
                    position = 'LONG'
                    entryPrice = bar.close
                    stopLoss = currentState.rangeLow
                    entryTime = bar.time
                    tp1Hit = false
                    currentState.hasTraded = true

                    // Init MAE/MFE
                    maxAdverse = entryPrice
                    maxFavorable = entryPrice

                    // Calculate TP
                    const risk = Math.abs(entryPrice - stopLoss)
                    if (tp_mode === 'BPS') {
                        const adjustment = entryPrice * (tp_value / 10000)
                        currentTpTarget = entryPrice + adjustment
                    } else {
                        currentTpTarget = entryPrice + (risk * tp_value)
                    }
                }
                // Short Entry
                else if (bar.close < currentState.rangeLow) {
                    position = 'SHORT'
                    entryPrice = bar.close
                    stopLoss = currentState.rangeHigh
                    entryTime = bar.time
                    tp1Hit = false
                    currentState.hasTraded = true

                    // Init MAE/MFE
                    maxAdverse = entryPrice
                    maxFavorable = entryPrice

                    // Calculate TP
                    const risk = Math.abs(entryPrice - stopLoss)
                    if (tp_mode === 'BPS') {
                        const adjustment = entryPrice * (tp_value / 10000)
                        currentTpTarget = entryPrice - adjustment
                    } else {
                        currentTpTarget = entryPrice - (risk * tp_value)
                    }
                }
            }
        }

        return trades
    }
}
