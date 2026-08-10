# RiskGuard + TradeCopier Hardening Plan

**Status** (2026-08-10, branch `harden/riskguard-p0-51`, suite **630 passed / 0 failed**): **41 of 55 closed**.
**`P0-51`/`P1-52` are VALIDATED LIVE** (replay, 2026-08-10 — see handover §4n). That replay opened
`P0-55` and `P1-54`.
Deployed, `shadow`, armed and guarding; NT8 compiles clean (0 errors, net48).
**`P0-51`, `P1-52` and `P0-53` are all CLOSED and deployed.** The suite is fully green again.
Live progress: [RISKGUARD_HARDENING_HANDOVER.md](RISKGUARD_HARDENING_HANDOVER.md).

> ✅ **`P0-48` is closed and verified live.** The restart cleared all 57 orphans, and a subsequent
> recompile — the exact event that used to add one every time — left `TradeCopierEngine` at
> exactly **1** handler. No operational items outstanding except `P2-41`.
**Created**: 2026-08-06

## Defect inventory — the count of record

**55 defects.** Numbered once, never renumbered, never reused. `P0-49` and `P0-50` were opened
and closed on 2026-08-07 (session 8); **`P0-51` and `P1-52` were opened on 2026-08-09 and are
OPEN**. All four were found by a live operator ATM trade rather than by any test — see the
entries at the end of §1.

> ✅ **`P0-51` is FIXED and deployed (2026-08-09).** Shadow no longer cancels or flattens: one
> `IsActingMode()` predicate gates both the sweep and, via `DrainPendingCancels`, the deferred
> cancel queue. `P1-52` is fixed with it.
>
> ✅ **`P0-53` is also fixed (2026-08-09).** The lockout's `CancelAllOrders` no longer cancels a
> protective stop while its position is open, so arming live no longer exposes a naked-flatten
> window.

| Band | IDs | Count | Status |
|---|---|---|---|
| P0 — naked-risk / wrong-size | `P0-1` … `P0-9`, `P0-48` … `P0-51`, `P0-53` | 14 | `P0-1`…`P0-9` closed; **`P0-9` items (3) and (4) pinned session 8; only profit-targets/OCO remains**. `P0-48` closed and verified live. **`P0-49`, `P0-50` opened and closed session 8**. **`P0-51` and `P0-53` both CLOSED 2026-08-09** |
| P1 — real bugs, not yet live-risk | `P1-10` … `P1-23`, `P1-35` … `P1-37`, `P1-39`, `P1-40`, `P1-42` … `P1-45`, `P1-47`, `P1-52` | 25 | **23 closed** — `P1-12`, `P1-14`, `P1-36` closed 2026-08-07 (session 8); `P1-13`'s fail-open half closed, its threading half open; **`P1-52` OPEN — flood governor counts a normal ATM bracket as a flood (2026-08-09)** |
| P2 — structural | `P2-24` … `P2-29`, `P2-38`, `P2-41`, `P2-46` | 9 | `P2-28`, `P2-46`, **`P2-38`, `P2-41`** closed; `P2-27` half-done; `P2-24`, `P2-25`, `P2-26`, `P2-29` open |
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
> Commits from the P0 phase (`d94d5521` … `f6405c7f`) still say `P1-30`/`P1-31`. Map them here.
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

### P0-9. Followers are left naked — no bracket replication — naked exposure CLOSED 2026-08-07 (stops); targets/ATM still open
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

