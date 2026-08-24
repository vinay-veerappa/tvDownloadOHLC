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

        private Indicators.Vinay.VWAPReclaimIndicator vwapIndicator;

        protected override string GetStrategyName() => "VWAPReclaim";

        protected override void SetStrategyDefaults()
        {
            Description = "VWAP Reclaim/Rejection strategy consuming VWAPReclaimIndicator with centralized risk manager";
            Name = "VWAPReclaimBot";

            StopAtrMult = 2.0;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.CoverTheQueen;
            BreakevenTriggerR = 2.0;
            TrailAtrMult = 3.5;

            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 930;
            LatestEntry = 1430;
            FlattenBy = 1545;

            ConfirmationBars = 2;
            MinPriorBars = 2;
            CooldownBars = 15;

            AddSecondaryTimeframe = false;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            vwapIndicator = VWAPReclaimIndicator(ConfirmationBars, MinPriorBars, CooldownBars);
        }

        protected override int CheckForSignal()
        {
            if (vwapIndicator == null || CurrentBar < 10) return 0;
            return vwapIndicator.SignalSeries[0];
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (vwapIndicator == null || CurrentBar < 10) return double.NaN;
            double sl = vwapIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}
