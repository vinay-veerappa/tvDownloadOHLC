"""
Autonomous Multi-Quarter Trajectory & Qualitative Deep Review Engine
Inspects sequential quarterly Revenue & EPS progression, RS momentum, and assigns
exact institutional adjustments, notes, and conviction tiers matching Ben (@PatternProfits).
"""

from typing import Dict, Any, List, Optional
import yfinance as yf
from scripts.csp_ranking.scoring_engine import ScoredCandidate


class CandidateDeepAnalysis:
    def __init__(self, candidate: ScoredCandidate):
        self.candidate = candidate
        self.ticker = candidate.contract.ticker
        self.strike = candidate.contract.strike
        self.mark = candidate.mark
        self.exp_str = candidate.contract.expiry_date.strftime("%b %d '%y") if candidate.contract.expiry_date else "-"
        self.trade_ror = candidate.trade_ror_pct
        self.base_score = candidate.base_score
        
        # Extracted sequential data
        self.revenue_history: List[Dict[str, Any]] = []
        self.eps_history: List[Dict[str, Any]] = []
        self.rev_values: List[float] = []
        self.eps_values: List[float] = []
        self.is_recent_ipo: bool = False
        
        # Calculated Qualitative Reads
        self.rs_line_read: str = ""
        self.rev_trend_read: str = ""
        self.eps_trend_read: str = ""
        self.notes_read: str = ""
        
        # Adjustments
        self.rs_adj: int = -5
        self.rev_adj: int = 0
        self.eps_adj: int = 0
        self.final_adj_score: float = 0.0
        self.rank: int = 0
        
        # Conviction Tier (1 = Green Light, 2 = Secondary, 3 = Avoid)
        self.tier: int = 2
        self.tier_label: str = "Tier 2: Cautious"
        self.tier_rationale: str = ""

        self._pull_quarterly_data()
        self._analyze_trajectory()

    def _pull_quarterly_data(self):
        try:
            stock = yf.Ticker(self.ticker)
            q_inc = stock.quarterly_income_stmt
            if q_inc is not None and not q_inc.empty:
                # Revenue
                if "Total Revenue" in q_inc.index:
                    rev_row = q_inc.loc["Total Revenue"].dropna()
                    self.rev_values = [float(v) for v in rev_row.values[:5]]
                    rev_dates = [d.strftime("%b '%y") if hasattr(d, "strftime") else str(d) for d in rev_row.index[:5]]
                    self.revenue_history = [
                        {"date": d, "val": v, "formatted": f"${v/1e6:.1f}M" if v < 1e9 else f"${v/1e9:.2f}B"}
                        for d, v in zip(rev_dates, self.rev_values)
                    ]
                    if len(self.rev_values) < 6:
                        self.is_recent_ipo = True

                # Diluted EPS
                if "Diluted EPS" in q_inc.index:
                    eps_row = q_inc.loc["Diluted EPS"].dropna()
                    self.eps_values = [float(v) for v in eps_row.values[:5]]
                    eps_dates = [d.strftime("%b '%y") if hasattr(d, "strftime") else str(d) for d in eps_row.index[:5]]
                    self.eps_history = [
                        {"date": d, "val": v, "formatted": f"${v:.2f}"}
                        for d, v in zip(eps_dates, self.eps_values)
                    ]
        except Exception as e:
            pass

    def _analyze_trajectory(self):
        # 1. RS Line Read & Adjustment
        tech = self.candidate.technicals
        if tech and tech.rs_ratio > 0:
            rs_val = round(tech.rs_ratio * 100, 2)
            rs_ma = round(tech.rs_sma21 * 100, 2)
            if tech.is_rs_above_ma:
                self.rs_adj = 5
                self.rs_line_read = f"{rs_val} vs {rs_ma} — above"
            else:
                self.rs_adj = -5
                if tech.rs_slope_10d < -10.0:
                    self.rs_line_read = f"{rs_val} vs {rs_ma} — below (sharp slope down)"
                else:
                    self.rs_line_read = f"{rs_val} vs {rs_ma} — below"
        else:
            self.rs_adj = -5
            self.rs_line_read = "Below moving average"

        # 2. Revenue Trend Read & Adjustment
        fin = self.candidate.profile
        sales_qq = fin.sales_qq if fin else 0.0
        
        # Check consecutive quarterly sequence (newest first in self.rev_values)
        if len(self.rev_values) >= 3:
            # Check for deceleration e.g. R0 < R1 or slowing growth
            is_decelerating = self.rev_values[0] < self.rev_values[1] and self.rev_values[1] < self.rev_values[2]
            is_accelerating = self.rev_values[0] > self.rev_values[1] and self.rev_values[1] > self.rev_values[2]
            
            rev_seq_str = " → ".join([item["formatted"] for item in reversed(self.revenue_history[:4])])
            
            if is_accelerating or sales_qq >= 25.0:
                self.rev_adj = 5
                self.rev_trend_read = f"Accelerating ({rev_seq_str})"
            elif is_decelerating or sales_qq < 0.0:
                self.rev_adj = -8
                self.rev_trend_read = f"Decelerating fast ({rev_seq_str})"
            elif sales_qq >= 5.0:
                self.rev_adj = 0
                self.rev_trend_read = f"Positive / Consistent ({rev_seq_str})"
            else:
                self.rev_adj = 0
                self.rev_trend_read = f"Mixed / Plateau ({rev_seq_str})"
        else:
            if sales_qq >= 15.0:
                self.rev_adj = 5
                self.rev_trend_read = f"Strong growth (+{sales_qq:.1f}% YoY)"
            elif sales_qq >= 0.0:
                self.rev_adj = 0
                self.rev_trend_read = f"Moderate (+{sales_qq:.1f}% YoY)"
            else:
                self.rev_adj = -8
                self.rev_trend_read = f"Declining ({sales_qq:.1f}% YoY)"

        # 3. EPS Trend Read & Adjustment
        eps_qq = fin.eps_qq if fin else 0.0
        if len(self.eps_values) >= 3:
            # Check sequential EPS (newest first: eps_values[0], eps_values[1], eps_values[2]...)
            e0, e1, e2 = self.eps_values[0], self.eps_values[1], self.eps_values[2]
            eps_seq_str = " → ".join([item["formatted"] for item in reversed(self.eps_history[:4])])
            
            # Decelerating 3 straight quarters
            if e0 < e1 and e1 < e2:
                self.eps_adj = -8
                self.eps_trend_read = f"Declining 3 straight qtrs ({eps_seq_str})"
            # Turnaround from negative to positive or strong acceleration
            elif (e2 <= 0 and e0 > 0) or (e0 > e1 and e1 >= e2 and e0 > 0):
                self.eps_adj = 5
                self.eps_trend_read = f"Turned profitable / Accelerating ({eps_seq_str})"
            elif e0 > 0 and eps_qq >= 15.0:
                self.eps_adj = 5
                self.eps_trend_read = f"Positive & expanding ({eps_seq_str})"
            elif e0 > 0:
                self.eps_adj = 0
                self.eps_trend_read = f"Positive but choppy ({eps_seq_str})"
            else:
                self.eps_adj = -8
                self.eps_trend_read = f"Volatile / Unprofitable ({eps_seq_str})"
        else:
            if eps_qq >= 20.0:
                self.eps_adj = 5
                self.eps_trend_read = f"Accelerating (+{eps_qq:.1f}% YoY)"
            elif eps_qq >= 0.0:
                self.eps_adj = 0
                self.eps_trend_read = f"Choppy / Flat (+{eps_qq:.1f}% YoY)"
            else:
                self.eps_adj = -8
                self.eps_trend_read = f"Decelerating ({eps_qq:.1f}% YoY)"

        # 4. Contextual Notes
        notes_list = []
        if self.is_recent_ipo:
            notes_list.append("Recent IPO / thin quarterly history")
        if self.rev_adj == -8 or self.eps_adj == -8:
            notes_list.append("Growth deceleration risk")
        if self.candidate.cushion_details.get("otm_cushion_pct", 0) >= 15.0:
            notes_list.append("Deep OTM safety cushion")
        if not notes_list:
            notes_list.append("Solid overall setup")
        self.notes_read = "; ".join(notes_list)

        # 5. Final Adjusted Score
        total_adj = self.rs_adj + self.rev_adj + self.eps_adj
        self.final_adj_score = round(max(0.0, min(100.0, self.base_score + total_adj)), 1)
        
        # Update candidate properties
        self.candidate.rs_adj_pts = self.rs_adj
        self.candidate.sales_adj_pts = self.rev_adj
        self.candidate.eps_adj_pts = self.eps_adj
        self.candidate.total_adjustments = total_adj
        self.candidate.final_score = self.final_adj_score

        # 6. Assign Actionable Conviction Tier
        if self.final_adj_score >= 88.0 and self.rev_adj >= 0 and self.eps_adj >= 0:
            self.tier = 1
            self.tier_label = "Tier 1: High Conviction Green Light"
            self.tier_rationale = "Exceptional base metrics with clean fundamental acceleration and strong technical buffer."
        elif self.rev_adj == -8 or self.eps_adj == -8 or self.final_adj_score < 70.0:
            self.tier = 3
            self.tier_label = "Tier 3: Disqualified / Deceleration Trap"
            self.tier_rationale = "Fundamental growth is decelerating despite mechanical scan score."
        else:
            self.tier = 2
            self.tier_label = "Tier 2: Cautious / Secondary Play"
            self.tier_rationale = "Viable premium collection with acceptable risk, but monitor moving average support."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "strike": self.strike,
            "mark": round(self.mark, 2),
            "exp_str": self.exp_str,
            "base_score": self.base_score,
            "rs_adj": self.rs_adj,
            "rev_adj": self.rev_adj,
            "eps_adj": self.eps_adj,
            "final_adj_score": self.final_adj_score,
            "trade_ror": round(self.trade_ror, 2),
            "rs_line_read": self.rs_line_read,
            "rev_trend_read": self.rev_trend_read,
            "eps_trend_read": self.eps_trend_read,
            "notes_read": self.notes_read,
            "tier": self.tier,
            "tier_label": self.tier_label,
            "tier_rationale": self.tier_rationale,
        }


def run_autonomous_deep_review(finalists: List[ScoredCandidate]) -> List[CandidateDeepAnalysis]:
    """
    Runs multi-quarter trajectory and qualitative analysis across all finalists
    and sorts them by final adjusted score descending.
    """
    analyses = [CandidateDeepAnalysis(c) for c in finalists]
    analyses.sort(key=lambda x: (x.final_adj_score, x.trade_ror), reverse=True)
    
    for i, item in enumerate(analyses, start=1):
        item.rank = i
        item.candidate.rank = i

    return analyses
