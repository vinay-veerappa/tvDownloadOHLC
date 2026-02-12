"use server"

import prisma from "@/lib/prisma"
import { startOfDay, startOfWeek, startOfMonth, subDays } from "date-fns"

import { Trade as PrismaTrade } from "@prisma/client"

interface Trade { // Local interface for compatibility, or consider refactoring later
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

export interface MaeMfePoint {
    id: string
    maePercent: number
    mfePercent: number
    pnl: number
    win: boolean
}

export async function getMaeMfeAnalysis(): Promise<{ success: boolean; data?: MaeMfePoint[]; error?: string }> {
    try {
        const trades = await prisma.trade.findMany({
            where: { 
                status: "CLOSED",
                mae: { not: null },
                mfe: { not: null },
                entryPrice: { not: null }
            },
            select: {
                id: true,
                direction: true,
                entryPrice: true,
                mae: true,
                mfe: true,
                pnl: true
            }
        })

        const points: MaeMfePoint[] = []

        for (const trade of trades) {
            if (!trade.entryPrice || !trade.mae || !trade.mfe) continue

            const entry = trade.entryPrice
            // TypeScript check: ensure mae/mfe are treated as numbers if they are nullable in schema but checked above
            const mae = trade.mae
            const mfe = trade.mfe
            
            let maePercent = 0
            let mfePercent = 0

            if (trade.direction === "LONG") {
                // MAE is usually below entry for Long. Distance = Entry - MAE.
                // If MAE data is just the lowest price reached:
                const adverseDist = Math.max(0, entry - mae)
                maePercent = (adverseDist / entry) * 100
                
                // MFE is usually above entry for Long. Distance = MFE - Entry.
                const favorableDist = Math.max(0, mfe - entry)
                mfePercent = (favorableDist / entry) * 100
            } else {
                // Short: MAE is above entry. Distance = MAE - Entry.
                const adverseDist = Math.max(0, mae - entry)
                maePercent = (adverseDist / entry) * 100
                
                // Short: MFE is below entry. Distance = Entry - MFE.
                const favorableDist = Math.max(0, entry - mfe)
                mfePercent = (favorableDist / entry) * 100
            }

            points.push({
                id: trade.id,
                maePercent,
                mfePercent,
                pnl: trade.pnl || 0,
                win: (trade.pnl || 0) > 0
            })
        }

        return { success: true, data: points }
    } catch (error) {
        console.error("getMaeMfeAnalysis Error:", error)
        return { success: false, error: "Failed to fetch MAE/MFE analysis" }
    }
}

// ------------------------------------------------------------------
// Risk Metrics & Edge Finder (Phase 2)
// ------------------------------------------------------------------

export interface RiskMetrics {
  totalTrades: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  ev: number;              // Expected Value $
  pf: number;              // Profit Factor
  sqn: number;             // System Quality Number
  ror: number;             // Risk of Ruin %
  combinedEdge: number;    // (EV / AvgLoss) * PF
  maxConsecutiveLosses: number; // Actual
  predictedMaxStreak: number;   // Statistical ln(N)/ln(1/Loss%)
  currentDrawdown: number;      // $ from peak
  maxDrawdown: number;          // Max $ from peak
  drr: number;             // Drawdown Risk Rating
}

export interface EdgeStat {
  group: string; // The label (e.g. "5m", "London")
  trades: number;
  winRate: number;
  pnl: number;
  pf: number;
}

export async function getRiskMetrics(filters?: {
  accountId?: string;
  strategyId?: string;
  startDate?: Date;
  endDate?: Date;
}): Promise<RiskMetrics> {
  const where: any = {};
  if (filters?.accountId) where.accountId = filters.accountId;
  if (filters?.strategyId) where.strategyId = filters.strategyId;
  if (filters?.startDate || filters?.endDate) {
    where.entryDate = {};
    if (filters.startDate) where.entryDate.gte = filters.startDate;
    if (filters.endDate) where.entryDate.lte = filters.endDate;
  }
  where.status = "CLOSED"; // Only closed trades for stats

  const trades = await prisma.trade.findMany({
    where,
    orderBy: { entryDate: "asc" },
    select: {
      pnl: true,
      entryPrice: true,
      exitPrice: true,
      direction: true,
      entryDate: true,
      // If risk field is missing in schema type, we handle it
    }
  });

  const n = trades.length;
  if (n === 0) {
    return {
      totalTrades: 0, winRate: 0, avgWin: 0, avgLoss: 0, ev: 0, pf: 0,
      sqn: 0, ror: 0, combinedEdge: 0, maxConsecutiveLosses: 0,
      predictedMaxStreak: 0, currentDrawdown: 0, maxDrawdown: 0, drr: 0
    };
  }

  // 1. Basic Stats
  const wins = trades.filter(t => (t.pnl || 0) > 0);
  const losses = trades.filter(t => (t.pnl || 0) <= 0);
  
  const winRate = (wins.length / n) * 100;
  const lossRate = 1 - (wins.length / n); // 0.0 to 1.0

  const totalWinAmt = wins.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const totalLossAmt = Math.abs(losses.reduce((sum, t) => sum + (t.pnl || 0), 0)); // Absolute value

  const avgWin = wins.length > 0 ? totalWinAmt / wins.length : 0;
  const avgLoss = losses.length > 0 ? totalLossAmt / losses.length : 0;

  // 2. EV & PF
  // EV = (Win% * AvgWin) - (Loss% * AvgLoss) - using decimal % for calc
  const ev = ((wins.length / n) * avgWin) - ((losses.length / n) * avgLoss);
  const pf = totalLossAmt === 0 ? (totalWinAmt > 0 ? 100 : 0) : totalWinAmt / totalLossAmt;

  // 3. Combined Edge
  // (EV / AvgLoss) * PF. Guard against div by zero.
  const combinedEdge = avgLoss > 0 ? (ev / avgLoss) * pf : 0;

  // 4. SQN
  // Need R-multiples. If 'risk' field is missing, assume AvgLoss is 1R.
  const rMultiples = trades.map((t: any) => {
    const r = (t.risk && t.risk > 0) ? t.risk : (avgLoss > 0 ? avgLoss : 1);
    return (t.pnl || 0) / r;
  });
  
  const avgR = rMultiples.reduce((a: number, b: number) => a + b, 0) / n;
  const variance = rMultiples.reduce((sum: number, r: number) => sum + Math.pow(r - avgR, 2), 0) / n;
  const stdDevR = Math.sqrt(variance);
  
  const sqn = stdDevR > 0 ? (avgR * Math.sqrt(n)) / stdDevR : 0;

  // 5. Drawdowns & Streaks
  let currentDrawdown = 0;
  let maxDrawdown = 0; // Dollar amount
  let maxConsLoss = 0;
  let currentConsLoss = 0;
  let peakEquity = 0; // Relative to start of period (0)
  let currentEquity = 0;

  for (const t of trades) {
    const pnl = t.pnl || 0;
    
    // Streaks
    if (pnl <= 0) {
      currentConsLoss++;
    } else {
      maxConsLoss = Math.max(maxConsLoss, currentConsLoss);
      currentConsLoss = 0;
    }

    // Drawdowns
    currentEquity += pnl;
    if (currentEquity > peakEquity) {
      peakEquity = currentEquity;
    }
    const dd = peakEquity - currentEquity; // Positive number for DD amount
    if (dd > maxDrawdown) maxDrawdown = dd;
  }
  maxConsLoss = Math.max(maxConsLoss, currentConsLoss); // Check final streak
  currentDrawdown = peakEquity - currentEquity;

  // 6. Probability Predictions
  // Predicted Max Streak = ln(N) / ln(1/Loss%)
  let predictedMaxStreak = 0;
  if (lossRate > 0 && lossRate < 1) {
    predictedMaxStreak = Math.log(n) / Math.log(1 / lossRate);
  }

  // RoR (Risk of Ruin)
  // Formula: ((1 - CombinedEdgeNorm) / (1 + CombinedEdgeNorm)) ^ BankrollUnits
  // Simplified logic using raw CombinedEdge logic from user doc
  const rawCombinedEdge = avgLoss > 0 ? (ev / avgLoss) * pf : 0;
  const bankrollUnits = 20; // Default assumption from doc

  let ror = 0;
  if (rawCombinedEdge > 0) {
     const term = (1 - rawCombinedEdge) / (1 + rawCombinedEdge);
     if (term <= 0) ror = 0;
     else ror = Math.pow(term, bankrollUnits) * 100; // %
  } else {
      ror = 100; // Negative edge = 100% ruin
  }

  // DRR = MaxDD / Risk (Approx MaxDD / AvgLoss)
  const drr = avgLoss > 0 ? maxDrawdown / avgLoss : 0;

  return {
    totalTrades: n,
    winRate,
    avgWin,
    avgLoss,
    ev,
    pf,
    sqn,
    ror,
    combinedEdge: rawCombinedEdge,
    maxConsecutiveLosses: maxConsLoss,
    predictedMaxStreak,
    currentDrawdown,
    maxDrawdown,
    drr
  };
}

export async function getEdgeFinderStats(
  groupBy: "timeframe" | "session" | "marketCondition" | "setup" | "dayOfWeek",
  filters?: { accountId?: string }
): Promise<EdgeStat[]> {
    
    const where: any = { status: "CLOSED" };
    if (filters?.accountId) where.accountId = filters.accountId;

    const trades = await prisma.trade.findMany({
        where,
        include: {
             marketCondition: true, 
             playbook: true,
        }
    });

    const groups: Record<string, { wins: number; total: number; pnl: number; winPnl: number; lossPnl: number }> = {};

    for (const t of trades) {
        let key = "Unknown";

        if (groupBy === "timeframe") {
            key = "All"; // Placeholder
        } 
        else if (groupBy === "session") {
            key = t.marketCondition?.session || getSessionFromTime(t.entryDate);
        }
        else if (groupBy === "marketCondition") {
            key = t.marketCondition?.trend || "Neutral";
        }
        else if (groupBy === "setup") {
            key = t.playbook?.name || "No Setup";
        }
        else if (groupBy === "dayOfWeek") {
            const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
            key = days[t.entryDate.getDay()];
        }

        if (!groups[key]) groups[key] = { wins: 0, total: 0, pnl: 0, winPnl: 0, lossPnl: 0 };
        
        const pnl = t.pnl || 0;
        groups[key].total++;
        groups[key].pnl += pnl;
        if (pnl > 0) {
            groups[key].wins++;
            groups[key].winPnl += pnl;
        } else {
            groups[key].lossPnl += Math.abs(pnl);
        }
    }

    return Object.entries(groups).map(([group, stats]) => {
        return {
            group,
            trades: stats.total,
            winRate: stats.total > 0 ? (stats.wins / stats.total) * 100 : 0,
            pnl: stats.pnl,
            pf: stats.lossPnl === 0 ? (stats.winPnl > 0 ? 100 : 0) : stats.winPnl / stats.lossPnl
        };
    }).sort((a, b) => b.pnl - a.pnl);
}

function getSessionFromTime(date: Date): string {
    const hour = date.getHours(); 
    if (hour < 8) return "Asian";
    if (hour < 13) return "London";
    if (hour < 17) return "NY AM";
    return "NY PM";
}
