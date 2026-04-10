'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  LineChart, 
  Line, 
  ResponsiveContainer, 
  YAxis, 
  XAxis, 
  Tooltip 
} from 'recharts';
import { 
  Beaker, 
  ChevronRight, 
  BarChart3, 
  TrendingUp, 
  Activity,
  History,
  Target,
  LayoutDashboard,
  Waves,
  SplitSquareVertical,
  GitCompareArrows,
  Clock3
} from 'lucide-react';

interface ResearchRun {
  id: string;
  runId: string;
  ticker: string;
  grade: string;
  metricsJson: string;
  thumbnailJson: string;
  createdAt: string;
}

interface StrategyGroup {
  id: string;
  name: string;
  description: string;
  runs: ResearchRun[];
}

export default function ResearchDashboard() {
  const [strategies, setStrategies] = useState<StrategyGroup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch('/api/research/strategies');
        const data = await response.json();
        setStrategies(data);
      } catch (error) {
        console.error('Failed to fetch research data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-full text-muted-foreground animate-pulse">
      <Beaker className="mr-2 h-5 w-5" />
      Analyzing Research Hierarchy...
    </div>
  );

  return (
    <div className="space-y-8 pb-10">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            Research Hub
          </h1>
          <p className="text-muted-foreground mt-1">
            Institutional strategy optimization and performance hierarchy.
          </p>
        </div>
        <div className="flex gap-4">
          <div className="px-4 py-2 bg-primary/5 border border-primary/10 rounded-lg flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{strategies.length} Strategies</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <Link
          href="/research/ranges"
          className="group rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/10 via-transparent to-transparent p-5 transition hover:border-cyan-400/40 hover:bg-cyan-500/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
                <LayoutDashboard className="h-3.5 w-3.5" />
                New Dashboard
              </div>
              <h2 className="text-xl font-bold text-white">Range Analytics</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Explore OR and IB range structure, extension hit rates, and strategy outcomes directly from the new parquet pipeline.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-cyan-300 transition group-hover:translate-x-1" />
          </div>
        </Link>

        <Link
          href="/research/range-comparison"
          className="group rounded-2xl border border-sky-500/20 bg-gradient-to-br from-sky-500/10 via-transparent to-transparent p-5 transition hover:border-sky-400/40 hover:bg-sky-500/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-sky-300">
                <GitCompareArrows className="h-3.5 w-3.5" />
                New Dashboard
              </div>
              <h2 className="text-xl font-bold text-white">Range Comparison</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Compare OR and IB definitions on follow-through, failed breakout behavior, mid retests, and selected strategy performance.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-sky-300 transition group-hover:translate-x-1" />
          </div>
        </Link>

        <Link
          href="/research/gaps"
          className="group rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-transparent to-transparent p-5 transition hover:border-emerald-400/40 hover:bg-emerald-500/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-emerald-300">
                <SplitSquareVertical className="h-3.5 w-3.5" />
                New Dashboard
              </div>
              <h2 className="text-xl font-bold text-white">Gap Analytics</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Track gap-fill behavior, directional continuation, and rolling fill probabilities across symbols and event contexts.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-emerald-300 transition group-hover:translate-x-1" />
          </div>
        </Link>

        <Link
          href="/research/reference-levels"
          className="group rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/10 via-transparent to-transparent p-5 transition hover:border-amber-400/40 hover:bg-amber-500/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-amber-300">
                <BarChart3 className="h-3.5 w-3.5" />
                New Dashboard
              </div>
              <h2 className="text-xl font-bold text-white">Reference Levels</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Explore midnight-open retraces, PDH and PDL continuation, outside-day reversals, and weekly reference interaction.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-amber-300 transition group-hover:translate-x-1" />
          </div>
        </Link>

        <Link
          href="/research/session-breakouts"
          className="group rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-500/10 via-transparent to-transparent p-5 transition hover:border-indigo-400/40 hover:bg-indigo-500/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-indigo-300">
                <Clock3 className="h-3.5 w-3.5" />
                New Dashboard
              </div>
              <h2 className="text-xl font-bold text-white">Session Breakouts</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Analyze London-to-NY break behavior, first-break continuation odds, reversal risk, and NY close location.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-indigo-300 transition group-hover:translate-x-1" />
          </div>
        </Link>

        <Link
          href="/edgeful"
          className="group rounded-2xl border border-primary/10 bg-gradient-to-br from-primary/10 via-transparent to-transparent p-5 transition hover:border-primary/30 hover:bg-primary/10"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-primary">
                <Waves className="h-3.5 w-3.5" />
                Existing Surface
              </div>
              <h2 className="text-xl font-bold text-white">Macro Analytics</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                The macro dashboard remains the dedicated surface for Judas, continuation, and FVG research.
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-primary transition group-hover:translate-x-1" />
          </div>
        </Link>
      </div>

      {/* Strategies Grid */}
      <div className="grid gap-8">
        {strategies.map((strategy) => (
          <section key={strategy.id} className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <div className="p-1.5 rounded-md bg-primary/10 border border-primary/20">
                <Target className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-bold">{strategy.name}</h2>
                <p className="text-sm text-muted-foreground">{strategy.description}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {strategy.runs.map((run) => (
                <RunCard key={run.id} run={run} />
              ))}
              {strategy.runs.length === 0 && (
                <div className="col-span-full py-12 border-2 border-dashed rounded-xl flex flex-col items-center justify-center text-muted-foreground/40 text-sm">
                  <History className="h-8 w-8 mb-2 opacity-20" />
                  No runs found for this strategy.
                </div>
              )}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function RunCard({ run }: { run: ResearchRun }) {
  const metrics = JSON.parse(run.metricsJson || '{}');
  const thumbnail = JSON.parse(run.thumbnailJson || '{"timestamps":[], "values":[]}');
  
  // Transform thumbnail for Recharts
  const chartData = thumbnail.values.map((v: number, i: number) => ({
    val: v,
    time: thumbnail.timestamps[i]
  }));

  const gradeColors: Record<string, string> = {
    'A': 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    'B': 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    'C': 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    'D': 'bg-orange-500/10 text-orange-500 border-orange-500/20',
    'F': 'bg-rose-500/10 text-rose-500 border-rose-500/20',
  };

  return (
    <Link 
      href={`/research/${run.id}`}
      className="group block relative p-5 bg-card border hover:border-primary/50 transition-all rounded-xl overflow-hidden glassmorphism shadow-sm"
    >
      {/* Background Pulse (Hover) */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

      <div className="relative space-y-4">
        {/* Run Header */}
        <div className="flex justify-between items-start">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-wider opacity-70">{run.ticker}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-black border ${gradeColors[run.grade] || 'bg-muted'}`}>
                GRADE {run.grade}
              </span>
            </div>
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Activity className="h-3 w-3" />
              {run.runId.split('_')[1]} {run.runId.split('_')[2]}
            </div>
          </div>
          <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
        </div>

        {/* Thumbnail Chart */}
        <div className="h-24 w-full -mx-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <Line 
                type="monotone" 
                dataKey="val" 
                stroke="hsl(var(--primary))" 
                strokeWidth={2} 
                dot={false}
                strokeOpacity={0.8}
              />
              <YAxis hide domain={['auto', 'auto']} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Highlight Metrics */}
        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-primary/5">
          <div className="space-y-0.5">
            <span className="text-[10px] uppercase font-bold text-muted-foreground opacity-60">Sharpe Ratio</span>
            <div className="text-sm font-mono font-bold text-primary">{metrics.sharpe?.toFixed(2)}</div>
          </div>
          <div className="space-y-0.5">
            <span className="text-[10px] uppercase font-bold text-muted-foreground opacity-60">Max DD</span>
            <div className="text-sm font-mono font-bold text-rose-500">{metrics.drawdown?.toFixed(2)}%</div>
          </div>
        </div>
      </div>
    </Link>
  );
}
