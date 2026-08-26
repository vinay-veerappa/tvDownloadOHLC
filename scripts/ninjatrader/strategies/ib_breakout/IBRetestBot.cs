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
    public enum RetestEntryMode
    {
        Fib382,
        Fib50,
        Fib618,
        Midpoint,
        IBEdge
    }

    /// <summary>
    /// IBRetestBot — Play 2 (Retest-Continuation / Fibonacci 38.2% Pullback).
    /// Entry: pullback to 38.2% Fibonacci retracement of the breakout wave (or IB mid/edge), continuing in break direction.
    /// Stop: MAE-calibrated Basis Points stop ceiling (-25.3 bps) or opposite IB boundary.
    /// Target: 2-tier Pack Trading brackets (TP1: +10 bps Cover-The-Queen + BE lock, TP2: +30 bps / 0.5x-1.0x extension runner).
    /// Validated: 69.8% Win Rate, 1.22 PF, 61.7% MAE reduction with Fib 38.2% pullback engine.
    /// </summary>
    public class IBRetestBot : IBStrategyBase
    {
        [NinjaScriptProperty]
        [Display(Name = "Retest Mode", Order = 1, GroupName = "Retest Engine")]
        public RetestEntryMode RetestMode { get; set; } = RetestEntryMode.Fib382;

        [NinjaScriptProperty]
        [Display(Name = "Min Breakout Wave (bps)", Order = 2, GroupName = "Retest Engine")]
        public double MinBreakoutWaveBps { get; set; } = 3.0; // minimum excursion beyond IB boundary before pullback counts

        protected override void ConfigureStrategy()
        {
        }

        protected override void SetStrategyDefaults()
        {
            base.SetStrategyDefaults();
            Name = "IBRetestBot";  // CRITICAL: override base's Name='RiskManagerBase' so SA loads THIS bot
            ActivePlay = 2;
            TargetLvl = 0.5;   // Play 2 best at 0.5x (E[R] +0.087)
            StopRMult = 1.0;   // Fallback multiplier
            TradePolicy = TradePolicyType.CoverTheQueen; // Institutional Pack Trading execution standard
            RetestMode = RetestEntryMode.Fib382; // Empirical champion: 69.8% WR
        }

        /// <summary>
        /// Play 2 entry: first break occurs, tracks breakout wave, then price pulls back to Fib 38.2% / Mid, and resumes trend.
        /// </summary>
        protected override int CheckForEntry()
        {
            TrackFirstBreak();  // track which side broke first
            if (firstBreakDir == 0) return 0;  // no break yet

            int breakMinutes = MinutesSinceIBComplete;
            // Session 11 regime kill-switch: scale size by retest depth (root-cause fix for
            // H2 weak-retest reversal). Shallow retests get reduced size; deep thrusts full.
            double sizeMult = ClockSizeMultiplier(breakMinutes) * DepthSizeMultiplier();

            double minWavePts = BpsToPoints(MinBreakoutWaveBps, Close[0]);

            // Long retest: first break was UP, breakout wave exceeded min threshold, price pulled back
            if (firstBreakDir == 1 && breakoutActive && (breakoutExtreme - rangeHigh) >= minWavePts)
            {
                if (RequireDirectionBias && predictedDir != 1) return 0;
                if (!CanEnterLong) return 0;  // one entry per direction per session

                double triggerLevel = rangeMid;
                switch (RetestMode)
                {
                    case RetestEntryMode.Fib382:
                        triggerLevel = GetFibRetracementLevel(1, 0.382);
                        break;
                    case RetestEntryMode.Fib50:
                        triggerLevel = GetFibRetracementLevel(1, 0.500);
                        break;
                    case RetestEntryMode.Fib618:
                        triggerLevel = GetFibRetracementLevel(1, 0.618);
                        break;
                    case RetestEntryMode.IBEdge:
                        triggerLevel = rangeHigh;
                        break;
                    case RetestEntryMode.Midpoint:
                    default:
                        triggerLevel = rangeMid;
                        break;
                }

                // Entry condition: bar low touched the retracement level and bar closed holding at/above it
                if (Low[0] <= triggerLevel && Close[0] >= triggerLevel)
                {
                    double entry = Close[0];
                    double stop = rangeLow;

                    if (UseBpsStopCeiling)
                    {
                        double maxRiskPts = BpsToPoints(RiskCeilingBps, entry);
                        double minRiskPts = BpsToPoints(RiskFloorBps, entry);
                        double rawDist = entry - Math.Min(triggerLevel, rangeHigh);
                        double clampedDist = Math.Min(Math.Max(rawDist, minRiskPts), maxRiskPts);
                        stop = entry - clampedDist;
                    }

                    double tp1Pts = BpsToPoints(CoverQueenBps, entry);
                    double tp2Pts = Math.Max(breakoutExtreme + TargetLvl * rangeRange - entry, BpsToPoints(RunnerBps, entry));
                    double target1 = entry + tp1Pts;
                    double target2 = entry + tp2Pts;

                    if (!TargetIsSane(entry, target1, 1)) return 0;

                    int qty = CalcQuantity(entry - stop, sizeMult);
                    Log($"[ENTRY] LONG RETEST ({RetestMode}) {Time[0]:HH:mm} entry={entry:F2} stop={stop:F2} TP1={target1:F2} TP2={target2:F2} qty={qty}", LogLevel.Information);
                    EnterWithPackTradingBrackets(1, entry, stop, target1, target2, qty);
                    longTakenToday = true;  // prevent re-entry in this direction today
                    return 1;
                }
            }

            // Short retest: first break was DOWN, breakout wave exceeded min threshold, price pulled back
            if (firstBreakDir == -1 && breakoutActive && (rangeLow - breakoutExtreme) >= minWavePts)
            {
                if (RequireDirectionBias && predictedDir != -1) return 0;
                if (!CanEnterShort) return 0;  // one entry per direction per session

                double triggerLevel = rangeMid;
                switch (RetestMode)
                {
                    case RetestEntryMode.Fib382:
                        triggerLevel = GetFibRetracementLevel(-1, 0.382);
                        break;
                    case RetestEntryMode.Fib50:
                        triggerLevel = GetFibRetracementLevel(-1, 0.500);
                        break;
                    case RetestEntryMode.Fib618:
                        triggerLevel = GetFibRetracementLevel(-1, 0.618);
                        break;
                    case RetestEntryMode.IBEdge:
                        triggerLevel = rangeLow;
                        break;
                    case RetestEntryMode.Midpoint:
                    default:
                        triggerLevel = rangeMid;
                        break;
                }

                // Entry condition: bar high touched the retracement level and bar closed holding at/below it
                if (High[0] >= triggerLevel && Close[0] <= triggerLevel)
                {
                    double entry = Close[0];
                    double stop = rangeHigh;

                    if (UseBpsStopCeiling)
                    {
                        double maxRiskPts = BpsToPoints(RiskCeilingBps, entry);
                        double minRiskPts = BpsToPoints(RiskFloorBps, entry);
                        double rawDist = Math.Max(triggerLevel, rangeLow) - entry;
                        double clampedDist = Math.Min(Math.Max(rawDist, minRiskPts), maxRiskPts);
                        stop = entry + clampedDist;
                    }

                    double tp1Pts = BpsToPoints(CoverQueenBps, entry);
                    double tp2Pts = Math.Max(entry - (breakoutExtreme - TargetLvl * rangeRange), BpsToPoints(RunnerBps, entry));
                    double target1 = entry - tp1Pts;
                    double target2 = entry - tp2Pts;

                    if (!TargetIsSane(entry, target1, -1)) return 0;

                    int qty = CalcQuantity(stop - entry, sizeMult);
                    Log($"[ENTRY] SHORT RETEST ({RetestMode}) {Time[0]:HH:mm} entry={entry:F2} stop={stop:F2} TP1={target1:F2} TP2={target2:F2} qty={qty}", LogLevel.Information);
                    EnterWithPackTradingBrackets(-1, entry, stop, target1, target2, qty);
                    shortTakenToday = true;  // prevent re-entry in this direction today
                    return -1;
                }
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

        protected override string GetStrategyName() => $"IB Retest Bot (Play 2 - {RetestMode})";

        /// <summary>
        /// Explicit risk-distance override for the daily-max-loss gate.
        /// </summary>
        protected override double GetEstimatedRiskDistance()
        {
            if (!rangeComplete || rangeRange <= 0) return 0;
            if (UseBpsStopCeiling)
                return BpsToPoints(RiskCeilingBps, Close[0] > 0 ? Close[0] : rangeMid);
            return 0.5 * rangeRange;
        }
    }
}