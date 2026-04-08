import { NextRequest } from "next/server";
import fs from "fs/promises";
import path from "path";
import prisma from "@/lib/prisma";
import { ok, readIntParam, readStringParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const PRIORITY_FILE = path.join(REPO_ROOT, "priority_tickers.json");
const TRIGGER_FILE = path.join(REPO_ROOT, "manual_trigger.json");

type PriorityPayload = {
  action: "update_priority";
  priorityList: string[];
};

type RefreshPayload = {
  action: "refresh_ticker";
  ticker?: string;
};

type OpsPayload = PriorityPayload | RefreshPayload;

function cleanTicker(value: string): string {
  return value.trim().toUpperCase();
}

function normalizePriorityList(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of items) {
    const normalized = cleanTicker(raw);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(normalized);
  }
  return out;
}

function buildTickerCandidates(symbol: string): string[] {
  const root = cleanTicker(symbol).replace(/^\//, "");
  return [root, `/${root}`];
}

function getTradingDateET(): string {
  // Use New York trading-day date instead of UTC calendar date.
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

async function readPriorityList(): Promise<string[]> {
  try {
    const raw = await fs.readFile(PRIORITY_FILE, "utf-8");
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? normalizePriorityList(parsed) : [];
  } catch {
    return [];
  }
}

async function appendManualTrigger(ticker: string): Promise<void> {
  let existing: string[] = [];
  try {
    const raw = await fs.readFile(TRIGGER_FILE, "utf-8");
    const parsed = JSON.parse(raw) as string[];
    existing = Array.isArray(parsed) ? normalizePriorityList(parsed) : [];
  } catch {
    existing = [];
  }

  const normalizedTicker = cleanTicker(ticker);
  if (!existing.includes(normalizedTicker)) {
    existing.push(normalizedTicker);
    await fs.writeFile(TRIGGER_FILE, JSON.stringify(existing, null, 2), "utf-8");
  }
}

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const warnings: string[] = [];

  try {
    const limit = readIntParam(req, "limit", 300, 1, 1000);
    const dateParam = req.nextUrl.searchParams.get("date")?.trim();
    const date = dateParam && dateParam.length > 0 ? dateParam : getTradingDateET();
    const from = new Date(`${date}T00:00:00.000Z`);
    const to = new Date(from.getTime() + 24 * 60 * 60 * 1000);
    const tickerCandidates = buildTickerCandidates(symbol);

    const [priorityList, datedSnapshots] = await Promise.all([
      readPriorityList(),
      prisma.gexSnapshot.findMany({
        where: {
          ticker: { in: tickerCandidates },
          tradingDate: { gte: from, lt: to },
        },
        orderBy: { timestamp: "asc" },
        take: limit,
        select: {
          timestamp: true,
          totalGex: true,
          gexRegime: true,
          regimeLabel: true,
          spotPrice: true,
          gammaMagnet: true,
          pinStrike: true,
          totalGexDeltaAdj: true,
          netSpeedExposure: true,
          netVannaExposure: true,
        },
      }),
    ]);

    let snapshots = datedSnapshots;
    let effectiveDate = date;

    if (snapshots.length === 0 && !dateParam) {
      const latest = await prisma.gexSnapshot.findMany({
        where: { ticker: { in: tickerCandidates } },
        orderBy: [{ tradingDate: "desc" }, { timestamp: "desc" }],
        take: limit,
        select: {
          timestamp: true,
          totalGex: true,
          gexRegime: true,
          regimeLabel: true,
          spotPrice: true,
          gammaMagnet: true,
          pinStrike: true,
          totalGexDeltaAdj: true,
          netSpeedExposure: true,
          netVannaExposure: true,
          tradingDate: true,
        },
      });

      if (latest.length > 0) {
        snapshots = latest.map((row) => ({
          timestamp: row.timestamp,
          totalGex: row.totalGex,
          gexRegime: row.gexRegime,
          regimeLabel: row.regimeLabel,
          spotPrice: row.spotPrice,
          gammaMagnet: row.gammaMagnet,
          pinStrike: row.pinStrike,
          totalGexDeltaAdj: row.totalGexDeltaAdj,
          netSpeedExposure: row.netSpeedExposure,
          netVannaExposure: row.netVannaExposure,
        }));
        effectiveDate = latest[0].tradingDate.toISOString().slice(0, 10);
      }
    }

    if (priorityList.length === 0) {
      warnings.push("Priority ticker list is currently empty");
    }

    if (snapshots.length === 0) {
      warnings.push(`No snapshots found for ${symbol} on ${effectiveDate}`);
    }

    const payload = {
      symbol,
      date: effectiveDate,
      priorityList,
      snapshotSummary: {
        count: snapshots.length,
        firstTs: snapshots[0]?.timestamp.toISOString() ?? null,
        lastTs: snapshots[snapshots.length - 1]?.timestamp.toISOString() ?? null,
      },
      snapshots: snapshots.map((row) => ({
        timestamp: row.timestamp.toISOString(),
        totalGex: row.totalGex,
        totalGexDeltaAdj: row.totalGexDeltaAdj,
        gexRegime: row.gexRegime,
        regimeLabel: row.regimeLabel,
        spotPrice: row.spotPrice,
        gammaMagnet: row.gammaMagnet,
        pinStrike: row.pinStrike,
        netSpeedExposure: row.netSpeedExposure,
        netVannaExposure: row.netVannaExposure,
      })),
    };

    return ok(payload, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to load v3 ops data: ${String(error)}`, symbol);
  }
}

export async function POST(req: NextRequest) {
  const symbol = readSymbol(req);

  try {
    const body = (await req.json()) as OpsPayload;

    if (body.action === "update_priority") {
      if (!Array.isArray(body.priorityList)) {
        return ok({ updated: false, message: "priorityList must be an array" }, symbol, ["Invalid priority list payload"]);
      }
      const normalized = normalizePriorityList(body.priorityList);
      await fs.writeFile(PRIORITY_FILE, JSON.stringify(normalized, null, 2), "utf-8");
      return ok({ updated: true, priorityList: normalized, message: "Priority list updated" }, symbol);
    }

    if (body.action === "refresh_ticker") {
      const ticker = cleanTicker(body.ticker || symbol);
      if (!ticker) {
        return ok({ updated: false, message: "ticker is required" }, symbol, ["Missing ticker for refresh action"]);
      }
      await appendManualTrigger(ticker);
      return ok({ updated: true, ticker, message: `Refresh triggered for ${ticker}` }, symbol);
    }

    return ok({ updated: false, message: "Unsupported action" }, symbol, ["Unsupported ops action"]);
  } catch (error) {
    return serverError(`Failed to process v3 ops action: ${String(error)}`, symbol);
  }
}
