#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class FailedAuctionIndicator : Indicator
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Fast Move Min Points", Order = 1, GroupName = "Parameters")]
        public double FastMoveMinPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fast Move Lookback (bars)", Order = 2, GroupName = "Parameters")]
        public int FastMoveBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Wait Bars For Fill", Order = 3, GroupName = "Parameters")]
        public int MaxWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Proximity (ATR mult)", Order = 4, GroupName = "Parameters")]
        public double EntryProximity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Order = 5, GroupName = "Visuals")]
        public bool ShowVisualElements { get; set; }
        #endregion

        #region Exported Series
        [Browsable(false)]
        [XmlIgnore]
        public Series<int> SignalSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> StopLossSeries { get; private set; }
        #endregion

        private struct SinglePrintLevel
        {
            public double OriginPrice;
            public double TargetPrice;
            public int Direction;
            public int CreatedBar;
            public bool Filled;
        }

        private List<SinglePrintLevel> activeLevels;
        private DateTime levelsSessionDate;
        private ATR atr;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Failed auction single-print fill indicator with visual level lines and trigger arrows.";
                Name = "FailedAuctionIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                FastMoveMinPoints = 20.0;
                FastMoveBars = 10;
                MaxWaitBars = 120;
                EntryProximity = 0.3;
                ShowVisualElements = true;
            }
            else if (State == State.DataLoaded)
            {
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);
                activeLevels = new List<SinglePrintLevel>();
                levelsSessionDate = DateTime.MinValue;
                atr = ATR(14);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < FastMoveBars + 2)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                return;
            }

            if (Time[0].Date != levelsSessionDate)
            {
                activeLevels.Clear();
                levelsSessionDate = Time[0].Date;
            }

            double atrVal = atr[0];
            if (atrVal <= 0)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                return;
            }

            double close = Close[0];
            double pastClose = Close[FastMoveBars];
            double move = close - pastClose;

            if (Math.Abs(move) >= FastMoveMinPoints)
            {
                SinglePrintLevel spl;
                spl.OriginPrice = pastClose;
                spl.TargetPrice = close;
                spl.Direction = move > 0 ? 1 : -1;
                spl.CreatedBar = CurrentBar;
                spl.Filled = false;
                activeLevels.Add(spl);
            }

            int signal = 0;
            double stopLoss = double.NaN;

            for (int i = activeLevels.Count - 1; i >= 0; i--)
            {
                SinglePrintLevel lvl = activeLevels[i];
                if (lvl.Filled || (CurrentBar - lvl.CreatedBar) > MaxWaitBars)
                    continue;

                double distToOrigin = Math.Abs(close - lvl.OriginPrice);
                if (distToOrigin <= EntryProximity * atrVal)
                {
                    // Reversion trigger
                    signal = -lvl.Direction;
                    stopLoss = lvl.Direction == 1 ? Low[0] - (10 * TickSize) : High[0] + (10 * TickSize);
                    lvl.Filled = true;
                    activeLevels[i] = lvl;

                    if (ShowVisualElements)
                    {
                        if (signal == 1)
                        {
                            string tag = "FA_Buy_" + CurrentBar;
                            Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.Magenta);
                            Draw.Text(this, tag + "_txt", false, "FA BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                        else
                        {
                            string tag = "FA_Sell_" + CurrentBar;
                            Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.Magenta);
                            Draw.Text(this, tag + "_txt", false, "FA SELL", 0, High[0] + (10 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                    }
                    break;
                }
            }

            SignalSeries[0] = signal;
            StopLossSeries[0] = stopLoss;
        }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.FailedAuctionIndicator[] cacheFailedAuctionIndicator;
        public Vinay.FailedAuctionIndicator FailedAuctionIndicator(double fastMoveMinPoints, int fastMoveBars, int maxWaitBars, double entryProximity)
        {
            return FailedAuctionIndicator(Input, fastMoveMinPoints, fastMoveBars, maxWaitBars, entryProximity, true);
        }

        public Vinay.FailedAuctionIndicator FailedAuctionIndicator(ISeries<double> input, double fastMoveMinPoints, int fastMoveBars, int maxWaitBars, double entryProximity, bool showVisualElements)
        {
            if (cacheFailedAuctionIndicator != null)
                for (int idx = 0; idx < cacheFailedAuctionIndicator.Length; idx++)
                    if (cacheFailedAuctionIndicator[idx] != null && cacheFailedAuctionIndicator[idx].FastMoveMinPoints == fastMoveMinPoints && cacheFailedAuctionIndicator[idx].FastMoveBars == fastMoveBars && cacheFailedAuctionIndicator[idx].MaxWaitBars == maxWaitBars && cacheFailedAuctionIndicator[idx].EntryProximity == entryProximity && cacheFailedAuctionIndicator[idx].ShowVisualElements == showVisualElements && cacheFailedAuctionIndicator[idx].EqualsInput(input))
                        return cacheFailedAuctionIndicator[idx];
            return CacheIndicator<Vinay.FailedAuctionIndicator>(new Vinay.FailedAuctionIndicator() { FastMoveMinPoints = fastMoveMinPoints, FastMoveBars = fastMoveBars, MaxWaitBars = maxWaitBars, EntryProximity = entryProximity, ShowVisualElements = showVisualElements }, input, ref cacheFailedAuctionIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.FailedAuctionIndicator FailedAuctionIndicator(double fastMoveMinPoints, int fastMoveBars, int maxWaitBars, double entryProximity)
        {
            return indicator.FailedAuctionIndicator(Input, fastMoveMinPoints, fastMoveBars, maxWaitBars, entryProximity, true);
        }

        public Indicators.Vinay.FailedAuctionIndicator FailedAuctionIndicator(ISeries<double> input, double fastMoveMinPoints, int fastMoveBars, int maxWaitBars, double entryProximity, bool showVisualElements)
        {
            return indicator.FailedAuctionIndicator(input, fastMoveMinPoints, fastMoveBars, maxWaitBars, entryProximity, showVisualElements);
        }
    }
}
#endregion
