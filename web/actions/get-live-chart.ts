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

        try {
            await fs.access(filePath);
        } catch {
            return { success: false, error: `Live data not available for ${ticker}. Streamer might not be watching it.` };
        }

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

            // Fallback: Read Full File (Slow Path - only if client is stale)
            const content = await fs.readFile(filePath, 'utf-8');
            const data = JSON.parse(content);

            if (data.candles) {
                const newCandles = data.candles.filter((c: any) => c.time >= since);
                return {
                    success: true,
                    data: {
                        ...data,
                        candles: newCandles
                    }
                };
            }
        }

        // Full Load (First time) - Read Big File
        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);

        // Apply limit if specified (windowing for performance)
        if (limit && data.candles && data.candles.length > limit) {
            const startIndex = data.candles.length - limit;
            return {
                success: true,
                data: {
                    ...data,
                    candles: data.candles.slice(startIndex),
                    hasMore: true, // Indicate more data available
                    totalCandles: data.candles.length
                }
            };
        }

        return { success: true, data };
    } catch (error: any) {
        return { success: false, error: error.message };
    }
}
