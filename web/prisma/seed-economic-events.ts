/**
 * Economic Event Sync (Historical CSV + Live Week Feed)
 *
 * Goals:
 * 1) Keep all historical events in Prisma DB (idempotent import from CSV)
 * 2) Keep near-term events up to date (live ForexFactory feed sync)
 * 3) Report remaining coverage gaps for visibility
 *
 * Usage: npx tsx prisma/seed-economic-events.ts
 */

import { PrismaClient } from '@prisma/client'
import * as fs from 'fs'
import * as path from 'path'

const prisma = new PrismaClient()

const FF_FEED_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
const TE_CALENDAR_URL = 'https://api.tradingeconomics.com/calendar/country'
const COUNTRIES = new Set(['USD']) // Only USD — international events pollute the narrative engine
const DEFAULT_GAP_THRESHOLD_DAYS = 14
const DEFAULT_MAX_API_BACKFILL_DAYS = 180

interface CsvRow {
    date: string           // 2000-01-03
    indicator: string      // ISM Manufacturing PMI
    category: string       // Manufacturing
    importance: string     // High | Medium | Low
    frequency: string      // Monthly | Weekly | etc
    time: string           // 10:00 ET
    year: string
    quarter: string
    month: string
    month_name: string
    day_of_week: string
    notes: string
}

interface LiveEconomicEvent {
    title: string
    country: string
    date: string
    impact: string
    forecast: string
    previous: string
}

interface DbEconomicEventInput {
    datetime: Date
    name: string
    impact: 'HIGH' | 'MEDIUM' | 'LOW'
    country: string  // Always 'USD' — this seed only fetches US data
    actual: number | null
    forecast: number | null
    previous: number | null
}

interface TimeGap {
    start: Date
    end: Date
    days: number
}

interface SyncConfig {
    csvPaths: string[]
    gapThresholdDays: number
    maxApiBackfillDays: number
    teApiToken: string | null
    teCountry: string
}

function mapImportance(importance: string): "HIGH" | "MEDIUM" | "LOW" {
    switch (importance.toUpperCase()) {
        case 'HIGH': return 'HIGH'
        case 'MEDIUM': return 'MEDIUM'
        case 'LOW': return 'LOW'
        default: return 'LOW'
    }
}

function parseNumberOrNull(value: string | null | undefined): number | null {
    if (!value) return null
    const normalized = String(value).trim().replace(/[^0-9.-]/g, '')
    if (!normalized) return null
    const parsed = Number(normalized)
    return Number.isFinite(parsed) ? parsed : null
}

function parseCsvLine(line: string): string[] {
    const result: string[] = []
    let current = ''
    let inQuotes = false

    for (let i = 0; i < line.length; i++) {
        const char = line[i]
        if (char === '"') {
            inQuotes = !inQuotes
        } else if (char === ',' && !inQuotes) {
            result.push(current.trim())
            current = ''
        } else {
            current += char
        }
    }
    result.push(current.trim())

    return result
}

function parseNyOffsetMinutes(dateIso: string): number {
    // Probe at noon UTC for stable offset parsing on the target date.
    const probe = new Date(`${dateIso}T12:00:00Z`)
    const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        timeZoneName: 'shortOffset'
    })
    const tzPart = formatter.formatToParts(probe).find(p => p.type === 'timeZoneName')?.value ?? 'GMT-5'
    const match = tzPart.match(/^GMT([+-])(\d{1,2})(?::(\d{2}))?$/)
    if (!match) return -300
    const sign = match[1] === '+' ? 1 : -1
    const hours = Number(match[2])
    const minutes = Number(match[3] ?? '0')
    return sign * (hours * 60 + minutes)
}

function parseEtDateTimeToUtc(dateIso: string, timeEt: string): Date {
    const safeTime = timeEt.replace(' ET', '').trim() || '09:30'
    const [hRaw, mRaw] = safeTime.split(':')
    const hours = Number(hRaw)
    const minutes = Number(mRaw)
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
        throw new Error(`Invalid ET time value: ${timeEt}`)
    }

    const [year, month, day] = dateIso.split('-').map(Number)
    if (!year || !month || !day) {
        throw new Error(`Invalid date value: ${dateIso}`)
    }

    const nyOffsetMinutes = parseNyOffsetMinutes(dateIso)
    const utcMs = Date.UTC(year, month - 1, day, hours, minutes, 0, 0) - (nyOffsetMinutes * 60 * 1000)
    return new Date(utcMs)
}

function eventKey(name: string, dt: Date): string {
    return `${name}__${dt.getTime()}`
}

