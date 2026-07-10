"""
formatting.py
=============
Shared formatting helpers for dealer-level outputs.

Both ``discord_notifier`` and ``file_writer`` import from here so that
copy-ready strings, level selectors, and trade-plan narratives are
defined once and stay consistent across all output channels.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from .config import get_ticker_profile
from .state_tracker import load_previous_state


# ---------------------------------------------------------------------------
# Protocol so helpers work with both TranslatedLevels and DealerLevels
# without importing either (avoids circular deps).
# ---------------------------------------------------------------------------

@runtime_checkable
class HasLevels(Protocol):
    """Structural type for any object that carries dealer-level attributes."""
    em_upper: float | None
    em_lower: float | None
    em_value: float
    call_wall: float | None
    put_wall: float | None
    local_call_node: float | None
    local_put_node: float | None
    call_wall_0dte: float | None
    put_wall_0dte: float | None
    dex_call_node: float | None
    dex_put_node: float | None
    gamma_flip_upper: float | None
    gamma_flip_lower: float | None
    gamma_cliff_up: float | None
    gamma_cliff_down: float | None
    zero_gamma: float | None
    zero_gamma_delta_adj: float | None
    opening_gap_target: float | None
    max_pain: float | None
    hedge_wall: float | None
    total_gex: float
    gex_regime: str
    secondary_call_wall: float | None
    secondary_put_wall: float | None
    vol_trigger_upper_05: float | None
    vol_trigger_lower_05: float | None
    vol_trigger_upper_10: float | None
    vol_trigger_lower_10: float | None
    vol_trigger_upper_15: float | None
    vol_trigger_lower_15: float | None
    vanna_call_node: float | None
    vanna_put_node: float | None
    charm_call_node: float | None
    charm_put_node: float | None
    volume_imbalance_call_node: float | None
    volume_imbalance_put_node: float | None
    liquidity_vacuum_lower: float | None
    liquidity_vacuum_upper: float | None
    skew_pivot_put_25d: float | None
    skew_pivot_call_25d: float | None
    # Tier 2
    gamma_magnet: float | None
    pin_strike: float | None
    pin_odds: float
    wall_separation: float | None
    regime_label: str
    directional_bias: str
    call_gamma_total: float
    put_gamma_total: float
    net_vanna_exposure: float
    wall_scope: str
    wall_dte_min: int
    wall_dte_max: int
    concentration_score: float
    call_wall_oi: int
    put_wall_oi: int
    pin_strike_oi: int
    net_speed_exposure: float | None
    hedge_flow_up_10: float
    hedge_flow_up_25: float
    hedge_flow_up_50: float
    hedge_flow_dn_10: float
    hedge_flow_dn_25: float
    hedge_flow_dn_50: float
    hourly_flow_curve: list[Any]
    total_gex_delta_adj: float | None
    expected_moves: list[Any]
    # Stability metrics
    call_gex_0dte: float | None = None
    put_gex_0dte: float | None = None
    # IV & Skew
    atm_iv: float | None = None
    iv_change: float = 0.0
    volatility_skew_premium: float | None = None


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def fmt(value: float | None, decimals: int = 2) -> str:
    """Format a float for display, returning ``'N/A'`` for ``None``."""
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


def fmt_copy(value: float | None) -> str:
    """Format a float for copy-ready Pine Script strings (no comma grouping)."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Level selectors
# ---------------------------------------------------------------------------

def first_level(*values: float | None) -> float | None:
    """Return the first non-None value, or ``None``."""
    for value in values:
        if value is not None:
            return value
    return None


def nearest_below(reference: float | None, *values: float | None) -> float | None:
    """Return the highest value strictly below *reference*."""
    if reference is None:
        return first_level(*values)
    candidates = [v for v in values if v is not None and v < reference]
    if not candidates:
        return None
    return max(candidates)


def nearest_above(reference: float | None, *values: float | None) -> float | None:
    """Return the lowest value strictly above *reference*."""
    if reference is None:
        return first_level(*values)
    candidates = [v for v in values if v is not None and v > reference]
    if not candidates:
        return None
    return min(candidates)


# ---------------------------------------------------------------------------
# Copy-ready Pine Script strings
#
# These produce the colon-delimited format consumed by the TradingView
# indicator:  ``TAG: price1:Label1, price2:Label2, ...``
#
# The 16 levels here match the Pine Script indicator's input order.
# ---------------------------------------------------------------------------

# Canonical level ordering for the copy-ready string.
_COPY_LEVEL_SPEC: list[tuple[str, str]] = [
    ("em_upper",          "Upper EM"),
    ("call_wall",         "Absolute Call Wall"),
    ("local_call_node",   "Local Call Node"),
    ("call_wall_0dte",    "0DTE Call Wall"),
    ("dex_call_node",     "DEX Call Node"),
    ("gamma_flip_upper",  "Gamma Flip Upper"),
    ("gamma_cliff_up",    "Gamma Cliff Up"),
    ("zero_gamma",        "Zero Gamma"),
    ("gamma_cliff_down",  "Gamma Cliff Down"),
    ("gamma_flip_lower",  "Gamma Flip Lower"),
    ("max_pain",          "Max Pain"),
    ("put_wall_0dte",     "0DTE Put Wall"),
    ("local_put_node",    "Local Put Node"),
    ("dex_put_node",      "DEX Put Node"),
    ("hedge_wall",        "Hedge Wall"),
    ("em_lower",          "Lower EM"),
    # ── Tier 2: included for Pine dashboard ──
    ("gamma_magnet",      "Gamma Magnet"),
    ("pin_strike",        "Pin Strike"),
]


def futures_tag(futures_symbol: str) -> str:
    """Normalise a futures symbol to always start with ``/``."""
    return futures_symbol if futures_symbol.startswith("/") else f"/{futures_symbol}"


