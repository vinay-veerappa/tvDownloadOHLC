"use server"

import path from "path"
import fs from "fs"
import { exec } from "child_process"
import { promisify } from "util"

const execAsync = promisify(exec)

interface OHLCData {
    time: string
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
        const { stdout, stderr } = await execAsync(`python "${scriptPath}" "${filePath}"`)

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

export async function getAvailableData(): Promise<{ success: boolean, tickers: string[], timeframes: string[] }> {
    try {
        const dataDir = path.join(process.cwd(), "..", "data")
        if (!fs.existsSync(dataDir)) {
            return { success: false, tickers: [], timeframes: [] }
        }

        const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.parquet'))
        const tickers = new Set<string>()
        const timeframes = new Set<string>()

        files.forEach(file => {
            // Expected format: Ticker_Timeframe.parquet
            const name = path.basename(file, '.parquet')
            const parts = name.split('_')
            if (parts.length >= 2) {
                // Handle cases like ES1_1D or NQ1_1m
                // If ticker has underscores, this might be tricky, but assuming standard format
                const timeframe = parts.pop() // Last part is timeframe
                const ticker = parts.join('_') // Rest is ticker

                if (ticker && timeframe) {
                    tickers.add(ticker)
                    timeframes.add(timeframe)
                }
            }
        })

        return {
            success: true,
            tickers: Array.from(tickers).sort(),
            timeframes: Array.from(timeframes).sort() // You might want custom sorting for timeframes later
        }
    } catch (error) {
        console.error("Error listing data files:", error)
        return { success: false, tickers: [], timeframes: [] }
    }
}
