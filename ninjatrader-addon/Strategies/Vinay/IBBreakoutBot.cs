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
    /// IBBreakoutBot — Play 1 (Breakout/Continuation).
    /// Entry: close beyond IB high/low (close-confirmed break).
    /// Stop: 0.25R MAE-calibrated (R = target distance).
    /// Target: 0.25x-1.0x IB range beyond break side.
    /// Validated E[R] +0.079 all-time (5-year, NQ1 NY AM IB30).
    /// </summary>
    public class IBBreakoutBot : IBStrategyBase
    {
        protected override void ConfigureStrategy()
        {
            Print("[DIAG] IBBreakoutBot.ConfigureStrategy called");
        }

        protected override void InitializeStrategy()
        {
            Print("[DIAG] IBBreakoutBot.InitializeStrategy called");
        }

        protected override void SetStrategyDefaults()
        {
            base.SetStrategyDefaults();
            Name = "IBBreakoutBot";  // CRITICAL: override base's Name='RiskManagerBase' so SA loads THIS bot
            ActivePlay = 1;
            TargetLvl = 0.5;   // Play 1 best at 0.5x (E[R] +0.093, PF 1.49)
            StopRMult = 0.25;  // MAE-calibrated
        }

        /// <summary>
        /// Play 1 entry: close-confirmed break of IB high/low.
        /// </summary>
        protected override int CheckForEntry()
        {
            // DIAG: log once per ~30 bars to avoid spam
            if (CurrentBar % 30 == 0)
                Print($"[DIAG] CheckForEntry bar={CurrentBar} time={ToET(Time[0]):HH:mm} close={Close[0]} rangeHigh={rangeHigh} rangeLow={rangeLow} rangeComplete={rangeComplete} predictedDir={predictedDir}");

            int breakMinutes = MinutesSinceIBComplete;
            double sizeMult = ClockSizeMultiplier(breakMinutes);

            // Long break: close above IB high
            if (Close[0] > rangeHigh)
            {
                if (RequireDirectionBias && predictedDir != 1) return 0;

                double entry  = Close[0];
                double stop   = entry - StopRMult * TargetLvl * rangeRange;  // MAE-calibrated
                double target = rangeHigh + TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, 1)) return 0;

                int qty = CalcQuantity(entry - stop, sizeMult);
                EnterWithRangeStop(1, entry, stop, target, qty);
                return 1;
            }

            // Short break: close below IB low
            if (Close[0] < rangeLow)
            {
                if (RequireDirectionBias && predictedDir != -1) return 0;

                double entry  = Close[0];
                double stop   = entry + StopRMult * TargetLvl * rangeRange;
                double target = rangeLow - TargetLvl * rangeRange;

                if (!TargetIsSane(entry, target, -1)) return 0;

                int qty = CalcQuantity(stop - entry, sizeMult);
                EnterWithRangeStop(-1, entry, stop, target, qty);
                return -1;
            }

            return 0;
        }

        /// <summary>
        /// Risk-scaled quantity: (equity * risk%) / (stopDistance * pointValue), min 1.
        /// </summary>
        private int CalcQuantity(double stopDistance, double sizeMult)
        {
            if (stopDistance <= 0) return 1;
            double riskPct = 0.005 * sizeMult;  // 0.5% base risk, scaled by clock
            double dollarRisk = accountEquity * riskPct;
            int qty = (int)(dollarRisk / (stopDistance * GetPointValue()));
            return Math.Max(1, qty);
        }

        protected override string GetStrategyName() => "IB Breakout Bot (Play 1)";
    }
}