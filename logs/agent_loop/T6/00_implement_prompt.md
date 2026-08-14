# TICKET T6: P0-51: shadow mode must restrain the lockout sweep AND the deferred cancel queue
## Defect
RiskGuard has TWO paths out of a lockout and only one is mode-gated.

(1) EvaluateLockoutPhase emits a FlattenPosition GuardAction. It goes through ProcessAction's mode gate, which correctly logs '[SHADOW] Would execute action FlattenPosition triggered by LOCKOUT_FLATTEN' and returns 'SHADOW (SKIPPED)'. This path is CORRECT and must not be changed.

(2) The lockout watchdog block inside ExecuteSafetySweep separately builds cancelBatches, deferredCancelBatches and flattenBatches, and after releasing _stateLock calls account.Cancel(...) and account.Flatten(...) DIRECTLY. There is no _mode check anywhere in that block. This path is the defect.

Both fire on the same lockout. The guard announces it is only observing and flattens the account anyway.

Observed live 2026-08-09 21:15:25 ET: Sim101, SimCopyTest1 and SimCopy2 each logged the [SHADOW] line and were each really flattened a moment later -- market Sell 2 named 'Close', which is the name Account.Flatten() gives its close order. Sim-ORB, the only account that had NOT tripped the lockout, was untouched, which is what rules out a manual operator flatten.

This is P0 because Phase A's entire premise is that shadow is a safe place to observe a guard that is not yet trusted. RiskGuardAddOn.cs prints 'it observes and logs; it cannot act outside live' on every startup. That statement is false for every lockout rule.
## Required change
1. Introduce ONE predicate that answers 'may I touch the broker right now', and route BOTH existing callers through it. ProcessAction currently computes this inline as `isLive = _mode == "live" || forceLive;`. Extract that into a single private/internal helper -- suggested shape:

     internal bool IsActingMode(bool forceLive = false)

   Have ProcessAction call it INSTEAD of its inline expression, so its behaviour is bit-for-bit unchanged, and have the lockout sweep call it too. The point of the ticket is that there is exactly one place where this question is answered; two copies would drift, and the sweep's copy is the one that would silently stop being checked.

2. In the lockout watchdog execution block (the code after the '---- lock released: everything below may talk to the broker ----' comment), do not issue ANY broker call when IsActingMode() is false. That covers all three batches: cancelBatches, flattenBatches, and deferredCancelBatches. No Cancel, no Flatten, no CreateOrder, no Submit.

3. Shadow must stay INFORMATIVE. When the sweep skips because of the mode, log what it would have done, using LogEvent with an event type that makes the skip obvious (for example 'LOCKOUT_SWEEP_SHADOW') and naming the account, the instruments it would have flattened and the number of orders it would have cancelled. A shadow run that logs nothing is a regression in observability.

4. Do not log the same skip on every 5-second sweep tick forever. Log it when the lockout phase changes, or at most once per account per lockout, whatever is simplest to reason about. Unbounded repetition is what P1-40 looked like in the live log and it makes the output useless.

5. Preserve the two invariants this block already keeps, both of which are separately tested:
   - P1-10/P1-35: broker calls happen OUTSIDE _stateLock. Your mode check may be read under the lock or outside it, but you must not move any broker call inside the lock.
   - P1-11: risk-INCREASING orders are cancelled first; position-REDUCING orders (above all the protective stop) are deferred until the flatten is confirmed, and are left working if the flatten failed. Do not collapse the three batches into one.

6. Do not change ProcessAction's semantics, ValidateInvariant, the arbiter, or EvaluateLockoutPhase's phase transitions. Do not change any behaviour that applies when the mode IS an acting mode: a live-mode lockout must still cancel and flatten exactly as it does today.

7. Do not add a config flag to make this optional. Shadow not touching the broker is not a preference.

