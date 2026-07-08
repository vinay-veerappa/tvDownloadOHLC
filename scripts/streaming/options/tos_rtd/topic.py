"""
Topic management utilities for RTD subscriptions.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/utils/topic.py

Handles topic ID generation, lookup, and validation.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple, Union

from .quote_types import QuoteType


def generate_topic_id(quote_type: str, symbol: str) -> int:
    """Generate a deterministic 16-bit topic ID from quote_type + symbol."""
    value = f"{quote_type}:{symbol}"
    return int(hashlib.md5(value.encode()).hexdigest(), 16) % (2**16)


def find_topic_id(
    topics: Dict[int, Tuple[str, str]], symbol: str, quote_type: str
) -> Optional[int]:
    """Find the topic ID for a given symbol + quote_type."""
    for tid, (sym, qt) in topics.items():
        if sym == symbol and qt == quote_type:
            return tid
    return None


def validate_quote_type(quote_type: Union[str, QuoteType]) -> str:
    """Validate and normalize a quote type to its string value."""
    if isinstance(quote_type, QuoteType):
        return quote_type.value
    try:
        return QuoteType[str(quote_type).upper()].value
    except KeyError:
        raise ValueError(f"Invalid quote type: {quote_type}")


def get_subscriptions(topics: Dict[int, Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Get list of all active (symbol, quote_type) subscriptions."""
    return [(symbol, quote_type) for symbol, quote_type in topics.values()]


def is_subscribed(
    topics: Dict[int, Tuple[str, str]],
    quote_type: Union[str, QuoteType],
    symbol: str,
) -> bool:
    """Check if a specific quote_type + symbol is subscribed."""
    qt_str = validate_quote_type(quote_type)
    return find_topic_id(topics, symbol, qt_str) is not None


def get_topic_stats(topics: Dict[int, Tuple[str, str]]) -> Dict[str, int]:
    """Get statistics about topic subscriptions."""
    symbols = {sym for sym, _ in topics.values()}
    quote_types = {qt for _, qt in topics.values()}
    return {
        "total_topics": len(topics),
        "unique_symbols": len(symbols),
        "quote_types_count": len(quote_types),
    }