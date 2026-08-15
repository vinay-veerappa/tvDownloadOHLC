#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
using NinjaTrader.NinjaScript.Strategies.Vinay;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class ICTFVGCISDBot : RiskManagerBase
    {
        #region Custom Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "HTF Resolution (Minutes)", Order = 1, GroupName = "1. Multi-Timeframe")]
        public int HtfPeriodMinutes { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Sweep Max Lookback Bars", Order = 2, GroupName = "2. Liquidity Rules")]
        public int SweepLookbackBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Retest Wait Bars", Order = 3, GroupName = "3. Entry Rules")]
        public int MaxRetestWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Cover The Queen (Basis Points)", Order = 4, GroupName = "4. Basis Points Targets")]
        public double Target1QueenBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "50th %ile Median MFE (Basis Points)", Order = 5, GroupName = "4. Basis Points Targets")]
        public double Target2MedianMfeBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "80th %ile Fat-Tail MFE (Basis Points)", Order = 6, GroupName = "4. Basis Points Targets")]
        public double Target3FatTailBps { get; set; }
        #endregion

        #region Internal State Fields
        private ATR primaryAtr;

        // Liquidity Sweep State
        private bool hasActiveBullSweep;
        private bool hasActiveBearSweep;
        private double activeBullSweepLow;
        private double activeBearSweepHigh;
        private int lastBullSweepBar;
        private int lastBearSweepBar;

        // Canonical CISD State
        private bool armedBullCisd;
        private bool armedBearCisd;
        private double armedBullHigh;
        private double armedBearLow;
        private int armedBullStartBar;
        private int armedBearStartBar;
        private double armedCisdOriginSL;
        private int currentDeliveryRegime;

        // Retest Entry Zone
        private bool hasPendingLongRetest;
        private bool hasPendingShortRetest;
        private double pendingLongEntryPrice;
        private double pendingShortEntryPrice;
        private double pendingLongSL;
        private double pendingShortSL;
        private int pendingLongArmedBar;
        private int pendingShortArmedBar;

        private int lastSignalBar;
        #endregion

        protected override string GetStrategyName()
        {
            return "ICT_Liquidity_CISD_CoverTheQueen_BPS";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Pure Liquidity -> CISD -> Retest Entry Strategy with Pure Basis Points (bps) MFE Scaling & Structural Stops";
            Name = "ICTFVGCISDBot";

            HtfPeriodMinutes = 15;
            SweepLookbackBars = 25;
            MaxRetestWaitBars = 20;

            Target1QueenBps = 10.0;     // 10 bps scale-out to make trade risk-free
            Target2MedianMfeBps = 30.0; // 30 bps (50th percentile MFE)
            Target3FatTailBps = 70.0;   // 70 bps (80th percentile Fat-Tail MFE)

            DailyMaxLoss = 1000;
            MaxTradesPerDay = 3;
            EarliestEntry = 945;
            LatestEntry = 1530;
            FlattenBy = 1555;
            TrailingDrawdown = 2000;
        }

        protected override void ConfigureStrategy()
        {
            AddDataSeries(BarsPeriodType.Minute, HtfPeriodMinutes);
            AddDataSeries(BarsPeriodType.Minute, 60);
            AddDataSeries(BarsPeriodType.Minute, 240);
            AddDataSeries(BarsPeriodType.Day, 1);
        }

        protected override void InitializeStrategy()
        {
            primaryAtr = ATR(14);

            hasActiveBullSweep = false;
            hasActiveBearSweep = false;
            activeBullSweepLow = double.NaN;
            activeBearSweepHigh = double.NaN;
            lastBullSweepBar = -9999;
            lastBearSweepBar = -9999;

            armedBullCisd = false;
            armedBearCisd = false;
            armedBullHigh = double.NaN;
            armedBearLow = double.NaN;
            armedBullStartBar = -1;
            armedBearStartBar = -1;
            armedCisdOriginSL = double.NaN;
            currentDeliveryRegime = 0;

            hasPendingLongRetest = false;
            hasPendingShortRetest = false;
            pendingLongEntryPrice = double.NaN;
            pendingShortEntryPrice = double.NaN;
            pendingLongSL = double.NaN;
            pendingShortSL = double.NaN;
            pendingLongArmedBar = -1;
            pendingShortArmedBar = -1;

            lastSignalBar = -1;
        }

        protected override double GetCurrentATR()
        {
            if (primaryAtr == null || CurrentBars[0] < 14)
                return 0;
            return primaryAtr[0];
        }

        private double CalcBpsDistance(double price, double bps)
        {
            double dist = price * (bps / 10000.0);
            return Math.Round(dist / TickSize) * TickSize;
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 1)
            {
                UpdateHtfLiquidityAndCisd();
                return;
            }

            if (BarsInProgress == 0)
            {
                base.OnBarUpdate();
            }
        }

        private void UpdateHtfLiquidityAndCisd()
        {
            if (CurrentBars[1] < 5)
                return;

            double o0 = Opens[1][0];
            double h0 = Highs[1][0];
            double l0 = Lows[1][0];
            double c0 = Closes[1][0];

            double h2 = Highs[1][2];
            double l2 = Lows[1][2];

            // 1. STEP 1: Liquidity Sweeps
            bool sslSwept = (l0 < l2) && (c0 > l2);
            bool bslSwept = (h0 > h2) && (c0 < h2);

            if (CurrentBars[4] >= 2)
            {
                double pdh = Highs[4][1];
                double pdl = Lows[4][1];
                if (h0 > pdh && c0 < pdh) bslSwept = true;
                if (l0 < pdl && c0 > pdl) sslSwept = true;
            }

            if (sslSwept)
            {
                hasActiveBullSweep = true;
                activeBullSweepLow = l0;
                lastBullSweepBar = CurrentBars[1];
            }

            if (bslSwept)
            {
                hasActiveBearSweep = true;
                activeBearSweepHigh = h0;
                lastBearSweepBar = CurrentBars[1];
            }

            if (CurrentBars[1] - lastBullSweepBar > SweepLookbackBars) hasActiveBullSweep = false;
            if (CurrentBars[1] - lastBearSweepBar > SweepLookbackBars) hasActiveBearSweep = false;

            // 2. STEP 2: Canonical Backward-Walking CISD Engine
            if (hasActiveBullSweep && sslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);
                int sStart = CurrentBars[1];

                for (int i = 1; i <= Math.Min(25, CurrentBars[1]); i++)
                {
                    if (Closes[1][i] <= Opens[1][i])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[1][i], Closes[1][i]));
                        sLow = Math.Min(sLow, Math.Min(Opens[1][i], Closes[1][i]));
                        sStart = CurrentBars[1] - i;
                    }
                    else break;
                }

                armedBullCisd = true;
                armedBullHigh = sHigh;
                armedBullStartBar = sStart;
                armedCisdOriginSL = sLow;
            }

            if (hasActiveBearSweep && bslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);
                int sStart = CurrentBars[1];

                for (int i = 1; i <= Math.Min(25, CurrentBars[1]); i++)
                {
                    if (Closes[1][i] >= Opens[1][i])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[1][i], Closes[1][i]));
                        sLow = Math.Min(sLow, Math.Min(Opens[1][i], Closes[1][i]));
                        sStart = CurrentBars[1] - i;
                    }
                    else break;
                }

                armedBearCisd = true;
                armedBearLow = sLow;
                armedBearStartBar = sStart;
                armedCisdOriginSL = sHigh;
            }

            if (armedBullCisd && !double.IsNaN(armedBullHigh) && c0 > armedBullHigh)
            {
                armedBullCisd = false;
                currentDeliveryRegime = 1;
                hasActiveBullSweep = false;

                bool newBullFvg = l0 > h2;
                double ePrice = newBullFvg ? l0 : armedBullHigh;
                double slPrice = activeBullSweepLow - (2 * TickSize);

                hasPendingLongRetest = true;
                pendingLongEntryPrice = ePrice;
                pendingLongSL = slPrice;
                pendingLongArmedBar = CurrentBars[1];
            }

            if (armedBearCisd && !double.IsNaN(armedBearLow) && c0 < armedBearLow)
            {
                armedBearCisd = false;
                currentDeliveryRegime = -1;
                hasActiveBearSweep = false;

                bool newBearFvg = h0 < l2;
                double ePrice = newBearFvg ? h0 : armedBearLow;
                double slPrice = activeBearSweepHigh + (2 * TickSize);

                hasPendingShortRetest = true;
                pendingShortEntryPrice = ePrice;
                pendingShortSL = slPrice;
                pendingShortArmedBar = CurrentBars[1];
            }
        }

        protected override int CheckForSignal()
        {
            if (CurrentBars[0] < 15 || CurrentBars[1] < 5)
                return 0;

            if (CurrentBars[0] == lastSignalBar)
                return 0;

            if (hasPendingLongRetest)
            {
                if (CurrentBars[1] - pendingLongArmedBar <= MaxRetestWaitBars)
                {
                    if (Lows[0][0] <= pendingLongEntryPrice)
                    {
                        hasPendingLongRetest = false;
                        lastSignalBar = CurrentBars[0];
                        return 1;
                    }
                }
                else
                {
                    hasPendingLongRetest = false;
                }
            }

            if (hasPendingShortRetest)
            {
                if (CurrentBars[1] - pendingShortArmedBar <= MaxRetestWaitBars)
                {
                    if (Highs[0][0] >= pendingShortEntryPrice)
                    {
                        hasPendingShortRetest = false;
                        lastSignalBar = CurrentBars[0];
                        return -1;
                    }
                }
                else
                {
                    hasPendingShortRetest = false;
                }
            }

            return 0;
        }
    }
}
