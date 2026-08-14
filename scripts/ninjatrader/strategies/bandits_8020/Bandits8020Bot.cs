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
    public enum BanditsSizingMode
    {
        FixedQuantity,
        AutoMicroScale,
        TargetRiskDollars
    }

    /// <summary>
    /// Bandits8020Bot — High-Precision Level Sniping & Sub-Grid Reversion Bot for NinjaTrader 8.
    /// 
    /// Key Capabilities:
    /// 1. Automatic Instrument Profiling: Automatically detects NQ, MNQ, ES, MES, YM, MYM, CL, MCL, RTY, M2K
    ///    and configures appropriate Grid Handles (100 vs 25 vs 1.0), Stop Distances, and Targets.
    /// 2. Multi-Contract Auto-Scaling:
    ///    - AutoMicroScale: Automatically scales 10x contracts on Micros to match Mini dollar risk/PnL.
    ///    - TargetRiskDollars: Computes exact contract quantities based on fixed dollar risk (e.g. $200 risk/trade).
    /// 3. Precision Limit Execution: Submits limit orders directly at xx20 & xx80 nodes.
    /// 4. True RTH Open (09:30 ET) Directional Dealing Bias Gate.
    /// 5. Prop Firm ATM Brackets with strict 2R daily loss limits.
    /// </summary>
    public class Bandits8020Bot : RiskManagerBase
    {
        #region Parameters

        #region Instrument & Auto-Calibration
        [NinjaScriptProperty]
        [Display(Name = "Auto-Calibrate by Instrument", Order = 1, GroupName = "1. Instrument & Auto-Calibration",
                 Description = "Automatically configures grid handle, stop loss, and targets based on detected ticker (NQ/ES/CL/YM/RTY)")]
        public bool AutoCalibrateInstrument { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Position Sizing Mode", Order = 2, GroupName = "1. Instrument & Auto-Calibration",
                 Description = "Choose between Fixed Quantity, Auto Micro Scaling (10x), or Fixed Dollar Risk Sizing")]
        public BanditsSizingMode SizingMode { get; set; } = BanditsSizingMode.TargetRiskDollars;

        [NinjaScriptProperty]
        [Display(Name = "Target Risk Per Trade ($)", Order = 3, GroupName = "1. Instrument & Auto-Calibration",
                 Description = "Fixed dollar risk per trade when Sizing Mode = TargetRiskDollars (e.g. $200)")]
        public double TargetRiskDollars { get; set; } = 200.0;
        #endregion

        #region Grid Configuration
        [NinjaScriptProperty]
        [Display(Name = "Grid Unit (pts)", Order = 1, GroupName = "2. Sub-Grid Configuration",
                 Description = "Macro grid handle (100 for NQ/YM, 25 for ES quarters, 1.0 for CL)")]
        public double GridUnit { get; set; } = 100.0;

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss (pts)", Order = 2, GroupName = "2. Sub-Grid Configuration",
                 Description = "Fixed stop loss distance in points (10.0 for NQ, 2.50 for ES)")]
        public double StopLossPoints { get; set; } = 10.0;

        [NinjaScriptProperty]
        [Display(Name = "Profit Target (pts)", Order = 3, GroupName = "2. Sub-Grid Configuration",
                 Description = "Fixed profit target in points (20.0 for NQ, 5.0 for ES)")]
        public double ProfitTargetPoints { get; set; } = 20.0;

        [NinjaScriptProperty]
        [Display(Name = "Level Proximity Tolerance (ticks)", Order = 4, GroupName = "2. Sub-Grid Configuration",
                 Description = "Tolerance in ticks to consider price interacting with the level")]
        public int LevelToleranceTicks { get; set; } = 4;
        #endregion

        #region Microstructure Setups
        [NinjaScriptProperty]
        [Display(Name = "Enable Fork Reversals", Order = 1, GroupName = "3. Setups & Microstructure",
                 Description = "Enable Fork (Twin-Wick Liquidity Sweep) reversal entries")]
        public bool EnableForkReversal { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Level Sniping", Order = 2, GroupName = "3. Setups & Microstructure",
                 Description = "Enable direct limit/touch sniping at xx20 and xx80 nodes")]
        public bool EnableLevelSniping { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable 'h' Pattern", Order = 3, GroupName = "3. Setups & Microstructure",
                 Description = "Enable lowercase 'h' pattern bearish continuation entries")]
        public bool EnableHPattern { get; set; } = true;
        #endregion

        #region Filters & Time Windows
        [NinjaScriptProperty]
        [Display(Name = "Use RTH Open Trend Gate", Order = 1, GroupName = "4. Filters & Sessions",
                 Description = "Filter trades with true 09:30 AM ET RTH Open institutional directional bias")]
        public bool UseRthOpenBias { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Trade Asia Session", Order = 2, GroupName = "4. Filters & Sessions",
                 Description = "Allow trading during Asia prime windows (18:00-19:00 & 20:00-21:00 ET)")]
        public bool TradeAsiaSession { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Skip Overnight Dead Zone", Order = 3, GroupName = "4. Filters & Sessions",
                 Description = "Strictly block entries between 23:00 and 01:30 ET")]
        public bool SkipDeadZone { get; set; } = true;
        #endregion

        #endregion

        #region Internal State

        private double rthOpenPrice;
        private bool rthOpenCaptured;
        private DateTime sessionDate;
        private int lastEntryBar;
        private double lastLevelTouched;
        private int touchesOnCurrentLevelToday;
        private bool isMicroInstrument;
        private int calculatedQuantity;

        #endregion

        protected override string GetStrategyName()
        {
            return "Bandits8020";
        }

        protected override void SetStrategyDefaults()
        {
            Description                  = "Prop Firm Bandits 80/20 & Orderflow Sub-Grid Strategy with Auto-Calibration & Contract Scaling";
            Name                         = "Bandits8020Bot";
            Calculate                    = Calculate.OnBarClose;
            EntriesPerDirection          = 1;
            EntryHandling                = EntryHandling.AllEntries;
            IsExitOnSessionCloseStrategy = true;
            ExitOnSessionCloseSeconds    = 60;
            IsFillLimitOnTouch           = true;

            StopAtrMult       = 1.0;
            TradePolicy       = "FixedTarget";
            TargetRMultiple   = 2.0;
            BreakevenTriggerR = 1.0;
            TrailAtrMult      = 1.0;

            StartingAccountBalance    = 50000;
            DailyMaxLoss              = 400;
            MaxConsecutiveLosers      = 2;
            PauseMinutes              = 45;
            HardStopConsecutiveLosers = 2;
            MaxTradesPerDay           = 3;
            TrailingDrawdown          = 2000;
            StopOnAccountBlown        = false;

            EarliestEntry = 930;
            LatestEntry   = 1100;
            FlattenBy     = 1555;

            AddSecondaryTimeframe = false;
            DebugMode             = false;

            AutoCalibrateInstrument = true;
            SizingMode              = BanditsSizingMode.TargetRiskDollars;
            TargetRiskDollars       = 200.0;

            GridUnit           = 100.0;
            StopLossPoints     = 10.0;
            ProfitTargetPoints = 20.0;
            LevelToleranceTicks= 4;
            EnableForkReversal = true;
            EnableLevelSniping = true;
            EnableHPattern     = true;
            UseRthOpenBias     = true;
            TradeAsiaSession   = false;
            SkipDeadZone       = true;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            lastEntryBar = -100;
            lastLevelTouched = 0;
            touchesOnCurrentLevelToday = 0;
            rthOpenPrice = 0;
            rthOpenCaptured = false;
            sessionDate = DateTime.MinValue;

            CalibrateInstrumentSettings();
        }

        private void CalibrateInstrumentSettings()
        {
            if (Instrument == null || Instrument.MasterInstrument == null)
                return;

            string name = Instrument.MasterInstrument.Name.ToUpper();
            isMicroInstrument = name.StartsWith("M") && (name.Contains("NQ") || name.Contains("ES") || name.Contains("YM") || name.Contains("CL") || name.Contains("2K") || name.Contains("RTY"));

            if (AutoCalibrateInstrument)
            {
                if (name.Contains("NQ"))
                {
                    GridUnit = 100.0;
                    StopLossPoints = 10.0;
                    ProfitTargetPoints = 20.0;
                    LevelToleranceTicks = 4;
                }
                else if (name.Contains("ES"))
                {
                    GridUnit = 25.0;
                    StopLossPoints = 2.50;
                    ProfitTargetPoints = 5.00;
                    LevelToleranceTicks = 2;
                }
                else if (name.Contains("YM"))
                {
                    GridUnit = 100.0;
                    StopLossPoints = 20.0;
                    ProfitTargetPoints = 40.0;
                    LevelToleranceTicks = 4;
                }
                else if (name.Contains("CL"))
                {
                    GridUnit = 1.0;
                    StopLossPoints = 0.20;
                    ProfitTargetPoints = 0.40;
                    LevelToleranceTicks = 2;
                }
                else if (name.Contains("RTY") || name.Contains("2K"))
                {
                    GridUnit = 10.0;
                    StopLossPoints = 3.0;
                    ProfitTargetPoints = 6.0;
                    LevelToleranceTicks = 3;
                }
            }

            // Calculate Order Quantity
            calculatedQuantity = Math.Max(1, DefaultQuantity);

            if (SizingMode == BanditsSizingMode.AutoMicroScale)
            {
                calculatedQuantity = isMicroInstrument ? Math.Max(1, DefaultQuantity * 10) : Math.Max(1, DefaultQuantity);
            }
            else if (SizingMode == BanditsSizingMode.TargetRiskDollars && TargetRiskDollars > 0)
            {
                double pointValue = GetPointValue();
                double dollarRiskPerContract = StopLossPoints * pointValue;
                if (dollarRiskPerContract > 0)
                {
                    calculatedQuantity = Math.Max(1, (int)Math.Floor(TargetRiskDollars / dollarRiskPerContract));
                }
            }

            Log(string.Format("[AUTO-CALIBRATION] Instrument: {0} | Micro: {1} | Grid: {2:F2} | SL: {3:F2} | TP: {4:F2} | Qty: {5} (Risk: ${6:F2})",
                name, isMicroInstrument, GridUnit, StopLossPoints, ProfitTargetPoints, calculatedQuantity, calculatedQuantity * StopLossPoints * GetPointValue()), LogLevel.Information);
        }

        protected override double GetCurrentATR()
        {
            return StopLossPoints;
        }

        protected override double GetPotentialLoss()
        {
            return StopLossPoints * GetPointValue() * Math.Max(1, calculatedQuantity);
        }

        // ──────────────────────────────────────────────────────────────
        // CORE SIGNAL & EXECUTION ENGINE
        // ──────────────────────────────────────────────────────────────

        protected override int CheckForSignal()
        {
            if (Position.MarketPosition != MarketPosition.Flat)
                return 0;

            if (CurrentBars[0] < 5)
                return 0;

            DateTime now = Times[0][0];
            int timeHHMM = now.Hour * 100 + now.Minute;

            // Reset day boundary
            if (now.Date != sessionDate)
            {
                sessionDate = now.Date;
                rthOpenCaptured = false;
                rthOpenPrice = 0;
                touchesOnCurrentLevelToday = 0;
                lastLevelTouched = 0;
            }

            // Capture true 09:30 AM ET RTH Open Price
            if (timeHHMM >= 930 && !rthOpenCaptured)
            {
                rthOpenPrice = Opens[0][0];
                rthOpenCaptured = true;
            }

            if (!IsAllowedTradingWindow(timeHHMM))
                return 0;

            if (CurrentBars[0] - lastEntryBar < 5)
                return 0;

            double close0 = Closes[0][0];
            double high0  = Highs[0][0];
            double low0   = Lows[0][0];
            double open0  = Opens[0][0];

            double baseHandle = Math.Floor(close0 / GridUnit) * GridUnit;
            double level20 = baseHandle + (0.20 * GridUnit);
            double level80 = baseHandle + (0.80 * GridUnit);
            double tol = LevelToleranceTicks * TickSize;

            int bias = 0;
            if (UseRthOpenBias && rthOpenPrice > 0)
            {
                bias = (close0 >= rthOpenPrice) ? 1 : -1;
            }

            // ──────────────────────────────────────────────────────────
            // SETUP 1: FORK REVERSAL
            // ──────────────────────────────────────────────────────────
            if (EnableForkReversal && CurrentBars[0] >= 2)
            {
                double r0 = high0 - low0;
                double b0 = Math.Abs(close0 - open0);
                double w0_lo = Math.Min(open0, close0) - low0;
                double w0_hi = high0 - Math.Max(open0, close0);

                double high1 = Highs[0][1];
                double low1  = Lows[0][1];
                double open1 = Opens[0][1];
                double close1= Closes[0][1];
                double r1 = high1 - low1;
                double b1 = Math.Abs(close1 - open1);
                double w1_lo = Math.Min(open1, close1) - low1;
                double w1_hi = high1 - Math.Max(open1, close1);

                // Bullish Fork at xx20
                if (r0 > 0 && r1 > 0 && (bias >= 0))
                {
                    bool isBullFork = (w0_lo >= 0.38 * r0) && (w1_lo >= 0.38 * r1) &&
                                      (b0 <= 0.52 * r0) && (b1 <= 0.52 * r1) &&
                                      (Math.Abs(low0 - low1) <= tol) && (close0 > open0) &&
                                      (Math.Abs(low0 - level20) <= StopLossPoints);

                    if (isBullFork)
                    {
                        ExecuteTrade("Long", level20, level20 - StopLossPoints, level20 + ProfitTargetPoints);
                        lastEntryBar = CurrentBars[0];
                        return 0;
                    }
                }

                // Bearish Fork at xx80
                if (r0 > 0 && r1 > 0 && (bias <= 0))
                {
                    bool isBearFork = (w0_hi >= 0.38 * r0) && (w1_hi >= 0.38 * r1) &&
                                      (b0 <= 0.52 * r0) && (b1 <= 0.52 * r1) &&
                                      (Math.Abs(high0 - high1) <= tol) && (close0 < open0) &&
                                      (Math.Abs(high0 - level80) <= StopLossPoints);

                    if (isBearFork)
                    {
                        ExecuteTrade("Short", level80, level80 + StopLossPoints, level80 - ProfitTargetPoints);
                        lastEntryBar = CurrentBars[0];
                        return 0;
                    }
                }
            }

            // ──────────────────────────────────────────────────────────
            // SETUP 2: 'h' PATTERN BEARISH CONTINUATION
            // ──────────────────────────────────────────────────────────
            if (EnableHPattern && bias <= 0 && close0 < open0 && CurrentBars[0] >= 5)
            {
                double recentLow = Lows[0][0];
                for (int b = 1; b <= 4; b++)
                {
                    if (Lows[0][b] < recentLow)
                        recentLow = Lows[0][b];
                }

                double archTop = Math.Max(Highs[0][1], Highs[0][2]);
                double barRange1 = Highs[0][1] - Lows[0][1];
                double archRejection = (barRange1 > 0) ? (archTop - Math.Max(Opens[0][1], Closes[0][1])) / barRange1 : 0;
                bool nearMagnet = (Math.Abs(archTop - level80) <= StopLossPoints) || (Math.Abs(archTop - level20) <= StopLossPoints);

                if (archRejection >= 0.30 && nearMagnet && close0 < Math.Min(Opens[0][1], Closes[0][1]))
                {
                    ExecuteTrade("Short", archTop, archTop + StopLossPoints, archTop - ProfitTargetPoints);
                    lastEntryBar = CurrentBars[0];
                    return 0;
                }
            }

            // ──────────────────────────────────────────────────────────
            // SETUP 3: DIRECT LEVEL SNIPING (Trend Aligned)
            // ──────────────────────────────────────────────────────────
            if (EnableLevelSniping)
            {
                // In Bullish Bias: Long Dip at xx20
                if (low0 <= level20 && close0 >= level20 && (bias >= 0))
                {
                    if (Math.Abs(level20 - lastLevelTouched) > tol)
                    {
                        lastLevelTouched = level20;
                        touchesOnCurrentLevelToday = 1;
                    }
                    else
                    {
                        touchesOnCurrentLevelToday++;
                    }

                    if (touchesOnCurrentLevelToday <= 2)
                    {
                        ExecuteTrade("Long", level20, level20 - StopLossPoints, level20 + ProfitTargetPoints);
                        lastEntryBar = CurrentBars[0];
                        return 0;
                    }
                }

                // In Bearish Bias: Short Rally at xx80
                if (high0 >= level80 && close0 <= level80 && (bias <= 0))
                {
                    if (Math.Abs(level80 - lastLevelTouched) > tol)
                    {
                        lastLevelTouched = level80;
                        touchesOnCurrentLevelToday = 1;
                    }
                    else
                    {
                        touchesOnCurrentLevelToday++;
                    }

                    if (touchesOnCurrentLevelToday <= 2)
                    {
                        ExecuteTrade("Short", level80, level80 + StopLossPoints, level80 - ProfitTargetPoints);
                        lastEntryBar = CurrentBars[0];
                        return 0;
                    }
                }
            }

            return 0;
        }

        private void ExecuteTrade(string direction, double entry, double stop, double target)
        {
            string signalName = direction == "Long" ? "Bandits8020_Long" : "Bandits8020_Short";
            int qty = Math.Max(1, calculatedQuantity);

            if (direction == "Long")
            {
                EnterLongLimit(qty, entry, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);
                SetProfitTarget(signalName, CalculationMode.Price, target);
            }
            else
            {
                EnterShortLimit(qty, entry, signalName);
                SetStopLoss(signalName, CalculationMode.Price, stop, false);
                SetProfitTarget(signalName, CalculationMode.Price, target);
            }

            Log(string.Format("[{0} LIMIT] {1:HH:mm:ss} | Qty: {2} | Entry: {3:F2} | Stop: {4:F2} | Target: {5:F2} | Total Risk: ${6:F2}",
                direction.ToUpper(), Times[0][0], qty, entry, stop, target, qty * Math.Abs(entry - stop) * GetPointValue()), LogLevel.Information);
        }

        private bool IsAllowedTradingWindow(int timeHHMM)
        {
            if (SkipDeadZone && (timeHHMM >= 2300 || timeHHMM < 130))
                return false;

            bool isRthMorning = (timeHHMM >= 930 && timeHHMM <= 1100);
            bool isRthClose   = (timeHHMM >= 1500 && timeHHMM <= 1530);

            if (isRthMorning || isRthClose)
                return true;

            if (TradeAsiaSession)
            {
                bool isAsiaOpen = (timeHHMM >= 1800 && timeHHMM <= 1900);
                bool isAsiaPeak = (timeHHMM >= 2000 && timeHHMM <= 2100);
                if (isAsiaOpen || isAsiaPeak)
                    return true;
            }

            return false;
        }
    }
}
