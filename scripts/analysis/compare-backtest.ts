
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinStrategy } from '../web/lib/backtest/strategies/nq-1min-strategy';
import { Nq1MinCloseInRangeStrategy } from '../web/lib/backtest/strategies/nq-1min-close-in-range-strategy';

// Standalone data loader
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

    let data: any[] = [];
    for (let i = chunks.length - 1; i >= 0; i--) {
        data = data.concat(chunks[i]);
    }
    return data;
}

async function runComparison() {
    console.log("Starting Strategy Comparison...");

    const ticker = "NQ1!";
    const timeframe = "1m";

    // 1. Load Data
    console.log("Loading Data...");
    let data;
    try {
        data = loadDataStandalone(ticker, timeframe);
        console.log(`Loaded ${data.length} bars.`);
    } catch (e) {
        console.error("Failed to load data:", e);
        return;
    }

    const params = {
        tp_mode: 'R' as const,
        tp_value: 3.0,
        max_trades: 100, // Limit to 100 trades for comparison
        exit_time: '9:44' // Using default hard exit in strategy, passing param just in case
    };

    // 2. Run Base Strategy
    console.log("Running Base Strategy...");
    const baseStrategy = new Nq1MinStrategy();
    const baseTrades = await baseStrategy.run(data, params);
    console.log(`Base Strategy: ${baseTrades.length} trades generated.`);

    // 3. Run New Strategy
    console.log("Running Close-In-Range Strategy...");
    const newStrategy = new Nq1MinCloseInRangeStrategy();
    const newTrades = await newStrategy.run(data, params);
    console.log(`New Strategy: ${newTrades.length} trades generated.`);

    // 4. Compare
    // Since both strategies run on same data and take 1 trade per day, they should align perfectly by index.
    // However, TP1 splits trades into multiple entries in the 'trades' array?
    // Let's check: Yes, TP1 pushes a trade result.
    // So 'trades' array might have multiple entries per "Day/Trade".
    // We need to group them by Entry Time to compare "Trade vs Trade".

    // Helper to group trades by entry time
    const groupTradesByEntry = (tradesList) => {
        const groups = {};
        for (const t of tradesList) {
            if (!groups[t.entryDate]) {
                groups[t.entryDate] = {
                    entryDate: t.entryDate,
                    direction: t.direction,
                    entryPrice: t.entryPrice,
                    pnl: 0,
                    segments: []
                };
            }
            groups[t.entryDate].pnl += t.pnl;
            groups[t.entryDate].segments.push(t);
        }
        return Object.values(groups).sort((a: any, b: any) => a.entryDate - b.entryDate);
    };

    const baseGroups = groupTradesByEntry(baseTrades);
    const newGroups = groupTradesByEntry(newTrades);

    console.log(`Base Unique Trades: ${baseGroups.length}`);
    console.log(`New Unique Trades: ${newGroups.length}`);

    // CSV Output
    const csvRows = [];
    csvRows.push([
        "TradeNo", "EntryDate", "Direction", "EntryPrice",
        "Base_PnL", "Base_Result", "Base_ExitCount",
        "New_PnL", "New_Result", "New_ExitCount", "New_ExitReasons",
        "PnL_Diff"
    ].join(","));

    // We only traverse up to 100 unique trades or min length
    const limit = Math.min(baseGroups.length, newGroups.length, 100);

    let totalDiff = 0;

    for (let i = 0; i < limit; i++) {
        const baseT = baseGroups[i];
        const newT = newGroups[i];

        // Sanity Check
        if (baseT.entryDate !== newT.entryDate) {
            console.error(`Mismatch at index ${i}: Dates ${baseT.entryDate} vs ${newT.entryDate}`);
            break;
        }

        const dateStr = new Date(baseT.entryDate * 1000).toISOString();
        const pnlDiff = newT.pnl - baseT.pnl;
        totalDiff += pnlDiff;

        // Collect new exit reasons
        const newReasons = newT.segments.map(s => s.exitReason || 'Standard').join('|');

        csvRows.push([
            i + 1,
            dateStr,
            baseT.direction,
            baseT.entryPrice,
            baseT.pnl.toFixed(2),
            baseT.pnl > 0 ? "WIN" : "LOSS",
            baseT.segments.length,
            newT.pnl.toFixed(2),
            newT.pnl > 0 ? "WIN" : "LOSS",
            newT.segments.length,
            newReasons,
            pnlDiff.toFixed(2)
        ].join(","));
    }

    const csvPath = path.join(process.cwd(), 'backtest_comparison.csv');
    fs.writeFileSync(csvPath, csvRows.join('\n'));
    console.log(`\nComparison complete.`);
    console.log(`Total PnL Difference (New - Base): ${totalDiff.toFixed(2)}`);
    console.log(`CSV saved to: ${csvPath}`);
}

runComparison().catch(console.error);
