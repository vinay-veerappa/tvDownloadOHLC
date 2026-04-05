"use client";

import React, { useMemo } from "react";

type HeatmapCell = {
  strike: number;
  expiry: string;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  call_oi: number;
  put_oi: number;
  pcr: number | null;
};

type HeatmapData = {
  strikes: number[];
  expiries: string[];
  matrix: HeatmapCell[];
};

type Props = {
  data: HeatmapData | null;
  isLoading?: boolean;
  onCellClick?: (cell: HeatmapCell) => void;
};

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function getColor(netGex: number, minVal: number, maxVal: number): string {
  if (minVal === maxVal) return "bg-zinc-600";
  
  // Normalize to -1..1 range
  const normalized = (netGex - minVal) / (maxVal - minVal) * 2 - 1;
  
  if (normalized > 0) {
    // Positive (green)
    const intensity = Math.min(1, normalized);
    const bgOp = Math.round(200 + intensity * 55); // 200-255
    return `bg-green-${Math.round(intensity * 9 + 1)}`;
  } else {
    // Negative (red)
    const intensity = Math.abs(normalized);
    return `bg-red-${Math.round(intensity * 9 + 1)}`;
  }
}

// Simple color function using opacity instead of Tailwind classes
function getCellBgStyle(netGex: number, minVal: number, maxVal: number): React.CSSProperties {
  if (minVal === maxVal) {
    return { backgroundColor: "rgb(82, 82, 91)" }; // zinc-600
  }
  
  const normalized = (netGex - minVal) / (maxVal - minVal) * 2 - 1;
  
  if (normalized > 0) {
    // Positive (green)
    const intensity = Math.min(1, normalized);
    const opacity = 0.3 + intensity * 0.7;
    return { backgroundColor: `rgba(34, 197, 94, ${opacity})` };
  } else {
    // Negative (red)
    const intensity = Math.abs(normalized);
    const opacity = 0.3 + intensity * 0.7;
    return { backgroundColor: `rgba(239, 68, 68, ${opacity})` };
  }
}

export function MatrixHeatmap({ data, isLoading, onCellClick }: Props) {
  const { cellMap, minVal, maxVal, strikes, expiries } = useMemo(() => {
    if (!data || !data.matrix.length) {
      return { cellMap: new Map(), minVal: 0, maxVal: 0, strikes: [], expiries: [] };
    }

    const map = new Map<string, HeatmapCell>();
    for (const cell of data.matrix) {
      map.set(`${cell.strike}:${cell.expiry}`, cell);
    }

    const netGexValues = data.matrix.map((c) => c.net_gex);
    const min = Math.min(...netGexValues);
    const max = Math.max(...netGexValues);

    return {
      cellMap: map,
      minVal: min,
      maxVal: max,
      strikes: data.strikes,
      expiries: data.expiries,
    };
  }, [data]);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Strike × Expiry Heatmap</h2>
        <p className="text-sm animate-pulse text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!strikes.length || !expiries.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Strike × Expiry Heatmap</h2>
        <p className="text-sm text-zinc-500">No heatmap data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Strike × Expiry Heatmap (Net GEX)</h2>
        <div className="flex items-center gap-2 text-xs">
          <span className="flex items-center gap-1">
            <span className="h-2 w-4 rounded" style={{ backgroundColor: "rgba(34, 197, 94, 1)" }} />
            Positive
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-4 rounded" style={{ backgroundColor: "rgba(82, 82, 91, 1)" }} />
            Neutral
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-4 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 1)" }} />
            Negative
          </span>
        </div>
      </div>

      {/* Scrollable grid */}
      <div className="overflow-x-auto border border-zinc-800 rounded-lg">
        <table className="text-xs border-collapse">
          <thead>
            <tr className="bg-zinc-900/50 sticky top-0">
              <th className="border border-zinc-800 px-2 py-1 text-zinc-400 text-left font-medium w-16">
                Strike
              </th>
              {expiries.map((exp) => (
                <th
                  key={exp}
                  className="border border-zinc-800 px-2 py-1 text-zinc-400 text-center font-medium w-20"
                >
                  {exp}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strikes.map((strike) => (
              <tr key={strike} className="hover:bg-zinc-900/30">
                <td className="border border-zinc-800 px-2 py-1 font-mono text-zinc-300 sticky left-0 bg-zinc-950">
                  {strike.toFixed(0)}
                </td>
                {expiries.map((exp) => {
                  const cell = cellMap.get(`${strike}:${exp}`);
                  const netGex = cell?.net_gex ?? 0;
                  const bgStyle = getCellBgStyle(netGex, minVal, maxVal);
                  return (
                    <td
                      key={`${strike}:${exp}`}
                      className="border border-zinc-800 px-2 py-1 text-center font-mono text-zinc-100 cursor-help hover:ring-1 hover:ring-yellow-500"
                      style={bgStyle}
                      title={`Net GEX: ${fmt(netGex)}\nCall GEX: ${fmt(cell?.call_gex ?? 0)}\nPut GEX: ${fmt(cell?.put_gex ?? 0)}`}
                      onClick={() => {
                        if (cell) onCellClick?.(cell);
                      }}
                    >
                      {fmt(netGex)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <p className="text-xs text-zinc-500 pt-2">
        Cells show <strong>Net GEX</strong> by strike (rows) and expiry (columns).{" "}
        <strong>Green</strong> = positive (bullish), <strong>Red</strong> = negative (bearish).
        Hover for details.
      </p>
    </div>
  );
}
