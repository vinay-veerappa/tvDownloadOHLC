import { NextRequest } from "next/server";
import { buildLevels } from "@/lib/options-live-v3/adapters";
import { ok, readSymbol, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  try {
    const { data, warnings } = await buildLevels(symbol);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build levels: ${String(error)}`, symbol);
  }
}
