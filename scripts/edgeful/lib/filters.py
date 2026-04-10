"""
Universal Filter Dimensions and Subreport Logic

Every report type in the platform is sliceable by the same set of dimensions.
This module defines those dimensions declaratively.

A "filter dimension" is a single axis (e.g., day_of_week, vix_regime) that can
be used in WHERE clauses, GROUP BY, or dashboard filter panels across all reports.

Usage:
    from edgeful.lib.filters import UNIVERSAL_FILTERS, FilterDimension
    
    # In dashboard: render filter buttons for each dimension
    for dim in UNIVERSAL_FILTERS:
        render_filter_control(dim.display_name, dim.values or dim.buckets)
    
    # In query builder: construct WHERE clause
    where_clause = " AND ".join([f"{dim.field} = '{value}'" for dim, value in active_filters])
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class FilterDimension:
    """
    A single filterable axis.
    
    Attributes:
        name: Internal identifier (e.g., "day_of_week")
        display_name: User-facing label (e.g., "Day of Week")
        field: Column name in parquet or DuckDB query
        type: "categorical", "numeric_bucket", or "date_range"
        values: For categorical: list of distinct values
        buckets: For numeric: list of (min, max, label) tuples
    """
    name: str
    display_name: str
    field: str
    type: str
    values: Optional[List[str]] = None
    buckets: Optional[List[Tuple[float, float, str]]] = None


# ── UNIVERSAL FILTERS ───────────────────────────────────────────────
# These are available on ALL reports and dimensions. Module-specific filters
# (e.g., range_width_category) are added by individual modules.

UNIVERSAL_FILTERS = [
    FilterDimension(
        "day_of_week", "Day of Week", "day_of_week", "categorical",
        values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    ),
    
    FilterDimension(
        "vix_regime", "VIX Regime", "vix_regime", "categorical",
        values=["LOW", "NORMAL", "HIGH", "EXTREME"]
    ),
    
    FilterDimension(
        "gap_direction", "Gap Direction", "gap_direction", "categorical",
        values=["UP", "DOWN", "NONE"]
    ),
    
    FilterDimension(
        "gap_size_bucket", "Gap Size", "gap_size_bucket", "categorical",
        values=["NONE", "SMALL", "MEDIUM", "LARGE"]
    ),
    
    FilterDimension(
        "open_vs_pd_range", "Open Location", "open_vs_pd_range", "categorical",
        values=["ABOVE_PDH", "INSIDE", "BELOW_PDL"]
    ),
    
    FilterDimension(
        "is_event_day", "Event Day", "is_event_day", "categorical",
        values=["Yes", "No"]
    ),
    
    FilterDimension(
        "is_opex_week", "OPEX Week", "is_opex_week", "categorical",
        values=["Yes", "No"]
    ),
    
    FilterDimension(
        "atr_respected", "ATR Respected", "atr_respected", "categorical",
        values=["Yes", "No"]
    ),
    
    FilterDimension(
        "session_direction", "Session Direction", "session_direction", "categorical",
        values=["GREEN", "RED"]
    ),
    
    FilterDimension(
        "streak_direction", "Streak Direction", "streak_direction", "categorical",
        values=["GREEN", "RED"]
    ),
    
    FilterDimension(
        "event_type", "Event Type", "event_type", "categorical",
        values=[
            "FOMC", "NFP", "CPI", "PPI",
            "OPEX", "ECB", "BOE", "BOJ",
            "PMI", "ISM", "GDP", "EARNINGS",
            "RETAIL", "HOUSING", "INCOME", "CLAIMS",
            "CONFERENCE", "DURABLE", "OIL", "ENERGY", "RATES"
        ]
    ),
    
    FilterDimension(
        "both_pd_broken", "Outside Day", "both_pd_broken", "categorical",
        values=["Yes", "No"]
    ),
    
    FilterDimension(
        "lookback_days", "Lookback Period", "__lookback__", "date_range"
    ),
]


# ── MODULE-SPECIFIC FILTERS (Examples) ────────────────────────────
# These are added by specific modules like macro, ranges, etc.

MACRO_FILTERS = [
    FilterDimension(
        "judas_direction", "Judas Direction", "judas_direction", "categorical",
        values=["BULL", "BEAR"]
    ),
    
    FilterDimension(
        "indicator_class", "Indicator Class", "indicator_class", "categorical",
        values=["ACCUM", "EXPANSION", "MANIP"]
    ),
    
    FilterDimension(
        "session_group", "Session", "session_group", "categorical",
        values=["ASIA", "LONDON", "NY_AM", "NY_PM"]
    ),
]

RANGE_FILTERS = [
    FilterDimension(
        "range_width_category", "Range Width", "range_width_category", "categorical",
        values=["NARROW", "NORMAL", "WIDE"]
    ),
    
    FilterDimension(
        "first_boundary_broken", "First Break", "first_boundary_broken", "categorical",
        values=["HIGH", "LOW"]
    ),
    
    FilterDimension(
        "close_vs_mid", "Close vs Mid", "close_vs_mid", "categorical",
        values=["ABOVE", "BELOW"]
    ),
    
    FilterDimension(
        "range_name", "Range Type", "range_name", "categorical",
        values=[
            "OR_5", "OR_15", "OR_30",
            "IB_30", "IB_60",
            "ASIA", "LONDON", "LUNCH", "NY_AM", "NY_PM",
            "OVERNIGHT", "PRIOR_DAY",
            "SILVER_BULLET_AM", "SILVER_BULLET_PM", "POWER_HOUR"
        ]
    ),
]


def get_filter_by_name(name: str, module_filters: List[FilterDimension] = None) -> Optional[FilterDimension]:
    """
    Look up a filter dimension by name.
    
    Searches UNIVERSAL_FILTERS first, then optional module-specific filters.
    """
    all_filters = UNIVERSAL_FILTERS.copy()
    if module_filters:
        all_filters.extend(module_filters)
    
    for f in all_filters:
        if f.name == name:
            return f
    
    return None


def build_filter_sql_expression(filters_dict: dict, module_filters: List[FilterDimension] = None) -> str:
    """
    Build a SQL WHERE clause from a dict of active filters.
    
    Args:
        filters_dict: Dict mapping filter_name -> selected_value (or list of values)
        module_filters: Optional list of module-specific FilterDimensions
    
    Returns:
        SQL WHERE fragment (without leading "WHERE")
    """
    clauses = []
    
    for filter_name, value in filters_dict.items():
        dim = get_filter_by_name(filter_name, module_filters)
        if not dim or not value:
            continue
        
        if isinstance(value, list):
            # Multiple values: IN clause
            quoted = [f"'{v}'" for v in value]
            clauses.append(f"{dim.field} IN ({','.join(quoted)})")
        else:
            # Single value
            if dim.type == "categorical":
                clauses.append(f"{dim.field} = '{value}'")
            else:
                clauses.append(f"{dim.field} = {value}")
    
    return " AND ".join(clauses) if clauses else "1=1"
