'use client';

import { useState, useMemo, useEffect } from 'react';
import { X, Maximize2, Minimize2 } from 'lucide-react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts';
import { ComparisonType } from '@/lib/candle-science/types';

interface ScatterPlotProps {
    distributions: Record<string, number[]>;
    initialType?: ComparisonType;
    onClose: () => void;
}

const COMPARISON_OPTIONS: { value: ComparisonType; label: string }[] = [
    { value: 'c3_high_vs_c2_high', label: 'C3 High vs C2 High' },
    { value: 'c3_high_vs_c2_open', label: 'C3 High vs C2 Open' },
    { value: 'c3_low_vs_c2_low', label: 'C3 Low vs C2 Low' },
    { value: 'c3_low_vs_c2_open', label: 'C3 Low vs C2 Open' },
    { value: 'c3_close_vs_c2_high', label: 'C3 Close vs C2 High' },
    { value: 'c3_close_vs_c2_low', label: 'C3 Close vs C2 Low' },
    { value: 'c3_close_vs_c2_close', label: 'C3 Close vs C2 Close' },
    { value: 'c3_close_vs_c2_open', label: 'C3 Close vs C2 Open' },
];

export function ScatterPlot({ distributions, initialType, onClose }: ScatterPlotProps) {
    const [comparisonType, setComparisonType] = useState<ComparisonType>(initialType || 'c3_high_vs_c2_high');
    const [squashOutliers, setSquashOutliers] = useState(true);

    // State for interactive lines
    const [upperBound, setUpperBound] = useState<number | null>(null);
    const [lowerBound, setLowerBound] = useState<number | null>(null);

    // 1. Raw Stats for Domain Calculation (IQR Method)
    const rawStats = useMemo(() => {
        const rawValues = distributions[comparisonType] || [];
        if (rawValues.length === 0) return null;

        const sorted = [...rawValues].sort((a, b) => a - b);
        const getP = (p: number) => sorted[Math.floor((p / 100) * (sorted.length - 1))];

        return {
            q1: getP(25),
            q3: getP(75),
            min: sorted[0],
            max: sorted[sorted.length - 1]
        };
    }, [distributions, comparisonType]);

    // 2. Determine Scale Domain using Tukey's Fences (1.5 * IQR)
    const domain = useMemo(() => {
        if (!rawStats) return [-1, 1];

        if (squashOutliers) {
            const { q1, q3 } = rawStats;
            const iqr = q3 - q1;

            // Standard statistical outlier fences
            let upperFence = q3 + (1.5 * iqr);
            let lowerFence = q1 - (1.5 * iqr);

            // Ensure fences don't cut off "normal" data if distribution is skewed or tight
            // e.g., if IQR is tiny, we still want a minimum visibility.
            // Also, fences shouldn't be narrower than the actual max if no outliers exist? 
            // Actually, clamping to fences is the definition of hiding outliers.

            // Heuristic: Ensure fences are symmetric-ish if desired, or allow asymmetry?
            // "Squash" implies bringing extremes in.
            // Let's enforce a minimum visual range for usability.
            const minRange = 1.0;
            if (upperFence - lowerFence < minRange) {
                const center = (upperFence + lowerFence) / 2;
                upperFence = center + minRange / 2;
                lowerFence = center - minRange / 2;
            }

            return [lowerFence, upperFence];
        }

        // Full Domain: Max extent + 10%
        const maxExtent = Math.max(Math.abs(rawStats.min), Math.abs(rawStats.max));
        const bound = Math.max(maxExtent * 1.1, 0.5);
        return [-bound, bound];
    }, [rawStats, squashOutliers]);

    // 3. Process Data (Clamping) & Split for Performance
    const { processedStats, positiveData, negativeData } = useMemo(() => {
        const rawValues = distributions[comparisonType] || [];
        if (rawValues.length === 0) return { processedStats: null, positiveData: [], negativeData: [] };

        const [minD, maxD] = domain;

        // Clamp and Create Data Points
        const processedValues: number[] = [];
        const posPoints: { index: number; value: number }[] = [];
        const negPoints: { index: number; value: number }[] = [];

        rawValues.forEach((val, idx) => {
            // Clamp if squashing
            let finalVal = val;
            if (squashOutliers) {
                finalVal = Math.max(minD, Math.min(maxD, val));
            }

            processedValues.push(finalVal);

            if (finalVal > 0) posPoints.push({ index: idx, value: finalVal });
            else negPoints.push({ index: idx, value: finalVal });
        });

        // Calculate Stats on PROCESSED (Clamped) values
        const sorted = [...processedValues].sort((a, b) => a - b);
        const getP = (arr: number[], p: number) => arr.length ? arr[Math.floor((p / 100) * (arr.length - 1))] : 0;

        const aboveArr = sorted.filter(v => v > 0);
        const belowArr = sorted.filter(v => v < 0);

        const stats = {
            totalCount: sorted.length,
            above: aboveArr.length ? {
                p30: getP(aboveArr, 30),
                median: getP(aboveArr, 50),
                p70: getP(aboveArr, 70),
                p90: getP(aboveArr, 90),
                count: aboveArr.length
            } : null,
            below: belowArr.length ? {
                p30: getP(belowArr, 30),
                median: getP(belowArr, 50),
                p70: getP(belowArr, 70),
                p90: getP(belowArr, 90),
                count: belowArr.length
            } : null,
            min: sorted[0],
            max: sorted[sorted.length - 1]
        };

        return { processedStats: stats, positiveData: posPoints, negativeData: negPoints };
    }, [distributions, comparisonType, domain, squashOutliers]);

    // Initialize bounds when stats load (or change comparison)
    useEffect(() => {
        if (processedStats) {
            // Default to P70s
            if (processedStats.above) setUpperBound(processedStats.above.p70);
            if (processedStats.below) setLowerBound(processedStats.below.p70);
        }
    }, [processedStats?.above?.p70, processedStats?.below?.p70]);

    // Calculate Dynamic Capture Stats
    const captureStats = useMemo(() => {
        if (!processedStats || upperBound === null || lowerBound === null) return null;

        let insideCount = 0;
        let total = 0;

        // Count from raw data (via clamp logic or source, usually source implies "reliability")
        // User wants "range I want to capture". If using clamped display, visual match is key.
        // Let's use the `positiveData` and `negativeData` since they are the display points.

        const checkPoint = (val: number) => val <= upperBound && val >= lowerBound;

        positiveData.forEach(p => { total++; if (checkPoint(p.value)) insideCount++; });
        negativeData.forEach(p => { total++; if (checkPoint(p.value)) insideCount++; });

        const pct = total > 0 ? (insideCount / total) * 100 : 0;
        return { insideCount, total, pct };
    }, [positiveData, negativeData, upperBound, lowerBound]);

    if (!processedStats) return null;

    return (
        <div className="fixed inset-0 bg-black/95 backdrop-blur-md z-[110] flex flex-col p-6 font-sans">
            <div className="flex items-center justify-between mb-6 shrink-0">
                <div className="flex items-center gap-6">
                    <h2 className="text-xl font-bold text-white flex items-center gap-3">
                        <span className="w-1.5 h-6 bg-blue-500 rounded-full" />
                        Distribution Analysis
                    </h2>
                    {/* ... Select ... */}
                    <div className="flex items-center gap-4">
                        <select
                            value={comparisonType}
                            onChange={(e) => setComparisonType(e.target.value as ComparisonType)}
                            className="bg-[#242424] border border-[#3d3d3d] rounded-lg px-3 py-1.5 text-xs font-bold text-white uppercase tracking-wider focus:outline-none"
                        >
                            {COMPARISON_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                        <button
                            onClick={() => setSquashOutliers(!squashOutliers)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest border ${squashOutliers
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500'
                                : 'bg-[#242424] border-[#3d3d3d] text-[#606060]'
                                }`}
                        >
                            {squashOutliers ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                            {squashOutliers ? 'Squashing Active' : 'Full Range'}
                        </button>
                    </div>

                    {/* Manual Range Controls */}
                    {(upperBound !== null && lowerBound !== null) && (
                        <div className="flex items-center gap-4 bg-[#242424] border border-[#3d3d3d] rounded-lg px-4 py-1.5">
                            <span className="text-[10px] uppercase font-bold text-[#808080] tracking-widest">Range</span>

                            {/* Lower Control */}
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-mono font-bold text-rose-400">{lowerBound.toFixed(2)}</span>
                                <input
                                    type="range"
                                    min={processedStats.min} max={0} step={0.05}
                                    value={lowerBound}
                                    onChange={(e) => setLowerBound(parseFloat(e.target.value))}
                                    className="w-24 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-rose-500"
                                />
                            </div>

                            <span className="text-[#404040]">|</span>

                            {/* Upper Control */}
                            <div className="flex items-center gap-2">
                                <input
                                    type="range"
                                    min={0} max={processedStats.max} step={0.05}
                                    value={upperBound}
                                    onChange={(e) => setUpperBound(parseFloat(e.target.value))}
                                    className="w-24 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                                />
                                <span className="text-xs font-mono font-bold text-emerald-400">+{upperBound.toFixed(2)}</span>
                            </div>

                            {/* Capture Stats */}
                            {captureStats && (
                                <div className="ml-2 pl-4 border-l border-[#3d3d3d] flex flex-col items-end leading-none">
                                    <span className="text-[9px] uppercase font-bold text-[#808080]">Captured</span>
                                    <span className="text-xs font-bold text-white">{captureStats.pct.toFixed(1)}%</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <button onClick={onClose} className="p-2 hover:bg-[#242424] rounded-full transition-all">
                    <X className="w-5 h-5 text-[#606060] hover:text-white" />
                </button>
            </div>

            {/* Stats Summary - Based on CLAMPED Data */}
            <div className="grid grid-cols-2 gap-8 mb-6 shrink-0">
                {/* Above Reference */}
                <div className="bg-[#1e1e1e] border border-[#2d2d2d] rounded-xl p-4 relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500" />
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-[#808080] mb-3 ml-2">Above Reference</h3>
                    <div className="grid grid-cols-4 gap-4">
                        <StatBox label="P30" value={processedStats.above?.p30} color="text-emerald-400" />
                        <StatBox label="Median" value={processedStats.above?.median} color="text-emerald-500" isHero />
                        <StatBox label="Target" value={upperBound} color="text-blue-400" />
                        <StatBox label="P90" value={processedStats.above?.p90} color="text-emerald-400" />
                    </div>
                </div>

                {/* Below Reference */}
                <div className="bg-[#1e1e1e] border border-[#2d2d2d] rounded-xl p-4 relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-1 h-full bg-rose-500" />
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-[#808080] mb-3 ml-2">Below Reference</h3>
                    <div className="grid grid-cols-4 gap-4">
                        <StatBox label="P30" value={processedStats.below?.p30} color="text-rose-400" />
                        <StatBox label="Median" value={processedStats.below?.median} color="text-rose-500" isHero />
                        <StatBox label="Target" value={lowerBound} color="text-blue-400" />
                        <StatBox label="P90" value={processedStats.below?.p90} color="text-rose-400" />
                    </div>
                </div>
            </div>

            {/* Main Chart Area */}
            <div className="flex-1 bg-[#1a1a1a] rounded-2xl border border-[#2d2d2d] p-4 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                        <XAxis
                            type="number"
                            dataKey="index"
                            name="Sample"
                            stroke="#404040"
                            fontSize={10}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            type="number"
                            dataKey="value"
                            name="Distance"
                            unit="%"
                            stroke="#404040"
                            fontSize={10}
                            domain={domain}
                            tickLine={false}
                            axisLine={false}
                        />
                        <ZAxis type="number" range={[20, 20]} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#242424', border: '1px solid #3d3d3d', borderRadius: '12px' }}
                            itemStyle={{ fontSize: '12px', fontWeight: 'bold' }}
                            cursor={{ stroke: '#404040', strokeWidth: 1 }}
                        />

                        <ReferenceLine y={0} stroke="#f59e0b" strokeWidth={2} label={{ value: 'REF', position: 'right', fill: '#f59e0b', fontSize: 10, fontWeight: 'bold' }} />

                        {/* Reference Lines from PROCESSED Stats */}
                        {processedStats.above && (
                            <>
                                <ReferenceLine y={processedStats.above.median} stroke="#10b981" strokeDasharray="5 5" strokeOpacity={0.7} label={{ value: 'MED', position: 'insideRight', fill: '#10b981', fontSize: 9 }} />
                                {/* Movable Upper Line */}
                                {upperBound !== null && (
                                    <ReferenceLine y={upperBound} stroke="#3b82f6" strokeWidth={2} strokeDasharray="5 5" label={{ value: 'TARGET', position: 'insideRight', fill: '#3b82f6', fontSize: 10, fontWeight: 'bold' }} />
                                )}
                            </>
                        )}

                        {processedStats.below && (
                            <>
                                <ReferenceLine y={processedStats.below.median} stroke="#f43f5e" strokeDasharray="5 5" strokeOpacity={0.7} label={{ value: 'MED', position: 'insideRight', fill: '#f43f5e', fontSize: 9 }} />
                                {/* Movable Lower Line */}
                                {lowerBound !== null && (
                                    <ReferenceLine y={lowerBound} stroke="#3b82f6" strokeWidth={2} strokeDasharray="5 5" label={{ value: 'TARGET', position: 'insideRight', fill: '#3b82f6', fontSize: 10, fontWeight: 'bold' }} />
                                )}
                            </>
                        )}

                        {/* Split Series for Performance - NO CELL MAPPING */}
                        <Scatter
                            name="Above"
                            data={positiveData}
                            fill="#10b981"
                            fillOpacity={0.6}
                            shape="circle"
                            isAnimationActive={false} // Disable animation for performance
                        />
                        <Scatter
                            name="Below"
                            data={negativeData}
                            fill="#f43f5e" // Rose/Red for below
                            fillOpacity={0.6}
                            shape="circle"
                            isAnimationActive={false}
                        />
                    </ScatterChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-6 flex items-center justify-center gap-12 shrink-0">
                <LegendItem color="bg-emerald-500" label="Above Reference" />
                <LegendItem color="bg-rose-500" label="Below Reference" />
                <LegendItem color="bg-amber-500" label="Baseline (0%)" />
            </div>
        </div>
    );
}

function StatBox({ label, value, color, isHero }: any) {
    if (value === undefined || value === null) return (
        <div>
            <div className="text-[9px] font-bold text-[#404040] uppercase">{label}</div>
            <div className="text-sm font-mono text-[#404040]">-</div>
        </div>
    );
    return (
        <div className="flex flex-col">
            <div className="text-[9px] font-bold text-[#606060] uppercase mb-0.5">{label}</div>
            <div className={`font-mono font-bold ${isHero ? 'text-lg' : 'text-sm'} ${color}`}>
                {value.toFixed(2)}%
            </div>
        </div>
    );
}

function LegendItem({ color, label }: { color: string; label: string }) {
    return (
        <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${color}`} />
            <span className="text-[10px] font-bold text-[#606060] uppercase tracking-widest">{label}</span>
        </div>
    );
}
