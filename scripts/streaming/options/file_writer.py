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
from .formatting import (
    build_coaches_note,
    build_plan,
    cash_tag,
    copy_ready_line,
    fmt,
    futures_tag,
)
from .futures_translator import TranslatedLevels
from .gex_calculator import DealerLevels

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full attribute list for JSON serialisation (all 34 level types).
# The copy-ready string uses the 16-level subset defined in formatting.py.
# ---------------------------------------------------------------------------

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
    ("gamma_magnet", "Gamma Magnet"),
    ("pin_strike", "Pin Strike"),
]


# ---------------------------------------------------------------------------
# JSON entry builders
# ---------------------------------------------------------------------------

def _to_entries(tl: TranslatedLevels) -> list[dict[str, Any]]:
    tag = cash_tag(tl.futures_symbol)
    rows: list[dict[str, Any]] = []
    for attr, label in _LEVEL_ATTRS:
        value = getattr(tl, attr, None)
        if value is None:
            continue
        entry: dict[str, Any] = {
            "level": round(float(value), 2),
            "type": label,
            "asset": tag,
            "regime": tl.gex_regime,
            "regime_label": tl.regime_label,
            "cash_ticker": tl.cash_ticker,
            "translation_mode": tl.translation_mode,
        }
        if tl.translation_mode == "additive":
            entry["basis_spread"] = tl.basis_spread
        else:
            entry["basis_ratio"] = tl.basis_ratio
        rows.append(entry)
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


# ---------------------------------------------------------------------------
# TXT detailed block (unique to file output)
# ---------------------------------------------------------------------------

