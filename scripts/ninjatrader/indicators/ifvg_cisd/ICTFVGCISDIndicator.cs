#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
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
        [Display(Name = "Queen Target R-Mult", Order = 1, GroupName = "2. Targets & Risk")]
        public double RMultTP1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target R-Mult", Order = 2, GroupName = "2. Targets & Risk")]
        public double RMultTP2 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk (Bps)", Order = 3, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 4, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Order = 5, GroupName = "3. Visuals")]
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
        #endregion

        #region Internal State Fields
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

        private bool legHasBpr;
        private bool legHasIfvg;
        private int bullMoveFvgCount;
        private int bearMoveFvgCount;
        private double legOriginLow;
        private double legOriginHigh;
        private double legCisdLevel;
        private double legCrossedLevel;
        private bool v2TriggeredInLeg;
        private int priorBearFvgCount;
        private int priorBullFvgCount;

        private List<double> legBullFvgBots;
        private List<double> legBearFvgTops;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Institutional ICT Change in State of Delivery (CISD) & iFVG Indicator with visual levels and exported signals.";
                Name = "ICTFVGCISDIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                Variant = 2; // Default to V2 (BPR / Multiple FVGs)
                RMultTP1 = 1.0;
                RMultTP2 = 2.5;
                MinRiskBps = 2.0;
                MaxRiskBps = 15.0;
                ShowVisualElements = true;

                AddPlot(new Stroke(Brushes.Gold, 2), PlotStyle.Line, "CisdLevel");
            }
            else if (State == State.DataLoaded)
            {
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);
                QueenTargetSeries = new Series<double>(this);
                RunnerTargetSeries = new Series<double>(this);
                CisdLevelSeries = new Series<double>(this);

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

                legHasBpr = false;
                legHasIfvg = false;
                bullMoveFvgCount = 0;
                bearMoveFvgCount = 0;
                legOriginLow = double.NaN;
                legOriginHigh = double.NaN;
                legCisdLevel = double.NaN;
                legCrossedLevel = double.NaN;
                v2TriggeredInLeg = false;
                priorBearFvgCount = 0;
                priorBullFvgCount = 0;

                legBullFvgBots = new List<double>();
                legBearFvgTops = new List<double>();
            }
        }

        private void ConsultCrystalBall(int bias, out double extremeOpen, out int extremeBarIdx)
        {
            int temporalShift = 0;
            for (int i = 1; i <= Math.Min(50, CurrentBar); i++)
            {
                bool isCorrectEra = (bias == 1) ? (Close[i] > Open[i]) : (Close[i] < Open[i]);
                if (isCorrectEra) { temporalShift = i; break; }
            }
            extremeOpen = Open[temporalShift];
            int maxShift = -1;
            for (int j = temporalShift; j <= Math.Min(50, CurrentBar); j++)
            {
                bool isCorrectEra = (bias == 1) ? (Close[j] > Open[j]) : (Close[j] < Open[j]);
                if (Variant == 0)
                {
                    if (isCorrectEra)
                    {
                        maxShift = j;
                        if (bias == 1 && Open[j] < extremeOpen) extremeOpen = Open[j];
                        if (bias == -1 && Open[j] > extremeOpen) extremeOpen = Open[j];
                    }
                }
                else
                {
                    if (!isCorrectEra) break;
                    maxShift = j;
                    if (bias == 1 && Open[j] < extremeOpen) extremeOpen = Open[j];
                    if (bias == -1 && Open[j] > extremeOpen) extremeOpen = Open[j];
                }
            }
            if (maxShift < 0) { extremeBarIdx = CurrentBar; return; }
            int extremeShift = maxShift;
            for (int k = 1; k <= maxShift; k++)
            {
                if (Open[k] == extremeOpen) { extremeShift = k; break; }
            }
            extremeBarIdx = CurrentBar - extremeShift;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 20)
            {
                SignalSeries[0] = 0;
                StopLossSeries[0] = double.NaN;
                QueenTargetSeries[0] = double.NaN;
                RunnerTargetSeries[0] = double.NaN;
                CisdLevelSeries[0] = double.NaN;
                return;
            }

            double h0 = High[0], l0 = Low[0], c0 = Close[0], o0 = Open[0];
            double h1 = High[1], l1 = Low[1], c1 = Close[1], o1 = Open[1];
            double h2 = High[2], l2 = Low[2], c2 = Close[2], o2 = Open[2];

            // FVG Detection (3-bar gap)
            bool isBullFvg = (l0 > h2);
            bool isBearFvg = (h0 < l2);
            bool isBullBpr = false;
            bool isBearBpr = false;
            bool isBullIfvg = false;
            bool isBearIfvg = false;

            if (isBullFvg)
            {
                double gTop = l0;
                double gBot = h2;
                for (int b = bearFvgTops.Count - 1; b >= 0; b--)
                {
                    if (Math.Min(gTop, bearFvgTops[b]) > Math.Max(gBot, bearFvgBots[b]))
                    {
                        isBullBpr = true;
                        break;
                    }
                }
                bullFvgTops.Add(gTop);
                bullFvgBots.Add(gBot);
                if (bullFvgTops.Count > 50) { bullFvgTops.RemoveAt(0); bullFvgBots.RemoveAt(0); }
                invBullTopsAdd(gTop, gBot);
            }

            if (isBearFvg)
            {
                double gTop = l2;
                double gBot = h0;
                for (int b = bullFvgTops.Count - 1; b >= 0; b--)
                {
                    if (Math.Min(gTop, bullFvgTops[b]) > Math.Max(gBot, bullFvgBots[b]))
                    {
                        isBearBpr = true;
                        break;
                    }
                }
                bearFvgTops.Add(gTop);
                bearFvgBots.Add(gBot);
                if (bearFvgTops.Count > 50) { bearFvgTops.RemoveAt(0); bearFvgBots.RemoveAt(0); }
                invBearTopsAdd(gTop, gBot);
            }

            // Inversion check
            for (int b = invBearFvgTops.Count - 1; b >= 0; b--)
            {
                if (c0 > invBearFvgTops[b] && c1 <= invBearFvgTops[b])
                {
                    isBullIfvg = true;
                    invBearFvgTops.RemoveAt(b);
                    invBearFvgBots.RemoveAt(b);
                    break;
                }
            }
            for (int b = invBullFvgBots.Count - 1; b >= 0; b--)
            {
                if (c0 < invBullFvgBots[b] && c1 >= invBullFvgBots[b])
                {
                    isBearIfvg = true;
                    invBullFvgTops.RemoveAt(b);
                    invBullFvgBots.RemoveAt(b);
                    break;
                }
            }

            // CISD Delivery Engine
            int candlePersonality = (c0 > o0) ? 1 : (c0 < o0) ? -1 : 0;
            if (vibes == 0)
            {
                vibes = candlePersonality != 0 ? candlePersonality : 1;
                double ep; int eb;
                ConsultCrystalBall(vibes, out ep, out eb);
                bagholderEntry = ep;
                painThreshold = (vibes == 1) ? h0 : l0;
            }

            if (vibes == 1 && h0 > painThreshold)
            {
                painThreshold = h0;
                double ep; int eb;
                ConsultCrystalBall(1, out ep, out eb);
                bagholderEntry = ep;
            }
            else if (vibes == -1 && l0 < painThreshold)
            {
                painThreshold = l0;
                double ep; int eb;
                ConsultCrystalBall(-1, out ep, out eb);
                bagholderEntry = ep;
            }

            double activeLevel = bagholderEntry;
            CisdLevelSeries[0] = activeLevel;
            Values[0][0] = activeLevel;

            int signal = 0;
            double stopLoss = double.NaN;
            double target1 = double.NaN;
            double target2 = double.NaN;

            // CISD Cross Detection
            if (vibes == -1 && c0 > bagholderEntry && c1 <= bagholderEntry)
            {
                // Bullish CISD Reversal Trigger
                signal = 1;
                vibes = 1;
                stopLoss = Low[1]; // Prior swing low / trigger bar low
                for (int k = 1; k <= 5; k++) if (Low[k] < stopLoss) stopLoss = Low[k];

                double riskPts = Math.Max(c0 - stopLoss, 10.0);
                double bpsPts = c0 * 0.0010;
                target1 = c0 + Math.Max(bpsPts, riskPts * RMultTP1);
                target2 = c0 + (riskPts * RMultTP2);

                if (ShowVisualElements)
                {
                    string tag = "CISD_Bull_" + CurrentBar;
                    Draw.ArrowUp(this, tag, false, 0, l0 - (6 * TickSize), Brushes.Gold);
                    Draw.Text(this, tag + "_txt", false, "CISD BUY", 0, l0 - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 10), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }

                painThreshold = h0;
                double ep; int eb;
                ConsultCrystalBall(1, out ep, out eb);
                bagholderEntry = ep;
            }
            else if (vibes == 1 && c0 < bagholderEntry && c1 >= bagholderEntry)
            {
                // Bearish CISD Reversal Trigger
                signal = -1;
                vibes = -1;
                stopLoss = High[1]; // Prior swing high
                for (int k = 1; k <= 5; k++) if (High[k] > stopLoss) stopLoss = High[k];

                double riskPts = Math.Max(stopLoss - c0, 10.0);
                double bpsPts = c0 * 0.0010;
                target1 = c0 - Math.Max(bpsPts, riskPts * RMultTP1);
                target2 = c0 - (riskPts * RMultTP2);

                if (ShowVisualElements)
                {
                    string tag = "CISD_Bear_" + CurrentBar;
                    Draw.ArrowDown(this, tag, false, 0, h0 + (6 * TickSize), Brushes.Cyan);
                    Draw.Text(this, tag + "_txt", false, "CISD SELL", 0, h0 + (14 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 10), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }

                painThreshold = l0;
                double ep; int eb;
                ConsultCrystalBall(-1, out ep, out eb);
                bagholderEntry = ep;
            }

            SignalSeries[0] = signal;
            StopLossSeries[0] = stopLoss;
            QueenTargetSeries[0] = target1;
            RunnerTargetSeries[0] = target2;
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
        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, double rMultTP1, double rMultTP2, double minRiskBps, double maxRiskBps)
        {
            return ICTFVGCISDIndicator(Input, variant, rMultTP1, rMultTP2, minRiskBps, maxRiskBps, true);
        }

        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, double rMultTP1, double rMultTP2, double minRiskBps, double maxRiskBps, bool showVisualElements)
        {
            if (cacheICTFVGCISDIndicator != null)
                for (int idx = 0; idx < cacheICTFVGCISDIndicator.Length; idx++)
                    if (cacheICTFVGCISDIndicator[idx] != null && cacheICTFVGCISDIndicator[idx].Variant == variant && cacheICTFVGCISDIndicator[idx].RMultTP1 == rMultTP1 && cacheICTFVGCISDIndicator[idx].RMultTP2 == rMultTP2 && cacheICTFVGCISDIndicator[idx].MinRiskBps == minRiskBps && cacheICTFVGCISDIndicator[idx].MaxRiskBps == maxRiskBps && cacheICTFVGCISDIndicator[idx].ShowVisualElements == showVisualElements && cacheICTFVGCISDIndicator[idx].EqualsInput(input))
                        return cacheICTFVGCISDIndicator[idx];
            return CacheIndicator<Vinay.ICTFVGCISDIndicator>(new Vinay.ICTFVGCISDIndicator() { Variant = variant, RMultTP1 = rMultTP1, RMultTP2 = rMultTP2, MinRiskBps = minRiskBps, MaxRiskBps = maxRiskBps, ShowVisualElements = showVisualElements }, input, ref cacheICTFVGCISDIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, double rMultTP1, double rMultTP2, double minRiskBps, double maxRiskBps)
        {
            return indicator.ICTFVGCISDIndicator(Input, variant, rMultTP1, rMultTP2, minRiskBps, maxRiskBps, true);
        }

        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, double rMultTP1, double rMultTP2, double minRiskBps, double maxRiskBps, bool showVisualElements)
        {
            return indicator.ICTFVGCISDIndicator(input, variant, rMultTP1, rMultTP2, minRiskBps, maxRiskBps, showVisualElements);
        }
    }
}
#endregion
