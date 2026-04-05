import path from "path";
import { readFile, writeFile } from "fs/promises";
import { NextRequest } from "next/server";
import { badRequest, ok, serverError } from "@/lib/options-live-v3/http";

const EVENT_RULES_PATH = path.join(process.cwd(), "..", "data", "event-rules.json");

async function loadRules(): Promise<Record<string, unknown>[]> {
  try {
    const raw = await readFile(EVENT_RULES_PATH, "utf-8");
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const symbol = searchParams.get("symbol");
    const rules = await loadRules();
    const filtered = symbol
      ? rules.filter((r) => (r as { symbol?: string }).symbol === symbol)
      : rules;
    return ok({ rules: filtered }, symbol ?? "all", []);
  } catch (error) {
    return serverError(`event-rule GET error: ${String(error)}`);
  }
}

export async function DELETE(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const ruleName = searchParams.get("ruleName");
    if (!ruleName) return badRequest("ruleName query param is required", "unknown");

    const rules = await loadRules();
    const before = rules.length;
    const updated = rules.filter((r) => (r as { ruleName?: string }).ruleName !== ruleName);
    await writeFile(EVENT_RULES_PATH, JSON.stringify(updated, null, 2), "utf-8");
    return ok({ deleted: before - updated.length, ruleName }, "unknown", []);
  } catch (error) {
    return serverError(`event-rule DELETE error: ${String(error)}`);
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const symbol = typeof body?.symbol === "string" ? body.symbol : "SPY";
    if (!body?.ruleName) return badRequest("ruleName is required", symbol);

    const ruleName = body.ruleName as string;
    const cronExpr = typeof body?.cron === "string" ? body.cron : "0 9 * * 1-5";
    const mode = typeof body?.mode === "string" ? body.mode : "brief";
    const channel = typeof body?.channel === "string" ? body.channel : "test_channel";

    // Read existing rules (or start fresh)
    const rules = await loadRules();

    // Upsert by ruleName
    const existing = rules.findIndex((r) => (r as { ruleName: string }).ruleName === ruleName);
    const ruleEntry = { ruleName, symbol, cron: cronExpr, mode, channel, updatedAt: new Date().toISOString() };
    if (existing >= 0) rules[existing] = ruleEntry;
    else rules.push(ruleEntry);

    await writeFile(EVENT_RULES_PATH, JSON.stringify(rules, null, 2), "utf-8");

    return ok(
      { implemented: true, module: "publish-event-rule", symbol, ruleName, cron: cronExpr, mode, channel, ruleId: ruleName },
      symbol,
      []
    );
  } catch (error) {
    return serverError(`event-rule error: ${String(error)}`);
  }
}