def cash_tag(futures_symbol: str) -> str:
    """Normalise a futures symbol to the bare ticker (no leading ``/``)."""
    return futures_symbol.lstrip("/")


# ---------------------------------------------------------------------------
# Trade-plan narrative
#
# This is the single source of truth for the interpretation / pre-open plan
# used by both Discord embeds and the TXT file.  Both channels get the same
# underlying analysis; the rendering can differ (Discord is more compact).
# ---------------------------------------------------------------------------

def _calculate_tactical_levels(levels: HasLevels) -> dict[str, float | None]:
    """
    Centralized logic for determining tactical triggers, targets, and invalidations.
    Shared by build_plan (Discord) and copy_ready_line (TradingView).
    """
    ref_price = getattr(levels, 'spot', None) or getattr(levels, 'futures_price', None)
    em = levels.em_value if levels.em_value > 0 else 1.0
    active_zg = getattr(levels, 'zero_gamma_delta_adj', None) or levels.zero_gamma

    regime = levels.regime_label
    is_positive_gex = (levels.total_gex >= 0)
    is_short_gamma = not is_positive_gex
    
    # Track B: Premium/Discount Fade
    if regime in ["PINNED", "BATTLE_ZONE"] and is_positive_gex:
        l_trig = first_level(levels.em_lower, levels.put_wall_0dte)
        s_trig = first_level(levels.em_upper, levels.call_wall_0dte)
        l_tgt = levels.gamma_magnet
        s_tgt = levels.gamma_magnet

        # Fix the boundary inversion by routing stop-losses to out-of-bounds volatility metrics:
        l_inv = first_level(levels.vol_trigger_lower_05, levels.em_lower * 0.998)
        s_inv = first_level(levels.vol_trigger_upper_05, levels.em_upper * 1.002)
    else:
        # Track A: Breakout Expansion
        l_trig = first_level(levels.call_wall_0dte, levels.call_wall, levels.em_upper)
        s_trig = first_level(levels.put_wall_0dte, levels.put_wall, levels.em_lower)
        l_tgt = nearest_above(l_trig, levels.vol_trigger_upper_05, levels.em_upper)
        s_tgt = nearest_below(s_trig, levels.vol_trigger_lower_05, levels.em_lower)

    # Fallbacks to guarantee non-None if levels exist
    if s_trig is None:
        s_trig = first_level(active_zg, levels.gamma_flip_lower, levels.put_wall_0dte)
    if l_trig is None:
        l_trig = first_level(levels.call_wall, levels.gamma_flip_upper, active_zg)
    if s_tgt is None:
        s_tgt = nearest_below(s_trig, levels.put_wall_0dte, levels.local_put_node, levels.hedge_wall, levels.em_lower)
    if l_tgt is None:
        l_tgt = nearest_above(l_trig, levels.max_pain, levels.em_upper)

    # ── Precision Invalidations ──
    if is_short_gamma:
        s_inv = nearest_above(s_trig, active_zg, levels.gamma_flip_upper, levels.call_wall_0dte, levels.local_call_node)
        if s_inv is None or s_inv == s_trig:
            s_inv = nearest_above(s_trig, active_zg, levels.gamma_flip_upper, levels.call_wall_0dte, levels.call_wall, levels.em_upper)
            
        l_inv = nearest_below(l_trig, active_zg, levels.gamma_flip_lower, levels.put_wall_0dte, levels.local_put_node)
        if l_inv is None or l_inv == l_trig:
            l_inv = nearest_below(l_trig, active_zg, levels.gamma_flip_lower, levels.put_wall_0dte, levels.put_wall, levels.em_lower)
    else:
        s_inv = nearest_above(s_trig, active_zg, levels.gamma_flip_upper, levels.call_wall_0dte, levels.call_wall, levels.em_upper)
        l_inv = nearest_below(l_trig, active_zg, levels.gamma_flip_lower, levels.put_wall_0dte, levels.put_wall, levels.em_lower)

    return {
        "s_trig": s_trig, "l_trig": l_trig,
        "s_tgt": s_tgt,   "l_tgt": l_tgt,
        "s_inv": s_inv,   "l_inv": l_inv
    }


