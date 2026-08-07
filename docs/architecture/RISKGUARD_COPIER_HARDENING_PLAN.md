# RiskGuard + TradeCopier Hardening Plan

**Status**: **P0 complete** (2026-08-06, branch `harden/riskguard-copier-p0`, suite 356/0).
P1–P3 not started. Live progress: [RISKGUARD_HARDENING_HANDOVER.md](RISKGUARD_HARDENING_HANDOVER.md).
**Created**: 2026-08-06

## Defect inventory — the count of record

**38 defects.** Numbered once, never renumbered, never reused.

| Band | IDs | Count | Status |
|---|---|---|---|
| P0 — naked-risk / wrong-size | `P0-1` … `P0-9` | 9 | ✅ all closed |
| P1 — real bugs, not yet live-risk | `P1-10` … `P1-23`, `P1-35`, `P1-36`, `P1-37` | 17 | 6 closed (`P1-10`, `P1-11`, `P1-15`, `P1-20`, `P1-35`, `P1-37`) |
| P2 — structural | `P2-24` … `P2-29`, `P2-38` | 7 | open (`P2-28` closed; `P2-27` half-done) |
| P3 — enhancements | `P3-30` … `P3-34` | 5 | open |

> **ID collision, resolved 2026-08-07 — read this if you are following a git commit or an old
> doc.** `P1-30` and `P1-31` were appended during the P0 work and collided with the pre-existing
> `P3-30` (reconciler) and `P3-31` (expected-position ledger) — four distinct defects sharing two
> numbers. The two newcomers were renumbered; `P3-30`/`P3-31` are unchanged.
>
> | Old | New | Defect |
> |---|---|---|
> | `P1-30` | **`P1-35`** | FSM teardown cancels the orphan auto-stop under `_stateLock` |
> | `P1-31` | **`P1-36`** | Coverage tracks a single stop; two partial stops read as under-covered |
>
> Commits from the P0 phase (`5fd26995` … `29b6c66a`) still say `P1-30`/`P1-31`. Map them here.
> **When adding a defect, take the next free number — do not extend a band in place.**
**Scope**: `scripts/ninjatrader/addons/{RiskGuardAddOn,TradeCopierEngine,TradeCopierWindow,PropFirmProtectionSuite,DynamicAtmManager}.cs`
**Comparison baseline**: `github.com/mkalhitti-cloud/universal-or-strategy` (V12 Photon Kernel — SIMA fleet dispatch, REAPER defense, Symmetry Guard)
**Related**: [RiskGuardAddOn.md](RiskGuardAddOn.md) (current design doc — contains drift, see §6), [NT8_FILE_ORGANIZATION.md](NT8_FILE_ORGANIZATION.md)

---

## 0. Why this review, and what the baseline gives us

Our addons and the V12 strategy solve overlapping problems — multi-account replication and
automated protection of unprotected positions — but from opposite directions:

| Concern | Our addons | V12 (`universal-or-strategy`) |
|---|---|---|
| Replication trigger | `Account.ExecutionUpdate` on the leader, fan-out to followers | Strategy-internal dispatch (`ExecuteSmartDispatchEntry`) before the master order is even submitted |
| Follower risk anchor | none — followers get scaled market orders | `AnchorSnapshot` pinned to the **master's actual weighted fill**, plus `SlippageCushionPoints` |
| Follower brackets | none (`EnableFollowerAtm` is dead config) | "Path B" fixed brackets submitted with the entry |
| Naked-position defense | per-position FSM + one-shot grace timer | FSM **plus** an independent REAPER audit loop that re-derives truth from the broker every cycle |
| Concurrency | one global `lock (_stateLock)`, work marshaled to the WPF dispatcher | zero `lock()`; actor/`Enqueue` model, background audit thread marshals only order calls |
| Submit safety | submit, then record state | reserve/record state **under lock before** submit, roll back on null/reject |
| Desync repair | `ReconcileFollowerPosition` exists but is never called | `REAPER.Repair` + `REAPER.NakedStop` with in-flight dedupe dictionaries and grace windows |

The single most important structural idea to borrow is **REAPER's separation of concerns**:
the FSM is an optimistic fast path, and a *separate, independent auditor* re-derives ground
truth from the broker and repairs whatever the fast path missed. Our FSM has no such
backstop — `FsmWatchdog()` (RiskGuardAddOn.cs:1763) only writes a log line. Every P0 below
is a case where the fast path can lose the position and nothing recovers it.

