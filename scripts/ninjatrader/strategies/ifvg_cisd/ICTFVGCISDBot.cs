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
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class ICTFVGCISDBot : Strategy
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
        [Display(Name = "PM Afternoon MFE (Basis Points)", Order = 6, GroupName = "4. Basis Points Targets")]
        public double Target2PmMfeBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "80th %ile Fat-Tail MFE (Basis Points)", Order = 7, GroupName = "4. Basis Points Targets")]
        public double Target3FatTailBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Hard Risk Ceiling (Basis Points)", Order = 8, GroupName = "5. Risk Management")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Daily Trades", Order = 9, GroupName = "5. Risk Management")]
        public int MaxDailyTrades { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Earliest Entry (HHMM)", Order = 10, GroupName = "5. Risk Management")]
        public int EarliestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Latest Entry (HHMM)", Order = 11, GroupName = "5. Risk Management")]
        public int LatestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten By (HHMM)", Order = 12, GroupName = "5. Risk Management")]
        public int FlattenBy { get; set; }
        #endregion

        #region Internal State Fields
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

        // 2-Contract Pack State
        private double activeEntryPrice;
        private double activeStopLoss;
        private double activeQueenTP;
        private double activeRunnerTP;
        private bool queenFilled;
        private int todayTradeCount;
        private DateTime lastTradeDate;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Institutional Liquidity -> CISD -> 50% CE Retest with 2-Contract Pack Trading (Cover The Queen 10 bps + Breakeven Lock)";
                Name = "ICTFVGCISDBot";
                Calculate = Calculate.OnPriceChange;
                EntriesPerDirection = 2;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;
                IsFillLimitOnTouch = true;

                HtfPeriodMinutes = 15;
                SweepLookbackBars = 25;
                MaxRetestWaitBars = 20;

                Target1QueenBps = 10.0;     // 10 bps scale-out to make trade risk-free
                Target2MedianMfeBps = 30.0; // 30 bps (50th percentile MFE)
                Target2PmMfeBps = 50.0;     // 50 bps PM expansion target
                Target3FatTailBps = 70.0;   // 70 bps (80th percentile Fat-Tail MFE)
                MaxRiskBps = 15.0;          // 15 bps Hard Risk Ceiling

                MaxDailyTrades = 5;
                EarliestEntry = 945;
                LatestEntry = 1530;
                FlattenBy = 1555;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, HtfPeriodMinutes);
                AddDataSeries(BarsPeriodType.Minute, 60);
                AddDataSeries(BarsPeriodType.Minute, 240);
                AddDataSeries(BarsPeriodType.Day, 1);
            }
            else if (State == State.DataLoaded)
            {
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

                activeEntryPrice = double.NaN;
                activeStopLoss = double.NaN;
                activeQueenTP = double.NaN;
                activeRunnerTP = double.NaN;
                queenFilled = false;
                todayTradeCount = 0;
                lastTradeDate = DateTime.MinValue;
            }
        }

        private double CalcBpsDistance(double price, double bps)
        {
            double dist = price * (bps / 10000.0);
            return Math.Round(dist / TickSize) * TickSize;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBars[0] < 20)
                return;

            // Manage HTF series updates
            if (BarsInProgress == 1)
            {
                UpdateHtfLiquidityAndCisd();
                return;
            }

            if (BarsInProgress != 0)
                return;

            DateTime barTime = Times[0][0];
            if (barTime.Date != lastTradeDate.Date)
            {
                lastTradeDate = barTime.Date;
                todayTradeCount = 0;
            }

            int timeNum = ToTime(barTime);

            // EOD Flatten
            if (timeNum >= FlattenBy * 100)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    FlattenEntirePosition("EOD 15:55 Flatten");
                }
                return;
            }

            bool inRth = timeNum >= EarliestEntry * 100 && timeNum <= LatestEntry * 100;
            bool canEnter = inRth && (todayTradeCount < MaxDailyTrades) && (Position.MarketPosition == MarketPosition.Flat);

            // -----------------------------------------------------------------
            // STEP 3 & 4: RETEST FILL CHECK (Limit Entry on 5m series)
            // -----------------------------------------------------------------
            if (hasPendingLongRetest && canEnter)
            {
                if (CurrentBars[1] - pendingLongArmedBar <= MaxRetestWaitBars)
                {
                    if (Lows[0][0] <= pendingLongEntryPrice)
                    {
                        ExecutePackEntry(1, pendingLongEntryPrice, pendingLongSL);
                        hasPendingLongRetest = false;
                    }
                }
                else
                {
                    hasPendingLongRetest = false;
                }
            }

            if (hasPendingShortRetest && canEnter)
            {
                if (CurrentBars[1] - pendingShortArmedBar <= MaxRetestWaitBars)
                {
                    if (Highs[0][0] >= pendingShortEntryPrice)
                    {
                        ExecutePackEntry(-1, pendingShortEntryPrice, pendingShortSL);
                        hasPendingShortRetest = false;
                    }
                }
                else
                {
                    hasPendingShortRetest = false;
                }
            }

            // -----------------------------------------------------------------
            // STEP 5: INTRABAR POSITION MANAGEMENT (Queen Scale-Out + BE Lock)
            // -----------------------------------------------------------------
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Check if Queen target reached
                if (!queenFilled && Highs[0][0] >= activeQueenTP)
                {
                    queenFilled = true;
                    // Lock Runner to Breakeven!
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (!queenFilled && Lows[0][0] <= activeQueenTP)
                {
                    queenFilled = true;
                    // Lock Runner to Breakeven!
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }
        }

        private void ExecutePackEntry(int direction, double entryPrice, double stopPrice)
        {
            activeEntryPrice = entryPrice;
            activeStopLoss = stopPrice;
            queenFilled = false;
            todayTradeCount++;

            int timeNum = ToTime(Times[0][0]);
            bool isPmMacro = timeNum >= 133000 && timeNum <= 153000;
            double runnerBps = isPmMacro ? Target2PmMfeBps : Target2MedianMfeBps;

            double distQueen = CalcBpsDistance(entryPrice, Target1QueenBps);
            double distRunner = CalcBpsDistance(entryPrice, runnerBps);

            if (direction == 1)
            {
                activeQueenTP = entryPrice + distQueen;
                activeRunnerTP = entryPrice + distRunner;

                EnterLong(1, "Queen");
                EnterLong(1, "Runner");

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);

                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);
            }
            else if (direction == -1)
            {
                activeQueenTP = entryPrice - distQueen;
                activeRunnerTP = entryPrice - distRunner;

                EnterShort(1, "Queen");
                EnterShort(1, "Runner");

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);

                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);
            }
        }

        private void FlattenEntirePosition(string signalName)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                ExitLong(signalName);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                ExitShort(signalName);
            }
            hasPendingLongRetest = false;
            hasPendingShortRetest = false;
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

            // 1. STEP 1: Liquidity Sweeps (15m Swings + 1H Swings + 4H Swings + Daily + HTF FVGs)
            bool sslSwept = (l0 < l2) && (c0 > l2);
            bool bslSwept = (h0 > h2) && (c0 < h2);

            // 1H High/Low Sweeps (Series 2)
            if (CurrentBars[2] >= 2)
            {
                double h1_h0 = Highs[2][1];
                double h1_l0 = Lows[2][1];
                if (h0 > h1_h0 && c0 < h1_h0) bslSwept = true;
                if (l0 < h1_l0 && c0 > h1_l0) sslSwept = true;
            }

            // 4H High/Low Sweeps (Series 3)
            if (CurrentBars[3] >= 2)
            {
                double h4_h0 = Highs[3][1];
                double h4_l0 = Lows[3][1];
                if (h0 > h4_h0 && c0 < h4_h0) bslSwept = true;
                if (l0 < h4_l0 && c0 > h4_l0) sslSwept = true;
            }

            // Daily PDH / PDL Sweeps (Series 4)
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

            if (CurrentBars[1] - lastBullSweepBar > SweepLookbackBars)
                hasActiveBullSweep = false;
            if (CurrentBars[1] - lastBearSweepBar > SweepLookbackBars)
                hasActiveBearSweep = false;

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

            // 3. CISD Delivery Breach & 50% Consequent Encroachment (CE) Arming
            bool newBullFvg = l0 > h2;
            bool newBearFvg = h0 < l2;

            if ((armedBullCisd && !double.IsNaN(armedBullHigh) && c0 > armedBullHigh) || 
                (currentDeliveryRegime == 1 && newBullFvg && !hasPendingLongRetest))
            {
                armedBullCisd = false;
                currentDeliveryRegime = 1;
                hasActiveBullSweep = false;

                double ePrice = newBullFvg ? ((l0 + h2) / 2.0) : armedBullHigh;
                double slPrice = !double.IsNaN(armedCisdOriginSL) ? armedCisdOriginSL - (2 * TickSize) : Lows[1][1] - (2 * TickSize);

                if (slPrice >= ePrice)
                    slPrice = ePrice - CalcBpsDistance(ePrice, MaxRiskBps);

                double riskBps = ((ePrice - slPrice) / ePrice) * 10000.0;
                if (riskBps <= MaxRiskBps)
                {
                    hasPendingLongRetest = true;
                    pendingLongEntryPrice = ePrice;
                    pendingLongSL = slPrice;
                    pendingLongArmedBar = CurrentBars[1];
                }
            }

            if ((armedBearCisd && !double.IsNaN(armedBearLow) && c0 < armedBearLow) || 
                (currentDeliveryRegime == -1 && newBearFvg && !hasPendingShortRetest))
            {
                armedBearCisd = false;
                currentDeliveryRegime = -1;
                hasActiveBearSweep = false;

                double ePrice = newBearFvg ? ((l2 + h0) / 2.0) : armedBearLow;
                double slPrice = !double.IsNaN(armedCisdOriginSL) ? armedCisdOriginSL + (2 * TickSize) : Highs[1][1] + (2 * TickSize);

                if (slPrice <= ePrice)
                    slPrice = ePrice + CalcBpsDistance(ePrice, MaxRiskBps);

                double riskBps = ((slPrice - ePrice) / ePrice) * 10000.0;
                if (riskBps <= MaxRiskBps)
                {
                    hasPendingShortRetest = true;
                    pendingShortEntryPrice = ePrice;
                    pendingShortSL = slPrice;
                    pendingShortArmedBar = CurrentBars[1];
                }
            }
        }
    }
}
