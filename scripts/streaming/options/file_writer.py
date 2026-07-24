"""
file_writer.py
==============
Persist translated levels to JSON and TXT, including copy-ready string format
and interpretation text for alerts / pre-open planning.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    DAILY_LEVELS_JSON, 
    DAILY_LEVELS_TXT, 
    GEX_PROFILES_JSON, 
    LIVE_TREND_JSON,
    MACRO_LEVELS_TXT,
    MACRO_QUANT_JSON,
    MAX_VISIBLE_DTE_DAYS,
    DEFAULT_NEAR_DUPLICATE_TOLERANCE,
    NEAR_DUPLICATE_TOLERANCE_BY_TICKER,
    UNIFIED_LEVELS_TXT,
    UNIFIED_LEVELS_JSON,
    SCORED_LEVELS_TXT,
    ENABLE_UNIFIED_MACRO_EXTENSIONS,
    SHOW_FAR_MACRO_LEVELS,
    MACRO_EXTENSION_BAND_PCT,
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

log = logging.getLogger(__name__)

# Baseline front-EM percent used to scale duplicate suppression tolerance.
# Example: if front EM is 4% and baseline is 2%, tolerance scales 2x.
_FRONT_EM_BASELINE_PCT: float = 0.02
_FRONT_EM_SCALE_MIN: float = 0.6
_FRONT_EM_SCALE_MAX: float = 2.0
 
 
def _sidecar_path(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.stem}_{suffix}{path.suffix}")


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


def _snapshot_month_bucket(snapshot_suffix: str) -> str:
    match = re.match(r"^(\d{8})_\d{4}$", snapshot_suffix)
    if match:
        date_part = match.group(1)
        return f"{date_part[:4]}-{date_part[4:6]}"
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _snapshot_history_path(path: Path, snapshot_suffix: str) -> Path:
    month_bucket = _snapshot_month_bucket(snapshot_suffix)
    return path.parent / "history" / month_bucket / f"{path.stem}_{snapshot_suffix}{path.suffix}"


def _current_path(path: Path) -> Path:
    return path.parent / "current" / path.name


def _sync_current_txt(path: Path, text: str) -> Path:
    current_path = _current_path(path)
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_text(text, encoding="utf-8")
    return current_path


def _snapshot_hhmm(snapshot_suffix: str) -> str | None:
    match = re.match(r"^(?:\d{8}_)?(\d{4})$", snapshot_suffix)
    return match.group(1) if match else None
 

def _get_strength(tl):
    if isinstance(tl, MechanicalWall):
        return round(tl.pct_of_book, 4)
    if isinstance(tl, StructuralAnchor):
        return round(tl.oi_zscore, 2)
    if isinstance(tl, InflectionPoint):
        return round(tl.slope_magnitude, 4)
    return 0.0


def _front_em_pct(scored: Any) -> float | None:
    """Estimate front expected-move percent from scored.expected_moves."""
    ems = [em for em in getattr(scored, "expected_moves", []) if getattr(em, "dte", None) is not None]
    if not ems:
        return None
    front = min(ems, key=lambda em: em.dte)
    em_value = float(getattr(front, "em_value", 0.0) or 0.0)
    em_upper = float(getattr(front, "em_upper", 0.0) or 0.0)
    em_lower = float(getattr(front, "em_lower", 0.0) or 0.0)
    center = (em_upper + em_lower) / 2.0
    if em_value <= 0.0 or abs(center) < 1e-9:
        return None
    return abs(em_value) / abs(center)


def _scaled_duplicate_tolerance(
    ticker: str,
    scored: Any,
    near_duplicate_tolerance: float | None,
) -> float:
    """Return ticker tolerance scaled by front expected-move percent."""
    base = (
        near_duplicate_tolerance
        if near_duplicate_tolerance is not None
        else NEAR_DUPLICATE_TOLERANCE_BY_TICKER.get(ticker, DEFAULT_NEAR_DUPLICATE_TOLERANCE)
    )
    if base <= 0:
        return base

    em_pct = _front_em_pct(scored)
    if em_pct is None:
        return base

    ratio = em_pct / _FRONT_EM_BASELINE_PCT if _FRONT_EM_BASELINE_PCT > 0 else 1.0
    scale = max(_FRONT_EM_SCALE_MIN, min(_FRONT_EM_SCALE_MAX, ratio))
    return base * scale

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
    ("zero_gamma_delta_adj", "Zero Gamma (DA)"),
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
        f"── {tl.cash_ticker} -> {tag} {'─' * 40}",
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
        f"  ATM IV (0DTE)      : {tl.atm_iv*100:,.1f}%" if tl.atm_iv else "  ATM IV (0DTE)      : —",
        f"  Daily Vol Change   : {tl.iv_change*100:+.1f}%",
        "",
        f"  ── Key Levels ───────────────────────────────",
        f"  Upper EM           : {fmt(tl.em_upper)}",
        f"  Absolute Call Wall : {fmt(tl.call_wall)}",
        f"  Local Call Node    : {fmt(tl.local_call_node)}",
        f"  0DTE Call Wall     : {fmt(tl.call_wall_0dte)}",
        f"  Zero Gamma         : {fmt(tl.zero_gamma)}",
        f"  Zero Gamma (DA)    : {fmt(tl.zero_gamma_delta_adj)}",
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
    txt_path: Path | None = DAILY_LEVELS_TXT,
    txt_mode: str = "daily",
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

    # Market structure summary — CASH-FIRST (ETF-scale, not futures-translated).
    # The market_structure should use cash/ETF DealerLevels as the primary source.
    # TranslatedLevels (futures-scale) are only used for tickers that have no
    # cash version (e.g., pure futures like /ES without an ETF proxy).
    market_structure: list[dict[str, Any]] = []

    # Build a lookup of cash levels by ticker for quick access
    cash_levels_lookup: dict[str, Any] = {}
    for levels in cash_levels or []:
        cash_levels_lookup[levels.ticker] = levels

    # Build a lookup of translated levels by cash_ticker for translation metadata
    # (futures_symbol, basis_ratio, translation_mode, futures_price, cash_spot)
    tl_by_cash: dict[str, Any] = {}
    for tl in translated_levels:
        if tl.cash_ticker:
            tl_by_cash[tl.cash_ticker] = tl

    # 1. Add cash levels FIRST (ETF-scale) — these are the primary source
    cash_tickers_seen = set()
    for levels in cash_levels or []:
        cash_tickers_seen.add(levels.ticker)
        # Read translation metadata from the DealerLevels object directly.
        # translate_to_futures() attaches futures_symbol, basis_ratio,
        # translation_mode, basis_spread to the DealerLevels before
        # constructing the TranslatedLevels. This survives RTD replacement.
        market_structure.append({
            "asset": levels.ticker,
            "cash_ticker": levels.ticker,
            # Translation metadata (for ETF→futures scaling by consumers)
            "futures_symbol": getattr(levels, 'futures_symbol', None),
            "translation_mode": getattr(levels, 'translation_mode', None),
            "basis_ratio": getattr(levels, 'basis_ratio', None),
            "futures_price": getattr(levels, 'futures_price', None),
            "cash_spot": getattr(levels, 'spot', None),
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
            "wall_scope": getattr(levels, "wall_scope", "UNSPECIFIED"),
            "wall_dte_min": getattr(levels, "wall_dte_min", 0),
            "wall_dte_max": getattr(levels, "wall_dte_max", 0),
            "concentration_score": getattr(levels, "concentration_score", 0.0),
            "call_wall_oi": getattr(levels, "call_wall_oi", 0),
            "put_wall_oi": getattr(levels, "put_wall_oi", 0),
            "pin_strike_oi": getattr(levels, "pin_strike_oi", 0),
            "hedge_flow": {
                "up_10": getattr(levels, "hedge_flow_up_10", 0.0),
                "up_25": getattr(levels, "hedge_flow_up_25", 0.0),
                "up_50": getattr(levels, "hedge_flow_up_50", 0.0),
                "dn_10": getattr(levels, "hedge_flow_dn_10", 0.0),
                "dn_25": getattr(levels, "hedge_flow_dn_25", 0.0),
                "dn_50": getattr(levels, "hedge_flow_dn_50", 0.0),
            },
            "hourly_flow_curve": getattr(levels, "hourly_flow_curve", []),
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
                    "straddle": em.straddle,
                    "em85_upper": getattr(em, 'straddle_85_upper', 0.0),
                    "em85_lower": getattr(em, 'straddle_85_lower', 0.0),
                }
                for em in getattr(levels, 'expected_moves', [])
            ],
            "coach_note": build_coaches_note(levels.ticker, levels),
            "tactical_plan": build_plan(levels.ticker, levels)
        })

    # 2. Add translated levels ONLY for tickers not already covered by cash levels
    #    (e.g., pure futures symbols like /ES that don't have an ETF proxy)
    for tl in translated_levels:
        if tl.cash_ticker in cash_tickers_seen:
            continue  # already covered by cash (ETF-scale) version
        market_structure.append({
            "asset": cash_tag(tl.futures_symbol),
            "cash_ticker": tl.cash_ticker,
            "futures_symbol": tl.futures_symbol,
            "translation_mode": tl.translation_mode,
            "basis_ratio": tl.basis_ratio,
            "futures_price": tl.futures_price,
            "cash_spot": tl.cash_spot,
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
            "wall_scope": getattr(tl, "wall_scope", "UNSPECIFIED"),
            "wall_dte_min": getattr(tl, "wall_dte_min", 0),
            "wall_dte_max": getattr(tl, "wall_dte_max", 0),
            "concentration_score": getattr(tl, "concentration_score", 0.0),
            "call_wall_oi": getattr(tl, "call_wall_oi", 0),
            "put_wall_oi": getattr(tl, "put_wall_oi", 0),
            "pin_strike_oi": getattr(tl, "pin_strike_oi", 0),
            "hedge_flow": {
                "up_10": getattr(tl, "hedge_flow_up_10", 0.0),
                "up_25": getattr(tl, "hedge_flow_up_25", 0.0),
                "up_50": getattr(tl, "hedge_flow_up_50", 0.0),
                "dn_10": getattr(tl, "hedge_flow_dn_10", 0.0),
                "dn_25": getattr(tl, "hedge_flow_dn_25", 0.0),
                "dn_50": getattr(tl, "hedge_flow_dn_50", 0.0),
            },
            "hourly_flow_curve": getattr(tl, "hourly_flow_curve", []),
            "call_volume_centroid": tl.call_volume_centroid,
            "put_volume_centroid": tl.put_volume_centroid,
            "call_centroid": tl.call_volume_centroid,
            "put_centroid": tl.put_volume_centroid,
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
                    "straddle": em.straddle,
                    "em85_upper": getattr(em, 'straddle_85_upper', 0.0),
                    "em85_lower": getattr(em, 'straddle_85_lower', 0.0),
                }
                for em in tl.expected_moves
            ],
            "coach_note": build_coaches_note(cash_tag(tl.futures_symbol) if tl.futures_symbol else cash_tag(tl.cash_ticker), tl),
            "tactical_plan": build_plan(cash_tag(tl.futures_symbol) if tl.futures_symbol else cash_tag(tl.cash_ticker), tl)
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
    log.debug("JSON written -> %s  (%d levels)", json_path, len(all_entries))

    if versioned:
        v_json_path = _sidecar_path(json_path, "versioned")
        v_json_path.write_text(json_data, encoding="utf-8")
        log.debug("Versioned JSON written -> %s", v_json_path)

    if snapshot_suffix:
        s_json_path = _sidecar_path(json_path, snapshot_suffix)
        s_json_path.write_text(json_data, encoding="utf-8")
        log.debug("Snapshot JSON written -> %s (overwrites daily)", s_json_path)

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
        elif tl and tl.translation_mode == "additive" and tl.basis_spread is not None:
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
    log.debug("GEX Profiles written -> %s", GEX_PROFILES_JSON)

    if versioned:
        v_profiles_path = _sidecar_path(GEX_PROFILES_JSON, "versioned")
        v_profiles_path.write_text(profiles_data, encoding="utf-8")
        log.debug("Versioned GEX Profiles written -> %s", v_profiles_path)

    if snapshot_suffix:
        s_profiles_path = _sidecar_path(GEX_PROFILES_JSON, snapshot_suffix)
        s_profiles_path.write_text(profiles_data, encoding="utf-8")
        log.debug("Snapshot GEX Profiles written -> %s", s_profiles_path)

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
        log.debug("Live Trend written -> %s  (RTH only)", LIVE_TREND_JSON)
    else:
        log.debug("Skipping live_trend.json update — outside RTH.")

    # ── TXT output ─────────────────────────────────────────────────────────
    if txt_mode == "macro":
        lines: list[str] = [
            f"Macro Dealer Levels — {run_label}",
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

        # Concise macro-specific section. Keep this focused on structural levels.
        lines.extend(["", "Macro Tagged Levels (PRIMARY/SECONDARY)", ""])
        for sl in scored_levels or []:
            lines.append(f"{sl.ticker} [{sl.view_mode}]  Regime={sl.regime}  Bias={sl.bias}")
            emitted = 0
            for tl in sl.tagged_levels:
                if tl.significance == "CONTEXT":
                    continue
                lines.append(
                    f"  - {tl.strike:.2f} | {tl.significance} | {tl.side} | {tl.label}"
                )
                emitted += 1
            if emitted == 0:
                lines.append("  - no primary/secondary levels")
            lines.append("")
    else:
        lines = [
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

    if txt_path:
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_data = "\n".join(lines)
        txt_path.write_text(txt_data, encoding="utf-8")
        log.debug("TXT written  -> %s", txt_path)
        current_txt_path = _sync_current_txt(txt_path, txt_data)
        log.debug("Current TXT mirror written -> %s", current_txt_path)

        if versioned:
            v_txt_path = _sidecar_path(txt_path, "versioned")
            v_txt_path.write_text(txt_data, encoding="utf-8")
            log.debug("Versioned TXT written -> %s", v_txt_path)

        if snapshot_suffix:
            s_txt_path = _snapshot_history_path(txt_path, snapshot_suffix)
            s_txt_path.parent.mkdir(parents=True, exist_ok=True)
            s_txt_path.write_text(txt_data, encoding="utf-8")
            log.debug("Snapshot TXT written -> %s", s_txt_path)


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

    if levels.get("zero_gamma_delta_adj"):
        tokens.append(f"{levels['zero_gamma_delta_adj']:.2f}:Zero Gamma DA")

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
        v_path = _sidecar_path(path, "versioned")
        _upsert_ticker_line(v_path, ticker, final_string)
        
    log.debug("Macro Levels written to %s (versioned=%s)", path, versioned)


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
        "zero_gamma_delta_adj": levels.get("zero_gamma_delta_adj"),
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
    log.debug("Quant JSON updated for %s -> %s", ticker, path)

    if versioned:
        v_path = _sidecar_path(path, "versioned")
        # Note: if multiple tickers call this with versioned=True in one run,
        # we'd want to read the versioned file first.
        # But for simplicity, if it's the same run, the versioned file name should be identical.
        v_existing = {}
        if v_path.exists():
            try: v_existing = json.loads(v_path.read_text(encoding="utf-8"))
            except: pass
        v_existing[ticker] = quant_payload
        v_path.write_text(json.dumps(v_existing, indent=2), encoding="utf-8")
        log.debug("Versioned Quant JSON updated -> %s", v_path)
 
 
def write_scored_levels_txt(
    ticker: str,
    scored: Any,  # ScoredLevels
    metadata_levels: Any | None = None,
    path: Path | None = None,
    versioned: bool = False,
    snapshot_suffix: str | None = None,
    max_visible_dte_days: int = MAX_VISIBLE_DTE_DAYS,
    near_duplicate_tolerance: float | None = None,
    include_structural_tokens: bool = True,
    include_meta_tokens: bool = True,
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
              - Anchors: "JHEQX C 14d" or "OI NODE 3.2σ P 45d" 
              - Inflect: "ZERO GEX" or "CLIFF UP" or "VOID LOW" or "MAGNET"
    
    Only PRIMARY and SECONDARY levels are exported (CONTEXT stays in JSON for dashboard).
    """
    if path is None:
        from .config import SCORED_LEVELS_TXT
        path = SCORED_LEVELS_TXT

    tolerance = _scaled_duplicate_tolerance(
        ticker=ticker,
        scored=scored,
        near_duplicate_tolerance=near_duplicate_tolerance,
    )
 
    tokens = _build_scored_tokens(
        scored,
        max_visible_dte_days=max_visible_dte_days,
        near_duplicate_tolerance=tolerance,
    )
 
    if not tokens:
        log.debug("No scored levels to write for %s", ticker)
        return

    source_levels = metadata_levels if metadata_levels is not None else scored
    seen_tokens = set(tokens)

    if include_structural_tokens:
        for token in _extract_structural_tokens_from_copy_line(ticker, source_levels):
            if token in seen_tokens:
                continue
            tokens.append(token)
            seen_tokens.add(token)

    if include_meta_tokens:
        tokens.extend(_extract_meta_tokens_from_copy_line(ticker, source_levels))
 
    # First token gets ticker prefix (matching existing Pine parser convention)
    tokens[0] = f"{ticker}:{tokens[0]}"
 
    final_string = ", ".join(tokens)
 
    # Use robust upsert to prevent data loss for other tickers in partial runs
    _upsert_ticker_line(path, ticker, final_string)

    # Keep a stable current-day mirror for user workflows.
    current_path = _current_path(path)
    _upsert_ticker_line(current_path, ticker, final_string)
 
    if versioned:
        v_path = _sidecar_path(path, "versioned")
        _upsert_ticker_line(v_path, ticker, final_string)
        log.debug("Versioned scored levels TXT written -> %s", v_path)

    if snapshot_suffix:
        s_path = _snapshot_history_path(path, snapshot_suffix)
        s_path.parent.mkdir(parents=True, exist_ok=True)
        _upsert_ticker_line(s_path, ticker, final_string)
        log.debug("Snapshot scored levels TXT written -> %s", s_path)

    log.debug("Scored levels TXT appended for %s -> %s (%d levels)", ticker, path, len(tokens))


