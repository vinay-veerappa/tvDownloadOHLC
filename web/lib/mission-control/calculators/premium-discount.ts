/**
 * Premium/Discount Calculator
 * 
 * Multi-timeframe analysis to determine if price is in Premium (upper 50%)
 * or Discount (lower 50%) zone of each timeframe's range.
 * Implementation follows CALCULATIONS.md specification.
 */

import { readParquetOHLC } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';

export type PremiumDiscountZone = 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM';

export interface TimeframeAnalysis {
    timeframe: string;
    range_high: number;
    range_low: number;
    equilibrium: number;
    current_price: number;
    zone: PremiumDiscountZone;
    position_pct: number; // 0% = at low, 50% = EQ, 100% = at high
}

export interface PremiumDiscountAnalysis {
    current_price: number;
    timeframes: TimeframeAnalysis[];
}

/**
 * Calculate Premium/Discount analysis across multiple timeframes
 */
export async function calculatePremiumDiscount(
    ticker: string,
    timeframes: string[] = ['1W', '1D', '4H', '1H', '15m']
): Promise<PremiumDiscountAnalysis> {
    const analyses: TimeframeAnalysis[] = [];
    let currentPrice = 0;

    for (const tf of timeframes) {
        try {
            const analysis = await analyzeTimeframe(ticker, tf);
            analyses.push(analysis);
            if (currentPrice === 0) {
                currentPrice = analysis.current_price;
            }
        } catch (error) {
            console.error(`Error analyzing ${tf} for ${ticker}:`, error);
            // Skip this timeframe if data not available
        }
    }

    return {
        current_price: currentPrice,
        timeframes: analyses,
    };
}

/**
 * Analyze a single timeframe
 */
async function analyzeTimeframe(
    ticker: string,
    timeframe: string
): Promise<TimeframeAnalysis> {
    // Map timeframe to parquet filename
    const tfMap: Record<string, string> = {
        '1W': '1w',
        '1D': '1d',
        '4H': '4h',
        '1H': '1h',
        '15m': '15m',
        '5m': '5m',
    };

    const filename = tfMap[timeframe] || timeframe.toLowerCase();
    const bars = await readParquetOHLC(ticker, filename);

    if (bars.length < 2) {
        throw new Error(`Insufficient data for ${timeframe}`);
    }

    // Use previous bar's range (completed bar)
    const prevBar = bars[bars.length - 2];
    const currentBar = bars[bars.length - 1];

    const rangeHigh = prevBar.high;
    const rangeLow = prevBar.low;
    const equilibrium = (rangeHigh + rangeLow) / 2;
    const currentPrice = currentBar.close;

    // Calculate position percentage
    const rangeSize = rangeHigh - rangeLow;
    let positionPct: number;

    if (rangeSize > 0) {
        positionPct = ((currentPrice - rangeLow) / rangeSize) * 100;
    } else {
        positionPct = 50; // No range = at equilibrium
    }

    // Determine zone (with 5% buffer around equilibrium)
    let zone: PremiumDiscountZone;
    if (positionPct > 55) {
        zone = 'PREMIUM';
    } else if (positionPct < 45) {
        zone = 'DISCOUNT';
    } else {
        zone = 'EQUILIBRIUM';
    }

    return {
        timeframe,
        range_high: rangeHigh,
        range_low: rangeLow,
        equilibrium,
        current_price: currentPrice,
        zone,
        position_pct: positionPct,
    };
}
