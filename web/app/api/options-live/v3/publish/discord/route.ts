import { NextRequest } from "next/server";
import { buildPublishDiscord } from "@/lib/options-live-v3/adapters";
import { badRequest, ok, serverError } from "@/lib/options-live-v3/http";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const symbol = typeof body?.symbol === "string" ? body.symbol : "SPY";
    if (!body?.idempotencyKey) return badRequest("idempotencyKey is required", symbol);
    const channel = typeof body?.channel === "string" ? body.channel : "test_channel";
    const previewToken = typeof body?.previewToken === "string" ? body.previewToken : "";
    const mode = typeof body?.mode === "string" ? body.mode : "spot";
    const dryRun = body?.dryRun === true;
    const chartImageDataUrl = typeof body?.chartImageDataUrl === "string" ? body.chartImageDataUrl : undefined;
    const { data, warnings } = await buildPublishDiscord(
      symbol,
      channel,
      body.idempotencyKey as string,
      previewToken,
      mode,
      dryRun,
      chartImageDataUrl
    );
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Invalid JSON payload: ${String(error)}`);
  }
}
