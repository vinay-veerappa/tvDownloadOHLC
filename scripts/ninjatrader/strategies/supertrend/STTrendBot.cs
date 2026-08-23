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
    /// STTrendBot — Supertrend intraday trend-following bot.
    /// Python validation (supertrend_intraday_cost.py, 19mo ES 5m, 1x MES $5/pt $1.20/rt 1-tick slip):
    ///   ST(14,2) trail 1.5xATR: 762 trades, WR 38.7%, PF 1.50, Net +$1889, DD $179, 40/mo ES
    ///
    /// Confluence (from research): trailing stop, NOT flip/fixed targets, NO range gate.
    ///   - Entry: 5m Supertrend(period,mult) flip
    ///   - Exit: trailing stop at trail_mult x ATR (ratcheted), or opposite flip, or 16:00 flatten
    ///   - RiskManagerBase BreakevenTrail with BreakevenTriggerR=0 (move to BE immediately) + TrailAtrMult=1.5
    ///     approximates the Python trailing stop (initial buffer differs slightly — documented).
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

        private ATR atr5;
        private double stUpper, stLower, stValue;
        private double prevStValue;
        private bool stInit;

        private System.IO.StreamWriter diagCsv;
        private bool diagCsvHeaderWritten;

        protected override string GetStrategyName() => "STTrend";

        protected override void SetStrategyDefaults()
        {
            Description = "Supertrend intraday trend-following — trailing stop, no range gate. Python PF1.50 ST(14,2) trail1.5.";
            Name = "STTrendBot";

            StopAtrMult = 1.5;
            AtrPeriod = 14;
            TradePolicy = "SupertrendTrail";  // ratchet from entry -/+ trail*ATR, never jump to BE
            BreakevenTriggerR = 0.0;
            TrailAtrMult = 1.5;

            DailyMaxLoss = 400;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 6;
            TrailingDrawdown = 2000;

            // Full day — trend-following needs trend days, NO range gate
            EarliestEntry = 930;
            LatestEntry = 1555;
            FlattenBy = 1555;

            AddSecondaryTimeframe = true; // 5m for ST
            DebugMode = true;

            StPeriod = 14;
            StAtrMult = 2.0;
            TrailAtrMultParam = 1.5;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            atr5 = ATR(BarsArray[1], 14);
            stUpper = stLower = stValue = 0;
            prevStValue = 0;
            stInit = false;

            string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "sttrend_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Strategy=STTrendBot StPeriod={0} StAtrMult={1} TrailAtrMult={2} StopAtrMult={3} AtrPeriod={4} EntryMode=limit Risk=1xMES", StPeriod, StAtrMult, TrailAtrMultParam, StopAtrMult, AtrPeriod));
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Execution: Earliest={0} Latest={1} FlattenBy={2} MaxTradesPerDay={3} DailyMaxLoss={4} TrailingDD={5}", EarliestEntry, LatestEntry, FlattenBy, MaxTradesPerDay, DailyMaxLoss, TrailingDrawdown));
            diagCsvHeaderWritten = false;
            Print("[DIAG] STTrendBot CSV path: " + csvPath);
        }

        protected override double GetCurrentATR()
        {
            if (atr5 == null || CurrentBars[1] < AtrPeriod) return 0;
            return atr5[0];
        }

        /// <summary>
        /// Update Supertrend on 5m secondary. Seban: median + mult*ATR, upper can't rise, lower can't fall.
        /// </summary>
        private void UpdateSupertrend()
        {
            if (CurrentBars[1] < StPeriod + 2) return;
            double hl2 = (Highs[1][0] + Lows[1][0]) / 2.0;
            double atr = atr5[0];
            if (atr <= 0) return;

            double upper = hl2 + StAtrMult * atr;
            double lower = hl2 - StAtrMult * atr;

            // final bands: upper can't rise, lower can't fall
            if (stInit)
            {
                if (upper > stUpper) upper = stUpper;
                if (lower < stLower) lower = stLower;
            }

            double close = Closes[1][0];
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
            if (CurrentBars[1] < StPeriod + 2 || !stInit) return 0;

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
            if (CurrentBars[1] < 2) return;
            if (!diagCsvHeaderWritten)
            {
                diagCsv.WriteLine("BarTime,BarIdx,Close0,StUpper,StLower,StValue,PrevStValue,Atr5,LongFlip,ShortFlip,Signal");
                diagCsvHeaderWritten = true;
            }
            double close0 = Closes[1][0];
            double atr = atr5 != null ? atr5[0] : 0;
            bool longFlip = stValue == 1 && prevStValue == -1;
            bool shortFlip = stValue == -1 && prevStValue == 1;
            int sig = longFlip ? 1 : (shortFlip ? -1 : 0);
            var bt = Times[1][0];
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0:yyyy-MM-dd HH:mm:ss},{1},{2:G},{3:G},{4:G},{5:G},{6:G},{7:G},{8},{9},{10}",
                bt, CurrentBars[1], close0, stUpper, stLower, stValue, prevStValue, atr,
                longFlip ? 1 : 0, shortFlip ? 1 : 0, sig));
            diagCsv.Flush();
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (atr5 == null || CurrentBars[1] < AtrPeriod) return double.NaN;
            double atr = atr5[0];
            if (atr <= 0) return double.NaN;
            // initial stop: entry -/+ trail_mult*ATR (Python parity)
            return signal == 1 ? entryPrice - TrailAtrMultParam * atr : entryPrice + TrailAtrMultParam * atr;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            return double.NaN; // no fixed target — trailing stop only
        }
    }
}