def _detailed_block(tl: TranslatedLevels) -> list[str]:
    tag = futures_tag(tl.futures_symbol)
    return [
        f"── {tl.cash_ticker} → {tag} {'─' * 40}",
        f"  Regime             : {tl.gex_regime} GEX — {tl.regime_label} ({tl.directional_bias})  (total GEX = {tl.total_gex:,.0f})",
        f"  Cash Spot          : {tl.cash_spot:,.2f}",
        f"  {tag} Futures       : {tl.futures_price:,.2f}  "
        f"({'basis: ' + f'{tl.basis_spread:+.2f}' if tl.translation_mode == 'additive' else 'ratio: ' + f'{tl.basis_ratio:.2f}×'})",
        "",
        f"  ── Market Structure ──────────────────────────",
        f"  Gamma Magnet       : {fmt(tl.gamma_magnet)}",
        f"  Pin Strike         : {fmt(tl.pin_strike)}  ({tl.pin_odds:.0%} concentration)",
        f"  Wall Separation    : {fmt(tl.wall_separation)} pts",
        f"  Regime             : {tl.regime_label} — {tl.directional_bias}",
        f"  Call Gamma Total   : {tl.call_gamma_total:,.0f}",
        f"  Put Gamma Total    : {tl.put_gamma_total:,.0f}",
        f"  Net Vanna Exposure : {tl.net_vanna_exposure:,.0f}",
        "",
        f"  ── Key Levels ───────────────────────────────",
        f"  Upper EM           : {fmt(tl.em_upper)}",
        f"  Absolute Call Wall : {fmt(tl.call_wall)}",
        f"  Local Call Node    : {fmt(tl.local_call_node)}",
        f"  0DTE Call Wall     : {fmt(tl.call_wall_0dte)}",
        f"  Zero Gamma         : {fmt(tl.zero_gamma)}",
        f"  Max Pain           : {fmt(tl.max_pain)}",
        f"  0DTE Put Wall      : {fmt(tl.put_wall_0dte)}",
        f"  Local Put Node     : {fmt(tl.local_put_node)}",
        f"  Hedge Wall         : {fmt(tl.hedge_wall)}",
        f"  Lower EM           : {fmt(tl.em_lower)}",
        "",
        f"  Secondary Call/Put : {fmt(tl.secondary_call_wall)} / {fmt(tl.secondary_put_wall)}",
        f"  Gamma Flip Zone    : {fmt(tl.gamma_flip_lower)} ↔ {fmt(tl.gamma_flip_upper)}",
        f"  Gamma Cliffs       : Down {fmt(tl.gamma_cliff_down)} | Up {fmt(tl.gamma_cliff_up)}",
        f"  Vanna Nodes C/P    : {fmt(tl.vanna_call_node)} / {fmt(tl.vanna_put_node)}",
        f"  Charm Nodes C/P    : {fmt(tl.charm_call_node)} / {fmt(tl.charm_put_node)}",
        f"  Vol Imbalance C/P  : {fmt(tl.volume_imbalance_call_node)} / {fmt(tl.volume_imbalance_put_node)}",
        f"  DEX Nodes C/P      : {fmt(tl.dex_call_node)} / {fmt(tl.dex_put_node)}",
        f"  Liquidity Vacuum   : {fmt(tl.liquidity_vacuum_lower)} ↔ {fmt(tl.liquidity_vacuum_upper)}",
        f"  Skew Pivots 25D    : Put {fmt(tl.skew_pivot_put_25d)} | Call {fmt(tl.skew_pivot_call_25d)}",
        f"  Vol Triggers       : 0.5σ {fmt(tl.vol_trigger_lower_05)}-{fmt(tl.vol_trigger_upper_05)} | "
        f"1.0σ {fmt(tl.vol_trigger_lower_10)}-{fmt(tl.vol_trigger_upper_10)} | "
        f"1.5σ {fmt(tl.vol_trigger_lower_15)}-{fmt(tl.vol_trigger_upper_15)}",
        "",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_levels(
    translated_levels: list[TranslatedLevels],
    run_label: str = "",
    cash_levels: list[DealerLevels] | None = None,
    json_path: Path = DAILY_LEVELS_JSON,
    txt_path: Path = DAILY_LEVELS_TXT,
) -> None:
    if not run_label:
        run_label = datetime.now().strftime("%Y-%m-%d %H:%M ET")

    # ── JSON output ────────────────────────────────────────────────────────
    all_entries: list[dict[str, Any]] = []
    for tl in translated_levels:
        all_entries.extend(_to_entries(tl))
    for levels in cash_levels or []:
        all_entries.extend(_to_cash_entries(levels))

    # Market structure summary per translated instrument (Tier 2 metrics).
    market_structure: list[dict[str, Any]] = []
    for tl in translated_levels:
        market_structure.append({
            "asset": cash_tag(tl.futures_symbol),
            "cash_ticker": tl.cash_ticker,
            "regime_label": tl.regime_label,
            "gex_regime": tl.gex_regime,
            "total_gex": tl.total_gex,
            "gamma_magnet": tl.gamma_magnet,
            "pin_strike": tl.pin_strike,
            "pin_odds": tl.pin_odds,
            "wall_separation": tl.wall_separation,
            "call_gamma_total": tl.call_gamma_total,
            "put_gamma_total": tl.put_gamma_total,
            "net_vanna_exposure": tl.net_vanna_exposure,
        })

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "market_structure": market_structure,
        "levels": all_entries,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    log.info("JSON written → %s  (%d levels)", json_path, len(all_entries))

    # ── TXT output ─────────────────────────────────────────────────────────
    lines: list[str] = [
        f"Dealer Levels — {run_label}",
        "=" * 60,
        "",
        "Formatted Strings (copy-ready)",
        "",
    ]

    for tl in translated_levels:
        lines.append(copy_ready_line(cash_tag(tl.futures_symbol), tl))

    if cash_levels:
        lines.append("")
        for levels in cash_levels:
            lines.append(copy_ready_line(levels.ticker, levels))

    lines.extend(["", "Interpretation / Pre-Open Plan", ""])
    for tl in translated_levels:
        tag = cash_tag(tl.futures_symbol)
        lines.extend(build_plan(tag, tl, extended=True))
        lines.append("")

    lines.extend(["", "Coach's Briefing", "─" * 60, ""])
    for tl in translated_levels:
        tag = futures_tag(tl.futures_symbol)
        lines.append(build_coaches_note(tag, tl))
        lines.append("")

    lines.extend(["Detailed Summary", ""])
    for tl in translated_levels:
        lines.extend(_detailed_block(tl))

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("TXT written  → %s", txt_path)