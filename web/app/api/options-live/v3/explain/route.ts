import { NextRequest } from "next/server";
import { buildExplain } from "@/lib/options-live-v3/adapters";
import { badRequest, ok, readSymbol, readStringParam, serverError } from "@/lib/options-live-v3/http";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const snapshotId = readStringParam(req, "snapshotId", "");

  if (!snapshotId) {
    return badRequest("snapshotId is required", symbol);
  }

  try {
    const { data, warnings } = await buildExplain(symbol, snapshotId);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build explain payload: ${String(error)}`, symbol);
  }
}
