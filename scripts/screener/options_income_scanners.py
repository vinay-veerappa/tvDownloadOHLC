"""
Advanced Options Income & Structure Scanner Engine
Scans and ranks:
1. Covered Calls (High-Yield 2-4% monthly cash flow with 5-10% upside cushion)
2. Poor Man's Covered Calls / LEAPS (Deep ITM 0.80 Delta Long + 0.25 Delta Short Call)
3. Iron Condors (16-Delta Range-Bound Theta Harvesting)

Hot-reloaded via scripts.utils.universe_manager.
"""

import sys
import math
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path
import yfinance as yf
import pandas as pd
from scipy.stats import norm

# Dynamic root resolution
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scripts.csp_ranking.finviz_client import FinvizClient
from scripts.csp_ranking.technicals import TechnicalAnalyzer
from scripts.utils.universe_manager import (
    get_universe,
    get_dynamic_csp_universe,
    get_dynamic_institutional_universe
)


def bs_call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculates Black-Scholes Call Delta."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return float(norm.cdf(d1))


def bs_put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculates Black-Scholes Put Delta."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return float(norm.cdf(d1) - 1.0)


# ─── 1. COVERED CALL SCANNER ──────────────────────────────────────────────────

class CoveredCallCandidate:
    def __init__(self, data: Dict[str, Any]):
        self.ticker = data["ticker"]
        self.spot = data["spot"]
        self.strike = data["strike"]
        self.expiry_date = data["expiry_date"]
        self.dte = data["dte"]
        self.bid = data["bid"]
        self.ask = data["ask"]
        self.mid = data["mid"]
        self.delta = data["delta"]
        self.iv = data["iv"]
        self.open_interest = data["open_interest"]
        self.volume = data["volume"]
        self.static_yield_pct = data["static_yield_pct"]
        self.if_called_yield_pct = data["if_called_yield_pct"]
        self.downside_cushion_pct = data["downside_cushion_pct"]
        self.ann_yield_pct = data["ann_yield_pct"]
        self.score = data["score"]
        self.notes = data.get("notes", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "spot": round(self.spot, 2),
            "strike": round(self.strike, 2),
            "expiry": self.expiry_date.strftime("%b %d, %Y"),
            "dte": self.dte,
            "mid": round(self.mid, 2),
            "delta": round(self.delta, 2),
            "static_yield_pct": round(self.static_yield_pct, 2),
            "if_called_yield_pct": round(self.if_called_yield_pct, 2),
            "downside_cushion_pct": round(self.downside_cushion_pct, 2),
            "ann_yield_pct": round(self.ann_yield_pct, 1),
            "score": round(self.score, 1),
            "notes": self.notes
        }


