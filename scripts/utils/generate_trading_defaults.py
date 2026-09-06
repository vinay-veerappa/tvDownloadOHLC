"""Generate `scripts/ninjatrader/shared/TradingDefaults.cs` from the frozen JSON.

ONE SOURCE, THREE CONSUMERS (STRATEGY_WORKFLOW.md section 1.3): the Python engine
reads `trading_defaults.json` directly, the NT8 Strategy Analyzer profile is
cross-checked against its `nt8` block, and the C# bot reads the class this script
emits. Generated rather than hand-written because a second hand-maintained copy
is the drift this whole exercise exists to remove.

WHY A GENERATOR AND NOT A RUNTIME READ. `StratConfig.cs` already reads a JSON at
runtime and is explicitly FAIL-OPEN -- "any missing file / parse error returns
compiled defaults". That is right for tunables a human edits between runs, and
wrong for these: a bot that silently falls back to its own flatten time is the
defect being fixed. Compiled-in constants cannot fail open.

    python scripts/utils/generate_trading_defaults.py           # write
    python scripts/utils/generate_trading_defaults.py --check   # verify only

`--check` is what the test calls: it regenerates in memory and compares, so a
JSON edit that was never propagated to C# fails a build instead of drifting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "trading_framework" / "config" / "trading_defaults.json"
OUT = REPO / "scripts" / "ninjatrader" / "shared" / "TradingDefaults.cs"


def _hhmm_to_int(hhmm: str) -> int:
    """"15:45" -> 1545, the form NT8 strategies compare against."""
    h, m = hhmm.split(":")
    return int(h) * 100 + int(m)


def _int_or_nolimit(v) -> str:
    """A null cap is NoLimit (-1), never 0 -- see the emitted comment."""
    return "NoLimit" if v is None else str(int(v))


def _time_or_nolimit(v) -> str:
    return "NoLimit" if v is None else str(_hhmm_to_int(v))


def source_hash(text: str) -> str:
    """Hash of the canonical JSON, so C# can assert it matches what Python read."""
    canonical = json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def render(raw: str) -> str:
    d = json.loads(raw)
    inst = d["instruments"]
    risk = d["risk"]
    execu = d["execution"]
    nt8 = d["nt8"]
    sessions = d["sessions"]

    L: list[str] = []
    a = L.append
    a("// GENERATED FILE -- DO NOT EDIT.")
    a("//")
    a("// Source : scripts/trading_framework/config/trading_defaults.json")
    a("// Tool   : scripts/utils/generate_trading_defaults.py")
    a("// Spec   : docs/architecture/STRATEGY_WORKFLOW.md section 1.3")
    a("//")
    a("// Edit the JSON and re-run the tool. A hand edit here is reverted by the")
    a("// next generation and fails test_bot_defaults.py in the meantime.")
    a("//")
    a("// WHY COMPILED CONSTANTS AND NOT A RUNTIME JSON READ: StratConfig.cs reads")
    a("// its JSON at runtime and is deliberately FAIL-OPEN. That is correct for")
    a("// tunables and wrong for these -- a bot that silently falls back to its own")
    a("// flatten time is the defect this file exists to remove.")
    a("")
    a("namespace NinjaTrader.NinjaScript.Strategies.Vinay")
    a("{")
    a("    /// <summary>")
    a("    /// The frozen defaults every strategy inherits. Only the trade setup varies.")
    a("    /// </summary>")
    a("    public static class TradingDefaults")
    a("    {")
    a('        public const string SourceHash = "{}";'.format(source_hash(raw)))
    a('        public const string FrozenOn   = "{}";'.format(d["frozenOn"]))
    a("")
    a("        // ---- Instrument (ADR-009: micros are the traded class) ----------")
    a('        public const string DefaultInstrument = "{}";'.format(inst["default"]))
    for sym in sorted(inst["table"]):
        spec = inst["table"][sym]
        a("        public const double PointValue{0} = {1};   // tick {2} = ${3}"
          .format(sym, spec["pointValue"], spec["tickSize"], spec["tickValue"]))
    a("")
    a("        /// <summary>Point value for a data ticker OR a contract symbol.")
    a("        /// NQ1 names a PRICE SERIES; MNQ names the CONTRACT you trade.")
    a("        /// Throws rather than guessing -- a silent default here valued one")
    a("        /// run's point at $20 in P&amp;L and $2 in the prop simulation.</summary>")
    a("        public static double PointValueFor(string ticker)")
    a("        {")
    a("            switch ((ticker ?? \"\").Trim().ToUpperInvariant())")
    a("            {")
    groups: dict[str, list[str]] = {}
    for sym in inst["table"]:
        groups.setdefault(sym, []).append(sym)
    for alias, target in inst["aliases"].items():
        groups.setdefault(target, []).append(alias)
    for target in sorted(groups):
        for key in sorted(set(groups[target])):
            a('                case "{}":'.format(key))
        a("                    return PointValue{};".format(target))
    a("                default:")
    a("                    throw new System.ArgumentException(")
    a('                        "unknown instrument \'" + ticker + "\'. Add it to '
      'trading_defaults.json; do not pass a point value at the call site.");')
    a("            }")
    a("        }")
    a("")
    a("        // ---- Risk ------------------------------------------------------")
    a("        // NoLimit is -1, not 0 and not int.MaxValue: 0 would read as 'no")
    a("        // trades allowed' if a caller compared with >=, and MaxValue hides")
    a("        // in arithmetic. A cap is an OUTPUT of reporting/trade_ordinal.py,")
    a("        // not a frozen input, and an entry may happen at ANY time -- only")
    a("        // the 16:00 exit is fixed. See trading_defaults.json risk._doc.")
    a("        public const int    NoLimit = -1;")
    a("        public const int    MaxContractsPerTrade   = {};".format(risk["maxContractsPerTrade"]))
    a("        public const int    MaxConcurrentPositions = {};".format(risk["maxConcurrentPositions"]))
    a("        public const int    MaxTradesPerDay        = {};   // {}".format(
        _int_or_nolimit(risk["maxTradesPerDay"]),
        "analysis-derived; no frozen cap" if risk["maxTradesPerDay"] is None
        else "frozen"))
    a("        public const int    MaxTradesPerSession    = {};   // {}".format(
        _int_or_nolimit(risk.get("maxTradesPerSession")),
        "analysis-derived; no frozen cap"
        if risk.get("maxTradesPerSession") is None else "frozen"))
    a("        public const int    LastEntry              = {};   // {}"
      .format(_time_or_nolimit(risk["lastEntryEt"]),
              "an entry may happen at ANY time"
              if risk["lastEntryEt"] is None else risk["lastEntryEt"] + " ET"))
    a("        public const int    FlattenBy              = {};   // {} ET, overridable"
      .format(_hhmm_to_int(risk["flattenByEt"]), risk["flattenByEt"]))
    a("        public const int    RthHardExit            = {};   // {} ET, ADR-020"
      .format(_hhmm_to_int(risk["rthHardExitEt"]), risk["rthHardExitEt"]))
    a("        public const double RiskPerTradeFraction   = {};".format(risk["riskPerTradeFraction"]))
    a("")
    a("        // ---- Execution -------------------------------------------------")
    a("        public const int    SlippageTicks   = {};".format(execu["slippageTicks"]))
    a("        public const double CommissionRT    = {};".format(execu["commissionPerContractRoundTrip"]))
    a("        public const int    DefaultContracts = {};".format(execu["defaultContracts"]))
    # Section 11 item 19: the CoverTheQueen bracket distances, bps of entry.
    # The queen leg honours a DECLARED target when one is on the right side;
    # these are the fallback the runner always carries.
    a("        public const double QueenBps       = {};".format(execu["queenBps"]))
    a("        public const double RunnerBps       = {};".format(execu["runnerBps"]))
    a("")
    a("        // ---- NT8 Strategy Analyzer (asserted, never written) -----------")
    a('        public const string GlobalMergePolicy = "{}";'.format(nt8["globalMergePolicy"]))
    a("        public const bool   IncludeCommission = {};".format(
        str(nt8["includeCommission"]).lower()))
    a("")
    a("        // ---- Sessions, ET. A PARTITION: contiguous, non-overlapping, and")
    a("        //      covering the day exactly once (asserted on the Python side).")
    for w in sessions["windows"]:
        a("        public const int {0}Start = {1};   // {2}".format(
            w["name"].replace("_", ""), _hhmm_to_int(w["start"]), w["start"]))
    a("")
    a("        /// <summary>Frozen session name for a HHMM time-of-day.</summary>")
    a("        public static string SessionFor(int hhmm)")
    a("        {")
    for w in sessions["windows"]:
        s_, e_ = _hhmm_to_int(w["start"]), _hhmm_to_int(w["end"])
        name = w["name"]
        if e_ <= s_:   # wraps midnight
            a('            if (hhmm >= {0} || hhmm < {1}) return "{2}";'.format(s_, e_, name))
        else:
            a('            if (hhmm >= {0} && hhmm < {1}) return "{2}";'.format(s_, e_, name))
    a('            throw new System.ArgumentException("no session for " + hhmm);')
    a("        }")
    a("")
    _emit_governance_gates(a, d.get("governance") or {})
    a("    }")
    a("}")
    return "\n".join(L) + "\n"


