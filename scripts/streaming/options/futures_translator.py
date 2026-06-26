"""
futures_translator.py
=====================
Translate cash-index levels (SPX/NDX) into futures-space (ES/NQ).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math

from .gex_calculator import DealerLevels, ExpectedMove, StrikeGEX
from .options_fetcher import FuturesQuote

log = logging.getLogger(__name__)


def get_min_tick(symbol: str) -> float:
    """Determine the minimum tick increment for a futures symbol."""
    sym = symbol.upper().lstrip('/')
    # Strip micro prefix if present
    if sym.startswith('M') and (
        sym[1:3] in ['ES', 'NQ', 'YM', 'GC', 'SI', 'HG', '6E', '6A', '6B', '6J'] or 
        sym[1:4] in ['RTY', 'CL']
    ):
        sym = sym[1:]
        
    if sym.startswith('ES') or sym.startswith('NQ'):
        return 0.25
    elif sym.startswith('YM'):
        return 1.0
    elif sym.startswith('RTY') or sym.startswith('GC'):
        return 0.1
    elif sym.startswith('CL'):
        return 0.01
    elif sym.startswith('SI'):
        return 0.005
    elif sym.startswith('HG'):
        return 0.0005
    elif sym.startswith('6E') or sym.startswith('6A') or sym.startswith('6B'):
        return 0.0001
    elif sym.startswith('6J'):
        return 0.000001
    else:
        return 0.01


def round_to_tick(value: float, min_tick: float) -> float:
    """Round a price value to the nearest minimum tick increment."""
    min_tick_str = f"{min_tick:.8f}".rstrip('0')
    decimals = len(min_tick_str.split('.')[1]) if '.' in min_tick_str else 0
    return round(round(value / min_tick) * min_tick, decimals)


@dataclass
class TranslatedLevels:
    futures_symbol: str
    cash_ticker: str
    futures_price: float
    cash_spot: float
    basis_spread: float         # Additive: futures - cash (e.g. ES-SPX = +4). Multiplicative: 0.0
    basis_ratio: float          # Multiplicative: futures/cash (e.g. NQ/QQQ = 41.4). Additive: 1.0
    translation_mode: str       # "additive" or "multiplicative"
    min_tick: float
    total_gex: float
    gex_regime: str

    zero_gamma: float | None
    zero_gamma_delta_adj: float | None
    gamma_flip_lower: float | None
    gamma_flip_upper: float | None

    call_wall: float | None
    put_wall: float | None
    secondary_call_wall: float | None
    secondary_put_wall: float | None
    local_call_node: float | None
    local_put_node: float | None
    call_wall_0dte: float | None
    put_wall_0dte: float | None

    hedge_wall: float | None
    max_pain: float | None

    em_upper: float
    em_lower: float
    em_value: float
    atm_straddle: float

    vol_trigger_upper_05: float | None
    vol_trigger_lower_05: float | None
    vol_trigger_upper_10: float | None
    vol_trigger_lower_10: float | None
    vol_trigger_upper_15: float | None
    vol_trigger_lower_15: float | None

    gamma_cliff_up: float | None
    gamma_cliff_down: float | None

    vanna_call_node: float | None
    vanna_put_node: float | None
    charm_call_node: float | None
    charm_put_node: float | None

    volume_imbalance_call_node: float | None
    volume_imbalance_put_node: float | None

    dex_call_node: float | None
    dex_put_node: float | None

    liquidity_vacuum_lower: float | None
    liquidity_vacuum_upper: float | None

    skew_pivot_put_25d: float | None
    skew_pivot_call_25d: float | None

    # ── Tier 2: Market-structure metrics ──────────────────────────────────
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
    net_speed_exposure: float
    hedge_flow_up_10: float
    hedge_flow_up_25: float
    hedge_flow_up_50: float
    hedge_flow_dn_10: float
    hedge_flow_dn_25: float
    hedge_flow_dn_50: float
    hourly_flow_curve: list[dict[str, float | str]]
    total_gex_delta_adj: float | None
    call_volume_centroid: float | None
    put_volume_centroid: float | None
    atm_iv: float | None          # ATM implied volatility from cash chain (passes through unchanged)
    iv_change: float               # Percentage change in IV
    expected_moves: list[ExpectedMove]
    strike_gex: list[StrikeGEX] = field(default_factory=list) # Re-add just in case needed for UI pass-through
    put_25d_iv: float | None = None
    call_25d_iv: float | None = None
    volatility_skew_premium: float | None = None


def translate_to_futures(
    levels: DealerLevels, 
    futures: FuturesQuote,
    anchor_basis: float | None = None,
    anchor_ratio: float | None = None,
) -> TranslatedLevels:
    """
    Translate cash levels to futures space.
    
    If anchor_basis or anchor_ratio is provided, it replaces the dynamic (futures.price - levels.spot)
    or (futures.price / levels.spot) for translation. This pins the basis/scale to the market open.
    """
    spread = anchor_basis if anchor_basis is not None else (futures.price - levels.spot)
    ratio = anchor_ratio if anchor_ratio is not None else (futures.price / levels.spot if levels.spot else 1.0)

    # Use multiplicative scaling when cash source and futures trade at different
    # scales (e.g. QQQ ~600 -> NQ ~24400, ratio ~41).  Additive basis is correct
    # only when they trade at the same scale (e.g. SPX ~6632 -> ES ~6636, ratio ~1).
    #
    # Threshold: if the ratio deviates from 1.0 by more than 2%, use multiplicative.
    use_scale = abs(ratio - 1.0) > 0.02
    log.info(
        "%s %s vs %s: %+.2f  (futures=%.2f  cash=%.2f  ratio=%.4f)",
        "Scale" if use_scale else "Basis",
        futures.symbol,
        levels.ticker,
        spread,
        futures.price,
        levels.spot,
        ratio,
    )

    min_tick = get_min_tick(futures.symbol)

    def _shift(value: float | None) -> float | None:
        if value is None:
            return None
        raw_val = value * ratio if use_scale else value + spread
        return round_to_tick(raw_val, min_tick)

    # em_value is a ± magnitude (not a price level).  Magnitude scales with ratio.
    translated_em_value = (
        round_to_tick(levels.em_value * ratio, min_tick) if use_scale
        else round_to_tick(levels.em_value, min_tick)
    )

    # Attach Translation Matrix to the original DealerLevels object
    levels.futures_symbol = futures.symbol
    levels.translation_mode = "multiplicative" if use_scale else "additive"
    levels.basis_spread = round(spread, 2) if not use_scale else 0.0
    levels.basis_ratio = round(ratio, 4) if use_scale else 1.0

    return TranslatedLevels(
        futures_symbol=futures.symbol,
        cash_ticker=levels.ticker,
        futures_price=futures.price,
        cash_spot=levels.spot,
        basis_spread=round(spread, 2) if not use_scale else 0.0,
        basis_ratio=round(ratio, 4) if use_scale else 1.0,
        translation_mode="multiplicative" if use_scale else "additive",
        min_tick=min_tick,
        total_gex=levels.total_gex,
        gex_regime=levels.gex_regime,
        zero_gamma=_shift(levels.zero_gamma),
        zero_gamma_delta_adj=_shift(levels.zero_gamma_delta_adj),
        gamma_flip_lower=_shift(levels.gamma_flip_lower),
        gamma_flip_upper=_shift(levels.gamma_flip_upper),
        call_wall=_shift(levels.call_wall),
        put_wall=_shift(levels.put_wall),
        secondary_call_wall=_shift(levels.secondary_call_wall),
        secondary_put_wall=_shift(levels.secondary_put_wall),
        local_call_node=_shift(levels.local_call_node),
        local_put_node=_shift(levels.local_put_node),
        call_wall_0dte=_shift(levels.call_wall_0dte),
        put_wall_0dte=_shift(levels.put_wall_0dte),
        hedge_wall=_shift(levels.hedge_wall),
        max_pain=_shift(levels.max_pain),
        em_upper=_shift(levels.em_upper),  # type: ignore[arg-type]
        em_lower=_shift(levels.em_lower),  # type: ignore[arg-type]
        em_value=translated_em_value,
        atm_straddle=levels.atm_straddle,
        vol_trigger_upper_05=_shift(levels.vol_trigger_upper_05),
        vol_trigger_lower_05=_shift(levels.vol_trigger_lower_05),
        vol_trigger_upper_10=_shift(levels.vol_trigger_upper_10),
        vol_trigger_lower_10=_shift(levels.vol_trigger_lower_10),
        vol_trigger_upper_15=_shift(levels.vol_trigger_upper_15),
        vol_trigger_lower_15=_shift(levels.vol_trigger_lower_15),
        gamma_cliff_up=_shift(levels.gamma_cliff_up),
        gamma_cliff_down=_shift(levels.gamma_cliff_down),
        vanna_call_node=_shift(levels.vanna_call_node),
        vanna_put_node=_shift(levels.vanna_put_node),
        charm_call_node=_shift(levels.charm_call_node),
        charm_put_node=_shift(levels.charm_put_node),
        volume_imbalance_call_node=_shift(levels.volume_imbalance_call_node),
        volume_imbalance_put_node=_shift(levels.volume_imbalance_put_node),
        dex_call_node=_shift(levels.dex_call_node),
        dex_put_node=_shift(levels.dex_put_node),
        liquidity_vacuum_lower=_shift(levels.liquidity_vacuum_lower),
        liquidity_vacuum_upper=_shift(levels.liquidity_vacuum_upper),
        skew_pivot_put_25d=_shift(levels.skew_pivot_put_25d),
        skew_pivot_call_25d=_shift(levels.skew_pivot_call_25d),
        gamma_magnet=_shift(levels.gamma_magnet),
        pin_strike=_shift(levels.pin_strike),
        pin_odds=levels.pin_odds,
        wall_separation=(
            round_to_tick(levels.wall_separation * ratio, min_tick) if use_scale and levels.wall_separation is not None
            else (round_to_tick(levels.wall_separation, min_tick) if levels.wall_separation is not None else None)
        ),
        regime_label=levels.regime_label,
        directional_bias=levels.directional_bias,
        call_gamma_total=levels.call_gamma_total,
        put_gamma_total=levels.put_gamma_total,
        net_vanna_exposure=levels.net_vanna_exposure,
        wall_scope=levels.wall_scope,
        wall_dte_min=levels.wall_dte_min,
        wall_dte_max=levels.wall_dte_max,
        concentration_score=levels.concentration_score,
        call_wall_oi=levels.call_wall_oi,
        put_wall_oi=levels.put_wall_oi,
        pin_strike_oi=levels.pin_strike_oi,
        net_speed_exposure=levels.net_speed_exposure,
        hedge_flow_up_10=levels.hedge_flow_up_10,
        hedge_flow_up_25=levels.hedge_flow_up_25,
        hedge_flow_up_50=levels.hedge_flow_up_50,
        hedge_flow_dn_10=levels.hedge_flow_dn_10,
        hedge_flow_dn_25=levels.hedge_flow_dn_25,
        hedge_flow_dn_50=levels.hedge_flow_dn_50,
        hourly_flow_curve=levels.hourly_flow_curve,
        total_gex_delta_adj=levels.total_gex_delta_adj,
        call_volume_centroid=_shift(levels.call_volume_centroid),
        put_volume_centroid=_shift(levels.put_volume_centroid),
        atm_iv=levels.atm_iv,
        iv_change=levels.iv_change,
        put_25d_iv=levels.put_25d_iv,
        call_25d_iv=levels.call_25d_iv,
        volatility_skew_premium=levels.volatility_skew_premium,
        expected_moves=[
            ExpectedMove(
                expiry=em.expiry,
                dte=em.dte,
                em_value=round_to_tick(em.em_value * ratio, min_tick) if use_scale else round_to_tick(em.em_value, min_tick),
                em_upper=_shift(em.em_upper),
                em_lower=_shift(em.em_lower),
                straddle=round_to_tick(em.straddle * ratio, min_tick) if use_scale else round_to_tick(em.straddle, min_tick),
                straddle_85_upper=_shift(em.straddle_85_upper) or 0.0,
                straddle_85_lower=_shift(em.straddle_85_lower) or 0.0,
            )
            for em in levels.expected_moves
        ],
        strike_gex=levels.strike_gex,
    )


def translate_scored_levels(
    scored: ScoredLevels,
    basis_spread: float,
    basis_ratio: float,
    use_scale: bool,
    min_tick: float | None = None,
) -> ScoredLevels:
    """
    Translate the strikes and expected moves in a ScoredLevels object to futures space.
    """
    import copy
    from .level_scorer import ScoredLevels
    
    translated_scored = copy.deepcopy(scored)
    
    def _shift(value: float | None) -> float | None:
        if value is None:
            return None
        raw_val = value * basis_ratio if use_scale else value + basis_spread
        if min_tick is not None:
            return round_to_tick(raw_val, min_tick)
        return round(raw_val, 2)

    # Shift each TaggedLevel strike
    for level in translated_scored.tagged_levels:
        if level.strike is not None:
            level.strike = _shift(level.strike)

    # Shift each ExpectedMove
    shifted_ems = []
    for em in translated_scored.expected_moves:
        shifted_ems.append(
            ExpectedMove(
                expiry=em.expiry,
                dte=em.dte,
                em_value=round_to_tick(em.em_value * basis_ratio, min_tick) if min_tick is not None else (round(em.em_value * basis_ratio, 2) if use_scale else em.em_value),
                em_upper=_shift(em.em_upper),
                em_lower=_shift(em.em_lower),
                straddle=round_to_tick(em.straddle * basis_ratio, min_tick) if min_tick is not None else (round(em.straddle * basis_ratio, 2) if use_scale else em.straddle),
                straddle_85_upper=_shift(getattr(em, "straddle_85_upper", 0.0)) or 0.0,
                straddle_85_lower=_shift(getattr(em, "straddle_85_lower", 0.0)) or 0.0,
            )
        )
    translated_scored.expected_moves = shifted_ems
    return translated_scored

