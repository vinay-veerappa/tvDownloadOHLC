# TICKET T2: P0-2 + P0-3: reserve-before-submit with rollback for the auto-stop, and size it from the live position

## Defect
P0-2: In ExecuteAction's PlaceStopOrder branch the FSM is mutated AFTER account.Submit:
    if (stopOrder != null) { account.Submit(new[] { stopOrder }); lock (_stateLock) { ... fsm.State = GuardFsmState.ProtectedPending; } }
Three defects: (a) the OrderUpdate for the new stop can be processed before that lock is taken, so a stop already Working is regressed to ProtectedPending and - worse - a stop that was REJECTED (correctly reset to Unprotected by UpdateFsmOnOrder) is overwritten to ProtectedPending, after which nothing ever re-arms grace and the position is naked permanently; (b) stopOrder == null is a completely silent no-op - no log, no retry, no flatten fallback; (c) if Submit throws, the FSM is left in whatever state the pre-submit code left it.

P0-3: The stop is sized from action.Quantity, a snapshot taken when the action was emitted, even though the live position is already re-read on the line above. If the position scaled DOWN in between, the auto-stop is LARGER than the position and opens a new opposite-side position when it triggers. If it scaled UP, part of the position is silently uncovered. ValidateInvariant for PlaceStopOrder only checks 'InstrumentObj != null && Quantity > 0' - it never confirms a position exists, its side, or its size, despite being described as an arbiter that only permits risk-reducing actions.

## Required change
1. In the PlaceStopOrder branch of ExecuteAction, size the order from the LIVE position: use position.Quantity (clamped to a positive int) rather than action.Quantity. If the live position is flat or its MarketPosition no longer matches the side the action was built for, abort the action, log a distinct event, and do not submit anything.

2. Adopt reserve-before-submit: BEFORE calling account.Submit, take lock (_stateLock) and set fsm.AutoStopOrder / fsm.RecognizedStopOrder / fsm.State = ProtectedPending / fsm.CoveredQuantity for the created order, then RELEASE the lock and submit. Do not hold _stateLock across CreateOrder or Submit.

3. Add rollback: if CreateOrder returns null, or Submit throws, re-acquire lock (_stateLock) and roll the FSM back to Unprotected, clear AutoStopOrder / RecognizedStopOrder / CoveredQuantity, log an explicit failure event (e.g. AUTO_STOP_SUBMIT_FAILED with the reason), and re-throw so ProcessAction records EXECUTION_ERROR. Never leave the FSM claiming protection that does not exist.

4. Remove the post-submit FSM write entirely. After a successful submit, UpdateFsmOnOrder owns all further FSM state for that order.

5. Track attempts so a repeatedly failing auto-stop escalates instead of looping: add an int AutoStopAttempts to PositionGuardFsm (increment on each attempt for that FSM, reset when the FSM leaves Unprotected or is torn down). Read the ceiling from _config.StopGuard.MaxAutoStopAttempts, adding that int property to StopGuardConfig with a default of 2 and defensive handling when it is 0 or negative (treat <= 0 as 2). When attempts exceed the ceiling, do not submit another stop; instead flatten that single instrument (account.Flatten(new[] { instrument })) and log the escalation.

6. Tighten ValidateInvariant's PlaceStopOrder case into a real arbiter: resolve the live Account and its Position for action.Instrument, and return false unless a non-flat position exists, action.Quantity > 0, and the action's implied order side is genuinely the closing side for that position. Keep the existing FlattenPosition / CancelAllOrders / CancelOrder cases unchanged. ValidateInvariant is called from inside lock (_stateLock) in ProcessAction, so it may read Account collections but must not call Flatten / Cancel / Submit / CreateOrder.

## Additional context you must respect
ExecuteAction is called from ProcessAction AFTER the lock is released, so ExecuteAction may take _stateLock itself for short state updates. Existing behaviour that must be preserved: the STOP_SIDE_FLATTEN paths when market price is unavailable or the computed stop is already through the market; RoundToTickSize on the stop price; the offsetTicks resolution from _config.StopGuard.Offsets with the 'default' fallback and 30-tick final default; the AUTO_STOP_DIAGNOSTIC order dump; the order name string 'RiskGuardAutoStop' (UpdateFsmOnOrder matches on it). PositionGuardFsm gains CoveredQuantity in ticket T1 - assume that field exists. StopGuardConfig is a plain settings class deserialised from config.json.

