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
        [Display(Name = "Queen Target (Basis Points)", Order = 1, GroupName = "1. Basis Points Targets")]
        public double QueenBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (Basis Points)", Order = 2, GroupName = "1. Basis Points Targets")]
        public double RunnerBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Hard Risk Ceiling (Basis Points)", Order = 3, GroupName = "2. Risk Management")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Volume Multiplier (x SMA20)", Order = 4, GroupName = "2. Risk Management")]
        public double MinVolMult { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Risk per Trade (USD)", Order = 5, GroupName = "2. Risk Management")]
        public double RiskUsd { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Contracts", Order = 6, GroupName = "2. Risk Management")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Daily Trades", Order = 7, GroupName = "3. Execution Rules")]
        public int MaxDailyTrades { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Retest Wait Bars", Order = 8, GroupName = "3. Execution Rules")]
        public int MaxRetestWaitBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Earliest Entry (HHMM)", Order = 9, GroupName = "4. Time Window")]
        public int EarliestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Latest Entry (HHMM)", Order = 10, GroupName = "4. Time Window")]
        public int LatestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten By (HHMM)", Order = 11, GroupName = "4. Time Window")]
        public int FlattenBy { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Track 4H Sweeps", Order = 12, GroupName = "5. Liquidity Sources")]
        public bool Check4H { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Track Session Sweeps", Order = 13, GroupName = "5. Liquidity Sources")]
        public bool CheckSessions { get; set; }
        #endregion

        #region Internal State Fields
        private SMA volSma20;

        // 1H Rolling Swings
        private List<double> htfBslList;
        private List<double> htfSslList;

        // 4H High/Low (from Series 2)
        private double prev4hHigh;
        private double prev4hLow;

        // Session H/L
        private double asiaHigh, asiaLow;
        private double lonHigh, lonLow;
        private double nyamHigh, nyamLow;
        private bool wasAsia, wasLon, wasNyam;
        private bool hasAsia, hasLon, hasNyam;

        // Liquidity Sweep State
        private bool hasBullSweep;
        private bool hasBearSweep;
        private int bullSweepBar;
        private int bearSweepBar;
        private string sweepLevelName;

        // Canonical CISD State
        private bool armedBullCisd;
        private bool armedBearCisd;
        private double armedBullHigh;
        private double armedBearLow;
        private double armedCisdOriginSL;
        private int deliveryRegime;

        // Pending Entry Zone
        private bool hasPendingLong;
        private bool hasPendingShort;
        private double pendingLongEntryPrice;
        private double pendingShortEntryPrice;
        private double pendingLongSL;
        private double pendingShortSL;
        private int pendingLongArmedBar;
        private int pendingShortArmedBar;

        // Triggered entry (touch detected, execute on next bar open)
        private bool longTriggered;
        private bool shortTriggered;
        private double triggeredLongEntry;
        private double triggeredLongSL;
        private double triggeredShortEntry;
        private double triggeredShortSL;

        // Active Trade State (2-contract: Queen + Runner)
        private double activeEntryPrice;
        private double activeStopLoss;
        private double activeQueenTP;
        private double activeRunnerTP;
        private bool queenFilled;
        private int entryBarIndex;      // bar where entry filled — stops set from next bar
        private bool stopsArmed;         // false until stops/targets are submitted

        private int todayTradeCount;
        private DateTime lastTradeDate;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ICT v3: Liquidity Sweep -> CISD -> FVG Touch -> SL-4 -> Cover The Queen (2-contract pack)";
                Name = "ICTFVGCISDBot";
                Calculate = Calculate.OnBarClose;
                IsFillLimitOnTouch = true;
                EntriesPerDirection = 2;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;
                BarsRequiredToTrade = 25;
                IncludeTradeHistoryInBacktest = true;
                IsTradingHoursBreakLineVisible = false;

                QueenBps = 10.0;
                RunnerBps = 30.0;
                MaxRiskBps = 15.0;
                MinVolMult = 1.5;
                RiskUsd = 250.0;
                MaxContracts = 10;
                MaxRetestWaitBars = 20;
                MaxDailyTrades = 5;
                EarliestEntry = 945;
                LatestEntry = 1530;
                FlattenBy = 1555;
                Check4H = true;
                CheckSessions = true;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, 60);   // Series 1: 1-Hour
                AddDataSeries(BarsPeriodType.Minute, 240);  // Series 2: 4-Hour
                AddDataSeries(BarsPeriodType.Day, 1);       // Series 3: Daily PDH/PDL
            }
            else if (State == State.DataLoaded)
            {
                volSma20 = SMA(Volume, 20);

                htfBslList = new List<double>();
                htfSslList = new List<double>();

                prev4hHigh = double.NaN;
                prev4hLow = double.NaN;

                asiaHigh = asiaLow = lonHigh = lonLow = nyamHigh = nyamLow = double.NaN;
                wasAsia = wasLon = wasNyam = false;
                hasAsia = hasLon = hasNyam = false;

                hasBullSweep = false;
                hasBearSweep = false;
                bullSweepBar = -9999;
                bearSweepBar = -9999;
                sweepLevelName = string.Empty;

                armedBullCisd = false;
                armedBearCisd = false;
                armedBullHigh = double.NaN;
                armedBearLow = double.NaN;
                armedCisdOriginSL = double.NaN;
                deliveryRegime = 0;

                hasPendingLong = false;
                hasPendingShort = false;
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
                entryBarIndex = -1;
                stopsArmed = false;

                todayTradeCount = 0;
                lastTradeDate = DateTime.MinValue;
            }
        }

        private double CalcBpsDistance(double price, double bps)
        {
            double dist = price * (bps / 10000.0);
            return Math.Round(dist / TickSize) * TickSize;
        }

        private int CalcContracts(double entryPrice, double stopPrice)
        {
            double slDist = Math.Abs(entryPrice - stopPrice);
            if (slDist <= 0) return 2;
            int qty = (int)(RiskUsd / (slDist * Instrument.MasterInstrument.PointValue));
            return Math.Max(2, Math.Min(qty, MaxContracts));
        }

        protected override void OnBarUpdate()
        {
            // === Series 1: 1H Swings ===
            if (BarsInProgress == 1)
            {
                if (CurrentBars[1] >= 5)
                {
                    if (Highs[1][2] > Highs[1][4] && Highs[1][2] > Highs[1][3] &&
                        Highs[1][2] > Highs[1][1] && Highs[1][2] > Highs[1][0])
                    {
                        htfBslList.Add(Highs[1][2]);
                        if (htfBslList.Count > 10) htfBslList.RemoveAt(0);
                    }
                    if (Lows[1][2] < Lows[1][4] && Lows[1][2] < Lows[1][3] &&
                        Lows[1][2] < Lows[1][1] && Lows[1][2] < Lows[1][0])
                    {
                        htfSslList.Add(Lows[1][2]);
                        if (htfSslList.Count > 10) htfSslList.RemoveAt(0);
                    }
                }
                return;
            }

            // === Series 2: 4H High/Low ===
            if (BarsInProgress == 2)
            {
                if (CurrentBars[2] >= 2)
                {
                    prev4hHigh = Highs[2][1];
                    prev4hLow = Lows[2][1];
                }
                return;
            }

            // === Series 3: Daily (no processing needed) ===
            if (BarsInProgress == 3)
                return;

            // Primary Series 0 (5-minute execution chart)
            if (BarsInProgress != 0)
                return;

            if (CurrentBars[0] < 25 || CurrentBars[1] < 50 || CurrentBars[3] < 2)
                return;

            DateTime barTime = Times[0][0];
            if (barTime.Date != lastTradeDate.Date)
            {
                lastTradeDate = barTime.Date;
                todayTradeCount = 0;
            }

            int timeNum = ToTime(barTime);
            double h0 = Highs[0][0], l0 = Lows[0][0], c0 = Closes[0][0], o0 = Opens[0][0];
            double h1 = Highs[0][1], l1 = Lows[0][1];
            double h2 = Highs[0][2], l2 = Lows[0][2];

            // === Session H/L Tracking ===
            int hh = barTime.Hour;
            int mm = barTime.Minute;
            int hhmm = hh * 100 + mm;

            bool isAsia = (hhmm >= 1800 || hhmm < 200);
            bool isLon = (hhmm >= 200 && hhmm < 800);
            bool isNyam = (hhmm >= 930 && hhmm < 1000);

            if (isAsia && !wasAsia) { asiaHigh = h0; asiaLow = l0; hasAsia = true; }
            else if (isAsia) { if (h0 > asiaHigh) asiaHigh = h0; if (l0 < asiaLow) asiaLow = l0; }
            wasAsia = isAsia;

            if (isLon && !wasLon) { lonHigh = h0; lonLow = l0; hasLon = true; }
            else if (isLon) { if (h0 > lonHigh) lonHigh = h0; if (l0 < lonLow) lonLow = l0; }
            wasLon = isLon;

            if (isNyam && !wasNyam) { nyamHigh = h0; nyamLow = l0; hasNyam = true; }
            else if (isNyam) { if (h0 > nyamHigh) nyamHigh = h0; if (l0 < nyamLow) nyamLow = l0; }
            wasNyam = isNyam;

            // === STEP 1: EOD FLATTEN (15:55 ET) ===
            if (timeNum >= FlattenBy * 100)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitLong("EOD Flatten", "Queen");
                    ExitLong("EOD Flatten", "Runner");
                    ExitShort("EOD Flatten", "Queen");
                    ExitShort("EOD Flatten", "Runner");
                }
                hasPendingLong = false;
                hasPendingShort = false;
                return;
            }

            // === STEP 2: QUEEN BE RATCHET (only after entry bar) ===
            if (Position.MarketPosition == MarketPosition.Long && !double.IsNaN(activeEntryPrice))
            {
                if (!queenFilled && !double.IsNaN(activeQueenTP) && CurrentBars[0] > entryBarIndex && h0 >= activeQueenTP)
                {
                    queenFilled = true;
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short && !double.IsNaN(activeEntryPrice))
            {
                if (!queenFilled && !double.IsNaN(activeQueenTP) && CurrentBars[0] > entryBarIndex && l0 <= activeQueenTP)
                {
                    queenFilled = true;
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }

            // === RTH Session ===
            bool inRth = timeNum >= EarliestEntry * 100 && timeNum <= LatestEntry * 100;
            bool canEnter = inRth && (todayTradeCount < MaxDailyTrades) && (Position.MarketPosition == MarketPosition.Flat);

            // Volume gate
            bool passesVol = volSma20[0] > 0 && Volume[0] >= (MinVolMult * volSma20[0]);

            // === STEP 3: PENDING ZONE FILL (detect touch, defer execution to next bar) ===
            if (longTriggered)
            {
                ExecutePackEntry(1, triggeredLongEntry, triggeredLongSL);
                longTriggered = false;
            }
            else if (hasPendingLong && canEnter && passesVol)
            {
                if (CurrentBars[0] > pendingLongArmedBar && (CurrentBars[0] - pendingLongArmedBar <= MaxRetestWaitBars))
                {
                    if (l0 <= pendingLongEntryPrice)
                    {
                        longTriggered = true;
                        triggeredLongEntry = pendingLongEntryPrice;
                        triggeredLongSL = pendingLongSL;
                        hasPendingLong = false;
                    }
                }
                else if (CurrentBars[0] - pendingLongArmedBar > MaxRetestWaitBars)
                {
                    hasPendingLong = false;
                }
            }

            if (shortTriggered)
            {
                ExecutePackEntry(-1, triggeredShortEntry, triggeredShortSL);
                shortTriggered = false;
            }
            else if (hasPendingShort && canEnter && passesVol)
            {
                if (CurrentBars[0] > pendingShortArmedBar && (CurrentBars[0] - pendingShortArmedBar <= MaxRetestWaitBars))
                {
                    if (h0 >= pendingShortEntryPrice)
                    {
                        shortTriggered = true;
                        triggeredShortEntry = pendingShortEntryPrice;
                        triggeredShortSL = pendingShortSL;
                        hasPendingShort = false;
                    }
                }
                else if (CurrentBars[0] - pendingShortArmedBar > MaxRetestWaitBars)
                {
                    hasPendingShort = false;
                }
            }

            // === STEP 4: SWEEP DETECTION (Daily + 4H + 1H + Sessions + Swings) ===
            bool bslSwept = false;
            bool sslSwept = false;
            string curLevel = string.Empty;

            // Daily PDH/PDL
            double pdh = Highs[3][1];
            double pdl = Lows[3][1];
            if (h0 > pdh && (c0 < pdh || o0 < pdh)) { bslSwept = true; curLevel = "PDH"; }
            if (l0 < pdl && (c0 > pdl || o0 > pdl)) { sslSwept = true; curLevel = "PDL"; }

            // 4H Sweeps
            if (Check4H && !bslSwept && !double.IsNaN(prev4hHigh))
            {
                if (h0 > prev4hHigh && (c0 < prev4hHigh || o0 < prev4hHigh)) { bslSwept = true; curLevel = "4H_BSL"; }
            }
            if (Check4H && !sslSwept && !double.IsNaN(prev4hLow))
            {
                if (l0 < prev4hLow && (c0 > prev4hLow || o0 > prev4hLow)) { sslSwept = true; curLevel = "4H_SSL"; }
            }

            // 1H Swings
            if (!bslSwept)
            {
                foreach (double bsl in htfBslList)
                {
                    if (h0 > bsl && (c0 < bsl || o0 < bsl)) { bslSwept = true; curLevel = "1H_BSL"; break; }
                }
            }
            if (!sslSwept)
            {
                foreach (double ssl in htfSslList)
                {
                    if (l0 < ssl && (c0 > ssl || o0 > ssl)) { sslSwept = true; curLevel = "1H_SSL"; break; }
                }
            }

            // Session Sweeps
            if (CheckSessions)
            {
                if (!bslSwept && hasAsia && !double.IsNaN(asiaHigh) && h0 > asiaHigh && (c0 < asiaHigh || o0 < asiaHigh)) { bslSwept = true; curLevel = "Asia_H"; }
                if (!sslSwept && hasAsia && !double.IsNaN(asiaLow) && l0 < asiaLow && (c0 > asiaLow || o0 > asiaLow)) { sslSwept = true; curLevel = "Asia_L"; }
                if (!bslSwept && hasLon && !double.IsNaN(lonHigh) && h0 > lonHigh && (c0 < lonHigh || o0 < lonHigh)) { bslSwept = true; curLevel = "Lon_H"; }
                if (!sslSwept && hasLon && !double.IsNaN(lonLow) && l0 < lonLow && (c0 > lonLow || o0 > lonLow)) { sslSwept = true; curLevel = "Lon_L"; }
                if (!bslSwept && hasNyam && !double.IsNaN(nyamHigh) && h0 > nyamHigh && (c0 < nyamHigh || o0 < nyamHigh)) { bslSwept = true; curLevel = "NYAM_H"; }
                if (!sslSwept && hasNyam && !double.IsNaN(nyamLow) && l0 < nyamLow && (c0 > nyamLow || o0 > nyamLow)) { sslSwept = true; curLevel = "NYAM_L"; }
            }

            // Intraday 3-bar fractal swings (on primary series)
            if (CurrentBars[0] >= 7)
            {
                if (!bslSwept && Highs[0][3] > Highs[0][5] && Highs[0][3] > Highs[0][4] &&
                    Highs[0][3] > Highs[0][2] && Highs[0][3] > Highs[0][1])
                {
                    double swH = Highs[0][3];
                    if (h0 > swH && c0 < swH) { bslSwept = true; curLevel = "Swing_H"; }
                }
                if (!sslSwept && Lows[0][3] < Lows[0][5] && Lows[0][3] < Lows[0][4] &&
                    Lows[0][3] < Lows[0][2] && Lows[0][3] < Lows[0][1])
                {
                    double swL = Lows[0][3];
                    if (l0 < swL && c0 > swL) { sslSwept = true; curLevel = "Swing_L"; }
                }
            }

            if (sslSwept) { hasBullSweep = true; bullSweepBar = CurrentBars[0]; sweepLevelName = curLevel; }
            if (bslSwept) { hasBearSweep = true; bearSweepBar = CurrentBars[0]; sweepLevelName = curLevel; }

            if (CurrentBars[0] - bullSweepBar > 25) hasBullSweep = false;
            if (CurrentBars[0] - bearSweepBar > 25) hasBearSweep = false;

            // === STEP 5: CANONICAL BACKWARD-WALKING CISD ===
            // Requires a minimum 3-candle opposing run for a valid CISD origin.
            // A 1-2 candle "run" produces an SL too close to the sweep = invalid setup.
            if (hasBullSweep && sslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);
                int runLen = 0;
                for (int k = 1; k <= Math.Min(25, CurrentBars[0]); k++)
                {
                    if (Closes[0][k] <= Opens[0][k])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[0][k], Closes[0][k]));
                        sLow = Math.Min(sLow, Math.Min(Opens[0][k], Closes[0][k]));
                        runLen++;
                    }
                    else break;
                }

                if (runLen >= 3)
                {
                    armedBullCisd = true;
                    armedBullHigh = sHigh;
                    armedCisdOriginSL = sLow;
                }
            }

            if (hasBearSweep && bslSwept)
            {
                double sHigh = Math.Max(o0, c0);
                double sLow = Math.Min(o0, c0);
                int runLen = 0;
                for (int k = 1; k <= Math.Min(25, CurrentBars[0]); k++)
                {
                    if (Closes[0][k] >= Opens[0][k])
                    {
                        sHigh = Math.Max(sHigh, Math.Max(Opens[0][k], Closes[0][k]));
                        sLow = Math.Min(sLow, Math.Min(Opens[0][k], Closes[0][k]));
                        runLen++;
                    }
                    else break;
                }

                if (runLen >= 3)
                {
                    armedBearCisd = true;
                    armedBearLow = sLow;
                    armedCisdOriginSL = sHigh;
                }
            }

            // === STEP 6: CISD CONFIRMATION + FVG TOUCH ENTRY ARMING ===
            bool bullCisdTrigger = false;
            bool bearCisdTrigger = false;

            if (armedBullCisd && !double.IsNaN(armedBullHigh) && c0 > armedBullHigh)
            {
                armedBullCisd = false;
                hasBullSweep = false;
                bullCisdTrigger = true;
                deliveryRegime = 1;
            }

            if (armedBearCisd && !double.IsNaN(armedBearLow) && c0 < armedBearLow)
            {
                armedBearCisd = false;
                hasBearSweep = false;
                bearCisdTrigger = true;
                deliveryRegime = -1;
            }

            bool newBullFvg = l0 > h2 && (l0 - h2) >= (2 * TickSize);
            bool newBearFvg = h0 < l2 && (l2 - h0) >= (2 * TickSize);

            // Long: CISD trigger OR continuation FVG in bull regime
            // Continuation FVG requires a recent CISD origin (within 25 bars)
            bool bullContFvg = deliveryRegime == 1 && newBullFvg && !double.IsNaN(armedCisdOriginSL) && (CurrentBars[0] - bullSweepBar <= 25);
            if ((bullCisdTrigger || bullContFvg) && !hasPendingLong && Position.MarketPosition == MarketPosition.Flat)
            {
                double zTop = newBullFvg ? l0 : armedBullHigh;
                double zBot = newBullFvg ? h2 : (armedBullHigh - (4 * TickSize));

                // FVG Touch entry = zTop (top of the FVG)
                double ePrice = zTop;

                // SL-4: CISD delivery origin (run LOW) minus 2 ticks. No fallback — if no CISD origin, skip.
                if (double.IsNaN(armedCisdOriginSL))
                    return;

                double slPrice = armedCisdOriginSL - (2 * TickSize);

                // Sanity: stop must be below entry for a long
                if (slPrice >= ePrice)
                    return;

                double riskBps = ((ePrice - slPrice) / ePrice) * 10000.0;
                if (riskBps >= 10.0 && riskBps <= MaxRiskBps)
                {
                    hasPendingLong = true;
                    pendingLongEntryPrice = ePrice;
                    pendingLongSL = slPrice;
                    pendingLongArmedBar = CurrentBars[0];
                }
            }

            // Short: CISD trigger OR continuation FVG in bear regime
            bool bearContFvg = deliveryRegime == -1 && newBearFvg && !double.IsNaN(armedCisdOriginSL) && (CurrentBars[0] - bearSweepBar <= 25);
            if ((bearCisdTrigger || bearContFvg) && !hasPendingShort && Position.MarketPosition == MarketPosition.Flat)
            {
                double zTop = newBearFvg ? l2 : (armedBearLow + (4 * TickSize));
                double zBot = newBearFvg ? h0 : armedBearLow;

                // FVG Touch entry = zBot (bottom of the FVG)
                double ePrice = zBot;

                // SL-4: CISD delivery origin (run HIGH) plus 2 ticks. No fallback — if no CISD origin, skip.
                if (double.IsNaN(armedCisdOriginSL))
                    return;

                double slPrice = armedCisdOriginSL + (2 * TickSize);

                // Sanity: stop must be above entry for a short
                if (slPrice <= ePrice)
                    return;

                double riskBps = ((slPrice - ePrice) / ePrice) * 10000.0;
                if (riskBps >= 10.0 && riskBps <= MaxRiskBps)
                {
                    hasPendingShort = true;
                    pendingShortEntryPrice = ePrice;
                    pendingShortSL = slPrice;
                    pendingShortArmedBar = CurrentBars[0];
                }
            }
        }

        private void ExecutePackEntry(int direction, double entryPrice, double stopPrice)
        {
            // Use actual fill price (next bar open) for risk check
            double fillPrice = Open[0];

            // Recalculate risk at execution time
            double actualRisk = direction == 1
                ? ((fillPrice - stopPrice) / fillPrice) * 10000.0
                : ((stopPrice - fillPrice) / fillPrice) * 10000.0;

            if (actualRisk < 10.0 || actualRisk > MaxRiskBps)
                return;

            activeEntryPrice = fillPrice;
            activeStopLoss = stopPrice;
            queenFilled = false;
            entryBarIndex = CurrentBars[0];
            todayTradeCount++;

            int contracts = CalcContracts(entryPrice, stopPrice);

            double distQueen = CalcBpsDistance(entryPrice, QueenBps);
            double distRunner = CalcBpsDistance(entryPrice, RunnerBps);

            if (direction == 1)
            {
                activeQueenTP = entryPrice + distQueen;
                activeRunnerTP = entryPrice + distRunner;

                EnterLong(contracts, "Queen");
                EnterLong(contracts, "Runner");

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);
                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);
            }
            else if (direction == -1)
            {
                activeQueenTP = entryPrice - distQueen;
                activeRunnerTP = entryPrice - distRunner;

                EnterShort(contracts, "Queen");
                EnterShort(contracts, "Runner");

                SetStopLoss("Queen", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Queen", CalculationMode.Price, activeQueenTP);
                SetStopLoss("Runner", CalculationMode.Price, activeStopLoss, false);
                SetProfitTarget("Runner", CalculationMode.Price, activeRunnerTP);
            }
        }
    }
}