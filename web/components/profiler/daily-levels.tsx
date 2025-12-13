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
    Tooltip,
    Brush,
    ReferenceLine
} from 'recharts';

const SESSION_RANGES: Record<string, { start: string; end: string }> = {
    'Asia': { start: '18:00', end: '02:00' },
    'London': { start: '02:00', end: '07:00' },
    'NY1': { start: '08:00', end: '12:00' },
    'NY2': { start: '12:00', end: '16:00' },
    'P12': { start: '06:00', end: '17:00' },
    'Daily': { start: '18:00', end: '17:00' },
    // Custom Bounds for specific levels
    'Midnight': { start: '00:00', end: '17:00' },
    'Open0730': { start: '07:30', end: '17:00' },
    'AsiaMid': { start: '02:00', end: '17:00' },
    'LondonMid': { start: '07:00', end: '17:00' },
    'NY1Mid': { start: '12:00', end: '17:00' },
    'NY2Mid': { start: '16:00', end: '17:00' },
};

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
    targetSession: string; // Add targetSession prop
}

function LevelCard({ title, levelKey, levelTouches, filteredDates, granularity, color, targetSession }: LevelCardProps) {
    const stats = useMemo(() => {
        let touched = 0;
        let total = 0;
        const touchTimes: string[] = [];

        // Helper to check if time is in range (handles crossing midnight)
        const isInRange = (timeStr: string, range: { start: string, end: string }) => {
            if (range.start === '00:00' && range.end === '23:59') return true;

            const time = parseInt(timeStr.replace(':', ''));
            const start = parseInt(range.start.replace(':', ''));
            const end = parseInt(range.end.replace(':', ''));

            // Debug first few calls
            if (Math.random() < 0.0001) {
                console.log(`Debug isInRange: Time=${timeStr} (${time}), Range=${range.start}-${range.end}, Start=${start}, End=${end}`);
            }

            if (start < end) {
                return time >= start && time < end;
            } else {
                // Crossing midnight (e.g., 18:00 - 02:00)
                return time >= start || time < end;
            }
        };

        const sessionRange = SESSION_RANGES[targetSession as keyof typeof SESSION_RANGES];

        const bucketHits = new Map<string, Set<string>>(); // Removed, using allBuckets and filteredHitDates

        // Generate all buckets for the full session range to ensure fixed X-Axis
        const allBuckets: string[] = [];

        // Define Start/End minutes for iteration
        let startMins = 0;
        let endMins = 24 * 60; // 1440

        if (targetSession !== 'All') {
            const [sh, sm] = sessionRange.start.split(':').map(Number);
            const [eh, em] = sessionRange.end.split(':').map(Number);

            startMins = sh * 60 + sm;
            endMins = eh * 60 + em;
            // Handle midnight crossing? e.g. 18:00-02:00
            if (endMins < startMins) endMins += 24 * 60;
        }

        // Populate all buckets
        for (let m = startMins; m < endMins; m += granularity) {
            // Normalized time for bucket name map key (00:00 - 23:59)
            const normM = m % (24 * 60);
            const h = Math.floor(normM / 60);
            const min = normM % 60;
            const bucketKey = `${h.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;
            allBuckets.push(bucketKey);
        }

        const filteredHitDates = new Map<string, Set<string>>(); // bucket -> Set of dates

        filteredDates.forEach(date => {
            const dayData = levelTouches[date];
            if (!dayData) return;

            const levelData = dayData[levelKey as keyof typeof dayData] as LevelTouchEntry | undefined;
            if (!levelData) return;

            total++;

            if (levelData.touched && levelData.touch_times && levelData.touch_times.length > 0) {
                // Filter hits relevant to this session
                const validHits = levelData.touch_times.filter(t => isInRange(t, sessionRange));

                if (validHits.length > 0) {
                    touched++;

                    // Sort to ensure we get the earliest hit in the session
                    validHits.sort();

                    // ONLY use the first hit for the histogram distribution
                    const firstHit = validHits[0];

                    const [h, m] = firstHit.split(':').map(Number);
                    const mins = h * 60 + m;
                    const bucketMins = Math.floor(mins / granularity) * granularity;
                    const bucketH = Math.floor(bucketMins / 60);
                    const bucketM = bucketMins % 60;
                    const bucket = `${bucketH.toString().padStart(2, '0')}:${bucketM.toString().padStart(2, '0')}`;

                    if (!filteredHitDates.has(bucket)) {
                        filteredHitDates.set(bucket, new Set());
                    }
                    filteredHitDates.get(bucket)!.add(date);
                }
            }
        });

        const hitRate = total > 0 ? (touched / total) * 100 : 0;

        // Find mode bucket (bucket with most unique hit days)
        let mode = '-';
        let maxHits = 0;

        // Build histData from allBuckets (preserving X-Axis order)
        const histData = allBuckets.map(time => {
            const dates = filteredHitDates.get(time);
            const count = dates ? dates.size : 0;

            if (count > maxHits) {
                maxHits = count;
                mode = time;
            }
            const pct = total > 0 ? (count / total) * 100 : 0;
            return { time, count, pct };
        });

        // Calculate Median
        let median = '-';
        let cumulativeHits = 0;
        const halfTotal = touched / 2;

        for (const bin of histData) {
            cumulativeHits += bin.count;
            if (cumulativeHits >= halfTotal) {
                median = bin.time;
                break;
            }
        }

        return { hitRate, mode, median, total, touched, histData };
    }, [levelTouches, filteredDates, levelKey, granularity, targetSession]); // Add targetSession to dependency array

    return (
        <Card>
            <CardHeader className="pb-2 pt-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium">{title}</CardTitle>
                    <div className="flex items-center gap-2">
                        <div className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
                        <Badge variant="outline" className="text-lg font-bold border-muted-foreground/20 text-foreground">
                            {stats.hitRate.toFixed(1)}%
                        </Badge>
                    </div>
                </div>
                <div className="text-xs text-muted-foreground">
                    Mode: <span className="font-mono font-semibold">{stats.mode}</span> •
                    Median: <span className="font-mono font-semibold">{stats.median}</span> •
                    {stats.touched}/{stats.total} days
                    {targetSession !== 'All' && <span className="ml-1 text-[10px] opacity-70">({targetSession})</span>}
                </div>
            </CardHeader>
            <CardContent className="h-[150px] pt-0"> {/* Increased height for Brush */}
                {stats.histData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={stats.histData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                            <XAxis
                                dataKey="time"
                                fontSize={10}
                                tickMargin={5}
                                minTickGap={30}
                                height={30}
                            />
                            <YAxis hide />
                            <Tooltip
                                cursor={{ fill: 'var(--muted)', fillOpacity: 0.2 }}
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        const labelStr = String(label);
                                        const [h, m] = labelStr.split(':').map(Number);
                                        const startMins = h * 60 + m;
                                        const endMins = startMins + granularity;
                                        const endH = Math.floor(endMins / 60) % 24;
                                        const endM = endMins % 60;
                                        const endTime = `${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`;

                                        return (

                                            <div className="bg-background border border-border shadow-xl rounded-md text-xs p-3 min-w-[140px]">
                                                {/* Header: Level Name */}
                                                <div className="font-bold text-base mb-1 flex items-center gap-2 text-foreground border-b border-border pb-2">
                                                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                                                    {title}
                                                </div>

                                                {/* Time Range */}
                                                <div className="mt-2 text-muted-foreground font-medium text-[10px] uppercase tracking-wider">
                                                    Eastern Time
                                                </div>
                                                <div className="text-foreground font-mono text-sm mb-2">
                                                    {label} - {endTime}
                                                </div>

                                                {/* Stats */}
                                                <div className="pt-2 border-t border-border flex items-center justify-between text-sm">
                                                    <span className="font-bold text-foreground">
                                                        {Number(data.pct).toFixed(2)}%
                                                    </span>
                                                    <span className="text-muted-foreground text-xs">
                                                        {data.count} hits
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="pct" fill={color} radius={[2, 2, 0, 0]} activeBar={{ fill: color, opacity: 0.8 }} />
                            <ReferenceLine x={stats.median} stroke="white" strokeDasharray="3 3" />
                            <Brush dataKey="time" height={20} stroke={color} opacity={0.5} tickFormatter={() => ''} />
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

// Export optimized component
export const DailyLevels = memo(function DailyLevels({ levelTouches, filteredDates, limitLevels }: DailyLevelsProps) {
    const [granularity, setGranularity] = useState<number>(15);
    const [targetSession, setTargetSession] = useState<string>('Daily');

    if (!levelTouches || filteredDates.size === 0) {
        return <div className="text-muted-foreground text-center py-8">Loading level data...</div>;
    }

    const shouldShow = (key: string) => !limitLevels || limitLevels.includes(key);

    return (
        <div className="space-y-6">
            {/* Controls Row */}
            <div className="flex justify-end items-center gap-4">
                {/* Session Selector */}
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Target Session:</span>
                    <Select
                        value={targetSession}
                        onValueChange={setTargetSession}
                    >
                        <SelectTrigger className="h-8 w-[160px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="Daily">Daily (18:00-17:00)</SelectItem>
                            <SelectItem value="P12">P12 (06:00-17:00)</SelectItem>
                            <SelectItem value="Asia">Asia (18:00-02:00)</SelectItem>
                            <SelectItem value="London">London (02:00-07:00)</SelectItem>
                            <SelectItem value="NY1">NY1 (08:00-12:00)</SelectItem>
                            <SelectItem value="NY2">NY2 (12:00-16:00)</SelectItem>
                        </SelectContent>
                    </Select >
                </div >

                {/* Granularity selector */}
                < div className="flex items-center gap-2" >
                    <span className="text-sm text-muted-foreground">Granularity:</span>
                    <Select
                        value={granularity.toString()}
                        onValueChange={(v) => setGranularity(Number(v))}
                    >
                        <SelectTrigger className="h-8 w-20">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="1">1min</SelectItem>
                            <SelectItem value="5">5min</SelectItem>
                            <SelectItem value="15">15min</SelectItem>
                            <SelectItem value="30">30min</SelectItem>
                            <SelectItem value="60">1hr</SelectItem>
                        </SelectContent>
                    </Select>
                </div >
            </div >

            {/* Previous Day Levels */}
            {
                (shouldShow('pdl') || shouldShow('pdm') || shouldShow('pdh')) && (
                    <div>
                        <h3 className="text-lg font-semibold mb-3">Previous Day Levels</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {shouldShow('pdl') && <LevelCard title="Previous Day Low" levelKey="pdl" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#ef4444" targetSession={targetSession} />}
                            {shouldShow('pdm') && <LevelCard title="Previous Day Mid" levelKey="pdm" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#f59e0b" targetSession={targetSession} />}
                            {shouldShow('pdh') && <LevelCard title="Previous Day High" levelKey="pdh" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#22c55e" targetSession={targetSession} />}
                        </div>
                    </div>
                )
            }

            {/* P12 Levels */}
            {
                (shouldShow('p12h') || shouldShow('p12m') || shouldShow('p12l')) && (
                    <div>
                        <h3 className="text-lg font-semibold mb-3">P12 Levels (Overnight)</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {shouldShow('p12h') && <LevelCard title="P12 High" levelKey="p12h" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#22c55e" targetSession={targetSession} />}
                            {shouldShow('p12m') && <LevelCard title="P12 Mid" levelKey="p12m" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#06b6d4" targetSession={targetSession} />}
                            {shouldShow('p12l') && <LevelCard title="P12 Low" levelKey="p12l" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#ef4444" targetSession={targetSession} />}
                        </div>
                    </div>
                )
            }

            {/* Time-Based Opens */}
            {
                (shouldShow('daily_open') || shouldShow('midnight_open') || shouldShow('open_0730')) && (
                    <div>
                        <h3 className="text-lg font-semibold mb-3">Time-Based Opens</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {shouldShow('daily_open') && <LevelCard title="Daily Open (18:00)" levelKey="daily_open" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#8b5cf6" targetSession={targetSession} />}
                            {shouldShow('midnight_open') && <LevelCard title="Midnight Open (00:00)" levelKey="midnight_open" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#a855f7" targetSession={targetSession} />}
                            {shouldShow('open_0730') && <LevelCard title="07:30 Open" levelKey="open_0730" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#c084fc" targetSession={targetSession} />}
                        </div>
                    </div>
                )
            }

            {/* Session Mids */}
            {
                (shouldShow('asia_mid') || shouldShow('london_mid') || shouldShow('ny1_mid') || shouldShow('ny2_mid')) && (
                    <div>
                        <h3 className="text-lg font-semibold mb-3">Session Mids</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {shouldShow('asia_mid') && <LevelCard title="Asia Mid" levelKey="asia_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#f472b6" targetSession={targetSession} />}
                            {shouldShow('london_mid') && <LevelCard title="London Mid" levelKey="london_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#fb923c" targetSession={targetSession} />}
                            {shouldShow('ny1_mid') && <LevelCard title="NY1 Mid" levelKey="ny1_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#38bdf8" targetSession={targetSession} />}
                        </div>
                    </div>
                )
            }
        </div >
    );
});
