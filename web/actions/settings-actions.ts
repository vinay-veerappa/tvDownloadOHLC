"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

// ============ ACCOUNTS ============

export async function getAccounts() {
    try {
        const accounts = await prisma.account.findMany({
            orderBy: { name: 'asc' },
            include: {
                _count: { select: { trades: true } }
            }
        })
        return { success: true, data: accounts }
    } catch (error) {
        console.error("getAccounts Error:", error)
        return { success: false, error: "Failed to fetch accounts" }
    }
}

export async function createAccount(data: {
    name: string
    initialBalance?: number
}) {
    try {
        const balance = data.initialBalance || 0
        const account = await prisma.account.create({
            data: {
                name: data.name,
                initialBalance: balance,
                currentBalance: balance
            }
        })
        revalidatePath("/journal/settings")
        revalidatePath("/journal")
        return { success: true, data: account }
    } catch (error) {
        console.error("createAccount Error:", error)
        return { success: false, error: "Failed to create account" }
    }
}

export async function updateAccount(id: string, data: {
    name?: string
    currentBalance?: number
}) {
    try {
        const account = await prisma.account.update({
            where: { id },
            data
        })
        revalidatePath("/journal/settings")
        revalidatePath("/journal")
        return { success: true, data: account }
    } catch (error) {
        console.error("updateAccount Error:", error)
        return { success: false, error: "Failed to update account" }
    }
}

export async function deleteAccount(id: string) {
    try {
        // Check if account has trades
        const count = await prisma.trade.count({ where: { accountId: id } })
        if (count > 0) {
            return { success: false, error: `Cannot delete account with ${count} trades. Delete trades first.` }
        }

        await prisma.account.delete({ where: { id } })
        revalidatePath("/journal/settings")
        revalidatePath("/journal")
        return { success: true }
    } catch (error) {
        console.error("deleteAccount Error:", error)
        return { success: false, error: "Failed to delete account" }
    }
}

// ============ STRATEGIES ============

export async function getStrategies() {
    try {
        const strategies = await prisma.strategy.findMany({
            orderBy: { name: 'asc' }
        })
        return { success: true, data: strategies }
    } catch (error) {
        console.error("getStrategies Error:", error)
        return { success: false, error: "Failed to fetch strategies" }
    }
}

export async function createStrategy(data: {
    name: string
    description?: string
}) {
    try {
        const strategy = await prisma.strategy.create({
            data: {
                name: data.name,
                description: data.description
            }
        })
        revalidatePath("/journal/settings")
        revalidatePath("/journal")
        return { success: true, data: strategy }
    } catch (error) {
        console.error("createStrategy Error:", error)
        return { success: false, error: "Failed to create strategy" }
    }
}

export async function updateStrategy(id: string, data: {
    name?: string
    description?: string
}) {
    try {
        const strategy = await prisma.strategy.update({
            where: { id },
            data
        })
        revalidatePath("/journal/settings")
        return { success: true, data: strategy }
    } catch (error) {
        console.error("updateStrategy Error:", error)
        return { success: false, error: "Failed to update strategy" }
    }
}

export async function deleteStrategy(id: string) {
    try {
        // Check if strategy has trades
        const count = await prisma.trade.count({ where: { strategyId: id } })
        if (count > 0) {
            return { success: false, error: `Cannot delete strategy with ${count} trades. Unlink trades first.` }
        }

        await prisma.strategy.delete({ where: { id } })
        revalidatePath("/journal/settings")
        return { success: true }
    } catch (error) {
        console.error("deleteStrategy Error:", error)
        return { success: false, error: "Failed to delete strategy" }
    }
}

// ============ TAGS ============

export async function getTagGroups() {
    try {
        const groups = await prisma.tagGroup.findMany({
            orderBy: { name: 'asc' }
        })
        return { success: true, data: groups }
    } catch (error) {
        console.error("getTagGroups Error:", error)
        return { success: false, error: "Failed to fetch tag groups" }
    }
}

export async function getTags() {
    try {
        const tags = await prisma.tag.findMany({
            orderBy: { name: 'asc' },
            include: { group: true }
        })
        return { success: true, data: tags }
    } catch (error) {
        console.error("getTags Error:", error)
        return { success: false, error: "Failed to fetch tags" }
    }
}

export async function createTag(data: {
    name: string
    groupId?: string
}) {
    try {
        const tag = await prisma.tag.create({
            data: {
                name: data.name,
                groupId: data.groupId || null
            }
        })
        revalidatePath("/journal/settings")
        return { success: true, data: tag }
    } catch (error) {
        console.error("createTag Error:", error)
        return { success: false, error: "Failed to create tag" }
    }
}

