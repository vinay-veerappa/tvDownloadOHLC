"use client"

import { useMemo } from 'react';
import { ProfilerSession, LevelTouchesResponse } from '@/lib/api/profiler';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
import { OutcomePanel } from './outcome-panel';
import { HodLodAnalysis } from './hod-lod-analysis';
import { DailyLevels } from './daily-levels';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface SessionAnalysisViewProps {
    session: string;
    sessions: ProfilerSession[]; // Fully filtered sessions from parent
    filteredDates: Set<string>;
    ticker: string;
    levelTouches: LevelTouchesResponse | null;  // Passed from parent to avoid duplicate fetch
}

const OUTCOMES = ['Long True', 'Short True', 'Long False', 'Short False'];

// Level configuration per session
const SESSION_LEVELS: Record<string, string[]> = {
    'Asia': ['daily_open', 'pdl', 'pdm', 'pdh', 'p12h', 'p12m', 'p12l', 'asia_mid'],
    'London': ['midnight_open', 'asia_mid', 'london_mid', 'pdl', 'pdh'],
    'NY1': ['open_0730', 'london_mid', 'ny1_mid', 'asia_mid'],
    'NY2': ['ny1_mid', 'ny2_mid', 'london_mid']
};

export function SessionAnalysisView({ session, sessions, filteredDates, ticker, levelTouches }: SessionAnalysisViewProps) {

    // Filter sessions to strictly this session context
    const sessionData = useMemo(() => {
        return sessions.filter(s => s.session === session);
    }, [sessions, session]);

    // Calculate Outcome Splits
    const outcomeGroups = useMemo(() => {
        const groups: Record<string, ProfilerSession[]> = {};
        const bases: Record<string, number> = {}; // Denominator for probability

        // Initialize
        OUTCOMES.forEach(o => groups[o] = []);

        // Group data
        sessionData.forEach(s => {
            if (OUTCOMES.includes(s.status)) {
                groups[s.status].push(s);
            }
        });

        // Calculate bases (e.g. Total Long Broken for "Long True")
        // "Long True" base = Long True + Long False
        const longTrue = groups['Long True'].length;
        const longFalse = groups['Long False'].length;
        const shortTrue = groups['Short True'].length;
        const shortFalse = groups['Short False'].length;

        bases['Long True'] = longTrue + longFalse;
        bases['Long False'] = longTrue + longFalse;
        bases['Short True'] = shortTrue + shortFalse;
        bases['Short False'] = shortTrue + shortFalse;

        return { groups, bases };
    }, [sessionData]);

    if (sessionData.length === 0) {
        return <div className="p-8 text-center text-muted-foreground">No data matches criteria for {session} session.</div>;
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500">

            {/* Row 1: HOD/LOD Analysis (Moved to Top) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">HOD/LOD Analysis</h3>
                <HodLodAnalysis
                    sessions={sessionData}
                    ticker={ticker}
                    selectedSession={session} // Force session context
                />
            </section>

            {/* Row 2: Range Distribution (Locked to Session) */}
            <section>
                <RangeDistribution sessions={sessionData} forcedSession={session} />
            </section>

            {/* Row 3: Price Model (Median) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Median Price Model</h3>
                <PriceModelChart
                    ticker={ticker}
                    session={session}
                    targetSession={session} // Use session as target in this view
                    filters={{}}
                    brokenFilters={{}}
                    intraState="Any"
                    height={350}
                />
            </section>

            {/* Row 4: Outcome Analysis (Grid) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Outcome Analysis</h3>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    {OUTCOMES.map(outcome => {
                        const sList = outcomeGroups.groups[outcome];
                        if (sList.length === 0) return null; // Skip empty? Or show 0%?
                        // User wants "True or False outcomes only". If 0, maybe skip to save space.

                        return (
                            <OutcomePanel
                                key={outcome}
                                outcomeName={outcome}
                                sessions={sList}
                                targetSession={session}
                                totalInCategory={outcomeGroups.bases[outcome]}
                                ticker={ticker}
                                outcomeDates={new Set(sList.map(s => s.date))}
                            />
                        );
                    })}
                </div>
            </section>

            {/* Row 5: Session Levels */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Session Levels</h3>
                <DailyLevels
                    levelTouches={levelTouches || null}
                    filteredDates={filteredDates}
                    limitLevels={SESSION_LEVELS[session]}
                />
            </section>

        </div>
    );
}