def _build_scored_tokens(
    scored: Any,
    max_visible_dte_days: int,
    near_duplicate_tolerance: float,
) -> list[str]:
    from .level_scorer import MechanicalWall, StructuralAnchor, InflectionPoint

    emitted_strikes: list[float] = []
    tokens: list[str] = []

    # Day-trader priority: explicit EM and EM85 markers for ALL expiries
    # through Friday, so the unified levels always show the full weekly EM
    # term structure (daily EM for Mon-Fri).
    ems = sorted(
        [em for em in getattr(scored, "expected_moves", []) if getattr(em, "dte", None) is not None],
        key=lambda em: em.dte,
    )
    for em in ems:
        dte_tag = f" {em.dte}d" if getattr(em, "dte", None) is not None else ""
        em_tokens: list[tuple[float, str]] = [
            (round(float(em.em_upper), 2), f"E|P|EM HI{dte_tag}"),
            (round(float(em.em_lower), 2), f"E|P|EM LO{dte_tag}"),
        ]
        if hasattr(em, "straddle_85_upper") and em.straddle_85_upper > 0:
            em_tokens.extend([
                (round(float(em.straddle_85_upper), 2), f"E|P|EM85 HI{dte_tag}"),
                (round(float(em.straddle_85_lower), 2), f"E|P|EM85 LO{dte_tag}"),
            ])
        for strike, meta in em_tokens:
            tokens.append(f"{strike:.2f}:{meta}")
            emitted_strikes.append(strike)

    for tl in scored.tagged_levels:
        is_kept_context_inflection = False
        if tl.significance == "CONTEXT":
            # Keep directional inflections in compact payloads so Pine can render
            # Gamma Flip zone and Gamma Cliff rails. Drop other context noise.
            is_kept_context_inflection = (
                isinstance(tl, InflectionPoint)
                and (
                    str(getattr(tl, "inflection_type", "")).upper() == "CLIFF"
                    or "gamma_flip" in str(getattr(tl, "field_name", "")).lower()
                )
            )
            if not is_kept_context_inflection:
                continue

        if isinstance(tl, InflectionPoint) and "zero_gamma" in str(getattr(tl, "field_name", "")).lower():
            is_kept_context_inflection = True

        if isinstance(tl, StructuralAnchor) and tl.days_to_expiry > max_visible_dte_days:
            continue

        if (
            near_duplicate_tolerance > 0
            and not is_kept_context_inflection
            and any(abs(tl.strike - existing) <= near_duplicate_tolerance for existing in emitted_strikes)
        ):
            continue

        sig = {"PRIMARY": "P", "SECONDARY": "S"}.get(tl.significance, "C")

        if isinstance(tl, MechanicalWall):
            filt = "W"
            prefix_map = {
                "call_wall": "CW",
                "put_wall": "PW",
                "call_wall_0dte": "0D CW",
                "put_wall_0dte": "0D PW",
                "hedge_wall": "HW",
                "local_call_node": "LOC C",
                "local_put_node": "LOC P",
                "max_gex_strike": "MAX GEX",
            }
            short = prefix_map.get(tl.field_name, tl.label[:8])
            label = f"{short} {tl.pct_of_book * 100:.0f}%BK" if tl.pct_of_book > 0 else short
        elif isinstance(tl, StructuralAnchor):
            filt = "A"
            prog = tl.matched_program if tl.matched_program else "OI NODE"
            if not tl.matched_program and tl.oi_zscore > 0:
                prog = f"OI NODE {tl.oi_zscore:.1f}σ"
            side_char = tl.side[0] if tl.side else "N"
            dte_str = f"{tl.days_to_expiry}d" if tl.days_to_expiry > 0 else ""
            rel = f" [{tl.relevance[:4]}]" if tl.relevance in ("ACTIVE", "CRITICAL") else ""
            label = f"{prog} {side_char} {dte_str}{rel}".strip()
        elif isinstance(tl, InflectionPoint):
            filt = "I"
            field_l = tl.field_name.lower()
            if "zero_gamma_delta_adj" in field_l:
                label = "ZERO GEX DA"
            elif "zero" in field_l:
                label = "ZERO GEX"
            elif "gamma_flip_upper" in field_l:
                label = "FLIP UP"
            elif "gamma_flip_lower" in field_l:
                label = "FLIP DN"
            elif str(tl.inflection_type).upper() == "CLIFF":
                label = f"CLIFF {'UP' if 'up' in field_l else 'DN'}"
            elif str(tl.inflection_type).upper() == "MAGNET":
                label = "MAGNET"
            elif str(tl.inflection_type).upper() == "VOID":
                label = f"VOID {'LO' if 'lower' in field_l else 'HI'}"
            else:
                label = tl.label[:10]
        else:
            filt = "X"
            label = tl.label[:12]

        tokens.append(f"{tl.strike:.2f}:{filt}|{sig}|{label}")
        emitted_strikes.append(tl.strike)

    return tokens


