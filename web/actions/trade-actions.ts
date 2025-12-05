"use server"

import { db } from "@/lib/db"
import { revalidatePath } from "next/cache"

export async function getTrades() {
    try {
        const trades = await db.trade.findMany({
            orderBy: {
                entryDate: 'desc'
            }
        })
        const mappedTrades = trades.map(t => ({
            ...t,
            symbol: t.ticker // Map ticker to symbol for frontend compatibility
        }))
        return { success: true, data: mappedTrades }
    } catch (error) {
        return { success: false, error: "Failed to fetch trades" }
    }
}

export async function createTrade(data: {
    symbol: string
    direction: "LONG" | "SHORT"
    entryDate: Date
    entryPrice: number
    quantity: number
    status: "OPEN" | "PENDING"
}) {
    try {
        const trade = await db.trade.create({
            data: {
                ...data,
                ticker: data.symbol,
                status: data.status,
            }
        })

        revalidatePath("/")
        revalidatePath("/journal")

        return { success: true, data: trade }
    } catch (error) {
        return { success: false, error: "Failed to create trade" }
    }
}
