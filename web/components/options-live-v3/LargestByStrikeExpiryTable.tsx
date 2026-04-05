"use client";

import React, { useMemo, useState } from "react";

type HeatmapCell = {
  strike: number;
  expiry: string;
  call_gex: number;
  put_gex: number;
  net_gex: number;
};

type SortMode = "abs_net" | "call_gex" | "put_gex";

type Props = {
  rows: HeatmapCell[];
  spot: number | null;
  limit: number;
  sortMode: SortMode;
  onSortModeChange: (mode: SortMode) => void;
  onLimitChange: (limit: number) => void;
  onSelectRow?: (row: HeatmapCell) => void;
};

function fmt(v: number, digits = 0): string {
  if (!Number.isFinite(v)) return "-";
  return v.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function distLabel(strike: number, spot: number | null): string {
  if (spot == null) return "-";
  const dist = strike - spot;
  const pct = spot === 0 ? 0 : (dist / spot) * 100;
  return `${dist >= 0 ? "+" : ""}${fmt(dist, 2)} (${pct >= 0 ? "+" : ""}${fmt(pct, 2)}%)`;
}

export function LargestByStrikeExpiryTable({
  rows,
  spot,
  limit,
  sortMode,
  onSortModeChange,
  onLimitChange,
  onSelectRow,
}: Props) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const ranked = useMemo(() => {
    const withAbs = rows.map((row) => ({ ...row, abs_net_gex: Math.abs(row.net_gex) }));
    if (sortMode === "call_gex") {
      withAbs.sort((a, b) => b.call_gex - a.call_gex);
    } else if (sortMode === "put_gex") {
      withAbs.sort((a, b) => b.put_gex - a.put_gex);
    } else {
      withAbs.sort((a, b) => b.abs_net_gex - a.abs_net_gex);
    }
    return withAbs.slice(0, limit);
  }, [rows, sortMode, limit]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-200">Largest GEX by Strike + Expiry</h2>
        <div className="flex items-center gap-2 text-xs">
          <select
            value={sortMode}
            onChange={(e) => onSortModeChange(e.target.value as SortMode)}
            className="h-7 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          >
            <option value="abs_net">Sort: Abs Net</option>
            <option value="call_gex">Sort: Call GEX</option>
            <option value="put_gex">Sort: Put GEX</option>
          </select>
          <select
            value={String(limit)}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="h-7 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          >
            <option value="10">Rows: 10</option>
            <option value="25">Rows: 25</option>
            <option value="50">Rows: 50</option>
            <option value="100">Rows: 100</option>
          </select>
        </div>
      </div>

      {!ranked.length ? (
        <p className="text-sm text-zinc-500">No strike+expiry concentration rows available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400">
                <th className="py-2 text-left">Rank</th>
                <th className="py-2 text-left">Expiry</th>
                <th className="py-2 text-left">Strike</th>
                <th className="py-2 text-right">Call GEX</th>
                <th className="py-2 text-right">Put GEX</th>
                <th className="py-2 text-right">Net GEX</th>
                <th className="py-2 text-right">Abs Net</th>
                <th className="py-2 text-right">Dist Spot</th>
                <th className="py-2 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((row, idx) => {
                const key = `${row.expiry}:${row.strike}`;
                const selected = selectedKey === key;
                return (
                  <tr
                    key={key}
                    className={`border-b border-zinc-900 ${selected ? "bg-emerald-950/20" : "hover:bg-zinc-900/30"}`}
                  >
                    <td className="py-2 text-zinc-400">{idx + 1}</td>
                    <td className="py-2 text-zinc-200">{row.expiry}</td>
                    <td className="py-2 font-mono text-zinc-100">{fmt(row.strike, 2)}</td>
                    <td className="py-2 text-right text-emerald-300">{fmt(row.call_gex, 0)}</td>
                    <td className="py-2 text-right text-rose-300">{fmt(row.put_gex, 0)}</td>
                    <td className={`py-2 text-right ${row.net_gex >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {fmt(row.net_gex, 0)}
                    </td>
                    <td className="py-2 text-right text-zinc-100">{fmt(Math.abs(row.net_gex), 0)}</td>
                    <td className="py-2 text-right text-zinc-300">{distLabel(row.strike, spot)}</td>
                    <td className="py-2">
                      <button
                        onClick={() => {
                          setSelectedKey(key);
                          onSelectRow?.(row);
                        }}
                        className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200 hover:bg-zinc-800"
                      >
                        Highlight
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
