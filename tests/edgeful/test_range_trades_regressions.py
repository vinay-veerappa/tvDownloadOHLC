import pandas as pd

from scripts.ranges import compute_trades as ct


def test_compute_trades_writes_no_entry_when_range_end_missing(monkeypatch, tmp_path):
    rr = pd.DataFrame(
        [
            {
                "symbol": "NQ1",
                "range_name": "LUNCH",
                "strategy_name": "BO_1X",
                "trading_date": "2026-01-02",
                "range_high": 100.0,
                "range_low": 99.0,
                "range_mid": 99.5,
                "range_width": 1.0,
            }
        ]
    )

    rr_path = tmp_path / "range_records.parquet"
    rr.to_parquet(rr_path)

    bars = pd.DataFrame(
        {
            "open": [100.0],
            "high": [100.1],
            "low": [99.9],
            "close": [100.0],
            "volume": [1000],
            "trading_date": ["2026-01-02"],
        },
        index=pd.to_datetime(["2026-01-02 13:00:00"]),
    )

    monkeypatch.setattr(ct, "_RANGE_PATH", rr_path)
    monkeypatch.setattr(ct, "_load_symbol_bars", lambda _s, _a, _b: bars)
    monkeypatch.setattr(ct, "_get_post_bars_for_trade", lambda _d, _r: (pd.DataFrame(), None))

    out = ct.compute_trades(
        symbols=["NQ1"],
        ranges=["LUNCH"],
        strategies=["BO_1X"],
        start=None,
        end=None,
    )

    assert not out.empty
    assert len(out) == 1
    assert bool(out.iloc[0]["entry_triggered"]) is False
