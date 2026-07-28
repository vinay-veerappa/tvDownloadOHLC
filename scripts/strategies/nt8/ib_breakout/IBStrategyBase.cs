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

        // ── Per-play confluence filter toggles (for ablation testing) ──
        // Defaults: only filters that work from session 1 are enabled.
        // VCP and OPEX filters need warmup/calendar alignment — enable for longer backtests.
        [NinjaScriptProperty]
        [Display(Name = "P1: Trend Misaligned", Order = 6, GroupName = "IB Confluence Filters")]
        public bool Play1TrendMisalignedFilter { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "P1: VCP 3-Day", Order = 7, GroupName = "IB Confluence Filters")]
        public bool Play1VcpFilter { get; set; } = false;  // over-restrictive in NT8 (kills trades); enable for ablation only

        [NinjaScriptProperty]
        [Display(Name = "P1: OPEX Week", Order = 8, GroupName = "IB Confluence Filters")]
        public bool Play1OpexWeekFilter { get; set; } = false;  // over-restrictive in NT8; enable for ablation only

        [NinjaScriptProperty]
        [Display(Name = "P1: Low Body Close", Order = 9, GroupName = "IB Confluence Filters")]
        public bool Play1LowBodyCloseFilter { get; set; } = false;  // over-restrictive in NT8; enable for ablation only

        [NinjaScriptProperty]
        [Display(Name = "P3: VCP 3-Day", Order = 10, GroupName = "IB Confluence Filters")]
        public bool Play3VcpFilter { get; set; } = false;  // kills all IBFadeBot entries in NT8; enable for ablation only

        [NinjaScriptProperty]
        [Display(Name = "P3: Quarterly OPEX", Order = 11, GroupName = "IB Confluence Filters")]
        public bool Play3QuarterlyOpexFilter { get; set; } = false;  // over-restrictive in NT8; enable for ablation only

        [NinjaScriptProperty]
        [Display(Name = "P3: High Body Close", Order = 12, GroupName = "IB Confluence Filters")]
        public bool Play3HighBodyCloseFilter { get; set; } = false;  // over-restrictive in NT8; enable for ablation only

        #endregion

        #region IB-Specific State (Play 3 overshoot state machine + entry guards)

        /// <summary>Set when price overshoots above IB high by 0.25× range. Reset on entry/session-open.</summary>
        protected bool overshootAbove;

        /// <summary>Set when price overshoots below IB low by 0.25× range. Reset on entry/session-open.</summary>
        protected bool overshootBelow;

        /// <summary>Direction of the first IB break (+1 up, -1 down, 0 none yet). Used by Play 2 retest.</summary>
        protected int firstBreakDir;

        /// <summary>Time of the first break — for clock-size multiplier.</summary>
        protected DateTime firstBreakTime;

        // ── One-entry-per-direction guards (prevents over-trading: Python enters
        //    once per session per direction; without these guards, the bot re-enters
        //    on every bar beyond the IB boundary, producing 15+ trades/day vs 1). ──
        protected bool longTakenToday;
        protected bool shortTakenToday;

        #endregion

        #region Confluence Filter State (validated Python filter stack port)

        // ── VCP 3-day contraction: prev2 > prev1 > today IB range ──
        private double prevIBRange1;  // yesterday's IB range
        private double prevIBRange2;  // day-before-yesterday's IB range

        // ── 09:30-anchored AVWAP (cumulative TPV / cumulative volume from 09:30) ──
        private double avwapCumTPV;
        private double avwapCumVol;
        private double avwap0930Price;  // current 09:30-anchored AVWAP price
        private bool avwapActive;       // true once 09:30 anchor starts accumulating

        // ── EMA 20/50 for trend alignment (computed on DAILY close, matching Python) ──
        // Python computes EMA on session-window bars (last close per day), NOT every 1m bar.
        // We update these once per session at FinalizeRange using rangeClose as the daily close.
        private double dailyEma20;
        private double dailyEma50;
        private int dailyEmaBarCount;
        private bool dailyEmaUpdatedThisSession;

        // ── IB body-close flags (computed during BuildRangeWindow) ──
        private bool ibHighBodyClose;   // bar that made IB high closed in top 10% of range
        private bool ibLowBodyClose;    // bar that made IB low closed in bottom 10% of range

        // ── Break-vs-AVWAP direction (computed at first break) ──
        private int breakVsAvwap0930;    // +1 if close > AVWAP at first break, -1 if below, 0 unknown

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
            // Reset one-entry-per-direction guards at session open
            longTakenToday = false;
            shortTakenToday = false;

            // Confluence filter state — reset at session open
            // Roll VCP history: today's range becomes prev1, prev1 becomes prev2
            if (rangeRange > 0)
            {
                prevIBRange2 = prevIBRange1;
                prevIBRange1 = rangeRange;
            }
            avwapCumTPV = 0;
            avwapCumVol = 0;
            avwap0930Price = 0;
            avwapActive = false;
            breakVsAvwap0930 = 0;
            ibHighBodyClose = false;
            ibLowBodyClose = false;
            dailyEmaUpdatedThisSession = false;
        }

        #endregion

        #region Entry Guard Helpers (shared by all play bots)

        /// <summary>
        /// Returns true if a long entry is still allowed today (one per direction per session).
        /// Callers MUST set longTakenToday=true immediately after calling EnterWithRangeStop.
        /// </summary>
        protected bool CanEnterLong => !longTakenToday;

        /// <summary>
        /// Returns true if a short entry is still allowed today (one per direction per session).
        /// Callers MUST set shortTakenToday=true immediately after calling EnterWithRangeStop.
        /// </summary>
        protected bool CanEnterShort => !shortTakenToday;

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
                // Body-close: first bar sets both (will be overwritten if a later bar makes a new extreme)
                ibHighBodyClose = Close[0] >= rangeHigh - 0.1 * (rangeHigh - rangeLow);
                ibLowBodyClose  = Close[0] <= rangeLow + 0.1 * (rangeHigh - rangeLow);
            }
            else
            {
                if (High[0] > rangeHigh)
                {
                    rangeHigh = High[0];
                    firstHighTouch = now;
                    ibHighBodyClose = Close[0] >= rangeHigh - 0.1 * (rangeHigh - rangeLow);
                }
                if (Low[0] < rangeLow)
                {
                    rangeLow = Low[0];
                    firstLowTouch = now;
                    ibLowBodyClose = Close[0] <= rangeLow + 0.1 * (rangeHigh - rangeLow);
                }
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
            // firstBreakDir is now detected in UpdateConfluenceIndicators() (runs before filter).
            // This method is kept for backward compatibility with IBRetestBot.
            // No-op: break direction + breakVsAvwap already computed in UpdateConfluenceIndicators.
        }

        /// <summary>
        /// Detects overshoot for Play 3 fade entry.
        /// Overshoot threshold = LateBreakSizeMult × rangeRange (default 0.25×).
        /// Sets overshootAbove/Below flags — the fade bot checks for close-back-inside.
        /// </summary>
        protected void DetectOvershoot()
        {
            double threshold = LateBreakSizeMult * rangeRange;
            if (High[0] > rangeHigh + threshold) overshootAbove = true;
            if (Low[0] < rangeLow - threshold) overshootBelow = true;
        }

        #endregion

        #region Confluence Filter Stack (validated Python filters ported to NT8)

        /// <summary>
        /// Updates the 09:30-anchored AVWAP and EMA 20/50 on every bar.
        /// Call this from the start of CheckForEntry (or a per-bar hook).
        /// AVWAP resets at 09:30 each session; EMA is continuous across sessions.
        /// </summary>
        protected void UpdateConfluenceIndicators()
        {
            DateTime now = Time[0];

            // ── 09:30-anchored AVWAP: reset at 09:30, accumulate TPV/Vol ──
            int barMin = now.Hour * 60 + now.Minute;
            int anchorMin = RangeStartHour * 60 + RangeStartMinute;

            if (barMin == anchorMin)
            {
                avwapCumTPV = 0;
                avwapCumVol = 0;
                avwapActive = true;
                if (DebugMode) Log($"[DIAG] AVWAP anchor reset at {now:HH:mm} barMin={barMin} anchorMin={anchorMin}", LogLevel.Information);
            }

            if (avwapActive)
            {
                double tp = (High[0] + Low[0] + Close[0]) / 3.0;
                double vol = Volume[0];
                avwapCumTPV += tp * vol;
                avwapCumVol += vol;
                avwap0930Price = avwapCumVol > 0 ? avwapCumTPV / avwapCumVol : 0;
            }
            else if (DebugMode && barMin >= anchorMin && barMin <= anchorMin + 5)
            {
                Log($"[DIAG] AVWAP NOT active at {now:HH:mm} barMin={barMin} anchorMin={anchorMin} vol={Volume[0]}", LogLevel.Information);
            }

            // ── EMA 20/50 on DAILY close (matching Python session-window EMA) ──
            // Python computes EMA on the last close of each session window (daily granularity).
            // We update once per session at FinalizeRange using rangeClose as the daily close.
            // This captures the broader trend, not the intrabar noise that makes 1m EMA always
            // trend with the break direction.
            if (rangeComplete && !dailyEmaUpdatedThisSession)
            {
                double alpha20 = 2.0 / (20.0 + 1.0);
                double alpha50 = 2.0 / (50.0 + 1.0);
                if (dailyEmaBarCount == 0)
                {
                    dailyEma20 = rangeClose;
                    dailyEma50 = rangeClose;
                }
                else
                {
                    dailyEma20 = rangeClose * alpha20 + dailyEma20 * (1.0 - alpha20);
                    dailyEma50 = rangeClose * alpha50 + dailyEma50 * (1.0 - alpha50);
                }
                dailyEmaBarCount++;
                dailyEmaUpdatedThisSession = true;
                if (DebugMode) Log($"[DIAG] daily EMA updated: ema20={dailyEma20} ema50={dailyEma50} close={rangeClose} count={dailyEmaBarCount} at {Time[0]:HH:mm}", LogLevel.Information);
            }

            // ── Detect first break direction + break-vs-AVWAP (before filter checks) ──
            if (rangeComplete && firstBreakDir == 0)
            {
                if (Close[0] > rangeHigh) { firstBreakDir = 1; firstBreakTime = now; }
                else if (Close[0] < rangeLow) { firstBreakDir = -1; firstBreakTime = now; }
            }

            // Compute break-vs-AVWAP at the moment of first break
            if (breakVsAvwap0930 == 0 && firstBreakDir != 0 && avwapActive && avwap0930Price > 0)
            {
                breakVsAvwap0930 = Close[0] > avwap0930Price ? 1
                                : Close[0] < avwap0930Price ? -1 : 0;
                if (DebugMode) Log($"[DIAG] breakVsAvwap computed: dir={firstBreakDir} close={Close[0]} avwap={avwap0930Price} result={breakVsAvwap0930} at {Time[0]:HH:mm}", LogLevel.Information);
            }

            // Log AVWAP state periodically for debugging
            if (DebugMode && avwapActive && CurrentBar % 30 == 0)
                Log($"[DIAG] avwap: price={avwap0930Price} cumTPV={avwapCumTPV} cumVol={avwapCumVol} active={avwapActive} at {Time[0]:HH:mm}", LogLevel.Information);
        }

        /// <summary>
        /// break_vs_avwap_0930: +1 if close > 09:30-anchored AVWAP, -1 if below.
        /// Computed at the first break bar. Returns 0 if not yet computed.
        /// </summary>
        protected int BreakVsAvwap0930 => breakVsAvwap0930;

        /// <summary>
        /// trend_misaligned_with_break: EMA20 < EMA50 when break is up (or vice versa).
        /// True when the EMA trend disagrees with the first break direction.
        /// </summary>
        protected bool TrendMisalignedWithBreak
        {
            get
            {
                if (firstBreakDir == 0 || dailyEmaBarCount < 2) return false;
                bool emaBullish = dailyEma20 > dailyEma50;
                return (firstBreakDir == 1 && !emaBullish) || (firstBreakDir == -1 && emaBullish);
            }
        }

        /// <summary>
        /// trend_aligned_with_break: EMA trend agrees with first break direction.
        /// </summary>
        protected bool TrendAlignedWithBreak
        {
            get
            {
                if (firstBreakDir == 0 || dailyEmaBarCount < 2) return false;
                bool emaBullish = dailyEma20 > dailyEma50;
                return (firstBreakDir == 1 && emaBullish) || (firstBreakDir == -1 && !emaBullish);
            }
        }

        /// <summary>
        /// ib_vcp_3day_contracting: prev2 IB range > prev1 IB range > today's IB range.
        /// Requires 2 prior sessions of IB range history.
        /// </summary>
        protected bool Vcp3DayContracting
        {
            get
            {
                if (prevIBRange2 <= 0 || prevIBRange1 <= 0 || rangeRange <= 0) return false;
                return prevIBRange2 > prevIBRange1 && prevIBRange1 > rangeRange;
            }
        }

        /// <summary>
        /// is_opex_week: Monday-Friday of the monthly opex week (3rd Friday of month).
        /// </summary>
        protected bool IsOpexWeek
        {
            get
            {
                DateTime now = Time[0];
                return IsInOpexWeek(now);
            }
        }

        /// <summary>
        /// is_opex_friday: the 3rd Friday of the month (monthly opex day).
        /// </summary>
        protected bool IsOpexFriday
        {
            get
            {
                DateTime now = Time[0];
                return IsThirdFriday(now);
            }
        }

        /// <summary>
        /// is_quarterly_opex: 3rd Friday of Mar/Jun/Sep/Dec (triple witching).
        /// </summary>
        protected bool IsQuarterlyOpex
        {
            get
            {
                DateTime now = Time[0];
                return IsThirdFriday(now) && (now.Month == 3 || now.Month == 6 || now.Month == 9 || now.Month == 12);
            }
        }

        /// <summary>
        /// break_dir_matches_avwap0930: first break direction == break_vs_avwap_0930 direction.
        /// </summary>
        protected bool BreakDirMatchesAvwap0930
        {
            get { return firstBreakDir != 0 && breakVsAvwap0930 != 0 && firstBreakDir == breakVsAvwap0930; }
        }

        // ── Calendar helpers ──

        /// <summary>
        /// Returns true if the date is the 3rd Friday of its month.
        /// </summary>
        private static bool IsThirdFriday(DateTime d)
        {
            if (d.DayOfWeek != DayOfWeek.Friday) return false;
            // 3rd Friday: day-of-month is between 15 and 21
            return d.Day >= 15 && d.Day <= 21;
        }

        /// <summary>
        /// Returns true if the date falls in the opex week (Mon-Fri containing the 3rd Friday).
        /// </summary>
        private static bool IsInOpexWeek(DateTime d)
        {
            // Find the 3rd Friday of this month
            int year = d.Year;
            int month = d.Month;
            DateTime firstOfMonth = new DateTime(year, month, 1);
            int daysToFirstFriday = ((int)DayOfWeek.Friday - (int)firstOfMonth.DayOfWeek + 7) % 7;
            DateTime firstFriday = firstOfMonth.AddDays(daysToFirstFriday);
            DateTime thirdFriday = firstFriday.AddDays(14);
            // OpEx week: Monday (4 days before Friday) through Friday
            DateTime opexMonday = thirdFriday.AddDays(-4);
            return d.Date >= opexMonday.Date && d.Date <= thirdFriday.Date;
        }

        // ── ConfluenceFilter override: per-play validated filter stacks ──

        /// <summary>
        /// Updates the 09:30-anchored AVWAP and EMA 20/50 on every bar.
        /// Called by IntradayStrategyBase.CheckForSignal() before ConfluenceFilter().
        /// </summary>
        protected override void UpdateConfluenceIndicatorsHook()
        {
            UpdateConfluenceIndicators();
        }

        /// <summary>
        /// Per-play validated filter stack from ib_filter_stacks.parquet.
        /// Returns true to SKIP the trade (filter rejects), false to allow.
        ///
        /// Play 1 (Breakout): break_vs_avwap_0930==1 & trend_misaligned & vcp_3day & is_opex_week & ib_low_body_close
        ///   → WR 42.3% (from 28.9%), expectancy -0.15 (better but still negative)
        /// Play 2 (Retest): break_vs_avwap_0930==1 & trend_misaligned & vcp_3day & is_opex_week & break_dir_matches_avwap
        ///   → WR 15.5% (from 9.9%), expectancy -0.28 (worse — avoid)
        /// Play 3 (Fade): break_vs_avwap_0930==1 & vcp_3day & is_quarterly_opex & ib_high_body_close
        ///   → WR 20.3% (from 13.7%), expectancy +0.05 (barely positive)
        ///
        /// NOTE: Play 2 stack has negative expectancy — only enable for Play 1 and Play 3.
        /// The "realized_dir_break" stack (WR 62.5%, exp +0.25) is a direction-prediction
        /// filter, not a per-play entry filter — it can be used as a bias gate.
        /// </summary>
        protected override bool ConfluenceFilter()
        {
            if (!ConfluenceFilterEnabled) return false;
            if (!rangeComplete || rangeRange <= 0) return false;

            // Common: break_vs_avwap_0930 must be non-zero (close != AVWAP at first break).
            // Python converts via .astype(bool) — both +1 and -1 are True, only 0 is False.
            // This means "a break has occurred with a clear direction relative to AVWAP".
            if (breakVsAvwap0930 == 0)
            {
                if (DebugMode) Log($"[DIAG] filter: breakVsAvwap0930=0 (need non-zero) at {Time[0]:HH:mm}", LogLevel.Information);
                return true;  // skip if no break-vs-AVWAP computed yet
            }

            if (ActivePlay == 1)
            {
                // Play 1 stack: trend_misaligned & vcp_3day & is_opex_week & ib_low_body_close
                // NOTE: Each filter is individually toggleable for ablation testing.
                // All default true (the validated stack). Set false to relax individual filters.
                if (Play1TrendMisalignedFilter && !TrendMisalignedWithBreak) { if (DebugMode) Log($"[DIAG] filter P1: trend_misaligned FAIL at {Time[0]:HH:mm} dailyEma20={dailyEma20} dailyEma50={dailyEma50} firstBreakDir={firstBreakDir}", LogLevel.Information); return true; }
                if (Play1VcpFilter && !Vcp3DayContracting) { if (DebugMode) Log($"[DIAG] filter P1: vcp_3day FAIL at {Time[0]:HH:mm} prev2={prevIBRange2} prev1={prevIBRange1} today={rangeRange}", LogLevel.Information); return true; }
                if (Play1OpexWeekFilter && !IsOpexWeek) { if (DebugMode) Log($"[DIAG] filter P1: is_opex_week FAIL at {Time[0]:HH:mm} date={Time[0]:yyyy-MM-dd}", LogLevel.Information); return true; }
                if (Play1LowBodyCloseFilter && !ibLowBodyClose) { if (DebugMode) Log($"[DIAG] filter P1: ib_low_body_close FAIL at {Time[0]:HH:mm}", LogLevel.Information); return true; }
                return false;  // all filters passed — allow trade
            }

            if (ActivePlay == 3)
            {
                // Play 3 stack: vcp_3day & is_quarterly_opex & ib_high_body_close
                if (Play3VcpFilter && !Vcp3DayContracting) { if (DebugMode) Log($"[DIAG] filter P3: vcp_3day FAIL at {Time[0]:HH:mm} prev2={prevIBRange2} prev1={prevIBRange1} today={rangeRange}", LogLevel.Information); return true; }
                if (Play3QuarterlyOpexFilter && !IsQuarterlyOpex) { if (DebugMode) Log($"[DIAG] filter P3: is_quarterly_opex FAIL at {Time[0]:HH:mm} date={Time[0]:yyyy-MM-dd}", LogLevel.Information); return true; }
                if (Play3HighBodyCloseFilter && !ibHighBodyClose) { if (DebugMode) Log($"[DIAG] filter P3: ib_high_body_close FAIL at {Time[0]:HH:mm}", LogLevel.Information); return true; }
                return false;  // all filters passed — allow trade
            }

            // Play 2: stack has negative expectancy — skip filtering (let all entries through)
            return false;  // no filter for unhandled plays
        }

        #endregion
    }
}