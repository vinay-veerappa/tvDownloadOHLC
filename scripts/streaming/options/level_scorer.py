"""
level_scorer.py
================
Implementation of the Three-Filter Level Triage architecture.
This module classifies each mathematical dealer level (Strike) into a 
contextual tag (STRATEGIC, PIVOT, CONTEXTUAL) based on significance and 
proximity to spot.
"""
from __future__ import annotations
import logging
from typing import Any
from .gex_calculator import DealerLevels, TaggedLevel, ScoredLevels
from .options_fetcher import OptionChainData
from .config import ViewModeConfig, INTRADAY_VIEW, MACRO_VIEW

log = logging.getLogger(__name__)

# --- Primary Config Table: Field -> Metadata ---------------------------------
# Maps DealerLevels field names to their structural metadata.
_LEVEL_METADATA: dict[str, dict[str, str]] = {
    "call_wall": {
        "label": "Absolute Call Wall",
        "significance": "PRIMARY",
        "side": "CALL",
        "desc": "The strike with maximum absolute gamma exposure. Operates as a major structural ceiling for dealer hedging.",
    },
    "put_wall": {
        "label": "Absolute Put Wall",
        "significance": "PRIMARY",
        "side": "PUT",
        "desc": "The strike with maximum absolute negative gamma exposure. Operates as the floor for dealer downside protection.",
    },
    "call_wall_0dte": {
        "label": "Tactical Call Wall",
        "significance": "SECONDARY",
        "side": "CALL",
        "desc": "Gamma concentration in near-term expirations. High daily magnet strength in bullish tape.",
    },
    "put_wall_0dte": {
        "label": "Tactical Put Wall",
        "significance": "SECONDARY",
        "side": "PUT",
        "desc": "Near-term downside gamma wall. Represents active dealer downside hedging for current session.",
    },
    "zero_gamma": {
        "label": "Zero Gamma Level",
        "significance": "PIVOT",
        "side": "NEUTRAL",
        "desc": "The point where dealer positioning flips from long to short gamma. Volatility increases significantly below this level.",
    },
    "gamma_magnet": {
        "label": "Gamma Magnet",
        "significance": "CONTEXTUAL",
        "side": "NEUTRAL",
        "desc": "The gravity center of dealer positioning. Price tends to be drawn to or 'pin' at this level during low-volume sessions.",
    },
    "max_pain": {
        "label": "Maximum Pain",
        "significance": "CONTEXTUAL",
        "side": "NEUTRAL",
        "desc": "The strike where the most option value expires worthless. Useful as a magnet during opex weeks.",
    },
    "hedge_wall": {
        "label": "Dealer Hedge Wall",
        "significance": "SECONDARY",
        "side": "PUT",
        "desc": "A structural floor where dealer positive gamma is exhausted and liquidity begins to diminish.",
    },
    "vanna_call_node": {
        "label": "Vanna Resistance Node",
        "significance": "CONTEXTUAL",
        "side": "CALL",
        "desc": "Peak Vanna concentration (Strike × Vega × Delta). Represents significant volatility sensitivity for upside dealers.",
    },
    "vanna_put_node": {
        "label": "Vanna Support Node",
        "significance": "CONTEXTUAL",
        "side": "PUT",
        "desc": "Peak Vanna sensitivity for puts. Significant for spotting IV-expansion-based selling acceleration.",
    },
    "charm_call_node": {
        "label": "Charm Gravity Node (C)",
        "significance": "CONTEXTUAL",
        "side": "CALL",
        "desc": "Peak Charm sensitivity (Delta decay over time). Dealers will tend to buy/sell passively around this strike over the weekend.",
    },
    "charm_put_node": {
        "label": "Charm Gravity Node (P)",
        "significance": "CONTEXTUAL",
        "side": "PUT",
        "desc": "Concentration of Put charm. Potential for passive buyback pressure as weekend/expiry approach.",
    },
    "max_gex_strike": {
        "label": "Major GEX Anchor",
        "significance": "PRIMARY",
        "side": "NEUTRAL",
        "desc": "The strike with the single highest net GEX magnitude in the entire chain.",
    },
    "vol_trigger_upper_05": {
        "label": "Vol Trigger Upper (0.5σ)",
        "significance": "CONTEXTUAL",
        "side": "CALL",
        "desc": "Price level where implied volatility expansion begins to drive dealer gamma-ramping for calls.",
    },
    "vol_trigger_lower_05": {
        "label": "Vol Trigger Lower (0.5σ)",
        "significance": "CONTEXTUAL",
        "side": "PUT",
        "desc": "Price level where downside IV expansion accelerates dealer selling in put space.",
    },
    "gamma_flip_lower": {
        "label": "Gamma Flip Low",
        "significance": "PIVOT",
        "side": "NEUTRAL",
        "desc": "Lower boundary of the transition zone between positive and negative gamma regimes.",
    },
    "gamma_flip_upper": {
        "label": "Gamma Flip High",
        "significance": "PIVOT",
        "side": "NEUTRAL",
        "desc": "Upper boundary of the gamma transition zone. Support typically hardens above this level.",
    },
    "local_call_node": {
        "label": "Local Call Cluster",
        "significance": "SECONDARY",
        "side": "CALL",
        "desc": "Secondary cluster of positive gamma near current spot price.",
    },
    "local_put_node": {
        "label": "Local Put Cluster",
        "significance": "SECONDARY",
        "side": "PUT",
        "desc": "Secondary cluster of negative gamma near current spot price.",
    },
    "liquidity_vacuum_lower": {
        "label": "Liquidity Void (Low)",
        "significance": "CONTEXTUAL",
        "side": "NEUTRAL",
        "desc": "The bottom of a low-OI pocket where price can slide quickly due to lack of dealer support.",
    },
    "liquidity_vacuum_upper": {
        "label": "Liquidity Void (High)",
        "significance": "CONTEXTUAL",
        "side": "NEUTRAL",
        "desc": "An overhead gap in the OI chain where upside momentum may overextend due to low dealer resistance.",
    }
}

