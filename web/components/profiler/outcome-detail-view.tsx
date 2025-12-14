"use client"

import { useMemo, memo } from 'react';
import { ProfilerSession, DailyHodLodResponse, LevelTouchesResponse } from '@/lib/api/profiler';
import { HodLodChart, SessionStats } from './hod-lod-analysis';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
import { DailyLevels } from './daily-levels'; // [NEW]
import { SESSION_LEVELS } from './session-analysis-view'; // [NEW]
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface OutcomeDetailViewProps {
    outcome: string; // "Long True", "Short True", etc.
    sessions: ProfilerSession[]; // Sessions matching this outcome (e.g. Asia rows)
    allSessions: ProfilerSession[]; // [NEW] All sessions for context
    dailyHodLod?: DailyHodLodResponse | null;
    dailyHodLod?: DailyHodLodResponse | null;
    ticker: string;
    targetSession: string;
    levelTouches: LevelTouchesResponse | null; // [NEW]
    // Global Filters to extend
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
}

export const OutcomeDetailView = memo(function OutcomeDetailView({
    outcome,
    sessions,
    allSessions,
    dailyHodLod,
    ticker,
    targetSession,
    levelTouches,
    filters,
    brokenFilters,
    intraState
}: OutcomeDetailViewProps) {

    // 1. Identification: Which dates match this outcome?
    const outcomeDates = useMemo(() => {
        return new Set(sessions.map(s => s.date));
    }, [sessions]);

    // 2. Daily Context: Create Synthetic Sessions from dailyHodLod
    // The backend filtered list usually lacks "Daily" rows or specific daily_open fields.
    // We construct them here to ensure RangeDistribution has correct daily stats.
    const dailyRangeSessions = useMemo(() => {
        if (!dailyHodLod) return [];
        const synthetic: ProfilerSession[] = [];

        outcomeDates.forEach(date => {
            const d = dailyHodLod[date];
            if (d) {
                // @ts-ignore - Constructing partial session with required fields for RangeDistribution
                synthetic.push({
                    date: date,
                    session: 'Asia', // RangeDistribution looks for 'Asia' to grab daily_open/high/low attached
                    open: d.daily_open,
                    // Attach daily stats that RangeDistribution (daily mode) looks for
                    // @ts-ignore
                    daily_open: d.daily_open,
                    // @ts-ignore
                    daily_high: d.daily_high,
                    // @ts-ignore
                    daily_low: d.daily_low,
                    // Dummy props to satisfy interface
                    range_high: 0,
                    range_low: 0,
                    mid: 0, high_time: null, low_time: null, high_pct: 0, low_pct: 0,
                    status: 'None', status_time: null, broken: false, broken_time: null,
                    start_time: '', end_time: ''
                });
            }
        });
        return synthetic;
    }, [dailyHodLod, outcomeDates]);

    // 3. Merge Outcome Filter
    // We strictly force the target session to have this outcome status
    const mergedFilters = useMemo(() => ({
        ...filters,
        [targetSession]: outcome
    }), [filters, targetSession, outcome]);

    if (sessions.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-12 border rounded-md bg-muted/10">
                <p className="text-muted-foreground">No sessions found with outcome: <span className="font-medium text-foreground">{outcome}</span></p>
                <p className="text-xs text-muted-foreground mt-2">Try adjusting global filters.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-300">
            {/* Header / Stats */}
            <div className="flex items-center gap-4">
                <Badge variant="outline" className="text-base px-4 py-1">
                    Count: {sessions.length}
                </Badge>
                {/* Could add win rate or other stats here if passed */}
            </div>

            {/* 1. HOD/LOD Analysis (Daily Context) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">HOD/LOD Analysis ({outcome})</h3>
                <p className="text-xs text-muted-foreground mb-2">Showing <strong>Full Day</strong> HOD/LOD times for these dates.</p>
                <HodLodChart
                    sessions={sessions} // The chart component handles dailyHodLod lookup internally via dates
                    dailyHodLod={dailyHodLod}
                />
            </section>

            {/* 2. Range Distribution (Daily Context) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Price Range Distribution  ({outcome})</h3>
                <p className="text-xs text-muted-foreground mb-2">Showing <strong>Daily Range</strong> distribution.</p>
                <RangeDistribution sessions={dailyRangeSessions} forcedSession="daily" />
            </section>

            {/* 3. Price Model (Median) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Median Price Model  ({outcome})</h3>
                <PriceModelChart
                    ticker={ticker}
                    session={targetSession}
                    targetSession={targetSession}
                    filters={mergedFilters} // <--- Critical: use merged filters
                    brokenFilters={brokenFilters}
                    intraState={intraState}
                    height={400}
                />
            </section>

            {/* 4. Session Levels (Outcome Specific) */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Session Levels ({outcome})</h3>
                <p className="text-xs text-muted-foreground mb-2">Showing touch rates for dates matching this outcome.</p>
                <DailyLevels
                    levelTouches={levelTouches}
                    filteredDates={outcomeDates}
                    limitLevels={SESSION_LEVELS[targetSession] || undefined}
                    initialSession={targetSession}
                />
            </section>

            {/* 5. Session Contribution Stats */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Session HOD/LOD Contribution  ({outcome})</h3>
                <SessionStats sessions={sessions} />
            </section>
        </div>
    );
});
