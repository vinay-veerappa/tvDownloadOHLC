import { NextRequest } from "next/server";
import { buildLevels } from "@/lib/options-live-v3/adapters";
import { ok, readSymbol, serverError } from "@/lib/options-live-v3/http";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function deriveExpectedMoveFromNotes(lines: string[] | undefined, spot: number | null | undefined) {
  if (!lines?.length || typeof spot !== "number" || !Number.isFinite(spot) || spot <= 0) {
    return { upper: null, lower: null, width: null };
  }

  const patterns = [
    /Expected Move is\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)/i,
    /Risk map:\s*EM\s*([\d,]+(?:\.\d+)?)\s*[↔→\-–—]\s*([\d,]+(?:\.\d+)?)/i,
  ];

  for (const line of lines) {
    const normalized = line.replace(/[ÂÏâ]/g, " ");
    for (const pattern of patterns) {
      const match = pattern.exec(normalized);
      if (!match) continue;
      const lowerRaw = Number(match[1].replace(/,/g, ""));
      const upperRaw = Number(match[2].replace(/,/g, ""));
      if (!Number.isFinite(lowerRaw) || !Number.isFinite(upperRaw) || upperRaw <= lowerRaw) continue;

      const widthRaw = (upperRaw - lowerRaw) / 2;
      const midRaw = (upperRaw + lowerRaw) / 2;
      if (widthRaw <= 0 || midRaw <= 0) continue;

      const scaledWidth = (widthRaw / midRaw) * spot;
      if (!Number.isFinite(scaledWidth) || scaledWidth <= 0) continue;

      return {
        upper: spot + scaledWidth,
        lower: spot - scaledWidth,
        width: scaledWidth,
      };
    }
  }

  return { upper: null, lower: null, width: null };
}

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  try {
    const { data, warnings } = await buildLevels(symbol);
    if (data.levels.expectedMoveWidth == null) {
      const derived = deriveExpectedMoveFromNotes(
        [...(data.notes.coach ?? []), ...(data.notes.tactical ?? [])],
        data.levels.spot ?? data.spot
      );
      if (derived.width != null) {
        data.levels.expectedMoveUpper = derived.upper;
        data.levels.expectedMoveLower = derived.lower;
        data.levels.expectedMoveWidth = derived.width;
      }
    }
    return ok(data, symbol, warnings);
  } catch (error) {
    return serverError(`Failed to build levels: ${String(error)}`, symbol);
  }
}
