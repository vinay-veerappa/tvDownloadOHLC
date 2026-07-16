# NinjaTrader 8 Risk Manager Strategy Suite

This folder implements the NinjaTrader plan with one abstract base class,
three concrete strategies, a shared risk gatekeeper, and a monitoring AddOn.

## File Overview

| File | Role |
|------|------|
| `RiskManagerBase.cs` | Abstract base — session/trade management, entry gates, stop logic |
| `RiskGatekeeper.cs` | Static shared risk registry — per-account state, persistence, recovery |
| `RiskManagerAddOn.cs` | NinjaTrader AddOn — account discovery, real equity, event wiring |
| `VWAPReclaimBot.cs` | Concrete strategy — VWAP reclaim/rejection signal |
| `EMAPullbackBot.cs` | Concrete strategy — EMA pullback continuation signal |
| `FailedAuctionBot.cs` | Concrete strategy — failed auction single-print fill signal |

---

## Architecture

```
RiskManagerAddOn (AddOn)
  │  Discovers all accounts → excludes configured ones
  │  Subscribes to AccountItemUpdate (real equity)
  │  Subscribes to ExecutionUpdate (fills)
  │  Calls RiskGatekeeper.RegisterAccount / UpdateEquity / RecordTrade / ResetDay
  │
  ▼
RiskGatekeeper (static, thread-safe)
  │  Per-account: SessionPnL, TodayTradeCount, ConsecutiveLosers,
  │               IsDoneForDay, IsPaused, AccountEquity, HighWaterMark
  │  Persists state to JSON per account (MyDocuments/NinjaTrader 8/risk_gatekeeper/)
  │  Runtime recovery: RecoverFromHistory() replays broker history on stale state
  │
  ▼
RiskManagerBase (abstract Strategy)
  │  CanEnterTrade() → RiskGatekeeper.CanTrade(Account.Name) first,
  │                    local backtest flags as fallback when AddOn absent
  │  OnExecutionUpdate() → RiskGatekeeper.RecordTrade() after closing fill
  │  ManageOpenTrade()  → RiskGatekeeper.MarkDailyMaxLossBreached() when open PnL limit hit
  │
  ▼
VWAPReclaimBot / EMAPullbackBot / FailedAuctionBot
     Signal logic only (CheckForSignal returns 1 / -1 / 0)
```

---

## What Is Centralised in RiskManagerBase

All non-signal concerns:

- **Session risk**: daily max loss, max trades/day, pause after consecutive losses,
  hard-stop day lockout
- **Account risk tracking**: trailing drawdown based on real account equity (via
  RiskGatekeeper / AddOn)
- **Trade management**: ATR stop placement, fixed target policy,
  breakeven + ATR trail policy
- **Session controls**: earliest/latest entry and flatten-by time fence
- **Shared utilities**: 5-minute ATR, 5-minute OHLC accessors, time-window checks

---

## Bug Fixes Applied (v2)

### 1. Stale `tradeIsActive` Blocking Re-Entry
`FlattenPosition()` now resets `tradeIsActive = false` immediately after issuing
the exit order. Previously the flag was only cleared in `OnExecutionUpdate`, causing
`ManageOpenTrade()` to be called on subsequent bars even when the position was flat,
preventing re-entry for the rest of the bar.

### 2. `OnBarUpdate` Early Return After Forced Flatten
Previously `ManageOpenTrade()` was always followed by `return`, so if it flattened
the position (e.g., daily max loss), the entry gate was never evaluated on that bar.
Now we check `Position.MarketPosition` after `ManageOpenTrade()` and only return if
still in a position.

### 3. Complete Session State Reset
`ResetSessionState()` now resets `tradeDirection`, `entryPrice`, `initialStopPrice`,
`currentStopPrice`, and `riskPoints` in addition to the session counters. Stale values
from the previous session can no longer bleed into the next entry.

### 4. `OnExecutionUpdate` Entry Fill Guard
Split the original single guard into two explicit checks: (1) bail if `tradeIsActive`
is false; (2) bail if `Position.MarketPosition != Flat` (entry fill, position still
open). This prevents PnL double-counting when entry and exit fills fire on the same bar.

---

## Cross-Account Risk (RiskGatekeeper + AddOn)

Previously each strategy instance tracked its own isolated risk state. This meant:
- A loss on Account A had no effect on Account B
- Restarting a strategy reset all counters regardless of trades already taken
- Risk limits were measured against a hardcoded starting balance, not real equity

Now:
- The AddOn subscribes to **all accounts** by default
- Accounts with their own strategy-level risk management can be **excluded** via the
  `ExcludedAccounts` comma-separated parameter (e.g. `"Sim101,MyAlgoAccount"`)
- Real account equity from the broker is the source of truth for drawdown
- State is persisted to JSON and survives NinjaTrader restarts
- On startup, if the persisted state is from a prior day, `RecoverFromHistory()`
  replays today's broker fills to reconstruct where we stand

---

## Strategy Defaults

### VWAPReclaimBot
- Policy: BreakevenTrail | Stop ATR: 2.0 | BE trigger: 2.0R | Trail ATR: 3.5

### EMAPullbackBot
- Policy: FixedTarget | Stop ATR: 1.25 | Target: 3.75R

### FailedAuctionBot
- Policy: BreakevenTrail | Stop ATR: 3.5 | BE trigger: 0.5R | Trail ATR: 1.0

---

## Install into NinjaTrader

### Strategies (all three bots + base)
1. Copy `RiskGatekeeper.cs`, `RiskManagerBase.cs`, `VWAPReclaimBot.cs`,
   `EMAPullbackBot.cs`, `FailedAuctionBot.cs` to:
   `Documents\NinjaTrader 8\bin\Custom\Strategies\Vinay\`
2. Open NinjaScript Editor → compile.
3. Apply each strategy on a 1-minute chart.

### AddOn
1. Copy `RiskManagerAddOn.cs` to:
   `Documents\NinjaTrader 8\bin\Custom\AddOns\`
2. Compile (same NinjaScript Editor).
3. Enable: Control Center → Tools → Options → AddOns → ✓ RiskManagerAddOn
4. Configure `ExcludedAccounts` with any accounts you want to skip.

### State Files
Persisted JSON state files are stored at:
`Documents\NinjaTrader 8\risk_gatekeeper\<AccountName>_risk_state.json`

These are safe to delete to force a clean-slate reset for an account.

---

## Validation Sequence

1. Visual chart validation on Sim account.
2. Strategy Analyzer backtests for 6 months (AddOn not active — local fallback gates apply).
3. Compare trade count, win rate, and PF versus Python research outputs.
4. Run paper trade burn-in with AddOn enabled before any live deployment.
5. Verify `risk_gatekeeper/` state files update correctly after each trade.
6. Kill and restart NinjaTrader mid-session — verify state recovers correctly.

---

## Notes

- The AddOn is optional. Without it, strategies fall back to their own local risk state
  (backward-compatible with backtesting).
- `AccountBlown` persists across sessions and is NOT reset daily. Delete the JSON state
  file or manually edit it to clear an account-blown flag.
- `RiskGatekeeper` is in the `Vinay` namespace alongside the strategies. Both the
  AddOn (in `AddOns` namespace) and strategies reference it by full namespace.
