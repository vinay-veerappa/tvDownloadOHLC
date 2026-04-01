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
    expected_moves: list[Any]


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


def copy_ready_line(tag: str, levels: Any) -> str:
    """
    Build a copy-ready string for *levels* prefixed by *tag*.

    Parameters
    ----------
    tag    : Ticker or futures tag, e.g. ``"ES"`` or ``"/ES"`` or ``"SPX"``.
    levels : Any object whose attributes match ``_COPY_LEVEL_SPEC`` names
             (``TranslatedLevels``, ``DealerLevels``, etc.).
    """
    parts = [
        f"{fmt_copy(getattr(levels, attr, None))}:{label}"
        for attr, label in _COPY_LEVEL_SPEC
    ]
    
    # ── Multi-Expiry Expected Moves ──
    ems = getattr(levels, "expected_moves", [])
    for em in ems:
        # Use descriptive labels with DTE suffix
        prefix = f"{em.expiry} ({em.dte}d) "
        parts.append(f"{fmt_copy(em.em_upper)}:{prefix}Upper EM")
        parts.append(f"{fmt_copy(em.em_lower)}:{prefix}Lower EM")

    return f"{tag}: " + ", ".join(parts)


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

def build_plan(
    tag: str,
    levels: HasLevels,
    *,
    extended: bool = False,
) -> list[str]:
    """
    Build a structured trade-plan narrative.

    Parameters
    ----------
    tag      : Display tag, e.g. ``"/ES"`` or ``"ES"``.
    levels   : Any object carrying dealer-level attributes.
    extended : If True, include vol-trigger targets and a second target per
               direction (used for the TXT file).  If False, produce a
               condensed plan (used for Discord embeds).
    """
    f = fmt_copy  # shorthand

    # ── Determine a reference price for sanity checks ──────────────────
    # Use spot if available (DealerLevels), futures_price if translated.
    ref_price = getattr(levels, 'spot', None) or getattr(levels, 'futures_price', None)
    em = levels.em_value if levels.em_value > 0 else 1.0

    def _is_near_spot(value: float | None, threshold_ems: float = 3.0) -> bool:
        """True if value is within threshold_ems × EM of the reference price."""
        if value is None or ref_price is None:
            return False
        return abs(value - ref_price) <= threshold_ems * em

    # ── Short-side trigger: the level that, if broken, favors downside ──
    # Prefer levels near spot. Zero gamma 170pts away is not actionable
    # as a trigger — use put wall or gamma flip lower instead.
    near_short_candidates = [
        v for v in [levels.gamma_flip_lower, levels.put_wall_0dte,
                    levels.local_put_node, levels.hedge_wall, levels.zero_gamma]
        if v is not None and _is_near_spot(v)
    ]
    if near_short_candidates:
        # Pick the highest near-spot support level as the short trigger
        short_trigger = max(near_short_candidates)
    else:
        short_trigger = first_level(levels.zero_gamma, levels.gamma_flip_lower, levels.put_wall_0dte)

    # ── Long-side trigger: the level that, if broken, favors upside ────
    near_long_candidates = [
        v for v in [levels.call_wall, levels.gamma_flip_upper,
                    levels.call_wall_0dte, levels.local_call_node, levels.zero_gamma]
        if v is not None and _is_near_spot(v)
    ]
    if near_long_candidates:
        # Pick the lowest near-spot resistance level as the long trigger
        long_trigger = min(near_long_candidates)
    else:
        long_trigger = first_level(levels.call_wall, levels.gamma_flip_upper, levels.zero_gamma)

    # ── Short targets: levels below the short trigger ──────────────────
    if extended:
        short_target_1 = nearest_below(
            short_trigger,
            levels.put_wall_0dte, levels.local_put_node, levels.hedge_wall,
            levels.vol_trigger_lower_05, levels.vol_trigger_lower_10,
            levels.em_lower,
        )
        short_target_2 = nearest_below(
            short_target_1 if short_target_1 is not None else short_trigger,
            levels.hedge_wall, levels.vol_trigger_lower_10,
            levels.vol_trigger_lower_15, levels.em_lower,
        )
    else:
        short_target_1 = nearest_below(
            short_trigger,
            levels.put_wall_0dte, levels.local_put_node, levels.hedge_wall,
            levels.em_lower,
        )
        short_target_2 = None

    # ── Short invalidation: nearest level above the trigger ────────────
    short_invalidation = nearest_above(
        short_trigger,
        levels.call_wall, levels.gamma_flip_upper, levels.em_upper,
    )

    # ── Long targets: levels above the long trigger ────────────────────
    if extended:
        long_target_1 = nearest_above(
            long_trigger,
            levels.max_pain, levels.vol_trigger_upper_05, levels.em_upper,
        )
        long_target_2 = nearest_above(
            long_target_1 if long_target_1 is not None else long_trigger,
            levels.vol_trigger_upper_10, levels.secondary_call_wall, levels.em_upper,
        )
    else:
        long_target_1 = nearest_above(long_trigger, levels.max_pain, levels.em_upper)
        long_target_2 = None

    # ── Long invalidation: nearest level below the trigger ─────────────
    long_invalidation = nearest_below(
        long_trigger,
        levels.zero_gamma, levels.gamma_flip_lower, levels.put_wall_0dte,
    )

    regime_tone = (
        "sellers have structural control" if levels.gex_regime == "NEGATIVE"
        else "buyers have structural control"
    )

    # ── Zero gamma context line (always useful even when distant) ──────
    zg_context = ""
    if levels.zero_gamma is not None and ref_price is not None:
        zg_dist = levels.zero_gamma - ref_price
        direction = "above" if zg_dist > 0 else "below"
        if not _is_near_spot(levels.zero_gamma, threshold_ems=2.0):
            zg_context = (
                f" Note: Zero Gamma ({f(levels.zero_gamma)}) is {abs(zg_dist):.0f} pts "
                f"{direction} — too distant to act as an intraday trigger, but marks the "
                f"structural GEX boundary."
            )

    if extended:
        # Full TXT-style narrative
        tgt2_short = f" first, then {f(short_target_2)}" if short_target_2 is not None else ""
        tgt2_long = f" and then {f(long_target_2)}" if long_target_2 is not None else ""
        return [
            f"{tag} Narrative Plan:",
            (
                f"- Context: {tag} is in a {levels.gex_regime} GEX regime "
                f"({levels.total_gex:,.0f}), which means {regime_tone}. "
                f"Start with this as your default bias, then let price confirm or reject it.{zg_context}"
            ),
            (
                f"- What to watch first: short trigger at {f(short_trigger)}, long trigger at {f(long_trigger)}, "
                f"gamma-flip zone {f(levels.gamma_flip_lower)} ↔ {f(levels.gamma_flip_upper)}, "
                f"and DEX nodes {f(levels.dex_put_node)} / {f(levels.dex_call_node)}."
            ),
            (
                f"- Base-case execution: If price accepts below {f(short_trigger)}, look for "
                f"downside rotation into {f(short_target_1)}{tgt2_short}. "
                f"Treat Gamma Cliff Down {f(levels.gamma_cliff_down)} and DEX node {f(levels.dex_put_node)} "
                f"as reaction zones where momentum can stall or accelerate. "
                f"Short idea is invalidated if price reclaims and holds above {f(short_invalidation)}."
            ),
            (
                f"- Alternate execution: If buyers reclaim {f(long_trigger)} and hold, "
                f"look for upside rotation toward {f(long_target_1)}{tgt2_long}. "
                f"Treat Gamma Cliff Up {f(levels.gamma_cliff_up)} and DEX node {f(levels.dex_call_node)} "
                f"as decision zones for continuation vs rejection. "
                f"Long idea is invalidated if price loses {f(long_invalidation)} after the breakout."
            ),
            (
                f"- Risk map for the session: Expected move envelope is "
                f"{f(levels.em_lower)} ↔ {f(levels.em_upper)} (±{levels.em_value:.2f}). "
                f"Inside the band, expect two-way trade; outside the band, expect expansion "
                f"and faster trend continuation."
            ),
            (
                f"- Practical rule for newer traders: wait for candle-close acceptance and then "
                f"a retest before entry; if acceptance fails, stand down and wait for the opposite scenario."
            ),
        ]
    else:
        # Compact Discord-style narrative
        lines = [
            f"Context: {tag} is in a {levels.gex_regime} GEX regime ({levels.total_gex:,.0f}); {regime_tone}.",
        ]
        if zg_context:
            lines.append(zg_context.strip())
        lines.extend([
            (
                f"Watch: Short trigger {f(short_trigger)}, long trigger {f(long_trigger)}, "
                f"GF {f(levels.gamma_flip_lower)}↔{f(levels.gamma_flip_upper)}, "
                f"DEX {f(levels.dex_put_node)}/{f(levels.dex_call_node)}."
            ),
            (
                f"Base case: Below {f(short_trigger)}, look for rotation into {f(short_target_1)}. "
                f"Use GC↓ {f(levels.gamma_cliff_down)} and DEX {f(levels.dex_put_node)} "
                f"as reaction zones; invalidation is reclaim/hold above {f(short_invalidation)}."
            ),
            (
                f"Alternate: Above {f(long_trigger)}, look for continuation into {f(long_target_1)}. "
                f"Use GC↑ {f(levels.gamma_cliff_up)} and DEX {f(levels.dex_call_node)} "
                f"as decision zones; invalidation is loss of {f(long_invalidation)} after breakout."
            ),
            f"Risk map: EM {f(levels.em_lower)}↔{f(levels.em_upper)}.",
        ])
        return lines


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
        return "RED", "Multiple key levels are missing — data may be stale or incomplete. Stand down."

    if levels.wall_separation is not None and levels.wall_separation < 3.0:
        return "RED", "Wall separation is extremely tight (<3 pts). No room to trade — stand down."

    # YELLOW: transitional or hard-to-trade conditions
    if levels.regime_label == "COILED":
        return "YELLOW", (
            "COILED regime — negative GEX with tight walls. Market is compressed and can break "
            "sharply in either direction. Reduce size, wait for confirmation before entry."
        )

    if levels.pin_odds < 0.08 and levels.regime_label != "PINNED":
        return "YELLOW", (
            "Gamma is very diffuse (pin odds <8%). No strong gravitational anchor. "
            "Levels may not hold as well. Trade lighter."
        )

    if levels.regime_label == "NEUTRAL":
        return "YELLOW", "Regime unclear — not enough data to classify. Trade cautiously or paper trade."

    # GREEN: clear regime with actionable structure
    if levels.regime_label == "PINNED":
        return "GREEN", (
            "PINNED regime — positive GEX with tight walls. Mean-revert environment. "
            "Fade moves toward the walls with confidence. Best conditions for newer traders."
        )

    if levels.regime_label == "TRENDING":
        return "GREEN", (
            "TRENDING regime — negative GEX with wide separation. Trend-follow environment. "
            "Join moves after confirmation, trail stops, don't fight the direction."
        )

    if levels.regime_label == "BATTLE_ZONE":
        return "GREEN", (
            "BATTLE_ZONE regime — positive GEX with wide walls. Expect big swings that "
            "reverse at the walls. Trade wall-to-wall if you can handle the movement."
        )

    return "YELLOW", "Mixed signals — trade with caution."


