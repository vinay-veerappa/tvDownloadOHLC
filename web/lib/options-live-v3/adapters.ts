import { createHash } from "crypto";
import { readFile } from "fs/promises";
import path from "path";
import {
  type DailyStructure,
  loadDailyLevels,
  loadGexProfiles,
  loadMacroCache,
  normalizeSymbolRoot,
  loadPipelineState,
  type MacroContract,
  resolveExpectedMoveTicker,
  resolveDailyStructure,
  resolveProfileRows,
  resolveTickerEntry,
} from "@/lib/options-live-v3/data";
import { queryDoltByExpiry } from "@/lib/options-live-v3/dolt";
import { loadLiveOptionSnapshot } from "@/lib/options-live-v3/live-chain";
import prisma from "@/lib/prisma";
import { getExpectedMoveData } from "@/actions/get-expected-move";

type SummaryData = {
  implemented: true;
  module: "summary";
  symbol: string;
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
  implemented: true;
  module: "levels";
  symbol: string;
  runLabel: string | null;
  spot: number | null;
  levels: {
    spot: number | null;
    gammaFlip: number | null;
    callWall: number | null;
      secondaryCallWall: number | null;
    putWall: number | null;
      secondaryPutWall: number | null;
    gammaMagnet: number | null;
    pinStrike: number | null;
      expectedMoveUpper: number | null;
      expectedMoveLower: number | null;
      expectedMoveWidth: number | null;
  };
  scored: {
    resistanceWalls: Array<Record<string, unknown>>;
    supportWalls: Array<Record<string, unknown>>;
    pivots: Array<Record<string, unknown>>;
  };
  notes: {
    coach: string[];
    tactical: string[];
  };
};

function parseNumericToken(value: string): number | null {
  const cleaned = value.replace(/,/g, "").trim();
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseExpectedMoveFromNotes(lines: string[] | undefined): {
  lower: number | null;
  upper: number | null;
  width: number | null;
} {
  if (!lines || lines.length === 0) {
    return { lower: null, upper: null, width: null };
  }
  const patterns = [
    /Expected move:\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)(?:\s*\(±\s*([\d,]+(?:\.\d+)?)\))?/i,
    /Expected\s*Move\s*(?:is|:)\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)(?:\s*\(±\s*([\d,]+(?:\.\d+)?)\))?/i,
  ];

  for (const line of lines) {
    for (const pattern of patterns) {
      const match = pattern.exec(line);
      if (!match) continue;
      const lower = parseNumericToken(match[1]);
      const upper = parseNumericToken(match[2]);
      const width = match[3]
        ? parseNumericToken(match[3])
        : lower !== null && upper !== null
          ? Math.abs(upper - lower) / 2
          : null;
      return { lower, upper, width };
    }
  }
  return { lower: null, upper: null, width: null };
}

function parseExpectedMoveFromStructure(structure: DailyStructure | null | undefined): {
  lower: number | null;
  upper: number | null;
  width: number | null;
} {
  const rows = (structure?.expected_moves as Array<Record<string, unknown>> | undefined) ?? [];
  for (const row of rows) {
    const lower = toNum(row.em_lower);
    const upper = toNum(row.em_upper);
    const width = toNum(row.em_value) ?? (lower !== null && upper !== null ? Math.abs(upper - lower) / 2 : null);
    if (lower !== null && upper !== null && width !== null && width > 0) {
      return { lower, upper, width };
    }
  }
  return { lower: null, upper: null, width: null };
}

function structureSupportsExpectedMove(structure: DailyStructure | null | undefined, symbol: string): boolean {
  if (!structure) return false;
  const root = normalizeSymbolRoot(symbol);
  const asset = normalizeSymbolRoot(String(structure.asset ?? ""));
  const cash = normalizeSymbolRoot(String(structure.cash_ticker ?? ""));
  const canonical = resolveExpectedMoveTicker(symbol);
  return asset === root || cash === root || cash === canonical;
}

function resolveExpectedMoveFromStructure(
  structure: DailyStructure | null | undefined,
  symbol: string,
  targetSpot: number | null
): {
  lower: number | null;
  upper: number | null;
  width: number | null;
} {
  if (!structure) return { lower: null, upper: null, width: null };

  const parsed = parseExpectedMoveFromStructure(structure);
  if (parsed.width === null || parsed.lower === null || parsed.upper === null) {
    return parsed;
  }

  const root = normalizeSymbolRoot(symbol);
  const asset = normalizeSymbolRoot(String(structure.asset ?? ""));
  const cash = normalizeSymbolRoot(String(structure.cash_ticker ?? ""));
  const canonical = resolveExpectedMoveTicker(symbol);

  // Exact asset-space match: already in the correct space.
  if (asset === root) {
    return parsed;
  }

  // Cash-ticker match from translated futures structure: scale EM by percentage
  // back into the requested cash symbol's spot space.
  if ((cash === root || cash === canonical) && targetSpot !== null && targetSpot > 0) {
    const sourceMid = (parsed.upper + parsed.lower) / 2;
    if (sourceMid > 0) {
      const scaledWidth = (parsed.width / sourceMid) * targetSpot;
      if (scaledWidth > 0) {
        return {
          lower: targetSpot - scaledWidth,
          upper: targetSpot + scaledWidth,
          width: scaledWidth,
        };
      }
    }
  }

  return { lower: null, upper: null, width: null };
}

async function loadExpectedMoveBandFromDb(symbol: string): Promise<{
  lower: number | null;
  upper: number | null;
  width: number | null;
  ticker: string;
} | null> {
  const isPositiveFinite = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value) && value > 0;

  const ticker = resolveExpectedMoveTicker(symbol);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const queryFirstRow = async () =>
    prisma.expectedMove.findFirst({
      where: {
        ticker,
        calculationDate: today,
      },
      orderBy: {
        expiryDate: "asc",
      },
    });

  let row = await queryFirstRow();

  // New symbols may not be in today's EM cache yet. Trigger one live pull
  // for the canonical ticker and re-check DB before giving up.
  if (!row) {
    try {
      const live = await getExpectedMoveData([ticker], false);
      row = await queryFirstRow();

      // Brand-new tickers may not have an immediately queryable DB row yet.
      // If live fetch succeeded, derive EM band directly from response payload.
      if (!row && live?.success && Array.isArray(live.data)) {
        const item = live.data.find((entry: unknown) => {
          if (!entry || typeof entry !== "object") return false;
          const t = (entry as { ticker?: unknown }).ticker;
          return typeof t === "string" && t.toUpperCase() === ticker;
        }) as { price?: unknown; expirations?: Array<Record<string, unknown>> } | undefined;

        if (item && isPositiveFinite(item.price)) {
          const firstExp = Array.isArray(item.expirations) ? item.expirations[0] : undefined;
          const widthCandidates = [
            firstExp?.manual_em,
            firstExp?.adj_em,
            firstExp?.em_252,
            firstExp?.em_365,
          ];
          const width = widthCandidates.find((v) => isPositiveFinite(v));

          if (typeof width === "number") {
            return {
              lower: item.price - width,
              upper: item.price + width,
              width,
              ticker,
            };
          }
        }
      }
    } catch {
      // Keep null row path; callers will apply guarded fallback behavior.
    }
  }

  if (!row) return null;

  const width =
    (isPositiveFinite(row.manualEm) ? row.manualEm : null) ??
    (isPositiveFinite(row.adjEm) ? row.adjEm : null) ??
    (isPositiveFinite(row.em252) ? row.em252 : null) ??
    (isPositiveFinite(row.em365) ? row.em365 : null);

  const anchor = isPositiveFinite(row.price) ? row.price : null;
  if (width === null || anchor === null) {
    return { lower: null, upper: null, width: null, ticker };
  }

  return {
    lower: anchor - width,
    upper: anchor + width,
    width,
    ticker,
  };
}

function deriveExpectedMoveFromSnapshot(
  snapshot: import("@/lib/options-live-v3/data").MacroCacheResult | null | undefined,
  fallbackSpot: number | null | undefined
): {
  lower: number | null;
  upper: number | null;
  width: number | null;
  expiry: string | null;
} {
  const spot = snapshot?.spot ?? fallbackSpot ?? null;
  if (spot === null || !Number.isFinite(spot) || spot <= 0) {
    return { lower: null, upper: null, width: null, expiry: null };
  }

  const calls = snapshot?.calls ?? [];
  const puts = snapshot?.puts ?? [];
  if (!calls.length || !puts.length) {
    return { lower: null, upper: null, width: null, expiry: null };
  }

  const expirySet = new Set<string>();
  for (const contract of calls) {
    if (typeof contract.expiry === "string" && contract.expiry) expirySet.add(contract.expiry);
  }
  for (const contract of puts) {
    if (typeof contract.expiry === "string" && contract.expiry) expirySet.add(contract.expiry);
  }

  const sortedExpiries = Array.from(expirySet)
    .map((expiry) => ({ expiry, time: new Date(expiry).getTime() }))
    .filter((entry) => Number.isFinite(entry.time))
    .sort((a, b) => a.time - b.time);

  for (const entry of sortedExpiries) {
    const callCandidates = calls.filter((contract) => contract.expiry === entry.expiry && typeof contract.strike === "number");
    const putCandidates = puts.filter((contract) => contract.expiry === entry.expiry && typeof contract.strike === "number");
    if (!callCandidates.length || !putCandidates.length) continue;

    const nearestCall = [...callCandidates].sort((a, b) => Math.abs((a.strike ?? 0) - spot) - Math.abs((b.strike ?? 0) - spot))[0];
    const nearestPut = [...putCandidates].sort((a, b) => Math.abs((a.strike ?? 0) - spot) - Math.abs((b.strike ?? 0) - spot))[0];
    if (!nearestCall || !nearestPut) continue;

    const callMark = nearestCall.mark ?? nearestCall.last ?? 0;
    const putMark = nearestPut.mark ?? nearestPut.last ?? 0;
    const straddle = callMark + putMark;
    const width = Number.isFinite(straddle) && straddle > 0 ? straddle * 0.85 : null;
    if (width === null || width <= 0) continue;

    return {
      lower: spot - width,
      upper: spot + width,
      width,
      expiry: entry.expiry,
    };
  }

  return { lower: null, upper: null, width: null, expiry: null };
}

function firstNumericLevel(rows: Array<Record<string, unknown>> | undefined): number | null {
  if (!rows || rows.length === 0) return null;
  for (const row of rows) {
    const value =
      toNum(row.level) ??
      toNum(row.price) ??
      toNum(row.strike) ??
      toNum(row.value) ??
      toNum(row.wall);
    if (value !== null) return value;
  }
  return null;
}

function isReasonableSecondaryLevel(level: number | null, spot: number | null): boolean {
  if (level === null) return false;
  if (spot === null || spot === 0) return true;
  const pct = Math.abs((level - spot) / spot);
  return pct <= 0.35;
}

type OptionSnapshotSource = "macro-cache" | "live-chain";

type OptionSnapshot = {
  snapshot: import("@/lib/options-live-v3/data").MacroCacheResult;
  source: OptionSnapshotSource;
};

