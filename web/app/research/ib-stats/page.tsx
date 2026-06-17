'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState, memo } from 'react';
import Link from 'next/link';
import { ArrowLeft, BarChart2, RefreshCcw, TrendingDown, TrendingUp, Waves, Zap, Maximize2, HelpCircle } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Brush,
} from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

// ΓöÇΓöÇΓöÇ Types ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

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
  false_break_rate: number;
  mode_first_break_time: string | null;
};

type BiasRow = {
  metric: string;
  dir_pct: number;
  hit_05: number;
  hit_1: number;
  lift_dir: number;
  lift_tgt: number;
  base_dir: number;
  base_up05: number;
  base_dn05: number;
  is_baseline: number;
  n: number;
};

type ConflictRow = {
  pair_label: string;
  a_name: string;
  b_name: string;
  n_conflict: number;
  winA: number;
  winB: number;
  winner: string;
  edge: number;
};

type NoSignalRow = {
  variant: string;
  n_absent: number;
  chop_rate_absent: number;
  chop_rate_all: number;
};

type AgreementRow = {
  bucket: string;
  accuracy: number;
  n: number;
};

type PlayRow = {
  play: number;
  win_rate: number;
  stop_loss_rate: number;
  timeout_loss_rate: number;
  no_setup_rate: number;
  avg_mfe: number;
  avg_mae: number;
  expectancy: number;
  setup_rate: number;
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
  metric: string;
  touch_rate: number;
  median_mins: number | null;
  n: number;
};

type RangeBucketRow = {
  bucket: string;
  n: number;
  break_high_rate: number;
  break_low_rate: number;
  double_break_rate: number;
};

type TimingRow = {
  bucket: string;
  play1_n: number;
};

// ΓöÇΓöÇΓöÇ Constants ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

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
];

type IbIndexResponse = {
  symbols?: string[];
  tables?: Record<string, string[]>;
};

// ΓöÇΓöÇΓöÇ Helpers ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

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

