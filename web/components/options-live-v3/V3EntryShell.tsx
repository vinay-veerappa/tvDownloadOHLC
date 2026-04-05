"use client";

import React, { useEffect, useMemo, useState } from "react";
import type { V3Envelope } from "@/lib/options-live-v3/contracts/types";
import { StatCard } from "@/components/options-live-v3/StatCard";
import { SimpleTable } from "@/components/options-live-v3/SimpleTable";
import { GlobalControlBar, type GexTabId, type MetricFamily } from "@/components/options-live-v3/GlobalControlBar";
import { LiveLevelsLadder } from "@/components/options-live-v3/LiveLevelsLadder";
import { ByStrikeSplitBars } from "@/components/options-live-v3/ByStrikeSplitBars";
import { SpotGammaPanel } from "@/components/options-live-v3/SpotGammaPanel";
import { SqueezeScreenerCard } from "@/components/options-live-v3/SqueezeScreenerCard";
import { RecentFlowTape } from "@/components/options-live-v3/RecentFlowTape";
import { DiscordPublishDrawer } from "@/components/options-live-v3/DiscordPublishDrawer";
import { MatrixHeatmap } from "@/components/options-live-v3/MatrixHeatmap";
import { TreemapHeatmap } from "@/components/options-live-v3/TreemapHeatmap";
import { ByExpiryAggregationChart } from "@/components/options-live-v3/ByExpiryAggregationChart";

type SummaryData = {
  runLabel: string | null;
  asOf: string | null;
  spot: number | null;
  gex: {
    total: number | null;
    regime: string | null;
    regimeLabel: string | null;
    directionalBias: string | null;
  };
  keyLevels: {
    gammaFlip: number | null;
    callWall: number | null;
    putWall: number | null;
    gammaMagnet: number | null;
    pinStrike: number | null;
  };
};

type LevelsData = {
  levels: {
    spot: number | null;
    gammaFlip: number | null;
    callWall: number | null;
    putWall: number | null;
    gammaMagnet: number | null;
    pinStrike: number | null;
  };
  notes: {
    coach: string[];
    tactical: string[];
  };
};

type ByStrikeRow = {
  strike?: number;
  call_gex?: number;
  put_gex?: number;
  net_gex?: number;
  call_oi?: number;
  put_oi?: number;
};

type ByStrikeData = {
  filters: {
    strikes: number;
    expiryScope: string;
    metricFamily: string;
  };
  spot: number | null;
  rows: ByStrikeRow[];
};

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
  call_avg_iv?: number | null;
  put_avg_iv?: number | null;
};

type ByExpiryData = {
  dataSource?: string;
  rows: ByExpiryRow[];
};

type NarrativeData = {
  intradayDelta: {
    session: number | null;
    sessionPct: number | null;
    recent: number | null;
    snapshotCount: number | null;
  };
  signals: Array<{
    type: string;
    severity: "WEAK" | "MODERATE" | "STRONG";
    message: string;
    level: number | null;
    distancePct: number | null;
  }>;
  screener: {
    setup: string;
    probabilityScore: number;
    confidence: "POSSIBLE" | "LIKELY" | "IMMINENT";
    factors: Array<{ name: string; score: number }>;
  };
};

type SummaryResponse = V3Envelope<SummaryData>;
type LevelsResponse = V3Envelope<LevelsData>;
type ByStrikeResponse = V3Envelope<ByStrikeData>;
type ByExpiryResponse = V3Envelope<ByExpiryData>;
type NarrativeResponse = V3Envelope<NarrativeData>;

type RecentFlowRow = {
  strike?: number;
  expiry?: string;
  call_put?: string;
  volume?: number;
  open_interest?: number;
  gamma?: number;
  iv?: number;
  score?: number;
};
type RecentFlowData = { dataSource?: string; flowRegime?: string; rows: RecentFlowRow[] };
type RecentFlowResponse = V3Envelope<RecentFlowData>;

