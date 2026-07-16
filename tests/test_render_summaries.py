"""Tests for the multi-ticker render path.

Covers:
- The NARRATIVE_INSTRUMENT_MAP central registry (pipeline / micro split).
- Slot names use the PIPELINE label (NQ, ES), not the micro (MNQ, MES).
- LLM JSON contract uses the pipeline label as the dict key.
- `plan_json.trades[].asset` uses the MICRO label (the actual contract).
- Legacy `mes` / `mnq` / `tomorrow_mes` / `tomorrow_mnq` / `session_log.mes`
  / `session_log.mnq` keys still work (backward compat).
- Adding a new ticker via monkeypatch renders without code changes.

Background
----------
Issue §2.1 found that the renderers hardcoded `mes` / `mnq` keys, and
the slot names were `MNQ_REGIME` / `MES_REGIME`. That conflated two
different concepts:

  - The PIPELINE label (NQ, ES) — the futures the trader WATCHES.
    Slot names, regime lines, level tables, and the LLM's JSON keys
    should all use this.

  - The MICRO label (MNQ, MES) — the actual prop-firm contract.
    Only `plan_json.trades[].asset` should use this, because that
    is the field the prop-firm API cares about.

This file is the test for that fix.
"""
from __future__ import annotations

import pytest

from scripts.trader import daily_narrative as dn
from scripts.trader.daily_narrative import (
    MICRO_TO_NARRATIVE,
    NARRATIVE_INSTRUMENT_MAP,
    NARRATIVE_TO_MICRO,
    PIPELINE_TO_NARRATIVE,
    build_eod_static_template,
    build_open_static_template,
    render_eod_summary,
    render_open_summary,
)


# ── NARRATIVE_INSTRUMENT_MAP shape ──────────────────────────────────


def test_instrument_map_contains_nq1_and_es1():
    assert "NQ1" in NARRATIVE_INSTRUMENT_MAP
    assert "ES1" in NARRATIVE_INSTRUMENT_MAP


def test_instrument_map_uses_pipeline_label_for_narrative():
    """NQ1's pipeline label is NQ, micro label is MNQ. The narrative
    uses NQ for slots / regime lines / levels. MNQ is only for the
    `plan_json.trades[].asset` field."""
    nq1 = NARRATIVE_INSTRUMENT_MAP["NQ1"]
    assert nq1["pipeline"] == "NQ"
    assert nq1["micro"] == "MNQ"
    es1 = NARRATIVE_INSTRUMENT_MAP["ES1"]
    assert es1["pipeline"] == "ES"
    assert es1["micro"] == "MES"


def test_reverse_maps_are_consistent():
    # Every narrative ticker has a unique pipeline and micro label.
    pipelines = [s["pipeline"] for s in NARRATIVE_INSTRUMENT_MAP.values()]
    micros = [s["micro"] for s in NARRATIVE_INSTRUMENT_MAP.values()]
    assert len(set(pipelines)) == len(pipelines)
    assert len(set(micros)) == len(micros)

    # Each reverse map should be the inverse of the forward map.
    for ticker, spec in NARRATIVE_INSTRUMENT_MAP.items():
        assert PIPELINE_TO_NARRATIVE[spec["pipeline"]] == ticker
        assert MICRO_TO_NARRATIVE[spec["micro"]] == ticker
        assert NARRATIVE_TO_MICRO[ticker] == spec["micro"]


# ── Static template slot names use PIPELINE label ───────────────────


def _fake_briefing(tickers: list[str] | None = None) -> dict:
    """Build a briefing payload keyed by pipeline label (the canonical
    shape the daily-eod-update pipeline produces)."""
    if tickers is None:
        tickers = ["NQ1", "ES1"]
    return {
        "meta": {"date": "2026-07-14"},
        "tickers": [
            {
                "ticker": NARRATIVE_INSTRUMENT_MAP[t]["pipeline"],
                "regime_check": {"current_regime": "TRENDING"},
                "weekly_anchor": {"mandated_track": "A"},
            }
            for t in tickers
        ],
        "economic_events": [],
    }


def test_open_template_uses_pipeline_slot_names():
    template = build_open_static_template(_fake_briefing(), "(levels)")
    # Pipeline slots MUST be present.
    assert "{{NQ_REGIME}}" in template
    assert "{{NQ_ENTRY}}" in template
    assert "{{NQ_STOP}}" in template
    assert "{{ES_REGIME}}" in template
    assert "{{ES_ENTRY}}" in template
    assert "{{ES_STOP}}" in template
    # Micro labels MUST NOT appear in slot names.
    assert "MNQ_REGIME" not in template
    assert "MNQ_ENTRY" not in template
    assert "MES_REGIME" not in template
    assert "MES_ENTRY" not in template


def test_open_template_trade_plan_uses_micro_for_asset():
    """The default plan_json.trades[].asset uses the micro label —
    that's the actual prop-firm contract."""
    template = build_open_static_template(_fake_briefing(), "(levels)")
    assert '"asset": "MNQ"' in template
    assert '"asset": "MES"' in template


