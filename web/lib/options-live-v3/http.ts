import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import type { V3Meta } from "@/lib/options-live-v3/contracts/types";

const DEFAULT_SYMBOL = "SPY";

// ---------------------------------------------------------------------------
// Zod envelope validation (only runs in development to avoid prod overhead)
// ---------------------------------------------------------------------------

const v3MetaSchema = z.object({
  symbol: z.string(),
  asOf: z.string(),
  freshnessMs: z.number(),
  source: z.string(),
  computeVersion: z.string(),
  adapterVersion: z.string(),
});

const v3EnvelopeSchema = z.object({
  success: z.boolean(),
  data: z.unknown(),
  meta: v3MetaSchema,
  warnings: z.array(z.string()),
  error: z.string().nullable(),
});

function validateEnvelope(payload: unknown): void {
  if (process.env.NODE_ENV !== "development") return;
  const result = v3EnvelopeSchema.safeParse(payload);
  if (!result.success) {
    console.warn("[V3] Envelope validation failed:", result.error.issues);
  }
}

export function readSymbol(req: NextRequest): string {
  const symbol = req.nextUrl.searchParams.get("symbol")?.trim();
  return symbol && symbol.length > 0 ? symbol.toUpperCase() : DEFAULT_SYMBOL;
}

export function readIntParam(
  req: NextRequest,
  name: string,
  fallback: number,
  min?: number,
  max?: number
): number {
  const raw = req.nextUrl.searchParams.get(name);
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed)) return fallback;

  let value = parsed;
  if (typeof min === "number") value = Math.max(min, value);
  if (typeof max === "number") value = Math.min(max, value);
  return value;
}

export function readStringParam(req: NextRequest, name: string, fallback: string): string {
  const raw = req.nextUrl.searchParams.get(name)?.trim();
  return raw && raw.length > 0 ? raw : fallback;
}

export function buildMeta(symbol: string): V3Meta {
  return {
    symbol,
    asOf: new Date().toISOString(),
    freshnessMs: 0,
    source: "options-live-v3-stub",
    computeVersion: "v3-draft",
    adapterVersion: "v1",
  };
}

export function ok(data: unknown, symbol = DEFAULT_SYMBOL, warnings: string[] = []) {
  const payload = {
    success: true,
    data,
    meta: buildMeta(symbol),
    warnings,
    error: null,
  };
  validateEnvelope(payload);
  return NextResponse.json(payload);
}

export function badRequest(message: string, symbol = DEFAULT_SYMBOL) {
  return NextResponse.json(
    {
      success: false,
      data: null,
      meta: buildMeta(symbol),
      warnings: [],
      error: message,
    },
    { status: 400 }
  );
}

export function serverError(message: string, symbol = DEFAULT_SYMBOL) {
  return NextResponse.json(
    {
      success: false,
      data: null,
      meta: buildMeta(symbol),
      warnings: [],
      error: message,
    },
    { status: 500 }
  );
}
