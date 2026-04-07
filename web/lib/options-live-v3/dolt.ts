/**
 * Dolt options database query helpers for the V3 options dashboard.
 *
 * The Dolt DB at data/options/options/ contains:
 *   option_chain      — EOD greeks per contract (no open_interest column)
 *   volatility_history — IV/HV trending metrics per symbol
 *
 * Queries are executed by shelling out to the `dolt` CLI binary using
 * child_process.execFile, which requires `dolt` to be in the system PATH.
 *
 * NOTE: option_chain has NO open_interest column. Values returned are
 * gamma sums per expiry — directional proxies, not proper GEX (gamma × OI × spot²).
 */

import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";

const execFileAsync = promisify(execFile);

/** Absolute path to the Dolt database directory. */
function getDoltDir(): string {
  // Next.js cwd is web/; repo root is one level up.
  return path.join(process.cwd(), "..", "data", "options", "options");
}

/** Map input symbol to candidate act_symbol values used in Dolt's option_chain. */
function toDoltSymbols(symbol: string): string[] {
  const raw = symbol.trim().toUpperCase().replace(/^\//, "");
  const futuresRoot = raw.match(/^([A-Z]{1,8})\d+!?$/);
  const clean = futuresRoot?.[1] ?? raw;
  const map: Record<string, string[]> = {
    ES: ["SPY", "SPX"],
    SPX: ["SPX", "SPY"],
    SPY: ["SPY", "SPX"],
    NQ: ["QQQ", "NDX"],
    NDX: ["NDX", "QQQ"],
    QQQ: ["QQQ", "NDX"],
    RTY: ["IWM"],
    IWM: ["IWM"],
    YM: ["DIA"],
    DIA: ["DIA"],
  };
  const candidates = map[clean] ?? [];
  // Always try the raw clean symbol in case it exists directly
  return [...new Set([clean, ...candidates])];
}

/** Run a Dolt SQL query and return raw stdout (CSV format). */
async function runDoltCsv(sql: string): Promise<string> {
  const cwd = getDoltDir();
  const { stdout } = await execFileAsync("dolt", ["sql", "-r", "csv", "-q", sql], {
    cwd,
    timeout: 20_000,
  });
  return stdout;
}

/** Minimal CSV parser that handles double-quoted fields. */
function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let cur = "";
  let inQuote = false;
  for (const ch of line) {
    if (ch === '"') {
      inQuote = !inQuote;
    } else if (ch === "," && !inQuote) {
      result.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  result.push(cur.trim());
  return result;
}

function toFloat(s: string): number | null {
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : null;
}

function toInt(s: string): number {
  return parseInt(s, 10) || 0;
}

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type DoltExpiryRow = {
  expiry: string;
  dte: number;
  /** Sum of call gamma across all strikes for this expiry (no OI weighting). */
  call_gamma_sum: number;
  /** Sum of put gamma across all strikes for this expiry (no OI weighting). */
  put_gamma_sum: number;
  /** call_gamma_sum − |put_gamma_sum| */
  net_gamma_sum: number;
  call_contracts: number;
  put_contracts: number;
  call_avg_iv: number | null;
  put_avg_iv: number | null;
  /** Always "dolt" so callers can flag the limitation. */
  source: "dolt";
};

export type DoltVolatilityRow = {
  date: string;
  symbol: string;
  iv_current: number | null;
  iv_week_ago: number | null;
  iv_month_ago: number | null;
  iv_year_high: number | null;
  iv_year_low: number | null;
  iv_year_high_date: string | null;
  iv_year_low_date: string | null;
  hv_current: number | null;
  hv_week_ago: number | null;
  hv_month_ago: number | null;
};

// ---------------------------------------------------------------------------
// queryDoltByExpiry
// ---------------------------------------------------------------------------

/**
 * Query option_chain for the latest available date, grouped by expiry.
 * Tries each candidate symbol in priority order and returns the first match.
 *
 * IMPORTANT: Dolt option_chain has no open_interest column. The returned
 * call_gamma_sum / put_gamma_sum values are raw gamma totals, not GEX.
 */
export async function queryDoltByExpiry(
  symbol: string
): Promise<{ rows: DoltExpiryRow[]; resolvedSymbol: string; date: string } | null> {
  const candidates = toDoltSymbols(symbol);

  for (const sym of candidates) {
    // Step 1: find the latest date available for this symbol
    const dateCsv = await runDoltCsv(
      `SELECT MAX(date) AS latest FROM option_chain WHERE act_symbol = '${sym}'`
    ).catch(() => null);

    if (!dateCsv) continue;

    const dateLines = dateCsv.trim().split("\n");
    if (dateLines.length < 2) continue;

    const latestDate = parseCsvLine(dateLines[1])[0] ?? "";
    if (!latestDate || latestDate.toUpperCase() === "NULL" || latestDate === "") continue;

    // Step 2: aggregate per expiry
    const aggCsv = await runDoltCsv(`
      SELECT expiration, call_put,
             CAST(SUM(gamma) AS CHAR) AS gamma_sum,
             COUNT(*) AS contracts,
             CAST(AVG(vol) AS CHAR) AS avg_iv
      FROM option_chain
      WHERE act_symbol = '${sym}' AND date = '${latestDate}'
      GROUP BY expiration, call_put
      ORDER BY expiration ASC
      LIMIT 300
    `).catch(() => null);

    if (!aggCsv) continue;

    const aggLines = aggCsv.trim().split("\n");
    if (aggLines.length < 2) continue;

    // Accumulate per-expiry rows
    type Acc = {
      expiry: string;
      call_gamma_sum: number;
      put_gamma_sum: number;
      call_contracts: number;
      put_contracts: number;
      call_avg_iv: number | null;
      put_avg_iv: number | null;
    };
    const acc = new Map<string, Acc>();

    for (let i = 1; i < aggLines.length; i++) {
      const cols = parseCsvLine(aggLines[i]);
      if (cols.length < 5) continue;

      const expiry = cols[0];
      const callPut = cols[1].toLowerCase();
      const gammaSum = toFloat(cols[2]) ?? 0;
      const contracts = toInt(cols[3]);
      const avgIv = toFloat(cols[4]);

      if (!expiry) continue;

      if (!acc.has(expiry)) {
        acc.set(expiry, {
          expiry,
          call_gamma_sum: 0,
          put_gamma_sum: 0,
          call_contracts: 0,
          put_contracts: 0,
          call_avg_iv: null,
          put_avg_iv: null,
        });
      }

      const row = acc.get(expiry)!;
      if (callPut === "call") {
        row.call_gamma_sum = gammaSum;
        row.call_contracts = contracts;
        row.call_avg_iv = avgIv;
      } else {
        row.put_gamma_sum = gammaSum;
        row.put_contracts = contracts;
        row.put_avg_iv = avgIv;
      }
    }

    if (acc.size === 0) continue;

    const refDate = new Date(latestDate);
    const rows: DoltExpiryRow[] = Array.from(acc.values())
      .map((r) => {
        const expiryDate = new Date(r.expiry);
        const dte = Math.max(0, Math.round((expiryDate.getTime() - refDate.getTime()) / 86_400_000));
        return {
          expiry: r.expiry,
          dte,
          call_gamma_sum: r.call_gamma_sum,
          put_gamma_sum: r.put_gamma_sum,
          net_gamma_sum: r.call_gamma_sum - Math.abs(r.put_gamma_sum),
          call_contracts: r.call_contracts,
          put_contracts: r.put_contracts,
          call_avg_iv: r.call_avg_iv,
          put_avg_iv: r.put_avg_iv,
          source: "dolt" as const,
        };
      })
      .sort((a, b) => a.dte - b.dte);

    return { rows, resolvedSymbol: sym, date: latestDate };
  }

  return null;
}

// ---------------------------------------------------------------------------
// queryDoltVolatility
// ---------------------------------------------------------------------------

/**
 * Fetch the most recent IV/HV row from volatility_history for a symbol.
 */
export async function queryDoltVolatility(symbol: string): Promise<DoltVolatilityRow | null> {
  const candidates = toDoltSymbols(symbol);

  for (const sym of candidates) {
    const csv = await runDoltCsv(`
      SELECT date, act_symbol,
             CAST(iv_current AS CHAR), CAST(iv_week_ago AS CHAR), CAST(iv_month_ago AS CHAR),
             CAST(iv_year_high AS CHAR), iv_year_high_date,
             CAST(iv_year_low AS CHAR), iv_year_low_date,
             CAST(hv_current AS CHAR), CAST(hv_week_ago AS CHAR), CAST(hv_month_ago AS CHAR)
      FROM volatility_history
      WHERE act_symbol = '${sym}'
      ORDER BY date DESC
      LIMIT 1
    `).catch(() => null);

    if (!csv) continue;

    const lines = csv.trim().split("\n");
    if (lines.length < 2) continue;

    const cols = parseCsvLine(lines[1]);
    if (cols.length < 12) continue;

    return {
      date: cols[0],
      symbol: cols[1],
      iv_current: toFloat(cols[2]),
      iv_week_ago: toFloat(cols[3]),
      iv_month_ago: toFloat(cols[4]),
      iv_year_high: toFloat(cols[5]),
      iv_year_high_date: cols[6] || null,
      iv_year_low: toFloat(cols[7]),
      iv_year_low_date: cols[8] || null,
      hv_current: toFloat(cols[9]),
      hv_week_ago: toFloat(cols[10]),
      hv_month_ago: toFloat(cols[11]),
    };
  }

  return null;
}
