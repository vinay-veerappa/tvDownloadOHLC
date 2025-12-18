"use server"

import path from "path"
import fs from "fs"
import { resolutionToFolderName } from "../lib/resolution"

export interface OHLCData {
    time: number
    open: number
    high: number
    low: number
    close: number
    volume?: number
}

interface ChunkRange {
    index: number
    startTime: number
    endTime: number
    bars: number
}

interface ChunkMeta {
    ticker: string
    timeframe: string
    totalBars: number
    chunkSize: number
    numChunks: number
    startTime: number
    endTime: number
    chunks?: ChunkRange[]  // Per-chunk time ranges for precise lookup
}

// Get the JSON data directory path
function getDataDir() {
    return path.join(process.cwd(), "public", "data")
}

// Helper to normalize ticker to folder name prefix
// e.g. "NQ1!" -> "NQ1", "/NQ" -> "NQ1", "ES" -> "ES1"
function normalizeTickerForFolder(ticker: string): string {
    let clean = ticker.replace(/!/g, '').replace(/\//g, '');

    // Map known roots to continuous contract 1
    const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];

    // Exact match check (e.g. "NQ" -> "NQ1")
    if (roots.includes(clean)) {
        return clean + "1";
    }

    // If it already ends in 1 (e.g. NQ1), keep it
    return clean;
}

// Load chunk metadata for a ticker/timeframe
function loadMeta(ticker: string, timeframe: string): ChunkMeta | null {
    const cleanTicker = normalizeTickerForFolder(ticker)
    const metaPath = path.join(getDataDir(), `${cleanTicker}_${timeframe}`, "meta.json")
    if (!fs.existsSync(metaPath)) {
        return null
    }
    return JSON.parse(fs.readFileSync(metaPath, 'utf8'))
}

// Global Cache for loaded chunks to speed up backtests
// Key: "Ticker_Timeframe_ChunkIndex" -> Value: OHLCData[]
const CHUNK_CACHE = new Map<string, OHLCData[]>()

// Load a specific chunk with Caching
function loadChunk(ticker: string, timeframe: string, chunkIndex: number): OHLCData[] {
    const cleanTicker = normalizeTickerForFolder(ticker)
    const cacheKey = `${cleanTicker}_${timeframe}_${chunkIndex}`

    // 1. Check Cache
    if (CHUNK_CACHE.has(cacheKey)) {
        return CHUNK_CACHE.get(cacheKey)!
    }

    const chunkPath = path.join(getDataDir(), `${cleanTicker}_${timeframe}`, `chunk_${chunkIndex}.json`)
    if (!fs.existsSync(chunkPath)) {
        return []
    }

    // 2. Load and Parse
    try {
        const data = JSON.parse(fs.readFileSync(chunkPath, 'utf8'))

        // 3. Store in Cache
        CHUNK_CACHE.set(cacheKey, data)

        return data
    } catch (e) {
        console.error(`Failed to load chunk ${chunkPath}:`, e)
        return []
    }
}

export async function clearCache() {
    CHUNK_CACHE.clear()
    console.log("Memory Cache Cleared")
    return { success: true }
}