function parseCliArgs(argv: string[]): Record<string, string | boolean> {
    const out: Record<string, string | boolean> = {}
    for (let i = 0; i < argv.length; i++) {
        const arg = argv[i]
        if (!arg.startsWith('--')) continue
        const key = arg.slice(2)
        const next = argv[i + 1]
        if (!next || next.startsWith('--')) {
            out[key] = true
            continue
        }
        out[key] = next
        i += 1
    }
    return out
}

function collectCsvPaths(baseDir: string, cliArgs: Record<string, string | boolean>): string[] {
    const defaultCsv = path.join(baseDir, 'docs', 'JournalRequirements', 'us_complete_economic_calendar_2000_2025.csv')
    const discovered = new Set<string>([defaultCsv])

    const backfillDir = path.join(baseDir, 'docs', 'JournalRequirements', 'economic_backfill')
    if (fs.existsSync(backfillDir)) {
        const extra = fs.readdirSync(backfillDir)
            .filter(name => name.toLowerCase().endsWith('.csv'))
            .map(name => path.join(backfillDir, name))
        for (const file of extra) discovered.add(file)
    }

    const csvArgs = [
        typeof cliArgs['extra-csv'] === 'string' ? cliArgs['extra-csv'] : null,
        process.env.ECON_EXTRA_CSV_PATHS ?? null,
    ].filter((v): v is string => !!v)

    for (const csvArg of csvArgs) {
        for (const token of csvArg.split(/[;,]/).map(s => s.trim()).filter(Boolean)) {
            const abs = path.isAbsolute(token) ? token : path.join(baseDir, token)
            discovered.add(abs)
        }
    }

    return Array.from(discovered)
}

function buildSyncConfig(): SyncConfig {
    const cliArgs = parseCliArgs(process.argv.slice(2))
    const baseDir = path.join(__dirname, '..', '..')
    const csvPaths = collectCsvPaths(baseDir, cliArgs)

    const gapThresholdDays = Number(
        (typeof cliArgs['gap-threshold-days'] === 'string' ? cliArgs['gap-threshold-days'] : null)
        ?? process.env.ECON_GAP_THRESHOLD_DAYS
        ?? DEFAULT_GAP_THRESHOLD_DAYS
    )

    const maxApiBackfillDays = Number(
        (typeof cliArgs['max-api-backfill-days'] === 'string' ? cliArgs['max-api-backfill-days'] : null)
        ?? process.env.ECON_MAX_API_BACKFILL_DAYS
        ?? DEFAULT_MAX_API_BACKFILL_DAYS
    )

    return {
        csvPaths,
        gapThresholdDays: Number.isFinite(gapThresholdDays) ? gapThresholdDays : DEFAULT_GAP_THRESHOLD_DAYS,
        maxApiBackfillDays: Number.isFinite(maxApiBackfillDays) ? maxApiBackfillDays : DEFAULT_MAX_API_BACKFILL_DAYS,
        teApiToken: process.env.TE_API_TOKEN ?? process.env.TE_CALENDAR_TOKEN ?? 'guest:guest',
        teCountry: process.env.TE_COUNTRY ?? 'united states',
    }
}

async function loadExistingEventKeySet(): Promise<Set<string>> {
    const rows = await prisma.economicEvent.findMany({
        select: { name: true, datetime: true }
    })
    return new Set(rows.map(r => eventKey(r.name, r.datetime)))
}

async function insertMissingEvents(
    candidateEvents: DbEconomicEventInput[],
    existingKeys: Set<string>,
    label: string
): Promise<number> {
    const deduped: DbEconomicEventInput[] = []
    const seen = new Set<string>()

    for (const event of candidateEvents) {
        const key = eventKey(event.name, event.datetime)
        if (existingKeys.has(key) || seen.has(key)) continue
        seen.add(key)
        deduped.push(event)
    }

    if (deduped.length === 0) {
        console.log(`No missing ${label} events to insert.`)
        return 0
    }

    const batchSize = 500
    let inserted = 0
    for (let i = 0; i < deduped.length; i += batchSize) {
        const batch = deduped.slice(i, i + batchSize)
        await prisma.economicEvent.createMany({ data: batch })
        inserted += batch.length
        for (const e of batch) existingKeys.add(eventKey(e.name, e.datetime))
        console.log(`Inserted ${inserted}/${deduped.length} ${label} events...`)
    }

    return inserted
}

function buildHistoricalEvents(csvPath: string): DbEconomicEventInput[] {
    const content = fs.readFileSync(csvPath, 'utf-8')
    const lines = content.split('\n').filter(line => line.trim())
    const dataLines = lines.slice(1)

    const events: DbEconomicEventInput[] = []

    for (const line of dataLines) {
        const fields = parseCsvLine(line)
        if (fields.length < 6) continue

        const [date, indicator, , importance, , time] = fields
        if (!date || !indicator) continue

        try {
            events.push({
                datetime: parseEtDateTimeToUtc(date, time),
                name: indicator,
                impact: mapImportance(importance),
                country: 'USD',  // Historical CSV is all US data
                actual: null,
                forecast: null,
                previous: null
            })
        } catch {
            // Skip malformed rows while preserving the rest of the import.
            continue
        }
    }

    return events
}