type SpotGammaRow = {
  strike: number;
  net_gex: number;
  call_gex: number;
  put_gex: number;
  cumulative_gex: number;
};
type SpotGammaData = {
  spot: number | null;
  current: { net_gex: number | null; call_gex: number | null; put_gex: number | null; cumulative_gex: number | null; atm_strike: number | null } | null;
  series: SpotGammaRow[];
};
type SpotGammaResponse = V3Envelope<SpotGammaData>;

type LargestRow = {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  abs_net_gex: number;
  call_oi: number;
  put_oi: number;
};
type LargestData = { cacheDate: string | null; filters: { limit: number; sort: string }; rows: LargestRow[] };
type LargestResponse = V3Envelope<LargestData>;

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
  treemap: Array<{ expiry: string; net_gex: number; call_gex: number; put_gex: number; total_oi: number }>;
};
type HeatmapResponse = V3Envelope<HeatmapData>;

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "-";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function toneByNumber(v: number | null | undefined): "neutral" | "positive" | "negative" {
  if (typeof v !== "number" || Number.isNaN(v)) return "neutral";
  if (v > 0) return "positive";
  if (v < 0) return "negative";
  return "neutral";
}

async function fetchEnvelope<T>(url: string): Promise<V3Envelope<T>> {
  const res = await fetch(url);
  return (await res.json()) as V3Envelope<T>;
}

