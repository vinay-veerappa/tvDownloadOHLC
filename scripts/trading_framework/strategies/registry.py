"""
Strategy registry for dynamic discovery.
"""
from typing import Dict, Type, Any
from scripts.strategies.logic.box_reversion import BoxMeanReversionSignal

# Map of strategy names to their signal generation classes
STRATEGY_REGISTRY: Dict[str, Any] = {
    "box_reversion": BoxMeanReversionSignal,
    # Add other strategies as they are ported to the new framework
}

def get_strategy_class(name: str):
    """
    Resolve a strategy name to its class.
    """
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Strategy '{name}' not found in registry. Available: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name]
