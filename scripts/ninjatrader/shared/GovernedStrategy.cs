// GovernedStrategy -- the governance layer every bot in this repo inherits.
//
// Spec: docs/architecture/STRATEGY_WORKFLOW.md section 3.4
//
// WHY A BASE CLASS, AND WHY NOT `RiskManagerBase` ITSELF. Ten of the fourteen
// bots here already inherit `RiskManagerBase`, and tickets B1-B6 exist because
// those same ten hardcoded their own flatten times and trade caps anyway. The
// pattern "a base class the bot may CONSULT" has been tried and did not hold: a
// default a bot is free to restate is a default it will restate.
//
// `RiskManagerBase` is also not ours to change -- nt8-riskguard owns it
// (`strategies/Vinay/RiskManagerBase.cs`) and it arrives here through the
// bridge's vendored-core sweep. ADR-025: one artifact, one owner. The split:
//
//     RiskManagerBase   (nt8-riskguard)  the loop, brackets, stops, sizing
//     GovernedStrategy  (this repo)      the WORKFLOW's rules, listed below
//
// WHAT MAKES THE LOGGING NON-BYPASSABLE. `RiskManagerBase` owns `OnBarUpdate`
// and asks its subclass exactly one question -- `CheckForSignal()`, returning
// 1 / -1 / 0. **This class SEALS that method.** The only way a bot can produce a
// signal is by declaring gates that pass, and the return value is COMPUTED from
// the gates rather than supplied alongside them. So a criterion the log does not
// carry cannot influence a trade: there is no such code path. Contrast a helper
// the bot calls, where the bot can log one thing and do another and nothing
// notices -- the same defect class as a config that reads as protection which is
// not enforced.
//
// THE SUBCLASS DECLARES; IT DOES NOT ACT. `OnEvaluate` receives a
// `SetupEvaluation` and contains no orders, no clock reads and no logging calls.
// A bot cannot forget to log because it never had the option.
//
// FIVE THINGS THIS GOVERNS
//
//  1. The frozen defaults (section 1.3) are PUSHED into RiskManagerBase's own
//     properties before the bot's `OnStrategyDefaults()` runs, and ADR-020's
//     16:00 hard exit is re-clamped AFTER it -- so a bot that sets a later
//     flatten time is corrected rather than trusted. `BBMRReversionBot`
//     flattened at 16:15 for an unknown period.
//  2. A null cap is `NoLimit` (-1), never 0 -- which any `>=` comparison reads
//     as "no trades allowed".
//  3. Unique entry signal names. `RiskManagerBase.GetSignalName` returns
//     `"<Strategy>_Long"` for EVERY long entry ever taken, so no fill can be
//     joined to a specific decision; this overrides it with a per-entry name.
//     The `_Queen` / `_Runner` suffixes the base appends then give the two legs
//     of one bracket a shared entry key, which is what the leg convention needs.
//  4. Its own refusals, recorded as gates under the frozen names in
//     `TradingDefaults.GovernanceGates`.
//  5. `CanEnterTrade`'s NINE refusal paths -- gatekeeper, account blown, done
//     for day, paused after consecutive losses, max trades, two time fences and
//     two daily-loss limits. Every one is computed and then visible only under
//     `DebugMode` on 1% of bars, so "why did the bot not trade" had nine
//     invisible answers. `OnEntryBlocked` turns each into a logged gate. This is
//     the C# half of the funnel gap section 11 item 13 records for Python.

