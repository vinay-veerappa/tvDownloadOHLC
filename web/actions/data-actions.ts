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
