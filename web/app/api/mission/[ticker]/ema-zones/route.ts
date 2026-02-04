import { NextRequest, NextResponse } from 'next/server';
import { isValidTicker } from '@/config/tickers';
import { calculateEMAZones } from '@/lib/mission-control/calculators/ema-zones';

/**
 * GET /api/mission/[ticker]/ema-zones
 * 
 * Returns EMA zone analysis for a ticker.
 */
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ ticker: string }> }
) {
    try {
        const { ticker } = await params;

        // Validate ticker
        if (!isValidTicker(ticker)) {
            return NextResponse.json(
                { error: `Invalid ticker: ${ticker}` },
                { status: 400 }
            );
        }

        // Calculate EMA zones
        const analysis = await calculateEMAZones(ticker);

        return NextResponse.json(analysis);
    } catch (error) {
        console.error('Error in /api/mission/[ticker]/ema-zones:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal server error' },
            { status: 500 }
        );
    }
}
