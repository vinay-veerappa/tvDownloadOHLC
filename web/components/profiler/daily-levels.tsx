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
import { ChartTooltipFrame, ChartTooltipHeader, ChartTooltipRow } from '@/components/ui/chart-tooltip';
import { Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const SESSION_RANGES: Record<string, { start: string; end: string }> = {
    'Asia': { start: '18:00', end: '02:00' },
    'London': { start: '02:00', end: '07:00' },
    'NY1': { start: '08:00', end: '12:00' },
    'NY2': { start: '12:00', end: '16:00' },
    'P12': { start: '06:00', end: '17:00' },
    'Daily': { start: '18:00', end: '17:00' },
};

// Start times for specific levels to avoid empty space
const LEVEL_START_TIMES: Record<string, string> = {
    'p12h': '06:00', 'p12m': '06:00', 'p12l': '06:00',
    'midnight_open': '00:00',
    'open_0730': '07:30',
    'asia_mid': '02:00',   // Asia ends 02:00
    'london_mid': '07:00', // London ends 07:00
    'ny1_mid': '12:00',    // NY1 ends 12:00
    'ny2_mid': '16:00',    // NY2 ends 16:00
};

interface DailyLevelsProps {
    levelTouches: LevelTouchesResponse | null;
    filteredDates: Set<string>;
    limitLevels?: string[];
    initialSession?: string;
}

interface LevelCardProps {
    title: string;
    levelKey: string;
    levelTouches: LevelTouchesResponse;
    filteredDates: Set<string>;
    granularity: number;
    color: string;
    targetSession: string;
}

function timeToMinutes(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
}

function LevelCard({ title, levelKey, levelTouches, filteredDates, granularity, color, targetSession }: LevelCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const stats = useMemo(() => {
        let touched = 0;
        let total = 0;

        const sessionRange = SESSION_RANGES[targetSession as keyof typeof SESSION_RANGES];
        const [sessionStartH, sessionStartM] = sessionRange.start.split(':').map(Number);
        const [sessionEndH, sessionEndM] = sessionRange.end.split(':').map(Number);

        let startMins = sessionStartH * 60 + sessionStartM;
        let endMins = sessionEndH * 60 + sessionEndM;

        // Handle midnight crossing for session (e.g. 18:00 -> 17:00 next day, or 18:00 -> 02:00)
        // If end < start, it means it crosses midnight
        if (endMins < startMins) endMins += 24 * 60;

        // Apply Level specific start time constraint
        const specificStart = LEVEL_START_TIMES[levelKey];
        if (specificStart) {
            // Need to determine where this specific start falls relative to the session start
            // We assume the specific start is within the session duration (possibly next day)

            const [specH, specM] = specificStart.split(':').map(Number);
            let specMins = specH * 60 + specM;

            // Adjust specMins to be >= startMins
            // Case 1: Session starts 18:00, specific is 00:00. 18*60=1080. 00*60=0.
            // 0 < 1080. But we know 00:00 is "tomorrow". So add 24*60.
            // Case 2: Session starts 06:00, specific 07:00. 360 < 420. Correct.

            // Heuristic: if specific time < session start time, assume it's next day
            // UNLESS session crosses midnight and specific time is effectively "late" in day?
            // Actually simpler: 
            // 1. Normalize both to 0-1440.
            // 2. If session crosses midnight (start > end_nom), loop.

            // Robust way:
            // Calculate offset from session start.
            let offset = specMins - (sessionStartH * 60 + sessionStartM);
            if (offset < 0) offset += 24 * 60;

            // New effective start 
            const newStart = startMins + offset;

            // Only update if newStart is within [startMins, endMins]
            // and it is actually *later* than current start (which it always is by def)
            if (newStart < endMins) {
                startMins = newStart;
            }
        }

        // Generate all buckets for the ADJUSTED range
        const allBuckets: string[] = [];

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

            if (levelData.touched && levelData.hits) {
                // Optimized backend returns pre-calculated first hit per session
                const firstHit = levelData.hits[targetSession];

                if (firstHit) {
                    touched++;

                    const [h, m] = firstHit.split(':').map(Number);
                    const mins = h * 60 + m;

                    // We need to map this hit (HH:MM) to our linear minute timeline [startMins, endMins]
                    // Calculate offset from session start
                    let offset = mins - (sessionStartH * 60 + sessionStartM);
                    if (offset < 0) offset += 24 * 60;

                    const absMins = (sessionStartH * 60 + sessionStartM) + offset;

                    // Only count if within our potentially shortened window
                    if (absMins >= startMins && absMins < endMins) {
                        // Bucket logic
                        const bucketMins = Math.floor(absMins / granularity) * granularity;
                        // Convert back to HH:MM for map key
                        const bucketH = Math.floor((bucketMins % (24 * 60)) / 60);
                        const bucketM = bucketMins % 60;
                        const bucket = `${bucketH.toString().padStart(2, '0')}:${bucketM.toString().padStart(2, '0')}`;

                        if (!filteredHitDates.has(bucket)) {
                            filteredHitDates.set(bucket, new Set());
                        }
                        filteredHitDates.get(bucket)!.add(date);
                    }
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
    }, [levelTouches, filteredDates, levelKey, granularity, targetSession]);

    const ChartContent = () => (
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

                                <ChartTooltipFrame>
                                    {/* Header: Level Name */}
                                    <ChartTooltipHeader color={color}>
                                        {title}
                                    </ChartTooltipHeader>

                                    {/* Time Range */}
                                    <div className="mt-2 text-muted-foreground font-medium text-[10px] uppercase tracking-wider">
                                        Eastern Time
                                    </div>
                                    <div className="text-foreground font-mono text-sm mb-2">
                                        {label} - {endTime}
                                    </div>

                                    {/* Stats */}
                                    <div className="pt-2 border-t border-border">
                                        <ChartTooltipRow
                                            label="Probability"
                                            value={`${Number(data.pct).toFixed(2)}%`}
                                            subValue={`${data.count} hits`}
                                        />
                                    </div>
                                </ChartTooltipFrame>
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
    );

    return (
        <>
            <Card>
                <CardHeader className="pb-2 pt-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">{title}</CardTitle>
                        <div className="flex items-center gap-2">
                            <div className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
                            <Badge variant="outline" className="text-lg font-bold border-muted-foreground/20 text-foreground">
                                {stats.hitRate.toFixed(1)}%
                            </Badge>
                            <Button variant="ghost" size="icon" className="h-5 w-5 ml-1" onClick={() => setIsExpanded(true)}>
                                <Maximize2 className="h-3 w-3" />
                            </Button>
                        </div>
                    </div>
                    <div className="text-xs text-muted-foreground">
                        Mode: <span className="font-mono font-semibold">{stats.mode}</span> •
                        Median: <span className="font-mono font-semibold">{stats.median}</span> •
                        {stats.touched}/{stats.total} days
                        {targetSession !== 'All' && <span className="ml-1 text-[10px] opacity-70">({targetSession})</span>}
                    </div>
                </CardHeader>
                <CardContent className="h-[150px] pt-0">
                    {stats.histData.length > 0 ? (
                        <ChartContent />
                    ) : (
                        <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                            No touch data
                        </div>
                    )}
                </CardContent>
            </Card>

            <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
                <DialogContent className="max-w-[90vw] w-[90vw] h-[85vh] flex flex-col sm:max-w-[90vw]">
                    <DialogHeader>
                        <DialogTitle>{title} - Touch Probability ({granularity}m)</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 w-full min-h-0 mt-4">
                        {stats.histData.length > 0 ? (
                            <ChartContent />
                        ) : (
                            <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                                No touch data
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}

// Export optimized component
export const DailyLevels = memo(function DailyLevels({ levelTouches, filteredDates, limitLevels, initialSession = 'Daily' }: DailyLevelsProps) {
    const [granularity, setGranularity] = useState<number>(15);
    const [targetSession, setTargetSession] = useState<string>(initialSession);

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
                            {shouldShow('ny2_mid') && <LevelCard title="NY2 Mid" levelKey="ny2_mid" levelTouches={levelTouches} filteredDates={filteredDates} granularity={granularity} color="#60a5fa" targetSession={targetSession} />}
                        </div>
                    </div>
                )
            }
        </div >
    );
});
