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
    /// Fixed:
    ///   - Self-contained ATR and structural risk calculations (No secondary timeframe dependency).
    ///   - Fixed potential loss estimation so DailyMaxLoss never falsely blocks entries.
    ///   - Unconditional visual bar numbering on all bars.
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

        private ATR chartAtr;

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

            // RiskManagerBase Defaults (NQ/MNQ)
            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 3;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 4;
            MaxTradesPerDay = 6;
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
            AddSecondaryTimeframe = false; // Self-contained on chart series
        }

        protected override void ConfigureStrategy()
        {
        }

        protected override void InitializeStrategy()
        {
            chartAtr = ATR(AtrPeriod);
        }

        protected override double GetCurrentATR()
        {
            if (chartAtr == null || CurrentBar < AtrPeriod)
                return 15.0 * TickSize * 4; // safe default ~15 pts
            return chartAtr[0];
        }

        protected override double GetPotentialLoss()
        {
            // Estimate based on 15 pt stop to avoid false DailyMaxLoss triggers
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar >= 2 && ShowVisualElements)
            {
                RenderBarNumber();
            }

            base.OnBarUpdate();
        }

        protected override int CheckForSignal()
        {
            if (CurrentBar < 4)
                return 0;

            double h0 = High[0];
            double l0 = Low[0];
            double h1 = High[1];
            double l1 = Low[1];
            double h2 = High[2];
            double l2 = Low[2];
            double h3 = High[3];
            double l3 = Low[3];

            // 1. Classify Bar[1]
            bool h1Higher = h1 > h2;
            bool l1Lower = l1 < l2;
            bool bar1IsInside = (!h1Higher && !l1Lower);

            if (!bar1IsInside)
                return 0;

            // 2. Classify Bar[2]
            bool h2Higher = h2 > h3;
            bool l2Lower = l2 < l3;
            bool bar2Is2U = (h2Higher && !l2Lower);
            bool bar2Is2D = (l2Lower && !h2Higher);

            // Bullish 2-1-2 Trigger: Current bar breaks High[1]
            if (h0 > h1)
            {
                if (bar2Is2U || (AllowReversals && bar2Is2D))
                {
                    if (ShowVisualElements)
                    {
                        string tag = "Strat212_Buy_" + CurrentBar;
                        Draw.ArrowUp(this, tag, false, 0, l0 - (6 * TickSize), Brushes.Lime);
                        Draw.Text(this, tag + "_txt", false, "2-1-2 BUY", 0, l0 - (14 * TickSize), 0, Brushes.Lime, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                    return 1; // Long
                }
            }

            // Bearish 2-1-2 Trigger: Current bar breaks Low[1]
            if (l0 < l1)
            {
                if (bar2Is2D || (AllowReversals && bar2Is2U))
                {
                    if (ShowVisualElements)
                    {
                        string tag = "Strat212_Sell_" + CurrentBar;
                        Draw.ArrowDown(this, tag, false, 0, h0 + (6 * TickSize), Brushes.Red);
                        Draw.Text(this, tag + "_txt", false, "2-1-2 SELL", 0, h0 + (14 * TickSize), 0, Brushes.Red, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    }
                    return -1; // Short
                }
            }

            return 0;
        }

        private void RenderBarNumber()
        {
            double currH = High[0];
            double currL = Low[0];
            double prevH = High[1];
            double prevL = Low[1];

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

            string tag = "StratNum_" + CurrentBar;
            double price = above ? currH + (6 * TickSize) : currL - (6 * TickSize);
            Draw.Text(this, tag, false, numText, 0, price, 0, numColor, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
        }
    }
}
#region NinjaScript generated code. Neither change nor remove.
#endregion
