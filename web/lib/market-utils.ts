export const SESSION_HOURS = {
    ASIAN: { start: 18, end: 2 },      // 6pm - 2am ET (Tokyo/Sydney)
    EUROPEAN: { start: 3, end: 8 },     // 3am - 8am ET (London open)
    US_PREMARKET: { start: 8, end: 9 }, // 8am - 9:30am ET
    US_REGULAR: { start: 9, end: 16 },  // 9:30am - 4pm ET
    AFTER_HOURS: { start: 16, end: 18 } // 4pm - 6pm ET
}

/**
 * Detects the trading session based on the provided date.
 * Returns: "US_REGULAR", "US_PREMARKET", "AFTER_HOURS", "ASIAN", "EUROPEAN", or "OVERNIGHT"
 */
export function detectSession(date: Date): string {
    const hour = date.getHours()
    const minutes = date.getMinutes()
    const timeDecimal = hour + minutes / 60

    if (timeDecimal >= 9.5 && timeDecimal < 16) return "US_REGULAR"
    if (timeDecimal >= 8 && timeDecimal < 9.5) return "US_PREMARKET"
    if (timeDecimal >= 16 && timeDecimal < 18) return "AFTER_HOURS"
    if (timeDecimal >= 18 || timeDecimal < 2) return "ASIAN"
    if (timeDecimal >= 3 && timeDecimal < 8) return "EUROPEAN"
    return "OVERNIGHT"
}

/**
 * Detects the trend based on entry price and previous close.
 */
export function detectTrend(entryPrice: number, prevClose?: number): string {
    if (!prevClose) return "UNKNOWN"
    const change = ((entryPrice - prevClose) / prevClose) * 100
    if (change > 0.5) return "TRENDING_UP"
    if (change < -0.5) return "TRENDING_DOWN"
    return "RANGING"
}
