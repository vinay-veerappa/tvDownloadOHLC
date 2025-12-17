
// @ts-nocheck
const fs = require('fs');

// Parse CSV helper
function parseCSV(filepath) {
    const rawData = fs.readFileSync(filepath, 'utf8');
    const lines = rawData.trim().split('\n');

    return lines.slice(1).map(line => {
        const rawVals = line.split(',');
        let offset = 0;
        if (rawVals[1].startsWith('"')) {
            offset = 1;
        }
        const getVal = (i) => rawVals[i + offset];

        return {
            result: getVal(8),
            mfePct: parseFloat(getVal(15).replace('%', '')),
            rangePct: parseFloat(getVal(19).replace('%', '')),
            pnl: parseFloat(getVal(6))
        };
    }).filter(t => !isNaN(t.pnl));
}

function calculateStats(values) {
    if (values.length === 0) return { min: 0, max: 0, avg: 0, median: 0, p75: 0, p90: 0 };
    const sorted = [...values].sort((a, b) => a - b);
    const sum = values.reduce((a, b) => a + b, 0);
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    const p75 = sorted[Math.floor(sorted.length * 0.75)];
    const p90 = sorted[Math.floor(sorted.length * 0.90)];

    return {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        avg: sum / values.length,
        median,
        p75,
        p90,
        count: values.length
    };
}

async function main() {
    console.log('\n=== MFE ANALYSIS: Optimal Profit Targets ===\n');

    // Load the 0% Threshold CSV (our recommended strategy)
    const trades = parseCSV('Threshold_0Pct_2016_2025.csv');
    console.log(`Total Trades Analyzed: ${trades.length}`);

    // Filter for the "Sweet Spot" ranges (0.10-0.25%)
    const filtered = trades.filter(t => t.rangePct >= 0.10 && t.rangePct <= 0.25);
    console.log(`Sweet Spot Trades (0.10-0.25%): ${filtered.length}\n`);

    // Separate Winners and Losers
    const winners = filtered.filter(t => t.result === 'WIN');
    const losers = filtered.filter(t => t.result === 'LOSS');

    console.log('--- ALL TRADES (Winners + Losers) ---');
    const allMFE = filtered.map(t => t.mfePct);
    const allStats = calculateStats(allMFE);
    console.log(`MFE Stats (All):`);
    console.log(`  Avg:    ${allStats.avg.toFixed(3)}%`);
    console.log(`  Median: ${allStats.median.toFixed(3)}%`);
    console.log(`  75th %: ${allStats.p75.toFixed(3)}%`);
    console.log(`  90th %: ${allStats.p90.toFixed(3)}%`);
    console.log(`  Max:    ${allStats.max.toFixed(3)}%`);

    console.log('\n--- WINNERS ONLY ---');
    const winMFE = winners.map(t => t.mfePct);
    const winStats = calculateStats(winMFE);
    console.log(`MFE Stats (Winners, n=${winners.length}):`);
    console.log(`  Avg:    ${winStats.avg.toFixed(3)}%`);
    console.log(`  Median: ${winStats.median.toFixed(3)}%`);
    console.log(`  75th %: ${winStats.p75.toFixed(3)}%`);
    console.log(`  90th %: ${winStats.p90.toFixed(3)}%`);
    console.log(`  Max:    ${winStats.max.toFixed(3)}%`);

    console.log('\n--- LOSERS (for context) ---');
    const lossMFE = losers.map(t => t.mfePct);
    const lossStats = calculateStats(lossMFE);
    console.log(`MFE Stats (Losers, n=${losers.length}):`);
    console.log(`  Avg:    ${lossStats.avg.toFixed(3)}%`);
    console.log(`  Median: ${lossStats.median.toFixed(3)}%`);

    // Calculate in terms of R-multiples
    // Assuming Range = 1R (the risk)
    console.log('\n--- PROFIT TARGETS (In R-Multiples) ---');
    console.log('Assuming Opening Range Height = 1R (Risk)\n');

    // Typical range is ~0.15-0.20%
    const typicalRange = 0.18; // Midpoint of sweet spot

    console.log(`For a typical ${typicalRange}% range:`);
    console.log(`  0.5R Target = ${(typicalRange * 0.5).toFixed(3)}% move`);
    console.log(`  1.0R Target = ${(typicalRange * 1.0).toFixed(3)}% move`);
    console.log(`  1.5R Target = ${(typicalRange * 1.5).toFixed(3)}% move`);
    console.log(`  2.0R Target = ${(typicalRange * 2.0).toFixed(3)}% move`);
    console.log(`  3.0R Target = ${(typicalRange * 3.0).toFixed(3)}% move`);

    console.log('\n--- RECOMMENDED TARGETS ---');
    console.log(`Based on MFE data:\n`);

    // Calculate what % of winners reach various R levels
    const rangeAvg = filtered.reduce((sum, t) => sum + t.rangePct, 0) / filtered.length;

    const targets = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0];
    targets.forEach(r => {
        const targetPct = rangeAvg * r;
        const reachedCount = winners.filter(t => t.mfePct >= targetPct).length;
        const reachedPct = (reachedCount / winners.length) * 100;
        console.log(`  ${r}R (${targetPct.toFixed(3)}%): ${reachedPct.toFixed(1)}% of winners reached this`);
    });

    console.log('\n--- SCALING STRATEGY RECOMMENDATION ---');
    console.log('Based on the data, consider this scaling approach:\n');
    console.log('  TP1 (50% position): 1.5R - Captures median winner');
    console.log('  TP2 (30% position): 2.5R - Captures above-avg winners');
    console.log('  TP3 (20% position): 4.0R+ - Let runners run');
    console.log('\nThis balances capturing consistent profits while allowing for big winners.');
}

main().catch(console.error);
