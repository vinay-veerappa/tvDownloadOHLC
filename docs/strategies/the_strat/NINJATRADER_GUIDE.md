# NinjaTrader 8 Integration & Deployment Guide: The Strat

This guide details how to deploy, compile, and run **The Strat** indicators and automated strategies in **NinjaTrader 8**.

---

## 1. File Locations in Repository

| Type | Script Name | Canonical Path | Description |
|---|---|---|---|
| **Indicator** | `TheStratClassifier.cs` | `scripts/ninjatrader/indicators/the_strat/TheStratClassifier.cs` | Paints `1`, `2U`, `2D`, `3` above/below candles and exports data series. |
| **Indicator** | `TheStratFTFCHud.cs` | `scripts/ninjatrader/indicators/the_strat/TheStratFTFCHud.cs` | Real-time Multi-Timeframe Continuity HUD dashboard table. |
| **Strategy** | `Strat212ContinuationBot.cs` | `scripts/ninjatrader/strategies/the_strat/Strat212ContinuationBot.cs` | Automated 2-1-2 bot inheriting from `RiskManagerBase`. |
| **Strategy** | `Strat22RevStratBot.cs` | `scripts/ninjatrader/strategies/the_strat/Strat22RevStratBot.cs` | Automated 2-2 reversal bot inheriting from `RiskManagerBase`. |

---

## 2. Dependencies

The strategies inherit from [`RiskManagerBase`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/strategies/base/RiskManagerBase.cs) located at `scripts/ninjatrader/strategies/base/RiskManagerBase.cs`.

Ensure `RiskManagerBase.cs` is included in your NinjaTrader 8 custom strategies directory:
- **NT8 Custom Strategies Folder**: `Documents\NinjaTrader 8\bin\Custom\Strategies\`
- **NT8 Custom Indicators Folder**: `Documents\NinjaTrader 8\bin\Custom\Indicators\`

---

## 3. Deploying & Compiling in NinjaTrader 8

### Option A: Direct Symlink / File Copy
Copy or link the files to your NinjaTrader 8 Custom folder:
```powershell
# Copy Indicators
Copy-Item scripts\ninjatrader\indicators\the_strat\*.cs "$HOME\Documents\NinjaTrader 8\bin\Custom\Indicators\"

# Copy Strategies
Copy-Item scripts\ninjatrader\strategies\the_strat\*.cs "$HOME\Documents\NinjaTrader 8\bin\Custom\Strategies\"
Copy-Item scripts\ninjatrader\strategies\base\RiskManagerBase.cs "$HOME\Documents\NinjaTrader 8\bin\Custom\Strategies\"
```

### Option B: Compile via NinjaScript Editor / NinjaTrader MCP
In NinjaTrader 8:
1. Press `F5` or open **New > NinjaScript Editor**.
2. Right-click the editor window and select **Compile** (`F5`).
3. Verify 0 errors in the Output window.

---

## 4. Strategy Parameter Recommendations

### `Strat212ContinuationBot` (NQ 5-Min Chart)
- **Timeframe**: 5-minute (NQ or MNQ)
- **UseFTFCFilter**: `True`
- **MinFTFCScore**: `2` (requires at least 2 agreeing timeframes)
- **MinRewardRiskRatio**: `1.0`
- **DailyMaxLoss**: `$500` (for MNQ: `$50`)
- **MaxConsecutiveLosers**: `2` (auto 30-min pause)
- **EarliestEntry**: `0930` ET
- **LatestEntry**: `1530` ET
- **FlattenBy**: `1555` ET

---

## 5. Cross-Platform Reconciliation with Python

To reconcile trade-by-trade executions between NT8 Strategy Analyzer and Python:
1. Export trades from NinjaTrader 8 Strategy Analyzer as CSV.
2. Place the export in `data/range_prob/backtest_feeds/` or `scripts/strategies/From_NT8/`.
3. Run the Trade Reconciler to verify 1:1 match in entries, stops, and magnitude target fills.
