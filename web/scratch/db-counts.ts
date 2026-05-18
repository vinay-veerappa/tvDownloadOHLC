import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient({
  datasources: {
    db: {
      url: 'file:c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db'
    }
  }
});

async function getTickerSummary(table: string) {
  try {
    const data = await (prisma as any)[table].groupBy({
      by: ['ticker'],
      _count: true,
      _min: { date: true },
      _max: { date: true }
    });
    return data;
  } catch (e) {
    // If table doesn't have standard date or ticker field, try custom
    try {
      const data = await (prisma as any)[table].groupBy({
        by: ['ticker'],
        _count: true
      });
      return data;
    } catch (err) {
      return null;
    }
  }
}

async function main() {
  console.log("=========================================");
  console.log("🔍 ADVANCED DATABASE TICKER COVERAGE AUDIT");
  console.log("=========================================\n");

  const tables = [
    'historicalVolatility',
    'expectedMove',
    'expectedMoveHistory',
    'rthExpectedMove',
    'gexSnapshot',
    'macroSnapshot'
  ];

  for (const table of tables) {
    console.log(`📋 Table: ${table}`);
    try {
      const count = await (prisma as any)[table].count();
      console.log(`   Total rows: ${count}`);
      if (count === 0) {
        console.log(`   ❌ No data found.\n`);
        continue;
      }

      // Group by ticker to see which ones are covered
      const summary = await getTickerSummary(table);
      if (summary && summary.length > 0) {
        console.log(`   Tickers covered:`);
        summary.forEach((t: any) => {
          const minDateStr = t._min && t._min.date ? t._min.date.toISOString().split('T')[0] : 'N/A';
          const maxDateStr = t._max && t._max.date ? t._max.date.toISOString().split('T')[0] : 'N/A';
          console.log(`     - ${t.ticker.padEnd(8)}: ${t._count} rows [${minDateStr} to ${maxDateStr}]`);
        });
      } else {
        console.log(`   Could not aggregate by ticker.`);
      }
    } catch (e: any) {
      console.log(`   ❌ Error querying table: ${e.message}`);
    }
    console.log("");
  }
}

main()
  .catch(e => console.error(e))
  .finally(async () => await prisma.$disconnect());