type StrikeAggregateRow = {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  cumulative_gex: number;
  call_oi: number;
  put_oi: number;
  call_vol: number;
  put_vol: number;
  call_premium: number;
  put_premium: number;
  call_dex: number | null;
  put_dex: number | null;
  call_charm: number | null;
  put_charm: number | null;
  call_avg_iv: number | null;
  put_avg_iv: number | null;
};

async function loadOptionSnapshot(symbol: string): Promise<OptionSnapshot | null> {
  const macro = await loadMacroCache(symbol).catch(() => null);
  if (macro && ((macro.calls?.length ?? 0) > 0 || (macro.puts?.length ?? 0) > 0)) {
    return { snapshot: macro, source: "macro-cache" };
  }

  const live = await loadLiveOptionSnapshot(symbol).catch(() => null);
  if (live && ((live.calls?.length ?? 0) > 0 || (live.puts?.length ?? 0) > 0)) {
    return { snapshot: live, source: "live-chain" };
  }

  return null;
}

function buildStrikeAggregatesFromSnapshot(
  snapshot: import("@/lib/options-live-v3/data").MacroCacheResult,
  expiryScope = "all"
): StrikeAggregateRow[] {
  const spot = snapshot.spot ?? 0;
  const now = new Date();

  type Acc = Omit<StrikeAggregateRow, "net_gex" | "cumulative_gex" | "call_avg_iv" | "put_avg_iv"> & {
    call_iv_sum: number;
    put_iv_sum: number;
    call_iv_count: number;
    put_iv_count: number;
  };
  const acc = new Map<number, Acc>();

  function ensure(strike: number): Acc {
    if (!acc.has(strike)) {
      acc.set(strike, {
        strike,
        call_gex: 0,
        put_gex: 0,
        call_oi: 0,
        put_oi: 0,
        call_vol: 0,
        put_vol: 0,
        call_premium: 0,
        put_premium: 0,
        call_dex: 0,
        put_dex: 0,
        call_charm: 0,
        put_charm: 0,
        call_iv_sum: 0,
        put_iv_sum: 0,
        call_iv_count: 0,
        put_iv_count: 0,
      });
    }
    return acc.get(strike)!;
  }

  function addContracts(contracts: MacroContract[], side: "call" | "put") {
    if (!contracts || contracts.length === 0) return;
    for (const contract of contracts) {
      if (!isInExpiryScope(contract.expiry, expiryScope, now)) continue;
      const strike = contract.strike ?? null;
      if (strike === null || !Number.isFinite(strike)) continue;

      const row = ensure(strike);
      const openInterest = contract.open_interest ?? 0;
      const volume = contract.volume ?? 0;
      const gamma = contract.gamma ?? 0;
      const delta = contract.delta ?? 0;
      const theta = contract.theta ?? 0;
      const iv = contract.iv;
      const mark = contract.mark ?? contract.last ?? 0;
      const gex = gamma * openInterest * spot * spot * 0.01;
      const dex = delta * openInterest * spot * 100;
      const charm = theta * openInterest * 100;
      const premium = mark * openInterest * 100;

      if (side === "call") {
        row.call_gex += gex;
        row.call_oi += openInterest;
        row.call_vol += volume;
        row.call_premium += premium;
        row.call_dex = (row.call_dex ?? 0) + dex;
        row.call_charm = (row.call_charm ?? 0) + charm;
        if (typeof iv === "number" && Number.isFinite(iv)) {
          row.call_iv_sum += iv;
          row.call_iv_count += 1;
        }
      } else {
        row.put_gex += gex;
        row.put_oi += openInterest;
        row.put_vol += volume;
        row.put_premium += premium;
        row.put_dex = (row.put_dex ?? 0) + dex;
        row.put_charm = (row.put_charm ?? 0) + charm;
        if (typeof iv === "number" && Number.isFinite(iv)) {
          row.put_iv_sum += iv;
          row.put_iv_count += 1;
        }
      }
    }
  }

  addContracts(snapshot.calls ?? [], "call");
  addContracts(snapshot.puts ?? [], "put");

  let cumulative = 0;
  return Array.from(acc.values())
    .sort((a, b) => a.strike - b.strike)
    .map((row) => {
      const net = row.call_gex - row.put_gex;
      cumulative += net;
      return {
        ...row,
        net_gex: net,
        cumulative_gex: cumulative,
        call_avg_iv: row.call_iv_count > 0 ? row.call_iv_sum / row.call_iv_count : null,
        put_avg_iv: row.put_iv_count > 0 ? row.put_iv_sum / row.put_iv_count : null,
      };
    });
}

function deriveGammaFlip(rows: StrikeAggregateRow[]): number | null {
  for (let i = 1; i < rows.length; i += 1) {
    const previous = rows[i - 1];
    const current = rows[i];
    if (previous.cumulative_gex === 0) return previous.strike;
    if ((previous.cumulative_gex > 0) !== (current.cumulative_gex > 0)) {
      const span = current.cumulative_gex - previous.cumulative_gex;
      if (span === 0) return (previous.strike + current.strike) / 2;
      const weight = Math.abs(previous.cumulative_gex) / Math.abs(span);
      return previous.strike + (current.strike - previous.strike) * weight;
    }
  }
  return null;
}

function deriveScoredWalls(rows: StrikeAggregateRow[], spot: number | null) {
  const resistanceWalls = rows
    .filter((row) => row.call_gex > 0 && (spot === null || row.strike >= spot))
    .sort((a, b) => b.call_gex - a.call_gex)
    .slice(0, 3)
    .map((row) => ({ level: row.strike, strike: row.strike, score: Math.round(row.call_gex), type: "call-wall" }));

  const supportWalls = rows
    .filter((row) => row.put_gex > 0 && (spot === null || row.strike <= spot))
    .sort((a, b) => b.put_gex - a.put_gex)
    .slice(0, 3)
    .map((row) => ({ level: row.strike, strike: row.strike, score: Math.round(row.put_gex), type: "put-wall" }));

  return { resistanceWalls, supportWalls };
}

function deriveLiveSnapshotMetrics(rows: StrikeAggregateRow[], spot: number | null) {
  const totalGex = rows.reduce((sum, row) => sum + row.net_gex, 0);
  const gammaFlip = deriveGammaFlip(rows);
  const strongestCall = rows.reduce<StrikeAggregateRow | null>((best, row) =>
    !best || row.call_gex > best.call_gex ? row : best,
  null);
  const strongestPut = rows.reduce<StrikeAggregateRow | null>((best, row) =>
    !best || row.put_gex > best.put_gex ? row : best,
  null);
  const pinStrike = rows.reduce<StrikeAggregateRow | null>((best, row) => {
    const score = row.call_oi + row.put_oi;
    const bestScore = best ? best.call_oi + best.put_oi : -1;
    return score > bestScore ? row : best;
  }, null);
  const gammaMagnet = rows.reduce<StrikeAggregateRow | null>((best, row) => {
    const rowDist = spot === null ? 0 : Math.abs(row.strike - spot);
    const bestDist = best && spot !== null ? Math.abs(best.strike - spot) : Number.POSITIVE_INFINITY;
    if (!best) return row;
    if (rowDist === bestDist) {
      return Math.abs(row.net_gex) > Math.abs(best.net_gex) ? row : best;
    }
    return rowDist < bestDist ? row : best;
  }, null);

  return {
    totalGex,
    gammaFlip,
    callWall: strongestCall?.strike ?? null,
    putWall: strongestPut?.strike ?? null,
    pinStrike: pinStrike?.strike ?? null,
    gammaMagnet: gammaMagnet?.strike ?? null,
    regime: totalGex < 0 ? "NEGATIVE" : totalGex > 0 ? "POSITIVE" : null,
    regimeLabel: totalGex < 0 ? "Negative Gamma" : totalGex > 0 ? "Positive Gamma" : null,
    directionalBias:
      totalGex < 0
        ? "Expansion risk"
        : totalGex > 0
          ? "Mean reversion bias"
          : null,
  };
}

type ByStrikeData = {
  implemented: true;
  module: "by-strike";
  symbol: string;
  filters: {
    strikes: number;
    expiryScope: string;
    metricFamily: string;
  };
  spot: number | null;
  rows: Array<Record<string, unknown>>;
};

type ByExpiryData = {
  implemented: true;
  module: "by-expiry";
  symbol: string;
  filters: {
    strikes: number;
    metricFamily: string;
  };
  rows: Array<Record<string, unknown>>;
};

type NarrativeData = {
  implemented: true;
  module: "narrative";
  symbol: string;
  runLabel: string | null;
  /** Data quality tier for this narrative, derived from the backing data source. */
  integrityTier: "Measured" | "Proxy" | "Low-Integrity";
  /** Human-readable label for the backing data source. */
  dataSourceLabel: string;
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
    scope: string;
    scopedNetGex: number | null;
    integrityTier: "Measured" | "Proxy" | "Low-Integrity";
    factors: Array<{ name: string; score: number }>;
  };
  perspectives: Array<{
    mode: "Scalper" | "Intraday" | "Swing";
    scope: "0dte" | "weekly" | "monthly";
    netGex: number | null;
    bias: "Expansion" | "Compression" | "Unavailable";
    /** Mode-specific weighted tactical quality score (0-100). */
    tacticalScore: number;
  }>;
  notes: {
    coach: string[];
    tactical: string[];
  };
};

type ExplainData = {
  implemented: true;
  module: "explain";
  symbol: string;
  snapshotId: string;
  sources: {
    pipelineStatePresent: boolean;
    dailyLevelsPresent: boolean;
  };
  inputs: Record<string, unknown>;
  rules: Array<{ name: string; description: string }>;
  outputs: Record<string, unknown>;
};

function toNum(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export async function buildSummary(symbol: string): Promise<{ data: SummaryData; warnings: string[] }> {
  const warnings: string[] = [];
  const [state, levels] = await Promise.all([loadPipelineState(), loadDailyLevels()]);

  const ticker = resolveTickerEntry(state, symbol);
  const structure = resolveDailyStructure(levels, symbol);
  const snapshotBundle = !ticker || !structure ? await loadOptionSnapshot(symbol) : null;
  const snapshotRows = snapshotBundle ? buildStrikeAggregatesFromSnapshot(snapshotBundle.snapshot) : [];
  const liveMetrics = snapshotBundle
    ? deriveLiveSnapshotMetrics(snapshotRows, snapshotBundle.snapshot.spot ?? null)
    : null;

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol; fallback used where available");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");
  if (snapshotBundle?.source === "live-chain") {
    warnings.push(`Using live option-chain fallback for ${symbol}; precomputed universe entry is unavailable.`);
  }

  const spot = toNum(ticker?.spot) ?? toNum(structure?.scored_analysis?.spot) ?? snapshotBundle?.snapshot.spot ?? null;

  return {
    data: {
      implemented: true,
      module: "summary",
      symbol,
      runLabel: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
      asOf: (state?.timestamp as string | undefined) ?? (levels?.generated_at as string | undefined) ?? null,
      spot,
      gex: {
        total: toNum(ticker?.total_gex) ?? toNum(structure?.total_gex) ?? liveMetrics?.totalGex ?? null,
        regime: (ticker?.gex_regime as string | undefined) ?? (structure?.gex_regime as string | undefined) ?? liveMetrics?.regime ?? null,
        regimeLabel: (ticker?.regime_label as string | undefined) ?? (structure?.regime_label as string | undefined) ?? liveMetrics?.regimeLabel ?? null,
        directionalBias: (ticker?.directional_bias as string | undefined) ?? liveMetrics?.directionalBias ?? null,
      },
      keyLevels: {
        gammaFlip: toNum(ticker?.zero_gamma) ?? liveMetrics?.gammaFlip ?? null,
        callWall: toNum(ticker?.call_wall) ?? liveMetrics?.callWall ?? null,
        putWall: toNum(ticker?.put_wall) ?? liveMetrics?.putWall ?? null,
        gammaMagnet: toNum(ticker?.gamma_magnet) ?? liveMetrics?.gammaMagnet ?? null,
        pinStrike: toNum(ticker?.pin_strike) ?? liveMetrics?.pinStrike ?? null,
      },
    },
    warnings,
  };
}

