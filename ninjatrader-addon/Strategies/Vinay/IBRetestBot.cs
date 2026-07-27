#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// IBRetestBot — Play 2 (Retest-Continuation / Mid Pullback).
    /// Entry: touch of IB mid after the first break, continue in break direction.
    /// Stop: opposite IB boundary.
    /// Target: 0.5x IB range beyond break side.
    /// Validated E[R] +0.097 all-time (regime-dependent — best Wed, worst Mon).
    /// </summary>
    public class IBRetestBot : IBStrategyBase
    {
        protected override void ConfigureStrategy()
        {
        }

        protected override void SetStrategyDefaults()
        {
            base.SetStrategyDefaults();
            Name = "IBRetestBot";  // CRITICAL: override base's Name='RiskManagerBase' so SA loads THIS bot
            ActivePlay = 2;
            TargetLvl = 0.5;   // Play 2 best at 0.5x (E[R] +0.087, borderline significant)
            StopRMult = 1.0;   // Play 2 uses opposite IB boundary as stop (wider)
        }

        /// <summary>
        /// Play 2 entry: first break occurs, then price retests IB mid, continue in break direction.
        /// </summary>
        protected override int CheckForEntry()
        {
            TrackFirstBreak();  // track which side broke first
            if (firstBreakDir == 0) return 0;  // no break yet

            int breakMinutes = MinutesSinceIBComplete;
            double sizeMult = ClockSizeMultiplier(breakMinutes);

            // Long retest: first break was UP, price pulled back to IB mid, close back above mid
            if (firstBreakDir == 1 && Low[0] <= rangeMid && Close[0] >= rangeMid)
            {
                if (RequireDirectionBias && predictedDir != 1) return 0;

                double entry  = rangeMid;
                double stop   = rangeLow;                         // opposite IB boundary
                double target = rangeHigh + TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, 1)) return 0;

                int qty = CalcQuantity(entry - stop, sizeMult);
                EnterWithRangeStop(1, entry, stop, target, qty);
                return 1;
            }

            // Short retest: first break was DOWN, price pulled back to IB mid, close back below mid
            if (firstBreakDir == -1 && High[0] >= rangeMid && Close[0] <= rangeMid)
            {
                if (RequireDirectionBias && predictedDir != -1) return 0;

                double entry  = rangeMid;
                double stop   = rangeHigh;
                double target = rangeLow - TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, -1)) return 0;

                int qty = CalcQuantity(stop - entry, sizeMult);
                EnterWithRangeStop(-1, entry, stop, target, qty);
                return -1;
            }

            return 0;
        }

        private int CalcQuantity(double stopDistance, double sizeMult)
        {
            if (stopDistance <= 0) return 1;
            double riskPct = 0.005 * sizeMult;
            double dollarRisk = accountEquity * riskPct;
            int qty = (int)(dollarRisk / (stopDistance * GetPointValue()));
            return Math.Max(1, qty);
        }

        protected override string GetStrategyName() => "IB Retest Bot (Play 2)";
    }
}