def build_scored_levels_line(
    ticker: str,
    scored: Any,
    max_visible_dte_days: int = MAX_VISIBLE_DTE_DAYS,
    near_duplicate_tolerance: float | None = None,
) -> str | None:
    tolerance = _scaled_duplicate_tolerance(
        ticker=ticker,
        scored=scored,
        near_duplicate_tolerance=near_duplicate_tolerance,
    )

    tokens = _build_scored_tokens(
        scored,
        max_visible_dte_days=max_visible_dte_days,
        near_duplicate_tolerance=tolerance,
    )
    if not tokens:
        return None
    tokens[0] = f"{ticker}:{tokens[0]}"
    return ", ".join(tokens)


def _parse_scored_token(token: str) -> tuple[float, str, str, str] | None:
    strike_str, sep, meta = token.partition(":")
    if not sep:
        return None
    parts = meta.split("|", 2)
    if len(parts) != 3:
        return None
    try:
        strike = round(float(strike_str), 2)
    except ValueError:
        return None
    filt, sig, label = parts
    return strike, filt, sig, label


def _format_scored_token(strike: float, filt: str, sig: str, label: str) -> str:
    return f"{strike:.2f}:{filt}|{sig}|{label}"


def _extract_meta_tokens_from_copy_line(ticker: str, levels: Any) -> list[str]:
    """Extract 0:META_* tokens from copy_ready_line output for unified payloads."""
    try:
        copy_line = copy_ready_line(ticker, levels)
    except Exception as exc:  # pragma: no cover - defensive guard
        log.debug("Failed to derive META tokens for %s: %s", ticker, exc)
        return []

    _, sep, payload = copy_line.partition(": ")
    if not sep:
        return []

    tokens = [chunk.strip() for chunk in payload.split(",") if chunk.strip()]
    return [token for token in tokens if ":META_" in token]


