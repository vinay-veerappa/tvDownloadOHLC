"""
Quote — represents a single RTD data update.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/utils/quote.py

Handles value type conversion (float/int/None) including the special
Treasury futures tick format (e.g. "109'080" → 109.25).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Union

from .quote_types import QuoteType

log = logging.getLogger(__name__)


class Quote:
    """A single RTD quote update with type-aware value processing."""

    # Quote types that should be floats
    FLOAT_TYPES = {
        QuoteType.LAST, QuoteType.BID, QuoteType.ASK, QuoteType.HIGH,
        QuoteType.LOW, QuoteType.OPEN, QuoteType.CLOSE, QuoteType.MARK,
        QuoteType.DELTA, QuoteType.GAMMA, QuoteType.THETA, QuoteType.VEGA,
        QuoteType.RHO, QuoteType.MARK_CHANGE, QuoteType.NET_CHANGE,
    }

    # Quote types that should be ints
    INT_TYPES = {
        QuoteType.VOLUME, QuoteType.ASK_SIZE, QuoteType.BID_SIZE,
        QuoteType.LAST_SIZE, QuoteType.OPEN_INT,
    }

    def __init__(
        self,
        quote_type: Union[str, QuoteType],
        symbol: str,
        value: Any,
        timestamp: Optional[float] = None,
    ):
        self.quote_type = self._parse_quote_type(quote_type)
        self.symbol = symbol
        self.value = self._process_value(value)
        self.timestamp = timestamp or time.time()

    @staticmethod
    def _parse_quote_type(quote_type: Union[str, QuoteType]) -> QuoteType:
        if isinstance(quote_type, QuoteType):
            return quote_type
        if isinstance(quote_type, str):
            try:
                return QuoteType[quote_type.upper()]
            except KeyError:
                raise ValueError(f"Invalid quote type: {quote_type}")
        raise ValueError(f"Invalid quote type: {quote_type}")

    def _process_value(self, value: Any) -> Any:
        """Convert raw RTD value to appropriate Python type."""
        if value is None or value in ("N/A", "!N/A"):
            return None

        if self.quote_type in self.FLOAT_TYPES:
            return self._to_float(value)
        elif self.quote_type in self.INT_TYPES:
            return self._to_int(value)
        elif self.quote_type == QuoteType.IMPL_VOL:
            float_value = self._to_float(value)
            return round(float_value, 4) if float_value is not None else None
        return value

    @staticmethod
    def _to_float(value: Any, percentage: bool = False) -> Optional[float]:
        """
        Convert value to float, handling Treasury futures format.

        Examples:
            "109'080" -> 109.25  (109 + 8/32)
            "123'165" -> 123.515625 (123 + 16.5/32)
        """
        try:
            if isinstance(value, str):
                # Treasury futures format: "109'080"
                if "'" in value:
                    whole, ticks = value.split("'")
                    whole_num = float(whole)
                    ticks_num = float(ticks[:2])
                    if len(ticks) > 2 and ticks[2] == "5":
                        ticks_num += 0.5
                    return whole_num + (ticks_num / 32)
                value = value.rstrip("%")
            return float(value)
        except (ValueError, TypeError) as e:
            log.debug("Error converting value %r: %s", value, e)
            return None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def __str__(self) -> str:
        if self.value is None:
            return "N/A"
        if isinstance(self.value, float):
            if self.quote_type == QuoteType.IMPL_VOL:
                return f"{self.value:.2%}"
            if self.quote_type in (QuoteType.DELTA, QuoteType.GAMMA):
                return f"{self.value:.4f}"
            return f"${self.value:.2f}"
        if isinstance(self.value, int):
            return f"{self.value:,}"
        return str(self.value)

    def __repr__(self) -> str:
        return (
            f"Quote(type={self.quote_type!r}, symbol='{self.symbol}', "
            f"value={self.value!r}, timestamp={self.timestamp})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quote_type": self.quote_type.value,
            "symbol": self.symbol,
            "value": self.value,
            "timestamp": self.timestamp,
        }