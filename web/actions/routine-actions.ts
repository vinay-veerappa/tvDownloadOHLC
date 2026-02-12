'use server'

import { db } from "@/lib/db"
import { revalidatePath } from "next/cache"


export type Sentiment = "BULLISH" | "BEARISH" | "NEUTRAL" | "MIXED"
export type Bias = "LONG" | "SHORT" | "BOTH" | "NONE"

// --- Analysis Actions ---

export async function getDailyContext(date: Date) {
  // Normalize date to start of UT day or local day? 
  // For now, let's assume the date passed is already normalized or we query by range.
  // Actually, standard practice: query by range [startOfDay, endOfDay]
  
  const start = new Date(date)
  start.setHours(0, 0, 0, 0)
  const end = new Date(date)
  end.setHours(23, 59, 59, 999)

  const analysis = await db.analysis.findFirst({
    where: {
      date: {
        gte: start,
        lte: end
      }
    },
    include: {
      wargames: {
        include: { charts: true } // Include charts linked to wargames
      },
      charts: true // Charts linked directly to analysis
    }
  })

  const routine = await db.routine.findFirst({
    where: {
      date: {
        gte: start,
        lte: end
      }
    }
  })

  // Also fetch trades for this day to show side-by-side?
  // We can do that in a separate call or here.
  
  return { analysis, routine }
}

export async function upsertAnalysis(data: {
  date: Date
  sentiment?: Sentiment
  bias?: Bias
  notes?: string
  keyLevels?: string // JSON
  invalidationLevel?: string
  profilerSnapshot?: string
  candleScienceSnapshot?: string
}) {
  const start = new Date(data.date)
  start.setHours(0, 0, 0, 0)
  const end = new Date(data.date)
  end.setHours(23, 59, 59, 999)

  // Check if exists
  const existing = await db.analysis.findFirst({
    where: {
      date: { gte: start, lte: end }
    }
  })

  if (existing) {
    await db.analysis.update({
      where: { id: existing.id },
      data: {
        sentiment: data.sentiment,
        bias: data.bias,
        notes: data.notes,
        keyLevels: data.keyLevels,
        invalidationLevel: data.invalidationLevel,
        profilerSnapshot: data.profilerSnapshot,
        candleScienceSnapshot: data.candleScienceSnapshot
      }
    })
  } else {
    await db.analysis.create({
      data: {
        date: data.date, // Should be normalized?
        sentiment: data.sentiment,
        bias: data.bias,
        notes: data.notes,
        keyLevels: data.keyLevels,
        invalidationLevel: data.invalidationLevel,
        profilerSnapshot: data.profilerSnapshot,
        candleScienceSnapshot: data.candleScienceSnapshot
      }
    })
  }
  
  revalidatePath("/journal")
  return { success: true }
}

// --- Wargame Actions ---

export async function createWargame(analysisId: string, data: {
  scenario: string
  plan: string
  probability?: string
}) {
  const wargame = await db.wargame.create({
    data: {
      analysisId,
      scenario: data.scenario,
      plan: data.plan,
      probability: data.probability
    }
  })
  revalidatePath("/journal")
  return wargame
}

export async function updateWargameOutcome(id: string, outcome: string) {
  await db.wargame.update({
    where: { id },
    data: { outcome }
  })
  revalidatePath("/journal")
}

export async function deleteWargame(id: string) {
    await db.wargame.delete({ where: { id }})
    revalidatePath("/journal")
}

// --- Routine Actions ---

export async function upsertRoutine(data: {
  date: Date
  checklist?: any // JSON
  rating?: number
  notes?: string
}) {
  const start = new Date(data.date)
  start.setHours(0, 0, 0, 0)
  const end = new Date(data.date)
  end.setHours(23, 59, 59, 999)

  const existing = await db.routine.findFirst({
    where: { date: { gte: start, lte: end } }
  })

  if (existing) {
    await db.routine.update({
      where: { id: existing.id },
      data: {
        checklist: JSON.stringify(data.checklist),
        rating: data.rating,
        notes: data.notes
      }
    })
  } else {
    await db.routine.create({
      data: {
        date: data.date,
        checklist: JSON.stringify(data.checklist),
        rating: data.rating,
        notes: data.notes
      }
    })
  }
  revalidatePath("/journal")
}

// --- Chart Actions ---

export async function saveChart(data: {
  url: string
  type: string // "PRE_MARKET", "TRADE", "REVIEW"
  tags?: string[]
  tradeId?: string
  analysisId?: string
  wargameId?: string
}) {
  await db.chart.create({
    data: {
      url: data.url,
      type: data.type,
      tags: data.tags ? data.tags.join(",") : undefined,
      tradeId: data.tradeId,
      analysisId: data.analysisId,
      wargameId: data.wargameId
    }
  })
  revalidatePath("/journal")
}

export async function getCharts(params: {
    tag?: string
    type?: string
    limit?: number
}) {
    const where: any = {}
    if (params.tag) {
        where.tags = { contains: params.tag }
    }
    if (params.type) {
        where.type = params.type
    }

    return await db.chart.findMany({
        where,
        orderBy: { createdAt: 'desc' },
        take: params.limit || 50
    })
}
