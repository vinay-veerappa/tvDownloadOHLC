"use client"

import { useState, useMemo, useDeferredValue } from 'react';
import { useServerFilteredStats } from '@/hooks/use-server-filtered-stats';
import { useLevelTouches } from '@/hooks/use-level-touches';
import { useDailyHodLod } from '@/hooks/use-daily-hod-lod';
import { SESSION_ORDER } from '@/hooks/use-profiler-filter';
import { useDebounce } from '@/hooks/use-debounce'; // New Hook

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfilerFilterSidebar } from './profiler-filter-sidebar';
import { SessionAnalysisView } from './session-analysis-view';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
import { PriceModelGrid } from './price-model-grid';
import { HodLodAnalysis, HodLodChart, SessionStats } from './hod-lod-analysis';
import { DailyLevels } from './daily-levels';
import { LevelProbabilityWidget } from './level-probability-widget';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const AVAILABLE_TICKERS = ['NQ1', 'ES1', 'CL1', 'GC1', 'RTY1', 'YM1'] as const; // Extensible for future tickers

interface ProfilerViewProps {
    ticker?: string;
}

export function ProfilerView({ ticker: initialTicker = "NQ1" }: ProfilerViewProps) {
    // 1. Global State
    const [ticker, setTicker] = useState(initialTicker);
    const [activeTab, setActiveTab] = useState('daily');
    const [targetSession, setTargetSession] = useState('NY1'); // Standalone state now!

    const [filters, setFilters] = useState<Record<string, string>>({});
    const [brokenFilters, setBrokenFilters] = useState<Record<string, string>>({});

    // Intra-session state
    const intraState = 'Any';

    // 2. Debounced API State (Delays fetch by 800ms to allow multi-selection)
    const debouncedTargetSession = useDebounce(targetSession, 800);
    const debouncedFilters = useDebounce(filters, 800);
    const debouncedBrokenFilters = useDebounce(brokenFilters, 800);
    const debouncedTicker = useDebounce(ticker, 800);

    // 3. Server-Side Filtered Data
    const {
        filteredDates,
        filteredSessions,
        distribution,
        validSamples,
        isLoading: isFilterLoading,
        error: filterError
    } = useServerFilteredStats({
        ticker: debouncedTicker,
        targetSession: debouncedTargetSession,
        filters: debouncedFilters,
        brokenFilters: debouncedBrokenFilters,
        intraState: intraState
    });

    // 4. Other Data Fetching
    const { levelTouches } = useLevelTouches(debouncedTicker);
    const { dailyHodLod } = useDailyHodLod(debouncedTicker);

    // 5. Deferred Data for Heavy Charts (Unblocks UI during rendering)
    const deferredFilteredSessions = useDeferredValue(filteredSessions);
    const deferredLevelTouches = useDeferredValue(levelTouches);
    const deferredDailyHodLod = useDeferredValue(dailyHodLod);

    // 6. UI State
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    // Handlers (Memoized)
    const handleFilterChange = useMemo(() => (s: string, v: string) => setFilters(prev => ({ ...prev, [s]: v })), []);
    const handleBrokenFilterChange = useMemo(() => (s: string, v: string) => setBrokenFilters(prev => ({ ...prev, [s]: v })), []);
    const handleReset = useMemo(() => () => {
        setFilters({});
        setBrokenFilters({});
    }, []);

    const sidebarStats = useMemo(() => ({ validSamples }), [validSamples]);

    // --- Prediction / Distribution Chart Logic ---
    const distributionChartData = useMemo(() => {
        if (!distribution || Object.keys(distribution).length === 0) return [];

        const total = Object.values(distribution).reduce((sum, count) => sum + count, 0);
        if (total === 0) return [];

        return Object.entries(distribution)
            .map(([status, count]) => {
                const parts = status.split(' ');
                return {
                    outcome_label: status,
                    direction: parts[0] || 'Unknown',
                    count,
                    percent: (count / total) * 100
                };
            })
            .sort((a, b) => {
                // Same sorting logic as PredictionPanel: Group by Direction, then Value
                if (a.direction === b.direction) return b.percent - a.percent;
                if (a.direction === 'Long') return -1;
                if (b.direction === 'Long') return 1;
                if (a.direction === 'Short') return -1;
                if (b.direction === 'Short') return 1;
                return 0;
            });
    }, [distribution]);

    const maxProb = distributionChartData.length > 0 ? Math.max(...distributionChartData.map(d => d.percent)) : 100;

    // --- Memoized Tab Content ---
    const dailyTabContent = useMemo(() => (
        <TabsContent value="daily" className="mt-6 space-y-8">
            
            {/* 0. NEW: Outcome Probabilities (Prediction replacement) */}
            {distributionChartData.length > 0 && (
                <section>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-semibold">
                            Outcome Probabilities for <span className="text-primary">{debouncedTargetSession}</span>
                        </h2>
                    </div>
                    <Card className="bg-card border-border">
                        <CardContent className="p-6">
                            <div className="h-[300px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={distributionChartData} layout="vertical" margin={{ left: 80, right: 40, top: 10, bottom: 10 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" horizontal={true} vertical={false} />
                                        <XAxis 
                                            type="number" 
                                            domain={[0, Math.ceil(maxProb / 10) * 10]} 
                                            hide 
                                        />
                                        <YAxis 
                                            type="category" 
                                            dataKey="outcome_label" 
                                            stroke="#ffffff60" 
                                            fontSize={12}
                                            width={80}
                                        />
                                        <Tooltip 
                                            cursor={{ fill: '#ffffff05' }}
                                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #ffffff10', borderRadius: '8px' }}
                                            itemStyle={{ color: '#fff' }}
                                            formatter={(value: number, name: string, props: any) => [
                                                `${value.toFixed(1)}% (${props.payload.count} occur.)`, 
                                                'Probability'
                                            ]}
                                        />
                                        <Bar dataKey="percent" radius={[0, 4, 4, 0]} barSize={24}>
                                            {distributionChartData.map((entry, index) => (
                                                <Cell 
                                                    key={`cell-${index}`} 
                                                    fill={
                                                        entry.direction === 'Long' ? 'rgba(52, 211, 153, 0.6)' : 
                                                        entry.direction === 'Short' ? 'rgba(251, 113, 133, 0.6)' : 
                                                        'rgba(156, 163, 175, 0.4)'
                                                    }
                                                />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </CardContent>
                    </Card>
                </section>
            )}

            {/* 1. HOD/LOD Time Analysis */}
            <section>
                <h2 className="text-xl font-semibold mb-4">HOD/LOD Time Analysis</h2>
                <HodLodChart
                    sessions={deferredFilteredSessions}
                    dailyHodLod={deferredDailyHodLod}
                />
            </section>

            {/* 2. Global Price Range Distribution */}
            <section>
                <h2 className="text-xl font-semibold mb-4">Global Price Range Distribution</h2>
                <RangeDistribution sessions={deferredFilteredSessions} forcedSession="daily" dailyHodLod={deferredDailyHodLod} />
            </section>

            {/* 3. Daily Price Model */}
            <section>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold">Price Models</h2>
                </div>

                <div className="space-y-8">
                    {/* 3.1 Aggregate Daily Model */}
                    <div className="space-y-2">
                        <h4 className="text-sm font-semibold opacity-70">Daily Aggregate</h4>
                        <PriceModelChart
                            ticker={debouncedTicker}
                            session="Daily"
                            targetSession={debouncedTargetSession}
                            filters={debouncedFilters}
                            brokenFilters={debouncedBrokenFilters}
                            intraState={intraState}
                            height={400}
                        />
                    </div>

                    {/* 3.2 Session Breakdowns (Grid) */}
                    <div className="space-y-2">
                        <h4 className="text-sm font-semibold opacity-70">Session Breakdown</h4>
                        <PriceModelGrid
                            ticker={debouncedTicker}
                            targetSession={debouncedTargetSession}
                            filters={debouncedFilters}
                            brokenFilters={debouncedBrokenFilters}
                            intraState={intraState}
                        />
                    </div>
                </div>
            </section>

            {/* 4. Daily Levels Analysis */}
            <section>
                <h2 className="text-xl font-semibold mb-4">Daily Levels Analysis</h2>
                <DailyLevels
                    levelTouches={deferredLevelTouches}
                    filteredDates={filteredDates}
                />
            </section>

            {/* 5. Session Contribution Stats */}
            <section>
                <h2 className="text-xl font-semibold mb-4">Session HOD/LOD Contribution</h2>
                <SessionStats sessions={deferredFilteredSessions} />
            </section>
        </TabsContent>
    ), [
        deferredFilteredSessions,
        deferredDailyHodLod,
        debouncedTicker,
        debouncedTargetSession,
        debouncedFilters,
        debouncedBrokenFilters,
        intraState,
        deferredLevelTouches,
        filteredDates,
        distributionChartData,
        maxProb
    ]);

    const sessionTabsContent = useMemo(() => (
        <>
            {['asia', 'london', 'ny1', 'ny2'].map(sessKey => {
                const sessName = sessKey === 'asia' ? 'Asia' : sessKey === 'london' ? 'London' : sessKey === 'ny1' ? 'NY1' : 'NY2';
                return (
                    <TabsContent key={sessKey} value={sessKey} className="mt-6">
                        <SessionAnalysisView
                            session={sessName}
                            sessions={deferredFilteredSessions}
                            allSessions={deferredFilteredSessions}
                            dailyHodLod={deferredDailyHodLod || null}
                            filteredDates={filteredDates}
                            ticker={debouncedTicker}
                            levelTouches={deferredLevelTouches}
                            filters={debouncedFilters}
                            brokenFilters={debouncedBrokenFilters}
                            intraState={intraState}
                        />
                    </TabsContent>
                );
            })}
        </>
    ), [
        deferredFilteredSessions,
        deferredDailyHodLod,
        filteredDates,
        debouncedTicker,
        deferredLevelTouches,
        debouncedFilters,
        debouncedBrokenFilters,
        intraState
    ]);

    if (filterError) return <div className="p-8 text-center text-red-500">Failed to load profiler data.</div>;

    return (
        <div className="flex items-start gap-4 h-full">
            {/* 1. Sidebar (Sticky) with fixed height for independent scrolling */}
            <div className={`sticky top-4 flex-none z-10 transition-all duration-300 ${isSidebarCollapsed ? 'w-[60px]' : 'w-[280px]'} h-[calc(100vh-2rem)] space-y-4`}>
                <ProfilerFilterSidebar
                    // Standard Props
                    stats={sidebarStats}
                    filters={filters}
                    brokenFilters={brokenFilters}
                    onFilterChange={handleFilterChange}
                    onBrokenFilterChange={handleBrokenFilterChange}
                    onReset={handleReset}
                    ticker={ticker}
                    onTickerChange={setTicker}
                    isCollapsed={isSidebarCollapsed}
                    onToggleCollapse={setIsSidebarCollapsed}
                    
                    // Target Session
                    targetSession={targetSession}
                    onTargetSessionChange={setTargetSession}
                />
            </div>

            {/* 2. Main Content (Scrolls naturally) */}
            <div className={`flex-1 min-w-0 space-y-6 ${isFilterLoading ? 'opacity-80' : ''}`}>
                <div className="flex items-center justify-between">
                    <h1 className="text-3xl font-bold tracking-tight">Market Profiler</h1>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <TabsList className="w-full justify-start h-auto p-1 bg-muted">
                        <TabsTrigger value="daily" className="px-6 py-2">Daily Overview</TabsTrigger>
                        <TabsTrigger value="asia" className="px-6 py-2">Asia</TabsTrigger>
                        <TabsTrigger value="london" className="px-6 py-2">London</TabsTrigger>
                        <TabsTrigger value="ny1" className="px-6 py-2">NY1</TabsTrigger>
                        <TabsTrigger value="ny2" className="px-6 py-2">NY2</TabsTrigger>
                    </TabsList>

                    {/* --- Tab 1: Daily Overview (Memoized) --- */}
                    {dailyTabContent}

                    {/* --- Session Tabs (Memoized) --- */}
                    {sessionTabsContent}
                </Tabs>
            </div>
        </div>
    );
}
