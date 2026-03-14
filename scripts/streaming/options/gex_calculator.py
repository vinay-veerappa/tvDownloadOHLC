"""
gex_calculator.py
=================
Core quantitative engine for dealer-positioning and intraday options levels.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from .config import CONTRACT_MULTIPLIER, EM_STRADDLE_SCALAR, MIN_OI_THRESHOLD, USE_STRADDLE_EM
from .options_fetcher import OptionChainData, OptionContract

log = logging.getLogger(__name__)


@dataclass
class StrikeGEX:
    strike: float
    call_gex: float
    put_gex: float
    net_gex: float
    call_oi: int
    put_oi: int
    call_vol: int
    put_vol: int
    cumulative_gex: float = 0.0


@dataclass
class DealerLevels:
    ticker: str
    spot: float
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

    strike_gex: list[StrikeGEX] = field(default_factory=list)


def _best_contract_per_strike(contracts: list[OptionContract]) -> dict[float, OptionContract]:
    best: dict[float, OptionContract] = {}
    for contract in contracts:
        existing = best.get(contract.strike)
        if existing is None or contract.open_interest > existing.open_interest:
            best[contract.strike] = contract
    return best


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _build_strike_gex(calls: list[OptionContract], puts: list[OptionContract], spot: float) -> list[StrikeGEX]:
    call_map = _best_contract_per_strike(calls)
    put_map = _best_contract_per_strike(puts)
    all_strikes = sorted(set(call_map) | set(put_map))

    rows: list[StrikeGEX] = []
    for strike in all_strikes:
        call = call_map.get(strike)
        put = put_map.get(strike)
        call_gex = abs(call.gamma) * call.open_interest * CONTRACT_MULTIPLIER * spot if call else 0.0
        put_gex = abs(put.gamma) * put.open_interest * CONTRACT_MULTIPLIER * spot if put else 0.0
        rows.append(
            StrikeGEX(
                strike=strike,
                call_gex=call_gex,
                put_gex=put_gex,
                net_gex=call_gex - put_gex,
                call_oi=call.open_interest if call else 0,
                put_oi=put.open_interest if put else 0,
                call_vol=call.volume if call else 0,
                put_vol=put.volume if put else 0,
            )
        )
    return rows


def _build_cumulative_profile(strike_gex: list[StrikeGEX]) -> list[StrikeGEX]:
    running = 0.0
    for row in strike_gex:
        running += row.net_gex
        row.cumulative_gex = running
    return strike_gex


def _find_walls(contracts: list[OptionContract], min_oi: int) -> tuple[float | None, float | None]:
    candidates = [c for c in contracts if c.open_interest >= min_oi]
    if not candidates:
        return None, None
    ranked = sorted(candidates, key=lambda c: c.open_interest * abs(c.gamma), reverse=True)
    primary = ranked[0].strike
    secondary = ranked[1].strike if len(ranked) > 1 else None
    return primary, secondary


def _find_local_nodes(strikes: list[StrikeGEX], spot: float) -> tuple[float | None, float | None]:
    if not strikes or spot <= 0:
        return None, None
    lo = spot * 0.985
    hi = spot * 1.015
    local = [row for row in strikes if lo <= row.strike <= hi]
    if not local:
        local = strikes
    return max(local, key=lambda row: row.call_gex).strike, max(local, key=lambda row: row.put_gex).strike


def _find_front_dte_contracts(calls: list[OptionContract], puts: list[OptionContract]) -> tuple[list[OptionContract], list[OptionContract]]:
    universe = calls + puts
    if not universe:
        return [], []
    front_dte = min(contract.dte for contract in universe)
    return [c for c in calls if c.dte == front_dte], [p for p in puts if p.dte == front_dte]


def _find_gamma_flip_zone(strikes: list[StrikeGEX], spot: float, min_oi: int) -> tuple[float | None, float | None, float | None]:
    if not strikes:
        return None, None, None

    def significant(row: StrikeGEX) -> bool:
        return (row.call_oi + row.put_oi) >= min_oi

    crossing = None
    for idx in range(1, len(strikes)):
        if strikes[idx - 1].cumulative_gex * strikes[idx].cumulative_gex < 0:
            crossing = idx
            break

    if crossing is not None:
        lower = next((strikes[i].strike for i in range(crossing - 1, -1, -1) if significant(strikes[i])), None)
        upper = next((strikes[i].strike for i in range(crossing, len(strikes)) if significant(strikes[i])), None)
    else:
        below = [row for row in strikes if row.strike <= spot and significant(row)]
        above = [row for row in strikes if row.strike >= spot and significant(row)]
        lower = below[-1].strike if below else spot
        upper = above[0].strike if above else spot

    lower = lower if lower is not None else spot
    upper = upper if upper is not None else spot
    mid = round((float(lower) + float(upper)) / 2.0, 2)
    return float(lower), float(upper), mid


def _find_hedge_wall(strikes: list[StrikeGEX], spot: float) -> float | None:
    downside = [row for row in strikes if row.strike < spot and row.put_oi > 0]
    if not downside:
        return None
    return min(downside, key=lambda row: row.net_gex).strike


def _atm_contract(calls: list[OptionContract], spot: float) -> OptionContract | None:
    if not calls:
        return None
    return min(calls, key=lambda contract: abs(contract.strike - spot))


def _atm_straddle_cost(calls: list[OptionContract], puts: list[OptionContract], spot: float) -> float:
    if not calls or not puts:
        return 0.0
    atm_call = min(calls, key=lambda contract: abs(contract.strike - spot))
    atm_put = min(puts, key=lambda contract: abs(contract.strike - spot))
    return atm_call.ask + atm_put.ask


def _expected_move(calls: list[OptionContract], puts: list[OptionContract], spot: float) -> tuple[float, float]:
    straddle = _atm_straddle_cost(calls, puts, spot)
    if USE_STRADDLE_EM:
        return straddle * EM_STRADDLE_SCALAR, straddle

    atm = _atm_contract(calls, spot)
    if atm is None or atm.iv <= 0:
        return 0.0, straddle
    iv_move = spot * atm.iv * math.sqrt(max(atm.dte, 1) / 365.0)
    return iv_move, straddle


def _find_max_pain(calls: list[OptionContract], puts: list[OptionContract]) -> float | None:
    call_map = _best_contract_per_strike(calls)
    put_map = _best_contract_per_strike(puts)
    strikes = sorted(set(call_map) | set(put_map))
    if not strikes:
        return None

    best_strike = None
    best_loss = float("inf")
    for px in strikes:
        call_loss = sum(contract.open_interest * max(0.0, px - contract.strike) for contract in call_map.values())
        put_loss = sum(contract.open_interest * max(0.0, contract.strike - px) for contract in put_map.values())
        total = call_loss + put_loss
        if total < best_loss:
            best_loss = total
            best_strike = px

    return best_strike


def _find_gamma_cliffs(strikes: list[StrikeGEX], spot: float) -> tuple[float | None, float | None]:
    if len(strikes) < 2:
        return None, None

    diffs = []
    for idx in range(1, len(strikes)):
        prev_row = strikes[idx - 1]
        curr_row = strikes[idx]
        slope = curr_row.net_gex - prev_row.net_gex
        mid = (curr_row.strike + prev_row.strike) / 2.0
        diffs.append((mid, slope))

    up = [item for item in diffs if item[0] >= spot]
    down = [item for item in diffs if item[0] <= spot]
    cliff_up = max(up, key=lambda item: abs(item[1]))[0] if up else None
    cliff_down = max(down, key=lambda item: abs(item[1]))[0] if down else None
    return cliff_up, cliff_down


def _find_proxy_node(
    contracts: list[OptionContract],
    proxy_fn,
) -> float | None:
    if not contracts:
        return None
    best = max(contracts, key=proxy_fn)
    return best.strike


def _aggregate_by_strike(calls: list[OptionContract], puts: list[OptionContract]) -> dict[float, dict[str, float]]:
    agg: dict[float, dict[str, float]] = {}

    def ensure(strike: float) -> dict[str, float]:
        if strike not in agg:
            agg[strike] = {
                "call_vol": 0.0,
                "put_vol": 0.0,
                "call_oi": 0.0,
                "put_oi": 0.0,
                "call_dex": 0.0,
                "put_dex": 0.0,
            }
        return agg[strike]

    for c in calls:
        bucket = ensure(c.strike)
        bucket["call_vol"] += c.volume
        bucket["call_oi"] += c.open_interest
        bucket["call_dex"] += c.delta * c.open_interest * CONTRACT_MULTIPLIER

    for p in puts:
        bucket = ensure(p.strike)
        bucket["put_vol"] += p.volume
        bucket["put_oi"] += p.open_interest
        bucket["put_dex"] += p.delta * p.open_interest * CONTRACT_MULTIPLIER

    return agg


def _find_volume_imbalance_nodes(agg: dict[float, dict[str, float]]) -> tuple[float | None, float | None]:
    if not agg:
        return None, None
    rows = list(agg.items())
    call_side = max(rows, key=lambda item: item[1]["call_vol"] - item[1]["put_vol"])[0]
    put_side = max(rows, key=lambda item: item[1]["put_vol"] - item[1]["call_vol"])[0]
    return call_side, put_side


def _find_dex_nodes(agg: dict[float, dict[str, float]]) -> tuple[float | None, float | None]:
    if not agg:
        return None, None
    rows = list(agg.items())
    call_node = max(rows, key=lambda item: item[1]["call_dex"])[0]
    put_node = min(rows, key=lambda item: item[1]["put_dex"])[0]
    return call_node, put_node


def _find_liquidity_vacuum(agg: dict[float, dict[str, float]], spot: float) -> tuple[float | None, float | None]:
    if not agg:
        return None, None

    strikes = sorted(agg.keys())
    totals = {strike: agg[strike]["call_oi"] + agg[strike]["put_oi"] for strike in strikes}
    values = sorted(totals.values())
    threshold = values[max(0, int(len(values) * 0.3) - 1)] if values else 0

    lower_candidates = [strike for strike in strikes if strike <= spot and totals[strike] <= threshold]
    upper_candidates = [strike for strike in strikes if strike >= spot and totals[strike] <= threshold]

    lower = lower_candidates[-1] if lower_candidates else None
    upper = upper_candidates[0] if upper_candidates else None
    return lower, upper


def _find_skew_pivots(front_calls: list[OptionContract], front_puts: list[OptionContract]) -> tuple[float | None, float | None]:
    if not front_calls and not front_puts:
        return None, None

    call_25d = min(front_calls, key=lambda contract: abs(abs(contract.delta) - 0.25)).strike if front_calls else None
    put_25d = min(front_puts, key=lambda contract: abs(abs(contract.delta) - 0.25)).strike if front_puts else None
    return put_25d, call_25d


def _vol_trigger_bands(front_calls: list[OptionContract], spot: float) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    atm = _atm_contract(front_calls, spot)
    if atm is None or atm.iv <= 0:
        return None, None, None, None, None, None

    base = spot * atm.iv * math.sqrt(max(atm.dte, 1) / 365.0)
    half = base * 0.5
    one = base
    one_half = base * 1.5

    return (
        round(spot + half, 2), round(spot - half, 2),
        round(spot + one, 2), round(spot - one, 2),
        round(spot + one_half, 2), round(spot - one_half, 2),
    )


def calculate_dealer_levels(chain: OptionChainData, ticker: str) -> DealerLevels:
    spot = chain.spot_price
    if spot <= 0:
        raise ValueError(f"Spot price is zero for {ticker} — cannot calculate levels.")

    strikes = _build_cumulative_profile(_build_strike_gex(chain.calls, chain.puts, spot))
    total_gex = sum(row.net_gex for row in strikes)
    gex_regime = "POSITIVE" if total_gex >= 0 else "NEGATIVE"

    call_wall, secondary_call_wall = _find_walls(chain.calls, MIN_OI_THRESHOLD)
    put_wall, secondary_put_wall = _find_walls(chain.puts, MIN_OI_THRESHOLD)
    local_call_node, local_put_node = _find_local_nodes(strikes, spot)

    front_calls, front_puts = _find_front_dte_contracts(chain.calls, chain.puts)
    call_wall_0dte, _ = _find_walls(front_calls, MIN_OI_THRESHOLD)
    put_wall_0dte, _ = _find_walls(front_puts, MIN_OI_THRESHOLD)

    gamma_flip_lower, gamma_flip_upper, zero_gamma = _find_gamma_flip_zone(strikes, spot, MIN_OI_THRESHOLD)
    hedge_wall = _find_hedge_wall(strikes, spot)
    max_pain = _find_max_pain(front_calls or chain.calls, front_puts or chain.puts)

    em_value, straddle = _expected_move(chain.calls, chain.puts, spot)

    cliff_up, cliff_down = _find_gamma_cliffs(strikes, spot)

    vanna_call_node = _find_proxy_node(chain.calls, lambda c: c.open_interest * abs(c.vega * c.delta))
    vanna_put_node = _find_proxy_node(chain.puts, lambda p: p.open_interest * abs(p.vega * p.delta))
    charm_call_node = _find_proxy_node(chain.calls, lambda c: c.open_interest * abs(c.theta * c.delta))
    charm_put_node = _find_proxy_node(chain.puts, lambda p: p.open_interest * abs(p.theta * p.delta))

    agg = _aggregate_by_strike(chain.calls, chain.puts)
    vol_imb_call, vol_imb_put = _find_volume_imbalance_nodes(agg)
    dex_call_node, dex_put_node = _find_dex_nodes(agg)
    vacuum_lower, vacuum_upper = _find_liquidity_vacuum(agg, spot)

    skew_put_25d, skew_call_25d = _find_skew_pivots(front_calls, front_puts)

    vt_u05, vt_l05, vt_u10, vt_l10, vt_u15, vt_l15 = _vol_trigger_bands(front_calls or chain.calls, spot)

    call_wall = call_wall if call_wall is not None else local_call_node or spot
    put_wall = put_wall if put_wall is not None else local_put_node or spot
    local_call_node = local_call_node if local_call_node is not None else call_wall
    local_put_node = local_put_node if local_put_node is not None else put_wall
    call_wall_0dte = call_wall_0dte if call_wall_0dte is not None else call_wall
    put_wall_0dte = put_wall_0dte if put_wall_0dte is not None else put_wall
    hedge_wall = hedge_wall if hedge_wall is not None else put_wall
    max_pain = max_pain if max_pain is not None else spot

    log.info(
        "%s levels: spot=%.2f gex=%.0f regime=%s zg=%s cw=%s pw=%s mp=%s em=±%.2f",
        ticker,
        spot,
        total_gex,
        gex_regime,
        zero_gamma,
        call_wall,
        put_wall,
        max_pain,
        em_value,
    )

    return DealerLevels(
        ticker=ticker,
        spot=spot,
        total_gex=total_gex,
        gex_regime=gex_regime,
        zero_gamma=zero_gamma,
        gamma_flip_lower=gamma_flip_lower,
        gamma_flip_upper=gamma_flip_upper,
        call_wall=call_wall,
        put_wall=put_wall,
        secondary_call_wall=secondary_call_wall,
        secondary_put_wall=secondary_put_wall,
        local_call_node=local_call_node,
        local_put_node=local_put_node,
        call_wall_0dte=call_wall_0dte,
        put_wall_0dte=put_wall_0dte,
        hedge_wall=hedge_wall,
        max_pain=max_pain,
        em_upper=round(spot + em_value, 2),
        em_lower=round(spot - em_value, 2),
        em_value=round(em_value, 2),
        atm_straddle=round(straddle, 2),
        vol_trigger_upper_05=vt_u05,
        vol_trigger_lower_05=vt_l05,
        vol_trigger_upper_10=vt_u10,
        vol_trigger_lower_10=vt_l10,
        vol_trigger_upper_15=vt_u15,
        vol_trigger_lower_15=vt_l15,
        gamma_cliff_up=cliff_up,
        gamma_cliff_down=cliff_down,
        vanna_call_node=vanna_call_node,
        vanna_put_node=vanna_put_node,
        charm_call_node=charm_call_node,
        charm_put_node=charm_put_node,
        volume_imbalance_call_node=vol_imb_call,
        volume_imbalance_put_node=vol_imb_put,
        dex_call_node=dex_call_node,
        dex_put_node=dex_put_node,
        liquidity_vacuum_lower=vacuum_lower,
        liquidity_vacuum_upper=vacuum_upper,
        skew_pivot_put_25d=skew_put_25d,
        skew_pivot_call_25d=skew_call_25d,
        strike_gex=strikes,
    )


def rescale_levels_to_target_spot(levels: DealerLevels, target_ticker: str, target_spot: float) -> DealerLevels:
    if levels.spot <= 0 or target_spot <= 0:
        raise ValueError("Proxy and target spots must be positive for rescaling.")

    if abs(levels.spot - target_spot) < 1e-9 and levels.ticker == target_ticker:
        return levels

    scale = target_spot / levels.spot

    def _scale(value: float | None) -> float | None:
        if value is None:
            return None
        return round(target_spot + (value - levels.spot) * scale, 2)

    return DealerLevels(
        ticker=target_ticker,
        spot=round(target_spot, 2),
        total_gex=levels.total_gex,
        gex_regime=levels.gex_regime,
        zero_gamma=_scale(levels.zero_gamma),
        gamma_flip_lower=_scale(levels.gamma_flip_lower),
        gamma_flip_upper=_scale(levels.gamma_flip_upper),
        call_wall=_scale(levels.call_wall),
        put_wall=_scale(levels.put_wall),
        secondary_call_wall=_scale(levels.secondary_call_wall),
        secondary_put_wall=_scale(levels.secondary_put_wall),
        local_call_node=_scale(levels.local_call_node),
        local_put_node=_scale(levels.local_put_node),
        call_wall_0dte=_scale(levels.call_wall_0dte),
        put_wall_0dte=_scale(levels.put_wall_0dte),
        hedge_wall=_scale(levels.hedge_wall),
        max_pain=_scale(levels.max_pain),
        em_upper=_scale(levels.em_upper) or round(target_spot, 2),
        em_lower=_scale(levels.em_lower) or round(target_spot, 2),
        em_value=round(levels.em_value * scale, 2),
        atm_straddle=round(levels.atm_straddle * scale, 2),
        vol_trigger_upper_05=_scale(levels.vol_trigger_upper_05),
        vol_trigger_lower_05=_scale(levels.vol_trigger_lower_05),
        vol_trigger_upper_10=_scale(levels.vol_trigger_upper_10),
        vol_trigger_lower_10=_scale(levels.vol_trigger_lower_10),
        vol_trigger_upper_15=_scale(levels.vol_trigger_upper_15),
        vol_trigger_lower_15=_scale(levels.vol_trigger_lower_15),
        gamma_cliff_up=_scale(levels.gamma_cliff_up),
        gamma_cliff_down=_scale(levels.gamma_cliff_down),
        vanna_call_node=_scale(levels.vanna_call_node),
        vanna_put_node=_scale(levels.vanna_put_node),
        charm_call_node=_scale(levels.charm_call_node),
        charm_put_node=_scale(levels.charm_put_node),
        volume_imbalance_call_node=_scale(levels.volume_imbalance_call_node),
        volume_imbalance_put_node=_scale(levels.volume_imbalance_put_node),
        dex_call_node=_scale(levels.dex_call_node),
        dex_put_node=_scale(levels.dex_put_node),
        liquidity_vacuum_lower=_scale(levels.liquidity_vacuum_lower),
        liquidity_vacuum_upper=_scale(levels.liquidity_vacuum_upper),
        skew_pivot_put_25d=_scale(levels.skew_pivot_put_25d),
        skew_pivot_call_25d=_scale(levels.skew_pivot_call_25d),
        strike_gex=[],
    )
