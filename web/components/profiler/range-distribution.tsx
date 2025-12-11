
"use client"

import { useMemo, useState } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface Props {
    sessions: ProfilerSession[];
}

function median(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function mode(arr: number[], bucketSize: number = 0.1): number | null {
    if (arr.length === 0) return null;
    const counts: Record<string, number> = {};
    arr.forEach(v => {
        const bucket = (Math.round(v / bucketSize) * bucketSize).toFixed(1);
        counts[bucket] = (counts[bucket] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? parseFloat(sorted[0][0]) : null;
}

export function RangeDistribution({ sessions }: Props) {
    const [selectedSession, setSelectedSession] = useState<string>('daily');

    // Calculate range distribution from session data (fully filter-aware)
    const { highData, lowData, highStats, lowStats } = useMemo(() => {
        if (sessions.length === 0) {
            return { highData: [], lowData: [], highStats: null, lowStats: null };
        }

        let targetSessions = sessions;

        if (selectedSession === 'daily') {
            // For daily, we need to look at the full day's high/low from open
            // Group by date and calculate daily range
            const byDate: Record<string, ProfilerSession[]> = {};
            sessions.forEach(s => {
                if (!byDate[s.date]) byDate[s.date] = [];
                byDate[s.date].push(s);
            });

            const dailyHighPcts: number[] = [];
            const dailyLowPcts: number[] = [];

            Object.values(byDate).forEach(daySessions => {
                if (daySessions.length < 2) return;

                // Find the Asia session (first session of day) for open
                const asiaSess = daySessions.find(s => s.session === 'Asia');
                if (!asiaSess || !asiaSess.open) return;

                const dayOpen = asiaSess.open;
                const dayHigh = Math.max(...daySessions.map(s => s.range_high));
                const dayLow = Math.min(...daySessions.map(s => s.range_low));

                if (dayOpen > 0) {
                    dailyHighPcts.push(((dayHigh - dayOpen) / dayOpen) * 100);
                    dailyLowPcts.push(((dayLow - dayOpen) / dayOpen) * 100);
                }
            });

            return buildDistribution(dailyHighPcts, dailyLowPcts);
        } else {
            // For specific session, use the session's high_pct and low_pct
            targetSessions = sessions.filter(s => s.session === selectedSession);
            const highPcts = targetSessions.map(s => s.high_pct).filter(p => p !== undefined);
            const lowPcts = targetSessions.map(s => s.low_pct).filter(p => p !== undefined);
            return buildDistribution(highPcts, lowPcts);
        }
    }, [sessions, selectedSession]);

    function buildDistribution(highPcts: number[], lowPcts: number[]) {
        const bucketSize = 0.1;

        // Build histogram data
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

        // Convert to chart data
        const highData = Object.entries(highBuckets)
            .map(([pct, count]) => ({
                pct: parseFloat(pct),
                percent: (count / totalHigh) * 100,
                count,
            }))
            .sort((a, b) => a.pct - b.pct);

        const lowData = Object.entries(lowBuckets)
            .map(([pct, count]) => ({
                pct: parseFloat(pct),
                percent: (count / totalLow) * 100,
                count,
            }))
            .sort((a, b) => a.pct - b.pct);

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
                        <div className="flex gap-4 text-sm mt-1">
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
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={highData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
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
                                    formatter={(value: number, name: string, props: any) => [
                                        `${value.toFixed(1)}% (${props.payload.count} days)`,
                                        'Frequency'
                                    ]}
                                    labelFormatter={(label) => `High: +${label}% from open`}
                                />
                                {highStats?.median && <ReferenceLine x={highStats.median} stroke="#888" strokeDasharray="3 3" />}
                                <Bar dataKey="percent" fill="#22c55e" radius={[2, 2, 0, 0]} />
                            </BarChart>
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
                        <div className="flex gap-4 text-sm mt-1">
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
                    </CardHeader>
                    <CardContent className="h-[220px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={lowData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
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
                                    formatter={(value: number, name: string, props: any) => [
                                        `${value.toFixed(1)}% (${props.payload.count} days)`,
                                        'Frequency'
                                    ]}
                                    labelFormatter={(label) => `Low: ${label}% from open`}
                                />
                                {lowStats?.median && <ReferenceLine x={lowStats.median} stroke="#888" strokeDasharray="3 3" />}
                                <Bar dataKey="percent" fill="#ef4444" radius={[2, 2, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
