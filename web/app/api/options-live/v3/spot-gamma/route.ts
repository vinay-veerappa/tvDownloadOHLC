import { NextRequest } from "next/server";
import { buildSpotGamma } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readSymbol } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const smooth = readIntParam(req, "smooth", 1, 1, 5);
  const { data, warnings } = await buildSpotGamma(symbol, smooth);
  return ok(data, symbol, warnings);
}
