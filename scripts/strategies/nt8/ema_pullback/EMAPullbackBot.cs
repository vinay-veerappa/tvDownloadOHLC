#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class EMAPullbackBot : RiskManagerBase
    {
        [NinjaScriptProperty]
        [Display(Name = "Min Move From Open (pts)", Order = 1, GroupName = "EMA Pullback")]
        public double MinMoveFromOpen { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pullback Proximity (ATR mult)", Order = 2, GroupName = "EMA Pullback")]
        public double PullbackProximity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "EMA Period", Order = 3, GroupName = "EMA Pullback")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Pullback Bars", Order = 4, GroupName = "EMA Pullback")]
        public int MinPullbackBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Engulfing Confirmation", Order = 5, GroupName = "EMA Pullback")]
        public bool UseEngulfingConfirmation { get; set; }

        // ── VWAP-distance filter ──
        [NinjaScriptProperty]
        [Display(Name = "Use VWAP Distance Filter", Order = 6, GroupName = "EMA Pullback")]
        public bool UseVwapFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "VWAP Min Distance (ATR mult)", Order = 7, GroupName = "EMA Pullback")]
        public double VwapMinDistanceAtr { get; set; }

        // ── Relative-volume filter ──
        [NinjaScriptProperty]
        [Display(Name = "Use Relative Volume Filter", Order = 8, GroupName = "EMA Pullback")]
        public bool UseVolumeFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Volume Lookback (bars)", Order = 9, GroupName = "EMA Pullback")]
        public int VolumeLookback { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Volume Percentile Threshold", Order = 10, GroupName = "EMA Pullback")]
        public double VolumePercentile { get; set; }

        private EMA emaIndicator;
        private VWAP8 vwapIndicator;

        private DateTime sessionDate;
        private double sessionOpen;
        private double sessionHigh;
        private double sessionLow;

        private bool initialMoveDetected;
        private int moveDirection;
        private int pullbackBars;

        private DateTime lastSignalDate;

        protected override string GetStrategyName()
        {
            return "EMAPullback";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "EMA pullback continuation strategy with centralized risk manager";
            Name = "EMAPullbackBot";

            // Trade management defaults tuned to Python backtest harness
            StopAtrMult = 1.25;
            AtrPeriod = 14;
            TradePolicy = "FixedTarget";
            TargetRMultiple = 3.0;
            BreakevenTriggerR = 1.0;
            TrailAtrMult = 2.0;

            // Risk/session defaults
            DailyMaxLoss = 400;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 945;
            LatestEntry = 1100;
            FlattenBy = 1545;

            // Signal defaults tuned to Python harness (NQ 5m)
            MinMoveFromOpen = 2.0;
            PullbackProximity = 0.3;
            EmaPeriod = 20;
            MinPullbackBars = 2;
            UseEngulfingConfirmation = true;

            // Filter defaults tuned to Python harness
            UseVwapFilter = true;
            VwapMinDistanceAtr = 0.33;
            UseVolumeFilter = true;
            VolumeLookback = 20;
            VolumePercentile = 27.0;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            emaIndicator = EMA(BarsArray[1], EmaPeriod);
            if (UseVwapFilter)
                vwapIndicator = VWAP8();

            sessionDate = DateTime.MinValue;
            sessionOpen = 0;
            sessionHigh = double.MinValue;
            sessionLow = double.MaxValue;
            initialMoveDetected = false;
            moveDirection = 0;
            pullbackBars = 0;
            lastSignalDate = DateTime.MinValue;
        }

        protected override int CheckForSignal()
        {
            DateTime barDate = Times[0][0].Date;
            int barTime = ToTime(Times[0][0]);

            if (barDate != sessionDate && barTime >= 93000)
            {
                sessionDate = barDate;
                sessionOpen = Opens[0][0];
                sessionHigh = Highs[0][0];
                sessionLow = Lows[0][0];
                initialMoveDetected = false;
                moveDirection = 0;
                pullbackBars = 0;
            }

            if (sessionOpen == 0)
                return 0;

            if (Highs[0][0] > sessionHigh)
                sessionHigh = Highs[0][0];

            if (Lows[0][0] < sessionLow)
                sessionLow = Lows[0][0];

            if (lastSignalDate == barDate)
                return 0;

            double atr = GetCurrentATR();
            if (atr <= 0)
                return 0;

            if (!initialMoveDetected)
            {
                if (sessionHigh - sessionOpen >= MinMoveFromOpen)
                {
                    initialMoveDetected = true;
                    moveDirection = 1;
                }
                else if (sessionOpen - sessionLow >= MinMoveFromOpen)
                {
                    initialMoveDetected = true;
                    moveDirection = -1;
                }

                return 0;
            }

            double close = Closes[0][0];
            double ema = emaIndicator[0];
            double distanceToEma = Math.Abs(close - ema);
            bool nearEma = distanceToEma <= PullbackProximity * atr;

            if (!nearEma)
            {
                pullbackBars = 0;
                return 0;
            }

            pullbackBars++;
            if (pullbackBars < MinPullbackBars)
                return 0;

            bool bullishBar = Closes[0][0] > Opens[0][0];
            bool bearishBar = Closes[0][0] < Opens[0][0];
            bool bullishEngulf = Closes[0][0] > Opens[0][1] && Opens[0][0] <= Closes[0][1];
            bool bearishEngulf = Closes[0][0] < Opens[0][1] && Opens[0][0] >= Closes[0][1];

            bool longConfirm = UseEngulfingConfirmation ? bullishEngulf : bullishBar;
            bool shortConfirm = UseEngulfingConfirmation ? bearishEngulf : bearishBar;

            int signal = 0;
            if (moveDirection == 1 && longConfirm)
                signal = 1;
            else if (moveDirection == -1 && shortConfirm)
                signal = -1;

            if (signal == 0)
                return 0;

            // ── VWAP distance filter ──
            if (UseVwapFilter && vwapIndicator != null)
            {
                double vwap = vwapIndicator.PlotVWAP[0];
                if (vwap > 0 && Math.Abs(close - vwap) / atr < VwapMinDistanceAtr)
                    return 0;
            }

            // ── Relative volume filter ──
            if (UseVolumeFilter && CurrentBar > 0)
            {
                double threshold = VolumePercentileForBar(VolumeLookback, VolumePercentile);
                if (Volume[0] < threshold)
                    return 0;
            }

            lastSignalDate = barDate;
            return signal;
        }

        /// <summary>
        /// Computes the requested percentile of the prior N bars' volume.
        /// Uses a simple nearest-rank percentile to avoid LINQ/ordering overhead.
        /// </summary>
        private double VolumePercentileForBar(int lookback, double percentile)
        {
            int start = Math.Max(0, CurrentBar - lookback);
            int count = CurrentBar - start;
            if (count <= 0)
                return Volume[0];

            double[] values = new double[count];
            for (int i = 0; i < count; i++)
                values[i] = Volume[i + 1]; // skip current bar

            Array.Sort(values);
            double rank = (percentile / 100.0) * (count - 1);
            int lower = (int)Math.Floor(rank);
            int upper = (int)Math.Ceiling(rank);
            if (lower == upper)
                return values[lower];
            double weight = rank - lower;
            return values[lower] * (1.0 - weight) + values[upper] * weight;
        }
    }
}
