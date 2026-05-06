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

from .config import (
    DAILY_LEVELS_JSON, 
    DAILY_LEVELS_TXT, 
    GEX_PROFILES_JSON, 
    LIVE_TREND_JSON,
    MACRO_LEVELS_TXT,
    MACRO_QUANT_JSON
)
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
from .level_scorer import ScoredLevels, MechanicalWall, StructuralAnchor, InflectionPoint
from .config import SCORED_LEVELS_TXT
from .level_scorer import ScoredLevels, MechanicalWall, StructuralAnchor, InflectionPoint

log = logging.getLogger(__name__)
 
 
def _upsert_ticker_line(path: Path, ticker: str, new_line: str) -> None:
    """
    Replaces or appends a line for a specific ticker in a TXT file.
    Ensures that partial pipeline runs (e.g. Tier-1 only) don't wipe 
    out existing data for other tickers.
    """
    lines: list[str] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            log.warning("Failed to read %s for upsert: %s", path.name, e)
    
    new_lines: list[str] = []
    found = False
    ticker_prefix = f"{ticker}:"
    
    for line in lines:
        if line.strip().startswith(ticker_prefix):
            new_lines.append(new_line)
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(new_line)
    
    # Clean up empty lines and write back
    final_content = "\n".join(l for l in new_lines if l.strip()) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(final_content, encoding="utf-8")
 

def _get_strength(tl):
    if isinstance(tl, MechanicalWall):
        return round(tl.pct_of_book, 4)
    if isinstance(tl, StructuralAnchor):
        return round(tl.oi_zscore, 2)
    if isinstance(tl, InflectionPoint):
        return round(tl.slope_magnitude, 4)
    return 0.0

