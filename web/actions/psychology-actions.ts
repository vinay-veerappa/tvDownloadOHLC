"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function updateTradePsychology(tradeId: string, data: {
    disciplineRating?: number,
    emotions?: string[],
    mistakes?: string[],
    playbookId?: string
}) {
    try {
        const updateData: any = {}
        if (data.disciplineRating !== undefined) updateData.disciplineRating = data.disciplineRating
        if (data.emotions !== undefined) updateData.emotions = data.emotions.join(",")
        if (data.mistakes !== undefined) updateData.mistakes = data.mistakes.join(",")
        if (data.playbookId !== undefined) updateData.playbookId = data.playbookId

        await prisma.trade.update({
            where: { id: tradeId },
            data: updateData
        })
        
        revalidatePath('/journal')
        return { success: true }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getPsychologyStats(dateRange?: { from: Date, to: Date }) {
    try {
        const where: any = { status: "CLOSED" }
        if (dateRange) {
            where.exitDate = {
                gte: dateRange.from,
                lte: dateRange.to
            }
        }

        const trades = await prisma.trade.findMany({ where })

        // Initialize Stats
        const disciplineBuckets = new Map<number, { count: number, pnl: number }>() // score -> stats
        const emotionMap = new Map<string, { count: number, pnl: number }>()
        const mistakeMap = new Map<string, { count: number, pnl: number }>()
        
        // Tiltmeter Stats (Discipline)
        let totalDiscipline = 0
        let ratedTradeCount = 0

        trades.forEach(trade => {
            const pnl = trade.pnl || 0

            // Discipline
            if (trade.disciplineRating) {
                const score = trade.disciplineRating
                totalDiscipline += score
                ratedTradeCount++

                const bucket = disciplineBuckets.get(score) || { count: 0, pnl: 0 }
                bucket.count++
                bucket.pnl += pnl
                disciplineBuckets.set(score, bucket)
            }

            // Emotions
            if (trade.emotions) {
                trade.emotions.split(",").forEach(tag => {
                    const t = tag.trim()
                    if (!t) return
                    const entry = emotionMap.get(t) || { count: 0, pnl: 0 }
                    entry.count++
                    entry.pnl += pnl
                    emotionMap.set(t, entry)
                })
            }

            // Mistakes (Demons)
            if (trade.mistakes) {
                trade.mistakes.split(",").forEach(tag => {
                    const t = tag.trim()
                    if (!t) return
                    const entry = mistakeMap.get(t) || { count: 0, pnl: 0 }
                    entry.count++
                    entry.pnl += pnl
                    mistakeMap.set(t, entry)
                })
            }
        })

        const avgDiscipline = ratedTradeCount > 0 ? totalDiscipline / ratedTradeCount : 0

        return {
            success: true,
            data: {
                avgDiscipline,
                disciplineStats: Array.from(disciplineBuckets.entries()).map(([score, stats]) => ({ score, ...stats })).sort((a,b) => a.score - b.score),
                emotionStats: Array.from(emotionMap.entries()).map(([tag, stats]) => ({ tag, ...stats })).sort((a,b) => b.count - a.count),
                mistakeStats: Array.from(mistakeMap.entries()).map(([tag, stats]) => ({ tag, ...stats })).sort((a,b) => b.count - a.count)
            }
        }

    } catch (e) {
        return { success: false, error: String(e) }
    }
}
