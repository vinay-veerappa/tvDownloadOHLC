import { NextRequest, NextResponse } from 'next/server';
import { isValidTicker } from '@/config/tickers';
import { calculateDistro } from '@/lib/mission-control/calculators/distro';

/**
 * GET /api/mission/[ticker]/distro
 * 
 * Returns Distro (Fuel) analysis for configured sessions.
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

        // Calculate Distro
        const analysis = await calculateDistro(ticker);

        return NextResponse.json(analysis);
    } catch (error) {
        console.error('Error in /api/mission/[ticker]/distro:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal server error' },
            { status: 500 }
        );
    }
}
