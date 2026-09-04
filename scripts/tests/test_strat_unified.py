"""Tests for the unified Strat stack: config, targets, session, signals engine."""

import pandas as pd

from scripts.libs_py.the_strat.config import StratConfig, load_strat_config
from scripts.libs_py.the_strat.session import entry_allowed, parse_hhmm
from scripts.libs_py.the_strat.signals import StratSignalEngine
from scripts.libs_py.the_strat.targets import measured_targets


def _bars():
    # 2U -> 1 -> 2U bull 2-1-2, plus confirming bars.
    bars = [
        (100, 105, 95, 102),
        (102, 110, 101, 109),
        (109, 108, 103, 106),
        (106, 112, 104, 111),
        (111, 114, 109, 113),
        (112, 115, 110, 114),
    ]
    idx = pd.date_range("2025-01-06 10:00", periods=len(bars), freq="5min", tz="America/New_York")
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)


def test_config_loads_canonical():
    cfg = load_strat_config()
    assert isinstance(cfg, StratConfig)
    assert "2-1-2_BULL_CONT" in cfg.allowed_setups
    assert cfg.use_ftfc_filter is True
    assert cfg.instrument("NQ1").point_value == 20.0
    assert cfg.instrument("MES1").point_value == 5.0


def test_measured_targets_beat_structural():
    # Old combos logic gave target=110 vs entry 108.25 (RR ~0.3). Measured engine
    # must project a real expansion move honoring min_target_points.
    mt = measured_targets(1, 108.25, 102.75, 108.0, 103.0, 5.0, 15.0, 15.0, 0.25)
    assert mt.target1 == 108.25 + 15.0
    assert mt.target2 == 108.25 + 30.0
    assert mt.rr_ratio > 1.0
    assert mt.stop_capped is False


def test_measured_targets_cap_risk_and_flag():
    mt = measured_targets(1, 108.25, 80.0, 108.0, 103.0, 5.0, 15.0, 15.0, 0.25)
    assert mt.risk_points == 15.0
    assert mt.stop_capped is True


def test_session_gate_killzones():
    earliest, latest, flat = parse_hhmm("09:30"), parse_hhmm("15:30"), parse_hhmm("15:55")
    kz = [(parse_hhmm("09:45"), parse_hhmm("11:30"))]
    assert entry_allowed(parse_hhmm("10:00"), earliest, latest, flat, kz, True) is True
    assert entry_allowed(parse_hhmm("12:00"), earliest, latest, flat, kz, True) is False
    assert entry_allowed(parse_hhmm("12:00"), earliest, latest, flat, kz, False) is True
    assert entry_allowed(parse_hhmm("15:56"), earliest, latest, flat, kz, False) is False


def test_engine_emits_measured_signal():
    eng = StratSignalEngine()
    out = eng.generate(
        _bars(),
        params={"use_ftfc_filter": False, "use_killzones": False,
                "confirm_next_bar": True, "min_rr_ratio": 0.0},
    )
    assert len(out) >= 1
    row = out.iloc[0]
    assert row["model_name"] == "2-1-2_BULL_CONT"
    assert row["direction"] == 1
    assert row["target1_price"] > row["entry_price"] + 10.0  # measured, not prior high
    assert row["risk_pts"] <= 15.0
    assert bool(row["confirmed"]) is True


def test_engine_ftfc_gate_blocks_countertrend():
    eng = StratSignalEngine()
    # Same up-trend bars: a SHORT must not survive the FTFC gate.
    out = eng.generate(
        _bars(),
        params={"allowed_setups": ["2-2_BEAR_REV"], "min_rr_ratio": 0.0},
    )
    assert len(out) == 0
