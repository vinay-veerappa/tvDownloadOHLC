import { ArrowUp, ArrowDown, BarChart2 } from 'lucide-react';
import { ComparisonType } from '@/lib/candle-science/types';

interface LedgerItem {
    bullLabel: string;
    bullSubLabel: string;
    bearLabel: string;
    bearSubLabel: string;
    bull_val: number;
    bear_val: number;
    bull_return?: number;
    bear_return?: number;
    comparisonKey?: ComparisonType;
}

interface SignalCardGridProps {
    title: string;
    items: LedgerItem[];
    gridCols?: string;
    onOpenScatter?: (key: ComparisonType) => void;
}

export function SignalCardGrid({ title, items, gridCols, onOpenScatter }: SignalCardGridProps) {
    return (
        <div className="flex flex-col gap-4">
            {/* Header */}
            <div className="flex items-center gap-3 mb-2 px-2">
                <span className="w-1.5 h-4 rounded-full bg-blue-500" />
                <h3 className="text-sm font-black uppercase tracking-[0.2em] text-white">
                    {title}
                </h3>
            </div>

            {/* Grid */}
            <div className={`grid gap-4 ${gridCols || 'grid-cols-2 xl:grid-cols-4'}`}>
                {items.map((item, idx) => (
                    <SignalCard key={idx} item={item} onClick={onOpenScatter} />
                ))}
            </div>
        </div>
    );
}

function SignalCard({ item, onClick }: { item: LedgerItem; onClick?: (key: ComparisonType) => void }) {
    const isBullFavored = item.bull_val >= item.bear_val;
    const isClose = Math.abs(item.bull_val - item.bear_val) < 2;

    // Use median return if available
    const winRet = isBullFavored ? item.bull_return : item.bear_return;
    const loseRet = isBullFavored ? item.bear_return : item.bull_return;

    // Fallback if return not provided (e.g. for C1/C2 trend which don't have it)
    const hasReturn = winRet !== undefined;
    const displayRet = winRet ?? 0;

    const winVal = isBullFavored ? item.bull_val : item.bear_val;
    const loseVal = isBullFavored ? item.bear_val : item.bull_val;

    const currentLabel = isBullFavored ? item.bullLabel : item.bearLabel;
    const currentSubLabel = isBullFavored ? item.bullSubLabel : item.bearSubLabel;

    const canClick = !!item.comparisonKey;

    return (
        <div
            onClick={() => canClick && onClick?.(item.comparisonKey!)}
            className={`bg-[#1e1e1e]/60 backdrop-blur-xl rounded-xl border border-white/5 p-4 flex flex-col items-center text-center shadow-lg transition-all group relative overflow-hidden
                ${canClick ? 'cursor-pointer hover:border-white/20 hover:bg-[#1e1e1e]/80 hover:scale-[1.02]' : ''}
            `}
        >
            {/* Ambient Glow */}
            <div className={`absolute -top-10 -right-10 w-20 h-20 blur-[40px] pointer-events-none transition-opacity duration-500
                ${isBullFavored ? 'bg-emerald-500/10' : 'bg-rose-500/10'} opacity-0 group-hover:opacity-100
            `} />

            {/* Click Hint */}
            {canClick && (
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <BarChart2 className="w-3 h-3 text-white/40" />
                </div>
            )}

            <span className="text-[9px] font-bold text-[#808080] uppercase tracking-widest mb-0.5">
                {currentLabel}
            </span>
            <span className="text-[8px] font-medium text-[#505050] uppercase tracking-tight mb-2">
                {currentSubLabel}
            </span>

            {/* Hero Number */}
            <div className="flex items-baseline gap-1 mb-1">
                <span className={`text-2xl font-black tracking-tighter
                    ${isBullFavored ? 'text-emerald-400' : 'text-rose-400'}
                `}>
                    {winVal.toFixed(1)}
                </span>
                <span className="text-xs font-bold text-[#606060]">%</span>
            </div>

            {/* Secondary & Return Badge */}
            <div className="w-full flex items-center justify-between border-t border-white/5 pt-3 mt-1">
                <div className="flex flex-col items-start">
                    <span className="text-[8px] font-bold text-[#505050] uppercase">Vs</span>
                    <span className="text-[10px] font-bold text-[#808080]">
                        {loseVal.toFixed(1)}%
                    </span>
                </div>

                <div className={`px-2 py-0.5 rounded border flex items-center gap-1.5
                    ${displayRet > 0
                        ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-500'
                        : displayRet < 0
                            ? 'bg-rose-500/5 border-rose-500/20 text-rose-500'
                            : 'bg-white/5 border-white/10 text-[#606060]'
                    }
                `}>
                    {hasReturn ? (
                        <span className="text-[9px] font-mono font-bold">
                            {displayRet > 0 ? '+' : ''}{displayRet.toFixed(2)}%
                        </span>
                    ) : (
                        <span className="text-[8px] font-black uppercase tracking-widest opacity-50">Edge</span>
                    )}
                </div>
            </div>
        </div>
    );
}