NOTE ON CURRENT STATE: ticket T1 has already landed. PositionGuardFsm now has CoveredQuantity, GracePending, GraceEmitted and GraceGeneration; ArmGraceTimer(fsm, account, instrument, delayMs) exists and MUST be called with _stateLock held; EvaluateGraceExpiry sizes its action to the uncovered delta and sets GraceEmitted as an anti-duplicate latch. When you roll the FSM back after a failed auto-stop submit you MUST also clear GraceEmitted, otherwise the latch suppresses every future grace action for that position and it stays naked. Do not re-implement or rename anything T1 added.

## Regions to rewrite

### REGION id="PositionGuardFsm"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 3333-3368
Purpose: add AutoStopAttempts (int) used by the escalation ceiling
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

        // Quantity covered by the single RecognizedStopOrder.
        public int CoveredQuantity { get; set; }
        // True while a one-shot grace timer is armed.
        public bool GracePending { get; set; }
        // True once a grace action has been emitted and its outcome is still pending.
        public bool GraceEmitted { get; set; }
        // Monotonically increasing generation counter to invalidate stale timer callbacks.
        public long GraceGeneration { get; set; }

        public PositionGuardFsm(string accountName, string instrument)
        {
            AccountName = accountName;
            Instrument = instrument;
        }
    }
```

### REGION id="ValidateInvariant"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 2571-2598
Purpose: real risk-reducing arbiter for PlaceStopOrder
```csharp
        private bool ValidateInvariant(GuardAction action)
        {
            var account = Account.All.FirstOrDefault(a => a.Name == action.AccountName);
            if (account == null) return false;

            if (action.ActionType == GuardActionType.FlattenPosition)
            {
                return true; 
            }

            if (action.ActionType == GuardActionType.CancelAllOrders)
            {
                return true;
            }

            if (action.ActionType == GuardActionType.CancelOrder)
            {
                return !string.IsNullOrEmpty(action.OrderId);
            }

            if (action.ActionType == GuardActionType.PlaceStopOrder)
            {
                // Placing stop order is risk-reducing only if we have an unprotected position covering it.
                return action.InstrumentObj != null && action.Quantity > 0;
            }

            return false;
        }
