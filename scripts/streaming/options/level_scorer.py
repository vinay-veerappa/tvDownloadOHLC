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
from .options_fetcher import OptionChainData
from .config import ViewModeConfig, INTRADAY_VIEW, MACRO_VIEW, TickerProfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import math

log = logging.getLogger(__name__)

@dataclass
class TaggedLevel:
    """Base class for a recognized dealer level."""
    strike: float
    label: str
    significance: str  # PRIMARY, SECONDARY, CONTEXT
    side: str          # CALL, PUT, NEUTRAL
    description: str = ""
    field_name: str = "" # Backwards compat with DealerLevels field

@dataclass
class MechanicalWall(TaggedLevel):
    """Filter 1: Levels defined by book-depth concentration."""
    net_gex: float = 0.0
    pct_of_book: float = 0.0
    hedge_contracts: int = 0
    proximity_score: float = 0.0

@dataclass
class StructuralAnchor(TaggedLevel):
    """Filter 2: Large-OI institutional positions."""
    open_interest: int = 0
    matched_program: str = "" # e.g. JHEQX
    oi_zscore: float = 0.0
    relevance: str = "DORMANT" # DORMANT, APPROACHING, ACTIVE, CRITICAL
    days_to_expiry: int = 0

@dataclass
class InflectionPoint(TaggedLevel):
    """Filter 3: Points where dealer positioning transitions."""
    inflection_type: str = "FLIP" # FLIP (0 Gamma), MAGNET (Pin), VOID (Gap)
    slope_magnitude: float = 0.0
    gamma_velocity: float = 0.0

@dataclass
class CalendarContext:
    """Opex and cycle awareness."""
    is_opex_week: bool = False
    is_opex_day: bool = False
    days_to_monthly_opex: int = 0
    days_to_quarterly_opex: int = 0

@dataclass
class ScoredLevels:
    """The final prioritized output of the scoring engine."""
    ticker: str
    view_mode: str
    tagged_levels: list[TaggedLevel] = field(default_factory=list)
    calendar: CalendarContext = field(default_factory=CalendarContext)
    bias: str = "NEUTRAL"
    regime: str = "TRANSITION"
    
    @property
    def resistance_walls(self) -> list[MechanicalWall]:
        return [l for l in self.tagged_levels if isinstance(l, MechanicalWall) and l.side == "CALL"]

    @property
    def support_walls(self) -> list[MechanicalWall]:
        return [l for l in self.tagged_levels if isinstance(l, MechanicalWall) and l.side == "PUT"]

    @property
    def strategic(self) -> list[StructuralAnchor]:
        return [l for l in self.tagged_levels if isinstance(l, StructuralAnchor) or l.significance == "PRIMARY"]

    @property
    def pivots(self) -> list[InflectionPoint]:
        return [l for l in self.tagged_levels if isinstance(l, InflectionPoint) or l.label == "Zero Gamma Level"]

    @property
    def contextual(self) -> list[TaggedLevel]:
        return [l for l in self.tagged_levels if l.significance == "CONTEXT"]


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

def _calendar_context(today: date) -> CalendarContext:
    """Calculate proximity to major option expirations."""
    # Monthly OPEX: 3rd Friday of the month
    def get_third_friday(yr, mo):
        d = date(yr, mo, 15)
        while d.weekday() != 4:
            d += timedelta(days=1)
        return d

    monthly_opex = get_third_friday(today.year, today.month)
    if today > monthly_opex:
        # Check next month
        nm = today.month + 1 if today.month < 12 else 1
        ny = today.year if today.month < 12 else today.year + 1
        monthly_opex = get_third_friday(ny, nm)

    # Quarterly OPEX: March, June, Sept, Dec
    q_months = [3, 6, 9, 12]
    q_month = next((m for m in q_months if m >= today.month), 3)
    q_year = today.year
    if today > get_third_friday(q_year, q_month) and q_month == 12:
        q_month = 3
        q_year += 1
    elif today > get_third_friday(q_year, q_month):
        q_month = next((m for m in q_months if m > q_month), 3)
        
    quarterly_opex = get_third_friday(q_year, q_month)

    days_to_m = (monthly_opex - today).days
    days_to_q = (quarterly_opex - today).days
    
    return CalendarContext(
        is_opex_week=days_to_m <= 5,
        is_opex_day=today == monthly_opex,
        days_to_monthly_opex=days_to_m,
        days_to_quarterly_opex=days_to_q
    )

