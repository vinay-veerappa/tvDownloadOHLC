import { createHash } from "crypto";
import { readFile } from "fs/promises";
import path from "path";
import {
  loadDailyLevels,
  loadGexProfiles,
  loadMacroCache,
  loadPipelineState,
  type MacroContract,
  resolveDailyStructure,
  resolveProfileRows,
  resolveTickerEntry,
} from "@/lib/options-live-v3/data";
import { queryDoltByExpiry } from "@/lib/options-live-v3/dolt";

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

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol; fallback used where available");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const spot = toNum(ticker?.spot) ?? toNum(structure?.scored_analysis?.spot) ?? null;

  return {
    data: {
      implemented: true,
      module: "summary",
      symbol,
      runLabel: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
      asOf: (state?.timestamp as string | undefined) ?? (levels?.generated_at as string | undefined) ?? null,
      spot,
      gex: {
        total: toNum(ticker?.total_gex) ?? toNum(structure?.total_gex),
        regime: (ticker?.gex_regime as string | undefined) ?? (structure?.gex_regime as string | undefined) ?? null,
        regimeLabel: (ticker?.regime_label as string | undefined) ?? (structure?.regime_label as string | undefined) ?? null,
        directionalBias: (ticker?.directional_bias as string | undefined) ?? null,
      },
      keyLevels: {
        gammaFlip: toNum(ticker?.zero_gamma),
        callWall: toNum(ticker?.call_wall),
        putWall: toNum(ticker?.put_wall),
        gammaMagnet: toNum(ticker?.gamma_magnet),
        pinStrike: toNum(ticker?.pin_strike),
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

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const scored = (structure?.scored_analysis as Record<string, unknown> | undefined) ?? {};
  const resistanceWalls = (scored.resistance_walls as Array<Record<string, unknown>> | undefined) ?? [];
  const supportWalls = (scored.support_walls as Array<Record<string, unknown>> | undefined) ?? [];
  const expectedMove = parseExpectedMoveFromNotes((structure?.coach_note as string[] | undefined) ?? []);

  const primaryCallWall = toNum(ticker?.call_wall);
  const primaryPutWall = toNum(ticker?.put_wall);
  const centroidCallWall = toNum((ticker as Record<string, unknown> | undefined)?.call_centroid);
  const centroidPutWall = toNum((ticker as Record<string, unknown> | undefined)?.put_centroid);
  const scoredCallWall = firstNumericLevel(resistanceWalls);
  const scoredPutWall = firstNumericLevel(supportWalls);

  const spot = toNum(ticker?.spot);
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

  return {
    data: {
      implemented: true,
      module: "levels",
      symbol,
      runLabel: (state?.run_label as string | undefined) ?? (levels?.run_label as string | undefined) ?? null,
      spot: toNum(ticker?.spot),
      levels: {
        spot,
        gammaFlip: toNum(ticker?.zero_gamma),
        callWall: primaryCallWall,
        secondaryCallWall,
        putWall: primaryPutWall,
        secondaryPutWall,
        gammaMagnet: toNum(ticker?.gamma_magnet),
        pinStrike: toNum(ticker?.pin_strike),
        expectedMoveUpper: expectedMove.upper,
        expectedMoveLower: expectedMove.lower,
        expectedMoveWidth: expectedMove.width,
      },
      scored: {
        resistanceWalls,
        supportWalls,
        pivots: (scored.pivots as Array<Record<string, unknown>> | undefined) ?? [],
      },
      notes: {
        coach: (structure?.coach_note as string[] | undefined) ?? [],
        tactical: (structure?.tactical_plan as string[] | undefined) ?? [],
      },
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

  const rows = resolveProfileRows(profiles, symbol)
    .map((row) => ({ ...row }))
    .sort((a, b) => Number(a.strike ?? 0) - Number(b.strike ?? 0));

  if (!rows.length) warnings.push("No strike profile rows found for symbol");

  const ticker = resolveTickerEntry(state, symbol);
  const spot = toNum(ticker?.spot);

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

  if (!ticker) warnings.push("Pipeline ticker entry not found for symbol");
  if (!structure) warnings.push("Daily levels structure entry not found for symbol");

  const spot = toNum(ticker?.spot);
  const callWall = toNum(ticker?.call_wall);
  const putWall = toNum(ticker?.put_wall);
  const zeroGamma = toNum(ticker?.zero_gamma);
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
      notes: {
        coach: (structure?.coach_note as string[] | undefined) ?? [],
        tactical: [
          ...tacticalScoped,
          ...((structure?.tactical_plan as string[] | undefined) ?? []),
        ],
      },
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
  const macro = await loadMacroCache(symbol).catch(() => null);

  if (macro && ((macro.calls?.length ?? 0) > 0 || (macro.puts?.length ?? 0) > 0)) {
    const spot = macro.spot ?? 1;
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

    processContracts(macro.calls ?? [], "call");
    processContracts(macro.puts ?? [], "put");

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
      `Expiry GEX from macro cache (${macro._sym}, ${macro._date}, scope=${expiryScope}): ${macro.calls?.length ?? 0} calls, ${macro.puts?.length ?? 0} puts`
    );

    return {
      data: {
        implemented: true,
        module: "by-expiry",
        symbol,
        dataSource: "macro-cache",
        cacheDate: macro._date,
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

  const macro = await loadMacroCache(symbol).catch(() => null);

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
    `Flow proxy derived from macro cache contract anomalies (${macro._sym}, ${macro._date}). ` +
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

  const rawRows = resolveProfileRows(profiles, symbol)
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

  if (!rawRows.length) warnings.push("No spot-gamma profile rows found for symbol");

  const ticker = resolveTickerEntry(state, symbol);
  const spot = toNum(ticker?.spot);

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
  const macro = await loadMacroCache(symbol).catch(() => null);

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

    warnings.push(`Largest strikes from macro cache (${macro._sym}, ${macro._date}, scope=${expiryScope})`);

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

  const [macro, state] = await Promise.all([
    loadMacroCache(symbol).catch(() => null),
    loadPipelineState(),
  ]);

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

  warnings.push(`Heatmap from macro cache (${macro._sym}, ${macro._date}), ${sortedStrikes.length} strikes × ${sortedExpiries.length} expiries`);

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

  const coachLines = (structure?.coach_note as string[] | undefined) ?? [];
  const tacticalLines = (structure?.tactical_plan as string[] | undefined) ?? [];
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
