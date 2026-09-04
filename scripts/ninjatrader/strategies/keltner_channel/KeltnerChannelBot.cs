#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public enum KeltnerStrategyMode
    {
        AdaptiveHybrid,
        TrendPullback,
        MeanReversion
    }

    /// <summary>
    /// KeltnerChannelBot — Systematic Keltner Channel Strategy with Multi-Regime & MTF capabilities.
    /// Inherits from RiskManagerBase for institutional risk controls, ATM profit brackets,
    /// dynamic ATR stops, daily max loss circuit breakers, and execution logging.
    /// Supports NQ, MNQ, ES, MES, and other futures instruments.
    /// </summary>
    public class KeltnerChannelBot : RiskManagerBase
    {
        #region Parameters

        [NinjaScriptProperty]
        [Display(Name = "Strategy Mode", GroupName = "1. Strategy Mode", Order = 1, Description = "Operating mode: AdaptiveHybrid, TrendPullback, or MeanReversion")]
        public KeltnerStrategyMode StrategyMode { get; set; }

        // ── 2. Keltner Base Parameters ──
        [NinjaScriptProperty]
        [Range(5, 200)]
        [Display(Name = "MA Length", GroupName = "2. Keltner Base", Order = 1, Description = "Lookback period for Centerline")]
        public int MovingAverageLength { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "MA Type", GroupName = "2. Keltner Base", Order = 2, Description = "Moving Average algorithm")]
        public MovingAverageVariant MaType { get; set; }

        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name = "ATR Multiplier Min", GroupName = "2. Keltner Base", Order = 3, Description = "Inner band multiplier")]
        public double AtrMultiplierMin { get; set; }

        [NinjaScriptProperty]
        [Range(1.0, 6.0)]
        [Display(Name = "ATR Multiplier Max", GroupName = "2. Keltner Base", Order = 4, Description = "Outer band multiplier")]
        public double AtrMultiplierMax { get; set; }

        // ── 3. Filters & Confluence ──
        [NinjaScriptProperty]
        [Display(Name = "Require WaveTrend Filter", GroupName = "3. Filters & Confluence", Order = 1, Description = "Filter mean-reversion entries with WaveTrend extreme")]
        public bool RequireWaveTrendFilter { get; set; }

        [NinjaScriptProperty]
        [Range(50.0, 95.0)]
        [Display(Name = "WaveTrend Extreme Threshold", GroupName = "3. Filters & Confluence", Order = 2, Description = "WaveTrend Overbought/Oversold threshold (e.g. 70 or 80)")]
        public double WaveTrendExtremeThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(2, 50)]
        [Display(Name = "Trend Slope Period", GroupName = "3. Filters & Confluence", Order = 3, Description = "Bars back to calculate Centerline slope delta")]
        public int TrendSlopePeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "Trend Slope Threshold (pts)", GroupName = "3. Filters & Confluence", Order = 4, Description = "Slope threshold in points to identify trending vs ranging")]
        public double TrendSlopeThreshold { get; set; }

        // ── 4. Target & Trailing ──
        [NinjaScriptProperty]
        [Range(0.5, 10.0)]
        [Display(Name = "Target R Multiple", GroupName = "4. Target & Trailing", Order = 1, Description = "Target 2 Risk-to-Reward multiple")]
        public double TargetRMultiple { get; set; }

        // ── 5. Multi-Timeframe (MTF) ──
        [NinjaScriptProperty]
        [Display(Name = "Use Higher Timeframe (MTF)", GroupName = "5. MTF Settings", Order = 1, Description = "Compute Keltner Channels on a secondary MTF data series")]
        public bool UseHtf { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "HTF Period Type", GroupName = "5. MTF Settings", Order = 2, Description = "Bar period type for MTF")]
        public BarsPeriodType HtfPeriodType { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "HTF Period Value", GroupName = "5. MTF Settings", Order = 3, Description = "Period value for MTF (e.g. 15 or 60)")]
        public int HtfPeriodValue { get; set; }

        #endregion

        private Indicators.KeltnerChannelSignals keltner;
        private ATR atr;

        protected override string GetStrategyName() => "KeltnerChannelBot";

        protected override void SetStrategyDefaults()
        {
            Description                 = "Systematic Keltner Channel strategy with multi-regime adaptability, WaveTrend confluence, and institutional risk management.";
            Name                        = "KeltnerChannelBot";

            // Default Risk Management (mirrors RiskManagerBase)
            DailyMaxLoss                = 1000.0;
            MaxConsecutiveLosers        = 3;
            PauseMinutes                = 30;
            HardStopConsecutiveLosers   = 4;
            MaxTradesPerDay             = 4;
            TrailingDrawdown            = 2000.0;

            EarliestEntry               = 930;
            LatestEntry                 = 1530;
            FlattenBy                   = 1600;

            StopAtrMult                 = 1.0;
            AtrPeriod                   = 14;
            TradePolicy                 = TradePolicyType.FixedTarget;
            BreakevenTriggerR           = 1.0;
            TrailAtrMult                = 1.5;

            // Strategy Specific Defaults
            StrategyMode                = KeltnerStrategyMode.AdaptiveHybrid;
            MovingAverageLength         = 34;
            MaType                      = MovingAverageVariant.EMA;
            AtrMultiplierMin            = 1.5;
            AtrMultiplierMax            = 3.5;

            RequireWaveTrendFilter      = true;
            WaveTrendExtremeThreshold   = 70.0;
            TrendSlopePeriod            = 10;
            TrendSlopeThreshold         = 3.0; // 3.0 pts for NQ; set to 0.75 for ES
            TargetRMultiple             = 2.0;

            UseHtf                      = false;
            HtfPeriodType               = BarsPeriodType.Minute;
            HtfPeriodValue              = 15;
        }

        protected override void ConfigureStrategy()
        {
            if (UseHtf)
            {
                AddDataSeries(BarsArray[0].Instrument.FullName, HtfPeriodType, HtfPeriodValue);
            }
        }

        protected override void InitializeStrategy()
        {
            keltner = KeltnerChannelSignals(
                UseHtf, HtfPeriodType, HtfPeriodValue,
                MovingAverageLength, MaType, AtrMultiplierMin, AtrMultiplierMax,
                MovingAverageVariant.EMA, 88, 34, 2.0, 1.0, 0.0,
                false, 10, 3, 3, 90.0, -90.0, false, false, false
            );

            atr = ATR(BarsArray[0], AtrPeriod);
        }

        protected override double GetPotentialLoss()
        {
            double a = GetCurrentATR();
            if (a <= 0) a = 10.0;
            return a * StopAtrMult * GetPointValue();
        }

        protected override double GetCurrentATR()
        {
            if (atr == null || CurrentBars[0] < AtrPeriod) return 0;
            return atr[0];
        }

        protected override int CheckForSignal()
        {
            int warmup = Math.Max(MovingAverageLength, 88) + TrendSlopePeriod + 5;
            if (keltner == null || CurrentBars[0] < warmup) return 0;

            double kcMid     = keltner.KcBase[0];
            double kcTopMin  = keltner.KcTopMin[0];
            double kcBotMin  = keltner.KcBottomMin[0];
            int rawSig       = keltner.SignalSeries[0];
            double wt1       = keltner.WaveTrend1[0];
            double wt2       = keltner.WaveTrend2[0];

            double prevKcMid = keltner.KcBase[TrendSlopePeriod];
            double slope     = kcMid - prevKcMid;

            bool isTrendingUp   = slope > TrendSlopeThreshold;
            bool isTrendingDown = slope < -TrendSlopeThreshold;
            bool isRanging      = !isTrendingUp && !isTrendingDown;

            int signal = 0;

            switch (StrategyMode)
            {
                case KeltnerStrategyMode.TrendPullback:
                    if (isTrendingUp && Low[0] <= kcMid && Close[0] > kcMid && wt1 > wt2)
                        signal = 1;
                    else if (isTrendingDown && High[0] >= kcMid && Close[0] < kcMid && wt1 < wt2)
                        signal = -1;
                    break;

                case KeltnerStrategyMode.MeanReversion:
                    if (rawSig == 1 && (!RequireWaveTrendFilter || wt2 < -WaveTrendExtremeThreshold) && slope >= -TrendSlopeThreshold)
                        signal = 1;
                    else if (rawSig == -1 && (!RequireWaveTrendFilter || wt2 > WaveTrendExtremeThreshold) && slope <= TrendSlopeThreshold)
                        signal = -1;
                    break;

                case KeltnerStrategyMode.AdaptiveHybrid:
                default:
                    if (isTrendingUp)
                    {
                        if ((Low[0] <= kcMid || Low[0] <= kcBotMin) && Close[0] > kcMid && wt1 > wt2)
                            signal = 1;
                    }
                    else if (isTrendingDown)
                    {
                        if ((High[0] >= kcMid || High[0] >= kcTopMin) && Close[0] < kcMid && wt1 < wt2)
                            signal = -1;
                    }
                    else
                    {
                        // Range market exhaustion fades
                        if (rawSig == 1 && (!RequireWaveTrendFilter || wt2 < -60.0))
                            signal = 1;
                        else if (rawSig == -1 && (!RequireWaveTrendFilter || wt2 > 60.0))
                            signal = -1;
                    }
                    break;
            }

            // Visual annotation on charts
            if (signal != 0 && DrawVisuals)
            {
                string tag = "KC_Sig_" + CurrentBar;
                if (signal == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arr", false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                    Draw.Text(this, tag + "_Txt", false, "KC BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (signal == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arr", false, 0, High[0] + (4 * TickSize), Brushes.OrangeRed);
                    Draw.Text(this, tag + "_Txt", false, "KC SELL", 0, High[0] + (10 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }

            return signal;
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            double a = GetCurrentATR();
            if (a <= 0) a = 10.0;
            double slDist = StopAtrMult * a;

            if (signal == 1)
            {
                double structLow = keltner != null ? keltner.Support[0] : Low[0];
                double targetStop = Math.Min(structLow, entryPrice - slDist);
                // Cap max risk at 40 pts for NQ / 10 pts for ES
                double maxRisk = (Instrument.MasterInstrument.Name.Contains("ES")) ? 10.0 : 40.0;
                return Math.Max(targetStop, entryPrice - maxRisk);
            }
            else
            {
                double structHigh = keltner != null ? keltner.Resistance[0] : High[0];
                double targetStop = Math.Max(structHigh, entryPrice + slDist);
                double maxRisk = (Instrument.MasterInstrument.Name.Contains("ES")) ? 10.0 : 40.0;
                return Math.Min(targetStop, entryPrice + maxRisk);
            }
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            if (stopDist <= 0) return double.NaN;
            double targetDist = stopDist * TargetRMultiple;
            return signal == 1 ? entryPrice + targetDist : entryPrice - targetDist;
        }
    }
}
