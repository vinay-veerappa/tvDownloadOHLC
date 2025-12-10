
"use client"

import { useState, useMemo } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowRight, Filter, RefreshCcw } from 'lucide-react';

interface WizardProps {
    sessions: ProfilerSession[];
}

const SESSION_ORDER = ['Asia', 'London', 'NY1', 'NY2'];
const STATUS_OPTIONS = ['Long True', 'Short True', 'Long False', 'Short False', 'None'];

export function ProfilerWizard({ sessions }: WizardProps) {
    const [targetSession, setTargetSession] = useState<string>('NY1');
    const [filters, setFilters] = useState<Record<string, string>>({});
    const [brokenFilters, setBrokenFilters] = useState<Record<string, string>>({});
    const [intraSessionState, setIntraSessionState] = useState<string>('Any');

    // 1. Determine available context sessions (those before target)
    const contextSessions = useMemo(() => {
        const idx = SESSION_ORDER.indexOf(targetSession);
        return SESSION_ORDER.slice(0, idx);
    }, [targetSession]);

    // 2. Filter Logic
    const stats = useMemo(() => {
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

        Object.values(sessionsByDate).forEach(daySessions => {
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
                        if (intraSessionState === 'High Broken First') {
                            if (!['Long True', 'Long False'].includes(target.status)) return;
                        } else if (intraSessionState === 'Low Broken First') {
                            if (!['Short True', 'Short False'].includes(target.status)) return;
                        }
                    }

                    matchingDaysCount++;
                    distribution[target.status] = (distribution[target.status] || 0) + 1;
                    validSamples++;
                }
            }
        });

        return { distribution, matchingDaysCount, validSamples };
    }, [sessions, targetSession, filters, brokenFilters, contextSessions, intraSessionState]);

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
        <Card className="border-2 border-primary/20">
            <CardHeader className="bg-muted/50 pb-4">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Filter className="h-5 w-5" />
                        Probability Wizard
                    </CardTitle>
                    <Button variant="ghost" size="sm" onClick={() => { setFilters({}); setBrokenFilters({}); setIntraSessionState('Any'); }}>
                        <RefreshCcw className="h-4 w-4 mr-2" />
                        Reset
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="pt-6 text-2xl">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

                    {/* LEFT: Configuration */}
                    <div className="md:col-span-5 space-y-6">
                        <div className="space-y-2">
                            <Label>I want to trade (Target Session)</Label>
                            <Select value={targetSession} onValueChange={handleTargetChange}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {SESSION_ORDER.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>Current Session State (Intra-day)</Label>
                            <Select value={intraSessionState} onValueChange={setIntraSessionState}>
                                <SelectTrigger className="border-blue-200 bg-blue-50/50">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="Any">Session just started (No break)</SelectItem>
                                    <SelectItem value="High Broken First">High Broken First (Bullish Break)</SelectItem>
                                    <SelectItem value="Low Broken First">Low Broken First (Bearish Break)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {contextSessions.length > 0 && (
                            <div className="space-y-4 rounded-lg border p-4 bg-muted/10">
                                <Label className="text-muted-foreground font-semibold">Context (What happened so far?)</Label>
                                {contextSessions.map(sess => (
                                    <div key={sess} className="space-y-2">
                                        <Label className="text-sm font-medium">{sess}</Label>
                                        <div className="flex gap-2">
                                            {/* Status Filter */}
                                            <Select
                                                value={filters[sess] || 'Any'}
                                                onValueChange={(v) => updateFilter(sess, v)}
                                            >
                                                <SelectTrigger className="h-9 flex-1">
                                                    <SelectValue placeholder="Status" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="Any">Status: Any</SelectItem>
                                                    {STATUS_OPTIONS.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                                                </SelectContent>
                                            </Select>

                                            {/* Broken Filter */}
                                            <Select
                                                value={brokenFilters[sess] || 'Any'}
                                                onValueChange={(v) => updateBrokenFilter(sess, v)}
                                            >
                                                <SelectTrigger className="h-9 w-[110px]">
                                                    <SelectValue placeholder="Broken" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="Any">Broken: Any</SelectItem>
                                                    <SelectItem value="Yes">Broken: Yes</SelectItem>
                                                    <SelectItem value="No">Broken: No</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* CENTER: Arrow */}
                    <div className="hidden md:flex md:col-span-2 items-center justify-center text-muted-foreground/30">
                        <ArrowRight className="h-16 w-16" />
                    </div>

                    {/* RIGHT: Results */}
                    <div className="md:col-span-6 space-y-6">
                        <div className="flex items-baseline justify-between mb-2">
                            <h3 className="text-lg font-semibold">Predicted Outcome</h3>
                            <Badge variant="secondary">
                                Based on {stats.validSamples} matching days
                            </Badge>
                        </div>

                        {stats.validSamples === 0 ? (
                            <div className="h-40 flex items-center justify-center border-2 border-dashed rounded-lg text-muted-foreground">
                                No historical patterns match this context
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {Object.entries(stats.distribution)
                                    .sort((a, b) => b[1] - a[1])
                                    .map(([status, count]) => {
                                        const percent = ((count / stats.validSamples) * 100).toFixed(1);
                                        const isHighArray = parseFloat(percent) > 40;

                                        return (
                                            <div key={status} className="space-y-1">
                                                <div className="flex justify-between text-sm">
                                                    <span className={`font-medium ${status.includes('True') ? 'text-green-600' : status.includes('False') ? 'text-red-600' : ''}`}>
                                                        {status}
                                                    </span>
                                                    <span>{percent}% ({count})</span>
                                                </div>
                                                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full rounded-full transition-all ${status.includes('True') ? 'bg-green-500' : status.includes('False') ? 'bg-red-500' : 'bg-gray-400'}`}
                                                        style={{ width: `${percent}%` }}
                                                    />
                                                </div>
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