export async function buildLevels(symbol: string): Promise<{ data: LevelsData; warnings: string[] }> {
  const warnings: string[] = [];
  const [state, levels] = await Promise.all([loadPipelineState(), loadDailyLevels()]);

  const ticker = resolveTickerEntry(state, symbol);
  const structure = resolveDailyStructure(levels, symbol);
  const snapshotBundle = !ticker || !structure ? await loadOptionSnapshot(symbol) : null;
  const snapshotRows = snapshotBundle ? buildStrikeAggregatesFromSnapshot(snapshotBundle.snapshot) : [];
  const liveMetrics = snapshotBundle
    ? deriveLiveSnapshotMetrics(snapshotRows, snapshotBundle.snapshot.spot ?? null)
    : null;
  const derivedWalls = snapshotBundle ? deriveScoredWalls(snapshotRows, snapshotBundle.snapshot.spot ?? null) : null;

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");
  if (snapshotBundle?.source === "live-chain") {
    warnings.push(`Using live option-chain fallback for ${symbol}; scored walls and summary levels are derived on demand.`);
  }

  const scored = (structure?.scored_analysis as Record<string, unknown> | undefined) ?? {};
  const resistanceWalls =
    (scored.resistance_walls as Array<Record<string, unknown>> | undefined) ??
    derivedWalls?.resistanceWalls ??
    [];
  const supportWalls =
    (scored.support_walls as Array<Record<string, unknown>> | undefined) ??
    derivedWalls?.supportWalls ??
    [];

  const primaryCallWall = toNum(ticker?.call_wall) ?? liveMetrics?.callWall ?? null;
  const primaryPutWall = toNum(ticker?.put_wall) ?? liveMetrics?.putWall ?? null;
  const centroidCallWall = toNum((ticker as Record<string, unknown> | undefined)?.call_centroid);
  const centroidPutWall = toNum((ticker as Record<string, unknown> | undefined)?.put_centroid);
  const scoredCallWall = firstNumericLevel(resistanceWalls);
  const scoredPutWall = firstNumericLevel(supportWalls);

  const spot = toNum(ticker?.spot) ?? snapshotBundle?.snapshot.spot ?? null;
  const secondaryCallWall =
    scoredCallWall !== null && scoredCallWall !== primaryCallWall && isReasonableSecondaryLevel(scoredCallWall, spot)
      ? scoredCallWall
      : centroidCallWall !== null && centroidCallWall !== primaryCallWall && isReasonableSecondaryLevel(centroidCallWall, spot)
        ? centroidCallWall
        : null;
  const secondaryPutWall =
    scoredPutWall !== null && scoredPutWall !== primaryPutWall && isReasonableSecondaryLevel(scoredPutWall, spot)
      ? scoredPutWall
      : centroidPutWall !== null && centroidPutWall !== primaryPutWall && isReasonableSecondaryLevel(centroidPutWall, spot)
        ? centroidPutWall
        : null;

  const root = normalizeSymbolRoot(symbol);
  const protectedExpectedMoveRoots = new Set(["ES", "MES", "SPX", "SPY", "NQ", "MNQ", "NDX", "QQQ", "RTY", "M2K", "RUT", "IWM", "YM", "MYM", "DJI", "DIA"]);
  const dbExpectedMove = await loadExpectedMoveBandFromDb(symbol).catch(() => null);
  const structuredExpectedMove = structureSupportsExpectedMove(structure, symbol)
    ? resolveExpectedMoveFromStructure(structure, symbol, spot)
    : { lower: null, upper: null, width: null };
  const noteExpectedMove = parseExpectedMoveFromNotes((structure?.coach_note as string[] | undefined) ?? []);
  const snapshotExpectedMove = deriveExpectedMoveFromSnapshot(snapshotBundle?.snapshot, spot);
  const expectedMove = dbExpectedMove
    ? { lower: dbExpectedMove.lower, upper: dbExpectedMove.upper, width: dbExpectedMove.width }
    : structuredExpectedMove.width !== null
      ? structuredExpectedMove
    : snapshotExpectedMove.width !== null
      ? { lower: snapshotExpectedMove.lower, upper: snapshotExpectedMove.upper, width: snapshotExpectedMove.width }
    : protectedExpectedMoveRoots.has(root)
      ? { lower: null, upper: null, width: null }
      : noteExpectedMove;

  if (!dbExpectedMove && structuredExpectedMove.width === null && protectedExpectedMoveRoots.has(root)) {
    warnings.push(`Expected-move DB row not found for canonical ticker ${resolveExpectedMoveTicker(symbol)}; EM levels withheld to avoid cross-symbol scaling.`);
  }
  if (!dbExpectedMove && structuredExpectedMove.width === null && snapshotExpectedMove.width !== null) {
    warnings.push(`Expected move derived from live option snapshot (${snapshotExpectedMove.expiry ?? "nearest expiry"}) because EM cache is unavailable for ${symbol}.`);
  }

  return {
    data: {
      implemented: true,
      module: "levels",
      symbol,
      runLabel: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
      spot: toNum(ticker?.spot),
      levels: {
        spot,
        gammaFlip: toNum(ticker?.zero_gamma) ?? liveMetrics?.gammaFlip ?? null,
        callWall: primaryCallWall,
        secondaryCallWall,
        putWall: primaryPutWall,
        secondaryPutWall,
        gammaMagnet: toNum(ticker?.gamma_magnet) ?? liveMetrics?.gammaMagnet ?? null,
        pinStrike: toNum(ticker?.pin_strike) ?? liveMetrics?.pinStrike ?? null,
        expectedMoveUpper: expectedMove.upper,
        expectedMoveLower: expectedMove.lower,
        expectedMoveWidth: expectedMove.width,
      },
      scored: {
        resistanceWalls,
        supportWalls,
        pivots: (scored.pivots as Array<Record<string, unknown>> | undefined) ?? [],
      },
      notes: (() => {
        const preCoach = (structure?.coach_note as string[] | undefined) ?? [];
        const preTactical = (structure?.tactical_plan as string[] | undefined) ?? [];
        const synth = preCoach.length === 0
          ? synthesizeCoachNotes(
              symbol, spot, primaryCallWall, primaryPutWall,
              toNum(ticker?.zero_gamma) ?? liveMetrics?.gammaFlip ?? null,
              ticker?.gex_regime as string | undefined,
              ticker?.directional_bias as string | undefined,
              expectedMove, []
            )
          : null;
        const liveChainNote = snapshotBundle?.source === "live-chain"
          ? "Live chain fallback active; levels are synthesized from the current option snapshot."
          : null;
        return {
          coach: synth ? synth.coach : preCoach,
          tactical: preTactical.length > 0
            ? preTactical
            : synth
              ? (liveChainNote ? [liveChainNote, ...synth.tactical] : synth.tactical)
              : (liveChainNote ? [liveChainNote] : []),
        };
      })(),
    },
    warnings,
  };
}

export async function buildByStrike(
  symbol: string,
  strikes: number,
  expiryScope: string,
  metricFamily: string
): Promise<{ data: ByStrikeData; warnings: string[] }> {
  const warnings: string[] = [];
  const [profiles, state] = await Promise.all([loadGexProfiles(), loadPipelineState()]);

  if (expiryScope !== "all") {
    warnings.push(
      `By-strike rows are sourced from consolidated gex_profiles; expiry scope '${expiryScope}' is informational only.`
    );
  }

  let rows = resolveProfileRows(profiles, symbol)
    .map((row) => {
      const callAvgIv = toNum((row as Record<string, unknown>).call_avg_iv) ?? toNum((row as Record<string, unknown>).call_iv);
      const putAvgIv = toNum((row as Record<string, unknown>).put_avg_iv) ?? toNum((row as Record<string, unknown>).put_iv);
      return {
        ...row,
        call_avg_iv: callAvgIv,
        put_avg_iv: putAvgIv,
      };
    })
    .sort((a, b) => Number(a.strike ?? 0) - Number(b.strike ?? 0));

  const ticker = resolveTickerEntry(state, symbol);
  let spot = toNum(ticker?.spot);

  if (!rows.length) {
    const snapshotBundle = await loadOptionSnapshot(symbol).catch(() => null);
    if (snapshotBundle) {
      rows = buildStrikeAggregatesFromSnapshot(snapshotBundle.snapshot, expiryScope).map((row) => ({
        strike: row.strike,
        call_gex: Math.round(row.call_gex),
        put_gex: Math.round(row.put_gex),
        net_gex: Math.round(row.net_gex),
        cumulative_gex: Math.round(row.cumulative_gex),
        call_oi: row.call_oi,
        put_oi: row.put_oi,
        call_vol: row.call_vol,
        put_vol: row.put_vol,
        call_premium: Math.round(row.call_premium),
        put_premium: Math.round(row.put_premium),
        call_dex: row.call_dex !== null ? Math.round(row.call_dex) : null,
        put_dex: row.put_dex !== null ? Math.round(row.put_dex) : null,
        call_charm: row.call_charm !== null ? Math.round(row.call_charm) : null,
        put_charm: row.put_charm !== null ? Math.round(row.put_charm) : null,
        call_avg_iv: row.call_avg_iv,
        put_avg_iv: row.put_avg_iv,
      }));
      spot = snapshotBundle.snapshot.spot ?? spot;
      warnings.push(`No gex_profiles rows found for ${symbol}; using ${snapshotBundle.source} strike aggregates.`);
    } else {
      warnings.push("No strike profile rows found for symbol");
    }
  }

  let filtered = rows;
  if (rows.length > 0 && spot !== null) {
    let nearestIdx = 0;
    let nearestDist = Number.POSITIVE_INFINITY;

    for (let i = 0; i < rows.length; i += 1) {
      const strike = Number(rows[i].strike ?? 0);
      const dist = Math.abs(strike - spot);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = i;
      }
    }

    const start = Math.max(0, nearestIdx - strikes);
    const end = Math.min(rows.length, nearestIdx + strikes + 1);
    filtered = rows.slice(start, end);
  }

  return {
    data: {
      implemented: true,
      module: "by-strike",
      symbol,
      filters: { strikes, expiryScope, metricFamily },
      spot,
      rows: filtered,
    },
    warnings,
  };
}

