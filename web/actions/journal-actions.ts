"use server"

import prisma from "@/lib/prisma"
import { startOfDay, startOfWeek, startOfMonth, subDays, eachDayOfInterval, format } from "date-fns"

export interface DashboardFilters {
    accountId?: string
    groupId?: string
    strategyId?: string
    dateRange?: {
        from: Date
        to: Date
    }
}

export interface AggregatedStats {
    totalPnl: number
    winRate: number
    profitFactor: number
    totalTrades: number
    avgWin: number
    avgLoss: number
    expectancy: number
    rMultiple: number
    bestDay: number
    worstDay: number
    consecutiveWins: number
    consecutiveLosses: number
}

// Helper to build WHERE clause
function buildWhereClause(filters?: DashboardFilters) {
    const where: any = { status: "CLOSED" }

    if (filters?.accountId) {
        where.accountId = filters.accountId
    } else if (filters?.groupId) {
        where.account = { groupId: filters.groupId }
    }

    if (filters?.strategyId) {
        where.strategyId = filters.strategyId
    }

    if (filters?.dateRange) {
        where.exitDate = {
            gte: filters.dateRange.from,
            lte: filters.dateRange.to
        }
    }

    return where
}

export async function getAggregatedStats(filters?: DashboardFilters): Promise<{ success: boolean; data?: AggregatedStats }> {
    try {
        const where = buildWhereClause(filters)
        const trades = await prisma.trade.findMany({
            where,
            orderBy: { exitDate: "asc" }
        })

        if (trades.length === 0) {
            return {
                success: true,
                data: {
                    totalPnl: 0, winRate: 0, profitFactor: 0, totalTrades: 0,
                    avgWin: 0, avgLoss: 0, expectancy: 0, rMultiple: 0,
                    bestDay: 0, worstDay: 0, consecutiveWins: 0, consecutiveLosses: 0
                }
            }
        }

        let totalPnl = 0
        let grossProfit = 0
        let grossLoss = 0
        let wins = 0
        let losses = 0
        let maxWin = -Infinity
        let maxLoss = Infinity
        let currentWinStreak = 0
        let maxWinStreak = 0
        let currentLossStreak = 0
        let maxLossStreak = 0

        // Daily P&L tracking
        const dailyPnlMap = new Map<string, number>()

        trades.forEach(trade => {
            const pnl = trade.pnl || 0
            totalPnl += pnl

            // Classification
            if (pnl > 0) {
                wins++
                grossProfit += pnl
                
                currentWinStreak++
                currentLossStreak = 0
                if (currentWinStreak > maxWinStreak) maxWinStreak = currentWinStreak
            } else if (pnl < 0) {
                losses++
                grossLoss += Math.abs(pnl)
                
                currentLossStreak++
                currentWinStreak = 0
                if (currentLossStreak > maxLossStreak) maxLossStreak = currentLossStreak
            }

            // Day tracking
            if (trade.exitDate) {
                const dateKey = format(trade.exitDate, 'yyyy-MM-dd')
                const currentDay = dailyPnlMap.get(dateKey) || 0
                dailyPnlMap.set(dateKey, currentDay + pnl)
            }
        })

        // Metrics
        const totalTrades = trades.length
        const winRate = (wins / totalTrades) * 100
        const profitFactor = grossLoss === 0 ? (grossProfit > 0 ? 100 : 0) : grossProfit / grossLoss
        const avgWin = wins > 0 ? grossProfit / wins : 0
        const avgLoss = losses > 0 ? grossLoss / losses : 0
        const expectancy = (avgWin * (winRate/100)) - (avgLoss * (1 - (winRate/100)))
        const rMultiple = avgLoss > 0 ? avgWin / avgLoss : 0

        // Daily stats
        let bestDay = -Infinity
        let worstDay = Infinity
        dailyPnlMap.forEach(val => {
            if (val > bestDay) bestDay = val
            if (val < worstDay) worstDay = val
        })
        if (bestDay === -Infinity) bestDay = 0
        if (worstDay === Infinity) worstDay = 0

        return {
            success: true,
            data: {
                totalPnl,
                winRate,
                profitFactor,
                totalTrades,
                avgWin,
                avgLoss,
                expectancy,
                rMultiple,
                bestDay,
                worstDay,
                consecutiveWins: maxWinStreak,
                consecutiveLosses: maxLossStreak
            }
        }

    } catch (e) {
        console.error("getAggregatedStats failed", e)
        return { success: false, data: undefined }
    }
}

export async function getEquityCurve(filters?: DashboardFilters) {
    try {
        const where = buildWhereClause(filters)
        const trades = await prisma.trade.findMany({
            where,
            orderBy: { exitDate: "asc" },
            select: { exitDate: true, pnl: true }
        })

        let cumulative = 0
        let peak = 0
        const points = trades.map(t => {
            cumulative += (t.pnl || 0)
            if (cumulative > peak) peak = cumulative
            const drawdown = cumulative - peak

            return {
                date: t.exitDate!.toISOString(),
                equity: cumulative,
                drawdown: drawdown
            }
        })

        return { success: true, data: points }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getCalendarData(filters?: DashboardFilters) {
    try {
        const where = buildWhereClause(filters)
        const trades = await prisma.trade.findMany({
            where,
            select: { exitDate: true, pnl: true, status: true }
        })

        const calendarMap = new Map<string, { pnl: number, trades: number, wins: number, losses: number }>()

        trades.forEach(t => {
            if (!t.exitDate) return
            const dateStr = format(t.exitDate, 'yyyy-MM-dd')
            const entry = calendarMap.get(dateStr) || { pnl: 0, trades: 0, wins: 0, losses: 0 }
            
            entry.pnl += (t.pnl || 0)
            entry.trades++
            if ((t.pnl || 0) > 0) entry.wins++
            else if ((t.pnl || 0) < 0) entry.losses++

            calendarMap.set(dateStr, entry)
        })

        const data = Array.from(calendarMap.entries()).map(([date, stats]) => ({
            date,
            ...stats
        }))

        return { success: true, data }

    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getJournalTrades(filters?: DashboardFilters) {
    try {
        const where = buildWhereClause(filters)
        const trades = await prisma.trade.findMany({
            where,
            orderBy: { entryDate: "desc" },
            take: 100 // Limit for performance? Or pagination?
        })
        return { success: true, data: trades }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getAccounts() {
    try {
        const accounts = await prisma.account.findMany({
            orderBy: { name: 'asc' }
        })
        return { success: true, data: accounts }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function createAccount(name: string, balance: number, currency: string) {
    try {
        const acc = await prisma.account.create({
            data: {
                name,
                initialBalance: balance,
                currentBalance: balance,
                currency,
            }
        });
        return { success: true, data: acc };
    } catch (e) {
        return { success: false, error: String(e) };
    }
}

export async function deleteAccount(id: string) {
    try {
        await prisma.account.delete({ where: { id } });
        return { success: true };
    } catch (e) {
        return { success: false, error: String(e) };
    }
}

export async function resetAccount(id: string) {
    try {
        await prisma.trade.deleteMany({ where: { accountId: id } });
        return { success: true };
    } catch (e) {
        return { success: false, error: String(e) };
    }
}