8. THE DEFERRED CANCEL QUEUE IS PART OF THIS DEFECT. Two earlier attempts at this ticket both got
   it wrong and BOTH passed every gate, so read this carefully.

   _pendingCancels exists because P1-43 forbids sending a cancel from under _stateLock: a decision
   made inside the lock is queued and DrainPendingCancels() sends it after the lock is released.
   DrainPendingCancels() has FOUR call sites, not one. Gating it at the sweep's call site fixes
   nothing, because ExecuteOrderUpdate drains it too and cancels the trader's order in shadow mode
   anyway. Do NOT put the mode check at the call sites. Put it INSIDE DrainPendingCancels(), so
   every present and future caller is covered by construction -- the same 'one place answers the
   question' principle as item 1.

   The queue mixes two kinds of work and they must be treated differently:

   - INTERVENTION -- cancelling an order the TRADER placed. Three sites, all in
     ExecuteOrderUpdate: the lockout entry-cancel, the blacklist cancel, and the per-instrument
     cap cancel. These are exactly what shadow mode exists to withhold. In a non-acting mode they
     must NOT reach the broker, and they must be DISCARDED rather than retained: a queue that
     grows all session and then fires the moment someone switches the mode combo to live is a
     stale burst of cancels against orders that have moved on.

   - CLEANUP -- cancelling an order RISKGUARD ITSELF submitted. One site, in UpdateFsmOnPosition:
     the orphaned auto-stop left on a position that has gone flat. This is not an intervention,
     it is the guard removing its own footprint, and skipping it is its own naked-risk defect --
     an orphan stop on a flat account opens a NEW position in the opposite direction when it
     triggers (this is P0-50, already closed once on the copier side). Cleanup cancels must be
     sent in EVERY mode, including shadow.

   Carry the intent explicitly on the queue -- an enum or a bool alongside each entry, or a
   second queue. Do NOT infer intent from the order's Name at drain time; a name comparison is
   exactly the kind of implicit coupling that drifts, and there are two independent naming schemes
   in play already.

9. Log what shadow withheld: when intervention cancels are discarded, LogEvent the account and the
   count. Silence here is what made this defect survive two review rounds.
