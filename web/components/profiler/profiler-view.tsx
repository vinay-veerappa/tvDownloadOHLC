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
import { HodLodAnalysis, HodLodChart, SessionStats } from './hod-lod-analysis';
import { DailyLevels } from './daily-levels';
import { LevelProbabilityWidget } from './level-probability-widget';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const AVAILABLE_TICKERS = ['NQ1'] as const; // Extensible for future tickers

interface ProfilerViewProps {
    ticker?: string;
}

export function ProfilerView({ ticker: initialTicker = "NQ1" }: ProfilerViewProps) {
    // 1. Global State
    const [ticker, setTicker] = useState(initialTicker);
    const [activeTab, setActiveTab] = useState('daily');

    // Target Session is derived from Active Tab
    // If 'daily' tab, we default to 'NY1' for context (or 'Daily'), but for filtering logic 'Daily' works if supported,
    // or we just pick 'NY1' as the "primary" session to show distribution for in the sidebar.
    // Let's use 'NY1' as default target when in 'Daily' view, or 'Daily' if backend supports it for stats.
    const targetSession = activeTab === 'daily' ? 'NY1' :
        activeTab === 'asia' ? 'Asia' :
            activeTab === 'london' ? 'London' :
                activeTab === 'ny1' ? 'NY1' : 'NY2';

    const [filters, setFilters] = useState<Record<string, string>>({});
    const [brokenFilters, setBrokenFilters] = useState<Record<string, string>>({});

    // Intra-session state is usually for "Target Session". 
    // If we removed the "Target" dropdown, we might want to allow filtering the "Target" direction in the Sidebar.
    // The Sidebar has "Direction" for *each* session.
    // So if Target is NY1, "NY1 Direction" in sidebar *is* the intra-state filter.
    // We can map `intraState` to the `filters[targetSession]` basically.
    // Actually, `intraState` in the backend logic was just an extra convenience. 
    // Using `filters[targetSession]` is equivalent to `intraState` if implemented correctly in backend.
    // Backend `apply_filters` checks `intra_state` against `target_session`.
    // It ALSO checks `filters`. So we can just use `filters`.
    // I will pass "Any" for `intraState` and rely on `filters`.
    const intraState = 'Any';

    // 2. Debounced API State (Delays fetch by 800ms to allow multi-selection)
    const debouncedTargetSession = useDebounce(targetSession, 800);
    const debouncedFilters = useDebounce(filters, 800);
    const debouncedBrokenFilters = useDebounce(brokenFilters, 800);
    const debouncedIntraState = useDebounce(intraState, 800);
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
    const deferredDistribution = useDeferredValue(distribution);
    const deferredValidSamples = useDeferredValue(validSamples);
    const deferredLevelTouches = useDeferredValue(levelTouches);
    const deferredDailyHodLod = useDeferredValue(dailyHodLod);

    // Handlers (Memoized)
    const handleFilterChange = useMemo(() => (s: string, v: string) => setFilters(prev => ({ ...prev, [s]: v })), []);
    const handleBrokenFilterChange = useMemo(() => (s: string, v: string) => setBrokenFilters(prev => ({ ...prev, [s]: v })), []);
    const handleReset = useMemo(() => () => {
        setFilters({});
        setBrokenFilters({});
    }, []);

    const sidebarStats = useMemo(() => ({ validSamples }), [validSamples]);


    // Calculate Context for Probability Widget
    // We look at the 'London' filter direction if set, or try to infer?
    // Actually, the widget expects 'Long' | 'Short' | 'None'.
    // The Sidebar filter for London is EXACTLY that direction.
    // If user filtered London='Long True' => Context is Green.
    // If 'Short True' => Red.
    // If 'None' or 'Any', it falls back to 'All'.
    const londonDirFilter = filters['London'] || '';
    const londonContext = londonDirFilter.startsWith('Long') ? 'Long' :
        londonDirFilter.startsWith('Short') ? 'Short' : 'None';

    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    if (filterError) return <div className="p-8 text-center text-red-500">Failed to load profiler data.</div>;

    return (
        <div className="flex items-start gap-4">
            {/* 1. Sidebar (Sticky) */}
            <div className={`sticky top-4 flex-none z-10 transition-all duration-300 ${isSidebarCollapsed ? 'w-[60px]' : 'w-[280px]'} space-y-4`}>
                <ProfilerFilterSidebar
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
                />

                {/* Level Probability Widget removed per user request */}
            </div>

            {/* 2. Main Content (Scrolls naturally) */}
            <div className={`flex-1 min-w-0 space-y-6 ${isFilterLoading ? 'opacity-80' : ''}`}>
                <div className="flex items-center justify-between">
                    <h1 className="text-3xl font-bold tracking-tight">Market Profiler</h1>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <TabsList className="w-full justify-start h-auto p-1 bg-muted/20">
                        <TabsTrigger value="daily" className="px-6 py-2">Daily Overview</TabsTrigger>
                        <TabsTrigger value="asia" className="px-6 py-2">Asia</TabsTrigger>
                        <TabsTrigger value="london" className="px-6 py-2">London</TabsTrigger>
                        <TabsTrigger value="ny1" className="px-6 py-2">NY1</TabsTrigger>
                        <TabsTrigger value="ny2" className="px-6 py-2">NY2</TabsTrigger>
                    </TabsList>

                    {/* --- Tab 1: Daily Overview (Memoized) --- */}
                    {useMemo(() => (
                        <TabsContent value="daily" className="mt-6 space-y-8">
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
                                <RangeDistribution sessions={deferredFilteredSessions} forcedSession="daily" />
                            </section>

                            {/* 3. Daily Price Model */}
                            <section>
                                <h2 className="text-xl font-semibold mb-4">Daily Price Model</h2>
                                <PriceModelChart
                                    ticker={debouncedTicker}
                                    session="Daily"
                                    targetSession={debouncedTargetSession} // NY1 derived
                                    filters={debouncedFilters}
                                    brokenFilters={debouncedBrokenFilters}
                                    intraState={intraState}
                                    height={400}
                                />
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
                        filteredDates
                    ])}

                    {/* --- Session Tabs (Memoized) --- */}
                    {useMemo(() => (
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
                    ])}
                </Tabs>
            </div>
        </div>
    );
}
