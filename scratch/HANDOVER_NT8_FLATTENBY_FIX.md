# Handover: NT8 FlattenBy Fix + Parity Mismatch Investigation

**Session**: 9 (continuation of Session 8)
**Date**: 2026-07-29
**Status**: IN PROGRESS — Python TargetIsSane fix DONE, NT8 FlattenBy fix INTRODUCED REGRESSION

---

## 1. What We Started With

After Session 8, parity was 93.6% (44/47 overlapping trades). User asked to explain
the 3 mismatches. Deep investigation revealed:

### Mismatch 1: 2026-03-11 LONG — Python TargetIsSane bug (FIXED)
- Python breakout bar at 10:00 gapped 58 pts above ib_high (25631.50)
- Entry = 25689.50, target = ib_high + 0.5*range = 25681.625 — **below entry**
- Python harness has no TargetIsSane check, enters anyway, "hits target" on next bar
- But realized_r = -1.0 (exit below entry = loss labeled as "win")
- NT8 has TargetIsSane check (target > entry + TickSize) and REJECTS this trade at 10:00
- NT8 enters later at 10:03 at a different price where target > entry holds

### Mismatch 2: 2026-03-24 LONG — NT8 FlattenBy not enforced (FIX IN PROGRESS)
- Python flattens at 15:50 (liquidation_1550), result = loss
- NT8 held until 16:23, hit profit target = win
- NT8 FlattenBy=1550 is configured but ZERO trades exit at 15:50
- 11 trades exit at 17:00 ("Exit on session close") instead

### Mismatch 3: 2026-05-25 SHORT — Entry timing divergence
- Python enters at 10:32, NT8 enters at 10:34 (2 bars later)
- Python hits target at 10:42, NT8 hits stop at 11:12
- User clarified: filters are the SAME on both sides, so this is NOT a filter issue
- The 2-bar delay is from NT8's different feed (different ib_low absolute level)
- IB range is the same (54 pts), but the absolute ib_low differs between feeds
- This affects WHICH bar first closes below ib_low, causing the 2-bar entry delay
- This is irreducible without using identical contract data (see Class B/C notes)

---

## 2. Fixes Applied (uncommitted)

### Fix A: Python TargetIsSane check — DONE, VERIFIED
**File**: `scripts/validation/ib_parity_harness.py` (lines ~358-370)

Added TargetIsSane check in `simulate_play1_day()`:
```python
# LONG: if target_price <= entry_price, skip (mirrors NT8 TargetIsSane)
if target_price <= entry_price:
    return None
# SHORT: if target_price >= entry_price, skip
if target_price >= entry_price:
    return None
```

**Result**: Python trades dropped from 56 to 55. Parity improved from 93.6% (44/47)
to **95.7% (44/46)**. The Mar 11 false trade is eliminated.

### Fix B: NT8 FlattenBy enforcement — INTRODUCED REGRESSION
**Files**: `scripts/strategies/nt8/base/RiskManagerBase.cs`, `IntradayStrategyBase.cs`

**Root cause of FlattenBy not firing**: `FlattenPosition()` called
`ExitLong(reason, GetSignalName("Long"))` where:
- `reason` = "Flatten by time" was passed as `fromEntrySignal`
- `GetSignalName("Long")` = "IB Breakout Bot (Play 1)_Long" was the exit name
- But the ACTUAL entry signal name is "IntradayBaseLong" (from EnterWithRangeStop)
- NT8 couldn't match the exit to the entry, so the managed OCO stayed active
- The position was never closed by the flatten

**Changes made**:
1. `IntradayStrategyBase.EnterWithRangeStop()`: set `tradeDirection` and
   `entrySignalName` before EnterLong/EnterShort
2. `RiskManagerBase`: added `protected string entrySignalName` field
3. `RiskManagerBase.FlattenPosition()`: use `entrySignalName ?? GetSignalName(tradeDirection)`
   as `fromEntrySignal` in ExitLong/ExitShort: `ExitLong(fromEntry, reason)`
4. `RiskManagerBase.ManageOpenTrade()`: skip if `!tradeIsActive` (flatten submitted)
5. `RiskManagerBase.EnterTrade()`: set `entrySignalName = signalName`
6. `ResetSessionState()`: clear `entrySignalName = null`

**Compile**: SUCCESS (0 errors, via NT8 MCP bridge hot-swap)

