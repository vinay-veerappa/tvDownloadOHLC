import { NextRequest } from "next/server";
import { buildNarrative } from "@/lib/options-live-v3/adapters";
import { ok, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  try {
    const { data, warnings } = await buildNarrative(symbol);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build narrative: ${String(error)}`, symbol);
  }
}
