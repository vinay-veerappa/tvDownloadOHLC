"""
futures_translator.py
=====================
Translate cash-index levels (SPX/NDX) into futures-space (ES/NQ).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .gex_calculator import DealerLevels
from .options_fetcher import FuturesQuote

log = logging.getLogger(__name__)


@dataclass
class TranslatedLevels:
    futures_symbol: str
    cash_ticker: str
    futures_price: float
    cash_spot: float
    basis_spread: float         # Additive: futures - cash (e.g. ES-SPX = +4). Multiplicative: 0.0
    basis_ratio: float          # Multiplicative: futures/cash (e.g. NQ/QQQ = 41.4). Additive: 1.0
    translation_mode: str       # "additive" or "multiplicative"
    total_gex: float
    gex_regime: str

    zero_gamma: float | None
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
    net_speed_exposure: float
    total_gex_delta_adj: float | None
    call_volume_centroid: float | None
    put_volume_centroid: float | None
    atm_iv: float | None          # ATM implied volatility from cash chain (passes through unchanged)
    iv_change: float               # Percentage change in IV


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
    # scales (e.g. QQQ ~600 → NQ ~24400, ratio ~41).  Additive basis is correct
    # only when they trade at the same scale (e.g. SPX ~6632 → ES ~6636, ratio ~1).
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

    def _shift(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value * ratio, 2) if use_scale else round(value + spread, 2)

    # em_value is a ± magnitude (not a price level).  Magnitude scales with ratio.
    translated_em_value = (
        round(levels.em_value * ratio, 2) if use_scale
        else round(levels.em_value, 2)
    )

    return TranslatedLevels(
        futures_symbol=futures.symbol,
        cash_ticker=levels.ticker,
        futures_price=futures.price,
        cash_spot=levels.spot,
        basis_spread=round(spread, 2) if not use_scale else 0.0,
        basis_ratio=round(ratio, 4) if use_scale else 1.0,
        translation_mode="multiplicative" if use_scale else "additive",
        total_gex=levels.total_gex,
        gex_regime=levels.gex_regime,
        zero_gamma=_shift(levels.zero_gamma),
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
            round(levels.wall_separation * ratio, 2) if use_scale and levels.wall_separation is not None
            else levels.wall_separation
        ),
        regime_label=levels.regime_label,
        directional_bias=levels.directional_bias,
        call_gamma_total=levels.call_gamma_total,
        put_gamma_total=levels.put_gamma_total,
        net_vanna_exposure=levels.net_vanna_exposure,
        net_speed_exposure=levels.net_speed_exposure,
        total_gex_delta_adj=levels.total_gex_delta_adj,
        call_volume_centroid=_shift(levels.call_volume_centroid),
        put_volume_centroid=_shift(levels.put_volume_centroid),
        atm_iv=levels.atm_iv,  # dimensionless — pass through unchanged
        iv_change=levels.iv_change,
    )