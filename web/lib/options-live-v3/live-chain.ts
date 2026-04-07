import fs from "fs";
import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import type { MacroCacheResult } from "@/lib/options-live-v3/data";

const execFileAsync = promisify(execFile);
const LIVE_SNAPSHOT_TTL_MS = 30_000;

type LiveSnapshotPayload = {
  ticker?: string;
  api_symbol?: string;
  snapshot_time?: string;
  spot?: number;
  calls?: MacroCacheResult["calls"];
  puts?: MacroCacheResult["puts"];
};

const snapshotCache = new Map<string, { expiresAt: number; data: MacroCacheResult | null }>();

function normalizeCacheKey(symbol: string): string {
  return symbol.trim().toUpperCase();
}

function getProjectRoot(): string {
  return path.resolve(process.cwd(), "..");
}

function getPythonExecutable(projectRoot: string): string {
  const venvPython = path.join(projectRoot, ".venv", "Scripts", "python.exe");
  return fs.existsSync(venvPython) ? venvPython : "python";
}

function toMacroCacheResult(symbol: string, payload: LiveSnapshotPayload): MacroCacheResult | null {
  const calls = Array.isArray(payload.calls) ? payload.calls : [];
  const puts = Array.isArray(payload.puts) ? payload.puts : [];
  const spot = typeof payload.spot === "number" && Number.isFinite(payload.spot) ? payload.spot : null;

  if ((calls.length === 0 && puts.length === 0) || spot === null || spot <= 0) {
    return null;
  }

  return {
    ticker: payload.ticker ?? symbol,
    spot,
    snapshot_time: payload.snapshot_time,
    calls,
    puts,
    _sym: payload.api_symbol ?? symbol,
    _date: payload.snapshot_time ?? new Date().toISOString(),
  };
}

export async function loadLiveOptionSnapshot(symbol: string): Promise<MacroCacheResult | null> {
  const cacheKey = normalizeCacheKey(symbol);
  const cached = snapshotCache.get(cacheKey);
  const now = Date.now();
  if (cached && cached.expiresAt > now) {
    return cached.data;
  }

  const projectRoot = getProjectRoot();
  const scriptPath = path.join(projectRoot, "scripts", "streaming", "api_option_snapshot.py");
  const pythonExecutable = getPythonExecutable(projectRoot);

  try {
    const { stdout } = await execFileAsync(
      pythonExecutable,
      [scriptPath, "--tickers", symbol],
      {
        cwd: projectRoot,
        timeout: 45_000,
        maxBuffer: 8 * 1024 * 1024,
      }
    );

    const parsed = JSON.parse(stdout) as unknown;
    const payload = Array.isArray(parsed) ? (parsed[0] as LiveSnapshotPayload | undefined) : undefined;
    const result = payload ? toMacroCacheResult(symbol, payload) : null;
    snapshotCache.set(cacheKey, { expiresAt: now + LIVE_SNAPSHOT_TTL_MS, data: result });
    return result;
  } catch {
    snapshotCache.set(cacheKey, { expiresAt: now + 5_000, data: null });
    return null;
  }
}