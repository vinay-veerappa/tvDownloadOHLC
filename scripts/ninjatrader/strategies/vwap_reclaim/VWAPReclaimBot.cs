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
    /// <summary>
    /// VWAPReclaimBot — VWAP Reclaim/Rejection strategy consuming
    /// VWAPReclaimIndicator with centralized risk manager.
    ///
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8). The
    /// reclaim/rejection detection (confirmation bars, prior distance,
    /// cooldown) lives in VWAPReclaimIndicator; the bot declares what IT
    /// evaluates: the warmup gate and the indicator's signal as the trigger.
    /// Matches the frozen defaults exactly, so no value changes here.
    /// </summary>
    public class VWAPReclaimBot : GovernedStrategy
    {
        [NinjaScriptProperty]
        [Display(Name = "Confirmation Bars", Order = 1, GroupName = "VWAP Reclaim")]
        public int ConfirmationBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Bars Away From VWAP", Order = 2, GroupName = "VWAP Reclaim")]
        public int MinPriorBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signal Cooldown Bars", Order = 3, GroupName = "VWAP Reclaim")]
        public int CooldownBars { get; set; }

        /// <summary>Section 11 item 19: the queen-leg payoff as an R-multiple of
        /// the stop distance -- the same number the paired Python hunter
        /// vwap_reclaim declares as target1_price (tp_r_mult, default 1.8).</summary>
        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Queen Target R-Mult", Order = 4, GroupName = "VWAP Reclaim")]
        public double QueenTargetRMult { get; set; }

        private Indicators.Vinay.VWAPReclaimIndicator vwapIndicator;

        protected override string GetStrategyName() => "VWAPReclaim";

        protected override void OnStrategyDefaults()
        {
            Description = "VWAP Reclaim/Rejection strategy consuming VWAPReclaimIndicator with centralized risk manager";
            Name = "VWAPReclaimBot";

            StopAtrMult = 2.0;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.CoverTheQueen;
            BreakevenTriggerR = 2.0;
            TrailAtrMult = 3.5;

            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            // MaxTradesPerDay = 3 deliberately KEPT: no trade-ordinal measurement
            // exists for vwap_reclaim yet (hunter uninstrumented, §11 item 18),
            // so the existing number stands until one is taken.
            MaxTradesPerDay = 3;
            EarliestEntry = 930;
            LatestEntry = 1430;
            FlattenBy = 1545;

            ConfirmationBars = 2;
            MinPriorBars = 2;
            CooldownBars = 15;
            QueenTargetRMult = 1.8;   // vwap_reclaim twin: tp_r_mult default

            AddSecondaryTimeframe = false;
        }

        protected override void OnInitialize()
        {
            vwapIndicator = VWAPReclaimIndicator(ConfirmationBars, MinPriorBars, CooldownBars);
        }

        /// <summary>
        /// DECLARE this bar's criteria. The verdict is computed by the sealed
        /// base from what is declared here; nothing returns a signal.
        /// </summary>
        protected override void OnEvaluate(SetupEvaluation e)
        {
            bool warmed = vwapIndicator != null && CurrentBar >= 10;
            e.Gate("warmup", warmed, CurrentBar, 10);
            if (!warmed) return;

            // Chart visual — side-effect, not logic; unchanged from the original
            if (DrawVisuals)
            {
                double vwapCurr = vwapIndicator.VwapSeries[0];
                double vwapPrev = vwapIndicator.VwapSeries[1];
                if (vwapCurr > 0 && vwapPrev > 0)
                {
                    Draw.Line(this, "VWAP_Line_" + CurrentBar, false, 1, vwapPrev, 0, vwapCurr, Brushes.DarkOrange, DashStyleHelper.Solid, 2);
                }
            }

            int sig = vwapIndicator.SignalSeries[0];
            e.Trigger(sig != 0, sig == 1 ? "long" : "short");

            // Section 11 item 19: the DECLARED payoff, entry +/- risk x R --
            // the same number the vwap_reclaim twin declares. NaN stop = no
            // declaration (bps fallback, logged).
            if (sig != 0)
            {
                double stop = vwapIndicator.StopLossSeries[0];
                if (!double.IsNaN(stop) && stop > 0)
                {
                    double risk = Math.Abs(Close[0] - stop);
                    if (risk > 0)
                        e.DeclareTarget(Close[0] + (sig > 0 ? risk : -risk) * QueenTargetRMult);
                }
            }

            if (sig == 0 || !DrawVisuals) return;

            string tag = "VWAP_Strat_" + CurrentBar;
            if (sig == 1)
            {
                Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.DarkOrange);
                Draw.Text(this, tag + "_Txt", false, "VWAP BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.DarkOrange, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }
            else
            {
                Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.OrangeRed);
                Draw.Text(this, tag + "_Txt", false, "VWAP SELL", 0, High[0] + (10 * TickSize), 0, Brushes.DarkOrange, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (vwapIndicator == null || CurrentBar < 10) return double.NaN;
            double sl = vwapIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}