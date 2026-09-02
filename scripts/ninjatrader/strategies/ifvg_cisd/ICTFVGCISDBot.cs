#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    public class ICTFVGCISDBot : RiskManagerBase
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant (0=Baseline, 1=V1, 2=V2)", Order = 0, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Mode (0=Market, 1=FVG Touch, 2=FVG CE 50%)", Order = 1, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use MTF 5m+1m Precision Entry", Order = 2, GroupName = "1. Strategy Variant")]
        public bool UseMtfExecution { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Stage 2 Distribution", Order = 3, GroupName = "1. Strategy Variant")]
        public bool UseStage2Distribution { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Orderflow Filter", Order = 4, GroupName = "1. Strategy Variant")]
        public bool UseHtfFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter NY Lunch (12:00-13:30)", Order = 5, GroupName = "1. Strategy Variant")]
        public bool FilterLunch { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Require External Liquidity Sweep", Order = 6, GroupName = "1. Strategy Variant")]
        public bool RequireExternalSweep { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target (Bps)", Order = 7, GroupName = "2. Targets & Risk")]
        public double QueenTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (Bps)", Order = 8, GroupName = "2. Targets & Risk")]
        public double RunnerTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss (Bps)", Order = 9, GroupName = "2. Targets & Risk")]
        public double StopLossBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk Floor (Bps)", Order = 10, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 11, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable 50% Midline Reclaims", Order = 12, GroupName = "3. Midline Features")]
        public bool EnableMidlineReclaims { get; set; }
        #endregion

        private Indicators.Vinay.ICTFVGCISDIndicator ictIndicator;

        // TTrades "Let the Wick Form, Trade the Body" MTF State
        private int armedDirection = 0;
        private int armedBar = 0;
        private int lastArmed5mBar = -1;
        private int wickState = 0; // 0 = Idle, 1 = Waiting for Wick pullback, 2 = Wick inside PD Array
        private double pdArrayHigh = double.NaN;
        private double pdArrayLow = double.NaN;
        private double protectedSwing = double.NaN;
        private double customMtfLimit = double.NaN;
        private double customMtfStop = double.NaN;

        protected override string GetStrategyName() => "ICT_CISD";

        protected override void SetStrategyDefaults()
        {
            Description = "Institutional ICT CISD & FVG Strategy (TTrades 'Let the Wick Form, Trade the Body') with 5m Structure + 1m Precision Entry and Cover The Queen scale-out.";
            Name = "ICTFVGCISDBot";

            // Policy & Risk Defaults
            TradePolicy = TradePolicyType.CoverTheQueen;
            TargetRMultiple = 2.5;
            BreakevenTriggerR = 1.0;
            DailyMaxLoss = 1500;
            MaxTradesPerDay = 3;
            TrailingDrawdown = 2500;

            // Session Windows (09:45 Turnaround to 15:30 ET, Flat at 15:55 ET)
            EarliestEntry = 945;  // Filter 09:30-09:45 Judas Open Trap
            LatestEntry = 1530;
            FlattenBy = 1555;

            Variant = 2;
            EntryMode = 1;                 // 1 = FVG Limit Touch
            UseMtfExecution = true;        // Multi-Timeframe: 5m Structure + 1m Precision Entry
            UseStage2Distribution = false;
            UseHtfFilter = true;           // Pro-Trend 4H Orderflow
            FilterLunch = true;            // Blackout 12:00-13:30
            RequireExternalSweep = true;   // Mandatory Turtle Soup Liquidity Sweep Filter
            QueenTargetBps = 10.0;         // +10 Basis Points (0.10%)
            RunnerTargetBps = 30.0;        // +30 Basis Points (0.30%)
            StopLossBps = 5.0;             // 5.0 Basis Points default stop ceiling
            MinRiskBps = 2.0;              // 2 Basis Points risk floor
            MaxRiskBps = 12.0;             // 12 Basis Points risk ceiling
            EnableMidlineReclaims = true;

            AddSecondaryTimeframe = true;
            DebugMode = true;
        }

        protected override void ConfigureStrategy()
        {
            if (UseMtfExecution)
            {
                AddSecondaryTimeframe = true;
            }
        }

        protected override void InitializeStrategy()
        {
            if (AddSecondaryTimeframe && BarsArray.Length > 1)
            {
                // Run the 5-minute CISD indicator on BarsArray[1] (5m series)
                ictIndicator = ICTFVGCISDIndicator(BarsArray[1], Variant, EntryMode, UseHtfFilter, FilterLunch, RequireExternalSweep, QueenTargetBps, RunnerTargetBps, StopLossBps, MinRiskBps, MaxRiskBps, EnableMidlineReclaims, DrawVisuals);
            }
            else
            {
                // Single timeframe execution on BarsArray[0]
                ictIndicator = ICTFVGCISDIndicator(BarsArray[0], Variant, EntryMode, UseHtfFilter, FilterLunch, RequireExternalSweep, QueenTargetBps, RunnerTargetBps, StopLossBps, MinRiskBps, MaxRiskBps, EnableMidlineReclaims, DrawVisuals);
            }

            armedDirection = 0;
            armedBar = 0;
            wickState = 0;
            pdArrayHigh = double.NaN;
            pdArrayLow = double.NaN;
            protectedSwing = double.NaN;
            customMtfLimit = double.NaN;
            customMtfStop = double.NaN;
        }

        protected override int CheckForSignal()
        {
            if (ictIndicator == null) return 0;

            // ──────────────────────────────────────────────────────────
            // 1. MULTI-TIMEFRAME EXECUTION: TTrades "Let the Wick Form, Trade the Body"
            // ──────────────────────────────────────────────────────────
            if (AddSecondaryTimeframe && BarsArray.Length > 1)
            {
                if (CurrentBars[0] < 20 || CurrentBars[1] < 50) return 0;

                // Step 1 & 2: Check 5m CISD Signal & Displacement on secondary series (BarsArray[1])
                if (CurrentBars[1] != lastArmed5mBar)
                {
                    lastArmed5mBar = CurrentBars[1];
                    int sig5m = ictIndicator.SignalSeries.GetValueAt(CurrentBars[1]);
                    if (sig5m != 0)
                    {
                        armedDirection = sig5m;
                        armedBar = CurrentBars[0];
                        wickState = 1; // Waiting for wick pullback into PD Array

                        double c5 = Closes[1][0];
                        double o5 = Opens[1][0];
                        double h5_0 = Highs[1][0];
                        double l5_0 = Lows[1][0];
                        double h5_2 = Highs[1][2];
                        double l5_2 = Lows[1][2];
                        double cisdLvl = ictIndicator.CisdLevelSeries.GetValueAt(CurrentBars[1]);

                        if (sig5m == 1)
                        {
                            bool isFvg = (l5_0 > h5_2);
                            pdArrayHigh = isFvg ? l5_0 : Math.Max(cisdLvl, c5);
                            pdArrayLow = isFvg ? h5_2 : Math.Min(cisdLvl, o5);
                        }
                        else
                        {
                            bool isFvg = (h5_0 < l5_2);
                            pdArrayHigh = isFvg ? l5_2 : Math.Max(cisdLvl, o5);
                            pdArrayLow = isFvg ? h5_0 : Math.Min(cisdLvl, c5);
                        }
                        protectedSwing = double.NaN;
                    }
                }

                // Step 3 & 4: Manage Wick Formation & Confirmation Window (Within 25 1-minute bars)
                if (armedDirection != 0 && (CurrentBars[0] - armedBar) <= 25)
                {
                    double c0 = Closes[0][0];
                    double o0 = Opens[0][0];
                    double h0 = Highs[0][0];
                    double l0 = Lows[0][0];

                    // Step 3: "Let the Wick Form" -> Price enters PD Array
                    if (wickState == 1)
                    {
                        if (armedDirection == 1 && l0 <= pdArrayHigh)
                        {
                            wickState = 2;
                            protectedSwing = l0;
                        }
                        else if (armedDirection == -1 && h0 >= pdArrayLow)
                        {
                            wickState = 2;
                            protectedSwing = h0;
                        }
                    }

                    // Step 4: "Wick Confirmation" inside/rejecting PD Array
                    if (wickState == 2)
                    {
                        if (armedDirection == 1)
                            protectedSwing = double.IsNaN(protectedSwing) ? l0 : Math.Min(protectedSwing, l0);
                        else
                            protectedSwing = double.IsNaN(protectedSwing) ? h0 : Math.Max(protectedSwing, h0);

                        // 1m candle turns back in trend direction (Wick Formed!)
                        bool confirmed = (armedDirection == 1 && c0 > o0) || (armedDirection == -1 && c0 < o0);

                        if (confirmed)
                        {
                            double stopDist = Math.Abs(c0 - protectedSwing) + (1.0 * TickSize);
                            double riskBps = (stopDist / c0) * 10000.0;

                            // Squeeze filter: valid between MinRiskBps (2.0) and MaxRiskBps (12.0)
                            if (riskBps >= MinRiskBps && riskBps <= MaxRiskBps)
                            {
                                int tradeDir = armedDirection;
                                customMtfLimit = double.NaN; // Market fill on 1m confirmation close
                                customMtfStop = tradeDir == 1 ? protectedSwing - (1.0 * TickSize) : protectedSwing + (1.0 * TickSize);

                                // Reset state
                                armedDirection = 0;
                                wickState = 0;

                                if (DrawVisuals)
                                {
                                    if (tradeDir == 1)
                                    {
                                        Draw.ArrowUp(this, "TTrades_Buy_" + CurrentBar, false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                                        Draw.Text(this, "TTrades_Buy_Txt_" + CurrentBar, false, "WICK FORMED\nTRADE BODY", 0, Low[0] - (10 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                                    }
                                    else
                                    {
                                        Draw.ArrowDown(this, "TTrades_Sell_" + CurrentBar, false, 0, High[0] + (4 * TickSize), Brushes.Magenta);
                                        Draw.Text(this, "TTrades_Sell_Txt_" + CurrentBar, false, "WICK FORMED\nTRADE BODY", 0, High[0] + (10 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                                    }
                                }

                                return tradeDir;
                            }
                        }
                    }
                }
                else if (armedDirection != 0 && (CurrentBars[0] - armedBar) > 25)
                {
                    armedDirection = 0;
                    wickState = 0;
                }

                return 0;
            }

            // ──────────────────────────────────────────────────────────
            // 2. SINGLE TIMEFRAME EXECUTION (5-Minute Direct)
            // ──────────────────────────────────────────────────────────
            if (CurrentBar < 50) return 0;

            if (DrawVisuals && CurrentBar > 50)
            {
                double cisdCurr = ictIndicator.CisdLevelSeries[0];
                double cisdPrev = ictIndicator.CisdLevelSeries[1];
                if (!double.IsNaN(cisdCurr) && !double.IsNaN(cisdPrev) && cisdCurr > 0 && cisdPrev > 0)
                {
                    Draw.Line(this, "CISD_Line_" + CurrentBar, false, 1, cisdPrev, 0, cisdCurr, Brushes.Gold, DashStyleHelper.Solid, 2);
                }
            }

            int sig = ictIndicator.SignalSeries[0];
            if (sig != 0 && DrawVisuals)
            {
                string tag = "CISD_Strat_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (6 * TickSize), Brushes.Gold);
                    Draw.Text(this, tag + "_Txt", false, "CISD BUY", 0, Low[0] - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (6 * TickSize), Brushes.Cyan);
                    Draw.Text(this, tag + "_Txt", false, "CISD SELL", 0, High[0] + (14 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 10), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            return sig;
        }

        protected override double GetCustomLimitPrice(int signal, double currentPrice)
        {
            if (AddSecondaryTimeframe && !double.IsNaN(customMtfLimit))
                return customMtfLimit;

            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double lp = ictIndicator.LimitPriceSeries[0];
            if (!double.IsNaN(lp) && lp > 0) return lp;
            return double.NaN;
        }

        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (AddSecondaryTimeframe && !double.IsNaN(customMtfStop))
                return customMtfStop;

            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double sl = ictIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0) return sl;
            return double.NaN;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDistance)
        {
            if (AddSecondaryTimeframe && !double.IsNaN(customMtfLimit))
            {
                double pts = customMtfLimit * (RunnerTargetBps / 10000.0);
                return signal == 1 ? customMtfLimit + pts : customMtfLimit - pts;
            }

            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double tp = ictIndicator.RunnerTargetSeries[0];
            if (!double.IsNaN(tp) && tp > 0) return tp;
            return double.NaN;
        }

        protected override double GetCurrentATR()
        {
            if (CurrentBar >= 14) return Math.Max(10.0, High[0] - Low[0]);
            return 15.0;
        }

        protected override double GetPotentialLoss()
        {
            if (AddSecondaryTimeframe && !double.IsNaN(customMtfStop))
            {
                double dist = Math.Abs(Close[0] - customMtfStop);
                return dist * GetPointValue() * Math.Max(1, DefaultQuantity);
            }

            if (ictIndicator != null && CurrentBar >= 50)
            {
                double sl = ictIndicator.StopLossSeries[0];
                if (!double.IsNaN(sl) && sl > 0)
                {
                    double dist = Math.Abs(Close[0] - sl);
                    return dist * GetPointValue() * Math.Max(1, DefaultQuantity);
                }
            }
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }
    }
}