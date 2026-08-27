#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
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

        [NinjaScriptProperty]
        [Display(Name = "P2: FVG Bias Aligned", Order = 13, GroupName = "IB Confluence Filters")]
        public bool Play2FvgBiasFilter { get; set; } = true;  // Session 10: FVG-aligned is the only OOS-valid ex-ante filter

        // ── Play 2 retest-depth bias overlay (Session 11 regime kill-switch) ──
        // Scales position size by retest quality: shallow retests (weak breaks that
        // reverse) get reduced size; deep retests (genuine thrusts) get full size.
        // Forensic (2026-07-30): depth>=0.9 H2 WR 0.50 (positive EV), depth<0.9 H2 WR 0.00.
        // Overlay (0.10/0.50/1.00 @ 0.6/0.9): MaxDD -23,145 -> -7,157 (-69%), PF 1.475 -> 2.024.
        // NOT a hard skip — keeps all trades, penalizes the weak-retest root cause via size.
        [NinjaScriptProperty]
        [Display(Name = "P2: Depth Size Overlay", Order = 14, GroupName = "IB Confluence Filters")]
        public bool Play2DepthSizeOverlay { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "P2: Depth Weak Threshold", Order = 15, GroupName = "IB Confluence Filters")]
        public double DepthWeakThreshold { get; set; } = 0.6;   // depth < this -> weak size

        [NinjaScriptProperty]
        [Display(Name = "P2: Depth Strong Threshold", Order = 16, GroupName = "IB Confluence Filters")]
        public double DepthStrongThreshold { get; set; } = 0.9; // depth >= this -> full size

        [NinjaScriptProperty]
        [Display(Name = "P2: Depth Weak Size Mult", Order = 17, GroupName = "IB Confluence Filters")]
        public double DepthWeakSizeMult { get; set; } = 0.10;   // weak retest size fraction

        [NinjaScriptProperty]
        [Display(Name = "P2: Depth Moderate Size Mult", Order = 18, GroupName = "IB Confluence Filters")]
        public double DepthModerateSizeMult { get; set; } = 0.50; // moderate retest size fraction

        #endregion

        #region Universal Basis Points (bps) & Pack Trading Parameters

        [NinjaScriptProperty]
        [Display(Name = "Risk Floor (bps)", Order = 1, GroupName = "Pack Trading & Risk Brackets")]
        public double RiskFloorBps { get; set; } = 2.0;

        [NinjaScriptProperty]
        [Display(Name = "Risk Ceiling (bps)", Order = 2, GroupName = "Pack Trading & Risk Brackets")]
        public double RiskCeilingBps { get; set; } = 15.0;

        [NinjaScriptProperty]
        [Display(Name = "Cover The Queen Target (bps)", Order = 3, GroupName = "Pack Trading & Risk Brackets")]
        public double CoverQueenBps { get; set; } = 10.0;

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (bps)", Order = 4, GroupName = "Pack Trading & Risk Brackets")]
        public double RunnerBps { get; set; } = 30.0;

        [NinjaScriptProperty]
        [Display(Name = "Use BPS Stop Ceiling", Order = 5, GroupName = "Pack Trading & Risk Brackets")]
        public bool UseBpsStopCeiling { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Use IB Midpoint Gate", Order = 6, GroupName = "Pack Trading & Risk Brackets")]
        public bool UseIbMidFilter { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Earliest Continuation Time (ET)", Order = 7, GroupName = "Pack Trading & Risk Brackets")]
        public int EarliestContinuationTime { get; set; } = 1030;

        [NinjaScriptProperty]
        [Display(Name = "Enable Lunch Moratorium (11:30-13:30)", Order = 8, GroupName = "Pack Trading & Risk Brackets")]
        public bool EnableLunchMoratorium { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Use 5m FVG Anti-Chop Gate", Order = 9, GroupName = "Pack Trading & Risk Brackets")]
        public bool UseFvgChopGate { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Use 09:00 Sweep / R1 Whipsaw Gate", Order = 10, GroupName = "Pack Trading & Risk Brackets")]
        public bool Use0900SweepGate { get; set; } = true;

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

        /// <summary>Breakout wave extreme tracked after the first break (highest high for long, lowest low for short).</summary>
        protected double breakoutExtreme;
        protected bool breakoutActive;

        // ── Retest-depth tracker (Play 2 bias overlay — Session 11 regime kill-switch) ──
        // Max excursion past rangeMid in the break direction, measured in POINTS,
        // accumulated each bar AFTER the first break and BEFORE the retest entry.
        // depth_ratio = maxExcursionPastMid / rangeRange. Ex-ante at entry time.
        // Root cause (forensic 2026-07-30): shallow retests (depth<0.9) are weak/false
        // breaks that reverse to the opposite IB boundary (H2-2026 loss mechanism);
        // deep retests (depth>=0.9) are genuine momentum thrusts that continue.
        protected double maxExcursionPastMid;

        // ── One-entry-per-direction guards (prevents over-trading: Python enters
        //    once per session per direction; without these guards, the bot re-enters
        //    on every bar beyond the IB boundary, producing 15+ trades/day vs 1). ──
        protected bool longTakenToday;
        protected bool shortTakenToday;

        // ── 09:00 AM Hourly sweep & R1 whipsaw tracking ──
        protected double h09High;
        protected double h09Low;
        protected bool isDoubleSweepWhipsawDay;

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

        // ── FVG (Fair Value Gap) bias from the IB window ──
        // Mirrors Python's detect_fvgs_v5 on 5-min resampled bars within the IB window.
        // bias_fvg = +1 (bullish FVG), -1 (bearish FVG), 0 (none).
        // Only the FIRST FVG finalized within the IB window (09:30-09:59) counts.
        // FVG finalized time = bar_start + 5min must be <= IB end (09:59).
        private int biasFvg;
        private bool biasFvgComputed;
        // FVG price band (for chart drawing)
        private double fvgTop, fvgBottom;
        private DateTime fvgFinalizedTime;
        // 5-min bar accumulator (built from 1-min bars during the IB window)
        private double fvg5mOpen, fvg5mHigh, fvg5mLow, fvg5mClose;
        private int fvg5mBarCount;  // 1-min bars in the current 5-min bucket (0-4)
        private DateTime fvg5mBucketStart;
        // Rolling 5-min bars for the 3-bar FVG pattern (need bars i-2, i-1, i)
        private double[] prev5mHigh = new double[2];  // [i-2 high, i-1 high]
        private double[] prev5mLow = new double[2];    // [i-2 low,  i-1 low]
        private int prev5mCount;  // how many completed 5-min bars we have (0, 1, 2+)

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

            // Enable ConfluenceFilter (the per-play validated filter stack) — Session 10:
            // required for the FVG-aligned bias filter on Play 2 to take effect.
            ConfluenceFilterEnabled = true;
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
            breakoutExtreme = 0;
            breakoutActive = false;
            // Reset retest-depth tracker at session open
            maxExcursionPastMid = 0;
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
            // FVG state — reset at session open
            biasFvg = 0;
            fvgTop = fvgBottom = 0;
            fvgFinalizedTime = DateTime.MinValue;
            biasFvgComputed = false;
            fvg5mBarCount = 0;
            fvg5mBucketStart = DateTime.MinValue;
            prev5mCount = 0;
            prev5mHigh[0] = prev5mHigh[1] = 0;
            prev5mLow[0] = prev5mLow[1] = 0;
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

        /// <summary>
        /// Override FinalizeRange to draw IB boundaries + quarters once the range completes.
        /// </summary>
        protected override void FinalizeRange()
        {
            base.FinalizeRange();
            DrawIBBoundaries();
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
        /// Retest-depth size multiplier (Play 2 regime kill-switch overlay, Session 11).
        /// Scales position size by retest quality. Root cause: shallow retests (depth &lt;
        /// DepthStrongThreshold) are weak/false breaks that reverse to the opposite IB
        /// boundary (confirmed H2-2026 loss mechanism, 91.7% full reversal); deep retests
        /// are genuine momentum thrusts that continue (H2 depth>=0.9 WR 0.50 vs depth<0.9 WR 0.00).
        /// depth_ratio = maxExcursionPastMid / rangeRange (ex-ante, known at entry).
        /// Returns: DepthWeakSizeMult if depth &lt; DepthWeakThreshold, DepthModerateSizeMult
        /// if depth &lt; DepthStrongThreshold, else 1.0 (full size). Falls back to 1.0 when
        /// the overlay is disabled or range is unavailable (never blocks entry).
        /// </summary>
        protected double DepthSizeMultiplier()
        {
            if (!Play2DepthSizeOverlay || ActivePlay != 2) return 1.0;
            if (!rangeComplete || rangeRange <= 0) return 1.0;
            double depthRatio = maxExcursionPastMid / rangeRange;
            if (depthRatio < DepthWeakThreshold) return DepthWeakSizeMult;
            if (depthRatio < DepthStrongThreshold) return DepthModerateSizeMult;
            return 1.0;
        }

        /// <summary>
        /// Converts Basis Points (bps, 1 bps = 0.01% = 0.0001) to price points.
        /// </summary>
        public double BpsToPoints(double bps, double refPrice)
        {
            return refPrice * (bps * 0.0001);
        }

        /// <summary>
        /// Converts price points to Basis Points (bps).
        /// </summary>
        public double PointsToBps(double points, double refPrice)
        {
            return refPrice > 0 ? (points / refPrice) * 10000.0 : 0;
        }

        /// <summary>
        /// Calculates the Fibonacci retracement level after an IB breakout (Play 2 Fib Retest).
        /// Long: Fib retraced from breakoutExtreme back towards rangeHigh.
        /// Short: Fib retraced from breakoutExtreme back towards rangeLow.
        /// </summary>
        public double GetFibRetracementLevel(int dir, double fibRatio)
        {
            if (dir == 1 && rangeHigh > 0 && breakoutExtreme >= rangeHigh)
            {
                double wave = breakoutExtreme - rangeHigh;
                return breakoutExtreme - (wave * fibRatio);
            }
            else if (dir == -1 && rangeLow > 0 && breakoutExtreme <= rangeLow)
            {
                double wave = rangeLow - breakoutExtreme;
                return breakoutExtreme + (wave * fibRatio);
            }
            return rangeMid;
        }

        /// <summary>
        /// Validates temporal and macro gates (10:30 stabilization fence, lunch moratorium, and R1 double sweep lockout).
        /// </summary>
        public bool IsContinuationTimeAllowed()
        {
            int nowNum = ToTime(Time[0]);
            if (nowNum < EarliestContinuationTime * 100) return false;
            if (EnableLunchMoratorium && nowNum >= 113000 && nowNum <= 133000) return false;
            if (Use0900SweepGate && isDoubleSweepWhipsawDay) return false;
            return true;
        }

        /// <summary>
        /// Validates IB Midpoint gravitational gate (Long > Mid, Short < Mid).
        /// </summary>
        public bool HasIbMidConfluence(int dir, double price)
        {
            if (!UseIbMidFilter || rangeMid <= 0) return true;
            return dir == 1 ? price > rangeMid : price < rangeMid;
        }

        /// <summary>
        /// Enters trade with 2-tier Pack Trading brackets (Cover The Queen + Runner) or single-order range stop/target.
        /// Conforms strictly to Universal Basis Points standard (ADR-002/ADR-010).
        /// </summary>
        protected void EnterWithPackTradingBrackets(int dir, double entry, double stopPrice, double tp1Price, double tp2Price, int qty)
        {
            if (dir == 1 && (stopPrice >= entry || tp1Price <= entry)) return;
            if (dir == -1 && (stopPrice <= entry || tp1Price >= entry)) return;

            entryPrice = entry;
            initialStopPrice = stopPrice;
            currentStopPrice = stopPrice;
            riskPoints = Math.Abs(entry - stopPrice);
            breakevenMoved = false;
            tradeIsActive = true;

            int halfQty = Math.Max(1, qty / 2);
            int runnerQty = Math.Max(1, qty - halfQty);

            if (TradePolicy == TradePolicyType.CoverTheQueen)
            {
                if (dir == 1)
                {
                    tradeDirection = "Long";
                    entrySignalName = "IB_Long";
                    EnterLong(halfQty, entrySignalName + "_Queen");
                    EnterLong(runnerQty, entrySignalName + "_Runner");
                    SetProfitTarget(entrySignalName + "_Queen", CalculationMode.Price, tp1Price);
                    SetStopLoss(entrySignalName + "_Queen", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget(entrySignalName + "_Runner", CalculationMode.Price, tp2Price);
                    SetStopLoss(entrySignalName + "_Runner", CalculationMode.Price, stopPrice, false);
                }
                else
                {
                    tradeDirection = "Short";
                    entrySignalName = "IB_Short";
                    EnterShort(halfQty, entrySignalName + "_Queen");
                    EnterShort(runnerQty, entrySignalName + "_Runner");
                    SetProfitTarget(entrySignalName + "_Queen", CalculationMode.Price, tp1Price);
                    SetStopLoss(entrySignalName + "_Queen", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget(entrySignalName + "_Runner", CalculationMode.Price, tp2Price);
                    SetStopLoss(entrySignalName + "_Runner", CalculationMode.Price, stopPrice, false);
                }
            }
            else
            {
                EnterWithRangeStop(dir, entry, stopPrice, tp1Price, qty);
                return;
            }

            todayTradeCount++;
            Print(string.Format("[{0}] ENTRY {1} @ {2:F2} | Stop {3:F2} | TP1 {4:F2} | TP2 {5:F2} | Qty {6} | Policy {7}",
                GetStrategyName(), tradeDirection, entry, stopPrice, tp1Price, tp2Price, qty, TradePolicy));
        }

        // ── CHART VISUALIZATION (Session 12) ────────────────────────────────
        // Draws IB boundaries (high/low/mid), quarter levels (25/50/75%), FVG box,
        // and a HUD text panel with all filter criteria so you can visually verify
        // the bot is computing the same values as the Python harness.
        // All drawing uses NT8 Draw.* API (auto-managed — objects are tagged with
        // the current bar so they update/expire correctly).
        //
        // Drawing schedule:
        //   - IB boundaries + quarters: drawn once at FinalizeRange (10:00 ET)
        //   - FVG box: drawn when the FVG is detected (during IB window)
        //   - HUD: updated every bar (so filter states stay current)
        //
        // Toggle via the DrawVisuals NinjaScriptProperty (default true).

        /// <summary>
        /// Draws the IB range box, quarter levels, and mid line on the chart.
        /// Called once at FinalizeRange. Lines extend to session end (16:00 ET).
        /// </summary>
        protected void DrawIBBoundaries()
        {
            if (!DrawVisuals || !rangeComplete || rangeRange <= 0) return;
            if (BarsArray == null || BarsArray.Length == 0) return;

            int sessionEndBar = BarsArray[0].GetBar(Time[0].Date.AddHours(16));
            if (sessionEndBar < CurrentBar) sessionEndBar = CurrentBar + 390;
            DateTime sessionEnd = BarsArray[0].GetTime(sessionEndBar);
            if (sessionEnd < Time[0]) sessionEnd = Time[0].Date.AddHours(16);

            // IB high (blue dashed)
            Draw.Line(this, "IB_High", false, rangeCompleteTime, rangeHigh, sessionEnd, rangeHigh,
                Brushes.DodgerBlue, DashStyleHelper.Dash, 2);
            Draw.Text(this, "IB_High_L", $"IB H {rangeHigh:F2}", 0, rangeHigh + TickSize * 2);

            // IB low (blue dashed)
            Draw.Line(this, "IB_Low", false, rangeCompleteTime, rangeLow, sessionEnd, rangeLow,
                Brushes.DodgerBlue, DashStyleHelper.Dash, 2);
            Draw.Text(this, "IB_Low_L", $"IB L {rangeLow:F2}", 0, rangeLow - TickSize * 2);

            // IB mid (orange dotted)
            Draw.Line(this, "IB_Mid", false, rangeCompleteTime, rangeMid, sessionEnd, rangeMid,
                Brushes.Orange, DashStyleHelper.Dot, 2);
            Draw.Text(this, "IB_Mid_L", $"Mid {rangeMid:F2}", 0, rangeMid);

            // Quarter levels: 25% and 75% of IB range (thin gray)
            double q25 = rangeLow + 0.25 * rangeRange;
            double q75 = rangeLow + 0.75 * rangeRange;
            Draw.Line(this, "IB_Q25", false, rangeCompleteTime, q25, sessionEnd, q25,
                Brushes.Gray, DashStyleHelper.Dot, 1);
            Draw.Text(this, "IB_Q25_L", "25%", 0, q25);
            Draw.Line(this, "IB_Q75", false, rangeCompleteTime, q75, sessionEnd, q75,
                Brushes.Gray, DashStyleHelper.Dot, 1);
            Draw.Text(this, "IB_Q75_L", "75%", 0, q75);

            // IB box shading (light blue rectangle)
            Draw.Rectangle(this, "IB_Box", false, rangeCompleteTime, rangeHigh,
                rangeCompleteTime.AddMinutes(-RangeDurationMin), rangeLow,
                Brushes.LightSkyBlue, Brushes.LightSkyBlue, 30);
        }

        /// <summary>
        /// Draws the IB-window FVG as a colored box on the chart.
        /// Called when the FVG is first detected. Bullish=green, bearish=red.
        /// </summary>
        protected void DrawFVG()
        {
            if (!DrawVisuals || biasFvg == 0 || fvgTop <= 0 || fvgBottom <= 0) return;
            if (BarsArray == null || BarsArray.Length == 0) return;

            int sessionEndBar = BarsArray[0].GetBar(Time[0].Date.AddHours(16));
            if (sessionEndBar < CurrentBar) sessionEndBar = CurrentBar + 390;
            DateTime sessionEnd = BarsArray[0].GetTime(sessionEndBar);
            if (sessionEnd < Time[0]) sessionEnd = Time[0].Date.AddHours(16);

            Brush fvgColor = biasFvg == 1 ? Brushes.LimeGreen : Brushes.IndianRed;
            string fvgDir = biasFvg == 1 ? "BULL" : "BEAR";

            Draw.Rectangle(this, "FVG_Box", false, fvgFinalizedTime, fvgTop,
                sessionEnd, fvgBottom, fvgColor, fvgColor, 50);
            Draw.Text(this, "FVG_L", $"FVG {fvgDir} [{fvgBottom:F1}-{fvgTop:F1}]", 0, fvgTop + TickSize * 2);
        }

        /// <summary>
        /// Draws a HUD text panel in the upper-left of the chart showing all filter
        /// criteria and their current state. Updated every bar.
        /// Layout: Play | Time | IB range | First break | FVG | AVWAP | Trend | Depth
        /// </summary>
        protected void DrawHUD()
        {
            if (!DrawVisuals) return;
            if (BarsArray == null || BarsArray.Length == 0) return;

            string playName = ActivePlay == 1 ? "P1 Breakout" : ActivePlay == 2 ? "P2 Retest" : ActivePlay == 3 ? "P3 Fade" : "?";
            string breakStr = firstBreakDir == 0 ? "none" : firstBreakDir == 1 ? "UP" : "DOWN";
            string fvgStr = biasFvg == 0 ? "none" : biasFvg == 1 ? "bull" : "bear";
            string fvgAligned = BiasFvgAlignedWithBreak ? "YES" : "NO";
            string avwapStr = breakVsAvwap0930 == 0 ? "n/a" : breakVsAvwap0930 == 1 ? "above" : "below";
            string trendStr = firstBreakDir == 0 ? "n/a" : TrendMisalignedWithBreak ? "misaligned" : "aligned";
            double depthRatio = rangeRange > 0 ? maxExcursionPastMid / rangeRange : 0;
            string depthTier = depthRatio < DepthWeakThreshold ? "weak" : depthRatio < DepthStrongThreshold ? "moderate" : "strong";
            string depthOverlay = (Play2DepthSizeOverlay && ActivePlay == 2) ? $"x{DepthSizeMultiplier():F2}" : "off";

            // Calendar filters
            string calFilters = "";
            if (SkipMondayPlay2 && ActivePlay == 2) calFilters += "SkipMon ";
            if (SkipFebruaryPlay2 && ActivePlay == 2) calFilters += "SkipFeb ";
            if (SkipMayPlay1 && ActivePlay == 1) calFilters += "SkipMay ";
            if (SkipOctoberPlay3 && ActivePlay == 3) calFilters += "SkipOct ";
            if (string.IsNullOrEmpty(calFilters)) calFilters = "none";

            string confState = ConfluenceFilterEnabled ? "ON" : "OFF";
            string ibCompStr = rangeComplete ? "YES @ " + rangeCompleteTime.ToString("HH:mm") : "NO";

            string hud = $"=== {GetStrategyName()} ===\n" +
                $"Play: {playName}  |  Time: {Time[0]:HH:mm} ET  |  Date: {Time[0]:yyyy-MM-dd}\n" +
                $"IB: H={rangeHigh:F2} L={rangeLow:F2} Mid={rangeMid:F2} Range={rangeRange:F2}\n" +
                $"IB complete: {ibCompStr}\n" +
                $"First break: {breakStr}  |  AVWAP: {avwapStr}  |  Trend: {trendStr}\n" +
                $"FVG: {fvgStr} aligned={fvgAligned}  |  Depth: {depthRatio:F2} [{depthTier}] {depthOverlay}\n" +
                $"ConfluenceFilter: {confState}  |  Calendar: {calFilters}\n" +
                $"EMA20={dailyEma20:F2} EMA50={dailyEma50:F2}  |  MaxTrades={MaxTradesPerDay} Today={todayTradeCount}";

            // Draw HUD as text at the upper-left (barsAgo=0, price=High[0] offset up)
            Draw.Text(this, "HUD", hud, 0, High[0] + rangeRange * 0.5);
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

            // ── Retest-depth tracker: max excursion past rangeMid in break dir (Play 2 overlay) ──
            // Updated every bar AFTER the first break, BEFORE the retest entry. Ex-ante at entry.
            // depth_ratio = maxExcursionPastMid / rangeRange. Used by DepthSizeMultiplier().
            if (firstBreakDir != 0 && rangeRange > 0 && rangeComplete)
            {
                double excursion = firstBreakDir == 1 ? High[0] - rangeMid : rangeMid - Low[0];
                if (excursion > maxExcursionPastMid) maxExcursionPastMid = excursion;

                // Track breakout wave extreme for Fibonacci retracement calculations (Play 2 Fib 38.2%)
                if (firstBreakDir == 1)
                {
                    if (!breakoutActive) { breakoutExtreme = High[0]; breakoutActive = true; }
                    else if (High[0] > breakoutExtreme) breakoutExtreme = High[0];
                }
                else if (firstBreakDir == -1)
                {
                    if (!breakoutActive) { breakoutExtreme = Low[0]; breakoutActive = true; }
                    else if (Low[0] < breakoutExtreme) breakoutExtreme = Low[0];
                }
            }

            // Log AVWAP state periodically for debugging
            if (DebugMode && avwapActive && CurrentBar % 30 == 0)
                Log($"[DIAG] avwap: price={avwap0930Price} cumTPV={avwapCumTPV} cumVol={avwapCumVol} active={avwapActive} at {Time[0]:HH:mm}", LogLevel.Information);

            // ── FVG detection on 5-min resampled bars (IB window only) ───────────
            // Mirrors Python detect_fvgs_v5 on '5min' resampled bars, filtered to
            // FVGs finalized within the IB window (09:30-09:59). The FIRST such FVG
            // sets bias_fvg for the day. Bullish FVG: high[i-2] < low[i]. Bearish: low[i-2] > high[i].
            if (!biasFvgComputed && now >= new DateTime(now.Year, now.Month, now.Day, RangeStartHour, RangeStartMinute, 0))
            {
                Update5mFvgAccumulator(now);
                // Draw the FVG box as soon as it's detected (first detection only)
                if (biasFvg != 0 && fvgFinalizedTime == Time[0])
                    DrawFVG();
            }

            // ── HUD: update every bar so filter states stay current ──
            DrawHUD();
        }

        /// <summary>
        /// Builds 5-min OHLC bars from 1-min bars and detects the first IB-window FVG.
        /// Mirrors Python's detect_fvgs_v5(resample='5min') + is_eligible_ib filter.
        /// A 5-min bar is finalized at minute :04, :09, :14, ... (bar_start + 5min).
        /// FVG finalized time = 5-min bar close, must be <= IB end (09:59 for 30-min IB).
        /// </summary>
        private void Update5mFvgAccumulator(DateTime now)
        {
            DateTime ibStart = new DateTime(now.Year, now.Month, now.Day, RangeStartHour, RangeStartMinute, 0);
            DateTime ibEnd = ibStart.AddMinutes(RangeDurationMin);  // 10:00 for 30-min IB

            // Skip bars outside the IB window (only finalize FVGs whose 5-min bar closes by ibEnd)
            if (now >= ibEnd.AddMinutes(5))  // 5-min bar starting at 09:55 closes at 10:00 — too late
            {
                biasFvgComputed = true;  // IB window elapsed, no more FVGs can finalize in time
                return;
            }

            // Determine which 5-min bucket this 1-min bar belongs to
            int minuteOfDay = now.Hour * 60 + now.Minute;
            int bucketStartMin = (minuteOfDay / 5) * 5;
            DateTime bucketStart = new DateTime(now.Year, now.Month, now.Day, bucketStartMin / 60, bucketStartMin % 60, 0);

            // If we moved to a new 5-min bucket, finalize the previous one
            if (fvg5mBucketStart != DateTime.MinValue && bucketStart > fvg5mBucketStart)
            {
                Finalize5mBar();
            }

            // Accumulate this 1-min bar into the current 5-min bucket
            if (fvg5mBarCount == 0)
            {
                fvg5mBucketStart = bucketStart;
                fvg5mOpen = Open[0];
                fvg5mHigh = High[0];
                fvg5mLow = Low[0];
            }
            else
            {
                if (High[0] > fvg5mHigh) fvg5mHigh = High[0];
                if (Low[0] < fvg5mLow) fvg5mLow = Low[0];
            }
            fvg5mClose = Close[0];
            fvg5mBarCount++;
        }

        /// <summary>
        /// Finalize the current 5-min bar and check for a 3-bar FVG pattern.
        /// Bullish FVG: high[i-2] < low[i] (gap above the middle bar).
        /// Bearish FVG: low[i-2] > high[i] (gap below the middle bar).
        /// Only the FIRST FVG finalized within the IB window is kept.
        /// </summary>
        private void Finalize5mBar()
        {
            if (fvg5mBarCount == 0) return;

            // Check for FVG if we have at least 3 completed 5-min bars (i-2, i-1, i)
            // At prev5mCount==2, prev5mHigh[0]=i-2, prev5mHigh[1]=i-1, current=i
            if (prev5mCount >= 2 && biasFvg == 0)
            {
                double highIm2 = prev5mHigh[0];  // high[i-2]
                double lowIm2 = prev5mLow[0];    // low[i-2]
                double highI = fvg5mHigh;        // high[i]
                double lowI = fvg5mLow;          // low[i]

                if (highIm2 < lowI)
                {
                    biasFvg = 1;  // bullish FVG: gap between high[i-2] and low[i]
                    biasFvgComputed = true;
                    fvgBottom = highIm2;
                    fvgTop = lowI;
                    fvgFinalizedTime = Time[0];
                    if (DebugMode) Log($"[DIAG] FVG bullish detected: high[i-2]={highIm2} < low[i]={lowI} gap=[{fvgBottom},{fvgTop}] at {Time[0]:HH:mm}", LogLevel.Information);
                }
                else if (lowIm2 > highI)
                {
                    biasFvg = -1;  // bearish FVG: gap between low[i-2] and high[i]
                    biasFvgComputed = true;
                    fvgTop = lowIm2;
                    fvgBottom = highI;
                    fvgFinalizedTime = Time[0];
                    if (DebugMode) Log($"[DIAG] FVG bearish detected: low[i-2]={lowIm2} > high[i]={highI} gap=[{fvgBottom},{fvgTop}] at {Time[0]:HH:mm}", LogLevel.Information);
                }
            }

            // Shift the rolling window: [i-1] becomes [i-2], current becomes [i-1]
            prev5mHigh[0] = prev5mHigh[1];
            prev5mLow[0] = prev5mLow[1];
            prev5mHigh[1] = fvg5mHigh;
            prev5mLow[1] = fvg5mLow;
            if (prev5mCount < 2) prev5mCount++;

            fvg5mBarCount = 0;  // reset for the next 5-min bucket
        }

        /// <summary>
        /// bias_fvg: +1 (bullish FVG in IB window), -1 (bearish), 0 (none).
        /// Mirrors Python's ib_confluence bias_fvg column (first IB-window FVG).
        /// </summary>
        protected int BiasFvg => biasFvg;

        /// <summary>
        /// bias_fvg aligned with first break direction (the validated FVG filter).
        /// True when the IB-window FVG direction matches the first break direction.
        /// </summary>
        protected bool BiasFvgAlignedWithBreak
        {
            get
            {
                if (biasFvg == 0 || firstBreakDir == 0) return false;
                return biasFvg == firstBreakDir;
            }
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

            // Play 2: FVG-aligned bias filter (Session 10: only OOS-valid ex-ante filter)
            if (ActivePlay == 2)
            {
                // Param-propagation guard: the SA grid may not inherit SetStrategyDefaults
                // values for NinjaScriptProperty booleans. If the ConfluenceFilter is
                // enabled but Play2FvgBiasFilter got reset to false by the SA template,
                // force it back on (the only OOS-valid filter — never trade Play 2 without it).
                if (ConfluenceFilterEnabled && !Play2FvgBiasFilter)
                {
                    Play2FvgBiasFilter = true;
                    if (DebugMode) Log("[DIAG] filter P2: Play2FvgBiasFilter was false — forced ON (OOS-valid filter)", LogLevel.Information);
                }
                if (Play2FvgBiasFilter)
                {
                    if (biasFvg == 0)
                    {
                        if (DebugMode) Log($"[DIAG] filter P2: no IB-window FVG at {Time[0]:HH:mm}", LogLevel.Information);
                        return true;  // skip if no FVG formed in the IB window
                    }
                    if (!BiasFvgAlignedWithBreak)
                    {
                        if (DebugMode) Log($"[DIAG] filter P2: FVG not aligned w/ break (biasFvg={biasFvg} firstBreakDir={firstBreakDir}) at {Time[0]:HH:mm}", LogLevel.Information);
                        return true;  // skip if FVG direction disagrees with break
                    }
                }
                return false;  // FVG-aligned or filter disabled — allow trade
            }

            // Play 2: stack has negative expectancy — skip filtering (let all entries through)
            return false;  // no filter for unhandled plays
        }

        #endregion
    }
}