import { NextRequest } from "next/server";
import { buildByExpiryTrue } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readStringParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const strikes = readIntParam(req, "strikes", 20, 5, 200);
  const metricFamily = readStringParam(req, "metricFamily", "gamma");
  const expiryScope = readStringParam(req, "expiryScope", "all");

  try {
    const { data, warnings } = await buildByExpiryTrue(symbol, strikes, metricFamily, expiryScope);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build by-expiry view: ${String(error)}`, symbol);
  }
}