export async function buildByExpiry(
  symbol: string,
  strikes: number,
  metricFamily: string
): Promise<{ data: ByExpiryData; warnings: string[] }> {
  const warnings: string[] = [];
  const [levels, state] = await Promise.all([loadDailyLevels(), loadPipelineState()]);

  const structure = resolveDailyStructure(levels, symbol);
  const ticker = resolveTickerEntry(state, symbol);

  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const expectedMoves = (structure?.expected_moves as Array<Record<string, unknown>> | undefined) ?? [];
  const rows = expectedMoves.map((entry) => ({
    expiry: entry.expiry ?? null,
    dte: entry.dte ?? null,
    em_upper: entry.em_upper ?? null,
    em_lower: entry.em_lower ?? null,
    em_value: entry.em_value ?? null,
    straddle: entry.straddle ?? null,
    spot: toNum(ticker?.spot),
  }));

  if (!rows.length) {
    warnings.push("No expected-move expiry rows found for symbol");
  }
  warnings.push("Expiry-level GEX aggregation is pending; current rows are sourced from expected-move data");

  return {
    data: {
      implemented: true,
      module: "by-expiry",
      symbol,
      filters: { strikes, metricFamily },
      rows,
    },
    warnings,
  };
}

function calcDistancePct(level: number | null, spot: number | null): number | null {
  if (level === null || spot === null || spot === 0) return null;
  return ((level - spot) / spot) * 100;
}

function bucketScore(score: number): "POSSIBLE" | "LIKELY" | "IMMINENT" {
  if (score >= 70) return "IMMINENT";
  if (score >= 50) return "LIKELY";
  return "POSSIBLE";
}

/**
 * Synthesize coach + tactical notes from live market data when a ticker has no
 * precomputed coach_note / tactical_plan in the daily-levels JSON.  Produces
 * human-readable context lines that mirror the style of hand-written notes so
 * the notes panel is never empty for a valid ticker.
 */
