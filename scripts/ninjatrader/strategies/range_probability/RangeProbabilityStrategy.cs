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

        private RangeProbabilityIndicator rangeIndicator;
        private DateTime currentRangeStart = DateTime.MinValue;
        private double curO = double.NaN;
        private double curH = double.MinValue;
        private double curL = double.MaxValue;
        private double prvH = double.NaN;
        private double prvL = double.NaN;
        private TimeZoneInfo nyTimeZone;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Automated Range Probability Decile Edge Strategy for NinjaTrader 8.";
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
                MinProbThreshold = 70.0;
                MinResolveRate = 40.0;
                MinSampleSize = 20;
                OrderQuantity = 1;
                StopMode = "PriorMidpoint";
                FixedStopTicks = 40;
                FixedTargetTicks = 80;
                UseTrailingStop = false;
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
            }
            else if (State == State.DataLoaded)
            {
                rangeIndicator = RangeProbabilityIndicator(RangeMinutes, AnchorHourET);
                AddChartIndicator(rangeIndicator);
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

            bool isNewRange = (currentRangeStart == DateTime.MinValue) || (rStart != currentRangeStart);

            if (isNewRange)
            {
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

                // Check for trade signal entry at the open of the range
                if (!double.IsNaN(prvH) && prvH > prvL)
                {
                    double span = prvH - prvL;
                    double openPos = (curO - prvL) / span;
                    int bucket = openPos < 0.0 ? 0 : openPos >= 1.0 ? 11 : Math.Min(10, Math.Max(1, (int)Math.Floor(openPos * 10) + 1));
                    double priorMid = (prvH + prvL) / 2.0;

                    // Signal heuristics or indicator lookup
                    bool longSignal = bucket <= 2; // Oversold open decile
                    bool shortSignal = bucket >= 9; // Overbought open decile

                    if (longSignal && Position.MarketPosition == MarketPosition.Flat)
                    {
                        double targetPrice = prvH;
                        double stopPrice = (StopMode == "PriorMidpoint") ? priorMid : (curO - FixedStopTicks * TickSize);

                        int stopTicks = Math.Max(10, (int)Math.Round((curO - stopPrice) / TickSize));
                        int targetTicks = Math.Max(10, (int)Math.Round((targetPrice - curO) / TickSize));

                        SetStopLoss("LongRange", CalculationMode.Ticks, stopTicks, false);
                        SetProfitTarget("LongRange", CalculationMode.Ticks, targetTicks);
                        EnterLong(OrderQuantity, "LongRange");
                    }
                    else if (shortSignal && Position.MarketPosition == MarketPosition.Flat)
                    {
                        double targetPrice = prvL;
                        double stopPrice = (StopMode == "PriorMidpoint") ? priorMid : (curO + FixedStopTicks * TickSize);

                        int stopTicks = Math.Max(10, (int)Math.Round((stopPrice - curO) / TickSize));
                        int targetTicks = Math.Max(10, (int)Math.Round((curO - targetPrice) / TickSize));

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
        [Display(Name = "Stop Mode", GroupName = "Order Management", Order = 4)]
        public string StopMode { get => stopMode; set => stopMode = value; }

        [NinjaScriptProperty]
        [Range(5, 500)]
        [Display(Name = "Fixed Stop Ticks", GroupName = "Order Management", Order = 5)]
        public int FixedStopTicks { get => fixedStopTicks; set => fixedStopTicks = value; }

        [NinjaScriptProperty]
        [Range(5, 1000)]
        [Display(Name = "Fixed Target Ticks", GroupName = "Order Management", Order = 6)]
        public int FixedTargetTicks { get => fixedTargetTicks; set => fixedTargetTicks = value; }

        [NinjaScriptProperty]
        [Range(50.0, 95.0)]
        [Display(Name = "Min Probability Edge (%)", GroupName = "Filters", Order = 7)]
        public double MinProbThreshold { get => minProbThreshold; set => minProbThreshold = value; }

        [NinjaScriptProperty]
        [Range(20.0, 90.0)]
        [Display(Name = "Min Resolve Rate (%)", GroupName = "Filters", Order = 8)]
        public double MinResolveRate { get => minResolveRate; set => minResolveRate = value; }

        [NinjaScriptProperty]
        [Range(10, 500)]
        [Display(Name = "Min Sample Size", GroupName = "Filters", Order = 9)]
        public int MinSampleSize { get => minSampleSize; set => minSampleSize = value; }
        #endregion
    }
}