def _score_mechanical_walls(
    levels: Any, # DealerLevels
    profile: TickerProfile,
    lo: float, hi: float
) -> list[MechanicalWall]:
    """Filter 1: Detect primary and tactical gamma walls."""
    walls: list[MechanicalWall] = []
    # Build a quick lookup from strike_gex
    _gex_by_strike = {round(sg.strike, 2): sg.net_gex for sg in levels.strike_gex} if levels.strike_gex else {}
    # Absolute Walls
    if levels.call_wall is not None and lo <= levels.call_wall <= hi:
        walls.append(MechanicalWall(
            strike=levels.call_wall,
            label="Absolute Call Wall",
            significance="PRIMARY",
            side="CALL",
            net_gex=_gex_by_strike.get(round(levels.call_wall, 2), 0.0),
            field_name="call_wall"
        ))
    
    if levels.put_wall is not None and lo <= levels.put_wall <= hi:
        walls.append(MechanicalWall(
            strike=levels.put_wall,
            label="Absolute Put Wall",
            significance="PRIMARY",
            side="PUT",
            net_gex=_gex_by_strike.get(round(levels.put_wall, 2), 0.0),
            field_name="put_wall"
        ))

    # Tactical (0DTE/Near-term) Walls
    if hasattr(levels, "call_wall_0dte") and levels.call_wall_0dte is not None and lo <= levels.call_wall_0dte <= hi:
        if round(levels.call_wall_0dte, 2) != round(levels.call_wall, 2):
            walls.append(MechanicalWall(
                strike=levels.call_wall_0dte,
                label="Tactical Call Wall",
                significance="SECONDARY",
                side="CALL",
                field_name="call_wall_0dte"
            ))

    if hasattr(levels, "put_wall_0dte") and levels.put_wall_0dte is not None and lo <= levels.put_wall_0dte <= hi:
        if round(levels.put_wall_0dte, 2) != round(levels.put_wall, 2):
            walls.append(MechanicalWall(
                strike=levels.put_wall_0dte,
                label="Tactical Put Wall",
                significance="SECONDARY",
                side="PUT",
                field_name="put_wall_0dte"
            ))

    # Calculate metrics for walls
    for w in walls:
        # Distance proximity (1.0 at spot, 0.0 at boundary)
        dist = abs(w.strike - levels.spot)
        max_dist = levels.spot * 0.15 # 15% range
        w.proximity_score = max(0.0, 1.0 - (dist / max_dist))
        
        # Hedge Contracts Estimate
        if profile.contract_value_per_point > 0:
            # Simple heuristic: absolute GEX / (multiplier * price)
            w.hedge_contracts = int(abs(w.net_gex) / (profile.contract_value_per_point * levels.spot)) if w.net_gex else 0
            # Normalized against book depth
            if profile.book_depth_contracts > 0:
                w.pct_of_book = w.hedge_contracts / profile.book_depth_contracts

    return walls

