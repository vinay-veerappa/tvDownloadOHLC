"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export interface CsvTradeRow {
    ticker: string
    direction: "LONG" | "SHORT"
    entryDate: string // ISO date string
    exitDate?: string
    entryPrice: number
    exitPrice?: number
    quantity: number
    pnl?: number
    stopLoss?: number
    takeProfit?: number
    notes?: string
    strategy?: string
}

// Export trades to CSV format
export async function exportTradesToCsv(filters?: {
    accountId?: string
    strategyId?: string
    startDate?: Date
    endDate?: Date
}) {
    try {
        const where: any = {}

        if (filters?.accountId) where.accountId = filters.accountId
        if (filters?.strategyId) where.strategyId = filters.strategyId
        if (filters?.startDate || filters?.endDate) {
            where.entryDate = {}
            if (filters.startDate) where.entryDate.gte = filters.startDate
            if (filters.endDate) where.entryDate.lte = filters.endDate
        }

        const trades = await prisma.trade.findMany({
            where,
            include: { strategy: true, account: true },
            orderBy: { entryDate: "asc" }
        })

        const csvHeader = [
            "id", "ticker", "direction", "entryDate", "exitDate",
            "entryPrice", "exitPrice", "quantity", "pnl",
            "stopLoss", "takeProfit", "status", "strategy", "account", "notes"
        ].join(",")

        const csvRows = trades.map(t => [
            t.id,
            t.ticker,
            t.direction,
            t.entryDate.toISOString(),
            t.exitDate?.toISOString() || "",
            t.entryPrice,
            t.exitPrice || "",
            t.quantity,
            t.pnl || "",
            t.stopLoss || "",
            t.takeProfit || "",
            t.status,
            t.strategy?.name || "",
            t.account?.name || "",
            `"${(t.notes || "").replace(/"/g, '""')}"`
        ].join(","))

        const csv = [csvHeader, ...csvRows].join("\n")

        return { success: true, data: csv, count: trades.length }
    } catch (error) {
        console.error("Export failed:", error)
        return { success: false, error: "Failed to export trades" }
    }
}

