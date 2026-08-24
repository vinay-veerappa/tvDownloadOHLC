#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
using NinjaTrader.NinjaScript.Indicators.TheStrat;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// Strat22RevStratBot - Automated 2-2 Reversal and RevStrat Momentum Trap Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM order execution.
    ///
    /// Logic:
    ///   - Bullish: Bar[1] == 2D -> Bar[0] crosses above High[1] -> Enter Long, SL @ Low[1] - 1 tick, TP @ High[2]
    ///   - Bearish: Bar[1] == 2U -> Bar[0] crosses below Low[1] -> Enter Short, SL @ High[1] + 1 tick, TP @ Low[2]
    /// </summary>
    public class Strat22RevStratBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Require Actionable Wick (Hammer/Shooter)", Description = "Only take 2-2 reversals if setup bar formed an actionable wick", Order = 1, GroupName = "The Strat")]
        public bool RequireActionableWick { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use FTFC Filter", Description = "Only trade in direction of Full Time Frame Continuity", Order = 2, GroupName = "The Strat")]
        public bool UseFTFCFilter { get; set; }

        [NinjaScriptProperty]
        [Range(1, 4)]
        [Display(Name = "Min FTFC Score", Description = "Minimum agreeing timeframes required", Order = 3, GroupName = "The Strat")]
        public int MinFTFCScore { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min R:R Ratio", Description = "Minimum Reward to Risk ratio to accept setup", Order = 4, GroupName = "The Strat")]
        public double MinRewardRiskRatio { get; set; }
        #endregion

        private TheStratClassifier stratClassifier;
        private TheStratFTFCHud ftfcHud;

        protected override string GetStrategyName()
        {
            return "Strat22Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-2 Reversal and RevStrat trap strategy with centralized RiskManagerBase";
            Name = "Strat22RevStratBot";

            // Strat Parameters
            RequireActionableWick = false;
            UseFTFCFilter = true;
            MinFTFCScore = 2;
            MinRewardRiskRatio = 1.0;

            // RiskManagerBase Defaults
            DailyMaxLoss = 500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 4;
            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            // Brackets
            TradePolicy = "FixedTarget";
            TargetRMultiple = 2.0;
            BreakevenTriggerR = 1.0;
            AtrPeriod = 14;
            StopAtrMult = 1.5;
        }

        protected override void OnStrategyStateChange(State state)
        {
            if (state == State.DataLoaded)
            {
                stratClassifier = TheStratClassifier(true, true, 0.65, 4);
                if (UseFTFCFilter)
                {
                    ftfcHud = TheStratFTFCHud(false, NinjaTrader.Gui.Chart.TextPosition.TopRight, 10);
                }
            }
        }

        protected override void OnBarUpdate()
        {
            base.OnBarUpdate();

            if (CurrentBar < 2 || Position.MarketPosition != MarketPosition.Flat)
                return;

            int prev1Strat = stratClassifier.StratTypeSeries[1]; // Bar[1]
            int prev1Wick = stratClassifier.ActionableWickSeries[1]; // 1 = Hammer, -1 = Shooter

            int ftfcScore = ftfcHud != null ? ftfcHud.FTFCScore : 0;

            // ----------------------------------------------------
            // 1. Bullish 2-2 Reversal: Bar[1] is 2D -> Enter Long if price breaks High[1]
            // ----------------------------------------------------
            if (prev1Strat == 22)
            {
                if (!RequireActionableWick || prev1Wick == 1)
                {
                    if (!UseFTFCFilter || ftfcScore >= MinFTFCScore)
                    {
                        double entryPrice = High[1] + TickSize;
                        double stopPrice = Low[1] - TickSize;
                        double targetPrice = High[2]; // Magnitude 1

                        double risk = entryPrice - stopPrice;
                        double reward = targetPrice - entryPrice;
                        double rr = risk > 0 ? reward / risk : 0.0;

                        if (rr >= MinRewardRiskRatio || targetPrice <= entryPrice)
                        {
                            EnterLongStopMarket(0, true, 1, entryPrice, "Strat22_Long");
                            SetStopLoss("Strat22_Long", CalculationMode.Price, stopPrice, false);
                            if (targetPrice > entryPrice)
                            {
                                SetProfitTarget("Strat22_Long", CalculationMode.Price, targetPrice);
                            }
                        }
                    }
                }
            }

            // ----------------------------------------------------
            // 2. Bearish 2-2 Reversal: Bar[1] is 2U -> Enter Short if price breaks Low[1]
            // ----------------------------------------------------
            if (prev1Strat == 21)
            {
                if (!RequireActionableWick || prev1Wick == -1)
                {
                    if (!UseFTFCFilter || ftfcScore <= -MinFTFCScore)
                    {
                        double entryPrice = Low[1] - TickSize;
                        double stopPrice = High[1] + TickSize;
                        double targetPrice = Low[2]; // Magnitude 1

                        double risk = stopPrice - entryPrice;
                        double reward = entryPrice - targetPrice;
                        double rr = risk > 0 ? reward / risk : 0.0;

                        if (rr >= MinRewardRiskRatio || targetPrice >= entryPrice)
                        {
                            EnterShortStopMarket(0, true, 1, entryPrice, "Strat22_Short");
                            SetStopLoss("Strat22_Short", CalculationMode.Price, stopPrice, false);
                            if (targetPrice < entryPrice)
                            {
                                SetProfitTarget("Strat22_Short", CalculationMode.Price, targetPrice);
                            }
                        }
                    }
                }
            }
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
