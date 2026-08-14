# TICKET T7: P1-52: the order-flood governor counts a normal ATM bracket as a flood
## Defect
The order-rate governor in ExecuteOrderUpdate counts distinct order IDs inside a one-second window with no notion of a bracket. A single 2-contract ATM entry is SIX orders -- two entries, two protective stops, two targets -- against a default MaxOrdersPerSecond of 5. So every 2-lot bracketed entry trips a lockout.

Observed live 2026-08-09 21:15:22 ET: 'ORDER FLOOD DETECTED: 6 distinct orders in 1s (limit 5)' on three accounts in the same second, because a third-party copier mirrored the bracket to two of them. Copier fan-out multiplies a false positive across every mirrored account at once. That false lockout is what then triggered P0-51's real flatten.

This is the third defect on this governor. P1-44 (it could cancel a protective stop), P1-45 (the lockout never lapsed) and P2-46 (it double-counted Submitted and Accepted as two orders) came before it. P2-46 is the closest and is NOT the same bug: it fixed counting one order twice, this is six genuinely distinct orders that are one trade.
## Required change
1. Make the governor count TRADING RATE rather than order-object churn, so that one bracketed entry counts as one burst of activity and a runaway strategy loop still trips.

   Two acceptable mechanisms -- pick ONE and justify it in your notes:
   (a) Key the flood map on the order's OCO group when it has one, falling back to Order.Id when it does not. NT8 brackets share an OCO id per contract pair, so a 2-lot ATM collapses from 6 keys to 4.
   (b) Count only orders that are not protective legs, i.e. exclude the stop/target orders that cover an existing or incoming position, so a 2-lot ATM counts 2.

   Either satisfies the acceptance test. Do not implement both.

2. Do NOT 'fix' this by raising MaxOrdersPerSecond, and do not change its default of 5. A limit high enough to clear a 5-lot ATM is high enough to miss a real runaway loop, which is the only thing this governor exists to catch. Changing the threshold is explicitly rejected as a fix.

3. Keep P2-46's property: the same order passing through Submitted and then Accepted must still count ONCE, never twice. There is an existing test for this; it must stay green.

4. Keep P1-45's property: when the lockout does fire, it still sets LockoutUntil from Overtrading.LockoutMinutes. Do not touch the lockout body, only what gets counted.

5. Keep the one-second sliding window and the stale-key eviction as they are.

6. The count must still be per-account. Do not introduce a cross-account counter.
## Additional context you must respect
The governor lives inside ExecuteOrderUpdate, in the branch guarded by `if (e.Order.OrderState == OrderState.Submitted || e.Order.OrderState == OrderState.Accepted)`. State lives on AccountState.RecentOrderIds, a Dictionary<string, DateTime> mapping key -> first-seen UTC time. The mock and real Order both expose: string Id, string Oco, string Name, OrderState OrderState, OrderType OrderType, OrderAction OrderAction, int Quantity, Instrument Instrument, double LimitPrice, double StopPrice. RiskGuardAddOn already has `internal bool IsPositionReducingOrder(Order order, AccountState stateModel)` and the static helpers `IsStopType(Order o)` and `IsProtectiveSide(Order o, MarketPosition positionSide)` -- reuse them rather than writing a second definition of 'this order is a protective leg'; two definitions would drift and the copier already learned that lesson under P0-9. Note that at the moment a bracket is SUBMITTED the position may still be flat, so any mechanism that depends on the current position side must cope with MarketPosition.Flat.
## Regions to rewrite
### REGION id="ExecuteOrderUpdate"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1597-1761
Purpose: contains the order-rate governor and the flood lockout body
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
                                    _pendingCancels.Add(new PendingCancelEntry(account, e.Order, PendingCancelIntent.Intervention));
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
                                        _pendingCancels.Add(new PendingCancelEntry(account, e.Order, PendingCancelIntent.Intervention));
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
                            _pendingCancels.Add(new PendingCancelEntry(account, e.Order, PendingCancelIntent.Intervention));
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
                                _pendingCancels.Add(new PendingCancelEntry(account, e.Order, PendingCancelIntent.Intervention));
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
Return one block per region id above, in the same order. No other output.