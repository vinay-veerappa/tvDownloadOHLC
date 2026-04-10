'use client';

import { useState, useEffect, useCallback } from 'react';
import { FilterPanel } from './components/FilterPanel';
import { SummaryCards } from './components/SummaryCards';
import { useFilters } from './hooks/useFilters';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { buildWhereClause, getSummarySql } from './lib/queryBuilder';
import { SummaryMetrics } from './types';
import { DistributionCharts } from './components/DistributionCharts';
import { CrossTab } from './components/CrossTab';
import { DrillDownTable } from './components/DrillDownTable';
import { FVGAnalysis } from './components/FVGAnalysis';
import { UniversalFilterBar } from './components/UniversalFilterBar';
import { ExtensionProbabilityPanel } from './components/ExtensionProbabilityPanel';
import { RollingProbabilityPanel } from './components/RollingProbabilityPanel';
import { PDLevelInteractionPanel } from './components/PDLevelInteractionPanel';
import { OpeningCandleContinuationPanel } from './components/OpeningCandleContinuationPanel';
import { LayoutDashboard, RefreshCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { QueryStatus } from './components/QueryStatus';

import { Suspense } from 'react';

function DashboardContent() {
  const { filters, updateFilter, updateDateRange, updateLookback, updateAdvanced, resetFilters } = useFilters();
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [dbStatus, setDbStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [metrics, setMetrics] = useState<SummaryMetrics | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);

  const loadDataEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('macro_records.parquet', `/api/data/macro_records.parquet?v=${version}`);
      await loadParquet('fvg_detail.parquet', `/api/data/fvg_detail.parquet?v=${version}`);

      const metaResponse = await fetch(`/api/data/macro_records.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      const lastModified = metaResponse.headers.get('last-modified');
      if (lastModified) {
        setLastDataUpdate(lastModified);
      }

      setDbStatus('ready');
    } catch (err) {
      console.error('Failed to initialize DuckDB:', err);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedFilters(filters);
    }, 200);
    return () => clearTimeout(timeout);
  }, [filters]);

  // Initialize Data Engine
  useEffect(() => {
    loadDataEngine();
  }, [loadDataEngine]);

  const refreshData = useCallback(async () => {
    setMetrics(null);
    await resetDuckDB();
    await loadDataEngine();
  }, [loadDataEngine]);

  // Update Metrics on Filter Change
  const fetchMetrics = useCallback(async () => {
    if (dbStatus !== 'ready') return;
    
    setLoadingMetrics(true);
    const start = performance.now();
    try {
      const whereClause = buildWhereClause(debouncedFilters);
      const sql = getSummarySql(whereClause);
      const result = await runQuery(sql);
      
      console.log('Query Result:', result);
      
      if (result.length > 0) {
        setMetrics({
          ...result[0],
          query_time_ms: performance.now() - start
        });
      } else {
        console.warn('Query returned empty result.');
      }
    } catch (err) {
      console.error('Query failed:', err, 'SQL:', getSummarySql(buildWhereClause(debouncedFilters)));
    } finally {
      setLoadingMetrics(false);
    }
  }, [dbStatus, debouncedFilters]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return (
    <div className="flex h-screen bg-black text-zinc-100 overflow-hidden font-sans">
      {/* Sidebar: Filters */}
      <div className="w-64 flex-shrink-0 border-r border-zinc-900">
        <FilterPanel 
          filters={filters} 
          updateFilter={updateFilter} 
          updateDateRange={updateDateRange}
          updateLookback={updateLookback}
          updateAdvanced={updateAdvanced} 
          resetFilters={resetFilters} 
        />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-zinc-900 flex items-center justify-between px-6 bg-zinc-950/50 backdrop-blur-sm relative z-10">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-amber-500/10 rounded-lg">
              <LayoutDashboard className="h-4 w-4 text-amber-500" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight">Macro Research Dashboard</h1>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`w-1.5 h-1.5 rounded-full ${dbStatus === 'ready' ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-700'}`} />
                <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-widest">
                  {dbStatus === 'ready' ? 'Engine Ready' : 'Initializing Engine...'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <QueryStatus
              dbStatus={dbStatus}
              queryTimeMs={metrics?.query_time_ms}
              totalRecords={metrics?.total}
              lastDataUpdate={lastDataUpdate}
            />
            <Button 
              variant="outline" 
              size="sm" 
              className="h-8 border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 text-xs gap-2"
              onClick={refreshData}
              disabled={dbStatus === 'loading' || loadingMetrics}
            >
              <RefreshCcw className={`h-3 w-3 ${dbStatus === 'loading' ? 'animate-spin' : ''}`} />
              Refresh Data
            </Button>
          </div>
        </header>

        {/* Dynamic Content */}
        <main className="flex-1 overflow-y-auto p-6 space-y-8 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] bg-repeat">
          <UniversalFilterBar
            filters={filters}
            updateFilter={updateFilter}
            updateLookback={updateLookback}
            updateAdvanced={updateAdvanced}
          />

          {/* Top Metrics Row */}
          <SummaryCards metrics={metrics} loading={loadingMetrics || dbStatus === 'loading'} />

          {/* Tabs for Macro vs FVG Analysis */}
          <Tabs defaultValue="macro" className="w-full">
            <TabsList className="bg-zinc-900 border border-zinc-800 mb-6">
              <TabsTrigger value="macro" className="text-xs uppercase tracking-widest font-bold data-[state=active]:bg-zinc-800 data-[state=active]:text-amber-500">
                Macro Analysis
              </TabsTrigger>
              <TabsTrigger value="fvg" className="text-xs uppercase tracking-widest font-bold data-[state=active]:bg-zinc-800 data-[state=active]:text-amber-500">
                FVG Analysis (Phase 5)
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="macro" className="space-y-8 mt-0 outline-none">
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <ExtensionProbabilityPanel filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
                <RollingProbabilityPanel filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <PDLevelInteractionPanel filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
                <OpeningCandleContinuationPanel filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
              </div>

              {/* Phase 4: Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DistributionCharts filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
                <CrossTab filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
              </div>

              {/* Drill-Down */}
              <DrillDownTable filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
            </TabsContent>
            
            <TabsContent value="fvg" className="mt-0 outline-none">
              <FVGAnalysis filters={debouncedFilters} dbReady={dbStatus === 'ready'} />
            </TabsContent>
          </Tabs>
        </main>

        {/* Footer info line */}
        <footer className="h-8 border-t border-zinc-900 bg-black flex items-center px-6 justify-between text-[9px] text-zinc-600 uppercase tracking-widest font-bold">
          <span>Sprint 3: Edgeful Dashboard MVP</span>
          <span>Last Data Update: {lastDataUpdate ? new Date(lastDataUpdate).toLocaleString() : 'Unknown'}</span>
        </footer>
      </div>
    </div>
  );
}

export default function EdgefulDashboard() {
  return (
    <Suspense fallback={<div className="flex h-screen bg-black items-center justify-center text-zinc-500 text-xs tracking-widest uppercase font-bold">Loading Engine...</div>}>
      <DashboardContent />
    </Suspense>
  );
}

// Internal icons needed for the placeholder
function TrendingUp(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  )
}
