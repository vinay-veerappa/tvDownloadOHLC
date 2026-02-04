/**
 * Distro (Fuel) Panel
 * 
 * Session range distribution and fuel percentage analysis.
 */

'use client';

import type { DistroAnalysis } from '@/lib/mission-control/calculators/distro';

interface DistroPanelProps {
    data: DistroAnalysis | null;
    isLoading: boolean;
}

export function DistroPanel({ data, isLoading }: DistroPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'No data available'}
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {/* Session Cards */}
            <div className="grid grid-cols-2 gap-3">
                {data.sessions.map((session) => (
                    <div
                        key={session.session}
                        className="rounded-lg border bg-card p-3"
                    >
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-sm font-medium">{session.session}</span>
                            <span
                                className={`rounded px-2 py-0.5 text-xs font-medium ${session.status === 'High'
                                    ? 'bg-green-500/20 text-green-500'
                                    : session.status === 'Low'
                                        ? 'bg-red-500/20 text-red-500'
                                        : 'bg-yellow-500/20 text-yellow-500'
                                    }`}
                            >
                                {session.status}
                            </span>
                        </div>

                        <div className="space-y-1">
                            <div className="flex justify-between text-xs">
                                <span className="text-muted-foreground">Current Range:</span>
                                <span className="font-medium tabular-nums">{session.current_range.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-muted-foreground">Median Range:</span>
                                <span className="font-medium tabular-nums">{session.median_range.toFixed(2)}</span>
                            </div>
                            <div className="mt-2 flex justify-between">
                                <span className="text-xs text-muted-foreground">Fuel:</span>
                                <span
                                    className={`text-lg font-bold ${session.fuel_pct > 120
                                        ? 'text-green-500'
                                        : session.fuel_pct < 80
                                            ? 'text-red-500'
                                            : 'text-yellow-500'
                                        }`}
                                >
                                    {session.fuel_pct.toFixed(0)}%
                                </span>
                            </div>
                        </div>

                        {/* Fuel Bar */}
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                            <div
                                className={`h-full transition-all dynamic-width ${session.fuel_pct > 120
                                    ? 'bg-green-500'
                                    : session.fuel_pct < 80
                                        ? 'bg-red-500'
                                        : 'bg-yellow-500'
                                    }`}
                                style={{ '--width': `${session.fuel_pct}%` } as React.CSSProperties}
                            />
                        </div>
                    </div>
                ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-green-500" />
                    <span>High (&gt;120%)</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-yellow-500" />
                    <span>Normal (80-120%)</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-red-500" />
                    <span>Low (&lt;80%)</span>
                </div>
            </div>
        </div>
    );
}
