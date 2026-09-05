"""
DEAD STUB -- kept only so an old import does not vanish silently.

There is no `StrategyBase` in this repo and there never was. The spec that named
one (`BACKTEST_ENGINE_ARCHITECTURE.md`, deleted 2026-09-05) described an abstract
`generate_signals` / `get_required_features` / `get_search_space` interface that
**no strategy has ever implemented**, and the `IMPLEMENTATION_SPEC.md` this file
used to cite does not exist.

The live strategy contract is:

    class MyStrategy:
        def hunt(self, data: pd.DataFrame, params: dict) -> pd.DataFrame: ...
        def get_param_grid(self) -> dict: ...

All 15 registered strategies implement exactly that, and it is enforced by
`trading_framework/core/backtest_engine.py::validate_signal_geometry` and
`core/nt8_parity_backtester.py::_prepare_series`.

See docs/architecture/STRATEGY_WORKFLOW.md section 2.1 before writing a hunter.
Do not add a base class here -- register the strategy instead (section 2.5).
"""
