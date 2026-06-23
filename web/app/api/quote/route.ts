import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('ticker');

    if (!ticker) {
        return NextResponse.json({ error: 'Ticker required' }, { status: 400 });
    }

    try {
        const apiRes = await fetch(`http://127.0.0.1:8001/quote?symbol=${encodeURIComponent(ticker)}`, { cache: 'no-store' });
        
        if (apiRes.ok) {
            const data = await apiRes.json();
            return NextResponse.json(data);
        } else {
            return NextResponse.json({ error: 'Quote not found' }, { status: 404 });
        }
    } catch (e: any) {
        return NextResponse.json({ error: `Failed to fetch quote: ${e.message}` }, { status: 500 });
    }
}
