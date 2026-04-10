'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Clock3, RefreshCcw, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  eventDay: string;
  firstBreakDirection: string;
  startDate: string;
  endDate: string;
};

type Overview = {
  total_rows: number;
  london_break_rate: number;
  both_sides_rate: number;
  continuation_rate: number;
  reversal_rate: number;
  avg_first_break_minutes: number | null;
};

type DistRow = {
  label: string;
  n: number;
  continuation_rate: number;
  reversal_rate: number;
};

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  eventDay: 'ALL',
  firstBreakDirection: 'ALL',
  startDate: '',
  endDate: '',
};

function quote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function formatPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(1)}%`;
}

function buildWhere(filters: FilterState, alias?: string) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];

  if (filters.symbol !== 'ALL') conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  if (filters.eventDay === 'YES') conditions.push(`${prefix}is_event_day = true`);
  if (filters.eventDay === 'NO') conditions.push(`${prefix}is_event_day = false`);
  if (filters.firstBreakDirection !== 'ALL') {
    conditions.push(`${prefix}first_break_direction = ${quote(filters.firstBreakDirection)}`);
  }
  if (filters.startDate) conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  if (filters.endDate) conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);

  return conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex min-w-[150px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-indigo-400"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === 'ALL' ? 'All' : option}
          </option>
        ))}
      </select>
    </label>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="border-zinc-900 bg-zinc-950/70 p-4">
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-100">{value}</div>
    </Card>
  );
}

export default function SessionBreakoutsPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [loading, setLoading] = useState(false);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);

  const [symbols, setSymbols] = useState<string[]>(['ALL']);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [distRows, setDistRows] = useState<DistRow[]>([]);
  const [closeRows, setCloseRows] = useState<{ label: string; n: number }[]>([]);

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('session_breakout_records.parquet', `/api/data/session_breakout_records.parquet?v=${version}`);
      const metaResponse = await fetch(`/api/data/session_breakout_records.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      setLastDataUpdate(metaResponse.headers.get('last-modified'));
      setDbStatus('ready');
    } catch (error) {
      console.error('Failed to initialize session breakout analytics engine:', error);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  useEffect(() => {
    if (dbStatus !== 'ready') return;
    runQuery('SELECT DISTINCT symbol FROM session_breakout_records ORDER BY symbol')
      .then((rows) => setSymbols(['ALL', ...rows.map((r: { symbol: string }) => r.symbol)]))
      .catch((error) => console.error('Failed to load symbols for breakout dashboard:', error));
  }, [dbStatus]);

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;

    setLoading(true);
    const started = performance.now();
    try {
      const where = buildWhere(deferredFilters);
      const [overviewRows, directionRows, closeLocationRows] = await Promise.all([
        runQuery(`
          SELECT
            CAST(COUNT(*) AS DOUBLE) AS total_rows,
            CAST(AVG(CASE WHEN london_high_broken_in_ny OR london_low_broken_in_ny THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS london_break_rate,
            CAST(AVG(CASE WHEN both_sides_broken_in_ny THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS both_sides_rate,
            CAST(AVG(CASE WHEN first_break_direction IN ('UP','DOWN') THEN CASE WHEN continuation_after_first_break THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS continuation_rate,
            CAST(AVG(CASE WHEN first_break_direction IN ('UP','DOWN') THEN CASE WHEN reversal_after_first_break THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS reversal_rate,
            CAST(AVG(first_break_time_minutes) AS DOUBLE) AS avg_first_break_minutes
          FROM session_breakout_records
          ${where}
        `),
        runQuery(`
          SELECT
            first_break_direction AS label,
            CAST(COUNT(*) AS DOUBLE) AS n,
            CAST(AVG(CASE WHEN continuation_after_first_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_rate,
            CAST(AVG(CASE WHEN reversal_after_first_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS reversal_rate
          FROM session_breakout_records
          ${where}
          GROUP BY first_break_direction
          ORDER BY CASE first_break_direction WHEN 'UP' THEN 1 WHEN 'DOWN' THEN 2 WHEN 'NONE' THEN 3 ELSE 4 END
        `),
        runQuery(`
          SELECT
            ny_close_location_vs_london AS label,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM session_breakout_records
          ${where}
          GROUP BY ny_close_location_vs_london
          ORDER BY CASE ny_close_location_vs_london WHEN 'ABOVE' THEN 1 WHEN 'INSIDE' THEN 2 WHEN 'BELOW' THEN 3 ELSE 4 END
        `),
      ]);

      setOverview((overviewRows[0] as Overview) ?? null);
      setDistRows(directionRows as DistRow[]);
      setCloseRows(closeLocationRows as { label: string; n: number }[]);
      setQueryTimeMs(performance.now() - started);
    } catch (error) {
      console.error('Failed to query session breakout dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const totalRows = useMemo(() => Math.round(overview?.total_rows ?? 0), [overview]);

  const refreshData = useCallback(async () => {
    setOverview(null);
    setDistRows([]);
    setCloseRows([]);
    await resetDuckDB();
    await loadEngine();
  }, [loadEngine]);

  return (
    <div className="space-y-6 pb-10 text-zinc-100">
      <div className="rounded-3xl border border-indigo-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.18),_transparent_42%),linear-gradient(135deg,rgba(24,24,27,0.96),rgba(9,9,11,0.98))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-4">
            <Link href="/research" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-indigo-300">
              <ArrowRight className="h-3.5 w-3.5 rotate-180" />
              Research Hub
            </Link>
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.3em] text-indigo-200">
                <Clock3 className="h-3.5 w-3.5" />
                Phase 6 Dashboard
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Session Breakouts</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
                London-to-NY breakout behavior: first break direction, continuation probability, reversal risk, and close-location distribution.
              </p>
            </div>
          </div>
          <Button variant="outline" className="border-zinc-700 bg-zinc-950/70 text-zinc-100 hover:bg-zinc-900" disabled={dbStatus === 'loading' || loading} onClick={refreshData}>
            <RefreshCcw className={`mr-2 h-4 w-4 ${dbStatus === 'loading' ? 'animate-spin' : ''}`} />
            Reload Data
          </Button>
        </div>
      </div>

      <Card className="border-zinc-900 bg-black/30 p-5">
        <div className="grid gap-4 lg:grid-cols-[repeat(3,minmax(0,1fr))_160px_160px] xl:grid-cols-[repeat(5,minmax(0,1fr))]">
          <SelectField label="Symbol" value={filters.symbol} options={symbols} onChange={(value) => setFilters((prev) => ({ ...prev, symbol: value }))} />
          <SelectField label="Event Day" value={filters.eventDay} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((prev) => ({ ...prev, eventDay: value }))} />
          <SelectField label="First Break" value={filters.firstBreakDirection} options={['ALL', 'UP', 'DOWN', 'NONE']} onChange={(value) => setFilters((prev) => ({ ...prev, firstBreakDirection: value }))} />

          <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
            <span>Start</span>
            <input type="date" value={filters.startDate} onChange={(event) => setFilters((prev) => ({ ...prev, startDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-indigo-400" />
          </label>
          <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
            <span>End</span>
            <input type="date" value={filters.endDate} onChange={(event) => setFilters((prev) => ({ ...prev, endDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-indigo-400" />
          </label>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-zinc-400">{totalRows > 0 ? `${totalRows.toLocaleString()} session records` : 'Waiting for query results'}</div>
        <QueryStatus dbStatus={dbStatus} queryTimeMs={queryTimeMs} totalRecords={totalRows} lastDataUpdate={lastDataUpdate} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <MiniStat label="London Broken In NY" value={formatPct(overview?.london_break_rate)} />
        <MiniStat label="Both Sides Broken" value={formatPct(overview?.both_sides_rate)} />
        <MiniStat label="Avg First Break Time" value={overview?.avg_first_break_minutes != null ? `${overview.avg_first_break_minutes.toFixed(1)} min` : '--'} />
        <MiniStat label="Continuation After First Break" value={formatPct(overview?.continuation_rate)} />
        <MiniStat label="Reversal After First Break" value={formatPct(overview?.reversal_rate)} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">First Break</div>
              <h2 className="mt-1 text-lg font-semibold">Continuation vs reversal by first break direction</h2>
            </div>
            <TrendingUp className="h-5 w-5 text-indigo-300" />
          </div>

          <div className="h-80 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distRows}>
                <CartesianGrid vertical={false} stroke="#18181b" />
                <XAxis dataKey="label" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                  contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                  formatter={(v: number, key: string) => [formatPct(v), key === 'continuation_rate' ? 'Continuation' : 'Reversal']}
                />
                <Bar dataKey="continuation_rate" fill="#818cf8" radius={[8, 8, 0, 0]} />
                <Bar dataKey="reversal_rate" fill="#fb7185" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5">
            <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Close Location</div>
            <h2 className="mt-1 text-lg font-semibold">NY close versus London range</h2>
          </div>

          <div className="space-y-3">
            {closeRows.map((row) => (
              <div key={row.label} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-sm font-medium text-zinc-200">{row.label}</div>
                  <div className="text-right text-zinc-300">{Math.round(row.n).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