def _legacy_level_to_unified_token(token: str) -> str | None:
    strike_str, sep, label = token.partition(":")
    if not sep:
        return None

    try:
        strike = round(float(strike_str.strip()), 2)
    except ValueError:
        return None

    norm = label.strip().upper()
    mapping: dict[str, tuple[str, str, str]] = {
        "ABSOLUTE CALL WALL": ("W", "P", "CW"),
        "ABSOLUTE PUT WALL":  ("W", "P", "PW"),
        "ZERO GAMMA":         ("I", "P", "ZERO GEX"),
        "ZERO GAMMA (Δ-ADJ)": ("I", "P", "ZERO GEX DA"),
        "LOCAL CALL NODE": ("W", "S", "LOC C"),
        "LOCAL PUT NODE": ("W", "S", "LOC P"),
        "0DTE CALL WALL": ("W", "S", "0D CW"),
        "0DTE PUT WALL": ("W", "S", "0D PW"),
        "DEX CALL NODE": ("W", "S", "DEX C"),
        "DEX PUT NODE": ("W", "S", "DEX P"),
        "HEDGE WALL": ("W", "S", "HW"),
        "MAX PAIN": ("A", "S", "MAX"),
        "GAMMA MAGNET": ("I", "C", "MAGNET"),
        "PIN STRIKE": ("A", "S", "PIN"),
    }
    mapped = mapping.get(norm)
    if mapped is None:
        return None
    filt, sig, compact_label = mapped
    return _format_scored_token(strike, filt, sig, compact_label)


