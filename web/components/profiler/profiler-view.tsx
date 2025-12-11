
"use client"

import { useEffect, useState, useMemo } from 'react';
import { fetchProfilerStats, ProfilerResponse, ProfilerSession, fetchDailyHodLod, DailyHodLodResponse, fetchLevelTouches, LevelTouchesResponse } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProfilerWizard } from '@/components/profiler/profiler-wizard';
import { TimeHistograms } from '@/components/profiler/time-histograms';
import { HodLodTimes, SessionHodLod } from '@/components/profiler/hod-lod-analysis';
import { RangeDistribution } from '@/components/profiler/range-distribution';
import { OutcomePanelGrid } from '@/components/profiler/outcome-panel-grid';
import { DailyLevels } from '@/components/profiler/daily-levels';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Loader2, Calendar } from 'lucide-react';

interface ProfilerStats {
    total: number;
    counts: Record<string, number>;
}

function calculateAggregates(sessions: ProfilerSession[]): Record<string, ProfilerStats> {
    const aggs: Record<string, ProfilerStats> = {};
    ['Asia', 'London', 'NY1', 'NY2'].forEach(s => {
        aggs[s] = { total: 0, counts: {} };
    });

    sessions.forEach(s => {
        if (!aggs[s.session]) {
            aggs[s.session] = { total: 0, counts: {} };
        }
        aggs[s.session].total++;
        const status = s.status || 'None';
        aggs[s.session].counts[status] = (aggs[s.session].counts[status] || 0) + 1;
    });

    return aggs;
}