def build_plan(
    tag: str,
    levels: HasLevels,
    *,
    extended: bool = False,
) -> list[str]:
    """Build a structured trade-plan narrative."""
    f = fmt_copy
    ref_price = getattr(levels, 'spot', None) or getattr(levels, 'futures_price', None)
    
    tactical = _calculate_tactical_levels(levels)
    s_trig, l_trig = tactical["s_trig"], tactical["l_trig"]
    s_tgt, l_tgt = tactical["s_tgt"], tactical["l_tgt"]
    s_inv, l_inv = tactical["s_inv"], tactical["l_inv"]

    regime_tone = (
        "sellers have structural control" if levels.gex_regime == "NEGATIVE"
        else "buyers have structural control"
    )
    
    regime_specific_context = {
        "PINNED": "Expect high mean-reversion and 'sticky' price action near the magnet.",
        "TRENDING": "Expect directional expansion; gamma traps are active and fuel moves.",
        "COILED": "Energy is building in a tight range; expect a violent breakout soon.",
        "BATTLE_ZONE": "Institutional walls are actively capping price; expect sharp rotations.",
        "NEUTRAL": "Structure is balanced; monitor for early directional signs."
    }.get(levels.regime_label, "")

    zg_context = ""
    active_zg = getattr(levels, 'zero_gamma_delta_adj', None) or levels.zero_gamma
    if active_zg is not None and ref_price is not None:
        zg_dist = active_zg - ref_price
        direction = "above" if zg_dist > 0 else "below"
        # Only show distance if it's significant (>0.5 EM)
        em = levels.em_value if levels.em_value > 0 else 1.0
        if abs(zg_dist) > 0.5 * em:
            zg_label = "Zero Gamma (DA)" if getattr(levels, 'zero_gamma_delta_adj', None) is not None else "Zero Gamma"
            zg_context = f" Note: {zg_label} ({f(active_zg)}) is {abs(zg_dist):.0f} pts {direction}."

    if extended:
        return [
            f"{tag} Narrative Plan:",
            f"- Context: {tag} {levels.regime_label} ({levels.gex_regime} GEX). {regime_specific_context} Dealers providing '{regime_tone}' environment.{zg_context}",
            f"- Watch: Short trigger {f(s_trig)}, Long trigger {f(l_trig)}, GF {f(levels.gamma_flip_lower)}↔{f(levels.gamma_flip_upper)}.",
            f"- Base-case (Short): Below {f(s_trig)}, target {f(s_tgt)}. Invalidation: hold above {f(s_inv)}.",
            f"- Alternate (Long): Above {f(l_trig)}, target {f(l_tgt)}. Invalidation: lose {f(l_inv)}.",
            f"- Risk map: ±1.0σ Expected Move is {f(levels.em_lower)} ↔ {f(levels.em_upper)}.",
        ]
    else:
        return [
            f"Context: {tag} {levels.regime_label} ({levels.gex_regime}); {regime_specific_context}{zg_context}",
            f"Watch: Short {f(s_trig)}, Long {f(l_trig)}, GF {f(levels.gamma_flip_lower)}↔{f(levels.gamma_flip_upper)}.",
            f"Base: Below {f(s_trig)} → {f(s_tgt)}; Inv: >{f(s_inv)}.",
            f"Alt: Above {f(l_trig)} → {f(l_tgt)}; Inv: <{f(l_inv)}.",
            f"Risk: EM {f(levels.em_lower)}↔{f(levels.em_upper)}.",
        ]


# ---------------------------------------------------------------------------
# Traffic Light — single "should I trade?" signal
# ---------------------------------------------------------------------------

def traffic_light(levels: HasLevels) -> tuple[str, str]:
    """
    Synthesise all signals into a single go/caution/stop recommendation.

    Returns
    -------
    tuple[str, str]
        (color, explanation)  where color is "GREEN", "YELLOW", or "RED".
    """
    # RED: data too thin to trust
    critical_none = sum(
        1 for v in [levels.call_wall, levels.put_wall, levels.zero_gamma, levels.gamma_magnet]
        if v is None
    )
    if critical_none >= 2:
        return "RED", "Insufficient structural data — stand down until liquidity nodes resolve."

    if levels.wall_separation is not None and levels.wall_separation < 3.0:
        return "RED", "Wall separation <3 pts. Market is non-tradable; stand down."

    # YELLOW: transitional or hard-to-trade conditions
    if levels.regime_label == "COILED":
        return "YELLOW", (
            "COILED regime — market is compressed. High-velocity breakout imminent. "
            "Wait for a definitive level break before deployment."
        )

    if levels.pin_odds < 0.08 and levels.regime_label != "PINNED":
        return "YELLOW", (
            "Diffuse gamma landscape. Gravitational anchors are weak; levels may be porous. "
            "Reduce sizing."
        )

    if levels.regime_label == "NEUTRAL":
        return "YELLOW", "Regime stabilization in progress. Trade for context, not size."

    # GREEN: clear regime with actionable structure
    if levels.regime_label == "PINNED":
        return "GREEN", (
            "PINNED regime — positive GEX environment. Dealers providing deep liquidity. "
            "Favor mean-reversion at the walls."
        )

    if levels.regime_label == "TRENDING":
        return "GREEN", (
            "TRENDING regime — negative GEX acceleration. Trend-follow environment. "
            "Dealers forced to chase; join directional moves on retests."
        )
    if levels.regime_label == "BATTLE_ZONE":
        return "GREEN", (
            "BATTLE_ZONE regime — institutional extremes active. Expect wide, two-way rotation. "
            "Trade wall-to-wall with trailing stops."
        )

    return "YELLOW", "Mixed signals — trade with caution."


