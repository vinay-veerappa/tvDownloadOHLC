"use client"

import { useState, useMemo } from 'react';
import { useServerFilteredStats } from '@/hooks/use-server-filtered-stats';
import { useLevelTouches } from '@/hooks/use-level-touches';
import { useDailyHodLod } from '@/hooks/use-daily-hod-lod';
import { SESSION_ORDER } from '@/hooks/use-profiler-filter';

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfilerWizard } from './profiler-wizard';
import { ActiveFiltersRow } from './active-filters-row';
import { SessionAnalysisView } from './session-analysis-view';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
import { HodLodAnalysis, HodLodChart, SessionStats } from './hod-lod-analysis';
import { DailyLevels } from './daily-levels';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const AVAILABLE_TICKERS = ['NQ1'] as const; // Extensible for future tickers

interface ProfilerViewProps {
    ticker?: string;
}

export function ProfilerView({ ticker: initialTicker = "NQ1" }: ProfilerViewProps) {
    // 1. Global State
    const [ticker, setTicker] = useState(initialTicker);
    const [targetSession, setTargetSession] = useState('NY1'); // "Context Target" for Wizard
    const [filters, setFilters] = useState<Record<string, string>>({});
    const [brokenFilters, setBrokenFilters] = useState<Record<string, string>>({});
    const [intraState, setIntraState] = useState('Any');

    // 2. Compute context sessions (sessions before target)
    const contextSessions = useMemo(() => {
        const idx = SESSION_ORDER.indexOf(targetSession);
        return idx === -1 ? [] : SESSION_ORDER.slice(0, idx);
    }, [targetSession]);

    // 3. Server-Side Filtered Data (uses backend filter endpoints)
    const {
        filteredDates,
        filteredSessions,  // Server-side filtered sessions - no need to fetch all!
        distribution,
        validSamples,
        isLoading: isFilterLoading,
        error: filterError
    } = useServerFilteredStats({
        ticker,
        targetSession,
        filters,
        brokenFilters,
        intraState
    });

    // 4. Other Data Fetching
    const { levelTouches } = useLevelTouches(ticker);
    const { dailyHodLod } = useDailyHodLod(ticker);

    if (filterError) return <div className="p-8 text-center text-red-500">Failed to load profiler data.</div>;
    if (isFilterLoading) return <div className="p-8 text-center text-muted-foreground">Loading...</div>;

    // Reset Handlers
    const handleReset = () => {
        setFilters({});
        setBrokenFilters({});
        setIntraState('Any');
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500 pb-20">
            <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                    <h1 className="text-3xl font-bold tracking-tight">Market Profiler</h1>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Ticker:</span>
                        <Select value={ticker} onValueChange={setTicker}>
                            <SelectTrigger className="w-[100px] h-8">
                                <SelectValue placeholder="Select ticker" />
                            </SelectTrigger>
                            <SelectContent>
                                {AVAILABLE_TICKERS.map(t => (
                                    <SelectItem key={t} value={t}>{t}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* 1. Profiler Wizard (Controls Global Filters) */}
                <ProfilerWizard
                    targetSession={targetSession}
                    filters={filters}
                    brokenFilters={brokenFilters}
                    intraSessionState={intraState}
                    contextSessions={contextSessions}
                    stats={{ validSamples, distribution }}
                    onTargetChange={setTargetSession}
                    onFilterChange={(s, v) => setFilters(prev => ({ ...prev, [s]: v }))}
                    onBrokenFilterChange={(s, v) => setBrokenFilters(prev => ({ ...prev, [s]: v }))}
                    onIntraStateChange={setIntraState}
                    onReset={handleReset}
                />

                {/* 2. Active Filters Display */}
                <ActiveFiltersRow
                    filters={filters}
                    brokenFilters={brokenFilters}
                    intraSessionState={intraState}
                    onClearAll={handleReset}
                />
            </div>

            {/* 3. Main Tabs */}
            <Tabs defaultValue="daily" className="w-full">
                <TabsList className="w-full justify-start h-auto p-1 bg-muted/20">
                    <TabsTrigger value="daily" className="px-6 py-2">Daily Overview</TabsTrigger>
                    <TabsTrigger value="asia" className="px-6 py-2">Asia</TabsTrigger>
                    <TabsTrigger value="london" className="px-6 py-2">London</TabsTrigger>
                    <TabsTrigger value="ny1" className="px-6 py-2">NY1</TabsTrigger>
                    <TabsTrigger value="ny2" className="px-6 py-2">NY2</TabsTrigger>
                </TabsList>

                {/* --- Tab 1: Daily Overview --- */}
                <TabsContent value="daily" className="mt-6 space-y-8">

                    {/* 1. HOD/LOD Time Analysis (Moved to Top) */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">HOD/LOD Time Analysis</h2>
                        <HodLodChart
                            sessions={filteredSessions}
                            dailyHodLod={dailyHodLod}
                        />
                    </section>

                    {/* 2. Global Price Range Distribution */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Global Price Range Distribution</h2>
                        <RangeDistribution sessions={filteredSessions} forcedSession="daily" />
                    </section>

                    {/* 3. Daily Price Model (Median, Full Day) */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Daily Price Model (Median)</h2>
                        <PriceModelChart
                            ticker={ticker}
                            session="Daily"
                            targetSession={targetSession}
                            filters={filters}
                            brokenFilters={brokenFilters}
                            intraState={intraState}
                            height={400}
                        />
                    </section>

                    {/* 4. Daily Levels Analysis */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Daily Levels Analysis</h2>
                        <DailyLevels
                            levelTouches={levelTouches}
                            filteredDates={filteredDates}
                        // No limitLevels = Show all
                        />
                    </section>

                    {/* 5. Session Contribution Stats (Moved to Bottom) */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Session HOD/LOD Contribution</h2>
                        <SessionStats sessions={filteredSessions} />
                    </section>
                </TabsContent>

                {/* --- Session Tabs --- */}
                <TabsContent value="asia" className="mt-6">
                    <SessionAnalysisView
                        session="Asia"
                        sessions={filteredSessions}
                        allSessions={filteredSessions} // Pass full list for Daily context
                        dailyHodLod={dailyHodLod || null}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                        levelTouches={levelTouches}
                        filters={filters}
                        brokenFilters={brokenFilters}
                        intraState={intraState}
                    />
                </TabsContent>

                <TabsContent value="london" className="mt-6">
                    <SessionAnalysisView
                        session="London"
                        sessions={filteredSessions}
                        allSessions={filteredSessions}
                        dailyHodLod={dailyHodLod || null}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                        levelTouches={levelTouches}
                        filters={filters}
                        brokenFilters={brokenFilters}
                        intraState={intraState}
                    />
                </TabsContent>

                <TabsContent value="ny1" className="mt-6">
                    <SessionAnalysisView
                        session="NY1"
                        sessions={filteredSessions}
                        allSessions={filteredSessions}
                        dailyHodLod={dailyHodLod || null}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                        levelTouches={levelTouches}
                        filters={filters}
                        brokenFilters={brokenFilters}
                        intraState={intraState}
                    />
                </TabsContent>

                <TabsContent value="ny2" className="mt-6">
                    <SessionAnalysisView
                        session="NY2"
                        sessions={filteredSessions}
                        allSessions={filteredSessions}
                        dailyHodLod={dailyHodLod || null}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                        levelTouches={levelTouches}
                        filters={filters}
                        brokenFilters={brokenFilters}
                        intraState={intraState}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