def _extract_structural_tokens_from_copy_line(ticker: str, levels: Any) -> list[str]:
    """Promote dashboard-critical legacy levels into unified tokens for one-paste mode."""
    try:
        copy_line = copy_ready_line(ticker, levels)
    except Exception as exc:  # pragma: no cover - defensive guard
        log.debug("Failed to derive structural tokens for %s: %s", ticker, exc)
        return []

    _, sep, payload = copy_line.partition(": ")
    if not sep:
        return []

    tokens = [chunk.strip() for chunk in payload.split(",") if chunk.strip()]
    structural_tokens: list[str] = []
    for token in tokens:
        if ":META_" in token:
            continue
        mapped = _legacy_level_to_unified_token(token)
        if mapped is not None:
            structural_tokens.append(mapped)
    return structural_tokens


def translate_unified_tokens_to_futures(proxy_ticker: str, target_ticker: str, tokens: list[str]) -> list[str]:
    """Translates a list of unified levels tokens from an equity ETF proxy (QQQ, SPY) 
    or index (SPX) to its corresponding futures ticker (NQ, ES).
    """
    ratio = None
    basis = None
    for token in tokens:
        if token.startswith("0:META_FUTURES_RATIO_") or (":" in token and token.split(":", 1)[1].startswith("META_FUTURES_RATIO_")):
            parts = token.split(":")
            meta_part = parts[1] if len(parts) > 1 else parts[0]
            try:
                ratio = float(meta_part.split("_")[-1])
            except ValueError:
                pass
        elif token.startswith("0:META_FUTURES_BASIS_") or (":" in token and token.split(":", 1)[1].startswith("META_FUTURES_BASIS_")):
            parts = token.split(":")
            meta_part = parts[1] if len(parts) > 1 else parts[0]
            try:
                basis = float(meta_part.split("_")[-1])
            except ValueError:
                pass

    if ratio is None and basis is None:
        # Fallback hardcoded ratios for ETF→futures when no META_ token is present.
        # These are approximate and used only as a last-resort perspective view.
        if proxy_ticker == "QQQ" and target_ticker == "NQ":
            ratio = 40.0
        elif proxy_ticker in ("SPY", "SPX") and target_ticker == "ES":
            if proxy_ticker == "SPY":
                ratio = 10.0
            else:
                basis = 0.0
        else:
            return []

    translated_tokens = []
    for token in tokens:
        if not token:
            continue
        if ":" not in token:
            translated_tokens.append(token)
            continue

        parts = token.split(":", 1)
        price_str, content = parts[0], parts[1]

        # Check if it's a numeric level token
        is_level = False
        try:
            val = float(price_str)
            if val > 0:
                is_level = True
        except ValueError:
            pass

        if is_level:
            price_val = float(price_str)
            if ratio is not None:
                new_price = price_val * ratio
            else:
                new_price = price_val + basis
            translated_tokens.append(f"{new_price:.2f}:{content}")
        else:
            # It's a metadata token (price_str == "0") or header
            if content.startswith("META_"):
                # We need to scale numeric values in metadata
                keys_to_scale = [
                    "META_OGT_", "META_VOL_EXPANSION_UP_", "META_VOL_EXPANSION_DN_",
                    "META_S_TRIG_", "META_L_TRIG_", "META_S_TGT_", "META_L_TGT_",
                    "META_S_INV_", "META_L_INV_", "META_OI_CALLWALL_", "META_OI_PUTWALL_",
                    "META_OI_PIN_"
                ]
                scaled = False
                for key in keys_to_scale:
                    if content.startswith(key):
                        val_str = content[len(key):]
                        sub_label = ""
                        if ":" in val_str:
                            sub_val_str, sub_label = val_str.split(":", 1)
                        else:
                            sub_val_str = val_str
                        try:
                            val_float = float(sub_val_str)
                            if ratio is not None:
                                new_val = val_float * ratio
                            else:
                                new_val = val_float + basis
                            if "META_OI_" in key:
                                new_val_str = f"{int(round(new_val))}"
                            else:
                                new_val_str = f"{new_val:.2f}"
                                
                            if sub_label:
                                new_content = f"{key}{new_val_str}:{sub_label}"
                            else:
                                new_content = f"{key}{new_val_str}"
                            translated_tokens.append(f"0:{new_content}")
                            scaled = True
                        except ValueError:
                            pass
                        break
                if not scaled:
                    translated_tokens.append(token)
            else:
                translated_tokens.append(token)

    return translated_tokens


