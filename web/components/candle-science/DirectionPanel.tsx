import { DirectionStats } from '@/lib/candle-science/types';

interface DirectionPanelProps {
    direction: {
        c1: DirectionStats;
        c2: DirectionStats;
        c3: DirectionStats;
    };
}

export function DirectionPanel({ direction }: DirectionPanelProps) {
    return (
        <div className="bg-[#1e1e1e]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-6 flex flex-col h-full shadow-2xl relative overflow-hidden group">
            {/* Ambient Accent */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 blur-[60px] pointer-events-none" />

            <h3 className="text-sm font-bold text-white mb-6 flex items-center gap-3 relative z-10">
                <span className="w-1.5 h-4 bg-gradient-to-b from-blue-400 to-blue-600 rounded-full" />
                Candle Direction
            </h3>

            <div className="grid grid-cols-1 gap-4 flex-1 relative z-10">
                {['c1', 'c2', 'c3'].map((key, i) => (
                    <div key={key} className="flex flex-col bg-black/30 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors shadow-inner">
                        <span className="text-[9px] font-black text-[#404040] uppercase tracking-[0.2em] mb-4">
                            Cycle {i + 1}
                        </span>

                        <div className="grid grid-cols-2 gap-6">
                            <SignalMeter label="Bull" val={direction[key as keyof typeof direction].bull} color="emerald" />
                            <SignalMeter label="Bear" val={direction[key as keyof typeof direction].bear} color="rose" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function SignalMeter({ label, val, color }: { label: string; val: number; color: 'emerald' | 'rose' }) {
    const isMain = val > 50;
    const accent = color === 'emerald' ? 'bg-emerald-500' : 'bg-rose-500';
    const text = color === 'emerald' ? 'text-emerald-400' : 'text-rose-400';
    const glow = color === 'emerald' ? 'shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'shadow-[0_0_15px_rgba(244,63,94,0.3)]';

    return (
        <div className={`flex flex-col gap-2 ${isMain ? 'opacity-100 scale-105' : 'opacity-40'} transition-all`}>
            <div className="flex justify-between items-end px-1">
                <span className={`text-[10px] font-black uppercase tracking-tighter ${text}`}>{label}</span>
                <span className={`text-xs font-mono font-bold ${text}`}>{val}%</span>
            </div>
            <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div
                    className={`h-full ${accent} ${glow} rounded-full transition-all duration-700 ease-out`}
                    style={{ width: `${val}%` }}
                />
            </div>
        </div>
    );
}
