import { useMemo } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';

export const SESSION_ORDER = ['Asia', 'London', 'NY1', 'NY2'];

interface FilterState {
    targetSession: string;
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraSessionState: string;
}

export function useProfilerFilter(sessions: ProfilerSession[], state: FilterState) {
    const { targetSession, filters, brokenFilters, intraSessionState } = state;

    // 1. Determine available context sessions (those before target)
    const contextSessions = useMemo(() => {
        const idx = SESSION_ORDER.indexOf(targetSession);
        return idx === -1 ? [] : SESSION_ORDER.slice(0, idx);
    }, [targetSession]);

    // 2. Filter Logic
    const { filteredDates, distribution, validSamples, matches } = useMemo(() => {
        // Group sessions by date
        const sessionsByDate: Record<string, Record<string, ProfilerSession>> = {};
        sessions.forEach(s => {
            if (!sessionsByDate[s.date]) sessionsByDate[s.date] = {};
            sessionsByDate[s.date][s.session] = s;
        });

        const dist: Record<string, number> = {};
        let count = 0;
        const resultDates = new Set<string>();
        const matchedSessions: ProfilerSession[] = []; // All sessions for matched days? Or just target?
        // Actually for "Global Intersection", we want the set of DATES that match.
        // Then individual views filter their own sessions by this date set.

        Object.entries(sessionsByDate).forEach(([date, daySessions]) => {
            // Check context filters
            const isMatch = contextSessions.every(ctxSess => {
                const actualSess = daySessions[ctxSess];
                if (!actualSess) return false;

                // Status Filter
                const statusVal = filters[ctxSess];
                if (statusVal && statusVal !== 'Any') {
                    if (actualSess.status !== statusVal) return false;
                }

                // Broken Filter
                const brokenVal = brokenFilters[ctxSess];
                if (brokenVal && brokenVal !== 'Any') {
                    const isBroken = brokenVal === 'Yes';
                    if (actualSess.broken !== isBroken) return false;
                }

                return true;
            });

            if (isMatch) {
                // Check Intra-Session Filter (on Target)
                const target = daySessions[targetSession];
                if (target && target.status) {
                    if (intraSessionState !== 'Any') {
                        if (intraSessionState === 'Long') {
                            if (!target.status.startsWith('Long')) return;
                        } else if (intraSessionState === 'Short') {
                            if (!target.status.startsWith('Short')) return;
                        } else {
                            if (target.status !== intraSessionState) return;
                        }
                    }

                    count++;
                    dist[target.status] = (dist[target.status] || 0) + 1;
                    resultDates.add(date);
                    matchedSessions.push(target);
                }
            }
        });

        return {
            filteredDates: resultDates,
            distribution: dist,
            validSamples: count,
            matches: matchedSessions
        };
    }, [sessions, contextSessions, filters, brokenFilters, targetSession, intraSessionState]);

    return { filteredDates, distribution, validSamples, contextSessions };
}
