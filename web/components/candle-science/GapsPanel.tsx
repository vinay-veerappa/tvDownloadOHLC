import { ProbabilityBar } from './ProbabilityBar';
import { GapsStats } from '@/lib/candle-science/types';

interface GapsPanelProps {
    gaps: GapsStats;
}

export function GapsPanel({ gaps }: GapsPanelProps) {
    return (
        <div className="bg-[#1e1e1e]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-6 flex flex-col shadow-2xl relative overflow-hidden group">
            {/* Ambient Accent */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 blur-[60px] pointer-events-none" />

            <h3 className="text-sm font-bold text-white mb-6 flex items-center gap-3 relative z-10">
                <span className="w-1.5 h-4 bg-blue-400 rounded-full" />
                Gaps (Open)
            </h3>

            <div className="grid grid-cols-1 gap-8">
                {/* C2 vs C1 */}
                <div className="space-y-6">
                    <div className="text-[10px] font-bold text-[#606060] uppercase tracking-widest mb-4">C2 Open vs C1</div>
                    <div className="space-y-4">
                        <ProbabilityBar
                            leftLabel="C2 Open"
                            rightLabel="C1 Close"
                            leftValue={gaps.c2_vs_c1.open_vs_close.above}
                            rightValue={gaps.c2_vs_c1.open_vs_close.below}
                        />
                        <ProbabilityBar
                            leftLabel="C2 Open"
                            rightLabel="C1 Open"
                            leftValue={gaps.c2_vs_c1.open_vs_open.above}
                            rightValue={gaps.c2_vs_c1.open_vs_open.below}
                        />
                    </div>
                </div>

                {/* C3 vs C2 */}
                <div className="space-y-6">
                    <div className="text-[10px] font-bold text-[#606060] uppercase tracking-widest mb-4">C3 Open vs C2</div>
                    <div className="space-y-4">
                        <ProbabilityBar
                            leftLabel="C3 Open"
                            rightLabel="C2 Close"
                            leftValue={gaps.c3_vs_c2.open_vs_close.above}
                            rightValue={gaps.c3_vs_c2.open_vs_close.below}
                            median_dist={gaps.c3_vs_c2.open_vs_close.median_dist}
                            showMedian
                        />
                        <ProbabilityBar
                            leftLabel="C3 Open"
                            rightLabel="C2 Open"
                            leftValue={gaps.c3_vs_c2.open_vs_open.above}
                            rightValue={gaps.c3_vs_c2.open_vs_open.below}
                            median_dist={gaps.c3_vs_c2.open_vs_open.median_dist}
                            showMedian
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
