"""
gex_calculator.py
=================
Core quantitative engine for dealer-positioning and intraday options levels.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .config import CONTRACT_MULTIPLIER, MIN_OI_THRESHOLD
from .options_fetcher import OptionChainData, OptionContract

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Higher-order Greeks (analytical BSM) — ported from ezoptionsschwab.py
# ---------------------------------------------------------------------------

def _bsm_d1d2(S: float, K: float, t: float, sigma: float,
               r: float = 0.02, q: float = 0.0) -> tuple:
    """Return (d1, d2, N'(d1)) for BSM. Returns (None,None,None) on error."""
    try:
        t = max(t, 1e-5)
        sigma = max(sigma, 1e-4)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        norm_d1 = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)  # PDF
        return d1, d2, norm_d1
    except Exception:
        return None, None, None


def _analytical_charm(flag: str, S: float, K: float, t: float, sigma: float,
                       r: float = 0.02, q: float = 0.0) -> float:
    """Charm = d(delta)/d(t) — rate of delta decay (per calendar day).
    Analytical formula from Hull's Options textbook.
    """
    try:
        from math import erfc
        d1, d2, norm_d1 = _bsm_d1d2(S, K, t, sigma, r, q)
        if d1 is None:
            return 0.0
        t = max(t, 1e-5)
        inner = (2 * (r - q) * t - d2 * sigma * math.sqrt(t)) / (2 * t * sigma * math.sqrt(t))
        if flag == 'c':
            N_d1 = 0.5 * erfc(-d1 / math.sqrt(2))
            charm = -math.exp(-q * t) * (norm_d1 * inner - q * N_d1)
        else:
            N_neg_d1 = 0.5 * erfc(d1 / math.sqrt(2))
            charm = -math.exp(-q * t) * (norm_d1 * inner + q * N_neg_d1)
        return charm
    except Exception:
        return 0.0


def _analytical_speed(S: float, K: float, t: float, sigma: float,
                       r: float = 0.02, q: float = 0.0) -> float:
    """Speed = d(gamma)/dS — third derivative of option price w.r.t. spot.
    Speed = -gamma * (d1/(sigma*sqrt(t)) + 1) / S
    """
    try:
        d1, d2, norm_d1 = _bsm_d1d2(S, K, t, sigma, r, q)
        if d1 is None:
            return 0.0
        t = max(t, 1e-5)
        gamma = math.exp(-q * t) * norm_d1 / (S * sigma * math.sqrt(t))
        speed = -gamma * (d1 / (sigma * math.sqrt(t)) + 1) / S
        return speed
    except Exception:
        return 0.0


def _volume_centroid(contracts: list) -> float | None:
    """Volume-weighted average strike price (VWAP of strikes).
    Call centroid above spot = upside activity concentration.
    Put centroid below spot = downside hedging concentration.
    """
    total_vol = sum(c.volume for c in contracts if c.volume > 0)
    if total_vol == 0:
        return None
    weighted = sum(c.strike * c.volume for c in contracts if c.volume > 0)
    return round(weighted / total_vol, 2)


def _delta_adjusted_gex(calls: list, puts: list, spot: float) -> float:
    """Delta-adjusted GEX: multiplies each contract's gamma exposure by |delta|.
    This de-emphasises deep ITM/OTM contracts and focuses on hedging near ATM.
    Returns net delta-adjusted GEX (calls positive, puts negative convention).
    """
    total = 0.0
    for c in calls:
        gex = abs(c.gamma) * c.open_interest * CONTRACT_MULTIPLIER * spot
        total += gex * abs(c.delta)
    for p in puts:
        gex = abs(p.gamma) * p.open_interest * CONTRACT_MULTIPLIER * spot
        total -= gex * abs(p.delta)
    return round(total, 2)


