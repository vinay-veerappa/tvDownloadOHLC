'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, BarChart2, RefreshCcw, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type EngineStatus = 'loading' | 'ready' | 'error';

type SymbolCard = {
  symbol: string;
  trading_date: string;
  day_of_week: number;
  vix_regime: string;
  gap_direction: string;
  gap_size_bucket: string;
  open_vs_pd_range: string;
  streak_direction: string;
  streak_length: number;
  occ_first_direction: string;
  is_event_day: boolean;
  event_type: string | null;
  atr_14d: number;
  atr_usage_pct: number;
  gap_fill_probability: number | null;
  or_breakout_probability: number | null;
  ib_single_break_probability: number | null;
  occ_continuation_probability: number | null;
  mop_retrace_probability: number | null;
  pdh_pdl_break_probability: number | null;
  streak_reversal_probability: number | null;
  total_vote: number;
  continuation_confluence_count: number;
  reversal_confluence_count: number;
  dominant_bias: string;
  confidence: string;
};

type TrendRow = {
  trading_date: string;
  gap_fill_probability: number | null;
  or_breakout_probability: number | null;
  occ_continuation_probability: number | null;
  mop_retrace_probability: number | null;
  streak_reversal_probability: number | null;
  dominant_bias: string;
};

type MaxDateRow = {
  max_date: string | null;
};

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const SYMBOLS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'CL1', 'GC1'];
const DOW_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PARQUET_FILE = 'daily_confluence_records.parquet';
const TABLE_NAME = 'daily_confluence_records';

const BIAS_COLORS: Record<string, string> = {
  BULLISH: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  BEARISH: 'bg-rose-500/15 text-rose-300 border border-rose-500/30',
  NEUTRAL: 'bg-zinc-500/15 text-zinc-300 border border-zinc-500/30',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH:   'bg-violet-500/15 text-violet-300 border border-violet-500/30',
  MEDIUM: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  LOW:    'bg-slate-500/15 text-slate-300 border border-slate-500/30',
};

const VIX_COLORS: Record<string, string> = {
  LOW:     'text-emerald-300',
  NORMAL:  'text-sky-300',
  HIGH:    'text-amber-300',
  EXTREME: 'text-rose-300',
};

const TREND_COLORS = {
  gap_fill_probability:         '#6366f1',
  or_breakout_probability:      '#10b981',
  occ_continuation_probability: '#f59e0b',
  mop_retrace_probability:      '#ef4444',
  streak_reversal_probability:  '#8b5cf6',
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
}

function quote(s: string) {
  return `'${s.replace(/'/g, "''")}'`;
}

function ProbBar({
  label,
  value,
  context,
}: {
  label: string;
  value: number | null | undefined;
  context?: string;
}) {
  const pctVal = value == null || Number.isNaN(value) ? null : value * 100;
  const barColor =
    pctVal == null
      ? 'bg-gray-200'
      : pctVal >= 60
      ? 'bg-emerald-400'
      : pctVal >= 52
      ? 'bg-amber-400'
      : 'bg-red-300';

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-32 text-zinc-300 shrink-0 text-xs font-medium">{label}</span>
      <div className="flex-1 h-2.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor} transition-all`}
          style={{ width: pctVal != null ? `${Math.min(pctVal, 100)}%` : '0%' }}
        />
      </div>
      <span className="w-12 text-right text-xs font-mono text-zinc-100">{pct(value)}</span>
      {context && <span className="text-xs text-zinc-400 italic">{context}</span>}
    </div>
  );
}

function BiasIcon({ bias }: { bias: string }) {
  if (bias === 'BULLISH') return <TrendingUp className="w-4 h-4 text-emerald-300" />;
  if (bias === 'BEARISH') return <TrendingDown className="w-4 h-4 text-rose-300" />;
  return <Minus className="w-4 h-4 text-zinc-400" />;
}

