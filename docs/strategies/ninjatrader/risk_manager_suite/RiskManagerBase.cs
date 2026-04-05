#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
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
        [Display(Name = "Policy (BreakevenTrail / FixedTarget)", Order = 3, GroupName = "Trade Management")]
        public string TradePolicy { get; set; }

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

        // ──────────────────────────────────────────────────────────────
        // STATE FIELDS
        // ──────────────────────────────────────────────────────────────

        // Session state — reset every day
        protected DateTime currentTradingDate;
        protected int      todayTradeCount;
        protected int      consecutiveLosers;
        protected double   sessionPnL;
        protected bool     isDoneForDay;
        protected bool     isPaused;
        protected DateTime pauseUntil;

        // Trade state — reset on each entry
        protected double entryPrice;
        protected double initialStopPrice;
        protected double currentStopPrice;
        protected double riskPoints;
        protected bool   breakevenMoved;
        protected bool   tradeIsActive;
        protected string tradeDirection;

        // Account state — persists across sessions for the whole backtest
        protected double accountEquity;
        protected double highWaterMark;
        protected bool   accountBlown;

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
                EntriesPerDirection          = 1;
                EntryHandling                = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds    = 60;
                IsFillLimitOnTouch           = false;
                TraceOrders                  = false;
                BarsRequiredToTrade          = 50;
                StartBehavior                = StartBehavior.WaitUntilFlat;
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
                EarliestEntry = 930;
                LatestEntry   = 1430;
                FlattenBy     = 1545;

                // Trade management defaults
                StopAtrMult         = 2.0;
                AtrPeriod           = 14;
                TradePolicy         = "BreakevenTrail";
                BreakevenTriggerR   = 1.0;
                TrailAtrMult        = 2.0;
                TargetRMultiple     = 2.0;

                SetStrategyDefaults();
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, 5);
                ConfigureStrategy();
            }
            else if (State == State.DataLoaded)
            {
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
                return;

            if (CurrentBars[0] < BarsRequiredToTrade || CurrentBars[1] < BarsRequiredToTrade)
                return;

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
                return;
            }

            // ── Entry gate ──
            if (!CanEnterTrade(currentTime))
                return;

            int signal = CheckForSignal();
            if (signal == 0)
                return;

            double atr = GetCurrentATR();
            if (atr <= 0)
                return;

            double stopDistance = StopAtrMult * atr;
            if (signal == 1)
                EnterTrade("Long",  Closes[0][0], Closes[0][0] - stopDistance, stopDistance);
            else if (signal == -1)
                EnterTrade("Short", Closes[0][0], Closes[0][0] + stopDistance, stopDistance);
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
            tradeIsActive     = false;
            breakevenMoved    = false;
            // NOTE: accountBlown intentionally NOT reset here —
            // it persists across sessions for the life of the backtest
        }

        // ──────────────────────────────────────────────────────────────
        // ENTRY GATE
        // ──────────────────────────────────────────────────────────────

        private bool CanEnterTrade(int currentTime)
        {
            // Account-level blocks
            if (accountBlown && StopOnAccountBlown)
                return false;

            // Session-level blocks
            if (isDoneForDay)
                return false;

            // Pause window
            if (isPaused)
            {
                if (Times[0][0] < pauseUntil)
                    return false;

                // Pause expired
                isPaused = false;
            }

            // Max trades per day
            if (todayTradeCount >= MaxTradesPerDay)
                return false;

            // Time fence
            if (currentTime < EarliestEntry * 100 || currentTime > LatestEntry * 100)
                return false;

            // ATR sanity
            double atr = GetCurrentATR();
            if (atr <= 0)
                return false;

            // Daily max loss — only blocks when session is already losing
            // Math.Abs was wrong: it also blocked entries on winning days
            double potentialLoss = StopAtrMult * atr * GetPointValue() * Math.Max(1, DefaultQuantity);
            if (sessionPnL - potentialLoss < -DailyMaxLoss)
                return false;

            return true;
        }

        // ──────────────────────────────────────────────────────────────
        // TRADE ENTRY
        // ──────────────────────────────────────────────────────────────

        private void EnterTrade(string direction, double entry, double stop, double stopDist)
        {
            string signalName = GetSignalName(direction);

            entryPrice        = entry;
            initialStopPrice  = stop;
            currentStopPrice  = stop;
            riskPoints        = stopDist;
            breakevenMoved    = false;
            tradeIsActive     = true;
            tradeDirection    = direction;

            if (direction == "Long")
            {
                EnterLong(1, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);

                if (TradePolicy == "FixedTarget")
                    SetProfitTarget(signalName, CalculationMode.Price, entry + TargetRMultiple * riskPoints);
            }
            else
            {
                EnterShort(1, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);

                if (TradePolicy == "FixedTarget")
                    SetProfitTarget(signalName, CalculationMode.Price, entry - TargetRMultiple * riskPoints);
            }

            todayTradeCount++;

            Print(string.Format("[{0}] ENTRY {1} @ {2:F2} | Stop {3:F2} | Risk {4:C} | Trade #{5}",
                GetStrategyName(), direction, entry, stop,
                stopDist * GetPointValue(), todayTradeCount));
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

            double currentPrice    = Closes[0][0];
            double unrealizedPnL   = GetUnrealizedPnL(currentPrice);

            // Intraday max loss including open position
            if (sessionPnL + unrealizedPnL <= -DailyMaxLoss)
            {
                FlattenPosition("Daily max loss breached (with open PnL)");
                isDoneForDay = true;
                return;
            }

            if (TradePolicy == "BreakevenTrail")
                ManageBreakevenTrail(currentPrice);
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
            // Only react when the position has just closed AND we were tracking a trade
            // Using AND (not OR) so entry fills are ignored
            if (!tradeIsActive || Position.MarketPosition != MarketPosition.Flat)
                return;

            tradeIsActive = false;

            // Use execution data directly — more reliable than SystemPerformance in realtime
            double pnl = 0;
            if (SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                pnl = lastTrade.ProfitCurrency;
            }

            sessionPnL += pnl;

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

            Print(string.Format("[{0}] EXIT | PnL: {1:C} | Session: {2:C} | Trades: {3} | ConsecL: {4} | DoneForDay: {5}",
                GetStrategyName(), pnl, sessionPnL,
                todayTradeCount, consecutiveLosers, isDoneForDay));
        }

        // ──────────────────────────────────────────────────────────────
        // HELPERS
        // ──────────────────────────────────────────────────────────────

        protected double GetCurrentATR()
        {
            if (CurrentBars[1] < AtrPeriod)
                return 0;
            return atrIndicator[0];
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
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong(reason, GetSignalName("Long"));
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort(reason, GetSignalName("Short"));

            Print(string.Format("[{0}] FLATTEN — {1}", GetStrategyName(), reason));
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

        protected double Close5m(int barsAgo = 0) => Closes[1][barsAgo];
        protected double High5m(int barsAgo  = 0) => Highs[1][barsAgo];
        protected double Low5m(int barsAgo   = 0) => Lows[1][barsAgo];

        private string GetSignalName(string direction)
        {
            return string.Format("{0}_{1}", GetStrategyName(), direction);
        }
    }
}