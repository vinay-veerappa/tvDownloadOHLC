import { ArrowUp, ArrowDown, Minus } from 'lucide-react';

interface LedgerItem {
    label: string;
    bull_val: number;
    bear_val: number;
    subLabel?: string;
    description?: string;
}

interface CycleLedgerProps {
    title: string;
    items: LedgerItem[];
    priority?: boolean;
}

export function CycleLedger({ title, items, priority = false }: CycleLedgerProps) {
    return (
        <div className={`flex flex-col rounded-2xl border backdrop-blur-xl overflow-hidden shadow-2xl transition-all duration-300 group
             ${priority
                ? 'bg-[#1e1e1e]/80 border-emerald-500/30'
                : 'bg-[#1e1e1e]/40 border-white/5'
            }`}>

            {/* Header */}
            <div className={`px-6 py-4 border-b flex items-center justify-between
                ${priority ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-white/5 bg-white/2'}
            `}>
                <div className="flex items-center gap-3">
                    <span className={`w-1.5 h-4 rounded-full ${priority ? 'bg-emerald-500' : 'bg-[#606060]'}`} />
                    <h3 className={`text-sm font-black uppercase tracking-[0.2em] ${priority ? 'text-white' : 'text-[#808080]'}`}>
                        {title}
                    </h3>
                </div>
                {priority && (
                    <span className="text-[9px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20 uppercase tracking-widest">
                        Primary Forecast
                    </span>
                )}
            </div>

            {/* Ledger Table */}
            <div className="divide-y divide-white/5">
                {items.map((item, idx) => (
                    <LedgerRow key={idx} item={item} />
                ))}
            </div>
        </div>
    );
}

function LedgerRow({ item }: { item: LedgerItem }) {
    const total = item.bull_val + item.bear_val;
    // Normalize if they assume 100%, but usually they sum to 100 roughly. 
    // If "Both > 50" (excursions), logic is different, but user data seems to be prob distributions.

    // Calculate Edge
    const edge = item.bull_val - item.bear_val;
    const isBullFavored = edge > 0;
    const absEdge = Math.abs(edge);

    // Dynamic Opacity for non-favored side
    const bullOpacity = isBullFavored || Math.abs(edge) < 5 ? 1 : 0.4;
    const bearOpacity = !isBullFavored || Math.abs(edge) < 5 ? 1 : 0.4;

    return (
        <div className="grid grid-cols-12 gap-4 px-6 py-4 hover:bg-white/2 transition-colors items-center group">
            {/* 1. Label Section (Cols 1-4) - NO CLIPPING */}
            <div className="col-span-4 flex flex-col justify-center">
                <span className="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors uppercase tracking-tight">
                    {item.label}
                </span>
                {item.subLabel && (
                    <span className="text-[10px] font-medium text-[#606060] uppercase tracking-widest mt-0.5">
                        {item.subLabel}
                    </span>
                )}
            </div>

            {/* 2. The Battle Bar (Cols 5-9) - VISUAL INTUITION */}
            <div className="col-span-5 flex items-center gap-2">
                {/* Bear Side */}
                <span className={`text-[10px] font-mono font-bold text-rose-500 w-8 text-right transition-opacity duration-300`} style={{ opacity: bearOpacity }}>
                    {item.bear_val.toFixed(1)}%
                </span>

                {/* Bar */}
                <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden flex relative">
                    {/* Center Marker */}
                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#404040] z-10" />

                    {/* Bear Fill (Right to Left from center effectively, but we use flex) */}
                    {/* Actually, simpler: Bull % width */}
                    <div
                        className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-500"
                        style={{ width: `${item.bull_val}%` }}
                    />
                    <div className="flex-1 bg-[#2a2a2a]" />
                    {/* Note: This assumes Bull% + Bear% ~= 100%. If not, we might need normalization */}
                </div>

                {/* Bull Side */}
                <span className={`text-[10px] font-mono font-bold text-emerald-500 w-8 transition-opacity duration-300`} style={{ opacity: bullOpacity }}>
                    {item.bull_val.toFixed(1)}%
                </span>
            </div>

            {/* 3. The Signal / Edge (Cols 10-12) - THE "ANSWER" */}
            <div className="col-span-3 flex justify-end">
                <div className={`px-3 py-1.5 rounded-lg border flex items-center gap-2 w-24 justify-between
                    ${isBullFavored
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                        : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                    } ${absEdge < 2 ? 'opacity-50 grayscale' : 'opacity-100'}
                `}>
                    <span className="text-[9px] font-black uppercase tracking-widest">Edge</span>
                    <span className="text-[10px] font-mono font-bold">
                        {absEdge < 0.1 ? '0.0' : absEdge.toFixed(1)}%
                    </span>
                </div>
            </div>
        </div>
    );
}
