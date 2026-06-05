'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, BarChart2, RefreshCcw, TrendingDown, TrendingUp, Waves, Zap } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

// ─── Types ─────────────────────────────────────────────────────────────────────

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  sessionSlot: string;
  timeBasis: string;
  dow: string;
  startDate: string;
  endDate: string;
};

type Overview = {
  sample: number;
  avg_range_pct: number;
  break_high_rate: number;
  break_low_rate: number;
  double_break_rate: number;
  false_break_high_rate: number;
  false_break_low_rate: number;
  mode_first_break_time: string | null;
};

type BiasRow = {
  metric: string;
  bull_rate: number;
  bear_rate: number;
  n: number;
};

type PlayRow = {
  play: number;
  win_rate: number;
  avg_mfe: number;
  avg_mae: number;
  avg_rr: number;
  n: number;
};

type ExtRow = {
  level: number;
  up_hit_rate: number;
  down_hit_rate: number;
  n: number;
};

type TouchRow = {
  phase: string;
  avg_touch_count: number;
  n: number;
};

type FvgRow = {
  direction: string;
  touch_rate: number;
  held_rate: number;
  inverted_rate: number;
  n: number;
};

type RangeBucketRow = {
  bucket: string;
  n: number;
  break_rate: number;
  double_break_rate: number;
};

type TimingRow = {
  bucket: string;
  play1_n: number;
};

// ─── Constants ─────────────────────────────────────────────────────────────────

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  sessionSlot: 'ALL',
  timeBasis: 'ALL',
  dow: 'ALL',
  startDate: '',
  endDate: '',
};

const SESSION_SLOTS = [
  'ALL',
  'Globex IB',
  'Tokyo IB',
  'London IB',
  'Midnight OR',
  'NY AM IB',
  'NY PM IB',
];

const DOW_OPTIONS = ['ALL', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

const CORE_SYMBOLS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'CL1', 'GC1'];

const TABLE_NAMES = [
  'ib_facts',
  'ib_ext_detail',
  'ib_play_detail',
  'ib_level_touch_detail',
  'ib_fvg_detail',
];

// ─── Helpers ───────────────────────────────────────────────────────────────────

function q(v: string) {
  return `'${v.replace(/'/g, "''")}'`;
}

function buildWhere(filters: FilterState, table = 'ib_facts') {
  const p = `${table}.`;
  const conds: string[] = [];
  if (filters.symbol !== 'ALL') conds.push(`${p}symbol = ${q(filters.symbol)}`);
  if (filters.sessionSlot !== 'ALL') conds.push(`${p}session_slot = ${q(filters.sessionSlot)}`);
  if (filters.timeBasis !== 'ALL') conds.push(`${p}time_basis = ${q(filters.timeBasis)}`);
  if (filters.dow !== 'ALL') conds.push(`${p}dow = ${q(filters.dow)}`);
  if (filters.startDate) conds.push(`${p}trading_day >= ${q(filters.startDate)}`);
  if (filters.endDate) conds.push(`${p}trading_day <= ${q(filters.endDate)}`);
  return conds.length > 0 ? `WHERE ${conds.join(' AND ')}` : '';
}

function buildWhereAliasless(filters: FilterState) {
  const conds: string[] = [];
  if (filters.symbol !== 'ALL') conds.push(`symbol = ${q(filters.symbol)}`);
  if (filters.sessionSlot !== 'ALL') conds.push(`session_slot = ${q(filters.sessionSlot)}`);
  if (filters.timeBasis !== 'ALL') conds.push(`time_basis = ${q(filters.timeBasis)}`);
  if (filters.startDate) conds.push(`trading_day >= ${q(filters.startDate)}`);
  if (filters.endDate) conds.push(`trading_day <= ${q(filters.endDate)}`);
  return conds.length > 0 ? `WHERE ${conds.join(' AND ')}` : '';
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex min-w-[140px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
      <span>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o === 'ALL' ? 'All' : o}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card className="border-zinc-900 bg-zinc-950/70 p-4">
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className={`mt-2 text-xl font-semibold ${accent ?? 'text-zinc-100'}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-zinc-500">{sub}</div>}
    </Card>
  );
}

function SectionHeader({
  icon,
  title,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  color: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <span className={color}>{icon}</span>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function IBStatsPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();
  const [loading, setLoading] = useState(false);

  const [symbols, setSymbols] = useState<string[]>(['ALL']);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [biasRows, setBiasRows] = useState<BiasRow[]>([]);
  const [playRows, setPlayRows] = useState<PlayRow[]>([]);
  const [extRows, setExtRows] = useState<ExtRow[]>([]);
  const [touchRows, setTouchRows] = useState<TouchRow[]>([]);
  const [fvgRows, setFvgRows] = useState<FvgRow[]>([]);
  const [rangeBucketRows, setRangeBucketRows] = useState<RangeBucketRow[]>([]);
  const [timingRows, setTimingRows] = useState<TimingRow[]>([]);

  // ── Engine init ───────────────────────────────────────────────────────────────

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const v = Date.now();
      let lastMod: string | null = null;
      
      for (const table of TABLE_NAMES) {
        const loadedSymbols = [];
        for (const sym of CORE_SYMBOLS) {
          const fileName = `${table}_${sym}.parquet`;
          try {
            await loadParquet(fileName, `/api/data/${fileName}?v=${v}`);
            loadedSymbols.push(sym);
            if (!lastMod) {
              const r = await fetch(`/api/data/${fileName}?v=${v}`, { headers: { Range: 'bytes=0-0' } });
              lastMod = r.headers.get('last-modified');
            }
          } catch (e) {
            console.warn(`File not found or failed to load: ${fileName}`);
          }
        }
        
        if (loadedSymbols.length > 0) {
          const unionQuery = loadedSymbols.map(sym => `SELECT * FROM ${table}_${sym}`).join(' UNION ALL ');
          await runQuery(`CREATE OR REPLACE VIEW ${table} AS ${unionQuery}`);
        } else {
           console.warn(`No symbols loaded for table ${table}`);
        }
      }

      setLastDataUpdate(lastMod);
      setDbStatus('ready');
    } catch (err) {
      console.error('IB Stats engine init failed:', err);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  // ── Populate symbol options ───────────────────────────────────────────────────

  useEffect(() => {
    if (dbStatus !== 'ready') return;
    runQuery<{ symbol: string }>('SELECT DISTINCT symbol FROM ib_facts ORDER BY symbol')
      .then((rows) => setSymbols(['ALL', ...rows.map((r) => r.symbol)]))
      .catch(console.error);
  }, [dbStatus]);

  // ── Main query ────────────────────────────────────────────────────────────────

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;
    setLoading(true);
    const started = performance.now();
    const where = buildWhere(deferredFilters);
    const whereAl = buildWhereAliasless(deferredFilters);

    try {
      const [
        overviewRows,
        biasData,
        playData,
        extData,
        touchData,
        fvgData,
        bucketData,
      ] = await Promise.all([
        // Overview
        runQuery<Overview>(`
          SELECT
            CAST(COUNT(*) AS DOUBLE) AS sample,
            CAST(AVG(range_pct) AS DOUBLE) AS avg_range_pct,
            CAST(AVG(CASE WHEN first_break_dir = 1 OR (first_break_dir = -1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_high_rate,
            CAST(AVG(CASE WHEN first_break_dir = -1 OR (first_break_dir = 1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_low_rate,
            CAST(AVG(CASE WHEN double_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS double_break_rate,
            CAST(AVG(CASE WHEN false_break_high THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS false_break_high_rate,
            CAST(AVG(CASE WHEN false_break_low THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS false_break_low_rate,
            MODE(first_break_bucket) AS mode_first_break_time
          FROM ib_facts
          ${where}
        `),

        // Directional bias accuracy (firstreach, lasttouch, close_dir, fvg)
        runQuery<{ metric: string; bull_rate: number; bear_rate: number; n: number }>(`
          SELECT
            'First Reach' AS metric,
            CAST(AVG(CASE WHEN bias_formation_firstreach = 1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bull_rate,
            CAST(AVG(CASE WHEN bias_formation_firstreach = -1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bear_rate,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'Last Touch' AS metric,
            CAST(AVG(CASE WHEN bias_formation_lasttouch = 1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bull_rate,
            CAST(AVG(CASE WHEN bias_formation_lasttouch = -1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bear_rate,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'Close Direction' AS metric,
            CAST(AVG(CASE WHEN bias_close_dir = 1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bull_rate,
            CAST(AVG(CASE WHEN bias_close_dir = -1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bear_rate,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'FVG Bias' AS metric,
            CAST(AVG(CASE WHEN bias_fvg = 1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bull_rate,
            CAST(AVG(CASE WHEN bias_fvg = -1 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bear_rate,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
        `),

        // Plays P1 / P2 / P3
        runQuery<{ play: number; win_rate: number; avg_mfe: number; avg_mae: number; avg_rr: number; n: number }>(`
          SELECT
            CAST(play AS DOUBLE) AS play,
            CAST(SUM(CASE WHEN result = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS win_rate,
            CAST(AVG(mfe) AS DOUBLE) AS avg_mfe,
            CAST(AVG(mae) AS DOUBLE) AS avg_mae,
            CAST(AVG(CASE WHEN mae > 0 THEN mfe / mae ELSE NULL END) AS DOUBLE) AS avg_rr,
            CAST(SUM(CASE WHEN result != 0 THEN 1 ELSE 0 END) AS DOUBLE) AS n
          FROM ib_play_detail
          ${whereAl}
          GROUP BY play
          ORDER BY play
        `),

        // Extension levels
        runQuery<{ level: number; up_hit_rate: number; down_hit_rate: number; n: number }>(`
          SELECT
            CAST(level AS DOUBLE) AS level,
            CAST(AVG(CASE WHEN side = 'up' AND hit THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS up_hit_rate,
            CAST(AVG(CASE WHEN side = 'down' AND hit THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS down_hit_rate,
            CAST(COUNT(DISTINCT trading_day || session_slot) AS DOUBLE) AS n
          FROM ib_ext_detail
          ${whereAl}
          GROUP BY level
          ORDER BY level
        `),

        // Level touches by phase
        runQuery<{ phase: string; avg_touch_count: number; n: number }>(`
          SELECT
            phase,
            CAST(AVG(touch_count) AS DOUBLE) AS avg_touch_count,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_level_touch_detail
          ${whereAl}
          GROUP BY phase
          ORDER BY phase
        `),

        // FVG reuse & inversion
        runQuery<{ direction: string; touch_rate: number; held_rate: number; inverted_rate: number; n: number }>(`
          SELECT
            CASE WHEN dir = 1 THEN 'Bullish' ELSE 'Bearish' END AS direction,
            CAST(AVG(CASE WHEN touch_time IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            CAST(AVG(CASE WHEN reaction = 'held' THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS held_rate,
            CAST(AVG(CASE WHEN inverted THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS inverted_rate,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_fvg_detail
          ${whereAl}
          GROUP BY dir
          ORDER BY dir DESC
        `),

        // Range bucket breakdown
        runQuery<{ bucket: string; n: number; break_rate: number; double_break_rate: number }>(`
          SELECT
            range_bucket_full AS bucket,
            CAST(COUNT(*) AS DOUBLE) AS n,
            CAST(AVG(CASE WHEN first_break_dir != 0 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_rate,
            CAST(AVG(CASE WHEN double_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS double_break_rate
          FROM ib_facts
          ${where}
          GROUP BY range_bucket_full
          ORDER BY CASE range_bucket_full WHEN 'Small' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        `),

        // Timing histogram
        runQuery<TimingRow>(`
          SELECT
            first_break_bucket AS bucket,
            CAST(COUNT(*) AS DOUBLE) AS play1_n
          FROM ib_facts
          ${where}
          AND first_break_bucket IS NOT NULL
          GROUP BY first_break_bucket
          ORDER BY first_break_bucket
        `),
      ]);

      setOverview(overviewRows[0] ?? null);
      setBiasRows(biasData as BiasRow[]);
      setPlayRows(playData as PlayRow[]);
      setExtRows(extData as ExtRow[]);
      setTouchRows(touchData as TouchRow[]);
      setFvgRows(fvgData as FvgRow[]);
      setRangeBucketRows(bucketData as RangeBucketRow[]);
      setTimingRows(bucketData[7] ? (bucketData[7] as unknown as TimingRow[]) : (bucketData as any)[7] as TimingRow[]);
      setQueryTimeMs(performance.now() - started);
    } catch (err) {
      console.error('IB Stats dashboard query failed:', err);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const refreshData = useCallback(async () => {
    await resetDuckDB();
    await loadEngine();
  }, [loadEngine]);

  const totalRecords = useMemo(() => overview?.sample, [overview]);

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.08),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.1),_transparent_26%),#050816] text-zinc-100">
      <div className="mx-auto w-full max-w-[1600px] space-y-8 px-6 py-8">
        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex flex-col gap-5 border-b border-zinc-900 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <Link
              href="/research"
              className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-amber-300"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Research Hub
            </Link>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-3 text-amber-300">
                <BarChart2 className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight">IB Stats</h1>
                <p className="mt-1 max-w-2xl text-sm text-zinc-400">
                  Multi-session Initial Balance analytics — breakouts, bias formation, plays, extensions, level touches, and FVG behaviour.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 lg:items-end">
            <QueryStatus
              dbStatus={dbStatus}
              queryTimeMs={queryTimeMs}
              totalRecords={totalRecords}
              lastDataUpdate={lastDataUpdate}
            />
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-800 bg-zinc-950 text-zinc-100 hover:bg-zinc-900"
              disabled={dbStatus === 'loading' || loading}
              onClick={refreshData}
            >
              <RefreshCcw className={`mr-2 h-4 w-4 ${dbStatus === 'loading' ? 'animate-spin' : ''}`} />
              Refresh Parquet
            </Button>
          </div>
        </div>

        {/* ── Filters ────────────────────────────────────────────────────────── */}
        <Card className="border-zinc-900 bg-black/30 p-5 backdrop-blur-sm">
          <div className="flex flex-wrap gap-4">
            <SelectField
              label="Symbol"
              value={filters.symbol}
              options={symbols}
              onChange={(v) => setFilters((x) => ({ ...x, symbol: v }))}
            />
            <SelectField
              label="Session Slot"
              value={filters.sessionSlot}
              options={SESSION_SLOTS}
              onChange={(v) => setFilters((x) => ({ ...x, sessionSlot: v }))}
            />
            <SelectField
              label="Time Basis"
              value={filters.timeBasis}
              options={['ALL', 'ET_fixed', 'event_anchored']}
              onChange={(v) => setFilters((x) => ({ ...x, timeBasis: v }))}
            />
            <SelectField
              label="Day of Week"
              value={filters.dow}
              options={DOW_OPTIONS}
              onChange={(v) => setFilters((x) => ({ ...x, dow: v }))}
            />
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>Start</span>
              <input
                type="date"
                value={filters.startDate}
                onChange={(e) => setFilters((x) => ({ ...x, startDate: e.target.value }))}
                className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400"
              />
            </label>
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>End</span>
              <input
                type="date"
                value={filters.endDate}
                onChange={(e) => setFilters((x) => ({ ...x, endDate: e.target.value }))}
                className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-amber-400"
              />
            </label>
          </div>
        </Card>

        {/* ── Overview Stats ─────────────────────────────────────────────────── */}
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
          <StatCard
            label="Sample"
            value={overview ? Math.round(overview.sample).toLocaleString() : '--'}
            sub="sessions"
          />
          <StatCard
            label="Avg Range %"
            value={overview ? `${(overview.avg_range_pct ?? 0).toFixed(2)}%` : '--'}
            accent="text-amber-300"
          />
          <StatCard
            label="Break High"
            value={overview ? `${(overview.break_high_rate ?? 0).toFixed(1)}%` : '--'}
            accent="text-emerald-300"
          />
          <StatCard
            label="Break Low"
            value={overview ? `${(overview.break_low_rate ?? 0).toFixed(1)}%` : '--'}
            accent="text-rose-300"
          />
          <StatCard
            label="Double Break"
            value={overview ? `${(overview.double_break_rate ?? 0).toFixed(1)}%` : '--'}
            accent="text-fuchsia-300"
          />
          <StatCard
            label="False Break ▲"
            value={overview ? `${(overview.false_break_high_rate ?? 0).toFixed(1)}%` : '--'}
            accent="text-orange-300"
          />
          <StatCard
            label="Break Time (Mode)"
            value={overview?.mode_first_break_time ?? '--'}
            sub="EST Clock Time"
          />
        </div>

        {/* ── 0: SUGGESTED (Placeholder) ─────────────────────────────────────── */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <SectionHeader
            icon={<Zap className="h-5 w-5" />}
            title="SUGGESTED"
            color="text-amber-300"
          />
          <div className="text-sm text-zinc-400 italic">
            [Placeholder] Algorithmic one-line synthesis will be displayed here based on highest-expectancy bias direction.
          </div>
        </Card>

        {/* ── ① DIRECTION ───────────────────────────────────────────────────── */}
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr] mt-6">
          {/* Directional Bias */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<TrendingUp className="h-5 w-5" />}
              title="① DIRECTION: Bias Formation"
              color="text-emerald-300"
            />
            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Metric</th>
                    <th className="px-4 py-3 text-right">Bullish %</th>
                    <th className="px-4 py-3 text-right">Bearish %</th>
                    <th className="px-4 py-3 text-right">N</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {biasRows.map((row) => (
                    <tr key={row.metric}>
                      <td className="px-4 py-3 text-zinc-200">{row.metric}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">
                        {(row.bull_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right text-rose-300">
                        {(row.bear_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-500">
                        {Math.round(row.n).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* FVG Reuse (Moved here for Direction context) */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<Zap className="h-5 w-5" />}
              title="FVG Reuse & Inversion"
              color="text-violet-300"
            />
            <div className="grid gap-6">
              {fvgRows.map((row) => (
                <div key={row.direction} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                  <div className="mb-3 text-sm font-semibold text-zinc-200">
                    {row.direction} FVG
                    <span className="ml-2 text-xs text-zinc-500">N={Math.round(row.n).toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    {[
                      { label: 'Touch Rate', value: row.touch_rate, color: 'text-sky-300' },
                      { label: 'Held Rate', value: row.held_rate, color: 'text-emerald-300' },
                      { label: 'Inverted', value: row.inverted_rate, color: 'text-violet-300' },
                    ].map(({ label, value, color }) => (
                      <div key={label}>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">{label}</div>
                        <div className={`mt-1 text-xl font-semibold ${color}`}>{value.toFixed(1)}%</div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-900">
                          <div
                            className={`h-full rounded-full ${
                              color === 'text-sky-300'
                                ? 'bg-sky-400'
                                : color === 'text-emerald-300'
                                ? 'bg-emerald-400'
                                : 'bg-violet-400'
                            }`}
                            style={{ width: `${Math.min(100, value)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ── ② FAKE-OUT ─────────────────────────────────────────────────────── */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <SectionHeader
            icon={<TrendingDown className="h-5 w-5" />}
            title="② FAKE-OUT & BREAKS"
            color="text-orange-300"
          />
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
            <StatCard
              label="Double Break"
              value={overview ? `${(overview.double_break_rate ?? 0).toFixed(1)}%` : '--'}
              accent="text-fuchsia-300"
            />
            <StatCard
              label="False Break ▲"
              value={overview ? `${(overview.false_break_high_rate ?? 0).toFixed(1)}%` : '--'}
              accent="text-orange-300"
            />
            <StatCard
              label="False Break ▼"
              value={overview ? `${(overview.false_break_low_rate ?? 0).toFixed(1)}%` : '--'}
              accent="text-orange-300"
            />
          </div>
        </Card>

        {/* ── PLAYS ──────────────────────────────────────────────────────────── */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <SectionHeader
            icon={<Zap className="h-5 w-5" />}
            title="PLAYS Performance (P1 / P2 / P3)"
            color="text-cyan-300"
          />
          <div className="grid gap-6 lg:grid-cols-3">
            {playRows.map((play) => {
              const colorClass =
                play.play === 1
                  ? 'text-cyan-300'
                  : play.play === 2
                  ? 'text-sky-300'
                  : 'text-indigo-300';
              const barColor =
                play.play === 1 ? '#67e8f9' : play.play === 2 ? '#7dd3fc' : '#a5b4fc';

              return (
                <div key={play.play} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                  <div className={`mb-3 text-xs font-semibold uppercase tracking-[0.2em] ${colorClass}`}>
                    Play {play.play}
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Win Rate</div>
                      <div className={`mt-1 text-xl font-semibold ${colorClass}`}>
                        {(play.win_rate ?? 0).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Avg R:R</div>
                      <div className="mt-1 text-xl font-semibold text-zinc-100">
                        {play.avg_rr != null ? (play.avg_rr).toFixed(2) : '--'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Avg MFE</div>
                      <div className="mt-1 text-lg font-medium text-emerald-300">
                        {(play.avg_mfe ?? 0).toFixed(1)} pts
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Avg MAE</div>
                      <div className="mt-1 text-lg font-medium text-rose-300">
                        {(play.avg_mae ?? 0).toFixed(1)} pts
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={[
                          { label: 'Win', value: play.win_rate },
                          { label: 'Loss', value: 100 - play.win_rate },
                        ]}
                      >
                        <XAxis dataKey="label" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis hide domain={[0, 100]} />
                        <Tooltip
                          contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 10 }}
                          formatter={(v: number) => [`${v.toFixed(1)}%`]}
                        />
                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                          <Cell fill={barColor} />
                          <Cell fill="#27272a" />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-1 text-right text-xs text-zinc-500">
                    N={Math.round(play.n).toLocaleString()}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Histogram */}
          {timingRows.length > 0 && (
            <div className="mt-6 border-t border-zinc-900 pt-6">
              <div className="mb-4 text-sm font-semibold text-zinc-200">Play 1 Entry Timing Distribution (EST)</div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={timingRows} barCategoryGap="5%">
                    <CartesianGrid vertical={false} stroke="#18181b" />
                    <XAxis
                      dataKey="bucket"
                      tick={{ fill: '#71717a', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      interval="preserveStartEnd"
                      minTickGap={20}
                    />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
                      formatter={(v: number) => [v, 'Occurrences']}
                      labelStyle={{ color: '#a1a1aa' }}
                    />
                    <Bar dataKey="play1_n" name="Frequency" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Card>

        {/* ── ③ TARGETS ─────────────────────────────────────────────────────── */}
        <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr] mt-6">
          {/* Extension Levels */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<TrendingDown className="h-5 w-5" />}
              title="③ TARGETS: Extension Hit Rates"
              color="text-sky-300"
            />
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={extRows} barCategoryGap="20%">
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis
                    dataKey="level"
                    tick={{ fill: '#a1a1aa', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `${v}×`}
                  />
                  <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
                  <Tooltip
                    contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                    formatter={(v: number) => [`${v.toFixed(1)}%`]}
                  />
                  <Bar dataKey="up_hit_rate" name="Up Hit %" fill="#34d399" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="down_hit_rate" name="Down Hit %" fill="#f87171" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Level Touch Phases */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<Waves className="h-5 w-5" />}
              title="Level Touch by Phase"
              color="text-fuchsia-300"
            />
            <div className="space-y-3">
              {touchRows.map((row) => (
                <div key={row.phase} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-zinc-300">
                      {row.phase.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <span className="text-fuchsia-300">{row.avg_touch_count.toFixed(2)} avg</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                    <div
                      className="h-full rounded-full bg-fuchsia-400"
                      style={{ width: `${Math.min(100, (row.avg_touch_count / 5) * 100)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">N={Math.round(row.n).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ── ④ DAY TYPE & RANGE Δ ─────────────────────────────────────────── */}
        <div className="grid gap-6 xl:grid-cols-2 mt-6">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<Waves className="h-5 w-5" />}
              title="④ DAY TYPE & RANGE Δ: Size Distribution"
              color="text-amber-300"
            />
            <div className="space-y-4">
              {rangeBucketRows.map((row) => (
                <div key={row.bucket} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
                  <div className="mb-2 flex items-center justify-between text-sm font-medium">
                    <span className="text-zinc-200">{row.bucket}</span>
                    <span className="text-xs text-zinc-500">N={Math.round(row.n).toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">Break Rate</div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                        <div
                          className="h-full rounded-full bg-amber-400"
                          style={{ width: `${Math.min(100, row.break_rate ?? 0)}%` }}
                        />
                      </div>
                      <div className="mt-1 text-xs text-amber-300">{(row.break_rate ?? 0).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">Double Break</div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                        <div
                          className="h-full rounded-full bg-fuchsia-400"
                          style={{ width: `${Math.min(100, row.double_break_rate ?? 0)}%` }}
                        />
                      </div>
                      <div className="mt-1 text-xs text-fuchsia-300">{(row.double_break_rate ?? 0).toFixed(1)}%</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
