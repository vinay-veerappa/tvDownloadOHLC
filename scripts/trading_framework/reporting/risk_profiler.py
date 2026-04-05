import pandas as pd
import numpy as np
from typing import Dict, Any

class RiskProfiler:
    """
    Institutional Risk Profiler for Prop Firm & Day Trading evaluation.
    Implements advanced metrics from the Edge System:
    EV, PF, SQN, DRR, Losing Streaks, RoR, and CombinedEdge.
    """
    def __init__(self, account_size: float = 50000.0, risk_per_trade: float = 250.0):
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.risk_pct = risk_per_trade / account_size

    def calculate_metrics(self, trade_returns_pct: pd.Series, max_drawdown_pct: float, formatted: bool = True) -> Dict[str, Any]:
        """
        Calculates institutional risk metrics given a series of trade percentage returns.
        """
        # Drop zero-return trades if any (or keep them as breakeven)
        trades = trade_returns_pct[trade_returns_pct != 0].dropna()
        n_trades = len(trades)
        
        if n_trades == 0:
            return {"Error": "No trades executed."}
            
        # Convert % returns to dollar returns based on account size
        trades_dollars = trades * self.account_size
        
        wins = trades_dollars[trades_dollars > 0]
        losses = trades_dollars[trades_dollars < 0]
        
        win_rate = len(wins) / n_trades if n_trades > 0 else 0
        loss_rate = 1.0 - win_rate
        
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else self.risk_per_trade
        
        # 1. Expected Value (EV)
        ev_dollars = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        # 2. Profit Factor (PF)
        total_profit = wins.sum() if len(wins) > 0 else 0
        total_loss = abs(losses.sum()) if len(losses) > 0 else 1e-5
        pf = total_profit / total_loss
        
        # 3. Normalized EV (EV_R)
        ev_r = ev_dollars / self.risk_per_trade
        
        # 4. Combined Edge
        combined_edge = ev_r * pf
        
        # 5. Risk of Ruin (RoR)
        bankroll_losses = self.account_size / self.risk_per_trade
        # Safety bound combined_edge to avoid negative bases or divide by zero
        ce_safe = max(0, min(combined_edge, 0.99))
        if ce_safe > 0:
            ror = ((1 - ce_safe) / (1 + ce_safe)) ** bankroll_losses
        else:
            ror = 1.0 # 100% chance of ruin if edge is 0 or negative
            
        # 6. Consecutive Losses (Max Streak)
        loss_pct_safe = max(1e-5, loss_rate)
        if loss_pct_safe < 1.0:
            max_streak = np.log(n_trades) / np.log(1 / loss_pct_safe)
        else:
            max_streak = n_trades
            
        # 7. Drawdown Risk Rating (DRR)
        # Using the actual max drawdown (which is typically negative, so we abs it)
        mdd_abs_pct = abs(max_drawdown_pct)
        drr = mdd_abs_pct / (self.risk_pct * 100)
        
        # 8. SQN (System Quality Number)
        # R-Multiples for each trade = trade_dollar / risk_per_trade
        r_multiples = trades_dollars / self.risk_per_trade
        std_r = r_multiples.std()
        sqn = (r_multiples.mean() * np.sqrt(n_trades)) / std_r if std_r > 0 else 0
        
        raw = {
            'account_size': self.account_size,
            'risk_per_trade': self.risk_per_trade,
            'risk_pct': self.risk_pct * 100,
            'total_trades': n_trades,
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'ev_dollars': ev_dollars,
            'ev_grade': self._grade_ev(ev_dollars),
            'profit_factor': pf,
            'pf_grade': self._grade_pf(pf),
            'sqn': sqn,
            'sqn_grade': self._grade_sqn(sqn),
            'combined_edge': combined_edge,
            'ce_grade': self._grade_ce(combined_edge),
            'ror': ror * 100,
            'ror_grade': 'Excellent' if ror < 0.01 else 'Dangerous' if ror > 0.1 else 'OK',
            'max_streak': int(np.ceil(max_streak)),
            'drr': drr,
            'drr_grade': self._grade_drr(drr)
        }

        if not formatted:
            return raw

        return {
            'Account Size': f"${raw['account_size']:,.2f}",
            'Risk Per Trade': f"${raw['risk_per_trade']:,.2f} ({raw['risk_pct']:.2f}%)",
            'Total Trades': raw['total_trades'],
            'Win Rate': f"{raw['win_rate']:.1f}%",
            'Avg Win': f"${raw['avg_win']:.2f}",
            'Avg Loss': f"${raw['avg_loss']:.2f}",
            'EV ($)': f"${raw['ev_dollars']:.2f} (Grade: {raw['ev_grade']})",
            'Profit Factor': f"{raw['profit_factor']:.2f} (Grade: {raw['pf_grade']})",
            'SQN': f"{raw['sqn']:.2f} (Grade: {raw['sqn_grade']})",
            'Combined Edge': f"{raw['combined_edge']:.2f} (Grade: {raw['ce_grade']})",
            'Risk of Ruin': f"{raw['ror']:.2f}% (Grade: {raw['ror_grade']})",
            'Max Losing Streak': f"{raw['max_streak']} trades",
            'DRR': f"{raw['drr']:.2f} (Grade: {raw['drr_grade']})"
        }

    def _grade_ev(self, ev: float) -> str:
        if ev > 100: return 'A'
        if ev >= 50: return 'B'
        if ev >= 10: return 'C'
        if ev > 0: return 'D'
        return 'F'

    def _grade_pf(self, pf: float) -> str:
        if pf >= 1.8: return 'A'
        if pf >= 1.4: return 'B'
        if pf >= 1.2: return 'C'
        if pf >= 1.0: return 'D'
        return 'F'

    def _grade_sqn(self, sqn: float) -> str:
        if sqn >= 3.0: return 'A'
        if sqn >= 2.5: return 'B'
        if sqn >= 2.0: return 'C'
        if sqn >= 1.5: return 'D'
        return 'F'

    def _grade_drr(self, drr: float) -> str:
        if drr < 4: return 'A'
        if drr <= 6: return 'B'
        if drr <= 8: return 'C'
        if drr <= 10: return 'D'
        return 'F'
        
    def _grade_ce(self, ce: float) -> str:
        if ce > 150: return 'A'
        if ce >= 100: return 'B'
        if ce >= 50: return 'C'
        if ce >= 20: return 'D'
        return 'F'

    def print_report(self, metrics: Dict[str, Any], title: str = "Institutional Risk Profile"):
        print(f"\n{'='*50}\n{title.upper().center(50)}\n{'='*50}")
        for k, v in metrics.items():
            print(f"{k.ljust(25)}: {v}")
        print("="*50 + "\n")
