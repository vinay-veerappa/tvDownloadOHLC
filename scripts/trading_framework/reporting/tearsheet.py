"""
Tearsheet generation logic - metrics and performance summary.

Computes standard risk/reward metrics (Sharpe, Sortino, CAGR, DD)
and institutional metrics (Prop Pass Rate, Consecutive Losers).
"""
import pandas as pd
import numpy as np

from scripts.trading_framework.reporting import institutional_metrics as _im
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict

# The grade thresholds are the spec's and live with the formulas. Aliased rather
# than re-stated: a second copy of a threshold is how the /100 vs /225 Combined
# Edge scale error survived long enough to grade the spec's own A+ system as F.
_grade_ev = _im.grade_ev
_grade_pf = _im.grade_pf
_grade_sqn = _im.grade_sqn
_grade_drr = _im.grade_drr
_grade_ce = _im.grade_ce


def compute_institutional_metrics(trades: List[Any], equity_curve: pd.Series,
                                  account_size: float = 50000.0,
                                  risk_per_trade: float = 250.0,
                                  ruin_basis=None) -> Dict[str, Any]:
    """The Edge System metrics. Delegates -- the formulas live in ONE place.

    This function used to hold its own copy of every formula, and
    `risk_profiler.py` held a second copy. They agreed on the arithmetic and
    disagreed on the UNITS of `ror` (fraction here, fraction*100 there) while
    `optimization_summary.py` read the key expecting a percentage.

    `ruin_basis` says what "ruin" means, and it is the single most important
    input: the SAME trades score 0.00% against a 100%-of-account threshold and
    ~20% against a prop firm's trailing drawdown. When it is not supplied the
    default is a fraction of the account (NOT the whole account, which is the
    defect that made this metric unable to report danger).
    """
    if trades is None or len(trades) == 0:
        return {}

    pnl_dollars = np.array([t.realized_pnl for t in trades], dtype="float64")

    rolling_max = equity_curve.cummax()
    max_dd_pct = abs(float(((equity_curve - rolling_max) / rolling_max).min()) * 100.0)

    return _im.compute(pnl_dollars, risk_per_trade=risk_per_trade,
                       account_size=account_size, max_drawdown_pct=max_dd_pct,
                       ruin_basis=ruin_basis)


