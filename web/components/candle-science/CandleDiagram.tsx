import { CandleScienceStats, ReferenceFilters } from '@/lib/candle-science/types';
import { useMemo, useState } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

interface CandleDiagramProps {
    stats: CandleScienceStats;
    filters: ReferenceFilters;
}

export function CandleDiagram({ stats, filters }: CandleDiagramProps) {
    const [scale, setScale] = useState(1.5); // Default to 1.5x as requested

    // Coordinate System
    // ViewBox Width fixed at 1000 to maintain horizontal containment 
    // ViewBox Height scales to allow vertical growth without squishing

    // Derived Dimensions - FIXED CLIPPING & REDUCED WHITESPACE
    const DIMS = {
        candleWidth: 100 * scale,
        fontSize: 24 * scale,
        labelSize: 32 * scale,
        strokeWidth: 6 * scale,
        step: 80 * scale,
        vbw: 1600, // Widened to prevent badge clipping
        vbh: 600 + (scale * 300) // Reduced height to remove dead space
    };

    const layout = useMemo(() => {
        // Tighter vertical centering
        const centerY = (600 + (scale * 200)) / 2;

        const c1 = {
            x: 180,
            open: centerY + (40 * scale),
            close: centerY - (40 * scale),
            high: centerY - (120 * scale),
            low: centerY + (120 * scale),
            color: '#10b981'
        };

        if (filters.c1Direction === 'bear') {
            c1.open = centerY - (40 * scale);
            c1.close = centerY + (40 * scale);
            c1.color = '#f43f5e';
        }

        const c2 = {
            x: 520,
            open: c1.open,
            close: c1.close,
            high: c1.high,
            low: c1.low,
            color: '#10b981'
        };

        if (filters.c2Direction === 'bear') {
            c2.color = '#f43f5e';
        }

        const STEP = 70 * scale;

        if (filters.c2HighVsC1High === 'above') c2.high = c1.high - STEP;
        else if (filters.c2HighVsC1High === 'below') c2.high = c1.high + STEP;
        else c2.high = c1.high;

        if (filters.c2LowVsC1Low === 'above') c2.low = c1.low - STEP;
        else if (filters.c2LowVsC1Low === 'below') c2.low = c1.low + STEP;
        else c2.low = c1.low;

        if (filters.c2CloseVsC1High === 'above') {
            const target = c1.high - (30 * scale);
            if (c2.high > target) c2.high = target - (20 * scale);
        }

        const bodySize = Math.abs(c2.high - c2.low) * 0.75;
        const mid = (c2.high + c2.low) / 2;

        if (filters.c2Direction === 'bear') {
            c2.open = mid - bodySize / 2;
            c2.close = mid + bodySize / 2;
        } else {
            c2.close = mid - bodySize / 2;
            c2.open = mid + bodySize / 2;
        }

        if (filters.c2CloseVsC1High === 'above') {
            const limit = c1.high;
            if (c2.close > limit) {
                const shift = c2.close - limit + (30 * scale);
                c2.high -= shift; c2.low -= shift; c2.open -= shift; c2.close -= shift;
            }
        }

        const c3 = {
            x: 880,
            open: c2.close,
            close: c2.close - (50 * scale),
            high: c2.close - (100 * scale),
            low: c2.close + (50 * scale),
            color: stats.direction.c3.bull > 50 ? '#10b981' : '#f43f5e'
        };

        if (filters.c3OpenVsC2Close === 'above') {
            c3.open = c2.close - (80 * scale);
        } else if (filters.c3OpenVsC2Close === 'below') {
            c3.open = c2.close + (80 * scale);
        }

        if (filters.c3OpenVsC2Open === 'above') {
            if (c3.open > c2.open) c3.open = c2.open - (30 * scale);
        }

        c3.high = c3.open - (100 * scale);
        c3.close = c3.open - (50 * scale);
        c3.low = c3.open + (100 * scale);

        return { c1, c2, c3 };
    }, [filters, stats, scale]);

    return (
        <div className="bg-[#1e1e1e]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-4 flex flex-col items-center shadow-2xl relative overflow-hidden group">
            {/* Ambient Background Glow */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-emerald-500/5 blur-[100px] pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-rose-500/5 blur-[100px] pointer-events-none" />

            {/* Scale Control Header - Compact */}
            <div className="w-full flex items-center justify-between mb-2 relative z-10 px-2">
                <div className="flex flex-col">
                    <h3 className="text-sm font-black text-white flex items-center gap-3">
                        <span className="w-1 h-4 bg-emerald-500 rounded-full shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                        Probability Model
                    </h3>
                </div>

                <div className="flex items-center gap-2 bg-black/40 backdrop-blur-md rounded-lg p-1 border border-white/5">
                    <input
                        type="range"
                        min="0.5"
                        max="3.0"
                        step="0.1"
                        value={scale}
                        onChange={(e) => setScale(parseFloat(e.target.value))}
                        className="w-20 h-1 bg-[#2a2a2a] rounded-full appearance-none cursor-pointer accent-emerald-500 hover:accent-emerald-400"
                    />
                    <span className="text-[9px] font-mono text-emerald-500/80 w-8 text-center font-bold">{scale.toFixed(1)}x</span>
                </div>
            </div>

            <div className="relative w-full px-2 py-2 overflow-hidden flex justify-center">
                <svg viewBox={`0 0 ${DIMS.vbw} ${DIMS.vbh}`} className="w-full h-auto max-h-[450px] overflow-visible font-mono transition-all duration-300 ease-in-out">
                    <defs>
                        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur stdDeviation="5" result="blur" />
                            <feComposite in="SourceGraphic" in2="blur" operator="over" />
                        </filter>

                        <filter id="textShadow">
                            <feDropShadow dx="0" dy="2" stdDeviation="4" floodOpacity="0.8" />
                        </filter>

                        <linearGradient id="bullGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor="#34d399" />
                            <stop offset="100%" stopColor="#059669" />
                        </linearGradient>

                        <linearGradient id="bearGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor="#fb7185" />
                            <stop offset="100%" stopColor="#e11d48" />
                        </linearGradient>
                    </defs>

                    {/* Projections lines - High Contrast */}
                    <g className="projections">
                        <line x1={layout.c2.x} y1={layout.c2.high} x2={layout.c3.x + (220 * scale)} y2={layout.c2.high}
                            stroke="#ffffff" strokeOpacity="0.15" strokeDasharray="8,8" strokeWidth={scale * 2} />
                        <text x={layout.c3.x + (230 * scale)} y={layout.c2.high + 6} fill="#ffffff" fillOpacity="0.4" fontSize={DIMS.fontSize * 0.8} fontWeight="900"
                            className="uppercase tracking-[0.2em]" filter="url(#textShadow)">Level High</text>

                        <line x1={layout.c2.x} y1={layout.c2.close} x2={layout.c3.x + (220 * scale)} y2={layout.c2.close}
                            stroke="#ffffff" strokeOpacity="0.1" strokeDasharray="4,4" strokeWidth={scale * 2} />
                    </g>

                    {/* Candles */}
                    <Candle {...layout.c1} label="C1" dims={DIMS} />
                    <Candle {...layout.c2} label="C2" dims={DIMS} />
                    <Candle {...layout.c3} label="C3" isProjection dims={DIMS} />

                    {/* Probability Annotations - Repositioned for Clipping Fix */}
                    <g transform={`translate(${layout.c3.x + (250 * scale)}, 0)`}>
                        <ProbLabel y={layout.c2.high - (40 * scale)} label="H > H" val={stats.high_wicks.c3_vs_c2.high_vs_high.above} dims={DIMS} />
                        <ProbLabel y={layout.c2.close} label="C > C" val={stats.body.c3_vs_c2.close_vs_close.above} dims={DIMS} />
                        <ProbLabel y={layout.c2.low + (40 * scale)} label="L < L" val={stats.low_wicks.c3_vs_c2.low_vs_low.below} dims={DIMS} />
                    </g>
                </svg>
            </div>

            <div className="w-full flex justify-between items-center mt-2 opacity-30">
                <div className="text-[8px] font-black text-white uppercase tracking-[0.3em] flex items-center gap-2">
                    <Maximize2 className="w-2 h-2" />
                    Projection Meta V2.1
                </div>
                <div className="text-[8px] font-black text-white uppercase tracking-[0.3em]">
                    Sync: Active
                </div>
            </div>
        </div>
    );
}

function Candle({ x, open, close, high, low, color, label, isProjection, dims }: any) {
    const isBull = close < open;
    const bodyTop = isBull ? close : open;
    const bodyHeight = Math.abs(open - close);
    const gradId = isBull ? 'url(#bullGrad)' : 'url(#bearGrad)';

    return (
        <g transform={`translate(${x}, 0)`} className="candle-group transition-all duration-300">
            <line x1="0" y1={high} x2="0" y2={low}
                stroke={color} strokeWidth={dims.strokeWidth} strokeLinecap="round" opacity={isProjection ? 0.3 : 0.5} />
            <rect
                x={-dims.candleWidth / 2}
                y={bodyTop}
                width={dims.candleWidth}
                height={Math.max(bodyHeight, 2 * dims.strokeWidth)}
                fill={isProjection ? 'none' : gradId}
                stroke={color}
                rx={dims.strokeWidth / 3}
                strokeWidth={dims.strokeWidth / 2}
                fillOpacity={isProjection ? 0.05 : 0.8}
                filter={isProjection ? 'none' : 'url(#glow)'}
            />
            <text x="0" y={low + (50 * (dims.candleWidth / 100))} textAnchor="middle" fill="#ffffff" fillOpacity="0.2"
                fontSize={dims.labelSize} fontWeight="900" className="tracking-tighter select-none uppercase">{label}</text>
        </g>
    );
}

function ProbLabel({ y, label, val, dims }: any) {
    const isHigh = val > 50;
    const color = isHigh ? '#34d399' : '#fb7185';
    const bgColor = isHigh ? 'rgba(52, 211, 153, 0.12)' : 'rgba(251, 113, 133, 0.12)';

    return (
        <g transform={`translate(0, ${y})`} className="prob-badge">
            <rect x="-10" y="-22" width="280" height="44" rx="22" fill={bgColor} className="backdrop-blur-sm" />
            <text x="15" y="2" fill={color} fontSize={dims.fontSize * 0.75} fontWeight="900"
                dominantBaseline="middle" filter="url(#textShadow)" className="uppercase tracking-[0.2em] opacity-80">
                {label}
            </text>
            <text x="260" y="2" fill={color} fontSize={dims.fontSize} fontWeight="900"
                textAnchor="end" dominantBaseline="middle" filter="url(#textShadow)">
                {val}%
            </text>
        </g>
    );
}
