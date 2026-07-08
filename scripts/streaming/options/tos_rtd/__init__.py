"""
tos_rtd
=======
ThinkorSwim RTD (Real-Time Data) COM client for futures options.

Windows-only package. Provides real-time Greeks, OI, volume, and last price
streaming directly from the TOS desktop application via COM — no REST API,
no rate limits, no auth tokens.

Usage::

    from scripts.streaming.options.tos_rtd import TOSRTDAdapter

    adapter = TOSRTDAdapter()
    adapter.start(symbols=["/ES", "/NQ"], expiry=date(2026, 7, 17))
    snapshot = adapter.get_snapshot()
    price = adapter.get_futures_price("/ES")
    adapter.stop()
"""
from __future__ import annotations

import sys

# Guard: entire package is Windows-only
if sys.platform != "win32":
    raise ImportError(
        "tos_rtd requires Windows (COM/pythoncom). "
        "This package is not available on this platform."
    )

from .quote_types import QuoteType
from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol
from .adapter import TOSRTDAdapter

__all__ = [
    "QuoteType",
    "OptionSymbolBuilder",
    "parse_rtd_option_symbol",
    "TOSRTDAdapter",
]