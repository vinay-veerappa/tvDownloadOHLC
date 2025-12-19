
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const tickers = await prisma.historicalVolatility.findMany({
        select: { ticker: true },
        distinct: ['ticker']
    });
    console.log('Available Tickers:', tickers.map(t => t.ticker));

    const spyData = await prisma.historicalVolatility.findMany({
        where: { ticker: 'SPY' },
        orderBy: { date: 'desc' },
        take: 5
    });
    console.log('SPY Recent:', spyData);

    const esData = await prisma.historicalVolatility.findMany({
        where: { ticker: { contains: 'ES' } },
        orderBy: { date: 'desc' },
        take: 5
    });
    console.log('ES-like Recent:', esData);
}

main()
    .catch(e => console.error(e))
    .finally(async () => {
        await prisma.$disconnect();
    });
