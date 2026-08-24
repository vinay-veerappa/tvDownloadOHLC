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
    /// STTrendBot — Supertrend intraday trend-following bot. Run on a 5-MINUTE chart (primary = 5m,
    /// so every signal/stop reads CLOSED 5m bars exactly like the Python sim supertrend_intraday_cost.py).
    ///
    /// Python validation (19mo ES 5m, 1x MES $5/pt $1.20/rt 1-tick slip):
    ///   ST(14,2) trail 1.5xATR: 762 trades, WR 38.7%, PF 1.50, Net +$1889, DD $179, 40/mo ES
    ///
    /// Confluence: trailing stop ratcheted on the bar High/Low (not close), NO range gate, NO fixed targets.
    ///   - Entry: 5m Supertrend(period,mult) flip on closed bar
    ///   - Exit: stop = max(stop, High - trail*ATR) long / min(stop, Low + trail*ATR) short, or 16:00 flatten
    ///
    /// ⚠️ Do NOT run on a 1m chart with a 5m secondary — the forming-5m-bar repaint causes whipsaw
    /// (measured PF0.556). Must be 5m primary.
    /// </summary>
    public class STTrendBot : RiskManagerBase
    {
        #region Parameters

        [NinjaScriptProperty]
        [Range(2, 30)]
        [Display(Name = "ST Period", Order = 1, GroupName = "Supertrend")]
        public int StPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name = "ST ATR Mult", Order = 2, GroupName = "Supertrend")]
        public double StAtrMult { get; set; }

        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name = "Trail ATR Mult", Order = 3, GroupName = "Supertrend")]
        public double TrailAtrMultParam { get; set; }

        #endregion

        private Indicators.Vinay.SupertrendIndicator stIndicator;
        private ATR atr;
        private MAX maxHigh;
        private MIN minLow;
        private const int TRAIL_ATR_PERIOD = 14;

        private System.IO.StreamWriter diagCsv;
        private bool diagCsvHeaderWritten;

        protected override string GetStrategyName() => "STTrend";

        protected override void SetStrategyDefaults()
        {
            Description = "Supertrend intraday trend-following — 5m primary, trailing stop on High/Low, no range gate. Python PF1.50 ST(14,2) trail1.5.";
            Name = "STTrendBot";

            StopAtrMult = 1.5;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.SupertrendTrail;  // ratchet from entry -/+ trail*ATR on bar High/Low
            BreakevenTriggerR = 0.0;
            TrailAtrMult = 1.5;

            // RISK GATES DISABLED for Python-parity validation (Python sim has none).
            DailyMaxLoss = 99999;
            MaxConsecutiveLosers = 99;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 99;
            MaxTradesPerDay = 99;
            TrailingDrawdown = 99999;

            // Full day — trend-following needs trend days, NO range gate
            EarliestEntry = 930;
            LatestEntry = 1555;
            FlattenBy = 1555;

            // MUST be 5m primary, no secondary — closed bars only
            AddSecondaryTimeframe = false;
            DebugMode = true;

            StPeriod = 14;
            StAtrMult = 2.0;
            TrailAtrMultParam = 1.5;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            stIndicator = SupertrendIndicator(StPeriod, StAtrMult);
            atr = ATR(BarsArray[0], 14);
            maxHigh = MAX(High, TRAIL_ATR_PERIOD);
            minLow = MIN(Low, TRAIL_ATR_PERIOD);

            string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "sttrend_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Strategy=STTrendBot StPeriod={0} StAtrMult={1} TrailAtrMult={2} AtrPeriod={3} Primary=5m Risk=1xMES", StPeriod, StAtrMult, TrailAtrMultParam, AtrPeriod));
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Execution: Earliest={0} Latest={1} FlattenBy={2} MaxTradesPerDay={3} DailyMaxLoss={4} TrailingDD={5}", EarliestEntry, LatestEntry, FlattenBy, MaxTradesPerDay, DailyMaxLoss, TrailingDrawdown));
            diagCsvHeaderWritten = false;
            Print("[DIAG] STTrendBot CSV path: " + csvPath);
        }

        private double GetTrailAtr()
        {
            if (maxHigh == null || minLow == null || CurrentBars[0] < TRAIL_ATR_PERIOD) return 0;
            double diff = maxHigh[0] - minLow[0];
            return diff / TRAIL_ATR_PERIOD;
        }

        protected override double GetPotentialLoss()
        {
            double a = GetCurrentATR();
            if (a <= 0) a = 15.0;
            return a * TrailAtrMultParam * GetPointValue();
        }

        // Primary = 5m, so ATR is on the 5m primary itself (no secondary).
        protected override double GetCurrentATR()
        {
            // Return the crude (MAX-MIN)/14 ATR for the trail — Python parity.
            double trailAtr = GetTrailAtr();
            if (trailAtr > 0) return trailAtr;
            if (atr == null || CurrentBars[0] < AtrPeriod) return 0;
            return atr[0];
        }

        protected override int CheckForSignal()
        {
            if (stIndicator == null || CurrentBars[0] < StPeriod + 2) return 0;
            return stIndicator.SignalSeries[0];
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (atr == null || CurrentBars[0] < AtrPeriod) return double.NaN;
            double a = atr[0];
            if (a <= 0) return double.NaN;
            return signal == 1 ? entryPrice - TrailAtrMultParam * a : entryPrice + TrailAtrMultParam * a;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            return double.NaN; // no fixed target — trailing stop only
        }
    }
}
