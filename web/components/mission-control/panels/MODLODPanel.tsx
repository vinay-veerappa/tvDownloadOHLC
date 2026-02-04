'use client';

import '@/app/mission-control.css';
import type { HODLODAnalysis } from '@/lib/mission-control/calculators/hod-lod';

interface MODLODPanelProps {
    data: HODLODAnalysis | null;
    isLoading: boolean;
}

export function MODLODPanel({ data, isLoading }: MODLODPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground animate-pulse">
                {isLoading ? 'Loading HOD/LOD Radar...' : 'Insufficient data for conditional profile'}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Context Header */}
            <div className="rounded-lg bg-slate-900/50 border border-slate-800 p-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Context: {data.overnight_profile.replace('_', ' ')} sessions ({data.match_count} matches)
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* HOD Distribution */}
                <div className="space-y-3">
                    <div className="flex justify-between items-center">
                        <h4 className="text-[11px] font-black text-green-500 uppercase tracking-tighter">HOD Timing</h4>
                        <span className="text-[10px] font-mono font-bold text-green-400/70 border border-green-500/20 px-1.5 py-0.5 rounded bg-green-500/5">{data.hod_mode}</span>
                    </div>
                    <div className="space-y-2">
                        {data.hod_distribution.slice(0, 5).map((item) => (
                            <div key={item.time} className="flex items-center gap-3 group">
                                <span className="w-10 text-[10px] font-mono text-slate-500 tabular-nums">{item.time}</span>
                                <div className="progress-bar-container h-1.5 bg-slate-900">
                                    <div
                                        className="progress-bar-fill bg-green-500"
                                        style={{ width: `${item.probability}%` } as React.CSSProperties}
                                    />
                                </div>
                                <span className="w-8 text-[10px] text-right font-black tabular-nums text-slate-400">
                                    {item.probability.toFixed(0)}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* LOD Distribution */}
                <div className="space-y-3">
                    <div className="flex justify-between items-center">
                        <h4 className="text-[11px] font-black text-red-500 uppercase tracking-tighter">LOD Timing</h4>
                        <span className="text-[10px] font-mono font-bold text-red-400/70 border border-red-500/20 px-1.5 py-0.5 rounded bg-red-500/5">{data.lod_mode}</span>
                    </div>
                    <div className="space-y-2">
                        {data.lod_distribution.slice(0, 5).map((item) => (
                            <div key={item.time} className="flex items-center gap-3 group">
                                <span className="w-10 text-[10px] font-mono text-slate-500 tabular-nums">{item.time}</span>
                                <div className="progress-bar-container h-1.5 bg-slate-900">
                                    <div
                                        className="progress-bar-fill bg-red-500"
                                        style={{ width: `${item.probability}%` } as React.CSSProperties}
                                    />
                                </div>
                                <span className="w-8 text-[10px] text-right font-black tabular-nums text-slate-400">
                                    {item.probability.toFixed(0)}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
