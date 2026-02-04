/**
 * Mission Control - Timeframe Configuration
 * 
 * Defines configurable timeframes for multi-timeframe analysis.
 * Easily modified to add/remove timeframes as needed.
 */

export type Timeframe = '1W' | '1D' | '4H' | '1H' | '15m' | '5m';

/**
 * Timeframes for Premium/Discount analysis
 * Order matters: displayed top-to-bottom in UI
 */
export const PREMIUM_DISCOUNT_TIMEFRAMES: Timeframe[] = [
    '1W',   // Weekly
    '1D',   // Daily
    '4H',   // 4-Hour
    '1H',   // 1-Hour
    '15m',  // 15-Minute
];

/**
 * Timeframe display names
 */
export const TIMEFRAME_LABELS: Record<Timeframe, string> = {
    '1W': 'Weekly',
    '1D': 'Daily',
    '4H': '4-Hour',
    '1H': '1-Hour',
    '15m': '15-Minute',
    '5m': '5-Minute',
};

/**
 * Timeframe to minutes conversion
 * Used for calculations and comparisons
 */
export const TIMEFRAME_MINUTES: Record<Timeframe, number> = {
    '1W': 7 * 24 * 60,
    '1D': 24 * 60,
    '4H': 4 * 60,
    '1H': 60,
    '15m': 15,
    '5m': 5,
};

/**
 * Get display label for a timeframe
 */
export function getTimeframeLabel(tf: Timeframe): string {
    return TIMEFRAME_LABELS[tf] || tf;
}

/**
 * Get minutes for a timeframe
 */
export function getTimeframeMinutes(tf: Timeframe): number {
    return TIMEFRAME_MINUTES[tf];
}

/**
 * Parse timeframe string to Timeframe type
 */
export function parseTimeframe(tf: string): Timeframe {
    if (!isValidTimeframe(tf)) {
        throw new Error(`Invalid timeframe: ${tf}`);
    }
    return tf as Timeframe;
}

/**
 * Validate if a string is a valid timeframe
 */
export function isValidTimeframe(tf: string): tf is Timeframe {
    return tf in TIMEFRAME_LABELS;
}
