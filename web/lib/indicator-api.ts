/**
 * API client for Python Indicator Service
 * 
 * This client sends OHLCV data from the chart to the Python backend
 * for indicator calculations, ensuring 100% consistency between
 * displayed data and indicator values.
 */

import { OHLCData } from "@/actions/data-actions"

const API_BASE_URL = process.env.NEXT_PUBLIC_INDICATOR_API_URL || "http://localhost:8000"

export interface IndicatorResult {
    time: number[]
    indicators: Record<string, (number | null)[]>
}

/**
 * Calculate indicators from chart OHLCV data via Python API
 * 
 * @param ohlcv - The OHLCV data array from the chart
 * @param indicators - List of indicators to calculate (e.g., ["vwap", "sma_20", "ema_9"])
 * @returns Calculated indicator values aligned with time series
 */
export async function calculateIndicators(
    ohlcv: OHLCData[],
    indicators: string[]
): Promise<IndicatorResult | null> {
    if (!ohlcv.length || !indicators.length) {
        return null
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/indicators/calculate`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                ohlcv: ohlcv.map(bar => ({
                    time: bar.time,
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close,
                    volume: bar.volume || 0
                })),
                indicators
            }),
        })

        if (!response.ok) {
            console.error(`Indicator API error: ${response.status}`)
            return null
        }

        return await response.json()
    } catch (error) {
        console.error("Failed to calculate indicators:", error)
        return null
    }
}

/**
 * Get list of available indicators from the API
 */
export async function getAvailableIndicators(): Promise<{ name: string; description: string }[] | null> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/indicators/available`)
        if (!response.ok) return null
        const data = await response.json()
        return data.indicators
    } catch (error) {
        console.error("Failed to get available indicators:", error)
        return null
    }
}

/**
 * Convert Python API indicator format to Lightweight Charts line data format
 * 
 * @param time - Array of timestamps
 * @param values - Array of indicator values (may contain nulls)
 * @returns Data formatted for Lightweight Charts line series
 */
export function toLineSeriesData(
    time: number[],
    values: (number | null)[]
): { time: number; value: number }[] {
    const result: { time: number; value: number }[] = []

    for (let i = 0; i < time.length; i++) {
        if (values[i] !== null && values[i] !== undefined) {
            result.push({
                time: time[i],
                value: values[i] as number
            })
        }
    }

    return result
}
