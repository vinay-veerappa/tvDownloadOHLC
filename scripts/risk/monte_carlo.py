"""
Monte Carlo Simulation Engine for Trading Strategy Risk Assessment

Features:
- Block bootstrap resampling of trade sequences to preserve temporal dependencies.
- Stress scenario generation (e.g., 2008 GFC, 2020 COVID shock).
- Risk metrics: CVaR, drawdown, risk of ruin.
- Integration with rule-based constraints from `master_rule_catalog.json`.

Usage:
    from scripts.risk.monte_carlo import MonteCarloSimulator
    simulator = MonteCarloSimulator(trades, rules)
    results = simulator.run_block_bootstrap(iterations=1000, block_size=5)
    stress_results = simulator.run_stress_scenario(scenario="2008_gfc")
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import json
import os


@dataclass
class Trade:
    """Represents a single trade with P&L and metadata."""
    pnl: float
    duration: int  # Bars held
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    mae: float  # Maximum adverse excursion
    mfe: float  # Maximum favorable excursion


@dataclass
class RuleConstraint:
    """Represents a risk rule from `master_rule_catalog.json`."""
    name: str
    max_drawdown: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_position_size: Optional[int] = None
    max_leverage: Optional[float] = None
    max_consecutive_losses: Optional[int] = None


class MonteCarloSimulator:
    """Monte Carlo simulator for trading strategy risk assessment."""

    def __init__(
        self,
        trades: List[Trade],
        rules: Optional[List[RuleConstraint]] = None,
        initial_capital: float = 100_000,
    ):
        """
        Args:
            trades: List of historical trades.
            rules: List of rule constraints from `master_rule_catalog.json`.
            initial_capital: Starting capital for simulations.
        """
        self.trades = trades
        self.rules = rules or []
        self.initial_capital = initial_capital
        self.trade_pnl = np.array([trade.pnl for trade in trades])
        self.trade_durations = np.array([trade.duration for trade in trades])

    def _validate_rules(self, equity_curve: np.ndarray) -> bool:
        """Validate equity curve against rule constraints."""
        for rule in self.rules:
            drawdown = self._calculate_drawdown(equity_curve)
            if rule.max_drawdown and drawdown > rule.max_drawdown:
                return False
            if rule.max_daily_loss and self._calculate_max_daily_loss(equity_curve) > rule.max_daily_loss:
                return False
        return True

    def _calculate_drawdown(self, equity_curve: np.ndarray) -> float:
        """Calculate max drawdown from equity curve."""
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        return np.max(drawdown)

    def _calculate_max_daily_loss(self, equity_curve: np.ndarray) -> float:
        """Calculate max daily loss from equity curve."""
        daily_returns = np.diff(equity_curve) / equity_curve[:-1]
        return np.min(daily_returns)

    def run_block_bootstrap(
        self,
        iterations: int = 1000,
        block_size: int = 5,
        sizing_model: str = "fixed_lot",
    ) -> Dict[str, Union[float, np.ndarray]]:
        """
        Run block bootstrap Monte Carlo simulation.

        Args:
            iterations: Number of simulation iterations.
            block_size: Size of blocks for resampling (preserves temporal dependencies).
            sizing_model: Position sizing model ("fixed_lot", "fixed_fractional", "volatility_scaled").

        Returns:
            Dictionary of risk metrics:
            - cvar_95: Conditional Value at Risk at 95% confidence.
            - cvar_99: Conditional Value at Risk at 99% confidence.
            - max_drawdown: Worst drawdown across simulations.
            - risk_of_ruin: Probability of hitting 50% drawdown.
            - equity_curves: Array of all simulated equity curves.
        """
        n_trades = len(self.trades)
        n_blocks = int(np.ceil(n_trades / block_size))
        equity_curves = []

        for _ in range(iterations):
            # Resample blocks with replacement
            resampled_indices = np.random.choice(
                n_blocks, size=n_blocks, replace=True
            )
            resampled_pnl = np.concatenate([
                self.trade_pnl[i * block_size : (i + 1) * block_size]
                for i in resampled_indices
            ])
            
            # Apply position sizing
            if sizing_model == "fixed_fractional":
                resampled_pnl = self._apply_fixed_fractional(resampled_pnl)
            elif sizing_model == "volatility_scaled":
                resampled_pnl = self._apply_volatility_scaling(resampled_pnl)

            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(resampled_pnl)
            
            # Validate against rules
            if self._validate_rules(equity_curve):
                equity_curves.append(equity_curve)

        equity_curves = np.array(equity_curves)
        return self._calculate_risk_metrics(equity_curves)

    def _apply_fixed_fractional(self, pnl: np.ndarray) -> np.ndarray:
        """Apply fixed fractional position sizing."""
        # TODO: Implement fixed fractional sizing logic
        return pnl

    def _apply_volatility_scaling(self, pnl: np.ndarray) -> np.ndarray:
        """Apply volatility-scaled position sizing."""
        # TODO: Implement volatility scaling logic
        return pnl

    def run_stress_scenario(
        self,
        scenario: str = "2008_gfc",
        iterations: int = 1000,
    ) -> Dict[str, Union[float, np.ndarray]]:
        """
        Run stress scenario simulation.

        Args:
            scenario: Stress scenario ("2008_gfc", "2020_covid", "high_volatility").
            iterations: Number of simulation iterations.

        Returns:
            Dictionary of risk metrics (same as `run_block_bootstrap`).
        """
        if scenario == "2008_gfc":
            pnl_scaler = 0.7  # 30% reduction in P&L
            volatility_scaler = 2.0  # 2x volatility
        elif scenario == "2020_covid":
            pnl_scaler = 0.5  # 50% reduction in P&L
            volatility_scaler = 3.0  # 3x volatility
        elif scenario == "high_volatility":
            pnl_scaler = 1.0
            volatility_scaler = 2.5  # 2.5x volatility
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        equity_curves = []
        for _ in range(iterations):
            # Apply scenario adjustments
            scenario_pnl = self.trade_pnl * pnl_scaler
            scenario_pnl = self._apply_volatility_scaling(
                scenario_pnl * volatility_scaler
            )
            
            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(scenario_pnl)
            
            # Validate against rules
            if self._validate_rules(equity_curve):
                equity_curves.append(equity_curve)

        equity_curves = np.array(equity_curves)
        return self._calculate_risk_metrics(equity_curves)

    def _calculate_risk_metrics(
        self, equity_curves: np.ndarray
    ) -> Dict[str, Union[float, np.ndarray]]:
        """Calculate risk metrics from simulated equity curves."""
        final_equity = equity_curves[:, -1]
        returns = (final_equity - self.initial_capital) / self.initial_capital
        
        # CVaR (Conditional Value at Risk)
        cvar_95 = np.percentile(returns, 5)
        cvar_99 = np.percentile(returns, 1)
        
        # Max drawdown
        drawdowns = np.array([
            self._calculate_drawdown(curve) for curve in equity_curves
        ])
        max_drawdown = np.max(drawdowns)
        
        # Risk of ruin (50% drawdown)
        risk_of_ruin = np.mean(drawdowns >= 0.5)
        
        return {
            "cvar_95": cvar_95,
            "cvar_99": cvar_99,
            "max_drawdown": max_drawdown,
            "risk_of_ruin": risk_of_ruin,
            "equity_curves": equity_curves,
        }


def load_rules_from_catalog(catalog_path: str) -> List[RuleConstraint]:
    """Load rule constraints from `master_rule_catalog.json`."""
    with open(catalog_path, "r") as f:
        catalog = json.load(f)
    
    rules = []
    for rule_name, rule_data in catalog.items():
        rules.append(
            RuleConstraint(
                name=rule_name,
                max_drawdown=rule_data.get("max_drawdown"),
                max_daily_loss=rule_data.get("max_daily_loss"),
                max_position_size=rule_data.get("max_position_size"),
                max_leverage=rule_data.get("max_leverage"),
                max_consecutive_losses=rule_data.get("max_consecutive_losses"),
            )
        )
    return rules


if __name__ == "__main__":
    # Example usage
    from scripts.journal.trade_extractor import extract_trades

    # Load trades and rules
    trades = extract_trades("data/trades.csv")
    rules = load_rules_from_catalog("docs/profiler/master_rule_catalog.json")
    
    # Run simulation
    simulator = MonteCarloSimulator(trades, rules)
    results = simulator.run_block_bootstrap(iterations=1000, block_size=5)
    print(f"CVaR 95%: {results['cvar_95']:.2%}")
    print(f"Risk of Ruin: {results['risk_of_ruin']:.2%}")