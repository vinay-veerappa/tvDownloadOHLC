#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.TheStrat
{
    /// <summary>
    /// TheStratClassifier - Real-time candle classifier & setup detector for Rob Smith's 'The Strat'.
    /// Classifies each bar as:
    ///   1  = Inside Bar (Equilibrium)
    ///   21 = 2U (Directional Up)
    ///   22 = 2D (Directional Down)
    ///   3  = Outside Bar (Broadening)
    /// Also detects and visualizes 2-1-2 Continuations and 2-2 Reversals.
    /// </summary>
    public class TheStratClassifier : Indicator
    {
        #region Properties & Inputs
        [NinjaScriptProperty]
        [Display(Name = "Show Bar Numbers", Description = "Draw Strat numbers (1, 2U, 2D, 3) above/below candles", Order = 1, GroupName = "1. Display Settings")]
        public bool ShowBarNumbers { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Actionable Wick Markers", Description = "Highlight actionable hammer / shooter wicks", Order = 2, GroupName = "1. Display Settings")]
        public bool ShowActionableWicks { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Setup Arrows (2-1-2 & 2-2)", Description = "Draw Buy/Sell trigger arrows for Strat patterns", Order = 3, GroupName = "1. Display Settings")]
        public bool ShowSetupArrows { get; set; }

        [NinjaScriptProperty]
        [Range(0.50, 0.90)]
        [Display(Name = "Actionable Wick Threshold", Description = "Minimum wick ratio of total range for hammer/shooter", Order = 4, GroupName = "1. Display Settings")]
        public double WickThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Text Offset (Ticks)", Description = "Distance from candle high/low in ticks", Order = 5, GroupName = "1. Display Settings")]
        public int TextOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(8, 24)]
        [Display(Name = "Font Size", Description = "Font size for bar numbers", Order = 6, GroupName = "1. Display Settings")]
        public int FontSize { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "1 (Inside) Color", Order = 7, GroupName = "2. Colors")]
        public Brush ColorInside { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "2U (Up) Color", Order = 8, GroupName = "2. Colors")]
        public Brush ColorTwoUp { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "2D (Down) Color", Order = 9, GroupName = "2. Colors")]
        public Brush ColorTwoDown { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "3 (Outside) Color", Order = 10, GroupName = "2. Colors")]
        public Brush ColorOutside { get; set; }

        #region Exported Series
        [Browsable(false)]
        [XmlIgnore]
        public Series<int> StratTypeSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> ActionableWickSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> Signal212Series { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> Signal22Series { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> InsideBarStopSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> MagnitudeTargetSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> MagnitudeTarget2Series { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> TriggerPriceSeries { get; private set; }
        #endregion
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Rob Smith's The Strat Candle Classifier & Pattern Detector (1, 2U, 2D, 3, 2-1-2, 2-2)";
                Name = "TheStratClassifier";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                ShowBarNumbers = true;
                ShowActionableWicks = true;
                ShowSetupArrows = true;
                WickThreshold = 0.60;
                TextOffsetTicks = 6;
                FontSize = 11;

                ColorInside = Brushes.Gold;
                ColorTwoUp = Brushes.LimeGreen;
                ColorTwoDown = Brushes.Crimson;
                ColorOutside = Brushes.DeepSkyBlue;
            }
            else if (State == State.DataLoaded)
            {
                StratTypeSeries = new Series<int>(this);
                ActionableWickSeries = new Series<int>(this);
                Signal212Series = new Series<int>(this);
                Signal22Series = new Series<int>(this);
                InsideBarStopSeries = new Series<double>(this);
                MagnitudeTargetSeries = new Series<double>(this);
                MagnitudeTarget2Series = new Series<double>(this);
                TriggerPriceSeries = new Series<double>(this);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
            {
                StratTypeSeries[0] = 0;
                ActionableWickSeries[0] = 0;
                Signal212Series[0] = 0;
                Signal22Series[0] = 0;
                InsideBarStopSeries[0] = double.NaN;
                MagnitudeTargetSeries[0] = double.NaN;
                MagnitudeTarget2Series[0] = double.NaN;
                TriggerPriceSeries[0] = double.NaN;
                return;
            }

            double currHigh = High[0];
            double currLow = Low[0];
            double prevHigh = High[1];
            double prevLow = Low[1];

            // 1. Classification — single source: Strategies.Vinay.StratCore
            // (mirror of scripts/libs_py/the_strat/taxonomy.py).
            int stratType = Strategies.Vinay.StratCore.ClassifyBar(currHigh, currLow, prevHigh, prevLow);
            string labelText = "";
            Brush labelBrush = Brushes.Gray;
            bool drawAbove = false;

            if (stratType == Strategies.Vinay.StratCore.Inside)
            {
                labelText = "1";
                labelBrush = ColorInside;
                drawAbove = true;
            }
            else if (stratType == Strategies.Vinay.StratCore.TwoUp)
            {
                labelText = "2";
                labelBrush = ColorTwoUp;
                drawAbove = false;
            }
            else if (stratType == Strategies.Vinay.StratCore.TwoDown)
            {
                labelText = "2";
                labelBrush = ColorTwoDown;
                drawAbove = true;
            }
            else if (stratType == Strategies.Vinay.StratCore.Outside)
            {
                labelText = "3";
                labelBrush = ColorOutside;
                drawAbove = true;
            }

            StratTypeSeries[0] = stratType;

            // 2. Wick calculation — single source: StratCore.WickType.
            int wickType = Strategies.Vinay.StratCore.WickType(
                Open[0], Close[0], currHigh, currLow, WickThreshold, TickSize);

            ActionableWickSeries[0] = wickType;

            // 3. Render Bar Numbers
            if (ShowBarNumbers && !string.IsNullOrEmpty(labelText))
            {
                double textPrice = drawAbove ? currHigh + (TextOffsetTicks * TickSize) : currLow - (TextOffsetTicks * TickSize);
                string tag = "StratLabel_" + CurrentBar;
                Draw.Text(this, tag, false, labelText, 0, textPrice, 0, labelBrush, new SimpleFont("Arial", FontSize), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }

            // 4. Render Actionable Wick Markers
            if (ShowActionableWicks && wickType != 0)
            {
                string wickTag = "StratWick_" + CurrentBar;
                if (wickType == 1)
                    Draw.ArrowUp(this, wickTag, false, 0, currLow - (TextOffsetTicks * 2 * TickSize), Brushes.Lime);
                else
                    Draw.ArrowDown(this, wickTag, false, 0, currHigh + (TextOffsetTicks * 2 * TickSize), Brushes.Red);
            }

            // 5. Detect 2-1-2 Continuations & 2-2 Reversals
            int sig212 = 0;
            int sig22 = 0;
            double stopDist = double.NaN;
            double target = double.NaN;
            double target2 = double.NaN;
            double trigger = double.NaN;

            if (CurrentBar >= 3)
            {
                int type1 = StratTypeSeries[1];
                int type2 = StratTypeSeries[2];
                var cfg = Strategies.Vinay.StratConfig.Load();
                double minTgt = cfg.MinTargetPoints;
                double maxRisk = cfg.MaxRiskPoints;

                // 2-1-2 Setup: Bar[1] is Inside (1)
                if (type1 == 1)
                {
                    if (currHigh > prevHigh) // Bullish trigger
                    {
                        sig212 = 1;
                        stopDist = prevLow; // Stop below inside bar low
                        // Canonical measured-move target (mirror of targets.py):
                        // entry +/- max(inside_range, 0.5*prior_leg, min_target).
                        // Prior mag target (High[2]) sits ~1-2pts above entry vs
                        // 5-15pts risk — untradable RR, see targets.py header.
                        {
                            double entry = prevHigh + TickSize;
                            double leg = Math.Abs(Close[0] - Open[2]);
                            var m = Strategies.Vinay.StratCore.MeasuredTargets(
                                1, entry, prevLow - TickSize, prevHigh, prevLow,
                                leg, minTgt, maxRisk, TickSize);
                            target = m.Target1;
                            target2 = m.Target2;
                            trigger = entry;
                            // min-RR gate (mirror of signals.py): untradable RR emits no signal.
                            if (m.RrRatio < cfg.MinRrRatio) { sig212 = 0; sig22 = 0; target = double.NaN; target2 = double.NaN; trigger = double.NaN; stopDist = double.NaN; }
                        }
                        if (ShowSetupArrows)
                        {
                            string tag = "Strat212_Buy_" + CurrentBar;
                            Draw.ArrowUp(this, tag, false, 0, currLow - (TextOffsetTicks * 3 * TickSize), Brushes.Lime);
                            Draw.Text(this, tag + "_txt", false, "2-1-2 BUY", 0, currLow - (TextOffsetTicks * 5 * TickSize), 0, Brushes.Lime, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                    }
                    else if (currLow < prevLow) // Bearish trigger
                    {
                        sig212 = -1;
                        stopDist = prevHigh; // Stop above inside bar high
                        {
                            double entry = prevLow - TickSize;
                            double leg = Math.Abs(Close[0] - Open[2]);
                            var m = Strategies.Vinay.StratCore.MeasuredTargets(
                                -1, entry, prevHigh + TickSize, prevHigh, prevLow,
                                leg, minTgt, maxRisk, TickSize);
                            target = m.Target1;
                            target2 = m.Target2;
                            trigger = entry;
                            // min-RR gate (mirror of signals.py): untradable RR emits no signal.
                            if (m.RrRatio < cfg.MinRrRatio) { sig212 = 0; sig22 = 0; target = double.NaN; target2 = double.NaN; trigger = double.NaN; stopDist = double.NaN; }
                        }
                        if (ShowSetupArrows)
                        {
                            string tag = "Strat212_Sell_" + CurrentBar;
                            Draw.ArrowDown(this, tag, false, 0, currHigh + (TextOffsetTicks * 3 * TickSize), Brushes.Red);
                            Draw.Text(this, tag + "_txt", false, "2-1-2 SELL", 0, currHigh + (TextOffsetTicks * 5 * TickSize), 0, Brushes.Red, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        }
                    }
                }

                // 2-2 Reversal Setup: Bar[1] is 2D/2U
                if (type1 == 22 && currHigh > prevHigh) // 2D -> 2U Reversal
                {
                    sig22 = 1;
                    stopDist = prevLow;
                    {
                        double entry = prevHigh + TickSize;
                        double leg = Math.Abs(Close[0] - Open[1]);
                        var m = Strategies.Vinay.StratCore.MeasuredTargets(
                            1, entry, prevLow - TickSize, prevHigh, prevLow,
                            leg, minTgt, maxRisk, TickSize);
                        target = m.Target1;
                        target2 = m.Target2;
                        trigger = entry;
                        // min-RR gate (mirror of signals.py): untradable RR emits no signal.
                        if (m.RrRatio < cfg.MinRrRatio) { sig212 = 0; sig22 = 0; target = double.NaN; target2 = double.NaN; trigger = double.NaN; stopDist = double.NaN; }
                    }
                    if (ShowSetupArrows)
                    {
                        string tag = "Strat22_Buy_" + CurrentBar;
                        Draw.ArrowUp(this, tag, false, 0, currLow - (TextOffsetTicks * 3 * TickSize), Brushes.Gold);
                        Draw.Text(this, tag + "_txt", false, "2-2 REV BUY", 0, currLow - (TextOffsetTicks * 5 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                }
                else if (type1 == 21 && currLow < prevLow) // 2U -> 2D Reversal
                {
                    sig22 = -1;
                    stopDist = prevHigh;
                    {
                        double entry = prevLow - TickSize;
                        double leg = Math.Abs(Close[0] - Open[1]);
                        var m = Strategies.Vinay.StratCore.MeasuredTargets(
                            -1, entry, prevHigh + TickSize, prevHigh, prevLow,
                            leg, minTgt, maxRisk, TickSize);
                        target = m.Target1;
                        target2 = m.Target2;
                        trigger = entry;
                        // min-RR gate (mirror of signals.py): untradable RR emits no signal.
                        if (m.RrRatio < cfg.MinRrRatio) { sig212 = 0; sig22 = 0; target = double.NaN; target2 = double.NaN; trigger = double.NaN; stopDist = double.NaN; }
                    }
                    if (ShowSetupArrows)
                    {
                        string tag = "Strat22_Sell_" + CurrentBar;
                        Draw.ArrowDown(this, tag, false, 0, currHigh + (TextOffsetTicks * 3 * TickSize), Brushes.Cyan);
                        Draw.Text(this, tag + "_txt", false, "2-2 REV SELL", 0, currHigh + (TextOffsetTicks * 5 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                }
            }

            Signal212Series[0] = sig212;
            Signal22Series[0] = sig22;
            InsideBarStopSeries[0] = stopDist;
            MagnitudeTargetSeries[0] = target;
            MagnitudeTarget2Series[0] = target2;
            TriggerPriceSeries[0] = trigger;
        }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private TheStrat.TheStratClassifier[] cacheTheStratClassifier;
        public TheStrat.TheStratClassifier TheStratClassifier(double wickThreshold)
        {
            return TheStratClassifier(Input, wickThreshold);
        }

        public TheStrat.TheStratClassifier TheStratClassifier(ISeries<double> input, double wickThreshold)
        {
            if (cacheTheStratClassifier != null)
                for (int idx = 0; idx < cacheTheStratClassifier.Length; idx++)
                    if (cacheTheStratClassifier[idx] != null && cacheTheStratClassifier[idx].WickThreshold == wickThreshold && cacheTheStratClassifier[idx].EqualsInput(input))
                        return cacheTheStratClassifier[idx];
            return CacheIndicator<TheStrat.TheStratClassifier>(new TheStrat.TheStratClassifier() { WickThreshold = wickThreshold }, input, ref cacheTheStratClassifier);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.TheStrat.TheStratClassifier TheStratClassifier(double wickThreshold)
        {
            return indicator.TheStratClassifier(Input, wickThreshold);
        }

        public Indicators.TheStrat.TheStratClassifier TheStratClassifier(ISeries<double> input, double wickThreshold)
        {
            return indicator.TheStratClassifier(input, wickThreshold);
        }
    }
}
#endregion