function computeLargeGaps(datesAsc: Date[], thresholdDays: number): TimeGap[] {
    const gaps: TimeGap[] = []
    for (let i = 1; i < datesAsc.length; i++) {
        const prev = datesAsc[i - 1]
        const curr = datesAsc[i]
        const gapDays = (curr.getTime() - prev.getTime()) / (24 * 60 * 60 * 1000)
        if (gapDays >= thresholdDays) {
            gaps.push({ start: prev, end: curr, days: gapDays })
        }
    }
    return gaps
}

function mapTeImportance(rawImportance: unknown): 'HIGH' | 'MEDIUM' | 'LOW' {
    if (typeof rawImportance === 'number') {
        if (rawImportance >= 3) return 'HIGH'
        if (rawImportance === 2) return 'MEDIUM'
        return 'LOW'
    }
    if (typeof rawImportance === 'string') {
        return mapImportance(rawImportance)
    }
    return 'LOW'
}

async function fetchTradingEconomicsRange(
    start: Date,
    end: Date,
    country: string,
    apiToken: string
): Promise<DbEconomicEventInput[]> {
    const startIso = start.toISOString().split('T')[0]
    const endIso = end.toISOString().split('T')[0]
    const countryPath = encodeURIComponent(country)
    const url = `${TE_CALENDAR_URL}/${countryPath}/${startIso}/${endIso}?f=json&c=${encodeURIComponent(apiToken)}`

    try {
        const response = await fetch(url)
        if (!response.ok) {
            console.warn(`TradingEconomics request failed (${response.status}) for ${startIso} -> ${endIso}`)
            return []
        }

        const payload = await response.json() as Array<Record<string, unknown>>
        if (!Array.isArray(payload)) return []

        return payload
            .map(item => {
                const dt = new Date(String(item.Date ?? ''))
                if (Number.isNaN(dt.getTime())) return null
                return {
                    datetime: dt,
                    name: String(item.Event ?? item.Category ?? 'Unknown Event'),
                    impact: mapTeImportance(item.Importance),
                    country: 'USD',  // TradingEconomics fetch is country-specific (US)
                    actual: parseNumberOrNull(item.Actual == null ? null : String(item.Actual)),
                    forecast: parseNumberOrNull(item.Forecast == null ? null : String(item.Forecast)),
                    previous: parseNumberOrNull(item.Previous == null ? null : String(item.Previous)),
                } satisfies DbEconomicEventInput
            })
            .filter((v): v is DbEconomicEventInput => !!v)
            .filter(v => v.datetime.getTime() >= start.getTime() && v.datetime.getTime() <= end.getTime())
    } catch (error) {
        console.warn(`TradingEconomics fetch failed for ${startIso} -> ${endIso}:`, error)
        return []
    }
}

async function backfillGapsFromHistoricalApi(
    config: SyncConfig,
    existingKeys: Set<string>
): Promise<number> {
    const chronological = await prisma.economicEvent.findMany({
        select: { datetime: true },
        orderBy: { datetime: 'asc' }
    })
    if (chronological.length < 2 || !config.teApiToken) return 0

    const gaps = computeLargeGaps(
        chronological.map(r => r.datetime),
        config.gapThresholdDays
    )

    let inserted = 0
    for (const gap of gaps) {
        if (gap.days > config.maxApiBackfillDays) {
            console.warn(
                `Skipping API backfill for oversized gap ${gap.days.toFixed(1)} days ` +
                `(${gap.start.toISOString()} -> ${gap.end.toISOString()})`
            )
            continue
        }

        const fetched = await fetchTradingEconomicsRange(gap.start, gap.end, config.teCountry, config.teApiToken)
        if (fetched.length === 0) continue
        inserted += await insertMissingEvents(fetched, existingKeys, 'api-gap')
    }

    return inserted
}