def copy_ready_line(tag: str, levels: Any) -> str:
    """
    Build a copy-ready string for *levels* prefixed by *tag*.
    This version includes full narrative metadata for the TradingView dashboard.
    """
    parts = []
    for attr, label in _COPY_LEVEL_SPEC:
        if attr == "zero_gamma":
            zg_da = getattr(levels, "zero_gamma_delta_adj", None)
            if zg_da is not None:
                parts.append(f"{fmt_copy(zg_da)}:Zero Gamma (Δ-Adj)")
            else:
                parts.append(f"{fmt_copy(getattr(levels, attr, None))}:{label}")
        else:
            parts.append(f"{fmt_copy(getattr(levels, attr, None))}:{label}")
    
    # ── Multi-Expiry Expected Moves ──
    ems = getattr(levels, "expected_moves", [])
    for em in ems:
        prefix = f"{em.expiry} ({em.dte}d) "
        parts.append(f"{fmt_copy(em.em_upper)}:{prefix}Upper EM")
        parts.append(f"{fmt_copy(em.em_lower)}:{prefix}Lower EM")
        if hasattr(em, 'straddle_85_upper') and em.straddle_85_upper > 0:
            parts.append(f"{fmt_copy(em.straddle_85_upper)}:{prefix}Upper 85% Straddle")
            parts.append(f"{fmt_copy(em.straddle_85_lower)}:{prefix}Lower 85% Straddle")

    weekly_upper = getattr(levels, "weekly_scope_upper", None)
    weekly_lower = getattr(levels, "weekly_scope_lower", None)
    weekly_85_upper = getattr(levels, "weekly_scope_85_upper", None)
    weekly_85_lower = getattr(levels, "weekly_scope_85_lower", None)
    weekly_expiry = getattr(levels, "weekly_scope_expiry", None)
    if weekly_upper is not None and weekly_lower is not None:
        parts.append(f"{fmt_copy(weekly_upper)}:Weekly Scope Upper EM")
        parts.append(f"{fmt_copy(weekly_lower)}:Weekly Scope Lower EM")
        if weekly_85_upper is not None and weekly_85_upper > 0:
            parts.append(f"{fmt_copy(weekly_85_upper)}:Weekly Scope Upper 85% Straddle")
            parts.append(f"{fmt_copy(weekly_85_lower)}:Weekly Scope Lower 85% Straddle")
        if weekly_expiry:
            parts.append(f"0:META_WEEKLY_SCOPE_EXPIRY_{weekly_expiry}")

    # ── METADATA for Pine Script ──
    regime = getattr(levels, "regime_label", "NEUTRAL")
    bias = getattr(levels, "directional_bias", "NEUTRAL")
    parts.append(f"0:META_REGIME_{regime}")
    parts.append(f"0:META_BIAS_{bias}")
    parts.append(f"0:META_OGT_{fmt_copy(getattr(levels, 'opening_gap_target', None))}")
    
    # Greeks as metadata for dashboard rows
    vanna = getattr(levels, "net_vanna_exposure", 0.0)
    charm = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0.0
    parts.append(f"0:META_VANNA_{vanna:.2f}")
    parts.append(f"0:META_CHARM_{charm:.2f}")
    parts.append("0:META_SPEED_0.00")
    parts.append(f"0:META_HFLOW_UP10_{getattr(levels, 'hedge_flow_up_10', 0.0):.2f}")
    parts.append(f"0:META_HFLOW_DN10_{getattr(levels, 'hedge_flow_dn_10', 0.0):.2f}")
    parts.append(f"0:META_HFLOW_UP25_{getattr(levels, 'hedge_flow_up_25', 0.0):.2f}")
    parts.append(f"0:META_HFLOW_DN25_{getattr(levels, 'hedge_flow_dn_25', 0.0):.2f}")
    parts.append(f"0:META_HFLOW_UP50_{getattr(levels, 'hedge_flow_up_50', 0.0):.2f}")
    parts.append(f"0:META_HFLOW_DN50_{getattr(levels, 'hedge_flow_dn_50', 0.0):.2f}")
    
    total_gex = getattr(levels, "total_gex", 0.0)
    gex_da = getattr(levels, "total_gex_delta_adj", 0.0) or 0.0
    parts.append(f"0:META_GEX_DA_{gex_da:.2f}")
    parts.append(f"0:META_GEX_TOTAL_{total_gex:.2f}")

    # Stability & Integrity
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    stability = (abs(gex_0dte) / abs(total_gex)) if total_gex != 0 else 0.0
    concentration = float(getattr(levels, "concentration_score", 0.0) or 0.0)
    concentration = min(1.0, max(0.0, concentration))
    parts.append(f"0:META_STABILITY_{stability:.2f}")
    parts.append(f"0:META_CONCENTRATION_{concentration:.2f}")
    parts.append(f"0:META_INTEGRITY_{concentration:.2f}")
    parts.append(f"0:META_WALL_SCOPE_{getattr(levels, 'wall_scope', 'UNSPECIFIED')}")
    parts.append(f"0:META_OI_CALLWALL_{int(getattr(levels, 'call_wall_oi', 0) or 0)}")
    parts.append(f"0:META_OI_PUTWALL_{int(getattr(levels, 'put_wall_oi', 0) or 0)}")
    parts.append(f"0:META_OI_PIN_{int(getattr(levels, 'pin_strike_oi', 0) or 0)}")
    oi_vel = _oi_velocity_snapshot(tag, levels)
    parts.append(f"0:META_OI_VEL_CW_STATUS_{oi_vel['cw'][0]}")
    parts.append(f"0:META_OI_VEL_PW_STATUS_{oi_vel['pw'][0]}")
    parts.append(f"0:META_OI_VEL_PIN_STATUS_{oi_vel['pin'][0]}")
    parts.append(f"0:META_OI_VEL_CW_RATE_{oi_vel['cw'][1]:.2f}")
    parts.append(f"0:META_OI_VEL_PW_RATE_{oi_vel['pw'][1]:.2f}")
    parts.append(f"0:META_OI_VEL_PIN_RATE_{oi_vel['pin'][1]:.2f}")

    # IV & Skew
    atm_iv = getattr(levels, "atm_iv", 0.0) or 0.0
    iv_chg = getattr(levels, "iv_change", 0.0)
    skew = getattr(levels, "volatility_skew_premium", 0.0) or 0.0
    parts.append(f"0:META_IV_{atm_iv:.4f}")
    parts.append(f"0:META_IVCHG_{iv_chg:.4f}")
    parts.append(f"0:META_SKEW_{skew:.4f}")

    # Futures Translation
    if getattr(levels, "translation_mode", None) == "additive":
        parts.append(f"0:META_FUTURES_BASIS_{getattr(levels, 'basis_spread')}")
    elif getattr(levels, "translation_mode", None) == "multiplicative":
        parts.append(f"0:META_FUTURES_RATIO_{getattr(levels, 'basis_ratio')}")

    # Vol Triggers (Vol Expansion Boundaries)
    vol_up_05 = getattr(levels, "vol_trigger_upper_05", None)
    vol_dn_05 = getattr(levels, "vol_trigger_lower_05", None)
    if vol_up_05: parts.append(f"0:META_VOL_EXPANSION_UP_{vol_up_05:.2f}")
    if vol_dn_05: parts.append(f"0:META_VOL_EXPANSION_DN_{vol_dn_05:.2f}")



    # Synchronized Tactical Plan (Shared Logic)
    f = fmt_copy
    tactical = _calculate_tactical_levels(levels)
    
    regime = getattr(levels, "regime_label", "NEUTRAL")
    is_positive_gex = (getattr(levels, "total_gex", 0.0) >= 0)
    
    if regime in ["PINNED", "BATTLE_ZONE"] and is_positive_gex:
        parts.append(f"0:META_S_TRIG_{f(tactical['s_trig'])}:► SELL PREMIUM ZONE (Look for Short Rejection)")
        parts.append(f"0:META_L_TRIG_{f(tactical['l_trig'])}:► BUY DISCOUNT ZONE (Look for Long Rejection)")
    else:
        parts.append(f"0:META_S_TRIG_{f(tactical['s_trig'])}")
        parts.append(f"0:META_L_TRIG_{f(tactical['l_trig'])}")
    parts.append(f"0:META_S_TGT_{f(tactical['s_tgt'])}")
    parts.append(f"0:META_L_TGT_{f(tactical['l_tgt'])}")
    parts.append(f"0:META_S_INV_{f(tactical['s_inv'])}")
    parts.append(f"0:META_L_INV_{f(tactical['l_inv'])}")

    # Add condensed Coach's Note for visual dashboard
    note = build_pine_note(levels)
    parts.append(f"0:META_NOTE_{note}")

    return f"{tag}: " + ", ".join(parts)


