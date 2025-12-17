
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

async function runTest(data, config) {
    const strat = new Nq1MinCloseInRangeStrategy();

    const params = {
        tp_mode: 'R',
        tp_value: config.target,
        max_trades: 500, // Large sample
        exit_hour: 9,
        exit_minute: 44,
        penetration_threshold: 0.0,
        max_range_pct: config.rangeFilter
    };

    // Filter data for 2016-2025
    const startTs = new Date('2016-01-01T00:00:00.000Z').getTime() / 1000;
    const filtered = data.filter(d => d.time >= startTs);

    const trades = await strat.run(filtered, params);

    const wins = trades.filter(t => t.result === 'WIN').length;
    const pnl = trades.reduce((a, t) => a + t.pnl, 0);

    return {
        trades: trades.length,
        wins,
        winRate: ((wins / trades.length) * 100).toFixed(1) + '%',
        pnl: pnl.toFixed(0),
        avgPnL: (pnl / trades.length).toFixed(2)
    };
}

async function main() {
    console.log('\n=== WIN RATE OPTIMIZATION ANALYSIS ===\n');
    console.log('Loading data...');

    const data = loadDataStandalone('NQ1!', '1m');
    console.log(`Data loaded: ${data.length} bars\n`);

    const targets = [0.5, 1.0, 1.5, 2.0, 3.0];
    const rangeFilters = [0, 0.25, 0.18, 0.15]; // 0 = no filter

    const results = [];

    // Test all combinations
    for (const rangeFilter of rangeFilters) {
        console.log(`\n--- Range Filter: ${rangeFilter === 0 ? 'NONE' : rangeFilter + '%'} ---`);

        for (const target of targets) {
            const config = { target, rangeFilter };
            console.log(`  Testing ${target}R...`);
            const result = await runTest(data, config);

            results.push({
                RangeFilter: rangeFilter === 0 ? 'NONE' : rangeFilter + '%',
                Target: target + 'R',
                ...result
            });
        }
    }

    console.log('\n\n========================================');
    console.log('         COMPLETE RESULTS TABLE');
    console.log('========================================\n');

    console.table(results);

    // Summary analysis
    console.log('\n========================================');
    console.log('         KEY INSIGHTS');
    console.log('========================================\n');

    // Find highest win rate config
    const sorted = [...results].sort((a, b) => parseFloat(b.winRate) - parseFloat(a.winRate));
    console.log('TOP 5 HIGHEST WIN RATES:');
    sorted.slice(0, 5).forEach((r, i) => {
        console.log(`  ${i + 1}. ${r.Target} + ${r.RangeFilter} filter → ${r.winRate} (PnL: ${r.pnl})`);
    });

    // Find highest PnL config
    const sortedPnL = [...results].sort((a, b) => parseFloat(b.pnl) - parseFloat(a.pnl));
    console.log('\nTOP 5 HIGHEST PnL:');
    sortedPnL.slice(0, 5).forEach((r, i) => {
        console.log(`  ${i + 1}. ${r.Target} + ${r.RangeFilter} filter → ${r.pnl} pts (WR: ${r.winRate})`);
    });

    // Range filter impact
    console.log('\n\nRANGE FILTER IMPACT (at 2R target):');
    const twoR = results.filter(r => r.Target === '2R');
    twoR.forEach(r => {
        console.log(`  ${r.RangeFilter.padEnd(10)} → WR: ${r.winRate.padEnd(6)} | PnL: ${r.pnl.padStart(8)} | Trades: ${r.trades}`);
    });
}

main().catch(console.error);
