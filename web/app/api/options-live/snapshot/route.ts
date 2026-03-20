/**
 * POST /api/options-live/snapshot
 * --------------------------------
 * Receives a GexSnapshot payload from the Python pipeline (interval_writer.py)
 * and upserts it into the Prisma database.
 *
 * GET /api/options-live/snapshot?ticker=SPX&date=2026-03-19&limit=200
 * -----------------------------------------------------------------------
 * Returns intraday GEX history for a ticker/date, used by the GEX Trend chart
 * in the live dashboard as a richer alternative to live_trend.json.
 */

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

// ─── POST: write a new snapshot ───────────────────────────────────────────────
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    const {
      ticker,
      timestamp,
      tradingDate,
      totalGex,
      totalGexDeltaAdj,
      callGammaTotal,
      putGammaTotal,
      gexRegime,
      regimeLabel,
      spotPrice,
      gammaMagnet,
      pinStrike,
      callVolumeCentroid,
      putVolumeCentroid,
      netSpeedExposure,
      netVannaExposure,
    } = body;

    if (!ticker || !timestamp || !tradingDate || totalGex === undefined || !gexRegime || !spotPrice) {
      return NextResponse.json(
        { error: "Missing required fields: ticker, timestamp, tradingDate, totalGex, gexRegime, spotPrice" },
        { status: 400 }
      );
    }

    const snapshot = await prisma.gexSnapshot.create({
      data: {
        ticker,
        timestamp: new Date(timestamp),
        tradingDate: new Date(tradingDate),
        totalGex,
        totalGexDeltaAdj: totalGexDeltaAdj ?? null,
        callGammaTotal: callGammaTotal ?? null,
        putGammaTotal: putGammaTotal ?? null,
        gexRegime,
        regimeLabel: regimeLabel ?? null,
        spotPrice,
        gammaMagnet: gammaMagnet ?? null,
        pinStrike: pinStrike ?? null,
        callVolumeCentroid: callVolumeCentroid ?? null,
        putVolumeCentroid: putVolumeCentroid ?? null,
        netSpeedExposure: netSpeedExposure ?? null,
        netVannaExposure: netVannaExposure ?? null,
      },
    });

    return NextResponse.json({ id: snapshot.id, ticker: snapshot.ticker });
  } catch (err: any) {
    console.error("[GexSnapshot POST]", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

// ─── GET: fetch intraday history for a ticker ─────────────────────────────────
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const ticker = searchParams.get("ticker");
  const dateStr = searchParams.get("date"); // "YYYY-MM-DD"
  const limit = Math.min(parseInt(searchParams.get("limit") ?? "500", 10), 1000);

  if (!ticker) {
    return NextResponse.json({ error: "ticker is required" }, { status: 400 });
  }

  try {
    // Build date filter — if no date supplied, use today (ET)
    const targetDate = dateStr
      ? new Date(`${dateStr}T00:00:00.000Z`)
      : (() => {
          const now = new Date();
          // Shift to ET and floor to midnight
          const etOffset = -5 * 60; // rough EST offset in minutes
          const et = new Date(now.getTime() + etOffset * 60 * 1000);
          return new Date(`${et.toISOString().slice(0, 10)}T00:00:00.000Z`);
        })();
    const nextDate = new Date(targetDate.getTime() + 24 * 60 * 60 * 1000);

    const snapshots = await prisma.gexSnapshot.findMany({
      where: {
        ticker,
        tradingDate: { gte: targetDate, lt: nextDate },
      },
      orderBy: { timestamp: "asc" },
      take: limit,
      select: {
        timestamp: true,
        totalGex: true,
        totalGexDeltaAdj: true,
        callGammaTotal: true,
        putGammaTotal: true,
        gexRegime: true,
        regimeLabel: true,
        spotPrice: true,
        gammaMagnet: true,
        callVolumeCentroid: true,
        putVolumeCentroid: true,
        netSpeedExposure: true,
        netVannaExposure: true,
      },
    });

    return NextResponse.json({ ticker, date: dateStr, count: snapshots.length, snapshots });
  } catch (err: any) {
    console.error("[GexSnapshot GET]", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
