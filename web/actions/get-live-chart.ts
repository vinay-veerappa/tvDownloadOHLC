"use server";

import fs from 'fs/promises';
import path from 'path';

export async function getLiveChartData() {
    try {
        // Use live_chart.json which now contains the full session history (up to 5000 bars)
        const filePath = path.join(process.cwd(), '..', 'data', 'live_chart.json');

        try {
            await fs.access(filePath);
        } catch {
            return { success: false, error: 'Live data not available (Streamer not running)' };
        }

        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);

        return { success: true, data };
    } catch (error: any) {
        return { success: false, error: error.message };
    }
}
