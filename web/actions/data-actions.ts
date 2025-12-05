"use server"

import path from "path"
import fs from "fs"
import { exec } from "child_process"
import { promisify } from "util"

const execAsync = promisify(exec)

interface OHLCData {
    time: number
    open: number
    high: number
    low: number
    close: number
}

export async function getChartData(ticker: string, timeframe: string): Promise<{ success: boolean, data?: OHLCData[], error?: string }> {
    try {
        const dataDir = path.join(process.cwd(), "..", "data")
        const fileName = `${ticker}_${timeframe}.parquet`
        const filePath = path.join(dataDir, fileName)
        const scriptPath = path.join(process.cwd(), "..", "scripts", "read_parquet.py")

        if (!fs.existsSync(filePath)) {
            return { success: false, error: "File not found" }
        }

        // Execute Python script
        // Execute Python script
        // Increase maxBuffer to 50MB to handle large JSON output
        const { stdout, stderr } = await execAsync(`python "${scriptPath}" "${filePath}"`, { maxBuffer: 50 * 1024 * 1024 })

        if (stderr) {
            console.error(`[getChartData] Stderr: ${stderr}`)
        }

        const result = JSON.parse(stdout)

        if (result.error) {
            console.error(`[getChartData] Python Error: ${result.error}`)
            return { success: false, error: result.error }
        }

        return { success: true, data: result.data }

    } catch (error) {
        console.error(`[getChartData] Exception: ${error}`)
        return { success: false, error: "Failed to load data" }
    }
}

export async function getAvailableData(): Promise<{ success: boolean, tickers: string[], timeframes: string[], tickerMap: Record<string, string[]> }> {
    try {
        const dataDir = path.join(process.cwd(), "..", "data")
        if (!fs.existsSync(dataDir)) {
            return { success: false, tickers: [], timeframes: [], tickerMap: {} }
        }

        const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.parquet'))
        const tickerMap: Record<string, string[]> = {}

        files.forEach(file => {
            // Expected format: Ticker_Timeframe.parquet
            const name = path.basename(file, '.parquet')
            const parts = name.split('_')
            if (parts.length >= 2) {
                const timeframe = parts.pop()! // Last part is timeframe
                const ticker = parts.join('_') // Rest is ticker

                if (ticker && timeframe) {
                    if (!tickerMap[ticker]) {
                        tickerMap[ticker] = []
                    }
                    tickerMap[ticker].push(timeframe)
                }
            }
        })

        // Sort timeframes for each ticker
        Object.keys(tickerMap).forEach(ticker => {
            tickerMap[ticker].sort()
        })

        return {
            success: true,
            tickers: Object.keys(tickerMap).sort(),
            timeframes: Array.from(new Set(Object.values(tickerMap).flat())).sort(),
            tickerMap // Return the map
        }
    } catch (error) {
        console.error("Error listing data files:", error)
        return { success: false, tickers: [], timeframes: [], tickerMap: {} }
    }
}
