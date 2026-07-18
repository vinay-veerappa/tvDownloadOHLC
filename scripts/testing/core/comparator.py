"""
comparator.py — Generic field-by-field comparison engine.

Compares local reference data against WebUI API response data,
producing FieldComparison objects for each field.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Callable

from .base import FieldComparison, ComparisonStatus


class FieldComparator:
    """
    Compares local vs WebUI values field by field.

    Supports:
      - Exact match
      - Numeric tolerance match
      - Custom comparison functions
      - Nested dict traversal via dot-separated paths
    """

    def __init__(self, tolerance: float = 0.0):
        self.tolerance = tolerance
        self._custom_comparators: Dict[str, Callable] = {}

    def register_comparator(self, field_path: str, fn: Callable):
        """Register a custom comparison function for a field path."""
        self._custom_comparators[field_path] = fn

    def compare(
        self,
        field_path: str,
        local_val: Any,
        webui_val: Any,
        tolerance: Optional[float] = None,
    ) -> FieldComparison:
        """
        Compare a single field value.

        Args:
            field_path: Dot-separated path for identification.
            local_val: Value from local computation.
            webui_val: Value from WebUI API.
            tolerance: Override default tolerance for this field.

        Returns:
            FieldComparison with status.
        """
        # Check for custom comparator
        if field_path in self._custom_comparators:
            return self._custom_comparators[field_path](field_path, local_val, webui_val)

        tol = tolerance if tolerance is not None else self.tolerance

        # Both None → match
        if local_val is None and webui_val is None:
            return FieldComparison(field_path, None, None, ComparisonStatus.MATCH)

        # One None, one not → mismatch
        if local_val is None or webui_val is None:
            return FieldComparison(
                field_path, local_val, webui_val,
                ComparisonStatus.MISMATCH,
                message=f"One value is None: local={local_val}, webui={webui_val}",
            )

        # String comparison
        if isinstance(local_val, str) and isinstance(webui_val, str):
            if local_val == webui_val:
                return FieldComparison(field_path, local_val, webui_val, ComparisonStatus.MATCH)
            return FieldComparison(
                field_path, local_val, webui_val,
                ComparisonStatus.MISMATCH,
                message=f"'{local_val}' != '{webui_val}'",
            )

        # Numeric comparison with tolerance
        if isinstance(local_val, (int, float)) and isinstance(webui_val, (int, float)):
            diff = abs(float(local_val) - float(webui_val))
            if diff <= tol:
                return FieldComparison(
                    field_path, local_val, webui_val,
                    ComparisonStatus.MATCH, tolerance=tol, diff=diff,
                )
            return FieldComparison(
                field_path, local_val, webui_val,
                ComparisonStatus.MISMATCH, tolerance=tol, diff=diff,
                message=f"diff={diff:.4f} > tol={tol}",
            )

        # Fallback: exact equality
        if local_val == webui_val:
            return FieldComparison(field_path, local_val, webui_val, ComparisonStatus.MATCH)
        return FieldComparison(
            field_path, local_val, webui_val,
            ComparisonStatus.MISMATCH,
            message=f"{type(local_val).__name__} values differ",
        )

    def compare_dicts(
        self,
        local: Dict[str, Any],
        webui: Dict[str, Any],
        field_map: Dict[str, Tuple[str, Optional[float]]],
    ) -> List[FieldComparison]:
        """
        Compare two dicts using a field map.

        Args:
            local: Local reference data dict.
            webui: WebUI API response dict.
            field_map: Dict mapping local_field_path -> (webui_field_path, tolerance).
                       Use None tolerance to use default.

        Returns:
            List of FieldComparison objects.
        """
        results = []
        for local_path, (webui_path, tolerance) in field_map.items():
            lv = self._get_nested(local, local_path)
            wv = self._get_nested(webui, webui_path)
            results.append(self.compare(local_path, lv, wv, tolerance))
        return results

    @staticmethod
    def _get_nested(d: Dict[str, Any], path: str) -> Any:
        """Get a nested value from a dict using dot-separated path."""
        parts = path.split(".")
        current = d
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


def compare_values(local: Any, webui: Any, tolerance: float = 0.0) -> bool:
    """Simple value comparison helper."""
    if local is None and webui is None:
        return True
    if local is None or webui is None:
        return False
    if isinstance(local, (int, float)) and isinstance(webui, (int, float)):
        return abs(float(local) - float(webui)) <= tolerance
    return local == webui
