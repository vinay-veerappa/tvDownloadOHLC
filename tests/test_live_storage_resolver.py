"""Pytest suite for LiveStorageResolver."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from scripts.utils.live_storage_resolver import (
    TICKER_MAP,
    get_live_storage_path,
    get_session_slice_manifest,
    load_session_bars_as_of_cutoff,
)


def test_resolver_mappings():
    """Tests that all standard futures and equity aliases resolve to their correct parquet files."""
    assert get_live_storage_path("NQ1").name == "live_storage_-NQ.parquet"
    assert get_live_storage_path("-NQ").name == "live_storage_-NQ.parquet"
    assert get_live_storage_path("ES1").name == "live_storage_-ES.parquet"
    assert get_live_storage_path("-ES").name == "live_storage_-ES.parquet"
    assert get_live_storage_path("YM1").name == "live_storage_-YM.parquet"
    assert get_live_storage_path("RTY1").name == "live_storage_-RTY.parquet"
    assert get_live_storage_path("GC1").name == "live_storage_-GC.parquet"
    assert get_live_storage_path("CL1").name == "live_storage_-CL.parquet"
    assert get_live_storage_path("AAPL").name == "live_storage_AAPL.parquet"
    assert get_live_storage_path("NVDA").name == "live_storage_NVDA.parquet"


def _make_parquet(tmp_path, session_date: str):
    start_dt = datetime(int(session_date[:4]), int(session_date[5:7]), int(session_date[8:10]), 9, 30, tzinfo=timezone.utc)
    records = []
    price = 20000.0
    for i in range(390):
        dt = pd.Timestamp(start_dt) + pd.Timedelta(minutes=i)
        price += 0.05
        records.append({
            "dt": dt,
            "open": price,
            "high": price + 4,
            "low": price - 3,
            "close": price + 1,
            "volume": 500 + i * 10,
        })
    df = pd.DataFrame(records)
    target = tmp_path / "live_storage_-NQ.parquet"
    df.to_parquet(target)
    return target


def test_slice_manifest_hashes_actual_rows_and_derives_max_timestamp(tmp_path):
    session_date = "2026-08-28"
    _make_parquet(tmp_path, session_date)
    cutoff = pd.Timestamp(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    manifest = get_session_slice_manifest("NQ1", session_date, cutoff, custom_dir=tmp_path)
    assert manifest["provider_name"] == "LIVE_STORAGE_1M"
    assert manifest["max_timestamp_utc"] == "2026-08-28T12:00:00Z"
    assert manifest["row_count"] == 151  # 09:30 to 12:00 inclusive
    assert manifest["content_hash"].startswith("sha256:")


def test_slice_manifest_changes_when_bars_added(tmp_path):
    session_date = "2026-08-28"
    _make_parquet(tmp_path, session_date)
    cutoff = pd.Timestamp(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    h1 = get_session_slice_manifest("NQ1", session_date, cutoff, custom_dir=tmp_path)["content_hash"]

    # Extend with an extra pre-market bar before cutoff (not in the original 09:30-15:59 set)
    extra = pd.DataFrame([{
        "dt": pd.Timestamp(datetime(2026, 8, 28, 8, 30, tzinfo=timezone.utc)),
        "open": 21000.0, "high": 21004.0, "low": 20997.0, "close": 21001.0, "volume": 999
    }])
    path = tmp_path / "live_storage_-NQ.parquet"
    df = pd.read_parquet(path)
    df = pd.concat([df, extra], ignore_index=True).drop_duplicates(subset=["dt"]).sort_values("dt")
    df.to_parquet(path)
    from scripts.utils.live_storage_resolver import _DF_CACHE
    _DF_CACHE.pop(str(path.resolve()), None)

    h2 = get_session_slice_manifest("NQ1", session_date, cutoff, custom_dir=tmp_path)["content_hash"]
    assert h1 != h2
    assert get_session_slice_manifest("NQ1", session_date, cutoff, custom_dir=tmp_path)["row_count"] == 152


def test_load_session_bars_as_of_cutoff(tmp_path):
    session_date = "2026-08-28"
    _make_parquet(tmp_path, session_date)
    cutoff = pd.Timestamp(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    df = load_session_bars_as_of_cutoff("NQ1", session_date, cutoff, custom_dir=tmp_path)
    assert df["dt"].max() <= cutoff
    assert len(df) == 151


def test_manifest_includes_prior_evening_leg_of_logical_session(tmp_path):
    """F4 regression: the sealed manifest slices the LOGICAL futures session - the
    prior-evening Globex bar (previous ET calendar day) must be inside the hash."""
    from datetime import datetime as _dt, timezone as _tz
    import pandas as _pd
    from scripts.utils.live_storage_resolver import _DF_CACHE

    records = [
        # Prior-evening leg: Aug 27 20:00 ET = Aug 28 00:00Z (~midnight UTC Aug 28)
        {"dt": _pd.Timestamp(_dt(2026, 8, 28, 0, 0, tzinfo=_tz.utc)),
         "open": 20000.0, "high": 20004.0, "low": 19997.0, "close": 20001.0, "volume": 100},
        # RTH leg: Aug 28 09:30 ET = 13:30Z
        {"dt": _pd.Timestamp(_dt(2026, 8, 28, 13, 30, tzinfo=_tz.utc)),
         "open": 20010.0, "high": 20014.0, "low": 20007.0, "close": 20011.0, "volume": 100},
    ]
    _pd.DataFrame(records).to_parquet(tmp_path / "live_storage_-NQ.parquet")

    cutoff = _pd.Timestamp(_dt(2026, 8, 28, 14, 0, tzinfo=_tz.utc))
    manifest = get_session_slice_manifest("NQ1", "2026-08-28", cutoff, custom_dir=tmp_path)
    # Both the prior-evening bar AND the RTH bar are inside the sealed slice.
    assert manifest["row_count"] == 2
    assert manifest["max_timestamp_utc"] == "2026-08-28T13:30:00Z"
