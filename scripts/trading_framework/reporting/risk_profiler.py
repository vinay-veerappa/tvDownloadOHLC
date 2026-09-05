import pandas as pd
import numpy as np
from typing import Dict, Any

from scripts.trading_framework.reporting import institutional_metrics as _im


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

    def calculate_metrics(self, trade_returns_pct, max_drawdown_pct: float,
                          formatted: bool = True, ruin_basis=None):
        """The Edge System metrics. Delegates -- see institutional_metrics.py.

        THE RETURNED `ror` IS NOW A FRACTION, not a percentage. This method used
        to return `ror * 100` under the same key `tearsheet.py` used for a
        fraction, so the same field meant two things depending on which report
        produced it. `ror_pct` is provided for renderers that want the
        percentage, and it is named for what it is.
        """
        import numpy as _np
        import pandas as _pd

        r = trade_returns_pct
        if r is None or len(r) == 0:
            return {"Error": "No trades executed."}
        arr = _np.asarray(_pd.Series(r).to_numpy(), dtype="float64")
        pnl_dollars = (arr / 100.0) * self.account_size

        m = _im.compute(pnl_dollars, risk_per_trade=self.risk_per_trade,
                        account_size=self.account_size,
                        max_drawdown_pct=abs(float(max_drawdown_pct)),
                        ruin_basis=ruin_basis)
        if "error" in m:
            return {"Error": m["error"]}
        m["ror_pct"] = m["ror"] * 100.0
        return m

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
