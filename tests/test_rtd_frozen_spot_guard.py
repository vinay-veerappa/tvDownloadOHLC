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
import json
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


def test_prior_session_oi_carried_forward():
    """A failed fresh scan must not destroy the prior session's good OI."""
    c = object.__new__(HybridCoordinator)
    c._market_cache_path = m.MagicMock()
    c._market_cache_path.exists.return_value = True
    c._market_cache_path.read_text.return_value = json.dumps({
        "session_key": "2026-08-30",
        "open_interest": {
            "/ES": {"./EWQ26C7800:XCME": 4203, "./EWQ26P7500:XCME": 0},
            "/NQ": {"./QN1U26C29600:XCME": 106},
        },
    })
    oi = c._load_prior_session_oi()
    assert oi["/ES"]["./EWQ26C7800:XCME"] == 4203, "real OI must carry"
    assert "./EWQ26P7500:XCME" not in oi["/ES"], "zero-OI must be dropped"
    assert oi["/NQ"]["./QN1U26C29600:XCME"] == 106
    print("PASS: prior-session OI carried forward, zeros dropped")


def test_oi_history_append_and_read(tmp_path=None):
    """The OI book is appended per session and readable back."""
    import tempfile
    from pathlib import Path
    from scripts.streaming.options.tos_rtd.oi_history import (
        load_oi_history, oi_delta,
    )
    tmp = Path(tempfile.mkdtemp())
    hist = tmp / "history" / "oi" / "oi_book.jsonl"
    hist.parent.mkdir(parents=True)

    c = object.__new__(HybridCoordinator)
    c._market_cache_path = tmp / ".rtd_market_cache.json"
    c._append_oi_history("2026-09-01", {"/ES": {"./EWQ26C7800:XCME": 4203}}, {"degraded": False})
    c._append_oi_history("2026-09-02", {"/ES": {"./EWQ26C7800:XCME": 4500}}, {"degraded": False})

    rows = load_oi_history(path=hist)
    assert len(rows) == 2, f"expected 2 records, got {len(rows)}"
    assert rows[0]["session_key"] == "2026-09-01"
    assert rows[1]["open_interest"]["/ES"]["./EWQ26C7800:XCME"] == 4500

    deltas = oi_delta("/ES", path=hist)
    assert deltas[1]["delta"]["./EWQ26C7800:XCME"] == 297, "OI delta must be +297"
    print("PASS: OI history appended + readable + delta computed")


def test_persistent_wave_completeness_scoped_to_wave():
    """Persistent multi-wave scan must scope completeness to the CURRENT wave.

    Regression for the 0-OI bug: in persistent mode the snapshot accumulates
    prior waves' OPEN_INT keys, so counting all of them made wave 2+ break
    instantly and then collect nothing for the current wave.
    """
    import scripts.streaming.options.tos_rtd.hybrid_coordinator as hc_mod
    from scripts.streaming.options.tos_rtd.quote_types import QuoteType

    # Wave 1 symbols already delivered (in snapshot); wave 2 not yet.
    wave1 = [f"./EW1U26C76{i:02d}:XCME" for i in range(0, 6)]
    wave2 = [f"./EW1U26C77{i:02d}:XCME" for i in range(0, 6)]

    c = object.__new__(HybridCoordinator)
    c._adapter = SimpleNamespace(
        is_running=lambda: True,
        subscribe_more=lambda subs: None,
        get_snapshot=lambda: {f"{s}:OPEN_INT": 100 for s in wave1},
        stop=lambda: None,
    )

    # Patch the poll loop to a single iteration so we can inspect the
    # completeness decision without a real 20s wait.
    import scripts.streaming.options.tos_rtd.hybrid_coordinator as hc
    orig = hc.time.sleep
    hc.time.sleep = lambda *a, **k: None
    try:
        # Wave 2 has 6 symbols, target 80% = 4. Snapshot has only wave1 keys.
        # With the fix, completeness must NOT be reached (0 wave2 keys < 4),
        # so the loop runs to timeout and returns {} for wave2.
        result = c._run_oi_scan(wave2, timeout=0.1, completeness_pct=0.8, persistent=True)
    finally:
        hc.time.sleep = orig

    assert result == {}, f"wave2 must return empty (no wave2 OI delivered), got {result}"
    print("PASS: persistent wave completeness scoped to current wave (no false-complete)")


def main():
    test_frozen_last_refused()
    test_fresh_last_accepted()
    test_watchdog_catches_frozen_rtd_without_schwab()
    test_watchdog_passes_when_agreeing()
    test_prior_session_oi_carried_forward()
    test_oi_history_append_and_read()
    test_persistent_wave_completeness_scoped_to_wave()
    print("ALL PASS")


if __name__ == "__main__":
    main()