"use server"

import prisma from "@/lib/prisma"
import { startOfDay, startOfWeek, startOfMonth, subDays } from "date-fns"

interface Trade {
    id: string
    entryDate: Date
    exitDate?: Date | null
    pnl?: number | null
    direction: string
    status: string
    strategy?: { name: string } | null
}

export interface AnalyticsSummary {
    totalPnl: number
    todayPnl: number
    weekPnl: number
    monthPnl: number
    totalTrades: number
    winCount: number
    lossCount: number
    winRate: number
    profitFactor: number
    avgWin: number
    avgLoss: number
    largestWin: number
    largestLoss: number
    avgTradeDuration: number // in minutes
}

export interface EquityCurvePoint {
    date: string
    pnl: number
    cumulative: number
    drawdown: number
}

export interface StrategyPerformance {
    strategy: string
    trades: number
    pnl: number
    winRate: number
}

export interface DayHourHeatmap {
    day: number // 0-6 (Sun-Sat)
    hour: number // 0-23
    pnl: number
    trades: number
}

export async function getAnalyticsSummary(): Promise<{ success: boolean; data?: AnalyticsSummary; error?: string }> {
    try {
        const trades = await prisma.trade.findMany({
            where: { status: "CLOSED" },
            orderBy: { exitDate: "asc" }
        })

        const now = new Date()
        const todayStart = startOfDay(now)
        const weekStart = startOfWeek(now, { weekStartsOn: 1 })
        const monthStart = startOfMonth(now)

        let totalPnl = 0
        let todayPnl = 0
        let weekPnl = 0
        let monthPnl = 0
        let winCount = 0
        let lossCount = 0
        let grossProfit = 0
        let grossLoss = 0
        let largestWin = 0
        let largestLoss = 0
        let totalDuration = 0

        for (const trade of trades) {
            const pnl = trade.pnl || 0
            totalPnl += pnl

            const exitDate = trade.exitDate ? new Date(trade.exitDate) : now

            if (exitDate >= todayStart) todayPnl += pnl
            if (exitDate >= weekStart) weekPnl += pnl
            if (exitDate >= monthStart) monthPnl += pnl

            if (pnl > 0) {
                winCount++
                grossProfit += pnl
                if (pnl > largestWin) largestWin = pnl
            } else if (pnl < 0) {
                lossCount++
                grossLoss += Math.abs(pnl)
                if (pnl < largestLoss) largestLoss = pnl
            }

            if (trade.duration) {
                totalDuration += trade.duration
            }
        }

        const totalTrades = trades.length
        const winRate = totalTrades > 0 ? (winCount / totalTrades) * 100 : 0
        const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0
        const avgWin = winCount > 0 ? grossProfit / winCount : 0
        const avgLoss = lossCount > 0 ? grossLoss / lossCount : 0
        const avgTradeDuration = totalTrades > 0 ? (totalDuration / totalTrades) / 60 : 0 // convert to minutes

        return {
            success: true,
            data: {
                totalPnl,
                todayPnl,
                weekPnl,
                monthPnl,
                totalTrades,
                winCount,
                lossCount,
                winRate,
                profitFactor,
                avgWin,
                avgLoss,
                largestWin,
                largestLoss,
                avgTradeDuration
            }
        }
    } catch (error) {
        console.error("getAnalyticsSummary Error:", error)
        return { success: false, error: "Failed to fetch analytics" }
    }
}

export async function getEquityCurve(): Promise<{ success: boolean; data?: EquityCurvePoint[]; error?: string }> {
    try {
        const trades = await prisma.trade.findMany({
            where: { status: "CLOSED", exitDate: { not: null } },
            orderBy: { exitDate: "asc" },
            select: { exitDate: true, pnl: true }
        })

        const points: EquityCurvePoint[] = []
        let cumulative = 0
        let peak = 0

        for (const trade of trades) {
            const pnl = trade.pnl || 0
            cumulative += pnl
            if (cumulative > peak) peak = cumulative
            const drawdown = peak - cumulative

            points.push({
                date: trade.exitDate!.toISOString().split('T')[0],
                pnl,
                cumulative,
                drawdown: -drawdown // negative for display
            })
        }

        return { success: true, data: points }
    } catch (error) {
        console.error("getEquityCurve Error:", error)
        return { success: false, error: "Failed to fetch equity curve" }
    }
}

export async function getStrategyPerformance(): Promise<{ success: boolean; data?: StrategyPerformance[]; error?: string }> {
    try {
        const trades = await prisma.trade.findMany({
            where: { status: "CLOSED" },
            include: { strategy: true }
        })

        const strategyMap = new Map<string, { trades: number; pnl: number; wins: number }>()

        for (const trade of trades) {
            const strategyName = trade.strategy?.name || "No Strategy"
            const existing = strategyMap.get(strategyName) || { trades: 0, pnl: 0, wins: 0 }

            existing.trades++
            existing.pnl += trade.pnl || 0
            if ((trade.pnl || 0) > 0) existing.wins++

            strategyMap.set(strategyName, existing)
        }

        const result: StrategyPerformance[] = []
        for (const [strategy, stats] of strategyMap.entries()) {
            result.push({
                strategy,
                trades: stats.trades,
                pnl: stats.pnl,
                winRate: stats.trades > 0 ? (stats.wins / stats.trades) * 100 : 0
            })
        }

        // Sort by P&L descending
        result.sort((a, b) => b.pnl - a.pnl)

        return { success: true, data: result }
    } catch (error) {
        console.error("getStrategyPerformance Error:", error)
        return { success: false, error: "Failed to fetch strategy performance" }
    }
}

export async function getDayHourHeatmap(): Promise<{ success: boolean; data?: DayHourHeatmap[]; error?: string }> {
    try {
        const trades = await prisma.trade.findMany({
            where: { status: "CLOSED" },
            select: { entryDate: true, pnl: true }
        })

        const heatmap = new Map<string, { pnl: number; trades: number }>()

        for (const trade of trades) {
            const date = new Date(trade.entryDate)
            const day = date.getDay()
            const hour = date.getHours()
            const key = `${day}-${hour}`

            const existing = heatmap.get(key) || { pnl: 0, trades: 0 }
            existing.pnl += trade.pnl || 0
            existing.trades++
            heatmap.set(key, existing)
        }

        const result: DayHourHeatmap[] = []
        for (const [key, stats] of heatmap.entries()) {
            const [day, hour] = key.split('-').map(Number)
            result.push({ day, hour, pnl: stats.pnl, trades: stats.trades })
        }

        return { success: true, data: result }
    } catch (error) {
        console.error("getDayHourHeatmap Error:", error)
        return { success: false, error: "Failed to fetch heatmap" }
    }
}
