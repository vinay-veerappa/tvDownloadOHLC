# TICKET SELFTEST: P0-7: peak-giveback rule compares a total-PnL peak against unrealized-only PnL
## Defect
EvaluatePnLRules calls propSuite.EvaluatePeakEquityGiveback(stateModel.PeakEquity, stateModel.UnrealizedPnL, ...). The predicate's parameters are (double peakOpenGain, double currentUnrealized), but PeakEquity is the running peak of Realized + Unrealized while the second argument is Unrealized only. An account that banked +2000 and is now flat yields giveback = 2000 - 0 = 2000 and givebackPct = 1.0 >= 0.30, so PEAK_GIVEBACK_BREACH fires on EVERY AccountItemUpdate. It is inert while flat because there is nothing to flatten, and this branch deliberately never sets IsLockedOut so it never latches - but it will instantly flatten the first position taken after any profitable session.
## Required change
1. Give AccountState a dedicated peak for this rule: double PeakOpenGain, meaning the running peak of UNREALIZED PnL for the current open position. It must reset to 0 whenever the account becomes flat (no open position) and must only rise while a position is open. Reset it alongside the other per-session fields where PeakEquity is reset. Leave the existing PeakEquity field and the trailing-drawdown rule that uses it untouched.

2. In EvaluatePnLRules, maintain PeakOpenGain from stateModel.UnrealizedPnL and pass the consistent pair to the predicate: (stateModel.PeakOpenGain, stateModel.UnrealizedPnL).

3. Add the missing preconditions so the rule cannot fire spuriously: only evaluate the giveback rule when the account actually has a non-flat position, and when PeakOpenGain is greater than zero. Determine flatness from state already available on AccountState (its per-instrument position map) rather than by calling into Account.

4. Latch the rule so it fires once per episode instead of on every account update: add a bool PeakGivebackTriggered to AccountState, set it when the action is emitted, and clear it when the account returns to flat (alongside the PeakOpenGain reset). Do not set IsLockedOut - that behaviour change is out of scope for this ticket.

