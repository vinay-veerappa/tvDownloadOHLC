
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
            pnl: parseFloat(getVal(6)),
            rangePct: parseFloat(getVal(19).replace('%', ''))
        };
    }).filter(t => !isNaN(t.pnl));
}

// Risk of Ruin Formula (simplified Kelly-based)
function calculateRiskOfRuin(winRate, avgWin, avgLoss, accountSize, riskPerTrade) {
    // Using the formula: RoR = ((1 - Edge) / (1 + Edge))^(N)
    // Where Edge = (WinRate * AvgWin - LossRate * AvgLoss) / AvgLoss
    // N = Account / RiskPerTrade

    const lossRate = 1 - winRate;
    const edge = (winRate * avgWin - lossRate * avgLoss) / avgLoss;

    if (edge <= 0) {
        return { ror: 1.0, edge: edge, edgePct: edge * 100 }; // 100% ruin if no edge
    }

    const units = accountSize / riskPerTrade;
    const ror = Math.pow((1 - edge) / (1 + edge), units);

    return {
        ror: Math.min(1, Math.max(0, ror)),
        edge: edge,
        edgePct: edge * 100,
        units: units
    };
}

// Monte Carlo simulation for more accurate RoR
function monteCarloRoR(trades, accountSize, riskPerTrade, simulations = 10000) {
    let ruinCount = 0;
    let maxDrawdownSum = 0;

    for (let sim = 0; sim < simulations; sim++) {
        let balance = accountSize;
        let peak = accountSize;
        let maxDD = 0;

        // Randomly sample trades with replacement
        for (let i = 0; i < 500; i++) { // 500 trades per simulation
            const trade = trades[Math.floor(Math.random() * trades.length)];
            const pnlDollars = trade.pnl * 2; // MNQ = $2/point

            balance += pnlDollars;

            if (balance > peak) peak = balance;
            const dd = (peak - balance) / peak;
            if (dd > maxDD) maxDD = dd;

            if (balance <= 0) {
                ruinCount++;
                break;
            }
        }

        maxDrawdownSum += maxDD;
    }

    return {
        ruinProbability: (ruinCount / simulations) * 100,
        avgMaxDrawdown: (maxDrawdownSum / simulations) * 100
    };
}

