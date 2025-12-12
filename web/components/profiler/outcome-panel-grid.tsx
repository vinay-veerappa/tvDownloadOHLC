"use client"

import { useMemo } from 'react';
import { ProfilerSession, DailyHodLodResponse } from '@/lib/api/profiler';
import { OutcomePanel } from './outcome-panel';

interface OutcomePanelGridProps {
    sessions: ProfilerSession[];  // All filtered sessions
    targetSession: string;  // Which session outcomes to show (Asia, London, NY1, NY2)
    directionFilter?: string | null;  // 'Long', 'Short', 'Long True', etc. or null
    dailyHodLod?: DailyHodLodResponse | null;  // True daily HOD/LOD times
    ticker: string; // [NEW]
}

const OUTCOME_STATUSES = ['Long True', 'Long False', 'Short True', 'Short False'] as const;

export function OutcomePanelGrid({ sessions, targetSession, directionFilter, dailyHodLod, ticker }: OutcomePanelGridProps) {
    // Group sessions by date and get target session outcome
    const { outcomeData, outcomeDates, totalDays } = useMemo(() => {
        const byDate: Record<string, Record<string, ProfilerSession>> = {};

        sessions.forEach(s => {
            if (!byDate[s.date]) byDate[s.date] = {};
            byDate[s.date][s.session] = s;
        });

        // Count days with each outcome
        const outcomes: Record<string, ProfilerSession[]> = {
            'Long True': [],
            'Long False': [],
            'Short True': [],
            'Short False': []
        };

        // Also track dates per outcome for HOD/LOD filtering
        const dates: Record<string, Set<string>> = {
            'Long True': new Set(),
            'Long False': new Set(),
            'Short True': new Set(),
            'Short False': new Set()
        };

        let total = 0;
        Object.entries(byDate).forEach(([date, sessMap]) => {
            const target = sessMap[targetSession];
            if (!target || !target.status) return;

            total++;
            if (outcomes[target.status]) {
                // Add ALL sessions for this day (not just target)
                outcomes[target.status].push(...Object.values(sessMap));
                dates[target.status].add(date);
            }
        });

        return { outcomeData: outcomes, outcomeDates: dates, totalDays: total };
    }, [sessions, targetSession]);

    // Filter outcomes based on direction/status
    const visibleOutcomes = useMemo(() => {
        if (!directionFilter || directionFilter === 'Any') {
            return OUTCOME_STATUSES;
        }
        // Check for exact match first (e.g. "Long True")
        if (OUTCOME_STATUSES.includes(directionFilter as any)) {
            return [directionFilter];
        }
        // Fallback to startsWith (e.g. "Long" -> Long True, Long False)
        return OUTCOME_STATUSES.filter(s => s.startsWith(directionFilter));
    }, [directionFilter]);

    // Dynamic grid layout
    // Dynamic grid layout - Force one per row as requested
    const gridCols = 'grid-cols-1';

    return (
        <div className={`grid ${gridCols} gap-4`}>
            {visibleOutcomes.map(outcome => (
                <OutcomePanel
                    key={outcome}
                    outcomeName={outcome}
                    sessions={outcomeData[outcome] || []}
                    outcomeDates={outcomeDates[outcome]}
                    totalInCategory={totalDays}
                    targetSession={targetSession}
                    dailyHodLod={dailyHodLod}
                    ticker={ticker}
                />
            ))}
        </div>
    );
}
