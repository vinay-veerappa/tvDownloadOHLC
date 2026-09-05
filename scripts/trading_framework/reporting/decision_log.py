"""Why did this trade get taken, and why were the others skipped?

A trade list says WHAT happened. It cannot say why, and no change to the NT8
bridge can make it -- the criteria live in the strategy, so only the strategy can
report them. This module freezes the format in which both sides report them, so
one reader serves the Python hunter and the C# bot and the two are DIFFABLE
rather than merely both available.

THE GATE ROSTER IS THE FIRST PARITY CHECK, and it is cheaper and far more
diagnostic than trade-set recall. Measured 2026-09-05 on the `mean_reversion` /
`BBMRReversionBot` pair, which section 6 treats as one strategy:

    Python  `hunt()`      : 2 conditions (close vs a Bollinger band), then
                            `groupby('date').head(1)` -- ONE signal per day
    C#      BBMRReversionBot : 20 [NinjaScriptProperty] parameters and gates for
                            RSI, ADX, squeeze, IB compression, lunch, MACD,
                            Kaufman ER, a 2-bar hook and short-only

They are not one strategy with a divergence. They are two different strategies,
and NO recall number computed between them means anything. A roster diff says so
in one command; a trade-set comparison says "recall 11%" and invites a week of
looking for a fill-model bug. Trade caps are the same story three ways: the
hunter structurally takes 1/day, `sessions.yaml` says 3, the bot allows 99.

FIVE DESIGN RULES, each of which is a failure mode seen in the existing
per-bar dump (`BBMRReversionBot` writes 22 indicator columns for EVERY bar to
`%TEMP%/bbmr_diag_<guid>.csv` and prints the path only to the NT8 output window):

 1. LOG DECISIONS, NOT BARS. A per-bar state dump makes you re-implement the
    rule in your head to find out why a bar did not trade. Rows are bounded by
    triggers x gates, not by bars.

 2. RECORD EVERY GATE, NOT THE FIRST FAILURE. Short-circuit order is an
    implementation accident; reporting "the first gate that failed" reports the
    accident as the cause. `&&` in C# and `and` in Python both stop early, so
    the emitter must evaluate all gates deliberately.

 3. RECORD THE VALUE, NOT JUST PASS/FAIL. "ADX passed" is not analysable.
    "ADX 18.2 vs threshold 15" tells you the trade was marginal, which is what
    separates a losing trade from a badly gated one.

 4. A REJECTION NEEDS A DENOMINATOR. A bar with no trigger at all must be
    distinguishable from a bar with a trigger that a gate blocked, or
    "gate X blocked 40 setups" has no scale. Hence the `SKIP` decision.

 5. LONG FORMAT, ONE ROW PER (DECISION, GATE). A wide format needs a column per
    gate, so two strategies cannot share a schema and adding a gate is a
    migration. Long format costs rows and buys a schema that never changes.

WHAT THIS FILE DOES NOT CARRY: P&L, MAE, MFE, exit prices. Those are in the
trade list already and duplicating them would create a second version to
disagree with. The log carries `signal_name` to JOIN to the fill --
`Execution.Name` on the NT8 side, which is why a bot must emit a UNIQUE signal
name per entry. `win_loss_attribution.py` does the join and reports what did not
match rather than dropping it.

TRANSPORT: the C# emitter writes `mcp_decisions_*.csv` into `Globals.UserDataDir`,
which the bridge's existing `nt_list_exports` / `nt_get_export` endpoints already
serve behind their filename gate. No bridge change is needed to collect it.
"""

from __future__ import annotations

import csv
import os
import pathlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from scripts.trading_framework.reporting.session_breakdown import (
    label_trades_by_session,
)

# Bumped only when a column is added or removed. The reader refuses a file whose
# version it does not know rather than silently reading a shifted column.
SCHEMA_VERSION = 1

