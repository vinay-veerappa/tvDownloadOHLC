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
    public class SupertrendIndicator : Indicator
    {
        #region Parameters
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Period", Order = 1, GroupName = "Parameters")]
        public int Period { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 20.0)]
        [Display(Name = "Multiplier", Order = 2, GroupName = "Parameters")]
        public double Multiplier { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Arrows", Order = 3, GroupName = "Visuals")]
        public bool ShowVisualArrows { get; set; }
        #endregion

        #region Series / Plots
        [Browsable(false)]
        [XmlIgnore]
        public Series<int> SignalSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> TrendDirection { get; private set; }
        #endregion

        private ATR atr;
        private double stUpper;
        private double stLower;
        private double prevStValue;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Supertrend Indicator with directional plots, visual flip arrows, and exported signal series.";
                Name = "SupertrendIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                Period = 14;
                Multiplier = 2.0;
                ShowVisualArrows = true;

                AddPlot(new Stroke(Brushes.Lime, 2), PlotStyle.Line, "SupertrendUp");
                AddPlot(new Stroke(Brushes.Red, 2), PlotStyle.Line, "SupertrendDown");
            }
            else if (State == State.DataLoaded)
            {
                atr = ATR(Period);
                SignalSeries = new Series<int>(this);
                TrendDirection = new Series<int>(this);
                stUpper = stLower = 0;
                prevStValue = 0;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < Period)
            {
                SignalSeries[0] = 0;
                TrendDirection[0] = 0;
                return;
            }

            double hl2 = (High[0] + Low[0]) / 2.0;
            double atrVal = atr[0];
            double basicUpper = hl2 + (Multiplier * atrVal);
            double basicLower = hl2 - (Multiplier * atrVal);

            if (CurrentBar == Period)
            {
                stUpper = basicUpper;
                stLower = basicLower;
                prevStValue = Close[0] > hl2 ? stLower : stUpper;
                TrendDirection[0] = Close[0] > hl2 ? 1 : -1;
                SignalSeries[0] = 0;
                return;
            }

            // Continuous band calculation
            double prevUpper = stUpper;
            double prevLower = stLower;

            stLower = (basicLower > prevLower || Close[1] < prevLower) ? basicLower : prevLower;
            stUpper = (basicUpper < prevUpper || Close[1] > prevUpper) ? basicUpper : prevUpper;

            int prevDir = TrendDirection[1];
            int curDir = prevDir;

            if (prevDir == -1 && Close[0] > prevUpper)
                curDir = 1;
            else if (prevDir == 1 && Close[0] < prevLower)
                curDir = -1;

            TrendDirection[0] = curDir;
            double stValue = curDir == 1 ? stLower : stUpper;

            // Plot styling
            if (curDir == 1)
            {
                Values[0][0] = stValue; // SupertrendUp
                Values[1].Reset(0);
            }
            else
            {
                Values[1][0] = stValue; // SupertrendDown
                Values[0].Reset(0);
            }

            // Flip signal detection
            int signal = 0;
            if (curDir == 1 && prevDir == -1)
            {
                signal = 1; // Bullish flip
                if (ShowVisualArrows)
                {
                    string tag = "ST_Bull_" + CurrentBar;
                    Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.Lime);
                    Draw.Text(this, tag + "_txt", false, "ST BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.Lime, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            else if (curDir == -1 && prevDir == 1)
            {
                signal = -1; // Bearish flip
                if (ShowVisualArrows)
                {
                    string tag = "ST_Bear_" + CurrentBar;
                    Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.Red);
                    Draw.Text(this, tag + "_txt", false, "ST SELL", 0, High[0] + (10 * TickSize), 0, Brushes.Red, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }

            SignalSeries[0] = signal;
        }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.SupertrendIndicator[] cacheSupertrendIndicator;
        public Vinay.SupertrendIndicator SupertrendIndicator(int period, double multiplier)
        {
            return SupertrendIndicator(Input, period, multiplier, true);
        }

        public Vinay.SupertrendIndicator SupertrendIndicator(ISeries<double> input, int period, double multiplier, bool showVisualArrows)
        {
            if (cacheSupertrendIndicator != null)
                for (int idx = 0; idx < cacheSupertrendIndicator.Length; idx++)
                    if (cacheSupertrendIndicator[idx] != null && cacheSupertrendIndicator[idx].Period == period && cacheSupertrendIndicator[idx].Multiplier == multiplier && cacheSupertrendIndicator[idx].ShowVisualArrows == showVisualArrows && cacheSupertrendIndicator[idx].EqualsInput(input))
                        return cacheSupertrendIndicator[idx];
            return CacheIndicator<Vinay.SupertrendIndicator>(new Vinay.SupertrendIndicator() { Period = period, Multiplier = multiplier, ShowVisualArrows = showVisualArrows }, input, ref cacheSupertrendIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.SupertrendIndicator SupertrendIndicator(int period, double multiplier)
        {
            return indicator.SupertrendIndicator(Input, period, multiplier, true);
        }

        public Indicators.Vinay.SupertrendIndicator SupertrendIndicator(ISeries<double> input, int period, double multiplier, bool showVisualArrows)
        {
            return indicator.SupertrendIndicator(input, period, multiplier, showVisualArrows);
        }
    }
}
#endregion
