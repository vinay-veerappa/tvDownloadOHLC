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
        [Display(Name = "Entry Mode (0=Market, 1=FVG Touch, 2=FVG CE 50%)", Order = 1, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Orderflow Filter", Order = 2, GroupName = "1. Strategy Variant")]
        public bool UseHtfFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter NY Lunch (12:00-13:30)", Order = 3, GroupName = "1. Strategy Variant")]
        public bool FilterLunch { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Require External Liquidity Sweep", Order = 4, GroupName = "1. Strategy Variant")]
        public bool RequireExternalSweep { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target (Bps)", Order = 5, GroupName = "2. Targets & Risk")]
        public double QueenTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (Bps)", Order = 6, GroupName = "2. Targets & Risk")]
        public double RunnerTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss (Bps)", Order = 7, GroupName = "2. Targets & Risk")]
        public double StopLossBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk Floor (Bps)", Order = 8, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 9, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable 50% Midline Reclaims", Order = 10, GroupName = "3. Midline Features")]
        public bool EnableMidlineReclaims { get; set; }
        #endregion

        private Indicators.Vinay.ICTFVGCISDIndicator ictIndicator;

        protected override string GetStrategyName() => "ICT_CISD";

        protected override void SetStrategyDefaults()
        {
            Description = "Institutional ICT Change in State of Delivery (CISD) & FVG Retest Strategy with Cover The Queen scale-out.";
            Name = "ICTFVGCISDBot";

            // Policy & Risk Defaults
            TradePolicy = TradePolicyType.CoverTheQueen;
            TargetRMultiple = 2.5;
            BreakevenTriggerR = 1.0;
            DailyMaxLoss = 1500;
            MaxTradesPerDay = 3;
            TrailingDrawdown = 2500;

            // Session Windows (09:45 Turnaround to 15:30 ET, Flat at 15:55 ET)
            EarliestEntry = 945;  // Filter 09:30-09:45 Judas Open Trap
            LatestEntry = 1530;
            FlattenBy = 1555;

            AddSecondaryTimeframe = false;
            DebugMode = true;

            Variant = 2;
            EntryMode = 1;               // 1 = FVG Limit Touch
            UseHtfFilter = true;         // Pro-Trend 4H Orderflow
            FilterLunch = true;          // Blackout 12:00-13:30
            RequireExternalSweep = false; // Modular toggle
            QueenTargetBps = 10.0;       // +10 Basis Points (0.10%)
            RunnerTargetBps = 30.0;      // +30 Basis Points (0.30%)
            StopLossBps = 5.0;           // 5.0 Basis Points tight FVG-covering stop
            MinRiskBps = 2.0;            // 2 Basis Points risk floor
            MaxRiskBps = 15.0;           // 15 Basis Points risk ceiling
            EnableMidlineReclaims = true;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            ictIndicator = ICTFVGCISDIndicator(Variant, EntryMode, UseHtfFilter, FilterLunch, RequireExternalSweep, QueenTargetBps, RunnerTargetBps, StopLossBps, MinRiskBps, MaxRiskBps, EnableMidlineReclaims);
        }

        protected override int CheckForSignal()
        {
            if (ictIndicator == null || CurrentBar < 50) return 0;

            if (DrawVisuals && CurrentBar > 50)
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

        protected override double GetCustomLimitPrice(int signal, double currentPrice)
        {
            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double lp = ictIndicator.LimitPriceSeries[0];
            if (!double.IsNaN(lp) && lp > 0) return lp;
            return double.NaN;
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double sl = ictIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDistance)
        {
            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double tp = ictIndicator.RunnerTargetSeries[0];
            if (!double.IsNaN(tp) && tp > 0) return tp;
            return double.NaN;
        }

        protected override double GetCurrentATR()
        {
            if (CurrentBar >= 14) return Math.Max(10.0, High[0] - Low[0]);
            return 15.0;
        }

        protected override double GetPotentialLoss()
        {
            if (ictIndicator != null && CurrentBar >= 50)
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