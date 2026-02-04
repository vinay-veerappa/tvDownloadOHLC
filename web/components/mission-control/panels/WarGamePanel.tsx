/**
 * War Game Matrix Panel
 * 
 * Visualizes scenario-based probability analysis (The Battle).
 */

'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Target, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';
import type { WarGameAnalysis, WarGameScenario } from '@/lib/mission-control/calculators/war-game';

interface WarGamePanelProps {
    data: WarGameAnalysis | null;
    isLoading: boolean;
}

import { Skeleton } from '@/components/ui/skeleton';

export function WarGamePanel({ data, isLoading }: WarGamePanelProps) {
    if (isLoading || !data) {
        return (
            <div className="grid grid-cols-2 gap-4 h-full">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="rounded-xl border border-slate-800 p-4 space-y-3">
                        <div className="flex justify-between">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-4 rounded-full" />
                        </div>
                        <Skeleton className="h-8 w-16" />
                        <div className="space-y-1">
                            <Skeleton className="h-3 w-full" />
                            <Skeleton className="h-3 w-2/3" />
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    const renderScenario = (scenario: WarGameScenario) => {
        const isActive = data.currentScenario === (scenario.id.startsWith('long') ? 'long' : 'short');
        const isTrue = scenario.id.endsWith('True');

        return (
            <div
                key={scenario.id}
                className={`relative overflow-hidden rounded-xl border p-4 transition-all duration-300 ${isActive
                    ? 'border-orange-500/50 bg-orange-500/5 ring-1 ring-orange-500/20'
                    : 'border-slate-800 bg-slate-900/50 opacity-60'
                    }`}
            >
                {/* Status Indicator */}
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        {isTrue ? (
                            <TrendingUp className={`w-4 h-4 ${isActive ? 'text-green-400' : 'text-slate-500'}`} />
                        ) : (
                            <TrendingDown className={`w-4 h-4 ${isActive ? 'text-red-400' : 'text-slate-500'}`} />
                        )}
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${isActive ? 'text-slate-200' : 'text-slate-500'
                            }`}>
                            {scenario.name}
                        </span>
                    </div>
                    {isActive && (
                        <Badge variant="outline" className="bg-orange-500/10 text-orange-400 border-orange-500/30 text-[9px] h-4 px-1.5 font-bold">
                            ACTIVE
                        </Badge>
                    )}
                </div>

                {/* Probability Display */}
                <div className="flex items-baseline gap-1 mb-1">
                    <span className={`text-3xl font-black tabular-nums ${isActive ? 'text-white' : 'text-slate-400'
                        }`}>
                        {scenario.probability.toFixed(1)}
                    </span>
                    <span className="text-sm font-bold text-slate-500">%</span>
                </div>

                <div className="text-[10px] text-slate-500 mb-3">
                    Sample: n={scenario.sampleSize}
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-2 gap-2 border-t border-slate-800/50 pt-3">
                    <div>
                        <div className="text-[9px] uppercase text-slate-500 mb-0.5">Avg MFE</div>
                        <div className={`text-xs font-mono font-bold ${isActive ? 'text-green-400' : 'text-slate-500'}`}>
                            +{scenario.metrics.avgMfe.toFixed(2)}%
                        </div>
                    </div>
                    <div>
                        <div className="text-[9px] uppercase text-slate-500 mb-0.5">Avg MAE</div>
                        <div className={`text-xs font-mono font-bold ${isActive ? 'text-red-400' : 'text-slate-500'}`}>
                            {scenario.metrics.avgMae.toFixed(2)}%
                        </div>
                    </div>
                </div>

                {/* Subtext description */}
                <div className="mt-3 text-[10px] italic text-slate-500 leading-tight">
                    {scenario.description}
                </div>

                {/* Background Decoration */}
                <div className="absolute top-0 right-0 p-4 pointer-events-none opacity-5">
                    {isTrue ? <Target size={64} /> : <AlertTriangle size={64} />}
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
                {data.scenarios.map(renderScenario)}
            </div>

            {/* Legend/Note */}
            <div className="flex items-center justify-center gap-4 py-2 border-t border-slate-800/50 mt-2">
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    <span className="text-[9px] font-medium text-slate-400 uppercase tracking-tighter">Follow Through</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                    <span className="text-[9px] font-medium text-slate-400 uppercase tracking-tighter">Trap/Reversal</span>
                </div>
            </div>
        </div>
    );
}
