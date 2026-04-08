"use client";

import React, { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type LegacyRow = {
  strike?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_oi?: number;
  put_oi?: number;
  call_dex?: number;
  put_dex?: number;
  call_avg_iv?: number | null;
  put_avg_iv?: number | null;
};

type SnapshotRow = {
  timestamp: string;
  totalGex: number | null;
  spotPrice: number | null;
};

type ProfileMode = "nodes" | "net" | "liquidity";
type ViewMode = "profile" | "cumulative" | "dex" | "skew" | "history";

type Props = {
  rows: LegacyRow[];
  spot: number | null;
  snapshots: SnapshotRow[];
  isLoading?: boolean;
};

function fmt(v: number | null | undefined, digits = 0): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "-";
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function LegacyProfileViewsPanel({ rows, spot, snapshots, isLoading = false }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("profile");
  const [profileMode, setProfileMode] = useState<ProfileMode>("nodes");
  const [zoomPct, setZoomPct] = useState(5);

  const orderedRows = useMemo(
    () =>
      [...rows]
        .filter((row) => typeof row.strike === "number")
        .sort((a, b) => (a.strike ?? 0) - (b.strike ?? 0)),
    [rows]
  );

  const zoomedRows = useMemo(() => {
    if (orderedRows.length === 0) return [];
    if (typeof spot !== "number" || !Number.isFinite(spot) || spot <= 0) return orderedRows;
    const range = spot * (zoomPct / 100);
    return orderedRows.filter((row) => {
      const strike = row.strike ?? 0;
      return strike >= spot - range && strike <= spot + range;
    });
  }, [orderedRows, spot, zoomPct]);

  const cumulativeRows = useMemo(() => {
    let cumulative = 0;
    return orderedRows.map((row) => {
      cumulative += row.net_gex ?? 0;
      return {
        strike: row.strike ?? 0,
        cumulative,
      };
    });
  }, [orderedRows]);

  const dexRows = useMemo(
    () =>
      zoomedRows.map((row) => ({
        strike: row.strike ?? 0,
        netDex: (row.call_dex ?? 0) + (row.put_dex ?? 0),
      })),
    [zoomedRows]
  );

  const skewRows = useMemo(
    () =>
      zoomedRows
        .filter((row) => row.call_avg_iv != null || row.put_avg_iv != null)
        .map((row) => ({
          strike: row.strike ?? 0,
          callIv: row.call_avg_iv ?? null,
          putIv: row.put_avg_iv ?? null,
          skew: (row.put_avg_iv ?? 0) - (row.call_avg_iv ?? 0),
        })),
    [zoomedRows]
  );

  const historyRows = useMemo(
    () =>
      [...snapshots]
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .map((row) => ({
          time: new Date(row.timestamp).toLocaleTimeString(),
          totalGex: row.totalGex ?? 0,
          spot: row.spotPrice ?? null,
        })),
    [snapshots]
  );

  const noData = orderedRows.length === 0;

  return (
    <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-widest text-zinc-500">Legacy Views</span>
        {(["profile", "cumulative", "dex", "skew", "history"] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setViewMode(mode)}
            className={`rounded px-2 py-1 text-xs font-medium uppercase tracking-wide ${
              viewMode === mode ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"
            }`}
          >
            {mode}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-zinc-500">Zoom</span>
          <input
            type="range"
            min={2}
            max={15}
            value={zoomPct}
            onChange={(e) => setZoomPct(Number(e.target.value))}
            className="h-1.5 w-28 accent-emerald-500"
          />
          <span className="w-8 text-right text-xs text-zinc-300">{zoomPct}%</span>
        </div>
      </div>

      {viewMode === "profile" && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {(["nodes", "net", "liquidity"] as ProfileMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setProfileMode(mode)}
                className={`rounded px-2 py-1 text-xs font-medium uppercase tracking-wide ${
                  profileMode === mode ? "bg-indigo-700 text-white" : "bg-zinc-800 text-zinc-300"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>

          {isLoading ? (
            <p className="text-sm text-zinc-500">Loading profile view...</p>
          ) : noData ? (
            <p className="text-sm text-zinc-500">No strike rows available.</p>
          ) : (
            <div className="h-[420px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                {profileMode === "nodes" ? (
                  <BarChart data={zoomedRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                      formatter={(value) => fmt(Number(value), 0)}
                    />
                    <Bar dataKey="call_gex" fill="#10b981" name="Call GEX" />
                    <Bar dataKey="put_gex" fill="#f43f5e" name="Put GEX" />
                  </BarChart>
                ) : profileMode === "net" ? (
                  <BarChart data={zoomedRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                      formatter={(value) => fmt(Number(value), 0)}
                    />
                    <Bar dataKey="net_gex" name="Net GEX">
                      {zoomedRows.map((row, idx) => (
                        <Cell key={`net-${idx}`} fill={(row.net_gex ?? 0) >= 0 ? "#10b981" : "#f43f5e"} />
                      ))}
                    </Bar>
                  </BarChart>
                ) : (
                  <BarChart data={zoomedRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                      formatter={(value) => fmt(Number(value), 0)}
                    />
                    <Bar dataKey="call_oi" fill="#10b981" name="Call OI" />
                    <Bar dataKey="put_oi" fill="#f43f5e" name="Put OI" />
                  </BarChart>
                )}
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {viewMode === "cumulative" && (
        <div className="h-[380px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={cumulativeRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
              <Tooltip
                contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                formatter={(value) => fmt(Number(value), 0)}
              />
              <Line type="monotone" dataKey="cumulative" stroke="#22d3ee" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {viewMode === "dex" && (
        <div className="h-[380px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dexRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
              <Tooltip
                contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                formatter={(value) => fmt(Number(value), 0)}
              />
              <Bar dataKey="netDex" name="Net DEX">
                {dexRows.map((row, idx) => (
                  <Cell key={`dex-${idx}`} fill={(row.netDex ?? 0) >= 0 ? "#10b981" : "#f43f5e"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {viewMode === "skew" && (
        <div>
          {skewRows.length === 0 ? (
            <p className="text-sm text-zinc-500">Skew view unavailable for current data source (no strike IV values).</p>
          ) : (
            <div className="h-[380px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={skewRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="strike" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                  <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 3)} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                    formatter={(value) => fmt(Number(value), 4)}
                  />
                  <Line type="monotone" dataKey="callIv" stroke="#10b981" strokeWidth={2} dot={false} name="Call IV" />
                  <Line type="monotone" dataKey="putIv" stroke="#f43f5e" strokeWidth={2} dot={false} name="Put IV" />
                  <Line type="monotone" dataKey="skew" stroke="#a78bfa" strokeWidth={2} dot={false} name="Skew" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {viewMode === "history" && (
        <div>
          {historyRows.length === 0 ? (
            <p className="text-sm text-zinc-500">No intraday snapshots available for history view.</p>
          ) : (
            <div className="h-[380px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="time" tick={{ fill: "#a1a1aa", fontSize: 10 }} minTickGap={22} />
                  <YAxis yAxisId="left" tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 0)} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => fmt(Number(v), 2)} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", color: "#e4e4e7" }}
                    formatter={(value) => fmt(Number(value), 2)}
                  />
                  <Line yAxisId="left" type="monotone" dataKey="totalGex" stroke="#22d3ee" strokeWidth={2} dot={false} name="Total GEX" />
                  <Line yAxisId="right" type="monotone" dataKey="spot" stroke="#facc15" strokeWidth={2} dot={false} name="Spot" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