def build_pine_note(levels: HasLevels) -> str:
    """Generate a high-signal tactical summary for the Pine Script dashboard."""
    regime = levels.regime_label
    bias = levels.directional_bias
    iv_chg = levels.iv_change
    skew = levels.volatility_skew_premium or 0.0
    ref_price = getattr(levels, "spot", None) or getattr(levels, "futures_price", None)
    
    # Market Mood Emoji
    mood = "🛡️" if regime == "PINNED" else "🚀" if regime == "TRENDING" else "🔄" if regime == "BATTLE_ZONE" else "⚡" if regime == "COILED" else "⚪"
    
    # Core strategy per regime
    strategies = {
        "PINNED": "Mean-Reversion Profile. Fade extremes toward Magnet.",
        "TRENDING": "Momentum Profile. Follow expansion; do not fade walls.",
        "COILED": "Breakout Profile. Energy building; wait for level break.",
        "BATTLE_ZONE": "Rotation Profile. Wide auction; trade wall-to-wall.",
        "NEUTRAL": "Transition Profile. Structure resetting; watch primary nodes."
    }
    base = strategies.get(regime, "Context: Neutral.")
    
    # Add Greek/Institutional modifiers
    mods = []
    
    # Vanna impact (Squeeze vs Expansion)
    vanna = levels.net_vanna_exposure
    if abs(vanna) > 1.5:
        if vanna > 0:
            mods.append("🌊 Vanna Squeeze" if iv_chg < 0 else "📈 Vanna Support")
        else:
            mods.append("💨 Vanna Drag" if iv_chg < 0 else "📉 Vanna Expansion")
    
    # Charm impact (Afternoon Drift)
    charm_net = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0
    if abs(charm_net) > 5.0: 
         mods.append("⏳ Afternoon Drift" if charm_net > 0 else "⚡ Afternoon Weight")

    # Expected hedge flow stress (day-trading scenario sensitivity)
    flow_25 = max(
        abs(getattr(levels, "hedge_flow_up_25", 0.0) or 0.0),
        abs(getattr(levels, "hedge_flow_dn_25", 0.0) or 0.0),
    )
    if flow_25 > 50_000_000:
        mods.append("🏎️ Hedge Flow Sensitive")

    # Concentration-aware structure metric [0,1]
    concentration = float(getattr(levels, "concentration_score", 0.0) or 0.0)
    concentration = min(1.0, max(0.0, concentration))
    if concentration < 0.35:
        mods.append("🕳️ Porous Structure")
    elif concentration > 0.7:
        mods.append("🧱 Solid Integrity")

    # Liquidity Vacuum (Gap Risk)
    gf_up = levels.gamma_flip_upper
    gf_dn = levels.gamma_flip_lower
    wall_c = levels.call_wall
    wall_p = levels.put_wall
    if ref_price and gf_up and wall_c and gf_up < ref_price < wall_c:
        mods.append("🕳️ Gap Risk Up")
    if ref_price and gf_dn and wall_p and wall_p < ref_price < gf_dn:
        mods.append("🕳️ Gap Risk Dn")

    # IV/Skew modifiers
    if iv_chg > 0.02: mods.append("📈 Vol Expansion")
    elif iv_chg < -0.02: mods.append("📉 Vol Crush")
    
    if skew > 0.05: mods.append("🛡️ Put Demand")
    elif skew < -0.05: mods.append("💎 Call Demand")

    total_gex = getattr(levels, "total_gex", 0.0)
    # Stability (0DTE concentration)
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    if total_gex != 0 and (abs(gex_0dte) / abs(total_gex)) > 0.5:
        mods.append("⚠️ Gamma Trap Sensitive (0DTE)")

    if levels.pin_odds > 0.15:
        mods.append(f"🎯 Pin {levels.pin_odds:.0%}")
    
    # Proximity Check (Dynamic based on Spot)
    mod_str = f" | {' '.join(mods)}" if mods else ""
    return f"{mood} [{bias}] {base}{mod_str}"


def _fmt_flow(value: float) -> str:
    abs_m = abs(value) / 1_000_000.0
    side = "Dealer Buy" if value >= 0 else "Dealer Sell"
    return f"{side} ${abs_m:.1f}M"


