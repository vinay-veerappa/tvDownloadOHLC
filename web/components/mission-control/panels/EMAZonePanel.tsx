/**
 * EMA Zone Panel
 * 
 * Displays Daily 5 EMA probability zones with hit rates.
 */

'use client';

import type { EMAZoneAnalysis } from '@/lib/mission-control/calculators/ema-zones';

interface EMAZonePanelProps {
    data: EMAZoneAnalysis | null;
    isLoading: boolean;
}

export function EMAZonePanel({ data, isLoading }: EMAZonePanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'No data available'}
            </div>
        );
    }

    const { current_ema, current_price, current_distance_pct, zone_levels } = data;

    return (
        <div className="space-y-4">
            {/* Current Status */}
            <div className="grid grid-cols-3 gap-4 rounded-lg bg-muted/50 p-3">
                <div>
                    <div className="text-xs text-muted-foreground">Current Price</div>
                    <div className="text-lg font-semibold">{current_price.toFixed(2)}</div>
                </div>
                <div>
                    <div className="text-xs text-muted-foreground">Daily 5 EMA</div>
                    <div className="text-lg font-semibold">{current_ema.toFixed(2)}</div>
                </div>
                <div>
                    <div className="text-xs text-muted-foreground">Distance</div>
                    <div
                        className={`text-lg font-semibold ${current_distance_pct > 0 ? 'text-green-500' : 'text-red-500'
                            }`}
                    >
                        {current_distance_pct > 0 ? '+' : ''}
                        {current_distance_pct.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* Zone Levels Table */}
            <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="px-3 py-2 text-left font-medium">Zone</th>
                            <th className="px-3 py-2 text-right font-medium">Price Above</th>
                            <th className="px-3 py-2 text-right font-medium">Price Below</th>
                            <th className="px-3 py-2 text-right font-medium">Hit Rate ↑</th>
                            <th className="px-3 py-2 text-right font-medium">Hit Rate ↓</th>
                            <th className="px-3 py-2 text-center font-medium">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {zone_levels.map((zone, idx) => (
                            <tr
                                key={zone.level_pct}
                                className={`border-t ${idx % 2 === 0 ? 'bg-background' : 'bg-muted/20'}`}
                            >
                                <td className="px-3 py-2 font-medium">{zone.level_pct}%</td>
                                <td className="px-3 py-2 text-right tabular-nums">
                                    {zone.price_above.toFixed(2)}
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums">
                                    {zone.price_below.toFixed(2)}
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums text-green-500">
                                    {zone.hit_rate_up.toFixed(0)}%
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums text-red-500">
                                    {zone.hit_rate_down.toFixed(0)}%
                                </td>
                                <td className="px-3 py-2 text-center">
                                    <span
                                        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${zone.status === 'Good'
                                                ? 'bg-green-500/20 text-green-500'
                                                : zone.status === 'Fair'
                                                    ? 'bg-yellow-500/20 text-yellow-500'
                                                    : 'bg-red-500/20 text-red-500'
                                            }`}
                                    >
                                        {zone.status}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Footer */}
            <div className="text-xs text-muted-foreground">
                Based on {data.lookback_weeks} weeks of data
            </div>
        </div>
    );
}
