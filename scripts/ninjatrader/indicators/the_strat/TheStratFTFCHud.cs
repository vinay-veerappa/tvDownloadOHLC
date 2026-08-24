#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.TheStrat
{
    /// <summary>
    /// TheStratFTFCHud - Real-Time Full Time Frame Continuity (FTFC) Dashboard for NinjaTrader 8.
    /// Tracks open vs. current price direction across: Day, 60m, 15m, 5m.
    /// Renders a HUD table in the top or bottom corner showing green/red states and aggregate FTFC score.
    /// </summary>
    public class TheStratFTFCHud : Indicator
    {
        #region Properties & Inputs
        [NinjaScriptProperty]
        [Display(Name = "Show Dashboard HUD", Description = "Draw real-time FTFC dashboard on chart", Order = 1, GroupName = "Dashboard Settings")]
        public bool ShowHud { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Text Position", Description = "HUD anchor corner", Order = 2, GroupName = "Dashboard Settings")]
        public TextPosition HudPosition { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Font Size", Description = "Dashboard font size", Order = 3, GroupName = "Dashboard Settings")]
        public int FontSize { get; set; }

        [Browsable(false)]
        [XmlIgnore]
        public int FTFCScore { get; private set; } // +4 (Full Bull) to -4 (Full Bear)
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Rob Smith's The Strat FTFC Multi-Timeframe HUD Dashboard";
                Name = "TheStratFTFCHud";
                Calculate = Calculate.OnPriceChange;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                ShowHud = true;
                HudPosition = TextPosition.TopRight;
                FontSize = 11;
            }
            else if (State == State.Configure)
            {
                // Add higher timeframe data series
                // BarsArray[0] = Primary Chart Timeframe
                // BarsArray[1] = 5-minute
                AddDataSeries(BarsPeriodType.Minute, 5);
                // BarsArray[2] = 15-minute
                AddDataSeries(BarsPeriodType.Minute, 15);
                // BarsArray[3] = 60-minute
                AddDataSeries(BarsPeriodType.Minute, 60);
                // BarsArray[4] = Daily
                AddDataSeries(BarsPeriodType.Day, 1);
            }
        }

        protected override void OnBarUpdate()
        {
            // Only evaluate when all series have data
            if (CurrentBars[0] < 1 || CurrentBars[1] < 1 || CurrentBars[2] < 1 || CurrentBars[3] < 1 || CurrentBars[4] < 1)
                return;

            // Only run on the primary bar update
            if (BarsInProgress != 0)
                return;

            double currPrice = Closes[0][0];

            // 5M direction
            double o5m = Opens[1][0];
            string d5m = currPrice > o5m ? "G" : (currPrice < o5m ? "R" : "N");
            int score5m = currPrice > o5m ? 1 : (currPrice < o5m ? -1 : 0);

            // 15M direction
            double o15m = Opens[2][0];
            string d15m = currPrice > o15m ? "G" : (currPrice < o15m ? "R" : "N");
            int score15m = currPrice > o15m ? 1 : (currPrice < o15m ? -1 : 0);

            // 60M direction
            double o60m = Opens[3][0];
            string d60m = currPrice > o60m ? "G" : (currPrice < o60m ? "R" : "N");
            int score60m = currPrice > o60m ? 1 : (currPrice < o60m ? -1 : 0);

            // Daily direction
            double oD = Opens[4][0];
            string dD = currPrice > oD ? "G" : (currPrice < oD ? "R" : "N");
            int scoreD = currPrice > oD ? 1 : (currPrice < oD ? -1 : 0);

            FTFCScore = score5m + score15m + score60m + scoreD;

            if (ShowHud)
            {
                string biasText = FTFCScore >= 3 ? "FULL BULLISH" : (FTFCScore <= -3 ? "FULL BEARISH" : (FTFCScore > 0 ? "BULL LEAN" : (FTFCScore < 0 ? "BEAR LEAN" : "MIXED / CONFLICT")));
                Brush hudColor = FTFCScore >= 3 ? Brushes.Lime : (FTFCScore <= -3 ? Brushes.Red : (FTFCScore > 0 ? Brushes.LightGreen : (FTFCScore < 0 ? Brushes.LightCoral : Brushes.Yellow)));

                string hudMsg = string.Format("FTFC: {0} ({1:+0;-0;0})\n[D:{2}] [1H:{3}] [15m:{4}] [5m:{5}]",
                    biasText, FTFCScore, dD, d60m, d15m, d5m);

                Draw.TextFixed(this, "TheStrat_FTFC_HUD", hudMsg, HudPosition, hudColor, new SimpleFont("Consolas", FontSize), Brushes.Black, Brushes.DimGray, 70);
            }
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
