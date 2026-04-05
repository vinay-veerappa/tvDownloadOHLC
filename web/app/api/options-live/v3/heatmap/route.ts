import { NextRequest } from "next/server";
import { buildHeatmap } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readStringParam, readSymbol } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const market = readStringParam(req, "market", "spx");
  const mode = readStringParam(req, "mode", "pcr");
  const metric = readStringParam(req, "metric", "net_gex");
  const strikes = readIntParam(req, "strikes", 20, 5, 200);
  const expiryMode = readStringParam(req, "expiryMode", "bucketed");
  const { data, warnings } = await buildHeatmap(symbol, market, mode, metric, strikes, expiryMode);
  return ok(data, symbol, warnings);
}
