import { NextRequest } from "next/server";
import { ok, serverError } from "@/lib/options-live-v3/http";
import {
  loadDailyLevels,
  loadGexProfiles,
  loadPipelineState,
  normalizeSymbolRoot,
  buildCandidates,
} from "@/lib/options-live-v3/data";
import prisma from "@/lib/prisma";
import { DEFAULT_WATCHLIST } from "@/lib/watchlist-constants";
import { searchSymbols } from "@/lib/yahoo-finance";
import fs from "fs/promises";
import path from "path";

type LookupCandidate = {
  symbol: string;
  sources: Set<string>;
  name?: string;
  exchange?: string;
  type?: string;
};

type PersistedCatalogItem = {
  symbol: string;
  name?: string;
  exchange?: string;
  type?: string;
  sources?: string[];
  lastSeen?: string;
};

type PersistedCatalog = {
  updatedAt: string;
  items: PersistedCatalogItem[];
};

const CATALOG_PATH = path.join(process.cwd(), "..", "data", "options", "symbol_catalog.json");
const LOCAL_REFRESH_MS = 30 * 60 * 1000;
const REMOTE_QUERY_TTL_MS = 6 * 60 * 60 * 1000;

let inMemoryCatalog: Map<string, LookupCandidate> | null = null;
let lastLocalRefreshMs = 0;
const remoteQueryCooldown = new Map<string, number>();

function normalizeLookupKey(raw: string): string {
  return normalizeSymbolRoot(raw).replace(/[^A-Z0-9]/g, "").toUpperCase();
}

function upsert(
  map: Map<string, LookupCandidate>,
  raw: string | undefined,
  source: string,
  details?: { name?: string; exchange?: string; type?: string }
): void {
  if (!raw) return;
  const key = normalizeLookupKey(raw);
  if (!key) return;

  const existing = map.get(key);
  if (existing) {
    existing.sources.add(source);
    // Prefer the slashed version for display (e.g., /ES over ES)
    if (raw.startsWith("/") && !existing.symbol.startsWith("/")) {
      existing.symbol = raw.toUpperCase();
    }
    if (!existing.name && details?.name) existing.name = details.name;
    if (!existing.exchange && details?.exchange) existing.exchange = details.exchange;
    if (!existing.type && details?.type) existing.type = details.type;
    return;
  }

  // Use the raw symbol if it has a slash, otherwise use the key
  const displaySymbol = raw.startsWith("/") ? ("/" + key) : key;

  map.set(key, {
    symbol: displaySymbol,
    sources: new Set([source]),
    name: details?.name,
    exchange: details?.exchange,
    type: details?.type,
  });
}

const FALLBACK_SYMBOLS = [
  "SPY",
  "QQQ",
  "IWM",
  "DIA",
  "SPX",
  "NDX",
  "RUT",
  "AAPL",
  "MSFT",
  "NVDA",
  "TSLA",
  "META",
  "AMZN",
  "GOOGL",
  "AMD",
  "PLTR",
  "COIN",
  "NFLX",
  "MU",
  "JPM",
  "ES",
  "NQ",
  "RTY",
  "YM",
  "GC",
  "CL",
  "/ES",
  "/NQ",
  "/RTY",
  "/YM",
  "/GC",
  "/CL",
];

