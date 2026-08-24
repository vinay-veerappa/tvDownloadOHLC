#region Using declarations
using System;
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
    public class VWAPReclaimIndicator : Indicator
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Confirmation Bars", Order = 1, GroupName = "Parameters")]
        public int ConfirmationBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Prior Bars Away", Order = 2, GroupName = "Parameters")]
        public int MinPriorBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signal Cooldown Bars", Order = 3, GroupName = "Parameters")]
        public int CooldownBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Order = 4, GroupName = "Visuals")]
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

        private double cumTypicalPriceVolume;
        private double cumVolume;
        private DateTime sessionDate;

        private int consecutiveClosesAbove;
        private int consecutiveClosesBelow;
        private int priorBelowStreak;
        private int priorAboveStreak;
        private long lastLongSignalBar;
        private long lastShortSignalBar;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Session VWAP Reclaim Indicator with visual line plot and reclaim trigger arrows.";
                Name = "VWAPReclaimIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                ConfirmationBars = 2;
                MinPriorBars = 2;
                CooldownBars = 15;
                ShowVisualElements = true;

                AddPlot(new Stroke(Brushes.DarkOrange, 2), PlotStyle.Line, "VWAP");
            }
            else if (State == State.DataLoaded)
            {
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);

                cumTypicalPriceVolume = 0;
                cumVolume = 0;
                sessionDate = DateTime.MinValue;
                consecutiveClosesAbove = 0;
                consecutiveClosesBelow = 0;
                priorBelowStreak = 0;
                priorAboveStreak = 0;
                lastLongSignalBar = -100000;
                lastShortSignalBar = -100000;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                return;
            }

            if (Time[0].Date != sessionDate)
            {
                sessionDate = Time[0].Date;
                cumTypicalPriceVolume = 0;
                cumVolume = 0;
                consecutiveClosesAbove = 0;
                consecutiveClosesBelow = 0;
                priorBelowStreak = 0;
                priorAboveStreak = 0;
            }

            double typicalPrice = (High[0] + Low[0] + Close[0]) / 3.0;
            double vol = Volume[0];

            cumTypicalPriceVolume += typicalPrice * vol;
            cumVolume += vol;

            double currentVWAP = cumVolume > 0 ? cumTypicalPriceVolume / cumVolume : typicalPrice;
            Values[0][0] = currentVWAP;

            // Tracking streaks
            if (Close[0] > currentVWAP)
            {
                if (consecutiveClosesBelow > 0)
                    priorBelowStreak = consecutiveClosesBelow;
                consecutiveClosesAbove++;
                consecutiveClosesBelow = 0;
            }
            else if (Close[0] < currentVWAP)
            {
                if (consecutiveClosesAbove > 0)
                    priorAboveStreak = consecutiveClosesAbove;
                consecutiveClosesBelow++;
                consecutiveClosesAbove = 0;
            }

            int signal = 0;
            double stopLoss = double.NaN;

            // Long reclaim
            if (consecutiveClosesAbove >= ConfirmationBars && priorBelowStreak >= MinPriorBars && (CurrentBar - lastLongSignalBar) >= CooldownBars)
            {
                signal = 1;
                lastLongSignalBar = CurrentBar;
                stopLoss = currentVWAP - (15 * TickSize * 4);

                if (ShowVisualElements)
                {
                    string tag = "VWAP_Buy_" + CurrentBar;
                    Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.DarkOrange);
                    Draw.Text(this, tag + "_txt", false, "VWAP BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.DarkOrange, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            // Short reject
            else if (consecutiveClosesBelow >= ConfirmationBars && priorAboveStreak >= MinPriorBars && (CurrentBar - lastShortSignalBar) >= CooldownBars)
            {
                signal = -1;
                lastShortSignalBar = CurrentBar;
                stopLoss = currentVWAP + (15 * TickSize * 4);

                if (ShowVisualElements)
                {
                    string tag = "VWAP_Sell_" + CurrentBar;
                    Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.DarkOrange);
                    Draw.Text(this, tag + "_txt", false, "VWAP SELL", 0, High[0] + (10 * TickSize), 0, Brushes.DarkOrange, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
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
        private Vinay.VWAPReclaimIndicator[] cacheVWAPReclaimIndicator;
        public Vinay.VWAPReclaimIndicator VWAPReclaimIndicator(int confirmationBars, int minPriorBars, int cooldownBars)
        {
            return VWAPReclaimIndicator(Input, confirmationBars, minPriorBars, cooldownBars, true);
        }

        public Vinay.VWAPReclaimIndicator VWAPReclaimIndicator(ISeries<double> input, int confirmationBars, int minPriorBars, int cooldownBars, bool showVisualElements)
        {
            if (cacheVWAPReclaimIndicator != null)
                for (int idx = 0; idx < cacheVWAPReclaimIndicator.Length; idx++)
                    if (cacheVWAPReclaimIndicator[idx] != null && cacheVWAPReclaimIndicator[idx].ConfirmationBars == confirmationBars && cacheVWAPReclaimIndicator[idx].MinPriorBars == minPriorBars && cacheVWAPReclaimIndicator[idx].CooldownBars == cooldownBars && cacheVWAPReclaimIndicator[idx].ShowVisualElements == showVisualElements && cacheVWAPReclaimIndicator[idx].EqualsInput(input))
                        return cacheVWAPReclaimIndicator[idx];
            return CacheIndicator<Vinay.VWAPReclaimIndicator>(new Vinay.VWAPReclaimIndicator() { ConfirmationBars = confirmationBars, MinPriorBars = minPriorBars, CooldownBars = cooldownBars, ShowVisualElements = showVisualElements }, input, ref cacheVWAPReclaimIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.VWAPReclaimIndicator VWAPReclaimIndicator(int confirmationBars, int minPriorBars, int cooldownBars)
        {
            return indicator.VWAPReclaimIndicator(Input, confirmationBars, minPriorBars, cooldownBars, true);
        }

        public Indicators.Vinay.VWAPReclaimIndicator VWAPReclaimIndicator(ISeries<double> input, int confirmationBars, int minPriorBars, int cooldownBars, bool showVisualElements)
        {
            return indicator.VWAPReclaimIndicator(input, confirmationBars, minPriorBars, cooldownBars, showVisualElements);
        }
    }
}
#endregion
