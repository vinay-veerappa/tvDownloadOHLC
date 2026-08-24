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
    public class EMAPullbackIndicator : Indicator
    {
        #region Parameters
        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "EMA Period", Order = 1, GroupName = "Parameters")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Move From Open (ATR mult)", Order = 2, GroupName = "Parameters")]
        public double MinMoveFromOpen { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pullback Proximity (ATR mult)", Order = 3, GroupName = "Parameters")]
        public double PullbackProximity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Pullback Bars", Order = 4, GroupName = "Parameters")]
        public int MinPullbackBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Engulfing Confirmation", Order = 5, GroupName = "Parameters")]
        public bool UseEngulfingConfirmation { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Arrows", Order = 6, GroupName = "Visuals")]
        public bool ShowVisualArrows { get; set; }
        #endregion

        #region Exported Series
        [Browsable(false)]
        [XmlIgnore]
        public Series<int> SignalSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> StopLossSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> EmaSeries { get; private set; }
        #endregion

        private EMA ema;
        private ATR atr;
        private DateTime sessionDate;
        private double sessionOpen;
        private bool initialMoveDetected;
        private int moveDirection;
        private int pullbackBars;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "EMA Pullback continuation indicator with visual plot, touch markers, and trigger arrows.";
                Name = "EMAPullbackIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                EmaPeriod = 20;
                MinMoveFromOpen = 2.0;
                PullbackProximity = 0.3;
                MinPullbackBars = 1;
                UseEngulfingConfirmation = true;
                ShowVisualArrows = true;

                AddPlot(new Stroke(Brushes.DodgerBlue, 2), PlotStyle.Line, "EmaLine");
            }
            else if (State == State.DataLoaded)
            {
                ema = EMA(EmaPeriod);
                atr = ATR(14);
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);
                EmaSeries = new Series<double>(this);
                sessionDate = DateTime.MinValue;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < EmaPeriod + 5)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                EmaSeries[0] = ema[0];
                return;
            }

            Values[0][0] = ema[0];
            EmaSeries[0] = ema[0];

            if (Time[0].Date != sessionDate)
            {
                sessionDate = Time[0].Date;
                sessionOpen = Open[0];
                initialMoveDetected = false;
                moveDirection = 0;
                pullbackBars = 0;
            }

            double atrVal = atr[0];
            if (atrVal <= 0)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                return;
            }

            // Step 1: Detect expansion move from open
            if (!initialMoveDetected)
            {
                double moveFromOpen = Close[0] - sessionOpen;
                double moveInAtr = Math.Abs(moveFromOpen) / atrVal;

                if (moveInAtr >= MinMoveFromOpen)
                {
                    initialMoveDetected = true;
                    moveDirection = moveFromOpen > 0 ? 1 : -1;
                    pullbackBars = 0;
                }
            }

            int signal = 0;
            double stopLoss = double.NaN;

            if (initialMoveDetected)
            {
                double emaVal = ema[0];
                double distToEma = Math.Abs(Close[0] - emaVal) / atrVal;
                bool nearEma = distToEma <= PullbackProximity || (moveDirection == 1 ? Low[0] <= emaVal : High[0] >= emaVal);

                if (nearEma)
                {
                    pullbackBars++;

                    if (pullbackBars >= MinPullbackBars)
                    {
                        bool confirmed = !UseEngulfingConfirmation;
                        if (UseEngulfingConfirmation && CurrentBar > 1)
                        {
                            if (moveDirection == 1)
                                confirmed = Close[0] > Open[0] && Close[0] > High[1];
                            else
                                confirmed = Close[0] < Open[0] && Close[0] < Low[1];
                        }

                        if (confirmed)
                        {
                            signal = moveDirection;
                            stopLoss = moveDirection == 1 ? Math.Min(Low[0], Low[1]) : Math.Max(High[0], High[1]);

                            if (ShowVisualArrows)
                            {
                                if (signal == 1)
                                {
                                    string tag = "EMA_Buy_" + CurrentBar;
                                    Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.DodgerBlue);
                                    Draw.Text(this, tag + "_txt", false, "EMA BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.DodgerBlue, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                                }
                                else
                                {
                                    string tag = "EMA_Sell_" + CurrentBar;
                                    Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.OrangeRed);
                                    Draw.Text(this, tag + "_txt", false, "EMA SELL", 0, High[0] + (10 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                                }
                            }

                            // Reset after trigger
                            initialMoveDetected = false;
                            pullbackBars = 0;
                        }
                    }
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
        private Vinay.EMAPullbackIndicator[] cacheEMAPullbackIndicator;
        public Vinay.EMAPullbackIndicator EMAPullbackIndicator(int emaPeriod, double minMoveFromOpen, double pullbackProximity, int minPullbackBars, bool useEngulfingConfirmation)
        {
            return EMAPullbackIndicator(Input, emaPeriod, minMoveFromOpen, pullbackProximity, minPullbackBars, useEngulfingConfirmation, true);
        }

        public Vinay.EMAPullbackIndicator EMAPullbackIndicator(ISeries<double> input, int emaPeriod, double minMoveFromOpen, double pullbackProximity, int minPullbackBars, bool useEngulfingConfirmation, bool showVisualArrows)
        {
            if (cacheEMAPullbackIndicator != null)
                for (int idx = 0; idx < cacheEMAPullbackIndicator.Length; idx++)
                    if (cacheEMAPullbackIndicator[idx] != null && cacheEMAPullbackIndicator[idx].EmaPeriod == emaPeriod && cacheEMAPullbackIndicator[idx].MinMoveFromOpen == minMoveFromOpen && cacheEMAPullbackIndicator[idx].PullbackProximity == pullbackProximity && cacheEMAPullbackIndicator[idx].MinPullbackBars == minPullbackBars && cacheEMAPullbackIndicator[idx].UseEngulfingConfirmation == useEngulfingConfirmation && cacheEMAPullbackIndicator[idx].ShowVisualArrows == showVisualArrows && cacheEMAPullbackIndicator[idx].EqualsInput(input))
                        return cacheEMAPullbackIndicator[idx];
            return CacheIndicator<Vinay.EMAPullbackIndicator>(new Vinay.EMAPullbackIndicator() { EmaPeriod = emaPeriod, MinMoveFromOpen = minMoveFromOpen, PullbackProximity = pullbackProximity, MinPullbackBars = minPullbackBars, UseEngulfingConfirmation = useEngulfingConfirmation, ShowVisualArrows = showVisualArrows }, input, ref cacheEMAPullbackIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.EMAPullbackIndicator EMAPullbackIndicator(int emaPeriod, double minMoveFromOpen, double pullbackProximity, int minPullbackBars, bool useEngulfingConfirmation)
        {
            return indicator.EMAPullbackIndicator(Input, emaPeriod, minMoveFromOpen, pullbackProximity, minPullbackBars, useEngulfingConfirmation, true);
        }

        public Indicators.Vinay.EMAPullbackIndicator EMAPullbackIndicator(ISeries<double> input, int emaPeriod, double minMoveFromOpen, double pullbackProximity, int minPullbackBars, bool useEngulfingConfirmation, bool showVisualArrows)
        {
            return indicator.EMAPullbackIndicator(input, emaPeriod, minMoveFromOpen, pullbackProximity, minPullbackBars, useEngulfingConfirmation, showVisualArrows);
        }
    }
}
#endregion
