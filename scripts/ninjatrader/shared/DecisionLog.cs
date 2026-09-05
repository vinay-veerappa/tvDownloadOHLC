// GENERATED FILE -- DO NOT EDIT.
//
// Source : scripts/trading_framework/reporting/decision_log.py (COLUMNS)
// Tool   : scripts/utils/generate_decision_log.py
// Spec   : docs/architecture/STRATEGY_WORKFLOW.md section 5.1
//
// Edit the Python schema and re-run the tool. A hand edit here is reverted
// by the next generation and fails test_decision_log.py in the meantime.
//
// WHAT THIS IS FOR: a trade list says what happened; only the strategy can
// say WHY. The gate roster this emits is also the cheapest parity check
// there is -- two sides evaluating different criteria are two strategies,
// and a trade-set recall between them is a number about nothing.
//
// FOUR RULES, each a failure mode of the per-bar dump this replaces:
//   1. Log DECISIONS, not bars. Rows are bounded by triggers x gates.
//   2. Record EVERY gate. `&&` stops early, so a first-failure log
//      reports the short-circuit ORDER as the cause. Gate() is called
//      before the verdict for exactly this reason.
//   3. Record the VALUE, not just pass/fail. "ADX passed" is not
//      analysable; "ADX 18.2 vs 15" says the trade was marginal.
//   4. Rejections need a DENOMINATOR -- Skip() counts bars that never
//      triggered, or "gate X blocked 40 setups" has no scale.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>One named criterion, its outcome, and the numbers behind it.</summary>
    public struct DecisionGate
    {
        public string Name;
        public bool   Passed;
        public double Value;
        public double Threshold;
        public bool   HasValue;
        public bool   HasThreshold;
        public string Detail;
        /// <summary>"gate" blocks and enters the roster; "measure" is a
        /// covariate that never blocks. Recording a magnitude as a gate
        /// produces a 0%-failure gate -- a green that can never be red.</summary>
        public string Kind;
    }

    /// <summary>
    /// One decision under construction. Gates are added BEFORE the verdict so
    /// that every one is evaluated (rule 2); a verdict taken first would let
    /// the caller short-circuit and record only the earliest failure.
    /// </summary>
    public class DecisionBuilder
    {
        private readonly DecisionLog log;
        private readonly DateTime   barTime;
        private readonly string     direction;
        private readonly List<DecisionGate> gates = new List<DecisionGate>();

        internal DecisionBuilder(DecisionLog log, DateTime barTime, string direction)
        { this.log = log; this.barTime = barTime; this.direction = direction ?? ""; }

        public DecisionBuilder Gate(string name, bool passed)
        { return Add(name, passed, 0, false, 0, false, null, "gate"); }

        public DecisionBuilder Gate(string name, bool passed, double value)
        { return Add(name, passed, value, true, 0, false, null, "gate"); }

        public DecisionBuilder Gate(string name, bool passed, double value, double threshold)
        { return Add(name, passed, value, true, threshold, true, null, "gate"); }

        /// <summary>A covariate for the win/loss analysis. NEVER blocks, and
        /// never enters the roster: recording "close is past the band" as a
        /// gate on bars that triggered BECAUSE the close is past the band gives
        /// a gate with a structural 0% failure rate.</summary>
        public DecisionBuilder Measure(string name, double value)
        { return Add(name, true, value, true, 0, false, null, "measure"); }

        public DecisionBuilder Measure(string name, double value, double threshold)
        { return Add(name, true, value, true, threshold, true, null, "measure"); }

        public DecisionBuilder Note(string name, bool passed, string detail)
        { return Add(name, passed, 0, false, 0, false, detail, "note"); }

        private DecisionBuilder Add(string name, bool passed, double value, bool hasValue,
                                    double threshold, bool hasThreshold, string detail,
                                    string kind)
        {
            if (string.IsNullOrWhiteSpace(name))
                name = "unnamed";   // never drop a gate; an unnamed one is still a row
            gates.Add(new DecisionGate {
                Name = name, Passed = passed, Value = value, Threshold = threshold,
                HasValue = hasValue, HasThreshold = hasThreshold, Detail = detail,
                Kind = kind });
            return this;
        }

        /// <summary>Every gate passed and the order was submitted.</summary>
        /// <param name="signalName">The NT8 order signal name. It is the JOIN KEY
        /// to the fill (Execution.Name), so it MUST be unique per entry -- a
        /// constant name makes every entry indistinguishable downstream.</param>
        public void Entry(string signalName) { log.Write(barTime, "ENTRY", direction, signalName, gates); }

        /// <summary>A setup existed and a gate stopped it.</summary>
        public void Reject() { log.Write(barTime, "REJECTED", direction, "", gates); }

        /// <summary>True when no gate failed -- so the caller can branch on the
        /// SAME data it logged, rather than re-evaluating the conditions and
        /// risking a log that disagrees with the behaviour it describes.</summary>
        public bool AllPassed
        {
            get {
                foreach (var g in gates)
                    if (g.Kind == "gate" && !g.Passed) return false;
                return true;
            }
        }
    }

    /// <summary>
    /// Appends decision rows to an mcp_*.csv in Globals.UserDataDir, which the
    /// bridge's existing nt_get_export endpoint already serves. Never throws into
    /// the strategy: a logging failure must not kill a backtest. It is not silent
    /// either -- LastError is set and printed once, because a logger that fails
    /// quietly produces a short file that reads as "the strategy took no trades".
    /// </summary>
    public class DecisionLog : IDisposable
    {
        public const int    SchemaVersion = 1;
        public const string FilePrefix    = "mcp_decisions_";

        // The column order IS the schema. Generated from decision_log.COLUMNS.
        public const string Header =
            "schema_version,"
            + "run_id,"
            + "side,"
            + "strategy,"
            + "seq,"
            + "bar_time,"
            + "session,"
            + "direction,"
            + "decision,"
            + "signal_name,"
            + "gate,"
            + "kind,"
            + "gate_pass,"
            + "gate_value,"
            + "gate_threshold,"
            + "detail";

        // Recognised decision values, mirrored from decision_log.DECISIONS.
        public static readonly string[] Decisions = new string[] { "ENTRY", "REJECTED", "EXIT", "SKIP" };

        public string Path      { get; private set; }
        public string LastError { get; private set; }
        public int    Skipped   { get; private set; }
        public int    Bars      { get; private set; }

        private readonly string runId;
        private readonly string strategy;
        private StreamWriter    w;
        private int             seq;
        private bool            printed;

        // Instance counter: the Strategy Analyzer runs many instances of one
        // strategy CONCURRENTLY during an optimisation, and two of them opening
        // the same path is a truncated file rather than an error.
        private static int instances;

        public DecisionLog(string strategyName, string runId)
        {
            this.strategy = strategyName ?? "unknown";
            this.runId    = string.IsNullOrWhiteSpace(runId) ? "na" : runId;
            try
            {
                int n = System.Threading.Interlocked.Increment(ref instances);
                string name = string.Format(CultureInfo.InvariantCulture,
                    "{0}{1}_{2}_{3:D3}.csv", FilePrefix, Sanitize(this.strategy),
                    DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture), n);
                Path = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir, name);
                w = new StreamWriter(Path, false, new UTF8Encoding(false));
                w.WriteLine(Header);
                w.Flush();
            }
            catch (Exception ex) { LastError = ex.Message; w = null; }
        }

        /// <summary>Start a decision. Add gates, then call Entry or Reject.</summary>
        public DecisionBuilder Decision(DateTime barTime, string direction)
        { return new DecisionBuilder(this, barTime, direction); }

        /// <summary>A bar that produced no setup at all. Counted, not written --
        /// the denominator is what rule 4 needs, and a row per quiet bar would be
        /// the per-bar dump this class exists to replace.</summary>
        public void Skip() { Bars++; Skipped++; }

        /// <summary>A bar that produced a setup. Counts toward Bars only.</summary>
        public void Bar() { Bars++; }

        internal void Write(DateTime barTime, string decision, string direction,
                            string signalName, List<DecisionGate> gates)
        {
            if (w == null) return;
            seq++;
            try
            {
                string stamp   = barTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);
                string session = TradingDefaults.SessionFor(barTime.Hour * 100 + barTime.Minute);
                if (gates == null || gates.Count == 0)
                {
                    Row(stamp, session, direction, decision, signalName, "", "note",
                        decision != "REJECTED", "", "", "");
                }
                else
                {
                    foreach (var g in gates)
                        Row(stamp, session, direction, decision, signalName, g.Name,
                            string.IsNullOrEmpty(g.Kind) ? "gate" : g.Kind, g.Passed,
                            g.HasValue     ? Num(g.Value)     : "",
                            g.HasThreshold ? Num(g.Threshold) : "",
                            g.Detail ?? "");
                }
                // Flush per DECISION, not per bar. An SA run that is cancelled, or a
                // strategy that throws, otherwise loses the tail -- and the tail is
                // where the interesting decisions are.
                w.Flush();
            }
            catch (Exception ex) { LastError = ex.Message; }
        }

        private void Row(string stamp, string session, string direction, string decision,
                         string signalName, string gate, string kind, bool pass,
                         string value, string threshold, string detail)
        {
            w.WriteLine(string.Join(",", new string[] {
                SchemaVersion.ToString(CultureInfo.InvariantCulture),
                Q(runId), "nt8", Q(strategy),
                seq.ToString(CultureInfo.InvariantCulture),
                stamp, Q(session), Q(direction), decision, Q(signalName), Q(gate),
                kind, pass ? "1" : "0", value, threshold, Q(detail) }));
        }

        /// <summary>Emits the SKIP denominator row. Call from OnTermination.</summary>
        public void Dispose()
        {
            if (w == null) return;
            try
            {
                w.WriteLine(string.Join(",", new string[] {
                    SchemaVersion.ToString(CultureInfo.InvariantCulture),
                    Q(runId), "nt8", Q(strategy), "0", "", "", "", "SKIP", "", "",
                    "note", "1",
                    Skipped.ToString(CultureInfo.InvariantCulture),
                    Bars.ToString(CultureInfo.InvariantCulture),
                    Q("bars with no trigger of any kind (rule 4 denominator)") }));
                w.Flush(); w.Close();
            }
            catch (Exception ex) { LastError = ex.Message; }
            finally { w = null; }
        }

        /// <summary>What to Print() once, so an operator can FIND the file. The
        /// existing per-bar dump printed a %TEMP% GUID path and nothing else,
        /// which is data that exists and cannot be addressed.</summary>
        public string Banner()
        {
            printed = true;
            if (LastError != null)
                return "[DECISIONLOG] DISABLED: " + LastError;
            return "[DECISIONLOG] " + System.IO.Path.GetFileName(Path)
                 + " (fetch with nt_get_export)";
        }

        public bool Printed { get { return printed; } }

        private static string Num(double v)
        {
            if (double.IsNaN(v) || double.IsInfinity(v)) return "";
            return v.ToString("G6", CultureInfo.InvariantCulture);
        }

        // A gate name or a detail containing a comma would shift every column to
        // its right, and the Python reader would refuse the file -- which is the
        // good outcome, but only after a wasted run. Quote instead.
        private static string Q(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            if (s.IndexOf(',') < 0 && s.IndexOf('"') < 0 && s.IndexOf('\n') < 0) return s;
            return "\"" + s.Replace("\"", "\"\"") + "\"";
        }

        private static string Sanitize(string s)
        {
            var sb = new StringBuilder();
            foreach (var c in s)
                sb.Append(char.IsLetterOrDigit(c) || c == '_' || c == '-' ? c : '_');
            return sb.ToString();
        }
    }
}