# ---------------------------------------------------------------------------
# Coach's Note — plain-English game plan per run
# ---------------------------------------------------------------------------

def build_coaches_note(tag: str, levels: HasLevels) -> list[str]:
    """
    Generate a professional tactical briefing that tells a day trader
    exactly how to approach the current session based on options telemetry.
    """
    f = fmt_copy
    light_color, light_reason = traffic_light(levels)
    light_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[light_color]
    
    # 1. Macro Thesis
    # This becomes the first paragraph in the UI (styled as italic/highlighted)
    bias = levels.directional_bias
    bias_arrow = "↓" if bias == "BEARISH" else "↑" if bias == "BULLISH" else "↔"
    
    macro_thesis = (
        f"The {tag} options chain is currently in a {levels.regime_label} regime ({levels.gex_regime} GEX) "
        f"with a {bias} lean. "
    )
    
    if levels.regime_label == "PINNED":
        macro_thesis += "Dealers are providing high liquidity; expect price to seek the 🧲 Gamma Magnet and stall at the walls."
    elif levels.regime_label == "TRENDING":
        macro_thesis += "Short gamma is active; expect price to accelerate away from the walls with expanding volatility."
    elif levels.regime_label == "COILED":
        macro_thesis += "The range is extremely tight; a high-velocity volatility breakout is imminent. Wait for the pivot break."
    elif levels.regime_label == "BATTLE_ZONE":
        macro_thesis += "Expect heavy two-way volume with sharp reversals at the Call and Put walls today."
    else:
        macro_thesis += "Market structure is stabilizing. Monitor price action around the primary walls for early conviction."

    parts: list[str] = [macro_thesis]

    # 2. Execution Directives
    # These will be numbered in the UI
    
    # Directive: The Pivot
    pivot = levels.zero_gamma if levels.zero_gamma else (levels.gamma_flip_lower if levels.gamma_flip_lower else levels.max_pain)
    if pivot is not None:
        parts.append(
            f"**THE PIVOT:** Use {f(pivot)} as today's line-in-the-sand. "
            f"Trading above = Buyers in control, targeting higher DEX nodes. "
            f"Trading below = Sellers in control, seeking GC↓ liquidity."
        )

    # Directive: What to do (Regime Specific)
    if levels.regime_label == "PINNED":
        parts.append(
            "**TACTICAL DELTA:** Favor mean-reversion. Long at Put Wall/EM Lower, Short at Call Wall/EM Upper. "
            "Keep take-profits frequent as the magnet pulls price back to the center."
        )
    elif levels.regime_label == "TRENDING":
        parts.append(
            "**TACTICAL DELTA:** Join the trend. Do not fade the walls. "
            "Wait for a 5-min candle to close outside the 0DTE wall, then enter on a retest in the same direction."
        )
    elif levels.regime_label == "COILED":
        parts.append(
            "**TACTICAL DELTA:** Stay flat until a breakout. If price breaks {f(pivot)} with volume, "
            "join the move. If price remains inside the GF range, do not take mid-range entries."
        )
    elif levels.regime_label == "BATTLE_ZONE":
        parts.append(
            "**TACTICAL DELTA:** Trade wall-to-wall. These are wide swings—ensure your stop is outside the ATR, "
            "not just at the level. Target the Gamma Magnet as your target 1."
        )
    else:
        parts.append("**TACTICAL DELTA:** Reassess at the 10:30am ET liquidity window to confirm if a new regime is forming.")

    # Directive: Gravity & Flow
    if levels.gamma_magnet is not None:
        parts.append(
            f"**GRAVITY:** Price is likely to drift toward the {f(levels.gamma_magnet)} Gamma Magnet. "
            "Use this as your primary profit-taking zone for range trades."
        )

    # Directive: The Pin
    if levels.pin_strike is not None and levels.pin_odds > 0.12:
        parts.append(
            f"**THETA RISK:** High pinning probability at {f(levels.pin_strike)} ({levels.pin_odds:.0%}). "
            "Expect a price squeeze toward this level in the final 90 minutes of the session."
        )

    # Directive: Vanna/Vol
    if abs(levels.net_vanna_exposure) > 0 and abs(levels.iv_change) > 0.02:
        vanna_direction = "supportive" if levels.net_vanna_exposure > 0 else "bearish"
        parts.append(
            f"**VOL SQUEEZE:** Net Vanna is {vanna_direction}. If current IV expansion/contraction persists, "
            "dealers will be forced to hedge aggressively, amplifying the move."
        )

    # Directive: The Envelope (EM)
    parts.append(
        f"**RISK ENVELOPE:** Today's ±1.0σ Expected Move is {f(levels.em_lower)} ↔ {f(levels.em_upper)}. "
        "Any trade outside this range is a 'regime break'—reset your stops and look for a multi-day trend."
    )

    return parts