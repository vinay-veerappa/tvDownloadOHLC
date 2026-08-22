#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
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
    /// IBFadeBot — IB Sweep Fade with FVG Displacement (Play 3 Enhanced).
    ///
    /// Upgraded from the original overshoot-only fade to match the Python
    /// benchmark_range_regime_fvg.py strategy that achieved 87% WR / PF 9.4
    /// over 5 years (2021-2026) on ES and NQ.
    ///
    /// KEY CHANGES FROM ORIGINAL:
    /// 1. FVG Displacement Filter: requires a 5m Fair Value Gap on the rejection
    ///    bar (the edge that separates real institutional rejections from noise).
    /// 2. IB Compression Filter: only trades when IB range < 0.40 × ATR (mean-reverting regime).
    /// 3. Session Restriction: Midday + PM only (11:30-16:00 ET) — morning momentum is excluded.
    /// 4. 2-Leg Scaling: 50% at IB midpoint (TP1), 50% runner to opposite IB boundary (TP2).
    /// 5. Stop: 2 ticks beyond the sweep wick extreme (not a fixed fraction of IB range).
    /// 6. Diagnostic CSV: bar-by-bar state output for Python parity comparison.
    ///
    /// Python validation (2021-2026, 4 Micro MES / 2 Micro MNQ):
    ///   ES: 747 trades, 86.7% WR, PF 9.39, MaxDD $330, Net $59,853, 100% prop pass
    ///   NQ: 780 trades, 87.6% WR, PF 10.91, MaxDD $398, Net $67,199, 100% prop pass
    /// </summary>
    public class IBFadeBot : IBStrategyBase
    {
        #region FVG Sweep Fade Parameters

        [NinjaScriptProperty]
        [Display(Name = "FVG Displacement Required", Order = 20, GroupName = "Sweep Fade")]
        public bool FvgDisplacementRequired { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min FVG Size (pts)", Order = 21, GroupName = "Sweep Fade")]
        public double MinFvgSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "IB Compression Max ATR Ratio", Order = 22, GroupName = "Sweep Fade")]
        public double IbCompressionAtrRatio { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Sweep Stop Ticks Beyond Wick", Order = 23, GroupName = "Sweep Fade")]
        public int SweepStopTicks { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk ATR Fraction", Order = 24, GroupName = "Sweep Fade")]
        public double MaxRiskAtrFraction { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Midday Start (HHMM)", Order = 25, GroupName = "Sweep Fade")]
        public int MiddayStart { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "PM End (HHMM)", Order = 26, GroupName = "Sweep Fade")]
        public int PmEnd { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use 2-Leg Scaling", Order = 27, GroupName = "Sweep Fade")]
        public bool UseTwoLegScaling { get; set; }

        #endregion

        #region Diagnostic CSV

        private System.IO.StreamWriter diagCsv;
        private bool diagCsvHeaderWritten;

        #endregion

        #region 5m Bar Accumulator (post-IB sweep detection)

        // Rolling 5m bars built from 1m bars for FVG detection during Midday/PM
        private double fvg5mOpen, fvg5mHigh, fvg5mLow, fvg5mClose;
        private int fvg5mBarCount;
        private DateTime fvg5mBucketStart;

        // Rolling 3-bar window for 3-bar FVG pattern (b0, b1, b2)
        private double[] prev5mHigh = new double[2];
        private double[] prev5mLow = new double[2];
        private double[] prev5mOpen = new double[2];
        private double[] prev5mClose = new double[2];
        private int prev5mCount;

        // Track the sweep wick extreme for stop placement
        private double currentSweepExtreme;
        private int sweepSweepDir;  // +1 = swept high (short setup), -1 = swept low (long setup)
        private double armedEntryPrice;
        private double armedStopPrice;
        private double armedTp1Price;
        private double armedTp2Price;

        // ATR for compression filter (daily ATR from 1m bars)
        private double dailyAtrVal;
        private double priorDayHigh, priorDayLow, priorDayClose;
        private bool priorDayReady;

        #endregion

        protected override void ConfigureStrategy()
        {
        }

        protected override void SetStrategyDefaults()
        {
            base.SetStrategyDefaults();
            Name = "IBFadeBot";
            ActivePlay = 3;
            TargetLvl = 1.0;      // Full reversion to opposite IB boundary
            StopRMult = 0.5;      // Fallback if FVG sweep not used
            LateBreakSizeMult = 0.35;

            // FVG Sweep Fade defaults (matching Python benchmark)
            FvgDisplacementRequired = true;
            MinFvgSize = 0.75;     // ES default; NQ uses 3.5 (auto-adjusted in InitializeStrategy)
            IbCompressionAtrRatio = 0.40;
            SweepStopTicks = 2;
            MaxRiskAtrFraction = 0.30;
            MiddayStart = 1130;
            PmEnd = 1600;
            UseTwoLegScaling = true;

            // Session: EarliestEntry must be before IB window (09:30) so the IB gets built
            // Actual FVG entry is gated to Midday/PM inside CheckForEntry
            EarliestEntry = 930;
            LatestEntry = 1555;
            FlattenBy = 1555;

            MaxTradesPerDay = 2;
            ConfluenceFilterEnabled = false;  // Override the old Play 3 filter stack — FVG is the real filter

            // Use manual 5m accumulator (not secondary series) — avoids BarsArray[1] indexing issues
            AddSecondaryTimeframe = false;
            BarsRequiredToTrade = 1;

            // Limit orders fill on touch (matches Python limit fill behavior)
            IsFillLimitOnTouch = true;
        }

        protected override void InitializeStrategy()
        {
            base.InitializeStrategy();

            // Auto-adjust FVG size for NQ
            string inst = Instrument?.MasterInstrument?.Name?.ToUpper() ?? "";
            if (inst.Contains("NQ") || inst.Contains("MNQ"))
                MinFvgSize = 3.5;
            else if (inst.Contains("YM") || inst.Contains("MYM"))
                MinFvgSize = 5.0;
            else if (inst.Contains("RTY") || inst.Contains("M2K"))
                MinFvgSize = 1.0;
            else if (inst.Contains("GC") || inst.Contains("MGC"))
                MinFvgSize = 1.0;
            else if (inst.Contains("CL") || inst.Contains("MCL"))
                MinFvgSize = 0.05;

            // Init diagnostic CSV
            string csvPath = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "ibfade_sweep_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsvHeaderWritten = false;
            Print("[DIAG] IBFadeBot CSV path: " + csvPath);

            // Init 5m accumulator
            Reset5mAccumulator();

            currentSweepExtreme = 0;
            sweepSweepDir = 0;
            dailyAtrVal = 0;
            priorDayHigh = priorDayLow = priorDayClose = 0;
            priorDayReady = false;
        }

        protected override void OnSessionOpenReset()
        {
            base.OnSessionOpenReset();
            Reset5mAccumulator();
            currentSweepExtreme = 0;
            sweepSweepDir = 0;

            // Capture prior day OHLC for ATR (will be finalized at first bar of new day)
            // priorDayReady is set when we have enough data
        }

        /// <summary>
        /// Override the IB confluence indicator hook — skip the expensive AVWAP/EMA/FVG
        /// computation when in FVG Sweep Fade mode. We use the 5m secondary series instead.
        /// </summary>
        protected override void UpdateConfluenceIndicatorsHook()
        {
            if (FvgDisplacementRequired)
                return;  // skip — we use BarsArray[1] for FVG detection
            base.UpdateConfluenceIndicatorsHook();
        }

        private void Reset5mAccumulator()
        {
            fvg5mOpen = fvg5mHigh = fvg5mLow = fvg5mClose = 0;
            fvg5mBarCount = 0;
            fvg5mBucketStart = DateTime.MinValue;
            prev5mCount = 0;
            prev5mHigh[0] = prev5mHigh[1] = 0;
            prev5mLow[0] = prev5mLow[1] = 0;
            prev5mOpen[0] = prev5mOpen[1] = 0;
            prev5mClose[0] = prev5mClose[1] = 0;
        }

        /// <summary>
        /// Compute daily ATR from prior day OHLC.
        /// TR = max(H-L, |H-prevClose|, |L-prevClose|), ATR = 10-day SMA of TR.
        /// For simplicity in NT8 1m context, we approximate using prior day's range
        /// as a proxy when full 10-day ATR history is not available.
        /// </summary>
        private void UpdateDailyAtr()
        {
            if (CurrentBar < 1) return;

            DateTime today = Time[0].Date;
            DateTime prevDay = today.AddDays(-1);
            // Find the actual prior trading day by looking back
            if (!priorDayReady)
            {
                // Approximate: use the rolling high/low of the last ~390 bars (1 day)
                int lookback = Math.Min(CurrentBar, 390);
                double h = double.MinValue, l = double.MaxValue, c = 0;
                for (int i = lookback; i >= 1; i--)
                {
                    if (High[i] > h) h = High[i];
                    if (Low[i] < l) l = Low[i];
                    if (i == 1) c = Close[i];
                }
                if (h > double.MinValue && l < double.MaxValue)
                {
                    priorDayHigh = h;
                    priorDayLow = l;
                    priorDayClose = c;
                    dailyAtrVal = h - l;  // Simple proxy: prior day range
                    priorDayReady = true;
                }
            }
            else
            {
                // Update on new day
                if (Time[0].Date != Time[1].Date)
                {
                    priorDayHigh = High[1];
                    priorDayLow = Low[1];
                    priorDayClose = Close[1];
                    // Rolling ATR approximation: 90% old + 10% new TR
                    double newTr = Math.Max(
                        High[0] - Low[0],
                        Math.Max(Math.Abs(High[0] - priorDayClose), Math.Abs(Low[0] - priorDayClose)));
                    dailyAtrVal = dailyAtrVal * 0.9 + newTr * 0.1;
                }
            }
        }

        /// <summary>
        /// Enhanced Play 3 entry: IB Sweep + FVG Displacement.
        ///
        /// Logic (matching Python benchmark_range_regime_fvg.py):
        /// 1. Only scan during Midday/PM (11:30-16:00 ET)
        /// 2. IB must be compressed: rangeRange < IbCompressionAtrRatio × ATR
        /// 3. Build 5m bars from 1m bars
        /// 4. On each 5m bar close (b2), check:
        ///    a. b1 or b2 swept IB High (high > rangeHigh)
        ///    b. b2 closed back inside IB (close < rangeHigh) and bearish (close < open)
        ///    c. Bearish FVG: b0.low - b2.high >= MinFvgSize
        /// 5. Entry = b2.high (FVG edge), Stop = sweep extreme + SweepStopTicks
        /// 6. TP1 = IB mid (50% scale), TP2 = IB low (runner)
        /// </summary>
        protected override int CheckForEntry()
        {
            // TOP-LEVEL DIAG: confirm CheckForEntry is being called
            if (CurrentBar % 500 == 0)
                Print(string.Format("[SWEEP-ENTRY] CheckForEntry called bar={0} time={1:HH:mm} rangeComplete={2} fvgReq={3}",
                    CurrentBar, Time[0], rangeComplete, FvgDisplacementRequired));

            DateTime now = Time[0];
            int timeNum = now.Hour * 10000 + now.Minute * 100 + now.Second;

            // Update daily ATR (wrapped — may throw on early bars)
            try { UpdateDailyAtr(); } catch { /* ignore on warmup */ }

            // Write diagnostic CSV row (wrapped in try/catch — SA context may not have file access)
            try { WriteDiagRow(timeNum); } catch { /* swallow diag errors */ }

            // Must have IB complete
            if (!rangeComplete || rangeRange <= 0)
                return 0;

            // If FVG displacement is NOT required, fall back to original overshoot logic
            // (original overshoot mode trades the full IB session, not just Midday/PM)
            if (!FvgDisplacementRequired)
            {
                return CheckForEntryOvershootOnly();
            }

            // FVG Sweep Fade mode: use manual 5m accumulator (built from 1m bars)
            // This avoids the BarsArray[1] indexing issues with Calculate.OnBarClose
            Accumulate5mBar(now);

            // Only scan for entries during Midday/PM window
            if (timeNum < MiddayStart * 100 || timeNum >= PmEnd * 100)
                return 0;

            // IB Compression Filter: IB range must be < ratio × ATR
            // Skip filter if ATR not yet computed (allow trades when ATR unknown)
            if (dailyAtrVal > 0 && rangeRange >= IbCompressionAtrRatio * dailyAtrVal)
                return 0;

            // FVG Sweep Fade: check for fill of armed signal or new signal
            return CheckForEntryFvgSweepFill(now);
        }

        /// <summary>
        /// Original overshoot-only fade logic (for backward compatibility / comparison).
        /// </summary>
        private int CheckForEntryOvershootOnly()
        {
            DetectOvershoot();

            if (overshootAbove && Close[0] < rangeHigh)
            {
                if (!CanEnterShort) return 0;
                double entry = rangeHigh;
                double stop = rangeHigh + StopRMult * rangeRange;
                double target = rangeHigh - TargetLvl * rangeRange;
                if (!TargetIsSane(entry, target, -1)) { overshootAbove = false; return 0; }
                int qty = CalcQuantity(stop - entry, 1.0);
                EnterWithRangeStop(-1, entry, stop, target, qty);
                overshootAbove = false;
                shortTakenToday = true;
                return -1;
            }

            if (overshootBelow && Close[0] > rangeLow)
            {
                if (!CanEnterLong) return 0;
                double entry = rangeLow;
                double stop = rangeLow - StopRMult * rangeRange;
                double target = rangeLow + TargetLvl * rangeRange;
                if (!TargetIsSane(entry, target, 1)) { overshootBelow = false; return 0; }
                int qty = CalcQuantity(entry - stop, 1.0);
                EnterWithRangeStop(1, entry, stop, target, qty);
                overshootBelow = false;
                longTakenToday = true;
                return 1;
            }

            return 0;
        }

        /// <summary>
        /// FVG Sweep Fade using 5m secondary series (BarsArray[1]).
        /// Checks the 3 most recent CLOSED 5m bars for the sweep+FVG pattern.
        /// b0 = 5m bar [2], b1 = 5m bar [1], b2 = 5m bar [0] (most recent closed)
        /// </summary>
        private int CheckForEntryFvgSweep5m(DateTime now)
        {
            // Use BarsArray[1] for 5m bars — need at least 4 closed bars
            // Index 0 = currently forming 5m bar (incomplete)
            // Index 1 = last closed 5m bar (b2 in our pattern)
            // Index 2 = 5m bar before that (b1)
            // Index 3 = 5m bar before that (b0)
            if (BarsArray[1] == null || CurrentBars[1] < 4)
                return 0;

            double b0High = Highs[1][3];  // 5m bar i-2 (oldest)
            double b0Low = Lows[1][3];
            double b1High = Highs[1][2];  // 5m bar i-1
            double b1Low = Lows[1][2];
            double b2High = Highs[1][1];  // 5m bar i (last closed)
            double b2Low = Lows[1][1];
            double b2Open = Opens[1][1];
            double b2Close = Closes[1][1];

            // SHORT: Sweep IB High + bearish FVG
            bool sweptH = (b1High > rangeHigh || b2High > rangeHigh);
            bool closedInside = (b2Close < rangeHigh) && (b2Close < b2Open);
            bool bearFvg = (b0Low - b2High) >= MinFvgSize;

            if (sweptH && closedInside && bearFvg && CanEnterShort)
            {
                double sweepExt = Math.Max(b1High, b2High);
                double entryPrice = b2High;
                double stopPrice = sweepExt + SweepStopTicks * TickSize;
                double tp1Price = rangeMid;
                double tp2Price = rangeLow;
                double risk = stopPrice - entryPrice;

                if (risk > 0 && risk < MaxRiskAtrFraction * (dailyAtrVal > 0 ? dailyAtrVal : rangeRange * 3) && tp1Price < entryPrice)
                {
                    int qty = CalcQuantity(risk, 1.0);
                    Print(string.Format("[SWEEP-FADE] SHORT entry={0:F2} stop={1:F2} tp1={2:F2} tp2={3:F2} risk={4:F2} at {5:HH:mm}",
                        entryPrice, stopPrice, tp1Price, tp2Price, risk, now));
                    EnterSweepFade(-1, entryPrice, stopPrice, tp1Price, tp2Price, qty);
                    shortTakenToday = true;
                    return -1;
                }
            }

            // LONG: Sweep IB Low + bullish FVG
            bool sweptL = (b1Low < rangeLow || b2Low < rangeLow);
            bool closedInsideL = (b2Close > rangeLow) && (b2Close > b2Open);
            bool bullFvg = (b2Low - b0High) >= MinFvgSize;

            if (sweptL && closedInsideL && bullFvg && CanEnterLong)
            {
                double sweepExt = Math.Min(b1Low, b2Low);
                double entryPrice = b2Low;
                double stopPrice = sweepExt - SweepStopTicks * TickSize;
                double tp1Price = rangeMid;
                double tp2Price = rangeHigh;
                double risk = entryPrice - stopPrice;

                if (risk > 0 && risk < MaxRiskAtrFraction * (dailyAtrVal > 0 ? dailyAtrVal : rangeRange * 3) && tp1Price > entryPrice)
                {
                    int qty = CalcQuantity(risk, 1.0);
                    Print(string.Format("[SWEEP-FADE] LONG entry={0:F2} stop={1:F2} tp1={2:F2} tp2={3:F2} risk={4:F2} at {5:HH:mm}",
                        entryPrice, stopPrice, tp1Price, tp2Price, risk, now));
                    EnterSweepFade(1, entryPrice, stopPrice, tp1Price, tp2Price, qty);
                    longTakenToday = true;
                    return 1;
                }
            }

            return 0;
        }

        /// <summary>
        /// FVG Sweep Fade: check for fill of an armed sweep signal.
        /// The 5m accumulator runs from CheckForEntry (before the time gate).
        /// This method only checks if the current 1m bar fills the limit entry.
        /// </summary>
        private int CheckForEntryFvgSweepFill(DateTime now)
        {
            // If we have a pending sweep signal, check for limit fill
            if (sweepSweepDir == 1 && CanEnterShort)
            {
                // Short: fill when price rallies back up to the FVG edge
                if (High[0] >= armedEntryPrice)
                {
                    double risk = armedStopPrice - armedEntryPrice;
                    int qty = CalcQuantity(risk, 1.0);
                    EnterSweepFade(-1, armedEntryPrice, armedStopPrice, armedTp1Price, armedTp2Price, qty);
                    sweepSweepDir = 0;
                    shortTakenToday = true;
                    return -1;
                }
            }
            else if (sweepSweepDir == -1 && CanEnterLong)
            {
                // Long: fill when price dips back down to the FVG edge
                if (Low[0] <= armedEntryPrice)
                {
                    double risk = armedEntryPrice - armedStopPrice;
                    int qty = CalcQuantity(risk, 1.0);
                    EnterSweepFade(1, armedEntryPrice, armedStopPrice, armedTp1Price, armedTp2Price, qty);
                    sweepSweepDir = 0;
                    longTakenToday = true;
                    return 1;
                }
            }

            return 0;
        }

        /// <summary>
        /// Accumulate 1m bars into 5m buckets and finalize FVG pattern detection.
        /// Accumulation starts at IB completion (10:30) so by Midday (11:30) we have
        /// 12 completed 5m bars for the rolling 3-bar pattern window.
        /// Signal detection only fires during Midday/PM (checked in Finalize5mBarForSweep).
        /// </summary>
        private void Accumulate5mBar(DateTime now)
        {
            int minuteOfDay = now.Hour * 60 + now.Minute;
            int bucketStartMin = (minuteOfDay / 5) * 5;
            DateTime bucketStart = new DateTime(now.Year, now.Month, now.Day, bucketStartMin / 60, bucketStartMin % 60, 0);

            // Start accumulating from IB completion (RangeStart + RangeDuration = 10:00 for 30m IB)
            // so by Midday (11:30) we have 18 completed 5m bars in the rolling window.
            int ibCompleteMin = RangeStartHour * 60 + RangeStartMinute + RangeDurationMin;
            if (minuteOfDay < ibCompleteMin) return;

            // If we moved to a new 5m bucket, finalize the previous one
            if (fvg5mBucketStart != DateTime.MinValue && bucketStart > fvg5mBucketStart)
            {
                Finalize5mBarForSweep();
            }

            // Accumulate this 1m bar into the current 5m bucket
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
        /// Finalize a 5m bar and check for the 3-bar sweep+FVG pattern.
        /// b0 = bar[i-2], b1 = bar[i-1], b2 = bar[i] (just finalized)
        ///
        /// SHORT setup:
        ///   b1.high > IB_High OR b2.high > IB_High  (swept the high)
        ///   b2.close < IB_High AND b2.close < b2.open  (closed back inside, bearish)
        ///   b0.low - b2.high >= MinFvgSize  (bearish FVG displacement)
        ///
        /// LONG setup:
        ///   b1.low < IB_Low OR b2.low < IB_Low  (swept the low)
        ///   b2.close > IB_Low AND b2.close > b2.open  (closed back inside, bullish)
        ///   b2.low - b0.high >= MinFvgSize  (bullish FVG displacement)
        /// </summary>
        private void Finalize5mBarForSweep()
        {
            if (fvg5mBarCount == 0) return;

            // Only arm sweep signals during Midday/PM session
            int timeNum = Time[0].Hour * 100 + Time[0].Minute;
            bool inScanWindow = (timeNum >= MiddayStart && timeNum < PmEnd);

            // Need at least 3 completed 5m bars for the 3-bar pattern
            if (inScanWindow && prev5mCount >= 2 && rangeComplete && rangeRange > 0)
            {
                double b0High = prev5mHigh[0];
                double b0Low = prev5mLow[0];
                double b1High = prev5mHigh[1];
                double b1Low = prev5mLow[1];
                double b2High = fvg5mHigh;
                double b2Low = fvg5mLow;
                double b2Open = fvg5mOpen;
                double b2Close = fvg5mClose;

                // SHORT: Sweep IB High + bearish FVG
                bool sweptH = (b1High > rangeHigh || b2High > rangeHigh);
                bool closedInside = (b2Close < rangeHigh) && (b2Close < b2Open);
                bool bearFvg = (b0Low - b2High) >= MinFvgSize;

                if (sweptH && closedInside && bearFvg && CanEnterShort)
                {
                    currentSweepExtreme = Math.Max(b1High, b2High);
                    armedEntryPrice = b2High;
                    armedStopPrice = currentSweepExtreme + SweepStopTicks * TickSize;
                    armedTp1Price = rangeMid;
                    armedTp2Price = rangeLow;
                    double risk = armedStopPrice - armedEntryPrice;
                    double atrFallback = dailyAtrVal > 0 ? dailyAtrVal : rangeRange * 3;
                    if (risk > 0 && risk < MaxRiskAtrFraction * atrFallback && armedTp1Price < armedEntryPrice)
                    {
                        sweepSweepDir = 1;  // armed for short entry
                        Print(string.Format("[SWEEP-FADE] SHORT armed: entry={0:F2} stop={1:F2} tp1={2:F2} risk={3:F2} at {4:HH:mm}",
                            armedEntryPrice, armedStopPrice, armedTp1Price, risk, Time[0]));
                    }
                }

                // LONG: Sweep IB Low + bullish FVG
                if (sweepSweepDir == 0)  // don't overwrite a short signal
                {
                    bool sweptL = (b1Low < rangeLow || b2Low < rangeLow);
                    bool closedInsideL = (b2Close > rangeLow) && (b2Close > b2Open);
                    bool bullFvg = (b2Low - b0High) >= MinFvgSize;

                    if (sweptL && closedInsideL && bullFvg && CanEnterLong)
                    {
                        currentSweepExtreme = Math.Min(b1Low, b2Low);
                        armedEntryPrice = b2Low;
                        armedStopPrice = currentSweepExtreme - SweepStopTicks * TickSize;
                        armedTp1Price = rangeMid;
                        armedTp2Price = rangeHigh;
                        double risk = armedEntryPrice - armedStopPrice;
                        double atrFallback = dailyAtrVal > 0 ? dailyAtrVal : rangeRange * 3;
                        if (risk > 0 && risk < MaxRiskAtrFraction * atrFallback && armedTp1Price > armedEntryPrice)
                        {
                            sweepSweepDir = -1;  // armed for long entry
                            Print(string.Format("[SWEEP-FADE] LONG armed: entry={0:F2} stop={1:F2} tp1={2:F2} risk={3:F2} at {4:HH:mm}",
                                armedEntryPrice, armedStopPrice, armedTp1Price, risk, Time[0]));
                        }
                    }
                }
            }

            // Shift rolling window: [i-1] -> [i-2], current -> [i-1]
            prev5mHigh[0] = prev5mHigh[1];
            prev5mLow[0] = prev5mLow[1];
            prev5mOpen[0] = prev5mOpen[1];
            prev5mClose[0] = prev5mClose[1];
            prev5mHigh[1] = fvg5mHigh;
            prev5mLow[1] = fvg5mLow;
            prev5mOpen[1] = fvg5mOpen;
            prev5mClose[1] = fvg5mClose;
            if (prev5mCount < 2) prev5mCount++;

            fvg5mBarCount = 0;  // reset for next 5m bucket
        }

        /// <summary>
        /// Enter with 2-leg scaling: 50% at TP1 (IB mid), 50% at TP2 (opposite IB boundary).
        /// Stop moves to breakeven after TP1 hits.
        /// Falls back to single-leg if UseTwoLegScaling is false.
        /// </summary>
        private void EnterSweepFade(int dir, double entry, double stop, double tp1, double tp2, int qty)
        {
            if (!UseTwoLegScaling)
            {
                EnterWithRangeStop(dir, entry, stop, tp2, qty);
                return;
            }

            // 2-leg: split qty in half, each leg has its own TP
            int qtyPerLeg = Math.Max(1, qty / 2);

            // Trade tracking
            entryPrice = entry;
            initialStopPrice = stop;
            currentStopPrice = stop;
            riskPoints = Math.Abs(entry - stop);
            breakevenMoved = false;
            tradeIsActive = true;

            if (dir == 1)
            {
                tradeDirection = "Long";
                entrySignalName = "SweepFadeLong";
                // Limit entry at the FVG edge (matches Python limit fill)
                EnterLongLimit(qtyPerLeg, entry, "SweepFadeLeg1");
                EnterLongLimit(qtyPerLeg, entry, "SweepFadeLeg2");
                SetProfitTarget("SweepFadeLeg1", CalculationMode.Price, tp1);
                SetStopLoss("SweepFadeLeg1", CalculationMode.Price, stop, false);
                SetProfitTarget("SweepFadeLeg2", CalculationMode.Price, tp2);
                SetStopLoss("SweepFadeLeg2", CalculationMode.Price, stop, false);
            }
            else
            {
                tradeDirection = "Short";
                entrySignalName = "SweepFadeShort";
                // Limit entry at the FVG edge (matches Python limit fill)
                EnterShortLimit(qtyPerLeg, entry, "SweepFadeLeg1");
                EnterShortLimit(qtyPerLeg, entry, "SweepFadeLeg2");
                SetProfitTarget("SweepFadeLeg1", CalculationMode.Price, tp1);
                SetStopLoss("SweepFadeLeg1", CalculationMode.Price, stop, false);
                SetProfitTarget("SweepFadeLeg2", CalculationMode.Price, tp2);
                SetStopLoss("SweepFadeLeg2", CalculationMode.Price, stop, false);
            }

            todayTradeCount++;
            Print(string.Format("[SWEEP-FADE] ENTRY {0} @ {1:F2} | Stop {2:F2} | TP1 {3:F2} | TP2 {4:F2} | Qty {5}+{5} | Risk {6:C} | {7:HH:mm}",
                tradeDirection, entry, stop, tp1, tp2, qtyPerLeg, riskPoints * GetPointValue(), Time[0]));
        }

        /// <summary>
        /// Manage the 2-leg trade: move Leg 2 stop to BE when TP1 fills.
        /// </summary>
        protected override void OnExecutionUpdate(
            Execution execution, string executionId,
            double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            base.OnExecutionUpdate(execution, executionId, price, quantity, marketPosition, orderId, time);

            // Check if Leg1 TP1 filled → move Leg2 to breakeven
            if (UseTwoLegScaling && tradeIsActive && !breakevenMoved)
            {
                // If one leg is closed (position reduced), move the other to BE
                if (Position.MarketPosition != MarketPosition.Flat &&
                    Math.Abs(Position.Quantity) < quantity * 2)  // one leg closed
                {
                    breakevenMoved = true;
                    if (tradeDirection == "Long")
                        SetStopLoss("SweepFadeLeg2", CalculationMode.Price, entryPrice, false);
                    else
                        SetStopLoss("SweepFadeLeg2", CalculationMode.Price, entryPrice, false);

                    if (DebugMode)
                        Print(string.Format("[SWEEP-FADE] TP1 filled — Leg2 stop moved to BE @ {0:F2} at {1:HH:mm}", entryPrice, time));
                }
            }
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
        /// IBFadeBot stop geometry: sweep wick + ticks, not a fixed fraction of IB range.
        /// </summary>
        protected override double GetEstimatedRiskDistance()
        {
            if (!rangeComplete || rangeRange <= 0) return 0;
            if (FvgDisplacementRequired)
                return SweepStopTicks * TickSize + rangeRange * 0.1;  // approx: wick beyond IB + small buffer
            return StopRMult * rangeRange;
        }

        protected override string GetStrategyName() => "IB Sweep Fade (Play 3 Enhanced)";

        /// <summary>
        /// Write diagnostic CSV row for every bar — enables bar-by-bar parity comparison
        /// with the Python benchmark_range_regime_fvg.py output.
        /// Columns match the Python TradeResult dataclass + NT8-specific execution fields.
        /// </summary>
        private void WriteDiagRow(int timeNum)
        {
            if (diagCsv == null) return;

            if (!diagCsvHeaderWritten)
            {
                diagCsv.WriteLine("BarTime,BarIdx,Open,High,Low,Close,RangeHigh,RangeLow,RangeRange,RangeMid,RangeComplete,DailyAtr,IbCompressed,InMiddayPM,SweepDir,SweepExtreme,Fvg5mHigh,Fvg5mLow,Fvg5mClose,Prev5mCount,Prev5mH0,Prev5mL0,Prev5mH1,Prev5mL1,CanEnterLong,CanEnterShort,FvgRequired,MinFvgSize,TimeNum");
                diagCsvHeaderWritten = true;
            }

            bool ibCompressed = (dailyAtrVal > 0 && rangeRange < IbCompressionAtrRatio * dailyAtrVal);
            bool inMiddayPm = (timeNum >= MiddayStart * 100 && timeNum < PmEnd * 100);

            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0:yyyy-MM-dd HH:mm:ss},{1},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8:G},{9:G},{10},{11:G},{12},{13},{14},{15:G},{16:G},{17:G},{18:G},{19},{20:G},{21:G},{22:G},{23:G},{24},{25},{26},{27},{28:G},{29}",
                Time[0], CurrentBar,
                Open[0], High[0], Low[0], Close[0],
                rangeHigh, rangeLow, rangeRange, rangeMid,
                rangeComplete ? 1 : 0,
                dailyAtrVal,
                ibCompressed ? 1 : 0,
                inMiddayPm ? 1 : 0,
                sweepSweepDir,
                currentSweepExtreme,
                fvg5mHigh, fvg5mLow, fvg5mClose,
                prev5mCount,
                prev5mHigh[0], prev5mLow[0], prev5mHigh[1], prev5mLow[1],
                CanEnterLong ? 1 : 0, CanEnterShort ? 1 : 0,
                FvgDisplacementRequired ? 1 : 0,
                MinFvgSize,
                timeNum));
            diagCsv.Flush();
        }
    }
}