def _net_speed_exposure(calls: list, puts: list, spot: float) -> float:
    """Portfolio-level net speed exposure.
    Speed tells you how fast gamma (and thus dealer hedging) will change as spot moves.
    Large positive speed -> gamma ramps quickly on rallies (accelerating dealer buying).
    Large negative speed -> gamma ramps on declines (selling pressure accelerates).
    """
    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    r_rf, q_div = 0.02, 0.0
    total = 0.0
    for c in calls:
        try:
            exp_dt = datetime.combine(c.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
            iv = max(c.iv, 0.01)
            speed = _analytical_speed(spot, c.strike, t, iv, r_rf, q_div)
            total += speed * c.open_interest * CONTRACT_MULTIPLIER * spot * spot * 0.01
        except Exception:
            pass
    for p in puts:
        try:
            exp_dt = datetime.combine(p.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
            iv = max(p.iv, 0.01)
            speed = _analytical_speed(spot, p.strike, t, iv, r_rf, q_div)
            total -= speed * p.open_interest * CONTRACT_MULTIPLIER * spot * spot * 0.01
        except Exception:
            pass
    return round(total, 2)


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
    call_iv: float = 0.0
    put_iv: float = 0.0
    cumulative_gex: float = 0.0
    # ── Per-strike Greek exposures (same methodology as ezoptionsschwab.py) ──
    call_dex: float = 0.0       # Delta exposure: delta × OI × 100 × S
    put_dex: float = 0.0
    net_dex: float = 0.0       # Net Delta exposure (Call Dex + Put Dex)
    call_vex: float = 0.0       # Vanna exposure: vanna × OI × 100 × S × 0.01
    put_vex: float = 0.0
    call_charm: float = 0.0     # Charm exposure: charm × OI × 100 × S / 365
    put_charm: float = 0.0
    call_speed: float = 0.0     # Speed exposure: speed × OI × 100 × S² × 0.01
    put_speed: float = 0.0
    call_vomma: float = 0.0     # Vomma exposure: vomma × OI × 100 × 0.01
    put_vomma: float = 0.0
    call_premium: float = 0.0   # Dollar premium: mid_price × OI × 100
    put_premium: float = 0.0


@dataclass
class ExpectedMove:
    expiry: str        # YYYY-MM-DD
    dte: int
    em_value: float
    em_upper: float
    em_lower: float
    straddle: float
    straddle_85_upper: float = 0.0
    straddle_85_lower: float = 0.0




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

    # ── Tier 2: Market-structure metrics ──────────────────────────────────
    gamma_magnet: float | None          # Gamma-weighted average strike (intraday gravity)
    pin_strike: float | None            # Strike with highest combined gamma concentration
    pin_odds: float                     # 0.0–1.0, how concentrated gamma is at pin_strike
    wall_separation: float | None       # call_wall − put_wall in points (range character)
    regime_label: str                   # Human-readable: PINNED, TRENDING, COILED, BATTLE_ZONE
    directional_bias: str               # BEARISH, BULLISH, or NEUTRAL
    call_gamma_total: float             # Aggregate call-side gamma (for regime decomposition)
    put_gamma_total: float              # Aggregate put-side gamma
    net_vanna_exposure: float           # Signed net vanna: negative -> IV↓ = bearish pressure
    wall_scope: str                     # Explicit wall-construction scope descriptor
    wall_dte_min: int                   # Lower DTE bound used for wall construction
    wall_dte_max: int                   # Upper DTE bound used for wall construction
    concentration_score: float          # Bounded [0,1] concentration metric
    call_wall_oi: int = 0               # OI resting at call wall strike (all contracts)
    put_wall_oi: int = 0                # OI resting at put wall strike (all contracts)
    pin_strike_oi: int = 0              # Combined call+put OI at pin strike

    # ── Enhanced analytics (from ezoptionsschwab integration) ─────────────
    call_volume_centroid: float | None = None  # Volume-weighted avg call strike (VWAP-of-strikes)
    put_volume_centroid: float | None = None   # Volume-weighted avg put strike
    total_gex_delta_adj: float = 0.0           # Delta-adjusted GEX: |delta|-weighted gamma exposure
    net_speed_exposure: float = 0.0            # Backward-compat only (deprecated for briefing)
    hedge_flow_up_10: float = 0.0
    hedge_flow_up_25: float = 0.0
    hedge_flow_up_50: float = 0.0
    hedge_flow_dn_10: float = 0.0
    hedge_flow_dn_25: float = 0.0
    hedge_flow_dn_50: float = 0.0
    hourly_flow_curve: list[dict[str, float | str]] = field(default_factory=list)
    max_gex_strike: float | None = None # Strike with the absolute maximum net GEX
    atm_iv: float | None = None         # ATM implied volatility (decimal, e.g. 0.20 = 20%)
    iv_change: float = 0.0             # Daily change in IV (delta from previous run)

    expected_moves: list[ExpectedMove] = field(default_factory=list)
    strike_gex: list[StrikeGEX] = field(default_factory=list)

    # ── Institutional Skew Metrics (passed through) ───────────────────────
    put_25d_iv: float | None = None
    call_25d_iv: float | None = None
    volatility_skew_premium: float | None = None
    zero_gamma_delta_adj: float | None = None


def _best_contract_per_strike(contracts: list[OptionContract]) -> dict[float, OptionContract]:
    """
    Keep the highest-OI contract at each strike.

    When contracts span multiple DTEs (e.g. 0DTE + 1DTE), a 1DTE contract can
    replace a 0DTE at the same strike if it has more OI.  This is logged at
    DEBUG so you can audit whether the blended profile is skewed.
    """
    best: dict[float, OptionContract] = {}
    for contract in contracts:
        existing = best.get(contract.strike)
        if existing is None:
            best[contract.strike] = contract
        elif contract.open_interest > existing.open_interest:
            if contract.dte != existing.dte:
                log.debug(
                    "Strike %.1f: %dDTE (OI=%d) replaces %dDTE (OI=%d) in blended profile.",
                    contract.strike,
                    contract.dte,
                    contract.open_interest,
                    existing.dte,
                    existing.open_interest,
                )
            best[contract.strike] = contract
    return best


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _normal_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _build_strike_gex(calls: list[OptionContract], puts: list[OptionContract], spot: float) -> list[StrikeGEX]:
    from .config import WEIGHT_MODE

    def _weight(c: OptionContract) -> float:
        """Return the effective position weight for a contract based on WEIGHT_MODE."""
        oi, vol = c.open_interest, max(c.volume, 0)
        if WEIGHT_MODE == "VOLUME":
            return vol if vol > 0 else oi   # fall back to OI if no volume yet
        if WEIGHT_MODE == "OI_VOL_SUM":
            return oi + vol
        if WEIGHT_MODE == "OI_VOL_MAX":
            return max(oi, vol)
        return oi  # default: "OI"

    def _calc_per_strike_exposures(c: OptionContract, flag: str, spot: float, weight: int) -> dict:
        """Compute all per-strike Greek exposures using the same methodology as ezoptionsschwab.py.
        Exposures are in notional (dollar) terms: Greek × weight × 100 × scale_factor.
        """
        tz_et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz_et)
        contract_size = 100
        r, q = 0.02, 0.0
        try:
            exp_dt = datetime.combine(c.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
        except Exception:
            t = 1e-5
        iv = max(c.iv, 1e-4)
        K = c.strike

        d1, d2, norm_d1_val = _bsm_d1d2(spot, K, t, iv, r, q)
        if d1 is None:
            return {"dex": 0.0, "vex": 0.0, "charm": 0.0, "speed": 0.0, "vomma": 0.0, "premium": 0.0}

        # Delta (BSM)
        try:
            import math
            from math import erfc
            if flag == 'c':
                delta = math.exp(-q * t) * 0.5 * erfc(-d1 / math.sqrt(2))
            else:
                delta = math.exp(-q * t) * (0.5 * erfc(-d1 / math.sqrt(2)) - 1)
        except Exception:
            delta = 0.0

        # Vanna: -exp(-q*t) * N'(d1) * d2 / sigma
        try:
            vanna = -math.exp(-q * t) * norm_d1_val * d2 / iv
        except Exception:
            vanna = 0.0

        # Vomma: vega * d1 * d2 / sigma
        try:
            vega = spot * math.exp(-q * t) * norm_d1_val * math.sqrt(t)
            vomma = vega * (d1 * d2) / iv
        except Exception:
            vomma = 0.0

        # Charm
        charm = _analytical_charm(flag, spot, K, t, iv, r, q)

        # Speed: d(gamma)/dS
        speed = _analytical_speed(spot, K, t, iv, r, q)

        # ── Institutional Exposure Formulas (from ezoptionsschwab.py) ────────
        # All exposures are in Notional ($) terms per $1 move in underlying.
        # spot_multiplier = spot (since we calculate in notional)
        
        # DEX: Delta Exposure = Delta * Weight * 100 * Spot
        dex = delta * weight * contract_size * spot
        
        # VEX: Vanna Exposure = Vanna * Weight * 100 * Spot * 0.01
        vex = vanna * weight * contract_size * spot * 0.01
        
        # Charm Exposure = Charm * Weight * 100 * Spot / 365
        charm_exp = charm * weight * contract_size * spot / 365.0
        
        # Speed Exposure = Speed * Weight * 100 * Spot * Spot * 0.01
        # (This captures the rate of change of GEX)
        speed_exp = speed * weight * contract_size * spot * spot * 0.01
        
        # Vomma Exposure = Vomma * Weight * 100 * 0.01
        vomma_exp = vomma * weight * contract_size * 0.01
        
        # Premium = Mid * Weight * 100
        premium = c.mark * weight * contract_size

        return {
            "dex": round(dex, 2),
            "vex": round(vex, 2),
            "charm": round(charm_exp, 2),
            "speed": round(speed_exp, 2),
            "vomma": round(vomma_exp, 2),
            "premium": round(premium, 2)
        }

    call_map = _best_contract_per_strike(calls)
    put_map = _best_contract_per_strike(puts)
    all_strikes = sorted(set(call_map) | set(put_map))

    rows: list[StrikeGEX] = []
    for strike in all_strikes:
        call = call_map.get(strike)
        put = put_map.get(strike)
        call_wt = _weight(call) if call else 0
        put_wt = _weight(put) if put else 0
        
        # GEX calculation (standard Gamma * OI * 100 * Spot)
        call_gex = abs(call.gamma) * call_wt * CONTRACT_MULTIPLIER * spot if call else 0.0
        put_gex  = abs(put.gamma)  * put_wt  * CONTRACT_MULTIPLIER * spot if put  else 0.0

        c_exp = _calc_per_strike_exposures(call, 'c', spot, call_wt) if call else {"dex": 0.0, "vex": 0.0, "charm": 0.0, "speed": 0.0, "vomma": 0.0, "premium": 0.0}
        p_exp = _calc_per_strike_exposures(put,  'p', spot, put_wt)  if put  else {"dex": 0.0, "vex": 0.0, "charm": 0.0, "speed": 0.0, "vomma": 0.0, "premium": 0.0}

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
                call_iv=call.iv if call else 0.0,
                put_iv=put.iv if put else 0.0,
                # Per-strike exposures
                call_dex=c_exp["dex"],
                put_dex=p_exp["dex"],
                net_dex=c_exp["dex"] + p_exp["dex"], # Net Delta exposure
                call_vex=c_exp["vex"],
                put_vex=p_exp["vex"],
                call_charm=c_exp["charm"],
                put_charm=p_exp["charm"],
                call_speed=c_exp["speed"],
                put_speed=p_exp["speed"],
                call_vomma=c_exp["vomma"],
                put_vomma=p_exp["vomma"],
                call_premium=c_exp["premium"],
                put_premium=p_exp["premium"],
            )
        )
    return rows



def _build_cumulative_profile(strike_gex: list[StrikeGEX]) -> list[StrikeGEX]:
    running = 0.0
    for row in strike_gex:
        running += row.net_gex
        row.cumulative_gex = running
    return strike_gex


def _find_walls(
    contracts: list[OptionContract],
    min_oi: int,
    spot: float = 0.0,
    side: str = "",
) -> tuple[float | None, float | None]:
    """
    Find the primary and secondary wall strikes for a set of contracts.

    Parameters
    ----------
    contracts : Call or put contracts to search.
    min_oi    : Minimum open interest threshold.
    spot      : Current spot price (used for side filtering).
    side      : ``"CALL"`` to restrict to strikes ≥ spot (resistance),
                ``"PUT"`` to restrict to strikes ≤ spot (support).
                Empty string disables side filtering (backward compat).

    Returns
    -------
    tuple[primary_strike, secondary_strike]
    """
    candidates = [c for c in contracts if c.open_interest >= min_oi]
    if not candidates:
        return None, None

    # Filter to the correct side of spot when requested.
    if side and spot > 0:
        if side == "CALL":
            sided = [c for c in candidates if c.strike >= spot]
        elif side == "PUT":
            sided = [c for c in candidates if c.strike <= spot]
        else:
            sided = candidates

        if sided:
            candidates = sided
        else:
            # No qualifying strikes on the correct side — keep all candidates
            # but log so we know this happened.
            log.debug(
                "No %s-side candidates above min_oi=%d at spot=%.2f; "
                "using best strike from either side.",
                side, min_oi, spot,
            )

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


