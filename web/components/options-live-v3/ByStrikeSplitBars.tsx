"use client";

import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  Legend,
  ResponsiveContainer,
} from "recharts";

type ByStrikeRow = {
  strike?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_vex?: number;
  put_vex?: number;
  call_charm?: number;
  put_charm?: number;
  call_dex?: number;
  put_dex?: number;
  call_oi?: number;
  put_oi?: number;
};

type MetricFamily = "GEX" | "DEX" | "VANNA" | "CHARM";

type Props = {
  rows: ByStrikeRow[];
  spot: number | null;
  gammaFlip?: number | null;
  highlightedStrike?: number | null;
  sortMode?: "strike" | "abs";
  metricFamily?: MetricFamily;
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

const TOOLTIP_STYLE = {
  backgroundColor: "#09090b",
  border: "1px solid #27272a",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#e4e4e7",
};

// ─── Bar chart config (GEX / DEX) ────────────────────────────────────────────
type BarConfig = {
  title: string;
  callLabel: string;
  putLabel: string;
  callVal: (r: ByStrikeRow) => number;
  putValNeg: (r: ByStrikeRow) => number; // stored negative for left extension
  netSort: (r: ByStrikeRow) => number;
};

const BAR_CONFIG: Record<"GEX" | "DEX", BarConfig> = {
  GEX: {
    title: "GEX by Strike",
    callLabel: "Call GEX",
    putLabel: "Put GEX",
    callVal: (r) => r.call_gex ?? 0,
    putValNeg: (r) => -(r.put_gex ?? 0),
    netSort: (r) => r.net_gex ?? 0,
  },
  DEX: {
    title: "Delta Exposure (DEX) by Strike",
    callLabel: "Call DEX",
    putLabel: "Put DEX",
    callVal: (r) => r.call_dex ?? 0,
    putValNeg: (r) => r.put_dex ?? 0, // already negative in data
    netSort: (r) => (r.call_dex ?? 0) + (r.put_dex ?? 0),
  },
};

// ─── Line chart config (VANNA / CHARM) ───────────────────────────────────────
// Raw data: call_vex / put_vex are both negative; call_charm / put_charm both positive.
// Negate so displayed values match unusualwhales sign convention:
//   Vanna → positive peaks above zero; Charm → negative troughs below zero.
type LineConfig = {
  title: string;
  callLabel: string;
  putLabel: string;
  netLabel: string;
  callVal: (r: ByStrikeRow) => number;
  putVal: (r: ByStrikeRow) => number;
  netVal: (r: ByStrikeRow) => number;
};

const LINE_CONFIG: Record<"VANNA" | "CHARM", LineConfig> = {
  VANNA: {
    title: "Vanna Exposure by Strike",
    callLabel: "Call Vanna",
    putLabel: "Put Vanna",
    netLabel: "Net Vanna",
    callVal: (r) => -(r.call_vex ?? 0),
    putVal: (r) => -(r.put_vex ?? 0),
    netVal: (r) => -((r.call_vex ?? 0) + (r.put_vex ?? 0)),
  },
  CHARM: {
    title: "Charm Exposure by Strike",
    callLabel: "Call Charm",
    putLabel: "Put Charm",
    netLabel: "Net Charm",
    callVal: (r) => -(r.call_charm ?? 0),
    putVal: (r) => -(r.put_charm ?? 0),
    netVal: (r) => -((r.call_charm ?? 0) + (r.put_charm ?? 0)),
  },
};

type BarRow = {
  strike: number;
  callVal: number;
  putValNeg: number;
  netSort: number;
  isAtm: boolean;
};

type LineRow = {
  strike: number;
  callVal: number;
  putVal: number;
  netVal: number;
  isAtm: boolean;
};

export function ByStrikeSplitBars({
  rows,
  spot,
  gammaFlip,
  highlightedStrike = null,
  sortMode = "strike",
  metricFamily = "GEX",
}: Props) {
  const isLineChart = metricFamily === "VANNA" || metricFamily === "CHARM";

  const sortedBase = useMemo(
    () =>
      [...rows]
        .filter((r) => r.strike != null)
        .sort((a, b) => (a.strike ?? 0) - (b.strike ?? 0)),
    [rows]
  );

  const spotDists = useMemo(
    () => sortedBase.map((r) => (spot ? Math.abs((r.strike ?? 0) - spot) : Infinity)),
    [sortedBase, spot]
  );
  const minDist = useMemo(() => Math.min(...spotDists), [spotDists]);

  // ─── Bar data (GEX / DEX) ─────────────────────────────────────────────────
  const barRows = useMemo((): BarRow[] => {
    if (isLineChart) return [];
    const cfg = BAR_CONFIG[metricFamily as "GEX" | "DEX"];
    const withVals: BarRow[] = sortedBase.map((r, i) => ({
      strike: r.strike ?? 0,
      callVal: cfg.callVal(r),
      putValNeg: cfg.putValNeg(r),
      netSort: cfg.netSort(r),
      isAtm: spotDists[i] === minDist,
    }));
    if (sortMode === "abs") {
      return [...withVals].sort(
        (a, b) => Math.abs(b.netSort) - Math.abs(a.netSort) || a.strike - b.strike
      );
    }
    return withVals;
  }, [isLineChart, metricFamily, sortedBase, spotDists, minDist, sortMode]);

  // ─── Line data (VANNA / CHARM) — always strike-sorted ────────────────────
  const lineRows = useMemo((): LineRow[] => {
    if (!isLineChart) return [];
    const cfg = LINE_CONFIG[metricFamily as "VANNA" | "CHARM"];
    return sortedBase.map((r, i) => ({
      strike: r.strike ?? 0,
      callVal: cfg.callVal(r),
      putVal: cfg.putVal(r),
      netVal: cfg.netVal(r),
      isAtm: spotDists[i] === minDist,
    }));
  }, [isLineChart, metricFamily, sortedBase, spotDists, minDist]);

  if (!sortedBase.length) {
    const title = isLineChart
      ? LINE_CONFIG[metricFamily as "VANNA" | "CHARM"].title
      : BAR_CONFIG[metricFamily as "GEX" | "DEX"].title;
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">{title}</h2>
        <p className="text-sm text-zinc-500">No strike data available.</p>
      </div>
    );
  }

  // ─── LINE CHART (VANNA / CHARM) ───────────────────────────────────────────
  if (isLineChart) {
    const lcfg = LINE_CONFIG[metricFamily as "VANNA" | "CHARM"];
    const metricName = metricFamily === "VANNA" ? "Vanna" : "Charm";

    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-3 text-sm font-semibold text-zinc-200">{lcfg.title}</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* Left: Net exposure */}
          <div>
            <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">
              Net {metricName} Exposure
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={lineRows} margin={{ top: 4, right: 12, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="strike"
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  axisLine={{ stroke: "#3f3f46" }}
                  tickLine={false}
                  tickFormatter={(v: number) => Number(v).toFixed(0)}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={fmt}
                  width={52}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={(label) => `Strike: ${Number(label).toFixed(2)}`}
                  formatter={(value: number) => [fmt(value), lcfg.netLabel]}
                />
                <ReferenceLine y={0} stroke="#3f3f46" strokeWidth={1.5} />
                {spot && (
                  <ReferenceLine
                    x={spot}
                    stroke="#fbbf24"
                    strokeDasharray="4 2"
                    strokeWidth={1.5}
                    label={{
                      value: `Price: ${spot.toFixed(2)}`,
                      fill: "#fbbf24",
                      fontSize: 10,
                      position: "insideTopRight",
                    }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="netVal"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#a855f7", stroke: "#09090b", strokeWidth: 2 }}
                  name={lcfg.netLabel}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Right: Call / Put split */}
          <div>
            <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">
              {metricName} Exposure — Call / Put
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={lineRows} margin={{ top: 4, right: 12, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="strike"
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  axisLine={{ stroke: "#3f3f46" }}
                  tickLine={false}
                  tickFormatter={(v: number) => Number(v).toFixed(0)}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={fmt}
                  width={52}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={(label) => `Strike: ${Number(label).toFixed(2)}`}
                  formatter={(value: number, name: string) => {
                    if (name === lcfg.callLabel) return [fmt(value), lcfg.callLabel];
                    if (name === lcfg.putLabel) return [fmt(value), lcfg.putLabel];
                    return [fmt(value), name];
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
                  iconType="line"
                />
                <ReferenceLine y={0} stroke="#3f3f46" strokeWidth={1.5} />
                {spot && (
                  <ReferenceLine
                    x={spot}
                    stroke="#fbbf24"
                    strokeDasharray="4 2"
                    strokeWidth={1.5}
                    label={{
                      value: `Price: ${spot.toFixed(2)}`,
                      fill: "#fbbf24",
                      fontSize: 10,
                      position: "insideTopRight",
                    }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="callVal"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#10b981", stroke: "#09090b", strokeWidth: 2 }}
                  name={lcfg.callLabel}
                />
                <Line
                  type="monotone"
                  dataKey="putVal"
                  stroke="#f43f5e"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#f43f5e", stroke: "#09090b", strokeWidth: 2 }}
                  name={lcfg.putLabel}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  }

  // ─── BAR CHART (GEX / DEX) ────────────────────────────────────────────────
  const bcfg = BAR_CONFIG[metricFamily as "GEX" | "DEX"];
  const maxAbs = Math.max(
    ...barRows.map((d) => Math.max(Math.abs(d.callVal), Math.abs(d.putValNeg)))
  );

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">{bcfg.title}</h2>
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm bg-emerald-600" /> {bcfg.callLabel}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm bg-rose-600" /> {bcfg.putLabel}
          </span>
          {gammaFlip && <span className="text-violet-400">Γ Flip: {gammaFlip.toFixed(2)}</span>}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={barRows.length * 24 + 48}>
        <BarChart
          layout="vertical"
          data={barRows}
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
              const row = barRows.find((d) => d.strike === payload.value);
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
                  {Number(payload.value).toFixed(0)}
                </text>
              );
            }}
            width={64}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(label) => `Strike: ${Number(label).toFixed(2)}`}
            formatter={(value: number, name: string) => {
              if (name === "callVal") return [fmt(value), bcfg.callLabel];
              if (name === "putValNeg") return [fmt(-value), bcfg.putLabel];
              return [fmt(value), name];
            }}
          />

          <ReferenceLine x={0} stroke="#3f3f46" strokeWidth={1} />
          {gammaFlip && (
            <ReferenceLine
              y={gammaFlip}
              stroke="#7c3aed"
              strokeDasharray="4 2"
              strokeWidth={1.5}
            />
          )}

          <Bar dataKey="callVal" name="callVal" radius={[0, 2, 2, 0]}>
            {barRows.map((entry, idx) => (
              <Cell
                key={idx}
                fill={
                  highlightedStrike === entry.strike
                    ? "#22c55e"
                    : entry.isAtm
                    ? "#059669"
                    : "#16a34a"
                }
                opacity={highlightedStrike === entry.strike ? 1 : entry.isAtm ? 1 : 0.75}
              />
            ))}
          </Bar>

          <Bar dataKey="putValNeg" name="putValNeg" radius={[2, 0, 0, 2]}>
            {barRows.map((entry, idx) => (
              <Cell
                key={idx}
                fill={
                  highlightedStrike === entry.strike
                    ? "#fb7185"
                    : entry.isAtm
                    ? "#dc2626"
                    : "#e11d48"
                }
                opacity={highlightedStrike === entry.strike ? 1 : entry.isAtm ? 1 : 0.75}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
