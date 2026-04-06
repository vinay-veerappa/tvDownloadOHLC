"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

type ByExpiryRow = {
  expiry?: string;
  dte?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_oi?: number;
  put_oi?: number;
  call_vol?: number;
  put_vol?: number;
};

type Props = {
  rows: ByExpiryRow[] | null;
  isLoading?: boolean;
  viewMode?: "split" | "net";
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function ExpiryTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: {
  expiry: string;
  dte: number | null;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  call_oi: number;
  put_oi: number;
  total_oi: number;
  call_vol: number;
  put_vol: number;
  total_vol: number;
} }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="min-w-[190px] rounded-md border border-zinc-800 bg-zinc-950/95 p-3 shadow-xl">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-300">Expiry {row.expiry}</div>
      <div className="space-y-1 text-xs">
        {row.dte !== null && (
          <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">DTE</span><span className="text-zinc-100">{row.dte}</span></div>
        )}
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Call GEX</span><span className="text-emerald-300">{fmt(row.call_gex)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Put GEX</span><span className="text-rose-300">{fmt(row.put_gex)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Net GEX</span><span className="text-violet-300">{fmt(row.net_gex)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Call OI</span><span className="text-zinc-100">{fmt(row.call_oi)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Put OI</span><span className="text-zinc-100">{fmt(row.put_oi)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Total OI</span><span className="text-zinc-100">{fmt(row.total_oi)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Call Vol</span><span className="text-zinc-100">{fmt(row.call_vol)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Put Vol</span><span className="text-zinc-100">{fmt(row.put_vol)}</span></div>
        <div className="flex items-center justify-between gap-4"><span className="text-zinc-400">Total Vol</span><span className="text-zinc-100">{fmt(row.total_vol)}</span></div>
      </div>
    </div>
  );
}

export function ByExpiryAggregationChart({ rows, isLoading, viewMode = "split" }: Props) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">GEX by Expiry</h2>
        <p className="text-sm animate-pulse text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!rows || !rows.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">GEX by Expiry</h2>
        <p className="text-sm text-zinc-500">No expiry data available.</p>
      </div>
    );
  }

  // Sort by expiry (date)
  const sortedRows = [...rows].sort((a, b) =>
    (a.expiry ?? "").localeCompare(b.expiry ?? "")
  );

  // Transform for Recharts (add put_gex as negative for stacked area)
  const chartData = sortedRows.map((row) => ({
    expiry: row.expiry ?? "Unknown",
    dte: row.dte ?? null,
    call_gex: Math.max(0, row.call_gex ?? 0),
    put_gex_neg: Math.min(0, row.put_gex ?? 0), // Keep as negative
    put_gex: row.put_gex ?? 0,
    net_gex: row.net_gex ?? 0,
    call_oi: row.call_oi ?? 0,
    put_oi: row.put_oi ?? 0,
    total_oi: (row.call_oi ?? 0) + (row.put_oi ?? 0),
    call_vol: row.call_vol ?? 0,
    put_vol: row.put_vol ?? 0,
    total_vol: (row.call_vol ?? 0) + (row.put_vol ?? 0),
  }));

  const [minNet, maxNet] = chartData.reduce(
    ([min, max], d) => [
      Math.min(min, d.net_gex),
      Math.max(max, d.net_gex),
    ],
    [Infinity, -Infinity]
  );

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <h2 className="text-sm font-semibold text-zinc-200">GEX by Expiry Date</h2>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
        >
          <defs>
            <linearGradient id="callGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#059669" stopOpacity={0.6} />
              <stop offset="95%" stopColor="#059669" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="putGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#dc2626" stopOpacity={0} />
              <stop offset="95%" stopColor="#dc2626" stopOpacity={0.6} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="expiry"
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#3f3f46" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={fmt}
            domain={[minNet * 1.1, maxNet * 1.1]}
            width={48}
          />
          <Tooltip
            content={<ExpiryTooltip />}
          />
          <Legend
            wrapperStyle={{ paddingTop: "12px" }}
            iconType="line"
          />
          <ReferenceLine y={0} stroke="#3f3f46" strokeWidth={1} />
          {viewMode === "split" && (
            <Area
              type="monotone"
              dataKey="call_gex"
              name="Call GEX"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#callGradient)"
              dot={false}
              isAnimationActive={false}
            />
          )}
          {viewMode === "split" && (
            <Area
              type="monotone"
              dataKey="put_gex_neg"
              name="Put GEX"
              stroke="#ef4444"
              strokeWidth={2}
              fill="url(#putGradient)"
              dot={false}
              isAnimationActive={false}
            />
          )}
          <Area
            type="monotone"
            dataKey="net_gex"
            name="Net GEX"
            stroke="#6366f1"
            strokeWidth={2.5}
            fill="none"
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-2">
        {chartData.map((d, idx) => (
          <div
            key={idx}
            className="rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1.5 text-xs"
          >
            <p className="font-mono text-zinc-400">{d.expiry}</p>
            <p className={`text-sm font-semibold ${d.net_gex >= 0 ? "text-green-400" : "text-red-400"}`}>
              {fmt(d.net_gex)}
            </p>
            <p className="text-zinc-500">
              {fmt(d.call_oi + d.put_oi)} OI
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
