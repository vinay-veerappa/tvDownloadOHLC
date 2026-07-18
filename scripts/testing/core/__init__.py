"""Core validation framework — base types, protocols, and utilities."""

from .base import (
    FeatureValidator,
    ValidationResult,
    FieldComparison,
    ComparisonStatus,
)
from .filter_engine import FilterEngine
from .api_client import WebUIClient
from .comparator import FieldComparator, compare_values
from .reporter import (
    MarkdownReporter,
    JsonReporter,
    format_validation_result,
    format_summary_table,
)

__all__ = [
    "FeatureValidator",
    "ValidationResult",
    "FieldComparison",
    "ComparisonStatus",
    "FilterEngine",
    "WebUIClient",
    "FieldComparator",
    "compare_values",
    "MarkdownReporter",
    "JsonReporter",
    "format_validation_result",
    "format_summary_table",
]
