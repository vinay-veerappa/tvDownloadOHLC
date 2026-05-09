from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.streaming.options import discord_notifier, file_writer, level_scorer
from scripts.streaming.options.config import INTRADAY_VIEW
from scripts.streaming.options.level_scorer import StructuralAnchor, MechanicalWall, InflectionPoint


def test_sidecar_path_is_deterministic() -> None:
    base = file_writer.DAILY_LEVELS_TXT

    versioned = file_writer._sidecar_path(base, "versioned")
    snapshot = file_writer._sidecar_path(base, "pulse")

    assert versioned.name.endswith("_versioned.txt")
    assert snapshot.name.endswith("_pulse.txt")
    assert "20" not in versioned.name
    assert "20" not in snapshot.name


def test_copy_block_payloads_are_raw_and_chunked(monkeypatch) -> None:
    monkeypatch.setattr(discord_notifier, "futures_tag", lambda symbol: symbol)
    monkeypatch.setattr(
        discord_notifier,
        "copy_ready_line",
        lambda ticker, levels: f"{ticker}:RAW:{getattr(levels, 'marker', 'x')}",
    )

    translated = [SimpleNamespace(futures_symbol="ES", marker="a")]
    cash_levels = [SimpleNamespace(ticker=f"T{i}", marker="b" * 500) for i in range(5)]

    payloads = discord_notifier._copy_block_payloads(translated, "RUN", cash_levels=cash_levels)

    assert payloads
    assert all("```" not in payload["content"] for payload in payloads)
    assert all("Dealer Levels" not in payload["content"] for payload in payloads)
    assert all(payload["content"].strip() for payload in payloads)
    assert "ES:RAW:a" in payloads[0]["content"]
    assert any("T4:RAW" in payload["content"] for payload in payloads)


def test_copy_attachment_payload_is_text_file() -> None:
    payload, files = discord_notifier._copy_attachment_payload(["SPY:1:A|P|L", "QQQ:2:W|S|L"], "RUN")

    assert "attached as text file" in payload["content"]
    assert "file" in files
    name, data, mime = files["file"]
    assert name.endswith(".txt")
    assert b"SPY:1:A|P|L" in data
    assert mime == "text/plain"


def test_write_scored_levels_respects_max_visible_dte(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            StructuralAnchor(
                strike=100.0,
                label="Anchor Near",
                significance="PRIMARY",
                side="CALL",
                matched_program="",
                oi_zscore=2.0,
                days_to_expiry=5,
            ),
            StructuralAnchor(
                strike=110.0,
                label="Anchor Far",
                significance="PRIMARY",
                side="PUT",
                matched_program="",
                oi_zscore=2.0,
                days_to_expiry=30,
            ),
            MechanicalWall(
                strike=120.0,
                label="Wall",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
        ]
    )

    out = tmp_path / "scored.txt"
    file_writer.write_scored_levels_txt("SPY", scored, path=out, max_visible_dte_days=7)
    text = out.read_text(encoding="utf-8")

    assert "100.00" in text
    assert "120.00" in text
    assert "110.00" not in text


def test_write_scored_levels_suppresses_near_duplicates(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            MechanicalWall(
                strike=100.00,
                label="Wall 1",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
            MechanicalWall(
                strike=100.30,
                label="Wall 2",
                significance="SECONDARY",
                side="CALL",
                field_name="secondary_call_wall",
                pct_of_book=0.1,
            ),
        ]
    )

    out = tmp_path / "scored_dupes.txt"
    file_writer.write_scored_levels_txt("SPY", scored, path=out, near_duplicate_tolerance=0.5)
    text = out.read_text(encoding="utf-8")

    assert "100.00" in text
    assert "100.30" not in text


def test_write_scored_levels_em_scaled_tolerance_low_em_keeps_neighbor(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            MechanicalWall(
                strike=100.00,
                label="Wall 1",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
            MechanicalWall(
                strike=100.40,
                label="Wall 2",
                significance="SECONDARY",
                side="CALL",
                field_name="secondary_call_wall",
                pct_of_book=0.1,
            ),
        ],
        expected_moves=[
            SimpleNamespace(dte=1, em_value=0.55, em_upper=110.55, em_lower=109.45),
        ],
    )

    out = tmp_path / "scored_low_em.txt"
    # For SPY base tolerance is 0.5. Low EM scales down (clamped min 0.6 => 0.3), so 0.4 gap should remain.
    file_writer.write_scored_levels_txt("SPY", scored, path=out)
    text = out.read_text(encoding="utf-8")

    assert "100.00" in text
    assert "100.40" in text


