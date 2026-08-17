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

//This namespace holds Strategies in this folder and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Strategies
{
    public class RangeProbabilityStrategy : Strategy
    {
        #region Variables
        private int rangeMinutes = 60;
        private int anchorHourET = 18;
        private double minProbThreshold = 70.0;
        private double minResolveRate = 40.0;
        private int minSampleSize = 20;

        private int orderQuantity = 1;
        private string stopMode = "PriorMidpoint"; // "PriorMidpoint", "FixedTicks"
        private int fixedStopTicks = 40;
        private int fixedTargetTicks = 80;
        private bool useTrailingStop = false;

        private DateTime currentRangeStart = DateTime.MinValue;
        private double curO = double.NaN;
        private double curH = double.MinValue;
        private double curL = double.MaxValue;
        private double prvH = double.NaN;
        private double prvL = double.NaN;
        private TimeZoneInfo nyTimeZone;

        // Direct self-contained LUT lookup table for 100% deterministic execution
        private Dictionary<string, RangeLutCell> lookupTable = new Dictionary<string, RangeLutCell>();

        // Session & Hourly Filtering
        private bool useHourlyFilter = true;
        private string allowedSlots = "0100,0300,0400,0600,0700,1000,1100,1200,1300,1400,1600,1800,1900,2000,2100,2200,2300";
        private HashSet<string> allowedSlotSet = new HashSet<string>();

        // Exit management
        private bool exitOnRangeClose = true;
        private string targetMode = "PriorBoundary";
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Automated Range Probability Decile Edge Strategy with Time-of-Day Hourly Filtering for NinjaTrader 8.";
                Name = "RangeProbabilityStrategy";
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
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;

                RangeMinutes = 60;
                AnchorHourET = 18;
                MinProbThreshold = 75.0;
                MinResolveRate = 45.0;
                MinSampleSize = 25;
                OrderQuantity = 1;
                TargetMode = "PriorBoundary";
                StopMode = "PriorOpposite";
                FixedStopTicks = 40;
                FixedTargetTicks = 80;
                UseTrailingStop = false;
                ExitOnRangeClose = true;
                UseHourlyFilter = true;
                AllowedSlots = "0100,0300,0400,0600,0700,1000,1100,1200,1300,1400,1600,1800,1900,2000,2100,2200,2300";
            }
            else if (State == State.Configure)
            {
                try
                {
                    nyTimeZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                }
                catch
                {
                    nyTimeZone = TimeZoneInfo.Local;
                }

                allowedSlotSet.Clear();
                if (!string.IsNullOrEmpty(AllowedSlots))
                {
                    foreach (var s in AllowedSlots.Split(','))
                    {
                        var trimmed = s.Trim();
                        if (!string.IsNullOrEmpty(trimmed)) allowedSlotSet.Add(trimmed);
                    }
                }

                string inst = (Instrument != null && Instrument.MasterInstrument != null) ? Instrument.MasterInstrument.Name : "NQ";
                lookupTable = RangeProbabilityLutData.GetEntries(inst, RangeMinutes);
            }
            else if (State == State.DataLoaded)
            {
                // Headless-safe: no UI chart indicator allocation needed
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;

            DateTime timeNy = TimeZoneInfo.ConvertTime(Time[0], nyTimeZone);
            int etMins = timeNy.Hour * 60 + timeNy.Minute;
            int sinceAnchor = (etMins - anchorHourET * 60 + 1440) % 1440;
            int offsetMins = sinceAnchor % rangeMinutes;
            DateTime rStart = timeNy.AddMinutes(-offsetMins).AddSeconds(-timeNy.Second);
            string slotStr = string.Format("{0:D2}{1:D2}", rStart.Hour, rStart.Minute);

            bool isNewRange = (currentRangeStart == DateTime.MinValue) || (rStart != currentRangeStart);

            if (isNewRange)
            {
                // Exit any open trade at the end of the range window if it hasn't hit target/stop
                if (ExitOnRangeClose && Position.MarketPosition != MarketPosition.Flat)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong();
                    else if (Position.MarketPosition == MarketPosition.Short)
                        ExitShort();
                }

                // Range rollover
                if (!double.IsNaN(curO))
                {
                    prvH = curH;
                    prvL = curL;
                }

                currentRangeStart = rStart;
                curO = Open[0];
                curH = High[0];
                curL = Low[0];

                // Check Time-of-Day Filter
                if (UseHourlyFilter && !allowedSlotSet.Contains(slotStr))
                {
                    return; // Skip toxic hours
                }

                // Check for trade signal entry at the open of the range
                if (!double.IsNaN(prvH) && prvH > prvL)
                {
                    double span = prvH - prvL;
                    double openPos = (curO - prvL) / span;
                    int bucket = openPos < 0.0 ? 0 : openPos >= 1.0 ? 11 : Math.Min(10, Math.Max(1, (int)Math.Floor(openPos * 10) + 1));
                    string bChar = "0123456789ab".Substring(bucket, 1);
                    string key = slotStr + bChar;

                    bool longSignal = false;
                    bool shortSignal = false;

                    if (lookupTable.TryGetValue(key, out var cell))
                    {
                        if (cell.Prob >= MinProbThreshold && cell.Res >= MinResolveRate && cell.N >= MinSampleSize)
                        {
                            if (cell.Dir == 'U') longSignal = true;
                            else if (cell.Dir == 'D') shortSignal = true;
                        }
                    }

                    double priorMid = (prvH + prvL) / 2.0;

                    if (longSignal && Position.MarketPosition == MarketPosition.Flat)
                    {
                        double targetPrice = (TargetMode == "PriorBoundary") ? prvH : (curO + FixedTargetTicks * TickSize);
                        double stopPrice = (StopMode == "PriorMidpoint") ? priorMid : (StopMode == "PriorOpposite") ? prvL : (curO - FixedStopTicks * TickSize);

                        if (stopPrice >= curO) stopPrice = curO - FixedStopTicks * TickSize;
                        if (targetPrice <= curO) targetPrice = curO + FixedTargetTicks * TickSize;

                        int stopTicks = Math.Max(4, (int)Math.Round((curO - stopPrice) / TickSize));
                        int targetTicks = Math.Max(4, (int)Math.Round((targetPrice - curO) / TickSize));

                        SetStopLoss("LongRange", CalculationMode.Ticks, stopTicks, false);
                        SetProfitTarget("LongRange", CalculationMode.Ticks, targetTicks);
                        EnterLong(OrderQuantity, "LongRange");
                    }
                    else if (shortSignal && Position.MarketPosition == MarketPosition.Flat)
                    {
                        double targetPrice = (TargetMode == "PriorBoundary") ? prvL : (curO - FixedTargetTicks * TickSize);
                        double stopPrice = (StopMode == "PriorMidpoint") ? priorMid : (StopMode == "PriorOpposite") ? prvH : (curO + FixedStopTicks * TickSize);

                        if (stopPrice <= curO) stopPrice = curO + FixedStopTicks * TickSize;
                        if (targetPrice >= curO) targetPrice = curO - FixedTargetTicks * TickSize;

                        int stopTicks = Math.Max(4, (int)Math.Round((stopPrice - curO) / TickSize));
                        int targetTicks = Math.Max(4, (int)Math.Round((curO - targetPrice) / TickSize));

                        SetStopLoss("ShortRange", CalculationMode.Ticks, stopTicks, false);
                        SetProfitTarget("ShortRange", CalculationMode.Ticks, targetTicks);
                        EnterShort(OrderQuantity, "ShortRange");
                    }
                }
            }
            else
            {
                curH = Math.Max(curH, High[0]);
                curL = Math.Min(curL, Low[0]);
            }
        }

        #region Properties
        [NinjaScriptProperty]
        [Range(15, 240)]
        [Display(Name = "Range Minutes", GroupName = "Strategy Parameters", Order = 1)]
        public int RangeMinutes { get => rangeMinutes; set => rangeMinutes = value; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Anchor Hour ET", GroupName = "Strategy Parameters", Order = 2)]
        public int AnchorHourET { get => anchorHourET; set => anchorHourET = value; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Order Quantity", GroupName = "Order Management", Order = 3)]
        public int OrderQuantity { get => orderQuantity; set => orderQuantity = value; }

        [NinjaScriptProperty]
        [Display(Name = "Target Mode", GroupName = "Order Management", Order = 4)]
        public string TargetMode { get => targetMode; set => targetMode = value; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Mode", GroupName = "Order Management", Order = 5)]
        public string StopMode { get => stopMode; set => stopMode = value; }

        [NinjaScriptProperty]
        [Range(5, 500)]
        [Display(Name = "Fixed Stop Ticks", GroupName = "Order Management", Order = 6)]
        public int FixedStopTicks { get => fixedStopTicks; set => fixedStopTicks = value; }

        [NinjaScriptProperty]
        [Range(5, 1000)]
        [Display(Name = "Fixed Target Ticks", GroupName = "Order Management", Order = 7)]
        public int FixedTargetTicks { get => fixedTargetTicks; set => fixedTargetTicks = value; }

        [NinjaScriptProperty]
        [Display(Name = "Exit on Range Close", GroupName = "Order Management", Order = 8)]
        public bool ExitOnRangeClose { get => exitOnRangeClose; set => exitOnRangeClose = value; }

        [NinjaScriptProperty]
        [Range(50.0, 95.0)]
        [Display(Name = "Min Probability Edge (%)", GroupName = "Filters", Order = 9)]
        public double MinProbThreshold { get => minProbThreshold; set => minProbThreshold = value; }

        [NinjaScriptProperty]
        [Range(20.0, 90.0)]
        [Display(Name = "Min Resolve Rate (%)", GroupName = "Filters", Order = 10)]
        public double MinResolveRate { get => minResolveRate; set => minResolveRate = value; }

        [NinjaScriptProperty]
        [Range(10, 500)]
        [Display(Name = "Min Sample Size", GroupName = "Filters", Order = 11)]
        public int MinSampleSize { get => minSampleSize; set => minSampleSize = value; }

        [NinjaScriptProperty]
        [Display(Name = "Use Trailing Stop", GroupName = "Order Management", Order = 12)]
        public bool UseTrailingStop { get => useTrailingStop; set => useTrailingStop = value; }

        [NinjaScriptProperty]
        [Display(Name = "Use Hourly Time Filter", GroupName = "Session Filters", Order = 13)]
        public bool UseHourlyFilter { get => useHourlyFilter; set => useHourlyFilter = value; }

        [NinjaScriptProperty]
        [Display(Name = "Allowed Slots (HHMM, CSV)", GroupName = "Session Filters", Order = 14)]
        public string AllowedSlots { get => allowedSlots; set => allowedSlots = value; }
        #endregion
    }
}
