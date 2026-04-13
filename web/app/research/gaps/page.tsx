'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, Clock3, LayoutDashboard, RefreshCcw, SplitSquareVertical, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  direction: string;
  bucket: string;
  filled: string;
  eventDay: string;
  startDate: string;
  endDate: string;
};

type Overview = {
  total_rows: number;
  valid_gap_rows: number;
  fill_rate: number;
  avg_fill_minutes: number | null;
  avg_gap_abs_pct: number;
  continuation_rate: number;
};

type DistRow = {
  label: string;
  count: number;
  fill_rate: number;
};

type WeekdayRow = {
  day_of_week: number;
  n: number;
  fill_rate: number;
  avg_gap_abs_pct: number;
};

type RollingRow = {
  trading_date: string;
  fill_rate_20d: number;
};

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  direction: 'ALL',
  bucket: 'ALL',
  filled: 'ALL',
  eventDay: 'ALL',
  startDate: '',
  endDate: '',
};

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function quote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function buildWhere(filters: FilterState, alias?: string) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];

  if (filters.symbol !== 'ALL') {
    conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  }
  if (filters.direction !== 'ALL') {
    conditions.push(`${prefix}gap_direction = ${quote(filters.direction)}`);
  }
  if (filters.bucket !== 'ALL') {
    conditions.push(`${prefix}gap_size_bucket = ${quote(filters.bucket)}`);
  }
  if (filters.filled === 'YES') {
    conditions.push(`${prefix}gap_filled = true`);
  } else if (filters.filled === 'NO') {
    conditions.push(`${prefix}gap_filled = false`);
  }
  if (filters.eventDay === 'YES') {
    conditions.push(`${prefix}is_event_day = true`);
  } else if (filters.eventDay === 'NO') {
    conditions.push(`${prefix}is_event_day = false`);
  }
  if (filters.startDate) {
    conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  }
  if (filters.endDate) {
    conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);
  }

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
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400"
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

