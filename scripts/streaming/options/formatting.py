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
    Generate a plain-English coaching paragraph that tells a novice day
    trader exactly what the current options landscape means and what to do.

    Parameters
    ----------
    tag    : Display tag, e.g. ``"/ES"`` or ``"SPX"``.
    levels : Any object carrying dealer-level + Tier 2 attributes.
    """
    f = fmt_copy
    light_color, light_reason = traffic_light(levels)
    light_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[light_color]

    # ── Regime description ──────────────────────────────────────────────
    regime_descriptions = {
        "PINNED": (
            "This is a PINNED environment — dealers are long gamma and hedging keeps price "
            "range-bound. Fade moves toward the walls. This is the most forgiving regime for "
            "newer traders because overextensions tend to snap back."
        ),
        "TRENDING": (
            "This is a TRENDING environment — dealers are short gamma and amplifying moves. "
            "Don't fade. Wait for a direction to establish, then join the trend with a trailing "
            "stop. Moves can extend further than you'd expect."
        ),
        "COILED": (
            "This is a COILED environment — dealers are short gamma but the range is compressed. "
            "The market is storing energy for a breakout. This is the hardest regime to trade. "
            "Wait for a clear break of zero gamma or the gamma flip zone before committing. "
            "If you're unsure, stand down entirely."
        ),
        "BATTLE_ZONE": (
            "This is a BATTLE_ZONE — dealers are long gamma but the range is wide. Expect large "
            "swings between the call wall and put wall. These swings tend to reverse at the walls. "
            "Trade wall-to-wall if you have the stomach for it, but use wider stops."
        ),
        "NEUTRAL": (
            "Regime is unclear — the options data isn't giving a strong signal. "
            "Trade lighter than normal and rely more on price action than levels."
        ),
    }
    regime_text = regime_descriptions.get(levels.regime_label, regime_descriptions["NEUTRAL"])

    # ── Directional bias ────────────────────────────────────────────────
    bias = levels.directional_bias
    bias_arrow = "↓" if bias == "BEARISH" else "↑" if bias == "BULLISH" else "↔"
    bias_emoji = "🔴" if bias == "BEARISH" else "🟢" if bias == "BULLISH" else "⚪"

    bias_text = ""
    if bias == "BEARISH":
        bias_text = (
            "Directional lean is BEARISH — gamma magnet is below price, put gamma dominates, "
            "and/or vanna favors downside. Look for short setups first."
        )
    elif bias == "BULLISH":
        bias_text = (
            "Directional lean is BULLISH — gamma magnet is above price, call gamma dominates, "
            "and/or vanna favors upside. Look for long setups first."
        )
    else:
        bias_text = (
            "Directional lean is NEUTRAL — mixed signals. No strong directional edge from "
            "options positioning. Let price action lead."
        )

    # ── Key levels summary ──────────────────────────────────────────────
    parts: list[str] = []

    parts.append(f"{light_emoji} {light_color}: {light_reason}")
    parts.append("")
    parts.append(f"**{tag} — {levels.regime_label} {bias_arrow}** (GEX: {levels.total_gex:,.0f}) {bias_emoji} {bias}")
    parts.append(regime_text)
    parts.append(bias_text)

    # Wall structure
    if levels.call_wall is not None and levels.put_wall is not None:
        sep_text = f"{f(levels.wall_separation)} pts" if levels.wall_separation is not None else "N/A"
        parts.append(
            f"Call wall {f(levels.call_wall)} | Put wall {f(levels.put_wall)} "
            f"({sep_text} separation, {f(levels.em_value)} EM)."
        )

    # Gravity
    if levels.gamma_magnet is not None:
        magnet_vs_spot = ""
        if hasattr(levels, 'spot'):
            spot = getattr(levels, 'spot', None)
            if spot is not None and levels.gamma_magnet is not None:
                diff = levels.gamma_magnet - spot
                direction = "above" if diff > 0 else "below"
                magnet_vs_spot = f" ({abs(diff):.1f} pts {direction} current price)"
        elif hasattr(levels, 'futures_price'):
            fp = getattr(levels, 'futures_price', None)
            if fp is not None and levels.gamma_magnet is not None:
                diff = levels.gamma_magnet - fp
                direction = "above" if diff > 0 else "below"
                magnet_vs_spot = f" ({abs(diff):.1f} pts {direction} current price)"
        parts.append(f"Gamma magnet at {f(levels.gamma_magnet)}{magnet_vs_spot} — price wants to drift here.")

    # Pin
    if levels.pin_strike is not None and levels.pin_odds > 0.15:
        parts.append(
            f"Pin strike {f(levels.pin_strike)} has {levels.pin_odds:.0%} gamma concentration — "
            f"watch for convergence, especially after 2pm ET."
        )
    elif levels.pin_strike is not None:
        parts.append(
            f"Pin strike at {f(levels.pin_strike)} but concentration is low ({levels.pin_odds:.0%}) — "
            f"pinning effect is weak today."
        )

    # Vanna context
    if abs(levels.net_vanna_exposure) > 0:
        if levels.net_vanna_exposure < 0:
            parts.append(
                "Net vanna is negative — if IV drops into the close, expect bearish dealer hedging pressure."
            )
        else:
            parts.append(
                "Net vanna is positive — if IV drops into the close, expect supportive dealer hedging."
            )

    # Action items based on regime
    parts.append("")
    if levels.regime_label == "PINNED":
        parts.append("**What to do:** Fade moves toward the walls. Short near call wall, long near put wall. "
                      "Use zero gamma as your pivot — above it lean long, below it lean short. "
                      "Take profit at the gamma magnet or the opposite wall.")
    elif levels.regime_label == "TRENDING":
        parts.append("**What to do:** Wait for price to break and hold above call wall (bullish) or "
                      "below put wall (bearish). Join the trend on a retest. Trail your stop to the "
                      "previous level. Don't try to pick tops or bottoms.")
    elif levels.regime_label == "COILED":
        parts.append("**What to do:** Be patient. Watch zero gamma and the gamma flip zone. "
                      "If price breaks and closes outside the flip zone, take the trade in that direction "
                      "with a stop back inside. If it doesn't break, don't force it.")
    elif levels.regime_label == "BATTLE_ZONE":
        parts.append("**What to do:** Trade the range. Short at call wall, long at put wall, "
                      "with stops just beyond. Expect wide swings — don't get shaken out on noise. "
                      "The gamma magnet is your mid-range target.")
    else:
        parts.append("**What to do:** Trade lighter. Let the first 30 minutes develop, then reassess.")

    # EM reminder
    parts.append(
        f"Expected move: {f(levels.em_lower)} ↔ {f(levels.em_upper)} (±{f(levels.em_value)}). "
        f"Inside the band = two-way chop. Outside = expansion, trend continuation."
    )

    # Return as a list so callers can render each item as a paragraph.
    # Filter out empty strings to avoid blank paragraphs in the UI.
    return [p for p in parts if p.strip()]