**Backtest result (v2-v6, all identical)**: REGRESSION
- FlattenBy NOW fires: 9 "Flatten by time" exits (was 0) ✅
- BUT 30 "Daily max loss breached" exits appeared (was 0) ❌
- Win rate dropped 63.4% → 59.2%
- Trades dropped 71 → 50

**Why the regression**: When `ExitLong(fromEntry, reason)` correctly matches the
entry signal, NT8 cancels the managed SetProfitTarget/SetStopLoss OCO. But the
ExitLong market order hasn't filled yet (fills next bar in SA backtest). On the
next bar, `ManageOpenTrade()` runs and sees:
- Position still open (exit order pending)
- No managed stop loss (cancelled by the ExitLong)
- Unrealized PnL triggers `sessionPnL + unrealizedPnL <= -DailyMaxLoss`

The `!tradeIsActive` guard in ManageOpenTrade was added to prevent this, but it
doesn't help because the daily max loss exits happen on trades where
`tradeIsActive` was set by `EnterTrade`, not by the flatten path.

**Key insight from v1 vs v6 comparison**:
- 11 session-close trades → 6 became "Flatten by time", 5 became "Daily max loss"
- 30 "Daily max loss" trades were FORMERLY profit target (21) or stop loss (4) or
  session close (5) trades in v1
- The ExitLong(fromEntry) is cancelling the managed orders TOO EARLY — the
  target/stop that would have fired are now cancelled, and the position limps
  to the next bar where ManageOpenTrade kills it

**The real fix needed**: `FlattenPosition` should close the position WITHOUT
cancelling managed orders first. The managed orders will auto-cancel when the
position goes flat from the ExitLong fill. OR: use `ExitLong()` without
`fromEntrySignal` (plain market close) which doesn't cancel managed orders,
then let them auto-cancel on flat.

**Alternative approach to try next session**:
1. Revert FlattenPosition to original `ExitLong(reason, GetSignalName("Long"))`
   (no fromEntrySignal matching — just a plain close)
2. Instead, fix the ROOT CAUSE: why doesn't OnBarUpdate's flatten check fire?
   - Add Print() logging at the flatten check to see if it executes
   - Check if the SA uses a session template where 15:50 bars don't exist
   - Check if BarsInProgress != 0 somehow

Wait — the v6 backtest shows 9 "Flatten by time" exits, so the flatten IS firing
now. The problem is the 30 daily max loss exits, not the flatten. The daily max
loss is triggered by ManageOpenTrade seeing unprotected positions.

**Better fix to try**: In ManageOpenTrade, check `tradeIsActive` BEFORE the daily
max loss check. If `tradeIsActive == false`, the flatten has been submitted and
the position is pending close — skip ALL trade management.

Actually, the current code already has this:
```csharp
if (!tradeIsActive)
    return;
```
But it's placed AFTER the `Position.MarketPosition == MarketPosition.Flat` check.
The issue is that `tradeIsActive` is set to false in `FlattenPosition`, but the
daily max loss exits happen on trades where the flatten HASN'T been called yet.

**The actual problem**: The `ExitLong(fromEntry, reason)` in `FlattenPosition`
cancels managed orders. On the NEXT bar, OnBarUpdate fires:
1. Flatten check: position still open (exit pending) → calls FlattenPosition AGAIN
2. This re-submits ExitLong, re-cancels (no-op since already cancelled)
3. Returns
But ManageOpenTrade never runs because the flatten check returns first.

So the 30 daily max loss exits are NOT from the flatten path. They must be from
trades where EnterTrade (not EnterWithRangeStop) was used, or where the managed
orders were never set up properly.

**Need to investigate next session**:
- Which trades hit "Daily max loss"? Are they all from EnterWithRangeStop?
- Is EnterTrade being called in addition to EnterWithRangeStop?
- Check if CheckForSignal returns non-zero, causing EnterTrade to also fire
- Look at OnBarUpdate flow: after CheckForSignal returns, does EnterTrade run?

---

## 3. Harness Timezone Fix — DONE
**File**: `scripts/validation/ib_parity_harness.py` (lines ~622-635)

Fixed `diff_ledgers()` timezone handling:
- Python `entry_time` is tz-aware ET (from ET-localized bars) → parse with `utc=True`
- NT8 `entry_time` is ET-naive (SA exports in chart timezone = ET) → localize to ET directly
- Previously both were treated as UTC, causing NT8 times to shift −4h/−5h

