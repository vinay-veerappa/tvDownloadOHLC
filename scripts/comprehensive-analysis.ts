
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

// Stats helper
function calculateStats(values) {
    if (values.length === 0) return { min: 0, max: 0, avg: 0, median: 0 };
    const sorted = [...values].sort((a, b) => a - b);
    const sum = values.reduce((a, b) => a + b, 0);
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    return {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        avg: sum / values.length,
        median: median
    };
}

// Mode helper
function calculateMode(values) {
    const counts = {};
    for (const v of values) counts[v] = (counts[v] || 0) + 1;
    let mode = null;
    let maxCount = 0;
    for (const k in counts) {
        if (counts[k] > maxCount) {
            maxCount = counts[k];
            mode = k;
        }
    }
    return mode;
}

async function analyzeBatch(data, batchName, startIndex) {
    console.log(`\n\n==================================================`);
    console.log(`ANALYSIS REPORT: ${batchName}`);
    console.log(`==================================================`);

    // Safety check
    if (startIndex >= data.length) return startIndex; // return current index if OOB

    const dataSlice = data.slice(startIndex);

    // Determine Date Range of Slice (approx)
    const startDate = new Date(dataSlice[0].time * 1000).toISOString().split('T')[0];

    const params = {
        tp_mode: 'R' as const,
        tp_value: 3.0,
        max_trades: 100,
        exit_time: '9:44',
        penetration_threshold: 0.0 // Strict 0%
    };

    // Run Strategies
    const baseStrat = new Nq1MinStrategy();
    const newStrat = new Nq1MinCloseInRangeStrategy();

    const baseTrades = await baseStrat.run(dataSlice, params);
    const newTrades = await newStrat.run(dataSlice, params);

    // Wait... max_trades limits the OUTPUT array length.
    // The strategies might process slightly different amount of data if one generates MORE trades per bar (unlikely here).

    if (baseTrades.length === 0) return startIndex;

    const endDate = new Date(baseTrades[baseTrades.length - 1].exitDate * 1000).toISOString().split('T')[0];
    console.log(`Date Range: ${startDate} to ${endDate}`);
    console.log(`Trades Analyzed: Base=${baseTrades.length}, New=${newTrades.length}`);

    // --- 1. MAE / MFE Analysis (Base Strategy - Unfiltered behavior) ---
    console.log(`\n--- MAE / MFE Analysis (Base Strategy) ---`);
    const maes_pts = [];
    const mfes_pts = [];
    const maes_pct = [];
    const mfes_pct = [];

    baseTrades.forEach(t => {
        // MAE is "Adverse" price. Difference from Entry.
        // Long: Entry - MAE_Price
        // Short: MAE_Price - Entry
        // Always positive distance
        let maeDist = 0;
        let mfeDist = 0;

        if (t.direction === 'LONG') {
            maeDist = t.entryPrice - (t.mae || t.entryPrice);
            mfeDist = (t.mfe || t.entryPrice) - t.entryPrice;
        } else {
            maeDist = (t.mae || t.entryPrice) - t.entryPrice;
            mfeDist = t.entryPrice - (t.mfe || t.entryPrice);
        }

        // Ensure non-negative (sometimes init logic might be slightly off if gap)
        maeDist = Math.max(0, maeDist);
        mfeDist = Math.max(0, mfeDist);

        maes_pts.push(maeDist);
        mfes_pts.push(mfeDist);

        maes_pct.push((maeDist / t.entryPrice) * 100);
        mfes_pct.push((mfeDist / t.entryPrice) * 100);
    });

    const maeStats = calculateStats(maes_pts);
    const mfeStats = calculateStats(mfes_pts);

    console.log(`Effective MAE (Points): Avg=${maeStats.avg.toFixed(2)}, Median=${maeStats.median.toFixed(2)}, Max=${maeStats.max.toFixed(2)}`);
    console.log(`Effective MFE (Points): Avg=${mfeStats.avg.toFixed(2)}, Median=${mfeStats.median.toFixed(2)}, Max=${mfeStats.max.toFixed(2)}`);

    // PnL vs MFE Correlation (Win Potential)
    // Avg MFE of Winning Trades vs Avg MFE of Losing Trades
    const winMFE = [];
    const lossMFE = [];
    baseTrades.forEach((t, i) => {
        const mfe = mfes_pts[i];
        if (t.result === 'WIN') winMFE.push(mfe);
        else lossMFE.push(mfe);
    });
    console.log(`Avg MFE of Winners: ${calculateStats(winMFE).avg.toFixed(2)}`);
    console.log(`Avg MFE of Losers:  ${calculateStats(lossMFE).avg.toFixed(2)}  <-- Potential missed profit?`);

    // --- 2. Timing Analysis ---
    console.log(`\n--- Timing Analysis ---`);
    const durations = baseTrades.map(t => (t.exitDate - t.entryDate) / 60); // minutes
    const durStats = calculateStats(durations);
    console.log(`Trade Duration (min): Avg=${durStats.avg.toFixed(1)}, Median=${durStats.median.toFixed(1)}, Max=${durStats.max.toFixed(1)}`);

    const entryHours = baseTrades.map(t => {
        const d = new Date(t.entryDate * 1000);
        // UTC to ET conversion roughly (if server is UTC)
        // Wait, timestamps are Unix. 
        // We can just look at minute past 9:30 if we assume they are all 9:30 trades?
        // Ah, current strategy ONLY enters at 9:30 range breakout (9:31+).
        // Let's see entry distribution relative to 9:30.
        // Assuming data is correct, let's just show entry Minute (0-59).
        // Actually, let's show "Minutes after 9:30".

        // Need to parse properly with timezone but rough relative check:
        // entryDate - (9:30 timestamp of that day).
        // Hard to calculate 9:30 timestamp without heavy lifting.
        // Let's just look at minute component of entry time?
        return d.getMinutes();
    });
    console.log(`Entry Minute Mode: ${calculateMode(entryHours)}`);


    // --- 3. Range Size Analysis ---
    console.log(`\n--- Range Size Correlations ---`);
    const ranges = [];

    baseTrades.forEach(t => {
        if (t.metadata && t.metadata.rangeHigh) {
            const size = t.metadata.rangeHigh - t.metadata.rangeLow;
            const pct = (size / t.entryPrice) * 100;
            ranges.push({
                size: size,
                pct: pct,
                result: t.result,
                pnl: t.pnl
            });
        }
    });

    if (ranges.length > 0) {
        const rangeSizes = ranges.map(r => r.size);
        const rangePcts = ranges.map(r => r.pct);
        const rStats = calculateStats(rangeSizes);
        const pStats = calculateStats(rangePcts);

        console.log(`Avg Entry Price: ${calculateStats(baseTrades.map(t => t.entryPrice)).avg.toFixed(2)}`);
        console.log(`Range Size (Pts): Avg=${rStats.avg.toFixed(2)}, Median=${rStats.median.toFixed(2)}, Max=${rStats.max.toFixed(2)}`);
        console.log(`Range Size (%):   Avg=${pStats.avg.toFixed(3)}%, Median=${pStats.median.toFixed(3)}%, Max=${pStats.max.toFixed(3)}%`);

        // Correlation by % Median
        const medianPct = pStats.median;
        const smallRangePnL = ranges.filter(r => r.pct < medianPct).reduce((a, b) => a + b.pnl, 0);
        const largeRangePnL = ranges.filter(r => r.pct >= medianPct).reduce((a, b) => a + b.pnl, 0);

        console.log(`PnL (Small Ranges < ${medianPct.toFixed(3)}%): ${smallRangePnL.toFixed(2)}`);
        console.log(`PnL (Large Ranges >= ${medianPct.toFixed(3)}%): ${largeRangePnL.toFixed(2)}`);
    } else {
        console.log("No metadata available for Range Analysis.");
    }

    // --- 4. Strategy Comparison Stats ---
    console.log(`\n--- Comparison (Base vs New) ---`);
    const basePnL = baseTrades.reduce((a, t) => a + t.pnl, 0);
    const newPnL = newTrades.reduce((a, t) => a + t.pnl, 0);

    const baseWR = (baseTrades.filter(t => t.result === 'WIN').length / baseTrades.length) * 100;
    const newWR = (newTrades.filter(t => t.result === 'WIN').length / newTrades.length) * 100;

    console.log(`Base: PnL=${basePnL.toFixed(2)}, WR=${baseWR.toFixed(1)}%`);
    console.log(`New:  PnL=${newPnL.toFixed(2)}, WR=${newWR.toFixed(1)}%`);
    console.log(`Diff: PnL=${(newPnL - basePnL).toFixed(2)}, WR=${(newWR - baseWR).toFixed(1)}%`);


    // Return end index for next batch
    const lastExitTime = baseTrades[baseTrades.length - 1].exitDate;
    let lastIndex = startIndex;
    for (let i = startIndex; i < data.length; i++) {
        if (data[i].time >= lastExitTime) {
            lastIndex = i;
            break;
        }
    }
    return lastIndex + 1000;
}

async function main() {
    const ticker = "NQ1!";
    const timeframe = "1m";
    console.log("Loading Data...");
    const data = loadDataStandalone(ticker, timeframe);
    console.log(`Total Data: ${data.length} bars`);

    let nextIndex = 0;
    nextIndex = await analyzeBatch(data, "Batch 1 (Bullish/Constructive)", nextIndex);

    // Skip to next distinct period (approx +20k bars for 100 trades)
    if (nextIndex) {
        nextIndex += 20000;
        await analyzeBatch(data, "Batch 2 (Drawdown/Challenging)", nextIndex);
    }
}

main().catch(console.error);
