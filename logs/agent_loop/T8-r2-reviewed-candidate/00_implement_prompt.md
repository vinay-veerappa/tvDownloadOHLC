# TICKET T8: P1-56: concurrent bracket syncs create duplicate protective legs -- reserve before submit, with rollback
## Defect
`SyncFollowerStop` decides what to do under `_lock`, sets `bracket.WorkingStop = null` while it still holds the lock, then releases the lock and calls the broker. `WorkingStop` is only reassigned AFTER `Submit`. A second sync entering that window reads `WorkingStop == null`, concludes the follower has no protective stop, and creates another one.

Observed live 2026-08-10 01:02 on a clean 2-lot ATM: `Sim-ORB` finished holding `COPIER_STOP` qty 1 AND `COPIER_STOP` qty 2 against a 2-lot position -- three contracts of stop behind two contracts of position, both orders carrying the same creation timestamp. That is over-cover: when both fire the follower is flipped to the opposite side, which is the exact hazard the cancel-then-replace rule was written to avoid.

The two triggers that raced are the pair a partial fill produces. `UpdateFollowerBracketFromPosition` syncs from the follower's PositionUpdate at 1 lot; `ReevaluateLeaderStops` -> `OnLeaderOrderUpdate` (the P0-55 re-anchor) syncs at 2 lots a few milliseconds later. Both call `SyncFollowerStop`.

The window is PRE-EXISTING and is not caused by the parked mirrored-target work; that work only doubled the number of sync invocations and turned a rare interleaving into a reproducible one.

653 tests passed with this defect live, because every existing test drives the sync paths sequentially. The acceptance test written for this ticket does not: it parks the first sync inside `CreateOrder` and drives the second one from another thread.
## Required change
1. PUBLISH AN IN-FLIGHT RESERVATION ON THE BRACKET, UNDER `_lock`, BEFORE THE LOCK IS RELEASED for any broker call. This is `T2`'s reserve-before-submit pattern (`P0-2`/`P0-3`) applied to the bracket.

   Use a FIELD ON `FollowerBracket` -- a bool, or a small enum if you prefer. Do NOT publish a placeholder `Order` into `WorkingStop`: `WorkingStop` is read by `ReleaseFollowerBracket`, `OnFollowerOrderUpdate` and `GetMirroredStopPriceForTest`, and a non-order sentinel there would leak into all three.

   TIMING IS THE WHOLE TICKET. The reservation must be visible before the FIRST broker call, which is `CreateOrder` (or `Cancel`/`Change` on the trail path) -- not just before `Submit`. `T2`'s auto-stop reserves between `CreateOrder` and `Submit`; copying that literally here leaves the window from lock-release to `CreateOrder` wide open and the acceptance test will still fail.

2. WHILE THE RESERVATION IS SET, no other invocation of `SyncFollowerStop` for THAT bracket may reach the broker -- no `Cancel`, no `Change`, no `CreateOrder`, no `Submit`. It returns without touching the broker.

3. DO NOT DROP THE NEWER INSTRUCTION. The sync that backs off records that a re-sync is owed (a second bool on the bracket, set under `_lock`). The sync holding the reservation, once its broker work has resolved, clears the reservation and -- if a re-sync is owed -- clears that flag and re-drives the sync so the newer size/price is applied. Bound the re-drive: at most 2 extra passes, then log and stop. Unbounded ping-pong is the order-flood failure mode this codebase has already paid for twice.

   This half is mandatory, not a refinement. The live case was a PARTIAL FILL: the first sync is sized to 1 lot and the second to 2. Backing the second one off and forgetting it leaves a 1-lot stop behind a 2-lot position -- under-cover, which is naked risk on the delta. The acceptance test asserts the surviving stop covers 2.

