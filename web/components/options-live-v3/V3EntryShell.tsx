"use client";

import React, { useEffect, useMemo, useState } from "react";
import type { V3Envelope } from "@/lib/options-live-v3/contracts/types";
import { StatCard } from "@/components/options-live-v3/StatCard";
import { SimpleTable } from "@/components/options-live-v3/SimpleTable";
import { GlobalControlBar, type GexTabId, type MetricFamily, type WorkflowPresetId } from "@/components/options-live-v3/GlobalControlBar";
import { LiveLevelsLadder } from "@/components/options-live-v3/LiveLevelsLadder";
import { ByStrikeSplitBars } from "@/components/options-live-v3/ByStrikeSplitBars";
import { SpotGammaPanel } from "@/components/options-live-v3/SpotGammaPanel";
import { SqueezeScreenerCard } from "@/components/options-live-v3/SqueezeScreenerCard";
import { RecentFlowTape } from "@/components/options-live-v3/RecentFlowTape";
import { DiscordPublishDrawer } from "@/components/options-live-v3/DiscordPublishDrawer";
import { MatrixHeatmap } from "@/components/options-live-v3/MatrixHeatmap";
import { TreemapHeatmap } from "@/components/options-live-v3/TreemapHeatmap";
import { ByExpiryAggregationChart } from "@/components/options-live-v3/ByExpiryAggregationChart";
import { LargestByStrikeExpiryTable } from "@/components/options-live-v3/LargestByStrikeExpiryTable";
import { IntegratedViewPane } from "@/components/options-live-v3/IntegratedViewPane";
import { DataStatusStrip } from "@/components/options-live-v3/DataStatusStrip";
import { ExplainabilityDrawer } from "@/components/options-live-v3/ExplainabilityDrawer";
import { ModuleEmptyBanner } from "@/components/options-live-v3/ModuleEmptyBanner";
import { AlertRulesPanel } from "@/components/options-live-v3/AlertRulesPanel";
import { LlmNarrativeComparePanel } from "@/components/options-live-v3/LlmNarrativeComparePanel";

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
    secondaryCallWall?: number | null;
    putWall: number | null;
    secondaryPutWall?: number | null;
    gammaMagnet: number | null;
    pinStrike: number | null;
    expectedMoveUpper?: number | null;
    expectedMoveLower?: number | null;
    expectedMoveWidth?: number | null;
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
  call_vex?: number;
  put_vex?: number;
  call_charm?: number;
  put_charm?: number;
  call_dex?: number;
  put_dex?: number;
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
  integrityTier?: "Measured" | "Proxy" | "Low-Integrity";
  dataSourceLabel?: string;
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
    scope?: string;
    scopedNetGex?: number | null;
    integrityTier?: "Measured" | "Proxy" | "Low-Integrity";
    factors: Array<{ name: string; score: number }>;
  };
  notes?: {
    coach?: string[];
    tactical?: string[];
  };
  perspectives?: Array<{
    mode: "Scalper" | "Intraday" | "Swing";
    scope: "0dte" | "weekly" | "monthly";
    netGex: number | null;
    bias: "Expansion" | "Compression" | "Unavailable";
    tacticalScore?: number;
  }>;
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
type LargestData = { cacheDate: string | null; filters: { limit: number; sort: string; expiryScope?: string }; rows: LargestRow[] };
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

function deriveExpectedMoveFromText(lines: string[] | undefined, spot: number | null | undefined): {
  expectedMoveUpper: number | null;
  expectedMoveLower: number | null;
  expectedMoveWidth: number | null;
} {
  if (!lines?.length || typeof spot !== "number" || !Number.isFinite(spot) || spot <= 0) {
    return { expectedMoveUpper: null, expectedMoveLower: null, expectedMoveWidth: null };
  }

  const patterns = [
    /Expected Move is\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)/i,
    /Risk map:\s*EM\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)/i,
  ];

  for (const line of lines) {
    const normalized = line.replace(/[ÂÏâ]/g, " ");
    for (const pattern of patterns) {
      const match = pattern.exec(normalized);
      if (!match) continue;
      const lowerRaw = Number(match[1].replace(/,/g, ""));
      const upperRaw = Number(match[2].replace(/,/g, ""));
      if (!Number.isFinite(lowerRaw) || !Number.isFinite(upperRaw) || upperRaw <= lowerRaw) continue;

      const widthRaw = (upperRaw - lowerRaw) / 2;
      const midRaw = (upperRaw + lowerRaw) / 2;
      if (widthRaw <= 0 || midRaw <= 0) continue;

      const scaledWidth = (widthRaw / midRaw) * spot;
      if (!Number.isFinite(scaledWidth) || scaledWidth <= 0) continue;

      return {
        expectedMoveUpper: spot + scaledWidth,
        expectedMoveLower: spot - scaledWidth,
        expectedMoveWidth: scaledWidth,
      };
    }
  }

  return { expectedMoveUpper: null, expectedMoveLower: null, expectedMoveWidth: null };
}

