"use client";

import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
} from "recharts";

type ByStrikeRow = {
  strike?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_oi?: number;
  put_oi?: number;
};

type Props = {
  rows: ByStrikeRow[];
  spot: number | null;
  gammaFlip?: number | null;
  highlightedStrike?: number | null;
  sortMode?: "strike" | "abs";
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

type ChartRow = {
  strike: number;
  call_gex: number;
  put_gex_neg: number; // stored as negative for left extension
  net_gex: number;
  isAtm: boolean;
};

export function ByStrikeSplitBars({ rows, spot, gammaFlip, highlightedStrike = null, sortMode = "strike" }: Props) {
  const chartData = useMemo((): ChartRow[] => {
    if (!rows.length) return [];
    const base = [...rows]
      .filter((r) => r.strike != null)
      .sort((a, b) => (a.strike ?? 0) - (b.strike ?? 0));

    const sorted =
      sortMode === "abs"
        ? [...base].sort(
            (a, b) =>
              Math.abs((b.net_gex ?? 0)) - Math.abs((a.net_gex ?? 0)) ||
              (a.strike ?? 0) - (b.strike ?? 0)
          )
        : base;

    return sorted.map((r) => {
      const strike = r.strike ?? 0;
      const atmDistance = spot ? Math.abs(strike - spot) : Infinity;
      const allDists = sorted.map((s) => (spot ? Math.abs((s.strike ?? 0) - spot) : Infinity));
      const minDist = Math.min(...allDists);
      return {
        strike,
        call_gex: r.call_gex ?? 0,
        put_gex_neg: -(r.put_gex ?? 0), // flip sign so it extends left
        net_gex: r.net_gex ?? 0,
        isAtm: atmDistance === minDist,
      };
    });
  }, [rows, spot, sortMode]);

  if (!chartData.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">GEX by Strike</h2>
        <p className="text-sm text-zinc-500">No strike data available.</p>
      </div>
    );
  }

  // Axis domain: symmetric around 0
  const maxAbs = Math.max(
    ...chartData.map((d) => Math.max(Math.abs(d.call_gex), Math.abs(d.put_gex_neg)))
  );

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">GEX by Strike</h2>
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm bg-emerald-600" /> Call GEX
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm bg-rose-600" /> Put GEX
          </span>
          {gammaFlip && <span className="text-violet-400">Γ Flip: {gammaFlip.toFixed(2)}</span>}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={chartData.length * 24 + 48}>
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 12, bottom: 4, left: 64 }}
          barCategoryGap="20%"
        >
          <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            type="number"
            domain={[-maxAbs * 1.1, maxAbs * 1.1]}
            tickFormatter={fmt}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#3f3f46" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="strike"
            tick={({ y, payload }: { y: number; payload: { value: number } }) => {
              const row = chartData.find((d) => d.strike === payload.value);
              return (
                <text
                  x={60}
                  y={y}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fill={row?.isAtm ? "#34d399" : "#a1a1aa"}
                  fontSize={10}
                  fontWeight={row?.isAtm ? 700 : 400}
                >
                  {payload.value.toFixed(0)}
                </text>
              );
            }}
            width={64}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              backgroundColor: "#09090b",
              border: "1px solid #27272a",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#e4e4e7",
            }}
            formatter={(value: number, name: string) => {
              const label = name === "call_gex" ? "Call GEX" : name === "put_gex_neg" ? "Put GEX" : "Net GEX";
              const displayVal = name === "put_gex_neg" ? -value : value;
              return [fmt(displayVal), label];
            }}
          />

          {/* Zero line */}
          <ReferenceLine x={0} stroke="#3f3f46" strokeWidth={1} />

          {/* Gamma flip reference line */}
          {gammaFlip && (
            <ReferenceLine
              y={gammaFlip}
              stroke="#7c3aed"
              strokeDasharray="4 2"
              strokeWidth={1.5}
            />
          )}

          {/* Call GEX bars (extend right, positive) */}
          <Bar dataKey="call_gex" name="call_gex" radius={[0, 2, 2, 0]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={highlightedStrike === entry.strike ? "#22c55e" : entry.isAtm ? "#059669" : "#16a34a"}
                opacity={highlightedStrike === entry.strike ? 1 : entry.isAtm ? 1 : 0.75}
              />
            ))}
          </Bar>

          {/* Put GEX bars (extend left, stored as negative) */}
          <Bar dataKey="put_gex_neg" name="put_gex_neg" radius={[2, 0, 0, 2]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={highlightedStrike === entry.strike ? "#fb7185" : entry.isAtm ? "#dc2626" : "#e11d48"}
                opacity={highlightedStrike === entry.strike ? 1 : entry.isAtm ? 1 : 0.75}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
