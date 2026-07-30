# 📈 NinjaTrader 8 Legacy Strategies Index (`From_NT8`)

> [!NOTE]
> The full index and detailed breakdown for strategies in [`scripts/strategies/From_NT8/`](file:///C:/Users/vinay/tvDownloadOHLC/scripts/strategies/From_NT8) can be found in the master documentation at:  
> **[docs/From_NT8/README.md](file:///C:/Users/vinay/tvDownloadOHLC/docs/From_NT8/README.md)**

---

## 📌 Summary Matrix

| Category | Key Strategies | Core Logic |
| :--- | :--- | :--- |
| **ICT & Price Action** | `ICTHighLowBreak`, `ICTFVGBoS`, `VWAPReclaimBot`, `EMAPullbackBot`, `FailedAuctionBot` | Liquidity sweeps, Market Structure Shifts, FVGs, VWAP reclaims & failed auction fills |
| **Opening Range Breakouts** | `ORB_AllDay_MultiTP`, `ORB_V6_Strategy`, `ORBv5Strategy`, `ORBreakoutStrategy`, `ORBStrategyV2_Mikey` | ORB breakout/retest (0%, 25%, 50%), multi-target scaling, Fibonacci extensions |
| **Trend & Moving Average** | `BB1`, `BarUpDown`, `BarUpDownSwingPoints`, `BollingerCrossOver`, `HmaCrossOver`, `SuperTrend`, `WilliamsRStrategy` | Trend following using Heiken Ashi, HMA crossovers, SuperTrend, and Swing point SLs |
| **Volatility & Statistical** | `FiveMinVolatilityAlgo`, `FifteenMinVolatilityAlgo`, `MySigmaSpikesStrategyNT8`, `WeeklyFactorStrategy` | MNQ volatility breakouts, Adam Grimes' SigmaSpikes, TASC Weekly Factor day patterns |
| **Order Flow & Correlated** | `LargeTradesStrategyNT8v3`, `v5`, `CowboyCorrelated` | Cumulative Delta block trade spikes & index pair correlation (ES/NQ) |
| **Utilities & Execution** | `SimpleTradeCopierV2`, `OrderEntryButtons`, `tiyfEasyOrdering`, `EquityGuardNT8strategy` | WPF Trade Copier, ChartTrader execution panels, ATR/PSAR trailing, Equity Guard protection |

---

*For full details, parameter specs, and improvement roadmaps, see the main catalog: **[docs/From_NT8/README.md](file:///C:/Users/vinay/tvDownloadOHLC/docs/From_NT8/README.md)**.*
