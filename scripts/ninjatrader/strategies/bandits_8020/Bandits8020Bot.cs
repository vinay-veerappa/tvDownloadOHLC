#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
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
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8). The three
    /// setups (fork reversal, 'h' pattern, level sniping) are declared as triggers
    /// and their criteria as gates; the verdict is computed by the sealed base.
    ///
    /// B6 SIZING DECISION (2026-09-05, user call): the old TargetRiskDollars /
    /// AutoMicroScale sizing engine is DELETED. $200 risk over a 10-pt MNQ stop
    /// computed 10 contracts per trade where the frozen document fixes
    /// MaxContractsPerTrade = 1 and every other bot trades 1; the bot also entered
    /// through its own ExecuteTrade, which bypassed RiskManagerBase.EnterTrade and
    /// never incremented todayTradeCount (the HUD counter was frozen). Entries now
    /// route through the base at 1 contract, entering on a LIMIT at the level via
    /// GetCustomLimitPrice — the same fill price the old path used.
    ///
    /// The HUD, sub-grid rays, setup markers and trade brackets are chart visuals
    /// and survive unchanged; the HUD's trade count now reads the live counter.
    /// </summary>
    public class Bandits8020Bot : GovernedStrategy
    {
        #region Parameters

        #region Instrument & Auto-Calibration
        [NinjaScriptProperty]
        [Display(Name = "Auto-Calibrate by Instrument", Order = 1, GroupName = "1. Instrument & Auto-Calibration",
                 Description = "Automatically configures grid handle, stop loss, and targets based on detected ticker (NQ/ES/CL/YM/RTY)")]
        public bool AutoCalibrateInstrument { get; set; } = true;
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

        #region Visuals & On-Chart UI
        [NinjaScriptProperty]
        [Display(Name = "Show Dashboard HUD", Order = 1, GroupName = "5. Visuals & Chart UI",
                 Description = "Displays sleek top-right Head-Up Display panel with live bias, grid levels, and PnL")]
        public bool ShowDashboardHUD { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Sub-Grid Rays", Order = 2, GroupName = "5. Visuals & Chart UI",
                 Description = "Plots dynamic horizontal rays for xx00, xx20, xx50, and xx80 nodes")]
        public bool ShowSubGridLines { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Setup Verification Markers", Order = 3, GroupName = "5. Visuals & Chart UI",
                 Description = "Draws arrows and text tags verifying the exact setup triggering the entry")]
        public bool ShowSignalMarkers { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Active Trade Brackets", Order = 4, GroupName = "5. Visuals & Chart UI",
                 Description = "Draws real-time Entry, Stop Loss, and Profit Target horizontal bracket lines")]
        public bool ShowTradeBrackets { get; set; } = true;
        #endregion

        #endregion

        #region Internal State

        private double rthOpenPrice;
        private bool rthOpenCaptured;
        private DateTime sessionDate;
        private int lastEntryBar;
        private double lastLevelTouched;
        private int touchesOnCurrentLevelToday;

        // The setup the trigger declared, and the price the entry should fill at.
        // GetCustomLimitPrice returns it after the base accepts the verdict.
        private double pendingEntryPrice;

        #endregion

        protected override string GetStrategyName()
        {
            return "Bandits8020";
        }

        protected override void OnStrategyDefaults()
        {
            Description                  = "Prop Firm Bandits 80/20 & Orderflow Sub-Grid Strategy with Bulletproof OCO Brackets";
            Name                         = "Bandits8020Bot";
            EntriesPerDirection          = 1;
            IsFillLimitOnTouch           = true;

            StopAtrMult       = 1.0;
            TradePolicy       = TradePolicyType.FixedTarget;
            TargetRMultiple   = 2.0;
            BreakevenTriggerR = 1.0;
            TrailAtrMult      = 1.0;

            StartingAccountBalance    = 50000;
            DailyMaxLoss              = 400;
            MaxConsecutiveLosers      = 2;
            PauseMinutes              = 45;
            HardStopConsecutiveLosers = 2;
            // B6: MaxTradesPerDay = 3 KEPT — no trade-ordinal measurement exists
            // (no registry key, no hunter; a research artifact per §1.2), so the
            // recorded number stands. Unlike the old 99s, 3 matches the base's
            // own registered-account default.
            MaxTradesPerDay           = 3;
            TrailingDrawdown          = 2000;
            StopOnAccountBlown        = false;

            EarliestEntry = 930;
            LatestEntry   = 1100;
            FlattenBy     = 1555;

            AddSecondaryTimeframe = false;
            DebugMode             = false;

            AutoCalibrateInstrument = true;

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

            ShowDashboardHUD   = true;
            ShowSubGridLines   = true;
            ShowSignalMarkers  = true;
            ShowTradeBrackets  = true;
        }

        protected override void OnInitialize()
        {
            lastEntryBar = -100;
            lastLevelTouched = 0;
            touchesOnCurrentLevelToday = 0;
            rthOpenPrice = 0;
            rthOpenCaptured = false;
            sessionDate = DateTime.MinValue;
            pendingEntryPrice = double.NaN;

            CalibrateInstrumentSettings();

            // Set bulletproof global tick-based OCO brackets
            int stopTicks = Math.Max(1, (int)Math.Round(StopLossPoints / TickSize));
            int targetTicks = Math.Max(1, (int)Math.Round(ProfitTargetPoints / TickSize));

            SetStopLoss(CalculationMode.Ticks, stopTicks);
            SetProfitTarget(CalculationMode.Ticks, targetTicks);
        }

        private void CalibrateInstrumentSettings()
        {
            if (Instrument == null || Instrument.MasterInstrument == null)
                return;

            string name = Instrument.MasterInstrument.Name.ToUpper();

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
                    StopLossPoints = 15.0;
                    ProfitTargetPoints = 30.0;
                    LevelToleranceTicks = 4;
                }
                else if (name.Contains("CL"))
                {
                    GridUnit = 1.0;
                    StopLossPoints = 0.10;
                    ProfitTargetPoints = 0.20;
                    LevelToleranceTicks = 2;
                }
                else if (name.Contains("RTY") || name.Contains("2K"))
                {
                    GridUnit = 10.0;
                    StopLossPoints = 1.0;
                    ProfitTargetPoints = 2.0;
                    LevelToleranceTicks = 3;
                }
                else if (name.Contains("GC"))
                {
                    GridUnit = 10.0;
                    StopLossPoints = 1.0;
                    ProfitTargetPoints = 2.0;
                    LevelToleranceTicks = 3;
                }
            }

            Log(string.Format("[AUTO-CALIBRATION] Instrument: {0} | Grid: {1:F2} | SL: {2:F2} | TP: {3:F2} | Qty: 1 (frozen MaxContractsPerTrade)",
                name, GridUnit, StopLossPoints, ProfitTargetPoints), LogLevel.Information);
        }

        protected override double GetCurrentATR()
        {
            return StopLossPoints;
        }

        protected override double GetPotentialLoss()
        {
            return StopLossPoints * GetPointValue();
        }

        // ──────────────────────────────────────────────────────────────
        // DECLARED CRITERIA — the sealed base computes the verdict
        // ──────────────────────────────────────────────────────────────

        protected override void OnEvaluate(SetupEvaluation e)
        {
            bool warmed = CurrentBars[0] >= 5;
            e.Gate("warmup", warmed, CurrentBars[0], 5);
            if (!warmed) return;

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

            double close0 = Closes[0][0];
            double high0  = Highs[0][0];
            double low0   = Lows[0][0];
            double open0  = Opens[0][0];

            double baseHandle = Math.Floor(close0 / GridUnit) * GridUnit;
            double level20 = baseHandle + (0.20 * GridUnit);
            double level50 = baseHandle + (0.50 * GridUnit);
            double level80 = baseHandle + (0.80 * GridUnit);
            double tol = LevelToleranceTicks * TickSize;

            int bias = 0;
            if (UseRthOpenBias && rthOpenPrice > 0)
            {
                bias = (close0 >= rthOpenPrice) ? 1 : -1;
            }

            // Render on-chart UI elements — side effects, not logic
            if (ShowSubGridLines)
                RenderSubGridLines(baseHandle, level20, level50, level80);

            if (ShowDashboardHUD)
                RenderDashboardHUD(bias, baseHandle, level20, level80);

            // No entries while a position is open (the original returned here too)
            if (Position.MarketPosition != MarketPosition.Flat)
                return;

            // Trading-window gate — declared with its value so an out-of-window
            // bar is attributable rather than silent
            bool windowOk = IsAllowedTradingWindow(timeHHMM);
            e.Gate("trading_window", windowOk, timeHHMM, 0);
            if (!windowOk) return;

            // Cooldown between entries
            int barsSinceEntry = CurrentBars[0] - lastEntryBar;
            bool cooldownOk = barsSinceEntry >= 5;
            e.Gate("entry_cooldown", cooldownOk, barsSinceEntry, 5);
            if (!cooldownOk) return;

            // ──────────────────────────────────────────────────────────
            // SETUP 1: FORK REVERSAL
            // ──────────────────────────────────────────────────────────
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
            if (EnableForkReversal && CurrentBars[0] >= 2 && r0 > 0 && r1 > 0 && (bias >= 0))
            {
                bool isBullFork = (w0_lo >= 0.38 * r0) && (w1_lo >= 0.38 * r1) &&
                                  (b0 <= 0.52 * r0) && (b1 <= 0.52 * r1) &&
                                  (Math.Abs(low0 - low1) <= tol) && (close0 > open0) &&
                                  (Math.Abs(low0 - level20) <= StopLossPoints);

                if (isBullFork)
                {
                    e.Trigger("long");
                    e.Measure("fork_lower_wick_ratio", w0_lo / r0);
                    pendingEntryPrice = level20;
                    lastEntryBar = CurrentBars[0];
                    return;
                }
            }

            // Bearish Fork at xx80
            if (EnableForkReversal && CurrentBars[0] >= 2 && r0 > 0 && r1 > 0 && (bias <= 0))
            {
                bool isBearFork = (w0_hi >= 0.38 * r0) && (w1_hi >= 0.38 * r1) &&
                                  (b0 <= 0.52 * r0) && (b1 <= 0.52 * r1) &&
                                  (Math.Abs(high0 - high1) <= tol) && (close0 < open0) &&
                                  (Math.Abs(high0 - level80) <= StopLossPoints);

                if (isBearFork)
                {
                    e.Trigger("short");
                    e.Measure("fork_upper_wick_ratio", w0_hi / r0);
                    pendingEntryPrice = level80;
                    lastEntryBar = CurrentBars[0];
                    return;
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
                    e.Trigger("short");
                    e.Measure("arch_rejection_ratio", archRejection);
                    pendingEntryPrice = archTop;
                    lastEntryBar = CurrentBars[0];
                    return;
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
                        e.Trigger("long");
                        e.Measure("touches_on_level", touchesOnCurrentLevelToday);
                        pendingEntryPrice = level20;
                        lastEntryBar = CurrentBars[0];
                        return;
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
                        e.Trigger("short");
                        e.Measure("touches_on_level", touchesOnCurrentLevelToday);
                        pendingEntryPrice = level80;
                        lastEntryBar = CurrentBars[0];
                        return;
                    }
                }
            }
        }

        /// <summary>
        /// The entry fills at the level the trigger declared — the same limit
        /// price the old ExecuteTrade submitted. Returns NaN (market at close)
        /// when no trigger is pending, matching the base's fallback.
        /// </summary>
        protected override double GetCustomLimitPrice(int signal, double currentPrice)
        {
            if (!double.IsNaN(pendingEntryPrice))
            {
                double p = pendingEntryPrice;
                pendingEntryPrice = double.NaN;   // consumed by this one entry
                return p;
            }
            return double.NaN;
        }

        // ──────────────────────────────────────────────────────────────
        // ON-CHART UI & VISUALIZATION ENGINE
        // ──────────────────────────────────────────────────────────────

        private void RenderDashboardHUD(int bias, double baseHandle, double level20, double level80)
        {
            string biasStr = bias > 0 ? "BULLISH ▲ (Price >= RTH Open)" : (bias < 0 ? "BEARISH ▼ (Price < RTH Open)" : "NEUTRAL ◄►");
            string instName = Instrument != null ? Instrument.MasterInstrument.Name : "FUTURES";
            double dollarRisk = StopLossPoints * GetPointValue();
            double pnl = SystemPerformance.AllTrades.TradesPerformance.NetProfit;

            string hud = string.Format(
                "╔══════════════════════════════════════════════════╗\n" +
                "║ 🏛️  BANDITS 80/20 SUB-GRID ENGINE                ║\n" +
                "╠══════════════════════════════════════════════════╣\n" +
                "║ Instrument : {0,-8} | Qty: 1 cnts (${1:F0} Risk)     ║\n" +
                "║ Dealing Bias: {2,-33}║\n" +
                "║ 09:30 Open  : {3,-10:F2} | Current: {4,-10:F2}      ║\n" +
                "║ Active Grid : 20: {5:F2} ◄► 80: {6:F2}       ║\n" +
                "║ Session PnL : ${7,-9:F2} | Today Trades: {8}/{9}      ║\n" +
                "╚══════════════════════════════════════════════════╝",
                instName, dollarRisk,
                biasStr,
                rthOpenPrice, Closes[0][0],
                level20, level80,
                pnl, todayTradeCount, MaxTradesPerDay
            );

            Draw.TextFixed(this, "BanditsHUD", hud, TextPosition.TopRight,
                Brushes.White, new SimpleFont("Consolas", 10),
                Brushes.Transparent, new SolidColorBrush(Color.FromArgb(220, 15, 23, 42)), 1);
        }

        private void RenderSubGridLines(double baseHandle, double level20, double level50, double level80)
        {
            Draw.Ray(this, "Handle_00", false, 10, baseHandle, 0, baseHandle, Brushes.DarkGoldenrod, DashStyleHelper.Solid, 1);
            Draw.Ray(this, "SubGrid_20", false, 10, level20, 0, level20, Brushes.DodgerBlue, DashStyleHelper.Solid, 2);
            Draw.Ray(this, "MidPoint_50", false, 10, level50, 0, level50, Brushes.SlateGray, DashStyleHelper.Dash, 1);
            Draw.Ray(this, "SubGrid_80", false, 10, level80, 0, level80, Brushes.Crimson, DashStyleHelper.Solid, 2);
            Draw.Ray(this, "Handle_100", false, 10, baseHandle + GridUnit, 0, baseHandle + GridUnit, Brushes.DarkGoldenrod, DashStyleHelper.Solid, 1);
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