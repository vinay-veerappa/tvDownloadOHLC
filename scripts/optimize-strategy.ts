
import { getChartData } from "../web/actions/data-actions";
import { Nq1MinStrategy } from "../web/lib/backtest/strategies/nq-1min-strategy";
import { BacktestConfig } from "../web/lib/backtest/types";

async function optimize() {
    console.log("Starting optimization...");

    // 1. Load Data Once
    const ticker = "NQ1!";
    const timeframe = "1m";
    console.log("Loading data...");
    const dataResult = await getChartData(ticker, timeframe, -1);

    if (!dataResult.success || !dataResult.data) {
        console.error("Failed to load data");
        return;
    }
    console.log(`Loaded ${dataResult.data.length} bars. Starting sweep...`);

    // 2. Define Parameters to Sweep
    const tp_values = [0.8, 1.0, 1.2, 1.5, 2.0, 3.0];
    const exit_times = [
        { h: 9, m: 44 }, // Original
        { h: 9, m: 59 }, // End of first hour
        { h: 10, m: 29 }, // 10:30 reversal
        { h: 10, m: 59 }, // Lunch
        { h: 15, m: 55 }  // End of day
    ];

    const results: any[] = [];

    // 3. Loop
    const strategy = new Nq1MinStrategy();

    for (const tp of tp_values) {
        for (const time of exit_times) {
            const params = {
                tp_mode: 'R',
                tp_value: tp,
                exit_hour: time.h,
                exit_minute: time.m,
                max_trades: 0
            };

            const trades = await strategy.run(dataResult.data, params);

            // Calculate Profit Factor & Total PnL
            const wins = trades.filter(t => t.pnl > 0);
            const losses = trades.filter(t => t.pnl <= 0);
            const totalPnL = trades.reduce((sum, t) => sum + t.pnl, 0);
            const grossWin = wins.reduce((sum, t) => sum + t.pnl, 0);
            const grossLoss = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0));
            const pf = grossLoss === 0 ? grossWin : grossWin / grossLoss;

            const name = `TP:${tp}R | Exit ${time.h}:${time.m}`;

            results.push({
                name,
                pnl: totalPnL,
                pf,
                trades: trades.length,
                winRate: (wins.length / trades.length) * 100
            });

            process.stdout.write('.');
        }
    }

    console.log("\n\n=== Optimization Results (Sorted by PnL) ===");
    results.sort((a, b) => b.pnl - a.pnl);

    console.table(results.map(r => ({
        Config: r.name,
        'Total PnL': r.pnl.toFixed(0),
        'Profit Factor': r.pf.toFixed(2),
        'Win Rate': r.winRate.toFixed(1) + '%',
        'Trades': r.trades
    })));
}

optimize().catch(console.error);