export function V3EntryShell() {
  const [symbol, setSymbol] = useState("SPY");
  const [activeTab, setActiveTab] = useState<GexTabId>("daily-gex");
  const [strikeCount, setStrikeCount] = useState(20);
  const [expiryScope, setExpiryScope] = useState("all");
  const [metricFamily, setMetricFamily] = useState<MetricFamily>("GEX");
  const [publishOpen, setPublishOpen] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [levels, setLevels] = useState<LevelsResponse | null>(null);
  const [byStrike, setByStrike] = useState<ByStrikeResponse | null>(null);
  const [byExpiry, setByExpiry] = useState<ByExpiryResponse | null>(null);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [recentFlow, setRecentFlow] = useState<RecentFlowResponse | null>(null);
  const [spotGamma, setSpotGamma] = useState<SpotGammaResponse | null>(null);
  const [largest, setLargest] = useState<LargestResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const encoded = encodeURIComponent(symbol);
        const strikes = strikeCount > 0 ? strikeCount : 60;
        const [s, l, bs, be, n, rf, sg, lg, hm] = await Promise.all([
          fetchEnvelope<SummaryData>(`/api/options-live/v3/summary?symbol=${encoded}`),
          fetchEnvelope<LevelsData>(`/api/options-live/v3/levels?symbol=${encoded}`),
          fetchEnvelope<ByStrikeData>(`/api/options-live/v3/by-strike?symbol=${encoded}&strikes=${strikes}&expiryScope=${expiryScope}&metricFamily=${metricFamily.toLowerCase()}`),
          fetchEnvelope<ByExpiryData>(`/api/options-live/v3/by-expiry?symbol=${encoded}&strikes=${strikes}&metricFamily=${metricFamily.toLowerCase()}`),
          fetchEnvelope<NarrativeData>(`/api/options-live/v3/narrative?symbol=${encoded}`),
          fetchEnvelope<RecentFlowData>(`/api/options-live/v3/recent-flow?symbol=${encoded}&limit=20`),
          fetchEnvelope<SpotGammaData>(`/api/options-live/v3/spot-gamma?symbol=${encoded}&smooth=1`),
          fetchEnvelope<LargestData>(`/api/options-live/v3/largest?symbol=${encoded}&limit=15&sort=abs_net`),
          fetchEnvelope<HeatmapData>(`/api/options-live/v3/heatmap?symbol=${encoded}&strikes=${strikes}&metric=net_gex`),
        ]);

        if (!alive) return;
        setSummary(s);
        setLevels(l);
        setByStrike(bs);
        setByExpiry(be);
        setNarrative(n);
        setRecentFlow(rf);
        setSpotGamma(sg);
        setLargest(lg);
        setHeatmap(hm);
      } catch (error) {
        if (alive) {
          setLoadError(String(error));
        }
      } finally {
        if (alive) setIsLoading(false);
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, [symbol, strikeCount, expiryScope, metricFamily]);

  const strikeRows = useMemo(() => {
    const rows = byStrike?.data?.rows ?? [];
    return rows.slice(0, 12).map((row) => [
      fmtNum(row.strike, 2),
      fmtNum(row.call_gex, 0),
      fmtNum(row.put_gex, 0),
      fmtNum(row.net_gex, 0),
      fmtNum(row.call_oi, 0),
      fmtNum(row.put_oi, 0),
    ]);
  }, [byStrike]);

  const expiryRows = useMemo(() => {
    const rows = byExpiry?.data?.rows ?? [];
    return rows.slice(0, 12).map((row) => [
      row.expiry ?? "-",
      String(row.dte ?? "-"),
      fmtNum(row.call_gex, 0),
      fmtNum(row.put_gex, 0),
      fmtNum(row.net_gex, 0),
      fmtNum(row.call_oi, 0),
      fmtNum(row.put_oi, 0),
    ]);
  }, [byExpiry]);

  const recentFlowRows = useMemo(() => {
    const rows = recentFlow?.data?.rows ?? [];
    return rows.slice(0, 10).map((row) => [
      fmtNum(row.strike, 2),
      row.expiry ?? "-",
      row.call_put ?? "-",
      fmtNum(row.volume, 0),
      fmtNum(row.open_interest, 0),
      fmtNum(row.gamma, 4),
      fmtNum(row.iv, 4),
      fmtNum(row.score, 2),
    ]);
  }, [recentFlow]);

  const spotGammaTopRows = useMemo(() => {
    const rows = spotGamma?.data?.series ?? [];
    // Pick 10 rows spread around ATM
    const atm = spotGamma?.data?.current?.atm_strike ?? null;
    const sorted = atm !== null
      ? [...rows].sort((a, b) => Math.abs(a.strike - atm) - Math.abs(b.strike - atm)).slice(0, 10)
      : rows.slice(0, 10);
    return sorted.sort((a, b) => a.strike - b.strike).map((row) => [
      fmtNum(row.strike, 2),
      fmtNum(row.call_gex, 0),
      fmtNum(row.put_gex, 0),
      fmtNum(row.net_gex, 0),
      fmtNum(row.cumulative_gex, 0),
    ]);
  }, [spotGamma]);

  const largestRows = useMemo(() => {
    const rows = largest?.data?.rows ?? [];
    return rows.map((row) => [
      fmtNum(row.strike, 2),
      fmtNum(row.call_gex, 0),
      fmtNum(row.put_gex, 0),
      fmtNum(row.net_gex, 0),
      fmtNum(row.call_oi, 0),
      fmtNum(row.put_oi, 0),
    ]);
  }, [largest]);

  const allWarnings = useMemo(() => {
    return [
      ...(summary?.warnings ?? []),
      ...(levels?.warnings ?? []),
      ...(byStrike?.warnings ?? []),
      ...(byExpiry?.warnings ?? []),
      ...(narrative?.warnings ?? []),
      ...(recentFlow?.warnings ?? []),
      ...(spotGamma?.warnings ?? []),
      ...(largest?.warnings ?? []),
      ...(heatmap?.warnings ?? []),
    ];
  }, [summary, levels, byStrike, byExpiry, narrative, recentFlow, spotGamma, largest, heatmap]);

  const coachLines = levels?.data?.notes?.coach ?? [];
  const signals = narrative?.data?.signals ?? [];
  const screener = narrative?.data?.screener ?? null;
  const freshness = summary?.meta?.asOf ?? null;

  // ---------------------------------------------------------------------------
  // Tab pane renderers
  // ---------------------------------------------------------------------------

  function renderDailyGex() {
    return (
      <div className="space-y-4">
        {/* KPI row */}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Spot" value={`$${fmtNum(summary?.data?.spot)}`} />
          <StatCard
            label="Total GEX"
            value={fmtNum(summary?.data?.gex?.total, 0)}
            tone={toneByNumber(summary?.data?.gex?.total)}
            subValue={summary?.data?.gex?.regimeLabel ?? "-"}
          />
          <StatCard
            label="Gamma Flip"
            value={fmtNum(levels?.data?.levels?.gammaFlip)}
            subValue={`CW ${fmtNum(levels?.data?.levels?.callWall)} | PW ${fmtNum(levels?.data?.levels?.putWall)}`}
          />
          <StatCard
            label="Directional Bias"
            value={summary?.data?.gex?.directionalBias ?? "-"}
            tone={
              (summary?.data?.gex?.directionalBias ?? "").includes("BULL") ? "positive"
              : (summary?.data?.gex?.directionalBias ?? "").includes("BEAR") ? "negative"
              : "neutral"
            }
          />
        </div>

        {/* Screener + Signals */}
        <div className="grid gap-4 lg:grid-cols-2">
          <SqueezeScreenerCard
            screener={
              screener
                ? {
                    probabilityScore: screener.probabilityScore,
                    setup: screener.setup,
                    confidence: screener.confidence,
                    factors: screener.factors?.map((f) => ({ name: f.name, value: f.score })),
                  }
                : null
            }
            isLoading={isLoading}
          />

          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <h2 className="mb-2 text-sm font-semibold text-zinc-200">Narrative Signals</h2>
            {isLoading ? (
              <p className="text-sm animate-pulse text-zinc-500">Loading…</p>
            ) : signals.length === 0 ? (
              <p className="text-sm text-zinc-500">No signals yet.</p>
            ) : (
              <div className="space-y-2 text-sm">
                {signals.map((signal, idx) => (
                  <div key={idx} className="rounded-lg border border-zinc-800 bg-black p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium capitalize text-zinc-200">{signal.type}</span>
                      <span className={`text-xs uppercase tracking-widest ${
                        signal.severity === "STRONG" ? "text-rose-400"
                        : signal.severity === "MODERATE" ? "text-amber-400"
                        : "text-zinc-400"
                      }`}>{signal.severity}</span>
                    </div>
                    <p className="mt-1 text-zinc-400">{signal.message}</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      Level: {fmtNum(signal.level)} | Dist: {fmtNum(signal.distancePct)}%
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Coach notes */}
        {coachLines.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <h3 className="mb-2 text-sm font-semibold text-zinc-200">Coach Notes</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
              {coachLines.slice(0, 5).map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  function renderByStrike() {
    const rows = byStrike?.data?.rows ?? [];
    return (
      <div className="space-y-4">
        <ByStrikeSplitBars
          rows={rows}
          spot={byStrike?.data?.spot ?? null}
          gammaFlip={levels?.data?.levels?.gammaFlip ?? null}
        />
        <SimpleTable
          title={`By Strike — ${rows.length} rows (${byStrike?.data?.filters?.expiryScope ?? expiryScope})`}
          columns={["Strike", "Call GEX", "Put GEX", "Net GEX", "Call OI", "Put OI"]}
          rows={strikeRows}
          emptyLabel="No strike rows returned"
        />
      </div>
    );
  }

  function renderByExpiry() {
    return (
      <SimpleTable
        title={`By Expiry (${byExpiry?.data?.dataSource ?? "—"})`}
        columns={["Expiry", "DTE", "Call GEX", "Put GEX", "Net GEX", "Call OI", "Put OI"]}
        rows={expiryRows}
        emptyLabel="No expiry rows returned"
      />
    );
  }

  function renderLargest() {
    return (
      <SimpleTable
        title={`Largest Strikes by GEX (${largest?.data?.filters?.sort ?? "abs_net"}, ${largest?.data?.cacheDate ?? "—"})`}
        columns={["Strike", "Call GEX", "Put GEX", "Net GEX", "Call OI", "Put OI"]}
        rows={largestRows}
        emptyLabel="No largest strike data"
      />
    );
  }

  function renderLevels() {
    const lvls = levels?.data?.levels;
    return (
      <div className="space-y-4">
        <LiveLevelsLadder
          spot={lvls?.spot ?? null}
          gammaFlip={lvls?.gammaFlip ?? null}
          callWall={lvls?.callWall ?? null}
          putWall={lvls?.putWall ?? null}
          gammaMagnet={lvls?.gammaMagnet ?? null}
          pinStrike={lvls?.pinStrike ?? null}
        />
        {coachLines.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <h3 className="mb-2 text-sm font-semibold text-zinc-200">Tactical Notes</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
              {coachLines.map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  function renderSpotGamma() {
    return (
      <SpotGammaPanel
        data={spotGamma?.data ?? null}
        isLoading={isLoading}
      />
    );
  }

  function renderHeatmap() {
    return (
      <div className="space-y-4">
        {/* Treemap + By Expiry Chart */}
        <div className="grid gap-4 lg:grid-cols-2">
          <TreemapHeatmap
            data={heatmap?.data?.treemap ?? null}
            isLoading={isLoading}
          />
          <ByExpiryAggregationChart
            rows={byExpiry?.data?.rows ?? null}
            isLoading={isLoading}
          />
        </div>

        {/* Matrix Heatmap */}
        <MatrixHeatmap
          data={
            heatmap?.data
              ? {
                  strikes: heatmap.data.strikes,
                  expiries: heatmap.data.expiries,
                  matrix: heatmap.data.matrix,
                }
              : null
          }
          isLoading={isLoading}
        />
      </div>
    );
  }

  function renderFlow() {
    return (
      <RecentFlowTape
        data={
          recentFlow?.data
            ? {
                flowRegime: recentFlow.data.flowRegime ?? null,
                dataSource: recentFlow.data.dataSource ?? null,
                rows: recentFlow.data.rows,
              }
            : null
        }
        isLoading={isLoading}
      />
    );
  }

  const tabContent: Record<GexTabId, () => React.ReactNode> = {
    "daily-gex": renderDailyGex,
    "by-strike": renderByStrike,
    "by-expiry": renderByExpiry,
    "largest": renderLargest,
    "levels": renderLevels,
    "spot-gamma": renderSpotGamma,
    "heatmap": renderHeatmap,
    "flow": renderFlow,
  };

  return (
    <div className="min-h-screen bg-zinc-950">
      <GlobalControlBar
        symbol={symbol}
        onSymbolChange={setSymbol}
        strikeCount={strikeCount}
        onStrikeCountChange={setStrikeCount}
        expiryScope={expiryScope}
        onExpiryScopeChange={setExpiryScope}
        metricFamily={metricFamily}
        onMetricFamilyChange={setMetricFamily}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isLoading={isLoading}
        freshness={freshness}
      />

      <div className="px-4 py-4 space-y-3">
        {/* Error banner */}
        {loadError && (
          <div className="rounded-xl border border-rose-900/70 bg-rose-950/30 p-4 text-sm text-rose-300">
            Failed to load: {loadError}
          </div>
        )}

        {/* Warnings */}
        {allWarnings.length > 0 && (
          <div className="rounded-xl border border-amber-900/70 bg-amber-950/30 p-3">
            <details>
              <summary className="cursor-pointer text-xs font-semibold text-amber-300">
                {allWarnings.length} module warning{allWarnings.length !== 1 ? "s" : ""}
              </summary>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-amber-200">
                {allWarnings.map((w, i) => (
                  <li key={`${w}-${i}`}>{w}</li>
                ))}
              </ul>
            </details>
          </div>
        )}

        {/* Active tab content */}
        <div>{tabContent[activeTab]?.()}</div>

        {/* Publish button — always visible at bottom */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => setPublishOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-indigo-700 bg-indigo-900/40 px-4 py-2 text-sm font-medium text-indigo-300 hover:bg-indigo-900/70 transition-colors"
          >
            <span>📤</span> Publish to Discord
          </button>
        </div>
      </div>

      <DiscordPublishDrawer
        symbol={symbol}
        isOpen={publishOpen}
        onClose={() => setPublishOpen(false)}
      />
    </div>
  );
}
