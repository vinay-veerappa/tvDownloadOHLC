#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// BBMRReversionBot — BB(20,2) + RSI(14) mean-reversion bot.
    /// Clean port of From_NT8/BB1.cs core (HAClose re-enter + 2-bar hook) but using Close + RSI + ADX gate
    /// so it retains prop frequency. P1 in range_strategy_comparison.py.
    ///
    /// Logic (5m, NY 11:30-16:00):
    ///   Long: close[1] < lower[1] && RSI[1] < 33  &&  close[0] > lower[0] && RSI[0] > RSI[1] && close[0] < middle[0] && RSI[0] < 50
    ///   Short: mirror upper / RSI>67
    ///   Filter: ADX(14) < AdxThreshold (25) — skip trending regime. Optional SqueezeOnly (BW percentile).
    ///   Stop: band ± 1.5× 5m ATR (mirrors python 1.5*atr5m). Target: middle → opposite band.
    /// </summary>
    public class BBMRReversionBot : RiskManagerBase
    {
        #region Parameters

        [NinjaScriptProperty]
        [Range(5, 50)]
        [Display(Name = "BB Period", Order = 1, GroupName = "BB+RSI")]
        public int BBPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.5, 3.0)]
        [Display(Name = "BB Std Dev", Order = 2, GroupName = "BB+RSI")]
        public double StdDev { get; set; }

        [NinjaScriptProperty]
        [Range(2, 30)]
        [Display(Name = "RSI Period", Order = 3, GroupName = "BB+RSI")]
        public int RsiPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(10, 40)]
        [Display(Name = "ADX Threshold", Order = 4, GroupName = "BB+RSI")]
        public double AdxThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use ADX Gate", Order = 5, GroupName = "BB+RSI")]
        public bool UseAdxGate { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Squeeze Only (30% narrow BW)", Order = 6, GroupName = "BB+RSI")]
        public bool SqueezeOnly { get; set; }

        [NinjaScriptProperty]
        [Range(10, 50)]
        [Display(Name = "Squeeze Lookback", Order = 7, GroupName = "BB+RSI")]
        public int SqueezeLookback { get; set; }

        [NinjaScriptProperty]
        [Range(10, 60)]
        [Display(Name = "Squeeze Pct (narrowest %)", Order = 8, GroupName = "BB+RSI")]
        public double SqueezePct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use IB Compress Gate (<0.4 ATR)", Order = 9, GroupName = "BB+RSI")]
        public bool UseIbCompress { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 1.0)]
        [Display(Name = "IB Max ATR Ratio", Order = 10, GroupName = "BB+RSI")]
        public double IbMaxAtrRatio { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Skip Lunch 13-14 ET", Order = 11, GroupName = "BB+RSI")]
        public bool SkipLunchHour { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use MACD Hist Gate", Order = 12, GroupName = "BB+RSI")]
        public bool UseMacdGate { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Kaufman ER RSI", Order = 13, GroupName = "BB+RSI")]
        public bool UseKaufmanErRsi { get; set; }

        [NinjaScriptProperty]
        [Range(5, 30)]
        [Display(Name = "Kaufman ER Period", Order = 14, GroupName = "BB+RSI")]
        public int ErPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(3, 15)]
        [Display(Name = "Kaufman Fast Len", Order = 15, GroupName = "BB+RSI")]
        public int KaufmanFastLen { get; set; }

        [NinjaScriptProperty]
        [Range(20, 50)]
        [Display(Name = "Kaufman Slow Len", Order = 16, GroupName = "BB+RSI")]
        public int KaufmanSlowLen { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow 2-Bar Hook", Order = 17, GroupName = "BB+RSI")]
        public bool Allow2BarHook { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "SHORT Only (drop LONG)", Order = 18, GroupName = "BB+RSI")]
        public bool ShortOnly { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Proximity Filter", Order = 19, GroupName = "BB+RSI")]
        public bool UseHtfProximity { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "HTF Proximity (pts)", Order = 20, GroupName = "BB+RSI")]
        public double HtfProximityPts { get; set; }

        #endregion

        private Bollinger bollinger;
        private RSI rsi;
        private RSI rsiKaufman;  // dynamic-period RSI for Kaufman ER mode
        private ADX adx;
        private ATR atr5;
        private MACD macd;

        // Kaufman ER RSI state
        private double[] erValues;  // rolling efficiency ratio
        private double[] closeHistory;  // rolling close for ER computation
        private int erHistoryCount;
        private double[] dynamicRsiGain;
        private double[] dynamicRsiLoss;
        private double prevDynamicRsi;
        private int last5mBarIdx;  // track 5m bar index changes (not timestamp)
        private double rsi1Saved;  // properly saved rsi1 from prior 5m bar

        // 2-bar hook state
        private double rsi2barsAgo;
        private double close2barsAgo;
        private double lower2barsAgo;
        private double upper2barsAgo;

        // HTF levels (Prior Day High/Low)
        private double pdh = double.NaN;
        private double pdl = double.NaN;
        private DateTime htfDate;

        // IB tracking for regime gate (09:30-10:00)
        private double ibHigh, ibLow;
        private bool ibComplete;
        private DateTime ibDate;

        private System.IO.StreamWriter diagCsv;
        private bool diagCsvHeaderWritten;

        protected override string GetStrategyName() => "BBMRReversion";

        protected override void SetStrategyDefaults()
        {
            Description = "BB(20,2)+RSI(14) mean reversion — clean BB1 port. Squeeze gate optional. Prop-frequency tuned.";
            Name = "BBMRReversionBot";

            // Risk — DISABLED for Python-parity validation (Python sim has none)
            StopAtrMult = 1.5;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.FixedTP1TP2;  // Python parity: TP1=BB mid, TP2=opp band
            BreakevenTriggerR = 1.0;
            TrailAtrMult = 1.0;

            DailyMaxLoss = 99999;
            MaxConsecutiveLosers = 99;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 99;
            MaxTradesPerDay = 99;
            TrailingDrawdown = 99999;

            // Time — NY_PM only (matches Python v3: 13:30-16:00)
            EarliestEntry = 1330;
            LatestEntry = 1600;
            // FlattenBy was 1615, PAST the ADR-020 hard exit of 16:00 (close of
            // the 15:59 bar). A prop account can be liquidated for holding an
            // intraday position past it, so this is a safety limit and not a
            // tuning choice. The NY_PM intent above is unchanged.
            // See TradingDefaults.RthHardExit.
            FlattenBy = 1600;

            AddSecondaryTimeframe = true; // 5m for BB/RSI/ADX
            DebugMode = true;

            BBPeriod = 20;
            StdDev = 2.0;
            RsiPeriod = 14;
            AdxThreshold = 25;
            UseAdxGate = true;
            SqueezeOnly = false;
            SqueezeLookback = 20;
            SqueezePct = 30;
            UseIbCompress = false;
            IbMaxAtrRatio = 0.40;
            SkipLunchHour = false;
            UseMacdGate = false;
            UseKaufmanErRsi = false;  // v3: Wilder RSI (not Kaufman ER)
            ErPeriod = 10;
            KaufmanFastLen = 5;
            KaufmanSlowLen = 30;
            Allow2BarHook = true;  // 2-bar hook: doubles trades while maintaining PF
            ShortOnly = false;

            // HTF proximity filter (v3: require entry within 15pts of PDH/PDL)
            UseHtfProximity = true;
            HtfProximityPts = 15.0;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            bollinger = Bollinger(Closes[1], StdDev, BBPeriod);
            rsi = RSI(Closes[1], RsiPeriod, 3);
            adx = ADX(BarsArray[1], 14);
            atr5 = ATR(BarsArray[1], 14);
            macd = MACD(Closes[1], 12, 26, 9);
            AddChartIndicator(bollinger);

            // Kaufman ER RSI state — buffer must be large enough for the slowest RSI period
            int bufSize = Math.Max(ErPeriod, KaufmanSlowLen) + 2;
            erValues = new double[ErPeriod + 1];
            closeHistory = new double[bufSize];
            erHistoryCount = 0;
            dynamicRsiGain = new double[1];
            dynamicRsiLoss = new double[1];
            prevDynamicRsi = 50.0;
            rsi1Saved = 50.0;
            last5mBarIdx = -1;
            rsi2barsAgo = close2barsAgo = lower2barsAgo = upper2barsAgo = 0;

            string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "bbmr_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Strategy=BBMRReversionBot BBPeriod={0} StdDev={1} RsiPeriod={2} AdxThr={3} UseAdx={4} SqueezeOnly={5} UseIbCompress={6} IbMaxAtrRatio={7} SkipLunch={8} UseMacdGate={9} UseKaufmanErRsi={10} Allow2BarHook={11} ShortOnly={12} ErPeriod={13} FastLen={14} SlowLen={15}", BBPeriod, StdDev, RsiPeriod, AdxThreshold, UseAdxGate, SqueezeOnly, UseIbCompress, IbMaxAtrRatio, SkipLunchHour, UseMacdGate, UseKaufmanErRsi, Allow2BarHook, ShortOnly, ErPeriod, KaufmanFastLen, KaufmanSlowLen));
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Execution: Earliest={0} Latest={1} FlattenBy={2} MaxTradesPerDay={3} DailyMaxLoss={4} TrailingDD={5}", EarliestEntry, LatestEntry, FlattenBy, MaxTradesPerDay, DailyMaxLoss, TrailingDrawdown));
            diagCsvHeaderWritten = false;
            Print("[DIAG] BBMRReversionBot CSV path: " + csvPath);
            Print(String.Format("[DIAG] Params UseKaufman={0} 2BarHook={1} ShortOnly={2}", UseKaufmanErRsi, Allow2BarHook, ShortOnly));
            ibHigh = ibLow = 0; ibComplete = false; ibDate = DateTime.MinValue;
        }

        /// <summary>
        /// Compute Kaufman Efficiency Ratio and return a dynamic-period RSI value.
        /// ER = |close[t] - close[t-er_period]| / sum(|close[i]-close[i-1]|, er_period)
        /// Period interpolates between FastLen (ER=1, trending) and SlowLen (ER=0, choppy).
        /// Only updates when a new 5m bar closes (detected via CurrentBars[1] change).
        /// </summary>
        private double ComputeKaufmanErRsi()
        {
            if (CurrentBars[1] < ErPeriod + 2) return 50.0;

            int bufSize = Math.Max(ErPeriod, KaufmanSlowLen) + 2;

            // Only update on new 5m bar close — detect via bar index change
            int current5mBar = CurrentBars[1];
            if (current5mBar == last5mBarIdx)
            {
                // Same 5m bar — return the last computed value
                return prevDynamicRsi;
            }

            // Save the prior bar's RSI as rsi1 before computing new one
            rsi1Saved = prevDynamicRsi;

            // New 5m bar — update the close history
            last5mBarIdx = current5mBar;
            closeHistory[erHistoryCount % bufSize] = Closes[1][0];
            erHistoryCount++;

            if (erHistoryCount < ErPeriod + 1)
            {
                prevDynamicRsi = 50.0;
                return prevDynamicRsi;
            }

            // Get closes from ErPeriod bars ago and now
            int idxNow = erHistoryCount % bufSize;
            int idxThen = (erHistoryCount - ErPeriod) % bufSize;
            double closeNow = closeHistory[idxNow];
            double closeThen = closeHistory[idxThen];

            // Change = |close_now - close_er_period_ago|
            double change = Math.Abs(closeNow - closeThen);

            // Volatility = sum of |close[i] - close[i-1]| over ErPeriod bars
            double volatility = 0;
            for (int i = 0; i < ErPeriod; i++)
            {
                int idxI = (erHistoryCount - i) % bufSize;
                int idxI1 = (erHistoryCount - i - 1) % bufSize;
                // Handle negative modulo in C#
                if (idxI < 0) idxI += bufSize;
                if (idxI1 < 0) idxI1 += bufSize;
                volatility += Math.Abs(closeHistory[idxI] - closeHistory[idxI1]);
            }

            if (volatility <= 0)
            {
                return prevDynamicRsi;
            }

            double er = change / volatility;
            er = Math.Max(0, Math.Min(1, er));

            // Dynamic period: interpolate between slow (ER=0) and fast (ER=1)
            int period = (int)(KaufmanSlowLen + (KaufmanFastLen - KaufmanSlowLen) * er);
            period = Math.Max(2, Math.Min(50, period));

            // Compute Wilder RSI over the dynamic period using the close history
            if (erHistoryCount < period + 1)
            {
                return prevDynamicRsi;
            }

            double avgGain = 0, avgLoss = 0;
            for (int i = erHistoryCount - period; i < erHistoryCount; i++)
            {
                int idxI = i % bufSize;
                int idxI1 = (i - 1) % bufSize;
                if (idxI < 0) idxI += bufSize;
                if (idxI1 < 0) idxI1 += bufSize;
                double diff = closeHistory[idxI] - closeHistory[idxI1];
                if (diff > 0) avgGain += diff;
                else avgLoss += -diff;
            }
            avgGain /= period;
            avgLoss /= period;

            double rsiVal;
            if (avgLoss == 0) rsiVal = 100.0;
            else if (avgGain == 0) rsiVal = 0.0;
            else rsiVal = 100.0 - 100.0 / (1.0 + avgGain / avgLoss);

            prevDynamicRsi = rsiVal;
            return rsiVal;
        }

        protected override double GetCurrentATR()
        {
            if (atr5 == null || CurrentBars[1] < AtrPeriod) return 0;
            return atr5[0];
        }

        private bool IsSqueeze()
        {
            if (CurrentBars[1] < BBPeriod + SqueezeLookback) return false;
            // Compute BW percentile on 5m
            int lookback = Math.Min(SqueezeLookback, CurrentBars[1]);
            double curUpper = bollinger.Upper[0];
            double curLower = bollinger.Lower[0];
            double curMid = bollinger.Middle[0];
            if (curMid == 0) return false;
            double curBW = (curUpper - curLower) / curMid;

            int narrowCount = 0;
            for (int i = 0; i < lookback; i++)
            {
                double up = bollinger.Upper[i];
                double lo = bollinger.Lower[i];
                double mid = bollinger.Middle[i];
                if (mid == 0) continue;
                double bw = (up - lo) / mid;
                if (bw <= curBW) narrowCount++;
            }
            double pct = 100.0 * narrowCount / lookback;
            return pct <= SqueezePct;
        }

        protected override int CheckForSignal()
        {
            // IB tracking on primary 1m (09:30-10:00)
            try { UpdateIb(); } catch { }
            try { WriteDiagRow(); } catch { }
            if (CurrentBars[1] < BBPeriod + 5) return 0;
            if (SqueezeOnly && !IsSqueeze()) return 0;
            // IB compress gate
            if (UseIbCompress && ibComplete)
            {
                double ibRange = ibHigh - ibLow;
                double dailyAtrProxy = atr5 != null && CurrentBars[1] >= 14 ? atr5[0] * 17.0 : 70.0; // 5m ATR * ~17 ≈ daily
                if (ibRange >= IbMaxAtrRatio * dailyAtrProxy) return 0;
            }
            // Lunch skip
            if (SkipLunchHour && Times[1][0].Hour == 13) return 0;

            double close0 = Closes[1][0];
            double close1 = Closes[1][1];
            double upper0 = bollinger.Upper[0];
            double lower0 = bollinger.Lower[0];
            double upper1 = bollinger.Upper[1];
            double lower1 = bollinger.Lower[1];
            double mid0 = bollinger.Middle[0];

            // RSI: use Kaufman ER RSI or Wilder RSI
            double rsi0, rsi1;
            if (UseKaufmanErRsi)
            {
                rsi0 = ComputeKaufmanErRsi();
                rsi1 = rsi1Saved;  // properly saved from prior 5m bar
            }
            else
            {
                rsi0 = rsi[0];
                rsi1 = rsi[1];
            }

            double adx0 = adx[0];

            if (UseAdxGate && adx0 >= AdxThreshold) return 0;

            // RSI thresholds — use 33/67 for both Wilder and Kaufman
            double rsiOsThreshold = 33;
            double rsiObThreshold = 67;

            // 1-bar hook (standard)
            bool longTouch1 = close1 < lower1 && rsi1 < rsiOsThreshold;
            bool shortTouch1 = close1 > upper1 && rsi1 > rsiObThreshold;

            // 2-bar hook: touch was 2 bars ago, hook back on current bar
            bool longTouch2 = false, shortTouch2 = false;
            if (Allow2BarHook && CurrentBars[1] >= 3)
            {
                // Use stored values from 2 bars ago (updated at end of each bar)
                // For the first call, these are 0, so the check will fail safely.
                longTouch2 = close2barsAgo < lower2barsAgo && rsi2barsAgo < rsiOsThreshold
                          && close1 > lower1 && rsi1 > rsi2barsAgo;
                shortTouch2 = close2barsAgo > upper2barsAgo && rsi2barsAgo > rsiObThreshold
                           && close1 < upper1 && rsi1 < rsi2barsAgo;
            }

            bool longSetup = (longTouch1 || longTouch2)
                          && close0 > lower0 && rsi0 > rsi1
                          && close0 < mid0 && rsi0 < 50;

            bool shortSetup = (shortTouch1 || shortTouch2)
                           && close0 < upper0 && rsi0 < rsi1
                           && close0 > mid0 && rsi0 > 50;

            // SHORT-only filter
            if (ShortOnly) longSetup = false;

            // HTF proximity filter (v3): require entry near PDH (for SHORT) or PDL (for LONG)
            if (UseHtfProximity)
            {
                UpdateHtfLevels();
                if (longSetup && !double.IsNaN(pdl))
                {
                    if (Math.Abs(close0 - pdl) > HtfProximityPts) longSetup = false;
                }
                if (shortSetup && !double.IsNaN(pdh))
                {
                    if (Math.Abs(close0 - pdh) > HtfProximityPts) shortSetup = false;
                }
            }

            if (longSetup)
            {
                if (UseMacdGate && macd != null && macd.Diff[0] <= macd.Diff[1]) return 0;
                return 1;
            }

            if (shortSetup)
            {
                if (UseMacdGate && macd != null && macd.Diff[0] >= macd.Diff[1]) return 0;
                return -1;
            }

            // Store 2-bars-ago values for next bar's 2-bar hook check
            rsi2barsAgo = rsi1;
            close2barsAgo = close1;
            lower2barsAgo = lower1;
            upper2barsAgo = upper1;

            return 0;
        }

        private void UpdateHtfLevels()
        {
            // Compute PDH/PDL from the prior day's RTH bars (09:30-16:00 ET)
            var today = Times[0][0].Date;
            if (htfDate == today) return;  // already computed for this day

            try
            {
                // Use BarsArray[0] (1m primary) to find prior day's high/low
                var priorDate = today.AddDays(-1);
                // Skip weekends
                while (priorDate.DayOfWeek == DayOfWeek.Saturday || priorDate.DayOfWeek == DayOfWeek.Sunday)
                    priorDate = priorDate.AddDays(-1);

                double dayHigh = double.MinValue;
                double dayLow = double.MaxValue;
                bool found = false;

                for (int i = 0; i < BarsArray[0].Count && i < 5000; i++)
                {
                    var barTime = Times[0][i];
                    if (barTime.Date == priorDate && barTime.Hour >= 9 && barTime.Hour < 16)
                    {
                        dayHigh = Math.Max(dayHigh, Highs[0][i]);
                        dayLow = Math.Min(dayLow, Lows[0][i]);
                        found = true;
                    }
                }

                if (found)
                {
                    pdh = dayHigh;
                    pdl = dayLow;
                    htfDate = today;
                }
            }
            catch { }
        }

        private void UpdateIb()
        {
            var now = Times[0][0];
            if (now.Date != ibDate)
            {
                ibHigh = double.MinValue; ibLow = double.MaxValue; ibComplete = false; ibDate = now.Date;
            }
            int hm = now.Hour * 100 + now.Minute;
            if (hm >= 930 && hm < 1000)
            {
                if (High[0] > ibHigh) ibHigh = High[0];
                if (Low[0] < ibLow) ibLow = Low[0];
            }
            else if (hm >= 1000 && !ibComplete)
            {
                ibComplete = true;
            }
        }

        private void WriteDiagRow()
        {
            if (diagCsv == null) return;
            if (CurrentBars[1] < 2) return;
            if (!diagCsvHeaderWritten)
            {
                diagCsv.WriteLine("BarTime,BarIdx,Close0,Close1,Upper0,Lower0,Upper1,Lower1,Mid0,Rsi0,Rsi1,Adx0,Atr5,IsSqueeze,AdxGatePass,LongSetup,ShortSetup,Signal,IbHigh,IbLow,IbComplete,SkipLunch");
                diagCsvHeaderWritten = true;
            }
            double close0 = Closes[1][0];
            double close1 = Closes[1][1];
            double upper0 = bollinger.Upper[0];
            double lower0 = bollinger.Lower[0];
            double upper1 = bollinger.Upper[1];
            double lower1 = bollinger.Lower[1];
            double mid0 = bollinger.Middle[0];
            double rsi0 = rsi[0];
            double rsi1 = rsi[1];
            double adx0 = adx[0];
            double atr = atr5 != null ? atr5[0] : 0;
            bool isSq = IsSqueeze();
            bool adxPass = !UseAdxGate || adx0 < AdxThreshold;
            bool longSetup = close1 < lower1 && rsi1 < 33 && close0 > lower0 && rsi0 > rsi1 && close0 < mid0 && rsi0 < 50;
            bool shortSetup = close1 > upper1 && rsi1 > 67 && close0 < upper0 && rsi0 < rsi1 && close0 > mid0 && rsi0 > 50;
            int sig = 0;
            bool lunchSkip = SkipLunchHour && Times[1][0].Hour == 13;
            bool ibPass = !UseIbCompress || !ibComplete || (ibHigh - ibLow) < IbMaxAtrRatio * (atr * 17.0);
            if (adxPass && (!SqueezeOnly || isSq) && !lunchSkip && ibPass)
            {
                if (longSetup) sig = 1;
                else if (shortSetup) sig = -1;
            }
            var bt = Times[1][0];
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0:yyyy-MM-dd HH:mm:ss},{1},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8:G},{9:G},{10:G},{11:G},{12:G},{13},{14},{15},{16},{17},{18:G},{19:G},{20},{21}",
                bt, CurrentBars[1], close0, close1, upper0, lower0, upper1, lower1, mid0, rsi0, rsi1, adx0, atr,
                isSq ? 1 : 0, adxPass ? 1 : 0, longSetup ? 1 : 0, shortSetup ? 1 : 0, sig, ibHigh, ibLow, ibComplete ? 1 : 0, lunchSkip ? 1 : 0));
            diagCsv.Flush();
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (atr5 == null || CurrentBars[1] < AtrPeriod) return double.NaN;
            double atr = atr5[0];
            if (atr <= 0) return double.NaN;
            double mid = bollinger.Middle[0];
            double lower = bollinger.Lower[0];
            double upper = bollinger.Upper[0];
            double close = Closes[1][0];
            if (signal == 1)
            {
                double bandStop = Math.Min(lower, close) - 1.5 * atr;
                double minStop = entryPrice - 1.0 * atr;
                return Math.Min(bandStop, minStop);
            }
            else
            {
                double bandStop = Math.Max(upper, close) + 1.5 * atr;
                double minStop = entryPrice + 1.0 * atr;
                return Math.Max(bandStop, minStop);
            }
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            // TP1 = BB middle band (matches Python)
            double mid = bollinger.Middle[0];
            return mid;
        }

        protected override double GetCustomTP2(int signal, double entryPrice)
        {
            // TP2 = opposite BB band (matches Python)
            if (signal == 1)
                return bollinger.Upper[0];  // LONG runner target = upper band
            else
                return bollinger.Lower[0];  // SHORT runner target = lower band
        }

        // diag flush is per-bar; no OnTermination needed — file closed on process exit
    }
}
