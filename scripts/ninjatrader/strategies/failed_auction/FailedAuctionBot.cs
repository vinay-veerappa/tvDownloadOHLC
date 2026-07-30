#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.NinjaScript;
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

        private struct SinglePrintLevel
        {
            public double OriginPrice;
            public double TargetPrice;
            public int Direction;
            public int CreatedBar;
            public bool Filled;
        }

        private List<SinglePrintLevel> activeLevels;
        private DateTime levelsSessionDate;

        protected override string GetStrategyName()
        {
            return "FailedAuction";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Failed auction single-print fill strategy with centralized risk manager";
            Name = "FailedAuctionBot";

            StopAtrMult = 3.5;
            AtrPeriod = 14;
            TradePolicy = "BreakevenTrail";
            BreakevenTriggerR = 0.5;
            TrailAtrMult = 1.0;

            DailyMaxLoss = 400;
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
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            activeLevels = new List<SinglePrintLevel>();
            levelsSessionDate = DateTime.MinValue;
        }

        protected override int CheckForSignal()
        {
            DateTime barDate = Times[0][0].Date;
            if (barDate != levelsSessionDate)
            {
                activeLevels.Clear();
                levelsSessionDate = barDate;
            }

            double atr = GetCurrentATR();
            if (atr <= 0)
                return 0;

            int currentBar = CurrentBars[0];
            double close = Closes[0][0];

            if (currentBar >= FastMoveBars)
            {
                double origin = Closes[0][FastMoveBars];
                double move = close - origin;
                if (Math.Abs(move) >= FastMoveMinPoints)
                {
                    bool tooClose = false;
                    for (int i = 0; i < activeLevels.Count; i++)
                    {
                        if (!activeLevels[i].Filled
                            && Math.Abs(activeLevels[i].OriginPrice - origin) < atr)
                        {
                            tooClose = true;
                            break;
                        }
                    }

                    if (!tooClose)
                    {
                        activeLevels.Add(new SinglePrintLevel
                        {
                            OriginPrice = origin,
                            TargetPrice = close,
                            Direction = move > 0 ? 1 : -1,
                            CreatedBar = currentBar,
                            Filled = false
                        });
                    }
                }
            }

            for (int i = activeLevels.Count - 1; i >= 0; i--)
            {
                SinglePrintLevel level = activeLevels[i];

                if (level.Filled)
                    continue;

                if (currentBar - level.CreatedBar > MaxWaitBars)
                {
                    level.Filled = true;
                    activeLevels[i] = level;
                    continue;
                }

                double distToOrigin = Math.Abs(close - level.OriginPrice);
                if (distToOrigin <= EntryProximity * atr)
                {
                    level.Filled = true;
                    activeLevels[i] = level;

                    // Counter-direction fill
                    return level.Direction == -1 ? 1 : -1;
                }
            }

            return 0;
        }
    }
}
