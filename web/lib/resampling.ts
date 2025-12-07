import { OHLCData } from "@/actions/data-actions"

// Helper to parse timeframe string into seconds
// e.g., "1m" -> 60, "1h" -> 3600
export function parseTimeframeToSeconds(tf: string): number {
    // Strict case matching for units: m (min), h (hour), D (day), W (week), M (month)
    // We allow 'd' and 'w' to leniently map to Day/Week, but 'm' MUST be minute and 'M' MUST be Month
    const match = tf.match(/^(\d+)(m|h|d|w|M)$/i)
    if (!match) return 0

    const [, numStr, unit] = match
    const num = parseInt(numStr, 10)

    // Use raw unit for m/M distinction
    switch (unit) {
        case 'm': return num * 60
        case 'h':
        case 'H': return num * 60 * 60
        case 'd':
        case 'D': return num * 60 * 60 * 24
        case 'w':
        case 'W': return num * 60 * 60 * 24 * 7
        case 'M': return num * 60 * 60 * 24 * 30 // Approximate month
        default: return 0
    }
}

// Main resampling function
// Aggregates lower timeframe data into higher timeframe buckets
export function resampleOHLC(data: OHLCData[], fromTF: string, toTF: string): OHLCData[] {
    const fromSeconds = parseTimeframeToSeconds(fromTF)
    const toSeconds = parseTimeframeToSeconds(toTF)

    // Validation
    if (fromSeconds === 0 || toSeconds === 0) {
        console.error(`Invalid timeframes: ${fromTF} -> ${toTF}`)
        return []
    }

    if (toSeconds <= fromSeconds) {
        // Target TF is smaller or equal, return original data
        // (Downsampling not supported, equal doesn't need resampling)
        return data
    }

    // Daily/Weekly handling: STRICTLY prohibit resampling to D/W/M
    // User requested to rely on native files for these to ensure settlement time accuracy
    // Check for D, W, M in the suffix
    if (toTF.match(/[DWM]$/) || toTF.match(/[dw]$/)) {
        console.warn(`Resampling to ${toTF} is not supported (Daily/Weekly require native data)`)
        return []
    }

    if (data.length === 0) return []

    const resampled: OHLCData[] = []
    let currentBucket: OHLCData | null = null
    let bucketEndTime = Number.NaN // Initialize to NaN so first comparison (valid_ts !== NaN) is always true

    for (const candle of data) {
        // Calculate which bucket this candle belongs to
        // We align to the start of the bucket (e.g., 10:00:00 for 10:00-10:05 bucket)
        const timestamp = candle.time
        const bucketStart = Math.floor(timestamp / toSeconds) * toSeconds

        // If this is a new bucket
        if (bucketStart !== bucketEndTime) {
            // Push previous bucket if complete
            if (currentBucket) {
                resampled.push(currentBucket)
            }

            // Start new bucket
            currentBucket = {
                time: bucketStart,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
                volume: candle.volume || 0
            }
            bucketEndTime = bucketStart
        } else if (currentBucket) {
            // Aggregate into current bucket
            currentBucket.high = Math.max(currentBucket.high, candle.high)
            currentBucket.low = Math.min(currentBucket.low, candle.low)
            currentBucket.close = candle.close // Close is always the last candle's close
            currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0)
        }
    }

    // Push final bucket
    if (currentBucket) {
        resampled.push(currentBucket)
    }

    return resampled
}

// Function to check if we can resample from source to target
export function canResample(fromTF: string, toTF: string): boolean {
    const fromSeconds = parseTimeframeToSeconds(fromTF)
    const toSeconds = parseTimeframeToSeconds(toTF)

    // Valid if target is larger
    if (toSeconds <= fromSeconds) return false

    // AND target is not Daily/Weekly/Monthly (D, W, M)
    // We strictly check for 'D', 'W', 'M', 'd', 'w' but ALLOW 'm' (minutes)
    if (toTF.match(/[DWM]$/)) return false // Uppercase D, W, M forbidden
    if (toTF.match(/[dw]$/)) return false  // Lowercase d, w forbidden (just in case)

    // 'm' (minutes) is allowed!
    return true
}
