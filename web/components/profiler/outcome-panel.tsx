"use client"

import { useMemo, useState } from 'react';
import { ProfilerSession, DailyHodLodResponse } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
    ResponsiveContainer,
    ComposedChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ReferenceLine
} from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface OutcomePanelProps {
    outcomeName: string;  // e.g., "Short True"
    sessions: ProfilerSession[];  // Sessions matching this outcome for the target session
    outcomeDates?: Set<string>;  // Dates that match this outcome
    totalInCategory: number;  // Total days in the filter category (for probability)
    targetSession: string;  // Which session we're analyzing (NY1, NY2, etc.)
    dailyHodLod?: DailyHodLodResponse | null;  // True daily HOD/LOD times
}

// Time bucket helpers
function timeToMinutes(timeStr: string): number {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
}

function minutesToTime(minutes: number): string {
    const h = Math.floor(minutes / 60) % 24;
    const m = minutes % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function calculateMedian(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function calculateMode(arr: number[], bucketSize: number): number {
    if (arr.length === 0) return 0;
    const buckets: Record<number, number> = {};
    arr.forEach(v => {
        const bucket = Math.floor(v / bucketSize) * bucketSize;
        buckets[bucket] = (buckets[bucket] || 0) + 1;
    });
    let maxCount = 0;
    let mode = 0;
    Object.entries(buckets).forEach(([k, count]) => {
        if (count > maxCount) {
            maxCount = count;
            mode = Number(k);
        }
    });
    return mode;
}

export function OutcomePanel({ outcomeName, sessions, outcomeDates, totalInCategory, targetSession, dailyHodLod }: OutcomePanelProps) {
    const [granularity, setGranularity] = useState<number>(15);

    // Count unique days from sessions for probability calculation
    const uniqueDays = useMemo(() => {
        return new Set(sessions.map(s => s.date)).size;
    }, [sessions]);

    const probability = totalInCategory > 0
        ? ((uniqueDays / totalInCategory) * 100).toFixed(1)
        : '0.0';

    // Calculate Price Range Distribution (High/Low % from Open)
    const { highDistData, lowDistData, highRangeStats, lowRangeStats } = useMemo(() => {
        const highPcts: number[] = [];
        const lowPcts: number[] = [];

        // Use true daily data if available, otherwise session fallback
        if (dailyHodLod) {
            // Use outcomeDates if available to ensure we only count each day once
            const datesToProcess = outcomeDates ? Array.from(outcomeDates) : Array.from(new Set(sessions.map(s => s.date)));

            datesToProcess.forEach(date => {
                const dayData = dailyHodLod[date];
                if (dayData && dayData.daily_open > 0) {
                    const hp = ((dayData.daily_high - dayData.daily_open) / dayData.daily_open) * 100;
                    const lp = ((dayData.daily_low - dayData.daily_open) / dayData.daily_open) * 100;
                    highPcts.push(hp);
                    lowPcts.push(lp);
                }
            });
        } else {
            // Fallback: This path is less accurate as we don't have daily open
            // We could try to deduce it but since we always fetch dailyHodLod in parent, this case handles 'loading' or missing data
        }

        const bucketSize = 0.1;
        const buildDist = (values: number[]) => {
            const buckets: Record<string, number> = {};
            values.forEach(v => {
                const b = (Math.round(v / bucketSize) * bucketSize).toFixed(1);
                buckets[b] = (buckets[b] || 0) + 1;
            });
            const total = values.length || 1;
            return Object.entries(buckets)
                .map(([k, count]) => ({
                    pct: parseFloat(k),
                    percent: (count / total) * 100,
                    count
                }))
                .sort((a, b) => a.pct - b.pct);
        };

        return {
            highDistData: buildDist(highPcts),
            lowDistData: buildDist(lowPcts),
            highRangeStats: {
                median: highPcts.length > 0 ? calculateMedian(highPcts) : 0,
                mode: highPcts.length > 0 ? calculateMode(highPcts, bucketSize) : 0,
                count: highPcts.length
            },
            lowRangeStats: {
                median: lowPcts.length > 0 ? calculateMedian(lowPcts) : 0,
                mode: lowPcts.length > 0 ? calculateMode(lowPcts, bucketSize) : 0,
                count: lowPcts.length
            }
        };
    }, [sessions, dailyHodLod, outcomeDates]);

    // Calculate HOD/LOD time distributions using true daily data when available
    const { timeHistogramData, hodStats, lodStats } = useMemo(() => {
        const hodTimes: number[] = [];
        const lodTimes: number[] = [];

        // Use true daily HOD/LOD data if available
        if (dailyHodLod && outcomeDates) {
            outcomeDates.forEach(date => {
                const dayData = dailyHodLod[date];
                if (dayData) {
                    if (dayData.hod_time) hodTimes.push(timeToMinutes(dayData.hod_time));
                    if (dayData.lod_time) lodTimes.push(timeToMinutes(dayData.lod_time));
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
                let dailyHigh = -Infinity;
                let dailyLow = Infinity;
                let dailyHighTime: string | null = null;
                let dailyLowTime: string | null = null;

                daySessions.forEach(s => {
                    if (s.range_high > dailyHigh && s.high_time) {
                        dailyHigh = s.range_high;
                        dailyHighTime = s.high_time;
                    }
                    if (s.range_low < dailyLow && s.low_time) {
                        dailyLow = s.range_low;
                        dailyLowTime = s.low_time;
                    }
                });

                if (dailyHighTime) {
                    const ht: string = dailyHighTime;
                    const time = ht.split('T')[1]?.slice(0, 5) || ht.slice(0, 5);
                    hodTimes.push(timeToMinutes(time));
                }
                if (dailyLowTime) {
                    const lt: string = dailyLowTime;
                    const time = lt.split('T')[1]?.slice(0, 5) || lt.slice(0, 5);
                    lodTimes.push(timeToMinutes(time));
                }
            });
        }

        // Bucket times
        const hodBuckets: Record<number, number> = {};
        const lodBuckets: Record<number, number> = {};

        hodTimes.forEach(t => {
            const bucket = Math.floor(t / granularity) * granularity;
            hodBuckets[bucket] = (hodBuckets[bucket] || 0) + 1;
        });

        lodTimes.forEach(t => {
            const bucket = Math.floor(t / granularity) * granularity;
            lodBuckets[bucket] = (lodBuckets[bucket] || 0) + 1;
        });

        // Create histogram data (18:00 to 17:00 next day)
        const data: { time: string; hod: number; lod: number }[] = [];
        const startMin = 18 * 60; // 18:00
        const endMin = 17 * 60;   // 17:00

        for (let m = startMin; m < 24 * 60; m += granularity) {
            const hodPct = hodTimes.length > 0 ? ((hodBuckets[m] || 0) / hodTimes.length) * 100 : 0;
            const lodPct = lodTimes.length > 0 ? ((lodBuckets[m] || 0) / lodTimes.length) * 100 : 0;
            data.push({
                time: minutesToTime(m),
                hod: hodPct,
                lod: -lodPct
            });
        }
        for (let m = 0; m <= endMin; m += granularity) {
            const hodPct = hodTimes.length > 0 ? ((hodBuckets[m] || 0) / hodTimes.length) * 100 : 0;
            const lodPct = lodTimes.length > 0 ? ((lodBuckets[m] || 0) / lodTimes.length) * 100 : 0;
            data.push({
                time: minutesToTime(m),
                hod: hodPct,
                lod: -lodPct
            });
        }

        // Calculate stats
        const hodStatsCalc = {
            median: hodTimes.length > 0 ? minutesToTime(Math.round(calculateMedian(hodTimes))) : 'N/A',
            mode: hodTimes.length > 0 ? minutesToTime(calculateMode(hodTimes, granularity)) : 'N/A',
            count: hodTimes.length
        };
        const lodStatsCalc = {
            median: lodTimes.length > 0 ? minutesToTime(Math.round(calculateMedian(lodTimes))) : 'N/A',
            mode: lodTimes.length > 0 ? minutesToTime(calculateMode(lodTimes, granularity)) : 'N/A',
            count: lodTimes.length
        };

        return { timeHistogramData: data, hodStats: hodStatsCalc, lodStats: lodStatsCalc };
    }, [sessions, granularity, dailyHodLod, outcomeDates]);

    // Calculate reference level touch rates
    const referenceLevelStats = useMemo(() => {
        // Group by date
        const byDate: Record<string, ProfilerSession[]> = {};
        sessions.forEach(s => {
            if (!byDate[s.date]) byDate[s.date] = [];
            byDate[s.date].push(s);
        });

        const stats: Record<string, { touched: number; total: number }> = {
            'Asia Mid': { touched: 0, total: 0 },
            'London Mid': { touched: 0, total: 0 },
            'NY1 Mid': { touched: 0, total: 0 },
            'NY2 Mid': { touched: 0, total: 0 }
        };

        Object.values(byDate).forEach(daySessions => {
            const sessionMap: Record<string, ProfilerSession> = {};
            daySessions.forEach(s => { sessionMap[s.session] = s; });

            // Get target session data
            const target = sessionMap[targetSession];
            if (!target) return;

            // Check if each prior session mid was touched during/after
            const sessions = ['Asia', 'London', 'NY1', 'NY2'];
            sessions.forEach(sess => {
                const sessData = sessionMap[sess];
                if (!sessData) return;

                const key = `${sess} Mid`;
                if (!stats[key]) return;

                stats[key].total++;

                // Check if session mid was touched by looking at subsequent sessions
                const mid = sessData.mid;
                const sessIdx = sessions.indexOf(sess);
                const targetIdx = sessions.indexOf(targetSession);

                // Check all sessions from sess to target
                for (let i = sessIdx; i <= targetIdx; i++) {
                    const checkSess = sessionMap[sessions[i]];
                    if (checkSess && checkSess.range_low <= mid && checkSess.range_high >= mid) {
                        stats[key].touched++;
                        break;
                    }
                }
            });
        });

        return Object.entries(stats).map(([name, data]) => ({
            name,
            rate: data.total > 0 ? ((data.touched / data.total) * 100).toFixed(1) : '0.0'
        }));
    }, [sessions, targetSession]);

    return (
        <Card className="border-2">
            <CardHeader className="py-3 bg-muted/30">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{outcomeName}</CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-base font-bold">
                            {probability}%
                        </Badge>
                        <Badge variant="secondary">
                            {uniqueDays} days
                        </Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-4 space-y-6">
                {/* HOD/LOD Time Distribution */}
                <div>
                    <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium">HOD/LOD Times</h4>
                        <Select
                            value={granularity.toString()}
                            onValueChange={(v) => setGranularity(Number(v))}
                        >
                            <SelectTrigger className="h-6 w-16 text-xs">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="15">15m</SelectItem>
                                <SelectItem value="30">30m</SelectItem>
                                <SelectItem value="60">1h</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="text-xs text-muted-foreground flex gap-4 mb-1">
                        <span>HOD Mode: <span className="text-green-600 font-medium">{hodStats.mode}</span></span>
                        <span>LOD Mode: <span className="text-red-600 font-medium">{lodStats.mode}</span></span>
                    </div>
                    <div className="h-32">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={timeHistogramData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                                <XAxis
                                    dataKey="time"
                                    tick={{ fontSize: 9 }}
                                    interval={Math.floor(timeHistogramData.length / 6)}
                                />
                                <YAxis tick={{ fontSize: 9 }} domain={['auto', 'auto']} />
                                <Tooltip
                                    formatter={(value: number, name: string) => [
                                        `${Math.abs(value).toFixed(1)}%`,
                                        name === 'hod' ? 'HOD' : 'LOD'
                                    ]}
                                />
                                <ReferenceLine y={0} stroke="#666" strokeWidth={0.5} />
                                <Bar dataKey="hod" fill="#22c55e" />
                                <Bar dataKey="lod" fill="#ef4444" />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Price Range Distribution (High & Low) */}
                <div>
                    <h4 className="text-sm font-medium mb-2">Price Range Distribution (Daily)</h4>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* High Dist */}
                        <div className="border rounded-lg p-0 overflow-hidden">
                            <div className="p-4 pb-2">
                                <h3 className="text-base font-semibold flex items-center gap-2 mb-2">
                                    <TrendingUp className="h-4 w-4 text-green-600" />
                                    High Distribution (from Open)
                                </h3>
                                <div className="flex flex-wrap gap-3 text-sm">
                                    <div className="flex items-center gap-2 bg-green-50 dark:bg-green-950 px-2 py-1 rounded">
                                        <span className="text-muted-foreground">Mode:</span>
                                        <span className="font-mono font-bold">{highRangeStats.mode.toFixed(1)}%</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground">Median:</span>
                                        <span className="font-mono">{highRangeStats.median.toFixed(2)}%</span>
                                    </div>
                                    <Badge variant="outline">{highRangeStats.count} days</Badge>
                                </div>
                            </div>
                            <div className="h-48 px-2 pb-2">
                                <ResponsiveContainer width="100%" height="100%">
                                    <ComposedChart data={highDistData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
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
                                            labelFormatter={(v) => `+${v}%`}
                                            formatter={(v: number) => [`${v.toFixed(1)}%`, 'Frequency']}
                                        />
                                        <ReferenceLine x={highRangeStats.median} stroke="#22c55e" strokeDasharray="3 3" />
                                        <Bar dataKey="percent" fill="#22c55e" radius={[2, 2, 0, 0]} opacity={0.8} />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                        {/* Low Dist */}
                        <div className="border rounded-lg p-0 overflow-hidden">
                            <div className="p-4 pb-2">
                                <h3 className="text-base font-semibold flex items-center gap-2 mb-2">
                                    <TrendingDown className="h-4 w-4 text-red-600" />
                                    Low Distribution (from Open)
                                </h3>
                                <div className="flex flex-wrap gap-3 text-sm">
                                    <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950 px-2 py-1 rounded">
                                        <span className="text-muted-foreground">Mode:</span>
                                        <span className="font-mono font-bold">{lowRangeStats.mode.toFixed(1)}%</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground">Median:</span>
                                        <span className="font-mono">{lowRangeStats.median.toFixed(2)}%</span>
                                    </div>
                                    <Badge variant="outline">{lowRangeStats.count} days</Badge>
                                </div>
                            </div>
                            <div className="h-48 px-2 pb-2">
                                <ResponsiveContainer width="100%" height="100%">
                                    <ComposedChart data={lowDistData} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
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
                                            labelFormatter={(v) => `${v}%`}
                                            formatter={(v: number) => [`${v.toFixed(1)}%`, 'Frequency']}
                                        />
                                        <ReferenceLine x={lowRangeStats.median} stroke="#ef4444" strokeDasharray="3 3" />
                                        <Bar dataKey="percent" fill="#ef4444" radius={[2, 2, 0, 0]} opacity={0.8} />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Reference Level Touch Rates */}
                <div>
                    <h4 className="text-sm font-medium mb-2">Session Mid Touch Rates</h4>
                    <div className="grid grid-cols-2 gap-1 text-xs">
                        {referenceLevelStats.map(({ name, rate }) => (
                            <div key={name} className="flex justify-between bg-muted/30 px-2 py-1 rounded">
                                <span>{name}</span>
                                <span className="font-medium">{rate}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
