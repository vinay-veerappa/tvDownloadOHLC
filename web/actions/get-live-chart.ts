"use server";

export async function getLiveChartData(ticker: string = "/NQ", timeframe: string = "1", since?: number, limit?: number) {
    try {
        // Normalization Logic (Mirroring frontend/hooks)
        let safeTicker = ticker;
        const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
        const clean = ticker.replace(/[^a-zA-Z]/g, "").toUpperCase(); // Remove '1', '!', '/'
        const root = clean.replace(/\d+$/, "");

        if (roots.includes(root)) {
            safeTicker = "/" + root;
        }

        // Request from Python API
        try {
            const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=${limit || 180000}`, { cache: 'no-store' });
            if (!apiRes.ok) {
                 return { success: false, error: `Python API error: ${apiRes.statusText}` };
            }
            const apiData = await apiRes.json();
            
            if (apiData.error) {
                return { success: false, error: apiData.error };
            }

            let candles = apiData.candles || [];
            if (since) {
                candles = candles.filter((c: any) => c.time >= since);
            }

            return { 
                success: true, 
                data: {
                    ...apiData,
                    candles,
                    last_update: new Date().toISOString(),
                    live_price: candles.length > 0 ? candles[candles.length - 1].close : null,
                    totalCandles: candles.length
                } 
            };
        } catch (apiError: any) {
             return { success: false, error: `Failed to connect to Python Streamer API: ${apiError.message}` };
        }
    } catch (error: any) {
        return { success: false, error: error.message };
    }
}
