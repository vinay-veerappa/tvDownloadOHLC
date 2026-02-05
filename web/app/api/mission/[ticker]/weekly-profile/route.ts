
import { NextRequest, NextResponse } from 'next/server';
import { MissionControlService } from '@/lib/mission-control/service';

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ ticker: string }> }
) {
    try {
        const { ticker } = await params;
        const service = new MissionControlService(ticker);
        const data = await service.getWeeklyProfile();
        return NextResponse.json(data || {});
    } catch (error) {
        return NextResponse.json(
            { error: 'Failed to fetch weekly profile' },
            { status: 500 }
        );
    }
}
