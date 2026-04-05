"use client";

import React, { useMemo } from "react";
import { Treemap, Tooltip, ResponsiveContainer } from "recharts";

type TreemapNode = {
  expiry: string;
  net_gex: number;
  call_gex: number;
  put_gex: number;
  total_oi: number;
};

type Props = {
  data: TreemapNode[] | null;
  isLoading?: boolean;
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function getNodeColor(netGex: number, minVal: number, maxVal: number): string {
  if (minVal === maxVal) return "#5A5A6A";

  const normalized = (netGex - minVal) / (maxVal - minVal) * 2 - 1;

  if (normalized > 0) {
    // Positive (green)
    const intensity = Math.min(1, normalized);
    return `rgb(${Math.round(34 + (255 - 34) * intensity)}, ${Math.round(197 + (255 - 197) * intensity)}, ${Math.round(94 + (255 - 94) * intensity)})`;
  } else {
    // Negative (red)
    const intensity = Math.abs(normalized);
    return `rgb(${Math.round(239 + (255 - 239) * intensity)}, ${Math.round(68 + (255 - 68) * intensity)}, ${Math.round(68 + (255 - 68) * intensity)})`;
  }
}

interface RecChartsData {
  name: string;
  value: number;
  expiry: string;
  net_gex: number;
  call_gex: number;
  put_gex: number;
  total_oi: number;
  fill: string;
  [key: string]: any;
}

export function TreemapHeatmap({ data, isLoading }: Props) {
  const chartData: RecChartsData[] = useMemo(() => {
    if (!data || !data.length) return [];

    const netGexValues = data.map((d) => d.net_gex);
    const minVal = Math.min(...netGexValues);
    const maxVal = Math.max(...netGexValues);

    return data.map((d) => ({
      name: d.expiry,
      value: Math.max(1, d.total_oi / 1_000_000), // Scale OI for visualization
      expiry: d.expiry,
      net_gex: d.net_gex,
      call_gex: d.call_gex,
      put_gex: d.put_gex,
      total_oi: d.total_oi,
      fill: getNodeColor(d.net_gex, minVal, maxVal),
    }));
  }, [data]);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Expiry GEX Treemap</h2>
        <p className="text-sm animate-pulse text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!chartData.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Expiry GEX Treemap</h2>
        <p className="text-sm text-zinc-500">No treemap data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <h2 className="text-sm font-semibold text-zinc-200">Expiry GEX Treemap</h2>
      <p className="text-xs text-zinc-500">
        Rectangle size = Open Interest • Color = Net GEX (green = positive, red = negative)
      </p>

      <ResponsiveContainer width="100%" height={320}>
        <Treemap
          data={chartData}
          dataKey="value"
          nameKey="name"
          stroke="#27272a"
          fill="#2a2a3a"
          isAnimationActive={false}
        >
          <Tooltip
            contentStyle={{
              backgroundColor: "#09090b",
              border: "1px solid #27272a",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#e4e4e7",
            }}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            formatter={(value: number, name: string, props) => {
              const node = props.payload as RecChartsData;
              if (name === "value") {
                return [
                  `OI: ${fmt(node.total_oi)}`,
                  "Total OI",
                ];
              }
              return [value, name];
            }}
            labelFormatter={(label: string) => `Expiry: ${label}`}
          />
        </Treemap>
      </ResponsiveContainer>

      {/* Detail table */}
      <div className="mt-3 text-xs">
        <div className="space-y-1">
          {chartData.map((node) => (
            <div
              key={node.name}
              className="flex items-center gap-2 rounded px-2 py-1"
              style={{ backgroundColor: node.fill + "22" }}
            >
              <div
                className="h-3 w-3 rounded"
                style={{ backgroundColor: node.fill }}
              />
              <span className="font-mono text-zinc-300 flex-1">{node.expiry}</span>
              <span className="text-zinc-400">OI: {fmt(node.total_oi)}</span>
              <span className={node.net_gex >= 0 ? "text-green-400" : "text-red-400"}>
                {node.net_gex >= 0 ? "+" : ""}{fmt(node.net_gex)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
