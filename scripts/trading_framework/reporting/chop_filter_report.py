"""
Chop Filter Impact Analysis.

Evaluates how the composite chop score (Layer 5/6) affects signal quality.
Helps determine the optimal chop_score threshold for a strategy.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from typing import List, Any, Dict

def analyze_chop_impact(
    trades: List[Any], 
    df_enriched: pd.DataFrame,
    output_dir: str = "scripts/trading_framework/reporting/outputs"
) -> Dict[str, Any]:
    """
    Correlate trade outcomes with the chop_score at entry.
    
    Args:
        trades: List of TradeRecord instances
        df_enriched: The full DataFrame with chop_score/chop_regime columns
    """
    os.makedirs(output_dir, exist_ok=True)
    if not trades or "chop_score" not in df_enriched.columns:
        return {}

    # 1. Build a local DataFrame of trades joined with chop data
    trade_data = []
    for t in trades:
        # Get chop data at the bar of entry
        entry_time = t.entry_time
        if entry_time in df_enriched.index:
            chop_row = df_enriched.loc[entry_time]
            trade_data.append({
                "entry_time": entry_time,
                "realized_pnl": t.realized_pnl,
                "chop_score": chop_row["chop_score"],
                "chop_regime": chop_row["chop_regime"],
                "is_win": t.realized_pnl > 0
            })
    
    tdf = pd.DataFrame(trade_data)
    if tdf.empty:
        return {}

    # 2. Group by chop_regime
    regime_stats = tdf.groupby("chop_regime", observed=True).agg({
        "realized_pnl": ["count", "mean", "sum"],
        "is_win": "mean"
    })
    regime_stats.columns = ["count", "avg_pnl", "total_pnl", "win_rate"]

    # 3. Group by chop_score (0 to 4)
    score_stats = tdf.groupby("chop_score").agg({
        "realized_pnl": ["count", "mean", "sum"],
        "is_win": "mean"
    })
    score_stats.columns = ["count", "avg_pnl", "total_pnl", "win_rate"]

    # 4. Plotting
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Chop Filter Impact Analysis", fontsize=16)

    # Panel A: Win Rate by Chop Score
    axes[0].bar(score_stats.index.astype(str), score_stats["win_rate"] * 100, color='skyblue', edgecolor='black')
    axes[0].axhline(tdf["is_win"].mean() * 100, color='red', linestyle='--', label='Baseline Win Rate')
    axes[0].set_title("Win Rate % by Chop Score")
    axes[0].set_xlabel("Chop Score (Higher = More Trending)")
    axes[0].set_ylabel("Win Rate (%)")
    axes[0].legend()

    # Panel B: Cumulative P&L by Chop Score
    axes[1].bar(score_stats.index.astype(str), score_stats["total_pnl"], color='lightgreen', edgecolor='black')
    axes[1].set_title("Total P&L by Chop Score")
    axes[1].set_xlabel("Chop Score")
    axes[1].set_ylabel("Total P&L ($)")

    plot_path = os.path.join(output_dir, "chop_filter_impact.png")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(plot_path)
    plt.close()

    return {
        "regime_stats": regime_stats.to_dict(orient="index"),
        "score_stats": score_stats.to_dict(orient="index"),
        "plot_path": plot_path
    }

def generate_chop_report(impact_data: Dict[str, Any]) -> str:
    """
    Generate markdown summary of chop impact.
    """
    if not impact_data:
        return "> [!WARNING]\n> No chop data available for analysis."

    rs = impact_data["regime_stats"]
    rows = []
    for regime, stats in rs.items():
        rows.append(f"| {regime:10} | {stats['count']:5} | {stats['win_rate']*100:6.1f}% | ${stats['avg_pnl']:8.2f} |")

    report = f"""
## Chop Regime Performance Breakdown
| Regime | Trades | Win Rate | Avg P&L |
| :--- | :--- | :--- | :--- |
{chr(10).join(rows)}

### Recommendation
"""
    # Simple recommendation logic
    trending_wr = rs.get("trending", {}).get("win_rate", 0)
    choppy_wr = rs.get("choppy", {}).get("win_rate", 0)
    
    if trending_wr > choppy_wr + 0.1:
        report += "> [!IMPORTANT]\n> High correlation detected. Consider a **Chop Score >= 3** filter to improve expectancy."
    else:
        report += "> [!NOTE]\n> Strategy shows relative resilience to chop. Chop filtering may not be the primary driver of performance."

    return report
