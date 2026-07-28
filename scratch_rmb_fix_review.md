# RiskManagerBase Root-Cause Fix — Review Brief

## PROBLEM

`RiskManagerBase` is the reusable base class for ALL NT8 strategies in this project.
Inheritance chain:
```
Strategy (NT8) ← RiskManagerBase (abstract) ← IntradayStrategyBase (abstract, generic intraday)
                ← IBStrategyBase (abstract, IB-specific) ← IBBreakoutBot / IBRetestBot / IBFadeBot
```

### Symptoms
- IBBreakoutBot, IBRetestBot, IBFadeBot all produce **0 trades** in NT8 Strategy Analyzer.
- IBBreakoutBotStandalone (bypasses RiskManagerBase, inherits Strategy directly) produces 283 trades, +.50, 55.8% WR, PF 1.202 — proving the IB logic is correct.
- The standalone was a diagnostic experiment, NOT the intended architecture. Bypassing RiskManagerBase discards: daily max loss, max trades/day, consecutive-loser pause, trailing drawdown, flatten-by (ADR-020), breakeven-trail management, RiskGatekeeper live coordination, OnExecutionUpdate PnL attribution.

### Root Cause (3 issues, all in RiskManagerBase)

**Issue 1: `GetCurrentATR()` is non-virtual**
- `CanEnterTrade()` (private) gates on `GetCurrentATR() > 0`.
- `GetCurrentATR()` returns 0 until the 5-min secondary ATR loads `AtrPeriod` bars (14 bars × 5 min = 70 min).
- IB completes at 10:00 but entries are blocked until ~10:40+ (and with BarsRequiredToTrade=50 on the secondary, until ~13:20).
- IB strategies use the **IB range** as their risk metric, NOT ATR. They cannot substitute it because `GetCurrentATR()` is non-virtual.

**Issue 2: `AddDataSeries(BarsPeriodType.Minute, 5)` is unconditional**
- Every subclass is forced into a 5-min secondary series even when the strategy never reads `Close5m/High5m/Low5m`.
- This creates a `CurrentBars[1]` warmup tax that blocks entries.

**Issue 3: `CanEnterTrade()` is private**
- Cannot override the atr>0 gate. Must fix via `GetCurrentATR` virtual instead.

## PROPOSED FIX (3 changes)

### Change 1: RiskManagerBase.cs
- Add `bool AddSecondaryTimeframe` property (default `true` for backward compat with ATR-based strategies like EMAPullbackBot/VWAPReclaimBot).
- In `OnStateChange State.Configure`: only `AddDataSeries(Minute, 5)` if `AddSecondaryTimeframe` is true.
- In `OnStateChange State.DataLoaded`: only create `atrIndicator = ATR(BarsArray[1], AtrPeriod)` if `AddSecondaryTimeframe` is true.
- Make `GetCurrentATR()` `virtual`. Base impl: return 0 if no secondary/atrIndicator, else `atrIndicator[0]` if `CurrentBars[1] >= AtrPeriod`.
- In `OnBarUpdate`: gate on `CurrentBars[1]` only when `AddSecondaryTimeframe` is true.
- Guard `Close5m/High5m/Low5m` helpers: throw `InvalidOperationException` if called when `AddSecondaryTimeframe` is false.

### Change 2: IntradayStrategyBase.cs
- `override GetCurrentATR()` → return `rangeRange` when `rangeComplete && rangeRange > 0`, else `0`.
- This unblocks `CanEnterTrade` the moment the range completes (10:00 for IB) without waiting for ATR.
- Before rangeComplete, returns 0 so the gate blocks pre-range entries (the time fence `EarliestEntry=930` also guards this).
- Works for ALL range-bounded intraday strategies (IB, ORB, Asia session, midnight OR).

