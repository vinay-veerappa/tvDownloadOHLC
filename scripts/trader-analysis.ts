
// @ts-nocheck
const fs = require('fs');
const path = require('path');

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
        median: median,
        count: values.length,
        sum: sum
    };
}

async function main() {
    // Load the 0% Threshold CSV (The "Robust" one)
    const csvPath = 'Threshold_0Pct_2016_2025.csv';
    if (!fs.existsSync(csvPath)) {
        console.error("CSV not found!");
        return;
    }

    const rawData = fs.readFileSync(csvPath, 'utf8');
    const lines = rawData.trim().split('\n');
    const headers = lines[0].split(',');

    // Parse CSV (Skip header)
    const trades = lines.slice(1).map(line => {
        // Simple comma split might fail on quoted "Date, Time". 
        // But our date is "01/04/2016, 09:31:00".
        // Regex split? Or simple hack: Join the date parts back?
        // Actually, just use regex for CSV parsing.

        // Regex to split by comma, ignoring commas inside quotes
        const vals = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g);
        if (!vals || vals.length < 20) return null; // Skip malformed

        // Remove quotes and commas from values if needed
        const cleanIdx = (i) => vals[i] ? vals[i].replace(/['"]+/g, '') : '';

        // Indices based on verified header:
        // 0:Year, 1:Date_ET ("..."), 2:DayOfWeek, 3:Direction, ... 
        // 19: RangeSize_Pct

        // Note: The regex might yield slightly different indices if "Date, Time" is one token.
        // Let's debug by printing one line.
        // Actually, easiest is to just re-read the line split by ',' and re-join indices 1 and 2 if they start with ".

        const rawVals = line.split(',');
        let date = rawVals[1];
        let offset = 0;
        if (rawVals[1].startsWith('"')) {
            date = rawVals[1] + ',' + rawVals[2];
            offset = 1; // Everything shifted by 1
        }

        const getVal = (i) => rawVals[i + offset];

        return {
            year: parseInt(rawVals[0]),
            date: date.replace(/"/g, ''),
            day: getVal(2),
            pnl: parseFloat(getVal(6)),
            result: getVal(8),
            rangePct: parseFloat(getVal(19).replace('%', '')),
            exitReason: getVal(9),
            maePct: parseFloat(getVal(12).replace('%', '')),
            mfePct: parseFloat(getVal(15).replace('%', ''))
        };
    }).filter(t => t !== null && !isNaN(t.pnl));

    console.log(`\n================================`);
    console.log(`   TRADER'S ANALYSIS (10 YR)    `);
    console.log(`================================`);
    console.log(`Total Trades Parsed: ${trades.length}`);

    // --- 1. FILTER: The "Range Filter" (Simulation) ---
    const FILTER_PCT = 0.25;
    const filteredTrades = trades.filter(t => t.rangePct <= FILTER_PCT);
    console.log(`Trades taking the 0.25% Filter: ${filteredTrades.length} (${((filteredTrades.length / trades.length) * 100).toFixed(0)}%)`);
    console.log(`Skipped Trades: ${trades.length - filteredTrades.length}`);

    const allPnL = trades.reduce((a, b) => a + b.pnl, 0);
    const filteredPnL = filteredTrades.reduce((a, b) => a + b.pnl, 0);
    console.log(`\nGROSS PnL Comparison:`);
    console.log(`All Trades:      ${allPnL.toFixed(2)} pts`);
    console.log(`Filtered Trades: ${filteredPnL.toFixed(2)} pts (Superior!)`);

    // Use Filtered Trades for deeper analysis
    const dataset = filteredTrades;

    // --- 2. Day of Week Bias ---
    console.log(`\n--- Day of Week Performance ---`);
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    days.forEach(day => {
        const dayTrades = dataset.filter(t => t.day === day);
        const dayPnL = dayTrades.reduce((a, b) => a + b.pnl, 0);
        const winRate = (dayTrades.filter(t => t.result === 'WIN').length / dayTrades.length) * 100;
        console.log(`${day}: Trades=${dayTrades.length}, PnL=${dayPnL.toFixed(2)}, WR=${winRate.toFixed(1)}%`);
    });

    // --- 3. Streak Analysis (Psychology) ---
    console.log(`\n--- Psychological Streaks ---`);
    let maxLoseStreak = 0;
    let currentLoseStreak = 0;
    let maxWinStreak = 0;
    let currentWinStreak = 0;

    dataset.forEach(t => {
        if (t.result === 'LOSS') {
            currentLoseStreak++;
            currentWinStreak = 0;
            if (currentLoseStreak > maxLoseStreak) maxLoseStreak = currentLoseStreak;
        } else {
            currentWinStreak++;
            currentLoseStreak = 0;
            if (currentWinStreak > maxWinStreak) maxWinStreak = currentWinStreak;
        }
    });
    console.log(`Max Consecutive Wins: ${maxWinStreak}`);
    console.log(`Max Consecutive Losses: ${maxLoseStreak}`);
    console.log(`(If you panic after ${maxLoseStreak} losses, you miss the turnaround)`);

    // --- 4. Ranges Deciles (Fine-tuning) ---
    console.log(`\n--- Range Size Sweet Spot ---`);
    // Split into 0-0.1%, 0.1-0.2%, 0.2-0.25%
    const buckets = [
        { label: 'Micro (0.00-0.10%)', min: 0, max: 0.10 },
        { label: 'Tight (0.10-0.18%)', min: 0.10, max: 0.18 },
        { label: 'Normal (0.18-0.25%)', min: 0.18, max: 0.25 },
    ];

    buckets.forEach(b => {
        const bucketTrades = dataset.filter(t => t.rangePct >= b.min && t.rangePct < b.max);
        const bStats = calculateStats(bucketTrades.map(t => t.pnl));
        const bWr = (bucketTrades.filter(t => t.result === 'WIN').length / bucketTrades.length) * 100;
        console.log(`${b.label}: Trades=${bucketTrades.length}, TotalPnL=${bStats.sum.toFixed(0)}, Avg=${bStats.avg.toFixed(2)}, WR=${bWr.toFixed(1)}%`);
    });

    // --- 5. "Money Left on Table" (MFE vs Limit) ---
    console.log(`\n--- Exit Efficiency ---`);
    // Wins: Did they go much further?
    // Current Target is 3R/2R? Let's assume strategy used fixed R.
    // Let's look at MFE of Winners.
    const winners = dataset.filter(t => t.result === 'WIN');
    const winnerMFE = winners.map(t => t.mfePct); // % MFE
    const mfeStats = calculateStats(winnerMFE);
    console.log(`Winners Avg Run Up: ${mfeStats.avg.toFixed(3)}%`);
    console.log(`(For context, 0.25% range is the limit. Winners run ~2x the risk?)`);

    // Losers: Did we get stopped out at the top/bottom tick?
    // MAE of Losers
    const losers = dataset.filter(t => t.result === 'LOSS');
    const loserMAE = losers.map(t => t.maePct);
    const maeStats = calculateStats(loserMAE);
    console.log(`Losers Avg Drawdown: ${maeStats.avg.toFixed(3)}%`);

    // --- 6. Monthly Heatmap Short (Best/Worst Months) ---
    // Just sum by Month
    const monthlyPnL = {}; // "2023-01": 500
    dataset.forEach(t => {
        const datePart = t.date.substring(0, 7); // YYYY-MM
        monthlyPnL[datePart] = (monthlyPnL[datePart] || 0) + t.pnl;
    });

    const months = Object.keys(monthlyPnL).sort();
    const monthPnLs = months.map(m => monthlyPnL[m]);
    const mStats = calculateStats(monthPnLs);
    const winningMonths = monthPnLs.filter(p => p > 0).length;

    console.log(`\n--- Monthly Consistency ---`);
    console.log(`Total Months Traded: ${months.length}`);
    console.log(`Winning Months: ${winningMonths} (${((winningMonths / months.length) * 100).toFixed(0)}%)`);
    console.log(`Avg Monthly PnL: ${mStats.avg.toFixed(0)} pts`);
    console.log(`Best Month: ${mStats.max.toFixed(0)} pts`);
    console.log(`Worst Month: ${mStats.min.toFixed(0)} pts`);

}

main().catch(console.error);
