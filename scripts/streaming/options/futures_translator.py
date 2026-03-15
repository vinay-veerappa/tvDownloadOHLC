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
    basis_spread: float
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


def translate_to_futures(levels: DealerLevels, futures: FuturesQuote) -> TranslatedLevels:
    spread = futures.price - levels.spot
    ratio = futures.price / levels.spot if levels.spot else 1.0
    # Use multiplicative scaling when cash source and futures trade at different scales
    # (e.g. QQQ ~600 -> NQ ~24400, ratio ~41).  Additive basis is correct only when
    # they trade at the same scale (e.g. SPX ~6632 -> ES ~6636, ratio ~1).
    use_scale = abs(ratio - 1.0) > 0.1
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

    return TranslatedLevels(
        futures_symbol=futures.symbol,
        cash_ticker=levels.ticker,
        futures_price=futures.price,
        cash_spot=levels.spot,
        basis_spread=round(spread, 2),
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
        em_value=levels.em_value,
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
    )