function integrityTierClasses(tier: string | null | undefined): string {
  switch (tier) {
    case "Measured":
      return "border-emerald-700 bg-emerald-950/40 text-emerald-300";
    case "Proxy":
      return "border-amber-700 bg-amber-950/40 text-amber-300";
    case "Low-Integrity":
      return "border-zinc-600 bg-zinc-900/60 text-zinc-400";
    default:
      return "border-zinc-700 bg-zinc-900/40 text-zinc-500";
  }
}

async function fetchEnvelope<T>(url: string): Promise<V3Envelope<T>> {
  const res = await fetch(url, { cache: "no-store" });
  return (await res.json()) as V3Envelope<T>;
}

export function V3EntryShell() {
  const [symbol, setSymbol] = useState("SPY");
  const [activeTab, setActiveTab] = useState<GexTabId>("daily-gex");
  const [strikeCount, setStrikeCount] = useState(20);
  const [expiryScope, setExpiryScope] = useState("all");
  const [metricFamily, setMetricFamily] = useState<MetricFamily>("GEX");
  const [workflowPreset, setWorkflowPreset] = useState<WorkflowPresetId | null>(null);
  const [byStrikeSortMode, setByStrikeSortMode] = useState<"strike" | "abs">("strike");
  const [byExpirySortMode, setByExpirySortMode] = useState<"nearest" | "abs">("nearest");
  const [byExpiryViewMode, setByExpiryViewMode] = useState<"split" | "net">("split");
  const [largestLimit, setLargestLimit] = useState(25);
  const [largestSortMode, setLargestSortMode] = useState<"abs_net" | "call_gex" | "put_gex">("abs_net");
  const [pinnedStrike, setPinnedStrike] = useState<number | null>(null);

  const [heatmapMarket, setHeatmapMarket] = useState<"spx" | "ndx">("spx");
  const [heatmapMode, setHeatmapMode] = useState<"pcr" | "regular">("pcr");
  const [heatmapMetric, setHeatmapMetric] = useState<"net_gex" | "abs_gex" | "volume" | "oi">("net_gex");
  const [heatmapExpiryMode, setHeatmapExpiryMode] = useState<"bucketed" | "exact">("bucketed");
  const [selectedHeatmapCell, setSelectedHeatmapCell] = useState<{ strike: number; expiry: string } | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [explainOpen, setExplainOpen] = useState(false);
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

  const setStrikeCountManual = (value: number) => {
    setWorkflowPreset(null);
    setStrikeCount(value);
  };

  const setExpiryScopeManual = (value: string) => {
    setWorkflowPreset(null);
    setExpiryScope(value);
  };

  const applyWorkflowPreset = (preset: WorkflowPresetId) => {
    setWorkflowPreset(preset);
    if (preset === "scalper") {
      setStrikeCount(10);
      setExpiryScope("0dte");
      return;
    }
    if (preset === "intraday") {
      setStrikeCount(20);
      setExpiryScope("weekly");
      return;
    }
    setStrikeCount(50);
    setExpiryScope("monthly");
  };

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) {
        return;
      }
      if (event.altKey) {
        if (event.key === "1") setActiveTab("daily-gex");
        if (event.key === "2") setActiveTab("by-strike");
        if (event.key === "3") setActiveTab("by-expiry");
        if (event.key === "4") setActiveTab("spot-gamma");
        if (event.key === "5") setActiveTab("heatmap");
        if (event.key === "6") setActiveTab("flow");
      }
      if (event.shiftKey) {
        if (event.key === "1") setStrikeCountManual(10);
        if (event.key === "2") setStrikeCountManual(20);
        if (event.key === "3") setStrikeCountManual(50);
        if (event.key.toLowerCase() === "p") setPublishOpen(true);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = `options-live-v3:prefs:${symbol}`;
    const raw = window.localStorage.getItem(key);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as {
        strikeCount?: number;
        expiryScope?: string;
        metricFamily?: MetricFamily;
        activeTab?: GexTabId;
      };
      if (typeof saved.strikeCount === "number") setStrikeCount(saved.strikeCount);
      if (typeof saved.expiryScope === "string") setExpiryScope(saved.expiryScope);
      if (saved.metricFamily) setMetricFamily(saved.metricFamily);
      if (saved.activeTab) setActiveTab(saved.activeTab);
    } catch {
      // ignore malformed saved prefs
    }
  }, [symbol]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = `options-live-v3:prefs:${symbol}`;
    window.localStorage.setItem(
      key,
      JSON.stringify({ strikeCount, expiryScope, metricFamily, activeTab })
    );
  }, [symbol, strikeCount, expiryScope, metricFamily, activeTab]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = "options-live-v3:heatmap-prefs";
    const raw = window.localStorage.getItem(key);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as Record<string, { mode?: "pcr" | "regular"; metric?: "net_gex" | "abs_gex" | "volume" | "oi"; expiryMode?: "bucketed" | "exact" }>;
      const marketPrefs = saved[heatmapMarket];
      if (marketPrefs?.mode) setHeatmapMode(marketPrefs.mode);
      if (marketPrefs?.metric) setHeatmapMetric(marketPrefs.metric);
      if (marketPrefs?.expiryMode) setHeatmapExpiryMode(marketPrefs.expiryMode);
    } catch {
      // ignore malformed saved prefs
    }
  }, [heatmapMarket]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = "options-live-v3:heatmap-prefs";
    let saved: Record<string, { mode?: "pcr" | "regular"; metric?: "net_gex" | "abs_gex" | "volume" | "oi"; expiryMode?: "bucketed" | "exact" }> = {};
    try {
      saved = JSON.parse(window.localStorage.getItem(key) ?? "{}") as typeof saved;
    } catch {
      saved = {};
    }
    saved[heatmapMarket] = { mode: heatmapMode, metric: heatmapMetric, expiryMode: heatmapExpiryMode };
    window.localStorage.setItem(key, JSON.stringify(saved));
  }, [heatmapMarket, heatmapMode, heatmapMetric, heatmapExpiryMode]);

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
          fetchEnvelope<ByExpiryData>(`/api/options-live/v3/by-expiry?symbol=${encoded}&strikes=${strikes}&metricFamily=${metricFamily.toLowerCase()}&expiryScope=${expiryScope}`),
          fetchEnvelope<NarrativeData>(`/api/options-live/v3/narrative?symbol=${encoded}&expiryScope=${expiryScope}`),
          fetchEnvelope<RecentFlowData>(`/api/options-live/v3/recent-flow?symbol=${encoded}&limit=20`),
          fetchEnvelope<SpotGammaData>(`/api/options-live/v3/spot-gamma?symbol=${encoded}&smooth=1`),
          fetchEnvelope<LargestData>(`/api/options-live/v3/largest?symbol=${encoded}&limit=${largestLimit}&sort=${largestSortMode}&expiryScope=${expiryScope}`),
          fetchEnvelope<HeatmapData>(`/api/options-live/v3/heatmap?symbol=${encoded}&strikes=${strikes}&market=${heatmapMarket}&mode=${heatmapMode}&metric=${heatmapMetric}&expiryMode=${heatmapExpiryMode}`),
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
  }, [symbol, strikeCount, expiryScope, metricFamily, largestLimit, largestSortMode, heatmapMarket, heatmapMode, heatmapMetric, heatmapExpiryMode]);

  const strikeRows = useMemo(() => {
    const rows = byStrike?.data?.rows ?? [];
    return rows.slice(0, 12).map((row) => {
      switch (metricFamily) {
        case "VANNA":
          return [
            fmtNum(row.strike, 2),
            fmtNum(row.call_vex, 0),
            fmtNum(row.put_vex, 0),
            fmtNum((row.call_vex ?? 0) + (row.put_vex ?? 0), 0),
            fmtNum(row.call_oi, 0),
            fmtNum(row.put_oi, 0),
          ];
        case "CHARM":
          return [
            fmtNum(row.strike, 2),
            fmtNum(row.call_charm, 0),
            fmtNum(row.put_charm, 0),
            fmtNum((row.call_charm ?? 0) - (row.put_charm ?? 0), 0),
            fmtNum(row.call_oi, 0),
            fmtNum(row.put_oi, 0),
          ];
        case "DEX":
          return [
            fmtNum(row.strike, 2),
            fmtNum(row.call_dex, 0),
            fmtNum(row.put_dex, 0),
            fmtNum((row.call_dex ?? 0) + (row.put_dex ?? 0), 0),
            fmtNum(row.call_oi, 0),
            fmtNum(row.put_oi, 0),
          ];
        default: // GEX
          return [
            fmtNum(row.strike, 2),
            fmtNum(row.call_gex, 0),
            fmtNum(row.put_gex, 0),
            fmtNum(row.net_gex, 0),
            fmtNum(row.call_oi, 0),
            fmtNum(row.put_oi, 0),
          ];
      }
    });
  }, [byStrike, metricFamily]);

  const byExpirySortedRows = useMemo(() => {
    const rows = [...(byExpiry?.data?.rows ?? [])];
    if (byExpirySortMode === "abs") {
      rows.sort((a, b) => Math.abs((b.net_gex ?? 0)) - Math.abs((a.net_gex ?? 0)) || (a.expiry ?? "").localeCompare(b.expiry ?? ""));
    } else {
      rows.sort((a, b) => (a.dte ?? Number.MAX_SAFE_INTEGER) - (b.dte ?? Number.MAX_SAFE_INTEGER));
    }
    return rows;
  }, [byExpiry, byExpirySortMode]);

  const expiryRows = useMemo(() => {
    const rows = byExpirySortedRows;
    return rows.slice(0, 12).map((row) => [
      row.expiry ?? "-",
      String(row.dte ?? "-"),
      fmtNum(row.call_gex, 0),
      fmtNum(row.put_gex, 0),
      fmtNum(row.net_gex, 0),
      fmtNum(row.call_oi, 0),
      fmtNum(row.put_oi, 0),
    ]);
  }, [byExpirySortedRows]);

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

  const largestStrikeExpiryRows = useMemo(() => {
    const matrix = heatmap?.data?.matrix ?? [];
    if (!selectedHeatmapCell) return matrix;
    return matrix.filter((row) => row.expiry === selectedHeatmapCell.expiry);
  }, [heatmap, selectedHeatmapCell]);

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
  const modeTacticalLines = narrative?.data?.notes?.tactical ?? [];
  const perspectiveRows = narrative?.data?.perspectives ?? [];
  const signals = narrative?.data?.signals ?? [];
  const tacticalUnifiedLines = useMemo(() => {
    const seen = new Set<string>();
    const dropPrefixes = [
      "Scalper (",
      "Intraday (",
      "Swing (",
      "Scope mode active",
      "scoped net GEX",
      "0DTE scoped net GEX",
      "Weekly scoped net GEX",
      "Monthly scoped net GEX",
    ];

    const merged = [...coachLines, ...modeTacticalLines]
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .filter((line) => !dropPrefixes.some((prefix) => line.startsWith(prefix)));

    const deduped: string[] = [];
    for (const line of merged) {
      const key = line.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(line);
    }
    return deduped.slice(0, 8);
  }, [coachLines, modeTacticalLines]);
  const screener = narrative?.data?.screener ?? null;
  const narrativeIntegrityTier = narrative?.data?.integrityTier ?? null;
  const narrativeDataSourceLabel = narrative?.data?.dataSourceLabel ?? null;
  const freshness = summary?.meta?.asOf ?? null;
  const activeStatus = useMemo(() => {
    if (activeTab === "by-strike") return { meta: byStrike?.meta, warnings: byStrike?.warnings ?? [], error: byStrike?.error ?? null };
    if (activeTab === "by-expiry") return { meta: byExpiry?.meta, warnings: byExpiry?.warnings ?? [], error: byExpiry?.error ?? null };
    if (activeTab === "largest") return { meta: largest?.meta, warnings: largest?.warnings ?? [], error: largest?.error ?? null };
    if (activeTab === "spot-gamma") return { meta: spotGamma?.meta, warnings: spotGamma?.warnings ?? [], error: spotGamma?.error ?? null };
    if (activeTab === "heatmap") return { meta: heatmap?.meta, warnings: heatmap?.warnings ?? [], error: heatmap?.error ?? null };
    if (activeTab === "flow") return { meta: recentFlow?.meta, warnings: recentFlow?.warnings ?? [], error: recentFlow?.error ?? null };
    return {
      meta: summary?.meta ?? levels?.meta,
      warnings: [...(summary?.warnings ?? []), ...(narrative?.warnings ?? []), ...(levels?.warnings ?? [])],
      error: summary?.error ?? narrative?.error ?? levels?.error ?? null,
    };
  }, [activeTab, byStrike, byExpiry, largest, levels, spotGamma, heatmap, recentFlow, summary, narrative]);

  // ---------------------------------------------------------------------------
  // Tab pane renderers
  // ---------------------------------------------------------------------------

  function renderDailyGex() {
    const lvlsRaw = levels?.data?.levels;
    const derivedExpectedMove = deriveExpectedMoveFromText(
      [...(levels?.data?.notes?.coach ?? []), ...(narrative?.data?.notes?.tactical ?? []), ...(narrative?.data?.notes?.coach ?? [])],
      lvlsRaw?.spot ?? summary?.data?.spot ?? null
    );
    const lvls = {
      ...lvlsRaw,
      expectedMoveUpper: lvlsRaw?.expectedMoveUpper ?? derivedExpectedMove.expectedMoveUpper,
      expectedMoveLower: lvlsRaw?.expectedMoveLower ?? derivedExpectedMove.expectedMoveLower,
      expectedMoveWidth: lvlsRaw?.expectedMoveWidth ?? derivedExpectedMove.expectedMoveWidth,
    };
    const directionalBias = summary?.data?.gex?.directionalBias ?? "-";
    const directionalBiasTone =
      directionalBias.includes("BULL") ? "positive"
      : directionalBias.includes("BEAR") ? "negative"
      : "neutral";

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
            label="Expected Move"
            value={
              lvls?.expectedMoveWidth != null
                ? `±${fmtNum(lvls.expectedMoveWidth)}`
                : "-"
            }
            subValue={
              lvls?.expectedMoveLower != null && lvls?.expectedMoveUpper != null
                ? `${fmtNum(lvls.expectedMoveLower)} ↔ ${fmtNum(lvls.expectedMoveUpper)}`
                : undefined
            }
            tone={lvls?.expectedMoveWidth != null ? "neutral" : undefined}
          />
        </div>

        {/* Integrity tier strip */}
        {narrativeIntegrityTier && (
          <div className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs ${integrityTierClasses(narrativeIntegrityTier)}`}>
            <span className="font-semibold uppercase tracking-wider">{narrativeIntegrityTier}</span>
            <span className="opacity-60">·</span>
            <span>{narrativeDataSourceLabel}</span>
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-3">
          <div className="space-y-4 xl:col-span-2">
            <LiveLevelsLadder
              spot={lvls?.spot ?? null}
              gammaFlip={lvls?.gammaFlip ?? null}
              callWall={lvls?.callWall ?? null}
              secondaryCallWall={lvls?.secondaryCallWall ?? null}
              putWall={lvls?.putWall ?? null}
              secondaryPutWall={lvls?.secondaryPutWall ?? null}
              gammaMagnet={lvls?.gammaMagnet ?? null}
              pinStrike={lvls?.pinStrike ?? null}
              expectedMoveUpper={lvls?.expectedMoveUpper ?? null}
              expectedMoveLower={lvls?.expectedMoveLower ?? null}
              expectedMoveWidth={lvls?.expectedMoveWidth ?? null}
              symbol={symbol}
              selectedLevel={selectedLevel}
              onSelectLevel={(level) => {
                setSelectedLevel(level);
                setPinnedStrike(level);
              }}
            />
          </div>

          <div className="space-y-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
              <p className="text-xs uppercase tracking-widest text-zinc-400">Directional Bias</p>
              <div className="mt-2 flex items-center justify-between gap-3">
                <span
                  className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${
                    directionalBiasTone === "positive"
                      ? "border-emerald-700/60 bg-emerald-900/30 text-emerald-200"
                      : directionalBiasTone === "negative"
                        ? "border-rose-700/60 bg-rose-900/30 text-rose-200"
                        : "border-zinc-700 bg-zinc-900 text-zinc-200"
                  }`}
                >
                  {directionalBias}
                </span>
                {narrativeIntegrityTier && (
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${integrityTierClasses(narrativeIntegrityTier)}`}>
                    {narrativeIntegrityTier}
                  </span>
                )}
              </div>
            </div>

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
              onExplain={() => setExplainOpen(true)}
            />

            {screener && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                <h2 className="mb-2 text-sm font-semibold text-zinc-200">Mode Analysis Context</h2>
                <div className="space-y-1 text-sm text-zinc-300">
                  <p>
                    Scope: <span className="font-semibold text-zinc-100 uppercase">{screener.scope ?? expiryScope}</span>
                  </p>
                  <p>
                    Scoped Net GEX: <span className={`font-mono font-semibold ${(screener.scopedNetGex ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{fmtNum(screener.scopedNetGex, 0)}</span>
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {perspectiveRows.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-zinc-200">Multi-Timeframe Tactical View (Primary)</h3>
              {narrativeIntegrityTier && (
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${integrityTierClasses(narrativeIntegrityTier)}`}>
                  {narrativeIntegrityTier}
                </span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-zinc-400">
                    <th className="py-1.5">Mode</th>
                    <th className="py-1.5">Scope</th>
                    <th className="py-1.5 text-right">Net GEX</th>
                    <th className="py-1.5 text-right">Bias</th>
                    <th className="py-1.5 text-right">Tactical Score</th>
                  </tr>
                </thead>
                <tbody>
                  {perspectiveRows.map((row) => (
                    <tr key={row.mode} className="border-b border-zinc-900 text-zinc-300 last:border-b-0">
                      <td className="py-1.5 font-medium text-zinc-100">{row.mode}</td>
                      <td className="py-1.5 uppercase text-zinc-400">{row.scope}</td>
                      <td className="py-1.5 text-right font-mono">{fmtNum(row.netGex, 0)}</td>
                      <td className={`py-1.5 text-right font-semibold ${row.bias === "Expansion" ? "text-rose-400" : row.bias === "Compression" ? "text-emerald-400" : "text-zinc-400"}`}>
                        {row.bias}
                      </td>
                      <td className="py-1.5 text-right">
                        {row.tacticalScore != null ? (
                          <span className={`font-mono font-semibold ${row.tacticalScore >= 60 ? "text-emerald-400" : row.tacticalScore >= 35 ? "text-amber-400" : "text-zinc-400"}`}>
                            {row.tacticalScore}
                          </span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tacticalUnifiedLines.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <h3 className="mb-2 text-sm font-semibold text-zinc-200">Tactical Guidance (Execution)</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
              {tacticalUnifiedLines.map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-zinc-200">Alert Rules (Secondary)</h3>
            <span className="rounded border border-zinc-700 bg-zinc-900 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
              Lower Priority
            </span>
          </div>
          <AlertRulesPanel symbol={symbol} />
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-zinc-200">Narrative Signals (Context)</h2>
            <div className="flex items-center gap-1.5">
              {narrativeIntegrityTier && (
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${integrityTierClasses(narrativeIntegrityTier)}`}>
                  {narrativeIntegrityTier}
                </span>
              )}
              <span className="rounded border border-indigo-800 bg-indigo-950/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-200">
                Scope: {screener?.scope ?? expiryScope}
              </span>
            </div>
          </div>
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
                  <button
                    onClick={() => setExplainOpen(true)}
                    className="mt-2 text-xs text-indigo-300 hover:text-indigo-200"
                  >
                    Why this score?
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <LlmNarrativeComparePanel symbol={symbol} expiryScope={expiryScope} />

        {(levels?.warnings?.length ?? 0) > 0 && <ModuleEmptyBanner state="degraded" moduleName="Key Levels" warnings={levels?.warnings ?? []} />}

        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-xs text-zinc-400">
          Shortcuts: Alt+1..6 switches major tabs. Shift+1/2/3 sets 10, 20, 50 strikes. Shift+P opens Discord publish.
        </div>
      </div>
    );
  }

  function renderByStrike() {
    const rows = byStrike?.data?.rows ?? [];
    if (!isLoading && byStrike?.error) return <ModuleEmptyBanner state="error" moduleName="By-Strike" message={byStrike.error} />;
    if (!isLoading && !byStrike?.data) return <ModuleEmptyBanner state="empty" moduleName="By-Strike" />;
    return (
      <div className="space-y-4">
        {/* Panel scope applicability label — by-strike uses consolidated gex_profiles (not expiry-filtered) */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded border border-zinc-700 bg-zinc-900/40 px-2 py-0.5 font-semibold uppercase tracking-wider text-zinc-400">
            Consolidated
          </span>
          <span className="text-zinc-500">Source: gex_profiles (all-expiry rollup)</span>
          <span className="ml-auto rounded border border-indigo-800/60 bg-indigo-950/30 px-2 py-0.5 text-indigo-300 uppercase">
            Scope: {byStrike?.data?.filters?.expiryScope ?? expiryScope}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-xs">
          <span className="text-zinc-500">Sort:</span>
          <button
            onClick={() => setByStrikeSortMode("strike")}
            className={`rounded px-2 py-1 ${byStrikeSortMode === "strike" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Strike Order
          </button>
          <button
            onClick={() => setByStrikeSortMode("abs")}
            className={`rounded px-2 py-1 ${byStrikeSortMode === "abs" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Abs Magnitude
          </button>
          {pinnedStrike !== null && (
            <button
              onClick={() => setPinnedStrike(null)}
              className="ml-auto rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-300"
            >
              Clear Highlight ({fmtNum(pinnedStrike, 2)})
            </button>
          )}
        </div>
        <ByStrikeSplitBars
          rows={rows}
          spot={byStrike?.data?.spot ?? null}
          gammaFlip={levels?.data?.levels?.gammaFlip ?? null}
          highlightedStrike={pinnedStrike ?? selectedLevel}
          sortMode={byStrikeSortMode}
          metricFamily={metricFamily}
        />
        <SimpleTable
          title={`By Strike — ${rows.length} rows (${byStrike?.data?.filters?.expiryScope ?? expiryScope})`}
          columns={(() => {
            const suffix = metricFamily === "VANNA" ? "VEX" : metricFamily === "CHARM" ? "Charm" : metricFamily === "DEX" ? "DEX" : "GEX";
            return ["Strike", `Call ${suffix}`, `Put ${suffix}`, `Net ${suffix}`, "Call OI", "Put OI"];
          })()}
          rows={strikeRows}
          emptyLabel="No strike rows returned"
        />
        {(byStrike?.warnings?.length ?? 0) > 0 && <ModuleEmptyBanner state="degraded" moduleName="By-Strike" warnings={byStrike?.warnings ?? []} />}
      </div>
    );
  }

  function renderByExpiry() {
    if (!isLoading && byExpiry?.error) return <ModuleEmptyBanner state="error" moduleName="By-Expiry" message={byExpiry.error} />;
    if (!isLoading && !byExpiry?.data) return <ModuleEmptyBanner state="empty" moduleName="By-Expiry" />;
    const byExpirySource = byExpiry?.data?.dataSource;
    const byExpiryTier: "Measured" | "Proxy" | "Low-Integrity" | null =
      byExpirySource === "macro-cache" ? "Measured"
      : byExpirySource === "dolt" ? "Proxy"
      : byExpirySource === "expected-moves" ? "Low-Integrity"
      : null;
    return (
      <div className="space-y-4">
        {/* Panel scope applicability label */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded border px-2 py-0.5 font-semibold uppercase tracking-wider ${integrityTierClasses(byExpiryTier)}`}>
            {byExpiryTier ?? "Unknown"}
          </span>
          <span className="text-zinc-500">Source: {byExpirySource ?? "—"}</span>
          <span className="ml-auto rounded border border-indigo-800/60 bg-indigo-950/30 px-2 py-0.5 text-indigo-300 uppercase">
            Scope: {expiryScope}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-xs">
          <span className="text-zinc-500">View:</span>
          <button
            onClick={() => setByExpiryViewMode("split")}
            className={`rounded px-2 py-1 ${byExpiryViewMode === "split" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Net + Split
          </button>
          <button
            onClick={() => setByExpiryViewMode("net")}
            className={`rounded px-2 py-1 ${byExpiryViewMode === "net" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Net Only
          </button>
          <span className="ml-3 text-zinc-500">Rank:</span>
          <button
            onClick={() => setByExpirySortMode("nearest")}
            className={`rounded px-2 py-1 ${byExpirySortMode === "nearest" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Nearest Expiry
          </button>
          <button
            onClick={() => setByExpirySortMode("abs")}
            className={`rounded px-2 py-1 ${byExpirySortMode === "abs" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-300"}`}
          >
            Abs GEX
          </button>
        </div>

        <ByExpiryAggregationChart rows={byExpirySortedRows} isLoading={isLoading} viewMode={byExpiryViewMode} />

        <SimpleTable
          title={`By Expiry (${byExpiry?.data?.dataSource ?? "—"})`}
          columns={["Expiry", "DTE", "Call GEX", "Put GEX", "Net GEX", "Call OI", "Put OI"]}
          rows={expiryRows}
          emptyLabel="No expiry rows returned"
        />
        {(byExpiry?.warnings?.length ?? 0) > 0 && <ModuleEmptyBanner state="degraded" moduleName="By-Expiry" warnings={byExpiry?.warnings ?? []} />}
      </div>
    );
  }

  function renderLargest() {
    return (
      <div className="space-y-4">
        {selectedHeatmapCell && (
          <div className="rounded-xl border border-indigo-900/70 bg-indigo-950/20 px-3 py-2 text-xs text-indigo-200">
            Filtered from heatmap cell: expiry <strong>{selectedHeatmapCell.expiry}</strong>, strike <strong>{fmtNum(selectedHeatmapCell.strike, 2)}</strong>
            <button
              onClick={() => setSelectedHeatmapCell(null)}
              className="ml-3 rounded border border-indigo-700 px-2 py-0.5 text-indigo-200 hover:bg-indigo-900/40"
            >
              Clear Filter
            </button>
          </div>
        )}

        <LargestByStrikeExpiryTable
          rows={largestStrikeExpiryRows}
          spot={summary?.data?.spot ?? null}
          limit={largestLimit}
          sortMode={largestSortMode}
          onLimitChange={setLargestLimit}
          onSortModeChange={setLargestSortMode}
          onSelectRow={(row) => {
            setPinnedStrike(row.strike);
            setActiveTab("by-strike");
          }}
        />

        <SimpleTable
          title={`Largest Strikes by GEX (${largest?.data?.filters?.sort ?? "abs_net"}, ${largest?.data?.cacheDate ?? "—"})`}
          columns={["Strike", "Call GEX", "Put GEX", "Net GEX", "Call OI", "Put OI"]}
          rows={largestRows}
          emptyLabel="No largest strike data"
        />
      </div>
    );
  }

  function renderIntegrated() {
    return (
      <IntegratedViewPane
        rows={byStrike?.data?.rows ?? []}
        spot={summary?.data?.spot ?? null}
        pinnedStrike={pinnedStrike ?? selectedLevel}
        onPinStrike={(strike) => {
          setPinnedStrike(strike);
          setSelectedLevel(strike);
        }}
      />
    );
  }

  function renderSpotGamma() {
    if (!isLoading && spotGamma?.error) return <ModuleEmptyBanner state="error" moduleName="Spot Gamma" message={spotGamma.error} />;
    if (!isLoading && !spotGamma?.data) return <ModuleEmptyBanner state="empty" moduleName="Spot Gamma" />;
    return (
      <div className="space-y-3">
        <SpotGammaPanel
          data={spotGamma?.data ?? null}
          isLoading={isLoading}
        />
        {(spotGamma?.warnings?.length ?? 0) > 0 && <ModuleEmptyBanner state="degraded" moduleName="Spot Gamma" warnings={spotGamma?.warnings ?? []} />}
      </div>
    );
  }

  function renderHeatmap() {
    return (
      <div id="options-live-v3-heatmap-pack-capture" className="space-y-4">
        <div className="grid gap-2 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <select
            value={heatmapMarket}
            onChange={(e) => setHeatmapMarket(e.target.value as "spx" | "ndx")}
            className="h-8 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          >
            <option value="spx">S&P</option>
            <option value="ndx">Nasdaq</option>
          </select>
          <select
            value={heatmapMode}
            onChange={(e) => setHeatmapMode(e.target.value as "pcr" | "regular")}
            className="h-8 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          >
            <option value="pcr">P/C Ratio Heatmap</option>
            <option value="regular">Regular Heatmap</option>
          </select>
          <select
            value={heatmapMetric}
            onChange={(e) => setHeatmapMetric(e.target.value as "net_gex" | "abs_gex" | "volume" | "oi")}
            className="h-8 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
            disabled={heatmapMode === "pcr"}
          >
            <option value="net_gex">Net GEX</option>
            <option value="abs_gex">Abs GEX</option>
            <option value="volume">Volume</option>
            <option value="oi">Open Interest</option>
          </select>
          <select
            value={heatmapExpiryMode}
            onChange={(e) => setHeatmapExpiryMode(e.target.value as "bucketed" | "exact")}
            className="h-8 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          >
            <option value="bucketed">Bucketed Expiry</option>
            <option value="exact">Exact Expiry</option>
          </select>
        </div>

        {/* Treemap + By Expiry Chart */}
        <div className="grid gap-4 lg:grid-cols-2">
          <TreemapHeatmap
            data={heatmap?.data?.treemap ?? null}
            isLoading={isLoading}
          />
          <ByExpiryAggregationChart
            rows={byExpirySortedRows}
            isLoading={isLoading}
            viewMode={byExpiryViewMode}
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
          onCellClick={(cell) => {
            setSelectedHeatmapCell({ strike: cell.strike, expiry: cell.expiry });
            setPinnedStrike(cell.strike);
            setActiveTab("largest");
          }}
        />
      </div>
    );
  }

  function renderFlow() {
    if (!isLoading && recentFlow?.error) return <ModuleEmptyBanner state="error" moduleName="Recent Flow" message={recentFlow.error} />;
    if (!isLoading && !recentFlow?.data) return <ModuleEmptyBanner state="empty" moduleName="Recent Flow" />;
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
    "integrated": renderIntegrated,
    "largest": renderLargest,
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
        onStrikeCountChange={setStrikeCountManual}
        expiryScope={expiryScope}
        onExpiryScopeChange={setExpiryScopeManual}
        metricFamily={metricFamily}
        onMetricFamilyChange={setMetricFamily}
        activeWorkflowPreset={workflowPreset}
        onWorkflowPresetChange={applyWorkflowPreset}
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

        {/* Active tab content */}
        <div id="options-live-v3-publish-capture">{tabContent[activeTab]?.()}</div>

        <DataStatusStrip
          asOf={activeStatus.meta?.asOf ?? null}
          freshnessMs={activeStatus.meta?.freshnessMs ?? null}
          warnings={activeStatus.warnings}
          error={activeStatus.error}
        />

        {/* Module warnings — collapsed, low-priority info */}
        {allWarnings.length > 0 && (
          <details className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-2">
            <summary className="cursor-pointer text-xs text-zinc-500">
              {allWarnings.length} module warning{allWarnings.length !== 1 ? "s" : ""}
            </summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-zinc-400">
              {allWarnings.map((w, i) => (
                <li key={`${w}-${i}`}>{w}</li>
              ))}
            </ul>
          </details>
        )}

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
        activeTab={activeTab}
        onRequestTabChange={setActiveTab}
        isOpen={publishOpen}
        onClose={() => setPublishOpen(false)}
      />

      <ExplainabilityDrawer
        symbol={symbol}
        snapshotId={summary?.meta?.asOf ? `${summary.meta.asOf}:${activeTab}` : null}
        isOpen={explainOpen}
        onClose={() => setExplainOpen(false)}
      />
    </div>
  );
}