4. RELEASE THE RESERVATION ON EVERY EXIT PATH. A `try/finally` around everything after the lock is released is the way to make this true by construction rather than by enumeration. The paths that exist today: the flat abort (`BRACKET_ABORTED_FLAT`), the side-mismatch abort (`BRACKET_ABORTED_SIDE`), the successful `Change()` return (`BRACKET_MODIFIED`), the `CreateOrder`-returned-null return (`BRACKET_SUBMIT_FAILED`), the successful submit (`BRACKET_MIRRORED`), and the `catch`.

   A LEAKED RESERVATION IS PERMANENT AND IS WORSE THAN THE DEFECT: every later trigger backs off politely and the follower never gets a stop at all. There is a test for exactly this -- `TestBracket_P1_56_AFailedSubmitDoesNotWedgeLaterSyncs` passes today and must still pass.

5. A SYNC THAT BACKS OFF MUST NOT INCREMENT `bracket.StopAttempts`. It made no attempt. Incrementing it lets a burst of triggers exhaust `MaxBracketStopAttempts`, after which the copier gives up on a position for which no stop was ever actually submitted.

6. STOP CLEARING `bracket.WorkingStop` BEFORE THE BROKER CALL. Leave it holding the previous order until the outcome is known, then reassign it to the new or modified order, or clear it if the attempt failed. The existing `stillLive` / `IsPendingOrWorking` checks already cope with it pointing at a cancelled order, and an honest `WorkingStop` is what makes `OnFollowerOrderUpdate`'s `ReferenceEquals` check meaningful during the window.

7. NO NEW LOCKING AROUND BROKER CALLS. `_lock` must not be held across `Cancel`/`Change`/`CreateOrder`/`Submit` (`P1-10`/`P1-35`). Do NOT add a second lock, a semaphore, `Monitor.TryEnter` with a timeout, `Thread.Sleep`, or a spin-wait to serialise the syncs. A sync that BLOCKS waiting for another one is holding an NT8 event thread, and the acceptance test bounds its wait for precisely this reason and reports the timeout as a failure.

8. THE RESERVATION IS PER BRACKET. No static or engine-wide flag: two different followers, or two instruments on one follower, must still sync independently.

9. KEEP EVERYTHING ELSE INTACT. `P0-50`'s live-position re-read immediately before every broker call and both of its aborts; the `Change()`-first trail path and its `BRACKET_MODIFY_FAILED` fallback to cancel-then-create; sizing from `Math.Min(bracket quantity, live position quantity)`; the `MaxBracketStopAttempts` bound and the rule that a successful `Submit` does NOT reset it; and every existing log event name, because operators and the handover grep for them.

10. `OnFollowerOrderUpdate` IS IN YOUR REGION SET FOR A REASON: it also nulls `WorkingStop` and then calls `SyncFollowerStop`. A terminal OrderUpdate arriving DURING an in-flight sync must still end with the follower protected. It may back off like any other sync, but it must leave a re-sync owed so the re-drive covers it. Do not give it a bypass around the reservation.
## Additional context you must respect
WHAT EXISTS. `FollowerBracket` is a private class with: `RelationshipId`, `FollowerAccountName`, `InstrumentFullName`, `FollowerSide`, `FollowerQuantity`, `FollowerEntryPrice`, `StopOffset`, `WorkingStop`, `StopAttempts`. `MaxBracketStopAttempts` is a private const int = 3. The engine's lock field is `_lock` (NOT `_stateLock` -- the implementer rules name `_stateLock` because that is RiskGuard's; the identical no-broker-calls-under-the-lock rule applies to `_lock` here). `_followerBrackets` is a Dictionary keyed by `BracketKey(followerAccount, instrumentFullName)`. Helpers available: `CopierLog(accountName, eventType, message)`, `RiskGuardAddOn.IsPendingOrWorking(OrderState)`, `RiskGuardAddOn.IsStopType(Order)`.

