"use server"

import { runBacktest, BacktestConfig, BacktestResult } from "@/lib/backtest/runner"

import prisma from "@/lib/prisma"
import fs from "fs"
import path from "path"

export async function executeBacktest(config: BacktestConfig): Promise<{ success: boolean, result?: BacktestResult, error?: string }> {
    const logFile = path.join(process.cwd(), "backtest_debug.log")
    fs.appendFileSync(logFile, `executeBacktest called with: ${JSON.stringify(config)}\n`)

    try {
        const result = await runBacktest(config)
        fs.appendFileSync(logFile, `executeBacktest success: ${result.totalTrades} trades\n`)

        // Save to Database
        try {
            await prisma.backtestResult.create({
                data: {
                    strategy: config.strategy,
                    ticker: config.ticker,
                    timeframe: config.timeframe,
                    startDate: new Date(result.startDate * 1000),
                    endDate: new Date(result.endDate * 1000),
                    totalTrades: result.totalTrades,
                    winRate: result.winRate,
                    profitFactor: result.profitFactor,
                    totalPnl: result.totalPnl,
                    config: JSON.stringify(config.params),
                    trades: JSON.stringify(result.trades)
                }
            })
            fs.appendFileSync(logFile, `Saved backtest result to DB\n`)
        } catch (dbError) {
            console.error("Failed to save backtest result:", dbError)
            fs.appendFileSync(logFile, `Failed to save backtest result: ${dbError}\n`)
            // Don't fail the request if saving fails, just log it
        }

        return { success: true, result }
    } catch (error) {
        fs.appendFileSync(logFile, `Backtest failed: ${error}\n`)
        console.error("Backtest failed:", error)
        return { success: false, error: "Backtest failed execution" }
    }
}
