# NinjaTrader 8 Risk Manager Strategy Suite

This folder implements the NinjaTrader plan with one abstract base class and three concrete strategies:

- RiskManagerBase.cs
- VWAPReclaimBot.cs
- EMAPullbackBot.cs
- FailedAuctionBot.cs

## What is centralized in the base class

RiskManagerBase handles all non-signal concerns:

- Session risk: daily max loss, max trades/day, pause after consecutive losses, hard-stop day lockout
- Account risk tracking: trailing drawdown based on strategy equity high-water mark
- Trade management: ATR stop placement, fixed target policy, breakeven + ATR trail policy
- Session controls: earliest/latest entry and flatten-by time fence
- Shared utilities: 5-minute ATR, 5-minute OHLC accessors, time-window checks

Each child strategy only returns signal direction through CheckForSignal:

- 1 for long
- -1 for short
- 0 for no trade

## Strategy defaults from the implementation plan

### VWAPReclaimBot
- Policy: BreakevenTrail
- Stop ATR: 2.0
- BE trigger: 2.0R
- Trail ATR: 3.5

### EMAPullbackBot
- Policy: FixedTarget
- Stop ATR: 1.25
- Target: 3.75R

### FailedAuctionBot
- Policy: BreakevenTrail
- Stop ATR: 3.5
- BE trigger: 0.5R
- Trail ATR: 1.0

## Install into NinjaTrader

1. Copy all four .cs files to Documents/NinjaTrader 8/bin/Custom/Strategies.
2. Open NinjaTrader 8, open NinjaScript Editor, compile.
3. Apply each strategy on a 1-minute chart.

## Validation sequence

1. Visual chart validation on Sim account.
2. Strategy Analyzer backtests for 6 months.
3. Compare trade count, win rate, and PF versus Python research outputs.
4. Run paper trade burn-in before any live deployment.

## Notes

- Base class adds a secondary 5-minute series to compute ATR and shared context.
- All entry/exit logs are printed with strategy-prefixed messages for diagnostics.
- Session/account lockouts are strategy-local safeguards and should be treated as execution controls, not broker-level risk hard stops.