THE THREE CALLERS of `SyncFollowerStop`, none of whose signatures you may change: `OnLeaderOrderUpdate` (the leader moved or attached its stop), `UpdateFollowerBracketFromPosition` (the follower's own fill or position update; the `P0-55` re-anchor reaches `SyncFollowerStop` through `OnLeaderOrderUpdate`), and `OnFollowerOrderUpdate` (the mirrored stop went terminal). All three already resolve the bracket under `_lock` and pass it in, so the bracket object identity is stable and is the right place to hang the reservation.

OUT OF SCOPE, deliberately. (a) The parked `SyncFollowerTarget` on branch `wip/p09-oco-target` -- it is not in this tree and you must not add it. (b) `ReleaseFollowerBracket` not cancelling an order that a still-in-flight sync is about to create: pre-existing, and `P0-50`'s live-position re-read is what covers the flat case. Do not widen the ticket to either.

BUILD. C# 8.0, and the file must compile for BOTH net48 inside NinjaTrader and the net8.0 `-DTESTING` test build. ASCII only in comments and string literals. `System.Threading` is NOT imported in `TradeCopierEngine.cs`; if you want `Interlocked` or `Volatile`, fully qualify it (`System.Threading.Interlocked`) rather than adding a using -- though a plain bool read and written under `_lock` needs neither.

HOW THE ACCEPTANCE TEST DRIVES IT, so you can reason about what will actually be observed: the follower is long 1 after a partial fill, the leader then attaches a 2-lot stop, and `Account.BrokerCallObserver` fires INSIDE the first sync's `CreateOrder` -- at that instant the lock is released and nothing has been submitted. Parked there, the test drives the follower's PositionUpdate at 2 lots from a second thread. With the defect that produces two live `COPIER_STOP` orders, qty 2 and qty 1. The test asserts exactly one live `COPIER_STOP` and that it covers 2 contracts.
## Regions to rewrite
### REGION id="FollowerBracket"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 893-916
Purpose: add the in-flight reservation and the re-sync-owed flag here
```csharp
        private class FollowerBracket
        {
            public string RelationshipId;
            public string FollowerAccountName;
            public string InstrumentFullName;
            public MarketPosition FollowerSide = MarketPosition.Flat;
            public int FollowerQuantity;
            public double FollowerEntryPrice = double.NaN;   // the anchor; NaN until the follower fills
            // SIGNED offset from the leader's average entry to its stop, in points.
            // Negative = stop below entry, positive = above. NaN until the leader's stop appears.
            // It must stay signed: a leader trailing its stop INTO PROFIT puts the stop above
            // entry on a long, and an absolute distance would mirror that as a loss of the same
            // size on the follower -- turning the leader's locked-in gain into open risk.
            public double StopOffset = double.NaN;
            public Order WorkingStop;                        // the follower's live protective order

            // Bounded re-submission. Raised by review of the first implementation: if Submit
            // threw, or the broker rejected the stop moments later, WorkingStop ended up null
            // with a perfectly valid offset and NOTHING re-triggered submission -- the follower
            // stayed naked for the life of the position. Re-submission fixes that, and the
            // counter is what stops a persistently-rejecting instrument turning it into an
            // order flood (the failure mode P2-46 and the flood cluster already cost us once).
            public int StopAttempts;
        }
```
### REGION id="SyncFollowerStop"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 1090-1266
Purpose: the defect: WorkingStop is nulled under the lock before the broker call and only reassigned after Submit
```csharp
        private void SyncFollowerStop(Account followerAcc, Instrument instrument, FollowerBracket bracket)
        {
            if (followerAcc == null || instrument == null || bracket == null) return;

            Order toCancel = null;
            double stopPrice;
            int qty;
            OrderAction action;
            MarketPosition bracketSide;

            lock (_lock)
            {
                if (double.IsNaN(bracket.FollowerEntryPrice) || double.IsNaN(bracket.StopOffset)) return;
                if (bracket.FollowerQuantity <= 0 || bracket.FollowerSide == MarketPosition.Flat) return;

                // One expression for both sides, because the offset is signed. A long's stop is
                // normally below entry (negative offset) and a short's above (positive), but
                // either can invert once the leader trails into profit -- and that MUST carry
                // through, or the follower is put at risk while the leader is protected.
                stopPrice = bracket.FollowerEntryPrice + bracket.StopOffset;

                if (stopPrice <= 0) return;

                qty = bracket.FollowerQuantity;
                bracketSide = bracket.FollowerSide;
                action = bracket.FollowerSide == MarketPosition.Long ? OrderAction.Sell : OrderAction.BuyToCover;

                if (bracket.WorkingStop != null)
                {
                    bool samePrice = Math.Abs(bracket.WorkingStop.StopPrice - stopPrice) < 1e-9;
                    bool sameQty = bracket.WorkingStop.Quantity == qty;
                    bool stillLive = RiskGuardAddOn.IsPendingOrWorking(bracket.WorkingStop.OrderState);
                    if (stillLive && samePrice && sameQty) return;   // already correct

                    // Cancel-then-replace rather than modify: NT8's Change path is not available
                    // through this seam, and a stale stop left working alongside a new one would
                    // over-cover and flip the follower when both fire.
                    if (stillLive) toCancel = bracket.WorkingStop;
                }
                bracket.WorkingStop = null;

                if (bracket.StopAttempts >= MaxBracketStopAttempts)
                {
                    // Bounded: keep retrying a broker that will not accept the order and the
                    // copier becomes the order flood it was hardened against.
                    return;
                }
                bracket.StopAttempts++;
            }

            // P0-50: re-read the live position immediately before touching the broker.
            //
            // The bracket's view of the follower can be stale by the time we get here -- and on
            // 2026-08-07 it was: three COPIER_STOP orders were submitted against a FLAT Sim-ORB
            // after the trade had closed, each cancelling the last. **An orphan stop on a flat
            // account is not a leftover, it is a new position in the opposite direction the
            // moment it triggers.** Same discipline as T2's auto-stop, which re-sizes from the
            // live position immediately before CreateOrder for exactly this reason.
            var livePos = followerAcc.Positions.FirstOrDefault(p =>
                p.Instrument != null &&
                p.Instrument.FullName.Equals(instrument.FullName, StringComparison.OrdinalIgnoreCase));

            if (livePos == null || livePos.MarketPosition == MarketPosition.Flat || livePos.Quantity <= 0)
            {
                lock (_lock) { bracket.FollowerQuantity = 0; bracket.FollowerSide = MarketPosition.Flat; }
                if (toCancel != null)
                {
                    try { followerAcc.Cancel(new[] { toCancel }); } catch { }
                }
                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] BRACKET_ABORTED_FLAT: {followerAcc.Name} {instrument.FullName} went flat before the mirrored stop was submitted; no stop placed.",
                    PrintTo.OutputTab1);
                return;
            }

            if (livePos.MarketPosition != bracketSide)
            {
                lock (_lock) { bracket.FollowerQuantity = 0; bracket.FollowerSide = MarketPosition.Flat; }
                if (toCancel != null)
                {
                    try { followerAcc.Cancel(new[] { toCancel }); } catch { }
                }
                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] BRACKET_ABORTED_SIDE: {followerAcc.Name} {instrument.FullName} is {livePos.MarketPosition} but the bracket was built for {bracketSide}; no stop placed.",
                    PrintTo.OutputTab1);
                return;
            }

            try
            {
                // Outside the lock: Cancel/Change/CreateOrder/Submit are broker calls, and holding
                // _lock across them is the P1-10/P1-35 violation.

                // Size from the live position, not the bracket's snapshot: a follower that
                // scaled out between the decision and here would otherwise get a stop larger
                // than the position, which flips it on trigger.
                int liveQty = Math.Min(qty, livePos.Quantity);

                // A leader trailing its stop is the ordinary case, and cancel-then-create left the
                // follower unprotected on EVERY trail step, between the cancel and the new order's
                // acceptance. Modify the working order instead: one order, no window.
                //
                // The original P0-9 note said "cancel-then-replace, not modify", to stop a stale
                // stop working beside a new one -- that over-covers and flips the follower when
                // both fire. Change() cannot produce that state: there is only ever one order.
                // Verified available: the connection serving every account here advertises the
                // OrderChange feature (/api/connections). Any failure falls through to the
                // cancel-then-create path below, so an unsupporting connection degrades rather
                // than breaks.
                if (toCancel != null
                    && RiskGuardAddOn.IsPendingOrWorking(toCancel.OrderState)
                    && toCancel.OrderType == OrderType.StopMarket
                    && toCancel.OrderAction == action)
                {
                    try
                    {
                        toCancel.StopPrice = stopPrice;
                        toCancel.Quantity = liveQty;
                        followerAcc.Change(new[] { toCancel });

                        lock (_lock) { bracket.WorkingStop = toCancel; }

                        CopierLog(followerAcc.Name, "BRACKET_MODIFIED",
                            $"{instrument.FullName} stop moved to {liveQty}@{stopPrice} in place "
                            + $"(leader offset {bracket.StopOffset:+0.##;-0.##}, follower entry {bracket.FollowerEntryPrice}); "
                            + "no cancel/replace, so no unprotected window.");
                        return;
                    }
                    catch (Exception cex)
                    {
                        CopierLog(followerAcc.Name, "BRACKET_MODIFY_FAILED",
                            $"{instrument.FullName}: {cex.Message}. Falling back to cancel-then-create.");
                        // fall through
                    }
                }

                if (toCancel != null) followerAcc.Cancel(new[] { toCancel });

                Order stop = followerAcc.CreateOrder(
                    instrument, action, OrderType.StopMarket, TimeInForce.Day,
                    liveQty, 0, stopPrice, "", "COPIER_STOP", null);

                if (stop == null)
                {
                    NinjaTrader.Code.Output.Process(
                        $"[CopierEngine] BRACKET_SUBMIT_FAILED on {followerAcc.Name} {instrument.FullName}: CreateOrder returned null. The follower is UNPROTECTED.",
                        PrintTo.OutputTab1);
                    return;
                }
                followerAcc.Submit(new[] { stop });

                // Deliberately does NOT reset StopAttempts. The failure this bound exists for is a
                // broker that ACCEPTS the submit and rejects the order a moment later, so
                // "Submit did not throw" is not evidence of protection and resetting here makes
                // the bound unreachable. The budget is refreshed only by a genuinely new
                // instruction from the leader, or by the bracket being released when the follower
                // goes flat. (Caught by this test failing at 21 submissions.)
                lock (_lock) { bracket.WorkingStop = stop; }

                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] BRACKET_MIRRORED: {followerAcc.Name} {instrument.FullName} stop {liveQty}@{stopPrice} (leader offset {bracket.StopOffset:+0.##;-0.##}, follower entry {bracket.FollowerEntryPrice}).",
                    PrintTo.OutputTab1);
            }
            catch (Exception ex)
            {
                int attempts;
                lock (_lock) { attempts = bracket.StopAttempts; }
                bool exhausted = attempts >= MaxBracketStopAttempts;
                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] BRACKET_SUBMIT_FAILED on {followerAcc.Name} {instrument.FullName} "
                    + $"(attempt {attempts}/{MaxBracketStopAttempts}): {ex.Message}. The follower is UNPROTECTED"
                    + (exhausted
                        ? " and the copier has GIVEN UP on this position -- RiskGuard's auto-stop is the only remaining cover, and only if it is armed and live."
                        : "; it will retry on the next leader stop update or follower fill."),
                    PrintTo.OutputTab1);
            }
        }
```
### REGION id="OnFollowerOrderUpdate"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 850-870
Purpose: also nulls WorkingStop, then re-drives the sync; must interact correctly with the reservation
```csharp
        private void OnFollowerOrderUpdate(Account followerAcc, Order order)
        {
            if (followerAcc == null || order == null || order.Instrument == null) return;
            if (RiskGuardAddOn.IsPendingOrWorking(order.OrderState)) return;   // still live
            if (order.OrderState == OrderState.Filled) return;                 // it did its job

            string key = BracketKey(followerAcc.Name, order.Instrument.FullName);
            FollowerBracket bracket;
            lock (_lock)
            {
                if (!_followerBrackets.TryGetValue(key, out bracket)) return;
                if (!ReferenceEquals(bracket.WorkingStop, order)) return;      // not our stop
                bracket.WorkingStop = null;
            }

            NinjaTrader.Code.Output.Process(
                $"[CopierEngine] BRACKET_STOP_LOST: {followerAcc.Name} {order.Instrument.FullName} mirrored stop went {order.OrderState}; re-submitting.",
                PrintTo.OutputTab1);

            SyncFollowerStop(followerAcc, order.Instrument, bracket);
        }
```
Return one block per region id above, in the same order. No other output.

## ORCHESTRATOR DIRECTIVE (overrides the reviewer if they conflict)
A previous round of this ticket produced a candidate that was correct in almost every respect: an
in-flight reservation on the bracket (`StopInFlight`), a re-sync-owed flag (`StopResyncOwed`),
removal of the eager `bracket.WorkingStop = null`, release in a `finally`, and no new locking around
broker calls. Reproduce all of that. It failed review on ONE point, and this directive settles both
the point and its fix.

THE DEFECT IN THAT CANDIDATE. Its `finally` cleared `StopInFlight` and only THEN called
`SyncFollowerStop` again (recursively) to service the owed re-sync. Between the `finally` releasing
`_lock` and the re-drive re-acquiring it, no reservation is published, so a third sync can enter and
proceed to the broker. Close that window.

THE FIX THE REVIEWERS PROPOSED IS WRONG AND YOU MUST NOT IMPLEMENT IT. They proposed "do not clear
`StopInFlight` in the `finally` when a re-sync is owed, and let the re-drive's own `finally` clear
it". The re-drive's FIRST act is to test `StopInFlight` and back off, so it would return immediately
without ever reaching a `finally`, and the reservation would be leaked FOREVER: every later trigger
backs off politely and that follower can never be given another protective stop for the life of the
position. That is the permanent wedge this ticket's own spec calls worse than the original defect.

WHAT TO IMPLEMENT INSTEAD -- take the reservation ONCE and hold it across every pass:

1. Split the work in two. `SyncFollowerStop(Account, Instrument, FollowerBracket)` KEEPS ITS
   SIGNATURE -- all three callers depend on it -- and becomes the reservation HOLDER. A new private
   helper, `SyncFollowerStopOnce`, carries the existing body: the validation, the `P0-50` live
   position re-read, the two aborts, the `Change()`-first trail path with its
   `BRACKET_MODIFY_FAILED` fallback, `CreateOrder`/`Submit`, the `WorkingStop` assignments, and the
   `catch`. The helper MUST NOT read, set or clear `StopInFlight` or `StopResyncOwed`.

2. The holder does exactly this. Acquire `_lock`; if `bracket.StopInFlight` is already true, set
   `bracket.StopResyncOwed = true` and return WITHOUT any broker call and WITHOUT touching
   `StopAttempts`; otherwise set `bracket.StopInFlight = true`, then release the lock. Then, inside
   a `try` whose `finally` clears `StopInFlight` under `_lock` exactly once, run a BOUNDED LOOP:
   call `SyncFollowerStopOnce`, then under `_lock` read and clear `StopResyncOwed`; if it was not
   set, stop; if it was, run another pass. At most 2 extra passes, after which log
   `BRACKET_RESYNC_BOUND` naming the account and instrument and stop.

3. Properties this must have, and which are the whole point of the shape:
   - the reservation is published before the FIRST broker call and released exactly once, on every
     exit path including an exception;
   - an early `return` inside `SyncFollowerStopOnce` ends that PASS, never the reservation, so no
     early return can leak it;
   - there is no instant between passes at which a third sync sees no reservation;
   - there is NO recursion -- the re-drive is a loop iteration on the same stack frame.

4. Everything else from the previous candidate stands and must not be undone: do not restore the
   eager `bracket.WorkingStop = null` before the broker call; do not restore
   `bracket.WorkingStop = null` in `OnFollowerOrderUpdate`; keep every existing log event name.

FOR REVIEWERS, SETTLED -- do not raise these again. (a) Removing `bracket.WorkingStop = null` from
`OnFollowerOrderUpdate` is deliberate: an honest `WorkingStop` is what makes the `ReferenceEquals`
guard meaningful during an in-flight sync, and it is also what stops an entering sync creating a
SECOND stop rather than modifying the existing one. (b) A missing test is a coverage gap to report,
not a reason to reject a patch, and the acceptance tests are protected files the implementer cannot
reach. (c) Do not propose serialising syncs with a lock, semaphore, `Monitor.TryEnter` with a
timeout, `Thread.Sleep` or a spin-wait: a sync that BLOCKS waiting for another one holds an NT8
event thread.