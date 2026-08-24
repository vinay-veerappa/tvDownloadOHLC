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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// Strat22RevStratBot - Automated 2-2 Reversal and RevStrat Momentum Trap Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    ///
    /// Visual Features:
    ///   - Paints Strat numbers (1, 2U, 2D, 3) on ALL bars on the chart.
    ///   - Draws Reversal trigger arrows and annotations.
    /// </summary>
    public class Strat22RevStratBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Description = "Draw Strat numbers, entry arrows, and price levels on chart", Order = 1, GroupName = "Visual Settings")]
        public bool ShowVisualElements { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Require Rejection Wick (60%)", Order = 2, GroupName = "The Strat")]
        public bool RequireRejectionWick { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 3, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }
        #endregion

        protected override string GetStrategyName()
        {
            return "Strat22Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-2 Reversal and RevStrat momentum trap bot with built-in visual chart rendering and centralized RiskManagerBase";
            Name = "Strat22RevStratBot";

            // Strat Parameters
            ShowVisualElements = true;
            RequireRejectionWick = false;
            MinTargetPoints = 20.0;

            // RiskManagerBase Defaults
            DailyMaxLoss = 500;
            MaxConsecutiveLosers = 2;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 3;
            MaxTradesPerDay = 4;
            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            // Brackets
            TradePolicy = "BreakevenTrail";
            TargetRMultiple = 2.0;
            BreakevenTriggerR = 1.0;
            AtrPeriod = 14;
            StopAtrMult = 1.5;
            TrailAtrMult = 2.0;
            AddSecondaryTimeframe = true;
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 0 && CurrentBars[0] >= 2 && ShowVisualElements)
            {
                RenderBarNumber();
            }

            base.OnBarUpdate();
        }

        protected override int CheckForSignal()
        {
            if (CurrentBars[0] < 3)
                return 0;

            double h0 = Highs[0][0];
            double l0 = Lows[0][0];
            double h1 = Highs[0][1];
            double l1 = Lows[0][1];
            double o1 = Opens[0][1];
            double c1 = Closes[0][1];
            double h2 = Highs[0][2];
            double l2 = Lows[0][2];

            bool h1Higher = h1 > h2;
            bool l1Lower = l1 < l2;

            bool bar1Is2D = (l1Lower && !h1Higher);
            bool bar1Is2U = (h1Higher && !l1Lower);

            double range1 = h1 - l1;

            // 1. Bullish 2-2 Reversal: Bar[1] was 2D, Bar[0] breaks High[1]
            if (bar1Is2D && h0 > h1)
            {
                if (RequireRejectionWick && range1 > TickSize)
                {
                    double lowerWick = Math.Min(o1, c1) - l1;
                    if ((lowerWick / range1) < 0.60)
                        return 0;
                }

                if (ShowVisualElements)
                {
                    string tag = "Strat22_Buy_" + CurrentBars[0];
                    Draw.ArrowUp(this, tag, false, 0, l0 - (6 * TickSize), Brushes.Gold);
                    Draw.Text(this, tag + "_txt", false, "2-2 REV BUY", 0, l0 - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                return 1; // Long
            }

            // 2. Bearish 2-2 Reversal: Bar[1] was 2U, Bar[0] breaks Low[1]
            if (bar1Is2U && l0 < l1)
            {
                if (RequireRejectionWick && range1 > TickSize)
                {
                    double upperWick = h1 - Math.Max(o1, c1);
                    if ((upperWick / range1) < 0.60)
                        return 0;
                }

                if (ShowVisualElements)
                {
                    string tag = "Strat22_Sell_" + CurrentBars[0];
                    Draw.ArrowDown(this, tag, false, 0, h0 + (6 * TickSize), Brushes.OrangeRed);
                    Draw.Text(this, tag + "_txt", false, "2-2 REV SELL", 0, h0 + (14 * TickSize), 0, Brushes.OrangeRed, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                return -1; // Short
            }

            return 0;
        }

        private void RenderBarNumber()
        {
            double currH = Highs[0][0];
            double currL = Lows[0][0];
            double prevH = Highs[0][1];
            double prevL = Lows[0][1];

            string numText = "";
            Brush numColor = Brushes.Gray;
            bool above = true;

            if (currH <= prevH && currL >= prevL)
            {
                numText = "1";
                numColor = Brushes.Gold;
                above = true;
            }
            else if (currH > prevH && currL >= prevL)
            {
                numText = "2U";
                numColor = Brushes.LimeGreen;
                above = false;
            }
            else if (currL < prevL && currH <= prevH)
            {
                numText = "2D";
                numColor = Brushes.Crimson;
                above = true;
            }
            else
            {
                numText = "3";
                numColor = Brushes.MediumOrchid;
                above = true;
            }

            string tag = "StratNum_" + CurrentBars[0];
            double price = above ? currH + (6 * TickSize) : currL - (6 * TickSize);
            Draw.Text(this, tag, false, numText, 0, price, 0, numColor, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