def _compose_unified_tokens_for_ticker(
    ticker: str,
    scored: Any,
    *,
    max_visible_dte_days: int,
    near_duplicate_tolerance: float,
    macro_scored: Any | None = None,
    metadata_levels: Any | None = None,
    macro_spot: float | None = None,
    enable_macro_extensions: bool = ENABLE_UNIFIED_MACRO_EXTENSIONS,
    show_far_macro: bool = SHOW_FAR_MACRO_LEVELS,
    macro_extension_band_pct: float = MACRO_EXTENSION_BAND_PCT,
) -> list[str]:
    base_tokens = _build_scored_tokens(
        scored,
        max_visible_dte_days=max_visible_dte_days,
        near_duplicate_tolerance=near_duplicate_tolerance,
    )
    if not base_tokens:
        return []

    owner_strikes: set[float] = set()
    merged_tokens: list[str] = []
    for token in base_tokens:
        parsed = _parse_scored_token(token)
        if not parsed:
            continue
        strike, filt, sig, label = parsed
        owner_strikes.add(strike)
        merged_tokens.append(_format_scored_token(strike, filt, sig, label))

    if enable_macro_extensions and macro_scored is not None:
        macro_tokens = _build_scored_tokens(
            macro_scored,
            max_visible_dte_days=max_visible_dte_days,
            near_duplicate_tolerance=near_duplicate_tolerance,
        )
        for token in macro_tokens:
            parsed = _parse_scored_token(token)
            if not parsed:
                continue
            strike, filt, sig, label = parsed
            if strike in owner_strikes:
                continue

            if macro_spot and macro_spot > 0:
                dist_pct = abs(strike - macro_spot) / macro_spot
                if dist_pct > macro_extension_band_pct:
                    if not show_far_macro:
                        continue
                    label = f"{label} [FAR]"
                else:
                    label = f"{label} [MEXT]"
            else:
                label = f"{label} [MEXT]"

            owner_strikes.add(strike)
            merged_tokens.append(_format_scored_token(strike, filt, sig, label))

    structural_source = metadata_levels if metadata_levels is not None else scored
    seen_tokens = set(merged_tokens)
    for token in _extract_structural_tokens_from_copy_line(ticker, structural_source):
        if token in seen_tokens:
            continue
        merged_tokens.append(token)
        seen_tokens.add(token)

    # Carry tactical/dashboard metadata so Pine can load full briefing from unified text.
    meta_source = metadata_levels if metadata_levels is not None else scored
    merged_tokens.extend(_extract_meta_tokens_from_copy_line(ticker, meta_source))

    return merged_tokens