def test_write_scored_levels_em_scaled_tolerance_high_em_suppresses_neighbor(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            MechanicalWall(
                strike=100.00,
                label="Wall 1",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
            MechanicalWall(
                strike=100.60,
                label="Wall 2",
                significance="SECONDARY",
                side="CALL",
                field_name="secondary_call_wall",
                pct_of_book=0.1,
            ),
        ],
        expected_moves=[
            SimpleNamespace(dte=1, em_value=3.3, em_upper=113.3, em_lower=106.7),
        ],
    )

    out = tmp_path / "scored_high_em.txt"
    # For SPY base tolerance is 0.5. High EM scales to 0.75, so 0.6 gap is suppressed.
    file_writer.write_scored_levels_txt("SPY", scored, path=out)
    text = out.read_text(encoding="utf-8")

    assert "100.00" in text
    assert "100.60" not in text


def test_write_scored_levels_keeps_flip_cliff_context_inflections(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            InflectionPoint(
                strike=101.0,
                label="Gamma Flip High",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_upper",
            ),
            InflectionPoint(
                strike=99.0,
                label="Gamma Flip Low",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_lower",
            ),
            InflectionPoint(
                strike=102.5,
                label="Gamma Cliff Up",
                significance="CONTEXT",
                side="CALL",
                inflection_type="CLIFF",
                field_name="gamma_cliff_up",
            ),
            InflectionPoint(
                strike=97.0,
                label="Gamma Cliff Down",
                significance="CONTEXT",
                side="PUT",
                inflection_type="CLIFF",
                field_name="gamma_cliff_down",
            ),
            InflectionPoint(
                strike=100.0,
                label="Gamma Magnet",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="MAGNET",
                field_name="gamma_magnet",
            ),
        ],
        expected_moves=[],
    )

    out = tmp_path / "scored_flip_cliff.txt"
    file_writer.write_scored_levels_txt("SPY", scored, path=out)
    text = out.read_text(encoding="utf-8")

    assert "FLIP UP" in text
    assert "FLIP DN" in text
    assert "CLIFF UP" in text
    assert "CLIFF DN" in text
    assert "MAGNET" not in text


