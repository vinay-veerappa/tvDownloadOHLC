import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import quantstats as qs
import os
import json

class QuantReporter:
    """
    Standardized Reporting Layer for the Statistical Trading Framework.
    Layer 7: Generates tear sheets and persists results.
    """
    
    def __init__(self, output_dir: str = "scripts/trading_framework/reporting/outputs", run_id: Optional[str] = None):
        if run_id:
            self.output_dir = os.path.join(output_dir, run_id)
        else:
            self.output_dir = output_dir
            
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_tear_sheet(self, returns: pd.Series, strategy_name: str, benchmark: str = "SPY") -> str:
        """
        Generate a comprehensive QuantStats HTML report.
        """
        output_path = os.path.join(self.output_dir, f"{strategy_name}_tearsheet.html")
        
        # Ensure returns are a pd.Series with a DatetimeIndex
        daily_returns = (1 + returns).resample('D').prod() - 1
        daily_returns = daily_returns[daily_returns != 0] # Remove non-trading days
        
        qs.reports.html(daily_returns, title=f"{strategy_name} Performance Report", output=output_path)
        return output_path

    def save_metadata(self, metadata: Dict[str, Any], filename: str = "run_metadata.json"):
        """
        Save run-specific parameters and metrics as JSON.
        """
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        return output_path

    def plot_equity_curve(self, equity_curve: pd.Series, strategy_name: str):
        """
        Generate a simple equity curve plot for quick preview.
        """
        plt.figure(figsize=(10, 6))
        plt.plot(equity_curve)
        plt.title(f"Equity Curve: {strategy_name}")
        plt.xlabel("Datetime")
        plt.ylabel("Cumulative Returns (normalized)")
        plt.grid(True)
        
        plot_path = os.path.join(self.output_dir, f"{strategy_name}_equity.png")
        plt.savefig(plot_path)
        plt.close()
        return plot_path
