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
        [Display(Name = "Cover The Queen (Basis Points)", Order = 1, GroupName = "1. Basis Points Targets")]
        public double Target1QueenBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "AM Expansion Target (Basis Points)", Order = 2, GroupName = "1. Basis Points Targets")]
        public double Target2AmBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "PM Macro Expansion Target (Basis Points)", Order = 3, GroupName = "1. Basis Points Targets")]
        public double Target2PmBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Hard Risk Ceiling (Basis Points)", Order = 4, GroupName = "2. Risk Management")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Failed CISD Trap Breakout", Order = 5, GroupName = "2. Risk Management")]
        public bool EnableTrapReExpansion { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable 1H Trend Alignment", Order = 6, GroupName = "3. Filters")]
        public bool EnableHtfTrend { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Displacement Body (Basis Points)", Order = 7, GroupName = "3. Filters")]
        public double MinDisplacementBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Daily Trades", Order = 8, GroupName = "4. Execution Rules")]
        public int MaxDailyTrades { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Retest Wait Bars", Order = 9, GroupName = "4. Execution Rules")]
        public int MaxRetestWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Earliest Entry (HHMM)", Order = 10, GroupName = "5. Time Window")]
        public int EarliestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Latest Entry (HHMM)", Order = 11, GroupName = "5. Time Window")]
        public int LatestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten By (HHMM)", Order = 12, GroupName = "5. Time Window")]
        public int FlattenBy { get; set; }
        #endregion

        #region Internal State Fields
        // Indicators
        private EMA ema20_1h;
        private EMA ema50_1h;
        private SMA volSma20;

        // Rolling Fractal Swings
        private List<double> bslList;
        private List<double> sslList;

        // Liquidity Sweep State
        private bool hasBullSweep;
        private bool hasBearSweep;
        private int bullSweepBar;
        private int bearSweepBar;

        // Canonical CISD State
        private bool armedBullCisd;
        private bool armedBearCisd;
        private double armedBullHigh;
        private double armedBearLow;
        private double armedCisdOriginSL;

        // Pending Entry Zone (First Presented FVG)
        private bool hasPendingLong;
        private bool hasPendingShort;
        private double pendingLongEntryPrice;
        private double pendingShortEntryPrice;
        private double pendingLongSL;
        private double pendingShortSL;
        private int pendingLongArmedBar;
        private int pendingShortArmedBar;

        // Trapped Liquidity Re-Expansion State (Alpha 1)
        private bool hasPendingTrap;
        private int trapDirection;
        private double trapEntryPrice;
        private double trapStopLoss;
        private int trapArmedBar;

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
                Description = "Institutional Master Model: SMT + First Presented FVG + 1H HTF Trend + 2-Contract Pack + Failed CISD Trap";
                Name = "ICTFVGCISDBot";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 2;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;

                Target1QueenBps = 10.0;     // 10 bps scale-out & BE lock
                Target2AmBps = 40.0;        // 40 bps AM expansion target
                Target2PmBps = 60.0;        // 60 bps PM expansion target
                MaxRiskBps = 12.0;          // 12 bps Max Risk Ceiling
                EnableTrapReExpansion = true;
                EnableHtfTrend = true;
                MinDisplacementBps = 3.0;
                MaxRetestWaitBars = 15;

                MaxDailyTrades = 3;
                EarliestEntry = 950;
                LatestEntry = 1515;
                FlattenBy = 1555;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, 60);  // Series 1: 1H HTF
                AddDataSeries(BarsPeriodType.Day, 1);      // Series 2: Daily PDH/PDL
            }
            else if (State == State.DataLoaded)
            {
                ema20_1h = EMA(BarsArray[1], 20);
                ema50_1h = EMA(BarsArray[1], 50);
                volSma20 = SMA(Volume, 20);

                bslList = new List<double>();
                sslList = new List<double>();

                hasBullSweep = false;
                hasBearSweep = false;
                bullSweepBar = -9999;
                bearSweepBar = -9999;

                armedBullCisd = false;
                armedBearCisd = false;
                armedBullHigh = double.NaN;
                armedBearLow = double.NaN;
                armedCisdOriginSL = double.NaN;

                hasPendingLong = false;
                hasPendingShort = false;
                pendingLongEntryPrice = double.NaN;
                pendingShortEntryPrice = double.NaN;
                pendingLongSL = double.NaN;
                pendingShortSL = double.NaN;
                pendingLongArmedBar = -1;
                pendingShortArmedBar = -1;

                hasPendingTrap = false;
                trapDirection = 0;
                trapEntryPrice = double.NaN;
                trapStopLoss = double.NaN;
                trapArmedBar = -1;

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
            if (BarsInProgress != 0)
                return;

            if (CurrentBars[0] < 25 || CurrentBars[1] < 50)
                return;

            DateTime barTime = Times[0][0];
            if (barTime.Date != lastTradeDate.Date)
            {
                lastTradeDate = barTime.Date;
                todayTradeCount = 0;
            }

            int timeNum = ToTime(barTime);

            // EOD Flatten (15:55 ET)
            if (timeNum >= FlattenBy * 100)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    FlattenEntirePosition("EOD 15:55 Flatten");
                }
                return;
            }

            // -----------------------------------------------------------------
            // STEP 1: POSITION MANAGEMENT (Queen Fill -> Move Runner SL to BE)
            // -----------------------------------------------------------------
            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (!queenFilled && Highs[0][0] >= activeQueenTP)
                {
                    queenFilled = true;
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (!queenFilled && Lows[0][0] <= activeQueenTP)
                {
                    queenFilled = true;
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }

            // Session Windows (AM Macro: 09:50-11:15 & PM Macro: 13:30-15:15)
            bool inAm = timeNum >= 95000 && timeNum <= 111500;
            bool inPm = timeNum >= 133000 && timeNum <= 151500;
            bool inSession = (inAm || inPm) && (timeNum >= EarliestEntry * 100 && timeNum <= LatestEntry * 100);
            bool canEnter = inSession && (todayTradeCount < MaxDailyTrades) && (Position.MarketPosition == MarketPosition.Flat);

            // -----------------------------------------------------------------
            // STEP 2: EVALUATE TRAPPED LIQUIDITY RE-EXPANSION (Alpha 1)
            // -----------------------------------------------------------------
            if (hasPendingTrap && canEnter)
            {
                if (CurrentBars[0] - trapArmedBar <= 3)
                {
                    if (trapDirection == 1 && Highs[0][0] >= trapEntryPrice)
                    {
                        ExecutePackEntry(1, trapEntryPrice, trapStopLoss);
                        hasPendingTrap = false;
                    }
                    else if (trapDirection == -1 && Lows[0][0] <= trapEntryPrice)
                    {
                        ExecutePackEntry(-1, trapEntryPrice, trapStopLoss);
                        hasPendingTrap = false;
                    }
                }
                else
                {
                    hasPendingTrap = false;
                }
            }

            // -----------------------------------------------------------------
            // STEP 3: EVALUATE FIRST PRESENTED FVG RETEST FILL
            // -----------------------------------------------------------------
            if (hasPendingLong && canEnter)
            {
                if (CurrentBars[0] - pendingLongArmedBar <= MaxRetestWaitBars)
                {
                    if (Lows[0][0] <= pendingLongEntryPrice)
                    {
                        ExecutePackEntry(1, pendingLongEntryPrice, pendingLongSL);
                        hasPendingLong = false;
                    }
                }
                else
                {
                    hasPendingLong = false;
                }
            }

            if (hasPendingShort && canEnter)
            {
                if (CurrentBars[0] - pendingShortArmedBar <= MaxRetestWaitBars)
                {
                    if (Highs[0][0] >= pendingShortEntryPrice)
                    {
                        ExecutePackEntry(-1, pendingShortEntryPrice, pendingShortSL);
                        hasPendingShort = false;
                    }
                }
                else
                {
                    hasPendingShort = false;
                }
            }

            // -----------------------------------------------------------------
            // STEP 4: 5-MINUTE CANDLE LIQUIDITY & CISD DETECTION
            // -----------------------------------------------------------------
            double h0 = Highs[0][0], l0 = Lows[0][0], c0 = Closes[0][0], o0 = Opens[0][0];
            double h1 = Highs[0][1], l1 = Lows[0][1], c1 = Closes[0][1], o1 = Opens[0][1];
            double h2 = Highs[0][2], l2 = Lows[0][2], c2 = Closes[0][2], o2 = Opens[0][2];

            // 3-Bar Fractal Swing Pivots (Offset by 3 bars)
            if (CurrentBars[0] >= 6)
            {
                if (Highs[0][3] > Highs[0][4] && Highs[0][3] > Highs[0][5] && Highs[0][3] > Highs[0][6] &&
                    Highs[0][3] > Highs[0][2] && Highs[0][3] > Highs[0][1] && Highs[0][3] > Highs[0][0])
                {
                    bslList.Add(Highs[0][3]);
                    if (bslList.Count > 10) bslList.RemoveAt(0);
                }

                if (Lows[0][3] < Lows[0][4] && Lows[0][3] < Lows[0][5] && Lows[0][3] < Lows[0][6] &&
                    Lows[0][3] < Lows[0][2] && Lows[0][3] < Lows[0][1] && Lows[0][3] < Lows[0][0])
                {
                    sslList.Add(Lows[0][3]);
                    if (sslList.Count > 10) sslList.RemoveAt(0);
                }
            }

            bool bslSwept = false;
            bool sslSwept = false;

            // Daily PDH / PDL Sweeps (Series 2)
            if (CurrentBars[2] >= 2)
            {
                double pdh = Highs[2][1];
                double pdl = Lows[2][1];
                if (h0 > pdh && (c0 < pdh || o0 < pdh)) bslSwept = true;
                if (l0 < pdl && (c0 > pdl || o0 > pdl)) sslSwept = true;
            }

            // Intraday Swing Sweeps
            if (!bslSwept)
            {
                foreach (double bsl in bslList)
                {
                    if (h0 > bsl && c0 < bsl) { bslSwept = true; break; }
                }
            }

            if (!sslSwept)
            {
                foreach (double ssl in sslList)
                {
                    if (l0 < ssl && c0 > ssl) { sslSwept = true; break; }
                }
            }

            if (sslSwept)
            {
                hasBullSweep = true;
                bullSweepBar = CurrentBars[0];
            }

            if (bslSwept)
            {
                hasBearSweep = true;
                bearSweepBar = CurrentBars[0];
            }

            if (CurrentBars[0] - bullSweepBar > 20) hasBullSweep = false;
            if (CurrentBars[0] - bearSweepBar > 20) hasBearSweep = false;

            // -----------------------------------------------------------------
            // STEP 5: CANONICAL BACKWARD-WALKING CISD
            // -----------------------------------------------------------------
            if (hasBullSweep && sslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);

                for (int k = 1; k <= Math.Min(20, CurrentBars[0]); k++)
                {
                    if (Closes[0][k] <= Opens[0][k])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[0][k], Closes[0][k]));
                        sLow = Math.Min(sLow, Math.Min(Opens[0][k], Closes[0][k]));
                    }
                    else break;
                }

                armedBullCisd = true;
                armedBullHigh = sHigh;
                armedCisdOriginSL = sLow;
            }

            if (hasBearSweep && bslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);

                for (int k = 1; k <= Math.Min(20, CurrentBars[0]); k++)
                {
                    if (Closes[0][k] >= Opens[0][k])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[0][k], Closes[0][k]));
                        sLow = Math.Min(sLow, Math.Min(Opens[0][k], Closes[0][k]));
                    }
                    else break;
                }

                armedBearCisd = true;
                armedBearLow = sLow;
                armedCisdOriginSL = sHigh;
            }

            // Displacement & HTF Trend Quality Filters
            double bodyBps = (Math.Abs(c0 - o0) / c0) * 10000.0;
            bool passesDisp = bodyBps >= MinDisplacementBps && Volume[0] >= (1.1 * volSma20[0]);

            bool bullHtf = !EnableHtfTrend || (ema20_1h[1] >= ema50_1h[1]);
            bool bearHtf = !EnableHtfTrend || (ema20_1h[1] <= ema50_1h[1]);

            // -----------------------------------------------------------------
            // STEP 6: ARM FIRST PRESENTED FVG RETEST ONLY
            // -----------------------------------------------------------------
            if (armedBullCisd && !double.IsNaN(armedBullHigh) && c0 > armedBullHigh)
            {
                armedBullCisd = false;
                hasBullSweep = false;

                if (passesDisp && bullHtf && !hasPendingLong && Position.MarketPosition == MarketPosition.Flat)
                {
                    bool newBullFvg = l0 > h2;
                    double zTop = newBullFvg ? l0 : armedBullHigh;
                    double zBot = newBullFvg ? h2 : (armedBullHigh - (4 * TickSize));
                    double zCE = (zTop + zBot) / 2.0;

                    double ePrice = zCE;
                    double slPrice = !double.IsNaN(armedCisdOriginSL) ? armedCisdOriginSL - (2 * TickSize) : l1 - (2 * TickSize);

                    if (slPrice >= ePrice)
                        slPrice = min3(l0, l1, l2) - (2 * TickSize);

                    double riskBps = ((ePrice - slPrice) / ePrice) * 10000.0;
                    if (riskBps > 0 && riskBps <= MaxRiskBps)
                    {
                        hasPendingLong = true;
                        pendingLongEntryPrice = ePrice;
                        pendingLongSL = slPrice;
                        pendingLongArmedBar = CurrentBars[0];
                    }
                }
            }

            if (armedBearCisd && !double.IsNaN(armedBearLow) && c0 < armedBearLow)
            {
                armedBearCisd = false;
                hasBearSweep = false;

                if (passesDisp && bearHtf && !hasPendingShort && Position.MarketPosition == MarketPosition.Flat)
                {
                    bool newBearFvg = h0 < l2;
                    double zTop = newBearFvg ? l2 : (armedBearLow + (4 * TickSize));
                    double zBot = newBearFvg ? h0 : armedBearLow;
                    double zCE = (zTop + zBot) / 2.0;

                    double ePrice = zCE;
                    double slPrice = !double.IsNaN(armedCisdOriginSL) ? armedCisdOriginSL + (2 * TickSize) : h1 + (2 * TickSize);

                    if (slPrice <= ePrice)
                        slPrice = max3(h0, h1, h2) + (2 * TickSize);

                    double riskBps = ((slPrice - ePrice) / ePrice) * 10000.0;
                    if (riskBps > 0 && riskBps <= MaxRiskBps)
                    {
                        hasPendingShort = true;
                        pendingShortEntryPrice = ePrice;
                        pendingShortSL = slPrice;
                        pendingShortArmedBar = CurrentBars[0];
                    }
                }
            }
        }

        private double min3(double a, double b, double c) => Math.Min(a, Math.Min(b, c));
        private double max3(double a, double b, double c) => Math.Max(a, Math.Max(b, c));

        private void ExecutePackEntry(int direction, double entryPrice, double stopPrice)
        {
            activeEntryPrice = entryPrice;
            activeStopLoss = stopPrice;
            queenFilled = false;
            todayTradeCount++;

            int timeNum = ToTime(Times[0][0]);
            bool isPmMacro = timeNum >= 133000 && timeNum <= 151500;
            double runnerBps = isPmMacro ? Target2PmBps : Target2AmBps;

            double distQueen = CalcBpsDistance(entryPrice, Target1QueenBps);
            double distRunner = CalcBpsDistance(entryPrice, runnerBps);

            if (direction == 1)
            {
                activeQueenTP = entryPrice + distQueen;
                activeRunnerTP = entryPrice + distRunner;

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);

                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);

                EnterLong(1, "Queen");
                EnterLong(1, "Runner");
            }
            else if (direction == -1)
            {
                activeQueenTP = entryPrice - distQueen;
                activeRunnerTP = entryPrice - distRunner;

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);

                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);

                EnterShort(1, "Queen");
                EnterShort(1, "Runner");
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            // If stopped out at SL-4 origin anchor, trigger Alpha 1 Trapped Liquidity Breakout!
            if (EnableTrapReExpansion && execution.Order != null && execution.Order.OrderState == OrderState.Filled)
            {
                if (execution.Name.Contains("Stop loss") || execution.Name.Contains("StopLoss"))
                {
                    if (execution.Order.OrderAction == OrderAction.Sell || execution.Order.OrderAction == OrderAction.SellShort)
                    {
                        // Long trade stopped out -> Arm Short Breakout Trap
                        trapDirection = -1;
                        trapEntryPrice = activeStopLoss - (2 * TickSize);
                        trapStopLoss = activeEntryPrice;
                        trapArmedBar = CurrentBars[0];
                        hasPendingTrap = true;
                    }
                    else if (execution.Order.OrderAction == OrderAction.Buy || execution.Order.OrderAction == OrderAction.BuyToCover)
                    {
                        // Short trade stopped out -> Arm Long Breakout Trap
                        trapDirection = 1;
                        trapEntryPrice = activeStopLoss + (2 * TickSize);
                        trapStopLoss = activeEntryPrice;
                        trapArmedBar = CurrentBars[0];
                        hasPendingTrap = true;
                    }
                }
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
            hasPendingLong = false;
            hasPendingShort = false;
            hasPendingTrap = false;
        }
    }
}