function SymbolCardView({ card }: { card: SymbolCard }) {
  const dowName = DOW_NAMES[card.day_of_week] ?? '';
  const vixClass = VIX_COLORS[card.vix_regime] ?? 'text-gray-600';
  const biasClass = BIAS_COLORS[card.dominant_bias] ?? BIAS_COLORS.NEUTRAL;
  const confClass = CONFIDENCE_COLORS[card.confidence] ?? CONFIDENCE_COLORS.LOW;

  const gapContext =
    card.gap_direction === 'NONE'
      ? 'no gap'
      : `${card.gap_direction.toLowerCase()} • ${(card.gap_size_bucket ?? '').toLowerCase()}`;

  const occContext = card.occ_first_direction
    ? card.occ_first_direction.toLowerCase() + ' candle'
    : undefined;

  const streakContext = card.streak_direction
    ? `${card.streak_length}d ${card.streak_direction.toLowerCase()} streak`
    : undefined;

  return (
    <Card className="p-4 flex flex-col gap-3 border-zinc-900 bg-black/30 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-zinc-100">{card.symbol}</span>
        <div className="flex items-center gap-1.5">
          <BiasIcon bias={card.dominant_bias} />
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${biasClass}`}>
            {card.dominant_bias}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${confClass}`}>
            {card.confidence}
          </span>
        </div>
      </div>

      {/* Context */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-400">
        <span>{dowName}</span>
        <span className={`font-medium ${vixClass}`}>{card.vix_regime}</span>
        {card.is_event_day && (
          <span className="text-amber-300 font-semibold">
            EVENT{card.event_type ? ` (${card.event_type})` : ''}
          </span>
        )}
        <span>ATR use: {card.atr_usage_pct != null ? `${card.atr_usage_pct.toFixed(0)}%` : '—'}</span>
        <span>{(card.open_vs_pd_range ?? '').replace(/_/g, ' ')}</span>
      </div>

      {/* Probability bars */}
      <div className="flex flex-col gap-1.5">
        <ProbBar label="Gap Fill" value={card.gap_fill_probability} context={gapContext} />
        <ProbBar label="OR-15 Breakout" value={card.or_breakout_probability} />
        <ProbBar label="OCC Continuation" value={card.occ_continuation_probability} context={occContext} />
        <ProbBar label="MOP Retrace" value={card.mop_retrace_probability} />
        <ProbBar label="Streak Reversal" value={card.streak_reversal_probability} context={streakContext} />
        <ProbBar label="PD Level Break" value={card.pdh_pdl_break_probability} />
      </div>

      {/* Vote summary */}
      <div className="flex gap-3 text-xs pt-1 border-t border-zinc-800">
        <span className="text-emerald-300 font-semibold">
          ↑ {card.continuation_confluence_count} continuation
        </span>
        <span className="text-rose-300 font-semibold">
          ↓ {card.reversal_confluence_count} reversal
        </span>
        <span className="text-zinc-300 ml-auto font-medium">net {card.total_vote > 0 ? '+' : ''}{card.total_vote}</span>
      </div>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ScreenerPage() {
  const [status, setStatus] = useState<EngineStatus>('loading');
  const [statusMsg, setStatusMsg] = useState('Initialising DuckDB…');
  const [cards, setCards] = useState<SymbolCard[]>([]);
  const [maxDate, setMaxDate] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [biasFilter, setBiasFilter] = useState('ALL');

  // Trend section
  const [trendSymbol, setTrendSymbol] = useState('NQ1');
  const [trendLookback, setTrendLookback] = useState('252');
  const [trendData, setTrendData] = useState<TrendRow[]>([]);

  // ── Engine init ────────────────────────────────────────────────────────────
  const initEngine = useCallback(async () => {
    setStatus('loading');
    setStatusMsg('Initialising DuckDB…');
    try {
      await initDuckDB();
      setStatusMsg('Loading confluence parquet…');
      const version = Date.now();
      await loadParquet(PARQUET_FILE, `/api/data/${PARQUET_FILE}?v=${version}`);
      const rows = await runQuery<MaxDateRow>(
        `SELECT MAX(trading_date)::VARCHAR AS max_date FROM ${TABLE_NAME}`
      );
      const md = rows[0]?.max_date ?? '';
      setMaxDate(md);
      setSelectedDate(md);
      setStatus('ready');
    } catch (e) {
      setStatus('error');
      setStatusMsg(String(e));
    }
  }, []);

  useEffect(() => {
    initEngine();
  }, [initEngine]);

  // ── Card query ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (status !== 'ready' || !selectedDate) return;
    const biasWhere = biasFilter !== 'ALL' ? `AND dominant_bias = ${quote(biasFilter)}` : '';

    runQuery<SymbolCard>(`
      SELECT
        symbol, trading_date::VARCHAR AS trading_date,
        day_of_week, vix_regime,
        gap_direction, gap_size_bucket, open_vs_pd_range,
        streak_direction, streak_length,
        occ_first_direction,
        is_event_day, event_type,
        atr_14d, atr_usage_pct,
        gap_fill_probability::DOUBLE AS gap_fill_probability,
        or_breakout_probability::DOUBLE AS or_breakout_probability,
        ib_single_break_probability::DOUBLE AS ib_single_break_probability,
        occ_continuation_probability::DOUBLE AS occ_continuation_probability,
        mop_retrace_probability::DOUBLE AS mop_retrace_probability,
        pdh_pdl_break_probability::DOUBLE AS pdh_pdl_break_probability,
        streak_reversal_probability::DOUBLE AS streak_reversal_probability,
        total_vote, continuation_confluence_count, reversal_confluence_count,
        dominant_bias, confidence
      FROM ${TABLE_NAME}
      WHERE trading_date = ${quote(selectedDate)} ${biasWhere}
      ORDER BY ABS(total_vote) DESC, symbol
    `).then(setCards).catch(console.error);
  }, [status, selectedDate, biasFilter]);

  // ── Trend query ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (status !== 'ready') return;
    const lookback = parseInt(trendLookback, 10);
    const lookbackWhere = !Number.isNaN(lookback)
      ? `AND trading_date >= (SELECT MAX(trading_date) - INTERVAL '${lookback}' DAY FROM ${TABLE_NAME})`
      : '';

    runQuery<TrendRow>(`
      SELECT
        trading_date::VARCHAR AS trading_date,
        gap_fill_probability::DOUBLE AS gap_fill_probability,
        or_breakout_probability::DOUBLE AS or_breakout_probability,
        occ_continuation_probability::DOUBLE AS occ_continuation_probability,
        mop_retrace_probability::DOUBLE AS mop_retrace_probability,
        streak_reversal_probability::DOUBLE AS streak_reversal_probability,
        dominant_bias
      FROM ${TABLE_NAME}
      WHERE symbol = ${quote(trendSymbol)} ${lookbackWhere}
      ORDER BY trading_date
    `).then(setTrendData).catch(console.error);
  }, [status, trendSymbol, trendLookback]);

  const handleReset = useCallback(async () => {
    await resetDuckDB();
    initEngine();
  }, [initEngine]);

  const filteredCards = useMemo(() => cards, [cards]);

  // ── Render ─────────────────────────────────────────────────────────────────

  if (status !== 'ready') {
    return (
      <div className="p-12 flex flex-col items-center gap-3 text-gray-500">
        {status === 'loading' ? (
          <>
            <RefreshCcw className="w-6 h-6 animate-spin" />
            <span className="text-sm">{statusMsg}</span>
          </>
        ) : (
          <>
            <span className="text-sm text-red-500">Error: {statusMsg}</span>
            <Button variant="outline" size="sm" onClick={handleReset}>Retry</Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(139,92,246,0.14),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.12),_transparent_28%),#050816] p-6 max-w-7xl mx-auto space-y-8 text-zinc-100">
      {/* Page header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm text-zinc-500 mb-1">
            <Link href="/research" className="hover:text-violet-300 flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Research
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-violet-300" />
            What&apos;s in Play
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Daily edge-signal confluence — probability-weighted setup screener
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleReset} className="flex items-center gap-1 border-zinc-700 bg-zinc-950/70 text-zinc-100 hover:bg-zinc-900">
          <RefreshCcw className="w-4 h-4" /> Reload
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-4 items-end bg-black/30 rounded-lg p-4 border border-zinc-900 backdrop-blur-sm">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-400">Date</label>
          <input
            type="date"
            className="h-9 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm text-zinc-100"
            value={selectedDate}
            max={maxDate}
            onChange={(e) => setSelectedDate(e.target.value || maxDate)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-400">Bias filter</label>
          <select
            className="h-9 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm text-zinc-100"
            value={biasFilter}
            onChange={(e) => setBiasFilter(e.target.value)}
          >
            {['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'].map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>
        <div className="ml-auto text-xs text-zinc-400 self-end">
          {selectedDate && (
            <span>
              Showing {filteredCards.length} symbol{filteredCards.length !== 1 ? 's' : ''} ·{' '}
              {selectedDate}
            </span>
          )}
        </div>
      </div>

      {/* Symbol cards */}
      {filteredCards.length === 0 ? (
        <Card className="p-8 text-center text-zinc-400 border-zinc-900 bg-black/30">
          No data for {selectedDate}. Try a different date.
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCards.map((card) => (
            <SymbolCardView key={card.symbol} card={card} />
          ))}
        </div>
      )}

      {/* Legend */}
      <Card className="p-4 border-zinc-900 bg-black/30 backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-zinc-100 mb-3">Signal Interpretation Guide</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs text-zinc-300">
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">Gap Fill</span>
            <p className="mt-1">Historical P(gap fills | DOW, VIX regime). &gt;55% = edge. Gap-up fill → bearish; gap-down fill → bullish.</p>
          </div>
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">OR-15 Breakout</span>
            <p className="mt-1">Historical OR-15 BO_1X win rate | DOW + VIX. Green bar = historically productive breakout environment.</p>
          </div>
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">OCC Continuation</span>
            <p className="mt-1">Opening candle (15-min) continuation rate. High + bullish candle → continuation long edge.</p>
          </div>
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">MOP Retrace</span>
            <p className="mt-1">P(price returns to Midnight Open) by end of session. Mean-reversion signal.</p>
          </div>
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">Streak Reversal</span>
            <p className="mt-1">P(streak ends today | streak direction + length). High = fade the trend.</p>
          </div>
          <div className="bg-zinc-900/60 rounded p-2 border border-zinc-800">
            <span className="font-medium text-zinc-100">PD Level Break</span>
            <p className="mt-1">P(PDH or PDL broken today | DOW, VIX). Context for expansion vs compression days.</p>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t border-zinc-800 flex flex-wrap gap-4 text-xs text-zinc-300">
          <span>
            <span className="inline-block w-3 h-2 rounded bg-emerald-400 mr-1" />≥60% (edge)
          </span>
          <span>
            <span className="inline-block w-3 h-2 rounded bg-amber-400 mr-1" />52–60% (lean)
          </span>
          <span>
            <span className="inline-block w-3 h-2 rounded bg-red-300 mr-1" />&lt;52% (no edge)
          </span>
          <span className="ml-auto">Confidence: MEDIUM = 2 of 5 signals aligned · HIGH = 3+</span>
        </div>
      </Card>

      {/* Probability trend */}
      <Card className="p-4 border-zinc-900 bg-black/30 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-base font-semibold text-zinc-100">Probability Trend</h2>
          <div className="flex gap-3 items-end flex-wrap">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-zinc-400">Symbol</label>
              <select
                className="h-9 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm text-zinc-100"
                value={trendSymbol}
                onChange={(e) => setTrendSymbol(e.target.value)}
              >
                {SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-zinc-400">Lookback (days)</label>
              <select
                className="h-9 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm text-zinc-100"
                value={trendLookback}
                onChange={(e) => setTrendLookback(e.target.value)}
              >
                <option value="126">6 months</option>
                <option value="252">1 year</option>
                <option value="504">2 years</option>
                <option value="0">All time</option>
              </select>
            </div>
          </div>
        </div>

        {trendData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-zinc-400 text-sm">
            No trend data
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="trading_date"
                tick={{ fontSize: 11, fill: '#a1a1aa' }}
                tickFormatter={(v: string) => v.slice(0, 7)}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0.3, 0.9]}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                tick={{ fontSize: 11, fill: '#a1a1aa' }}
                width={40}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', color: '#f4f4f5' }}
                labelStyle={{ color: '#d4d4d8' }}
                formatter={(v: number, name: string) => [
                  `${(v * 100).toFixed(1)}%`,
                  name.replace(/_/g, ' ').replace('probability', '').trim(),
                ]}
                labelFormatter={(l: string) => `Date: ${l}`}
              />
              <Legend
                wrapperStyle={{ color: '#d4d4d8' }}
                formatter={(v: string) =>
                  v.replace(/_/g, ' ').replace('probability', '').trim()
                }
              />
              {Object.entries(TREND_COLORS).map(([key, color]) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={color}
                  dot={false}
                  strokeWidth={1.5}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="text-xs text-zinc-400 mt-2">
          Rolling expanding conditional probabilities (causal — no look-ahead). Each line reflects
          P(signal event | day-of-week, VIX regime) using all history prior to that date.
        </p>
      </Card>
    </div>
  );
}
