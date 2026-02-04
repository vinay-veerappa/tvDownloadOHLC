'use client';

import '@/app/mission-control.css';
import type { PremiumDiscountAnalysis } from '@/lib/mission-control/calculators/premium-discount';

interface PremiumDiscountPanelProps {
    data: PremiumDiscountAnalysis | null;
    isLoading: boolean;
}

export function PremiumDiscountPanel({ data, isLoading }: PremiumDiscountPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'No data available'}
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {/* Current Price */}
            <div className="rounded-lg bg-muted/50 p-2 text-center">
                <div className="text-xs text-muted-foreground">Current Price</div>
                <div className="text-xl font-bold">{data.current_price.toFixed(2)}</div>
            </div>

            {/* Timeframe Analysis Table */}
            <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="px-2 py-1.5 text-left font-medium">TF</th>
                            <th className="px-2 py-1.5 text-right font-medium">High</th>
                            <th className="px-2 py-1.5 text-right font-medium">Low</th>
                            <th className="px-2 py-1.5 text-right font-medium">EQ</th>
                            <th className="px-2 py-1.5 text-center font-medium">Zone</th>
                            <th className="px-2 py-1.5 text-right font-medium">Pos%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.timeframes.map((tf, idx) => (
                            <tr
                                key={tf.timeframe}
                                className={`border-t ${idx % 2 === 0 ? 'bg-background' : 'bg-muted/20'}`}
                            >
                                <td className="px-2 py-1.5 font-medium">{tf.timeframe}</td>
                                <td className="px-2 py-1.5 text-right tabular-nums text-xs">
                                    {tf.range_high.toFixed(2)}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums text-xs">
                                    {tf.range_low.toFixed(2)}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums text-xs">
                                    {tf.equilibrium.toFixed(2)}
                                </td>
                                <td className="px-2 py-1.5 text-center">
                                    <span
                                        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tf.zone === 'PREMIUM'
                                            ? 'bg-green-500/20 text-green-500'
                                            : tf.zone === 'DISCOUNT'
                                                ? 'bg-red-500/20 text-red-500'
                                                : 'bg-yellow-500/20 text-yellow-500'
                                            }`}
                                    >
                                        {tf.zone === 'PREMIUM' ? 'PREM' : tf.zone === 'DISCOUNT' ? 'DISC' : 'EQ'}
                                    </span>
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums text-xs">
                                    {tf.position_pct.toFixed(0)}%
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Visual Bar */}
            <div className="space-y-1">
                {data.timeframes.slice(0, 3).map((tf) => (
                    <div key={tf.timeframe} className="flex items-center gap-2">
                        <span className="w-8 text-xs font-medium text-muted-foreground">{tf.timeframe}</span>
                        <div className="relative h-4 flex-1 rounded-full bg-muted">
                            {/* Equilibrium line */}
                            <div className="absolute left-1/2 top-0 h-full w-0.5 bg-yellow-500/50" />
                            {/* Position indicator */}
                            <div
                                className="absolute top-0 h-full w-1 rounded-full bg-foreground dynamic-left"
                                style={{ '--left': `${tf.position_pct}%` } as React.CSSProperties}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
