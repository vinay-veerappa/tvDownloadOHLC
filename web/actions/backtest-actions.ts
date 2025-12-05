"use server"

export async function runBacktest() {
    // Simulate processing time
    await new Promise(resolve => setTimeout(resolve, 2000))

    return {
        success: true,
        logs: [
            "[INFO] Initializing Backtest Engine...",
            "[INFO] Loading data for NQ (1min)...",
            "[INFO] Strategy: Simple Moving Average Crossover",
            "[INFO] Processing 1000 candles...",
            "[TRADE] LONG at 15200.50 (2023-10-01 09:30)",
            "[TRADE] CLOSE at 15250.00 (2023-10-01 10:15) | PnL: +$1000.00",
            "[TRADE] SHORT at 15300.00 (2023-10-01 11:00)",
            "[TRADE] CLOSE at 15280.00 (2023-10-01 11:45) | PnL: +$400.00",
            "[INFO] Backtest Complete.",
            "[RESULT] Total PnL: +$1400.00 | Win Rate: 100%"
        ]
    }
}
