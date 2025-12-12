"use client"

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { fetchProfilerStats, fetchLevelTouches } from '@/lib/api/profiler';
import { useServerFilteredStats } from '@/hooks/use-server-filtered-stats';
import { useLevelTouches } from '@/hooks/use-level-touches';
import { SESSION_ORDER } from '@/hooks/use-profiler-filter';

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfilerWizard } from './profiler-wizard';
import { ActiveFiltersRow } from './active-filters-row';
import { SessionAnalysisView } from './session-analysis-view';
import { RangeDistribution } from './range-distribution';
import { PriceModelChart } from './price-model-chart';
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

    // 3. Server-Side Filtered Data (NEW - calls backend filter endpoints)
    const {
        filteredDates,
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
    const { data: profilerData, error: profilerError } = useSWR(`profilerStats-${ticker}`, () => fetchProfilerStats(ticker, 10000));
    const { levelTouches } = useLevelTouches(ticker);

    // 5. Compute filtered sessions from the matched dates
    const sessions = profilerData?.sessions || [];
    const filteredSessions = useMemo(() => {
        return sessions.filter(s => filteredDates.has(s.date));
    }, [sessions, filteredDates]);

    const error = filterError || profilerError;
    if (error) return <div className="p-8 text-center text-red-500">Failed to load profiler data.</div>;
    if (!profilerData || isFilterLoading) return <div className="p-8 text-center text-muted-foreground">Loading...</div>;

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

                    {/* A. Global Price Range Distribution */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Global Price Range Distribution</h2>
                        <RangeDistribution sessions={filteredSessions} forcedSession="daily" />
                    </section>

                    {/* B. Daily Price Model (Median, Full Day) - TEMPORARILY DISABLED */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Daily Price Model (Median)</h2>
                        <div className="h-[400px] flex items-center justify-center border rounded-md text-muted-foreground">
                            Price Model chart temporarily disabled for debugging.
                        </div>
                        {/* <PriceModelChart
                            ticker="NQ1"
                            session="Daily"
                            filteredDates={filteredDates}
                            height={400}
                        /> */}
                    </section>

                    {/* C. Daily Levels */}
                    <section>
                        <h2 className="text-xl font-semibold mb-4">Daily Levels Analysis</h2>
                        <DailyLevels
                            levelTouches={levelTouches}
                            filteredDates={filteredDates}
                        // No limitLevels = Show all
                        />
                    </section>
                </TabsContent>

                {/* --- Session Tabs --- */}
                <TabsContent value="asia" className="mt-6">
                    <SessionAnalysisView
                        session="Asia"
                        sessions={filteredSessions}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                    />
                </TabsContent>

                <TabsContent value="london" className="mt-6">
                    <SessionAnalysisView
                        session="London"
                        sessions={filteredSessions}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                    />
                </TabsContent>

                <TabsContent value="ny1" className="mt-6">
                    <SessionAnalysisView
                        session="NY1"
                        sessions={filteredSessions}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                    />
                </TabsContent>

                <TabsContent value="ny2" className="mt-6">
                    <SessionAnalysisView
                        session="NY2"
                        sessions={filteredSessions}
                        filteredDates={filteredDates}
                        ticker="NQ1"
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
