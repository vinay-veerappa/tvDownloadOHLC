import { NextRequest, NextResponse } from 'next/server';
import { isValidTicker } from '@/config/tickers';
import { calculatePremiumDiscount } from '@/lib/mission-control/calculators/premium-discount';

/**
 * GET /api/mission/[ticker]/premium-discount
 * 
 * Returns Premium/Discount analysis across multiple timeframes.
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

        // Calculate Premium/Discount
        const analysis = await calculatePremiumDiscount(ticker);

        return NextResponse.json(analysis);
    } catch (error) {
        console.error('Error in /api/mission/[ticker]/premium-discount:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal server error' },
            { status: 500 }
        );
    }
}
