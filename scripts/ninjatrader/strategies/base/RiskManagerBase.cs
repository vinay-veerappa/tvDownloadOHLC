#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public enum TradePolicyType
    {
        CoverTheQueen,
        BreakevenTrail,
        FixedTarget,
        BaseHits,
        SupertrendTrail
    }

    public abstract class RiskManagerBase : Strategy
    {
        // ──────────────────────────────────────────────────────────────
        // INPUT PARAMETERS
        // ──────────────────────────────────────────────────────────────

        #region Risk Management Parameters
        [NinjaScriptProperty]
        [Display(Name = "Starting Account Balance ($)", Order = 0, GroupName = "Risk Management")]
        public double StartingAccountBalance { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Daily Max Loss ($)", Order = 1, GroupName = "Risk Management")]
        public double DailyMaxLoss { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Consecutive Losers (pause)", Order = 2, GroupName = "Risk Management")]
        public int MaxConsecutiveLosers { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pause Minutes After Consec Loss", Order = 3, GroupName = "Risk Management")]
        public int PauseMinutes { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Hard Stop Consecutive Losers (done for day)", Order = 4, GroupName = "Risk Management")]
        public int HardStopConsecutiveLosers { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Trades Per Day", Order = 5, GroupName = "Risk Management")]
        public int MaxTradesPerDay { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trailing Drawdown ($)", Order = 6, GroupName = "Risk Management")]
        public double TrailingDrawdown { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Trading When Account Blown", Order = 7, GroupName = "Risk Management")]
        public bool StopOnAccountBlown { get; set; }
        #endregion

        #region Time Parameters
        [NinjaScriptProperty]
        [Display(Name = "Bars Required To Trade", Order = 0, GroupName = "Time")]
        public int BarsRequiredToTradeParam { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Earliest Entry (HHMM)", Order = 1, GroupName = "Time")]
        public int EarliestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Latest Entry (HHMM)", Order = 2, GroupName = "Time")]
        public int LatestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten By (HHMM)", Order = 3, GroupName = "Time")]
        public int FlattenBy { get; set; }
        #endregion

        #region Trade Management Parameters
        [NinjaScriptProperty]
        [Display(Name = "Stop ATR Multiplier", Order = 1, GroupName = "Trade Management")]
        public double StopAtrMult { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "ATR Period", Order = 2, GroupName = "Trade Management")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade Policy", Description = "Trade management and profit target policy", Order = 3, GroupName = "Trade Management")]
        public TradePolicyType TradePolicy { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "BE Trigger (R-multiple)", Order = 4, GroupName = "Trade Management")]
        public double BreakevenTriggerR { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trail ATR Multiplier", Order = 5, GroupName = "Trade Management")]
        public double TrailAtrMult { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Target R-Multiple", Order = 6, GroupName = "Trade Management")]
        public double TargetRMultiple { get; set; }
        #endregion

        #region Timeframe Configuration
        /// <summary>
        /// When true (default), adds a 5-minute secondary series and computes ATR on it.
        /// Range-based strategies (IB, ORB) should set this false in SetStrategyDefaults()
        /// and override GetCurrentATR() to return their range-based risk metric instead.
        /// When false, Close5m/High5m/Low5m helpers MUST NOT be called.
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Add Secondary Timeframe (5m)", Order = 0, GroupName = "Timeframe")]
        public bool AddSecondaryTimeframe { get; set; }

        /// <summary>
        /// When true, emits verbose [DBG]/[DIAG] Log() diagnostics for every gate in
        /// OnBarUpdate/CanEnterTrade/CheckForSignal. Set false for production/live.
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode (verbose logging)", Order = 1, GroupName = "Timeframe")]
        public bool DebugMode { get; set; }
        #endregion

        // ──────────────────────────────────────────────────────────────
        // STATE FIELDS
        // ──────────────────────────────────────────────────────────────

        // Session state — local per-strategy (trade-level counters delegated to RiskGatekeeper in live mode)
        protected DateTime currentTradingDate;

        // Trade state — reset on each entry
        protected double entryPrice;
        protected double initialStopPrice;
        protected double currentStopPrice;
        protected double riskPoints;
        protected bool   breakevenMoved;
        protected bool   tradeIsActive;
        protected string tradeDirection;
        protected string entrySignalName;  // set by EnterWithRangeStop / EnterTrade

        // Backtest-only account state (not used in live mode — RiskGatekeeper owns this)
        protected double accountEquity;
        protected double highWaterMark;
        protected bool   accountBlown;
        protected int    todayTradeCount;
        protected int    consecutiveLosers;
        protected double sessionPnL;
        protected bool   isDoneForDay;
        protected bool   isPaused;
        protected DateTime pauseUntil;

        // Indicator
        protected ATR atrIndicator;

        // ──────────────────────────────────────────────────────────────
        // LIFECYCLE
        // ──────────────────────────────────────────────────────────────

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                  = "Risk Manager Base — inherited by all strategies";
                Name                         = "RiskManagerBase";
                Calculate                    = Calculate.OnBarClose;
                EntriesPerDirection          = 2; // Allow multi-bracket entries (Queen + Runner)
                EntryHandling                = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds    = 60;
                IsFillLimitOnTouch           = false;
                TraceOrders                  = false;
                BarsRequiredToTrade          = 1;   // FIX: was 50 — blocked IB entries for 250 min on 5-min secondary
                BarsRequiredToTradeParam     = 1;   // exposed as NinjaScriptProperty so SA params can override
                StartBehavior                = StartBehavior.AdoptAccountPosition;
                RealtimeErrorHandling        = RealtimeErrorHandling.StopCancelClose;

                // Risk defaults
                StartingAccountBalance    = 50000;
                DailyMaxLoss              = 400;
                MaxConsecutiveLosers      = 2;
                PauseMinutes              = 30;
                HardStopConsecutiveLosers = 3;
                MaxTradesPerDay           = 3;
                TrailingDrawdown          = 2000;
                StopOnAccountBlown        = false; // log only by default — don't kill backtest

                // Time defaults
                BarsRequiredToTradeParam = 1;  // default: 1 bar warmup (SA can override via params)
                EarliestEntry = 930;
                LatestEntry   = 1430;
                FlattenBy     = 1545;

                // Trade management defaults
                StopAtrMult         = 2.0;
                AtrPeriod           = 14;
                TradePolicy         = TradePolicyType.CoverTheQueen;
                BreakevenTriggerR   = 1.0;
                TrailAtrMult        = 2.0;
                TargetRMultiple     = 2.0;

                // Timeframe — default true for backward compat with ATR-based strategies.
                // Range-based strategies (IB/ORB) override to false in SetStrategyDefaults().
                AddSecondaryTimeframe = true;

                // DebugMode — default true for backtest diagnostics. Set false for live.
                DebugMode = true;

                SetStrategyDefaults();
            }
            else if (State == State.Configure)
            {
                // Apply BarsRequiredToTradeParam here — NT8 does NOT allow setting
                // BarsRequiredToTrade from OnBarUpdate (throws "cannot be set from this state").
                if (BarsRequiredToTradeParam > 0)
                    BarsRequiredToTrade = BarsRequiredToTradeParam;

                // Only add the 5-min secondary when the strategy actually uses it.
                // Range-based strategies set AddSecondaryTimeframe=false and override
                // GetCurrentATR() to return their range-based risk metric.
                if (AddSecondaryTimeframe)
                    AddDataSeries(BarsPeriodType.Minute, 5);
                ConfigureStrategy();
            }
            else if (State == State.DataLoaded)
            {
                // Only construct the ATR indicator when the secondary series exists.
                // When AddSecondaryTimeframe=false, atrIndicator stays null and
                // GetCurrentATR() returns 0 unless overridden by the subclass.
                if (AddSecondaryTimeframe)
                    atrIndicator = ATR(BarsArray[1], AtrPeriod);

                // Account state — initialise once from the parameter
                // HWM starts at the same value so no phantom drawdown on day 1
                accountEquity  = StartingAccountBalance;
                highWaterMark  = StartingAccountBalance;
                accountBlown   = false;

                currentTradingDate = DateTime.MinValue;

                ResetSessionState();
                InitializeStrategy();
            }
        }

        // ──────────────────────────────────────────────────────────────
        // ABSTRACT HOOKS — implemented by each child strategy
        // ──────────────────────────────────────────────────────────────

        protected abstract void   SetStrategyDefaults();
        protected abstract void   ConfigureStrategy();
        protected abstract void   InitializeStrategy();
        protected abstract int    CheckForSignal();   // return 1 = long, -1 = short, 0 = flat
        protected abstract string GetStrategyName();

        // ──────────────────────────────────────────────────────────────
        // BAR UPDATE
        // ──────────────────────────────────────────────────────────────

        protected override void OnBarUpdate()
        {
            // Only process the primary (1-min) series
            if (BarsInProgress != 0)
            {
                if (DebugMode && CurrentBar % 200 == 0) Log($"[DBG] BIP!=0 skipping: BarsInProgress={BarsInProgress} bar={CurrentBar}", LogLevel.Information);
                return;
            }

            // NOTE: BarsRequiredToTrade is now set in State.Configure (not here — NT8 throws
            // "cannot be set from this state" if set during OnBarUpdate).

            // Gate on primary series always; gate on secondary only when it exists.
            // When AddSecondaryTimeframe=false, there is no BarsArray[1] to check.
            if (CurrentBars[0] < BarsRequiredToTrade)
            {
                if (DebugMode && CurrentBar % 200 == 0) Log($"[DBG] BarsRequired gate: CurrentBars[0]={CurrentBars[0]} < BRT={BarsRequiredToTrade}", LogLevel.Information);
                return;
            }
            if (AddSecondaryTimeframe && CurrentBars[1] < BarsRequiredToTrade)
            {
                if (DebugMode && CurrentBar % 200 == 0) Log($"[DBG] Secondary BRT gate: CurrentBars[1]={CurrentBars[1]} < BRT={BarsRequiredToTrade}", LogLevel.Information);
                return;
            }

            // ── New session detection ──
            DateTime barDate = Times[0][0].Date;
            if (barDate != currentTradingDate)
                OnNewSession(barDate);

            // ── End-of-day flatten ──
            int currentTime = ToTime(Times[0][0]);
            if (currentTime >= FlattenBy * 100 && Position.MarketPosition != MarketPosition.Flat)
            {
                FlattenPosition("Flatten by time");
                return;
            }

            // ── Manage open trade ──
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManageOpenTrade();
                // FIX: don't blindly return — ManageOpenTrade may have just flattened
                // us (e.g. daily max loss). If we're now flat, fall through to the
                // entry gate so the rest of this bar is not wasted.
                if (Position.MarketPosition != MarketPosition.Flat)
                    return;
            }

            // ── Entry gate ──
            if (!CanEnterTrade(currentTime))
            {
                if (DebugMode)
                {
                    int h = Time[0].Hour;
                    bool inWindow = (h >= 10 && h <= 14);
                    if ((inWindow && CurrentBar % 10 == 0) || CurrentBar % 100 == 0)
                        Log($"[DBG] CanEnterTrade BLOCKED bar={CurrentBar} time={Time[0]:HH:mm} currentTime={currentTime} Earliest={EarliestEntry*100} Latest={LatestEntry*100} atr={GetCurrentATR()}", LogLevel.Information);
                }
                return;
            }

            int signal = CheckForSignal();
            if (signal == 0)
            {
                if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CheckForSignal=0 bar={CurrentBar} time={Time[0]:HH:mm}", LogLevel.Information);
                return;
            }

            double atr = GetCurrentATR();
            if (atr <= 0)
                return;

            double stopPrice = GetCustomStopPrice(signal, Closes[0][0]);
            double stopDistance = Math.Abs(Closes[0][0] - stopPrice);
            if (double.IsNaN(stopPrice) || stopDistance <= 0)
            {
                stopDistance = StopAtrMult * atr;
                stopPrice = signal == 1 ? Closes[0][0] - stopDistance : Closes[0][0] + stopDistance;
            }

            if (signal == 1)
                EnterTrade("Long",  Closes[0][0], stopPrice, stopDistance);
            else if (signal == -1)
                EnterTrade("Short", Closes[0][0], stopPrice, stopDistance);
        }

        // ──────────────────────────────────────────────────────────────
        // SESSION MANAGEMENT
        // ──────────────────────────────────────────────────────────────

        private void OnNewSession(DateTime newDate)
        {
            if (currentTradingDate != DateTime.MinValue)
                OnSessionClose();

            currentTradingDate = newDate;
            ResetSessionState();

            Print(string.Format("[{0}] {1} New session | Equity: {2:C} | HWM: {3:C} | Blown: {4}",
                GetStrategyName(), newDate.ToShortDateString(),
                accountEquity, highWaterMark, accountBlown));
        }

        private void OnSessionClose()
        {
            // Commit session PnL to running equity
            accountEquity += sessionPnL;

            // Ratchet high-water mark upward only
            if (accountEquity > highWaterMark)
                highWaterMark = accountEquity;

            // Trailing drawdown check — measured from peak, using real equity
            double drawdownFromPeak = highWaterMark - accountEquity;
            if (!accountBlown && drawdownFromPeak >= TrailingDrawdown)
            {
                accountBlown = true;
                Print(string.Format("[{0}] *** ACCOUNT BLOWN *** drawdown {1:C} exceeded limit {2:C} | Equity: {3:C}",
                    GetStrategyName(), drawdownFromPeak, TrailingDrawdown, accountEquity));

                // StopOnAccountBlown=false → log the event but keep running (useful for research)
                // StopOnAccountBlown=true  → halt all further trading
            }

            Print(string.Format("[{0}] Session close | PnL: {1:C} | Equity: {2:C} | HWM: {3:C} | DrawnFrom Peak: {4:C}",
                GetStrategyName(), sessionPnL, accountEquity, highWaterMark, drawdownFromPeak));
        }

        private void ResetSessionState()
        {
            todayTradeCount   = 0;
            consecutiveLosers = 0;
            sessionPnL        = 0;
            isDoneForDay      = false;
            isPaused          = false;
            pauseUntil        = DateTime.MinValue;

            // FIX: reset ALL trade-level fields so stale values can't
            // bleed into the next session or the next entry
            tradeIsActive    = false;
            breakevenMoved   = false;
            tradeDirection   = null;
            entrySignalName  = null;
            entryPrice       = 0;
            initialStopPrice = 0;
            currentStopPrice = 0;
            riskPoints       = 0;

            // NOTE: accountBlown intentionally NOT reset here —
            // it persists across sessions for the life of the backtest
        }

        // ──────────────────────────────────────────────────────────────
        // ENTRY GATE
        // ──────────────────────────────────────────────────────────────

        private bool CanEnterTrade(int currentTime)
        {
            string acctName = Account?.Name ?? "null";

            // ── Backtest / Historical mode bypass ──
            // In Strategy Analyzer or when processing historical chart bars (State == State.Historical),
            // Account.Name is "Backtest" or a Sim account. Skip gatekeeper live lockout checks.
            bool isBacktest = (State == State.Historical)
                           || acctName.IndexOf("backtest", StringComparison.OrdinalIgnoreCase) >= 0
                           || acctName.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0;

            // ── RiskGatekeeper check (live/sim mode — cross-strategy, cross-session) ──
            if (!isBacktest && !RiskGatekeeper.CanTrade(acctName))
            {
                if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL gatekeeper: acct={acctName} bar={CurrentBar}", LogLevel.Information);
                return false;
            }

            // ── Local backtest / fallback gates ──
            bool registered = !isBacktest && RiskGatekeeper.RegisteredAccounts.Contains(acctName,
                    StringComparer.OrdinalIgnoreCase);
            if (registered)
            {
                if (accountBlown && StopOnAccountBlown)
                {
                    if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL accountBlown: bar={CurrentBar}", LogLevel.Information);
                    return false;
                }

                if (isDoneForDay)
                {
                    if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL doneForDay: bar={CurrentBar}", LogLevel.Information);
                    return false;
                }

                if (isPaused)
                {
                    if (Times[0][0] < pauseUntil)
                    {
                        if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL paused: bar={CurrentBar} until={pauseUntil}", LogLevel.Information);
                        return false;
                    }
                    isPaused = false;
                }

                if (todayTradeCount >= MaxTradesPerDay)
                {
                    if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL maxTrades: bar={CurrentBar} {todayTradeCount}/{MaxTradesPerDay}", LogLevel.Information);
                    return false;
                }
            }

            // Time fence — always enforced locally (strategy-specific windows)
            if (currentTime < EarliestEntry * 100 || currentTime > LatestEntry * 100)
            {
                if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL timeFence: currentTime={currentTime} Earliest={EarliestEntry*100} Latest={LatestEntry*100} bar={CurrentBar}", LogLevel.Information);
                return false;
            }

            // NOTE: The GetCurrentATR()>0 sanity gate was REMOVED from here.
            // It created a circular deadlock: CanEnterTrade needs GetCurrentATR()>0,
            // which (for range-based strategies) needs rangeComplete=true, which is
            // only set inside CheckForSignal/FinalizeRange — but CheckForSignal is
            // called AFTER CanEnterTrade passes. So rangeComplete could never become
            // true, blocking all entries. The atr>0 check in OnBarUpdate (after
            // CheckForSignal returns non-zero) still protects the EnterTrade path.
            // Use the strategy's actual estimated risk distance for the daily-max-loss
            // potential calc. VIRTUAL so range-based subclasses override with their
            // real stop geometry (StopRMult * TargetLvl * rangeRange) instead of the
            // ATR formula (StopAtrMult * rangeRange), which over-estimates by ~8-16x
            // and would block legitimate entries on funded accounts with tight daily
            // loss limits. See GetPotentialLoss() / GetEstimatedRiskDistance().
            double potentialLoss = GetPotentialLoss();
            if (!isBacktest && RiskGatekeeper.WouldBreachDailyMaxLoss(Account.Name, potentialLoss))
            {
                if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL gatekeeperDailyMaxLoss: bar={CurrentBar} potentialLoss={potentialLoss}", LogLevel.Information);
                return false;
            }

            // Local fallback for daily max loss (only when NOT registered with gatekeeper AND not backtest)
            if (!isBacktest && !RiskGatekeeper.RegisteredAccounts.Contains(Account.Name,
                    StringComparer.OrdinalIgnoreCase))
            {
                if (sessionPnL - potentialLoss < -DailyMaxLoss)
                {
                    if (DebugMode && CurrentBar % 100 == 0) Log($"[DBG] CanEnterTrade FAIL localDailyMaxLoss: bar={CurrentBar} sessionPnL={sessionPnL} potentialLoss={potentialLoss} DailyMaxLoss={DailyMaxLoss}", LogLevel.Information);
                    return false;
                }
            }

            return true;
        }

        // ──────────────────────────────────────────────────────────────
        // TRADE ENTRY
        // ──────────────────────────────────────────────────────────────

        protected virtual (double stopPts, double tp1Pts, double tp2Pts) GetBaseHitsTargets()
        {
            string inst = (Instrument != null && Instrument.MasterInstrument != null) ? Instrument.MasterInstrument.Name.ToUpper() : "NQ";
            if (inst.Contains("NQ") || inst.Contains("MNQ"))
                return (10.0, 10.0, 20.0);
            if (inst.Contains("ES") || inst.Contains("MES"))
                return (2.50, 2.50, 5.00);
            if (inst.Contains("YM") || inst.Contains("MYM"))
                return (15.0, 15.0, 30.0);
            if (inst.Contains("RTY") || inst.Contains("M2K"))
                return (1.00, 1.25, 2.50);
            if (inst.Contains("CL") || inst.Contains("MCL"))
                return (0.10, 0.15, 0.30);
            if (inst.Contains("GC") || inst.Contains("MGC"))
                return (1.00, 1.25, 2.50);
            return (10.0, 10.0, 20.0); // Default to NQ
        }

        private void EnterTrade(string direction, double entry, double stop, double stopDist)
        {
            string signalName = GetSignalName(direction);

            // ── P1-149 sub-task 2: pre-trade contract-size refusal (strategy-side half) ──
            // The one enforcement gap RiskManagerBase strategies had: the per-account contract cap
            // (MaxContractsPerAccount) was configured, reported in the UI and enforced reactively by the
            // guard's MAX_SIZE_BREACH flatten -- but nothing on THIS entry path said no BEFORE the fill.
            // The decision lives in the pure, mutation-tested ContractCapGate; RiskGatekeeper.CanTradeSize
            // supplies this account's cap and delegates, so the strategy path and the bridge/order path
            // enforce the SAME rule. INERT unless an operator has set MaxContractsPerAccount > 0 (cap <= 0
            // allows everything), and a strictly-reducing order is NEVER refused, so this can only block a
            // size-INCREASING entry that would leave the account over its cap. Position.Quantity is an
            // ABSOLUTE magnitude and MarketPosition carries the side -- there is no sign to misread.
            {
                string sizeAcct = (Account != null) ? Account.Name : "";
                bool sizeIsBacktest = (State == State.Historical)
                                   || sizeAcct.IndexOf("backtest", StringComparison.OrdinalIgnoreCase) >= 0
                                   || sizeAcct.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0;
                if (!sizeIsBacktest)
                {
                    string orderSide = direction == "Long" ? "buy" : "sell";
                    var sizeDecision = RiskGatekeeper.CanTradeSize(
                        sizeAcct, 1, orderSide,
                        Position.MarketPosition.ToString(), Position.Quantity);
                    if (!sizeDecision.Allowed)
                    {
                        Log(string.Format("[RiskManagerBase] entry refused by contract cap: {0}",
                            sizeDecision.Reason), LogLevel.Warning);
                        return;
                    }
                }
            }

            if (TradePolicy == TradePolicyType.BaseHits)
            {
                var targets = GetBaseHitsTargets();
                stopDist = targets.stopPts;
                stop = direction == "Long" ? entry - targets.stopPts : entry + targets.stopPts;
            }

            entryPrice        = entry;
            initialStopPrice  = stop;
            currentStopPrice  = stop;
            riskPoints        = stopDist;
            breakevenMoved    = false;
            tradeIsActive     = true;
            tradeDirection    = direction;
            entrySignalName   = signalName;

            if (TradePolicy == TradePolicyType.CoverTheQueen)
            {
                double bpsPts = entry * 0.0010; // 10 Basis Points (approx 20-29 pts on NQ)
                double queenPts = Math.Max(bpsPts, riskPoints);
                double runnerPts = Math.Max(TargetRMultiple * riskPoints, queenPts * 2.5);

                if (direction == "Long")
                {
                    EnterLong(1, signalName + "_Queen");
                    SetStopLoss(signalName + "_Queen", CalculationMode.Price, stop, false);
                    SetProfitTarget(signalName + "_Queen", CalculationMode.Price, entry + queenPts);

                    EnterLong(1, signalName + "_Runner");
                    SetStopLoss(signalName + "_Runner", CalculationMode.Price, stop, false);
                    SetProfitTarget(signalName + "_Runner", CalculationMode.Price, entry + runnerPts);
                }
                else
                {
                    EnterShort(1, signalName + "_Queen");
                    SetStopLoss(signalName + "_Queen", CalculationMode.Price, stop, false);
                    SetProfitTarget(signalName + "_Queen", CalculationMode.Price, entry - queenPts);

                    EnterShort(1, signalName + "_Runner");
                    SetStopLoss(signalName + "_Runner", CalculationMode.Price, stop, false);
                    SetProfitTarget(signalName + "_Runner", CalculationMode.Price, entry - runnerPts);
                }
            }
            else if (direction == "Long")
            {
                EnterLong(1, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);

                double customTarget = GetCustomProfitTarget(1, entry, stopDist);
                if (!double.IsNaN(customTarget) && customTarget > entry)
                    SetProfitTarget(signalName, CalculationMode.Price, customTarget);
                else if (TradePolicy == TradePolicyType.FixedTarget)
                    SetProfitTarget(signalName, CalculationMode.Price, entry + TargetRMultiple * riskPoints);
                else if (TradePolicy == TradePolicyType.BaseHits)
                    SetProfitTarget(signalName, CalculationMode.Price, entry + GetBaseHitsTargets().tp1Pts);
            }
            else
            {
                EnterShort(1, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);

                double customTarget = GetCustomProfitTarget(-1, entry, stopDist);
                if (!double.IsNaN(customTarget) && customTarget < entry)
                    SetProfitTarget(signalName, CalculationMode.Price, customTarget);
                else if (TradePolicy == TradePolicyType.FixedTarget)
                    SetProfitTarget(signalName, CalculationMode.Price, entry - TargetRMultiple * riskPoints);
                else if (TradePolicy == TradePolicyType.BaseHits)
                    SetProfitTarget(signalName, CalculationMode.Price, entry - GetBaseHitsTargets().tp1Pts);
            }

            todayTradeCount++;

            Print(string.Format("[{0}] ENTRY {1} @ {2:F2} | Stop {3:F2} | Risk {4:C} | Trade #{5} | Policy {6}",
                GetStrategyName(), direction, entry, stop,
                stopDist * GetPointValue(), todayTradeCount, TradePolicy));
        }

        // ──────────────────────────────────────────────────────────────
        // OPEN TRADE MANAGEMENT
        // ──────────────────────────────────────────────────────────────

        private void ManageOpenTrade()
        {
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                tradeIsActive = false;
                return;
            }

            // If a flatten has already been submitted (tradeIsActive=false),
            // skip trade management — the exit order is pending fill and
            // managed orders have been cancelled.
            if (!tradeIsActive)
                return;

            double currentPrice    = Closes[0][0];
            double unrealizedPnL   = GetUnrealizedPnL(currentPrice);

            // Intraday max loss including open position
            if (sessionPnL + unrealizedPnL <= -DailyMaxLoss)
            {
                FlattenPosition("Daily max loss breached (with open PnL)");
                isDoneForDay = true;
                RiskGatekeeper.MarkDailyMaxLossBreached(Account.Name);
                return;
            }

            if (TradePolicy == TradePolicyType.BreakevenTrail)
                ManageBreakevenTrail(currentPrice);
            else if (TradePolicy == TradePolicyType.CoverTheQueen)
                ManageCoverTheQueen(currentPrice);
            else if (TradePolicy == TradePolicyType.BaseHits)
                ManageBaseHits(currentPrice);
            else if (TradePolicy == TradePolicyType.SupertrendTrail)
                ManageSupertrendTrail(currentPrice);
        }

        private void ManageCoverTheQueen(double currentPrice)
        {
            string runnerSignal = GetSignalName(tradeDirection) + "_Runner";
            double bpsPts = entryPrice * 0.0010;
            double queenPts = Math.Max(bpsPts, riskPoints);

            // Once price reaches Queen TP1, move Runner stop to Breakeven (+1 tick)
            if (!breakevenMoved)
            {
                bool queenHit = tradeDirection == "Long"
                    ? (currentPrice >= entryPrice + queenPts)
                    : (currentPrice <= entryPrice - queenPts);

                if (queenHit)
                {
                    breakevenMoved = true;
                    currentStopPrice = tradeDirection == "Long" ? entryPrice + TickSize : entryPrice - TickSize;
                    SetStopLoss(runnerSignal, CalculationMode.Price, currentStopPrice, false);
                    Print(string.Format("[{0}] CoverTheQueen TP1 Hit! Runner stop moved to BE @ {1:F2}", GetStrategyName(), currentStopPrice));
                }
            }

            // Trail Runner stop once Breakeven is secured
            if (breakevenMoved)
            {
                double atr = GetCurrentATR();
                if (atr <= 0) return;
                double trailDistance = TrailAtrMult * atr;

                if (tradeDirection == "Long")
                {
                    double newStop = currentPrice - trailDistance;
                    if (newStop > currentStopPrice)
                    {
                        currentStopPrice = newStop;
                        SetStopLoss(runnerSignal, CalculationMode.Price, currentStopPrice, false);
                    }
                }
                else
                {
                    double newStop = currentPrice + trailDistance;
                    if (newStop < currentStopPrice)
                    {
                        currentStopPrice = newStop;
                        SetStopLoss(runnerSignal, CalculationMode.Price, currentStopPrice, false);
                    }
                }
            }
        }

        /// <summary>
        /// Supertrend-style trailing stop: starts at entry -/+ trail_mult*ATR and only ratchets
        /// toward price. NEVER jumps to breakeven (unlike BreakevenTrail with trigger R=0).
        /// Mirrors Python supertrend_intraday_cost.py: stop = max(stop, high - trail_mult*ATR).
        /// </summary>
        private void ManageSupertrendTrail(double currentPrice)
        {
            string signalName = GetSignalName(tradeDirection);
            double atr = GetCurrentATR();
            if (atr <= 0) return;
            double trailDistance = TrailAtrMult * atr;

            // Ratchet on the BAR HIGH/LOW (Python parity: stop = max(stop, high - trail*ATR)),
            // not on close — a 5m bar that spikes through the stop must still fill it.
            if (tradeDirection == "Long")
            {
                double newStop = High[0] - trailDistance;
                if (newStop > currentStopPrice)
                {
                    currentStopPrice = newStop;
                    SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);
                }
            }
            else
            {
                double newStop = Low[0] + trailDistance;
                if (newStop < currentStopPrice)
                {
                    currentStopPrice = newStop;
                    SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);
                }
            }
        }

        private void ManageBaseHits(double currentPrice)
        {
            string signalName = GetSignalName(tradeDirection);
            var targets = GetBaseHitsTargets();

            if (!breakevenMoved)
            {
                bool triggerBE = tradeDirection == "Long"
                    ? (currentPrice >= entryPrice + (targets.tp1Pts * 0.8))
                    : (currentPrice <= entryPrice - (targets.tp1Pts * 0.8));

                if (triggerBE)
                {
                    breakevenMoved = true;
                    currentStopPrice = entryPrice;
                    SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);
                    Print(string.Format("[{0}] BaseHits Breakeven moved @ {1:F2}", GetStrategyName(), entryPrice));
                }
            }
        }

        private void ManageBreakevenTrail(double currentPrice)
        {
            string signalName = GetSignalName(tradeDirection);
            double currentR   = GetCurrentRMultiple(currentPrice);

            // Move stop to breakeven once trigger R is reached
            if (!breakevenMoved && currentR >= BreakevenTriggerR)
            {
                breakevenMoved   = true;
                currentStopPrice = entryPrice;
                SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);

                Print(string.Format("[{0}] Breakeven moved @ {1:F2} | R={2:F2}",
                    GetStrategyName(), entryPrice, currentR));
            }

            // Trail stop after breakeven
            if (breakevenMoved)
            {
                double atr = GetCurrentATR();
                if (atr <= 0)
                    return;

                double trailDistance = TrailAtrMult * atr;

                if (tradeDirection == "Long")
                {
                    double newStop = currentPrice - trailDistance;
                    if (newStop > currentStopPrice)
                    {
                        currentStopPrice = newStop;
                        SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);
                    }
                }
                else
                {
                    double newStop = currentPrice + trailDistance;
                    if (newStop < currentStopPrice)
                    {
                        currentStopPrice = newStop;
                        SetStopLoss(signalName, CalculationMode.Price, currentStopPrice, false);
                    }
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // EXECUTION UPDATE — only process closing fills
        // ──────────────────────────────────────────────────────────────

        protected override void OnExecutionUpdate(
            Execution execution, string executionId,
            double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            // FIX: Guard against entry fills triggering exit logic.
            // An entry fill leaves the position non-flat; an exit fill leaves it flat.
            // We also check tradeIsActive so we don't double-fire if multiple
            // exit fills arrive (e.g. partial fills).
            if (!tradeIsActive)
                return;

            // FIX: Use execution.Order to distinguish entry vs. exit orders.
            // Entry orders are Buy/BuyToCover/Sell (opening); exit orders are
            // the complementary direction that closes the position.
            // The simplest reliable check: position is flat after this fill.
            if (Position.MarketPosition != MarketPosition.Flat)
                return; // Still in a position — this was an entry or partial fill

            tradeIsActive = false;

            // PnL from the last completed trade (more reliable than execution.Price math)
            double pnl = 0;
            if (SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                pnl = lastTrade.ProfitCurrency;
            }

            // ── Update local backtest state ──
            sessionPnL += pnl;
            todayTradeCount++;

            if (pnl < 0)
            {
                consecutiveLosers++;

                if (consecutiveLosers >= HardStopConsecutiveLosers)
                {
                    isDoneForDay = true;
                    Print(string.Format("[{0}] DONE FOR DAY — {1} consecutive losers",
                        GetStrategyName(), consecutiveLosers));
                }
                else if (consecutiveLosers >= MaxConsecutiveLosers)
                {
                    isPaused   = true;
                    pauseUntil = Times[0][0].AddMinutes(PauseMinutes);
                    Print(string.Format("[{0}] PAUSED until {1} — {2} consecutive losers",
                        GetStrategyName(), pauseUntil.ToShortTimeString(), consecutiveLosers));
                }
            }
            else
            {
                consecutiveLosers = 0;
            }

            // ── Forward to RiskGatekeeper (live/sim — cross-strategy awareness) ──
            RiskGatekeeper.RecordTrade(Account.Name, pnl, time);

            Print(string.Format("[{0}] EXIT | PnL: {1:C} | Session: {2:C} | Trades: {3} | ConsecL: {4} | DoneForDay: {5}",
                GetStrategyName(), pnl, sessionPnL,
                todayTradeCount, consecutiveLosers, isDoneForDay));
        }

        // ──────────────────────────────────────────────────────────────
        // HELPERS
        // ──────────────────────────────────────────────────────────────

        /// <summary>
        /// Returns the current ATR value from the 5-min secondary series.
        /// VIRTUAL so range-based subclasses (IntradayStrategyBase) can override
        /// it to return their range-based risk metric (e.g. IB rangeRange) instead —
        /// this unblocks the CanEnterTrade atr&gt;0 gate as soon as the range completes,
        /// without waiting for the 5-min ATR to warm up.
        /// When AddSecondaryTimeframe=false, the base returns 0; subclasses MUST override.
        /// </summary>
        protected virtual double GetCurrentATR()
        {
            if (!AddSecondaryTimeframe || atrIndicator == null)
                return 0;
            if (CurrentBars[1] < AtrPeriod)
                return 0;
            return atrIndicator[0];
        }

        /// <summary>
        /// Estimated dollar loss if the next trade is stopped out. Used by the
        /// daily-max-loss gate in CanEnterTrade. VIRTUAL so range-based subclasses
        /// (IntradayStrategyBase) can override with their ACTUAL stop distance
        /// instead of the ATR formula, which over-estimates by ~8-16x for IB
        /// strategies and would block legitimate entries on funded accounts with
        /// tight daily loss limits (e.g. Apex $100/day).
        /// Default: StopAtrMult * GetCurrentATR() * PointValue * Qty (ATR-based).
        /// Range-based override: GetEstimatedRiskDistance() * PointValue * Qty.
        /// </summary>
        protected virtual double GetPotentialLoss()
        {
            double atrForRisk = GetCurrentATR();
            if (atrForRisk <= 0)
                atrForRisk = StopAtrMult * TickSize * 100;  // nominal fallback before range/warmup completes
            double riskDistance = StopAtrMult * atrForRisk;
            return riskDistance * GetPointValue() * Math.Max(1, DefaultQuantity);
        }

        protected double GetPointValue()
        {
            return Instrument.MasterInstrument.PointValue;
        }

        protected double GetCurrentRMultiple(double currentPrice)
        {
            if (riskPoints <= 0)
                return 0;

            return tradeDirection == "Long"
                ? (currentPrice - entryPrice) / riskPoints
                : (entryPrice - currentPrice) / riskPoints;
        }

        protected double GetUnrealizedPnL(double currentPrice)
        {
            double points = tradeDirection == "Long"
                ? currentPrice - entryPrice
                : entryPrice - currentPrice;

            return points * GetPointValue() * Math.Max(1, Position.Quantity);
        }

        protected void FlattenPosition(string reason)
        {
            // Plain market close — do NOT pass fromEntrySignal. Passing an entry
            // signal (ExitLong(fromEntry, reason)) cancels the managed
            // SetProfitTarget/SetStopLoss OCO immediately, but the market exit
            // fills on the NEXT bar in SA backtest. On that next bar
            // ManageOpenTrade sees an unprotected open position and triggers a
            // spurious "Daily max loss" exit (regression observed in v2-v6:
            // 15 false daily-max-loss exits, WR 63.4% -> 59.2%).
            //
            // A plain ExitLong()/ExitShort() submits a market exit without
            // touching the managed OCO. The managed orders auto-cancel when the
            // position goes flat from this fill. This was also the root cause of
            // the original bug: the old ExitLong(reason, GetSignalName) passed
            // "Flatten by time" as fromEntrySignal, which matched no entry, so
            // the exit never associated and the position survived to 17:00.
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong();
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort();

            // FIX: reset tradeIsActive immediately so OnBarUpdate doesn't stay
            // stuck in ManageOpenTrade on subsequent bars before the fill confirms.
            tradeIsActive = false;

            Print(string.Format("[{0}] FLATTEN — {1} at {2:HH:mm} (plain market close)",
                GetStrategyName(), reason, Times[0][0]));
        }

        protected int GetCurrentTimeInt()
        {
            return ToTime(Times[0][0]);
        }

        protected bool IsInTimeWindow(int startHHMM, int endHHMM)
        {
            int current = GetCurrentTimeInt();
            return current >= startHHMM * 100 && current <= endHHMM * 100;
        }

        // 5-min secondary helpers — ONLY valid when AddSecondaryTimeframe=true.
        // Calling these when the secondary was not added will throw an index error.
        protected double Close5m(int barsAgo = 0)
        {
            if (!AddSecondaryTimeframe) throw new InvalidOperationException("Close5m requires AddSecondaryTimeframe=true");
            return Closes[1][barsAgo];
        }
        protected double High5m(int barsAgo  = 0)
        {
            if (!AddSecondaryTimeframe) throw new InvalidOperationException("High5m requires AddSecondaryTimeframe=true");
            return Highs[1][barsAgo];
        }
        protected double Low5m(int barsAgo   = 0)
        {
            if (!AddSecondaryTimeframe) throw new InvalidOperationException("Low5m requires AddSecondaryTimeframe=true");
            return Lows[1][barsAgo];
        }

        protected virtual double GetCustomStopPrice(int signal, double entryPrice)
        {
            return double.NaN;
        }

        protected virtual double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            return double.NaN;
        }

        private string GetSignalName(string direction)
        {
            return string.Format("{0}_{1}", GetStrategyName(), direction);
        }
    }
}