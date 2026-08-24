#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class ICTFVGCISDBot : RiskManagerBase
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant (0=Baseline, 1=V1, 2=V2)", Order = 0, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target R-Mult", Order = 1, GroupName = "2. Targets & Risk")]
        public double RMultTP1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target R-Mult", Order = 2, GroupName = "2. Targets & Risk")]
        public double RMultTP2 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk (Bps)", Order = 3, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 4, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }
        #endregion

        private Indicators.Vinay.ICTFVGCISDIndicator ictIndicator;

        protected override string GetStrategyName() => "ICT_CISD";

        protected override void SetStrategyDefaults()
        {
            Description = "Institutional ICT Change in State of Delivery (CISD) & iFVG Strategy Engine with Cover The Queen scale-out.";
            Name = "ICTFVGCISDBot";

            // Policy & Risk
            TradePolicy = TradePolicyType.CoverTheQueen;
            TargetRMultiple = 2.5;
            BreakevenTriggerR = 1.0;
            DailyMaxLoss = 1500;
            MaxTradesPerDay = 3;
            TrailingDrawdown = 2500;

            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            AddSecondaryTimeframe = false; // Self-contained on primary chart series
            DebugMode = true;

            Variant = 2;
            RMultTP1 = 1.0;
            RMultTP2 = 2.5;
            MinRiskBps = 2.0;
            MaxRiskBps = 15.0;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            ictIndicator = ICTFVGCISDIndicator(Variant, RMultTP1, RMultTP2, MinRiskBps, MaxRiskBps);
        }

        protected override int CheckForSignal()
        {
            if (ictIndicator == null || CurrentBar < 20) return 0;

            if (DrawVisuals && CurrentBar > 20)
            {
                double cisdCurr = ictIndicator.CisdLevelSeries[0];
                double cisdPrev = ictIndicator.CisdLevelSeries[1];
                if (!double.IsNaN(cisdCurr) && !double.IsNaN(cisdPrev) && cisdCurr > 0 && cisdPrev > 0)
                {
                    Draw.Line(this, "CISD_Line_" + CurrentBar, false, 1, cisdPrev, 0, cisdCurr, Brushes.Gold, DashStyleHelper.Solid, 2);
                }
            }

            int sig = ictIndicator.SignalSeries[0];
            if (sig != 0 && DrawVisuals)
            {
                string tag = "CISD_Strat_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (6 * TickSize), Brushes.Gold);
                    Draw.Text(this, tag + "_Txt", false, "CISD BUY", 0, Low[0] - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (6 * TickSize), Brushes.Cyan);
                    Draw.Text(this, tag + "_Txt", false, "CISD SELL", 0, High[0] + (14 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            return sig;
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (ictIndicator == null || CurrentBar < 20) return double.NaN;
            double sl = ictIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetCurrentATR()
        {
            if (CurrentBar >= 14) return Math.Max(10.0, High[0] - Low[0]);
            return 15.0;
        }

        protected override double GetPotentialLoss()
        {
            if (ictIndicator != null && CurrentBar >= 20)
            {
                double sl = ictIndicator.StopLossSeries[0];
                if (!double.IsNaN(sl) && sl > 0)
                {
                    double dist = Math.Abs(Close[0] - sl);
                    return dist * GetPointValue() * Math.Max(1, DefaultQuantity);
                }
            }
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}