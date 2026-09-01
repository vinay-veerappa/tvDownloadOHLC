"""
Cash-Secured Put (CSP) Scoring Engine
Implements Ben (@PatternProfits)'s exact 100-Point Scoring Model,
Hard Exclusion Filters, and RS / REV / EPS Trend Adjustment Layer.
"""

from datetime import date
from typing import Dict, Any, List, Optional
from scripts.csp_ranking.tos_parser import TOSOptionContract
from scripts.csp_ranking.finviz_client import FinvizTickerProfile
from scripts.csp_ranking.technicals import TechnicalMetrics


class ScoredCandidate:
    def __init__(
        self,
        contract: TOSOptionContract,
        profile: Optional[FinvizTickerProfile],
        technicals: Optional[TechnicalMetrics],
        scan_date: Optional[date] = None,
        min_volume: int = 10,
        max_spread_pct: float = 50.0,
    ):
        self.contract = contract
        self.profile = profile
        self.technicals = technicals
        self.scan_date = scan_date or date.today()
        self.min_volume = min_volume
        self.max_spread_pct = max_spread_pct
        
        # Hard Filter Flags
        self.is_passed_hard_filters: bool = True
        self.exclusion_reasons: List[str] = []
        
        # Base Score Breakdown (100 pts)
        self.ror_pts: float = 0.0           # 25 pts
        self.spread_pts: float = 0.0        # 20 pts
        self.liquidity_pts: float = 0.0     # 15 pts
        self.cushion_pts: float = 0.0       # 15 pts
        self.fundamentals_pts: float = 0.0  # 15 pts
        self.delta_pts: float = 0.0         # 10 pts
        self.base_score: float = 0.0        # Max 100
        
        # Ben Adjustment Layer: RS (+5/-5), REV (+5/0/-8), EPS (+5/0/-8)
        self.rs_adj_pts: int = -5           # +5 if RS > MA, -5 if RS <= MA
        self.sales_adj_pts: int = 0         # +5 growing, 0 mixed, -8 declining
        self.eps_adj_pts: int = 0           # +5 accelerating/stable, 0 choppy, -8 decelerating
        self.total_adjustments: int = 0
        
        # Final Score
        self.final_score: float = 0.0
        self.rank: int = 0

        # Mark & ROR (as displayed in Ben's dashboard)
        self.mark: float = self.contract.mid_price
        self.trade_ror_pct: float = (self.mark / self.contract.strike * 100.0) if self.contract.strike > 0 else 0.0

        # Technical buffer details
        self.cushion_details: Dict[str, Any] = {}
        if self.technicals:
            self.cushion_details = self.technicals.evaluate_cushion(self.contract.strike)
        elif self.profile and self.profile.price > 0:
            otm = (self.profile.price - self.contract.strike) / self.profile.price * 100.0
            self.cushion_details = {
                "otm_cushion_pct": round(otm, 2),
                "is_below_sma50": self.contract.strike < (self.profile.price * (1 + self.profile.sma50_pct / 100.0)),
                "is_below_sma200": self.contract.strike < (self.profile.price * (1 + self.profile.sma200_pct / 100.0)),
                "is_below_swing_low": False,
            }
        else:
            self.cushion_details = {"otm_cushion_pct": 0.0, "is_below_sma50": False, "is_below_sma200": False, "is_below_swing_low": False}

        self._evaluate()

    def _evaluate(self):
        # 1. Hard Exclusion Filters (before scoring)
        
        # A. Earnings before expiration
        if self.profile and self.profile.earnings_date and self.contract.expiry_date:
            earn_d = self.profile.earnings_date
            exp_d = self.contract.expiry_date
            if self.scan_date <= earn_d <= exp_d:
                self.is_passed_hard_filters = False
                self.exclusion_reasons.append(f"Earnings ({earn_d.strftime('%b %d')}) before expiry ({exp_d.strftime('%b %d')})")

        # B. Volume filter (< 10)
        if self.contract.volume < self.min_volume:
            self.is_passed_hard_filters = False
            self.exclusion_reasons.append(f"Volume < {self.min_volume} ({self.contract.volume})")

        # C. Spread filter (> 50% of mid)
        if (self.contract.spread_pct * 100.0) > self.max_spread_pct:
            self.is_passed_hard_filters = False
            self.exclusion_reasons.append(f"Spread > {self.max_spread_pct:.0f}% ({round(self.contract.spread_pct*100, 1)}%)")

        # D. Bid sanity
        if self.contract.bid <= 0.05:
            self.is_passed_hard_filters = False
            self.exclusion_reasons.append(f"Bid too low (${self.contract.bid:.2f})")

        # 2. Base Quantitative Scoring (100 pts)
        
        # A. Return on Risk (25 pts max)
        # Scaled on Trade ROR & Annualized ROR
        ann_ror = self.contract.annualized_ror_pct
        if ann_ror >= 35.0:
            self.ror_pts = 25.0
        elif ann_ror >= 28.0:
            self.ror_pts = 22.0
        elif ann_ror >= 20.0:
            self.ror_pts = 18.0
        elif ann_ror >= 14.0:
            self.ror_pts = 14.0
        elif ann_ror >= 8.0:
            self.ror_pts = 10.0
        else:
            self.ror_pts = 5.0

        # B. Spread Tightness (20 pts max)
        sp_pct = self.contract.spread_pct * 100.0
        if sp_pct <= 8.0:
            self.spread_pts = 20.0
        elif sp_pct <= 15.0:
            self.spread_pts = 16.0
        elif sp_pct <= 25.0:
            self.spread_pts = 12.0
        elif sp_pct <= 35.0:
            self.spread_pts = 8.0
        elif sp_pct <= 50.0:
            self.spread_pts = 4.0
        else:
            self.spread_pts = 0.0

        # C. Liquidity (15 pts max)
        vol = self.contract.volume
        if vol >= 100:
            self.liquidity_pts = 15.0
        elif vol >= 50:
            self.liquidity_pts = 12.0
        elif vol >= 25:
            self.liquidity_pts = 9.0
        elif vol >= 10:
            self.liquidity_pts = 6.0
        else:
            self.liquidity_pts = 2.0

        # D. Technical Cushion (15 pts max)
        otm = self.cushion_details.get("otm_cushion_pct", 0.0)
        cushion_base = 0.0
        if otm >= 15.0:
            cushion_base = 8.0
        elif otm >= 10.0:
            cushion_base = 6.0
        elif otm >= 6.0:
            cushion_base = 4.0
        else:
            cushion_base = 2.0

        sma50_pts = 4.0 if self.cushion_details.get("is_below_sma50", False) else 0.0
        sma200_pts = 3.0 if self.cushion_details.get("is_below_sma200", False) else 0.0
        if sma200_pts == 0 and self.cushion_details.get("is_below_swing_low", False):
            sma200_pts = 3.0
            
        self.cushion_pts = min(15.0, cushion_base + sma50_pts + sma200_pts)

        # E. Fundamentals (15 pts max)
        pe_pts = 5.0 if (self.profile and self.profile.pe and self.profile.pe > 0) else 2.0
        sales_pts = 0.0
        if self.profile:
            if self.profile.sales_qq >= 15.0:
                sales_pts = 5.0
            elif self.profile.sales_qq > 0.0:
                sales_pts = 3.0
            else:
                sales_pts = 0.0

        eps_pts = 0.0
        if self.profile:
            if self.profile.eps_qq >= 20.0:
                eps_pts = 5.0
            elif self.profile.eps_qq > 0.0:
                eps_pts = 3.0
            else:
                eps_pts = 0.0

        self.fundamentals_pts = min(15.0, pe_pts + sales_pts + eps_pts)

        # F. Delta Safety (10 pts max)
        abs_delta = abs(self.contract.delta)
        if 0.12 <= abs_delta <= 0.18:
            self.delta_pts = 10.0 # Sweet spot
        elif (0.08 <= abs_delta < 0.12) or (0.18 < abs_delta <= 0.22):
            self.delta_pts = 8.0
        elif 0.22 < abs_delta <= 0.28:
            self.delta_pts = 5.0
        else:
            self.delta_pts = 2.0

        self.base_score = round(self.ror_pts + self.spread_pts + self.liquidity_pts + self.cushion_pts + self.fundamentals_pts + self.delta_pts, 1)

        # 3. Ben's Exact Adjustment Layer (RS Line, Revenue & EPS Trend)
        
        # RS Line: above its MA -> +5, below -> -5
        if self.technicals and self.technicals.is_rs_above_ma:
            self.rs_adj_pts = 5
        else:
            self.rs_adj_pts = -5

        # Revenue trend: growing -> +5, mixed -> 0, declining -> -8
        if self.profile:
            if self.profile.sales_qq >= 8.0:
                self.sales_adj_pts = 5
            elif self.profile.sales_qq >= 0.0:
                self.sales_adj_pts = 0
            else:
                self.sales_adj_pts = -8
        else:
            self.sales_adj_pts = 0

        # EPS trend: accelerating/stable -> +5, choppy/no clear direction -> 0, decelerating -> -8
        if self.profile:
            if self.profile.eps_qq >= 15.0:
                self.eps_adj_pts = 5
            elif self.profile.eps_qq >= 0.0:
                self.eps_adj_pts = 0
            else:
                self.eps_adj_pts = -8
        else:
            self.eps_adj_pts = 0

        self.total_adjustments = self.rs_adj_pts + self.sales_adj_pts + self.eps_adj_pts
        self.final_score = round(max(0.0, min(100.0, self.base_score + self.total_adjustments)), 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "ticker": self.contract.ticker,
            "strike": self.contract.strike,
            "mark": round(self.mark, 2),
            "stock_price": self.technicals.current_price if self.technicals else (self.profile.price if self.profile else 0.0),
            "otm_cushion_pct": self.cushion_details.get("otm_cushion_pct", 0.0),
            "expiry_date": self.contract.expiry_date.strftime("%b %d '%y") if self.contract.expiry_date else "",
            "dte": self.contract.dte,
            "delta": self.contract.delta,
            "bid": self.contract.bid,
            "ask": self.contract.ask,
            "spread_pct": round(self.contract.spread_pct * 100.0, 1),
            "volume": self.contract.volume,
            "base_score": self.base_score,
            "rs_adj": self.rs_adj_pts,
            "rev_adj": self.sales_adj_pts,
            "eps_adj": self.eps_adj_pts,
            "adj_score": self.final_score,
            "trade_ror_pct": round(self.trade_ror_pct, 2),
            "annualized_ror_pct": round(self.contract.annualized_ror_pct, 1),
            "is_passed_hard_filters": self.is_passed_hard_filters,
            "exclusion_reasons": "; ".join(self.exclusion_reasons),
            "sales_qq": self.profile.sales_qq if self.profile else 0.0,
            "eps_qq": self.profile.eps_qq if self.profile else 0.0,
            "earnings_date": self.profile.earnings_date.strftime("%b %d") if (self.profile and self.profile.earnings_date) else (self.profile.earnings_str if self.profile else "-"),
        }


