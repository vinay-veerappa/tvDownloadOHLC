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
        [NinjaScriptProperty]
        [Display(Name = "Use VWAP Distance Filter", Order = 6, GroupName = "EMA Pullback")]
        public bool UseVwapFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "VWAP Min Distance (ATR mult)", Order = 7, GroupName = "EMA Pullback")]
        public double VwapMinDistanceAtr { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Relative Volume Filter", Order = 8, GroupName = "EMA Pullback")]
        public bool UseVolumeFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Volume Percentile Threshold", Order = 9, GroupName = "EMA Pullback")]
        public double VolumePercentile { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Volume Lookback (bars)", Order = 10, GroupName = "EMA Pullback")]
        public int VolumeLookback { get; set; }


        private EMA emaIndicator;

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

            StopAtrMult = 1.25;
            AtrPeriod = 14;
            TradePolicy = "FixedTarget";
            TargetRMultiple = 3.75;
            BreakevenTriggerR = 1.0;
            TrailAtrMult = 2.0;

            DailyMaxLoss = 400;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 945;
            LatestEntry = 1100;
            FlattenBy = 1545;

            MinMoveFromOpen = 4.0;
            PullbackProximity = 0.3;
            EmaPeriod = 20;
            MinPullbackBars = 2;
            UseEngulfingConfirmation = true;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            emaIndicator = EMA(BarsArray[1], EmaPeriod);

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

            if (moveDirection == 1 && longConfirm)
            {
                lastSignalDate = barDate;
                return 1;
            }

            if (moveDirection == -1 && shortConfirm)
            {
                lastSignalDate = barDate;
                return -1;
            }

            return 0;
        }
    }
}
