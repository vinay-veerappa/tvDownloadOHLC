import { NextRequest } from "next/server";
import { buildNarrative } from "@/lib/options-live-v3/adapters";
import { ok, readStringParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const expiryScope = readStringParam(req, "expiryScope", "all");
  try {
    const { data, warnings } = await buildNarrative(symbol, expiryScope);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build narrative: ${String(error)}`, symbol);
  }
}