def rank_csp_candidates(candidates: List[ScoredCandidate], one_contract_per_ticker: bool = False) -> List[ScoredCandidate]:
    """
    Ranks candidates:
    - If one_contract_per_ticker=True, picks the highest scoring contract for each ticker.
    - Passed candidates sorted by adj_score descending, then trade_ror_pct.
    - Excluded candidates sorted descending.
    """
    passed = [c for c in candidates if c.is_passed_hard_filters]
    excluded = [c for c in candidates if not c.is_passed_hard_filters]

    if one_contract_per_ticker:
        # Group passed by ticker, keeping the top scored contract
        ticker_best: Dict[str, ScoredCandidate] = {}
        for c in passed:
            t = c.contract.ticker
            if t not in ticker_best or c.final_score > ticker_best[t].final_score:
                ticker_best[t] = c
            elif c.final_score == ticker_best[t].final_score and c.trade_ror_pct > ticker_best[t].trade_ror_pct:
                ticker_best[t] = c
        passed = list(ticker_best.values())

    passed.sort(key=lambda x: (x.final_score, x.trade_ror_pct, -x.contract.spread_pct), reverse=True)
    excluded.sort(key=lambda x: (x.final_score, x.trade_ror_pct), reverse=True)

    for i, c in enumerate(passed, start=1):
        c.rank = i

    for j, c in enumerate(excluded, start=len(passed) + 1):
        c.rank = j

    return passed + excluded
