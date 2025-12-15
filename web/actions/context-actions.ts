"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"
import { fetchMarketData, fetchNews, YahooQuote, YahooNewsItem } from "@/lib/yahoo-finance"

export interface DashboardContext {
    marketData: YahooQuote[]
    news: YahooNewsItem[]
    dailyNote: any | null
    events: any[]
}

export async function getDashboardContext(): Promise<{ success: boolean, data?: DashboardContext, error?: string }> {
    try {
        const today = new Date()
        const startOfDay = new Date(today.setHours(0, 0, 0, 0))
        const endOfDay = new Date(today.setHours(23, 59, 59, 999))

        // 1. Fetch Market Data (VIX, VVIX, SPY, QQQ)
        const marketDataIn = fetchMarketData(["^VIX", "^VVIX", "SPY", "QQQ"])

        // 2. Fetch News (Market general)
        const newsIn = fetchNews("stock market analysis")

        // 3. Fetch Daily Note
        const noteIn = prisma.note.findFirst({
            where: {
                type: "DAY",
                date: {
                    gte: startOfDay,
                    lte: endOfDay
                }
            }
        })

        // 4. Fetch Economic Events for today
        const eventsIn = prisma.economicEvent.findMany({
            where: {
                datetime: {
                    gte: startOfDay,
                    lte: endOfDay
                }
            },
            orderBy: { datetime: 'asc' }
        })

        const [marketData, news, dailyNote, events] = await Promise.all([
            marketDataIn,
            newsIn,
            noteIn,
            eventsIn
        ])

        return {
            success: true,
            data: {
                marketData,
                news,
                dailyNote,
                events
            }
        }

    } catch (error) {
        console.error("getDashboardContext Error:", error)
        return { success: false, error: "Failed to fetch dashboard context" }
    }
}

export async function saveDailyContext(data: {
    bias?: "BULLISH" | "BEARISH" | "NEUTRAL"
    content: string
    keyLevels?: string
}) {
    try {
        const today = new Date()
        const startOfDay = new Date(today.setHours(0, 0, 0, 0))
        const endOfDay = new Date(today.setHours(23, 59, 59, 999))

        // Check if note exists for today
        const existingNote = await prisma.note.findFirst({
            where: { type: "DAY", date: { gte: startOfDay, lte: endOfDay } }
        })

        let note
        if (existingNote) {
            note = await prisma.note.update({
                where: { id: existingNote.id },
                data: {
                    content: data.content,
                    mood: data.bias, // Reusing mood field for bias
                    tags: JSON.stringify({ keyLevels: data.keyLevels })
                }
            })
        } else {
            note = await prisma.note.create({
                data: {
                    type: "DAY",
                    content: data.content,
                    mood: data.bias,
                    tags: JSON.stringify({ keyLevels: data.keyLevels })
                }
            })
        }

        revalidatePath("/journal/context")
        return { success: true, data: note }

    } catch (error) {
        console.error("saveDailyContext Error:", error)
        return { success: false, error: "Failed to save daily context" }
    }
}