def _detect_structural_anchors(
    chain: OptionChainData,
    profile: TickerProfile,
    cal: CalendarContext,
    lo: float, hi: float
) -> list[StructuralAnchor]:
    """Filter 2: Detect institutional program nodes from OI anomalies."""
    anchors: list[StructuralAnchor] = []
    from .config import STRUCTURAL_PROGRAMS
    
    # 1. Get Top OI Strikes
    all_contracts = chain.contracts
    if not all_contracts: return []
    
    # Filter by proximity and minimum OI
    relevant = [c for c in all_contracts if lo <= c.strike <= hi and c.open_interest >= profile.min_oi_floor]
    
    # Sort by OI desc
    top_oi = sorted(relevant, key=lambda x: x.open_interest, reverse=True)[:10]
    
    # Check against known programs
    for c in top_oi:
        matched_prog = None
        relevance = "DORMANT"
        
        for prog_id in profile.known_programs:
            prog = STRUCTURAL_PROGRAMS.get(prog_id)
            if not prog: continue
            
            # Match rules
            strike_matches = prog.moneyness_range[0] <= (c.strike / chain.spot_price) <= prog.moneyness_range[1]
            oi_matches = c.open_interest >= prog.typical_oi_min
            
            # Expiry match (Quarterly vs Monthly)
            is_quarterly = c.expiry.month in [3, 6, 9, 12]
            expiry_matches = (prog.schedule == "quarterly" and is_quarterly) or (prog.schedule == "monthly")
            
            if strike_matches and oi_matches and expiry_matches:
                matched_prog = prog.name
                # Escalation logic
                if cal.days_to_quarterly_opex <= prog.roll_window_days and is_quarterly:
                    relevance = "CRITICAL" # In roll window
                elif cal.is_opex_week:
                    relevance = "ACTIVE"
                else:
                    relevance = "APPROACHING"
                break
        
        if matched_prog:
            anchors.append(StructuralAnchor(
                strike=c.strike,
                label=matched_prog,
                significance="PRIMARY",
                side="CALL" if c.contract_type == "CALL" else "PUT",
                open_interest=c.open_interest,
                matched_program=matched_prog,
                relevance=relevance,
                days_to_expiry=(c.expiry - date.today()).days
            ))
    # Second pass: flag unknown anomalies via z-score
    # Group contracts by expiry, compute OI stats, flag outliers
    from collections import defaultdict
    by_expiry = defaultdict(list)
    for c in relevant:
        if isinstance(c.expiry, date):
            by_expiry[c.expiry].append(c)

    already_flagged = {a.strike for a in anchors}

    for expiry, contracts in by_expiry.items():
        oi_values = [c.open_interest for c in contracts]
        if len(oi_values) < 10:
            continue
        mean_oi = sum(oi_values) / len(oi_values)
        var_oi = sum((x - mean_oi) ** 2 for x in oi_values) / len(oi_values)
        std_oi = math.sqrt(var_oi) if var_oi > 0 else 1.0

        for c in contracts:
            if c.strike in already_flagged:
                continue
            zscore = (c.open_interest - mean_oi) / std_oi
            if zscore < profile.oi_node_zscore:
                continue
            dte = (c.expiry - date.today()).days
            anchors.append(StructuralAnchor(
                strike=c.strike,
                label=f"OI Node ({zscore:.1f}σ)",
                significance="SECONDARY",
                side="CALL" if c.contract_type == "CALL" else "PUT",
                open_interest=c.open_interest,
                matched_program="",
                oi_zscore=round(zscore, 2),
                relevance="APPROACHING" if dte <= 45 else "DORMANT",
                days_to_expiry=dte,
            ))
            already_flagged.add(c.strike)        
    return anchors

