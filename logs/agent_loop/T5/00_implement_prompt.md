# TICKET T5: P0-8 + P0-9(fail-closed): make the copier respect the RiskGuard lockout and refuse to copy into an unguarded account
## Defect
P0-8: Every order-submitting path in McpBridgeAddOn checks RiskGuardAddOn.Instance.IsAccountLocked(...) before submitting. TradeCopierEngine.OnExecution does not. A follower that RiskGuard locked out for a daily-loss breach still receives fresh copied entries, and RiskGuard's lockout sweep then fights the copier - cancel and flatten every sweep against new entries arriving on every leader fill.

P0-9: The copier submits bare market orders and never replicates protective legs. A follower's only protection is RiskGuard's grace-period auto-stop, which does not exist if RiskGuard is disarmed, in shadow mode, or the follower sits in ExcludedAccounts. Full bracket replication is a separate feature; this ticket implements only the fail-closed precondition.
## Required change
1. Add a public read-only query to RiskGuardAddOn that answers whether the guard would actually protect a given account right now. Suggested shape:
     public bool IsGuardProtecting(string accountName)
   Return true only when: _isArmed is true, the resolved mode is live (GetMode() equals "live"), the account is present in _subscribedAccounts, the account is NOT in _config.ExcludedAccounts, and StopGuard is configured to act (its enable flag, if any, is on and StopAttachSeconds >= 0). Read all of it under lock (_stateLock). Do not change any existing public method.

2. In OnExecution's per-relationship loop, before creating any follower order, consult RiskGuard when the instance exists:
   a. If RiskGuardAddOn.Instance.CanTrade(followerName, targetInstrument.FullName, "TradeCopier") returns false, skip that follower, log '[CopierEngine] BLOCKED ...' with the reason, and continue.
   b. Also skip when the LEADER account is locked - a locked leader's fills must not be propagated. Use the same CanTrade query for the leader account.
   c. Fail closed on unguarded live followers: for a follower that is NOT a simulated account, require IsGuardProtecting(followerName) to be true; if it is false, skip the copy and log COPY_BLOCKED_NO_GUARD. Simulated followers are exempt from this requirement only.
   d. If RiskGuardAddOn.Instance is null, treat that as unguarded: allow simulated followers, block non-simulated ones.

3. Do not call CanTrade or IsGuardProtecting while holding the copier's own lock (_lock) - both take RiskGuard's _stateLock and the copier must not introduce a lock-ordering dependency. The existing recursion-guard block near the top of OnExecution is the only part that needs _lock.

