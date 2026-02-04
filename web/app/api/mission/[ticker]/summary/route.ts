import { NextRequest, NextResponse } from 'next/server';
import { isValidTicker } from '@/config/tickers';

/**
 * GET /api/mission/[ticker]/summary
 * 
 * Returns aggregated dashboard data for a ticker.
 * This is the primary endpoint for loading the dashboard.
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

        console.log(`[Summary API] Fetching data for ${ticker}...`);

        const { MissionControlService } = await import('@/lib/mission-control/service');
        const service = new MissionControlService(ticker);
        const data = await service.getSummary();

        console.log(`[Summary API] Data fetched for ${ticker}:`, {
            hasEmaZones: !!data.panels.emaZones,
            hasPremiumDiscount: !!data.panels.premiumDiscount,
            hasDistro: !!data.panels.distro,
        });

        return NextResponse.json(data);
    } catch (error) {
        console.error('Error in /api/mission/[ticker]/summary:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
