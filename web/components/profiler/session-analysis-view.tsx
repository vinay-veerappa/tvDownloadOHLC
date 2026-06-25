"use client"

import { useMemo, memo, useState } from 'react';
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
    startDate?: string;
    endDate?: string;
}

const OUTCOMES = ['Long True', 'Short True', 'Long False', 'Short False'];

// Level configuration per session
export const SESSION_LEVELS: Record<string, string[]> = {
    'Asia': ['daily_open', 'pdl', 'pdm', 'pdh', 'ny_p12h', 'ny_p12m', 'ny_p12l', 'prev_asia_mid', 'prev_london_mid', 'prev_ny1_mid', 'prev_ny2_mid'],
    'London': ['midnight_open', 'asia_mid', 'prev_london_mid', 'pdl', 'pdh', 'pdm', 'ny_p12h', 'ny_p12m', 'ny_p12l', 'prev_ny1_mid', 'prev_ny2_mid'],
    'NY1': ['open_0730', 'london_mid', 'prev_ny1_mid', 'asia_mid', 'midnight_open', 'pdl', 'pdh', 'pdm', 'p12h', 'p12m', 'p12l', 'prev_ny2_mid'],
    'NY2': ['ny1_mid', 'prev_ny2_mid', 'london_mid', 'open_0730', 'asia_mid', 'daily_open', 'pdl', 'pdh', 'pdm'],
};

export const SessionAnalysisView = memo(function SessionAnalysisView({ session, sessions, allSessions, dailyHodLod, filteredDates, ticker, levelTouches, filters, brokenFilters, intraState, startDate, endDate }: SessionAnalysisViewProps) {

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

    const [activeOutcome, setActiveOutcome] = useState<string>(validOutcomes[0] || 'Long True');
    const currentActive = validOutcomes.includes(activeOutcome) ? activeOutcome : (validOutcomes[0] || 'Long True');

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
                <Tabs value={currentActive} onValueChange={setActiveOutcome} className="w-full">
                    <div className="flex justify-start">
                        <TabsList className="h-10 p-1 bg-muted/60 inline-flex mb-8 border border-border/40">
                            {validOutcomes.map(outcome => {
                                const count = outcomeGroups.groups[outcome].length;
                                return (
                                    <TabsTrigger
                                        key={outcome}
                                        value={outcome}
                                        className="px-6 py-2 flex items-center gap-2 font-semibold"
                                    >
                                        {outcome}
                                        <span className="text-[10px] bg-background text-foreground/70 px-1.5 py-0.5 rounded-full border border-border/50">{count}</span>
                                    </TabsTrigger>
                                )
                            })}
                        </TabsList>
                    </div>

                    {validOutcomes.map(outcome => (
                        <TabsContent key={outcome} value={outcome} className="mt-0">
                            {currentActive === outcome && (
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
                                    startDate={startDate}
                                    endDate={endDate}
                                />
                            )}
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
