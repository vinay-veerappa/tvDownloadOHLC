"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getPlaybooks() {
    try {
        const playbooks = await prisma.playbook.findMany({
            orderBy: { name: 'asc' }
        })
        return { success: true, data: playbooks }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function createPlaybook(name: string, description?: string, rules?: string) {
    try {
        const playbook = await prisma.playbook.create({
            data: { name, description, rules }
        })
        revalidatePath('/journal')
        return { success: true, data: playbook }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getPlaybookPerformance(dateRange?: { from: Date, to: Date }) {
    try {
        const where: any = { status: "CLOSED" }
        if (dateRange) {
            where.exitDate = {
                gte: dateRange.from,
                lte: dateRange.to
            }
        }

        const trades = await prisma.trade.findMany({
            where,
            include: { playbook: true }
        })

        const performanceMap = new Map<string, {
            id: string,
            name: string,
            wins: number,
            losses: number,
            totalPnl: number,
            tradeCount: number
        }>()

        // Initialize with "No Playbook"
        performanceMap.set("none", {
            id: "none",
            name: "No Playbook",
            wins: 0,
            losses: 0,
            totalPnl: 0,
            tradeCount: 0
        })

        trades.forEach(trade => {
            const playbookId = trade.playbookId || "none"
            const playbookName = trade.playbook?.name || "No Playbook"
            
            const stats = performanceMap.get(playbookId) || {
                id: playbookId,
                name: playbookName,
                wins: 0,
                losses: 0,
                totalPnl: 0,
                tradeCount: 0
            }

            const pnl = trade.pnl || 0
            stats.totalPnl += pnl
            stats.tradeCount++
            if (pnl > 0) stats.wins++
            else if (pnl < 0) stats.losses++

            performanceMap.set(playbookId, stats)
        })

        const data = Array.from(performanceMap.values()).map(stats => ({
            ...stats,
            winRate: stats.tradeCount > 0 ? (stats.wins / stats.tradeCount) * 100 : 0
        })).sort((a, b) => b.totalPnl - a.totalPnl)

        return { success: true, data }

    } catch (e) {
        return { success: false, error: String(e) }
    }
}
