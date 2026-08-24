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
    /// TheStratClassifier - Real-time candle classifier for Rob Smith's 'The Strat'.
    /// Classifies each bar as:
    ///   1  = Inside Bar (Equilibrium)
    ///   21 = 2U (Directional Up)
    ///   22 = 2D (Directional Down)
    ///   3  = Outside Bar (Broadening)
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
        [Range(0.50, 0.90)]
        [Display(Name = "Actionable Wick Threshold", Description = "Minimum wick ratio of total range for hammer/shooter", Order = 3, GroupName = "1. Display Settings")]
        public double WickThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Text Offset (Ticks)", Description = "Distance from candle high/low in ticks", Order = 4, GroupName = "1. Display Settings")]
        public int TextOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(8, 24)]
        [Display(Name = "Font Size", Description = "Font size for bar numbers", Order = 5, GroupName = "1. Display Settings")]
        public int FontSize { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "1 (Inside) Color", Order = 6, GroupName = "2. Colors")]
        public Brush ColorInside { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "2U (Up) Color", Order = 7, GroupName = "2. Colors")]
        public Brush ColorTwoUp { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "2D (Down) Color", Order = 8, GroupName = "2. Colors")]
        public Brush ColorTwoDown { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "3 (Outside) Color", Order = 9, GroupName = "2. Colors")]
        public Brush ColorOutside { get; set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> StratTypeSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> ActionableWickSeries { get; private set; }
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Rob Smith's The Strat Candle Classifier (1, 2U, 2D, 3 & Actionable Wicks)";
                Name = "TheStratClassifier";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                ShowBarNumbers = true;
                ShowActionableWicks = true;
                WickThreshold = 0.60;
                TextOffsetTicks = 6;
                FontSize = 11;

                ColorInside = Brushes.Gold;
                ColorTwoUp = Brushes.LimeGreen;
                ColorTwoDown = Brushes.Crimson;
                ColorOutside = Brushes.MediumOrchid;
            }
            else if (State == State.DataLoaded)
            {
                StratTypeSeries = new Series<int>(this);
                ActionableWickSeries = new Series<int>(this);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
            {
                StratTypeSeries[0] = 0;
                ActionableWickSeries[0] = 0;
                return;
            }

            double currHigh = High[0];
            double currLow = Low[0];
            double prevHigh = High[1];
            double prevLow = Low[1];

            bool isHigher = currHigh > prevHigh;
            bool isLower = currLow < prevLow;

            int stratType = 0;
            string labelText = "";
            Brush labelBrush = Brushes.Gray;
            bool drawAbove = false;

            // Classification
            if (!isHigher && !isLower)
            {
                // 1: Inside bar
                stratType = 1;
                labelText = "1";
                labelBrush = ColorInside;
                drawAbove = true;
            }
            else if (isHigher && !isLower)
            {
                // 2U: Directional Up
                stratType = 21;
                labelText = "2";
                labelBrush = ColorTwoUp;
                drawAbove = false;
            }
            else if (isLower && !isHigher)
            {
                // 2D: Directional Down
                stratType = 22;
                labelText = "2";
                labelBrush = ColorTwoDown;
                drawAbove = true;
            }
            else
            {
                // 3: Outside bar
                stratType = 3;
                labelText = "3";
                labelBrush = ColorOutside;
                drawAbove = true;
            }

            StratTypeSeries[0] = stratType;

            // Wick calculation
            double totalRange = currHigh - currLow;
            int wickType = 0; // 1 = Hammer, -1 = Shooter, 0 = None

            if (totalRange > TickSize)
            {
                double bodyTop = Math.Max(Open[0], Close[0]);
                double bodyBottom = Math.Min(Open[0], Close[0]);
                double upperWick = currHigh - bodyTop;
                double lowerWick = bodyBottom - currLow;

                double upperRatio = upperWick / totalRange;
                double lowerRatio = lowerWick / totalRange;

                if (lowerRatio >= WickThreshold && Close[0] >= (currLow + 0.5 * totalRange))
                {
                    wickType = 1; // Bullish Hammer
                }
                else if (upperRatio >= WickThreshold && Close[0] <= (currLow + 0.5 * totalRange))
                {
                    wickType = -1; // Bearish Shooter
                }
            }

            ActionableWickSeries[0] = wickType;

            // Render numbers on chart
            if (ShowBarNumbers && !string.IsNullOrEmpty(labelText))
            {
                double textPrice = drawAbove ? currHigh + (TextOffsetTicks * TickSize) : currLow - (TextOffsetTicks * TickSize);
                string tag = "StratLabel_" + CurrentBar;
                Draw.Text(this, tag, false, labelText, 0, textPrice, 0, labelBrush, new SimpleFont("Arial", FontSize), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
            }

            // Render actionable wick markers
            if (ShowActionableWicks && wickType != 0)
            {
                string wickTag = "StratWick_" + CurrentBar;
                if (wickType == 1)
                {
                    Draw.ArrowUp(this, wickTag, false, 0, currLow - (TextOffsetTicks * 2 * TickSize), Brushes.Lime);
                }
                else
                {
                    Draw.ArrowDown(this, wickTag, false, 0, currHigh + (TextOffsetTicks * 2 * TickSize), Brushes.Red);
                }
            }
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