function formatTimeFromMicroseconds(val: any): string {
  if (val == null) return '--';
  const valStr = val.toString().trim();
  if (!valStr) return '--';
  
  if (valStr.includes(':')) {
    const parts = valStr.split(':');
    return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  }
  
  const num = parseInt(valStr, 10);
  if (isNaN(num)) return valStr;
  
  const totalSeconds = Math.floor(num / 1000000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  
  const hStr = hours.toString().padStart(2, '0');
  const mStr = minutes.toString().padStart(2, '0');
  return `${hStr}:${mStr}`;
}

function formatTimeFromValue(val: any): string {
  if (val == null) return '00:00';
  const valStr = val.toString().trim();
  if (valStr.includes(':')) {
    const parts = valStr.split(':');
    return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  }
  const num = parseInt(valStr, 10);
  if (isNaN(num)) return '00:00';
  const totalSeconds = Math.floor(num / 1000000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

function timeToMinutes(timeStr: any): number {
  if (timeStr == null) return 0;
  const str = typeof timeStr === 'string' ? timeStr : String(timeStr);
  const parts = str.split(':');
  if (parts.length < 2) return 0;
  const h = Number(parts[0]) || 0;
  const m = Number(parts[1]) || 0;
  return h * 60 + m;
}

function minutesToTime(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function roundToBucket(timeStr: string, granularity: number): string {
  const mins = timeToMinutes(timeStr);
  const rounded = Math.floor(mins / granularity) * granularity;
  return minutesToTime(rounded);
}

function formatTimeFromEpoch(epochVal: number | null): string {
  if (epochVal == null || isNaN(epochVal)) return '--';
  const totalSecs = Math.floor(epochVal);
  const h = Math.floor((totalSecs / 3600) % 24);
  const m = Math.floor((totalSecs % 3600) / 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function TooltipHelp({ text }: { text: string }) {
  return (
    <div className="group relative inline-block ml-1">
      <HelpCircle className="h-3.5 w-3.5 text-zinc-500 cursor-pointer hover:text-zinc-300" />
      <div className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg bg-zinc-950 border border-zinc-800 p-2 text-xs text-zinc-300 opacity-0 shadow-xl transition-opacity group-hover:opacity-100 font-normal normal-case tracking-normal">
        {text}
      </div>
    </div>
  );
}

const TimingInnerChart = memo(function TimingInnerChart({ data, granularity }: { data: any[], granularity: number }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
        <CartesianGrid vertical={false} stroke="#18181b" />
        <XAxis
          dataKey="time"
          fontSize={11}
          tick={{ fill: '#71717a' }}
          interval={0}
          ticks={Array.from(new Set(data
            .filter(d => {
              const [h, m] = d.time.split(':').map(Number);
              if (granularity >= 60) return true;
              if (granularity === 30) return m === 0;
              if (granularity === 15) return m === 0 || m === 30;
              return m % 15 === 0;
            })
            .map(d => d.time)
          ))}
          angle={-45}
          textAnchor="end"
          height={50}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          fontSize={11}
          tick={{ fill: '#71717a' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
          formatter={(v: number) => [v, 'Occurrences']}
          labelStyle={{ color: '#a1a1aa' }}
        />
        <Bar dataKey="count" name="Frequency" fill="#38bdf8" radius={[4, 4, 0, 0]} />
        <Brush
          dataKey="time"
          height={20}
          stroke="#38bdf8"
          travellerWidth={10}
          alwaysShowText={false}
          fill="#09090b"
        />
      </BarChart>
    </ResponsiveContainer>
  );
});

// ΓöÇΓöÇΓöÇ Sub-components ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

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

// ΓöÇΓöÇΓöÇ Page ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

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
  const [conflictRows, setConflictRows] = useState<ConflictRow[]>([]);
  const [noSignalRows, setNoSignalRows] = useState<NoSignalRow[]>([]);
  const [agreementRows, setAgreementRows] = useState<AgreementRow[]>([]);
  const [playRows, setPlayRows] = useState<PlayRow[]>([]);
  const [extRows, setExtRows] = useState<ExtRow[]>([]);
  const [touchRows, setTouchRows] = useState<TouchRow[]>([]);
  const [fvgRows, setFvgRows] = useState<FvgRow[]>([]);
  const [rangeBucketRows, setRangeBucketRows] = useState<RangeBucketRow[]>([]);
  const [timingRows, setTimingRows] = useState<TimingRow[]>([]);
  const [dstRows, setDstRows] = useState<any[]>([]);
  const [levelTouchOutcomeRows, setLevelTouchOutcomeRows] = useState<any[]>([]);
  const [frontRunStats, setFrontRunStats] = useState<{ rate: number; median_mins: number | null; mode_mins: number | null } | null>(null);
  const [granularity, setGranularity] = useState<number>(5);
  const [isExpanded, setIsExpanded] = useState(false);
  
  const [biasTargetLvl, setBiasTargetLvl] = useState<string>('0.5');
  const [playTargetLvl, setPlayTargetLvl] = useState<string>('0.5');
  const [withBiasFilter, setWithBiasFilter] = useState<string>('all');
  const [realizedDirMethod, setRealizedDirMethod] = useState<'break' | 'close' | 'ext'>('break');

  // ΓöÇΓöÇ Engine init ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const v = Date.now();
      let lastMod: string | null = null;
      let symbolsToLoad = CORE_SYMBOLS;
      const tableSymbolsToLoad: Record<string, string[]> = {};

      try {
        const r = await fetch(`/api/data/ib-index?v=${v}`);
        if (r.ok) {
          const idx = (await r.json()) as IbIndexResponse;
          if (Array.isArray(idx.symbols) && idx.symbols.length > 0) {
            symbolsToLoad = idx.symbols;
          }
          if (idx.tables && typeof idx.tables === 'object') {
            for (const [table, syms] of Object.entries(idx.tables)) {
              if (Array.isArray(syms) && syms.length > 0) {
                tableSymbolsToLoad[table] = syms;
              }
            }
          }
        }
      } catch {
        // Fall back to CORE_SYMBOLS if index discovery fails.
      }

      const firstProbeFile = `ib_facts_${symbolsToLoad[0] ?? CORE_SYMBOLS[0]}.parquet`;
      try {
        const r = await fetch(`/api/data/${firstProbeFile}?v=${v}`, { headers: { Range: 'bytes=0-0' } });
        lastMod = r.headers.get('last-modified');
      } catch {
        // Metadata probe is optional; continue with data load.
      }
      
      for (const table of TABLE_NAMES) {
        const symbolsForTable = tableSymbolsToLoad[table] ?? symbolsToLoad;
        const loadedSymbols = (
          await Promise.all(
            symbolsForTable.map(async (sym) => {
              const fileName = `${table}_${sym}.parquet`;
              try {
                await loadParquet(fileName, `/api/data/${fileName}?v=${v}`);
                return sym;
              } catch {
                console.warn(`File not found or failed to load: ${fileName}`);
                return null;
              }
            })
          )
        ).filter((sym): sym is string => !!sym);
        
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

  // ΓöÇΓöÇ Populate symbol options ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

  useEffect(() => {
    if (dbStatus !== 'ready') return;
    runQuery<{ symbol: string }>('SELECT DISTINCT symbol FROM ib_facts ORDER BY symbol')
      .then((rows) => setSymbols(['ALL', ...rows.map((r) => r.symbol)]))
      .catch(console.error);
  }, [dbStatus]);

  // ΓöÇΓöÇ Main query ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;
    setLoading(true);
    const started = performance.now();
    const where = buildWhere(deferredFilters);
    const whereAl = buildWhereAliasless(deferredFilters);
    const realizedExpr =
      realizedDirMethod === 'break'
        ? 'first_break_dir'
        : realizedDirMethod === 'close'
        ? "CASE WHEN outcome_close > ib_close THEN 1 WHEN outcome_close < ib_close THEN -1 ELSE 0 END"
        : "CASE WHEN max_ext_up > max_ext_down THEN 1 WHEN max_ext_up < max_ext_down THEN -1 ELSE 0 END";

    // DST validations should ignore sessionSlot and timeBasis filters
    const dstConds: string[] = [];
    if (deferredFilters.symbol !== 'ALL') dstConds.push(`symbol = ${q(deferredFilters.symbol)}`);
    if (deferredFilters.dow !== 'ALL') dstConds.push(`dow = ${q(deferredFilters.dow)}`);
    if (deferredFilters.startDate) dstConds.push(`trading_day >= ${q(deferredFilters.startDate)}`);
    if (deferredFilters.endDate) dstConds.push(`trading_day <= ${q(deferredFilters.endDate)}`);
    const dstWhere = dstConds.length > 0 ? `WHERE ${dstConds.join(' AND ')}` : '';

    try {
      const [
        overviewRows,
        biasData,
        noSignalData,
        conflictData,
        agreementData,
        playData,
        extData,
        touchData,
        fvgData,
        bucketData,
        timingHistogramData,
        dstData,
        levelTouchOutcomeData,
        frontRunData,
      ] = await Promise.all([
        // Overview
        runQuery<Overview>(`
          SELECT
            CAST(COUNT(*) AS DOUBLE) AS sample,
            CAST(AVG(range_pct) AS DOUBLE) AS avg_range_pct,
            CAST(AVG(CASE WHEN first_break_dir = 1 OR (first_break_dir = -1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_high_rate,
            CAST(AVG(CASE WHEN first_break_dir = -1 OR (first_break_dir = 1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_low_rate,
            CAST(AVG(CASE WHEN double_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS double_break_rate,
            CAST(SUM(CASE WHEN false_break_high THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN first_break_dir = 1 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS false_break_high_rate,
            CAST(SUM(CASE WHEN false_break_low THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN first_break_dir = -1 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS false_break_low_rate,
            CAST(SUM(CASE WHEN (first_break_dir = 1 AND false_break_high) OR (first_break_dir = -1 AND false_break_low) THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN first_break_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS false_break_rate,
            CAST(MODE(first_break_bucket) AS VARCHAR) AS mode_first_break_time
          FROM ib_facts
          ${where}
        `),

        // Directional bias comparison (DIR% + HIT% + empirical baselines/lifts)
        runQuery<any>(`
          WITH base AS (
            SELECT *, ${realizedExpr} AS realized_dir
            FROM ib_facts
            ${where}
          ),
          resolved AS (
            SELECT * FROM base WHERE realized_dir != 0
          ),
          dir_base AS (
            SELECT
              CAST(GREATEST(
                AVG(CASE WHEN realized_dir = 1 THEN 1.0 ELSE 0.0 END),
                AVG(CASE WHEN realized_dir = -1 THEN 1.0 ELSE 0.0 END)
              ) * 100 AS DOUBLE) AS base_dir
            FROM resolved
          ),
          tgt_base AS (
            SELECT
              CAST(AVG(CASE WHEN max_ext_up >= 0.5 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS base_up05,
              CAST(AVG(CASE WHEN max_ext_down >= 0.5 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS base_dn05
            FROM base
          ),
          variants AS (
            SELECT 'Formation First Reach' AS metric, 'formation_firstreach' AS key FROM (SELECT 1)
            UNION ALL SELECT 'Formation Last Touch', 'formation_lasttouch' FROM (SELECT 1)
            UNION ALL SELECT 'Close Direction', 'close_dir' FROM (SELECT 1)
            UNION ALL SELECT 'FVG Bias', 'fvg' FROM (SELECT 1)
            UNION ALL SELECT 'IFVG Bias', 'fvg_ifvg' FROM (SELECT 1)
            UNION ALL SELECT 'Combined', 'combined' FROM (SELECT 1)
          )
          SELECT
            metric,
            CAST(CASE key
              WHEN 'formation_firstreach' THEN SUM(CASE WHEN bias_formation_firstreach != 0 AND realized_dir != 0 AND bias_formation_firstreach = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_firstreach != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
              WHEN 'formation_lasttouch' THEN SUM(CASE WHEN bias_formation_lasttouch != 0 AND realized_dir != 0 AND bias_formation_lasttouch = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_lasttouch != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
              WHEN 'close_dir' THEN SUM(CASE WHEN bias_close_dir != 0 AND realized_dir != 0 AND bias_close_dir = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_close_dir != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
              WHEN 'fvg' THEN SUM(CASE WHEN bias_fvg != 0 AND realized_dir != 0 AND bias_fvg = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
              WHEN 'fvg_ifvg' THEN SUM(CASE WHEN bias_fvg_ifvg != 0 AND realized_dir != 0 AND bias_fvg_ifvg = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg_ifvg != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
              WHEN 'combined' THEN SUM(CASE WHEN bias_combined != 0 AND realized_dir != 0 AND bias_combined = realized_dir THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_combined != 0 AND realized_dir != 0 THEN 1.0 ELSE 0.0 END), 0) * 100
            END AS DOUBLE) AS dir_pct,
            CAST(CASE key
              WHEN 'formation_firstreach' THEN AVG(CASE WHEN bias_correct_formation_firstreach_05x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'formation_lasttouch' THEN AVG(CASE WHEN bias_correct_formation_lasttouch_05x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'close_dir' THEN AVG(CASE WHEN bias_correct_close_dir_05x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'fvg' THEN AVG(CASE WHEN bias_correct_fvg_05x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'fvg_ifvg' THEN AVG(CASE WHEN bias_correct_fvg_ifvg_05x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'combined' THEN AVG(CASE WHEN bias_correct_combined_05x THEN 1.0 ELSE 0.0 END) * 100
            END AS DOUBLE) AS hit_05,
            CAST(CASE key
              WHEN 'formation_firstreach' THEN AVG(CASE WHEN bias_correct_formation_firstreach_10x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'formation_lasttouch' THEN AVG(CASE WHEN bias_correct_formation_lasttouch_10x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'close_dir' THEN AVG(CASE WHEN bias_correct_close_dir_10x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'fvg' THEN AVG(CASE WHEN bias_correct_fvg_10x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'fvg_ifvg' THEN AVG(CASE WHEN bias_correct_fvg_ifvg_10x THEN 1.0 ELSE 0.0 END) * 100
              WHEN 'combined' THEN AVG(CASE WHEN bias_correct_combined_10x THEN 1.0 ELSE 0.0 END) * 100
            END AS DOUBLE) AS hit_1,
            CAST(db.base_dir AS DOUBLE) AS base_dir,
            CAST(tb.base_up05 AS DOUBLE) AS base_up05,
            CAST(tb.base_dn05 AS DOUBLE) AS base_dn05,
            CAST(CASE key
              WHEN 'formation_firstreach' THEN (SUM(CASE WHEN bias_formation_firstreach = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_firstreach != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_formation_firstreach = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_firstreach != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
              WHEN 'formation_lasttouch' THEN (SUM(CASE WHEN bias_formation_lasttouch = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_lasttouch != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_formation_lasttouch = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_formation_lasttouch != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
              WHEN 'close_dir' THEN (SUM(CASE WHEN bias_close_dir = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_close_dir != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_close_dir = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_close_dir != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
              WHEN 'fvg' THEN (SUM(CASE WHEN bias_fvg = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_fvg = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
              WHEN 'fvg_ifvg' THEN (SUM(CASE WHEN bias_fvg_ifvg = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg_ifvg != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_fvg_ifvg = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg_ifvg != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
              WHEN 'combined' THEN (SUM(CASE WHEN bias_combined = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_combined != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_up05 + (SUM(CASE WHEN bias_combined = -1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_combined != 0 THEN 1.0 ELSE 0.0 END), 0)) * tb.base_dn05
            END AS DOUBLE) AS base_tgt,
            CAST(COUNT(*) AS DOUBLE) AS n,
            0 AS is_baseline
          FROM base
          CROSS JOIN variants
          CROSS JOIN dir_base db
          CROSS JOIN tgt_base tb
          GROUP BY metric, key, db.base_dir, tb.base_up05, tb.base_dn05

          UNION ALL

          SELECT
            'BASELINE' AS metric,
            CAST(db.base_dir AS DOUBLE) AS dir_pct,
            CAST(tb.base_up05 AS DOUBLE) AS hit_05,
            CAST(tb.base_dn05 AS DOUBLE) AS hit_1,
            CAST(db.base_dir AS DOUBLE) AS base_dir,
            CAST(tb.base_up05 AS DOUBLE) AS base_up05,
            CAST(tb.base_dn05 AS DOUBLE) AS base_dn05,
            CAST(1.0 AS DOUBLE) AS base_tgt,
            CAST((SELECT COUNT(*) FROM resolved) AS DOUBLE) AS n,
            1 AS is_baseline
          FROM dir_base db
          CROSS JOIN tgt_base tb
          ORDER BY is_baseline DESC, metric
        `),

        // No-signal buckets (FVG/IFVG)
        runQuery<any>(`
          WITH base AS (
            SELECT * FROM ib_facts ${where}
          ),
          flags AS (
            SELECT *,
              CASE
                WHEN first_break_dir = 0
                  OR (first_break_dir = 1 AND false_break_high)
                  OR (first_break_dir = -1 AND false_break_low)
                  OR (max_ext_up < 0.5 AND max_ext_down < 0.5)
                THEN 1 ELSE 0
              END AS chop_flag
            FROM base
          )
          SELECT
            'FVG' AS variant,
            CAST(SUM(CASE WHEN bias_fvg = 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS n_absent,
            CAST(SUM(CASE WHEN bias_fvg = 0 AND chop_flag = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg = 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS chop_rate_absent,
            CAST(AVG(chop_flag) * 100 AS DOUBLE) AS chop_rate_all
          FROM flags
          UNION ALL
          SELECT
            'IFVG' AS variant,
            CAST(SUM(CASE WHEN bias_fvg_ifvg = 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS n_absent,
            CAST(SUM(CASE WHEN bias_fvg_ifvg = 0 AND chop_flag = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN bias_fvg_ifvg = 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS chop_rate_absent,
            CAST(AVG(chop_flag) * 100 AS DOUBLE) AS chop_rate_all
          FROM flags
        `),

        // Conflict matrix (required pairs)
        runQuery<any>(`
          WITH base AS (
            SELECT *, ${realizedExpr} AS realized_dir
            FROM ib_facts
            ${where}
          ),
          pairs AS (
            SELECT 'Formation ├ù FVG' AS pair_label, 'Formation' AS a_name, 'FVG' AS b_name, bias_formation_firstreach AS a_sig, bias_fvg AS b_sig, realized_dir FROM base
            UNION ALL
            SELECT 'Formation ├ù IFVG', 'Formation', 'IFVG', bias_formation_firstreach, bias_fvg_ifvg, realized_dir FROM base
            UNION ALL
            SELECT 'FVG ├ù Close-Dir', 'FVG', 'Close-Dir', bias_fvg, bias_close_dir, realized_dir FROM base
            UNION ALL
            SELECT 'Formation ├ù Close-Dir', 'Formation', 'Close-Dir', bias_formation_firstreach, bias_close_dir, realized_dir FROM base
          ),
          filtered AS (
            SELECT * FROM pairs WHERE a_sig != 0 AND b_sig != 0 AND a_sig != b_sig AND realized_dir != 0
          )
          SELECT
            pair_label,
            a_name,
            b_name,
            CAST(COUNT(*) AS DOUBLE) AS n_conflict,
            CAST(AVG(CASE WHEN realized_dir = a_sig THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS winA,
            CAST(AVG(CASE WHEN realized_dir = b_sig THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS winB,
            CASE WHEN AVG(CASE WHEN realized_dir = a_sig THEN 1.0 ELSE 0.0 END) >= AVG(CASE WHEN realized_dir = b_sig THEN 1.0 ELSE 0.0 END) THEN a_name ELSE b_name END AS winner,
            CAST(ABS(AVG(CASE WHEN realized_dir = a_sig THEN 1.0 ELSE 0.0 END) - AVG(CASE WHEN realized_dir = b_sig THEN 1.0 ELSE 0.0 END)) * 100 AS DOUBLE) AS edge
          FROM filtered
          GROUP BY pair_label, a_name, b_name
          ORDER BY edge DESC
        `),

        // Agreement lift
        runQuery<any>(`
          WITH base AS (
            SELECT *, ${realizedExpr} AS realized_dir
            FROM ib_facts
            ${where}
          ),
          sigs AS (
            SELECT *,
              (CASE WHEN bias_formation_firstreach != 0 THEN 1 ELSE 0 END +
               CASE WHEN bias_close_dir != 0 THEN 1 ELSE 0 END +
               CASE WHEN bias_fvg != 0 THEN 1 ELSE 0 END +
               CASE WHEN bias_fvg_ifvg != 0 THEN 1 ELSE 0 END +
               CASE WHEN bias_combined != 0 THEN 1 ELSE 0 END) AS firing_n,
              CASE
                WHEN bias_combined != 0 THEN bias_combined
                WHEN bias_fvg_ifvg != 0 THEN bias_fvg_ifvg
                WHEN bias_fvg != 0 THEN bias_fvg
                WHEN bias_close_dir != 0 THEN bias_close_dir
                ELSE bias_formation_firstreach
              END AS lead_sig
            FROM base
            WHERE realized_dir != 0
          ),
          agree2 AS (
            SELECT *,
              CASE
                WHEN ABS((CASE WHEN bias_formation_firstreach = 1 THEN 1 ELSE 0 END + CASE WHEN bias_close_dir = 1 THEN 1 ELSE 0 END + CASE WHEN bias_fvg = 1 THEN 1 ELSE 0 END + CASE WHEN bias_fvg_ifvg = 1 THEN 1 ELSE 0 END + CASE WHEN bias_combined = 1 THEN 1 ELSE 0 END) -
                         (CASE WHEN bias_formation_firstreach = -1 THEN 1 ELSE 0 END + CASE WHEN bias_close_dir = -1 THEN 1 ELSE 0 END + CASE WHEN bias_fvg = -1 THEN 1 ELSE 0 END + CASE WHEN bias_fvg_ifvg = -1 THEN 1 ELSE 0 END + CASE WHEN bias_combined = -1 THEN 1 ELSE 0 END)) >= 2
                THEN 1 ELSE 0
              END AS is_agree_2plus,
              CASE
                WHEN firing_n >= 2 AND (
                  (bias_formation_firstreach = bias_close_dir OR bias_close_dir = 0 OR bias_formation_firstreach = 0) AND
                  (bias_formation_firstreach = bias_fvg OR bias_fvg = 0 OR bias_formation_firstreach = 0) AND
                  (bias_formation_firstreach = bias_fvg_ifvg OR bias_fvg_ifvg = 0 OR bias_formation_firstreach = 0)
                )
                THEN 1 ELSE 0
              END AS is_agree_all
            FROM sigs
          )
          SELECT
            'agree_2plus' AS bucket,
            CAST(AVG(CASE WHEN lead_sig = realized_dir THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM agree2
          WHERE is_agree_2plus = 1
          UNION ALL
          SELECT
            'agree_all' AS bucket,
            CAST(AVG(CASE WHEN lead_sig = realized_dir THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM agree2
          WHERE is_agree_all = 1
        `),

        // Bias accuracy per variant
        runQuery<any>(`
          SELECT
            'First Reach' AS metric,
            CAST(AVG(CASE WHEN bias_correct_formation_firstreach_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'Last Touch' AS metric,
            CAST(AVG(CASE WHEN bias_correct_formation_lasttouch_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'Close Direction' AS metric,
            CAST(AVG(CASE WHEN bias_correct_close_dir_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'FVG Bias' AS metric,
            CAST(AVG(CASE WHEN bias_correct_fvg_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'IFVG Bias' AS metric,
            CAST(AVG(CASE WHEN bias_correct_fvg_ifvg_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
          UNION ALL
          SELECT
            'Combined' AS metric,
            CAST(AVG(CASE WHEN bias_correct_combined_${biasTargetLvl.replace('.', '')}x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS accuracy,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_facts ${where}
        `),

        // Plays
        runQuery<any>(`
          WITH counts AS (
            SELECT
              CAST(COUNT(*) AS DOUBLE) AS total_sessions,
              CAST(SUM(CASE WHEN first_break_dir != 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS breakout_sessions
            FROM ib_facts
            ${where}
          ),
          plays AS (
            SELECT
              play,
              CAST(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS entered_sessions,
              CAST(SUM(CASE WHEN result = 1 THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS win_rate,
              CAST(SUM(CASE WHEN result = -1 AND COALESCE(timeout_loss, FALSE) = FALSE THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS stop_loss_rate,
              CAST(SUM(CASE WHEN result = -1 AND COALESCE(timeout_loss, FALSE) = TRUE THEN 1.0 ELSE 0.0 END) / NULLIF(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END), 0) * 100 AS DOUBLE) AS timeout_loss_rate,
              CAST(SUM(CASE WHEN result = 0 THEN 1.0 ELSE 0.0 END) / NULLIF(COUNT(*), 0) * 100 AS DOUBLE) AS no_setup_rate,
              CAST(AVG(mfe) AS DOUBLE) AS avg_mfe,
              CAST(AVG(mae) AS DOUBLE) AS avg_mae,
              CAST(AVG(realized_r) AS DOUBLE) AS expectancy,
              CAST(SUM(CASE WHEN result != 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS n
            FROM ib_play_detail
            ${whereAl ? `${whereAl} AND target_lvl = ${playTargetLvl}` : `WHERE target_lvl = ${playTargetLvl}`}
            ${withBiasFilter === 'with_bias' ? 'AND with_bias = 1' : withBiasFilter === 'counter_bias' ? 'AND with_bias = -1' : ''}
            GROUP BY play
          )
          SELECT
            p.play,
            p.win_rate,
            p.avg_mfe,
            p.avg_mae,
            p.expectancy,
            p.n,
            CASE
              WHEN p.play = 1 THEN (p.entered_sessions / NULLIF(c.total_sessions, 0)) * 100
              ELSE (p.entered_sessions / NULLIF(c.breakout_sessions, 0)) * 100
            END AS setup_rate
          FROM plays p, counts c
          ORDER BY p.play
        `),

        // Extension levels
        runQuery<any>(`
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
        runQuery<any>(`
          SELECT
            phase,
            CAST(AVG(touch_count) AS DOUBLE) AS avg_touch_count,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM ib_level_touch_detail
          ${whereAl}
          GROUP BY phase
          ORDER BY phase
        `),

        // FVG touch timing split (formation vs outcome), derived from facts.
        runQuery<FvgRow>(`
          WITH base AS (
            SELECT *
            FROM ib_facts
            ${where}
          )
          SELECT
            'IB FVG Formation Touch' AS metric,
            CAST(AVG(CASE WHEN fvg_touch_first_formation_time IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            CAST(MEDIAN((epoch(fvg_touch_first_formation_time) - epoch(ib_fvg_fin_time)) / 60.0) AS DOUBLE) AS median_mins,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM base
          WHERE bias_fvg != 0 AND ib_fvg_fin_time IS NOT NULL

          UNION ALL

          SELECT
            'IB FVG Outcome Touch' AS metric,
            CAST(AVG(CASE WHEN fvg_touch_first_outcome_time IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            CAST(MEDIAN((epoch(fvg_touch_first_outcome_time) - epoch(ib_fvg_fin_time)) / 60.0) AS DOUBLE) AS median_mins,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM base
          WHERE bias_fvg != 0 AND ib_fvg_fin_time IS NOT NULL

          UNION ALL

          SELECT
            '10:11 FVG Formation Touch' AS metric,
            CAST(AVG(CASE WHEN fvg_1011_touch_first_formation_time IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            CAST(MEDIAN((epoch(fvg_1011_touch_first_formation_time) - epoch(fvg_1011_fin_time)) / 60.0) AS DOUBLE) AS median_mins,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM base
          WHERE session_slot = 'NY AM IB' AND bias_fvg_1011 != 0 AND fvg_1011_fin_time IS NOT NULL

          UNION ALL

          SELECT
            '10:11 FVG Outcome Touch' AS metric,
            CAST(AVG(CASE WHEN fvg_1011_touch_first_outcome_time IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            CAST(MEDIAN((epoch(fvg_1011_touch_first_outcome_time) - epoch(fvg_1011_fin_time)) / 60.0) AS DOUBLE) AS median_mins,
            CAST(COUNT(*) AS DOUBLE) AS n
          FROM base
          WHERE session_slot = 'NY AM IB' AND bias_fvg_1011 != 0 AND fvg_1011_fin_time IS NOT NULL
        `),

        // Range bucket breakdown
        runQuery<any>(`
          SELECT
            range_bucket_full AS bucket,
            CAST(COUNT(*) AS DOUBLE) AS n,
            CAST(AVG(CASE WHEN first_break_dir = 1 OR (first_break_dir = -1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_high_rate,
            CAST(AVG(CASE WHEN first_break_dir = -1 OR (first_break_dir = 1 AND double_break) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_low_rate,
            CAST(AVG(CASE WHEN double_break THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS double_break_rate
          FROM ib_facts
          ${where}
          GROUP BY range_bucket_full
          ORDER BY CASE range_bucket_full WHEN 'Small' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        `),

        // Timing histogram
        runQuery<TimingRow>(`
          SELECT
            CAST(first_break_bucket AS VARCHAR) AS bucket,
            CAST(COUNT(*) AS DOUBLE) AS play1_n
          FROM ib_facts
          ${where ? `${where} AND first_break_bucket IS NOT NULL` : 'WHERE first_break_bucket IS NOT NULL'}
          GROUP BY first_break_bucket
          ORDER BY first_break_bucket
        `),

        // DST validation
        runQuery<any>(`
          WITH dst_base AS (
            SELECT
              symbol,
              trading_day,
              session_slot,
              time_basis,
              first_break_dir,
              bias_correct_combined_05x,
              play1_result
            FROM ib_facts
            ${dstWhere ? `${dstWhere} AND session_slot IN ('Tokyo IB', 'London IB') AND dst_regime = 'shifted'` : "WHERE session_slot IN ('Tokyo IB', 'London IB') AND dst_regime = 'shifted'"}
          ),
          base_stats AS (
            SELECT
              session_slot,
              time_basis,
              CAST(COUNT(*) AS DOUBLE) AS sample,
              CAST(AVG(CASE WHEN first_break_dir != 0 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS break_rate,
              CAST(AVG(CASE WHEN bias_correct_combined_05x THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS bias_accuracy,
              CAST(AVG(CASE WHEN play1_result = 1 THEN 1.0 WHEN play1_result = -1 THEN 0.0 ELSE NULL END) * 100 AS DOUBLE) AS play1_win_rate
            FROM dst_base
            GROUP BY session_slot, time_basis
          ),
          play2_stats AS (
            SELECT
              b.session_slot,
              b.time_basis,
              CAST(AVG(CASE WHEN p.result = 1 THEN 1.0 WHEN p.result = -1 THEN 0.0 ELSE NULL END) * 100 AS DOUBLE) AS play2_win_rate
            FROM dst_base b
            JOIN ib_play_detail p
              ON p.symbol = b.symbol
             AND p.trading_day = b.trading_day
             AND p.session_slot = b.session_slot
             AND p.time_basis = b.time_basis
             AND p.play = 2
             AND p.target_lvl = ${playTargetLvl}
            GROUP BY b.session_slot, b.time_basis
          )
          SELECT
            bs.session_slot,
            bs.time_basis,
            bs.sample,
            bs.break_rate,
            bs.bias_accuracy,
            bs.play1_win_rate,
            p2.play2_win_rate
          FROM base_stats bs
          LEFT JOIN play2_stats p2
            ON p2.session_slot = bs.session_slot
           AND p2.time_basis = bs.time_basis
          ORDER BY bs.session_slot, bs.time_basis
        `),

        // Level Touches outcome table
        runQuery<any>(`
          SELECT
            level_pct,
            CAST(AVG(CASE WHEN touch_count > 0 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS touch_rate,
            MODE(STRFTIME(first_touch_time, '%H:%M')) AS mode_touch_time,
            CAST(MEDIAN(epoch(first_touch_time)) AS DOUBLE) AS median_epoch
          FROM ib_level_touch_detail
          ${whereAl ? `${whereAl} AND phase = 'outcome'` : "WHERE phase = 'outcome'"}
          GROUP BY level_pct
          ORDER BY level_pct
        `),

        // Front-Running stats
        runQuery<any>(`
          SELECT
            CAST(AVG(CASE WHEN front_run_active THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS rate,
            CAST(MEDIAN(front_run_activation_mins) AS DOUBLE) AS median_mins,
            MODE(floor(front_run_activation_mins / 5) * 5) AS mode_mins
          FROM ib_facts
          ${where}
        `),
      ]);

      setOverview(overviewRows[0] ?? null);
      setBiasRows((biasData as any[]).map((r) => {
        const baseTgt = Number(r.base_tgt ?? 0);
        const dirPct = Number(r.dir_pct ?? 0);
        const hit05 = Number(r.hit_05 ?? 0);
        const baseDir = Number(r.base_dir ?? 0);
        return {
          ...r,
          lift_dir: Number(r.is_baseline) === 1 ? 0 : dirPct - baseDir,
          lift_tgt: Number(r.is_baseline) === 1 ? 0 : hit05 - baseTgt,
        } as BiasRow;
      }));
      setNoSignalRows(noSignalData as NoSignalRow[]);
      setConflictRows(conflictData as ConflictRow[]);
      setAgreementRows(agreementData as AgreementRow[]);
      setPlayRows(playData as PlayRow[]);
      setExtRows(extData as ExtRow[]);
      setTouchRows(touchData as TouchRow[]);
      setFvgRows(fvgData as FvgRow[]);
      setRangeBucketRows(bucketData as unknown as RangeBucketRow[]);
      setTimingRows(timingHistogramData as TimingRow[]);
      setDstRows(dstData);
      setLevelTouchOutcomeRows(levelTouchOutcomeData);
      setFrontRunStats(frontRunData[0] ?? null);
      setQueryTimeMs(performance.now() - started);
    } catch (err) {
      console.error('IB Stats dashboard query failed:', err);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters, biasTargetLvl, playTargetLvl, withBiasFilter, realizedDirMethod]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const refreshData = useCallback(async () => {
    await resetDuckDB();
    await loadEngine();
  }, [loadEngine]);

  const totalRecords = useMemo(() => overview?.sample, [overview]);

  const aggregatedTimingData = useMemo(() => {
    if (!timingRows.length) return [];
    const groups: Record<string, number> = {};
    for (const row of timingRows) {
      if (!row.bucket) continue;
      const rounded = roundToBucket(row.bucket, granularity);
      groups[rounded] = (groups[rounded] || 0) + (row.play1_n || 0);
    }
    return Object.entries(groups)
      .map(([time, count]) => ({ time, count }))
      .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time));
  }, [timingRows, granularity]);

  const timingStats = useMemo(() => {
    if (!aggregatedTimingData.length) return { mode: '--', median: '--' };
    
    let maxCount = -1;
    let modeVal = '--';
    for (const item of aggregatedTimingData) {
      if (item.count > maxCount) {
        maxCount = item.count;
        modeVal = item.time;
      }
    }
    
    const total = aggregatedTimingData.reduce((sum, item) => sum + item.count, 0);
    let cumulative = 0;
    let medianVal = '--';
    for (const item of aggregatedTimingData) {
      cumulative += item.count;
      if (cumulative >= total / 2) {
        medianVal = item.time;
        break;
      }
    }
    
    return { mode: modeVal, median: medianVal };
  }, [aggregatedTimingData]);

  const suggestedSynthesis = useMemo(() => {
    if (!biasRows.length || !playRows.length) return null;
    const baseline = biasRows.find((r) => r.is_baseline === 1);
    const candidates = biasRows.filter((r) => r.is_baseline === 0);
    const bestBias = [...candidates].sort((a, b) => b.lift_dir - a.lift_dir)[0];
    
    const playExpectancies = playRows.map(p => {
      const ev = p.expectancy;
      return { ...p, ev };
    });
    const bestPlay = [...playExpectancies].sort((a, b) => b.ev - a.ev)[0];
    
    if (!bestBias || !bestPlay) return null;
    
    const biasName = bestBias.metric;
    const playName = `Play ${bestPlay.play} (${bestPlay.play === 1 ? 'Breakout' : bestPlay.play === 2 ? 'Retest' : 'Fade'})`;
    const bestPlayEv = typeof bestPlay.ev === 'number' && Number.isFinite(bestPlay.ev) ? bestPlay.ev : 0;
    const evStr = `${bestPlayEv > 0 ? '+' : ''}${bestPlayEv.toFixed(2)}R`;
    const isFadeSignal = baseline ? (bestBias.dir_pct ?? 0) < (baseline.base_dir ?? 50) : false;
    
    let suggestionText = '';
    if (bestPlay.play === 3) {
      suggestionText = `Reversion bias is dominant. Focus on Play 3 (Fade-to-Mid) entering on boundary overshoot pullbacks, targeting the mid-line. Expected Value: ${evStr}.`;
    } else {
      suggestionText = `${isFadeSignal ? 'Fade signal:' : 'Expansion bias is dominant:'} Trust ${biasName} (${(bestBias.dir_pct ?? 0).toFixed(1)}% DIR, LIFT ${(bestBias.lift_dir ?? 0).toFixed(1)}pp) with ${playName}. Expected Value: ${evStr}.`;
    }
    
    return {
      biasName,
      playName,
      ev: bestPlayEv,
      text: suggestionText
    };
  }, [biasRows, playRows]);

  // ΓöÇΓöÇ Render ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.08),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.1),_transparent_26%),#050816] text-zinc-100">
      <div className="mx-auto w-full max-w-[1600px] space-y-8 px-6 py-8">
        {/* ΓöÇΓöÇ Header ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
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
                  Multi-session Initial Balance analytics ΓÇö breakouts, bias formation, plays, extensions, level touches, and FVG behaviour.
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

        {/* ΓöÇΓöÇ Filters ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
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

        {/* ΓöÇΓöÇ Overview Stats ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
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
            label="False Break Γû▓"
            value={overview ? `${(overview.false_break_high_rate ?? 0).toFixed(1)}%` : '--'}
            accent="text-orange-300"
          />
          <StatCard
            label="Break Time (Mode)"
            value={overview ? formatTimeFromMicroseconds(overview.mode_first_break_time) : '--'}
            sub="EST Clock Time"
          />
        </div>

        {/* ΓöÇΓöÇ 0: SUGGESTED SYNTHESIS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <Card className="border-zinc-900 bg-zinc-950/60 border-l-2 border-l-amber-500 p-5 mt-6">
          <SectionHeader
            icon={<Zap className="h-5 w-5" />}
            title="SUGGESTED SYNTHESIS"
            color="text-amber-300"
          />
          <div className="text-sm text-zinc-100 font-medium font-mono">
            {suggestedSynthesis ? suggestedSynthesis.text : 'No synthesis available. Adjust filters.'}
          </div>
        </Card>

        {/* ΓöÇΓöÇ Γæá DIRECTION ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr] mt-6">
          {/* Directional Bias */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <span className="text-emerald-300"><TrendingUp className="h-5 w-5" /></span>
                <h2 className="text-lg font-semibold tracking-tight flex items-center">
                  Γæá DIRECTION: Bias Comparison & Conflict
                  <TooltipHelp text="DIR% measures direction correctness versus realized direction; HIT% measures extension hits. LIFTs are measured against empirical baselines." />
                </h2>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 uppercase tracking-wider font-mono">Realized:</span>
                <Select value={realizedDirMethod} onValueChange={(v) => setRealizedDirMethod(v as 'break' | 'close' | 'ext')}>
                  <SelectTrigger className="w-28 h-8 border-zinc-800 bg-zinc-950 text-xs text-zinc-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950 text-zinc-200">
                    <SelectItem value="break">Break</SelectItem>
                    <SelectItem value="close">Close</SelectItem>
                    <SelectItem value="ext">Ext</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-zinc-400 uppercase tracking-wider font-mono">Target:</span>
                <Select value={biasTargetLvl} onValueChange={setBiasTargetLvl}>
                  <SelectTrigger className="w-28 h-8 border-zinc-800 bg-zinc-950 text-xs text-zinc-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950 text-zinc-200">
                    <SelectItem value="0.0">0.00x (IB)</SelectItem>
                    <SelectItem value="0.25">0.25x</SelectItem>
                    <SelectItem value="0.5">0.50x</SelectItem>
                    <SelectItem value="0.75">0.75x</SelectItem>
                    <SelectItem value="1.0">1.00x</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Metric</th>
                    <th className="px-4 py-3 text-right">DIR%</th>
                    <th className="px-4 py-3 text-right">0.5x HIT%</th>
                    <th className="px-4 py-3 text-right">1.0x HIT%</th>
                    <th className="px-4 py-3 text-right">LIFT_dir</th>
                    <th className="px-4 py-3 text-right">LIFT_tgt</th>
                    <th className="px-4 py-3 text-right">N</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {biasRows.map((row, idx) => {
                    const getLiftColor = (val: number) => {
                      if (val > 1.0) return 'text-emerald-400 font-semibold';
                      if (val < -1.0) return 'text-rose-400/90';
                      return 'text-zinc-300';
                    };
                    const rowClass = row.is_baseline ? 'bg-zinc-950/60' : '';
                    return (
                      <tr key={`bias-row-${row.metric}-${idx}`} className={rowClass}>
                        <td className="px-4 py-3 text-zinc-200">{row.metric}</td>
                        <td className="px-4 py-3 text-right text-zinc-200">{(row.dir_pct ?? 0).toFixed(1)}%</td>
                        <td className="px-4 py-3 text-right text-sky-300">{(row.hit_05 ?? 0).toFixed(1)}%</td>
                        <td className="px-4 py-3 text-right text-indigo-300">{(row.hit_1 ?? 0).toFixed(1)}%</td>
                        <td className={`px-4 py-3 text-right ${getLiftColor(row.lift_dir ?? 0)}`}>
                          {(row.lift_dir ?? 0) >= 0 ? '+' : ''}{(row.lift_dir ?? 0).toFixed(1)}pp
                        </td>
                        <td className={`px-4 py-3 text-right ${getLiftColor(row.lift_tgt ?? 0)}`}>
                          {(row.lift_tgt ?? 0) >= 0 ? '+' : ''}{(row.lift_tgt ?? 0).toFixed(1)}pp
                        </td>
                        <td className="px-4 py-3 text-right text-zinc-500">
                          {Math.round(row.n).toLocaleString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 rounded-lg border border-zinc-900 bg-zinc-950/40 p-3 text-xs text-zinc-300">
              {noSignalRows.map((r, idx) => (
                <div key={`no-sig-${r.variant}-${idx}`}>
                  No-{r.variant} day {'->'} chop {(r.chop_rate_absent ?? 0).toFixed(1)}% (vs {(r.chop_rate_all ?? 0).toFixed(1)}% baseline, N={Math.round(r.n_absent ?? 0)})
                </div>
              ))}
              {agreementRows.map((r, idx) => (
                <div key={`agree-${r.bucket}-${idx}`}>
                  {r.bucket}: {(r.accuracy ?? 0).toFixed(1)}% (N={Math.round(r.n ?? 0)})
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-lg border border-zinc-900 bg-zinc-950/40 p-3 text-xs text-zinc-300">
              <div className="mb-1 uppercase tracking-[0.18em] text-zinc-500">Conflict Matrix (Ranked)</div>
              {conflictRows.length === 0 ? (
                <div className="text-zinc-500">No conflict rows for current filters.</div>
              ) : (
                conflictRows.slice(0, 6).map((r, idx) => (
                  <div key={`conflict-${r.pair_label}-${idx}`}>
                    {r.pair_label}: {r.a_name} {(r.winA ?? 0).toFixed(1)}% / {r.b_name} {(r.winB ?? 0).toFixed(1)}% (N={Math.round(r.n_conflict ?? 0)}) {'->'} <span className="text-amber-300">{r.winner}</span>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* FVG touch timing split (formation/outcome) */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <SectionHeader
              icon={<Zap className="h-5 w-5" />}
              title="FVG Touch Timing"
              color="text-violet-300"
            />
            <div className="grid gap-6">
              {fvgRows.map((row, idx) => (
                <div key={`fvg-row-${row.metric}-${idx}`} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                  <div className="mb-3 text-sm font-semibold text-zinc-200">
                    {row.metric}
                    <span className="ml-2 text-xs text-zinc-500 font-mono">N={Math.round(row.n).toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    {[
                      { label: 'Touch Rate', value: row.touch_rate, color: 'text-sky-300', tooltip: 'Probability of first touch occurring in this phase after FVG formation.' },
                    ].map(({ label, value, color, tooltip }) => (
                      <div key={label}>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 flex items-center justify-center">
                          {label}
                          <TooltipHelp text={tooltip} />
                        </div>
                        <div className={`mt-1 text-xl font-semibold ${color}`}>{value != null ? `${Number(value ?? 0).toFixed(1)}%` : '--%'}</div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-900">
                          <div
                            className={`h-full rounded-full ${
                              color === 'text-sky-300'
                                ? 'bg-sky-400'
                                : 'bg-violet-400'
                            }`}
                            style={{ width: `${Math.min(100, Number(value ?? 0))}%` }}
                          />
                        </div>
                      </div>
                    ))}
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 flex items-center justify-center">
                        Median Touch Delay
                        <TooltipHelp text="Median minutes from FVG finalized time to first touch in this phase." />
                      </div>
                      <div className="mt-1 text-xl font-semibold text-emerald-300">
                        {row.median_mins != null ? `${row.median_mins.toFixed(1)}m` : '--'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ΓöÇΓöÇ Γæí FAKE-OUT & BREAKS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-orange-300"><TrendingDown className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                Γæí FAKE-OUT & BREAKS
                <TooltipHelp text="Analysis of breakouts that fail to expand and instead reverse to the opposite side." />
              </h2>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="border-zinc-900 bg-zinc-950/70 p-4">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <span>Double Break</span>
                <TooltipHelp text="Session price expanded past both high and low IB boundaries during the same day." />
              </div>
              <div className="mt-2 text-xl font-semibold text-fuchsia-300">
                {overview ? `${(overview.double_break_rate ?? 0).toFixed(1)}%` : '--'}
              </div>
              <div className="mt-1 text-[10px] text-zinc-500">of all sessions</div>
            </Card>

            <Card className="border-zinc-900 bg-zinc-950/70 p-4">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <span>False Break (Bull)</span>
                <TooltipHelp text="Probability that price breaks the IB High but fails to hit target extension, reversing to close/touch mid/opposite." />
              </div>
              <div className="mt-2 text-xl font-semibold text-orange-300">
                {overview ? `${(overview.false_break_high_rate ?? 0).toFixed(1)}%` : '--'}
              </div>
              <div className="mt-1 text-[10px] text-zinc-500">conditioned on High breakouts</div>
            </Card>

            <Card className="border-zinc-900 bg-zinc-950/70 p-4">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <span>False Break (Bear)</span>
                <TooltipHelp text="Probability that price breaks the IB Low but fails to hit target extension, reversing to close/touch mid/opposite." />
              </div>
              <div className="mt-2 text-xl font-semibold text-orange-300">
                {overview ? `${(overview.false_break_low_rate ?? 0).toFixed(1)}%` : '--'}
              </div>
              <div className="mt-1 text-[10px] text-zinc-500">conditioned on Low breakouts</div>
            </Card>

            <Card className="border-zinc-900 bg-zinc-950/70 p-4">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <span>False Break (Combined)</span>
                <TooltipHelp text="Overall probability of breakout failure, calculated only on sessions that actually broke." />
              </div>
              <div className="mt-2 text-xl font-semibold text-rose-300 font-bold">
                {overview ? `${(overview.false_break_rate ?? 0).toFixed(1)}%` : '--'}
              </div>
              <div className="mt-1 text-[10px] text-zinc-500">conditioned on any breakout</div>
            </Card>
          </div>
        </Card>

        {/* ΓöÇΓöÇ PLAYS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-2">
              <span className="text-cyan-300"><Zap className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                PLAYS Performance (P1 / P2 / P3)
                <TooltipHelp text="Performance metrics for specific trade plays: Play 1 (Breakout Expansion), Play 2 (Pullback Retest), Play 3 (Fade Boundary)." />
              </h2>
            </div>
            
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-400 uppercase tracking-wider font-mono">Target:</span>
                <Select value={playTargetLvl} onValueChange={setPlayTargetLvl}>
                  <SelectTrigger className="w-24 h-8 border-zinc-800 bg-zinc-950 text-xs text-zinc-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950 text-zinc-200">
                    <SelectItem value="0.25">0.25x</SelectItem>
                    <SelectItem value="0.5">0.50x</SelectItem>
                    <SelectItem value="0.75">0.75x</SelectItem>
                    <SelectItem value="1.0">1.00x</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-400 uppercase tracking-wider font-mono">Filter:</span>
                <Select value={withBiasFilter} onValueChange={setWithBiasFilter}>
                  <SelectTrigger className="w-36 h-8 border-zinc-800 bg-zinc-950 text-xs text-zinc-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950 text-zinc-200">
                    <SelectItem value="all">All Trades</SelectItem>
                    <SelectItem value="with_bias">With Bias Only</SelectItem>
                    <SelectItem value="counter_bias">Counter Bias Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
              {playRows.map((play, idx) => {
              const colorClass =
                play.play === 1
                  ? 'text-cyan-300'
                  : play.play === 2
                  ? 'text-sky-300'
                  : 'text-indigo-300';
              const barColor =
                play.play === 1 ? '#67e8f9' : play.play === 2 ? '#7dd3fc' : '#a5b4fc';

              const expectancy = play.expectancy;
              const evColorClass = expectancy >= 0 ? 'text-emerald-400' : 'text-rose-400';

              return (
                  <div key={`play-card-${play.play}-${idx}`} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4 flex flex-col justify-between">
                  <div>
                    <div className={`mb-3 text-xs font-semibold uppercase tracking-[0.2em] ${colorClass}`}>
                      Play {play.play} ({play.play === 1 ? 'Breakout' : play.play === 2 ? 'Retest' : 'Fade'})
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Win Rate</div>
                        <div className={`mt-1 text-lg font-semibold ${colorClass}`}>
                          {(play.win_rate ?? 0).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 flex items-center">
                          Setup Rate
                          <TooltipHelp text="The historical frequency that this setup triggers and fills, indicating trade capacity." />
                        </div>
                        <div className="mt-1 text-lg font-semibold text-zinc-100">
                          {play.setup_rate != null ? `${play.setup_rate.toFixed(1)}%` : '--'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 flex items-center">
                          EV (R)
                          <TooltipHelp text="The average R-multiplier gain/loss per trade (including fractional close-outs at 16:00)." />
                        </div>
                        <div className={`mt-1 text-lg font-bold ${evColorClass}`}>
                          {expectancy != null ? `${expectancy > 0 ? '+' : ''}${expectancy.toFixed(2)}R` : '--'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Avg MFE</div>
                        <div className="mt-1 text-md font-medium text-emerald-300">
                          {(Number(play.avg_mfe ?? 0) * 100).toFixed(2)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Avg MAE</div>
                        <div className="mt-1 text-md font-medium text-rose-300">
                          {(Number(play.avg_mae ?? 0) * 100).toFixed(2)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">Sample (N)</div>
                        <div className="mt-1 text-md font-medium text-zinc-400">
                          {Math.round(play.n).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 rounded-lg border border-zinc-900 bg-zinc-950/50 p-2 text-[11px] text-zinc-300">
                      <span className="text-zinc-500 uppercase tracking-[0.14em] mr-2">Loss Split</span>
                      <span className="text-rose-300">Stop {(play.stop_loss_rate ?? 0).toFixed(1)}%</span>
                      <span className="mx-2 text-zinc-600">|</span>
                      <span className="text-orange-300">Timeout {(play.timeout_loss_rate ?? 0).toFixed(1)}%</span>
                      <span className="mx-2 text-zinc-600">|</span>
                      <span className="text-zinc-400">No-Setup {(play.no_setup_rate ?? 0).toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="mt-4 h-24 w-full">
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
                </div>
              );
            })}
          </div>

          {/* Histogram */}
          {aggregatedTimingData.length > 0 && (
            <div className="mt-6 border-t border-zinc-900 pt-6">
              <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sky-300"><BarChart2 className="h-5 w-5" /></span>
                  <h3 className="text-sm font-semibold text-zinc-200 flex items-center">
                    Play 1 Entry Timing Distribution (EST)
                    <TooltipHelp text="Shows the historical frequency of breakouts clustered by clock time, helping target optimal trading windows." />
                  </h3>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  {/* Mode & Median Badges */}
                  <div className="flex items-center gap-2 mr-2">
                    <Badge variant="outline" className="border-sky-500/20 bg-sky-500/10 text-sky-300 font-mono text-[10px]">
                      MODE: {timingStats.mode}
                    </Badge>
                    <Badge variant="outline" className="border-emerald-500/20 bg-emerald-500/10 text-emerald-300 font-mono text-[10px]">
                      MEDIAN: {timingStats.median}
                    </Badge>
                  </div>

                  {/* Granularity Selector */}
                  <div className="flex items-center bg-zinc-950 border border-zinc-800 rounded-lg p-0.5">
                    {[
                      { label: '5m', value: 5 },
                      { label: '15m', value: 15 },
                      { label: '30m', value: 30 },
                      { label: '1h', value: 60 },
                    ].map((g) => (
                      <button
                        key={g.value}
                        onClick={() => setGranularity(g.value)}
                        className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${
                          granularity === g.value
                            ? 'bg-zinc-800 text-zinc-100'
                            : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                      >
                        {g.label}
                      </button>
                    ))}
                  </div>

                  {/* Maximize Button */}
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 border-zinc-800 bg-zinc-950 hover:bg-zinc-900"
                    onClick={() => setIsExpanded(true)}
                  >
                    <Maximize2 className="h-4 w-4 text-zinc-400" />
                  </Button>
                </div>
              </div>

              <div className="h-56 w-full bg-zinc-950/20 rounded-xl border border-zinc-900 p-2 min-h-[224px]">
                <TimingInnerChart data={aggregatedTimingData} granularity={granularity} />
              </div>

              {/* Dialog for Maximized view */}
              <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
                <DialogContent className="max-w-5xl border-zinc-900 bg-[#070a19] text-zinc-100 p-6">
                  <DialogHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-zinc-900 pb-4">
                    <div>
                      <DialogTitle className="text-xl font-semibold tracking-tight text-zinc-100">
                        Play 1 Entry Timing Distribution
                      </DialogTitle>
                      <p className="text-xs text-zinc-400 mt-1">
                        Zoom and inspect breakout timing across {totalRecords?.toLocaleString()} sessions.
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="border-sky-500/20 bg-sky-500/10 text-sky-300 font-mono text-xs px-2.5 py-1">
                        MODE: {timingStats.mode}
                      </Badge>
                      <Badge variant="outline" className="border-emerald-500/20 bg-emerald-500/10 text-emerald-300 font-mono text-xs px-2.5 py-1">
                        MEDIAN: {timingStats.median}
                      </Badge>
                      <div className="flex items-center bg-zinc-950 border border-zinc-800 rounded-lg p-0.5">
                        {[
                          { label: '5m', value: 5 },
                          { label: '15m', value: 15 },
                          { label: '30m', value: 30 },
                          { label: '1h', value: 60 },
                        ].map((g) => (
                          <button
                            key={g.value}
                            onClick={() => setGranularity(g.value)}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                              granularity === g.value
                                ? 'bg-zinc-800 text-zinc-100'
                                : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                          >
                            {g.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </DialogHeader>
                  
                  <div className="h-[450px] w-full mt-6 bg-zinc-950/40 rounded-xl border border-zinc-900 p-4">
                    <TimingInnerChart data={aggregatedTimingData} granularity={granularity} />
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          )}

          {/* Style Note / Takeaway */}
          <div className="mt-5 rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-4 text-xs text-cyan-200">
            <span className="font-semibold uppercase tracking-wider block mb-1">Trading Takeaway:</span>
            Play 2 (Retest) achieves its highest expectancy at 0.50x targets. Fading overshoot extensions (Play 3) has a higher raw win rate but lower reward-to-risk ratio. Win rates and setup expectancies are heavily conditioned by Directional Bias accuracy.
          </div>
        </Card>

        {/* ΓöÇΓöÇ Γæó TARGETS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr] mt-6">
          {/* Extension Levels */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center gap-2">
              <span className="text-sky-300"><TrendingDown className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                Γæó TARGETS: Extension Hit Rates
                <TooltipHelp text="Probability that price reaches specific multiples of the IB range in the direction of the breakout." />
              </h2>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={extRows} barCategoryGap="20%">
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis
                    dataKey="level"
                    tick={{ fill: '#a1a1aa', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `${v}├ù`}
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
              {touchRows.map((row, index) => (
                <div key={`${row.phase ?? 'unknown-phase'}-${index}`} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-zinc-300">
                      {(row.phase ?? 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <span className="text-fuchsia-300">{Number(row.avg_touch_count ?? 0).toFixed(2)} avg</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                    <div
                      className="h-full rounded-full bg-fuchsia-400"
                      style={{ width: `${Math.min(100, (Number(row.avg_touch_count ?? 0) / 5) * 100)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">N={Math.round(row.n).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ΓöÇΓöÇ Γæú DAY TYPE, RANGE ╬ö & FRONT RUNNING ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <div className="grid gap-6 xl:grid-cols-2 mt-6">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center gap-2">
              <span className="text-amber-300"><Waves className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                Γæú DAY TYPE & RANGE ╬ö: Size Distribution
                <TooltipHelp text="Breakout behavior categorized by the relative size of the Initial Balance range (Small, Medium, Large terciles)." />
              </h2>
            </div>
            <div className="space-y-4">
              {rangeBucketRows.map((row, idx) => (
                <div key={`${row.bucket}-${idx}`} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                  <div className="mb-3 flex items-center justify-between text-sm font-semibold">
                    <span className="text-zinc-200">{row.bucket} IB Size</span>
                    <span className="text-xs text-zinc-500 font-mono">N={Math.round(row.n).toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500 flex items-center justify-between">
                        <span>High Break</span>
                        <span className="text-emerald-400 font-semibold font-mono">{(row.break_high_rate ?? 0).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                        <div
                          className="h-full rounded-full bg-emerald-500"
                          style={{ width: `${Math.min(100, row.break_high_rate ?? 0)}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500 flex items-center justify-between">
                        <span>Low Break</span>
                        <span className="text-rose-400 font-semibold font-mono">{(row.break_low_rate ?? 0).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                        <div
                          className="h-full rounded-full bg-rose-500"
                          style={{ width: `${Math.min(100, row.break_low_rate ?? 0)}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500 flex items-center justify-between">
                        <span>Double Break</span>
                        <span className="text-fuchsia-400 font-semibold font-mono">{(row.double_break_rate ?? 0).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-900">
                        <div
                          className="h-full rounded-full bg-fuchsia-500"
                          style={{ width: `${Math.min(100, row.double_break_rate ?? 0)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Front-Running & Level Touches */}
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-4 flex items-center gap-2">
              <span className="text-amber-300"><Zap className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                Front-Running & Level Touches
                <TooltipHelp text="Tracks mid-line front-running activations inside the IB session, and subsequent Fib level touches during the outcome window." />
              </h2>
            </div>

            {/* Front-running stats */}
            <div className="mb-6 grid grid-cols-3 gap-4 rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 flex items-center">
                  Activation Rate
                  <TooltipHelp text="Frequency of price touching the provisional mid when it has already equaled the final mid before the IB close." />
                </div>
                <div className="mt-2 text-xl font-bold text-amber-300">
                  {frontRunStats ? `${(frontRunStats.rate ?? 0).toFixed(1)}%` : '--'}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">of all sessions</div>
              </div>
              
              <div>
                <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500">Median Activation</div>
                <div className="mt-2 text-xl font-semibold text-emerald-400 font-mono">
                  {frontRunStats?.median_mins != null ? `${Math.round(frontRunStats.median_mins)} mins` : '--'}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">from session open</div>
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500">Mode Activation</div>
                <div className="mt-2 text-xl font-semibold text-sky-400 font-mono">
                  {frontRunStats?.mode_mins != null ? `${Math.round(frontRunStats.mode_mins)} mins` : '--'}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">5m bucket peak</div>
              </div>
            </div>

            {/* Level touches table */}
            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500 sticky top-0">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Level %</th>
                    <th className="px-4 py-2.5 text-right font-mono">Touch Rate %</th>
                    <th className="px-4 py-2.5 text-right">Median Time</th>
                    <th className="px-4 py-2.5 text-right">Mode Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20 font-mono text-xs">
                  {levelTouchOutcomeRows.map((row, idx) => (
                    <tr key={`${row.level_pct}-${idx}`} className="hover:bg-zinc-900/30">
                      <td className="px-4 py-2 text-zinc-200 font-semibold">{row.level_pct}%</td>
                      <td className="px-4 py-2 text-right text-emerald-400 font-semibold">
                        {(row.touch_rate ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-4 py-2 text-right text-zinc-300">
                        {formatTimeFromEpoch(row.median_epoch)}
                      </td>
                      <td className="px-4 py-2 text-right text-zinc-400">
                        {row.mode_touch_time || '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* ΓöÇΓöÇ DST VALIDATION ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */}
        <Card className="border-zinc-900 bg-black/30 p-5 mt-6">
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <span className="text-amber-300"><Waves className="h-5 w-5" /></span>
              <h2 className="text-lg font-semibold tracking-tight flex items-center">
                DST Validation (Tokyo & London Slots)
                <TooltipHelp text="Compares fixed ET session hours against timezone-adjusted event-anchored boundaries during weeks where US/UK/JP DST shifts are misaligned." />
              </h2>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Only showing dates under <strong>dst_regime = 'shifted'</strong> (misaligned DST weeks) to isolate timezone drift effects.
            </p>
          </div>
          <div className="overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Session</th>
                  <th className="px-4 py-3 text-left">Basis</th>
                  <th className="px-4 py-3 text-right">Sample (N)</th>
                  <th className="px-4 py-3 text-right">Break Rate %</th>
                  <th className="px-4 py-3 text-right">Combined Bias Accuracy %</th>
                  <th className="px-4 py-3 text-right">Play 1 Win %</th>
                  <th className="px-4 py-3 text-right">Play 2 Win %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {dstRows.map((row, idx) => (
                  <tr key={`${row.session_slot}-${row.time_basis}-${idx}`}>
                    <td className="px-4 py-3 text-zinc-200 font-semibold">{row.session_slot}</td>
                    <td className={`px-4 py-3 font-mono text-xs ${row.time_basis === 'event_anchored' ? 'text-amber-300 font-semibold' : 'text-zinc-500'}`}>
                      {row.time_basis}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-400">
                      {Math.round(row.sample).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right text-sky-400">
                      {Number(row.break_rate ?? 0).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-emerald-400">
                      {Number(row.bias_accuracy ?? 0).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300">
                      {row.play1_win_rate != null ? `${row.play1_win_rate.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300">
                      {row.play2_win_rate != null ? `${row.play2_win_rate.toFixed(1)}%` : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Analysis Takeaway / Warning Note */}
          <div className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 text-xs text-amber-200">
            <span className="font-semibold uppercase tracking-wider block mb-1">Analysis Note:</span>
            Locked EST slots show significant statistical degradation (3-5% win rate drops) during shifted weeks. Event-anchored boundaries are required to maintain statistical edge.
          </div>
        </Card>
      </div>
    </div>
  );
}
