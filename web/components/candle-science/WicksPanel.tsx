import { ProbabilityBar } from './ProbabilityBar';
import { WicksStats, LowWicksStats } from '@/lib/candle-science/types';

interface WicksPanelProps {
    title: string;
    c2VsC1: WicksStats['c2_vs_c1'] | LowWicksStats['c2_vs_c1'];
    c3VsC2: WicksStats['c3_vs_c2'] | LowWicksStats['c3_vs_c2'];
    type: 'high' | 'low';
}

export function WicksPanel({ title, c2VsC1, c3VsC2, type }: WicksPanelProps) {
    const isHigh = type === 'high';

    return (
        <div className="bg-[#1e1e1e]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-6 flex flex-col shadow-2xl relative overflow-hidden group">
            {/* Ambient Background */}
            <div className={`absolute top-0 right-0 w-32 h-32 ${type === 'high' ? 'bg-emerald-500/5' : 'bg-rose-500/5'} blur-[60px] pointer-events-none`} />

            <h3 className="text-sm font-bold text-white mb-6 flex items-center gap-3 relative z-10">
                <span className={`w-1.5 h-4 ${type === 'high' ? 'bg-orange-500' : 'bg-blue-500'} rounded-full`} />
                {title}
            </h3>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 xl:gap-16">
                {/* C2 vs C1 */}
                <div className="space-y-6">
                    <div className="text-[10px] font-bold text-[#606060] uppercase tracking-widest mb-4">C2 vs C1</div>
                    <div className="space-y-4">
                        <ProbabilityBar
                            leftLabel={isHigh ? "C2 High" : "C2 Low"}
                            rightLabel={isHigh ? "C1 High" : "C1 Low"}
                            leftValue={(c2VsC1 as any)[isHigh ? 'high_vs_high' : 'low_vs_low'].above}
                            rightValue={(c2VsC1 as any)[isHigh ? 'high_vs_high' : 'low_vs_low'].below}
                        />
                        <ProbabilityBar
                            leftLabel={isHigh ? "C2 High" : "C2 Low"}
                            rightLabel="C1 Open"
                            leftValue={(c2VsC1 as any)[isHigh ? 'high_vs_open' : 'low_vs_open'].above}
                            rightValue={(c2VsC1 as any)[isHigh ? 'high_vs_open' : 'low_vs_open'].below}
                        />
                    </div>
                </div>

                {/* C3 vs C2 */}
                <div className="space-y-6">
                    <div className="text-[10px] font-bold text-[#606060] uppercase tracking-widest mb-4">C3 vs C2</div>
                    <div className="space-y-4">
                        <ProbabilityBar
                            leftLabel={isHigh ? "C3 High" : "C3 Low"}
                            rightLabel={isHigh ? "C2 High" : "C2 Low"}
                            leftValue={(c3VsC2 as any)[isHigh ? 'high_vs_high' : 'low_vs_low'].above}
                            rightValue={(c3VsC2 as any)[isHigh ? 'high_vs_high' : 'low_vs_low'].below}
                            median_dist={(c3VsC2 as any)[isHigh ? 'high_vs_high' : 'low_vs_low'].median_dist}
                            showMedian
                        />
                        <ProbabilityBar
                            leftLabel={isHigh ? "C3 High" : "C3 Low"}
                            rightLabel="C2 Open"
                            leftValue={(c3VsC2 as any)[isHigh ? 'high_vs_open' : 'low_vs_open'].above}
                            rightValue={(c3VsC2 as any)[isHigh ? 'high_vs_open' : 'low_vs_open'].below}
                            median_dist={(c3VsC2 as any)[isHigh ? 'high_vs_open' : 'low_vs_open'].median_dist}
                            showMedian
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
