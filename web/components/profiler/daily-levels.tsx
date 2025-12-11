"use client"

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LevelTouchesResponse, LevelTouchEntry } from '@/lib/api/profiler';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip
} from 'recharts';

interface DailyLevelsProps {
    levelTouches: LevelTouchesResponse | null;
    filteredDates: Set<string>;
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

interface LevelCardProps {
    title: string;
    levelKey: string;
    levelTouches: LevelTouchesResponse;
    filteredDates: Set<string>;
    granularity: number;
    color: string;
}

function LevelCard({ title, levelKey, levelTouches, filteredDates, granularity, color }: LevelCardProps) {
    // Calculate stats for this level
    const stats = useMemo(() => {
        const touchTimes: number[] = [];
        let touched = 0;
        let total = 0;

        filteredDates.forEach(date => {
            const dayData = levelTouches[date];
            if (!dayData) return;

            const entry = dayData[levelKey as keyof typeof dayData] as LevelTouchEntry | undefined;
            if (!entry) return;

            total++;
            if (entry.touched && entry.touch_time) {
                touched++;
                touchTimes.push(timeToMinutes(entry.touch_time));
            }
        });

        const hitRate = total > 0 ? (touched / total) * 100 : 0;
        const mode = touchTimes.length > 0 ? minutesToTime(calculateMode(touchTimes, granularity)) : 'N/A';
        const median = touchTimes.length > 0 ? minutesToTime(Math.round(calculateMedian(touchTimes))) : 'N/A';

        // Build histogram
        const buckets: Record<number, number> = {};
        touchTimes.forEach(t => {
            const bucket = Math.floor(t / granularity) * granularity;
            buckets[bucket] = (buckets[bucket] || 0) + 1;
        });

        // Create data from 06:00 to 16:00 (main session)
        const data: { time: string; count: number }[] = [];
        for (let m = 6 * 60; m <= 16 * 60; m += granularity) {
            const pct = touchTimes.length > 0 ? ((buckets[m] || 0) / touchTimes.length) * 100 : 0;
            data.push({
                time: minutesToTime(m),
                count: pct
            });
        }

        return { hitRate, mode, median, data, touched, total };
    }, [levelTouches, filteredDates, levelKey, granularity]);

    return (
        <Card className="border">
            <CardHeader className="py-2 px-3 bg-muted/30">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium">{title}</CardTitle>
                    <Badge variant="outline" className="font-bold">
                        {stats.hitRate.toFixed(1)}%
                    </Badge>
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Mode: <span className="font-medium">{stats.mode}</span></span>
                    <span>Median: <span className="font-medium">{stats.median}</span></span>
                </div>
            </CardHeader>
            <CardContent className="p-2">
                <div className="h-24">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={stats.data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                            <XAxis
                                dataKey="time"
                                tick={{ fontSize: 8 }}
                                interval={Math.floor(stats.data.length / 4)}
                            />
                            <YAxis tick={{ fontSize: 8 }} domain={[0, 'auto']} />
                            <Tooltip
                                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Touches']}
                            />
                            <Bar dataKey="count" fill={color} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
}

export function DailyLevels({ levelTouches, filteredDates }: DailyLevelsProps) {
    const [granularity, setGranularity] = useState<number>(15);

    if (!levelTouches || filteredDates.size === 0) {
        return <div className="text-muted-foreground text-center py-8">Loading level data...</div>;
    }

    return (
        <div className="space-y-6">
            {/* Granularity selector */}
            <div className="flex justify-end">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Granularity:</span>
                    <Select
                        value={granularity.toString()}
                        onValueChange={(v) => setGranularity(Number(v))}
                    >
                        <SelectTrigger className="h-8 w-20">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="15">15min</SelectItem>
                            <SelectItem value="30">30min</SelectItem>
                            <SelectItem value="60">1hr</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Previous Day Levels */}
            <div>
                <h3 className="text-lg font-semibold mb-3">Previous Day Levels</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <LevelCard
                        title="Previous Day Low"
                        levelKey="pdl"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#ef4444"
                    />
                    <LevelCard
                        title="Previous Day Mid"
                        levelKey="pdm"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#f59e0b"
                    />
                    <LevelCard
                        title="Previous Day High"
                        levelKey="pdh"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#22c55e"
                    />
                </div>
            </div>

            {/* P12 Levels */}
            <div>
                <h3 className="text-lg font-semibold mb-3">P12 Levels (Overnight)</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <LevelCard
                        title="P12 High"
                        levelKey="p12h"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#22c55e"
                    />
                    <LevelCard
                        title="P12 Mid"
                        levelKey="p12m"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#06b6d4"
                    />
                    <LevelCard
                        title="P12 Low"
                        levelKey="p12l"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#ef4444"
                    />
                </div>
            </div>

            {/* Time-Based Opens */}
            <div>
                <h3 className="text-lg font-semibold mb-3">Time-Based Opens</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <LevelCard
                        title="Daily Open (18:00)"
                        levelKey="daily_open"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#8b5cf6"
                    />
                    <LevelCard
                        title="Midnight Open (00:00)"
                        levelKey="midnight_open"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#a855f7"
                    />
                    <LevelCard
                        title="07:30 Open"
                        levelKey="open_0730"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#c084fc"
                    />
                </div>
            </div>

            {/* Session Mids */}
            <div>
                <h3 className="text-lg font-semibold mb-3">Session Mids</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <LevelCard
                        title="Asia Mid"
                        levelKey="asia_mid"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#f472b6"
                    />
                    <LevelCard
                        title="London Mid"
                        levelKey="london_mid"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#fb923c"
                    />
                    <LevelCard
                        title="NY1 Mid"
                        levelKey="ny1_mid"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#38bdf8"
                    />
                    <LevelCard
                        title="NY2 Mid"
                        levelKey="ny2_mid"
                        levelTouches={levelTouches}
                        filteredDates={filteredDates}
                        granularity={granularity}
                        color="#34d399"
                    />
                </div>
            </div>
        </div>
    );
}