def test_open_template_description_names_pipeline_with_micro_contract():
    """The trade-plan block header should make both labels visible
    so the trader knows they're trading the NQ chart with the MNQ
    contract."""
    template = build_open_static_template(_fake_briefing(), "(levels)")
    # Header line should mention the pipeline label, then "(MNQ micro)"
    # in the description, then the contract.
    assert "**NQ**" in template
    assert "(MNQ micro)" in template
    assert "contract: MNQ" in template


def test_eod_template_uses_pipeline_slot_names():
    template = build_eod_static_template(_fake_briefing(), "(levels)")
    # TM_* slots use pipeline label.
    assert "{{TM_NQ_REGIME}}" in template
    assert "{{TM_NQ_ENTRY}}" in template
    assert "{{TM_ES_REGIME}}" in template
    assert "{{TM_ES_ENTRY}}" in template
    # SESSION_* uses pipeline label.
    assert "{{SESSION_NQ}}" in template
    assert "{{SESSION_ES}}" in template
    # Micro labels MUST NOT appear in slot names.
    assert "TM_MNQ_" not in template
    assert "TM_MES_" not in template
    assert "SESSION_MNQ" not in template
    assert "SESSION_MES" not in template


def test_eod_template_session_log_line_uses_pipeline_label():
    template = build_eod_static_template(_fake_briefing(), "(levels)")
    # The "**NQ**: {{SESSION_NQ}}" line is what the LLM fills.
    assert "**NQ**:" in template
    assert "**ES**:" in template


# ── render_open_summary ─────────────────────────────────────────────


def test_open_renders_pipeline_keyed_tickers_dict():
    """The new JSON contract: `tickers: {NQ: {...}, ES: {...}}`."""
    template = build_open_static_template(_fake_briefing(), "(levels)")
    analysis = {
        "overnight_delta": "Bias stayed bullish",
        "dynamic": "Clean structure",
        "tickers": {
            "NQ": {"regime": "TRENDING", "logic": "trend continuation",
                   "entry": "17500.0", "stop": "17450.0", "stop_dist": "50.0",
                   "contracts": "2", "target": "17700.0", "rr": "4.0"},
            "ES": {"regime": "PINNED", "logic": "fade the wall",
                   "entry": "5000.0", "stop": "5010.0", "stop_dist": "10.0",
                   "contracts": "3", "target": "4960.0", "rr": "4.0"},
        },
        "risk_summary": {"line_1": "ES: $150 | NQ: $200",
                         "line_2": "Combined: $200",
                         "line_3": "Daily stop remaining: ES $300 | NQ $250"},
    }
    out = render_open_summary(template, analysis)

    assert "17500.0" in out
    assert "trend continuation" in out
    assert "5000.0" in out
    assert "fade the wall" in out
    assert "ES: $150" in out
    # Per-instrument trade block must be fully filled.
    nq_block = out.split("**NQ**", 1)[1].split("**ES**", 1)[0]
    es_block = out.split("**ES**", 1)[1].split("### Risk Summary", 1)[0]
    assert "N/A" not in nq_block
    assert "N/A" not in es_block


def test_open_legacy_mes_mnq_keys_still_work():
    """Backward compat: legacy `mes` / `mnq` flat keys still fill the
    pipeline slots."""
    template = build_open_static_template(_fake_briefing(), "(levels)")
    analysis = {
        "overnight_delta": "x",
        "dynamic": "y",
        "mes": {"regime": "PINNED", "logic": "fade",
                "entry": "5000.0", "stop": "5010.0", "stop_dist": "10.0",
                "contracts": "3", "target": "4960.0", "rr": "4.0"},
        "mnq": {"regime": "TRENDING", "logic": "trend",
                "entry": "17500.0", "stop": "17450.0", "stop_dist": "50.0",
                "contracts": "2", "target": "17700.0", "rr": "4.0"},
    }
    out = render_open_summary(template, analysis)
    # Pipeline slots are filled from the micro keys (fallback path).
    assert "17500.0" in out
    assert "5000.0" in out