export async function getChartData(ticker: string, timeframe: string, limit: number = 0): Promise<{ success: boolean, data?: OHLCData[], totalRows?: number, chunksLoaded?: number, numChunks?: number, error?: string }> {
    try {
        // Try direct folder (for legacy support like 'folder_3m') OR converted folder name
        let folderName = timeframe
        const directMeta = loadMeta(ticker, folderName)

        if (!directMeta) {
            folderName = resolutionToFolderName(timeframe)
        }

        const meta = loadMeta(ticker, folderName)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        // Determine how many chunks to load
        // If limit is 0 (default), load 1 chunk (chart view)
        // If limit is -1, load ALL chunks (backtest)
        // If limit > 0, load that many chunks
        let chunksToLoad = 1

        if (limit === 0) {
            chunksToLoad = 1
        } else if (limit === -1) {
            chunksToLoad = meta.numChunks
        } else {
            chunksToLoad = Math.min(limit, meta.numChunks)
        }

        const allChunks: OHLCData[][] = []
        for (let i = 0; i < chunksToLoad; i++) {
            const chunkData = loadChunk(ticker, folderName, i)
            allChunks.push(chunkData)
        }

        // Combine chunks: oldest chunk first, then newer chunks
        // Chunk 0 is newest, Chunk N is oldest.
        // We want data sorted by time (oldest to newest).
        // So we want Chunk N, Chunk N-1, ... Chunk 0.

        // Efficient flattening
        const validChunks = allChunks.filter(c => c && c.length > 0)
        let totalLen = 0
        for (const c of validChunks) totalLen += c.length

        const data = new Array(totalLen)
        let offset = 0

        // Iterate backwards (from oldest chunk to newest chunk)
        for (let i = validChunks.length - 1; i >= 0; i--) {
            const chunk = validChunks[i]
            for (let j = 0; j < chunk.length; j++) {
                data[offset++] = chunk[j]
            }
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

// Get metadata about the full data range (for calendar)
export interface DataMetadata {
    firstBarTime: number  // Oldest bar timestamp
    lastBarTime: number   // Newest bar timestamp
    totalBars: number
    numChunks: number
    chunkSize: number
}

export async function getDataMetadata(
    ticker: string,
    timeframe: string
): Promise<{ success: boolean, metadata?: DataMetadata, error?: string }> {
    try {
        let folderName = timeframe
        const directMeta = loadMeta(ticker, folderName)

        if (!directMeta) {
            folderName = resolutionToFolderName(timeframe)
        }

        const meta = loadMeta(ticker, folderName)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        return {
            success: true,
            metadata: {
                firstBarTime: meta.startTime,
                lastBarTime: meta.endTime,
                totalBars: meta.totalBars,
                numChunks: meta.numChunks,
                chunkSize: meta.chunkSize
            }
        }
    } catch (error) {
        console.error(`[getDataMetadata] Exception: ${error}`)
        return { success: false, error: "Failed to load metadata" }
    }
}

// Load chunks around a specific timestamp (for "go to date" feature)
// Returns data centered around the target time
export async function loadChunksForTime(
    ticker: string,
    timeframe: string,
    targetTime: number,
    chunksToLoad: number = 10 // Load 10 chunks (~200K bars) centered on target
): Promise<{ success: boolean, data?: OHLCData[], startChunkIndex?: number, endChunkIndex?: number, error?: string }> {
    try {
        let folderName = timeframe
        const directMeta = loadMeta(ticker, folderName)

        if (!directMeta) {
            folderName = resolutionToFolderName(timeframe)
        }

        const meta = loadMeta(ticker, folderName)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        // Validate target time is within data range
        if (targetTime < meta.startTime || targetTime > meta.endTime) {
            return { success: false, error: "Target time is outside available data range" }
        }

        // Find chunk containing target time using precise metadata
        let targetChunk = -1

        if (meta.chunks && meta.chunks.length > 0) {
            // Use precise chunk lookup from metadata
            for (const chunk of meta.chunks) {
                if (targetTime >= chunk.startTime && targetTime <= chunk.endTime) {
                    targetChunk = chunk.index
                    break
                }
            }
            // If not found (edge case), find closest
            if (targetChunk === -1) {
                for (const chunk of meta.chunks) {
                    if (targetTime <= chunk.endTime) {
                        targetChunk = chunk.index
                        break
                    }
                }
                if (targetChunk === -1) {
                    targetChunk = meta.numChunks - 1
                }
            }
        } else {
            // Fallback: estimate using linear interpolation (old behavior)
            const timeRange = meta.endTime - meta.startTime
            const timeOffset = meta.endTime - targetTime
            const estimatedProgress = timeOffset / timeRange
            targetChunk = Math.floor(estimatedProgress * (meta.numChunks - 1))
        }

        // Load chunks centered around target chunk
        const halfChunks = Math.floor(chunksToLoad / 2)
        const startChunk = Math.max(0, targetChunk - halfChunks)
        const endChunk = Math.min(meta.numChunks, startChunk + chunksToLoad)

        console.log(`[loadChunksForTime] Target: ${new Date(targetTime * 1000).toISOString()}, Chunk: ${targetChunk}, Loading: ${startChunk}-${endChunk}`)

        // Load chunks
        const allChunks: OHLCData[][] = []
        for (let i = startChunk; i < endChunk; i++) {
            const chunkData = loadChunk(ticker, folderName, i)
            allChunks.push(chunkData)
        }

        // Combine: reverse so oldest chunk is first (for correct time ordering)
        let data: OHLCData[] = []
        for (let i = allChunks.length - 1; i >= 0; i--) {
            data = [...data, ...allChunks[i]]
        }

        return {
            success: true,
            data,
            startChunkIndex: startChunk,
            endChunkIndex: endChunk
        }

    } catch (error) {
        console.error(`[loadChunksForTime] Exception: ${error}`)
        return { success: false, error: "Failed to load chunks" }
    }
}

// Load next batch of chunks (for infinite scrolling)
// Loads 'count' chunks starting from 'startIndex' (going backwards in time)
// Returns new data and updated index
export async function loadNextChunks(
    ticker: string,
    timeframe: string,
    startIndex: number,
    count: number = 5
): Promise<{ success: boolean, data?: OHLCData[], nextChunkIndex?: number, hasMore?: boolean, chunksLoaded?: number, error?: string }> {
    try {
        let folderName = timeframe
        const directMeta = loadMeta(ticker, folderName)

        if (!directMeta) {
            folderName = resolutionToFolderName(timeframe)
        }

        const meta = loadMeta(ticker, folderName)
        if (!meta) {
            return { success: false, error: "Data not found" }
        }

        const startChunk = startIndex
        const endChunk = Math.min(meta.numChunks, startChunk + count)
        const chunksToLoad = endChunk - startChunk

        if (chunksToLoad <= 0) {
            return { success: false, hasMore: false, error: "No more data" }
        }

        console.log(`[loadNextChunks] Loading chunks ${startChunk} to ${endChunk} for ${ticker} ${timeframe}`)

        const allChunks: OHLCData[][] = []
        for (let i = startChunk; i < endChunk; i++) {
            const chunkData = loadChunk(ticker, folderName, i)
            allChunks.push(chunkData)
        }

        // Combine chunks
        // Chunks are loaded from newest to oldest (index 0 is newest)
        // Inside each chunk, data is oldest to newest
        // We want the resulting array to be continuous time, oldest to newest
        // So we append chunks: Chunk X+4, Chunk X+3, ... Chunk X
        // WAIT: Chunks are contiguous in index order. Chunk 0 is newest. Chunk 1 is older.
        // If we load Chunk 1 and Chunk 2.
        // Chunk 2 contains older data than Chunk 1.
        // We want [Older Data, Newer Data].
        // So we want [Chunk 2 data, Chunk 1 data].

        let data: OHLCData[] = []
        for (let i = allChunks.length - 1; i >= 0; i--) {
            data = [...data, ...allChunks[i]]
        }

        return {
            success: true,
            data,
            nextChunkIndex: endChunk,
            hasMore: endChunk < meta.numChunks,
            chunksLoaded: chunksToLoad
        }

    } catch (error) {
        console.error(`[loadNextChunks] Exception: ${error}`)
        return { success: false, error: "Failed to load next chunks" }
    }
}

// Legacy function - kept for compatibility but should be replaced
export async function loadRemainingChunks(ticker: string, timeframe: string, startChunkIndex: number): Promise<{ success: boolean, data?: OHLCData[], chunkIndex?: number, error?: string }> {
    return loadNextChunks(ticker, timeframe, startChunkIndex, 1000) // Load plenty
}

// Discover available data files
export async function getAvailableData() {
    try {
        const dataDir = getDataDir()
        if (!fs.existsSync(dataDir)) {
            return { success: false, tickers: [], timeframes: [], tickerMap: {} }
        }

        const entries = fs.readdirSync(dataDir, { withFileTypes: true })
        const dirs = entries.filter(e => e.isDirectory()).map(e => e.name)

        const tickerMap: Record<string, string[]> = {}
        const allTickers = new Set<string>()
        const allTimeframes = new Set<string>()

        for (const dir of dirs) {
            const parts = dir.split('_')
            if (parts.length >= 2) {
                const baseTicker = parts[0]
                const timeframe = parts.slice(1).join('_') // Handle timeframes with underscores if any

                // Standardize: "ES1" -> "ES1!"
                // Strategy: If it ends in a digit, assume it's a future and add !
                let ticker = baseTicker
                if (baseTicker && /\d$/.test(baseTicker)) {
                    ticker = `${baseTicker}!`
                }

                allTickers.add(ticker)
                allTimeframes.add(timeframe)

                if (!tickerMap[ticker]) {
                    tickerMap[ticker] = []
                }
                tickerMap[ticker].push(timeframe)
            }
        }

        // Sort timeframes logically
        const tfOrder = ['15s', '30s', '1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '8H', '12H', '1D', '3D', '1W', '1M']
        const sortedTimeframes = Array.from(allTimeframes).sort((a, b) => {
            const indexA = tfOrder.indexOf(a)
            const indexB = tfOrder.indexOf(b)
            if (indexA !== -1 && indexB !== -1) return indexA - indexB
            if (indexA !== -1) return -1
            if (indexB !== -1) return 1
            return a.localeCompare(b)
        })

        // Always add 15s and 30s for Live Mode availability
        if (!sortedTimeframes.includes('15s')) sortedTimeframes.unshift('15s');
        if (!sortedTimeframes.includes('30s')) {
            const idx = sortedTimeframes.indexOf('15s');
            sortedTimeframes.splice(idx + 1, 0, '30s');
        }

        // Add to ticker maps as well
        Object.keys(tickerMap).forEach(k => {
            if (!tickerMap[k].includes('15s')) tickerMap[k].unshift('15s');
            if (!tickerMap[k].includes('30s')) {
                const idx = tickerMap[k].indexOf('15s');
                tickerMap[k].splice(idx + 1, 0, '30s');
            }
        });

        return {
            success: true,
            tickers: Array.from(allTickers).sort(),
            timeframes: sortedTimeframes,
            tickerMap
        }
    } catch (error) {
        console.error("Error listing data files:", error)
        return { success: false, tickers: [], timeframes: [], tickerMap: {} }
    }
}
