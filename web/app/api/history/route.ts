import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('symbol');
    const limit = searchParams.get('limit') || '180000';
    const interval = searchParams.get('interval') || '1d';

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

    let yfInterval = '1d';
    let period = '2y';
    if (interval === '1w' || interval === '1wk') {
        yfInterval = '1wk';
        period = '5y';
    } else if (interval === '1m' || interval === '1mo') {
        yfInterval = '1mo';
        period = 'max';
    } else if (interval === '3m' || interval === '3mo') {
        yfInterval = '3mo';
        period = 'max';
    }

    try {
        const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=${limit}`, { cache: 'no-store' });
        
        if (!apiRes.ok) {
            if (apiRes.status === 404) {
                // Fallback to local python yfinance execution for stocks not tracked in the streaming spoke
                try {
                    const pyPath = path.join(process.cwd(), '..', '.venv', 'Scripts', 'python.exe');
                    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'screener', 'fetch_ticker_profile.py');
                    const cmd = `"${pyPath}" "${scriptPath}" "${safeTicker}" "${yfInterval}" "${period}"`;
                    
                    const { stdout } = await execAsync(cmd, { timeout: 20000 });
                    const resJson = JSON.parse(stdout);
                    
                    if (!resJson.success) {
                        return NextResponse.json({ success: false, error: resJson.error }, { status: 404 });
                    }
                    
                    const candles = resJson.candles.map((c: any) => ({
                        time: c.time,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume || 0
                    }));
                    
                    return NextResponse.json({
                        success: true,
                        data: {
                            symbol: safeTicker,
                            candles,
                            info: resJson.info,
                            news: resJson.news,
                            upgrades: resJson.upgrades,
                            financials: resJson.financials,
                            last_update: new Date().toISOString(),
                            live_price: candles.length > 0 ? candles[candles.length - 1].close : null,
                            totalCandles: candles.length
                        }
                    });
                } catch (yfError: any) {
                    return NextResponse.json({ success: false, error: `yfinance fallback failed: ${yfError.message}` }, { status: 404 });
                }
            }
            return NextResponse.json({ success: false, error: `Python API error: ${apiRes.statusText}` }, { status: apiRes.status });
        }
        
        const apiData = await apiRes.json();
        
        if (apiData.error) {
            return NextResponse.json({ success: false, error: apiData.error }, { status: 400 });
        }

        // If it's a stock symbol (and not a futures contract starting with / or in roots), 
        // enrich it with yfinance metadata!
        let enrichedData: any = {};
        const isFuture = safeTicker.startsWith('/') || roots.includes(safeTicker);
        if (!isFuture) {
            try {
                const pyPath = path.join(process.cwd(), '..', '.venv', 'Scripts', 'python.exe');
                const scriptPath = path.join(process.cwd(), '..', 'scripts', 'screener', 'fetch_ticker_profile.py');
                const cmd = `"${pyPath}" "${scriptPath}" "${safeTicker}" "${yfInterval}" "${period}"`;
                
                const { stdout } = await execAsync(cmd, { timeout: 20000 });
                const resJson = JSON.parse(stdout);
                
                if (resJson.success) {
                    enrichedData = {
                        info: resJson.info,
                        news: resJson.news,
                        upgrades: resJson.upgrades,
                        financials: resJson.financials
                    };
                    // Optionally override candles if the local ones are empty/stale
                    if ((!apiData.candles || apiData.candles.length === 0) && resJson.candles) {
                        apiData.candles = resJson.candles;
                    }
                }
            } catch (yfError: any) {
                console.error('Failed to enrich metadata for tracked stock:', yfError.message);
            }
        }

        return NextResponse.json({
            success: true,
            data: {
                ...apiData,
                ...enrichedData,
                last_update: new Date().toISOString(),
                live_price: apiData.candles && apiData.candles.length > 0 ? apiData.candles[apiData.candles.length - 1].close : null,
                totalCandles: apiData.candles?.length || 0
            }
        });
    } catch (e: any) {
        return NextResponse.json({ success: false, error: `Proxy error: ${e.message}` }, { status: 500 });
    }
}
