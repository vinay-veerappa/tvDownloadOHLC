
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinCloseInRangeStrategy } from '../web/lib/backtest/strategies/nq-1min-close-in-range-strategy';

// Reuse data loading
function loadDataStandalone(ticker: string, timeframe: string) {
    const cleanTicker = ticker.replace('!', '');
    const dataDir = path.join(process.cwd(), 'public', 'data', `${cleanTicker}_${timeframe}`);
    const metaPath = path.join(dataDir, 'meta.json');
    if (!fs.existsSync(metaPath)) throw new Error("Meta not found");
    const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));

    const chunks = [];
    for (let i = 0; i < meta.numChunks; i++) {
        const chunkPath = path.join(dataDir, `chunk_${i}.json`);
        if (fs.existsSync(chunkPath)) {
            chunks.push(JSON.parse(fs.readFileSync(chunkPath, 'utf8')));
        }
    }
    let data: any[] = [];
    for (let i = chunks.length - 1; i >= 0; i--) {
        data = data.concat(chunks[i]);
    }
    return data;
}

async function main() {
    const ticker = "NQ1!";
    const timeframe = "1m";
    console.log("Loading Data...");
    const data = loadDataStandalone(ticker, timeframe);
    console.log(`Total Data: ${data.length} bars`);

    const years = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016];
    const results = [];
    const allTradesForCsv = [];

    const strat = new Nq1MinCloseInRangeStrategy();

    // Loop through years
    for (const year of years) {
        console.log(`\n--- Testing Year ${year} ---`);

        // Find start index for the year
        // We look for the first bar where date starts with 'Year-'
        // Or timestamp logic. Data is sorted.
        // Let's iterate linearly since 5M bars is fast enough to scan once.
        // Actually, let's scan.

        const startTs = new Date(`${year}-01-01T00:00:00.000Z`).getTime() / 1000;
        let startIndex = -1;

        // Binary search for efficiency? Or just linear scan from end if usually recent?
        // Data is ascending? Yes (chunks reversed/concatenated to be chronological).

        for (let i = 0; i < data.length; i++) {
            if (data[i].time >= startTs) {
                startIndex = i;
                break;
            }
        }

        if (startIndex === -1) {
            console.log(`No data found for start of ${year}`);
            continue;
        }

        // Slice data efficiently? The strategy might need context but usually doesn't need much.
        // Let's just pass sliced data or big data with index? 
        // Strategy interface takes `OHLCData[]`. We'll slice.
        // We only need enough data for 100 trades. Let's slice maybe 50,000 bars (approx 2 months).
        // 100 trades might take longer though provided we filter a lot.
        // Let's slice 150,000 bars (approx 6 months). If not enough trades, we'll see.

        let dataSlice = data.slice(startIndex, startIndex + 200000);

        const params = {
            tp_mode: 'R',
            tp_value: 2.0, // Per recommendation from MFE analysis
            max_trades: 100,
            exit_time: '9:44',
            penetration_threshold: 0.0,
            max_range_pct: 0.25 // The Filter
        };

        const trades = await strat.run(dataSlice, params);

        console.log(`Trades Found: ${trades.length}`);

        if (trades.length > 0) {
            const pnl = trades.reduce((a, b) => a + b.pnl, 0);
            const wins = trades.filter(t => t.result === 'WIN').length;
            const losses = trades.filter(t => t.result === 'LOSS').length;
            const wr = (wins / trades.length) * 100;

            const startDate = new Date(trades[0].entryDate * 1000).toISOString().split('T')[0];
            const endDate = new Date(trades[trades.length - 1].exitDate * 1000).toISOString().split('T')[0];

            results.push({
                Year: year,
                Trades: trades.length,
                PnL: pnl.toFixed(2),
                WinRate: wr.toFixed(1) + '%',
                Range: `${startDate} to ${endDate}`
            });

            trades.forEach(t => {
                const rangeSize = t.metadata.rangeHigh - t.metadata.rangeLow;
                const rangePct = (rangeSize / t.entryPrice) * 100;
                const dateStr = new Date(t.entryDate * 1000).toISOString();

                allTradesForCsv.push([
                    year,
                    dateStr,
                    t.direction,
                    t.entryPrice.toFixed(2),
                    t.exitPrice.toFixed(2),
                    rangeSize.toFixed(2),
                    rangePct.toFixed(3) + '%',
                    t.result,
                    t.pnl.toFixed(2),
                    t.exitReason
                ].join(','));
            });
        }
    }

    console.table(results);

    // CSV Output
    const csvHeader = "Year,EntryDate,Direction,EntryPrice,ExitPrice,RangeSize_Pts,RangeSize_Pct,Result,PnL,ExitReason\n";
    fs.writeFileSync('multi_year_backtest_2016_2025.csv', csvHeader + allTradesForCsv.join('\n'));
    console.log("CSV saved to multi_year_backtest_2016_2025.csv");
}

main().catch(console.error);
