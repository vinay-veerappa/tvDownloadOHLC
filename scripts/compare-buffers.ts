
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinStrategy } from '../web/lib/backtest/strategies/nq-1min-strategy';
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

async function runBatch(data, batchName, startIndex) {
    console.log(`\n--- Running Batch: ${batchName} ---`);
    const params = {
        tp_mode: 'R' as const,
        tp_value: 3.0,
        max_trades: 100, // Limit to 100 trades for comparison
        exit_time: '9:44'
    };

    // We need to slice data from startIndex. 
    // And to prevent "running out" of data, maybe we should just pass the full data slice?
    // But max_trades handles the limit. We just need to skip the first X trades.
    // The Strategy `run` method doesn't support 'start index' param.
    // We can slice the input array.

    // Safety check
    if (startIndex >= data.length) {
        console.log("Start index exceeds data length.");
        return;
    }

    const dataSlice = data.slice(startIndex);
    console.log(`Data Slice Size: ${dataSlice.length} bars`);

    const results = [];

    // 1. Base Strategy
    const baseStrategy = new Nq1MinStrategy();
    const baseTrades = await baseStrategy.run(dataSlice, params);
    const baseWinRate = baseTrades.filter(t => t.result === 'WIN').length / baseTrades.length;
    const basePnL = baseTrades.reduce((acc, t) => acc + t.pnl, 0);

    results.push({
        name: "Base",
        trades: baseTrades.length,
        wins: baseTrades.filter(t => t.result === 'WIN').length,
        winRate: (baseWinRate * 100).toFixed(1) + "%",
        pnl: basePnL.toFixed(2)
    });

    // 2. Threshold Variants
    const thresholds = [0.0, 0.25, 0.50, 0.75];

    for (const threshold of thresholds) {
        const strat = new Nq1MinCloseInRangeStrategy();
        const p = { ...params, penetration_threshold: threshold };
        const trades = await strat.run(dataSlice, p);

        const winRate = trades.filter(t => t.result === 'WIN').length / trades.length;
        const pnl = trades.reduce((acc, t) => acc + t.pnl, 0);

        results.push({
            name: `Threshold ${(threshold * 100).toFixed(0)}%`,
            trades: trades.length,
            wins: trades.filter(t => t.result === 'WIN').length,
            winRate: (winRate * 100).toFixed(1) + "%",
            pnl: pnl.toFixed(2)
        });
    }

    console.table(results);

    // Return the end index (approximation) so we can offset next batch
    // We processed 100 trades. The last trade exit time gives us a hint.
    if (baseTrades.length > 0) {
        const lastExitTime = baseTrades[baseTrades.length - 1].exitDate;
        // Find rough index in original data
        // Just searching linearly from startIndex is fast enough
        let lastIndex = startIndex;
        for (let i = startIndex; i < data.length; i++) {
            if (data[i].time >= lastExitTime) {
                lastIndex = i;
                break;
            }
        }
        return lastIndex + 1000; // Add buffer to be safe
    }
    return startIndex + 50000; // Fallback
}

async function main() {
    console.log("Loading Data...");
    const ticker = "NQ1!";
    const timeframe = "1m";
    const data = loadDataStandalone(ticker, timeframe);
    console.log(`Total Data: ${data.length} bars`);

    // Batch 1: Start (Index 0)
    const endOfBatch1 = await runBatch(data, "Batch 1 (First 100 Trades)", 0);

    // Batch 2: Offset
    // We want a distinct set. If batch 1 took ~100 days (1 trade/day), that's ~40k bars?
    // Let's use the returned index.

    if (endOfBatch1) {
        // Skip ahead a bit more to be sure
        const startBatch2 = endOfBatch1 + 20000;
        await runBatch(data, "Batch 2 (Next 100 Trades)", startBatch2);
    }
}

main().catch(console.error);