COLUMNS: tuple[str, ...] = (
    "schema_version",
    "run_id",         # joins to the workflow run record
    "side",           # "python" | "nt8" -- so both files merge into one frame
    "strategy",       # registry key (python) or C# class name (nt8)
    "seq",            # monotonic decision index within the run
    "bar_time",       # ISO8601 with offset, America/New_York
    "session",        # frozen session name, computed by the emitter
    "direction",      # long | short | ""
    "decision",       # see DECISIONS
    "signal_name",    # join key to the fill; MUST be unique per entry
    "gate",           # stable gate name; "" for a decision with no gates
    "kind",           # see KINDS -- a blocking gate is not a covariate
    "gate_pass",      # 1 | 0
    "gate_value",     # the measured number, as text; "" if not numeric
    "gate_threshold",  # what it was compared against; "" if not applicable
    "detail",         # free text, last resort
)

#: `SKIP` is the denominator (rule 4): a bar that produced no trigger at all.
#: It is emitted as a COUNT rather than a row per bar -- see `GateRecorder`.
DECISIONS: tuple[str, ...] = ("ENTRY", "REJECTED", "EXIT", "SKIP")

SIDES: tuple[str, ...] = ("python", "nt8")

#: A `gate` can BLOCK a setup and belongs in the roster. A `measure` never
#: blocks -- it is a covariate recorded so the win/loss analysis has something
#: to correlate with -- and must be kept out of the roster, because a "gate"
#: whose fail rate is structurally 0% is a green that can never be red, and
#: mixing the two makes every roster contain some.
KINDS: tuple[str, ...] = ("gate", "measure", "note")


@dataclass(frozen=True)
class Gate:
    """One named criterion, its outcome, and the numbers behind the outcome."""

    name: str
    passed: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""
    kind: str = "gate"


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "1" if v else "0"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return "" if not np.isfinite(f) else "{:.6g}".format(f)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

class DecisionLogWriter:
    """Row-wise emitter. ASCII CSV, one row per (decision, gate).

    Flushes after every decision on purpose: a backtest that ends without
    reaching a clean shutdown -- an SA run cancelled, a strategy that throws --
    otherwise loses the tail, and the tail is where the interesting decisions
    are. Decisions are rare enough that per-decision flushing costs nothing;
    per-BAR flushing would not be, which is a further reason for rule 1.
    """

    def __init__(self, path, *, run_id: str, strategy: str, side: str = "python"):
        if side not in SIDES:
            raise ValueError("side must be one of {}: {!r}".format(SIDES, side))
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.strategy = strategy
        self.side = side
        self._seq = 0
        self._fh = None
        self._w = None

    def __enter__(self) -> "DecisionLogWriter":
        self._fh = open(self.path, "w", newline="", encoding="ascii", errors="replace")
        self._w = csv.writer(self._fh)
        self._w.writerow(COLUMNS)
        return self

    def __exit__(self, *exc) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def log(self, *, bar_time, decision: str, gates: Sequence[Gate] = (),
            direction: str = "", signal_name: str = "", session: str = "",
            detail: str = "") -> int:
        """Emit one decision. Returns its `seq`.

        Raises on the two states that mean the log disagrees with the behaviour
        it claims to describe -- an `ENTRY` with a failed gate, or a `REJECTED`
        with none. A log that can record either is worse than no log, because it
        looks like evidence.
        """
        if decision not in DECISIONS:
            raise ValueError("unknown decision {!r}; expected one of {}"
                             .format(decision, DECISIONS))
        bad_kind = sorted({g.kind for g in gates} - set(KINDS))
        if bad_kind:
            raise ValueError("unknown kind(s) {}; expected {}".format(bad_kind, KINDS))
        # Only a BLOCKING gate can contradict a verdict. A `measure` records a
        # covariate and its `passed` flag is meaningless, so counting it here
        # would make every instrumented entry look like a contradiction.
        failed = [g.name for g in gates if g.kind == "gate" and not g.passed]
        if decision == "ENTRY" and failed:
            raise ValueError(
                "ENTRY at {} records FAILED gates {} -- the log contradicts the "
                "trade it claims to explain".format(bar_time, failed))
        if decision == "REJECTED" and gates and not failed:
            raise ValueError(
                "REJECTED at {} records no failed gate -- then what rejected it?"
                .format(bar_time))
        if self._w is None:
            raise RuntimeError("DecisionLogWriter must be used as a context manager")

        self._seq += 1
        ts = pd.Timestamp(bar_time)
        stamp = ts.isoformat()
        rows = list(gates) or [Gate(name="", passed=(decision != "REJECTED"),
                                    detail=detail)]
        for g in rows:
            self._w.writerow([
                SCHEMA_VERSION, self.run_id, self.side, self.strategy, self._seq,
                stamp, session, direction, decision, signal_name, g.name,
                g.kind, 1 if g.passed else 0, _fmt(g.value), _fmt(g.threshold),
                g.detail or (detail if not g.name else ""),
            ])
        self._fh.flush()
        return self._seq


