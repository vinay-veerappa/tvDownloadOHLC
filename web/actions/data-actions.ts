"use server"

import path from "path"
import fs from "fs"

interface OHLCData {
    time: number
    open: number
    high: number
    low: number
    close: number
}

interface ChunkMeta {
    ticker: string
    timeframe: string
    totalBars: number
    chunkSize: number
    numChunks: number
    startTime: number
    endTime: number
}

// Get the JSON data directory path
function getDataDir() {
    return path.join(process.cwd(), "public", "data")
}

// Load chunk metadata for a ticker/timeframe
function loadMeta(ticker: string, timeframe: string): ChunkMeta | null {
    const metaPath = path.join(getDataDir(), `${ticker}_${timeframe}`, "meta.json")
    if (!fs.existsSync(metaPath)) {
        return null
    }
    return JSON.parse(fs.readFileSync(metaPath, 'utf8'))
}

// Load a specific chunk
function loadChunk(ticker: string, timeframe: string, chunkIndex: number): OHLCData[] {
    const chunkPath = path.join(getDataDir(), `${ticker}_${timeframe}`, `chunk_${chunkIndex}.json`)
    if (!fs.existsSync(chunkPath)) {
        return []
    }
    return JSON.parse(fs.readFileSync(chunkPath, 'utf8'))
}

export async function getChartData(ticker: string, timeframe: string): Promise<{ success: boolean, data?: OHLCData[], totalRows?: number, chunksLoaded?: number, numChunks?: number, error?: string }> {
    try {
        const meta = loadMeta(ticker, timeframe)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        // Determine how many chunks to load initially based on timeframe
        // Each chunk is 20,000 bars
        // Load ~8 months initially (~240ms), background load rest
        let initialChunks: number
        switch (timeframe) {
            case '1m':
                initialChunks = 12  // ~240,000 bars (~8 months)
                break
            case '5m':
                initialChunks = 12  // ~240,000 bars (~2+ years)
                break
            case '15m':
                initialChunks = 12  // ~240,000 bars (~7+ years)
                break
            default:
                // For 1h and above, load all data
                initialChunks = meta.numChunks
        }

        // Load initial chunks (most recent first)
        // Chunk 0 = most recent, Chunk N = oldest
        // Within each chunk, data is sorted oldest to newest
        const chunksToLoad = Math.min(initialChunks, meta.numChunks)
        const allChunks: OHLCData[][] = []
        for (let i = 0; i < chunksToLoad; i++) {
            const chunkData = loadChunk(ticker, timeframe, i)
            allChunks.push(chunkData)
        }

        // Combine chunks: oldest chunk first, then newer chunks
        // Reverse the array so we go from oldest (last loaded) to newest (first loaded)
        let data: OHLCData[] = []
        for (let i = allChunks.length - 1; i >= 0; i--) {
            data = [...data, ...allChunks[i]]
        }

        return {
            success: true,
            data,
            totalRows: meta.totalBars,
            chunksLoaded: chunksToLoad,
            numChunks: meta.numChunks
        }

    } catch (error) {
        console.error(`[getChartData] Exception: ${error}`)
        return { success: false, error: "Failed to load data" }
    }
}

// Load specific number of chunks for on-demand loading
// Returns older data starting from startChunk, loading up to numToLoad chunks
export async function loadNextChunks(
    ticker: string,
    timeframe: string,
    startChunk: number,
    numToLoad: number = 5 // Default to 5 chunks (~100K bars, ~3 months of 1m data)
): Promise<{ success: boolean, data?: OHLCData[], chunksLoaded?: number, nextChunkIndex?: number, hasMore?: boolean, error?: string }> {
    try {
        const meta = loadMeta(ticker, timeframe)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        if (startChunk >= meta.numChunks) {
            // No more data to load
            return { success: true, data: [], chunksLoaded: 0, nextChunkIndex: startChunk, hasMore: false }
        }

        // Load up to numToLoad chunks (older data)
        const endChunk = Math.min(startChunk + numToLoad, meta.numChunks)
        const allChunks: OHLCData[][] = []

        for (let i = startChunk; i < endChunk; i++) {
            const chunkData = loadChunk(ticker, timeframe, i)
            allChunks.push(chunkData)
        }

        // Combine: reverse so oldest chunk is first
        let data: OHLCData[] = []
        for (let i = allChunks.length - 1; i >= 0; i--) {
            data = [...data, ...allChunks[i]]
        }

        const chunksLoaded = allChunks.length
        const hasMore = endChunk < meta.numChunks

        return {
            success: true,
            data,
            chunksLoaded,
            nextChunkIndex: endChunk,
            hasMore
        }

    } catch (error) {
        console.error(`[loadNextChunks] Exception: ${error}`)
        return { success: false, error: "Failed to load data chunks" }
    }
}

// Legacy function - loads ALL remaining chunks (can cause OOM with large datasets)
export async function loadRemainingChunks(
    ticker: string,
    timeframe: string,
    startChunk: number
): Promise<{ success: boolean, data?: OHLCData[], chunksLoaded?: number, error?: string }> {
    try {
        const meta = loadMeta(ticker, timeframe)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        if (startChunk >= meta.numChunks) {
            // No more data to load
            return { success: true, data: [], chunksLoaded: 0 }
        }

        // Load all remaining chunks (older data)
        // Collect chunks first, then combine oldest to newest
        const allChunks: OHLCData[][] = []
        for (let i = startChunk; i < meta.numChunks; i++) {
            const chunkData = loadChunk(ticker, timeframe, i)
            allChunks.push(chunkData)
        }

        // Combine: reverse so oldest chunk is first
        let data: OHLCData[] = []
        for (let i = allChunks.length - 1; i >= 0; i--) {
            data = [...data, ...allChunks[i]]
        }
        const chunksLoaded = allChunks.length

        return {
            success: true,
            data,
            chunksLoaded
        }

    } catch (error) {
        console.error(`[loadRemainingChunks] Exception: ${error}`)
        return { success: false, error: "Failed to load remaining data" }
    }
}

export async function getAvailableData(): Promise<{ success: boolean, tickers: string[], timeframes: string[], tickerMap: Record<string, string[]> }> {
    try {
        const dataDir = getDataDir()
        if (!fs.existsSync(dataDir)) {
            return { success: false, tickers: [], timeframes: [], tickerMap: {} }
        }

        // Get all directories (each is a ticker_timeframe combo)
        const entries = fs.readdirSync(dataDir, { withFileTypes: true })
        const tickerMap: Record<string, string[]> = {}

        entries.forEach(entry => {
            if (entry.isDirectory()) {
                // Expected format: Ticker_Timeframe
                const parts = entry.name.split('_')
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
            tickerMap
        }
    } catch (error) {
        console.error("Error listing data files:", error)
        return { success: false, tickers: [], timeframes: [], tickerMap: {} }
    }
}
