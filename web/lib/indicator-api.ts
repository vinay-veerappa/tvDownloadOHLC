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

export interface LineStyle {
    color: string
    width: number
    style: number // 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed
}

export interface VWAPSettings {
    anchor?: "session" | "week" | "month"
    anchor_time?: string // "09:30"
    anchor_timezone?: string // "America/New_York"
    bands?: number[] // [1.0, 2.0]
    bandsEnabled?: boolean[] // [true, false]
    source?: "hlc3" | "close" | "ohlc4"
    vwapStyle?: LineStyle
    bandStyles?: LineStyle[]
}

/**
 * Calculate indicators from chart OHLCV data via Python API
 * 
 * @param ohlcv - The OHLCV data array from the chart
 * @param indicators - List of indicators to calculate (e.g., ["vwap", "sma_20", "ema_9"])
 * @param timeframe - Current timeframe (e.g. "5m") to allow auto-hiding on daily+
 * @param vwapSettings - Optional settings for VWAP
 * @returns Calculated indicator values aligned with time series
 */
export async function calculateIndicators(
    ohlcv: OHLCData[],
    indicators: string[],
    timeframe?: string,
    vwapSettings?: VWAPSettings
): Promise<IndicatorResult | null> {
    if (!ohlcv.length || !indicators.length) {
        return null
    }

    try {
        // Use v2 endpoint which supports settings
        const response = await fetch(`${API_BASE_URL}/api/indicators/calculate-v2`, {
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
                indicators,
                timeframe,
                vwap_settings: vwapSettings
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
 * Calculate VWAP from backend data files (uses actual volume data).
 * 
 * This is preferred over calculateIndicators for VWAP because:
 * 1. Backend has full volume data from parquet files
 * 2. Frontend may not load/display volume
 * 3. Avoids sending large OHLCV arrays over the network
 * 
 * @param ticker - The ticker symbol (e.g., "ES1", "CL1!")
 * @param timeframe - The timeframe (e.g., "1m", "5m")
 * @param vwapSettings - Optional VWAP settings
 * @param startTime - Optional start timestamp filter
 * @param endTime - Optional end timestamp filter
 * @returns Calculated VWAP values aligned with time series
 */
export async function calculateVWAPFromFile(
    ticker: string,
    timeframe: string,
    vwapSettings?: VWAPSettings,
    startTime?: number,
    endTime?: number
): Promise<IndicatorResult | null> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/indicators/vwap-from-file`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                ticker,
                timeframe,
                vwap_settings: vwapSettings,
                start_time: startTime,
                end_time: endTime
            }),
        })

        if (!response.ok) {
            console.error(`VWAP API error: ${response.status}`)
            return null
        }

        return await response.json()
    } catch (error) {
        console.error("Failed to calculate VWAP from file:", error)
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
                time: time[i] as any, // Cast to any to satisfy LW Charts Time type requirement
                value: values[i] as number
            })
        }
    }

    return result
}
