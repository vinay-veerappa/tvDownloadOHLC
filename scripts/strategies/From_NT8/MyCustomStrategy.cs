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
    public class ORBStrategyV2_Mikey : Strategy
    {
        #region Variables
        private double orbHigh = double.MinValue;
        private double orbLow = double.MaxValue;
        private bool orbCaptured = false;
        private bool entryTaken = false;
        private DateTime currentDate = DateTime.MinValue;
        private List<double> orbSizes = new List<double>();
        private int orbStartBar = -1;
        
        // Extension levels
        private double[] upperExtensions = new double[10];
        private double[] lowerExtensions = new double[10];
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"1-Minute Opening Range Breakout Strategy - V2 with improved drawing";
                Name = "ORBStrategyV2_Mikey";
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
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;

                // ORB Parameters
                OrbLookback = 20;
                OrbHour = 6;        // 6:30 AM PST = 9:30 AM EST
                OrbMinute = 30;
                OrbDuration = 1;
                
                // Extension Settings
                ShowExtensions = true;
                ExtensionBps = 10;
                NumExtensions = 3;
                ExtensionWidth = 1;
                UpperExtensionColor = Brushes.Green;
                LowerExtensionColor = Brushes.Red;
                
                // Entry Cutoff
                UseEntryCutoff = true;
                EntryCutoffHour = 12;   // Noon PST
                EntryCutoffMinute = 0;
                
                // Exit Time
                ExitHour = 13;          // 1 PM PST = 4 PM EST
                ExitMinute = 0;
                
                // Take Profit Settings
                TpType = TakeProfitType.BasisPoints;
                TpFixedPoints = 100;    // 100 ticks = 25 points on MNQ
                TpBasisPoints = 50;
                TpPercent = 1.0;
                TpMultiplier = 1.0;
                
                // Stop Loss Settings
                StopType = StopLossType.OppositeOrbWithMaxLoss;
                StopPercent = 0.75;
                StopFixedPoints = 60;   // 60 ticks = 15 points on MNQ
                StopBasisPoints = 26;
                MaxLossLimit = 350;
                ContractSize = 3;
                
                // ORB Range Filter
                UseRangeFilter = true;
                MaxRangeBps = 30;
                
                // Display Settings
                ShowStatsTable = false;
                ShowTradeStats = false;
                OrbBoxColor = Brushes.Blue;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                orbSizes.Clear();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // Check for new day
            if (Time[0].Date != currentDate)
            {
                // Remove previous day's drawings before resetting
                if (currentDate != DateTime.MinValue)
                {
                    string prevDateTag = currentDate.ToString("yyyyMMdd");
                    
                    // Remove ORB levels
                    RemoveDrawObject("ORBHigh_" + prevDateTag);
                    RemoveDrawObject("ORBLow_" + prevDateTag);
                    RemoveDrawObject("ORBBox_" + prevDateTag);
                    
                    // Remove extensions
                    if (ShowExtensions)
                    {
                        for (int i = 0; i < NumExtensions && i < 10; i++)
                        {
                            RemoveDrawObject("UpperExt_" + (i + 1) + "_" + prevDateTag);
                            RemoveDrawObject("LowerExt_" + (i + 1) + "_" + prevDateTag);
                        }
                    }
                }
                
                currentDate = Time[0].Date;
                orbHigh = double.MinValue;
                orbLow = double.MaxValue;
                orbCaptured = false;
                entryTaken = false;
                orbStartBar = -1;
            }

            // Check if we're in the ORB period
            bool isOrbBar = IsOrbBar(Time[0]);

            // Capture ORB high and low during the ENTIRE ORB period
            if (isOrbBar)
            {
                if (orbStartBar == -1)
                {
                    // First bar of ORB period - initialize
                    orbStartBar = CurrentBar;
                    orbHigh = High[0];
                    orbLow = Low[0];
                    Print(string.Format("{0}: ORB Period Started - High: {1}, Low: {2}", 
                        Time[0], orbHigh, orbLow));
                }
                else
                {
                    // Subsequent bars in ORB period - update high/low
                    if (High[0] > orbHigh)
                    {
                        orbHigh = High[0];
                        Print(string.Format("{0}: ORB High updated to {1}", Time[0], orbHigh));
                    }
                    if (Low[0] < orbLow)
                    {
                        orbLow = Low[0];
                        Print(string.Format("{0}: ORB Low updated to {1}", Time[0], orbLow));
                    }
                }
                
                // Don't mark as captured yet - we're still in the period
            }
            else if (orbStartBar != -1 && !orbCaptured)
            {
                // We just exited the ORB period - NOW capture it
                orbCaptured = true;
                entryTaken = false;
                
                // Store ORB size
                double currentOrbSize = orbHigh - orbLow;
                orbSizes.Add(currentOrbSize);
                
                // Keep only the specified lookback period
                if (orbSizes.Count > OrbLookback)
                    orbSizes.RemoveAt(0);
                    
                // Calculate extensions
                CalculateExtensions();
                
                // Draw immediately after capture
                DrawOrbLevels();
                
                Print(string.Format("{0}: ORB CAPTURED - High: {1}, Low: {2}, Size: {3}", 
                    Time[0], orbHigh, orbLow, currentOrbSize));
            }
            
            // Redraw ORB levels on every bar after capture
            if (orbCaptured)
            {
                DrawOrbLevels();
            }

            if (!orbCaptured)
                return;

            // Calculate average ORB size
            double avgOrbSize = orbSizes.Count > 0 ? orbSizes.Average() : 0;

            // Check if ORB range is within acceptable limits
            double orbRange = orbHigh - orbLow;
            double orbRangeBps = orbLow > 0 ? (orbRange / orbLow) * 10000 : 0;
            bool rangeAcceptable = !UseRangeFilter || orbRangeBps <= MaxRangeBps;

            // Check if we've reached the exit time
            bool isExitTime = Time[0].Hour == ExitHour && Time[0].Minute == ExitMinute;
            
            // Check if we've passed the entry cutoff time
            bool isPastCutoff = UseEntryCutoff && 
                ((Time[0].Hour > EntryCutoffHour) || 
                 (Time[0].Hour == EntryCutoffHour && Time[0].Minute >= EntryCutoffMinute));

            // Force exit at specified time
            if (isExitTime && Position.MarketPosition != MarketPosition.Flat)
            {
                ExitLong();
                ExitShort();
                Print(string.Format("{0}: Time Exit", Time[0]));
            }

            // Check for breakout entry (Close must break above/below ORB levels)
            bool longCondition = orbCaptured && !entryTaken && Close[0] > orbHigh && 
                                !isOrbBar && Position.MarketPosition == MarketPosition.Flat && 
                                rangeAcceptable && !isPastCutoff;
                                
            bool shortCondition = orbCaptured && !entryTaken && Close[0] < orbLow && 
                                 !isOrbBar && Position.MarketPosition == MarketPosition.Flat && 
                                 rangeAcceptable && !isPastCutoff;

            if (longCondition)
            {
                double actualLongStop = CalculateStopLoss(true, orbLow);
                double actualLongTp = CalculateTakeProfit(true, orbRange);
                
                EnterLong(ContractSize, "Long");
                SetStopLoss("Long", CalculationMode.Price, actualLongStop, false);
                SetProfitTarget("Long", CalculationMode.Price, actualLongTp);
                entryTaken = true;
                
                Print(string.Format("{0}: LONG Entry @ {1}, Stop: {2}, Target: {3}", 
                    Time[0], Close[0], actualLongStop, actualLongTp));
            }
            
            if (shortCondition)
            {
                double actualShortStop = CalculateStopLoss(false, orbHigh);
                double actualShortTp = CalculateTakeProfit(false, orbRange);
                
                EnterShort(ContractSize, "Short");
                SetStopLoss("Short", CalculationMode.Price, actualShortStop, false);
                SetProfitTarget("Short", CalculationMode.Price, actualShortTp);
                entryTaken = true;
                
                Print(string.Format("{0}: SHORT Entry @ {1}, Stop: {2}, Target: {3}", 
                    Time[0], Close[0], actualShortStop, actualShortTp));
            }
        }

        #region Helper Methods
        
        private bool IsOrbBar(DateTime barTime)
        {
            int orbEndMinute = OrbMinute + OrbDuration;
            int orbEndHour = OrbHour;
            
            if (orbEndMinute >= 60)
            {
                orbEndMinute -= 60;
                orbEndHour += 1;
            }

            bool isInOrbPeriod = false;
            
            if (orbEndHour > OrbHour)
            {
                isInOrbPeriod = (barTime.Hour == OrbHour && barTime.Minute >= OrbMinute) ||
                               (barTime.Hour == orbEndHour && barTime.Minute < orbEndMinute);
            }
            else
            {
                isInOrbPeriod = barTime.Hour == OrbHour && 
                               barTime.Minute >= OrbMinute && 
                               barTime.Minute < orbEndMinute;
            }
            
            return isInOrbPeriod;
        }

        private double CalculateStopLoss(bool isLong, double oppositeOrbLevel)
        {
            double stopLevel = 0;
            
            switch (StopType)
            {
                case StopLossType.OppositeOrb:
                    stopLevel = oppositeOrbLevel;
                    break;
                    
                case StopLossType.OppositeOrbWithMaxLoss:
                    double oppositeOrbStop = oppositeOrbLevel;
                    double oppositeOrbLossPts = Math.Abs(Close[0] - oppositeOrbStop);
                    double oppositeOrbLossDollars = oppositeOrbLossPts * Instrument.MasterInstrument.PointValue * ContractSize;
                    
                    if (oppositeOrbLossDollars > MaxLossLimit)
                    {
                        double maxLossPts = MaxLossLimit / (Instrument.MasterInstrument.PointValue * ContractSize);
                        stopLevel = isLong ? Close[0] - maxLossPts : Close[0] + maxLossPts;
                    }
                    else
                    {
                        stopLevel = oppositeOrbStop;
                    }
                    break;
                    
                case StopLossType.PercentageOfOrb:
                    double orbRange = orbHigh - orbLow;
                    stopLevel = isLong ? 
                        orbHigh - (orbRange * StopPercent) : 
                        orbLow + (orbRange * StopPercent);
                    break;
                    
                case StopLossType.FixedPoints:
                    stopLevel = isLong ? 
                        Close[0] - (StopFixedPoints * TickSize) : 
                        Close[0] + (StopFixedPoints * TickSize);
                    break;
                    
                case StopLossType.BasisPoints:
                    double stopDistance = Close[0] * (StopBasisPoints / 10000.0);
                    stopLevel = isLong ? Close[0] - stopDistance : Close[0] + stopDistance;
                    break;
            }
            
            return stopLevel;
        }

        private double CalculateTakeProfit(bool isLong, double orbRange)
        {
            double tpLevel = 0;
            
            switch (TpType)
            {
                case TakeProfitType.FixedPoints:
                    tpLevel = isLong ? 
                        Close[0] + (TpFixedPoints * TickSize) : 
                        Close[0] - (TpFixedPoints * TickSize);
                    break;
                    
                case TakeProfitType.BasisPoints:
                    double tpDistance = Close[0] * (TpBasisPoints / 10000.0);
                    tpLevel = isLong ? Close[0] + tpDistance : Close[0] - tpDistance;
                    break;
                    
                case TakeProfitType.PercentageOfOrb:
                    tpLevel = isLong ? 
                        Close[0] + (orbRange * TpPercent) : 
                        Close[0] - (orbRange * TpPercent);
                    break;
                    
                case TakeProfitType.MultipleOfOrb:
                    tpLevel = isLong ? 
                        Close[0] + (orbRange * TpMultiplier) : 
                        Close[0] - (orbRange * TpMultiplier);
                    break;
            }
            
            return tpLevel;
        }

        private void CalculateExtensions()
        {
            if (!ShowExtensions || !orbCaptured)
                return;

            double extensionDistance = orbHigh * (ExtensionBps / 10000.0);
            
            for (int i = 0; i < NumExtensions && i < 10; i++)
            {
                upperExtensions[i] = orbHigh + (extensionDistance * (i + 1));
                lowerExtensions[i] = orbLow - (extensionDistance * (i + 1));
            }
        }

        private void DrawOrbLevels()
        {
            if (!orbCaptured || orbStartBar < 0)
                return;
                
            string dateTag = Time[0].Date.ToString("yyyyMMdd");
            
            // Remove old drawings for this date
            RemoveDrawObject("ORBHigh_" + dateTag);
            RemoveDrawObject("ORBLow_" + dateTag);
            RemoveDrawObject("ORBBox_" + dateTag);
            
            // Calculate bars ago for start
            int barsAgoStart = CurrentBar - orbStartBar;
            
            // Draw ORB High - from ORB start to current bar
            Draw.Line(this, "ORBHigh_" + dateTag, false, 
                barsAgoStart, orbHigh, 0, orbHigh, 
                Brushes.Red, DashStyleHelper.Solid, 2);
            
            // Draw ORB Low
            Draw.Line(this, "ORBLow_" + dateTag, false, 
                barsAgoStart, orbLow, 0, orbLow, 
                Brushes.Green, DashStyleHelper.Solid, 2);
            
            // Draw ORB Box using time-based anchors
            Draw.Rectangle(this, "ORBBox_" + dateTag, false,
                Time[Math.Min(barsAgoStart, CurrentBar)], orbHigh, 
                Time[0], orbLow,
                OrbBoxColor, OrbBoxColor, 20);
            
            // Draw Extensions
            if (ShowExtensions)
            {
                for (int i = 0; i < NumExtensions && i < 10; i++)
                {
                    string upperTag = "UpperExt_" + (i + 1) + "_" + dateTag;
                    string lowerTag = "LowerExt_" + (i + 1) + "_" + dateTag;
                    
                    RemoveDrawObject(upperTag);
                    RemoveDrawObject(lowerTag);
                    
                    // Upper extensions
                    Draw.Line(this, upperTag, false,
                        barsAgoStart, upperExtensions[i], 0, upperExtensions[i],
                        UpperExtensionColor, DashStyleHelper.Dot, ExtensionWidth);
                    
                    // Lower extensions
                    Draw.Line(this, lowerTag, false,
                        barsAgoStart, lowerExtensions[i], 0, lowerExtensions[i],
                        LowerExtensionColor, DashStyleHelper.Dot, ExtensionWidth);
                }
            }
        }

        #endregion

        #region Properties

        [NinjaScriptProperty]
        [Range(1, 252)]
        [Display(Name = "ORB Avg Lookback (Days)", Order = 1, GroupName = "ORB Parameters")]
        public int OrbLookback { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "ORB Hour (24hr format)", Order = 2, GroupName = "ORB Parameters")]
        public int OrbHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "ORB Start Minute", Order = 3, GroupName = "ORB Parameters")]
        public int OrbMinute { get; set; }

        [NinjaScriptProperty]
        [Range(1, 60)]
        [Display(Name = "ORB Duration (minutes)", Order = 4, GroupName = "ORB Parameters")]
        public int OrbDuration { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Extensions", Order = 1, GroupName = "Extensions")]
        public bool ShowExtensions { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Extension Distance (Basis Points)", Order = 2, GroupName = "Extensions")]
        public int ExtensionBps { get; set; }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Number of Extensions", Order = 3, GroupName = "Extensions")]
        public int NumExtensions { get; set; }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Extension Line Width", Order = 4, GroupName = "Extensions")]
        public int ExtensionWidth { get; set; }

        [XmlIgnore]
        [Display(Name = "Upper Extension Color", Order = 5, GroupName = "Extensions")]
        public Brush UpperExtensionColor { get; set; }

        [Browsable(false)]
        public string UpperExtensionColorSerializable
        {
            get { return Serialize.BrushToString(UpperExtensionColor); }
            set { UpperExtensionColor = Serialize.StringToBrush(value); }
        }

        [XmlIgnore]
        [Display(Name = "Lower Extension Color", Order = 6, GroupName = "Extensions")]
        public Brush LowerExtensionColor { get; set; }

        [Browsable(false)]
        public string LowerExtensionColorSerializable
        {
            get { return Serialize.BrushToString(LowerExtensionColor); }
            set { LowerExtensionColor = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Use Entry Cutoff Time", Order = 1, GroupName = "Entry/Exit Times")]
        public bool UseEntryCutoff { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Entry Cutoff Hour", Order = 2, GroupName = "Entry/Exit Times")]
        public int EntryCutoffHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Entry Cutoff Minute", Order = 3, GroupName = "Entry/Exit Times")]
        public int EntryCutoffMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Exit Hour", Order = 4, GroupName = "Entry/Exit Times")]
        public int ExitHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Exit Minute", Order = 5, GroupName = "Entry/Exit Times")]
        public int ExitMinute { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Take Profit Type", Order = 1, GroupName = "Take Profit")]
        public TakeProfitType TpType { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "TP Fixed Points", Order = 2, GroupName = "Take Profit")]
        public int TpFixedPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "TP Basis Points", Order = 3, GroupName = "Take Profit")]
        public int TpBasisPoints { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, 5.0)]
        [Display(Name = "TP as % of ORB Range", Order = 4, GroupName = "Take Profit")]
        public double TpPercent { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "TP as Multiple of ORB Range", Order = 5, GroupName = "Take Profit")]
        public double TpMultiplier { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss Type", Order = 1, GroupName = "Stop Loss")]
        public StopLossType StopType { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, 1.0)]
        [Display(Name = "Stop as % of ORB Range", Order = 2, GroupName = "Stop Loss")]
        public double StopPercent { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Fixed Stop Loss (Points)", Order = 3, GroupName = "Stop Loss")]
        public int StopFixedPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Stop Loss (Basis Points)", Order = 4, GroupName = "Stop Loss")]
        public int StopBasisPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Loss Limit ($)", Order = 5, GroupName = "Stop Loss")]
        public int MaxLossLimit { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Contract Size", Order = 6, GroupName = "Stop Loss")]
        public int ContractSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use ORB Range Filter", Order = 1, GroupName = "Range Filter")]
        public bool UseRangeFilter { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Max ORB Range (Basis Points)", Order = 2, GroupName = "Range Filter")]
        public int MaxRangeBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Stats Table", Order = 1, GroupName = "Display")]
        public bool ShowStatsTable { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Trade Statistics", Order = 2, GroupName = "Display")]
        public bool ShowTradeStats { get; set; }

        [XmlIgnore]
        [Display(Name = "ORB Box Color", Order = 3, GroupName = "Display")]
        public Brush OrbBoxColor { get; set; }

        [Browsable(false)]
        public string OrbBoxColorSerializable
        {
            get { return Serialize.BrushToString(OrbBoxColor); }
            set { OrbBoxColor = Serialize.StringToBrush(value); }
        }

        #endregion
    }

    #region Enumerations
    public enum TakeProfitType
    {
        FixedPoints,
        BasisPoints,
        PercentageOfOrb,
        MultipleOfOrb
    }

    public enum StopLossType
    {
        OppositeOrb,
        OppositeOrbWithMaxLoss,
        PercentageOfOrb,
        FixedPoints,
        BasisPoints
    }
    #endregion
}