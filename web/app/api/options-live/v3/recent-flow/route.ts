import { NextRequest } from "next/server";
import { buildRecentFlow } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const limit = readIntParam(req, "limit", 50, 1, 500);

  try {
    const { data, warnings } = await buildRecentFlow(symbol, limit);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build recent-flow view: ${String(error)}`, symbol);
  }
}