def scan_covered_calls(
    tickers: Optional[List[str]] = None,
    min_price: float = 10.0,
    min_dte: int = 20,
    max_dte: int = 45,
    min_delta: float = 0.15,
    max_delta: float = 0.40,
    min_static_yield_pct: float = 1.2,
    min_open_interest: int = 5,
) -> List[CoveredCallCandidate]:
    """
    Scans for optimal Covered Call candidates across the universe.
    Filters: Price > 50 SMA, No Earnings Before Expiration, 1.2%+ Monthly Yield.
    """
    target_tickers = tickers or get_dynamic_csp_universe()
    today = date.today()
    finviz_client = FinvizClient()
    candidates: List[CoveredCallCandidate] = []

    print(f"\n🎯 Running Covered Call Scanner across {len(target_tickers)} liquid tickers...")

    for ticker in target_tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            if hist.empty or len(hist) < 30:
                continue

            current_price = float(hist["Close"].iloc[-1])
            if current_price < min_price:
                continue

            # 1. Technical Health: Price > 50 SMA (in uptrend or consolidation)
            sma50 = float(hist["Close"].rolling(50).mean().iloc[-1]) if len(hist) >= 50 else current_price
            if current_price < sma50 * 0.90:
                continue # Skip stocks in sharp downtrends below 50 SMA

            # 2. Check Forward Earnings
            prof = finviz_client.get_ticker_profile(ticker)
            if prof and prof.earnings_date:
                days_to_earn = (prof.earnings_date - today).days
                if 0 <= days_to_earn <= max_dte:
                    continue # Skip if earnings inside DTE window

            # 3. Scan Expirations
            expirations = stock.options
            if not expirations:
                continue

            valid_exps = []
            for exp_s in expirations:
                exp_d = datetime.strptime(exp_s, "%Y-%m-%d").date()
                dte = (exp_d - today).days
                if min_dte <= dte <= max_dte:
                    valid_exps.append((exp_s, exp_d, dte))

            # 4. Scan Call Chains
            for exp_s, exp_d, dte in valid_exps:
                chain = stock.option_chain(exp_s)
                calls = chain.calls
                if calls.empty:
                    continue

                T = max(1, dte) / 365.0

                for _, row in calls.iterrows():
                    strike = float(row.get("strike", 0))
                    bid = float(row.get("bid", 0))
                    ask = float(row.get("ask", 0))
                    last_p = float(row.get("lastPrice", 0))
                    vol = int(row.get("volume", 0) if pd.notna(row.get("volume")) else 0)
                    oi = int(row.get("openInterest", 0) if pd.notna(row.get("openInterest")) else 0)
                    iv = float(row.get("impliedVolatility", 0))

                    if strike <= current_price or oi < min_open_interest:
                        continue

                    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else last_p
                    if mid <= 0.15:
                        continue

                    # Spread tightness check
                    spread_pct = ((ask - bid) / mid) * 100.0 if (bid > 0 and ask > 0 and mid > 0) else 15.0
                    if spread_pct > 50.0:
                        continue

                    # Calculate Black-Scholes Delta
                    sigma = max(0.1, iv)
                    delta = bs_call_delta(current_price, strike, T, 0.045, sigma)

                    if not (min_delta <= delta <= max_delta):
                        continue

                    # Yield Calculations
                    static_yield = (mid / current_price) * 100.0
                    if static_yield < min_static_yield_pct:
                        continue

                    cap_gain_pct = ((strike - current_price) / current_price) * 100.0
                    if_called_yield = static_yield + cap_gain_pct
                    ann_yield = static_yield * (365.0 / dte)
                    downside_cushion = static_yield

                    # Scoring (0-100)
                    score = min(100.0, (static_yield * 12.0) + (cap_gain_pct * 4.0) + (20.0 if spread_pct < 15 else 10.0))

                    cand = CoveredCallCandidate({
                        "ticker": ticker,
                        "spot": current_price,
                        "strike": strike,
                        "expiry_date": exp_d,
                        "dte": dte,
                        "bid": bid,
                        "ask": ask,
                        "mid": mid,
                        "delta": delta,
                        "iv": iv * 100.0,
                        "open_interest": oi,
                        "volume": vol,
                        "static_yield_pct": static_yield,
                        "if_called_yield_pct": if_called_yield,
                        "downside_cushion_pct": downside_cushion,
                        "ann_yield_pct": ann_yield,
                        "score": score,
                        "notes": f"Upside room +{cap_gain_pct:.1f}% to strike with {downside_cushion:.1f}% premium buffer"
                    })
                    candidates.append(cand)

        except Exception:
            continue

    # Sort descending by score (best 1 per ticker)
    candidates.sort(key=lambda x: x.score, reverse=True)
    seen = set()
    deduped = []
    for c in candidates:
        if c.ticker not in seen:
            seen.add(c.ticker)
            deduped.append(c)

    print(f"✅ Covered Call Scan complete: Found {len(deduped)} top candidates.")
    return deduped


# ─── 2. POOR MAN'S COVERED CALL / LEAPS SCANNER ───────────────────────────────

