"use client";

import React, { useMemo, useState } from "react";

type ByStrikeRow = {
  strike?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
};

type Props = {
  rows: ByStrikeRow[];
  spot: number | null;
  pinnedStrike?: number | null;
  onPinStrike?: (strike: number) => void;
};

function fmt(v: number, digits = 0): string {
  if (!Number.isFinite(v)) return "-";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function IntegratedViewPane({ rows, spot, pinnedStrike = null, onPinStrike }: Props) {
  const [hoverStrike, setHoverStrike] = useState<number | null>(null);

  const levels = useMemo(() => {
    return [...rows]
      .filter((r) => r.strike != null)
      .map((r) => ({
        strike: r.strike ?? 0,
        call_gex: r.call_gex ?? 0,
        put_gex: r.put_gex ?? 0,
        net_gex: r.net_gex ?? 0,
      }))
      .sort((a, b) => b.strike - a.strike)
      .slice(0, 30);
  }, [rows]);

  const maxAbs = useMemo(() => {
    if (!levels.length) return 1;
    return Math.max(
      ...levels.map((l) => Math.max(Math.abs(l.call_gex), Math.abs(l.put_gex), Math.abs(l.net_gex)))
    );
  }, [levels]);

  if (!levels.length) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Integrated View</h2>
        <p className="text-sm text-zinc-500">No strike rows available for integrated view.</p>
      </div>
    );
  }

  const activeStrike = pinnedStrike ?? hoverStrike;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Integrated View (Price + Exposure)</h2>
        <span className="text-xs text-zinc-500">
          Spot: <span className="font-mono text-cyan-300">{spot != null ? fmt(spot, 2) : "-"}</span>
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
          <p className="mb-2 text-xs uppercase tracking-wider text-zinc-500">Price Ladder</p>
          <div className="space-y-1">
            {levels.map((level) => {
              const isSpotBand = spot != null && Math.abs(level.strike - spot) <= 0.5;
              const isActive = activeStrike === level.strike;
              return (
                <button
                  key={`ladder-${level.strike}`}
                  onMouseEnter={() => setHoverStrike(level.strike)}
                  onMouseLeave={() => setHoverStrike(null)}
                  onClick={() => onPinStrike?.(level.strike)}
                  className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                    isActive ? "bg-emerald-900/40" : isSpotBand ? "bg-cyan-900/30" : "hover:bg-zinc-800"
                  }`}
                >
                  <span className="font-mono text-zinc-100">{fmt(level.strike, 2)}</span>
                  <span className="ml-2 text-zinc-500">Net {fmt(level.net_gex, 0)}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
          <p className="mb-2 text-xs uppercase tracking-wider text-zinc-500">Exposure Pane</p>
          <div className="space-y-1">
            {levels.map((level) => {
              const callPct = Math.min(100, Math.max(2, (Math.abs(level.call_gex) / maxAbs) * 100));
              const putPct = Math.min(100, Math.max(2, (Math.abs(level.put_gex) / maxAbs) * 100));
              const isActive = activeStrike === level.strike;
              return (
                <button
                  key={`exp-${level.strike}`}
                  onMouseEnter={() => setHoverStrike(level.strike)}
                  onMouseLeave={() => setHoverStrike(null)}
                  onClick={() => onPinStrike?.(level.strike)}
                  className={`w-full rounded px-2 py-1 text-left transition-colors ${isActive ? "bg-emerald-900/40" : "hover:bg-zinc-800"}`}
                >
                  <div className="mb-1 flex items-center justify-between text-[11px] text-zinc-400">
                    <span className="font-mono">{fmt(level.strike, 2)}</span>
                    <span className={level.net_gex >= 0 ? "text-emerald-300" : "text-rose-300"}>{fmt(level.net_gex, 0)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="h-2 rounded bg-rose-500/80" style={{ width: `${putPct}%` }} />
                    <div className="h-2 rounded bg-emerald-500/80" style={{ width: `${callPct}%` }} />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <p className="text-xs text-zinc-500">
        Hover links both panes by strike. Click a strike to pin it across Integrated and By-Strike views.
      </p>
    </div>
  );
}