The second idea worth borrowing is the **reserve-before-submit / rollback-on-failure**
discipline (V12's `A1-1/A2-1` pattern), which we currently invert.

Conversely, we have things V12 lacks and should keep: shadow mode with a preflight gate
(`RunPreflight`, `MinShadowSessions`), friction-gated lockout override, JSONL intervention
log + heartbeat file, and `SeedFsmsForExistingPositions` — a genuinely good state
re-derivation routine that is currently called from only one place.

---

## 1. P0 — Naked-risk and wrong-size defects (fix before any live use)

### P0-1. FSM returning to `Unprotected` never re-arms the grace timer → permanent naked position
**Where**: `RiskGuardAddOn.cs:1667-1677` (`UpdateFsmOnOrder`, terminal-stop branch), `1763-1776` (`FsmWatchdog`)
**What happens**: When the recognised protective stop goes terminal (cancelled by the user,
rejected by the broker, or filled on a partial) while the position is still open, the FSM is
set back to `Unprotected` — but no new `GraceTimer` is armed. Grace expiry moved off the sweep
onto per-FSM one-shot timers (`UpdateFsmOnPosition:1591-1606`), and the timer was disposed when
the FSM first left `Unprotected` (`1700-1704`). `EvaluateGraceExpiry` is called from exactly one
place, `OnGraceExpired` (`1633`), so nothing will ever fire again for that position.
`FsmWatchdog` notices and logs `FSM_WATCHDOG` every 5 s, forever, without acting.
**Impact**: Cancel your stop manually (or have a broker reject one) and the position runs
unprotected for the rest of the session with the guard reporting the condition in the log only.
**Fix**:
1. Extract timer arming into `ArmGraceTimer(PositionGuardFsm fsm, Account acct, string instrument)`
   and call it from *every* transition into `Unprotected`, not just FSM creation.
2. Promote `FsmWatchdog` from log-only to remediation: if a FSM has been `Unprotected` past
   `GraceDeadline + StopGuard.WatchdogEscalateSeconds`, re-derive state via the existing
   `SeedFsmsForExistingPositions` logic (refactor it into
   `ReDeriveFsmFromBroker(account, instrument)`), then call `OnGraceExpired`.
3. Borrow REAPER's `_repairInFlight` / `_nakedPositionFirstSeen` pattern: a
   `ConcurrentDictionary<string, DateTime>` keyed by FSM key so escalation fires once per
   naked episode and not once per sweep.
**Test**: position open + stop reaches `Working` → cancel the stop → assert a new grace timer is
armed and `MISSING_STOP_ATTACH` (or `_FLATTEN`) is emitted exactly once.

### P0-2. Auto-stop state is recorded *after* submission and unconditionally
**Where**: `RiskGuardAddOn.cs:2595-2611`
**What happens**:
```csharp
if (stopOrder != null) {
    account.Submit(new[] { stopOrder });
    lock (_stateLock) { ... fsm.State = GuardFsmState.ProtectedPending; }
}
```
Three defects in six lines:
- The `OrderUpdate` for the new stop can arrive **before** the lock is taken, so a stop that
  already reached `Working` (state `Protected`) is regressed to `ProtectedPending`; worse, a stop
  that was **rejected** (state correctly reset to `Unprotected`) is overwritten to
  `ProtectedPending` — and per P0-1 no timer is armed, so the position is naked permanently.
- `stopOrder == null` is a silent no-op: no log, no retry, no flatten fallback.
- The submit itself is not wrapped in try/catch here (the outer `ProcessAction` catches, but the
  FSM is then left in whatever state the pre-submit code left it).
**Fix**: adopt V12's ordering — set `fsm.AutoStopOrder`/`State = ProtectedPending` **under lock
before** `Submit`, then roll back to `Unprotected` + re-arm grace if `CreateOrder` returns null or
`Submit` throws. Never write FSM state from the post-submit path; let `UpdateFsmOnOrder` own it
from there. Add an explicit `AUTO_STOP_SUBMIT_FAILED` event and escalate to
`MISSING_STOP_FLATTEN` after `StopGuard.MaxAutoStopAttempts` (new config, default 2).

### P0-3. Auto-stop quantity is a stale snapshot — can flip the position
**Where**: `RiskGuardAddOn.cs:2508-2597` (uses `action.Quantity`), `ValidateInvariant:2436-2440`
**What happens**: `ExecuteAction` re-reads the live `position` (line 2511) but then sizes the stop
from `action.Quantity`, captured when the action was emitted. `ValidateInvariant` for
`PlaceStopOrder` only checks `InstrumentObj != null && Quantity > 0` — it does not verify that a
position still exists, its side, or its size.
**Impact**: position scaled down between emission and execution → the auto-stop is **larger than
the position**, and when it triggers it opens a **new position in the opposite direction**. Scaled
up → the stop under-covers and part of the position is silently naked.
**Fix**: size from `position.Quantity` at submit time; assert side matches `orderAction`; reject
the action if the position is flat or the side flipped. Tighten `ValidateInvariant` to look up the
live position and confirm the action is genuinely risk-reducing (this is what the "ActionArbiter"
claims to do — see §6 doc drift).

### P0-4. Scale-in keeps `Protected` without checking stop coverage
**Where**: `RiskGuardAddOn.cs:1555-1563`
**What happens**: A same-side quantity update updates `PositionQuantity` in place and explicitly
preserves `Protected`/`ProtectedPending`. Nothing compares `RecognizedStopOrder.Quantity` to
`PositionQuantity`, so 1 → 5 contracts with a 1-lot stop still reports fully protected.
**Fix**: add `GuardFsmState.PartiallyProtected` (or a `CoveredQuantity` field, which is less
invasive). On a same-side increase, if covered < position, re-arm the grace timer for the
uncovered delta and emit `MISSING_STOP_ATTACH` sized to the delta. REAPER does the equivalent by
checking stop *quantity* coverage, not mere existence.

### P0-5. Copier exit sizing is not position-mirroring → follower reverses
**Where**: `TradeCopierEngine.cs:401` (`return isExit ? leaderQty : rel.FixedLotSize`),
`427` (`if (isExit) return rawCopyQty;`), consumed at `OnExecution:685-737`
**What happens**: exits are sized from the leader's execution quantity and returned
**unclamped**, never compared to the follower's actual position. In `FixedLot` mode the exit uses
the **leader's raw quantity** and ignores `FixedLotSize` entirely.
**Concrete failure**: `FixedLotSize = 1`. Leader buys 5, follower buys 1. Leader sells 5 →
follower submits `Sell 5` while holding 1 → **follower ends up short 4 contracts** on a market
order, with no stop (P0-9) and no reconciliation (P2-24).
The same happens after any clamp by `MaxPositionSize`, any failed entry copy, or any
micro/mini rounding difference.
**Fix**: route every copy decision through the already-written but **never called**
`CalculateSafeFollowerDelta` (`TradeCopierEngine.cs:165`) — it clamps a reducing delta to
`Math.Abs(currentFollowerQty)` and blocks opposite-side market opens, which is exactly the guard
needed. Target-position mirroring (compute the follower's *desired* position from the leader's
*resulting* position, then submit the delta) is strictly safer than replaying execution
quantities; adopt it.

### P0-6. Micro→Mini conversion floors to 1 contract → 10× notional
**Where**: `TradeCopierEngine.cs:426` — `Math.Max(1, Math.Round(leaderQty * absRatio * symbolMultiplier))`
**What happens**: with `symbolMultiplier = 0.1` (MNQ→NQ), a leader trading 5 MNQ yields
`Math.Max(1, round(0.5))` = **1 NQ = 10 MNQ equivalent**, i.e. 2× intended notional; a leader
trading 1 MNQ yields 1 NQ = **10× intended notional**. Any `QuantityRatio < 1` hits the same floor.
**Fix**: floor to 0 and skip the copy (log `SUB_MINIMUM_SKIPPED`) instead of `Math.Max(1, …)`.
Optionally carry a per-(relationship, instrument) fractional residue accumulator so repeated
sub-1 copies eventually emit one contract. Add a hard notional-parity assertion in tests:
`followerQty × followerPointValue ≈ leaderQty × leaderPointValue × ratio`.

### P0-7. Peak-giveback rule compares incompatible quantities → fires on every profitable flat account
**Where**: `RiskGuardAddOn.cs:1154`, predicate at `PropFirmProtectionSuite.cs:104-111`
**What happens**: `EvaluatePeakEquityGiveback(peakOpenGain, currentUnrealized)` is called as
`EvaluatePeakEquityGiveback(stateModel.PeakEquity, stateModel.UnrealizedPnL, …)`.
`PeakEquity` is the peak of **Realized + Unrealized** (`1038-1040`), the second argument is
**Unrealized only**. An account that banked +$2,000 and is now flat gives
`giveback = 2000 - 0 = 2000`, `givebackPct = 1.0 ≥ 0.30` → `PEAK_GIVEBACK_BREACH` →
`FlattenPosition` emitted on **every** `AccountItemUpdate`.
**Impact**: harmless while flat (nothing to flatten), then it instantly flattens the next
position taken after any profitable session. Note this branch deliberately does *not* set
`IsLockedOut`, so it never latches and never stops.
**Fix**: define one basis and use it consistently. Recommended: track `PeakOpenGain` (peak of
unrealized only, reset on flat) and compare against current unrealized; or track
`PeakTotalPnL` and compare against current total. Add a `position != flat` precondition and a
latch so the rule fires once per episode.

### P0-8. The copier is the only order path that bypasses the RiskGuard lockout
**Where**: `TradeCopierEngine.OnExecution:645-737` vs `McpBridgeAddOn.cs:2252`, `2315`, `3966`
**What happens**: every order path in `McpBridgeAddOn` checks
`RiskGuardAddOn.Instance.IsAccountLocked(...)` before submitting. The copier does not. A follower
that RiskGuard has locked out for a daily-loss breach will still receive fresh copied entries;
RiskGuard's lockout sweep then fights the copier — cancel/flatten every 5 s against new entries
arriving on every leader fill.
**Fix**: gate the per-relationship loop on the public API that already exists for this —
`RiskGuardAddOn.Instance.CanTrade(followerName, instrument, "TradeCopier")` (`RiskGuardAddOn.cs:108`)
— and auto-quarantine the relationship (P2-24) when the follower is locked. Also skip copying
*from* a locked leader.

### P0-9. Followers are left naked — no bracket replication
**Where**: `TradeCopierEngine.OnExecution:721-738` (always `OrderType.Market`, no protective legs);
`EnableFollowerAtm` / `FollowerAtmStrategyName` are carried between DTOs (`:91`, `:36-37`) and
**never read**
**What happens**: followers receive bare market orders. Their only protection is RiskGuard's
`StopAttachSeconds` grace → `RiskGuardAutoStop` at a fixed tick offset from *average price*
(`RiskGuardAddOn.cs:2545`), which bears no relation to the leader's actual stop. If RiskGuard is
disarmed, in shadow mode, or the follower is in `ExcludedAccounts`, there is no stop at all.
**Fix** (in preference order):
1. Replicate the leader's protective legs: on leader stop/target `OrderUpdate`, mirror them to
   followers scaled by the same quantity function, anchored to the **follower's own fill** (V12
   Symmetry Guard pattern) rather than the leader's price.
