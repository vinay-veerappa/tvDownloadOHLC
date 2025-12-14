'use server'

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"
import { Trade } from "@/lib/backtest/types"

export async function exportToJournal(trades: Trade[], accountName: string, config: any) {
    try {
        // 1. Create a new Account for this backtest run
        // We append a timestamp to ensure uniqueness if run multiple times
        const uniqueName = `${accountName} (${new Date().toLocaleString()})`

        const account = await prisma.account.create({
            data: {
                name: uniqueName,
                initialBalance: 100000, // Dummy balance
                currentBalance: 100000 + trades.reduce((sum, t) => sum + (t.pnl * 20), 0), // Approx NQ point value $20
                currency: "USD",
                isDefault: false
            }
        })

        if (!account) throw new Error("Failed to create account")

        // 2. Create Strategy if needed
        let strategyId: string | undefined
        const stratName = config.strategy || "Backtest Strategy"

        const strategy = await prisma.strategy.findFirst({ where: { name: stratName } })
        if (strategy) {
            strategyId = strategy.id
        } else {
            const newStrat = await prisma.strategy.create({
                data: { name: stratName, color: "#FF9800" }
            })
            strategyId = newStrat.id
        }

        // 3. Bulk Insert Trades
        // Prisma createMany is efficient
        const tradeData = trades.map(t => ({
            accountId: account.id,
            strategyId: strategyId,
            ticker: config.ticker || "NQ1!",
            entryDate: new Date(t.entryDate * 1000),
            exitDate: new Date(t.exitDate * 1000),
            entryPrice: t.entryPrice,
            exitPrice: t.exitPrice,
            quantity: 1, // Default 1 contract
            direction: t.direction,
            status: "CLOSED",
            pnl: t.pnl * 20, // Convert points to Dollar PnL (assuming NQ $20/pt)
            orderType: "MARKET", // Simulation assumption
            metadata: t.metadata ? JSON.stringify(t.metadata) : undefined
        }))

        // Chunking the inserts to avoid parameter limits (SQLite limit 999)
        const CHUNK_SIZE = 50
        for (let i = 0; i < tradeData.length; i += CHUNK_SIZE) {
            const chunk = tradeData.slice(i, i + CHUNK_SIZE)
            await prisma.trade.createMany({
                data: chunk
            })
        }

        revalidatePath('/journal')
        return { success: true, accountName: uniqueName }

    } catch (error) {
        console.error("Export failed:", error)
        return { success: false, error: String(error) }
    }
}
