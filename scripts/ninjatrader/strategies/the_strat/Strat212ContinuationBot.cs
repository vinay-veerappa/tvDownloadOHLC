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
    /// Strat212ContinuationBot - Automated 2-1-2 Strat Continuation Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    ///
    /// Logic:
    ///   - Bullish 2-1-2: Bar[2] is 2U (Higher High), Bar[1] is 1 (Inside Bar) -> Signal Long = +1
    ///   - Bearish 2-1-2: Bar[2] is 2D (Lower Low), Bar[1] is 1 (Inside Bar) -> Signal Short = -1
    /// </summary>
    public class Strat212ContinuationBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Allow Reversals (2D-1-2U / 2U-1-2D)", Order = 1, GroupName = "The Strat")]
        public bool AllowReversals { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 2, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }
        #endregion

        protected override string GetStrategyName()
        {
            return "Strat212Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-1-2 Strat continuation and reversal bot with centralized RiskManagerBase";
            Name = "Strat212ContinuationBot";

            // Strat Parameters
            AllowReversals = false;
            MinTargetPoints = 15.0;

            // RiskManagerBase Defaults (NQ 5m)
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

            // Evaluate Bar[1] vs Bar[2] for Strat Type
            double h1 = Highs[0][1];
            double l1 = Lows[0][1];
            double h2 = Highs[0][2];
            double l2 = Lows[0][2];

            bool h1Higher = h1 > h2;
            bool l1Lower = l1 < l2;

            // Bar[1] must be an Inside Bar (Type 1): High[1] <= High[2] and Low[1] >= Low[2]
            bool bar1IsInside = (!h1Higher && !l1Lower);
            if (!bar1IsInside)
                return 0;

            // Evaluate Bar[2] vs Bar[3]
            if (CurrentBars[0] < 4)
                return 0;

            double h3 = Highs[0][3];
            double l3 = Lows[0][3];
            bool h2Higher = h2 > h3;
            bool l2Lower = l2 < l3;

            bool bar2Is2U = (h2Higher && !l2Lower);
            bool bar2Is2D = (l2Lower && !h2Higher);

            // Check current bar trigger
            double h0 = Highs[0][0];
            double l0 = Lows[0][0];

            // Bullish Trigger: Current bar breaks High[1]
            if (h0 > h1)
            {
                if (bar2Is2U || (AllowReversals && bar2Is2D))
                {
                    double targetDist = Math.Max(MinTargetPoints, h2 - h1);
                    if (targetDist >= MinTargetPoints)
                        return 1; // Long
                }
            }

            // Bearish Trigger: Current bar breaks Low[1]
            if (l0 < l1)
            {
                if (bar2Is2D || (AllowReversals && bar2Is2U))
                {
                    double targetDist = Math.Max(MinTargetPoints, l1 - l2);
                    if (targetDist >= MinTargetPoints)
                        return -1; // Short
                }
            }

            return 0;
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
