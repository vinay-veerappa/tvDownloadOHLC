export type Resolution = string // e.g., "1", "5", "60", "240", "1D"

/**
 * Standardizes a resolution string to internal format.
 * - "1m" -> "1"
 * - "60m", "1h" -> "60"
 * - "1D" -> "1D"
 * - "1W" -> "1W"
 */
export function normalizeResolution(input: string): Resolution {
    if (!input) return "1"

    // Handle days/weeks first (case sensitive usually, but let's be robust)
    if (input.toUpperCase().endsWith('D')) return input.toUpperCase() // "1D"
    if (input.toUpperCase().endsWith('W')) return input.toUpperCase() // "1W"
    if (input.toUpperCase().endsWith('M') && !input.endsWith('m')) return input.toUpperCase() // "1M" (Month)

    // Handle minutes/hours/seconds
    const lower = input.toLowerCase()

    if (lower.endsWith('s')) {
        return input.toLowerCase() // "15s", "30s"
    }

    if (lower.endsWith('h')) {
        const hours = parseInt(lower.replace('h', ''))
        return (hours * 60).toString()
    }

    if (lower.endsWith('m')) {
        return parseInt(lower.replace('m', '')).toString()
    }

    // Assume raw number is minutes
    if (!isNaN(parseInt(input))) {
        return parseInt(input).toString()
    }

    return input // Fallback
}

/**
 * Formats a resolution for display.
 * - "1" -> "1m"
 * - "60" -> "1h"
 * - "240" -> "4h"
 * - "1D" -> "1D"
 * - "15s" -> "15s"
 */
export function formatResolution(res: Resolution): string {
    if (res.endsWith('D') || res.endsWith('W') || res.endsWith('M') || res.endsWith('s')) {
        return res
    }

    const mins = parseInt(res)
    if (isNaN(mins)) return res

    if (mins >= 60 && mins % 60 === 0) {
        return `${mins / 60}h`
    }

    return `${mins}m`
}

/**
 * Converts resolution to legacy folder name format.
 * - "1" -> "1m"
 * - "60" -> "1h"
 * - "240" -> "4h"
 * - "1440" (if passed) -> "1D" (though 1D usually passed as string)
 */
export function resolutionToFolderName(res: Resolution): string {
    if (res.endsWith('D') || res.endsWith('W') || res.endsWith('M')) {
        return res
    }
    if (res.endsWith('s')) {
        return res // Folders for seconds if we ever need them
    }

    const mins = parseInt(res)
    if (isNaN(mins)) return res

    // 1h, 4h convention for folders
    if (mins >= 60 && mins % 60 === 0) {
        return `${mins / 60}h`
    }

    return `${mins}m`
}

/**
 * Returns the duration of the resolution in minutes.
 * Useful for resampling calculations.
 */
export function getResolutionInMinutes(res: Resolution): number {
    if (res.endsWith('D')) return parseInt(res) * 1440
    if (res.endsWith('W')) return parseInt(res) * 10080
    if (res.endsWith('M')) return parseInt(res) * 43200 // Approx
    if (res.endsWith('s')) return parseInt(res) / 60

    return parseInt(res) || 1
}

/**
 * Checks if a resolution is intraday (minutes/hours).
 */
export function isIntraday(res: Resolution): boolean {
    return !res.endsWith('D') && !res.endsWith('W') && !res.endsWith('M')
}