// Import trades from CSV
export async function importTradesFromCsv(
    csvContent: string,
    accountId: string,
    defaultStrategy?: string
) {
    try {
        const lines = csvContent.split("\n").filter(line => line.trim())
        if (lines.length < 2) {
            return { success: false, error: "CSV must have header and at least one data row" }
        }

        const header = lines[0].toLowerCase().split(",").map(h => h.trim())
        const dataLines = lines.slice(1)

        // Map column indices
        const colIdx = {
            ticker: header.indexOf("ticker") >= 0 ? header.indexOf("ticker") : header.indexOf("symbol"),
            direction: header.indexOf("direction"),
            entryDate: header.indexOf("entrydate") >= 0 ? header.indexOf("entrydate") : header.indexOf("entry_date"),
            exitDate: header.indexOf("exitdate") >= 0 ? header.indexOf("exitdate") : header.indexOf("exit_date"),
            entryPrice: header.indexOf("entryprice") >= 0 ? header.indexOf("entryprice") : header.indexOf("entry_price"),
            exitPrice: header.indexOf("exitprice") >= 0 ? header.indexOf("exitprice") : header.indexOf("exit_price"),
            quantity: header.indexOf("quantity") >= 0 ? header.indexOf("quantity") : header.indexOf("qty"),
            pnl: header.indexOf("pnl") >= 0 ? header.indexOf("pnl") : header.indexOf("profit"),
            stopLoss: header.indexOf("stoploss") >= 0 ? header.indexOf("stoploss") : header.indexOf("sl"),
            takeProfit: header.indexOf("takeprofit") >= 0 ? header.indexOf("takeprofit") : header.indexOf("tp"),
            notes: header.indexOf("notes"),
            strategy: header.indexOf("strategy")
        }

        if (colIdx.ticker < 0 || colIdx.direction < 0 || colIdx.entryDate < 0 || colIdx.entryPrice < 0) {
            return { success: false, error: "CSV must have columns: ticker, direction, entryDate, entryPrice" }
        }

        // Find or create default strategy
        let strategyId: string | undefined
        if (defaultStrategy) {
            const existing = await prisma.strategy.findFirst({ where: { name: defaultStrategy } })
            if (existing) {
                strategyId = existing.id
            } else {
                const newStrat = await prisma.strategy.create({
                    data: { name: defaultStrategy, color: "#607D8B" }
                })
                strategyId = newStrat.id
            }
        }

        const trades: any[] = []
        let errors: string[] = []

        for (let i = 0; i < dataLines.length; i++) {
            const line = dataLines[i]
            const cols = parseCsvLine(line)

            try {
                const ticker = cols[colIdx.ticker]?.trim()
                const direction = cols[colIdx.direction]?.trim().toUpperCase()
                const entryDateStr = cols[colIdx.entryDate]?.trim()
                const entryPriceStr = cols[colIdx.entryPrice]?.trim()

                if (!ticker || !direction || !entryDateStr || !entryPriceStr) {
                    errors.push(`Row ${i + 2}: Missing required field`)
                    continue
                }

                const entryDate = new Date(entryDateStr)
                if (isNaN(entryDate.getTime())) {
                    errors.push(`Row ${i + 2}: Invalid entry date`)
                    continue
                }

                const entryPrice = parseFloat(entryPriceStr)
                if (isNaN(entryPrice)) {
                    errors.push(`Row ${i + 2}: Invalid entry price`)
                    continue
                }

                const exitDateStr = colIdx.exitDate >= 0 ? cols[colIdx.exitDate]?.trim() : undefined
                const exitPriceStr = colIdx.exitPrice >= 0 ? cols[colIdx.exitPrice]?.trim() : undefined

                let exitDate: Date | undefined
                let exitPrice: number | undefined

                if (exitDateStr) {
                    exitDate = new Date(exitDateStr)
                    if (isNaN(exitDate.getTime())) exitDate = undefined
                }
                if (exitPriceStr) {
                    exitPrice = parseFloat(exitPriceStr)
                    if (isNaN(exitPrice)) exitPrice = undefined
                }

                const quantity = colIdx.quantity >= 0 ? parseFloat(cols[colIdx.quantity]) || 1 : 1
                const pnl = colIdx.pnl >= 0 ? parseFloat(cols[colIdx.pnl]) || undefined : undefined
                const stopLoss = colIdx.stopLoss >= 0 ? parseFloat(cols[colIdx.stopLoss]) || undefined : undefined
                const takeProfit = colIdx.takeProfit >= 0 ? parseFloat(cols[colIdx.takeProfit]) || undefined : undefined
                const notes = colIdx.notes >= 0 ? cols[colIdx.notes]?.trim() : undefined

                // Status
                const status = exitDate && exitPrice ? "CLOSED" : "OPEN"

                trades.push({
                    accountId,
                    strategyId,
                    ticker,
                    direction: direction as "LONG" | "SHORT",
                    entryDate,
                    exitDate,
                    entryPrice,
                    exitPrice,
                    quantity,
                    pnl,
                    stopLoss,
                    takeProfit,
                    notes,
                    status,
                    orderType: "MARKET"
                })
            } catch (err) {
                errors.push(`Row ${i + 2}: Parse error`)
            }
        }

        if (trades.length === 0) {
            return { success: false, error: "No valid trades found", errors }
        }

        // Bulk insert
        const CHUNK_SIZE = 50
        for (let i = 0; i < trades.length; i += CHUNK_SIZE) {
            const chunk = trades.slice(i, i + CHUNK_SIZE)
            await prisma.trade.createMany({ data: chunk })
        }

        revalidatePath("/journal")

        return {
            success: true,
            imported: trades.length,
            errors: errors.length > 0 ? errors.slice(0, 10) : undefined
        }
    } catch (error) {
        console.error("Import failed:", error)
        return { success: false, error: String(error) }
    }
}

// Helper to parse CSV line with quote handling
function parseCsvLine(line: string): string[] {
    const result: string[] = []
    let current = ""
    let inQuotes = false

    for (let i = 0; i < line.length; i++) {
        const char = line[i]
        if (char === '"') {
            inQuotes = !inQuotes
        } else if (char === "," && !inQuotes) {
            result.push(current.trim())
            current = ""
        } else {
            current += char
        }
    }
    result.push(current.trim())
    return result
}

// Get backtest results for import UI
export async function getBacktestResults() {
    try {
        const results = await prisma.backtestResult.findMany({
            orderBy: { createdAt: "desc" },
            take: 20
        })

        return {
            success: true,
            data: results.map(r => ({
                id: r.id,
                strategy: r.strategy,
                ticker: r.ticker,
                timeframe: r.timeframe,
                totalTrades: r.totalTrades,
                winRate: r.winRate,
                totalPnl: r.totalPnl,
                createdAt: r.createdAt.toISOString()
            }))
        }
    } catch (error) {
        console.error("Failed to get backtest results:", error)
        return { success: false, error: "Failed to fetch backtest results" }
    }
}

// Import specific backtest result to journal
export async function importBacktestToJournal(backtestId: string, accountName?: string) {
    try {
        const backtest = await prisma.backtestResult.findUnique({
            where: { id: backtestId }
        })

        if (!backtest) {
            return { success: false, error: "Backtest result not found" }
        }

        const trades = JSON.parse(backtest.trades)
        const config = JSON.parse(backtest.config)

        // Use existing exportToJournal logic
        const { exportToJournal } = await import("./backtest-exporter")

        return exportToJournal(
            trades,
            accountName || `Backtest: ${backtest.strategy}`,
            { ...config, ticker: backtest.ticker }
        )
    } catch (error) {
        console.error("Import backtest failed:", error)
        return { success: false, error: String(error) }
    }
}
