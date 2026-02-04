/**
 * Candle Science Calculator
 * 
 * Projects C3 distribution based on C1-C2 patterns.
 * Implementation follows CALCULATIONS.md specification.
 */

import { readParquetOHLC } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';

export interface C3Projection {
    bullish_pct: number;
    bearish_pct: number;
    sample_size: number;
    patterns: {
        c1: number;
        c2: number;
    };
    probabilities: {
        close_above_c2_high: number;
        close_below_c2_low: number;
        high_above_c2_high: number;
        low_below_c2_low: number;
    };
}

/**
 * Classify a candle into an 8-bit pattern
 */
export function classifyCandle(bar: OHLCBar): number {
    let pattern = 0;
    const bodySize = Math.abs(bar.close - bar.open);
    const rangeSize = bar.high - bar.low || 1;
    const midPoint = (bar.high + bar.low) / 2;

    // 1. Bullish body
    if (bar.close > bar.open) pattern |= 0b00000001;
    // 2. Close in upper half
    if (bar.close > midPoint) pattern |= 0b00000010;
    // 3. Large body (> 50% of range)
    if (bodySize > rangeSize * 0.5) pattern |= 0b00000100;
    // 4. Close near high (< 10% from high)
    if (bar.high - bar.close < rangeSize * 0.1) pattern |= 0b00001000;
    // 5. Open near low (< 10% from low)
    if (bar.open - bar.low < rangeSize * 0.1) pattern |= 0b00010000;
    // 6. Gap up from prev close (handled in sequence logic usually, but here as self-contained)
    // 7. & 8. Reserved for wick comparisons

    return pattern;
}

/**
 * Calculate C3 projection for a ticker
 */
export async function calculateCandleScience(
    ticker: string,
    lookbackDays: number = 250
): Promise<C3Projection | null> {
    const bars = await readParquetOHLC(ticker, '1d');
    if (bars.length < 3) return null;

    // Get current C1 (2 days ago) and C2 (yesterday)
    const c1_curr = bars[bars.length - 2];
    const c2_curr = bars[bars.length - 1];
    const p1 = classifyCandle(c1_curr);
    const p2 = classifyCandle(c2_curr);

    let matches = 0;
    let bullish = 0;
    let caH = 0; // Close above High
    let cbL = 0; // Close below Low
    let haH = 0; // High above High
    let laL = 0; // Low below Low

    // Historically scan (excluding the very recent ones we used for C1/C2)
    for (let i = 2; i < bars.length - 1; i++) {
        const h_c1 = bars[i - 2];
        const h_c2 = bars[i - 1];
        const h_c3 = bars[i];

        if (classifyCandle(h_c1) === p1 && classifyCandle(h_c2) === p2) {
            matches++;
            if (h_c3.close > h_c3.open) bullish++;
            if (h_c3.close > h_c2.high) caH++;
            if (h_c3.close < h_c2.low) cbL++;
            if (h_c3.high > h_c2.high) haH++;
            if (h_c3.low < h_c2.low) laL++;
        }
    }

    if (matches < 5) return null; // Insufficient statistical sample

    return {
        bullish_pct: (bullish / matches) * 100,
        bearish_pct: ((matches - bullish) / matches) * 100,
        sample_size: matches,
        patterns: { c1: p1, c2: p2 },
        probabilities: {
            close_above_c2_high: (caH / matches) * 100,
            close_below_c2_low: (cbL / matches) * 100,
            high_above_c2_high: (haH / matches) * 100,
            low_below_c2_low: (laL / matches) * 100
        }
    };
}
