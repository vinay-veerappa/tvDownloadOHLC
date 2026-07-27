using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// Represents a calendar skip rule for filtering trading days.
    /// (class, not record — NT8's Roslyn compiler does not support C# 9 record syntax)
    /// </summary>
    public class CalendarSkipRule
    {
        public Func<DateTime, bool> ShouldSkip { get; }
        public string Name { get; }
        public CalendarSkipRule(Func<DateTime, bool> shouldSkip, string name)
        {
            ShouldSkip = shouldSkip;
            Name = name;
        }
    }

    /// <summary>
    /// Generic abstract base class for time-bounded intraday strategies.
    /// Extends RiskManagerBase to provide range-based entry logic, filters, and risk geometry.
    /// Implements ADR-001 (ET Conversion + UTC persistence) and ADR-002 (MAE/MFE % logging).
    /// </summary>
    public abstract class IntradayStrategyBase : RiskManagerBase
    {
        #region Parameters

        [NinjaScriptProperty]
        [Display(Name = "Range Start Hour", Order = 1, GroupName = "Time Window")]
        public int RangeStartHour { get; set; } = 9;

        [NinjaScriptProperty]
        [Display(Name = "Range Start Minute", Order = 2, GroupName = "Time Window")]
        public int RangeStartMinute { get; set; } = 30;

        [NinjaScriptProperty]
        [Display(Name = "Range Duration Min", Order = 3, GroupName = "Time Window")]
        public int RangeDurationMin { get; set; } = 30;

        [NinjaScriptProperty]
        [Display(Name = "Session End Hour", Order = 4, GroupName = "Time Window")]
        public int SessionEndHour { get; set; } = 16;

        [NinjaScriptProperty]
        [Display(Name = "Session End Minute", Order = 5, GroupName = "Time Window")]
        public int SessionEndMinute { get; set; } = 0;

        [NinjaScriptProperty]
        [Display(Name = "Flatten By Hour", Order = 6, GroupName = "Time Window")]
        public int FlattenByHour { get; set; } = 15;

        [NinjaScriptProperty]
        [Display(Name = "Flatten By Minute", Order = 7, GroupName = "Time Window")]
        public int FlattenByMinute { get; set; } = 50;

        [NinjaScriptProperty]
        [Display(Name = "Slippage Ticks", Order = 1, GroupName = "Execution")]
        public int SlippageTicks { get; set; } = 1;

        [NinjaScriptProperty]
        [Display(Name = "Close Position Top %", Order = 2, GroupName = "Execution")]
        public double ClosePositionTopPct { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Close Position Bot %", Order = 3, GroupName = "Execution")]
        public double ClosePositionBotPct { get; set; } = 0.25;

        [NinjaScriptProperty]
        [Display(Name = "Require Direction Bias", Order = 1, GroupName = "Filters")]
        public bool RequireDirectionBias { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Target Level (R)", Order = 2, GroupName = "Risk Geometry")]
        public double TargetLvl { get; set; } = 0.25;

        [NinjaScriptProperty]
        [Display(Name = "Stop R Mult", Order = 3, GroupName = "Risk Geometry")]
        public double StopRMult { get; set; } = 0.25; // MAE Calibrated: P80 Winner 0.232R / P50 Loser 0.405R (IB 96% rule)

        [NinjaScriptProperty]
        [Display(Name = "Early Break Threshold Min", Order = 1, GroupName = "Sizing")]
        public int EarlyBreakThresholdMin { get; set; } = 90;

        [NinjaScriptProperty]
        [Display(Name = "Early Break Size Mult", Order = 2, GroupName = "Sizing")]
        public double EarlyBreakSizeMult { get; set; } = 0.5;

        [NinjaScriptProperty]
        [Display(Name = "Late Break Size Mult", Order = 3, GroupName = "Sizing")]
        public double LateBreakSizeMult { get; set; } = 1.0;

        [NinjaScriptProperty]
        [Display(Name = "Skip Huge Range", Order = 1, GroupName = "Range Filter")]
        public bool SkipHugeRange { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Max Range %", Order = 2, GroupName = "Range Filter")]
        public double MaxRangePct { get; set; } = 0.90;

        [NinjaScriptProperty]
        [Display(Name = "Min Range %", Order = 3, GroupName = "Range Filter")]
        public double MinRangePct { get; set; } = 0.10;

        [NinjaScriptProperty]
        [Display(Name = "News Moratorium Enabled", Order = 1, GroupName = "Moratorium")]
        public bool NewsMoratoriumEnabled { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Vix Regime Filter Enabled", Order = 2, GroupName = "Moratorium")]
        public bool VixRegimeFilterEnabled { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Correlation Filter Enabled", Order = 3, GroupName = "Moratorium")]
        public bool CorrelationFilterEnabled { get; set; } = false;

        #endregion

        #region State Fields

        protected double rangeHigh;
        protected double rangeLow;
        protected double rangeOpen;
        protected double rangeClose;
        protected double rangeRange;
        protected double rangeMid;
        protected double rangeClosePosition; // 0 to 1
        protected int biasFirstreach; // +1, -1, 0
        protected bool rangeComplete;
        protected bool rangeStarted;
        protected DateTime rangeCompleteTime;
        protected DateTime firstHighTouch;
        protected DateTime firstLowTouch;
        protected int predictedDir;
        protected double priorSessionClose; // previous day/session close for range-size filter
        private readonly List<CalendarSkipRule> _calendarRules = new List<CalendarSkipRule>();

        #endregion

        /// <summary>
        /// Called on session start. Resets range state and calls subclass hook.
        /// NOTE: RiskManagerBase.OnNewSession is private, so we cannot override it.
        /// Instead we hook into SetStrategyDefaults/InitializeStrategy lifecycle +
        /// detect the session change in CheckForSignal via date comparison.
        /// </summary>
        private DateTime _lastSessionDate = DateTime.MinValue;
        private void CheckSessionReset(DateTime now)
        {
            DateTime barDate = now.Date;
            if (barDate != _lastSessionDate)
            {
                _lastSessionDate = barDate;
                // Capture prior session close before resetting
                if (BarsArray[0] != null && BarsArray[0].Count > 1)
                    priorSessionClose = BarsArray[0].GetClose(BarsArray[0].Count - 2);
                ResetRangeState();
                OnSessionOpenReset();
            }
        }

        /// <summary>
        /// Resets all range-related state fields to defaults.
        /// </summary>
        protected virtual void ResetRangeState()
        {
            rangeComplete = false;
            rangeStarted = false;
            rangeHigh = rangeLow = rangeOpen = rangeClose = rangeRange = rangeMid = 0;
            rangeClosePosition = 0;
            biasFirstreach = 0;
            predictedDir = 0;
            rangeCompleteTime = DateTime.MinValue;
            firstHighTouch = DateTime.MinValue;
            firstLowTouch = DateTime.MinValue;
        }

        /// <summary>
        /// Hook for subclass-specific session open resets (overshoot state, etc.).
        /// </summary>
        protected virtual void OnSessionOpenReset() { }

        /// <summary>
        /// Core signal logic. Builds range, applies filters, and requests entry.
        /// Implements the abstract hook from RiskManagerBase.
        /// </summary>
        /// <returns>1 (Long), -1 (Short), or 0 (Flat).</returns>
        protected override int CheckForSignal()
        {
            try
            {
            // DIAG: log every 60 bars to confirm CheckForSignal is called
            if (CurrentBar % 60 == 0) Print($"[DIAG] CheckForSignal bar={CurrentBar} time={Time[0]:HH:mm} BIP={BarsInProgress} rangeComplete={rangeComplete}");

            // Use Time[0] directly — NT8 is set to ET per user.
            DateTime now = Time[0];
            CheckSessionReset(now);  // detect session boundary + reset state

            DateTime rangeStart = new DateTime(now.Year, now.Month, now.Day, RangeStartHour, RangeStartMinute, 0);
            DateTime rangeEnd = rangeStart.AddMinutes(RangeDurationMin);

            if (!rangeComplete)
            {
                if (now >= rangeStart && now < rangeEnd)
                {
                    BuildRangeWindow();
                }
                else if (now >= rangeEnd)
                {
                    FinalizeRange();
                    Print($"[DIAG] IB finalized: high={rangeHigh} low={rangeLow} range={rangeRange} closePos={rangeClosePosition} bias={biasFirstreach} predicted={predictedDir}");
                }
                return 0;
            }

            if (CalendarFilter(now)) { Print($"[DIAG] skipped by calendar filter at {now:HH:mm}"); return 0; }
            if (RangeSizeFilter()) { Print($"[DIAG] skipped by range-size filter at {now:HH:mm} rangePct={rangeRange/priorSessionClose*100}"); return 0; }

            if (rangeRange < TickSize)
            {
                Print($"[DIAG] Range too small ({rangeRange}) to trade.");
                return 0;
            }

            if (NewsMoratoriumEnabled && IsNewsMoratorium()) return 0;
            if (VixRegimeFilterEnabled && IsVixHostile()) return 0;
            if (CorrelationFilterEnabled && IsCorrelationDiverging()) return 0;

            int signal = CheckForEntry();
            if (signal != 0) Print($"[DIAG] CheckForEntry returned signal={signal} at {now:HH:mm} close={Close[0]} rangeHigh={rangeHigh} rangeLow={rangeLow}");
            // CRITICAL: return 0 so RiskManagerBase.OnBarUpdate does NOT call EnterTrade()
            // with ATR stops — our CheckForEntry already entered via EnterWithRangeStop().
            // Returning the signal would cause a double-entry attempt with wrong stops.
            return 0;  // we handle entry inside CheckForEntry; suppress base's EnterTrade
            }
            catch (Exception ex)
            {
                // Log once, then suppress — don't crash the backtest
                if (CurrentBar % 100 == 0) Print($"[DIAG] CheckForSignal exception at bar {CurrentBar}: {ex.Message}");
                return 0;
            }
        }

        /// <summary>
        /// Finalizes range calculations and computes bias.
        /// </summary>
        protected virtual void FinalizeRange()
        {
            rangeComplete = true;
            rangeCompleteTime = Time[0];  // NT8 is set to ET — no conversion needed
            rangeMid = (rangeHigh + rangeLow) / 2.0;
            rangeRange = rangeHigh - rangeLow;
            ComputeBias();
            Print($"[DIAG] FinalizeRange: high={rangeHigh} low={rangeLow} range={rangeRange} mid={rangeMid} closePos={rangeClosePosition} bias={biasFirstreach} predicted={predictedDir} time={Time[0]:HH:mm}");
        }

        /// <summary>
        /// ATR override — range-based strategies use the IB/range range as their risk
        /// metric, NOT ATR. RiskManagerBase.CanEnterTrade() gates on GetCurrentATR() > 0.
        /// By overriding to return rangeRange once the range completes, the gate passes
        /// immediately at range completion (10:00 for IB) without waiting for a 5-min ATR
        /// to warm up. Before rangeComplete, returns 0 so the gate blocks pre-range entries
        /// (the time fence EarliestEntry also guards this).
        /// This works for ALL range-bounded intraday strategies (IB, ORB, Asia session).
        /// </summary>
        protected override double GetCurrentATR()
        {
            if (rangeComplete && rangeRange > 0)
                return rangeRange;
            return 0;
        }

        /// <summary>
        /// Checks registered calendar rules.
        /// </summary>
        /// <returns>True if any rule indicates a skip.</returns>
        protected bool CalendarFilter(DateTime now)
        {
            return _calendarRules.Any(rule => rule.ShouldSkip(now));
        }

        /// <summary>
        /// Registers a new calendar skip rule.
        /// </summary>
        public void RegisterCalendarRule(Func<DateTime, bool> shouldSkip, string name)
        {
            _calendarRules.Add(new CalendarSkipRule(shouldSkip, name));
        }

        /// <summary>
        /// Filters based on range size relative to prior session close (ADR-002: percentage, not points).
        /// Uses priorSessionClose captured at OnNewSession, not the previous intraday bar.
        /// </summary>
        /// <returns>True if range should be skipped.</returns>
        protected bool RangeSizeFilter()
        {
            if (!SkipHugeRange) return false;
            if (priorSessionClose <= 0) return false;
            double rangePct = (rangeRange / priorSessionClose) * 100.0;
            return (rangePct > MaxRangePct * 100.0 || rangePct < MinRangePct * 100.0);
        }

        /// <summary>
        /// Returns size multiplier based on break time.
        /// </summary>
        protected double ClockSizeMultiplier(int breakMinutes)
        {
            return breakMinutes <= EarlyBreakThresholdMin ? EarlyBreakSizeMult : LateBreakSizeMult;
        }

        /// <summary>
        /// Validates target price sanity relative to entry and direction.
        /// </summary>
        protected bool TargetIsSane(double entry, double target, int dir)
        {
            if (dir == 1) return target > entry + TickSize;
            if (dir == -1) return target < entry - TickSize;
            return false;
        }

        /// <summary>
        /// Hook for news moratorium check. Default false.
        /// </summary>
        protected virtual bool IsNewsMoratorium() => false;

        /// <summary>
        /// Hook for VIX regime check. Default false.
        /// </summary>
        protected virtual bool IsVixHostile() => false;

        /// <summary>
        /// Hook for correlation divergence check. Default false.
        /// </summary>
        protected virtual bool IsCorrelationDiverging() => false;

        /// <summary>
        /// Enters trade with range-calibrated stop and target (bypasses base ATR sizing).
        /// Same-bar tie-break favors target first (Q1 resolution: SetProfitTarget BEFORE SetStopLoss).
        /// Stop is MAE-calibrated at 0.25R — between P80 winner (0.232R) and P50 loser (0.405R) per IB 96% rule.
        /// </summary>
        protected void EnterWithRangeStop(int dir, double entry, double stopPrice, double targetPrice, int qty)
        {
            if (!TargetIsSane(entry, targetPrice, dir))
            {
                Print("Invalid target price rejected.");
                return;
            }

            if (dir == 1)
            {
                EnterLong(qty, "IntradayBaseLong");
                // Target-first tie-break (Q1): SetProfitTarget before SetStopLoss
                SetProfitTarget(CalculationMode.Price, targetPrice);
                SetStopLoss(CalculationMode.Price, stopPrice);
            }
            else if (dir == -1)
            {
                EnterShort(qty, "IntradayBaseShort");
                // Target-first tie-break (Q1): SetProfitTarget before SetStopLoss
                SetProfitTarget(CalculationMode.Price, targetPrice);
                SetStopLoss(CalculationMode.Price, stopPrice);
            }
        }

        /// <summary>
        /// Handles order updates, reanchoring stops on partial fills and clearing on rejection.
        /// </summary>
        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string nativeError)
        {
            base.OnOrderUpdate(order, limitPrice, stopPrice, quantity, filled, averageFillPrice, orderState, time, error, nativeError);

            if (orderState == OrderState.Rejected)
            {
                tradeIsActive = false;
                Print($"Order Rejected: {nativeError}");
            }
            else if (filled < quantity && filled > 0)
            {
                ReanchorProtectiveOrders(filled);
            }
        }

        /// <summary>
        /// Hook to reanchor stops on partial fills.
        /// </summary>
        protected virtual void ReanchorProtectiveOrders(int filledQty) { }

        // NOTE: OnConnectionStatusUpdate removed — NT8's ConnectionStatus / ConnectionEventArgs
        // signatures vary by NT8 version and the base Strategy class doesn't expose a clean
        // override. Reconnect reconciliation will be handled by the RiskGuard AddOn instead,
        // which is the architectural owner of account-state recovery.

        /// <summary>
        /// Converts the supplied DateTime to Eastern Time (America/New_York) per ADR-001.
        /// NinjaTrader Time[0] is exchange-local; for CME futures this is Central Time.
        /// Handles UTC, Local, and Unspecified DateTime kinds safely.
        /// </summary>
        protected DateTime ToET(DateTime time)
        {
            TimeZoneInfo easternZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");

            if (time.Kind == DateTimeKind.Utc)
                return TimeZoneInfo.ConvertTimeFromUtc(time, easternZone);

            // Treat Unspecified/Local as exchange-local (CT for CME US futures).
            TimeZoneInfo centralZone = TimeZoneInfo.FindSystemTimeZoneById("America/Chicago");
            DateTime asCentral = time.Kind == DateTimeKind.Local
                ? TimeZoneInfo.ConvertTime(time, TimeZoneInfo.Local, centralZone)
                : DateTime.SpecifyKind(time, DateTimeKind.Unspecified);
            return TimeZoneInfo.ConvertTime(asCentral, centralZone, easternZone);
        }

        /// <summary>
        /// Converts an ET-anchored timestamp to UTC for persistence (ADR-001 storage mandate).
        /// Call this before writing rangeCompleteTime / firstHighTouch / firstLowTouch to disk.
        /// </summary>
        protected DateTime ToUTC(DateTime etTime)
        {
            TimeZoneInfo easternZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
            DateTime unspecified = etTime.Kind == DateTimeKind.Unspecified
                ? etTime
                : DateTime.SpecifyKind(etTime, DateTimeKind.Unspecified);
            return TimeZoneInfo.ConvertTimeToUtc(unspecified, easternZone);
        }

        /// <summary>
        /// Logs MAE/MFE as price percentage of rangeMid per ADR-002 (never raw points).
        /// Subclasses should call this from their trade-tracking logic.
        /// </summary>
        protected void LogMaeMfePercent(double mae, double mfe)
        {
            if (rangeMid > 0)
            {
                double maePct = (mae / rangeMid) * 100.0;
                double mfePct = (mfe / rangeMid) * 100.0;
                Print($"ADR-002 MAE/MFE (% of rangeMid): MAE={maePct:F3}% MFE={mfePct:F3}%");
            }
        }

        /// <summary>
        /// Builds the range window during the active range period.
        /// </summary>
        protected abstract void BuildRangeWindow();

        /// <summary>
        /// Computes directional bias after range close.
        /// </summary>
        protected abstract void ComputeBias();

        /// <summary>
        /// Determines entry signal based on range and bias.
        /// </summary>
        /// <returns>1 (Long), -1 (Short), or 0 (Flat).</returns>
        protected abstract int CheckForEntry();
    }
}
