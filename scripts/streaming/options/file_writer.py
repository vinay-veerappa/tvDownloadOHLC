"""
file_writer.py
==============
Persist translated levels to JSON and TXT, including copy-ready string format
and interpretation text for alerts / pre-open planning.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DAILY_LEVELS_JSON, DAILY_LEVELS_TXT
from .futures_translator import TranslatedLevels
from .gex_calculator import DealerLevels

log = logging.getLogger(__name__)


_LEVEL_ATTRS: list[tuple[str, str]] = [
    ("em_upper", "Upper EM"),
    ("call_wall", "Absolute Call Wall"),
    ("local_call_node", "Local Call Node"),
    ("call_wall_0dte", "0DTE Call Wall"),
    ("zero_gamma", "Zero Gamma"),
    ("max_pain", "Max Pain"),
    ("put_wall_0dte", "0DTE Put Wall"),
    ("local_put_node", "Local Put Node"),
    ("hedge_wall", "Hedge Wall"),
    ("em_lower", "Lower EM"),
    ("put_wall", "Absolute Put Wall"),
    ("secondary_call_wall", "Secondary Call Wall"),
    ("secondary_put_wall", "Secondary Put Wall"),
    ("gamma_flip_lower", "Gamma Flip Lower"),
    ("gamma_flip_upper", "Gamma Flip Upper"),
    ("vol_trigger_upper_05", "Vol Trigger +0.5σ"),
    ("vol_trigger_lower_05", "Vol Trigger -0.5σ"),
    ("vol_trigger_upper_10", "Vol Trigger +1.0σ"),
    ("vol_trigger_lower_10", "Vol Trigger -1.0σ"),
    ("vol_trigger_upper_15", "Vol Trigger +1.5σ"),
    ("vol_trigger_lower_15", "Vol Trigger -1.5σ"),
    ("gamma_cliff_up", "Gamma Cliff Up"),
    ("gamma_cliff_down", "Gamma Cliff Down"),
    ("vanna_call_node", "Vanna Call Node"),
    ("vanna_put_node", "Vanna Put Node"),
    ("charm_call_node", "Charm Call Node"),
    ("charm_put_node", "Charm Put Node"),
    ("volume_imbalance_call_node", "Volume Imbalance Call Node"),
    ("volume_imbalance_put_node", "Volume Imbalance Put Node"),
    ("dex_call_node", "DEX Call Node"),
    ("dex_put_node", "DEX Put Node"),
    ("liquidity_vacuum_lower", "Liquidity Vacuum Lower"),
    ("liquidity_vacuum_upper", "Liquidity Vacuum Upper"),
    ("skew_pivot_put_25d", "Skew Pivot Put 25D"),
    ("skew_pivot_call_25d", "Skew Pivot Call 25D"),
]


def _to_entries(tl: TranslatedLevels) -> list[dict[str, Any]]:
    tag = tl.futures_symbol.lstrip("/")
    rows: list[dict[str, Any]] = []
    for attr, label in _LEVEL_ATTRS:
        value = getattr(tl, attr, None)
        if value is None:
            continue
        rows.append(
            {
                "level": round(float(value), 2),
                "type": label,
                "asset": tag,
                "regime": tl.gex_regime,
                "cash_ticker": tl.cash_ticker,
                "basis_spread": tl.basis_spread,
            }
        )
    return rows


def _to_cash_entries(levels: DealerLevels) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attr, label in _LEVEL_ATTRS:
        value = getattr(levels, attr, None)
        if value is None:
            continue
        rows.append(
            {
                "level": round(float(value), 2),
                "type": label,
                "asset": levels.ticker,
                "regime": levels.gex_regime,
                "cash_ticker": levels.ticker,
                "basis_spread": 0.0,
                "price_space": "cash",
            }
        )
    return rows


def _fmt(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "N/A"


def _copy_ready_line(tl: TranslatedLevels) -> str:
    tag = tl.futures_symbol.lstrip("/")
    ordered = [
        (_fmt(tl.em_upper), "Upper EM"),
        (_fmt(tl.call_wall), "Absolute Call Wall"),
        (_fmt(tl.local_call_node), "Local Call Node"),
        (_fmt(tl.call_wall_0dte), "0DTE Call Wall"),
        (_fmt(tl.zero_gamma), "Zero Gamma"),
        (_fmt(tl.max_pain), "Max Pain"),
        (_fmt(tl.put_wall_0dte), "0DTE Put Wall"),
        (_fmt(tl.local_put_node), "Local Put Node"),
        (_fmt(tl.hedge_wall), "Hedge Wall"),
        (_fmt(tl.em_lower), "Lower EM"),
    ]
    return f"{tag}: " + ", ".join(f"{px}:{label}" for px, label in ordered)


def _copy_ready_cash_line(levels: DealerLevels) -> str:
    ordered = [
        (_fmt(levels.em_upper), "Upper EM"),
        (_fmt(levels.call_wall), "Absolute Call Wall"),
        (_fmt(levels.local_call_node), "Local Call Node"),
        (_fmt(levels.call_wall_0dte), "0DTE Call Wall"),
        (_fmt(levels.zero_gamma), "Zero Gamma"),
        (_fmt(levels.max_pain), "Max Pain"),
        (_fmt(levels.put_wall_0dte), "0DTE Put Wall"),
        (_fmt(levels.local_put_node), "Local Put Node"),
        (_fmt(levels.hedge_wall), "Hedge Wall"),
        (_fmt(levels.em_lower), "Lower EM"),
    ]
    return f"{levels.ticker}: " + ", ".join(f"{px}:{label}" for px, label in ordered)


def _interpretation_lines(tl: TranslatedLevels) -> list[str]:
    tag = tl.futures_symbol.lstrip("/")
    lines = [
        f"{tag} Plan:",
        f"- Regime: {tl.gex_regime} (Total GEX: {tl.total_gex:,.0f})",
        f"- Bias Anchor: Zero Gamma {_fmt(tl.zero_gamma)} | Max Pain {_fmt(tl.max_pain)}",
        f"- Key Resistance Ladder: Local/0DTE/Abs Call = {_fmt(tl.local_call_node)} / {_fmt(tl.call_wall_0dte)} / {_fmt(tl.call_wall)}",
        f"- Key Support Ladder: Local/0DTE/Hedge = {_fmt(tl.local_put_node)} / {_fmt(tl.put_wall_0dte)} / {_fmt(tl.hedge_wall)}",
        f"- EM Envelope: {_fmt(tl.em_lower)} ↔ {_fmt(tl.em_upper)} (±{tl.em_value:.2f})",
        f"- Gamma Flip Zone: {_fmt(tl.gamma_flip_lower)} ↔ {_fmt(tl.gamma_flip_upper)}",
        f"- Flow Nodes: Vanna(C/P) {_fmt(tl.vanna_call_node)}/{_fmt(tl.vanna_put_node)} | Charm(C/P) {_fmt(tl.charm_call_node)}/{_fmt(tl.charm_put_node)}",
        f"- Intraday Flow: Vol-Imb(C/P) {_fmt(tl.volume_imbalance_call_node)}/{_fmt(tl.volume_imbalance_put_node)} | DEX(C/P) {_fmt(tl.dex_call_node)}/{_fmt(tl.dex_put_node)}",
        f"- Vol Trigger Bands: 0.5σ {_fmt(tl.vol_trigger_lower_05)}-{_fmt(tl.vol_trigger_upper_05)}, 1.0σ {_fmt(tl.vol_trigger_lower_10)}-{_fmt(tl.vol_trigger_upper_10)}, 1.5σ {_fmt(tl.vol_trigger_lower_15)}-{_fmt(tl.vol_trigger_upper_15)}",
    ]
    return lines


def _detailed_block(tl: TranslatedLevels) -> list[str]:
    tag = tl.futures_symbol.lstrip("/")
    return [
        f"── {tl.cash_ticker} → {tag} {'─' * 40}",
        f"  Regime             : {tl.gex_regime} GEX  (total GEX = {tl.total_gex:,.0f})",
        f"  Cash Spot          : {tl.cash_spot:,.2f}",
        f"  {tag} Futures       : {tl.futures_price:,.2f}  (basis spread: {tl.basis_spread:+.2f})",
        "",
        f"  Upper EM           : {_fmt(tl.em_upper)}",
        f"  Absolute Call Wall : {_fmt(tl.call_wall)}",
        f"  Local Call Node    : {_fmt(tl.local_call_node)}",
        f"  0DTE Call Wall     : {_fmt(tl.call_wall_0dte)}",
        f"  Zero Gamma         : {_fmt(tl.zero_gamma)}",
        f"  Max Pain           : {_fmt(tl.max_pain)}",
        f"  0DTE Put Wall      : {_fmt(tl.put_wall_0dte)}",
        f"  Local Put Node     : {_fmt(tl.local_put_node)}",
        f"  Hedge Wall         : {_fmt(tl.hedge_wall)}",
        f"  Lower EM           : {_fmt(tl.em_lower)}",
        "",
        f"  Secondary Call/Put : {_fmt(tl.secondary_call_wall)} / {_fmt(tl.secondary_put_wall)}",
        f"  Gamma Flip Zone    : {_fmt(tl.gamma_flip_lower)} ↔ {_fmt(tl.gamma_flip_upper)}",
        f"  Gamma Cliffs       : Down {_fmt(tl.gamma_cliff_down)} | Up {_fmt(tl.gamma_cliff_up)}",
        f"  Vanna Nodes C/P    : {_fmt(tl.vanna_call_node)} / {_fmt(tl.vanna_put_node)}",
        f"  Charm Nodes C/P    : {_fmt(tl.charm_call_node)} / {_fmt(tl.charm_put_node)}",
        f"  Vol Imbalance C/P  : {_fmt(tl.volume_imbalance_call_node)} / {_fmt(tl.volume_imbalance_put_node)}",
        f"  DEX Nodes C/P      : {_fmt(tl.dex_call_node)} / {_fmt(tl.dex_put_node)}",
        f"  Liquidity Vacuum   : {_fmt(tl.liquidity_vacuum_lower)} ↔ {_fmt(tl.liquidity_vacuum_upper)}",
        f"  Skew Pivots 25D    : Put {_fmt(tl.skew_pivot_put_25d)} | Call {_fmt(tl.skew_pivot_call_25d)}",
        f"  Vol Triggers       : 0.5σ {_fmt(tl.vol_trigger_lower_05)}-{_fmt(tl.vol_trigger_upper_05)} | "
        f"1.0σ {_fmt(tl.vol_trigger_lower_10)}-{_fmt(tl.vol_trigger_upper_10)} | "
        f"1.5σ {_fmt(tl.vol_trigger_lower_15)}-{_fmt(tl.vol_trigger_upper_15)}",
        "",
    ]


def write_levels(
    translated_levels: list[TranslatedLevels],
    run_label: str = "",
    cash_levels: list[DealerLevels] | None = None,
    json_path: Path = DAILY_LEVELS_JSON,
    txt_path: Path = DAILY_LEVELS_TXT,
) -> None:
    if not run_label:
        run_label = datetime.now().strftime("%Y-%m-%d %H:%M ET")

    all_entries: list[dict[str, Any]] = []
    for tl in translated_levels:
        all_entries.extend(_to_entries(tl))
    for levels in cash_levels or []:
        all_entries.extend(_to_cash_entries(levels))

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "levels": all_entries,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    log.info("JSON written → %s  (%d levels)", json_path, len(all_entries))

    lines: list[str] = [
        f"Dealer Levels — {run_label}",
        "=" * 60,
        "",
        "Formatted Strings (copy-ready)",
        "",
    ]

    for tl in translated_levels:
        lines.append(_copy_ready_line(tl))

    if cash_levels:
        lines.extend(["", "Cash-Space Test Symbols", ""])
        for levels in cash_levels:
            lines.append(_copy_ready_cash_line(levels))

    lines.extend(["", "Interpretation / Pre-Open Plan", ""])
    for tl in translated_levels:
        lines.extend(_interpretation_lines(tl))
        lines.append("")

    lines.extend(["Detailed Summary", ""])
    for tl in translated_levels:
        lines.extend(_detailed_block(tl))

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("TXT written  → %s", txt_path)
