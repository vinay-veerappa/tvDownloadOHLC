"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"
import { fetchMarketData, fetchNews, YahooQuote, YahooNewsItem } from "@/lib/yahoo-finance"

export interface DashboardContext {
    marketData: YahooQuote[]
    news: YahooNewsItem[]
    dailyNote: any | null
    events: any[]
    watchlist: any[]
}

export async function getDashboardContext(): Promise<{ success: boolean, data?: DashboardContext, error?: string }> {
    try {
        const today = new Date()
        const startOfDay = new Date(today.setHours(0, 0, 0, 0))
        const endOfDay = new Date(today.setHours(23, 59, 59, 999))

        // 0. Fetch Watchlist
        const watchlist = await prisma.watchlist.findMany({
            orderBy: { createdAt: 'desc' }
        })
        const watchlistSymbols = watchlist.map(w => w.symbol)

        // 1. Fetch Market Data (VIX, VVIX, SPY, QQQ + Watchlist)
        const defaultSymbols = ["^VIX", "^VVIX", "SPY", "QQQ"]
        // Deduplicate symbols
        const allSymbols = Array.from(new Set([...defaultSymbols, ...watchlistSymbols]))

        const marketDataIn = fetchMarketData(allSymbols)

        // 2. Fetch News (Prioritize Watchlist + Generals)
        // Construct query: "SPY OR NVDA OR QQQ news"
        // Limit query length/complexity: pick top 3 watchlist items + SPY to keep it relevant
        const keySymbols = ["SPY", ...watchlistSymbols.slice(0, 3)]
        const newsQuery = keySymbols.join(" OR ") + " market news"
        const newsIn = fetchNews(newsQuery)

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
                events,
                watchlist
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
