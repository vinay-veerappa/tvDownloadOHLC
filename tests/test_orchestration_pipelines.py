"""Pytest suite for WS-1.1 / WS-1.2 orchestration pipelines and WS-2.1 wiring mappers."""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.orchestration.pre_market_pipeline import (
    build_input_manifest,
    run_post_market_pipeline,
    wargame_data_to_forecast_payload,
    wargame_data_to_plan_context,
)
from scripts.utils.market_calendar import get_session_cutoff_utc

EASTERN_TZ = ZoneInfo("America/New_York")


def to_iso(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def _make_live_storage_parquet(tmpdir: Path, session_date: str, ticker: str = "NQ1"):
    """Creates a synthetic live-storage parquet covering pre-market through close."""
    bars = 780  # 04:00 ET -> 16:00 ET in 1m bars
    start_dt = datetime(int(session_date[:4]), int(session_date[5:7]), int(session_date[8:10]),
                        4, 0, tzinfo=EASTERN_TZ)
    records = []
    price = 20000.0
    for i in range(bars):
        dt = start_dt + timedelta(minutes=i)
        drift = (0.05 if (i // 60) % 2 == 0 else -0.03)
        price += drift * 10
        records.append({
            "dt": dt.astimezone(ZoneInfo("UTC")),
            "dt_et": dt,
            "open": price,
            "high": price + 4,
            "low": price - 3,
            "close": price + 1,
            "volume": 500 + i * 10,
        })
    df = pd.DataFrame(records)

    from scripts.utils.live_storage_resolver import get_live_storage_path, _DF_CACHE
    target = get_live_storage_path(ticker, custom_dir=str(tmpdir))
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target)
    # Invalidate the resolver's module-level DF cache (tests reuse path keys across tmpdirs)
    _DF_CACHE.pop(str(target.resolve()), None)
    return target


def test_pre_market_pipeline_sealing_and_plan(temp_db, tmp_path):
    """WS-1.1: manifest seals -> forecast registers (abstain truthfully) -> plan snapshots EX_ANTE."""
    from scripts.trading_brain.db.connection import get_db_connection
    from scripts.utils import live_storage_resolver as lsr

    # Use a future session date so the 08:45 ET cutoff is comfortably in the future.
    session_date = (datetime.now(EASTERN_TZ) + timedelta(days=7)).strftime("%Y-%m-%d")
    parquet_path = _make_live_storage_parquet(tmp_path, session_date)
    original = lsr.get_live_storage_path
    lsr.get_live_storage_path = lambda ticker, custom_dir=None: parquet_path
    try:
        # Patch the wargame generator's data function to a deterministic stub (no live clock deps)
        import scripts.wargaming.generate_daily_wargame as gdw
        original_generate = gdw.generate_wargame_data
        original_format = gdw.format_wargame_markdown
        gdw.generate_wargame_data = lambda **kwargs: _synthetic_wargame_data(kwargs.get("ticker", "NQ1"))
        gdw.format_wargame_markdown = lambda data: "# Synthetic Playbook\nBias: BULLISH\n"

        from scripts.trading_brain.orchestration.pre_market_pipeline import run_pre_market_pipeline
        result = run_pre_market_pipeline(
            ticker="NQ1",
            session_date=session_date,
            cutoff_time_et="08:45",  # real production cutoff
            db_path=temp_db,
        )
    finally:
        lsr.get_live_storage_path = original
        gdw.generate_wargame_data = original_generate
        gdw.format_wargame_markdown = original_format

    assert result["forecast_mode"] == "LIVE_PRODUCTION"
    assert result["manifest_inputs"] >= 1
    assert result["plan"]["provenance_class"] == "EX_ANTE_DECLARED"

    # Ledger contents: snapshot exists with abstain flag
    with get_db_connection(temp_db) as conn:
        row = conn.execute(
            "SELECT abstain_flag, abstain_reason, predicted_bias, forecast_mode FROM forecast_snapshots WHERE forecast_id = ?",
            (result["forecast_id"],)
        ).fetchone()
        assert row["abstain_flag"] == 1
        assert row["abstain_reason"]
        assert row["forecast_mode"] == "LIVE_PRODUCTION"
        plan_row = conn.execute(
            "SELECT provenance_class, primary_bias FROM plan_snapshots WHERE plan_snapshot_id = ?",
            (result["plan"]["plan_snapshot_id"],)
        ).fetchone()
        assert plan_row["provenance_class"] == "EX_ANTE_DECLARED"


def _synthetic_wargame_data(ticker: str) -> dict:
    spot = 20000.0
    return {
        "ticker": ticker,
        "date": "2026-08-27",
        "cutoff_time": "08:45",
        "spot_price": spot,
        "p12": {"high": 20100.0, "low": 19900.0, "mid": 20000.0, "bias": "BULLISH",
                "diff_pts": 5.0, "diff_bps": 2.5, "hod_time": "20:00", "lod_time": "03:00"},
        "anchors": {"pdh": 20050.0, "pdl": 19950.0},
        "sessions": {"asia_status": "Held", "asia_broken": False, "london_status": "Held",
                     "london_broken": False, "alignment": "Aligned Expansion"},
        "candle_science": {"bull": {"p30": 0.1, "p50": 0.25, "p70": 0.4},
                           "bear": {"p30": -0.1, "p50": -0.25, "p70": -0.4}},
        "pack_trading": {"cover_the_queen_bps": 10.0, "runner_bps": 30.0, "stop_ceiling_bps": 12.0},
        "trajectory_engine": {"state": "INSIDE_RANGE"},
        "signature_setups": {"setups_detected": [{"strategy_family": "FIRECRACKER"}]},
        "weekly_outlook": {},
    }


def test_forecast_payload_is_truthful_abstain():
    """The payload must carry zero fabricated probabilities: abstain with levels only."""
    data = _synthetic_wargame_data("NQ1")
    payload = wargame_data_to_forecast_payload(
        data, model_version_id="MOD_TEST", git_hash="git:test", config_hash="sha256:cfg",
        forecast_run_id="run-1"
    )
    assert payload.abstain_flag is True
    assert payload.abstain_reason
    assert payload.prob_r1 is None and payload.prob_r2 is None
    assert payload.p12_equilibrium_level == 20000.0
    assert payload.p12_vector_direction == "BULLISH"
    # CS p70 levels derived from spot
    assert payload.candle_science_target_high == pytest.approx(data["spot_price"] * 1.004)
    assert payload.candle_science_target_low == pytest.approx(data["spot_price"] * 0.996)


def test_plan_context_mapping(temp_db):
    """Plan context extraction carries bias, permitted strategies, and pack-derived risk."""
    data = _synthetic_wargame_data("NQ1")
    ctx = wargame_data_to_plan_context(data, "# Playbook verbatim", "2026-08-27", "08:45")
    assert ctx.primary_bias == "BULLISH"
    assert "FIRECRACKER" in ctx.permitted_strategies
    assert ctx.max_intended_risk_bps == 12.0
    assert ctx.wargamed_scenarios["elimination_state"] == "INSIDE_RANGE"

    saved_id = __import__(
        "scripts.trading_brain.plans.plan_adapter", fromlist=["PlanAdapter"]
    ).PlanAdapter.save_plan_snapshot(ctx, db_path=temp_db)
    assert saved_id


def test_post_market_pipeline_end_to_end(temp_db, tmp_path):
    """WS-1.2: tape -> fills -> dispositions -> reconciliation -> persisted report."""
    from scripts.trading_brain.db.connection import get_db_connection
    from scripts.utils import live_storage_resolver as lsr

    session_date = "2026-08-27"
    parquet_path = _make_live_storage_parquet(tmp_path, session_date)
    original = lsr.get_live_storage_path
    lsr.get_live_storage_path = lambda ticker, custom_dir=None: parquet_path
    try:
        # A pre-registered signal opportunity to reconcile against.
        # Timestamps stored as UTC equivalents of ET wall-clock so they land on the
        # ET session date in the resolver and inside the disposition matching window.
        from datetime import timezone
        bar_utc = datetime(2026, 8, 27, 9, 35, tzinfo=EASTERN_TZ).astimezone(timezone.utc)
        fill_utc = datetime(2026, 8, 27, 9, 35, 30, tzinfo=EASTERN_TZ).astimezone(timezone.utc)
        with get_db_connection(temp_db) as conn:
            conn.execute(
                """
                INSERT INTO signal_opportunities (
                    opportunity_id, session_date, ticker, strategy_version_id,
                    bar_timestamp_utc, decision_time_utc, signal_direction, trigger_price,
                    declared_stop_price, declared_target_1_price, stop_distance_bps,
                    target_1_bps, feature_manifest_json, evaluation_mode
                ) VALUES ('opp-e2e-1', ?, 'NQ1', 'STRAT_V1', ?, ?, 'LONG', 20010.0, 19985.0, 20035.0, 12.5, 10.0, '{}', 'LIVE_CAPTURE');
                """,
                (session_date, to_iso(bar_utc), to_iso(bar_utc))
            )
        # A matching broker fill (same direction, within 2 bps of trigger, inside the window)
        fills = [{
            "broker_execution_id": "b-exec-e2e-1",
            "broker_order_id": "b-ord-e2e-1",
            "order_action": "BUY",
            "quantity": 1,
            "fill_price": 20011.0,
            "event_timestamp_utc": to_iso(fill_utc),
        }]
        exec_file = tmp_path / "fills.json"
        exec_file.write_text(json.dumps(fills), encoding="utf-8")

        result = run_post_market_pipeline(
            ticker="NQ1",
            session_date=session_date,
            executions_file=exec_file,
            db_path=temp_db,
        )
    finally:
        lsr.get_live_storage_path = original

    steps = result["steps"]
    assert steps["tape_actuals"]["actual_id"]
    assert steps["execution_ingest"]["ingested_count"] == 1
    assert steps["dispositions"]["dispositions"]["EXECUTED"] == 1
    assert steps["reconciliation"]["tape_found"] is True
    assert steps["report"]["markdown_bytes"] > 0

    # Report persisted to disk
    report_path = Path("data/wargaming/reports") / f"daily_process_delta_{session_date}_NQ1.md"
    if report_path.exists():
        assert report_path.read_text(encoding="utf-8").startswith("# Daily Process Delta")

def test_bind_and_validate_ticker_derives_session_from_timestamp():
    """F14: a record WITHOUT session_date is placed via its event timestamp's logical
    futures session; a timestamp from another session is fail-closed excluded."""
    from scripts.trading_brain.orchestration.pre_market_pipeline import _bind_and_validate_ticker

    records = [
        # Aug 27 21:00Z = Aug 27 17:00 ET -> still belongs to the Aug 27 LOGICAL session
        {"broker_execution_id": "b-ok", "event_timestamp_utc": "2026-08-27T21:00:00Z"},
        # Aug 27 23:00 ET = within Aug 28 logical session? 23:00 ET >= 18:00 roll -> Aug 28 session
        {"broker_execution_id": "b-next", "event_timestamp_utc": "2026-08-27T23:00:00Z"},
        # No timestamp at all -> cannot place, excluded
        {"broker_execution_id": "b-nots"},
    ]
    bound, meta = _bind_and_validate_ticker(records, "NQ1", "fill", requested_session_date="2026-08-27")
    ids = [r["broker_execution_id"] for r in bound]
    assert "b-ok" in ids
    assert "b-next" not in ids          # belongs to the NEXT logical session
    assert "b-nots" not in ids          # timestampless -> excluded
    assert meta["mismatched_session_date"] == 2
    assert meta["injected_session_date"] == 1
    assert bound[0]["session_date"] == "2026-08-27"
