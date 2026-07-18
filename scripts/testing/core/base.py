"""
base.py — Core types and protocols for the validation framework.

Every WebUI feature validator implements the FeatureValidator protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple


class ComparisonStatus(str, Enum):
    """Status of a field-level comparison."""
    MATCH = "✅"
    MISMATCH = "⚠️"
    ERROR = "❌"
    SKIPPED = "⏭️"


@dataclass
class FieldComparison:
    """Result of comparing a single field between local and WebUI."""
    field_path: str
    local_value: Any
    webui_value: Any
    status: ComparisonStatus
    tolerance: float = 0.0
    diff: Optional[float] = None
    message: str = ""


@dataclass
class ValidationResult:
    """
    Result of validating a single filter combination for a feature.

    Each result contains:
      - The filter combination that was tested
      - Per-field comparison results
      - Summary statistics
      - Raw local and WebUI data for debugging
    """
    # Identification
    feature: str
    filter_key: str
    target_session: str
    ticker: str

    # Matching info
    local_count: int
    webui_count: Optional[int] = None

    # Comparisons
    field_comparisons: List[FieldComparison] = field(default_factory=list)
    summary: Dict[str, ComparisonStatus] = field(default_factory=dict)

    # Raw data for debugging
    local_data: Dict[str, Any] = field(default_factory=dict)
    webui_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def overall_status(self) -> ComparisonStatus:
        """Overall status: MATCH if all fields match, MISMATCH otherwise."""
        if self.error:
            return ComparisonStatus.ERROR
        if any(fc.status == ComparisonStatus.MISMATCH for fc in self.field_comparisons):
            return ComparisonStatus.MISMATCH
        return ComparisonStatus.MATCH

    @property
    def total_fields(self) -> int:
        return len(self.field_comparisons)

    @property
    def matched_fields(self) -> int:
        return sum(1 for fc in self.field_comparisons if fc.status == ComparisonStatus.MATCH)

    @property
    def mismatched_fields(self) -> int:
        return sum(1 for fc in self.field_comparisons if fc.status == ComparisonStatus.MISMATCH)


class FeatureValidator(Protocol):
    """
    Protocol that each WebUI feature validator must implement.

    A feature validator knows how to:
      1. Load local reference data for the feature
      2. Call the WebUI API for the same data
      3. Compare the two and produce ValidationResults
    """

    @property
    def name(self) -> str:
        """Human-readable feature name (e.g. 'profiler', 'candle-science')."""
        ...

    @property
    def description(self) -> str:
        """Short description of what this validator checks."""
        ...

    def get_filter_keys(self, ticker: str, target_session: str,
                        min_samples: int = 5) -> List[str]:
        """
        Return all filter keys to validate for this feature.

        Args:
            ticker: Ticker symbol.
            target_session: Target session name.
            min_samples: Minimum historical samples to include.

        Returns:
            List of filter key strings.
        """
        ...

    def validate(self, ticker: str, target_session: str,
                 filter_key: str) -> ValidationResult:
        """
        Validate a single filter combination.

        Args:
            ticker: Ticker symbol.
            target_session: Target session name.
            filter_key: Compact filter key string.

        Returns:
            ValidationResult with all field comparisons.
        """
        ...

    def get_target_sessions(self) -> List[str]:
        """Return the list of target sessions this feature supports."""
        ...

    def get_tickers(self) -> List[str]:
        """Return the list of tickers this feature supports."""
        ...
