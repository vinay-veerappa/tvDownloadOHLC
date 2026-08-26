#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
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

        [NinjaScriptProperty]
        [Display(Name = "Use ATR Regime Filter", Order = 4, GroupName = "Supertrend")]
        public bool UseAtrRegimeFilter { get; set; }

        #endregion

        private Indicators.Vinay.SupertrendIndicator stIndicator;
        private ATR atr;
        private const int TRAIL_ATR_PERIOD = 14;
        private double[] atr5mHistory;
        private int atr5mHistoryCount;
        private const int ATR_REGIME_LOOKBACK = 20;

        // Per-day rolling high/low for crude ATR (Python parity: fresh per-day)
        private double[] dayHighs;
        private double[] dayLows;
        private int dayBarCount;
        private DateTime currentDay;

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
            // Time filter: skip 14:00+ (afternoon chop whipsaws trailing stop)
            // Python: if h >= 14: continue (so 13:xx is OK, 14:00+ is skipped)
            // LatestEntry=1555 means "last allowed entry at 15:55" but we want
            // to skip 14:00+, so LatestEntry should be 1359 (last 13:xx bar).
            // Actually the time fence in RiskManagerBase checks currentTime > LatestEntry*100
            // where currentTime = hour*100 + minute. So 1359 → 135900. 14:00 → 140000 > 135900 → blocked. ✓
            // But we also want to ALLOW entries from 09:30-13:59. So LatestEntry=1359 is correct.
            // However, Python's time_filter also blocks 14:00+ but allows 09:30-13:59.
            // The mismatch is that NT8 also has FlattenBy=1555 which flattens at 15:55.
            // Python doesn't flatten at 15:55 — it exits at EOD (16:00 close).
            // For parity, set FlattenBy=1555 (ADR-020 requires 16:00 ET exit).
            EarliestEntry = 930;
            LatestEntry = 1359;  // skip 14:00+ (time filter — afternoon chop)
            FlattenBy = 1555;

            // MUST be 5m primary, no secondary — closed bars only
            AddSecondaryTimeframe = false;
            DebugMode = true;

            StPeriod = 14;
            StAtrMult = 2.0;
            TrailAtrMultParam = 1.0;  // tighter trail (was 1.5) — captures MFE before reversion
            UseAtrRegimeFilter = true;  // only trade when 5m ATR > 20-bar median
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            stIndicator = SupertrendIndicator(StPeriod, StAtrMult);
            atr = ATR(BarsArray[0], 14);
            atr5mHistory = new double[ATR_REGIME_LOOKBACK];
            atr5mHistoryCount = 0;
            dayHighs = new double[TRAIL_ATR_PERIOD];
            dayLows = new double[TRAIL_ATR_PERIOD];
            dayBarCount = 0;
            currentDay = DateTime.MinValue;

            string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "sttrend_diag_" + Guid.NewGuid().ToString("N") + ".csv");
            diagCsv = new System.IO.StreamWriter(csvPath);
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Strategy=STTrendBot StPeriod={0} StAtrMult={1} TrailAtrMult={2} AtrPeriod={3} Primary=5m Risk=1xMES AtrRegimeFilter={4} LatestEntry={5}", StPeriod, StAtrMult, TrailAtrMultParam, AtrPeriod, UseAtrRegimeFilter, LatestEntry));
            diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture, "# Execution: Earliest={0} Latest={1} FlattenBy={2} MaxTradesPerDay={3} DailyMaxLoss={4} TrailingDD={5}", EarliestEntry, LatestEntry, FlattenBy, MaxTradesPerDay, DailyMaxLoss, TrailingDrawdown));
            diagCsvHeaderWritten = false;
            Print("[DIAG] STTrendBot CSV path: " + csvPath);
        }

        private double GetTrailAtr()
        {
            if (CurrentBars[0] < 1) return 0;

            // Detect new day — reset per-day buffers (Python parity: fresh per-day)
            if (Time[0].Date != currentDay)
            {
                currentDay = Time[0].Date;
                dayBarCount = 0;
            }

            // Store this bar's high/low in the per-day rolling buffer
            dayHighs[dayBarCount % TRAIL_ATR_PERIOD] = High[0];
            dayLows[dayBarCount % TRAIL_ATR_PERIOD] = Low[0];
            dayBarCount++;

            if (dayBarCount < 2) return 0;

            // Compute MAX(High, min(dayBarCount, 14)) and MIN(Low, min(dayBarCount, 14))
            int lookback = Math.Min(dayBarCount, TRAIL_ATR_PERIOD);
            double maxH = double.MinValue;
            double minL = double.MaxValue;
            for (int i = 0; i < lookback; i++)
            {
                int idx = (dayBarCount - lookback + i) % TRAIL_ATR_PERIOD;
                if (dayHighs[idx] > maxH) maxH = dayHighs[idx];
                if (dayLows[idx] < minL) minL = dayLows[idx];
            }

            if (maxH == double.MinValue || minL == double.MaxValue) return 0;
            return (maxH - minL) / TRAIL_ATR_PERIOD;
        }

        private bool PassesAtrRegimeFilter()
        {
            if (!UseAtrRegimeFilter) return true;
            // Compute crude (MAX-MIN)/14 ATR for this bar (per-day, Python parity)
            double currentAtr5m = GetTrailAtr();
            if (currentAtr5m <= 0) return false;

            // Reset ATR regime buffer at start of each new day too
            if (CurrentBar > 0 && Time[0].Date != Time[1].Date)
            {
                atr5mHistoryCount = 0;
            }

            // Store in rolling buffer
            atr5mHistory[atr5mHistoryCount % ATR_REGIME_LOOKBACK] = currentAtr5m;
            atr5mHistoryCount++;

            if (atr5mHistoryCount < 5) return true;  // min_periods=5 (Python parity)

            // Compute median of the available history (up to ATR_REGIME_LOOKBACK bars)
            int count = Math.Min(atr5mHistoryCount, ATR_REGIME_LOOKBACK);
            double[] sorted = new double[count];
            for (int i = 0; i < count; i++)
                sorted[i] = atr5mHistory[(atr5mHistoryCount - count + i) % ATR_REGIME_LOOKBACK];
            Array.Sort(sorted);
            double median = sorted[count / 2];

            // Only trade when current ATR >= median (high-vol regime)
            return currentAtr5m >= median;
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

            // ATR regime filter: only trade in high-vol regimes
            if (!PassesAtrRegimeFilter()) return 0;

            if (DrawVisuals && CurrentBars[0] > StPeriod + 2)
            {
                double stCurr = stIndicator.SupertrendValue[0];
                double stPrev = stIndicator.SupertrendValue[1];
                int dir = stIndicator.TrendDirection[0];
                Brush lineBrush = dir == 1 ? Brushes.LimeGreen : Brushes.OrangeRed;
                Draw.Line(this, "ST_Line_" + CurrentBar, false, 1, stPrev, 0, stCurr, lineBrush, DashStyleHelper.Solid, 2);
            }

            int sig = stIndicator.SignalSeries[0];
            if (sig != 0 && DrawVisuals)
            {
                string tag = "ST_Flip_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                    Draw.Text(this, tag + "_Txt", false, "ST BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.OrangeRed);
                    Draw.Text(this, tag + "_Txt", false, "ST SELL", 0, High[0] + (10 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            return sig;
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
