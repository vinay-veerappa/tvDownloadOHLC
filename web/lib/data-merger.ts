import { OHLCData } from "@/actions/data-actions"

/**
 * Merges historical base data with live-stored data.
 * 
 * Normalizes all timestamps to seconds (divides by 1000 if in milliseconds).
 * If a timestamp exists in both historical and live datasets, the live data overwrites the historical.
 * The final array is sorted chronologically.
 * 
 * @param historical Array of historical candles (from Parquet /api/ohlc)
 * @param live Array of live-stored candles (from Schwab cache /api/history)
 * @returns Deduplicated, chronologically sorted array of merged candles
 */
export function mergeDatasets(historical: OHLCData[], live: OHLCData[]): OHLCData[] {
    if (!historical || historical.length === 0) {
        return (live || []).map(normalizeCandle);
    }
    if (!live || live.length === 0) {
        return historical.map(normalizeCandle);
    }

    const histNormalized = historical.map(normalizeCandle);
    const liveNormalized = live.map(normalizeCandle);

    // Use Map to deduplicate. Since Map preserves insertion order of unique keys,
    // we insert historical first, then overwrite with live.
    const map = new Map<number, OHLCData>();
    
    for (const c of histNormalized) {
        map.set(c.time, c);
    }
    
    for (const c of liveNormalized) {
        map.set(c.time, c);
    }

    // Sort chronologically
    return Array.from(map.values()).sort((a, b) => a.time - b.time);
}

function normalizeCandle(c: OHLCData): OHLCData {
    return {
        ...c,
        time: c.time > 10000000000 ? c.time / 1000 : c.time
    };
}