4. Leave the existing ArmedForLive safety gate in place; the new checks are additional, not a replacement.
## Additional context you must respect
RiskGuardAddOn is in the same namespace and assembly (NinjaTrader.NinjaScript.AddOns) and exposes a static Instance property. Its existing signatures: public bool CanTrade(string accountName, string instrument, string strategyName = "DefaultStrategy"), public bool IsAccountLocked(string accountName), public string GetMode(). Private fields available inside RiskGuardAddOn: _isArmed (bool), _mode (string), _subscribedAccounts (HashSet<string>), _config (RiskConfig with ExcludedAccounts and StopGuard), _stateLock. OnExecution and the surrounding code are inside '#if !TESTING' in TradeCopierEngine.cs, but RiskGuardAddOn.cs compiles in BOTH configurations - so the new IsGuardProtecting method must compile under TESTING too and must not reference WPF or NinjaTrader.Gui types. The current simulated-account test in OnExecution is 'followerAcc.Name.StartsWith("Sim", ...)'; keep using it for now (replacing it is tracked separately as P1-20) but centralise it in a single local variable.
## Regions to rewrite
### REGION id="IsAccountLocked"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 798-808
Purpose: append the new public IsGuardProtecting query after this method
```csharp
        public bool IsAccountLocked(string accountName)
        {
            lock (_stateLock)
            {
                if (_accountStates.TryGetValue(accountName, out var state))
                {
                    return state.IsLockedOut;
                }
                return false;
            }
        }
```
### REGION id="OnExecution"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 664-803
Purpose: risk gate + fail-closed on unguarded live followers
```csharp
        public void OnExecution(Execution exec)
        {
            if (exec == null || exec.Account == null || exec.Quantity <= 0) return;
            
            // Skip copy if order is null (cannot determine order direction safely)
            if (exec.Order == null) return;

            string acctName = exec.Account.Name;

            lock (_lock)
            {
                // Recursion Guard 1: Followers can NEVER act as Leaders (prevents copy feedback loops)
                bool isFollowerInDirect = _relationships.Any(r => r.IsEnabled && r.FollowerAccountName.Equals(acctName, StringComparison.OrdinalIgnoreCase));
                bool isFollowerInGroups = _groups.Any(g => g.IsEnabled && g.FollowerAccounts != null && g.FollowerAccounts.Any(f => f.Equals(acctName, StringComparison.OrdinalIgnoreCase)));
                if (isFollowerInDirect || isFollowerInGroups)
                {
                    return;
                }

                // Recursion Guard 2: Ignore executions originated by copier placement
                if (!string.IsNullOrEmpty(exec.Order.Name) && exec.Order.Name.Contains("COPIER")) return;
                if (exec.Name != null && exec.Name.Contains("COPIER")) return;
            }

            // Redelivery Guard 3: Deduplicate exact duplicate socket redelivery of same execution ID (bounded FIFO queue)
            if (DeduplicateExecutionId(exec.ExecutionId)) return;

            List<CopierRelationship> activeRels = GetActiveRelationshipsForLeader(acctName);

            if (activeRels.Count == 0) return;

            foreach (var rel in activeRels)
            {
                Account followerAcc = Account.All.FirstOrDefault(a => a.Name.Equals(rel.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
                if (followerAcc == null) continue;

                bool isSimFollower = followerAcc.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase);

                // SAFETY GATE: Disarmed copier MUST NOT place orders on non-Sim (live) accounts
                if (!rel.ArmedForLive && !isSimFollower)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] BLOCKED execution copy to live account {followerAcc.Name} (ArmedForLive=false)", PrintTo.OutputTab1);
                    continue;
                }

                // Determine target Instrument (AutoSymbolConversion e.g. NQ -> MNQ)
                Instrument targetInstrument = exec.Instrument;
                if (rel.AutoSymbolConversion && exec.Instrument != null)
                {
                    string translatedSymbolName = TranslateSymbol(exec.Instrument.FullName, rel);
                    if (!string.Equals(translatedSymbolName, exec.Instrument.FullName, StringComparison.OrdinalIgnoreCase))
                    {
                        var resolvedInst = Instrument.GetInstrument(translatedSymbolName);
                        if (resolvedInst != null)
                        {
                            targetInstrument = resolvedInst;
                        }
                    }
                }

                OrderAction leadOrderAction = exec.Order.OrderAction;
                bool isExit = leadOrderAction == OrderAction.Sell || leadOrderAction == OrderAction.BuyToCover;

                int currentFollowerPos = 0;
                var followerPositionObj = followerAcc.Positions.FirstOrDefault(p => p.Instrument.FullName.Equals(targetInstrument.FullName, StringComparison.OrdinalIgnoreCase));
                if (followerPositionObj != null)
                {
                    currentFollowerPos = followerPositionObj.Quantity;
                }

                bool isClamped;
                int targetQty = CalculateFollowerQuantity(rel, exec.Quantity, exec.Instrument.FullName, currentFollowerPos, isExit, out isClamped);
                if (targetQty <= 0)
                {
                    if (isExit && currentFollowerPos == 0)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] NO POSITION TO EXIT: Follower has no position in {targetInstrument.FullName} on account {followerAcc.Name}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    else if (isClamped)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] CLAMPED TO ZERO: Follower position on {followerAcc.Name} at MaxPositionSize {rel.MaxPositionSize}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    else
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] SUB_MINIMUM_SKIPPED: Scaled copy quantity for {targetInstrument.FullName} is below 1 contract on account {followerAcc.Name}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    continue;
                }

                if (isClamped)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] POSITION CLAMP WARNING: Follower copy qty for {targetInstrument.FullName} clamped to {targetQty} (MaxPositionSize: {rel.MaxPositionSize}, CurrentPos: {currentFollowerPos}) on account {followerAcc.Name}", PrintTo.OutputTab1);
                }

                OrderAction followerAction = leadOrderAction;

                // Handle Inverse / Fade Trading (QuantityRatio < 0)
                if (rel.QuantityRatio < 0)
                {
                    if (leadOrderAction == OrderAction.Buy) followerAction = OrderAction.Sell;
                    else if (leadOrderAction == OrderAction.Sell) followerAction = OrderAction.BuyToCover;
                    else if (leadOrderAction == OrderAction.SellShort) followerAction = OrderAction.Buy;
                    else if (leadOrderAction == OrderAction.BuyToCover) followerAction = OrderAction.SellShort;
                }
                else if (isExit)
                {
                    // Align exit order action with follower's current position direction if non-zero
                    if (currentFollowerPos < 0) followerAction = OrderAction.BuyToCover;
                    else if (currentFollowerPos > 0) followerAction = OrderAction.Sell;
                }

                TimeInForce tif = (exec.Order.TimeInForce != TimeInForce.Gtc) ? exec.Order.TimeInForce : TimeInForce.Day;

                try
                {
                    Order followerOrder = followerAcc.CreateOrder(
                        targetInstrument,
                        followerAction,
                        OrderType.Market,
                        tif,
                        targetQty,
                        0,
                        0,
                        "",
                        "COPIER_FOLLOW",
                        null
                    );

                    // Submit follower order
                    if (followerOrder != null)
                    {
                        followerAcc.Submit(new[] { followerOrder });
                    }
                }
                catch (Exception ex)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] Error placing follower order on {followerAcc.Name}: {ex.Message}", PrintTo.OutputTab1);
                }
            }
        }
```
Return one block per region id above, in the same order. No other output.