"use server";
import fs from 'fs/promises';
import path from 'path';

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

        safeTicker = safeTicker.replace(/\//g, "-");

        let suffix = "";
        if (timeframe === "15s") suffix = "_15s";
        if (timeframe === "30s") suffix = "_30s";

        const filename = `live_chart_${safeTicker}${suffix}.json`;
        const filePath = path.join(process.cwd(), '..', 'data', 'live', filename);

        // --- Delta Logic (Optimized) ---
        if (since) {
            // Try reading Snapshot first (Fast Path)
            const snapPath = filePath.replace(".json", "_snapshot.json");
            let useSnapshot = false;
            let snapContent = "";

            try {
                snapContent = await fs.readFile(snapPath, 'utf-8');
                useSnapshot = true;
            } catch {
                // Snapshot missing, fallback to full
            }

            if (useSnapshot) {
                const snapData = JSON.parse(snapContent);
                const snapCandles = snapData.candles || [];

                // Check if snapshot covers the gap
                // If the oldest candle in snapshot is older than or equal to 'since', 
                // we have continuity.
                if (snapCandles.length > 0 && snapCandles[0].time <= since) {
                    const newCandles = snapCandles.filter((c: any) => c.time >= since);
                    return {
                        success: true,
                        data: {
                            ...snapData,
                            candles: newCandles
                        }
                    };
                }
            }

            // Fallback: Read Full File via API (Slow Path - only if client is stale or missing snapshot)
            try {
                const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=5000`, { cache: 'no-store' });
                if (apiRes.ok) {
                    const apiData = await apiRes.json();
                    if (apiData.candles) {
                        const newCandles = apiData.candles.filter((c: any) => c.time >= since);
                        return {
                            success: true,
                            data: {
                                ...apiData,
                                candles: newCandles,
                                last_update: new Date().toISOString(),
                                live_price: apiData.candles.length > 0 ? apiData.candles[apiData.candles.length - 1].close : null,
                            }
                        };
                    }
                }
            } catch (e) {
                // Ignore and fall through to full load
            }
        }

        // Full Load (First time or deep history) - Request from Python API
        try {
            const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=${limit || 180000}`, { cache: 'no-store' });
            if (!apiRes.ok) {
                 return { success: false, error: `Python API error: ${apiRes.statusText}` };
            }
            const apiData = await apiRes.json();
            
            if (apiData.error) {
                return { success: false, error: apiData.error };
            }

            // Return mock metadata so frontend doesn't break
            return { 
                success: true, 
                data: {
                    ...apiData,
                    last_update: new Date().toISOString(),
                    live_price: apiData.candles && apiData.candles.length > 0 ? apiData.candles[apiData.candles.length - 1].close : null,
                    totalCandles: apiData.candles?.length || 0
                } 
            };
        } catch (apiError: any) {
             return { success: false, error: `Failed to connect to Python Streamer API: ${apiError.message}` };
        }
    } catch (error: any) {
        return { success: false, error: error.message };
    }
}
