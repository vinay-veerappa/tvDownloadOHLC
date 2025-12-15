
// @ts-nocheck
const fs = require('fs');

// Parse CSV helper
function parseCSV(filepath) {
    const rawData = fs.readFileSync(filepath, 'utf8');
    const lines = rawData.trim().split('\n');

    return lines.slice(1).map(line => {
        const rawVals = line.split(',');
        let offset = 0;
        let dateStr = rawVals[1];
        if (rawVals[1].startsWith('"')) {
            dateStr = rawVals[1] + ',' + rawVals[2];
            offset = 1;
        }
        const getVal = (i) => rawVals[i + offset];

        // Parse time from date string like "01/04/2016, 09:31:00"
        const cleanDate = dateStr.replace(/"/g, '');
        const timePart = cleanDate.split(', ')[1] || cleanDate.split(' ')[1];
        const [hour, minute] = timePart ? timePart.split(':').map(Number) : [0, 0];

        return {
            year: parseInt(rawVals[0]),
            entryHour: hour,
            entryMinute: minute,
            result: getVal(8),
            exitReason: getVal(9),
            mfePct: parseFloat(getVal(15).replace('%', '')),
            rangePct: parseFloat(getVal(19).replace('%', '')),
            pnl: parseFloat(getVal(6))
        };
    }).filter(t => !isNaN(t.pnl) && t.entryHour > 0);
}

function mode(arr) {
    const counts = {};
    arr.forEach(v => counts[v] = (counts[v] || 0) + 1);
    let maxCount = 0, modeVal = null;
    for (const k in counts) {
        if (counts[k] > maxCount) {
            maxCount = counts[k];
            modeVal = k;
        }
    }
    return { value: modeVal, count: maxCount };
}

function calculateStats(values) {
    if (values.length === 0) return { min: 0, max: 0, avg: 0, median: 0 };
    const sorted = [...values].sort((a, b) => a - b);
    const sum = values.reduce((a, b) => a + b, 0);
    const mid = Math.floor(sorted.length / 2);
    return {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        avg: sum / values.length,
        median: sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2,
        count: values.length,
        sum
    };
}

async function main() {
    console.log('\n=== COMPREHENSIVE TIMING & SCALING ANALYSIS ===\n');

    const trades = parseCSV('Threshold_0Pct_2016_2025.csv');
    console.log(`Total Trades: ${trades.length}\n`);

    // Filter for sweet spot
    const filtered = trades.filter(t => t.rangePct >= 0.10 && t.rangePct <= 0.25);
    console.log(`Sweet Spot Trades (0.10-0.25%): ${filtered.length}\n`);

    // ===============================
    // 1. ENTRY TIME ANALYSIS
    // ===============================
    console.log('=== ENTRY TIME ANALYSIS ===\n');

    const entryMinutes = filtered.map(t => t.entryMinute);
    const entryMode = mode(entryMinutes);
    console.log(`Entry Minute Mode: :${entryMode.value} (${entryMode.count} trades)`);

    // Distribution by entry minute
    console.log('\nEntry Time Distribution (ET):');
    const byEntryMinute = {};
    filtered.forEach(t => {
        const key = `9:${t.entryMinute.toString().padStart(2, '0')}`;
        if (!byEntryMinute[key]) byEntryMinute[key] = { trades: [], wins: 0, losses: 0, pnl: 0 };
        byEntryMinute[key].trades.push(t);
        if (t.result === 'WIN') byEntryMinute[key].wins++;
        else byEntryMinute[key].losses++;
        byEntryMinute[key].pnl += t.pnl;
    });

    console.log('Time\t\tTrades\tWins\tLosses\tWR%\tTotal PnL');
    console.log('----\t\t------\t----\t------\t---\t---------');
    Object.keys(byEntryMinute).sort().forEach(time => {
        const d = byEntryMinute[time];
        const wr = ((d.wins / d.trades.length) * 100).toFixed(1);
        console.log(`${time}\t\t${d.trades.length}\t${d.wins}\t${d.losses}\t${wr}%\t${d.pnl.toFixed(0)}`);
    });

    // Should you wait?
    console.log('\n--- WAITING ANALYSIS ---');
    const immediate = filtered.filter(t => t.entryMinute === 31);
    const waited = filtered.filter(t => t.entryMinute >= 32);

    const immPnL = immediate.reduce((a, t) => a + t.pnl, 0);
    const waitPnL = waited.reduce((a, t) => a + t.pnl, 0);
    const immWR = (immediate.filter(t => t.result === 'WIN').length / immediate.length * 100);
    const waitWR = (waited.filter(t => t.result === 'WIN').length / waited.length * 100);
    const immAvg = immPnL / immediate.length;
    const waitAvg = waitPnL / waited.length;

    console.log(`\nImmediate Entry (9:31): ${immediate.length} trades, PnL=${immPnL.toFixed(0)}, WR=${immWR.toFixed(1)}%, Avg=${immAvg.toFixed(2)}`);
    console.log(`Waited Entry (9:32+):   ${waited.length} trades, PnL=${waitPnL.toFixed(0)}, WR=${waitWR.toFixed(1)}%, Avg=${waitAvg.toFixed(2)}`);

    if (immAvg > waitAvg) {
        console.log(`\n>>> VERDICT: Enter immediately (9:31) - ${((immAvg / waitAvg - 1) * 100).toFixed(0)}% better avg PnL`);
    } else {
        console.log(`\n>>> VERDICT: Wait for breakout (9:32+) - ${((waitAvg / immAvg - 1) * 100).toFixed(0)}% better avg PnL`);
    }

    // ===============================
    // 2. EXIT TIME ANALYSIS (by exit reason)
    // ===============================
    console.log('\n\n=== EXIT REASON ANALYSIS ===\n');

    const byExitReason = {};
    filtered.forEach(t => {
        const reason = t.exitReason || 'UNKNOWN';
        if (!byExitReason[reason]) byExitReason[reason] = { count: 0, wins: 0, pnl: 0 };
        byExitReason[reason].count++;
        if (t.result === 'WIN') byExitReason[reason].wins++;
        byExitReason[reason].pnl += t.pnl;
    });

    console.log('Exit Reason\t\tCount\tWins\tWR%\tTotal PnL\tAvg PnL');
    console.log('-----------\t\t-----\t----\t---\t---------\t-------');
    Object.keys(byExitReason).sort().forEach(reason => {
        const d = byExitReason[reason];
        const wr = ((d.wins / d.count) * 100).toFixed(1);
        const avg = (d.pnl / d.count).toFixed(2);
        const reasonPad = reason.padEnd(20);
        console.log(`${reasonPad}\t${d.count}\t${d.wins}\t${wr}%\t${d.pnl.toFixed(0)}\t\t${avg}`);
    });

    // ===============================
    // 3. SCALING SIMULATION
    // ===============================
    console.log('\n\n=== SCALING STRATEGY SIMULATION ===\n');
    console.log('Approach: TP1@1.5R (50%), TP2@2.5R (30%), TP3@4R+ (20%)\n');

    const winners = filtered.filter(t => t.result === 'WIN');
    const losers = filtered.filter(t => t.result === 'LOSS');

    // For simulation, assume range = 1R
    // Winners: Calculate how much of position would have been exited at each level
    let scaledPnL = 0;
    let flatPnL = 0;

    const avgRange = filtered.reduce((sum, t) => sum + t.rangePct, 0) / filtered.length;

    filtered.forEach(t => {
        flatPnL += t.pnl; // Current 2R flat target

        if (t.result === 'LOSS') {
            scaledPnL += t.pnl; // Full loss on losing trades
        } else {
            // Winner - check MFE to see which TPs were hit
            const mfeR = t.mfePct / t.rangePct; // MFE in R-multiples

            // Tiers hit
            let tp1 = mfeR >= 1.5 ? t.rangePct * 1.5 * 0.50 : 0; // 50% at 1.5R
            let tp2 = mfeR >= 2.5 ? t.rangePct * 2.5 * 0.30 : (mfeR >= 1.5 ? t.rangePct * mfeR * 0.30 : 0); // 30% at 2.5R or actual exit
            let tp3 = mfeR >= 4.0 ? t.rangePct * 4.0 * 0.20 : (mfeR >= 1.5 ? t.rangePct * mfeR * 0.20 : 0); // 20% at 4R or actual exit

            // Simplification for simulation: Calculate expected value based on actual MFE
            // If MFE >= level, assume we captured it
            let gain = 0;
            if (mfeR >= 1.5) gain += t.rangePct * 1.5 * 0.50; // TP1 hit
            else gain += t.mfePct * 0.50; // Partial at actual MFE

            if (mfeR >= 2.5) gain += t.rangePct * 2.5 * 0.30; // TP2 hit
            else if (mfeR >= 1.5) gain += Math.min(t.mfePct, t.rangePct * 2.5) * 0.30; // Partial
            else gain += t.mfePct * 0.30;

            if (mfeR >= 4.0) gain += t.rangePct * 4.0 * 0.20; // TP3 hit
            else if (mfeR >= 1.5) gain += Math.min(t.mfePct, t.rangePct * 4.0) * 0.20;
            else gain += t.mfePct * 0.20;

            // Convert back to points (approximate using entry price relationship)
            scaledPnL += (gain / t.rangePct) * Math.abs(t.pnl / (t.result === 'WIN' ? 2 : 1)); // Rough conversion
        }
    });

    console.log(`Flat Exit (2R target):    PnL = ${flatPnL.toFixed(0)} pts`);
    console.log(`Scaled Exit (1.5/2.5/4R): PnL = ${scaledPnL.toFixed(0)} pts (estimate)`);

    // ===============================
    // 4. TIME OF DAY EXIT PATTERNS
    // ===============================
    console.log('\n\n=== EXIT TIME PATTERNS ===\n');

    // For the "No Time Exit" version, we'd need to track exit times
    // For now, analyze exit reasons as proxy

    const tp1Exits = filtered.filter(t => t.exitReason === 'TP1');
    const slExits = filtered.filter(t => t.exitReason === 'SL' || t.exitReason === 'LONG SL' || t.exitReason === 'SHORT SL');
    const closeInRange = filtered.filter(t => t.exitReason === 'CLOSE_INSIDE_RANGE');
    const timeExits = filtered.filter(t => t.exitReason === 'TIME_EXIT');

    console.log('Exit Type Distribution:');
    console.log(`  TP Hit:           ${tp1Exits.length} (${(tp1Exits.length / filtered.length * 100).toFixed(1)}%)`);
    console.log(`  Stop Loss:        ${slExits.length} (${(slExits.length / filtered.length * 100).toFixed(1)}%)`);
    console.log(`  Close In Range:   ${closeInRange.length} (${(closeInRange.length / filtered.length * 100).toFixed(1)}%)`);
    console.log(`  Time Exit (9:44): ${timeExits.length} (${(timeExits.length / filtered.length * 100).toFixed(1)}%)`);

    // Time exit analysis
    if (timeExits.length > 0) {
        const timePnL = timeExits.reduce((a, t) => a + t.pnl, 0);
        const timeWR = (timeExits.filter(t => t.result === 'WIN').length / timeExits.length * 100);
        console.log(`\nTime Exit Analysis:`);
        console.log(`  Total PnL of Time Exits: ${timePnL.toFixed(0)} pts`);
        console.log(`  Win Rate: ${timeWR.toFixed(1)}%`);
        console.log(`  >>> These are trades that COULD run longer with No Time Exit!`);
    }
}

main().catch(console.error);
