"use client"

import { useMemo } from 'react';
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
    ReferenceLine
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

export function PriceModelChart({
    ticker,
    session,
    targetSession,
    filters,
    brokenFilters,
    intraState,
    height = 300
}: PriceModelChartProps) {
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
        intraState
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
                intra_state: intraState
            };
            return fetchFilteredPriceModel(payload);
        },
        {
            revalidateOnFocus: false,
            dedupingInterval: 1000,
        }
    );

    const chartData = useMemo(() => {
        if (!data || !data.average) return [];
        return data.average.map(d => ({
            ...d,
            // Format time for X-axis display if needed? 
            // Or use time_idx as minutes
        }));
    }, [data]);

    // Format minute index to HH:MM relative to session start?
    // Session start times: Asia=18:00, London=03:00, NY1=07:30, NY2=11:30, Daily=18:00
    const formatXAxis = (tickItem: number) => {
        let startHour = 18;
        let startMin = 0;

        if (session === 'London') startHour = 3;
        if (session === 'NY1') { startHour = 7; startMin = 30; }
        if (session === 'NY2') { startHour = 11; startMin = 30; }
        // daily is 18:00

        const totalMinutes = startHour * 60 + startMin + tickItem;
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
                time: formatXAxis(payload.time_idx), // Recalculate time string
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
                <div className="pt-2 px-4">
                    <ChartHeaderInfo
                        title={`${session} Price Model (Median)`}
                        subtitle={`${data.count} Sessions`}
                        items={headerItems.length > 0 ? headerItems : [
                            { label: 'Hover chart for details', value: '' }
                        ]}
                    />
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
                                tick={{ fontSize: 10, fill: '#6B7280' }}
                                axisLine={false}
                                tickLine={false}
                                minTickGap={30}
                            />
                            <YAxis
                                tick={{ fontSize: 10, fill: '#6B7280' }}
                                axisLine={false}
                                tickLine={false}
                                domain={['auto', 'auto']}
                                tickFormatter={(val) => `${val.toFixed(2)}%`}
                                width={45}
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
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="low"
                                stroke="#ef4444"
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
}
