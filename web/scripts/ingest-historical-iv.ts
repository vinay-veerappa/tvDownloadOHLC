
import fs from 'fs';
import path from 'path';
import readline from 'readline';
import { PrismaClient } from '@prisma/client';
import pkg from 'yahoo-finance2';
import { DEFAULT_WATCHLIST } from '../lib/watchlist-constants';

const prisma = new PrismaClient();

// Fix V3 Instantiation: 
// The default export appears to be the class or a compatible object that requires 'new'.
// "Call const yahooFinance = new YahooFinance() first" strongly implies we need an instance.
const YahooFinance = (pkg as any).default || pkg;
const yf = new YahooFinance();

// Map System Ticker (e.g. /ES) to CSV/Yahoo Ticker
function getLookupKeys(systemTicker: string): { csv: string, yahoo: string } {
    if (systemTicker.startsWith('/')) {
        const clean = systemTicker.replace('/', '');
        return { csv: clean, yahoo: `${clean}=F` };
    }
    return { csv: systemTicker, yahoo: systemTicker };
}

async function ingest() {
    console.log("Starting Ingestion from Dolt Dump (Prices Fix V3)...");
    const csvPath = path.resolve(__dirname, '../../data/options/options/doltdump/volatility_history.csv');

    if (!fs.existsSync(csvPath)) {
        console.error(`File not found: ${csvPath}`);
        process.exit(1);
    }

    const csvToSystem = new Map<string, string>();
    const systemToYahoo = new Map<string, string>();

    DEFAULT_WATCHLIST.forEach(t => {
        const { csv, yahoo } = getLookupKeys(t);
        csvToSystem.set(csv, t);
        systemToYahoo.set(t, yahoo);
    });

    const fileStream = fs.createReadStream(csvPath);
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    const tickerMap = new Map<string, any[]>();
    let rowCount = 0;

    let isHeader = true;
    for await (const line of rl) {
        if (isHeader) { isHeader = false; continue; }

        const parts = line.split(',');
        if (parts.length < 10) continue;

        const dateStr = parts[0].trim();
        const csvSymbol = parts[1].trim();
        const systemTicker = csvToSystem.get(csvSymbol);

        if (!systemTicker) continue;

        const hv = parseFloat(parts[2]) || 0;
        const iv = parseFloat(parts[9]) || 0;

        if (iv === 0) continue;

        if (!tickerMap.has(systemTicker)) tickerMap.set(systemTicker, []);
        tickerMap.get(systemTicker)?.push({ date: new Date(dateStr), iv, hv });
        rowCount++;
    }
    console.log(`\nParsed ${rowCount} matching rows across ${tickerMap.size} tickers.`);

    for (const [ticker, rows] of tickerMap) {
        let minDate = new Date(rows[0].date);
        let maxDate = new Date(rows[0].date);
        rows.forEach((r: any) => {
            if (r.date < minDate) minDate = r.date;
            if (r.date > maxDate) maxDate = r.date;
        });
        minDate.setDate(minDate.getDate() - 5);
        maxDate.setDate(maxDate.getDate() + 5);

        const priceMap = new Map<string, number>();
        const yfTicker = systemToYahoo.get(ticker) || ticker;

        try {
            const queryOptions = {
                period1: minDate,
                period2: maxDate,
                interval: '1d' as const
            };

            // Use the instance 'yf'
            const result = await yf.historical(yfTicker, queryOptions);
            result.forEach((candle: any) => {
                const d = candle.date.toISOString().split('T')[0];
                priceMap.set(d, candle.close);
            });
        } catch (e: any) {
            console.error(`  Price fetch failed for ${ticker} (${yfTicker}): ${e.message}`);
        }

        const operations = rows.map((row: any) => {
            const dStr = row.date.toISOString().split('T')[0];
            const price = priceMap.get(dStr) || null;

            return (prisma as any).historicalVolatility.upsert({
                where: {
                    ticker_date: {
                        ticker: ticker,
                        date: row.date
                    }
                },
                update: {
                    iv: row.iv,
                    hv: row.hv,
                    closePrice: price
                },
                create: {
                    ticker: ticker,
                    date: row.date,
                    iv: row.iv,
                    hv: row.hv,
                    closePrice: price
                }
            });
        });

        const CHUNK_SIZE = 500;
        let upserted = 0;
        for (let i = 0; i < operations.length; i += CHUNK_SIZE) {
            const chunk = operations.slice(i, i + CHUNK_SIZE);
            try {
                await prisma.$transaction(chunk);
                upserted += chunk.length;
            } catch (err) {
                for (const op of chunk) { try { await op; upserted++; } catch (e) { } }
            }
        }
        process.stdout.write(`  ${ticker}: ${upserted},`);
    }
    console.log("\nIngestion Complete.");
}

ingest()
    .catch(e => console.error(e))
    .finally(async () => {
        await prisma.$disconnect();
    });
