---
name: nt8-framework-constraints
description: NT8 NinjaScript framework constraints — method visibility, supported C# features, API signatures, common pitfalls. Load BEFORE generating any C# NinjaScript strategy code. Supplements the nt8-docs MCP (which lacks virtual/override modifiers and lifecycle method signatures).
applyTo: "**/*.cs"
---

# NT8 NinjaScript Framework Constraints

**Purpose:** Prevent the compile errors and runtime bugs that occurred during the
2026-07-27 IB strategy implementation session. Load this skill before generating
any C# NinjaScript code. The nt8-docs MCP (`mcp_gitmcp_search_ninjatrader_docs`)
has method signatures but LACKS virtual/override/abstract modifiers and lifecycle
method docs — this skill fills that gap.

## 1. C# Language Feature Support

NT8 uses an older Roslyn compiler. The following C# features are **NOT supported**:

| Feature | Error | Fix |
|---|---|---|
| `record` (C# 9) | CS0518 `IsExternalInit` not defined | Use `class` with constructor + properties |
| `init` accessor (C# 9) | CS0518 | Use `set` |
| Target-typed `new()` (C# 9) | CS0246 | Use explicit `new Type()` |
| Pattern matching `and`/`or` (C# 9) | CS0246 | Use `&&`/`||` |
| File-scoped namespaces (C# 10) | CS8101 | Use block-scoped `namespace { }` |

## 2. Required `using` Directives

Every NinjaScript strategy file must include:

```csharp
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
```

Missing `System.ComponentModel.DataAnnotations` → CS0246 `Display` not found.
Missing `NinjaTrader.NinjaScript.Strategies` → can't inherit `Strategy`.

## 3. Display Attribute

Use `GroupName` NOT `Group`:

```csharp
[Display(Name = "My Param", Order = 1, GroupName = "My Group")]  // ✅ correct
[Display(Name = "My Param", Order = 1, Group = "My Group")]      // ❌ CS0246
```

## 4. EnterLong / EnterShort Signatures

```csharp
EnterLong()                           // 1 contract, auto signal name
EnterLong(string signalName)          // 1 contract, named
EnterLong(int quantity)               // N contracts, auto name
EnterLong(int quantity, string signalName)  // ✅ correct: qty + name
EnterLong(int barsInProgressIndex, int quantity, string signalName)  // multi-series
```

**Common bug:** `EnterLong(qty, price)` — there is NO overload taking a price as
the 2nd arg. The 2nd arg is always `string signalName`. Use `EnterLongLimit(qty, limitPrice, signalName)` for limit entries.

## 5. GetPointValue()

```csharp
protected double GetPointValue()  // NOT a property — it's a method
{
    return Instrument.MasterInstrument.PointValue;
}
```

`PointValue` (as a property) does NOT exist on Strategy. Use `GetPointValue()`.

## 6. Lifecycle Method Visibility (NinjaScriptBase → StrategyBase → Strategy)

These are the virtual/override methods available. **All are `protected override`**
unless noted:

| Method | Defined On | Virtual? | Notes |
|---|---|---|---|
| `OnStateChange()` | NinjaScriptBase | ✅ virtual | Override to handle State.SetDefaults, State.Configure, State.DataLoaded |
| `OnBarUpdate()` | NinjaScriptBase | ✅ virtual | Main bar-by-bar logic. Called once per bar per BarsInProgress. |
| `OnOrderUpdate(...)` | NinjaScriptBase | ✅ virtual | 10-param signature (see below) |
| `OnConnectionStatusUpdate(...)` | StrategyBase | ✅ virtual | **Signature varies by NT8 version** — check before overriding |
| `OnExecutionUpdate(...)` | NinjaScriptBase | ✅ virtual | |
| `OnPositionUpdate(...)` | NinjaScriptBase | ✅ virtual | |

### OnOrderUpdate exact signature (NT8):

```csharp
protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice,
    int quantity, int filled, double averageFillPrice, OrderState orderState,
    DateTime time, ErrorCode error, string nativeError)
```

### OnConnectionStatusUpdate — CAUTION:

The signature has changed across NT8 versions. In some versions it's:
```csharp
protected override void OnConnectionStatusUpdate(ConnectionStatus oldStatus,
    ConnectionStatus newStatus, ConnectionEventArgs e)
```
In others it may be 2-arg. **If you get CS0246 `ConnectionEventArgs` not found,
remove the override entirely** and handle reconnection via the RiskGuard AddOn instead.

## 7. RiskManagerBase (our custom base) — Method Visibility

**CRITICAL:** These methods in `RiskManagerBase` are **NOT virtual** — you cannot
`override` them. Use `new` (hiding) or work around them:

| Method | Visibility | Overridable? | Workaround |
|---|---|---|---|
| `GetCurrentATR()` | `protected` | ❌ NOT virtual | Set `AtrPeriod = 1` in `SetStrategyDefaults()` so ATR is available after 1 bar |
| `CanEnterTrade(int)` | `private` | ❌ NOT accessible | Cannot override; must ensure ATR > 0 and time fence passes |
| `OnNewSession(DateTime)` | `private` | ❌ NOT accessible | Detect session change via date comparison in `CheckForSignal()` |
| `ResetSessionState()` | `private` | ❌ NOT accessible | Called by `OnNewSession`; do your own reset in `CheckForSignal()` |
| `EnterTrade(...)` | `private` | ❌ NOT accessible | Called by `OnBarUpdate` after `CheckForSignal()` returns non-zero |
| `ManageOpenTrade()` | `private` | ❌ NOT accessible | Called by `OnBarUpdate` when position is open |

**Abstract methods you MUST implement:**
| Method | Returns | Notes |
|---|---|---|
| `SetStrategyDefaults()` | void | Set Name, risk params, time fences here |
| `ConfigureStrategy()` | void | AddDataSeries goes here |
| `InitializeStrategy()` | void | Called after DataLoaded |
| `CheckForSignal()` | int | Return 1=long, -1=short, 0=flat |
| `GetStrategyName()` | string | **`protected`** not `public` |

### The ATR Gate Bug (the #1 gotcha):

`RiskManagerBase.OnBarUpdate()` calls `CanEnterTrade(currentTime)` which calls
`GetCurrentATR()`. If ATR returns 0 (which happens when `CurrentBars[1] < AtrPeriod`),
`CanEnterTrade` returns `false` and **ALL entries are blocked**.

`BarsArray[1]` is a 5-min secondary series added by `RiskManagerBase.ConfigureStrategy()`.
With `AtrPeriod = 14` (default), you need 14 × 5 = 70 minutes of data before ATR is non-zero.
If your IB completes at 10:00 (30 min after open), entries between 10:00 and 10:40 are blocked.

**Fix:** Set `AtrPeriod = 1` in your `SetStrategyDefaults()`:
```csharp
AtrPeriod = 1;  // 1 bar needed, not 14 — we don't use ATR for stops anyway
```

**Alternative fix:** Make `GetCurrentATR()` virtual in `RiskManagerBase` (requires
editing the base class) and override it in `IntradayStrategyBase` to return `rangeRange`.

### The Double-Entry Bug:

`RiskManagerBase.OnBarUpdate()` calls `CheckForSignal()`, and if it returns non-zero,
calls `EnterTrade()` with ATR stops. If your `CheckForEntry()` already entered via
`EnterWithRangeStop()`, returning the signal causes a double entry.

**Fix:** Return `0` from `CheckForSignal()` after `CheckForEntry()` enters:
```csharp
int signal = CheckForEntry();
return 0;  // we handle entry inside CheckForEntry; suppress base's EnterTrade
```

### The Name Property Bug:

`RiskManagerBase.SetDefaults()` sets `Name = "RiskManagerBase"`. If you don't override
`Name` in your concrete strategy's `SetStrategyDefaults()`, the Strategy Analyzer loads
`RiskManagerBase` instead of your bot.

**Fix:** Set `Name` AFTER `base.SetStrategyDefaults()`:
```csharp
protected override void SetStrategyDefaults()
{
    base.SetStrategyDefaults();  // sets Name = "RiskManagerBase"
    Name = "IBBreakoutBot";      // override AFTER base call
}
```

## 8. Strategy Analyzer (SA) Backtest via MCP

- SA `Strategy` property: use the **short Name** (`"IBBreakoutBot"`), NOT the qualified
  type name (`"NinjaTrader.NinjaScript.Strategies.Vinay.IBBreakoutBot"`)
- SA `Print()` output goes to the **SA output window**, NOT the main Output tab.
  The MCP `/api/logs?tab=Output` does NOT capture SA strategy prints.
- SA template may override `AtrPeriod` — pass it via `params` in the backtest request
- NT MCP binds to `http://localhost:7890` — use `localhost` NOT `127.0.0.1`

## 9. NT MCP Compile Endpoint

```
POST http://localhost:7890/api/compile  {}  → triggers hot-swap compile
GET  http://localhost:7890/api/compile/result  → reads compile result
```

A successful compile **drops the HTTP connection** as the AppDomain reloads.
Wait 5 seconds then read `/api/compile/result`.

## 10. Pre-Generation Checklist

Before generating any NT8 C# strategy code, verify:

- [ ] All `using` directives present (see §2)
- [ ] `Display` uses `GroupName` not `Group` (see §3)
- [ ] `EnterLong` takes `(int qty, string signalName)` not `(int qty, double price)` (see §4)
- [ ] `GetPointValue()` is a method call, not a property (see §5)
- [ ] No `record`, `init`, target-typed `new()`, or other C# 9+ features (see §1)
- [ ] `GetStrategyName()` is `protected override` not `public override` (see §7)
- [ ] `Name` is set in `SetStrategyDefaults()` AFTER `base.SetStrategyDefaults()` (see §7)
- [ ] `AtrPeriod = 1` if the strategy doesn't use ATR stops (see §7)
- [ ] `CheckForSignal()` returns 0 if `CheckForEntry()` already entered (see §7)
- [ ] `OnConnectionStatusUpdate` signature matches your NT8 version (see §6)