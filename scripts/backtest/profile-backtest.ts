
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinStrategy } from '../web/lib/backtest/strategies/nq-1min-strategy';

// Standalone data loader to bypass Next.js action issues
function loadDataStandalone(ticker: string, timeframe: string) {
    const cleanTicker = ticker.replace('!', '');
    const dataDir = path.join(process.cwd(), 'public', 'data', `${cleanTicker}_${timeframe}`);

    if (!fs.existsSync(dataDir)) {
        throw new Error(`Data directory not found: ${dataDir}`);
    }

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

    // Flatten logic
    let data: any[] = [];
    for (let i = chunks.length - 1; i >= 0; i--) {
        data = data.concat(chunks[i]);
    }
    return data;
}

async function profile() {
    console.log("Starting Profiler (CommonJS)...");

    const ticker = "NQ1!";
    const timeframe = "1m";

    // 1. Measure Data Loading
    console.log("1. Measuring Data Loading...");
    const startLoad = performance.now();
    let data;
    try {
        data = loadDataStandalone(ticker, timeframe);
        const endLoad = performance.now();
        console.log(`   Data Loading took: ${(endLoad - startLoad).toFixed(2)}ms`);
        console.log(`   Loaded ${data.length} bars.`);
    } catch (e) {
        console.error("Failed to load data:", e);
        return;
    }

    // 2. Measure Strategy Execution
    console.log("\n2. Measuring Strategy Execution...");
    const strategy = new Nq1MinStrategy();
    const params = {
        tp_mode: 'R' as const,
        tp_value: 3.0,
        max_trades: 0,
        exit_time: '15:55'
    };

    const startStrat = performance.now();
    const trades = await strategy.run(data, params);
    const endStrat = performance.now();
    console.log(`   Strategy Execution took: ${(endStrat - startStrat).toFixed(2)}ms`);
    console.log(`   Generated ${trades.length} trades.`);

    // Summary
    console.log("\n--- SUMMARY ---");
    console.log(`Load: ${(performance.now() - startLoad).toFixed(2)}ms`);
}

profile().catch(console.error);
