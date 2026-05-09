"""
formatting.py
=============
Shared formatting helpers for dealer-level outputs.

Both ``discord_notifier`` and ``file_writer`` import from here so that
copy-ready strings, level selectors, and trade-plan narratives are
defined once and stay consistent across all output channels.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


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
    net_speed_exposure: float | None
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
    """Return the highest value strictly below *reference*, or fall back to first_level."""
    if reference is None:
        return first_level(*values)
    candidates = [v for v in values if v is not None and v < reference]
    if not candidates:
        return first_level(*values)
    return max(candidates)


def nearest_above(reference: float | None, *values: float | None) -> float | None:
    """Return the lowest value strictly above *reference*, or fall back to first_level."""
    if reference is None:
        return first_level(*values)
    candidates = [v for v in values if v is not None and v > reference]
    if not candidates:
        return first_level(*values)
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

    def _is_near_spot(value: float | None, threshold_ems: float = 3.0) -> bool:
        if value is None or ref_price is None:
            return False
        return abs(value - ref_price) <= threshold_ems * em

    # ── Short-side trigger ──
    near_short_candidates = [
        v for v in [levels.gamma_flip_lower, levels.put_wall_0dte,
                    levels.local_put_node, levels.hedge_wall, levels.zero_gamma]
        if v is not None and _is_near_spot(v)
    ]
    s_trig = max(near_short_candidates) if near_short_candidates else first_level(levels.zero_gamma, levels.gamma_flip_lower, levels.put_wall_0dte)

    # ── Long-side trigger ──
    near_long_candidates = [
        v for v in [levels.call_wall, levels.gamma_flip_upper,
                    levels.call_wall_0dte, levels.local_call_node, levels.zero_gamma]
        if v is not None and _is_near_spot(v)
    ]
    l_trig = min(near_long_candidates) if near_long_candidates else first_level(levels.call_wall, levels.gamma_flip_upper, levels.zero_gamma)

    # ── Targets ──
    s_tgt = nearest_below(s_trig, levels.put_wall_0dte, levels.local_put_node, levels.hedge_wall, levels.em_lower)
    l_tgt = nearest_above(l_trig, levels.max_pain, levels.em_upper)

    # ── Invalidations (Institutional Safety Nets) ──
    # Short invalidated if we reclaim key resistance above trigger
    s_inv = nearest_above(s_trig, levels.zero_gamma, levels.gamma_flip_upper, levels.call_wall_0dte, levels.call_wall, levels.em_upper)
    # Long invalidated if we lose key support below trigger
    l_inv = nearest_below(l_trig, levels.zero_gamma, levels.gamma_flip_lower, levels.put_wall_0dte, levels.put_wall, levels.em_lower)

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
    if levels.zero_gamma is not None and ref_price is not None:
        zg_dist = levels.zero_gamma - ref_price
        direction = "above" if zg_dist > 0 else "below"
        # Only show distance if it's significant (>0.5 EM)
        em = levels.em_value if levels.em_value > 0 else 1.0
        if abs(zg_dist) > 0.5 * em:
            zg_context = f" Note: Zero Gamma ({f(levels.zero_gamma)}) is {abs(zg_dist):.0f} pts {direction}."

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
    parts = [
        f"{fmt_copy(getattr(levels, attr, None))}:{label}"
        for attr, label in _COPY_LEVEL_SPEC
    ]
    
    # ── Multi-Expiry Expected Moves ──
    ems = getattr(levels, "expected_moves", [])
    for em in ems:
        prefix = f"{em.expiry} ({em.dte}d) "
        parts.append(f"{fmt_copy(em.em_upper)}:{prefix}Upper EM")
        parts.append(f"{fmt_copy(em.em_lower)}:{prefix}Lower EM")
        if hasattr(em, 'straddle_85_upper') and em.straddle_85_upper > 0:
            parts.append(f"{fmt_copy(em.straddle_85_upper)}:{prefix}Upper 85% Straddle")
            parts.append(f"{fmt_copy(em.straddle_85_lower)}:{prefix}Lower 85% Straddle")

    # ── METADATA for Pine Script ──
    regime = getattr(levels, "regime_label", "NEUTRAL")
    bias = getattr(levels, "directional_bias", "NEUTRAL")
    parts.append(f"0:META_REGIME_{regime}")
    parts.append(f"0:META_BIAS_{bias}")
    
    # Greeks as metadata for dashboard rows
    vanna = getattr(levels, "net_vanna_exposure", 0.0)
    speed = getattr(levels, "net_speed_exposure", 0.0) or 0.0
    charm = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0.0
    parts.append(f"0:META_VANNA_{vanna:.2f}")
    parts.append(f"0:META_SPEED_{speed:.2f}")
    parts.append(f"0:META_CHARM_{charm:.2f}")
    
    total_gex = getattr(levels, "total_gex", 0.0)
    parts.append(f"0:META_GEX_DA_{gex_da:.2f}")
    parts.append(f"0:META_GEX_TOTAL_{total_gex:.2f}")

    # Stability & Integrity
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    stability = (abs(gex_0dte) / abs(total_gex)) if total_gex != 0 else 0.0
    integrity = 1.0 - (abs(gex_da / total_gex)) if total_gex != 0 else 0.0
    parts.append(f"0:META_STABILITY_{stability:.2f}")
    parts.append(f"0:META_INTEGRITY_{integrity:.2f}")

    # IV & Skew
    atm_iv = getattr(levels, "atm_iv", 0.0) or 0.0
    iv_chg = getattr(levels, "iv_change", 0.0)
    skew = getattr(levels, "volatility_skew_premium", 0.0) or 0.0
    parts.append(f"0:META_IV_{atm_iv:.4f}")
    parts.append(f"0:META_IVCHG_{iv_chg:.4f}")
    parts.append(f"0:META_SKEW_{skew:.4f}")



    # Synchronized Tactical Plan (Shared Logic)
    f = fmt_copy
    tactical = _calculate_tactical_levels(levels)
    
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
    \"\"\"Generate a high-signal tactical summary for the Pine Script dashboard.\"\"\"
    regime = levels.regime_label
    bias = levels.directional_bias
    
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
    
    # Vanna impact
    vanna = levels.net_vanna_exposure
    if abs(vanna) > 1.5:
        mods.append("🌊 Vanna Squeeze" if vanna > 0 else "💨 Vanna Drag")
    
    # Charm impact (passive rehedging)
    charm_net = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0
    if abs(charm_net) > 5.0: 
         mods.append("⏳ Charm Decay" if charm_net > 0 else "⚡ Charm Accel")

    # Speed / Volatility sensitivity
    speed = getattr(levels, "net_speed_exposure", 0.0) or 0.0
    if abs(speed) > 10.0:
        mods.append("🏎️ High Hedging Velocity")

    # GEX DA Awareness (Porous structure check)
    gex_da = getattr(levels, "total_gex_delta_adj", 0.0) or 0.0
    total_gex = getattr(levels, "total_gex", 0.0)
    da_ratio = abs(gex_da / total_gex) if total_gex != 0 else 1.0
    
    if da_ratio < 0.6:
        mods.append("🕳️ Porous")
    elif da_ratio > 0.9:
        mods.append("🧱 Solid")

    # IV/Skew modifiers
    atm_iv = getattr(levels, "atm_iv", 0.0) or 0.0
    iv_chg = getattr(levels, "iv_change", 0.0)
    skew = getattr(levels, "volatility_skew_premium", 0.0) or 0.0

    if iv_chg > 0.02: mods.append("📈 Vol Expansion")
    elif iv_chg < -0.02: mods.append("📉 Vol Crush")
    
    if skew > 0.05: mods.append("🛡️ Put Demand")
    elif skew < -0.05: mods.append("💎 Call Demand")

    # Stability (0DTE concentration)
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    if total_gex != 0 and (abs(gex_0dte) / abs(total_gex)) > 0.6:
        mods.append("⚠️ 0DTE Trap")

    if levels.pin_odds > 0.15:
        mods.append(f"🎯 Pin {levels.pin_odds:.0%}")
    
    # Proximity Check (Dynamic based on Spot)
    ref_price = getattr(levels, "spot", None) or getattr(levels, "futures_price", None)
    if ref_price:
        walls = [levels.call_wall, levels.put_wall, levels.call_wall_0dte, levels.put_wall_0dte]
        near_wall = any(abs(w - ref_price) / ref_price < 0.0015 for w in walls if w)
        if near_wall:
            mods.append("🛑 Wall Nearby")

    mod_str = f" | {' '.join(mods)}" if mods else ""
    return f"[{bias}] {base}{mod_str}"


# ---------------------------------------------------------------------------
# Coach's Note — plain-English game plan
# ---------------------------------------------------------------------------

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
        "PINNED": "Mean-Reversion Profile. Dealers are net long gamma, providing thick liquidity and dampening volatility. Expect price to seek the 🧲 Gamma Magnet. Volatility is suppressed.",
        "TRENDING": "Expansion Profile. Negative GEX acceleration is active. Dealers are forced to chase price (Gamma Trap), fueling directional momentum. Avoid fading extremes.",
        "COILED": "Compression Profile. Energy is building inside a tight structural corridor. Expect a high-velocity volatility breakout. Stay flat until a definitive level is accepted.",
        "BATTLE_ZONE": "Two-Way Auction. Large institutional walls are active at the extremes. Expect sharp reversals and 'ping-pong' rotation between walls. Trade for range, not trend.",
        "NEUTRAL": "Transition Profile. Market structure is resetting. Monitor the primary walls for early directional conviction. Reduced sizing recommended."
    }
    
    thesis = (
        f"The {tag} options landscape is in a {levels.regime_label} regime ({levels.gex_regime} GEX) "
        f"with a {bias} bias. {regime_desc.get(levels.regime_label, '')}"
    )

    parts: list[str] = [thesis]

    # 2. Execution Directives
    
    # Directive: The Pivot
    pivot = levels.zero_gamma if levels.zero_gamma else (levels.gamma_flip_lower if levels.gamma_flip_lower else levels.max_pain)
    if pivot is not None:
        parts.append(
            f"**THE PIVOT:** {f(pivot)} is today's primary line-in-the-sand. "
            f"Holding above = Buyers in structural control, targeting overhead DEX nodes. "
            f"Slipping below = Sellers in control, seeking GC↓ liquidity and hedge walls."
        )

    # Directive: Tactical Delta (Regime Specific)
    if levels.regime_label == "PINNED":
        parts.append(
            "**TACTICAL DELTA:** Favor mean-reversion. Buy at Put Wall/EM Lower, Short at Call Wall/EM Upper. "
            "Primary profit target is the Gamma Magnet. Tighten stops on approach to walls."
        )
    elif levels.regime_label == "TRENDING":
        parts.append(
            "**TACTICAL DELTA:** Join the trend. Negative gamma increases velocity. Do not fade the walls. "
            "Wait for a 5-min candle to accept outside the 0DTE wall, then enter on the first retest. Target 2.0σ EM."
        )
    elif levels.regime_label == "COILED":
        parts.append(
            f"**TACTICAL DELTA:** Stay flat until the break. If price clears {f(pivot)} with volume, "
            "join the expansion. Avoid mid-range entries inside the flip zone as noise remains high."
        )
    elif levels.regime_label == "BATTLE_ZONE":
        parts.append(
            "**TACTICAL DELTA:** Trade the extremes. These are wide rotations. Ensure stops are outside the ATR. "
            "Target the Gamma Magnet as Target 1 and the opposite wall as Target 2."
        )
    else:
        parts.append("**TACTICAL DELTA:** Reassess at the 10:30am ET liquidity window to confirm regime resolution before deploying risk.")

    # Directive: GEX Delta-Adjusted (Structure Quality / Porousness)
    gex_da = getattr(levels, "total_gex_delta_adj", 0.0) or 0.0
    total_gex = getattr(levels, "total_gex", 0.0)
    if total_gex != 0:
        da_ratio = abs(gex_da / total_gex)
        if da_ratio < 0.6:
            parts.append(f"**STRUCTURE ALERT:** High delta-imbalance (DA Ratio: {da_ratio:.2f}). The gamma walls are 'porous'. Price is likely to 'slip' through levels rather than bounce cleanly.")
        elif da_ratio > 0.9:
             parts.append(f"**STRUCTURE ALERT:** High structural integrity (DA Ratio: {da_ratio:.2f}). Levels are robust and likely to hold on first tests.")

    # Directive: Stability Audit (0DTE Concentration)
    gex_0dte = (getattr(levels, "call_gex_0dte", 0.0) or 0.0) + (getattr(levels, "put_gex_0dte", 0.0) or 0.0)
    if total_gex != 0:
        stability = abs(gex_0dte) / abs(total_gex)
        if stability > 0.6:
            parts.append(f"**STABILITY ALERT:** High 0DTE Concentration ({stability:.0%}). The 'Tail is wagging the dog'. Structure is fragile; expect sudden, violent hedging rotations as strikes are challenged.")

    # Directive: Vanna Flow
    vanna = levels.net_vanna_exposure
    if abs(vanna) > 1.0:
        v_direction = "Bullish Tailwind" if vanna > 0 else "Bearish Headwind"
        v_logic = (
            "Dealers will be forced to buy as IV drops (Vanna Squeeze), providing upward drift." if vanna > 0 
            else "Dealers will be forced to sell as IV drops, amplifying downside pressure. Retests of resistance may be sold aggressively."
        )
        parts.append(f"**VANNA FLOW:** {v_direction}. {v_logic}")

    # Directive: Charm Flow (Time Decay)
    charm_net = (levels.charm_call_node - levels.charm_put_node) if (levels.charm_call_node and levels.charm_put_node) else 0
    if abs(charm_net) > 3.0:
        c_direction = "Positive Charm" if charm_net > 0 else "Negative Charm"
        c_logic = (
            "Passive delta buying as time passes (decay). Expect drift toward the upside into the afternoon." if charm_net > 0
            else "Passive delta selling as time passes. Expect afternoon selling pressure or 'heavy' price action."
        )
        parts.append(f"**CHARM FLOW:** {c_direction}. {c_logic}")

    # Directive: Speed Awareness (Gamma Sensitivity)
    speed = getattr(levels, "net_speed_exposure", None)
    if speed is not None and abs(speed) > 10.0:
        parts.append(f"**SPEED ALERT:** Extreme Gamma Sensitivity ({speed:+.1f}). Price movements will trigger rapid dealer rehedging. Expect 'jumpy' price action near major strikes.")

    # Directive: Liquidity Vacuums
    v_low = levels.liquidity_vacuum_lower
    v_high = levels.liquidity_vacuum_upper
    if ref_price:
        if v_low and abs(v_low - ref_price) / ref_price < 0.003:
            parts.append(f"**LIQUIDITY GAP:** Price is near a downside vacuum at {f(v_low)}. If support breaks, expect a rapid acceleration into this zone.")
        if v_high and abs(v_high - ref_price) / ref_price < 0.003:
            parts.append(f"**LIQUIDITY GAP:** Price is near an upside vacuum at {f(v_high)}. If resistance clears, expect a 'vacuum rally' toward the next node.")

    # Directive: Gravity
    if levels.gamma_magnet is not None:
        parts.append(
            f"**GRAVITY:** Price is likely to be drawn toward the {f(levels.gamma_magnet)} Magnet. "
            "This strike marks the center of the dealer's book; expect stalls, rotations, or 'pinning' behavior here."
        )

    # Directive: IV & Skew Dynamics
    atm_iv = getattr(levels, "atm_iv", 0.0) or 0.0
    iv_chg = getattr(levels, "iv_change", 0.0)
    skew = getattr(levels, "volatility_skew_premium", 0.0) or 0.0
    
    if atm_iv > 0:
        vol_state = "Expanding" if iv_chg > 0.01 else "Contracting" if iv_chg < -0.01 else "Stable"
        skew_state = "Bullish (Call Favor)" if skew < -0.05 else "Bearish (Put Favor)" if skew > 0.05 else "Neutral"
        parts.append(
            f"**VOLATILITY DASH:** IV is {atm_iv:.1%} ({vol_state}). Skew is {skew_state} ({skew:+.1%}). "
            f"{'Rising IV suggests expansion/hedging velocity increase.' if iv_chg > 0.01 else 'Falling IV favors dealer mean-reversion and pinning.'}"
        )

    # Directive: The Risk Envelope
    parts.append(
        f"**RISK ENVELOPE:** ±1.0σ Expected Move is {f(levels.em_lower)} ↔ {f(levels.em_upper)}. "
        f"Vol Triggers: {f(levels.vol_trigger_upper_05)} (Upper) | {f(levels.vol_trigger_lower_05)} (Lower). "
        "Acceptance outside these triggers signals a regime shift."
    )

    return parts
.vol_trigger_lower_05)} (Lower). "
        "Breaching these levels signals a volatility expansion event."
    )

    return parts