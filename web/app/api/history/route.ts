import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('symbol');
    const limit = searchParams.get('limit') || '180000';

    if (!ticker) {
        return NextResponse.json({ success: false, error: 'Missing symbol' }, { status: 400 });
    }

    // Map TradingView continuous tickers (e.g., NQ1!) back to futures roots (/NQ)
    let safeTicker = ticker;
    const roots = ["ES", "NQ", "YM", "RTY", "CL", "GC"];
    const root = ticker.replace(/1!$/, "");
    if (roots.includes(root)) {
        safeTicker = "/" + root;
    }

    try {
        const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=${limit}`, { cache: 'no-store' });
        
        if (!apiRes.ok) {
            return NextResponse.json({ success: false, error: `Python API error: ${apiRes.statusText}` }, { status: apiRes.status });
        }
        
        const apiData = await apiRes.json();
        
        if (apiData.error) {
            return NextResponse.json({ success: false, error: apiData.error }, { status: 400 });
        }

        return NextResponse.json({
            success: true,
            data: {
                ...apiData,
                last_update: new Date().toISOString(),
                live_price: apiData.candles && apiData.candles.length > 0 ? apiData.candles[apiData.candles.length - 1].close : null,
                totalCandles: apiData.candles?.length || 0
            }
        });
    } catch (e: any) {
        return NextResponse.json({ success: false, error: `Proxy error: ${e.message}` }, { status: 500 });
    }
}