def test_write_unified_levels_txt_includes_structural_tokens_from_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        file_writer,
        "copy_ready_line",
        lambda ticker, levels: (
            f"{ticker}: "
            "100.00:Upper EM, "
            "99.00:Gamma Magnet, "
            "98.00:Pin Strike, "
            "97.00:DEX Put Node, "
            "96.00:DEX Call Node, "
            "95.00:Local Put Node, "
            "94.00:Local Call Node, "
            "93.00:0DTE Put Wall, "
            "92.00:0DTE Call Wall, "
            "91.00:Max Pain, "
            "90.00:Hedge Wall, "
            "0:META_NOTE_Test"
        ),
    )

    scored = SimpleNamespace(
        ticker="SPX",
        tagged_levels=[
            MechanicalWall(
                strike=110.0,
                label="Wall",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
        ],
        expected_moves=[],
    )

    out = tmp_path / "unified_structural.txt"
    file_writer.write_unified_levels_txt(
        [scored],
        path=out,
        metadata_levels_by_ticker={"SPX": SimpleNamespace()},
    )
    text = out.read_text(encoding="utf-8")

    assert "99.00:I|C|MAGNET" in text
    assert "98.00:A|S|PIN" in text
    assert "97.00:W|S|DEX P" in text
    assert "96.00:W|S|DEX C" in text
    assert "95.00:W|S|LOC P" in text
    assert "94.00:W|S|LOC C" in text
    assert "93.00:W|S|0D PW" in text
    assert "92.00:W|S|0D CW" in text
    assert "91.00:A|S|MAX" in text
    assert "90.00:W|S|HW" in text


def test_write_scored_levels_keeps_flip_cliff_even_when_near_duplicates(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        tagged_levels=[
            InflectionPoint(
                strike=100.00,
                label="Zero Gamma",
                significance="SECONDARY",
                side="NEUTRAL",
                inflection_type="ZERO",
                field_name="zero_gamma",
            ),
            InflectionPoint(
                strike=100.10,
                label="Gamma Flip High",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_upper",
            ),
            InflectionPoint(
                strike=99.90,
                label="Gamma Flip Low",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_lower",
            ),
            InflectionPoint(
                strike=100.20,
                label="Gamma Cliff Up",
                significance="CONTEXT",
                side="CALL",
                inflection_type="CLIFF",
                field_name="gamma_cliff_up",
            ),
            InflectionPoint(
                strike=99.80,
                label="Gamma Cliff Down",
                significance="CONTEXT",
                side="PUT",
                inflection_type="CLIFF",
                field_name="gamma_cliff_down",
            ),
        ],
        expected_moves=[],
    )

    out = tmp_path / "scored_flip_cliff_near_dupes.txt"
    file_writer.write_scored_levels_txt(
        "SPY",
        scored,
        path=out,
        near_duplicate_tolerance=0.5,
    )
    text = out.read_text(encoding="utf-8")

    assert "ZERO GEX" in text
    assert "FLIP UP" in text
    assert "FLIP DN" in text
    assert "CLIFF UP" in text
    assert "CLIFF DN" in text


def test_score_levels_keeps_flip_cliff_context_when_intraday_mask_excludes_context(
    monkeypatch,
) -> None:
    monkeypatch.setattr(level_scorer, "_score_mechanical_walls", lambda *args, **kwargs: [])
    monkeypatch.setattr(level_scorer, "_detect_structural_anchors", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        level_scorer,
        "_find_inflection_points",
        lambda *args, **kwargs: [
            InflectionPoint(
                strike=100.10,
                label="Gamma Flip High",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_upper",
            ),
            InflectionPoint(
                strike=99.90,
                label="Gamma Flip Low",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="FLIP",
                field_name="gamma_flip_lower",
            ),
            InflectionPoint(
                strike=100.20,
                label="Gamma Cliff Up",
                significance="CONTEXT",
                side="CALL",
                inflection_type="CLIFF",
                field_name="gamma_cliff_up",
            ),
            InflectionPoint(
                strike=100.00,
                label="Gamma Magnet",
                significance="CONTEXT",
                side="NEUTRAL",
                inflection_type="MAGNET",
                field_name="gamma_magnet",
            ),
        ],
    )

    scored = level_scorer.score_levels(
        levels=SimpleNamespace(spot=100.0, directional_bias="NEUTRAL", gex_regime="POSITIVE"),
        chain=SimpleNamespace(),
        ticker="SPY",
        profile=SimpleNamespace(),
        view_mode=INTRADAY_VIEW,
    )
    fields = {tl.field_name for tl in scored.tagged_levels}

    assert "gamma_flip_upper" in fields
    assert "gamma_flip_lower" in fields
    assert "gamma_cliff_up" in fields
    assert "gamma_magnet" not in fields


def test_discord_output_prefers_attachment_mode(monkeypatch) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "futures_tag", lambda symbol: symbol)
    monkeypatch.setattr(discord_notifier, "copy_ready_line", lambda ticker, levels: f"{ticker}:1:A|P|TEST")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((payload, files)))
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", True)

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    discord_notifier.send_discord_update(translated, run_label="RUN")

    assert calls
    assert any(files is not None for _, files in calls)
    attachment_payload, attachment_files = next((p, f) for p, f in calls if f is not None)
    assert "attached as text file" in attachment_payload["content"]
    assert "file" in attachment_files


def test_discord_output_falls_back_to_raw_lines(monkeypatch) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "futures_tag", lambda symbol: symbol)
    monkeypatch.setattr(discord_notifier, "copy_ready_line", lambda ticker, levels: f"{ticker}:1:A|P|TEST")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((payload, files)))
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", False)

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    discord_notifier.send_discord_update(translated, run_label="RUN")

    assert calls
    first_payload, first_files = calls[0]
    assert first_files is None
    assert first_payload["content"].startswith("ES:1:A|P|TEST")


