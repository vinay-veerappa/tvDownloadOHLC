"use server"

import { exec } from "child_process"
import path from "path"
import util from "util"

const execAsync = util.promisify(exec)

export interface DataFileStatus {
    name: string
    updated: string
    size: string
    rows: string
    status: string
}

export async function getDataStatus() {
    try {
        const projectRoot = path.resolve(process.cwd(), "..")
        const scriptAbsPath = path.join(projectRoot, "scripts", "check_data_status.py")

        const command = `python "${scriptAbsPath}"`

        const { stdout, stderr } = await execAsync(command)

        try {
            const data = JSON.parse(stdout.trim()) as DataFileStatus[]
            return { success: true, data }
        } catch (parseError) {
            console.error("JSON parse error from script output:", stdout)
            return { success: false, error: "Failed to parse script output" }
        }

    } catch (error) {
        console.error("Failed to run check_data_status:", error)
        return { success: false, error: "Failed to execute status script" }
    }
}

export async function runDataUpdate() {
    try {
        const projectRoot = path.resolve(process.cwd(), "..")
        const scriptAbsPath = path.join(projectRoot, "scripts", "update_intraday.py")
        const command = `python "${scriptAbsPath}"`

        const { stdout, stderr } = await execAsync(command)

        return { success: true, output: stdout, error: stderr }
    } catch (error) {
        console.error("Failed to run update:", error)
        return { success: false, error: "Failed to execute update script" }
    }
}
