"use client"

import { useMemo, useState, useEffect } from 'react';
import { ProfilerSession, DailyHodLodResponse } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChartTooltipFrame, ChartTooltipHeader, ChartTooltipRow } from '@/components/ui/chart-tooltip';
import {
    ResponsiveContainer,
    ComposedChart,
    Line,
    Area,
    XAxis,
    YAxis,
    Tooltip,
    ReferenceLine,
    Bar,
    Legend,

    CartesianGrid,
    ReferenceArea
} from 'recharts';

const SESSION_CONFIG: Record<string, { start: string; duration: number }> = {
    "NY1": { start: "07:30", duration: 60 },
    "NY2": { start: "11:30", duration: 60 },
    "London": { start: "02:30", duration: 60 },
    "Asia": { start: "18:00", duration: 90 },
    "Open730": { start: "07:30", duration: 60 },
    "MidnightOpen": { start: "00:00", duration: 60 },
};
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { fetchFilteredPriceModel, PriceModelResponse } from '@/lib/api/profiler';

interface OutcomePanelProps {
    outcomeName: string;  // e.g., "Short True"
    sessions: ProfilerSession[];
    outcomeDates?: Set<string>;
    totalInCategory: number;
    targetSession: string;
    dailyHodLod?: DailyHodLodResponse | null;
    ticker: string; // [NEW] Needed for API calls
}

// ... existing helper functions (lines 28-63) ... [RETAIN UNCHANGED]

