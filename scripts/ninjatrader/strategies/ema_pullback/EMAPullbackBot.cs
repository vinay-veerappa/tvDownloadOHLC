#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class EMAPullbackBot : RiskManagerBase
    {
        [NinjaScriptProperty]
        [Display(Name = "EMA Period", Order = 1, GroupName = "EMA Pullback")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Move From Open (ATR mult)", Order = 2, GroupName = "EMA Pullback")]
        public double MinMoveFromOpen { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pullback Proximity (ATR mult)", Order = 3, GroupName = "EMA Pullback")]
        public double PullbackProximity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Pullback Bars", Order = 4, GroupName = "EMA Pullback")]
        public int MinPullbackBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Engulfing Confirmation", Order = 5, GroupName = "EMA Pullback")]
        public bool UseEngulfingConfirmation { get; set; }

        private Indicators.Vinay.EMAPullbackIndicator emaIndicator;

        protected override string GetStrategyName() => "EMAPullback";

        protected override void SetStrategyDefaults()
        {
            Description = "EMA pullback continuation strategy consuming EMAPullbackIndicator with centralized risk manager";
            Name = "EMAPullbackBot";

            // Trade management defaults
            StopAtrMult = 1.25;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.CoverTheQueen;
            TargetRMultiple = 3.0;
            BreakevenTriggerR = 1.0;
            TrailAtrMult = 2.0;

            // Risk/session defaults
            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 945;
            LatestEntry = 1530;
            FlattenBy = 1545;

            // Signal defaults
            EmaPeriod = 20;
            MinMoveFromOpen = 2.0;
            PullbackProximity = 0.3;
            MinPullbackBars = 1;
            UseEngulfingConfirmation = true;

            AddSecondaryTimeframe = false; // Self-contained on chart
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            emaIndicator = EMAPullbackIndicator(EmaPeriod, MinMoveFromOpen, PullbackProximity, MinPullbackBars, UseEngulfingConfirmation);
        }

        protected override int CheckForSignal()
        {
            if (emaIndicator == null || CurrentBar < EmaPeriod + 5) return 0;

            if (DrawVisuals && CurrentBar > EmaPeriod + 5)
            {
                double emaCurr = emaIndicator.EmaSeries[0];
                double emaPrev = emaIndicator.EmaSeries[1];
                if (emaCurr > 0 && emaPrev > 0)
                {
                    Draw.Line(this, "EMA_Line_" + CurrentBar, false, 1, emaPrev, 0, emaCurr, Brushes.DodgerBlue, DashStyleHelper.Solid, 2);
                }
            }

            int sig = emaIndicator.SignalSeries[0];
            if (sig != 0 && DrawVisuals)
            {
                string tag = "EMA_Strat_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.DodgerBlue);
                    Draw.Text(this, tag + "_Txt", false, "EMA BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.DodgerBlue, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.OrangeRed);
                    Draw.Text(this, tag + "_Txt", false, "EMA SELL", 0, High[0] + (10 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            return sig;
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (emaIndicator == null || CurrentBar < EmaPeriod + 5) return double.NaN;
            double sl = emaIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}
