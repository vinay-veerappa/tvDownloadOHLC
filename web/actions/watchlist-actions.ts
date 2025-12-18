"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getWatchlist() {
    try {
        const watchlist = await prisma.watchlist.findMany({
            orderBy: { createdAt: 'desc' }
        })
        // Return symbols as a simple array for easy checking
        return { success: true, data: watchlist }
    } catch (error) {
        console.error("getWatchlist Error:", error)
        return { success: false, error: "Failed to fetch watchlist" }
    }
}

export async function addToWatchlist(symbol: string) {
    try {
        let cleanSymbol = symbol.toUpperCase().trim()

        // Common Futures Validation
        // If user types "NQ" or "ES" or "NQ1!", normalize to "/NQ" for Schwab API
        const futuresRoots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG"]

        // Remove '!' if present (e.g. from TradingView style input)
        if (cleanSymbol.includes("!")) {
            cleanSymbol = cleanSymbol.replace("!", "")
        }

        // If it matches a known root exactly, prepend '/'
        if (futuresRoots.includes(cleanSymbol)) {
            cleanSymbol = "/" + cleanSymbol
        }

        // check if exists to avoid error (though unique constraint handles it)
        const existing = await prisma.watchlist.findUnique({
            where: { symbol: cleanSymbol }
        })

        if (existing) {
            return { success: false, error: "Symbol already in watchlist" }
        }

        const item = await prisma.watchlist.create({
            data: {
                symbol: cleanSymbol,
                name: cleanSymbol // We could fetch name from Yahoo later
            }
        })

        revalidatePath("/journal/context")
        return { success: true, data: item }
    } catch (error) {
        console.error("addToWatchlist Error:", error)
        return { success: false, error: "Failed to add to watchlist" }
    }
}

export async function removeFromWatchlist(id: string) {
    try {
        await prisma.watchlist.delete({
            where: { id }
        })

        revalidatePath("/journal/context")
        return { success: true }
    } catch (error) {
        console.error("removeFromWatchlist Error:", error)
        return { success: false, error: "Failed to remove from watchlist" }
    }
}

export async function searchTicker(query: string) {
    try {
        const { searchSymbols } = await import("@/lib/yahoo-finance")
        const results = await searchSymbols(query)
        return { success: true, data: results }
    } catch (error) {
        console.error("searchTicker Error:", error)
        return { success: false, error: "Failed to search tickers" }
    }
}

