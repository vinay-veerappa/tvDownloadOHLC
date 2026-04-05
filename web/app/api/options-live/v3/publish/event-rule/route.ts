import path from "path";
import { readFile, writeFile } from "fs/promises";
import { NextRequest } from "next/server";
import { badRequest, ok, serverError } from "@/lib/options-live-v3/http";

const EVENT_RULES_PATH = path.join(process.cwd(), "..", "data", "event-rules.json");

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
    let rules: Record<string, unknown>[] = [];
    try {
      const raw = await readFile(EVENT_RULES_PATH, "utf-8");
      rules = JSON.parse(raw);
      if (!Array.isArray(rules)) rules = [];
    } catch {
      rules = [];
    }

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
