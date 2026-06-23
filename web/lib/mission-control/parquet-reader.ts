/**
 * Data Reader
 * 
 * Utility for reading OHLC data from chunked JSON files in public/data.
 * Replaces previous Parquet-based implementation for better performance and stability.
 */

import * as path from 'path';
import * as fs from 'fs/promises';
import { existsSync } from 'fs';

export interface OHLCBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

interface ChunkMeta {
    ticker: string;
    timeframe: string;
    totalBars: number;
    chunkSize: number;
    numChunks: number;
    startTime: number;
    endTime: number;
    chunks: {
        index: number;
        startTime: number;
        endTime: number;
        bars: number;
    }[];
}

/**
 * Read OHLC data from chunked JSON files
 * Reads the most recent data by default (Chunk 0 = newest)
 */
export async function readParquetOHLC(
    ticker: string,
    timeframe: string
): Promise<OHLCBar[]> {
    // For compatibility, this reads ALL data if called without limits
    // But realistically we usually want recent bars. This method is dangerous for massive datasets.
    // We will warn and just return recent bars (e.g. last 5 chunks) to prevent OOM.

    return readRecentBars(ticker, timeframe, 50000); // Default to reasonable limit (approx 35 days of 1m data)
}

/**
 * Read the most recent N bars from chunked JSON files, including live data
 */
export async function readRecentBars(
    ticker: string,
    timeframe: string,
    count: number
): Promise<OHLCBar[]> {
    // 1. Locate data directory: web/public/data/{ticker}_{timeframe}
    const dataDir = path.join(process.cwd(), 'public', 'data', `${ticker}_${timeframe}`);
    const metaPath = path.join(dataDir, 'meta.json');

    let loadedBars: OHLCBar[] = [];

    // --- Part A: Read Historical Chunks ---
    if (existsSync(metaPath)) {
        try {
            const metaContent = await fs.readFile(metaPath, 'utf-8');
            const meta: ChunkMeta = JSON.parse(metaContent);

            let chunkIndex = 0;
            while (loadedBars.length < count && chunkIndex < meta.numChunks) {
                const chunkPath = path.join(dataDir, `chunk_${chunkIndex}.json`);

                if (existsSync(chunkPath)) {
                    const chunkContent = await fs.readFile(chunkPath, 'utf-8');
                    const rawData = JSON.parse(chunkContent);

                    const bars: OHLCBar[] = rawData.map((r: any) => ({
                        timestamp: r.time * 1000,
                        open: r.open,
                        high: r.high,
                        low: r.low,
                        close: r.close,
                        volume: r.volume
                    }));

                    // Prepend older chunk's bars to our collection
                    loadedBars = bars.concat(loadedBars);
                }
                chunkIndex++;
            }
        } catch (error) {
            console.error(`Error reading historical data for ${ticker}:`, error);
        }
    }

    // --- Part B: Read Live Data ---
    try {
        const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
        const clean = ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
        const root = clean.replace(/\d+$/, "");
        const safeTicker = roots.includes(root) ? `/${root}` : ticker;

        const apiRes = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=5000`, { cache: 'no-store' });
        if (apiRes.ok) {
            const apiData = await apiRes.json();
            if (apiData && apiData.candles && Array.isArray(apiData.candles)) {
                const liveBars: OHLCBar[] = apiData.candles.map((c: any) => ({
                    timestamp: c.time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume
                }));

                const lastHistTime = loadedBars.length > 0 ? loadedBars[loadedBars.length - 1].timestamp : 0;
                if (timeframe === '1m' || timeframe === '1') {
                    const newLiveBars = liveBars.filter(b => b.timestamp > lastHistTime);
                    loadedBars = loadedBars.concat(newLiveBars);
                } else if (timeframe === '1d' || timeframe === 'D') {
                    const lastBar = liveBars[liveBars.length - 1];
                    const dailyCandle: OHLCBar = {
                        timestamp: lastBar.timestamp,
                        open: liveBars[0].open,
                        high: liveBars.reduce((max, b) => Math.max(max, b.high), -Infinity),
                        low: liveBars.reduce((min, b) => Math.min(min, b.low), Infinity),
                        close: lastBar.close,
                        volume: liveBars.reduce((sum, b) => sum + (b.volume || 0), 0)
                    };
                    loadedBars.push(dailyCandle);
                }
            }
        }
    } catch (error) {
        console.error(`Error processing live data from Spoke API for ${ticker}:`, error);
    }

    // Return requested count (sliced from the end)
    return loadedBars.slice(-count);
}

/**
 * Calculate Simple Moving Average
 */
export function calculateSMA(values: number[], period: number): number[] {
    const sma: number[] = [];

    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            sma.push(NaN);
            continue;
        }

        const sum = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
        sma.push(sum / period);
    }

    return sma;
}

/**
 * Calculate Exponential Moving Average
 */
export function calculateEMA(values: number[], period: number): number[] {
    const ema: number[] = [];
    const multiplier = 2 / (period + 1);

    // Start with SMA for first value
    let sum = 0;
    for (let i = 0; i < period; i++) {
        if (i >= values.length) break;
        sum += values[i];
    }

    if (values.length < period) {
        return values.map(() => NaN);
    }

    ema[period - 1] = sum / period;

    // Calculate EMA for remaining values
    for (let i = period; i < values.length; i++) {
        ema[i] = (values[i] - ema[i - 1]) * multiplier + ema[i - 1];
    }

    // Fill initial NaN values
    for (let i = 0; i < period - 1; i++) {
        ema[i] = NaN;
    }

    return ema;
}
