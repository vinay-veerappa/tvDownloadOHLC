"use client"

import { useMemo, memo } from 'react';
import { ProfilerSession, LevelTouchesResponse, DailyHodLodResponse } from '@/lib/api/profiler';
import { SessionStats } from './hod-lod-analysis';
import { DailyLevels } from './daily-levels';
import { OutcomeDetailView } from './outcome-detail-view'; // [NEW]
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"; // [NEW]
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface SessionAnalysisViewProps {
    session: string;
    sessions: ProfilerSession[]; // Fully filtered sessions from parent (contains specific session rows)
    allSessions: ProfilerSession[]; // [NEW] All sessions (including "Daily" rows) for context lookup
    dailyHodLod: DailyHodLodResponse | null; // [NEW] True Daily HOD/LOD data
    filteredDates: Set<string>;
    ticker: string;
    levelTouches: LevelTouchesResponse | null;  // Passed from parent to avoid duplicate fetch
    // [NEW] Filter Props for PriceModelChart and OutcomeDetailView
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
}

const OUTCOMES = ['Long True', 'Short True', 'Long False', 'Short False'];

// Level configuration per session
export const SESSION_LEVELS: Record<string, string[]> = {
    'Asia': ['daily_open', 'pdl', 'pdm', 'pdh', 'p12h', 'p12m', 'p12l', 'asia_mid'],
    'London': ['midnight_open', 'asia_mid', 'london_mid', 'pdl', 'pdh', 'pdm', 'p12h', 'p12m', 'p12l'],
    'NY1': ['open_0730', 'london_mid', 'ny1_mid', 'asia_mid', 'midnight_open', 'pdl', 'pdh', 'pdm', 'p12h', 'p12m', 'p12l'],
    'NY2': ['ny1_mid', 'ny2_mid', 'london_mid', 'open_0730', 'asia_mid', 'daily_open', 'pdl', 'pdh', 'pdm'],
};

export const SessionAnalysisView = memo(function SessionAnalysisView({ session, sessions, allSessions, dailyHodLod, filteredDates, ticker, levelTouches, filters, brokenFilters, intraState }: SessionAnalysisViewProps) {

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

    // [NEW] Dynamic Tabs: Filter for outcomes that have data
    const validOutcomes = useMemo(() => {
        return OUTCOMES.filter(o => outcomeGroups.groups[o].length > 0);
    }, [outcomeGroups]);

    if (sessionData.length === 0) {
        return <div className="p-8 text-center text-muted-foreground">No data matches criteria for {session} session.</div>;
    }

    // Edge case: Data exists but not mapped to these 4 outcomes (e.g. "None")
    if (validOutcomes.length === 0) {
        return <div className="p-8 text-center text-muted-foreground">Sessions found but no specific Long/Short outcomes (likely consolidated inside range).</div>;
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500">



            {/* Row 4: Outcome Analysis (Tabs) */}
            <section>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-semibold">Outcome Detailed Analysis</h3>
                    <button
                        className="text-xs bg-muted hover:bg-muted/80 px-3 py-1 rounded flex items-center gap-2 transition-colors border"
                        onClick={() => {
                            import('@/lib/profiler-export').then(({ generateBulkExportString }) => {
                                const str = generateBulkExportString({
                                    ticker,
                                    targetSession: session,
                                    allSessions,
                                    dailyHodLod,
                                    levelTouches,
                                    validOutcomes // [NEW] Only export what is visible in tabs
                                });
                                navigator.clipboard.writeText(str);
                                alert("Copied All Outcomes to clipboard!");
                            });
                        }}
                    >
                        <span>📋</span> Copy All Outcomes
                    </button>
                </div>
                <Tabs defaultValue={validOutcomes[0]} className="w-full">
                    <TabsList className="w-full justify-start h-auto p-1 bg-muted/20 mb-4 overflow-x-auto">
                        {validOutcomes.map(outcome => {
                            const count = outcomeGroups.groups[outcome].length;
                            return (
                                <TabsTrigger
                                    key={outcome}
                                    value={outcome}
                                    className="px-4 py-2 flex items-center gap-2"
                                >
                                    {outcome}
                                    <span className="text-xs bg-muted text-muted-foreground px-1.5 rounded-full">{count}</span>
                                </TabsTrigger>
                            )
                        })}
                    </TabsList>

                    {validOutcomes.map(outcome => (
                        <TabsContent key={outcome} value={outcome} className="mt-0">
                            <OutcomeDetailView
                                outcome={outcome}
                                sessions={outcomeGroups.groups[outcome]}
                                allSessions={allSessions}
                                dailyHodLod={dailyHodLod}
                                ticker={ticker}
                                targetSession={session}
                                levelTouches={levelTouches} // [NEW] Pass level data
                                filters={filters}
                                brokenFilters={brokenFilters}
                                intraState={intraState}
                            />
                        </TabsContent>
                    ))}
                </Tabs>
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


            {/* Row 6: Session Contribution (Bottom) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Session HOD/LOD Contribution</h3>
                <SessionStats sessions={sessionData} />
            </section>

        </div>
    );
});