def _find_inflection_points(
    levels: Any,
    lo: float, hi: float
) -> list[InflectionPoint]:
    """Filter 3: Zero Gamma and structural flip zones."""
    pts: list[InflectionPoint] = []
    
    if levels.zero_gamma is not None and lo <= levels.zero_gamma <= hi:
        pts.append(InflectionPoint(
            strike=levels.zero_gamma,
            label="Zero Gamma Level",
            significance="SECONDARY", # Design called it PIVOT, using SECONDARY for taxonomy
            side="NEUTRAL",
            inflection_type="FLIP",
            field_name="zero_gamma"
        ))

    if hasattr(levels, "gamma_flip_upper") and levels.gamma_flip_upper is not None and lo <= levels.gamma_flip_upper <= hi:
        pts.append(InflectionPoint(
            strike=levels.gamma_flip_upper,
            label="Gamma Flip High",
            significance="CONTEXT",
            side="NEUTRAL",
            inflection_type="FLIP",
            field_name="gamma_flip_upper"
        ))

    if hasattr(levels, "gamma_magnet") and levels.gamma_magnet is not None and lo <= levels.gamma_magnet <= hi:
        pts.append(InflectionPoint(
            strike=levels.gamma_magnet,
            label="Gamma Magnet",
            significance="CONTEXT",
            side="NEUTRAL",
            inflection_type="MAGNET",
            field_name="gamma_magnet"
        ))
    if levels.gamma_cliff_up is not None and lo <= levels.gamma_cliff_up <= hi:
        pts.append(InflectionPoint(
            strike=levels.gamma_cliff_up,
            label="Gamma Cliff Up",
            significance="CONTEXT",
            side="CALL",
            inflection_type="CLIFF",
            field_name="gamma_cliff_up"
        ))

    if levels.gamma_cliff_down is not None and lo <= levels.gamma_cliff_down <= hi:
        pts.append(InflectionPoint(
            strike=levels.gamma_cliff_down,
            label="Gamma Cliff Down",
            significance="CONTEXT",
            side="PUT",
            inflection_type="CLIFF",
            field_name="gamma_cliff_down"
        ))

    if levels.liquidity_vacuum_lower is not None and lo <= levels.liquidity_vacuum_lower <= hi:
        pts.append(InflectionPoint(
            strike=levels.liquidity_vacuum_lower,
            label="Liquidity Void (Low)",
            significance="CONTEXT",
            side="NEUTRAL",
            inflection_type="VOID",
            field_name="liquidity_vacuum_lower"
        ))

    if levels.liquidity_vacuum_upper is not None and lo <= levels.liquidity_vacuum_upper <= hi:
        pts.append(InflectionPoint(
            strike=levels.liquidity_vacuum_upper,
            label="Liquidity Void (High)",
            significance="CONTEXT",
            side="NEUTRAL",
            inflection_type="VOID",
            field_name="liquidity_vacuum_upper"
        ))
    return pts

def score_levels(
    levels: Any,
    chain: OptionChainData,
    ticker: str,
    profile: TickerProfile,
    view_mode: ViewModeConfig = INTRADAY_VIEW
) -> ScoredLevels:
    """
    Orchestrates the Three-Filter Triage to build a prioritized level structured.
    """
    spot = levels.spot
    lo = spot * (1.0 - view_mode.strike_range_pct)
    hi = spot * (1.0 + view_mode.strike_range_pct)
    
    # 0. Context
    cal = _calendar_context(date.today())
    
    # Filter 1: Mechanical
    walls = _score_mechanical_walls(levels, profile, lo, hi)
    
    # Filter 2: Structural
    anchors = _detect_structural_anchors(chain, profile, cal, lo, hi)
    
    # Filter 3: Inflection
    inflection = _find_inflection_points(levels, lo, hi)
    
    # Combine and Deduplicate
    all_levels: list[TaggedLevel] = []
    seen_strikes: set[float] = set()
    
    # Order of priority: Anchors > Walls > Inflection
    # But only if they are allowed by the view's mask
    mask = view_mode.significance_mask
    
    for l in (anchors + walls + inflection):
        if l.significance not in mask:
            continue
        
        # Round strike for dedup
        s_rounded = round(l.strike, 1)
        if s_rounded in seen_strikes:
            continue
            
        seen_strikes.add(s_rounded)
        all_levels.append(l)

    # Final Sort: PRIMARY first, then proximity to spot
    def _rank(lvl):
        sig_rank = {"PRIMARY": 0, "SECONDARY": 1, "CONTEXT": 2}
        dist_rank = abs(lvl.strike - spot) / spot
        return (sig_rank.get(lvl.significance, 2), dist_rank)

    all_levels.sort(key=_rank)

    return ScoredLevels(
        ticker=ticker,
        view_mode=view_mode.name,
        tagged_levels=all_levels,
        calendar=cal,
        bias=levels.directional_bias,
        regime=levels.gex_regime
    )