class GateRecorder:
    """The vectorised emitter -- the shape a `hunt()` actually has.

    A zero-loop hunter (section 2.2) has no per-decision loop to hook; it has
    boolean MASKS. Handing it a row-wise API guarantees it goes uninstrumented,
    so this takes the masks directly and does one vectorised pass at the end.

        rec = GateRecorder(data.index, run_id=..., strategy="mean_reversion")
        rec.trigger(long_mask, "long")
        rec.gate("close_below_lower_band", close <= lower, value=close,
                 threshold=lower)
        rec.gate("first_signal_of_day", is_first)
        rec.to_frame()

    A bar is a `SKIP` unless some `trigger()` covers it, an `ENTRY` if every
    gate passed, and `REJECTED` otherwise -- which is rules 2 and 4 falling out
    of the construction instead of relying on the caller to get them right.
    """

    def __init__(self, index: pd.DatetimeIndex, *, run_id: str, strategy: str,
                 side: str = "python"):
        self.index = pd.DatetimeIndex(index)
        self.run_id = run_id
        self.strategy = strategy
        self.side = side
        self._direction = pd.Series("", index=self.index, dtype=object)
        self._triggered = pd.Series(False, index=self.index)
        # (name, mask, value, threshold, kind)
        self._gates: list[tuple[str, pd.Series, Optional[pd.Series],
                                Optional[pd.Series], str]] = []

    def _align(self, v) -> Optional[pd.Series]:
        if v is None:
            return None
        if isinstance(v, pd.Series):
            return v.reindex(self.index)
        return pd.Series(np.broadcast_to(np.asarray(v), (len(self.index),)),
                         index=self.index)

    def trigger(self, mask, direction: str) -> "GateRecorder":
        """Mark the bars where a setup EXISTS at all. Without this every bar is
        a candidate and the rejection counts are meaningless (rule 4)."""
        m = self._align(mask).fillna(False).astype(bool)
        self._triggered = self._triggered | m
        self._direction = self._direction.mask(m, direction)
        return self

    def gate(self, name: str, mask, *, value=None, threshold=None) -> "GateRecorder":
        """A criterion that can BLOCK the setup. Counts toward the verdict."""
        return self._add(name, mask, value, threshold, "gate")

    def measure(self, name: str, values, *, threshold=None) -> "GateRecorder":
        """A covariate recorded for attribution, which never blocks anything.

        The distinction is load-bearing. Recording "close is past the band" as a
        GATE on bars that triggered because the close is past the band produces
        a gate with a structural 0% failure rate -- a green that can never be
        red, and it would sit at the top of every roster. Recorded as a measure
        it stays out of the roster and still reaches question 3 of the win/loss
        report, which is where a magnitude actually earns its keep.
        """
        return self._add(name, pd.Series(True, index=self.index), values,
                         threshold, "measure")

    def _add(self, name: str, mask, value, threshold, kind: str) -> "GateRecorder":
        if not name:
            raise ValueError("a gate must be named -- an unnamed gate cannot be "
                             "compared across the two sides")
        if any(g[0] == name for g in self._gates):
            raise ValueError("gate {!r} recorded twice; names must be unique so a "
                             "roster diff is meaningful".format(name))
        self._gates.append((name, self._align(mask).fillna(False).astype(bool),
                            self._align(value), self._align(threshold), kind))
        return self

    def to_frame(self, *, signal_prefix: str = "") -> pd.DataFrame:
        """Long-format rows for the triggered bars only, plus one SKIP summary.

        The SKIP row carries the untriggered bar COUNT in `gate_value` rather
        than one row per bar: the denominator is what rule 4 needs, and a row
        per quiet bar would be the per-bar dump this module exists to replace.
        """
        trig = self._triggered.to_numpy()
        n_skip = int((~trig).sum())
        if not self._gates and not trig.any():
            return pd.DataFrame(columns=COLUMNS)

        # A `measure` never blocks, so it must not enter the verdict.
        passed_all = np.ones(len(self.index), dtype=bool)
        for _n, m, _v, _t, kind in self._gates:
            if kind == "gate":
                passed_all &= m.to_numpy()

        sessions = label_trades_by_session(
            pd.DataFrame({"bar_time": self.index}), "bar_time")
        sessions = sessions.to_numpy() if len(sessions) else np.full(len(self.index), "")

        idx = np.flatnonzero(trig)
        seq = pd.Series(np.arange(1, len(idx) + 1), index=idx)
        blocks = []
        gates = self._gates or [("", pd.Series(True, index=self.index), None,
                                 None, "gate")]
        for name, m, val, thr, kind in gates:
            blocks.append(pd.DataFrame({
                "schema_version": SCHEMA_VERSION,
                "run_id": self.run_id,
                "side": self.side,
                "strategy": self.strategy,
                "seq": seq.to_numpy(),
                "bar_time": [t.isoformat() for t in self.index[idx]],
                "session": sessions[idx],
                "direction": self._direction.to_numpy()[idx],
                "decision": np.where(passed_all[idx], "ENTRY", "REJECTED"),
                "signal_name": ["{}{}".format(signal_prefix, s) for s in seq.to_numpy()]
                                if signal_prefix else "",
                "gate": name,
                "kind": kind,
                "gate_pass": m.to_numpy()[idx].astype(int),
                "gate_value": ([_fmt(x) for x in val.to_numpy()[idx]]
                               if val is not None else ""),
                "gate_threshold": ([_fmt(x) for x in thr.to_numpy()[idx]]
                                   if thr is not None else ""),
                "detail": "",
            }))
        out = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame(columns=COLUMNS)
        skip = pd.DataFrame([{
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "side": self.side, "strategy": self.strategy, "seq": 0,
            "bar_time": self.index[0].isoformat() if len(self.index) else "",
            "session": "", "direction": "", "decision": "SKIP", "signal_name": "",
            "gate": "", "kind": "note", "gate_pass": 1, "gate_value": str(n_skip),
            "gate_threshold": str(len(self.index)),
            "detail": "bars with no trigger of any kind (rule 4 denominator)",
        }])
        return pd.concat([out, skip], ignore_index=True)[list(COLUMNS)]