def write_unified_levels_txt(
    scored_levels: list[Any],
    path: Path = UNIFIED_LEVELS_TXT,
    versioned: bool = False,
    snapshot_suffix: str | None = None,
    max_visible_dte_days: int = MAX_VISIBLE_DTE_DAYS,
    macro_scored_levels: list[Any] | None = None,
    metadata_levels_by_ticker: dict[str, Any] | None = None,
    macro_spot_by_ticker: dict[str, float] | None = None,
    enable_macro_extensions: bool = ENABLE_UNIFIED_MACRO_EXTENSIONS,
    show_far_macro: bool = SHOW_FAR_MACRO_LEVELS,
    macro_extension_band_pct: float = MACRO_EXTENSION_BAND_PCT,
    enable_futures_fallbacks: bool = True,
) -> None:
    scored_lookup = {s.ticker: s for s in scored_levels}
    macro_lookup = {s.ticker: s for s in (macro_scored_levels or [])}
    lines: list[str] = []
    for ticker in sorted(scored_lookup.keys()):
        tolerance = NEAR_DUPLICATE_TOLERANCE_BY_TICKER.get(ticker, DEFAULT_NEAR_DUPLICATE_TOLERANCE)
        tokens = _compose_unified_tokens_for_ticker(
            ticker,
            scored_lookup[ticker],
            max_visible_dte_days=max_visible_dte_days,
            near_duplicate_tolerance=tolerance,
            macro_scored=macro_lookup.get(ticker),
            metadata_levels=metadata_levels_by_ticker.get(ticker) if metadata_levels_by_ticker else None,
            macro_spot=(macro_spot_by_ticker or {}).get(ticker),
            enable_macro_extensions=enable_macro_extensions,
            show_far_macro=show_far_macro,
            macro_extension_band_pct=macro_extension_band_pct,
        )
        # Sanitize tokens to prevent delimiter corruption
        clean_tokens = []
        for t in tokens:
            # Remove any unintended carriage returns or commas inside the token
            cleaned = t.replace("\r\n", " ").replace("\n", " ").replace(",", "")
            if cleaned:
                clean_tokens.append(cleaned)
                
        if not clean_tokens:
            continue
            
        clean_tokens[0] = f"{ticker}:{clean_tokens[0]}"
        lines.append(", ".join(clean_tokens))

        # Generate translated NQ entry from QQQ (backup/perspective view)
        # RTD-native tickers (NQ, ES) should NOT get SPY/QQQ-translated fallbacks
        # when missing — that produces fake levels indistinguishable from real RTD data.
        if enable_futures_fallbacks and ticker == "QQQ" and "NQ" not in scored_lookup:
            log.warning("NQ missing from scored levels — generating QQQ-translated fallback (NOT RTD-native)")
            nq_tokens = translate_unified_tokens_to_futures("QQQ", "NQ", tokens)
            if nq_tokens:
                clean_nq = [t.replace("\r\n", " ").replace("\n", " ").replace(",", "") for t in nq_tokens if t]
                clean_nq = [t for t in clean_nq if t]
                if clean_nq:
                    clean_nq[0] = f"NQ:{clean_nq[0]}"
                    lines.append(", ".join(clean_nq))
                    
        # Generate translated ES entry from SPY (backup/perspective view)
        if enable_futures_fallbacks and (ticker == "SPY" or (ticker == "SPX" and "SPY" not in scored_lookup)) and "ES" not in scored_lookup:
            log.warning("ES missing from scored levels — generating SPY-translated fallback (NOT RTD-native)")
            es_tokens = translate_unified_tokens_to_futures(ticker, "ES", tokens)
            if es_tokens:
                clean_es = [t.replace("\r\n", " ").replace("\n", " ").replace(",", "") for t in es_tokens if t]
                clean_es = [t for t in clean_es if t]
                if clean_es:
                    clean_es[0] = f"ES:{clean_es[0]}"
                    lines.append(", ".join(clean_es))

    text = "\n".join(lines)
    final_text = text + ("\n" if text else "")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final_text, encoding="utf-8")
        log.debug("Unified levels TXT written -> %s (%d tickers)", path, len(lines))
    except IOError as e:
        log.error("Failed to write unified levels main file: %s", e)

    try:
        current_path = _sync_current_txt(path, final_text)
        log.debug("Current unified TXT mirror written -> %s", current_path)
    except IOError as e:
        log.error("Failed to write current unified TXT mirror: %s", e)

    if versioned:
        try:
            v_path = _sidecar_path(path, "versioned")
            v_path.write_text(final_text, encoding="utf-8")
            log.debug("Versioned unified levels TXT written -> %s", v_path)
        except IOError as e:
            log.error("Failed to write versioned unified levels TXT: %s", e)

    if snapshot_suffix:
        try:
            s_path = _snapshot_history_path(path, snapshot_suffix)
            s_path.parent.mkdir(parents=True, exist_ok=True)
            s_path.write_text(final_text, encoding="utf-8")
            log.debug("Snapshot unified levels TXT written -> %s", s_path)
        except IOError as e:
            log.error("Failed to write snapshot unified levels TXT: %s", e)

        try:
            hhmm = _snapshot_hhmm(snapshot_suffix)
            if hhmm in {"0930", "1615"}:
                alias_name = f"{path.stem}_{'open' if hhmm == '0930' else 'close'}{path.suffix}"
                alias_path = path.parent / "current" / alias_name
                alias_path.parent.mkdir(parents=True, exist_ok=True)
                alias_path.write_text(final_text, encoding="utf-8")
                log.debug("Current unified session alias written -> %s", alias_path)
        except IOError as e:
            log.error("Failed to write current unified session alias: %s", e)


