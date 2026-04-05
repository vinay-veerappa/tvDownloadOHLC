"use client";

import React, { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { StatCard } from "@/components/options-live-v3/StatCard";

type SpotGammaSeries = {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  cumulative_gex: number;
};

type SpotGammaCurrent = {
  atm_strike: number | null;
  call_gex: number | null;
  put_gex: number | null;
  net_gex: number | null;
};

type SpotGammaData = {
  series: SpotGammaSeries[];
  current: SpotGammaCurrent | null;
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function toneByNumber(v: number | null | undefined): "positive" | "negative" | "neutral" {
  if (v == null) return "neutral";
  return v >= 0 ? "positive" : "negative";
}

type Props = {
  data: SpotGammaData | null;
  isLoading?: boolean;
};

export function SpotGammaPanel({ data, isLoading }: Props) {
  const series = data?.series ?? [];
  const current = data?.current ?? null;

  const displaySeries = useMemo(() => {
    if (!series.length) return [];
    // Sort by strike ascending for chart continuity
    return [...series].sort((a, b) => a.strike - b.strike);
  }, [series]);

  // Find domain extremes for cumulative_gex
  const [minCum, maxCum] = useMemo(() => {
    if (!displaySeries.length) return [0, 0];
    const vals = displaySeries.map((d) => d.cumulative_gex);
    return [Math.min(...vals), Math.max(...vals)];
  }, [displaySeries]);

  const zeroFlipStrike = useMemo(() => {
    // Find strike where cumulative_gex crosses zero
    for (let i = 1; i < displaySeries.length; i++) {
      const prev = displaySeries[i - 1];
      const curr = displaySeries[i];
      if ((prev.cumulative_gex >= 0) !== (curr.cumulative_gex >= 0)) {
        return (prev.strike + curr.strike) / 2;
      }
    }
    return null;
  }, [displaySeries]);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Spot-Gamma Profile</h2>
        <p className="text-sm animate-pulse text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!displaySeries.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Spot-Gamma Profile</h2>
        <p className="text-sm text-zinc-500">No spot-gamma data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Spot-Gamma Profile</h2>
        {current?.atm_strike && (
          <span className="text-xs text-zinc-400">
            ATM: <span className="font-mono text-emerald-300">{current.atm_strike.toFixed(2)}</span>
          </span>
        )}
      </div>

      {/* ATM stats */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatCard
          label="Net GEX @ ATM"
          value={fmt(current?.net_gex ?? 0)}
          tone={toneByNumber(current?.net_gex)}
        />
        <StatCard
          label="Call GEX @ ATM"
          value={fmt(current?.call_gex ?? 0)}
          tone="positive"
        />
        <StatCard
          label="Put GEX @ ATM"
          value={fmt(current?.put_gex ?? 0)}
          tone="negative"
        />
        {zeroFlipStrike !== null && (
          <StatCard
            label="Γ Flip (curve)"
            value={zeroFlipStrike.toFixed(2)}
            tone="neutral"
          />
        )}
      </div>

      {/* Cumulative GEX area chart */}
      <div>
        <p className="mb-1 text-xs text-zinc-500 uppercase tracking-wider">Cumulative GEX Profile</p>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={displaySeries} margin={{ top: 4, right: 12, bottom: 4, left: 8 }}>
            <defs>
              <linearGradient id="cumGexPositive" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#059669" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#059669" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="cumGexNegative" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#e11d48" stopOpacity={0} />
                <stop offset="95%" stopColor="#e11d48" stopOpacity={0.3} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="strike"
              tick={{ fill: "#71717a", fontSize: 10 }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              tickFormatter={(v: number) => v.toFixed(0)}
            />
            <YAxis
              tick={{ fill: "#71717a", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={fmt}
              width={48}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#09090b",
                border: "1px solid #27272a",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#e4e4e7",
              }}
              formatter={(value: number) => [fmt(value), "Cum GEX"]}
              labelFormatter={(label: number) => `Strike: ${label}`}
            />
            <ReferenceLine y={0} stroke="#3f3f46" strokeWidth={1.5} label={{ value: "0", fill: "#71717a", fontSize: 10 }} />
            {/* ATM reference line */}
            {current?.atm_strike && (
              <ReferenceLine
                x={current.atm_strike}
                stroke="#34d399"
                strokeDasharray="4 2"
                strokeWidth={1.5}
                label={{ value: "ATM", fill: "#34d399", fontSize: 10 }}
              />
            )}
            {/* Zero-flip reference */}
            {zeroFlipStrike !== null && (
              <ReferenceLine
                x={zeroFlipStrike}
                stroke="#7c3aed"
                strokeDasharray="2 2"
                strokeWidth={1}
              />
            )}
            <Area
              type="monotone"
              dataKey="cumulative_gex"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#cumGexPositive)"
              dot={false}
              activeDot={{ r: 3, fill: "#34d399" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Net GEX per-strike bar sparkline */}
      <div>
        <p className="mb-1 text-xs text-zinc-500 uppercase tracking-wider">Net GEX per Strike</p>
        <ResponsiveContainer width="100%" height={80}>
          <AreaChart data={displaySeries} margin={{ top: 2, right: 12, bottom: 2, left: 8 }}>
            <XAxis dataKey="strike" hide />
            <YAxis hide />
            <ReferenceLine y={0} stroke="#3f3f46" strokeWidth={1} />
            {current?.atm_strike && (
              <ReferenceLine x={current.atm_strike} stroke="#34d399" strokeWidth={1} strokeDasharray="3 2" />
            )}
            <Area
              type="monotone"
              dataKey="net_gex"
              stroke="#6366f1"
              strokeWidth={1.5}
              fill="#6366f1"
              fillOpacity={0.2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
