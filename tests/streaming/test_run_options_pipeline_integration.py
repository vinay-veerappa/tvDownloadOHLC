from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

from scripts.streaming.options import run_options_levels as rol


@dataclass
class _FakeContract:
    expiry: date
    open_interest: int = 10


@dataclass
class _FakeChain:
    calls: list[_FakeContract]
    puts: list[_FakeContract]
    contracts: list[_FakeContract]
    spot_price: float = 100.0
    spot_open: float = 99.5


def _patch_pipeline_basics(monkeypatch) -> dict[str, list]:
    today = date.today()
    contract = _FakeContract(expiry=today + timedelta(days=2), open_interest=25)
    chain = _FakeChain(calls=[contract], puts=[contract], contracts=[contract, contract])

    captured: dict[str, list] = {
        "write_unified_txt": [],
        "write_unified_json": [],
        "send_discord": [],
    }

    monkeypatch.setattr(rol, "create_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(rol, "load_basis_anchors", lambda: {})
    monkeypatch.setattr(rol, "save_basis_anchors", lambda anchors: None)
    monkeypatch.setattr(rol, "fetch_option_chain_data", lambda *args, **kwargs: chain)
    monkeypatch.setattr(rol, "fetch_futures_quote", lambda *args, **kwargs: None)
    monkeypatch.setattr(rol, "_chain_has_actionable_oi", lambda _chain: True)
    monkeypatch.setattr(rol, "calculate_price_metrics", lambda _chain: {})
    monkeypatch.setattr(rol, "replace", lambda obj, **kwargs: obj)
    
    # Force HybridCoordinator to return None to avoid picking up live host RTD prices during test runs
    monkeypatch.setattr(rol.HybridCoordinator, "start", lambda self: None)
    monkeypatch.setattr(rol.HybridCoordinator, "stop", lambda self: None)
    monkeypatch.setattr(rol.HybridCoordinator, "get_futures_price", lambda self, symbol, schwab_price=None: None)
    
    # Mock a complete DealerLevels structure to prevent AttributeError if translate_to_futures is called
    monkeypatch.setattr(
        rol, 
        "calculate_dealer_levels", 
        lambda _chain, ticker, *args, **kwargs: SimpleNamespace(
            ticker=ticker,
            spot=100.0,
            total_gex=0.0,
            gex_regime="POSITIVE",
            zero_gamma=100.0,
            gamma_flip_lower=100.0,
            gamma_flip_upper=100.0,
            call_wall=100.0,
            put_wall=100.0,
            secondary_call_wall=100.0,
            secondary_put_wall=100.0,
            local_call_node=100.0,
            local_put_node=100.0,
            call_wall_0dte=100.0,
            put_wall_0dte=100.0,
            hedge_wall=100.0,
            max_pain=100.0,
            em_upper=100.0,
            em_lower=100.0,
            em_value=0.0,
            atm_straddle=0.0,
            vol_trigger_upper_05=100.0,
            vol_trigger_lower_05=100.0,
            vol_trigger_upper_10=100.0,
            vol_trigger_lower_10=100.0,
            gamma_magnet=100.0,
            zero_gamma_delta_adj=100.0,
        )
    )
    monkeypatch.setattr(
        rol,
        "score_levels",
        lambda levels, chain_data, ticker, profile, view: SimpleNamespace(
            ticker=ticker,
            tagged_levels=[],
            view_mode=getattr(view, "name", "view"),
            regime="POSITIVE",
            bias="NEUTRAL",
        ),
    )
    monkeypatch.setattr(rol, "write_scored_levels_txt", lambda *args, **kwargs: None)
    monkeypatch.setattr(rol, "write_levels", lambda *args, **kwargs: None)
    monkeypatch.setattr(rol, "_is_rth", lambda: False)
    monkeypatch.setattr(rol, "_discord_window_allowed", lambda *args, **kwargs: True)

    monkeypatch.setattr(
        rol,
        "write_unified_levels_txt",
        lambda *args, **kwargs: captured["write_unified_txt"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        rol,
        "write_unified_levels_json",
        lambda *args, **kwargs: captured["write_unified_json"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        rol,
        "unified_payload_fingerprint",
        lambda path: {"exists": True, "bytes": 10, "lines": 1, "sha256": "abc"},
    )

    monkeypatch.setattr(rol, "load_previous_state", lambda: {})
    monkeypatch.setattr(rol, "build_current_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(rol, "detect_changes", lambda *args, **kwargs: [])
    monkeypatch.setattr(rol, "save_current_state", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        rol,
        "send_discord_update",
        lambda *args, **kwargs: captured["send_discord"].append((args, kwargs)),
    )
    monkeypatch.setattr(rol, "send_regime_change_alert", lambda *args, **kwargs: None)

    return captured


def test_run_pipeline_wires_unified_outputs_and_discord_source(monkeypatch) -> None:
    captured = _patch_pipeline_basics(monkeypatch)
    monkeypatch.setattr(rol, "ENABLE_UNIFIED_CONTRACT_OUTPUTS", True)

    rol.run_pipeline(
        tickers=["SPY"],
        run_label="INTEG",
        enable_discord=True,
        discord_target_key="test_channel",
    )

    assert captured["write_unified_txt"]
    assert captured["write_unified_json"]

    _, txt_kwargs = captured["write_unified_txt"][0]
    _, json_kwargs = captured["write_unified_json"][0]

    assert "macro_scored_levels" in txt_kwargs
    assert "macro_spot_by_ticker" in txt_kwargs
    assert txt_kwargs["macro_spot_by_ticker"].get("SPY") == 100.0
    assert "macro_scored_levels" in json_kwargs
    assert "macro_spot_by_ticker" in json_kwargs

    assert captured["send_discord"]
    _, discord_kwargs = captured["send_discord"][0]
    assert discord_kwargs["unified_copy_path"] == rol.UNIFIED_LEVELS_TXT
    assert discord_kwargs["webhook_key"] == "test_channel"


def test_run_pipeline_disables_unified_source_when_flag_off(monkeypatch) -> None:
    captured = _patch_pipeline_basics(monkeypatch)
    monkeypatch.setattr(rol, "ENABLE_UNIFIED_CONTRACT_OUTPUTS", False)

    rol.run_pipeline(
        tickers=["SPY"],
        run_label="INTEG_OFF",
        enable_discord=True,
        discord_target_key="test_channel",
    )

    assert not captured["write_unified_txt"]
    assert not captured["write_unified_json"]

    assert captured["send_discord"]
    _, discord_kwargs = captured["send_discord"][0]
    assert discord_kwargs["unified_copy_path"] is None
    assert discord_kwargs["webhook_key"] == "test_channel"
