
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
                // Capture first segment details for metadata
                rangeHigh: t.metadata?.rangeHigh,
                rangeLow: t.metadata?.rangeLow,
                closeInsideExitPrice: null,
                closeInsideExitTime: null,
                segments: []
            };
        }
        groups[t.entryDate].pnl += t.pnl;
        groups[t.entryDate].segments.push(t);

        // Check if this segment was the close inside range exit
        if (t.exitReason === 'CLOSE_INSIDE_RANGE') {
            groups[t.entryDate].closeInsideExitPrice = t.exitPrice;
            groups[t.entryDate].closeInsideExitTime = t.exitDate;
        }
    }
    return Object.values(groups).sort((a: any, b: any) => a.entryDate - b.entryDate);
};

async function analyzeRetracement() {
    console.log("Starting Retracement Analysis...");

    const ticker = "NQ1!";
    const timeframe = "1m";
    const data = loadDataStandalone(ticker, timeframe);

    // Run limit 100
    const params = {
        tp_mode: 'R' as const,
        tp_value: 3.0,
        max_trades: 100,
        exit_time: '9:44'
    };

    console.log("Running Strategies...");
    const baseStrategy = new Nq1MinStrategy();
    const newStrategy = new Nq1MinCloseInRangeStrategy(); // This now has metadata

    // Warning: Base strategy does NOT have metadata populated in my edits.
    // I only edited CloseInRange strategy.
    // But I can get metadata from New Strategy run since entries are same.

    const baseTrades = await baseStrategy.run(data, params);
    const newTrades = await newStrategy.run(data, params);

    const baseGroups = groupTradesByEntry(baseTrades);
    const newGroups = groupTradesByEntry(newTrades);

    console.log(`Analyzed ${Math.min(baseGroups.length, newGroups.length)} trades.`);

    const cutWins = []; // Base WIN, New LOSS or Reduced Profit
    const savedLosses = [];

    const limit = Math.min(baseGroups.length, newGroups.length, 100);

    for (let i = 0; i < limit; i++) {
        const baseT = baseGroups[i];
        const newT = newGroups[i];

        // Identify "Cut Wins" -> Base Result WIN, New Result LOSS or PPnL significantly lower
        const isBaseWin = baseT.pnl > 0;
        const isNewLoss = newT.pnl < 0;

        // Strict Cut Win: Win to Loss
        if (isBaseWin && isNewLoss) {
            cutWins.push({ base: baseT, new: newT });
        }
    }

    console.log(`Found ${cutWins.length} Cut Wins (Base=WIN -> New=LOSS)`);

    // Analyze Quarters
    const quarters = {
        Q1: 0, // 0-25% penetration (shallow)
        Q2: 0, // 25-50%
        Q3: 0, // 50-75%
        Q4: 0  // 75-100% (deep)
    };

    console.log("\n--- Cut Wins Analysis ---");
    console.log("Trade | Dir | Range | Breakout | Exit | Penetration % | Quarter");

    for (const item of cutWins) {
        const t = item.new;
        const rangeHigh = t.rangeHigh;
        const rangeLow = t.rangeLow;
        const exitPrice = t.closeInsideExitPrice;

        if (!rangeHigh || !rangeLow || !exitPrice) {
            console.log("Missing metadata for trade", t.entryDate);
            continue;
        }

        const rangeSize = rangeHigh - rangeLow;
        let penetration = 0;

        if (t.direction === 'LONG') {
            // Long breakout at rangeHigh.
            // Retraced BELOW rangeHigh.
            // Penetration = (High - Exit) / Range
            penetration = (rangeHigh - exitPrice) / rangeSize;
        } else {
            // Short breakout at rangeLow.
            // Retraced ABOVE rangeLow.
            // Penetration = (Exit - Low) / Range
            penetration = (exitPrice - rangeLow) / rangeSize;
        }

        let quarter = '';
        if (penetration <= 0.25) { quarter = 'Q1'; quarters.Q1++; }
        else if (penetration <= 0.50) { quarter = 'Q2'; quarters.Q2++; }
        else if (penetration <= 0.75) { quarter = 'Q3'; quarters.Q3++; }
        else { quarter = 'Q4'; quarters.Q4++; }

        console.log(`#${item.base.entryDate} | ${t.direction} | ${rangeSize.toFixed(2)} | ${t.direction === 'LONG' ? rangeHigh : rangeLow} | ${exitPrice} | ${(penetration * 100).toFixed(1)}% | ${quarter}`);
    }

    console.log("\n--- Summary by Quarter ---");
    console.log(`Q1 (0-25%): ${quarters.Q1}`);
    console.log(`Q2 (25-50%): ${quarters.Q2}`);
    console.log(`Q3 (50-75%): ${quarters.Q3}`);
    console.log(`Q4 (75-100%): ${quarters.Q4}`);

    console.log("\nInterpretation:");
    console.log("If most cut wins are in Q1, it means we are stopping out too early on shallow pullbacks.");
    console.log("If we relax the rule to only close if price penetrates > 25% (enter Q2), we might save these wins.");
}

analyzeRetracement().catch(console.error);
