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
    /// Strat212ContinuationBot - Automated 2-1-2 Strat Continuation Strategy.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    ///
    /// Visual Features:
    ///   - Paints Strat numbers (1, 2U, 2D, 3) directly on chart.
    ///   - Draws Signal entry arrows, Stop Loss lines, and Target lines.
    /// </summary>
    public class Strat212ContinuationBot : RiskManagerBase
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Description = "Draw Strat numbers, entry arrows, and price levels on chart", Order = 1, GroupName = "Visual Settings")]
        public bool ShowVisualElements { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow Reversals (2D-1-2U / 2U-1-2D)", Order = 2, GroupName = "The Strat")]
        public bool AllowReversals { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 3, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }
        #endregion

        protected override string GetStrategyName()
        {
            return "Strat212Bot";
        }

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-1-2 Strat continuation bot with built-in visual chart rendering and centralized RiskManagerBase";
            Name = "Strat212ContinuationBot";

            // Strat Parameters
            ShowVisualElements = true;
            AllowReversals = false;
            MinTargetPoints = 15.0;

            // RiskManagerBase Defaults (NQ 5m)
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

        protected override int CheckForSignal()
        {
            if (CurrentBars[0] < 4)
                return 0;

            double h0 = Highs[0][0];
            double l0 = Lows[0][0];
            double h1 = Highs[0][1];
            double l1 = Lows[0][1];
            double h2 = Highs[0][2];
            double l2 = Lows[0][2];
            double h3 = Highs[0][3];
            double l3 = Lows[0][3];

            // 1. Classify Bar[1]
            bool h1Higher = h1 > h2;
            bool l1Lower = l1 < l2;
            bool bar1IsInside = (!h1Higher && !l1Lower);

            // 2. Classify Bar[2]
            bool h2Higher = h2 > h3;
            bool l2Lower = l2 < l3;
            bool bar2Is2U = (h2Higher && !l2Lower);
            bool bar2Is2D = (l2Lower && !h2Higher);

            // 3. Draw Strat numbering if enabled
            if (ShowVisualElements)
            {
                RenderBarNumber(0, h0, l0, h1, l1);
            }

            if (!bar1IsInside)
                return 0;

            // Bullish 2-1-2 Trigger: Current bar breaks High[1]
            if (h0 > h1)
            {
                if (bar2Is2U || (AllowReversals && bar2Is2D))
                {
                    double targetPrice = Math.Max(h2, h1 + MinTargetPoints);
                    double stopPrice = l1 - TickSize;

                    if (ShowVisualElements)
                    {
                        string tag = "Strat212_Buy_" + CurrentBars[0];
                        Draw.ArrowUp(this, tag, false, 0, l0 - (4 * TickSize), Brushes.Lime);
                        Draw.Text(this, tag + "_txt", false, "2-1-2 BUY", 0, l0 - (10 * TickSize), 0, Brushes.Lime, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                    return 1; // Long
                }
            }

            // Bearish 2-1-2 Trigger: Current bar breaks Low[1]
            if (l0 < l1)
            {
                if (bar2Is2D || (AllowReversals && bar2Is2U))
                {
                    double targetPrice = Math.Min(l2, l1 - MinTargetPoints);
                    double stopPrice = h1 + TickSize;

                    if (ShowVisualElements)
                    {
                        string tag = "Strat212_Sell_" + CurrentBars[0];
                        Draw.ArrowDown(this, tag, false, 0, h0 + (4 * TickSize), Brushes.Red);
                        Draw.Text(this, tag + "_txt", false, "2-1-2 SELL", 0, h0 + (10 * TickSize), 0, Brushes.Red, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                    return -1; // Short
                }
            }

            return 0;
        }

        private void RenderBarNumber(int barsAgo, double currH, double currL, double prevH, double prevL)
        {
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
            double price = above ? currH + (4 * TickSize) : currL - (4 * TickSize);
            Draw.Text(this, tag, false, numText, barsAgo, price, 0, numColor, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