using System;
using System.Collections.Generic;
using System.Globalization;
using NinjaTrader.Cbi;

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// THE MANDATED STRUCTURE. A subclass fills one of these in and returns; the
    /// base reads it and decides. It deliberately exposes nothing that places an
    /// order, moves a stop or writes a file -- every means by which a bot could
    /// diverge from its own log is absent by construction rather than by rule.
    /// </summary>
    public sealed class SetupEvaluation
    {
        internal readonly List<DecisionGate> Gates = new List<DecisionGate>();

        /// <summary>Direction of the declared setup, or "" if none.</summary>
        public string Direction { get; private set; }

        /// <summary>Did this bar produce a setup at all? Without it every bar is
        /// a candidate and the rejection counts have no denominator, so "gate X
        /// blocked 40 setups" cannot be scaled (rule 4).</summary>
        public bool HasTrigger { get { return !string.IsNullOrEmpty(Direction); } }

        /// <summary>The DECLARED queen-leg target for this setup, or NaN when
        /// none was declared (section 11 item 19). Captured at arm time like
        /// the limit and the stop; the base owns the right-side guard and the
        /// bps fallback, so an invalid declaration falls back rather than
        /// blocking, exactly like the Python engine.</summary>
        public double DeclaredTarget { get; private set; }

        internal bool HasDeclaredTarget { get { return !double.IsNaN(DeclaredTarget); } }

        internal SetupEvaluation() { Direction = ""; DeclaredTarget = double.NaN; }

        /// <summary>A setup EXISTS on this bar. Call before any Gate.</summary>
        public SetupEvaluation Trigger(string direction)
        {
            if (!string.IsNullOrEmpty(direction)) Direction = direction;
            return this;
        }

        public SetupEvaluation Trigger(bool condition, string direction)
        { return condition ? Trigger(direction) : this; }

        /// <summary>
        /// DECLARE the payoff this setup promises (section 11 item 19): the
        /// price at which the QUEEN leg should exit. Same declare-don't-act
        /// shape as Trigger/Gate/Measure -- it cannot place an order or move
        /// anything. NaN / absent means "no declaration" and behaves exactly
        /// like the bps fallback; a WRONG-SIDE declaration (behind entry) is
        /// refused by the base's guard and falls back to bps VISIBLY -- the
        /// refusal is logged, never silent. Never blocks the trade.
        /// </summary>
        public SetupEvaluation DeclareTarget(double price)
        { DeclaredTarget = price; return this; }

        /// <summary>A criterion that CAN BLOCK the setup. Enters the roster.
        ///
        /// Call every one unconditionally. `&amp;&amp;` short-circuits, so
        /// lifting these out of an existing `if` chain records the SHORT-CIRCUIT
        /// ORDER as the cause of a rejection instead of the reason (rule 2).
        /// </summary>
        public SetupEvaluation Gate(string name, bool passed)
        { return Add(name, passed, 0, false, 0, false, null, "gate"); }

        public SetupEvaluation Gate(string name, bool passed, double value)
        { return Add(name, passed, value, true, 0, false, null, "gate"); }

        /// <summary>PREFERRED FORM: the value and what it was compared to. "ADX
        /// passed" is not analysable; "ADX 18.2 vs 15" says the trade was
        /// marginal, which is what separates a losing trade from a badly gated
        /// one (rule 3).</summary>
        public SetupEvaluation Gate(string name, bool passed, double value, double threshold)
        { return Add(name, passed, value, true, threshold, true, null, "gate"); }

        /// <summary>A covariate for the win/loss analysis. NEVER blocks.
        ///
        /// Use for a MAGNITUDE. Recording "close is past the band" as a Gate, on
        /// bars that triggered BECAUSE the close is past the band, yields a gate
        /// with a structural 0% failure rate -- a green that can never be red --
        /// which would top every roster and inflate the set the parity diff runs
        /// over (rule 6).</summary>
        public SetupEvaluation Measure(string name, double value)
        { return Add(name, true, value, true, 0, false, null, "measure"); }

        public SetupEvaluation Measure(string name, double value, double threshold)
        { return Add(name, true, value, true, threshold, true, null, "measure"); }

        public SetupEvaluation Note(string name, string detail)
        { return Add(name, true, 0, false, 0, false, detail, "note"); }

        private SetupEvaluation Add(string name, bool passed, double value, bool hasValue,
                                    double threshold, bool hasThreshold, string detail,
                                    string kind)
        {
            if (string.IsNullOrWhiteSpace(name))
                name = "unnamed";     // never DROP a gate; an unnamed one is still a row
            Gates.Add(new DecisionGate {
                Name = name, Passed = passed, Value = value, Threshold = threshold,
                HasValue = hasValue, HasThreshold = hasThreshold, Detail = detail,
                Kind = kind });
            return this;
        }

        /// <summary>True when no BLOCKING gate failed. A `measure` carries a
        /// meaningless pass flag and must not enter the verdict.</summary>
        public bool AllGatesPassed
        {
            get
            {
                foreach (var g in Gates)
                    if (g.Kind == "gate" && !g.Passed) return false;
                return true;
            }
        }
    }

    public abstract class GovernedStrategy : RiskManagerBase
    {
        // ---- what a subclass implements ------------------------------------- //

        /// <summary>
        /// DECLARE this bar's setup and every criterion behind it. Place no
        /// orders, read no clock, write no files: the base does all three from
        /// what is declared here.
        /// </summary>
        protected abstract void OnEvaluate(SetupEvaluation e);

        /// <summary>The bot's own NT8 defaults. Called AFTER the frozen defaults
        /// are applied, and ADR-020's hard exit is re-clamped afterwards -- so a
        /// value set here that exceeds it is corrected, not trusted.</summary>
        protected virtual void OnStrategyDefaults() { }

        /// <summary>Indicators and per-run state. Called after the decision log
        /// is open, so a subclass may Print alongside the banner.</summary>
        protected virtual void OnInitialize() { }

        /// <summary>
        /// The one abstract member of RiskManagerBase GovernedStrategy does not
        /// otherwise touch. Implemented empty so a bot with nothing to configure
        /// need not restate a `ConfigureStrategy() { }` stub per file; a subclass
        /// that DOES add data series overrides it as before.
        /// </summary>
        protected override void ConfigureStrategy() { }

        /// <summary>A short stable tag for signal names. The class name is fine;
        /// override only to shorten it.</summary>
        protected virtual string SignalTag { get { return GetType().Name; } }

        // ---- state the base owns -------------------------------------------- //

        private DecisionLog decisions;
        private int         entrySeq;
        private string      pendingSignalName;
        private double      pendingDeclaredTarget = double.NaN;

        protected DecisionLog Decisions { get { return decisions; } }

        // ---- the frozen defaults, pushed not offered ------------------------ //

        protected sealed override void SetStrategyDefaults()
        {
            // Section 1.3. Assigned BEFORE the bot's own defaults so a bot can
            // still choose a legitimately different flatten time (`overridable`),
            // and the hard exit is re-clamped after, because that one is not.
            FlattenBy = TradingDefaults.FlattenBy;

            // A null cap is NoLimit (-1). RiskManagerBase compares
            // `todayTradeCount >= MaxTradesPerDay`, so 0 would read as "no trades
            // allowed" and int.MaxValue would vanish into arithmetic.
            if (TradingDefaults.MaxTradesPerDay != TradingDefaults.NoLimit)
                MaxTradesPerDay = TradingDefaults.MaxTradesPerDay;

            OnStrategyDefaults();

            // ADR-020. A prop account can be liquidated by a position held past
            // 16:00, so this is applied LAST and unconditionally. It is the one
            // value in the frozen document that is neither overridable nor
            // analysis-derived.
            int hardExitHhmm = TradingDefaults.RthHardExit;
            if (FlattenBy * 100 > hardExitHhmm * 100 || FlattenBy > hardExitHhmm)
                FlattenBy = hardExitHhmm;
            if (LatestEntry > hardExitHhmm)
                LatestEntry = hardExitHhmm;
        }

        protected sealed override void InitializeStrategy()
        {
            decisions = new DecisionLog(GetType().Name, RunId());
            Print(decisions.Banner());
            OnInitialize();
        }

        /// <summary>Ties the log to a workflow run when one is driving it, and to
        /// the wall clock otherwise. Deliberately not a GUID: a run id nobody can
        /// correlate is the same problem as the %TEMP% GUID path this
        /// replaces.</summary>
        protected virtual string RunId()
        {
            var env = Environment.GetEnvironmentVariable("TVD_RUN_ID");
            return string.IsNullOrWhiteSpace(env)
                ? DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture)
                : env;
        }

        // ---- the one question RiskManagerBase asks, sealed ------------------ //

        /// <summary>
        /// SEALED. The verdict is COMPUTED from the declared gates, which is what
        /// makes the log impossible to diverge from: a bot cannot return a signal
        /// whose reasons are not recorded, because it does not return the signal.
        /// </summary>
        protected sealed override int CheckForSignal()
        {
            if (decisions == null) return 0;      // log not open: never trade unlogged

            var e = new SetupEvaluation();
            OnEvaluate(e);

            // Rule 4: a bar with no setup is the DENOMINATOR. Counted, never
            // written -- a row per quiet bar is the per-bar dump this replaces.
            if (!e.HasTrigger) { decisions.Skip(); return 0; }
            decisions.Bar();

            var d = decisions.Decision(Time[0], e.Direction);
            foreach (var g in e.Gates) d.Add(g);

            int hhmm = Time[0].Hour * 100 + Time[0].Minute;
            // The base's own rules land on the SAME decision, so a framework
            // refusal is attributable rather than looking like the strategy
            // declining. Every one is evaluated -- no short circuit -- for the
            // same reason the subclass's are.
            bool govOk = true;
            govOk &= Governance(d, TradingDefaults.GateLastEntry,
                hhmm < TradingDefaults.LastEntry, hhmm, TradingDefaults.LastEntry);
            govOk &= Governance(d, TradingDefaults.GateHardExit,
                hhmm < TradingDefaults.RthHardExit, hhmm, TradingDefaults.RthHardExit);

            if (!e.AllGatesPassed || !govOk) { d.Reject(); return 0; }

            // Section 11 item 19: the declared queen-leg target, evaluated
            // against the direction EXACTLY like the Python engine's fill-time
            // guard. Logged either way -- a refusal that is silent is the same
            // defect class as a refusal that never happened. A note never
            // blocks, so recording it here cannot contradict the verdict.
            bool longSide = !e.Direction.StartsWith("s", StringComparison.OrdinalIgnoreCase);
            pendingDeclaredTarget = double.NaN;
            if (e.HasDeclaredTarget)
            {
                double t = e.DeclaredTarget;
                bool rightSide = longSide ? t > Close[0] : t < Close[0];
                if (rightSide)
                {
                    d.Note("declared_queen_target", true, "used: " + t.ToString("G6", CultureInfo.InvariantCulture));
                }
                else
                {
                    // The geometry-defect class: a target behind entry would
                    // fill instantly and pay a nonsense profit. Falls back to
                    // bps, VISIBLY.
                    d.Note("queen_bps_fallback", false, "declared target " +
                        t.ToString("G6", CultureInfo.InvariantCulture) +
                        " refused: wrong side of " + (longSide ? "long" : "short"));
                }
                // Hand the RAW declaration to the risk base either way; the
                // base's own guard re-checks the side at fill time against the
                // EFFECTIVE entry (which may be a limit price, not this close),
                // so this note is the decision-time record and the base is the
                // fill-time one.
                pendingDeclaredTarget = t;
            }
            else
            {
                d.Note("queen_bps_fallback", true, "no target declared: " + TradingDefaults.QueenBps + " bps");
            }

            // Named HERE and handed to GetSignalName, because RiskManagerBase
            // asks for the name after this returns. Recording the ENTRY before
            // the order is placed is deliberate: a rejected or unfilled order is
            // still a decision that was taken, and dropping it would make the log
            // describe fills rather than decisions.
            pendingSignalName = NextSignalName(e.Direction);
            d.Entry(pendingSignalName);

            return e.Direction.StartsWith("s", StringComparison.OrdinalIgnoreCase) ? -1 : 1;
        }

        // ---- the nine invisible refusals ------------------------------------ //

        /// <summary>
        /// `CanEnterTrade` refused, and it says why. Nine distinct reasons were
        /// previously computed and then logged only under `DebugMode` on 1% of
        /// bars, so a bot that quietly stopped trading had nine possible causes
        /// and no record of which. Each becomes a gate on its own decision.
        ///
        /// Recorded with no direction: `CanEnterTrade` runs BEFORE
        /// `CheckForSignal`, so at this point nobody has asked the strategy
        /// whether it even had a setup. Claiming one would be inventing it.
        /// </summary>
        protected override void OnEntryBlocked(string reason, int currentTime)
        {
            base.OnEntryBlocked(reason, currentTime);
            if (decisions == null) return;
            decisions.Decision(Time[0], "")
                .Note("entry_blocked", false, reason ?? "unstated")
                .Reject();
        }

        // ---- unique entry names --------------------------------------------- //

        /// <summary>
        /// Overrides a base that returned `"<Strategy>_Long"` for every long
        /// entry ever taken. That name becomes `Execution.Name` on the fill and
        /// is the join key back to the decision log, so a constant made every
        /// entry indistinguishable and forced an approximate nearest-time join.
        ///
        /// `RiskManagerBase` appends `_Queen` / `_Runner` (or `_Leg1` / `_Leg2`),
        /// so the two legs of one bracket share this entry key -- which is
        /// exactly what the leg convention needs to group them.
        /// </summary>
        protected override string GetSignalName(string direction)
        {
            return string.IsNullOrEmpty(pendingSignalName)
                ? base.GetSignalName(direction)   // a path that did not go through CheckForSignal
                : pendingSignalName;
        }

        private string NextSignalName(string direction)
        {
            entrySeq++;
            // Per RUN, not per day: two entries then cannot collide even across a
            // day boundary, and the number is readable in an NT8 execution list.
            return string.Format(CultureInfo.InvariantCulture, "{0}_{1}_{2:D5}",
                SignalTag,
                direction.StartsWith("s", StringComparison.OrdinalIgnoreCase) ? "S" : "L",
                entrySeq);
        }

        // ---- the declared queen-leg target (section 11 item 19) ------------- //

        /// <summary>
        /// Arm-time capture, exactly like `GetCustomLimitPrice`: `CheckForSignal`
        /// stashed what the subclass declared in `pendingDeclaredTarget`, and the
        /// risk base consults this hook in its CoverTheQueen bracket path. The
        /// base owns the FILL-TIME right-side guard and the bps fallback (it
        /// knows the effective entry, which may be a limit price, not the close
        /// this note was recorded against); NaN here means "no declaration".
        /// </summary>
        protected override double GetDeclaredQueenTarget(int signal, double entryPrice)
        {
            return pendingDeclaredTarget;
        }

        // ---- helpers -------------------------------------------------------- //

        /// <summary>Records the gate and returns whether it passed, so the caller
        /// cannot decide on a value different from the one it logged.
        ///
        /// A limit of `NoLimit` is recorded as a MEASURE, not omitted: an absent
        /// row and a satisfied row are different statements, and the caps are
        /// `analysisDerived` (null today), so omitting them would make the roster
        /// change shape on the day a cap is finally set.</summary>
        private bool Governance(DecisionBuilder d, string name, bool passed,
                                double value, int limit)
        {
            if (limit == TradingDefaults.NoLimit) { d.Measure(name, value); return true; }
            d.Gate(name, passed, value, limit);
            return passed;
        }
    }
}
