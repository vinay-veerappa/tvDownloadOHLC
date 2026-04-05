"use client";

import React, { useMemo } from "react";

type FlowRow = {
  strike?: number;
  expiry?: string | null;
  call_put?: string | null;
  volume?: number | null;
  open_interest?: number | null;
  gamma?: number | null;
  iv?: number | null;
  score?: number | null;
};

type RecentFlowData = {
  flowRegime: string | null;
  dataSource: string | null;
  rows: FlowRow[];
};

type Props = {
  data: RecentFlowData | null;
  isLoading?: boolean;
};

function fmtScore(score: number | null | undefined): { label: string; cls: string } {
  if (score == null) return { label: "—", cls: "text-zinc-500" };
  if (score >= 7) return { label: score.toFixed(1), cls: "text-emerald-400" };
  if (score >= 4) return { label: score.toFixed(1), cls: "text-amber-400" };
  return { label: score.toFixed(1), cls: "text-rose-400" };
}

function cpBadge(cp: string | null | undefined): React.ReactElement {
  if (cp?.toLowerCase().startsWith("c")) {
    return (
      <span className="rounded px-1.5 py-0.5 text-xs font-medium bg-emerald-900/50 text-emerald-400">
        C
      </span>
    );
  }
  if (cp?.toLowerCase().startsWith("p")) {
    return (
      <span className="rounded px-1.5 py-0.5 text-xs font-medium bg-rose-900/50 text-rose-400">
        P
      </span>
    );
  }
  return <span className="text-zinc-500 text-xs">—</span>;
}

function fmt(v: number | null | undefined, d = 0): string {
  if (v == null) return "—";
  if (d === 0) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return v.toFixed(d);
}

function regimeColor(regime: string | null): string {
  if (!regime) return "text-zinc-400";
  const r = regime.toLowerCase();
  if (r.includes("call") || r.includes("bullish")) return "text-emerald-400";
  if (r.includes("put") || r.includes("bearish")) return "text-rose-400";
  if (r.includes("mixed") || r.includes("neutral")) return "text-amber-400";
  return "text-zinc-400";
}

export function RecentFlowTape({ data, isLoading }: Props) {
  const rows = useMemo(() => data?.rows ?? [], [data]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Recent Flow Tape</h2>
        <div className="flex items-center gap-3 text-xs">
          {data?.flowRegime && (
            <span className={`font-medium ${regimeColor(data.flowRegime)}`}>
              Regime: {data.flowRegime}
            </span>
          )}
          {data?.dataSource && (
            <span className="text-zinc-500">{data.dataSource}</span>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-zinc-800 animate-pulse" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="text-sm text-zinc-500">No flow data available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-xs">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="pb-1.5 pl-2 text-left font-medium text-zinc-400">Strike</th>
                <th className="pb-1.5 text-left font-medium text-zinc-400">Expiry</th>
                <th className="pb-1.5 text-center font-medium text-zinc-400">C/P</th>
                <th className="pb-1.5 text-right font-medium text-zinc-400">Volume</th>
                <th className="pb-1.5 text-right font-medium text-zinc-400">OI</th>
                <th className="pb-1.5 text-right font-medium text-zinc-400 hidden sm:table-cell">
                  Gamma
                </th>
                <th className="pb-1.5 text-right font-medium text-zinc-400 hidden sm:table-cell">
                  IV
                </th>
                <th className="pb-1.5 pr-2 text-right font-medium text-zinc-400">Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const { label: scoreLabel, cls: scoreCls } = fmtScore(row.score);
                return (
                  <tr
                    key={idx}
                    className={`border-b border-zinc-900 transition-colors hover:bg-zinc-900/50 ${
                      idx === 0 ? "bg-zinc-900/30" : ""
                    }`}
                  >
                    <td className="py-1.5 pl-2 font-mono text-zinc-200">
                      {fmt(row.strike, 2)}
                    </td>
                    <td className="py-1.5 text-zinc-400">
                      {row.expiry ?? "—"}
                    </td>
                    <td className="py-1.5 text-center">
                      {cpBadge(row.call_put)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-zinc-300">
                      {fmt(row.volume)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-zinc-400">
                      {fmt(row.open_interest)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-zinc-400 hidden sm:table-cell">
                      {row.gamma != null ? row.gamma.toFixed(4) : "—"}
                    </td>
                    <td className="py-1.5 text-right font-mono text-zinc-400 hidden sm:table-cell">
                      {row.iv != null ? (row.iv * 100).toFixed(1) + "%" : "—"}
                    </td>
                    <td className={`py-1.5 pr-2 text-right font-mono font-semibold ${scoreCls}`}>
                      {scoreLabel}
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
