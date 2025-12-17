
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinCloseInRangeStrategy } from '../web/lib/backtest/strategies/nq-1min-close-in-range-strategy';

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
    const fullData = loadDataStandalone(ticker, timeframe);
    console.log(`Total Data: ${fullData.length} bars`);

    const years = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016];
    const results = [];

    const strat = new Nq1MinCloseInRangeStrategy();

    // Test with NO TIME EXIT (set to 16:00 - end of session)
    const params = {
        tp_mode: 'R',
        tp_value: 2.0,
        max_trades: 100,
        exit_hour: 16,  // Changed from 9
        exit_minute: 0,  // Changed from 44
        penetration_threshold: 0.0,
        max_range_pct: 0.25
    };

    for (const year of years) {
        console.log(`\n--- Testing Year ${year} (No Time Exit) ---`);

        const startTs = new Date(`${year}-01-01T00:00:00.000Z`).getTime() / 1000;
        let startIndex = -1;

        for (let i = 0; i < fullData.length; i++) {
            if (fullData[i].time >= startTs) {
                startIndex = i;
                break;
            }
        }

        if (startIndex === -1) {
            console.log(`No data found for start of ${year}`);
            continue;
        }

        let dataSlice = fullData.slice(startIndex, startIndex + 200000);

        const trades = await strat.run(dataSlice, params);

        console.log(`Trades Found: ${trades.length}`);

        if (trades.length > 0) {
            const pnl = trades.reduce((a, b) => a + b.pnl, 0);
            const wins = trades.filter(t => t.result === 'WIN').length;
            const wr = (wins / trades.length) * 100;

            const startDate = new Date(trades[0].entryDate * 1000).toISOString().split('T')[0];
            const endDate = new Date(trades[trades.length - 1].exitDate * 1000).toISOString().split('T')[0];

            // Calculate avg trade duration
            const durations = trades.map(t => (t.exitDate - t.entryDate) / 60);
            const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;

            results.push({
                Year: year,
                Trades: trades.length,
                PnL: pnl.toFixed(2),
                WinRate: wr.toFixed(1) + '%',
                AvgDuration_Min: avgDuration.toFixed(1),
                Range: `${startDate} to ${endDate}`
            });
        }
    }

    console.log('\n\n=== COMPARISON: 9:44 Exit vs No Time Exit ===\n');
    console.table(results);

    // Calculate totals
    const totalPnL = results.reduce((sum, r) => sum + parseFloat(r.PnL), 0);
    const totalTrades = results.reduce((sum, r) => sum + r.Trades, 0);
    console.log(`\nTOTAL PnL (No Time Exit): ${totalPnL.toFixed(2)} pts`);
    console.log(`TOTAL Trades: ${totalTrades}`);
    console.log(`\nPrevious (9:44 Exit): +4,418.28 pts (1000 trades)`);
    console.log(`Difference: ${(totalPnL - 4418.28).toFixed(2)} pts`);
}

main().catch(console.error);