def write_frame(df: pd.DataFrame, path) -> pathlib.Path:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.reindex(columns=list(COLUMNS)).to_csv(p, index=False, encoding="ascii",
                                             errors="replace")
    return p


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

class DecisionLogError(RuntimeError):
    pass


def read_decision_log(path) -> pd.DataFrame:
    """Read and VALIDATE. A shifted column is worse than a missing file."""
    p = pathlib.Path(path)
    if not p.exists():
        raise DecisionLogError("no decision log at {}".format(p))
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise DecisionLogError(
            "{} is not a decision log: missing {}".format(p.name, missing))
    if df.empty:
        return df
    vers = sorted(set(df["schema_version"]))
    if vers != [str(SCHEMA_VERSION)]:
        raise DecisionLogError(
            "{} declares schema_version {} and this reader knows {}. Refusing "
            "rather than reading a shifted column.".format(p.name, vers, SCHEMA_VERSION))
    bad = sorted(set(df["decision"]) - set(DECISIONS))
    if bad:
        raise DecisionLogError("unknown decision value(s) {} in {}".format(bad, p.name))
    bad_kind = sorted(set(df["kind"]) - set(KINDS) - {""})
    if bad_kind:
        raise DecisionLogError("unknown kind(s) {} in {}".format(bad_kind, p.name))
    df["gate_pass"] = pd.to_numeric(df["gate_pass"], errors="coerce")
    df["seq"] = pd.to_numeric(df["seq"], errors="coerce")
    return df


