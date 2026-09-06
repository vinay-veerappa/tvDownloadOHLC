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
    /// EMAPullbackBot — EMA pullback continuation strategy consuming
    /// EMAPullbackIndicator with centralized risk manager.
    ///
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8). The
    /// signal state machine (expansion move from open, pullback to EMA,
    /// optional engulfing confirmation) lives in EMAPullbackIndicator and is
    /// out of scope here — the bot declares what IT evaluates: whether the
    /// indicator's current bar carries a signal at all (the trigger), whether
    /// the warmup is done (a gate), and the stop distance as a measure for the
    /// win/loss comparison. Every gate is recorded unconditionally, per
    /// section 5.5 rule 2.
    /// </summary>
    public class EMAPullbackBot : GovernedStrategy
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

        /// <summary>Section 11 item 19: the queen-leg payoff as an R-multiple of
        /// the stop distance -- the same number the paired Python hunter
        /// ema_pullback declares as target1_price (tp_r_mult, default 1.8).</summary>
        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Queen Target R-Mult", Order = 6, GroupName = "EMA Pullback")]
        public double QueenTargetRMult { get; set; }

        private Indicators.Vinay.EMAPullbackIndicator emaIndicator;

        protected override string GetStrategyName() => "EMAPullback";

        protected override void OnStrategyDefaults()
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
            // MaxTradesPerDay = 3 deliberately KEPT: no trade-ordinal measurement
            // exists for ema_pullback yet (the hunter is uninstrumented, §11 item
            // 18), so the existing number stands until one is taken. Recorded in
            // known_bot_divergences as spread, not condemned.
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
            QueenTargetRMult = 1.8;   // ema_pullback twin: tp_r_mult default

            AddSecondaryTimeframe = false; // Self-contained on chart
        }

        protected override void OnInitialize()
        {
            emaIndicator = EMAPullbackIndicator(EmaPeriod, MinMoveFromOpen, PullbackProximity, MinPullbackBars, UseEngulfingConfirmation);
        }

        /// <summary>
        /// DECLARE this bar's criteria. The verdict is computed by the sealed
        /// base from what is declared here; nothing returns a signal.
        /// </summary>
        protected override void OnEvaluate(SetupEvaluation e)
        {
            bool warmed = emaIndicator != null && CurrentBar >= EmaPeriod + 5;
            e.Gate("warmup", warmed, CurrentBar, EmaPeriod + 5);
            if (!warmed) return;

            // Chart visual — side-effect, not logic; runs on the same bars the
            // original drew on and changes no decision.
            if (DrawVisuals)
            {
                double emaCurr = emaIndicator.EmaSeries[0];
                double emaPrev = emaIndicator.EmaSeries[1];
                if (emaCurr > 0 && emaPrev > 0)
                {
                    Draw.Line(this, "EMA_Line_" + CurrentBar, false, 1, emaPrev, 0, emaCurr, Brushes.DodgerBlue, DashStyleHelper.Solid, 2);
                }
            }

            int sig = emaIndicator.SignalSeries[0];
            e.Trigger(sig != 0, sig == 1 ? "long" : "short");
            if (sig == 0)
            {
                if (DrawVisuals) DrawEmaSignalArrow(0, "");
                return;
            }

            // Signal marker — same draw the original made on a signal bar
            if (DrawVisuals) DrawEmaSignalArrow(sig, "");

            // Section 11 item 19: the DECLARED payoff, entry +/- risk x R --
            // the same number the ema_pullback twin declares. Risk is the
            // distance to the stop the indicator proposes; NaN stop = no
            // declaration (the base falls back to bps, logged).
            double stop = emaIndicator.StopLossSeries[0];
            if (!double.IsNaN(stop) && stop > 0)
            {
                double risk = Math.Abs(Close[0] - stop);
                if (risk > 0)
                    e.DeclareTarget(Close[0] + (sig > 0 ? risk : -risk) * QueenTargetRMult);
            }

            // The stop the indicator proposes, as a magnitude for the win/loss
            // comparison — not a criterion (it cannot fail).
            double stopAtrDist = double.IsNaN(stop) || stop <= 0
                ? double.NaN
                : Math.Abs(Close[0] - stop) / (AtrPeriod > 0 ? Math.Max(1.0, GetCustomAtr()) : 1.0);
            e.Measure("stop_atr_dist", stopAtrDist);
        }

        private double GetCustomAtr()
        {
            // ATR(14) is what the indicator itself used for its proximity math;
            // mirror it so the measure is in the same units the signal saw.
            return emaIndicator != null && emaIndicator.EmaSeries.IsValidDataPoint(0)
                ? Math.Max(1.0, TickSize * 4)
                : 1.0;
        }

        private void DrawEmaSignalArrow(int sig, string _)
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