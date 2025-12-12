"use client"

import { useMemo, useState, memo } from 'react';
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
    limitLevels?: string[];
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
    const stats = useMemo(() => {
        let touched = 0;
        let total = 0;
        const touchTimes: string[] = [];

        filteredDates.forEach(date => {
            const dayData = levelTouches[date];
            if (!dayData) return;

            const levelData = dayData[levelKey as keyof typeof dayData] as LevelTouchEntry | undefined;
            if (!levelData) return;

            total++;
            if (levelData.touched) {
                touched++;
                if (levelData.touch_time) {
                    touchTimes.push(levelData.touch_time);
                }
            }
        });

        const hitRate = total > 0 ? (touched / total) * 100 : 0;

        // Calculate time distribution
        const timeBuckets: Record<string, number> = {};
        touchTimes.forEach(time => {
            const [h, m] = time.split(':').map(Number);
            const mins = h * 60 + m;
            const bucketMins = Math.floor(mins / granularity) * granularity;
            const bucketH = Math.floor(bucketMins / 60);
            const bucketM = bucketMins % 60;
            const bucket = `${bucketH.toString().padStart(2, '0')}:${bucketM.toString().padStart(2, '0')}`;
            timeBuckets[bucket] = (timeBuckets[bucket] || 0) + 1;
        });

        // Find mode
        const mode = Object.entries(timeBuckets).sort((a, b) => b[1] - a[1])[0]?.[0] || '-';

        // Create histogram data
        const histData = Object.entries(timeBuckets)
            .map(([time, count]) => ({ time, count, pct: (count / touched) * 100 }))
            .sort((a, b) => a.time.localeCompare(b.time));

        return { hitRate, mode, total, touched, histData };
    }, [levelTouches, filteredDates, levelKey, granularity]);

    return (
        <Card>
            <CardHeader className="pb-2 pt-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium">{title}</CardTitle>
                    <Badge variant="outline" className="text-lg font-bold" style={{ color }}>
                        {stats.hitRate.toFixed(1)}%
                    </Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                    Mode: <span className="font-mono font-semibold">{stats.mode}</span> •
                    {stats.touched}/{stats.total} days
                </div>
            </CardHeader>
            <CardContent className="h-[120px] pt-0">
                {stats.histData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={stats.histData} margin={{ top: 5, right: 5, bottom: 20, left: 5 }}>
                            <XAxis dataKey="time" fontSize={8} angle={-45} textAnchor="end" height={40} interval={0} />
                            <YAxis hide />
                            <Tooltip
                                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Frequency']}
                                contentStyle={{ fontSize: '12px' }}
                            />
                            <Bar dataKey="pct" fill={color} radius={[2, 2, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                        No touch data
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// Export optimized component
export const DailyLevels = memo(function DailyLevels({ levelTouches, filteredDates, limitLevels }: DailyLevelsProps) {
    const [granularity, setGranularity] = useState<number>(15);

    if (!levelTouches || filteredDates.size === 0) {
        return <div className="text-muted-foreground text-center py-8">Loading level data...</div>;
    }

    const shouldShow = (key: string) => !limitLevels || limitLevels.includes(key);

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
            {(shouldShow('pdl') || shouldShow('pdm') || shouldShow('pdh')) && (
                <div>
                    <h3 className="text-lg font-semibold mb-3">Previous Day Levels</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {shouldShow('pdl') && <LevelCard title="Previous Day Low" levelKey="pdl" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#ef4444" />}
                        {shouldShow('pdm') && <LevelCard title="Previous Day Mid" levelKey="pdm" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#f59e0b" />}
                        {shouldShow('pdh') && <LevelCard title="Previous Day High" levelKey="pdh" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#22c55e" />}
                    </div>
                </div>
            )}

            {/* P12 Levels */}
            {(shouldShow('p12h') || shouldShow('p12m') || shouldShow('p12l')) && (
                <div>
                    <h3 className="text-lg font-semibold mb-3">P12 Levels (Overnight)</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {shouldShow('p12h') && <LevelCard title="P12 High" levelKey="p12h" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#22c55e" />}
                        {shouldShow('p12m') && <LevelCard title="P12 Mid" levelKey="p12m" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#06b6d4" />}
                        {shouldShow('p12l') && <LevelCard title="P12 Low" levelKey="p12l" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#ef4444" />}
                    </div>
                </div>
            )}

            {/* Time-Based Opens */}
            {(shouldShow('daily_open') || shouldShow('midnight_open') || shouldShow('open_0730')) && (
                <div>
                    <h3 className="text-lg font-semibold mb-3">Time-Based Opens</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {shouldShow('daily_open') && <LevelCard title="Daily Open (18:00)" levelKey="daily_open" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#8b5cf6" />}
                        {shouldShow('midnight_open') && <LevelCard title="Midnight Open (00:00)" levelKey="midnight_open" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#a855f7" />}
                        {shouldShow('open_0730') && <LevelCard title="07:30 Open" levelKey="open_0730" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#c084fc" />}
                    </div>
                </div>
            )}

            {/* Session Mids */}
            {(shouldShow('asia_mid') || shouldShow('london_mid') || shouldShow('ny1_mid') || shouldShow('ny2_mid')) && (
                <div>
                    <h3 className="text-lg font-semibold mb-3">Session Mids</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {shouldShow('asia_mid') && <LevelCard title="Asia Mid" levelKey="asia_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#f472b6" />}
                        {shouldShow('london_mid') && <LevelCard title="London Mid" levelKey="london_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#fb923c" />}
                        {shouldShow('ny1_mid') && <LevelCard title="NY1 Mid" levelKey="ny1_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#38bdf8" />}
                        {shouldShow('ny2_mid') && <LevelCard title="NY2 Mid" levelKey="ny2_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#34d399" />}
                    </div>
                </div>
            )}
        </div>
    );
});