def test_discord_output_prefers_scored_unified_lines(monkeypatch) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((payload, files)))
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", False)
    monkeypatch.setattr(discord_notifier, "build_scored_levels_line", lambda ticker, scored: f"{ticker}:100.00:A|P|UNIFIED")

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    scored_levels = [SimpleNamespace(ticker="SPY")]
    discord_notifier.send_discord_update(translated, run_label="RUN", scored_levels=scored_levels)

    assert calls
    first_payload, _ = calls[0]
    assert first_payload["content"].startswith("SPY:100.00:A|P|UNIFIED")


def test_write_unified_levels_txt_writes_stable_lines(tmp_path: Path) -> None:
    scored_levels = [
        SimpleNamespace(ticker="QQQ", tagged_levels=[]),
        SimpleNamespace(ticker="SPY", tagged_levels=[]),
    ]

    # Force deterministic token composition for this test.
    original = file_writer._compose_unified_tokens_for_ticker
    file_writer._compose_unified_tokens_for_ticker = lambda *args, **kwargs: ["100.00:A|P|U"]
    try:
        out = tmp_path / "unified_levels.txt"
        file_writer.write_unified_levels_txt(scored_levels, path=out)
        text = out.read_text(encoding="utf-8")
    finally:
        file_writer._compose_unified_tokens_for_ticker = original

    assert text.splitlines() == ["QQQ:100.00:A|P|U", "SPY:100.00:A|P|U"]


def test_write_unified_levels_txt_includes_meta_tokens(tmp_path: Path) -> None:
    scored = SimpleNamespace(
        ticker="SPY",
        tagged_levels=[
            MechanicalWall(
                strike=100.0,
                label="Wall",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            )
        ],
        expected_moves=[],
    )

    metadata = SimpleNamespace(
        ticker="SPY",
        em_value=5.0,
        em_upper=105.0,
        em_lower=95.0,
        call_wall=101.0,
        put_wall=99.0,
        local_call_node=101.5,
        local_put_node=98.5,
        call_wall_0dte=102.0,
        put_wall_0dte=98.0,
        dex_call_node=103.0,
        dex_put_node=97.0,
        gamma_flip_upper=101.2,
        gamma_flip_lower=98.8,
        gamma_cliff_up=104.0,
        gamma_cliff_down=96.0,
        zero_gamma=100.0,
        max_pain=100.5,
        hedge_wall=97.5,
        total_gex=10_000.0,
        gex_regime="POSITIVE",
        secondary_call_wall=102.5,
        secondary_put_wall=97.5,
        vol_trigger_upper_05=102.0,
        vol_trigger_lower_05=98.0,
        vol_trigger_upper_10=103.0,
        vol_trigger_lower_10=97.0,
        vol_trigger_upper_15=104.0,
        vol_trigger_lower_15=96.0,
        vanna_call_node=101.0,
        vanna_put_node=99.0,
        charm_call_node=8.0,
        charm_put_node=2.0,
        volume_imbalance_call_node=101.0,
        volume_imbalance_put_node=99.0,
        liquidity_vacuum_lower=95.0,
        liquidity_vacuum_upper=105.0,
        skew_pivot_put_25d=98.0,
        skew_pivot_call_25d=102.0,
        gamma_magnet=100.2,
        pin_strike=100.1,
        pin_odds=0.6,
        wall_separation=2.0,
        regime_label="BATTLE_ZONE",
        directional_bias="NEUTRAL",
        call_gamma_total=6_000.0,
        put_gamma_total=4_000.0,
        net_vanna_exposure=2.0,
        net_speed_exposure=11.0,
        total_gex_delta_adj=3_000.0,
        call_gex_0dte=2_000.0,
        put_gex_0dte=1_000.0,
        atm_iv=0.15,
        iv_change=0.01,
        volatility_skew_premium=0.03,
        spot=100.0,
        futures_price=100.0,
    )

    out = tmp_path / "unified_with_meta.txt"
    file_writer.write_unified_levels_txt(
        [scored],
        path=out,
        metadata_levels_by_ticker={"SPY": metadata},
    )
    line = out.read_text(encoding="utf-8").strip()

    assert "META_REGIME_" in line
    assert "META_NOTE_" in line
    assert "META_S_TRIG_" in line


