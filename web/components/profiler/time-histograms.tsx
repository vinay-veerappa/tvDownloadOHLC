
"use client"

import { useMemo, useState } from 'react';
import { ProfilerSession } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface Props {
    sessions: ProfilerSession[];
}

// Helper functions
function timeToMinutes(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
}

function minutesToTime(mins: number): string {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function median(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function mode(arr: string[]): string {
    if (arr.length === 0) return '-';
    const counts: Record<string, number> = {};
    arr.forEach(v => { counts[v] = (counts[v] || 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
}

// Round time to bucket based on granularity
function roundToBucket(time: string, granularity: number): string {
    const mins = timeToMinutes(time);
    const rounded = Math.floor(mins / granularity) * granularity;
    return minutesToTime(rounded);
}

export function TimeHistograms({ sessions }: Props) {
    const [granularity, setGranularity] = useState<number>(60); // Default: 1 hour

    // Build histogram data with selected granularity
    const { falseData, brokenData, falseStats, brokenStats } = useMemo(() => {
        const falseTimes: string[] = [];
        const brokenTimes: string[] = [];

        sessions.forEach(s => {
            if (s.status.includes('False') && s.status_time) {
                const time = s.status_time.substring(11, 16);
                falseTimes.push(time);
            }
            if (s.broken && s.broken_time) {
                brokenTimes.push(s.broken_time);
            }
        });

        // Bucket the times
        const bucket = (times: string[]) => {
            const counts: Record<string, number> = {};
            times.forEach(t => {
                const bucket = roundToBucket(t, granularity);
                counts[bucket] = (counts[bucket] || 0) + 1;
            });
            return Object.entries(counts)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([time, count]) => ({ time, count }));
        };

        // Stats calculation
        const calcStats = (times: string[]) => {
            if (times.length === 0) return { median: '-', mode: '-', count: 0 };
            const medianTime = minutesToTime(Math.round(median(times.map(timeToMinutes))));
            const modeTime = mode(times);
            return { median: medianTime, mode: modeTime, count: times.length };
        };

        return {
            falseData: bucket(falseTimes),
            brokenData: bucket(brokenTimes),
            falseStats: calcStats(falseTimes),
            brokenStats: calcStats(brokenTimes),
        };
    }, [sessions, granularity]);

    const granularityOptions = [
        { value: 1, label: '1 min' },
        { value: 5, label: '5 min' },
        { value: 15, label: '15 min' },
        { value: 30, label: '30 min' },
        { value: 60, label: '1 hour' },
    ];

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Time Analysis</h2>
                <Select value={granularity.toString()} onValueChange={(v) => setGranularity(parseInt(v))}>
                    <SelectTrigger className="w-[100px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {granularityOptions.map(o => (
                            <SelectItem key={o.value} value={o.value.toString()}>{o.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* False Moves */}
                <Card>
                    <CardHeader className="pb-2 pt-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">False Moves</CardTitle>
                            <div className="flex gap-2 text-xs">
                                <Badge variant="secondary" className="font-mono">Med: {falseStats.median}</Badge>
                                <Badge variant="outline" className="font-mono">Mode: {falseStats.mode}</Badge>
                                <Badge>{falseStats.count}</Badge>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="h-[180px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={falseData}>
                                <XAxis
                                    dataKey="time"
                                    fontSize={9}
                                    interval={granularity <= 5 ? 11 : granularity <= 15 ? 3 : 0}
                                    angle={-45}
                                    textAnchor="end"
                                    height={40}
                                />
                                <YAxis fontSize={10} width={30} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--popover))', borderColor: 'hsl(var(--border))', fontSize: 12 }}
                                />
                                <Bar dataKey="count" name="False" fill="#ef4444" radius={[3, 3, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Broken Times */}
                <Card>
                    <CardHeader className="pb-2 pt-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">Session Breaks</CardTitle>
                            <div className="flex gap-2 text-xs">
                                <Badge variant="secondary" className="font-mono">Med: {brokenStats.median}</Badge>
                                <Badge variant="outline" className="font-mono">Mode: {brokenStats.mode}</Badge>
                                <Badge>{brokenStats.count}</Badge>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="h-[180px] pt-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={brokenData}>
                                <XAxis
                                    dataKey="time"
                                    fontSize={9}
                                    interval={granularity <= 5 ? 11 : granularity <= 15 ? 3 : 0}
                                    angle={-45}
                                    textAnchor="end"
                                    height={40}
                                />
                                <YAxis fontSize={10} width={30} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--popover))', borderColor: 'hsl(var(--border))', fontSize: 12 }}
                                />
                                <Bar dataKey="count" name="Broken" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
