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
from typing import Dict, List, Tuple

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


def tradeable_sessions() -> Tuple[str, ...]:
    return tuple(load_trading_defaults()["sessions"]["tradeable"])
