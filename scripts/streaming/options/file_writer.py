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

from .config import DAILY_LEVELS_JSON, DAILY_LEVELS_TXT, GEX_PROFILES_JSON, LIVE_TREND_JSON
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


def _is_rth() -> bool:
    """Return True if current time falls within Regular Trading Hours (9:30–16:00 ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo
    from datetime import time as dt_time
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    mkt_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    mkt_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return mkt_open <= now <= mkt_close


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
    for em in tl.expected_moves:
        base_entry = {
            "asset": tag,
            "regime": tl.gex_regime,
            "regime_label": tl.regime_label,
            "cash_ticker": tl.cash_ticker,
            "translation_mode": tl.translation_mode,
        }
        if tl.translation_mode == "additive":
            base_entry["basis_spread"] = tl.basis_spread
        else:
            base_entry["basis_ratio"] = tl.basis_ratio

        rows.append({**base_entry, "level": round(float(em.em_upper), 2), "type": f"{em.expiry} Upper EM"})
        rows.append({**base_entry, "level": round(float(em.em_lower), 2), "type": f"{em.expiry} Lower EM"})

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
    
    for em in levels.expected_moves:
        # Add dte-prefixed labels to the copy-ready string for Pine Script filtering
        label_dte = f" ({em.dte}d)" if em.dte is not None else ""
        rows.append({
            "level": round(float(em.em_upper), 2),
            "type": f"{em.expiry}{label_dte} Upper EM",
            "asset": levels.ticker,
            "regime": levels.gex_regime,
            "cash_ticker": levels.ticker,
            "basis_spread": 0.0,
            "price_space": "cash",
        })
        rows.append({
            "level": round(float(em.em_lower), 2),
            "type": f"{em.expiry} Lower EM",
            "asset": levels.ticker,
            "regime": levels.gex_regime,
            "cash_ticker": levels.ticker,
            "basis_spread": 0.0,
            "price_space": "cash",
        })

    return rows


# ---------------------------------------------------------------------------
# TXT detailed block (unique to file output)
# ---------------------------------------------------------------------------

def _detailed_block(tl: TranslatedLevels) -> list[str]:
    tag = futures_tag(tl.futures_symbol)
    block = [
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
        f"  Implied Vol (ATM)  : {tl.atm_iv*100:,.1f}%" if tl.atm_iv else "  Implied Vol (ATM)  : —",
        f"  Daily Vol Change   : {tl.iv_change*100:+.1f}%",
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
        "",
        "  ── Expected Moves (All Expiries) ──────────",
    ]

    for em in tl.expected_moves:
        block.append(f"  {em.expiry} ({em.dte}d) : {fmt(em.em_lower)} ↔ {fmt(em.em_upper)}  (±{em.em_value:,.2f})")

    block.extend([
        "",
        f"  Vol Triggers       : 0.5σ {fmt(tl.vol_trigger_lower_05)}-{fmt(tl.vol_trigger_upper_05)} | "
        f"1.0σ {fmt(tl.vol_trigger_lower_10)}-{fmt(tl.vol_trigger_upper_10)} | "
        f"1.5σ {fmt(tl.vol_trigger_lower_15)}-{fmt(tl.vol_trigger_upper_15)}",
        "",
    ])
    return block


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
            "total_gex_delta_adj": tl.total_gex_delta_adj,
            "gamma_magnet": tl.gamma_magnet,
            "pin_strike": tl.pin_strike,
            "pin_odds": tl.pin_odds,
            "wall_separation": tl.wall_separation,
            "call_gamma_total": tl.call_gamma_total,
            "put_gamma_total": tl.put_gamma_total,
            "net_vanna_exposure": tl.net_vanna_exposure,
            "net_speed_exposure": tl.net_speed_exposure,
            "call_volume_centroid": tl.call_volume_centroid,
            "put_volume_centroid": tl.put_volume_centroid,
            "call_centroid": tl.call_volume_centroid, # standardized name
            "put_centroid": tl.put_volume_centroid,   # standardized name
            "atm_iv": tl.atm_iv,
            "iv_change": tl.iv_change,
            "expected_moves": [
                {
                    "expiry": em.expiry,
                    "dte": em.dte,
                    "em_upper": em.em_upper,
                    "em_lower": em.em_lower,
                    "em_value": em.em_value,
                    "straddle": em.straddle
                }
                for em in tl.expected_moves
            ],
            "coach_note": build_coaches_note(cash_tag(tl.futures_symbol) if tl.futures_symbol else cash_tag(tl.cash_ticker), tl)
        })
    # Also include cash-only tickers (ETFs, stocks) that don't have futures translation
    translated_cash_tickers = {tl.cash_ticker for tl in translated_levels}
    for levels in cash_levels or []:
        if levels.ticker in translated_cash_tickers:
            continue  # already covered by translated version
        market_structure.append({
            "asset": levels.ticker,
            "cash_ticker": levels.ticker,
            "regime_label": getattr(levels, 'regime_label', 'NEUTRAL'),
            "gex_regime": levels.gex_regime,
            "total_gex": levels.total_gex,
            "total_gex_delta_adj": levels.total_gex_delta_adj,
            "gamma_magnet": levels.gamma_magnet,
            "pin_strike": levels.pin_strike,
            "pin_odds": levels.pin_odds,
            "wall_separation": levels.wall_separation,
            "call_gamma_total": levels.call_gamma_total,
            "put_gamma_total": levels.put_gamma_total,
            "net_vanna_exposure": levels.net_vanna_exposure,
            "net_speed_exposure": levels.net_speed_exposure,
            "call_volume_centroid": levels.call_volume_centroid,
            "put_volume_centroid": levels.put_volume_centroid,
            "call_centroid": levels.call_volume_centroid,
            "put_centroid": levels.put_volume_centroid,
            "atm_iv": levels.atm_iv,
            "iv_change": levels.iv_change,
            "expected_moves": [
                {
                    "expiry": em.expiry,
                    "dte": em.dte,
                    "em_upper": em.em_upper,
                    "em_lower": em.em_lower,
                    "em_value": em.em_value,
                    "straddle": em.straddle
                }
                for em in getattr(levels, 'expected_moves', [])
            ],
            "coach_note": build_coaches_note(levels.ticker, levels)
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

    # ── GEX Profiles JSON output ───────────────────────────────────────────
    profiles_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "profiles": {}
    }

    # Build a lookup: cash_ticker → TranslatedLevels for futures translation
    cash_to_translated: dict[str, TranslatedLevels] = {
        tl.cash_ticker: tl for tl in translated_levels
    }



    def _sg_to_dict(sg, strike_override=None) -> dict:
        """Serialize a StrikeGEX to a JSON-friendly dict, including all Greek exposure fields."""
        return {
            "strike": round(strike_override, 2) if strike_override is not None else sg.strike,
            "call_gex": sg.call_gex,
            "put_gex": sg.put_gex,
            "net_gex": sg.net_gex,
            "call_vol": sg.call_vol,
            "put_vol": sg.put_vol,
            "call_oi": sg.call_oi,
            "put_oi": sg.put_oi,
            "call_iv": sg.call_iv,
            "put_iv": sg.put_iv,
            "cumulative_gex": sg.cumulative_gex,
            # Per-strike Greek exposures (notional, matching ezoptionsschwab.py methodology)
            "call_dex": sg.call_dex,
            "put_dex": sg.put_dex,
            "call_vex": sg.call_vex,
            "put_vex": sg.put_vex,
            "call_charm": sg.call_charm,
            "put_charm": sg.put_charm,
            "call_speed": sg.call_speed,
            "put_speed": sg.put_speed,
            "call_vomma": sg.call_vomma,
            "put_vomma": sg.put_vomma,
            "call_premium": sg.call_premium,
            "put_premium": sg.put_premium,
        }

    for levels in cash_levels or []:
        if not levels.strike_gex:
            continue
        tl = cash_to_translated.get(levels.ticker)
        if tl and tl.translation_mode == "multiplicative" and tl.basis_ratio > 0:
            ratio = tl.basis_ratio
            futures_key = cash_tag(tl.futures_symbol)
            profiles_doc["profiles"][futures_key] = [
                _sg_to_dict(sg, strike_override=round(sg.strike * ratio, 2))
                for sg in levels.strike_gex
            ]
            profiles_doc["profiles"][levels.ticker] = [
                _sg_to_dict(sg)
                for sg in levels.strike_gex
            ]
        elif tl and tl.translation_mode == "additive":
            spread = tl.basis_spread
            futures_key = cash_tag(tl.futures_symbol)
            profiles_doc["profiles"][futures_key] = [
                _sg_to_dict(sg, strike_override=round(sg.strike + spread, 2))
                for sg in levels.strike_gex
            ]
            profiles_doc["profiles"][levels.ticker] = [
                _sg_to_dict(sg)
                for sg in levels.strike_gex
            ]
        else:
            profiles_doc["profiles"][levels.ticker] = [
                _sg_to_dict(sg)
                for sg in levels.strike_gex
            ]

    GEX_PROFILES_JSON.parent.mkdir(parents=True, exist_ok=True)
    GEX_PROFILES_JSON.write_text(json.dumps(profiles_doc, indent=2), encoding="utf-8")
    log.info("GEX Profiles written → %s", GEX_PROFILES_JSON)

    # ── Live Trend JSON Append (RTH only) ────────────────────────────────────
    # We only write trend data during Regular Trading Hours to avoid polluting
    # the GEX Trend chart with flat pre-market / post-market / overnight points.
    if _is_rth():
        trend_doc = {"generated_at": datetime.now(timezone.utc).isoformat(), "history": {}}
        if LIVE_TREND_JSON.exists():
            try:
                existing_doc = json.loads(LIVE_TREND_JSON.read_text(encoding="utf-8"))
                # Reset history on a new trading day
                if "generated_at" in existing_doc:
                    old_time = datetime.fromisoformat(existing_doc["generated_at"]).astimezone(timezone.utc)
                    now_time = datetime.now(timezone.utc)
                    if old_time.date() == now_time.date():
                        trend_doc["history"] = existing_doc.get("history", {})
            except Exception as e:
                log.warning("Failed to parse existing live trend json, resetting. Error: %s", e)

        now_str = datetime.now(timezone.utc).isoformat()
        spot_by_ticker: dict[str, float] = {lvl.ticker: lvl.spot for lvl in (cash_levels or [])}

        for tl in market_structure:
            ticker = tl["cash_ticker"]
            if ticker not in trend_doc["history"]:
                trend_doc["history"][ticker] = []
            spot = spot_by_ticker.get(ticker, 0)
            trend_doc["history"][ticker].append({
                "timestamp": now_str,
                "total_gex": tl["total_gex"],
                "total_gex_delta_adj": tl.get("total_gex_delta_adj"),
                "gamma_magnet": tl["gamma_magnet"],
                "call_volume_centroid": tl.get("call_volume_centroid"),
                "put_volume_centroid": tl.get("put_volume_centroid"),
                "spot": spot,
                "gex_regime": tl["gex_regime"]
            })

        LIVE_TREND_JSON.parent.mkdir(parents=True, exist_ok=True)
        LIVE_TREND_JSON.write_text(json.dumps(trend_doc, indent=2), encoding="utf-8")
        log.info("Live Trend written → %s  (RTH only)", LIVE_TREND_JSON)
    else:
        log.debug("Skipping live_trend.json update — outside RTH.")

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
        lines.extend(build_coaches_note(tag, tl))  # now returns list[str]
        lines.append("")

    lines.extend(["Detailed Summary", ""])
    for tl in translated_levels:
        lines.extend(_detailed_block(tl))

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("TXT written  → %s", txt_path)