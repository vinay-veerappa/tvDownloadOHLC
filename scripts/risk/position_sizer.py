"""Position Sizing Risk Engine (Dump Pouch Python Implementation)

Calculates exact contract sizing based on account equity, risk percentage, stop loss distance in points,
and ticker-specific point/tick values from ticker_registry.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = REPO_ROOT / "scripts" / "config" / "ticker_registry.json"

log = logging.getLogger(__name__)

_DEFAULT_REGISTRY = {
    "NQ1": {"tick_size": 0.25, "tick_value": 5.0, "point_value": 20.0},
    "ES1": {"tick_size": 0.25, "tick_value": 12.5, "point_value": 50.0},
    "CL1": {"tick_size": 0.01, "tick_value": 10.0, "point_value": 1000.0},
    "GC1": {"tick_size": 0.10, "tick_value": 10.0, "point_value": 100.0},
}


def load_ticker_config(ticker: str) -> dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                registry = json.load(f)
                if ticker in registry:
                    return registry[ticker]
        except Exception as e:
            log.warning("Failed to load ticker registry: %s", e)
    return _DEFAULT_REGISTRY.get(ticker, {"tick_size": 0.25, "tick_value": 5.0, "point_value": 20.0})


def calculate_position_size(
    account_equity: float,
    risk_pct: float,
    stop_distance_points: float,
    ticker: str = "NQ1",
    max_contracts: int = 20,
) -> dict[str, Any]:
    """Calculates contract position size for a trade.
    
    Args:
        account_equity: Current account balance ($)
        risk_pct: Risk percentage per trade (e.g. 5.0 for 5%)
        stop_distance_points: Distance from entry to stop loss in points
        ticker: Futures ticker symbol (e.g. NQ1, ES1, CL1)
        max_contracts: Account cap on contract size
        
    Returns:
        Dict with dollars_at_risk, stop_distance_points, contract_count, point_value, risk_per_contract
    """
    cfg = load_ticker_config(ticker)
    point_val = cfg.get("point_value", 20.0)
    
    dollars_at_risk = account_equity * (risk_pct / 100.0)
    
    if stop_distance_points <= 0:
        return {
            "error": "Invalid stop distance (must be > 0)",
            "contract_count": 0,
            "dollars_at_risk": round(dollars_at_risk, 2),
        }

    risk_per_contract = stop_distance_points * point_val
    
    raw_contracts = dollars_at_risk / risk_per_contract if risk_per_contract > 0 else 0
    contract_count = max(1, min(int(raw_contracts), max_contracts)) if raw_contracts >= 1.0 else 0

    actual_risk = contract_count * risk_per_contract

    return {
        "ticker": ticker,
        "account_equity": account_equity,
        "risk_pct": risk_pct,
        "dollars_at_risk": round(dollars_at_risk, 2),
        "actual_risk": round(actual_risk, 2),
        "stop_distance_points": round(stop_distance_points, 2),
        "risk_per_contract": round(risk_per_contract, 2),
        "contract_count": contract_count,
        "point_value": point_val,
    }


if __name__ == "__main__":
    # Quick test
    res_nq = calculate_position_size(4500.0, 5.0, 10.0, "NQ1")  # $225 risk, 10 pt stop = 1.125 -> 1 contract ($200)
    res_es = calculate_position_size(4500.0, 5.0, 3.0, "ES1")   # $225 risk, 3 pt stop = $150/contract -> 1 contract
    print("NQ1 Sizing:", res_nq)
    print("ES1 Sizing:", res_es)
