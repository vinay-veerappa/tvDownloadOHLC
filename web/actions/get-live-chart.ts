"use server";
import fs from 'fs/promises';
import path from 'path';

export async function getLiveChartData(ticker: string = "/NQ") {
    try {
        // Sanitize ticker to match python script logic (replace / with -)
        const safeTicker = ticker.replace(/\//g, "-");
        const filename = `live_chart_${safeTicker}.json`;
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
