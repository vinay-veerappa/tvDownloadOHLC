
import { getChartData } from "../web/actions/data-actions";
import { Nq1MinStrategy } from "../web/lib/backtest/strategies/nq-1min-strategy";
import { BacktestConfig } from "../web/lib/backtest/types";

async function runTest() {
    console.log("Starting standalone backtest test...");

    const config: BacktestConfig = {
        ticker: "NQ1!",
        timeframe: "1m",
        strategy: "NQ_1MIN",
        params: {
            tp_mode: "R",
            tp_value: 1.0,
            max_trades: 200
        }
    };

    console.log("Config:", JSON.stringify(config, null, 2));

    const loadStart = performance.now();
    console.log("Loading data (limit = -1)...");

    // Test data loading performance
    const dataResult = await getChartData(config.ticker, config.timeframe, -1);

    const loadEnd = performance.now();
    console.log(`Data load took: ${(loadEnd - loadStart).toFixed(2)}ms`);

    if (!dataResult.success || !dataResult.data) {
        console.error("Failed to load data:", dataResult.error);
        return;
    }

    console.log(`Loaded ${dataResult.data.length} bars`);

    // Test strategy execution performance
    console.log("Running strategy...");
    const strategy = new Nq1MinStrategy();

    const stratStart = performance.now();
    const trades = await strategy.run(dataResult.data, config.params);
    const stratEnd = performance.now();

    console.log(`Strategy run took: ${(stratEnd - stratStart).toFixed(2)}ms`);
    console.log(`Generated ${trades.length} trades`);

    if (trades.length > 0) {
        console.log("First 3 trades:", trades.slice(0, 3));
        console.log("Last 3 trades:", trades.slice(-3));

        // Save to CSV
        const fs = await import('fs');
        const path = await import('path');
        const csvPath = path.join(process.cwd(), '..', 'backtest_results.csv'); // Save to root (since we run from web/)

        const header = "EntryTime,ExitTime,Direction,EntryPrice,ExitPrice,PnL,Result\n";
        const rows = trades.map(t => {
            const entryTime = new Date(t.entryDate * 1000).toISOString();
            const exitTime = new Date(t.exitDate * 1000).toISOString();
            return `${entryTime},${exitTime},${t.direction},${t.entryPrice},${t.exitPrice},${t.pnl},${t.result}`;
        }).join('\n');

        fs.writeFileSync(csvPath, header + rows);
        console.log(`\nResults saved to: ${csvPath}`);
    }
}

runTest().catch(console.error);
