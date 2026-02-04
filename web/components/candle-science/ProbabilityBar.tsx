interface ProbabilityBarProps {
    leftLabel: string;
    rightLabel: string;
    leftValue: number;
    rightValue: number;
    median_dist?: number;
    showMedian?: boolean;
}

export function ProbabilityBar({
    leftLabel,
    rightLabel,
    leftValue,
    rightValue,
    median_dist,
    showMedian = false
}: ProbabilityBarProps) {
    const isLeftHigher = leftValue >= rightValue;

    return (
        <div className="flex items-center gap-3 w-full">
            <span className="text-[11px] font-bold text-[#a0a0a0] w-24 text-right shrink-0 uppercase tracking-tight">{leftLabel}</span>

            <div className="flex-1 flex items-center gap-1 min-w-0">
                <div
                    className={`px-2 py-1.5 rounded text-[10px] font-bold shrink-0 min-w-[70px] text-center transition-all ${leftValue > 50 ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/20' : 'bg-[#3d3d3d] text-[#a0a0a0]'
                        }`}
                >
                    {leftValue}%
                </div>
                <div className="flex-1 h-[2px] bg-[#3d3d3d] rounded" />
                <div
                    className={`px-2 py-1.5 rounded text-[10px] font-bold shrink-0 min-w-[70px] text-center transition-all ${rightValue > 50 ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/20' : 'bg-[#3d3d3d] text-[#a0a0a0]'
                        }`}
                >
                    {rightValue}%
                </div>
            </div>

            <span className="text-[11px] font-bold text-[#a0a0a0] w-24 shrink-0 uppercase tracking-tight">{rightLabel}</span>

            {showMedian && median_dist !== undefined && (
                <span className={`text-[10px] w-14 text-right shrink-0 font-mono font-bold ${median_dist >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {median_dist >= 0 ? '+' : ''}{median_dist.toFixed(3)}%
                </span>
            )}
        </div>
    );
}
