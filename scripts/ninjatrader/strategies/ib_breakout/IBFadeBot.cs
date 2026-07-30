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
    /// IBFadeBot — Play 3 (Fade / Reversion).
    /// Entry: 0.25x overshoot beyond IB boundary, then close back inside → fade to IB mid.
    /// Stop: 0.5x IB range beyond the boundary.
    /// Target: IB mid.
    /// Validated E[R] +0.259 at 0.25x target (strongest single strategy, PF 1.51).
    ///
    /// This is the DEFAULT play (Phase D finding: Play 3 at 0.25x is the standout).
    /// The overshoot state machine lives in IBStrategyBase (overshootAbove/overshootBelow).
    /// </summary>
    public class IBFadeBot : IBStrategyBase
    {
        protected override void ConfigureStrategy()
        {
        }

        protected override void SetStrategyDefaults()
        {
            base.SetStrategyDefaults();
            Name = "IBFadeBot";  // CRITICAL: override base's Name='RiskManagerBase' so SA loads THIS bot
            ActivePlay = 3;
            TargetLvl = 1.0;   // Full reversion to opposite IB boundary (2:1 R:R with 0.5R stop)
            StopRMult = 0.5;   // 0.5R stop beyond boundary (0.5x range)
            LateBreakSizeMult = 0.35;  // NT8-validated: 0.35x overshoot threshold (PF 1.215, net +$609)
            ConfluenceFilterEnabled = true;  // Enable Play 3 validated filter stack
        }

        /// <summary>
        /// Play 3 entry: detect overshoot, then fade on close-back-inside.
        /// Two-state bar-close-only state machine (Q5 resolution).
        /// </summary>
        protected override int CheckForEntry()
        {
            DetectOvershoot();  // update overshootAbove/overshootBelow flags

            int breakMinutes = MinutesSinceIBComplete;
            double sizeMult = ClockSizeMultiplier(breakMinutes);

            // Fade the upside overshoot: close back below IB high after overshooting above
            if (overshootAbove && Close[0] < rangeHigh)
            {
                if (!CanEnterShort)  // one entry per direction per session
                    return 0;

                double entry  = rangeHigh;
                // Stop: StopRMult * range beyond the boundary (default 0.5R).
                double stop   = rangeHigh + StopRMult * rangeRange;
                // Target: TargetLvl * range reversion from entry (Python-validated 0.25x).
                // Python Edge Validation: Play 3 at 0.25x target is the standout
                // (E[R] +0.259, PF 1.51, 38.5% WR). 0.5x target is NOT significant.
                double target = rangeHigh - TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, -1)) { overshootAbove = false; return 0; }

                int qty = CalcQuantity(stop - entry, sizeMult);
                EnterWithRangeStop(-1, entry, stop, target, qty);
                overshootAbove = false;  // reset after entry (Q5: reset on successful entry)
                shortTakenToday = true;  // prevent re-entry in this direction today
                return -1;
            }

            // Fade the downside overshoot: close back above IB low after overshooting below
            if (overshootBelow && Close[0] > rangeLow)
            {
                if (!CanEnterLong)  // one entry per direction per session
                    return 0;

                double entry  = rangeLow;
                double stop   = rangeLow - StopRMult * rangeRange;
                // Target: TargetLvl * range reversion from entry (0.25x).
                double target = rangeLow + TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, 1)) { overshootBelow = false; return 0; }

                int qty = CalcQuantity(entry - stop, sizeMult);
                EnterWithRangeStop(1, entry, stop, target, qty);
                overshootBelow = false;
                longTakenToday = true;  // prevent re-entry in this direction today
                return 1;
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

        /// <summary>
        /// IBFadeBot stop geometry differs from the default IB formula: the stop
        /// is placed StopRMult * rangeRange beyond the IB boundary (0.5R), with NO
        /// TargetLvl multiplier. Override so the daily-max-loss gate uses the
        /// actual stop distance instead of over-estimating via TargetLvl.
        /// </summary>
        protected override double GetEstimatedRiskDistance()
        {
            if (!rangeComplete || rangeRange <= 0) return 0;
            return StopRMult * rangeRange;
        }

        protected override string GetStrategyName() => "IB Fade Bot (Play 3)";
    }
}