/**
 * Distro (Fuel) Panel
 * 
 * Matrix view of Session Ranges vs Day of Week (DOW) medians.
 */

'use client';

import type { DistroAnalysis, DistroMetric } from '@/lib/mission-control/calculators/distro';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

interface DistroPanelProps {
    data: DistroAnalysis | null;
    isLoading: boolean;
}

export function DistroPanel({ data, isLoading }: DistroPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="space-y-4 p-2">
                <Skeleton className="h-6 w-48" />
                <div className="space-y-2">
                    {[...Array(5)].map((_, i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                    ))}
                </div>
            </div>
        );
    }

    const { globalMedianRange, rows } = data;
    // Get DOW for today (from system time as dashboard is live-ish)
    // Or derive from data if possible. Let's use system Mon-Fri for now.
    const dowMap = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
    const todayIndex = new Date().getDay();
    const todayLabel = dowMap[todayIndex];
    // If weekend, maybe show Friday? Or just current day.
    // Let's default to todayLabel, but if it's SAT/SUN, maybe show FRI or empty?
    // User trades weekdays.

    return (
        <div className="space-y-4">
            {/* Header / Global Stat */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 px-2">
                <div className="flex flex-col">
                    <span className="text-xs text-slate-500 uppercase tracking-wider">Daily Range</span>
                    <div className="flex items-baseline gap-2">
                        <span className="font-mono text-xl font-bold text-slate-200">
                            {data.todayDailyRange.toFixed(1)}
                        </span>
                        <span className="text-xs text-slate-400">
                            ({data.todayDailyRangePct.toFixed(2)}%)
                        </span>
                    </div>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-xs text-slate-500 uppercase tracking-wider">10d Median</span>
                    <span className="font-mono text-lg font-bold text-slate-400">
                        {globalMedianRange.toFixed(2)}
                    </span>
                </div>
            </div>

            {/* Simplified Table */}
            <Table>
                <TableHeader>
                    <TableRow className="hover:bg-transparent border-slate-800">
                        <TableHead className="w-[80px] text-xs font-bold text-slate-400">Session</TableHead>
                        <TableHead className="text-right text-xs font-bold text-slate-300">
                            Today
                        </TableHead>
                        <TableHead className="text-right text-xs font-bold text-slate-500">
                            {todayLabel} Median
                        </TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {rows.map((row) => {
                        // Find median for today's DOW
                        const medianMetric = row.history[todayLabel];
                        // If we are on weekend, might be undefined if logic skips SAT/SUN
                        // But distro.ts populates MON-FRI.

                        return (
                            <TableRow key={row.id} className="hover:bg-slate-900/50 border-slate-800">
                                <TableCell className="font-bold text-slate-400 text-xs">
                                    {row.label}
                                </TableCell>
                                <TableCell className="text-right font-mono bg-slate-900/20">
                                    {row.today ? (
                                        <DataCell metric={row.today} isToday />
                                    ) : (
                                        <span className="text-slate-700">-</span>
                                    )}
                                </TableCell>
                                <TableCell className="text-right font-mono text-slate-500">
                                    {medianMetric ? (
                                        <DataCell metric={medianMetric} />
                                    ) : (
                                        <span className="text-slate-800">-</span>
                                    )}
                                </TableCell>
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </div>
    );
}

function DataCell({ metric, isToday = false }: { metric: DistroMetric, isToday?: boolean }) {
    if (metric.count === 0 || metric.range === 0) return <span className="text-slate-800">-</span>;

    return (
        <div className="flex flex-col items-end leading-tight">
            <div className="flex items-baseline gap-1">
                <span className={`text-sm ${isToday ? 'text-slate-200 font-bold' : 'text-slate-400'}`}>
                    {metric.range.toFixed(1)}
                </span>
                <span className="text-[10px] text-muted-foreground">
                    ({metric.pct.toFixed(2)}%)
                </span>
            </div>
            {!isToday && metric.count > 0 && (
                <span className="text-[9px] text-slate-600">
                    [{metric.count}]
                </span>
            )}
        </div>
    );
}
