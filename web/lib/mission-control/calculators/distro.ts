/**
 * Distro (Fuel) Calculator
 * 
 * Calculates session range distribution and fuel percentage.
 * Fuel = current session range / median session range * 100
 * Implementation follows CALCULATIONS.md specification.
 */

import { readParquetOHLC } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';
import { getSessionConfig } from '@/config/sessions';

export interface SessionDistro {
    session: string;
    current_range: number;
    median_range: number;
    fuel_pct: number;
    status: 'High' | 'Normal' | 'Low';
}

export interface DistroAnalysis {
    sessions: SessionDistro[];
}

/**
 * Calculate Distro (Fuel) for configured sessions
 */
export async function calculateDistro(
    ticker: string,
    sessions: string[] = ['ASIA', 'LONDON', 'NY1', 'NY2'],
    lookbackDays: number = 20
): Promise<DistroAnalysis> {
    const sessionAnalyses: SessionDistro[] = [];

    for (const session of sessions) {
        try {
            const analysis = await analyzeSession(ticker, session, lookbackDays);
            sessionAnalyses.push(analysis);
        } catch (error) {
            console.error(`Error analyzing session ${session}:`, error);
        }
    }

    return {
        sessions: sessionAnalyses,
    };
}

/**
 * Analyze a single session
 */
async function analyzeSession(
    ticker: string,
    session: string,
    lookbackDays: number
): Promise<SessionDistro> {
    // Read 1-minute data
    const bars = await readParquetOHLC(ticker, '1m');

    if (bars.length === 0) {
        throw new Error(`No data for ${ticker}`);
    }

    const sessionConfig = getSessionConfig(session);

    // Extract session ranges for last N days
    const sessionRanges = extractSessionRanges(bars, sessionConfig.start, sessionConfig.end, lookbackDays);

    if (sessionRanges.length === 0) {
        throw new Error(`No session data found for ${session}`);
    }

    // Calculate median range
    const sortedRanges = [...sessionRanges].sort((a, b) => a - b);
    const medianRange = sortedRanges[Math.floor(sortedRanges.length / 2)];

    // Current session range (last session)
    const currentRange = sessionRanges[sessionRanges.length - 1];

    // Calculate fuel percentage
    const fuelPct = (currentRange / medianRange) * 100;

    // Determine status
    let status: 'High' | 'Normal' | 'Low';
    if (fuelPct > 120) {
        status = 'High';
    } else if (fuelPct < 80) {
        status = 'Low';
    } else {
        status = 'Normal';
    }

    return {
        session,
        current_range: currentRange,
        median_range: medianRange,
        fuel_pct: fuelPct,
        status,
    };
}

/**
 * Extract session ranges from 1m bars
 */
function extractSessionRanges(
    bars: OHLCBar[],
    sessionStart: string,
    sessionEnd: string,
    lookbackDays: number
): number[] {
    const ranges: number[] = [];
    const [startHour, startMin] = sessionStart.split(':').map(Number);
    const [endHour, endMin] = sessionEnd.split(':').map(Number);

    // Group bars by date
    const barsByDate = new Map<string, OHLCBar[]>();

    for (const bar of bars) {
        const date = new Date(bar.timestamp);
        const dateKey = date.toISOString().split('T')[0];

        if (!barsByDate.has(dateKey)) {
            barsByDate.set(dateKey, []);
        }
        barsByDate.get(dateKey)!.push(bar);
    }

    // Get last N days
    const dates = Array.from(barsByDate.keys()).sort().slice(-lookbackDays);

    for (const dateKey of dates) {
        const dayBars = barsByDate.get(dateKey)!;
        let sessionHigh = -Infinity;
        let sessionLow = Infinity;

        for (const bar of dayBars) {
            const date = new Date(bar.timestamp);
            const hour = date.getHours();
            const min = date.getMinutes();
            const timeInMinutes = hour * 60 + min;
            const startMinutes = startHour * 60 + startMin;
            const endMinutes = endHour * 60 + endMin;

            // Check if bar is in session
            let inSession = false;
            if (endMinutes < startMinutes) {
                // Overnight session
                inSession = timeInMinutes >= startMinutes || timeInMinutes < endMinutes;
            } else {
                inSession = timeInMinutes >= startMinutes && timeInMinutes < endMinutes;
            }

            if (inSession) {
                sessionHigh = Math.max(sessionHigh, bar.high);
                sessionLow = Math.min(sessionLow, bar.low);
            }
        }

        if (sessionHigh > sessionLow) {
            ranges.push(sessionHigh - sessionLow);
        }
    }

    return ranges;
}
