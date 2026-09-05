r"""Differential test: does StratCore.cs still compute what the_strat computes?

`scripts/ninjatrader/shared/StratCore.cs` opens with its own contract:

    PURE Strat math, zero NT8 dependencies (no Series, no Draw).
    This is the C# mirror of scripts/libs_py/the_strat/:
      taxonomy.py (ClassifyBar/WickType) + targets.py (MeasuredTargets) +
      session.py (EntryAllowed) + signals.py FTFC scoring.
    Rule changes go here AND in Python together - never in only one side.

That last line is the whole design, and it is a COMMENT. A comment cannot fail,
cannot be run, and does not notice when someone edits one side. This runs the
same inputs through both languages and requires identical answers.

WHY THIS AND NOT TRADE-SET PARITY. Both matter, and they answer different
questions. A trade-set comparison tells you two implementations diverged --
after a deploy, after a backtest, in aggregate, with every downstream difference
folded in. This tells you WHICH RULE diverged and on WHICH INPUT, needs no NT8,
no market data and no deploy, and runs in about a second. Drift is cheapest to
catch where it originates.

CASE DESIGN. Random inputs are close to useless here: the two implementations
agree almost everywhere, and the disagreements live on boundaries. So the grid is
deliberately weighted to edges -- equal highs and lows, a range of exactly one
tick, a zero range, a wick ratio exactly at the threshold, a close exactly at the
midpoint, a stop exactly at the risk cap, times exactly on a window edge -- with
a random block behind it to catch what the edges do not anticipate.

Run:
  .venv\Scripts\python.exe -m scripts.parity.strat_core_parity
  .venv\Scripts\python.exe -m scripts.parity.strat_core_parity --keep   (keep CSVs)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import time as dtime
from typing import Any, Dict, List

import numpy as np

from scripts.libs_py.the_strat.session import entry_allowed
from scripts.libs_py.the_strat.targets import measured_targets
from scripts.libs_py.the_strat.taxonomy import classify_bar

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJ = os.path.join(REPO, "scripts", "parity", "csharp", "stratcore")
EXE = os.path.join(PROJ, "bin", "Debug", "net8.0", "StratCoreHarness.exe")

TICK = 0.25
# Floats crossing a language boundary through decimal text are compared with a
# tolerance, not ==. It is deliberately TIGHT: these are the same arithmetic in
# two languages, so anything above round-trip noise is a real difference.
FLOAT_TOL = 1e-9


# ---------------------------------------------------------------------------
# Case generation
# ---------------------------------------------------------------------------
def classify_cases() -> List[Dict[str, Any]]:
    """Bar classification. The boundaries are the strict inequalities."""
    cases = []
    # (high, low, prev_high, prev_low)
    edges = [
        (10.0, 5.0, 10.0, 5.0),      # exactly equal -> inside (neither > nor <)
        (10.25, 5.0, 10.0, 5.0),     # one tick higher
        (10.0, 4.75, 10.0, 5.0),     # one tick lower
        (10.25, 4.75, 10.0, 5.0),    # both -> outside
        (10.0, 5.0, 10.0, 4.0),      # equal high, higher low -> inside
        (11.0, 6.0, 10.0, 5.0),      # clean 2U
        (9.0, 4.0, 10.0, 5.0),       # clean 2D
        (1e12, -1e12, 0.0, 0.0),     # extreme magnitudes
        (0.0, 0.0, 0.0, 0.0),        # degenerate
    ]
    for i, (h, l, ph, pl) in enumerate(edges):
        cases.append({"id": f"cls_edge_{i}", "fn": "classify",
                      "p": [h, l, ph, pl, 0, 0, 0, 0, 0]})
    rng = np.random.default_rng(17)
    for i in range(200):
        ph, pl = 100.0, 95.0
        h = ph + rng.choice([-1, 0, 1]) * rng.choice([0.0, TICK, 1.0])
        l = pl + rng.choice([-1, 0, 1]) * rng.choice([0.0, TICK, 1.0])
        cases.append({"id": f"cls_rnd_{i}", "fn": "classify",
                      "p": [float(h), float(l), ph, pl, 0, 0, 0, 0, 0]})
    return cases


def wick_cases() -> List[Dict[str, Any]]:
    """Hammer / shooter. This is where the two guards differ, so it is dense."""
    cases = []
    thr = 0.65
    # (open, close, high, low)
    edges = [
        (10.0, 10.0, 10.0, 10.0),        # ZERO range
        (10.0, 10.0, 10.25, 10.0),       # range == ONE TICK
        (10.0, 10.0, 10.24, 10.0),       # range just UNDER one tick
        (10.0, 10.0, 10.26, 10.0),       # range just OVER one tick
        (10.0, 10.0, 10.5, 10.0),        # range == two ticks
        (10.0, 11.0, 11.0, 8.0),         # long lower wick -> hammer
        (10.0, 9.0, 12.0, 9.0),          # long upper wick -> shooter
        # wick ratio EXACTLY at threshold: range 10, lower wick 6.5
        (16.5, 17.0, 17.0, 7.0),
        # close exactly at the midpoint
        (12.0, 12.0, 17.0, 7.0),
    ]
    for i, (o, c, h, l) in enumerate(edges):
        cases.append({"id": f"wick_edge_{i}", "fn": "wick",
                      "p": [o, c, h, l, thr, TICK, 0, 0, 0]})
    rng = np.random.default_rng(23)
    for i in range(300):
        l = 100.0
        rng_size = float(rng.choice([0.0, 0.1, TICK, 0.5, 1.0, 5.0, 20.0]))
        h = l + rng_size
        o = float(rng.uniform(l, h)) if rng_size > 0 else l
        c = float(rng.uniform(l, h)) if rng_size > 0 else l
        cases.append({"id": f"wick_rnd_{i}", "fn": "wick",
                      "p": [o, c, h, l, thr, TICK, 0, 0, 0]})
    return cases


def target_cases() -> List[Dict[str, Any]]:
    """Measured targets. Boundaries: the risk cap, the tick floor, a zero leg."""
    cases = []
    edges = [
        # dir, entry, stop, insideHigh, insideLow, priorLeg, minTarget, maxRisk, tick
        (1, 100.0, 95.0, 102.0, 98.0, 20.0, 2.0, 15.0, TICK),
        (-1, 100.0, 105.0, 102.0, 98.0, 20.0, 2.0, 15.0, TICK),
        (1, 100.0, 100.0, 100.0, 100.0, 0.0, 0.0, 15.0, TICK),   # everything degenerate
        (1, 100.0, 85.0, 102.0, 98.0, 0.0, 2.0, 15.0, TICK),     # risk EXACTLY at the cap
        (1, 100.0, 84.99, 102.0, 98.0, 0.0, 2.0, 15.0, TICK),    # just OVER the cap
        (1, 100.0, 99.9, 102.0, 98.0, 0.0, 2.0, 15.0, TICK),     # risk under one tick
        (1, 100.0, 95.0, 98.0, 102.0, 0.0, 2.0, 15.0, TICK),     # INVERTED inside bar
        (1, 100.0, 95.0, 102.0, 98.0, -50.0, 2.0, 15.0, TICK),   # NEGATIVE prior leg
        (1, 100.0, 95.0, 102.0, 98.0, 0.0, 0.0, 0.0, TICK),      # zero max risk
        (0, 100.0, 95.0, 102.0, 98.0, 20.0, 2.0, 15.0, TICK),    # direction 0 (neither)
    ]
    for i, p in enumerate(edges):
        cases.append({"id": f"tgt_edge_{i}", "fn": "targets", "p": list(map(float, p))})
    rng = np.random.default_rng(31)
    for i in range(300):
        d = float(rng.choice([1, -1]))
        entry = 100.0
        stop = entry - d * float(rng.choice([0.1, TICK, 1.0, 5.0, 15.0, 15.0001, 40.0]))
        ih = entry + float(rng.uniform(0, 5))
        il = entry - float(rng.uniform(0, 5))
        cases.append({"id": f"tgt_rnd_{i}", "fn": "targets",
                      "p": [d, entry, stop, ih, il,
                            float(rng.choice([0.0, 1.0, 20.0, 100.0])),
                            float(rng.choice([0.0, 2.0, 10.0])),
                            float(rng.choice([5.0, 15.0, 1e9])), TICK]})
    return cases


def entry_cases() -> List[Dict[str, Any]]:
    """Session gate. Boundaries are the window edges themselves."""
    cases = []
    kz = "930;1030;1330;1500"
    for hhmm in (0, 929, 930, 931, 1029, 1030, 1031, 1200, 1329, 1330,
                 1500, 1501, 1529, 1530, 1531, 1554, 1555, 1556, 2359):
        for use_kz in (0.0, 1.0):
            cases.append({"id": f"ent_{hhmm}_{int(use_kz)}", "fn": "entry",
                          "p": [float(hhmm), 930.0, 1530.0, 1555.0, use_kz,
                                0, 0, 0, 0],
                          "extra": kz if use_kz else ""})
    # killzones requested but none supplied: must fall through to the plain window
    for hhmm in (1000, 1200):
        cases.append({"id": f"ent_nokz_{hhmm}", "fn": "entry",
                      "p": [float(hhmm), 930.0, 1530.0, 1555.0, 1.0, 0, 0, 0, 0],
                      "extra": ""})
    return cases


def ftfc_cases() -> List[Dict[str, Any]]:
    """FTFC score. Boundary: price EXACTLY equal to an open counts zero."""
    cases = []
    sets = [
        ("100;100;100;100", 100.0),   # all exactly equal -> 0
        ("99;99;99;99", 100.0),       # all below -> +4
        ("101;101;101;101", 100.0),   # all above -> -4
        ("99;101;100;99", 100.0),     # mixed with an exact tie
        ("0;-5;100;99", 100.0),       # non-positive opens are skipped
        ("", 100.0),                  # empty
    ]
    for i, (opens, price) in enumerate(sets):
        cases.append({"id": f"ftfc_{i}", "fn": "ftfc",
                      "p": [price, 0, 0, 0, 0, 0, 0, 0, 0], "extra": opens})
    return cases


# ---------------------------------------------------------------------------
# The Python side, called exactly as a strategy would call it
# ---------------------------------------------------------------------------
def _hhmm_to_time(v: float) -> dtime:
    i = int(v)
    return dtime(i // 100, i % 100)


def python_result(case: Dict[str, Any]) -> List[str]:
    fn, p = case["fn"], case["p"]
    extra = case.get("extra", "")
    out = [""] * 6

    if fn == "classify":
        out[0] = str(int(classify_bar(p[0], p[1], p[2], p[3]).strat_type))

    elif fn == "wick":
        o, c, h, l, thr = p[0], p[1], p[2], p[3], p[4]
        info = classify_bar(h, l, h, l, open_price=o, close_price=c,
                            wick_threshold=thr)
        out[0] = str(int(info.wick_type))

    elif fn == "targets":
        m = measured_targets(int(p[0]), p[1], p[2], p[3], p[4], p[5], p[6],
                             p[7], p[8])
        out[0] = repr(m.target1)
        out[1] = repr(m.target2)
        out[2] = repr(m.risk_points)
        out[3] = repr(m.reward_points)
        out[4] = repr(m.rr_ratio)
        out[5] = "1" if m.stop_capped else "0"

    elif fn == "entry":
        kz = []
        if extra:
            vals = [int(v) for v in extra.split(";") if v]
            kz = [(_hhmm_to_time(vals[i]), _hhmm_to_time(vals[i + 1]))
                  for i in range(0, len(vals) - 1, 2)]
        ok = entry_allowed(_hhmm_to_time(p[0]), _hhmm_to_time(p[1]),
                           _hhmm_to_time(p[2]), _hhmm_to_time(p[3]),
                           killzones=kz, use_killzones=bool(p[4]))
        out[0] = "1" if ok else "0"

    elif fn == "ftfc":
        opens = [float(v) for v in extra.split(";") if v]
        score = 0
        for op in opens:
            if op <= 0 or op != op:
                continue
            if p[0] > op:
                score += 1
            elif p[0] < op:
                score -= 1
        out[0] = str(score)

    else:
        raise ValueError("unknown fn: " + fn)
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def write_cases(path: str, cases: List[Dict[str, Any]]) -> None:
    lines = ["id,fn,p1,p2,p3,p4,p5,p6,p7,p8,p9,extra"]
    for c in cases:
        p = list(c["p"]) + [0.0] * (9 - len(c["p"]))
        lines.append(",".join([c["id"], c["fn"]]
                              + [repr(float(v)) for v in p]
                              + [c.get("extra", "")]))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def run_csharp(cases_csv: str, out_csv: str) -> None:
    if not os.path.exists(EXE):
        build = subprocess.run(["dotnet", "build", "-v", "q", "--nologo"],
                               cwd=PROJ, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600)
        if build.returncode != 0:
            raise RuntimeError("StratCoreHarness build FAILED:\n"
                               + (build.stdout or "") + (build.stderr or ""))
    r = subprocess.run([EXE, cases_csv, out_csv], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    if r.returncode != 0:
        raise RuntimeError("StratCoreHarness exited {}:\n{}".format(
            r.returncode, (r.stdout or "") + (r.stderr or "")))


def read_results(path: str) -> Dict[str, List[str]]:
    out = {}
    with open(path, encoding="utf-8") as fh:
        rows = fh.read().splitlines()
    for row in rows[1:]:
        if not row.strip():
            continue
        c = row.split(",")
        out[c[0]] = (c[2:8] + [""] * 6)[:6]
    return out


def values_agree(a: str, b: str) -> bool:
    if a == b:
        return True
    if a == "" or b == "":
        return False
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return False
    if fa != fa and fb != fb:      # both NaN
        return True
    if fa == fb:
        return True
    scale = max(1.0, abs(fa), abs(fb))
    return abs(fa - fb) <= FLOAT_TOL * scale


def compare(cases, py, cs):
    rows = []
    for c in cases:
        cid = c["id"]
        pr = py[cid]
        cr = cs.get(cid)
        if cr is None:
            rows.append({"id": cid, "fn": c["fn"], "agree": False,
                         "detail": "C# produced NO ROW for this case"})
            continue
        bad = [i for i in range(6) if not values_agree(pr[i], cr[i])]
        rows.append({
            "id": cid, "fn": c["fn"], "agree": not bad,
            "detail": "" if not bad else "; ".join(
                "r{}: py={!r} cs={!r}".format(i + 1, pr[i], cr[i]) for i in bad),
            "inputs": c["p"], "extra": c.get("extra", ""),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the CSVs on disk")
    ap.add_argument("--max-report", type=int, default=25)
    args = ap.parse_args()

    cases = (classify_cases() + wick_cases() + target_cases()
             + entry_cases() + ftfc_cases())

    tmp = tempfile.mkdtemp(prefix="stratcore_parity_")
    cases_csv = os.path.join(tmp, "cases.csv")
    out_csv = os.path.join(tmp, "cs_results.csv")
    write_cases(cases_csv, cases)
    run_csharp(cases_csv, out_csv)

    py = {c["id"]: python_result(c) for c in cases}
    cs = read_results(out_csv)
    rows = compare(cases, py, cs)

    by_fn = {}
    for r in rows:
        d = by_fn.setdefault(r["fn"], [0, 0])
        d[0] += 1
        if not r["agree"]:
            d[1] += 1

    print("StratCore.cs  vs  scripts/libs_py/the_strat/")
    print("=" * 70)
    print(f"{'function':<12} | {'cases':>6} | {'DISAGREE':>9}")
    print("-" * 70)
    for fn in ("classify", "wick", "targets", "entry", "ftfc"):
        if fn in by_fn:
            n, bad = by_fn[fn]
            print(f"{fn:<12} | {n:>6} | {bad:>9}")
    total = sum(v[0] for v in by_fn.values())
    total_bad = sum(v[1] for v in by_fn.values())
    print("-" * 70)
    print(f"{'TOTAL':<12} | {total:>6} | {total_bad:>9}")

    if total_bad:
        print("\nDIVERGENCES (the two sides do not implement the same rule):")
        shown = 0
        for r in rows:
            if r["agree"]:
                continue
            if shown >= args.max_report:
                print(f"  ... {total_bad - shown} more")
                break
            print(f"  [{r['fn']}] {r['id']}")
            print(f"      inputs: {r.get('inputs')} extra={r.get('extra')!r}")
            print(f"      {r['detail']}")
            shown += 1

    if args.keep:
        print(f"\nCSVs kept in {tmp}")
    print()
    if total_bad:
        print("FAIL: the C# core and the Python core disagree. StratCore.cs claims "
              "to be a mirror of scripts/libs_py/the_strat/ and says rule changes "
              "must land on both sides together.")
        return 1
    print("OK: every case agrees. The mirror holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
