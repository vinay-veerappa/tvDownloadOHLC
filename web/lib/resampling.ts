import { OHLCData } from "@/actions/data-actions"

// Helper to parse timeframe string into seconds
// e.g., "1m" -> 60, "1h" -> 3600, "240" -> 14400
export function parseTimeframeToSeconds(tf: string): number {
    // Check for resolution string (number only)
    if (/^\d+$/.test(tf)) {
        return parseInt(tf, 10) * 60 // Default to minutes
    }

    // Strict case matching for units: m (min), h (hour), D (day), W (week), M (month), Y (year)
    // We allow 'd' and 'w' to leniently map to Day/Week, but 'm' MUST be minute and 'M' MUST be Month
    const match = tf.match(/^(\d+)(m|h|d|w|M|y)$/i)
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
        case 'y':
        case 'Y': return num * 60 * 60 * 24 * 365 // Approximate year
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
        resampled.push(currentBucket);
        // If weekly aggregation, add empty bucket for next week start
        if (isWeekly) {
            const nextWeekStart = currentBucket.time + 7 * 86400;
            resampled.push({ time: nextWeekStart, open: 0, high: 0, low: 0, close: 0, volume: 0 });
        }
    }

    return resampled;
}

// Function to check if we can resample from source to target
export function canResample(fromTF: string, toTF: string): boolean {
    const fromSeconds = parseTimeframeToSeconds(fromTF)
    const toSeconds = parseTimeframeToSeconds(toTF)

    // Valid if target is larger
    if (toSeconds <= fromSeconds) return false

    // AND target is not Daily/Weekly/Monthly (D, W, M)
    // We strictly check for 'D', 'W', 'M', 'd', 'w' but ALLOW 'm' (minutes) AND number-only strings
    if (toTF.match(/[DWM]$/)) return false // Uppercase D, W, M forbidden
    if (toTF.match(/[dw]$/)) return false  // Lowercase d, w forbidden (just in case)

    // 'm' (minutes) and raw resolution strings ("240") are allowed!
    return true
}

// Helper to resample Daily/Weekly/Monthly/Yearly on the client for fallback purposes
export function resampleDataForWMY(data: OHLCData[], targetTimeframe: string): OHLCData[] {
    if (data.length === 0) return data

    // Parse timeframe
    const isWeekly = targetTimeframe.toUpperCase().endsWith('W')
    const isMonthly = targetTimeframe.toUpperCase().endsWith('M')
    const isYearly = targetTimeframe.toUpperCase().endsWith('Y')

    let months = 1
    if (isMonthly) {
        const match = targetTimeframe.match(/^(\d+)M$/i)
        if (match) {
            months = parseInt(match[1], 10)
        }
    }
    let years = 1
    if (isYearly) {
        const match = targetTimeframe.match(/^(\d+)Y$/i)
        if (match) {
            years = parseInt(match[1], 10)
        }
    }

    const resampled: OHLCData[] = []
    let currentBucket: OHLCData | null = null
    let bucketEndTime = Number.NaN

    for (const candle of data) {
        const date = new Date(candle.time * 1000)
        let bucketStart = 0

        if (isWeekly) {
            const weekSeconds = 7 * 86400;
            bucketStart = Math.floor(candle.time / weekSeconds) * weekSeconds;
        } else if (isMonthly) {
            const year = date.getUTCFullYear()
            const month = date.getUTCMonth()
            const bucketMonth = Math.floor(month / months) * months
            const firstOfMonth = new Date(Date.UTC(year, bucketMonth, 1, 0, 0, 0, 0))
            bucketStart = Math.floor(firstOfMonth.getTime() / 1000)
        } else if (isYearly) {
            const year = date.getUTCFullYear()
            const bucketYear = Math.floor(year / years) * years
            const firstOfYear = new Date(Date.UTC(bucketYear, 0, 1, 0, 0, 0, 0))
            bucketStart = Math.floor(firstOfYear.getTime() / 1000)
        } else {
            // Fallback to simple seconds-based bucketing if it's something else
            const toSeconds = parseTimeframeToSeconds(targetTimeframe)
            if (toSeconds <= 0) return data
            bucketStart = Math.floor(candle.time / toSeconds) * toSeconds
        }

        if (bucketStart !== bucketEndTime) {
            if (currentBucket) resampled.push(currentBucket)
            currentBucket = { ...candle, time: bucketStart }
            bucketEndTime = bucketStart
        } else if (currentBucket) {
            currentBucket.high = Math.max(currentBucket.high, candle.high)
            currentBucket.low = Math.min(currentBucket.low, candle.low)
            currentBucket.close = candle.close
            currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0)
        }
    }
    if (currentBucket) resampled.push(currentBucket)
    return resampled
}