2. Failing that, implement `EnableFollowerAtm` by submitting a fixed bracket at copy time
   (V12 "Path B") using a stop distance derived from the leader's stop, with
   `SlippageCushionPoints`-style padding so follower dollar risk ≤ the configured cap.
3. Minimum bar: refuse to copy to a follower unless RiskGuard is armed, live, and subscribed to
   that account — fail closed, log `COPY_BLOCKED_NO_GUARD`.

---

## 2. P1 — Concurrency and invariant violations

### P1-10. The safety sweep holds `_stateLock` across broker calls — CLOSED 2026-08-07
**Where**: `RiskGuardAddOn.cs:1336-1446` — the `lock (_stateLock)` block contains
`account.Cancel` (1413), `account.Flatten` (1423), `account.Submit` (1429) and
`ProcessAction(...)` (1439), which itself calls `ExecuteAction` → `Flatten`/`Cancel`/`Submit`.
**Why it matters**: [RiskGuardAddOn.md](RiskGuardAddOn.md) §5 and §6.7 both state the invariant
"deadlocks are avoided by yielding the lock before calling NinjaTrader's `Flatten` or `Cancel`".
The event paths honour it correctly (`ExecutePositionUpdateDetails:905-913` collects actions under
lock and processes them after release). The sweep does not. Because the sweep runs on the WPF
dispatcher via `InvokeAsync` (`1320`), any NT8 internal path that blocks on a background thread
which in turn needs `_stateLock` deadlocks the UI thread — and with it the guard.
**Fix**: restructure the sweep to the same collect-then-execute shape as the event handlers.
Nothing inside `lock` may call into `Account`.

> **How the lock-scope invariant is enforced now (2026-08-07).** The stub account reports every
> `Cancel`/`Flatten`/`CreateOrder`/`Submit` to `Account.BrokerCallObserver`, and the addon exposes
> `TestIsStateLockHeld()` (`Monitor.IsEntered`). `TestP1_10_...` and `TestP1_35_...` therefore assert
> the invariant directly instead of relying on someone spotting a broker call three frames deep
> inside a lock block. Any new violation anywhere on those paths fails the suite.
>
> `DrainPendingCancels()` **throws in the TESTING build if called with `_stateLock` held.** The
> tempting wrong fix here is a nested `lock (_stateLock)` around the cancel — it is re-entrant, so
> it changes nothing and merely hides the violation. The guard makes that mistake loud.