```

### REGION id="ExecuteAction"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 2600-2768
Purpose: live sizing, reserve-before-submit, rollback, attempt ceiling
```csharp
        private void ExecuteAction(GuardAction action)
        {
            var account = Account.All.FirstOrDefault(a => a.Name == action.AccountName);
            if (account == null) throw new Exception("Account not found");

            if (action.ActionType == GuardActionType.FlattenPosition)
            {
                var instrumentsToFlatten = new List<Instrument>();
                foreach (Position p in account.Positions)
                {
                    if (p.MarketPosition != MarketPosition.Flat && p.Instrument != null)
                    {
                        instrumentsToFlatten.Add(p.Instrument);
                    }
                }
                foreach (Order o in account.Orders)
                {
                    if ((o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted) && o.Instrument != null)
                    {
                        if (!instrumentsToFlatten.Contains(o.Instrument))
                        {
                            instrumentsToFlatten.Add(o.Instrument);
                        }
                    }
                }

                if (instrumentsToFlatten.Count > 0)
                {
                    try
                    {
                        account.Flatten(instrumentsToFlatten.ToArray());
                    }
                    catch (Exception fex)
                    {
                        LogEvent(action.AccountName, "FLATTEN_ERROR",
                            $"Flatten failed for {string.Join(",", instrumentsToFlatten.Select(i => i.FullName))}: {fex.Message}");
                        throw;
                    }
                }
            }
            else if (action.ActionType == GuardActionType.CancelAllOrders)
            {
                var orders = new List<Order>();
                foreach (Order o in account.Orders)
                {
                    if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted)
                    {
                        orders.Add(o);
                    }
                }
                if (orders.Count > 0)
                {
                    account.Cancel(orders);
                }
            }
            else if (action.ActionType == GuardActionType.CancelOrder)
            {
                var order = account.Orders.FirstOrDefault(o => o.Id.ToString() == action.OrderId);
                if (order != null)
                {
                    account.Cancel(new[] { order });
                }
            }
            else if (action.ActionType == GuardActionType.PlaceStopOrder)
            {
                var instrument = action.InstrumentObj;
                var position = account.Positions.FirstOrDefault(p => p.Instrument.FullName == action.Instrument);
                if (position == null || position.MarketPosition == MarketPosition.Flat) return;

                string symbolName = instrument.MasterInstrument.Name;
                int offsetTicks = 30; // default
                if (_config.StopGuard.Offsets.TryGetValue(symbolName, out int ticks))
                {
                    offsetTicks = ticks;
                }
                else if (_config.StopGuard.Offsets.TryGetValue("default", out int defTicks))
                {
                    offsetTicks = defTicks;
                }

                double tickSize = instrument.MasterInstrument.TickSize;
                double stopPrice = 0.0;
                OrderAction orderAction = OrderAction.Buy;

                // Fix B: Read real last price from market data
                double currentPrice = 0.0;
                if (instrument.MarketData != null && instrument.MarketData.Last != null)
                {
                    currentPrice = instrument.MarketData.Last.Price;
                }

                if (currentPrice <= 0.0)
                {
                    LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Market price unavailable for {instrument.FullName}. Flattening.");
                    account.Flatten(new[] { instrument });
                    return;
                }

                if (position.MarketPosition == MarketPosition.Long)
                {
                    stopPrice = position.AveragePrice - (offsetTicks * tickSize);
                    orderAction = OrderAction.Sell;
                    
                    if (stopPrice >= currentPrice)
                    {
                        LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Long stop {stopPrice} >= current price {currentPrice}. Flattening.");
                        account.Flatten(new[] { instrument });
                        return;
                    }
                }
                else if (position.MarketPosition == MarketPosition.Short)
                {
                    stopPrice = position.AveragePrice + (offsetTicks * tickSize);
                    orderAction = OrderAction.Buy;

                    if (stopPrice <= currentPrice)
                    {
                        LogEvent(account.Name, "STOP_SIDE_FLATTEN", $"Short stop {stopPrice} <= current price {currentPrice}. Flattening.");
                        account.Flatten(new[] { instrument });
                        return;
                    }
                }

                stopPrice = instrument.MasterInstrument.RoundToTickSize(stopPrice);

                // Diagnostic logging
                var orderDump = new StringBuilder();
                orderDump.AppendLine($"RiskGuard triggering auto-stop for {action.Quantity} {symbolName}. Current Orders:");
                foreach (Order o in account.Orders)
                {
                    if (o.Instrument?.FullName == action.Instrument)
                    {
                        orderDump.AppendLine($" - {o.OrderAction} {o.Quantity} {o.OrderType} | State: {o.OrderState} | Name: {o.Name}");
                    }
                }
                LogEvent(account.Name, "AUTO_STOP_DIAGNOSTIC", orderDump.ToString().TrimEnd());

                Order stopOrder = account.CreateOrder(
                    instrument,
                    orderAction,
                    OrderType.StopMarket,
                    TimeInForce.Day,
                    action.Quantity,
                    0,
                    stopPrice,
                    string.Empty,
                    "RiskGuardAutoStop",
                    null
                );

                if (stopOrder != null)
                {
                    account.Submit(new[] { stopOrder });

                    // Record the auto-stop on the FSM so it can cancel the orphan
                    // if the position flattens before the stop is hit (-6.4).
                    string key = FsmKey(account.Name, action.Instrument);
                    lock (_stateLock)
                    {
                        if (_guardFsms.TryGetValue(key, out var fsm))
                        {
                            fsm.AutoStopOrder = stopOrder;
                            fsm.RecognizedStopOrder = stopOrder;
                            fsm.State = GuardFsmState.ProtectedPending;
                        }
                    }
                }
            }
        }
```

### REGION id="StopGuardConfig"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 3523-3535
Purpose: add MaxAutoStopAttempts (default 2)
```csharp
    public class StopGuardConfig
    {
        public string OnMissing { get; set; } = "Flatten"; // "AutoStop", "Flatten", "WarnOnly"
        public int StopAttachSeconds { get; set; } = 3;
        public Dictionary<string, int> Offsets { get; set; } = new Dictionary<string, int>
        {
            { "NQ", 40 },
            { "MNQ", 40 },
            { "ES", 16 },
            { "MES", 16 },
            { "default", 30 }
        };
    }
```

Return one block per region id above, in the same order. No other output.