"use client"

import { useMemo } from 'react';
import { ProfilerSession, DailyHodLodResponse } from '@/lib/api/profiler';
import { HodLodChart, SessionStats } from './hod-lod-analysis';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface OutcomeDetailViewProps {
    outcome: string; // "Long True", "Short True", etc.
    sessions: ProfilerSession[]; // Sessions matching this outcome
    dailyHodLod?: DailyHodLodResponse | null;
    ticker: string;
    targetSession: string;
    // Global Filters to extend
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
}

export function OutcomeDetailView({
    outcome,
    sessions,
    dailyHodLod,
    ticker,
    targetSession,
    filters,
    brokenFilters,
    intraState
}: OutcomeDetailViewProps) {

    // 1. Merge Outcome Filter
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

            {/* 1. HOD/LOD Analysis */}
            <section>
                <h3 className="text-lg font-semibold mb-3">HOD/LOD Analysis ({outcome})</h3>
                <HodLodChart
                    sessions={sessions}
                    dailyHodLod={dailyHodLod}
                />
            </section>

            {/* 2. Range Distribution */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Price Range Distribution  ({outcome})</h3>
                <RangeDistribution sessions={sessions} forcedSession={targetSession} />
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

            {/* 4. Session Contribution Stats */}
            <section>
                <h3 className="text-lg font-semibold mb-3">Session HOD/LOD Contribution  ({outcome})</h3>
                <SessionStats sessions={sessions} />
            </section>
        </div>
    );
}