### P1-11. Lockout sweep cancels protective stops and reducing orders — CLOSED 2026-08-07
**Where**: `RiskGuardAddOn.cs:1410-1414`
```csharp
var toCancel = account.Orders.Where(o => o.OrderState != OrderState.Filled
                                      && o.OrderState != OrderState.Cancelled).ToList();
account.Cancel(toCancel);
```
This cancels **everything non-terminal** — including the protective stop covering the position it
is about to flatten, and including position-reducing orders that §6.10 of the design doc
explicitly promises to preserve (`IsPositionReducingOrder` is honoured in `OnOrderUpdate` but not
here). If the subsequent `Flatten` fails (the code catches and falls back to a market order,
which can also fail), the account is left with a position and **no stop**.
**Fix**: order of operations — (a) cancel only *entry / risk-increasing* working orders, (b)
flatten, (c) cancel the remainder after confirming flat. Reuse `RiskGuardOrderUtils.IsPositionReducingOrder`
and `IsProtectiveSide`. Add an attempt counter with escalation to a loud alert after N cycles
instead of silent infinite retry (REAPER's `_reaperFlattenInFlight` + grace pattern).

### P1-12. Blocking file I/O under the global lock
**Where**: heartbeat `File.WriteAllText` (`1342`), log `File.AppendAllLines` (`1351`),
`SavePersistedState()` (`1395`) — all inside `lock (_stateLock)`; plus
`SavePersistedState()` called **synchronously on every position change** at `865`.
**Why it matters**: `_stateLock` is the same lock every NT8 event handler needs. A slow disk
stalls order-event processing. The `_stateDirty` batching mechanism already exists and is used by
the sweep — line 865 bypasses it.
**Fix**: replace line 865 with `_stateDirty = true`. Move all file writes outside the lock;
consider a dedicated writer thread draining `_logQueue`.

### P1-13. Guard evaluation runs on the WPF dispatcher
**Where**: `OnSafetySweep:1317-1323`, `UpdateFsmOnPosition:1599-1604`, `SeedFsms…:501-507`
**Why it matters**: safety-critical latency is coupled to UI responsiveness. V12 does the
inverse — REAPER audits on a background thread and marshals *only* the order-submitting calls to
the strategy thread via `TriggerCustomEvent`.
**Fix**: evaluate on the timer's own thread; marshal only `Account.Flatten/Cancel/Submit` to the
dispatcher. This also removes the "no dispatcher → silently return" failure mode at `1318`,
where the entire sweep is skipped if `Application.Current` is null.

### P1-14. `_pendingStops` is single-slot, unbounded in lifetime, and side-blind
**Where**: `UpdateFsmOnOrder:1651-1658`, consumed at `UpdateFsmOnPosition:1577-1587`
- `_pendingStops[key] = order` keeps **one** order per (account, instrument) — a bracket with
  multiple stop legs, or a second stop arriving first, overwrites the first.
- Entries are only removed on consumption or on flat. A buffered stop for a position that never
  materialises (entry rejected) leaks and can be consumed by a *later, unrelated* position on the
  same instrument.
- The comment admits the side is unknown at buffer time, so a **stop-market entry order** (a
  breakout entry, exactly what V12's OR mode submits) is buffered as a candidate protective stop.
**Fix**: `Dictionary<string, List<Order>>` with a TTL (e.g. `StopAttachSeconds × 2`), swept in the
watchdog; classify by side on consumption only, and require `order.Quantity <= positionQuantity`.

### P1-15. Re-arming does not seed FSMs for open positions — CLOSED 2026-08-07
**Where**: `ToggleArmed:2231-2249`; `SeedFsmsForExistingPositions` is only called from
`SubscribeToAccount`
**What happens**: `UpdateFsmOnPosition`/`UpdateFsmOnOrder` return early when `!_isArmed`
(`1547`, `1645`). Disarm → open a position → re-arm, and there is no FSM, no grace timer, and no
protection until the position changes side.
**Fix**: call `SeedFsmsForExistingPositions` for every subscribed account inside `ToggleArmed`
when transitioning to armed. Same on `SaveAndReloadConfig`/`ReloadConfig` if
`ExcludedAccounts` shrank.

### P1-35. FSM teardown cancels the orphan auto-stop while the caller holds `_stateLock` — CLOSED 2026-08-07
*(found during T1 implementation, 2026-08-06 — a P1-10 site this review originally missed)*
**Where**: `RiskGuardAddOn.cs:1620` inside `UpdateFsmOnPosition`'s nonflat→flat branch:
`try { account.Cancel(new[] { fsm.AutoStopOrder }); }`
**What happens**: `UpdateFsmOnPosition` is only ever called with `_stateLock` held — from
`ExecutePositionUpdateDetails:880` and from `TestFsmOnPosition`. So the orphan-auto-stop
cancellation is a broker call under the global lock, exactly the invariant §5/§6.7 of the design
doc claims is never violated. P1-10 catalogued the sweep as the only offender; this is a second,
independent site on the hot event path.
**Fix**: fold into P1-10's collect-then-execute restructuring — queue the orphan order on a
pending-cancel list and drain it in `ExecutePositionUpdateDetails` after the lock is released,
alongside the existing `ProcessAction` loop. Do not add a separate drain mechanism.

### P1-36. Coverage tracking follows a single stop order, so two partial stops read as under-covered
*(found during T1 review, 2026-08-06)*
**Where**: `PositionGuardFsm.RecognizedStopOrder` / the new `CoveredQuantity` (T1)
**What happens**: the FSM tracks exactly one protective stop. A trader covering a 6-lot position
with two working 3-lot stops leaves `CoveredQuantity = 3`, so the under-coverage rule introduced by
T1 fires and attaches a 3-lot auto-stop — total protective quantity 9 on a 6-lot position, which
flips the position when the stops trigger. T1 deliberately scopes this out (it clamps the emitted
action to the uncovered delta computed from one stop), so the defect is narrowed but not closed.
**Fix**: aggregate coverage across all non-terminal protective-side stop orders for the
`(account, instrument)` pair rather than tracking a single `Order` reference — i.e. replace
`RecognizedStopOrder` with a small list, and compute `CoveredQuantity` as the sum. This is the
same computation the P3-30 reconciler needs, so build it once and share it.

### P1-37. The `MinShadowSessions` arming gate counts addon restarts, not sessions — CLOSED 2026-08-07
*(found during the Phase A shadow deployment, 2026-08-07 — observed live, then confirmed in code)*
**Where**: `RiskGuardAddOn.cs:1510` (the increment) against `RiskGuardAddOn.cs:211` (the date
marker) and `RiskGuardAddOn.cs:609` (the rehydrate).
**What happens**: the counter `_shadowSessionsCompleted` **is** persisted and rehydrated across
restarts, but the date marker that debounces it, `_lastShadowSessionDate`, is **not** — it is a
plain field initialised to `DateTime.MinValue.Date` on every construction, and there is no
`LastShadowSessionDate` key in `PersistedStateData`. So the guard `_lastShadowSessionDate !=
currentSessionDate` is true after *every* addon reload, and the counter increments again on the
same calendar day.

This is not theoretical. During the Phase A deployment the addon reloaded repeatedly (ordinary
NinjaScript recompile churn from `nt_compile` and `nt_script_execute`), and
`ShadowSessionsCompleted` went **0 → 3 in about four minutes**, on a single day, with no market
data connected and not one position taken. `MinShadowSessions=3` was satisfied outright. The
FR-29 soft gate at `RiskGuardAddOn.cs:2454-2460` — the check that is supposed to stand between
shadow mode and live arming — will now pass on this machine.

Severity is P1 rather than P0 because it cannot itself place or miss an order; it removes a
safety interlock. Note the asymmetry with FR-30/31 directly above it at line 604: that code is
careful never to rehydrate `_isArmed`, precisely so a restart cannot silently re-arm. The same
reasoning was not applied to the gate that authorises arming.

**Fix**: persist `_lastShadowSessionDate` in `PersistedStateData` alongside
`ShadowSessionsCompleted` and rehydrate it in the same block, so the pair moves together. A
restart then re-reads today's date and does not re-count. Consider also requiring a session to
have *seen activity* before it counts at all — a shadow day with no connected feed teaches
nothing, and counting it is the same error in a milder form.
**Test**: two constructions on the same simulated date increment the counter exactly once;
constructions on two different dates increment it twice.
**Fixed by**: persisting `LastShadowSessionDate` in `PersistedStateData` and rehydrating it in
the same block as the counter, so the pair travels together. Verified in production — the live
counter held steady across a recompile that would previously have bumped it.

**OUTSTANDING operational step.** The live `state.json` reads `ShadowSessionsCompleted = 5`,
inflated by restarts before the fix landed. It no longer climbs, but the historical value is
wrong and `MinShadowSessions=3` currently reads as satisfied. **Reset it with NinjaTrader
closed**, then restart:

```powershell
# NT8 must be CLOSED - shutdown flushes in-memory state and would overwrite the edit
$p = Join-Path $env:USERPROFILE 'Documents/NinjaTrader 8/RiskGuard/state.json'
$j = Get-Content $p -Raw | ConvertFrom-Json
$j.ShadowSessionsCompleted = 0
$j.LastShadowSessionDate = '0001-01-01T00:00:00'
$j | ConvertTo-Json -Depth 20 | Out-File $p -Encoding utf8
```

Do not edit it while NT8 is running: the addon rewrites the file on flush, and a torn write
loses persisted lockouts.

---

## 3. P1 — Rule semantics

### P1-16. `ConsecutiveLosses` over-counts on partial exits
**Where**: `RiskGuardAddOn.cs:1008-1014` — every negative delta in `RealizedProfitLoss`
increments the counter.
One trade closed in three partials at a loss = **3 consecutive losses**. §6.9 of the design doc
introduced flat-transition debouncing for `TradesToday` but not for this counter, so the two
disagree about what a "trade" is.
**Fix**: attribute realized-PnL deltas to the trade lifecycle already tracked by
`PositionState.LastFlatTransition`; evaluate win/loss once per flat transition.

### P1-17. Evaluation profit target is fed session-scoped PnL
**Where**: `RiskGuardAddOn.cs:1139` passes `stateModel.RealizedPnL`, which is
`raw - SessionStartRealizedPnL` (`1006`) and reset daily (`1376`).
`EvaluationTargetProfit` ($3,000 default) is a **cumulative** prop-firm evaluation target.
**Fix**: track `CumulativeRealizedPnL` in `PersistedStateData` (survives restarts) and feed that;
keep the session value for the daily-loss rule.

### P1-18. Two overlapping trailing-drawdown implementations
`EvaluatePnLRules` enforces `profile.TrailingDrawdown` against a **session-reset** `PeakEquity`
(`1101-1118`, reset to 0 at `1370`), while `EvaluateFirmMirror` (`2688`) implements the firm's
real trailing-DD model with `FirmTrailingDDConfig`. For Apex-style accounts the high-water mark
does **not** reset daily, so the first rule is either redundant or wrong depending on config.
**Fix**: make `FirmMirror` authoritative when `FirmMirror.Enabled`; skip the profile-level
trailing-DD rule in that case and document the precedence in the design doc.

### P1-19. Actions are neither deduplicated nor instrument-scoped
- A single `EvaluatePnLRules` pass can append `DAILY_LOSS_BREACH`, `TRAILING_DD_BREACH`,
  `NEWS_SHIELD_LOCKOUT`, `EVALUATION_TARGET_REACHED` and `PEAK_GIVEBACK_BREACH` — five
  `FlattenPosition` actions, each of which independently walks all positions and calls
  `account.Flatten` (`2450-2483`).
- `ExecuteAction`'s `FlattenPosition` **ignores `action.Instrument`** and flattens every
  instrument on the account, including instruments that only have working orders (`2460-2469`).
  A missing stop on MES therefore flattens MNQ too.
**Fix**: coalesce actions by `(AccountName, ActionType, Instrument)` before processing; honour
`action.Instrument` when set and only fall back to account-wide for lockout/panic rules.

### P1-20. Weak simulated-account detection gates the live safety switch — CLOSED 2026-08-07
**Where**: `TradeCopierEngine.cs:650` — `followerAcc.Name.StartsWith("Sim", …)`
An account named e.g. `SimplyApex-01` is treated as simulated and **bypasses the
`ArmedForLive` gate** (`653-657`).
**Fix as landed**: `TradeCopierEngine.IsSimulationAccount(account)` tests
`account.Provider == Provider.Simulator` and fails closed — a null account or an
unidentifiable provider reads as live. Playback is deliberately *not* exempt. The defect cut
both ways and the tests pin both: a live `SimpsonFund` is now refused, and a genuine Simulator
account whose name lacks the `Sim` prefix is now served.

**Same defect, different file, still open**: `McpBridgeAddOn.cs:1710, 2243, 2307` gate strategy
deployment with `Name.StartsWith("Sim") || Provider…` — the name prefix is OR'd in, so it has
the same hole. Tracked as **P2-38**.

### P1-21. Copier never re-subscribes to accounts that connect later
**Where**: `McpBridgeAddOn.cs:252-258` — `Account.All` is enumerated once at `State.Configure`.
RiskGuard handles this correctly via `Connection.ConnectionStatusUpdate`
(`RiskGuardAddOn.cs:296`, `OnConnectionStatusUpdate:770`).
**Fix**: mirror RiskGuard's pattern for `ExecutionUpdate` subscription, and unsubscribe on
disconnect to avoid duplicate handlers.

### P1-22. No slippage/latency control on copies
Everything is `OrderType.Market` with no reference to the leader's fill price, no maximum
acceptable slippage, and no latency measurement — while `LatencyMs` and `AvgSlippageTicks` are
displayed in the UI (`TradeCopierWindow.cs:799`) as if they were real.
**Fix**: record `exec.Time` → follower fill time to populate `LatencyMs`; compute realised
slippage in ticks vs the leader fill; add `MaxSlippageTicks` per relationship that quarantines
the relationship when exceeded; consider limit-with-offset instead of pure market for entries.

### P1-23. Symbol translation and sizing modes are partly cosmetic
- `TranslateSymbol` (`:360-395`) uses global `rawSymbol.Replace(symbol, target)` rather than a
  prefix substitution — fragile against any symbol appearing inside the expiry portion.
- `CopierSizingMode.NetLiquidationRatio`, `AvailableCashPercent` and `PerTickerMatrix` are
  declared (`:19`) but **not implemented** in `CalculateFollowerQuantity`; they silently degrade
  to `QuantityRatio`.
**Fix**: replace `Replace` with root-symbol substitution on the parsed root; either implement the
three sizing modes or remove them from the enum and the UI so the config cannot lie.

---

## 4. P2 — Dead safety code, unreachable features, and stated-vs-actual gaps

### P2-24. Written-but-never-called safety machinery
| Symbol | Location | Status |
|---|---|---|
| `CalculateSafeFollowerDelta` | TradeCopierEngine.cs:165 | never called — the fix for P0-5 already exists |
| `ReconcileFollowerPosition` | TradeCopierEngine.cs:194 | never called — the REAPER-equivalent desync repair |
| `IsQuarantined` | :326, :342 | read as a filter, **never set** by the engine on error |
| `DailyLossLimit` | :40, :501 | parsed, persisted, surfaced in the UI, **never enforced** |
| `EnableFollowerAtm` / `FollowerAtmStrategyName` | :36-37, :91 | copied between DTOs, never read |
| `LatencyMs` / `AvgSlippageTicks` | :43-44 | displayed in the UI, never computed |
| `StealthMode` | :38 | persisted, never read |

**Fix**: wire each one or delete it. Priority order: `CalculateSafeFollowerDelta` (P0-5),
`ReconcileFollowerPosition` (schedule it on a periodic reconciler — see P3-30), automatic
quarantine on submit exception / risk breach, then `DailyLossLimit` enforcement per relationship.
Config that is displayed but not enforced is worse than absent config — it invites a live
account to be armed on the belief that a limit is active.

### P2-25. The news shield can never fire in production
**Where**: `PropFirmProtectionSuite.cs:51` (`_newsEvents`), populated **only** by
`AddTestNewsEvent` (`:55`). `LocalNewsEventsFilePath` (`:36`) is parsed and persisted but never
read. `IsInNewsWindow` therefore always returns `false` outside tests, so the
`NEWS_SHIELD_LOCKOUT` branch (`RiskGuardAddOn.cs:1124`) is unreachable.
Also unimplemented: `EnableConsistencyCap` / `MaxDailyProfitPctOfTarget` / `EnableAutoDayFiller`
(parsed, never evaluated).
**Fix**: load events from `LocalNewsEventsFilePath` on config load and refresh periodically.
This repo already has an economic-calendar pipeline —
[ECONOMIC_CALENDAR_ARCHITECTURE.md](ECONOMIC_CALENDAR_ARCHITECTURE.md) — so the correct move is
to emit a JSON feed from it into the path the suite reads, not to build a second source.

### P2-26. Design-doc drift ([RiskGuardAddOn.md](RiskGuardAddOn.md))
| Doc claim | Code reality |
|---|---|
| §5, §6.5, §6.8: "1-second sweep" / "1-second `DispatcherTimer`" | `new Timer(OnSafetySweep, null, 5000, 5000)` — 5 s, `System.Threading.Timer` (`:303`) |
| §3 data-flow diagram: sweep → `EvaluateRules` | sweep no longer calls `EvaluateRules` (`:1448-1453`) |
| §6.5: sweep keeps aggregate sizing, firm-mirror, grace-expiry polling | all three moved to event handlers (`:889`, `:1048`) / per-FSM timers; sweep keeps only heartbeat, log flush, session reset, persist, lockout watchdog, FSM watchdog |
| §5, §6.7: "lock released before `Flatten`/`Cancel`" | violated by the sweep (P1-10) |
| §6.7: `EvaluateGraceExpiry` "called from a per-FSM Timer or the sweep" (code comment `:1708-1710`) | sweep never calls it — the "defensive" path does not exist |
| §9.1: "Automatic relationship quarantine on execution error or risk limit breach" | not implemented (P2-24) |
| §9.3: news / target / giveback "auto-lockout, auto-flatten" | news unreachable (P2-25); giveback mis-wired (P0-7); target semantics wrong (P1-17) |
| §2, §4, §8: "87 unit tests" / "84 comprehensive test methods" / "60 original + 24 FSM" in the same document | reconcile against an actual test run |
**Fix**: the doc is the artifact most likely to cause a wrong decision under pressure. Update it
in the same commit as each code change, and add a doc-drift check to the test harness (assert the
sweep interval constant matches the documented value).

### P2-27. The riskiest code has zero test coverage
`TradeCopierEngine.OnExecution` (`:613-745`) and `ReconcileFollowerPosition` (`:193-228`) are
inside `#if !TESTING`, so the entire copy path is excluded from `RiskGuardTests.csproj`. The same
applies to all real order submission in `RiskGuardAddOn.ExecuteAction`. The 4,237-line
`RiskGuardAddOnTests.cs` is a hand-rolled `Main`-plus-`Assert` console app with no CI job.
**Fix** — borrow V12's `PureLogic` split:
1. Extract the decision math into an NT8-free static class (`CopierSizingLogic`,
   `StopGuardDecisionLogic`) taking primitives/DTOs, with **no `#if`** — target position, delta,
   notional parity, stop price/side/quantity, coverage checks.
2. Keep `OnExecution`/`ExecuteAction` as thin submission shells over those functions.
3. Extend the stub `Account` (`TestingStubs.cs`) with a recording `Submit`/`Cancel`/`Flatten` so
   the submission shells become testable too.
4. Add a GitHub Actions job (`dotnet run --project ninjatrader-addon/RiskGuardTests.csproj`)
   with a non-zero exit on failure — the harness currently has to be run by hand.

### P2-28. Three divergent copies of the addon sources + committed build output — ✅ **closed 2026-08-07**
- `scripts/ninjatrader/addons/` — canonical (referenced by `ninjatrader-addon/RiskGuardTests.csproj`)
- ~~`scripts/strategies/nt8/addons_DONOTUSE/`~~ — **deleted**. Nine tracked files, zero code
  references (only this plan mentioned it); recoverable from history if ever needed.
- `mcp/ninjatrader-mcp/nt8-addon/` — **out of scope for this repo.** That path is a *git
  submodule* (gitlink `160000`), so its copies belong to the `ninjatrader-mcp` repo and must be
  fixed there. Deleting them from here would only dirty the submodule pointer.
- ~~`ninjatrader-addon/bin/`, `obj/`, committed `RiskGuardTests.exe`~~ — already resolved: all
  three are gitignored (`.gitignore:91-93`) and untracked. The plan text was stale.

**Fix as landed** — not the hard-link idea. `scripts/utils/sync_nt8_strategies.py` already
existed and does the job; it just had to be made trustworthy and safe:

- **It was blind to line endings.** It compared raw byte md5s, so with the repo on LF and the
  NT8 tree on CRLF it reported *every* file as drifted. That is where the runbook's false
  "the deployed sources have diverged" claim came from. `file_hash` now normalises CRLF and
  strips a BOM before hashing. A drift check that cries wolf on every file gets ignored, which
  is worse than no check.
- **It was all-or-nothing.** A full sync would have pushed 21 unrelated indicator files into a
  live NT8 mid-shadow-session. New `--only {strategies,indicators,addons}` scopes a deliberate
  deployment; orphan detection is skipped for scoped-out areas so it cannot report every
  deployed file as an orphan.

A hard link from the repo into `bin/Custom/AddOns/` was **considered and rejected**: it would
make every editor keystroke change what the live trading system compiles next, and destroy the
ability to run a shadow session against a known build while working on the next change. The
explicit deploy step is the feature.

Use `--verify --only addons` to check drift and `--only addons` to deploy. Never copy by hand
(this session did, and it is what left canonical two files ahead of deployed).

### P2-38. The strategy-deploy guard has P1-20's name-prefix hole too
*(found while fixing P1-20, 2026-08-07)*
**Where**: `McpBridgeAddOn.cs:1710`, `:2243`, `:2307` —
`account.Name.StartsWith("Sim") || account.Provider.ToString().Contains("imulat")`.
**What happens**: the provider test is correct, but the name test is OR'd in front of it, so a
funded account called `SimpsonFund` is still classified as simulated and can be deployed to
without `confirmLive=true`. Same root cause as P1-20, different file and different blast radius
— this one gates *strategy deployment*, not copying.
**Fix**: drop the name clause at all three sites and reuse
`TradeCopierEngine.IsSimulationAccount`, or lift that helper somewhere both addons can share.
**Test**: an account named `SimpsonFund` on a live provider is refused without `confirmLive`.
P2 rather than P1 because it requires an explicit deploy call to reach, not an automatic path.

### P2-29. Single-file size / complexity
`RiskGuardAddOn.cs` is 4,108 lines including a ~700-line WPF window (`RiskGuardWindow`,
`:3389-4096`); `McpBridgeAddOn.cs` is 5,452. V12 solved the same problem by splitting one
`partial class` across 71 files by concern and gating complexity in CI.
**Fix**: split into `RiskGuardAddOn.{Core,Fsm,Rules,Actions,FirmMirror,Persistence,Ui}.cs` as
`partial class`, and move `RiskGuardWindow`/`CardControls` to their own files. Optionally port
`scripts/complexity_audit.py` from the baseline repo as a pre-commit metric.

---

## 5. P3 — Architecture upgrades worth porting from V12

### P3-30. An independent reconciler (the REAPER port) — highest-value single addition
Today both addons trust their own in-memory model. V12's REAPER assumes the model is wrong and
re-derives truth from the broker every cycle. Build one auditor serving both addons:

```
RiskGuardReconciler (background thread, 1-2 s)
  for each subscribed account:
    broker truth  := account.Positions + account.Orders
    expected      := AccountState + _guardFsms  (+ copier target positions)
    detect:
      - naked position          (position != flat, no non-terminal covering stop >= qty)
      - partially covered       (stop qty < position qty)
      - orphan stop             (working stop, no position)
      - FSM/broker divergence   (FSM says Protected, broker has no stop)
      - copier desync           (follower position != f(leader position))
    remediate (marshaled to the order thread, deduped by in-flight dictionary,
               each with its own grace window):
      - attach stop | flatten | cancel orphan | re-derive FSM | quarantine relationship
```
Reuse what exists: `SeedFsmsForExistingPositions` is already a correct re-derivation routine, and
`ReconcileFollowerPosition` is already a correct follower repair — both just need to be called
from here. Borrow REAPER's `_repairInFlight` / `_nakedPositionFirstSeen` grace pattern so a
normal bracket-confirmation window is not mistaken for a naked position.

### P3-31. Expected-position ledger with reserve/rollback
V12 registers the master's expected position **before** submitting and rolls the reservation back
if the submit returns null. Adopting this fixes P0-2 structurally and gives the reconciler a
precise "expected vs actual" to compare, instead of inferring intent from order names.

### P3-32. Follower risk anchored to the follower's own fill
V12's Symmetry Guard resolves an `AnchorSnapshot` from the master's weighted fill and sizes
followers with a `SlippageCushionPoints` reserve so follower dollar risk cannot exceed the cap
even on a worse fill. Our copier has no equivalent. Minimum viable version: after the follower
fill, compute realised dollar risk from the follower's actual fill and the mirrored stop; if it
exceeds the relationship cap, reduce the position immediately rather than at the next evaluation.

### P3-33. Replace the global lock on the hot path
V12 enforces zero `lock()` via an `Enqueue(ctx => …)` actor model, so no event handler can ever
block another. A full port is large; the pragmatic subset is: keep `_stateLock` for state
mutation only, never hold it across I/O or broker calls (P1-10/12), and move the action queue to
a `ConcurrentQueue<GuardAction>` drained by a single executor.

### P3-34. Arm/shadow discipline extended to the copier
RiskGuard's `RunPreflight` + `MinShadowSessions` gate is the best-designed safety feature in
either addon. The copier only has a per-relationship `ArmedForLive` bool with a name-based sim
check (P1-20). Give the copier the same treatment: a global arm switch, a shadow mode that logs
intended follower orders without submitting, and a preflight that verifies every follower is
connected, subscribed, not locked, and has a resolvable instrument.

---

## 6. Execution order

> **Superseded for P0, which is complete.** The original phases 1–2 were the P0 work and landed
> as tickets T1–T5 (see [RISKGUARD_HARDENING_HANDOVER.md](RISKGUARD_HARDENING_HANDOVER.md) §1).
> The table below is the **remaining** work, re-ordered for what P0 changed and for test-first
> development. The live roadmap with current status is handover §4a; this is the reference
> version with exit gates.

### 6.0 Development model: test-first, suite as a first-class artifact

**Every defect gets its failing test before it gets its fix.** This is enforced mechanically, not
by convention:

- A ticket declares `expect_green` — the tests it exists to make pass.
- The loop **refuses the ticket** unless those tests are already *failing* at baseline. A name
  that is not red is either a typo (making the gate unfalsifiable) or a test that passes without
  the fix (so it does not test the defect).
- The test gate then **fails the candidate** while any named test is still red. "No regression" is
  not evidence that a defect is closed.
- Reviewers receive the acceptance tests read-only and must judge **completeness** (which spec
  behaviours and failure paths nothing covers) and **accuracy** (would this test fail if the
  defect returned?). Gaps are MAJOR findings.

The suite is never edited to make a patch pass: `*Tests.cs` is in the loop's protected paths, so
the implementer cannot reach it by construction. Tests are authored *outside* the implementation
loop, by a different party than the one being graded — which is the strongest form of this
discipline available here, not a limitation of it.

Two lessons paid for during P0 apply directly:
- **A test that cannot observe its own subject is worse than no test**, because it reads as proof.
  The P0-8 test built a locked RiskGuard but never wired the static the copier reads; it could
  never have passed however correct the fix.
- **A green suite is not a tested suite.** `ddba3433` found a test whose body had been replaced by
  a bad merge, silently skipping 21% of the run, while the suite reported green.

### 6.1 Remaining phases

| Phase | Content | Tests to write FIRST | Gate to exit |
|---|---|---|---|
| **A. Deploy P0** | no new code | — | A full session in `shadow`; `interventions.jsonl` shows no `PEAK_GIVEBACK_BREACH` on a profitable flat account and no wrong `COPY_BLOCKED_NO_GUARD` |
| **B. Foundation** ✅ | `expect_green` ✅, backfill T1–T3 tests ✅, P2-28 ✅ | submit-failure rolls back and clears `GraceEmitted`; auto-stop sized from live qty; scaled-down position still gets a stop; stop cancelled mid-position re-arms; profitable-flat emits no giveback; flip does not carry `PeakOpenGain` | Every P0 behaviour has a test that fails when reverted |
| **C. Gate integrity** DONE | **P1-20** done, then **P1-37** done | live-named account is NOT treated as simulated; unguarded live follower is refused; two restarts on one date count as one shadow session | T5's fail-closed gate no longer keys off a name prefix; `MinShadowSessions` cannot be satisfied by restarting |
| **D. Concurrency** | P1-35 + P1-10 (one ticket), P1-11, P1-12, P1-13, P1-14, P1-15, P1-36 | no `Account.*` reachable under `lock (_stateLock)`; sweep does not cancel protective stops; coverage aggregates across two partial stops | Lock-scope gate clean; sweep off the dispatcher |
| **E. Rule semantics** | P1-16, P1-17, P1-18, P1-19 | 3-partial loss counts as 1; eval target fed cumulative PnL; one trailing-DD implementation; instrument-scoped flatten leaves other instruments alone | Each rule has a test pinning its boundary |
| **F. Copier fidelity** | P0-9 (real bracket replication), P1-21, P1-22, P1-23, P3-32 | follower brackets present on every copy; re-subscribe on late connect; symbol translation table-driven | Brackets on every copy; latency/slippage from real fills |
| **G. P2 structural** | P2-24, P2-25, P2-26, P2-27 (CI half), P2-29 | drift assertion: design doc claims match code | CI runs the suite on push; doc matches code |
| **H. P3** | **P3-30 first** (reconciler/REAPER), P3-31, P3-33, P3-34 | manual stop cancel, manual naked position, follower desync each repaired within one grace window | Sim stress scenarios pass unattended |

**P3-30 is P3 by effort, not by value** — an independent auditor that re-derives truth from the
broker is the single highest-value addition in this document. Consider promoting it once D lands.

### Validation protocol (every phase)
1. Failing tests written and committed **before** the implementation ticket runs.
2. `shadow` mode on Sim accounts for the whole phase; diff intended vs actual actions in
   `interventions.jsonl`.
3. Adversarial Sim scenarios, run against the live bridge (extend
   `tmp/comprehensive_stress_test.ps1`): cancel a stop under an open position; reject a stop
   (invalid price); scale in past stop coverage; flatten the leader while a follower copy is
   in flight; lock a follower mid-session; disconnect a follower mid-copy; disarm and re-arm with
   positions open; kill NT8 with positions open and restart.
4. Only then flip `ArmedForLive` on a single live micro account with minimum size.

### Non-goals for this plan
- No port of V12's Photon SPSC ring / MMIO mirror. Our latency budget (HTTP bridge, 5 s sweep)
  is orders of magnitude above where zero-allocation ring buffers matter; adopting them would add
  risk, not remove it.
- No adoption of V12's entry logic (OR/RMA/MOMO/TREND/FFMA) — different problem domain.
- No move to `Account.All` iteration inside a strategy (V12's SIMA model). Our addon-based
  design is the right choice for copying trades placed by hand or by other strategies.

---

## 7. Quick-reference defect index

| ID | Severity | File:line | One-line |
|---|---|---|---|
| P0-1 | naked risk | RiskGuardAddOn.cs:1667, 1763 | `Protected→Unprotected` never re-arms grace; watchdog is log-only |
| P0-2 | naked risk | RiskGuardAddOn.cs:2595 | FSM state written after submit, overwrites reject; null submit silent |
| P0-3 | wrong size | RiskGuardAddOn.cs:2508, 2436 | auto-stop uses stale qty; over-cover flips position |
| P0-4 | naked risk | RiskGuardAddOn.cs:1555 | scale-in stays `Protected` without coverage check |
| P0-5 | wrong side | TradeCopierEngine.cs:401, 427 | exit qty unclamped → follower reverses; `CalculateSafeFollowerDelta` unused |
| P0-6 | wrong size | TradeCopierEngine.cs:426 | `Math.Max(1, …)` on micro→mini = up to 10× notional |
| P0-7 | false trigger | RiskGuardAddOn.cs:1154 | peak-giveback compares total-PnL peak vs unrealized only |
| P0-8 | gate bypass | TradeCopierEngine.cs:645 | copier ignores RiskGuard lockout |
| P0-9 | naked risk | TradeCopierEngine.cs:721 | followers get bare market orders; `EnableFollowerAtm` dead |
| P1-10 CLOSED | deadlock | RiskGuardAddOn.cs:1336-1446 | broker calls under `_stateLock`, violating documented invariant |
| P1-11 CLOSED | naked window | RiskGuardAddOn.cs:1410 | lockout sweep cancels protective + reducing orders |
| P1-12 | latency | RiskGuardAddOn.cs:865, 1342 | blocking file I/O under the global lock |
| P1-13 | latency | RiskGuardAddOn.cs:1317 | guard evaluation on the WPF dispatcher; skipped if null |
| P1-14 | correctness | RiskGuardAddOn.cs:1651 | `_pendingStops` single-slot, no TTL, side-blind |
| P1-15 CLOSED | coverage gap | RiskGuardAddOn.cs:2231 | re-arm does not seed FSMs for open positions |
| P1-35 CLOSED | deadlock | RiskGuardAddOn.cs:1620 | FSM teardown cancels orphan auto-stop under `_stateLock` |
| P1-36 | over-cover | RiskGuardAddOn.cs:3167 | coverage tracks one stop; two partial stops read as under-covered |
| P1-37 CLOSED | gate bypass | RiskGuardAddOn.cs:1510, 211, 609 | `MinShadowSessions` counted addon restarts; 0→3 in 4 min during Phase A |
| P1-16 | false lockout | RiskGuardAddOn.cs:1008 | consecutive losses counted per partial exit |
| P1-17 | never fires | RiskGuardAddOn.cs:1139 | eval target fed session PnL, not cumulative |
| P1-18 | conflict | RiskGuardAddOn.cs:1101 vs 2688 | two trailing-DD implementations, undefined precedence |
| P1-19 | over-broad | RiskGuardAddOn.cs:1085-1162, 2450 | duplicate actions; flatten ignores instrument scope |
| P1-20 CLOSED | gate bypass | TradeCopierEngine.cs:650 | sim detection by name prefix |
| P2-38 | gate bypass | McpBridgeAddOn.cs:1710, 2243, 2307 | same name-prefix hole in the strategy-deploy guard |
| P1-21 | silent no-op | McpBridgeAddOn.cs:252 | copier never re-subscribes on connect |
| P1-22 | no control | TradeCopierEngine.cs:721 | market-only copies; latency/slippage fields fake |
| P1-23 | silent fallback | TradeCopierEngine.cs:360, 397 | `Replace`-based symbol translation; 3 sizing modes unimplemented |
| P2-24 | dead safety | TradeCopierEngine.cs:165, 194, 326 | reconciler, delta clamp, quarantine, daily-loss all unwired |
| P2-25 | never fires | PropFirmProtectionSuite.cs:51 | news events only injectable from tests |
| P2-26 | doc drift | RiskGuardAddOn.md | 8 concrete claims contradicted by code |
| P2-27 | test gap | TradeCopierEngine.cs:613 | whole copy path inside `#if !TESTING`; no CI |
| P2-28 ✅ | hygiene | `addons_DONOTUSE` deleted; sync script fixed | CRLF-blind drift check; mcp copy is a submodule |
| P2-29 | maintainability | RiskGuardAddOn.cs (4,108 lines) | single file incl. 700-line WPF window |
