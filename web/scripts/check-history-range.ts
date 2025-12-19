
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    // 1. Overall Range
    const aggregate = await prisma.historicalVolatility.aggregate({
        _min: { date: true },
        _max: { date: true },
        _count: true
    });

    console.log(`Total Records: ${aggregate._count}`);
    console.log(`Earliest Date: ${aggregate._min.date?.toISOString().split('T')[0]}`);
    console.log(`Latest Date:   ${aggregate._max.date?.toISOString().split('T')[0]}`);

    // 2. Count per Ticker
    const tickers = await prisma.historicalVolatility.groupBy({
        by: ['ticker'],
        _count: true,
        _min: { date: true },
        _max: { date: true }
    });

    console.log("\nPer Ticker Summary:");
    tickers.forEach(t => {
        console.log(`${t.ticker.padEnd(8)}: ${t._count} records (${t._min.date?.toISOString().split('T')[0]} to ${t._max.date?.toISOString().split('T')[0]})`);
    });
}

main()
    .catch(e => console.error(e))
    .finally(async () => await prisma.$disconnect());