export default function GapAnalyticsPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();
  const [loading, setLoading] = useState(false);

  const [symbols, setSymbols] = useState<string[]>(['ALL']);
  const [buckets, setBuckets] = useState<string[]>(['ALL']);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [directionRows, setDirectionRows] = useState<DistRow[]>([]);
  const [bucketRows, setBucketRows] = useState<DistRow[]>([]);
  const [weekdayRows, setWeekdayRows] = useState<WeekdayRow[]>([]);
  const [rollingRows, setRollingRows] = useState<RollingRow[]>([]);

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('gap_records.parquet', `/api/data/gap_records.parquet?v=${version}`);
      const metaResponse = await fetch(`/api/data/gap_records.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      setLastDataUpdate(metaResponse.headers.get('last-modified'));
      setDbStatus('ready');
    } catch (error) {
      console.error('Failed to initialize gap analytics engine:', error);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  useEffect(() => {
    if (dbStatus !== 'ready') return;

    const loadOptions = async () => {
      const [symbolRows, bucketRowsResult] = await Promise.all([
        runQuery<{ symbol: string }>('SELECT DISTINCT symbol FROM gap_records ORDER BY symbol'),
        runQuery<{ gap_size_bucket: string }>('SELECT DISTINCT gap_size_bucket FROM gap_records ORDER BY gap_size_bucket'),
      ]);
      setSymbols(['ALL', ...symbolRows.map((r) => r.symbol)]);
      setBuckets(['ALL', ...bucketRowsResult.map((r) => r.gap_size_bucket)]);
    };

    loadOptions().catch((error) => {
      console.error('Failed to load gap options:', error);
    });
  }, [dbStatus]);

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;

    setLoading(true);
    const started = performance.now();
    try {
      const where = buildWhere(deferredFilters);
      const gapValidWhere = where
        ? `${where} AND gap_valid = true`
        : 'WHERE gap_valid = true';

      const [overviewRows, directionDistRows, bucketDistRows, weekdayDistRows, rollingDistRows] = await Promise.all([
        runQuery<Overview>(`
          SELECT
            CAST(COUNT(*) AS DOUBLE) AS total_rows,
            CAST(SUM(CASE WHEN gap_valid THEN 1 ELSE 0 END) AS DOUBLE) AS valid_gap_rows,
            CAST(AVG(CASE WHEN gap_valid THEN CASE WHEN gap_filled THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS fill_rate,
            CAST(AVG(CASE WHEN gap_filled THEN gap_fill_time_minutes END) AS DOUBLE) AS avg_fill_minutes,
            CAST(AVG(CASE WHEN gap_valid THEN gap_abs_pct END) AS DOUBLE) AS avg_gap_abs_pct,
            CAST(AVG(CASE WHEN gap_valid THEN CASE WHEN same_as_session_direction THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS continuation_rate
          FROM gap_records
          ${where}
        `),
        runQuery<DistRow>(`
          SELECT
            gap_direction AS label,
            CAST(COUNT(*) AS DOUBLE) AS count,
            CAST(AVG(CASE WHEN gap_filled THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS fill_rate
          FROM gap_records
          ${gapValidWhere}
          GROUP BY gap_direction
          ORDER BY count DESC
        `),
        runQuery<DistRow>(`
          SELECT
            gap_size_bucket AS label,
            CAST(COUNT(*) AS DOUBLE) AS count,
            CAST(AVG(CASE WHEN gap_filled THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS fill_rate
          FROM gap_records
          ${gapValidWhere}
          GROUP BY gap_size_bucket
          ORDER BY CASE gap_size_bucket WHEN 'NONE' THEN 1 WHEN 'SMALL' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END
        `),
        runQuery<WeekdayRow>(`
          SELECT
            day_of_week,
            CAST(COUNT(*) AS DOUBLE) AS n,
            CAST(AVG(CASE WHEN gap_filled THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS fill_rate,
            CAST(AVG(gap_abs_pct) AS DOUBLE) AS avg_gap_abs_pct
          FROM gap_records
          ${gapValidWhere}
          GROUP BY day_of_week
          ORDER BY day_of_week
        `),
        runQuery<RollingRow>(`
          WITH daily AS (
            SELECT
              trading_date,
              CAST(AVG(CASE WHEN gap_filled THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS day_fill_rate
            FROM gap_records
            ${gapValidWhere}
            GROUP BY trading_date
          )
          SELECT
            trading_date,
            CAST(AVG(day_fill_rate) OVER (ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS DOUBLE) AS fill_rate_20d
          FROM daily
          ORDER BY trading_date
        `),
      ]);

      setOverview((overviewRows[0] as Overview) ?? null);
      setDirectionRows(directionDistRows);
      setBucketRows(bucketDistRows);
      setWeekdayRows(weekdayDistRows);
      setRollingRows(rollingDistRows);
      setQueryTimeMs(performance.now() - started);
    } catch (error) {
      console.error('Failed to query gap dashboard:', error);
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

  const totalRecords = useMemo(() => overview?.valid_gap_rows ?? overview?.total_rows, [overview]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.1),_transparent_30%),radial-gradient(circle_at_bottom_right,_rgba(251,191,36,0.12),_transparent_28%),#050816] text-zinc-100">
      <div className="mx-auto w-full max-w-[1500px] space-y-8 px-6 py-8">
        <div className="flex flex-col gap-5 border-b border-zinc-900 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <Link href="/research" className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-cyan-300">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Research Hub
            </Link>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-cyan-300">
                <SplitSquareVertical className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight">Gap Analytics</h1>
                <p className="mt-1 max-w-2xl text-sm text-zinc-400">
                  Gap-fill behavior by direction, size bucket, day-of-week, and event context.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 lg:items-end">
            <QueryStatus dbStatus={dbStatus} queryTimeMs={queryTimeMs} totalRecords={totalRecords} lastDataUpdate={lastDataUpdate} />
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

        <Card className="border-zinc-900 bg-black/30 p-5 backdrop-blur-sm">
          <div className="grid gap-4 lg:grid-cols-[repeat(5,minmax(0,1fr))_140px_140px]">
            <SelectField label="Symbol" value={filters.symbol} options={symbols} onChange={(value) => setFilters((x) => ({ ...x, symbol: value }))} />
            <SelectField label="Direction" value={filters.direction} options={['ALL', 'UP', 'DOWN']} onChange={(value) => setFilters((x) => ({ ...x, direction: value }))} />
            <SelectField label="Bucket" value={filters.bucket} options={buckets} onChange={(value) => setFilters((x) => ({ ...x, bucket: value }))} />
            <SelectField label="Gap Filled" value={filters.filled} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((x) => ({ ...x, filled: value }))} />
            <SelectField label="Event Day" value={filters.eventDay} options={['ALL', 'YES', 'NO']} onChange={(value) => setFilters((x) => ({ ...x, eventDay: value }))} />
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>Start</span>
              <input type="date" value={filters.startDate} onChange={(e) => setFilters((x) => ({ ...x, startDate: e.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400" />
            </label>
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>End</span>
              <input type="date" value={filters.endDate} onChange={(e) => setFilters((x) => ({ ...x, endDate: e.target.value }))} className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400" />
            </label>
          </div>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MiniStat label="Sample" value={overview ? `${Math.round(overview.valid_gap_rows).toLocaleString()} gaps` : '--'} />
          <MiniStat label="Gap Fill Rate" value={overview ? `${overview.fill_rate?.toFixed(1)}%` : '--'} />
          <MiniStat label="Avg Fill Time" value={overview?.avg_fill_minutes != null ? `${overview.avg_fill_minutes.toFixed(1)}m` : '--'} />
          <MiniStat label="Avg Abs Gap" value={overview ? `${overview.avg_gap_abs_pct?.toFixed(3)}%` : '--'} />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Direction Fill Rates</h2>
              <TrendingUp className="h-5 w-5 text-emerald-300" />
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={directionRows}>
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis dataKey="label" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }} />
                  <Bar dataKey="fill_rate" fill="#34d399" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Bucket Fill Rates</h2>
              <LayoutDashboard className="h-5 w-5 text-amber-300" />
            </div>
            <div className="space-y-3">
              {bucketRows.map((row) => (
                <div key={row.label} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span>{row.label}</span>
                    <span className="text-amber-300">{row.fill_rate.toFixed(1)}%</span>
                  </div>
                  <div className="mb-1 h-2 overflow-hidden rounded-full bg-zinc-900">
                    <div className="h-full rounded-full bg-amber-400" style={{ width: `${Math.max(0, Math.min(100, row.fill_rate))}%` }} />
                  </div>
                  <div className="text-xs text-zinc-500">N={Math.round(row.count).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Weekday Matrix</h2>
              <Clock3 className="h-5 w-5 text-cyan-300" />
            </div>
            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">DOW</th>
                    <th className="px-4 py-3 text-right">N</th>
                    <th className="px-4 py-3 text-right">Fill %</th>
                    <th className="px-4 py-3 text-right">Avg Abs Gap %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {weekdayRows.map((row) => (
                    <tr key={row.day_of_week}>
                      <td className="px-4 py-3 text-zinc-200">{DOW_LABELS[row.day_of_week] ?? `D${row.day_of_week}`}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.n).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{row.fill_rate.toFixed(1)}%</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{row.avg_gap_abs_pct.toFixed(3)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Rolling 20D Fill Probability</h2>
              <TrendingUp className="h-5 w-5 text-fuchsia-300" />
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rollingRows}>
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis dataKey="trading_date" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
                  <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }} />
                  <Line type="monotone" dataKey="fill_rate_20d" stroke="#e879f9" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
