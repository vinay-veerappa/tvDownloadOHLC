
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
    const openTrades = await prisma.trade.findMany({
        where: { status: 'OPEN' },
        orderBy: { entryDate: 'asc' }
    })

    console.log(`Found ${openTrades.length} OPEN trades:`)
    openTrades.forEach(t => {
        console.log(`- ID: ${t.id} | ${t.ticker} | ${t.direction} | Qty: ${t.quantity} | Entry: ${t.entryPrice} | Date: ${t.entryDate.toISOString()}`)
    })
}

main()
    .catch(e => {
        console.error(e)
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })
