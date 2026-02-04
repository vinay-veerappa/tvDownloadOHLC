/**
 * War Game Calculator
 * 
 * Provides scenario-based probability analysis (The Battle).
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync } from 'fs';

export interface WarGameScenario {
    id: 'longTrue' | 'longFalse' | 'shortTrue' | 'shortFalse';
    name: string;
    probability: number;
    sampleSize: number;
    description: string;
    metrics: {
        avgMfe: number;
        avgMae: number;
    };
}

export interface WarGameAnalysis {
    scenarios: WarGameScenario[];
    currentScenario: string | null;
}

/**
 * Calculate War Game analysis
 */
export async function calculateWarGame(ticker: string): Promise<WarGameAnalysis | null> {
    const profilerPath = path.join(process.cwd(), '..', 'data', `${ticker}_profiler.json`);

    if (!existsSync(profilerPath)) {
        console.warn(`Profiler data not found for ${ticker} at ${profilerPath}`);
        return null;
    }

    try {
        const content = await fs.readFile(profilerPath, 'utf-8');
        const allSessions: any[] = JSON.parse(content);

        // 1. Group by date
        const days: Record<string, any[]> = {};
        allSessions.forEach(s => {
            if (!days[s.date]) days[s.date] = [];
            days[s.date].push(s);
        });

        const dayDates = Object.keys(days).sort();
        const results = {
            longTrue: 0,
            longFalse: 0,
            shortTrue: 0,
            shortFalse: 0,
            totalLongCases: 0,
            totalShortCases: 0
        };

        const metrics = {
            longTrue: { mfe: 0, mae: 0 },
            longFalse: { mfe: 0, mae: 0 },
            shortTrue: { mfe: 0, mae: 0 },
            shortFalse: { mfe: 0, mae: 0 }
        };

        dayDates.forEach(date => {
            const sessions = days[date];
            const asia = sessions.find(s => s.session === 'ASIA');
            const london = sessions.find(s => s.session === 'LONDON');
            const ny1 = sessions.find(s => s.session === 'NY1');
            const ny2 = sessions.find(s => s.session === 'NY2');

            if (!ny1) return; // Need at least some NY data to classify outcome

            // Determine Overnight Bias
            const isAsiaBull = asia?.status?.toLowerCase().includes('long true') || asia?.status?.toLowerCase().includes('short false');
            const isAsiaBear = asia?.status?.toLowerCase().includes('short true') || asia?.status?.toLowerCase().includes('long false');
            const isLdnBull = london?.status?.toLowerCase().includes('long true') || london?.status?.toLowerCase().includes('short false');
            const isLdnBear = london?.status?.toLowerCase().includes('short true') || london?.status?.toLowerCase().includes('long false');

            const isOvernightBull = isAsiaBull || isLdnBull;
            const isOvernightBear = isAsiaBear || isLdnBear;

            // Determine NY Outcome
            const isNYBull = ny1?.status?.toLowerCase().includes('long true') || ny2?.status?.toLowerCase().includes('long true');
            const isNYBear = ny1?.status?.toLowerCase().includes('short true') || ny2?.status?.toLowerCase().includes('short true');

            // Classify into Scenarios
            if (isOvernightBull) {
                results.totalLongCases++;
                if (isNYBull) {
                    results.longTrue++;
                    metrics.longTrue.mfe += (ny1?.high_pct || 0) + (ny2?.high_pct || 0);
                    metrics.longTrue.mae += (ny1?.low_pct || 0) + (ny2?.low_pct || 0);
                } else if (isNYBear) {
                    results.longFalse++;
                    metrics.longFalse.mfe += (ny1?.high_pct || 0) + (ny2?.high_pct || 0);
                    metrics.longFalse.mae += (ny1?.low_pct || 0) + (ny2?.low_pct || 0);
                }
            } else if (isOvernightBear) {
                results.totalShortCases++;
                if (isNYBear) {
                    results.shortTrue++;
                    metrics.shortTrue.mfe += Math.abs(ny1?.low_pct || 0) + Math.abs(ny2?.low_pct || 0);
                    metrics.shortTrue.mae += Math.abs(ny1?.high_pct || 0) + Math.abs(ny2?.high_pct || 0);
                } else if (isNYBull) {
                    results.shortFalse++;
                    metrics.shortFalse.mfe += Math.abs(ny1?.low_pct || 0) + Math.abs(ny2?.low_pct || 0);
                    metrics.shortFalse.mae += Math.abs(ny1?.high_pct || 0) + Math.abs(ny2?.high_pct || 0);
                }
            }
        });

        const scenarios: WarGameScenario[] = [
            {
                id: 'longTrue',
                name: 'Long TRUE (Follow Through)',
                probability: results.totalLongCases > 0 ? (results.longTrue / results.totalLongCases) * 100 : 0,
                sampleSize: results.totalLongCases,
                description: 'Overnight bullishness leads to NY expansion higher.',
                metrics: {
                    avgMfe: results.longTrue > 0 ? metrics.longTrue.mfe / results.longTrue : 0,
                    avgMae: results.longTrue > 0 ? metrics.longTrue.mae / results.longTrue : 0
                }
            },
            {
                id: 'longFalse',
                name: 'Long FALSE (Bull Trap)',
                probability: results.totalLongCases > 0 ? (results.longFalse / results.totalLongCases) * 100 : 0,
                sampleSize: results.totalLongCases,
                description: 'Overnight bullishness fails; NY reverses lower.',
                metrics: {
                    avgMfe: results.longFalse > 0 ? metrics.longFalse.mfe / results.longFalse : 0,
                    avgMae: results.longFalse > 0 ? metrics.longFalse.mae / results.longFalse : 0
                }
            },
            {
                id: 'shortTrue',
                name: 'Short TRUE (Follow Through)',
                probability: results.totalShortCases > 0 ? (results.shortTrue / results.totalShortCases) * 100 : 0,
                sampleSize: results.totalShortCases,
                description: 'Overnight bearishness leads to NY expansion lower.',
                metrics: {
                    avgMfe: results.shortTrue > 0 ? metrics.shortTrue.mfe / results.shortTrue : 0,
                    avgMae: results.shortTrue > 0 ? metrics.shortTrue.mae / results.shortTrue : 0
                }
            },
            {
                id: 'shortFalse',
                name: 'Short FALSE (Bear Trap)',
                probability: results.totalShortCases > 0 ? (results.shortFalse / results.totalShortCases) * 100 : 0,
                sampleSize: results.totalShortCases,
                description: 'Overnight bearishness fails; NY reverses higher.',
                metrics: {
                    avgMfe: results.shortFalse > 0 ? metrics.shortFalse.mfe / results.shortFalse : 0,
                    avgMae: results.shortFalse > 0 ? metrics.shortFalse.mae / results.shortFalse : 0
                }
            }
        ];

        // Determine which scenario is CURRENTLY active (based on Today's overnight)
        const lastDay = days[dayDates[dayDates.length - 1]];
        const todayAsia = lastDay.find(s => s.session === 'ASIA');
        const todayLondon = lastDay.find(s => s.session === 'LONDON');

        let currentScenario: string | null = null;
        const isTodayAsiaBull = todayAsia?.status?.toLowerCase().includes('long true') || todayAsia?.status?.toLowerCase().includes('short false');
        const isTodayAsiaBear = todayAsia?.status?.toLowerCase().includes('short true') || todayAsia?.status?.toLowerCase().includes('long false');
        const isTodayLdnBull = todayLondon?.status?.toLowerCase().includes('long true') || todayLondon?.status?.toLowerCase().includes('short false');
        const isTodayLdnBear = todayLondon?.status?.toLowerCase().includes('short true') || todayLondon?.status?.toLowerCase().includes('long false');

        if (isTodayAsiaBull || isTodayLdnBull) currentScenario = 'long';
        else if (isTodayAsiaBear || isTodayLdnBear) currentScenario = 'short';

        return {
            scenarios,
            currentScenario
        };

    } catch (error) {
        console.error('Error calculating War Game Matrix:', error);
        return null;
    }
}
