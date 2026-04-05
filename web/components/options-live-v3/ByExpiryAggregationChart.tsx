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
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_oi?: number;
  put_oi?: number;
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
    call_gex: Math.max(0, row.call_gex ?? 0),
    put_gex_neg: Math.min(0, row.put_gex ?? 0), // Keep as negative
    net_gex: row.net_gex ?? 0,
    call_oi: row.call_oi ?? 0,
    put_oi: row.put_oi ?? 0,
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
            contentStyle={{
              backgroundColor: "#09090b",
              border: "1px solid #27272a",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#e4e4e7",
            }}
            formatter={(value: number, name: string) => [fmt(value), name]}
            labelFormatter={(label: string) => `Expiry: ${label}`}
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
