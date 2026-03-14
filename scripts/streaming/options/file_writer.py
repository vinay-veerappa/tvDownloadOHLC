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


def _first_level(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _nearest_below(reference: float | None, *values: float | None) -> float | None:
    if reference is None:
        return _first_level(*values)
    candidates = [value for value in values if value is not None and value < reference]
    if not candidates:
        return _first_level(*values)
    return max(candidates)


def _nearest_above(reference: float | None, *values: float | None) -> float | None:
    if reference is None:
        return _first_level(*values)
    candidates = [value for value in values if value is not None and value > reference]
    if not candidates:
        return _first_level(*values)
    return min(candidates)


def _copy_ready_line(tl: TranslatedLevels) -> str:
    tag = tl.futures_symbol.lstrip("/")
    ordered = [
        (_fmt(tl.em_upper), "Upper EM"),
        (_fmt(tl.call_wall), "Absolute Call Wall"),
        (_fmt(tl.local_call_node), "Local Call Node"),
        (_fmt(tl.call_wall_0dte), "0DTE Call Wall"),
        (_fmt(tl.gamma_flip_upper), "Gamma Flip Upper"),
        (_fmt(tl.zero_gamma), "Zero Gamma"),
        (_fmt(tl.gamma_flip_lower), "Gamma Flip Lower"),
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
        (_fmt(levels.gamma_flip_upper), "Gamma Flip Upper"),
        (_fmt(levels.zero_gamma), "Zero Gamma"),
        (_fmt(levels.gamma_flip_lower), "Gamma Flip Lower"),
        (_fmt(levels.max_pain), "Max Pain"),
        (_fmt(levels.put_wall_0dte), "0DTE Put Wall"),
        (_fmt(levels.local_put_node), "Local Put Node"),
        (_fmt(levels.hedge_wall), "Hedge Wall"),
        (_fmt(levels.em_lower), "Lower EM"),
    ]
    return f"{levels.ticker}: " + ", ".join(f"{px}:{label}" for px, label in ordered)


def _interpretation_lines(tl: TranslatedLevels) -> list[str]:
    tag = tl.futures_symbol.lstrip("/")

    short_trigger = _first_level(tl.zero_gamma, tl.gamma_flip_lower, tl.call_wall)
    short_target_1 = _nearest_below(
        short_trigger,
        tl.put_wall_0dte,
        tl.local_put_node,
        tl.hedge_wall,
        tl.vol_trigger_lower_05,
        tl.vol_trigger_lower_10,
        tl.em_lower,
    )
    short_target_2 = _nearest_below(
        short_target_1 if short_target_1 is not None else short_trigger,
        tl.hedge_wall,
        tl.vol_trigger_lower_10,
        tl.vol_trigger_lower_15,
        tl.em_lower,
    )
    short_invalidation = _nearest_above(short_trigger, tl.call_wall, tl.gamma_flip_upper, tl.em_upper)

    long_trigger = _first_level(tl.call_wall, tl.gamma_flip_upper, tl.zero_gamma)
    long_target_1 = _nearest_above(long_trigger, tl.max_pain, tl.vol_trigger_upper_05, tl.em_upper)
    long_target_2 = _nearest_above(
        long_target_1 if long_target_1 is not None else long_trigger,
        tl.vol_trigger_upper_10,
        tl.secondary_call_wall,
        tl.em_upper,
    )
    long_invalidation = _nearest_below(long_trigger, tl.zero_gamma, tl.gamma_flip_lower, tl.put_wall_0dte)

    regime_tone = (
        "sellers have structural control" if tl.gex_regime == "NEGATIVE" else "buyers have structural control"
    )

    lines = [
        f"{tag} Narrative Plan:",
        f"- Context: {tag} is in a {tl.gex_regime} GEX regime ({tl.total_gex:,.0f}), which means {regime_tone}. Start with this as your default bias, then let price confirm or reject it.",
        f"- What to watch first: the market's reaction around Zero Gamma {_fmt(tl.zero_gamma)} and the gamma-flip zone {_fmt(tl.gamma_flip_lower)} ↔ {_fmt(tl.gamma_flip_upper)}. Acceptance below this area favors continuation down; acceptance above favors a squeeze.",
        f"- Base-case execution: If price accepts below {_fmt(short_trigger)}, look for downside rotation into {_fmt(short_target_1)} first, then {_fmt(short_target_2)}. Short idea is invalidated if price reclaims and holds above {_fmt(short_invalidation)}.",
        f"- Alternate execution: If buyers reclaim {_fmt(long_trigger)} and hold, look for upside rotation toward {_fmt(long_target_1)} and then {_fmt(long_target_2)}. Long idea is invalidated if price loses {_fmt(long_invalidation)} after the breakout.",
        f"- Risk map for the session: Expected move envelope is {_fmt(tl.em_lower)} ↔ {_fmt(tl.em_upper)} (±{tl.em_value:.2f}). Inside the band, expect two-way trade; outside the band, expect expansion and faster trend continuation.",
        f"- Practical rule for newer traders: wait for candle-close acceptance and then a retest before entry; if acceptance fails, stand down and wait for the opposite scenario.",
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
        lines.append("")
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
