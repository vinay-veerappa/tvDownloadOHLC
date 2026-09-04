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
    /// Strat212ContinuationBot - Automated 2-1-2 Strat Continuation Strategy.
    /// Consumes TheStratClassifier indicator for visual rendering and signals.
    /// Inherits from RiskManagerBase for centralized risk management and ATM execution.
    /// </summary>
    public class Strat212ContinuationBot : RiskManagerBase
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

        protected override string GetStrategyName() => "Strat212Bot";

        protected override void SetStrategyDefaults()
        {
            Description = "Automated 2-1-2 Strat continuation bot consuming TheStratClassifier with centralized RiskManagerBase";
            Name = "Strat212ContinuationBot";

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
            AddSecondaryTimeframe = false; // Self-contained on chart series
        }

        protected override void ConfigureStrategy() { }

        protected override void InitializeStrategy()
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

        protected override int CheckForSignal()
        {
            if (stratClassifier == null || CurrentBar < 4) return 0;

            // ── Canonical Strat gates (mirror of Python signals.py) ──
            // Bot-owned: RiskManagerBase skips its trade cap in backtests
            // (unregistered account), so the bot enforces the config max itself —
            // identical number live and in Strategy Analyzer.
            var gateCfg = StratConfig.Load();
            sessionTracker.Update(Time[0], Open[0]);
            DateTime today = Time[0].Date;
            if (today != stratGateDay) { stratGateDay = today; stratTradesToday = 0; pendingSig = 0; }
            bool useKz = UseKillzones && gateCfg.UseKillzones;

            // ── 1. Confirm the prior bar's staged setup (Python confirm_next_bar) ──
            // Entry bar re-checks day-cap + killzone (entry must be tradable too);
            // FTFC was scored at the signal bar, exactly like signals.py.
            if (pendingSig != 0)
            {
                int ps = pendingSig;
                double pt = pendingTrigger;
                pendingSig = 0;
                bool broke = !double.IsNaN(pt) && (ps > 0 ? High[0] >= pt : Low[0] <= pt);
                if (broke
                    && stratTradesToday < gateCfg.MaxTradesPerDay
                    && StratCore.EntryAllowed(Time[0], gateCfg.EarliestEntry, gateCfg.LatestEntry,
                        gateCfg.FlattenBy, gateCfg.Killzones, useKz))
                {
                    stratTradesToday++;
                    if (DrawVisuals)
                    {
                        string tag = "Strat212_Entry_" + CurrentBar;
                        if (ps == 1)
                            Draw.ArrowUp(this, tag, false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                        else
                            Draw.ArrowDown(this, tag, false, 0, High[0] + (4 * TickSize), Brushes.Red);
                    }
                    return ps;
                }
                // Unconfirmed → fall through and stage any fresh setup on this bar.
            }

            // ── 2. Fresh setup: gate, score, stage (never enter on the signal bar) ──
            if (stratTradesToday >= gateCfg.MaxTradesPerDay) return 0;
            // Killzone gate (session.py mirror; base still owns earliest/latest/flatten).
            if (!StratCore.EntryAllowed(Time[0], gateCfg.EarliestEntry, gateCfg.LatestEntry,
                    gateCfg.FlattenBy, gateCfg.Killzones, useKz))
                return 0;

            int sig = stratClassifier.Signal212Series[0];
            if (sig == 0) return 0;
            // FTFC alignment gate (signals.py mirror: long needs score >= +min, short <= -min).
            if (UseFtfcFilter && gateCfg.UseFtfcFilter)
            {
                int score = sessionTracker.FtfcScore(Close[0]);
                if (sig > 0 && score < MinFtfcScore) return 0;
                if (sig < 0 && score > -MinFtfcScore) return 0;
            }
            double trig = stratClassifier.TriggerPriceSeries[0];
            if (double.IsNaN(trig)) return 0;
            // Capture the FULL bracket now: the base reads stop/targets on the
            // ENTRY bar (next bar), when these series no longer hold this setup.
            double stp = stratClassifier.InsideBarStopSeries[0];
            double t1 = stratClassifier.MagnitudeTargetSeries[0];
            double t2 = stratClassifier.MagnitudeTarget2Series[0];
            if (double.IsNaN(stp) || double.IsNaN(t1) || double.IsNaN(t2)) return 0;
            if (sig > 0 && !(stp < trig && trig < t1 && t1 <= t2)) return 0;
            if (sig < 0 && !(stp > trig && trig > t1 && t1 >= t2)) return 0;
            if (Math.Abs(t1 - trig) < MinTargetPoints) return 0;
            pendingSig = sig;
            pendingTrigger = trig;
            pendingStop = stp;
            pendingTP1 = t1;
            pendingTP2 = t2;
            if (DrawVisuals)
            {
                string tag = "Strat212_Strat_" + CurrentBar;
                if (sig == 1)
                {
                    Draw.ArrowUp(this, tag + "_Arrow", false, 0, Low[0] - (4 * TickSize), Brushes.LimeGreen);
                    Draw.Text(this, tag + "_Txt", false, "2-1-2 BUY", 0, Low[0] - (10 * TickSize), 0, Brushes.LimeGreen, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                else if (sig == -1)
                {
                    Draw.ArrowDown(this, tag + "_Arrow", false, 0, High[0] + (4 * TickSize), Brushes.Red);
                    Draw.Text(this, tag + "_Txt", false, "2-1-2 SELL", 0, High[0] + (10 * TickSize), 0, Brushes.Red, new SimpleFont("Arial", 9), TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
            }
            return 0;
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
