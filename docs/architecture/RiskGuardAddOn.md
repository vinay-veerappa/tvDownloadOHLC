# RiskGuardAddOn Architecture

## 1. Overview
The `RiskGuardAddOn` is a centralized, robust risk management module for NinjaTrader that actively monitors positions, orders, and PnL across multiple accounts. It enforces strict trading rules (max size, daily loss, consecutive losses, trading windows, stop-loss attachments) and automatically takes defensive actions (flattening positions, cancelling orders) when thresholds are breached.

## 2. Key Responsibilities
- **Rule Evaluation**: Continuously assesses account states against per-account and aggregate risk configurations.
- **Action Execution**: Cancels orders and flattens positions when breaches occur.
- **StopGuard**: Automatically attaches missing stop-loss orders to unprotected positions, or flattens them after a grace period.
- **Lockout Enforcement**: Locks out accounts when severe limits (daily loss, consecutive losses) are hit, blocking further entry.
- **Thread Safety**: Safely bridges NinjaTrader's asynchronous order/execution events with a central UI/State lock.
- **Testing**: A rigorous `RiskGuardAddOnTests.cs` suite containing 97 unit tests validates edge cases, mode switching (Live/Shadow), and exclusion logic.

## 3. Data Flow
```mermaid
graph TD;
  NT_Events[NinjaTrader Events: OrderUpdate, Execution] --> EventHandlers[OnOrderUpdate / OnExecutionUpdate];
  EventHandlers --> StateModel[Update AccountState];
  StateModel --> EvaluateRules[EvaluateRules()];
  
  Timer[DispatcherTimer: 1 sec pulse] --> SafetySweep[ExecuteSafetySweep()];
  SafetySweep --> SyncPnL[Sync Realized / Unrealized PnL];
  SyncPnL --> EvaluateRules;
  
  EvaluateRules --> GenerateActions[Generate GuardActions];
  GenerateActions --> ProcessAction[ProcessAction()];
  
  ProcessAction --> ActionQueue[NinjaTrader Action Queue];
  ActionQueue --> CancelOrders[Cancel() / Flatten()];
```

## 4. Key Components
- **`RiskGuardAddOn.cs`**: The main AddOn class. Houses the Timer loop (`ExecuteSafetySweep`), the rule engine (`EvaluateRules`), and the action executor (`ProcessAction`).
- **`RiskConfig` / Models**: C# objects parsed from `config.json` defining limits (Sizing, Overtrading, PnL, StopGuard, Windows, FirmMirror).
- **`AccountState`**: In-memory tracker for a specific account's positions, PnL, trades today, and lockout status. 
- **`RiskGuardAddOnTests.cs`**: A dedicated C# test suite utilizing NinjaTrader stubs to run 97 comprehensive scenarios against the `RiskGuardAddOn` logic, ensuring no regressions on exclusions, partial stops, or sweep lockouts.

## 5. Technology & Constraints
- **Concurrency**: Relies heavily on `lock (_stateLock)` because NinjaTrader fires events on different threads. Deadlocks are avoided by yielding the lock before calling NinjaTrader's `Flatten` or `Cancel`.
- **Latency**: The safety sweep runs on a 1-second `DispatcherTimer` to catch lagged PnL updates that native NinjaTrader events might miss.
- **Exclusions**: Specific accounts can be excluded from evaluation. The sweep loop explicitly bypasses these to avoid mutating state (e.g., triggering cooldowns) on ignored accounts.