5. In PropFirmProtectionSuite.EvaluatePeakEquityGiveback, keep the signature and semantics but harden it: rename nothing, and return false when peakOpenGain <= 0 (already present) or when currentUnrealized >= peakOpenGain. Add a short comment stating the required basis - both arguments must be unrealized-only, in dollars - so the mis-wiring cannot recur.
## Additional context you must respect
AccountState already tracks per-instrument PositionState objects in a dictionary and exposes RealizedPnL, UnrealizedPnL, PeakEquity, TradesToday, ConsecutiveLosses, IsLockedOut, LockoutUntil, CurrentLockoutPhase. EvaluatePnLRules is called from ExecuteAccountItemUpdate while _stateLock is held, and its returned actions are processed after the lock is released - preserve that. Session reset in ExecuteSafetySweep resets PeakEquity to 0.0 and must also reset the new fields; that reset lives outside the regions you are given, so instead make the new fields safe to leave stale by resetting them on the flat transition, and mention in your notes that the session-reset block should also clear them.
## Regions to rewrite
### REGION id="AccountState"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 4650-4905
Purpose: add PeakOpenGain + PeakGivebackTriggered; reset on flat
```csharp
    public class AccountState
    {
        public string AccountName { get; }
        public Dictionary<string, PositionState> Positions { get; } = new Dictionary<string, PositionState>();
        public double RealizedPnL { get; set; } = 0.0;
        // P1-17: realized PnL banked in *completed* sessions. RealizedPnL above is
        // session-scoped and zeroed at every reset, which is right for the daily-loss rule and
        // wrong for EvaluationTargetProfit -- a cumulative, multi-day prop evaluation target.
        // The total to evaluate a cumulative target against is TotalRealizedPnL below.
        // Accumulated once per session reset rather than per realized-PnL delta: a delta-based
        // total would be permanently corrupted by a single spurious tick (e.g. the broker
        // rebasing its own counter before our session reset runs), whereas a session total is
        // rebased every day and cannot drift.
        public double CumulativeRealizedPnL { get; set; } = 0.0;
        public double TotalRealizedPnL { get { return CumulativeRealizedPnL + RealizedPnL; } }
        // P1-16: realized PnL banked for the trade currently being closed, summed across its
        // partial exits and judged once at the flat transition. Deliberately not persisted --
        // a restart mid-trade settles it as a scratch rather than inventing a result.
        public double OpenTradeRealizedDelta { get; set; } = 0.0;
        // True from a flat transition until the next entry: the window in which a late fill
        // for the closed trade may still arrive and must revise its settlement.
        public bool ClosedTradeAwaitingLateFills { get; set; } = false;
        // The streak as it stood before the current trade was judged, so re-judging on a late
        // fill is a correction rather than a second increment.
        public int ConsecutiveLossesBeforeSettlement { get; set; } = 0;
        public double UnrealizedPnL { get; set; } = 0.0;
        public double PeakEquity { get; set; } = 0.0;
        public double PeakOpenGain { get; set; } = 0.0;
        public bool PeakGivebackTriggered { get; set; } = false;
        public double PeakGivebackLastTriggerUnrealized { get; set; } = double.NaN;
        public bool IsLockedOut { get; set; } = false;
        public DateTime LockoutUntil { get; set; } = DateTime.MinValue;
        public bool InitialLockoutFlattened { get; set; } = false;
        public DateTime LastLockoutFlattenAttempt { get; set; } = DateTime.MinValue;
        // P2-46: order id -> first time seen inside the rate window. Keyed by id so one order
        // passing Submitted -> Accepted -> Working counts once, not three times.
        public Dictionary<string, DateTime> RecentOrderIds { get; set; } = new Dictionary<string, DateTime>();

        // Lockout phase: PendingCancel -> PendingFlatten -> Confirmed.
        // Only Confirmed stops emitting actions. This prevents the infinite
        // flatten loop where account.Flatten() fails silently but the sweep
        // keeps re-firing every second.
        public enum LockoutPhase { None, PendingCancel, PendingFlatten, Confirmed }
        public LockoutPhase CurrentLockoutPhase { get; set; } = LockoutPhase.None;
        
        // Session and Overtrading
        public DateTime LastSessionDate { get; set; } = DateTime.MinValue;
        public int TradesToday { get; set; } = 0;
        public int ConsecutiveLosses { get; set; } = 0;
        public DateTime CooldownUntil { get; set; } = DateTime.MinValue;
        public double LastRealizedPnL { get; set; } = 0.0; // To track delta for consec losses
        public double SessionStartRealizedPnL { get; set; } = 0.0; // Baseline for session PnL

        // - Firm-mirror tracking (independent of discretionary PeakEquity) -
        public double FirmTrailingPeak { get; set; } = double.MinValue;
        public bool FirmFloorLocked { get; set; } = false;
        public DateTime FirmDailyDate { get; set; } = DateTime.MinValue;
        public double FirmDailyStartRealized { get; set; } = 0.0;
        public double FirmStartingBalance { get; set; } = 0.0;

        public AccountState(string name)
        {
            AccountName = name;
        }

        // P1-16: realized PnL arrives per execution, so a single trade exited in three partials
        // delivers three negative deltas. Counting each one as a "consecutive loss" made a
        // MaxConsecutiveLosses=3 lockout reachable from one losing trade, and put this counter
        // at odds with TradesToday, which is already debounced to the trade lifecycle.
        // Deltas are banked and judged once per trade. Three cases, because the relative order
        // of the realized-PnL event and the position-flat event is NOT guaranteed:
        //
        //  1. A trade is open  -> bank it; SettleClosedTrade judges the total at the flat
        //     transition. This is the fix: partial exits no longer count separately.
        //  2. The trade just closed and a late fill arrives -> revise the settlement in place
        //     rather than let the delta land on the next trade. This is why the running total
        //     and the pre-settlement streak are kept until the *next entry*, not cleared at
        //     settlement: re-judging from the snapshot is exact for any number of late fills,
        //     including one that flips the trade's net result from win to loss.
        //  3. No trade is tracked at all (the guard never saw the position, or this is a
        //     standalone adjustment) -> judge the delta on its own, preserving the pre-existing
        //     behaviour. Silently ignoring untracked realized losses would make the lockout
        //     less sensitive than before, which is not an acceptable trade for this fix.
        public void RecordRealizedDelta(double tradePnL, RiskConfig config)
        {
            OpenTradeRealizedDelta += tradePnL;

            if (ClosedTradeAwaitingLateFills)
            {
                ApplyTradeJudgement(config);
                return;
            }

            if (!HasOpenPosition())
            {
                ConsecutiveLossesBeforeSettlement = ConsecutiveLosses;
                ApplyTradeJudgement(config);
                OpenTradeRealizedDelta = 0.0;
                ConsecutiveLossesBeforeSettlement = ConsecutiveLosses;
            }
        }

        private bool HasOpenPosition()
        {
            foreach (var p in Positions.Values)
            {
                if (p.MarketPosition != MarketPosition.Flat) return true;
            }
            return false;
        }

        // Re-judges the current trade total from the streak as it stood before this trade was
        // settled, so calling it repeatedly as late fills arrive is idempotent rather than
        // cumulative. A scratch trade leaves the streak untouched in either direction.
        private void ApplyTradeJudgement(RiskConfig config)
        {
            ConsecutiveLosses = ConsecutiveLossesBeforeSettlement;

            if (OpenTradeRealizedDelta < -0.01)
                ConsecutiveLosses++;
            else if (OpenTradeRealizedDelta > 0.01)
                ConsecutiveLosses = 0;

            if (config != null && config.Overtrading != null
                && config.Overtrading.MaxConsecutiveLosses > 0
                && ConsecutiveLosses >= config.Overtrading.MaxConsecutiveLosses
                && config.Overtrading.CooldownMinutes > 0)
            {
                CooldownUntil = DateTime.UtcNow.AddMinutes(config.Overtrading.CooldownMinutes);
            }
        }

        // Judges the trade that just closed. Called on flat transitions and on flips (a flip is
        // a close plus an entry in one update).
        private void SettleClosedTrade(RiskConfig config)
        {
            ConsecutiveLossesBeforeSettlement = ConsecutiveLosses;
            ApplyTradeJudgement(config);
            ClosedTradeAwaitingLateFills = true;
        }

        public bool UpdatePosition(Account account, Instrument instrument, MarketPosition position, int quantity, double avgPrice, double unrealizedPnL, RiskConfig config)
        {
            if (quantity == 0)
            {
                position = MarketPosition.Flat;
            }

            string instrumentName = instrument.FullName;
            if (!Positions.TryGetValue(instrumentName, out var pState))
            {
                pState = new PositionState(instrument);
                Positions[instrumentName] = pState;
            }

            bool stateChanged = false;

            bool wasNonFlat = pState.MarketPosition != MarketPosition.Flat;
            bool isNonFlat = position != MarketPosition.Flat;
            bool isFlip = wasNonFlat && isNonFlat && position != pState.MarketPosition;

            // Treat a flip as a close of the old trade followed by a new entry.
            if ((position == MarketPosition.Flat && wasNonFlat) || isFlip)
            {
                pState.LastFlatTransition = DateTime.UtcNow;
                stateChanged = true;

                // P1-16: the trade is over -- judge it once, on its net realized result.
                SettleClosedTrade(config);

                if (isFlip)
                {
                    // NinjaTrader collapsed a close + reverse into one update.
                    // Log it so shadow data reveals how often flips occur.
                    NinjaTrader.Code.Output.Process(
                        $"[RiskGuard] FLIP detected on {AccountName}/{instrumentName}: " +
                        $"{pState.MarketPosition} -> {position}. Counted as close+entry.",
                        PrintTo.OutputTab1);
                }
            }

            // --- OPEN side: a new entry begins (flat->nonflat, or the new leg of a flip) ---
            if ((isNonFlat && !wasNonFlat) || isFlip)
            {
                pState.LastNonFlatTransition = DateTime.UtcNow;

                // A flip closes the old position and opens a new opposite leg in one
                // update. Reset the per-open-position peak-giveback tracking so the
                // new leg is not judged against the prior direction's peak.
                if (isFlip)
                {
                    PeakOpenGain = 0.0;
                    PeakGivebackTriggered = false;
                    PeakGivebackLastTriggerUnrealized = double.NaN;
                }

                // Debounce multi-contract / split-order trade count increment:
                // Only increment TradesToday if this is a genuine new trade lifecycle
                // (either a flip, or position was flat for > 1000ms, or initial entry).
                bool isGenuineNewTrade = isFlip || pState.LastFlatTransition == DateTime.MinValue ||
                                         (DateTime.UtcNow - pState.LastFlatTransition).TotalMilliseconds > 1000;

                if (isGenuineNewTrade)
                {
                    TradesToday++; // Increment trade count
                }

                // P1-16: a new trade starts with a clean slate. Until this point the previous
                // trade's total and pre-settlement streak are deliberately retained so a late
                // fill can revise its judgement.
                ClosedTradeAwaitingLateFills = false;
                OpenTradeRealizedDelta = 0.0;
                ConsecutiveLossesBeforeSettlement = ConsecutiveLosses;
                stateChanged = true;
            }
            else if (position == MarketPosition.Flat && wasNonFlat)
            {
                pState.LastNonFlatTransition = DateTime.MinValue;
            }

            pState.MarketPosition = position;
            pState.Quantity = quantity;
            pState.AveragePrice = avgPrice;
            pState.UnrealizedPnL = unrealizedPnL;

            // When the account returns to flat, reset the per-open-position
            // peak-giveback tracking so it cannot carry into the next trade.
            if (position == MarketPosition.Flat && wasNonFlat)
            {
                bool accountNowFlat = true;
                foreach (var pos in Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat)
                    {
                        accountNowFlat = false;
                        break;
                    }
                }

                if (accountNowFlat)
                {
                    PeakOpenGain = 0.0;
                    PeakGivebackTriggered = false;
                    PeakGivebackLastTriggerUnrealized = double.NaN;
                }
            }

            return stateChanged;
        }

        public void RecordExecution(string instrument, string action, int quantity, double price)
        {
            // Simple calculation of PnL can be done if execution updates are matched,
            // but in practice NinjaTrader handles account balance updates directly.
        }
    }
```
### REGION id="EvaluatePnLRules"  file=scripts/ninjatrader/addons/RiskGuardAddOn.cs  lines 1423-1596
Purpose: consistent basis, preconditions, latch
```csharp
        internal List<GuardAction> EvaluatePnLRules(Account account, AccountState stateModel)
        {
            var actions = new List<GuardAction>();
            if (!_isArmed) return actions;
            if (_config.ExcludedAccounts != null && _config.ExcludedAccounts.Contains(stateModel.AccountName)) return actions;

            var profile = GetResolvedProfile(account);
            if (profile == null) return actions;

            double currentPnL = stateModel.RealizedPnL + stateModel.UnrealizedPnL;

            // Daily Loss
            if (currentPnL < -profile.DailyLossLimit)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "DAILY_LOSS_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.PnLRules.LockoutMinutes > 0)
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.PnLRules.LockoutMinutes);
                    _stateDirty = true;
                }
            }

            // Trailing Drawdown
            //
            // P1-18: FirmMirror implements the firm's real trailing model, whose high-water mark
            // typically does NOT reset daily, while the rule below runs against a session-reset
            // PeakEquity. Where the firm rule is actually in effect for this account it owns the
            // decision and this one would double-fire on the same event.
            //
            // Keying on FirmMirror.Enabled alone would be a protection *removal*: on a config
            // where FirmMirror is enabled but its TrailingDD sub-rule is off and the account is
            // unmapped -- the shape observed live on 2026-08-07 -- that would skip the rule below
            // while the firm rule evaluates nothing, leaving the account with no trailing-drawdown
            // cover at all. So resolve what is actually in effect for THIS account.
            bool firmTrailingInEffect = false;
            if (_config.FirmMirror != null && _config.FirmMirror.Enabled)
            {
                var fmEff = ResolveEffectiveFirmConfig(_config.FirmMirror, stateModel.AccountName);
                firmTrailingInEffect = fmEff != null && fmEff.TrailingDD != null && fmEff.TrailingDD.Enabled;
            }

            // Keep tracking the peak either way, so the value stays meaningful if the firm rule
            // is later disabled and this rule resumes ownership.
            if (currentPnL > stateModel.PeakEquity)
                stateModel.PeakEquity = currentPnL;
            if (!firmTrailingInEffect && currentPnL < stateModel.PeakEquity - profile.TrailingDrawdown)
            {
                actions.Add(new GuardAction
                {
                    AccountName = stateModel.AccountName,
                    ActionType = GuardActionType.FlattenPosition,
                    RuleId = "TRAILING_DD_BREACH"
                });
                if (!stateModel.IsLockedOut)
                {
                    stateModel.IsLockedOut = true;
                    if (_config.PnLRules.LockoutMinutes > 0)
                        stateModel.LockoutUntil = DateTime.UtcNow.AddMinutes(_config.PnLRules.LockoutMinutes);
                    _stateDirty = true;
                }
            }

            // Prop Firm Protection Suite Integrations (News Shield, Target Profit Lock, Peak Giveback)
            var propSuite = PropFirmProtectionSuite.Instance;
            if (propSuite != null && propSuite.Config != null)
            {
                // Peak Open Gain tracks the running peak of unrealized PnL for
                // the current open position. It resets when the account is flat
                // and only rises while a position is open.
                bool accountIsFlat = true;
                foreach (var pos in stateModel.Positions.Values)
                {
                    if (pos.MarketPosition != MarketPosition.Flat)
                    {
                        accountIsFlat = false;
                        break;
                    }
                }

                if (!accountIsFlat)
                {
                    if (stateModel.UnrealizedPnL > stateModel.PeakOpenGain)
                    {
                        // New peak = new episode. Re-arm the giveback latch.
                        stateModel.PeakOpenGain = stateModel.UnrealizedPnL;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        _stateDirty = true;
                    }
                }
                else
                {
                    bool needsReset = stateModel.PeakOpenGain != 0.0
                        || stateModel.PeakGivebackTriggered
                        || !double.IsNaN(stateModel.PeakGivebackLastTriggerUnrealized);
                    if (needsReset)
                    {
                        stateModel.PeakOpenGain = 0.0;
                        stateModel.PeakGivebackTriggered = false;
                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;
                        _stateDirty = true;
                    }
                }

                if (propSuite.Config.EnableNewsShield && propSuite.IsInNewsWindow(DateTime.UtcNow, propSuite.Config.NewsBufferMinutesBefore, propSuite.Config.NewsBufferMinutesAfter))
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        RuleId = "NEWS_SHIELD_LOCKOUT"
                    });
                    if (!stateModel.IsLockedOut)
                    {
                        stateModel.IsLockedOut = true;
                        _stateDirty = true;
                    }
                }

                // P1-17: EvaluationTargetProfit is a cumulative, multi-day evaluation target.
                // Feeding it the session-scoped RealizedPnL meant it only fired if the whole
                // target was cleared in a single day. TotalRealizedPnL = banked + this session.
                if (propSuite.EvaluateProfitTargetLock(stateModel.TotalRealizedPnL, propSuite.Config))
                {
                    actions.Add(new GuardAction
                    {
                        AccountName = stateModel.AccountName,
                        ActionType = GuardActionType.FlattenPosition,
                        RuleId = "EVALUATION_TARGET_REACHED"
                    });
                    if (!stateModel.IsLockedOut)
                    {
                        stateModel.IsLockedOut = true;
                        _stateDirty = true;
                    }
                }

                if (!accountIsFlat && stateModel.PeakOpenGain > 0)
                {
                    if (propSuite.EvaluatePeakEquityGiveback(stateModel.PeakOpenGain, stateModel.UnrealizedPnL, propSuite.Config))
                    {
                        bool alreadyTriggered = stateModel.PeakGivebackTriggered;
                        bool worsenedSinceTrigger = alreadyTriggered
                            && stateModel.UnrealizedPnL < stateModel.PeakGivebackLastTriggerUnrealized;

                        // Fire on the first breach of the episode, and re-fire if the
                        // position gives back further than the prior trigger point.
                        // This prevents a silently-failed flatten from leaving the
                        // position unprotected as the loss continues to deepen.
                        if (!alreadyTriggered || worsenedSinceTrigger)
                        {
                            actions.Add(new GuardAction
                            {
                                AccountName = stateModel.AccountName,
                                ActionType = GuardActionType.FlattenPosition,
                                RuleId = "PEAK_GIVEBACK_BREACH"
                            });
                            stateModel.PeakGivebackTriggered = true;
                            stateModel.PeakGivebackLastTriggerUnrealized = stateModel.UnrealizedPnL;
                            _stateDirty = true;
                        }
                    }
                }
            }

            return actions;
        }
```
### REGION id="EvaluatePeakEquityGiveback"  file=scripts/ninjatrader/addons/PropFirmProtectionSuite.cs  lines 109-126
Purpose: document + harden the predicate
```csharp
        public bool EvaluatePeakEquityGiveback(double peakOpenGain, double currentUnrealized, PropFirmProtectionConfig config = null)
        {
            // Both arguments must be unrealized-only PnL in dollars. Passing a
            // total-equity peak combined with unrealized PnL causes spurious
            // giveback breaches when the account is flat after a profitable session.
            var cfg = config ?? Config;
            if (cfg == null || !cfg.EnablePeakEquityProtection || peakOpenGain <= 0 || currentUnrealized >= peakOpenGain) return false;
            // P1-40: the test below is proportional, so without an absolute floor a peak of one
            // tick ($0.50 on MNQ) turns any retrace into a >=100% giveback. Live on 2026-08-07
            // that fired six times in 36 seconds, first 2.4s after entry with the position down
            // $1.00; in an acting mode it would flatten nearly every trade on entry. Below the
            // floor there is no meaningful profit to protect, and the daily-loss and stop-guard
            // rules already cover the downside.
            if (peakOpenGain < cfg.MinPeakGainDollars) return false;
            double giveback = peakOpenGain - currentUnrealized;
            double givebackPct = giveback / peakOpenGain;
            return givebackPct >= cfg.MaxPeakGivebackPct;
        }
```
Return one block per region id above, in the same order. No other output.