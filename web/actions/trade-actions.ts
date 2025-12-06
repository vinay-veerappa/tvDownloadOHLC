"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

interface CreateTradeParams {
    ticker: string
    entryDate: Date
    entryPrice?: number
    quantity: number
    direction: "LONG" | "SHORT"
    status: "OPEN" | "PENDING"
    orderType: "MARKET" | "LIMIT" | "STOP"
    limitPrice?: number
    stopPrice?: number
    stopLoss?: number
    takeProfit?: number
    accountId: string
    strategyId?: string
    risk?: number // Intended risk
}

// ... types above ...

export async function getTrades() {
    try {
        const trades = await prisma.trade.findMany({
            orderBy: {
                entryDate: 'desc'
            },
            include: {
                account: true,
                strategy: true
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

export async function createTrade(data: CreateTradeParams) {
    try {
        const trade = await prisma.trade.create({
            data: {
                ticker: data.ticker,
                entryDate: data.entryDate,
                entryPrice: data.entryPrice,
                quantity: data.quantity,
                direction: data.direction,
                status: data.status,
                orderType: data.orderType,
                limitPrice: data.limitPrice,
                stopPrice: data.stopPrice,
                stopLoss: data.stopLoss,
                takeProfit: data.takeProfit,
                accountId: data.accountId,
                strategyId: data.strategyId,
                risk: data.risk
            }
        })

        revalidatePath("/")
        revalidatePath("/journal")

        return { success: true, data: trade }
    } catch (error) {
        console.error("createTrade Error:", error)
        // Log the data that caused the error
        console.error("Payload:", data)
        return { success: false, error: "Failed to create trade" }
    }
}

export async function closeTrade(id: string, data: {
    exitPrice: number
    exitDate: Date
    pnl: number
    mae?: number
    mfe?: number
    duration?: number
}) {
    try {
        const trade = await prisma.trade.update({
            where: { id },
            data: {
                ...data,
                status: "CLOSED"
            }
        })

        // TODO: Update Account Balance here if needed

        revalidatePath("/")
        revalidatePath("/journal")

        return { success: true, data: trade }
    } catch (error) {
        return { success: false, error: "Failed to close trade" }
    }
}
