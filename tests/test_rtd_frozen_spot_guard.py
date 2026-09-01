"""Regression test for the 2026-08-31 incident: frozen RTD LAST served all day.

Root causes fixed:
  1. adapter: global _last_data_time updated by ANY topic (incl. OI scan
     waves), so a frozen /ES:LAST passed the data-path-age gate all Monday.
     Fix: per-topic arrival times (_topic_time); get_futures_price rejects
     when the LAST topic itself is stale.
  2. coordinator: divergence watchdog only compared against cached Schwab
     prices, and off-hours/weekday-morning cycles skip Schwab — so the frozen
     feed was never cross-checked. Fix: fall back to the freshest 1m futures
     parquet close as reference (only when the parquet itself is <10 min old).
"""
import sys
import threading
import time
from types import SimpleNamespace
import unittest.mock as m

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import scripts.streaming.options.tos_rtd.adapter as adapter_mod
from scripts.streaming.options.tos_rtd.hybrid_coordinator import HybridCoordinator

# Monday 2026-08-31 numbers: RTD kept serving Friday's 7724.75 all day
# while ES actually closed ~7697-7701 (0.35% divergence > 0.2% threshold).
FROZEN = 7724.75
PARQUET_MON = 7697.5


def make_adapter(last_price: float, topic_age: float) -> SimpleNamespace:
    """Adapter stub with per-topic freshness semantics like the real one."""
    now = time.time()
    a = SimpleNamespace()
    a._running = True
    a._drain_dead = False
    a._latest_data = {"/ES:XCME:LAST": last_price}
    a._topic_time = {"/ES:XCME:LAST": now - topic_age}
    a._last_data_time = now  # global age fresh: other topics flowing
    a._latest_lock = threading.Lock()
    # bind the real method
    a.get_futures_price = adapter_mod.TOSRTDAdapter.get_futures_price.__get__(a)
    a.get_snapshot = lambda: dict(a._latest_data)
    return a


def test_frozen_last_refused():
    a = make_adapter(FROZEN, topic_age=999_999)  # LAST arrived Friday
    p = a.get_futures_price("/ES", max_age=120)
    assert p is None, f"frozen LAST must be refused, got {p}"
    print("PASS: stale LAST topic refused despite fresh global data path")


def test_fresh_last_accepted():
    a = make_adapter(7701.5, topic_age=5)
    p = a.get_futures_price("/ES", max_age=120)
    assert abs((p or 0) - 7701.5) < 1e-6, f"fresh LAST must pass, got {p}"
    print("PASS: fresh LAST topic accepted")


def make_coordinator(rtd_price: float | None):
    c = object.__new__(HybridCoordinator)
    c._schwab_prices = {}
    c._divergence_count = {}
    c._topic_time = {}
    if rtd_price is None:
        c._adapter = SimpleNamespace(get_futures_price=lambda s, max_age=None: None)
    else:
        c._adapter = SimpleNamespace(
            get_futures_price=lambda s, max_age=None: rtd_price)
    type(c).is_rtd_active = property(lambda self: True)
    return c


def test_watchdog_catches_frozen_rtd_without_schwab():
    with (m.patch.object(HybridCoordinator, "is_rtd_active", True),
          m.patch.object(HybridCoordinator, "_recent_parquet_close",
                         lambda self, s: PARQUET_MON)):
        c = make_coordinator(FROZEN)
        q = c.get_futures_price("/ES")
    assert q is not None, "expected a quote"
    assert q.source == "parquet_fallback", f"expected parquet_fallback, got {q.source}"
    assert abs(q.price - PARQUET_MON) < 1e-6, f"expected {PARQUET_MON}, got {q.price}"
    print(f"PASS: coordinator prefers parquet ref over frozen RTD "
          f"(source={q.source}, price={q.price})")


def test_watchdog_passes_when_agreeing():
    with (m.patch.object(HybridCoordinator, "is_rtd_active", True),
          m.patch.object(HybridCoordinator, "_recent_parquet_close",
                         lambda self, s: 7725.10)):
        c = make_coordinator(FROZEN)
        q = c.get_futures_price("/ES")
    assert q is not None and q.source == "tos_rtd", \
        f"agreement should serve RTD, got {q.source}"
    assert abs(q.price - FROZEN) < 1e-6
    print("PASS: agreeing parquet ref does not hijack live RTD")


def main():
    test_frozen_last_refused()
    test_fresh_last_accepted()
    test_watchdog_catches_frozen_rtd_without_schwab()
    test_watchdog_passes_when_agreeing()
    print("ALL PASS")


if __name__ == "__main__":
    main()