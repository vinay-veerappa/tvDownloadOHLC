"""The one reader of `trading_defaults.json`.

Every strategy inherits these; only the trade setup varies. Nothing else in this
repo may carry a point-value table, a tick-size table, or a session window list
-- `tests/test_frozen_defaults.py` scans for a second one.

WHY A SEPARATE MODULE FROM config_loader.py. `sessions.yaml` is per-run settings
a caller may legitimately override (trial count, which prop profiles to run).
These are FROZEN: a strategy that needs a different point value for NQ is not
configured differently, it is wrong. Keeping them apart makes that visible in
the import.

RESOLUTION NEVER DEFAULTS. `resolve_instrument` raises on an unknown ticker. The
defect this replaces was `point_value.get(ticker, 2.0)`: "NQ1" was not a key, so
the fallback answered $2/pt while the backtest engine's own table answered $20 --
and neither said so. An unknown instrument is a question, not a number.
"""

from __future__ import annotations

import functools
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_PATH = pathlib.Path(__file__).with_name("trading_defaults.json")

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point_value: float
    tick_size: float
    tick_value: float
    klass: str
    requested: str          # what the caller asked for, e.g. "NQ1"

    @property
    def is_micro(self) -> bool:
        return self.klass == "micro"


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start_min: int          # minutes past ET midnight, inclusive
    end_min: int            # exclusive; < start_min means it crosses midnight

    @property
    def wraps(self) -> bool:
        return self.end_min <= self.start_min

    def contains_minute(self, m: int) -> bool:
        if self.wraps:
            return m >= self.start_min or m < self.end_min
        return self.start_min <= m < self.end_min


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@functools.lru_cache(maxsize=1)
def load_trading_defaults() -> dict:
    """Read and VALIDATE the frozen document. Raises rather than degrading."""
    with _PATH.open(encoding="utf-8") as fh:
        d = json.load(fh)

    # tickValue is derivable, so it is a CONSISTENCY CHECK, not a source.
    for sym, spec in d["instruments"]["table"].items():
        want = spec["tickSize"] * spec["pointValue"]
        if abs(spec["tickValue"] - want) > 1e-9:
            raise ValueError(
                "{}: tickValue {} != tickSize {} x pointValue {} = {}".format(
                    sym, spec["tickValue"], spec["tickSize"],
                    spec["pointValue"], want))

    for alias, target in d["instruments"]["aliases"].items():
        if target not in d["instruments"]["table"]:
            raise ValueError(
                "alias {} -> {} names no instrument".format(alias, target))
    if d["instruments"]["default"] not in d["instruments"]["table"]:
        raise ValueError("default instrument is not in the table")

    assert_sessions_partition(session_windows(d))

    for name in d["sessions"]["tradeable"]:
        if name not in {w["name"] for w in d["sessions"]["windows"]}:
            raise ValueError("tradeable session {} has no window".format(name))
    return d


def session_windows(d: dict = None) -> List[SessionWindow]:
    d = d or load_trading_defaults()
    return [SessionWindow(w["name"], _to_minutes(w["start"]), _to_minutes(w["end"]))
            for w in d["sessions"]["windows"]]


