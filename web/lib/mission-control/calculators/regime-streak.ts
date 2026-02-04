/**
 * Regime Streak Calculator
 * 
 * Calculates session status (Long/Short True/False) and streaks.
 * Implementation follows CALCULATIONS.md specification.
 */

import { readParquetOHLC } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';
import { getSessionConfig } from '@/config/sessions';

export type SessionStatus = 'LONG_TRUE' | 'LONG_FALSE' | 'SHORT_TRUE' | 'SHORT_FALSE' | 'NEUTRAL';

export interface SessionResult {
    date: string;
    session: string;
    status: SessionStatus;
    mfe: number;
    mae: number;
}

export interface RegimeAnalysis {
    session: string;
    status: SessionStatus;
    current_streak: number;
    true_pct: number;
    false_pct: number;
    max_streak_true: number;
    max_streak_false: number;
}

export interface MultiRegimeAnalysis {
    sessions: RegimeAnalysis[];
}

/**
 * Calculate Regime Streak analysis for a ticker
 */
export async function calculateRegimeStreak(
    ticker: string,
    sessions: string[] = ['ASIA', 'LONDON', 'NY1', 'NY2'],
    lookbackDays: number = 20
): Promise<MultiRegimeAnalysis> {
    const bars = await readParquetOHLC(ticker, '1m');
    if (bars.length === 0) throw new Error(`No data for ${ticker}`);

    const results: RegimeAnalysis[] = [];

    for (const session of sessions) {
        try {
            const analysis = analyzeRegime(bars, session, lookbackDays);
            results.push(analysis);
        } catch (error) {
            console.error(`Error analyzing regime for ${session}:`, error);
        }
    }

    return { sessions: results };
}

function analyzeRegime(bars: OHLCBar[], sessionName: string, lookbackDays: number): RegimeAnalysis {
    const config = getSessionConfig(sessionName);
    const dayData = groupBarsByDay(bars);
    const days = Array.from(dayData.keys()).sort().slice(-lookbackDays - 1); // Get extra day for prev session

    const sessionHistory: SessionStatus[] = [];

    // Process days to get session status
    for (let i = 1; i < days.length; i++) {
        const prevDayBars = dayData.get(days[i - 1])!;
        const currDayBars = dayData.get(days[i])!;

        const prevSessionRange = getSessionRange(prevDayBars, config.start, config.end);
        const currSessionRange = getSessionRange(currDayBars, config.start, config.end);

        if (prevSessionRange && currSessionRange) {
            const status = determineStatus(prevSessionRange, currSessionRange);
            sessionHistory.push(status);
        }
    }

    if (sessionHistory.length === 0) throw new Error(`No history for ${sessionName}`);

    const currentStatus = sessionHistory[sessionHistory.length - 1];

    // Calculate Streaks
    let currentStreak = 0;
    let maxStreakTrue = 0;
    let maxStreakFalse = 0;
    let tempStreak = 0;
    let lastType = '';

    for (const status of sessionHistory) {
        const type = status.includes('TRUE') ? 'TRUE' : status.includes('FALSE') ? 'FALSE' : 'NEUTRAL';
        if (type === 'NEUTRAL') continue;

        if (type === lastType) {
            tempStreak++;
        } else {
            tempStreak = 1;
            lastType = type;
        }

        if (type === 'TRUE') maxStreakTrue = Math.max(maxStreakTrue, tempStreak);
        if (type === 'FALSE') maxStreakFalse = Math.max(maxStreakFalse, tempStreak);
    }

    // Current streak (trailing from end)
    const lastValidType = lastType;
    currentStreak = 0;
    for (let i = sessionHistory.length - 1; i >= 0; i--) {
        const type = sessionHistory[i].includes('TRUE') ? 'TRUE' : sessionHistory[i].includes('FALSE') ? 'FALSE' : 'NEUTRAL';
        if (type === 'NEUTRAL') continue;
        if (currentStreak === 0) {
            lastType = type;
            currentStreak = 1;
        } else if (type === lastType) {
            currentStreak++;
        } else {
            break;
        }
    }

    // Probabilities
    const trueCount = sessionHistory.filter(s => s.includes('TRUE')).length;
    const falseCount = sessionHistory.filter(s => s.includes('FALSE')).length;
    const total = trueCount + falseCount;

    return {
        session: sessionName,
        status: currentStatus,
        current_streak: currentStreak,
        true_pct: total > 0 ? (trueCount / total) * 100 : 0,
        false_pct: total > 0 ? (falseCount / total) * 100 : 0,
        max_streak_true: maxStreakTrue,
        max_streak_false: maxStreakFalse
    };
}

function determineStatus(prev: { high: number, low: number }, curr: { high: number, low: number, close: number }): SessionStatus {
    const mid = (curr.high + curr.low) / 2;
    const brokeAbove = curr.high > prev.high;
    const brokeBelow = curr.low < prev.low;
    const closedUpper = curr.close >= mid;

    if (brokeAbove && closedUpper) return 'LONG_TRUE';
    if (brokeAbove && !closedUpper) return 'LONG_FALSE';
    if (brokeBelow && !closedUpper) return 'SHORT_TRUE';
    if (brokeBelow && closedUpper) return 'SHORT_FALSE';
    return 'NEUTRAL';
}

function getSessionRange(bars: OHLCBar[], start: string, end: string) {
    const [sH, sM] = start.split(':').map(Number);
    const [eH, eM] = end.split(':').map(Number);
    const sMin = sH * 60 + sM;
    const eMin = eH * 60 + eM;

    let high = -Infinity;
    let low = Infinity;
    let close = 0;
    let found = false;

    for (const bar of bars) {
        const d = new Date(bar.timestamp);
        const bMin = d.getHours() * 60 + d.getMinutes();

        let inSession = eMin < sMin ? (bMin >= sMin || bMin < eMin) : (bMin >= sMin && bMin < eMin);

        if (inSession) {
            high = Math.max(high, bar.high);
            low = Math.min(low, bar.low);
            close = bar.close;
            found = true;
        }
    }

    return found ? { high, low, close } : null;
}

function groupBarsByDay(bars: OHLCBar[]): Map<string, OHLCBar[]> {
    const map = new Map<string, OHLCBar[]>();
    for (const bar of bars) {
        const date = new Date(bar.timestamp).toISOString().split('T')[0];
        if (!map.has(date)) map.set(date, []);
        map.get(date)!.push(bar);
    }
    return map;
}
