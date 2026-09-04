"""Strat session / killzone / flatten engine (Pillar 1 — pure).

One implementation of ET session logic shared by:
  - Python backtests (via signals.py + run_* presets), and
  - NT8 bots (mirrored in StratCore.cs — keep the window semantics identical).

Rules:
  - All comparisons on America/New_York wall-clock time (naive time objects
    are assumed to already be ET — DataLoader localizes upstream per ADR-001).
  - Entry allowed in [earliest_entry, latest_entry]; when use_killzones is
    true the bar must additionally fall inside one killzone window.
  - flatten_by is a HARD exit: no new entries at/after it, positions closed.
    ADR-020 requires flat by 16:00 ET; default 15:55 leaves a bar of slack.
"""

from __future__ import annotations

from datetime import time


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")[:2]
    return time(int(h), int(m))


def in_window(t: time, start: time, end: time) -> bool:
    return start <= t <= end


def entry_allowed(
    t: time,
    earliest: time,
    latest: time,
    flatten_by: time,
    killzones: list[tuple[time, time]] | None = None,
    use_killzones: bool = True,
) -> bool:
    """True if a new entry may be taken on a bar stamped time t (ET)."""
    if t < earliest or t > latest or t >= flatten_by:
        return False
    if use_killzones and killzones:
        return any(in_window(t, s, e) for s, e in killzones)
    return True


def killzones_from_config(killzones: list[dict]) -> list[tuple[time, time]]:
    out: list[tuple[time, time]] = []
    for kz in killzones or []:
        try:
            out.append((parse_hhmm(kz["start"]), parse_hhmm(kz["end"])))
        except (KeyError, ValueError, AttributeError):
            continue
    return out
