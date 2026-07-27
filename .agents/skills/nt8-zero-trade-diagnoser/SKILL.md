---
name: nt8-zero-trade-diagnoser
description: Auto-diagnose NT8 Strategy Analyzer backtests that return 0 trades. Checks common blockers: wrong strategy loaded, ATR gate, time fence, CanEnterTrade, calendar filter, range-size filter, DATA AVAILABILITY. Run AFTER a backtest returns tradeCount=0.
applyTo: "**"
---

# NT8 Zero-Trade Diagnoser

**When to use:** after `POST /api/backtest` returns `tradeCount: 0`.
**Purpose:** instantly identify the blocker instead of guessing.

## ⚠️ STEP 0 (DO THIS FIRST): Check if ANY strategy produces trades

**CRITICAL LESSON (2026-07-27):** Before debugging your strategy code, run an
EXISTING root-folder strategy (e.g. `ORBv5Strategy`) on the same symbol/date range.
If it also returns 0 trades, the problem is NOT your code — it's data availability
or SA state. Do NOT waste cycles fixing strategy code if ALL strategies produce 0 trades.

```powershell
# Run this FIRST
$body = @{ strategy = "ORBv5Strategy"; symbol = "NQ ##-##"; from = "2025-01-01"; to = "2025-06-30"; period = "Minute"; periodValue = 1 } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "http://localhost:7890/api/backtest" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 300
"ORBv5 trades: $($r.tradeCount)"
# If 0 → problem is data/SA, NOT your strategy. Check data availability first.
# If >0 → problem IS your strategy. Proceed to Step 1.
```

**If ALL strategies return 0 trades:**
1. Check `/api/quote?symbol=NQ+%23%23-%23%23` — if all zeros, NT8 has no data connection
2. Check if NT8 has cached historical data in `Documents\NinjaTrader 8\db\`
3. Restart NT8 (the SA window may have lost its data series after hot-swap compiles)
4. Try the backtest from the NT8 GUI (not MCP) to isolate MCP vs SA issues
5. Verify a data provider (Kinetick/Rithmic/Denada) is connected

## Diagnostic Script

```powershell
# Usage: .\diagnose_zero_trades.ps1 -Strategy "IBBreakoutBot" -BacktestResponse $r
# Or run manually after a backtest:

# 1. Check if the correct strategy loaded (summary should show strategy name, not RiskManagerBase)
if ($r.summary -match "RiskManagerBase Backtest") {
    Write-Host "❌ WRONG STRATEGY: SA loaded RiskManagerBase, not your bot."
    Write-Host "   FIX: Set Name='YourBotName' in SetStrategyDefaults() AFTER base.SetStrategyDefaults()"
    Write-Host "   Also: use short name in backtest request, not qualified type name"
}

# 2. Check AtrPeriod in summary (should be 1 if not using ATR stops)
if ($r.summary -match "/14/") {
    Write-Host "❌ ATR GATE: AtrPeriod=14 in summary. CanEnterTrade blocks until 70 min of 5-min data."
    Write-Host "   FIX: Set AtrPeriod=1 in SetStrategyDefaults()"
}

# 3. Check time fence (EarliestEntry/LatestEntry)
$earliest = if ($r.summary -match "(\d{3,4})/(\d{3,4})/(\d{3,4})") { $matches[1] } else { "930" }
$latest   = if ($r.summary -match "(\d{3,4})/(\d{3,4})/(\d{3,4})") { $matches[2] } else { "1430" }
Write-Host "ℹ️ Time fence: EarliestEntry=$earliest LatestEntry=$latest FlattenBy=..."

# 4. Check if CheckForSignal is being called (look for DIAG logs)
$logs = Invoke-RestMethod -Uri "http://localhost:7890/api/logs?lines=200&tab=Output" -Method Get -TimeoutSec 30
$diag = $logs.logs | Where-Object { $_ -match "DIAG" }
if ($diag.Count -eq 0) {
    Write-Host "❌ NO DIAG LOGS: CheckForSignal() may not be called."
    Write-Host "   Possible causes:"
    Write-Host "   - BarsInProgress != 0 (base OnBarUpdate returns early)"
    Write-Host "   - CurrentBars[0] < BarsRequiredToTrade (50 bars needed)"
    Write-Host "   - CurrentBars[1] < BarsRequiredToTrade (5-min secondary needs 50 bars)"
    Write-Host "   - CanEnterTrade returns false (ATR=0, time fence, daily loss, etc.)"
    Write-Host "   - Print() goes to SA output window, not main Output tab"
} else {
    Write-Host "✅ DIAG logs found: $($diag.Count) entries"
    $diag | Select-Object -First 5
}

# 5. Check if strategy was actually instantiated (look for Configure/Initialize)
$configLogs = $logs.logs | Where-Object { $_ -match "Configure|Initialize|SetDefaults" }
if ($configLogs.Count -eq 0) {
    Write-Host "❌ NO LIFECYCLE LOGS: strategy ConfigureStrategy/InitializeStrategy never called."
    Write-Host "   The SA may be running the base class, not your concrete bot."
}

# 6. Check SA for error messages
$saLogs = $logs.logs | Where-Object { $_ -match "error|Error|exception|Exception" }
if ($saLogs.Count -gt 0) {
    Write-Host "❌ ERRORS in logs:"
    $saLogs | Select-Object -First 5
}
```

## Common Blockers (ranked by frequency)

| # | Blocker | Symptom | Fix |
|---|---|---|---|
| 1 | **ATR gate** (`GetCurrentATR() = 0`) | 0 trades, no DIAG logs, AtrPeriod=14 in summary | `AtrPeriod = 1` in `SetStrategyDefaults()` |
| 2 | **Wrong strategy loaded** | Summary shows `RiskManagerBase Backtest` | `Name = "BotName"` after `base.SetStrategyDefaults()` |
| 3 | **BarsRequiredToTrade not met** | 0 trades in short backtest | Use ≥3 days of data (50 bars × 1 min = 50 min minimum) |
| 4 | **Time fence blocks** | Entries outside EarliestEntry/LatestEntry | Check `EarliestEntry`/`LatestEntry` values in summary |
| 5 | **Calendar filter skips all days** | 0 trades on specific DOW/month | Check `SkipMondayPlay2` etc. in params |
| 6 | **Range-size filter skips all days** | 0 trades when IB range too big/small | Check `MaxRangePct`/`MinRangePct` vs actual IB ranges |
| 7 | **Print() invisible in SA** | No DIAG logs even when strategy runs | Print goes to SA output window, not main Output tab |
| 8 | **Double-entry suppression** | `CheckForSignal` returns non-zero but base `EnterTrade` conflicts | Return 0 from `CheckForSignal` after `CheckForEntry` enters |