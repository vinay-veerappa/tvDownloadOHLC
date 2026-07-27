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
    /// IBStrategyBase — IB-specific subclass of IntradayStrategyBase.
    /// Implements the 09:30-10:30 IB window builder, the Rule 1 direction trigger,
    /// and registers the 4 validated IB calendar filters.
    /// Play 3 overshoot state is declared here (shared by IBFadeBot).
    /// CheckForEntry() stays abstract — implemented by IBBreakoutBot / IBRetestBot / IBFadeBot.
    ///
    /// Key decisions (from AUTOMATION_DESIGN.md §0.3):
    ///   - Default IB duration = 30 min (Phase F: stronger Rule 1, 29% less dollar risk)
    ///   - Default stop = 0.25R MAE-calibrated (Phase D)
    ///   - Rule 3 clock filter INVERTED on NQ1/ES1 (late breaks hold 92.8%)
    ///   - Calendar: skip Mon(P2), Feb(P2), May(P1), Oct(P3)
    /// </summary>
    public abstract class IBStrategyBase : IntradayStrategyBase
    {
        #region IB-Specific Parameters

        /// <summary>
        /// Which IB play to execute (1=breakout, 2=retest, 3=fade).
        /// IB-specific — lives here, NOT in the generic IntradayStrategyBase.
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Active Play (1=BO, 2=Retest, 3=Fade)", Order = 1, GroupName = "IB Play")]
        public int ActivePlay { get; set; } = 3;  // Phase D: Play 3 is strongest

        // ── IB-specific calendar filters (registered with the base via RegisterCalendarRule) ──
        [NinjaScriptProperty]
        [Display(Name = "Skip Monday (Play 2)", Order = 2, GroupName = "IB Calendar")]
        public bool SkipMondayPlay2 { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Skip February (Play 2)", Order = 3, GroupName = "IB Calendar")]
        public bool SkipFebruaryPlay2 { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Skip May (Play 1)", Order = 4, GroupName = "IB Calendar")]
        public bool SkipMayPlay1 { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Skip October (Play 3)", Order = 5, GroupName = "IB Calendar")]
        public bool SkipOctoberPlay3 { get; set; } = true;

        #endregion

        #region IB-Specific State (Play 3 overshoot state machine)

        /// <summary>Set when price overshoots above IB high by 0.25× range. Reset on entry/session-open.</summary>
        protected bool overshootAbove;

        /// <summary>Set when price overshoots below IB low by 0.25× range. Reset on entry/session-open.</summary>
        protected bool overshootBelow;

        /// <summary>Direction of the first IB break (+1 up, -1 down, 0 none yet). Used by Play 2 retest.</summary>
        protected int firstBreakDir;

        /// <summary>Time of the first break — for clock-size multiplier.</summary>
        protected DateTime firstBreakTime;

        #endregion

        #region Lifecycle

        /// <summary>
        /// Called by the base during InitializeStrategy (from RiskManagerBase.OnStateChange DataLoaded).
        /// Register IB's 4 play-specific calendar rules with the generic base.
        /// </summary>
        protected override void InitializeStrategy()
        {
            // Register IB's 4 calendar rules — the generic base owns the filter mechanism
            RegisterCalendarRule(d => ActivePlay == 2 && SkipMondayPlay2   && d.DayOfWeek == DayOfWeek.Monday, "skip_mon_p2");
            RegisterCalendarRule(d => ActivePlay == 2 && SkipFebruaryPlay2 && d.Month == 2,                    "skip_feb_p2");
            RegisterCalendarRule(d => ActivePlay == 1 && SkipMayPlay1      && d.Month == 5,                    "skip_may_p1");
            RegisterCalendarRule(d => ActivePlay == 3 && SkipOctoberPlay3  && d.Month == 10,                   "skip_oct_p3");
        }

        /// <summary>
        /// IB defaults — override the generic base defaults for the validated IB configuration.
        /// </summary>
        protected override void SetStrategyDefaults()
        {
            // IB window: 09:30 ET, 30 min duration (Phase F: 30 is optimal)
            RangeStartHour = 9;
            RangeStartMinute = 30;
            RangeDurationMin = 30;

            // Phase D defaults: Play 3, 0.25x target, 0.25R stop
            ActivePlay = 3;
            TargetLvl = 0.25;
            StopRMult = 0.25;

            // Risk manager defaults (inherited from RiskManagerBase but tuned for Micro)
            StartingAccountBalance = 50000;
            DailyMaxLoss = 300;
            MaxTradesPerDay = 2;
            TrailingDrawdown = 2000;
            FlattenBy = 1550;  // ADR-020: flatten by 15:50 ET

            // Time fences
            EarliestEntry = 930;
            LatestEntry = 1430;

            // Range-based strategy — do NOT add the 5-min secondary series.
            // IB strategies use rangeRange as the risk metric (via IntradayStrategyBase.GetCurrentATR override),
            // not ATR from a 5-min secondary. Skipping AddDataSeries(Minute,5) eliminates the 250-min warmup
            // that was blocking all entries before ~13:20. RiskManagerBase gates on CurrentBars[1] only when
            // AddSecondaryTimeframe=true, so with false we only need CurrentBars[0] >= BarsRequiredToTrade.
            AddSecondaryTimeframe = false;

            // Lower BarsRequiredToTrade — base requires 50 on BOTH series (primary + 5-min secondary).
            // With 50 on the 5-min, that's 250 min before CanEnterTrade passes. Set to 1 so
            // only 1 bar of 5-min secondary is needed (5 min warmup).
            BarsRequiredToTrade = 1;
        }

        /// <summary>
        /// Override ConfigureStrategy — base already adds a 5-min secondary in OnStateChange.
        /// We can't prevent that. But with BarsRequiredToTrade=1 and AtrPeriod=1, only 1 bar
        /// of the 5-min secondary is needed before CanEnterTrade passes (5 min warmup).
        /// </summary>
        protected override void ConfigureStrategy()
        {
            // Base already added 5-min secondary. Nothing extra needed here.
        }

        /// <summary>
        /// IB-specific session-open reset — clears Play 3 overshoot + Play 2 break direction.
        /// Called by the base's CheckSessionReset().
        /// </summary>
        protected override void OnSessionOpenReset()
        {
            overshootAbove = false;
            overshootBelow = false;
            firstBreakDir = 0;
            firstBreakTime = DateTime.MinValue;
        }

        #endregion

        #region Abstract Method Implementations

        /// <summary>
        /// IB Window Builder (spec §3.1) — builds the 09:30-10:30 IB high/low/open/close.
        /// Uses DateTime arithmetic from the base (avoids the int*100+min rollover bug).
        /// Finalizes on the first bar AT OR AFTER the range end (handles missing 10:30 bar).
        /// </summary>
        protected override void BuildRangeWindow()
        {
            DateTime now = Time[0];
            DateTime rStart = new DateTime(now.Year, now.Month, now.Day, RangeStartHour, RangeStartMinute, 0);
            DateTime rEnd = rStart.AddMinutes(RangeDurationMin);

            // Finalize on the first bar AT OR AFTER range end — handles the edge case
            // where the exact 10:30 bar is dropped by the live feed.
            if (!rangeComplete && now >= rEnd)
            {
                FinalizeRange();
                return;
            }

            // Not yet in the IB window
            if (now < rStart || now >= rEnd) return;

            // Build the IB window
            if (!rangeStarted)
            {
                rangeHigh = High[0];
                rangeLow = Low[0];
                rangeOpen = Open[0];
                firstHighTouch = now;
                firstLowTouch = now;
                rangeStarted = true;
            }
            else
            {
                if (High[0] > rangeHigh) { rangeHigh = High[0]; firstHighTouch = now; }
                if (Low[0] < rangeLow)   { rangeLow = Low[0];   firstLowTouch = now; }
            }
            rangeClose = Close[0];
        }

        /// <summary>
        /// Rule 1 Direction Trigger (spec §3.2) — predicts which IB boundary breaks first.
        /// Low formed first + close in top 25% → long bias (88.1% hit rate, N=387).
        /// High formed first + close in bottom 25% → short bias (86.3% hit rate, N=322).
        /// </summary>
        protected override void ComputeBias()
        {
            // Which extreme was touched first?
            biasFirstreach = firstLowTouch < firstHighTouch ? 1   // low first
                          : firstHighTouch < firstLowTouch ? -1  // high first
                          : 0;                                     // tie

            if (!RequireDirectionBias)
            {
                predictedDir = 0;  // trade both directions
                return;
            }

            if (biasFirstreach == 1 && rangeClosePosition >= ClosePositionTopPct)
                predictedDir = 1;   // long bias
            else if (biasFirstreach == -1 && rangeClosePosition <= ClosePositionBotPct)
                predictedDir = -1;  // short bias
            else
                predictedDir = 0;   // no directional edge
        }

        // CheckForEntry() stays abstract — implemented by IBBreakoutBot / IBRetestBot / IBFadeBot

        #endregion

        #region IB Helpers (shared by play bots)

        /// <summary>
        /// Minutes since the IB completed — used for clock-size multiplier.
        /// </summary>
        protected int MinutesSinceIBComplete
        {
            get
            {
                if (!rangeComplete || rangeCompleteTime == DateTime.MinValue) return 0;
                return (int)(Time[0] - rangeCompleteTime).TotalMinutes;
            }
        }

        /// <summary>
        /// Tracks the first break direction (used by Play 2 retest).
        /// Call this from CheckForEntry() before checking for retest entries.
        /// </summary>
        protected void TrackFirstBreak()
        {
            if (firstBreakDir == 0)
            {
                if (Close[0] > rangeHigh) { firstBreakDir = 1; firstBreakTime = Time[0]; }
                else if (Close[0] < rangeLow) { firstBreakDir = -1; firstBreakTime = Time[0]; }
            }
        }

        /// <summary>
        /// Detects 0.25× overshoot for Play 3 fade entry.
        /// Sets overshootAbove/Below flags — the fade bot checks for close-back-inside.
        /// </summary>
        protected void DetectOvershoot()
        {
            if (High[0] > rangeHigh + 0.25 * rangeRange) overshootAbove = true;
            if (Low[0] < rangeLow - 0.25 * rangeRange) overshootBelow = true;
        }

        #endregion
    }
}