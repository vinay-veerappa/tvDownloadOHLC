"use client"

import { useMemo, memo, useState } from 'react';
import useSWR from 'swr';
import { fetchFilteredPriceModel, fetchLevelStats, FilterPayload, PriceModelResponse, LevelContextData, AllLevelStats } from '@/lib/api/profiler';
import { Card, CardContent } from '@/components/ui/card';
import { ChartHeaderInfo } from './chart-header-info';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ReferenceArea,
    Brush
} from 'recharts';
import { Loader2, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface PriceModelChartProps {
    ticker: string;
    session: string; // 'Asia', 'London', 'NY1', 'NY2', or 'Daily'
    // Filter parameters for server-side filtering
    targetSession: string;
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
    height?: number;
}

// Export optimized component
export const PriceModelChart = memo(function PriceModelChart({
    ticker,
    session,
    targetSession,
    filters,
    brokenFilters,
    intraState,
    height = 300
}: PriceModelChartProps) {
    // State for aggregation interval
    const [bucketMinutes, setBucketMinutes] = useState<number>(5);

    const [hoverData, setHoverData] = useState<{
        time: string;
        high: number;
        low: number;
    } | null>(null);

    const [isExpanded, setIsExpanded] = useState(false);

    // Create stable cache key from filter params
    const cacheKey = JSON.stringify({
        type: 'price-model',
        ticker,
        session,
        targetSession,
        filters,
        brokenFilters,
        intraState,
        bucketMinutes
    });

    // Use SWR for caching and deduplication
    const { data, isLoading: loading } = useSWR<PriceModelResponse>(
        cacheKey,
        async () => {
            const payload: FilterPayload = {
                ticker,
                target_session: session,  // Price model session (e.g. "Daily")
                filters,
                broken_filters: brokenFilters,
                intra_state: intraState,
                bucket_minutes: bucketMinutes
            };
            return fetchFilteredPriceModel(payload);
        },
        {
            revalidateOnFocus: false,
            dedupingInterval: 1000,
        }
    );

    const chartData = useMemo(() => {
        if (!data || !data.median) return [];
        return data.median.map(d => ({
            ...d,
            // Format time for X-axis display if needed? 
            // Or use time_idx as minutes
        }));
    }, [data]);

    // Format time for display (using backend 'time' string if available)
    const formatXAxis = (tickItem: any, index: number) => {
        // tickItem is the value of time_idx (e.g., 0, 5, 10...)
        const val = Number(tickItem);

        // 1. Try to find the exact data point matching this time_idx
        // SKIP `match.time` for Daily session to force strict 18:00 alignment
        const match = chartData.find(d => d.time_idx === val);
        if (session !== 'Daily' && match && match.time) {
            return match.time;
        }

        // 2. Fallback to strict calculation based on session start
        let startHour = 18;
        let startMin = 0;

        if (session === 'London') { startHour = 2; startMin = 30; }
        if (session === 'NY1') { startHour = 7; startMin = 30; } // NY1 starts 07:30
        if (session === 'NY2') { startHour = 11; startMin = 30; } // NY2 starts 11:30
        if (session === 'P12') { startHour = 6; startMin = 0; }
        if (session === 'Daily') { startHour = 18; startMin = 0; }

        // Correct: val is already minutes (time_idx from backend is raw minutes offset)
        const totalMinutes = startHour * 60 + startMin + val;

        const normalizedMinutes = totalMinutes % (24 * 60);
        const h = Math.floor(normalizedMinutes / 60);
        const m = normalizedMinutes % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    };

    // Calculate ticks for XAxis based on duration
    const xAxisTicks = useMemo(() => {
        if (chartData.length === 0) return undefined;

        const lastIdx = chartData[chartData.length - 1].time_idx;
        const generatedTicks: number[] = [];

        // Determine interval based on total duration
        let interval = 60; // Default: Hourly for long sessions (Daily)

        if (lastIdx <= 180) { // <= 3 hours
            interval = 15; // 15 mins
        } else if (lastIdx <= 360) { // <= 6 hours
            interval = 30; // 30 mins
        }

        // Ensure we cover the full range
        for (let i = 0; i <= lastIdx; i += interval) {
            generatedTicks.push(i);
        }

        return generatedTicks;
    }, [chartData]);

    // Prepare Header Items
    const headerItems = useMemo(() => {
        if (!hoverData) return [];
        return [

            { label: 'Time', value: hoverData.time }
            // User requested to remove High/Low values
        ];
    }, [hoverData]);

    const handleMouseMove = (state: any) => {
        if (state && state.activePayload && state.activePayload.length > 0) {
            const payload = state.activePayload[0].payload;
            // payload.time might be undefined if not in data, recalculate if needed
            const timeDisplay = (session === 'Daily' || !payload.time)
                ? formatXAxis(payload.time_idx, 0)
                : payload.time;

            setHoverData({
                time: timeDisplay,
                high: payload.high,
                low: payload.low
            });
        }
    };

    const handleMouseLeave = () => {
        setHoverData(null);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center border rounded-md" style={{ height }}>
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!data || chartData.length === 0) {
        return (
            <div className="flex items-center justify-center border rounded-md text-muted-foreground text-sm" style={{ height }}>
                No active data for this selection.
            </div>
        );
    }

    // Extracted Chart Content for reuse in Dialog
    const ChartContent = () => (
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
            <LineChart
                data={chartData}
                margin={{ top: 10, right: 10, bottom: 0, left: 10 }}
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
            >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis
                    dataKey="time_idx"
                    tickFormatter={formatXAxis}
                    tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                    axisLine={false}
                    tickLine={false}
                    ticks={xAxisTicks}
                    interval={0} // Force show all calculated ticks
                    type="number"
                    domain={[0, 'auto']} // Force start at 0 to ensure shading is visible
                />
                <YAxis
                    tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                    axisLine={false}
                    tickLine={false}
                    domain={['auto', 'auto']}
                    tickFormatter={(val) => `${val.toFixed(2)}%`}
                    width={50}
                />
                {/* Grey line at 0 */}
                <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="3 3" />

                {/* Tooltip hidden via opacity to ensure events fire but no popover */}
                <Tooltip
                    wrapperStyle={{ opacity: 0 }}
                    cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1, strokeDasharray: '4 4' }}
                />

                {/* Session Shading (Opening Range / Classification Window) */}
                {(() => {
                    let shadeEnd = 0;
                    if (session === 'Asia') shadeEnd = 90; // 18:00 - 19:30
                    else if (session === 'London') shadeEnd = 60; // 02:30 - 03:30
                    else if (session === 'NY1') shadeEnd = 60; // 07:30 - 08:30
                    else if (session === 'NY2') shadeEnd = 60; // 11:30 - 12:30

                    if (shadeEnd > 0) {
                        return (
                            <ReferenceArea
                                x1={0}
                                x2={shadeEnd}
                                fill="#888888"
                                fillOpacity={0.2}
                                ifOverflow="extendDomain"
                            />
                        );
                    }
                    return null;
                })()}

                <Line
                    type="monotone"
                    dataKey="high"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false} // Disable animation for performance
                />
                <Line
                    type="monotone"
                    dataKey="low"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                />
                <Brush
                    dataKey="time_idx"
                    height={30}
                    stroke="#8884d8"
                    tickFormatter={formatXAxis}
                    travellerWidth={10}
                    alwaysShowText={false}
                />
            </LineChart>
        </ResponsiveContainer>
    );

    return (
        <>
            <Card className="border border-border/50 shadow-none">
                <CardContent className="p-0">
                    <div className="pt-2 px-4 flex justify-between items-start">
                        <ChartHeaderInfo
                            title=""
                            subtitle={hoverData ? '' : `${data.count} Sessions`}
                            items={headerItems}
                        />

                        {/* Tools: Interval + Expand */}
                        <div className="flex items-center space-x-2 ml-auto">
                            <div className="flex space-x-1 bg-secondary/30 rounded p-1">
                                {[1, 5, 15].map((mins) => (
                                    <button
                                        key={mins}
                                        onClick={() => setBucketMinutes(mins)}
                                        className={`text-xs px-2 py-0.5 rounded transition-colors ${bucketMinutes === mins
                                            ? 'bg-primary text-primary-foreground'
                                            : 'hover:bg-muted text-muted-foreground'
                                            }`}
                                    >
                                        {mins}m
                                    </button>
                                ))}
                            </div>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setIsExpanded(true)}>
                                <Maximize2 className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                    <div style={{ height: height - 40, width: '100%', minWidth: 0, minHeight: 0 }}>
                        <ChartContent />
                    </div>
                </CardContent>
            </Card>

            <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
                <DialogContent className="max-w-[90vw] w-[90vw] h-[85vh] flex flex-col sm:max-w-[90vw]">
                    <DialogHeader>
                        <DialogTitle>{session} Price Model ({bucketMinutes}m)</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 w-full min-h-0 mt-4">
                        <div style={{ height: '100%', width: '100%' }}>
                            <ChartContent />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
});
