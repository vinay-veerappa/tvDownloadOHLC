"""
Reporting logic for MFE/MAE analysis.

Generates visualizations (scatter plots, histograms) to analyze
signal quality and efficiency.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from typing import List, Optional

def plot_mfe_mae_analysis(
    mfe_mae_df: pd.DataFrame, 
    horizon: int, 
    output_dir: str = "scripts/trading_framework/reporting/outputs"
) -> str:
    """
    Generate a 3-panel statistical report for a specific horizon.
    
    1. MFE vs MAE Scatter (Risk/Reward clusters)
    2. Efficiency Histogram (MFE / absolute MAE)
    3. Net Excursion (MFE + MAE) - Average "bias" over time
    """
    os.makedirs(output_dir, exist_ok=True)
    mfe_col = f"mfe_{horizon}"
    mae_col = f"mae_{horizon}"
    
    # Filter valid rows
    data = mfe_mae_df[[mfe_col, mae_col]].dropna()
    if data.empty:
        return ""

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Signal Quality Analysis ({horizon} bars)", fontsize=16)

    # 1. Scatter Plot
    axes[0].scatter(data[mfe_col], data[mae_col], alpha=0.5, c='blue', edgecolors='white')
    axes[0].set_title("MFE vs MAE (ATR Normalized)")
    axes[0].set_xlabel("MFE (Favorable)")
    axes[0].set_ylabel("MAE (Adverse)")
    axes[0].grid(True, linestyle='--', alpha=0.7)
    # Add identity line
    lims = [
        np.min([axes[0].get_xlim(), axes[0].get_ylim()]),
        np.max([axes[0].get_xlim(), axes[0].get_ylim()]),
    ]
    axes[0].plot(lims, [-x for x in lims], 'r--', alpha=0.3)

    # 2. Efficiency (MFE / |MAE|)
    # Use log scale or clip to reasonable range to handle infinite/huge values
    efficiency = data[mfe_col] / data[mae_col].abs().replace(0, 0.001)
    efficiency = efficiency.clip(-10, 10)
    
    axes[1].hist(efficiency, bins=30, color='green', alpha=0.6, edgecolor='black')
    axes[1].axvline(1.0, color='red', linestyle='--', label='1:1 Risk/Reward')
    axes[1].set_title("Efficiency Ratio (MFE / |MAE|)")
    axes[1].set_xlabel("Ratio (clipped to [-10, 10])")
    axes[1].legend()

    # 3. Net Bias (MFE + MAE)
    # Sum of excursions should be positive for an edge (MFE > |MAE|)
    net_bias = data[mfe_col] + data[mae_col]
    axes[2].hist(net_bias, bins=30, color='orange', alpha=0.6, edgecolor='black')
    axes[2].axvline(0, color='black', linestyle='-', linewidth=1)
    axes[2].axvline(net_bias.mean(), color='red', linestyle='--', label=f'Mean: {net_bias.mean():.2f}')
    axes[2].set_title("Net Signal Bias (MFE + MAE)")
    axes[2].set_xlabel("ATR Net Excursion")
    axes[2].legend()

    file_path = os.path.join(output_dir, f"mfe_mae_analysis_{horizon}.png")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(file_path)
    plt.close()
    
    return file_path


def generate_mfe_mae_summary(mfe_mae_df: pd.DataFrame, horizons: List[int]) -> str:
    """
    Generate a markdown summary of MFE/MAE stats across horizons.
    """
    rows = []
    for h in horizons:
        m_col = f"mfe_{h}"
        a_col = f"mae_{h}"
        if m_col in mfe_mae_df.columns:
            m_mean = mfe_mae_df[m_col].mean()
            a_mean = mfe_mae_df[a_col].mean()
            eff = m_mean / abs(a_mean) if a_mean != 0 else 0
            rows.append(f"| {h} | {m_mean:.2f} ATR | {a_mean:.2f} ATR | {eff:.2f} |")

    report = f"""
## MFE/MAE Efficiency Matrix
| Horizon (Bars) | Avg MFE | Avg MAE | Efficiency Ratio |
| :--- | :--- | :--- | :--- |
{chr(10).join(rows)}

> [!TIP]
> An efficiency ratio > 1.0 indicates a positive statistical expectancy at that time horizon.
"""
    return report
