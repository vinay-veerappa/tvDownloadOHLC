
"use client"

import { useState, useMemo, useEffect } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Filter, RefreshCcw } from 'lucide-react';

interface WizardProps {
    sessions: ProfilerSession[];
    onMatchingDatesChange?: (dates: Set<string> | null) => void; // null = no filter active
    onStateChange?: (state: string) => void; // Expose selected state (Long, Short, Long True, etc.)
}

const SESSION_ORDER = ['Asia', 'London', 'NY1', 'NY2'];
const STATUS_OPTIONS = ['Long True', 'Short True', 'Long False', 'Short False', 'None'];

export function ProfilerWizard({ sessions, onMatchingDatesChange, onStateChange }: WizardProps) {
    const [targetSession, setTargetSession] = useState<string>('NY1');
    const [filters, setFilters] = useState<Record<string, string>>({});
    const [brokenFilters, setBrokenFilters] = useState<Record<string, string>>({});
    const [intraSessionState, setIntraSessionState] = useState<string>('Any');

    // 1. Determine available context sessions (those before target)
    const contextSessions = useMemo(() => {
        const idx = SESSION_ORDER.indexOf(targetSession);
        return SESSION_ORDER.slice(0, idx);
    }, [targetSession]);

    // Check if any filter is active
    const isFilterActive = useMemo(() => {
        const hasStatusFilter = Object.values(filters).some(v => v && v !== 'Any');
        const hasBrokenFilter = Object.values(brokenFilters).some(v => v && v !== 'Any');
        const hasIntraFilter = intraSessionState !== 'Any';
        return hasStatusFilter || hasBrokenFilter || hasIntraFilter;
    }, [filters, brokenFilters, intraSessionState]);

    // 2. Filter Logic - now also returns matching dates
    const { stats, matchingDates } = useMemo(() => {
        // Group sessions by date to reconstruct "Days"
        const sessionsByDate: Record<string, Record<string, ProfilerSession>> = {};

        sessions.forEach(s => {
            if (!sessionsByDate[s.date]) sessionsByDate[s.date] = {};
            sessionsByDate[s.date][s.session] = s;
        });

        // Values for calculating distribution
        const distribution: Record<string, number> = {};
        let matchingDaysCount = 0;
        let validSamples = 0;
        const dates = new Set<string>();

        Object.entries(sessionsByDate).forEach(([date, daySessions]) => {
            // Check if this day matches all active filters
            const isMatch = contextSessions.every(ctxSess => {
                const actualSess = daySessions[ctxSess];
                if (!actualSess) return false; // Data missing

                // 1. Status Filter
                const statusVal = filters[ctxSess];
                if (statusVal && statusVal !== 'Any') {
                    if (actualSess.status !== statusVal) return false;
                }

                // 2. Broken Filter
                const brokenVal = brokenFilters[ctxSess];
                if (brokenVal && brokenVal !== 'Any') {
                    const isBroken = brokenVal === 'Yes';
                    if (actualSess.broken !== isBroken) return false;
                }

                return true;
            });

            if (isMatch) {
                const target = daySessions[targetSession];
                if (target && target.status) {

                    // 3. Intra-Session Filter (Target Session State)
                    if (intraSessionState !== 'Any') {
                        // Handle direction-only filters (Long, Short)
                        if (intraSessionState === 'Long') {
                            if (!target.status.startsWith('Long')) return;
                        } else if (intraSessionState === 'Short') {
                            if (!target.status.startsWith('Short')) return;
                        } else {
                            // Direct match to full status (Long True, Long False, etc.)
                            if (target.status !== intraSessionState) return;
                        }
                    }

                    matchingDaysCount++;
                    distribution[target.status] = (distribution[target.status] || 0) + 1;
                    validSamples++;
                    dates.add(date);
                }
            }
        });

        return {
            stats: { distribution, matchingDaysCount, validSamples },
            matchingDates: dates
        };
    }, [sessions, targetSession, filters, brokenFilters, contextSessions, intraSessionState]);

    // 3. Call callback when matching dates change (use useEffect for side effects)
    useEffect(() => {
        if (onMatchingDatesChange) {
            // Only apply filter if user has set some filters, otherwise pass null (no filter)
            onMatchingDatesChange(isFilterActive ? matchingDates : null);
        }
    }, [matchingDates, isFilterActive, onMatchingDatesChange]);

    // Notify state change
    useEffect(() => {
        if (onStateChange) {
            onStateChange(intraSessionState);
        }
    }, [intraSessionState, onStateChange]);

    // Reset filters when target changes
    const handleTargetChange = (val: string) => {
        setTargetSession(val);
        setFilters({});
        setBrokenFilters({});
        setIntraSessionState('Any');
    };

    const updateFilter = (sess: string, val: string) => {
        setFilters(prev => ({ ...prev, [sess]: val }));
    };

    const updateBrokenFilter = (sess: string, val: string) => {
        setBrokenFilters(prev => ({ ...prev, [sess]: val }));
    };

    return (
        <Card className="border border-primary/20">
            <CardContent className="py-3 px-4">
                {/* Compact horizontal wizard layout */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* Target Session */}
                    <div className="flex items-center gap-2">
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Target:</span>
                        <Select value={targetSession} onValueChange={handleTargetChange}>
                            <SelectTrigger className="h-8 w-[80px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {SESSION_ORDER.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Divider */}
                    <div className="h-6 w-px bg-border" />

                    {/* Context Filters - inline */}
                    {contextSessions.length > 0 && (
                        <>
                            <span className="text-sm text-muted-foreground">Given:</span>
                            {contextSessions.map(sess => (
                                <div key={sess} className="flex items-center gap-1">
                                    <span className="text-xs font-medium text-muted-foreground">{sess}</span>
                                    <Select
                                        value={filters[sess] || 'Any'}
                                        onValueChange={(v) => updateFilter(sess, v)}
                                    >
                                        <SelectTrigger className="h-7 w-[90px] text-xs">
                                            <SelectValue placeholder="Status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Any">Any</SelectItem>
                                            {STATUS_OPTIONS.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={brokenFilters[sess] || 'Any'}
                                        onValueChange={(v) => updateBrokenFilter(sess, v)}
                                    >
                                        <SelectTrigger className="h-7 w-[85px] text-xs">
                                            <SelectValue placeholder="Broken" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Any">Broken?</SelectItem>
                                            <SelectItem value="Yes">Broken Yes</SelectItem>
                                            <SelectItem value="No">Broken No</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            ))}
                            <div className="h-6 w-px bg-border" />
                        </>
                    )}

                    {/* Current State Filter */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">State:</span>
                        <Select value={intraSessionState} onValueChange={setIntraSessionState}>
                            <SelectTrigger className="h-8 w-[110px] border-blue-200 bg-blue-50/50">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="Any">Any</SelectItem>
                                <SelectItem value="Long">Long</SelectItem>
                                <SelectItem value="Short">Short</SelectItem>
                                <SelectItem value="Long True">Long True</SelectItem>
                                <SelectItem value="Long False">Long False</SelectItem>
                                <SelectItem value="Short True">Short True</SelectItem>
                                <SelectItem value="Short False">Short False</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Reset Button */}
                    {isFilterActive && (
                        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => { setFilters({}); setBrokenFilters({}); setIntraSessionState('Any'); }}>
                            <RefreshCcw className="h-3 w-3 mr-1" />
                            Reset
                        </Button>
                    )}

                    {/* Results Badge */}
                    <div className="ml-auto flex items-center gap-3">
                        <Badge variant={isFilterActive ? "default" : "secondary"} className="whitespace-nowrap">
                            {stats.validSamples} days
                        </Badge>

                        {/* Outcome Distribution - compact bars */}
                        {stats.validSamples > 0 && (
                            <div className="flex items-center gap-3">
                                {Object.entries(stats.distribution)
                                    .sort((a, b) => b[1] - a[1])
                                    .slice(0, 2) // Show top 2
                                    .map(([status, count]) => {
                                        const percent = ((count / stats.validSamples) * 100).toFixed(0);
                                        const isTrue = status.includes('True');
                                        const isFalse = status.includes('False');
                                        return (
                                            <div key={status} className="flex items-center gap-1 text-xs">
                                                <span className={`font-medium ${isTrue ? 'text-green-600' : isFalse ? 'text-red-600' : ''}`}>
                                                    {status}
                                                </span>
                                                <span className="text-muted-foreground">{percent}%</span>
                                            </div>
                                        );
                                    })}
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