def test_write_unified_levels_json_matches_unified_txt_lines(tmp_path: Path) -> None:
    scored_levels = [
        SimpleNamespace(ticker="QQQ", tagged_levels=[]),
        SimpleNamespace(ticker="SPY", tagged_levels=[]),
    ]

    original = file_writer._compose_unified_tokens_for_ticker
    file_writer._compose_unified_tokens_for_ticker = lambda *args, **kwargs: ["100.00:A|P|U"]
    try:
        txt_out = tmp_path / "unified_levels.txt"
        json_out = tmp_path / "unified_levels.json"
        file_writer.write_unified_levels_txt(scored_levels, path=txt_out)
        file_writer.write_unified_levels_json(scored_levels, path=json_out)
        txt_lines = [ln for ln in txt_out.read_text(encoding="utf-8").splitlines() if ln.strip()]
        parsed = json.loads(json_out.read_text(encoding="utf-8"))
    finally:
        file_writer._compose_unified_tokens_for_ticker = original

    assert [row["line"] for row in parsed["tickers"]] == txt_lines


def test_parse_unified_line_extracts_token_fields() -> None:
    line = "SPY:736.04:I|S|ZERO GEX, 725.00:A|S|OI NODE 3.0σ P 6d"
    parsed = file_writer._parse_unified_line(line)

    assert parsed["ticker"] == "SPY"
    assert parsed["token_count"] == 2
    assert parsed["tokens"][0]["strike"] == 736.04
    assert parsed["tokens"][0]["filter"] == "I"
    assert parsed["tokens"][0]["significance"] == "S"
    assert parsed["tokens"][0]["label"] == "ZERO GEX"


def test_unified_payload_fingerprint_reports_sha_and_lines(tmp_path: Path) -> None:
    payload = tmp_path / "unified_levels.txt"
    payload.write_text("SPY:100.00:A|P|ONE\nQQQ:200.00:W|S|TWO\n", encoding="utf-8")

    fp = file_writer.unified_payload_fingerprint(payload)

    assert fp["exists"] is True
    assert fp["bytes"] > 0
    assert fp["lines"] == 2
    assert len(fp["sha256"]) == 64


