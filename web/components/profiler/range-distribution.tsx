

"use client"

import { useMemo, useState, useEffect, memo } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';
import { useReferenceData } from '@/hooks/use-reference-data';
import { ReferenceData } from '@/lib/api/reference';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ComposedChart, Bar, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown, Layers } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

interface Props {
    sessions: ProfilerSession[];
    forcedSession?: string;
}

function median(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function mode(arr: number[], bucketSize: number = 0.1, referenceDist?: Record<string, number>): number | null {
    if (referenceDist) {
        // If reference provided, return its mode bucket key
        const sorted = Object.entries(referenceDist).sort((a, b) => b[1] - a[1]);
        return sorted.length > 0 ? parseFloat(sorted[0][0]) : null;
    }

    if (arr.length === 0) return null;
    const counts: Record<string, number> = {};
    arr.forEach(v => {
        const bucket = (Math.round(v / bucketSize) * bucketSize).toFixed(1);
        counts[bucket] = (counts[bucket] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? parseFloat(sorted[0][0]) : null;
}

export const RangeDistribution = memo(function RangeDistribution({ sessions, forcedSession }: Props) {
    const [selectedSession, setSelectedSession] = useState<string>(forcedSession || 'daily');
    const { referenceData } = useReferenceData();  // Use shared hook (SWR deduplicates)
    const [showReference, setShowReference] = useState(false);

    useEffect(() => {
        if (forcedSession) setSelectedSession(forcedSession);
    }, [forcedSession]);

    // Calculate range distribution from session data (fully filter-aware)
    const { highData, lowData, highStats, lowStats } = useMemo(() => {
        if (sessions.length === 0) {
            return { highData: [], lowData: [], highStats: null, lowStats: null };
        }

        let targetSessions = sessions;
        let highPcts: number[] = [];
        let lowPcts: number[] = [];

        if (selectedSession === 'daily') {
            // Group by date and calculate daily range
            const byDate: Record<string, ProfilerSession[]> = {};
            sessions.forEach(s => {
                if (!byDate[s.date]) byDate[s.date] = [];
                byDate[s.date].push(s);
            });

            Object.values(byDate).forEach(daySessions => {
                const asiaSess = daySessions.find(s => s.session === 'Asia');
                if (!asiaSess || !asiaSess.open) return;

                // Use precomputed daily stats if available (from enrichment), otherwise calculate from visible sessions
                // @ts-ignore
                const dailyOpen = asiaSess.daily_open;
                // @ts-ignore
                const dailyHigh = asiaSess.daily_high;
                // @ts-ignore
                const dailyLow = asiaSess.daily_low;

                // CRITICAL: If we have explicit daily stats (e.g. synthetic sessions or enriched data), 
                // we don't need to enforce having \u003e= 2 sessions.
                const hasExplicitDaily = dailyOpen !== undefined && dailyHigh !== undefined;

                if (daySessions.length < 2 && !hasExplicitDaily) return;

                const dayOpen = dailyOpen !== undefined ? dailyOpen : asiaSess.open;
                // If dailyHigh is available, use it. Otherwise finding max of visible sessions is the best fallback, but incorrect for filtered views.
                // The enrichment ensures dailyHigh is present.
                const dayHigh = dailyHigh !== undefined ? dailyHigh : Math.max(...daySessions.map(s => s.range_high));
                const dayLow = dailyLow !== undefined ? dailyLow : Math.min(...daySessions.map(s => s.range_low));

                if (dayOpen > 0) {
                    highPcts.push(((dayHigh - dayOpen) / dayOpen) * 100);
                    lowPcts.push(((dayLow - dayOpen) / dayOpen) * 100);
                }
            });
        } else {
            targetSessions = sessions.filter(s => s.session === selectedSession);
            highPcts = targetSessions.map(s => s.high_pct).filter(p => p !== undefined);
            lowPcts = targetSessions.map(s => s.low_pct).filter(p => p !== undefined);
        }

        // Filter out any invalid numbers (NaN, Infinity)
        highPcts = highPcts.filter(p => Number.isFinite(p));
        lowPcts = lowPcts.filter(p => Number.isFinite(p));

        return buildDistribution(highPcts, lowPcts, selectedSession === 'daily' ? referenceData : null);

    }, [sessions, selectedSession, referenceData]);

    function buildDistribution(highPcts: number[], lowPcts: number[], refData: ReferenceData | null) {
        const bucketSize = 0.1;

        // Build histogram data (My Data)
        const highBuckets: Record<string, number> = {};
        const lowBuckets: Record<string, number> = {};

        highPcts.forEach(v => {
            const bucket = (Math.round(v / bucketSize) * bucketSize).toFixed(1);
            highBuckets[bucket] = (highBuckets[bucket] || 0) + 1;
        });

        lowPcts.forEach(v => {
            const bucket = (Math.round(v / bucketSize) * bucketSize).toFixed(1);
            lowBuckets[bucket] = (lowBuckets[bucket] || 0) + 1;
        });

        const totalHigh = highPcts.length || 1;
        const totalLow = lowPcts.length || 1;

        // Process Reference Data if available (and applicable)
        let refHighBuckets: Record<string, number> = {};
        let refLowBuckets: Record<string, number> = {};
        let totalRefHigh = 1;
        let totalRefLow = 1;

        if (refData && refData.stats.distributions.daily) {
            refHighBuckets = refData.stats.distributions.daily.high;
            refLowBuckets = refData.stats.distributions.daily.low;
            // Calculate totals for normalization
            totalRefHigh = Object.values(refHighBuckets).reduce((sum, c) => sum + c, 0) || 1;
            totalRefLow = Object.values(refLowBuckets).reduce((sum, c) => sum + c, 0) || 1;
        }

        // Merge keys from both datasets
        const allHighKeys = new Set([...Object.keys(highBuckets), ...(refData ? Object.keys(refHighBuckets) : [])]);
        const allLowKeys = new Set([...Object.keys(lowBuckets), ...(refData ? Object.keys(refLowBuckets) : [])]);

        const highData = Array.from(allHighKeys).map(pctStr => {
            const pct = parseFloat(pctStr);
            return {
                pct,
                percent: ((highBuckets[pctStr] || 0) / totalHigh) * 100,
                count: highBuckets[pctStr] || 0,
                refPercent: ((refHighBuckets[pctStr] || 0) / totalRefHigh) * 100,
            };
        }).sort((a, b) => a.pct - b.pct);

        const lowData = Array.from(allLowKeys).map(pctStr => {
            const pct = parseFloat(pctStr);
            return {
                pct,
                percent: ((lowBuckets[pctStr] || 0) / totalLow) * 100,
                count: lowBuckets[pctStr] || 0,
                refPercent: ((refLowBuckets[pctStr] || 0) / totalRefLow) * 100,
            };
        }).sort((a, b) => a.pct - b.pct);


        // ... (previous code)

        return {
            highData,
            lowData,
            highStats: {
                median: median(highPcts),
                mode: mode(highPcts),
                count: highPcts.length,
            },
            lowStats: {
                median: median(lowPcts),
                mode: mode(lowPcts),
                count: lowPcts.length,
            },
            refStats: (referenceData && selectedSession === 'daily') ? {
                high: {
                    median: referenceData.stats.distributions.daily.high.median,
                    mode: referenceData.stats.distributions.daily.high.mode
                },
                low: {
                    median: referenceData.stats.distributions.daily.low.median,
                    mode: referenceData.stats.distributions.daily.low.mode
                }
            } : null
        };
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Price Range Distribution</h2>
                <Select value={selectedSession} onValueChange={setSelectedSession}>
                    <SelectTrigger className="w-[120px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="daily">Full Day</SelectItem>
                        <SelectItem value="Asia">Asia</SelectItem>
                        <SelectItem value="London">London</SelectItem>
                        <SelectItem value="NY1">NY1</SelectItem>
                        <SelectItem value="NY2">NY2</SelectItem>
                    </SelectContent>
                </Select>
            </div>


            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* High Distribution */}
                <Card className="border-green-200">
                    <CardHeader className="pb-2 pt-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <TrendingUp className="h-4 w-4 text-green-600" />
                            High Distribution (from Open)
                        </CardTitle>
                        <div className="flex flex-col gap-2 mt-1">
                            <div className="flex gap-4 text-sm">
                                <div className="flex items-center gap-2 bg-green-50 dark:bg-green-950 px-2 py-1 rounded">
                                    <span className="text-muted-foreground">Mode:</span>
                                    <span className="font-mono font-bold">{highStats?.mode?.toFixed(1) ?? '-'}%</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-muted-foreground">Median:</span>
                                    <span className="font-mono">{highStats?.median?.toFixed(2) ?? '-'}%</span>
                                </div>
                                <Badge variant="outline">{highStats?.count ?? 0} days</Badge>
                            </div>
                            {/* Reference Stats */}
                            {/* @ts-ignore - refStats added to return object */}
                            {highStats?.refStats?.high && showReference && (
                                <div className="flex gap-4 text-xs text-muted-foreground pl-1 border-l-2 border-indigo-200">
                                    <span className="font-medium text-indigo-600">Reference:</span>
                                    <span>Mode: {(highStats as any).refStats.high.mode}%</span>
                                    <span>Median: {(highStats as any).refStats.high.median}%</span>
                                </div>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={highData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                <XAxis
                                    dataKey="pct"
                                    fontSize={9}
                                    tickFormatter={(v) => `${v}%`}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    fontSize={10}
                                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                                />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                    formatter={(value: number, name: string, props: any) => {
                                        if (name === 'Reference') return [`${value.toFixed(1)}%`, 'Reference (All-Time)'];
                                        return [`${value.toFixed(1)}% (${props.payload.count} days)`, 'Current Data'];
                                    }}
                                    labelFormatter={(label) => `High: +${label}% from open`}
                                />
                                {highStats?.median && <ReferenceLine x={highStats.median} stroke="#22c55e" strokeDasharray="3 3" />}
                                {/* @ts-ignore */}
                                {(highStats as any)?.refStats?.high?.median && showReference && <ReferenceLine x={(highStats as any).refStats.high.median} stroke="#6366f1" strokeDasharray="3 3" label={{ value: 'Ref', position: 'insideTopRight', fill: '#6366f1', fontSize: 10 }} />}
                                {showReference && selectedSession === 'daily' && (
                                    <Area type="monotone" dataKey="refPercent" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} name="Reference" strokeWidth={2} />
                                )}
                                <Bar dataKey="percent" fill="#22c55e" radius={[2, 2, 0, 0]} name="Current" opacity={0.8} />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Low Distribution */}
                <Card className="border-red-200">
                    <CardHeader className="pb-2 pt-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <TrendingDown className="h-4 w-4 text-red-600" />
                            Low Distribution (from Open)
                        </CardTitle>
                        <div className="flex flex-col gap-2 mt-1">
                            <div className="flex gap-4 text-sm">
                                <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950 px-2 py-1 rounded">
                                    <span className="text-muted-foreground">Mode:</span>
                                    <span className="font-mono font-bold">{lowStats?.mode?.toFixed(1) ?? '-'}%</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-muted-foreground">Median:</span>
                                    <span className="font-mono">{lowStats?.median?.toFixed(2) ?? '-'}%</span>
                                </div>
                                <Badge variant="outline">{lowStats?.count ?? 0} days</Badge>
                            </div>
                            {/* Reference Stats */}
                            {/* @ts-ignore - refStats added to return object */}
                            {lowStats?.refStats?.low && showReference && (
                                <div className="flex gap-4 text-xs text-muted-foreground pl-1 border-l-2 border-indigo-200">
                                    <span className="font-medium text-indigo-600">Reference:</span>
                                    <span>Mode: {(lowStats as any).refStats.low.mode}%</span>
                                    <span>Median: {(lowStats as any).refStats.low.median}%</span>
                                </div>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={lowData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                <XAxis
                                    dataKey="pct"
                                    fontSize={9}
                                    tickFormatter={(v) => `${v}%`}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    fontSize={10}
                                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                                />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                    formatter={(value: number, name: string, props: any) => {
                                        if (name === 'Reference') return [`${value.toFixed(1)}%`, 'Reference (All-Time)'];
                                        return [`${value.toFixed(1)}% (${props.payload.count} days)`, 'Current Data'];
                                    }}
                                    labelFormatter={(label) => `Low: ${label}% from open`}
                                />
                                {lowStats?.median && <ReferenceLine x={lowStats.median} stroke="#ef4444" strokeDasharray="3 3" />}
                                {/* @ts-ignore */}
                                {(lowStats as any)?.refStats?.low?.median && showReference && <ReferenceLine x={(lowStats as any).refStats.low.median} stroke="#6366f1" strokeDasharray="3 3" label={{ value: 'Ref', position: 'insideTopRight', fill: '#6366f1', fontSize: 10 }} />}
                                {showReference && selectedSession === 'daily' && (
                                    <Area type="monotone" dataKey="refPercent" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} name="Reference" strokeWidth={2} />
                                )}
                                <Bar dataKey="percent" fill="#ef4444" radius={[2, 2, 0, 0]} name="Current" opacity={0.8} />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div >
    );
});