def _emit_governance_gates(a, gov: dict) -> None:
    """The names `GovernedStrategy` records its OWN refusals under.

    Emitted rather than written as C# literals because the Python reader groups
    the roster on these exact strings: a rename on one side alone splits one
    gate into two rows that never compare, and nothing would fail.
    """
    gates = gov.get("gates") or {}
    if not gates:
        return
    a("        // ---- governance gate names (section 3.4) --------------------------")
    a("        // GovernedStrategy records its own refusals under these, so a bot")
    a("        // blocked by a FRAMEWORK rule lands in the roster instead of")
    a("        // vanishing -- the C# half of the funnel gap in section 11 item 13.")
    for key, name in gates.items():
        a('        public const string Gate{0} = "{1}";'.format(
            key[0].upper() + key[1:], name))
    a("")
    a("        /// <summary>Every governance gate name, so a test can assert the")
    a("        /// set rather than each member -- a new one added to the JSON and")
    a("        /// never recorded would otherwise pass every existing check.</summary>")
    a("        public static readonly string[] GovernanceGates = new string[] {")
    a("            " + ", ".join(
        "Gate{0}".format(k[0].upper() + k[1:]) for k in gates) + " };")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file matches the JSON; write nothing")
    args = ap.parse_args()

    raw = SRC.read_text(encoding="utf-8")
    want = render(raw)

    if args.check:
        if not OUT.exists():
            print("MISSING: {}".format(OUT.relative_to(REPO)), file=sys.stderr)
            return 1
        got = OUT.read_text(encoding="utf-8")
        if got.replace("\r\n", "\n") != want:
            print("STALE: {} does not match {}.\n"
                  "Re-run: python scripts/utils/generate_trading_defaults.py"
                  .format(OUT.relative_to(REPO), SRC.relative_to(REPO)),
                  file=sys.stderr)
            return 1
        print("ok: TradingDefaults.cs matches trading_defaults.json "
              "(hash {})".format(source_hash(raw)))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(want, encoding="utf-8")
    print("wrote {} ({} lines, source hash {})".format(
        OUT.relative_to(REPO), len(want.splitlines()), source_hash(raw)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