def score_levels(
    levels: DealerLevels,
    chain: OptionChainData,
    ticker: str,
    profile: dict[str, Any],
    view_config: ViewModeConfig = INTRADAY_VIEW
) -> ScoredLevels:
    """
    Applies the triple-filter logic to build a prioritized list of tagged levels.
    """
    spot = levels.spot
    proximity_pct = view_config.strike_range_pct
    lo_bound = spot * (1.0 - proximity_pct)
    hi_bound = spot * (1.0 + proximity_pct)

    tagged_output: list[TaggedLevel] = []
    seen_levels: set[float] = set()

    # Iterate through all configured fields
    for field_name, meta in _LEVEL_METADATA.items():
        # Only process fields included in this view's significance mask
        if meta["significance"] not in view_config.significance_mask:
            continue

        raw_val = getattr(levels, field_name, None)
        if not isinstance(raw_val, (int, float)) or raw_val <= 0:
            continue

        # Proximity Filter: Is it relevant to current tape?
        if raw_val < lo_bound or raw_val > hi_bound:
            continue

        # Prevent duplicate strikes on the same side
        # (e.g. if Call Wall and 0DTE Call Wall are the same strike, keep primary)
        level_key = (round(raw_val, 2), meta["side"])
        if level_key in seen_levels:
            # We already have a tag for this strike; if this one is PRIMARY, keep it?
            # For simplicity, we just keep the FIRST one (which follows our iteration order)
            continue
        
        seen_levels.add(level_key)

        # Baseline strength score (normalized distance from spot)
        # 1.0 = at spot, 0.0 = at proximity boundary
        dist = abs(raw_val - spot)
        strength = max(0.0, 1.0 - (dist / (spot * proximity_pct)))

        # Hierarchical Tag Assignment (Filter 3)
        # Strategic: Deep Primary walls
        # Pivot: Inflection points (Zero Gamma, Flip Zone)
        # Contextual: Supporting magnets
        if meta["significance"] == "PRIMARY":
            final_tag = "STRATEGIC"
            strength = 1.0 # strategic walls are always 'strong'
        elif meta["significance"] in ("SECONDARY", "PIVOT"):
            final_tag = "PIVOT"
        else:
            final_tag = "CONTEXTUAL"

        tagged_output.append(TaggedLevel(
            strike=round(float(raw_val), 2),
            label=meta["label"],
            significance=final_tag,
            side=meta["side"],
            strength_score=round(strength, 3),
            description=meta["desc"],
            field_name=field_name
        ))

    # Sort by significance PRIORITY then STRENGTH
    _sig_rank = {"STRATEGIC": 0, "PIVOT": 1, "CONTEXTUAL": 2}
    tagged_output.sort(key=lambda x: (_sig_rank[x.significance], -x.strength_score))

    return ScoredLevels(
        ticker=ticker,
        view_mode=view_config.name,
        tagged_levels=tagged_output,
        bias=levels.directional_bias,
        regime=levels.gex_regime
    )
