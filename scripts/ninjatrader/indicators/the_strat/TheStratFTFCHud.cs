#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Text;
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
    /// TheStratFTFCHud - Real-Time Full Time Frame Continuity (FTFC) Dashboard for NinjaTrader 8.
    /// Tracks open vs. current price direction across: Day, 60m, 15m, 5m.
    /// Calculates continuity cleanly from intraday bar timestamps with 100% chart compatibility.
    /// </summary>
    public class TheStratFTFCHud : Indicator
    {
        #region Properties & Inputs
        [NinjaScriptProperty]
        [Display(Name = "Show Dashboard HUD", Description = "Draw real-time FTFC dashboard on chart", Order = 1, GroupName = "1. Dashboard Settings")]
        public bool ShowHud { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "HUD Position", Description = "HUD anchor corner", Order = 2, GroupName = "1. Dashboard Settings")]
        public TextPosition HudPosition { get; set; }

        [NinjaScriptProperty]
        [Range(8, 24)]
        [Display(Name = "Font Size", Description = "Dashboard font size", Order = 3, GroupName = "1. Dashboard Settings")]
        public int FontSize { get; set; }

        [Browsable(false)]
        [XmlIgnore]
        public int FTFCScore { get; private set; } // +4 (Full Bull) to -4 (Full Bear)
        #endregion

        private DateTime currentDay = DateTime.MinValue;
        private double dayOpen = 0;
        private double h1Open = 0;
        private int currentHour = -1;
        private double m15Open = 0;
        private int currentM15 = -1;
        private double m5Open = 0;
        private int currentM5 = -1;

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
            else if (State == State.DataLoaded)
            {
                currentDay = DateTime.MinValue;
                dayOpen = 0;
                h1Open = 0;
                currentHour = -1;
                m15Open = 0;
                currentM15 = -1;
                m5Open = 0;
                currentM5 = -1;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
                return;

            DateTime barTime = Time[0];
            double currPrice = Close[0];

            // 1. Daily Open (Session boundary at 18:00 ET or Day change)
            if (barTime.Date != currentDay)
            {
                currentDay = barTime.Date;
                dayOpen = Open[0];
            }

            // 2. 1-Hour Open
            if (barTime.Hour != currentHour)
            {
                currentHour = barTime.Hour;
                h1Open = Open[0];
            }

            // 3. 15-Min Open
            int m15Bucket = barTime.Minute / 15;
            if (m15Bucket != currentM15 || barTime.Hour != currentHour)
            {
                currentM15 = m15Bucket;
                m15Open = Open[0];
            }

            // 4. 5-Min Open
            int m5Bucket = barTime.Minute / 5;
            if (m5Bucket != currentM5 || barTime.Hour != currentHour)
            {
                currentM5 = m5Bucket;
                m5Open = Open[0];
            }

            if (dayOpen == 0) dayOpen = Open[0];
            if (h1Open == 0) h1Open = Open[0];
            if (m15Open == 0) m15Open = Open[0];
            if (m5Open == 0) m5Open = Open[0];

            string dD = currPrice >= dayOpen ? "G" : "R";
            int sD = currPrice >= dayOpen ? 1 : -1;

            string d60 = currPrice >= h1Open ? "G" : "R";
            int s60 = currPrice >= h1Open ? 1 : -1;

            string d15 = currPrice >= m15Open ? "G" : "R";
            int s15 = currPrice >= m15Open ? 1 : -1;

            string d5 = currPrice >= m5Open ? "G" : "R";
            int s5 = currPrice >= m5Open ? 1 : -1;

            FTFCScore = sD + s60 + s15 + s5;

            if (ShowHud)
            {
                string biasText;
                Brush statusBrush;

                if (FTFCScore >= 4)
                {
                    biasText = "FULL BULLISH FTFC";
                    statusBrush = Brushes.Lime;
                }
                else if (FTFCScore <= -4)
                {
                    biasText = "FULL BEARISH FTFC";
                    statusBrush = Brushes.Red;
                }
                else if (FTFCScore > 0)
                {
                    biasText = "BULLISH LEAN";
                    statusBrush = Brushes.LightGreen;
                }
                else if (FTFCScore < 0)
                {
                    biasText = "BEARISH LEAN";
                    statusBrush = Brushes.LightCoral;
                }
                else
                {
                    biasText = "CONFLICT / MIXED";
                    statusBrush = Brushes.Yellow;
                }

                StringBuilder sb = new StringBuilder();
                sb.AppendLine("=== THE STRAT FTFC ===");
                sb.AppendLine($"Status: {biasText} ({FTFCScore:+0;-0;0})");
                sb.AppendLine($"[Day: {dD}] [1H: {d60}] [15m: {d15}] [5m: {d5}]");
                sb.AppendLine($"Price: {currPrice:F2} | Day Open: {dayOpen:F2}");

                Draw.TextFixed(this, "TheStrat_FTFC_HUD", sb.ToString(), HudPosition, statusBrush, new SimpleFont("Consolas", FontSize), Brushes.DimGray, Brushes.Black, 85);
            }
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
