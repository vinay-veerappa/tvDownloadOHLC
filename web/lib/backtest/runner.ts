import { getChartData } from "@/actions/data-actions"
import { BacktestConfig, BacktestResult, OHLCData } from "./types"
import { STRATEGIES } from "./strategies"

// Re-export types for consumers
export type { BacktestConfig, BacktestResult }

export async function runBacktest(config: BacktestConfig): Promise<BacktestResult> {
    console.log("Running backtest with config:", config)

    // 1. Select Strategy
    const strategy = STRATEGIES[config.strategy]
    if (!strategy) {
        throw new Error(`Strategy ${config.strategy} not found`)
    }

    // 2. Load Data
    // Load ALL data for backtest
    const dataResult = await getChartData(config.ticker, config.timeframe, -1)
    if (!dataResult.success || !dataResult.data) {
        throw new Error(`Failed to load data for ${config.ticker} ${config.timeframe}`)
    }

    const data = dataResult.data as OHLCData[]

    // 3. Run Strategy
    const trades = await strategy.run(data, config.params)

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
        startDate: data.length > 0 ? data[0].time : 0,
        endDate: data.length > 0 ? data[data.length - 1].time : 0,
        trades
    }
}
