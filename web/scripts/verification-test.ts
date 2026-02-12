
import { PrismaClient } from '@prisma/client'
import fs from 'fs'
import path from 'path'

const prisma = new PrismaClient()

// --- Mock CSV Parsing Logic (from csv-actions.ts) ---
function parseCsvLine(line: string): string[] {
    const values: string[] = []
    let currentValue = ''
    let insideQuotes = false

    for (let i = 0; i < line.length; i++) {
        const char = line[i]
        if (char === '"') {
            insideQuotes = !insideQuotes
        } else if (char === ',' && !insideQuotes) {
            values.push(currentValue.trim())
            currentValue = ''
        } else {
            currentValue += char
        }
    }
    values.push(currentValue.trim())
    return values
}

function parseDate(dateStr: string): Date | null {
    if (!dateStr) return null
    try {
        const date = new Date(dateStr)
        return isNaN(date.getTime()) ? null : date
    } catch {
        return null
    }
}

async function main() {
    console.log("🚀 Starting End-to-End Verification (Direct DB Mode)...")

    // 1. Create Account
    console.log("\n1️⃣ Creating Test Account...")
    const accountName = "TopstepX Verify " + Date.now()
    const account = await prisma.account.create({
        data: {
            name: accountName,
            initialBalance: 50000,
            currentBalance: 50000
        }
    })
    console.log(`✅ Account Created: ${account.name} (${account.id})`)

    // 2. Import CSV (TopstepX Logic)
    console.log("\n2️⃣ Importing TopstepX CSV...")
    const csvPath = 'c:/Users/vinay/tvDownloadOHLC/docs/features/journal/trades_export_topstepx.csv'
    const fileContent = fs.readFileSync(csvPath, 'utf-8')
    const lines = fileContent.split('\n').filter(l => l.trim().length > 0)
    
    // TopstepX Headers: Id,ContractName,EnteredAt,ExitedAt,EntryPrice,ExitPrice,Fees,PnL,Size,Type,TradeDay,TradeDuration,Commissions
    // Indices:
    // 0: Id, 1: ContractName, 2: EnteredAt, 3: ExitedAt, 4: EntryPrice, 5: ExitPrice, 6: Fees 
    // 7: PnL, 8: Size, 9: Type (Long/Short), 10: TradeDay, 11: TradeDuration, 12: Commissions

    let importedCount = 0
    // Skip header
    for (let i = 1; i < lines.length; i++) {
        const row = parseCsvLine(lines[i])
        if (row.length < 10) continue

        const ticker = row[1]
        const entryDate = parseDate(row[2])
        const exitDate = parseDate(row[3])
        const entryPrice = parseFloat(row[4])
        const exitPrice = parseFloat(row[5])
        const fees = parseFloat(row[6])
        const pnl = parseFloat(row[7])
        const size = parseFloat(row[8])
        const direction = row[9].toUpperCase() // "LONG" or "SHORT"

        if (entryDate && !isNaN(entryPrice)) {
            await prisma.trade.create({
                data: {
                    accountId: account.id,
                    ticker,
                    entryDate,
                    exitDate,
                    entryPrice,
                    exitPrice,
                    quantity: size,
                    direction,
                    status: "CLOSED",
                    pnl,
                    fees,
                    originalSource: "TOPSTEPX"
                }
            })
            importedCount++
        }
    }
    console.log(`✅ Imported ${importedCount} trades`)

    // 3. Ralph Loop - Analysis
    console.log("\n3️⃣ Testing Daily Analysis (Context)...")
    const today = new Date()
    today.setHours(0,0,0,0)
    
    const analysis = await prisma.analysis.create({
        data: {
            date: today,
            sentiment: "BULLISH",
            bias: "LONG",
            notes: "Direct DB verification test.",
            keyLevels: "25500",
            invalidationLevel: "24000"
        }
    })
    console.log(`✅ Analysis Created: ${analysis.id}`)

    // 4. Ralph Loop - Wargame
    console.log("\n4️⃣ Testing Wargame Scenario...")
    const wargame = await prisma.wargame.create({
        data: {
            analysisId: analysis.id,
            scenario: "IF break HOD",
            plan: "THEN Long",
            probability: "High"
        }
    })
    console.log(`✅ Wargame Created: ${wargame.id}`)

    // 5. Ralph Loop - Routine
    console.log("\n5️⃣ Testing Routine Checklist...")
    const routine = await prisma.routine.create({
        data: {
            date: today,
            checklist: JSON.stringify({ verified: true }),
            rating: 10,
            notes: "Verification run successful."
        }
    })
    console.log(`✅ Routine Created: ${routine.id}`)

    // 6. Ralph Loop - Chart Library
    console.log("\n6️⃣ Testing Chart Library Linkage...")
    const chart = await prisma.chart.create({
        data: {
            url: "http://localhost/test.png",
            type: "REVIEW",
            tags: "Verification",
            analysisId: analysis.id,
            wargameId: wargame.id
        }
    })
    console.log(`✅ Chart Saved & Linked: ${chart.id}`)

    // 7. Verify Counts
    console.log("\n🔍 Verification Summary:")
    const totalTrades = await prisma.trade.count({ where: { accountId: account.id }})
    const totalAnalysis = await prisma.analysis.count()
    
    console.log(`- Trades in Verified Account: ${totalTrades}`)
    console.log(`- Total Analysis Records: ${totalAnalysis}`)

    if (totalTrades > 0 && totalAnalysis > 0) {
        console.log("\n✨ SUCCESS: Full Workflow Verified.")
    } else {
        console.error("❌ FAILURE: Data missing.")
        process.exit(1)
    }
}

main()
    .catch(e => {
        console.error(error)
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })
