# TICKET T1: P0-1 + P0-4: re-arm grace on every loss of full coverage; make the auto-stop delta-sized

## Defect
Two related naked-position defects in the stop-guard FSM.

P0-1: When the recognised protective stop goes terminal (Cancelled / Rejected / Filled) while the position is still open, UpdateFsmOnOrder sets State back to Unprotected but does NOT arm a new GraceTimer. The original one-shot timer was already disposed when the FSM first left Unprotected. EvaluateGraceExpiry is only reachable from OnGraceExpired, which is only called from a GraceTimer callback. FsmWatchdog merely logs. Net effect: cancel a stop under an open position and it stays unprotected for the rest of the session while FSM_WATCHDOG logs every sweep, forever.

P0-4: A same-side quantity update (scale-in) updates PositionQuantity in place and preserves Protected / ProtectedPending. Nothing compares the recognised stop's Quantity to PositionQuantity, so scaling 1 -> 5 contracts behind a 1-lot stop still reports fully protected.

## Required change
This ticket introduces an explicit coverage model. Implement it exactly as specified - the state machine semantics below are decided, not open for redesign.

A. NEW FIELDS on PositionGuardFsm. Do NOT add new GuardFsmState values - the enum already has Unprotected/ProtectedPending/Protected/FlattenPending/Flat and existing tests assert on them:
   public int CoveredQuantity  - quantity of the single RecognizedStopOrder. This tracker follows ONE stop order; do NOT invent multi-stop aggregation.
   public bool GracePending    - a one-shot grace timer is currently armed.
   public bool GraceEmitted    - a grace action has been emitted and its outcome is still pending. This is the anti-duplicate latch.

B. NEW HELPER, exactly this signature:
     private void ArmGraceTimer(PositionGuardFsm fsm, Account account, string instrument, int delayMs)
   - MUST only be called with _stateLock already held; state that in a comment.
   - Disposes any existing fsm.GraceTimer, then assigns the new one.
   - Sets fsm.GraceDeadline = DateTime.UtcNow.AddMilliseconds(delayMs) and fsm.GracePending = true.
   - Reproduces the existing dispatcher-marshalling shape currently inlined in UpdateFsmOnPosition and SeedFsmsForExistingPositions (the '#if TESTING / dispatcher.InvokeAsync / else' block), one-shot (Timeout.Infinite period).
   - The callback MUST NOT null or dispose fsm.GraceTimer and MUST NOT touch FSM fields. Ownership of GracePending belongs to EvaluateGraceExpiry, which already takes _stateLock. Nulling the field from the callback races with a concurrent re-arm and orphans a live timer.
   - Replace BOTH existing inline timer-arming sites with calls to this helper.

C. UpdateFsmOnOrder:
   - When a protective stop is recognised (Working, or Submitted/Accepted/Initialized/PartFilled): set CoveredQuantity = order.Quantity and clear GraceEmitted (a real stop arrived, so a later grace cycle is allowed). If CoveredQuantity >= fsm.PositionQuantity, dispose the grace timer and clear GracePending - full coverage, nothing pending.
   - When the recognised stop goes terminal while fsm.PositionQuantity > 0: State = Unprotected, RecognizedStopOrder = null, AutoStopOrder = null, CoveredQuantity = 0, GraceEmitted = false, and re-arm via ArmGraceTimer(..., _config.StopGuard.StopAttachSeconds * 1000) but ONLY when !fsm.GracePending, so repeated identical OrderUpdates cannot stack timers.

D. UpdateFsmOnPosition:
   - Flip or flat->nonflat recreation: BEFORE overwriting _guardFsms[key], dispose the OUTGOING fsm.GraceTimer. Leaving it running lets a stale callback attach a stop using the old side/quantity.
   - Same-side quantity update (scale-in/out): after updating PositionQuantity, if the FSM is Protected or ProtectedPending and CoveredQuantity < PositionQuantity, log FSM_UNDERCOVERED with both quantities, clear GraceEmitted, and arm the grace timer when !GracePending. Do NOT change State and do NOT emit orders here.

E. EvaluateGraceExpiry - make it coverage-aware and delta-sized. It already holds _stateLock:
   - Set fsm.GracePending = false at the top (the timer that woke us has fired).
   - Return no actions if fsm.GraceEmitted is already true.
   - Proceed when the position is non-flat AND now >= GraceDeadline AND either State == Unprotected OR CoveredQuantity < pos.Quantity. Today it returns early unless State == Unprotected, which would make the scale-in fix in D dead code.
   - CRITICAL: size the emitted action to the UNCOVERED DELTA. int uncovered = pos.Quantity - Math.Max(0, fsm.CoveredQuantity); return no actions if uncovered <= 0; set Quantity = uncovered on the GuardAction. Emitting pos.Quantity while a partial stop is already working would over-cover the position and flip it to the opposite side when the stops trigger.
   - Set fsm.GraceEmitted = true when an action is emitted.
   - Keep the existing OnMissing 'AutoStop' / 'Flatten' branches, the RuleIds MISSING_STOP_ATTACH / MISSING_STOP_FLATTEN, and the existing state transitions for the Unprotected case. For the under-covered case where State is already Protected/ProtectedPending, do NOT downgrade State - GraceEmitted is the latch there.

F. FsmWatchdog - promote from log-only to remediation, but it is called from INSIDE lock (_stateLock) in ExecuteSafetySweep, so it may ONLY inspect FSM state, log, and arm timers. It must NOT call ProcessAction, EvaluateGraceExpiry, or any Account API other than resolving an Account reference from Account.All:
   - For any FSM that is (Unprotected OR CoveredQuantity < PositionQuantity), is past GraceDeadline plus a 2 second margin, and has !GracePending: arm the grace timer with a small positive delay of 250 ms - NOT 0 - so the sweep releases _stateLock before the callback needs it.
   - Dedupe to once per naked episode with a new private ConcurrentDictionary<string, DateTime> _watchdogFired keyed by FsmKey. Remove the key whenever the FSM regains full coverage or is torn down.
   - Keep the existing FSM_WATCHDOG log line unchanged.

## Additional context you must respect
HARD REQUIREMENT: the patch must COMPILE. You may only reference members that already exist in the file or that you define inside the regions you are given. Do not assume a helper, field, queue, or changed method signature exists elsewhere - if you need it, define it inside one of your returned regions. Do not change the signature of any method whose callers are outside your regions: EvaluateGraceExpiry is called from OnGraceExpired, and FsmWatchdog is called from ExecuteSafetySweep with no arguments.

PositionGuardFsm currently has: State, AccountName, Instrument, PositionSide, PositionQuantity, RecognizedStopOrder, AutoStopOrder, EntryOcoId, EntryTime, GraceDeadline, LastTransitionTime, GraceTimer. Existing helpers you may call: FsmKey(accountName, instrument), IsStopType(order), IsTerminal(orderState), IsProtectiveSide(order, positionSide), LogEvent(account, eventType, message). _config.StopGuard.StopAttachSeconds is an int in seconds; _config.StopGuard.OnMissing is a string. The file already has 'using System.Collections.Concurrent;' and 'using System.Linq;' - do not add or remove usings. You may add private fields inside any region you return.

## Regions to rewrite

### REGION id="PositionGuardFsm"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 3167-3193
Purpose: add CoveredQuantity, GracePending, GraceEmitted
```csharp
    public class PositionGuardFsm
    {
        public string AccountName { get; }
        public string Instrument { get; }
        public GuardFsmState State { get; set; } = GuardFsmState.Unprotected;
        public MarketPosition PositionSide { get; set; } = MarketPosition.Flat;
        public int PositionQuantity { get; set; }
        // NOTE: NT8 Order.OrderId is NOT unique and can change over the order's
        // lifetime (historical->live transition). Track recognised stops by the
        // Order object reference, not by id string. See RiskGuardAddOn.md -6.6.
        public Order RecognizedStopOrder { get; set; }
        public Order AutoStopOrder { get; set; }
        public string EntryOcoId { get; set; }   // best-effort join key; may be empty for external brackets
        public DateTime EntryTime { get; set; } = DateTime.MinValue;
        public DateTime GraceDeadline { get; set; } = DateTime.MinValue;
        public DateTime LastTransitionTime { get; set; } = DateTime.UtcNow;
        // One-shot grace timer: fires exactly at EntryTime + StopGuard.StopAttachSeconds.
        // Cancelled when the FSM reaches Protected or Flat. This replaces the sweep
        // polling of GraceDeadline with an instant event-driven trigger.
        public Timer GraceTimer { get; set; }

        public PositionGuardFsm(string accountName, string instrument)
        {
            AccountName = accountName;
            Instrument = instrument;
        }
    }
```

### REGION id="SeedFsms"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 451-521
Purpose: use the new arming helper; behaviour unchanged
```csharp
        private void SeedFsmsForExistingPositions(Account account)
        {
            if (account == null) return;
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;

            try
            {
                foreach (Position pos in account.Positions)
                {
                    if (pos == null || pos.MarketPosition == MarketPosition.Flat || pos.Quantity <= 0) continue;
                    string instrument = pos.Instrument != null ? pos.Instrument.FullName : null;
                    if (string.IsNullOrEmpty(instrument)) continue;

                    string key = FsmKey(account.Name, instrument);
                    if (_guardFsms.ContainsKey(key)) continue; // already tracked

                    var fsm = new PositionGuardFsm(account.Name, instrument)
                    {
                        PositionSide = pos.MarketPosition,
                        PositionQuantity = pos.Quantity,
                        EntryTime = DateTime.UtcNow,
                        State = GuardFsmState.Unprotected
                    };
                    fsm.GraceDeadline = fsm.EntryTime.AddSeconds(_config.StopGuard.StopAttachSeconds);

                    // Scan existing working orders for a protective stop on the opposite side.
                    // If found, seed the FSM as Protected (or ProtectedPending) so the grace
                    // timer does not place a duplicate auto-stop on an already-covered position.
                    foreach (Order o in account.Orders)
                    {
                        if (o == null || o.Instrument == null) continue;
                        if (!string.Equals(o.Instrument.FullName, instrument, StringComparison.OrdinalIgnoreCase)) continue;
                        if (!IsStopType(o) || !IsProtectiveSide(o, pos.MarketPosition)) continue;
                        if (IsTerminal(o.OrderState)) continue;
                        fsm.RecognizedStopOrder = o;
                        fsm.State = o.OrderState == OrderState.Working
                            ? GuardFsmState.Protected
                            : GuardFsmState.ProtectedPending;
                        break;
                    }

                    // Arm a one-shot grace timer only if still Unprotected (no existing stop found).
                    if (fsm.State == GuardFsmState.Unprotected && _config.StopGuard.StopAttachSeconds > 0)
                    {
                        int graceMs = _config.StopGuard.StopAttachSeconds * 1000;
                        var capturedAccount = account;
                        var capturedInstrument = instrument;
                        fsm.GraceTimer = new Timer(_ =>
                        {
#if TESTING
                            OnGraceExpired(capturedAccount, capturedInstrument);
#else
                            var dispatcher = Application.Current?.Dispatcher;
                            if (dispatcher != null)
                                dispatcher.InvokeAsync(() => OnGraceExpired(capturedAccount, capturedInstrument));
                            else
                                OnGraceExpired(capturedAccount, capturedInstrument);
#endif
                        }, null, graceMs, Timeout.Infinite);
                    }

                    _guardFsms[key] = fsm;
                    LogEvent(account.Name, "FSM_SEED",
                        $"Seeded FSM for existing position {key} -> {fsm.State} (qty {fsm.PositionQuantity})");
                }
            }
            catch (Exception ex)
            {
                LogEvent(account.Name, "ERROR", "SeedFsmsForExistingPositions failed: " + ex.Message);
            }
        }
```

### REGION id="UpdateFsmOnPosition"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1544-1628
Purpose: dispose outgoing timer on flip; under-coverage detection; define ArmGraceTimer here
```csharp
        private void UpdateFsmOnPosition(Account account, string instrument, MarketPosition newPos, int qty)
        {
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;
            if (!_isArmed) return;

            string key = FsmKey(account.Name, instrument);
            bool isNonFlat = newPos != MarketPosition.Flat && qty > 0;

            if (isNonFlat)
            {
                // Check if an FSM already exists for this (account, instrument).
                if (_guardFsms.TryGetValue(key, out var existingFsm) && existingFsm.PositionSide == newPos)
                {
                    // Same-side qty-only update (partial fill, scale-out/in):
                    // update qty in place, preserving Protected/ProtectedPending state
                    // and the recognized stop order. Do NOT recreate the FSM.
                    existingFsm.PositionQuantity = qty;
                    LogEvent(account.Name, "FSM_UPDATE",
                        $"{key}: qty updated to {qty} (state stays {existingFsm.State})");
                    return;
                }

                // flat->nonflat or flip: (re)create FSM, arm grace, consume pending stop
                var fsm = new PositionGuardFsm(account.Name, instrument)
                {
                    PositionSide = newPos,
                    PositionQuantity = qty,
                    EntryTime = DateTime.UtcNow,
                    State = GuardFsmState.Unprotected
                };
                fsm.GraceDeadline = fsm.EntryTime.AddSeconds(_config.StopGuard.StopAttachSeconds);

                // Consume a buffered stop that arrived before the position event
                if (_pendingStops.TryGetValue(key, out var pending) && pending != null)
                {
                    if (IsProtectiveSide(pending, newPos) && IsStopType(pending) && !IsTerminal(pending.OrderState))
                    {
                        fsm.RecognizedStopOrder = pending;
                        fsm.State = pending.OrderState == OrderState.Working
                            ? GuardFsmState.Protected
                            : GuardFsmState.ProtectedPending;
                    }
                    _pendingStops.Remove(key);
                }

                // Arm a one-shot grace timer that fires at the exact grace deadline.
                // This replaces the sweep polling of GraceDeadline with an instant trigger.
                if (fsm.State == GuardFsmState.Unprotected && _config.StopGuard.StopAttachSeconds > 0)
                {
                    int graceMs = _config.StopGuard.StopAttachSeconds * 1000;
                    fsm.GraceTimer = new Timer(_ =>
                    {
#if TESTING
                        OnGraceExpired(account, instrument);
#else
                        var dispatcher = Application.Current?.Dispatcher;
                        if (dispatcher != null)
                            dispatcher.InvokeAsync(() => OnGraceExpired(account, instrument));
                        else
                            OnGraceExpired(account, instrument);
#endif
                    }, null, graceMs, Timeout.Infinite);
                }

                _guardFsms[key] = fsm;
                LogEvent(account.Name, "FSM_TRANSITION",
                    $"Created FSM {key} -> {fsm.State} (grace deadline {fsm.GraceDeadline:HH:mm:ss})");
            }
            else
            {
                // nonflat->flat: tear down, cancel grace timer, cancel orphan auto-stop
                if (_guardFsms.TryGetValue(key, out var fsm))
                {
                    fsm.GraceTimer?.Dispose();
                    if (fsm.AutoStopOrder != null && !IsTerminal(fsm.AutoStopOrder.OrderState))
                    {
                        try { account.Cancel(new[] { fsm.AutoStopOrder }); }
                        catch (Exception cex) { LogEvent(account.Name, "FSM_AUTOSTOP_CANCEL_FAIL", cex.Message); }
                    }
                    _guardFsms.Remove(key);
                    LogEvent(account.Name, "FSM_TRANSITION", $"Tore down FSM {key} -> Flat");
                }
                _pendingStops.Remove(key);
            }
        }
```

### REGION id="UpdateFsmOnOrder"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1642-1706
Purpose: re-arm on every Unprotected transition; maintain CoveredQuantity
```csharp
        private void UpdateFsmOnOrder(Account account, string instrument, Order order)
        {
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;
            if (!_isArmed) return;
            if (order?.Instrument == null) return;

            string key = FsmKey(account.Name, instrument);

            // If no FSM yet, buffer protective-side stops pending the position event.
            if (!_guardFsms.ContainsKey(key))
            {
                if (IsStopType(order) && !IsTerminal(order.OrderState))
                {
                    // We don't know the position side yet; buffer and classify on consumption.
                    _pendingStops[key] = order;
                }
                return;
            }

            var fsm = _guardFsms[key];
            var prev = fsm.State;

            // Recognise a protective stop for the current position side.
            if (IsProtectiveSide(order, fsm.PositionSide) && IsStopType(order))
            {
                if (IsTerminal(order.OrderState))
                {
                    // The recognised stop filled/cancelled while position still open
                    if (fsm.PositionQuantity > 0)
                    {
                        fsm.State = GuardFsmState.Unprotected;
                        fsm.RecognizedStopOrder = null;
                        fsm.AutoStopOrder = null;
                        LogEvent(account.Name, "FSM_TRANSITION",
                            $"{key}: stop {order.Name} terminal ({order.OrderState}) -> Unprotected");
                    }
                }
                else if (order.OrderState == OrderState.Working)
                {
                    fsm.RecognizedStopOrder = order;
                    fsm.State = GuardFsmState.Protected;
                    if (order.Name == "RiskGuardAutoStop") fsm.AutoStopOrder = order;
                    LogEvent(account.Name, "FSM_TRANSITION",
                        $"{key}: stop {order.Name} Working -> Protected");
                }
                else // Submitted/Accepted/Initialized/PartFilled
                {
                    fsm.RecognizedStopOrder = order;
                    fsm.State = GuardFsmState.ProtectedPending;
                    LogEvent(account.Name, "FSM_TRANSITION",
                        $"{key}: stop {order.Name} {order.OrderState} -> ProtectedPending");
                }
            }

            if (prev != fsm.State)
            {
                fsm.LastTransitionTime = DateTime.UtcNow;
                // Cancel the grace timer when the FSM leaves Unprotected
                if (fsm.State != GuardFsmState.Unprotected)
                {
                    fsm.GraceTimer?.Dispose();
                    fsm.GraceTimer = null;
                }
            }
        }
```

### REGION id="EvaluateGraceExpiry"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1711-1760
Purpose: coverage-aware entry condition, delta-sized action, GraceEmitted latch
```csharp
        internal List<GuardAction> EvaluateGraceExpiry(Account account, string instrument)
        {
            var actions = new List<GuardAction>();
            lock (_stateLock)
            {
                if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return actions;
                if (!_isArmed) return actions;

                string key = FsmKey(account.Name, instrument);
                if (!_guardFsms.TryGetValue(key, out var fsm)) return actions;
                if (fsm.State != GuardFsmState.Unprotected) return actions;
                if (DateTime.UtcNow < fsm.GraceDeadline) return actions;

                // Position still open and still unprotected past the deadline.
                var pos = account.Positions.FirstOrDefault(p => p.Instrument.FullName == instrument);
                if (pos == null || pos.MarketPosition == MarketPosition.Flat) return actions;

                if (_config.StopGuard.OnMissing == "AutoStop")
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = account.Name,
                        ActionType = GuardActionType.PlaceStopOrder,
                        Instrument = instrument,
                        InstrumentObj = pos.Instrument,
                        Quantity = pos.Quantity,
                        RuleId = "MISSING_STOP_ATTACH"
                    });
                    // Mark as pending-protection so a duplicate event/sweep does not re-emit.
                    fsm.State = GuardFsmState.ProtectedPending;
                }
                else if (_config.StopGuard.OnMissing == "Flatten")
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = account.Name,
                        ActionType = GuardActionType.FlattenPosition,
                        Instrument = instrument,
                        InstrumentObj = pos.Instrument,
                        Quantity = pos.Quantity,
                        RuleId = "MISSING_STOP_FLATTEN"
                    });
                    // Transition to a non-Unprotected state so a duplicate call
                    // does not re-emit. We use a new transitional state
                    // FlattenPending to distinguish from ProtectedPending.
                    fsm.State = GuardFsmState.FlattenPending;
                }
            }
            return actions;
        }
```

### REGION id="FsmWatchdog"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1763-1776
Purpose: lock-safe remediation via timer arming + once-per-episode dedupe
```csharp
        private void FsmWatchdog()
        {
            foreach (var kv in _guardFsms)
            {
                var fsm = kv.Value;
                if (fsm.State == GuardFsmState.Unprotected &&
                    DateTime.UtcNow > fsm.GraceDeadline.AddSeconds(2))
                {
                    LogEvent(fsm.AccountName, "FSM_WATCHDOG",
                        $"{fsm.Instrument}: Unprotected past grace deadline by " +
                        $"{(DateTime.UtcNow - fsm.GraceDeadline).TotalSeconds:F1}s");
                }
            }
        }
```

Return one block per region id above, in the same order. No other output.

## ORCHESTRATOR DIRECTIVE (overrides the reviewer if they conflict)
Start from YOUR OWN round-1 answer (the one that compiled cleanly) and apply ONLY the changes below.
Do not restructure anything else. Two of your later attempts broke the build; keep the diff small.

(1) DELETE the _watchdogFired dictionary completely - every declaration and every TryAdd/TryRemove
call. Do not add any static field, and do not widen the access modifier of any PositionGuardFsm
member. A static collection on a per-position data record is shared by every AddOn instance in the
process; RiskGuardAddOnTests.cs constructs a fresh RiskGuardAddOn per test, so process-static state
leaks a naked-episode key from one test into the next and silently suppresses watchdog remediation
there. It is also why you needed a fully-qualified System.Collections.Concurrent name: the
`using System.Collections.Concurrent;` in this file sits inside the `#if !TESTING` branch and is not
in scope for the test build.

The dedupe already exists on the FSM. In FsmWatchdog, arm the grace timer only when:

    !fsm.GracePending && !fsm.GraceEmitted

ArmGraceTimer sets GracePending = true; EvaluateGraceExpiry clears GracePending and sets
GraceEmitted = true when it emits; GraceEmitted is cleared exactly where coverage changes. So that
condition already means "this naked episode has no timer armed and no action outstanding" - once per
episode, scoped to the FSM lifetime, nothing to clean up on teardown.

(2) In UpdateFsmOnOrder, guard the terminal-stop branch with REFERENCE EQUALITY so an unrelated
stop's cancellation cannot wipe live coverage:
  - Only treat a terminal order as losing coverage when object.ReferenceEquals(order,
    fsm.RecognizedStopOrder). If a different protective stop goes terminal, leave State,
    CoveredQuantity, RecognizedStopOrder and AutoStopOrder untouched.
  - Only null fsm.AutoStopOrder when object.ReferenceEquals(order, fsm.AutoStopOrder).
Failure this closes: a working 5-lot RiskGuardAutoStop plus a separate manual stop that gets
cancelled currently wipes coverage to 0 and re-arms grace, so a second full-size stop is attached on
top of the live auto-stop - 10 lots of protection on a 5-lot position, which flips it short.

(3) In UpdateFsmOnOrder, coverage may only be REPLACED BY AN EQUAL OR LARGER stop while the tracked
stop is still live. In the non-terminal recognition branches, only assign RecognizedStopOrder and
CoveredQuantity when any of these hold:
      fsm.RecognizedStopOrder == null
   || object.ReferenceEquals(order, fsm.RecognizedStopOrder)
   || IsTerminal(fsm.RecognizedStopOrder.OrderState)
   || order.Quantity >= fsm.CoveredQuantity
Otherwise ignore the order for coverage purposes (a LogEvent is fine). Failure this closes: a 1-lot
manual stop arriving under a live 5-lot auto-stop currently overwrites CoveredQuantity to 1, so a
4-lot delta stop is emitted on top - again over-covering and flipping the position.

(4) Do NOT cancel the outgoing AutoStopOrder on a flip or FSM recreation. Dispose the outgoing
GraceTimer only, exactly as you already do. account.Cancel is a broker call and this code path runs
with _stateLock held; adding one here would deepen an existing lock-discipline defect that is
tracked separately (P1-30) and fixed by moving all orphan cancellation off-lock. Leave it alone.

(5) The review claim that SeedFsmsForExistingPositions calls ArmGraceTimer without holding
_stateLock is a FALSE POSITIVE - its only caller, SubscribeToAccount, is invoked from inside
lock (_stateLock) at both call sites (InitializeRiskGuard and OnConnectionStatusUpdate). Do NOT add
a lock there and do NOT restructure SeedFsmsForExistingPositions.

(6) Ignore any review finding that asks you to aggregate coverage across multiple stop orders. That
is deliberately out of scope for this ticket and is tracked separately; items (2) and (3) are the
bounded mitigation we want instead.