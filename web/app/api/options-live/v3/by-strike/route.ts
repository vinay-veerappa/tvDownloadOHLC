import { NextRequest } from "next/server";
import { buildByStrike } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readStringParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const strikes = readIntParam(req, "strikes", 20, 5, 200);
  const expiryScope = readStringParam(req, "expiryScope", "all");
  const metricFamily = readStringParam(req, "metricFamily", "gamma");
  try {
    const { data, warnings } = await buildByStrike(symbol, strikes, expiryScope, metricFamily);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build by-strike view: ${String(error)}`, symbol);
  }
}
