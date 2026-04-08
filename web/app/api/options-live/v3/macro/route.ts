import { NextRequest } from "next/server";
import prisma from "@/lib/prisma";
import { ok, readSymbol, serverError } from "@/lib/options-live-v3/http";

type MacroAnomaly = {
  strike?: number;
  type?: "CALL" | "PUT";
  dte_str?: string;
  tier?: number;
  notional?: number;
  avg_vol_oi_ratio?: number;
};

type DominantNode = {
  strike?: number;
  type?: "CALL" | "PUT";
  oi?: number;
  dominance_pct?: number;
  label?: string;
};

function dedupe(items: string[]): string[] {
  return [...new Set(items.filter((item) => item && item.trim().length > 0))];
}

function buildMacroTickerCandidates(symbol: string): string[] {
  const root = symbol.trim().toUpperCase();
  const mappedRoots: Record<string, string[]> = {
    ES: ["ES", "SPX"],
    MES: ["MES", "ES", "SPX"],
    NQ: ["NQ", "NDX", "QQQ"],
    MNQ: ["MNQ", "NQ", "NDX", "QQQ"],
    RTY: ["RTY", "RUT", "IWM"],
    M2K: ["M2K", "RTY", "RUT", "IWM"],
    YM: ["YM", "DJI", "DIA"],
    MYM: ["MYM", "YM", "DJI", "DIA"],
  };

  const roots = mappedRoots[root] ?? [root];
  const variants = roots.flatMap((r) => [r, `${r}[M]`, `${r}[D]`]);
  return dedupe([root, `${root}[M]`, `${root}[D]`, ...variants]);
}

function parseJsonSafe<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const warnings: string[] = [];

  try {
    const candidates = buildMacroTickerCandidates(symbol);
    const snapshot = await prisma.macroSnapshot.findFirst({
      where: { ticker: { in: candidates } },
      orderBy: [{ tradingDate: "desc" }, { timestamp: "desc" }],
    });

    if (!snapshot) {
      warnings.push(`No macro snapshot found for ${symbol}`);
      return ok(null, symbol, warnings);
    }

    const anomalies = parseJsonSafe<{ structural?: MacroAnomaly[]; tactical?: MacroAnomaly[] }>(
      snapshot.anomalies,
      { structural: [], tactical: [] }
    );
    const dominantNodes = parseJsonSafe<DominantNode[]>(snapshot.dominantNodes, []);

    const allAnomalies = [...(anomalies.structural ?? []), ...(anomalies.tactical ?? [])];
    const tierBuckets = [1, 2, 3, 4].map((tier) => {
      const bucket = allAnomalies.filter((row) => row.tier === tier);
      const topNotional = bucket.reduce<number | null>((acc, row) => {
        if (typeof row.notional !== "number") return acc;
        if (acc === null || row.notional > acc) return row.notional;
        return acc;
      }, null);
      return {
        tier,
        count: bucket.length,
        topNotional,
      };
    });

    const topAnomalies = [...allAnomalies]
      .filter((row) => typeof row.strike === "number")
      .sort((a, b) => (b.notional ?? 0) - (a.notional ?? 0))
      .slice(0, 12)
      .map((row) => ({
        tier: row.tier ?? null,
        strike: row.strike ?? null,
        type: row.type ?? null,
        dte: row.dte_str ?? null,
        volOi: row.avg_vol_oi_ratio ?? null,
        notional: row.notional ?? null,
      }));

    const payload = {
      ticker: snapshot.ticker,
      tradingDate: snapshot.tradingDate.toISOString(),
      timestamp: snapshot.timestamp.toISOString(),
      spotPrice: snapshot.spotPrice,
      levels: {
        zeroGamma: snapshot.zeroGamma,
        macroCallWall: snapshot.macroCallWall,
        macroPutWall: snapshot.macroPutWall,
      },
      dominantNodes: dominantNodes
        .filter((row) => typeof row.strike === "number")
        .sort((a, b) => (b.oi ?? 0) - (a.oi ?? 0))
        .slice(0, 12)
        .map((row) => ({
          strike: row.strike ?? null,
          type: row.type ?? null,
          label: row.label ?? null,
          oi: row.oi ?? null,
          dominancePct: row.dominance_pct ?? null,
        })),
      tierBuckets,
      topAnomalies,
    };

    if (snapshot.ticker !== symbol) {
      warnings.push(`Macro data resolved via ${snapshot.ticker} for requested ${symbol}`);
    }

    return ok(payload, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to load macro snapshot: ${String(error)}`, symbol);
  }
}