export function OutcomePanel({ outcomeName, sessions, outcomeDates, totalInCategory, targetSession, dailyHodLod, ticker }: OutcomePanelProps) {
    const [granularity, setGranularity] = useState<number>(15);
    const [priceModel, setPriceModel] = useState<PriceModelResponse | null>(null);
    const [loadingModel, setLoadingModel] = useState(false);

    // Fetch Price Model Aggregates - TEMPORARILY DISABLED
    // Fetch Price Model Aggregates (Restored using Filter API)
    useEffect(() => {
        if (ticker && targetSession && outcomeName) {
            setLoadingModel(true);

            // Construct payload for specific outcome
            // Filter: Target Session Status == Outcome Name
            const payload = {
                ticker,
                target_session: targetSession,
                filters: { [targetSession]: outcomeName },
                broken_filters: {},
                intra_state: "Any",
                bucket_minutes: 5 // Default for small charts
            };

            fetchFilteredPriceModel(payload)
                .then(data => setPriceModel(data))
                .catch(err => console.error("Failed to fetch price model", err))
                .finally(() => setLoadingModel(false));
        }
    }, [ticker, targetSession, outcomeName]);

    const { uniqueDays, probability, timeHistogramData, referenceLevelStats, hodStats, lodStats, highRangeStats, lowRangeStats, highDistData, lowDistData } = useMemo(() => {
        const unique = outcomeDates ? outcomeDates.size : new Set(sessions.map(s => s.date)).size;
        const prob = totalInCategory > 0 ? ((unique / totalInCategory) * 100).toFixed(1) : "0.0";

        // 1. Price Range Data (HOD/LOD) percent from open
        // Using high_pct/low_pct if available in session, else calc
        const hods = sessions.map(s => s.high_pct ? s.high_pct : 0); // Assuming backend provides high_pct
        const lods = sessions.map(s => s.low_pct ? s.low_pct : 0);

        // Helper to bin data
        const binData = (data: number[], binSize: number) => {
            if (data.length === 0) return { data: [], mode: 0 };
            const min = Math.floor(Math.min(...data) / binSize) * binSize;
            const max = Math.ceil(Math.max(...data) / binSize) * binSize;
            const bins = new Map<number, number>();
            let maxCount = 0;
            let modeBin = min;

            for (let v of data) {
                const b = Math.floor(v / binSize) * binSize;
                const newCount = (bins.get(b) || 0) + 1;
                bins.set(b, newCount);
                if (newCount > maxCount) { maxCount = newCount; modeBin = b; }
            }

            const result = [];
            const total = data.length;
            for (let b = min; b <= max; b += binSize) {
                const c = bins.get(b) || 0;
                // Use Key 'pct' for XAxis match in Line 256/300
                result.push({ pct: b, count: c, percent: (c / total) * 100 });
            }
            return { data: result, mode: modeBin };
        };

        const calcMedian = (arr: number[]) => {
            if (arr.length === 0) return 0;
            const sorted = [...arr].sort((a, b) => a - b);
            const mid = Math.floor(sorted.length / 2);
            return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
        }

        const hStats = binData(hods, 0.2); // 0.2% bins
        const lStats = binData(lods, 0.2);

        // 2. Time Distribution Data
        // Parse "HH:MM"
        const parseTime = (t: string | null) => t ? parseInt(t.split(':')[0]) * 60 + parseInt(t.split(':')[1]) : null;
        // Check property existence or use split on non-null
        // Since backend data guarantees type string|null, access safely
        const hodTimes = sessions.filter(s => s.high_time).map(s => {
            const parts = s.high_time!.split(':');
            return parseInt(parts[0]) * 60 + parseInt(parts[1]);
        });
        const lodTimes = sessions.filter(s => s.low_time).map(s => {
            const parts = s.low_time!.split(':');
            return parseInt(parts[0]) * 60 + parseInt(parts[1]);
        });

        // Group into buckets (e.g. 30 mins)
        const timeBuckets = new Map<string, { time: string, hod: number, lod: number }>();
        const processTime = (times: number[], type: 'hod' | 'lod') => {
            times.forEach(t => {
                const bucketStart = Math.floor(t / 30) * 30; // 30 min buckets
                const h = Math.floor(bucketStart / 60);
                const m = bucketStart % 60;
                const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;

                if (!timeBuckets.has(timeStr)) {
                    timeBuckets.set(timeStr, { time: timeStr, hod: 0, lod: 0 });
                }
                const b = timeBuckets.get(timeStr)!;
                if (type === 'hod') b.hod++;
                else b.lod++;
            });
        };
        processTime(hodTimes, 'hod');
        processTime(lodTimes, 'lod');

        const timeHistData = Array.from(timeBuckets.values()).sort((a, b) => a.time.localeCompare(b.time));

        // Find Time Modes
        const getModeTime = (data: typeof timeHistData, key: 'hod' | 'lod') => {
            if (!data.length) return "N/A";
            const max = data.reduce((prev, current) => (prev[key] > current[key]) ? prev : current);
            return max[key] > 0 ? max.time : "N/A";
        };

        // 3. Reference Levels
        const refStats = [
            { name: "PDH Broken", rate: "0.0" },
            { name: "PDL Broken", rate: "0.0" }
        ];

        const avgHod = hods.length ? (hods.reduce((a, b) => a + b, 0) / hods.length).toFixed(2) : "0.00";
        const avgLod = lods.length ? (lods.reduce((a, b) => a + b, 0) / lods.length).toFixed(2) : "0.00";

        return {
            uniqueDays: unique,
            probability: prob,
            timeHistogramData: timeHistData,
            referenceLevelStats: refStats,
            hodStats: { avg: avgHod, mode: getModeTime(timeHistData, 'hod') },
            lodStats: { avg: avgLod, mode: getModeTime(timeHistData, 'lod') },
            highRangeStats: { count: hods.length, mode: hStats.mode, median: calcMedian(hods) },
            lowRangeStats: { count: lods.length, mode: lStats.mode, median: calcMedian(lods) },
            highDistData: hStats.data,
            lowDistData: lStats.data
        };
    }, [sessions, outcomeDates, totalInCategory]);

    // Helper for Price Model Charts
    const renderPriceModelChart = (data: any[], title: string, color: string, dataKeyH: string, dataKeyL: string) => {
        const sessionName = targetSession || "NY1";
        const config = SESSION_CONFIG[sessionName] || { start: "09:30", duration: 60 };

        const formatTimeTick = (minutes: number) => {
            const [h, m] = config.start.split(':').map(Number);
            const date = new Date();
            date.setHours(h, m + minutes, 0, 0);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        };

        const ticks = Array.from({ length: 15 }, (_, i) => i * 60);

        return (
            <div className="border rounded-lg p-3">
                <h5 className="text-xs font-semibold mb-2 flex items-center gap-1">
                    <Activity className="h-3 w-3" /> {title}
                </h5>
                <div className="h-40">
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#444" opacity={0.3} />
                            {/* Shade the Session Duration */}
                            <ReferenceArea x1={0} x2={config.duration} fill="currentColor" fillOpacity={0.05} />

                            <XAxis
                                dataKey="time_idx"
                                fontSize={9}
                                tickFormatter={formatTimeTick}
                                ticks={ticks}
                                type="number"
                                domain={[0, 'dataMax']}
                                tick={{ fill: '#888888' }}
                                axisLine={{ stroke: '#444' }}
                            />
                            <YAxis
                                fontSize={9}
                                tickFormatter={(v) => `${v.toFixed(1)}%`}
                                domain={['auto', 'auto']}
                                tick={{ fill: '#888888' }}
                                width={35}
                                axisLine={{ stroke: '#444' }}
                            />
                            <Tooltip
                                cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload || !payload.length) return null;
                                    return (
                                        <ChartTooltipFrame>
                                            <ChartTooltipHeader>{formatTimeTick(label as number)} (+{label}m)</ChartTooltipHeader>
                                            {payload.map((entry: any, index: number) => (
                                                <ChartTooltipRow
                                                    key={index}
                                                    label="Probability"
                                                    value={`${Number(entry.value).toFixed(2)}%`}
                                                    indicatorColor={entry.stroke}
                                                />
                                            ))}
                                        </ChartTooltipFrame>
                                    );
                                }}
                            />
                            <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeWidth={0.5} strokeDasharray="3 3" />
                            <Area
                                type="monotone"
                                dataKey={dataKeyH}
                                stroke={color}
                                fill={color}
                                fillOpacity={0.1}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4, strokeWidth: 0 }}
                                name="High"
                            />
                            <Area
                                type="monotone"
                                dataKey={dataKeyL}
                                stroke={color}
                                fill={color}
                                fillOpacity={0.1}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4, strokeWidth: 0 }}
                                name="Low"
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>
        );
    };

    return (
        <Card className="border-2">
            {/* ... Header ... */}
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
                    {/* ... (Existing HOD/LOD content) ... */}
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
                                    cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                                    content={({ active, payload, label }) => {
                                        if (!active || !payload || !payload.length) return null;
                                        return (
                                            <ChartTooltipFrame>
                                                <ChartTooltipHeader>{label}</ChartTooltipHeader>
                                                {payload.map((entry: any, index: number) => (
                                                    <ChartTooltipRow
                                                        key={index}
                                                        label={entry.name === 'hod' ? 'HOD' : 'LOD'}
                                                        value={`${Math.abs(Number(entry.value)).toFixed(1)}%`}
                                                        indicatorColor={entry.fill}
                                                    />
                                                ))}
                                            </ChartTooltipFrame>
                                        );
                                    }}
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
                                            cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                                            content={({ active, payload, label }) => {
                                                if (!active || !payload || !payload.length) return null;
                                                return (
                                                    <ChartTooltipFrame>
                                                        <ChartTooltipHeader>High: +{label}%</ChartTooltipHeader>
                                                        {payload.map((entry: any, index: number) => (
                                                            <ChartTooltipRow
                                                                key={index}
                                                                label="Frequency"
                                                                value={`${Number(entry.value).toFixed(1)}%`}
                                                                indicatorColor={entry.fill}
                                                            />
                                                        ))}
                                                    </ChartTooltipFrame>
                                                );
                                            }}
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
                                            cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                                            content={({ active, payload, label }) => {
                                                if (!active || !payload || !payload.length) return null;
                                                return (
                                                    <ChartTooltipFrame>
                                                        <ChartTooltipHeader>Low: {label}%</ChartTooltipHeader>
                                                        {payload.map((entry: any, index: number) => (
                                                            <ChartTooltipRow
                                                                key={index}
                                                                label="Frequency"
                                                                value={`${Number(entry.value).toFixed(1)}%`}
                                                                indicatorColor={entry.fill}
                                                            />
                                                        ))}
                                                    </ChartTooltipFrame>
                                                );
                                            }}
                                        />
                                        <ReferenceLine x={lowRangeStats.median} stroke="#ef4444" strokeDasharray="3 3" />
                                        <Bar dataKey="percent" fill="#ef4444" radius={[2, 2, 0, 0]} opacity={0.8} />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Price Model Analysis [NEW] */}
                <div>
                    <h4 className="text-sm font-medium mb-2">Price Model (Intraday Path)</h4>
                    {loadingModel ? (
                        <div className="text-xs text-muted-foreground p-4">Loading model...</div>
                    ) : priceModel && priceModel.count > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {renderPriceModelChart(priceModel.median, "Median Path", "#3b82f6", "high", "low")}
                        </div>
                    ) : (
                        <div className="text-xs text-muted-foreground p-4">No model data available</div>
                    )}
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
