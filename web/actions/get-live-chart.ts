"use server";
import fs from 'fs/promises';
import path from 'path';

export async function getLiveChartData(ticker: string = "/NQ", timeframe: string = "1") {
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
        const filePath = path.join(process.cwd(), '..', 'data', filename);

        try {
            await fs.access(filePath);
        } catch {
            return { success: false, error: `Live data not available for ${ticker}. Streamer might not be watching it.` };
        }

        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);

        return { success: true, data };
    } catch (error: any) {
        return { success: false, error: error.message };
    }
}
