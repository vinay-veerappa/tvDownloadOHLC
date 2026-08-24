#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// Strat22RevStratBot - Automated 2-2 Strat Reversal Strategy.
    /// Consumes TheStratClassifier indicator for visual rendering and signals.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    /// </summary>
    public class Strat22RevStratBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Range(0.50, 0.90)]
        [Display(Name = "Actionable Wick Threshold", Order = 1, GroupName = "The Strat")]
        public double WickThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 2, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }
        #endregion

        private Indicators.TheStrat.TheStratClassifier stratClassifier;
        private ATR chartAtr;

        protected override string GetStrategyName() => "Strat22Bot";

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-2 Strat reversal bot consuming TheStratClassifier with centralized RiskManagerBase";
            Name = "Strat22RevStratBot";

            WickThreshold = 0.60;
            MinTargetPoints = 15.0;

            // RiskManagerBase Defaults (NQ/MNQ)
            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 3;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 4;
            MaxTradesPerDay = 6;
            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            // Brackets & Execution Policy
            TradePolicy = TradePolicyType.CoverTheQueen; // Default to Cover the Queen (10 bps scale-out + risk-free runner)
            TargetRMultiple = 2.5;
            BreakevenTriggerR = 1.0;
            AtrPeriod = 14;
            StopAtrMult = 1.5;
            TrailAtrMult = 2.0;
            AddSecondaryTimeframe = false; // Self-contained on chart series
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
        {
            stratClassifier = TheStratClassifier(WickThreshold);
            chartAtr = ATR(AtrPeriod);
        }

        protected override double GetCurrentATR()
        {
            if (chartAtr == null || CurrentBar < AtrPeriod)
                return 15.0 * TickSize * 4;
            return chartAtr[0];
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }

        protected override int CheckForSignal()
        {
            if (stratClassifier == null || CurrentBar < 4)
                return 0;

            return stratClassifier.Signal22Series[0];
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (stratClassifier == null || CurrentBar < 4) return double.NaN;
            double sl = stratClassifier.InsideBarStopSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            if (stratClassifier == null || CurrentBar < 4) return double.NaN;
            double target = stratClassifier.MagnitudeTargetSeries[0];
            if (!double.IsNaN(target) && target > 0)
            {
                double dist = Math.Abs(target - entryPrice);
                if (dist >= MinTargetPoints) return target;
            }
            return double.NaN;
        }
    }
}
