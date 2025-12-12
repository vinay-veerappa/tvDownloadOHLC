"use client"

import { useMemo, memo } from 'react';
import useSWR from 'swr';
import { fetchFilteredPriceModel, FilterPayload, PriceModelResponse, PriceModelEntry } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
    Brush
} from 'recharts';
import { Loader2 } from 'lucide-react';
import { useState } from 'react';

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

    // Header Info State (Hover)
    const [hoverData, setHoverData] = useState<{
        time: string;
        high: number;
        low: number;
    } | null>(null);

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
        const match = chartData.find(d => d.time_idx === val);
        if (match && match.time) {
            return match.time;
        }

        // 2. Fallback to calculation
        let startHour = 18;
        let startMin = 0;
        if (session === 'London') startHour = 3; // London starts 02:30 or 03:00? Backend says 02:30.
        // Let's use backend strings primarily to avoid this guessing game.

        if (session === 'London') { startHour = 2; startMin = 30; }
        if (session === 'NY1') { startHour = 7; startMin = 30; }
        if (session === 'NY2') { startHour = 11; startMin = 30; }
        if (session === 'Daily') { startHour = 18; startMin = 0; }

        const totalMinutes = startHour * 60 + startMin + val;
        const h = Math.floor(totalMinutes / 60) % 24;
        const m = totalMinutes % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    };

    // Prepare Header Items
    const headerItems = useMemo(() => {
        if (!hoverData) return [];
        return [
            { label: 'Time', value: hoverData.time },
            { label: 'Med High', value: hoverData.high.toFixed(2) + '%', color: '#10b981' }, // Green
            { label: 'Med Low', value: hoverData.low.toFixed(2) + '%', color: '#ef4444' }   // Red
        ];
    }, [hoverData]);

    const handleMouseMove = (state: any) => {
        if (state && state.activePayload && state.activePayload.length > 0) {
            const payload = state.activePayload[0].payload;
            setHoverData({
                time: payload.time || formatXAxis(payload.time_idx, 0), // Use payload.time directly
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

    return (
        <Card className="border border-border/50 shadow-none">
            <CardContent className="p-0">
                <div className="pt-2 px-4 flex justify-between items-start">
                    <ChartHeaderInfo
                        title={`${session} Price Model (Median)`}
                        subtitle={`${data.count} Sessions`}
                        items={headerItems.length > 0 ? headerItems : [
                            { label: 'Hover chart for details', value: '' }
                        ]}
                    />

                    {/* Interval Selector */}
                    <div className="flex space-x-1 bg-secondary/30 rounded p-1 ml-auto">
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
                </div>
                <div style={{ height: height - 40, width: '100%', minWidth: 0, minHeight: 0 }}>
                    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                        <LineChart
                            data={chartData}
                            margin={{ top: 10, right: 10, bottom: 0, left: 10 }}
                            onMouseMove={handleMouseMove}
                            onMouseLeave={handleMouseLeave}
                        >
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                            <XAxis
                                dataKey="time_idx"
                                tickFormatter={formatXAxis}
                                tick={{ fontSize: 12, fill: '#9CA3AF' }}
                                axisLine={false}
                                tickLine={false}
                                minTickGap={40}
                            />
                            <YAxis
                                tick={{ fontSize: 12, fill: '#9CA3AF' }}
                                axisLine={false}
                                tickLine={false}
                                domain={['auto', 'auto']}
                                tickFormatter={(val) => `${val.toFixed(2)}%`}
                                width={50}
                            />
                            {/* Grey line at 0 */}
                            <ReferenceLine y={0} stroke="#9CA3AF" strokeDasharray="3 3" />

                            {/* Invisible tooltip to capture hover but not render popover */}
                            <Tooltip content={() => null} cursor={{ stroke: '#9CA3AF', strokeWidth: 1, strokeDasharray: '4 4' }} />

                            <Line
                                type="monotone"
                                dataKey="high"
                                stroke="#10b981"
                                strokeWidth={2}
                                dot={false}
                                connectNulls={true}
                                name="Median High"
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="low"
                                stroke="#ef4444"
                                strokeWidth={2}
                                dot={false}
                                connectNulls={true}
                                name="Median Low"
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
                </div>
            </CardContent>
        </Card>
    );
});