def contradictions(df: pd.DataFrame) -> pd.DataFrame:
    """Decisions whose gates disagree with the decision.

    An `ENTRY` carrying a failed gate, or a `REJECTED` carrying none. Both mean
    the log does not describe the behaviour it claims to -- the same class as a
    config that reads as protection which is not enforced. Reported rather than
    raised, because a partial log is still worth reading once you know which
    rows to distrust.
    """
    if df.empty:
        return pd.DataFrame(columns=["seq", "decision", "problem"])
    # `measure` rows carry a meaningless pass flag; counting them would make
    # every instrumented entry look self-contradictory.
    g = df[(df["gate"] != "") & (df["kind"] == "gate")]
    if g.empty:
        return pd.DataFrame(columns=["seq", "decision", "problem"])
    agg = g.groupby(["seq", "decision"], as_index=False).agg(
        n_gates=("gate", "size"), n_failed=("gate_pass", lambda s: int((s == 0).sum())))
    rows = []
    for _, r in agg.iterrows():
        if r["decision"] == "ENTRY" and r["n_failed"]:
            rows.append({"seq": r["seq"], "decision": "ENTRY",
                         "problem": "{} gate(s) failed but the trade was taken"
                                    .format(int(r["n_failed"]))})
        elif r["decision"] == "REJECTED" and not r["n_failed"]:
            rows.append({"seq": r["seq"], "decision": "REJECTED",
                         "problem": "no gate failed but the setup was rejected"})
    return pd.DataFrame(rows, columns=["seq", "decision", "problem"])