def test_open_new_ticker_renders_without_code_changes():
    """Simulate adding YM1 (pipeline YM, micro MYM)."""
    original = dn.NARRATIVE_INSTRUMENT_MAP
    try:
        dn.NARRATIVE_INSTRUMENT_MAP = {
            "NQ1": {"pipeline": "NQ", "micro": "MNQ", "description": "Nasdaq-100"},
            "ES1": {"pipeline": "ES", "micro": "MES", "description": "S&P 500"},
            "YM1": {"pipeline": "YM", "micro": "MYM", "description": "Dow"},
        }
        briefing = {
            "meta": {"date": "2026-07-14"},
            "tickers": [
                {"ticker": t, "regime_check": {"current_regime": "TRENDING"},
                 "weekly_anchor": {"mandated_track": "A"}}
                for t in ["NQ1", "ES1", "YM1"]
            ],
        }
        template = build_open_static_template(briefing, "(levels)", tickers=["NQ1", "ES1", "YM1"])
        analysis = {
            "overnight_delta": "x", "dynamic": "y",
            "tickers": {
                "NQ": {"regime": "TRENDING", "entry": "17500.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
                "ES": {"regime": "PINNED", "entry": "5000.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
                "YM": {"regime": "TRENDING", "entry": "40000.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
            },
        }
        out = render_open_summary(template, analysis, tickers=["NQ1", "ES1", "YM1"])
        # All three pipeline labels render with their data.
        assert "17500.0" in out
        assert "5000.0" in out
        assert "40000.0" in out
        # Slot names use pipeline label.
        assert "YM" in out
    finally:
        dn.NARRATIVE_INSTRUMENT_MAP = original


def test_open_missing_ticker_payload_yields_na_not_crash():
    template = build_open_static_template(_fake_briefing(), "(levels)")
    analysis = {"overnight_delta": "x", "dynamic": "y"}
    out = render_open_summary(template, analysis)
    assert isinstance(out, str)


# ── render_eod_summary ──────────────────────────────────────────────


def test_eod_renders_tomorrow_dict_and_pipeline_session_log():
    """New contract: `tomorrow: {NQ: {...}, ES: {...}}` and
    `session_log: {NQ: ..., ES: ..., daily_pnl: ...}`."""
    template = build_eod_static_template(_fake_briefing(), "(levels)")
    analysis = {
        "session_log": {
            "NQ": "Win",
            "ES": "Loss",
            "daily_pnl": "ES $-50 | NQ $+200",
        },
        "drawdown_analysis": "Healthy",
        "level_accuracy_review": "Walls held",
        "trade_quality": "Good",
        "note_of_day": "Patience",
        "overnight_considerations": "Watch China",
        "tomorrow": {
            "NQ": {"regime": "TRENDING", "logic": "l1",
                   "entry": "17500.0", "stop": "17450.0", "stop_dist": "50.0",
                   "contracts": "2", "target": "17700.0", "rr": "4.0"},
            "ES": {"regime": "PINNED", "logic": "l2",
                   "entry": "5000.0", "stop": "5010.0", "stop_dist": "10.0",
                   "contracts": "3", "target": "4960.0", "rr": "4.0"},
        },
        "tomorrow_risk_budget": {"line_1": "ES: $150 | NQ: $200",
                                  "line_2": "Daily stop remaining: ES $300 | NQ $250"},
    }
    out = render_eod_summary(template, analysis)
    assert "Win" in out
    assert "Loss" in out
    assert "17500.0" in out
    assert "5000.0" in out
    assert "ES: $150" in out


def test_eod_legacy_tomorrow_mes_mnq_and_lowercase_session_log_still_work():
    template = build_eod_static_template(_fake_briefing(), "(levels)")
    analysis = {
        "session_log": {
            "mes": "Loss",
            "mnq": "Win",
            "daily_pnl": "x",
        },
        "tomorrow_mes": {"regime": "PINNED", "entry": "5000.0",
                         "logic": "x", "stop": "s", "stop_dist": "d",
                         "contracts": "c", "target": "t", "rr": "r"},
        "tomorrow_mnq": {"regime": "TRENDING", "entry": "17500.0",
                         "logic": "x", "stop": "s", "stop_dist": "d",
                         "contracts": "c", "target": "t", "rr": "r"},
    }
    out = render_eod_summary(template, analysis)
    assert "5000.0" in out
    assert "17500.0" in out
    assert "Loss" in out
    assert "Win" in out


def test_eod_new_ticker_renders_without_code_changes():
    original = dn.NARRATIVE_INSTRUMENT_MAP
    try:
        dn.NARRATIVE_INSTRUMENT_MAP = {
            "NQ1": {"pipeline": "NQ", "micro": "MNQ", "description": "Nasdaq-100"},
            "ES1": {"pipeline": "ES", "micro": "MES", "description": "S&P 500"},
            "YM1": {"pipeline": "YM", "micro": "MYM", "description": "Dow"},
        }
        briefing = {
            "meta": {"date": "2026-07-14"},
            "tickers": [
                {"ticker": t, "regime_check": {"current_regime": "TRENDING"}}
                for t in ["NQ1", "ES1", "YM1"]
            ],
        }
        template = build_eod_static_template(briefing, "(levels)", tickers=["NQ1", "ES1", "YM1"])
        analysis = {
            "session_log": {"NQ": "a", "ES": "b", "YM": "c", "daily_pnl": "d"},
            "tomorrow": {
                "NQ": {"regime": "x", "entry": "17500.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
                "ES": {"regime": "x", "entry": "5000.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
                "YM": {"regime": "x", "entry": "40000.0",
                       "logic": "x", "stop": "s", "stop_dist": "d",
                       "contracts": "c", "target": "t", "rr": "r"},
            },
        }
        out = render_eod_summary(template, analysis, tickers=["NQ1", "ES1", "YM1"])
        assert "17500.0" in out
        assert "5000.0" in out
        assert "40000.0" in out
    finally:
        dn.NARRATIVE_INSTRUMENT_MAP = original


def test_eod_missing_payload_yields_na_not_crash():
    template = build_eod_static_template(_fake_briefing(), "(levels)")
    out = render_eod_summary(template, {})
    assert isinstance(out, str)
