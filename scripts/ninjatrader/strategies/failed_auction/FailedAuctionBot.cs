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
    /// FailedAuctionBot — failed auction single-print fill strategy consuming
    /// FailedAuctionIndicator with centralized risk manager.
    ///
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8). The
    /// failed-auction detection (fast move, wait window, proximity) lives in
    /// FailedAuctionIndicator; the bot declares what IT evaluates: the warmup
    /// gate and the indicator's signal as the trigger. Matches the frozen
    /// defaults exactly, so no value changes with this migration.
    /// </summary>
    public class FailedAuctionBot : GovernedStrategy
    {
        [NinjaScriptProperty]
        [Display(Name = "Fast Move Min Points", Order = 1, GroupName = "Failed Auction")]
        public double FastMoveMinPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fast Move Bars (1-min)", Order = 2, GroupName = "Failed Auction")]
        public int FastMoveBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Wait Bars For Fill", Order = 3, GroupName = "Failed Auction")]
        public int MaxWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Proximity (ATR mult)", Order = 4, GroupName = "Failed Auction")]
        public double EntryProximity { get; set; }

        /// <summary>Section 11 item 19: the queen-leg payoff as an R-multiple of
        /// the stop distance -- the same number the paired Python hunter
        /// failed_auction declares as target1_price (tp_r_mult, default 2.0).</summary>
        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Queen Target R-Mult", Order = 5, GroupName = "Failed Auction")]
        public double QueenTargetRMult { get; set; }

        private Indicators.Vinay.FailedAuctionIndicator faIndicator;

        protected override string GetStrategyName() => "FailedAuction";

        protected override void OnStrategyDefaults()
        {
            Description = "Failed auction single-print fill strategy consuming FailedAuctionIndicator with centralized risk manager";
            Name = "FailedAuctionBot";

            StopAtrMult = 3.5;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.CoverTheQueen;
            BreakevenTriggerR = 0.5;
            TrailAtrMult = 1.0;

            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            // MaxTradesPerDay = 3 deliberately KEPT: no trade-ordinal measurement
            // exists for failed_auction yet (hunter uninstrumented, §11 item 18),
            // so the existing number stands until one is taken.
            MaxTradesPerDay = 3;
            EarliestEntry = 930;
            LatestEntry = 1430;
            FlattenBy = 1545;

            FastMoveMinPoints = 20.0;
            FastMoveBars = 10;
            MaxWaitBars = 120;
            EntryProximity = 0.3;
            QueenTargetRMult = 2.0;   // failed_auction twin: tp_r_mult default

        }

        protected override void OnInitialize()
        {
            faIndicator = FailedAuctionIndicator(FastMoveMinPoints, FastMoveBars, MaxWaitBars, EntryProximity);
        }

        /// <summary>
        /// DECLARE this bar's criteria. The verdict is computed by the sealed
        /// base from what is declared here; nothing returns a signal.
        /// </summary>
        protected override void OnEvaluate(SetupEvaluation e)
        {
            bool warmed = faIndicator != null && CurrentBar >= FastMoveBars + 2;
            e.Gate("warmup", warmed, CurrentBar, FastMoveBars + 2);
            if (!warmed) return;

            int sig = faIndicator.SignalSeries[0];
            e.Trigger(sig != 0, sig == 1 ? "long" : "short");

            // Section 11 item 19: the DECLARED payoff, entry +/- risk x R --
            // the same number the failed_auction twin declares. NaN stop = no
            // declaration (bps fallback, logged).
            if (sig != 0)
            {
                double stop = faIndicator.StopLossSeries[0];
                if (!double.IsNaN(stop) && stop > 0)
                {
                    double risk = Math.Abs(Close[0] - stop);
                    if (risk > 0)
                        e.DeclareTarget(Close[0] + (sig > 0 ? risk : -risk) * QueenTargetRMult);
                }
            }

            if (sig == 0 || !DrawVisuals) return;

            string tag = "FA_Strat_" + CurrentBar;
            if (sig == 1)
            {
                Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.Magenta);
                Draw.Text(this, tag + "_Txt", false, "FA BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }
            else
            {
                Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.Magenta);
                Draw.Text(this, tag + "_Txt", false, "FA SELL", 0, High[0] + (10 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (faIndicator == null || CurrentBar < FastMoveBars + 2) return double.NaN;
            double sl = faIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}
