#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// Strat22RevStratBot - Automated 2-2 Reversal and RevStrat Momentum Trap Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    ///
    /// Logic:
    ///   - Bullish: Bar[1] is 2D (failed breakdown) -> Bar[0] breaks High[1] -> Signal Long = +1
    ///   - Bearish: Bar[1] is 2U (failed breakout) -> Bar[0] breaks Low[1] -> Signal Short = -1
    /// </summary>
    public class Strat22RevStratBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Require Rejection Wick (60%)", Order = 1, GroupName = "The Strat")]
        public bool RequireRejectionWick { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 2, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }
        #endregion

        protected override string GetStrategyName()
        {
            return "Strat22Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-2 Reversal and RevStrat momentum trap bot with centralized RiskManagerBase";
            Name = "Strat22RevStratBot";

            // Strat Parameters
            RequireRejectionWick = false;
            MinTargetPoints = 20.0;

            // RiskManagerBase Defaults
            DailyMaxLoss = 500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 4;
            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            // Brackets
            TradePolicy = "BreakevenTrail";
            TargetRMultiple = 2.0;
            BreakevenTriggerR = 1.0;
            AtrPeriod = 14;
            StopAtrMult = 1.5;
            TrailAtrMult = 2.0;
            AddSecondaryTimeframe = true;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
        }

        protected override int CheckForSignal()
        {
            if (CurrentBars[0] < 3)
                return 0;

            double h1 = Highs[0][1];
            double l1 = Lows[0][1];
            double o1 = Opens[0][1];
            double c1 = Closes[0][1];

            double h2 = Highs[0][2];
            double l2 = Lows[0][2];

            bool h1Higher = h1 > h2;
            bool l1Lower = l1 < l2;

            bool bar1Is2D = (l1Lower && !h1Higher);
            bool bar1Is2U = (h1Higher && !l1Lower);

            double h0 = Highs[0][0];
            double l0 = Lows[0][0];

            double range1 = h1 - l1;

            // 1. Bullish 2-2 Reversal: Bar[1] was 2D, Bar[0] breaks High[1]
            if (bar1Is2D && h0 > h1)
            {
                if (RequireRejectionWick && range1 > TickSize)
                {
                    double lowerWick = Math.Min(o1, c1) - l1;
                    if ((lowerWick / range1) < 0.60)
                        return 0;
                }
                return 1; // Long
            }

            // 2. Bearish 2-2 Reversal: Bar[1] was 2U, Bar[0] breaks Low[1]
            if (bar1Is2U && l0 < l1)
            {
                if (RequireRejectionWick && range1 > TickSize)
                {
                    double upperWick = h1 - Math.Max(o1, c1);
                    if ((upperWick / range1) < 0.60)
                        return 0;
                }
                return -1; // Short
            }

            return 0;
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