def _is_rth() -> bool:
    """Return True if current time falls within Regular Trading Hours (9:30–16:00 ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo
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

    return rows


def _to_scored_entries(scored: ScoredLevels) -> list[dict[str, Any]]:
    """Converts TaggedLevels into JSON-serializable entries for the UI."""
    return [
        {
            "strike": tl.strike,
            "label": tl.label,
            "significance": tl.significance,
            "side": tl.side,
            "strength": round(_get_strength(tl), 3),
            "description": tl.description,
            "field": tl.field_name,
            "asset": scored.ticker,
            "type": "TAGGED_LEVEL"
        }
        for tl in scored.tagged_levels
    ]


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
    scored_levels: list[ScoredLevels] | None = None,
    json_path: Path = DAILY_LEVELS_JSON,
    txt_path: Path = DAILY_LEVELS_TXT,
    versioned: bool = False,
    snapshot_suffix: str | None = None,
) -> None:
    if not run_label:
        run_label = datetime.now().strftime("%Y-%m-%d %H:%M ET")

    # ── JSON output ────────────────────────────────────────────────────────
    all_entries: list[dict[str, Any]] = []
    # Legacy flat-list format for back-compat
    for tl in translated_levels:
        all_entries.extend(_to_entries(tl))
    for levels in cash_levels or []:
        all_entries.extend(_to_cash_entries(levels))
        
    # New Tagged Levels format
    tagged_entries: list[dict[str, Any]] = []
    for sl in scored_levels or []:
        tagged_entries.extend(_to_scored_entries(sl))

    # Market structure summary per translated instrument (Tier 2 metrics).

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
            "put_25d_iv": tl.put_25d_iv,
            "call_25d_iv": tl.call_25d_iv,
            "volatility_skew_premium": tl.volatility_skew_premium,
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
            "coach_note": build_coaches_note(cash_tag(tl.futures_symbol) if tl.futures_symbol else cash_tag(tl.cash_ticker), tl),
            "tactical_plan": build_plan(cash_tag(tl.futures_symbol) if tl.futures_symbol else cash_tag(tl.cash_ticker), tl)
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
            "put_25d_iv": levels.put_25d_iv,
            "call_25d_iv": levels.call_25d_iv,
            "volatility_skew_premium": levels.volatility_skew_premium,
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
            "coach_note": build_coaches_note(levels.ticker, levels),
            "tactical_plan": build_plan(levels.ticker, levels)
        })
    

    # --- Append Scored Analysis Data (Filter Data) ---
    scored_lookup: dict[str, ScoredLevels] = {s.ticker: s for s in (scored_levels or [])}
    def _scored_to_dict(s: ScoredLevels) -> dict:
        return {
            "view_mode": s.view_mode,
            "regime": s.regime,
            "bias": s.bias,
            "strategic": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "side": l.side,
                    "strength": _get_strength(l),
                    "desc": l.description
                } for l in s.strategic
            ],
            "pivots": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "side": l.side,
                    "strength": _get_strength(l),
                    "desc": l.description
                } for l in s.pivots
            ],
            "contextual": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "side": l.side,
                    "strength": _get_strength(l),
                    "desc": l.description
                } for l in s.contextual
            ],
            "resistance_walls": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "side": l.side,
                    "strength":_get_strength(l)
                } for l in s.resistance_walls
            ],
            "support_walls": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "side": l.side,
                    "strength": _get_strength(l)
                } for l in s.support_walls
            ],
            "all_tagged": [
                {
                    "strike": l.strike,
                    "label": l.label,
                    "significance": l.significance,
                    "side": l.side,
                    "strength": _get_strength(l),
                    "field": l.field_name
                } for l in s.tagged_levels
            ]
        }

    for ms in market_structure:
        ticker = ms["cash_ticker"]
        if ticker in scored_lookup:
            ms["scored_analysis"] = _scored_to_dict(scored_lookup[ticker])

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "market_structure": market_structure,
        "levels": all_entries,
        "tagged_levels": tagged_entries,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_data = json.dumps(doc, indent=2)
    json_path.write_text(json_data, encoding="utf-8")
    log.info("JSON written -> %s  (%d levels)", json_path, len(all_entries))

    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_json_path = json_path.with_name(f"{json_path.stem}_{ts}{json_path.suffix}")
        v_json_path.write_text(json_data, encoding="utf-8")
        log.info("Versioned JSON written -> %s", v_json_path)

    if snapshot_suffix:
        s_json_path = json_path.with_name(f"{json_path.stem}_{snapshot_suffix}{json_path.suffix}")
        s_json_path.write_text(json_data, encoding="utf-8")
        log.info("Snapshot JSON written -> %s (overwrites daily)", s_json_path)

    # ── GEX Profiles JSON output ───────────────────────────────────────────
    profiles_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "profiles": {}
    }

    # Build a lookup: cash_ticker -> TranslatedLevels for futures translation
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
            "net_dex": sg.net_dex,
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
    profiles_data = json.dumps(profiles_doc, indent=2)
    GEX_PROFILES_JSON.write_text(profiles_data, encoding="utf-8")
    log.info("GEX Profiles written -> %s", GEX_PROFILES_JSON)

    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_profiles_path = GEX_PROFILES_JSON.with_name(f"{GEX_PROFILES_JSON.stem}_{ts}{GEX_PROFILES_JSON.suffix}")
        v_profiles_path.write_text(profiles_data, encoding="utf-8")
        log.info("Versioned GEX Profiles written -> %s", v_profiles_path)

    if snapshot_suffix:
        s_profiles_path = GEX_PROFILES_JSON.with_name(f"{GEX_PROFILES_JSON.stem}_{snapshot_suffix}{GEX_PROFILES_JSON.suffix}")
        s_profiles_path.write_text(profiles_data, encoding="utf-8")
        log.info("Snapshot GEX Profiles written -> %s", s_profiles_path)

    # ── Live Trend JSON Append (RTH only) ────────────────────────────────────
    # We only write trend data during Regular Trading Hours to avoid polluting
    # the GEX Trend chart with flat pre-market / post-market / overnight points.
    if _is_rth():
        trend_doc = {"generated_at": datetime.now(timezone.utc).isoformat(), "history": {}}
        if LIVE_TREND_JSON.exists():
            try:
                existing_doc = json.loads(LIVE_TREND_JSON.read_text(encoding="utf-8"))
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
                "gex_regime": tl["gex_regime"],
                "volatility_skew_premium": tl.get("volatility_skew_premium"),
                "atm_iv": tl.get("atm_iv"),
                "iv_change": tl.get("iv_change", 0.0)
            })

        LIVE_TREND_JSON.parent.mkdir(parents=True, exist_ok=True)
        LIVE_TREND_JSON.write_text(json.dumps(trend_doc, indent=2), encoding="utf-8")
        log.info("Live Trend written -> %s  (RTH only)", LIVE_TREND_JSON)
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
    txt_data = "\n".join(lines)
    txt_path.write_text(txt_data, encoding="utf-8")
    log.info("TXT written  -> %s", txt_path)

    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_txt_path = txt_path.with_name(f"{txt_path.stem}_{ts}{txt_path.suffix}")
        v_txt_path.write_text(txt_data, encoding="utf-8")
        log.info("Versioned TXT written -> %s", v_txt_path)

    if snapshot_suffix:
        s_txt_path = txt_path.with_name(f"{txt_path.stem}_{snapshot_suffix}{txt_path.suffix}")
        s_txt_path.write_text(txt_data, encoding="utf-8")
        log.info("Snapshot TXT written -> %s", s_txt_path)


def write_macro_levels(
    ticker: str, 
    levels: dict[str, float | None], 
    anomalies: dict[str, list[dict[str, Any]]],
    dominant_nodes: list[dict[str, Any]] = None,
    path: Path = MACRO_LEVELS_TXT,
    versioned: bool = False
) -> None:
    """
    Pillar 5: Strict text output for Pine Script.
    Format: TICKER:Price:Label, Price:Label, Price:Label
    """
    tokens: list[str] = []
    
    # 1. Macro Walls
    if levels.get("macro_call_wall"):
        tokens.append(f"{levels['macro_call_wall']:.2f}:Macro Call Wall")
        
    if levels.get("macro_put_wall"):
        tokens.append(f"{levels['macro_put_wall']:.2f}:Macro Put Wall")

    if levels.get("zero_gamma"):
        tokens.append(f"{levels['zero_gamma']:.2f}:Zero Gamma")

    # 2. Structural Whales (Confluence >= 2)
    for w in anomalies.get("structural", []):
        # Add a multiplier tag if there are multiple expirations (e.g., "x5")
        conf_tag = f" x{w['confluence']}" if w['confluence'] > 1 else ""
        prefix = "GOLDEN SWEEP: " if w.get('is_golden_sweep') else ""
        label = f"{prefix}Whale {w['type']}{conf_tag} {w['dte_str']} ({w['avg_vol_oi_ratio']}x)"
        tokens.append(f"{w['strike']:.2f}:{label}")

    # 3. Tactical Whales (Confluence == 1)
    # We label these "Local Whale" so the Pine Script 'isTactical' proximity 
    # filter automatically catches the word "LOCAL" and hides them if they are far away.
    for w in anomalies.get("tactical", []):
        prefix = "GOLDEN SWEEP: " if w.get('is_golden_sweep') else ""
        label = f"{prefix}Local Whale {w['type']} {w['dte_str']} ({w['avg_vol_oi_ratio']}x)"
        tokens.append(f"{w['strike']:.2f}:{label}")

    # 4. Dominant OI Nodes (The Map)
    if dominant_nodes:
        for node in dominant_nodes:
            label = f"Major {node['type'].capitalize()} Node ({node['dominance_pct']}%)"
            tokens.append(f"{node['strike']:.2f}:{label}")

    # 5. Format for Pine Script Parser
    if tokens:
        # The Pine script expects the VERY FIRST token to include the ticker
        # Example: SPX:5100.00:Macro Call Wall
        tokens[0] = f"{ticker}:{tokens[0]}"
        
    final_string = ", ".join(tokens)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use robust upsert to prevent data loss for other tickers in partial runs
    _upsert_ticker_line(path, ticker, final_string)

    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_path = path.with_name(f"{path.stem}_{ts}{path.suffix}")
        _upsert_ticker_line(v_path, ticker, final_string)
        
    log.info("Macro Levels written to %s (versioned=%s)", path, versioned)


def write_quant_json(
    ticker: str,
    spot: float,
    levels: dict[str, float | None],
    anomalies: dict[str, list[dict[str, Any]]],
    dominant_nodes: list[dict[str, Any]],
    path: Path = MACRO_QUANT_JSON,
    versioned: bool = False
) -> None:
    """
    Pillar 6: High-signal Quant JSON output.
    Filters major nodes (>4%) and top 3 golden sweeps.
    """
    quant_payload = {
        "ticker": ticker,
        "spot": spot,
        "zero_gamma": levels.get("zero_gamma"),
        "call_wall": levels.get("macro_call_wall"),
        "put_wall": levels.get("macro_put_wall"),
        "major_nodes": [n for n in dominant_nodes if n.get('dominance_pct', 0) > 4.0],
        "top_call_sweeps": [w for w in anomalies.get("structural", []) if w.get("type") == "CALL" and w.get("is_golden_sweep")][:3],
        "top_put_sweeps": [w for w in anomalies.get("structural", []) if w.get("type") == "PUT" and w.get("is_golden_sweep")][:3]
    }

    # Use a dictionary in the file keyed by ticker
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    existing[ticker] = quant_payload
    
    path.parent.mkdir(parents=True, exist_ok=True)
    json_data = json.dumps(existing, indent=2)
    path.write_text(json_data, encoding="utf-8")
    log.info("Quant JSON updated for %s → %s", ticker, path)

    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_path = path.with_name(f"{path.stem}_{ts}{path.suffix}")
        # Note: if multiple tickers call this with versioned=True in one run, 
        # we'd want to read the versioned file first. 
        # But for simplicity, if it's the same run, the versioned file name should be identical.
        v_existing = {}
        if v_path.exists():
            try: v_existing = json.loads(v_path.read_text(encoding="utf-8"))
            except: pass
        v_existing[ticker] = quant_payload
        v_path.write_text(json.dumps(v_existing, indent=2), encoding="utf-8")
        log.info("Versioned Quant JSON updated -> %s", v_path)
 
 
def write_scored_levels_txt(
    ticker: str,
    scored: Any,  # ScoredLevels
    path: Path | None = None,
    versioned: bool = False,
    snapshot_suffix: str | None = None,
) -> None:
    """
    Export ScoredLevels as Pine Script-compatible TXT.
    
    Format per level:  STRIKE:FILTER|SIG|LABEL
    First token gets:  TICKER:STRIKE:FILTER|SIG|LABEL
    
    Encoding:
      FILTER: W = MechanicalWall, A = StructuralAnchor, I = InflectionPoint, X = other
      SIG:    P = PRIMARY, S = SECONDARY, C = CONTEXT
      LABEL:  Human-readable, compact. Includes filter-specific metrics:
              - Walls:   "CW 18%BK" or "PW 22%BK" or "0D CW" or "HW"
              - Anchors: "JHEQX C 14d" or "UNK 3.2σ P 45d" 
              - Inflect: "ZERO GEX" or "CLIFF UP" or "VOID LOW" or "MAGNET"
    
    Only PRIMARY and SECONDARY levels are exported (CONTEXT stays in JSON for dashboard).
    """
    # Import here to avoid circular deps at module level
    from .level_scorer import MechanicalWall, StructuralAnchor, InflectionPoint
 
    if path is None:
        from .config import SCORED_LEVELS_TXT
        path = SCORED_LEVELS_TXT
 
    tokens: list[str] = []
 
    for tl in scored.tagged_levels:
        # Skip CONTEXT — too noisy for chart
        if tl.significance == "CONTEXT":
            continue
 
        sig = {"PRIMARY": "P", "SECONDARY": "S"}.get(tl.significance, "C")
 
        if isinstance(tl, MechanicalWall):
            filt = "W"
            # Build compact wall label
            # Map field_name to short prefix
            prefix_map = {
                "call_wall":     "CW",
                "put_wall":      "PW",
                "call_wall_0dte": "0D CW",
                "put_wall_0dte":  "0D PW",
                "hedge_wall":    "HW",
                "local_call_node": "LOC C",
                "local_put_node":  "LOC P",
                "max_gex_strike":  "MAX GEX",
            }
            short = prefix_map.get(tl.field_name, tl.label[:8])
            # Append book depth % if available
            if tl.pct_of_book > 0:
                label = f"{short} {tl.pct_of_book * 100:.0f}%BK"
            else:
                label = short
 
        elif isinstance(tl, StructuralAnchor):
            filt = "A"
            prog = tl.matched_program if tl.matched_program else "UNK"
            if prog == "UNK" and tl.oi_zscore > 0:
                prog = f"UNK {tl.oi_zscore:.1f}σ"
            side_char = tl.side[0] if tl.side else "N"
            dte_str = f"{tl.days_to_expiry}d" if tl.days_to_expiry > 0 else ""
            # Include relevance for ACTIVE/CRITICAL
            rel = ""
            if tl.relevance in ("ACTIVE", "CRITICAL"):
                rel = f" [{tl.relevance[:4]}]"
            label = f"{prog} {side_char} {dte_str}{rel}".strip()
 
        elif isinstance(tl, InflectionPoint):
            filt = "I"
            # Map inflection types to compact labels
            type_map = {
                "FLIP":   "ZERO GEX" if "zero" in tl.field_name.lower() else "FLIP",
                "MAGNET": "MAGNET",
                "CLIFF":  f"CLIFF {'UP' if 'up' in tl.field_name.lower() else 'DN'}",
                "VOID":   f"VOID {'LO' if 'lower' in tl.field_name.lower() else 'HI'}",
            }
            label = type_map.get(tl.inflection_type, tl.label[:10])
 
        else:
            filt = "X"
            label = tl.label[:12]
 
        tokens.append(f"{tl.strike:.2f}:{filt}|{sig}|{label}")
 
    if not tokens:
        log.info("No scored levels to write for %s", ticker)
        return
 
    # First token gets ticker prefix (matching existing Pine parser convention)
    tokens[0] = f"{ticker}:{tokens[0]}"
 
    final_string = ", ".join(tokens)
 
    # Use robust upsert to prevent data loss for other tickers in partial runs
    _upsert_ticker_line(path, ticker, final_string)
 
    if versioned:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        v_path = path.with_name(f"{path.stem}_{ts}{path.suffix}")
        _upsert_ticker_line(v_path, ticker, final_string)
        log.info("Versioned scored levels TXT written -> %s", v_path)

    if snapshot_suffix:
        s_path = path.with_name(f"{path.stem}_{snapshot_suffix}{path.suffix}")
        _upsert_ticker_line(s_path, ticker, final_string)
        log.info("Snapshot scored levels TXT written -> %s", s_path)

    log.info("Scored levels TXT appended for %s → %s (%d levels)", ticker, path, len(tokens))
 