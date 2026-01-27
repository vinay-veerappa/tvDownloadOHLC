'use client';

import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '@/components/candle-science/Sidebar';
import { Header } from '@/components/candle-science/Header';
import { ExportModal } from '@/components/candle-science/ExportModal';
import { ScatterPlot } from '@/components/candle-science/ScatterPlot';
import { CandleDiagram } from '@/components/candle-science/CandleDiagram';
// New Ledger Component
import { SignalCardGrid } from '@/components/candle-science/SignalCardGrid';
import {
    CandleScienceStats,
    ReferenceFilters,
    ComparisonType
    // ... other types
} from '@/lib/candle-science/types';
import { Loader2, Filter } from 'lucide-react';

export default function CandleSciencePage() {
    const [ticker, setTicker] = useState('NQ1');
    const [timeframe, setTimeframe] = useState('1d');
    const [years, setYears] = useState<string[]>([]);
    const [months, setMonths] = useState<number[]>([]);
    const [daysOfWeek, setDaysOfWeek] = useState<number[]>([]);
    const [c1OpenHours, setC1OpenHours] = useState<number[]>([]);
    const [referenceFilters, setReferenceFilters] = useState<ReferenceFilters>({
        c1Direction: 'all',
        c2Direction: 'all',
        c2HighVsC1High: 'all',
        c2HighVsC1Low: 'all',
        c2LowVsC1Low: 'all',
        c2LowVsC1High: 'all',
        c2CloseVsC1High: 'all',
        c2CloseVsC1Low: 'all',
        c2CloseVsC1Close: 'all',
        c2CloseVsC1Open: 'all',
        c2OpenVsC1Close: 'all',
        c2OpenVsC1Open: 'all',
        c3OpenVsC2High: 'all',
        c3OpenVsC2Low: 'all',
        c3OpenVsC2Close: 'all',
        c3OpenVsC2Open: 'all'
    });

    const [stats, setStats] = useState<CandleScienceStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [showExport, setShowExport] = useState(false);
    const [showScatter, setShowScatter] = useState(false);
    const [scatterType, setScatterType] = useState<ComparisonType>('c3_high_vs_c2_high');

    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/candle-science/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker,
                    timeframe,
                    filters: {
                        years,
                        months,
                        daysOfWeek,
                        c1OpenHours,
                        ...referenceFilters
                    }
                })
            });
            const data = await res.json();
            setStats(data);
        } catch (error) {
            console.error('Failed to fetch stats:', error);
        } finally {
            setLoading(false);
        }
    }, [ticker, timeframe, years, months, daysOfWeek, c1OpenHours, referenceFilters]);

    useEffect(() => {
        fetchStats();
    }, [fetchStats]);

    const resetFilters = () => {
        setYears([]);
        setMonths([]);
        setDaysOfWeek([]);
        setC1OpenHours([]);
        setReferenceFilters({
            c1Direction: 'all',
            c2Direction: 'all',
            c2HighVsC1High: 'all',
            c2HighVsC1Low: 'all',
            c2LowVsC1Low: 'all',
            c2LowVsC1High: 'all',
            c2CloseVsC1High: 'all',
            c2CloseVsC1Low: 'all',
            c2CloseVsC1Close: 'all',
            c2CloseVsC1Open: 'all',
            c2OpenVsC1Close: 'all',
            c2OpenVsC1Open: 'all',
            c3OpenVsC2High: 'all',
            c3OpenVsC2Low: 'all',
            c3OpenVsC2Close: 'all',
            c3OpenVsC2Open: 'all'
        });
    };

    return (
        <div className="flex min-h-screen w-full bg-[#121212] font-sans text-gray-200">
            {/* Sidebar with sticky positioning handled internally */}
            <Sidebar
                ticker={ticker}
                setTicker={setTicker}
                timeframe={timeframe}
                setTimeframe={setTimeframe}
                years={years}
                setYears={setYears}
                months={months}
                setMonths={setMonths}
                daysOfWeek={daysOfWeek}
                setDaysOfWeek={setDaysOfWeek}
                c1OpenHours={c1OpenHours}
                setC1OpenHours={setC1OpenHours}
                referenceFilters={referenceFilters}
                setReferenceFilters={setReferenceFilters}
                resetFilters={resetFilters}
                isCollapsed={isSidebarCollapsed}
                onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            />

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 bg-[#0a0a0a] relative overflow-hidden transition-all duration-300">
                {/* Cinema Gradient Overlays */}
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,0.03),transparent)] pointer-events-none" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.03] mix-blend-overlay pointer-events-none" />

                <Header
                    ticker={ticker}
                    timeframe={timeframe}
                    sampleCount={stats?.sample_count ?? 0}
                    onExport={() => setShowExport(true)}
                    onReset={resetFilters}
                />

                <main className="flex-1 overflow-y-auto overflow-x-hidden p-6 scrollbar-thin scrollbar-thumb-white/5">
                    <div className="max-w-[1600px] mx-auto space-y-6 relative z-10">
                        {loading ? (
                            <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
                                <Loader2 className="w-12 h-12 text-emerald-500 animate-spin" />
                                <span className="text-sm font-bold text-[#606060] uppercase tracking-widest">Processing Data...</span>
                            </div>
                        ) : stats && stats.sample_count > 0 ? (
                            <div className="flex flex-col gap-6">
                                {/* Top Section: Diagram + Main Direction Side-by-Side on XL */}
                                <div className="grid grid-cols-1 2xl:grid-cols-3 gap-6">
                                    <div className="2xl:col-span-2">
                                        <CandleDiagram stats={stats} filters={referenceFilters} />
                                    </div>
                                    <SignalCardGrid
                                        title="Candle Trend Probability"
                                        gridCols="grid-cols-3"
                                        items={[
                                            {
                                                bullLabel: "Bullish Trend (C1)",
                                                bearLabel: "Bearish Trend (C1)",
                                                bullSubLabel: "History Favors Bulls",
                                                bearSubLabel: "History Favors Bears",
                                                bull_val: stats.direction.c1.bull,
                                                bear_val: stats.direction.c1.bear
                                            },
                                            {
                                                bullLabel: "Bullish Context (C2)",
                                                bearLabel: "Bearish Context (C2)",
                                                bullSubLabel: "Setup Favors Bulls",
                                                bearSubLabel: "Setup Favors Bears",
                                                bull_val: stats.direction.c2.bull,
                                                bear_val: stats.direction.c2.bear
                                            },
                                            {
                                                bullLabel: "Bullish Target (C3)",
                                                bearLabel: "Bearish Target (C3)",
                                                bullSubLabel: "Projection Favors Bulls",
                                                bearSubLabel: "Projection Favors Bears",
                                                bull_val: stats.direction.c3.bull,
                                                bear_val: stats.direction.c3.bear
                                            }
                                        ]}
                                    />
                                </div>

                                <div className="h-full space-y-6 overflow-y-auto pr-2">
                                    <SignalCardGrid
                                        title="Candle 3 Projections"
                                        gridCols="grid-cols-2 xl:grid-cols-4"
                                        onOpenScatter={(key) => {
                                            setScatterType(key);
                                            setShowScatter(true);
                                        }}
                                        items={[
                                            {
                                                bullLabel: "New High",
                                                bearLabel: "Lower High",
                                                bullSubLabel: "C3 High > C2 High",
                                                bearSubLabel: "C3 High < C2 High",
                                                bull_val: stats.high_wicks.c3_vs_c2.high_vs_high.above,
                                                bear_val: stats.high_wicks.c3_vs_c2.high_vs_high.below,
                                                bull_return: stats.high_wicks.c3_vs_c2.high_vs_high.aboveStats.median,
                                                bear_return: stats.high_wicks.c3_vs_c2.high_vs_high.belowStats.median,
                                                comparisonKey: 'c3_high_vs_c2_high'
                                            },
                                            {
                                                bullLabel: "High vs Open",
                                                bearLabel: "Below Open",
                                                bullSubLabel: "C3 High > C2 Open",
                                                bearSubLabel: "C3 High < C2 Open",
                                                bull_val: stats.high_wicks.c3_vs_c2.high_vs_open.above,
                                                bear_val: stats.high_wicks.c3_vs_c2.high_vs_open.below,
                                                bull_return: stats.high_wicks.c3_vs_c2.high_vs_open.aboveStats.median,
                                                bear_return: stats.high_wicks.c3_vs_c2.high_vs_open.belowStats.median,
                                                comparisonKey: 'c3_high_vs_c2_open'
                                            },
                                            {
                                                bullLabel: "Higher Low",
                                                bearLabel: "New Low",
                                                bullSubLabel: "C3 Low > C2 Low",
                                                bearSubLabel: "C3 Low < C2 Low",
                                                bull_val: stats.low_wicks.c3_vs_c2.low_vs_low.above,
                                                bear_val: stats.low_wicks.c3_vs_c2.low_vs_low.below,
                                                bull_return: stats.low_wicks.c3_vs_c2.low_vs_low.aboveStats.median,
                                                bear_return: stats.low_wicks.c3_vs_c2.low_vs_low.belowStats.median,
                                                comparisonKey: 'c3_low_vs_c2_low'
                                            },
                                            {
                                                bullLabel: "Low vs Open",
                                                bearLabel: "Below Open",
                                                bullSubLabel: "C3 Low > C2 Open",
                                                bearSubLabel: "C3 Low < C2 Open",
                                                bull_val: stats.low_wicks.c3_vs_c2.low_vs_open.above,
                                                bear_val: stats.low_wicks.c3_vs_c2.low_vs_open.below,
                                                bull_return: stats.low_wicks.c3_vs_c2.low_vs_open.aboveStats.median,
                                                bear_return: stats.low_wicks.c3_vs_c2.low_vs_open.belowStats.median,
                                                comparisonKey: 'c3_low_vs_c2_open'
                                            },
                                            {
                                                bullLabel: "Higher Close",
                                                bearLabel: "Lower Close",
                                                bullSubLabel: "C3 Close > C2 Close",
                                                bearSubLabel: "C3 Close < C2 Close",
                                                bull_val: stats.body.c3_vs_c2.close_vs_close.above,
                                                bear_val: stats.body.c3_vs_c2.close_vs_close.below,
                                                bull_return: stats.body.c3_vs_c2.close_vs_close.aboveStats.median,
                                                bear_return: stats.body.c3_vs_c2.close_vs_close.belowStats.median,
                                                comparisonKey: 'c3_close_vs_c2_close'
                                            },
                                            {
                                                bullLabel: "Close > High",
                                                bearLabel: "Close < High",
                                                bullSubLabel: "C3 Close > C2 High",
                                                bearSubLabel: "C3 Close < C2 High",
                                                bull_val: stats.body.c3_vs_c2.close_vs_high.above,
                                                bear_val: stats.body.c3_vs_c2.close_vs_high.below,
                                                bull_return: stats.body.c3_vs_c2.close_vs_high.aboveStats.median,
                                                bear_return: stats.body.c3_vs_c2.close_vs_high.belowStats.median,
                                                comparisonKey: 'c3_close_vs_c2_high'
                                            },
                                            {
                                                bullLabel: "Close > Low",
                                                bearLabel: "Close < Low",
                                                bullSubLabel: "C3 Close > C2 Low",
                                                bearSubLabel: "C3 Close < C2 Low",
                                                bull_val: stats.body.c3_vs_c2.close_vs_low.above,
                                                bear_val: stats.body.c3_vs_c2.close_vs_low.below,
                                                bull_return: stats.body.c3_vs_c2.close_vs_low.aboveStats.median,
                                                bear_return: stats.body.c3_vs_c2.close_vs_low.belowStats.median,
                                                comparisonKey: 'c3_close_vs_c2_low'
                                            },
                                            {
                                                bullLabel: "Gap Up",
                                                bearLabel: "Gap Down",
                                                bullSubLabel: "C3 Open > C2 Close",
                                                bearSubLabel: "C3 Open < C2 Close",
                                                bull_val: stats.gaps.c3_vs_c2.open_vs_close.above,
                                                bear_val: stats.gaps.c3_vs_c2.open_vs_close.below
                                            }
                                        ]}
                                    />
                                </div>

                                {/* Secondary Row: Context (C2) & Direction */}
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 pb-12">
                                    <SignalCardGrid
                                        title="Candle 2 Context (Signal)"
                                        gridCols="grid-cols-2"
                                        items={[
                                            {
                                                bullLabel: "New High",
                                                bearLabel: "Lower High",
                                                bullSubLabel: "C2 High > C1 High",
                                                bearSubLabel: "C2 High < C1 High",
                                                bull_val: stats.high_wicks.c2_vs_c1.high_vs_high.above,
                                                bear_val: stats.high_wicks.c2_vs_c1.high_vs_high.below
                                            },
                                            {
                                                bullLabel: "Higher Low",
                                                bearLabel: "New Low",
                                                bullSubLabel: "C2 Low > C1 Low",
                                                bearSubLabel: "C2 Low < C1 Low",
                                                bull_val: stats.low_wicks.c2_vs_c1.low_vs_low.above,
                                                bear_val: stats.low_wicks.c2_vs_c1.low_vs_low.below
                                            },
                                            {
                                                bullLabel: "Bullish Close",
                                                bearLabel: "Weak Close",
                                                bullSubLabel: "C2 Close > C1 High",
                                                bearSubLabel: "C2 Close < C1 High",
                                                bull_val: stats.body.c2_vs_c1.close_vs_high.above,
                                                bear_val: stats.body.c2_vs_c1.close_vs_high.below
                                            },
                                            {
                                                bullLabel: "Gap Up",
                                                bearLabel: "Gap Down",
                                                bullSubLabel: "C2 Open > C1 Close",
                                                bearSubLabel: "C2 Open < C1 Close",
                                                bull_val: stats.gaps.c2_vs_c1.open_vs_close.above,
                                                bear_val: stats.gaps.c2_vs_c1.open_vs_close.below
                                            }
                                        ]}
                                    />
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-[60vh] text-center gap-6">
                                <div className="w-20 h-20 bg-[#1a1a1a] rounded-full flex items-center justify-center border border-[#2d2d2d]">
                                    <Filter className="w-8 h-8 text-[#404040]" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-bold text-white mb-2">Insufficient Relationship Data</h2>
                                    <p className="text-sm text-[#606060] max-w-sm">The current filter criteria are too restrictive for this timeframe. Try broadening your temporal range or removing relationship constraints.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </main>
            </div >

            {/* Overlays */}
            {
                showExport && stats && (
                    <ExportModal
                        stats={stats}
                        onClose={() => setShowExport(false)}
                    />
                )
            }

            {
                showScatter && stats && (
                    <ScatterPlot
                        distributions={stats.distributions}
                        initialType={scatterType}
                        onClose={() => setShowScatter(false)}
                    />
                )
            }
        </div >
    );
}