export async function deleteTag(id: string) {
    try {
        await prisma.tag.delete({ where: { id } })
        revalidatePath("/journal/settings")
        return { success: true }
    } catch (error) {
        console.error("deleteTag Error:", error)
        return { success: false, error: "Failed to delete tag" }
    }
}

// ============ DATA MANAGEMENT ============

export async function getOverviewStats() {
    try {
        const [tradeCount, accountCount, strategyCount, tagCount, trades] = await Promise.all([
            prisma.trade.count(),
            prisma.account.count(),
            prisma.strategy.count(),
            prisma.tag.count(),
            prisma.trade.findMany({
                where: { status: 'CLOSED' },
                select: { pnl: true }
            })
        ])

        const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0)
        const winningTrades = trades.filter(t => (t.pnl || 0) > 0).length
        const losingTrades = trades.filter(t => (t.pnl || 0) < 0).length

        return {
            success: true,
            data: {
                tradeCount,
                accountCount,
                strategyCount,
                tagCount,
                totalPnl,
                winningTrades,
                losingTrades,
                winRate: trades.length > 0 ? (winningTrades / trades.length) * 100 : 0
            }
        }
    } catch (error) {
        console.error("getOverviewStats Error:", error)
        return { success: false, error: "Failed to fetch stats" }
    }
}

export async function deleteAllTrades() {
    try {
        // Delete related records first
        await prisma.marketCondition.deleteMany({})
        await prisma.tradeEvent.deleteMany({})

        // Then delete trades
        const result = await prisma.trade.deleteMany({})

        revalidatePath("/journal")
        revalidatePath("/journal/settings")
        revalidatePath("/journal/analytics")

        return { success: true, deletedCount: result.count }
    } catch (error) {
        console.error("deleteAllTrades Error:", error)
        return { success: false, error: "Failed to delete trades" }
    }
}

export async function deleteTradesByDateRange(startDate: Date, endDate: Date) {
    try {
        // Find trades in range
        const tradesToDelete = await prisma.trade.findMany({
            where: {
                entryDate: {
                    gte: startDate,
                    lte: endDate
                }
            },
            select: { id: true }
        })

        const tradeIds = tradesToDelete.map(t => t.id)

        // Delete related records
        await prisma.marketCondition.deleteMany({
            where: { tradeId: { in: tradeIds } }
        })
        await prisma.tradeEvent.deleteMany({
            where: { tradeId: { in: tradeIds } }
        })

        // Delete trades
        const result = await prisma.trade.deleteMany({
            where: { id: { in: tradeIds } }
        })

        revalidatePath("/journal")
        revalidatePath("/journal/settings")
        revalidatePath("/journal/analytics")

        return { success: true, deletedCount: result.count }
    } catch (error) {
        console.error("deleteTradesByDateRange Error:", error)
        return { success: false, error: "Failed to delete trades" }
    }
}

export async function deleteTradesByAccount(accountId: string) {
    try {
        // Find trades for this account
        const tradesToDelete = await prisma.trade.findMany({
            where: { accountId },
            select: { id: true }
        })

        const tradeIds = tradesToDelete.map(t => t.id)

        // Delete related records
        await prisma.marketCondition.deleteMany({
            where: { tradeId: { in: tradeIds } }
        })
        await prisma.tradeEvent.deleteMany({
            where: { tradeId: { in: tradeIds } }
        })

        // Delete trades
        const result = await prisma.trade.deleteMany({
            where: { accountId }
        })

        revalidatePath("/journal")
        revalidatePath("/journal/settings")
        revalidatePath("/journal/analytics")

        return { success: true, deletedCount: result.count }
    } catch (error) {
        console.error("deleteTradesByAccount Error:", error)
        return { success: false, error: "Failed to delete trades" }
    }
}

export async function exportAllData() {
    try {
        const [trades, accounts, strategies, tags] = await Promise.all([
            prisma.trade.findMany({ include: { marketCondition: true } }),
            prisma.account.findMany(),
            prisma.strategy.findMany(),
            prisma.tag.findMany()
        ])

        return {
            success: true,
            data: {
                exportedAt: new Date().toISOString(),
                trades,
                accounts,
                strategies,
                tags
            }
        }
    } catch (error) {
        console.error("exportAllData Error:", error)
        return { success: false, error: "Failed to export data" }
    }
}
