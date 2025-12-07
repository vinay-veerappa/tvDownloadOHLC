import { OHLCData } from "@/actions/data-actions";

export interface VolumeProfileRow {
    price: number;
    vol: number;
}

export interface VolumeProfileData {
    time: number; // Anchor time (usually end of session or visible range)
    width: number; // Width in bars (visual width)
    profile: VolumeProfileRow[];
}

/**
 * Calculates a volume profile for the given data range.
 * @param data The OHLC data array
 * @param rowSize The price size of each row (bucket size). If null, auto-calculated.
 * @param rowCount Target number of rows if rowSize is not provided (default 24).
 */
export function calculateVolumeProfile(
    data: OHLCData[],
    rowSize: number | null = null,
    rowCount: number = 24
): VolumeProfileRow[] {
    if (!data.length) return [];

    let min = Infinity;
    let max = -Infinity;

    // 1. Find Min/Max
    for (const d of data) {
        if (d.low < min) min = d.low;
        if (d.high > max) max = d.high;
    }

    if (max === min) return [];

    // 2. Determine Step Size
    const range = max - min;
    const step = rowSize || (range / rowCount);

    // 3. Initialize Buckets
    // Map price_floor -> volume
    const buckets = new Map<number, number>();

    // 4. Populate Buckets
    for (const d of data) {
        // Simple approximation: assign total volume to the close price's bucket
        // A better approach splits volume across high-low, but strict VP usually uses tick data.
        // For OHLC, typical price or close price is standard.
        // Let's use Typical Price (H+L+C)/3
        const typ = (d.high + d.low + d.close) / 3;

        const bucketIndex = Math.floor((typ - min) / step);
        const bucketPrice = min + (bucketIndex * step);

        const currentVol = buckets.get(bucketPrice) || 0;
        buckets.set(bucketPrice, currentVol + (d.volume || 0));
    }

    // 5. Convert to Array and Sort
    const result: VolumeProfileRow[] = [];
    buckets.forEach((vol, price) => {
        result.push({ price, vol });
    });

    return result.sort((a, b) => b.price - a.price); // Top to bottom
}
