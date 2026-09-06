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
    /// <summary>
    /// ICTFVGCISDBot — Institutional ICT CISD & FVG Strategy with 5m Structure +
    /// 1m Precision Entry, Cover The Queen scale-out, and Confirmed Re-entry Protocol.
    ///
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8). All strategy
    /// parameters come from the SHARED MANIFEST (Indicators.Vinay.IfvgCisdConfig.cs,
    /// auto-generated from configs/strategies/ifvg_cisd.yaml) — never hand-tuned here.
    ///
    /// DECLARED CRITERIA: indicator presence, re-entry window (a time-boxed gate),
    /// MTF warmup, single-TF warmup, and the risk-bps squeeze window on the wick
    /// confirmation. The wick confirmation itself is the TRIGGER; the risk window is
    /// the GATE that can block it — and when it blocks, the armed state is NOT reset
    /// (the original retried on the next bar while still in wickState 2, and this
    /// preserves that). State mutations (arming, wick tracking, re-entry arming)
    /// remain here; the base computes the verdict and owns every order.
    ///
    /// OnExecutionUpdate stays overridden: re-entry arming on a losing round trip is
    /// execution-bookkeeping, not a bar decision, and RiskManagerBase owns the hook.
    /// </summary>
    public class ICTFVGCISDBot : GovernedStrategy
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant (0=Baseline, 1=V1, 2=V2)", Order = 0, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Mode (0=Market, 1=CISD Limit)", Order = 1, GroupName = "1. Strategy Variant")]
        [Range(0, 1)]
        public int EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss Type (0=BpsStat,1=Struct,2=StructCapped,3=SkipOOB)", Order = 2, GroupName = "1. Strategy Variant")]
        [Range(0, 3)]
        public int StopLossType { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use MTF 5m+1m Precision Entry", Order = 3, GroupName = "1. Strategy Variant")]
        public bool UseMtfExecution { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Stage 2 Distribution", Order = 3, GroupName = "1. Strategy Variant")]
        public bool UseStage2Distribution { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Orderflow Filter", Order = 4, GroupName = "1. Strategy Variant")]
        public bool UseHtfFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter NY Lunch (11:30-13:30)", Order = 5, GroupName = "1. Strategy Variant")]
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

        [NinjaScriptProperty]
        [Display(Name = "Enable Confirmed Re-Entry", Order = 13, GroupName = "1. Strategy Variant")]
        public bool EnableConfirmedReentry { get; set; }

        [NinjaScriptProperty]
        [Range(10, 10000)]
        [Display(Name = "HTF EMA Period", Order = 14, GroupName = "1. Strategy Variant")]
        public int HtfEmaPeriod { get; set; } = 2400;
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

        // Confirmed Re-Entry State
        private bool reentryArmed = false;
        private int reentryDirection = 0;
        private int reentryBar = 0;
        private bool isReentryTrade = false;

        protected override string GetStrategyName() => "ICT_CISD";

        protected override void OnStrategyDefaults()
        {
            Description = "Institutional ICT CISD & FVG Strategy with 5m Structure + 1m Precision Entry, Cover The Queen scale-out, and Confirmed Re-entry Protocol.";
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

            // Strategy defaults come from the SHARED MANIFEST (Indicators.Vinay.IfvgCisdConfig.cs,
            // auto-generated from configs/strategies/ifvg_cisd.yaml). Never
            // hand-tune a value here that the manifest owns.
            Variant = Indicators.Vinay.IfvgCisdConfig.Variant;                    // manifest: variant2
            EntryMode = Indicators.Vinay.IfvgCisdConfig.EntryMode;                 // manifest: cisd_limit
            StopLossType = Indicators.Vinay.IfvgCisdConfig.StopLossTypeId;         // manifest: bps_stat
            UseMtfExecution = true;        // Multi-Timeframe: 5m Structure + 1m Precision Entry
            UseStage2Distribution = false;
            UseHtfFilter = Indicators.Vinay.IfvgCisdConfig.UseHtfFilter;           // manifest: false (V1/V2 parity)
            HtfEmaPeriod = Indicators.Vinay.IfvgCisdConfig.HtfEmaPeriod;
            FilterLunch = Indicators.Vinay.IfvgCisdConfig.LunchFilterEnabled;      // manifest: 11:30-13:30
            RequireExternalSweep = Indicators.Vinay.IfvgCisdConfig.RequireExternalSweep;
            EnableConfirmedReentry = Indicators.Vinay.IfvgCisdConfig.EnableConfirmedReentry;
            QueenTargetBps = Indicators.Vinay.IfvgCisdConfig.QueenTargetBps;
            RunnerTargetBps = Indicators.Vinay.IfvgCisdConfig.RunnerTargetBps;
            StopLossBps = Indicators.Vinay.IfvgCisdConfig.StopLossBps;
            MinRiskBps = Indicators.Vinay.IfvgCisdConfig.MinRiskBps;
            MaxRiskBps = Indicators.Vinay.IfvgCisdConfig.MaxRiskBps;
            EnableMidlineReclaims = Indicators.Vinay.IfvgCisdConfig.EnableMidlineReclaims;

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

        protected override void OnInitialize()
        {
            if (AddSecondaryTimeframe && BarsArray.Length > 1)
            {
                // Run the 5-minute CISD indicator on BarsArray[1] (5m series).
                // Signature parity contract: indicator params are
                // (Variant, EntryMode, StopLossType, UseHtfFilter, FilterLunch,
                //  RequireExternalSweep, Queen, Runner, StopBps, MinBps, MaxBps,
                //  Midlines, Visuals) — mirrors the shared manifest.
                ictIndicator = ICTFVGCISDIndicator(BarsArray[1], Variant, EntryMode, StopLossType, UseHtfFilter, FilterLunch, RequireExternalSweep, QueenTargetBps, RunnerTargetBps, StopLossBps, MinRiskBps, MaxRiskBps, EnableMidlineReclaims, DrawVisuals);
                if (ictIndicator != null) ictIndicator.HtfEmaPeriod = HtfEmaPeriod;
            }
            else
            {
                // Single timeframe execution on BarsArray[0]
                ictIndicator = ICTFVGCISDIndicator(BarsArray[0], Variant, EntryMode, StopLossType, UseHtfFilter, FilterLunch, RequireExternalSweep, QueenTargetBps, RunnerTargetBps, StopLossBps, MinRiskBps, MaxRiskBps, EnableMidlineReclaims, DrawVisuals);
                if (ictIndicator != null) ictIndicator.HtfEmaPeriod = HtfEmaPeriod;
            }

            armedDirection = 0;
            armedBar = 0;
            wickState = 0;
            pdArrayHigh = double.NaN;
            pdArrayLow = double.NaN;
            protectedSwing = double.NaN;
            customMtfLimit = double.NaN;
            customMtfStop = double.NaN;

            reentryArmed = false;
            reentryDirection = 0;
            reentryBar = 0;
            isReentryTrade = false;
        }

        /// <summary>
        /// DECLARE this bar's criteria. The verdict is computed by the sealed
        /// base from what is declared here; nothing here returns a signal.
        /// State mutation order matches the original CheckForSignal exactly:
        /// re-entry evaluation first (its confirm short-circuits the bar), then
        /// the MTF state machine, then the single-TF fallback.
        /// </summary>
        protected override void OnEvaluate(SetupEvaluation e)
        {
            e.Gate("ict_indicator", ictIndicator != null);
            if (ictIndicator == null) return;

            // ──────────────────────────────────────────────────────────
            // 0. CONFIRMED RE-ENTRY EVALUATION (If stopped out on initial 5 bps SL)
            // ──────────────────────────────────────────────────────────
            if (EnableConfirmedReentry && reentryArmed)
            {
                int reentryAge = CurrentBars[0] - reentryBar;
                e.Gate("reentry_window", reentryAge <= 20, reentryAge, 20);
                if (reentryAge <= 20)
                {
                    double c0 = Closes[0][0];
                    double o0 = Opens[0][0];
                    double h0 = Highs[0][0];
                    double l0 = Lows[0][0];
                    double h2 = Highs[0][2];
                    double l2 = Lows[0][2];

                    bool reconfirmed = false;
                    if (reentryDirection == 1 && (c0 > o0 && (l0 > h2 || c0 > Highs[0][1])))
                        reconfirmed = true;
                    else if (reentryDirection == -1 && (c0 < o0 && (h0 < l2 || c0 < Lows[0][1])))
                        reconfirmed = true;

                    e.Trigger(reconfirmed, reentryDirection == 1 ? "long" : "short");
                    if (reconfirmed)
                    {
                        int tradeDir = reentryDirection;
                        reentryArmed = false;
                        isReentryTrade = true;

                        double entryP = c0;
                        double slDist = entryP * (StopLossBps / 10000.0);
                        customMtfLimit = double.NaN;
                        customMtfStop = tradeDir == 1 ? entryP - slDist : entryP + slDist;

                        // Section 11 item 19: the DECLARED payoff -- 1R of the
                        // actual stop distance, the same number the ifvg_cisd
                        // twin declares (r_mult_tp1 = 1.0).
                        e.DeclareTarget(entryP + (tradeDir == 1 ? slDist : -slDist));
                        e.Measure("stop_bps", StopLossBps, StopLossBps);

                        if (DrawVisuals)
                        {
                            string tag = "ReEntry_" + CurrentBar;
                            if (tradeDir == 1)
                                Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.Cyan);
                            else
                                Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.Orange);
                        }

                        // The original returned here — the MTF block is skipped
                        // on a re-entry bar.
                        return;
                    }
                }
                else
                {
                    reentryArmed = false;
                }
            }

            // ──────────────────────────────────────────────────────────
            // 1. MULTI-TIMEFRAME EXECUTION: 5m Structure + 1m Precision Entry
            // ──────────────────────────────────────────────────────────
            if (AddSecondaryTimeframe && BarsArray.Length > 1)
            {
                bool mtfWarmed = CurrentBars[0] >= 20 && CurrentBars[1] >= 50;
                e.Gate("mtf_warmup", mtfWarmed, Math.Min(CurrentBars[0], CurrentBars[1]), 20);
                if (!mtfWarmed) return;

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

                        e.Trigger(confirmed, armedDirection == 1 ? "long" : "short");
                        if (confirmed)
                        {
                            double stopDist = Math.Abs(c0 - protectedSwing) + (1.0 * TickSize);
                            double riskBps = (stopDist / c0) * 10000.0;

                            // Squeeze filter: valid between MinRiskBps (2.0) and MaxRiskBps (15.0)
                            bool riskOk = riskBps >= MinRiskBps && riskBps <= MaxRiskBps;
                            e.Gate("risk_bps_window", riskOk, riskBps, MinRiskBps);

                            // NOTE: state is reset ONLY when the window passes —
                            // the original left the setup armed to retry on the
                            // next bar when the squeeze rejected it.
                            if (riskOk)
                            {
                                int tradeDir = armedDirection;
                                customMtfLimit = double.NaN; // Market fill on 1m confirmation close

                                // Strictly hard-cap stop loss at StopLossBps (5.0 bps) for Python parity
                                double maxSlDist = c0 * (StopLossBps / 10000.0);
                                double actualSlDist = Math.Min(stopDist, maxSlDist);
                                customMtfStop = tradeDir == 1 ? c0 - actualSlDist : c0 + actualSlDist;

                                // Section 11 item 19: the DECLARED payoff -- 1R
                                // of the effective stop distance, matching the
                                // ifvg_cisd twin (r_mult_tp1 = 1.0).
                                e.DeclareTarget(c0 + (tradeDir == 1 ? actualSlDist : -actualSlDist));

                                // Reset state
                                armedDirection = 0;
                                wickState = 0;

                                if (DrawVisuals)
                                {
                                    string tag = "TTrades_" + CurrentBar;
                                    double entryP = c0;
                                    double qPts = entryP * (QueenTargetBps / 10000.0);
                                    double rPts = entryP * (RunnerTargetBps / 10000.0);
                                    double tp1 = tradeDir == 1 ? entryP + qPts : entryP - qPts;
                                    double tp2 = tradeDir == 1 ? entryP + rPts : entryP - rPts;
                                    double sl = customMtfStop;

                                    if (tradeDir == 1)
                                    {
                                        Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                                        Draw.Text(this, tag + "_Txt", false, $"BUY LONG (Wick Rejection -> Trade Body)\nEntry: {entryP:F2} | SL: {sl:F2} ({riskBps:F1}bps)\nTP1: {tp1:F2} | TP2: {tp2:F2}", 0, Low[0] - (14 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);

                                        if (!double.IsNaN(pdArrayHigh) && !double.IsNaN(pdArrayLow))
                                            Draw.Rectangle(this, tag + "_PDZone", false, 15, pdArrayHigh, 0, pdArrayLow, Brushes.Transparent, Brushes.DarkGreen, 20);

                                        Draw.Line(this, tag + "_SL", false, 8, sl, 0, sl, Brushes.Red, DashStyleHelper.Dash, 2);
                                        Draw.Line(this, tag + "_TP1", false, 8, tp1, 0, tp1, Brushes.LimeGreen, DashStyleHelper.Dash, 2);
                                        Draw.Line(this, tag + "_TP2", false, 8, tp2, 0, tp2, Brushes.LimeGreen, DashStyleHelper.Solid, 2);
                                    }
                                    else
                                    {
                                        Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.Magenta);
                                        Draw.Text(this, tag + "_Txt", false, $"SELL SHORT (Wick Rejection -> Trade Body)\nEntry: {entryP:F2} | SL: {sl:F2} ({riskBps:F1}bps)\nTP1: {tp1:F2} | TP2: {tp2:F2}", 0, High[0] + (14 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);

                                        if (!double.IsNaN(pdArrayHigh) && !double.IsNaN(pdArrayLow))
                                            Draw.Rectangle(this, tag + "_PDZone", false, 15, pdArrayHigh, 0, pdArrayLow, Brushes.Transparent, Brushes.DarkRed, 20);

                                        Draw.Line(this, tag + "_SL", false, 8, sl, 0, sl, Brushes.Red, DashStyleHelper.Dash, 2);
                                        Draw.Line(this, tag + "_TP1", false, 8, tp1, 0, tp1, Brushes.Magenta, DashStyleHelper.Dash, 2);
                                        Draw.Line(this, tag + "_TP2", false, 8, tp2, 0, tp2, Brushes.Magenta, DashStyleHelper.Solid, 2);
                                    }
                                }
                            }
                        }
                    }
                }
                else if (armedDirection != 0 && (CurrentBars[0] - armedBar) > 25)
                {
                    armedDirection = 0;
                    wickState = 0;
                }

                return;
            }

            // ──────────────────────────────────────────────────────────
            // 2. SINGLE TIMEFRAME EXECUTION (5-Minute Direct)
            // ──────────────────────────────────────────────────────────
            bool stfWarmed = CurrentBar >= 50;
            e.Gate("stf_warmup", stfWarmed, CurrentBar, 50);
            if (!stfWarmed) return;

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
            e.Trigger(sig != 0, sig == 1 ? "long" : "short");

            // Section 11 item 19: the DECLARED payoff for the single-TF path --
            // 1R of the indicator's own stop, matching the ifvg_cisd twin.
            if (sig != 0)
            {
                double sl = ictIndicator.StopLossSeries[0];
                if (!double.IsNaN(sl) && sl > 0)
                    e.DeclareTarget(Close[0] + (sig > 0 ? 1.0 : -1.0) * Math.Abs(Close[0] - sl));
            }

            if (sig != 0 && DrawVisuals)
            {
                string tag = "CISD_Strat_" + CurrentBar;
                double entryP = Close[0];
                double sl = ictIndicator.StopLossSeries[0];
                double tp1 = ictIndicator.QueenTargetSeries[0];
                double tp2 = ictIndicator.RunnerTargetSeries[0];
                double riskPts = Math.Abs(entryP - sl);
                double riskBps = (riskPts / entryP) * 10000.0;

                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (6 * TickSize), Brushes.LimeGreen);
                    Draw.Text(this, tag + "_Txt", false, $"BUY LONG (CISD Reversal)\nEntry: {entryP:F2} | SL: {sl:F2} ({riskBps:F1}bps)\nTP1: {tp1:F2} | TP2: {tp2:F2}", 0, Low[0] - (14 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);

                    Draw.Line(this, tag + "_SL", false, 8, sl, 0, sl, Brushes.Red, DashStyleHelper.Dash, 2);
                    Draw.Line(this, tag + "_TP1", false, 8, tp1, 0, tp1, Brushes.LimeGreen, DashStyleHelper.Dash, 2);
                    Draw.Line(this, tag + "_TP2", false, 8, tp2, 0, tp2, Brushes.LimeGreen, DashStyleHelper.Solid, 2);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (6 * TickSize), Brushes.Magenta);
                    Draw.Text(this, tag + "_Txt", false, $"SELL SHORT (CISD Reversal)\nEntry: {entryP:F2} | SL: {sl:F2} ({riskBps:F1}bps)\nTP1: {tp1:F2} | TP2: {tp2:F2}", 0, High[0] + (14 * TickSize), 0, Brushes.Magenta, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);

                    Draw.Line(this, tag + "_SL", false, 8, sl, 0, sl, Brushes.Red, DashStyleHelper.Dash, 2);
                    Draw.Line(this, tag + "_TP1", false, 8, tp1, 0, tp1, Brushes.Magenta, DashStyleHelper.Dash, 2);
                    Draw.Line(this, tag + "_TP2", false, 8, tp2, 0, tp2, Brushes.Magenta, DashStyleHelper.Solid, 2);
                }
            }
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
            double maxSlDist = entryPrice * (StopLossBps / 10000.0);
            if (AddSecondaryTimeframe && !double.IsNaN(customMtfStop))
            {
                double reqDist = Math.Abs(entryPrice - customMtfStop);
                double actualDist = Math.Min(reqDist, maxSlDist);
                return signal == 1 ? entryPrice - actualDist : entryPrice + actualDist;
            }

            if (ictIndicator == null || CurrentBar < 50) return double.NaN;
            double sl = ictIndicator.StopLossSeries[0];
            if (!double.IsNaN(sl) && sl > 0)
            {
                double reqDist = Math.Abs(entryPrice - sl);
                double actualDist = Math.Min(reqDist, maxSlDist);
                return signal == 1 ? entryPrice - actualDist : entryPrice + actualDist;
            }
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

        protected override void OnExecutionUpdate(
            Execution execution, string executionId,
            double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            base.OnExecutionUpdate(execution, executionId, price, quantity, marketPosition, orderId, time);

            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (EnableConfirmedReentry && !isReentryTrade && SystemPerformance.AllTrades.Count > 0)
                {
                    Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                    if (lastTrade.ProfitCurrency < 0)
                    {
                        reentryArmed = true;
                        reentryDirection = (lastTrade.Entry.MarketPosition == MarketPosition.Long) ? 1 : -1;
                        reentryBar = CurrentBars[0];
                        if (DebugMode) Log($"[ICTFVGCISDBot] Stop Loss Hit (-${Math.Abs(lastTrade.ProfitCurrency):F2}). Re-armed for Confirmed Re-Entry in direction {reentryDirection} at bar {reentryBar}", LogLevel.Information);
                    }
                    else
                    {
                        reentryArmed = false;
                        isReentryTrade = false;
                    }
                }
                else
                {
                    isReentryTrade = false;
                }
            }
        }
    }
}