import { NextRequest } from "next/server";
import { buildPublishPreview } from "@/lib/options-live-v3/adapters";
import { badRequest, ok, serverError } from "@/lib/options-live-v3/http";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const symbol = typeof body?.symbol === "string" ? body.symbol : "SPY";
    if (!body?.mode) return badRequest("mode is required", symbol);
    const { data, warnings } = await buildPublishPreview(symbol, body.mode as string);
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Invalid JSON payload: ${String(error)}`);
  }
}
