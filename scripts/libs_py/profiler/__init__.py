"""
Profiler Library - Direct JSON access and filtering for the Institutional Daily Profiler.

Usage:
    from scripts.libs.profiler import ProfilerData, ProfilerFilter, ProfilerStats, ProfilerReport

    data = ProfilerData.load("NQ1")
    context = data.get_trading_day_context(date)   # prev sessions for filters
    matches = ProfilerFilter.filter(data, session="Asia", context=context)
    result = ProfilerStats.compute(matches, data)
    ProfilerReport.render(result, ticker="NQ1", session="Asia")
"""

from .loader import ProfilerData
from .filters import ProfilerFilter
from .stats import ProfilerStats, compute as compute_stats
from .report import ProfilerReport
from .context import get_live_context, get_current_trading_date, get_current_session