def compute_performance_metrics(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> Dict[str, Any]:
    """
    Compute standard performance metrics for an equity curve.
    
    Args:
        equity_curve: Series of cumulative account balance
        risk_free_rate: Annualized risk-free rate
        
    Returns:
        Dictionary of metrics
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return {}
        
    # 1. Total & Annualized Return
    start_val = equity_curve.iloc[0]
    end_val = equity_curve.iloc[-1]
    total_return = (end_val / start_val) - 1
    
    # Calculate years based on index (assuming 252 trading days/year)
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = max(days / 365.25, 0.001)
    cagr = (end_val / start_val) ** (1 / years) - 1 if end_val > 0 else -1.0

    # 2. Daily & Volatility
    daily_returns = equity_curve.pct_change().dropna()
    avg_daily_return = daily_returns.mean()
    daily_vol = daily_returns.std()
    
    # 3. Risk-Adjusted
    sharpe = 0
    if daily_vol > 0:
        # Sharpe = (Avg - RF) / Std -> Annualized
        excess_return = avg_daily_return - (risk_free_rate / 252)
        sharpe = (excess_return / daily_vol) * np.sqrt(252)
        
    # Sortino (Downside risk only)
    downside_returns = daily_returns[daily_returns < 0]
    downside_vol = downside_returns.std()
    sortino = 0
    if downside_vol > 0:
        sortino = (avg_daily_return / downside_vol) * np.sqrt(252)
        
    # 4. Drawdown
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # Calmar (CAGR / MaxDD)
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else np.nan

    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "volatility": daily_vol * np.sqrt(252),
        "end_balance": end_val
    }


def analyze_trade_metrics(trades: List[Any], point_value: float = 2.0) -> Dict[str, Any]:
    """
    Analyze per-trade statistics.
    
    Args:
        trades: List of TradeRecord instances
        
    Returns:
        Dictionary of trade stats
    """
    if trades is None or len(trades) == 0:
        return {}
        
    realized_pnl = np.array([t.realized_pnl for t in trades])
    wins = realized_pnl[realized_pnl > 0]
    losses = realized_pnl[realized_pnl <= 0]
    
    win_rate = len(wins) / len(realized_pnl)
    profit_factor = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else np.inf
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = losses.mean() if len(losses) > 0 else 0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    
    # Calculate max consecutive losers
    consecutive_losers = 0
    max_consecutive_losers = 0
    for pnl in realized_pnl:
        if pnl <= 0:
            consecutive_losers += 1
            max_consecutive_losers = max(max_consecutive_losers, consecutive_losers)
        else:
            consecutive_losers = 0
            
    return {
        "count": len(realized_pnl),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "max_consecutive_losers": max_consecutive_losers,
        "net_pnl": realized_pnl.sum()
    }


def generate_tearsheet(result: Any) -> str:
    """
    Generate a full markdown tearsheet summary of a PortfolioResult.
    """
    # result is expected to be a PortfolioResult or similar
    perf = compute_performance_metrics(result.combined_equity_curve)
    trades = analyze_trade_metrics(result.combined_trades)
    
    # Fetch account-level risk parameters for institutional grading
    # Note: result.account_summary should have 'starting_equity' and 'risk_per_trade'
    starting_equity = result.account_summary.get('starting_equity', 50000.0)
    risk_per_trade = result.account_summary.get('risk_per_trade', 250.0)
    
    # The caller may declare what ruin MEANS. Without it the module falls back
    # to a fraction of the account -- never to the whole account.
    inst = compute_institutional_metrics(
        result.combined_trades, result.combined_equity_curve,
        starting_equity, risk_per_trade,
        ruin_basis=getattr(result, 'ruin_basis', None))
    
    report = f"""
# Institutional Performance Tearsheet

## Summary
- **Prop Eval Passed**: {'✅ YES' if result.prop_eval_passed else '❌ NO'}
- **Days to Pass**: {result.days_to_pass if result.days_to_pass is not None else 'N/A'}
- **Net P&L**: ${trades.get('net_pnl', 0):,.2f}
- **Final Balance**: ${perf.get('end_balance', 0):,.2f}

## Institutional Grades
| Component | Metric | Grade |
| :--- | :--- | :---: |
| **Expected Value (EV)** | ${inst.get('ev', 0):.2f} | **{inst.get('ev_grade', 'F')}** |
| **Profit Factor (PF)** | {inst.get('pf', 0):.2f} | **{inst.get('pf_grade', 'F')}** |
| **System Quality (SQN)** | {inst.get('sqn', 0):.2f} | **{inst.get('sqn_grade', 'F')}** |
| **Drawdown Risk (DRR)** | {inst.get('drr', 0):.2f} | **{inst.get('drr_grade', 'F')}** |
| **Combined Edge** | {inst.get('combined_edge', 0):.2f} | **{inst.get('ce_grade', 'F')}** |

### Risk Analysis
- **Risk of Ruin (RoR)**: {inst.get('ror', 1)*100:.2f}% ({inst.get('ror_grade', 'unknown')})
  - *measured against*: {inst.get('ruin_basis', 'UNDECLARED')} = {inst.get('ruin_units', float('nan')):.1f} losing trades
- **Max losing streak (expected)**: {inst.get('max_streak', 0)} trades
- **Unit Risk (R)**: ${risk_per_trade:,.2f} ({ (risk_per_trade/starting_equity)*100:.2f}%)
- **Starting Equity**: ${starting_equity:,.2f}

## Risk/Reward Profiles
| Metric | Value |
| :--- | :--- |
| **Total Return** | {perf.get('total_return', 0)*100:,.2f}% |
| **Annualized Return (CAGR)** | {perf.get('cagr', 0)*100:,.2f}% |
| **Max Drawdown** | {perf.get('max_drawdown', 0)*100:,.2f}% |
| **Sharpe Ratio** | {perf.get('sharpe', 0):.2f} |
| **Sortino Ratio** | {perf.get('sortino', 0):.2f} |
| **Calmar Ratio** | {perf.get('calmar', 0):.2f} |
| **Volatility (Ann.)** | {perf.get('volatility', 0)*100:,.2f}% |

## Trade Statistics
| Metric | Value |
| :--- | :--- |
| **Total Trades** | {trades.get('count', 0)} |
| **Win Rate** | {trades.get('win_rate', 0)*100:,.2f}% |
| **Profit Factor** | {trades.get('profit_factor', 0):.2f} |
| **Average Win** | ${trades.get('avg_win', 0):,.2f} |
| **Average Loss** | ${trades.get('avg_loss', 0):,.2f} |
| **Expectancy** | ${trades.get('expectancy', 0):,.2f} per trade |
| **Max Consecutive Losers** | {trades.get('max_consecutive_losers', 0)} |

## Account Summary
- **Peak Equity**: ${result.account_summary.get('peak_equity', 0):,.2f}
- **Current Balance**: ${result.account_summary.get('current_balance', 0):,.2f}
- **Current Drawdown**: ${result.account_summary.get('current_drawdown', 0):,.2f}
- **Max Trailing Drawdown Limit**: ${result.account_summary.get('max_trailing_drawdown', 0):,.2f}
"""
    return report