async function fetchLiveEvents(): Promise<DbEconomicEventInput[]> {
    const retries = 3
    const delayMs = 1500

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch(FF_FEED_URL, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            })
            if (!response.ok) {
                if (response.status === 429 && attempt < retries) {
                    console.warn(`Live feed rate-limited (attempt ${attempt}/${retries}); retrying...`)
                    await new Promise(resolve => setTimeout(resolve, delayMs * attempt))
                    continue
                }
                console.warn(`Live feed request failed: ${response.status}`)
                return []
            }

            const payload = (await response.json()) as LiveEconomicEvent[]
            return payload
                .filter(e => COUNTRIES.has(e.country))
                .map(e => ({
                    datetime: new Date(e.date),
                    name: e.title,
                    impact: mapImportance(e.impact),
                    country: e.country,  // Store the currency code from ForexFactory
                    actual: null,
                    forecast: parseNumberOrNull(e.forecast),
                    previous: parseNumberOrNull(e.previous)
                }))
                .filter(e => !Number.isNaN(e.datetime.getTime()))
        } catch (error) {
            if (attempt < retries) {
                await new Promise(resolve => setTimeout(resolve, delayMs * attempt))
                continue
            }
            console.warn('Live feed fetch failed:', error)
            return []
        }
    }

    return []
}

async function printCoverageReport(gapThresholdDays: number) {
    const count = await prisma.economicEvent.count()
    const first = await prisma.economicEvent.findFirst({ orderBy: { datetime: 'asc' } })
    const last = await prisma.economicEvent.findFirst({ orderBy: { datetime: 'desc' } })

    console.log('\nCoverage Report')
    console.log(`Total events in DB: ${count}`)
    console.log(`Range: ${first?.datetime.toISOString()} -> ${last?.datetime.toISOString()}`)

    const nowUtc = new Date()
    const daysToLast = last ? Math.floor((last.datetime.getTime() - nowUtc.getTime()) / (24 * 60 * 60 * 1000)) : null
    if (daysToLast !== null) {
        if (daysToLast >= 0) {
            console.log(`Freshness: latest event is ${daysToLast} day(s) ahead (future schedule loaded).`)
        } else {
            const daysSinceLast = Math.abs(daysToLast)
            if (daysSinceLast > 10) {
                console.warn(`Gap warning: latest event is ${daysSinceLast} days old.`)
            } else {
                console.log(`Freshness: latest event is ${daysSinceLast} day(s) old.`)
            }
        }
    }

    const chronological = await prisma.economicEvent.findMany({
        select: { datetime: true, name: true },
        orderBy: { datetime: 'asc' }
    })

    let maxGapDays = 0
    let maxGapStart: Date | null = null
    let maxGapEnd: Date | null = null
    for (let i = 1; i < chronological.length; i++) {
        const prev = chronological[i - 1].datetime
        const curr = chronological[i].datetime
        const gapDays = (curr.getTime() - prev.getTime()) / (24 * 60 * 60 * 1000)
        if (gapDays > maxGapDays) {
            maxGapDays = gapDays
            maxGapStart = prev
            maxGapEnd = curr
        }
    }

    if (maxGapDays >= gapThresholdDays && maxGapStart && maxGapEnd) {
        console.warn(
            `Largest gap detected: ${maxGapDays.toFixed(1)} days ` +
            `(${maxGapStart.toISOString()} -> ${maxGapEnd.toISOString()}).`
        )
    }
}

async function main() {
    const config = buildSyncConfig()

    const existingCsvPaths = config.csvPaths.filter(p => fs.existsSync(p))
    if (existingCsvPaths.length === 0) {
        console.error('No economic calendar CSV sources found for historical sync.')
        process.exit(1)
    }

    let historicalEvents: DbEconomicEventInput[] = []
    for (const csvPath of existingCsvPaths) {
        console.log(`Reading CSV from: ${csvPath}`)
        const events = buildHistoricalEvents(csvPath)
        console.log(`Historical candidates from file: ${events.length}`)
        historicalEvents = historicalEvents.concat(events)
    }
    console.log(`Historical candidates total: ${historicalEvents.length}`)

    const existingKeys = await loadExistingEventKeySet()
    console.log(`Existing events in DB before sync: ${existingKeys.size}`)

    const insertedHistorical = await insertMissingEvents(historicalEvents, existingKeys, 'historical')

    const liveEvents = await fetchLiveEvents()
    console.log(`Live-week candidates from feed: ${liveEvents.length}`)
    const insertedLive = await insertMissingEvents(liveEvents, existingKeys, 'live')

    const insertedApiGap = await backfillGapsFromHistoricalApi(config, existingKeys)

    console.log('\n✅ Economic event sync complete!')
    console.log(`   Inserted historical: ${insertedHistorical}`)
    console.log(`   Inserted live: ${insertedLive}`)
    console.log(`   Inserted api-gap: ${insertedApiGap}`)

    await printCoverageReport(config.gapThresholdDays)
}

main()
    .then(async () => {
        await prisma.$disconnect()
    })
    .catch(async (e) => {
        console.error(e)
        await prisma.$disconnect()
        process.exit(1)
    })
