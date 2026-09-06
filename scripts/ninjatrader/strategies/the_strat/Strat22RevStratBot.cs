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
    /// Strat22RevStratBot - Automated 2-2 Strat Reversal Strategy.
    /// Consumes TheStratClassifier indicator for visual rendering and signals.
    ///
    /// Migrated onto GovernedStrategy (STRATEGY_WORKFLOW.md 3.4; B7+B8, unblocked
    /// by the WickType range-guard decision of section 11 item 2). Same two-phase
    /// state machine and declared-criteria shape as Strat212ContinuationBot,
    /// differing only in the signal series (Signal22Series) and the visuals.
    /// All tunables come from strat_config.json (the parameter document, 3.3).
    /// </summary>
    public class Strat22RevStratBot : GovernedStrategy
    {
        #region Strat Strategy Parameters
        [NinjaScriptProperty]
        [Range(0.50, 0.90)]
        [Display(Name = "Actionable Wick Threshold", Order = 1, GroupName = "The Strat")]
        public double WickThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Target Points", Order = 2, GroupName = "The Strat")]
        public double MinTargetPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use FTFC Filter", Order = 3, GroupName = "The Strat")]
        public bool UseFtfcFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min FTFC Score", Order = 4, GroupName = "The Strat")]
        public int MinFtfcScore { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Killzones", Order = 5, GroupName = "The Strat")]
        public bool UseKillzones { get; set; }
        #endregion

        private Indicators.TheStrat.TheStratClassifier stratClassifier;
        private ATR chartAtr;
        private StratSessionTracker sessionTracker;
        private DateTime stratGateDay = DateTime.MinValue;
        private int stratTradesToday;
        private int pendingSig;
        private double pendingTrigger;
        private double pendingStop;
        private double pendingTP1;
        private double pendingTP2;
        // Values scored on the SIGNAL bar, carried to the ENTRY decision so the
        // log describes the criteria that produced the staged setup.
        private int stagedFtfcScore;
        private double stagedTargetDist;

        protected override string GetStrategyName() => "Strat22Bot";

        protected override void OnStrategyDefaults()
        {
            Description = "Automated 2-2 Strat reversal bot consuming TheStratClassifier with centralized RiskManagerBase";
            Name = "Strat22RevStratBot";

            WickThreshold = 0.60;
            MinTargetPoints = 15.0;
            UseFtfcFilter = true;
            MinFtfcScore = 2;
            UseKillzones = true;

            // RiskManagerBase Defaults (NQ/MNQ)
            DailyMaxLoss = 1500;
            MaxConsecutiveLosers = 3;
            PauseMinutes = 30;
            HardStopConsecutiveLosers = 4;
            MaxTradesPerDay = 6;
            EarliestEntry = 930;
            LatestEntry = 1530;
            FlattenBy = 1555;

            // Canonical config overlay — same strat_config.json Python reads.
            // Fail-open: missing/unparseable file keeps the compiled defaults above.
            try
            {
                var cfg = StratConfig.Load();
                MinTargetPoints = cfg.MinTargetPoints;
                WickThreshold = cfg.WickThreshold;
                EarliestEntry = cfg.EarliestEntry;
                LatestEntry = cfg.LatestEntry;
                FlattenBy = cfg.FlattenBy;
                MaxTradesPerDay = cfg.MaxTradesPerDay;
                UseFtfcFilter = cfg.UseFtfcFilter;
                MinFtfcScore = cfg.MinFtfcScore;
                UseKillzones = cfg.UseKillzones;
            }
            catch { /* compiled defaults stand */ }

            // Brackets & Execution Policy
            // FixedTP1TP2 = parity with the Python two-leg sim: 50% scale at measured
            // T1, runner to measured T2 with stop to breakeven after TP1 (no ATR trail).
            TradePolicy = TradePolicyType.FixedTP1TP2;
            TargetRMultiple = 2.5;
            BreakevenTriggerR = 1.0;
            AtrPeriod = 14;
            StopAtrMult = 1.5;
            TrailAtrMult = 2.0;
        }

        protected override void OnInitialize()
        {
            stratClassifier = TheStratClassifier(WickThreshold);
            chartAtr = ATR(AtrPeriod);
            sessionTracker = new StratSessionTracker();
            stratGateDay = DateTime.MinValue;
            stratTradesToday = 0;
            pendingSig = 0;
            pendingTrigger = double.NaN;
            pendingStop = double.NaN;
            pendingTP1 = double.NaN;
            pendingTP2 = double.NaN;
            stagedFtfcScore = 0;
            stagedTargetDist = double.NaN;
        }

        protected override double GetCurrentATR()
        {
            if (chartAtr == null || CurrentBar < AtrPeriod)
                return 15.0 * TickSize * 4;
            return chartAtr[0];
        }

        protected override double GetPotentialLoss()
        {
            return 15.0 * GetPointValue() * Math.Max(1, DefaultQuantity);
        }

        /// <summary>
        /// DECLARE this bar's criteria. Phase order matches the original
        /// CheckForSignal exactly: confirm the staged setup first, then fall
        /// through to staging on confirmation failure. Staging declares no
        /// trigger — a bar that only stages is a Skip (the denominator), with
        /// the staging criteria recorded as a note for the roster.
        /// </summary>
        protected override void OnEvaluate(SetupEvaluation e)
        {
            if (stratClassifier == null) { e.Gate("warmup", false); return; }
            bool warmed = CurrentBar >= 4;
            e.Gate("warmup", warmed, CurrentBar, 4);
            if (!warmed) return;

            var gateCfg = StratConfig.Load();
            sessionTracker.Update(Time[0], Open[0]);
            DateTime today = Time[0].Date;
            if (today != stratGateDay) { stratGateDay = today; stratTradesToday = 0; pendingSig = 0; }
            bool useKz = UseKillzones && gateCfg.UseKillzones;

            // ── 1. Confirm the prior bar's staged setup (Python confirm_next_bar) ──
            if (pendingSig != 0)
            {
                int ps = pendingSig;
                double pt = pendingTrigger;
                pendingSig = 0;
                bool broke = !double.IsNaN(pt) && (ps > 0 ? High[0] >= pt : Low[0] <= pt);

                bool capOk = stratTradesToday < gateCfg.MaxTradesPerDay;
                bool windowOk = StratCore.EntryAllowed(Time[0], gateCfg.EarliestEntry, gateCfg.LatestEntry,
                    gateCfg.FlattenBy, gateCfg.Killzones, useKz);

                if (broke)
                {
                    e.Trigger(broke, ps > 0 ? "long" : "short");
                    e.Gate("strat_day_cap", capOk, stratTradesToday, gateCfg.MaxTradesPerDay);
                    e.Gate("entry_window", windowOk);
                    e.Measure("staged_ftfc_score", stagedFtfcScore);
                    e.Measure("staged_target_dist", stagedTargetDist, MinTargetPoints);

                    if (capOk && windowOk)
                    {
                        stratTradesToday++;
                        if (DrawVisuals)
                        {
                            string tag = "Strat22_Entry_" + CurrentBar;
                            if (ps == 1)
                                Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.Gold);
                            else
                                Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.Cyan);
                        }
                        return;
                    }
                }
                // Unconfirmed → fall through and stage any fresh setup on this bar.
            }

            // ── 2. Fresh setup: gate, score, stage (never enter on the signal bar) ──
            bool stageCapOk = stratTradesToday < gateCfg.MaxTradesPerDay;
            bool stageWindowOk = StratCore.EntryAllowed(Time[0], gateCfg.EarliestEntry, gateCfg.LatestEntry,
                    gateCfg.FlattenBy, gateCfg.Killzones, useKz);

            int sig = stratClassifier.Signal22Series[0];
            if (sig == 0) return;

            // FTFC alignment gate (signals.py mirror: long needs score >= +min, short <= -min).
            int scoreNow = sessionTracker.FtfcScore(Close[0]);
            bool ftfcOk = !(UseFtfcFilter && gateCfg.UseFtfcFilter)
                          || (sig > 0 && scoreNow >= MinFtfcScore)
                          || (sig < 0 && scoreNow <= -MinFtfcScore);

            double trig = stratClassifier.TriggerPriceSeries[0];
            bool hasTrig = !double.IsNaN(trig);

            double stp = stratClassifier.InsideBarStopSeries[0];
            double t1 = stratClassifier.MagnitudeTargetSeries[0];
            double t2 = stratClassifier.MagnitudeTarget2Series[0];
            bool hasBracket = !double.IsNaN(stp) && !double.IsNaN(t1) && !double.IsNaN(t2);
            bool geometryOk = hasBracket
                              && (sig > 0 ? (stp < trig && trig < t1 && t1 <= t2)
                                          : (stp > trig && trig > t1 && t1 >= t2));
            double targetDist = hasBracket ? Math.Abs(t1 - trig) : double.NaN;
            bool targetOk = hasBracket && targetDist >= MinTargetPoints;

            e.Note("stage_setup", (sig > 0 ? "2-2 rev long staged: " : "2-2 rev short staged: ")
                + "ftfc=" + scoreNow + "/" + MinFtfcScore
                + " trig=" + (hasTrig ? "ok" : "NaN")
                + " geometry=" + (geometryOk ? "ok" : "invalid")
                + " target=" + (double.IsNaN(targetDist) ? "NaN" : targetDist.ToString("G6"))
                + (targetOk ? "" : " < min " + MinTargetPoints)
                + (stageCapOk ? "" : " [cap reached]")
                + (stageWindowOk ? "" : " [window closed]"));

            if (!stageCapOk || !stageWindowOk) return;
            if (!hasTrig) return;
            if (!ftfcOk) return;
            if (!hasBracket) return;
            if (!geometryOk) return;
            if (!targetOk) return;

            pendingSig = sig;
            pendingTrigger = trig;
            pendingStop = stp;
            pendingTP1 = t1;
            pendingTP2 = t2;
            stagedFtfcScore = scoreNow;
            stagedTargetDist = targetDist;
            if (DrawVisuals)
            {
                string tag = "Strat22_Strat_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.Gold);
                    Draw.Text(this, tag + "_Txt", false, "2-2 REV BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.Cyan);
                    Draw.Text(this, tag + "_Txt", false, "2-2 REV SELL", 0, High[0] + (10 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
        }

        // Bracket levels come from the STAGED setup (signal bar), not the entry bar:
        // the classifier series no longer hold this setup one bar later. Staged
        // levels are validated at stage time (sides + MinTargetPoints); re-check
        // the side here against the actual fill, then hand them to the base.
        protected override double GetCustomStopPrice(int signal, double entryPrice)
        {
            if (double.IsNaN(pendingStop)) return double.NaN;
            if (signal > 0 && pendingStop >= entryPrice) return double.NaN;
            if (signal < 0 && pendingStop <= entryPrice) return double.NaN;
            return pendingStop;
        }

        protected override double GetCustomProfitTarget(int signal, double entryPrice, double stopDist)
        {
            if (double.IsNaN(pendingTP1)) return double.NaN;
            if (signal > 0 && pendingTP1 <= entryPrice) return double.NaN;
            if (signal < 0 && pendingTP1 >= entryPrice) return double.NaN;
            if (Math.Abs(pendingTP1 - entryPrice) < MinTargetPoints) return double.NaN;
            return pendingTP1;
        }

        protected override double GetCustomTP2(int signal, double entryPrice)
        {
            if (double.IsNaN(pendingTP2)) return double.NaN;
            if (signal > 0 && pendingTP2 <= entryPrice) return double.NaN;
            if (signal < 0 && pendingTP2 >= entryPrice) return double.NaN;
            return pendingTP2;
        }
    }
}
