const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
    console.log("Checking MacroSnapshot tickers...");
    const tickers = await prisma.macroSnapshot.findMany({
        select: { ticker: true },
        distinct: ['ticker'],
    });
    console.log("Found tickers:", tickers);

    for (const t of tickers) {
        const count = await prisma.macroSnapshot.count({
            where: { ticker: t.ticker }
        });
        console.log(`Ticker: ${t.ticker}, Record Count: ${count}`);
    }
}

main()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
