"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getWatchlistGroups() {
    try {
        const groups = await prisma.watchlistGroup.findMany({
            orderBy: [{ isDefault: 'desc' }, { createdAt: 'desc' }]
        })
        return { success: true, data: groups }
    } catch (error) {
        console.error("getWatchlistGroups Error:", error)
        return { success: false, error: "Failed to fetch groups" }
    }
}

export async function getWatchlistItems(groupId: string) {
    try {
        const items = await prisma.watchlistItem.findMany({
            where: { groupId },
            orderBy: { createdAt: 'desc' }
        })
        return { success: true, data: items }
    } catch (error) {
        console.error("getWatchlistItems Error:", error)
        return { success: false, error: "Failed to fetch items" }
    }
}

export async function createWatchlistGroup(name: string) {
    try {
        const group = await prisma.watchlistGroup.create({
            data: { name }
        })
        revalidatePath("/journal/context")
        return { success: true, data: group }
    } catch (error) {
        return { success: false, error: "Failed to create group" }
    }
}

export async function deleteWatchlistGroup(id: string) {
    try {
        await prisma.watchlistGroup.delete({ where: { id } })
        revalidatePath("/journal/context")
        return { success: true }
    } catch (error) {
        return { success: false, error: "Failed to delete group" }
    }
}

export async function addToWatchlist(symbol: string, groupId?: string) {
    try {
        let cleanSymbol = symbol.toUpperCase().trim()
        const futuresRoots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"]
        if (cleanSymbol.includes("!")) cleanSymbol = cleanSymbol.replace("!", "")
        if (futuresRoots.includes(cleanSymbol)) cleanSymbol = "/" + cleanSymbol

        // Resolve Group
        let targetGroupId = groupId
        if (!targetGroupId) {
            // Find or create Default
            let defaultGroup = await prisma.watchlistGroup.findFirst({ where: { isDefault: true } })
            if (!defaultGroup) {
                // Try finding by name "Default"
                defaultGroup = await prisma.watchlistGroup.findUnique({ where: { name: "Default" } })
                if (!defaultGroup) {
                    defaultGroup = await prisma.watchlistGroup.create({
                        data: { name: "Default", isDefault: true }
                    })
                }
            }
            targetGroupId = defaultGroup.id
        }

        const existing = await prisma.watchlistItem.findFirst({
            where: { symbol: cleanSymbol, groupId: targetGroupId }
        })

        if (existing) return { success: false, error: "Symbol already in list" }

        const item = await prisma.watchlistItem.create({
            data: {
                symbol: cleanSymbol,
                name: cleanSymbol,
                groupId: targetGroupId
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
        await prisma.watchlistItem.delete({ where: { id } })
        revalidatePath("/journal/context")
        return { success: true }
    } catch (error) {
        return { success: false, error: "Failed to remove" }
    }
}

export async function searchTicker(query: string) {
    try {
        const { searchSymbols } = await import("@/lib/yahoo-finance")
        const results = await searchSymbols(query)
        return { success: true, data: results }
    } catch (error) {
        return { success: false, error: "Search failed" }
    }
}

export async function seedDefaultWatchlist() {
    try {
        const { DEFAULT_WATCHLIST } = await import("@/lib/watchlist-constants")

        // Ensure Default Group
        let defaultGroup = await prisma.watchlistGroup.findFirst({ where: { isDefault: true } })
        if (!defaultGroup) {
            defaultGroup = await prisma.watchlistGroup.create({
                data: { name: "Default", isDefault: true }
            })
        }

        for (const sym of DEFAULT_WATCHLIST) {
            const existing = await prisma.watchlistItem.findFirst({
                where: { symbol: sym, groupId: defaultGroup.id }
            })
            if (!existing) {
                await prisma.watchlistItem.create({
                    data: { symbol: sym, name: sym, groupId: defaultGroup.id }
                })
            }
        }

        revalidatePath("/journal/context")
        return { success: true }
    } catch (error) {
        return { success: false, error: "Seed failed" }
    }
}


