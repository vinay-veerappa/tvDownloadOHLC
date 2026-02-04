'use client';

import '@/app/mission-control.css';
import type { HTFTrinityAnalysis } from '@/lib/mission-control/calculators/htf-trinity';

interface HTFTrinityPanelProps {
    data: HTFTrinityAnalysis | null;
    isLoading: boolean;
}

export function HTFTrinityPanel({ data, isLoading }: HTFTrinityPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'HTF Data Unavailable'}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Bias Summary */}
            <div className={`rounded-xl border-2 p-3 text-center transition-all ${data.trinity_bias === 'BULLISH'
                ? 'border-green-500/50 bg-green-500/10'
                : 'border-red-500/50 bg-red-500/10'
                }`}>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Trinity Alignment</div>
                <div className={`text-xl font-black ${data.trinity_bias === 'BULLISH' ? 'text-green-500' : 'text-red-500'
                    }`}>
                    {data.trinity_bias}
                </div>
            </div>

            {/* EMA Status */}
            <div className="flex items-center justify-between rounded-lg bg-muted/30 p-2">
                <div className="text-xs font-bold uppercase text-muted-foreground">Daily 5 EMA</div>
                <div className="flex items-center gap-2">
                    <span className="text-sm font-bold tabular-nums">{data.daily_ema.value.toFixed(2)}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${data.daily_ema.position === 'ABOVE' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
                        }`}>
                        {data.daily_ema.position}
                    </span>
                </div>
            </div>

            {/* TF Grid */}
            <div className="grid grid-cols-2 gap-3">
                {[data.weekly, data.monthly].map((profile) => (
                    <div key={profile.timeframe} className="rounded-lg border bg-card p-3 shadow-sm">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                            {profile.timeframe}
                        </div>
                        <div className="flex justify-between items-end mb-2">
                            <div className="text-lg font-black tabular-nums leading-none">
                                {profile.position_pct.toFixed(0)}%
                            </div>
                            <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${profile.zone === 'PREMIUM' ? 'bg-green-500/20 text-green-500' :
                                profile.zone === 'DISCOUNT' ? 'bg-red-500/20 text-red-500' :
                                    'bg-yellow-500/20 text-yellow-500'
                                }`}>
                                {profile.zone}
                            </div>
                        </div>
                        <div className="htf-trinity-slider">
                            <div className="htf-trinity-midline" />
                            <div
                                className={`htf-trinity-slider-marker ${profile.position_pct > 50 ? 'bg-green-500' : 'bg-red-500'}`}
                                style={{ left: `${profile.position_pct}%` } as React.CSSProperties}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
