'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, GitCompareArrows, RefreshCcw, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  strategyName: string;
  startDate: string;
  endDate: string;
};

type FilterOptions = {
  symbols: string[];
  strategies: string[];
};

type ComparisonRow = {
  range_name: string;
  total_ranges: number;
  avg_width_pct: number | null;
  aligned_close_rate: number | null;
  failed_breakout_rate: number | null;
  ext_1x_hit_rate: number | null;
  mr_mid_retest_rate: number | null;
  strategy_win_rate: number | null;
  strategy_avg_r: number | null;
};

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  strategyName: 'MR_TO_MID',
  startDate: '',
  endDate: '',
};

function quote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function formatPct(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

function buildRangeWhere(filters: FilterState, alias?: string) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];
  if (filters.symbol !== 'ALL') conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  if (filters.startDate) conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  if (filters.endDate) conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);
  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}

function buildTradeWhere(filters: FilterState, alias?: string) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];
  if (filters.symbol !== 'ALL') conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  if (filters.strategyName !== 'ALL') conditions.push(`${prefix}strategy_name = ${quote(filters.strategyName)}`);
  if (filters.startDate) conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  if (filters.endDate) conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);
  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}

function getComparisonSql(rangeWhere: string, tradeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records rr
      ${rangeWhere}
    ),
    rt AS (
      SELECT *
      FROM range_trades rt
      ${tradeWhere}
    )
    SELECT
      rr.range_name,
      CAST(COUNT(*) AS DOUBLE) AS total_ranges,
      CAST(AVG(rr.range_width_pct) AS DOUBLE) AS avg_width_pct,
      CAST(AVG(CASE WHEN rr.first_bo_direction IN ('UP', 'DOWN') AND rr.first_bo_direction = rr.final_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS aligned_close_rate,
      CAST(AVG(CASE WHEN rr.first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS failed_breakout_rate,
      CAST(AVG(CASE WHEN rr.first_bo_direction = 'UP' THEN CASE WHEN rr.ext_up_100_hit THEN 1.0 ELSE 0.0 END WHEN rr.first_bo_direction = 'DOWN' THEN CASE WHEN rr.ext_dn_100_hit THEN 1.0 ELSE 0.0 END ELSE NULL END) * 100 AS DOUBLE) AS ext_1x_hit_rate,
      CAST(AVG(CASE WHEN rr.first_bo_direction = 'UP' THEN CASE WHEN rr.retest_mid_after_high_break THEN 1.0 ELSE 0.0 END WHEN rr.first_bo_direction = 'DOWN' THEN CASE WHEN rr.retest_mid_after_low_break THEN 1.0 ELSE 0.0 END ELSE NULL END) * 100 AS DOUBLE) AS mr_mid_retest_rate,
      CAST(AVG(CASE WHEN rt.entry_triggered THEN CASE WHEN rt.pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS strategy_win_rate,
      CAST(AVG(CASE WHEN rt.entry_triggered THEN rt.pnl_r_multiple END) AS DOUBLE) AS strategy_avg_r
    FROM rr
    LEFT JOIN rt
      ON rt.symbol = rr.symbol
     AND rt.range_name = rr.range_name
     AND rt.trading_date = rr.trading_date
    GROUP BY rr.range_name
    ORDER BY CASE rr.range_name
      WHEN 'OR_5' THEN 1
      WHEN 'OR_15' THEN 2
      WHEN 'OR_30' THEN 3
      WHEN 'IB_60' THEN 4
      WHEN 'IB_90' THEN 5
      WHEN 'LUNCH' THEN 6
      WHEN 'ASIA' THEN 7
      WHEN 'OVERNIGHT' THEN 8
      WHEN 'SILVER_BULLET_AM' THEN 9
      WHEN 'SILVER_BULLET_PM' THEN 10
      WHEN 'POWER_HOUR' THEN 11
      ELSE 12
    END
  `;
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
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-sky-400"
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

function MiniStat({ label, value, sublabel }: { label: string; value: string; sublabel?: string }) {
  return (
    <Card className="border-zinc-900 bg-zinc-950/70 p-4">
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-100">{value}</div>
      {sublabel ? <div className="mt-1 text-xs text-zinc-500">{sublabel}</div> : null}
    </Card>
  );
}

export default function RangeComparisonPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();

  const [options, setOptions] = useState<FilterOptions>({ symbols: ['ALL'], strategies: ['ALL', 'MR_TO_MID'] });
  const [rows, setRows] = useState<ComparisonRow[]>([]);

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('range_records.parquet', `/api/data/range_records.parquet?v=${version}`);
      await loadParquet('range_trades.parquet', `/api/data/range_trades.parquet?v=${version}`);
      const metaResponse = await fetch(`/api/data/range_records.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      setLastDataUpdate(metaResponse.headers.get('last-modified'));
      setDbStatus('ready');
    } catch (error) {
      console.error('Failed to initialize range comparison engine:', error);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  useEffect(() => {
    if (dbStatus !== 'ready') return;
    const loadOptions = async () => {
      const [symbols, strategies] = await Promise.all([
        runQuery('SELECT DISTINCT symbol FROM range_records ORDER BY symbol'),
        runQuery('SELECT DISTINCT strategy_name FROM range_trades ORDER BY strategy_name'),
      ]);
      setOptions({
        symbols: ['ALL', ...symbols.map((row: { symbol: string }) => row.symbol)],
        strategies: ['ALL', ...strategies.map((row: { strategy_name: string }) => row.strategy_name)],
      });
    };
    loadOptions().catch((error) => {
      console.error('Failed to load range comparison filters:', error);
    });
  }, [dbStatus]);

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;
    setLoading(true);
    const startedAt = performance.now();
    try {
      const rangeWhere = buildRangeWhere(deferredFilters, 'rr');
      const tradeWhere = buildTradeWhere(deferredFilters, 'rt');
      const result = await runQuery(getComparisonSql(rangeWhere, tradeWhere));
      setRows(result as ComparisonRow[]);
      setQueryTimeMs(performance.now() - startedAt);
    } catch (error) {
      console.error('Failed to query range comparison page:', error);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const bestAligned = useMemo(() => rows.reduce<ComparisonRow | null>((best, row) => (!best || (row.aligned_close_rate ?? -1) > (best.aligned_close_rate ?? -1) ? row : best), null), [rows]);
  const bestMR = useMemo(() => rows.reduce<ComparisonRow | null>((best, row) => (!best || (row.mr_mid_retest_rate ?? -1) > (best.mr_mid_retest_rate ?? -1) ? row : best), null), [rows]);
  const bestStrategy = useMemo(() => rows.reduce<ComparisonRow | null>((best, row) => (!best || (row.strategy_win_rate ?? -1) > (best.strategy_win_rate ?? -1) ? row : best), null), [rows]);

  const refreshData = useCallback(async () => {
    setRows([]);
    await resetDuckDB();
    await loadEngine();
  }, [loadEngine]);

  return (
    <div className="space-y-6 pb-10 text-zinc-100">
      <div className="rounded-3xl border border-sky-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_42%),linear-gradient(135deg,rgba(24,24,27,0.96),rgba(9,9,11,0.98))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-4">
            <Link href="/research" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-sky-300">
              <ArrowRight className="h-3.5 w-3.5 rotate-180" />
              Research Hub
            </Link>
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.3em] text-sky-200">
                <GitCompareArrows className="h-3.5 w-3.5" />
                Phase 5 Dashboard
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Range Comparison</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
                Compare OR and IB definitions side by side on structure, mean reversion behavior, and selected strategy performance.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link href="/research/ranges" className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/80 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-900">
              Full Range Dashboard
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Button variant="outline" className="border-zinc-700 bg-zinc-950/70 text-zinc-100 hover:bg-zinc-900" disabled={dbStatus === 'loading' || loading} onClick={refreshData}>
              <RefreshCcw className={`mr-2 h-4 w-4 ${dbStatus === 'loading' ? 'animate-spin' : ''}`} />
              Reload Data
            </Button>
          </div>
        </div>
      </div>

      <Card className="border-zinc-900 bg-black/30 p-5">
        <div className="grid gap-4 lg:grid-cols-[repeat(2,minmax(0,1fr))_160px_160px] xl:grid-cols-[repeat(4,minmax(0,1fr))]">
          <SelectField label="Symbol" value={filters.symbol} options={options.symbols} onChange={(value) => setFilters((prev) => ({ ...prev, symbol: value }))} />
          <SelectField label="Strategy" value={filters.strategyName} options={options.strategies} onChange={(value) => setFilters((prev) => ({ ...prev, strategyName: value }))} />
          <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
            <span>Start</span>
            <input type="date" value={filters.startDate} onChange={(event) => setFilters((prev) => ({ ...prev, startDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-sky-400" />
          </label>
          <label className="flex min-w-[160px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
            <span>End</span>
            <input type="date" value={filters.endDate} onChange={(event) => setFilters((prev) => ({ ...prev, endDate: event.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-sky-400" />
          </label>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-zinc-400">{rows.length > 0 ? `${rows.length} range definitions in comparison` : 'Waiting for query results'}</div>
        <QueryStatus dbStatus={dbStatus} queryTimeMs={queryTimeMs} totalRecords={rows.length} lastDataUpdate={lastDataUpdate} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <MiniStat label="Best Structural Follow-Through" value={bestAligned ? bestAligned.range_name : '--'} sublabel={bestAligned ? formatPct(bestAligned.aligned_close_rate) : undefined} />
        <MiniStat label="Best Mean Reversion" value={bestMR ? bestMR.range_name : '--'} sublabel={bestMR ? `${formatPct(bestMR.mr_mid_retest_rate)} mid retest` : undefined} />
        <MiniStat label="Best Selected Strategy" value={bestStrategy ? bestStrategy.range_name : '--'} sublabel={bestStrategy ? `${formatPct(bestStrategy.strategy_win_rate)} win rate` : undefined} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Structure</div>
              <h2 className="mt-1 text-lg font-semibold">Follow-through vs mean reversion by range</h2>
            </div>
            <TrendingUp className="h-5 w-5 text-sky-300" />
          </div>

          <div className="h-80 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows}>
                <CartesianGrid vertical={false} stroke="#18181b" />
                <XAxis dataKey="range_name" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                  contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                  formatter={(v: number, key: string) => {
                    if (key === 'aligned_close_rate') return [formatPct(v), 'Aligned close'];
                    if (key === 'mr_mid_retest_rate') return [formatPct(v), 'Mid retest'];
                    return [formatPct(v), 'Failed breakout'];
                  }}
                />
                <Bar dataKey="aligned_close_rate" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                <Bar dataKey="mr_mid_retest_rate" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                <Bar dataKey="failed_breakout_rate" fill="#fb7185" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Selected Strategy</div>
              <h2 className="mt-1 text-lg font-semibold">{filters.strategyName === 'ALL' ? 'All visible strategies' : filters.strategyName} by range</h2>
            </div>
            <div className="text-sm text-sky-300">Avg R comparison</div>
          </div>

          <div className="space-y-3">
            {rows.map((row) => (
              <div key={`strategy-${row.range_name}`} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-zinc-200">{row.range_name}</div>
                    <div className="text-xs text-zinc-500">{Math.round(row.total_ranges).toLocaleString()} sessions</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-fuchsia-300">{formatPct(row.strategy_win_rate)}</div>
                    <div className="text-xs text-zinc-500">Avg R {formatNumber(row.strategy_avg_r)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="border-zinc-900 bg-black/30 p-5">
        <div className="overflow-hidden rounded-xl border border-zinc-900">
          <table className="min-w-full divide-y divide-zinc-900 text-sm">
            <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
              <tr>
                <th className="px-4 py-3 text-left">Range</th>
                <th className="px-4 py-3 text-right">N</th>
                <th className="px-4 py-3 text-right">Avg Width %</th>
                <th className="px-4 py-3 text-right">Aligned Close %</th>
                <th className="px-4 py-3 text-right">Failed %</th>
                <th className="px-4 py-3 text-right">1.0x Hit %</th>
                <th className="px-4 py-3 text-right">Mid Retest %</th>
                <th className="px-4 py-3 text-right">Strategy Win %</th>
                <th className="px-4 py-3 text-right">Strategy Avg R</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 bg-black/20">
              {rows.map((row) => (
                <tr key={row.range_name}>
                  <td className="px-4 py-3 font-medium text-zinc-200">{row.range_name}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.total_ranges).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{formatPct(row.avg_width_pct, 3)}</td>
                  <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.aligned_close_rate)}</td>
                  <td className="px-4 py-3 text-right text-rose-300">{formatPct(row.failed_breakout_rate)}</td>
                  <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.ext_1x_hit_rate)}</td>
                  <td className="px-4 py-3 text-right text-amber-300">{formatPct(row.mr_mid_retest_rate)}</td>
                  <td className="px-4 py-3 text-right text-fuchsia-300">{formatPct(row.strategy_win_rate)}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{formatNumber(row.strategy_avg_r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}