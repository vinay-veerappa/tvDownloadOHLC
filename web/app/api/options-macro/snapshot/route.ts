import { NextResponse } from 'next/server';
import prisma from '@/lib/prisma';
import { MacroSnapshotData } from '@/types/macro';

export async function POST(request: Request) {
  try {
    const data: MacroSnapshotData = await request.json();
    console.log(`[API] Received snapshot for ${data.ticker} on ${data.tradingDate}`);

    if (!data.ticker || !data.tradingDate) {
      return NextResponse.json(
        { error: 'Missing required fields ticker or tradingDate' },
        { status: 400 }
      );
    }

    // Convert date strings to Date objects
    const timestamp = new Date(data.timestamp);
    const tradingDate = new Date(data.tradingDate);

    // Upsert the record based on ticker and tradingDate
    const snapshot = await prisma.macroSnapshot.upsert({
      where: {
        ticker_tradingDate: {
          ticker: data.ticker,
          tradingDate: tradingDate,
        },
      },
      update: {
        timestamp,
        spotPrice: data.spotPrice ?? 0,
        macroCallWall: data.macroCallWall,
        macroPutWall: data.macroPutWall,
        zeroGamma: data.zeroGamma,
        anomalies: data.anomalies ? JSON.stringify(data.anomalies) : null,
        dominantNodes: data.dominantNodes ? JSON.stringify(data.dominantNodes) : null,
      },
      create: {
        ticker: data.ticker,
        timestamp,
        tradingDate,
        spotPrice: data.spotPrice ?? 0,
        macroCallWall: data.macroCallWall,
        macroPutWall: data.macroPutWall,
        zeroGamma: data.zeroGamma,
        anomalies: data.anomalies ? JSON.stringify(data.anomalies) : null,
        dominantNodes: data.dominantNodes ? JSON.stringify(data.dominantNodes) : null,
      },
    });

    return NextResponse.json({ success: true, data: snapshot });
  } catch (error: any) {
    console.error('Error in options-macro snapshot POST:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error.message || String(error) },
      { status: 500 }
    );
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const ticker = searchParams.get('ticker') || 'SPX';

    const snapshot = await prisma.macroSnapshot.findFirst({
      where: { ticker },
      orderBy: { tradingDate: 'desc' },
    });

    if (!snapshot) {
      return NextResponse.json({ data: null });
    }

    // Parse the anomalies back from string to object array
    const parsedData: MacroSnapshotData = {
      ...snapshot,
      timestamp: snapshot.timestamp.toISOString(),
      tradingDate: snapshot.tradingDate.toISOString(),
      anomalies: snapshot.anomalies ? JSON.parse(snapshot.anomalies) : { structural: [], tactical: [] },
      dominantNodes: snapshot.dominantNodes ? JSON.parse(snapshot.dominantNodes) : [],
    };

    return NextResponse.json({ data: parsedData });
  } catch (error) {
    console.error('Error in options-macro snapshot GET:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
