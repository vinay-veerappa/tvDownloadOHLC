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

        // 4. Fetch Economic Events (Hybrid: Live for Today/Future + DB Sync)

        // Strategy: 
        // 1. Fetch live events for "today" from ForexFactory
        // 2. If successful, display them AND upsert to DB (so they become history)
        // 3. If live fails, fall back to DB

        let events = []
        try {
            // Fetch from DB first (fastest, covers history)
            const dbEvents = await prisma.economicEvent.findMany({
                where: {
                    datetime: {
                        gte: startOfDay,
                        lte: endOfDay
                    }
                },
                orderBy: { datetime: 'asc' }
            })
            events = dbEvents

            // Try Live Fetch for today
            const { fetchLiveCalendar, mapImpact, syncLiveEventsToDb } = await import("@/lib/economic-calendar")
            const liveEvents = await fetchLiveCalendar()

            // Filter live events for *today* locally since feed gives whole week
            const todayStr = today.toISOString().split('T')[0]
            const todayLive = liveEvents.filter(e => e.date.startsWith(todayStr))

            if (todayLive.length > 0) {
                // We have live data! Use it for display.
                // Map to UI format (simulating DB model)
                events = todayLive.map(e => ({
                    id: `live-${e.date}-${e.title}`, // temp ID
                    name: e.title, // Map 'title' to 'name'
                    datetime: new Date(e.date),
                    impact: mapImpact(e.impact),
                    forecast: parseFloat(e.forecast) || null,
                    previous: parseFloat(e.previous) || null,
                    actual: null // FF feed often doesn't have actual immediately in this JSON
                }))

                // Async Sync to DB (Fire and forget, don't block UI)
                // This ensures "static history" requirement is met for tomorrow
                syncLiveEventsToDb(todayLive).catch(err => console.error("Sync events failed", err))
            }
        } catch (e) {
            console.error("Live calendar fetch failed, using DB events only", e)
        }

        const [marketData, news, dailyNote] = await Promise.all([
            marketDataIn,
            newsIn,
            noteIn
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

import { LiveEconomicEvent, syncLiveEventsToDb } from "@/lib/economic-calendar"

export async function syncLiveEvents(events: LiveEconomicEvent[]) {
    try {
        await syncLiveEventsToDb(events)
        return { success: true }
    } catch (e) {
        console.error("Sync action failed", e)
        return { success: false }
    }
}

import { fetchLiveCalendar } from "@/lib/economic-calendar"

export async function getLiveEconomicEvents() {
    try {
        const events = await fetchLiveCalendar()
        return { success: true, data: events }
    } catch (e) {
        console.error("Server fetch failed", e)
        return { success: false, error: "Failed to fetch events" }
    }
}