**Fixed by (option 1, stops only) — 2026-08-07.** Followers are no longer naked. The copier now
subscribes to `OrderUpdate` (via `P1-21`'s subscription seam), recognises the leader's protective
stop, and mirrors it to every follower:

```
followerStop = followerEntry -/+ |leaderPositionAvgPrice - leaderStopPrice|
```

**The stop carries the leader's risk DISTANCE, anchored to the follower's own fill — not the
leader's stop price.** Copying the price is wrong by exactly the slippage `P1-22` now measures,
and wrong by an entire price scale across a micro/mini conversion. A follower that filled 2 points
worse than the leader gets the same 10 points of risk, not 12.

Lifecycle, each pinned by a falsifiable test:

| Behaviour | Test |
|---|---|
| Distance anchored to the follower's fill | `TestBracket_StopMirrorsLeaderDistanceFromFollowerFill` |
| Leader stop seen *before* the copy fills is held and applied on the fill | `TestBracket_StopBeforeFollowerFillIsAppliedOnFill` |
| Leader trailing its stop replaces, never duplicates | `TestBracket_MovingLeaderStopReplacesRatherThanDuplicates` |
| Follower flat → mirrored stop cancelled | `TestBracket_FollowerGoingFlatCancelsTheMirroredStop` |
| Price-incomparable instruments are not mirrored | `TestBracket_IncomparableInstrumentsAreNotMirrored` |

Notes that are not obvious:

- **The classification is RiskGuard's, not a second copy.** `IsStopType`, `IsProtectiveSide` and
  `IsPendingOrWorking` were promoted from `private` to `internal` and are reused. Two definitions
  of "the order protecting this position" would drift, and the copier's would be the one that
  silently stopped recognising a stop.
- **Cancel-then-replace, not modify.** A stale stop left working beside a new one over-covers: when
  both fire the follower is flipped to the opposite side.
- **Every broker call is outside `_lock`** (`P1-10`/`P1-35`). `SyncFollowerStop` computes under the
  lock, releases, then calls `Cancel`/`CreateOrder`/`Submit`.
- **An orphan stop is not a leftover, it is a new position.** Releasing on flat is why
  `UpdateFollowerBracketOnFill` re-reads `account.Positions` rather than accumulating from
  executions — the fill may be our copy, the mirrored stop firing, or a manual trade, and only the
  broker knows the net.
- **The mirrored stop is also visible to RiskGuard**, which will seed the follower's FSM as
  `Protected` instead of firing `MISSING_STOP_FLATTEN` at the grace deadline.

**Explicitly NOT done — do not read this as P0-9 fully closed:**

1. **Profit targets and OCO pairing.** Only stops are mirrored. A target is upside, not risk;
   adding it brings OCO and partial-fill re-pairing with it. The follower still exits via the
   copied market exit when the leader's target fills.
2. ~~Option 2 (`EnableFollowerAtm` / `FollowerAtmStrategyName`) is still unread config~~ —
   **RESOLVED by deletion.** Both fields were carried between DTOs and read by nothing: not
   parsed in `LoadFromDisk`, not exposed by the bridge API, not shown in the UI. They could not
   be set by any means, while implying followers were getting an ATM bracket. Removed, per
   `P1-23`'s rule that config must not lie.
   > **A copier-side DEFAULT bracket was deliberately not built in their place.** RiskGuard's
   > `StopAttachSeconds` → auto-stop already owns "position with no stop". Two independent stop
   > sources on one position over-cover, and when both fire the follower is flipped — the same
   > hazard the cancel-then-replace rule above exists to prevent, but across two components that
   > cannot see each other. If the leader never sets a stop, RiskGuard is the answer, not a
   > second mechanism.
3. **`StopLimit` leaders become `StopMarket` followers.** The limit offset is not carried.
   > **Assessed and accepted, not overlooked.** The trigger price is mirrored correctly; only the
   > post-trigger order type differs. A `StopMarket` is *more* likely to fill than a `StopLimit`,
   > so the divergence is toward the follower being protected, never toward a wrong or unfilled
   > exit. It is a fidelity gap, not a safety one.
   > **Investigating it is what found the signed-offset defect below**, which was a safety one.
4. **A leader that CANCELS its stop but stays in the position leaves the follower's stop working.**
   Deliberate — fail-safe — but it is a divergence from the leader, and it is not tested.

> Tracked as follow-on work rather than a new defect number, since `P0-9` remains open for (1),
> (3) and (4). The naked-follower exposure that made it P0 is closed.

#### The signed-offset defect — shipped in `76137575`, fixed same session

The first implementation computed `Math.Abs(leaderAnchor - stopPrice)` and always subtracted it
for a long. **A leader trailing its stop into profit puts the stop ABOVE its entry on a long**, and
the absolute distance mirrored that as a stop the same distance BELOW the follower's entry —
converting the leader's locked-in gain into open risk of equal size, on every follower, silently
and on the most ordinary trade management there is.

The offset is now signed and one expression covers both sides:

```
followerStop = followerEntry + (leaderStopPrice - leaderPositionAvgPrice)
```

**The original trail test could never have caught it**: it moved the stop 17990 → 17995 → 17998,
all below entry. Two tests now cover the inversion on both sides
(`TestBracket_StopTrailedIntoProfitStaysAboveFollowerEntry`,
`TestBracket_ShortStopTrailedIntoProfitStaysBelowFollowerEntry`), and the revert case reproduces
the exact shipped defect.

> **How it was found is the transferable part.** Not by a test, a gate, or review — by the
> operator asking whether item (3), the `StopLimit` conversion, could trigger wrong orders.
> Answering that honestly meant re-deriving what price the follower's stop actually lands on,
> which is when the `Math.Abs` became visible. **A test suite confirms the cases you thought of.**

### P0-49. The mirrored stop is never placed, because the anchor is read before the position exists — CLOSED 2026-08-07
*(found by an operator ATM trade on the live box, 2026-08-07 — not by any test)*
**Where**: `TradeCopierEngine.UpdateFollowerBracketOnFill`, called only from the follower's
`ExecutionUpdate`
**What happens**: the bracket's anchor (`FollowerEntryPrice`/`Side`/`Quantity`) was derived by
re-reading `followerAcc.Positions` at execution time. **NT8 raises `ExecutionUpdate` BEFORE
`PositionUpdate`**, so on an entry fill there is no position row yet: the method took its flat
branch, called `ReleaseFollowerBracket`, and returned. The anchor was never set.

Nothing rebuilt it. An ATM stop sits at `Accepted` and raises no further `OrderUpdate`, so
`OnLeaderOrderUpdate` never fired again either. **The follower was naked for the entire trade** —
precisely the exposure `P0-9` exists to close, surviving in the trigger rather than the arithmetic.

Observed live, Sim101 → Sim-ORB, MNQ SEP26:

```
15:43:21.237  Created FSM Sim-ORB|MNQ SEP26 -> Unprotected
15:43:24.241  [SHADOW] Would execute FlattenPosition triggered by MISSING_STOP_FLATTEN
15:45:22.572  COPIER_STOP finally submitted -- as the position was CLOSING
```

**Fixed**: the copier subscribes to `Account.PositionUpdate` for follower accounts, which is the
authoritative anchor source. On the execution path a flat read is ambiguous, and the anchor
disambiguates it — a bracket that has never held a position (`FollowerEntryPrice` is `NaN`) has
nothing to exit *from*, so flat means "the position event is still in flight"; once an anchor
exists, flat means flat and the bracket is released as before.

> **The first version of this fix simply stopped releasing on the execution path, and
> `TestBracket_FollowerGoingFlatCancelsTheMirroredStop` caught it immediately.** Releasing on flat
> is load-bearing; the defect was never that it released, only that it could not tell the two
> kinds of flat apart.

**The arithmetic was correct throughout.** The live stop landed at 29774.25 = follower entry
29789.25 + (29774.5 − 29789.5). `P0-9`'s signed offset is now **confirmed on real fills**.

### P0-50. Orphan mirrored stops submitted against a follower that is already flat — CLOSED 2026-08-07
*(found in the same live trade)*
**Where**: `TradeCopierEngine.SyncFollowerStop`
**What happens**: the method trusted the bracket's snapshot of the follower all the way to
`Submit`. When the follower had gone flat in the meantime, it submitted a protective stop anyway —
three of them on the live box (`34225`, `34226`, `34227` at 15:45:22 / :30 / :31), each cancelling
the last, all against a flat account, each consuming one of `MaxBracketStopAttempts`.

**An orphan stop on a flat account is not a leftover. It opens a position in the opposite
direction the moment it triggers.** The design doc already says this under `P0-9`; the code did
not enforce it on this path.

**Fixed**: `SyncFollowerStop` re-reads the live position immediately before touching the broker
and aborts on flat (`BRACKET_ABORTED_FLAT`) or on a side mismatch (`BRACKET_ABORTED_SIDE`),
cancelling any stale stop on the way out. Quantity is taken from the live position too, so a
follower that scaled out in between cannot receive a stop larger than the position it covers.
This is the same discipline T2 already applies to `RiskGuardAutoStop`, and for the same reason.

---

### P0-51. Shadow mode does not restrain the lockout — the sweep flattens for real — CLOSED 2026-08-09
*(found by a live operator ATM trade on 2026-08-09, the same way `P0-49`/`P0-50` were)*
**Where**: `RiskGuardAddOn.cs:1848-1889` (the lockout watchdog collects `cancelBatches` and
`flattenBatches`) and `:1899-1940` (it executes them: `batch.Key.Cancel(...)` at `:1901`,
`account.Flatten(...)` at `:1913`)

**What happens**: there are **two parallel paths out of a lockout, and only one is mode-gated.**

1. `EvaluateLockoutPhase` (`:2718-2735`) emits a `FlattenPosition` `GuardAction`, which goes
   through `ProcessAction`'s shadow gate at `:3277-3285` and correctly returns `SHADOW (SKIPPED)`,
   logging `[SHADOW] Would execute action FlattenPosition triggered by LOCKOUT_FLATTEN`.
2. The lockout watchdog sweep at `:1848` builds its own batches **with no `_mode` check anywhere
   in the block**, and after the lock releases calls `Cancel` and `Flatten` straight at the broker.

Path 2 does the work. The guard announces it is only observing, and flattens the account anyway.

**Observed live, 2026-08-09 21:15:25 ET.** A false flood lockout (`P1-52`) hit `Sim101`,
`SimCopyTest1` and `SimCopy2`. All three logged `[SHADOW] Would execute action FlattenPosition`,
and all three were then really flattened: market orders `34256`/`34257`/`34258`, action `Sell`,
qty 2, **name `"Close"`** — the name NT8's `Account.Flatten()` gives its close order — filled at
29848.75 within 15 ms of each other.

> **Manual operator action is ruled out.** A human "flatten everything" would also have closed
> `Sim-ORB`, which was long 2 on the same instrument at the same moment. `Sim-ORB` was the one
> account that had **not** tripped the lockout, and it was the one account left untouched. The
> flatten tracked lockout state exactly.

**Why this is P0 and not a tidiness issue.** Phase A's entire premise is that shadow is a safe
place to observe a guard that is not yet trusted — `:443` prints *"it observes and logs; it cannot
act outside 'live'"* on every startup. That statement is false for every lockout rule: order
flood, consecutive losses, daily loss. Any subscribed account, including a funded one, can be
cancelled and flattened by an addon the operator believes is inert.

**Fix**: the sweep must not reach the broker outside an acting mode. Do **not** simply wrap `:1899-1940`
in `if (_mode == "live")` and stop there — that leaves the divergence in place for the next path
that grows its own broker call. Route the sweep's cancel/flatten through the same arbiter +
mode gate every other action uses, so there is exactly one place where "may I touch the broker"
is answered. Until then, treat shadow as an **acting** mode for lockouts.

**A test would not have caught this by construction.** The suite exercises `ProcessAction`'s gate,
which is correct. Nothing asserts the *negative* — that in shadow mode, no broker call is issued
by any path. `S4`'s `BrokerCallObserver` is the machinery to assert it with; §0's lesson 2 ("a
machine check is only as good as the paths driven through it") applies verbatim, for the third time.

**Fixed 2026-08-09.** One predicate, `IsActingMode(bool forceLive = false)`, now answers "may I
touch the broker". `ProcessAction` calls it in place of its inline expression (behaviour unchanged)
and the lockout sweep calls it too.

The half that mattered was the **deferred cancel queue**, and two candidates got it wrong before
one got it right — both passing every gate:

| Attempt | What it did | Why it was wrong |
|---|---|---|
| 1 | Gated `DrainPendingCancels()` at the sweep's call site | The drain has **four** call sites; `ExecuteOrderUpdate` drains it too, so shadow still cancelled the trader's orders. Also left the queue growing all session, to fire as a stale burst on a mode switch |
| 2 | Drained unconditionally in every mode (the arbiter's own remedy) | Reintroduces the defect: four of the five enqueue sites are interventions against the trader's orders |
| 3 ✅ | Moved the decision **inside** `DrainPendingCancels` and gave the queue an intent | Covers all four call sites by construction |

`_pendingCancels` now carries `PendingCancelIntent`:

- **`Intervention`** — the trader's orders (lockout entry-cancel, blacklist, per-instrument cap).
  Withheld in a non-acting mode **and discarded**, never retained. Counts log as
  `SHADOW_PENDING_CANCEL`.
- **`Cleanup`** — RiskGuard's own orphaned auto-stop, from `UpdateFsmOnPosition`. Sent in **every**
  mode. Skipping it strands an orphan stop on a flat account, which opens a new position when it
  triggers — that is `P0-50`, and the review panel was right to catch it.

Pinned by six acceptance tests written before the fix. `P1-10`/`P1-35` and `P1-11` are preserved;
live-mode behaviour is unchanged. NT8 `nt_compile`: **0 errors** under net48.

---

### P0-53. In an acting mode the lockout cancels the protective stop before flattening — CLOSED 2026-08-09
*(found while fixing `P0-51`, by making an existing test state its mode honestly)*
**Where**: `RiskGuardAddOn.cs:3461-3474` — `ExecuteAction`'s `CancelAllOrders` branch
**What happens**: `P1-11` filtered the **sweep's** cancel batches so a protective stop is never
cancelled before the flatten is confirmed. But the lockout's `PendingCancel` phase *also* emits a
`CancelAllOrders` `GuardAction`, and that branch cancels **every** working order — no
`IsPositionReducingOrder` filter, no scoping. In an acting mode the protective stop is therefore
cancelled *before* the flatten is attempted, and a flatten that then fails leaves the position
naked with nothing covering it.

This is the same hazard `P1-11` was opened for, surviving in the action pipeline rather than the
sweep. `P1-11` fixed one of the two routes and the second was never looked at.

**Why it was invisible**: `TestP1_11_LockoutSweepDoesNotCancelTheProtectiveStopBeforeFlattening`
never set a mode, and `_mode` defaults to `"shadow"`, so `ProcessAction` skipped the
`CancelAllOrders` action and only the (correctly filtered) sweep path ran. The test passed for a
reason that had nothing to do with what it claimed to prove. **Two defects — this and `P0-51` —
were both hidden by the same missing `SetModeForTest` call.**

**Fix**: apply the same intent split the sweep uses. `CancelAllOrders` must not cancel
position-reducing orders while the position is still open; reuse `IsPositionReducingOrder` rather
than writing a second definition. Either filter inside `ExecuteAction`, or have the lockout emit a
narrower action — but the guarantee must hold on both routes, not one.

**Fixed 2026-08-09.** The `CancelAllOrders` branch now reuses `IsPositionReducingOrder` and skips
any order that is reducing a still-open position, logging the retention as `LOCKOUT_STOP_RETAINED`.
Because "reducing" is only true while a position is actually open, a flat account still has every
order cancelled and the lockout still reaches `Confirmed`. The retained stop is cleared by the
sweep's existing deferred batch once the flatten is confirmed and the instrument is flat — that
machinery is `P1-11`'s and did not need rebuilding.

Pinned by `TestP1_11_LockoutSweepDoesNotCancelTheProtectiveStopBeforeFlattening`, which now covers
**both** routes. Its `SetModeForTest("live")` is load-bearing: in shadow the test proves nothing.

---

### P0-55. A follower can be left with NO mirrored stop after a partial-fill entry — OPEN 2026-08-10
*(found by the live replay of the 2026-08-09 incident)*
**Where**: the copier's bracket path (`TradeCopierEngine.SyncFollowerStop` and its `OrderUpdate`
trigger); interacts with `RiskGuardAddOn`'s `FSM_PENDING_STOP_REJECTED`
**What happens, observed live 2026-08-10 00:11:31 ET**: a 2-lot ATM entry on `Sim101` filled in two
parts (1 then 1). The ATM's protective stop for **2** contracts arrived while the position was still
**Long 1**, and RiskGuard discarded it:

```
Sim101  FSM_PENDING_STOP_REJECTED  discarded 1 buffered stop(s) that are not protective
                                   cover for a Long 1 position.
Sim101  FSM_TRANSITION             Created FSM Sim101|MNQ SEP26 -> Unprotected
```

**`Sim-ORB` then received the copied entry but NO `COPIER_STOP` at all** and sat `Unprotected` for
the life of the trade, with RiskGuard emitting `MISSING_STOP_FLATTEN` (withheld, shadow). This is
the naked-follower condition `P0-9` exists to prevent, reached by a route `P0-9` does not cover.

> **Do not assume the mechanism.** The copier classifies the leader's stop with the *static*
> helpers (`IsStopType`, `IsProtectiveSide`, `IsPendingOrWorking`), not with RiskGuard's FSM, so the
> FSM rejection should not by itself suppress the mirror. Why the mirror never fired is **not
> established** — the bracket path has no instrumentation. Instrument `SyncFollowerStop` and the
> `OrderUpdate` bracket trigger before theorising further.

Note the contrast with the 2026-08-09 incident, where `Sim-ORB` **did** receive a `COPIER_STOP`
1 ms after its fill. The difference is the partial fill.

---

### P1-54. A lockout never lapses; `LockoutMinutes` has no effect — OPEN 2026-08-10
**Where**: `RiskGuardAddOn.cs` — the lockout test at `:1734`, the flag clear at `:1847`,
`EvaluateLockoutPhase` at `:2783`, and `CapturePersistedState`
**What happens**: the lockout test is `IsLockedOut || DateTime.UtcNow < LockoutUntil` — an **OR** —
and **nothing clears `IsLockedOut` when `LockoutUntil` lapses**. The only clears are the daily
session reset (`:1847`) and the manual `UnlockAccount`. Worse, **`LockoutUntil` is not persisted at
all**: `state.json` carries a top-level `LockedOutAccounts` name list, so after any restart the flag
is restored with `LockoutUntil = DateTime.MinValue`.

So `Overtrading.LockoutMinutes` (default 60) is decorative. An account locked out at 21:15 is still
locked out hours later, until the 18:00 ET session boundary.

**Observed**: `Sim101`, `SimCopy2` and `SimCopyTest1` were all still locked out at 00:11 ET the
next day, ~3 hours after the false flood lockout, blocking a fresh test order with
*"Order blocked: Account Sim101 is locked out."* All three had to be cleared with
`POST /api/lockout {"action":"unlock"}`.

> **This is `P1-45`'s fix being ineffective, not `P1-45` reopened** (IDs are never reused). `P1-45`
> added `LockoutUntil` beside the flag, which is necessary but not sufficient: with an OR test and
> no expiry-clear, the deadline can only ever *extend* a lockout, never end one.

**Fix**: clear `IsLockedOut` when `LockoutUntil` has passed — the natural home is the top of
`EvaluateLockoutPhase`, which already runs every sweep — and persist `LockoutUntil` alongside the
name list so a restart cannot silently convert a 60-minute lockout into an all-day one.

---

### P1-52. The order-flood governor counts a normal ATM bracket as a flood — CLOSED 2026-08-09
**Where**: `RiskGuardAddOn.cs:1596-1631`; threshold `Overtrading.MaxOrdersPerSecond` (default 5,
`:5132`)
**What happens**: the governor counts distinct order IDs in a 1-second window with no notion of a
bracket. **One ordinary 2-contract ATM entry is 6 orders** — 2 entry fills, 2 stops, 2 targets —
against a limit of 5. So any 2-lot bracketed entry trips a lockout.

**Observed live, 2026-08-09 21:15:22 ET**: `ORDER FLOOD DETECTED: 6 distinct orders in 1s (limit 5)`
on `Sim101`, and — because the bracket was mirrored by a third-party copier (Replikanto) to
`SimCopyTest1` and `SimCopy2` — on all three accounts in the same second. Copier fan-out
multiplies the blast radius of a false positive across every mirrored account simultaneously.

This is the third defect on this governor (`P1-44`, `P1-45`, `P2-46` preceded it), and the second
about it firing when it should not. `P2-46` fixed *double-counting one order's state transitions*;
this is different — six genuinely distinct orders that are one trade.

**Fix options**, in preference order:
1. Count **entry** orders only, or count bracket groups (NT8 exposes the OCO id linking the
   protective legs), so the metric tracks trading rate rather than order-object churn.
2. Failing that, raise the default and scale it with position size — but this only moves the
   threshold, it does not make the metric mean the right thing.

> **Do not "fix" this by raising `MaxOrdersPerSecond` alone.** The governor exists to catch a
> runaway loop submitting orders; a bracket is not that, and a limit high enough to clear a 5-lot
> ATM is high enough to miss a real flood.

**Fixed 2026-08-09 (option 1).** The one-second window is keyed by **OCO group** where an order has
one, falling back to `Order.Id` where it does not. A bracket's legs collapse to one key per OCO
group instead of one per leg, so the live case counts 4 instead of 6. The threshold is untouched
at 5.

> **It keys rather than excludes, and the difference matters.** An earlier candidate treated any
> OCO-tagged order as a protective leg and dropped it from the count entirely. That makes OCO a
> blind spot: a runaway loop emitting OCO entry pairs — an ordinary breakout pattern — would never
> trip the governor. Keying keeps every distinct group counted. The review panel did not catch
> this; it was found by reading the diff.

`P2-46` (one order counted once across `Submitted`/`Accepted`), `P1-45` (`LockoutUntil` paired with
the flag) and `P1-44` (never cancel a protective order to enforce a rate limit) all still hold.

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

### P1-12. Blocking file I/O under the global lock — CLOSED 2026-08-07
**Where**: heartbeat `File.WriteAllText` (`1342`), log `File.AppendAllLines` (`1351`),
`SavePersistedState()` (`1395`) — all inside `lock (_stateLock)`; plus
`SavePersistedState()` called **synchronously on every position change** at `865`.
**Why it matters**: `_stateLock` is the same lock every NT8 event handler needs. A slow disk
stalls order-event processing. The `_stateDirty` batching mechanism already exists and is used by
the sweep — line 865 bypasses it.
**Fix**: replace line 865 with `_stateDirty = true`. Move all file writes outside the lock;
consider a dedicated writer thread draining `_logQueue`.

**Fixed 2026-08-07 (session 8).** `SavePersistedState` was split into `CapturePersistedState`
(builds the payload under the lock, no I/O) and `WritePersistedState` (serialise + write, lock
released) — the old method took the lock *itself*, so no caller could opt out. The sweep captures
its heartbeat stamp, log batch and state payload under the lock and writes all three in a
`finally` at the bottom, **after** the broker work: nothing about a heartbeat file is worth
delaying a flatten for, and a `finally` means log lines already drained out of the queue are not
lost if a rule throws. The position-change site sets `_stateDirty`. `ToggleArmed` and
`UnlockAccount` capture inside, write outside — neither was a latency problem alone, but both had
to move before the invariant could be enforced for anyone, because `_stateLock` is re-entrant.

Machine-checked by `FileWriteObserver` + `TestIsStateLockHeld()`, the same probe `P1-10` got. A
second test pins the batching itself, because a "fix" that merely deleted the write would pass the
lock-scope check while silently dropping persistence.

> **Scoped out deliberately**: `SaveAndReloadConfig`/`LoadConfig` still do their I/O under the
> lock. The write-then-read-back has to stay atomic with the `_config` swap, so moving it is a
> separate change with its own failure mode, and it is a rare user-initiated path rather than an
> event path.

### P1-13. Guard evaluation runs on the WPF dispatcher — HALF CLOSED 2026-08-07
**Where**: `OnSafetySweep:1317-1323`, `UpdateFsmOnPosition:1599-1604`, `SeedFsms…:501-507`
**Why it matters**: safety-critical latency is coupled to UI responsiveness. V12 does the
inverse — REAPER audits on a background thread and marshals *only* the order-submitting calls to
the strategy thread via `TriggerCustomEvent`.
**Fix**: evaluate on the timer's own thread; marshal only `Account.Flatten/Cancel/Submit` to the
dispatcher. This also removes the "no dispatcher → silently return" failure mode at `1318`,
where the entire sweep is skipped if `Application.Current` is null.

**The fail-open half is CLOSED (2026-08-07, session 8), and it was the worse half.** Five handlers
plus the entire sweep opened with `if (dispatcher == null) return;`, so with `Application.Current`
null — early startup, or a headless NT8 — the guard received every position, order, execution and
account-item event and **discarded all of them**: no FSM, no grace timer, no rule evaluation, no
heartbeat, no session reset, no lockout enforcement, no watchdog, no log line, and
`/api/riskguard/version` still reporting armed and guarding. All six now route through one
`RunGuardWork` seam that runs the work **inline** when there is no dispatcher.
`OnGraceTimerCallback` already had exactly that fallback and was the only one of the six that did.

Asserted against source text, because the branch lives under `#if !TESTING` and cannot be executed
by the suite at all — the `P1-47` shape. Comments are stripped first so the seam can quote the
defective pattern in its own documentation.

**STILL OPEN — the threading inversion.** Evaluating on the caller's thread and marshalling only
broker calls is the latency fix. The evidence says it is safe (the copier has been submitting real
follower orders straight off NT8's account-event thread, with no marshalling, in production). But
it turns six handlers the dispatcher was implicitly serialising into genuinely concurrent ones, and
**the S-series does not cover that**: `S4` is lock-scope, `S7` is copier fan-out, and
`S5`/`S6`/`S8`/`S9` are sequential scenario tests. A genuine concurrent-guard-event stress test is
a prerequisite, not an optional extra.

### P1-14. `_pendingStops` is single-slot, unbounded in lifetime, and side-blind — CLOSED 2026-08-07
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

**Fixed 2026-08-07 (session 8)**, exactly as prescribed. `List<BufferedStop>` with a UTC stamp;
re-buffering the same `Order` object refreshes the stamp rather than duplicating (NT8 raises
`OrderUpdate` repeatedly for one order). Expired in the watchdog after **two** grace periods, not
one — one grace period is the longest a legitimate stop can lag its position event and still be the
thing protecting it, so expiring at one would break the race the buffer exists for. The test
asserts both edges. Terminal orders are dropped at any age.

The side-blind half is the one with teeth: a 10-lot sell-stop **breakout entry** buffered while
flat, followed by a 1-lot long opened by hand, produced `State = Protected` with
`CoveredQuantity = 10` on a 1-lot position — grace cancelled, auto-stop suppressed, and the account
left **9 lots short** if that order ever triggered. A sell-stop entry passes the side test by pure
coincidence. Consumption now also requires `Quantity <= positionQuantity`.

> Not changed: the live (non-buffered) recognition path still accepts an oversized stop as full
> coverage. That is the trader's own working order against a live position rather than an unrelated
> resting one.

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

### P1-36. Coverage tracking follows a single stop order, so two partial stops read as under-covered — CLOSED 2026-08-07
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

**Fixed 2026-08-07 (session 8).** `CoveredQuantity` and `RecognizedStopOrder` are now **derived**
from a list on the FSM and are **read-only**. That is deliberate: the old pair had to be assigned
together at nine separate sites and nothing stopped them drifting apart. Making them read-only
turned "find every writer" into a compile error — which is how the second half below was found.
`AddRecognizedStop` is idempotent by object reference; reads prune terminal orders first; losing
one leg of two drops that leg and re-arms grace for the delta only; seeding no longer `break`s on
the first stop it finds.

> **The defect lived in a second place, and closing only the first would have changed nothing.**
> `ExecuteAction` re-sized the auto-stop from the **live position**, ignoring existing cover. T2
> established that sizing must come from the live position rather than the emission snapshot and
> that is still right — but "the live position" is the wrong figure when the trader already has
> stops working. `EvaluateGraceExpiry` sized its *action* to the uncovered delta and
> `ExecuteAction` re-sized it back up to the full position, undoing it. Now
> `liveQuantity - alreadyCovered`. When that delta is `<= 0` the action aborts **and clears
> `GraceEmitted`** — dropping an action without clearing it is the T1/T2 trap that leaves a
> position permanently naked.

**The settled decision was retired in both places** (handover §5 and
`scripts/agent_loop/profiles.py`), per the rule in §5: left standing it would instruct the review
panel to approve reintroducing this.

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

**Operational step — ✅ DONE 2026-08-07 (session 7).** The live `state.json` had read
`ShadowSessionsCompleted = 5`, inflated by restarts before the fix landed. It no longer climbed,
but the historical value was wrong and `MinShadowSessions=3` read as satisfied. Now `0`, with
`LastShadowSessionDate` at `DateTime.MinValue`; backup `state.json.bak_20260807_095249`. All 93
`AccountsData` entries and the empty `LockedOutAccounts` list verified unchanged after the write.

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

> **`LastShadowSessionDate` must be `'0001-01-01T00:00:00'`, never `null`.** It is a non-nullable
> `DateTime` (`:4525`). Json.NET throws converting `null` to it, `LoadPersistedState` catches that
> and logs `Failed to load persisted state`, and **the whole persisted state is discarded** —
> every account's PnL baseline and the locked-out list included. The command above is correct; a
> `null` variant that had crept into the handover was caught by checking the field's C# type
> before running it.
>
> **"NT8 closed" means "the AddOn is not loaded".** The reliable check is that the bridge does not
> answer on `localhost:7890` — the listener starts at `State.Configure`. NT8 can sit at its login
> dialog with the process running and no AddOn loaded; that is when this reset was performed.

**Verify after the next successful login**: `GET /api/riskguard/state` (or the dashboard) should
report `ShadowSessionsCompleted` climbing to exactly **1** after one genuine shadow session, not
jumping on recompiles.

### P1-39. Every config load appends the default windows, so `WindowsET` grows without bound and a default can never be deleted — CLOSED 2026-08-07
*(found on 2026-08-07 while excluding an account ahead of Phase A validation — observed live,
then confirmed in code)*
**Where**: `RiskGuardAddOn.cs:4251` (the initializer) against `RiskGuardAddOn.cs:599`
(`LoadConfig`) and `McpBridgeAddOn.cs:5126` (`req.ToObject<RiskConfig>()`).
**What happens**: `WindowsET` is a `List<WindowConfig>` property pre-populated by a collection
initializer with `NY_AM_Macro` and `NY_PM_Macro`. Json.NET's default
`ObjectCreationHandling.Auto` **reuses** an already-populated collection and *appends* to it
rather than replacing it. So every deserialization adds the two defaults on top of whatever the
file holds — and `WindowConfig.Days` has the same shape, so each window's day list grows by five
entries at the same time.

Observed live. A single POST to `/api/riskguard/config` took the config from 6 windows to 10,
because that path deserializes **twice**: once in `ToObject<RiskConfig>()` (6 → 8) and again in
the `LoadConfig()` inside `SaveAndReloadConfig` (8 → 10). `Days` went 5 → 10 → 15 → 20 on the
affected windows. A plain addon restart costs one round, not two — and the deployment record in
the handover notes 24 restarts in four minutes of ordinary recompile churn.

Two consequences, and the second is the safety-relevant one:
- **Unbounded growth.** The file is rewritten each time, so the corruption is persisted and
  compounds. The `Days` lists were already doubled before this session touched anything.
- **A default window can never be removed.** Delete `NY_AM_Macro` from `config.json` and it is
  back on the next load. `EnableWindowGate` is `true` on this machine, and the gate
  (`:2560`) flattens positions opened *outside* the permitted set — so the failure direction is
  that the permitted set silently **widens** and the operator cannot narrow it. That is the same
  class as P1-20 and P1-37: a safety gate that quietly stops gating.

Duplicate entries are otherwise behaviour-neutral, because `Days` is parsed into a
`HashSet<DayOfWeek>` (`:619`) and the window test is a union.

**Fix**: annotate each `List` property with
`[JsonProperty(ObjectCreationHandling = ObjectCreationHandling.Replace)]`.

> **The settings-level fix this entry originally recommended is wrong — do not apply it.**
> Setting `ObjectCreationHandling.Replace` in `JsonSerializerSettings` also replaces the
> *dictionaries*, and `InstrumentLimits`, `AccountFirmMap` and `FirmProfiles` are constructed
> with `StringComparer.OrdinalIgnoreCase` (`:4242`, `:4278`, `:4279`). Json.NET would discard
> those instances and hand back fresh `Dictionary` objects using the **default** comparer,
> silently turning case-insensitive instrument and firm lookups case-sensitive — a quiet
> correctness regression traded for a cosmetic one. Those three are empty-initialized, so
> appending to them is already correct and they need no fix. A test now pins this
> (`InstrumentLimits must stay case-insensitive after deserialization`).
**Test**: deserialize a config whose `WindowsET` holds exactly the two default windows and assert
the result has two, not four; round-trip it twice and assert the count is stable. Assert a config
that omits `NY_AM_Macro` still omits it after a load.
**Not introduced by this branch** — the initializer dates to `a19c2adc`, well before the
hardening work.

**Fixed by**: `ObjectCreationHandling.Replace` on `Profiles`, `ExcludedAccounts`,
`LockoutBypassWhileDisarmedAccounts`, `BlockedInstruments`, `WindowsET` and `WindowConfig.Days`.
The bridge's `ToObject<RiskConfig>()` is fixed by the same attributes; no bridge change was
needed. Test-first: red at baseline (421 passed / **6 failed**, reproducing 2 → 4 on a single
load and 8 after round-trips), green after (**427 / 0**), red again when the two attributes are
reverted. **Verified in production**: the live config now reports 6 windows from a 6-window file,
where the same file previously loaded as 8.

The on-disk `config.json` was repaired by hand before the fix landed (deduplicated to 6 windows;
backups at `config.json.bak_prerepair`, `config.json.bak_prearm_20260807_061407`).

> **Still true, and a *separate* hazard: `POST /api/riskguard/config` does not merge.**
> `req.ToObject<RiskConfig>()` (`McpBridgeAddOn.cs:5126`) deserializes the body into a whole
> `RiskConfig`, so any field the body omits comes back as its **default** and is then written to
> disk by `SaveAndReloadConfig`. Always GET the full document, mutate one key, and POST the whole
> thing back — then diff every key. Tracked separately as `P2-41`.

---

## 3. P1 — Rule semantics

### P1-16. `ConsecutiveLosses` over-counts on partial exits — CLOSED 2026-08-07
**Where**: `RiskGuardAddOn.cs:1008-1014` — every negative delta in `RealizedProfitLoss`
increments the counter.
One trade closed in three partials at a loss = **3 consecutive losses**. §6.9 of the design doc
introduced flat-transition debouncing for `TradesToday` but not for this counter, so the two
disagree about what a "trade" is.
**Fix**: attribute realized-PnL deltas to the trade lifecycle already tracked by
`PositionState.LastFlatTransition`; evaluate win/loss once per flat transition.
**Fixed by**: banking deltas in `AccountState.OpenTradeRealizedDelta` while a position is open
and judging the total once in `SettleClosedTrade` at the flat transition (and on flips).

> **The obvious version of this fix drops losses.** It assumes the closing execution's realized
> PnL always arrives before the position-flat update. That ordering is *not* established — the
> live log happens to show it, but nothing guarantees it, and if PnL lags then settlement runs on
> a zero total and the real loss lands on the next trade. So late fills **revise** the
> settlement: the streak as it stood before the trade was judged is retained until the *next
> entry*, and re-judging from that snapshot is exact for any number of late fills, correctly
> flipping a settled win to a loss or back. Tested in both directions.
>
> A realized delta with **no tracked trade** (the guard never saw the position, or a standalone
> adjustment) is still judged on its own. Four pre-existing tests cover this; despite their names
> they never open a position, so they assert exactly this and not an ordering. Ignoring untracked
> realized losses would make the lockout less sensitive than before the fix.

**Test**: one trade exited in three partials is one consecutive loss, not three; three separate
losing trades are still three; a trade that nets positive resets the streak despite a losing
partial; a late fill that flips the net result revises the streak in either direction.

### P1-17. Evaluation profit target is fed session-scoped PnL — CLOSED 2026-08-07
**Where**: `RiskGuardAddOn.cs:1139` passes `stateModel.RealizedPnL`, which is
`raw - SessionStartRealizedPnL` (`1006`) and reset daily (`1376`).
`EvaluationTargetProfit` ($3,000 default) is a **cumulative** prop-firm evaluation target.
**Fix**: track `CumulativeRealizedPnL` in `PersistedStateData` (survives restarts) and feed that;
keep the session value for the daily-loss rule.
**Fixed by**: `AccountState.CumulativeRealizedPnL` (banked completed sessions) plus
`TotalRealizedPnL` (banked + current session), fed to `EvaluateProfitTargetLock`, persisted in
`AccountPersistedData` and rehydrated on load.

> Accumulated **once per session reset**, not per realized-PnL delta. A delta-based running total
> is permanently corrupted by a single spurious tick — the broker rebasing its own realized
> counter before our session reset runs would do it — and unlike the session value, a cumulative
> total is never rebased, so the corruption would never wash out.

**Test**: $1,500 banked plus $1,600 today reaches a $3,000 target while today alone does not; a
single $3,200 session still fires; prior losses offset rather than being ignored; and the total
survives a save/load round-trip, because a cumulative target that resets on recompile is not
cumulative.

### P1-18. Two overlapping trailing-drawdown implementations — CLOSED 2026-08-07
`EvaluatePnLRules` enforces `profile.TrailingDrawdown` against a **session-reset** `PeakEquity`
(`1101-1118`, reset to 0 at `1370`), while `EvaluateFirmMirror` (`2688`) implements the firm's
real trailing-DD model with `FirmTrailingDDConfig`. For Apex-style accounts the high-water mark
does **not** reset daily, so the first rule is either redundant or wrong depending on config.
**Fix**: make `FirmMirror` authoritative when a firm trailing rule is actually in effect for the
account; skip the profile-level rule only then.

> **The original wording of this fix — "skip whenever `FirmMirror.Enabled`" — is retired because
> it removes protection.** On the live config `FirmMirror.Enabled` is `true` while its
> `TrailingDD.Enabled` is `false` and no account is mapped, so it would have skipped the profile
> rule while the firm rule evaluated nothing, leaving *no* trailing-drawdown cover at all.
> Precedence keys on the account's **effective** firm config (P1-42's `ResolveEffectiveFirmConfig`),
> so it follows a mapped per-firm profile while leaving unmapped accounts on the same config
> covered. A test pins the enabled-but-inert shape.

**Fixed by**: `firmTrailingInEffect` in `EvaluatePnLRules`. The peak is still tracked while
suppressed, so the value stays meaningful if the firm rule is later disabled.
**Test**: red at baseline (451 / 2), green after (453 / 0), red again when the guard is reverted.

### P1-19. Actions are neither deduplicated nor instrument-scoped — CLOSED 2026-08-07
- A single `EvaluatePnLRules` pass can append `DAILY_LOSS_BREACH`, `TRAILING_DD_BREACH`,
  `NEWS_SHIELD_LOCKOUT`, `EVALUATION_TARGET_REACHED` and `PEAK_GIVEBACK_BREACH` — five
  `FlattenPosition` actions, each of which independently walks all positions and calls
  `account.Flatten` (`2450-2483`).
- `ExecuteAction`'s `FlattenPosition` **ignores `action.Instrument`** and flattens every
  instrument on the account, including instruments that only have working orders (`2460-2469`).
  A missing stop on MES therefore flattens MNQ too.
**Fix**: coalesce actions by `(AccountName, ActionType, Instrument)` before processing; honour
`action.Instrument` when set and only fall back to account-wide for lockout/panic rules.
**Fixed by**: a `scoped` filter in `ExecuteAction`'s `FlattenPosition`, and `CoalesceActions`
applied at all four processing loops. An account-wide flatten supersedes scoped ones for the same
account, since the wide call closes those instruments anyway.

> **Dedup must not erase the audit trail.** `EvaluatePnLRules` logs no breach event of its own —
> the `GuardAction` *is* the record — so merging five actions would have silently discarded the
> fact that four other rules fired. The survivor keeps its own `RuleId` (callers and tests match
> on it) and carries the rest in `MergedRuleIds`, which the action's audit line now names.

**Test**: red at baseline (455 / 4, the scope failure reading `got [MNQ,MES]`), green after
(459 / 0), red again when scoping and coalescing are reverted. The stub now records which
instruments each `Flatten` call was asked to close, because the defect is in what `ExecuteAction`
*requests*.

### P1-40. The peak-giveback rule has no floor on the peak, so one tick of noise trips a flatten — CLOSED 2026-08-07
*(found 2026-08-07 by the first live armed shadow session — observed, then confirmed in code)*
**Where**: `PropFirmProtectionSuite.cs:110-113`, reached from `RiskGuardAddOn.cs:1325`.
**What happens**: the rule is purely *proportional*. The only floor on the peak is
`peakOpenGain <= 0`:

```csharp
if (... || peakOpenGain <= 0 || currentUnrealized >= peakOpenGain) return false;
double givebackPct = (peakOpenGain - currentUnrealized) / peakOpenGain;
return givebackPct >= cfg.MaxPeakGivebackPct;   // 0.30 live
```

One MNQ tick is 0.25 pt = **$0.50**. If a position ticks one tick into profit, `PeakOpenGain`
becomes `0.50`; the next tick back to breakeven gives `0.50 / 0.50 = 100% >= 30%` and the rule
fires. A *fraction* of a tick is enough — the breach threshold at a $0.50 peak is any value below
$0.35. So **essentially every position breaches within seconds of entry**, and the rule re-fires
each time the position worsens past the prior trigger (`RiskGuardAddOn.cs:1328-1335`).

Observed live on `SimCopyTest1`, 2026-08-07, armed + shadow, 1 MNQ:
entry 13:24:06.036 @ 29721.75 → **`PEAK_GIVEBACK_BREACH` at 13:24:08.78, 2.4 s later, with the
position at −$1.00 and never meaningfully profitable**. It fired **six times** in the 36 s the
position was open (13:24:08.78, :10.79, :18.90, :22.95, :39.08, :40.08). Total excursion of the
whole trade was a few dollars; it closed +$8.50.

**In `live` mode this flattens nearly every trade seconds after entry**, and because the action is
`FlattenPosition` it would realise the loss each time. This is a hard blocker for leaving shadow —
it is not a tuning issue, the rule is unusable at any percentage while the peak can be one tick.

Note the unit tests do not catch it: they exercise the rule with meaningful peaks (a $500-scale
peak against a 0.30 cap), where proportional-only logic behaves sensibly. The defect lives
entirely in the small-peak regime, which is *every real position for its first seconds*.

Note also that `PropFirmProtectionSuite`'s own `ArmedForLive: false` / `enforcing: false` does
**not** gate this: `RiskGuardAddOn` calls `EvaluatePeakEquityGiveback` as a pure predicate and
acts under its own arming. The suite's switch reads like an off-switch and is not one.

**Fix**: gate the rule on an absolute floor before the proportional test — a configurable
`MinPeakGainDollars` (and/or a floor expressed in ticks of the instrument), below which the peak
is not considered established. Consider also requiring the peak to have been held for a minimum
interval, so a single print cannot establish it. Whatever the floor, the rule must not be able to
arm off sub-tick noise.
**Test**: peak `$0.50`, current `$0.00`, cap `0.30` → **no** breach. Peak `$500`, current `$300`,
cap `0.30` → breach (the existing behaviour must survive). Peak below the floor never breaches
regardless of how far the position falls; the existing daily-loss and stop rules cover that case.
**Fixed by**: `PropFirmProtectionConfig.MinPeakGainDollars` (default **50.0**, parsed from disk by
`ParseConfig`, set to `0` for the old purely-proportional behaviour), checked immediately before
the proportional test in `EvaluatePeakEquityGiveback`. Test-first:
`TestP1_40_NoiseSizedPeakDoesNotTripGiveback` was observed red at baseline (417 passed / **3
failed**, on exactly the three noise-peak assertions), green after the fix (**420 / 0**), and red
again when the single guard line is reverted. Deployed and compiled in NT8 with 0 errors; the live
`/api/prop/limits` response now reports `MinPeakGainDollars`, which is how you can tell the new
code is loaded.

> **The `50.0` default is the one judgement call here** and it is the number to argue with, not
> the mechanism. It says "below $50 of open profit there is no peak worth protecting". For a
> $50k account against a $1,500 trailing drawdown that is noise; for a much smaller account it
> may not be. It is per-config, so tune it rather than removing the floor.

### P1-42. Per-firm profiles are never read — `FirmMirror` silently protects nothing on a mapped account — CLOSED 2026-08-07
*(found 2026-08-07 while deciding what an armed shadow session would actually exercise)*
**Where**: `RiskGuardAddOn.cs:3594` (the call site) and `:3656` (`ComputeFirmMirror`), against
`FirmMirrorConfig.AccountFirmMap` / `FirmProfiles` (`:4294`, `:4295`).
**What happens**: `EvaluateFirmMirror` calls
`ComputeFirmMirror(balance, realized, unrealized, _config.FirmMirror, st, nowUtc)` — it passes the
**top-level** `FirmMirrorConfig` straight through, and `ComputeFirmMirror` reads only
`fm.TrailingDD` and `fm.DailyLoss`. **Neither `AccountFirmMap` nor `FirmProfiles` is consulted by
any evaluation path.** The only reference to `AccountFirmMap` in the whole addon is
`RunPreflight`'s validation at `:2668`, which checks that every mapped firm exists in
`FirmProfiles`.

That validation is what makes this dangerous rather than merely incomplete. Preflight *validates*
the mapping and refuses to arm if a firm name is unknown (P2-8), so the mapping presents as
load-bearing configuration that the system has checked — while no code reads it. A validated
mapping that is never used is worse than no mapping at all, because it buys false confidence.

Observed on this machine, 2026-08-07: `FirmMirror.Enabled: true`, but top-level
`TrailingDD.Enabled: false` and `DailyLoss.Enabled: false`, `AccountFirmMap: {}`, and four fully
researched profiles in `FirmProfiles` (TakeProfitTrader, Tradeify, Lucid, Apex — the TPT one
carrying the real $1,500 EOD trailing drawdown). Net effect: **no firm rule evaluates for any
account, including the funded TakeProfit Trader account, and mapping that account would not
change it.** The researched numbers are dead config.

**Fixed by**: `ResolveEffectiveFirmConfig` — maps account → firm → profile and substitutes that
profile's `TrailingDD`/`DailyLoss`, keeping the daily boundary (a property of the clock, not the
firm). Falls back to the top-level pair when the account is unmapped, the firm is absent, or the
profile omits a sub-rule. **The audit-log payloads read the effective config too**: left on the
top-level values they would have described a rule that did not run, which is the shape of failure
that made this defect invisible in the first place.
**Test**: red at baseline (430 passed / 3 failed) against the exact live config shape, green after
(433/0), red again when the resolver call is reverted.

Original fix note follows.

**Fix**: resolve an effective profile per account before computing. Look up
`AccountFirmMap[st.AccountName]`, then `FirmProfiles[firmName]`, and feed that profile's
`TrailingDD`/`DailyLoss` into `ComputeFirmMirror`, falling back to the top-level pair when the
account is unmapped or the firm is missing. `ComputeFirmMirror` already takes a
`FirmMirrorConfig`, so the smallest correct change is to build an effective one at `:3594` rather
than to thread new parameters through it. Both dictionaries are `OrdinalIgnoreCase`, so the
lookups are already case-tolerant — do not "fix" that (see P1-39).
**Test**: an account mapped to `TakeProfitTrader` breaches at the *profile's* trailing amount and
not the top-level one; an unmapped account still uses the top-level pair; a mapped account whose
firm is absent from `FirmProfiles` falls back rather than throwing (preflight blocks arming in
that case, but the evaluator must not depend on preflight having run); and with the top-level pair
disabled but a mapped profile enabled, the rule **does** fire — which is the exact case that
silently does nothing today.
**Sequencing**: closing this switches on real firm enforcement for any mapped account. Land it,
map the account, then run a full shadow session and read the `FIRM_*` events **before** going
anywhere near an acting mode — the numbers involved are the ones that fail a funded evaluation.

### P1-43. `ExecuteOrderUpdate` makes broker calls under `_stateLock` — a third instance of the closed P1-10/P1-35 invariant — CLOSED 2026-08-07
*(found 2026-08-07 while investigating the order-flood stress-test output)*
**Where**: `RiskGuardAddOn.cs:1400` opens `lock (_stateLock)`; `:1422` and `:1436` call
`account.Cancel(...)` inside it.
**What happens**: the documented central invariant — never hold `_stateLock` across a broker call
— is violated on the order-update path, which is the hottest path in the addon. P1-10 and P1-35
closed the same violation in the safety sweep and FSM teardown, and the lock-scope check was made
machine-enforced (`Account.BrokerCallObserver` + `TestIsStateLockHeld()`). **It did not catch this
one because the check only exercises the sweep and teardown paths**, not `ExecuteOrderUpdate`.
A machine check is only as good as the paths driven through it.
**Fix**: queue the cancels and drain after the lock is released, exactly as P1-35 did
(`_pendingCancels` / `DrainPendingCancels`). Do **not** wrap in a nested `lock` — it is re-entrant
and changes nothing.
**Test**: drive `ExecuteOrderUpdate` with the observer armed and assert zero broker calls occur
while `TestIsStateLockHeld()` is true. Then extend the check to *every* entry point that can reach
a broker call, so the next instance is caught by construction.

### P1-44. The order-flood cancel can kill a protective stop and leave a naked position — CLOSED 2026-08-07
*(found 2026-08-07, same investigation)*
**Where**: `RiskGuardAddOn.cs:1420-1423`.
**What happens**: on flood detection the triggering order is cancelled unconditionally:

```csharp
if (e.Order.OrderState != OrderState.Filled && e.Order.OrderState != OrderState.Cancelled)
    account.Cancel(new[] { e.Order });
```

There is **no `IsPositionReducingOrder` guard** — while the lockout-enforcement block immediately
below it at `:1432` has exactly that guard. So if the order that trips the rate limit happens to
be a stop-loss or other reducing order (very likely: an ATM submits entry, stop and target
together, and a copier fans the same burst across followers), RiskGuard cancels the protection
**and** locks the account out, leaving an open position with no stop. This is the P1-11 failure
mode in a path P1-11 did not touch.
**Fix**: reuse `IsPositionReducingOrder` before cancelling, as `:1432` does. Never cancel
protective orders to enforce a rate limit — rate-limit the *entries*.
**Test**: a burst in which the threshold-tripping order is a protective stop must leave that stop
working; only risk-increasing orders may be cancelled.

### P1-45. An order-flood lockout never expires, and it is persisted — CLOSED 2026-08-07
*(found 2026-08-07, same investigation)*
**Where**: `RiskGuardAddOn.cs:1419` sets `stateModel.IsLockedOut = true` and **never sets
`LockoutUntil`**.
**What happens**: the lockout test at `:1485` is
`(lockState.IsLockedOut || DateTime.UtcNow < lockState.LockoutUntil)` — an **OR**. Every other
lockout in the addon pairs the flag with a deadline (PnL `:1231`, `:1271`; overtrading `:2539`,
`:2558`), so it lapses. The flood path sets the flag alone, so it lapses **never** — and
`LockedOutAccounts` is persisted, so it survives a restart. A one-second burst can therefore
stop an account trading indefinitely with no timer and no obvious recourse.
**Fix**: set `LockoutUntil` from a configurable flood-lockout duration, consistent with the other
rules. Decide deliberately whether a flood should also require manual acknowledgement — but "no
deadline at all" should not be the accident it currently is.
**Test**: a flood lockout lapses after its configured duration; it is not resurrected by a restart
once lapsed.

### P2-46. The flood detector double-counts, so the real threshold is about half the nominal one — CLOSED 2026-08-07
*(found 2026-08-07, same investigation)*
**Where**: `RiskGuardAddOn.cs:1413-1417`.
**What happens**: the counter adds a timestamp for `OrderState.Submitted` **and** for
`OrderState.Accepted`, which are two states of the **same order**, with no dedupe by order id. A
single order commonly contributes two ticks, so the nominal "more than 5 orders/sec" fires at
roughly **3 real orders per second** — well within normal ATM bracket submission. The live log's
"29–32 orders/sec" readings are therefore not order counts but state-transition counts. The
threshold is also **hardcoded** (`> 5`) with no config knob, unlike every other limit in the addon.
**Fix**: count distinct order ids within the window, and expose the threshold and window in
`RiskConfig` alongside the other overtrading limits.
**Test**: ten distinct orders in a second trips a threshold of 5; one order passing through
Submitted→Accepted→Working counts once, not three times.

### P1-47. The guard defaults to disarmed, so every recompile silently removes all protection — CLOSED 2026-08-07
*(raised by the operator 2026-08-07 after four consecutive silent disarms in one session)*
**Where**: `RiskGuardAddOn.cs:206` (`private bool _isArmed = false;` in the non-TESTING build) and
`:655-656`, which deliberately does not rehydrate `IsArmed` from persisted state.
**What happens**: `nt_compile`, an NT8 restart, or any NinjaScript recompile reloads every AddOn
and the guard comes back **disarmed**. Nothing announces this beyond one `INITIALIZE` line, and
every evaluation path then returns early (`:1837`, `:2034`, `:1205`, `:2159`, `:2392`, `:2450`)
while `CanTrade` returns *allow* (`:124`). The dashboard is the only place the state is visible.
Observed four times in a single session on 2026-08-07; each time the operator had to notice and
re-arm by hand. A risk guard whose default state is "not guarding" fails open.

**The conflation.** `_isArmed` controls whether the guard *evaluates*; `_mode` controls whether it
*acts* (`:2895`, `isLive = _mode == "live"`). Armed + `shadow` observes and logs and cannot touch
the broker. The dangerous state is `live`, not `armed` — but the default protects against the
wrong one, and the cost is paid as unobserved gaps.

**Fix (recommended)**: make the default conditional on the resolved mode — come up **armed** when
the mode is non-acting (`shadow`), and **disarmed** in any acting mode, where arming should stay a
deliberate act after preflight. That keeps the original intent (freshly-loaded code must not act
on a funded account unattended) while closing the observability gap.

Whatever is chosen, **the disarmed state must be loud**: surface it in `/api/riskguard/version`
and `nt_health`, and log a distinct warning event on initialise rather than burying it in the
`INITIALIZE` line. The present failure is not just the default — it is that being unprotected
looks identical to being protected.

**Do not simply rehydrate `IsArmed` from disk.** That was removed on purpose (`:655`) so a restart
could not silently *re-arm* into an acting mode; restoring it would reintroduce that.
**Test**: constructing in `shadow` yields armed; constructing in `live`/`pure`/
`override_with_friction` yields disarmed; a persisted `IsArmed=true` never re-arms an acting mode
across a restart.
**Fixed by**: `DefaultArmedForMode` + `ApplyInitialArmState`, applied once at initialise after
`LoadConfig` resolves the mode (deliberately **not** on a config reload, which would override an
operator who disarmed on purpose). An unrecognised mode is treated as non-acting, because
`ProcessAction` requires exactly `"live"`. Coming up disarmed now logs `UNPROTECTED_ON_START`
naming the consequence, and `/api/riskguard/version` reports `mode`, `isArmed` and `guarding` so
the state is visible without opening the dashboard.

**Verified in production**: the next recompile came up `ARMED_ON_START` in shadow with the
endpoint reporting `isArmed: true` — the first reload of the day that did not silently disarm.

> **This one only failed in NT8.** Both methods were first written inside the `#if TESTING`
> region, which compiled cleanly under net8.0 and failed in net48 with "ApplyInitialArmState does
> not exist". The suite was green throughout. The `TESTING` guard now closes around them with a
> comment saying why — and this is the standing reason `nt_compile` is not optional after a
> change near the test hooks.

### P0-48. Every AddOn reload leaks a copier execution handler — CLOSED 2026-08-07, verified live
*(found 2026-08-07 while validating `P1-21`'s deployment, by reflecting on the live event list —
not by any test, review or log line)*
**Where**: `McpBridgeAddOn.cs`, `State.Configure` attached `OnAccountExecutionUpdate` to every
account and `State.Terminated` only called `StopServer()`. Nothing ever detached it.
**What happens**: NT8 hot-swaps a **new assembly** on every recompile and reloads every AddOn, but
the old instances are kept alive by the very event subscription that should have been removed. The
`-=` before `+=` in the old subscribe loop cannot help: it is evaluated against the *new* instance's
delegate, which never equals the orphan's.

Each orphan carries its own assembly's `TradeCopierEngine.Instance` — a distinct singleton with its
own `_relationships` (loaded from disk at its own `Configure`) and its own `_copiedExecutionIds`.
The per-instance dedupe therefore does **not** suppress them: one leader fill is copied once per
orphan.

**Measured on the live box, 2026-08-07 15:5x UTC**, `Sim101.ExecutionUpdate` invocation list:

| Owner | Handlers |
|---|---|
| `McpBridgeAddOn` (orphaned instances) | **57** |
| `ChartBars` / `ExecutionGrid` (NT8's own) | 6 |
| `MaxAlgoAutoTraderV3` | 1 |
| `TradeCopierEngine`, `RiskGuardAddOn`, `RiskManagerAddOn` | 1 each |
| | **67 total** |

`RiskGuardAddOn` at exactly 1 is the control: it already unsubscribes in `State.Terminated`
(`:331-338`), which is why it has not accumulated. The copier had no such path.

**Exposure at the time of discovery**: both relationships enabled, `Sim101 → Sim-ORB` with
`ArmedForLive: true`. A single Sim101 fill would have been copied by all 58 live engines, bounded
only by each one's independent `MaxPositionSize` re-read of the follower position.

> **Stated precisely**: the 57 live handlers and their distinct target instances are *measured*.
> The resulting duplicate copies are *inferred from the mechanism* — no fill occurred during the
> inspection, so the end-to-end effect has not been observed. The inference does not depend on
> anything unverified: the handlers are attached, and each forwards into a separate engine.

**Why this is P0 and not a housekeeping item**: it places unbounded unintended orders. It is
listed after `P1-47` because IDs are assigned in discovery order and never renumbered.

**Fixed by**: `P1-21`'s teardown half — `TradeCopierEngine.UnsubscribeAllAccounts()`, called from
`State.Terminated`, detaches exactly the accounts this engine instance attached. That stops
*recurrence* from the next reload onward.

**Not fixed by it**: the 57 orphans already attached. They belong to assemblies that are no longer
referenced by any live code, so no in-process call can enumerate or detach them by name — only an
**NT8 restart** clears them.

**✅ Both halves verified live, 2026-08-07.** NT8 was restarted and re-censused:

| | Before | After restart | After a further recompile |
|---|---|---|---|
| `McpBridgeAddOn` (orphans) | **57** | 0 | 0 |
| `TradeCopierEngine` | 1 | 1 | **1** |
| `RiskGuardAddOn` / `RiskManagerAddOn` | 1 / 1 | 1 / 1 | 1 / 1 |
| total | 67 | 8 | 10 |

The third column is the proof. A recompile reloads every AddOn and is precisely the event that used
to add an orphan; `TradeCopierEngine` holding at exactly 1 across it is the leak fixed, observed
rather than argued. (Totals rose 8→10 only from NT8's own `ChartBars`/`ExecutionGrid` re-registering.)

> **Note the post-fix shape**: `McpBridgeAddOn` is now **0**, not 1 — `P1-21` moved ownership of the
> subscription to `TradeCopierEngine`. An earlier draft of the runbook said to expect
> `McpBridgeAddOn == 1`; that is wrong. Expect `TradeCopierEngine == 1` and `McpBridgeAddOn == 0`.

**Open follow-ups**:
- Add the handler census to the deployment runbook (§4e) — it is cheap, and nothing else detects
  this class of bug.
- `RiskManagerAddOn.cs:150/289` has the same shape (subscribe at `Configure`, unsubscribe at
  `Terminated`) and currently reads 1, so it appears correct; confirm rather than assume.
- Consider whether `TradeCopierWindow.cs:1090` and `DynamicAtmManager.cs:507` hold any comparable
  subscription.

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

### P1-21. Copier never re-subscribes to accounts that connect later — CLOSED 2026-08-07
**Where**: `McpBridgeAddOn.cs:252-258` — `Account.All` is enumerated once at `State.Configure`.
RiskGuard handles this correctly via `Connection.ConnectionStatusUpdate`
(`RiskGuardAddOn.cs:296`, `OnConnectionStatusUpdate:770`).
**Fix**: mirror RiskGuard's pattern for `ExecutionUpdate` subscription, and unsubscribe on
disconnect to avoid duplicate handlers.
**Fixed by**: `TradeCopierEngine.RefreshAccountSubscriptions()` / `UnsubscribeAllAccounts()`, wired
from `McpBridgeAddOn`'s `State.Configure`, `Connection.ConnectionStatusUpdate` and
`State.Terminated`. A leader whose broker connects after startup is now subscribed on the next
connection change instead of being silently dead while enabled in the config and visible in the UI.

> **The bookkeeping deliberately lives on `TradeCopierEngine`, not in `McpBridgeAddOn`.**
> `RiskGuardTests.csproj` excludes `McpBridgeAddOn.cs` from the test build (its WPF dependencies
> break it), so a subscription implemented there is unreachable by any test — which is how this
> survived. Only the `Connection` event wiring, four lines, stays outside the test build.
>
> **The teardown half turned out to matter more than the re-subscribe half.** Adding
> `UnsubscribeAllAccounts` was defensive housekeeping when written; inspecting the live event list
> to confirm it worked found **57 orphaned handlers** from earlier reloads. That is **P0-48**.

**Tests** (`RiskGuardAddOnTests.cs`, all three proven falsifiable by
`scripts/agent_loop/verify_backfill_reverts.py`, which now reverts in `TradeCopierEngine.cs` too):
`TestCopierSubs_LateConnectingLeaderIsCopied` (0 copies when the pass is one-shot),
`TestCopierSubs_RepeatedRefreshAttachesOneHandler` (5 handlers when the `-=` is dropped),
`TestCopierSubs_TeardownDetachesHandlers` (1 handler survives when the detach is dropped).

> The idempotence test asserts on the **handler count**, via a new `ExecutionUpdateHandlerCount`
> on the Account stub, rather than on the number of copy orders. `OnExecution`'s `ExecutionId`
> dedupe would have absorbed a doubled handler within a single engine instance, so an
> order-counting assertion would have passed while proving nothing — the vacuous-test trap that
> the first draft of `S1`–`S4` fell into.

### P1-22. No slippage/latency control on copies — CLOSED 2026-08-07 (measurement + ceiling)
Everything is `OrderType.Market` with no reference to the leader's fill price, no maximum
acceptable slippage, and no latency measurement — while `LatencyMs` and `AvgSlippageTicks` are
displayed in the UI (`TradeCopierWindow.cs:799`) as if they were real.
**Fix**: record `exec.Time` → follower fill time to populate `LatencyMs`; compute realised
slippage in ticks vs the leader fill; add `MaxSlippageTicks` per relationship that quarantines
the relationship when exceeded; consider limit-with-offset instead of pure market for entries.

**Fixed by**: `RecordPendingCopy` at submit and `ObserveFollowerFill` on the follower's fill.
`LatencyMs` is the last observed leader-fill→follower-fill gap; `AvgSlippageTicks` is a running
mean. `MaxSlippageTicks` (default `0` = off) quarantines on breach.

The measurement hooks in at the **follower's** execution, immediately before recursion guard 1
drops it — that event is the copier's only possible observation of what its own order cost.

Four things that are not obvious, each pinned by a test:

1. **Slippage is signed by the follower's side.** Positive always means *worse for the follower*:
   a buy filled above the leader, or a sell filled below. Unsigned, a threshold quarantines
   relationships for filling **better** than the leader.
2. **Quarantine is entry-only, and quarantined relationships still copy exits.**
   `GetActiveRelationshipsForLeader` gained `includeQuarantined`, passed `true` for exits.
   `IsQuarantined` otherwise blocks *every* copy including the one that closes the follower out,
   stranding it in a position the leader has already left — the `P0-5` failure by another route.
   Same asymmetry as `P0-6`'s exit clamp and `P1-23`'s fail-closed sizing modes.
3. **Slippage is only computed between price-comparable instruments** — equal roots, or either
   direction of the built-in mini/micro matrix. A `CustomSymbolMappings` entry may legitimately
   map ES→NQ, whose prices are unrelated; with the guard removed that test records **−52,000
   ticks** and quarantines a healthy relationship on its first copy. Latency is still recorded,
   since it does not depend on price.
4. **Pending copies are keyed by `Order` *reference*, never `OrderId`.** `RiskGuardAddOn.cs:4481`
   already records that NT8's `OrderId` is not unique and can change across the historical→live
   transition. An id-keyed map passes every test in the suite because the stub assigns one stable
   GUID per order; `TestCopierSlip_FillIsMatchedWhenOrderIdChanges` makes the stub behave like
   NT8 instead. `OrderReferenceComparer` uses `RuntimeHelpers.GetHashCode` so the map is immune to
   any future `Order.Equals` override. **This was caught by reading the existing warning comment,
   not by a failing test — the suite was green with the defect in place.**

**Deliberately not done: limit-with-offset entries.** The plan lists it as "consider". It changes
copies from guaranteed-fill to maybe-fill, and a partial or unfilled entry leaves the follower's
size diverged from the leader's with no reconciliation — which is `P0-9`/`P3-30` territory. It
belongs with the bracket-replication work, not here.

**Also noted while in this code, not fixed**: `LoadFromDisk` does not parse `SizingMode`, `Mode`,
`StealthMode`, `PerTickerRatios` or `CustomSymbolMappings` for relationships, so those take their
defaults on every load and can only be set through the API or UI. `P1-23` assumed `PerTickerRatios`
was live config. Not yet numbered — verify before opening a defect.

### P1-23. Symbol translation and sizing modes are partly cosmetic — CLOSED 2026-08-07
- `TranslateSymbol` (`:360-395`) uses global `rawSymbol.Replace(symbol, target)` rather than a
  prefix substitution — fragile against any symbol appearing inside the expiry portion.
- `CopierSizingMode.NetLiquidationRatio`, `AvailableCashPercent` and `PerTickerMatrix` are
  declared (`:19`) but **not implemented** in `CalculateFollowerQuantity`; they silently degrade
  to `QuantityRatio`.
**Fix**: replace `Replace` with root-symbol substitution on the parsed root; either implement the
three sizing modes or remove them from the enum and the UI so the config cannot lie.
**Fixed by**: `TranslateSymbol` now substitutes the parsed root and matches case-insensitively;
`NetLiquidationRatio` and `AvailableCashPercent` fail closed on entries with an explicit log
instead of degrading to `QuantityRatio`. `PerTickerMatrix` needs no change — the per-ticker ratio
override is already applied in the ratio branch regardless of mode.

> **The case bug was the sharper half.** The root was upper-cased before lookup but `Replace` ran
> against the raw string, so a lower-case instrument name matched nothing, returned untranslated,
> and the copy went to the **leader's own contract** on a follower configured for the converted
> one — silently, with no error.
>
> **Unimplemented sizing modes fail closed on entries only.** Blocking an exit would strand the
> follower in a position the leader has already left, which is the P0-5 failure and worse than an
> unscaled one. Same asymmetry as the P0-6 exit clamp.

**Test**: `ES 12-26` ↔ `MES 03-26` both ways; a lower-case name still translates; a root that
merely *contains* a mapped symbol (`XES`) is not rewritten; an unimplemented sizing mode returns 0
for an entry and non-zero for an exit; `QuantityRatio` is unchanged.

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
| §5, §6.7: "lock released before `Flatten`/`Cancel`" | ~~violated by the sweep (P1-10)~~ — **true again since 2026-08-07**; P1-10/P1-35 closed and the invariant is now machine-checked by `TestP1_10_...`/`TestP1_35_...` |
| §6.7: `EvaluateGraceExpiry` "called from a per-FSM Timer or the sweep" (code comment `:1708-1710`) | sweep never calls it — the "defensive" path does not exist |
| §9.1: "Automatic relationship quarantine on execution error or risk limit breach" | not implemented (P2-24) |
| §9.3: news / target / giveback "auto-lockout, auto-flatten" | news unreachable (P2-25); giveback mis-wired (P0-7); target semantics wrong (P1-17) |
| §2, §4, §8: "87 unit tests" / "84 comprehensive test methods" / "60 original + 24 FSM" in the same document | reconcile against an actual test run |
**Fix**: the doc is the artifact most likely to cause a wrong decision under pressure. Update it
in the same commit as each code change, and add a doc-drift check to the test harness (assert the
sweep interval constant matches the documented value).

**The drift got wider on 2026-08-07, not narrower.** Phases B and C changed real behaviour that
`RiskGuardAddOn.md` still does not describe: the pending-cancel queue and `DrainPendingCancels`
(P1-35), the sweep's three-phase lockout ordering (P1-11), provider-based simulation detection
(P1-20), FSM re-seeding on arm (P1-15), and `LastShadowSessionDate` in the persisted state
(P1-37). Anyone reading the design doc to understand the current lockout or copier gate will be
wrong about all five. Closing P2-26 means a rewrite against the code as it now stands, not a patch
of the table above.

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

### P2-38. The strategy-deploy guard has P1-20's name-prefix hole too — CLOSED 2026-08-07
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

**Fixed 2026-08-07 (session 8) — and there were FOUR sites, not three.** The fourth
(`McpBridgeAddOn.cs:3992`, an order-placement path) used the name prefix **alone**, with no
provider test at all to fall back on. All four now call `TradeCopierEngine.IsSimulationAccount`.
Checked partly against source text: `McpBridgeAddOn.cs` is excluded from the test build by
construction, so its gates cannot be executed by the suite. The behavioural half — that the shared
classifier gets `SimpsonFund` right — is executed properly.

### P2-41. `POST /api/riskguard/config` overwrites the whole config with defaults — CLOSED 2026-08-07, verified live
*(split out of P1-39 on 2026-08-07 — the append half is closed, this half is not)*
**Where**: `McpBridgeAddOn.cs:5126` — `req.ToObject<RiskConfig>()`, then
`SaveAndReloadConfig(cfg)`.
**What happens**: the body is deserialized into a complete `RiskConfig`, so **every field the
caller omits silently becomes its default** — and `SaveAndReloadConfig` then writes that to
`RiskGuard/config.json` and reloads it. A caller posting `{"ExcludedAccounts": ["X"]}` intending
to add one exclusion would also reset `Mode` to `shadow`, `MinShadowSessions` to 0,
`EnableWindowGate` to false, and every `StopGuard`/`PnLRules`/`FirmMirror` value to its default,
destroying the live risk configuration. Nothing in the response indicates this happened — it
returns `status: "applied"` and echoes the *request*, not the resulting config.
**Workaround until fixed**: GET the full document, mutate the one key, POST the whole thing back,
then GET again and diff every key. That discipline is what surfaced P1-39.
**Fix**: merge the incoming `JObject` onto the live config (`JObject.Merge` with
`MergeArrayHandling.Replace`) before deserializing, or require an explicit
`?full=true` for whole-document replacement and reject partial bodies otherwise. Echo the
resulting live config rather than the request.
**Test**: POST `{"ExcludedAccounts":["X"]}` against a config with `MinShadowSessions=3` and
`Mode="shadow"`; assert both survive and only `ExcludedAccounts` changed.
P2 rather than P1 because reaching it requires an explicit API call, not an automatic path.

**Fixed 2026-08-07 (session 8).** The incoming `JObject` is merged onto the live config
(`RiskConfigMerge`), with arrays **replaced** rather than concatenated — union semantics would make
`ExcludedAccounts` append-only with no way to remove an entry through the API, and concatenation is
the exact mechanism behind `P1-39`. The response now echoes the **resulting** live config as
`config` and the request as `requested`; the old reply looked identical whether the merge happened
or not.

The merge lives in `RiskGuardAddOn.cs`, not the bridge, because the bridge is excluded from the
test build — it is pure JSON manipulation with nothing NinjaTrader about it, and putting it there
is what makes it testable at all.

> **Verified live, by accident, immediately after deploying.** `nt_riskguard_config` with no
> arguments POSTs an **empty body**. Under the old code that single call would have flattened the
> live risk configuration to defaults: `Mode` shadow, `MinShadowSessions` 0, `EnableWindowGate`
> false, all six `WindowsET` gone, all four `FirmProfiles` gone. The post-fix response returned
> `"requested": {}` alongside the complete, unchanged live config. **The MCP tool most likely to be
> reached for as a read was itself a destructive write.**

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
- **A green suite is not a tested suite.** `ff72e574` found a test whose body had been replaced by
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
| P0-51 CLOSED | gate bypass | RiskGuardAddOn.cs:1848-1889, 1899-1940 | lockout sweep calls `Cancel`/`Flatten` with no `_mode` check; shadow logs "would execute" and flattens anyway |
| P1-52 CLOSED | false lockout | RiskGuardAddOn.cs:1596-1631, 5132 | flood governor counts a 2-lot ATM bracket (6 orders) as a flood against a limit of 5 |
| P1-10 CLOSED | deadlock | RiskGuardAddOn.cs:1336-1446 | broker calls under `_stateLock`, violating documented invariant |
| P1-11 CLOSED | naked window | RiskGuardAddOn.cs:1410 | lockout sweep cancels protective + reducing orders |
| P1-12 | latency | RiskGuardAddOn.cs:865, 1342 | blocking file I/O under the global lock |
| P1-13 | latency | RiskGuardAddOn.cs:1317 | guard evaluation on the WPF dispatcher; skipped if null |
| P1-14 | correctness | RiskGuardAddOn.cs:1651 | `_pendingStops` single-slot, no TTL, side-blind |
| P1-15 CLOSED | coverage gap | RiskGuardAddOn.cs:2231 | re-arm does not seed FSMs for open positions |
| P1-35 CLOSED | deadlock | RiskGuardAddOn.cs:1620 | FSM teardown cancels orphan auto-stop under `_stateLock` |
| P1-36 | over-cover | RiskGuardAddOn.cs:3167 | coverage tracks one stop; two partial stops read as under-covered |
| P1-37 CLOSED | gate bypass | RiskGuardAddOn.cs:1510, 211, 609 | `MinShadowSessions` counted addon restarts; 0→3 in 4 min during Phase A |
| P1-39 CLOSED | gate widens | RiskGuardAddOn.cs:4251, 599; McpBridgeAddOn.cs:5126 | Json.NET appends to initialized lists; `WindowsET` grows every load and a default window cannot be deleted |
| P1-47 CLOSED | fails open | RiskGuardAddOn.cs:206, 655 | guard defaults to disarmed, so every recompile silently removes all protection |
| P1-43 CLOSED | invariant | RiskGuardAddOn.cs:1400, 1422, 1436 | broker `Cancel` under `_stateLock` on the order-update path; the machine check never drove this path |
| P1-44 CLOSED | naked position | RiskGuardAddOn.cs:1420 | flood cancel has no `IsPositionReducingOrder` guard and can cancel a protective stop |
| P1-45 CLOSED | permanent lockout | RiskGuardAddOn.cs:1419, 1485 | flood lockout sets no `LockoutUntil`, so it never lapses, and it is persisted |
| P2-46 CLOSED | miscount | RiskGuardAddOn.cs:1413 | Submitted and Accepted both counted for one order; threshold hardcoded at 5 |
| P1-42 CLOSED | silent no-op | RiskGuardAddOn.cs:3594, 3656 | `AccountFirmMap`/`FirmProfiles` are never read; firm-mirror protects nothing on a mapped account, and preflight validates the unused mapping |
| P1-40 CLOSED | false flatten | PropFirmProtectionSuite.cs:110; RiskGuardAddOn.cs:1325 | giveback rule was proportional-only; a one-tick peak made any retrace a 100% breach — fired 6× in 36 s live |
| P1-16 CLOSED | false lockout | RiskGuardAddOn.cs:1008 | consecutive losses counted per partial exit |
| P1-17 CLOSED | never fires | RiskGuardAddOn.cs:1139 | eval target fed session PnL, not cumulative |
| P1-18 CLOSED | conflict | RiskGuardAddOn.cs:1101 vs 2688 | two trailing-DD implementations, undefined precedence |
| P1-19 CLOSED | over-broad | RiskGuardAddOn.cs:1085-1162, 2450 | duplicate actions; flatten ignores instrument scope |
| P1-20 CLOSED | gate bypass | TradeCopierEngine.cs:650 | sim detection by name prefix |
| P2-38 | gate bypass | McpBridgeAddOn.cs:1710, 2243, 2307 | same name-prefix hole in the strategy-deploy guard |
| P2-41 | silent overwrite | McpBridgeAddOn.cs:5126 | config POST does not merge; omitted fields reset to defaults and are written to disk |
| P1-21 | silent no-op | McpBridgeAddOn.cs:252 | copier never re-subscribes on connect |
| P1-22 | no control | TradeCopierEngine.cs:721 | market-only copies; latency/slippage fields fake |
| P1-23 CLOSED | silent fallback | TradeCopierEngine.cs:360, 397 | `Replace`-based symbol translation; 3 sizing modes unimplemented |
| P2-24 | dead safety | TradeCopierEngine.cs:165, 194, 326 | reconciler, delta clamp, quarantine, daily-loss all unwired |
| P2-25 | never fires | PropFirmProtectionSuite.cs:51 | news events only injectable from tests |
| P2-26 | doc drift | RiskGuardAddOn.md | 8 concrete claims contradicted by code |
| P2-27 | test gap | TradeCopierEngine.cs:613 | whole copy path inside `#if !TESTING`; no CI |
| P2-28 ✅ | hygiene | `addons_DONOTUSE` deleted; sync script fixed | CRLF-blind drift check; mcp copy is a submodule |
| P2-29 | maintainability | RiskGuardAddOn.cs (4,108 lines) | single file incl. 700-line WPF window |

---

## 8. Stress and adversarial test programme

The order-flood events in the live log were a deliberate operator stress test, and reading their
output found four defects in an afternoon (`P1-43`, `P1-44`, `P1-45`, `P2-46`) that months of
review and a green suite had not. That is the argument for making stress tests a standing part of
the suite rather than an ad-hoc exercise.

**The lesson from `P1-43` in particular**: the lock-scope invariant *is* machine-checked, and the
check still missed a violation, because it only ever drove two code paths. A check is only as good
as the paths driven through it. Stress tests exist to drive the paths nobody thought to drive.

### Already present
- `TestCopierGroup_GroupStressAndConcurrency` — parallel group mutation, asserts zero thread
  exceptions.
- `TestP1_10_...`, `TestP1_35_...` — lock-scope checks, but only over the sweep and FSM teardown.

### To build

| # | Stress test | Must prove | Defect it would have caught |
|---|---|---|---|
| S1 ✅ | **Order burst** — N distinct orders/sec against the rate governor | fires on *distinct order ids* at the configured threshold; one order passing Submitted→Accepted→Working counts once | `P2-46` |
| S2 ✅ | **Burst whose tripping order is a protective stop** | the stop stays working; only risk-increasing orders are cancelled | `P1-44` |
| S3 ✅ | **Flood lockout lifetime** | the lockout lapses after its configured duration and is not resurrected by a restart | `P1-45` |
| S4 ✅ | **Lock-scope sweep over every entry point** — drive `ExecuteOrderUpdate`, `ExecuteAccountItemUpdate`, position updates, grace expiry, watchdog and the sweep with the broker observer armed | **zero** broker calls while `TestIsStateLockHeld()` is true, on every path, not a hand-picked two | `P1-43` |
| S5 ✅ | **Partial-fill storm** — one trade exited in many small fills, both event orderings | exactly one consecutive-loss judgement; late fills revise rather than accumulate | `P1-16` |
| S6 ✅ | **Rapid flip loop** — long↔short repeatedly | FSM coverage never outlives its position; no stale `CoveredQuantity`; grace re-arms each leg | `P1-36`, T1 |
| S7 ✅ | **Copier fan-out under burst** — one leader, many followers, rapid entries and exits | no duplicate copies, no follower left inverted, sizing correct under concurrency | `P0-5`, `P0-6`, `P1-22` |
| S8 ✅ | **Config reload while armed and in position** | live reload does not drop FSMs, coverage or lockouts, and does not corrupt the config | `P1-39` |
| S9 ✅ | **Restart mid-trade** — kill and reload with a position open | seeded FSM matches the broker; no double-count of trades or losses; lockouts survive | `P1-15`, `P1-16` limit |

> **S1–S4 landed 2026-08-07** as `TestStress_S1toS4_OrderFloodGovernor`, and immediately caught
> all four defects (461 passed / 4 failed at baseline, 465 / 0 after). S4 currently drives
> `ExecuteOrderUpdate` only; extending it to *every* entry point is still open, and is the part
> that would stop a fourth instance of the lock-scope violation appearing somewhere else.
>
> **The first draft of these tests was vacuous and it nearly went unnoticed.** Passing `null` as
> `sender` made `ExecuteOrderUpdate` throw on `(Account)sender` inside its own `try/catch`, so
> every call was swallowed: three assertions "passed" against code that never ran, including the
> lock-scope one. Only the two assertions that expected a *positive* effect failed and gave it
> away. A stress test that drives no code is worse than no stress test, because it reports safety.
> Always confirm a stress test fails for the reason you intended before trusting a pass.

### Rules for these tests
- They are **acceptance tests for the defects above** — write each one red against current code,
  and keep it in the suite afterwards. Do not commit a stress test that has never failed.
- Drive them through the real entry points (`ExecuteOrderUpdate`, `ExecuteAccountItemUpdate`,
  `UpdatePosition`), not by calling internals directly, or they will not catch wiring defects.
- Concurrency tests must assert on an observed invariant, not merely on "no exception thrown" —
  the existing group-stress test only asserts the latter, which is why it has never caught
  anything.
