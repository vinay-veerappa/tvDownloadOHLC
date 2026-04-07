import fs from "fs/promises";
import path from "path";

type JsonRecord = Record<string, unknown>;

type PipelineTicker = {
  ticker?: string;
  total_gex?: number;
  gex_regime?: string;
  regime_label?: string;
  directional_bias?: string;
  gamma_magnet?: number;
  pin_strike?: number;
  pin_odds?: number;
  call_wall?: number;
  put_wall?: number;
  zero_gamma?: number;
  spot?: number;
  [key: string]: unknown;
};

type PipelineState = {
  run_label?: string;
  timestamp?: string;
  tickers?: Record<string, PipelineTicker>;
  [key: string]: unknown;
};

type DailyStructure = {
  asset?: string;
  cash_ticker?: string;
  regime_label?: string;
  gex_regime?: string;
  total_gex?: number;
  total_gex_delta_adj?: number;
  gamma_magnet?: number;
  pin_strike?: number;
  pin_odds?: number;
  call_centroid?: number;
  put_centroid?: number;
  coach_note?: string[];
  tactical_plan?: string[];
  scored_analysis?: Record<string, unknown>;
  [key: string]: unknown;
};

type DailyLevels = {
  generated_at?: string;
  run_label?: string;
  market_structure?: DailyStructure[];
  [key: string]: unknown;
};

type GexProfiles = {
  generated_at?: string;
  run_label?: string;
  profiles?: Record<string, Array<Record<string, unknown>>>;
  [key: string]: unknown;
};

export type MacroContract = {
  symbol?: string;
  strike?: number;
  type?: string;
  contract_type?: string;
  expiry?: string;
  last?: number;
  bid?: number;
  ask?: number;
  mark?: number;
  volume?: number;
  open_interest?: number;
  iv?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  dte?: number;
};

export type MacroCache = {
  ticker?: string;
  spot?: number;
  snapshot_time?: string;
  calls: MacroContract[];
  puts: MacroContract[];
};

export type MacroCacheResult = MacroCache & { _sym: string; _date: string };

const DATA_ROOTS = [
  path.join(process.cwd(), "..", "data", "options"),
  path.join(process.cwd(), "..", "data"),
];

async function readJsonFromRoots<T extends JsonRecord>(filename: string): Promise<T | null> {
  for (const root of DATA_ROOTS) {
    const candidate = path.join(root, filename);
    try {
      const content = await fs.readFile(candidate, "utf-8");
      return JSON.parse(content) as T;
    } catch {
      // Try next root.
    }
  }
  return null;
}

export async function loadPipelineState(): Promise<PipelineState | null> {
  return readJsonFromRoots<PipelineState>("pipeline_state.json");
}

export async function loadDailyLevels(): Promise<DailyLevels | null> {
  return readJsonFromRoots<DailyLevels>("daily_levels.json");
}

export async function loadGexProfiles(): Promise<GexProfiles | null> {
  return readJsonFromRoots<GexProfiles>("gex_profiles.json");
}