function synthesizeCoachNotes(
  symbol: string,
  spot: number | null,
  callWall: number | null,
  putWall: number | null,
  gammaFlip: number | null,
  regime: string | undefined,
  bias: string | undefined,
  em: { lower: number | null; upper: number | null; width: number | null },
  perspectives: Array<{ mode: string; scope: string; netGex: number | null; bias: string; tacticalScore: number }>
): { coach: string[]; tactical: string[] } {
  const fmt = (v: number | null, d = 2) =>
    v !== null ? `$${v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d })}` : "N/A";
  const fmtPct = (v: number | null) => (v !== null ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` : "N/A");

  const isNeg = regime === "NEGATIVE";
  const biasLabel = bias ?? (isNeg ? "Expansion" : "Compression");
  const regimeDesc = isNeg
    ? "negative gamma (short-gamma regime — dealers amplify moves)"
    : "positive gamma (dealers dampen moves, favoring mean-reversion)";

  const callDist = calcDistancePct(callWall, spot);
  const putDist = calcDistancePct(putWall, spot);
  const flipDist = calcDistancePct(gammaFlip, spot);

  const coach: string[] = [];

  // Line 1: spot + walls context
  if (spot !== null) {
    const wallContext =
      callWall !== null && putWall !== null
        ? `Call wall overhead at ${fmt(callWall)} (${fmtPct(callDist)}), put wall below at ${fmt(putWall)} (${fmtPct(putDist)}).`
        : callWall !== null
          ? `Call wall at ${fmt(callWall)} (${fmtPct(callDist)}).`
          : putWall !== null
            ? `Put wall at ${fmt(putWall)} (${fmtPct(putDist)}).`
            : "Key walls not yet resolved.";
    coach.push(`${symbol} trading at ${fmt(spot)} in a ${regimeDesc}. ${wallContext}`);
  }

  // Line 2: gamma flip context
  if (gammaFlip !== null && spot !== null) {
    const side = spot > gammaFlip ? "above" : "below";
    const implication =
      spot > gammaFlip
        ? "Dealer hedging flows should support upward continuation above the flip."
        : "Price is below the flip — dealer hedging flows may amplify downside.";
    coach.push(`Gamma flip at ${fmt(gammaFlip)} (${fmtPct(flipDist)}). Spot is ${side} the flip. ${implication}`);
  }

  // Line 3: EM + bias context
  if (em.width !== null) {
    const emBound =
      em.lower !== null && em.upper !== null
        ? `Expected-move band: ${fmt(em.lower)} – ${fmt(em.upper)} (±${fmt(em.width, 2)}).`
        : `Expected-move width: ±${fmt(em.width, 2)}.`;
    coach.push(`${emBound} Directional bias: ${biasLabel}. Treat levels as live-derived until next precomputed run.`);
  } else {
    coach.push(`Directional bias: ${biasLabel}. No expected-move band available — use walls as range boundaries.`);
  }

  // Tactical: one line per mode perspective
  const tactical: string[] = [];
  for (const p of perspectives) {
    if (p.netGex === null) {
      tactical.push(`${p.mode} (${p.scope.toUpperCase()}): GEX data unavailable — no tactical read.`);
    } else {
      const dirHint =
        p.bias === "Expansion"
          ? "directional bias — momentum setups preferred"
          : "compression bias — fade breakouts, target mean-reversion";
      tactical.push(
        `${p.mode} (${p.scope.toUpperCase()}): net GEX ${Math.round(p.netGex).toLocaleString()} (${p.bias}) | score ${p.tacticalScore}/100 — ${dirHint}.`
      );
    }
  }

  return { coach, tactical };
}

/**
 * Compute a mode-specific tactical quality score (0–100) by weighting regime,
 * wall proximity, and net-GEX signal strength differently per trading mode.
 *
 *  Scalper  — proximity-heavy (scalpers live near pinch points)
 *  Intraday — balanced
 *  Swing    — regime+flow-heavy (directional clarity matters more than proximity)
 */
function computeTacticalScore(
  mode: "Scalper" | "Intraday" | "Swing",
  netGex: number | null,
  totalGex: number | null,
  isNegativeRegime: boolean,
  callWallDistPct: number | null,
  putWallDistPct: number | null
): number {
  const weights =
    mode === "Scalper"
      ? { regime: 20, proximity: 45, flow: 35 }
      : mode === "Intraday"
        ? { regime: 35, proximity: 30, flow: 35 }
        : { regime: 40, proximity: 15, flow: 45 }; // Swing

  // Regime: negative GEX = amplified moves — universally meaningful but weighted by mode
  const regimeScore = isNegativeRegime ? 1.0 : 0.35;

  // Proximity: how close is spot to the nearest wall (lower distance = higher pinch pressure)
  const minDistAbs = Math.min(
    Math.abs(callWallDistPct ?? 100),
    Math.abs(putWallDistPct ?? 100)
  );
  // Full score within 0 %, zero score at ≥ 6 % away
  const proximityScore = Math.max(0, 1 - minDistAbs / 6);

  // Flow signal: magnitude of net GEX as share of total GEX
  let flowScore = 0;
  if (netGex !== null && totalGex !== null && totalGex !== 0) {
    flowScore = Math.min(1, Math.abs(netGex / totalGex) * 2.5);
  } else if (netGex !== null && netGex !== 0) {
    flowScore = 0.4;
  }

  const raw =
    regimeScore * weights.regime +
    proximityScore * weights.proximity +
    flowScore * weights.flow;

  return Math.round(Math.min(100, raw));
}

export async function buildNarrative(
  symbol: string,
  expiryScope = "all"
): Promise<{ data: NarrativeData; warnings: string[] }> {
  const warnings: string[] = [];
  const [state, levels] = await Promise.all([loadPipelineState(), loadDailyLevels()]);

  const ticker = resolveTickerEntry(state, symbol);
  const structure = resolveDailyStructure(levels, symbol);

  // When ticker is absent (ad-hoc / new symbol), load a live snapshot so that
  // spot + walls are available for the synthesized coach notes and signal distances.
  const narrativeSnapshot = !ticker ? await loadOptionSnapshot(symbol).catch(() => null) : null;
  const narrativeSnapshotRows = narrativeSnapshot
    ? buildStrikeAggregatesFromSnapshot(narrativeSnapshot.snapshot)
    : [];
  const narrativeLiveMetrics = narrativeSnapshot
    ? deriveLiveSnapshotMetrics(narrativeSnapshotRows, narrativeSnapshot.snapshot.spot ?? null)
    : null;

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const spot = toNum(ticker?.spot) ?? narrativeSnapshot?.snapshot.spot ?? null;
  const callWall = toNum(ticker?.call_wall) ?? narrativeLiveMetrics?.callWall ?? null;
  const putWall = toNum(ticker?.put_wall) ?? narrativeLiveMetrics?.putWall ?? null;
  const zeroGamma = toNum(ticker?.zero_gamma) ?? narrativeLiveMetrics?.gammaFlip ?? null;
  const sessionDelta = toNum(structure?.total_gex_delta_adj);
  const totalGex = toNum(ticker?.total_gex) ?? toNum(structure?.total_gex);
  const sessionPct =
    sessionDelta !== null && totalGex !== null && totalGex !== 0 ? (sessionDelta / totalGex) * 100 : null;

  const scopeData = await buildByExpiryTrue(symbol, 20, "gamma", expiryScope).catch(() => null);
  const scopedNetGex = scopeData
    ? scopeData.data.rows.reduce((sum, row) => sum + (toNum((row as Record<string, unknown>).net_gex) ?? 0), 0)
    : null;

  const perspectiveDefs = [
    { mode: "Scalper" as const, scope: "0dte" as const },
    { mode: "Intraday" as const, scope: "weekly" as const },
    { mode: "Swing" as const, scope: "monthly" as const },
  ];
  const perspectiveData = await Promise.all(
    perspectiveDefs.map(async (def) => {
      const result = await buildByExpiryTrue(symbol, 20, "gamma", def.scope).catch(() => null);
      const net = result
        ? result.data.rows.reduce((sum, row) => sum + (toNum((row as Record<string, unknown>).net_gex) ?? 0), 0)
        : null;
      const tacticalScore = computeTacticalScore(
        def.mode,
        net,
        totalGex,
        ticker?.gex_regime === "NEGATIVE",
        calcDistancePct(callWall, spot),
        calcDistancePct(putWall, spot)
      );
      return {
        mode: def.mode,
        scope: def.scope,
        netGex: net,
        bias: (net === null ? "Unavailable" : net < 0 ? "Expansion" : "Compression") as "Expansion" | "Compression" | "Unavailable",
        tacticalScore,
      };
    })
  );

  // ── Integrity tier: derived from the backing data source ─────────────────
  const rawSource = scopeData?.data?.dataSource ?? "expected-moves";
  const integrityTier: "Measured" | "Proxy" | "Low-Integrity" =
    rawSource === "macro-cache"
      ? "Measured"
      : rawSource === "dolt"
        ? "Proxy"
        : "Low-Integrity";
  const dataSourceLabel =
    rawSource === "macro-cache"
      ? `Macro cache (${scopeData?.data?.cacheDate ?? "?"})`
      : rawSource === "dolt"
        ? `Dolt DB (gamma sums — no OI)`
        : "Expected-move fallback";

  const scopeLabelMap: Record<string, string> = {
    all: "Full Curve",
    "0dte": "0DTE",
    weekly: "Weekly",
    monthly: "Monthly",
  };
  const scopeLabel = scopeLabelMap[expiryScope] ?? expiryScope.toUpperCase();

  if (!scopeData || scopeData.data.rows.length === 0) {
    warnings.push(`No scoped expiry rows available for narrative scope '${expiryScope}'`);
  }

  const factors = [
    { name: "Gamma Regime", score: ticker?.gex_regime === "NEGATIVE" ? 25 : 10 },
    { name: "Call Wall Proximity", score: Math.max(0, 20 - Math.abs(calcDistancePct(callWall, spot) ?? 20)) },
    {
      name: `${scopeLabel} Net GEX`,
      score:
        scopedNetGex === null
          ? 5
          : scopedNetGex < 0
            ? 20
            : 8,
    },
    { name: "Flow Alignment", score: 10 },
    { name: "Volume Confirm", score: 5 },
    { name: "DEX Bias", score: 5 },
  ];
  const probabilityScore = Math.round(factors.reduce((sum, f) => sum + f.score, 0));

  const setupBase = ticker?.gex_regime === "NEGATIVE" ? "Bullish Squeeze" : "Vol Compression";
  const setup = `${setupBase} (${scopeLabel})`;

  // ── Tier-aware signal wording ─────────────────────────────────────────────
  const tierQualifier =
    integrityTier === "Measured"
      ? ""
      : integrityTier === "Proxy"
        ? " (gamma-sum proxy — treat as directional, not magnitude)"
        : " (expected-move estimate — limited confidence)";

  const scopeMessage =
    scopedNetGex === null
      ? `${scopeLabel} lens: scoped net GEX unavailable.`
      : `${scopeLabel} lens: scoped net GEX ${scopedNetGex >= 0 ? "supports mean reversion" : "warns of expansion"}${tierQualifier}.`;

  const volSignalBase =
    ticker?.gex_regime === "NEGATIVE"
      ? "Short gamma regime can amplify directional price movement."
      : "Regime currently favors more contained movement.";
  const volSignalMsg =
    integrityTier === "Measured"
      ? `${volSignalBase} ${scopeMessage}`
      : integrityTier === "Proxy"
        ? `${volSignalBase} Gamma-sum proxy suggests similar dynamics; verify with live OI. ${scopeMessage}`
        : `${volSignalBase} Using expected-move estimates — regime read has reduced confidence. ${scopeMessage}`;

  const tacticalScoped = [
    `${scopeLabel} mode active for narrative scoring and signal framing (${integrityTier} — ${dataSourceLabel}).`,
    scopedNetGex === null
      ? `${scopeLabel} scoped net GEX could not be computed from current source data.`
      : `${scopeLabel} scoped net GEX = ${Math.round(scopedNetGex).toLocaleString()}.`,
    ...perspectiveData.map((p) =>
      p.netGex === null
        ? `${p.mode} (${p.scope.toUpperCase()}): data unavailable.`
        : `${p.mode} (${p.scope.toUpperCase()}): ${Math.round(p.netGex).toLocaleString()} (${p.bias}) — tactical score ${p.tacticalScore}/100.`
    ),
  ];

  return {
    data: {
      implemented: true,
      module: "narrative",
      symbol,
      runLabel: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
      integrityTier,
      dataSourceLabel,
      intradayDelta: {
        session: sessionDelta,
        sessionPct,
        recent: null,
        snapshotCount: 1,
      },
      signals: [
        {
          type: "volatility",
          severity: ticker?.gex_regime === "NEGATIVE" ? "STRONG" : "MODERATE",
          message: volSignalMsg,
          level: zeroGamma,
          distancePct: calcDistancePct(zeroGamma, spot),
        },
        {
          type: "resistance",
          severity: "MODERATE",
          message: `Call wall can act as resistance if approached from below (${scopeLabel} context${tierQualifier}).`,
          level: callWall,
          distancePct: calcDistancePct(callWall, spot),
        },
        {
          type: "support",
          severity: "MODERATE",
          message: `Put wall can act as support if approached from above (${scopeLabel} context${tierQualifier}).`,
          level: putWall,
          distancePct: calcDistancePct(putWall, spot),
        },
      ],
      screener: {
        setup,
        probabilityScore,
        confidence: bucketScore(probabilityScore),
        scope: expiryScope,
        scopedNetGex,
        integrityTier,
        factors,
      },
      perspectives: perspectiveData,
      notes: (() => {
        const preCoach = (structure?.coach_note as string[] | undefined) ?? [];
        const preTactical = (structure?.tactical_plan as string[] | undefined) ?? [];
        const synth = preCoach.length === 0
          ? synthesizeCoachNotes(
              symbol, spot, callWall, putWall, zeroGamma,
              ticker?.gex_regime as string | undefined,
              ticker?.directional_bias as string | undefined,
              { lower: null, upper: null, width: null },
              perspectiveData
            )
          : null;
        return {
          coach: synth ? synth.coach : preCoach,
          tactical: [
            ...tacticalScoped,
            ...(preTactical.length > 0 ? preTactical : (synth?.tactical ?? [])),
          ],
        };
      })(),
    },
    warnings,
  };
}

export async function buildExplain(
  symbol: string,
  snapshotId: string
): Promise<{ data: ExplainData; warnings: string[] }> {
  const warnings: string[] = [];
  const [state, levels] = await Promise.all([loadPipelineState(), loadDailyLevels()]);

  const ticker = resolveTickerEntry(state, symbol);
  const structure = resolveDailyStructure(levels, symbol);

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const outputs = {
    spot: toNum(ticker?.spot),
    total_gex: toNum(ticker?.total_gex) ?? toNum(structure?.total_gex),
    gamma_flip: toNum(ticker?.zero_gamma),
    call_wall: toNum(ticker?.call_wall),
    put_wall: toNum(ticker?.put_wall),
  };

  return {
    data: {
      implemented: true,
      module: "explain",
      symbol,
      snapshotId,
      sources: {
        pipelineStatePresent: Boolean(state),
        dailyLevelsPresent: Boolean(levels),
      },
      inputs: {
        run_label: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
        ticker,
        structure,
      },
      rules: [
        {
          name: "gamma_regime_interpretation",
          description: "NEGATIVE GEX implies short-gamma conditions and potentially amplified movement.",
        },
        {
          name: "wall_proximity",
          description: "Distance to call/put walls is used to contextualize resistance/support risk zones.",
        },
      ],
      outputs,
    },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// buildByExpiryTrue  — macro cache (primary) → Dolt (fallback) → expected moves
// ---------------------------------------------------------------------------

type ByExpiryTrueData = {
  implemented: true;
  module: "by-expiry";
  symbol: string;
  dataSource: "macro-cache" | "dolt" | "expected-moves";
  cacheDate: string | null;
  filters: { strikes: number; metricFamily: string; expiryScope: string };
  rows: Array<Record<string, unknown>>;
};

function isThirdFriday(date: Date): boolean {
  const day = date.getUTCDay();
  const dom = date.getUTCDate();
  return day === 5 && dom >= 15 && dom <= 21;
}

function isInExpiryScope(expiry: string | undefined, scope: string, now: Date): boolean {
  if (!expiry || scope === "all") return true;
  const dt = new Date(expiry);
  if (Number.isNaN(dt.getTime())) return false;
  const dte = Math.max(0, Math.round((dt.getTime() - now.getTime()) / 86_400_000));
  if (scope === "0dte") return dte === 0;
  if (scope === "monthly") return isThirdFriday(dt);
  if (scope === "weekly") return dte > 0 && !isThirdFriday(dt);
  return true;
}

export async function buildByExpiryTrue(
  symbol: string,
  strikes: number,
  metricFamily: string,
  expiryScope = "all"
): Promise<{ data: ByExpiryTrueData; warnings: string[] }> {
  const warnings: string[] = [];

  // ── 1. Macro cache (true GEX = gamma × OI × spot² × 0.01) ──────────────
  const snapshotBundle = await loadOptionSnapshot(symbol).catch(() => null);

  if (snapshotBundle && ((snapshotBundle.snapshot.calls?.length ?? 0) > 0 || (snapshotBundle.snapshot.puts?.length ?? 0) > 0)) {
    const spot = snapshotBundle.snapshot.spot ?? 1;
    const now = new Date();

    type Acc = {
      expiry: string;
      call_gex: number;
      put_gex: number;
      call_oi: number;
      put_oi: number;
      call_vol: number;
      put_vol: number;
      call_delta_sum: number;
      put_delta_sum: number;
      call_iv_sum: number;
      put_iv_sum: number;
      call_count: number;
      put_count: number;
    };

    const acc = new Map<string, Acc>();

    function processContracts(contracts: MacroContract[], side: "call" | "put") {
      if (!contracts || contracts.length === 0) return;
      for (const c of contracts) {
        if (!c.expiry) continue;
        if (!isInExpiryScope(c.expiry, expiryScope, now)) continue;
        // Standard GEX formula: γ × OI × S² × 0.01
        const gex = (c.gamma ?? 0) * (c.open_interest ?? 0) * spot * spot * 0.01;
        if (!acc.has(c.expiry)) {
          acc.set(c.expiry, {
            expiry: c.expiry,
            call_gex: 0, put_gex: 0,
            call_oi: 0, put_oi: 0,
            call_vol: 0, put_vol: 0,
            call_delta_sum: 0, put_delta_sum: 0,
            call_iv_sum: 0, put_iv_sum: 0,
            call_count: 0, put_count: 0,
          });
        }
        const row = acc.get(c.expiry)!;
        if (side === "call") {
          row.call_gex += gex;
          row.call_oi += c.open_interest ?? 0;
          row.call_vol += c.volume ?? 0;
          row.call_delta_sum += c.delta ?? 0;
          row.call_iv_sum += c.iv ?? 0;
          row.call_count += 1;
        } else {
          row.put_gex += gex;
          row.put_oi += c.open_interest ?? 0;
          row.put_vol += c.volume ?? 0;
          row.put_delta_sum += c.delta ?? 0;
          row.put_iv_sum += c.iv ?? 0;
          row.put_count += 1;
        }
      }
    }

    processContracts(snapshotBundle.snapshot.calls ?? [], "call");
    processContracts(snapshotBundle.snapshot.puts ?? [], "put");

    const rows = Array.from(acc.values())
      .map((r) => {
        const expiryDate = new Date(r.expiry);
        const dte = Math.max(0, Math.round((expiryDate.getTime() - now.getTime()) / 86_400_000));
        return {
          expiry: r.expiry,
          dte,
          call_gex: Math.round(r.call_gex),
          put_gex: Math.round(r.put_gex),
          net_gex: Math.round(r.call_gex - r.put_gex),
          call_oi: r.call_oi,
          put_oi: r.put_oi,
          call_vol: r.call_vol,
          put_vol: r.put_vol,
          call_avg_iv: r.call_count > 0 ? Math.round((r.call_iv_sum / r.call_count) * 10000) / 10000 : null,
          put_avg_iv: r.put_count > 0 ? Math.round((r.put_iv_sum / r.put_count) * 10000) / 10000 : null,
        };
      })
      .sort((a, b) => a.dte - b.dte);

    warnings.push(
      snapshotBundle.source === "macro-cache"
        ? `Expiry GEX from macro cache (${snapshotBundle.snapshot._sym}, ${snapshotBundle.snapshot._date}, scope=${expiryScope}): ${snapshotBundle.snapshot.calls?.length ?? 0} calls, ${snapshotBundle.snapshot.puts?.length ?? 0} puts`
        : `Expiry GEX from live option chain (${snapshotBundle.snapshot._sym}, ${snapshotBundle.snapshot._date}, scope=${expiryScope}): ${snapshotBundle.snapshot.calls?.length ?? 0} calls, ${snapshotBundle.snapshot.puts?.length ?? 0} puts`
    );

    return {
      data: {
        implemented: true,
        module: "by-expiry",
        symbol,
        dataSource: "macro-cache",
        cacheDate: snapshotBundle.snapshot._date,
        filters: { strikes, metricFamily, expiryScope },
        rows,
      },
      warnings,
    };
  }

  // ── 2. Dolt historical (gamma sums only — no OI) ─────────────────────────
  const dolt = await queryDoltByExpiry(symbol).catch(() => null);

  if (dolt && dolt.rows.length > 0) {
    warnings.push(
      `Expiry data from Dolt DB (${dolt.resolvedSymbol}, ${dolt.date}). ` +
        "Dolt option_chain has no open_interest — values are gamma sums, not proper GEX."
    );

    const now = new Date();
    const rows = dolt.rows
      .filter((r) => isInExpiryScope(r.expiry, expiryScope, now))
      .map((r) => ({
      expiry: r.expiry,
      dte: r.dte,
      call_gex: r.call_gamma_sum,   // labelled gex but is actually gamma sum
      put_gex: r.put_gamma_sum,
      net_gex: r.net_gamma_sum,
      call_oi: null,
      put_oi: null,
      call_contracts: r.call_contracts,
      put_contracts: r.put_contracts,
      call_avg_iv: r.call_avg_iv,
      put_avg_iv: r.put_avg_iv,
    }));

    return {
      data: {
        implemented: true,
        module: "by-expiry",
        symbol,
        dataSource: "dolt",
        cacheDate: dolt.date,
        filters: { strikes, metricFamily, expiryScope },
        rows,
      },
      warnings,
    };
  }

  // ── 3. Expected-moves fallback ────────────────────────────────────────────
  warnings.push("Macro cache and Dolt unavailable — falling back to expected-move data");
  if (expiryScope !== "all") {
    warnings.push(`Expiry scope '${expiryScope}' cannot be strictly enforced in expected-moves fallback`);
  }
  const fallback = await buildByExpiry(symbol, strikes, metricFamily);
  return {
    data: {
      ...fallback.data,
      dataSource: "expected-moves" as const,
      cacheDate: null,
      filters: { strikes, metricFamily, expiryScope },
    },
    warnings: [...warnings, ...fallback.warnings],
  };
}

// ---------------------------------------------------------------------------
// buildRecentFlow  — macro cache contract anomalies as flow proxy
// ---------------------------------------------------------------------------

type RecentFlowData = {
  implemented: true;
  module: "recent-flow";
  symbol: string;
  /** Macro cache snapshot date used as the data source. */
  cacheDate: string | null;
  dataSource: "macro-cache-proxy";
  flowDelayMs: null;
  flowRegime: string;
  limit: number;
  rows: Array<{
    strike: number;
    expiry: string;
    type: "call" | "put";
    volume: number;
    oi: number;
    gamma: number;
    iv: number | null;
    mark: number | null;
    dte: number | null;
    /** Composite score = |gamma| × volume × sqrt(OI) — used for ranking. */
    score: number;
  }>;
};

export async function buildRecentFlow(
  symbol: string,
  limit: number
): Promise<{ data: RecentFlowData; warnings: string[] }> {
  const warnings: string[] = [];

  const snapshotBundle = await loadOptionSnapshot(symbol).catch(() => null);
  const macro = snapshotBundle?.snapshot ?? null;

  if (!macro || ((macro.calls?.length ?? 0) === 0 && (macro.puts?.length ?? 0) === 0)) {
    warnings.push("Macro cache not found for symbol; no flow data available");
    return {
      data: {
        implemented: true,
        module: "recent-flow",
        symbol,
        cacheDate: null,
        dataSource: "macro-cache-proxy",
        flowDelayMs: null,
        flowRegime: "neutral",
        limit,
        rows: [],
      },
      warnings,
    };
  }

  warnings.push(
    `${snapshotBundle?.source === "live-chain" ? "Live chain" : "Macro cache"} flow proxy (${macro._sym}, ${macro._date}). ` +
      "This is NOT a real-time flow feed — it ranks contracts by |gamma|×volume×√OI."
  );

  type ContractRow = {
    strike: number;
    expiry: string;
    type: "call" | "put";
    volume: number;
    oi: number;
    gamma: number;
    iv: number | null;
    mark: number | null;
    dte: number | null;
    score: number;
  };

  function rankContracts(contracts: MacroContract[], side: "call" | "put"): ContractRow[] {
    if (!contracts || contracts.length === 0) return [];
    return contracts
      .filter((c) => (c.volume ?? 0) > 0 && (c.gamma ?? 0) !== 0)
      .map((c) => {
        const volume = c.volume ?? 0;
        const oi = c.open_interest ?? 0;
        const gamma = c.gamma ?? 0;
        const score = Math.abs(gamma) * volume * Math.sqrt(Math.max(oi, 1));
        return {
          strike: c.strike ?? 0,
          expiry: c.expiry ?? "",
          type: side,
          volume,
          oi,
          gamma,
          iv: c.iv ?? null,
          mark: c.mark ?? null,
          dte: c.dte ?? null,
          score,
        };
      });
  }

  const allRows: ContractRow[] = [
    ...rankContracts(macro.calls ?? [], "call"),
    ...rankContracts(macro.puts ?? [], "put"),
  ];

  allRows.sort((a, b) => b.score - a.score);
  const rows = allRows.slice(0, limit);

  // Derive a simple flow regime from call vs put dominance in top rows
  const topN = rows.slice(0, Math.min(20, rows.length));
  const callScore = topN.filter((r) => r.type === "call").reduce((s, r) => s + r.score, 0);
  const putScore = topN.filter((r) => r.type === "put").reduce((s, r) => s + r.score, 0);
  const flowRegime =
    callScore > putScore * 1.5 ? "call-dominant" : putScore > callScore * 1.5 ? "put-dominant" : "neutral";

  return {
    data: {
      implemented: true,
      module: "recent-flow",
      symbol,
      cacheDate: macro._date,
      dataSource: "macro-cache-proxy",
      flowDelayMs: null,
      flowRegime,
      limit,
      rows,
    },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// buildSpotGamma  — net GEX profile curve from gex_profiles
// ---------------------------------------------------------------------------

type SpotGammaRow = {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  cumulative_gex: number;
  call_dex: number | null;
  put_dex: number | null;
  call_charm: number | null;
  put_charm: number | null;
};

type SpotGammaData = {
  implemented: true;
  module: "spot-gamma";
  symbol: string;
  spot: number | null;
  smooth: number;
  current: {
    net_gex: number | null;
    call_gex: number | null;
    put_gex: number | null;
    cumulative_gex: number | null;
    atm_strike: number | null;
  } | null;
  series: SpotGammaRow[];
};

export async function buildSpotGamma(
  symbol: string,
  smooth: number
): Promise<{ data: SpotGammaData; warnings: string[] }> {
  const warnings: string[] = [];
  const [profiles, state] = await Promise.all([loadGexProfiles(), loadPipelineState()]);

  let rawRows = resolveProfileRows(profiles, symbol)
    .map((r) => ({
      strike: Number(r.strike ?? 0),
      call_gex: Number(r.call_gex ?? 0),
      put_gex: Number(r.put_gex ?? 0),
      net_gex: Number(r.net_gex ?? 0),
      cumulative_gex: Number(r.cumulative_gex ?? 0),
      call_dex: r.call_dex != null ? Number(r.call_dex) : null,
      put_dex: r.put_dex != null ? Number(r.put_dex) : null,
      call_charm: r.call_charm != null ? Number(r.call_charm) : null,
      put_charm: r.put_charm != null ? Number(r.put_charm) : null,
    }))
    .sort((a, b) => a.strike - b.strike);

  const ticker = resolveTickerEntry(state, symbol);
  let spot = toNum(ticker?.spot);

  if (!rawRows.length) {
    const snapshotBundle = await loadOptionSnapshot(symbol).catch(() => null);
    if (snapshotBundle) {
      rawRows = buildStrikeAggregatesFromSnapshot(snapshotBundle.snapshot).map((row) => ({
        strike: row.strike,
        call_gex: row.call_gex,
        put_gex: row.put_gex,
        net_gex: row.net_gex,
        cumulative_gex: row.cumulative_gex,
        call_dex: row.call_dex,
        put_dex: row.put_dex,
        call_charm: row.call_charm,
        put_charm: row.put_charm,
      }));
      spot = snapshotBundle.snapshot.spot ?? spot;
      warnings.push(`No spot-gamma profile rows found for ${symbol}; using ${snapshotBundle.source} strike aggregates.`);
    } else {
      warnings.push("No spot-gamma profile rows found for symbol");
    }
  }

  // Apply simple moving-average smoothing to net_gex and cumulative_gex
  const series: SpotGammaRow[] = rawRows.map((row, i) => {
    if (smooth <= 1) return row;
    const half = Math.floor(smooth / 2);
    const lo = Math.max(0, i - half);
    const hi = Math.min(rawRows.length - 1, i + half);
    const window = rawRows.slice(lo, hi + 1);
    const avg = (key: keyof typeof row) =>
      window.reduce((s, r) => s + (Number(r[key]) || 0), 0) / window.length;
    return {
      ...row,
      net_gex: avg("net_gex"),
      cumulative_gex: avg("cumulative_gex"),
    };
  });

  // Find ATM row
  let atmRow: (typeof series)[0] | null = null;
  if (spot !== null && series.length > 0) {
    atmRow = series.reduce((best, row) =>
      Math.abs(row.strike - spot) < Math.abs(best.strike - spot) ? row : best
    );
  }

  return {
    data: {
      implemented: true,
      module: "spot-gamma",
      symbol,
      spot,
      smooth,
      current: atmRow
        ? {
            net_gex: atmRow.net_gex,
            call_gex: atmRow.call_gex,
            put_gex: atmRow.put_gex,
            cumulative_gex: atmRow.cumulative_gex,
            atm_strike: atmRow.strike,
          }
        : null,
      series,
    },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// buildLargest  — top-N strikes by GEX magnitude
// ---------------------------------------------------------------------------

type LargestRow = {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  abs_net_gex: number;
  call_oi: number;
  put_oi: number;
  call_premium: number | null;
  put_premium: number | null;
  source: "macro-cache" | "gex-profile";
};

type LargestData = {
  implemented: true;
  module: "largest";
  symbol: string;
  cacheDate: string | null;
  filters: { limit: number; sort: string; expiryScope: string };
  rows: LargestRow[];
};

export async function buildLargest(
  symbol: string,
  limit: number,
  sort: string,
  expiryScope = "all"
): Promise<{ data: LargestData; warnings: string[] }> {
  const warnings: string[] = [];

  // Primary: aggregate macro cache contracts by strike (true GEX = γ × OI × S²)
  const snapshotBundle = await loadOptionSnapshot(symbol).catch(() => null);
  const macro = snapshotBundle?.snapshot ?? null;

  if (macro && ((macro.calls?.length ?? 0) > 0 || (macro.puts?.length ?? 0) > 0)) {
    const spot = macro.spot ?? 1;
    const now = new Date();
    type Acc = {
      strike: number;
      call_gex: number;
      put_gex: number;
      call_oi: number;
      put_oi: number;
      call_premium: number;
      put_premium: number;
    };
    const acc = new Map<number, Acc>();

    function addContracts(contracts: MacroContract[], side: "call" | "put") {
      if (!contracts || contracts.length === 0) return;
      for (const c of contracts) {
        if (!isInExpiryScope(c.expiry, expiryScope, now)) continue;
        const strike = c.strike ?? 0;
        const gex = (c.gamma ?? 0) * (c.open_interest ?? 0) * spot * spot * 0.01;
        const premium = (c.mark ?? 0) * (c.open_interest ?? 0) * 100;
        if (!acc.has(strike)) {
          acc.set(strike, { strike, call_gex: 0, put_gex: 0, call_oi: 0, put_oi: 0, call_premium: 0, put_premium: 0 });
        }
        const row = acc.get(strike)!;
        if (side === "call") {
          row.call_gex += gex;
          row.call_oi += c.open_interest ?? 0;
          row.call_premium += premium;
        } else {
          row.put_gex += gex;
          row.put_oi += c.open_interest ?? 0;
          row.put_premium += premium;
        }
      }
    }

    addContracts(macro.calls ?? [], "call");
    addContracts(macro.puts ?? [], "put");

    const rows: LargestRow[] = Array.from(acc.values()).map((r) => ({
      strike: r.strike,
      call_gex: Math.round(r.call_gex),
      put_gex: Math.round(r.put_gex),
      net_gex: Math.round(r.call_gex - r.put_gex),
      abs_net_gex: Math.round(Math.abs(r.call_gex - r.put_gex)),
      call_oi: r.call_oi,
      put_oi: r.put_oi,
      call_premium: Math.round(r.call_premium),
      put_premium: Math.round(r.put_premium),
      source: "macro-cache" as const,
    }));

    // Sort
    if (sort === "call_gex") rows.sort((a, b) => b.call_gex - a.call_gex);
    else if (sort === "put_gex") rows.sort((a, b) => b.put_gex - a.put_gex);
    else rows.sort((a, b) => b.abs_net_gex - a.abs_net_gex); // default: abs_net

    warnings.push(
      snapshotBundle?.source === "live-chain"
        ? `Largest strikes from live option chain (${macro._sym}, ${macro._date}, scope=${expiryScope})`
        : `Largest strikes from macro cache (${macro._sym}, ${macro._date}, scope=${expiryScope})`
    );

    return {
      data: {
        implemented: true,
        module: "largest",
        symbol,
        cacheDate: macro._date,
        filters: { limit, sort, expiryScope },
        rows: rows.slice(0, limit),
      },
      warnings,
    };
  }

  // Fallback: gex_profiles (no premium column)
  const [profiles, state] = await Promise.all([loadGexProfiles(), loadPipelineState()]);
  const rawRows = resolveProfileRows(profiles, symbol);

  if (!rawRows.length) {
    warnings.push("No profile rows found for symbol");
    return {
      data: { implemented: true, module: "largest", symbol, cacheDate: null, filters: { limit, sort, expiryScope }, rows: [] },
      warnings,
    };
  }

  const rows: LargestRow[] = rawRows.map((r) => {
    const callGex = Number(r.call_gex ?? 0);
    const putGex = Number(r.put_gex ?? 0);
    const netGex = Number(r.net_gex ?? callGex - putGex);
    return {
      strike: Number(r.strike ?? 0),
      call_gex: callGex,
      put_gex: putGex,
      net_gex: netGex,
      abs_net_gex: Math.abs(netGex),
      call_oi: Number(r.call_oi ?? 0),
      put_oi: Number(r.put_oi ?? 0),
      call_premium: r.call_premium != null ? Number(r.call_premium) : null,
      put_premium: r.put_premium != null ? Number(r.put_premium) : null,
      source: "gex-profile" as const,
    };
  });

  if (sort === "call_gex") rows.sort((a, b) => b.call_gex - a.call_gex);
  else if (sort === "put_gex") rows.sort((a, b) => b.put_gex - a.put_gex);
  else rows.sort((a, b) => b.abs_net_gex - a.abs_net_gex);

  const ticker = resolveTickerEntry(state, symbol);
  const spot = toNum(ticker?.spot);
  warnings.push("Macro cache unavailable — largest from gex_profiles (no per-expiry breakdown)");
  if (expiryScope !== "all") {
    warnings.push(`Expiry scope '${expiryScope}' is not applied to gex_profiles fallback rows`);
  }

  return {
    data: {
      implemented: true,
      module: "largest",
      symbol,
      cacheDate: null,
      filters: { limit, sort, expiryScope },
      rows: rows.slice(0, limit),
    },
    warnings,
  };
  void spot; // spot used for future expiry drilldown
}

// ---------------------------------------------------------------------------
// buildHeatmap  — strike × expiry matrix from macro cache
// ---------------------------------------------------------------------------

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
  implemented: true;
  module: "heatmap";
  symbol: string;
  cacheDate: string | null;
  filters: { market: string; mode: string; metric: string; strikes: number; expiryMode: string };
  strikes: number[];
  expiries: string[];
  matrix: HeatmapCell[];
  /** Summary stats per expiry for treemap mode */
  treemap: Array<{ expiry: string; net_gex: number; call_gex: number; put_gex: number; total_oi: number }>;
};

export async function buildHeatmap(
  symbol: string,
  market: string,
  mode: string,
  metric: string,
  strikes: number,
  expiryMode: string
): Promise<{ data: HeatmapData; warnings: string[] }> {
  const warnings: string[] = [];

  const [snapshotBundle, state] = await Promise.all([
    loadOptionSnapshot(symbol).catch(() => null),
    loadPipelineState(),
  ]);
  const macro = snapshotBundle?.snapshot ?? null;

  if (!macro || ((macro.calls?.length ?? 0) === 0 && (macro.puts?.length ?? 0) === 0)) {
    warnings.push("Macro cache unavailable; heatmap cannot be computed");
    return {
      data: {
        implemented: true,
        module: "heatmap",
        symbol,
        cacheDate: null,
        filters: { market, mode, metric, strikes, expiryMode },
        strikes: [],
        expiries: [],
        matrix: [],
        treemap: [],
      },
      warnings,
    };
  }

  const ticker = resolveTickerEntry(state, symbol);
  const spot = (macro.spot ?? toNum(ticker?.spot)) ?? 0;

  // Collect all unique strikes sorted around spot and all unique expiries
  const allStrikes = new Set<number>();
  const allExpiries = new Set<string>();
  for (const c of [...(macro.calls ?? []), ...(macro.puts ?? [])]) {
    if (c.strike != null) allStrikes.add(c.strike);
    if (c.expiry) allExpiries.add(c.expiry);
  }

  const sortedStrikes = Array.from(allStrikes)
    .sort((a, b) => a - b)
    // Center slice around spot
    .reduce<number[]>((acc, s) => {
      acc.push(s);
      acc.sort((a, b) => Math.abs(a - spot) - Math.abs(b - spot));
      return acc.slice(0, strikes * 2);
    }, [])
    .sort((a, b) => a - b);

  const sortedExpiries = Array.from(allExpiries).sort();

  // Build key: `${strike}:${expiry}`
  type CellAcc = {
    call_gex: number; put_gex: number; call_oi: number; put_oi: number;
  };
  const cellMap = new Map<string, CellAcc>();

  function addToCell(contracts: MacroContract[], side: "call" | "put") {
    if (!contracts || contracts.length === 0) return;
    for (const c of contracts) {
      if (c.strike == null || !c.expiry) continue;
      const key = `${c.strike}:${c.expiry}`;
      if (!cellMap.has(key)) {
        cellMap.set(key, { call_gex: 0, put_gex: 0, call_oi: 0, put_oi: 0 });
      }
      const cell = cellMap.get(key)!;
      const gex = (c.gamma ?? 0) * (c.open_interest ?? 0) * spot * spot * 0.01;
      if (side === "call") {
        cell.call_gex += gex;
        cell.call_oi += c.open_interest ?? 0;
      } else {
        cell.put_gex += gex;
        cell.put_oi += c.open_interest ?? 0;
      }
    }
  }

  addToCell(macro.calls ?? [], "call");
  addToCell(macro.puts ?? [], "put");

  const matrix: HeatmapCell[] = [];
  const strikeSet = new Set(sortedStrikes);
  for (const [key, cell] of cellMap) {
    const [strikeStr, expiry] = key.split(":");
    const strike = parseFloat(strikeStr);
    if (!strikeSet.has(strike)) continue;

    const netGex = cell.call_gex - cell.put_gex;
    const totalPutOi = cell.put_oi;
    matrix.push({
      strike,
      expiry,
      call_gex: Math.round(cell.call_gex),
      put_gex: Math.round(cell.put_gex),
      net_gex: Math.round(netGex),
      call_oi: cell.call_oi,
      put_oi: totalPutOi,
      pcr: cell.call_oi > 0 ? Math.round((totalPutOi / cell.call_oi) * 100) / 100 : null,
    });
  }

  // Treemap: aggregate per expiry
  const expiryAcc = new Map<string, { net_gex: number; call_gex: number; put_gex: number; total_oi: number }>();
  for (const cell of matrix) {
    if (!expiryAcc.has(cell.expiry)) {
      expiryAcc.set(cell.expiry, { net_gex: 0, call_gex: 0, put_gex: 0, total_oi: 0 });
    }
    const ea = expiryAcc.get(cell.expiry)!;
    ea.net_gex += cell.net_gex;
    ea.call_gex += cell.call_gex;
    ea.put_gex += cell.put_gex;
    ea.total_oi += cell.call_oi + cell.put_oi;
  }

  const treemap = Array.from(expiryAcc.entries())
    .map(([expiry, ea]) => ({ expiry, ...ea }))
    .sort((a, b) => a.expiry.localeCompare(b.expiry));

  warnings.push(
    `${snapshotBundle?.source === "live-chain" ? "Heatmap from live option chain" : "Heatmap from macro cache"} (${macro._sym}, ${macro._date}), ${sortedStrikes.length} strikes × ${sortedExpiries.length} expiries`
  );

  return {
    data: {
      implemented: true,
      module: "heatmap",
      symbol,
      cacheDate: macro._date,
      filters: { market, mode, metric, strikes, expiryMode },
      strikes: sortedStrikes,
      expiries: sortedExpiries,
      matrix,
      treemap,
    },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// buildPublishPreview  — render Discord-style text embed from live data
// ---------------------------------------------------------------------------

type PublishPreviewData = {
  implemented: true;
  module: "publish-preview";
  symbol: string;
  mode: string;
  previewToken: string;
  text: string;
  embed: {
    title: string;
    description: string;
    fields: Array<{ name: string; value: string; inline: boolean }>;
    color: number;
    footer: string;
  };
};

type PublishMode = "spot" | "full" | "heatmap-pack";
type PublishChannel = "test_channel" | "option-levels" | "alerts" | "macro-alerts" | string;

export async function buildPublishPreview(
  symbol: string,
  mode: string,
  channel: PublishChannel = "test_channel"
): Promise<{ data: PublishPreviewData; warnings: string[] }> {
  const warnings: string[] = [];
  const [state, levels] = await Promise.all([loadPipelineState(), loadDailyLevels()]);

  const ticker = resolveTickerEntry(state, symbol);
  const structure = resolveDailyStructure(levels, symbol);

  const spot = toNum(ticker?.spot);
  const gexTotal = toNum(ticker?.total_gex);
  const regime = (ticker?.regime_label as string | undefined) ?? (ticker?.gex_regime as string | undefined) ?? "UNKNOWN";
  const callWall = toNum(ticker?.call_wall);
  const putWall = toNum(ticker?.put_wall);
  const gammaFlip = toNum(ticker?.zero_gamma);
  const bias = (ticker?.directional_bias as string | undefined) ?? "NEUTRAL";
  const runLabel = (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? "";

  const fmt = (v: number | null, d = 2) =>
    v !== null ? v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }) : "N/A";

  const gexStr = gexTotal !== null ? (gexTotal >= 0 ? `+${fmt(gexTotal, 0)}` : fmt(gexTotal, 0)) : "N/A";

  const color = regime.includes("NEGATIVE") ? 0xe74c3c : regime.includes("POSITIVE") ? 0x2ecc71 : 0x95a5a6;

  const preCoachPP = (structure?.coach_note as string[] | undefined) ?? [];
  const preTacticalPP = (structure?.tactical_plan as string[] | undefined) ?? [];
  const synthPP = preCoachPP.length === 0
    ? synthesizeCoachNotes(
        symbol, spot, callWall, putWall, gammaFlip,
        ticker?.gex_regime as string | undefined,
        bias,
        { lower: null, upper: null, width: null },
        []
      )
    : null;
  const coachLines = synthPP ? synthPP.coach : preCoachPP;
  const tacticalLines = synthPP ? synthPP.tactical : preTacticalPP;
  const coachText = coachLines.slice(0, 2).join("\n") || "No notes available";
  const tacticalText = tacticalLines.slice(0, 2).join("\n") || "No notes available";

  const shortText =
    `**${symbol} Options Flow** | ${runLabel}\n` +
    `Spot: $${fmt(spot)} | GEX: ${gexStr} | ${regime}\n` +
    `• Gamma Flip: ${fmt(gammaFlip)}\n` +
    `• Call Wall: ${fmt(callWall)} | Put Wall: ${fmt(putWall)}\n` +
    `• Bias: ${bias}`;

  const normalizedMode: PublishMode =
    mode === "full" || mode === "heatmap-pack" || mode === "spot" ? mode : "spot";
  const fullText = normalizedMode === "full" ? `${shortText}\n\n${coachText}` : shortText;

  // Deterministic token so same content = same token
  const previewToken = Buffer.from(`${symbol}-${runLabel}-${normalizedMode}-${channel}`).toString("base64").slice(0, 24);

  const baseFields: Array<{ name: string; value: string; inline: boolean }> = [
    { name: "Regime", value: `${regime} | Bias: ${bias}`, inline: true },
    { name: "GEX", value: gexStr, inline: true },
  ];

  const modeFields =
    normalizedMode === "spot"
      ? [
          { name: "Key Levels", value: `Flip: ${fmt(gammaFlip)} | Calls: ${fmt(callWall)} | Puts: ${fmt(putWall)}`, inline: false },
          ...baseFields,
        ]
      : normalizedMode === "full"
        ? [
            { name: "Key Levels", value: `Flip: ${fmt(gammaFlip)} | Calls: ${fmt(callWall)} | Puts: ${fmt(putWall)}`, inline: false },
            ...baseFields,
            { name: "Coach Note", value: coachText, inline: false },
            { name: "Tactical Plan", value: tacticalText, inline: false },
          ]
        : [
            { name: "Heatmap Pack", value: "Visual-first publish. Use image to read per-expiry/per-strike pressure.", inline: false },
            ...baseFields,
            { name: "Key Levels", value: `Flip: ${fmt(gammaFlip)} | Calls: ${fmt(callWall)} | Puts: ${fmt(putWall)}`, inline: false },
          ];

  const moveSummary =
    spot !== null && gammaFlip !== null
      ? `Flip gap: ${fmt(gammaFlip - spot, 2)} (${(((gammaFlip - spot) / spot) * 100).toFixed(2)}%)`
      : "Flip gap: N/A";

  let channelDescription = shortText;
  let channelFields = modeFields;

  if (channel === "alerts") {
    channelDescription = `**${symbol} Alert** | ${runLabel}\nSpot $${fmt(spot)} | ${regime} | Bias ${bias}`;
    channelFields = [
      { name: "Action Context", value: moveSummary, inline: false },
      { name: "Key Levels", value: `Flip ${fmt(gammaFlip)} | Call ${fmt(callWall)} | Put ${fmt(putWall)}`, inline: false },
      { name: "GEX", value: gexStr, inline: true },
    ];
  } else if (channel === "macro-alerts") {
    channelDescription = `**${symbol} Macro Regime** | ${runLabel}\nSpot $${fmt(spot)} | ${regime}`;
    channelFields = [
      { name: "Regime", value: `${regime} | Bias: ${bias}`, inline: true },
      { name: "GEX", value: gexStr, inline: true },
      { name: "Macro Note", value: coachText, inline: false },
    ];
  } else if (channel === "option-levels") {
    channelDescription = `**${symbol} Levels Update** | ${runLabel}\nSpot $${fmt(spot)} | ${regime} | ${moveSummary}`;
    channelFields = [
      { name: "Key Levels", value: `Flip: ${fmt(gammaFlip)} | Calls: ${fmt(callWall)} | Puts: ${fmt(putWall)}`, inline: false },
      { name: "Regime", value: `${regime} | Bias: ${bias}`, inline: true },
      { name: "GEX", value: gexStr, inline: true },
      ...(normalizedMode === "full" ? [{ name: "Tactical Plan", value: tacticalText, inline: false }] : []),
    ];
  }

  return {
    data: {
      implemented: true,
      module: "publish-preview",
      symbol,
      mode: normalizedMode,
      previewToken,
      text: fullText,
      embed: {
        title: `${symbol} — GEX Dashboard | ${runLabel}`,
        description: channelDescription,
        fields: channelFields,
        color,
        footer: `Generated by V3 pipeline | channel=${channel} | ${new Date().toISOString()}`,
      },
    },
    warnings: ticker ? warnings : [...warnings, "Pipeline ticker not found; preview may be incomplete"],
  };
}

// ---------------------------------------------------------------------------
// buildPublishDiscord  — POST embed to a Discord webhook channel
// ---------------------------------------------------------------------------

async function loadDiscordWebhooks(): Promise<Record<string, string>> {
  const p = path.join(process.cwd(), "..", "discord_webhooks.json");
  const raw = await readFile(p, "utf-8");
  return JSON.parse(raw) as Record<string, string>;
}

type PublishDiscordData = {
  implemented: true;
  module: "publish-discord";
  symbol: string;
  channel: string;
  idempotencyKey: string;
  status: "sent" | "dry-run" | "error";
  discordStatusCode?: number;
  message: string;
};

export async function buildPublishDiscord(
  symbol: string,
  channel: string,
  idempotencyKey: string,
  previewToken: string,
  mode: string,
  dryRun = false,
  chartImageDataUrl?: string
): Promise<{ data: PublishDiscordData; warnings: string[] }> {
  const warnings: string[] = [];

  // Build the preview first
  const { data: preview, warnings: pWarn } = await buildPublishPreview(symbol, mode, channel);
  warnings.push(...pWarn);

  if (dryRun) {
    return {
      data: {
        implemented: true,
        module: "publish-discord",
        symbol,
        channel,
        idempotencyKey,
        status: "dry-run",
        message: "Dry-run — no HTTP request made",
      },
      warnings: [...warnings, "dry-run mode"],
    };
  }

  let webhooks: Record<string, string>;
  try {
    webhooks = await loadDiscordWebhooks();
  } catch {
    return {
      data: {
        implemented: true,
        module: "publish-discord",
        symbol,
        channel,
        idempotencyKey,
        status: "error",
        message: "discord_webhooks.json not found or unreadable",
      },
      warnings: [...warnings, "Failed to read discord_webhooks.json"],
    };
  }

  const webhookUrl = webhooks[channel];
  if (!webhookUrl) {
    const available = Object.keys(webhooks).join(", ");
    return {
      data: {
        implemented: true,
        module: "publish-discord",
        symbol,
        channel,
        idempotencyKey,
        status: "error",
        message: `Channel key '${channel}' not found. Available: ${available}`,
      },
      warnings: [...warnings, `Unknown channel '${channel}'`],
    };
  }

  // Sign idempotency key as username suffix so Discord deduplicates visually
  const keyHash = createHash("sha256").update(idempotencyKey).digest("hex").slice(0, 8);

  const embedPayload: {
    title: string;
    description: string;
    color: number;
    fields: Array<{ name: string; value: string; inline: boolean }>;
    footer: { text: string };
    timestamp: string;
    image?: { url: string };
  } = {
    title: preview.embed.title,
    description: preview.embed.description,
    color: preview.embed.color,
    fields: preview.embed.fields,
    footer: { text: preview.embed.footer },
    timestamp: new Date().toISOString(),
  };

  let chartImageBuffer: Buffer | null = null;
  if (chartImageDataUrl && chartImageDataUrl.startsWith("data:image/png;base64,")) {
    try {
      const b64 = chartImageDataUrl.slice("data:image/png;base64,".length);
      chartImageBuffer = Buffer.from(b64, "base64");
      if (chartImageBuffer.length > 0) {
        embedPayload.image = { url: "attachment://chart.png" };
      }
    } catch {
      warnings.push("Chart image payload could not be decoded; posting without attachment");
      chartImageBuffer = null;
    }
  } else if (chartImageDataUrl) {
    warnings.push("Chart image payload is not a PNG data URL; posting without attachment");
  }

  const body = {
    username: `GEX-Bot [${symbol}] #${keyHash}`,
    embeds: [embedPayload],
  };

  let status: "sent" | "error" = "sent";
  let discordStatusCode: number | undefined;
  let message = "Posted to Discord";

  try {
    let res: Response;
    if (chartImageBuffer && chartImageBuffer.length > 0) {
      const form = new FormData();
      form.append("payload_json", JSON.stringify(body));
      form.append("files[0]", new Blob([new Uint8Array(chartImageBuffer)], { type: "image/png" }), "chart.png");
      res = await fetch(webhookUrl, {
        method: "POST",
        body: form,
      });
    } else {
      res = await fetch(webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    }
    discordStatusCode = res.status;
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      status = "error";
      message = `Discord returned ${res.status}: ${text.slice(0, 200)}`;
    }
  } catch (err) {
    status = "error";
    message = `Fetch failed: ${(err as Error).message}`;
  }

  return {
    data: {
      implemented: true,
      module: "publish-discord",
      symbol,
      channel,
      idempotencyKey,
      status,
      discordStatusCode,
      message,
    },
    warnings,
  };
}