export function ProfilerView({ ticker }: { ticker: string }) {
    const [data, setData] = useState<ProfilerResponse | null>(null);
    const [dailyHodLod, setDailyHodLod] = useState<DailyHodLodResponse | null>(null);
    const [levelTouches, setLevelTouches] = useState<LevelTouchesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Date filter state
    const [startDate, setStartDate] = useState<string>('2008-12-11'); // Default to data start
    const [endDate, setEndDate] = useState<string>(new Date().toISOString().split('T')[0]); // Today

    // Wizard filter state - matching dates from wizard
    const [wizardDates, setWizardDates] = useState<Set<string> | null>(null);
    const [outcomeFilter, setOutcomeFilter] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([
            fetchProfilerStats(ticker, 10000),
            fetchDailyHodLod(ticker),
            fetchLevelTouches(ticker)
        ])
            .then(([profilerData, hodLodData, levelTouchData]) => {
                setData(profilerData);
                setDailyHodLod(hodLodData);
                setLevelTouches(levelTouchData);
            })
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [ticker]);

    // Filter sessions by date range first
    const dateFilteredSessions = useMemo(() => {
        if (!data) return [];
        return data.sessions.filter(s => {
            return s.date >= startDate && s.date <= endDate;
        });
    }, [data, startDate, endDate]);

    // Apply wizard filter on top of date filter
    const filteredSessions = useMemo(() => {
        if (!wizardDates) {
            // No wizard filter active - use all date-filtered sessions
            return dateFilteredSessions;
        }
        // Apply wizard filter - only sessions from matching dates
        return dateFilteredSessions.filter(s => wizardDates.has(s.date));
    }, [dateFilteredSessions, wizardDates]);

    // Log for debugging
    console.log('[ProfilerView] Filter:', {
        startDate, endDate,
        dateFiltered: dateFilteredSessions.length,
        wizardActive: wizardDates !== null,
        wizardDays: wizardDates?.size ?? 'N/A',
        outcomeFilter,
        final: filteredSessions.length
    });

    // Get date range from data
    const dateRange = useMemo(() => {
        if (!data || data.sessions.length === 0) return { min: '', max: '' };
        const dates = data.sessions.map(s => s.date);
        return {
            min: dates[0],
            max: dates[dates.length - 1],
        };
    }, [data]);

    // Unique days count
    const uniqueDays = useMemo(() => {
        return new Set(filteredSessions.map(s => s.date)).size;
    }, [filteredSessions]);

    // Filtered dates as Set for DailyLevels
    const filteredDatesSet = useMemo(() => {
        return new Set(filteredSessions.map(s => s.date));
    }, [filteredSessions]);

    if (loading) return <div className="flex justify-center p-10"><Loader2 className="animate-spin h-8 w-8" /></div>;
    if (error) return <div className="text-red-500 p-10">Error: {error}</div>;
    if (!data) return null;

    const recentSessions = filteredSessions.slice(-200);
    const aggregates = calculateAggregates(recentSessions);
    const sessionOrder = ['Asia', 'London', 'NY1', 'NY2'];

    return (
        <div className="space-y-6 p-6">
            {/* Header with Date Filter */}
            <div className="flex flex-wrap items-center justify-between gap-4">
                <h1 className="text-3xl font-bold">Session Profiler ({ticker})</h1>

                <div className="flex items-center gap-4 bg-muted/50 rounded-lg px-4 py-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <div className="flex items-center gap-2">
                        <Label htmlFor="startDate" className="text-sm">From</Label>
                        <input
                            id="startDate"
                            type="date"
                            aria-label="Start Date"
                            value={startDate}
                            min={dateRange.min}
                            max={endDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            className="h-8 px-2 rounded border bg-background text-sm"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <Label htmlFor="endDate" className="text-sm">To</Label>
                        <input
                            id="endDate"
                            type="date"
                            aria-label="End Date"
                            value={endDate}
                            min={startDate}
                            max={dateRange.max}
                            onChange={(e) => setEndDate(e.target.value)}
                            className="h-8 px-2 rounded border bg-background text-sm"
                        />
                    </div>
                    <Badge variant="secondary" className="ml-2">
                        {uniqueDays.toLocaleString()} days | {filteredSessions.length.toLocaleString()} sessions
                    </Badge>
                </div>
            </div>

            {/* Wizard - receives date-filtered sessions, reports matching dates */}
            <ProfilerWizard
                sessions={dateFilteredSessions}
                onMatchingDatesChange={setWizardDates}
                onStateChange={setOutcomeFilter}
            />

            {/* 3-Tab Analysis View */}
            <Tabs defaultValue="hod-lod" className="w-full">
                <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="hod-lod">HOD/LOD Analysis</TabsTrigger>
                    <TabsTrigger value="outcomes">Outcome Panels</TabsTrigger>
                    <TabsTrigger value="levels">Daily Levels</TabsTrigger>
                    <TabsTrigger value="history">Session History</TabsTrigger>
                </TabsList>

                {/* Tab 1: HOD/LOD Analysis */}
                <TabsContent value="hod-lod" className="space-y-6 mt-4">
                    <HodLodTimes sessions={filteredSessions} dailyHodLod={dailyHodLod} />
                    <RangeDistribution sessions={filteredSessions} />
                    <SessionHodLod sessions={filteredSessions} />
                    <TimeHistograms sessions={filteredSessions} />
                </TabsContent>

                {/* Tab 2: Outcome Panels */}
                <TabsContent value="outcomes" className="space-y-4 mt-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold">Outcome Analysis (NY1)</h2>
                        <Badge variant="secondary">{filteredDatesSet.size} days</Badge>
                    </div>
                    <OutcomePanelGrid
                        sessions={filteredSessions}
                        targetSession="NY1"
                        dailyHodLod={dailyHodLod}
                        directionFilter={outcomeFilter}
                    />
                </TabsContent>

                {/* Tab 3: Daily Levels */}
                <TabsContent value="levels" className="mt-4">
                    <DailyLevels
                        levelTouches={levelTouches}
                        filteredDates={filteredDatesSet}
                    />
                </TabsContent>

                {/* Tab 4: Session History & Stats */}
                <TabsContent value="history" className="space-y-6 mt-4">
                    {/* Aggregate Cards */}
                    <div>
                        <h2 className="text-xl font-semibold mb-4">Session Stats (Filtered Period)</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {sessionOrder.map(sess => {
                                const stats = aggregates[sess];
                                if (!stats || stats.total === 0) return null;
                                return (
                                    <Card key={sess} className="min-w-[250px]">
                                        <CardHeader className="pb-2">
                                            <CardTitle>{sess}</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="space-y-2 text-sm">
                                                <div className="flex justify-between font-semibold">
                                                    <span>Total Sessions</span>
                                                    <span>{stats.total}</span>
                                                </div>
                                                <div className="h-px bg-border my-2" />
                                                {Object.entries(stats.counts).sort((a, b) => b[1] - a[1]).map(([status, count]) => (
                                                    <div key={status} className="flex justify-between items-center">
                                                        <span className={`
                                                            ${status.includes('True') ? 'text-green-500' : ''}
                                                            ${status.includes('False') ? 'text-red-500' : ''}
                                                        `}>{status}</span>
                                                        <div className="flex gap-2">
                                                            <span>{count}</span>
                                                            <span className="text-muted-foreground w-12 text-right">
                                                                {((count / stats.total) * 100).toFixed(1)}%
                                                            </span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </div>

                    {/* Detailed Log */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Session History (Last 100 of filtered)</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-[600px] overflow-auto">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Date</TableHead>
                                            <TableHead>Session</TableHead>
                                            <TableHead className="text-right">High</TableHead>
                                            <TableHead className="text-right">Low</TableHead>
                                            <TableHead className="text-right">Mid</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Broken</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {[...filteredSessions].slice(-100).reverse().map((s, i) => (
                                            <TableRow key={i}>
                                                <TableCell className="font-mono text-xs">{s.date}</TableCell>
                                                <TableCell>{s.session}</TableCell>
                                                <TableCell className="text-right font-mono text-green-600">{s.range_high.toFixed(2)}</TableCell>
                                                <TableCell className="text-right font-mono text-red-600">{s.range_low.toFixed(2)}</TableCell>
                                                <TableCell className="text-right font-mono text-muted-foreground">{s.mid.toFixed(2)}</TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className={`
                                                        ${s.status.includes('True') ? 'bg-green-100 text-green-800' : ''}
                                                        ${s.status.includes('False') ? 'bg-red-100 text-red-800' : ''}
                                                    `}>
                                                        {s.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {s.broken ? (
                                                        <div className="flex flex-col text-xs">
                                                            <span className="text-red-500 font-bold">Yes</span>
                                                            <span>{s.broken_time}</span>
                                                        </div>
                                                    ) : (
                                                        <span className="text-green-500">No</span>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
