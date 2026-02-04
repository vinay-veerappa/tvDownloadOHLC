/**
 * Candle Science Panel
 * 
 * Displays C3 distribution probabilities and pattern matches.
 */

'use client';

import type { C3Projection } from '@/lib/mission-control/calculators/candle-science';

interface CandleSciencePanelProps {
    data: C3Projection | null;
    isLoading: boolean;
}

export function CandleSciencePanel({ data, isLoading }: CandleSciencePanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'No historical pattern matches found'}
            </div>
        );
    }

    const isBullish = data.bullish_pct > data.bearish_pct;

    return (
        <div className="space-y-4">
            {/* Bias Meter */}
            <div className="space-y-2">
                <div className="flex justify-between text-xs font-bold uppercase tracking-wider">
                    <span className="text-green-500">Bullish {data.bullish_pct.toFixed(0)}%</span>
                    <span className="text-red-500">Bearish {data.bearish_pct.toFixed(0)}%</span>
                </div>
                <div className="flex h-3 overflow-hidden rounded-full bg-muted shadow-inner">
                    <div
                        className="bg-green-500 transition-all duration-1000 dynamic-width"
                        style={{ '--width': `${data.bullish_pct}%` } as React.CSSProperties}
                    />
                    <div
                        className="bg-red-500 transition-all duration-1000 dynamic-width"
                        style={{ '--width': `${data.bearish_pct}%` } as React.CSSProperties}
                    />
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="text-[10px] uppercase text-muted-foreground">Pattern Match</div>
                    <div className="text-sm font-bold">
                        C1: {data.patterns.c1} → C2: {data.patterns.c2}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                        {data.sample_size} historical matches
                    </div>
                </div>
                <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="text-[10px] uppercase text-muted-foreground">Primary Bias</div>
                    <div className={`text-sm font-bold ${isBullish ? 'text-green-500' : 'text-red-500'}`}>
                        {isBullish ? 'BULLISH' : 'BEARISH'}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                        Conf: {(Math.abs(data.bullish_pct - 50) * 2).toFixed(0)}%
                    </div>
                </div>
            </div>

            {/* Probabilities Table */}
            <div className="rounded-lg border bg-background overflow-hidden">
                <div className="bg-muted px-3 py-1.5 text-[10px] font-bold uppercase text-muted-foreground">
                    C3 Position Probabilities
                </div>
                <div className="p-2 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-xs">Close &gt; C2 High</span>
                        <span className="text-sm font-bold tabular-nums">
                            {data.probabilities.close_above_c2_high.toFixed(1)}%
                        </span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-xs">Close &lt; C2 Low</span>
                        <span className="text-sm font-bold tabular-nums">
                            {data.probabilities.close_below_c2_low.toFixed(1)}%
                        </span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-xs">High &gt; C2 High</span>
                        <span className="text-sm font-bold tabular-nums">
                            {data.probabilities.high_above_c2_high.toFixed(1)}%
                        </span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-xs">Low &lt; C2 Low</span>
                        <span className="text-sm font-bold tabular-nums">
                            {data.probabilities.low_below_c2_low.toFixed(1)}%
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