def _parse_unified_line(line: str) -> dict[str, Any]:
    tokens = [chunk.strip() for chunk in line.split(",") if chunk.strip()]
    if not tokens:
        return {"ticker": "", "line": line, "token_count": 0, "tokens": []}

    first = tokens[0]
    first_parts = first.split(":", 2)
    if len(first_parts) != 3:
        return {"ticker": "", "line": line, "token_count": len(tokens), "tokens": []}

    ticker = first_parts[0].strip()
    normalized: list[str] = [f"{first_parts[1]}:{first_parts[2]}"] + tokens[1:]
    parsed_tokens: list[dict[str, Any]] = []

    for token in normalized:
        strike_part, _, meta = token.partition(":")
        if not _:
            continue
        parts = meta.split("|", 2)
        if len(parts) != 3:
            continue
        filt, sig, label = parts
        try:
            strike = round(float(strike_part), 2)
        except ValueError:
            continue
        parsed_tokens.append(
            {
                "strike": strike,
                "filter": filt,
                "significance": sig,
                "label": label,
                "raw": token,
            }
        )

    return {
        "ticker": ticker,
        "line": line,
        "token_count": len(parsed_tokens),
        "tokens": parsed_tokens,
    }


def write_unified_levels_json(
    scored_levels: list[Any],
    path: Path = UNIFIED_LEVELS_JSON,
    versioned: bool = False,
    snapshot_suffix: str | None = None,
    max_visible_dte_days: int = MAX_VISIBLE_DTE_DAYS,
    macro_scored_levels: list[Any] | None = None,
    metadata_levels_by_ticker: dict[str, Any] | None = None,
    macro_spot_by_ticker: dict[str, float] | None = None,
    enable_macro_extensions: bool = ENABLE_UNIFIED_MACRO_EXTENSIONS,
    show_far_macro: bool = SHOW_FAR_MACRO_LEVELS,
    macro_extension_band_pct: float = MACRO_EXTENSION_BAND_PCT,
    enable_futures_fallbacks: bool = True,
) -> None:
    scored_lookup = {s.ticker: s for s in scored_levels}
    macro_lookup = {s.ticker: s for s in (macro_scored_levels or [])}
    lines: list[str] = []
    for ticker in sorted(scored_lookup.keys()):
        tolerance = NEAR_DUPLICATE_TOLERANCE_BY_TICKER.get(ticker, DEFAULT_NEAR_DUPLICATE_TOLERANCE)
        tokens = _compose_unified_tokens_for_ticker(
            ticker,
            scored_lookup[ticker],
            max_visible_dte_days=max_visible_dte_days,
            near_duplicate_tolerance=tolerance,
            macro_scored=macro_lookup.get(ticker),
            metadata_levels=metadata_levels_by_ticker.get(ticker) if metadata_levels_by_ticker else None,
            macro_spot=(macro_spot_by_ticker or {}).get(ticker),
            enable_macro_extensions=enable_macro_extensions,
            show_far_macro=show_far_macro,
            macro_extension_band_pct=macro_extension_band_pct,
        )
        if not tokens:
            continue
        # Save clean tokens before ticker prefix is prepended — needed for
        # the ETF→futures translation fallback below.
        clean_tokens = list(tokens)
        tokens[0] = f"{ticker}:{tokens[0]}"
        lines.append(", ".join(tokens))

        # Generate translated NQ entry from QQQ — only if no direct RTD entry exists
        if enable_futures_fallbacks and ticker == "QQQ" and "NQ" not in scored_lookup:
            log.warning("NQ missing from scored levels — generating QQQ-translated fallback (NOT RTD-native)")
            nq_tokens = translate_unified_tokens_to_futures("QQQ", "NQ", clean_tokens)
            if nq_tokens:
                nq_tokens[0] = f"NQ:{nq_tokens[0]}"
                lines.append(", ".join(nq_tokens))

        # Generate translated ES entry from SPY — only if no direct RTD entry exists
        if enable_futures_fallbacks and (ticker == "SPY" or (ticker == "SPX" and "SPY" not in scored_lookup)) and "ES" not in scored_lookup:
            log.warning("ES missing from scored levels — generating SPY-translated fallback (NOT RTD-native)")
            es_tokens = translate_unified_tokens_to_futures(ticker, "ES", clean_tokens)
            if es_tokens:
                es_tokens[0] = f"ES:{es_tokens[0]}"
                lines.append(", ".join(es_tokens))

    rows = [_parse_unified_line(line) for line in lines]
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "scored_levels",
        "tickers": rows,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    json_data = json.dumps(doc, indent=2)
    path.write_text(json_data, encoding="utf-8")
    log.debug("Unified levels JSON written -> %s (%d tickers)", path, len(rows))

    if versioned:
        v_path = _sidecar_path(path, "versioned")
        v_path.write_text(json_data, encoding="utf-8")
        log.debug("Versioned unified levels JSON written -> %s", v_path)

    if snapshot_suffix:
        s_path = _sidecar_path(path, snapshot_suffix)
        s_path.write_text(json_data, encoding="utf-8")
        log.debug("Snapshot unified levels JSON written -> %s", s_path)


def unified_payload_fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "bytes": 0, "sha256": "", "lines": 0}

    data = path.read_bytes()
    line_count = sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
    return {
        "exists": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "lines": line_count,
    }
 