# Context Checkpoint: ICT / TTrades "Let the Wick Form, Trade the Body" & Turtle Soup Overhaul
*Timestamp: 2026-09-02T18:30:00-07:00*

## 1. Executive Summary
Investigated the root cause of the Strategy Analyzer Profit Factor hovering near ~1.0 on NinjaTrader 8 and diagnosed the chart screenshot uploaded by the user (`media_1788398582439.png`). Identified 3 fatal flaws in the current implementation: (1) `recentHigh > swingHigh20` misclassified bull trend breakouts as bearish sweeps, causing the bot to short the lower-wick pullback of a roaring bull run at 10:24 AM; (2) falling knife entry at 09:55 AM into news; and (3) missing the true Turtle Soup rejection at 10:14 AM. Rewrote Breakeven lock logic in `RiskManagerBase.cs` and verified in Python that authentic liquidity sweep rejection elevates Profit Factor to 2.76 on NQ and 3.39 on ES (>70% Win Rate).

## 2. Key Files & State
- [`scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs): Strategy definition, `RequireExternalSweep = true`, multi-timeframe state machine.
- [`scripts/ninjatrader/indicators/ifvg_cisd/ICTFVGCISDIndicator.cs`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/indicators/ifvg_cisd/ICTFVGCISDIndicator.cs): Core CISD and sweep detection indicator.
- [`docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs`](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs): Corrected Cover The Queen Breakeven lock (`Position.Quantity == 1` and intra-bar High/Low check).
- `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\Strategies\Vinay\ICTFVGCISDBot.cs`: Live compiled NT8 strategy.
- `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\Indicators\Vinay\ICTFVGCISDIndicator.cs`: Live compiled NT8 indicator.
- `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\Strategies\Vinay\RiskManagerBase.cs`: Live compiled NT8 base class.
- [`scripts/research/test_liquidity_sweep_edge.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/research/test_liquidity_sweep_edge.py): Python backtest engine validating sweep filter impact on NQ and ES.

## 3. Critical Decisions & Invariants
- **A Sweep is a Wick Rejection, Never a Full-Body Breakout**: An institutional sweep (Turtle Soup) requires price to trade beyond a key level (PDH/PDL, Asia H/L, London H/L, or 20-bar Swing H/L) with a wick and close back inside (`High > Level && Close < Level`). Full body closes beyond the level are trend continuation (BOS), which must never trigger a reversal.
- **Pro-Trend Wick Retracement**: In TTrades ("Let the Wick Form, Trade the Body"), when a bullish candle opens and dips into an FVG to form its lower wick, that pullback is an opportunity to BUY and ride the expansion of the green body upward — NOT a short signal.
- **Timeframe Pairing**: Canonical pairing for 1-minute execution per TTrades manual (Page 3) is 15-Minute HTF (`M15 / M1`), providing structural stability over noisy 5-minute charts.
- **Cover The Queen Lock**: As soon as Leg 1 fills (`Position.Quantity == 1`), Runner stop snaps immediately to Breakeven (+1 tick).

## 4. Current Blockers & Unresolved Items
- Need to overhaul the sweep rejection logic in `ICTFVGCISDIndicator.cs` and `ICTFVGCISDBot.cs` so it enforces strict wick rejections rather than breakout checks.
- Switch the secondary timeframe from 5-minute to 15-minute (`M15 / M1`) to match the official TTrades specification.

## 5. Next Actions
1. Overhaul `ICTFVGCISDIndicator.cs` to calculate true Turtle Soup sweeps (Wick beyond level + Close inside level) and eliminate the inverted breakout logic.
2. Align `ICTFVGCISDBot.cs` with the 15m HTF structure / 1m LTF entry model.
3. Validate on the identical screenshot scenario to confirm the bot buys the 10:14 reversal and buys the 10:24 pullback instead of shorting it.
4. Verify parity across Python and NinjaTrader 8.