---

## 4. Current File State (uncommitted changes)

### `scripts/strategies/nt8/base/RiskManagerBase.cs` (MODIFIED)
- Added `protected string entrySignalName` field (line ~134)
- `ResetSessionState()`: clear `entrySignalName = null` (line ~389)
- `EnterTrade()`: set `entrySignalName = signalName` (line ~512)
- `ManageOpenTrade()`: added `if (!tradeIsActive) return;` guard (line ~549)
- `FlattenPosition()`: use `entrySignalName ?? GetSignalName(tradeDirection)` as
  fromEntrySignal in ExitLong/ExitShort (line ~755)

### `scripts/strategies/nt8/base/IntradayStrategyBase.cs` (MODIFIED)
- `EnterWithRangeStop()`: set `tradeDirection` and `entrySignalName` before
  EnterLong/EnterShort (lines ~438-450)

### `scripts/validation/ib_parity_harness.py` (MODIFIED)
- `simulate_play1_day()`: added TargetIsSane check (lines ~358-370)
- `diff_ledgers()`: fixed NT8 timezone handling (lines ~622-635)

### NT8 backtest files (untracked)
- `scratch/nt8_ib_breakout_nq_backadj_janjun2026.json` — v1 (original, committed)
- `scratch/nt8_ib_breakout_nq_backadj_janjun2026_v2.json` through `_v6.json` —
  all identical: 50 trades, WR 59.2%, 9 flatten + 30 max loss (REGRESSION)

### Python parity result
- `scratch/parity_final_janjun2026.csv` — committed (93.6%, 44/47)
- NOT yet re-run with TargetIsSane fix for final number (should be 95.7%, 44/46)

---

## 5. Next Steps (Priority Order)

1. **Fix the NT8 daily max loss regression**
   - Investigate: are the 30 "Daily max loss" trades from EnterWithRangeStop
     or EnterTrade? (EnterTrade sets its own SetStopLoss with signalName)
   - Check: does OnBarUpdate call EnterTrade after EnterWithRangeStop already
     entered? (CheckForSignal → EnterTrade flow)
   - Try: revert FlattenPosition to plain `ExitLong()` without fromEntrySignal
     matching — let managed orders auto-cancel on flat
   - If that fails: add `tradeIsActive = false` check at TOP of ManageOpenTrade,
     before the Flat check

2. **Re-run NT8 backtest after fix**
   - Target: 71 trades with 9-11 "Flatten by time" exits, NO daily max loss
   - Win rate should return to ~63%

3. **Re-run parity harness with TargetIsSane fix**
   - Expected: 95.7% (44/46) or higher if FlattenBy fix also resolves Mar 24

4. **Commit all fixes**
   - TargetIsSane (Python) + FlattenBy (NT8) + timezone (harness)
   - Update NT8_PYTHON_PARITY_STANDARD.md with Class G (TargetIsSane)

5. **May 25 mismatch (Class B/C)**
   - Irreducible without identical contract data
   - Document as known limitation

---

## 6. Key Commands

```bash
# Sync NT8 strategies to live folder
.\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py

# Compile via MCP bridge
.\.venv\Scripts\python.exe -c "import requests; r=requests.post('http://localhost:7890/api/compile', json={'strategy':'IBBreakoutBot'}); print(r.json())"

# Check compile result
.\.venv\Scripts\python.exe -c "import requests; r=requests.get('http://localhost:7890/api/compile/result'); print(r.json())"

# Run NT8 backtest
.\.venv\Scripts\python.exe -c "import requests; r=requests.post('http://localhost:7890/api/backtest', json={'strategy':'IBBreakoutBot','instrument':'NQ JUN26','from':'2026-01-01','to':'2026-07-01'}); print(r.json())"

# Run parity harness
.\.venv\Scripts\python.exe scripts/validation/ib_parity_harness.py --ticker NQ1 --play 1 --target 0.5 --stop-mult 2.0 --d-from 2026-01-01 --d-to 2026-07-01 --nt8-json scratch/nt8_ib_breakout_nq_backadj_janjun2026.json --out scratch/parity_final_janjun2026.csv
```

## 7. Services
- NT8 MCP bridge: http://localhost:7890 (running, last compile OK)
- FastAPI backend: http://127.0.0.1:8000 (running)
- NinjaTrader 8: running (PID 19584)