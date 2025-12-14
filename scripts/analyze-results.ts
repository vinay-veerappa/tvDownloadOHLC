
import fs from 'fs';
import path from 'path';

interface TradeRow {
    EntryTime: string;
    ExitTime: string;
    Direction: string;
    EntryPrice: number;
    ExitPrice: number;
    PnL: number;
    Result: string;
}

function analyze() {
    const csvPath = path.join(process.cwd(), 'backtest_results.csv');
    if (!fs.existsSync(csvPath)) {
        console.error("Results file not found:", csvPath);
        return;
    }

    const content = fs.readFileSync(csvPath, 'utf8');
    const lines = content.trim().split('\n');
    const header = lines[0].split(',');

    // Parse CSV
    const trades: TradeRow[] = lines.slice(1).map(line => {
        const vals = line.split(',');
        return {
            EntryTime: vals[0],
            ExitTime: vals[1],
            Direction: vals[2],
            EntryPrice: parseFloat(vals[3]),
            ExitPrice: parseFloat(vals[4]),
            PnL: parseFloat(vals[5]),
            Result: vals[6]
        };
    });

    // Metrics
    const totalTrades = trades.length;
    const wins = trades.filter(t => t.PnL > 0);
    const losses = trades.filter(t => t.PnL <= 0); // Include breakeven as non-wins? or separate? strict > 0 is win.

    const winRate = (wins.length / totalTrades) * 100;

    const totalPnL = trades.reduce((sum, t) => sum + t.PnL, 0);
    const grossProfit = wins.reduce((sum, t) => sum + t.PnL, 0);
    const grossLoss = Math.abs(losses.reduce((sum, t) => sum + t.PnL, 0));
    const profitFactor = grossLoss === 0 ? grossProfit : grossProfit / grossLoss;

    const avgWin = grossProfit / wins.length || 0;
    const avgLoss = grossLoss / losses.length || 0; // Absolute value

    // Drawdown
    let peak = 0;
    let maxDrawdown = 0;
    let cumulative = 0;
    let equityCurve: number[] = [];

    trades.forEach(t => {
        cumulative += t.PnL;
        equityCurve.push(cumulative);
        if (cumulative > peak) peak = cumulative;
        const dd = peak - cumulative;
        if (dd > maxDrawdown) maxDrawdown = dd;
    });

    console.log("\n=== Backtest Analysis Strategy: NQ 9:30 Reversal ===");
    console.log(`Total Trades: ${totalTrades}`);
    console.log(`Win Rate: ${winRate.toFixed(2)}% (${wins.length} W / ${losses.length} L)`);
    console.log(`Total PnL: ${totalPnL.toFixed(2)} (Points)`);
    console.log(`Profit Factor: ${profitFactor.toFixed(2)}`);
    console.log(`Avg Trade: ${(totalPnL / totalTrades).toFixed(2)}`);
    console.log(`Avg Win: ${avgWin.toFixed(2)}`);
    console.log(`Avg Loss: -${avgLoss.toFixed(2)}`);
    console.log(`Max Drawdown: -${maxDrawdown.toFixed(2)}`);

    // Yearly breakdown
    console.log("\n--- Yearly Performance ---");
    const years: Record<string, number> = {};
    trades.forEach(t => {
        const year = t.EntryTime.substring(0, 4);
        years[year] = (years[year] || 0) + t.PnL;
    });

    Object.keys(years).sort().forEach(y => {
        console.log(`${y}: ${years[y].toFixed(2)}`);
    });
}

analyze();
