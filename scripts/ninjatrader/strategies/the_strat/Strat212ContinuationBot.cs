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
    /// Strat212ContinuationBot - Automated 2-1-2 Strat Continuation Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM order execution.
    ///
    /// Logic:
    ///   - Bullish: Bar[2] == 2U, Bar[1] == 1 (Inside Bar) -> Buy Stop @ High[1] + 1 tick, SL @ Low[1] - 1 tick, TP @ High[2] (Magnitude 1)
    ///   - Bearish: Bar[2] == 2D, Bar[1] == 1 (Inside Bar) -> Sell Stop @ Low[1] - 1 tick, SL @ High[1] + 1 tick, TP @ Low[2] (Magnitude 1)
    /// </summary>
    public class Strat212ContinuationBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Use FTFC Filter", Description = "Only trade in direction of Full Time Frame Continuity", Order = 1, GroupName = "The Strat")]
        public bool UseFTFCFilter { get; set; }

        [NinjaScriptProperty]
        [Range(1, 4)]
        [Display(Name = "Min FTFC Score", Description = "Minimum agreeing timeframes required", Order = 2, GroupName = "The Strat")]
        public int MinFTFCScore { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min R:R Ratio", Description = "Minimum Reward to Risk ratio to accept setup", Order = 3, GroupName = "The Strat")]
        public double MinRewardRiskRatio { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow Reversals (2D-1-2U / 2U-1-2D)", Description = "Also trade 2-1-2 reversals in addition to continuations", Order = 4, GroupName = "The Strat")]
        public bool AllowReversals { get; set; }
        #endregion

        private TheStratClassifier stratClassifier;
        private TheStratFTFCHud ftfcHud;

        protected override string GetStrategyName()
        {
            return "Strat212Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-1-2 Strat continuation and reversal bot with centralized RiskManagerBase";
            Name = "Strat212ContinuationBot";

            // Strat Parameters
            UseFTFCFilter = true;
            MinFTFCScore = 2;
            MinRewardRiskRatio = 1.0;
            AllowReversals = false;

            // RiskManagerBase Defaults (NQ 5m / 1m tuned)
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
            // Allow RiskManagerBase to run risk guards, daily stops, and trailing stops
            base.OnBarUpdate();

            if (CurrentBar < 3 || Position.MarketPosition != MarketPosition.Flat)
                return;

            // Verify Strat classifier outputs
            int prev1Strat = stratClassifier.StratTypeSeries[1]; // Bar[1]
            int prev2Strat = stratClassifier.StratTypeSeries[2]; // Bar[2]

            // We look for Bar[1] to be an Inside Bar (Type 1)
            if (prev1Strat != 1)
                return;

            double insideHigh = High[1];
            double insideLow = Low[1];

            int ftfcScore = ftfcHud != null ? ftfcHud.FTFCScore : 0;

            // ----------------------------------------------------
            // Bullish 2-1-2 Setup: Bar[2]=2U (or 2D if reversal enabled)
            // ----------------------------------------------------
            bool isBullishCont = (prev2Strat == 21);
            bool isBullishRev = AllowReversals && (prev2Strat == 22);

            if (isBullishCont || isBullishRev)
            {
                if (!UseFTFCFilter || ftfcScore >= MinFTFCScore)
                {
                    double entryPrice = insideHigh + TickSize;
                    double stopPrice = insideLow - TickSize;
                    double targetPrice = High[2]; // Magnitude 1

                    double risk = entryPrice - stopPrice;
                    double reward = targetPrice - entryPrice;
                    double rr = risk > 0 ? reward / risk : 0.0;

                    if (rr >= MinRewardRiskRatio || targetPrice <= entryPrice)
                    {
                        // Submit Stop Market Order
                        EnterLongStopMarket(0, true, 1, entryPrice, "Strat212_Long");
                        SetStopLoss("Strat212_Long", CalculationMode.Price, stopPrice, false);
                        if (targetPrice > entryPrice)
                        {
                            SetProfitTarget("Strat212_Long", CalculationMode.Price, targetPrice);
                        }
                    }
                }
            }

            // ----------------------------------------------------
            // Bearish 2-1-2 Setup: Bar[2]=2D (or 2U if reversal enabled)
            // ----------------------------------------------------
            bool isBearishCont = (prev2Strat == 22);
            bool isBearishRev = AllowReversals && (prev2Strat == 21);

            if (isBearishCont || isBearishRev)
            {
                if (!UseFTFCFilter || ftfcScore <= -MinFTFCScore)
                {
                    double entryPrice = insideLow - TickSize;
                    double stopPrice = insideHigh + TickSize;
                    double targetPrice = Low[2]; // Magnitude 1

                    double risk = stopPrice - entryPrice;
                    double reward = entryPrice - targetPrice;
                    double rr = risk > 0 ? reward / risk : 0.0;

                    if (rr >= MinRewardRiskRatio || targetPrice >= entryPrice)
                    {
                        // Submit Stop Market Order
                        EnterShortStopMarket(0, true, 1, entryPrice, "Strat212_Short");
                        SetStopLoss("Strat212_Short", CalculationMode.Price, stopPrice, false);
                        if (targetPrice < entryPrice)
                        {
                            SetProfitTarget("Strat212_Short", CalculationMode.Price, targetPrice);
                        }
                    }
                }
            }
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
