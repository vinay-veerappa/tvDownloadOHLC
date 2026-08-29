"""Pytest suite for LiveStorageResolver."""

from pathlib import Path
import pytest
from scripts.utils.live_storage_resolver import TICKER_MAP, get_live_storage_path


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
