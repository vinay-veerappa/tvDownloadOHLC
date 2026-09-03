#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class ICTFVGCISDIndicator : Indicator
    {
        #region Custom Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant (0=Baseline, 1=V1, 2=V2)", Order = 0, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Mode (0=Market, 1=FVG Touch, 2=FVG CE 50%)", Order = 1, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Orderflow Filter", Order = 2, GroupName = "1. Strategy Variant")]
        public bool UseHtfFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter NY Lunch (12:00-13:30)", Order = 3, GroupName = "1. Strategy Variant")]
        public bool FilterLunch { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Require External Liquidity Sweep", Order = 4, GroupName = "1. Strategy Variant")]
        public bool RequireExternalSweep { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target (Bps)", Order = 5, GroupName = "2. Targets & Risk")]
        public double QueenTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (Bps)", Order = 6, GroupName = "2. Targets & Risk")]
        public double RunnerTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss (Bps)", Order = 7, GroupName = "2. Targets & Risk")]
        public double StopLossBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk Floor (Bps)", Order = 8, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 9, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable 50% Midline Reclaims", Order = 10, GroupName = "3. Midline Features")]
        public bool EnableMidlineReclaims { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Order = 11, GroupName = "4. Visuals")]
        public bool ShowVisualElements { get; set; }
        #endregion

        #region Exported Series
        [Browsable(false)]
        [XmlIgnore]
        public Series<int> SignalSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> StopLossSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> QueenTargetSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RunnerTargetSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> CisdLevelSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> LimitPriceSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> ActiveMidlineSeries { get; private set; }
        #endregion

        #region Internal State Fields
        private EMA htfEma;
        private List<double> bullFvgTops;
        private List<double> bullFvgBots;
        private List<double> bearFvgTops;
        private List<double> bearFvgBots;

        private List<double> invBearFvgTops;
        private List<double> invBearFvgBots;
        private List<double> invBullFvgTops;
        private List<double> invBullFvgBots;

        private int vibes;              // +1 bull / -1 bear / 0 uninit
        private double bagholderEntry;  // extreme open
        private double painThreshold;   // running extreme in bias direction
        private double deliveryOriginLow;
        private double deliveryOriginHigh;

        // Midline Tracking (Asia 18-02, London 02-08, P12 18-06, NY AM 09:30-10:00, PDM)
        private double curAsiaH, curAsiaL, lastAsiaH, lastAsiaL, asiaMid;
        private double curLondonH, curLondonL, lastLondonH, lastLondonL, londonMid;
        private double curP12H, curP12L, lastP12H, lastP12L, p12Mid;
        private double curNyAmH, curNyAmL, lastNyAmH, lastNyAmL;
        private double prevDayH, prevDayL, prevDayMid;
        private DateTime curTradingDate;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Institutional ICT Change in State of Delivery (CISD) & FVG Retest Strategy Engine with Basis Points Brackets.";
                Name = "ICTFVGCISDIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                Variant = 2;
                EntryMode = 1;                 // 1 = FVG Limit Retest
                UseHtfFilter = false;          // Disabled by default: reversal trades at extreme lows occur below the EMA
                FilterLunch = true;            // Blackout 12:00-13:30
                RequireExternalSweep = true;   // Mandatory HTF Liquidity Grab Filter
                QueenTargetBps = 10.0;         // +10 Basis Points
                RunnerTargetBps = 30.0;        // +30 Basis Points
                StopLossBps = 5.0;             // 5.0 Basis Points default stop ceiling
                MinRiskBps = 2.0;              // 2.0 Basis Points risk floor
                MaxRiskBps = 12.0;             // 12.0 Basis Points risk ceiling
                EnableMidlineReclaims = true;
                ShowVisualElements = true;
            }
            else if (State == State.Configure)
            {
                AddPlot(new Stroke(Brushes.DodgerBlue, 2), PlotStyle.Line, "ActiveCISDLevel");
                AddPlot(new Stroke(Brushes.DarkOrange, DashStyleHelper.Dash, 1), PlotStyle.Line, "SessionMidline");
            }
            else if (State == State.DataLoaded)
            {
                htfEma = EMA(50);
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);
                QueenTargetSeries = new Series<double>(this);
                RunnerTargetSeries = new Series<double>(this);
                CisdLevelSeries = new Series<double>(this);
                LimitPriceSeries = new Series<double>(this);
                ActiveMidlineSeries = new Series<double>(this);

                bullFvgTops = new List<double>();
                bullFvgBots = new List<double>();
                bearFvgTops = new List<double>();
                bearFvgBots = new List<double>();

                invBearFvgTops = new List<double>();
                invBearFvgBots = new List<double>();
                invBullFvgTops = new List<double>();
                invBullFvgBots = new List<double>();

                vibes = 0;
                bagholderEntry = double.NaN;
                painThreshold = double.NaN;
                deliveryOriginLow = double.NaN;
                deliveryOriginHigh = double.NaN;

                curAsiaH = double.NaN; curAsiaL = double.NaN; lastAsiaH = double.NaN; lastAsiaL = double.NaN; asiaMid = double.NaN;
                curLondonH = double.NaN; curLondonL = double.NaN; lastLondonH = double.NaN; lastLondonL = double.NaN; londonMid = double.NaN;
                curP12H = double.NaN; curP12L = double.NaN; lastP12H = double.NaN; lastP12L = double.NaN; p12Mid = double.NaN;
                curNyAmH = double.NaN; curNyAmL = double.NaN; lastNyAmH = double.NaN; lastNyAmL = double.NaN;
                prevDayH = double.NaN; prevDayL = double.NaN; prevDayMid = double.NaN;
                curTradingDate = DateTime.MinValue;
            }
        }

        private void ConsultCrystalBall(int bias, out double extremeOpen, out double originExtreme, out int extremeBarIdx)
        {
            extremeOpen = bias == 1 ? Low[1] : High[1];
            originExtreme = bias == 1 ? Low[1] : High[1];
            extremeBarIdx = CurrentBar - 1;
            int maxLookback = Math.Min(15, CurrentBar);

            for (int i = 1; i <= maxLookback; i++)
            {
                bool isOpposing = (bias == 1) ? (Close[i] < Open[i]) : (Close[i] > Open[i]);
                if (isOpposing)
                {
                    extremeOpen = Open[i];
                    extremeBarIdx = CurrentBar - i;
                    break;
                }
            }

            for (int i = 1; i <= Math.Min(10, CurrentBar); i++)
            {
                if (bias == 1 && Low[i] < originExtreme) originExtreme = Low[i];
                if (bias == -1 && High[i] > originExtreme) originExtreme = High[i];
            }
        }

        private void UpdateSessionMidlines(double h0, double l0, DateTime barTime)
        {
            int hhmm = ToTime(barTime) / 100;

            if (barTime.Date != curTradingDate)
            {
                if (curTradingDate != DateTime.MinValue)
                {
                    prevDayH = High[1];
                    prevDayL = Low[1];
                    for (int k = 1; k <= Math.Min(100, CurrentBar); k++)
                    {
                        if (Time[k].Date == curTradingDate)
                        {
                            prevDayH = Math.Max(prevDayH, High[k]);
                            prevDayL = Math.Min(prevDayL, Low[k]);
                        }
                    }
                    prevDayMid = (prevDayH + prevDayL) / 2.0;
                }
                curTradingDate = barTime.Date;
            }

            // Asia (18:00 - 02:00)
            if (hhmm == 1800)
            {
                curAsiaH = h0; curAsiaL = l0;
                curP12H = h0; curP12L = l0;
            }
            else if (hhmm > 1800 || hhmm < 200)
            {
                curAsiaH = double.IsNaN(curAsiaH) ? h0 : Math.Max(curAsiaH, h0);
                curAsiaL = double.IsNaN(curAsiaL) ? l0 : Math.Min(curAsiaL, l0);
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm == 200)
            {
                lastAsiaH = curAsiaH; lastAsiaL = curAsiaL;
                if (!double.IsNaN(lastAsiaH) && !double.IsNaN(lastAsiaL)) asiaMid = (lastAsiaH + lastAsiaL) / 2.0;
                curLondonH = h0; curLondonL = l0;
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm > 200 && hhmm < 600)
            {
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm == 600)
            {
                lastP12H = curP12H; lastP12L = curP12L;
                if (!double.IsNaN(lastP12H) && !double.IsNaN(lastP12L)) p12Mid = (lastP12H + lastP12L) / 2.0;
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
            }
            else if (hhmm > 600 && hhmm < 800)
            {
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
            }
            else if (hhmm == 800)
            {
                lastLondonH = curLondonH; lastLondonL = curLondonL;
                if (!double.IsNaN(lastLondonH) && !double.IsNaN(lastLondonL)) londonMid = (lastLondonH + lastLondonL) / 2.0;
            }

            // NY AM Initial Balance (09:30 - 10:00)
            if (hhmm == 930)
            {
                curNyAmH = h0; curNyAmL = l0;
            }
            else if (hhmm > 930 && hhmm <= 1000)
            {
                curNyAmH = double.IsNaN(curNyAmH) ? h0 : Math.Max(curNyAmH, h0);
                curNyAmL = double.IsNaN(curNyAmL) ? l0 : Math.Min(curNyAmL, l0);
            }
            else if (hhmm > 1000)
            {
                lastNyAmH = curNyAmH;
                lastNyAmL = curNyAmL;
            }
        }

        private bool CheckRejectionSweepBull(double level, int lookback)
        {
            if (double.IsNaN(level) || level <= 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
            {
                if (Low[k] <= level && Close[k] > level)
                    return true;
            }
            return false;
        }

        private bool CheckRejectionSweepBear(double level, int lookback)
        {
            if (double.IsNaN(level) || level <= 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
            {
                if (High[k] >= level && Close[k] < level)
                    return true;
            }
            return false;
        }

        private bool CheckFvgTapBull(int lookback)
        {
            if (bullFvgTops == null || bullFvgTops.Count == 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
            {
                for (int f = 0; f < bullFvgTops.Count; f++)
                {
                    if (Low[k] <= bullFvgTops[f] && Low[k] >= bullFvgBots[f])
                        return true;
                }
            }
            return false;
        }

        private bool CheckFvgTapBear(int lookback)
        {
            if (bearFvgTops == null || bearFvgTops.Count == 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
            {
                for (int f = 0; f < bearFvgTops.Count; f++)
                {
                    if (High[k] >= bearFvgBots[f] && High[k] <= bearFvgTops[f])
                        return true;
                }
            }
            return false;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 50)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                QueenTargetSeries[0] = double.NaN;
                RunnerTargetSeries[0] = double.NaN;
                CisdLevelSeries[0] = double.NaN;
                LimitPriceSeries[0] = double.NaN;
                ActiveMidlineSeries[0] = double.NaN;
                return;
            }

            double h0 = High[0], l0 = Low[0], c0 = Close[0], o0 = Open[0];
            double h1 = High[1], l1 = Low[1], c1 = Close[1], o1 = Open[1];
            double h2 = High[2], l2 = Low[2], c2 = Close[2], o2 = Open[2];
            int hhmm = ToTime(Time[0]) / 100;

            UpdateSessionMidlines(h0, l0, Time[0]);

            double activeMid = !double.IsNaN(londonMid) ? londonMid : (!double.IsNaN(p12Mid) ? p12Mid : prevDayMid);
            ActiveMidlineSeries[0] = activeMid;
            Values[1][0] = activeMid;

            // FVG Tracking
            bool isBullFvg = (l0 > h2);
            bool isBearFvg = (h0 < l2);

            if (isBullFvg)
            {
                bullFvgTops.Add(l0); bullFvgBots.Add(h2);
                if (bullFvgTops.Count > 50) { bullFvgTops.RemoveAt(0); bullFvgBots.RemoveAt(0); }
                invBullTopsAdd(l0, h2);
            }
            if (isBearFvg)
            {
                bearFvgTops.Add(l2); bearFvgBots.Add(h0);
                if (bearFvgTops.Count > 50) { bearFvgTops.RemoveAt(0); bearFvgBots.RemoveAt(0); }
                invBearTopsAdd(l2, h0);
            }

            // CISD Delivery Engine
            int candlePersonality = (c0 > o0) ? 1 : (c0 < o0) ? -1 : 0;
            if (vibes == 0)
            {
                vibes = candlePersonality != 0 ? candlePersonality : 1;
                double ep, oe; int eb;
                ConsultCrystalBall(vibes, out ep, out oe, out eb);
                bagholderEntry = ep;
                painThreshold = (vibes == 1) ? h0 : l0;
                deliveryOriginLow = oe;
                deliveryOriginHigh = oe;
            }

            if (vibes == 1 && h0 > painThreshold)
            {
                painThreshold = h0;
                double ep, oe; int eb;
                ConsultCrystalBall(1, out ep, out oe, out eb);
                bagholderEntry = ep;
                deliveryOriginLow = oe;
            }
            else if (vibes == -1 && l0 < painThreshold)
            {
                painThreshold = l0;
                double ep, oe; int eb;
                ConsultCrystalBall(-1, out ep, out oe, out eb);
                bagholderEntry = ep;
                deliveryOriginHigh = oe;
            }

            double activeLevel = bagholderEntry;
            CisdLevelSeries[0] = activeLevel;
            Values[0][0] = activeLevel;

            int signal = 0;
            double stopLoss = double.NaN;
            double target1 = double.NaN;
            double target2 = double.NaN;
            double limitPrice = double.NaN;

            // ──────────────────────────────────────────────────────────
            // AUTHENTIC ICT HTF LIQUIDITY GRAB ARCHITECTURE
            // 1. Time-Based Sweeps: PDH/PDL, London H/L, Asia H/L, NY AM Opening Range (09:30-10:00)
            // 2. Structural HTF: Hourly (H1) & 4-Hourly (H4) Highs/Lows
            // 3. Imbalance Taps: Bullish/Bearish HTF Fair Value Gaps
            // Rule: Rejection Sweep requires piercing level with wick and closing back inside!
            // ──────────────────────────────────────────────────────────
            int periodVal = (BarsPeriod != null && BarsPeriod.Value > 0) ? BarsPeriod.Value : 15;
            int h1Bars = Math.Max(1, (int)Math.Round(60.0 / periodVal));
            int h4Bars = h1Bars * 4;

            double h1High = double.MinValue, h1Low = double.MaxValue;
            for (int k = 1; k <= Math.Min(h1Bars, CurrentBar); k++)
            {
                h1High = Math.Max(h1High, High[k]);
                h1Low = Math.Min(h1Low, Low[k]);
            }

            double h4High = double.MinValue, h4Low = double.MaxValue;
            for (int k = 1; k <= Math.Min(h4Bars, CurrentBar); k++)
            {
                h4High = Math.Max(h4High, High[k]);
                h4Low = Math.Min(h4Low, Low[k]);
            }

            string sweepSourceBull = "";
            if (CheckRejectionSweepBull(prevDayL, 8)) sweepSourceBull = "PDL (" + prevDayL.ToString("F2") + ")";
            else if (CheckRejectionSweepBull(lastLondonL, 8)) sweepSourceBull = "London Low (" + lastLondonL.ToString("F2") + ")";
            else if (CheckRejectionSweepBull(lastAsiaL, 8)) sweepSourceBull = "Asia Low (" + lastAsiaL.ToString("F2") + ")";
            else if (CheckRejectionSweepBull(lastNyAmL, 8)) sweepSourceBull = "NY AM Low (" + lastNyAmL.ToString("F2") + ")";
            else if (CheckRejectionSweepBull(h1Low, 8)) sweepSourceBull = "1H Low (" + h1Low.ToString("F2") + ")";
            else if (CheckRejectionSweepBull(h4Low, 8)) sweepSourceBull = "4H Low (" + h4Low.ToString("F2") + ")";
            else if (CheckFvgTapBull(8)) sweepSourceBull = "HTF Bullish FVG Tap";

            bool hasExtSweepBull = !string.IsNullOrEmpty(sweepSourceBull);

            string sweepSourceBear = "";
            if (CheckRejectionSweepBear(prevDayH, 8)) sweepSourceBear = "PDH (" + prevDayH.ToString("F2") + ")";
            else if (CheckRejectionSweepBear(lastLondonH, 8)) sweepSourceBear = "London High (" + lastLondonH.ToString("F2") + ")";
            else if (CheckRejectionSweepBear(lastAsiaH, 8)) sweepSourceBear = "Asia High (" + lastAsiaH.ToString("F2") + ")";
            else if (CheckRejectionSweepBear(lastNyAmH, 8)) sweepSourceBear = "NY AM High (" + lastNyAmH.ToString("F2") + ")";
            else if (CheckRejectionSweepBear(h1High, 8)) sweepSourceBear = "1H High (" + h1High.ToString("F2") + ")";
            else if (CheckRejectionSweepBear(h4High, 8)) sweepSourceBear = "4H High (" + h4High.ToString("F2") + ")";
            else if (CheckFvgTapBear(8)) sweepSourceBear = "HTF Bearish FVG Tap";

            bool hasExtSweepBear = !string.IsNullOrEmpty(sweepSourceBear);

            bool inLunch = FilterLunch && (hhmm >= 1200 && hhmm <= 1330);

            // 1. STANDARD CISD REVERSAL TRIGGER
            if (vibes == -1 && c0 > activeLevel && !inLunch)
            {
                bool allowSignal = true;
                if (UseHtfFilter && c0 < htfEma[0]) allowSignal = false;
                if (RequireExternalSweep && !hasExtSweepBull) allowSignal = false;

                if (allowSignal)
                {
                    if (EntryMode == 1) limitPrice = isBullFvg ? h2 : activeLevel;
                    else if (EntryMode == 2) limitPrice = isBullFvg ? (l0 + h2) / 2.0 : (c0 + activeLevel) / 2.0;
                    else limitPrice = double.NaN;

                    double effectiveEntry = !double.IsNaN(limitPrice) ? limitPrice : c0;
                    stopLoss = effectiveEntry - (effectiveEntry * (StopLossBps / 10000.0));

                    double riskPts = effectiveEntry - stopLoss;
                    double riskBps = (riskPts / effectiveEntry) * 10000.0;

                    if (riskBps >= MinRiskBps && riskBps <= MaxRiskBps)
                    {
                        signal = 1;
                        vibes = 1;

                        double queenPts = effectiveEntry * (QueenTargetBps / 10000.0);
                        double runnerPts = effectiveEntry * (RunnerTargetBps / 10000.0);
                        target1 = effectiveEntry + queenPts;
                        target2 = effectiveEntry + Math.Max(runnerPts, (!double.IsNaN(activeMid) && activeMid > effectiveEntry ? activeMid : runnerPts));

                        if (ShowVisualElements)
                        {
                            string tag = "CISD_Bull_" + CurrentBar;
                            Draw.ArrowUp(this, tag, false, 0, l0 - (6 * TickSize), Brushes.Gold);
                            string modeStr = EntryMode == 0 ? "MKT" : (EntryMode == 1 ? "LMT FVG" : "LMT CE");
                            Draw.Text(this, tag + "_txt", false, $"BULLISH CISD BUY {modeStr}\nSwept: {sweepSourceBull}\nLevel: {activeLevel:F2} ({riskBps:F1}bps)", 0, l0 - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                            Draw.Line(this, tag + "_line", false, 6, activeLevel, 0, activeLevel, Brushes.Gold, DashStyleHelper.Solid, 2);
                        }

                        painThreshold = h0;
                        double ep, oe; int eb;
                        ConsultCrystalBall(1, out ep, out oe, out eb);
                        bagholderEntry = ep;
                        deliveryOriginLow = oe;
                    }
                }
            }
            else if (vibes == 1 && c0 < activeLevel && !inLunch)
            {
                bool allowSignal = true;
                if (UseHtfFilter && c0 > htfEma[0]) allowSignal = false;
                if (RequireExternalSweep && !hasExtSweepBear) allowSignal = false;

                if (allowSignal)
                {
                    if (EntryMode == 1) limitPrice = isBearFvg ? l2 : activeLevel;
                    else if (EntryMode == 2) limitPrice = isBearFvg ? (h0 + l2) / 2.0 : (c0 + activeLevel) / 2.0;
                    else limitPrice = double.NaN;

                    double effectiveEntry = !double.IsNaN(limitPrice) ? limitPrice : c0;
                    stopLoss = effectiveEntry + (effectiveEntry * (StopLossBps / 10000.0));

                    double riskPts = stopLoss - effectiveEntry;
                    double riskBps = (riskPts / effectiveEntry) * 10000.0;

                    if (riskBps >= MinRiskBps && riskBps <= MaxRiskBps)
                    {
                        signal = -1;
                        vibes = -1;

                        double queenPts = effectiveEntry * (QueenTargetBps / 10000.0);
                        double runnerPts = effectiveEntry * (RunnerTargetBps / 10000.0);
                        target1 = effectiveEntry - queenPts;
                        target2 = effectiveEntry - Math.Max(runnerPts, (!double.IsNaN(activeMid) && activeMid < effectiveEntry ? (effectiveEntry - activeMid) : runnerPts));

                        if (ShowVisualElements)
                        {
                            string tag = "CISD_Bear_" + CurrentBar;
                            Draw.ArrowDown(this, tag, false, 0, h0 + (6 * TickSize), Brushes.Cyan);
                            string modeStr = EntryMode == 0 ? "MKT" : (EntryMode == 1 ? "LMT FVG" : "LMT CE");
                            Draw.Text(this, tag + "_txt", false, $"BEARISH CISD SELL {modeStr}\nSwept: {sweepSourceBear}\nLevel: {activeLevel:F2} ({riskBps:F1}bps)", 0, h0 + (14 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                            Draw.Line(this, tag + "_line", false, 6, activeLevel, 0, activeLevel, Brushes.Cyan, DashStyleHelper.Solid, 2);
                        }

                        painThreshold = l0;
                        double ep, oe; int eb;
                        ConsultCrystalBall(-1, out ep, out oe, out eb);
                        bagholderEntry = ep;
                        deliveryOriginHigh = oe;
                    }
                }
            }

            // 2. 50% MIDLINE RECLAIM SETUP (Optional Confluence)
            if (EnableMidlineReclaims && signal == 0 && !double.IsNaN(activeMid) && !inLunch)
            {
                if (l0 < activeMid && c0 > activeMid && o0 > activeMid && c1 <= activeMid)
                {
                    double effectiveEntry = c0;
                    stopLoss = effectiveEntry - (effectiveEntry * (StopLossBps / 10000.0));
                    double riskPts = effectiveEntry - stopLoss;
                    double riskBps = (riskPts / effectiveEntry) * 10000.0;

                    if (riskBps >= MinRiskBps && riskBps <= MaxRiskBps)
                    {
                        signal = 1;
                        limitPrice = double.NaN;
                        target1 = effectiveEntry + (effectiveEntry * (QueenTargetBps / 10000.0));
                        target2 = effectiveEntry + (effectiveEntry * (RunnerTargetBps / 10000.0));

                        if (ShowVisualElements)
                        {
                            string tag = "MID_Reclaim_Bull_" + CurrentBar;
                            Draw.Dot(this, tag, false, 0, l0 - (4 * TickSize), Brushes.LightGreen);
                            Draw.Text(this, tag + "_txt", false, "MID RECLAIM", 0, l0 - (12 * TickSize), 0, Brushes.LightGreen, new SimpleFont("Arial", 8), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                    }
                }
                else if (h0 > activeMid && c0 < activeMid && o0 < activeMid && c1 >= activeMid)
                {
                    double effectiveEntry = c0;
                    stopLoss = effectiveEntry + (effectiveEntry * (StopLossBps / 10000.0));
                    double riskPts = stopLoss - effectiveEntry;
                    double riskBps = (riskPts / effectiveEntry) * 10000.0;

                    if (riskBps >= MinRiskBps && riskBps <= MaxRiskBps)
                    {
                        signal = -1;
                        limitPrice = double.NaN;
                        target1 = effectiveEntry - (effectiveEntry * (QueenTargetBps / 10000.0));
                        target2 = effectiveEntry - (effectiveEntry * (RunnerTargetBps / 10000.0));

                        if (ShowVisualElements)
                        {
                            string tag = "MID_Reclaim_Bear_" + CurrentBar;
                            Draw.Dot(this, tag, false, 0, h0 + (4 * TickSize), Brushes.OrangeRed);
                            Draw.Text(this, tag + "_txt", false, "MID RECLAIM", 0, h0 + (12 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 8), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                    }
                }
            }

            SignalSeries[0] = signal;
            StopLossSeries[0] = stopLoss;
            QueenTargetSeries[0] = target1;
            RunnerTargetSeries[0] = target2;
            LimitPriceSeries[0] = limitPrice;
        }

        private void invBullTopsAdd(double top, double bot)
        {
            invBullFvgTops.Add(top);
            invBullFvgBots.Add(bot);
            if (invBullFvgTops.Count > 50) { invBullFvgTops.RemoveAt(0); invBullFvgBots.RemoveAt(0); }
        }

        private void invBearTopsAdd(double top, double bot)
        {
            invBearFvgTops.Add(top);
            invBearFvgBots.Add(bot);
            if (invBearFvgTops.Count > 50) { invBearFvgTops.RemoveAt(0); invBearFvgBots.RemoveAt(0); }
        }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.ICTFVGCISDIndicator[] cacheICTFVGCISDIndicator;
        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, int entryMode, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims)
        {
            return ICTFVGCISDIndicator(Input, variant, entryMode, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, true);
        }

        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, int entryMode, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            if (cacheICTFVGCISDIndicator != null)
                for (int idx = 0; idx < cacheICTFVGCISDIndicator.Length; idx++)
                    if (cacheICTFVGCISDIndicator[idx] != null && cacheICTFVGCISDIndicator[idx].Variant == variant && cacheICTFVGCISDIndicator[idx].EntryMode == entryMode && cacheICTFVGCISDIndicator[idx].UseHtfFilter == useHtfFilter && cacheICTFVGCISDIndicator[idx].FilterLunch == filterLunch && cacheICTFVGCISDIndicator[idx].RequireExternalSweep == requireExternalSweep && cacheICTFVGCISDIndicator[idx].QueenTargetBps == queenTargetBps && cacheICTFVGCISDIndicator[idx].RunnerTargetBps == runnerTargetBps && cacheICTFVGCISDIndicator[idx].StopLossBps == stopLossBps && cacheICTFVGCISDIndicator[idx].MinRiskBps == minRiskBps && cacheICTFVGCISDIndicator[idx].MaxRiskBps == maxRiskBps && cacheICTFVGCISDIndicator[idx].EnableMidlineReclaims == enableMidlineReclaims && cacheICTFVGCISDIndicator[idx].ShowVisualElements == showVisualElements && cacheICTFVGCISDIndicator[idx].EqualsInput(input))
                        return cacheICTFVGCISDIndicator[idx];
            return CacheIndicator<Vinay.ICTFVGCISDIndicator>(new Vinay.ICTFVGCISDIndicator() { Variant = variant, EntryMode = entryMode, UseHtfFilter = useHtfFilter, FilterLunch = filterLunch, RequireExternalSweep = requireExternalSweep, QueenTargetBps = queenTargetBps, RunnerTargetBps = runnerTargetBps, StopLossBps = stopLossBps, MinRiskBps = minRiskBps, MaxRiskBps = maxRiskBps, EnableMidlineReclaims = enableMidlineReclaims, ShowVisualElements = showVisualElements }, input, ref cacheICTFVGCISDIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, int entryMode, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims)
        {
            return indicator.ICTFVGCISDIndicator(Input, variant, entryMode, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, true);
        }

        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, int entryMode, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            return indicator.ICTFVGCISDIndicator(input, variant, entryMode, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, showVisualElements);
        }
    }
}
#endregion
