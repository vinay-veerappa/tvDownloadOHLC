import pytest

from scripts.screener.core.regime import get_market_regime, MarketRegimeState

def test_market_regime_evaluator():
    """Verify global market regime evaluator returns valid state."""
    regime = get_market_regime()
    assert isinstance(regime, MarketRegimeState)
    assert regime.status in ["BULL_EXPLOSIVE", "BULL_CHOPIER", "BEAR_PROTECTIVE"]
    assert isinstance(regime.is_macro_high_risk, bool)