async function main() {
    console.log('\n=== RISK OF RUIN ANALYSIS ===');
    console.log('Account: $3,000 | Contract: MNQ ($2/point)\n');

    const trades = parseCSV('Threshold_0Pct_2016_2025.csv');
    console.log(`Trades Analyzed: ${trades.length}\n`);

    // Calculate stats
    const winners = trades.filter(t => t.result === 'WIN');
    const losers = trades.filter(t => t.result === 'LOSS');

    const winRate = winners.length / trades.length;
    const avgWinPts = winners.reduce((a, t) => a + t.pnl, 0) / winners.length;
    const avgLossPts = Math.abs(losers.reduce((a, t) => a + t.pnl, 0) / losers.length);

    const avgWin$ = avgWinPts * 2; // MNQ
    const avgLoss$ = avgLossPts * 2;

    console.log('--- Trade Statistics ---');
    console.log(`Win Rate: ${(winRate * 100).toFixed(1)}%`);
    console.log(`Avg Win:  ${avgWinPts.toFixed(2)} pts ($${avgWin$.toFixed(2)})`);
    console.log(`Avg Loss: ${avgLossPts.toFixed(2)} pts ($${avgLoss$.toFixed(2)})`);
    console.log(`Win/Loss Ratio: ${(avgWin$ / avgLoss$).toFixed(2)}`);

    // Calculate expectancy
    const expectancy = (winRate * avgWin$) - ((1 - winRate) * avgLoss$);
    console.log(`\nExpectancy per Trade: $${expectancy.toFixed(2)}`);

    // Risk scenarios
    const accountSize = 3000;
    const riskScenarios = [
        { name: '1%', risk: 30 },
        { name: '2%', risk: 60 },
        { name: '3%', risk: 90 },
        { name: '5%', risk: 150 },
        { name: '10%', risk: 300 }
    ];

    console.log('\n--- Risk of Ruin by Position Size ---');
    console.log('Risk %\t\tRisk $\t\tMax Contracts\tRoR (Formula)\tRoR (MonteCarlo)');
    console.log('------\t\t------\t\t-------------\t-------------\t----------------');

    for (const scenario of riskScenarios) {
        // Calculate max contracts based on avg loss
        const maxContracts = Math.max(1, Math.floor(scenario.risk / avgLoss$));

        const formulaRoR = calculateRiskOfRuin(winRate, avgWin$, avgLoss$, accountSize, scenario.risk);
        const mcResult = monteCarloRoR(trades, accountSize, scenario.risk, 5000);

        console.log(`${scenario.name}\t\t$${scenario.risk}\t\t${maxContracts}\t\t${(formulaRoR.ror * 100).toFixed(2)}%\t\t${mcResult.ruinProbability.toFixed(2)}%`);
    }

    // Detailed analysis for recommended risk level (2%)
    console.log('\n\n--- DETAILED ANALYSIS: 2% Risk ($60/trade) ---');
    const mcDetailed = monteCarloRoR(trades, accountSize, 60, 10000);
    console.log(`Risk of Ruin: ${mcDetailed.ruinProbability.toFixed(2)}%`);
    console.log(`Avg Max Drawdown: ${mcDetailed.avgMaxDrawdown.toFixed(1)}%`);

    // Calculate drawdown in dollars
    const pnls = trades.map(t => t.pnl * 2); // Convert to dollars
    let balance = accountSize;
    let peak = accountSize;
    let maxDD = 0;
    let maxDDDollars = 0;
    let consecutiveLosses = 0;
    let maxConsecLosses = 0;

    trades.forEach(t => {
        const pnl = t.pnl * 2;
        balance += pnl;
        if (balance > peak) peak = balance;
        const dd = peak - balance;
        if (dd > maxDDDollars) maxDDDollars = dd;

        if (t.result === 'LOSS') {
            consecutiveLosses++;
            if (consecutiveLosses > maxConsecLosses) maxConsecLosses = consecutiveLosses;
        } else {
            consecutiveLosses = 0;
        }
    });

    console.log(`\nHistorical Max Drawdown: $${maxDDDollars.toFixed(2)} (${(maxDDDollars / accountSize * 100).toFixed(1)}%)`);
    console.log(`Max Consecutive Losses: ${maxConsecLosses}`);
    console.log(`Worst Case Loss (${maxConsecLosses} losses): $${(maxConsecLosses * avgLoss$).toFixed(2)}`);

    // Recommendation
    console.log('\n\n=== RECOMMENDATION ===');
    if (mcDetailed.ruinProbability < 1) {
        console.log('✅ 2% risk ($60/trade) is SAFE for this strategy');
        console.log('   - Risk of Ruin: < 1%');
        console.log('   - You can trade 1 MNQ contract per trade');
    } else if (mcDetailed.ruinProbability < 5) {
        console.log('⚠️  2% risk is acceptable but aggressive');
        console.log('   - Consider 1% risk for more safety');
    } else {
        console.log('❌ This strategy has high ruin probability at 2% risk');
        console.log('   - Use 1% risk or increase account size');
    }

    console.log('\n--- Position Sizing for $3,000 Account ---');
    const avgRangePts = trades.reduce((a, t) => a + (t.rangePct * 20000 / 100), 0) / trades.length; // Approx points
    console.log(`Avg Range (Risk): ~${avgRangePts.toFixed(0)} pts (~$${(avgRangePts * 2).toFixed(0)} on MNQ)`);
    console.log(`\nWith $60 max risk (2%):`);
    console.log(`  If range <= 30 pts: Trade 1 MNQ`);
    console.log(`  If range > 30 pts: SKIP (risk too high)`);
}

main().catch(console.error);