def gate_roster(df: pd.DataFrame) -> pd.DataFrame:
    """Every gate the run evaluated, and how often it was the blocker.

    `blocked_alone` is the column that matters: a gate that fails only alongside
    others is not what is costing you trades, and a gate that is the SOLE
    failure on many setups IS the strategy, whatever the rest of the roster says.
    """
    cols = ["gate", "evaluated", "failed", "blocked_alone", "fail_%", "never_fails"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    g = df[(df["gate"] != "") & (df["kind"] == "gate")
           & (df["decision"].isin(("ENTRY", "REJECTED")))].copy()
    if g.empty:
        return pd.DataFrame(columns=cols)
    failed_per_seq = g.groupby("seq")["gate_pass"].apply(lambda s: int((s == 0).sum()))
    lone = set(failed_per_seq[failed_per_seq == 1].index)
    rows = []
    for name, sub in g.groupby("gate"):
        fails = sub[sub["gate_pass"] == 0]
        rows.append({
            "gate": name,
            "evaluated": len(sub),
            "failed": len(fails),
            "blocked_alone": int(fails["seq"].isin(lone).sum()),
            "fail_%": 100.0 * len(fails) / len(sub) if len(sub) else np.nan,
            # A blocking gate that never blocked anything over a real sample is
            # either dead code or a `measure` mislabelled as a gate. Either way
            # it is a green that can never be red, and it inflates the roster
            # that the parity diff is computed over.
            "never_fails": len(fails) == 0 and len(sub) >= 20,
        })
    return (pd.DataFrame(rows)
            .sort_values(["blocked_alone", "failed"], ascending=False)
            .reset_index(drop=True))


def compare_rosters(a: pd.DataFrame, b: pd.DataFrame, *,
                    name_a: str = "python", name_b: str = "nt8") -> dict:
    """The cheap parity check that runs BEFORE any trade-set comparison.

    Two sides evaluating different criteria are two strategies, and a recall
    figure between them is a number about nothing. This returns the set
    difference in both directions, because each direction means something
    different: a gate only on the NT8 side means the bot refuses trades the
    hunter predicts (recall falls, and it looks like a Python defect); a gate
    only on the Python side means the bot takes trades nothing predicted.
    """
    ga = set(gate_roster(a)["gate"]) if not a.empty else set()
    gb = set(gate_roster(b)["gate"]) if not b.empty else set()
    only_a, only_b = sorted(ga - gb), sorted(gb - ga)
    return {
        "shared": sorted(ga & gb),
        "only_{}".format(name_a): only_a,
        "only_{}".format(name_b): only_b,
        "comparable": not only_a and not only_b and bool(ga),
        "reason": (
            "both sides evaluate the same {} gate(s)".format(len(ga & gb))
            if not only_a and not only_b and ga else
            "no gates recorded on either side" if not ga and not gb else
            "{} evaluates {} gate(s) the other does not; {} evaluates {}. These "
            "are different strategies and a trade-set recall between them is "
            "not interpretable.".format(name_a, len(only_a), name_b, len(only_b))
        ),
    }


def render_decision_log(df: pd.DataFrame, *, title: str = "Why these trades") -> str:
    """ASCII only -- a cp1252 console cannot encode an em-dash or a <= sign."""
    if df is None or df.empty:
        return ("### {}\n\n_Not available: no decision log was emitted. The "
                "strategy is not instrumented (see STRATEGY_WORKFLOW.md section "
                "5.1)._\n".format(title))
    L = ["### {}".format(title), ""]

    skips = df[df["decision"] == "SKIP"]
    n_dec = int(df.loc[df["decision"].isin(("ENTRY", "REJECTED")), "seq"].nunique())
    n_entry = int(df.loc[df["decision"] == "ENTRY", "seq"].nunique())
    if not skips.empty:
        quiet = pd.to_numeric(skips["gate_value"], errors="coerce").sum()
        total = pd.to_numeric(skips["gate_threshold"], errors="coerce").sum()
        L.append("{:,.0f} bars, {:,.0f} with no trigger of any kind. "
                 "{} setup(s) reached the gates and {} became entries."
                 .format(total, quiet, n_dec, n_entry))
    else:
        L.append("{} setup(s) reached the gates and {} became entries."
                 .format(n_dec, n_entry))

    bad = contradictions(df)
    if not bad.empty:
        L += ["", "**{} decision(s) contradict their own gates** -- these rows "
                  "are not evidence:".format(len(bad)), ""]
        for _, r in bad.head(10).iterrows():
            L.append("- seq {}: {}".format(int(r["seq"]), r["problem"]))

    roster = gate_roster(df)
    if not roster.empty:
        L += ["", "#### Gate roster", "",
              "`blocked alone` is the diagnostic column: a gate that is the SOLE "
              "failure on many setups is the strategy.", "",
              "| Gate | Evaluated | Failed | Fail% | Blocked alone |",
              "|---|---:|---:|---:|---:|"]
        for _, r in roster.iterrows():
            L.append("| `{}`{} | {} | {} | {:.1f} | {} |".format(
                r["gate"], " (never fails)" if r["never_fails"] else "",
                int(r["evaluated"]), int(r["failed"]),
                r["fail_%"], int(r["blocked_alone"])))
        dead = roster[roster["never_fails"]]["gate"].tolist()
        if dead:
            L += ["", "{} gate(s) never blocked anything: {}. Either dead code, "
                      "or a covariate that should be recorded with `measure()` "
                      "instead -- as a gate it is a green that can never be red "
                      "and it inflates the roster the parity diff runs over."
                      .format(len(dead), ", ".join("`{}`".format(d) for d in dead))]
    return "\n".join(L) + "\n"
