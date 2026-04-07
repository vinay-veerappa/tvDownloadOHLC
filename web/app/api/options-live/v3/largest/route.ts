import { NextRequest } from "next/server";
import { buildLargest } from "@/lib/options-live-v3/adapters";
import { ok, readIntParam, readStringParam, readSymbol } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const limit = readIntParam(req, "limit", 25, 1, 200);
  const sort = readStringParam(req, "sort", "abs_net");
  const expiryScope = readStringParam(req, "expiryScope", "all");
  const { data, warnings } = await buildLargest(symbol, limit, sort, expiryScope);
  return ok(data, symbol, warnings);
}