def test_unified_macro_extensions_dedupe_and_tagging(tmp_path: Path) -> None:
    intraday = SimpleNamespace(
        ticker="SPY",
        tagged_levels=[
            MechanicalWall(
                strike=100.0,
                label="Wall A",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            )
        ],
    )
    macro = SimpleNamespace(
        ticker="SPY",
        tagged_levels=[
            MechanicalWall(
                strike=100.0,
                label="Wall Dup",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
            MechanicalWall(
                strike=108.0,
                label="Wall Ext",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            ),
        ],
    )

    out = tmp_path / "unified_levels.txt"
    file_writer.write_unified_levels_txt(
        [intraday],
        path=out,
        macro_scored_levels=[macro],
        macro_spot_by_ticker={"SPY": 100.0},
        macro_extension_band_pct=0.10,
        show_far_macro=False,
    )
    line = out.read_text(encoding="utf-8").strip()

    assert line.count("100.00") == 1
    assert "108.00" in line
    assert "[MEXT]" in line


def test_unified_macro_far_levels_hidden_unless_enabled(tmp_path: Path) -> None:
    intraday = SimpleNamespace(
        ticker="SPY",
        tagged_levels=[
            MechanicalWall(
                strike=100.0,
                label="Wall A",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            )
        ],
    )
    macro = SimpleNamespace(
        ticker="SPY",
        tagged_levels=[
            MechanicalWall(
                strike=125.0,
                label="Wall Far",
                significance="PRIMARY",
                side="CALL",
                field_name="call_wall",
                pct_of_book=0.2,
            )
        ],
    )

    hidden = tmp_path / "unified_hidden.txt"
    shown = tmp_path / "unified_shown.txt"

    file_writer.write_unified_levels_txt(
        [intraday],
        path=hidden,
        macro_scored_levels=[macro],
        macro_spot_by_ticker={"SPY": 100.0},
        macro_extension_band_pct=0.10,
        show_far_macro=False,
    )
    file_writer.write_unified_levels_txt(
        [intraday],
        path=shown,
        macro_scored_levels=[macro],
        macro_spot_by_ticker={"SPY": 100.0},
        macro_extension_band_pct=0.10,
        show_far_macro=True,
    )

    hidden_line = hidden.read_text(encoding="utf-8").strip()
    shown_line = shown.read_text(encoding="utf-8").strip()

    assert "125.00" not in hidden_line
    assert "125.00" in shown_line
    assert "[FAR]" in shown_line


def test_discord_output_uses_unified_file_content_when_present(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((payload, files)))
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", False)
    monkeypatch.setattr(discord_notifier, "build_scored_levels_line", lambda ticker, scored: f"{ticker}:100.00:A|P|UNIFIED")

    unified = tmp_path / "unified_levels.txt"
    unified.write_text("SPY:200.00:W|P|FILE\nQQQ:300.00:A|S|FILE\n", encoding="utf-8")

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    scored_levels = [SimpleNamespace(ticker="SPY")]
    discord_notifier.send_discord_update(
        translated,
        run_label="RUN",
        scored_levels=scored_levels,
        unified_copy_path=unified,
    )

    assert calls
    first_payload, _ = calls[0]
    assert first_payload["content"].startswith("SPY:200.00:W|P|FILE")


def test_discord_output_uses_webhook_key_override(monkeypatch) -> None:
    calls: list[tuple[str, dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", False)
    monkeypatch.setattr(discord_notifier, "build_scored_levels_line", lambda ticker, scored: f"{ticker}:100.00:A|P|UNIFIED")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda key: f"https://example.invalid/{key}")
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((url, payload, files)))

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    scored_levels = [SimpleNamespace(ticker="SPY")]

    discord_notifier.send_discord_update(
        translated_levels=translated,
        run_label="RUN",
        scored_levels=scored_levels,
        webhook_key="test_channel",
    )

    assert calls
    assert all(url.endswith("/test_channel") for url, _, _ in calls)


def test_discord_attachment_failure_falls_back_to_raw_chunks(monkeypatch) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", True)

    def fake_post(url, payload, files=None):
        calls.append((payload, files))
        if files is not None:
            return False
        return True

    monkeypatch.setattr(discord_notifier, "_post_payload", fake_post)

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    scored_levels = [SimpleNamespace(ticker="SPY", tagged_levels=[])]
    monkeypatch.setattr(discord_notifier, "build_scored_levels_line", lambda ticker, scored: f"{ticker}:100.00:A|P|UNIFIED")

    discord_notifier.send_discord_update(translated, run_label="RUN", scored_levels=scored_levels)

    assert calls
    assert calls[0][1] is not None
    assert any(files is None and payload.get("content", "").startswith("SPY:100.00") for payload, files in calls[1:])


def test_discord_empty_unified_file_falls_back_to_scored_lines(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[dict, dict | None]] = []

    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda *args, **kwargs: "https://example.invalid")
    monkeypatch.setattr(discord_notifier, "_build_embed", lambda *args, **kwargs: {"title": "ok"})
    monkeypatch.setattr(discord_notifier, "_build_coaches_note_payloads", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_notifier, "_post_payload", lambda url, payload, files=None: calls.append((payload, files)))
    monkeypatch.setattr(discord_notifier, "ENABLE_DISCORD_COPY_ATTACHMENT", False)
    monkeypatch.setattr(discord_notifier, "build_scored_levels_line", lambda ticker, scored: f"{ticker}:111.00:A|P|FALLBACK")

    unified = tmp_path / "unified_levels.txt"
    unified.write_text("\n\n", encoding="utf-8")

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]
    scored_levels = [SimpleNamespace(ticker="SPY", tagged_levels=[])]

    discord_notifier.send_discord_update(
        translated,
        run_label="RUN",
        scored_levels=scored_levels,
        unified_copy_path=unified,
    )

    assert calls
    first_payload, _ = calls[0]
    assert first_payload["content"].startswith("SPY:111.00:A|P|FALLBACK")


def test_discord_invalid_webhook_key_raises_keyerror(monkeypatch) -> None:
    monkeypatch.setattr(discord_notifier, "_load_webhook_url", lambda key=None: (_ for _ in ()).throw(KeyError("missing key")))

    translated = [SimpleNamespace(futures_symbol="ES", cash_ticker="SPY")]

    try:
        discord_notifier.send_discord_update(translated, run_label="RUN", webhook_key="does_not_exist")
    except KeyError as exc:
        assert "missing key" in str(exc)
    else:
        raise AssertionError("Expected KeyError for invalid webhook key")
