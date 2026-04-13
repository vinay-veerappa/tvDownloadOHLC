'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, BarChart3, RefreshCcw, Route, TimerReset, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  mopRetrace: string;
  outsideDay: string;
  weeklyBreak: string;
  startDate: string;
  endDate: string;
};

type Overview = {
  total_rows: number;
  mop_retrace_rate: number;
  pdh_break_rate: number;
  pdl_break_rate: number;
  outside_day_reversal_rate: number;
  weekly_open_retrace_rate: number;
  avg_mop_retrace_time: number | null;
};

type DistRow = {
  label: string;
  count: number;
  metric_a: number;
  metric_b: number;
};

type TimingRow = {
  label: string;
  avg_minutes: number | null;
};

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  mopRetrace: 'ALL',
  outsideDay: 'ALL',
  weeklyBreak: 'ALL',
  startDate: '',
  endDate: '',
};

function quote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function buildWhere(filters: FilterState) {
  const conditions: string[] = [];

  if (filters.symbol !== 'ALL') conditions.push(`symbol = ${quote(filters.symbol)}`);
  if (filters.mopRetrace === 'YES') conditions.push('mop_retrace = true');
  else if (filters.mopRetrace === 'NO') conditions.push('mop_retrace = false');

  if (filters.outsideDay === 'YES') conditions.push('is_outside_day = true');
  else if (filters.outsideDay === 'NO') conditions.push('is_outside_day = false');

  if (filters.weeklyBreak === 'YES') conditions.push('(prior_week_high_broken = true OR prior_week_low_broken = true)');
  else if (filters.weeklyBreak === 'NO') conditions.push('(prior_week_high_broken = false AND prior_week_low_broken = false)');

  if (filters.startDate) conditions.push(`trading_date >= ${quote(filters.startDate)}`);
  if (filters.endDate) conditions.push(`trading_date <= ${quote(filters.endDate)}`);

  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
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
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400"
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

function formatPct(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatMinutes(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(1)}m`;
}

export default function ReferenceLevelsPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();
  const [loading, setLoading] = useState(false);

  const [symbols, setSymbols] = useState<string[]>(['ALL']);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [scenarioRows, setScenarioRows] = useState<DistRow[]>([]);
  const [weeklyRows, setWeeklyRows] = useState<DistRow[]>([]);
  const [timingRows, setTimingRows] = useState<TimingRow[]>([]);

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('reference_levels.parquet', `/api/data/reference_levels.parquet?v=${version}`);
      const metaResponse = await fetch(`/api/data/reference_levels.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      setLastDataUpdate(metaResponse.headers.get('last-modified'));
      setDbStatus('ready');
    } catch (error) {
      console.error('Failed to initialize reference-level analytics engine:', error);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  useEffect(() => {
    if (dbStatus !== 'ready') return;
    const loadOptions = async () => {
      const rows = await runQuery<{ symbol: string }>('SELECT DISTINCT symbol FROM reference_levels ORDER BY symbol');
      setSymbols(['ALL', ...rows.map((r) => r.symbol)]);
    };
    loadOptions().catch((error) => {
      console.error('Failed to load reference-level filters:', error);
    });
  }, [dbStatus]);

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;

    setLoading(true);
    const started = performance.now();
    try {
      const where = buildWhere(deferredFilters);
      const [overviewRows, scenarioDistRows, weeklyDistRows, timingDistRows] = await Promise.all([
        runQuery<Overview>(`
          SELECT
            CAST(COUNT(*) AS DOUBLE) AS total_rows,
            CAST(AVG(CASE WHEN mop_retrace THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS mop_retrace_rate,
            CAST(AVG(CASE WHEN pdh_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdh_break_rate,
            CAST(AVG(CASE WHEN pdl_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdl_break_rate,
            CAST(AVG(CASE WHEN is_outside_day THEN CASE WHEN outside_day_reversal THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS outside_day_reversal_rate,
            CAST(AVG(CASE WHEN weekly_open_retrace THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS weekly_open_retrace_rate,
            CAST(AVG(CASE WHEN mop_retrace THEN mop_retrace_time_minutes END) AS DOUBLE) AS avg_mop_retrace_time
          FROM reference_levels
          ${where}
        `),
        runQuery<DistRow>(`
          SELECT
            CASE
              WHEN is_outside_day THEN 'Outside Day'
              WHEN is_inside_day THEN 'Inside Day'
              ELSE 'Normal Day'
            END AS label,
            CAST(COUNT(*) AS DOUBLE) AS count,
            CAST(AVG(CASE WHEN mop_retrace THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_a,
            CAST(AVG(CASE WHEN outside_day_reversal THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_b
          FROM reference_levels
          ${where}
          GROUP BY 1
          ORDER BY count DESC
        `),
        runQuery<DistRow>(`
          SELECT 'Weekly Open Retrace' AS label,
                 CAST(COUNT(*) AS DOUBLE) AS count,
                 CAST(AVG(CASE WHEN weekly_open_retrace THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_a,
                 CAST(AVG(CASE WHEN prior_week_high_broken OR prior_week_low_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_b
          FROM reference_levels
          ${where}
          UNION ALL
          SELECT 'Prior Week High Broken' AS label,
                 CAST(COUNT(*) AS DOUBLE) AS count,
                 CAST(AVG(CASE WHEN prior_week_high_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_a,
                 CAST(AVG(CASE WHEN pdh_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_b
          FROM reference_levels
          ${where}
          UNION ALL
          SELECT 'Prior Week Low Broken' AS label,
                 CAST(COUNT(*) AS DOUBLE) AS count,
                 CAST(AVG(CASE WHEN prior_week_low_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_a,
                 CAST(AVG(CASE WHEN pdl_broken THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS metric_b
          FROM reference_levels
          ${where}
        `),
        runQuery<TimingRow>(`
          SELECT 'MOP Retrace' AS label, CAST(AVG(CASE WHEN mop_retrace THEN mop_retrace_time_minutes END) AS DOUBLE) AS avg_minutes
          FROM reference_levels ${where}
          UNION ALL
          SELECT 'PDH Break' AS label, CAST(AVG(CASE WHEN pdh_broken THEN pdh_break_time END) AS DOUBLE) AS avg_minutes
          FROM reference_levels ${where}
          UNION ALL
          SELECT 'PDL Break' AS label, CAST(AVG(CASE WHEN pdl_broken THEN pdl_break_time END) AS DOUBLE) AS avg_minutes
          FROM reference_levels ${where}
        `),
      ]);

      setOverview((overviewRows[0] as Overview) ?? null);
      setScenarioRows(scenarioDistRows);
      setWeeklyRows(weeklyDistRows);
      setTimingRows(timingDistRows);
      setQueryTimeMs(performance.now() - started);
    } catch (error) {
      console.error('Failed to query reference-level dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const heroStats = useMemo(
    () => [
      { label: 'MOP Retrace', value: formatPct(overview?.mop_retrace_rate) },
      { label: 'PDH Break', value: formatPct(overview?.pdh_break_rate) },
      { label: 'PDL Break', value: formatPct(overview?.pdl_break_rate) },
      { label: 'Weekly Open Retrace', value: formatPct(overview?.weekly_open_retrace_rate) },
    ],
    [overview]
  );

  return (
    <div className="space-y-6 pb-10 text-zinc-100">
      <div className="rounded-3xl border border-amber-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_42%),linear-gradient(135deg,rgba(24,24,27,0.96),rgba(9,9,11,0.98))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-4">
            <Link href="/research" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-amber-300">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Research Hub
            </Link>
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.3em] text-amber-200">
              <Route className="h-3.5 w-3.5" />
              Phase 5 Dashboard
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-white">Reference Levels</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
                Study midnight-open retraces, PDH and PDL continuation, outside-day reversals, and weekly reference interaction from the new report layer.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" className="border-zinc-700 bg-zinc-950/70 text-zinc-100 hover:bg-zinc-900" onClick={() => resetDuckDB().then(loadEngine)}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Reload Data
            </Button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {heroStats.map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-white/8 bg-black/20 px-4 py-4 backdrop-blur-sm">
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">{stat.label}</div>
              <div className="mt-2 text-2xl font-semibold text-white">{stat.value}</div>
            </div>
          ))}
        </div>
      </div>

      <Card className="border-zinc-900 bg-black/30 p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Filters</div>
            <h2 className="mt-1 text-lg font-semibold text-white">Reference-Level Conditions</h2>
          </div>

          <div className="flex flex-wrap gap-3">
            <SelectField label="Symbol" value={filters.symbol} options={symbols} onChange={(value) => setFilters((prev) => ({ ...prev, symbol: value }))} />
            <SelectField label="MOP Retrace" value={filters.mopRetrace} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((prev) => ({ ...prev, mopRetrace: value }))} />
            <SelectField label="Outside Day" value={filters.outsideDay} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((prev) => ({ ...prev, outsideDay: value }))} />
            <SelectField label="Weekly Break" value={filters.weeklyBreak} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((prev) => ({ ...prev, weeklyBreak: value }))} />
            <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>Start Date</span>
              <input type="date" value={filters.startDate} onChange={(event) => setFilters((prev) => ({ ...prev, startDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400" />
            </label>
            <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>End Date</span>
              <input type="date" value={filters.endDate} onChange={(event) => setFilters((prev) => ({ ...prev, endDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400" />
            </label>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Runtime</div>
          <div className="mt-1 text-sm text-zinc-300">
            {overview ? `${Math.round(overview.total_rows).toLocaleString()} sessions in scope` : '--'}
          </div>
        </div>

        <QueryStatus
          dbStatus={dbStatus}
          queryTimeMs={queryTimeMs}
          totalRecords={overview?.total_rows}
          lastDataUpdate={lastDataUpdate}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MiniStat label="Outside-Day Reversal" value={formatPct(overview?.outside_day_reversal_rate)} />
        <MiniStat label="Avg MOP Touch Time" value={formatMinutes(overview?.avg_mop_retrace_time)} />
        <MiniStat label="Rows In Scope" value={overview ? Math.round(overview.total_rows).toLocaleString() : '--'} />
        <MiniStat label="Weekly Open Retrace" value={formatPct(overview?.weekly_open_retrace_rate)} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Session Structure</div>
              <h2 className="mt-1 text-lg font-semibold">MOP Retrace vs Outside-Day Reversal</h2>
            </div>
            <BarChart3 className="h-5 w-5 text-amber-300" />
          </div>

          <div className="h-80 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scenarioRows}>
                <CartesianGrid vertical={false} stroke="#18181b" />
                <XAxis dataKey="label" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                  contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                  formatter={(v: number, key: string) => [formatPct(v), key === 'metric_a' ? 'MOP retrace' : 'Outside-day reversal']}
                />
                <Bar dataKey="metric_a" name="metric_a" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                <Bar dataKey="metric_b" name="metric_b" fill="#38bdf8" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Trigger Timing</div>
              <h2 className="mt-1 text-lg font-semibold">Average First-Touch Timing</h2>
            </div>
            <TimerReset className="h-5 w-5 text-cyan-300" />
          </div>

          <div className="space-y-3">
            {timingRows.map((row) => (
              <div key={row.label} className="rounded-2xl border border-zinc-900 bg-zinc-950/60 px-4 py-4">
                <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">{row.label}</div>
                <div className="mt-2 text-2xl font-semibold text-white">{formatMinutes(row.avg_minutes)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="border-zinc-900 bg-black/30 p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Weekly Interaction</div>
            <h2 className="mt-1 text-lg font-semibold">Weekly References and PD Continuation</h2>
          </div>
          <TrendingUp className="h-5 w-5 text-emerald-300" />
        </div>

        <div className="overflow-hidden rounded-xl border border-zinc-900">
          <table className="min-w-full divide-y divide-zinc-900 text-sm">
            <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
              <tr>
                <th className="px-4 py-3 text-left">Metric</th>
                <th className="px-4 py-3 text-right">N</th>
                <th className="px-4 py-3 text-right">Primary %</th>
                <th className="px-4 py-3 text-right">Linked PD %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 bg-black/20">
              {weeklyRows.map((row) => (
                <tr key={row.label}>
                  <td className="px-4 py-3 font-medium text-zinc-200">{row.label}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.count).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-amber-300">{formatPct(row.metric_a)}</td>
                  <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.metric_b)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}