function score(symbol: string, query: string): number {
  if (!query) return 1;
  const s = symbol.toUpperCase();
  const q = query.toUpperCase();

  const sClean = s.replace(/^\//, "");
  const qClean = q.replace(/^\//, "");

  // 1. Exact match (ignoring slash)
  if (sClean === qClean) return 500;

  // 2. Starts with (ignoring slash)
  if (sClean.startsWith(qClean)) return 250 - (sClean.length - qClean.length);

  // 3. Handle contract symbols in query (e.g., ESU24 matching ES root)
  const qRoot = qClean.match(/^([A-Z]{1,8})\d+!?$/)?.[1];
  if (qRoot && sClean === qRoot) return 400;

  // 4. Translation / Alias match (e.g., query "SPY" matching symbol "/ES")
  const sRoot = normalizeSymbolRoot(symbol);
  const qActualRoot = qRoot || qClean;
  const relatives = buildCandidates(qActualRoot).map(r => normalizeSymbolRoot(r));
  if (relatives.includes(sRoot)) return 200;

  // 5. Substring match
  const idx = sClean.indexOf(qClean);
  if (idx >= 0) return 120 - idx;

  return 0;
}

async function loadPersistedCatalog(): Promise<PersistedCatalogItem[]> {
  try {
    const raw = await fs.readFile(CATALOG_PATH, "utf-8");
    const parsed = JSON.parse(raw) as PersistedCatalog;
    if (!Array.isArray(parsed.items)) return [];
    return parsed.items;
  } catch {
    return [];
  }
}

async function persistCatalog(candidates: Map<string, LookupCandidate>): Promise<void> {
  try {
    const payload: PersistedCatalog = {
      updatedAt: new Date().toISOString(),
      items: Array.from(candidates.values())
        .sort((a, b) => a.symbol.localeCompare(b.symbol))
        .map((item) => ({
          symbol: item.symbol,
          name: item.name,
          exchange: item.exchange,
          type: item.type,
          sources: Array.from(item.sources),
          lastSeen: new Date().toISOString(),
        })),
    };
    await fs.mkdir(path.dirname(CATALOG_PATH), { recursive: true });
    await fs.writeFile(CATALOG_PATH, JSON.stringify(payload, null, 2), "utf-8");
  } catch {
    // Keep lookup responsive even when persistence fails.
  }
}

async function collectMacroCacheSymbols(candidates: Map<string, LookupCandidate>): Promise<void> {
  try {
    const optionsDir = path.join(process.cwd(), "..", "data", "options");
    const files = await fs.readdir(optionsDir);
    for (const file of files) {
      if (!file.startsWith("macro_cache_") || !file.endsWith(".json")) continue;
      const match = /^macro_cache_([A-Za-z0-9]+)_\d{4}-\d{2}-\d{2}\.json$/.exec(file);
      if (!match) continue;
      upsert(candidates, match[1], "macro-cache");
    }
  } catch {
    // Optional source.
  }
}

async function buildLocalCatalog(): Promise<Map<string, LookupCandidate>> {
  const [state, profiles, levels, persisted, watchlistItems, hvTickers, emTickers] = await Promise.all([
    loadPipelineState(),
    loadGexProfiles(),
    loadDailyLevels(),
    loadPersistedCatalog(),
    prisma.watchlistItem.findMany({
      select: { symbol: true, name: true },
      take: 2000,
      orderBy: { createdAt: "desc" },
    }).catch(() => []),
    prisma.historicalVolatility.findMany({
      select: { ticker: true },
      distinct: ["ticker"],
      take: 1000,
      orderBy: { date: "desc" },
    }).catch(() => []),
    prisma.expectedMoveHistory.findMany({
      select: { ticker: true },
      distinct: ["ticker"],
      take: 1000,
      orderBy: { date: "desc" },
    }).catch(() => []),
  ]);

  const candidates = new Map<string, LookupCandidate>();

  for (const item of persisted) {
    upsert(candidates, item.symbol, "catalog", {
      name: item.name,
      exchange: item.exchange,
      type: item.type,
    });
  }

  for (const key of Object.keys(state?.tickers ?? {})) {
    upsert(candidates, key, "pipeline");
  }

  for (const key of Object.keys(profiles?.profiles ?? {})) {
    upsert(candidates, key, "profiles");
  }

  for (const row of levels?.market_structure ?? []) {
    upsert(candidates, typeof row.asset === "string" ? row.asset : undefined, "levels");
    upsert(candidates, typeof row.cash_ticker === "string" ? row.cash_ticker : undefined, "levels");
  }

  for (const row of watchlistItems) {
    upsert(candidates, row.symbol, "watchlist", { name: row.name ?? undefined });
  }

  for (const row of hvTickers) {
    upsert(candidates, row.ticker, "historical-vol");
  }

  for (const row of emTickers) {
    upsert(candidates, row.ticker, "expected-move");
  }

  for (const symbol of DEFAULT_WATCHLIST) {
    upsert(candidates, symbol, "default-watchlist");
  }

  for (const symbol of FALLBACK_SYMBOLS) {
    upsert(candidates, symbol, "fallback");
  }

  await collectMacroCacheSymbols(candidates);
  return candidates;
}

async function getCatalog(): Promise<Map<string, LookupCandidate>> {
  const now = Date.now();
  if (!inMemoryCatalog || now - lastLocalRefreshMs > LOCAL_REFRESH_MS) {
    inMemoryCatalog = await buildLocalCatalog();
    lastLocalRefreshMs = now;
    void persistCatalog(inMemoryCatalog);
  }
  return inMemoryCatalog;
}

async function maybeEnrichFromRemote(candidates: Map<string, LookupCandidate>, query: string): Promise<void> {
  if (!query || query.length < 2) return;

  const cooldownUntil = remoteQueryCooldown.get(query) ?? 0;
  const now = Date.now();
  if (cooldownUntil > now) return;

  remoteQueryCooldown.set(query, now + REMOTE_QUERY_TTL_MS);

  const remote = await searchSymbols(query).catch(() => []);
  for (const item of remote ?? []) {
    upsert(candidates, item.symbol, "remote-search", {
      name: item.shortname || item.longname || undefined,
      exchange: item.exchDisp || undefined,
      type: item.typeDisp || undefined,
    });
  }
  void persistCatalog(candidates);
}

export async function GET(req: NextRequest) {
  const rawQ = (req.nextUrl.searchParams.get("q") ?? "").trim().toUpperCase();
  const q = rawQ; 
  const limitRaw = Number.parseInt(req.nextUrl.searchParams.get("limit") ?? "12", 10);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(30, limitRaw)) : 12;

  try {
    const candidates = await getCatalog();

    const preliminary = Array.from(candidates.values())
      .map((item) => ({ item, score: score(item.symbol, q) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.item.symbol.localeCompare(b.item.symbol))
      .slice(0, limit);

    // If local catalog is thin for this query, enrich from remote search occasionally.
    if (preliminary.length < Math.min(5, limit)) {
      await maybeEnrichFromRemote(candidates, q);
    }

    const results = Array.from(candidates.values())
      .map((item) => ({
        symbol: item.symbol,
        name: item.name ?? null,
        exchange: item.exchange ?? null,
        type: item.type ?? null,
        score: score(item.symbol, q),
        sources: Array.from(item.sources),
      }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.symbol.localeCompare(b.symbol))
      .slice(0, limit)
      .map(({ symbol, name, exchange, type, sources }) => ({ symbol, name, exchange, type, sources }));

    return ok({ query: q, results, localCatalogSize: candidates.size }, q || "SPY");
  } catch (error) {
    return serverError(`Failed to build symbol lookup: ${String(error)}`, q || "SPY");
  }
}