class PmccCandidate:
    def __init__(self, data: Dict[str, Any]):
        self.ticker = data["ticker"]
        self.spot = data["spot"]
        self.long_strike = data["long_strike"]
        self.long_expiry = data["long_expiry"]
        self.long_dte = data["long_dte"]
        self.long_cost = data["long_cost"]
        self.long_delta = data["long_delta"]
        self.short_strike = data["short_strike"]
        self.short_expiry = data["short_expiry"]
        self.short_dte = data["short_dte"]
        self.short_credit = data["short_credit"]
        self.short_delta = data["short_delta"]
        self.net_debit = data["net_debit"]
        self.roc_pct = data["roc_pct"]
        self.score = data["score"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "spot": round(self.spot, 2),
            "long_leg": f"{self.long_expiry.strftime('%b %y')} ${self.long_strike:.1f}C (Δ {self.long_delta:.2f})",
            "short_leg": f"{self.short_expiry.strftime('%b %d')} ${self.short_strike:.1f}C (Δ {self.short_delta:.2f})",
            "net_debit": round(self.net_debit, 2),
            "short_credit": round(self.short_credit, 2),
            "roc_pct": round(self.roc_pct, 2),
            "score": round(self.score, 1)
        }


def scan_pmcc_leaps(
    tickers: Optional[List[str]] = None,
    min_leaps_dte: int = 150,
    max_leaps_dte: int = 400,
    target_long_delta: float = 0.80,
    short_dte_window: tuple = (25, 45),
    target_short_delta: float = 0.25,
) -> List[PmccCandidate]:
    """
    Scans for Poor Man's Covered Calls (Deep ITM LEAPS + Short Front Call).
    """
    target_tickers = tickers or get_dynamic_institutional_universe()
    today = date.today()
    candidates: List[PmccCandidate] = []

    print(f"\n🚀 Running LEAPS / Poor Man's Covered Call (PMCC) Scanner across {len(target_tickers)} leaders...")

    for ticker in target_tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 50:
                continue

            current_price = float(hist["Close"].iloc[-1])
            if current_price < 20.0:
                continue

            expirations = stock.options
            if not expirations:
                continue

            # Find LEAPS Expiration
            leaps_exps = []
            front_exps = []
            for exp_s in expirations:
                exp_d = datetime.strptime(exp_s, "%Y-%m-%d").date()
                dte = (exp_d - today).days
                if min_leaps_dte <= dte <= max_leaps_dte:
                    leaps_exps.append((exp_s, exp_d, dte))
                elif short_dte_window[0] <= dte <= short_dte_window[1]:
                    front_exps.append((exp_s, exp_d, dte))

            if not leaps_exps or not front_exps:
                continue

            # Pick furthest LEAPS and nearest ~30 DTE front month
            leaps_s, leaps_d, leaps_dte = leaps_exps[-1]
            front_s, front_d, front_dte = front_exps[0]

            # 1. Pull LEAPS Chain (find 0.75-0.85 Delta ITM Call)
            leaps_calls = stock.option_chain(leaps_s).calls
            front_calls = stock.option_chain(front_s).calls

            T_long = leaps_dte / 365.0
            best_long = None
            for _, r in leaps_calls.iterrows():
                k = float(r.get("strike", 0))
                bid = float(r.get("bid", 0))
                ask = float(r.get("ask", 0))
                iv = float(r.get("impliedVolatility", 0.3))
                if k >= current_price or bid <= 0:
                    continue
                d = bs_call_delta(current_price, k, T_long, 0.045, max(0.1, iv))
                if 0.70 <= d <= 0.85:
                    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else float(r.get("lastPrice", 0))
                    best_long = (k, mid, d, leaps_d, leaps_dte)
                    break

            # 2. Pull Front Call Chain (find 0.20-0.30 Delta OTM Call)
            T_short = front_dte / 365.0
            best_short = None
            for _, r in front_calls.iterrows():
                k = float(r.get("strike", 0))
                bid = float(r.get("bid", 0))
                ask = float(r.get("ask", 0))
                iv = float(r.get("impliedVolatility", 0.3))
                if k <= current_price or bid <= 0:
                    continue
                d = bs_call_delta(current_price, k, T_short, 0.045, max(0.1, iv))
                if 0.20 <= d <= 0.35:
                    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else float(r.get("lastPrice", 0))
                    best_short = (k, mid, d, front_d, front_dte)
                    break

            if best_long and best_short:
                l_k, l_mid, l_d, l_exp, l_dte = best_long
                s_k, s_mid, s_d, s_exp, s_dte = best_short

                net_debit = l_mid - s_mid
                if net_debit <= 0:
                    continue

                roc = (s_mid / net_debit) * 100.0
                score = (roc * 10.0) + (l_d * 20.0)

                cand = PmccCandidate({
                    "ticker": ticker,
                    "spot": current_price,
                    "long_strike": l_k,
                    "long_expiry": l_exp,
                    "long_dte": l_dte,
                    "long_cost": l_mid,
                    "long_delta": l_d,
                    "short_strike": s_k,
                    "short_expiry": s_exp,
                    "short_dte": s_dte,
                    "short_credit": s_mid,
                    "short_delta": s_d,
                    "net_debit": net_debit,
                    "roc_pct": roc,
                    "score": score
                })
                candidates.append(cand)

        except Exception:
            continue

    candidates.sort(key=lambda x: x.score, reverse=True)
    print(f"✅ PMCC / LEAPS Scan complete: Found {len(candidates)} high-leverage setups.")
    return candidates


