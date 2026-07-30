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
    /// <summary>
    /// Opening Range Breakout Strategy with 3-Strike Rule v3
    /// Trades Opening Range Breakouts with configurable direction filter
    /// 
    /// Recommended settings by instrument:
    /// - MGC (Gold): Short Only (PF 2.48)
    /// - MNQ (Nasdaq): Short Only (PF 1.86)
    /// - MYM (Dow): Long Only (PF 1.78)
    /// - MES (S&P): Short Only (PF 1.37)
    /// - M2K (Russell): Skip (both directions losing)
    /// </summary>
    public class ORBreakoutStrategy : Strategy
    {
        #region Enums
        public enum DirectionFilter
        {
            Both,
            LongOnly,
            ShortOnly
        }
        
        private enum TradeState
        {
            Waiting,
            PendingEntry,
            InTrade,
            Cooling,
            Done
        }
        #endregion
        
        #region Variables
        // State variables
        private TradeState currentState = TradeState.Waiting;
        private int tradeDirection = 0; // 1 = Long, -1 = Short
        private double entryPrice = 0;
        private double targetPrice = 0;
        private double stopPrice = 0;
        private int strikes = 0;
        private bool dayDone = false;
        private bool needsFreshBreakout = false;
        private int coolingStartBar = 0;
        
        // Range tracking
        private double rangeHigh = double.MinValue;
        private double rangeLow = double.MaxValue;
        private DateTime rangeDate = DateTime.MinValue;
        
        // MFE/MAE tracking
        private double moveHigh = 0;
        private double moveLow = 0;
        private int tradeStartBar = 0;
        
        // Statistics
        private int totalWins = 0;
        private int totalLosses = 0;
        private int dayWins = 0;
        private int dayLosses = 0;
        private int skippedLong = 0;
        private int skippedShort = 0;
        
        // Time helpers
        private TimeSpan rangeStartTimeSpan;
        private TimeSpan rangeEndTimeSpan;
        private TimeSpan lastTradeTimeSpan;
        private TimeSpan sessionEndTimeSpan;
        
        // Order tracking
        private Order entryOrder = null;
        private Order targetOrder = null;
        private Order stopOrder = null;
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Range Start Time", Order = 1, GroupName = "1. Time Settings")]
        public DateTime RangeStartTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Range End Time", Order = 2, GroupName = "1. Time Settings")]
        public DateTime RangeEndTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Last Trade Time", Order = 3, GroupName = "1. Time Settings")]
        public DateTime LastTradeTime { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Session End Time", Order = 4, GroupName = "1. Time Settings")]
        public DateTime SessionEndTime { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.01, 5.0)]
        [Display(Name = "EV Target %", Order = 1, GroupName = "2. Strategy Settings")]
        public double EVTarget { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.01, 5.0)]
        [Display(Name = "Stop Loss %", Order = 2, GroupName = "2. Strategy Settings")]
        public double StopLoss { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Max Strikes", Order = 3, GroupName = "2. Strategy Settings")]
        public int MaxStrikes { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Stop After Win", Order = 4, GroupName = "2. Strategy Settings")]
        public bool StopAfterWin { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name = "Cooling Period (bars)", Order = 5, GroupName = "2. Strategy Settings")]
        public int CoolingPeriod { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Direction Filter", Order = 1, GroupName = "3. Direction Filter")]
        [Description("MGC/MNQ/MES: Short Only | MYM: Long Only | M2K: Skip")]
        public DirectionFilter Direction { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Breakout Requires Body In Range", Order = 1, GroupName = "4. Breakout Settings")]
        public bool BodyInRange { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Contracts", Order = 1, GroupName = "5. Position Sizing")]
        public int Contracts { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Range Box", Order = 1, GroupName = "6. Visuals")]
        public bool ShowRangeBox { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Trade Boxes", Order = 2, GroupName = "6. Visuals")]
        public bool ShowTradeBoxes { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Range Box Color", Order = 3, GroupName = "6. Visuals")]
        public Brush RangeBoxColor { get; set; }
        
        [Browsable(false)]
        public string RangeBoxColorSerializable
        {
            get { return Serialize.BrushToString(RangeBoxColor); }
            set { RangeBoxColor = Serialize.StringToBrush(value); }
        }
        #endregion
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Opening Range Breakout Strategy with 3-Strike Rule v3";
                Name = "ORBreakoutStrategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 1;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Day;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;
                
                // Default settings
                RangeStartTime = DateTime.Parse("06:00");
                RangeEndTime = DateTime.Parse("08:30");
                LastTradeTime = DateTime.Parse("12:00");
                SessionEndTime = DateTime.Parse("16:00");
                EVTarget = 0.15;
                StopLoss = 0.15;
                MaxStrikes = 3;
                StopAfterWin = true;
                CoolingPeriod = 0;
                Direction = DirectionFilter.Both;
                BodyInRange = true;
                Contracts = 1;
                ShowRangeBox = true;
                ShowTradeBoxes = true;
                RangeBoxColor = Brushes.Cyan;
            }
            else if (State == State.Configure)
            {
                rangeStartTimeSpan = RangeStartTime.TimeOfDay;
                rangeEndTimeSpan = RangeEndTime.TimeOfDay;
                lastTradeTimeSpan = LastTradeTime.TimeOfDay;
                sessionEndTimeSpan = SessionEndTime.TimeOfDay;
            }
            else if (State == State.DataLoaded)
            {
                ClearOutputWindow();
            }
        }
        
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;
            
            DateTime barTime = Time[0];
            TimeSpan currentTime = barTime.TimeOfDay;
            
            // Check for new day
            if (barTime.Date != rangeDate)
            {
                ResetDay();
                rangeDate = barTime.Date;
            }
            
            // Update range during range period
            if (IsInRange(currentTime))
            {
                rangeHigh = Math.Max(rangeHigh, High[0]);
                rangeLow = Math.Min(rangeLow, Low[0]);
                
                if (ShowRangeBox && rangeHigh != double.MinValue)
                {
                    RemoveDrawObject("RangeBox" + rangeDate.ToShortDateString());
                    Draw.Rectangle(this, "RangeBox" + rangeDate.ToShortDateString(), 
                        false, Bars.GetTime(CurrentBar - GetBarsInRange()), rangeHigh,
                        Time[0], rangeLow, RangeBoxColor, RangeBoxColor, 30);
                }
                return;
            }
            
            // Close position at session end
            if (currentTime >= sessionEndTimeSpan && Position.MarketPosition != MarketPosition.Flat)
            {
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong("Session End", "Long");
                else if (Position.MarketPosition == MarketPosition.Short)
                    ExitShort("Session End", "Short");
                
                dayDone = true;
                currentState = TradeState.Done;
                return;
            }
            
            // Skip if not in trading window or day is done
            if (!IsAfterRange(currentTime) || dayDone || rangeHigh == double.MinValue)
                return;
            
            // State machine
            ProcessState();
        }
        
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            // Handle fills
            if (execution.Order != null && execution.Order.OrderState == OrderState.Filled)
            {
                if (execution.Order.Name == "Long" || execution.Order.Name == "Short")
                {
                    // Entry filled
                    Print("Entry filled at " + price);
                }
                else if (execution.Order.Name == "Target")
                {
                    // Target hit - WIN
                    HandleWin();
                }
                else if (execution.Order.Name == "Stop")
                {
                    // Stop hit - LOSS
                    HandleLoss();
                }
            }
        }
        
        private void ProcessState()
        {
            switch (currentState)
            {
                case TradeState.Waiting:
                    ProcessWaitingState();
                    break;
                case TradeState.PendingEntry:
                    ProcessPendingEntryState();
                    break;
                case TradeState.InTrade:
                    ProcessInTradeState();
                    break;
                case TradeState.Cooling:
                    ProcessCoolingState();
                    break;
            }
        }
        
        private void ProcessWaitingState()
        {
            if (needsFreshBreakout)
            {
                if (IsPriceInsideRange())
                    needsFreshBreakout = false;
                return;
            }
            
            // Check for Bull Breakout
            if (IsValidBullBreakout())
            {
                if (AllowLong())
                {
                    currentState = TradeState.PendingEntry;
                    tradeDirection = 1;
                    tradeStartBar = CurrentBar;
                }
                else
                {
                    skippedLong++;
                    needsFreshBreakout = true;
                }
                return;
            }
            
            // Check for Bear Breakout
            if (IsValidBearBreakout())
            {
                if (AllowShort())
                {
                    currentState = TradeState.PendingEntry;
                    tradeDirection = -1;
                    tradeStartBar = CurrentBar;
                }
                else
                {
                    skippedShort++;
                    needsFreshBreakout = true;
                }
            }
        }
        
        private void ProcessPendingEntryState()
        {
            // Entry will be on next bar's open, but we calculate levels now
            entryPrice = Close[0]; // Will be adjusted to actual fill
            moveHigh = High[0];
            moveLow = Low[0];
            
            // Calculate target and stop (symmetric from entry)
            if (tradeDirection == 1)
            {
                targetPrice = entryPrice * (1 + EVTarget / 100);
                stopPrice = entryPrice * (1 - StopLoss / 100);
                
                // Enter long
                EnterLong(Contracts, "Long");
            }
            else
            {
                targetPrice = entryPrice * (1 - EVTarget / 100);
                stopPrice = entryPrice * (1 + StopLoss / 100);
                
                // Enter short
                EnterShort(Contracts, "Short");
            }
            
            // Set profit target and stop loss
            SetProfitTarget("Long", CalculationMode.Price, targetPrice);
            SetProfitTarget("Short", CalculationMode.Price, targetPrice);
            SetStopLoss("Long", CalculationMode.Price, stopPrice, false);
            SetStopLoss("Short", CalculationMode.Price, stopPrice, false);
            
            // Draw trade box
            if (ShowTradeBoxes)
                DrawTradeBox();
            
            currentState = TradeState.InTrade;
        }
        
        private void ProcessInTradeState()
        {
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                // Position was closed by target or stop
                // OnExecutionUpdate will handle the state transition
            }
            else
            {
                // Update MFE/MAE tracking
                moveHigh = Math.Max(moveHigh, High[0]);
                moveLow = Math.Min(moveLow, Low[0]);
            }
        }
        
        private void ProcessCoolingState()
        {
            if (IsPriceInsideRange())
            {
                currentState = TradeState.Waiting;
                needsFreshBreakout = false;
            }
            else if (CurrentBar > coolingStartBar + CoolingPeriod)
            {
                currentState = TradeState.Waiting;
                needsFreshBreakout = true;
            }
        }
        
        private void HandleWin()
        {
            totalWins++;
            
            string label = "WIN";
            if (tradeDirection == 1)
                Draw.Text(this, "Win" + CurrentBar, label, 0, High[0] + TickSize * 10, Brushes.Green);
            else
                Draw.Text(this, "Win" + CurrentBar, label, 0, Low[0] - TickSize * 10, Brushes.Green);
            
            if (StopAfterWin)
            {
                dayDone = true;
                dayWins++;
                currentState = TradeState.Done;
            }
            else
            {
                currentState = TradeState.Waiting;
                needsFreshBreakout = true;
                tradeDirection = 0;
            }
        }
        
        private void HandleLoss()
        {
            strikes++;
            
            string label = "STOP " + strikes + "/" + MaxStrikes;
            if (tradeDirection == 1)
                Draw.Text(this, "Loss" + CurrentBar, label, 0, Low[0] - TickSize * 10, Brushes.Red);
            else
                Draw.Text(this, "Loss" + CurrentBar, label, 0, High[0] + TickSize * 10, Brushes.Red);
            
            if (strikes >= MaxStrikes)
            {
                totalLosses++;
                dayLosses++;
                dayDone = true;
                currentState = TradeState.Done;
            }
            else
            {
                if (CoolingPeriod > 0)
                {
                    currentState = TradeState.Cooling;
                    coolingStartBar = CurrentBar;
                }
                else
                {
                    currentState = TradeState.Waiting;
                    needsFreshBreakout = true;
                }
                tradeDirection = 0;
            }
        }
        
        private void DrawTradeBox()
        {
            string boxId = "Trade" + CurrentBar;
            Brush profitColor = Brushes.Green;
            Brush riskColor = Brushes.Brown;
            
            if (tradeDirection == 1)
            {
                Draw.Rectangle(this, boxId + "Profit", false, Time[0], targetPrice, 
                    Time[0].AddMinutes(60), entryPrice, profitColor, profitColor, 30);
                Draw.Rectangle(this, boxId + "Risk", false, Time[0], entryPrice, 
                    Time[0].AddMinutes(60), stopPrice, riskColor, riskColor, 30);
            }
            else
            {
                Draw.Rectangle(this, boxId + "Profit", false, Time[0], entryPrice, 
                    Time[0].AddMinutes(60), targetPrice, profitColor, profitColor, 30);
                Draw.Rectangle(this, boxId + "Risk", false, Time[0], stopPrice, 
                    Time[0].AddMinutes(60), entryPrice, riskColor, riskColor, 30);
            }
        }
        
        #region Helper Methods
        private void ResetDay()
        {
            currentState = TradeState.Waiting;
            tradeDirection = 0;
            entryPrice = 0;
            targetPrice = 0;
            stopPrice = 0;
            strikes = 0;
            dayDone = false;
            needsFreshBreakout = false;
            rangeHigh = double.MinValue;
            rangeLow = double.MaxValue;
            moveHigh = 0;
            moveLow = 0;
        }
        
        private bool IsInRange(TimeSpan time)
        {
            return time >= rangeStartTimeSpan && time < rangeEndTimeSpan;
        }
        
        private bool IsAfterRange(TimeSpan time)
        {
            return time >= rangeEndTimeSpan && time < lastTradeTimeSpan;
        }
        
        private bool IsPriceInsideRange()
        {
            return Close[0] >= rangeLow && Close[0] <= rangeHigh;
        }
        
        private bool IsValidBullBreakout()
        {
            bool closeOutside = Close[0] > rangeHigh;
            if (!closeOutside) return false;
            
            if (BodyInRange)
            {
                double bodyLow = Math.Min(Open[0], Close[0]);
                return bodyLow <= rangeHigh;
            }
            return true;
        }
        
        private bool IsValidBearBreakout()
        {
            bool closeOutside = Close[0] < rangeLow;
            if (!closeOutside) return false;
            
            if (BodyInRange)
            {
                double bodyHigh = Math.Max(Open[0], Close[0]);
                return bodyHigh >= rangeLow;
            }
            return true;
        }
        
        private bool AllowLong()
        {
            return Direction == DirectionFilter.Both || Direction == DirectionFilter.LongOnly;
        }
        
        private bool AllowShort()
        {
            return Direction == DirectionFilter.Both || Direction == DirectionFilter.ShortOnly;
        }
        
        private int GetBarsInRange()
        {
            int count = 0;
            for (int i = 0; i < CurrentBar && i < 100; i++)
            {
                if (Time[i].Date == rangeDate && IsInRange(Time[i].TimeOfDay))
                    count++;
                else if (Time[i].Date != rangeDate)
                    break;
            }
            return Math.Max(1, count);
        }
        #endregion
    }
}
