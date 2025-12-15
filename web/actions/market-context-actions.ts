"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

// Session time ranges (Eastern Time) - moved to @/lib/market-utils
import { detectSession as detectSessionSync, detectTrend as detectTrendSync } from "@/lib/market-utils"

export async function detectSession(date: Date): Promise<string> {
    return detectSessionSync(date)
}

export async function detectTrend(entryPrice: number, prevClose?: number): Promise<string> {
    return detectTrendSync(entryPrice, prevClose)
}

interface MarketContextInput {
    tradeId: string
    vix?: number
    vvix?: number
    atr?: number
    trend?: string
    session?: string
    volume?: string
}

export async function createMarketCondition(data: MarketContextInput) {
    try {
        const condition = await prisma.marketCondition.create({
            data: {
                tradeId: data.tradeId,
                vix: data.vix,
                vvix: data.vvix,
                atr: data.atr,
                trend: data.trend,
                session: data.session,
                volume: data.volume
            }
        })

        revalidatePath(`/journal/trade/${data.tradeId}`)
        return { success: true, data: condition }
    } catch (error) {
        console.error("createMarketCondition Error:", error)
        return { success: false, error: "Failed to create market condition" }
    }
}

export async function updateMarketCondition(tradeId: string, updates: Partial<MarketContextInput>) {
    try {
        const condition = await prisma.marketCondition.upsert({
            where: { tradeId },
            update: {
                vix: updates.vix,
                vvix: updates.vvix,
                atr: updates.atr,
                trend: updates.trend,
                session: updates.session,
                volume: updates.volume
            },
            create: {
                tradeId,
                vix: updates.vix,
                vvix: updates.vvix,
                atr: updates.atr,
                trend: updates.trend,
                session: updates.session,
                volume: updates.volume
            }
        })

        revalidatePath(`/journal/trade/${tradeId}`)
        return { success: true, data: condition }
    } catch (error) {
        console.error("updateMarketCondition Error:", error)
        return { success: false, error: "Failed to update market condition" }
    }
}

export async function getMarketCondition(tradeId: string) {
    try {
        const condition = await prisma.marketCondition.findUnique({
            where: { tradeId }
        })
        return { success: true, data: condition }
    } catch (error) {
        console.error("getMarketCondition Error:", error)
        return { success: false, error: "Failed to fetch market condition" }
    }
}

// Economic Events

interface EconomicEventInput {
    datetime: Date
    name: string
    impact: "HIGH" | "MEDIUM" | "LOW"
    actual?: number
    forecast?: number
    previous?: number
}

export async function createEconomicEvent(data: EconomicEventInput) {
    try {
        const event = await prisma.economicEvent.create({
            data: {
                datetime: data.datetime,
                name: data.name,
                impact: data.impact,
                actual: data.actual,
                forecast: data.forecast,
                previous: data.previous
            }
        })

        revalidatePath("/journal")
        return { success: true, data: event }
    } catch (error) {
        console.error("createEconomicEvent Error:", error)
        return { success: false, error: "Failed to create economic event" }
    }
}

export async function getEconomicEvents(startDate: Date, endDate: Date) {
    try {
        const events = await prisma.economicEvent.findMany({
            where: {
                datetime: {
                    gte: startDate,
                    lte: endDate
                }
            },
            orderBy: { datetime: "asc" }
        })
        return { success: true, data: events }
    } catch (error) {
        console.error("getEconomicEvents Error:", error)
        return { success: false, error: "Failed to fetch economic events" }
    }
}

export async function linkTradeToEvent(tradeId: string, eventId: string) {
    try {
        await prisma.tradeEvent.create({
            data: { tradeId, eventId }
        })

        revalidatePath(`/journal/trade/${tradeId}`)
        return { success: true }
    } catch (error) {
        console.error("linkTradeToEvent Error:", error)
        return { success: false, error: "Failed to link trade to event" }
    }
}

export async function getEventsForTrade(tradeId: string) {
    try {
        const links = await prisma.tradeEvent.findMany({
            where: { tradeId },
            include: { event: true }
        })
        return { success: true, data: links.map(l => l.event) }
    } catch (error) {
        console.error("getEventsForTrade Error:", error)
        return { success: false, error: "Failed to fetch trade events" }
    }
}

// Find nearby economic events for a trade (within 1 hour before/after)
export async function findNearbyEvents(tradeDate: Date, windowHours: number = 1) {
    const startWindow = new Date(tradeDate.getTime() - windowHours * 60 * 60 * 1000)
    const endWindow = new Date(tradeDate.getTime() + windowHours * 60 * 60 * 1000)

    return getEconomicEvents(startWindow, endWindow)
}
