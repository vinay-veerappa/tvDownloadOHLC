"use client"

import { useMemo, useState, useEffect, memo } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ComposedChart, Bar, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown, Layers, Maximize2 } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { ChartTooltipFrame, ChartTooltipHeader, ChartTooltipRow } from '@/components/ui/chart-tooltip';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface Props {
    sessions: ProfilerSession[];
    forcedSession?: string;
}

// Helper to get bin range string (e.g. "0.2 to 0.3 %")
function getBinRangeResult(binStart: number, bucketSize: number = 0.1): string {
    if (binStart >= 5.0) return "> 5 %";
    if (binStart <= -5.0) return "< -5 %";
    const start = binStart.toFixed(1);
    const end = (binStart + bucketSize).toFixed(1);
    return `${start} to ${end} %`;
}

function medianBin(arr: number[], bucketSize: number = 0.1): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const midIndex = Math.floor(sorted.length / 2);
    const medianVal = sorted[midIndex];
    // Return the start of the bin containing the median
    return Math.floor(medianVal / bucketSize) * bucketSize;
}

function modeBin(arr: number[], bucketSize: number = 0.1, referenceDist?: Record<string, number>): number | null {
    if (referenceDist) {
        const sorted = Object.entries(referenceDist).sort((a, b) => b[1] - a[1]);
        return sorted.length > 0 ? parseFloat(sorted[0][0]) : null;
    }

    if (arr.length === 0) return null;
    const counts: Record<string, number> = {};
    arr.forEach(v => {
        const bucket = (Math.floor(v / bucketSize) * bucketSize).toFixed(1);
        counts[bucket] = (counts[bucket] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? parseFloat(sorted[0][0]) : null;
}

export const RangeDistribution = memo(function RangeDistribution({ sessions, forcedSession }: Props) {
    const [selectedSession, setSelectedSession] = useState<string>(forcedSession || 'daily');
    const [isExpandedHigh, setIsExpandedHigh] = useState(false);
    const [isExpandedLow, setIsExpandedLow] = useState(false);
    const bucketSize = 0.1;

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
                // we don't need to enforce having >= 2 sessions.
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

        return buildDistribution(highPcts, lowPcts);

    }, [sessions, selectedSession]);

    function buildDistribution(highPcts: number[], lowPcts: number[]) {
        // Clamp values to [-5, 5] for aggregation
        const clampedHigh = highPcts.map(v => Math.max(-5.0, Math.min(5.0, v)));
        const clampedLow = lowPcts.map(v => Math.max(-5.0, Math.min(5.0, v)));

        // Build histogram data (My Data)
        const highBuckets: Record<string, number> = {};
        const lowBuckets: Record<string, number> = {};

        clampedHigh.forEach(v => {
            const bucket = (Math.floor(v / bucketSize) * bucketSize).toFixed(1);
            highBuckets[bucket] = (highBuckets[bucket] || 0) + 1;
        });

        clampedLow.forEach(v => {
            const bucket = (Math.floor(v / bucketSize) * bucketSize).toFixed(1);
            lowBuckets[bucket] = (lowBuckets[bucket] || 0) + 1;
        });

        const totalHigh = clampedHigh.length || 1;
        const totalLow = clampedLow.length || 1;

        const highData = Object.keys(highBuckets).map(pctStr => {
            const pct = parseFloat(pctStr);
            return {
                pct,
                percent: ((highBuckets[pctStr] || 0) / totalHigh) * 100,
                count: highBuckets[pctStr] || 0,
            };
        }).sort((a, b) => a.pct - b.pct);

        const lowData = Object.keys(lowBuckets).map(pctStr => {
            const pct = parseFloat(pctStr);
            return {
                pct,
                percent: ((lowBuckets[pctStr] || 0) / totalLow) * 100,
                count: lowBuckets[pctStr] || 0,
            };
        }).sort((a, b) => a.pct - b.pct);

        return {
            highData,
            lowData,
            highStats: {
                medianBin: medianBin(clampedHigh),
                modeBin: modeBin(clampedHigh),
                count: clampedHigh.length,
            },
            lowStats: {
                medianBin: medianBin(clampedLow),
                modeBin: modeBin(clampedLow),
                count: clampedLow.length,
            }
        };
    }

    const HighChart = () => (
        <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={highData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                <XAxis
                    dataKey="pct"
                    fontSize={9}
                    tickFormatter={(v) => {
                        if (v >= 5) return '>5%';
                        if (v <= -5) return '<-5%';
                        return `${v}%`;
                    }}
                    interval="preserveStartEnd"
                />
                <YAxis
                    fontSize={10}
                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                />
                <Tooltip
                    cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                    content={({ active, payload, label }) => {
                        if (!active || !payload || !payload.length) return null;
                        return (
                            <ChartTooltipFrame>
                                <ChartTooltipHeader>High: {getBinRangeResult(Number(label))}</ChartTooltipHeader>
                                {payload.map((entry: any, index: number) => (
                                    <ChartTooltipRow
                                        key={index}
                                        label="Distribution"
                                        value={`${Number(entry.value).toFixed(1)}%`}
                                        subValue={`${entry.payload.count} days`}
                                        indicatorColor={entry.fill}
                                    />
                                ))}
                            </ChartTooltipFrame>
                        );
                    }}
                />
                {highStats?.medianBin && <ReferenceLine x={highStats.medianBin} stroke="#22c55e" strokeDasharray="3 3" />}
                <Bar dataKey="percent" fill="#22c55e" radius={[2, 2, 0, 0]} name="Current" opacity={0.8} barSize={100} />
            </ComposedChart>
        </ResponsiveContainer>
    );

    const LowChart = () => (
        <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={lowData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                <XAxis
                    dataKey="pct"
                    fontSize={9}
                    tickFormatter={(v) => {
                        if (v >= 5) return '>5%';
                        if (v <= -5) return '<-5%';
                        return `${v}%`;
                    }}
                    interval="preserveStartEnd"
                />
                <YAxis
                    fontSize={10}
                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                />
                <Tooltip
                    cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                    content={({ active, payload, label }) => {
                        if (!active || !payload || !payload.length) return null;
                        return (
                            <ChartTooltipFrame>
                                <ChartTooltipHeader>Low: {getBinRangeResult(Number(label))}</ChartTooltipHeader>
                                {payload.map((entry: any, index: number) => (
                                    <ChartTooltipRow
                                        key={index}
                                        label="Distribution"
                                        value={`${Number(entry.value).toFixed(1)}%`}
                                        subValue={`${entry.payload.count} days`}
                                        indicatorColor={entry.fill}
                                    />
                                ))}
                            </ChartTooltipFrame>
                        );
                    }}
                />
                {lowStats?.medianBin && <ReferenceLine x={lowStats.medianBin} stroke="#ef4444" strokeDasharray="3 3" />}
                <Bar dataKey="percent" fill="#ef4444" radius={[2, 2, 0, 0]} name="Current" opacity={0.8} barSize={100} />
            </ComposedChart>
        </ResponsiveContainer>
    );


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
                    <CardHeader className="pb-2 pt-3 flex flex-row items-center justify-between space-y-0">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <TrendingUp className="h-4 w-4 text-green-600" />
                                High Distribution
                            </CardTitle>
                            <div className="flex flex-col gap-2 mt-1">
                                <div className="flex gap-8 text-sm pt-2">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Mode</span>
                                        <span className="font-mono text-sm tabular-nums text-foreground/90">
                                            {highStats?.modeBin !== null && highStats?.modeBin !== undefined
                                                ? getBinRangeResult(highStats.modeBin)
                                                : '-'}
                                        </span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Median</span>
                                        <span className="font-mono text-sm tabular-nums text-muted-foreground">
                                            {highStats?.medianBin !== null && highStats?.medianBin !== undefined
                                                ? getBinRangeResult(highStats.medianBin)
                                                : '-'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <Button variant="ghost" size="icon" className="h-6 w-6 -mt-2 -mr-2" onClick={() => setIsExpandedHigh(true)}>
                            <Maximize2 className="h-4 w-4" />
                        </Button>
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <HighChart />
                    </CardContent>
                </Card>

                {/* Low Distribution */}
                <Card className="border-red-200">
                    <CardHeader className="pb-2 pt-3 flex flex-row items-center justify-between space-y-0">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <TrendingDown className="h-4 w-4 text-red-600" />
                                Low Distribution
                            </CardTitle>
                            <div className="flex flex-col gap-2 mt-1">
                                <div className="flex gap-8 text-sm pt-2">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Mode</span>
                                        <span className="font-mono text-sm tabular-nums text-foreground/90">
                                            {lowStats?.modeBin !== null && lowStats?.modeBin !== undefined
                                                ? getBinRangeResult(lowStats.modeBin)
                                                : '-'}
                                        </span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Median</span>
                                        <span className="font-mono text-sm tabular-nums text-muted-foreground">
                                            {lowStats?.medianBin !== null && lowStats?.medianBin !== undefined
                                                ? getBinRangeResult(lowStats.medianBin)
                                                : '-'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <Button variant="ghost" size="icon" className="h-6 w-6 -mt-2 -mr-2" onClick={() => setIsExpandedLow(true)}>
                            <Maximize2 className="h-4 w-4" />
                        </Button>
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <LowChart />
                    </CardContent>
                </Card>
            </div>

            <Dialog open={isExpandedHigh} onOpenChange={setIsExpandedHigh}>
                <DialogContent className="max-w-[90vw] w-[90vw] h-[85vh] flex flex-col sm:max-w-[90vw]">
                    <DialogHeader>
                        <DialogTitle>High Distribution ({selectedSession})</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 w-full min-h-0 mt-4">
                        <HighChart />
                    </div>
                </DialogContent>
            </Dialog>

            <Dialog open={isExpandedLow} onOpenChange={setIsExpandedLow}>
                <DialogContent className="max-w-[90vw] w-[90vw] h-[85vh] flex flex-col sm:max-w-[90vw]">
                    <DialogHeader>
                        <DialogTitle>Low Distribution ({selectedSession})</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 w-full min-h-0 mt-4">
                        <LowChart />
                    </div>
                </DialogContent>
            </Dialog>
        </div >
    );
});
