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
    public class FailedAuctionBot : RiskManagerBase
    {
        [NinjaScriptProperty]
        [Display(Name = "Fast Move Min Points", Order = 1, GroupName = "Failed Auction")]
        public double FastMoveMinPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fast Move Bars (1-min)", Order = 2, GroupName = "Failed Auction")]
        public int FastMoveBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Wait Bars For Fill", Order = 3, GroupName = "Failed Auction")]
        public int MaxWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Proximity (ATR mult)", Order = 4, GroupName = "Failed Auction")]
        public double EntryProximity { get; set; }

        private Indicators.Vinay.FailedAuctionIndicator faIndicator;

        protected override string GetStrategyName() => "FailedAuction";

        protected override void SetStrategyDefaults()
        {
            Description = "Failed auction single-print fill strategy consuming FailedAuctionIndicator with centralized risk manager";
            Name = "FailedAuctionBot";

            StopAtrMult = 3.5;
            AtrPeriod = 14;
            TradePolicy = TradePolicyType.CoverTheQueen;
            BreakevenTriggerR = 0.5;
            TrailAtrMult = 1.0;

            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 3;
            EarliestEntry = 930;
            LatestEntry = 1430;
            FlattenBy = 1545;

            FastMoveMinPoints = 20.0;
            FastMoveBars = 10;
            MaxWaitBars = 120;
            EntryProximity = 0.3;

            AddSecondaryTimeframe = false;
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            faIndicator = FailedAuctionIndicator(FastMoveMinPoints, FastMoveBars, MaxWaitBars, EntryProximity);
        }

        protected override int CheckForSignal()
        {
            if (faIndicator == null || CurrentBar < FastMoveBars + 2) return 0;
            return faIndicator.SignalSeries[0];
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (faIndicator == null || CurrentBar < FastMoveBars + 2) return double.NaN;
            double sl = faIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}
