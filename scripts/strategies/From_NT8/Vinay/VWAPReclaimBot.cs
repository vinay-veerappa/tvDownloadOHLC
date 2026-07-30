#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
using NinjaTrader.NinjaScript.Strategies.Vinay;

using System.IO;


#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class VWAPReclaimBot : RiskManagerBase
    {
        [NinjaScriptProperty]
        [Display(Name = "Confirmation Bars", Order = 1, GroupName = "VWAP Reclaim")]
        public int ConfirmationBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Bars Away From VWAP", Order = 2, GroupName = "VWAP Reclaim")]
        public int MinPriorBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signal Cooldown Bars", Order = 3, GroupName = "VWAP Reclaim")]
        public int CooldownBars { get; set; }

        private double cumTypicalPriceVolume;
        private double cumVolume;
        private double currentVWAP;
        private DateTime vwapSessionDate;

        private int consecutiveClosesAbove;
        private int consecutiveClosesBelow;
        private int priorBelowStreak;
        private int priorAboveStreak;

        private long lastLongSignalBar;
        private long lastShortSignalBar;

        protected override string GetStrategyName()
        {
            return "VWAPReclaim";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "VWAP Reclaim/Rejection strategy with centralized risk manager";
            Name = "VWAPReclaimBot";

            StopAtrMult = 2.0;
            AtrPeriod = 14;
            TradePolicy = "BreakevenTrail";
            BreakevenTriggerR = 2.0;
            TrailAtrMult = 3.5;

            DailyMaxLoss = 400;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 930;
            LatestEntry = 1430;
            FlattenBy = 1545;

            ConfirmationBars = 2;
            MinPriorBars   = 2;
            CooldownBars = 15;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            cumTypicalPriceVolume = 0;
            cumVolume = 0;
            currentVWAP = 0;
            vwapSessionDate = DateTime.MinValue;

            consecutiveClosesAbove = 0;
            consecutiveClosesBelow = 0;
            priorBelowStreak = 0;
            priorAboveStreak = 0;
            lastLongSignalBar = -100000;
            lastShortSignalBar = -100000;
        }

        protected override int CheckForSignal()
        {
			
	
            UpdateVWAP();
			
		
            if (GetCurrentATR() <= 0)
                return 0;

            double close = Closes[0][0];
            bool isAbove = close > currentVWAP;
            bool isBelow = close < currentVWAP;

            if (isAbove)
            {
                if (consecutiveClosesBelow > 0)
                    priorBelowStreak = consecutiveClosesBelow;

                consecutiveClosesAbove++;
                consecutiveClosesBelow = 0;
            }
            else if (isBelow)
            {
                if (consecutiveClosesAbove > 0)
                    priorAboveStreak = consecutiveClosesAbove;

                consecutiveClosesBelow++;
                consecutiveClosesAbove = 0;
            }
			int currentBar = CurrentBars[0];

            bool longInCooldown   = currentBar - lastLongSignalBar < CooldownBars;
			bool shortInCooldown  = currentBar - lastShortSignalBar < CooldownBars;
			

            
            if (consecutiveClosesAbove == ConfirmationBars
                && priorBelowStreak >= MinPriorBars 
                && !longInCooldown  )
            {
                lastLongSignalBar = currentBar;
                priorBelowStreak = 0;
                return 1;
            }

            
            if (consecutiveClosesBelow == ConfirmationBars
                && priorAboveStreak >= MinPriorBars 
                && !shortInCooldown )
            {
                lastShortSignalBar = currentBar;
                priorAboveStreak = 0;
                return -1;
            }

            return 0;
        }

        private void UpdateVWAP()
        {
            DateTime barDate = Times[0][0].Date;
            int barTime = ToTime(Times[0][0]);

            if (barDate != vwapSessionDate && barTime >= 93000)
            {
                cumTypicalPriceVolume = 0;
                cumVolume = 0;
                vwapSessionDate = barDate;
            }

            double typicalPrice = (Highs[0][0] + Lows[0][0] + Closes[0][0]) / 3.0;
            double volume = Volumes[0][0];

            cumTypicalPriceVolume += typicalPrice * volume;
            cumVolume += volume;

            currentVWAP = cumVolume > 0
                ? cumTypicalPriceVolume / cumVolume
                : Closes[0][0];
        }
    }
}