def _snapshot_delta_line(tag: str, levels: HasLevels) -> str:
    tz = ZoneInfo("America/New_York")
    now_et = datetime.now(tz)
    generated_at = now_et.strftime("%Y-%m-%d %H:%M ET")
    previous = load_previous_state()
    if previous is None:
        return f"**SNAPSHOT:** {generated_at} (fresh) | Δ vs prior: N/A"

    prev_key = tag
    prev = previous.tickers.get(prev_key)
    if prev is None:
        prev = previous.tickers.get(tag.lstrip("/"))
    if prev is None:
        return f"**SNAPSHOT:** {generated_at} (fresh) | Δ vs prior: N/A"

    try:
        prev_ts = datetime.fromisoformat(previous.timestamp.replace("Z", "+00:00")).astimezone(tz)
        age_min = max(0, int((now_et - prev_ts).total_seconds() // 60))
    except Exception:
        age_min = 0

    cw_now = getattr(levels, "call_wall", None)
    pw_now = getattr(levels, "put_wall", None)
    pin_now = getattr(levels, "pin_strike", None)

    def _delta(curr: float | None, prior: float | None) -> str:
        if curr is None or prior is None:
            return "N/A"
        return f"{curr - prior:+.2f}"

    return (
        f"**SNAPSHOT:** {generated_at} ({age_min}m from prior) | "
        f"ΔCallWall {_delta(cw_now, prev.call_wall)} | "
        f"ΔPutWall {_delta(pw_now, prev.put_wall)} | "
        f"ΔPin {_delta(pin_now, prev.pin_strike)}"
    )


def _profile_key_for_tag(tag: str) -> str:
    clean = tag.lstrip("/").upper()
    if clean == "ES":
        return "SPX"
    if clean == "NQ":
        return "NDX"
    if clean == "RTY":
        return "IWM"
    if clean == "YM":
        return "DIA"
    return clean


def _oi_velocity_thresholds(profile: Any) -> tuple[float, float]:
    canon = str(getattr(profile, "canonical_name", "")).upper()
    index_family = {"SPX", "SPY", "NDX", "QQQ", "RUT", "RTY", "IWM", "DIA", "DJI"}
    large_index = {"SPX", "SPY", "NDX", "QQQ"}

    if canon in large_index:
        abs_mult = 0.10
        pct_mult = 1.00
    elif canon in index_family:
        abs_mult = 0.14
        pct_mult = 1.15
    elif getattr(profile, "futures_target", None) is not None:
        abs_mult = 0.16
        pct_mult = 1.20
    else:
        abs_mult = 0.22
        pct_mult = 1.35

    abs_threshold = max(10.0, float(profile.min_oi_floor) * abs_mult, float(profile.book_depth_contracts) * 0.01)
    pct_threshold = max(0.001, float(profile.flow_significance_pct) / 60.0 * pct_mult)
    return abs_threshold, pct_threshold


def _oi_velocity_snapshot(tag: str, levels: HasLevels) -> dict[str, tuple[str, float]]:
    previous = load_previous_state()
    if previous is None:
        return {"cw": ("N/A", 0.0), "pw": ("N/A", 0.0), "pin": ("N/A", 0.0)}

    prev = previous.tickers.get(tag) or previous.tickers.get(tag.lstrip("/"))
    if prev is None:
        return {"cw": ("N/A", 0.0), "pw": ("N/A", 0.0), "pin": ("N/A", 0.0)}

    tz = ZoneInfo("America/New_York")
    now_et = datetime.now(tz)
    try:
        prev_ts = datetime.fromisoformat(previous.timestamp.replace("Z", "+00:00")).astimezone(tz)
        dt_min = max(1.0, (now_et - prev_ts).total_seconds() / 60.0)
    except Exception:
        dt_min = 1.0

    profile = get_ticker_profile(_profile_key_for_tag(tag))
    abs_threshold, pct_threshold = _oi_velocity_thresholds(profile)

    def _label(curr: int, prior: int) -> tuple[str, float]:
        delta = curr - prior
        vel_abs = delta / dt_min
        if prior > 0:
            vel_pct = (delta / float(prior)) / dt_min
            if vel_pct > pct_threshold and vel_abs > abs_threshold:
                return "BUILD", vel_abs
            if vel_pct < -pct_threshold and vel_abs < -abs_threshold:
                return "DECAY", vel_abs
            return "FLAT", vel_abs
        if vel_abs > abs_threshold:
            return "BUILD", vel_abs
        if vel_abs < -abs_threshold:
            return "DECAY", vel_abs
        return "FLAT", vel_abs

    return {
        "cw": _label(int(getattr(levels, "call_wall_oi", 0) or 0), int(getattr(prev, "call_wall_oi", 0) or 0)),
        "pw": _label(int(getattr(levels, "put_wall_oi", 0) or 0), int(getattr(prev, "put_wall_oi", 0) or 0)),
        "pin": _label(int(getattr(levels, "pin_strike_oi", 0) or 0), int(getattr(prev, "pin_strike_oi", 0) or 0)),
    }


def _oi_velocity_line(tag: str, levels: HasLevels) -> str:
    snap = _oi_velocity_snapshot(tag, levels)
    if snap["cw"][0] == "N/A":
        return "**OI VELOCITY:** No prior snapshot available."
    cw_status, cw_vel = snap["cw"]
    pw_status, pw_vel = snap["pw"]
    pin_status, pin_vel = snap["pin"]

    return (
        "**OI VELOCITY:** "
        f"CallWall {cw_status} ({cw_vel:+.1f}/min) | "
        f"PutWall {pw_status} ({pw_vel:+.1f}/min) | "
        f"Pin {pin_status} ({pin_vel:+.1f}/min)"
    )


def build_coaches_note(tag: str, levels: HasLevels) -> list[str]:
    """
    Generate a professional tactical briefing that tells a day trader
    exactly how to approach the current session based on options telemetry.
    """
    f = fmt_copy
    ref_price = getattr(levels, "spot", None) or getattr(levels, "futures_price", None)
    
    # 1. Macro Thesis
    bias = levels.directional_bias
    
    # Institutional Regime Descriptions
    regime_desc = {
        "PINNED": "The market is in a structural Mean-Reversion Profile. Dealers are net long gamma, acting as a volatility buffer. Expect price to be tethered to the 🧲 Gamma Magnet with suppressed realized volatility.",
        "TRENDING": "Expansion Profile active. Negative GEX acceleration is fueling a 'Gamma Trap' where dealers must chase price, amplifying directional momentum. Avoid fading walls; join the expansion.",
        "COILED": "Structural Compression Profile. Energy is building within a tight corridor. Expect a high-velocity breakout once a primary level is breached. Stay flat until acceptance is confirmed.",
        "BATTLE_ZONE": "Rotation Profile. Large institutional walls are active at the extremes. Expect sharp 'ping-pong' reversals and high-volatility rotations. Trade the range, not the trend.",
        "NEUTRAL": "Transition Profile. Market structure is resetting post-expiry or post-macro event. Monitor the primary walls for early conviction. Reduced sizing recommended."
    }
    
    thesis = (
        f"**INSTITUTIONAL REGIME:** The {tag} landscape is currently in a **{levels.regime_label}** regime "
        f"({levels.gex_regime} GEX) with a **{bias}** bias. {regime_desc.get(levels.regime_label, '')}"
    )

    parts: list[str] = [thesis]
    
    # Expose Futures Translation details if applicable
    if hasattr(levels, "translation_mode"):
        mode = getattr(levels, "translation_mode")
        if mode == "additive":
            val = getattr(levels, "basis_spread", 0.0)
            parts.append(f"**CONVERSION:** Additive Index Basis ({val:+.2f} pts)")
        elif mode == "multiplicative":
            val = getattr(levels, "basis_ratio", 1.0)
            parts.append(f"**CONVERSION:** Multiplicative ETF Scale ({val:.4f}x)")

    parts.append(_snapshot_delta_line(tag, levels))
    parts.append(_oi_velocity_line(tag, levels))

    # 0DTE-first reporting: no silent fallback to wider-dated walls.
    cw_0d = getattr(levels, "call_wall_0dte", None)
    pw_0d = getattr(levels, "put_wall_0dte", None)
    if cw_0d is not None or pw_0d is not None:
        parts.append(
            f"**0DTE WALLS:** Call {f(cw_0d)} | Put {f(pw_0d)} "
            f"(scope: {getattr(levels, 'wall_scope', 'UNSPECIFIED')} {getattr(levels, 'wall_dte_min', 0)}-{getattr(levels, 'wall_dte_max', 0)}DTE)."
        )
    else:
        parts.append(
            "**0DTE WALLS:** No meaningful 0DTE concentration found in current chain. "
            "Use wider walls only as secondary context, not primary intraday anchors."
        )

    # 2. THE PIVOT
    # Priority: Gamma Flip (Tactical) > Zero Gamma (Structural) > Max Pain (Gravitational)
    active_zg = getattr(levels, 'zero_gamma_delta_adj', None) or levels.zero_gamma
    zg_label = "Zero Gamma (DA) Pivot" if getattr(levels, 'zero_gamma_delta_adj', None) is not None else "Zero Gamma Pivot"
    
    pivots_of_interest = []
    if levels.gamma_flip_lower: pivots_of_interest.append(("Gamma Regime Lower", levels.gamma_flip_lower, 0))
    if levels.gamma_flip_upper: pivots_of_interest.append(("Gamma Regime Upper", levels.gamma_flip_upper, 0))
    if active_zg: pivots_of_interest.append((zg_label, active_zg, 1))
    if levels.max_pain: pivots_of_interest.append(("Max Pain", levels.max_pain, 2))
    
    if ref_price and pivots_of_interest:
        # Sort by proximity to ref_price
        pivots_of_interest.sort(key=lambda x: abs(x[1] - ref_price))
        best_name, best_price, _ = pivots_of_interest[0]
        
        parts.append(
            f"**THE PIVOT:** {best_name} at {f(best_price)} is the primary tactical 'line-in-the-sand'. "
            f"Trading { 'above' if ref_price > best_price else 'below' } this node with proximity to {f(ref_price)} "
            f"defines the immediate intraday conviction. Support here targets overhead liquidity."
        )
    elif pivots_of_interest:
        best_name, best_price, _ = sorted(pivots_of_interest, key=lambda x: x[2])[0]
        parts.append(f"**THE PIVOT:** {best_name} at {f(best_price)} is the primary structural level.")

    # 3. TACTICAL DELTA (Execution Plan)
    if levels.regime_label == "PINNED":
        parts.append(
            "**TACTICAL DELTA:** Prioritize mean-reversion. Fade extensions at Put Wall/EM Lower and Call Wall/EM Upper. "
            "Primary profit target is the Gamma Magnet. Expect 'sticky' price action at strikes."
        )
    elif levels.regime_label == "TRENDING":
        parts.append(
            "**TACTICAL DELTA:** Do not fade the walls. Negative gamma increases velocity; join the trend on 5-min acceptance "
            "outside the 0DTE walls. Target the 2.0σ Expected Move."
        )
    elif levels.regime_label == "COILED":
        breakout_ref = levels.zero_gamma or levels.gamma_flip_upper or levels.gamma_flip_lower
        parts.append(
            f"**TACTICAL DELTA:** Stay patient. If price clears {f(breakout_ref)} with volume, join the breakout. "
            "Avoid 'chopping' in the mid-range as dealers rebalance their books."
        )
    elif levels.regime_label == "BATTLE_ZONE":
        parts.append(
            "**TACTICAL DELTA:** Institutional extremes are in play. Short at Call Wall, Long at Put Wall. "
            "Take profit aggressively at the Gamma Magnet (Target 1) and the opposite wall (Target 2)."
        )
    else:
        parts.append("**TACTICAL DELTA:** Monitor the 10:30am ET liquidity window to confirm the day's primary rotation before deploying risk.")

    # 4. GREEK FLOW & INVENTORY
    g_mods = []
    
    # Vanna
    vanna = levels.net_vanna_exposure
    if abs(vanna) > 1.0:
        v_dir = "Bullish Tailwind" if vanna > 0 else "Bearish Headwind"
        # Deeper insight: Vanna is the change in Delta for a change in Vol.
        v_desc = "Dealers buying as IV drops (Vanna-positive)" if vanna > 0 else "Dealers selling as IV drops (Vanna-negative)"
        g_mods.append(f"Vanna ({v_dir}): {v_desc}. This creates a feedback loop that { 'supports dips' if vanna > 0 else 'accelerates slides' }.")
        
    # Charm
    charm_net = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0
    if abs(charm_net) > 3.0:
        c_dir = "Passive Buying" if charm_net > 0 else "Passive Selling"
        # Deeper insight: Charm is the change in Delta over time (Theta for Delta).
        g_mods.append(f"Charm ({c_dir}): Passive dealer flow from time-decay. This creates { 'afternoon upside drift' if charm_net > 0 else 'afternoon weight' } as we approach expiry.")

    # Expected hedge flow scenarios
    g_mods.append(
        "Hedge Scenarios: "
        f"+10pt {_fmt_flow(getattr(levels, 'hedge_flow_up_10', 0.0) or 0.0)} | "
        f"-10pt {_fmt_flow(getattr(levels, 'hedge_flow_dn_10', 0.0) or 0.0)} | "
        f"+25pt {_fmt_flow(getattr(levels, 'hedge_flow_up_25', 0.0) or 0.0)} | "
        f"-25pt {_fmt_flow(getattr(levels, 'hedge_flow_dn_25', 0.0) or 0.0)}"
    )

    curve_rows = getattr(levels, "hourly_flow_curve", []) or []
    if curve_rows:
        curve_text = " / ".join(
            f"{row.get('window')}: {_fmt_flow(float(row.get('flow_m', 0.0)) * 1_000_000.0)}"
            for row in curve_rows[:4]
        )
        g_mods.append(f"Charm/Vanna Curve: {curve_text}")

    if g_mods:
        parts.append("**DEALER INVENTORY:** " + " | ".join(g_mods))

    # 5. VOLATILITY & SKEW (The Tape)
    atm_iv = getattr(levels, "atm_iv", 0.0) or 0.0
    iv_chg = getattr(levels, "iv_change", 0.0)
    skew = getattr(levels, "volatility_skew_premium", 0.0) or 0.0
    
    if atm_iv > 0:
        vol_st = "EXPANDING" if iv_chg > 0.01 else "CONTRACTING" if iv_chg < -0.01 else "STABLE"
        skew_st = "BULLISH (Call Favor)" if skew < -0.05 else "BEARISH (Put Favor)" if skew > 0.05 else "NEUTRAL"
        
        # Deeper insight on Skew
        skew_logic = "Institutional demand for calls is distorting the surface; path of least resistance is up." if skew < -0.05 else \
                     "High demand for put protection; any break below the pivot could see sharp acceleration." if skew > 0.05 else \
                     "Volatility surface is balanced."
        
        iv_msg = "Rising IV increases hedging velocity and breakout risk." if iv_chg > 0.01 else "Contracting IV favors pinning and dealer liquidity provision."
        parts.append(f"**VOLATILITY DASH:** ATM IV (0DTE) is {atm_iv:.1%} ({vol_st}). Skew is {skew_st} ({skew:+.1%}). {skew_logic} {iv_msg}")

    # 6. STRUCTURAL INTEGRITY
    total_gex = getattr(levels, "total_gex", 0.0)
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    concentration = float(getattr(levels, "concentration_score", 0.0) or 0.0)
    concentration = min(1.0, max(0.0, concentration))
    
    s_mods = []
    if total_gex != 0:
        if concentration < 0.35:
            s_mods.append(f"🕳️ Porous Walls (Conc: {concentration:.2f}) - Dealer support is thin; expect levels to be 'leaky'.")
        elif concentration > 0.70:
            s_mods.append(f"🧱 Solid Structure (Conc: {concentration:.2f}) - Institutional positioning is robust; walls should hold on first test.")

        stability = abs(gex_0dte) / abs(total_gex)
        if stability > 0.6: 
            s_mods.append(f"⚠️ Fragile (0DTE Conc: {stability:.0%}) - Position is dominated by today's expiry; expect volatility as positions roll/expire.")

    if s_mods:
        parts.append("**STRUCTURE ALERTS:** " + " | ".join(s_mods))

    # 7. RISK ENVELOPE
    parts.append(
        f"**RISK ENVELOPE:** ±1.0σ EM: {f(levels.em_lower)} ↔ {f(levels.em_upper)}. "
        f"Vol Triggers: {f(levels.vol_trigger_upper_05)} (Up) | {f(levels.vol_trigger_lower_05)} (Down). "
        "Acceptance outside these triggers signals a structural regime shift and potential for gamma-ramping."
    )

    return parts