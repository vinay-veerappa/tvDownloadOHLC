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

        #endregion

        private Bollinger bollinger;
        private RSI rsi;
        private ADX adx;
        private ATR atr5;
        private MACD macd;

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

            // Risk — tight for prop, use base defaults but widen time window to midday/PM
            StopAtrMult = 1.5;
            AtrPeriod = 14;
            TradePolicy = "BreakevenTrail";
            BreakevenTriggerR = 1.0;
            TrailAtrMult = 1.0;

            DailyMaxLoss = 400;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 4;
            TrailingDrawdown = 2000;

            // Time — NY midday/PM only (matches python NY_MIDDAY+NY_PM 11:30-16:00)
            EarliestEntry = 1130;
            LatestEntry = 1600;
            FlattenBy = 1615;

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
            // DIAG built-in by default — params logged as # header for parity verification
            string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "bbmr_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Strategy=BBMRReversionBot BBPeriod={0} StdDev={1} RsiPeriod={2} AdxThr={3} UseAdx={4} SqueezeOnly={5} SqueezeLookback={6} SqueezePct={7} UseIbCompress={8} IbMaxAtrRatio={9} SkipLunch={10} UseMacdGate={11} StopAtrMult={12} AtrPeriod={13} EntryMode=limit Risk=4xMES", BBPeriod, StdDev, RsiPeriod, AdxThreshold, UseAdxGate, SqueezeOnly, SqueezeLookback, SqueezePct, UseIbCompress, IbMaxAtrRatio, SkipLunchHour, UseMacdGate, StopAtrMult, AtrPeriod));
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Execution: Earliest={0} Latest={1} FlattenBy={2} MaxTradesPerDay={3} DailyMaxLoss={4} TrailingDD={5}", EarliestEntry, LatestEntry, FlattenBy, MaxTradesPerDay, DailyMaxLoss, TrailingDrawdown));
            diagCsvHeaderWritten = false;
            Print("[DIAG] BBMRReversionBot CSV path: " + csvPath);
            Print(String.Format("[DIAG] Params BBPeriod={0} StdDev={1} AdxThr={2} UseMacd={3} UseIb={4} SkipLunch={5}", BBPeriod, StdDev, AdxThreshold, UseMacdGate, UseIbCompress, SkipLunchHour));
            ibHigh = ibLow = 0; ibComplete = false; ibDate = DateTime.MinValue;
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
            double rsi0 = rsi[0];
            double rsi1 = rsi[1];
            double adx0 = adx[0];

            if (UseAdxGate && adx0 >= AdxThreshold) return 0;

            bool longSetup = close1 < lower1 && rsi1 < 33
                          && close0 > lower0 && rsi0 > rsi1
                          && close0 < mid0 && rsi0 < 50;
            if (longSetup)
            {
                if (UseMacdGate && macd != null && macd.Diff[0] <= macd.Diff[1]) return 0;
                return 1;
            }

            bool shortSetup = close1 > upper1 && rsi1 > 67
                           && close0 < upper0 && rsi0 < rsi1
                           && close0 > mid0 && rsi0 > 50;
            if (shortSetup)
            {
                if (UseMacdGate && macd != null && macd.Diff[0] >= macd.Diff[1]) return 0;
                return -1;
            }

            return 0;
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
            double mid = bollinger.Middle[0];
            return mid;
        }

        // diag flush is per-bar; no OnTermination needed — file closed on process exit
    }
}
