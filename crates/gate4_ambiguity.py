r"""
Gate 4: intrabar ambiguity policy — Rust and Python agree PER POLICY, and the
policies actually disagree where a bar cannot say what happened.

Three assertions, and the middle one is the load-bearing negative control:

  1. On a bar where the stop AND the queen target both lie inside [low, high],
     `favourable` books a win (target, then breakeven lock) and `adverse` books a
     full stop. If these ever agree, the policy parameter is dead and every caller
     is silently getting one branch - which is exactly the state this gate exists
     to prevent (a detector that fires on everything passes every positive test).
  2. Rust and Python produce identical trades under EACH policy. `gate2_parity.py`
     pins them equal on real bars but only on the default, so it cannot see a
     policy threaded into one engine and not the other.
  3. An unrecognised policy name raises. A silent fallback would make the policy a
     suggestion and let a typo restore the favourable default this replaced.

Run: .venv\Scripts\python.exe crates\gate4_ambiguity.py
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\vinay\tvDownloadOHLC")
from scripts.execution.nt8_parity_engine import (  # noqa: E402
    AMBIGUITY_ADVERSE,
    AMBIGUITY_FAVOURABLE,
    NT8ParityEngine,
)

ENTRY = 20000.0          # limit price -> entry
STOP = 19990.0           # 10 pts of risk
QUEEN_BPS = 10.0         # tp1 = 20000 * 1.001 = 20020.0
RUNNER_BPS = 30.0        # tp2 = 20000 * 1.003 = 20060.0


def build_case() -> tuple:
    """Bar 0 arms a long; bar 1 fills it at the limit; bar 2 is AMBIGUOUS.

    Bar 2 has high >= tp1 (20020) and low <= stop (19990). A 1-minute OHLC bar
    does not record which came first, so the two policies must diverge here.
    Times are tz-naive and inside 09:45-15:30 (and outside the lunch filter) so
    that both engines derive the same hhmm - the Rust path reads it from epoch-ms
    as UTC while Python reads the index, so a tz-aware index would desync them.
    """
    idx = pd.to_datetime([
        "2026-03-10 10:00:00",   # arm
        "2026-03-10 10:01:00",   # fill at 20000
        "2026-03-10 10:02:00",   # AMBIGUOUS: touches 20025 and 19985
        "2026-03-10 10:03:00",   # benign tail
    ])
    df = pd.DataFrame(
        {
            "open":  [20010.0, 20005.0, 20005.0, 20000.0],
            "high":  [20012.0, 20006.0, 20025.0, 20001.0],
            "low":   [20008.0, 19999.0, 19985.0, 19999.0],
            "close": [20010.0, 20005.0, 20000.0, 20000.0],
        },
        index=idx,
    )
    signals = pd.Series([1, 0, 0, 0], index=idx, dtype="int32")
    limits = pd.Series([ENTRY] * 4, index=idx, dtype="float64")
    stops = pd.Series([STOP] * 4, index=idx, dtype="float64")
    return df, signals, limits, stops


def run(engine, df, signals, limits, stops, policy, use_rust):
    return engine.simulate(
        df, signals, limits, stops,
        queen_bps=QUEEN_BPS, runner_bps=RUNNER_BPS,
        earliest_entry_hhmm=945, latest_entry_hhmm=1530, flatten_hhmm=1555,
        filter_lunch=True,
        use_rust=use_rust,
        ambiguity_policy=policy,
    )


COMPARE_COLS = [
    "direction", "entry_price", "exit_price",
    "leg1_points", "leg2_points", "total_points", "exit_reason",
]


def main() -> int:
    engine = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
    df, signals, limits, stops = build_case()

    results = {}
    failures = []

    for policy in (AMBIGUITY_ADVERSE, AMBIGUITY_FAVOURABLE):
        rust = run(engine, df, signals, limits, stops, policy, use_rust=True)
        py = run(engine, df, signals, limits, stops, policy, use_rust=False)

        if len(rust) != 1 or len(py) != 1:
            failures.append(
                f"[{policy}] expected exactly 1 trade, got rust={len(rust)} py={len(py)}. "
                "The fixture no longer exercises the ambiguous bar."
            )
            continue

        r, p = rust.iloc[0], py.iloc[0]
        for col in COMPARE_COLS:
            rv, pv = r[col], p[col]
            same = (rv == pv) if isinstance(rv, str) else np.isclose(rv, pv)
            if not same:
                failures.append(f"[{policy}] engine mismatch on {col}: rust={rv!r} py={pv!r}")

        results[policy] = r
        print(f"[{policy}] pts={r['total_points']:+.2f} reason={r['exit_reason']!r} "
              f"leg1={r['leg1_points']:+.2f} leg2={r['leg2_points']:+.2f}")

    # 1. The negative control: the policies MUST disagree on this bar.
    if len(results) == 2:
        adv = results[AMBIGUITY_ADVERSE]
        fav = results[AMBIGUITY_FAVOURABLE]
        if np.isclose(adv["total_points"], fav["total_points"]):
            failures.append(
                f"POLICY IS DEAD: adverse and favourable both booked "
                f"{adv['total_points']:+.2f} pts on a bar that touched both the stop "
                f"({STOP}) and tp1. The parameter is not reaching the fill logic."
            )
        if adv["total_points"] >= 0:
            failures.append(
                f"adverse booked {adv['total_points']:+.2f} pts; a full stop must be "
                f"negative (stop {STOP} vs entry {ENTRY})"
            )
        if fav["total_points"] <= 0:
            failures.append(
                f"favourable booked {fav['total_points']:+.2f} pts; the queen fill plus "
                f"breakeven lock must be positive"
            )

    # 3. Unknown policy must raise, not fall back.
    for bad in ("Adverse", "pessimistic", "", None):
        try:
            run(engine, df, signals, limits, stops, bad, use_rust=True)
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001
            failures.append(f"policy {bad!r} raised {type(exc).__name__}, expected ValueError")
        else:
            failures.append(f"policy {bad!r} was ACCEPTED; unknown policies must be refused")

    if failures:
        print("\n=== GATE 4 FAILED ===")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n=== GATE 4 PASSED ===")
    print("  Rust == Python under each policy; policies diverge on the ambiguous bar;")
    print("  unknown policy names refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
