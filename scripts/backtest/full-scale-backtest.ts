
// @ts-nocheck
const fs = require('fs');
const path = require('path');
import { Nq1MinStrategy } from '../web/lib/backtest/strategies/nq-1min-strategy';
import { Nq1MinCloseInRangeStrategy } from '../web/lib/backtest/strategies/nq-1min-close-in-range-strategy';

// --- HELPER: Timezone & Formatting ---
const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
});

function getEtTimeStr(timestamp: number): string {
    return formatter.format(new Date(timestamp * 1000));
}

function getDayOfWeek(timestamp: number): string {
    // timestamp is UTC unix
    const date = new Date(timestamp * 1000);
    // Day of week relies on local time usually, but for trading 'Day' is usually based on ET session.
    // However, JS .getDay() is local. We should cast to ET date first.
    // Hack: stringify in ET, then parse back?
    // Simpler: Just allow slightly fuzzy UTC day since NQ trades global. 
    // Actually, user wants 'Market Conditions', likely session day.
    // Let's use the formatter parts.
    const parts = formatter.formatToParts(new Date(timestamp * 1000));
    // Reconstruct date object in 'fake local' time that matches ET?
    // Complicated. 
    // Simple way: Array of days.
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    // 9:30 ET is generally same day UTC except maybe borderline?
    // 9:30 ET is 14:30/13:30 UTC. Same day.
    return days[new Date(timestamp * 1000).getDay()];
}

// --- DATA LOADING ---
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
    console.log("Loading Data (Full 10 Years)...");
    const fullData = loadDataStandalone(ticker, timeframe);
    console.log(`Total Data: ${fullData.length} bars`);

    // Define Strategies
    const strategies = [
        { name: "Base_Strategy", threshold: null }, // Null implies Base Strategy Class
        { name: "Threshold_0Pct", threshold: 0.0 }, // 0% Penetration
        { name: "Threshold_25Pct", threshold: 0.25 },
        { name: "Threshold_50Pct", threshold: 0.50 },
        { name: "Threshold_75Pct", threshold: 0.75 }
    ];

    // Common Params
    const params = {
        tp_mode: 'R',
        tp_value: 2.0,
        max_trades: -1, // No Limit - Full Year
        exit_time: '9:44',
        max_range_pct: 0.0 // DISABLE FILTER so we capture ALL trades for CSV flexibility
    };

    for (const stratConfig of strategies) {
        console.log(`\nRunning ${stratConfig.name}...`);

        let strat;
        if (stratConfig.threshold === null) {
            strat = new Nq1MinStrategy();
        } else {
            strat = new Nq1MinCloseInRangeStrategy();
            params.penetration_threshold = stratConfig.threshold;
        }

        // We want 2016-2025. 
        // Data likely contains it.
        // We can just run on ALL data and filter by Year in CSV writing?
        // Or slice data? Strategy is fast. Running on full 5.6M bars might take 10s.
        // Let's run on full data to be safe.

        const trades = await strat.run(fullData, params);
        console.log(`Generated ${trades.length} trades.`);

        // Filter for 2016-2025
        const startTs = new Date('2016-01-01T00:00:00.000Z').getTime() / 1000;
        const validTrades = trades.filter(t => t.entryDate >= startTs);
        console.log(`Filtered (2016-2025): ${validTrades.length} trades.`);

        // Generate CSV
        const headers = [
            "Year", "Date_ET", "DayOfWeek", "Direction",
            "EntryPrice", "ExitPrice", "PnL_Pts", "PnL_R", "Result", "ExitReason",
            "MAE_Price", "MAE_Pts", "MAE_Pct",
            "MFE_Price", "MFE_Pts", "MFE_Pct",
            "RangeTop", "RangeBot", "RangeSize_Pts", "RangeSize_Pct"
        ].join(",");

        const rows = validTrades.map(t => {
            const dateObj = new Date(t.entryDate * 1000);
            const year = dateObj.getFullYear();
            const dateEt = getEtTimeStr(t.entryDate);
            const dayOfWeek = getDayOfWeek(t.entryDate);

            // MAE/MFE Calcs
            // Ensure inputs exist (Base strategy update should have added them)
            const maePrice = t.mae || t.entryPrice;
            const mfePrice = t.mfe || t.entryPrice;

            let maePts = 0;
            let mfePts = 0;

            if (t.direction === 'LONG') {
                maePts = t.entryPrice - maePrice; // Drawdown
                mfePts = mfePrice - t.entryPrice; // Run up
            } else {
                maePts = maePrice - t.entryPrice; // Drawdown (Price went up)
                mfePts = t.entryPrice - mfePrice; // Run up (Price went down)
            }

            // Stats often used positive values for MAE in DBs
            maePts = Math.max(0, maePts);
            mfePts = Math.max(0, mfePts);

            const maePct = (maePts / t.entryPrice) * 100;
            const mfePct = (mfePts / t.entryPrice) * 100;

            // Range
            const rh = t.metadata?.rangeHigh || 0;
            const rl = t.metadata?.rangeLow || 0;
            const rSize = rh - rl;
            const rPct = t.entryPrice > 0 ? (rSize / t.entryPrice) * 100 : 0;

            // R Multiples (Estimate Risk = Range Size)
            const risk = rSize > 0 ? rSize : 1;
            const pnlR = t.pnl / risk;

            return [
                year,
                `"${dateEt}"`, // Quote date to handle comma space
                dayOfWeek,
                t.direction,
                t.entryPrice.toFixed(2),
                t.exitPrice.toFixed(2),
                t.pnl.toFixed(2),
                pnlR.toFixed(2),
                t.result,
                t.exitReason,
                maePrice.toFixed(2),
                maePts.toFixed(2),
                maePct.toFixed(3) + "%",
                mfePrice.toFixed(2),
                mfePts.toFixed(2),
                mfePct.toFixed(3) + "%",
                rh.toFixed(2),
                rl.toFixed(2),
                rSize.toFixed(2),
                rPct.toFixed(3) + "%"
            ].join(",");
        });

        const filename = `${stratConfig.name}_2016_2025.csv`;
        fs.writeFileSync(filename, headers + "\n" + rows.join("\n"));
        console.log(`Saved ${filename}`);
    }
}

main().catch(console.error);
