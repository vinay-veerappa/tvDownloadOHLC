import { getChartData } from "@/actions/data-actions"
import { calculateSMA } from "@/lib/charts/indicators"

export interface BacktestConfig {
    ticker: string
    timeframe: string
    strategy: string
    params: Record<string, any>
}

export interface BacktestResult {
    totalTrades: number
    winRate: number
    profitFactor: number
    totalPnl: number
    startDate: number
    endDate: number
    trades: any[]
}

export async function runBacktest(config: BacktestConfig): Promise<BacktestResult> {
    console.log("Running backtest with config:", config)

    // 1. Load Data
    const dataResult = await getChartData(config.ticker, config.timeframe)
    if (!dataResult.success || !dataResult.data) {
        throw new Error(`Failed to load data for ${config.ticker} ${config.timeframe}`)
    }

    const data = dataResult.data

    // 2. Prepare Indicators
    // Simple SMA Crossover Strategy
    const fastPeriod = config.params.fastPeriod || 9
    const slowPeriod = config.params.slowPeriod || 21

    const fastSMA = calculateSMA(data as any[], fastPeriod)
    const slowSMA = calculateSMA(data as any[], slowPeriod)

    // Create Maps for O(1) lookup by time
    const fastSMAMap = new Map(fastSMA.map(i => [i.time as number, i.value]))
    const slowSMAMap = new Map(slowSMA.map(i => [i.time as number, i.value]))

    // 3. Run Simulation
    const trades: any[] = []
    let position: 'LONG' | 'SHORT' | null = null
    let entryPrice = 0
    let entryIndex = 0

    // Start after enough data for indicators
    const startIndex = Math.max(fastPeriod, slowPeriod)

    for (let i = startIndex; i < data.length; i++) {
        const currentTime = data[i].time as number
        const prevTime = data[i - 1].time as number

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

    // 4. Calculate Stats
    const totalTrades = trades.length
    const wins = trades.filter(t => t.result === 'WIN').length
    const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0
    const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0)
    const grossProfit = trades.filter(t => t.pnl > 0).reduce((sum, t) => sum + t.pnl, 0)
    const grossLoss = Math.abs(trades.filter(t => t.pnl < 0).reduce((sum, t) => sum + t.pnl, 0))
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0

    return {
        totalTrades,
        winRate,
        profitFactor,
        totalPnl,
        startDate: data.length > 0 ? (data[0].time as number) : 0,
        endDate: data.length > 0 ? (data[data.length - 1].time as number) : 0,
        trades
    }
}
