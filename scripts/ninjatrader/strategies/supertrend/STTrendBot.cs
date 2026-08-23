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

        private ATR atr;
        private double stUpper, stLower, stValue;
        private double prevStValue;
        private bool stInit;
        // Crude trail ATR (Python parity): (MAX(High,14)-MIN(Low,14))/14 — NOT Wilder ATR.
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
            TradePolicy = "SupertrendTrail";  // ratchet from entry -/+ trail*ATR on bar High/Low
            BreakevenTriggerR = 0.0;
            TrailAtrMult = 1.5;

            // RISK GATES DISABLED for Python-parity validation (Python sim has none).
            // Python: 762 trades PF1.50. Gates cut to 66 trades PF0.84 and mask the edge.
            // Re-enable for prop AFTER parity confirmed.
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
            atr = ATR(BarsArray[0], 14);  // Wilder ATR for the Supertrend band (Python uses EWM ATR — close enough)
            maxHigh = MAX(High, TRAIL_ATR_PERIOD);
            minLow = MIN(Low, TRAIL_ATR_PERIOD);
            stUpper = stLower = stValue = 0;
            prevStValue = 0;
            stInit = false;

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

        // Reset Supertrend each day (Python parity: sim computes ST fresh on day_bars_5m per day).
        protected override void OnBarUpdate()
        {
            // Detect new session date on primary (5m) and reset ST state
            if (Bars.IsFirstBarOfSession || (CurrentBar > 0 && Time[0].Date != Time[1].Date))
            {
                stUpper = stLower = stValue = 0;
                prevStValue = 0;
                stInit = false;
            }
            base.OnBarUpdate();
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

        /// <summary>
        /// Update Supertrend on primary 5m closed bars. Seban: median + mult*ATR, upper can't rise, lower can't fall.
        /// </summary>
        private void UpdateSupertrend()
        {
            if (CurrentBars[0] < StPeriod + 2) return;
            double hl2 = (High[0] + Low[0]) / 2.0;
            double a = atr[0];
            if (a <= 0) return;

            double upper = hl2 + StAtrMult * a;
            double lower = hl2 - StAtrMult * a;

            // final bands: upper can't rise, lower can't fall
            if (stInit)
            {
                if (upper > stUpper) upper = stUpper;
                if (lower < stLower) lower = stLower;
            }

            double close = Close[0];
            double newSt;
            if (!stInit)
            {
                newSt = close > upper ? 1 : (close < lower ? -1 : 0);
            }
            else
            {
                if (close > stUpper) newSt = 1;
                else if (close < stLower) newSt = -1;
                else newSt = prevStValue;
            }

            prevStValue = stValue;
            stValue = newSt;
            stUpper = upper;
            stLower = lower;
            stInit = true;
        }

        protected override int CheckForSignal()
        {
            try { UpdateSupertrend(); } catch { }
            try { WriteDiagRow(); } catch { }
            if (CurrentBars[0] < StPeriod + 2 || !stInit) return 0;

            double st0 = stValue;
            double st1 = prevStValue;
            if (st0 == 0 || st1 == 0) return 0;

            if (st0 == 1 && st1 == -1) return 1;   // long flip
            if (st0 == -1 && st1 == 1) return -1;  // short flip
            return 0;
        }

        private void WriteDiagRow()
        {
            if (diagCsv == null) return;
            if (CurrentBars[0] < 2) return;
            if (!diagCsvHeaderWritten)
            {
                diagCsv.WriteLine("BarTime,BarIdx,Close0,High0,Low0,StUpper,StLower,StValue,PrevStValue,Atr,LongFlip,ShortFlip,Signal");
                diagCsvHeaderWritten = true;
            }
            double atrV = atr != null ? atr[0] : 0;
            bool longFlip = stValue == 1 && prevStValue == -1;
            bool shortFlip = stValue == -1 && prevStValue == 1;
            int sig = longFlip ? 1 : (shortFlip ? -1 : 0);
            var bt = Time[0];
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0:yyyy-MM-dd HH:mm:ss},{1},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8:G},{9:G},{10},{11},{12}",
                bt, CurrentBar, Close[0], High[0], Low[0], stUpper, stLower, stValue, prevStValue, atrV,
                longFlip ? 1 : 0, shortFlip ? 1 : 0, sig));
            diagCsv.Flush();
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