## Additional context you must respect
Relevant existing members of RiskGuardAddOn: private string _mode (values 'shadow', 'live', 'pure', 'override_with_friction'; 'shadow' is the fail-safe default); private bool _isArmed; private readonly object _stateLock; internal void ExecuteSafetySweep(); string GetMode() returns _mode; LogEvent(string account, string eventType, string message). ProcessAction contains the existing mode gate and the SHADOW_ACTION log line -- read it before writing the helper so the extracted predicate matches it exactly, including the forceLive parameter. Note that 'live' is not the only acting mode name that exists in the config validator ('pure' and 'override_with_friction' are also accepted), but ProcessAction today treats ONLY 'live' (or forceLive) as acting -- preserve that exactly; widening it is a separate decision and is NOT in scope for this ticket. The tests build with -DTESTING against net8.0 and the addon must also compile under net48 inside NinjaTrader, so do not reference WPF or NinjaTrader.Gui types.
## Regions to rewrite
### REGION id="PendingCancelsField"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 249-287
Purpose: the deferred cancel queue; it currently carries no intent
```csharp
        private readonly List<KeyValuePair<Account, Order>> _pendingCancels =
            new List<KeyValuePair<Account, Order>>();
#if !TESTING
        private NTMenuItem _myMenuItem;
        private ControlCenter _controlCenter;
#endif
        private RiskConfig _config = new RiskConfig();

        // Cached Resources (Fix 12)
        private TimeZoneInfo _etZone = TimeZoneInfo.FindSystemTimeZoneById(
            Environment.OSVersion.Platform == PlatformID.Win32NT
                ? "Eastern Standard Time"
                : "America/New_York");
        private List<ParsedWindow> _parsedWindows = new List<ParsedWindow>();

        // Async Logging (Fix 11)
        private readonly System.Collections.Concurrent.ConcurrentQueue<string> _logQueue = new System.Collections.Concurrent.ConcurrentQueue<string>();

        // Per-account and aggregate state models
        private readonly Dictionary<string, AccountState> _accountStates = new Dictionary<string, AccountState>();
        private readonly List<string> _subscribedAccounts = new List<string>();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "RiskGuardAddOn";
                Description = "Cross-Account Risk Guard and Discipline Backstop";
            }
            else if (State == State.Configure)
            {
                Instance = this;
                InitializeRiskGuard();
            }
            else if (State == State.Terminated)
            {
                CleanupRiskGuard();
            }
        }
```
### REGION id="ExecuteSafetySweep"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1755-2009
Purpose: the lockout watchdog: collects the batches, then executes them against the broker with no mode check
```csharp
        internal void ExecuteSafetySweep()
        {
            // Decisions taken under the lock, executed after it is released (P1-10).
            var cancelBatches = new List<KeyValuePair<Account, List<Order>>>();
            var deferredCancelBatches = new List<KeyValuePair<Account, List<Order>>>();
            var flattenBatches = new List<KeyValuePair<Account, List<Instrument>>>();
            var sweepActions = new List<GuardAction>();

            // P1-12: the sweep's three disk writes are DECIDED here and performed at the bottom,
            // after the lock has been released and after the broker work. Nothing about a
            // heartbeat file or a log flush is worth delaying a flatten for.
            string heartbeatStamp = null;
            List<string> logsToWrite = null;
            PersistedStateData stateToWrite = null;

            try
            {
                lock (_stateLock)
                {
                    // 1. Heartbeat (liveness) - decide only.
                    if (DateTime.UtcNow - _lastHeartbeatTime >= TimeSpan.FromSeconds(5))
                    {
                        _lastHeartbeatTime = DateTime.UtcNow;
                        heartbeatStamp = DateTime.UtcNow.ToString("o");
                    }

                    // 2. Log flush: the queue is drained under the lock (it is shared state); the
                    // append is not. A ConcurrentQueue drain is microseconds, a file append on a
                    // stalled disk is not bounded at all.
                    logsToWrite = new List<string>();
                    while (_logQueue.TryDequeue(out string logLine))
                        logsToWrite.Add(logLine);

                    // 3. Session reset (check date change - the one remaining time-based rule)
                    DateTime nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _etZone);
                    DateTime currentSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

                    foreach (var accName in _subscribedAccounts)
                    {
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                        if (!_accountStates.TryGetValue(accName, out var stateModel)) continue;
                        if (stateModel.LastSessionDate == currentSessionDate) continue;

                        var account = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (account == null) continue;

                        stateModel.LastSessionDate = currentSessionDate;
                        stateModel.TradesToday = 0;
                        stateModel.ConsecutiveLosses = 0;
                        stateModel.PeakEquity = 0.0;
                        stateModel.PeakOpenGain = 0.0;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        stateModel.IsLockedOut = false;
                        stateModel.InitialLockoutFlattened = false;
                        stateModel.CurrentLockoutPhase = AccountState.LockoutPhase.None;
                        stateModel.SessionStartRealizedPnL = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        stateModel.LastRealizedPnL = stateModel.SessionStartRealizedPnL;
                        // P1-17: bank the session that just ended before zeroing it, so the
                        // cumulative evaluation total survives the daily reset.
                        stateModel.CumulativeRealizedPnL += stateModel.RealizedPnL;
                        stateModel.RealizedPnL = 0.0;
                        LogEvent(accName, "SESSION_RESET", $"Session reset for {currentSessionDate:yyyy-MM-dd}");
                        _stateDirty = true;
                    }

                    // FR-29: increment the shadow-session counter once per day when running in shadow mode.
                    // This is the soft gate that RunPreflight() checks before allowing live-mode arming.
                    if (_mode == "shadow" && _lastShadowSessionDate != currentSessionDate)
                    {
                        _lastShadowSessionDate = currentSessionDate;
                        _shadowSessionsCompleted++;
                        _stateDirty = true;
                        LogEvent("SYSTEM", "SHADOW_SESSION",
                            $"Shadow session #{_shadowSessionsCompleted} counted for {currentSessionDate:yyyy-MM-dd} (MinShadowSessions={_config.MinShadowSessions})");
                    }

                    // 4. State persist (batch flush) - capture now, write below. The flag is
                    // cleared here, not after the write: anything that dirties the state while
                    // the write is in flight must set it again and be picked up next sweep, not
                    // be cleared away by a flush that predates it.
                    if (_stateDirty)
                    {
                        stateToWrite = CapturePersistedState();
                        _stateDirty = false;
                    }

                    // 5. Lockout Watchdog - DECIDE ONLY (P1-10).
                    // This block used to call Cancel, Flatten, CreateOrder, Submit and
                    // ProcessAction with _stateLock held, which is the exact invariant the
                    // design doc claims is never violated. The event handlers already use
                    // collect-then-execute; the sweep now does too. Nothing below may touch
                    // Account until the lock is released.
                    foreach (var accName in _subscribedAccounts)
                    {
                        if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accName)) continue;
                        if (!_accountStates.TryGetValue(accName, out var stateModel)) continue;
                        if (!stateModel.IsLockedOut) continue;

                        var account = Account.All.FirstOrDefault(a => a.Name == accName);
                        if (account == null) continue;

                        // P1-11: split by intent. Risk-INCREASING orders go now; orders that
                        // reduce the position - above all the protective stop covering it -
                        // are held back until the flatten is confirmed. Cancelling the stop on
                        // the way in and then failing to flatten is how this path used to
                        // manufacture the naked position it exists to prevent.
                        var riskIncreasing = new List<Order>();
                        var reducing = new List<Order>();
                        foreach (Order o in account.Orders)
                        {
                            if (IsTerminal(o.OrderState)) continue;
                            if (RiskGuardOrderUtils.IsPositionReducingOrder(o, stateModel))
                                reducing.Add(o);
                            else
                                riskIncreasing.Add(o);
                        }
                        if (riskIncreasing.Count > 0)
                            cancelBatches.Add(new KeyValuePair<Account, List<Order>>(account, riskIncreasing));
                        if (reducing.Count > 0)
                            deferredCancelBatches.Add(new KeyValuePair<Account, List<Order>>(account, reducing));

                        var toFlatten = new List<Instrument>();
                        foreach (Position pos in account.Positions)
                        {
                            if (pos.Instrument != null && pos.MarketPosition != MarketPosition.Flat)
                                toFlatten.Add(pos.Instrument);
                        }
                        if (toFlatten.Count > 0)
                            flattenBatches.Add(new KeyValuePair<Account, List<Instrument>>(account, toFlatten));

                        var lockoutActions = EvaluateLockoutPhase(account, stateModel);
                        if (lockoutActions != null && lockoutActions.Count > 0)
                            sweepActions.AddRange(lockoutActions);
                    }

                    // 6. FSM watchdog (log-only diagnostic for stuck FSMs; arms timers, no broker calls)
                    FsmWatchdog();
                }

                // ---- lock released: everything below may talk to the broker ----

                DrainPendingCancels();

                foreach (var batch in cancelBatches)
                {
                    try { batch.Key.Cancel(batch.Value); }
                    catch (Exception cex)
                    { LogEvent(batch.Key.Name, "LOCKOUT_CANCEL_FAIL", cex.Message); }
                }

                foreach (var batch in flattenBatches)
                {
                    var account = batch.Key;
                    foreach (var instrument in batch.Value)
                    {
                        try
                        {
                            account.Flatten(new[] { instrument });
                        }
                        catch (Exception fex)
                        {
                            LogEvent(account.Name, "LOCKOUT_FLATTEN_FAIL",
                                $"{instrument.FullName}: {fex.Message}; falling back to a market close.");

                            // Re-read the position rather than trusting the quantity captured
                            // under the lock - the flatten may have partially succeeded.
                            var pos = account.Positions.FirstOrDefault(
                                p => p.Instrument != null && p.Instrument.FullName == instrument.FullName);
                            if (pos == null || pos.MarketPosition == MarketPosition.Flat || pos.Quantity <= 0)
                                continue;

                            var closeAction = pos.MarketPosition == MarketPosition.Long
                                ? OrderAction.Sell : OrderAction.BuyToCover;
                            try
                            {
                                var closeOrder = account.CreateOrder(
                                    instrument, closeAction, OrderType.Market, TimeInForce.Day,
                                    pos.Quantity, 0, 0, string.Empty, "RiskGuardWatchdogFlatten", null);
                                if (closeOrder != null) account.Submit(new[] { closeOrder });
                            }
                            catch (Exception sex)
                            { LogEvent(account.Name, "LOCKOUT_CLOSE_FAIL", $"{instrument.FullName}: {sex.Message}"); }
                        }
                    }
                }

                // P1-11 phase (c): only now, with the flatten attempted, may the reducing
                // orders go - and only for instruments that are actually flat. If the flatten
                // failed, the position is still open and its stop is the only thing standing
                // between the account and an uncapped loss. Leave it working; the next sweep
                // will try again.
                foreach (var batch in deferredCancelBatches)
                {
                    var account = batch.Key;
                    var stillCovered = new List<string>();
                    var safeToCancel = new List<Order>();

                    foreach (var order in batch.Value)
                    {
                        if (IsTerminal(order.OrderState)) continue;
                        if (order.Instrument == null) continue;

                        var pos = account.Positions.FirstOrDefault(
                            p => p.Instrument != null && p.Instrument.FullName == order.Instrument.FullName);
                        bool flat = pos == null || pos.MarketPosition == MarketPosition.Flat || pos.Quantity <= 0;

                        if (flat) safeToCancel.Add(order);
                        else stillCovered.Add(order.Instrument.FullName);
                    }

                    if (safeToCancel.Count > 0)
                    {
                        try { account.Cancel(safeToCancel); }
                        catch (Exception cex)
                        { LogEvent(account.Name, "LOCKOUT_CANCEL_FAIL", cex.Message); }
                    }

                    if (stillCovered.Count > 0)
                    {
                        LogEvent(account.Name, "LOCKOUT_STOP_RETAINED",
                            $"Position still open after flatten for {string.Join(",", stillCovered.Distinct())}; "
                            + "keeping its protective order working rather than leaving the position naked.");
                    }
                }

                foreach (var action in CoalesceActions(sweepActions))   // P1-19
                {
                    ProcessAction(action);
                }

                // All rule evaluation is now event-driven:
                // - PositionUpdate -> EvaluateRules + EvaluateLockoutPhase + UpdateFsmOnPosition
                // - OrderUpdate -> UpdateFsmOnOrder + EvaluateLockoutPhase
                // - ExecutionUpdate -> RecordExecution
                // - AccountItemUpdate -> EvaluatePnLRules + EvaluateFirmMirror
                // - Per-FSM one-shot Timer -> OnGraceExpired
            }
            catch (Exception ex)
            {
                LogEvent("SYSTEM", "ERROR", $"Error in ExecuteSafetySweep: {ex.Message}");
            }
            finally
            {
                // P1-12: last, outside the lock, and in a finally -- a rule that threw must not
                // cost us the log lines already drained out of the queue, which exist nowhere else.
                if (heartbeatStamp != null)
                    WriteFileOutsideLock("heartbeat", () => File.WriteAllText(_heartbeatFile, heartbeatStamp));

                if (logsToWrite != null && logsToWrite.Count > 0)
                    WriteFileOutsideLock("log", () => File.AppendAllLines(_logFile, logsToWrite, Encoding.UTF8));

                WritePersistedState(stateToWrite);
            }
        }
```
### REGION id="DrainPendingCancels"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 2253-2279
Purpose: the ONLY drain, with FOUR call sites; the mode decision belongs here, not at the call sites
```csharp
        private void DrainPendingCancels()
        {
#if TESTING
            if (Monitor.IsEntered(_stateLock))
                throw new InvalidOperationException(
                    "DrainPendingCancels() was called while _stateLock is held. The lock is "
                    + "re-entrant, so this would send the cancel under the lock and reintroduce "
                    + "P1-35. Move the call after the lock block.");
#endif
            List<KeyValuePair<Account, Order>> toSend;
            lock (_stateLock)
            {
                if (_pendingCancels.Count == 0) return;
                toSend = new List<KeyValuePair<Account, Order>>(_pendingCancels);
                _pendingCancels.Clear();
            }

            foreach (var pending in toSend)
            {
                var account = pending.Key;
                var order = pending.Value;
                if (account == null || order == null) continue;
                if (IsTerminal(order.OrderState)) continue;   // already resolved while queued
                try { account.Cancel(new[] { order }); }
                catch (Exception cex) { LogEvent(account.Name, "FSM_AUTOSTOP_CANCEL_FAIL", cex.Message); }
            }
        }
```
### REGION id="ExecuteOrderUpdate"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1569-1733
Purpose: three INTERVENTION enqueue sites: lockout entry-cancel, blacklist, per-instrument cap
```csharp
        internal void ExecuteOrderUpdate(object sender, OrderEventArgs e)
        {
            List<GuardAction> lockoutActions = null;
            lock (_stateLock)
            {
                try
                {
                    Account account = (Account)sender;
                    string accountName = account.Name;
                    if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(accountName))
                    {
                        // Skip entry cancellation for excluded accounts
                    }
                    else if (_accountStates.TryGetValue(accountName, out var stateModel))
                    {
                        // Order Rate Governor: detect rogue strategy order loops.
                        //
                        // P2-46: count DISTINCT ORDER IDS, not state transitions. This previously
                        // added a tick for Submitted and another for Accepted -- two states of the
                        // same order -- so a nominal "more than 5 per second" actually fired at
                        // about three real orders per second, inside normal ATM bracket
                        // submission. The live log's "29-32 orders/sec" were transition counts.
                        if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted)
                        {
                            string floodKey = e.Order.Id != null ? e.Order.Id.ToString() : Guid.NewGuid().ToString();
                            DateTime floodNow = DateTime.UtcNow;
                            if (!stateModel.RecentOrderIds.ContainsKey(floodKey))
                                stateModel.RecentOrderIds[floodKey] = floodNow;

                            DateTime floodCutoff = floodNow.AddSeconds(-1);
                            var staleOrderIds = stateModel.RecentOrderIds
                                .Where(kv => kv.Value < floodCutoff).Select(kv => kv.Key).ToList();
                            foreach (var staleId in staleOrderIds) stateModel.RecentOrderIds.Remove(staleId);

                            int maxPerSecond = (_config.Overtrading != null && _config.Overtrading.MaxOrdersPerSecond > 0)
                                ? _config.Overtrading.MaxOrdersPerSecond : 5;

                            if (stateModel.RecentOrderIds.Count > maxPerSecond)
                            {
                                stateModel.IsLockedOut = true;

                                // P1-45: pair the flag with a deadline. The lockout test is
                                // `IsLockedOut || UtcNow < LockoutUntil` -- an OR -- and every
                                // other rule sets a deadline, so setting the flag alone made a
                                // one-second burst lock the account out permanently, persisted
                                // across restarts.
                                if (_config.Overtrading.LockoutMinutes > 0)
                                {
                                    stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.Overtrading.LockoutMinutes);
                                }

                                // P1-44: never cancel a protective order to enforce a rate limit.
                                // Without this guard, a burst whose tripping order happened to be
                                // the stop-loss cancelled the protection AND locked the account
                                // out, leaving an open position naked. The lockout-enforcement
                                // block below has always had this guard; this path did not.
                                if (!IsPositionReducingOrder(e.Order, stateModel))
                                {
                                    // P1-43: queued, not sent -- this block runs under _stateLock.
                                    _pendingCancels.Add(new KeyValuePair<Account, Order>(account, e.Order));
                                }

                                LogEvent(accountName, "ORDER_FLOOD_LOCKOUT", $"ORDER FLOOD DETECTED: {stateModel.RecentOrderIds.Count} distinct orders in 1s (limit {maxPerSecond}) triggered lockout.");
                            }
                        }

                        if (stateModel.IsLockedOut || stateModel.ConsecutiveLosses >= _config.Overtrading.MaxConsecutiveLosses)
                        {
                            if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                            {
                                if (!IsPositionReducingOrder(e.Order, stateModel))
                                {
                                    if (e.Order.OrderType == OrderType.Limit || e.Order.OrderType == OrderType.StopMarket || e.Order.OrderType == OrderType.StopLimit || e.Order.OrderType == OrderType.Market)
                                    {
                                        // P1-43: queued, not sent -- this whole block runs under _stateLock.
                                        _pendingCancels.Add(new KeyValuePair<Account, Order>(account, e.Order));
                                        LogEvent(accountName, "ENTRY_CANCEL", $"Cancelled order {e.Order.Id} because account is locked out.");
                                    }
                                }
                            }
                        }
                    }

                    string rawInst = e.Order.Instrument != null ? e.Order.Instrument.FullName : "";
                    string instRoot = rawInst.Split(' ')[0].ToUpper();
                    if (_config.BlockedInstruments != null && _config.BlockedInstruments.Contains(instRoot))
                    {
                        if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                        {
                            // P1-43: queued, not sent -- this whole block runs under _stateLock.
                            _pendingCancels.Add(new KeyValuePair<Account, Order>(account, e.Order));
                            LogEvent(accountName, "BLACKLIST_CANCEL", $"Cancelled order {e.Order.Id} because instrument {instRoot} is blacklisted.");
                        }
                    }
                    if (_config.InstrumentLimits != null && _config.InstrumentLimits.TryGetValue(instRoot, out var perInstCap))
                    {
                        if (e.Order.Quantity > perInstCap.MaxContracts)
                        {
                            if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted || e.Order.OrderState == OrderState.Working)
                            {
                                // P1-43: queued, not sent -- this whole block runs under _stateLock.
                                _pendingCancels.Add(new KeyValuePair<Account, Order>(account, e.Order));
                                LogEvent(accountName, "PER_INSTRUMENT_CAP_CANCEL", $"Cancelled order {e.Order.Id} because quantity {e.Order.Quantity} exceeds {instRoot} cap ({perInstCap.MaxContracts}).");
                            }
                        }
                    }
                    string instrument = e.Order.Instrument.FullName;
                    string orderId = e.Order.Id.ToString();
                    string orderState = e.Order.OrderState.ToString();
                    string orderType = e.Order.OrderType.ToString();
                    double limitPrice = e.Order.LimitPrice;
                    double stopPrice = e.Order.StopPrice;
                    int quantity = e.Order.Quantity;

                    // - Per-position guard FSM (-6) -
                    // Classify this order against the active FSM for (account, instrument).
                    // If no FSM exists yet but this is a protective-side stop, buffer it
                    // in _pendingStops so it is consumed when the position-open event arrives.
                    UpdateFsmOnOrder(account, instrument, e.Order);

                    // -- Lockout phase: advance on order state changes --
                    // When an order goes Cancelled/Filled, check if the lockout can
                    // advance to the next phase (PendingFlatten or Confirmed).
                    // Collect actions here; process OUTSIDE the lock to avoid
                    // re-entrancy corruption when ProcessAction triggers events.
                    if (_accountStates.TryGetValue(accountName, out var lockState) &&
                        (lockState.IsLockedOut || DateTime.UtcNow < lockState.LockoutUntil))
                    {
                        lockoutActions = EvaluateLockoutPhase(account, lockState);
                    }

                    LogEvent(accountName, "ORDER_UPDATE", new JObject
                    {
                        { "instrument", instrument },
                        { "orderId", orderId },
                        { "orderState", orderState },
                        { "orderType", orderType },
                        { "orderAction", e.Order.OrderAction.ToString() },
                        { "orderName", e.Order.Name ?? "" },
                        { "quantity", quantity },
                        { "limitPrice", limitPrice },
                        { "stopPrice", stopPrice }
                    });
                }
                catch (Exception ex)
                {
                    LogEvent("SYSTEM", "ERROR", $"Error handling OnOrderUpdate: {ex.Message}");
                }
            }

            // P1-43: send the cancels queued above now that the lock is released. Four Cancel
            // calls sat inside the lock on this path -- the same invariant P1-10 and P1-35 closed
            // elsewhere. The machine check missed them because it only drove the sweep and FSM
            // teardown, never the order-update path.
            DrainPendingCancels();

            // Process lockout actions OUTSIDE the lock to prevent re-entrancy.
            if (lockoutActions != null && lockoutActions.Count > 0)
            {
                foreach (var a in lockoutActions)
                {
                    ProcessAction(a);
                }
            }
        }
```
### REGION id="UpdateFsmOnPosition"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 2098-2242
Purpose: the one CLEANUP enqueue site: cancelling RiskGuard's own orphaned auto-stop
```csharp
        private void UpdateFsmOnPosition(Account account, string instrument, MarketPosition newPos, int qty)
        {
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(account.Name)) return;
            if (!_isArmed) return;

            string key = FsmKey(account.Name, instrument);
            bool isNonFlat = newPos != MarketPosition.Flat && qty > 0;

            if (isNonFlat)
            {
                lock (_stateLock)
                {
                    // Check if an FSM already exists for this (account, instrument).
                    if (_guardFsms.TryGetValue(key, out var existingFsm) && existingFsm.PositionSide == newPos)
                    {
                        // Same-side qty-only update (partial fill, scale-out/in):
                        // update qty in place, preserving Protected/ProtectedPending state
                        // and the recognized stop order. Do NOT recreate the FSM.
                        existingFsm.PositionQuantity = qty;

                        // Under-coverage detection: if we are protected but the stop
                        // does not cover the full position, arm the grace timer.
                        if ((existingFsm.State == GuardFsmState.Protected ||
                             existingFsm.State == GuardFsmState.ProtectedPending) &&
                            existingFsm.CoveredQuantity < existingFsm.PositionQuantity)
                        {
                            LogEvent(account.Name, "FSM_UNDERCOVERED",
                                $"{key}: covered {existingFsm.CoveredQuantity} < pos {existingFsm.PositionQuantity}");
                            existingFsm.GraceEmitted = false;
                            if (!existingFsm.GracePending)
                            {
                                ArmGraceTimer(existingFsm, account, instrument,
                                    _config.StopGuard.StopAttachSeconds * 1000);
                            }
                        }

                        LogEvent(account.Name, "FSM_UPDATE",
                            $"{key}: qty updated to {qty} (state stays {existingFsm.State})");
                        return;
                    }

                    // flat->nonflat or flip: dispose the outgoing FSM's timer before overwriting.
                    if (_guardFsms.TryGetValue(key, out var oldFsm))
                    {
                        oldFsm.GraceTimer?.Dispose();
                    }

                    // (re)create FSM, arm grace, consume pending stop
                    var fsm = new PositionGuardFsm(account.Name, instrument)
                    {
                        PositionSide = newPos,
                        PositionQuantity = qty,
                        EntryTime = DateTime.UtcNow,
                        State = GuardFsmState.Unprotected
                    };

                    // Consume a buffered stop that arrived before the position event (P1-14).
                    if (_pendingStops.TryGetValue(key, out var pending) && pending != null)
                    {
                        // Now -- and only now -- the position side is known, so the buffered
                        // candidates can finally be judged. Two conditions, both load-bearing:
                        //
                        //   IsProtectiveSide  the order reduces THIS position rather than opening
                        //                     another one.
                        //   Quantity <= qty   a resting breakout ENTRY passes the side test by
                        //                     coincidence (a sell-stop entry does reduce a long)
                        //                     while being sized for a trade that has nothing to do
                        //                     with this position. Adopting it reports coverage the
                        //                     position does not have and, if it triggers, flips the
                        //                     account by the difference. A genuine protective stop
                        //                     is never larger than what it protects.
                        // P1-36: adopt every valid candidate, largest first, while the running
                        // total still fits the position. A bracket whose two stop legs both
                        // arrive before the position event is the ordinary case this has to get
                        // right; taking one of them reports the position half naked.
                        var candidates = pending
                            .Where(b => b.Order != null
                                     && IsStopType(b.Order)
                                     && !IsTerminal(b.Order.OrderState)
                                     && IsProtectiveSide(b.Order, newPos)
                                     && b.Order.Quantity <= qty)
                            .OrderByDescending(b => b.Order.Quantity)
                            .ToList();

                        int adoptedCount = 0;
                        bool anyPendingLeg = false;
                        foreach (var candidate in candidates)
                        {
                            if (fsm.CoveredQuantity + candidate.Order.Quantity > qty) continue;
                            fsm.AddRecognizedStop(candidate.Order);
                            adoptedCount++;
                            if (candidate.Order.OrderState != OrderState.Working) anyPendingLeg = true;
                        }

                        if (adoptedCount > 0)
                        {
                            fsm.State = anyPendingLeg
                                ? GuardFsmState.ProtectedPending
                                : GuardFsmState.Protected;
                        }

                        int rejected = pending.Count - adoptedCount;
                        if (rejected > 0)
                        {
                            LogEvent(account.Name, "FSM_PENDING_STOP_REJECTED",
                                $"{key}: discarded {rejected} buffered stop(s) that are not protective "
                                + $"cover for a {newPos} {qty} position.");
                        }
                        _pendingStops.Remove(key);
                    }

                    // Arm a one-shot grace timer that fires at the exact grace deadline.
                    // This replaces the sweep polling of GraceDeadline with an instant trigger.
                    if (fsm.State == GuardFsmState.Unprotected && _config.StopGuard.StopAttachSeconds > 0)
                    {
                        ArmGraceTimer(fsm, account, instrument, _config.StopGuard.StopAttachSeconds * 1000);
                    }

                    _guardFsms[key] = fsm;
                    LogEvent(account.Name, "FSM_TRANSITION",
                        $"Created FSM {key} -> {fsm.State} (grace deadline {fsm.GraceDeadline:HH:mm:ss})");
                }
            }
            else
            {
                // nonflat->flat: tear down, cancel grace timer, cancel orphan auto-stop.
                // P1-35 (was P1-30): this runs with _stateLock held - every caller of
                // UpdateFsmOnPosition already holds it. So the orphan cancel is QUEUED here and
                // sent by DrainPendingCancels() once the caller releases the lock. Do NOT
                // "fix" a future variant of this by wrapping the Cancel in a nested
                // lock(_stateLock) and calling it outside: the nested lock is re-entrant, the
                // outer lock is still held, and it only hides the violation.
                if (_guardFsms.TryGetValue(key, out var fsm))
                {
                    fsm.GraceTimer?.Dispose();
                    if (fsm.AutoStopOrder != null && !IsTerminal(fsm.AutoStopOrder.OrderState))
                    {
                        _pendingCancels.Add(new KeyValuePair<Account, Order>(account, fsm.AutoStopOrder));
                    }
                    _guardFsms.Remove(key);
                    LogEvent(account.Name, "FSM_TRANSITION", $"Tore down FSM {key} -> Flat");
                }
                _pendingStops.Remove(key);
            }
        }
```
### REGION id="ProcessAction"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 3265-3300
Purpose: holds the correct inline mode gate; extract it here and call the helper, changing nothing else
```csharp
        internal string ProcessAction(GuardAction action, bool forceLive = false)
        {
            bool isLive = false;
            lock (_stateLock)
            {
                // 1. ActionArbiter - Check Invariant (Risk-Reducing Only)
                if (!ValidateInvariant(action))
                {
                    LogEvent(action.AccountName, "ARBITER_REJECTED", $"Arbiter rejected action {action.ActionType} - would increase risk or target is invalid.");
                    return "REJECTED (INVARIANT VIOLATION)";
                }

                // 2. Mode Check (Shadow Mode Gate)
                isLive = _mode == "live" || forceLive;
                if (!isLive)
                {
                    string alsoShadow = (action.MergedRuleIds != null && action.MergedRuleIds.Count > 0)
                        ? $" (also: {string.Join(", ", action.MergedRuleIds)})" : "";
                    LogEvent(action.AccountName, "SHADOW_ACTION", $"[SHADOW] Would execute action {action.ActionType} triggered by {action.RuleId}{alsoShadow}");
                    return "SHADOW (SKIPPED)";
                }
            }

            // 3. Executor - Run the action (released lock to prevent deadlock with event dispatch thread)
            try
            {
                ExecuteAction(action);
                LogEvent(action.AccountName, "INTERVENTION", $"Executed action {action.ActionType} triggered by {action.RuleId}");
                return "EXECUTED";
            }
            catch (Exception ex)
            {
                LogEvent(action.AccountName, "EXECUTION_ERROR", $"Failed to execute {action.ActionType}: {ex.Message}");
                return $"ERROR: {ex.Message}";
            }
        }
```
Return one block per region id above, in the same order. No other output.