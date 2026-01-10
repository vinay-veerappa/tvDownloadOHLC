#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ORBv5Strategy : Strategy
    {
        #region Variables
        // Opening Range
        private double orHigh = 0;
        private double orLow = 0;
        private bool orDefined = false;
        private bool rangeSynced = false;  // Flag to sync range with primary bar
        
        // State Tracking
        private int attempts = 0;
        private int longAttempts = 0;
        private int shortAttempts = 0;
        private bool hasWonToday = false;
        private bool priceReturnedToRange = true;
        private int lastExitBar = -1;
        private DateTime lastTradeDate = DateTime.MinValue;
        
        // Multi-TP State
        private bool tp1Hit = false;
        private bool tp2Hit = false;
        private double tradeEntryPrice = 0;
        private double currentTrailStop = 0;
        private bool isRunnerActive = false;
        private bool adaptiveTrailActivated = false;
        private int tp1Qty = 0;
        private int remainingQty = 0;
        
        // Daily Risk
        private double dayStartEquity = 0;
        private double dayHighEquity = 0;
        private bool isDailyLossHit = false;
        
        // Timezone
        private TimeZoneInfo estZone;
        private TimeZoneInfo chartZone;
        #endregion

        #region Properties
        // Core Settings
        [NinjaScriptProperty]
        [Display(Name = "OR Start Time", Order = 1, GroupName = "1. Core Settings")]
        public TimeSpan ORStartTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "OR End Time", Order = 2, GroupName = "1. Core Settings")]
        public TimeSpan OREndTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Trading End Time", Order = 3, GroupName = "1. Core Settings")]
        public TimeSpan TradingEndTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Hard Exit Time", Order = 4, GroupName = "1. Core Settings")]
        public TimeSpan HardExitTime { get; set; }

        // Entry Configuration
        [NinjaScriptProperty]
        [Display(Name = "Use Immediate Entry", Order = 1, GroupName = "2. Entry")]
        public bool UseImmediateEntry { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Min Displacement %", Order = 2, GroupName = "2. Entry")]
        public double MinDisplacement { get; set; }

        // Re-entry Rules
        [NinjaScriptProperty]
        [Display(Name = "Require Fresh Breakout", Order = 1, GroupName = "3. Re-entry")]
        public bool RequireFreshBreakout { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Max Attempts Per Day", Order = 2, GroupName = "3. Re-entry")]
        public int MaxAttempts { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Stop After Win", Order = 3, GroupName = "3. Re-entry")]
        public bool StopAfterWin { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Cooldown Bars", Order = 4, GroupName = "3. Re-entry")]
        public int CooldownBars { get; set; }

        // Take Profit Settings
        [NinjaScriptProperty]
        [Display(Name = "Use Single TP", Order = 1, GroupName = "4. Take Profit")]
        public bool UseSingleTP { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "TP1 %", Order = 2, GroupName = "4. Take Profit")]
        public double TP1Pct { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "TP1 Position %", Order = 3, GroupName = "4. Take Profit")]
        public double TP1Weight { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "TP2 %", Order = 4, GroupName = "4. Take Profit")]
        public double TP2Pct { get; set; }

        // Runner Management
        [NinjaScriptProperty]
        [Display(Name = "Use Trailing Stop", Order = 1, GroupName = "5. Runner")]
        public bool UseTrailingStop { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Use Adaptive Trail", Order = 2, GroupName = "5. Runner")]
        public bool UseAdaptiveTrail { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Move to Breakeven After TP1", Order = 3, GroupName = "5. Runner")]
        public bool MoveToBE { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Trail Offset %", Order = 4, GroupName = "5. Runner")]
        public double TrailOffsetPct { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Trail Activation %", Order = 5, GroupName = "5. Runner")]
        public double TrailActivationPct { get; set; }

        // Stop Loss & Risk
        [NinjaScriptProperty]
        [Display(Name = "Use Fixed SL", Order = 1, GroupName = "6. Risk")]
        public bool UseFixedSL { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Fixed SL %", Order = 2, GroupName = "6. Risk")]
        public double SLFixedPct { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Risk per Trade %", Order = 3, GroupName = "6. Risk")]
        public double RiskPercent { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Min Contracts", Order = 4, GroupName = "6. Risk")]
        public int MinContracts { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Max Contracts", Order = 5, GroupName = "6. Risk")]
        public int MaxContracts { get; set; }

        // Daily Risk
        [NinjaScriptProperty]
        [Display(Name = "Use Max Daily Loss", Order = 1, GroupName = "7. Daily Risk")]
        public bool UseMaxDailyLoss { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Max Daily Loss $", Order = 2, GroupName = "7. Daily Risk")]
        public double MaxDailyLossUSD { get; set; }

        // Filters
        [NinjaScriptProperty]
        [Display(Name = "Max Range %", Order = 1, GroupName = "8. Filters")]
        public double MaxRangePct { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Min Range %", Order = 2, GroupName = "8. Filters")]
        public double MinRangePct { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Use MAE Filter", Order = 3, GroupName = "8. Filters")]
        public bool UseMAEFilter { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "MAE Threshold %", Order = 4, GroupName = "8. Filters")]
        public double MAEThreshold { get; set; }
        
        // Debug
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode", Order = 1, GroupName = "9. Debug")]
        public bool DebugMode { get; set; }
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Opening Range Breakout V5 Strategy";
                Name = "ORBv5Strategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 5;
                
                // Default Values (all times in EST)
                ORStartTime = new TimeSpan(9, 30, 0);
                OREndTime = new TimeSpan(9, 31, 0);
                TradingEndTime = new TimeSpan(15, 0, 0);  // 3:00 PM EST
                HardExitTime = new TimeSpan(15, 50, 0);   // 3:50 PM EST
                
                UseImmediateEntry = true;
                MinDisplacement = 0;
                
                RequireFreshBreakout = false;
                MaxAttempts = 10;
                StopAfterWin = false;
                CooldownBars = 0;
                
                UseSingleTP = false;
                TP1Pct = 0.20;
                TP1Weight = 50;
                TP2Pct = 0.50;
                
                UseTrailingStop = true;
                UseAdaptiveTrail = true;
                MoveToBE = true;
                TrailOffsetPct = 0.25;
                TrailActivationPct = 0.50;
                
                UseFixedSL = false;
                SLFixedPct = 0.20;
                RiskPercent = 1.0;
                MinContracts = 1;
                MaxContracts = 20;
                
                UseMaxDailyLoss = true;
                MaxDailyLossUSD = 200;
                
                MaxRangePct = 0.25;
                MinRangePct = 0.03;
                UseMAEFilter = true;
                MAEThreshold = 0.05;
                
                DebugMode = false;
            }
            else if (State == State.Configure)
            {
                // Add any additional data series if needed
            }
            else if (State == State.DataLoaded)
            {
                // Initialize timezones
                try { estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
                catch { estZone = TimeZoneInfo.Local; }
                
                // Use NinjaTrader's chart timezone
                try { chartZone = Core.Globals.GeneralOptions.TimeZoneInfo; }
                catch { chartZone = TimeZoneInfo.Local; }
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            DateTime barTime = Time[0];
            
            // Convert to EST for time comparisons (from chart timezone to EST)
            DateTime estTime = TimeZoneInfo.ConvertTime(barTime, chartZone, estZone);
            TimeSpan currentTime = estTime.TimeOfDay;
            
            // Check for new day (using EST date)
            if (estTime.Date != lastTradeDate)
            {
                ResetDailyState();
                lastTradeDate = estTime.Date;
            }
            
            // Update daily equity tracking
            UpdateDailyEquity();
            
            // Define Opening Range (using EST time)
            DefineOpeningRange(estTime);
            
            // Look-back Range Sync - ensure the 9:30/9:31 bar's extremes are captured
            if (orDefined && !rangeSynced)
            {
                for (int i = 0; i <= 5; i++)
                {
                    if (CurrentBar - i < 0) continue;
                    
                    DateTime barTimeEST = TimeZoneInfo.ConvertTime(Time[i], estZone);
                    // Match 9:30 or 9:31 bar
                    if (barTimeEST.Hour == 9 && (barTimeEST.Minute == 30 || barTimeEST.Minute == 31))
                    {
                        // Force Sync: Capture bar's High/Low into range
                        if (High[i] > orHigh) orHigh = High[i];
                        if (Low[i] < orLow) orLow = Low[i];
                        rangeSynced = true;
                        break;
                    }
                }
            }
            
            // Check for trading window
            if (!orDefined)
                return;
            
            bool isTradingTime = currentTime > OREndTime && currentTime < TradingEndTime;
            bool isHardExit = currentTime >= HardExitTime;
            
            // Hard Exit
            if (isHardExit && Position.MarketPosition != MarketPosition.Flat)
            {
                ExitLong("EOD Exit", "Long");
                ExitShort("EOD Exit", "Short");
                return;
            }
            
            // Check daily loss limit
            if (isDailyLossHit)
                return;
            
            // Filter checks
            double rSize = orHigh - orLow;
            double rPct = (rSize / Close[0]) * 100;
            bool isRangeFiltered = rPct > MaxRangePct || rPct < MinRangePct;
            
            if (isRangeFiltered)
                return;
            
            // Track price returning to range
            if (Position.MarketPosition == MarketPosition.Flat && Close[0] >= orLow && Close[0] <= orHigh)
                priceReturnedToRange = true;
            
            // Entry Logic
            if (isTradingTime && Position.MarketPosition == MarketPosition.Flat)
            {
                bool canTrade = attempts < MaxAttempts && 
                               !(StopAfterWin && hasWonToday) &&
                               (RequireFreshBreakout ? priceReturnedToRange : true) &&
                               (CooldownBars == 0 || CurrentBar - lastExitBar >= CooldownBars);
                
                if (canTrade && UseImmediateEntry)
                {
                    double displacementHigh = orHigh * (1 + MinDisplacement / 100);
                    double displacementLow = orLow * (1 - MinDisplacement / 100);
                    
                    // Breakout detection (using CrossAbove/CrossBelow like AllDay)
                    bool breakoutLong = CrossAbove(Close, orHigh, 1);
                    bool breakoutShort = CrossBelow(Close, orLow, 1);
                    
                    // Displacement check (or no displacement required if MinDisplacement == 0)
                    bool hasDisplacementLong = MinDisplacement > 0 ? Close[0] >= displacementHigh : true;
                    bool hasDisplacementShort = MinDisplacement > 0 ? Close[0] <= displacementLow : true;
                    
                    // DEBUG: Log breakout detection
                    if (DebugMode && (breakoutLong || breakoutShort))
                    {
                        Print($"[V5 DEBUG] {Time[0]:HH:mm} Breakout! Long:{breakoutLong} Short:{breakoutShort} | Close:{Close[0]:F2} orHigh:{orHigh:F2} orLow:{orLow:F2}");
                        Print($"[V5 DEBUG]   DisplacementLong:{hasDisplacementLong} DisplacementShort:{hasDisplacementShort} | Att:{attempts}/{MaxAttempts} Fresh:{priceReturnedToRange}");
                    }
                    
                    // Long Breakout with displacement
                    if (breakoutLong && hasDisplacementLong)
                    {
                        if (DebugMode) Print($"[V5 ENTRY] {Time[0]:HH:mm} >> LONG ENTRY @ {Close[0]:F2}");
                        EnterTrade(true);
                    }
                    // Short Breakout with displacement
                    else if (breakoutShort && hasDisplacementShort)
                    {
                        if (DebugMode) Print($"[V5 ENTRY] {Time[0]:HH:mm} >> SHORT ENTRY @ {Close[0]:F2}");
                        EnterTrade(false);
                    }
                }
                else if (!canTrade && UseImmediateEntry && DebugMode)
                {
                    // DEBUG: Log why we can't trade
                    bool attOK = attempts < MaxAttempts;
                    bool winOK = !(StopAfterWin && hasWonToday);
                    bool freshOK = RequireFreshBreakout ? priceReturnedToRange : true;
                    bool coolOK = CooldownBars == 0 || CurrentBar - lastExitBar >= CooldownBars;
                    
                    bool breakoutLong = CrossAbove(Close, orHigh, 1);
                    bool breakoutShort = CrossBelow(Close, orLow, 1);
                    
                    if (breakoutLong || breakoutShort)
                    {
                        Print($"[V5 BLOCKED] {Time[0]:HH:mm} Breakout detected but BLOCKED! att:{attOK} win:{winOK} fresh:{freshOK} cool:{coolOK}");
                    }
                }
            }
            
            // Exit Management
            ManageExits();
            
            // Draw visuals
            DrawRangeBox(estTime);
            DrawDashboard(estTime, rSize, rPct);
        }

        private void ResetDailyState()
        {
            orHigh = 0;
            orLow = 0;
            orDefined = false;
            rangeSynced = false;
            attempts = 0;
            longAttempts = 0;
            shortAttempts = 0;
            hasWonToday = false;
            priceReturnedToRange = true;
            tp1Hit = false;
            tp2Hit = false;
            tradeEntryPrice = 0;
            currentTrailStop = 0;
            isRunnerActive = false;
            adaptiveTrailActivated = false;
            dayStartEquity = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            dayHighEquity = dayStartEquity;
            isDailyLossHit = false;
        }

        private void UpdateDailyEquity()
        {
            double currentEquity = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            if (currentEquity > dayHighEquity)
                dayHighEquity = currentEquity;
            
            if (UseMaxDailyLoss && (dayStartEquity - currentEquity) >= MaxDailyLossUSD)
            {
                isDailyLossHit = true;
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitLong("Daily Loss", "Long");
                    ExitShort("Daily Loss", "Short");
                }
            }
        }

        private void DefineOpeningRange(DateTime estTime)
        {
            TimeSpan currentTime = estTime.TimeOfDay;
            
            // Capture OR during the OR window
            // Use > (not >=) to skip the bar exactly at 9:30:00 which is previous period
            if (currentTime > ORStartTime && currentTime <= OREndTime && !orDefined)
            {
                if (orHigh == 0)
                {
                    orHigh = High[0];
                    orLow = Low[0];
                }
                else
                {
                    orHigh = Math.Max(orHigh, High[0]);
                    orLow = Math.Min(orLow, Low[0]);
                }
            }
            // Lock in OR after the window closes
            else if (currentTime > OREndTime && orHigh > 0 && !orDefined)
            {
                orDefined = true;
            }
        }
        
        private void DrawRangeBox(DateTime estTime)
        {
            if (!orDefined) return;
            if (estZone == null) return;
            
            // Get chart timezone from NinjaTrader
            TimeZoneInfo chartZone;
            try { chartZone = Core.Globals.GeneralOptions.TimeZoneInfo; }
            catch { chartZone = TimeZoneInfo.Local; }

            DateTime rangeDate = estTime.Date;
            
            // Calculate start time: OR end time in EST, converted to chart time
            DateTime estOpen = rangeDate.Add(OREndTime);
            // End: 16:00:00 EST (End of Session)
            DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

            DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
            DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

            // Extend to current time if before end, otherwise draw full
            DateTime displayEnd = (Time[0] < chartEnd) ? Time[0] : chartEnd;
            
            string suffix = rangeDate.ToString("yyyyMMdd");
            
            // Main Lines using DateTime coordinates
            Draw.Line(this, "High" + suffix, false, chartStart, orHigh, displayEnd, orHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
            Draw.Line(this, "Low" + suffix, false, chartStart, orLow, displayEnd, orLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);
            
            // Mid line
            double mid = (orHigh + orLow) / 2;
            Draw.Line(this, "Mid" + suffix, false, chartStart, mid, displayEnd, mid, Brushes.Gold, DashStyleHelper.Dash, 1);
            
            // Box using DateTime coordinates
            Draw.Rectangle(this, "RangeBox" + suffix, false, chartStart, orHigh, displayEnd, orLow, Brushes.Transparent, Brushes.DeepSkyBlue, 20);
        }
        
        private void DrawDashboard(DateTime estTime, double rSize, double rPct)
        {
            TimeSpan currentTime = estTime.TimeOfDay;
            bool isTradingTime = currentTime > OREndTime && currentTime < TradingEndTime;
            bool canTrade = attempts < MaxAttempts && 
                           !(StopAfterWin && hasWonToday) &&
                           (RequireFreshBreakout ? priceReturnedToRange : true) &&
                           (CooldownBars == 0 || CurrentBar - lastExitBar >= CooldownBars);
            
            string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" :
                           hasWonToday && StopAfterWin ? "WON - DONE" :
                           isDailyLossHit ? "DAILY LOSS LIMIT" :
                           attempts >= MaxAttempts ? "MAX ATTEMPTS" :
                           !isTradingTime ? "WAIT: Time" :
                           !canTrade ? "BLOCKED" :
                           "READY";
            
            string tpMode = UseSingleTP ? $"Single: {TP1Pct}%" : $"Multi: {TP1Pct}%/{TP2Pct}%";
            int qty = CalcPositionSize(rSize);
            
            // Trade info
            int closedTrades = SystemPerformance.AllTrades.Count;
            double totalProfit = closedTrades > 0 ? SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit : 0;
            string lastTrade = closedTrades > 0 ? 
                $"Last: ${SystemPerformance.AllTrades[closedTrades-1].ProfitCurrency:F0}" : "No trades";
            
            // Debug info
            string debug = $"Tt:{isTradingTime} C:{canTrade} I:{UseImmediateEntry}";
            
            string hud = string.Format(
                "ORB V5 STRATEGY\n" +
                "─────────────\n" +
                "Range: {0:F2} pts ({1:F3}%)\n" +
                "Attempts: {2}/{3} (L:{4} S:{5})\n" +
                "TP Mode: {6}\n" +
                "Qty: {7} | Risk: {8}%\n" +
                "Trades: {11} | P/L: ${12:F0}\n" +
                "{13}\n" +
                "Status: {9} | EST:{10:HH:mm}\n" +
                "{14}",
                rSize, rPct,
                attempts, MaxAttempts, longAttempts, shortAttempts,
                tpMode, qty, RiskPercent, status, estTime,
                closedTrades, totalProfit, lastTrade, debug);
            
            Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White,
                new SimpleFont("Consolas", 10), Brushes.Black, Brushes.DimGray, 90);
        }

        private void EnterTrade(bool isLong)
        {
            attempts++;
            if (isLong) longAttempts++; else shortAttempts++;
            
            tradeEntryPrice = Close[0];
            tp1Hit = false;
            tp2Hit = false;
            isRunnerActive = false;
            adaptiveTrailActivated = false;
            priceReturnedToRange = false;
            
            // Calculate position size (matching PineScript logic)
            double rSize = orHigh - orLow;
            int totalQty = CalcPositionSize(rSize);
            tp1Qty = UseSingleTP ? totalQty : Math.Max(1, (int)(totalQty * TP1Weight / 100));
            remainingQty = totalQty - tp1Qty;
            
            // Calculate stops
            double slPrice = CalcSLPrice(tradeEntryPrice, isLong);
            double tp1Price = CalcTPPrice(tradeEntryPrice, TP1Pct, isLong);
            
            string entryName = isLong ? "Long" : "Short";
            
            if (isLong)
            {
                EnterLong(totalQty, entryName);
            }
            else
            {
                EnterShort(totalQty, entryName);
            }
            
            // Note: Exits are managed by ManageExits() every bar
            
            // Draw visual TP/SL lines
            double tp2Price = CalcTPPrice(tradeEntryPrice, TP2Pct, isLong);
            Draw.Line(this, "TP1Line", false, 0, tp1Price, -50, tp1Price, Brushes.Green, DashStyleHelper.Solid, 2);
            if (!UseSingleTP)
                Draw.Line(this, "TP2Line", false, 0, tp2Price, -50, tp2Price, Brushes.Lime, DashStyleHelper.Dash, 1);
            Draw.Line(this, "SLLine", false, 0, slPrice, -50, slPrice, Brushes.Red, DashStyleHelper.Solid, 2);
            Draw.Line(this, "EntryLine", false, 0, tradeEntryPrice, -50, tradeEntryPrice, Brushes.Yellow, DashStyleHelper.Dot, 1);
        }
        
        private int CalcPositionSize(double rSize)
        {
            // Match PineScript: min(maxContracts, max(minContracts, floor((equity * riskPct / 100) / (rSize * pointValue))))
            if (rSize <= 0) return MinContracts;
            
            double equity = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            double riskAmount = equity * RiskPercent / 100;
            double pointValue = Instrument.MasterInstrument.PointValue;
            
            int qtyRisk = (int)Math.Floor(riskAmount / (rSize * pointValue));
            return Math.Min(MaxContracts, Math.Max(MinContracts, qtyRisk));
        }

        private void ManageExits()
        {
            if (Position.MarketPosition == MarketPosition.Flat)
                return;
            
            bool isLong = Position.MarketPosition == MarketPosition.Long;
            double entryPrice = Position.AveragePrice;
            int posQty = Position.Quantity;
            
            // Base SL at range boundary (or fixed %)
            double baseSL = CalcSLPrice(entryPrice, isLong);
            double currentSL = baseSL;
            
            // Calculate TP prices
            double tp1Price = CalcTPPrice(entryPrice, TP1Pct, isLong);
            double tp2Price = CalcTPPrice(entryPrice, TP2Pct, isLong);
            
            if (UseSingleTP)
            {
                // Single TP Mode - exit all at TP1
                if (isLong)
                {
                    ExitLongLimit(0, true, posQty, tp1Price, "Target", "Long");
                    ExitLongStopMarket(0, true, posQty, baseSL, "Stop", "Long");
                }
                else
                {
                    ExitShortLimit(0, true, posQty, tp1Price, "Target", "Short");
                    ExitShortStopMarket(0, true, posQty, baseSL, "Stop", "Short");
                }
            }
            else
            {
                // Multi-TP Mode
                
                // Check if TP1 was hit
                if (!tp1Hit)
                {
                    bool tp1Reached = isLong ? High[0] >= tp1Price : Low[0] <= tp1Price;
                    if (tp1Reached)
                    {
                        tp1Hit = true;
                        isRunnerActive = true;
                        if (UseTrailingStop && !UseAdaptiveTrail)
                            currentTrailStop = UpdateTrailStop(0, entryPrice, isLong);
                    }
                }
                
                // Move SL to breakeven after TP1
                if (tp1Hit && MoveToBE)
                    currentSL = entryPrice;
                
                // Manage trailing stop for runner
                if (tp1Hit && UseTrailingStop)
                {
                    if (UseAdaptiveTrail)
                    {
                        double activationPrice = CalcTPPrice(entryPrice, TrailActivationPct, isLong);
                        bool isActivated = isLong ? High[0] >= activationPrice : Low[0] <= activationPrice;
                        
                        if (isActivated)
                            adaptiveTrailActivated = true;
                        
                        if (adaptiveTrailActivated)
                        {
                            currentTrailStop = UpdateTrailStop(currentTrailStop, entryPrice, isLong);
                            currentSL = isLong ? Math.Max(currentSL, currentTrailStop) : Math.Min(currentSL, currentTrailStop);
                        }
                    }
                    else
                    {
                        currentTrailStop = UpdateTrailStop(currentTrailStop, entryPrice, isLong);
                        currentSL = currentTrailStop;
                    }
                }
                
                // Set exit orders - TP1 for first portion, TP2 for runner
                int tp1ExitQty = Math.Min(tp1Qty, posQty);
                int runnerQty = posQty - tp1ExitQty;
                
                if (isLong)
                {
                    if (!tp1Hit && tp1ExitQty > 0)
                        ExitLongLimit(0, true, tp1ExitQty, tp1Price, "TP1", "Long");
                    if (runnerQty > 0)
                        ExitLongLimit(0, true, runnerQty, tp2Price, "TP2", "Long");
                    ExitLongStopMarket(0, true, posQty, currentSL, "SL", "Long");
                }
                else
                {
                    if (!tp1Hit && tp1ExitQty > 0)
                        ExitShortLimit(0, true, tp1ExitQty, tp1Price, "TP1", "Short");
                    if (runnerQty > 0)
                        ExitShortLimit(0, true, runnerQty, tp2Price, "TP2", "Short");
                    ExitShortStopMarket(0, true, posQty, currentSL, "SL", "Short");
                }
            }
            
            // MAE Filter - exit if price moves against entry by threshold
            if (UseMAEFilter)
            {
                double maeDistance = entryPrice * MAEThreshold / 100;
                if (isLong && Low[0] < entryPrice - maeDistance)
                {
                    ExitLong("MAE Exit", "Long");
                }
                else if (!isLong && High[0] > entryPrice + maeDistance)
                {
                    ExitShort("MAE Exit", "Short");
                }
            }
        }

        private double CalcTPPrice(double entryPrice, double tpPct, bool isLong)
        {
            return isLong ? entryPrice * (1 + tpPct / 100) : entryPrice * (1 - tpPct / 100);
        }

        private double CalcSLPrice(double entryPrice, bool isLong)
        {
            if (UseFixedSL)
                return isLong ? entryPrice * (1 - SLFixedPct / 100) : entryPrice * (1 + SLFixedPct / 100);
            else
                return isLong ? orLow : orHigh;
        }

        private double UpdateTrailStop(double currentStop, double entryPrice, bool isLong)
        {
            double offset = entryPrice * TrailOffsetPct / 100;
            
            if (isLong)
            {
                double newStop = High[0] - offset;
                return (currentStop == 0 || newStop > currentStop) ? newStop : currentStop;
            }
            else
            {
                double newStop = Low[0] + offset;
                return (currentStop == 0 || newStop < currentStop) ? newStop : currentStop;
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            // Track wins
            if (execution.Order.OrderState == OrderState.Filled)
            {
                if (execution.Order.Name.Contains("Profit") || execution.Order.Name.Contains("TP"))
                {
                    // Profit target hit
                    hasWonToday = true;
                }
                
                if (marketPosition == MarketPosition.Flat)
                {
                    lastExitBar = CurrentBar;
                    
                    // Clear visual TP/SL lines
                    RemoveDrawObject("TP1Line");
                    RemoveDrawObject("TP2Line");
                    RemoveDrawObject("SLLine");
                    RemoveDrawObject("EntryLine");
                }
            }
        }
    }
}
