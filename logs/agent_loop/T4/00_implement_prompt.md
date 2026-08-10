# TICKET T4: P0-5 + P0-6: clamp copier exits to the follower's real position; stop flooring sub-1 conversions to 1 contract
## Defect
P0-5: Exit copies are sized from the leader's execution quantity and returned unclamped. CalculateFollowerQuantity returns 'isExit ? leaderQty : rel.FixedLotSize' in fixed-lot mode - so on an exit it ignores FixedLotSize entirely and uses the LEADER's raw quantity - and in ratio mode returns rawCopyQty before the position clamp. Concrete failure with FixedLotSize = 1: leader buys 5, follower buys 1; leader sells 5, follower submits Sell 5 while holding 1, and ends up SHORT 4 on a market order with no stop. The same reversal happens after any MaxPositionSize clamp, any failed entry copy, or any rounding difference. CalculateSafeFollowerDelta already implements the correct clamp and is never called from anywhere.

P0-6: rawCopyQty uses Math.Max(1, Math.Round(leaderQty * absRatio * symbolMultiplier)). With the micro-to-mini multiplier of 0.1, a leader trading 1 MNQ produces 1 NQ - ten times the intended notional - and any QuantityRatio below 1 hits the same floor.
## Required change
1. Remove the Math.Max(1, ...) floor. Compute the scaled quantity, round it, and if the result is less than 1 return 0 so the caller skips the copy. Set the isClamped out-parameter to false in that case and make the reason visible to the caller - either via a new out parameter or by returning 0 and letting the caller log SUB_MINIMUM_SKIPPED - your choice, but the caller must be able to distinguish 'clamped by MaxPositionSize' from 'below one contract'.

2. Make exits position-mirroring rather than quantity-replaying. For exits, the returned quantity must never exceed Math.Abs(currentFollowerPosition). Route the decision through the existing CalculateSafeFollowerDelta helper rather than duplicating its logic, or - if its signature does not fit cleanly - clamp explicitly to Math.Abs(currentFollowerPosition) and state in your notes why the helper could not be reused. If the follower has no position, an exit must return 0.

3. Fixed-lot mode must respect the same rule: an exit in fixed-lot mode is still clamped to the follower's actual position, never the leader's quantity.

4. In OnExecution, handle the new zero-quantity outcomes: skip the copy, log a clear reason via NinjaTrader.Code.Output.Process with the existing '[CopierEngine] ' prefix, and continue to the next relationship. Keep the existing CLAMPED TO ZERO and POSITION CLAMP WARNING messages working.

5. Do not change the two-argument CalculateFollowerQuantity convenience overload's signature - other callers and tests use it. If you add an out parameter to the six-argument overload, keep a compatible path for existing callers.
## Additional context you must respect
currentFollowerPosition is read from followerAcc.Positions and is a NON-NEGATIVE quantity in NT8 (Position.Quantity is the absolute size; direction lives in Position.MarketPosition), so do NOT infer direction from its sign. OnExecution already computes 'isExit' from the leader's OrderAction and separately aligns the follower's OrderAction to the follower's current direction. Existing tests call both CalculateFollowerQuantity overloads and CalculateScaledQuantity and CalculateSafeFollowerDelta directly - preserve their existing behaviour for entry sizing, the PerTickerRatios override, and the mini/micro symbol multiplier. OnExecution is inside '#if !TESTING' - preserve that structure exactly.
## Regions to rewrite
### REGION id="CalculateFollowerQuantity"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 402-444
Purpose: no sub-1 floor; exits clamped to follower position
```csharp
        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol, int currentFollowerPosition, bool isExit, out bool isClamped)
        {
            isClamped = false;
            if (leaderQty <= 0) return 0;
            if (rel.FixedLotMode || rel.SizingMode == CopierSizingMode.FixedLot) return isExit ? leaderQty : rel.FixedLotSize;

            double absRatio = Math.Abs(rel.QuantityRatio);
            string symbol = rawSymbol.Split(' ')[0].ToUpper();

            // 1. Check Per-Ticker Ratio Overrides
            if (rel.PerTickerRatios != null && rel.PerTickerRatios.TryGetValue(symbol, out double tickerRatio))
            {
                absRatio = Math.Abs(tickerRatio);
            }

            // 2. Bidirectional Symbol Multiplier (Mini -> Micro 10x, Micro -> Mini 0.1x)
            double symbolMultiplier = 1.0;
            if (rel.AutoSymbolConversion)
            {
                if (symbol == "NQ" || symbol == "ES" || symbol == "YM" || symbol == "CL" || symbol == "GC" || symbol == "RTY")
                {
                    symbolMultiplier = 10.0; // Mini -> Micro
                }
                else if (symbol == "MNQ" || symbol == "MES" || symbol == "MYM" || symbol == "MCL" || symbol == "MGC" || symbol == "M2K")
                {
                    symbolMultiplier = 0.1; // Micro -> Mini
                }
            }

            int rawCopyQty = (int)Math.Max(1, Math.Round(leaderQty * absRatio * symbolMultiplier));
            if (isExit) return rawCopyQty;

            // Position-level Clamping: Cap against follower's resulting total position size
            int availableCapacity = Math.Max(0, rel.MaxPositionSize - Math.Abs(currentFollowerPosition));
            int finalQty = Math.Min(rawCopyQty, availableCapacity);

            if (rawCopyQty > availableCapacity)
            {
                isClamped = true;
            }

            return Math.Max(0, finalQty);
        }
```
### REGION id="CalculateFollowerQuantityShim"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 446-449
Purpose: keep the existing signature working
```csharp
        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol, bool isExit = false)
        {
            return CalculateFollowerQuantity(rel, leaderQty, rawSymbol, 0, isExit, out _);
        }
```
### REGION id="OnExecution"  file=scripts/ninjatrader/addons/TradeCopierEngine.cs  lines 623-754
Purpose: handle zero-quantity outcomes and log reasons
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
                    if (isClamped)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] CLAMPED TO ZERO: Follower position on {followerAcc.Name} at MaxPositionSize {rel.MaxPositionSize}. Copy order skipped.", PrintTo.OutputTab1);
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