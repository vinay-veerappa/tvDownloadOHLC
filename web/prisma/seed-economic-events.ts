/**
 * Import Economic Calendar from CSV
 * 
 * CSV Columns: date, indicator, category, importance, frequency, time, year, quarter, month, month_name, day_of_week, notes
 * 
 * Usage: npx tsx prisma/seed-economic-events.ts
 */

import { PrismaClient } from '@prisma/client'
import * as fs from 'fs'
import * as path from 'path'

const prisma = new PrismaClient()

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

function mapImportance(importance: string): "HIGH" | "MEDIUM" | "LOW" {
    switch (importance.toUpperCase()) {
        case 'HIGH': return 'HIGH'
        case 'MEDIUM': return 'MEDIUM'
        case 'LOW': return 'LOW'
        default: return 'LOW'
    }
}

function parseDateTime(date: string, time: string): Date {
    // date: 2000-01-03
    // time: 10:00 ET or 08:30 ET
    const timePart = time.replace(' ET', '').trim() || '09:30'
    const [hours, minutes] = timePart.split(':').map(Number)

    const dt = new Date(date)
    dt.setHours(hours, minutes, 0, 0)

    return dt
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

async function main() {
    const csvPath = path.join(__dirname, '..', '..', 'docs', 'JournalRequirements', 'us_complete_economic_calendar_2000_2025.csv')

    if (!fs.existsSync(csvPath)) {
        console.error(`CSV file not found: ${csvPath}`)
        process.exit(1)
    }

    console.log(`Reading CSV from: ${csvPath}`)

    const content = fs.readFileSync(csvPath, 'utf-8')
    const lines = content.split('\n').filter(line => line.trim())

    // Skip header
    const header = lines[0].split(',')
    console.log('CSV Headers:', header)

    const dataLines = lines.slice(1)
    console.log(`Found ${dataLines.length} events to import`)

    // Clear existing events
    await prisma.economicEvent.deleteMany({})
    console.log('Cleared existing events')

    let imported = 0
    let skipped = 0
    let errors = 0

    const batchSize = 500
    const events: any[] = []

    for (const line of dataLines) {
        try {
            const fields = parseCsvLine(line)

            if (fields.length < 6) {
                skipped++
                continue
            }

            const [date, indicator, category, importance, frequency, time] = fields

            if (!date || !indicator) {
                skipped++
                continue
            }

            const datetime = parseDateTime(date, time)

            // Validate date
            if (isNaN(datetime.getTime())) {
                skipped++
                continue
            }

            events.push({
                datetime,
                name: indicator,
                impact: mapImportance(importance),
                actual: null,
                forecast: null,
                previous: null
            })

            // Batch insert
            if (events.length >= batchSize) {
                await prisma.economicEvent.createMany({
                    data: events
                })
                imported += events.length
                console.log(`Imported ${imported} events...`)
                events.length = 0
            }

        } catch (err) {
            errors++
            if (errors < 5) {
                console.error(`Error parsing line: ${line.substring(0, 100)}...`, err)
            }
        }
    }

    // Insert remaining
    if (events.length > 0) {
        await prisma.economicEvent.createMany({
            data: events
        })
        imported += events.length
    }

    console.log(`\n✅ Import complete!`)
    console.log(`   Imported: ${imported}`)
    console.log(`   Skipped: ${skipped}`)
    console.log(`   Errors: ${errors}`)

    // Show count and range
    const count = await prisma.economicEvent.count()
    const first = await prisma.economicEvent.findFirst({ orderBy: { datetime: 'asc' } })
    const last = await prisma.economicEvent.findFirst({ orderBy: { datetime: 'desc' } })

    console.log(`\n📊 Total events in database: ${count}`)
    console.log(`📅 Date Range: ${first?.datetime.toISOString().split('T')[0]} to ${last?.datetime.toISOString().split('T')[0]}`)
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
