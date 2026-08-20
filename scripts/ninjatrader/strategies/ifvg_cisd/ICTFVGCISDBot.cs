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
    public enum CISDStrategyVariant
    {
        Baseline_IFVG_CISD,
        Variant1_BPR_Or_IFVG_FVG,
        Variant2_DoubleFVG_NoIFVG
    }

    public class ICTFVGCISDBot : Strategy
    {
        #region Custom Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant", Order = 0, GroupName = "1. Strategy Variant")]
        public CISDStrategyVariant Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target R-Mult", Order = 1, GroupName = "2. Targets & Risk Management")]
        public double RMultTP1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target R-Mult", Order = 2, GroupName = "2. Targets & Risk Management")]
        public double RMultTP2 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk Points", Order = 3, GroupName = "2. Targets & Risk Management")]
        public double MinRiskPts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Points", Order = 4, GroupName = "2. Targets & Risk Management")]
        public double MaxRiskPts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fixed Contracts (2-Pack)", Order = 5, GroupName = "2. Targets & Risk Management")]
        public int DefaultContracts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Daily Trades", Order = 6, GroupName = "3. Execution Rules")]
        public int MaxDailyTrades { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter Lunch (11:30 - 13:30 ET)", Order = 7, GroupName = "3. Execution Rules")]
        public bool FilterLunch { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Convert Time To Eastern", Order = 8, GroupName = "4. Time Window")]
        public bool ConvertToET { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Earliest Entry (HHMM ET)", Order = 9, GroupName = "4. Time Window")]
        public int EarliestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Latest Entry (HHMM ET)", Order = 10, GroupName = "4. Time Window")]
        public int LatestEntry { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten By (HHMM ET)", Order = 11, GroupName = "4. Time Window")]
        public int FlattenBy { get; set; }
        #endregion

        #region Internal State Fields
        private ATR atr14;
        private static readonly TimeZoneInfo EasternZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

        // FVG Pool & Inversion Tracking
        private List<double> bullFvgTops;
        private List<double> bullFvgBots;
        private List<double> bearFvgTops;
        private List<double> bearFvgBots;

        // CISD & Delivery State Machine (tncylyv extreme-open + continuous re-anchor)
        private int vibes;              // +1 bull / -1 bear / 0 uninit
        private double bagholderEntry;  // extreme open of current delivery run
        private double painThreshold;   // running extreme in bias direction

        // Diagnostic CSV writer for CISD parity analysis
        private System.IO.StreamWriter diagCsv;
        private bool diagCsvHeaderWritten;

        // Current Delivery Leg Statistics
        private bool legHasBpr;
        private bool legHasIfvg;
        private int bullMoveFvgCount;
        private int bearMoveFvgCount;
        private double legOriginLow;
        private double legOriginHigh;
        private double legCisdLevel;
        private bool v2TriggeredInLeg;

        // Active Trade State
        private double activeEntryPrice;
        private double activeStopLoss;
        private double activeTP1;
        private double activeTP2;
        private bool tp1Filled;
        private int entryBarIndex;
        private int todayTradeCount;
        private DateTime lastTradeDate;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Institutional CISD / iFVG / BPR Multi-Variant Strategy Engine";
                Name = "ICTFVGCISDBot";
                Calculate = Calculate.OnBarClose;
                IsFillLimitOnTouch = true;
                EntriesPerDirection = 2;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;
                BarsRequiredToTrade = 20;
                IncludeTradeHistoryInBacktest = true;
                IsTradingHoursBreakLineVisible = false;

                Variant = CISDStrategyVariant.Variant2_DoubleFVG_NoIFVG;
                RMultTP1 = 1.0;
                RMultTP2 = 2.5;
                MinRiskPts = 6.0;
                MaxRiskPts = 50.0;
                DefaultContracts = 2;
                MaxDailyTrades = 2;
                FilterLunch = true;
                ConvertToET = false;
                EarliestEntry = 945;
                LatestEntry = 1530;
                FlattenBy = 1555;
            }
            else if (State == State.DataLoaded)
            {
                atr14 = ATR(14);

                string csvPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "ictfvgcisd_diag_" + Guid.NewGuid().ToString("N") + ".csv");
                diagCsv = new System.IO.StreamWriter(csvPath);
                diagCsvHeaderWritten = false;
                Print("[DIAG] CSV path: " + csvPath);

                bullFvgTops = new List<double>();
                bullFvgBots = new List<double>();
                bearFvgTops = new List<double>();
                bearFvgBots = new List<double>();

                vibes = 0;
                bagholderEntry = double.NaN;
                painThreshold = double.NaN;

                legHasBpr = false;
                legHasIfvg = false;
                bullMoveFvgCount = 0;
                bearMoveFvgCount = 0;
                legOriginLow = double.NaN;
                legOriginHigh = double.NaN;
                legCisdLevel = double.NaN;
                v2TriggeredInLeg = false;

                activeEntryPrice = double.NaN;
                activeStopLoss = double.NaN;
                activeTP1 = double.NaN;
                activeTP2 = double.NaN;
                tp1Filled = false;
                entryBarIndex = -1;

                todayTradeCount = 0;
                lastTradeDate = DateTime.MinValue;
            }
        }

        // ── tncylyv CISD scan helpers ──────────────────────────────────
        // ConsultCrystalBall: scan from current bar backward. Never returns NaN.
        private void ConsultCrystalBall(int bias, out double extremeOpen, out int extremeBarIdx)
        {
            int temporalShift = 0;
            extremeOpen = Open[0];
            extremeBarIdx = CurrentBar;
            int att = (Close[0] > Open[0]) ? 1 : (Close[0] < Open[0]) ? -1 : 0;
            if (att == 0 || att != bias)
                return;
            int maxLookback = Math.Min(500, CurrentBar);
            for (int i = 1; i <= maxLookback; i++)
            {
                att = (Close[i] > Open[i]) ? 1 : (Close[i] < Open[i]) ? -1 : 0;
                if (att == 0) continue;
                if (att != bias) break;
                temporalShift = i;
                if (bias == 1)
                {
                    if (Open[i] < extremeOpen) extremeOpen = Open[i];
                }
                else
                {
                    if (Open[i] > extremeOpen) extremeOpen = Open[i];
                }
            }
            int extremeShift = 0;
            for (int k = 0; k <= temporalShift; k++)
            {
                if (Open[k] == extremeOpen) { extremeShift = k; break; }
            }
            extremeBarIdx = CurrentBar - extremeShift;
        }

        // ArchaeologistJones: skip current bar, find first matching candle backward. May return NaN.
        private void ArchaeologistJones(int bias, out double extremeOpen, out int extremeBarIdx)
        {
            extremeOpen = double.NaN;
            extremeBarIdx = -1;
            bool artifactFound = false;
            int maxShift = -1;
            int maxLookback = Math.Min(500, CurrentBar);
            for (int j = 1; j <= maxLookback; j++)
            {
                int att = (Close[j] > Open[j]) ? 1 : (Close[j] < Open[j]) ? -1 : 0;
                if (att == 0) continue;
                bool isCorrectEra = (att == bias);
                if (!artifactFound)
                {
                    if (isCorrectEra)
                    {
                        artifactFound = true;
                        maxShift = j;
                        extremeOpen = Open[j];
                    }
                }
                else
                {
                    if (!isCorrectEra) break;
                    maxShift = j;
                    if (bias == 1)
                    {
                        if (Open[j] < extremeOpen) extremeOpen = Open[j];
                    }
                    else
                    {
                        if (Open[j] > extremeOpen) extremeOpen = Open[j];
                    }
                }
            }
            if (maxShift < 0) return;
            int extremeShift = maxShift;
            for (int k = 1; k <= maxShift; k++)
            {
                if (Open[k] == extremeOpen) { extremeShift = k; break; }
            }
            extremeBarIdx = CurrentBar - extremeShift;
        }

        private DateTime GetETTime(DateTime dt)
        {
            if (!ConvertToET) return dt;
            try
            {
                if (dt.Kind == DateTimeKind.Utc)
                    return TimeZoneInfo.ConvertTimeFromUtc(dt, EasternZone);
                else
                    return TimeZoneInfo.ConvertTime(dt, TimeZoneInfo.Local, EasternZone);
            }
            catch
            {
                return dt;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 20)
                return;

            DateTime rawTime = Time[0];
            DateTime etTime = GetETTime(rawTime);

            if (etTime.Date != lastTradeDate.Date)
            {
                lastTradeDate = etTime.Date;
                todayTradeCount = 0;
            }

            int timeNum = etTime.Hour * 10000 + etTime.Minute * 100 + etTime.Second;
            double h0 = High[0], l0 = Low[0], c0 = Close[0], o0 = Open[0];
            double h1 = High[1], l1 = Low[1], c1 = Close[1], o1 = Open[1];
            double h2 = High[2], l2 = Low[2], c2 = Close[2], o2 = Open[2];

            // ── STEP 1: EOD FLATTEN (15:55 ET to 16:55 ET) ──────────────────
            if (timeNum >= FlattenBy * 100 && timeNum < 170000)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitLong("EOD Flatten", "Queen");
                    ExitLong("EOD Flatten", "Runner");
                    ExitShort("EOD Flatten", "Queen");
                    ExitShort("EOD Flatten", "Runner");
                }
            }

            // ── STEP 2: QUEEN SCALE-OUT & BREAKEVEN LOCK ───────────────────
            if (Position.MarketPosition == MarketPosition.Long && !double.IsNaN(activeEntryPrice))
            {
                if (!tp1Filled && !double.IsNaN(activeTP1) && CurrentBar > entryBarIndex && h0 >= activeTP1)
                {
                    tp1Filled = true;
                    // Move stop on Runner to Breakeven
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short && !double.IsNaN(activeEntryPrice))
            {
                if (!tp1Filled && !double.IsNaN(activeTP1) && CurrentBar > entryBarIndex && l0 <= activeTP1)
                {
                    tp1Filled = true;
                    // Move stop on Runner to Breakeven
                    SetStopLoss("Runner", CalculationMode.Price, activeEntryPrice, false);
                }
            }

            // ── STEP 3: FVG & INVERSION & BPR DETECTION ────────────────────
            bool isBullFvg = (l0 > h2);
            bool isBearFvg = (h0 < l2);
            bool isBullBpr = false;
            bool isBearBpr = false;
            bool isBullIfvg = false;
            bool isBearIfvg = false;

            // Track Bullish FVG and check for BPR overlap against active Bearish FVGs
            if (isBullFvg)
            {
                // Canonical ICT body-gap merging: gaps between candle bodies 1-2 and/or 2-3
                // within the 3-candle FVG formation expand the FVG zone.
                double gTop = l0;
                double gBot = h2;

                // Merge left-side body gap (t-2 / t-1)
                double bodyTop2 = Math.Max(o2, c2);
                double bodyBot1 = Math.Min(o1, c1);
                if ((bodyBot1 > bodyTop2) && (h2 >= l1) && (bodyTop2 <= gTop + 1e-9) && (bodyBot1 >= gBot - 1e-9))
                {
                    gTop = Math.Max(gTop, bodyBot1);
                    gBot = Math.Min(gBot, bodyTop2);
                }

                // Merge right-side body gap (t-1 / t)
                double bodyTop1 = Math.Max(o1, c1);
                double bodyBot0 = Math.Min(o0, c0);
                if ((bodyBot0 > bodyTop1) && (h1 >= l0) && (bodyTop1 <= gTop + 1e-9) && (bodyBot0 >= gBot - 1e-9))
                {
                    gTop = Math.Max(gTop, bodyBot0);
                    gBot = Math.Min(gBot, bodyTop1);
                }

                for (int b = bearFvgTops.Count - 1; b >= 0; b--)
                {
                    double ovTop = Math.Min(gTop, bearFvgTops[b]);
                    double ovBot = Math.Max(gBot, bearFvgBots[b]);
                    if (ovTop > ovBot)
                    {
                        isBullBpr = true;
                        break;
                    }
                }
                bullFvgTops.Add(gTop);
                bullFvgBots.Add(gBot);
                if (bullFvgTops.Count > 50) { bullFvgTops.RemoveAt(0); bullFvgBots.RemoveAt(0); }
            }

            // Track Bearish FVG and check for BPR overlap against active Bullish FVGs
            if (isBearFvg)
            {
                // Canonical ICT body-gap merging: gaps between candle bodies 1-2 and/or 2-3
                // within the 3-candle FVG formation expand the FVG zone.
                double gTop = l2;
                double gBot = h0;

                // Merge left-side body gap (t-2 / t-1)
                double bodyBot2 = Math.Min(o2, c2);
                double bodyTop1 = Math.Max(o1, c1);
                if ((bodyTop1 < bodyBot2) && (l2 <= h1) && (bodyBot2 >= gBot - 1e-9) && (bodyTop1 <= gTop + 1e-9))
                {
                    gBot = Math.Min(gBot, bodyTop1);
                    gTop = Math.Max(gTop, bodyBot2);
                }

                // Merge right-side body gap (t-1 / t)
                double bodyBot1 = Math.Min(o1, c1);
                double bodyTop0 = Math.Max(o0, c0);
                if ((bodyTop0 < bodyBot1) && (l1 <= h0) && (bodyBot1 >= gBot - 1e-9) && (bodyTop0 <= gTop + 1e-9))
                {
                    gBot = Math.Min(gBot, bodyTop0);
                    gTop = Math.Max(gTop, bodyBot1);
                }

                for (int b = bullFvgTops.Count - 1; b >= 0; b--)
                {
                    double ovTop = Math.Min(gTop, bullFvgTops[b]);
                    double ovBot = Math.Max(gBot, bullFvgBots[b]);
                    if (ovTop > ovBot)
                    {
                        isBearBpr = true;
                        break;
                    }
                }
                bearFvgTops.Add(gTop);
                bearFvgBots.Add(gBot);
                if (bearFvgTops.Count > 50) { bearFvgTops.RemoveAt(0); bearFvgBots.RemoveAt(0); }
            }

            // Inversion FVG check (body close through opposing active FVGs)
            for (int b = bearFvgTops.Count - 1; b >= 0; b--)
            {
                if (c0 > bearFvgTops[b])
                {
                    isBullIfvg = true;
                    break;
                }
            }
            for (int b = bullFvgTops.Count - 1; b >= 0; b--)
            {
                if (c0 < bullFvgBots[b])
                {
                    isBearIfvg = true;
                    break;
                }
            }

            // ── STEP 4: CANONICAL INSTITUTIONAL CISD ENGINE ───────────────
            // tncylyv extreme-open + continuous re-anchor model.
            // One continuous level per regime; extreme open of the delivery run;
            // re-anchors on every new bias-direction extreme.
            // See docs/strategies/ifvg_cisd/CISD_ENGINE_AUDIT.md

            int candlePersonality = (c0 > o0) ? 1 : (c0 < o0) ? -1 : 0;

            // --- Init ---
            if (vibes == 0 && CurrentBar > 10)
            {
                int firstImpression = candlePersonality;
                if (firstImpression == 0)
                {
                    for (int k = 1; k <= Math.Min(50, CurrentBar); k++)
                    {
                        firstImpression = (Close[k] > Open[k]) ? 1 : (Close[k] < Open[k]) ? -1 : 0;
                        if (firstImpression != 0) break;
                    }
                }
                if (firstImpression != 0)
                {
                    vibes = firstImpression;
                    double ep; int eb;
                    ConsultCrystalBall(firstImpression, out ep, out eb);
                    bagholderEntry = ep;
                    painThreshold = (firstImpression == 1) ? h0 : l0;
                }
            }

            // --- Re-anchor on new extreme ---
            if (vibes == 1 && h0 > painThreshold)
            {
                painThreshold = h0;
                double ep; int eb;
                if (candlePersonality == 1)
                    ConsultCrystalBall(1, out ep, out eb);
                else
                    ArchaeologistJones(1, out ep, out eb);
                if (!double.IsNaN(ep))
                    bagholderEntry = ep;
            }
            else if (vibes == -1 && l0 < painThreshold)
            {
                painThreshold = l0;
                double ep; int eb;
                if (candlePersonality == -1)
                    ConsultCrystalBall(-1, out ep, out eb);
                else
                    ArchaeologistJones(-1, out ep, out eb);
                if (!double.IsNaN(ep))
                    bagholderEntry = ep;
            }

            // --- Flip detection ---
            bool shortsSqueezed = vibes == -1 && !double.IsNaN(bagholderEntry) && c0 > bagholderEntry;
            bool longsRekt = vibes == 1 && !double.IsNaN(bagholderEntry) && c0 < bagholderEntry;

            bool bullCisdTrigger = false;
            bool bearCisdTrigger = false;

            if (shortsSqueezed)
            {
                bullCisdTrigger = true;
                vibes = 1;
                legOriginLow = double.NaN;
                legOriginHigh = bagholderEntry;
                legCisdLevel = bagholderEntry;
                legHasBpr = isBullBpr;
                legHasIfvg = isBullIfvg;
                v2TriggeredInLeg = false;
                bullMoveFvgCount = 0;
                double ep; int eb;
                ConsultCrystalBall(1, out ep, out eb);
                bagholderEntry = ep;
                painThreshold = h0;
            }
            else if (longsRekt)
            {
                bearCisdTrigger = true;
                vibes = -1;
                legOriginLow = bagholderEntry;
                legOriginHigh = double.NaN;
                legCisdLevel = bagholderEntry;
                legHasBpr = isBearBpr;
                legHasIfvg = isBearIfvg;
                v2TriggeredInLeg = false;
                bearMoveFvgCount = 0;
                double ep; int eb;
                ConsultCrystalBall(-1, out ep, out eb);
                bagholderEntry = ep;
                painThreshold = l0;
            }

            // Accumulate FVGs in the active move
            if (vibes == 1 && isBullFvg) bullMoveFvgCount++;
            if (vibes == -1 && isBearFvg) bearMoveFvgCount++;

            // ── STEP 5: VARIANT SIGNAL EVALUATION ──────────────────────────
            bool signalLong = false;
            bool signalShort = false;
            double entryPrice = c0;
            double stopPrice = double.NaN;

            if (Variant == CISDStrategyVariant.Baseline_IFVG_CISD)
            {
                if (vibes == 1 && isBullIfvg)
                {
                    signalLong = true;
                    entryPrice = c0;
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, atr14[0] * 1.8));
                    stopPrice = entryPrice - risk;
                }
                else if (vibes == -1 && isBearIfvg)
                {
                    signalShort = true;
                    entryPrice = c0;
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, atr14[0] * 1.8));
                    stopPrice = entryPrice + risk;
                }
            }
            else if (Variant == CISDStrategyVariant.Variant1_BPR_Or_IFVG_FVG)
            {
                if (bullCisdTrigger && (legHasBpr || (legHasIfvg && bullMoveFvgCount >= 1)))
                {
                    signalLong = true;
                    entryPrice = !double.IsNaN(legCisdLevel) ? legCisdLevel : c0;
                    double rawStop = !double.IsNaN(legOriginLow) ? (legOriginLow - 2 * TickSize) : (l0 - 2 * TickSize);
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, entryPrice - rawStop));
                    stopPrice = entryPrice - risk;
                }
                else if (bearCisdTrigger && (legHasBpr || (legHasIfvg && bearMoveFvgCount >= 1)))
                {
                    signalShort = true;
                    entryPrice = !double.IsNaN(legCisdLevel) ? legCisdLevel : c0;
                    double rawStop = !double.IsNaN(legOriginHigh) ? (legOriginHigh + 2 * TickSize) : (h0 + 2 * TickSize);
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, rawStop - entryPrice));
                    stopPrice = entryPrice + risk;
                }
            }
            else if (Variant == CISDStrategyVariant.Variant2_DoubleFVG_NoIFVG)
            {
                if ((vibes == 1 || bullCisdTrigger) && !v2TriggeredInLeg && isBullFvg && bullMoveFvgCount >= 2)
                {
                    signalLong = true;
                    entryPrice = c0;
                    double rawStop = !double.IsNaN(legOriginLow) ? (legOriginLow - 2 * TickSize) : (l0 - 2 * TickSize);
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, entryPrice - rawStop));
                    stopPrice = entryPrice - risk;
                    v2TriggeredInLeg = true;
                }
                else if ((vibes == -1 || bearCisdTrigger) && !v2TriggeredInLeg && isBearFvg && bearMoveFvgCount >= 2)
                {
                    signalShort = true;
                    entryPrice = c0;
                    double rawStop = !double.IsNaN(legOriginHigh) ? (legOriginHigh + 2 * TickSize) : (h0 + 2 * TickSize);
                    double risk = Math.Max(MinRiskPts, Math.Min(MaxRiskPts, rawStop - entryPrice));
                    stopPrice = entryPrice + risk;
                    v2TriggeredInLeg = true;
                }
            }

            // ── STEP 6: EXECUTION FILTERS & ORDER PLACEMENT ────────────────
            bool inRth = (timeNum >= EarliestEntry * 100) && (timeNum <= LatestEntry * 100);
            if (FilterLunch)
            {
                bool isLunch = (timeNum >= 113000) && (timeNum <= 133000);
                if (isLunch) inRth = false;
            }

            bool canEnter = inRth && (todayTradeCount < MaxDailyTrades) && (Position.MarketPosition == MarketPosition.Flat);

            // Diagnostic CSV row for every bar during Aug 19 2026 morning session
            if (Time[0].Date == new DateTime(2026, 8, 19) && Time[0].Hour >= 9 && Time[0].Hour <= 12)
            {
                if (!diagCsvHeaderWritten)
                {
                    diagCsv.WriteLine("BarCloseTime,BarOpenTime,Open,High,Low,Close,CandlePersonality,Vibes,BagholderEntry,PainThreshold,BullCisdTrigger,CurrentRegime,BullFvgCount,IsBullFvg,SignalLong,CanEnter,InRth");
                    diagCsvHeaderWritten = true;
                }
                DateTime barOpenTime = Time[0].AddMinutes(-BarsPeriod.Value);
                diagCsv.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss},{1:yyyy-MM-dd HH:mm:ss},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12},{13},{14},{15},{16},{17}",
                    Time[0], barOpenTime, o0, h0, l0, c0, candlePersonality, vibes, bagholderEntry, painThreshold,
                    bullCisdTrigger ? 1 : 0, vibes, bullMoveFvgCount, isBullFvg ? 1 : 0, signalLong ? 1 : 0, canEnter ? 1 : 0, inRth ? 1 : 0));
                diagCsv.Flush();
            }

            if (canEnter && (signalLong || signalShort))
            {
                int qtyPerContract = Math.Max(1, DefaultContracts / 2);
                double riskPts = Math.Abs(entryPrice - stopPrice);
                int slTicks = (int)Math.Round(riskPts / TickSize);
                int tp1Ticks = (int)Math.Round((riskPts * RMultTP1) / TickSize);
                int tp2Ticks = (int)Math.Round((riskPts * RMultTP2) / TickSize);

                if (signalLong)
                {
                    activeEntryPrice = entryPrice;
                    activeStopLoss = stopPrice;
                    activeTP1 = entryPrice + (riskPts * RMultTP1);
                    activeTP2 = entryPrice + (riskPts * RMultTP2);
                    tp1Filled = false;
                    entryBarIndex = CurrentBar;

                    SetStopLoss("Queen", CalculationMode.Ticks, slTicks, false);
                    SetProfitTarget("Queen", CalculationMode.Ticks, tp1Ticks);

                    SetStopLoss("Runner", CalculationMode.Ticks, slTicks, false);
                    SetProfitTarget("Runner", CalculationMode.Ticks, tp2Ticks);

                    EnterLong(qtyPerContract, "Queen");
                    EnterLong(qtyPerContract, "Runner");

                    todayTradeCount++;
                }
                else if (signalShort)
                {
                    activeEntryPrice = entryPrice;
                    activeStopLoss = stopPrice;
                    activeTP1 = entryPrice - (riskPts * RMultTP1);
                    activeTP2 = entryPrice - (riskPts * RMultTP2);
                    tp1Filled = false;
                    entryBarIndex = CurrentBar;

                    SetStopLoss("Queen", CalculationMode.Ticks, slTicks, false);
                    SetProfitTarget("Queen", CalculationMode.Ticks, tp1Ticks);

                    SetStopLoss("Runner", CalculationMode.Ticks, slTicks, false);
                    SetProfitTarget("Runner", CalculationMode.Ticks, tp2Ticks);

                    EnterShort(qtyPerContract, "Queen");
                    EnterShort(qtyPerContract, "Runner");

                    todayTradeCount++;
                }
            }
        }
    }
}