### Change 3: IBStrategyBase.SetStrategyDefaults()
- Set `AddSecondaryTimeframe = false` (IB strategies are range-based, don't need the 5-min series).
- Remove the `AtrPeriod=1` workaround (no longer needed — no secondary to warm up).

## EXPECTED RESULT

IBBreakoutBot (via proper inheritance: RiskManagerBase → IntradayStrategyBase → IBStrategyBase → IBBreakoutBot):
- `BarsRequiredToTrade=1` (already set, only primary series now).
- No 5-min secondary (`AddSecondaryTimeframe=false`).
- `GetCurrentATR()` returns `rangeRange > 0` once IB finalizes at 10:00.
- `CanEnterTrade` atr>0 check passes at 10:00.
- Time fence 930–1430 allows entries from 09:30 to 14:30.
- Entries fire from 10:00 onward (IB breakout).
- ALL risk gates (daily loss, max trades, trailing DD, flatten-by, consecutive losers) remain active.

## OPEN QUESTIONS FOR DEBATE

Q1: Is making `GetCurrentATR()` virtual the right seam, or should `CanEnterTrade()` itself be made `protected virtual` so subclasses can bypass the atr>0 gate entirely? Trade-off: `GetCurrentATR` virtual is more surgical (the gate logic stays intact, only the risk metric is substituted); `CanEnterTrade` virtual is more flexible but risks subclasses accidentally disabling risk gates.

Q2: Should `AddSecondaryTimeframe` be a `[NinjaScriptProperty]` (visible in SA params) or a plain `protected` field set only in code? Trade-off: SA-visible means a user could accidentally enable it for an IB strategy and re-introduce the bug; code-only means less flexibility but safer.

Q3: The `ManageBreakevenTrail` method uses `GetCurrentATR()` for trailing distance. With the override returning `rangeRange`, trailing would use `TrailAtrMult * rangeRange` instead of `TrailAtrMult * ATR`. Is this correct for IB strategies, or should trailing be disabled/overridden for range-based strategies?

Q4: `EnterTrade()` in RiskManagerBase uses `StopAtrMult * GetCurrentATR()` for stop distance. But IntradayStrategyBase.CheckForSignal returns 0 so `EnterTrade` is never called for IB strategies (they enter via `EnterWithRangeStop` in `CheckForEntry`). Is this the right separation, or should `EnterTrade` also be virtual so subclasses can control entry sizing?

Q5: With `AddSecondaryTimeframe=false`, `BarsArray[1]` doesn't exist. The `Close5m/High5m/Low5m` helpers now throw. Are there any existing strategies that inherit `IntradayStrategyBase` and call these helpers? If so, they'd break. (Current answer: no — IB strategies don't use 5-min data. But future strategies might want it.)

Q6: Should `IntradayStrategyBase.GetCurrentATR()` override return `rangeRange` or `StopRMult * rangeRange` (the actual stop distance)? `CanEnterTrade` uses `atr` for: (a) the atr>0 gate, (b) `potentialLoss = StopAtrMult * atr * GetPointValue() * DefaultQuantity`. If we return `rangeRange`, then `potentialLoss = StopAtrMult * rangeRange * PointValue * qty`. Is `StopAtrMult` meaningful for range-based strategies, or should it be 1.0?

## VERIFICATION PLAN

1. Compile all 6 files (RiskManagerBase, IntradayStrategyBase, IBStrategyBase, IBBreakoutBot, IBRetestBot, IBFadeBot) clean in NT8 via MCP `/api/compile`.
2. Backtest IBBreakoutBot (proper inheritance) on MNQ 03-25, Mar 3-14 2025, 1-min bars. Expected: trade count comparable to the standalone's 283 trades (may differ slightly due to risk gates filtering some entries).
3. Backtest IBFadeBot (Play 3, strongest edge E[R] +0.259).
4. Backtest IBRetestBot (Play 2, E[R] +0.097).
5. If all 3 produce trades, the root cause is confirmed fixed and the standalone bots can be deleted.
6. If any produce 0 trades, run the nt8-zero-trade-diagnoser skill.