def _calculate_hypothetical_total_gex(calls: list[OptionContract], puts: list[OptionContract], S_hypo: float, delta_adjusted: bool = False) -> float:
    from zoneinfo import ZoneInfo
    from datetime import datetime, time
    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    contract_size = 100
    r, q = 0.02, 0.0
    
    total = 0.0
    
    # Process calls
    for c in calls:
        try:
            exp_dt = datetime.combine(c.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
        except Exception:
            t = 1e-5
        iv = max(c.iv, 1e-4)
        K = c.strike
        d1, d2, norm_d1 = _bsm_d1d2(S_hypo, K, t, iv, r, q)
        if d1 is not None and norm_d1 is not None:
            gamma = math.exp(-q * t) * norm_d1 / (S_hypo * iv * math.sqrt(t))
            gex = gamma * c.open_interest * contract_size * S_hypo
            if delta_adjusted:
                delta = 0.5 * math.erfc(-d1 / math.sqrt(2))
                total += gex * abs(delta)
            else:
                total += gex

    # Process puts
    for p in puts:
        try:
            exp_dt = datetime.combine(p.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
        except Exception:
            t = 1e-5
        iv = max(p.iv, 1e-4)
        K = p.strike
        d1, d2, norm_d1 = _bsm_d1d2(S_hypo, K, t, iv, r, q)
        if d1 is not None and norm_d1 is not None:
            gamma = math.exp(-q * t) * norm_d1 / (S_hypo * iv * math.sqrt(t))
            gex = gamma * p.open_interest * contract_size * S_hypo
            if delta_adjusted:
                delta = 0.5 * math.erfc(-d1 / math.sqrt(2)) - 1.0
                total -= gex * abs(delta)
            else:
                total -= gex
                
    return total


def _find_dynamic_zero_gamma(calls: list[OptionContract], puts: list[OptionContract], spot: float, delta_adjusted: bool = False) -> float | None:
    """Find the zero-gamma level nearest to spot using a cascaded bounded binary search.

    Problem with the old [0.5x, 1.5x] approach: when a full option chain (including
    LEAPS) is passed, the GEX profile can have *multiple* sign crossings. The binary
    search would arbitrarily converge to whichever crossing happened to straddle the
    midpoint of the search range — often a spurious far-OTM LEAPS crossing (~1.25x
    spot) instead of the economically relevant near-ATM crossing (~1.01x spot).

    Fix: search three progressively wider bands centered on spot, collecting all
    candidate crossings, then return the one nearest to spot.
    """
    if not calls and not puts:
        return None

    def _bisect(lo: float, hi: float) -> float | None:
        g_lo = _calculate_hypothetical_total_gex(calls, puts, lo, delta_adjusted)
        g_hi = _calculate_hypothetical_total_gex(calls, puts, hi, delta_adjusted)
        if g_lo * g_hi > 0:
            return None
        for _ in range(50):
            mid = (lo + hi) / 2.0
            g_mid = _calculate_hypothetical_total_gex(calls, puts, mid, delta_adjusted)
            if abs(g_mid) < 1e-2:
                return round(mid, 2)
            if g_mid < 0:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2.0, 2)

    # Search three bands, picking the crossing nearest to spot.
    # Tighter bands first so we find near-ATM crossings before LEAPS crossings.
    candidates: list[float] = []
    for lo_scale, hi_scale in [(0.90, 1.10), (0.80, 1.20), (0.50, 1.50)]:
        result = _bisect(spot * lo_scale, spot * hi_scale)
        if result is not None:
            candidates.append(result)

    if not candidates:
        return None

    return min(candidates, key=lambda x: abs(x - spot))


def _find_gamma_flip_zone(strikes: list[StrikeGEX], spot: float, min_oi: int) -> tuple[float | None, float | None, float | None]:
    """
    Find the strike where cumulative GEX crosses zero (Gamma Flip).
    Also returns the nearest significant significant strikes above and below.
    """
    if not strikes:
        return None, None, None

    def significant(row: StrikeGEX) -> bool:
        return (row.call_oi + row.put_oi) >= min_oi

    # Collect ALL cumulative-GEX zero-crossings
    crossings: list[int] = []
    for idx in range(1, len(strikes)):
        prev_gex = strikes[idx - 1].cumulative_gex
        curr_gex = strikes[idx].cumulative_gex
        
        # Detect exact hits on zero
        if prev_gex == 0:
            crossings.append(idx - 1)
            continue
            
        # Detect sign changes
        if (prev_gex < 0 and curr_gex > 0) or (prev_gex > 0 and curr_gex < 0):
            crossings.append(idx)

    # ── Zero Gamma Interpolation ──
    # Instead of just picking a strike, we interpolate where it exactly crosses 0
    zero_gamma: float | None = None
    crossing_idx: int | None = None
    
    if crossings:
        # Structural crossing selection by tape regime:
        # long-gamma tape -> nearest crossing below spot,
        # short-gamma tape -> nearest crossing above spot.
        tape_is_long_gamma = strikes[-1].cumulative_gex >= 0
        below = [i for i in crossings if strikes[i].strike <= spot]
        above = [i for i in crossings if strikes[i].strike >= spot]
        if tape_is_long_gamma and below:
            crossing_idx = max(below, key=lambda i: strikes[i].strike)
        elif (not tape_is_long_gamma) and above:
            crossing_idx = min(above, key=lambda i: strikes[i].strike)
        else:
            crossing_idx = min(crossings, key=lambda i: abs(strikes[i].strike - spot))
        
        # Interpolate between crossing_idx-1 and crossing_idx
        idx = crossing_idx
        if idx > 0:
            s1, g1 = strikes[idx-1].strike, strikes[idx-1].cumulative_gex
            s2, g2 = strikes[idx].strike, strikes[idx].cumulative_gex
            if abs(g2 - g1) > 1e-9:
                zero_gamma = s1 - g1 * (s2 - s1) / (g2 - g1)
            else:
                zero_gamma = strikes[idx].strike
        else:
            zero_gamma = strikes[idx].strike
    else:
        # Edge case: No crossing found. Try to find the minimum absolute cumulative GEX.
        closest_row = min(strikes, key=lambda row: abs(row.cumulative_gex))
        zero_gamma = closest_row.strike

    # ── Flip Brackets ──
    if crossing_idx is not None:
        lower = next((strikes[i].strike for i in range(crossing_idx - 1, -1, -1) if significant(strikes[i])), None)
        upper = next((strikes[i].strike for i in range(crossing_idx, len(strikes)) if significant(strikes[i])), None)
    else:
        # Bracket spot with nearest significant strikes.
        below = [row for row in strikes if row.strike <= spot and significant(row)]
        above = [row for row in strikes if row.strike >= spot and significant(row)]
        lower = below[-1].strike if below else None
        upper = above[0].strike if above else None

    if lower is None and upper is None:
        return zero_gamma, None, None
        
    lower = lower if lower is not None else upper
    upper = upper if upper is not None else lower
    
    return float(lower), float(upper), round(zero_gamma, 2) if zero_gamma else None


def _find_hedge_wall(strikes: list[StrikeGEX], spot: float) -> float | None:
    downside = [row for row in strikes if row.strike < spot and row.put_oi > 0]
    if not downside:
        return None
    return min(downside, key=lambda row: row.net_gex).strike


def _net_delta_notional(
    calls: list[OptionContract],
    puts: list[OptionContract],
    eval_spot: float,
) -> float:
    """Approximate net dealer-delta notional at a given spot using BSM deltas."""
    if eval_spot <= 0:
        return 0.0

    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    total = 0.0

    for c in calls:
        try:
            exp_dt = datetime.combine(c.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
            iv = max(c.iv, 0.01)
            d1, _, _ = _bsm_d1d2(eval_spot, c.strike, t, iv)
            if d1 is None:
                continue
            delta = _normal_cdf(d1)
            total += delta * c.open_interest * CONTRACT_MULTIPLIER * eval_spot
        except Exception:
            continue

    for p in puts:
        try:
            exp_dt = datetime.combine(p.expiry, time(16, 0), tzinfo=tz_et)
            t = max((exp_dt - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)
            iv = max(p.iv, 0.01)
            d1, _, _ = _bsm_d1d2(eval_spot, p.strike, t, iv)
            if d1 is None:
                continue
            delta = _normal_cdf(d1) - 1.0
            total += delta * p.open_interest * CONTRACT_MULTIPLIER * eval_spot
        except Exception:
            continue

    return round(total, 2)


def _expected_hedge_flow_scenarios(
    calls: list[OptionContract],
    puts: list[OptionContract],
    spot: float,
) -> dict[str, float]:
    """
    Compute dealer hedge-flow deltas for +/-10, +/-25, +/-50 point scenarios.

    Positive value => dealers must buy notional; negative => dealers must sell.
    """
    base = _net_delta_notional(calls, puts, spot)

    def _flow(shift: float) -> float:
        shifted = _net_delta_notional(calls, puts, spot + shift)
        return round(shifted - base, 2)

    return {
        "up_10": _flow(10.0),
        "up_25": _flow(25.0),
        "up_50": _flow(50.0),
        "dn_10": _flow(-10.0),
        "dn_25": _flow(-25.0),
        "dn_50": _flow(-50.0),
    }


def _hourly_charm_vanna_curve(
    vanna_exposure: float,
    charm_call_node: float | None,
    charm_put_node: float | None,
) -> list[dict[str, float | str]]:
    """Project a simple hourly pressure curve from current ET hour to close."""
    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    start_hour = max(now_et.hour, 10)
    end_hour = 16

    if start_hour >= end_hour:
        return []

    charm_net = (charm_call_node - charm_put_node) if (charm_call_node is not None and charm_put_node is not None) else 0.0
    vanna_m = vanna_exposure / 1_000_000.0
    charm_m = charm_net / 1_000_000.0
    rows: list[dict[str, float | str]] = []

    for hour in range(start_hour, end_hour):
        # Weight rises into the close to reflect charm acceleration.
        progress = (hour - start_hour + 1) / max(1, (end_hour - start_hour))
        accel = 0.65 + 0.85 * progress
        flow_m = round((0.25 * vanna_m + 0.75 * charm_m) * accel, 2)
        rows.append({"window": f"{hour:02d}-{hour + 1:02d} ET", "flow_m": flow_m})

    return rows


def _filter_contracts_by_dte(contracts: list[OptionContract], dte_range: tuple[int, int]) -> list[OptionContract]:
    min_dte, max_dte = dte_range
    return [contract for contract in contracts if min_dte <= contract.dte <= max_dte]


def _oi_at_strike(contracts: list[OptionContract], strike: float | None) -> int:
    if strike is None:
        return 0
    target = float(strike)
    return int(sum(c.open_interest for c in contracts if abs(c.strike - target) < 1e-9))


def _atm_contract(calls: list[OptionContract], spot: float) -> OptionContract | None:
    if not calls:
        return None
    return min(calls, key=lambda contract: abs(contract.strike - spot))


def _atm_straddle_cost(calls: list[OptionContract], puts: list[OptionContract], spot: float) -> float:
    if not calls or not puts:
        return 0.0
    atm_call = min(calls, key=lambda contract: abs(contract.strike - spot))
    atm_put = min(puts, key=lambda contract: abs(contract.strike - spot))
    # Use mark (mid-price) rather than ask to avoid inflating EM by the full
    # bid-ask spread.  mark is already computed as (bid+ask)/2 by the fetcher.
    return atm_call.mark + atm_put.mark

def _log_em_calibration_record(
    ticker: str,
    expiry: Any,
    dte: int,
    spot: float,
    atm_strike: float,
    c_mid: float,
    p_mid: float,
    straddle: float,
    em_val: float
) -> None:
    try:
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import json
        
        # Clean ticker name
        clean_ticker = ticker.upper().replace("/", "").replace("$", "")
        tracked_tickers = {"SPX", "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"}
        if clean_ticker not in tracked_tickers:
            return
            
        from scripts.streaming.options.config import REPO_ROOT
        log_dir = os.path.join(REPO_ROOT, "data", "derived")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "em_calibration_log.jsonl")
        
        record = {
            "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "ticker": ticker,
            "expiry": expiry.isoformat() if isinstance(expiry, (date, datetime)) else str(expiry),
            "DTE": dte,
            "spot": spot,
            "atm_strike": atm_strike,
            "atm_call_mid": c_mid,
            "atm_put_mid": p_mid,
            "straddle": straddle,
            "computed_em": em_val,
            "tos_displayed_em": None
        }
        
        with open(log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

def _expected_move(
    calls: list[OptionContract], 
    puts: list[OptionContract], 
    spot: float,
    dte: int = 0,
    is_futures: bool = False,
    ticker: str = "",
    *args, **kwargs
) -> tuple[float, float]:
    import inspect
    if isinstance(dte, float) and dte < 1.0:
        frame = inspect.currentframe().f_back
        caller_name = frame.f_code.co_name if frame else "unknown"
        caller_file = frame.f_code.co_filename if frame else "unknown"
        caller_line = frame.f_lineno if frame else 0
        log.warning(
            "LOUD WARNING: _expected_move received invalid dte argument: %s (float < 1.0). "
            "Call origin: %s in %s:%d",
            dte, caller_name, caller_file, caller_line
        )

    # 1. Grab config multiplier
    from scripts.streaming.options.config import (
        EM_STRADDLE_MULTIPLE_DEFAULT,
        EM_STRADDLE_MULTIPLE_OVERRIDES
    )
    clean_ticker = ticker.lstrip("$").upper() if ticker else ""
    k = EM_STRADDLE_MULTIPLE_OVERRIDES.get(clean_ticker, EM_STRADDLE_MULTIPLE_DEFAULT)
    if not (0.9 <= k <= 1.3):
        log.warning("LOUD WARNING: Resolved expected move multiple k=%.4f is outside the sane band [0.9, 1.3].", k)

    # 2. Extract ATM strike closest to spot
    if not calls or not puts:
        log.warning("LOUD WARNING: Missing options contracts for expected move calculation.")
        return 0.0, 0.0
        
    strikes = sorted(list(set([c.strike for c in calls] + [p.strike for p in puts])))
    if not strikes:
        log.warning("LOUD WARNING: No strikes found for expected move calculation.")
        return 0.0, 0.0
        
    atm_strike = min(strikes, key=lambda s: abs(s - spot))
    
    c = next((x for x in calls if x.strike == atm_strike), None)
    p = next((x for x in puts if x.strike == atm_strike), None)
    
    if not c or not p:
        log.warning("LOUD WARNING: Missing ATM contract for expected move calculation at strike %.2f.", atm_strike)
        return 0.0, 0.0
        
    # 3. Guardrail: crossed or missing market check
    if c.bid <= 0 or c.ask <= 0 or p.bid <= 0 or p.ask <= 0:
        log.warning(
            "LOUD WARNING: Crossed or missing bid/ask for expected move at strike %.2f. "
            "Call bid/ask: %.2f/%.2f, Put bid/ask: %.2f/%.2f",
            atm_strike, c.bid, c.ask, p.bid, p.ask
        )
        return 0.0, 0.0
        
    if c.bid >= c.ask or p.bid >= p.ask:
        log.warning(
            "LOUD WARNING: Crossed bid/ask for expected move at strike %.2f. "
            "Call: %.2f >= %.2f, Put: %.2f >= %.2f",
            atm_strike, c.bid, c.ask, p.bid, p.ask
        )
        return 0.0, 0.0
        
    # 4. Compute straddle mid
    c_mid = (c.bid + c.ask) / 2.0
    p_mid = (p.bid + p.ask) / 2.0
    straddle_mid = c_mid + p_mid
    
    # 5. Compute Expected Move
    em_value = k * straddle_mid
    
    # 6. Capture log
    expiry = c.expiry
    _log_em_calibration_record(ticker, expiry, dte, spot, atm_strike, c_mid, p_mid, straddle_mid, em_value)
    
    return em_value, straddle_mid

def _calculate_all_ems(chain: OptionChainData) -> list[ExpectedMove]:
    """Calculate the Expected Move for every unique expiry in the chain."""
    by_expiry: dict[datetime.date, tuple[list[OptionContract], list[OptionContract]]] = {}
    
    for c in chain.calls:
        by_expiry.setdefault(c.expiry, ([], []))[0].append(c)
    for p in chain.puts:
        by_expiry.setdefault(p.expiry, ([], []))[1].append(p)
        
    spot = chain.spot_price
    ems = []
    
    tz = ZoneInfo("America/New_York")
    now_ny = datetime.now(tz)

    # ── DEBUG: log every expiry the chain has so we can diagnose coverage ──
    all_expiries = sorted(by_expiry.keys())
    log.info(
        "[EM-DEBUG] %s | spot=%.2f | %d unique expiries in chain: %s",
        chain.ticker,
        spot,
        len(all_expiries),
        ", ".join(str(e) for e in all_expiries),
    )
    
    for expiry, (calls, puts) in sorted(by_expiry.items()):
        dte = (expiry - now_ny.date()).days

        if not calls or not puts:
            log.info(
                "[EM-DEBUG] %s | %s (DTE=%d) — SKIP: calls=%d puts=%d",
                chain.ticker, expiry, dte, len(calls), len(puts),
            )
            continue

        # Get ATM call/put for diagnostics before calling _expected_move
        atm_call = min(calls, key=lambda c: abs(c.strike - spot)) if calls else None
        atm_put  = min(puts,  key=lambda p: abs(p.strike - spot)) if puts  else None
        atm_call_iv = atm_call.iv if atm_call else 0.0
        atm_put_iv  = atm_put.iv  if atm_put  else 0.0
        blended_iv  = (atm_call_iv + atm_put_iv) / 2.0 if (atm_call_iv > 0 and atm_put_iv > 0) else 0.0

        is_futures = any(chain.ticker.startswith(f) for f in ["/ES", "/NQ", "/CL", "/GC", "ES", "NQ"])
        move, straddle = _expected_move(calls, puts, spot, dte=dte, is_futures=is_futures, ticker=chain.ticker)

        if move <= 0:
            log.info(
                "[EM-DEBUG] %s | %s (DTE=%d) — SKIP: move=0 | ATM call_iv=%.4f put_iv=%.4f blended=%.4f straddle=%.2f",
                chain.ticker, expiry, dte,
                atm_call_iv, atm_put_iv, blended_iv, straddle,
            )
            continue

        log.info(
            "[EM-DEBUG] %s | %s (DTE=%d) — OK: ±%.2f | ATM blended_iv=%.4f (%.2f%%) straddle=%.2f",
            chain.ticker, expiry, dte,
            move, blended_iv, blended_iv * 100, straddle,
        )
            
        ems.append(ExpectedMove(
            expiry=expiry.isoformat(),
            dte=max(0, dte),
            em_value=round(move, 2),
            em_upper=round(spot + move, 2),
            em_lower=round(spot - move, 2),
            straddle=round(straddle, 2),
            straddle_85_upper=round(spot + straddle * 0.85, 2),
            straddle_85_lower=round(spot - straddle * 0.85, 2)
        ))

    log.info(
        "[EM-DEBUG] %s | %d EMs emitted: %s",
        chain.ticker,
        len(ems),
        ", ".join(f"{e.expiry}(±{e.em_value})" for e in ems),
    )
    return ems



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
    """
    Gamma cliff up  = strike zone ABOVE spot where net GEX increases most
                      steeply (positive slope -> resistance building).
    Gamma cliff down = strike zone BELOW spot where net GEX decreases most
                       steeply (negative slope -> support eroding).
    """
    if len(strikes) < 2:
        return None, None

    diffs: list[tuple[float, float]] = []
    for idx in range(1, len(strikes)):
        prev_row = strikes[idx - 1]
        curr_row = strikes[idx]
        slope = curr_row.net_gex - prev_row.net_gex
        mid = (curr_row.strike + prev_row.strike) / 2.0
        diffs.append((mid, slope))

    up = [item for item in diffs if item[0] >= spot]
    down = [item for item in diffs if item[0] <= spot]

    # Cliff up: steepest positive GEX slope above spot (wall building).
    # Fall back to largest absolute slope if no positive slopes exist.
    cliff_up = None
    if up:
        positive_up = [item for item in up if item[1] > 0]
        if positive_up:
            cliff_up = max(positive_up, key=lambda item: item[1])[0]
        else:
            cliff_up = max(up, key=lambda item: abs(item[1]))[0]

    # Cliff down: steepest negative GEX slope below spot (support eroding).
    # Fall back to largest absolute slope if no negative slopes exist.
    cliff_down = None
    if down:
        negative_down = [item for item in down if item[1] < 0]
        if negative_down:
            cliff_down = min(negative_down, key=lambda item: item[1])[0]
        else:
            cliff_down = max(down, key=lambda item: abs(item[1]))[0]

    return cliff_up, cliff_down


def _find_proxy_node(
    contracts: list[OptionContract],
    proxy_fn,
    spot: float | None = None,
    proximity: float = 0.10,
) -> float | None:
    """
    Find the strike with the highest proxy score.

    When *spot* is provided, restrict the search to contracts within
    ±*proximity* (default 10%) of spot first.  Falls back to the full
    chain only if no local contracts exist.
    """
    if not contracts:
        return None

    pool = contracts
    if spot is not None and spot > 0:
        lo = spot * (1.0 - proximity)
        hi = spot * (1.0 + proximity)
        local = [c for c in contracts if lo <= c.strike <= hi]
        if local:
            pool = local

    best = max(pool, key=proxy_fn)
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
    # Call DEX is positive (positive delta × OI); find the strike with the largest.
    call_node = max(rows, key=lambda item: item[1]["call_dex"])[0]
    # Put DEX is negative (negative delta × OI); find the largest absolute value.
    put_node = max(rows, key=lambda item: abs(item[1]["put_dex"]))[0]
    return call_node, put_node


def _find_liquidity_vacuum(agg: dict[float, dict[str, float]], spot: float) -> tuple[float | None, float | None]:
    if not agg:
        return None, None

    strikes = sorted(agg.keys())
    totals = {strike: agg[strike]["call_oi"] + agg[strike]["put_oi"] for strike in strikes}
    values = sorted(totals.values())

    # 30th percentile: need at least a few strikes for the concept to be meaningful.
    if len(values) < 5:
        return None, None
    pct_idx = int(math.ceil(len(values) * 0.3)) - 1   # 0-indexed, ceil ensures ≥0
    threshold = values[max(0, pct_idx)]

    lower_candidates = [strike for strike in strikes if strike < spot and totals[strike] <= threshold]
    upper_candidates = [strike for strike in strikes if strike > spot and totals[strike] <= threshold]

    lower = lower_candidates[-1] if lower_candidates else None
    upper = upper_candidates[0] if upper_candidates else None
    return lower, upper


def _find_skew_pivots(front_calls: list[OptionContract], front_puts: list[OptionContract]) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """
    Finds the 25-Delta strikes and extracts their Implied Volatility (IV)
    to calculate the Volatility Skew Premium (Put IV - Call IV).
    Returns: (put_strike, call_strike, put_iv, call_iv, skew_premium)
    """
    if not front_calls and not front_puts:
        return None, None, None, None, None

    call_25d = min(front_calls, key=lambda contract: abs(abs(contract.delta) - 0.25)) if front_calls else None
    put_25d = min(front_puts, key=lambda contract: abs(abs(contract.delta) - 0.25)) if front_puts else None
    
    call_strike = call_25d.strike if call_25d else None
    call_iv = call_25d.iv if call_25d else None
    
    put_strike = put_25d.strike if put_25d else None
    put_iv = put_25d.iv if put_25d else None
    
    skew_premium = None
    if put_iv is not None and call_iv is not None:
        # Positive = Puts are more expensive (Fear). Negative = Calls are more expensive (Greed).
        skew_premium = round(put_iv - call_iv, 4)

    return put_strike, call_strike, put_iv, call_iv, skew_premium


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


def calculate_price_metrics(chain: OptionChainData) -> dict[str, float | None]:
    spot = chain.spot_price
    if spot <= 0:
        raise ValueError("Spot price is zero — cannot calculate price-derived metrics.")

    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    front_expiry = min(c.expiry for c in chain.contracts) if chain.contracts else None
    front_dte = max(0, (front_expiry - now_et.date()).days) if front_expiry else 0

    is_futures = any(chain.ticker.startswith(f) for f in ["/ES", "/NQ", "/CL", "/GC", "ES", "NQ"])
    em_value, straddle = _expected_move(chain.calls, chain.puts, spot, front_dte, is_futures=is_futures, ticker=chain.ticker)
    front_calls, front_puts = _find_front_dte_contracts(chain.calls, chain.puts)
    skew_put_25d, skew_call_25d, _, _, _ = _find_skew_pivots(front_calls, front_puts)
    vt_u05, vt_l05, vt_u10, vt_l10, vt_u15, vt_l15 = _vol_trigger_bands(front_calls or chain.calls, spot)

    return {
        "em_upper": round(spot + em_value, 2),
        "em_lower": round(spot - em_value, 2),
        "em_value": round(em_value, 2),
        "atm_straddle": round(straddle, 2),
        "vol_trigger_upper_05": vt_u05,
        "vol_trigger_lower_05": vt_l05,
        "vol_trigger_upper_10": vt_u10,
        "vol_trigger_lower_10": vt_l10,
        "vol_trigger_upper_15": vt_u15,
        "vol_trigger_lower_15": vt_l15,
        "skew_pivot_put_25d": skew_put_25d,
        "skew_pivot_call_25d": skew_call_25d,
    }


# ---------------------------------------------------------------------------
# Tier 2: Market-structure metrics
# ---------------------------------------------------------------------------

def _gamma_magnet(strikes: list[StrikeGEX]) -> float | None:
    """
    Gamma-weighted average strike — the price where net hedging pull
    cancels out.  Conceptually the intraday "center of gravity."

    Uses absolute net GEX as the weight so that both positive- and
    negative-GEX strikes contribute pull proportional to their magnitude.
    """
    if not strikes:
        return None
    total_weight = sum(abs(row.net_gex) for row in strikes)
    if total_weight == 0:
        return None
    weighted = sum(row.strike * abs(row.net_gex) for row in strikes)
    return round(weighted / total_weight, 2)


def _pin_strike_and_odds(strikes: list[StrikeGEX]) -> tuple[float | None, float]:
    """
    Pin strike = strike with the highest combined gamma concentration.
    Pin odds  = what fraction of total gamma sits at the pin strike.

    High pin odds (> 0.25) -> strong pinning effect, expect convergence.
    Low pin odds  (< 0.10) -> gamma is diffuse, pinning is weak.
    """
    if not strikes:
        return None, 0.0
    total_gamma = sum(row.call_gex + row.put_gex for row in strikes)
    if total_gamma == 0:
        return None, 0.0
    pin = max(strikes, key=lambda row: row.call_gex + row.put_gex)
    pin_gamma = pin.call_gex + pin.put_gex
    odds = round(pin_gamma / total_gamma, 4)
    return pin.strike, odds


def _wall_separation(
    call_wall: float | None,
    put_wall: float | None,
) -> float | None:
    """Distance in points between call wall and put wall."""
    if call_wall is None or put_wall is None:
        return None
    return round(abs(call_wall - put_wall), 2)


def _classify_regime(
    total_gex: float,
    separation: float | None,
    em_value: float,
    spot: float,
    gamma_magnet: float | None,
    put_gamma_total: float,
    call_gamma_total: float,
    net_vanna: float,
    skew_premium: float | None = None,
    total_gex_delta_adj: float | None = None,
) -> tuple[str, str]:
    """
    Combine GEX sign/magnitude, wall separation, and directional signals
    into a regime label + directional bias.

    Returns
    -------
    tuple[str, str]
        (regime_label, directional_bias)
        regime_label: PINNED, TRENDING, COILED, BATTLE_ZONE, NEUTRAL
        directional_bias: "BEARISH", "BULLISH", or "NEUTRAL"
    """
    if separation is None or em_value <= 0:
        return "NEUTRAL", "NEUTRAL"

    positive_gex = total_gex >= 0
    tight = separation < em_value

    if positive_gex and tight:
        regime = "PINNED"
    elif positive_gex and not tight:
        regime = "BATTLE_ZONE"
    elif not positive_gex and tight:
        regime = "COILED"
    else:
        regime = "TRENDING"

    # ── Directional bias scoring ──────────────────────────────────────
    # Each signal contributes +1 (bullish) or -1 (bearish).
    bias_score = 0

    # 1. Price vs gamma magnet: magnet below price = bearish pull
    if gamma_magnet is not None and spot > 0:
        if spot > gamma_magnet:
            bias_score -= 1   # gravity pulls down
        elif spot < gamma_magnet:
            bias_score += 1   # gravity pulls up

    # 2. Put gamma dominance = bearish; call gamma dominance = bullish
    total_gamma = call_gamma_total + put_gamma_total
    if total_gamma > 0:
        put_ratio = put_gamma_total / total_gamma
        if put_ratio > 0.60:
            bias_score -= 1   # puts dominate -> bearish
        elif put_ratio < 0.40:
            bias_score += 1   # calls dominate -> bullish

    # 3. Net vanna: negative = IV drop is bearish
    if net_vanna < 0:
        bias_score -= 1
    elif net_vanna > 0:
        bias_score += 1

    if bias_score <= -2:
        bias = "BEARISH"
    elif bias_score >= 2:
        bias = "BULLISH"
    else:
        bias = "NEUTRAL"

    return regime, bias


def _net_vanna_exposure(
    calls: list[OptionContract],
    puts: list[OptionContract],
) -> float:
    """
    Signed net vanna exposure across all contracts.

    Vanna = d(delta)/d(IV).  For calls, vanna is typically positive OTM;
    for puts, vanna is typically negative OTM.  We approximate vanna as
    vega × delta (a common proxy when true vanna isn't in the feed).

    Positive net vanna -> IV drop is bullish (dealers buy as IV falls).
    Negative net vanna -> IV drop is bearish (dealers sell as IV falls).
    """
    call_vanna = sum(
        c.open_interest * c.vega * c.delta * CONTRACT_MULTIPLIER
        for c in calls
    )
    put_vanna = sum(
        p.open_interest * p.vega * p.delta * CONTRACT_MULTIPLIER
        for p in puts
    )
    return round(call_vanna + put_vanna, 2)


def calculate_dealer_levels(
    chain: OptionChainData,
    ticker: str,
    *,
    min_oi_floor: int = MIN_OI_THRESHOLD,
    wall_scope: str = "FRONT_WEEK_WEIGHTED",
    wall_dte_range: tuple[int, int] = (0, 14),
) -> DealerLevels:
    spot = chain.spot_price
    if spot <= 0:
        raise ValueError(f"Spot price is zero for {ticker} — cannot calculate levels.")

    strikes = _build_cumulative_profile(_build_strike_gex(chain.calls, chain.puts, spot))
    total_gex = sum(row.net_gex for row in strikes)
    gex_regime = "POSITIVE" if total_gex >= 0 else "NEGATIVE"

    wall_calls = _filter_contracts_by_dte(chain.calls, wall_dte_range)
    wall_puts = _filter_contracts_by_dte(chain.puts, wall_dte_range)
    call_wall, secondary_call_wall = _find_walls(wall_calls, min_oi_floor, spot=spot, side="CALL")
    put_wall, secondary_put_wall = _find_walls(wall_puts, min_oi_floor, spot=spot, side="PUT")
    local_call_node, local_put_node = _find_local_nodes(strikes, spot)

    front_calls, front_puts = _find_front_dte_contracts(chain.calls, chain.puts)
    call_wall_0dte, _ = _find_walls(front_calls, min_oi_floor, spot=spot, side="CALL")
    put_wall_0dte, _ = _find_walls(front_puts, min_oi_floor, spot=spot, side="PUT")

    gamma_flip_lower, gamma_flip_upper, _ = _find_gamma_flip_zone(strikes, spot, min_oi_floor)
    zero_gamma = _find_dynamic_zero_gamma(chain.calls, chain.puts, spot, delta_adjusted=False)
    zero_gamma_delta_adj = _find_dynamic_zero_gamma(chain.calls, chain.puts, spot, delta_adjusted=True)
    hedge_wall = _find_hedge_wall(strikes, spot)
    max_pain = _find_max_pain(front_calls or chain.calls, front_puts or chain.puts)

    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)
    front_expiry = min(c.expiry for c in chain.contracts) if chain.contracts else None
    front_dte = max(0, (front_expiry - now_et.date()).days) if front_expiry else 0
    is_futures = any(ticker.startswith(f) for f in ["/ES", "/NQ", "/CL", "/GC", "ES", "NQ"])
    em_value, straddle = _expected_move(chain.calls, chain.puts, spot, front_dte, is_futures=is_futures, ticker=ticker)

    cliff_up, cliff_down = _find_gamma_cliffs(strikes, spot)

    vanna_call_node = _find_proxy_node(chain.calls, lambda c: c.open_interest * abs(c.vega * c.delta), spot=spot)
    vanna_put_node = _find_proxy_node(chain.puts, lambda p: p.open_interest * abs(p.vega * p.delta), spot=spot)

    # ── Accurate analytical Charm nodes ──────────────────────────────────────
    # Uses the full BSM Charm formula rather than the old theta×delta proxy.
    tz_et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz_et)

    def _contract_t(c: OptionContract) -> float:
        exp_dt_c = datetime.combine(c.expiry, time(16, 0), tzinfo=tz_et)
        return max((exp_dt_c - now_et).total_seconds() / (365 * 24 * 3600), 1e-5)

    def _charm_score_call(c: OptionContract) -> float:
        return c.open_interest * abs(_analytical_charm('c', spot, c.strike, _contract_t(c), max(c.iv, 0.01)))

    def _charm_score_put(p: OptionContract) -> float:
        return p.open_interest * abs(_analytical_charm('p', spot, p.strike, _contract_t(p), max(p.iv, 0.01)))

    charm_call_node = _find_proxy_node(chain.calls, _charm_score_call, spot=spot)
    charm_put_node = _find_proxy_node(chain.puts, _charm_score_put, spot=spot)

    agg = _aggregate_by_strike(chain.calls, chain.puts)
    vol_imb_call, vol_imb_put = _find_volume_imbalance_nodes(agg)
    dex_call_node, dex_put_node = _find_dex_nodes(agg)
    vacuum_lower, vacuum_upper = _find_liquidity_vacuum(agg, spot)

    skew_put_25d, skew_call_25d, put_25d_iv, call_25d_iv, skew_premium = _find_skew_pivots(front_calls, front_puts)

    vt_u05, vt_l05, vt_u10, vt_l10, vt_u15, vt_l15 = _vol_trigger_bands(front_calls or chain.calls, spot)

    # ── Volume centroids (VWAP of strikes by volume) ─────────────────────────
    call_volume_centroid = _volume_centroid(chain.calls)
    put_volume_centroid = _volume_centroid(chain.puts)

    # ── Delta-adjusted GEX ───────────────────────────────────────────────────
    total_gex_delta_adj = _delta_adjusted_gex(chain.calls, chain.puts, spot)

    # ── Net Speed exposure retained for back-compat payloads only ───────────
    net_speed_exposure = _net_speed_exposure(chain.calls, chain.puts, spot)

    # ── Day-trading hedge-flow scenarios (replaces speed in briefing) ───────
    hedge_flow = _expected_hedge_flow_scenarios(chain.calls, chain.puts, spot)

    # NOTE: We intentionally leave None levels as None rather than defaulting
    # them to spot.  Collapsing everything to spot produces meaningless trade
    # plans ("short below spot, long above spot").  Downstream consumers
    # (discord_notifier, file_writer) already display "N/A" for None levels.
    #
    # The only fallback that makes structural sense:
    #   - hedge_wall falls back to put_wall (conceptually similar downside anchor)
    if hedge_wall is None and put_wall is not None:
        hedge_wall = put_wall

    # ── Tier 2 metrics ─────────────────────────────────────────────────────
    gamma_magnet = _gamma_magnet(strikes)
    pin_strike, pin_odds = _pin_strike_and_odds(strikes)
    separation = _wall_separation(call_wall, put_wall)
    call_gamma_total = round(sum(row.call_gex for row in strikes), 2)
    put_gamma_total = round(sum(row.put_gex for row in strikes), 2)
    net_vanna = _net_vanna_exposure(chain.calls, chain.puts)
    concentration_score = (
        abs(total_gex_delta_adj) / (abs(total_gex_delta_adj) + abs(total_gex))
        if (abs(total_gex_delta_adj) + abs(total_gex)) > 0
        else 0.0
    )
    
    # Strike with absolute maximum net GEX magnitude
    max_gex_strike = None
    if strikes:
        max_gex_strike = max(strikes, key=lambda x: abs(x.net_gex or 0)).strike

    call_wall_oi = _oi_at_strike(chain.calls, call_wall)
    put_wall_oi = _oi_at_strike(chain.puts, put_wall)
    pin_strike_oi = _oi_at_strike(chain.calls, pin_strike) + _oi_at_strike(chain.puts, pin_strike)

    # ── Multi-Expiry Expected Moves ──────────────────────────────────────────
    expected_moves = _calculate_all_ems(chain)
    hourly_flow_curve = _hourly_charm_vanna_curve(net_vanna, charm_call_node, charm_put_node)

    regime_label, directional_bias = _classify_regime(
        total_gex, separation, em_value, spot,
        gamma_magnet, put_gamma_total, call_gamma_total, net_vanna,
        skew_premium=skew_premium, total_gex_delta_adj=total_gex_delta_adj
    )

    log.info(
        "%s levels: spot=%.2f gex=%.0f regime=%s(%s %s) zg=%s cw=%s pw=%s "
        "mp=%s em=±%.2f magnet=%s pin=%s(%.0f%%) sep=%s vanna=%.0f skew=%.4f (P:%.4f C:%.4f)",
        ticker,
        spot,
        total_gex,
        gex_regime,
        regime_label,
        directional_bias,
        zero_gamma,
        call_wall,
        put_wall,
        max_pain,
        em_value,
        gamma_magnet,
        pin_strike,
        pin_odds * 100,
        separation,
        net_vanna,
        skew_premium or 0.0,
        put_25d_iv or 0.0,
        call_25d_iv or 0.0
    )

    return DealerLevels(
        ticker=ticker,
        spot=spot,
        total_gex=total_gex,
        gex_regime=gex_regime,
        zero_gamma=zero_gamma,
        zero_gamma_delta_adj=zero_gamma_delta_adj,
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
        put_25d_iv=put_25d_iv,
        call_25d_iv=call_25d_iv,
        volatility_skew_premium=skew_premium,
        # ── Tier 2 ──
        gamma_magnet=gamma_magnet,
        pin_strike=pin_strike,
        pin_odds=pin_odds,
        wall_separation=separation,
        regime_label=regime_label,
        directional_bias=directional_bias,
        call_gamma_total=call_gamma_total,
        put_gamma_total=put_gamma_total,
        net_vanna_exposure=net_vanna,
        wall_scope=wall_scope,
        wall_dte_min=wall_dte_range[0],
        wall_dte_max=wall_dte_range[1],
        concentration_score=round(concentration_score, 4),
        call_wall_oi=call_wall_oi,
        put_wall_oi=put_wall_oi,
        pin_strike_oi=pin_strike_oi,
        expected_moves=expected_moves,
        # ── Enhanced analytics ──
        call_volume_centroid=call_volume_centroid,
        put_volume_centroid=put_volume_centroid,
        total_gex_delta_adj=total_gex_delta_adj,
        net_speed_exposure=net_speed_exposure,
        hedge_flow_up_10=hedge_flow["up_10"],
        hedge_flow_up_25=hedge_flow["up_25"],
        hedge_flow_up_50=hedge_flow["up_50"],
        hedge_flow_dn_10=hedge_flow["dn_10"],
        hedge_flow_dn_25=hedge_flow["dn_25"],
        hedge_flow_dn_50=hedge_flow["dn_50"],
        hourly_flow_curve=hourly_flow_curve,
        max_gex_strike=max_gex_strike,
        atm_iv=_atm_contract(chain.calls, spot).iv if chain.calls else None,
        strike_gex=strikes,
    )


def rescale_levels_to_target_spot(levels: DealerLevels, target_ticker: str, target_spot: float) -> DealerLevels:
    """
    Rescale all price levels from *levels.spot* space into *target_spot* space
    using pure multiplicative scaling: ``new_value = value × (target_spot / source_spot)``.

    This is correct for cross-product rescaling where the ratio between the two
    instruments is roughly constant (e.g. DJX -> YM at ~100×, QQQ -> NDX at ~41×,
    or SPY -> SPX at ~10×).
    """
    if levels.spot <= 0 or target_spot <= 0:
        raise ValueError("Proxy and target spots must be positive for rescaling.")

    if abs(levels.spot - target_spot) < 1e-9 and levels.ticker == target_ticker:
        return levels

    scale = target_spot / levels.spot

    def _scale(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value * scale, 2)

    return DealerLevels(
        ticker=target_ticker,
        spot=round(target_spot, 2),
        total_gex=levels.total_gex,
        gex_regime=levels.gex_regime,
        zero_gamma=_scale(levels.zero_gamma),
        zero_gamma_delta_adj=_scale(levels.zero_gamma_delta_adj),
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
        put_25d_iv=levels.put_25d_iv,                           # <--- NEW (Pass through)
        call_25d_iv=levels.call_25d_iv,                         # <--- NEW (Pass through)
        volatility_skew_premium=levels.volatility_skew_premium,
        # ── Tier 2: price levels get scaled, ratios/labels pass through ──
        gamma_magnet=_scale(levels.gamma_magnet),
        pin_strike=_scale(levels.pin_strike),
        pin_odds=levels.pin_odds,
        wall_separation=round(levels.wall_separation * scale, 2) if levels.wall_separation is not None else None,
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
        # ── Enhanced analytics: centroids are price levels -> scale; rest pass through ──
        call_volume_centroid=_scale(levels.call_volume_centroid),
        put_volume_centroid=_scale(levels.put_volume_centroid),
        total_gex_delta_adj=levels.total_gex_delta_adj,
        net_speed_exposure=levels.net_speed_exposure,
        hedge_flow_up_10=levels.hedge_flow_up_10,
        hedge_flow_up_25=levels.hedge_flow_up_25,
        hedge_flow_up_50=levels.hedge_flow_up_50,
        hedge_flow_dn_10=levels.hedge_flow_dn_10,
        hedge_flow_dn_25=levels.hedge_flow_dn_25,
        hedge_flow_dn_50=levels.hedge_flow_dn_50,
        hourly_flow_curve=levels.hourly_flow_curve,
        max_gex_strike=_scale(levels.max_gex_strike),
        atm_iv=levels.atm_iv,  # dimensionless — no rescaling needed
        iv_change=levels.iv_change,
        strike_gex=[
            type(sg)(
                strike=round(sg.strike * scale, 2),
                call_gex=sg.call_gex,
                put_gex=sg.put_gex,
                net_gex=sg.net_gex,
                call_oi=sg.call_oi,
                put_oi=sg.put_oi,
                call_vol=sg.call_vol,
                put_vol=sg.put_vol,
                call_iv=sg.call_iv,
                put_iv=sg.put_iv,
                cumulative_gex=sg.cumulative_gex,
                # Greek exposures pass through unchanged (not price-scaled)
                call_dex=sg.call_dex,
                put_dex=sg.put_dex,
                call_vex=sg.call_vex,
                put_vex=sg.put_vex,
                call_charm=sg.call_charm,
                put_charm=sg.put_charm,
                call_speed=sg.call_speed,
                put_speed=sg.put_speed,
                call_vomma=sg.call_vomma,
                put_vomma=sg.put_vomma,
                call_premium=sg.call_premium,
                put_premium=sg.put_premium,
            )
            for sg in levels.strike_gex
        ],
        expected_moves=[
            ExpectedMove(
                expiry=em.expiry,
                dte=em.dte,
                em_value=round(em.em_value * scale, 2),
                em_upper=round(em.em_upper * scale, 2),
                em_lower=round(em.em_lower * scale, 2),
                straddle=round(em.straddle * scale, 2),
                straddle_85_upper=round(em.straddle_85_upper * scale, 2) if em.straddle_85_upper else 0.0,
                straddle_85_lower=round(em.straddle_85_lower * scale, 2) if em.straddle_85_lower else 0.0,
            )
            for em in levels.expected_moves
        ],
    )

def calculate_tos_expected_move(spot_price: float, expiry_date_str: str, expiry_volatility: float, is_futures: bool = False) -> float:
    """
    Calculates the Thinkorswim (TOS) Expected Move using the empirically
    calibrated linear time-scaling model (2026-05-09).
    
    expiry_date_str: 'YYYY-MM-DD'
    expiry_volatility: The volatility number (percentage or decimal).
    """
    tz = ZoneInfo("America/New_York")
    today = datetime.now(tz).date()
    
    try:
        clean_date_str = expiry_date_str.split(':')[0] 
        exp_date = datetime.strptime(clean_date_str, "%Y-%m-%d").date()
    except Exception:
        return 0.0
    
    dte = (exp_date - today).days
    if dte < 0:
        return 0.0
        
    vol_decimal = expiry_volatility / 100.0 if expiry_volatility > 1.0 else expiry_volatility
    
    # EM = Price * IV * sqrt((0.637 * DTE + intercept) / 365)
    intercept = 0.69 if is_futures else 0.24
    t_eff_yr = (0.637 * dte + intercept) / 365.0
    
    if t_eff_yr <= 0:
        return 0.0

    return spot_price * vol_decimal * math.sqrt(t_eff_yr)
    
    # 4. Output to screen for verification
    #print("\n" + "="*50)
    # print(f"TOS EXPECTED MOVE VERIFICATION")
    # print(f"Spot Price:        ${spot_price:.2f}")
    # print(f"Expiry Date:       {clean_date_str}")
    # print(f"Blended Vol (IV):  {vol_decimal:.4f} ({vol_decimal*100:.2f}%)")
    # print(f"Fractional DTE:    {fractional_dte:.4f} days")
    # print(f"Calculated TOS EM: ±${tos_expected_move:.2f}")
    # print("="*50 + "\n")
    
    return tos_expected_move


def extract_dominant_oi_nodes(
    chain: OptionChainData, 
    min_dominance_pct: float = 3.0, 
    min_oi_threshold: int | None = None
) -> list[dict[str, Any]]:
    """
    Extracts structural nodes based purely on resting Open Interest dominance,
    ignoring daily volume. 
    """
    spot = float(chain.spot_price)
    
    # Dynamic thresholding if not provided
    if min_oi_threshold is None:
        # Check underlying symbol if attached to chain
        underlying = getattr(chain, 'underlying_symbol', '').upper()
        if underlying.startswith('/'):
            # Futures options are less liquid strike-by-strike
            if 'NQ' in underlying:
                min_oi_threshold = 500    # NQ is thinner
            else:
                min_oi_threshold = 1000   # ES, RTY, etc.
        else:
            min_oi_threshold = 5000       # Standard for SPX/QQQ
            
    total_call_oi = sum(c.open_interest for c in chain.calls)
    total_put_oi = sum(p.open_interest for p in chain.puts)
    
    total_call_oi = max(total_call_oi, 1)
    total_put_oi = max(total_put_oi, 1)

    dominant_nodes = []

    for c in chain.calls:
        oi = c.open_interest
        if oi < min_oi_threshold: continue
        dominance_pct = (oi / total_call_oi) * 100
        # For futures, we allow lower dominance % because strikes are more fragmented
        curr_min_dominance = 1.5 if underlying.startswith('/') else min_dominance_pct
        if dominance_pct >= curr_min_dominance:
            pct_from_spot = abs(c.strike - spot) / spot
            if pct_from_spot <= 0.15: # Ignore deep OTM lotto tickets
                dominant_nodes.append({
                    "strike": float(c.strike),
                    "type": "CALL",
                    "oi": int(oi),
                    "dominance_pct": round(dominance_pct, 1),
                    "label": f"Major Call Node ({round(dominance_pct, 1)}%)"
                })

    for p in chain.puts:
        oi = p.open_interest
        if oi < min_oi_threshold: continue
        dominance_pct = (oi / total_put_oi) * 100
        # For futures, we allow lower dominance % 
        curr_min_dominance = 1.5 if underlying.startswith('/') else min_dominance_pct
        if dominance_pct >= curr_min_dominance:
            pct_from_spot = abs(p.strike - spot) / spot
            if pct_from_spot <= 0.15:
                dominant_nodes.append({
                    "strike": float(p.strike),
                    "type": "PUT",
                    "oi": int(oi),
                    "dominance_pct": round(dominance_pct, 1),
                    "label": f"Major Put Node ({round(dominance_pct, 1)}%)"
                })

    return sorted(dominant_nodes, key=lambda x: x["oi"], reverse=True)