function dedupe(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of items) {
    if (!item || seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  return out;
}

function normalizeSymbolRoot(symbol: string): string {
  const clean = symbol.trim().toUpperCase().replace(/^\//, "");
  const futuresRoot = clean.match(/^([A-Z]{1,8})\d+!?$/);
  return futuresRoot?.[1] ?? clean;
}

function buildCandidates(symbol: string): string[] {
  const normalized = normalizeSymbolRoot(symbol);
  const clean = normalized;
  const noSlash = clean.startsWith("/") ? clean.slice(1) : clean;
  const withSlash = noSlash.startsWith("/") ? noSlash : `/${noSlash}`;

  const aliasMap: Record<string, string[]> = {
    ES: ["/ES", "ES", "SPX", "SPY"],
    SPX: ["SPX", "SPY", "/ES", "ES"],
    SPY: ["SPY", "SPX", "/ES", "ES"],
    NQ: ["/NQ", "NQ", "QQQ", "NDX"],
    NDX: ["NDX", "QQQ", "/NQ", "NQ"],
    QQQ: ["QQQ", "NDX", "/NQ", "NQ"],
    RTY: ["/RTY", "RTY", "IWM"],
    IWM: ["IWM", "RTY", "/RTY"],
    YM: ["/YM", "YM", "DIA"],
    DIA: ["DIA", "YM", "/YM"],
  };

  const aliases = aliasMap[noSlash] ?? [noSlash, withSlash];
  return dedupe([clean, noSlash, withSlash, ...aliases]);
}

function findKeyByCandidates<T>(obj: Record<string, T> | undefined, candidates: string[]): string | null {
  if (!obj) return null;

  for (const candidate of candidates) {
    if (Object.prototype.hasOwnProperty.call(obj, candidate)) return candidate;
  }

  const normalized = new Map<string, string>();
  for (const key of Object.keys(obj)) {
    normalized.set(key.toUpperCase().replace(/^\//, ""), key);
  }

  for (const candidate of candidates) {
    const nk = candidate.toUpperCase().replace(/^\//, "");
    const found = normalized.get(nk);
    if (found) return found;
  }

  return null;
}

export function resolveTickerEntry(state: PipelineState | null, symbol: string): PipelineTicker | null {
  if (!state?.tickers) return null;
  const key = findKeyByCandidates(state.tickers, buildCandidates(symbol));
  return key ? state.tickers[key] : null;
}

export function resolveProfileRows(profiles: GexProfiles | null, symbol: string): Array<Record<string, unknown>> {
  const profileMap = profiles?.profiles;
  if (!profileMap) return [];
  const key = findKeyByCandidates(profileMap, buildCandidates(symbol));
  return key ? profileMap[key] ?? [] : [];
}

export function resolveDailyStructure(levels: DailyLevels | null, symbol: string): DailyStructure | null {
  const structures = levels?.market_structure;
  if (!structures?.length) return null;

  const candidates = new Set(buildCandidates(symbol).map((s) => s.toUpperCase().replace(/^\//, "")));
  const found = structures.find((item) => {
    const asset = String(item.asset ?? "").toUpperCase().replace(/^\//, "");
    const cash = String(item.cash_ticker ?? "").toUpperCase().replace(/^\//, "");
    return candidates.has(asset) || candidates.has(cash);
  });

  return found ?? null;
}

/**
 * Candidate file-name symbols for macro_cache_${SYM}_${DATE}.json, in resolution order.
 * Macro cache files are named by equity/ETF symbol (SPY, QQQ, IWM, SPX, …).
 */
function buildMacroCandidates(symbol: string): string[] {
  const clean = normalizeSymbolRoot(symbol);
  const groupMap: Record<string, string[]> = {
    ES: ["SPY", "SPX", "ES"],
    SPX: ["SPX", "SPY"],
    SPY: ["SPY", "SPX"],
    NQ: ["QQQ", "NDX", "NQ"],
    NDX: ["NDX", "QQQ"],
    QQQ: ["QQQ", "NDX"],
    RTY: ["IWM", "RTY"],
    IWM: ["IWM", "RTY"],
    YM: ["DIA", "YM"],
    DIA: ["DIA", "YM"],
  };
  return dedupe([clean, ...(groupMap[clean] ?? [])]);
}

/**
 * Load the latest macro_cache_{SYMBOL}_{DATE}.json file for a given symbol.
 * Tries all alias candidates in priority order and returns the most recent match.
 */
export async function loadMacroCache(symbol: string): Promise<MacroCacheResult | null> {
  const candidates = buildMacroCandidates(symbol);

  for (const root of DATA_ROOTS) {
    let files: string[] = [];
    try {
      files = await fs.readdir(root);
    } catch {
      continue;
    }

    const latestPerCandidate: Array<{ cand: string; file: string; dateStr: string }> = [];

    for (const cand of candidates) {
      const prefix = `macro_cache_${cand}_`;
      // ISO date strings sort lexically — descending = latest first.
      const matching = files
        .filter((f) => f.startsWith(prefix) && f.endsWith(".json"))
        .sort()
        .reverse();

      if (matching.length === 0) continue;

      const latestFile = matching[0];
      const dateStr = latestFile.slice(prefix.length, -5); // strip prefix + ".json"
      latestPerCandidate.push({ cand, file: latestFile, dateStr });
    }

    // Choose freshest snapshot across aliases (e.g. NQ -> QQQ latest over stale NQ file).
    latestPerCandidate.sort((a, b) => b.dateStr.localeCompare(a.dateStr));

    for (const candidate of latestPerCandidate) {
      try {
        const content = await fs.readFile(path.join(root, candidate.file), "utf-8");
        const data = JSON.parse(content) as MacroCache;
        return { ...data, _sym: candidate.cand, _date: candidate.dateStr };
      } catch {
        // unreadable — try next candidate
      }
    }
  }

  return null;
}