def assert_sessions_partition(windows: List[SessionWindow]) -> None:
    """Every minute of the day belongs to exactly ONE window.

    An overlapping set lets a single trade count in two sessions, so the
    per-session breakdown sums to more than the total and every rate in it is
    wrong. A gapped set silently drops trades out of the report entirely --
    which is the failure mode that matters more, because the total still looks
    right. nqstats' own set overlaps (RTH, IB and NY_AM all cover 09:30), which
    is why it could not be adopted unchanged.
    """
    owner: Dict[int, str] = {}
    for w in windows:
        for m in range(MINUTES_PER_DAY):
            if w.contains_minute(m):
                if m in owner:
                    raise ValueError(
                        "minute {:02d}:{:02d} is in both {} and {}".format(
                            m // 60, m % 60, owner[m], w.name))
                owner[m] = w.name
    missing = [m for m in range(MINUTES_PER_DAY) if m not in owner]
    if missing:
        raise ValueError(
            "{} minute(s) belong to no session, first {:02d}:{:02d}".format(
                len(missing), missing[0] // 60, missing[0] % 60))


def resolve_instrument(ticker: str) -> Instrument:
    """Data ticker or contract symbol -> the contract actually traded.

    RAISES on anything unrecognised. See the module docstring: a silent fallback
    here is how one run valued the same point at $20 and $2.
    """
    d = load_trading_defaults()
    key = (ticker or "").strip().upper()
    if not key:
        raise ValueError("no ticker given; there is no default instrument for a "
                         "run that did not say what it traded")
    sym = d["instruments"]["aliases"].get(key, key)
    spec = d["instruments"]["table"].get(sym)
    if spec is None:
        raise KeyError(
            "unknown instrument {!r} (resolved to {!r}). Known: {}. Aliases: {}. "
            "Add it to config/trading_defaults.json -- do not pass a point value "
            "at the call site.".format(
                ticker, sym, sorted(d["instruments"]["table"]),
                sorted(d["instruments"]["aliases"])))
    return Instrument(symbol=sym, point_value=float(spec["pointValue"]),
                      tick_size=float(spec["tickSize"]),
                      tick_value=float(spec["tickValue"]),
                      klass=spec["class"], requested=key)


def point_value(ticker: str) -> float:
    return resolve_instrument(ticker).point_value


def tick_size(ticker: str) -> float:
    return resolve_instrument(ticker).tick_size


def risk_defaults() -> dict:
    return dict(load_trading_defaults()["risk"])


def nt8_defaults() -> dict:
    return dict(load_trading_defaults()["nt8"])


def execution_defaults() -> dict:
    return dict(load_trading_defaults()["execution"])


#: `max_trades_per_day` is compared with `<` inside the engine loop, so "no cap"
#: cannot be expressed as None there. It is expressed as a number no run can
#: reach. The value is NEVER reported -- `execution_policy()` emits the null it
#: came from -- because an artifact saying "capped at 1000000000" and one saying
#: "uncapped" read differently to a human and only one of them is true.
UNCAPPED = 1_000_000_000

#: 00:00 and 23:59 as HHMM. The engine's entry window is an inclusive integer
#: comparison, so an unrestricted window is the widest one, not a missing one.
_NO_EARLIEST_HHMM = 0
_NO_LATEST_HHMM = 2359


def _hhmm(et: Optional[str], fallback: int) -> int:
    """"15:45" -> 1545. A null means the frozen document declined to restrict."""
    if not et:
        return fallback
    h, m = et.split(":")
    return int(h) * 100 + int(m)


def execution_policy(overrides: dict = None) -> dict:
    """THE execution policy a backtest runs under, resolved from ONE document.

    WHY THIS EXISTS. Measured 2026-09-05, a single sanctioned run carried three
    execution policies. `trading_defaults.json` said 1 contract, 1 tick of
    slippage, $0.62 round-trip, no entry cut-off, no daily trade cap and a 15:45
    flatten. `NT8ParityBacktester.__init__` said 2 contracts, 0 ticks, $1.40 and
    a 3-trade cap. `run_backtest.py` then passed 09:45-15:30 entries, lunch
    filtered and a 15:55 flatten as literals. None of the three cited the
    others, so the frozen document -- the thing §1.3 calls canonical -- was the
    only one of the three that did not decide anything.

    Two of those disagreements are not cosmetic. `filter_lunch=True` deletes the
    NY_LUNCH session, which `sessions.reportPerSession` exists to MEASURE; the
    run answered "is lunch worth trading?" by refusing to trade it. And a
    09:45-15:30 window forbids the NY_PM setup BBMRReversionBot is built around,
    which is precisely the reason `lastEntryEt` was set to null.

    `overrides` is for a value a STRATEGY legitimately decides (its own stop
    distance, its own target). It may not name a key in `risk.overridable`'s
    complement -- ADR-020's `rthHardExitEt` above all -- and it is recorded, so
    a result never carries a policy no artifact names.
    """
    ex = execution_defaults()
    rk = risk_defaults()
    cap = rk.get("maxTradesPerDay")
    policy = {
        "contracts": int(ex["defaultContracts"]),
        "commission": float(ex["commissionPerContractRoundTrip"]),
        "slippage_ticks": float(ex["slippageTicks"]),
        # Reported as the null it is; converted at the engine boundary only.
        "max_trades_per_day": cap,
        "earliest_entry_hhmm": _NO_EARLIEST_HHMM,
        "latest_entry_hhmm": _hhmm(rk.get("lastEntryEt"), _NO_LATEST_HHMM),
        "flatten_hhmm": _hhmm(rk.get("flattenByEt"), None),
        # The lunch session is REPORTED on, not filtered out. See above.
        "filter_lunch": False,
        "_source": "config/trading_defaults.json (frozen {})".format(
            load_trading_defaults().get("frozenOn")),
    }
    hard = _hhmm(rk["rthHardExitEt"], None)
    if policy["flatten_hhmm"] > hard:
        raise ValueError(
            "flattenByEt {} is after rthHardExitEt {}. ADR-020 has no "
            "exemptions.".format(rk.get("flattenByEt"), rk["rthHardExitEt"]))
    if overrides:
        allowed = set(policy) - {"_source"}
        unknown = sorted(set(overrides) - allowed)
        if unknown:
            raise ValueError(
                "execution_policy() cannot override {}: it is not part of the "
                "execution policy. Known: {}".format(
                    ", ".join(unknown), ", ".join(sorted(allowed))))
        policy.update(overrides)
        policy["_source"] += " + caller override of " + ", ".join(sorted(overrides))
    return policy


def engine_max_trades_per_day(cap: Optional[int]) -> int:
    """The engine boundary: a null cap becomes the unreachable number, once."""
    return UNCAPPED if cap is None else int(cap)


def tradeable_sessions() -> Tuple[str, ...]:
    return tuple(load_trading_defaults()["sessions"]["tradeable"])
