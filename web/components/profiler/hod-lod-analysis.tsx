
"use client"

import { useMemo } from 'react';
import { ProfilerSession, DailyHodLodResponse } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ComposedChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useState } from 'react';

interface Props {
    sessions: ProfilerSession[];
    dailyHodLod?: DailyHodLodResponse | null;
}

// Helper functions
function timeToMinutes(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
}

function minutesToTime(mins: number): string {
    const h = Math.floor(mins / 60) % 24;
    const m = mins % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function roundToBucket(time: string, granularity: number): string {
    const mins = timeToMinutes(time);
    const rounded = Math.floor(mins / granularity) * granularity;
    return minutesToTime(rounded);
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

export function HodLodAnalysis({ sessions, dailyHodLod }: Props) {
    const [granularity, setGranularity] = useState<number>(15);

    // Get unique dates from filtered sessions
    const filteredDates = useMemo(() => {
        return new Set(sessions.map(s => s.date));
    }, [sessions]);

    // Calculate HOD/LOD times from TRUE daily data (filtered by date)
    const { timeHistogramData, hodStats, lodStats } = useMemo(() => {
        const hodTimes: string[] = [];
        const lodTimes: string[] = [];

        // Use true daily HOD/LOD data if available
        if (dailyHodLod) {
            filteredDates.forEach(date => {
                const dayData = dailyHodLod[date];
                if (dayData) {
                    if (dayData.hod_time) hodTimes.push(dayData.hod_time);
                    if (dayData.lod_time) lodTimes.push(dayData.lod_time);
                }
            });
        } else {
            // Fallback to session-based calculation (less accurate)
            const byDate: Record<string, ProfilerSession[]> = {};
            sessions.forEach(s => {
                if (!byDate[s.date]) byDate[s.date] = [];
                byDate[s.date].push(s);
            });

            Object.values(byDate).forEach(daySessions => {
                if (daySessions.length < 2) return;
                let maxH = -Infinity, minL = Infinity;
                let hodSession: ProfilerSession | null = null;
                let lodSession: ProfilerSession | null = null;

                daySessions.forEach(s => {
                    if (s.range_high > maxH) { maxH = s.range_high; hodSession = s; }
                    if (s.range_low < minL) { minL = s.range_low; lodSession = s; }
                });

                const hTime = (hodSession as ProfilerSession | null)?.high_time;
                const lTime = (lodSession as ProfilerSession | null)?.low_time;
                if (hTime) hodTimes.push(hTime);
                if (lTime) lodTimes.push(lTime);
            });
        }

        // Consolidate times 16:15-17:00 into 16:15 boundary
        const consolidate = (times: string[]) => times.map(t => {
            const mins = timeToMinutes(t);
            // 16:15 is 975 min, 17:00 is 1020 min
            if (mins >= 975 && mins <= 1020) return "16:15";
            return t;
        });

        const finalHodTimes = consolidate(hodTimes);
        const finalLodTimes = consolidate(lodTimes);

        if (finalHodTimes.length === 0 && finalLodTimes.length === 0) {
            return { timeHistogramData: [], hodStats: null, lodStats: null };
        }

        // Bucket the times
        const hodBuckets: Record<string, number> = {};
        const lodBuckets: Record<string, number> = {};

        finalHodTimes.forEach(t => {
            const bucket = roundToBucket(t, granularity);
            hodBuckets[bucket] = (hodBuckets[bucket] || 0) + 1;
        });

        finalLodTimes.forEach(t => {
            const bucket = roundToBucket(t, granularity);
            lodBuckets[bucket] = (lodBuckets[bucket] || 0) + 1;
        });

        // Create ordered time slots from 18:00 to 16:59 (trading day)
        const orderedTimes: string[] = [];
        for (let mins = 18 * 60; mins < 24 * 60; mins += granularity) {
            orderedTimes.push(minutesToTime(mins));
        }
        for (let mins = 0; mins < 17 * 60; mins += granularity) {
            orderedTimes.push(minutesToTime(mins));
        }

        const totalHod = finalHodTimes.length || 1;
        const totalLod = finalLodTimes.length || 1;

        const data = orderedTimes.map(time => ({
            time,
            hodPercent: ((hodBuckets[time] || 0) / totalHod) * 100,
            lodPercent: -((lodBuckets[time] || 0) / totalLod) * 100,
            hodCount: hodBuckets[time] || 0,
            lodCount: lodBuckets[time] || 0,
        }));

        // Stats
        const hodBucketed = finalHodTimes.map(t => roundToBucket(t, granularity));
        const lodBucketed = finalLodTimes.map(t => roundToBucket(t, granularity));

        return {
            timeHistogramData: data,
            hodStats: {
                median: minutesToTime(Math.round(median(finalHodTimes.map(timeToMinutes)))),
                mode: mode(hodBucketed),
                count: finalHodTimes.length,
            },
            lodStats: {
                median: minutesToTime(Math.round(median(finalLodTimes.map(timeToMinutes)))),
                mode: mode(lodBucketed),
                count: finalLodTimes.length,
            },
        };
    }, [sessions, granularity, dailyHodLod, filteredDates]);

    // Session-based stats (which session makes HOD/LOD)
    const sessionStats = useMemo(() => {
        const byDate: Record<string, ProfilerSession[]> = {};
        sessions.forEach(s => {
            if (!byDate[s.date]) byDate[s.date] = [];
            byDate[s.date].push(s);
        });

        const hodSessions: string[] = [];
        const lodSessions: string[] = [];

        Object.values(byDate).forEach(daySessions => {
            if (daySessions.length < 2) return;
            let maxH = -Infinity, minL = Infinity, hodS = '', lodS = '';
            daySessions.forEach(s => {
                if (s.range_high > maxH) { maxH = s.range_high; hodS = s.session; }
                if (s.range_low < minL) { minL = s.range_low; lodS = s.session; }
            });
            if (hodS) hodSessions.push(hodS);
            if (lodS) lodSessions.push(lodS);
        });

        const countBy = (arr: string[]) => {
            const c: Record<string, number> = { Asia: 0, London: 0, NY1: 0, NY2: 0 };
            arr.forEach(s => c[s] = (c[s] || 0) + 1);
            return Object.entries(c).map(([session, count]) => ({ session, count }));
        };

        return {
            hod: countBy(hodSessions),
            lod: countBy(lodSessions),
            totalDays: Object.keys(byDate).length,
        };
    }, [sessions]);

    const granularityOptions = [
        { value: 5, label: '5m' },
        { value: 15, label: '15m' },
        { value: 30, label: '30m' },
        { value: 60, label: '1h' },
    ];

    return (
        <div className="space-y-4">
            {/* Combined HOD/LOD Time Histogram */}
            <Card>
                <CardHeader className="pb-2 pt-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">High and Low of Day Times</CardTitle>
                        <Select value={granularity.toString()} onValueChange={(v) => setGranularity(parseInt(v))}>
                            <SelectTrigger className="w-[70px] h-8">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {granularityOptions.map(o => (
                                    <SelectItem key={o.value} value={o.value.toString()}>{o.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="flex gap-6 mt-2 text-sm">
                        <div className="flex items-center gap-2 bg-green-50 dark:bg-green-950 px-3 py-1 rounded">
                            <TrendingUp className="h-4 w-4 text-green-600" />
                            <span className="font-medium text-green-700 dark:text-green-400">HOD</span>
                            <span className="text-muted-foreground">Mode:</span>
                            <span className="font-mono font-bold">{hodStats?.mode || '-'}</span>
                            <span className="text-muted-foreground">Med:</span>
                            <span className="font-mono">{hodStats?.median || '-'}</span>
                            <Badge variant="outline" className="ml-1">{hodStats?.count || 0}</Badge>
                        </div>
                        <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950 px-3 py-1 rounded">
                            <TrendingDown className="h-4 w-4 text-red-600" />
                            <span className="font-medium text-red-700 dark:text-red-400">LOD</span>
                            <span className="text-muted-foreground">Mode:</span>
                            <span className="font-mono font-bold">{lodStats?.mode || '-'}</span>
                            <span className="text-muted-foreground">Med:</span>
                            <span className="font-mono">{lodStats?.median || '-'}</span>
                            <Badge variant="outline" className="ml-1">{lodStats?.count || 0}</Badge>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="h-[280px] pt-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={timeHistogramData} margin={{ top: 10, right: 10, bottom: 30, left: 10 }}>
                            <XAxis
                                dataKey="time"
                                fontSize={9}
                                interval={granularity <= 15 ? 3 : 1}
                                angle={-45}
                                textAnchor="end"
                                height={50}
                            />
                            <YAxis
                                fontSize={10}
                                tickFormatter={(v) => `${Math.abs(v).toFixed(0)}%`}
                                domain={['auto', 'auto']}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'hsl(var(--background))',
                                    borderColor: 'hsl(var(--border))',
                                    padding: '8px 12px',
                                    borderRadius: '6px',
                                    fontSize: '12px',
                                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                                }}
                                itemStyle={{ color: 'hsl(var(--foreground))' }}
                                labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold', marginBottom: 4 }}
                                cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                                formatter={(value: number, name: string, props: any) => {
                                    const isHod = props.dataKey === 'hodPercent';
                                    const count = isHod ? props.payload.hodCount : props.payload.lodCount;
                                    return [`${Math.abs(value).toFixed(1)}% (${count} days)`, isHod ? '🟢 HOD' : '🔴 LOD'];
                                }}
                            />
                            <ReferenceLine y={0} stroke="hsl(var(--border))" />
                            <Bar dataKey="hodPercent" name="HOD" fill="#22c55e" radius={[2, 2, 0, 0]} />
                            <Bar dataKey="lodPercent" name="LOD" fill="#ef4444" radius={[0, 0, 2, 2]} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Which Session Makes HOD/LOD */}
            <div className="grid grid-cols-2 gap-3">
                <Card className="border-green-200">
                    <CardHeader className="pb-1 pt-2 px-3">
                        <CardTitle className="text-xs text-green-700 flex items-center gap-2">
                            <TrendingUp className="h-3 w-3" /> Which Session Makes HOD?
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-2">
                        <div className="space-y-1">
                            {sessionStats.hod.sort((a, b) => b.count - a.count).map(({ session, count }) => {
                                const pct = sessionStats.totalDays > 0 ? (count / sessionStats.totalDays) * 100 : 0;
                                return (
                                    <div key={session} className="flex items-center gap-2 text-xs">
                                        <span className="w-12">{session}</span>
                                        <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
                                            <div className="h-full bg-green-500 rounded" style={{ width: `${pct}%` }} />
                                        </div>
                                        <span className="w-10 text-right font-mono">{pct.toFixed(0)}%</span>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>

                <Card className="border-red-200">
                    <CardHeader className="pb-1 pt-2 px-3">
                        <CardTitle className="text-xs text-red-700 flex items-center gap-2">
                            <TrendingDown className="h-3 w-3" /> Which Session Makes LOD?
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-2">
                        <div className="space-y-1">
                            {sessionStats.lod.sort((a, b) => b.count - a.count).map(({ session, count }) => {
                                const pct = sessionStats.totalDays > 0 ? (count / sessionStats.totalDays) * 100 : 0;
                                return (
                                    <div key={session} className="flex items-center gap-2 text-xs">
                                        <span className="w-12">{session}</span>
                                        <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
                                            <div className="h-full bg-red-500 rounded" style={{ width: `${pct}%` }} />
                                        </div>
                                        <span className="w-10 text-right font-mono">{pct.toFixed(0)}%</span>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
