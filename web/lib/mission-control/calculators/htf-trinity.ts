/**
 * HTF Trinity Calculator
 * 
 * Provides Higher Timeframe context (Weekly/Monthly/Daily 5 EMA).
 */

import { readParquetOHLC, calculateEMA } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';

export interface HTFProfile {
    timeframe: 'WEEKLY' | 'MONTHLY';
    high: number;
    low: number;
    mid: number;
    close?: number;
    zone: 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM';
    position_pct: number;
}

export interface HTFTrinityAnalysis {
    weekly: HTFProfile;
    monthly: HTFProfile;
    daily_ema: {
        value: number;
        distance_pct: number;
        position: 'ABOVE' | 'BELOW';
    };
    trinity_bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
}

/**
 * Calculate HTF Trinity analysis
 */
export async function calculateHTFTrinity(ticker: string): Promise<HTFTrinityAnalysis | null> {
    const dailyBars = await readParquetOHLC(ticker, '1d');
    if (dailyBars.length < 20) return null;

    // 1. Daily 5 EMA
    const closes = dailyBars.map(b => b.close);
    const ema5 = calculateEMA(closes, 5);
    const currentPrice = dailyBars[dailyBars.length - 1].close;
    const currentEMA = ema5[ema5.length - 1];
    const emaDistance = ((currentPrice - currentEMA) / currentEMA) * 100;

    // 2. Weekly Profile (Current incomplete week vs Last full week)
    // Actually Trinity usually uses the PREVIOUS session's range as the context.
    const lastFullWeek = getRecentRange(dailyBars, 'WEEK');
    const lastFullMonth = getRecentRange(dailyBars, 'MONTH');

    if (!lastFullWeek || !lastFullMonth) return null;

    const weekly = analyzeInZone(lastFullWeek, currentPrice, 'WEEKLY');
    const monthly = analyzeInZone(lastFullMonth, currentPrice, 'MONTHLY');

    // 3. Overall Bias
    let bullishScore = 0;
    if (currentPrice > currentEMA) bullishScore++;
    if (weekly.position_pct > 50) bullishScore++;
    if (monthly.position_pct > 50) bullishScore++;

    const trinity_bias = bullishScore >= 2 ? 'BULLISH' : bullishScore <= 1 ? 'BEARISH' : 'NEUTRAL';

    return {
        weekly,
        monthly,
        daily_ema: {
            value: currentEMA,
            distance_pct: emaDistance,
            position: currentPrice > currentEMA ? 'ABOVE' : 'BELOW'
        },
        trinity_bias
    };
}

function analyzeInZone(range: { high: number, low: number }, price: number, timeframe: any): HTFProfile {
    const mid = (range.high + range.low) / 2;
    const position_pct = ((price - range.low) / (range.high - range.low)) * 100;

    let zone: 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM' = 'EQUILIBRIUM';
    if (position_pct > 55) zone = 'PREMIUM';
    else if (position_pct < 45) zone = 'DISCOUNT';

    return {
        timeframe,
        high: range.high,
        low: range.low,
        mid: mid,
        zone,
        position_pct
    };
}

function getRecentRange(bars: OHLCBar[], type: 'WEEK' | 'MONTH'): { high: number, low: number } | null {
    // For simplicity, we'll take the bars from the previous full week/month
    // For a quick implementation, we can just look back N bars and group them
    const now = new Date(bars[bars.length - 1].timestamp);

    let targetBars: OHLCBar[] = [];
    if (type === 'WEEK') {
        // Last 5 trading days approx a week
        targetBars = bars.slice(-10, -5);
    } else {
        // Last 20 trading days approx a month
        targetBars = bars.slice(-25, -20);
    }

    if (targetBars.length === 0) return null;

    return {
        high: Math.max(...targetBars.map(b => b.high)),
        low: Math.min(...targetBars.map(b => b.low))
    };
}
