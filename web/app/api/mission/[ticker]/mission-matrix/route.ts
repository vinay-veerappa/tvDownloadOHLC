import { NextRequest, NextResponse } from 'next/server';
import { calculateMissionMatrix } from '@/lib/mission-control/calculators/mission-matrix';

export async function GET(
    request: NextRequest,
    context: { params: Promise<{ ticker: string }> }
) {
    const { ticker } = await context.params;

    try {
        const data = await calculateMissionMatrix(ticker);
        return NextResponse.json(data);
    } catch (error) {
        console.error(`Error calculating Mission Matrix for ${ticker}:`, error);
        return NextResponse.json(
            { error: 'Failed to calculate Mission Matrix' },
            { status: 500 }
        );
    }
}