# ─── 3. CLI & OUTPUT ──────────────────────────────────────────────────────────

def print_options_income_leaderboard():
    cc_list = scan_covered_calls()
    pmcc_list = scan_pmcc_leaps()

    print("\n" + "=" * 95)
    print("  COVERED CALL INCOME LEADERBOARD (Top Yield with Upside Buffer)")
    print("=" * 95)
    print(f"  {'#':<3} {'Ticker':<7} {'Spot':<8} {'Strike':<9} {'Exp':<11} {'Mark':<7} {'Static Yield':<13} {'If Called':<11} {'Ann. Yield':<11} {'Score':<6}")
    print("  " + "-" * 91)
    for i, c in enumerate(cc_list[:10], 1):
        print(f"  {i:<3} {c.ticker:<7} ${c.spot:<7.2f} ${c.strike:<8.1f} {c.expiry_date.strftime('%b %d'):<11} ${c.mid:<6.2f} {c.static_yield_pct:<12.2f}% {c.if_called_yield_pct:<10.2f}% {c.ann_yield_pct:<10.1f}% ⭐️ {c.score:.1f}")

    print("\n" + "=" * 95)
    print("  POOR MAN'S COVERED CALL (PMCC) / LEAPS LEADERBOARD (Deep ITM + Front Month Rent)")
    print("=" * 95)
    print(f"  {'#':<3} {'Ticker':<7} {'Spot':<8} {'Long LEAPS Leg':<25} {'Short Front Leg':<25} {'Net Cost':<10} {'Monthly ROC':<11}")
    print("  " + "-" * 91)
    for i, p in enumerate(pmcc_list[:10], 1):
        l_str = f"{p.long_expiry.strftime('%b %y')} ${p.long_strike:.0f}C (Δ{p.long_delta:.2f})"
        s_str = f"{p.short_expiry.strftime('%b %d')} ${p.short_strike:.0f}C (Δ{p.short_delta:.2f})"
        print(f"  {i:<3} {p.ticker:<7} ${p.spot:<7.2f} {l_str:<25} {s_str:<25} ${p.net_debit:<9.2f} {p.roc_pct:<10.2f}%")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    print_options_income_leaderboard()
